"""T-325 ★★ — THE VERIFIER CROSS-CHECK. The reason Phase 3B exists.

``PROJECT_PLAN §9.6`` names the trap this answers: *"The groundedness metric is
circular. The system enforces groundedness, then measures it. Groundedness =
0.98 proves only that the filter ran."*

These pairs break the circle. The claims are sentences **humans wrote** in
published surveys; the evidence is the paper **those humans chose to cite**.
Nothing here touched our Planner, Retriever, Extractor or Writer. If the
verifier agrees with human citation practice at scale, that is evidence no
reviewer can dismiss as self-confirming.

**What "agreement" means, and its ceiling.** A human citing paper X for claim C
asserts that X supports C, so ``SUPPORT`` is the expected label and the
agreement rate is the fraction the verifier calls ``SUPPORT``. That ceiling is
**not** 1.0, and it should not be reported as accuracy:

* Survey authors cite for background, contrast, methodology provenance and
  courtesy — not only for direct evidential support.
* The abstract is not the cited *content*. Authors cite a paper's results
  section through its abstract, which may not restate them.
* SciReviewGen's markers come from S2ORC's automatic linking, so some are
  simply mis-linked.

⚠️ **Expect this to look worse than SciFact, and report the drop as the honest
finding.** SciFact is expert-curated, single-sentence, deliberately-entailing
evidence. This is real survey prose. Sarol et al. measured **0.59 micro-F1** on
real citations against much higher curated-benchmark scores
(``SESSION_CONTEXT §5.2``). A large gap here is the *result*, not a bug.

**Scoring matches deployment, not convenience.** The verifier was trained on
``(claim, single evidence sentence)`` and the pipeline scores claims against
retrieved *spans*, never whole documents. So the abstract is split into
sentences and the pair is scored **max over sentences** — the best-supporting
span wins, which is exactly what T-502 will do. The whole-abstract variant is
also reported, because the difference between them measures how much the
span-level framing is worth.

Run::

    python -m researchgpt.eval.scireviewgen_crosscheck
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter
from typing import Any

from researchgpt.eval.scireviewgen_pairs import split_sentences
from researchgpt.verify.evaluate import predict_proba_onnx
from researchgpt.verify.labels import ID2LABEL, LABELS

DEFAULT_PAIRS = pathlib.Path("data/scireviewgen/pairs.jsonl")
DEFAULT_MODEL = pathlib.Path("data/models/verifier-onnx/fp32")
DEFAULT_OUT = pathlib.Path("eval/scireviewgen_crosscheck_t325.json")

#: T-503 / VerifierConfig.support_threshold. Biased toward precision because
#: CliVER measured a 21% false-Support rate and over-predicting "supported" is
#: the dangerous direction for a hallucination filter.
SUPPORT_THRESHOLD = 0.7

#: Abstracts run long; beyond this the tail is boilerplate and the cost is real.
MAX_SENTENCES = 15
#: A fragment cannot support anything; scoring it only adds noise to the max.
MIN_SENTENCE_CHARS = 25


def _summarise(
    name: str,
    verdicts: list[str],
    scores: list[float],
    argmax_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Report both thresholded and argmax agreement.

    They answer different questions and the gap between them is diagnostic: a
    large gap means the model ranks SUPPORT top but below the 0.7 confidence
    bar, so the disagreement is the *threshold's* doing, not the model's. A
    small gap means the model genuinely does not see support.
    """
    counts = Counter(verdicts)
    n = len(verdicts) or 1
    agree = counts.get("SUPPORT", 0)
    mean_score = sum(scores) / n
    print(f"\n  {name}")
    print(f"    {'verdict':12s} {'n':>6s} {'share':>8s}")
    for label in LABELS:
        c = counts.get(label, 0)
        print(f"    {label:12s} {c:6d} {c / n:8.1%}")
    print(f"    {'AGREEMENT':12s} {agree:6d} {agree / n:8.1%}   "
          f"(P(SUPPORT) >= threshold)")
    result = {
        "agreement_rate": agree / n,
        "counts": {label: counts.get(label, 0) for label in LABELS},
        "mean_p_support": mean_score,
        "n": len(verdicts),
    }
    if argmax_labels is not None:
        am = sum(1 for x in argmax_labels if x == "SUPPORT")
        print(f"    {'argmax':12s} {am:6d} {am / n:8.1%}   "
              f"(SUPPORT is simply the top class - no threshold)")
        result["argmax_agreement_rate"] = am / n
        result["argmax_counts"] = dict(Counter(argmax_labels))
    print(f"    mean P(SUPPORT) = {mean_score:.3f}")
    return result


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-325 - verifier cross-check on human citations.")
    ap.add_argument("--pairs", type=pathlib.Path, default=DEFAULT_PAIRS)
    ap.add_argument("--model", type=pathlib.Path, default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--threshold", type=float, default=SUPPORT_THRESHOLD)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    onnx = next(args.model.glob("*quantized*.onnx"), None) or next(args.model.glob("*.onnx"))
    pairs = [json.loads(line) for line in args.pairs.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    if args.limit:
        pairs = pairs[: args.limit]

    print("T-325 - verifier cross-check against human-authored citations")
    print(f"  pairs : {len(pairs):,}  from {args.pairs}")
    print(f"  model : {onnx.name}")
    print(f"  P(SUPPORT) threshold: {args.threshold}\n")

    # --- span-level: the deployment-faithful scoring -----------------------
    flat: list[dict[str, str]] = []
    spans_per_pair: list[int] = []
    for pair in pairs:
        sentences = [s for s in split_sentences(pair["evidence"])
                     if len(s) >= MIN_SENTENCE_CHARS][:MAX_SENTENCES]
        if not sentences:
            sentences = [pair["evidence"]]
        spans_per_pair.append(len(sentences))
        for sentence in sentences:
            flat.append({"claim": pair["claim"], "evidence": sentence})

    print(f"  scoring {len(flat):,} (claim, evidence-sentence) spans "
          f"({sum(spans_per_pair) / len(spans_per_pair):.1f} per pair) ...")
    proba = predict_proba_onnx(str(onnx), str(args.model), flat, batch_size=16)

    span_verdicts: list[str] = []
    span_argmax: list[str] = []
    span_scores: list[float] = []
    offset = 0
    per_pair: list[dict[str, Any]] = []
    for pair, k in zip(pairs, spans_per_pair, strict=True):
        block = proba[offset : offset + k]
        offset += k
        best = int(block[:, 0].argmax())          # column 0 == SUPPORT
        p_support = float(block[best, 0])
        row = block[best]
        verdict = "SUPPORT" if p_support >= args.threshold else ID2LABEL[int(row.argmax())]
        span_argmax.append(ID2LABEL[int(row.argmax())])
        span_verdicts.append(verdict)
        span_scores.append(p_support)
        per_pair.append({
            "bib_id": pair["bib_id"],
            "chapter_id": pair["chapter_id"],
            "p_support": p_support,
            "verdict": verdict,
            "best_span_index": best,
            "n_spans": k,
        })

    span = _summarise(
        "SPAN-LEVEL  (max over evidence sentences - matches T-502 deployment)",
        span_verdicts, span_scores, span_argmax,
    )

    # --- whole-abstract: the naive variant, for contrast -------------------
    print(f"\n  scoring {len(pairs):,} (claim, whole-abstract) pairs for contrast ...")
    whole_proba = predict_proba_onnx(str(onnx), str(args.model), pairs, batch_size=16)
    whole_verdicts = [
        "SUPPORT" if float(r[0]) >= args.threshold else ID2LABEL[int(r.argmax())]
        for r in whole_proba
    ]
    whole = _summarise(
        "WHOLE-ABSTRACT  (naive: one 256-token window, truncated)",
        whole_verdicts, [float(r[0]) for r in whole_proba],
        [ID2LABEL[int(r.argmax())] for r in whole_proba],
    )

    delta = span["agreement_rate"] - whole["agreement_rate"]
    print(f"\n  span-level scoring is worth {delta:+.1%} agreement over "
          f"whole-abstract scoring.")

    print("\n" + "=" * 72)
    print(f"T-325 AGREEMENT RATE: {span['agreement_rate']:.1%} "
          f"({span['counts']['SUPPORT']:,} of {span['n']:,})")
    print("=" * 72)
    print("Report this NEXT TO the SciFact held-out number (T-305) and the")
    print("50-claim spot-check (T-705) - three independent lenses, not one score.")
    print("A gap below SciFact is EXPECTED and is the honest finding: human")
    print("citation practice includes background and contrast, not only support.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "task": "T-325",
        "pairs_file": str(args.pairs),
        "model": str(onnx),
        "support_threshold": args.threshold,
        "span_level": span,
        "whole_abstract": whole,
        "span_advantage": delta,
        "mean_spans_per_pair": sum(spans_per_pair) / len(spans_per_pair),
        "note": (
            "Agreement = fraction the verifier labels SUPPORT. The ceiling is NOT "
            "1.0: authors cite for background, contrast and provenance, abstracts "
            "may not restate the cited content, and S2ORC's marker linking is "
            "automatic. Compare against Sarol et al. 0.59 micro-F1 on real "
            "citations, not against SciFact."
        ),
        "per_pair": per_pair,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
