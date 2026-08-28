"""T-601 — request and response shapes for the API.

`PROJECT_PLAN §7.2`. Deliberately thin: the pipeline already writes typed
artefacts to ``outputs/runs/<run_id>/``, so these models mostly describe how
those files are surfaced rather than inventing a second representation of the
same data.

⚠️ **The artefact directory is the source of truth, not a database.** Phase 6B
(T-620..T-626) adds a Postgres run registry, but `T-625` requires
``GET /api/runs`` to work with no database at all, falling back to a filesystem
scan. Building against the filesystem first is therefore not a shortcut - it is
the contract the registry has to preserve.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    """``POST /api/review``."""

    question: str = Field(min_length=10)
    #: Defaults to the configured value when omitted. Capped low on purpose:
    #: the demo path (T-610) runs live only at small sizes, because a 25-paper
    #: run is minutes long and a 60-paper run is tens of minutes.
    max_papers: int | None = Field(default=None, ge=1, le=60)
    #: Run the six-agent graph (Verifier + Critic) rather than the M1 line.
    use_loop: bool = True


class ReviewAccepted(BaseModel):
    """``POST /api/review`` -> 202. The run has *started*, not finished."""

    run_id: str
    events_url: str
    result_url: str


class RunSummary(BaseModel):
    """One row of ``GET /api/runs``."""

    run_id: str
    status: str                      # running | complete | failed
    question: str | None = None
    started: str | None = None
    papers: int | None = None
    verified_claims: int | None = None
    dropped_claims: int | None = None
    grounding_score: float | None = None
    artefacts: list[str] = []


class EvidenceOut(BaseModel):
    chunk_id: str
    quote: str


class ClaimOut(BaseModel):
    """A verified or dropped claim, with what justified the verdict.

    ★ ``evidence`` is what makes Panel 3 (T-607) possible: click a sentence,
    see the span the Verifier actually scored it against. Returning a verdict
    without its evidence would make the panel a claim about the system rather
    than a demonstration of it.
    """

    claim_id: str
    text: str
    verdict: str
    support_score: float
    paper_ids: list[str] = []
    evidence: list[EvidenceOut] = []


class RunResult(BaseModel):
    """``GET /api/runs/{id}/result`` — everything the Vue app renders."""

    run_id: str
    status: str
    question: str | None = None
    review_markdown: str = ""
    grounding_score: float | None = None
    counts: dict[str, Any] = {}
    verified_claims: list[ClaimOut] = []
    #: Kept in the same payload as the verified ones, deliberately. Panel 4
    #: exists to show what the system REFUSED to say, and that is only
    #: persuasive next to what it did say.
    dropped_claims: list[ClaimOut] = []
    papers: list[dict[str, Any]] = []
    artefacts: list[str] = []
    decisions: list[str] = []
    iterations: int = 0


__all__ = [
    "ReviewRequest",
    "ReviewAccepted",
    "RunSummary",
    "ClaimOut",
    "EvidenceOut",
    "RunResult",
]
