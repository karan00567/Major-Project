"""BM25 sparse index over chunks, persistable to disk."""

from __future__ import annotations

import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from researchgpt.core.models import Chunk

_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.split(text.lower()) if t]


class BM25Index:
    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._chunk_ids: list[str] = []
        self._corpus_tokens: list[list[str]] = []

    def build(self, chunks: list[Chunk]) -> None:
        self._chunk_ids = [c.chunk_id for c in chunks]
        self._corpus_tokens = [_tokenize(c.text) for c in chunks]
        if not self._corpus_tokens:
            self._bm25 = None
            return
        self._bm25 = BM25Okapi(self._corpus_tokens)

    def query(self, text: str, k: int = 30) -> list[tuple[str, float]]:
        if self._bm25 is None or not self._chunk_ids:
            return []
        tokens = _tokenize(text)
        scores = self._bm25.get_scores(tokens)
        paired = list(zip(self._chunk_ids, (float(s) for s in scores), strict=True))
        paired.sort(key=lambda x: x[1], reverse=True)
        return paired[:k]

    def save(self, path: str = "data/bm25.pkl") -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("wb") as fh:
            pickle.dump(
                {
                    "chunk_ids": self._chunk_ids,
                    "corpus_tokens": self._corpus_tokens,
                },
                fh,
            )

    @classmethod
    def load(cls, path: str = "data/bm25.pkl") -> BM25Index:
        idx = cls()
        with Path(path).open("rb") as fh:
            data = pickle.load(fh)
        idx._chunk_ids = data["chunk_ids"]
        idx._corpus_tokens = data["corpus_tokens"]
        if idx._corpus_tokens:
            idx._bm25 = BM25Okapi(idx._corpus_tokens)
        return idx


__all__ = ["BM25Index"]
