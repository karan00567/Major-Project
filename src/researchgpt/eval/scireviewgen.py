"""T-320 — load the SciReviewGen mirror and record its provenance.

**Why this track exists.** ``PROJECT_PLAN.md §9.6`` names a credibility trap
that is fatal if unanswered: *"The groundedness metric is circular. The system
enforces groundedness, then measures it. Groundedness = 0.98 proves only that
the filter ran."* SciReviewGen supplies claims **humans wrote** citing papers
**humans chose**, so agreement with it is genuinely independent of our pipeline
(T-325).

**Mirror provenance — read this before citing anything.** The original dataset
is Kasanishi et al., *Findings of ACL 2023* (arXiv:2305.15186), released
**CC BY-NC 4.0**. This module reads the ungated Hugging Face mirror
``kejian/SciReviewGen``. ⚠️ **The mirrors' licence metadata is unreliable**:
``pat-jj/SciReviewGen`` declares MIT, which a mirror of S2ORC-derived data
cannot grant. **Cite Kasanishi et al. and state CC BY-NC regardless of what any
mirror card says** (T-326).

The dataset is frozen at **S2ORC 2020-07-05**, which matters twice over:
live OpenAlex retrieval surfaces post-2020 papers that are correct but score as
false positives (T-212b), and the corpus skews biomedical against our CS target
domain (T-334).

**Two columns only**, and both intended uses are recoverable by parsing::

    reference  survey_title <s> chapter <s> abstract <s> BIBnnn </s>   (repeated)
    target     the human-written chapter, with inline BIBnnn markers

Run::

    python -m researchgpt.eval.scireviewgen          # verify + record provenance
"""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

#: The mirror actually read. Two others exist (``kdercksen/scireviewgen-csv``
#: carries the same splits and is the T-321 fallback named in the Aug 28 kill
#: switch; ``pat-jj/SciReviewGen`` mis-declares its licence).
REPO = "kejian/SciReviewGen"

#: Shard filenames are content-hashed, so they are resolved from the repo
#: listing rather than hard-coded — a re-upload would change them.
_SPLIT_PREFIX = {"train": "data/train-", "validation": "data/validation-", "test": "data/test-"}

#: Row counts from the dataset card, verified 2026-08-25. :func:`load_split`
#: checks against these: a silently re-built mirror would otherwise change the
#: evidence base without changing any code.
EXPECTED_ROWS: dict[str, int] = {"train": 84705, "validation": 4410, "test": 4457}

CITATION = (
    "Kasanishi, T., Isonuma, M., Mori, J., Sakata, I. (2023). SciReviewGen: A "
    "Large-scale Dataset for Automatic Literature Review Generation. Findings of "
    "ACL 2023. arXiv:2305.15186."
)
LICENCE = "CC BY-NC 4.0 (non-commercial; an academic project satisfies this)"

DEFAULT_OUT = pathlib.Path("data/scireviewgen")


def shard_paths(split: str) -> list[pathlib.Path]:
    """Resolve and download the parquet shards for one split."""
    from huggingface_hub import hf_hub_download, list_repo_files

    prefix = _SPLIT_PREFIX[split]
    names = sorted(f for f in list_repo_files(REPO, repo_type="dataset") if f.startswith(prefix))
    if not names:
        raise SystemExit(f"no shards matching {prefix!r} in {REPO}")
    return [
        pathlib.Path(hf_hub_download(REPO, name, repo_type="dataset")) for name in names
    ]


def load_split(split: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Read one split as a list of ``{reference, target}`` dicts.

    ``limit`` stops after that many rows, reading only as many shards as needed
    — the train split is 460 MB across three shards and most callers want a
    sample, not all 84,705 rows.
    """
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for path in shard_paths(split):
        table = pq.read_table(path)
        rows.extend(table.to_pylist())
        if limit is not None and len(rows) >= limit:
            return rows[:limit]

    expected = EXPECTED_ROWS.get(split)
    if expected is not None and len(rows) != expected:
        print(
            f"  WARNING: {split}: got {len(rows)} rows, expected {expected}. The mirror "
            f"may have been rebuilt; re-verify T-321 before trusting T-325."
        )
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-320 - verify the SciReviewGen mirror.")
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    print(f"T-320 - SciReviewGen mirror check\n  repo: {REPO}\n")

    counts: dict[str, int] = {}
    shards: dict[str, list[str]] = {}
    ok = True
    for split in ("train", "validation", "test"):
        paths = shard_paths(split)
        rows = load_split(split)
        counts[split] = len(rows)
        shards[split] = [p.name for p in paths]
        expected = EXPECTED_ROWS[split]
        match = "OK " if len(rows) == expected else "MISMATCH"
        ok &= len(rows) == expected
        print(f"  {split:11s} {len(rows):7,d} rows  (expected {expected:7,d})  "
              f"{len(paths)} shard(s)  {match}")

    total_shards = sum(len(v) for v in shards.values())
    print(f"\n  {total_shards} parquet shards loaded")

    args.out.mkdir(parents=True, exist_ok=True)
    provenance = {
        "task": "T-320",
        "repo": REPO,
        "counts": counts,
        "expected": EXPECTED_ROWS,
        "shards": shards,
        "citation": CITATION,
        "licence": LICENCE,
        "licence_note": (
            "Mirror licence metadata is unreliable; pat-jj/SciReviewGen declares MIT, "
            "which a mirror of S2ORC-derived data cannot grant. Cite Kasanishi et al. "
            "and state CC BY-NC regardless of the mirror card (T-326)."
        ),
        "frozen_at": "S2ORC 2020-07-05",
        "frozen_note": (
            "Live OpenAlex retrieval surfaces post-2020 papers that are correct but "
            "score as false positives (T-212b). Report as a measurement artefact."
        ),
    }
    path = args.out / "provenance.json"
    path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(f"  wrote {path}")

    if not ok:
        raise SystemExit("T-320 FAILED: row counts do not match the dataset card.")
    print("\nT-320 PASS: all shards load and every split matches the published count.")


if __name__ == "__main__":
    main()
