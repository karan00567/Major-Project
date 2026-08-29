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

import hashlib
import pathlib
import uuid
from typing import Any

from researchgpt.agents.critic import Critic
from researchgpt.agents.extractor import Extractor
from researchgpt.agents.planner import Planner
from researchgpt.agents.ranker import Ranker
from researchgpt.agents.retriever import Retriever
from researchgpt.agents.verifier import Verifier, VerifierModel
from researchgpt.agents.writer import Writer
from researchgpt.core.llm import LLMClient
from researchgpt.core.logging import TraceLogger
from researchgpt.graph.routing import END_NODE, route_after_critic
from researchgpt.graph.state import ReviewState
from researchgpt.output.writers import (
    write_bibtex,
    write_claims,
    write_config,
    write_corpus,
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
    use_loop: bool = False,
) -> ReviewState:
    """Run the pipeline and write the run's artefacts.

    ``use_loop=False`` runs the five-agent line that landed M1 - the insurance
    policy, no dependency on the Verifier's model artefact.

    ``use_loop=True`` runs the full six-agent graph from
    :func:`build_loop_graph`: Verifier and Critic included, with the loop able
    to fire and terminate. That is T-509 / M2. Artefact writing is shared, so
    the two paths cannot produce differently-shaped output.
    """
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

    # T-624 — registry hooks. Every call is best-effort and returns None when
    # there is no database (DB_SCHEMA 9), so this block cannot affect the run.
    from researchgpt.db import registry

    registry.register_run(run_id, research_question, cfg.model_dump())
    registry.mark_running(run_id)

    trace.event("graph", "run_start", {"research_question": research_question,
                                       "max_papers": cfg.review.max_papers,
                                       "model": cfg.llm.model}, 0)
    try:
        if use_loop:
            # LangGraph applies the graph/state.py reducers itself, so no
            # _merge here - and a recursion_limit well above max_iterations so
            # the loop's own bound is what stops it, not the framework's.
            # 🔴 T-508 was inert until 2026-08-28: build_loop_graph grew a
            # `checkpointer=` parameter and tests for it, but this call site
            # never passed one, so no checkpoint was ever written on the real
            # path. A feature reachable only from its own tests is not shipped.
            from researchgpt.graph.checkpoint import checkpointer as _checkpointer
            from researchgpt.graph.checkpoint import resume_input, thread_config

            saver = _checkpointer()
            app = build_loop_graph(cfg, llm, trace, checkpointer=saver)
            config = thread_config(run_id)
            # The loop's own bound (review.max_iterations, enforced twice) is
            # what should stop this, not LangGraph's recursion guard.
            config["recursion_limit"] = 50
            # 🔴 The other half of T-508. Passing `state` here on a thread that
            # already has checkpoints re-runs the graph from START; only None
            # resumes. See checkpoint.resume_input.
            state = dict(app.invoke(resume_input(saver, config, state), config=config))
        else:
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
                "corpus_json": write_corpus(
                    run_dir, papers,
                    [i.paper_id for i in state.get("paper_insights") or []],
                    state.get("retrieval_log") or []),
                "claims_json": write_claims(
                    run_dir,
                    state.get("verified_claims") or [],
                    state.get("unsupported_claims") or [],
                    state.get("grounding_score"),
                ),
                "config_json": write_config(run_dir, cfg),
            }
            state["artefacts"].update(
                {k: str(v) for k, v in written.items() if v is not None}
            )
            # Attach each artefact with its size and digest, so the registry can
            # answer "which run produced this file, and is it intact?".
            for name, path in written.items():
                if path is None:
                    continue
                try:
                    blob = pathlib.Path(path).read_bytes()
                    digest = hashlib.sha256(blob).hexdigest()
                    size = len(blob)
                except OSError:
                    digest, size = None, None
                registry.attach_artefact(run_id, pathlib.Path(path).name,
                                         str(path), size, digest)
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
            registry.fail_run(run_id, "no review produced; every section was "
                                      "rejected or failed")
            raise RuntimeError(
                "Pipeline produced no review. Every section was rejected or failed - "
                "check the trace for section_rejected_uncited and section_failed."
            )

        registry.complete_run(run_id, {
            "papers": len(state.get("papers") or []),
            "insights": len(state.get("paper_insights") or []),
            "verified_claims": len(state.get("verified_claims") or []),
            "dropped_claims": len(state.get("unsupported_claims") or []),
            "grounding_score": state.get("grounding_score"),
            "iterations": state.get("iteration", 0),
            "decisions": [d.get("decision")
                          for d in (state.get("decision_log") or [])],
        })
        trace.event(
            "graph", "run_end",
            {"papers": len(state.get("papers") or []),
             "insights": len(state.get("paper_insights") or []),
             "sections": len(state.get("draft_sections") or {}),
             "review_chars": len(state.get("final_review") or ""),
             "verified_claims": len(state.get("verified_claims") or []),
             "dropped_claims": len(state.get("unsupported_claims") or []),
             "grounding_score": state.get("grounding_score"),
             "iterations": state.get("iteration", 0),
             "decisions": [d.get("decision")
                           for d in (state.get("decision_log") or [])],
             "llm_requests": llm.request_count, "llm_cache_hits": llm.cache_hits}, 0)
    finally:
        trace.close()

    return state  # type: ignore[return-value]


def make_verifier(cfg: Any, trace: TraceLogger | None = None) -> Verifier | None:
    """The Verifier, or ``None`` if its ONNX model has not been exported.

    Returning ``None`` rather than raising keeps M1's linear pipeline runnable
    in a checkout that has never run T-304 - the survey does not depend on
    verification, and a missing 23 MB artefact should not make the whole
    project unusable. :func:`build_loop_graph` raises instead, because a
    "six-agent graph" missing the graded agent is not the thing it claims.
    """
    try:
        model = VerifierModel(cfg.verifier.onnx_path, cfg.verifier.tokenizer)
    except Exception:
        return None
    return Verifier(model, cfg, trace=trace)


def build_graph(cfg: Any, llm: LLMClient, trace: TraceLogger | None = None):
    """The M1 nodes as a compiled LangGraph ``StateGraph``, linear.

    Kept because M1 is the insurance policy: a straight line that produces a
    cited survey, with no dependency on the Verifier's model artefact.
    :func:`build_loop_graph` is the Phase 5 topology.
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


def build_loop_graph(
    cfg: Any,
    llm: LLMClient,
    trace: TraceLogger | None = None,
    checkpointer: Any = None,
):
    """T-507 / T-509 — the six-agent graph with the Critic loop.

    Topology, and why it is this shape::

        START -> planner -> retriever -> ranker -> extractor -> critic
        critic --RETRIEVE--> retriever          (search harder)
        critic --REPLAN----> planner            (the plan itself is wrong)
        critic --WRITE-----> writer -> verifier -> critic
        critic --WRITE-----> END                (once a verified draft exists)

    ★ **The Critic is visited twice per iteration, deliberately.** Its cheap
    gates - corpus size and per-sub-question coverage - run *before* the Writer
    spends four sections' worth of tokens on a corpus that cannot support them.
    Its grounding gate only has a ``grounding_score`` to read after the
    Verifier, so it is reached again from there. Routing distinguishes the two
    visits by the presence of ``final_review``; without that the second visit
    would loop ``writer -> verifier -> critic -> writer`` forever inside one
    iteration.

    ⚠️ **The Verifier is required here.** ``build_graph`` tolerates a missing
    model because M1 does not depend on verification; this graph does not,
    because a six-agent graph missing the graded agent is not the thing it
    claims to be.

    Pass ``checkpointer=graph.checkpoint.checkpointer()`` (T-508) to make the
    run resumable. Invoke with ``config=thread_config(run_id)``; re-invoking
    with the same ``run_id`` continues after the last completed node instead of
    restarting from the Planner.
    """
    from langgraph.graph import END, START, StateGraph

    planner, retriever, ranker, extractor, writer = make_agents(cfg, llm, trace)
    critic = Critic(cfg, trace=trace)
    verifier = make_verifier(cfg, trace=trace)
    if verifier is None:
        raise FileNotFoundError(
            f"The Critic loop needs the verifier model, and "
            f"{cfg.verifier.onnx_path!r} could not be loaded. Export it with "
            f"`python -m researchgpt.verify.export_onnx --checkpoint "
            f"data/models/verifier-scifact` (T-304), or use build_graph() for "
            f"the linear M1 pipeline."
        )

    max_iterations = cfg.review.max_iterations
    graph = StateGraph(ReviewState)
    for agent in (planner, retriever, ranker, extractor, writer, verifier, critic):
        graph.add_node(agent.name, agent)

    graph.add_edge(START, planner.name)
    graph.add_edge(planner.name, retriever.name)
    graph.add_edge(retriever.name, ranker.name)
    graph.add_edge(ranker.name, extractor.name)
    graph.add_edge(extractor.name, critic.name)
    graph.add_edge(writer.name, verifier.name)
    graph.add_edge(verifier.name, critic.name)

    def _route(state: ReviewState) -> str:
        return route_after_critic(state, max_iterations)

    graph.add_conditional_edges(
        critic.name,
        _route,
        {
            "retriever": retriever.name,
            "planner": planner.name,
            "writer": writer.name,
            END_NODE: END,
        },
    )
    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "run_pipeline",
    "build_graph",
    "build_loop_graph",
    "make_agents",
    "make_verifier",
]
