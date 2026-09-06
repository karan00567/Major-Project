# Restoring the demo state on a second laptop

Snapshot taken 2026-09-06 from `C:\Users\Sreekaran\Desktop\Major Project`.

Three things travel outside the normal repo, because `.gitignore` excludes
them from `master`: the run artefacts, the Postgres run registry, and `.env`.
Two of them are on this branch. `.env` is not, and must not be — carry it on a
USB stick.

## 1. Run artefacts — already restored

`outputs/` is committed on this branch at its real path, so checking the branch
out puts every run back where the app looks for it. Nothing to copy.

128 files, 27 MB, 82 run directories including `outputs/runs/fixture/` — the
pre-baked run that `RESEARCHGPT_FIXTURE=1` replays.

**Not included: `outputs/runs/checkpoints.sqlite` (521 MB).** GitHub hard-rejects
any file over 100 MB. It is the LangGraph `SqliteSaver` used to resume an
interrupted live run; `graph/checkpoint.py` recreates it empty on first use, so
nothing breaks. Only a mid-run resume of one of *these specific* runs would need
it, which no demo does. Copy it by USB if you want it.

## 2. Postgres run registry

Without it the app still works — `DB_SCHEMA §9` makes the registry best-effort
and every call is wrapped. But the human-in-the-loop control in Panel 6 will
report **"Saved to the run trace. Not mirrored — the database is unavailable."**
(`PanelScores.vue:86`), which is a bad thing for an examiner to read at the
exact moment you are demonstrating Objective 2. So restore it.

The dump is 15 KB: 3 tables, 6 rows in `runs` (including `fixture`), 0 in
`paper_scores` and `artefact_scores`.

```powershell
# 1. Install PostgreSQL 18 on the target machine.
#
#    ⚠️ At the password prompt, set the postgres superuser password to the SAME
#    one already in your .env. Otherwise DATABASE_URL will not authenticate and
#    you will be editing .env in the demo room.
#
# 2. Create the database and load the dump:
$env:PATH += ";C:\Program Files\PostgreSQL\18\bin"
createdb -U postgres major_project
psql -U postgres -d major_project -v ON_ERROR_STOP=1 -f demo-state\database\major_project.sql

# 3. Verify — expect runs=6, paper_scores=0, artefact_scores=0:
psql -U postgres -d major_project -c "select 'runs' t, count(*) from runs union all select 'paper_scores', count(*) from paper_scores union all select 'artefact_scores', count(*) from artefact_scores;"
```

The dump was taken with `--clean --if-exists --no-owner --no-privileges`, so it
drops and recreates its own objects and does not assume a `postgres` role owner.
It was verified by restoring into a scratch database and diffing row counts
against the source.

`DATABASE_URL` in `.env` points at `postgresql+psycopg://postgres:<pw>@localhost:5432/major_project`.
Leave it alone if you matched the password at install; otherwise edit the
password in `.env` on the target machine.

## 3. Still needs a USB stick

| file | why |
|---|---|
| `.env` | 7 live API keys. Never commit it. |
| `outputs/runs/checkpoints.sqlite` | 521 MB, over GitHub's limit, optional |
| `data/` | only if demoing LIVE — see below |

For the **fixture** demo you need none of `data/`. For a live `max_papers=10`
run you need `data/vectorstore/` (237 MB) and two model directories,
`data/models/verifier-onnx/` and `data/models/reranker-mixed-onnx/`, each
**without its `fp32/` subdirectory** — both loaders glob `*quantized*.onnx`
non-recursively, so `fp32/` is never opened at runtime. That is 434 MB instead
of the full 3.6 GB.

## Order of operations on the day

```powershell
git clone https://github.com/karan00567/Major-Project.git
cd Major-Project
git checkout claude-session-major-project     # brings outputs/ + the dump
copy <usb>\.env .env
# restore Postgres as above
pip install -r requirements.txt
cd frontend; npm install; cd ..

$env:RESEARCHGPT_FIXTURE = "1"
python -m uvicorn researchgpt.api.app:app --port 8000     # terminal 1
cd frontend; npm run dev                                   # terminal 2
```

Open **http://localhost:5173/** — not `127.0.0.1`, Vite binds IPv6.
Then follow `documents/SHOWCASE.md`.
