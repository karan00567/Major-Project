# Phase 1 completion report — for Claude Code

> Written by Cursor after implementing `handoffs/phase1.md` (2026-08-25).
> Read this before reviewing diffs or ticking remaining Phase 1 boxes.

---

## 1. What was done

Implemented exactly the four Cursor-owned tasks from `handoffs/phase1.md`, in order. Did **not** edit `core/models.py` or `graph/state.py`.

| Task | File | Status |
|---|---|---|
| **T-107** | `src/researchgpt/core/logging.py` | Done + acceptance passed |
| **T-104** ★ | `src/researchgpt/core/llm.py` | Done + acceptance passed |
| **T-105** | `src/researchgpt/core/config.py` | Done + acceptance passed |
| **T-108** | `src/researchgpt/cli.py` | Done + acceptance passed |

Also added:

- `tests/test_phase1_acceptance.py` — encodes every DONE WHEN criterion from the handoff (cache, allowlist, 429 storm, extract_json, thought-filter, config env override, CLI run_start/run_end).
- `TASKLIST.md` — marked T-104 / T-105 / T-107 / T-108 as `[x]` with a one-line done note each. Left T-101–T-103 / T-106 / T-109 unchecked (Claude-owned; scaffold already on disk).

Package installed editable: `pip install -e ".[dev]"` succeeds; `import researchgpt` works.

Run acceptance anytime with:

```bash
python tests/test_phase1_acceptance.py
```

---

## 2. Design choices Cursor made (review these)

### T-107 — `TraceLogger`

- Opens `trace.jsonl` in `__init__` (append), creates `run_dir` including parents.
- Record key order matches the handoff exactly: `ts`, `run_id`, `agent`, `event`, `iteration`, `payload`.
- `ts` is ISO-8601 UTC with a trailing `Z` (via `.isoformat().replace("+00:00", "Z")`).
- Non-serialisable `payload` → `{"repr": ..., "serialisation_error": ...}`; never raises.
- Outer `try/except Exception` around the whole `event()` body so a logging bug cannot kill a run.
- Thread-safe via `threading.Lock` around write+flush.
- Context manager closes the file handle.

### T-104 — `LLMClient` ★ (priority review)

Handoff review checklist, mapped to the code:

1. **Allowlist before network** — `if resolved_model not in ALLOWED_MODELS: raise ModelNotAllowed` is the first action after resolving defaults, **before** cache read, throttle, or HTTP. Imports `ALLOWED_MODELS` / `MODEL_PROVIDER` from `core.models` (as required). No override flag.
2. **Google `thought` filter** — in `_google_complete`, any part with `part.get("thought") is True` is skipped before concatenating text. Without this, Gemma reasoning tokens corrupt JSON parses (observed 2026-08-25).
3. **Cache does not consume throttle** — cache hit returns immediately; `_throttle()` is only called on the live-request path.
4. **`RateLimitExceeded` aborts** — after more than `cfg.max_retries` consecutive 429s, raises with model name + attempt count. Does **not** fall back to another model. 5xx uses the same backoff, then raises `LLMError` (not `RateLimitExceeded`).

Other details:

- Cache key: `sha256(f"{model}|{temperature}|{max_tokens}|{prompt}")` → one JSON file under `cfg.cache_dir`.
- Throttle: monotonic spacing of `60/rpm` seconds between **live** requests only.
- Backoff: `min(2**attempt, 60)`, honours `Retry-After` when present.
- Keys via `python-dotenv` / `os.getenv`; missing key → `LLMError` with a clear message.
- Trace events (if `trace` provided): `agent="llm"`, events `request` | `cache_hit` | `retry` | `error`. Payload has `model`, `prompt_hash`, `latency_ms`, `attempt` — **never** the API key or full prompt text.
- `extract_json`: handles ` ```json ... ``` `, bare fences, leading space + trailing fence (` {"a": 1}\n``` `), and bare `{"a": 1}`. Raises `ValueError` if nothing recovers.

### T-105 — `load_config`

- Loads YAML → deep-merges env overrides → deep-merges `overrides` dict → `RunConfig.model_validate(...)`.
- Env pattern: `RESEARCHGPT__SECTION__KEY` (case-insensitive), values parsed as YAML scalars (`"25"` → int, `"true"` → bool).
- Precedence: YAML < env < `overrides`.
- Does **not** catch `ValidationError` — pydantic messages propagate unchanged (including the allowlist list for forbidden models).
- Does **not** redefine schema or the allowlist.

### T-108 — CLI

- `version` → `importlib.metadata.version("researchgpt")` (prints `0.1.0` when installed).
- `run`: builds `run_id = f"{UTC:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"`, loads config, applies `--max-papers` as `{"review": {"max_papers": N}}`, opens `TraceLogger`, writes `run_start` (question + fixture + full config dump) and `run_end`, prints `run_id` / `run_dir`, exits 0.
- `--fixture` is accepted and recorded in the trace payload; no other behaviour yet (T-603).
- Did **not** edit `pyproject.toml` (entry point already `researchgpt.cli:app`).

---

## 3. Observations Claude Code should know

1. **`researchgpt` console script may not be on PATH** on this Windows machine. Scripts land in `...\Python\pythoncore-3.14-64\Scripts`. Acceptance used `typer.testing.CliRunner` and `python -c` / `python tests/...` instead. Prefer `python -m` or CliRunner in CI until PATH is fixed.

2. **Python is 3.14.6.** Handoff says 3.11+; fine. Hatchling editable install worked with the existing `pyproject.toml` (`packages = ["src/researchgpt"]`).

3. **T-101 / T-102 / T-103 / T-106 / T-109 look already present on disk** (`pyproject.toml`, `models.py`, `state.py`, `configs/default.yaml`, `core/prompts/*_v1.md`) but are still `[ ]` in `TASKLIST.md`. Cursor did not tick them — those are Claude-owned. Reality-check line in TASKLIST still says “Zero code”; that is now stale.

4. **T-004 bake-off is still pending.** `configs/default.yaml` still has `# T-004 BAKE-OFF RESULT: <pending>` and provisional `gemma-4-31b-it` / `openai/gpt-oss-120b`. After T-004, update the comment and possibly the model fields; T-106’s “done when” depends on that.

5. **T-002 (Kaggle GPU) is still open** and still blocks Phase 3 training. Phase 1 Cursor tasks do not depend on it.

6. **Do not let Cursor touch `llm.py` again** after your line-by-line review — handoff rule. If something is wrong, Claude Code patches it.

7. **Acceptance test opens a real file handle** as the non-serialisable payload in T-107. It works; if you prefer a cleaner fixture, replace with a plain custom object that has no JSON encoding.

8. **Rate-limit test patches `time.sleep`** so the 429 storm finishes instantly. Live throttle behaviour is not load-tested here.

9. **Secrets:** `.env` has real Gemini / Groq / HF keys. It is gitignored. Do not commit it. Acceptance tests for T-104 cache/429/allowlist mock HTTP and do **not** burn quota.

---

## 4. Suggested Claude Code next actions

1. Line-by-line review of `src/researchgpt/core/llm.py` against the four checklist items in `handoffs/phase1.md` § “After Cursor finishes”.
2. Confirm T-101 / T-102 / T-103 / T-106 / T-109 and tick them if they already meet their DONE WHEN criteria (or finish any missing pieces).
3. Update TASKLIST reality-check (“Zero code” → code exists).
4. Run **T-004** JSON bake-off across the §0.1 allowlist; record winner + parse/repair counts at the top of `configs/default.yaml`.
5. Commit Phase 1 when satisfied (human must ask — Cursor does not commit unless requested).

---

## 5. Files touched this session

```
src/researchgpt/core/logging.py          (new)
src/researchgpt/core/llm.py              (new)
src/researchgpt/core/config.py           (new)
src/researchgpt/cli.py                   (new)
tests/test_phase1_acceptance.py          (new)
TASKLIST.md                              (T-104/105/107/108 checked)
handoffs/phase1_complete.md              (this file)
```

Not touched: `core/models.py`, `graph/state.py`, `pyproject.toml`, `configs/default.yaml` (content), `.env`.
