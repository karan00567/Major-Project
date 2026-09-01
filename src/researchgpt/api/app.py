"""T-601 / T-602 — the five endpoints from `PROJECT_PLAN §7.2`.

    POST   /api/review                    -> {run_id}      start a run
    GET    /api/runs/{id}/events          -> SSE           live agent progress
    GET    /api/runs/{id}/result          -> result JSON   review + evidence + drops
    GET    /api/runs/{id}/artifact/{name} -> file          review.md, insights.csv, ...
    GET    /api/runs                      -> [summaries]   for replaying pre-baked runs

★ **``trace.jsonl`` IS the event stream.** The SSE endpoint tails the run's
trace rather than maintaining a second in-memory bus. Three reasons this is the
right call and not a shortcut: T-904 fixes that schema and every report figure
already depends on it, so there is exactly one definition of "what happened";
a *finished* run replays identically to a live one, which is what T-610's
pre-baked demo needs; and a crashed run still has its events on disk, where an
in-memory bus would have lost them.

⚠️ **A run is minutes long, so ``POST /api/review`` returns 202 immediately**
and the work continues on a worker thread. Blocking would time out every proxy
between here and the browser. The client polls ``/result`` or watches
``/events``.

⚠️ **The filesystem is the source of truth.** No database is required, and
`T-625` says that must remain true even once Phase 6B lands: the registry is an
index over ``outputs/runs/``, never the record itself.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from researchgpt.api.schemas import (
    ArtefactInfo,
    ArtefactScoreIn,
    ClaimOut,
    OverrideOut,
    OverrideRequest,
    ReviewAccepted,
    ReviewRequest,
    RunResult,
    RunSummary,
    ScoredPaper,
    ScoreSheet,
    ScoreSubmission,
)
from researchgpt.db import scores as scores_db

log = logging.getLogger(__name__)

RUNS_DIR = pathlib.Path("outputs/runs")

#: T-603 — the recorded run the fixture mode replays.
FIXTURE_RUN_ID = "fixture"

#: ★ **Fixture mode: serve a recorded run and refuse to start real ones.**
#:
#: TASKLIST T-603: *"This decouples all frontend work from backend readiness
#: and costs zero API calls. It saves a full day. Do it before writing any
#: Vue."* The refusal is the point - during Panel work the front end will hit
#: POST /api/review by accident many times, and each real run costs minutes and
#: a slice of a metered daily token budget that four T-409 attempts exhausted
#: on 2026-08-28.
#:
#: No new serving path is needed, because the artefact directory already IS the
#: fixture: /result and /events read from disk, so a finished run replays
#: byte-identically to a live one. That is also what T-610's pre-baked demo
#: relies on.
#:
#: Set RESEARCHGPT_FIXTURE=1 (or pass --fixture to the serve command).
FIXTURE_MODE = os.getenv("RESEARCHGPT_FIXTURE", "").strip().lower() in (
    "1", "true", "yes", "on"
)

#: Only these may be downloaded. An allowlist rather than path sanitising: the
#: set of artefacts is small, closed and known, so there is no reason to accept
#: an arbitrary name and then try to prove it is safe.
DOWNLOADABLE = {
    "review.md": "text/markdown",
    "insights.csv": "text/csv",
    "refs.bib": "application/x-bibtex",
    "claims.json": "application/json",
    "corpus.json": "application/json",
    "config.json": "application/json",
    "trace.jsonl": "application/x-ndjson",
}

#: run_id -> "running" | "complete" | "failed". In-process only; a restart
#: falls back to inferring status from the artefacts on disk, which is why
#: _status() consults the filesystem rather than trusting this alone.
_RUNS: dict[str, str] = {}
_RUNS_LOCK = threading.Lock()

app = FastAPI(title="ResearchGPT", version="0.1.0")

# The Vue dev server is a different origin (T-604). Wide open because this is a
# localhost demo tool with no auth and no data worth stealing; it must not be
# deployed as-is.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _run_dir(run_id: str) -> pathlib.Path:
    """Resolve a run directory, refusing anything that escapes RUNS_DIR.

    ``run_id`` reaches us from the URL, so ``../../etc/passwd`` is a request we
    will actually receive. Resolving and then checking containment is the check
    that survives symlinks and encoding tricks, unlike filtering for "..".
    """
    base = RUNS_DIR.resolve()
    path = (RUNS_DIR / run_id).resolve()
    if base not in path.parents and path != base:
        raise HTTPException(status_code=400, detail="invalid run_id")
    if not path.is_dir():
        raise HTTPException(status_code=404, detail=f"no such run: {run_id}")
    return path


def _read_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _append_trace_events(
    run_dir: pathlib.Path, run_id: str,
    events: list[tuple[str, dict]], *, what: str = "event",
) -> None:
    """Append human-authored events to a run's trace.

    🔴 A trace that does not end in a newline would otherwise have the
    first record concatenated onto its last line, destroying BOTH - in the file
    every figure in the report is derived from. Appending blind is the obvious
    implementation and it is wrong; a real trace sometimes has no trailing
    newline (an interrupted run, an editor that strips it). Caught by
    ``test_override_survives_a_reload`` and by T-612's equivalent, both of
    which use a fixture with no trailing newline on purpose.

    Shared by T-609's overrides and T-612's scores: two human-input surfaces
    appending to the same file should not carry two copies of this.
    """
    if not events:
        return
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    lines = [
        json.dumps({"ts": now, "run_id": run_id, "agent": "human",
                    "event": name, "iteration": 0, "payload": payload},
                   ensure_ascii=False)
        for name, payload in events
    ]
    trace = run_dir / "trace.jsonl"
    try:
        needs_newline = False
        if trace.exists() and trace.stat().st_size:
            with trace.open("rb") as fh:
                fh.seek(-1, 2)
                needs_newline = fh.read(1) != b"\n"
        with trace.open("a", encoding="utf-8") as fh:
            payload = "\n".join(lines) + "\n"
            fh.write(("\n" if needs_newline else "") + payload)
    except OSError as exc:
        raise HTTPException(status_code=500,
                            detail=f"could not write {what}: {exc}") from exc


def _trace_events(run_dir: pathlib.Path) -> list[dict]:
    path = run_dir / "trace.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue          # a torn last line on a live run is normal
    return out


def _status(run_id: str, run_dir: pathlib.Path) -> str:
    """Live status if we started the run, otherwise inferred from disk."""
    with _RUNS_LOCK:
        known = _RUNS.get(run_id)
    if known:
        return known
    events = _trace_events(run_dir)
    names = {e.get("event") for e in events}
    if "run_end" in names or (run_dir / "review.md").exists():
        return "complete"
    if "run_failed" in names or "run_error" in names:
        return "failed"
    return "running" if events else "unknown"


#: The two keys a ``run_start`` payload can carry the question under. There are
#: genuinely two emitters and they never agreed: ``graph/build.py`` writes
#: ``research_question``, ``cli.py`` writes ``question``.
_QUESTION_KEYS = ("research_question", "question")


def _question_of(events: list[dict]) -> str | None:
    """The question a run was asked, from whichever emitter recorded it.

    🔴 This read ``research_question`` only, and returned on the FIRST
    ``run_start`` it saw. A CLI-launched run emits its own ``run_start`` first,
    under ``question`` — so the function hit that record, found no
    ``research_question``, and returned None. Measured 2026-08-30 across
    ``outputs/runs/``: **68 of 80 runs carry the CLI shape**, so the endpoint
    was blind to the question of 85% of runs on disk.

    That was invisible while the run picker led with the run id. It stopped
    being invisible the moment the picker led with the question, which is the
    only thing that distinguishes one run from another in a list of eighty.

    So: scan every ``run_start``, accept either key, and take the first one that
    actually has a question rather than the first record that merely looks like
    the right event.
    """
    for e in events:
        if e.get("event") != "run_start":
            continue
        payload = e.get("payload") or {}
        for key in _QUESTION_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _claims_out(rows: list[dict]) -> list[ClaimOut]:
    return [
        ClaimOut(
            claim_id=c.get("claim_id", ""),
            text=c.get("text", ""),
            verdict=c.get("verdict", ""),
            support_score=float(c.get("support_score") or 0.0),
            paper_ids=list(c.get("paper_ids") or []),
            evidence=[
                {"chunk_id": e.get("chunk_id", ""), "quote": e.get("quote", "")}
                for e in (c.get("evidence") or [])
            ],
        )
        for c in rows
    ]


# --------------------------------------------------------------------------
# endpoints
# --------------------------------------------------------------------------


@app.post("/api/review", response_model=ReviewAccepted, status_code=202)
def start_review(req: ReviewRequest) -> ReviewAccepted:
    """Start a run and return immediately.

    202, not 200: the run has been accepted and is minutes from finishing.
    """
    if FIXTURE_MODE:
        # 409, not 200-with-the-fixture: silently substituting a recorded run
        # for a requested one is how a demo ends up showing yesterday's answer
        # to today's question without anyone noticing.
        raise HTTPException(
            status_code=409,
            detail=(
                "fixture mode: refusing to start a real run. Replay the "
                f"recorded run at /api/runs/{FIXTURE_RUN_ID}/result and "
                f"/api/runs/{FIXTURE_RUN_ID}/events, or unset "
                "RESEARCHGPT_FIXTURE to run for real."
            ),
        )

    from researchgpt.core.config import load_config
    from researchgpt.graph.build import run_pipeline

    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    cfg = load_config("configs/default.yaml")

    with _RUNS_LOCK:
        _RUNS[run_id] = "running"

    def _work() -> None:
        try:
            run_pipeline(req.question, cfg, run_id=run_id,
                         max_papers=req.max_papers, use_loop=req.use_loop)
            status = "complete"
        except Exception:
            status = "failed"
        with _RUNS_LOCK:
            _RUNS[run_id] = status

    threading.Thread(target=_work, name=f"run-{run_id}", daemon=True).start()

    return ReviewAccepted(
        run_id=run_id,
        events_url=f"/api/runs/{run_id}/events",
        result_url=f"/api/runs/{run_id}/result",
    )


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs(limit: int = Query(default=50, ge=1, le=500)) -> list[RunSummary]:
    """Newest first. Registry if present, filesystem scan otherwise.

    ★ **T-625: this must work with no database at all.** The Vue run list and
    the T-610 pre-baked demo both depend on it, and the filesystem already
    holds everything the registry would store, so the fallback loses nothing
    the demo needs.

    🔴 **The filesystem is the BASE SET; the registry only enriches it.**
    The obvious implementation — "registry if present, else filesystem" — is
    wrong, and measurably so: the moment a real Postgres was connected on
    2026-08-28 the endpoint returned **2 rows against 60 runs on disk**, because
    the registry had only ever seen the runs made after it was enabled.
    Enabling an *index* must never make the application show less than reality
    (`DB_SCHEMA §1`: the filesystem is the record, every run is reconstructible
    from ``outputs/runs/``).

    So: enumerate the disk, then overlay registry metrics where a row exists.
    A registry row whose directory is gone is skipped — the artefacts are what
    this endpoint serves, and they are what has disappeared.
    """
    from researchgpt.db import registry

    enriched: dict[str, dict] = {}
    rows = registry.list_runs(500)
    if rows:
        enriched = {r["run_id"]: r for r in rows}

    if not RUNS_DIR.is_dir():
        return []
    dirs = sorted(
        (d for d in RUNS_DIR.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )[:limit]

    out: list[RunSummary] = []
    for d in dirs:
        events = _trace_events(d)
        end = next((e for e in reversed(events) if e.get("event") == "run_end"), None)
        payload = (end or {}).get("payload") or {}
        claims = _read_json(d / "claims.json") or {}
        indexed = enriched.get(d.name) or {}
        out.append(
            RunSummary(
                run_id=d.name,
                status=_status(d.name, d),
                question=_question_of(events) or indexed.get("question"),
                started=str(events[0].get("ts")) if events else indexed.get("started"),
                papers=payload.get("papers") or indexed.get("papers"),
                verified_claims=payload.get("verified_claims")
                if payload.get("verified_claims") is not None
                else indexed.get("verified_claims"),
                dropped_claims=payload.get("dropped_claims")
                if payload.get("dropped_claims") is not None
                else indexed.get("dropped_claims"),
                grounding_score=payload.get("grounding_score")
                or claims.get("grounding_score")
                or indexed.get("grounding_score"),
                artefacts=sorted(
                    f.name for f in d.iterdir() if f.name in DOWNLOADABLE
                ),
            )
        )
    return out


#: How many papers ``/result`` carries. A run's corpus runs to hundreds and the
#: page renders a handful, so the payload is capped — see ``_papers_for_panel``
#: for what the cap must never truncate.
RESULT_PAPER_LIMIT = 200


def _papers_for_panel(corpus: Any, claims: dict) -> list[dict]:
    """The corpus, capped — but never at the cost of a cited paper.

    🔴 A plain ``papers[:200]`` looks harmless and is not. The corpus is in
    RETRIEVAL order while the papers the review actually cites are whatever the
    Ranker floated to the top, so the two orders are unrelated: on the fixture,
    **five of the nine cited papers sit at positions 251-466** and fell outside
    the slice. Panel 3 resolves a claim's ``paper_ids`` against this list to
    name its source, so more than half of those lookups missed and the panel
    could only say "not in this payload" about a paper the run had read.

    Cited first, then the extracted set, then the rest of the corpus up to the
    cap: the papers the UI is guaranteed to ask about are the ones it is
    guaranteed to get.
    """
    papers = corpus.get("papers") if isinstance(corpus, dict) else corpus
    papers = list(papers or [])
    by_id = {p.get("paper_id"): p for p in papers if p.get("paper_id")}

    wanted: list[str] = []
    for bucket in ("verified", "dropped"):
        for claim in claims.get(bucket) or []:
            wanted.extend(claim.get("paper_ids") or [])
    if isinstance(corpus, dict):
        wanted.extend(corpus.get("extracted_paper_ids") or [])

    out: list[dict] = []
    seen: set[str] = set()
    for pid in wanted:
        if pid in by_id and pid not in seen:
            seen.add(pid)
            out.append(by_id[pid])
    for paper in papers:
        if len(out) >= RESULT_PAPER_LIMIT:
            break
        pid = paper.get("paper_id")
        if pid not in seen:
            seen.add(pid)
            out.append(paper)
    return out


@app.get("/api/runs/{run_id}/result", response_model=RunResult)
def run_result(run_id: str) -> RunResult:
    """Everything the Vue app renders, in one request."""
    run_dir = _run_dir(run_id)
    events = _trace_events(run_dir)
    end = next((e for e in reversed(events) if e.get("event") == "run_end"), None)
    payload = (end or {}).get("payload") or {}
    claims = _read_json(run_dir / "claims.json") or {}
    corpus = _read_json(run_dir / "corpus.json") or {}

    review = ""
    md = run_dir / "review.md"
    if md.exists():
        review = md.read_text(encoding="utf-8")

    return RunResult(
        run_id=run_id,
        status=_status(run_id, run_dir),
        question=_question_of(events),
        review_markdown=review,
        grounding_score=claims.get("grounding_score") or payload.get("grounding_score"),
        counts=claims.get("counts") or {},
        verified_claims=_claims_out(claims.get("verified") or []),
        dropped_claims=_claims_out(claims.get("dropped") or []),
        papers=_papers_for_panel(corpus, claims),
        extracted_paper_ids=list(
            (corpus.get("extracted_paper_ids") or []) if isinstance(corpus, dict) else []
        ),
        artefacts=sorted(f.name for f in run_dir.iterdir() if f.name in DOWNLOADABLE),
        decisions=list(payload.get("decisions") or []),
        iterations=int(payload.get("iterations") or 0),
        human_overrides=_overrides_of(run_dir),
    )


VALID_DECISIONS = {"confirm", "reinstate"}


def _overrides_of(run_dir: pathlib.Path) -> list[OverrideOut]:
    """Replay the trace's human_override events, last write per claim wins.

    ★ The trace is the single source of truth, not a side file. T-904 fixes its
    schema and the report's override count will be derived from it, so keeping
    a second store would create two answers to "what did the human decide?".
    Replaying also makes a cleared override (decision=null) work naturally: it
    is just the newest entry for that claim.
    """
    latest: dict[str, OverrideOut] = {}
    for e in _trace_events(run_dir):
        if e.get("event") != "human_override":
            continue
        p = e.get("payload") or {}
        cid = p.get("claim_id")
        if not cid:
            continue
        latest[cid] = OverrideOut(
            claim_id=cid, decision=p.get("decision"),
            note=p.get("note"), ts=str(e.get("ts") or ""),
        )
    return [o for o in latest.values() if o.decision]


@app.post("/api/runs/{run_id}/overrides", response_model=list[OverrideOut])
def record_override(run_id: str, req: OverrideRequest) -> list[OverrideOut]:
    """T-609 — write a human judgement back to the trace.

    `decisions.txt` T-007 (2026-08-25) made HITL mandatory: it is the concrete
    implementation of Objective 2's "and Human-in-the-loop" clause, and without
    it that objective is unmet.

    Appends rather than rewrites. The trace is append-only by construction
    (T-107), so an override is one more line and the history of a changed mind
    is preserved instead of being overwritten.
    """
    run_dir = _run_dir(run_id)

    if req.decision is not None and req.decision not in VALID_DECISIONS:
        raise HTTPException(
            status_code=422,
            detail=f"decision must be one of {sorted(VALID_DECISIONS)} or null",
        )

    # Refuse an override against a claim this run never produced: a typo would
    # otherwise land a judgement in the audit record that refers to nothing.
    claims = _read_json(run_dir / "claims.json") or {}
    known = {c.get("claim_id")
             for c in (claims.get("verified") or []) + (claims.get("dropped") or [])}
    if known and req.claim_id not in known:
        raise HTTPException(
            status_code=404,
            detail=f"no claim {req.claim_id!r} in run {run_id}",
        )

    _append_trace_events(run_dir, run_id, [
        ("human_override", {"claim_id": req.claim_id,
                            "decision": req.decision, "note": req.note}),
    ], what="override")

    return _overrides_of(run_dir)


@app.get("/api/runs/{run_id}/overrides", response_model=list[OverrideOut])
def list_overrides(run_id: str) -> list[OverrideOut]:
    return _overrides_of(_run_dir(run_id))


@app.get("/api/runs/{run_id}/artifact/{name}")
def run_artifact(run_id: str, name: str) -> FileResponse:
    run_dir = _run_dir(run_id)
    if name not in DOWNLOADABLE:
        raise HTTPException(
            status_code=404,
            detail=f"unknown artefact {name!r}; available: {sorted(DOWNLOADABLE)}",
        )
    path = run_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{name} not produced by this run")
    return FileResponse(path, media_type=DOWNLOADABLE[name], filename=name)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str) -> EventSourceResponse:
    """T-602 — one SSE event per trace line, tailing the file.

    Replays what already happened before following the tail, so a client that
    connects late (or replays a finished run for the T-610 demo) sees the whole
    story rather than only what arrives after it subscribed.
    """
    run_dir = _run_dir(run_id)
    trace = run_dir / "trace.jsonl"

    async def stream():
        sent = 0
        idle = 0
        while True:
            lines = []
            if trace.exists():
                try:
                    lines = trace.read_text(encoding="utf-8").splitlines()
                except OSError:
                    lines = []

            for line in lines[sent:]:
                sent += 1
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    sent -= 1     # torn final line; re-read it next tick
                    break
                yield {"event": event.get("event", "message"),
                       "data": json.dumps(event)}
                idle = 0

            status = _status(run_id, run_dir)
            if status in ("complete", "failed") and sent >= len(lines):
                yield {"event": "done", "data": json.dumps({"status": status})}
                return

            await asyncio.sleep(0.5)
            idle += 1
            # A run that produces nothing for 10 minutes is wedged. Ending the
            # stream tells the client that; holding it open forever does not.
            if idle > 1200:
                yield {"event": "done",
                       "data": json.dumps({"status": "stalled"})}
                return

    return EventSourceResponse(stream())


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Includes fixture state so the front end can show it.

    A demo that is quietly replaying a recording should say so on screen.
    """
    return {
        "ok": True,
        "runs_dir": str(RUNS_DIR),
        "known_runs": len(_RUNS),
        "fixture_mode": FIXTURE_MODE,
        "fixture_run_id": FIXTURE_RUN_ID if FIXTURE_MODE else None,
        "fixture_available": (RUNS_DIR / FIXTURE_RUN_ID).is_dir(),
    }


# --------------------------------------------------------------------------
# T-612 — human scoring
# --------------------------------------------------------------------------


def _scores_of(run_dir: pathlib.Path) -> tuple[dict[str, dict], dict | None]:
    """Replay the trace's ``human_score`` events, last write per target wins.

    Same shape as ``_overrides_of``: the trace is the record, the Postgres
    tables are a queryable mirror. Replaying means a re-score is just a newer
    line, so a changed mind is preserved in the history while the sheet shows
    the current answer.
    """
    papers: dict[str, dict] = {}
    artefact: dict | None = None
    for event in _trace_events(run_dir):
        if event.get("event") != "human_score":
            continue
        payload = event.get("payload") or {}
        kind, target = payload.get("kind"), payload.get("target")
        row = {"score": payload.get("score"), "note": payload.get("note")}
        if kind == "paper" and target:
            papers[target] = row
        elif kind == "artefact":
            artefact = dict(row, artefact=target or "review.md")
    return papers, artefact


def _extracted_papers(run_dir: pathlib.Path) -> list[dict]:
    """The papers the Extractor actually read, in ranked order.

    Not the whole pool: a run retrieves thousands and extracts ten, and asking
    a human to score thousands is not a review.
    """
    corpus = _read_json(run_dir / "corpus.json") or {}
    by_id = {p.get("paper_id"): p for p in (corpus.get("papers") or [])}
    return [by_id[i] for i in (corpus.get("extracted_paper_ids") or []) if i in by_id]


def _score_sheet(run_dir: pathlib.Path, run_id: str, persisted: str) -> ScoreSheet:
    scored, artefact_score = _scores_of(run_dir)
    rows = []
    for paper in _extracted_papers(run_dir):
        saved = scored.get(paper.get("paper_id")) or {}
        rows.append(ScoredPaper(
            paper_id=paper.get("paper_id") or "",
            doi=paper.get("doi"),
            title=paper.get("title") or "(untitled)",
            venue=paper.get("venue"),
            year=paper.get("year"),
            url=paper.get("url"),
            score=saved.get("score"),
            note=saved.get("note"),
        ))

    review = run_dir / "review.md"
    artefact = None
    if review.exists():
        try:
            artefact = ArtefactInfo(name="review.md",
                                    chars=len(review.read_text(encoding="utf-8")))
        except OSError:
            artefact = None

    current = None
    if artefact_score and artefact_score.get("score") is not None:
        current = ArtefactScoreIn(score=artefact_score["score"],
                                  note=artefact_score.get("note"),
                                  artefact=artefact_score.get("artefact") or "review.md")
    return ScoreSheet(run_id=run_id, papers=rows, artefact=artefact,
                      artefact_score=current, persisted=persisted)


def _mirror_state(run_id: str) -> str:
    """Whether the Postgres mirror currently holds a score for this run.

    🔴 Tests the CONTENTS, not the dict. ``get_scores`` returns
    ``{"papers": [], "artefact": None}`` for a run nobody has scored - which is
    truthy - so a truthiness check reported ``trace+db`` on an untouched sheet,
    telling the reviewer the database held a judgement that did not exist.
    """
    try:
        stored = scores_db.get_scores(run_id)
    except Exception:                       # the mirror is never load-bearing
        return "trace"
    if stored and (stored.get("papers") or stored.get("artefact")):
        return "trace+db"
    return "trace"


@app.get("/api/runs/{run_id}/scores", response_model=ScoreSheet)
def get_score_sheet(run_id: str) -> ScoreSheet:
    """T-612 — what a reviewer is asked to judge, plus anything judged so far."""
    run_dir = _run_dir(run_id)
    return _score_sheet(run_dir, run_id, _mirror_state(run_id))


@app.post("/api/runs/{run_id}/scores", response_model=ScoreSheet)
def submit_scores(run_id: str, req: ScoreSubmission) -> ScoreSheet:
    """T-612 — record a human 1-5 judgement of the papers and the review.

    ★ **The trace is written first, then Postgres.** `DB_SCHEMA.md §9` makes
    every registry call best-effort, which is right for a catalogue row the
    machine wrote and wrong for a judgement a human just formed. Writing the
    append-only trace first satisfies both: the score cannot be lost, the
    mirror stays best-effort, and the response says which happened instead of
    claiming a database write that did not occur.
    """
    run_dir = _run_dir(run_id)

    if not req.papers and req.artefact is None:
        raise HTTPException(status_code=422,
                            detail="submission scores nothing")

    # Refuse a judgement about a paper this run never read - the same guard the
    # override endpoint applies to claim_id, and for the same reason: a typo
    # would otherwise land in the audit record referring to nothing.
    known = {p.get("paper_id") for p in _extracted_papers(run_dir)}
    unknown = [p.paper_id for p in req.papers if p.paper_id not in known]
    if unknown:
        raise HTTPException(
            status_code=404,
            detail=f"run {run_id} did not extract these papers: {sorted(unknown)}",
        )

    by_id = {p.get("paper_id"): p for p in _extracted_papers(run_dir)}
    events: list[tuple[str, dict]] = []
    rows: list[dict] = []
    for entry in req.papers:
        paper = by_id.get(entry.paper_id) or {}
        events.append(("human_score", {
            "kind": "paper", "target": entry.paper_id, "score": entry.score,
            "note": entry.note, "doi": paper.get("doi"),
            "title": paper.get("title"),
        }))
        rows.append({"paper_id": entry.paper_id, "doi": paper.get("doi"),
                     "title": paper.get("title"), "score": entry.score,
                     "note": entry.note})

    artefact_row = None
    if req.artefact is not None:
        events.append(("human_score", {
            "kind": "artefact", "target": req.artefact.artefact,
            "score": req.artefact.score, "note": req.artefact.note,
        }))
        artefact_row = {"artefact": req.artefact.artefact,
                        "score": req.artefact.score, "note": req.artefact.note}

    _append_trace_events(run_dir, run_id, events, what="scores")

    persisted = "trace"
    try:
        if scores_db.save_scores(run_id, papers=rows, artefact=artefact_row):
            persisted = "trace+db"
    except Exception as exc:                # deliberately broad - DB_SCHEMA §9
        log.warning("scores not mirrored to Postgres for %s: %s", run_id, exc)

    return _score_sheet(run_dir, run_id, persisted)


__all__ = ["app", "DOWNLOADABLE", "RUNS_DIR", "FIXTURE_MODE", "FIXTURE_RUN_ID"]
