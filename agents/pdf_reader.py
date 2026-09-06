from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/pdfs")

USER_AGENT = "ResearchGPT/0.1 (academic; mailto:sreekaran005@gmail.com)"

TIMEOUT = 30.0

MAX_BYTES = 40 * 1024 * 1024

MIN_TEXT_CHARS = 400

_SECTION_RE = re.compile(
    r"(?im)^(?:\d+(?:\.\d+)*\.?\s+)?"
    r"(abstract|introduction|related works?|background|"
    r"methods?|methodology|approach|experiments?|evaluation|"
    r"results?|discussion|conclusions?|limitations|references)\b.*$"
)


def _safe_name(paper_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(paper_id))[:120] or "paper"


def pdf_path(paper_id: str) -> Path:
    return CACHE_DIR / f"{_safe_name(paper_id)}.pdf"


def text_path(paper_id: str) -> Path:
    return CACHE_DIR / f"{_safe_name(paper_id)}.txt"


def looks_like_pdf_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    path = parsed.path.lower()
    return path.endswith(".pdf") or "/pdf/" in path or "content/pdf" in url.lower()


def arxiv_pdf_url(url: str) -> str | None:
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)", url or "")
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}"
    return None


def resolve_pdf_url(url: str | None) -> str | None:
    if not url:
        return None
    arxiv = arxiv_pdf_url(url)
    if arxiv:
        return arxiv
    if looks_like_pdf_url(url):
        return url
    return None


def fetch(url: str, paper_id: str, *, force: bool = False) -> Path | None:
    dest = pdf_path(paper_id)
    if dest.is_file() and dest.stat().st_size > 0 and not force:
        return dest

    target = resolve_pdf_url(url)
    if not target:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(
            follow_redirects=True, timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            with client.stream("GET", target) as resp:
                if resp.status_code != 200:
                    logger.info("pdf %s: HTTP %d", target, resp.status_code)
                    return None
                ctype = (resp.headers.get("content-type") or "").lower()
                if "pdf" not in ctype and "octet-stream" not in ctype:
                    logger.info("pdf %s: content-type %r, not a PDF", target, ctype)
                    return None

                size = 0
                chunks: list[bytes] = []
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        logger.info("pdf %s: over %d bytes, abandoned", target, MAX_BYTES)
                        return None
                    chunks.append(chunk)
        body = b"".join(chunks)
    except Exception as exc:
        logger.info("pdf %s: %s", target, type(exc).__name__)
        return None

    if not body.startswith(b"%PDF"):
        logger.info("pdf %s: no %%PDF header, probably an HTML paywall", target)
        return None

    dest.write_bytes(body)
    return dest


def parse(path: Path) -> str:
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            logger.error("pymupdf is not installed; cannot parse PDFs")
            return ""

    try:
        doc = pymupdf.open(str(path))
        pages = [page.get_text("text") for page in doc]
        doc.close()
    except Exception as exc:
        logger.info("parse failed for %s: %s", path, type(exc).__name__)
        return ""

    full = "\n".join(pages)

    for match in _SECTION_RE.finditer(full):
        if match.group(1).lower().startswith("reference"):
            full = full[: match.start()].rstrip()
            break

    full = re.sub(r"[ \t]+\n", "\n", full)
    full = re.sub(r"\n{3,}", "\n\n", full)
    return full.strip()


def cached_text(paper_id: str) -> str | None:
    path = text_path(paper_id)
    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return text if text.strip() else None
    return None


def ensure_text(paper, *, force: bool = False) -> tuple[str | None, str]:
    paper_id = str(getattr(paper, "paper_id", "") or "")
    if not paper_id:
        return None, "none"

    if not force:
        hit = cached_text(paper_id)
        if hit is not None:
            return hit, "full_text"

    url = getattr(paper, "url", None)
    path = fetch(url, paper_id, force=force)
    if path is None:
        return None, "abstract_only" if getattr(paper, "abstract", None) else "none"

    text = parse(path)
    if len(text) < MIN_TEXT_CHARS:
        logger.info("pdf %s: only %d chars of text, treating as failed",
                    paper_id, len(text))
        return None, "abstract_only" if getattr(paper, "abstract", None) else "none"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    text_path(paper_id).write_text(text, encoding="utf-8")
    return text, "full_text"


def fetch_many(papers, *, on_result=None) -> dict[str, str]:
    out: dict[str, str] = {}
    for paper in papers:
        text, availability = ensure_text(paper)
        if text:
            out[str(paper.paper_id)] = text
        if on_result is not None:
            on_result(paper, availability, len(text or ""))
    return out


__all__ = ["CACHE_DIR", "cached_text", "ensure_text", "fetch", "fetch_many",
           "parse", "pdf_path", "resolve_pdf_url", "text_path"]
