"""T-324 — retrieval gold sets from SciReviewGen chapters, for T-212b.

Chapter topic becomes the query; the papers that chapter cites become the gold
set. Where T-212's gold set is one 35-paper bibliography, this is hundreds of
chapters — the breadth check against T-212's depth check.

🔴 **TASKLIST T-324 prescribes "fuzzy title matching", and that is not
possible: SciReviewGen carries no titles for the cited papers.** The
``reference`` column holds only ``(survey_title, chapter_heading, abstract,
BIBnnn)``. TASKLIST correctly flags the missing DOIs but assumes titles survive;
they do not. Verified 2026-08-27 against the parsed columns.

**Resolution: match on the abstract instead**, which is the only identifying
text present. The first ~18 words of a cited abstract go to OpenAlex's
``title_and_abstract.search``, and a candidate is accepted only if its
de-inverted abstract has Jaccard token overlap ≥ :data:`MATCH_THRESHOLD` with
the source. Probed on 8 papers before building this: **7 of 8 resolved**, most
at Jaccard 1.00.

The verification step is what makes this safe. A bare search would return
plausible-looking neighbours and quietly build a gold set of wrong papers,
which would then show up as a retrieval failure in T-212b rather than as the
matching failure it actually is.

⚠️ **Report the match rate as a limitation, not a footnote** (TASKLIST's own
instruction). Every unmatched paper is a gold-set entry that silently cannot be
retrieved, so T-212b's recall is bounded by this number and must be quoted
alongside it.

⚠️ **SciReviewGen is frozen at S2ORC 2020-07-05.** Live OpenAlex retrieval will
surface correct post-2020 papers that score as false positives in T-212b.
That is a measurement artefact of the frozen corpus, not a retrieval fault.

Run::

    python -m researchgpt.eval.scireviewgen_goldsets --chapters 60
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
from typing import Any

from researchgpt.eval.scireviewgen import load_split
from researchgpt.eval.scireviewgen_parser import parse_reference
from researchgpt.tools.search_sources import OpenAlexBudgetExhausted

DEFAULT_OUT = pathlib.Path("eval/gold_sets/scireviewgen_chapters.json")
DEFAULT_STATS = pathlib.Path("eval/scireviewgen_goldsets_t324.json")

#: Token-overlap floor for accepting an OpenAlex candidate as the cited paper.
#: 0.5 is deliberately loose: OpenAlex de-inversion and S2ORC's extraction
#: differ in boilerplate, so exact equality is rare even for a true match.
#: Measured on the probe set, true matches scored 0.52-1.00 and the single
#: miss scored 0.00 - the distribution is bimodal, so the threshold is not
#: delicately placed.
MATCH_THRESHOLD = 0.5

#: Words of the abstract used as the search query. OpenAlex ANDs the terms, so
#: longer is more precise but more brittle to extraction differences.
QUERY_WORDS = 18

#: Politeness delay between OpenAlex calls. The connector already sends a
#: mailto, which buys the faster pool; this keeps us inside it.
SLEEP_S = 0.34


def _tokens(text: str | None) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def abstract_query(abstract: str, words: int = QUERY_WORDS) -> str:
    return " ".join(re.findall(r"[A-Za-z0-9'-]+", abstract)[:words])


def resolve_abstract(abstract: str, *, max_results: int = 5) -> dict[str, Any] | None:
    """Find the OpenAlex work whose abstract matches ``abstract``.

    Returns ``None`` rather than a best guess when nothing clears
    :data:`MATCH_THRESHOLD` — an unverified match is worse than a miss here.
    """
    from researchgpt.tools.search_sources import search_openalex

    query = abstract_query(abstract)
    if not query:
        return None
    # Budget exhaustion propagates. It must NOT become `None`: a caller that
    # counts None as "no match" turns a dead quota into a fabricated match
    # rate, which is exactly what happened on the first T-324 run (18.6%,
    # every chapter from ~34 onward resolving zero). See main().
    results = search_openalex(query, year_min=None, max_results=max_results)

    source = _tokens(abstract)
    best, best_j = None, 0.0
    for paper in results:
        score = jaccard(source, _tokens(paper.abstract))
        if score > best_j:
            best_j, best = score, paper
    if best is None or best_j < MATCH_THRESHOLD:
        return None
    return {
        "doi": best.doi,
        "openalex_id": best.url,
        "title": best.title,
        "year": best.year,
        "venue": best.venue,
        "jaccard": round(best_j, 3),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-324 - SciReviewGen retrieval gold sets.")
    ap.add_argument("--split", default="validation", choices=["train", "validation", "test"])
    ap.add_argument("--chapters", type=int, default=60)
    ap.add_argument("--max-bibs", type=int, default=8,
                    help="cited papers resolved per chapter (caps the OpenAlex spend)")
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--stats", type=pathlib.Path, default=DEFAULT_STATS)
    args = ap.parse_args(argv)

    print("T-324 - SciReviewGen retrieval gold sets")
    print(f"  split {args.split}  chapters {args.chapters}  max_bibs {args.max_bibs}")
    print("  matching on ABSTRACT (no titles in the dataset - see module docstring)\n")

    rows = load_split(args.split, limit=args.chapters)
    chapters: list[dict[str, Any]] = []
    attempted = matched = 0
    jaccards: list[float] = []
    budget_exhausted = False

    for i, row in enumerate(rows, 1):
        parsed = parse_reference(row["reference"])
        gold: list[dict[str, Any]] = []
        unresolved: list[str] = []

        for bib in parsed["bibs"][: args.max_bibs]:
            attempted += 1
            try:
                hit = resolve_abstract(bib["abstract"])
            except OpenAlexBudgetExhausted as exc:
                # Stop immediately and report the partial run honestly. Carrying
                # on would append hundreds of false "unresolved" entries and
                # depress the match rate into meaninglessness.
                print(f"\n  !! {exc}")
                print(f"  !! STOPPING at chapter {i} after {attempted} requests. "
                      f"The match rate below covers only what was actually asked.")
                budget_exhausted = True
                break
            time.sleep(SLEEP_S)
            if hit is None:
                unresolved.append(bib["bib_id"])
                continue
            matched += 1
            jaccards.append(hit["jaccard"])
            gold.append({"bib_id": bib["bib_id"], **hit})

        chapters.append({
            "survey_title": parsed["survey_title"],
            "chapter": parsed["chapter"],
            # TASKLIST: "chapter topic -> query". Survey plus heading is the
            # topical context a Planner would be given for this chapter.
            "query": f"{parsed['survey_title']} {parsed['chapter']}".strip(),
            "gold": gold,
            "unresolved": unresolved,
            "cited_total": len(parsed["bibs"]),
        })
        if budget_exhausted:
            break
        rate = matched / attempted if attempted else 0.0
        print(f"  [{i:3d}/{len(rows)}] {len(gold):2d}/{len(parsed['bibs'][:args.max_bibs]):2d} "
              f"resolved   running match rate {rate:.1%}   "
              f"{parsed['survey_title'][:44]}")

    rate = matched / attempted if attempted else 0.0
    usable = [c for c in chapters if len(c["gold"]) >= 3]
    print("\n" + "=" * 70)
    print(f"  cited papers attempted        {attempted:6,d}")
    print(f"  resolved onto OpenAlex        {matched:6,d}")
    print(f"  MATCH RATE                    {rate:6.1%}   <- report this as a limitation")
    if jaccards:
        print(f"  median jaccard of matches     {sorted(jaccards)[len(jaccards) // 2]:6.2f}")
    print(f"  chapters with >=3 gold papers {len(usable):6,d} of {len(chapters)}")
    print("=" * 70)
    if budget_exhausted:
        print("!! PARTIAL RUN - the OpenAlex daily budget ran out. The match rate")
        print("!! above is NOT a finished measurement. Re-run after midnight UTC.")
    print("T-212b's recall is BOUNDED by this match rate: every unresolved paper")
    print("is a gold entry that cannot be retrieved. Quote them together.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "description": (
            "T-324 retrieval gold sets from SciReviewGen chapters. Breadth check "
            "for T-212b; the 35-paper own_bibliography.json stays the primary gate."
        ),
        "source": "kejian/SciReviewGen",
        "split": args.split,
        "matching": (
            f"abstract-prefix search onto OpenAlex, accepted at jaccard >= "
            f"{MATCH_THRESHOLD}. The dataset carries no titles and no DOIs."
        ),
        "match_rate": rate,
        "partial_run_budget_exhausted": budget_exhausted,
        "frozen_at": "S2ORC 2020-07-05 - post-2020 OpenAlex hits are correct but "
                     "score as false positives in T-212b. Measurement artefact.",
        "chapters": chapters,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")

    args.stats.parent.mkdir(parents=True, exist_ok=True)
    args.stats.write_text(json.dumps({
        "task": "T-324",
        "split": args.split,
        "chapters": len(chapters),
        "attempted": attempted,
        "matched": matched,
        "match_rate": rate,
        "partial_run_budget_exhausted": budget_exhausted,
        "median_jaccard": sorted(jaccards)[len(jaccards) // 2] if jaccards else None,
        "chapters_with_3plus_gold": len(usable),
        "match_threshold": MATCH_THRESHOLD,
        "note": (
            "TASKLIST prescribed fuzzy TITLE matching; SciReviewGen carries no "
            "titles for cited papers, only abstracts. Matched on abstract instead."
        ),
    }, indent=2), encoding="utf-8")
    print(f"wrote {args.stats}")


if __name__ == "__main__":
    main()
