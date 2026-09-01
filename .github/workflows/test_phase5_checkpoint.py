"""T-508 acceptance tests — SQLite checkpointing and resume.

The claim under test is narrow and worth stating precisely: a run that dies
part-way resumes **after the last completed node**, not from the Planner. The
tests therefore assert what was *skipped*, not merely that a second invocation
returns something — a graph that silently re-ran everything would also return
something.
"""

from __future__ import annotations

import pathlib
import sqlite3

import pytest

from researchgpt.graph.checkpoint import (
    DEFAULT_CHECKPOINT_DB,
    checkpointer,
    latest_state,
    resumable_runs,
    resume_report,
    thread_config,
)
from researchgpt.graph.state import ReviewState

pytest.importorskip("langgraph")


def crashing_graph(calls: list[str], fail: dict):
    """Two nodes; the second raises until ``fail['on']`` is cleared."""
    from langgraph.graph import END, START, StateGraph

    def planner(state):
        calls.append("planner")
        return {"sub_questions": [], "research_question": "Q"}

    def writer(state):
        calls.append("writer")
        if fail["on"]:
            raise RuntimeError("simulated mid-run crash")
        return {"final_review": "# A review"}

    graph = StateGraph(ReviewState)
    graph.add_node("planner", planner)
    graph.add_node("writer", writer)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "writer")
    graph.add_edge("writer", END)
    return graph


def test_thread_id_is_the_run_id():
    """So the checkpoint and outputs/runs/<run_id>/ name the same run, and a
    resumable run can be found from its artefacts and vice versa."""
    assert thread_config("abc123")["configurable"]["thread_id"] == "abc123"
    assert thread_config("abc", extra=1)["configurable"]["extra"] == 1


def test_a_crashed_run_resumes_without_repeating_completed_nodes(tmp_path):
    """T-508's acceptance criterion, and the only one that matters."""
    calls: list[str] = []
    fail = {"on": True}
    saver = checkpointer(tmp_path / "cp.sqlite")
    app = crashing_graph(calls, fail).compile(checkpointer=saver)
    config = thread_config("run-1")

    with pytest.raises(RuntimeError, match="simulated"):
        app.invoke({"run_id": "run-1"}, config=config)
    assert calls == ["planner", "writer"]

    fail["on"] = False
    out = app.invoke(None, config=config)      # None = continue from checkpoint

    assert out["final_review"] == "# A review"
    assert calls.count("planner") == 1, (
        "the planner re-ran on resume; the checkpoint bought nothing"
    )
    assert calls.count("writer") == 2


def test_resume_report_names_the_stages_that_would_be_skipped(tmp_path):
    """Quantities, not a boolean. "resumable" does not tell an operator whether
    resuming is worth it or whether this is the checkpoint they meant."""
    calls: list[str] = []
    fail = {"on": True}
    saver = checkpointer(tmp_path / "cp.sqlite")
    app = crashing_graph(calls, fail).compile(checkpointer=saver)

    assert resume_report(saver, "run-2")["resumable"] is False

    with pytest.raises(RuntimeError):
        app.invoke({"run_id": "run-2"}, config=thread_config("run-2"))

    report = resume_report(saver, "run-2")
    assert report["resumable"] is True
    # The planner ran and wrote sub_questions - even though it wrote an EMPTY
    # list. Keying this on truthiness reported resumable=True with skips=[],
    # a contradiction an operator would not trust.
    assert "planner" in report["skips"]
    assert "writer" not in report["skips"]


def test_an_empty_but_written_field_still_counts_as_a_completed_stage(tmp_path):
    saver = checkpointer(tmp_path / "cp.sqlite")
    calls: list[str] = []
    app = crashing_graph(calls, {"on": True}).compile(checkpointer=saver)
    with pytest.raises(RuntimeError):
        app.invoke({"run_id": "run-3"}, config=thread_config("run-3"))

    state = latest_state(saver, "run-3")
    assert state is not None
    assert state.get("sub_questions") == []          # empty, but written
    assert "planner" in resume_report(saver, "run-3")["skips"]


def test_resumable_runs_lists_every_thread_not_one(tmp_path):
    """The saver's own list() enumerates checkpoints for ONE thread - the
    opposite of what "which runs can I resume?" asks."""
    db = tmp_path / "cp.sqlite"
    saver = checkpointer(db)
    app = crashing_graph([], {"on": True}).compile(checkpointer=saver)
    for run_id in ("run-a", "run-b"):
        with pytest.raises(RuntimeError):
            app.invoke({"run_id": run_id}, config=thread_config(run_id))

    assert set(resumable_runs(db)) == {"run-a", "run-b"}


def test_resumable_runs_is_safe_on_a_missing_or_empty_database(tmp_path):
    assert resumable_runs(tmp_path / "nope.sqlite") == []
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(str(empty)).close()
    assert resumable_runs(empty) == []


def test_checkpointer_creates_its_parent_directory(tmp_path):
    path = tmp_path / "nested" / "deeper" / "cp.sqlite"
    checkpointer(path)
    assert path.parent.is_dir()


def test_default_database_is_one_file_for_all_runs():
    """A file per run would scatter hundreds of tiny SQLite files through
    outputs/ and make "what can I resume?" un-answerable without globbing."""
    assert DEFAULT_CHECKPOINT_DB == pathlib.Path("outputs/runs/checkpoints.sqlite")


def test_loop_graph_accepts_a_checkpointer():
    """T-508 has to reach the graph that actually runs, not just exist."""
    import inspect

    from researchgpt.graph.build import build_loop_graph

    assert "checkpointer" in inspect.signature(build_loop_graph).parameters
