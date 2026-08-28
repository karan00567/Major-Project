"""Federated literature search: OpenAlex + arXiv + Semantic Scholar.

Verified API facts (handoffs/phase2.md, measured 2026-08-25) are followed
exactly — do not "simplify" the abstract de-inversion, DOI normalisation,
HTTPS arXiv endpoint, or synthetic 10.48550/arxiv.* join key.
"""

from __future__ import annotations

import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from researchgpt.core.models import Paper

#: Both connectors read credentials from the environment - OPENALEX_API_KEY
#: (10x daily budget) and S2_API_KEY. A module imported from a script or a
#: notebook will not have had .env loaded, so a single guarded load_dotenv() at
#: import is the whole fix. Never raises: python-dotenv is a hard dependency,
#: but a missing .env is normal and must not break an import.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - defensive only
    pass

log = logging.getLogger(__name__)


class OpenAlexBudgetExhausted(RuntimeError):
    """OpenAlex returned 429 because the daily free budget is spent.

    Distinct from "the query matched nothing", and deliberately not swallowed:
    conflating the two silently converts a quota failure into a fabricated
    measurement. See the 2026-08-27 note in :func:`search_openalex`.
    """

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
    api_key: str | None = None,
) -> list[Paper]:
    """Search OpenAlex with ``title_and_abstract.search`` + date window.

    ``api_key`` defaults to ``OPENALEX_API_KEY`` from the environment. It is a
    **free registered key**, not a paid plan - verified 2026-08-27 that it
    reports ``prepaid-remaining-usd: 0``, so nothing is billable and TASKLIST
    §0.1 is satisfied. It raises the daily budget 10x:

        keyless   $0.10/day  ~  100 searches
        with key  $1.00/day  ~ 1000 searches

    Without it, evaluation work exhausts the day's quota in minutes.
    """
    key = api_key if api_key is not None else os.getenv("OPENALEX_API_KEY")
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
                # Courtesy only: measured 2026-08-27 that `mailto` no longer
                # buys any quota. The polite pool is gone.
                "mailto": mailto,
            }
            if key:
                params["api_key"] = key
            resp = client.get("https://api.openalex.org/works", params=params)
            if resp.status_code == 429:
                # ⚠️ OpenAlex moved to a METERED DAILY BUDGET (measured
                # 2026-08-27): x-ratelimit-limit-usd = $0.10/day, and a search
                # costs $0.001 -- roughly 100 searches per day. `mailto` no
                # longer buys extra budget; the polite pool is gone.
                #
                # This is raised as a NAMED exception rather than returned as
                # an empty list on purpose. A silent [] is indistinguishable
                # from "nothing matched", and that is exactly how an exhausted
                # budget once masqueraded as a real T-324 match rate of 18.6%.
                # Callers must be able to tell "no results" from "no quota".
                hint = (
                    "Set OPENALEX_API_KEY in .env - the free registered key "
                    "raises the daily budget 10x ($0.10 -> $1.00)."
                    if not key
                    else "TASKLIST 0.1 forbids buying more; wait for the reset."
                )
                raise OpenAlexBudgetExhausted(
                    f"OpenAlex daily budget exhausted "
                    f"({'with' if key else 'WITHOUT'} an api_key). "
                    f"remaining=${resp.headers.get('x-ratelimit-remaining-usd', '?')} "
                    f"of ${resp.headers.get('x-ratelimit-limit-usd', '?')}/day; "
                    f"resets in {resp.headers.get('x-ratelimit-reset', '?')}s. {hint}"
                )
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
            #
            # 🔴 arXiv was the ONLY source without backoff, and it showed:
            # OpenAlex handles 429 explicitly and Semantic Scholar retries with
            # delay, but this was a bare raise_for_status(). arXiv asks for
            # <= 1 request / 3 s and throttles bursts, so three acceptance
            # tests calling search_arxiv back to back turned a throttle into a
            # test failure (2026-08-28: test_t203_dedup and test_t204_pdf both
            # died on httpx.HTTPStatusError while OpenAlex sat at 83% of its
            # daily budget — the wrong host got the blame).
            resp = _arxiv_get_with_backoff(client, params)
            if resp is None:
                break          # throttled past patience: return what we have
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


#: arXiv's stated politeness rule is <= 1 request / 3 s. Bursts get 403/429.
_ARXIV_MAX_ATTEMPTS = 4
_ARXIV_BACKOFF_S = (3.0, 6.0, 12.0)


def _arxiv_get_with_backoff(client: Any, params: dict) -> Any:
    """One arXiv page, retried on throttling. ``None`` means give up quietly.

    Quietly, not loudly: arXiv is a *secondary* source. OpenAlex is the
    mandatory one (TASKLIST §0.2), so losing an arXiv page costs some preprint
    coverage, not the run. Raising here would abort a 25-minute pipeline over a
    politeness limit.
    """
    for attempt in range(_ARXIV_MAX_ATTEMPTS):
        try:
            resp = client.get("https://export.arxiv.org/api/query", params=params)
        except httpx.HTTPError:
            if attempt == _ARXIV_MAX_ATTEMPTS - 1:
                return None
            time.sleep(_ARXIV_BACKOFF_S[min(attempt, len(_ARXIV_BACKOFF_S) - 1)])
            continue
        if resp.status_code in (403, 429, 503):
            if attempt == _ARXIV_MAX_ATTEMPTS - 1:
                log.warning(
                    "arxiv: throttled (HTTP %s) after %d attempts; returning what "
                    "we have. arXiv is a secondary source - OpenAlex is the "
                    "mandatory one - so this degrades coverage, not the run.",
                    resp.status_code, _ARXIV_MAX_ATTEMPTS,
                )
                return None
            time.sleep(_ARXIV_BACKOFF_S[min(attempt, len(_ARXIV_BACKOFF_S) - 1)])
            continue
        resp.raise_for_status()
        return resp
    return None


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


# ---------------------------------------------------------------------------
# Semantic Scholar (T-214)
#
# SUPPLEMENTARY source. The pipeline must run fine without it, so every failure
# path here degrades to [] rather than raising - a run that dies because a
# best-effort source was throttled is a defect, not a symptom.
#
# Measured keyless 2026-08-25: 1 of 4 rapid requests succeeded; with backoff,
# 2 of 3 queries succeeded and 1 failed after 6 attempts. Unreliable-without-a-
# key is the EXPECTED case (see T-215 for the key application).
#
# Worth having anyway, despite the flakiness: abstracts arrive as plain text
# (no de-inversion, unlike OpenAlex) and ``externalIds`` carries DOI + ArXiv +
# DBLP + PubMed at once, which is the only thing in the pipeline that can
# bridge an arXiv preprint to its published DOI for T-203 dedup.
# ---------------------------------------------------------------------------

_S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

_S2_FIELDS = ",".join(
    (
        "paperId",
        "externalIds",
        "title",
        "abstract",
        "year",
        "venue",
        "authors",
        "citationCount",
        "isOpenAccess",
        "openAccessPdf",
        "publicationTypes",
    )
)

#: Delays between the (up to) ``_S2_MAX_ATTEMPTS`` tries. Module-level so the
#: acceptance suite can zero it out instead of sleeping through a 60s storm.
_BACKOFF_SCHEDULE: tuple[float, ...] = (2.0, 4.0, 8.0, 16.0, 30.0)
_S2_MAX_ATTEMPTS = 6
#: S2 asks for politeness even when requests succeed.
_POLITE_SLEEP_S: float = 1.0

#: S2 caps ``limit`` at 100 per page.
_S2_MAX_LIMIT = 100


def search_semantic_scholar(
    query: str,
    *,
    year_min: int | None = None,
    max_results: int = 25,
    api_key: str | None = None,
    _transport: Any = None,
) -> list[Paper]:
    """Search Semantic Scholar. Best-effort: never raises, may return ``[]``.

    ``api_key`` falls back to ``S2_API_KEY`` in the environment; absent is the
    normal case and only costs reliability, not correctness.

    ``_transport`` is a private test seam (an ``httpx`` transport) so the
    acceptance suite can exercise the 429 path without a live storm. It is not
    part of the T-214 contract - do not depend on it from pipeline code.
    """
    key = api_key or os.getenv("S2_API_KEY") or None
    headers = {"x-api-key": key} if key else {}

    papers: list[Paper] = []
    offset = 0

    with httpx.Client(
        timeout=60.0, follow_redirects=True, headers=headers, transport=_transport
    ) as client:
        while len(papers) < max_results:
            limit = min(_S2_MAX_LIMIT, max_results - len(papers))
            params = {
                "query": query,
                "limit": limit,
                "offset": offset,
                "fields": _S2_FIELDS,
            }
            if year_min is not None:
                params["year"] = f"{year_min}-"

            data = _s2_get(client, params)
            if data is None:
                # Throttled or errored out. Whatever was already collected is
                # still valid and still better than nothing; the first-page
                # case - the one T-214 specifies - returns [] exactly as asked.
                break

            results = data.get("data") or []
            if not results:
                break
            for result in results:
                paper = _s2_result_to_paper(result)
                if paper is not None:
                    papers.append(paper)
                    if len(papers) >= max_results:
                        break
            if len(results) < limit:
                break
            offset += len(results)
            if _POLITE_SLEEP_S:
                time.sleep(_POLITE_SLEEP_S)

    return papers[:max_results]


def _s2_get(client: httpx.Client, params: dict[str, Any]) -> dict[str, Any] | None:
    """One page, with 429 backoff. ``None`` means "give up quietly"."""
    for attempt in range(_S2_MAX_ATTEMPTS):
        try:
            resp = client.get(_S2_SEARCH_URL, params=params)
        except httpx.HTTPError as exc:
            log.warning("semantic_scholar: transport error (%s); degrading", type(exc).__name__)
            return None

        if resp.status_code == 429:
            if attempt + 1 >= _S2_MAX_ATTEMPTS:
                log.warning(
                    "semantic_scholar: throttled (429) after %d attempts; "
                    "returning no results for this query. This is expected "
                    "without an S2_API_KEY (T-215) and is not a run failure.",
                    _S2_MAX_ATTEMPTS,
                )
                return None
            delay = _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]
            if delay:
                time.sleep(delay)
            continue

        if resp.status_code >= 400:
            log.warning(
                "semantic_scholar: HTTP %d; degrading to no results", resp.status_code
            )
            return None

        try:
            return resp.json()
        except ValueError:
            log.warning("semantic_scholar: unparseable JSON body; degrading")
            return None

    return None


def _s2_result_to_paper(result: dict[str, Any]) -> Paper | None:
    paper_id = result.get("paperId")
    title = result.get("title")
    if not paper_id or not title:
        return None

    external = result.get("externalIds") or {}

    authors: list[str] = []
    for author in result.get("authors") or []:
        name = (author or {}).get("name")
        if name:
            authors.append(name)

    oa_pdf = result.get("openAccessPdf") or {}
    pub_types = result.get("publicationTypes") or []

    return Paper(
        paper_id=paper_id,
        doi=normalise_doi(external.get("DOI")),
        title=" ".join(str(title).split()),
        authors=authors,
        year=result.get("year"),
        venue=result.get("venue") or None,
        venue_tier=_s2_venue_tier(result),  # type: ignore[arg-type]
        abstract=result.get("abstract") or None,
        url=oa_pdf.get("url") or None,
        source="semantic_scholar",
        citation_count=result.get("citationCount"),
        is_preprint="JournalArticle" not in pub_types,
    )


def _s2_venue_tier(result: dict[str, Any]) -> str:
    """Venue tier from an S2 record. Deliberately conservative - SPEC 14.2
    forbids inventing a tier the source does not evidence."""
    pub_types = result.get("publicationTypes") or []
    venue = (result.get("venue") or "").strip()
    if not venue:
        return "preprint" if "JournalArticle" not in pub_types else "unknown"
    upper = venue.upper()
    if "ARXIV" in upper:
        return "preprint"
    if "IEEE" in upper:
        return "ieee"
    if any(tok in upper for tok in ("ACL", "EMNLP", "NAACL", "COLING")):
        return "acl"
    if "JournalArticle" in pub_types or "Conference" in pub_types:
        return "peer_reviewed"
    return "unknown"


__all__ = [
    "deinvert_abstract",
    "normalise_doi",
    "arxiv_id_to_doi",
    "infer_venue_tier",
    "search_openalex",
    "search_arxiv",
    "search_semantic_scholar",
]
