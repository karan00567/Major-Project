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


def test_every_cited_paper_reaches_the_evidence_panel():
    """Panel 3 names a claim's SOURCE by resolving its ``paper_ids`` against
    the ``papers`` list in the same payload. So the payload's size cap must
    never drop a paper a claim cites.

    🔴 It did. The cap was a plain ``papers[:200]`` over a corpus in RETRIEVAL
    order, while the cited papers are whatever the Ranker floated to the top —
    unrelated orders. On the fixture, five of the nine cited papers sit at
    positions 251-466 and fell outside the slice, so more than half of the
    panel's source lookups missed and it could only say "not in this payload"
    about a paper the run had read. A slice is the obvious implementation and
    the wrong one; this test is what makes that visible.
    """
    import json
    import pathlib

    from researchgpt.api.app import RESULT_PAPER_LIMIT, _papers_for_panel

    run = pathlib.Path("outputs/runs/fixture")
    if not (run / "claims.json").exists():
        pytest.skip("fixture not built in this checkout")

    claims = json.loads((run / "claims.json").read_text(encoding="utf-8"))
    corpus = json.loads((run / "corpus.json").read_text(encoding="utf-8"))

    served = _papers_for_panel(corpus, claims)
    served_ids = {p["paper_id"] for p in served}

    cited = {
        pid
        for bucket in ("verified", "dropped")
        for claim in claims[bucket]
        for pid in claim.get("paper_ids") or []
    }
    known = {p["paper_id"] for p in corpus["papers"]}

    missing = (cited & known) - served_ids
    assert not missing, (
        f"{len(missing)} cited papers are absent from /result: {sorted(missing)[:5]}. "
        "Panel 3 cannot name their source."
    )

    # The papers a human is asked to score must survive the cap for the same
    # reason - and the cap itself has to still be a cap.
    extracted = set(corpus.get("extracted_paper_ids") or []) & known
    assert extracted <= served_ids, "extracted papers were truncated away"
    assert len(served) <= RESULT_PAPER_LIMIT
    assert len(served_ids) == len(served), "the payload repeats a paper"


# --------------------------------------------------------------------------
# T-609 — human-in-the-loop, persisted
# --------------------------------------------------------------------------


def test_override_survives_a_reload(client):
    """The criterion that separates "a UI control" from HITL being implemented.

    decisions.txt T-007 (2026-08-25) made HITL mandatory: it is the concrete
    implementation of Objective 2's "and Human-in-the-loop" clause, and without
    persistence the claim on deck slide 5 is false.
    """
    r = client.post("/api/runs/demo/overrides",
                    json={"claim_id": "c3", "decision": "reinstate",
                          "note": "a reviewer disagreed"})
    assert r.status_code == 200
    assert r.json()[0]["decision"] == "reinstate"

    # A fresh read - i.e. what a page reload does.
    reloaded = client.get("/api/runs/demo/result").json()["human_overrides"]
    assert [o["claim_id"] for o in reloaded] == ["c3"]
    assert reloaded[0]["note"] == "a reviewer disagreed"


def test_overrides_are_appended_not_rewritten(client, runs):
    """The trace is append-only (T-107), so a changed mind is history, not a
    silent overwrite. The report counts overrides from this file."""
    trace = runs / "demo" / "trace.jsonl"
    before = len(trace.read_text(encoding="utf-8").splitlines())

    client.post("/api/runs/demo/overrides", json={"claim_id": "c3", "decision": "confirm"})
    client.post("/api/runs/demo/overrides", json={"claim_id": "c3", "decision": "reinstate"})

    after = len(trace.read_text(encoding="utf-8").splitlines())
    assert after == before + 2, "an override overwrote history instead of appending"
    # Last write wins for the current view.
    assert client.get("/api/runs/demo/overrides").json()[0]["decision"] == "reinstate"


def test_clearing_an_override_removes_it_from_the_view(client):
    """A mis-click must be undoable, or the audit record keeps a judgement
    nobody meant."""
    client.post("/api/runs/demo/overrides", json={"claim_id": "c3", "decision": "confirm"})
    assert client.get("/api/runs/demo/overrides").json()

    client.post("/api/runs/demo/overrides", json={"claim_id": "c3", "decision": None})
    assert client.get("/api/runs/demo/overrides").json() == []


def test_override_rejects_an_unknown_claim_or_decision(client):
    """A typo would otherwise land a judgement in the audit record that refers
    to nothing."""
    assert client.post("/api/runs/demo/overrides",
                       json={"claim_id": "nope", "decision": "confirm"}).status_code == 404
    assert client.post("/api/runs/demo/overrides",
                       json={"claim_id": "c3", "decision": "sure"}).status_code == 422


def test_override_does_not_touch_the_review(client, runs):
    """★ An override records a judgement ABOUT a dropped claim. Reinstating the
    prose into review.md would destroy the very property Panel 4 exists to
    demonstrate."""
    review = runs / "demo" / "review.md"
    before = review.read_text(encoding="utf-8")
    client.post("/api/runs/demo/overrides",
                json={"claim_id": "c3", "decision": "reinstate"})
    assert review.read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------
# T-611 — the max_papers picker
# --------------------------------------------------------------------------

#: What Panel 1 offers. A fixed list rather than a free number box: these are
#: the sizes whose cost is actually known (see the runtime note in the panel),
#: and a typed 8,347 is a two-hour run nobody meant to start.
MAX_PAPER_OPTIONS = (5, 10, 15, 25, 50, 100)


def test_t611_every_offered_size_is_accepted_by_the_api():
    """🔴 The bound was ``le=60`` while the panel now offers 100, so choosing
    the largest size would have 422'd - a picker that cannot pick its own top
    entry. This test exists to keep the two ends from drifting again."""
    import pydantic
    import pytest as _pytest

    from researchgpt.api.schemas import ReviewRequest

    question = "How do multi-agent systems reduce hallucination in reviews?"
    for size in MAX_PAPER_OPTIONS:
        assert ReviewRequest(question=question, max_papers=size).max_papers == size

    # The ceiling is still a ceiling: above the largest offered size it fails.
    with _pytest.raises(pydantic.ValidationError):
        ReviewRequest(question=question, max_papers=max(MAX_PAPER_OPTIONS) + 1)
    with _pytest.raises(pydantic.ValidationError):
        ReviewRequest(question=question, max_papers=0)


def test_t611_the_panel_offers_exactly_those_sizes():
    """The picker is the contract the test above checks. Read it from the
    component so the two cannot say different things."""
    import pathlib
    import re

    repo = pathlib.Path(__file__).resolve().parents[1]
    panel = (repo / "frontend" / "src" / "components" / "PanelRun.vue").read_text(
        encoding="utf-8")
    match = re.search(r"const PAPER_OPTIONS = \[([0-9,\s]+)\]", panel)
    assert match, "PanelRun.vue must declare PAPER_OPTIONS for this to be checkable"
    offered = tuple(int(n) for n in match.group(1).replace(" ", "").strip(",").split(","))
    assert offered == MAX_PAPER_OPTIONS


def test_t612_the_score_panel_is_gated_to_the_optimizer_path():
    """The scoring sheet is reachable at /optimizer and nowhere else.

    Asserted on the source because there is no JS test runner here: the panel
    must be rendered behind a condition, not unconditionally. A gate that
    quietly disappears would put a scoring form on the main demo page, which is
    exactly what it was asked not to do.
    """
    import pathlib
    import re

    repo = pathlib.Path(__file__).resolve().parents[1]
    src = (repo / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")

    assert "'/optimizer'" in src, "the gate must name the path it opens on"
    assert re.search(r"<PanelScores\s+v-if=", src), (
        "PanelScores must be behind a v-if; rendering it unconditionally puts "
        "the score sheet on every page"
    )


def test_t612_panel_two_no_longer_dumps_raw_trace_events():
    """Panel 2 shows the agents and the Critic chain. The tail of raw events
    ('graph run_end / critic agent_end / ...') described the shape of the log
    rather than the run, and was removed 2026-08-29. The reasons survive as
    each chip's title, and trace.jsonl remains the full record."""
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    panel = (repo / "frontend" / "src" / "components" / "PanelProgress.vue").read_text(
        encoding="utf-8")
    assert 'class="log"' not in panel
    assert 'class="why"' not in panel
    # The chain itself, and the reasons on hover, must stay. Matched on the
    # class PREFIX: utility classes are appended alongside the hook since
    # T-614, so pinning the exact attribute would break on restyling.
    assert 'class="chain' in panel
    assert 'd.decision' in panel
    assert 'd.reasons.join' in panel


def test_t613_the_dashboard_is_its_own_route_and_replaces_the_run_page():
    """/dashboard explains the project to someone who has never seen it, so it
    renders INSTEAD of the panels rather than above them."""
    import pathlib
    import re

    repo = pathlib.Path(__file__).resolve().parents[1]
    src = (repo / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")

    assert "'/dashboard'" in src
    assert re.search(r"<DashboardView\s+v-if=\"onDashboard\"", src)
    # v-else on the app shell: the two views are exclusive, not stacked.
    # Asserted on the directive, not on a class name - the class is styling and
    # changed when the UI moved to Tailwind (T-614); the exclusivity is the
    # contract.
    assert re.search(r"<div\s+v-else", src)


def test_t613_the_dashboard_cta_navigates_without_starting_a_run():
    """🔴 The button must take the reader to the run page, NOT run anything.
    A dashboard that kicks off a 40-minute job and a slice of a daily token
    budget because someone clicked 'Run literature review' to see what it does
    is a trap."""
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    view = (repo / "frontend" / "src" / "components" / "DashboardView.vue").read_text(
        encoding="utf-8")

    assert "window.location.href = '/'" in view
    for forbidden in ("startReview", "postScores", "/api/review"):
        assert forbidden not in view, (
            f"{forbidden} on the dashboard - the CTA must navigate, not run"
        )


def test_t613_the_dashboard_states_the_problem_with_its_evidence():
    """The argument for claim-level verification rests on these measurements;
    without them the page is marketing copy."""
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[1]
    view = (repo / "frontend" / "src" / "components" / "DashboardView.vue").read_text(
        encoding="utf-8")
    for cited in ("FActScore", "ALCE", "Sarol", "SurveyGen"):
        assert cited in view
    assert "39.18%" in view and "35.84%" in view
