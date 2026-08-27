"""CPU cross-encoder reranker. Model path is a constructor argument."""

from __future__ import annotations

import time

from sentence_transformers import CrossEncoder

from researchgpt.core.models import Chunk

#: handoffs/phase2_complete.md §4.4 — the suite logged "unauthenticated
#: requests" because HF_TOKEN sits in .env and nothing loaded it. Hub reads the
#: env var, so a single load_dotenv() at import is the whole fix. Never raises:
#: an absent .env just leaves the anonymous path in place.
try:  # pragma: no cover - environment plumbing
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


class Reranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
        batch_size: int = 16,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._model = CrossEncoder(model_name, device=device)
        self._last_latency_ms = 0

    @property
    def last_latency_ms(self) -> int:
        return self._last_latency_ms

    def rerank(
        self, query: str, chunks: list[Chunk], top_k: int = 12
    ) -> list[tuple[Chunk, float]]:
        if not chunks:
            return []
        pairs = [(query, c.text) for c in chunks]
        t0 = time.perf_counter()
        scores = self._model.predict(pairs, batch_size=self._batch_size)
        self._last_latency_ms = int((time.perf_counter() - t0) * 1000)
        ranked = sorted(
            zip(chunks, (float(s) for s in scores), strict=True),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]


__all__ = ["Reranker"]
