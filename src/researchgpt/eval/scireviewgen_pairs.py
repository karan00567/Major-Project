"""T-322 ★ — emit human-authored claim→evidence pairs from SciReviewGen.

For each sentence in a survey chapter that cites ``BIBnnn``, pair it with that
bib's abstract. The claim is a sentence **a human wrote**; the evidence is a
paper **a human chose to cite for it**. Neither came from our pipeline, which is
the entire point (``PROJECT_PLAN §9.6``, T-325).

**Attribution rule — decided, not defaulted.** ``decisions.txt`` D-07 (a):
**drop multi-cite sentences entirely.** A sentence citing three papers is not
cleanly attributable to any one of them, and pairing it against each in turn
would label the claim SUPPORTED by evidence that may only cover a third of it.
Keeping only single-cite sentences means every surviving pair is one claim, one
source — exactly the judgement the verifier makes in the pipeline.

The cost is real and is reported rather than hidden: survey prose cites in
bundles, so a large share of sentences are discarded. That drop rate belongs in
the report's method section.

⚠️ **Citation markers are stripped from the claim text.** Leaving ``BIB001``
inline would feed the verifier a token it never sees at inference time. The
surrounding prose citations SciReviewGen could not link (``(Jordan and Mitchell
2015)``) are left alone — removing them would need a second, unreliable parser.

⚠️ **Stripping the marker can destroy the sentence, and T-323's hand-inspection
is what caught it.** *"An integrated inverter and LIM loss model is proposed in
BIB018."* becomes *"...is proposed in."* — grammatical debris with no
proposition left to verify. Measured over the first 1,857-pair build, **11% of
pairs were degenerate this way**: 7.3% ended on a dangling preposition, 1.1%
carried punctuation debris from a stripped inline citation, and 2.8% were
meta-sentences about the survey itself (*"this article is an attempt to..."*)
rather than claims about the cited work.

None of these are verifiable claims, and leaving them in would have shown up
later as verifier "errors" that were really data defects — the worst kind of
measurement bug in a track whose entire purpose is an honest cross-check. The
build now repairs what it can and drops the rest, reporting both counts.

Run::

    python -m researchgpt.eval.scireviewgen_pairs --split validation --chapters 500
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from collections import Counter
from typing import Any

from researchgpt.eval.scireviewgen import load_split
from researchgpt.eval.scireviewgen_parser import BIB_RE, parse_reference, target_bib_ids

DEFAULT_OUT = pathlib.Path("data/scireviewgen/pairs.jsonl")
DEFAULT_STATS = pathlib.Path("eval/scireviewgen_pairs_t322.json")

#: Sentence-final abbreviations that must NOT end a sentence. Academic prose is
#: dense with these; without the guard "et al." splits mid-citation and produces
#: fragment claims that look like verifier failures later.
_ABBREV = {
    "e.g", "i.e", "cf", "vs", "etc", "al", "et al", "fig", "eq", "ref", "refs",
    "approx", "resp", "no", "vol", "pp", "sec", "ch", "dr", "prof", "mr", "ms",
    "st", "inc", "ltd", "jr", "sr", "ca", "viz", "ie", "eg",
}

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

#: A sentence whose grammatical object WAS the citation. After the marker is
#: stripped these end mid-thought ("...as described by.", "...(see.") and carry
#: no proposition. Found by T-323 hand-inspection, not by any count.
_DANGLING_RE = re.compile(
    r"\b(in|by|of|to|from|with|see|and|as|via|using|like|such as|e\.g|i\.e"
    r"|proposed|introduced|described|reported|shown|given|studied|discussed)"
    r"\s*[.;:,]?\s*$",
    re.IGNORECASE,
)

#: Sentences about the survey rather than about the cited paper. In survey prose
#: "we"/"our" are the survey's authors, so these are commentary, not claims.
_META_RE = re.compile(
    r"\b(this (article|survey|paper|review|chapter|section)|we\s|our\s)", re.IGNORECASE
)

#: Punctuation wreckage left where an inline citation used to be.
_DEBRIS_SUBS = (
    (re.compile(r"\(\s*[,;.\-]*\s*\)"), ""),      # ( ) ( , ) ( - )
    (re.compile(r"\[\s*[,;.\-]*\s*\]"), ""),      # [ ] [ - ]
    (re.compile(r"\s+-\s*(?=[,.;:])"), ""),       # " -," -> ","
    (re.compile(r"(,\s*){2,}"), ", "),             # ",," -> ","
    (re.compile(r"\s+([,.;:)\]])"), r"\1"),        # " ," -> ","
    (re.compile(r"([(\[])\s+"), r"\1"),            # "( x" -> "(x"
    (re.compile(r"\s{2,}"), " "),
)

#: A claim shorter than this is a fragment, not a proposition worth verifying.
MIN_CLAIM_CHARS = 40
#: Longer than this and it is almost certainly a failed split.
MAX_CLAIM_CHARS = 600


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, rejoining splits made after an abbreviation."""
    raw = _SENT_SPLIT.split(text)
    out: list[str] = []
    for piece in raw:
        piece = piece.strip()
        if not piece:
            continue
        if out:
            tail = out[-1].rstrip(".").rsplit(" ", 1)[-1].lower().strip("(),")
            if tail in _ABBREV:
                out[-1] = f"{out[-1]} {piece}"
                continue
        out.append(piece)
    return out


def chapter_id(survey_title: str, chapter: str) -> str:
    """Stable id for a (survey, chapter). Row order is not stable across mirrors."""
    key = f"{survey_title}\x00{chapter}".encode()
    return hashlib.sha1(key).hexdigest()[:12]


def clean_claim(sentence: str) -> str:
    """Strip BIB markers and repair the punctuation they leave behind.

    Repair, not just whitespace tidying: a stripped inline citation leaves
    constructs like ``Recently,, see also, Harrison 1999)`` that are noise to a
    cross-encoder. What cannot be repaired is dropped by :func:`is_degenerate`.
    """
    text = BIB_RE.sub("", sentence)
    for pattern, replacement in _DEBRIS_SUBS:
        text = pattern.sub(replacement, text)
    return text.strip(" ,;:-")


def is_degenerate(claim: str) -> str | None:
    """Return a drop reason, or ``None`` if the claim is worth verifying."""
    if _DANGLING_RE.search(claim):
        return "dangling_reference"
    if _META_RE.search(claim):
        return "meta_sentence"
    return None


def pairs_from_row(row: dict[str, Any]) -> tuple[list[dict[str, Any]], Counter]:
    """Emit single-cite pairs for one chapter, plus a reason-tally for the drops."""
    parsed = parse_reference(row["reference"])
    abstracts = {b["bib_id"]: b["abstract"] for b in parsed["bibs"]}
    cid = chapter_id(parsed["survey_title"], parsed["chapter"])

    tally: Counter = Counter()
    pairs: list[dict[str, Any]] = []

    for sentence in split_sentences(row["target"]):
        markers = set(target_bib_ids(sentence))
        if not markers:
            tally["no_citation"] += 1
            continue
        if len(markers) > 1:
            # D-07 (a): not cleanly attributable to one source.
            tally["multi_cite"] += 1
            continue

        bib_id = next(iter(markers))
        evidence = abstracts.get(bib_id)
        if not evidence:
            tally["unresolved_marker"] += 1
            continue

        claim = clean_claim(sentence)
        if len(claim) < MIN_CLAIM_CHARS:
            tally["too_short"] += 1
            continue
        if len(claim) > MAX_CLAIM_CHARS:
            tally["too_long"] += 1
            continue
        reason = is_degenerate(claim)
        if reason:
            tally[reason] += 1
            continue

        tally["kept"] += 1
        pairs.append({
            "claim": claim,
            "evidence": evidence,
            "bib_id": bib_id,
            "survey_title": parsed["survey_title"],
            "chapter_id": cid,
        })

    return pairs, tally


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-322 - human-authored claim->evidence pairs.")
    ap.add_argument("--split", default="validation", choices=["train", "validation", "test"])
    ap.add_argument("--chapters", type=int, default=500)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--stats", type=pathlib.Path, default=DEFAULT_STATS)
    args = ap.parse_args(argv)

    print(f"T-322 - claim->evidence pairs\n  split: {args.split}  "
          f"chapters: {args.chapters}\n  rule: D-07(a) drop multi-cite sentences\n")

    rows = load_split(args.split, limit=args.chapters)
    all_pairs: list[dict[str, Any]] = []
    tally: Counter = Counter()
    per_chapter: list[int] = []

    for row in rows:
        pairs, row_tally = pairs_from_row(row)
        all_pairs.extend(pairs)
        tally.update(row_tally)
        per_chapter.append(len(pairs))

    sentences = sum(tally.values())
    cited = sentences - tally["no_citation"]
    print(f"  sentences seen                 {sentences:7,d}")
    print(f"    without any citation         {tally['no_citation']:7,d}")
    print(f"    citing >1 paper (DROPPED)    {tally['multi_cite']:7,d}")
    print(f"    unresolved marker            {tally['unresolved_marker']:7,d}")
    print(f"    too short (<{MIN_CLAIM_CHARS} chars)        {tally['too_short']:7,d}")
    print(f"    too long (>{MAX_CLAIM_CHARS} chars)       {tally['too_long']:7,d}")
    print(f"    dangling reference (T-323)   {tally['dangling_reference']:7,d}")
    print(f"    meta-sentence (T-323)        {tally['meta_sentence']:7,d}")
    print(f"    KEPT                         {tally['kept']:7,d}")
    print()
    if cited:
        print(f"  of {cited:,} citing sentences, {tally['multi_cite'] / cited:.1%} were "
              f"multi-cite and dropped by D-07(a)")
    print(f"  pairs per chapter: min {min(per_chapter)}  max {max(per_chapter)}  "
          f"mean {sum(per_chapter) / max(len(per_chapter), 1):.2f}")
    print(f"  chapters yielding zero pairs: {sum(1 for n in per_chapter if n == 0)}")
    print(f"  distinct chapters: {len({p['chapter_id'] for p in all_pairs}):,}")
    print(f"  distinct surveys:  {len({p['survey_title'] for p in all_pairs}):,}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for pair in all_pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    print(f"\n  wrote {args.out}  ({len(all_pairs):,} pairs)")

    hist = Counter(per_chapter)
    stats = {
        "task": "T-322",
        "split": args.split,
        "chapters_read": len(rows),
        "attribution_rule": "D-07(a): drop multi-cite sentences",
        "tally": dict(tally),
        "pairs": len(all_pairs),
        "multi_cite_drop_rate_of_citing_sentences": (
            tally["multi_cite"] / cited if cited else 0.0
        ),
        "pairs_per_chapter": {
            "min": min(per_chapter), "max": max(per_chapter),
            "mean": sum(per_chapter) / max(len(per_chapter), 1),
            "histogram": {str(k): v for k, v in sorted(hist.items())},
        },
        "distinct_chapters": len({p["chapter_id"] for p in all_pairs}),
        "distinct_surveys": len({p["survey_title"] for p in all_pairs}),
    }
    args.stats.parent.mkdir(parents=True, exist_ok=True)
    args.stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"  wrote {args.stats}")


if __name__ == "__main__":
    main()
