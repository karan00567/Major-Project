"""T-213 diagnostic — why the gold papers T-212 never retrieved were missed.

T-212 (2026-08-26, ranked) found 13 of 35 gold papers anywhere in a 498-paper
union. Ranking cannot fix that: 0.371 is a hard ceiling on Recall@60 no matter
how good the reranker is. So the question that decides where the T-213 buffer
goes is not "how do we rank better" but:

    Are the 22 missing papers UNREACHABLE from our sources, or merely UNASKED
    for by the 15 hand-written stand-in queries?

Those have opposite fixes. Unreachable means the source set or the date window
is wrong — expensive. Unasked-for means query generation is wrong, which is the
Planner's job (T-402) and costs nothing extra to fix.

This probes each missed DOI three ways against OpenAlex:

  exact_title  - the full title as a search string. Reachable at all?
  doi_lookup   - direct /works/doi/... . In the index at all, window aside?
  short_query  - the first 4 content words, i.e. the shape our stand-in queries
                 use. Reachable by a query a Planner might plausibly emit?

The gap between ``exact_title`` and ``short_query`` is the size of the prize
sitting in T-402.

Run:  python -m researchgpt.eval.diagnose_misses
"""

from __future__ import annotations

import json
import pathlib
import time
from typing import Any

import httpx

from researchgpt.core.config import load_config
from researchgpt.eval.retrieval_eval import norm, norm_title
from researchgpt.tools.search_sources import search_openalex

GOLD = pathlib.Path("eval/gold_sets/own_bibliography.json")
RESULT = pathlib.Path("eval/retrieval_eval_t212.json")
OUT = pathlib.Path("eval/diagnose_misses_t213.json")

_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from", "in",
    "is", "of", "on", "or", "the", "to", "via", "with", "towards", "toward",
}


def short_query(title: str, n: int = 4) -> str:
    """The query shape our stand-in queries use: a few content words."""
    words = [w.strip(":,.—-") for w in title.lower().split()]
    content = [w for w in words if w and w not in _STOP]
    return " ".join(content[:n])


def doi_in_openalex(doi: str) -> dict[str, Any] | None:
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url, params={"mailto": "sreekaran005@gmail.com"})
        if resp.status_code != 200:
            return None
        return resp.json()
    except httpx.HTTPError:
        return None


def main() -> None:
    cfg = load_config("configs/default.yaml")
    year_min = cfg.review.year_min

    gold_doc = json.loads(GOLD.read_text(encoding="utf-8"))
    by_doi = {norm(p["doi"]): p for p in gold_doc["papers"] if p.get("doi")}
    missed = json.loads(RESULT.read_text(encoding="utf-8"))["missed"]

    print(f"diagnosing {len(missed)} never-retrieved gold papers "
          f"(year_min={year_min})\n")

    rows: list[dict[str, Any]] = []
    tally = {"exact_title": 0, "doi_lookup": 0, "short_query": 0, "out_of_window": 0}

    for i, doi in enumerate(missed, 1):
        paper = by_doi.get(doi, {})
        title = paper.get("title") or ""
        want = norm_title(title)
        row: dict[str, Any] = {"doi": doi, "title": title, "year": paper.get("year")}

        record = doi_in_openalex(doi)
        row["doi_lookup"] = record is not None
        if record is not None:
            tally["doi_lookup"] += 1
            row["openalex_year"] = record.get("publication_year")
            if (record.get("publication_year") or 0) < year_min:
                row["out_of_window"] = True
                tally["out_of_window"] += 1

        try:
            hits = search_openalex(title[:180], year_min=year_min, max_results=10)
        except Exception:
            hits = []
        row["exact_title"] = any(
            norm(h.doi) == doi or norm_title(h.title) == want for h in hits
        )
        tally["exact_title"] += bool(row["exact_title"])

        sq = short_query(title)
        row["short_query_text"] = sq
        try:
            hits = search_openalex(sq, year_min=year_min, max_results=25)
        except Exception:
            hits = []
        row["short_query"] = any(
            norm(h.doi) == doi or norm_title(h.title) == want for h in hits
        )
        tally["short_query"] += bool(row["short_query"])

        flag = (
            "UNASKED " if row["exact_title"] and not row["short_query"]
            else "reachable" if row["short_query"]
            else "UNREACHABLE"
        )
        print(f"  [{i:2d}/{len(missed)}] {flag}  {title[:56]}")
        rows.append(row)
        time.sleep(0.4)  # be polite to OpenAlex

    n = len(missed) or 1
    print("\n" + "=" * 66)
    print(f"in OpenAlex at all (DOI lookup)   {tally['doi_lookup']:2d}/{n}")
    print(f"  of those, published < {year_min}      {tally['out_of_window']:2d}  "
          f"(excluded by our own date window)")
    print(f"findable by EXACT TITLE           {tally['exact_title']:2d}/{n}")
    print(f"findable by a SHORT QUERY         {tally['short_query']:2d}/{n}")
    print("=" * 66)
    # Reachable = findable by EITHER probe. A short query sometimes beats the
    # exact-title probe, because the title search is truncated to 180 chars and
    # OpenAlex ANDs every term in it — so the two are a union, not a hierarchy.
    reachable = sum(1 for r in rows if r["exact_title"] or r["short_query"])
    print(f"\nreachable by some query, but our 15 never asked: {reachable}/{n}.")
    print("These need better QUERIES (T-402), not a better index or model.")
    print(f"genuinely unreachable from OpenAlex search: {n - reachable}/{n}.")

    OUT.write_text(
        json.dumps({"year_min": year_min, "tally": tally, "papers": rows}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
