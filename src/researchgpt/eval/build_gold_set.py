"""Build the retrieval gold set from the project's own literature review.

TASKLIST T-212a. ``PROJECT_PLAN.md §5.2`` designates the hand-curated 25-paper
bibliography as the primary retrieval gold set — "domain-matched, free, and
defensible in a viva because you can justify every gold label yourself". But
that bibliography lives as prose and markdown tables across three documents,
which no evaluator can consume.

This module extracts every DOI from those documents, resolves each against
OpenAlex for canonical metadata, and writes a machine-readable gold set.

Run:  python -m researchgpt.eval.build_gold_set

Output: ``eval/gold_sets/own_bibliography.json``

Unresolved DOIs are written to the ``unresolved`` list rather than dropped.
SPEC §14.2 forbids silent fabrication, and a gold set that quietly loses
entries produces a recall number that is wrong in the flattering direction.
"""

from __future__ import annotations

import json
import pathlib
import re
import time
from typing import Any

import httpx

SOURCE_DOCS = (
    "LITERATURE_REVIEW.md",
    "PAPER_ANALYSIS.md",
    "PAPER_DEEP_DIVE.md",
)

OUT_PATH = pathlib.Path("eval/gold_sets/own_bibliography.json")

# DOIs appear inside markdown links, parentheses and table cells; trailing
# punctuation must not become part of the identifier.
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s)\]|,;\"'>]+", re.IGNORECASE)

_MAILTO = "sreekaran005@gmail.com"
_UA = {"User-Agent": f"ResearchGPT/0.1 (mailto:{_MAILTO})"}


def normalise_doi(doi: str) -> str:
    """Canonical form: lowercase, no resolver prefix, no trailing punctuation."""
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix) :]
    return d.rstrip(".,;)")


def extract_dois(root: pathlib.Path) -> dict[str, list[str]]:
    """Map normalised DOI -> the documents it was found in."""
    found: dict[str, list[str]] = {}
    for name in SOURCE_DOCS:
        path = root / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for raw in _DOI_RE.findall(text):
            doi = normalise_doi(raw)
            found.setdefault(doi, [])
            if name not in found[doi]:
                found[doi].append(name)
    return found


def resolve(doi: str, client: httpx.Client) -> dict[str, Any] | None:
    """Fetch canonical metadata from OpenAlex. Returns None if unresolvable."""
    try:
        r = client.get(
            f"https://api.openalex.org/works/doi:{doi}",
            params={"mailto": _MAILTO},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        w = r.json()
    except (httpx.HTTPError, ValueError):
        return None

    primary = w.get("primary_location") or {}
    source = primary.get("source") or {}
    oa = w.get("open_access") or {}
    return {
        "doi": doi,
        "openalex_id": w.get("id"),
        "title": w.get("title") or w.get("display_name"),
        "year": w.get("publication_year"),
        "venue": source.get("display_name"),
        "type": w.get("type"),
        "is_preprint": w.get("type") == "preprint",
        "cited_by_count": w.get("cited_by_count"),
        "is_oa": bool(oa.get("is_oa")),
        "oa_url": oa.get("oa_url"),
        "authors": [
            (a.get("author") or {}).get("display_name")
            for a in (w.get("authorships") or [])[:8]
        ],
    }


def main() -> None:
    root = pathlib.Path(".")
    found = extract_dois(root)
    print(f"extracted {len(found)} unique DOIs from {len(SOURCE_DOCS)} documents")

    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    with httpx.Client(headers=_UA, follow_redirects=True) as client:
        for i, (doi, docs) in enumerate(sorted(found.items()), 1):
            meta = resolve(doi, client)
            if meta is None:
                unresolved.append({"doi": doi, "found_in": docs})
                print(f"  [{i:2d}/{len(found)}] UNRESOLVED {doi}")
            else:
                meta["found_in"] = docs
                resolved.append(meta)
                print(f"  [{i:2d}/{len(found)}] {meta['year']} {str(meta['title'])[:62]}")
            time.sleep(0.12)  # be polite to a keyless public API

    payload = {
        "description": (
            "Retrieval gold set built from the project's own hand-curated "
            "literature review (PROJECT_PLAN.md §5.2). Primary gate for "
            "TASKLIST T-212: Recall@20 >= 0.80."
        ),
        "source_documents": list(SOURCE_DOCS),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "papers": resolved,
        "unresolved": unresolved,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT_PATH}  ({len(resolved)} resolved, {len(unresolved)} unresolved)")


if __name__ == "__main__":
    main()
