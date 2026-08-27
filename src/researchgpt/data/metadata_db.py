"""DOI-based paper deduplication and SQLite metadata store."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from researchgpt.core.models import Paper
from researchgpt.tools.search_sources import normalise_doi

_TITLE_KEY_RE = re.compile(r"[^a-z0-9]+")


def _title_key(title: str) -> str:
    t = title.lower().strip()
    t = _TITLE_KEY_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def _richness(p: Paper) -> tuple:
    """Higher tuple wins on collision."""
    return (
        1 if p.abstract else 0,
        p.citation_count if p.citation_count is not None else -1,
        1 if p.source == "openalex" else 0,
    )


def _merge(winner: Paper, loser: Paper) -> Paper:
    """Fill null fields on winner from loser; prefer winner's non-null values."""
    data = winner.model_dump()
    other = loser.model_dump()
    for key, val in other.items():
        if key == "paper_id":
            continue
        cur = data.get(key)
        if cur is None or cur == [] or cur == "":
            if val is not None and val != [] and val != "":
                data[key] = val
        elif key == "authors" and not cur and val:
            data[key] = val
        elif key == "url" and not cur and val:
            data[key] = val
        elif key == "venue" and not cur and val:
            data[key] = val
        elif key == "citation_count" and cur is None and val is not None:
            data[key] = val
        elif key == "abstract" and not cur and val:
            data[key] = val
    # Prefer openalex paper_id when winner is openalex; keep winner id otherwise.
    # If winner is arxiv and loser is openalex, keep openalex id for stability.
    if winner.source == "arxiv" and loser.source == "openalex":
        data["paper_id"] = loser.paper_id
        if loser.venue_tier and loser.venue_tier != "unknown":
            data["venue_tier"] = loser.venue_tier
        if loser.venue:
            data["venue"] = loser.venue
        if loser.citation_count is not None:
            data["citation_count"] = loser.citation_count
        # Keep arxiv pdf url if openalex has none
        if not data.get("url") and winner.url:
            data["url"] = winner.url
        elif winner.url and (
            "arxiv.org" in (winner.url or "")
            and "arxiv.org" not in (data.get("url") or "")
        ):
            data["url"] = winner.url
        data["source"] = "openalex"
        if winner.url and "arxiv.org" in winner.url:
            data["url"] = winner.url
    return Paper.model_validate(data)


def dedup_papers(papers: list[Paper]) -> list[Paper]:
    """Deduplicate by normalised DOI, else normalised title."""
    by_key: dict[str, Paper] = {}
    order: list[str] = []

    for paper in papers:
        doi = normalise_doi(paper.doi) if paper.doi else None
        if doi:
            key = f"doi:{doi}"
        else:
            key = f"title:{_title_key(paper.title)}"

        if key not in by_key:
            by_key[key] = paper
            order.append(key)
            continue

        existing = by_key[key]
        if _richness(paper) > _richness(existing):
            by_key[key] = _merge(paper, existing)
        else:
            by_key[key] = _merge(existing, paper)

    return [by_key[k] for k in order]


class MetadataDB:
    def __init__(self, path: str = "data/metadata.db") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS papers (
                paper_id TEXT PRIMARY KEY,
                doi TEXT,
                title TEXT NOT NULL,
                authors TEXT,
                year INTEGER,
                venue TEXT,
                venue_tier TEXT,
                abstract TEXT,
                url TEXT,
                pdf_path TEXT,
                source TEXT,
                citation_count INTEGER,
                is_preprint INTEGER,
                text_availability TEXT
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi)"
        )
        self._conn.commit()

    def upsert_papers(self, papers: list[Paper]) -> int:
        n = 0
        for p in papers:
            self._conn.execute(
                """
                INSERT INTO papers (
                    paper_id, doi, title, authors, year, venue, venue_tier,
                    abstract, url, pdf_path, source, citation_count,
                    is_preprint, text_availability
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    doi=excluded.doi,
                    title=excluded.title,
                    authors=excluded.authors,
                    year=excluded.year,
                    venue=excluded.venue,
                    venue_tier=excluded.venue_tier,
                    abstract=excluded.abstract,
                    url=excluded.url,
                    pdf_path=COALESCE(excluded.pdf_path, papers.pdf_path),
                    source=excluded.source,
                    citation_count=excluded.citation_count,
                    is_preprint=excluded.is_preprint,
                    text_availability=COALESCE(
                        excluded.text_availability, papers.text_availability
                    )
                """,
                (
                    p.paper_id,
                    p.doi,
                    p.title,
                    json.dumps(p.authors),
                    p.year,
                    p.venue,
                    p.venue_tier,
                    p.abstract,
                    p.url,
                    p.pdf_path,
                    p.source,
                    p.citation_count,
                    1 if p.is_preprint else 0,
                    p.text_availability,
                ),
            )
            n += 1
        self._conn.commit()
        return n

    def get(self, paper_id: str) -> Paper | None:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        return self._row_to_paper(row) if row else None

    def get_by_doi(self, doi: str) -> Paper | None:
        nd = normalise_doi(doi)
        if not nd:
            return None
        row = self._conn.execute(
            "SELECT * FROM papers WHERE doi = ?", (nd,)
        ).fetchone()
        return self._row_to_paper(row) if row else None

    def all(self) -> list[Paper]:
        rows = self._conn.execute("SELECT * FROM papers").fetchall()
        return [self._row_to_paper(r) for r in rows]

    def set_text_availability(self, paper_id: str, value: str) -> None:
        self._conn.execute(
            "UPDATE papers SET text_availability = ? WHERE paper_id = ?",
            (value, paper_id),
        )
        self._conn.commit()

    def set_pdf_path(self, paper_id: str, path: str) -> None:
        self._conn.execute(
            "UPDATE papers SET pdf_path = ? WHERE paper_id = ?",
            (path, paper_id),
        )
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM papers").fetchone()
        return int(row["c"])

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_paper(row: sqlite3.Row) -> Paper:
        authors = json.loads(row["authors"] or "[]")
        return Paper(
            paper_id=row["paper_id"],
            doi=row["doi"],
            title=row["title"],
            authors=authors,
            year=row["year"],
            venue=row["venue"],
            venue_tier=row["venue_tier"] or "unknown",
            abstract=row["abstract"],
            url=row["url"],
            pdf_path=row["pdf_path"],
            source=row["source"],
            citation_count=row["citation_count"],
            is_preprint=bool(row["is_preprint"]),
            text_availability=row["text_availability"] or "none",
        )


__all__ = ["dedup_papers", "MetadataDB"]
