"""Versioned prompt files, one per agent (`SPEC §14.4`).

Prompts live as ``.md`` beside this module rather than as Python string
literals so that a prompt change is a reviewable diff with a version header,
and so the exact text that produced a run can be archived with it.

:func:`load` reads and formats one. It uses ``string.Template`` rather than
``str.format`` deliberately: prompts are full of JSON braces, and ``format``
would treat every ``{"sq_id": ...}`` in an output schema as a field reference
and raise. Placeholders are therefore ``$name``.
"""

from __future__ import annotations

import pathlib
from string import Template

PROMPT_DIR = pathlib.Path(__file__).parent


def load(name: str, /, **values: object) -> str:
    """Load ``<name>.md`` and substitute ``$placeholders``.

    Raises on an unfilled placeholder rather than shipping a prompt with a
    literal ``$research_question`` in it — an LLM will answer such a prompt
    plausibly, which is the worst possible failure mode.
    """
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        available = sorted(p.stem for p in PROMPT_DIR.glob("*.md"))
        raise FileNotFoundError(f"No prompt {name!r}. Available: {available}")
    text = path.read_text(encoding="utf-8")
    try:
        return Template(text).substitute(**values)
    except ValueError as exc:
        # Template's own message is just "Invalid placeholder in string: line
        # N, col M", which does not say WHAT is wrong. The cause is always the
        # same: a bare "$" in prose that Template reads as a placeholder. This
        # has cost three debugging rounds, so the error now names the offender.
        import re as _re

        bad = [
            (i, line) for i, line in enumerate(text.splitlines(), 1)
            if _re.search(r"\$(?![A-Za-z_{])", line)
        ]
        raise ValueError(
            f"{path.name} contains a bare '$' that string.Template reads as a "
            f"placeholder. Escape it as '$$' or reword. Offending line(s): "
            f"{[f'{i}: {ln.strip()[:70]}' for i, ln in bad[:3]]}"
        ) from exc


def version(name: str) -> str:
    """The ``version:`` field from the prompt's header comment, for the trace."""
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    for line in text.splitlines()[:12]:
        if line.strip().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


__all__ = ["load", "version", "PROMPT_DIR"]
