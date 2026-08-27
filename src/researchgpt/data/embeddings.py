"""CPU sentence-transformers wrapper for BAAI/bge-small-en-v1.5."""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

#: handoffs/phase2_complete.md §4.4 — the suite logged "unauthenticated
#: requests" because HF_TOKEN sits in .env and nothing loaded it. Hub reads the
#: env var, so a single load_dotenv() at import is the whole fix. Never raises:
#: an absent .env just leaves the anonymous path in place.
try:  # pragma: no cover - environment plumbing
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._model = SentenceTransformer(model_name, device=device)
        dim_fn = getattr(
            self._model, "get_embedding_dimension", None
        ) or getattr(self._model, "get_sentence_embedding_dimension")
        self._dim = int(dim_fn())

    @property
    def dim(self) -> int:
        return self._dim

    def encode(
        self, texts: list[str], show_progress: bool = False
    ) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=self._batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,
        )
        return [v.tolist() for v in vectors]

    def encode_query(self, text: str) -> list[float]:
        prefixed = _QUERY_PREFIX + text
        vec = self._model.encode(
            [prefixed],
            batch_size=1,
            show_progress_bar=False,
            normalize_embeddings=True,
        )[0]
        return vec.tolist()


__all__ = ["Embedder"]
