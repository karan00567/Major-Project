"""Phase 5 acceptance tests — the Verifier (T-501..T-505).

The interesting cases here are not the happy paths. They are the ways a
verification step can *appear* to work while verifying nothing:

* claims decomposed from prose that carries no citations, so every counter
  reads clean because there was nothing to count;
* the (evidence, claim) pair silently reversed, which costs F1 with no error;
* a claim rescued by evidence from a paper it never cited;
* the abstract-only rule (T-505) either ignored or applied so literally that it
  empties a 100%-abstract-only corpus.
"""

from __future__ import annotations

import pathlib

import pytest

from researchgpt.agents.verifier import (
    MIN_CLAIM_CHARS,
    SUPPORT_THRESHOLD,
    Verifier,
    decompose,
    split_sentences,
    verdict_for,
)
from researchgpt.core.models import Chunk, Paper

REPO = pathlib.Path(__file__).resolve().parents[1]


class FakeModel:
    """Returns a scripted softmax, and records the pair order it was given."""

    def __init__(self, probs=None):
        self.probs = probs or {"SUPPORT": 0.95, "CONTRADICT": 0.03, "NEI": 0.02}
        self.seen: list[tuple[str, str]] = []

    def score(self, pairs):
        self.seen.extend(pairs)
        return [dict(self.probs) for _ in pairs]


def paper(pid, availability="full", abstract="An abstract about retrieval."):
    return Paper(paper_id=pid, title=f"Paper {pid}", source="openalex",
                 abstract=abstract, text_availability=availability)


def chunk(pid, text, cid=None):
    return Chunk(chunk_id=cid or f"{pid}-c1", paper_id=pid, text=text,
                 start_char=0, end_char=len(text))


def state_with(sections, papers, chunks, refs):
    return {
        "iteration": 0,
        "draft_sections": sections,
        "papers": papers,
        "chunks": chunks,
        "artefacts": {"reference_order": refs},
    }


# --------------------------------------------------------------------------
# T-501 — decomposition
# --------------------------------------------------------------------------


def test_sentence_split_survives_academic_abbreviations():
    """"et al.", "Fig. 3" and initials are not sentence boundaries.

    Splitting on them shatters one claim into fragments that the NLI model then
    scores as unsupported, inflating the drop count for a punctuation reason.
    """
    text = ("Wadden et al. built SciFact. See Fig. 3 for the ablation. "
            "S. Wadden reports macro-F1 of 0.77.")
    assert len(split_sentences(text)) == 3


def test_sentence_split_ignores_markdown_furniture():
    text = "## Heading\n\n| a | b |\n- a bullet point here\nA real sentence follows."
    out = split_sentences(text)
    assert not any(s.startswith(("#", "|")) for s in out)
    assert "A real sentence follows." in out


def test_decompose_yields_a_claim_per_cited_sentence_with_a_pointer():
    """The T-501 acceptance criterion: claims each carry a source pointer."""
    sections = {
        "Methods": (
            "Retrieval-augmented generation reduces hallucination in surveys [1]. "
            "A second grounded sentence describes the reranking stage [2]. "
            "This section reviews the literature."          # uncited -> not a claim
        )
    }
    claims = decompose(sections, ["pA", "pB"])
    assert len(claims) == 2, "uncited prose must not become a claim"
    assert [c["paper_ids"] for c in claims] == [["pA"], ["pB"]]
    for c in claims:
        assert c["section"] == "Methods"
        assert isinstance(c["sentence_index"], int)
        assert "[" not in c["text"], "citation markers must be stripped from the claim"


def test_decompose_maps_markers_through_the_global_reference_order():
    """The Writer renumbers every section into one global order before
    stitching, so [3] must mean the same paper in every section."""
    sections = {"A": "A grounded claim about retrieval systems [2].",
                "B": "Another grounded claim about verification [2]."}
    claims = decompose(sections, ["pX", "pY", "pZ"])
    assert {c["paper_ids"][0] for c in claims} == {"pY"}


def test_decompose_skips_dangling_markers():
    """A marker past the end of the reference list resolves to no paper, so the
    sentence cannot be checked at all. That is a Writer defect, surfaced rather
    than verified against an arbitrary paper."""
    sections = {"A": "A sentence citing a reference that does not exist [9]."}
    assert decompose(sections, ["pA"]) == []


def test_decompose_skips_fragments_below_the_length_floor():
    sections = {"A": "Yes [1]. " + "A properly long grounded sentence about RAG [1]."}
    claims = decompose(sections, ["pA"])
    assert len(claims) == 1
    assert len(claims[0]["text"]) >= MIN_CLAIM_CHARS - len("[1]")


# --------------------------------------------------------------------------
# T-503 / T-505 — verdict mapping
# --------------------------------------------------------------------------


def test_verdict_mapping_follows_project_plan_4_2():
    assert verdict_for({"SUPPORT": 0.95, "CONTRADICT": 0.03, "NEI": 0.02})[0] == "SUPPORTED"
    assert verdict_for({"SUPPORT": 0.55, "CONTRADICT": 0.20, "NEI": 0.25})[0] == "PARTIAL"
    assert verdict_for({"SUPPORT": 0.10, "CONTRADICT": 0.15, "NEI": 0.75})[0] == "UNSUPPORTED"
    assert verdict_for({"SUPPORT": 0.10, "CONTRADICT": 0.80, "NEI": 0.10})[0] == "CONTRADICTED"


def test_support_score_is_always_the_support_probability():
    """So the number means one thing across the whole report, rather than
    "confidence in whatever the model happened to pick"."""
    for probs in (
        {"SUPPORT": 0.95, "CONTRADICT": 0.03, "NEI": 0.02},
        {"SUPPORT": 0.10, "CONTRADICT": 0.80, "NEI": 0.10},
        {"SUPPORT": 0.10, "CONTRADICT": 0.15, "NEI": 0.75},
    ):
        assert verdict_for(probs)[1] == pytest.approx(probs["SUPPORT"])


def test_threshold_is_biased_to_precision():
    """CliVER measured a 21% false-Support rate and our own tuned checkpoint
    measures SUPPORT precision 0.800 (T-305). Over-predicting "supported" ships
    a hallucination with a citation attached; under-predicting merely drops a
    true sentence, which is visible in the dropped-claims panel."""
    assert SUPPORT_THRESHOLD >= 0.7
    just_under = {"SUPPORT": SUPPORT_THRESHOLD - 0.01, "CONTRADICT": 0.0, "NEI": 0.0}
    assert verdict_for(just_under)[0] == "PARTIAL"


def test_t505_abstract_only_support_is_capped_not_dropped():
    """The rule says abstract-only papers "may not supply verified claims".

    Read as a ban it empties the corpus - the M1 run was 100% abstract-only.
    Read as a cap it matches the evidence: Li et al. measured abstract-
    conditioned faithfulness at 0.745 against 0.94-0.96 with full text, which
    is degradation, not disqualification.
    """
    strong = {"SUPPORT": 0.99, "CONTRADICT": 0.005, "NEI": 0.005}
    verdict, score, cap = verdict_for(strong, abstract_only_support=True)
    assert verdict == "PARTIAL", "abstract-only evidence must not reach SUPPORTED"
    assert cap == "abstract_only_evidence", "the cap must be recorded, not silent"
    assert score == pytest.approx(0.99), "the score is unchanged; only the verdict caps"
    assert verdict_for(strong, abstract_only_support=False)[0] == "SUPPORTED"


# --------------------------------------------------------------------------
# T-502 / T-504 — the agent
# --------------------------------------------------------------------------


def test_pair_order_is_evidence_then_claim():
    """Premise then hypothesis. Reversing them scores a subtly different task
    and costs several F1 points with no visible error."""
    model = FakeModel()
    papers = [paper("pA")]
    chunks = [chunk("pA", "The evidence sentence lives here and is distinctive.")]
    sections = {"M": "A grounded claim about retrieval augmented systems [1]."}
    Verifier(model, cfg=None).run(state_with(sections, papers, chunks, ["pA"]))

    assert model.seen, "the model was never called"
    evidence, claim = model.seen[0]
    assert evidence.startswith("The evidence sentence"), "pair order is reversed"
    assert "grounded claim" in claim


def test_unsupported_claims_are_dropped_and_counted():
    """T-504's acceptance criterion: a run reports N claims dropped."""
    model = FakeModel({"SUPPORT": 0.05, "CONTRADICT": 0.10, "NEI": 0.85})
    papers = [paper("pA")]
    chunks = [chunk("pA", "Unrelated evidence about something else entirely.")]
    sections = {"M": "A grounded claim about retrieval augmented systems [1]."}
    out = Verifier(model, cfg=None).run(state_with(sections, papers, chunks, ["pA"]))

    assert len(out["unsupported_claims"]) == 1
    assert out["verified_claims"] == []
    assert out["grounding_score"] == 0.0


def test_contradictions_are_paired_with_their_papers():
    model = FakeModel({"SUPPORT": 0.05, "CONTRADICT": 0.90, "NEI": 0.05})
    papers = [paper("pA")]
    chunks = [chunk("pA", "Evidence that flatly contradicts the drafted claim.")]
    sections = {"M": "A grounded claim about retrieval augmented systems [1]."}
    out = Verifier(model, cfg=None).run(state_with(sections, papers, chunks, ["pA"]))

    assert out["unsupported_claims"][0].verdict == "CONTRADICTED"
    assert out["contradiction_pairs"] == [("c0001", "pA")]


def test_evidence_never_comes_from_an_uncited_paper():
    """Scoring a claim against the whole corpus would let an unrelated paper
    rescue a miscited sentence - the ALCE error mode."""
    model = FakeModel()
    papers = [paper("pA"), paper("pB")]
    chunks = [chunk("pA", "Evidence belonging to paper A, the cited one."),
              chunk("pB", "Evidence belonging to paper B, which is NOT cited.")]
    sections = {"M": "A grounded claim about retrieval augmented systems [1]."}
    Verifier(model, cfg=None).run(state_with(sections, papers, chunks, ["pA", "pB"]))

    assert all("paper B" not in evidence for evidence, _ in model.seen)


def test_a_claim_with_no_evidence_text_is_dropped_not_passed():
    """Citing a paper we hold no text for is not verifiable, so it must not be
    counted as verified."""
    model = FakeModel()
    papers = [paper("pA", abstract=None)]
    sections = {"M": "A grounded claim about retrieval augmented systems [1]."}
    out = Verifier(model, cfg=None).run(state_with(sections, papers, [], ["pA"]))

    assert out["verified_claims"] == []
    assert out["unsupported_claims"][0].verdict == "UNSUPPORTED"
    assert not model.seen, "no evidence means nothing should have been scored"


def test_grounding_score_is_verified_over_total():
    model = FakeModel()          # everything SUPPORTED
    papers = [paper("pA")]
    chunks = [chunk("pA", "Evidence supporting both drafted claims equally well.")]
    sections = {"M": ("A grounded claim about retrieval augmented systems [1]. "
                      "A second grounded claim about verification models [1].")}
    out = Verifier(model, cfg=None).run(state_with(sections, papers, chunks, ["pA"]))

    assert len(out["verified_claims"]) == 2
    assert out["grounding_score"] == 1.0


def test_verifier_is_not_fail_soft():
    """The Extractor may skip a paper; the Verifier may not skip verification.

    A run whose verification step silently did nothing would publish unverified
    prose while every counter read clean - the exact failure this project
    claims to prevent.
    """
    assert Verifier.fail_soft is False


def test_verifier_returns_only_keys_it_owns():
    """The partial-state contract (T-401). Returning accumulating fields it did
    not compute would duplicate the corpus on the Critic loop's second pass."""
    model = FakeModel()
    papers = [paper("pA")]
    chunks = [chunk("pA", "Some evidence text for the drafted claim.")]
    sections = {"M": "A grounded claim about retrieval augmented systems [1]."}
    out = Verifier(model, cfg=None).run(state_with(sections, papers, chunks, ["pA"]))

    assert set(out) == {"verified_claims", "unsupported_claims",
                        "contradiction_pairs", "grounding_score"}


# --------------------------------------------------------------------------
# Config wiring
# --------------------------------------------------------------------------


def test_config_points_at_a_verifier_model_that_exists():
    """This pinned data/models/verifier-int8.onnx for three days - a file that
    never existed, because T-304 exports to a directory. Nothing loaded it
    until Phase 5, so nothing failed."""
    from researchgpt.core.config import load_config

    cfg = load_config("configs/default.yaml")
    path = REPO / cfg.verifier.onnx_path
    if not path.exists():
        pytest.skip("verifier model not exported in this checkout")
    assert path.is_dir(), "T-304 exports a directory, not a bare .onnx file"
    assert list(path.glob("*.onnx")), f"no ONNX graph inside {path}"
