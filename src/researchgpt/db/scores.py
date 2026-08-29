"""T-612 — human scores, mirrored into Postgres. `DB_SCHEMA.md §12`.

The reviewer scores each paper the Extractor read, and the review it produced,
from 1 (worst) to 5 (best). This module is the **mirror**, not the record.

★ **The trace is written first and this runs second.** `DB_SCHEMA.md §9` makes
every database call here best-effort - it logs a warning and returns ``None``
rather than raising - and that rule is right for a catalogue row the machine
wrote. It is *not* right for a judgement a human just spent minutes forming.
Both hold at once because ``api/app.py`` appends the score to the run's
``trace.jsonl`` before calling in here, exactly as T-609's overrides do. So a
database outage costs the mirror and never the score, and no rule is bent.

The same design decides what to do about duplicates: the trace is append-only
and keeps the history of a changed mind, while these tables hold one row per
(run, paper, reviewer) and update it in place. Two stores, two jobs - the log
and the queryable index - which is `DB_SCHEMA.md §1 rule 3` applied rather than
broken.
"""

from __future__ import annotations

import logging
from typing import Any

from researchgpt.db.models import DEFAULT_REVIEWER, ArtefactScore, PaperScore
from researchgpt.db.session import enabled, get_session

log = logging.getLogger(__name__)


def _with_session(work):
    """Commit-or-rollback around one unit of work. Mirrors ``registry.py``."""
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


def save_scores(
    run_id: str,
    papers: list[dict[str, Any]] | None = None,
    artefact: dict[str, Any] | None = None,
    reviewer: str = DEFAULT_REVIEWER,
) -> int | None:
    """Upsert the given scores. Returns rows written, or ``None`` if disabled.

    ⚠️ **This may raise, unlike ``registry.py``'s public functions.** The
    caller has already persisted the score to the trace and needs to know
    whether the mirror succeeded so it can tell the reviewer the truth - a
    silent ``None`` would make "saved to the database" unfalsifiable. The API
    catches it and downgrades the response to ``persisted: "trace"``.
    """
    if not enabled():
        return None

    def work(session) -> int:
        written = 0
        for row in papers or []:
            existing = (
                session.query(PaperScore)
                .filter_by(run_id=run_id, paper_id=row["paper_id"], reviewer=reviewer)
                .one_or_none()
            )
            if existing is None:
                session.add(PaperScore(
                    run_id=run_id, paper_id=row["paper_id"], doi=row.get("doi"),
                    title=row.get("title") or row["paper_id"], score=row["score"],
                    note=row.get("note"), reviewer=reviewer,
                ))
            else:
                # A changed mind updates the row; the trace keeps both answers.
                existing.score = row["score"]
                existing.note = row.get("note")
                existing.doi = row.get("doi")
                existing.title = row.get("title") or existing.title
            written += 1

        if artefact:
            name = artefact.get("artefact") or "review.md"
            existing = (
                session.query(ArtefactScore)
                .filter_by(run_id=run_id, artefact=name, reviewer=reviewer)
                .one_or_none()
            )
            if existing is None:
                session.add(ArtefactScore(
                    run_id=run_id, artefact=name, score=artefact["score"],
                    note=artefact.get("note"), reviewer=reviewer,
                ))
            else:
                existing.score = artefact["score"]
                existing.note = artefact.get("note")
            written += 1
        return written

    return _with_session(work)


def get_scores(run_id: str) -> dict[str, Any] | None:
    """Everything recorded for a run, or ``None`` when the database is absent.

    Best-effort on read: the sheet is rebuilt from the trace either way, so a
    failure here degrades the mirror's contribution and nothing else.
    """
    if not enabled():
        return None

    def work(session) -> dict[str, Any]:
        papers = (session.query(PaperScore)
                  .filter_by(run_id=run_id)
                  .order_by(PaperScore.created_at)
                  .all())
        artefact = (session.query(ArtefactScore)
                    .filter_by(run_id=run_id)
                    .order_by(ArtefactScore.created_at)
                    .first())
        return {"papers": [p.as_row() for p in papers],
                "artefact": artefact.as_row() if artefact else None}

    try:
        return _with_session(work)
    except Exception as exc:            # deliberately broad — see registry.py
        log.warning("score mirror unavailable: %s", exc)
        return None


__all__ = ["save_scores", "get_scores"]
