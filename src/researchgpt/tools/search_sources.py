"""Federated literature search: OpenAlex + arXiv.

Verified API facts (handoffs/phase2.md, measured 2026-08-25) are followed
exactly — do not "simplify" the abstract de-inversion, DOI normalisation,
HTTPS arXiv endpoint, or synthetic 10.48550/arxiv.* join key.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any
import httpx

from researchgpt.core.models import Paper

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_VERSION_RE = re.compile(r"v\d+$", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def deinvert_abstract(index: dict[str, list[int]] | None) -> str | None:
    """Rebuild abstract text from OpenAlex ``abstract_inverted_index``."""
    if not index:
        return None
    pairs: list[tuple[int, str]] = []
    for word, positions in index.items():
        for pos in positions:
            pairs.append((pos, word))
    if not pairs:
        return None
    pairs.sort(key=lambda x: x[0])
    text = " ".join(w for _, w in pairs).strip()
    return text or None


def normalise_doi(doi: str | None) -> str | None:
    """Strip ``https://doi.org/`` and lower-case. Bare DOI or None."""
    if not doi:
        return None
    d = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.lower().startswith(prefix):
            d = d[len(prefix) :]
            break
    d = d.strip().lower()
    return d or None


def arxiv_id_to_doi(arxiv_id: str) -> str:
    """``2506.21931v2`` → ``10.48550/arxiv.2506.21931`` (version stripped)."""
    aid = arxiv_id.strip()
    if aid.lower().startswith("arxiv:"):
        aid = aid.split(":", 1)[1]
    aid = _VERSION_RE.sub("", aid)
    return f"10.48550/arxiv.{aid}"


def infer_venue_tier(work: dict) -> str:
    """First-match VenueTier from an OpenAlex work dict. Never raises."""
    try:
        if work.get("type") == "preprint":
            return "preprint"
        loc = work.get("primary_location") or {}
        source = loc.get("source") or {}
        host = (source.get("host_organization_name") or "") or ""
        landing = (loc.get("landing_page_url") or "") or ""
        venue_name = (source.get("display_name") or "") or ""
        combined = f"{host} {landing} {venue_name}".lower()
        if "arxiv" in combined:
            return "preprint"
        upper = venue_name.upper()
        if "IEEE" in upper:
            return "ieee"
        if any(tok in upper for tok in ("ACL", "EMNLP", "NAACL", "COLING")):
            return "acl"
        if source.get("is_in_doaj") or source.get("is_core") or source.get("issn_l") or source.get("issn"):
            return "peer_reviewed"
        return "unknown"
    except Exception:
        return "unknown"


def search_openalex(
    query: str,
    *,
    year_min: int | None = None,
    max_results: int = 25,
    mailto: str = "sreekaran005@gmail.com",
) -> list[Paper]:
    """Search OpenAlex with ``title_and_abstract.search`` + date window."""
    filters = [f"title_and_abstract.search:{query}"]
    if year_min is not None:
        filters.append(f"from_publication_date:{year_min}-01-01")
        filters.append("to_publication_date:2026-12-31")
    filter_str = ",".join(filters)

    papers: list[Paper] = []
    cursor = "*"
    per_page = min(200, max_results)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        while len(papers) < max_results:
            params = {
                "filter": filter_str,
                "per-page": per_page,
                "cursor": cursor,
                "mailto": mailto,
            }
            resp = client.get("https://api.openalex.org/works", params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            if not results:
                break
            for work in results:
                paper = _openalex_work_to_paper(work)
                if paper is not None:
                    papers.append(paper)
                    if len(papers) >= max_results:
                        break
            meta = data.get("meta") or {}
            next_cursor = meta.get("next_cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

    return papers[:max_results]


def _openalex_work_to_paper(work: dict[str, Any]) -> Paper | None:
    title = work.get("title") or work.get("display_name")
    if not title:
        return None
    work_id = work.get("id") or ""
    paper_id = work_id.rsplit("/", 1)[-1] if work_id else ""
    if not paper_id:
        return None

    authors: list[str] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(name)

    venue: str | None = None
    loc = work.get("primary_location")
    if isinstance(loc, dict):
        source = loc.get("source")
        if isinstance(source, dict):
            venue = source.get("display_name") or None

    oa = work.get("open_access") or {}
    oa_url = oa.get("oa_url") if isinstance(oa, dict) else None

    return Paper(
        paper_id=paper_id,
        doi=normalise_doi(work.get("doi")),
        title=title,
        authors=authors,
        year=work.get("publication_year"),
        venue=venue,
        venue_tier=infer_venue_tier(work),  # type: ignore[arg-type]
        abstract=deinvert_abstract(work.get("abstract_inverted_index")),
        url=oa_url,
        source="openalex",
        citation_count=work.get("cited_by_count"),
        is_preprint=work.get("type") == "preprint",
    )


def search_arxiv(query: str, *, max_results: int = 25) -> list[Paper]:
    """Search arXiv Atom API over HTTPS (HTTP returns empty 301 body)."""
    papers: list[Paper] = []
    start = 0
    page_size = min(50, max_results)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        while len(papers) < max_results:
            n = min(page_size, max_results - len(papers))
            params = {
                "search_query": f'all:"{query}"',
                "start": start,
                "max_results": n,
            }
            # Mandatory HTTPS — http:// returns 301 with empty body.
            resp = client.get("https://export.arxiv.org/api/query", params=params)
            resp.raise_for_status()
            batch = _parse_arxiv_feed(resp.text)
            if not batch:
                break
            papers.extend(batch)
            start += len(batch)
            if len(batch) < n:
                break
            # arXiv asks for <= 1 request / 3 seconds.
            time.sleep(3.0)

    return papers[:max_results]


def _parse_arxiv_feed(xml_text: str) -> list[Paper]:
    root = ET.fromstring(xml_text)
    out: list[Paper] = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        paper = _arxiv_entry_to_paper(entry)
        if paper is not None:
            out.append(paper)
    return out


def _arxiv_entry_to_paper(entry: ET.Element) -> Paper | None:
    id_el = entry.find("atom:id", _ATOM_NS)
    if id_el is None or not id_el.text:
        return None
    # https://arxiv.org/abs/2506.21931v2
    raw_id = id_el.text.rsplit("/", 1)[-1]
    paper_id = raw_id

    title_el = entry.find("atom:title", _ATOM_NS)
    if title_el is None or not title_el.text:
        return None
    title = " ".join(title_el.text.split())

    authors = []
    for author in entry.findall("atom:author", _ATOM_NS):
        name_el = author.find("atom:name", _ATOM_NS)
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    published_el = entry.find("atom:published", _ATOM_NS)
    year: int | None = None
    if published_el is not None and published_el.text:
        try:
            year = int(published_el.text[:4])
        except ValueError:
            year = None

    summary_el = entry.find("atom:summary", _ATOM_NS)
    abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else None

    pdf_url: str | None = None
    for link in entry.findall("atom:link", _ATOM_NS):
        if link.attrib.get("title") == "pdf":
            pdf_url = link.attrib.get("href")
            break
    if pdf_url is None:
        # Fallback: any application/pdf link
        for link in entry.findall("atom:link", _ATOM_NS):
            if link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href")
                break

    return Paper(
        paper_id=paper_id,
        doi=arxiv_id_to_doi(paper_id),
        title=title,
        authors=authors,
        year=year,
        venue="arXiv",
        venue_tier="preprint",
        abstract=abstract,
        url=pdf_url,
        source="arxiv",
        is_preprint=True,
    )


__all__ = [
    "deinvert_abstract",
    "normalise_doi",
    "arxiv_id_to_doi",
    "infer_venue_tier",
    "search_openalex",
    "search_arxiv",
]
