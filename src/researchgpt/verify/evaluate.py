"""T-305 — stock vs fine-tuned verifier, on the same untouched held-out set.

This is the headline result that justifies the training component, and a graded
deliverable in its own right (TASKLIST T-305). It also implements the **T-307
escalation gate**: macro-F1 below :data:`ESCALATION_THRESHOLD` on the held-out
set means retrain at ``deberta-v3-base``.

Two details here are load-bearing and easy to get silently wrong.

**1. Pair order is (evidence, claim), not (claim, evidence).**
The cross-encoder is an NLI model: input is ``(premise, hypothesis)``. The
evidence sentence is the premise and the claim is the hypothesis being tested
against it. Reversing them trains and scores a subtly different task and costs
several F1 points for no visible reason. :func:`encode_pair` is the single
place this order is decided; the training notebook imports the same convention.

**2. The stock head is in a different order from ours.**
``cross-encoder/nli-deberta-v3-*`` emits ``{0: contradiction, 1: entailment,
2: neutral}``; :data:`~researchgpt.verify.labels.LABELS` is ``(SUPPORT,
CONTRADICT, NEI)``. A naive argmax comparison scores the stock model near
chance *for the wrong reason* and would make the fine-tune look far better than
it is. :func:`label_permutation` derives the mapping from the checkpoint's own
``config.id2label`` at load time and raises if it cannot — it never guesses.

Run::

    # stock zero-shot baseline only
    python -m researchgpt.verify.evaluate --stock cross-encoder/nli-deberta-v3-small

    # the full T-305 table, once Kaggle returns the checkpoint
    python -m researchgpt.verify.evaluate \\
        --stock cross-encoder/nli-deberta-v3-small \\
        --tuned data/models/verifier-scifact
"""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

from researchgpt.verify.labels import LABEL2ID, LABELS, NLI_TO_VERDICT
from researchgpt.verify.scifact_pairs import read_jsonl

#: T-307 escalation gate. Decided in `decisions.txt` D-09 (2026-08-27):
#: "escalate if macro-F1 on the held-out SciFact validation split is below 0.75".
#: Fixed *before* the first training run, so the decision is not post-hoc.
ESCALATION_THRESHOLD = 0.75

#: The verified escalation target. Same tokenizer family, ~184M vs ~44M.
ESCALATION_MODEL = "cross-encoder/nli-deberta-v3-base"

DEFAULT_PAIRS = pathlib.Path("data/scifact/pairs_validation.jsonl")


def encode_pair(pair: dict[str, Any]) -> tuple[str, str]:
    """The one place the (premise, hypothesis) order is decided.

    Premise = the evidence sentence. Hypothesis = the claim under test.
    Training and inference must both call this; do not inline the tuple.
    """
    return pair["evidence"], pair["claim"]


def label_permutation(id2label: dict[int, str]) -> list[int]:
    """Column indices that reorder a checkpoint's logits into ``LABELS`` order.

    ``logits[:, permutation]`` puts SUPPORT first, CONTRADICT second, NEI third.

    Accepts either a head already trained in our vocabulary (``SUPPORT``/...)
    or a stock NLI head (``entailment``/``contradiction``/``neutral``). Raises
    on anything else rather than guessing — a wrong permutation is invisible in
    the output and poisons every number downstream.
    """
    normalised: dict[str, int] = {}
    for idx, raw in id2label.items():
        name = str(raw).strip()
        verdict = name.upper() if name.upper() in LABEL2ID else NLI_TO_VERDICT.get(name.lower())
        if verdict is None:
            raise ValueError(
                f"Cannot map checkpoint label {raw!r} onto {LABELS}. "
                f"Checkpoint id2label={id2label}. Refusing to guess a permutation."
            )
        normalised[verdict] = int(idx)

    missing = [label for label in LABELS if label not in normalised]
    if missing:
        raise ValueError(f"Checkpoint head is missing {missing}; id2label={id2label}")
    return [normalised[label] for label in LABELS]


# --------------------------------------------------------------------------
# Prediction
# --------------------------------------------------------------------------


def predict_torch(
    model_path: str,
    pairs: list[dict[str, Any]],
    *,
    batch_size: int = 32,
    max_length: int = 256,
    device: str = "cpu",
) -> list[int]:
    """Score ``pairs`` with a HF sequence-classification checkpoint.

    Returns predicted class indices in ``LABELS`` order, permutation applied.
    """
    import torch  # noqa: PLC0415
    from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.eval().to(device)

    permutation = label_permutation(model.config.id2label)

    preds: list[int] = []
    with torch.no_grad():
        for start in range(0, len(pairs), batch_size):
            batch = pairs[start : start + batch_size]
            premises = [encode_pair(p)[0] for p in batch]
            hypotheses = [encode_pair(p)[1] for p in batch]
            enc = tokenizer(
                premises,
                hypotheses,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            ).to(device)
            logits = model(**enc).logits[:, permutation]
            preds.extend(logits.argmax(dim=-1).tolist())
    return preds


def predict_proba_onnx(
    onnx_path: str,
    tokenizer_path: str,
    pairs: list[dict[str, Any]],
    *,
    batch_size: int = 32,
    max_length: int = 256,
) -> Any:
    """Softmax probabilities in ``LABELS`` order, shape ``(len(pairs), 3)``.

    T-503 defines ``support_score`` as a softmax probability, so probabilities
    - not argmax - are what the pipeline actually consumes. :func:`predict_onnx`
    is a thin argmax over this.

    ⚠️ ``batch_size`` defaults to 32 for throughput on short inputs, but T-306
    measured batch=1 to be **faster** on this model - padding waste dominates.
    Callers that care about latency should pass ``batch_size=1``.
    """
    import numpy as np  # noqa: PLC0415
    import onnxruntime as ort  # noqa: PLC0415
    from transformers import AutoConfig, AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
    config = AutoConfig.from_pretrained(tokenizer_path)
    permutation = label_permutation(config.id2label)

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_names = {i.name for i in session.get_inputs()}

    chunks: list[Any] = []
    for start in range(0, len(pairs), batch_size):
        batch = pairs[start : start + batch_size]
        enc = tokenizer(
            [encode_pair(p)[0] for p in batch],
            [encode_pair(p)[1] for p in batch],
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="np",
        )
        feeds = {k: v.astype(np.int64) for k, v in enc.items() if k in input_names}
        logits = session.run(None, feeds)[0][:, permutation]
        # Subtract the row max before exp: raw logits reach +-15 here and a
        # plain exp overflows to inf, which silently becomes nan after division.
        shifted = logits - logits.max(axis=-1, keepdims=True)
        exp = np.exp(shifted)
        chunks.append(exp / exp.sum(axis=-1, keepdims=True))
    return np.concatenate(chunks, axis=0) if chunks else np.zeros((0, len(LABELS)))


def predict_onnx(
    onnx_path: str,
    tokenizer_path: str,
    pairs: list[dict[str, Any]],
    *,
    batch_size: int = 32,
    max_length: int = 256,
) -> list[int]:
    """Score ``pairs`` with the T-304 ONNX model. Same contract as the torch path."""
    proba = predict_proba_onnx(
        onnx_path, tokenizer_path, pairs, batch_size=batch_size, max_length=max_length
    )
    return proba.argmax(axis=-1).tolist()


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def score(y_true: list[int], y_pred: list[int]) -> dict[str, Any]:
    """Per-class precision / recall / F1 plus macro-F1, accuracy, confusion.

    Written out rather than pulled from sklearn so the notebook can reuse it on
    Kaggle without an extra import, and so the zero-division convention is
    explicit: a class the model never predicts scores precision 0, not NaN.
    """
    n_classes = len(LABELS)
    confusion = [[0] * n_classes for _ in range(n_classes)]
    for true, pred in zip(y_true, y_pred, strict=True):
        confusion[true][pred] += 1

    per_class: dict[str, dict[str, float]] = {}
    f1s: list[float] = []
    for i, label in enumerate(LABELS):
        tp = confusion[i][i]
        fp = sum(confusion[j][i] for j in range(n_classes)) - tp
        fn = sum(confusion[i]) - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(confusion[i]),
        }
        f1s.append(f1)

    correct = sum(confusion[i][i] for i in range(n_classes))
    total = len(y_true) or 1
    return {
        "per_class": per_class,
        "macro_f1": sum(f1s) / n_classes,
        "accuracy": correct / total,
        "confusion": confusion,
        "n": len(y_true),
    }


def format_report(name: str, result: dict[str, Any]) -> str:
    lines = [
        f"{name}   n={result['n']}  accuracy={result['accuracy']:.3f}  "
        f"macro-F1={result['macro_f1']:.3f}",
        f"  {'class':12s} {'P':>7s} {'R':>7s} {'F1':>7s} {'support':>8s}",
    ]
    for label, m in result["per_class"].items():
        lines.append(
            f"  {label:12s} {m['precision']:7.3f} {m['recall']:7.3f} "
            f"{m['f1']:7.3f} {m['support']:8d}"
        )
    lines.append(f"  confusion (rows=true {list(LABELS)}, cols=pred):")
    for i, row in enumerate(result["confusion"]):
        lines.append(f"    {LABELS[i]:12s} {row}")
    return "\n".join(lines)


def format_comparison(stock: dict[str, Any], tuned: dict[str, Any]) -> str:
    """The T-305 table: the two-row result the report and deck both need."""
    lines = [
        "T-305 - STOCK vs FINE-TUNED (same held-out set)",
        "",
        f"  {'arm':14s} {'acc':>7s} {'macro-F1':>9s} "
        + " ".join(f"{label[:9]+' F1':>13s}" for label in LABELS),
    ]
    for name, result in (("stock", stock), ("fine-tuned", tuned)):
        row = f"  {name:14s} {result['accuracy']:7.3f} {result['macro_f1']:9.3f} "
        row += " ".join(f"{result['per_class'][label]['f1']:13.3f}" for label in LABELS)
        lines.append(row)
    delta = tuned["macro_f1"] - stock["macro_f1"]
    lines.append(f"  {'delta':14s} {tuned['accuracy'] - stock['accuracy']:+7.3f} {delta:+9.3f}")
    return "\n".join(lines)


def escalation_verdict(macro_f1: float) -> str:
    """T-307. The threshold was fixed in decisions.txt D-09 before any training."""
    if macro_f1 < ESCALATION_THRESHOLD:
        return (
            f"T-307 GATE: ESCALATE. macro-F1 {macro_f1:.3f} < {ESCALATION_THRESHOLD}. "
            f"Retrain at {ESCALATION_MODEL} (same notebook, change BASE_MODEL). "
            f"Latency is not a constraint (TASKLIST 0.2); the only cost is Kaggle time."
        )
    return (
        f"T-307 GATE: PASS. macro-F1 {macro_f1:.3f} >= {ESCALATION_THRESHOLD}. "
        f"Keep deberta-v3-small and spend the Kaggle quota on T-332 (reranker)."
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-305 - stock vs fine-tuned verifier.")
    ap.add_argument("--stock", default="cross-encoder/nli-deberta-v3-small",
                    help="stock checkpoint scored zero-shot via the label permutation")
    ap.add_argument("--tuned", default=None,
                    help="fine-tuned checkpoint dir from T-303; omit to report stock only")
    ap.add_argument("--onnx", default=None,
                    help="score the tuned arm through this ONNX model instead of torch (T-304)")
    ap.add_argument("--pairs", type=pathlib.Path, default=DEFAULT_PAIRS)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--limit", type=int, default=None, help="score only the first N pairs")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("eval/verifier_t305.json"))
    args = ap.parse_args(argv)

    pairs = read_jsonl(args.pairs)
    if args.limit:
        pairs = pairs[: args.limit]
    y_true = [LABEL2ID[p["label"]] for p in pairs]
    print(f"held-out set: {args.pairs}  ({len(pairs)} pairs)\n")

    results: dict[str, Any] = {}

    print(f"scoring stock: {args.stock}")
    stock = score(y_true, predict_torch(args.stock, pairs, batch_size=args.batch_size))
    print(format_report("stock", stock) + "\n")
    results["stock"] = {"model": args.stock, **{k: v for k, v in stock.items()}}

    tuned = None
    if args.onnx:
        source = f"{args.onnx} (ONNX int8)"
        print(f"scoring fine-tuned: {source}")
        preds = predict_onnx(args.onnx, args.tuned or args.stock, pairs,
                             batch_size=args.batch_size)
        tuned = score(y_true, preds)
    elif args.tuned:
        source = args.tuned
        print(f"scoring fine-tuned: {source}")
        tuned = score(y_true, predict_torch(args.tuned, pairs, batch_size=args.batch_size))

    if tuned is not None:
        print(format_report("fine-tuned", tuned) + "\n")
        print(format_comparison(stock, tuned) + "\n")
        print(escalation_verdict(tuned["macro_f1"]))
        results["tuned"] = {"model": source, **{k: v for k, v in tuned.items()}}
        results["escalation"] = {
            "threshold": ESCALATION_THRESHOLD,
            "macro_f1": tuned["macro_f1"],
            "escalate": tuned["macro_f1"] < ESCALATION_THRESHOLD,
        }
    else:
        print("(no --tuned checkpoint given: stock baseline only)")
        print(f"\nFor reference, the T-307 gate is macro-F1 >= {ESCALATION_THRESHOLD}.")

    results["labels"] = list(LABELS)
    results["pairs_file"] = str(args.pairs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
