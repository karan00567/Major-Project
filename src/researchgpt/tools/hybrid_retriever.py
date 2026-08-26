"""Reciprocal Rank Fusion hybrid retriever (dense + BM25)."""

from __future__ import annotations

from researchgpt.core.models import Chunk, RetrievalConfig
from researchgpt.data.bm25_index import BM25Index
from researchgpt.data.embeddings import Embedder
from researchgpt.data.vectorstore import VectorStore


def rrf_fuse(
    rankings: list[list[str]], rrf_k: int = 60
) -> list[tuple[str, float]]:
    """Pure RRF: score(d) = Σ 1/(rrf_k + rank(d)), rank 1-based."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank_zero, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank_zero + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class HybridRetriever:
    def __init__(
        self,
        store: VectorStore,
        bm25: BM25Index,
        embedder: Embedder,
        cfg: RetrievalConfig,
    ) -> None:
        self._store = store
        self._bm25 = bm25
        self._embedder = embedder
        self._cfg = cfg

    def retrieve(self, query: str) -> list[tuple[Chunk, float]]:
        q_emb = self._embedder.encode_query(query)
        dense = self._store.query(q_emb, k=self._cfg.dense_k)
        sparse = self._bm25.query(query, k=self._cfg.sparse_k)
        dense_ids = [cid for cid, _ in dense]
        sparse_ids = [cid for cid, _ in sparse]
        fused = rrf_fuse([dense_ids, sparse_ids], rrf_k=self._cfg.rrf_k)
        out: list[tuple[Chunk, float]] = []
        for cid, score in fused:
            chunk = self._store.get_chunk(cid)
            if chunk is not None:
                out.append((chunk, score))
        return out


__all__ = ["rrf_fuse", "HybridRetriever"]
