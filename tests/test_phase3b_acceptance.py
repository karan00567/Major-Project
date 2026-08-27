"""Phase 3B acceptance tests — the SciReviewGen track (T-320..T-326).

All offline: the delimiter grammar and the attribution rule are exercised
against synthetic rows shaped like the real ones (verified 2026-08-27 over
6,284 validation blocks — every block is exactly four fields ending in BIBnnn).
Tests marked ``network`` touch the Hub or OpenAlex.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from researchgpt.eval.scireviewgen import CITATION, EXPECTED_ROWS, LICENCE
from researchgpt.eval.scireviewgen_goldsets import MATCH_THRESHOLD, abstract_query, jaccard
from researchgpt.eval.scireviewgen_pairs import (
    chapter_id,
    clean_claim,
    is_degenerate,
    pairs_from_row,
    split_sentences,
)
from researchgpt.eval.scireviewgen_parser import (
    RESOLUTION_GATE,
    parse_reference,
    parse_stats,
    target_bib_ids,
)

REPO = pathlib.Path(__file__).resolve().parents[1]


def make_reference(title, chapter, blocks):
    """Build a `reference` cell the way the dataset does: header repeated per block."""
    return " ".join(
        f"{title} <s> {chapter} <s> {abstract} <s> {bib} </s>" for bib, abstract in blocks
    )


# --------------------------------------------------------------------------
# T-321 — the delimiter parse
# --------------------------------------------------------------------------


def test_t321_parses_the_four_field_block_grammar():
    ref = make_reference("Survey X", "Chapter Y",
                         [("BIB001", "First abstract."), ("BIB002", "Second abstract.")])
    parsed = parse_reference(ref)
    assert parsed["survey_title"] == "Survey X"
    assert parsed["chapter"] == "Chapter Y"
    assert [b["bib_id"] for b in parsed["bibs"]] == ["BIB001", "BIB002"]
    assert parsed["bibs"][0]["abstract"] == "First abstract."


def test_t321_survives_an_abstract_containing_the_field_delimiter():
    """A literal `<s>` inside an abstract must not shift every field left.

    Not observed in the validation split, but a silent field shift would put
    an abstract fragment in the bib_id slot and poison every downstream pair.
    """
    ref = "Survey <s> Chapter <s> Part one <s> part two <s> BIB007 </s>"
    parsed = parse_reference(ref)
    assert len(parsed["bibs"]) == 1
    assert parsed["bibs"][0]["bib_id"] == "BIB007"
    assert "Part one" in parsed["bibs"][0]["abstract"]
    assert "part two" in parsed["bibs"][0]["abstract"]


def test_t321_rejects_a_block_not_ending_in_a_bib_id():
    ref = "Survey <s> Chapter <s> An abstract <s> NOTABIB </s>"
    parsed = parse_reference(ref)
    assert parsed["bibs"] == []
    assert parsed["malformed_blocks"] == 1


def test_t321_ignores_empty_trailing_segments():
    ref = make_reference("S", "C", [("BIB001", "a")]) + "   "
    assert len(parse_reference(ref)["bibs"]) == 1


def test_t321_target_bib_ids_keeps_order_and_duplicates():
    assert target_bib_ids("x BIB003 y BIB001 z BIB003") == ["BIB003", "BIB001", "BIB003"]


def test_t321_resolution_rate_is_perfect_when_every_marker_resolves():
    rows = [{
        "reference": make_reference("S", "C", [("BIB001", "a"), ("BIB002", "b")]),
        "target": "Claim one BIB001. Claim two BIB002.",
    }]
    stats = parse_stats(rows)
    assert stats["markers_total"] == 2
    assert stats["resolution_rate"] == 1.0
    assert stats["pass"] is True


def test_t321_gate_fails_when_a_marker_has_no_block():
    """The gate must actually be able to fail, or it is decoration."""
    rows = [{
        "reference": make_reference("S", "C", [("BIB001", "a")]),
        "target": " ".join(f"Claim BIB{i:03d}." for i in range(1, 11)),
    }]
    stats = parse_stats(rows)
    assert stats["markers_total"] == 10
    assert stats["markers_resolved"] == 1
    assert stats["resolution_rate"] == pytest.approx(0.1)
    assert stats["pass"] is False
    assert stats["unresolved_examples"]


def test_t321_gate_threshold_matches_tasklist():
    assert RESOLUTION_GATE == 0.95


# --------------------------------------------------------------------------
# T-322 — the attribution rule (decisions.txt D-07a)
# --------------------------------------------------------------------------


def test_t322_keeps_single_cite_sentences():
    row = {
        "reference": make_reference("S", "C", [("BIB001", "Evidence abstract text.")]),
        "target": "Transformers substantially improve translation quality on WMT BIB001.",
    }
    pairs, tally = pairs_from_row(row)
    assert len(pairs) == 1
    assert pairs[0]["bib_id"] == "BIB001"
    assert pairs[0]["evidence"] == "Evidence abstract text."
    assert tally["kept"] == 1


def test_t322_drops_multi_cite_sentences():
    """D-07(a). A sentence citing two papers is not attributable to either."""
    row = {
        "reference": make_reference("S", "C", [("BIB001", "a" * 60), ("BIB002", "b" * 60)]),
        "target": "Several systems report large gains on this benchmark BIB001 BIB002.",
    }
    pairs, tally = pairs_from_row(row)
    assert pairs == []
    assert tally["multi_cite"] == 1


def test_t322_repeated_marker_in_one_sentence_is_still_single_cite():
    """Two mentions of the SAME paper is one source, not a multi-cite."""
    row = {
        "reference": make_reference("S", "C", [("BIB001", "Evidence abstract text.")]),
        "target": "As BIB001 shows, the method described by BIB001 improves accuracy markedly.",
    }
    pairs, tally = pairs_from_row(row)
    assert tally["multi_cite"] == 0
    assert len(pairs) == 1


def test_t322_strips_citation_markers_from_the_claim():
    row = {
        "reference": make_reference("S", "C", [("BIB001", "Evidence abstract text.")]),
        "target": "Transformers substantially improve translation quality on WMT BIB001.",
    }
    pairs, _ = pairs_from_row(row)
    assert "BIB001" not in pairs[0]["claim"]
    assert pairs[0]["claim"].startswith("Transformers substantially improve")


def test_t322_uncited_sentences_produce_nothing():
    row = {
        "reference": make_reference("S", "C", [("BIB001", "abstract")]),
        "target": "This sentence cites nothing at all and is merely connective prose.",
    }
    pairs, tally = pairs_from_row(row)
    assert pairs == []
    assert tally["no_citation"] == 1


def test_t322_chapter_id_is_stable_and_distinguishes_chapters():
    a = chapter_id("Survey A", "Chapter 1")
    assert a == chapter_id("Survey A", "Chapter 1")
    assert a != chapter_id("Survey A", "Chapter 2")
    assert a != chapter_id("Survey B", "Chapter 1")


# --------------------------------------------------------------------------
# T-323 — the quality filters hand-inspection surfaced
# --------------------------------------------------------------------------


@pytest.mark.parametrize("claim", [
    "An integrated inverter and LIM loss model is proposed in.",
    "His result is identical to the Bayesian posterior of the same parameters (see.",
    "They synthesized the mixed findings using the approach as described by.",
])
def test_t323_flags_dangling_reference_claims(claim):
    """Stripping the marker left no proposition. These are not verifiable."""
    assert is_degenerate(claim) == "dangling_reference"


@pytest.mark.parametrize("claim", [
    "This article is an attempt to contribute to this difficult review task.",
    "In this survey we cover the main families of approaches to the problem.",
    "Our review is organised around four themes that recur in the literature.",
])
def test_t323_flags_meta_sentences(claim):
    assert is_degenerate(claim) == "meta_sentence"


def test_t323_keeps_a_real_claim():
    claim = "MongoDB stores documents in a binary representation called BSON."
    assert is_degenerate(claim) is None


def test_t323_repairs_punctuation_debris_left_by_a_stripped_citation():
    assert clean_claim("Recently,, a study BIB001 found gains.") == \
        "Recently, a study found gains."
    assert "()" not in clean_claim("A method ( BIB001 ) was proposed for this task.")
    assert clean_claim("Progress over 40 years BIB001 -, has been steady.") == \
        "Progress over 40 years, has been steady."


def test_t323_degenerate_claims_never_reach_the_output():
    row = {
        "reference": make_reference("S", "C", [("BIB001", "Some evidence abstract here.")]),
        "target": "An integrated inverter and LIM loss model was carefully proposed in BIB001.",
    }
    pairs, tally = pairs_from_row(row)
    assert pairs == []
    assert tally["dangling_reference"] == 1


# --------------------------------------------------------------------------
# Sentence splitting
# --------------------------------------------------------------------------


def test_split_sentences_does_not_break_on_academic_abbreviations():
    """"et al." and "e.g." end in a period but not a sentence. Splitting there
    produces fragment claims that later look like verifier failures."""
    text = "Smith et al. reported gains. Others, e.g. Jones, disagree. A third result stands."
    assert len(split_sentences(text)) == 3


def test_split_sentences_handles_question_and_exclamation():
    assert len(split_sentences("Is this so? It appears to be. Indeed!")) == 3


def test_split_sentences_ignores_blank_fragments():
    assert split_sentences("One.   \n\n  Two.") == ["One.", "Two."]


# --------------------------------------------------------------------------
# T-324 — abstract matching
# --------------------------------------------------------------------------


def test_t324_jaccard_bounds():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a"}, {"b"}) == 0.0
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_t324_abstract_query_is_bounded_and_drops_punctuation():
    q = abstract_query("We propose, in this paper, a system for mining videos!", words=5)
    assert q.split() == ["We", "propose", "in", "this", "paper"]


def test_t324_match_threshold_is_not_delicately_placed():
    """Measured true matches scored 0.52-1.00 and the miss scored 0.00, so the
    threshold sits in an empty region of a bimodal distribution."""
    assert 0.3 <= MATCH_THRESHOLD <= 0.6


# --------------------------------------------------------------------------
# T-326 — licence and citation compliance
# --------------------------------------------------------------------------


def test_t326_citation_is_in_refs_bib():
    bib = (REPO / "refs.bib").read_text(encoding="utf-8")
    assert "kasanishi2023scireviewgen" in bib
    assert "2305.15186" in bib
    assert "CC BY-NC" in bib


def test_t326_licence_is_stated_in_the_data_section_source():
    doc = (REPO / "DATA_PROVENANCE.md").read_text(encoding="utf-8")
    assert "CC BY-NC 4.0" in doc
    assert "Kasanishi" in doc
    # The mirror-licence trap must be written down, not just known.
    assert "MIT" in doc and "pat-jj" in doc


def test_t326_module_constants_agree_with_the_documents():
    assert "CC BY-NC" in LICENCE
    assert "Kasanishi" in CITATION and "2305.15186" in CITATION


def test_t320_expected_counts_match_the_dataset_card():
    assert EXPECTED_ROWS == {"train": 84705, "validation": 4410, "test": 4457}


# --------------------------------------------------------------------------
# Live
# --------------------------------------------------------------------------


@pytest.mark.network
def test_t321_live_gate_holds_on_real_rows():
    """The assumption the whole track rests on, checked against real data."""
    pytest.importorskip("pyarrow")
    from researchgpt.eval.scireviewgen import load_split

    stats = parse_stats(load_split("validation", limit=200))
    assert stats["markers_total"] > 500
    assert stats["resolution_rate"] >= RESOLUTION_GATE
    assert stats["malformed_blocks"] == 0


@pytest.mark.network
def test_t322_live_pairs_have_the_documented_schema():
    pytest.importorskip("pyarrow")
    from researchgpt.eval.scireviewgen import load_split

    seen = 0
    for row in load_split("validation", limit=40):
        for pair in pairs_from_row(row)[0]:
            assert set(pair) == {"claim", "evidence", "bib_id", "survey_title", "chapter_id"}
            assert pair["claim"] and pair["evidence"]
            assert "BIB" not in pair["claim"]
            seen += 1
    assert seen > 0


def test_t322_stats_artefact_records_the_attribution_rule():
    path = REPO / "eval" / "scireviewgen_pairs_t322.json"
    if not path.exists():
        pytest.skip("T-322 has not been run in this checkout")
    stats = json.loads(path.read_text(encoding="utf-8"))
    assert "D-07" in stats["attribution_rule"]
    assert stats["pairs"] > 0
    assert stats["tally"]["multi_cite"] > 0, "the drop rule should have fired"
