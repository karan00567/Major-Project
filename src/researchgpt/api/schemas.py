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
    #: Defaults to the configured value when omitted. The ceiling matches the
    #: largest size Panel 1 offers (T-611) - a picker whose top entry the API
    #: rejects is worse than no picker, and at le=60 that is exactly what
    #: choosing 100 did.
    #:
    #: ⚠️ The ceiling is a REQUEST bound, not a promise about runtime. Cost is
    #: roughly linear in max_papers and is paced by the provider's tokens per
    #: minute, not by CPU: measured 2026-08-29, extraction admits about one
    #: paper a minute on Groq's free tier, so 100 papers is ~100 minutes of
    #: extraction alone and ~650,000 reserved tokens against a 200,000/day
    #: budget - i.e. it cannot finish in one day. Panel 1 says so next to the
    #: sizes it offers; this bound only stops the request being absurd.
    max_papers: int | None = Field(default=None, ge=1, le=100)
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


class OverrideRequest(BaseModel):
    """``POST /api/runs/{id}/overrides`` — T-609.

    ⚠️ This records a human judgement ABOUT a dropped claim. It does not edit
    the review, and it must not: putting dropped prose back into ``review.md``
    on a click would destroy the very property the panel exists to demonstrate.
    """

    claim_id: str = Field(min_length=1)
    #: ``confirm``  - the Verifier was right to drop it
    #: ``reinstate`` - a human disagrees and would have kept it
    #: ``null``     - clear a previous override (a mis-click must be undoable)
    decision: str | None = None
    note: str | None = Field(default=None, max_length=2000)


class OverrideOut(BaseModel):
    claim_id: str
    decision: str | None = None
    note: str | None = None
    ts: str | None = None


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
    #: Which of those the Extractor actually read. A run retrieves hundreds and
    #: extracts ten, and the difference is the point: the panel can say "read"
    #: rather than "retrieved" about a paper only if it is told which is which.
    extracted_paper_ids: list[str] = []
    artefacts: list[str] = []
    decisions: list[str] = []
    iterations: int = 0
    #: T-609. Reconstructed from the trace, so a reload shows what a
    #: human already decided.
    human_overrides: list[OverrideOut] = []


# --------------------------------------------------------------------------
# T-612 — human scoring
# --------------------------------------------------------------------------

#: 1 is worst, 5 is best. Mirrors the CHECK constraint in ``db/models.py`` -
#: validated in both places on purpose, so a score written by psql or by a
#: later script is still in range.
SCORE_MIN, SCORE_MAX = 1, 5


class PaperScoreIn(BaseModel):
    """One reviewer judgement of one paper the Extractor read."""

    #: The pipeline's identity for the paper, not its DOI: about one OpenAlex
    #: record in five has no DOI, and those papers must still be scoreable.
    paper_id: str = Field(min_length=1)
    score: int = Field(ge=SCORE_MIN, le=SCORE_MAX)
    note: str | None = Field(default=None, max_length=2000)


class ArtefactScoreIn(BaseModel):
    """The reviewer's verdict on the generated review itself."""

    score: int = Field(ge=SCORE_MIN, le=SCORE_MAX)
    note: str | None = Field(default=None, max_length=2000)
    artefact: str = "review.md"


class ScoreSubmission(BaseModel):
    """``POST /api/runs/{id}/scores`` — T-612.

    Scoring the papers and scoring the write-up are deliberately separate
    fields rather than one number: they answer "was retrieval any good?" and
    "was the writing any good?", and the automated metrics cannot currently
    tell those apart.
    """

    papers: list[PaperScoreIn] = Field(default_factory=list)
    artefact: ArtefactScoreIn | None = None


class ScoredPaper(BaseModel):
    """A row of the review sheet: what to judge, plus any judgement so far."""

    paper_id: str
    doi: str | None = None
    title: str
    venue: str | None = None
    year: int | None = None
    url: str | None = None
    score: int | None = None
    note: str | None = None


class ArtefactInfo(BaseModel):
    name: str
    chars: int


class ScoreSheet(BaseModel):
    """``GET /api/runs/{id}/scores`` and the reply to a submission."""

    run_id: str
    papers: list[ScoredPaper]
    artefact: ArtefactInfo | None = None
    artefact_score: ArtefactScoreIn | None = None
    #: ``"trace"`` or ``"trace+db"``. The UI shows the difference rather than
    #: claiming a database write that did not happen - the registry is
    #: best-effort (`DB_SCHEMA.md §9`) and may simply be absent.
    persisted: str = "trace"


#: T-614 — accounts. Kept at the bottom so the run-facing schemas above stay
#: the first thing a reader meets.


class RegisterRequest(BaseModel):
    """``POST /api/auth/register``."""

    email: str = Field(min_length=3, max_length=255)
    #: The floor is enforced again in ``db.users.hash_password``. Two layers on
    #: purpose: this one gives a good error message, that one is the guarantee,
    #: and a password set by a seeding script never passes through here.
    password: str = Field(min_length=8, max_length=72)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    """``POST /api/auth/login``."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=72)


class ProfileUpdate(BaseModel):
    """``PATCH /api/auth/profile``. Every field optional; absent means unchanged."""

    display_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    new_password: str | None = Field(default=None, min_length=8, max_length=72)
    #: Required by the server whenever email or password changes.
    current_password: str | None = Field(default=None, max_length=72)


class UserOut(BaseModel):
    """An account as the API is willing to describe it. No password field
    exists here, so no handler can leak one by forgetting to strip it."""

    id: str
    email: str
    display_name: str | None = None
    #: Gates the T-612 scoring sheet in the UI. The client uses this only to
    #: decide what to render — every scoring route re-checks it server side, so
    #: editing this to true in a browser console reveals a panel whose every
    #: request then returns 403.
    is_admin: bool = False
    created_at: str | None = None


class AuthOut(BaseModel):
    """A successful register or login."""

    token: str
    token_type: str = "bearer"
    user: UserOut


__all__ = [
    "ReviewRequest",
    "OverrideRequest",
    "OverrideOut",
    "ReviewAccepted",
    "RunSummary",
    "ClaimOut",
    "EvidenceOut",
    "RunResult",
    "PaperScoreIn",
    "ArtefactScoreIn",
    "ScoreSubmission",
    "ScoredPaper",
    "ArtefactInfo",
    "ScoreSheet",
    "SCORE_MIN",
    "SCORE_MAX",
    "RegisterRequest",
    "LoginRequest",
    "ProfileUpdate",
    "UserOut",
    "AuthOut",
]
