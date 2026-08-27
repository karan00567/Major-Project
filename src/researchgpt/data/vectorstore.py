"""Persistent Chroma vector store over Chunk objects."""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings

from researchgpt.core.models import Chunk


class VectorStore:
    def __init__(
        self, path: str = "data/vectorstore", collection: str = "chunks"
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
        # upsert so re-ingestion does not duplicate
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
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
