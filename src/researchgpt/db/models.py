"""T-621 — the ``runs`` table. `DB_SCHEMA.md §7`.

Written by hand rather than generated, for the same reason as T-102: this is a
schema, and one line of it is a correctness requirement that looks like a style
choice.

🔴 **``MutableList`` / ``MutableDict`` are load-bearing.** `DB_SCHEMA.md §7.1`
calls this "the one gotcha that will bite": SQLAlchemy tracks changes by
identity, and a plain ``JSONB`` column holds an ordinary Python list. Mutating
it in place —

    run.artefacts.append({...})
    session.commit()

— leaves the object identical to the one SQLAlchemy loaded, so the row is never
marked dirty, **no UPDATE is emitted, and the artefact silently vanishes with no
error to debug.** The ``Mutable*`` wrappers make in-place mutation flush. Do not
"simplify" them away.

⚠️ **This module must never be imported by the pipeline.** The registry is
optional (T-625: the API works with no database at all), so anything that
imports SQLAlchemy at module scope has to stay behind ``db/``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: `DB_SCHEMA.md §3`. Enforced by a CHECK constraint as well as by convention,
#: because a typo'd status is invisible until a query silently returns nothing.
STATUSES = ("pending", "running", "completed", "failed")


class Base(DeclarativeBase):
    pass


class User(Base):
    """An account. Added T-614 alongside the chat-style UI.

    ⚠️ **This table breaks the "runs with no database" property, and only for
    itself.** `T-625` guarantees the *pipeline* runs with no Postgres, and that
    still holds — nothing under ``agents/``, ``graph/`` or ``core/`` imports
    this module. But identity has no filesystem fallback: there is nowhere else
    to check a password, so the API's authenticated routes require the registry
    to be up. That is a deliberate narrowing, documented here rather than
    discovered at a login prompt.

    Passwords are stored as a bcrypt hash and never in clear text; ``bcrypt``
    carries its own per-password salt inside the hash string, so there is no
    separate salt column.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: Stored lower-cased. The uniqueness of an account must not depend on how
    #: the user happened to capitalise it when they typed it.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    #: T-614 — an admin sees the T-612 manual scoring sheet; an ordinary account
    #: does not. Deliberately NOT settable through any API: there is no
    #: "promote" route and ``update_profile`` cannot reach this column, so the
    #: only way to grant it is ``scripts/seed_accounts.py`` or psql. A
    #: self-service privilege escalation is the failure mode worth designing
    #: out, and a project with one admin does not need a UI for it.
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("ix_users_email", "email"),)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email}>"

    def as_public(self) -> dict[str, Any]:
        """What the API is allowed to send back. ``password_hash`` is not in
        this dict, and that is the whole point of having the method."""
        return {
            "id": str(self.id),
            "email": self.email,
            "display_name": self.display_name,
            "is_admin": bool(self.is_admin),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Run(Base):
    """One pipeline run. Derived data: the filesystem remains the record.

    `DB_SCHEMA.md §1`: every run is reconstructible from ``outputs/runs/``, so
    this table is an index for querying, never the source of truth. That is
    what makes it safe for the registry to be absent (T-625) or to fail
    mid-run (T-626).
    """

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: The directory name under outputs/runs/. Unique, because it is the join
    #: key between this row and the artefacts on disk.
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    research_question: Mapped[str] = mapped_column(Text, nullable=False)

    #: Who started it. NULLABLE and carrying no foreign key, for the same
    #: reason ``paper_scores.run_id`` carries none: the registry is best-effort,
    #: so a run can exist on disk having never been registered, and every run
    #: made before T-614 predates accounts entirely. A NOT NULL column here
    #: would make the pipeline fail when Postgres is down, which inverts T-625.
    #: An unowned run belongs to nobody and is listed to nobody.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    config: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB), nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    #: Grows during a run: see the module docstring on why this is Mutable.
    artefacts: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSONB), nullable=False, default=list
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB), nullable=False, default=dict
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','completed','failed')",
            name="ck_runs_status",
        ),
        Index("ix_runs_created_at", created_at.desc()),
        # GIN over the artefact array, so "which run produced this file?" does
        # not become a sequential scan once there are hundreds of rows.
        Index("ix_runs_artefacts", artefacts, postgresql_using="gin"),
        # Every authenticated list is "this user's runs, newest first", so the
        # index carries the sort with it rather than making Postgres re-sort.
        Index("ix_runs_user_id_created", "user_id", created_at.desc()),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Run {self.run_id} {self.status} artefacts={len(self.artefacts or [])}>"

    def as_summary(self) -> dict[str, Any]:
        """The shape ``GET /api/runs`` serves, so the registry and the
        filesystem fallback return the same thing (T-625)."""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "user_id": str(self.user_id) if self.user_id else None,
            "question": self.research_question,
            "started": self.created_at.isoformat() if self.created_at else None,
            "papers": (self.metrics or {}).get("papers"),
            "verified_claims": (self.metrics or {}).get("verified_claims"),
            "dropped_claims": (self.metrics or {}).get("dropped_claims"),
            "grounding_score": (self.metrics or {}).get("grounding_score"),
            "artefacts": [a.get("name") for a in (self.artefacts or []) if a.get("name")],
        }


#: `DB_SCHEMA.md §12`. 1 is worst, 5 is best. Enforced by a CHECK constraint as
#: well as by Pydantic, so a score written by psql or a future script is still
#: in range - validation at one layer only is validation that can be walked
#: around.
SCORE_MIN, SCORE_MAX = 1, 5

#: No identity system in a single-user project, but the column exists so a
#: second rater can be added later without a migration (`DB_SCHEMA.md §8` has
#: no Alembic, so a column added later means drop-and-recreate).
DEFAULT_REVIEWER = "human"


class PaperScore(Base):
    """One human 1-5 judgement of one paper the Extractor read (T-612).

    ⚠️ **``run_id`` carries NO foreign key to ``runs``, deliberately.** The
    registry is best-effort (`DB_SCHEMA.md §9`), so a run whose artefacts are
    on disk may never have been registered - it only takes Postgres being down
    while the pipeline ran. An FK would then reject a human's score for a run
    that demonstrably exists, which inverts the rule: the index would be
    refusing data because the index is incomplete.
    """

    __tablename__ = "paper_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The pipeline's own identity for the paper, and the join key back to
    #: corpus.json. NOT the DOI: roughly one OpenAlex record in five has none,
    #: and keying on it silently drops exactly those papers.
    paper_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Carried for citation and for the reviewer's doi.org link. Nullable, and
    #: nullable is load-bearing - see above.
    doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: A snapshot of the title the reviewer actually saw when they scored.
    #: `DB_SCHEMA.md §11` gives paper metadata to SQLite and that stands; this
    #: is not a metadata store, it is evidence of what was judged, and it must
    #: not change when the corpus is re-fetched.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer: Mapped[str] = mapped_column(
        String(64), nullable=False, default=DEFAULT_REVIEWER
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(f"score BETWEEN {SCORE_MIN} AND {SCORE_MAX}",
                        name="ck_paper_scores_range"),
        # Re-scoring is a changed mind, not a second opinion: one row per
        # (run, paper, reviewer), updated in place. The trace keeps the history.
        UniqueConstraint("run_id", "paper_id", "reviewer",
                         name="uq_paper_scores_run_paper_reviewer"),
        Index("ix_paper_scores_run_id", "run_id"),
        Index("ix_paper_scores_doi", "doi"),
    )

    def as_row(self) -> dict[str, Any]:
        return {"paper_id": self.paper_id, "doi": self.doi, "title": self.title,
                "score": self.score, "note": self.note, "reviewer": self.reviewer}


class ArtefactScore(Base):
    """One human 1-5 judgement of a generated artefact, normally ``review.md``.

    Separate from :class:`PaperScore` because they answer different questions -
    "was the retrieval any good?" against "was the writing any good?" - and the
    metrics cannot currently tell those apart. Averaging them into one number
    would destroy the distinction the table exists to record.
    """

    __tablename__ = "artefact_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    artefact: Mapped[str] = mapped_column(String(64), nullable=False,
                                          default="review.md")
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer: Mapped[str] = mapped_column(
        String(64), nullable=False, default=DEFAULT_REVIEWER
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(f"score BETWEEN {SCORE_MIN} AND {SCORE_MAX}",
                        name="ck_artefact_scores_range"),
        UniqueConstraint("run_id", "artefact", "reviewer",
                         name="uq_artefact_scores_run_artefact_reviewer"),
        Index("ix_artefact_scores_run_id", "run_id"),
    )

    def as_row(self) -> dict[str, Any]:
        return {"artefact": self.artefact, "score": self.score,
                "note": self.note, "reviewer": self.reviewer}


__all__ = ["Base", "Run", "User", "STATUSES", "PaperScore", "ArtefactScore",
           "SCORE_MIN", "SCORE_MAX", "DEFAULT_REVIEWER"]
