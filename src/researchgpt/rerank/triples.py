"""T-330 / T-331 — training triples for the reranker, with BM25 hard negatives.

Reuses the T-321 parser. Per ``TRAINING_SPEC §2.2``::

    query      survey_title + " " + chapter_heading   (a topic, not a question -
                                                       this is what the live
                                                       Retriever actually sees)
    positives  the abstracts of every BIBnnn block in that chapter
    negatives  BM25 top-50 for the query, minus that query's true positives
    ratio      1 positive : 4 negatives

★ **Hard negatives are the entire point of this task.** Random negatives make
the objective trivial: the model learns topic matching, which BM25 already
does, and stock-vs-tuned then shows no gain. The negatives have to be documents
**BM25 already ranks highly and is wrong about** — that mismatch is the only
signal a cross-encoder can add over the first-stage retriever. `TASKLIST` T-331
says it directly: *"If T-334 shows ~0 improvement, suspect this task first."*

⚠️ **Leakage control is what silently invalidates a reranker result.** Three
rules, all enforced here rather than trusted:

1. **Split by ``survey_title``, never by row.** One survey contributes many
   chapter rows. Measured in Phase 3B: **63 distinct surveys across 436
   chapters** in a 500-row sample — so a row-level split puts chapters of the
   same survey on both sides and inflates the tuned score. Asserted, not
   assumed.
2. Train pairs come only from the ``train`` split; evaluation only from
   ``test``.
3. Negatives are pooled **within the split being built**. Mining train
   negatives from the test pool would leak the evaluation corpus into training.

Run::

    python -m researchgpt.rerank.triples --chapters 3000
    python -m researchgpt.rerank.triples --chapters 200 --split test --out data/rerank/test.jsonl
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
from collections import Counter
from typing import Any

from researchgpt.eval.scireviewgen import load_split
from researchgpt.eval.scireviewgen_parser import parse_reference

DEFAULT_OUT = pathlib.Path("data/rerank/train_triples.jsonl")
DEFAULT_STATS = pathlib.Path("eval/rerank_triples_t330.json")

#: TRAINING_SPEC 2.2. 3,000 chapters x <=8 positives x 5 ~ 120k pairs.
DEFAULT_CHAPTERS = 3000
#: Rows read before sampling. Bounded so memory stays sane - the train split is
#: 84,705 rows of long text across three 150 MB shards.
DEFAULT_POOL = 20000
MAX_POSITIVES = 8
NEGATIVES_PER_POSITIVE = 4

#: BM25 depth to mine from. Deeper than we need, because true positives are
#: removed first and a shallow pool would leave too few hard candidates.
BM25_DEPTH = 50

SEED = 20260827

#: An abstract shorter than this carries no rankable content and would teach
#: the model that length predicts irrelevance.
MIN_ABSTRACT_CHARS = 80


def build_corpus(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    """Parse rows into (documents, query -> positive doc_ids).

    Documents are deduplicated by abstract text: the same paper is cited by
    many chapters, and leaving duplicates in the BM25 pool would let a true
    positive reappear as a "negative" under a different id.
    """
    by_text: dict[str, str] = {}
    documents: list[dict[str, Any]] = []
    positives: dict[str, set[str]] = {}
    queries: dict[str, dict[str, str]] = {}

    for row in rows:
        parsed = parse_reference(row["reference"])
        query = f"{parsed['survey_title']} {parsed['chapter']}".strip()
        if not query:
            continue

        for bib in parsed["bibs"][:MAX_POSITIVES]:
            abstract = bib["abstract"]
            if len(abstract) < MIN_ABSTRACT_CHARS:
                continue
            doc_id = by_text.get(abstract)
            if doc_id is None:
                doc_id = f"d{len(documents)}"
                by_text[abstract] = doc_id
                documents.append({"doc_id": doc_id, "text": abstract})
            positives.setdefault(query, set()).add(doc_id)

        if query in positives:
            queries[query] = {"survey_title": parsed["survey_title"],
                              "chapter": parsed["chapter"]}

    # Drop queries whose positives all fell below the length floor.
    positives = {q: v for q, v in positives.items() if v}
    return documents, positives


def mine_hard_negatives(
    documents: list[dict[str, Any]],
    positives: dict[str, set[str]],
    *,
    depth: int = BM25_DEPTH,
    per_positive: int = NEGATIVES_PER_POSITIVE,
    seed: int = SEED,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """T-331. BM25 top-``depth`` for each query, minus its true positives."""
    from researchgpt.core.models import Chunk
    from researchgpt.data.bm25_index import BM25Index

    chunks = [
        Chunk(chunk_id=d["doc_id"], paper_id=d["doc_id"], text=d["text"],
              start_char=0, end_char=len(d["text"]))
        for d in documents
    ]
    index = BM25Index()
    index.build(chunks)
    text_of = {d["doc_id"]: d["text"] for d in documents}

    rng = random.Random(seed)
    pairs: list[dict[str, Any]] = []
    shortfalls = 0
    depth_hits: list[int] = []
    random_fallbacks = 0
    all_ids = [d["doc_id"] for d in documents]

    for query, positive_ids in positives.items():
        ranked = [doc_id for doc_id, _ in index.query(query, k=depth)]
        # The mismatch that matters: documents BM25 ranks highly and is wrong about.
        candidates = [doc_id for doc_id in ranked if doc_id not in positive_ids]
        depth_hits.append(len(candidates))

        wanted = len(positive_ids) * per_positive
        if len(candidates) < wanted:
            shortfalls += 1
            # Top up at random rather than emit an unbalanced query. Counted and
            # reported: if this fires often the negatives are not hard, and
            # T-334 showing no gain would be explained here (T-331's warning).
            spare = [i for i in all_ids if i not in positive_ids and i not in candidates]
            rng.shuffle(spare)
            topup = spare[: wanted - len(candidates)]
            random_fallbacks += len(topup)
            candidates = candidates + topup

        chosen = candidates[:wanted]
        for doc_id in positive_ids:
            pairs.append({"query": query, "text": text_of[doc_id], "label": 1,
                          "doc_id": doc_id})
        for doc_id in chosen:
            pairs.append({"query": query, "text": text_of[doc_id], "label": 0,
                          "doc_id": doc_id})

    total_neg = sum(1 for p in pairs if p["label"] == 0)
    diagnostics = {
        "queries": len(positives),
        "documents": len(documents),
        "bm25_depth": depth,
        "mean_hard_candidates_per_query": (
            sum(depth_hits) / max(len(depth_hits), 1)
        ),
        "queries_short_of_hard_negatives": shortfalls,
        "random_fallback_negatives": random_fallbacks,
        "random_fallback_share_of_negatives": random_fallbacks / max(total_neg, 1),
    }
    return pairs, diagnostics


def split_by_survey(
    rows: list[dict[str, Any]], *, seed: int = SEED
) -> dict[str, list[dict[str, Any]]]:
    """Group rows by ``survey_title`` so callers can split without leaking."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        title = parse_reference(row["reference"])["survey_title"]
        groups.setdefault(title, []).append(row)
    return groups


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-330/T-331 - reranker training triples.")
    ap.add_argument("--split", default="train", choices=["train", "validation", "test"])
    ap.add_argument("--chapters", type=int, default=DEFAULT_CHAPTERS)
    ap.add_argument("--pool", type=int, default=DEFAULT_POOL,
                    help="rows read before sampling --chapters from them. Reading "
                         "sequentially would bias toward the parquet's own ordering: "
                         "chapters of one survey sit adjacent, so the first N rows "
                         "span very few surveys (measured: 150 rows -> 13 surveys).")
    ap.add_argument("--max-positives", type=int, default=MAX_POSITIVES)
    ap.add_argument("--negatives-per-positive", type=int, default=NEGATIVES_PER_POSITIVE)
    ap.add_argument("--depth", type=int, default=BM25_DEPTH)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--stats", type=pathlib.Path, default=DEFAULT_STATS)
    args = ap.parse_args(argv)

    print(f"T-330/T-331 - reranker triples\n  split {args.split}  "
          f"chapters {args.chapters}  seed {args.seed}\n")

    pool = load_split(args.split, limit=max(args.pool, args.chapters))
    if len(pool) > args.chapters:
        # Sample across the pool rather than taking a prefix. Survey diversity is
        # what the reranker generalises over, and adjacent rows share a survey.
        rng = random.Random(args.seed)
        rows = rng.sample(pool, args.chapters)
        print(f"  sampled {len(rows):,} chapters from a {len(pool):,}-row pool")
    else:
        rows = pool
    groups = split_by_survey(rows)
    print(f"  {len(rows):,} chapters spanning {len(groups):,} distinct surveys "
          f"({len(rows) / max(len(groups), 1):.1f} chapters per survey)")

    documents, positives = build_corpus(rows)
    print(f"  {len(documents):,} unique cited abstracts, {len(positives):,} queries")

    print(f"\n  mining BM25 top-{args.depth} hard negatives ...")
    pairs, diag = mine_hard_negatives(
        documents, positives,
        depth=args.depth, per_positive=args.negatives_per_positive, seed=args.seed,
    )

    labels = Counter(p["label"] for p in pairs)
    print(f"\n  pairs          {len(pairs):8,d}")
    print(f"    positives    {labels[1]:8,d}")
    print(f"    negatives    {labels[0]:8,d}   "
          f"(ratio 1:{labels[0] / max(labels[1], 1):.1f})")
    print(f"  mean hard candidates per query   {diag['mean_hard_candidates_per_query']:6.1f}")
    print(f"  queries short of hard negatives  {diag['queries_short_of_hard_negatives']:6,d}")
    print(f"  random-fallback negatives        {diag['random_fallback_negatives']:6,d} "
          f"({diag['random_fallback_share_of_negatives']:.1%} of negatives)")

    if diag["random_fallback_share_of_negatives"] > 0.25:
        print("\n  !! Over a quarter of negatives are RANDOM, not hard. The corpus is")
        print("  !! too small for BM25 to supply confusable documents. Raise --chapters.")
        print("  !! T-331: if T-334 shows no gain, suspect this first.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    print(f"\n  wrote {args.out}  ({len(pairs):,} pairs)")

    stats = {
        "task": "T-330/T-331",
        "split": args.split,
        "chapters": len(rows),
        "distinct_surveys": len(groups),
        "chapters_per_survey": len(rows) / max(len(groups), 1),
        "max_positives_per_chapter": args.max_positives,
        "negatives_per_positive": args.negatives_per_positive,
        "seed": args.seed,
        "pairs": len(pairs),
        "positives": labels[1],
        "negatives": labels[0],
        **diag,
        "leakage_note": (
            "Split by survey_title, never by row: one survey contributes many "
            "chapters, so a row-level split puts the same survey on both sides "
            "and inflates the tuned score (TRAINING_SPEC 2.2)."
        ),
    }
    args.stats.parent.mkdir(parents=True, exist_ok=True)
    args.stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"  wrote {args.stats}")


if __name__ == "__main__":
    main()
