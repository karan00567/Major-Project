"""OA PDF fetch + PyMuPDF parse with heuristic section detection."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from researchgpt.core.models import Paper

logger = logging.getLogger(__name__)

_USER_AGENT = "ResearchGPT/0.1 (academic; mailto:sreekaran005@gmail.com)"
_SECTION_RE = re.compile(
    r"(?im)^(?:\d+(?:\.\d+)*\.?\s+)?"
    r"(abstract|introduction|related works?|background|"
    r"methods?|methodology|approach|experiments?|evaluation|"
    r"results?|discussion|conclusions?|limitations|references)\b.*$"
)
_KNOWN_OA_HOSTS = ("arxiv.org", "export.arxiv.org", "arxiv-export")


def fetch_pdf(paper: Paper, dest_dir: str = "data/pdfs") -> str | None:
    """Download an OA PDF if the URL looks fetchable. Never raises."""
    url = paper.url
    if not url:
        return None
    if not _looks_like_pdf_url(url):
        return None

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    # Sanitise paper_id for filesystem
    safe_id = re.sub(r"[^\w.\-]+", "_", paper.paper_id)
    out_path = dest / f"{safe_id}.pdf"

    try:
        with httpx.Client(
            timeout=60.0,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None
            ctype = (resp.headers.get("content-type") or "").lower()
            if "pdf" not in ctype and not url.lower().endswith(".pdf"):
                # Some arXiv mirrors omit content-type; accept if body starts with %PDF
                if not resp.content.startswith(b"%PDF"):
                    return None
            out_path.write_bytes(resp.content)
            return str(out_path)
    except Exception as exc:
        logger.info("fetch_pdf failed for %s: %s", paper.paper_id, exc)
        return None


def parse_pdf(path: str) -> tuple[str, list[tuple[str, int, int]]]:
    """Return (full_text, sections). Never raises — empty on failure."""
    try:
        import fitz  # pymupdf
    except ImportError:
        logger.error("pymupdf not installed")
        return "", []

    try:
        doc = fitz.open(path)
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
        full = "\n".join(pages)
    except Exception as exc:
        logger.info("parse_pdf failed for %s: %s", path, exc)
        return "", []

    sections = _detect_sections(full)
    # Truncate from references onward
    for name, start, _end in sections:
        if name.lower() == "references":
            full = full[:start].rstrip()
            sections = [(n, s, min(e, len(full))) for n, s, e in sections if s < len(full)]
            # Fix last section end
            if sections:
                n, s, _ = sections[-1]
                sections[-1] = (n, s, len(full))
            break
    return full, sections


def load_paper_text(
    paper: Paper, dest_dir: str = "data/pdfs"
) -> tuple[str, str]:
    """Return ``(text, text_availability)`` — full | abstract_only | none."""
    path = fetch_pdf(paper, dest_dir=dest_dir)
    if path:
        text, _sections = parse_pdf(path)
        if text.strip():
            return text, "full"
    if paper.abstract and paper.abstract.strip():
        return paper.abstract, "abstract_only"
    return "", "none"


def _looks_like_pdf_url(url: str) -> bool:
    lower = url.lower()
    if lower.endswith(".pdf"):
        return True
    host = urlparse(url).netloc.lower()
    if any(h in host for h in _KNOWN_OA_HOSTS):
        return True
    if "/pdf/" in lower:
        return True
    return False


def _detect_sections(text: str) -> list[tuple[str, int, int]]:
    matches: list[tuple[str, int]] = []
    for m in _SECTION_RE.finditer(text):
        name = m.group(1).lower()
        # Normalise plurals / aliases
        if name.startswith("method"):
            name = "methods"
        elif name.startswith("result"):
            name = "results"
        elif name.startswith("experiment"):
            name = "experiments"
        elif name.startswith("related"):
            name = "related work"
        elif name.startswith("conclusion"):
            name = "conclusion"
        matches.append((name, m.start()))

    if not matches:
        return [("body", 0, len(text))] if text else []

    sections: list[tuple[str, int, int]] = []
    for i, (name, start) in enumerate(matches):
        end = matches[i + 1][1] if i + 1 < len(matches) else len(text)
        if end > start:
            sections.append((name, start, end))
    return sections


__all__ = ["fetch_pdf", "parse_pdf", "load_paper_text"]
