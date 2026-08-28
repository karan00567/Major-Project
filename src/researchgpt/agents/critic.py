"""T-506 — the Critic. Is this review ready to be written?

`SPEC §7.5`. Full state in, ``WRITE | RETRIEVE | REPLAN`` out, plus the
coverage report the decision was made from.

★ **The Critic is deterministic. It makes no LLM call, and that is a decision,
not an omission.** Every gate `SPEC §7.5` specifies is arithmetic — coverage
≥ 80%, ≥ ``min_papers`` retained, grounding ≥ threshold, no sub-question below
two supporting papers. Three reasons to keep it that way:

* **Cost.** The free-tier token budget is this project's binding constraint,
  measured: T-409 exhausted a 200,000-token daily quota on four attempts in one
  afternoon. A loop that spends tokens deciding whether to spend tokens is the
  worst possible place for a generative call.
* **Auditability.** The loop is a graded claim ("agentic", `SPEC §7.5`). A
  reviewer can re-derive every routing decision from ``coverage_report`` in the
  trace. With an LLM in the seat the honest answer to *"why did it replan?"* is
  "the model said so".
* **Determinism.** A non-deterministic router turns an oscillating loop into an
  unreproducible bug. ``max_iterations = 3`` bounds it either way, but a
  deterministic Critic makes the same state produce the same route every time.

``core/prompts/critic_v1.md`` is kept — it is the shape an LLM Critic would
take if the budget ever allowed one, and its own header already says *"gate
thresholds come from config, not from this prompt"*.

⚠️ **Coverage is attributed through ``retrieval_log``, not through
``SubQuestion.supporting_paper_ids``.** Nothing populates the latter yet, and
inventing coverage from claim text would be a guess. The retrieval log records
``sq_id`` per search, so a paper is attributed to the sub-question whose query
first surfaced it. That under-counts: a paper found for SQ1 may well support
SQ3 too. It is a **conservative** bias — it can only make coverage look worse
and trigger an extra RETRIEVE, never wave a thin review through — which is the
right direction for the error to point.
"""

from __future__ import annotations

from typing import Any

from researchgpt.agents.base import Agent
from researchgpt.graph.state import ReviewState

#: `SPEC §7.5`: "no sub-question with < 2 supporting papers". One paper is an
#: anecdote; a survey section resting on it is not a review of the literature.
MIN_PAPERS_PER_SUB_QUESTION = 2

WRITE, RETRIEVE, REPLAN = "WRITE", "RETRIEVE", "REPLAN"


def coverage_report(
    sub_questions: list[Any], retrieval_log: list[dict]
) -> dict[str, Any]:
    """Papers attributable to each sub-question, and the resulting coverage."""
    found: dict[str, int] = {}
    for entry in retrieval_log or []:
        sq_id = entry.get("sq_id")
        if not sq_id:
            continue
        found[sq_id] = found.get(sq_id, 0) + int(entry.get("new") or 0)

    per_sq, uncovered = {}, []
    for sq in sub_questions or []:
        sq_id = getattr(sq, "sq_id", None) or ""
        n = found.get(sq_id, 0)
        covered = n >= MIN_PAPERS_PER_SUB_QUESTION
        per_sq[sq_id] = {
            "papers": n,
            "covered": covered,
            "text": getattr(sq, "text", ""),
            "facet": getattr(sq, "facet", ""),
        }
        if not covered:
            uncovered.append(sq_id)

    total = len(per_sq)
    return {
        "per_sub_question": per_sq,
        "uncovered": uncovered,
        "coverage": (total - len(uncovered)) / total if total else 0.0,
        "sub_questions": total,
    }


class Critic(Agent):
    name = "critic"
    #: NOT fail-soft. A Critic that fails and contributes nothing leaves
    #: ``decision`` unset, and the router would have to invent a route - which
    #: is how a loop becomes infinite or a thin review ships unnoticed.
    fail_soft = False

    def __init__(self, cfg: Any, trace: Any = None) -> None:
        super().__init__(trace=trace)
        self._cfg = cfg

    def run(self, state: ReviewState) -> dict[str, Any]:
        review = self._cfg.review
        iteration = state.get("iteration", 0)
        papers = state.get("papers") or []
        report = coverage_report(
            state.get("sub_questions") or [], state.get("retrieval_log") or []
        )
        grounding = state.get("grounding_score")
        prior = [d.get("decision") for d in (state.get("decision_log") or [])]

        decision, reasons = self._decide(
            review, iteration, len(papers), report, grounding, prior
        )
        feedback = self._feedback(decision, reasons, report)

        self._emit(
            "critic_decision",
            {
                "decision": decision,
                "iteration": iteration,
                "max_iterations": review.max_iterations,
                "papers": len(papers),
                "coverage": round(report["coverage"], 4),
                "uncovered": report["uncovered"],
                "grounding_score": grounding,
                "reasons": reasons,
            },
            iteration,
        )

        update: dict[str, Any] = {
            "decision": decision,
            "critic_feedback": feedback,
            "coverage_report": report,
            "decision_log": [
                {
                    "iteration": iteration,
                    "decision": decision,
                    "reasons": reasons,
                    "coverage": report["coverage"],
                    "papers": len(papers),
                    "grounding_score": grounding,
                }
            ],
        }

        # ★ Advance the loop counter HERE, and only on a loop-back.
        #
        # 🔴 Nothing else does. The counter is the only thing between a Critic
        # that keeps asking for more evidence and an unbounded spend against a
        # metered API, and in the compiled graph no node was incrementing it -
        # so both the Critic's cap and routing's safety bound compared against
        # a permanently-zero iteration and could never fire. Caught by an
        # unused-import lint on `next_iteration`, not by a test, which is why
        # `test_iteration_advances_only_on_a_loop_back` now exists.
        #
        # Incremented on RETRIEVE/REPLAN only: the Critic is visited twice per
        # iteration (after the Extractor, then after the Verifier), and
        # counting both visits would halve the real iteration budget.
        if decision in (RETRIEVE, REPLAN):
            update["iteration"] = iteration + 1

        return update

    # -- gates -------------------------------------------------------------

    def _decide(
        self,
        review: Any,
        iteration: int,
        n_papers: int,
        report: dict,
        grounding: float | None,
        prior: list[str],
    ) -> tuple[str, list[str]]:
        reasons: list[str] = []

        # Gate 0 - the loop bound, checked FIRST so nothing below can override
        # it. SPEC 7.5: "On the final iteration force WRITE and record
        # unresolved gaps in a Limitations section rather than looping forever."
        if iteration >= review.max_iterations - 1:
            reasons.append(
                f"iteration {iteration} is the last of {review.max_iterations}; "
                f"forcing WRITE per SPEC 7.5"
            )
            if report["uncovered"]:
                reasons.append(
                    f"unresolved coverage gaps carried into Limitations: "
                    f"{report['uncovered']}"
                )
            return WRITE, reasons

        # Gate 1 - corpus size. Nothing else is worth assessing on 3 papers.
        if n_papers < review.min_papers:
            reasons.append(
                f"{n_papers} papers retained, below min_papers={review.min_papers}"
            )
            return RETRIEVE, reasons

        # Gate 2 - coverage. RETRIEVE first; escalate to REPLAN only if a
        # RETRIEVE has already been tried and the gap is still there. Replanning
        # before searching harder throws away a plan that may only have needed
        # more results, and a replan costs the Planner's tokens.
        if report["coverage"] < review.coverage_threshold or report["uncovered"]:
            reasons.append(
                f"coverage {report['coverage']:.2f} < {review.coverage_threshold} "
                f"({len(report['uncovered'])} sub-question(s) under "
                f"{MIN_PAPERS_PER_SUB_QUESTION} papers: {report['uncovered']})"
            )
            if RETRIEVE in prior:
                reasons.append(
                    "a previous RETRIEVE did not close the gap, so the plan itself "
                    "is the problem, not the search depth"
                )
                return REPLAN, reasons
            return RETRIEVE, reasons

        # Gate 3 - grounding. Only meaningful once the Verifier has run; on the
        # first pass there is no draft yet and grounding is None.
        if grounding is not None and grounding < review.grounding_threshold:
            reasons.append(
                f"grounding {grounding:.2f} < {review.grounding_threshold}: the "
                f"corpus does not support the drafted claims"
            )
            return RETRIEVE, reasons

        reasons.append(
            f"coverage {report['coverage']:.2f}, {n_papers} papers"
            + (f", grounding {grounding:.2f}" if grounding is not None else "")
        )
        return WRITE, reasons

    @staticmethod
    def _feedback(decision: str, reasons: list[str], report: dict) -> str:
        lines = [f"DECISION: {decision}"] + [f"- {r}" for r in reasons]
        if decision in (RETRIEVE, REPLAN) and report["uncovered"]:
            lines.append("Under-covered sub-questions:")
            for sq_id in report["uncovered"]:
                info = report["per_sub_question"].get(sq_id, {})
                lines.append(
                    f"  {sq_id} ({info.get('facet', '?')}, {info.get('papers', 0)} "
                    f"papers): {info.get('text', '')}"
                )
        return "\n".join(lines)


__all__ = ["Critic", "coverage_report", "MIN_PAPERS_PER_SUB_QUESTION",
           "WRITE", "RETRIEVE", "REPLAN"]
