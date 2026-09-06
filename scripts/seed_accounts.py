"""T-614 — create the demo account and give it every pre-existing run.

Idempotent: safe to run repeatedly. Run it from the repo root:

    py -3.13 scripts/seed_accounts.py

WHY A SCRIPT AND NOT A MIGRATION
`DB_SCHEMA.md §8` deliberately has no Alembic — "one table, no production data,
and every run is reconstructible from outputs/runs/". ``create_all`` handles the
NEW ``users`` table on its own, but it does **not** alter an existing table, so
the ``runs.user_id`` column has to be added explicitly. That single ALTER is
done here, guarded by an existence check, rather than by dropping and recreating
``runs`` — which would throw away the six registry rows this script then needs.
"""

from __future__ import annotations

import sys

from sqlalchemy import select, text

from researchgpt.db import session as S
from researchgpt.db import users as users_db
from researchgpt.db.models import Run, User

DEMO_EMAIL = "demo_account@gmail.com"
DEMO_PASSWORD = "Karan*123"
# Shown in the sidebar. Deliberately NOT "Demo Account": nothing in the
# running application should announce itself as a demonstration.
DEMO_NAME = "Researcher"


def _has_column(conn, table: str, column: str) -> bool:
    return conn.execute(text(
        "select 1 from information_schema.columns "
        "where table_name=:t and column_name=:c"
    ), {"t": table, "c": column}).first() is not None


def migrate() -> list[str]:
    """Add the columns ``create_all`` cannot, because their tables exist.

    ``create_all`` builds a MISSING table in full, so ``users`` arrived complete
    — but it never ALTERs a table that is already there. ``runs`` predates
    accounts entirely, and on a database seeded before the admin flag existed so
    does ``users``. Both are handled here, each guarded by its own check so this
    script stays re-runnable.
    """
    engine = S.get_engine()
    if engine is None:
        raise SystemExit("DATABASE_URL is not set or Postgres is unreachable.")
    done: list[str] = []
    with engine.begin() as conn:
        if _has_column(conn, "runs", "user_id"):
            done.append("runs.user_id already present")
        else:
            conn.execute(text("alter table runs add column user_id uuid"))
            conn.execute(text(
                "create index if not exists ix_runs_user_id_created "
                "on runs (user_id, created_at desc)"
            ))
            done.append("runs.user_id added")

        if _has_column(conn, "users", "is_admin"):
            done.append("users.is_admin already present")
        else:
            conn.execute(text(
                "alter table users add column is_admin boolean not null default false"
            ))
            done.append("users.is_admin added")
    return done


def main() -> int:
    if not S.bootstrap():
        raise SystemExit("Could not reach the database. Check DATABASE_URL in .env.")
    for line in migrate():
        print(line)

    sess = S.get_session()
    if sess is None:
        raise SystemExit("No database session.")

    with sess as s:
        user = s.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                password_hash=users_db.hash_password(DEMO_PASSWORD),
                display_name=DEMO_NAME,
                is_admin=True,
            )
            s.add(user)
            s.commit()
            s.refresh(user)
            print(f"created {DEMO_EMAIL} (admin)")
        else:
            # Re-assert everything this script owns, so a re-run repairs a
            # forgotten password rather than leaving the account locked out on
            # the morning it is needed — and so an older row still carrying the
            # previous display name is corrected rather than left alone.
            user.password_hash = users_db.hash_password(DEMO_PASSWORD)
            user.is_admin = True
            user.display_name = DEMO_NAME
            s.commit()
            print(f"{DEMO_EMAIL} already existed; password, name and admin flag reset")

        demo_id = user.id

        # Every run that nobody owns becomes the demo account's. Runs already
        # owned by a real account are left alone, so re-running this after
        # someone registers cannot steal their history.
        orphans = s.scalars(select(Run).where(Run.user_id.is_(None))).all()
        for run in orphans:
            run.user_id = demo_id
        s.commit()
        print(f"assigned {len(orphans)} previously-unowned run(s) to {DEMO_EMAIL}")

        total = len(s.scalars(select(Run).where(Run.user_id == demo_id)).all())
        print(f"{DEMO_EMAIL} now owns {total} run(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
