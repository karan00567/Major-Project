"""Phase 6 acceptance tests — the API (T-601, T-602).

T-601's criterion is "all five respond", which is necessary and nowhere near
sufficient. The things that actually break a demo are tested here instead: a
run_id from the URL used as a path, an artefact name used as a path, a client
that connects to the event stream *after* the interesting events happened, and
a stream that never ends.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from researchgpt.api import app as app_module
from researchgpt.api.app import DOWNLOADABLE, app


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """Point the API at a throwaway runs directory with one finished run."""
    monkeypatch.setattr(app_module, "RUNS_DIR", tmp_path)
    run = tmp_path / "demo"
    run.mkdir()

    events = [
        {"ts": "2026-08-28T10:00:00Z", "agent": "graph", "event": "run_start",
         "iteration": 0, "payload": {"research_question": "Does it work?"}},
        {"ts": "2026-08-28T10:00:01Z", "agent": "planner", "event": "agent_end",
         "iteration": 0, "payload": {}},
        {"ts": "2026-08-28T10:00:02Z", "agent": "critic", "event": "critic_decision",
         "iteration": 0, "payload": {"decision": "WRITE"}},
        {"ts": "2026-08-28T10:00:03Z", "agent": "graph", "event": "run_end",
         "iteration": 0, "payload": {"papers": 42, "verified_claims": 2,
                                     "dropped_claims": 1, "grounding_score": 0.67,
                                     "decisions": ["WRITE"], "iterations": 0}},
    ]
    (run / "trace.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events), encoding="utf-8")
    (run / "review.md").write_text("# A review\n\nA grounded sentence [1].",
                                   encoding="utf-8")
    (run / "claims.json").write_text(json.dumps({
        "grounding_score": 0.67,
        "counts": {"verified": 2, "dropped": 1, "supported": 0, "partial": 2},
        "verified": [
            {"claim_id": "c1", "text": "A grounded sentence.", "verdict": "PARTIAL",
             "support_score": 0.81, "paper_ids": ["pA"],
             "evidence": [{"chunk_id": "pA-c1", "quote": "the evidence text",
                           "start_char": 0, "end_char": 17}]},
            {"claim_id": "c2", "text": "Another one.", "verdict": "PARTIAL",
             "support_score": 0.74, "paper_ids": ["pB"], "evidence": []},
        ],
        "dropped": [
            {"claim_id": "c3", "text": "An unsupported sentence.",
             "verdict": "UNSUPPORTED", "support_score": 0.03,
             "paper_ids": ["pA"], "evidence": []},
        ],
    }), encoding="utf-8")
    (run / "corpus.json").write_text(
        json.dumps({"papers": [{"paper_id": "pA", "title": "Paper A"}]}),
        encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(runs):
    return TestClient(app)


# --------------------------------------------------------------------------
# T-601 — the five endpoints
# --------------------------------------------------------------------------


def test_all_five_endpoints_respond(client):
    """T-601's stated acceptance criterion."""
    assert client.get("/api/runs").status_code == 200
    assert client.get("/api/runs/demo/result").status_code == 200
    assert client.get("/api/runs/demo/artifact/review.md").status_code == 200
    with client.stream("GET", "/api/runs/demo/events") as r:
        assert r.status_code == 200
    # POST is exercised separately; it starts a real pipeline.
    assert client.post("/api/review", json={"question": "too short"}).status_code == 422


def test_run_list_summarises_without_opening_every_artefact(client):
    rows = client.get("/api/runs").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "demo"
    assert row["status"] == "complete"
    assert row["question"] == "Does it work?"
    assert row["papers"] == 42
    assert row["verified_claims"] == 2
    assert "review.md" in row["artefacts"]


def test_result_carries_the_evidence_panel_3_needs(client):
    """T-607 is the graded money shot: click a sentence -> see its evidence.

    A verdict without its evidence span would make that panel a claim about the
    system rather than a demonstration of it.
    """
    data = client.get("/api/runs/demo/result").json()
    assert data["grounding_score"] == 0.67
    assert data["counts"]["verified"] == 2
    assert len(data["verified_claims"]) == 2
    assert len(data["dropped_claims"]) == 1

    first = data["verified_claims"][0]
    assert first["evidence"][0]["quote"] == "the evidence text"
    assert first["evidence"][0]["chunk_id"] == "pA-c1"
    # Panel 4 shows what the system refused to say.
    assert data["dropped_claims"][0]["verdict"] == "UNSUPPORTED"


def test_result_reports_the_critic_loop(client):
    data = client.get("/api/runs/demo/result").json()
    assert data["decisions"] == ["WRITE"]
    assert data["iterations"] == 0


# --------------------------------------------------------------------------
# The things that actually break
# --------------------------------------------------------------------------


def test_run_id_cannot_escape_the_runs_directory(client):
    """run_id arrives from the URL, so this is a request we will receive."""
    for hostile in ("../../etc", "..%2F..%2Fetc", "/etc/passwd"):
        r = client.get(f"/api/runs/{hostile}/result")
        assert r.status_code in (400, 404), hostile


def test_artifact_names_are_an_allowlist_not_a_path(client):
    """Filtering for '..' invites a bypass; a closed set does not."""
    assert client.get("/api/runs/demo/artifact/passwd").status_code == 404
    assert client.get("/api/runs/demo/artifact/../review.md").status_code in (404, 400)
    for name in DOWNLOADABLE:
        r = client.get(f"/api/runs/demo/artifact/{name}")
        assert r.status_code in (200, 404), name   # 404 only if not produced


def test_missing_run_is_404_not_500(client):
    assert client.get("/api/runs/nope/result").status_code == 404
    assert client.get("/api/runs/nope/artifact/review.md").status_code == 404


def test_review_request_rejects_a_trivial_question(client):
    assert client.post("/api/review", json={"question": "hi"}).status_code == 422
    assert client.post("/api/review",
                       json={"question": "A proper research question here?",
                             "max_papers": 999}).status_code == 422


# --------------------------------------------------------------------------
# T-602 — SSE
# --------------------------------------------------------------------------


def test_event_stream_replays_history_then_ends(client):
    """A client that connects late - or replays a finished run for the T-610
    demo - must see the whole story, not only what arrives after it
    subscribed. And the stream must END on a finished run, or the browser holds
    a connection open forever and the panel never settles.
    """
    with client.stream("GET", "/api/runs/demo/events") as r:
        assert r.status_code == 200
        body = "".join(chunk for chunk in r.iter_text())

    assert "run_start" in body
    assert "critic_decision" in body
    assert "run_end" in body
    assert "event: done" in body, "a finished run's stream must terminate"


def test_event_stream_payloads_are_the_trace_lines(client):
    """trace.jsonl IS the event stream. One schema (T-904), so a figure in the
    report and a panel in the browser cannot disagree about what happened."""
    with client.stream("GET", "/api/runs/demo/events") as r:
        body = "".join(chunk for chunk in r.iter_text())

    payloads = [json.loads(line[len("data: "):])
                for line in body.splitlines()
                if line.startswith("data: ") and "run_start" in line]
    assert payloads
    assert payloads[0]["agent"] == "graph"
    assert payloads[0]["payload"]["research_question"] == "Does it work?"


def test_event_stream_on_an_unknown_run_is_404(client):
    r = client.get("/api/runs/nope/events")
    assert r.status_code == 404


# --------------------------------------------------------------------------
# T-603 — the fixture
# --------------------------------------------------------------------------


def test_fixture_mode_refuses_to_start_a_real_run(runs, monkeypatch):
    """T-603 exists so frontend work cannot spend the token budget.

    During Panel work the front end will hit POST /api/review by accident many
    times. Each real run costs minutes and a slice of a metered DAILY budget
    that four T-409 attempts exhausted on 2026-08-28.
    """
    monkeypatch.setattr(app_module, "FIXTURE_MODE", True)
    client = TestClient(app)
    r = client.post("/api/review",
                    json={"question": "A perfectly reasonable question?"})
    assert r.status_code == 409
    assert "fixture mode" in r.json()["detail"]


def test_fixture_mode_does_not_silently_substitute_a_recording(runs, monkeypatch):
    """409 rather than 200-with-the-fixture.

    Quietly serving a recorded run for a requested one is how a demo ends up
    showing yesterday's answer to today's question without anyone noticing.
    """
    monkeypatch.setattr(app_module, "FIXTURE_MODE", True)
    client = TestClient(app)
    r = client.post("/api/review", json={"question": "Something else entirely?"})
    assert r.status_code != 200
    assert "run_id" not in r.json()


def test_health_declares_fixture_mode(runs, monkeypatch):
    """A demo replaying a recording should be able to say so on screen."""
    monkeypatch.setattr(app_module, "FIXTURE_MODE", True)
    body = TestClient(app).get("/api/health").json()
    assert body["fixture_mode"] is True
    assert body["fixture_run_id"] == app_module.FIXTURE_RUN_ID


def test_a_recorded_run_replays_through_the_normal_endpoints(runs):
    """No special serving path: the artefact directory IS the fixture, so a
    finished run replays byte-identically to a live one. That is also what
    T-610's pre-baked demo relies on."""
    client = TestClient(app)
    assert client.get("/api/runs/demo/result").json()["status"] == "complete"
    with client.stream("GET", "/api/runs/demo/events") as r:
        body = "".join(chunk for chunk in r.iter_text())
    assert "run_start" in body and "event: done" in body


# --------------------------------------------------------------------------
# T-607 — the data contract Panel 3 depends on
# --------------------------------------------------------------------------


def _normalise(s: str) -> str:
    """Must stay identical to PanelEvidence.vue::normalise."""
    import re

    s = re.sub(r"\[\d+\]", " ", s or "")
    s = re.sub(r"[*_`#]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def test_verified_claims_are_locatable_in_the_review():
    """Panel 3 highlights a sentence by matching NORMALISED text, not offsets.

    🔴 The Verifier strips `[n]` markers when it decomposes and the Writer's
    markdown carries them, so a byte offset into review.md points at the wrong
    place. If the two normalisations ever drift apart the panel silently
    highlights nothing and the graded "money shot" renders as plain prose -
    with no error anywhere. This asserts the contract from the Python side so a
    pipeline change cannot break the front end unnoticed.

    Measured on the fixture 2026-08-28: 19 of 19 claims located.
    """
    import json
    import pathlib

    run = pathlib.Path("outputs/runs/fixture")
    if not (run / "claims.json").exists():
        pytest.skip("fixture not built in this checkout")

    claims = json.loads((run / "claims.json").read_text(encoding="utf-8"))
    review = (run / "review.md").read_text(encoding="utf-8")
    verified = claims["verified"]
    assert verified, "fixture has no verified claims to inspect"

    haystack = _normalise(review)
    missing = [c["claim_id"] for c in verified if _normalise(c["text"]) not in haystack]

    assert not missing, (
        f"{len(missing)}/{len(verified)} verified claims cannot be found in "
        f"review.md ({missing[:5]}). Panel 3 would highlight nothing."
    )


def test_every_verified_claim_carries_its_evidence():
    """A verdict without its evidence makes Panel 3 an assertion about the
    system rather than a demonstration of it."""
    import json
    import pathlib

    path = pathlib.Path("outputs/runs/fixture/claims.json")
    if not path.exists():
        pytest.skip("fixture not built in this checkout")

    claims = json.loads(path.read_text(encoding="utf-8"))
    without = [c["claim_id"] for c in claims["verified"] if not c.get("evidence")]
    assert not without, f"verified claims with no evidence span: {without[:5]}"
