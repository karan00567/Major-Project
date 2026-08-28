"""T-507 — conditional edges, the loop bound, and the plan-diff rule.

`SPEC §7.5`. The Critic decides; this module decides whether the Critic is
*allowed* to have decided that.

★ **The iteration cap is enforced here as well as in the Critic, on purpose.**
Two independent guards on the same invariant looks redundant until you ask what
happens when one of them is wrong. The Critic's cap is a *policy* ("stop asking
for more evidence"); this one is a *safety* bound ("this graph terminates"). A
bug in the Critic — a threshold typo, a config with ``max_iterations`` unset —
turns an expensive loop into an unbounded one against a metered API. `SPEC §7.5`
calls for ``max_iterations = 3``; :func:`route_after_critic` guarantees it even
if every gate above it misbehaves.

★ **A REPLAN that returns the same plan is a defect, not a no-op.** It burns the
Planner's tokens, re-runs retrieval over the same queries, and arrives at the
same coverage gap — an oscillation that looks like progress in the trace
because the iteration counter moves. :func:`plan_diff` computes what actually
changed and :func:`assert_plan_changed` refuses a replan that changed nothing,
which is `SPEC §7.5`'s "mandatory plan diff on replan" made executable.
"""

from __future__ import annotations

from typing import Any

from researchgpt.agents.critic import REPLAN, RETRIEVE, WRITE
from researchgpt.graph.state import PLAN_FIELDS, ReviewState

#: Sentinel for "stop". ``build_graph`` maps it onto LangGraph's ``END``; the
#: sequential runner just stops. Kept as a plain string so routing stays
#: testable without importing LangGraph.
END_NODE = "__end__"

#: Where each decision sends the graph.
ROUTE: dict[str, str] = {
    WRITE: "writer",
    RETRIEVE: "retriever",
    REPLAN: "planner",
}


class PlanUnchangedError(RuntimeError):
    """A REPLAN produced the same plan it was asked to replace.

    Raised rather than warned: the loop would otherwise repeat the identical
    searches and reach the identical verdict, spending a full iteration and a
    Planner call to stand still.
    """


def plan_diff(before: ReviewState, after: ReviewState) -> dict[str, Any]:
    """What the Planner actually changed across ``PLAN_FIELDS``.

    Compared on the fields' *identifying* content rather than object identity,
    because the Planner rebuilds these objects every pass - so equal-but-new
    Pydantic models must count as unchanged, not as a change.
    """
    diff: dict[str, Any] = {}
    for field in PLAN_FIELDS:
        old = _fingerprint(before.get(field))
        new = _fingerprint(after.get(field))
        added = [x for x in new if x not in old]
        removed = [x for x in old if x not in new]
        diff[field] = {
            "added": added,
            "removed": removed,
            "changed": bool(added or removed),
            "before": len(old),
            "after": len(new),
        }
    diff["changed"] = any(diff[f]["changed"] for f in PLAN_FIELDS)
    return diff


def _fingerprint(value: Any) -> list[str]:
    """Comparable identity for plan items, whatever their concrete type."""
    if not value:
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        else:
            # SubQuestion -> its text; SearchTask -> its query. Both are what a
            # human means by "the plan changed".
            out.append(
                str(getattr(item, "text", None)
                    or getattr(item, "query", None)
                    or item)
            )
    return out


def assert_plan_changed(before: ReviewState, after: ReviewState) -> dict[str, Any]:
    """`SPEC §7.5`'s mandatory plan diff. Returns it; raises if it is empty."""
    diff = plan_diff(before, after)
    if not diff["changed"]:
        raise PlanUnchangedError(
            "REPLAN returned an identical plan: same sub-questions, same "
            "search queries, same inclusion criteria. Re-running it would "
            "repeat the same searches and reach the same coverage gap, "
            "spending an iteration and a Planner call to stand still. "
            "SPEC 7.5 requires a plan diff on replan."
        )
    return diff


def route_after_critic(state: ReviewState, max_iterations: int = 3) -> str:
    """The conditional edge. Returns the next node name, or :data:`END_NODE`.

    The cap is applied to the decision the Critic *made*, so a Critic that asks
    to loop past the bound is overridden rather than obeyed.

    ★ **WRITE means "stop" once a verified draft exists.** The Critic is
    reached twice per iteration: once after the Extractor (where its coverage
    and corpus gates run *before* the Writer spends tokens) and again after the
    Verifier (where the grounding gate finally has a ``grounding_score`` to
    read). Without this check the second visit would route back to the Writer
    and loop ``writer -> verifier -> critic -> writer`` forever inside a single
    iteration. The presence of ``final_review`` is what distinguishes the two
    visits, and it is the Writer's own output, so it cannot fall out of sync.
    """
    decision = state.get("decision") or WRITE
    iteration = state.get("iteration", 0)
    has_draft = bool(state.get("final_review"))

    if decision not in ROUTE:
        # An unknown decision must not silently become a loop. Finishing with
        # what we have is the recoverable direction; looping on a value nothing
        # understands is not.
        return END_NODE if has_draft else ROUTE[WRITE]

    if decision in (RETRIEVE, REPLAN) and iteration >= max_iterations - 1:
        return END_NODE if has_draft else ROUTE[WRITE]

    if decision == WRITE:
        return END_NODE if has_draft else ROUTE[WRITE]

    return ROUTE[decision]


def should_force_write(state: ReviewState, max_iterations: int = 3) -> bool:
    """True when the cap - not the Critic - is what sends us to the Writer.

    Kept separate from :func:`route_after_critic` so the Writer can say so in
    the Limitations section: `SPEC §7.5` wants unresolved gaps *recorded*, not
    quietly dropped because the loop ran out.
    """
    decision = state.get("decision") or WRITE
    return decision in (RETRIEVE, REPLAN) and state.get("iteration", 0) >= (
        max_iterations - 1
    )


def next_iteration(state: ReviewState) -> int:
    """Monotonic. The counter is the only thing standing between a stuck Critic
    and an unbounded spend, so it advances on every pass through the loop."""
    return state.get("iteration", 0) + 1


__all__ = [
    "ROUTE",
    "PlanUnchangedError",
    "assert_plan_changed",
    "plan_diff",
    "route_after_critic",
    "should_force_write",
    "next_iteration",
]
