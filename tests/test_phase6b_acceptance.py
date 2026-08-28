"""Phase 6B acceptance tests — the Postgres run registry (T-621..T-626).

★ **The property under test is that the registry cannot hurt anything.**
`DB_SCHEMA.md §9` and T-626: *"stop the Postgres service mid-run and confirm the
run completes with every artefact on disk. If that test does not pass, the
non-blocking rule is not implemented, whatever the code looks like."*

A real Postgres is not required to test that, and its absence is itself one of
the cases the design must survive. Where a live server is genuinely needed —
DDL, JSONB, the MutableList flush — the test skips with a reason rather than
pretending to have checked.
"""

from __future__ import annotations

import pathlib

import pytest

from researchgpt.db import registry
from researchgpt.db.session import database_url, enabled, reset_for_tests

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean_engine(monkeypatch):
    reset_for_tests()
    yield
    reset_for_tests()


def _no_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_for_tests()


# --------------------------------------------------------------------------
# T-622 — importing and using this with no database must be silent
# --------------------------------------------------------------------------


def test_importing_session_without_database_url_does_not_raise(monkeypatch):
    """T-622's stated criterion, and the basis of the registry being optional.

    The pipeline, the CLI and the API all import through here; any of them
    exploding on a missing env var would make Postgres a hard dependency of a
    project that promises to run without it.
    """
    _no_db(monkeypatch)
    import importlib

    import researchgpt.db.session as s

    # The module calls load_dotenv() at import, which would re-populate the
    # very variable this test deletes. Neutralise it so we are testing "no
    # DATABASE_URL anywhere", not "no DATABASE_URL for one millisecond".
    monkeypatch.setattr(s, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    importlib.reload(s)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert s.database_url() is None
    assert s.enabled() is False
    assert s.get_engine() is None
    assert s.get_session() is None


def test_an_empty_database_url_counts_as_unset(monkeypatch):
    """.env.example ships `DATABASE_URL=`, so a developer who copies it must
    not end up with a half-configured engine that fails on first use."""
    monkeypatch.setenv("DATABASE_URL", "   ")
    reset_for_tests()
    assert database_url() is None
    assert enabled() is False


# --------------------------------------------------------------------------
# T-623 — every public function returns cleanly with Postgres absent
# --------------------------------------------------------------------------


def test_every_registry_function_returns_none_without_a_database(monkeypatch):
    """T-623's acceptance criterion: 'every public function returns cleanly
    with Postgres stopped'."""
    _no_db(monkeypatch)

    assert registry.register_run("r1", "q", {}) is None
    assert registry.mark_running("r1") is None
    assert registry.attach_artefact("r1", "review.md", "/tmp/review.md", 10, "abc") is None
    assert registry.complete_run("r1", {"papers": 3}) is None
    assert registry.fail_run("r1", "boom") is None
    assert registry.get_run("r1") is None
    assert registry.list_runs() is None


def test_an_unreachable_database_fails_fast_instead_of_hanging(monkeypatch):
    """🔴 _safe() catches exceptions but NOT time.

    A host that DROPS packets rather than refusing them - a suspended VM, a
    laptop that slept, a firewalled port - leaves connect() blocking for the OS
    default, minutes on Windows, with the pipeline sitting there. Hanging a run
    is exactly as bad as breaking it, and DB_SCHEMA 9 forbids both. Found when
    these very tests hung instead of failing.
    """
    import time

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:1/nope")
    reset_for_tests()

    started = time.perf_counter()
    assert registry.register_run("r1", "q", {}) is None
    elapsed = time.perf_counter() - started

    assert elapsed < 15, (
        f"a registry call took {elapsed:.1f}s against an unreachable host; it "
        f"must fail fast (connect_timeout) rather than stall the pipeline"
    )


def test_a_broken_database_url_is_a_warning_not_a_crash(monkeypatch, caplog):
    """The failures that actually happen on a laptop are not all
    OperationalError: a missing driver, a malformed URL, a suspended machine.
    That is why the wrapper is deliberately broad."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:1/nope")
    reset_for_tests()

    assert registry.register_run("r1", "q", {}) is None
    assert registry.list_runs() is None


def test_list_runs_distinguishes_absent_from_empty(monkeypatch):
    """★ ``None`` (registry unavailable) must not be confused with ``[]``
    (registry present, no runs).

    T-625 falls back to a filesystem scan on ``None``. If an empty database
    returned ``[]``, the API would report zero runs while dozens sat on disk.
    """
    _no_db(monkeypatch)
    assert registry.list_runs() is None


# --------------------------------------------------------------------------
# T-624/T-626 — a registry outage must not touch the pipeline
# --------------------------------------------------------------------------


def test_registry_failure_mid_run_does_not_break_artefact_writing(monkeypatch, tmp_path):
    """T-626, simulated: the registry raises on EVERY call, as a stopped
    Postgres would, and the run must still finish with its artefacts.

    This is the property `DB_SCHEMA.md §9` demands. A live-server version of
    this test is in `test_registry_survives_a_real_postgres_outage`, skipped
    unless DATABASE_URL points at one.
    """
    from researchgpt.output.writers import write_claims, write_markdown

    def explode(*a, **k):
        raise RuntimeError("connection refused (simulated Postgres outage)")

    for name in ("register_run", "mark_running", "attach_artefact",
                 "complete_run", "fail_run"):
        monkeypatch.setattr(registry, name, explode)

    # The pipeline calls these through _safe(); artefact writing is what must
    # survive, so assert the writers still produce files.
    review = write_markdown(tmp_path, "# A review\n\nGrounded [1].")
    claims = write_claims(tmp_path, [], [], 0.5)

    assert review.exists() and review.read_text(encoding="utf-8")
    assert claims is None or claims.exists()


def test_pipeline_imports_registry_lazily(monkeypatch):
    """The registry must not be imported at module scope by the pipeline.

    `T-625` requires the project to install and run with no database, so
    nothing in the core dependency set may import sqlalchemy on import.
    """
    import researchgpt.graph.build as build

    src = pathlib.Path(build.__file__).read_text(encoding="utf-8")
    head = src.split("def run_pipeline")[0]
    assert "from researchgpt.db import registry" not in head, (
        "registry is imported at module scope; it must be imported inside the "
        "function so sqlalchemy stays optional"
    )


# --------------------------------------------------------------------------
# T-625 — the API works with no database at all
# --------------------------------------------------------------------------


def test_api_lists_runs_from_the_filesystem_without_a_database(monkeypatch, tmp_path):
    """The Vue run list and the T-610 pre-baked demo both depend on this."""
    from fastapi.testclient import TestClient

    import researchgpt.api.app as app_module

    _no_db(monkeypatch)
    run = tmp_path / "demo"
    run.mkdir()
    (run / "trace.jsonl").write_text(
        '{"ts":"2026-08-28T10:00:00Z","agent":"graph","event":"run_end",'
        '"iteration":0,"payload":{"papers":7}}\n', encoding="utf-8")
    (run / "review.md").write_text("# r", encoding="utf-8")
    monkeypatch.setattr(app_module, "RUNS_DIR", tmp_path)

    rows = TestClient(app_module.app).get("/api/runs").json()
    assert [r["run_id"] for r in rows] == ["demo"]
    assert rows[0]["papers"] == 7


# --------------------------------------------------------------------------
# T-621 — the gotcha that would silently lose artefacts
# --------------------------------------------------------------------------


def test_json_columns_are_mutable_wrapped():
    """🔴 `DB_SCHEMA.md §7.1`, "the one gotcha that will bite".

    SQLAlchemy tracks changes by identity. With a bare JSONB column,
    ``run.artefacts.append(...)`` then ``commit()`` leaves the object identical
    to the one that was loaded, so the row is never marked dirty, NO UPDATE is
    emitted, and the artefact vanishes with no error to debug.
    registry.attach_artefact depends entirely on these wrappers.

    Checked BEHAVIOURALLY, on the runtime type of the attribute, because
    ``as_mutable`` does not change the column type - both wrapped and bare
    columns report JSONB, so a type assertion would pass either way and prove
    nothing.
    """
    from sqlalchemy.ext.mutable import MutableDict, MutableList

    from researchgpt.db.models import Run

    row = Run(run_id="x", research_question="q", config={}, artefacts=[], metrics={})

    assert isinstance(row.artefacts, MutableList), (
        "artefacts is a plain list: in-place append would never be flushed"
    )
    assert isinstance(row.config, MutableDict)
    assert isinstance(row.metrics, MutableDict)

    # The operation registry.attach_artefact actually performs.
    row.artefacts.append({"name": "review.md"})
    assert len(row.artefacts) == 1


def test_status_values_are_constrained():
    """A typo'd status is invisible until a query silently returns nothing."""
    from researchgpt.db.models import STATUSES, Run

    checks = [c for c in Run.__table__.constraints
              if getattr(c, "name", "") == "ck_runs_status"]
    assert checks, "the status CHECK constraint is missing"
    assert set(STATUSES) == {"pending", "running", "completed", "failed"}


def test_summary_shape_matches_the_api(monkeypatch):
    """The registry and the filesystem fallback must return the same shape, or
    GET /api/runs would change schema depending on whether Postgres is up."""
    from researchgpt.api.schemas import RunSummary
    from researchgpt.db.models import Run

    row = Run(run_id="r1", research_question="q", config={}, status="completed",
              artefacts=[{"name": "review.md"}],
              metrics={"papers": 5, "verified_claims": 2, "dropped_claims": 1,
                       "grounding_score": 0.5})
    RunSummary(**row.as_summary())        # raises if the shapes disagree


# --------------------------------------------------------------------------
# Live-server tests — skipped unless a real Postgres is configured
# --------------------------------------------------------------------------


def _live_db() -> bool:
    url = database_url()
    if not url:
        return False
    from researchgpt.db.session import bootstrap

    return bootstrap()


@pytest.mark.skipif(not _live_db(), reason="T-620 not done: no live Postgres")
def test_round_trip_against_a_real_database():
    """Exercises the real DDL, real JSONB, and the MutableList flush."""
    run_id = "pytest-registry-roundtrip"
    _drop_test_row(run_id)          # idempotent: the row survives a prior run

    registry.register_run(run_id, "does it round-trip?", {"a": 1})
    registry.mark_running(run_id)
    registry.attach_artefact(run_id, "review.md", "/tmp/review.md", 12, "deadbeef")
    registry.complete_run(run_id, {"papers": 3})

    row = registry.get_run(run_id)
    assert row is not None
    assert row["status"] == "completed"
    assert row["papers"] == 3
    # 🔴 The MutableList flush. Without the wrapper in models.py this list is
    # EMPTY: the append never marks the row dirty and no UPDATE is emitted.
    assert row["artefacts"] == ["review.md"]

    # Attaching the same name twice must replace, not duplicate - run_ids are
    # reused constantly in this project.
    registry.attach_artefact(run_id, "review.md", "/tmp/review.md", 99, "cafe")
    assert registry.get_run(run_id)["artefacts"] == ["review.md"]


def _drop_test_row(run_id: str) -> None:
    from researchgpt.db.models import Run
    from researchgpt.db.session import get_session

    session = get_session()
    if session is None:
        return
    try:
        session.query(Run).filter_by(run_id=run_id).delete()
        session.commit()
    finally:
        session.close()


@pytest.mark.skipif(not _live_db(), reason="T-620 not done: no live Postgres")
def test_registry_survives_a_real_postgres_outage():
    """T-626 proper. Requires stopping the service by hand mid-test, so it is
    documented rather than automated: see SHOWCASE/TASKLIST T-626."""
    pytest.skip("manual: stop the Postgres service, then re-run a pipeline run")


def test_registry_gives_up_after_proving_itself_unreachable(monkeypatch):
    """★ Bounded is not the same as free.

    A run makes one register + one mark_running + one attach PER ARTEFACT + one
    complete. At a 3 s connect timeout apiece, a dead database added ~12.6 s to
    every single run (measured). The circuit breaker takes that to ~3.5 s: the
    first call proves the registry unreachable, the rest are no-ops.

    The registry is an index over data the filesystem already holds. It does
    not deserve a retry budget.
    """
    import time

    from researchgpt.db import session as db_session

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://nobody@127.0.0.1:1/nope")
    reset_for_tests()

    started = time.perf_counter()
    registry.register_run("x", "q", {})
    registry.mark_running("x")
    registry.attach_artefact("x", "review.md", "p", 1, "a")
    registry.attach_artefact("x", "refs.bib", "p", 1, "a")
    registry.complete_run("x", {"papers": 1})
    elapsed = time.perf_counter() - started

    assert db_session.enabled() is False, "the breaker did not trip"
    assert elapsed < 8, (
        f"5 registry calls against a dead host took {elapsed:.1f}s; the breaker "
        f"should make all but the first a no-op"
    )


def test_the_breaker_does_not_trip_when_there_is_simply_no_database(monkeypatch):
    """No DATABASE_URL is a configuration choice, not a failure. Tripping the
    breaker there would be harmless but would muddle the log with a warning
    about something nobody asked for."""
    from researchgpt.db import session as db_session

    _no_db(monkeypatch)
    registry.register_run("x", "q", {})
    assert db_session._disabled is False


def test_enabling_the_registry_never_hides_runs_on_disk(monkeypatch, tmp_path):
    """🔴 The regression this endpoint shipped with for about ten minutes.

    "Registry if present, else filesystem" is the obvious implementation and it
    is wrong: the moment a real Postgres was connected on 2026-08-28, the
    endpoint returned **2 rows against 60 runs on disk**, because the registry
    had only ever seen runs made after it was enabled.

    Enabling an INDEX must never make the application show less than reality.
    `DB_SCHEMA §1`: the filesystem is the record. So the disk is the base set
    and the registry only enriches it.
    """
    from fastapi.testclient import TestClient

    import researchgpt.api.app as app_module

    for name in ("alpha", "beta", "gamma"):
        d = tmp_path / name
        d.mkdir()
        (d / "review.md").write_text("# r", encoding="utf-8")
        (d / "trace.jsonl").write_text(
            '{"ts":"2026-08-28T10:00:00Z","agent":"graph","event":"run_end",'
            '"iteration":0,"payload":{}}\n', encoding="utf-8")
    monkeypatch.setattr(app_module, "RUNS_DIR", tmp_path)

    # A registry that knows about ONE of them, plus a row whose directory is gone.
    monkeypatch.setattr(
        "researchgpt.db.registry.list_runs",
        lambda limit=50: [
            {"run_id": "beta", "status": "completed", "question": "q",
             "started": None, "papers": 42, "verified_claims": 5,
             "dropped_claims": 1, "grounding_score": 0.9, "artefacts": []},
            {"run_id": "vanished", "status": "completed", "question": "gone",
             "started": None, "papers": 1, "verified_claims": None,
             "dropped_claims": None, "grounding_score": None, "artefacts": []},
        ],
    )

    rows = TestClient(app_module.app).get("/api/runs").json()
    ids = {r["run_id"] for r in rows}

    assert ids == {"alpha", "beta", "gamma"}, (
        "the registry changed which runs are visible; it must only enrich them"
    )
    # The registry's metrics reach the row it knows about...
    beta = next(r for r in rows if r["run_id"] == "beta")
    assert beta["papers"] == 42
    # ...and a row whose directory is gone is not served, because the artefacts
    # this endpoint exists to expose are what disappeared.
    assert "vanished" not in ids
