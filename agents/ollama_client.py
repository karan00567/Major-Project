from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from datetime import datetime, timezone
from typing import Any

import httpx

DEFAULT_HOST = "http://localhost:8080"


DEFAULT_NUM_CTX = 8192


DEFAULT_NUM_PREDICT = 2_560


DEFAULT_TIMEOUT = 600.0


class OllamaError(RuntimeError):
    pass


class OllamaClient:

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        *,
        temperature: float = 0.0,
        num_ctx: int = DEFAULT_NUM_CTX,
        cache_dir: str | os.PathLike[str] = "agents/cache",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST") or DEFAULT_HOST).rstrip("/")
        if not self.host.startswith("http"):

            self.host = f"http://{self.host}"
        self.model = model or os.getenv("OLLAMA_MODEL") or "qwen2.5:3b-instruct"
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout
        self._cache_dir = pathlib.Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._request_count = 0
        self._cache_hits = 0


        self.latencies: list[float] = []


    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    def health(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.host}/api/tags")
                resp.raise_for_status()
                data = resp.json()
        except httpx.RequestError as exc:
            return {
                "ok": False,
                "host": self.host,
                "error": f"cannot reach Ollama at {self.host}: {exc}",
                "hint": (
                    "Is `ollama serve` running on that machine, and is it bound "
                    "to this port? Ollama's default is 11434, not 8080 - set "
                    "OLLAMA_HOST=0.0.0.0:8080 on the server, or point OLLAMA_HOST "
                    "here at the port it actually uses. Across two laptops, "
                    "localhost will never work: use the server's LAN IP."
                ),
            }
        except httpx.HTTPStatusError as exc:
            return {
                "ok": False,
                "host": self.host,
                "error": f"HTTP {exc.response.status_code} from {self.host}/api/tags",
            }

        models = [m.get("name", "") for m in (data.get("models") or [])]
        return {
            "ok": True,
            "host": self.host,
            "models": models,
            "model_present": self.model in models,
        }


    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_cache: bool = True,
        force_json: bool = False,
    ) -> str:
        resolved_model = model or self.model
        resolved_temp = self.temperature if temperature is None else temperature
        resolved_max = max_tokens or DEFAULT_NUM_PREDICT

        key = hashlib.sha256(
            f"{resolved_model}|{resolved_temp}|{resolved_max}|"
            f"{self.num_ctx}|{force_json}|{prompt}".encode("utf-8")
        ).hexdigest()

        if use_cache:
            cached = self._read_cache(key)
            if cached is not None:
                self._cache_hits += 1
                self.latencies.append(0.0)
                return cached

        body: dict[str, Any] = {
            "model": resolved_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": resolved_temp,
                "num_predict": resolved_max,

                "num_ctx": self.num_ctx,
            },
        }
        if force_json:
            body["format"] = "json"

        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.host}/api/generate", json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = str(exc.response.json().get("error", ""))[:300]
            except Exception:
                detail = exc.response.text[:300]
            if exc.response.status_code == 404:
                raise OllamaError(
                    f"Model {resolved_model!r} is not on the server at {self.host}. "
                    f"Pull it there first:  ollama pull {resolved_model}\n"
                    f"Server said: {detail}"
                ) from exc
            raise OllamaError(
                f"HTTP {exc.response.status_code} from {self.host}: {detail}"
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.host}: {exc}. "
                f"Run `python -m agents.probe` for a diagnosis."
            ) from exc

        latency = time.monotonic() - t0
        self.latencies.append(latency)
        self._request_count += 1

        text = data.get("response")
        if not isinstance(text, str) or not text.strip():
            raise OllamaError(
                f"Empty response from {resolved_model!r}. "
                f"done_reason={data.get('done_reason')!r}. If that is 'length', "
                f"num_predict ({resolved_max}) was spent before any content - "
                f"raise it, or the model is emitting a reasoning preamble."
            )

        if use_cache:
            self._write_cache(key, resolved_model, prompt, text, data, latency)
        return text


    def _cache_path(self, key: str) -> pathlib.Path:
        return self._cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> str | None:
        path = self._cache_path(key)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            resp = data.get("response")
            return resp if isinstance(resp, str) else None
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def _write_cache(
        self,
        key: str,
        model: str,
        prompt: str,
        response: str,
        raw: dict[str, Any],
        latency: float,
    ) -> None:
        record = {
            "model": model,
            "provider": "ollama",
            "host": self.host,
            "num_ctx": self.num_ctx,
            "prompt": prompt,
            "response": response,
            "latency_s": round(latency, 2),


            "prompt_eval_count": raw.get("prompt_eval_count"),
            "eval_count": raw.get("eval_count"),
            "total_duration_ns": raw.get("total_duration"),
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        try:
            self._cache_path(key).write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:

            return


__all__ = ["OllamaClient", "OllamaError", "DEFAULT_HOST", "DEFAULT_NUM_CTX"]
