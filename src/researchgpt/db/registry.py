"""T-623 — the run registry. `DB_SCHEMA.md §9`.

★ **Every public function here is best-effort and returns ``None`` on failure.
Not one of them may raise.** `DB_SCHEMA.md §9` states the rule and T-626 is the
test that proves it: *stop the Postgres service mid-run and confirm the run
still completes with every artefact on disk.* A pipeline run costs minutes and,
on a metered free tier, a slice of a daily token budget — losing one because an
index of it could not be updated would be absurd.

The wrapper is deliberately broad. A narrow ``except OperationalError`` would
miss the failures that actually happen on a laptop: a driver missing from the
environment, a malformed URL, a suspended machine, a database that exists but
whose table does not.

⚠️ **The registry is derived data.** `DB_SCHEMA.md §1`: the filesystem is the
record, every run is reconstructible from ``outputs/runs/``, and `T-625` makes
``GET /api/runs`` fall back to scanning it. Nothing here may become the only
copy of anything.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from researchgpt.db.session import enabled, get_session

log = logging.getLogger(__name__)


def _safe(fn, *args, **kwargs):
    """A registry failure must never break a run. `DB_SCHEMA.md §9`."""
    if not enabled():
        return None
    try:
        return fn(*args, **kwargs)
    except Exception as exc:            # deliberately broad — see module docstring
        log.warning("run registry unavailable: %s", exc)
        return None


def _with_session(work):
    session = get_session()
    if session is None:
        return None
    try:
        result = work(session)
        session.commit()
        return result
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            session.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# public API — all best-effort
# --------------------------------------------------------------------------


def register_run(run_id: str, question: str, config: dict[str, Any] | None = None):
    """Insert a ``pending`` row. Idempotent on ``run_id``."""
    def work(session):
        from researchgpt.db.models import Run

        existing = session.query(Run).filter_by(run_id=run_id).one_or_none()
        if existing is not None:
            return existing.run_id
        session.add(Run(run_id=run_id, research_question=question,
                        config=dict(config or {}), status="pending"))
        return run_id

    return _safe(_with_session, work)


def mark_running(run_id: str):
    def work(session):
        from researchgpt.db.models import Run

        row = session.query(Run).filter_by(run_id=run_id).one_or_none()
        if row is None:
            return None
        row.status = "running"
        return run_id

    return _safe(_with_session, work)


def attach_artefact(run_id: str, name: str, path: str,
                    size_bytes: int | None = None, sha256: str | None = None):
    """Append one artefact record. `DB_SCHEMA.md §4`.

    🔴 The append relies on ``MutableList`` in models.py. Without it this
    mutates a plain list, SQLAlchemy never marks the row dirty, no UPDATE is
    emitted, and the artefact vanishes with no error at all.
    """
    def work(session):
        from researchgpt.db.models import Run

        row = session.query(Run).filter_by(run_id=run_id).one_or_none()
        if row is None:
            return None
        row.artefacts.append({
            "name": name,
            "path": str(path),
            "bytes": size_bytes,
            "sha256": sha256,
        })
        return name

    return _safe(_with_session, work)


def complete_run(run_id: str, metrics: dict[str, Any] | None = None):
    def work(session):
        from researchgpt.db.models import Run

        row = session.query(Run).filter_by(run_id=run_id).one_or_none()
        if row is None:
            return None
        row.status = "completed"
        row.metrics = dict(metrics or {})
        row.completed_at = datetime.now(UTC)
        return run_id

    return _safe(_with_session, work)


def fail_run(run_id: str, error: str):
    def work(session):
        from researchgpt.db.models import Run

        row = session.query(Run).filter_by(run_id=run_id).one_or_none()
        if row is None:
            return None
        row.status = "failed"
        # Truncated: a full traceback belongs in the trace, not in an index.
        row.error = (error or "")[:4000]
        row.completed_at = datetime.now(UTC)
        return run_id

    return _safe(_with_session, work)


def list_runs(limit: int = 50) -> list[dict[str, Any]] | None:
    """Summaries newest first, or ``None`` when the registry is unavailable.

    ``None`` rather than ``[]``, deliberately: the caller must be able to tell
    "the registry is not there, fall back to the filesystem" (T-625) from "the
    registry is there and genuinely has no runs". Returning ``[]`` for both
    would make an empty database look like an empty disk.
    """
    def work(session):
        from researchgpt.db.models import Run

        rows = (session.query(Run)
                .order_by(Run.created_at.desc())
                .limit(limit)
                .all())
        return [r.as_summary() for r in rows]

    return _safe(_with_session, work)


def get_run(run_id: str) -> dict[str, Any] | None:
    def work(session):
        from researchgpt.db.models import Run

        row = session.query(Run).filter_by(run_id=run_id).one_or_none()
        return row.as_summary() if row is not None else None

    return _safe(_with_session, work)


__all__ = [
    "register_run",
    "mark_running",
    "attach_artefact",
    "complete_run",
    "fail_run",
    "list_runs",
    "get_run",
]
