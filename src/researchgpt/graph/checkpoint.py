"""T-508 — SQLite checkpointing, so a run can resume instead of restarting.

`SPEC §14.10`. A run is checkpointed after **every node**, keyed by ``run_id``,
into one SQLite file. Re-invoking the graph with the same ``run_id`` picks up
after the last completed node instead of starting from the Planner.

★ **Why this matters more than it did when it was specified.** T-508 was
written as a nice-to-have. On 2026-08-28 four T-409 attempts died mid-run and
each restart re-paid for everything: ~35 s of retrieval, ~6 minutes of CPU
reranking, and — worse — a fresh slice of a 200,000-token **daily** budget that
was ultimately exhausted on *both* available models. Resuming is the difference
between a lost afternoon and a five-minute top-up.

⚠️ **Know exactly what this recovers, because the honest answer is "not the
thing that actually broke".** LangGraph checkpoints **between nodes**, not
inside one. The Extractor is a single node, so a run that dies at paper 18 of
25 resumes at the *start* of extraction, not at paper 18.

What makes resume genuinely cheap is the pairing:

===========================  ==========================================
checkpoint (this module)     skips Planner / Retriever / Ranker —
                             ~6-7 minutes of CPU and network, and the
                             OpenAlex request budget
LLM prompt cache (T-104)     skips extractions already completed, at
                             **zero tokens**, because a re-run hashes to
                             the same prompts
===========================  ==========================================

Together they give real resume. Neither does on its own, and it is worth saying
so in the report rather than claiming node-level checkpointing solves a
mid-node failure.

⚠️ **The cache pairing is only free while the request is identical.** The cache
key includes model, temperature, ``max_tokens`` and ``reasoning_effort``, so
changing any of them — as the 2026-08-28 debugging did, repeatedly — invalidates
it and a "resumed" run re-pays for every extraction. That is correct behaviour,
not a bug: a different ``max_tokens`` is a different request. Just do not expect
resume to be free across a config change.
"""

from __future__ import annotations

import pathlib
import sqlite3
from typing import Any

#: One database for every run, keyed by ``thread_id`` (= ``run_id``). A file
#: per run would scatter hundreds of tiny SQLite files through outputs/ and
#: make "what can I resume?" un-answerable without globbing.
DEFAULT_CHECKPOINT_DB = pathlib.Path("outputs/runs/checkpoints.sqlite")


def checkpointer(path: str | pathlib.Path = DEFAULT_CHECKPOINT_DB) -> Any:
    """A ``SqliteSaver`` on ``path``, ready to pass to ``compile()``.

    ``check_same_thread=False`` is required: LangGraph may touch the connection
    from a worker thread, and the default sqlite3 guard raises there. This is
    safe for our single-writer usage — one process, one run at a time.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    return SqliteSaver(conn)


def thread_config(run_id: str, **extra: Any) -> dict[str, Any]:
    """The config a checkpointed invocation needs.

    ``thread_id`` is the ``run_id``, deliberately: the checkpoint and
    ``outputs/runs/<run_id>/`` then name the same run, so a resumable run can be
    found from its artefacts and vice versa.
    """
    configurable = {"thread_id": run_id}
    configurable.update(extra)
    return {"configurable": configurable}


def resume_input(saver: Any, config: dict[str, Any], state: dict[str, Any]):
    """What to pass as ``invoke``'s input: ``None`` to resume, else the state.

    🔴 This is the half of T-508 that was missing, and its absence made the
    whole feature inert on the real path. LangGraph resumes a thread only when
    invoked with ``None``; given an input it records a fresh ``input``
    checkpoint and re-runs the graph from START.

    Measured 2026-08-29 - the checkpoint table after a "resume":

        step -1  source: input      first attempt
        step  0  loop               planner
        step  1  loop               retriever
        step  2  loop               ranker (died)
        step  3  source: input      <- the resume, starting over
        step  4  loop               planner AGAIN
        step  5  loop               retriever AGAIN

    So the docstring's promise - "picks up after the last completed node
    instead of starting from the Planner" - was false while the checkpointer
    itself worked perfectly and wrote every checkpoint. It cost a re-paid
    retrieval, and the replay then crashed the retriever against a state that
    already held its own results.
    """
    try:
        existing = saver.get_tuple(config)
    except Exception:
        return state
    return None if existing is not None else state


def latest_state(saver: Any, run_id: str) -> dict[str, Any] | None:
    """The most recent checkpointed state for ``run_id``, or ``None``."""
    tuple_ = saver.get_tuple(thread_config(run_id))
    if tuple_ is None:
        return None
    values = tuple_.checkpoint.get("channel_values") or {}
    return dict(values)


def resume_report(saver: Any, run_id: str) -> dict[str, Any]:
    """What a resume would skip. For the CLI and for the trace.

    Deliberately reports *quantities*, not a boolean: "resumable" is not very
    useful, whereas "417 papers and 20 insights already held" tells you whether
    resuming is worth it and whether the checkpoint is the one you meant.
    """
    state = latest_state(saver, run_id)
    if state is None:
        return {"resumable": False, "run_id": run_id}

    return {
        "resumable": True,
        "run_id": run_id,
        "iteration": state.get("iteration", 0),
        "papers": len(state.get("papers") or []),
        "chunks": len(state.get("chunks") or []),
        "insights": len(state.get("paper_insights") or []),
        "verified_claims": len(state.get("verified_claims") or []),
        "dropped_claims": len(state.get("unsupported_claims") or []),
        "has_draft": bool(state.get("final_review")),
        "decision": state.get("decision"),
        # The expensive stages, named so the operator can see what is saved.
        #
        # Keyed on the field being PRESENT, not on it being truthy. A node that
        # ran and legitimately produced an empty list has still run, and
        # re-running it would re-pay its cost for nothing - which is the whole
        # point of the checkpoint. Truthiness reported `resumable: True` with an
        # empty `skips`, which is a contradiction an operator would not trust.
        "skips": [
            stage
            for stage, field in (
                ("planner", "sub_questions"),
                ("retriever", "papers"),
                ("ranker", "chunks"),
                ("extractor", "paper_insights"),
                ("writer", "final_review"),
            )
            if state.get(field) is not None
        ],
    }


def resumable_runs(path: str | pathlib.Path = DEFAULT_CHECKPOINT_DB) -> list[str]:
    """Every ``run_id`` with at least one checkpoint, newest first.

    Read straight from the checkpoint table rather than through the saver's
    ``list()``, which enumerates checkpoints for **one** thread — the opposite
    of what "which runs can I resume?" asks.
    """
    path = pathlib.Path(path)
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    try:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "checkpoints" not in names:
            return []
        rows = conn.execute(
            "SELECT thread_id, MAX(rowid) AS r FROM checkpoints "
            "GROUP BY thread_id ORDER BY r DESC"
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


__all__ = [
    "DEFAULT_CHECKPOINT_DB",
    "resume_input",
    "checkpointer",
    "thread_config",
    "latest_state",
    "resume_report",
    "resumable_runs",
]
