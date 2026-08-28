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
    ClaimOut,
    OverrideOut,
    OverrideRequest,
    ReviewAccepted,
    ReviewRequest,
    RunResult,
    RunSummary,
)

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


def _question_of(events: list[dict]) -> str | None:
    for e in events:
        if e.get("event") == "run_start":
            return (e.get("payload") or {}).get("research_question")
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

    ``registry.list_runs`` returns ``None`` when unavailable and ``[]`` when it
    is present but empty — the distinction matters, or an empty database would
    be indistinguishable from an empty disk and we would scan for nothing.
    """
    from researchgpt.db import registry

    rows = registry.list_runs(limit)
    if rows is not None:
        return [RunSummary(**r) for r in rows]

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
        out.append(
            RunSummary(
                run_id=d.name,
                status=_status(d.name, d),
                question=_question_of(events),
                started=str(events[0].get("ts")) if events else None,
                papers=payload.get("papers"),
                verified_claims=payload.get("verified_claims"),
                dropped_claims=payload.get("dropped_claims"),
                grounding_score=payload.get("grounding_score")
                or claims.get("grounding_score"),
                artefacts=sorted(
                    f.name for f in d.iterdir() if f.name in DOWNLOADABLE
                ),
            )
        )
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
    papers = corpus.get("papers") if isinstance(corpus, dict) else corpus

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
        papers=list(papers or [])[:200],
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

    line = json.dumps({
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "run_id": run_id,
        "agent": "human",
        "event": "human_override",
        "iteration": 0,
        "payload": {"claim_id": req.claim_id, "decision": req.decision,
                    "note": req.note},
    }, ensure_ascii=False)
    trace = run_dir / "trace.jsonl"
    try:
        # 🔴 A trace that does not end in a newline would otherwise have this
        # record concatenated onto its last line, destroying BOTH - in the file
        # the report derives its figures from. Appending blind is the obvious
        # implementation and it is wrong; caught by
        # test_override_survives_a_reload, which uses a fixture with no
        # trailing newline precisely because real files sometimes do not have
        # one (an interrupted run, an editor that strips it).
        needs_newline = False
        if trace.exists() and trace.stat().st_size:
            with trace.open("rb") as fh:
                fh.seek(-1, 2)
                needs_newline = fh.read(1) != b"\n"
        with trace.open("a", encoding="utf-8") as fh:
            fh.write(("\n" if needs_newline else "") + line + "\n")
    except OSError as exc:
        raise HTTPException(status_code=500,
                            detail=f"could not write override: {exc}") from exc

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


__all__ = ["app", "DOWNLOADABLE", "RUNS_DIR", "FIXTURE_MODE", "FIXTURE_RUN_ID"]
