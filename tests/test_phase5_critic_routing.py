"""Phase 5 acceptance tests — the Critic (T-506) and routing (T-507).

The failure modes worth testing here are the ones that make a loop *look* like
it works: a Critic that rubber-stamps every state, a REPLAN that returns the
plan it was asked to replace, and a router that obeys a Critic asking to loop
past the bound. Each of those produces a plausible trace while doing nothing.
"""

from __future__ import annotations

import pytest

from researchgpt.agents.critic import (
    REPLAN,
    RETRIEVE,
    WRITE,
    Critic,
    coverage_report,
)
from researchgpt.core.models import Paper, SubQuestion
from researchgpt.graph.routing import (
    PlanUnchangedError,
    assert_plan_changed,
    next_iteration,
    plan_diff,
    route_after_critic,
    should_force_write,
)


class Review:
    """Minimal stand-in for cfg.review."""

    def __init__(self, min_papers=20, max_iterations=3,
                 coverage_threshold=0.8, grounding_threshold=0.7):
        self.min_papers = min_papers
        self.max_iterations = max_iterations
        self.coverage_threshold = coverage_threshold
        self.grounding_threshold = grounding_threshold


class Cfg:
    def __init__(self, **kw):
        self.review = Review(**kw)


def paper(pid):
    return Paper(paper_id=pid, title=f"Paper {pid}", source="openalex")


def sq(sq_id, facet="method"):
    return SubQuestion(sq_id=sq_id, text=f"question {sq_id}", facet=facet)


def log(sq_id, new):
    return {"sq_id": sq_id, "query": "q", "source": "openalex", "new": new}


def critic_state(**kw):
    base = {
        "iteration": 0,
        "papers": [paper(f"p{i}") for i in range(25)],
        "sub_questions": [sq("SQ1"), sq("SQ2")],
        "retrieval_log": [log("SQ1", 5), log("SQ2", 5)],
        "decision_log": [],
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# T-506 — coverage and the gates
# --------------------------------------------------------------------------


def test_coverage_counts_papers_per_sub_question():
    report = coverage_report(
        [sq("SQ1"), sq("SQ2")], [log("SQ1", 3), log("SQ1", 1), log("SQ2", 1)]
    )
    assert report["per_sub_question"]["SQ1"]["papers"] == 4
    assert report["per_sub_question"]["SQ1"]["covered"] is True
    # SPEC 7.5: fewer than 2 supporting papers is uncovered.
    assert report["per_sub_question"]["SQ2"]["covered"] is False
    assert report["uncovered"] == ["SQ2"]
    assert report["coverage"] == 0.5


def test_critic_writes_when_every_gate_passes():
    out = Critic(Cfg()).run(critic_state(grounding_score=0.9))
    assert out["decision"] == WRITE


def test_critic_retrieves_when_the_corpus_is_too_small():
    out = Critic(Cfg()).run(critic_state(papers=[paper("p1")]))
    assert out["decision"] == RETRIEVE
    assert "below min_papers" in out["critic_feedback"]


def test_critic_retrieves_on_an_under_covered_sub_question():
    out = Critic(Cfg()).run(critic_state(retrieval_log=[log("SQ1", 5), log("SQ2", 1)]))
    assert out["decision"] == RETRIEVE
    assert "SQ2" in out["critic_feedback"]


def test_critic_escalates_to_replan_only_after_a_retrieve_failed():
    """Replanning before searching harder throws away a plan that may only have
    needed more results - and a replan costs the Planner's tokens."""
    state = critic_state(
        retrieval_log=[log("SQ1", 5), log("SQ2", 1)],
        decision_log=[{"iteration": 0, "decision": RETRIEVE}],
    )
    out = Critic(Cfg()).run(state)
    assert out["decision"] == REPLAN
    assert "did not close the gap" in out["critic_feedback"]


def test_critic_retrieves_when_grounding_is_below_threshold():
    out = Critic(Cfg()).run(critic_state(grounding_score=0.30))
    assert out["decision"] == RETRIEVE
    assert "grounding" in out["critic_feedback"]


def test_grounding_gate_is_skipped_before_the_first_draft():
    """There is no draft on the first pass, so grounding is None. Treating that
    as 0.0 would force a pointless RETRIEVE on every single run."""
    out = Critic(Cfg()).run(critic_state(grounding_score=None))
    assert out["decision"] == WRITE


def test_critic_forces_write_on_the_final_iteration():
    """SPEC 7.5: force WRITE and record unresolved gaps in a Limitations
    section rather than looping forever."""
    state = critic_state(
        iteration=2, papers=[paper("p1")], retrieval_log=[log("SQ1", 0), log("SQ2", 0)]
    )
    out = Critic(Cfg(max_iterations=3)).run(state)
    assert out["decision"] == WRITE
    assert "forcing WRITE" in out["critic_feedback"]
    assert "carried into Limitations" in out["critic_feedback"]


def test_critic_logs_every_decision_for_after_the_fact_diagnosis():
    out = Critic(Cfg()).run(critic_state(grounding_score=0.9))
    assert len(out["decision_log"]) == 1
    entry = out["decision_log"][0]
    assert entry["decision"] == WRITE
    assert "coverage" in entry and "reasons" in entry


def test_critic_makes_no_llm_call():
    """Deterministic by design: a loop that spends tokens deciding whether to
    spend tokens is the worst possible place for a generative call, and an LLM
    router turns an oscillating loop into an unreproducible bug."""
    import inspect

    import researchgpt.agents.critic as critic_module

    source = inspect.getsource(critic_module)
    assert "self._llm" not in source
    assert "LLMClient" not in source


def test_critic_returns_only_keys_it_owns():
    out = Critic(Cfg()).run(critic_state(grounding_score=0.9))
    assert set(out) == {"decision", "critic_feedback", "coverage_report",
                        "decision_log"}


# --------------------------------------------------------------------------
# T-507 — routing
# --------------------------------------------------------------------------


def test_routes_follow_the_critic_when_inside_the_bound():
    assert route_after_critic({"decision": WRITE, "iteration": 0}) == "writer"
    assert route_after_critic({"decision": RETRIEVE, "iteration": 0}) == "retriever"
    assert route_after_critic({"decision": REPLAN, "iteration": 0}) == "planner"


def test_routing_overrides_a_critic_that_asks_to_loop_past_the_cap():
    """A second, independent guard. The Critic's cap is policy; this one is the
    safety bound that keeps the graph terminating if a gate above it is wrong."""
    assert route_after_critic({"decision": RETRIEVE, "iteration": 2},
                              max_iterations=3) == "writer"
    assert route_after_critic({"decision": REPLAN, "iteration": 5},
                              max_iterations=3) == "writer"


def test_unknown_decision_writes_rather_than_loops():
    assert route_after_critic({"decision": "MAYBE", "iteration": 0}) == "writer"
    assert route_after_critic({"iteration": 0}) == "writer"


def test_should_force_write_distinguishes_the_cap_from_a_real_write():
    """The Writer needs to know, so unresolved gaps reach Limitations instead
    of vanishing because the loop ran out."""
    assert should_force_write({"decision": RETRIEVE, "iteration": 2}) is True
    assert should_force_write({"decision": WRITE, "iteration": 2}) is False
    assert should_force_write({"decision": RETRIEVE, "iteration": 0}) is False


def test_iteration_counter_is_monotonic():
    assert next_iteration({"iteration": 0}) == 1
    assert next_iteration({}) == 1
    assert next_iteration({"iteration": 7}) == 8


def test_plan_diff_detects_a_real_replan():
    before = {"sub_questions": [sq("SQ1")], "search_plan": [], "inclusion_criteria": []}
    after = {"sub_questions": [sq("SQ1"), sq("SQ2")], "search_plan": [],
             "inclusion_criteria": []}
    diff = assert_plan_changed(before, after)
    assert diff["changed"] is True
    assert diff["sub_questions"]["added"] == ["question SQ2"]


def test_replan_that_changes_nothing_is_refused():
    """It would repeat the same searches and reach the same verdict, spending
    an iteration and a Planner call to stand still."""
    before = {"sub_questions": [sq("SQ1")], "search_plan": [], "inclusion_criteria": []}
    after = {"sub_questions": [sq("SQ1")], "search_plan": [], "inclusion_criteria": []}
    assert plan_diff(before, after)["changed"] is False
    with pytest.raises(PlanUnchangedError, match="identical plan"):
        assert_plan_changed(before, after)


def test_rebuilt_but_equal_plan_objects_count_as_unchanged():
    """The Planner rebuilds these objects on every pass, so identity comparison
    would report a change on every replan and defeat the guard entirely."""
    before = {"sub_questions": [sq("SQ1")], "search_plan": [], "inclusion_criteria": []}
    after = {"sub_questions": [sq("SQ1")], "search_plan": [], "inclusion_criteria": []}
    assert before["sub_questions"][0] is not after["sub_questions"][0]
    assert plan_diff(before, after)["changed"] is False


def test_loop_fires_on_an_under_covered_query_and_terminates():
    """T-507's acceptance criterion, as a bounded simulation.

    A corpus that never improves would loop forever without the cap. This
    asserts BOTH halves: that the loop actually fires (the Critic is not
    rubber-stamping) and that it stops.
    """
    cfg = Cfg(max_iterations=3)
    state = critic_state(retrieval_log=[log("SQ1", 5), log("SQ2", 0)])
    routes = []

    for _ in range(10):                       # far more passes than allowed
        out = Critic(cfg).run(state)
        # The Critic owns the counter and advances it on a loop-back, so the
        # harness must NOT also increment: doing so double-counted and halved
        # the observable loop budget.
        state = {**state, **out,
                 "decision_log": state["decision_log"] + out["decision_log"]}
        routes.append(route_after_critic(state, cfg.review.max_iterations))
        if routes[-1] == "writer":
            break

    assert routes[0] != "writer", "the loop never fired on an under-covered query"
    assert routes[-1] == "writer", "the loop did not terminate"
    assert len(routes) <= cfg.review.max_iterations, f"ran {len(routes)} iterations"
    # It must have tried RETRIEVE and then escalated, not sat on one verdict.
    decisions = [d["decision"] for d in state["decision_log"]]
    assert RETRIEVE in decisions and REPLAN in decisions, decisions


# --------------------------------------------------------------------------
# T-507 / T-509 — the loop terminates, and the graph has the shape it claims
# --------------------------------------------------------------------------


def test_write_ends_the_loop_once_a_verified_draft_exists():
    """The Critic is reached twice per iteration: once after the Extractor, and
    again after the Verifier. Without this the second visit routes back to the
    Writer and loops writer -> verifier -> critic -> writer forever inside one
    iteration."""
    from researchgpt.graph.routing import END_NODE

    before = {"decision": WRITE, "iteration": 0}
    after = {"decision": WRITE, "iteration": 0, "final_review": "# A review"}
    assert route_after_critic(before) == "writer"
    assert route_after_critic(after) == END_NODE


def test_the_cap_ends_rather_than_rewrites_when_a_draft_exists():
    from researchgpt.graph.routing import END_NODE

    state = {"decision": RETRIEVE, "iteration": 2, "final_review": "# A review"}
    assert route_after_critic(state, max_iterations=3) == END_NODE


def test_writer_verifier_critic_cannot_spin_inside_one_iteration():
    """Simulate the post-Writer half of the loop with a Critic that is happy.

    If routing sent WRITE back to the writer this would not terminate.
    """
    from researchgpt.graph.routing import END_NODE

    cfg = Cfg(max_iterations=3)
    state = critic_state(grounding_score=0.95, final_review="# A review")
    seen = []
    for _ in range(6):
        out = Critic(cfg).run(state)
        state = {**state, **out}
        seen.append(route_after_critic(state, cfg.review.max_iterations))
        if seen[-1] == END_NODE:
            break
    assert seen[-1] == END_NODE
    assert seen.count("writer") == 0, "re-entered the Writer with a draft in hand"


def test_loop_graph_has_all_six_agents_plus_the_rank_stage():
    """T-509's structural half: the graph really contains the agents the
    'six-agent' claim names, wired as a loop rather than a line."""
    pytest.importorskip("langgraph")
    from researchgpt.core.config import load_config
    from researchgpt.core.llm import LLMClient
    from researchgpt.graph.build import build_loop_graph, make_verifier

    cfg = load_config("configs/default.yaml")
    if make_verifier(cfg) is None:
        pytest.skip("verifier ONNX model not exported in this checkout")

    graph = build_loop_graph(cfg, LLMClient(cfg.llm)).get_graph()
    nodes = {n for n in graph.nodes if not n.startswith("__")}
    assert nodes == {"planner", "retriever", "ranker", "extractor",
                     "writer", "verifier", "critic"}

    edges = {(e.source, e.target) for e in graph.edges}
    # The loop-back edges are what make this a graph and not a pipeline.
    assert ("extractor", "critic") in edges
    assert ("verifier", "critic") in edges
    assert any(src == "critic" and dst == "retriever" for src, dst in edges)
    assert any(src == "critic" and dst == "planner" for src, dst in edges)


def test_loop_graph_refuses_to_build_without_the_verifier():
    """A six-agent graph missing the graded agent is not the thing it claims.

    build_graph() tolerates a missing model because M1 does not depend on
    verification; this one must not.
    """
    pytest.importorskip("langgraph")
    from researchgpt.core.config import load_config
    from researchgpt.core.llm import LLMClient
    from researchgpt.graph.build import build_loop_graph

    cfg = load_config("configs/default.yaml")
    broken = cfg.model_copy(
        update={"verifier": cfg.verifier.model_copy(
            update={"onnx_path": "data/models/does-not-exist"})}
    )
    with pytest.raises(FileNotFoundError, match="verifier model"):
        build_loop_graph(broken, LLMClient(cfg.llm))


def test_iteration_advances_only_on_a_loop_back():
    """The counter is the only thing between a Critic that keeps asking for
    more evidence and an unbounded spend against a metered API.

    Nothing in the compiled graph was incrementing it, so both the Critic's cap
    and routing's safety bound compared against a permanently-zero iteration
    and could never fire. It advances on RETRIEVE/REPLAN only: the Critic is
    visited twice per iteration, and counting both visits would halve the real
    budget.
    """
    looping = Critic(Cfg()).run(critic_state(papers=[paper("p1")]))
    assert looping["decision"] == RETRIEVE
    assert looping["iteration"] == 1

    settled = Critic(Cfg()).run(critic_state(grounding_score=0.9))
    assert settled["decision"] == WRITE
    assert "iteration" not in settled, (
        "a WRITE must not advance the counter; the Critic is visited twice per "
        "iteration and double-counting would halve the loop budget"
    )
