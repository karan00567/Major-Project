"""T-401 — the agent base class, the partial-state contract, and the trace hook.

Every node in the graph is an :class:`Agent`. Three things are centralised here
because getting any of them wrong is expensive and silent:

**1. Agents return a PARTIAL state, never the whole state** (`SPEC §14.3`).
LangGraph merges what a node returns through the reducers in
``graph/state.py``. Half those fields **accumulate** (``papers``, ``chunks``,
``retrieval_log``, ``decision_log``, ``human_overrides``) — so an agent that
helpfully returns the state it was given re-adds every paper it was handed, and
the corpus silently doubles on iteration 2 of the Critic loop. That is a
one-line mistake that looks like a retrieval bug three modules away, so
:meth:`Agent.__call__` refuses it rather than trusting each author to remember.

**2. The trace is written here, not in each agent.** `SPEC §14.10` and TASKLIST
T-107 make ``trace.jsonl`` the source of every figure in the report; T-904 says
its schema must stay stable from T-107 onward. Emitting the events in one place
is what makes that promise keepable.

**3. Failure containment is a per-agent decision, declared not improvised.**
``fail_soft = True`` means a raising agent is logged and contributes nothing,
and the run continues — right for the Extractor, where `SPEC §14.2` says one
unparseable paper must never abort a run. ``fail_soft = False`` (the default)
means the exception propagates — right for the Planner, where continuing with
no plan produces a confidently empty survey.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from researchgpt.core.logging import TraceLogger
from researchgpt.graph.state import ReviewState

#: Fields whose reducer is ``add``. Returning pre-existing members of these is
#: the duplication bug described above, so they are checked on the way out.
ACCUMULATE_FIELDS: frozenset[str] = frozenset(
    {"papers", "chunks", "retrieval_log", "decision_log", "human_overrides"}
)

#: Accumulating fields whose members carry a stable identity we can check.
_ID_ATTR: dict[str, str] = {"papers": "paper_id", "chunks": "chunk_id"}

#: Every key an agent is allowed to write. Typos in a returned key are
#: otherwise silent: LangGraph keeps the unknown key and nothing ever reads it.
VALID_STATE_KEYS: frozenset[str] = frozenset(ReviewState.__annotations__)


class PartialStateViolation(RuntimeError):
    """An agent returned something it is not allowed to return.

    Raised rather than warned. Both violations it catches — an unknown key, and
    re-returning already-accumulated items — corrupt state in ways that surface
    far from the cause.
    """


class Agent(ABC):
    """Base class for every graph node.

    Subclasses implement :meth:`run` and set :attr:`name`. The graph calls the
    instance (``__call__``), never ``run`` directly, so the trace and the
    contract checks cannot be bypassed by accident.
    """

    #: Appears in every trace event and in the Vue progress panel (T-606).
    name: str = "agent"

    #: See the module docstring. Default False: fail loudly unless a subclass
    #: has a stated reason not to.
    fail_soft: bool = False

    def __init__(self, trace: TraceLogger | None = None) -> None:
        self._trace = trace

    # -- subclass API ------------------------------------------------------

    @abstractmethod
    def run(self, state: ReviewState) -> dict[str, Any]:
        """Do the work and return **only the keys this agent changed**."""

    # -- graph API ---------------------------------------------------------

    def __call__(self, state: ReviewState) -> dict[str, Any]:
        iteration = state.get("iteration", 0)
        self._emit("agent_start", {}, iteration)
        started = time.perf_counter()

        try:
            update = self.run(state)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self._emit(
                "agent_error",
                {"error": f"{type(exc).__name__}: {exc}", "elapsed_ms": elapsed_ms,
                 "fail_soft": self.fail_soft},
                iteration,
            )
            if self.fail_soft:
                # Contribute nothing rather than a half-written update: a
                # partial write from a crashed agent is worse than no write.
                return {}
            # Re-raise UNCHANGED rather than wrapping. A wrapper would give the
            # graph one uniform failure type, but it destroys type-based
            # handling for the callers that need it - OpenAlexBudgetExhausted
            # and PlanValidationError both carry information a generic
            # AgentError would throw away. The trace already records which
            # agent failed, so the wrapper bought nothing.
            raise

        if update is None:
            update = {}
        if not isinstance(update, dict):
            raise PartialStateViolation(
                f"{self.name}.run() returned {type(update).__name__}, expected a dict "
                f"of state keys (SPEC 14.3)."
            )

        self._check_partial(update, state)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        self._emit("agent_end", {"elapsed_ms": elapsed_ms, **_summarise(update)}, iteration)
        return update

    # -- contract ----------------------------------------------------------

    def _check_partial(self, update: dict[str, Any], state: ReviewState) -> None:
        unknown = sorted(set(update) - VALID_STATE_KEYS)
        if unknown:
            raise PartialStateViolation(
                f"{self.name} returned unknown state key(s) {unknown}. Valid keys are "
                f"defined by ReviewState in graph/state.py. An unknown key is kept by "
                f"LangGraph and read by nothing, so this fails loudly instead."
            )

        for field, id_attr in _ID_ATTR.items():
            returned = update.get(field)
            if not returned:
                continue
            existing = {getattr(item, id_attr, None) for item in state.get(field, [])}
            if not existing:
                continue
            repeats = [
                getattr(item, id_attr, None)
                for item in returned
                if getattr(item, id_attr, None) in existing
            ]
            if repeats:
                raise PartialStateViolation(
                    f"{self.name} returned {len(repeats)} {field} that are ALREADY in "
                    f"state (e.g. {repeats[:3]}). '{field}' accumulates via an `add` "
                    f"reducer, so these would be duplicated. Return only what is new, "
                    f"and deduplicate against state[{field!r}] first."
                )

    def _emit(self, event: str, payload: dict, iteration: int) -> None:
        if self._trace is not None:
            self._trace.event(self.name, event, payload, iteration)


def _summarise(update: dict[str, Any]) -> dict[str, Any]:
    """Sizes, not contents.

    ``trace.jsonl`` is append-only and read end-to-end by the report scripts;
    dumping whole papers into it would make a 60-paper run's trace unusable.
    """
    out: dict[str, Any] = {}
    for key, value in update.items():
        if isinstance(value, (list, dict)):
            out[f"n_{key}"] = len(value)
        elif isinstance(value, (int, float, bool)) or value is None:
            out[key] = value
        elif isinstance(value, str):
            out[f"len_{key}"] = len(value)
    return out


__all__ = [
    "Agent",
    "PartialStateViolation",
    "ACCUMULATE_FIELDS",
    "VALID_STATE_KEYS",
]
