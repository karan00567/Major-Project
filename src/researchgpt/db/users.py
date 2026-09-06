"""T-614 — accounts, passwords and JWTs.

Kept under ``db/`` for the same reason the registry is: it imports SQLAlchemy at
module scope, and `T-625` forbids anything on the pipeline's import path from
doing that. Nothing in ``agents/``, ``graph/`` or ``core/`` imports this file.

**Three things here are security-relevant and are not style choices.**

1. ``verify_password`` runs bcrypt even when the email matched no user. Skipping
   it would make a miss return in microseconds and a hit in ~200 ms, which is a
   timing oracle for "does this address have an account here".
2. ``login`` returns the same message for "no such user" and "wrong password".
   Distinguishing them enumerates accounts for free.
3. The JWT secret is read from the environment. A hard-coded fallback would be
   the same secret on every deployment, i.e. anyone who has read this file can
   mint a token for any account. If ``JWT_SECRET`` is unset a random one is
   generated per process, which is safe but logs every user out on restart.
"""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from sqlalchemy import select

from researchgpt.db import session as S
from researchgpt.db.models import Run, User

log = logging.getLogger(__name__)

ALGORITHM = "HS256"
#: Long enough that a demo is never interrupted by a re-login.
TOKEN_TTL = timedelta(hours=12)

#: bcrypt truncates silently at 72 BYTES. A longer password would have its tail
#: ignored with no error, so it is rejected instead of quietly weakened.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LEN = 8

_SECRET: str | None = None


def jwt_secret() -> str:
    """The signing key. Environment first; a per-process random one otherwise."""
    global _SECRET
    if _SECRET is None:
        env = (os.getenv("JWT_SECRET") or "").strip()
        if env:
            _SECRET = env
        else:
            _SECRET = secrets.token_urlsafe(48)
            log.warning(
                "JWT_SECRET is not set; generated an ephemeral one. Tokens will "
                "not survive an API restart. Set JWT_SECRET in .env."
            )
    return _SECRET


# -- passwords -------------------------------------------------------------


class PasswordRejected(ValueError):
    """The password cannot be stored as given (too short, or over bcrypt's cap)."""


def hash_password(plain: str) -> str:
    raw = plain.encode("utf-8")
    if len(plain) < MIN_PASSWORD_LEN:
        raise PasswordRejected(
            f"Password must be at least {MIN_PASSWORD_LEN} characters."
        )
    if len(raw) > MAX_PASSWORD_BYTES:
        raise PasswordRejected(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes "
            "(bcrypt truncates beyond that, so a longer one would be silently cut)."
        )
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Constant-ish time check. ``hashed=None`` still pays the bcrypt cost."""
    raw = plain.encode("utf-8")[:MAX_PASSWORD_BYTES]
    if not hashed:
        # Burn a comparable amount of time against a throwaway hash so that a
        # missing account is not distinguishable by latency. See module docs.
        bcrypt.checkpw(raw, bcrypt.hashpw(b"decoy", bcrypt.gensalt()))
        return False
    try:
        return bcrypt.checkpw(raw, hashed.encode("utf-8"))
    except ValueError:
        return False  # a corrupt hash is a failed login, not a 500


# -- tokens ----------------------------------------------------------------


def make_token_for(user_id: str | uuid.UUID, email: str) -> str:
    """Sign a token from plain values.

    The primitive takes ids rather than a ``User`` so it can be called after the
    session that loaded the row has closed — touching a detached ORM instance
    raises ``DetachedInstanceError``, which is a confusing way to fail a login.
    """
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int((now + TOKEN_TTL).timestamp()),
        },
        jwt_secret(),
        algorithm=ALGORITHM,
    )


def make_token(user: User) -> str:
    """Convenience wrapper for a live ORM instance."""
    return make_token_for(user.id, user.email)


def decode_token(token: str) -> dict[str, Any] | None:
    """Claims, or ``None`` for anything not currently valid.

    ``algorithms`` is pinned to one entry deliberately: accepting the token's
    own ``alg`` header is the classic JWT forgery, where an attacker sets it to
    ``none`` (or to HS256 against an RS256 public key) and signs their own.
    """
    try:
        return jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


# -- queries ---------------------------------------------------------------


def normalise_email(email: str) -> str:
    return (email or "").strip().lower()


class EmailTaken(ValueError):
    pass


def create_user(email: str, password: str, display_name: str | None = None) -> dict:
    """Register. Raises :class:`EmailTaken` or :class:`PasswordRejected`."""
    email = normalise_email(email)
    pw_hash = hash_password(password)  # before touching the DB, so a bad
    # password never opens a transaction
    sm = S.get_session()
    if sm is None:
        raise RuntimeError("The account database is unavailable.")
    with sm as s:
        if s.scalar(select(User).where(User.email == email)):
            raise EmailTaken("That email already has an account.")
        user = User(email=email, password_hash=pw_hash,
                    display_name=(display_name or "").strip() or None)
        s.add(user)
        s.commit()
        s.refresh(user)
        return user.as_public()


def authenticate(email: str, password: str) -> dict | None:
    """The public dict on success, ``None`` on any failure."""
    email = normalise_email(email)
    sm = S.get_session()
    if sm is None:
        raise RuntimeError("The account database is unavailable.")
    with sm as s:
        user = s.scalar(select(User).where(User.email == email))
        if not verify_password(password, user.password_hash if user else None):
            return None
        user.last_login_at = datetime.now(UTC)
        s.commit()
        s.refresh(user)
        return {**user.as_public(), "_token": make_token(user)}


def get_user(user_id: str | uuid.UUID) -> dict | None:
    sm = S.get_session()
    if sm is None:
        return None
    try:
        uid = uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        return None
    with sm as s:
        user = s.get(User, uid)
        return user.as_public() if user else None


def update_profile(user_id: str, *, display_name: str | None = None,
                   email: str | None = None,
                   new_password: str | None = None,
                   current_password: str | None = None) -> dict:
    """Change the profile. Changing email or password requires the current one.

    Re-authenticating for those two is not ceremony: a token left open on a
    shared demo laptop would otherwise be enough to take the account over.
    """
    sm = S.get_session()
    if sm is None:
        raise RuntimeError("The account database is unavailable.")
    with sm as s:
        user = s.get(User, uuid.UUID(str(user_id)))
        if user is None:
            raise LookupError("No such account.")

        wants_sensitive = bool(new_password) or (
            email is not None and normalise_email(email) != user.email
        )
        if wants_sensitive and not verify_password(
            current_password or "", user.password_hash
        ):
            raise PermissionError(
                "Enter your current password to change your email or password."
            )

        if display_name is not None:
            user.display_name = display_name.strip() or None
        if email is not None:
            new_email = normalise_email(email)
            if new_email != user.email:
                if s.scalar(select(User).where(User.email == new_email)):
                    raise EmailTaken("That email already has an account.")
                user.email = new_email
        if new_password:
            user.password_hash = hash_password(new_password)

        s.commit()
        s.refresh(user)
        return user.as_public()


# -- run ownership ---------------------------------------------------------


def claim_run(run_id: str, user_id: str) -> bool:
    """Stamp a run with its owner. Best-effort, like everything in the registry.

    Returns False rather than raising when the registry is down: a pipeline run
    must not fail because its index could not record who started it.
    """
    sm = S.get_session()
    if sm is None:
        return False
    try:
        with sm as s:
            run = s.scalar(select(Run).where(Run.run_id == run_id))
            if run is None:
                return False
            run.user_id = uuid.UUID(str(user_id))
            s.commit()
            return True
    except Exception:  # pragma: no cover - best effort by contract
        log.warning("could not record the owner of run %s", run_id, exc_info=True)
        return False


def run_ids_for(user_id: str) -> set[str] | None:
    """Every ``run_id`` this user owns, or ``None`` if the registry is down.

    ``None`` and ``set()`` mean different things and the caller must tell them
    apart: an empty set is "you have no runs", ``None`` is "ownership could not
    be established", and listing everything in the second case would show one
    account another account's work.
    """
    sm = S.get_session()
    if sm is None:
        return None
    try:
        with sm as s:
            rows = s.scalars(
                select(Run.run_id).where(Run.user_id == uuid.UUID(str(user_id)))
            ).all()
            return set(rows)
    except Exception:
        log.warning("could not read run ownership", exc_info=True)
        return None


__all__ = [
    "authenticate", "claim_run", "create_user", "decode_token", "EmailTaken",
    "get_user", "make_token", "make_token_for", "PasswordRejected",
    "run_ids_for", "update_profile", "hash_password", "verify_password",
    "jwt_secret",
]
