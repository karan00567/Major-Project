"""T-614 — the FastAPI side of authentication: one dependency, two flavours.

``current_user`` rejects; ``optional_user`` does not. Both read the same bearer
token, so there is one place that decides what a request's identity is.

⚠️ **Import this lazily inside route bodies, never at ``app.py`` module scope.**
It reaches ``researchgpt.db.users``, which imports SQLAlchemy, and `T-625`
requires the API module to import with no database driver assumptions. The
existing ``scores_db`` import is the precedent.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

BEARER = "bearer"


def _token_from(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != BEARER or not token.strip():
        return None
    return token.strip()


def optional_user(request: Request) -> dict | None:
    """The caller's account, or ``None``. Never raises.

    Used by routes that must keep working unauthenticated — health, and the
    fixture replay the demo depends on.
    """
    token = _token_from(request)
    if not token:
        return None
    from researchgpt.db import users as users_db

    claims = users_db.decode_token(token)
    if not claims:
        return None
    return users_db.get_user(claims.get("sub"))


def current_user(request: Request) -> dict:
    """The caller's account, or 401.

    401 rather than 403 throughout: the caller has not proved who they are, and
    `RFC 9110` reserves 403 for "I know who you are and you still may not".
    """
    token = _token_from(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from researchgpt.db import users as users_db

    claims = users_db.decode_token(token)
    if not claims:
        raise HTTPException(
            status_code=401,
            detail="Your session has expired. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = users_db.get_user(claims.get("sub"))
    if user is None:
        # A validly-signed token for an account that no longer exists, or a
        # registry that has gone away. Either way the request has no identity.
        raise HTTPException(
            status_code=401,
            detail="That account is no longer available.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    """An administrator, or 403.

    **403 here, unlike the 404 used for run ownership.** The two are different
    questions and deserve different answers: a run you do not own should not be
    confirmed to exist, but the scoring sheet is a known, fixed part of the
    application, so hiding its existence buys nothing and "you are signed in but
    not an administrator" is the honest and more useful reply.

    ⚠️ Takes ``current_user`` as a **Depends**, not by calling it. Calling it
    directly resolves the real function every time and steps outside FastAPI's
    dependency graph, so ``app.dependency_overrides[current_user]`` would not
    reach it — which silently 401s every admin route under test while the
    non-admin routes pass.
    """
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="This area is for administrators.",
        )
    return user


CurrentUser = Depends(current_user)
OptionalUser = Depends(optional_user)
AdminUser = Depends(admin_user)

__all__ = ["current_user", "optional_user", "admin_user",
           "CurrentUser", "OptionalUser", "AdminUser"]
