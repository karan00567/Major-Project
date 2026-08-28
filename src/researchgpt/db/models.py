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

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: `DB_SCHEMA.md §3`. Enforced by a CHECK constraint as well as by convention,
#: because a typo'd status is invisible until a query silently returns nothing.
STATUSES = ("pending", "running", "completed", "failed")


class Base(DeclarativeBase):
    pass


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
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Run {self.run_id} {self.status} artefacts={len(self.artefacts or [])}>"

    def as_summary(self) -> dict[str, Any]:
        """The shape ``GET /api/runs`` serves, so the registry and the
        filesystem fallback return the same thing (T-625)."""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "question": self.research_question,
            "started": self.created_at.isoformat() if self.created_at else None,
            "papers": (self.metrics or {}).get("papers"),
            "verified_claims": (self.metrics or {}).get("verified_claims"),
            "dropped_claims": (self.metrics or {}).get("dropped_claims"),
            "grounding_score": (self.metrics or {}).get("grounding_score"),
            "artefacts": [a.get("name") for a in (self.artefacts or []) if a.get("name")],
        }


__all__ = ["Base", "Run", "STATUSES"]
