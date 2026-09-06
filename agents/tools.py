from __future__ import annotations

import json
import pathlib
import re
from string import Template

from pydantic import BaseModel

PROMPT_DIR = pathlib.Path(__file__).parent / "prompts"


class EvidenceSpan(BaseModel):
    chunk_id: str
    quote: str
    start_char: int
    end_char: int


class PaperInsight(BaseModel):
    paper_id: str
    methodology: str | None = None
    advantages: str | None = None
    disadvantages: str | None = None
    critique: str | None = None
    datasets: list[str] = []
    metrics: list[str] = []
    results: str | None = None
    limitations: str | None = None
    cluster: str | None = None
    evidence_spans: list[EvidenceSpan] = []
    extraction_note: str | None = None


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_BARE_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict:
    if text is None:
        raise ValueError("No JSON object can be recovered from empty input")
    raw = text.strip()
    if not raw:
        raise ValueError("No JSON object can be recovered from empty input")

    m = _FENCE_RE.search(raw)
    if m:
        try:
            obj = json.loads(m.group(1).strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    if raw.endswith("```"):
        try:
            obj = json.loads(raw[: raw.rfind("```")].strip())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    m2 = _BARE_OBJECT_RE.search(raw)
    if m2:
        try:
            obj = json.loads(m2.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise ValueError("No JSON object can be recovered")


def load(name: str, /, **values: object) -> str:
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        available = sorted(p.stem for p in PROMPT_DIR.glob("*.md"))
        raise FileNotFoundError(f"No prompt {name!r}. Available: {available}")
    text = path.read_text(encoding="utf-8")
    try:
        return Template(text).substitute(**values)
    except ValueError as exc:
        bad = [
            (i, line) for i, line in enumerate(text.splitlines(), 1)
            if re.search(r"\$(?![A-Za-z_{])", line)
        ]
        raise ValueError(
            f"{path.name} contains a bare '$' that string.Template reads as a "
            f"placeholder. Escape it as '$$' or reword. Offending line(s): "
            f"{[f'{i}: {ln.strip()[:70]}' for i, ln in bad[:3]]}"
        ) from exc


def version(name: str) -> str:
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    for line in text.splitlines()[:12]:
        if line.strip().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


__all__ = ["EvidenceSpan", "PaperInsight", "extract_json", "load", "version",
           "PROMPT_DIR"]
