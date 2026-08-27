"""T-405 — build and run the pipeline.

TASKLIST T-405: wire **linearly first** —
``PLANNER -> RETRIEVER -> INGEST/RANK -> EXTRACTOR -> WRITER`` — with no Critic
loop. The loop is T-507, in Phase 5. Getting a straight line to produce a cited
survey is **M1**, the milestone TASKLIST calls the insurance policy: *"if
everything after this collapses, there is still something to submit."*

Two implementations, deliberately:

* :func:`run_pipeline` — a plain sequential runner with no LangGraph
  dependency. This is what M1 is demonstrated with, and what the tests use.
* :func:`build_graph` — the same nodes compiled into a ``StateGraph``, so the
  Critic loop has something to attach to in Phase 5, and so the "agentic"
  claim is structurally true rather than asserted.

They share the node functions, so the two cannot drift.

**Why the sequential runner is not a shortcut.** The reducers in
``graph/state.py`` are what make the LangGraph version correct, and a plain
runner that merged state naively would hide the accumulate/replace distinction
until the Critic loop turned it into a duplication bug. :func:`_merge` therefore
applies **the same reducer rules** as the compiled graph.
"""

from __future__ import annotations

import pathlib
import uuid
from typing import Any

from researchgpt.agents.extractor import Extractor
from researchgpt.agents.planner import Planner
from researchgpt.agents.ranker import Ranker
from researchgpt.agents.retriever import Retriever
from researchgpt.agents.writer import Writer
from researchgpt.core.llm import LLMClient
from researchgpt.core.logging import TraceLogger
from researchgpt.graph.state import ReviewState
from researchgpt.output.writers import (
    write_bibtex,
    write_config,
    write_insight_table,
    write_markdown,
)

#: Same reducer semantics as graph/state.py. Kept in one place so the
#: sequential runner and the compiled graph cannot disagree.
_ACCUMULATE = ("papers", "chunks", "retrieval_log", "decision_log", "human_overrides")
_MERGE_DICT = ("artefacts",)


def _merge(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    for key, value in update.items():
        if key in _ACCUMULATE:
            state[key] = list(state.get(key) or []) + list(value)
        elif key in _MERGE_DICT:
            state[key] = {**(state.get(key) or {}), **value}
        else:
            state[key] = value
    return state


def make_agents(cfg: Any, llm: LLMClient, trace: TraceLogger | None):
    """The pipeline, in order. One place that knows the topology."""
    return [
        Planner(llm, cfg, trace=trace),
        Retriever(cfg, trace=trace),
        Ranker(cfg, trace=trace),
        Extractor(llm, cfg, trace=trace),
        Writer(llm, cfg, trace=trace),
    ]


def run_pipeline(
    research_question: str,
    cfg: Any,
    *,
    run_id: str | None = None,
    max_papers: int | None = None,
    write_artefacts: bool = True,
) -> ReviewState:
    """Run PLANNER -> ... -> WRITER and write the run's artefacts."""
    run_id = run_id or f"run_{uuid.uuid4().hex[:10]}"
    if max_papers is not None:
        cfg = cfg.model_copy(
            update={"review": cfg.review.model_copy(update={"max_papers": max_papers})}
        )

    trace = TraceLogger(run_id=run_id, runs_dir=cfg.output.runs_dir)
    llm = LLMClient(cfg.llm, trace=trace)
    state: dict[str, Any] = {
        "run_id": run_id,
        "research_question": research_question,
        "iteration": 0,
        "constraints": {"year_min": cfg.review.year_min,
                        "max_papers": cfg.review.max_papers},
    }

    trace.event("graph", "run_start", {"research_question": research_question,
                                       "max_papers": cfg.review.max_papers,
                                       "model": cfg.llm.model}, 0)
    try:
        for agent in make_agents(cfg, llm, trace):
            _merge(state, agent(state))

        if write_artefacts:
            state.setdefault("artefacts", {})
            run_dir = pathlib.Path(trace.run_dir)
            papers = state.get("papers") or []
            order = (state.get("artefacts") or {}).get("reference_order") or []
            by_id = {p.paper_id: p for p in papers}
            cited = [by_id[i] for i in order if i in by_id] or papers

            written = {
                "review_md": write_markdown(run_dir, state.get("final_review") or ""),
                "refs_bib": write_bibtex(run_dir, cited),
                "insights_csv": write_insight_table(
                    run_dir, papers, state.get("paper_insights") or []),
                "config_json": write_config(run_dir, cfg),
            }
            state["artefacts"].update(
                {k: str(v) for k, v in written.items() if v is not None}
            )
            trace.event("graph", "artefacts_written",
                        {k: str(v) for k, v in written.items()}, 0)

        # The Writer is fail_soft so one bad section costs a section, not the
        # run. But a run that produced NO review is a failed run, and it must
        # not exit 0 with an empty review.md. Artefacts are written first:
        # insights.csv and the trace are still worth having.
        if not (state.get("final_review") or "").strip():
            trace.event("graph", "run_failed",
                        {"reason": "no review produced; every section was rejected "
                                   "or failed. See section_rejected_uncited / "
                                   "section_failed events."}, 0)
            raise RuntimeError(
                "Pipeline produced no review. Every section was rejected or failed - "
                "check the trace for section_rejected_uncited and section_failed."
            )

        trace.event(
            "graph", "run_end",
            {"papers": len(state.get("papers") or []),
             "insights": len(state.get("paper_insights") or []),
             "sections": len(state.get("draft_sections") or {}),
             "review_chars": len(state.get("final_review") or ""),
             "llm_requests": llm.request_count, "llm_cache_hits": llm.cache_hits}, 0)
    finally:
        trace.close()

    return state  # type: ignore[return-value]


def build_graph(cfg: Any, llm: LLMClient, trace: TraceLogger | None = None):
    """The same nodes as a compiled LangGraph ``StateGraph``.

    Linear for M1. Phase 5 (T-507) adds the conditional edges from the Critic;
    the node set does not change, which is why this exists now rather than
    being retrofitted later.
    """
    from langgraph.graph import END, START, StateGraph

    agents = make_agents(cfg, llm, trace)
    graph = StateGraph(ReviewState)
    for agent in agents:
        graph.add_node(agent.name, agent)
    graph.add_edge(START, agents[0].name)
    for left, right in zip(agents, agents[1:], strict=False):
        graph.add_edge(left.name, right.name)
    graph.add_edge(agents[-1].name, END)
    return graph.compile()


__all__ = ["run_pipeline", "build_graph", "make_agents"]
