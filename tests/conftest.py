"""Shared test setup.

T-614 put every run-scoped API route behind a bearer token and an ownership
check. The Phase 6 and T-612 suites predate accounts: they point ``RUNS_DIR`` at
a ``tmp_path`` holding a run that, by construction, has no registry row and
therefore no owner. Left alone, every one of those tests would now assert
against a 401 or a 404 and tell us nothing about what it was written to check.

So the bypass below supplies a synthetic identity to those suites. **It is
deliberately opt-out rather than opt-in**, because the alternative — editing a
token into ~40 existing assertions — would have buried the behaviour those tests
exist to pin down under authentication boilerplate.

⚠️ **The bypass would happily hide a broken auth layer, so it must never be the
only thing in the suite.** ``test_t614_auth.py`` carries the
``no_auth_bypass`` marker and exercises the real dependency: unauthenticated
rejection, cross-account isolation, and token forgery. If you add a security
property, add it there, not here.
"""

from __future__ import annotations

import pytest

#: A stable fake account for the pre-T-614 suites. The uuid is obviously
#: synthetic so it cannot be confused with a row in anyone's database.
#: ``is_admin`` is True because the T-612 scoring suite exercises routes that
#: are now administrator-only. That the bypass hands out admin is exactly why
#: ``test_t614_auth.py`` has to check the 403 for itself, without it.
TEST_USER = {
    "id": "00000000-0000-0000-0000-000000000001",
    "email": "suite@test.invalid",
    "display_name": "Test Suite",
    "is_admin": True,
    "created_at": "2026-01-01T00:00:00Z",
}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "no_auth_bypass: run against the real authentication dependency",
    )


@pytest.fixture(autouse=True)
def _auth_bypass(request, monkeypatch):
    """Give the API suites an identity that owns every run they create."""
    if request.node.get_closest_marker("no_auth_bypass"):
        yield
        return

    try:
        from researchgpt.api import app as app_module
        from researchgpt.api.auth import current_user, optional_user
    except Exception:
        # Suites that never touch the API (the verifier, the reranker, the
        # graph) must not fail to collect because FastAPI is missing.
        yield
        return

    app_module.app.dependency_overrides[current_user] = lambda: TEST_USER
    app_module.app.dependency_overrides[optional_user] = lambda: TEST_USER
    # Ownership is a database question, and these suites have no rows. Both
    # helpers are looked up as module globals at call time, so patching the
    # module attribute reaches every route.
    monkeypatch.setattr(app_module, "_require_owner", lambda run_id, user: None)
    monkeypatch.setattr(app_module, "_user_from_query_token", lambda token: TEST_USER)

    # ⚠️ `list_runs` does NOT go through `_require_owner`: it filters the whole
    # listing against the set of run ids this account owns, so patching the
    # per-run guard alone leaves it returning an empty list. Ownership is
    # answered here by "every directory on disk", which restores the pre-T-614
    # contract those suites were written against.
    def _owns_everything(_user_id):
        runs_dir = app_module.RUNS_DIR
        if not runs_dir.is_dir():
            return set()
        return {d.name for d in runs_dir.iterdir() if d.is_dir()}

    from researchgpt.db import users as users_db

    monkeypatch.setattr(users_db, "run_ids_for", _owns_everything)

    yield

    app_module.app.dependency_overrides.pop(current_user, None)
    app_module.app.dependency_overrides.pop(optional_user, None)
