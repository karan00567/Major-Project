"""T-409 / T-213(1) — score a real pipeline run against the answer key.

TASKLIST T-409 runs the system on **its own topic**, where the project's
hand-curated 35-paper bibliography is the answer key. That makes the flagship
run do double duty, and the second job has been blocked since Phase 2:

> **T-212**: *"Re-run this gate right after T-402 and treat that as the real
> Phase 2 gate."*

The original gate read **union recall 0.371 / Recall@60 0.057** using 15
hand-written stand-in queries, and T-213's diagnosis was that the misses were
*never asked for* rather than unreachable. The Planner (T-402) is the fix. This
module measures whether it worked, on the queries the Planner actually emitted
rather than on a stand-in.

**Two numbers, and they answer different questions** (`decisions.txt` D-04):

* **union recall** — of the 35 gold papers, how many did retrieval find *at
  all*? This is a hard ceiling: no reranker can promote a paper that was never
  fetched. **This is the primary gate.**
* **Recall@N** — how many survived into the ``max_papers`` corpus the Extractor
  actually read? Bounded by ``max_papers / 35`` and by how the round-robin
  splits slots across sub-questions, so it is reported, not gated.

Matching is DOI-first with a title fallback, the same rule the T-212 harness
uses, so the numbers are comparable to the 2026-08-26 baseline.

Run::

    python -m researchgpt.eval.flagship_recall --run flagship
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any

GOLD = pathlib.Path("eval/gold_sets/own_bibliography.json")
DEFAULT_OUT = pathlib.Path("eval/flagship_recall_t409.json")

#: Same floor as the retriever's dedup key: shorter titles are not distinctive.
MIN_TITLE_KEY = 25


def norm_doi(doi: str | None) -> str:
    if not doi:
        return ""
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", str(doi).strip().lower())


def norm_title(title: str | None) -> str:
    key = re.sub(r"[^a-z0-9]+", "", (title or "").lower())
    return key if len(key) >= MIN_TITLE_KEY else ""


def load_gold() -> tuple[dict[str, dict], dict[str, str]]:
    """Returns (doi -> paper, title_key -> doi)."""
    doc = json.loads(GOLD.read_text(encoding="utf-8"))
    by_doi, by_title = {}, {}
    for paper in doc["papers"]:
        doi = norm_doi(paper.get("doi"))
        if doi:
            by_doi[doi] = paper
        title = norm_title(paper.get("title"))
        if title and doi:
            by_title[title] = doi
    return by_doi, by_title


def match(record: dict[str, Any], by_doi: dict, by_title: dict) -> str | None:
    """The gold DOI this record corresponds to, or None."""
    doi = norm_doi(record.get("doi"))
    if doi and doi in by_doi:
        return doi
    title = norm_title(record.get("title"))
    if title and title in by_title:
        return by_title[title]
    return None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-409 - score a run against the answer key.")
    ap.add_argument("--run", default="flagship")
    ap.add_argument("--runs-dir", type=pathlib.Path, default=pathlib.Path("outputs/runs"))
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    run_dir = args.runs_dir / args.run
    corpus_path = run_dir / "corpus.json"
    if not corpus_path.exists():
        raise SystemExit(
            f"{corpus_path} missing. The run must persist its corpus - see "
            f"write_corpus() in output/writers.py."
        )
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    retrieved = corpus["papers"]
    extracted_ids = set(corpus.get("extracted_paper_ids") or [])

    by_doi, by_title = load_gold()
    n_gold = len(by_doi)

    found_union: dict[str, dict] = {}
    found_corpus: dict[str, dict] = {}
    for record in retrieved:
        gold_doi = match(record, by_doi, by_title)
        if not gold_doi:
            continue
        found_union.setdefault(gold_doi, record)
        if record.get("paper_id") in extracted_ids:
            found_corpus.setdefault(gold_doi, record)

    union_recall = len(found_union) / n_gold
    corpus_recall = len(found_corpus) / n_gold
    missed = sorted(set(by_doi) - set(found_union))

    print("T-409 / T-213(1) - recall against the answer key\n")
    print(f"  run                  {args.run}")
    print(f"  gold papers          {n_gold}")
    print(f"  papers retrieved     {len(retrieved)}")
    print(f"  corpus extracted     {len(extracted_ids)}")
    print()
    print(f"  UNION RECALL         {len(found_union):3d}/{n_gold}   {union_recall:.3f}"
          f"   <- the primary gate (D-04)")
    print(f"  corpus recall        {len(found_corpus):3d}/{n_gold}   {corpus_recall:.3f}"
          f"   <- bounded by max_papers/{n_gold}")
    print()
    print("  2026-08-26 baseline, 15 stand-in queries:  union 0.371")
    delta = union_recall - 0.371
    print(f"  DELTA from the Planner (T-402):            {delta:+.3f}")
    print()
    if missed:
        print(f"  still missed ({len(missed)}):")
        for doi in missed[:10]:
            print(f"    {by_doi[doi]['title'][:66]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "task": "T-409 / T-213(1)",
        "run": args.run,
        "gold_papers": n_gold,
        "papers_retrieved": len(retrieved),
        "corpus_size": len(extracted_ids),
        "union_recall": union_recall,
        "corpus_recall": corpus_recall,
        "baseline_union_recall_2026_08_26": 0.371,
        "delta": delta,
        "found": sorted(found_union),
        "missed": missed,
        "note": (
            "union recall is the primary gate (decisions.txt D-04): it is a hard "
            "ceiling, since no reranker can promote a paper that was never "
            "fetched. corpus recall is bounded by max_papers/gold and by the "
            "round-robin split across sub-questions, so it is reported not gated."
        ),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
