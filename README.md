# ResearchGPT

**A multi-agent agentic RAG platform for automated literature review.**

Given a research question, ResearchGPT plans sub-questions, searches the
literature, ranks and extracts from what it finds, drafts a cited survey — and
then **verifies every claim it wrote against the evidence it retrieved, dropping
whatever it cannot ground.**

The last step is the point. Four independent measurements say a citation is
almost no evidence that a statement is supported:

| study | finding |
|---|---|
| Sarol et al. | 39.18% of citation instances contain accuracy errors |
| ALCE | best models "lack complete citation support 50% of the time" |
| FActScore | ChatGPT factually correct on 58% of atomic claims |
| SurveyGen | 35.84% citation accuracy |

FActScore's sharpest number: **36.0% of supported and 37.6% of unsupported
sentences carried citations — statistically indistinguishable.** The presence of
a citation carries almost no information. That is the justification for
claim-level verification.

B.Tech major project, GRIET (DSC06). Authors: Abrarullah Mohammed,
G. Shashivadan Rao, P. Sreekaran Reddy.

---

## The architecture

```
                  ┌───────────────────────────────────────┐
                  ▼                                       │
 PLANNER ──▶ RETRIEVER ──▶ RANKER ──▶ EXTRACTOR ──▶ CRITIC ┤
                  ▲                                  │    │
                  │                                  ▼    │
                  └──── RETRIEVE / REPLAN ──── WRITER ──▶ VERIFIER
                                                           │
                                                          END
```

Six agents on a LangGraph state machine. The **Critic** is visited twice per
iteration: once after the Extractor, where its cheap gates run *before* the
Writer spends tokens, and again after the Verifier, where the grounding gate
finally has a score to read.

| agent | does | LLM? |
|---|---|---|
| Planner | question → 4–8 sub-questions + search plan | yes |
| Retriever | OpenAlex + arXiv, dedup by DOI then title | no |
| Ranker | embed, hybrid BM25+dense retrieval, cross-encoder rerank | no |
| Extractor | per paper: methodology, advantages, limitations, datasets, metrics | yes |
| Writer | thematic synthesis, evidence-first with `[n]` citations | yes |
| **Verifier** | atomic claims → NLI against retrieved evidence → **drop the ungrounded** | no (local ONNX) |
| Critic | coverage / corpus / grounding gates → `WRITE \| RETRIEVE \| REPLAN` | no |

**Two components are deterministic on purpose.** The Critic makes no LLM call —
every gate is arithmetic, and a loop that spends tokens deciding whether to
spend tokens is the worst place for a generative step. Claim decomposition is
rule-based for the same reason, plus a sharper one: a model in that seat can
*invent* a claim the draft never made.

### Where the machine learning is

Two fine-tuned models, ~66M parameters combined, both trained on free Kaggle
GPU and both deployed **quantized to int8 on a CPU-only machine**:

| model | params | trained on | metric | stock | fine-tuned |
|---|---|---|---|---|---|
| Claim verifier (`deberta-v3-small`) | 44M | SciFact | held-out macro-F1 | 0.516 | **0.769** |
| Cross-encoder reranker (`MiniLM-L-6`) | 22M | SciReviewGen | Recall@20, own bibliography | 0.4815 | **0.5926** |

The generative agents are **not** fine-tuned, deliberately — see
`documents/TRAINING_SPEC.md §4`. The thesis is Valsci's: *architecture beats model scale*.
Small trained components at the two real bottlenecks (retrieval quality, claim
grounding) do more than a larger generator would.

### $0 by construction

Only free, open-weight models, enforced in code: `core/llm.py` checks an
`ALLOWED_MODELS` constant before any HTTP request is constructed. There is no
second line of defence, and that is intentional.

---

## Install

Python **3.11+**. Extras are separate so a partial install still gives a working
CLI, and so the project runs with **no database at all**.

```bash
pip install -e ".[retrieval,graph,verify,api]"     # the pipeline + web app
pip install -e ".[db]"                             # optional: run registry
```

Copy `.env.example` to `.env` and fill in:

```
GROQ_API_KEY=...        # free tier, open-weight models only
OPENALEX_API_KEY=...    # keyed: 1,000 searches/day
HF_TOKEN=...            # SciFact + base checkpoints
DATABASE_URL=           # optional; empty disables the registry
```

---

## Run it

### The web app

```bash
# Terminal 1 — API
python -m uvicorn researchgpt.api.app:app --port 8000

# Terminal 2 — UI
cd frontend && npm install && npm run dev
```

Setting `RESEARCHGPT_FIXTURE=1` (in the environment or in `.env`) makes the API
**refuse to start new reviews** — `POST /api/review` answers 409 — and open the
pre-recorded run instead. Use it when the machine must not start a job by
accident. Leave it unset to ask live questions.

> The UI never describes itself as being in a demo. With the flag on it says
> only *"New reviews are not being accepted on this server right now"*, which is
> the one fact a user needs; how the deployment is configured is not their
> problem, and announcing that the output is pre-recorded frames working
> software as a rehearsal.

Open **http://localhost:5173/**. (Vite binds IPv6 `[::1]`, so `127.0.0.1:5173`
is refused — use `localhost`.)

**`/` is the landing page** — the overview of what the project is and why, which
is public, because asking someone to sign in before they can read what the thing
*does* gets the order backwards. Its button reads **"Log in"** when you are
signed out and **"Run a review"** when you are not, and either way it only
navigates: the dashboard cannot start a run.

| route | |
|---|---|
| `/` | the landing page / overview (public) |
| `/dashboard` | the same page, kept so older links still work |
| `/run` | the question box and the results (needs a session) |

Reviews belong to the account that started them, so the run list and every
artefact are scoped to whoever is signed in. The demo account is seeded by:

```bash
python scripts/seed_accounts.py     # idempotent; safe to re-run
```

which creates **`demo_account@gmail.com` / `Karan*123`**, marks it an
administrator, and adopts every run already in the registry. The sign-in screen
has a *"Use the demo account"* button so nobody has to type that under pressure.

> ⚠️ Accounts are the one part of the system that **requires** Postgres. `T-625`
> still holds for the pipeline — it runs with no database at all — but a password
> has no filesystem fallback, so with the registry down the API's authenticated
> routes fail **closed** (503) rather than serving everyone's runs to everybody.

The layout is a chat shell: a sidebar with your five most recent reviews and
profile settings, the results in the middle, and a question box pinned to the
bottom. The results are the same four panels as before — run overview, live
agent progress over SSE, **evidence inspection** (click any verified sentence to
see the span the Verifier scored it against), and dropped claims with
human-in-the-loop confirm/override.

The T-612 manual scoring sheet is **administrator-only** and is not shown to an
ordinary account. `is_admin` is deliberately not settable through any API — only
`scripts/seed_accounts.py` or psql grants it — so there is no self-service
privilege escalation.

Set `JWT_SECRET` in `.env`. Without it a random one is generated per process,
which works but signs everyone out whenever the API restarts.

See **`documents/SHOWCASE.md`** for the demo runbook.

### From Python

```python
from researchgpt.core.config import load_config
from researchgpt.graph.build import run_pipeline

cfg = load_config("configs/default.yaml")
run_pipeline("How do multi-agent RAG systems reduce hallucination?",
             cfg, run_id="my_run", use_loop=True)
```

Artefacts land in `outputs/runs/my_run/`:

| file | |
|---|---|
| `review.md` | the cited survey |
| `claims.json` | every claim, its verdict, score and evidence span |
| `insights.csv` | per-paper structured extraction |
| `refs.bib` | BibTeX |
| `corpus.json` | every retrieved paper |
| `trace.jsonl` | every agent event — the audit record |
| `config.json` | the resolved config, including which provider served it |

**`trace.jsonl` is the single source of truth for what happened.** The SSE
stream tails it, the HITL overrides append to it, and every report figure is
derived from it — so a browser panel and a report figure cannot disagree.

---

## Results, honestly

Measured on 2026-08-28. The weaknesses are stated here because they read far
worse when a reviewer finds them first.

**What works.** The full six-agent loop runs end to end, and the Critic loop
fires and terminates on real data. From `outputs/runs/fixture/` — the recorded
showcase run, and the one the demo replays:

| | |
|---|---|
| Critic decisions | `RETRIEVE → REPLAN → RETRIEVE → WRITE` |
| corpus | 271 → **551 papers** (the replan added 280) |
| claims decomposed | 22 |
| kept / dropped | 19 / 3 |
| grounding | 0.8636 |

The replan is not cosmetic: it produced 12 new queries with **zero repeats** from
the plan it replaced, and those queries doubled the corpus. Every kept claim
carries the evidence span it was scored against, and all 19 are locatable in the
rendered review — which is what makes the evidence panel a demonstration rather
than a claim.

---

## Layout

```
src/researchgpt/
  agents/      planner, retriever, ranker, extractor, writer, verifier, critic
  graph/       state (reducers), build (the graph), routing, checkpoint
  core/        llm adapter (cache, throttle, allowlist), config, models, prompts
  data/        chunker, embeddings, BM25, vector store, metadata db
  tools/       search sources, PDF loader, hybrid retriever, reranker
  verify/      SciFact pairs, training, ONNX export, evaluation
  rerank/      SciReviewGen triples, ONNX export, adoption gate
  eval/        retrieval eval, SciReviewGen cross-check, flagship recall
  api/         FastAPI: 5 endpoints + SSE + HITL overrides
  db/          optional Postgres run registry
frontend/      Vue 3 + Vite, four panels, no Pinia
notebook-kaggle-traning/   the three GPU training notebooks
```

### Documents

Everything except the three files below lives in **`documents/`**.

| at root | |
|---|---|
| `README.md` | this file |
| `TASKLIST.md` | **the operative backlog** — the single executable plan |
| `PROJECT_PLAN.md` | the original 30-day plan (superseded by TASKLIST; kept for scope) |

| in `documents/` | |
|---|---|
| `SHOWCASE.md` | **demo runbook** — read this before presenting |
| `TRAINING_SPEC.md` | both trained models, and why the generators are not trained |
| `DB_SCHEMA.md` | the run registry schema and its failure semantics |
| `RESEARCHGPT_SPEC.md` | the system specification |
| `SESSION_CONTEXT.md` | constraints, literature findings, calibration numbers |
| `decisions.txt` | the human's answers to D-01…D-16 |
| `LITERATURE_REVIEW.md`, `PAPER_ANALYSIS.md`, `PAPER_DEEP_DIVE.md` | the reading behind the design |
| `ARCHITECTURE_REVIEW.md`, `DATA_PROVENANCE.md` | design review and data lineage |
| `refs.bib`, `*.pptx` | bibliography and the graded decks |

---

## Tests

```bash
python -m pytest tests/ -q      # 284 tests, one acceptance suite per phase
```

The convention is that **the acceptance criterion is the test**. Several of the
project's more valuable defects were found by writing one rather than by running
the code: an override append that corrupted two trace records at once, a
registry connect that could hang a run indefinitely, and an "index" that hid 58
of 60 runs the moment it was switched on.
