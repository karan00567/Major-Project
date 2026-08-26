"""JSONL trace logger for every agent event in a run.

Schema is frozen: every report figure is derived from these lines. A write must
never raise into the caller — losing one line is acceptable; killing a long run
because of a logging bug is not.
"""

from __future__ import annotations

import json
import pathlib
import threading
from datetime import datetime, timezone
from typing import Any


class TraceLogger:
    def __init__(self, run_id: str, runs_dir: str = "outputs/runs") -> None:
        self._run_id = run_id
        self._run_dir = pathlib.Path(runs_dir) / run_id
        self._path = self._run_dir / "trace.jsonl"
        self._lock = threading.Lock()
        self._fp: Any = None
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._fp = open(self._path, "a", encoding="utf-8")

    @property
    def run_dir(self) -> pathlib.Path:
        return self._run_dir

    def event(
        self,
        agent: str,
        event: str,
        payload: dict | None = None,
        iteration: int | None = None,
    ) -> None:
        try:
            safe_payload: dict
            if payload is None:
                safe_payload = {}
            else:
                try:
                    json.dumps(payload)
                    safe_payload = payload
                except (TypeError, ValueError) as exc:
                    safe_payload = {
                        "repr": repr(payload),
                        "serialisation_error": str(exc),
                    }

            record = {
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "run_id": self._run_id,
                "agent": agent,
                "event": event,
                "iteration": iteration,
                "payload": safe_payload,
            }
            line = json.dumps(record, ensure_ascii=False)
            with self._lock:
                if self._fp is None or self._fp.closed:
                    return
                self._fp.write(line + "\n")
                self._fp.flush()
        except Exception:
            # Never raise out of event() — lose the line, keep the run.
            return

    def close(self) -> None:
        with self._lock:
            if self._fp is not None and not self._fp.closed:
                self._fp.close()
            self._fp = None

    def __enter__(self) -> TraceLogger:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


__all__ = ["TraceLogger"]
