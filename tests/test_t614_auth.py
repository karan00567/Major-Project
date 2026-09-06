"""T-614 acceptance — accounts, JWTs, and run ownership.

Every test here carries ``no_auth_bypass``, so it runs against the real
dependency rather than conftest's synthetic identity. That is the point: the
bypass exists so the older suites still test what they were written to test,
and this file exists so the bypass cannot hide a hole.

The password and token tests need no database. The isolation tests do, and skip
cleanly when there is none — `T-625`'s rule that the project runs without
Postgres still applies to the test suite.
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from researchgpt.api.app import app

pytestmark = pytest.mark.no_auth_bypass


# -- passwords and tokens (no database needed) -----------------------------


def test_a_password_round_trips_and_a_wrong_one_does_not():
    from researchgpt.db.users import hash_password, verify_password

    h = hash_password("Karan*123")
    assert h != "Karan*123", "the password must not be stored in clear text"
    assert verify_password("Karan*123", h)
    assert not verify_password("karan*123", h), "must be case sensitive"


def test_verify_password_against_a_missing_hash_is_false_not_an_error():
    """A login for an address with no account must fail, not raise.

    It must also still pay the bcrypt cost — see db/users.py — or the latency
    difference tells an attacker which addresses are registered.
    """
    from researchgpt.db.users import verify_password

    assert verify_password("anything", None) is False


def test_a_password_over_bcrypts_72_byte_cap_is_refused_not_truncated():
    """bcrypt silently ignores everything past 72 bytes. Accepting a longer
    password would mean two different passwords opening the same account."""
    from researchgpt.db.users import PasswordRejected, hash_password

    with pytest.raises(PasswordRejected):
        hash_password("x" * 73)


def test_a_short_password_is_refused():
    from researchgpt.db.users import PasswordRejected, hash_password

    with pytest.raises(PasswordRejected):
        hash_password("short7c")


def test_a_token_round_trips():
    from researchgpt.db.users import decode_token, make_token_for

    token = make_token_for("11111111-1111-1111-1111-111111111111", "a@b.c")
    claims = decode_token(token)
    assert claims["sub"] == "11111111-1111-1111-1111-111111111111"
    assert claims["email"] == "a@b.c"


def test_a_token_signed_with_another_key_is_rejected():
    import jwt

    from researchgpt.db.users import decode_token

    forged = jwt.encode({"sub": "x", "exp": 9999999999}, "not-the-secret",
                        algorithm="HS256")
    assert decode_token(forged) is None


def test_an_alg_none_token_is_rejected():
    """The classic JWT forgery: strip the signature and set ``alg`` to none.

    It works against any decoder that trusts the token's own header to choose
    the algorithm, which is why ``decode_token`` pins ``algorithms=[HS256]``.
    """
    from researchgpt.db.users import decode_token

    def seg(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    forged = f"{seg({'alg': 'none', 'typ': 'JWT'})}.{seg({'sub': 'x', 'exp': 9999999999})}."
    assert decode_token(forged) is None


def test_an_expired_token_is_rejected(monkeypatch):
    from datetime import timedelta

    from researchgpt.db import users as users_db

    monkeypatch.setattr(users_db, "TOKEN_TTL", timedelta(seconds=-1))
    token = users_db.make_token_for("11111111-1111-1111-1111-111111111111", "a@b.c")
    assert users_db.decode_token(token) is None


# -- the API surface --------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize("method,path", [
    ("get", "/api/runs"),
    ("get", "/api/runs/fixture/result"),
    ("get", "/api/runs/fixture/artifact/review.md"),
    ("get", "/api/runs/fixture/overrides"),
    ("get", "/api/auth/me"),
])
def test_protected_routes_refuse_an_anonymous_caller(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_starting_a_run_requires_an_account(client):
    body = {"question": "Does authentication actually gate this?", "max_papers": 5}
    assert client.post("/api/review", json=body).status_code == 401


def test_the_event_stream_refuses_a_caller_with_no_token(client):
    """SSE cannot send a header, so it authenticates on ?token=. Missing or
    junk must be refused just as firmly as a missing header elsewhere."""
    assert client.get("/api/runs/fixture/events").status_code == 401
    assert client.get("/api/runs/fixture/events?token=nonsense").status_code == 401


def test_health_stays_public(client):
    """The one route that must answer without a session: it is what the UI
    uses to discover fixture mode before anyone has signed in."""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "fixture_mode" in r.json()


def test_a_login_failure_does_not_reveal_whether_the_account_exists(client):
    """Distinguishing "no such user" from "wrong password" enumerates accounts."""
    unknown = client.post("/api/auth/login",
                          json={"email": "nobody@example.invalid", "password": "whatever1"})
    if unknown.status_code == 503:
        pytest.skip("no database configured")
    known_bad = client.post("/api/auth/login",
                            json={"email": "demo_account@gmail.com",
                                  "password": "definitely-wrong"})
    assert unknown.status_code == known_bad.status_code == 401
    assert unknown.json()["detail"] == known_bad.json()["detail"]


# -- isolation (needs a database) ------------------------------------------


def _db_or_skip():
    from researchgpt.db import session as S

    if not S.enabled() or not S.bootstrap():
        pytest.skip("no database configured")


def test_a_new_account_sees_none_of_another_accounts_runs(client):
    """The property the whole feature exists for."""
    _db_or_skip()
    import uuid

    email = f"iso-{uuid.uuid4().hex[:10]}@test.invalid"
    reg = client.post("/api/auth/register",
                      json={"email": email, "password": "ProbePass123"})
    assert reg.status_code == 201, reg.text
    token = reg.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}

    try:
        assert client.get("/api/runs", headers=auth).json() == []

        # A run that exists on disk and belongs to somebody else must be
        # indistinguishable from one that was never there: 404, not 403.
        for path in ("/api/runs/fixture/result",
                     "/api/runs/fixture/artifact/review.md"):
            assert client.get(path, headers=auth).status_code == 404

        assert client.get(f"/api/runs/fixture/events?token={token}").status_code == 404
    finally:
        from sqlalchemy import delete

        from researchgpt.db import session as S
        from researchgpt.db.models import User

        sess = S.get_session()
        if sess is not None:
            with sess as s:
                s.execute(delete(User).where(User.email == email))
                s.commit()


def test_a_new_account_is_not_an_admin_and_cannot_reach_the_scoring_sheet(client):
    """Privilege must not be self-service.

    ``is_admin`` is settable only by ``scripts/seed_accounts.py`` or psql — no
    route writes it, and ``update_profile`` cannot reach the column. So a
    freshly registered account is an ordinary user, and the T-612 sheet answers
    it with 403 rather than data.
    """
    _db_or_skip()
    import uuid

    email = f"nonadmin-{uuid.uuid4().hex[:10]}@test.invalid"
    reg = client.post("/api/auth/register",
                      json={"email": email, "password": "ProbePass123"})
    assert reg.status_code == 201, reg.text
    assert reg.json()["user"]["is_admin"] is False
    auth = {"Authorization": f"Bearer {reg.json()['token']}"}

    try:
        r = client.get("/api/runs/fixture/scores", headers=auth)
        assert r.status_code == 403
        assert "administrator" in r.json()["detail"].lower()

        posted = client.post("/api/runs/fixture/scores", headers=auth,
                             json={"papers": [], "artefact": None})
        assert posted.status_code == 403

        # And it cannot promote itself through the one route that writes to the
        # user row. `is_admin` is not a field on ProfileUpdate at all, so it is
        # dropped before any handler sees it.
        client.patch("/api/auth/profile", headers=auth,
                     json={"display_name": "x", "is_admin": True})
        assert client.get("/api/auth/me", headers=auth).json()["is_admin"] is False
    finally:
        from sqlalchemy import delete

        from researchgpt.db import session as S
        from researchgpt.db.models import User

        sess = S.get_session()
        if sess is not None:
            with sess as s:
                s.execute(delete(User).where(User.email == email))
                s.commit()


def test_the_demo_account_is_an_admin(client):
    """The graded demo signs in as this account and shows the scoring sheet."""
    _db_or_skip()
    r = client.post("/api/auth/login",
                    json={"email": "demo_account@gmail.com", "password": "Karan*123"})
    if r.status_code != 200:
        pytest.skip("demo account not seeded; run scripts/seed_accounts.py")
    assert r.json()["user"]["is_admin"] is True


def test_the_run_list_fails_closed_when_ownership_cannot_be_established(client,
                                                                        monkeypatch):
    """No ownership answer means NO runs, never all of them.

    This is the deliberate narrowing of `T-625`. Before accounts, "registry
    down" meant "serve the filesystem", which was right: the index was only an
    index. Once runs have owners the same fallback would serve one account
    another account's work, so ``run_ids_for`` returns ``None`` rather than an
    empty set and the endpoint turns that into a 503.

    Getting this backwards is the classic authorisation bug — degrade to open
    instead of closed — so it gets its own test.
    """
    _db_or_skip()
    import researchgpt.api.app as app_module
    from researchgpt.db import users as users_db

    r = client.post("/api/auth/login",
                    json={"email": "demo_account@gmail.com", "password": "Karan*123"})
    if r.status_code != 200:
        pytest.skip("demo account not seeded; run scripts/seed_accounts.py")
    auth = {"Authorization": f"Bearer {r.json()['token']}"}

    assert client.get("/api/runs", headers=auth).status_code == 200

    monkeypatch.setattr(users_db, "run_ids_for", lambda _uid: None)
    assert client.get("/api/runs", headers=auth).status_code == 503
    # And a single run is refused too, not just the listing.
    monkeypatch.setattr(app_module, "_require_owner",
                        app_module._require_owner)  # unchanged; uses the patch above
    assert client.get("/api/runs/fixture/result",
                      headers=auth).status_code == 503


def test_registering_the_same_email_twice_is_refused(client):
    _db_or_skip()
    import uuid

    email = f"dupe-{uuid.uuid4().hex[:10]}@test.invalid"
    body = {"email": email, "password": "ProbePass123"}
    try:
        assert client.post("/api/auth/register", json=body).status_code == 201
        assert client.post("/api/auth/register", json=body).status_code == 409
    finally:
        from sqlalchemy import delete

        from researchgpt.db import session as S
        from researchgpt.db.models import User

        sess = S.get_session()
        if sess is not None:
            with sess as s:
                s.execute(delete(User).where(User.email == email))
                s.commit()


def test_an_email_is_stored_lower_cased_so_case_cannot_fork_an_account(client):
    _db_or_skip()
    import uuid

    stem = f"Case-{uuid.uuid4().hex[:10]}"
    email = f"{stem}@Test.Invalid"
    try:
        reg = client.post("/api/auth/register",
                          json={"email": email, "password": "ProbePass123"})
        assert reg.status_code == 201
        assert reg.json()["user"]["email"] == email.lower()

        # And the same address in a different case signs into the same account.
        again = client.post("/api/auth/login",
                            json={"email": email.upper(), "password": "ProbePass123"})
        assert again.status_code == 200
    finally:
        from sqlalchemy import delete

        from researchgpt.db import session as S
        from researchgpt.db.models import User

        sess = S.get_session()
        if sess is not None:
            with sess as s:
                s.execute(delete(User).where(User.email == email.lower()))
                s.commit()
