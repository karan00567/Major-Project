"""T-622 — engine and session factory. `DB_SCHEMA.md §8`.

★ **Importing this module with ``DATABASE_URL`` unset must not raise.** That is
T-622's stated acceptance criterion and it is the whole basis of the registry
being optional: the pipeline, the CLI and the API all import through here, and
any of them exploding on a missing environment variable would make Postgres a
hard dependency of a project that promises to run without it (T-625).

**No Alembic.** `DB_SCHEMA.md §8`: one table, no production data, and every run
is reconstructible from ``outputs/runs/``. ``create_all`` at first use is
correct here; a migration tool would be correct engineering and wrong for the
timeline. If the schema changes, drop and recreate.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

log = logging.getLogger(__name__)

#: Seconds to wait for a TCP connect before giving up on the registry.
#: Deliberately short: this is an index over data the filesystem already holds,
#: so waiting on it is never worth more than a moment of a pipeline run.
CONNECT_TIMEOUT_S = 3

#: ★ Circuit breaker. Once the registry has proved unreachable, stop trying for
#: the rest of the process.
#:
#: Without it every registry call pays the full connect timeout: a pipeline run
#: makes one register + one mark_running + one attach per artefact + one
#: complete, so a dead database added ~12 s to every run (measured). Bounded is
#: not the same as free, and the registry is an index over data the filesystem
#: already holds — it does not deserve a retry budget.
#:
#: Deliberately process-scoped rather than time-based: a run is minutes long,
#: and re-probing a database that was down 30 seconds ago just re-pays the
#: timeout. ``reset_for_tests()`` clears it, and so does a restart.
_disabled = False

_engine: Any = None
_sessionmaker: Any = None
_bootstrapped = False
_LOCK = threading.Lock()


def database_url() -> str | None:
    """The configured URL, or ``None`` when the registry is disabled.

    An empty string counts as unset: ``.env.example`` ships
    ``DATABASE_URL=`` so a developer who copies it does not accidentally get a
    half-configured engine that fails on first use.
    """
    url = (os.getenv("DATABASE_URL") or "").strip()
    return url or None


def enabled() -> bool:
    """False once the registry has been proved unreachable this process."""
    return not _disabled and database_url() is not None


def _trip_breaker(reason: str) -> None:
    global _disabled
    if not _disabled:
        _disabled = True
        log.warning(
            "run registry disabled for this process after: %s. The pipeline is "
            "unaffected - outputs/runs/ remains the record (DB_SCHEMA 1).",
            reason,
        )


def get_engine() -> Any:
    """The lazily-built engine, or ``None`` if unconfigured/unavailable.

    Built lazily rather than at import: a module-level engine would turn a
    missing driver into an ImportError for every consumer of this package.
    """
    global _engine, _sessionmaker
    url = database_url()
    if url is None or _disabled:
        return None
    if _engine is not None:
        return _engine

    with _LOCK:
        if _engine is not None:
            return _engine
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            _engine = create_engine(
                url,
                # Matters on a laptop where Postgres is restarted or the
                # machine suspends: without it the first query after a resume
                # dies on a stale pooled connection.
                pool_pre_ping=True,
                pool_size=5,
                future=True,
                # 🔴 BOUND THE WAIT, or _safe() does not actually protect the
                # run. It catches exceptions but not TIME: a host that DROPS
                # packets rather than refusing them (a suspended VM, a laptop
                # that slept, a firewalled port) leaves connect() blocking for
                # the OS default — minutes on Windows — and the pipeline sits
                # there. Hanging a run is exactly as bad as breaking it, and
                # DB_SCHEMA §9 forbids both. Found when the acceptance tests
                # hung on an unreachable host rather than failing fast.
                connect_args={"connect_timeout": CONNECT_TIMEOUT_S},
            )
            _sessionmaker = sessionmaker(bind=_engine, future=True,
                                         expire_on_commit=False)
        except Exception as exc:
            # A missing driver or a malformed URL disables the registry; it
            # does not stop the project from running.
            _trip_breaker(f"engine: {exc}")
            _engine = None
            _sessionmaker = None
    return _engine


def bootstrap() -> bool:
    """``create_all`` once per process. True if the table is ready."""
    global _bootstrapped
    if _bootstrapped:
        return True
    engine = get_engine()
    if engine is None:
        return False
    try:
        from researchgpt.db.models import Base

        Base.metadata.create_all(engine)
        _bootstrapped = True
    except Exception as exc:
        _trip_breaker(f"bootstrap: {exc}")
        return False
    return True


def get_session() -> Any:
    """A new Session, or ``None`` when the registry is unavailable."""
    if not bootstrap():
        return None
    if _sessionmaker is None:
        return None
    try:
        return _sessionmaker()
    except Exception as exc:
        log.warning("run registry unavailable (session): %s", exc)
        return None


def reset_for_tests() -> None:
    """Drop cached engine state so a test can change DATABASE_URL."""
    global _engine, _sessionmaker, _bootstrapped, _disabled
    with _LOCK:
        _disabled = False
        if _engine is not None:
            try:
                _engine.dispose()
            except Exception:
                pass
        _engine = None
        _sessionmaker = None
        _bootstrapped = False


__all__ = [
    "database_url",
    "enabled",
    "get_engine",
    "get_session",
    "bootstrap",
    "reset_for_tests",
]
