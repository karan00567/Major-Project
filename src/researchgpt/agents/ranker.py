"""INGEST + RANK — the node between Retriever and Extractor (part of T-405).

`SPEC §7.2` splits retrieval from ranking, and TASKLIST T-405 wires
``PLANNER -> RETRIEVER -> INGEST -> RANK -> EXTRACTOR -> WRITER``. This module
is the INGEST+RANK pair: it embeds and indexes the accumulated chunks (T-206,
T-207, T-208), retrieves per sub-question through the T-209 hybrid retriever,
reranks with T-210, and **reorders ``state['papers']`` so that the prefix the
Extractor takes is the top-N rather than an arbitrary N**.

★ **Why the reordering matters more than it looks.** ``Extractor.run`` reads
``papers[:max_papers]``. Without a ranking stage that prefix is *insertion
order* — i.e. whichever query happened to run first. That is exactly the defect
found in the T-212 harness on 2026-08-26, where ``union[:60]`` never ranked
anything and the gate read 0.029 instead of 0.057. The same bug at pipeline
level would silently feed the Extractor the wrong 60 papers, and nothing
downstream would notice.

**Round-robin across sub-questions, not a global top-N.** A global cut lets one
productive sub-question crowd out the rest, and coverage across sub-questions
is what the Critic (T-506) measures. Interleaving guarantees every
sub-question contributes before any contributes twice.

⚠️ **The reranker is ordering-only.** T-335 adopted a fine-tuned cross-encoder
whose absolute scores are not calibrated. This module ranks with it and never
thresholds on its score — see ``Reranker.scores_are_calibrated``.
"""

from __future__ import annotations

import tempfile
from typing import Any

from researchgpt.agents.base import Agent
from researchgpt.core.models import Paper
from researchgpt.data.bm25_index import BM25Index
from researchgpt.data.embeddings import Embedder
from researchgpt.data.vectorstore import VectorStore
from researchgpt.graph.state import ReviewState
from researchgpt.tools.hybrid_retriever import HybridRetriever
from researchgpt.tools.reranker import Reranker


class Ranker(Agent):
    """Embeds, indexes, retrieves per sub-question, and reorders the corpus."""

    name = "ranker"
    fail_soft = False

    def __init__(self, cfg: Any, trace: Any = None, store_path: str | None = None) -> None:
        super().__init__(trace=trace)
        self._cfg = cfg
        self._store_path = store_path

    def run(self, state: ReviewState) -> dict[str, Any]:
        chunks = list(state.get("chunks") or [])
        papers = list(state.get("papers") or [])
        if not papers:
            raise ValueError("no papers to rank - the Retriever must run first.")
        iteration = state.get("iteration", 0)

        queries = [sq.text for sq in state.get("sub_questions") or []]
        if not queries:
            queries = [state.get("research_question") or ""]

        if not chunks:
            # Every paper was abstract-less. Nothing to rank on; preserve order
            # rather than pretend a ranking happened.
            self._emit("rank_skipped", {"reason": "no chunks", "papers": len(papers)},
                       iteration)
            return {}

        cfg = self._cfg.retrieval
        embedder = Embedder(model_name=self._cfg.embeddings.model,
                            device=self._cfg.embeddings.device,
                            batch_size=self._cfg.embeddings.batch_size)
        vectors = embedder.encode([c.text for c in chunks])

        tmp = None
        path = self._store_path
        if path is None:
            tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
            path = tmp.name
        try:
            store = VectorStore(path=path, collection=f"run_{state.get('run_id', 'x')}")
            store.add(chunks, vectors)
            bm25 = BM25Index()
            bm25.build(chunks)

            # ⚠️ Widen the first stage to the corpus. The production dense_k/
            # sparse_k of 30 returns a GLOBAL top-60 and silently discards more
            # of each sub-question's candidates the larger the pool grows -
            # the second T-212 harness defect, found 2026-08-26 and
            # regression-tested. Here the pool IS the corpus, so nothing is lost.
            rank_cfg = cfg.model_copy(
                update={"dense_k": len(chunks), "sparse_k": len(chunks)}
            )
            retriever = HybridRetriever(store, bm25, embedder, rank_cfg)
            reranker = Reranker(model_name=cfg.reranker,
                                device=self._cfg.embeddings.device) if cfg.rerank else None

            per_query: list[list[str]] = []
            for query in queries:
                fused = retriever.retrieve(query)
                candidates = [c for c, _ in fused]
                if reranker is not None and candidates:
                    top = reranker.rerank(query, candidates, top_k=len(candidates))
                    candidates = [c for c, _ in top]
                # Chunk order -> paper order, first occurrence wins.
                ordered, seen = [], set()
                for chunk in candidates:
                    if chunk.paper_id not in seen:
                        seen.add(chunk.paper_id)
                        ordered.append(chunk.paper_id)
                per_query.append(ordered)
            store.reset()
        finally:
            if tmp is not None:
                tmp.cleanup()

        ranked_ids = _round_robin(per_query)
        by_id = {p.paper_id: p for p in papers}
        reordered: list[Paper] = [by_id[i] for i in ranked_ids if i in by_id]
        # Papers with no chunk (no abstract) never appear in a ranking; keep
        # them at the tail so they stay citable as existing (T-505).
        reordered += [p for p in papers if p.paper_id not in set(ranked_ids)]

        self._emit(
            "rank_summary",
            {"queries": len(queries), "chunks": len(chunks), "papers": len(papers),
             "ranked": len(ranked_ids), "unranked_tail": len(papers) - len(ranked_ids),
             "reranker": cfg.reranker if cfg.rerank else None,
             "top_10": [ (by_id[i].title or "")[:60] for i in ranked_ids[:10] ]},
            iteration,
        )

        # `papers` accumulates via an `add` reducer, so this node cannot return
        # a reordered list without duplicating the corpus. The order is handed
        # on out-of-band and applied by graph/build.py.
        return {"artefacts": {"ranked_paper_ids": [p.paper_id for p in reordered]}}


def _round_robin(per_query: list[list[str]]) -> list[str]:
    """Interleave per-sub-question rankings; first occurrence wins."""
    out, seen = [], set()
    for rank in range(max((len(q) for q in per_query), default=0)):
        for query_ranking in per_query:
            if rank < len(query_ranking):
                pid = query_ranking[rank]
                if pid not in seen:
                    seen.add(pid)
                    out.append(pid)
    return out


__all__ = ["Ranker"]
