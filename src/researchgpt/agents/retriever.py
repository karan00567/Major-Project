"""T-403 — the Retriever node. Wraps Phase 2; makes no LLM call.

`SPEC §7.2`. Executes the Planner's ``search_plan`` across the enabled
connectors, deduplicates, chunks, and returns **only what is new**.

⚠️ **Deduplication is this node's job, and nothing else will do it.**
``graph/state.py`` gives ``papers`` and ``chunks`` an ``add`` reducer so that a
Critic RETRIEVE loop *adds* coverage instead of starting over. The cost of that
choice is that a retriever which returns a paper already in state duplicates it
silently, and the corpus quietly inflates on iteration 2. ``agents/base.py``
enforces the contract, but the actual identity logic lives here because only
this node knows that the same paper arrives from three sources under three ids.

**Dedup key, in priority order** (T-203):

1. **normalised DOI** — the only real identifier. ``normalise_doi`` already
   strips the ``https://doi.org/`` prefix and lowercases.
2. **normalised title** — for the roughly 1-in-5 OpenAlex records with no DOI,
   and to bridge an arXiv preprint to its published version, which carry
   *different* DOIs (``10.48550/arxiv.*`` vs the publisher's) but the same
   title. Requires ≥25 alphanumeric characters so that short or truncated
   titles cannot collide.

When two records collide, the **richer** one wins: a version with an abstract
beats one without, because T-204/T-505 gate claim-sourcing on
``text_availability`` and an abstract-less duplicate would silently downgrade a
paper the pipeline could otherwise use.

**Degradation is per-source and per-query.** One connector failing, or the
OpenAlex daily budget expiring mid-plan (§0.2 — it is metered now), must not
lose the papers already gathered. Every failure is recorded in
``retrieval_log`` so a thin corpus is diagnosable after the fact rather than by
re-running a 30-minute pipeline.
"""

from __future__ import annotations

import re
import time
from typing import Any

from researchgpt.agents.base import Agent
from researchgpt.core.models import Chunk, Paper
from researchgpt.data.chunker import chunk_paper
from researchgpt.graph.state import ReviewState
from researchgpt.tools.search_sources import (
    OpenAlexBudgetExhausted,
    normalise_doi,
    search_arxiv,
    search_openalex,
    search_semantic_scholar,
)

#: Titles shorter than this are not distinctive enough to dedup on.
MIN_TITLE_KEY_CHARS = 25

#: Dropped before pairing: they carry no retrieval signal and OpenAlex ignores
#: them anyway, so pairing on them would spend a metered search on nothing.
QUERY_STOPWORDS = frozenset(
    {"a", "an", "the", "of", "in", "on", "for", "and", "or", "to", "with", "via"}
)

#: A "Firstname Lastname" token, allowing initials and hyphenated names.
_PERSON = re.compile(r"^[A-Z][A-Za-z.'-]+(?: [A-Z][A-Za-z.'-]+){1,3}$")

#: Fraction of comma-separated fragments that must look like person names
#: before a field is judged to be an author list rather than an abstract.
#: Tuned on the 432-abstract T-212 pool: 0.7 flags 8 records (1.9%), all
#: genuinely author lists, and spares a truncated 185-char real abstract that
#: a looser length-based heuristic wrongly caught.
_AUTHOR_LIST_RATIO = 0.7

#: Seconds a source may spend returning NOTHING before it is dropped for the
#: rest of the run.
#:
#: ⚠️ **The breaker trips on TIME WASTED, not on emptiness** - and the first
#: version got that wrong. Measured on the first M1 run: a 3-consecutive-misses
#: rule disabled **arXiv** after three narrow queries, even though arXiv is
#: unmetered and answers instantly. An empty response that costs nothing is not
#: a problem worth reacting to; the problem is a source that burns wall-clock
#: to tell you nothing.
#:
#: The measured case is Semantic Scholar keyless: it answers roughly 1 query in
#: 3 and spends up to 60s of exponential backoff before degrading to []
#: (decisions.txt D-03 chose to skip the free academic key). Across a 24-task
#: plan that is ~16 minutes of pure sleeping, and the first M1 attempt got
#: through 38 of 72 source-queries in 10 minutes before being killed.
#:
#: 90s allows one full S2 backoff cycle plus slack, so a single unlucky query
#: does not disable a source that is merely having a bad minute.
SOURCE_DEAD_TIME_S = 90.0


def expand_query(query: str) -> list[str]:
    """The planned query, then every 2-term subset of it.

    ``filter=title_and_abstract.search:<q>`` **ANDs every term**, so each term
    the Planner adds is an exclusion filter, not a refinement. Measured
    2026-08-29 against the 34 gold papers whose text OpenAlex holds:

        the flagship's 12 Planner queries          reach   3 / 34
        the same 12 plus every 2-term subset       reach  31 / 34

    and live, at ``max_per_source: 100``, that is union recall 0.057 -> 0.400.

    ⚠️ **The pairs are ADDITIONS, never replacements.** The planned query is
    issued first and unchanged: it is the precise one, and when it does match
    it matches best. The pairs exist to raise the ceiling underneath it.

    All pairs rather than a heuristic head-pair, because the best-reaching pair
    is not predictable from position - for "multi agent retrieval architecture"
    it is "multi retrieval", for "benchmark dataset literature review" it is
    "benchmark dataset". A head-pair policy reaches 25/34; all pairs reach
    31/34, for 5 extra searches on a 4-term query.

    Bounded by ``planner.MAX_QUERY_TERMS`` (6), so a task costs at most
    1 + C(6,2) = 16 searches; the observed 3-4 term plans cost 4-7.
    """
    seen: list[str] = []
    for token in query.split():
        if token.lower() in QUERY_STOPWORDS or token in seen:
            continue
        seen.append(token)
    out = [query]
    for i in range(len(seen)):
        for j in range(i + 1, len(seen)):
            pair = f"{seen[i]} {seen[j]}"
            if pair not in out:
                out.append(pair)
    return out


def looks_like_author_list(abstract: str) -> bool:
    """Is this "abstract" actually a citation string?

    Measured on the T-212 pool: ~1.9% of OpenAlex records carry an author list
    plus venue where the abstract should be, e.g.

        "David Wadden, Shanchuan Lin, Kyle Lo, ... Proceedings of EMNLP 2020."

    Left in, these are chunked into the index, ranked, sent to the Extractor
    (one wasted LLM request each) and produce an empty insight row. Detected on
    the name-list *shape* rather than on length, because short-but-real
    abstracts exist and dropping one is worse than the waste.
    """
    head = abstract[:400]
    parts = [x.strip() for x in head.split(",")]
    if len(parts) < 4:
        return False
    matches = sum(1 for x in parts if _PERSON.match(x))
    return matches / len(parts) >= _AUTHOR_LIST_RATIO


def title_key(title: str | None) -> str:
    key = re.sub(r"[^a-z0-9]+", "", (title or "").lower())
    return key if len(key) >= MIN_TITLE_KEY_CHARS else ""


def paper_keys(paper: Paper) -> tuple[str, str]:
    """(doi_key, title_key). Either may be empty."""
    return normalise_doi(paper.doi) or "", title_key(paper.title)


def _richness(paper: Paper) -> tuple[int, int, int]:
    """Higher is better. Used to pick a winner between duplicate records."""
    return (
        1 if (paper.abstract or "").strip() else 0,
        1 if paper.doi else 0,
        len(paper.abstract or ""),
    )


class Retriever(Agent):
    name = "retriever"
    #: Not fail-soft as a whole: if every source fails, an empty corpus should
    #: stop the run rather than produce a survey of nothing. Individual source
    #: and query failures ARE contained, below.
    fail_soft = False

    def __init__(self, cfg: Any, trace: Any = None) -> None:
        super().__init__(trace=trace)
        self._cfg = cfg

    # -- sources -----------------------------------------------------------

    def _search(self, source: str, query: str, year_min: int | None, limit: int) -> list[Paper]:
        if source == "openalex":
            return search_openalex(query, year_min=year_min, max_results=limit)
        if source == "arxiv":
            return search_arxiv(query, max_results=limit)
        if source == "semantic_scholar":
            return search_semantic_scholar(query, year_min=year_min, max_results=limit)
        raise ValueError(f"unknown source {source!r}")

    # -- run ---------------------------------------------------------------

    def run(self, state: ReviewState) -> dict[str, Any]:
        plan = state.get("search_plan") or []
        if not plan:
            raise ValueError(
                "state['search_plan'] is empty - the Planner (T-402) must run first."
            )

        enabled = list(getattr(self._cfg.sources, "enabled", ["openalex", "arxiv"]))
        max_per_source = self._cfg.sources.max_per_source
        year_min = self._cfg.review.year_min
        iteration = state.get("iteration", 0)

        # Everything already in state, so we return only genuinely new papers.
        seen_doi: set[str] = set()
        seen_title: set[str] = set()
        # 🔴 The LAST-RESORT key, and the one the contract is enforced on.
        # A record with no DOI and a title under MIN_TITLE_KEY_CHARS produces
        # two EMPTY keys, so neither set above can ever recognise it - while
        # `base.py::_check_partial` compares by paper_id and rejects the whole
        # update. That mismatch killed a run on W3167518830, titled "JBI
        # evidence synthesis": 20 characters, no DOI. It bites on any second
        # retrieval pass, the Critic's RETRIEVE loop included.
        seen_ids: set[str] = set()
        for paper in state.get("papers", []):
            doi, title = paper_keys(paper)
            if doi:
                seen_doi.add(doi)
            if title:
                seen_title.add(title)
            seen_ids.add(paper.paper_id)
        # Was anything known before this pass? Counted in PAPERS, not in keys:
        # a state full of DOI-less short-titled records summed to zero here and
        # would have turned "retrieved nothing new" into a hard failure.
        known_before = len(seen_ids)

        fresh: dict[str, Paper] = {}
        log: list[dict[str, Any]] = []
        budget_exhausted = False
        metadata_abstracts = 0
        # Circuit breaker: wall-clock spent per source with nothing to show
        # for it (see SOURCE_DEAD_TIME_S).
        dead_time: dict[str, float] = dict.fromkeys(enabled, 0.0)
        disabled: set[str] = set()

        for task in plan:
            sources = [s for s in (task.sources or enabled) if s in enabled]
            for query in expand_query(task.query):
                for source in sources:
                    if budget_exhausted and source == "openalex":
                        continue
                    if source in disabled:
                        continue
                    started = time.perf_counter()
                    try:
                        found = self._search(
                            source, query, task.year_min or year_min,
                            min(task.max_results or max_per_source, max_per_source),
                        )
                        error = None
                    except OpenAlexBudgetExhausted as exc:
                        # Keep everything gathered so far and stop asking OpenAlex.
                        budget_exhausted = True
                        found, error = [], f"budget_exhausted: {exc}"
                    except Exception as exc:  # one bad query must not sink the plan
                        found, error = [], f"{type(exc).__name__}: {exc}"

                    added = 0
                    for paper in found:
                        if paper.abstract and looks_like_author_list(paper.abstract):
                            # Keep the paper (citable as existing) but not the junk
                            # text: no chunks, no wasted extraction call.
                            paper = paper.model_copy(
                                update={"abstract": None, "text_availability": "none"}
                            )
                            metadata_abstracts += 1
                        doi, title = paper_keys(paper)
                        if paper.paper_id in seen_ids:
                            # Already in state. Unlike the key match below there
                            # is no upgrade path: the reducer ADDS, so returning
                            # it in any form duplicates it.
                            continue
                        if paper.paper_id in fresh:
                            if _richness(paper) > _richness(fresh[paper.paper_id]):
                                fresh[paper.paper_id] = paper
                            continue
                        if (doi and doi in seen_doi) or (title and title in seen_title):
                            # Already known - but a richer copy may still be an upgrade.
                            existing_id = _find_existing(fresh, doi, title)
                            if existing_id and _richness(paper) > _richness(fresh[existing_id]):
                                fresh[existing_id] = paper
                            continue
                        if doi:
                            seen_doi.add(doi)
                        if title:
                            seen_title.add(title)
                        fresh[paper.paper_id] = paper
                        added += 1

                    elapsed = time.perf_counter() - started
                    if found:
                        dead_time[source] = 0.0
                    else:
                        dead_time[source] = dead_time.get(source, 0.0) + elapsed
                        if dead_time[source] >= SOURCE_DEAD_TIME_S:
                            disabled.add(source)
                            self._emit(
                                "source_disabled",
                                {"source": source,
                                 "wasted_seconds": round(dead_time[source], 1),
                                 "remaining_tasks": len(plan) - plan.index(task) - 1,
                                 "why": "spent this long returning nothing; an instant "
                                        "empty response would NOT trip this."},
                                iteration,
                            )

                    # `query` is what was ASKED; `planned_query` is what the
                    # Planner wrote. They differ for every widened pair, and a
                    # log carrying only one of them cannot be compared against
                    # a pre-widening run months later.
                    log.append({
                        "sq_id": task.sq_id, "query": query,
                        "planned_query": task.query, "source": source,
                        "returned": len(found), "new": added, "error": error,
                        "iteration": iteration,
                    })
                    self._emit(
                        "search",
                        {"sq_id": task.sq_id, "query": query,
                         "planned_query": task.query, "source": source,
                         "returned": len(found), "new": added, "error": error},
                        iteration,
                    )

        papers = list(fresh.values())
        chunks = self._chunk(papers)

        failures = [row for row in log if row["error"]]
        if not papers and known_before == 0:
            raise ValueError(
                f"Retrieval returned nothing across {len(log)} source-queries "
                f"({len(failures)} errored). Refusing to continue with an empty corpus. "
                f"First errors: {[row['error'] for row in failures[:3]]}"
            )

        self._emit(
            "retrieval_summary",
            {"queries": len(plan),
             "issued_queries": sum(len(expand_query(t.query)) for t in plan),
             "source_queries": len(log), "failures": len(failures),
             "new_papers": len(papers), "new_chunks": len(chunks),
             "with_abstract": sum(1 for p in papers if (p.abstract or "").strip()),
             "metadata_abstracts_dropped": metadata_abstracts,
             "sources_disabled": sorted(disabled),
             "budget_exhausted": budget_exhausted},
            iteration,
        )
        return {"papers": papers, "chunks": chunks, "retrieval_log": log}

    # -- chunking ----------------------------------------------------------

    def _chunk(self, papers: list[Paper]) -> list[Chunk]:
        """Chunk the abstract. Full text arrives later via T-204's PDF loader.

        A paper with no abstract yields no chunks and so cannot be retrieved or
        cited for a claim — which is the T-505 abstract-only rule arriving one
        stage early, and is the correct behaviour: an empty chunk would let a
        paper be ranked on its title alone.
        """
        out: list[Chunk] = []
        for paper in papers:
            text = (paper.abstract or "").strip()
            if not text:
                continue
            title = (paper.title or "").strip()
            # Prepend the title: it carries most of the topical signal for
            # BM25 and the reranker, and abstracts often never restate it.
            body = f"{title}\n\n{text}" if title else text
            out.extend(
                chunk_paper(
                    paper.paper_id, body,
                    chunk_size=self._cfg.retrieval.chunk_size,
                    chunk_overlap=self._cfg.retrieval.chunk_overlap,
                )
            )
        return out


def _find_existing(pool: dict[str, Paper], doi: str, title: str) -> str | None:
    for pid, paper in pool.items():
        d, t = paper_keys(paper)
        if (doi and d == doi) or (title and t == title):
            return pid
    return None


__all__ = ["Retriever", "paper_keys", "title_key", "looks_like_author_list",
           "SOURCE_DEAD_TIME_S", "expand_query", "QUERY_STOPWORDS"]
