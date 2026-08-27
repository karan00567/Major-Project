"""T-321 ⛔ — parse SciReviewGen's ``reference`` column, and prove the parse is right.

``reference`` packs a repeated 4-field record into one string::

    survey_title <s> chapter_heading <s> cited_abstract <s> BIBnnn </s>

``target`` is the human-written chapter with inline ``BIBnnn`` markers pointing
into those blocks. **Everything downstream — T-322 pairs, T-324 gold sets, and
T-325, the cross-check this whole track exists for — rests on that alignment
holding.** TASKLIST flags it as the one unproven assumption in Phase 3B, because
it could only be checked against the datasets-server preview, which truncates
long cells.

**Measured here on full rows, which is the point of the task.**

The gate is the **bib-resolution rate**: of all ``BIBnnn`` markers appearing in
``target``, what fraction resolve to a block in ``reference``? TASKLIST sets
**≥ 0.95**. Below that the delimiter parse is wrong and must be fixed — *not*
worked around by silently dropping unresolved markers, which would quietly
shrink and bias the evidence base.

⚠️ **Not every citation in ``target`` is a ``BIBnnn`` marker.** Chapters also
carry plain prose citations (``(Jordan and Mitchell 2015)``) that SciReviewGen
could not link to a paper. Those are *out of scope by construction* — the gate
measures only the markers that claim to resolve, not citation coverage. Reading
it as coverage would understate the parse quality badly.

Run::

    python -m researchgpt.eval.scireviewgen_parser              # gate on validation
    python -m researchgpt.eval.scireviewgen_parser --split test --n 1000
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any

from researchgpt.eval.scireviewgen import load_split

#: The delimiters. Blocks are separated by ``</s>``; fields within a block by ``<s>``.
_BLOCK_SEP = "</s>"
_FIELD_SEP = "<s>"

#: Citation markers, in both `reference` blocks and `target` prose.
BIB_RE = re.compile(r"BIB\d+")

#: TASKLIST T-321. Below this the parse is wrong; fix it, do not drop markers.
RESOLUTION_GATE = 0.95

DEFAULT_OUT = pathlib.Path("eval/scireviewgen_parse_t321.json")


def parse_reference(reference: str) -> dict[str, Any]:
    """Split one ``reference`` cell into ``{survey_title, chapter, bibs}``.

    ``bibs`` is ``[{bib_id, abstract}]`` in document order.

    Every block carries its own copy of the survey title and chapter heading;
    they are taken from the first block and the rest are checked for agreement
    rather than assumed (:func:`parse_stats` reports disagreements).

    Field-count robustness: a block is read as
    ``parts[0] = title, parts[1] = chapter, parts[-1] = bib_id`` with everything
    between joined back as the abstract. Measured over 6,284 validation blocks
    every block is exactly 4 fields, but an abstract containing a literal
    ``<s>`` would otherwise silently shift every field left.
    """
    blocks: list[dict[str, str]] = []
    titles: set[str] = set()
    chapters: set[str] = set()
    malformed = 0

    for raw in reference.split(_BLOCK_SEP):
        if not raw.strip():
            continue
        parts = [p.strip() for p in raw.split(_FIELD_SEP)]
        if len(parts) < 4 or not BIB_RE.fullmatch(parts[-1]):
            malformed += 1
            continue
        titles.add(parts[0])
        chapters.add(parts[1])
        blocks.append(
            {"bib_id": parts[-1], "abstract": f" {_FIELD_SEP} ".join(parts[2:-1]).strip()}
        )

    return {
        "survey_title": next(iter(titles), ""),
        "chapter": next(iter(chapters), ""),
        "bibs": blocks,
        "n_titles": len(titles),
        "n_chapters": len(chapters),
        "malformed_blocks": malformed,
    }


def target_bib_ids(target: str) -> list[str]:
    """Every ``BIBnnn`` marker in the chapter text, in order, with duplicates."""
    return BIB_RE.findall(target)


def parse_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the parse over ``rows`` and compute the T-321 resolution rate."""
    markers_total = 0
    markers_resolved = 0
    rows_fully_resolved = 0
    rows_with_markers = 0
    malformed_blocks = 0
    inconsistent_header = 0
    empty_abstracts = 0
    unresolved_examples: list[dict[str, Any]] = []
    bibs_per_row: list[int] = []
    markers_per_row: list[int] = []
    orphan_blocks = 0

    for row in rows:
        parsed = parse_reference(row["reference"])
        malformed_blocks += parsed["malformed_blocks"]
        if parsed["n_titles"] > 1 or parsed["n_chapters"] > 1:
            inconsistent_header += 1
        available = {b["bib_id"] for b in parsed["bibs"]}
        empty_abstracts += sum(1 for b in parsed["bibs"] if not b["abstract"])
        bibs_per_row.append(len(parsed["bibs"]))

        markers = target_bib_ids(row["target"])
        markers_per_row.append(len(markers))
        if not markers:
            continue
        rows_with_markers += 1

        resolved = [m for m in markers if m in available]
        markers_total += len(markers)
        markers_resolved += len(resolved)
        if len(resolved) == len(markers):
            rows_fully_resolved += 1
        elif len(unresolved_examples) < 5:
            unresolved_examples.append({
                "survey_title": parsed["survey_title"][:80],
                "missing": sorted(set(markers) - available)[:8],
                "available": sorted(available)[:8],
            })

        # Cited papers the chapter never actually cites in its prose.
        orphan_blocks += len(available - set(markers))

    rate = markers_resolved / markers_total if markers_total else 0.0
    return {
        "rows": len(rows),
        "rows_with_markers": rows_with_markers,
        "markers_total": markers_total,
        "markers_resolved": markers_resolved,
        "resolution_rate": rate,
        "rows_fully_resolved": rows_fully_resolved,
        "row_full_resolution_rate": rows_fully_resolved / max(rows_with_markers, 1),
        "malformed_blocks": malformed_blocks,
        "rows_with_inconsistent_header": inconsistent_header,
        "empty_abstracts": empty_abstracts,
        "orphan_blocks": orphan_blocks,
        "mean_bibs_per_row": sum(bibs_per_row) / max(len(bibs_per_row), 1),
        "mean_markers_per_row": sum(markers_per_row) / max(len(markers_per_row), 1),
        "unresolved_examples": unresolved_examples,
        "gate": RESOLUTION_GATE,
        "pass": rate >= RESOLUTION_GATE,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-321 - parse SciReviewGen and gate on it.")
    ap.add_argument("--split", default="validation", choices=["train", "validation", "test"])
    ap.add_argument("--n", type=int, default=1000,
                    help="rows to check (TASKLIST requires >= 500)")
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    print(f"T-321 - bib-resolution gate\n  split: {args.split}  rows: {args.n}\n")
    rows = load_split(args.split, limit=args.n)
    stats = parse_stats(rows)

    print(f"  rows parsed                    {stats['rows']:7,d}")
    print(f"  rows carrying BIB markers      {stats['rows_with_markers']:7,d}")
    print(f"  mean cited papers per row      {stats['mean_bibs_per_row']:7.2f}")
    print(f"  mean BIB markers per row       {stats['mean_markers_per_row']:7.2f}")
    print()
    print(f"  BIB markers in target          {stats['markers_total']:7,d}")
    print(f"  resolved to a reference block  {stats['markers_resolved']:7,d}")
    print(f"  RESOLUTION RATE                {stats['resolution_rate']:7.4f}   "
          f"gate >= {RESOLUTION_GATE}   {'PASS' if stats['pass'] else 'FAIL'}")
    print()
    print(f"  rows fully resolved            {stats['row_full_resolution_rate']:7.4f}")
    print(f"  malformed blocks               {stats['malformed_blocks']:7,d}")
    print(f"  rows w/ inconsistent header    {stats['rows_with_inconsistent_header']:7,d}")
    print(f"  empty abstracts                {stats['empty_abstracts']:7,d}")
    print(f"  cited-but-never-marked blocks  {stats['orphan_blocks']:7,d}")

    if stats["unresolved_examples"]:
        print("\n  unresolved examples:")
        for ex in stats["unresolved_examples"]:
            print(f"    {ex['survey_title']}")
            print(f"      missing {ex['missing']}  available {ex['available']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"split": args.split, **stats}, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")

    if not stats["pass"]:
        raise SystemExit(
            f"T-321 FAILED: resolution {stats['resolution_rate']:.4f} < {RESOLUTION_GATE}. "
            f"The delimiter parse is wrong - fix it. Do NOT silently drop unresolved "
            f"markers. If it still fails, fall back to kdercksen/scireviewgen-csv "
            f"before abandoning T-325 (TASKLIST Aug 28 kill switch)."
        )
    print(f"T-321 PASS: {stats['resolution_rate']:.4f} >= {RESOLUTION_GATE}. "
          f"T-322..T-325 are unblocked.")


if __name__ == "__main__":
    main()
