"""CPU cross-encoder reranker. Model path is a constructor argument.

Two backends, chosen by what ``model_name`` points at:

* a Hugging Face model id, or a directory of PyTorch weights -> ``CrossEncoder``
* **a directory containing a ``.onnx`` graph -> onnxruntime** (T-333)

The ONNX backend exists because **T-335 gates the quantized model, and a gate is
worthless if the pipeline then runs something else.** That is exactly the
mismatch T-304 caught on the verifier: the artefact that passed the gate was not
the artefact that would have shipped. ``CrossEncoder`` cannot load an ONNX
graph, so without this the tuned reranker could only be "promoted" nominally.

⚠️ **A missing local model never blocks a run.** The tuned weights live under
``data/models/`` which is gitignored and rebuilt from Kaggle, so a fresh clone
has a config naming a path that does not exist. Rather than crash the pipeline,
the reranker warns and falls back to the stock model - same discipline as
``TraceLogger`` and the Phase 6B registry, which never raise into their callers.
"""

from __future__ import annotations

import logging
import pathlib
import time

from sentence_transformers import CrossEncoder

from researchgpt.core.models import Chunk

log = logging.getLogger(__name__)

#: Fallback when a configured local model is absent. Also the T-210 default.
STOCK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

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
        self._device = device
        self._batch_size = batch_size
        self._last_latency_ms = 0
        self._session = None
        self._tokenizer = None

        resolved = self._resolve(model_name)
        self._model_name = resolved
        onnx_path = self._find_onnx(resolved)
        if onnx_path is not None:
            self._load_onnx(onnx_path, resolved)
        else:
            self._model = CrossEncoder(resolved, device=device)

    # -- backend selection -------------------------------------------------

    @staticmethod
    def _resolve(model_name: str) -> str:
        """Fall back to the stock model if a local path is configured but absent."""
        looks_local = any(sep in model_name for sep in ("/", "\\")) and not model_name.count(
            "/"
        ) == 1
        if looks_local or pathlib.Path(model_name).is_absolute():
            if not pathlib.Path(model_name).exists():
                log.warning(
                    "Reranker model %r does not exist; falling back to %s. Rebuild it "
                    "with the Kaggle notebook + `python -m researchgpt.rerank.export_onnx`.",
                    model_name, STOCK_MODEL,
                )
                return STOCK_MODEL
        return model_name

    @staticmethod
    def _find_onnx(model_name: str) -> pathlib.Path | None:
        path = pathlib.Path(model_name)
        if not path.is_dir():
            return None
        return next(path.glob("*quantized*.onnx"), None) or next(path.glob("*.onnx"), None)

    def _load_onnx(self, onnx_path: pathlib.Path, model_dir: str) -> None:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        self._session = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        self._input_names = {i.name for i in self._session.get_inputs()}
        self._tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self._model = None
        log.info("Reranker using ONNX backend: %s", onnx_path)

    def _score_onnx(self, pairs: list[tuple[str, str]]) -> list[float]:
        import numpy as np

        out: list[float] = []
        for start in range(0, len(pairs), self._batch_size):
            batch = pairs[start : start + self._batch_size]
            enc = self._tokenizer([q for q, _ in batch], [t for _, t in batch],
                                  padding=True, truncation=True, max_length=512,
                                  return_tensors="np")
            feeds = {k: v.astype(np.int64) for k, v in enc.items()
                     if k in self._input_names}
            out.extend(self._session.run(None, feeds)[0].reshape(-1).tolist())
        return [float(x) for x in out]

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
        scores = (
            self._score_onnx(pairs)
            if self._session is not None
            else self._model.predict(pairs, batch_size=self._batch_size)
        )
        self._last_latency_ms = int((time.perf_counter() - t0) * 1000)
        ranked = sorted(
            zip(chunks, (float(s) for s in scores), strict=True),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]


__all__ = ["Reranker", "STOCK_MODEL"]
