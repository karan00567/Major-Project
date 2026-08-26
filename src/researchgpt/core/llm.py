"""Single LLM adapter for the whole project.

Every generative call goes through this module. No other module may import an
HTTP client or a provider SDK. Enforcement of TASKLIST §0.1 (free open-weight
allowlist) lives here: a forbidden model raises before any network call.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from dotenv import load_dotenv

from researchgpt.core.models import ALLOWED_MODELS, MODEL_PROVIDER, LLMConfig

if TYPE_CHECKING:
    from researchgpt.core.logging import TraceLogger


class ModelNotAllowed(ValueError):
    """Raised when a model is not in ALLOWED_MODELS."""


class RateLimitExceeded(RuntimeError):
    """Raised after max_retries consecutive 429 responses."""


class LLMError(RuntimeError):
    """Raised for missing keys, HTTP failures, or malformed provider responses."""


_FENCE_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)
_BARE_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict:
    """Strip markdown fences / leading prose, then json.loads a JSON object."""
    if text is None:
        raise ValueError("No JSON object can be recovered from empty input")
    raw = text.strip()
    if not raw:
        raise ValueError("No JSON object can be recovered from empty input")

    # Prefer fenced blocks (```json ... ``` or ``` ... ```).
    m = _FENCE_RE.search(raw)
    if m:
        candidate = m.group(1).strip()
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # Handle a trailing fence with a leading space, e.g. ' {"a": 1}\n```'
    if raw.endswith("```"):
        stripped = raw[: raw.rfind("```")].strip()
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # Direct parse.
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Last resort: first {...} span in the text.
    m2 = _BARE_OBJECT_RE.search(raw)
    if m2:
        try:
            obj = json.loads(m2.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise ValueError("No JSON object can be recovered")


class LLMClient:
    def __init__(self, cfg: LLMConfig, trace: TraceLogger | None = None) -> None:
        load_dotenv()
        self._cfg = cfg
        self._trace = trace
        self._request_count = 0
        self._cache_hits = 0
        self._last_request_mono: float | None = None
        self._cache_dir = pathlib.Path(cfg.cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_cache: bool = True,
    ) -> str:
        resolved_model = model if model is not None else self._cfg.model
        resolved_temp = (
            temperature if temperature is not None else self._cfg.temperature
        )
        resolved_max = max_tokens if max_tokens is not None else self._cfg.max_tokens

        # Allowlist check FIRST — before cache, throttle, or any HTTP.
        if resolved_model not in ALLOWED_MODELS:
            raise ModelNotAllowed(
                f"Model {resolved_model!r} is not in ALLOWED_MODELS "
                f"(TASKLIST §0.1). Permitted: {sorted(ALLOWED_MODELS)}"
            )

        provider = MODEL_PROVIDER[resolved_model]
        prompt_hash = hashlib.sha256(
            f"{resolved_model}|{resolved_temp}|{resolved_max}|{prompt}".encode("utf-8")
        ).hexdigest()

        if use_cache:
            cached = self._read_cache(prompt_hash)
            if cached is not None:
                self._cache_hits += 1
                self._log(
                    "cache_hit",
                    {
                        "model": resolved_model,
                        "prompt_hash": prompt_hash,
                        "latency_ms": 0,
                        "attempt": 0,
                    },
                )
                return cached

        # Live call path — throttle applies only here.
        consecutive_429 = 0
        last_exc: Exception | None = None
        for attempt in range(self._cfg.max_retries + 1):
            self._throttle()
            t0 = time.monotonic()
            try:
                text = self._dispatch(
                    provider, resolved_model, prompt, resolved_temp, resolved_max
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                self._request_count += 1
                self._log(
                    "request",
                    {
                        "model": resolved_model,
                        "prompt_hash": prompt_hash,
                        "latency_ms": latency_ms,
                        "attempt": attempt,
                    },
                )
                if use_cache:
                    self._write_cache(
                        prompt_hash, resolved_model, prompt, text
                    )
                return text
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                latency_ms = int((time.monotonic() - t0) * 1000)
                if status == 429:
                    consecutive_429 += 1
                    if consecutive_429 > self._cfg.max_retries:
                        self._log(
                            "error",
                            {
                                "model": resolved_model,
                                "prompt_hash": prompt_hash,
                                "latency_ms": latency_ms,
                                "attempt": attempt,
                                "status": status,
                            },
                        )
                        raise RateLimitExceeded(
                            f"Rate limit exceeded for model {resolved_model!r} "
                            f"after {consecutive_429} consecutive 429 responses "
                            f"({attempt + 1} attempts)"
                        ) from exc
                    wait = self._backoff_seconds(attempt, exc.response)
                    self._log(
                        "retry",
                        {
                            "model": resolved_model,
                            "prompt_hash": prompt_hash,
                            "latency_ms": latency_ms,
                            "attempt": attempt,
                            "status": status,
                            "wait_s": wait,
                        },
                    )
                    time.sleep(wait)
                    continue
                if 500 <= status < 600:
                    if attempt >= self._cfg.max_retries:
                        self._log(
                            "error",
                            {
                                "model": resolved_model,
                                "prompt_hash": prompt_hash,
                                "latency_ms": latency_ms,
                                "attempt": attempt,
                                "status": status,
                            },
                        )
                        raise LLMError(
                            f"HTTP {status} from {provider} for model "
                            f"{resolved_model!r} after {attempt + 1} attempts"
                        ) from exc
                    wait = self._backoff_seconds(attempt, exc.response)
                    self._log(
                        "retry",
                        {
                            "model": resolved_model,
                            "prompt_hash": prompt_hash,
                            "latency_ms": latency_ms,
                            "attempt": attempt,
                            "status": status,
                            "wait_s": wait,
                        },
                    )
                    time.sleep(wait)
                    continue
                self._log(
                    "error",
                    {
                        "model": resolved_model,
                        "prompt_hash": prompt_hash,
                        "latency_ms": latency_ms,
                        "attempt": attempt,
                        "status": status,
                    },
                )
                raise LLMError(
                    f"HTTP {status} from {provider} for model {resolved_model!r}"
                ) from exc
            except httpx.RequestError as exc:
                last_exc = exc
                latency_ms = int((time.monotonic() - t0) * 1000)
                if attempt >= self._cfg.max_retries:
                    self._log(
                        "error",
                        {
                            "model": resolved_model,
                            "prompt_hash": prompt_hash,
                            "latency_ms": latency_ms,
                            "attempt": attempt,
                        },
                    )
                    raise LLMError(
                        f"Network error calling {provider} for model "
                        f"{resolved_model!r}: {exc}"
                    ) from exc
                wait = min(2**attempt, 60)
                self._log(
                    "retry",
                    {
                        "model": resolved_model,
                        "prompt_hash": prompt_hash,
                        "latency_ms": latency_ms,
                        "attempt": attempt,
                        "wait_s": wait,
                    },
                )
                time.sleep(wait)

        raise RateLimitExceeded(
            f"Rate limit exceeded for model {resolved_model!r} "
            f"after {consecutive_429} consecutive 429 responses"
        ) from last_exc

    def _throttle(self) -> None:
        rpm = self._cfg.requests_per_minute
        if rpm <= 0:
            return
        min_interval = 60.0 / rpm
        now = time.monotonic()
        if self._last_request_mono is not None:
            elapsed = now - self._last_request_mono
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        self._last_request_mono = time.monotonic()

    @staticmethod
    def _backoff_seconds(attempt: int, response: httpx.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
        return float(min(2**attempt, 60))

    def _dispatch(
        self,
        provider: str,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        if provider == "google":
            return self._google_complete(model, prompt, temperature, max_tokens)
        if provider == "groq":
            return self._groq_complete(model, prompt, temperature, max_tokens)
        raise LLMError(f"Unknown provider {provider!r} for model {model!r}")

    def _google_complete(
        self, model: str, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError(
                "GEMINI_API_KEY is missing from the environment / .env "
                "(required for Google-provider models)"
            )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, params={"key": key}, json=body)
            resp.raise_for_status()
            data = resp.json()

        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"Malformed Google response for model {model!r}: missing parts"
            ) from exc

        texts: list[str] = []
        for part in parts:
            # Gemma emits reasoning parts flagged thought=true; skip them.
            if part.get("thought") is True:
                continue
            t = part.get("text")
            if t:
                texts.append(t)
        if not texts:
            raise LLMError(
                f"Empty Google response for model {model!r} "
                "(all parts were thought-only or missing text)"
            )
        return "".join(texts)

    def _groq_complete(
        self, model: str, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise LLMError(
                "GROQ_API_KEY is missing from the environment / .env "
                "(required for Groq-provider models)"
            )
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}"}
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"Malformed Groq response for model {model!r}: missing content"
            ) from exc
        if content is None:
            raise LLMError(f"Empty Groq response for model {model!r}")
        return content

    def _cache_path(self, prompt_hash: str) -> pathlib.Path:
        return self._cache_dir / f"{prompt_hash}.json"

    def _read_cache(self, prompt_hash: str) -> str | None:
        path = self._cache_path(prompt_hash)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            resp = data.get("response")
            return resp if isinstance(resp, str) else None
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def _write_cache(
        self, prompt_hash: str, model: str, prompt: str, response: str
    ) -> None:
        path = self._cache_path(prompt_hash)
        record = {
            "model": model,
            "prompt": prompt,
            "response": response,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        try:
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        except OSError:
            # Cache write failure must not kill the call.
            return

    def _log(self, event: str, payload: dict) -> None:
        if self._trace is None:
            return
        self._trace.event(agent="llm", event=event, payload=payload)


__all__ = [
    "ModelNotAllowed",
    "RateLimitExceeded",
    "LLMError",
    "extract_json",
    "LLMClient",
]
