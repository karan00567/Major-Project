"""T-304 — export the trained verifier to ONNX + int8, and prove it still works.

The pipeline runs on CPU with no torch at inference time (``pyproject.toml``'s
``verify`` extra deliberately omits torch), so the Kaggle checkpoint has to
become an ONNX graph before ``agents/verifier.py`` can use it.

**The acceptance criterion is a parity check, not a successful export.** An
export that silently produces garbage still "succeeds". Two separate checks,
because they fail for different reasons:

``PyTorch -> ONNX fp32``  logits must agree to ~1e-3 **and** argmax 100%.
                          This is the *export correctness* test. Measured
                          2026-08-27 on the stock checkpoint: max |dlogit|
                          **8e-6**, argmax 20/20, and identical macro-F1 on the
                          full 628-pair held-out set (0.516 both ways).

``ONNX fp32 -> int8``     gated on **macro-F1 over the whole held-out set**,
                          not on per-pair argmax.

⚠️ **The int8 gate was originally per-pair argmax agreement on 20 examples, and
that was the wrong test.** Measured on the stock checkpoint, dynamic int8 flips
**2 of 20** individual decisions and moves single logits by up to 4.2 — which
looks alarming — yet over the full 628-pair set it costs *nothing*:

    ONNX fp32               accuracy 0.553   macro-F1 0.516
    int8 per_channel=False  accuracy 0.554   macro-F1 0.538
    int8 per_channel=True   accuracy 0.556   macro-F1 0.539

The flips go both ways and cancel. A 20-sample argmax gate would have rejected
a quantization that is demonstrably free, so the gate now measures the thing
that actually matters. DeBERTa's disentangled attention is genuinely
quantization-sensitive per-logit; it just does not matter in aggregate.

⚠️ **Measured again on the FINE-TUNED checkpoint (2026-08-27), the conclusion
reversed — and the shipped artefact is now fp32, not int8.** The stock model
happened to be quantization-tolerant; the trained one is not:

    arm                     macro-F1   vs 0.75 gate   claims/sec   size
    fp32                       0.769   PASS                 41.9   568 MB
    int8 per_channel=True      0.741   FAIL                 52.3   173 MB
    int8 per_channel=False     0.741   FAIL                 20.5   173 MB

**int8 drops the deployed model below the T-307 gate that the trained model
passes.** All int8 buys is 10 seconds per run (48 s vs 38 s for 2,000 claims,
against a ~30-minute budget) and 400 MB of disk. `TASKLIST` §0.2 and
`PROJECT_PLAN` §4.2 both say the same thing about exactly this trade — *"trade
latency, not accuracy — the verifier is the graded component"* — so fp32 wins on
the project's own stated rule, not on preference.

This export therefore keeps **both** graphs, gates each against the T-307
threshold independently, and records ``recommended_model`` /
``recommended_path`` in ``export_report.json``. **T-502 must load the path that
report names**, not a hard-coded filename — which artefact wins is a property of
the checkpoint, and it already flipped once between the stock and tuned models.

*(`per_channel=False` is strictly dominated: same accuracy, half the speed.)*

Run::

    # after downloading and unzipping the Kaggle output
    python -m researchgpt.verify.export_onnx --checkpoint data/models/verifier-scifact

    # dry-run the whole path against the stock checkpoint, before Kaggle returns
    python -m researchgpt.verify.export_onnx --checkpoint cross-encoder/nli-deberta-v3-small
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
from typing import Any

from researchgpt.verify.evaluate import ESCALATION_THRESHOLD, encode_pair
from researchgpt.verify.labels import LABELS
from researchgpt.verify.scifact_pairs import read_jsonl

DEFAULT_PAIRS = pathlib.Path("data/scifact/pairs_validation.jsonl")
DEFAULT_OUT = pathlib.Path("data/models/verifier-onnx")

#: ONNX fp32 must be a faithful re-encoding of the PyTorch graph.
FP32_TOLERANCE = 1e-3


def _tokenize(tokenizer: Any, pairs: list[dict[str, Any]], max_length: int, framework: str):
    return tokenizer(
        [encode_pair(p)[0] for p in pairs],
        [encode_pair(p)[1] for p in pairs],
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors=framework,
    )


def export(
    checkpoint: str,
    out_dir: pathlib.Path,
    *,
    pairs: list[dict[str, Any]],
    eval_pairs: list[dict[str, Any]] | None = None,
    max_length: int = 256,
    per_channel: bool = True,
) -> dict[str, Any]:
    """Export, quantize, and parity-check. Returns the report dict.

    ``pairs`` drives the fast per-logit parity check; ``eval_pairs`` (the full
    held-out set) drives the int8 accuracy gate. Passing ``None`` for the latter
    skips the gate and leaves the export ungated — useful only for a dry run.
    """
    import numpy as np
    import torch
    from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    out_dir.mkdir(parents=True, exist_ok=True)
    fp32_dir = out_dir / "fp32"
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)

    print(f"[1/4] exporting {checkpoint} -> ONNX fp32")
    ort_model = ORTModelForSequenceClassification.from_pretrained(checkpoint, export=True)
    ort_model.save_pretrained(fp32_dir)
    tokenizer.save_pretrained(fp32_dir)

    print(f"[2/4] dynamic int8 quantization (per_channel={per_channel})")
    quantizer = ORTQuantizer.from_pretrained(fp32_dir)
    # avx2 rather than avx512_vnni: the VNNI graph is faster but silently
    # unsupported on older cores, and a demo that will not start on the
    # examiner's machine is worse than one that is slow.
    qconfig = AutoQuantizationConfig.avx2(is_static=False, per_channel=per_channel)
    quantizer.quantize(save_dir=out_dir, quantization_config=qconfig)
    tokenizer.save_pretrained(out_dir)

    int8_path = next(out_dir.glob("*quantized*.onnx"), None) or next(out_dir.glob("*.onnx"))
    print(f"      int8 graph: {int8_path.name}")

    print(f"[3/4] parity check on {len(pairs)} held-out pairs")
    torch_model = AutoModelForSequenceClassification.from_pretrained(checkpoint).eval()
    enc_pt = _tokenize(tokenizer, pairs, max_length, "pt")
    with torch.no_grad():
        logits_torch = torch_model(**enc_pt).logits.numpy()

    enc_np = _tokenize(tokenizer, pairs, max_length, "np")

    import onnxruntime as ort

    def run(path: pathlib.Path) -> Any:
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        names = {i.name for i in session.get_inputs()}
        feeds = {k: v.astype(np.int64) for k, v in enc_np.items() if k in names}
        return session.run(None, feeds)[0]

    fp32_path = next(fp32_dir.glob("*.onnx"))
    logits_fp32 = run(fp32_path)
    logits_int8 = run(int8_path)

    def logit_delta(name: str, other: Any) -> dict[str, Any]:
        delta = float(np.abs(logits_torch - other).max())
        agree = int((logits_torch.argmax(-1) == other.argmax(-1)).sum())
        print(f"      {name:10s} max|dlogit| {delta:.6f}  argmax agrees {agree}/{len(pairs)}")
        return {"max_abs_logit_delta": delta, "argmax_agreement": agree, "n": len(pairs)}

    fp32_parity = logit_delta("ONNX fp32", logits_fp32)
    fp32_parity["tolerance"] = FP32_TOLERANCE
    # The export test: fp32 ONNX must be numerically indistinguishable from torch.
    fp32_parity["pass"] = (
        fp32_parity["max_abs_logit_delta"] <= FP32_TOLERANCE
        and fp32_parity["argmax_agreement"] == len(pairs)
    )
    print(f"      -> export correctness: {'PASS' if fp32_parity['pass'] else 'FAIL'}")

    # int8 per-logit drift is recorded but NOT gated on: it is large per-pair and
    # ~zero in aggregate. See the module docstring for the measurement.
    int8_parity = logit_delta("ONNX int8", logits_int8)

    report: dict[str, Any] = {
        "task": "T-304",
        "checkpoint": checkpoint,
        "labels": list(LABELS),
        "per_channel": per_channel,
        "onnx_fp32": fp32_parity,
        "onnx_int8_logit_drift": int8_parity,
        "int8_model": str(int8_path),
        "sizes_mb": {
            "onnx_fp32": round(fp32_path.stat().st_size / 1e6, 2),
            "onnx_int8": round(int8_path.stat().st_size / 1e6, 2),
        },
    }
    print(
        f"[4/4] size: fp32 {report['sizes_mb']['onnx_fp32']} MB "
        f"-> int8 {report['sizes_mb']['onnx_int8']} MB"
    )

    if eval_pairs:
        from researchgpt.verify.evaluate import predict_onnx, score
        from researchgpt.verify.labels import LABEL2ID

        print(f"\n[gate] int8 accuracy over the full held-out set ({len(eval_pairs)} pairs)")
        y_true = [LABEL2ID[p["label"]] for p in eval_pairs]
        fp32_score = score(y_true, predict_onnx(str(fp32_path), str(fp32_dir), eval_pairs))
        int8_score = score(y_true, predict_onnx(str(int8_path), str(out_dir), eval_pairs))
        drop = fp32_score["macro_f1"] - int8_score["macro_f1"]
        # ⚠️ Gate each artefact against T-307 directly. Gating only on the *drop*
        # was the earlier mistake: a small drop still lands the shipped model
        # under the gate when the trained model sits close to it.
        fp32_ok = fp32_score["macro_f1"] >= ESCALATION_THRESHOLD
        int8_ok = int8_score["macro_f1"] >= ESCALATION_THRESHOLD
        for name, sc, ok in (("fp32", fp32_score, fp32_ok), ("int8", int8_score, int8_ok)):
            print(f"      {name}  accuracy {sc['accuracy']:.3f}  "
                  f"macro-F1 {sc['macro_f1']:.3f}  "
                  f"vs T-307 gate {ESCALATION_THRESHOLD}: {'PASS' if ok else 'FAIL'}")
        print(f"      macro-F1 lost to quantization: {drop:+.3f}")

        if int8_ok:
            recommended = "int8"
            why = "int8 clears the T-307 gate and is smaller and faster"
        elif fp32_ok:
            recommended = "fp32"
            why = (f"int8 falls to {int8_score['macro_f1']:.3f}, under the "
                   f"{ESCALATION_THRESHOLD} gate that fp32 clears. TASKLIST 0.2: "
                   f"trade latency, not accuracy - the verifier is the graded component")
        else:
            recommended = "fp32"
            why = "NEITHER artefact clears the T-307 gate - escalate the model (T-307)"

        report["int8_accuracy_gate"] = {
            "fp32": {"accuracy": fp32_score["accuracy"], "macro_f1": fp32_score["macro_f1"],
                     "pass": fp32_ok},
            "int8": {"accuracy": int8_score["accuracy"], "macro_f1": int8_score["macro_f1"],
                     "pass": int8_ok},
            "macro_f1_drop": drop,
            "t307_threshold": ESCALATION_THRESHOLD,
            "n": len(eval_pairs),
            "pass": fp32_ok or int8_ok,
        }
        report["recommended_model"] = recommended
        report["recommended_reason"] = why
        report["recommended_path"] = str(fp32_path if recommended == "fp32" else int8_path)
        print(f"\n      SHIP: {recommended}  ({why})")

    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-304 - ONNX + int8 export with parity check.")
    ap.add_argument("--checkpoint", required=True,
                    help="the unzipped Kaggle output dir, or any HF model id for a dry run")
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--pairs", type=pathlib.Path, default=DEFAULT_PAIRS)
    ap.add_argument("--n", type=int, default=20, help="held-out pairs for the parity check")
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--per-channel", dest="per_channel", action="store_true", default=True)
    ap.add_argument("--no-per-channel", dest="per_channel", action="store_false")
    ap.add_argument("--quick", action="store_true",
                    help="skip the full-set int8 accuracy gate (leaves the export UNGATED)")
    ap.add_argument("--discard-fp32", action="store_true",
                    help="delete the fp32 graph after exporting. ONLY safe if int8 clears "
                         "the T-307 gate - on the 2026-08-27 checkpoint it does not.")
    args = ap.parse_args(argv)

    all_pairs = read_jsonl(args.pairs)
    print(f"T-304 - ONNX export\n  checkpoint: {args.checkpoint}\n  out: {args.out}\n")

    report = export(
        args.checkpoint,
        args.out,
        pairs=all_pairs[: args.n],
        eval_pairs=None if args.quick else all_pairs,
        max_length=args.max_length,
        per_channel=args.per_channel,
    )

    if args.discard_fp32:
        shutil.rmtree(args.out / "fp32", ignore_errors=True)
        print("\n      removed the fp32 graph as requested")

    report_path = args.out / "export_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {report_path}")

    if not report["onnx_fp32"]["pass"]:
        raise SystemExit(
            "T-304 FAILED: ONNX fp32 does not reproduce PyTorch. The export itself is "
            "broken - do not ship it, and do not blame quantization."
        )
    gate = report.get("int8_accuracy_gate")
    if gate and not gate["pass"]:
        raise SystemExit(
            f"T-304 FAILED: neither fp32 ({gate['fp32']['macro_f1']:.3f}) nor int8 "
            f"({gate['int8']['macro_f1']:.3f}) clears the T-307 gate of "
            f"{gate['t307_threshold']}. This is a MODEL problem, not an export problem - "
            f"escalate to deberta-v3-base per T-307."
        )
    if gate:
        rec = report["recommended_model"]
        print(f"\nT-304 PASS: export is faithful. SHIP THE {rec.upper()} MODEL:")
        print(f"  {report['recommended_path']}")
        print(f"  reason: {report['recommended_reason']}")
    else:
        print("\nT-304 PARTIAL: export is faithful, but --quick skipped the accuracy "
              "gate. Re-run without --quick before shipping.")


if __name__ == "__main__":
    main()
