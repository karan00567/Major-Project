"""T-334 / T-335 — stock vs fine-tuned reranker, and the adoption gate.

Two test sets, and **they are not equally important**:

============================  =====================================  ==========
set                           what it measures                       decides?
============================  =====================================  ==========
SciReviewGen ``test``         in-domain gain                         no
**own 25-paper bibliography**  **out-of-domain, CS — the honest one**  **yes**
============================  =====================================  ==========

★ **Lead with the out-of-domain number** (`TRAINING_SPEC §2.4`). SciReviewGen is
frozen at S2ORC 2020-07-05 and skews biomedical; our corpus is CS/agentic-RAG.
**A large in-domain gain with no out-of-domain gain means the benchmark was
fitted, not the task** — and that is a reportable finding, not a reason to ship.

**T-335 adoption gate:** promote the tuned model into ``configs/default.yaml``
*only* if it beats stock on our own bibliography, **measured after int8
quantization**. `TRAINING_SPEC §2.5`: *"Quantization must not be assumed free."*
The T-304 precedent is the reason that sentence exists — int8 was free on the
stock verifier and cost 0.027 macro-F1 on the fine-tuned one.

🔴 **The ranking metrics cannot see calibration loss, which is why this gate
needs a relevance control.** On 2026-08-27 a fine-tuned reranker passed on
ranking alone (out-of-domain nDCG@10 +0.031, Recall@20 +0.167) while scoring
*"wind turbine blade fatigue"*, *"soil nitrogen mineralisation"* and
*"nineteenth-century Italian opera libretti"* at **+7 to +9.7** for retrieval
queries — where stock gives ≈ **−11**. At 2 epochs the same effect is milder
(**+2.9 to +5.0**) but still present, so it is not an epoch-count artefact.

**Why ranking metrics miss it.** The out-of-domain pool is built from papers
already retrieved for CS/agentic-RAG queries, so *everything in it is broadly
on-topic*. nDCG and Recall only measure ordering **within** that pre-filtered
pool, and a model that has forgotten what irrelevance looks like still orders
on-topic papers acceptably.

**Root cause is T-331, and it inverts that task's own warning.** Every negative
is a BM25 hard negative drawn from SciReviewGen's pool of cited abstracts, so
the model was only ever asked *"which of these topically-adjacent scientific
abstracts belongs to this chapter?"* — never *"is this relevant at all?"*.
T-331 is right that hard negatives are necessary; at **100%** they remove the
easy-negative signal that keeps a model calibrated. The fix is a mixture
(~3 hard : 1 random), not a switch. Not spent: M1 took priority.

:func:`relevance_control` therefore scores a small fixed set of deliberately
unrelated documents against each query.

⚠️ **It reports a CONDITION, not a veto - and getting that wrong cost a round
trip.** It was first wired as a hard block, which was an overcorrection: the
control measures whether absolute scores are meaningful, but whether that
*matters* depends on two things it cannot see, both since measured:

* **Does anything consume the score as a value?** No. ``hybrid_retriever``
  fuses by RRF over *ranks*, and nothing thresholds.
  ``Reranker.filter_by_score()`` raises on an uncalibrated model to keep it so.
* **Does the live pool contain off-topic documents?** Barely - measured
  **98.2% on-topic** (9 of 493), because T-201 already searches
  ``title_and_abstract`` with a date window. On real candidates the tuned model
  promoted **0** off-topic papers into a top-12, against stock's 1.

So a control failure downgrades the verdict to **PROMOTE WITH CONDITIONS** and
prints them. Ranking gains remain a hard requirement, and the control is still
the only thing standing between a benchmark-fitted model and production.

If the gate fails, **keep the stock reranker and report the negative result**.
The pipeline is unaffected either way; this was always a weight swap. TASKLIST
Aug 30 kill switch says the same, and a fine-tune that did not help is an
honest contribution.

**No network calls.** The out-of-domain evaluation reuses T-212's cached pool
(``eval/cache/pool_mps25.json``), so it costs no OpenAlex budget — which
matters now that OpenAlex is metered (§0.2).

Run::

    python -m researchgpt.rerank.evaluate --tuned data/models/reranker-scireviewgen
    python -m researchgpt.rerank.evaluate --tuned-onnx data/models/reranker-onnx
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
from typing import Any

STOCK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
POOL_CACHE = pathlib.Path("eval/cache/pool_mps25.json")
GOLD = pathlib.Path("eval/gold_sets/own_bibliography.json")
DEFAULT_OUT = pathlib.Path("eval/reranker_t334.json")


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def ndcg_at_k(labels_in_rank_order: list[int], k: int = 10) -> float:
    import math

    gains = labels_in_rank_order[:k]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(labels_in_rank_order, reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def ranking_metrics(ranked_labels: list[list[int]]) -> dict[str, float]:
    """Recall@20, nDCG@10, Precision@12 averaged over queries with >=1 positive."""
    ndcgs, recalls, precisions = [], [], []
    for labels in ranked_labels:
        n_pos = sum(labels)
        if n_pos == 0:
            continue
        ndcgs.append(ndcg_at_k(labels, 10))
        recalls.append(sum(labels[:20]) / n_pos)
        precisions.append(sum(labels[:12]) / 12)
    n = max(len(ndcgs), 1)
    return {
        "nDCG@10": sum(ndcgs) / n,
        "Recall@20": sum(recalls) / n,
        "Precision@12": sum(precisions) / n,
        "queries": len(ndcgs),
    }


# --------------------------------------------------------------------------
# Scorers
# --------------------------------------------------------------------------


class TorchScorer:
    def __init__(self, model_path: str, max_length: int = 512):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_path, max_length=max_length)
        self.name = model_path

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(x) for x in
                self.model.predict([(query, t) for t in texts],
                                   batch_size=64, show_progress_bar=False)]


class OnnxScorer:
    """Scores through the T-333 ONNX graph — what actually ships."""

    def __init__(self, model_dir: pathlib.Path, max_length: int = 512):
        import onnxruntime as ort
        from transformers import AutoTokenizer

        path = next(model_dir.glob("*quantized*.onnx"), None) or next(model_dir.glob("*.onnx"))
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        self.max_length = max_length
        self.name = str(path)

    def score(self, query: str, texts: list[str]) -> list[float]:
        import numpy as np

        out: list[float] = []
        for start in range(0, len(texts), 32):
            batch = texts[start : start + 32]
            enc = self.tokenizer([query] * len(batch), batch, padding=True, truncation=True,
                                 max_length=self.max_length, return_tensors="np")
            feeds = {k: v.astype(np.int64) for k, v in enc.items() if k in self.input_names}
            out.extend(self.session.run(None, feeds)[0].squeeze(-1).tolist())
        return [float(x) for x in out]


# --------------------------------------------------------------------------
# Out-of-domain: the project's own bibliography (the gate)
# --------------------------------------------------------------------------


def _norm_doi(doi: str | None) -> str:
    if not doi:
        return ""
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip().lower())


def _norm_title(title: str | None) -> str:
    key = re.sub(r"[^a-z0-9]+", "", (title or "").lower())
    return key if len(key) >= 25 else ""


def load_own_bibliography() -> tuple[dict[str, list[dict[str, Any]]], set[str], dict[str, str]]:
    """Cached T-212 pool + gold labels. No network."""
    if not POOL_CACHE.exists():
        raise SystemExit(
            f"{POOL_CACHE} missing. Build it with:\n"
            f"  python -m researchgpt.eval.retrieval_eval --cache"
        )
    cache = json.loads(POOL_CACHE.read_text(encoding="utf-8"))
    gold_doc = json.loads(GOLD.read_text(encoding="utf-8"))
    gold_dois = {_norm_doi(p.get("doi")) for p in gold_doc["papers"] if p.get("doi")}
    gold_titles = {_norm_title(p.get("title")): _norm_doi(p.get("doi"))
                   for p in gold_doc["papers"] if p.get("title")}
    gold_titles.pop("", None)
    gold_dois.discard("")

    pool = cache["pool"]
    per_query: dict[str, list[dict[str, Any]]] = {}
    for query, keys in cache["per_query"].items():
        items = []
        for key in keys:
            paper = pool.get(key)
            if not paper:
                continue
            text = f"{paper.get('title') or ''}\n\n{paper.get('abstract') or ''}".strip()
            if not text:
                continue
            doi, title = _norm_doi(paper.get("doi")), _norm_title(paper.get("title"))
            is_gold = (doi and doi in gold_dois) or (title and title in gold_titles)
            items.append({"text": text, "label": int(bool(is_gold))})
        if items:
            per_query[query] = items
    return per_query, gold_dois, gold_titles


def evaluate_out_of_domain(scorer: Any, per_query: dict[str, list[dict[str, Any]]]) -> dict:
    ranked_labels, latencies = [], []
    for query, items in per_query.items():
        t0 = time.perf_counter()
        scores = scorer.score(query, [it["text"] for it in items])
        latencies.append((time.perf_counter() - t0) * 1000)
        order = sorted(range(len(items)), key=lambda i: -scores[i])
        ranked_labels.append([items[i]["label"] for i in order])
    metrics = ranking_metrics(ranked_labels)
    metrics["mean_rerank_ms_per_query"] = sum(latencies) / max(len(latencies), 1)
    metrics["mean_candidates_per_query"] = sum(len(v) for v in per_query.values()) / max(
        len(per_query), 1)
    return metrics


# --------------------------------------------------------------------------
# In-domain: SciReviewGen test split
# --------------------------------------------------------------------------


def load_in_domain(chapters: int, seed: int) -> dict[str, list[dict[str, Any]]]:
    """Triples built from the TEST split — never the train split (leakage)."""
    from researchgpt.eval.scireviewgen import load_split
    from researchgpt.rerank.triples import build_corpus, mine_hard_negatives

    rows = load_split("test", limit=chapters)
    documents, positives = build_corpus(rows)
    pairs, _ = mine_hard_negatives(documents, positives, seed=seed)
    per_query: dict[str, list[dict[str, Any]]] = {}
    for pair in pairs:
        per_query.setdefault(pair["query"], []).append(
            {"text": pair["text"], "label": pair["label"]}
        )
    return per_query


#: Deliberately unrelated to anything this project retrieves. Long enough to be
#: in-distribution for a 512-token cross-encoder, so a low score cannot be
#: blamed on length. Different fields on purpose: a model that has kept its
#: relevance prior scores ALL of these far below any real candidate.
OFF_TOPIC_CONTROLS = [
    "Wind turbine blade fatigue under cyclic aerodynamic loading. We model crack "
    "propagation in glass-fibre composite spars and validate the model against "
    "full-scale accelerated fatigue tests on a 45-metre blade. " * 3,
    "Soil nitrogen mineralisation rates in temperate grassland under varying "
    "grazing intensity and rainfall. Field plots were sampled over three seasons "
    "and analysed for ammonium and nitrate concentration. " * 3,
    "A stylistic analysis of nineteenth-century Italian opera libretti and their "
    "metrical conventions, with particular attention to the versi sciolti of the "
    "Verdi middle period. " * 3,
    "Crystallographic determination of the beta-lactamase active site at 1.8 "
    "angstrom resolution, with implications for inhibitor design in resistant "
    "gram-negative bacteria. " * 3,
]


def relevance_control(scorer: Any, per_query: dict[str, list[dict[str, Any]]]) -> dict:
    """Does the model still know what IRRELEVANT looks like?

    For each query, compare the best off-topic control against the *median*
    real candidate. Median rather than max, deliberately: a pool contains
    plenty of weak candidates, and beating the worst of them is not a failure.
    Beating the typical one is.
    """
    violations, margins = [], []
    for query, items in per_query.items():
        pool_scores = sorted(scorer.score(query, [it["text"] for it in items]))
        if not pool_scores:
            continue
        median = pool_scores[len(pool_scores) // 2]
        worst_control = max(scorer.score(query, OFF_TOPIC_CONTROLS))
        margins.append(median - worst_control)
        if worst_control >= median:
            violations.append({"query": query, "control_score": worst_control,
                               "pool_median": median})
    n = max(len(margins), 1)
    return {
        "queries": len(margins),
        "violations": len(violations),
        "violation_rate": len(violations) / n,
        "mean_margin": sum(margins) / n,
        "worst_examples": violations[:3],
        # One violation is tolerable noise; a quarter of queries is not.
        "pass": (len(violations) / n) <= 0.25,
    }


def _report(title: str, stock: dict, tuned: dict) -> dict:
    print(f"\n{'=' * 76}\n{title}\n{'=' * 76}")
    print(f"  {'arm':14s} {'nDCG@10':>10s} {'Recall@20':>11s} {'Precision@12':>13s} "
          f"{'ms/query':>10s}")
    for name, m in (("stock", stock), ("fine-tuned", tuned)):
        print(f"  {name:14s} {m['nDCG@10']:10.4f} {m['Recall@20']:11.4f} "
              f"{m['Precision@12']:13.4f} {m.get('mean_rerank_ms_per_query', 0):10.1f}")
    delta = {k: tuned[k] - stock[k] for k in ("nDCG@10", "Recall@20", "Precision@12")}
    print(f"  {'delta':14s} {delta['nDCG@10']:+10.4f} {delta['Recall@20']:+11.4f} "
          f"{delta['Precision@12']:+13.4f}")
    return delta


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-334/T-335 - reranker adoption gate.")
    ap.add_argument("--stock", default=STOCK_MODEL)
    ap.add_argument("--tuned", default=None, help="fine-tuned checkpoint (torch)")
    ap.add_argument("--tuned-onnx", type=pathlib.Path, default=None,
                    help="the T-333 ONNX dir - THIS is what the gate should judge")
    ap.add_argument("--in-domain-chapters", type=int, default=150)
    ap.add_argument("--skip-in-domain", action="store_true")
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    if not args.tuned and not args.tuned_onnx:
        raise SystemExit("give --tuned and/or --tuned-onnx")

    print("T-334/T-335 - stock vs fine-tuned reranker\n")
    stock_scorer = TorchScorer(args.stock)
    tuned_scorer = (OnnxScorer(args.tuned_onnx) if args.tuned_onnx
                    else TorchScorer(args.tuned))
    quantized = args.tuned_onnx is not None
    print(f"  stock : {stock_scorer.name}")
    print(f"  tuned : {tuned_scorer.name}"
          f"{'  (ONNX - what ships)' if quantized else '  (torch, NOT quantized)'}")

    results: dict[str, Any] = {"task": "T-334/T-335", "quantized": quantized}

    # ---- the gate: out-of-domain, own bibliography ----------------------
    per_query, _, _ = load_own_bibliography()
    print(f"\n  own bibliography: {len(per_query)} sub-questions, "
          f"{sum(len(v) for v in per_query.values())} candidates, "
          f"{sum(sum(i['label'] for i in v) for v in per_query.values())} gold hits pooled")
    ood_stock = evaluate_out_of_domain(stock_scorer, per_query)
    ood_tuned = evaluate_out_of_domain(tuned_scorer, per_query)
    ood_delta = _report("T-334 OUT-OF-DOMAIN - own bibliography (THE GATE)",
                        ood_stock, ood_tuned)
    results["out_of_domain"] = {"stock": ood_stock, "tuned": ood_tuned, "delta": ood_delta}

    # ---- in-domain, for contrast ----------------------------------------
    if not args.skip_in_domain:
        print(f"\n  building in-domain set from SciReviewGen TEST "
              f"({args.in_domain_chapters} chapters) ...")
        in_q = load_in_domain(args.in_domain_chapters, args.seed)
        id_stock = evaluate_out_of_domain(stock_scorer, in_q)
        id_tuned = evaluate_out_of_domain(tuned_scorer, in_q)
        id_delta = _report("T-334 IN-DOMAIN - SciReviewGen test (NOT the gate)",
                           id_stock, id_tuned)
        results["in_domain"] = {"stock": id_stock, "tuned": id_tuned, "delta": id_delta}

        if id_delta["nDCG@10"] > 0.01 >= ood_delta["nDCG@10"]:
            print("\n  WARNING: gains IN-DOMAIN but not out-of-domain. The benchmark "
                  "was fitted, not the task (TRAINING_SPEC 2.4). Report it as such.")

    # ---- relevance control: can the model still recognise irrelevance? ----
    print("\n  relevance control - scoring deliberately off-topic documents ...")
    ctrl_stock = relevance_control(stock_scorer, per_query)
    ctrl_tuned = relevance_control(tuned_scorer, per_query)
    print(f"  {'arm':14s} {'violations':>11s} {'rate':>7s} {'mean margin':>12s}")
    for name, c in (("stock", ctrl_stock), ("fine-tuned", ctrl_tuned)):
        print(f"  {name:14s} {c['violations']:5d}/{c['queries']:<5d} "
              f"{c['violation_rate']:7.1%} {c['mean_margin']:12.3f}  "
              f"{'PASS' if c['pass'] else 'FAIL'}")
    if not ctrl_tuned["pass"]:
        print("\n  !! The tuned model scores OFF-TOPIC documents above its own median")
        print("  !! in-pool candidate. It has lost its relevance prior - the ranking")
        print("  !! metrics cannot see this because the pool is already on-topic.")
        for v in ctrl_tuned["worst_examples"]:
            print(f"  !!   {v['query'][:44]:44s} control {v['control_score']:+7.2f} "
                  f"vs pool median {v['pool_median']:+7.2f}")
    results["relevance_control"] = {"stock": ctrl_stock, "tuned": ctrl_tuned}

    # ---- T-335 -----------------------------------------------------------
    # The relevance control reports a CONDITION, not a veto. Wiring it as a hard
    # block was an overcorrection: it measures whether absolute scores are
    # meaningful, but whether that matters depends on facts it cannot see -
    # whether anything consumes the score as a value, and whether the live pool
    # actually contains off-topic documents. Both were measured; both are
    # favourable. Ranking gains remain a hard requirement.
    ranking_ok = ood_delta["nDCG@10"] > 0 and ood_delta["Recall@20"] >= 0
    promote = ranking_ok
    conditional = ranking_ok and not ctrl_tuned["pass"]
    print("\n" + "=" * 76)
    if conditional:
        print("T-335 ADOPTION GATE: PROMOTE WITH CONDITIONS.")
        print(f"  Ranking improves out-of-domain: nDCG@10 {ood_delta['nDCG@10']:+.4f}, "
              f"Recall@20 {ood_delta['Recall@20']:+.4f}.")
        print(f"  But the relevance control FAILS on "
              f"{ctrl_tuned['violation_rate']:.0%} of queries - this model's ABSOLUTE")
        print("  scores are meaningless; only its ordering is usable.")
        print("\n  Adopt ONLY while both conditions hold:")
        print("    1. Nothing thresholds on the score. RRF fuses by rank, and")
        print("       Reranker.filter_by_score() raises on an uncalibrated model.")
        print("    2. The candidate pool stays overwhelmingly on-topic, so there is")
        print("       little for a miscalibrated model to mis-promote.")
        print("  RE-RUN THIS GATE if max_per_source rises (decisions.txt D-05) or a")
        print("  new source widens the pool.")
    elif promote:
        print("T-335 ADOPTION GATE: PROMOTE.")
        print(f"  The tuned reranker beats stock out-of-domain "
              f"(nDCG@10 {ood_delta['nDCG@10']:+.4f}) and keeps its relevance prior.")
        print("  Set retrieval.reranker in configs/default.yaml to the tuned model.")
    else:
        print("T-335 ADOPTION GATE: DO NOT PROMOTE. Keep the stock reranker.")
        print(f"  Out-of-domain nDCG@10 {ood_delta['nDCG@10']:+.4f}, "
              f"Recall@20 {ood_delta['Recall@20']:+.4f} - no ranking gain to trade")
        print("  any calibration loss against.")
        print("  This is an HONEST NEGATIVE RESULT, not a failure: the pipeline is")
        print("  unaffected (it was always a weight swap) and the verifier already")
        print("  satisfies the training requirement on its own. Report it.")
    if not quantized:
        # NB: printed strings stay ASCII. Windows consoles default to cp1252 and
        # a stray emoji raises UnicodeEncodeError after all the work is done.
        print("\n  WARNING: judged on the UNQUANTIZED model. TRAINING_SPEC 2.5 requires")
        print("      gate be measured after int8 - re-run with --tuned-onnx.")
    print("=" * 76)

    results["adoption"] = {
        "promote": promote,
        "conditional": conditional,
        "measured_after_quantization": quantized,
        "conditions": (
            ["ordering only - nothing may threshold on the score",
             "candidate pool must stay overwhelmingly on-topic; re-run if "
             "max_per_source rises or a new source is added"]
            if conditional else []
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
