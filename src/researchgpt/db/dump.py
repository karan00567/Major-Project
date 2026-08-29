"""T-627 — dump the run registry to a file: schema, data, or both.

    python -m researchgpt.db.dump                    # plain SQL, schema + data
    python -m researchgpt.db.dump --format custom    # compressed, pg_restore
    python -m researchgpt.db.dump --format schema    # DDL only
    python -m researchgpt.db.dump --format json      # portable, no pg_dump needed

**Why this exists rather than a line in the README.** ``DB_SCHEMA.md`` documents
the schema as prose; prose drifts. A dump is the schema as the database actually
holds it, and the JSON format additionally survives having no PostgreSQL client
tools installed — which matters because ``DATABASE_URL`` is optional in this
project and a fresh clone may have no Postgres at all.

Output goes to ``data/backups/`` (gitignored, like everything under ``data/``).

FORMAT CHOICE
-------------
======== ============================== =========================================
format   restore with                   use it when
======== ============================== =========================================
plain    ``psql -f``                    the default. Readable, diffable, greppable
custom   ``pg_restore``                 large data, or restoring selected tables
schema   ``psql -f``                    committing the DDL alongside DB_SCHEMA.md
json     this module's ``--load``       no pg_dump available, or feeding a report
======== ============================== =========================================

⚠️ **The password is never printed and never passed on the command line.** It
goes to ``pg_dump`` through ``PGPASSWORD`` in the child environment, because an
argv password is visible in the process list to every user on the machine.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

DEFAULT_OUT = pathlib.Path("data/backups")

#: Windows installs put pg_dump outside PATH more often than not. Checked in
#: order after PATH itself; newest major version first.
_WINDOWS_HINTS = [
    pathlib.Path(r"C:\Program Files\PostgreSQL"),
    pathlib.Path(r"C:\Program Files (x86)\PostgreSQL"),
]


def find_pg_dump() -> str | None:
    """``pg_dump`` on PATH, else the newest versioned Windows install."""
    found = shutil.which("pg_dump")
    if found:
        return found
    candidates: list[tuple[int, pathlib.Path]] = []
    for root in _WINDOWS_HINTS:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            exe = child / "bin" / "pg_dump.exe"
            if exe.is_file():
                try:
                    candidates.append((int(child.name), exe))
                except ValueError:
                    candidates.append((0, exe))
    if not candidates:
        return None
    return str(max(candidates)[1])


def database_url() -> str:
    """``DATABASE_URL`` from the environment, else from ``.env``.

    Deliberately does not import ``researchgpt.db.session``: this must work when
    the optional ``[db]`` extra is not installed, so that ``--format json`` can
    still report *why* it cannot run.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url.strip()
    env = pathlib.Path(".env")
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return ""


def parse_url(url: str) -> dict[str, str]:
    """Split a SQLAlchemy URL into libpq connection parts."""
    # postgresql+psycopg://user:pw@host:port/db  ->  postgresql://...
    plain = re.sub(r"^postgresql\+\w+://", "postgresql://", url)
    p = urlparse(plain)
    if not p.hostname or not p.path:
        raise SystemExit(f"DATABASE_URL is not a usable PostgreSQL URL: {p.scheme}://...")
    return {
        "host": p.hostname,
        "port": str(p.port or 5432),
        "user": unquote(p.username or "postgres"),
        "password": unquote(p.password or ""),
        "dbname": p.path.lstrip("/"),
    }


def dump_with_pg_dump(parts: dict[str, str], out: pathlib.Path, fmt: str) -> None:
    exe = find_pg_dump()
    if not exe:
        raise SystemExit(
            "pg_dump not found on PATH or in a standard Windows install.\n"
            "Either install the PostgreSQL client tools, or use --format json, "
            "which needs only the Python driver."
        )
    flags = {
        "plain":  ["-f", str(out)],
        "custom": ["-Fc", "-f", str(out)],
        "schema": ["--schema-only", "-f", str(out)],
        "data":   ["--data-only", "-f", str(out)],
    }[fmt]

    cmd = [
        exe, "-h", parts["host"], "-p", parts["port"], "-U", parts["user"],
        "-d", parts["dbname"],
        # A dump that recreates ownership and grants fails to restore anywhere
        # the same roles do not exist. Portability beats fidelity here.
        "--no-owner", "--no-privileges",
        *flags,
    ]
    env = dict(os.environ)
    if parts["password"]:
        env["PGPASSWORD"] = parts["password"]      # never in argv

    print(f"  {pathlib.Path(exe).name} -> {out.name}")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"pg_dump failed ({proc.returncode}):\n{proc.stderr.strip()[:800]}")


def dump_json(parts: dict[str, str], out: pathlib.Path) -> dict[str, int]:
    """Portable dump: column types plus every row, no client tools required.

    Not a substitute for ``pg_dump`` — it carries no indexes, constraints or
    sequences, so it restores *data*, not a database. It exists because it works
    when nothing else does, and because a JSON file is what a report figure or a
    grep actually wants.
    """
    try:
        import psycopg
    except ImportError:
        raise SystemExit(
            "psycopg is not installed. Either `pip install -e \".[db]\"` "
            "or use a pg_dump-based format."
        )

    dsn = (f"postgresql://{parts['user']}:{parts['password']}@"
           f"{parts['host']}:{parts['port']}/{parts['dbname']}")

    payload: dict[str, object] = {
        "database": parts["dbname"],
        "dumped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "note": "data + column types only; no indexes, constraints or sequences",
        "tables": {},
    }
    counts: dict[str, int] = {}

    with psycopg.connect(dsn, connect_timeout=10) as conn:
        cur = conn.cursor()
        cur.execute(
            "select table_name from information_schema.tables "
            "where table_schema='public' and table_type='BASE TABLE' order by table_name"
        )
        tables = [r[0] for r in cur.fetchall()]

        for table in tables:
            cur.execute(
                "select column_name, data_type, is_nullable, column_default "
                "from information_schema.columns where table_schema='public' "
                "and table_name=%s order by ordinal_position",
                (table,),
            )
            columns = [
                {"name": n, "type": t, "nullable": nu == "YES", "default": d}
                for n, t, nu, d in cur.fetchall()
            ]
            cur.execute(f'select * from "{table}"')
            names = [d.name for d in cur.description]
            rows = [
                {k: _jsonable(v) for k, v in zip(names, row)}
                for row in cur.fetchall()
            ]
            payload["tables"][table] = {"columns": columns, "rows": rows}
            counts[table] = len(rows)

    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                   encoding="utf-8")
    return counts


def _jsonable(value: object) -> object:
    from datetime import date, datetime as dt
    from decimal import Decimal
    from uuid import UUID
    if isinstance(value, (dt, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        return f"<{len(bytes(value))} bytes>"
    return value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Dump the run registry to a file.")
    ap.add_argument("--format", default="plain",
                    choices=["plain", "custom", "schema", "data", "json", "all"])
    ap.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--name", default=None, help="basename; default is db + UTC stamp")
    args = ap.parse_args(argv)

    url = database_url()
    if not url:
        print("DATABASE_URL is empty or unset - the registry is disabled, so "
              "there is nothing to dump.", file=sys.stderr)
        return 1
    parts = parse_url(url)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = args.name or f"{parts['dbname']}_{stamp}"

    print(f"database   {parts['dbname']} @ {parts['host']}:{parts['port']} "
          f"as {parts['user']}")
    print(f"out        {args.out_dir}/\n")

    wanted = ["plain", "custom", "schema", "json"] if args.format == "all" else [args.format]
    written: list[pathlib.Path] = []

    for fmt in wanted:
        suffix = {"plain": ".sql", "custom": ".dump", "schema": ".schema.sql",
                  "data": ".data.sql", "json": ".json"}[fmt]
        out = args.out_dir / f"{base}{suffix}"
        if fmt == "json":
            counts = dump_json(parts, out)
            print(f"  json     -> {out.name}   " +
                  ", ".join(f"{t}={n}" for t, n in counts.items()))
        else:
            dump_with_pg_dump(parts, out, fmt)
        written.append(out)

    print()
    for path in written:
        print(f"  {path.stat().st_size / 1024:>8.1f} KB  {path}")

    print("\nrestore:")
    print(f"  createdb major_project_restored")
    print(f"  psql -d major_project_restored -f {written[0]}"
          if wanted[0] != "custom" else
          f"  pg_restore -d major_project_restored {written[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
