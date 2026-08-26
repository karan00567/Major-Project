"""T-212 — retrieval recall against the project's own bibliography.

Measures whether the corpus builder finds the papers a human curator found.

**Gate note.** `PROJECT_PLAN.md §9.2` specifies "Recall@20 >= 0.80". With a
35-paper gold set that is unachievable: retrieving 20 papers caps recall at
20/35 = 0.57. The corrected gate (TASKLIST T-212) is **Recall@60 >= 0.80**,
where 60 is ``review.max_papers`` - the corpus the Extractor actually sees and
therefore the thing downstream quality depends on. Recall@20 is still reported
as a secondary diagnostic, labelled with its ceiling.

Run:  python -m researchgpt.eval.retrieval_eval
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from researchgpt.core.config import load_config
from researchgpt.tools.search_sources import search_arxiv, search_openalex

GOLD = pathlib.Path("eval/gold_sets/own_bibliography.json")
OUT = pathlib.Path("eval/retrieval_eval_t212.json")

#: Stands in for the Planner (T-402), which does not exist yet. These mirror
#: the six thematic clusters of the literature review (SPEC §1.6) so the
#: evaluation reflects the real multi-sub-question retrieval pattern rather
#: than a single lucky query.
QUERIES = [
    # SHORT queries — 2-4 terms. OpenAlex ANDs every term in
    # title_and_abstract.search, so a 6-term query matches almost nothing
    # (measured 2026-08-25: "scientific claim verification evidence entailment
    # SciFact" -> 0 results; "scientific claim verification" -> 4,174).
    # This constraint must be reflected in the Planner prompt (T-402).
    "agentic retrieval augmented generation",
    "automated literature review generation",
    "scientific survey generation",
    "scientific claim verification",
    "citation accuracy language models",
    "hallucination large language models",
    "retrieval augmented generation evaluation",
    "multi-agent large language model",
    "systematic review automation",
    "cross-encoder reranking retrieval",
    "attributed question answering citations",
    "scientific information extraction",
    "citation text generation",
    "evidence retrieval fact checking",
    "RAG survey",
]


def norm(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.strip().lower().replace("https://doi.org/", "")


def main() -> None:
    cfg = load_config("configs/default.yaml")
    gold_doc = json.loads(GOLD.read_text(encoding="utf-8"))
    gold = {norm(p["doi"]) for p in gold_doc["papers"] if p.get("doi")}
    print(f"gold set: {len(gold)} DOIs\n", flush=True)

    per_query: list[dict[str, Any]] = []
    union: dict[str, Any] = {}          # doi -> first rank seen
    ordered: list[str] = []             # dedup order across queries

    for q in QUERIES:
        found: list[str] = []
        try:
            papers = search_openalex(q, year_min=cfg.review.year_min, max_results=25)
        except Exception as exc:
            print(f"  openalex failed on {q[:40]!r}: {type(exc).__name__}", flush=True)
            papers = []
        try:
            papers += search_arxiv(q, max_results=15)
        except Exception as exc:
            print(f"  arxiv failed on {q[:40]!r}: {type(exc).__name__}", flush=True)

        for p in papers:
            d = norm(p.doi)
            if not d:
                continue
            if d not in union:
                union[d] = len(ordered)
                ordered.append(d)
            if d in gold:
                found.append(d)

        hit = len(set(found))
        per_query.append({"query": q, "retrieved": len(papers), "gold_hits": hit})
        print(f"  {hit:2d} gold hits / {len(papers):3d} retrieved  |  {q[:52]}", flush=True)

    # Recall at increasing corpus cut-offs.
    recalls = {}
    for k in (20, 40, 60, 100, len(ordered)):
        if k <= 0:
            continue
        top = set(ordered[:k])
        recalls[k] = len(top & gold) / len(gold)

    found_all = set(ordered) & gold
    missed = sorted(gold - found_all)

    print(f"\nunion corpus: {len(ordered)} unique DOIs across {len(QUERIES)} queries", flush=True)
    print("\nRECALL")
    for k, v in recalls.items():
        ceiling = min(k, len(gold)) / len(gold)
        label = "  <- GATE (max_papers)" if k == 60 else ""
        note = f"  [ceiling {ceiling:.2f}]" if ceiling < 1.0 else ""
        print(f"  Recall@{k:<5d} = {v:.3f}{note}{label}", flush=True)

    gate = recalls.get(60, 0.0)
    print(f"\nGATE  Recall@60 >= 0.80  ->  {gate:.3f}  {'PASS' if gate >= 0.80 else 'FAIL'}")
    print(f"found {len(found_all)}/{len(gold)} gold papers; missed {len(missed)}")
    if missed:
        by_doi = {norm(p["doi"]): p for p in gold_doc["papers"]}
        print("\nMISSED (these bound every downstream metric):")
        for d in missed[:15]:
            p = by_doi.get(d, {})
            print(f"  {p.get('year','????')} {str(p.get('title'))[:66]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "gold_size": len(gold),
        "union_size": len(ordered),
        "recalls": {str(k): v for k, v in recalls.items()},
        "gate_recall_at_60": gate,
        "gate_pass": gate >= 0.80,
        "per_query": per_query,
        "missed": missed,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
