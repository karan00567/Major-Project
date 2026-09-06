# Claude Code session state

Everything Claude Code knows about this project that **is not** derivable from
the repo: the conversation transcripts, the persistent memory, and the settings.

None of it is account-synced. Signing into Claude Code as the same user on
another machine brings across *nothing* — this directory is the transfer
mechanism.

Committed 2026-09-06 so the project can be demoed from a second laptop.

## What is here

| path | what it is |
|---|---|
| `projects/C--Users-Sreekaran-Desktop-Major-Project/*.jsonl` | 12 session transcripts, ~15.5k messages |
| `projects/.../MEMORY.md` + `memory/` | Claude's persistent project memory |
| `settings/global-settings.json` | model, effort level, the 3 plugin marketplaces (`~/.claude/settings.json`) |
| `settings/project-settings.json` | enabled plugins (`.claude/settings.json`) |
| `settings/project-settings.local.json` | the permission allowlist — **gitignored in the working tree**, so a fresh clone loses it and Claude prompts on every command |
| `scripts/` | export/import helpers, see below |

## Secrets

The transcripts record tool output, which included `.env` reads. Before
committing, 10 occurrences were replaced with `<REDACTED:NAME>` placeholders:
`OPENALEX_API_KEY` (6), a `DATABASE_URL` (1), two other Postgres connection
strings (3). The scan is in the commit that added this file; re-run it before
adding any new transcript.

**`.env` itself is not here and must not be.** Carry it on a USB stick.

## Restoring on another machine

Claude keys history off the **absolute project path**, slugified by replacing
every non-alphanumeric character with `-`:

```
C:\Users\Sreekaran\Desktop\Major Project
  -> C--Users-Sreekaran-Desktop-Major-Project
```

If the clone lands at a different path — a different Windows username is
enough — the slug differs and Claude finds no history. So:

```powershell
# 1. install Claude Code on the target machine and log in
# 2. git clone, then check out this branch
# 3. copy the state into place, renamed for the new path:
$proj = "C:\Users\<them>\Desktop\Major Project"
$slug = $proj -replace '[^A-Za-z0-9]', '-'
Copy-Item "claude-sessions\projects\C--Users-Sreekaran-Desktop-Major-Project" `
          "$env:USERPROFILE\.claude\projects\$slug" -Recurse
Copy-Item "claude-sessions\settings\project-settings.local.json" ".claude\settings.local.json"
# merge settings/global-settings.json into $env:USERPROFILE\.claude\settings.json by hand,
# or let scripts\import-claude-bundle.ps1 do all of the above:

.\claude-sessions\scripts\import-claude-bundle.ps1 -Bundle <usb> -ProjectPath $proj
```

Then `claude --resume` in the project folder lists every past session.
An empty list means the slug did not match.

Do **not** copy `~/.claude/.credentials.json`. Log in on the target machine.

## Demoing the app itself

`git clone` gives you none of the 4.8 GB working tree — `/data/`, `/outputs/`,
`.env`, `*.zip` and `node_modules` are all gitignored. You do not need them:
`documents/SHOWCASE.md` demos from `RESEARCHGPT_FIXTURE=1`, which replays
`outputs/runs/fixture/` (1.6 MB, carry it on the USB) and refuses live runs.
`api/app.py` imports nothing heavy, so no models and no vectorstore are loaded
on that path.
