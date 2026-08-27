"""Section-aware chunking with exact character offsets into the original text."""

from __future__ import annotations

from researchgpt.core.models import Chunk

_SEPARATORS = ("\n\n", "\n", ". ", " ")


def chunk_paper(
    paper_id: str,
    text: str,
    sections: list[tuple[str, int, int]] | None = None,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[Chunk]:
    """Split ``text`` into Chunks whose offsets slice ``text`` exactly."""
    if not text:
        return []

    if sections:
        section_spans = sections
    else:
        section_spans = [("body", 0, len(text))]

    chunks: list[Chunk] = []
    ordinal = 0

    for section_name, sec_start, sec_end in section_spans:
        sec_start = max(0, sec_start)
        sec_end = min(len(text), sec_end)
        if sec_end <= sec_start:
            continue
        # Work on absolute offsets into `text` — never re-slice then forget.
        cursor = sec_start
        while cursor < sec_end:
            window_end = min(cursor + chunk_size, sec_end)
            if window_end < sec_end:
                split_at = _best_split(text, cursor, window_end)
            else:
                split_at = window_end

            if split_at <= cursor:
                split_at = window_end

            chunk_text = text[cursor:split_at]
            if len(chunk_text.strip()) >= 50:
                chunks.append(
                    Chunk(
                        chunk_id=f"{paper_id}:{ordinal:04d}",
                        paper_id=paper_id,
                        text=chunk_text,
                        section=section_name,
                        start_char=cursor,
                        end_char=split_at,
                    )
                )
                ordinal += 1

            if split_at >= sec_end:
                break
            next_start = split_at - chunk_overlap
            if next_start <= cursor:
                next_start = split_at
            cursor = next_start

    return chunks


def _best_split(text: str, start: int, hard_end: int) -> int:
    """Prefer natural breakpoints inside [start, hard_end]."""
    window = text[start:hard_end]
    for sep in _SEPARATORS:
        idx = window.rfind(sep)
        # Require a meaningful amount of content before the break.
        if idx >= max(50, (hard_end - start) // 4):
            return start + idx + len(sep)
    return hard_end


__all__ = ["chunk_paper"]
