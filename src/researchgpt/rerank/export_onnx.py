"""T-333 — export the fine-tuned reranker to ONNX + int8, same path as the verifier.

`TRAINING_SPEC §2.5` is explicit about the trap here: *"Quantization must not be
assumed free — verify the tuned-quantized model still beats stock on the
adoption gate."*

🔴 **That warning is not hypothetical — it already fired on the verifier.**
T-304 measured int8 as free on the *stock* DeBERTa checkpoint (macro-F1 actually
rose 0.516 → 0.539) and then, on the *fine-tuned* one, as a 0.027 loss that
dropped the deployed model **below its own T-307 gate**. The lesson generalises:
**a quantization result measured on one checkpoint says nothing about another.**

So this exports **both** graphs and gates neither here. The ranking comparison
that decides which ships is T-334/T-335 in :mod:`researchgpt.rerank.evaluate`,
run against the project's own bibliography — because for a *reranker*, per-pair
logit fidelity is not the quantity of interest at all. Only the induced
**ordering** matters, and a model whose scores all shift by a constant ranks
identically. Gating on logit drift would be measuring the wrong thing twice
over.

What is checked here is **export correctness**: ONNX fp32 must reproduce the
PyTorch scores, and the int8 graph must at least preserve the *ordering* of a
candidate list. Those are cheap and they catch a broken export.

Run::

    python -m researchgpt.rerank.export_onnx --checkpoint data/models/reranker-scireviewgen
"""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

DEFAULT_OUT = pathlib.Path("data/models/reranker-onnx")

#: ONNX fp32 must be a faithful re-encoding of the PyTorch graph.
FP32_TOLERANCE = 1e-3

#: Kendall-tau floor for the int8 ordering check. Not a ship/no-ship gate -
#: T-335 is - but an export that scrambles rank order is broken, not quantized.
INT8_MIN_KENDALL_TAU = 0.9


def _probe_pairs(n: int = 32) -> list[tuple[str, str]]:
    """Realistic (query, abstract) pairs from the T-330 triples, if present."""
    path = pathlib.Path("data/rerank/train_triples.jsonl")
    if not path.exists():
        return [(f"query {i}", f"candidate abstract number {i} about retrieval") for i in range(n)]
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
            if len(rows) >= n:
                break
    return [(r["query"], r["text"]) for r in rows]


def export(checkpoint: str, out_dir: pathlib.Path, *, max_length: int = 512) -> dict[str, Any]:
    import numpy as np
    import onnxruntime as ort
    import torch
    from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
    from scipy.stats import kendalltau
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    out_dir.mkdir(parents=True, exist_ok=True)
    fp32_dir = out_dir / "fp32"
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)

    print(f"[1/4] exporting {checkpoint} -> ONNX fp32")
    ORTModelForSequenceClassification.from_pretrained(
        checkpoint, export=True
    ).save_pretrained(fp32_dir)
    tokenizer.save_pretrained(fp32_dir)

    print("[2/4] dynamic int8 quantization (per_channel=True)")
    ORTQuantizer.from_pretrained(fp32_dir).quantize(
        save_dir=out_dir,
        quantization_config=AutoQuantizationConfig.avx2(is_static=False, per_channel=True),
    )
    tokenizer.save_pretrained(out_dir)
    int8_path = next(out_dir.glob("*quantized*.onnx"), None) or next(out_dir.glob("*.onnx"))
    fp32_path = next(fp32_dir.glob("*.onnx"))

    print(f"[3/4] score parity on {len(_probe_pairs())} realistic pairs")
    pairs = _probe_pairs()
    enc_pt = tokenizer([p[0] for p in pairs], [p[1] for p in pairs], padding=True,
                       truncation=True, max_length=max_length, return_tensors="pt")
    torch_model = AutoModelForSequenceClassification.from_pretrained(checkpoint).eval()
    with torch.no_grad():
        torch_scores = torch_model(**enc_pt).logits.squeeze(-1).numpy()

    enc_np = tokenizer([p[0] for p in pairs], [p[1] for p in pairs], padding=True,
                       truncation=True, max_length=max_length, return_tensors="np")

    def run(path: pathlib.Path) -> Any:
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        names = {i.name for i in session.get_inputs()}
        feeds = {k: v.astype(np.int64) for k, v in enc_np.items() if k in names}
        return session.run(None, feeds)[0].squeeze(-1)

    fp32_scores, int8_scores = run(fp32_path), run(int8_path)

    fp32_delta = float(np.abs(torch_scores - fp32_scores).max())
    fp32_ok = fp32_delta <= FP32_TOLERANCE
    int8_delta = float(np.abs(torch_scores - int8_scores).max())
    # For a reranker only the induced ORDER matters. A uniform score shift is
    # harmless; a reshuffle is not.
    tau = float(kendalltau(torch_scores, int8_scores).statistic)
    int8_ok = tau >= INT8_MIN_KENDALL_TAU

    print(f"      ONNX fp32  max|dscore| {fp32_delta:.6f} (tol {FP32_TOLERANCE})  "
          f"{'PASS' if fp32_ok else 'FAIL'}")
    print(f"      ONNX int8  max|dscore| {int8_delta:.6f}  "
          f"Kendall tau vs torch {tau:.4f} (min {INT8_MIN_KENDALL_TAU})  "
          f"{'PASS' if int8_ok else 'FAIL'}")

    report = {
        "task": "T-333",
        "checkpoint": checkpoint,
        "onnx_fp32": {"max_abs_score_delta": fp32_delta, "tolerance": FP32_TOLERANCE,
                      "pass": fp32_ok},
        "onnx_int8": {"max_abs_score_delta": int8_delta, "kendall_tau": tau,
                      "min_tau": INT8_MIN_KENDALL_TAU, "pass": int8_ok},
        "paths": {"fp32": str(fp32_path), "int8": str(int8_path)},
        "sizes_mb": {"onnx_fp32": round(fp32_path.stat().st_size / 1e6, 2),
                     "onnx_int8": round(int8_path.stat().st_size / 1e6, 2)},
        "note": (
            "Neither graph is gated here. Which one ships is decided by T-335 on "
            "ranking quality against the project's own bibliography, because for a "
            "reranker only the induced ordering matters. See TRAINING_SPEC 2.5 and "
            "the T-304 precedent, where int8 was free on a stock checkpoint and "
            "costly on the fine-tuned one."
        ),
    }
    print(f"[4/4] size: fp32 {report['sizes_mb']['onnx_fp32']} MB "
          f"-> int8 {report['sizes_mb']['onnx_int8']} MB")
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-333 - reranker ONNX + int8 export.")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--max-length", type=int, default=512)
    args = ap.parse_args(argv)

    print(f"T-333 - reranker ONNX export\n  checkpoint: {args.checkpoint}\n")
    report = export(args.checkpoint, args.out, max_length=args.max_length)

    path = args.out / "export_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")

    if not report["onnx_fp32"]["pass"]:
        raise SystemExit(
            "T-333 FAILED: ONNX fp32 does not reproduce PyTorch. The export is "
            "broken - do not blame quantization."
        )
    if not report["onnx_int8"]["pass"]:
        raise SystemExit(
            f"T-333 FAILED: int8 reshuffles the ranking (tau "
            f"{report['onnx_int8']['kendall_tau']:.3f}). Re-export with "
            f"--no-per-channel, or ship fp32."
        )
    print("T-333 PASS: export is faithful and int8 preserves rank order.")
    print("Next: python -m researchgpt.rerank.evaluate --tuned <checkpoint>  (T-334/T-335)")


if __name__ == "__main__":
    main()
