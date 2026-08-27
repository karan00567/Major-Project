"""T-212 — retrieval recall against the project's own bibliography.

Measures whether the corpus builder finds the papers a human curator found.

**Gate.** `PROJECT_PLAN.md §9.2` specifies "Recall@20 >= 0.80". With a 35-paper
gold set that is unachievable: retrieving 20 papers caps recall at 20/35 = 0.57.
The corrected gate (TASKLIST T-212) is **Recall@60 >= 0.80**, where 60 is
``review.max_papers`` — the corpus the Extractor actually sees and therefore the
thing downstream quality depends on. Recall@20 is still reported as a secondary
diagnostic, labelled with its ceiling.

**Two corrections applied 2026-08-26 (T-213 items 2 and 3).** The first run of
this harness reported ``Recall@60 = 0.029`` and that number was mostly an
artefact of the harness, not of retrieval:

1. *The cut-off ranked nothing.* The union was ordered by the sequence in which
   queries happened to run, so ``union[:60]`` meant "everything the first two
   queries returned" rather than "the best 60 papers". Recall over the whole
   447-paper union was 0.371 — 13x the reported gate number. The corpus is now
   **ranked through the real T-209 hybrid retriever and T-210 cross-encoder
   reranker**, then merged across sub-questions round-robin by rank, which is
   how the Retriever agent (T-403) will build it.
2. *DOI-only matching undercounts by construction.* arXiv records carry the
   synthetic ``10.48550/arxiv.*`` join key, so retrieving the preprint of a
   published paper scored as a miss. Of the original 22 misses, most were ACL
   Anthology papers — exactly the population most likely to be found as
   preprints. Recall is now reported **both ways**: DOI-only (conservative) and
   DOI-or-normalised-title (the honest "did we find this paper" number). Both
   are printed; neither is hidden.

Semantic Scholar (T-214) joins OpenAlex and arXiv here as a best-effort third
source. It is throttled without a key (T-215), and when it is, it contributes
nothing and the eval continues — that is the designed behaviour, not a failure.

⚠️ **Sequencing.** TASKLIST T-212 notes this gate is not final until the Planner
(T-402) exists, because recall is dominated by query generation. The queries
below are a hand-written stand-in for it. Re-run after T-402 and treat *that* as
the real Phase 2 gate.

Run:  python -m researchgpt.eval.retrieval_eval [--max-per-source N] [--no-rank]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import tempfile
from typing import Any

from researchgpt.core.config import load_config
from researchgpt.core.models import Chunk, Paper
from researchgpt.tools.search_sources import (
    search_arxiv,
    search_openalex,
    search_semantic_scholar,
)

GOLD = pathlib.Path("eval/gold_sets/own_bibliography.json")
OUT = pathlib.Path("eval/retrieval_eval_t212.json")

_TITLE_NOISE_RE = re.compile(r"[^a-z0-9]+")

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


def norm_title(title: str | None) -> str | None:
    """Aggressive title key so an arXiv preprint matches its published version.

    Collapses to lowercase alphanumerics. Short titles are dropped — a 3-word
    key collides too easily, and a false *hit* flatters the gate in the one
    direction that matters.
    """
    if not title:
        return None
    key = _TITLE_NOISE_RE.sub("", title.lower())
    return key if len(key) >= 25 else None


# ---------------------------------------------------------------------------
# Corpus construction
# ---------------------------------------------------------------------------


def gather(query: str, *, year_min: int, max_per_source: int) -> list[Paper]:
    """All three connectors for one sub-question. Never raises."""
    papers: list[Paper] = []
    for name, fn in (
        ("openalex", lambda: search_openalex(query, year_min=year_min, max_results=max_per_source)),
        ("arxiv", lambda: search_arxiv(query, max_results=max(10, max_per_source // 2))),
        (
            "semantic_scholar",
            lambda: search_semantic_scholar(
                query, year_min=year_min, max_results=max_per_source
            ),
        ),
    ):
        try:
            papers += fn()
        except Exception as exc:  # a source outage must not end the eval
            print(f"    {name} failed on {query[:36]!r}: {type(exc).__name__}", flush=True)
    return papers


def paper_key(p: Paper) -> str:
    """Stable identity for a retrieved record: DOI when present, else title."""
    return norm(p.doi) or norm_title(p.title) or f"{p.source}:{p.paper_id}"


def as_chunk(key: str, p: Paper) -> Chunk:
    """One pseudo-chunk per paper: title + abstract is what a corpus-selection
    decision is actually made on, so that is what gets ranked."""
    text = p.title if not p.abstract else f"{p.title}\n\n{p.abstract}"
    return Chunk(
        chunk_id=key,
        paper_id=key,
        text=text,
        section="abstract",
        start_char=0,
        end_char=len(text),
    )


def rank_corpus(
    per_query: dict[str, list[str]],
    pool: dict[str, Paper],
    cfg: Any,
) -> list[str]:
    """T-213(2) — rank the pool through the real T-209 + T-210 stack.

    Each sub-question is ranked independently, then merged round-robin by rank
    so every sub-question contributes to the head of the corpus. That is the
    policy the Retriever agent needs anyway: a corpus that answers one
    sub-question perfectly and five not at all fails coverage downstream.
    """
    # Imported here: these pull torch, and --no-rank must stay usable without it.
    from researchgpt.data.bm25_index import BM25Index
    from researchgpt.data.embeddings import Embedder
    from researchgpt.data.vectorstore import VectorStore
    from researchgpt.tools.hybrid_retriever import HybridRetriever
    from researchgpt.tools.reranker import Reranker

    chunks = [as_chunk(k, p) for k, p in pool.items()]
    print(f"\nranking {len(chunks)} pooled papers through T-209 + T-210 ...", flush=True)

    # ⚠️ The first stage must not be narrower than what one sub-question
    # retrieved live. With the production dense_k/sparse_k of 30, ``retrieve()``
    # returns a *global* top-60 over the whole pool; intersecting that with one
    # sub-question's own candidates then throws most of them away, and throws
    # away more of them the larger the pool gets. That makes pool size itself
    # change the score — measured 2026-08-26: raising max_per_source 25 -> 100
    # nearly doubled union recall (0.371 -> 0.714) while the Recall@60 gate
    # *fell* (0.057 -> 0.029), which is an artefact of this narrowing, not a
    # property of retrieval. Widening the first stage to the whole pool removes
    # the confound: RRF still fuses dense + sparse exactly as T-209 specifies,
    # it just no longer truncates before the reranker sees the candidates.
    rank_cfg = cfg.retrieval.model_copy(
        update={"dense_k": len(chunks), "sparse_k": len(chunks)}
    )

    embedder = Embedder(
        model_name=cfg.embeddings.model,
        device=cfg.embeddings.device,
        batch_size=cfg.embeddings.batch_size,
    )
    embeddings = embedder.encode([c.text for c in chunks])

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = VectorStore(path=tmp, collection="t212")
        store.add(chunks, embeddings)
        bm25 = BM25Index()
        bm25.build(chunks)
        retriever = HybridRetriever(store, bm25, embedder, rank_cfg)
        reranker = Reranker(model_name=cfg.retrieval.reranker, device=cfg.embeddings.device)

        ranked_per_query: list[list[str]] = []
        kept: list[int] = []
        for query in QUERIES:
            fused = retriever.retrieve(query)
            # Restrict to what this sub-question actually retrieved from the
            # live sources; the pool is shared, the attribution is not.
            allowed = set(per_query.get(query, ()))
            candidates = [c for c, _ in fused if c.chunk_id in allowed]
            kept.append(len(candidates))
            if not candidates:
                ranked_per_query.append([])
                continue
            top = reranker.rerank(query, candidates, top_k=len(candidates))
            ranked_per_query.append([c.chunk_id for c, _ in top])
        # Coverage of the first stage. If min() here is far below the mean
        # number of live candidates per sub-question, the confound above has
        # come back and the gate number is not trustworthy.
        print(
            f"  first-stage kept per sub-question: min={min(kept)} "
            f"max={max(kept)} (of {len(chunks)} pooled)",
            flush=True,
        )
        print(f"  reranker last batch: {reranker.last_latency_ms} ms", flush=True)

        store.reset()

    # Round-robin merge by rank.
    ordered: list[str] = []
    seen: set[str] = set()
    depth = max((len(r) for r in ranked_per_query), default=0)
    for i in range(depth):
        for ranking in ranked_per_query:
            if i < len(ranking) and ranking[i] not in seen:
                seen.add(ranking[i])
                ordered.append(ranking[i])
    # Anything no sub-question ranked still belongs in the union tail.
    for key in pool:
        if key not in seen:
            ordered.append(key)
    return ordered


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def recall_at(
    ordered: list[str],
    pool: dict[str, Paper],
    gold_dois: set[str],
    gold_title_to_doi: dict[str, str],
    k: int,
) -> tuple[float, float]:
    """(doi_only, doi_or_title) recall over the first ``k`` ranked papers.

    Both are keyed on the gold DOI, so an arXiv preprint matched by title and
    its published version matched by DOI count once, not twice.
    """
    hit_doi: set[str] = set()
    hit_any: set[str] = set()
    for key in ordered[:k]:
        p = pool[key]
        doi, title = norm(p.doi), norm_title(p.title)
        if doi and doi in gold_dois:
            hit_doi.add(doi)
            hit_any.add(doi)
        elif title and title in gold_title_to_doi:
            hit_any.add(gold_title_to_doi[title])
    denom = len(gold_dois) or 1
    return len(hit_doi) / denom, len(hit_any) / denom


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--max-per-source",
        type=int,
        default=None,
        help="T-213(3): override sources.max_per_source and re-measure.",
    )
    ap.add_argument(
        "--no-rank",
        action="store_true",
        help="Skip T-209/T-210 ranking and use raw insertion order (the old, "
             "broken behaviour — kept only to reproduce the 2026-08-25 number).",
    )
    ap.add_argument(
        "--cache",
        action="store_true",
        help="Reuse the gathered pool from eval/cache/ when present, and write "
             "it when absent. A live gather costs ~18 min, most of it Semantic "
             "Scholar backoff; re-ranking the same pool under different "
             "settings should not re-pay that. Also makes the sweep "
             "reproducible for T-810.",
    )
    args = ap.parse_args()

    cfg = load_config("configs/default.yaml")
    max_per_source = args.max_per_source or cfg.sources.max_per_source
    cache_path = pathlib.Path(f"eval/cache/pool_mps{max_per_source}.json")

    gold_doc = json.loads(GOLD.read_text(encoding="utf-8"))
    gold_dois = {norm(p["doi"]) for p in gold_doc["papers"] if p.get("doi")}
    gold_dois.discard(None)
    # normalised title -> gold DOI, so a title hit resolves to the same identity
    gold_title_to_doi: dict[str, str] = {}
    for p in gold_doc["papers"]:
        t, d = norm_title(p.get("title")), norm(p.get("doi"))
        if t and d:
            gold_title_to_doi[t] = d

    print(f"gold set: {len(gold_dois)} DOIs ({len(gold_title_to_doi)} with usable titles)")
    print(f"max_per_source: {max_per_source}   ranking: {'off' if args.no_rank else 'on'}\n")

    pool: dict[str, Paper] = {}
    per_query: dict[str, list[str]] = {}
    insertion_order: list[str] = []
    rows: list[dict[str, Any]] = []

    if args.cache and cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        pool = {k: Paper(**v) for k, v in cached["pool"].items()}
        per_query = cached["per_query"]
        insertion_order = cached["insertion_order"]
        rows = cached["rows"]
        print(f"reusing cached pool: {cache_path} ({len(pool)} papers)\n")
        for row in rows:
            print(
                f"  {row['gold_hits']:2d} gold hits / {row['retrieved']:3d} unique  "
                f"|  {row['query'][:46]}"
            )
    else:
        for query in QUERIES:
            papers = gather(
                query, year_min=cfg.review.year_min, max_per_source=max_per_source
            )
            keys: list[str] = []
            sources_seen: set[str] = set()
            for p in papers:
                key = paper_key(p)
                sources_seen.add(p.source)
                if key not in pool:
                    pool[key] = p
                    insertion_order.append(key)
                elif not pool[key].abstract and p.abstract:
                    pool[key] = p  # prefer the record that carries an abstract
                if key not in keys:
                    keys.append(key)
            per_query[query] = keys
            hits = sum(
                1
                for k in keys
                if (norm(pool[k].doi) in gold_dois)
                or (norm_title(pool[k].title) in gold_title_to_doi)
            )
            rows.append(
                {
                    "query": query,
                    "retrieved": len(keys),
                    "gold_hits": hits,
                    "sources": sorted(sources_seen),
                }
            )
            print(f"  {hits:2d} gold hits / {len(keys):3d} unique  |  {query[:46]}", flush=True)

        if args.cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "max_per_source": max_per_source,
                        "year_min": cfg.review.year_min,
                        "pool": {k: v.model_dump() for k, v in pool.items()},
                        "per_query": per_query,
                        "insertion_order": insertion_order,
                        "rows": rows,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"\ncached pool -> {cache_path}")

    ordered = insertion_order if args.no_rank else rank_corpus(per_query, pool, cfg)

    cutoffs = [20, 40, 60, 100, len(ordered)]
    recalls: dict[str, dict[str, float]] = {}
    for k in cutoffs:
        if k <= 0:
            continue
        doi_only, any_match = recall_at(ordered, pool, gold_dois, gold_title_to_doi, k)
        recalls[str(k)] = {"doi_only": doi_only, "doi_or_title": any_match}

    print(f"\nunion corpus: {len(ordered)} unique papers across {len(QUERIES)} queries")
    print("\nRECALL                doi-only   doi-or-title")
    for k_str, vals in recalls.items():
        k = int(k_str)
        ceiling = min(k, len(gold_dois)) / len(gold_dois)
        note = f"  [ceiling {ceiling:.2f}]" if ceiling < 1.0 else ""
        gate = "  <- GATE (max_papers)" if k == 60 else ""
        print(
            f"  Recall@{k:<6d}      {vals['doi_only']:.3f}      "
            f"{vals['doi_or_title']:.3f}{note}{gate}"
        )

    gate = recalls.get("60", {}).get("doi_or_title", 0.0)
    gate_doi = recalls.get("60", {}).get("doi_only", 0.0)
    verdict = "PASS" if gate >= 0.80 else "FAIL"
    print(f"\nGATE  Recall@60 >= 0.80  ->  {gate:.3f} (doi-or-title)  {verdict}")
    print(f"      doi-only equivalent: {gate_doi:.3f}")

    # What the whole union never found at all — these bound every downstream metric.
    found: set[str] = set()
    for key in ordered:
        p = pool[key]
        d, t = norm(p.doi), norm_title(p.title)
        if d and d in gold_dois:
            found.add(d)
        elif t and t in gold_title_to_doi:
            found.add(gold_title_to_doi[t])
    missed = sorted(gold_dois - found)
    print(f"\nfound {len(found)}/{len(gold_dois)} gold papers anywhere in the union; "
          f"missed {len(missed)}")
    if missed:
        by_doi = {norm(p["doi"]): p for p in gold_doc["papers"]}
        print("\nNEVER RETRIEVED (bounds every downstream metric):")
        for d in missed[:15]:
            p = by_doi.get(d, {})
            print(f"  {p.get('year', '????')} {str(p.get('title'))[:66]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "generated": "T-212 (harness corrected 2026-08-26; see module docstring)",
                "ranked": not args.no_rank,
                "max_per_source": max_per_source,
                "gold_size": len(gold_dois),
                "union_size": len(ordered),
                "recalls": recalls,
                "gate_recall_at_60": gate,
                "gate_recall_at_60_doi_only": gate_doi,
                "gate_pass": gate >= 0.80,
                "per_query": rows,
                "missed": missed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
