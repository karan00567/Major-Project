"""LangGraph state definition.

Source of truth: RESEARCHGPT_SPEC.md §8.1.

The reducer choice on each field is the load-bearing part of this file, because
the Critic loop (TASKLIST T-507) can re-enter ``retriever`` and ``planner`` up to
three times. Getting a reducer wrong shows up as silently duplicated papers or
silently lost insights on iteration 2, which is expensive to debug once six
agents sit on top of it.

The rule applied here:

* **Accumulate** (``add``) anything the loop legitimately gathers more of across
  iterations: papers, chunks, log lines.
* **Replace** (default) anything an agent recomputes wholesale each pass:
  insights, claims, the draft, the Critic's decision.

``papers`` and ``chunks`` accumulate, so the retriever must deduplicate by
``paper_id`` / ``chunk_id`` before returning — the reducer will not do it.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from researchgpt.core.models import (
    Chunk,
    Claim,
    Paper,
    PaperInsight,
    SearchTask,
    SubQuestion,
)


def _merge_dict(left: dict, right: dict) -> dict:
    """Shallow-merge reducer for dict fields written by more than one node."""
    return {**left, **right}


class ReviewState(TypedDict, total=False):
    # ---- input -----------------------------------------------------------
    run_id: str
    research_question: str
    constraints: dict  # years, venues, max_papers, language

    # ---- planner ---------------------------------------------------------
    # Replaced wholesale on REPLAN: a replan supersedes the previous plan
    # rather than adding to it (SPEC §7.5 requires a plan diff on replan).
    sub_questions: list[SubQuestion]
    search_plan: list[SearchTask]
    inclusion_criteria: list[str]

    # ---- retriever -------------------------------------------------------
    # Accumulated: a RETRIEVE loop is meant to add coverage, not start over.
    # Retriever MUST dedupe by paper_id / chunk_id before returning.
    papers: Annotated[list[Paper], add]
    chunks: Annotated[list[Chunk], add]
    retrieval_log: Annotated[list[dict], add]

    # ---- extractor / verifier -------------------------------------------
    # Replaced: recomputed over the full corpus each pass.
    paper_insights: list[PaperInsight]
    verified_claims: list[Claim]
    #: Dropped claims. Surfaced in Vue panel 4 (T-608) and counted in the
    #: trace — TASKLIST calls this "the real measure of what the architecture
    #: buys", so it is state, not a side effect.
    unsupported_claims: list[Claim]
    contradiction_pairs: list[tuple[str, str]]
    grounding_score: float

    # ---- critic ----------------------------------------------------------
    decision: str  # WRITE | RETRIEVE | REPLAN
    critic_feedback: str
    coverage_report: dict
    #: Hard-capped at review.max_iterations by routing.py (T-507).
    iteration: int
    #: Append-only audit of every routing decision, so an oscillating loop is
    #: diagnosable after the fact rather than by re-running.
    decision_log: Annotated[list[dict], add]

    # ---- human in the loop (T-609, gated on the T-007 decision) ----------
    human_overrides: Annotated[list[dict], add]

    # ---- writer ----------------------------------------------------------
    themes: list[dict]
    draft_sections: dict
    final_review: str
    artefacts: Annotated[dict[str, Any], _merge_dict]


#: Fields the Planner is allowed to overwrite on a REPLAN. Used by routing.py
#: to compute the mandatory plan diff (SPEC §7.5).
PLAN_FIELDS = ("sub_questions", "search_plan", "inclusion_criteria")

__all__ = ["ReviewState", "PLAN_FIELDS"]
