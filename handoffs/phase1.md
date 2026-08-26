# Cursor (Groq) handoffs — Phase 1

Paste each block below into Cursor **as its own prompt**, one at a time, in
order. Do not combine them. Attach the files named under CONTEXT.

Claude Code has already written and verified `core/models.py` and
`graph/state.py`; both are done and **must not be edited** by these tasks.

Order matters: T-107 has no dependencies, T-104 uses it, T-105 uses `RunConfig`,
T-108 uses all three.

---

## T-107 — `src/researchgpt/core/logging.py`

```
FILE: src/researchgpt/core/logging.py
CONTEXT (attach): src/researchgpt/core/models.py

WRITE: A JSONL trace logger. Every agent event in a run appends exactly one
JSON object to outputs/runs/<run_id>/trace.jsonl. This file is the sole source
of every figure in the final report, so the schema must never change once
written and a write must never raise into the caller.

SIGNATURES (exact):
    class TraceLogger:
        def __init__(self, run_id: str, runs_dir: str = "outputs/runs") -> None
        @property
        def run_dir(self) -> pathlib.Path
        def event(self, agent: str, event: str,
                  payload: dict | None = None,
                  iteration: int | None = None) -> None
        def close(self) -> None
        def __enter__(self) -> "TraceLogger"
        def __exit__(self, *exc) -> None

RECORD SHAPE (exact keys, this order):
    {"ts": "<ISO-8601 UTC>", "run_id": str, "agent": str, "event": str,
     "iteration": int | null, "payload": {...}}

CONSTRAINTS:
  - Python 3.11+, type-hinted. Stdlib only (json, pathlib, datetime, threading).
  - Creates run_dir on first use, including parents.
  - Opens the file in append mode; one flush per event so a crashed run still
    has a readable trace.
  - Thread-safe: guard writes with a threading.Lock.
  - payload must be JSON-serialisable; if it is not, fall back to
    {"repr": repr(payload), "serialisation_error": str(exc)} and keep going.
    NEVER raise out of event() - losing a trace line is acceptable, killing a
    30-minute run because of a logging bug is not.

DONE WHEN: a three-event dummy run produces a parseable trace.jsonl (each line
round-trips through json.loads), and passing a non-serialisable payload
(e.g. an open file handle) still writes a line instead of raising.

DO NOT: add features, refactor other files, or change function signatures.
```

---

## T-104 ★⛔ — `src/researchgpt/core/llm.py`

**This is the highest-leverage file in the build. Claude Code reviews it line
by line and Cursor does not touch it again afterwards.**

```
FILE: src/researchgpt/core/llm.py
CONTEXT (attach): src/researchgpt/core/models.py,
                  src/researchgpt/core/logging.py

WRITE: The single LLM adapter for the whole project. Every generative call in
the system goes through this file; no other module may import an HTTP client
or a provider SDK. It must do four things that are all mandatory on day one:
a prompt-hash disk cache, a requests-per-minute throttle, exponential backoff
on 429/5xx, and a hard model allowlist.

SIGNATURES (exact):
    class ModelNotAllowed(ValueError): ...
    class RateLimitExceeded(RuntimeError): ...
    class LLMError(RuntimeError): ...

    def extract_json(text: str) -> dict
        # Strips markdown fences and leading/trailing prose, then json.loads.
        # Handles ```json ... ``` and bare ``` ... ``` and a leading space.
        # Raises ValueError if no JSON object can be recovered.

    class LLMClient:
        def __init__(self, cfg: LLMConfig,
                     trace: "TraceLogger | None" = None) -> None
        def complete(self, prompt: str, *,
                     model: str | None = None,
                     temperature: float | None = None,
                     max_tokens: int | None = None,
                     use_cache: bool = True) -> str
        @property
        def request_count(self) -> int      # live API calls made
        @property
        def cache_hits(self) -> int

ALLOWLIST (the $0 hard rule - TASKLIST §0.1):
  - Import ALLOWED_MODELS and MODEL_PROVIDER from core.models.
  - complete() raises ModelNotAllowed BEFORE constructing any request or
    touching the network if the resolved model is not in ALLOWED_MODELS.
  - This check is the project's only defence against billing a paid endpoint.
    There is no second line of defence. Do not soften it, do not add an
    override flag, do not read it from config.

CACHE:
  - Key: sha256 of f"{model}|{temperature}|{max_tokens}|{prompt}".
  - Stored as one JSON file per key under cfg.cache_dir, containing
    {"model", "prompt", "response", "ts"}.
  - A cache hit must issue ZERO HTTP requests and must not consume throttle
    budget.

THROTTLE + BACKOFF:
  - Respect cfg.requests_per_minute with a simple monotonic-clock spacing of
    60/rpm seconds between live requests.
  - On HTTP 429 or 5xx: exponential backoff 2**attempt seconds (cap 60),
    honouring a Retry-After header when present, up to cfg.max_retries.
  - After cfg.max_retries consecutive 429s, raise RateLimitExceeded with a
    message naming the model and the attempt count. Abort loudly. Never loop
    silently and never fall back to a non-allowlisted model.

PROVIDERS (dispatch on MODEL_PROVIDER[model]):
  "google"  POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=$GEMINI_API_KEY
            body: {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": t, "maxOutputTokens": m}}
            response text: concatenate candidates[0].content.parts[*].text
            *** SKIP any part where part.get("thought") is true. ***
            Gemma emits reasoning parts flagged "thought": true alongside the
            answer; including them corrupts every downstream JSON parse. This
            was observed live on 2026-08-25 - it is not hypothetical.
  "groq"    POST https://api.groq.com/openai/v1/chat/completions
            header: Authorization: Bearer $GROQ_API_KEY
            body: {"model": model, "messages": [{"role": "user",
                   "content": prompt}], "temperature": t, "max_tokens": m}
            response text: choices[0].message.content

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependencies: httpx, python-dotenv only.
  - Load keys with dotenv from .env; raise LLMError with a clear message if the
    needed key for the chosen provider is absent.
  - If trace is provided, log one event per call: agent="llm",
    event="request"|"cache_hit"|"retry"|"error", payload includes model,
    prompt_hash, latency_ms, attempt. NEVER log the API key or full prompt
    text - prompt_hash only.

DONE WHEN (all four, tested):
  1. Calling complete() twice with the same prompt issues exactly one HTTP
     request; the second returns from cache and increments cache_hits.
  2. A simulated 429 storm raises RateLimitExceeded with a named message
     rather than hanging or looping.
  3. complete(prompt, model="gpt-4o-mini") raises ModelNotAllowed before any
     network call is made.
  4. extract_json() recovers a dict from '```json\n{"a": 1}\n```',
     from ' {"a": 1}\n```', and from '{"a": 1}'.

DO NOT: add streaming, add a provider not listed above, add an allowlist
override, or change function signatures.
```

---

## T-105 — `src/researchgpt/core/config.py`

```
FILE: src/researchgpt/core/config.py
CONTEXT (attach): src/researchgpt/core/models.py, configs/default.yaml

WRITE: A YAML config loader returning a validated RunConfig, with environment
variable overrides. RunConfig already exists in core/models.py and already
enforces the model allowlist and rejects unknown keys - this module only loads
and merges, it does not define or validate schema itself.

SIGNATURES (exact):
    def load_config(path: str | pathlib.Path = "configs/default.yaml",
                    overrides: dict | None = None) -> RunConfig

ENV OVERRIDES:
  - Pattern RESEARCHGPT__<SECTION>__<KEY>, double underscore as separator,
    case-insensitive. e.g. RESEARCHGPT__REVIEW__MAX_PAPERS=25 sets
    review.max_papers. Values are parsed as YAML scalars so "25" becomes int
    and "true" becomes bool.
  - Precedence, lowest to highest: YAML file < env vars < the overrides dict.

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependencies: pyyaml, python-dotenv.
  - Let pydantic's ValidationError propagate unchanged. Do not catch it and do
    not re-raise it as something else - its message names the offending field
    and, for a forbidden model, lists the permitted ones.

DONE WHEN: load_config("configs/default.yaml") returns a validated RunConfig;
an unknown top-level key raises ValidationError; RESEARCHGPT__REVIEW__MAX_PAPERS=25
is applied as the integer 25; and load_config(overrides={"llm": {"model":
"gpt-4o"}}) raises ValidationError.

DO NOT: define new Pydantic models, duplicate the allowlist, or edit models.py.
```

---

## T-108 — `src/researchgpt/cli.py`

```
FILE: src/researchgpt/cli.py
CONTEXT (attach): src/researchgpt/core/config.py,
                  src/researchgpt/core/logging.py,
                  src/researchgpt/core/models.py

WRITE: A Typer CLI stub. The pipeline does not exist yet, so `run` wires up
config + trace logger + a run_id and reports what it WOULD do, then exits 0.
It is a real entry point that later phases fill in, not a placeholder to be
rewritten.

SIGNATURES (exact):
    app = typer.Typer(add_completion=False)

    @app.command()
    def version() -> None

    @app.command()
    def run(question: str = typer.Option(..., "--question", "-q"),
            max_papers: int = typer.Option(None, "--max-papers"),
            config: str = typer.Option("configs/default.yaml", "--config"),
            fixture: bool = typer.Option(False, "--fixture")) -> None

BEHAVIOUR:
  - version: print the version from importlib.metadata("researchgpt").
  - run: generate run_id as f"{UTC:%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}";
    load config; apply --max-papers as an override when given; open a
    TraceLogger; write one event agent="cli", event="run_start" with the
    question and the resolved config; print the run_id and run_dir; write
    event="run_end"; exit 0.
  - --fixture is accepted and recorded in the trace but does nothing yet
    (it is wired up in T-603).

CONSTRAINTS:
  - Python 3.11+, type-hinted. Dependency: typer.
  - The console entry point `researchgpt` is already declared in
    pyproject.toml as researchgpt.cli:app. Do not edit pyproject.toml.

DONE WHEN: `researchgpt version` prints a version; `researchgpt run -q "test"`
creates outputs/runs/<run_id>/trace.jsonl containing a run_start and a run_end
event and exits 0.

DO NOT: implement any agent, import langgraph, or change function signatures.
```

---

## After Cursor finishes

Claude Code runs the acceptance checks, reviews the diffs (assume hallucinated
imports until proven otherwise), and ticks the boxes in `TASKLIST.md`.

The T-104 review is the one that matters. Check specifically:

1. **The allowlist check fires before any network call** — not after building
   the request, not inside the retry loop.
2. **The `thought` part filter is present** in the Google branch. Without it
   every Gemma JSON parse fails and the cause is not obvious from the error.
3. **A cache hit does not consume throttle budget** — otherwise dev re-runs
   are still rate-limited and the cache's main benefit is lost.
4. **`RateLimitExceeded` aborts** rather than degrading to another model.
