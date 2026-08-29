"""T-612 acceptance — the human scoring surface.

A reviewer opens a finished run, sees the papers the Extractor actually read
(with their DOIs) and the review it produced, and scores each 1-5. The scores
go to the run's ``trace.jsonl`` first and are mirrored into Postgres.

**Why the trace is written first, and why that is not belt-and-braces.**
`DB_SCHEMA.md §9` makes every registry call best-effort: a database failure
logs a warning and returns, because losing a 30-minute pipeline run to an index
update would be absurd. That rule is right for machine-generated catalogue rows
and wrong for a judgement a human just typed. Writing the trace first resolves
it - the submission cannot be lost, the registry stays best-effort, and no rule
has to be bent.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from researchgpt.api import app as app_module
from researchgpt.api.app import app
from researchgpt.db import scores as scores_module
from researchgpt.db.session import database_url, get_session


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """A finished run with three extracted papers, one of them DOI-less."""
    monkeypatch.setattr(app_module, "RUNS_DIR", tmp_path)
    run = tmp_path / "demo"
    run.mkdir()

    papers = [
        {"paper_id": "W1", "doi": "10.1162/tacl_a_00530", "title": "Paper One",
         "venue": "TACL", "year": 2023, "url": "https://example.org/1"},
        {"paper_id": "W2", "doi": "10.1145/3703155", "title": "Paper Two",
         "venue": "ACM", "year": 2024, "url": None},
        # 🔴 Measured on a real run: W3167518830 "JBI evidence synthesis" has
        # no DOI at all. A sheet keyed on DOI would silently drop it.
        {"paper_id": "W3", "doi": None, "title": "JBI evidence synthesis",
         "venue": None, "year": 2021, "url": None},
        # Retrieved but NOT extracted: must not appear on the sheet.
        {"paper_id": "W9", "doi": "10.1/unread", "title": "Never read",
         "venue": None, "year": 2020, "url": None},
    ]
    (run / "corpus.json").write_text(json.dumps({
        "papers": papers,
        "extracted_paper_ids": ["W1", "W2", "W3"],
    }), encoding="utf-8")
    (run / "review.md").write_text("# A review\n\nA grounded sentence [1].",
                                   encoding="utf-8")
    # Deliberately NO trailing newline: a real trace sometimes lacks one, and
    # appending blind would concatenate the new record onto the last line.
    (run / "trace.jsonl").write_text(json.dumps(
        {"ts": "2026-08-29T10:00:00Z", "run_id": "demo", "agent": "graph",
         "event": "run_end", "iteration": 0, "payload": {}}), encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(runs, monkeypatch):
    """Database mirroring off by default, so these test the HTTP contract."""
    monkeypatch.setattr(scores_module, "save_scores", lambda *a, **k: None)
    return TestClient(app)


def _trace_events(runs_dir, run_id="demo"):
    text = (runs_dir / run_id / "trace.jsonl").read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pytest.fail(f"trace line is not valid JSON - appended blind? {line[:120]!r}")
    return out


# --------------------------------------------------------------------------
# The sheet
# --------------------------------------------------------------------------


def test_t612_sheet_offers_the_papers_the_extractor_actually_read(client):
    """Not the whole pool. A cap-25 run retrieves ~2,200 papers and extracts
    10; asking a human to score 2,200 is not a review, it is a punishment."""
    sheet = client.get("/api/runs/demo/scores").json()
    assert [p["paper_id"] for p in sheet["papers"]] == ["W1", "W2", "W3"]
    assert "W9" not in json.dumps(sheet)


def test_t612_sheet_carries_the_doi_so_the_reviewer_can_check_the_paper(client):
    sheet = client.get("/api/runs/demo/scores").json()
    by_id = {p["paper_id"]: p for p in sheet["papers"]}
    assert by_id["W1"]["doi"] == "10.1162/tacl_a_00530"
    assert by_id["W1"]["title"] == "Paper One"


def test_t612_a_paper_with_no_doi_is_still_scoreable(client):
    """Roughly one OpenAlex record in five has no DOI, and this project has
    already been bitten once by keying on it."""
    sheet = client.get("/api/runs/demo/scores").json()
    by_id = {p["paper_id"]: p for p in sheet["papers"]}
    assert by_id["W3"]["doi"] is None
    r = client.post("/api/runs/demo/scores",
                    json={"papers": [{"paper_id": "W3", "score": 4}]})
    assert r.status_code == 200


def test_t612_sheet_names_the_artefact_being_scored(client):
    sheet = client.get("/api/runs/demo/scores").json()
    assert sheet["artefact"]["name"] == "review.md"
    assert sheet["artefact"]["chars"] > 0


def test_t612_unknown_run_is_404(client):
    assert client.get("/api/runs/nope/scores").status_code == 404
    assert client.post("/api/runs/nope/scores",
                       json={"papers": []}).status_code == 404


# --------------------------------------------------------------------------
# Submitting
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [0, 6, -1, 100])
def test_t612_a_score_outside_one_to_five_is_refused(client, bad):
    r = client.post("/api/runs/demo/scores",
                    json={"papers": [{"paper_id": "W1", "score": bad}]})
    assert r.status_code == 422


def test_t612_a_paper_not_in_this_run_is_refused(client):
    """A typo would otherwise land a judgement about a paper this run never
    read - the same failure the override endpoint guards against."""
    r = client.post("/api/runs/demo/scores",
                    json={"papers": [{"paper_id": "W_TYPO", "score": 3}]})
    assert r.status_code == 404
    assert "W_TYPO" in r.text


def test_t612_scoring_an_unextracted_paper_is_refused(client):
    """W9 was retrieved but never read, so there is nothing for a human to
    have judged."""
    r = client.post("/api/runs/demo/scores",
                    json={"papers": [{"paper_id": "W9", "score": 3}]})
    assert r.status_code == 404


def test_t612_scores_are_appended_to_the_trace(client, runs):
    client.post("/api/runs/demo/scores", json={
        "papers": [{"paper_id": "W1", "score": 5, "note": "spot on"},
                   {"paper_id": "W2", "score": 2}],
        "artefact": {"score": 3, "note": "thin"},
    })
    events = [e for e in _trace_events(runs) if e["event"] == "human_score"]
    assert len(events) == 3
    kinds = {(e["payload"].get("kind"), e["payload"].get("target")) for e in events}
    assert ("paper", "W1") in kinds
    assert ("artefact", "review.md") in kinds
    assert all(e["agent"] == "human" for e in events)


def test_t612_the_response_reports_where_the_score_was_persisted(client):
    """The UI must be able to say 'saved, not yet mirrored' honestly rather
    than claiming a database write that did not happen."""
    r = client.post("/api/runs/demo/scores",
                    json={"papers": [{"paper_id": "W1", "score": 4}]})
    assert r.json()["persisted"] == "trace"


def test_t612_rescoring_a_paper_replaces_the_earlier_score(client):
    """Append-only storage, last-write-wins on read - the same shape as
    human_override, so a changed mind stays in the history."""
    client.post("/api/runs/demo/scores",
                json={"papers": [{"paper_id": "W1", "score": 1}]})
    client.post("/api/runs/demo/scores",
                json={"papers": [{"paper_id": "W1", "score": 5, "note": "reread"}]})
    sheet = client.get("/api/runs/demo/scores").json()
    w1 = next(p for p in sheet["papers"] if p["paper_id"] == "W1")
    assert w1["score"] == 5
    assert w1["note"] == "reread"


def test_t612_scores_survive_a_reload(client, runs):
    """The sheet is rebuilt from the trace, so a restarted API still shows
    what the human said."""
    client.post("/api/runs/demo/scores", json={
        "papers": [{"paper_id": "W2", "score": 3}],
        "artefact": {"score": 4},
    })
    fresh = TestClient(app).get("/api/runs/demo/scores").json()
    assert next(p for p in fresh["papers"] if p["paper_id"] == "W2")["score"] == 3
    assert fresh["artefact_score"]["score"] == 4


def test_t612_an_empty_submission_is_refused(client):
    """A POST that scores nothing is a mistake, not a no-op worth recording."""
    r = client.post("/api/runs/demo/scores", json={"papers": []})
    assert r.status_code == 422


# --------------------------------------------------------------------------
# Durability — the rule this feature had to bend around
# --------------------------------------------------------------------------


def test_t612_a_database_outage_does_not_lose_what_the_human_typed(runs, monkeypatch):
    """🔴 The property this design exists for. `DB_SCHEMA.md §9` says a
    registry failure must never raise into its caller - but a human just spent
    minutes reading papers, and dropping that silently is a different thing
    from dropping a machine-written catalogue row.

    Postgres raises on every call here, as a stopped service would. The
    submission must still succeed, the trace must still hold every score, and
    the response must say the mirror did not happen.
    """
    def explode(*a, **k):
        raise RuntimeError("connection refused (simulated Postgres outage)")

    monkeypatch.setattr(scores_module, "save_scores", explode)
    client = TestClient(app)

    r = client.post("/api/runs/demo/scores", json={
        "papers": [{"paper_id": "W1", "score": 5, "note": "worth keeping"}],
        "artefact": {"score": 2},
    })
    assert r.status_code == 200
    assert r.json()["persisted"] == "trace"

    events = [e for e in _trace_events(runs) if e["event"] == "human_score"]
    assert len(events) == 2
    assert any(e["payload"].get("note") == "worth keeping" for e in events)


def test_t612_the_trace_is_never_corrupted_by_appending(client, runs):
    """The fixture's trace has NO trailing newline. Appending blind would
    concatenate the new record onto the last line and destroy both - in the
    file every figure in the report is derived from."""
    client.post("/api/runs/demo/scores",
                json={"papers": [{"paper_id": "W1", "score": 3}]})
    events = _trace_events(runs)          # fails loudly on a malformed line
    assert events[0]["event"] == "run_end"
    assert events[-1]["event"] == "human_score"


# --------------------------------------------------------------------------
# Against a real database
# --------------------------------------------------------------------------


def _live_db() -> bool:
    if not database_url():
        return False
    from researchgpt.db.session import bootstrap

    return bootstrap()


@pytest.fixture
def clean_db():
    """Remove this test's rows afterwards.

    These tests write to the developer's REAL database - there is no test
    instance (`DB_SCHEMA.md §8`: no Alembic, one database, drop and recreate).
    Without this, every run leaves synthetic judgements behind and the
    evaluation data slowly fills with rows no human ever wrote.
    """
    ids = ("demo-live", "demo-ck")
    yield ids
    from sqlalchemy import text

    session = get_session()
    if session is None:
        return
    try:
        for table in ("paper_scores", "artefact_scores"):
            session.execute(text(f"DELETE FROM {table} WHERE run_id = ANY(:ids)"),
                            {"ids": list(ids)})
        session.commit()
    finally:
        session.close()


@pytest.mark.skipif(not _live_db(), reason="T-620 not done: no live Postgres")
def test_t612_round_trip_against_a_real_database(runs, clean_db):
    """Scores reach Postgres and come back, and re-scoring updates the row
    rather than inserting a second one."""
    scores_module.save_scores(
        "demo-live",
        papers=[{"paper_id": "W1", "doi": "10.1/x", "title": "Paper One",
                 "score": 4, "note": "ok"}],
        artefact={"artefact": "review.md", "score": 3, "note": None},
    )
    scores_module.save_scores(
        "demo-live",
        papers=[{"paper_id": "W1", "doi": "10.1/x", "title": "Paper One",
                 "score": 1, "note": "changed my mind"}],
        artefact=None,
    )
    back = scores_module.get_scores("demo-live")
    assert back is not None
    assert len(back["papers"]) == 1, "re-scoring inserted a duplicate row"
    assert back["papers"][0]["score"] == 1
    assert back["papers"][0]["note"] == "changed my mind"
    assert back["artefact"]["score"] == 3


@pytest.mark.skipif(not _live_db(), reason="T-620 not done: no live Postgres")
@pytest.mark.parametrize("bad", [0, 6])
def test_t612_the_database_itself_rejects_an_out_of_range_score(bad, clean_db):
    """Validation lives in the schema too, not only in Pydantic: a score
    written by anything other than the API must still be 1-5."""
    import sqlalchemy

    from researchgpt.db.models import PaperScore
    from researchgpt.db.session import get_session

    session = get_session()
    assert session is not None
    try:
        session.add(PaperScore(run_id="demo-ck", paper_id="W1",
                               title="t", score=bad))
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_t612_schema_documents_the_new_tables():
    """DB_SCHEMA.md is the contract for this database; two tables landing in it
    without a section is how the next person finds them by surprise."""
    repo = pathlib.Path(__file__).resolve().parents[1]
    doc = (repo / "documents" / "DB_SCHEMA.md").read_text(encoding="utf-8")
    assert "paper_scores" in doc
    assert "artefact_scores" in doc


def test_t612_an_empty_mirror_does_not_claim_to_hold_anything(runs, monkeypatch):
    """🔴 get_scores() returns {"papers": [], "artefact": None} for a run with
    no scores - a truthy dict. Testing it for truthiness reported `trace+db` on
    a sheet nobody had ever scored, which tells the reviewer the database holds
    a judgement that does not exist."""
    monkeypatch.setattr(scores_module, "get_scores",
                        lambda run_id: {"papers": [], "artefact": None})
    sheet = TestClient(app).get("/api/runs/demo/scores").json()
    assert sheet["persisted"] == "trace"


def test_t612_a_populated_mirror_is_reported(runs, monkeypatch):
    monkeypatch.setattr(scores_module, "get_scores", lambda run_id: {
        "papers": [{"paper_id": "W1", "doi": None, "title": "t", "score": 4,
                    "note": None, "reviewer": "human"}],
        "artefact": None,
    })
    sheet = TestClient(app).get("/api/runs/demo/scores").json()
    assert sheet["persisted"] == "trace+db"
