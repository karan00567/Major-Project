"""Persistent Chroma vector store over Chunk objects."""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings

from researchgpt.core.models import Chunk


class VectorStore:
    #: Used only if the client will not say. Chroma's local limit is derived
    #: from SQLite's 32,766-variable cap divided by the bindings per row, so it
    #: is a property of the build, not a number to invent.
    FALLBACK_MAX_BATCH = 5000

    def __init__(
        self, path: str = "data/vectorstore", collection: str = "chunks",
        max_batch: int | None = None,
    ) -> None:
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self._path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )
        self.max_batch = max_batch or self._client_max_batch()

    def _client_max_batch(self) -> int:
        try:
            return int(self._client.get_max_batch_size())
        except Exception:
            return self.FALLBACK_MAX_BATCH

    def add(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "paper_id": c.paper_id,
                "section": c.section or "",
                "start_char": c.start_char,
                "end_char": c.end_char,
                "text": c.text,
            }
            for c in chunks
        ]
        # 🔴 Batched because Chroma REJECTS an oversized write rather than
        # splitting it, and the ceiling is a function of corpus size: 640
        # chunks (max_per_source 25) fit in one call, 15,166 (max_per_source
        # 100) do not, and the run died at the ranker 31 minutes in - after
        # retrieval and most of the embedding had been paid for. Any future
        # widening of the pool walks straight back into it.
        #
        # upsert so re-ingestion does not duplicate.
        for start in range(0, len(ids), self.max_batch):
            stop = start + self.max_batch
            self._collection.upsert(
                ids=ids[start:stop],
                embeddings=embeddings[start:stop],
                documents=documents[start:stop],
                metadatas=metadatas[start:stop],
            )

    def query(
        self, embedding: list[float], k: int = 30
    ) -> list[tuple[str, float]]:
        n = min(k, max(self.count(), 1))
        if self.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=n,
            include=["distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        # Chroma returns cosine DISTANCE; convert to similarity.
        out = [
            (cid, float(1.0 - dist))
            for cid, dist in zip(ids, distances, strict=False)
        ]
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:k]

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        result = self._collection.get(
            ids=[chunk_id], include=["metadatas", "documents"]
        )
        ids = result.get("ids") or []
        if not ids:
            return None
        meta = (result.get("metadatas") or [None])[0] or {}
        doc = (result.get("documents") or [None])[0]
        text = meta.get("text") or doc or ""
        section = meta.get("section") or None
        if section == "":
            section = None
        return Chunk(
            chunk_id=chunk_id,
            paper_id=str(meta.get("paper_id") or ""),
            text=text,
            section=section,
            start_char=int(meta.get("start_char") or 0),
            end_char=int(meta.get("end_char") or 0),
        )

    def count(self) -> int:
        return int(self._collection.count())

    def reset(self) -> None:
        name = self._collection.name
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )


__all__ = ["VectorStore"]
