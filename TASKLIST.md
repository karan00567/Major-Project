# ResearchGPT — Master Task List

> **What this file is.** The single executable backlog for the whole project, derived from `PROJECT_PLAN.md`, `RESEARCHGPT_SPEC.md`, `SESSION_CONTEXT.md`, `ARCHITECTURE_REVIEW.md` and the two `diagrams/*_EXPLAINED.md` files.
>
> **Two-agent workflow.** **Claude Code plans, specifies, reviews and integrates. Cursor (Groq) writes the code.** Every task below is written so it can be handed to Cursor as a self-contained unit of work with a hard acceptance test.
>
> **Companion documents:** `TRAINING_SPEC.md` (both fine-tuned models — verifier and reranker — and why the generative agents are not trained), `DB_SCHEMA.md` (the Postgres run registry), `PROJECT_PLAN.md` (scope), `SESSION_CONTEXT.md` (constraints and literature findings).
>
> Created 2026-08-25. Update the checkboxes in place; do not rewrite the file.

---

## 0. Reality check — read this before anything else

> **STATUS — last updated 2026-08-28.** The block below is the 2026-08-25 entry, kept because
> the descope decisions it justifies are still in force. **It is no longer a description of the
> project.**

| | 2026-08-25 (as written) | **2026-08-28 (now)** |
|---|---|---|
| Today | 2026-08-25 | **2026-08-28** |
| Days remaining | 13 | **10** |
| Code written | **Zero** | **86 of 117 tasks; 284 tests passing** |
| Milestones | none | **M1 landed 08-27 (4 days early), M2 landed 08-28 (5 days early)** |
| Phases complete | none | **0, 1, 2*, 3, 3B, 3C, 4, 5, 6, 6B** |

\* Phase 2 is complete except its **recall gate**, which is the one substantive thing still open
— see the warning below.

🔴 **THE BINDING CONSTRAINT IS NOW RETRIEVAL, NOT TIME.** Union recall against the
35-paper answer key is **0.057** (T-409, measured 2026-08-28) against a 0.371 baseline and a 0.80
gate. Retrieval recall is a hard ceiling on everything downstream: the Verifier cannot ground a
claim against a paper that was never fetched, which is why the flagship run produced **zero
SUPPORTED claims**. **T-702's ablation — the graded claim — will be measured on that same
corpus.** §13's Aug 28 kill switch names the response: spend a day on retrieval.

**Original 2026-08-25 entry, for the record:**

| | |
|---|---|
| Plan written | 2026-08-06 (30-day plan, Day 1 = 2026-08-07) |
| Today | **2026-08-25** |
| Target submission | **~2026-09-07** (was ~09-05; +2 days authorised 2026-08-25 to integrate SciReviewGen) |
| Days actually remaining | **13** |
| Code written so far | **Zero.** No `src/`, no `pyproject.toml`, no `.py` file anywhere in the folder. |

**The 30-day plan is no longer executable as written.** Nineteen of its thirty days are gone and none of them produced code. What exists is planning, literature, design and two graded decks.

This file is therefore **not** the 30-day plan re-typed. It is a compressed 11-day plan that applies the descope ladder in `PROJECT_PLAN.md §10` **up front** rather than in a panic on Day 28. Concretely, the following are cut before starting, not deferred:

| Cut now | Was | Why |
|---|---|---|
| Ollama feasibility probe | §6.3 | Already demoted to a footnote. Dead. |
| DOCX writer | §2.2 | Markdown + PDF-from-Markdown suffices. |
| 2-annotator Likert + Cohen's κ | §9 | Scheduling cost exceeds its evidentiary value at 11 days. Replaced by the 50-claim spot-check. |
| Ablations 3 and 4 | §9.4 | Kept only if Phase 7 finishes early. **Ablation 2 is never cut.** |
| Extraction F1 annotation (10 papers) | §5.4 | Replaced by 5 qualitative examples. |

**Reinstated 2026-08-25: SciReviewGen is back in scope (Phase 3B).** The original cut rested on a premise that turned out to be false — `PROJECT_PLAN.md §5.3` assumed distribution "as preprocessing scripts over S2ORC, historically requiring an AI2 access request with days of latency." **Three ungated public mirrors exist on Hugging Face** (`kejian/SciReviewGen`, `kdercksen/scireviewgen-csv`, `pat-jj/SciReviewGen`), verified downloadable 2026-08-25. There is no access request and no lead time. Two days were authorised for the integration; the schedule absorbs them at the back (§13).

**Never cut, under any circumstance** — these seven are the project: the six agents, the trained **verifier** (the reranker fine-tune in Phase 3C is a *second* trained model and is explicitly droppable — see T-335), the evidence-inspection panel, ablation 2 (− Verifier), `trace.jsonl`, the **M1 milestone** (first complete cited survey), the **SciReviewGen verifier cross-check (T-325)**, and — as of the 2026-08-25 decision — **Human-in-the-Loop (T-609)**.

> If M1 has not landed by **2026-08-31**, stop building forward and stabilise what exists. A working four-agent pipeline that produces a cited survey beats a half-wired six-agent graph that runs nothing.

---

## 0.1 Model policy — HARD RULE, no exceptions ★

**Only free, open-weight models. No paid models, no paid tiers, no trial credits, at any point in this project.**

This is Constraint 1 from `SESSION_CONTEXT.md §2` and it is not negotiable. If a task cannot be done on the allowlist below, the task gets descoped — the budget does not get raised.

### Allowlist — verified live on 2026-08-25

Every generative agent (Planner, Extractor, Critic, Writer) runs on one of these. All are **open-weight** models on a **free tier**, so the project is $0 by construction rather than by discipline.

| Model | Provider | Weights | Verified | Use for |
|---|---|---|---|---|
| `gemma-4-31b-it` | Google AI Studio | open | ✅ HTTP 200, extracted correctly | **Primary candidate** — all four agents |
| `gemma-4-26b-a4b-it` | Google AI Studio | open (MoE, ~4B active) | ⚠️ HTTP 200 but returned `{}` on the extraction probe | Speed fallback only; re-test before use |
| `openai/gpt-oss-120b` | Groq | open (Apache 2.0) | ✅ HTTP 200 | **Primary backup** — largest free open-weight option |
| `openai/gpt-oss-20b` | Groq | open (Apache 2.0) | not yet probed | Lightweight fallback |
| `qwen/qwen3.6-27b` | Groq | open | ✅ HTTP 200 | Second backup / bake-off arm |

*Despite the name, `openai/gpt-oss-*` are OpenAI's **open-weight** releases served free by Groq. They are not the paid OpenAI API.*

### Forbidden — do not call, do not put in a config, do not benchmark against

`gpt-4o`, `gpt-4o-mini`, `gpt-4*`, `o1/o3/o4`, Claude API models, `gemini-*-pro`, `deep-research-*`, and every other metered endpoint. **`RESEARCHGPT_SPEC.md §10.1` still names `gpt-4o-mini` and `gpt-4o` in `configs/default.yaml` — that config is from before the $0 constraint existed and must not be copied verbatim (see T-106).**

Proprietary free-tier models (`gemini-3.6-flash` and friends) are $0 today, but they are **not open-weight**, so a tier change can strand the project mid-build. They are permitted only as a temporary unblock, must be logged in the trace when used, and must never be the model reported in the paper.

### Enforcement, not good intentions

- **T-104 (`core/llm.py`) hard-fails on any model outside the allowlist.** The list lives in one constant in that file. A model not in it raises before any HTTP request is made. This is the whole enforcement mechanism — see T-104's acceptance criterion.
- The allowlist constant is the single source of truth. `configs/default.yaml` may only name models that appear in it.
- Every `trace.jsonl` LLM event records the model name, so the paper's "which model produced this" question is answerable from the run log.

### Measured consequence — Gemma ignores `responseSchema`

Probed 2026-08-25: Gemma on the Gemini API accepts `generationConfig.responseSchema` but **does not honour it**. It returns markdown-fenced JSON (a leading space and a trailing ```` ``` ````), not native structured output, and `gemma-4-26b-a4b-it` ignored the content entirely and returned `{}`.

This is not a blocker — it is a known cost of the $0 rule, and the plan already budgets for it (`SPEC §14`, retry-with-repair max 2). It has two consequences:

1. **T-404 (Extractor) needs a fence-stripping + repair layer**, not a bare `json.loads`. Assume fenced output is the normal case, not the error case.
2. **T-004's bake-off is now the decisive test**, not a formality. It measures clean-parse rate across the allowlist, which is exactly the property `PROJECT_PLAN.md §6.2` says to choose on.

### Local models — already free, unchanged

Embeddings (`bge-small-en-v1.5`), reranking (`ms-marco-MiniLM-L-6-v2`) and the fine-tuned verifier (`deberta-v3-small`, ONNX int8) all run on local CPU at $0 with no API involved. Training is on Kaggle's free GPU quota. **Do not run Gemma locally** — a 7B+ model on CPU-only hardware is 3–8 tokens/sec, hours per run, and `PROJECT_PLAN.md §6.3` already ruled it out as non-viable. The free *tier* is what makes $0 work here, not local inference.

---

## 0.2 Latency budget and mandatory source — decided 2026-08-25

### Latency is not a constraint. Correctness is.

**Decision: a full run may take ~30 minutes. Optimise for output quality, never for speed.**

What this changes:

| Decision | Was | Now |
|---|---|---|
| **T-004 bake-off criterion** | latency-led (`gpt-oss-120b` 3.1s beat `gemma-4-31b-it` 84.5s) | **quality-led** — decide on clean-parse rate and extraction correctness. Latency is a tiebreaker only. |
| **T-307 verifier escalation** | escalate to `deberta-v3-base` only if small scored poorly | **escalate readily.** `PROJECT_PLAN.md §4.2` already said *"trade latency, not accuracy — the verifier is the graded component"*; that trade is now nearly free. |
| **T-213 embedding escalation** | `bge-small` → `bge-base` only if recall was short | Cheap: measured 2.13 min for 3,000 chunks, so `bge-base` costs ~6 min. Take it if T-212 is anywhere near the gate. |
| **Semantic Scholar** | cut as *"rate-limited"* | **Reinstated (T-214).** Patient backoff was the blocker; patience is now free. |

What this does **not** change:

- **`requests_per_minute` and the response cache stay.** These defend the free-tier *request budget*, which is a hard quota, not a speed setting. Rate limits still bind.
- **`max_papers=25` for ablations stays** — that was about request budget, not wall clock (`PROJECT_PLAN.md §6.2`).
- **`gpt-oss-120b` stays primary for now.** Even with latency relaxed, `gemma-4-31b-it` at 84.5s × ~70 Extractor calls is **~1.6 h for extraction alone** — roughly 3× the stated 30-minute tolerance. It remains a legitimate T-004 candidate if it wins on quality, but it is not free.
- **T-610 (pre-baked demo run) stays.** Its value was never only speed — it removes any live-network dependency from the viva. Reframe the justification as demo *reliability*, not latency.

### 🔴 OpenAlex is now METERED — measured 2026-08-27

**This changes a load-bearing assumption and was found the hard way**, by a
T-324 run that silently produced a fabricated match rate after the budget ran
out mid-run.

OpenAlex has moved to a **daily spending budget**. Measured from live response
headers:

| | keyless | **with a free registered key** |
|---|---|---|
| `x-ratelimit-limit-usd` | $0.10 / day | **$1.00 / day** |
| `x-ratelimit-limit` (credits) | 1,000 | **10,000** |
| cost per search | $0.001 / 10 credits | same |
| **effective quota** | ~100 searches/day | **~1,000 searches/day** |

On exhaustion it returns **HTTP 429** with
`"Insufficient budget... Need more? Add funds at openalex.org/pricing"`.

✅ **`OPENALEX_API_KEY` obtained and wired in 2026-08-27 (Sreekaran).** It is the
**free registered tier, not a paid plan** — verified from live headers that
`prepaid-remaining-usd` is `0`, so nothing is billable and **§0.1 is satisfied**.
`search_openalex` reads it from `.env` automatically. **Never add funds**; the
$0 rule is not negotiable and 1,000 searches/day is ample.

⚠️ **`mailto` no longer buys anything.** The polite pool is gone — a request
with and without `mailto` gets the identical 429. `T-201`'s `mailto` parameter
is now courtesy only, not a quota mechanism.

**Consequences, all of which bind:**

- **Evaluation is what burns the quota, not the pipeline.** A real run asks
  4–8 Planner queries. T-324 asked 291 and died at ~100 *keyless*. With the
  key that is comfortable, but T-212, T-212b, T-324 and T-334 together still
  warrant caching rather than repeated live sweeps.
- **The `eval/cache/` pool cache (added for T-213) is now essential**, not a
  convenience. Never re-run a retrieval eval without it.
- **`search_openalex` now raises `OpenAlexBudgetExhausted`** rather than
  letting a 429 look like "no results". *A silent `[]` is indistinguishable
  from a genuine miss, and that is precisely how an exhausted budget
  masqueraded as a real T-324 match rate of 18.6%.*
- **`decisions.txt` D-03 (skip the Semantic Scholar key) still stands, but for
  a new reason.** It was made assuming OpenAlex was unlimited; that premise was
  false. The registered OpenAlex key restores the headroom, so S2 remains a
  genuine secondary rather than a needed fallback — the conclusion survives
  even though the reasoning behind it did not.
- **arXiv is unmetered** and gains importance as the third source.
- **T-610's pre-baked demo run stops being merely prudent and becomes
  necessary** — a live 60-paper demo could exhaust the day's budget on stage.

### OpenAlex or Semantic Scholar is mandatory

**Requirement satisfied: OpenAlex is already the primary source** (`configs/default.yaml`, T-201) and is keyless, reliable and rich in venue/OA metadata.

**Semantic Scholar is additionally reinstated as T-214**, because both decks claim it. Measured 2026-08-25: it appears on **8 slides of `PWP1 - Review 2 - DSC06.pptx`** — including the architecture (7) and MCD (8) slides that get explained to the committee — while OpenAlex appears on one. Building the connector makes the deck true, exactly as Phase 6B does for its PostgreSQL claim.

**Measured S2 behaviour, keyless (2026-08-25):** 1 of 4 rapid requests succeeded; with exponential backoff, 2 of 3 queries succeeded and one failed after 6 attempts. It is **usable but unreliable without a key**, so T-214 is best-effort and degradable — never a hard dependency. It does return **abstracts directly** (no de-inversion needed, unlike OpenAlex) and rich `externalIds` (DOI, ArXiv, DBLP, PubMed), which strengthens T-203 dedup.

---

## 1. How the two agents divide the work

### Claude Code — planning agent

Owns everything that requires reading across files, holding project context, or making a decision that is expensive to reverse:

- Writing and refining the task specs in this file.
- Designing schemas, contracts, state shape, graph topology, prompt structure.
- Reviewing every diff Cursor produces **before** it is committed.
- Debugging anything that spans more than one module.
- All document work: report chapters, spec corrections, deck edits, diagram explanations.
- Deciding when to descope.

### Cursor (Groq) — writing agent

Owns mechanical, well-specified, single-file code generation:

- Implementing one module at a time against a schema that already exists.
- Writing tests from an acceptance criterion that is already stated.
- Boilerplate: connectors, adapters, Pydantic models, Vue components, FastAPI routes.

### Operating rules for Cursor (Groq) — these matter

Groq's free models are fast and weak on long-horizon reasoning. Treat them accordingly:

1. **One file per prompt.** Never ask for "the retrieval layer." Ask for `src/researchgpt/data/chunker.py` and nothing else.
2. **Pin context explicitly.** Attach `core/models.py` and `RESEARCHGPT_SPEC.md` §8 to any task touching data shapes. Groq will not go and find them.
3. **Paste the acceptance criterion into the prompt verbatim.** It is the spec.
4. **Never let it make an architectural choice.** If a task prompt contains the word "decide," it is a Claude Code task, not a Cursor task.
5. **Never let it touch `core/llm.py` caching or the graph routing logic** after the first draft — those are where silent breakage hides.
6. **Read every diff.** Groq will invent library APIs that do not exist. Assume hallucinated imports until proven otherwise.
7. **No `# TODO` merges.** A task is done or it is not.
8. **Cursor must not edit `TASKLIST.md`, `configs/`, or anything under `handoffs/`.** *Learned the hard way on 2026-08-25: Cursor wrote back a stale copy of `TASKLIST.md` it had read earlier in its session and silently reverted five completed Claude-owned tasks and their notes.* Cursor reports what it finished; **Claude Code ticks the boxes.** If a handoff needs a checkbox changed, that is a Claude Code edit.

### Task handoff template (paste into Cursor)

```
FILE: <exact path>
CONTEXT (attached): <files to pin>
WRITE: <one paragraph, imperative>
SCHEMA / SIGNATURES:
  <exact type signatures Claude Code already fixed>
CONSTRAINTS:
  - Python 3.11+, type-hinted, no new dependencies beyond <list>
  - Every LLM call goes through core/llm.py (SPEC §14.5)
  - No silent fabrication: unresolvable value -> None + log (SPEC §14.2)
DONE WHEN: <the acceptance criterion, copied verbatim from TASKLIST.md>
DO NOT: add features, refactor other files, or change function signatures.
```

### Legend

| Tag | Meaning |
|---|---|
| 🧠 | Claude Code — plan / spec / review / integrate |
| ⌨️ | Cursor (Groq) — write the code |
| 👤 | Human (Sreekaran / team) — only you can do this |
| ★ | Graded critical path. Protect at all costs. |
| ⛔ | Blocking — downstream tasks cannot start |

---

## 2. Phase 0 — Preflight (today, 2026-08-25) ⛔

Nothing in Phase 1 starts until this phase closes. Budget: 2 hours.

- [x] **T-001** 👤 ⛔ Register **Google AI Studio (Gemini) free tier** and **Groq** API keys. Record both in `.env`. *Done when: both keys return a completion from a curl one-liner.* Verified 2026-08-25: both keys authenticate and return completions on **open-weight** models — `gemma-4-31b-it` (Google) and `openai/gpt-oss-120b` / `qwen/qwen3.6-27b` (Groq). **The model names in `PROJECT_PLAN.md` and `RESEARCHGPT_SPEC.md` are stale and some are paid** — `gemini-2.0-flash` is retired, Groq no longer serves `llama-3.3-70b-versatile`, and the spec's `gpt-4o-mini`/`gpt-4o` are forbidden outright. **Use §0.1's allowlist and nothing else.**
- [x] **T-002** 👤 ⛔ Confirm the **Kaggle** account has GPU quota available this week (Settings → phone verified → GPU hours remaining). *Done when: quota ≥ 5 h confirmed.* **Confirmed 2026-08-25 (`decsions.txt.txt`): Kaggle account with GPU access exists.** Phase 3 (verifier, T-303) and Phase 3C (reranker, T-332) are unblocked.
- [x] **T-003** 👤 Create a Hugging Face account + read token (needed for `allenai/scifact` and `deberta-v3-small`). *Done when: `huggingface-cli whoami` succeeds.* Verified 2026-08-25: token authenticates (HTTP 200, user `24f2000010`).
- [x] **T-004** 🧠 ★ Run the **JSON-reliability bake-off across the §0.1 allowlist only**: same Extractor prompt, 5 papers, four arms — `gemma-4-31b-it`, `gemma-4-26b-a4b-it`, `openai/gpt-oss-120b`, `qwen/qwen3.6-27b`. Count clean Pydantic parses **after** fence-stripping, and count how many needed a repair pass. Pick the primary on **parse reliability and extraction correctness** — see §0.2, latency is now only a tiebreaker. *This is now a decisive test rather than a formality: Gemma ignores `responseSchema` (§0.1), so parse reliability genuinely varies across the allowlist.* *Done when: a winner and its parse/repair counts are recorded as a comment at the top of `configs/default.yaml`, and the losing arms' failure modes are noted in one line each.* ✅ **COMPLETE 2026-08-25.** 5 real gold-set abstracts per arm through the real prompt and real client. Full table in `configs/default.yaml`; raw data in `eval/bakeoff_t004.json`.

  | arm | parse | valid | fields | echo | avg lat | verdict |
  |---|---|---|---|---|---|---|
  | `openai/gpt-oss-120b` | 100% | 100% | 4.6/8 | **0** | 26.6s | **PRIMARY** |
  | `qwen/qwen3.6-27b` | 100% | 100% | 7.0/8 | **2/5** | 41.8s | rejected |
  | `gemma-4-31b-it` | — | — | — | — | — | disqualified (latency) |
  | `gemma-4-26b-a4b-it` | — | — | — | — | — | disqualified (no text part) |

  **The decision turned on a failure mode a pass/fail test would have missed.** qwen populates more fields — but it echoed the literal schema placeholder `"string"` into `datasets`/`metrics` on **2 of 5 papers (40%)**. That parses, validates, *and silently injects fabricated content into a hallucination-graded pipeline* — precisely what `SPEC §14.2` forbids. Its 7.0/8 field score is itself inflated by the echo: excluding those rows it scores **6.33/8**. gpt-oss echoed 0/5. **Reliability beat coverage.**

  ⚠️ **Known weakness of the winner:** gpt-oss populates only **4.6/8** content fields. Most likely a *prompt* problem, not a model problem — `extractor_v1.md` ships 3 few-shot examples against the ~20 Dagdelen et al. measured as the stabilisation point. **T-404 must expand the few-shots and re-run this bake-off; expect the field count to rise.**

  ⚠️ **Latency reality check against §0.2's ~30 min tolerance:** 26.6s/paper × ~70 papers ≈ **31 min for the extraction stage alone**, so the first full run will sit at 30–40 min end to end. The response cache makes re-runs free. Groq latency is highly variable under load (measured 3.8s–55s within one arm) — do not treat single-sample timings as stable. (`PROJECT_PLAN.md §6.2`)
- [x] **T-005** 👤 ✅ **APPROVED 2026-08-25 (`decsions.txt.txt`, clarified in session): base paper switches Aytar et al. → SurveyGen (Bao et al., EMNLP 2025, DOI `10.18653/v1/2025.emnlp-main.136`).** Unblocks T-801. *Consequences: the Introduction now quotes the base paper's own authors stating your problem — "fully automatic survey generation still suffers from low citation quality and limited critical analysis" — rather than you asserting it; low citation quality → your Verifier, limited critical analysis → your four-field schema. Dropping GROBID also stops being a deviation to defend, since that was Aytar's dependency, not SurveyGen's.*
- [x] **T-006** 👤 ✅ **DECIDED 2026-08-25: UML component diagram.** Use `diagrams/02_module_connectivity_diagram.drawio` with `02_MODULE_CONNECTIVITY_DIAGRAM_EXPLAINED.md` as the slide-12 script. ⚠️ **Slide 12 must therefore describe «subsystem» packages and provided/required interfaces — NOT the ○/● coupling notation, which only applies to the structure-chart version** (`SESSION_CONTEXT.md §7.2`). The Yourdon/Constantine alternative in `ARCHITECTURE_REVIEW.md` is now dead; do not present it.
- [x] **T-007** 👤 **DECIDED 2026-08-25 (`decsions.txt.txt`): Human-in-the-Loop is MANDATORY.** It stays in Objective 2, on PPT slide 5, and in both diagrams. **Consequence: T-609 is now a required deliverable, not a conditional one, and HITL moves onto the never-cut list.** The Sep 4 kill switch has been amended accordingly — Panel 4 can no longer be dropped wholesale, because it is the surface HITL lives on.
- [x] **T-008** 🧠 `git init`, `.gitignore`, first commit of the existing markdown and diagrams. *Done when: `git log` shows one commit and `data/`, `outputs/`, `.env`, `*.pptx` are ignored.* Done 2026-08-25: repo initialised; `.gitignore` covers `data/`, `outputs/`, `.env`, `*.pptx`; first commit is the planning artefacts plus `.env.example`.

  🔴 **DEFECT FOUND AND FIXED 2026-08-26 — this one nearly cost the whole Phase 2 data layer.** The `data/` and `outputs/` patterns were **unanchored**, so `data/` matched not only the runtime directory at the repo root but also the *source package* `src/researchgpt/data/`. The result: `src/researchgpt/data/__init__.py`, `bm25_index.py`, `chunker.py`, `embeddings.py`, `metadata_db.py` and `vectorstore.py` were **never committed** — six modules, including **T-205 ★** (offset-preserving chunker) and **T-207 ★** (distance→similarity vectorstore). `git ls-files src/researchgpt/data/` returned nothing while every acceptance test passed locally, so nothing surfaced it. A fresh clone would have had a package that imports six missing modules; a disk failure would have lost two ★ critical-path tasks outright. **Fixed by anchoring to `/data/` and `/outputs/`**, verified both ways: no `src/**/*.py` is ignored any more, and `data/llm_cache` / `outputs/runs` still are. *Verify with `git ls-files src/ | wc -l` before the next commit — it should count every source file, not 25.*

---

## 3. Phase 1 — Core skeleton (Day 1: Aug 26) ⛔

Everything else sits on this. **Do not let Cursor improvise here** — Claude Code writes the schemas, Cursor fills the bodies.

- [x] **T-101** 🧠 Author `pyproject.toml` + the directory scaffold per `RESEARCHGPT_SPEC.md §10`, minus the cut modules (`docx_writer.py`, `ragas_runner.py`, `notebooks/`). *Done when: `pip install -e .` succeeds and `import researchgpt` works.* **Done 2026-08-25.** Deps split into optional extras (`retrieval`/`graph`/`verify`/`api`/`scireviewgen`). **Environment risk cleared:** `onnxruntime`, `chromadb`, `sentence-transformers`, `langgraph` and `torch` all resolve on this machine's Python 3.14.6 — the ONNX verifier path (T-304) is viable.
- [x] **T-102** 🧠 Write `src/researchgpt/core/models.py` — all Pydantic models from `SPEC §8`. **Claude Code writes this by hand.** Every other module imports from it; a wrong shape here costs a day downstream. *Done when: `Paper`, `Chunk`, `Insight`, `Claim`, `Verdict`, `CritiqueDecision`, `RunConfig` all instantiate and round-trip through `.model_dump_json()`.* **Done 2026-08-25, verified.** Deviations from SPEC §8: `Paper.text_availability` added (T-204/T-505); `RunConfig` + nested models added; **`ALLOWED_MODELS` lives here, not in `llm.py`** — dependency-free module, so a forbidden model fails at **config-load time**. Verified: `gpt-4o`, `gpt-4o-mini`, `gemini-3.6-flash` all rejected by `RunConfig`.
- [x] **T-103** 🧠 Write `src/researchgpt/graph/state.py` — the LangGraph state per `SPEC §8.1`, with reducers. **Claude Code writes this by hand.** *Done when: a dummy two-node graph merges partial state updates correctly.* **Done 2026-08-25, verified on a real compiled LangGraph.** **Accumulate** (`add`): `papers`, `chunks`, `retrieval_log`, `decision_log`, `human_overrides`. **Replace**: `paper_insights`, `verified_claims`, `iteration`, plan fields. **Merge**: `artefacts`. *Consequence for T-403: papers/chunks accumulate, so the Retriever must dedupe by id — the reducer will not.* Added beyond SPEC §8.1: `run_id`, `decision_log`, `human_overrides`, `PLAN_FIELDS`.
- [x] **T-104** ⌨️ ★ ⛔ `src/researchgpt/core/llm.py` — the LLM adapter, with **all four** of: prompt-hash disk cache, requests-per-minute throttle, exponential backoff on 429, and a rate-limit guardrail that aborts loudly instead of looping silently. *This is the highest-leverage file in the build (`PROJECT_PLAN.md §6.2`) — every dev re-run after the first costs zero API requests.* **Claude Code reviews it line by line; Cursor does not touch it again afterwards.** **It also owns the §0.1 model allowlist**: a single `ALLOWED_MODELS` constant, checked before any HTTP request is constructed, raising on anything outside it. That check is the project's entire defence against accidentally billing a paid endpoint — there is no second line of defence. *Done when: calling the same prompt twice issues exactly one HTTP request; a simulated 429 storm aborts with a named exception rather than hanging; and `model="gpt-4o-mini"` raises before any network call is made.* Done 2026-08-25 via `handoffs/phase1.md`: cache / allowlist / RateLimitExceeded / extract_json / Google `thought`-part skip all verified in `tests/test_phase1_acceptance.py`.
- [x] **T-105** ⌨️ `src/researchgpt/core/config.py` — YAML loader → `RunConfig`, with env-var overrides. *Done when: `load_config("configs/default.yaml")` returns a validated `RunConfig` and an unknown key raises.* Done 2026-08-25: YAML + `RESEARCHGPT__REVIEW__MAX_PAPERS` + forbidden-model ValidationError verified.
- [x] **T-106** 🧠 `configs/default.yaml` — revised from `SPEC §10.1` for the CPU/$0 reality: `bge-small-en-v1.5`, `ms-marco-MiniLM-L-6-v2`, `sources: [openalex, arxiv]`, `max_papers: 60` (25 for ablations), no `max_cost_usd`. **Do not copy `SPEC §10.1`'s `llm:` block — it names `gpt-4o-mini` and `gpt-4o`, both forbidden under §0.1.** Name only the T-004 winner and one allowlisted backup. *Done when: it loads clean through T-105 and every model it names passes T-104's allowlist check.* **Done 2026-08-25**, and **revised after the T-004 smoke measurement**: primary is now `openai/gpt-oss-120b`, not `gemma-4-31b-it`. See the measurement table in the file header. **T-004 still owes the 5-paper clean-parse-rate run.**
- [x] **T-107** ⌨️ ★ `src/researchgpt/core/logging.py` — the `trace.jsonl` writer. Append-only, one JSON object per agent event: `{ts, run_id, agent, event, payload, iteration}`. *Free today, impossible to retrofit. Every figure in the report comes from this file.* *Done when: a three-event dummy run produces a parseable `trace.jsonl`.* Done 2026-08-25: three-event dummy + non-serialisable payload fallback verified.
- [x] **T-108** ⌨️ `src/researchgpt/cli.py` — Typer stub: `researchgpt --version`, `researchgpt run --question "..." --max-papers N`. *Done when: `researchgpt --version` prints.* Done 2026-08-25: `version` prints `0.1.0`; `run -q test` writes `run_start`/`run_end` to `trace.jsonl`.
- [x] **T-109** 🧠 `src/researchgpt/core/prompts/` — one versioned file per agent, each with the header comment required by `SPEC §14.4`. Bodies may be stubs today; the **Extractor prompt must be real** — structured output stabilises at ~20 few-shot examples and is malformed below ~10 (`SESSION_CONTEXT.md §5.10`). **Done 2026-08-25:** `extractor_v1.md` (real; verified end-to-end producing a valid `PaperInsight` from a live call), plus `planner_v1.md` (**hardened 2026-08-25 with two measured constraints: queries must be 3–5 terms because OpenAlex ANDs them, and must mix broad with specific because targeted queries measurably out-recall topical ones**), `critic_v1.md`, `writer_v1.md` stubs. ⚠️ **Ships 3 few-shot examples, not 20** — T-404 must expand before Extractor output is trusted for a real run.

---

## 4. Phase 2 — Retrieval (Days 2–3: Aug 27–28)

Bad retrieval silently poisons grounding, which is the graded criterion. This phase is where Cursor earns its keep — the connectors are mechanical.

- [x] **T-201** ⌨️ 📋 `tools/search_sources.py` — **OpenAlex** connector. ⚠️ **Verified 2026-08-25: OpenAlex has no `abstract` field** — only `abstract_inverted_index`, which must be de-inverted — and `doi` arrives as a full URL needing normalisation. Both are pinned in `handoffs/phase2.md`. Use the `title_and_abstract.search` filter with a hard date window; plain `search=` sorted by citations returns irrelevant high-citation medical papers (`SESSION_CONTEXT.md §9`). Return `Paper` objects. *Done when: a query returns ≥20 deduped `Paper`s carrying DOI, venue, year and OA link.*
- [x] **T-202** ⌨️ 📋 Same file — **arXiv** connector via the Atom API. ⚠️ **Verified 2026-08-25: `http://export.arxiv.org` returns HTTP 301 with an empty body — HTTPS plus `follow_redirects=True` is mandatory.** Also: arXiv entries usually carry **no** `<arxiv:doi>`, so the dedup key is the synthetic `10.48550/arxiv.<id>` with the version suffix stripped. *Done when: it returns `Paper`s with `arxiv_id` and a PDF URL.*
- [x] **T-203** ⌨️ 📋 DOI-based dedup + `data/metadata_db.py` (SQLite). *Done when: the same paper arriving from both sources collapses to one row.*
- [x] **T-204** ⌨️ 📋 `tools/pdf_loader.py` — OA PDF fetch + PyMuPDF text extraction with a section-header regex. Set `text_availability` = `full` | `abstract_only`. *Done when: 10 OA PDFs parse and one paywalled paper degrades to `abstract_only` without crashing.*
- [x] **T-205** ⌨️ 📋 `data/chunker.py` — section-aware first, then recursive character split at 1200/200. **Must preserve `start_char`/`end_char`** — grounding depends on it. Never merge across papers. *Done when: every chunk's offsets slice the original text back out exactly.* ✅ **Independently re-verified by Claude Code 2026-08-25** on 17.6 KB of sectioned text: `text[start:end] == c.text` for all 20 chunks, **100% character coverage**, all 5 sections preserved, sizes 223–1200. *This was the file that could have silently poisoned every evidence span in Phase 5; it is correct.*
- [x] **T-206** ⌨️ 📋 `data/embeddings.py` — `BAAI/bge-small-en-v1.5` on CPU, batched. *Done when: 3,000 chunks embed in under 5 minutes on this machine and the wall time lands in the trace.* ✅ **Verified on REALISTIC 1,200-char chunks: 13.7–23.5 chunks/s → 3,000 chunks in 2.1–3.6 min** (the range is CPU contention from concurrent jobs). The plan's <5 min assertion holds. ⚠️ **Cursor's suite reported "3,000 chunks in 8.5s", but it embedded 65-character strings — ~26× optimistic. Do not quote that number.** The acceptance criterion has been tightened to name the chunk size. Model loads in 6.0s, dim=384. ⚠️ **BGE needs an asymmetric prefix**: queries get `"Represent this sentence for searching relevant passages: "`, documents get none. Reversing this silently degrades retrieval — pinned in `handoffs/phase2.md`.
- [x] **T-207** ⌨️ 📋 `data/vectorstore.py` — Chroma persistent collection. *Done when: a dense k=30 query returns chunks with metadata intact.*
- [x] **T-208** ⌨️ 📋 `data/bm25_index.py` — `rank_bm25` over the same chunks. *Done when: sparse k=30 returns results.*
- [x] **T-209** ⌨️ 📋 `tools/hybrid_retriever.py` — RRF fusion, `score = Σ 1/(60 + rank_i)`. *Done when: the fused ranking differs from both inputs and is stable across runs.*
- [x] **T-210** ⌨️ 📋 `tools/reranker.py` — `cross-encoder/ms-marco-MiniLM-L-6-v2` on CPU → top-12. **Measure and log per-query latency.** *Done when: top-12 is sensible on three hand-checked queries and the latency is in the trace.* ✅ **Verified on REALISTIC 1,200-char chunks: 1,335–1,425 ms to rerank 60 candidates.** ⚠️ **Cursor's suite reported 173–194 ms, but it reranked 80-character chunks — ~7× optimistic. Do not quote that number.** (model load 36s on first download, cached after). *Run budget: ~8 sub-questions × up to 3 critic iterations ≈ 24 rerank calls ≈ 32s per run — negligible beside the ~4 min extraction stage, so reranking is not a latency concern.* **This number is the stock baseline T-334 compares the Phase 3C fine-tune against.** ⚠️ Ammann et al. warn their gains "rely on a strong, domain-aligned cross-encoder reranker" — yours is a 22M MiniLM, so **measure reranking's contribution separately** (`SESSION_CONTEXT.md §5.6`).
- [x] **T-211** ⌨️ 📋 Venue tiering in `metadata_db`, from OpenAlex venue metadata. *Done when: papers carry a tier label usable as a ranking feature.*
- [x] **T-214** ⌨️ 📋 **DONE 2026-08-26 (by Claude Code, not Cursor).** *Was outstanding after Phase 2: appended to `handoffs/phase2.md` at 15:58 on 2026-08-25, after Cursor had already read the file, so it was never written — while `configs/default.yaml` already listed `semantic_scholar` in `sources.enabled`. A config naming a connector that did not exist failed silently for a day; **T-102's `SourcesConfig` now validates `enabled` against `IMPLEMENTED_SOURCES`** so that exact gap cannot recur.* **Semantic Scholar connector** (`tools/search_sources.py`). *Reinstated 2026-08-25 — see §0.2. It is claimed on 8 slides of the Review-2 deck, and the rate-limiting that got it cut is survivable now that latency is free.* `GET https://api.semanticscholar.org/graph/v1/paper/search`, `fields=paperId,externalIds,title,abstract,year,venue,authors,citationCount,isOpenAccess,openAccessPdf`. **Must be best-effort and degradable: on sustained 429s, log and return `[]` so the run continues on OpenAlex + arXiv.** Never a hard dependency. *Advantages over OpenAlex worth exploiting: abstracts come back directly (no de-inversion) and `externalIds` carries DOI + ArXiv + DBLP + PubMed ids, which strengthens T-203 dedup.* *Done when: a query returns ≥5 `Paper`s with populated abstracts; and a forced 429 storm returns `[]` without raising.*

  **Verified 2026-08-26** — `search_semantic_scholar()` in `tools/search_sources.py`, 5 acceptance tests in `tests/test_phase2_acceptance.py`, all green.
  - *Mapping* — every field per the handoff, offline against a captured S2 payload: DOI URL → bare lowercase via T-201's `normalise_doi`, empty-string venue → `None`, `is_preprint = "JournalArticle" not in publicationTypes`, plain-text abstracts (no de-inversion).
  - *Degradability* — a sustained-429 transport returns `[]` after exactly 6 attempts with a logged warning and no exception. A 429→429→200 transport recovers on attempt 3, so the backoff genuinely retries rather than counting down to `[]`.
  - *Request shape* — `year={year_min}-`, `limit ≤ 100`, all 11 fields requested; **`x-api-key` sent only when a key exists** (`S2_API_KEY` from the environment).
  - *Live* — 20 papers, 14 with populated abstracts, 19 with DOIs, all normalised. **But 2 of 3 live probe queries throttled out** (each burning the full 60 s backoff), so today's keyless hit rate was **1 in 3** — at or below the 2026-08-25 measurement. The connector degrades correctly every time, but this is the evidence for **T-215**: without a key S2 contributes roughly a third of the time.
  - *Backoff/politeness constants are module-level* (`_BACKOFF_SCHEDULE`, `_POLITE_SLEEP_S`) so the suite can zero them instead of sleeping through a 60 s storm; a private `_transport` argument is the test seam. The public T-214 signature is unchanged.
- [ ] **T-215** 👤 **Apply for a free Semantic Scholar API key** (https://www.semanticscholar.org/product/api — they grant academic keys). *Measured keyless 2026-08-25: only 1 of 4 rapid requests succeeded, and 1 of 3 backoff-retried queries failed entirely. A key removes the problem outright and makes T-214 reliable rather than opportunistic.* Put it in `.env` as `S2_API_KEY`; T-214 must work with or without it.
- [x] **T-212a** 🧠 ★ **Build the machine-readable gold set.** *Gap found 2026-08-25: T-212's gate depends on "your own 25-paper bibliography", but that bibliography lived only as prose and markdown tables across three documents — no task created a consumable version of it, so the gate had nothing to run against.* **Done:** `src/researchgpt/eval/build_gold_set.py` extracts every DOI from `LITERATURE_REVIEW.md`, `PAPER_ANALYSIS.md` and `PAPER_DEEP_DIVE.md`, resolves each against OpenAlex for canonical title/year/venue/OA status, and writes `eval/gold_sets/own_bibliography.json`. **35 DOIs extracted, 35 resolved, 0 unresolved.** Unresolved entries are recorded rather than dropped — a gold set that silently loses entries produces a recall number wrong in the flattering direction. *Re-runnable, so it feeds T-810's `make reproduce`.*
- [ ] **T-212** 🧠 ★ **Retrieval eval against your own 25-paper bibliography** (`PROJECT_PLAN.md §5.2`). ⚠️ **GATE CORRECTED 2026-08-25 — the original was unachievable.** `PROJECT_PLAN.md §9.2` and this task both said *"Recall@20 ≥ 0.80"*, but the gold set has **35 papers**, so retrieving 20 caps recall at **20/35 = 0.57**. The gate could never pass as written, and chasing it would have burned the T-213 buffer on a phantom failure. **Corrected gate: `Recall@60 ≥ 0.80`** — 60 is `review.max_papers`, i.e. the corpus the Extractor actually sees, which is what the downstream stages depend on. *Done when: recall of the retrieved corpus (union across search queries, capped at max_papers=60) is measured against `eval/gold_sets/own_bibliography.json`. Report Recall@20 per query as a secondary diagnostic, clearly labelled with its 0.57 ceiling. If Recall@60 misses 0.80, spend T-213 on it — do not build agents on bad retrieval.*

  🔴 **RUN 2026-08-25 — GATE FAILS, but the cause is NOT the retrieval stack.** Recall@60 = 0.029; 13/35 gold papers found across a 447-paper union. **Root cause diagnosed: query shape, not connector quality.**
  1. **OpenAlex ANDs every term** in `title_and_abstract.search`. Measured: `scientific claim verification evidence entailment SciFact` → **0 results**; `scientific claim verification` → **4,174**. My first eval harness used 5–8 term queries and returned near-nothing — producing a spurious Recall = 0.000 that had nothing to do with Cursor's code.
  2. **Specific queries massively outperform topical ones.** Measured: **5 targeted queries recovered 7 gold papers that 15 generic topical queries missed entirely.** This matches `SESSION_CONTEXT.md §9`, where the original review needed *"6 thematic clusters and 28 named-system queries"* — mostly *specific* queries.
  3. **The connectors are verified sound** — every probed gold paper is retrievable from OpenAlex given an appropriately-shaped query.

  ⚠️ **Sequencing consequence: T-212 cannot be meaningfully gated until the Planner (T-402) exists.** Recall is dominated by query generation, and that is the Planner's job. The 15 hand-written queries in `eval/retrieval_eval.py` are a stand-in. **Re-run this gate right after T-402 and treat that as the real Phase 2 gate.**

  **MEASURED 2026-08-26 (Claude Code). Gate FAILS. Left unticked deliberately — the diagnosis says it cannot pass before T-402.**

  | run | pool | union recall | **Recall@60 (gate)** |
  |---|---|---|---|
  | 2026-08-25, unranked | 447 | 0.371 | 0.029 |
  | `max_per_source=25`, ranked | 493 | 0.371 | **0.057** |
  | `max_per_source=100`, ranked | 1937 | **0.714** | **0.029** |

  *Harness defects found and fixed first, so the number is trustworthy:* (a) the union was ordered by **which query happened to run first**, so `union[:60]` never ranked anything — it is now ranked through the real T-209 retriever + T-210 reranker and merged round-robin across sub-questions; (b) the first stage used the production `dense_k=30`, which returns a *global* top-60 and silently discards more of each sub-question's candidates the larger the pool grows — now widened to the pool, and **locked by a regression test that was verified to fail against the old behaviour (50 of 88 candidates dropped)**.

  **Two hypotheses of mine were refuted by the data, and are recorded because they would otherwise be retried:**
  1. *"DOI-only matching undercounts, because arXiv preprints carry synthetic `10.48550/arxiv.*` DOIs."* Title-fallback matching adds **0.000 at `mps=25`** and one paper at `mps=100`. The instrumentation is verified live (a synthetic preprint-of-a-gold-paper scores, and does not double-count) — the misses are simply genuine absences.
  2. *"The `mps=100` gate drop is an artefact of the narrow first stage."* Fixing it changed the gate by **nothing** (0.029 → 0.029) even though the first stage now keeps 100–217 candidates per sub-question instead of ~30. The drop is real: more candidates genuinely make the top-60 selection harder.

  **The binding constraint is query generation, and that is T-402's job — confirmed three ways:**
  - Of the 10 gold papers never retrieved at `mps=100`, **10/10 are in OpenAlex**, **0** are excluded by the `year_min=2019` window, and **9/10 are findable by exactly the short-query shape we already use** (`eval/diagnose_misses_t213.json`, `src/researchgpt/eval/diagnose_misses.py`). They were not unreachable. **They were never asked for.**
  - Gold papers that *are* pooled rank **38 times** across the 15 sub-question rankings, but only **2 reach rank ≤ 4** — and rank ≤ 4 is all a 60-paper corpus split over 15 sub-questions can take.
  - The stock reranker is **above chance but only just**: 2 top-4 hits against 1.19 expected at random. It is not broken; it is under-informed by generic topic queries. Where a query was specific (`"scientific survey generation"`), gold landed at **ranks 1 and 2**.

  **Consequences — decide these, do not drift into them:**
  - ⚠️ **Do NOT adopt `max_per_source: 100` yet.** It nearly doubles the *ceiling* (0.371 → 0.714) but makes the corpus the Extractor actually sees **worse** (2 gold papers in the top 60 → 1). Revisit after T-402, when ranking can exploit a deeper pool. `configs/default.yaml` is deliberately unchanged.
  - ⚠️ **Do NOT spend T-213(4) on `bge-small` → `bge-base`.** Ranking is weak because the queries are generic, not because the encoder is small. TASKLIST already warned this; the measurement now confirms it.
  - ⚠️ **The gate has a structural tension worth raising before T-402.** `max_papers=60` over ~15 sub-questions is **4 slots each**. `Recall@60 ≥ 0.80` needs 28 of 35 gold papers into those 60 slots. Either T-402 emits far more specific queries, or `max_papers` rises, or the gate needs restating. *This is a decision for the human, not a number to chase.*

  ⚠️ **Second flaw, in my own harness, recorded so it is not trusted:** `Recall@60` takes the first 60 DOIs in *insertion order across queries* — arbitrary, because the eval has no ranking stage. **Until it is wired through T-209/T-210, quote recall over the full union (0.371), not Recall@60.** Use **F2, not F1**, for screening: recall matters more than precision when discarding papers (`SESSION_CONTEXT.md §5.10`).
- [ ] **T-212b** 🧠 **Secondary retrieval eval against SciReviewGen gold sets** (T-324), once Phase 3B lands. Reports Recall@20 at scale (hundreds of chapters) rather than against one 25-paper bibliography. *Treat your own bibliography as the primary gate and this as the breadth check — SciReviewGen is frozen at S2ORC 2020-07-05, so live OpenAlex retrieval will surface post-2020 papers that are correct but score as false positives. **Report that as a measurement artefact, not as a retrieval failure.***
- [ ] **T-213** 🧠 ★ **Buffer — now has a defined job, not a contingency.** Cheapest first: **(1)** re-run T-212 after T-402 with real Planner queries — highest leverage, costs nothing; **(2)** wire the eval through T-209/T-210 so `Recall@60` ranks instead of using insertion order; **(3)** raise `max_per_source` above 25 and re-measure; **(4)** only then consider `bge-small` → `bge-base`. *Do not escalate the embedding model before fixing the queries — the evidence says query shape dominates, and a model swap would mask that.* **Buffer — retrieval quality fixes only.** First escalation if recall is short: `bge-small` → `bge-base` (~109M). **Cheap under §0.2** — measured 2.13 min for 3,000 chunks with `bge-small`, so `bge-base` costs roughly 6 min. Take it if T-212 lands anywhere near the 0.80 gate rather than exactly at it. Bi-encoders embed once and cache, so size costs ingestion time, not per-query time. *Do not spend this buffer on features.*

  **Partially spent 2026-08-26.** *(2) wire the eval through T-209/T-210* — **done**, and it is what turned the gate from unmeasurable into measurable (0.029 → 0.057). *(3) raise `max_per_source`* — **done and measured at 100**; it raises the ceiling but lowers the gate, so it is **not** adopted (see T-212). *(4) `bge-base`* — **do not spend**, the evidence says query shape dominates. *(1) re-run after T-402* — **still the highest-leverage item, and now the only one left.** Pool caching (`--cache`, `eval/cache/`) was added so that re-run costs a re-rank, not another 18 minutes of Semantic Scholar backoff.

---

## 5. Phase 3 — Verifier training ★ (parallel, on Kaggle, Days 2–4)

This is the graded component *and* the required training component. **Start it the moment T-001/T-002 close — it runs unattended while Phase 2 proceeds.**

- [x] **T-301** ⌨️ Build `(claim, evidence_sentence) → SUPPORT | CONTRADICT | NEI` pairs. ⚠️ **USE `allenai/scifact_entailment`, NOT `allenai/scifact`** — pre-checked 2026-08-25: plain `allenai/scifact` returns **HTTP 501** from the datasets-server, the signature of a **script-based dataset**, which modern `datasets` releases no longer load. `scifact_entailment` is ungated, loads normally, and is *already in entailment form*. **Verified schema:** `claim_id`, `claim` (str), `abstract_id`, `title`, `abstract` (**list of sentences**), `verdict` ∈ `{SUPPORT, CONTRADICT, NEI}`, `evidence` (**list of sentence indices into `abstract`**). Splits: **train 919 / validation 340**. **Pairing rule:** for `SUPPORT`/`CONTRADICT` pair the claim with each sentence named in `evidence`; for `NEI` the evidence list is empty, so sample abstract sentences as the NEI class. *`verdict` is `NEI`, not `NOT_ENOUGH_INFO` — map it explicitly.* ⚠️ **There is no test split, only train and validation.** Hold out from `train` for tuning and keep `validation` untouched as the reported held-out set (T-305). *Done when: class counts and pair counts are printed per split.* ✅ **DONE 2026-08-27** — `src/researchgpt/verify/scifact_pairs.py`.

  | split | pairs | claims | SUPPORT | CONTRADICT | NEI |
  |---|---|---|---|---|---|
  | train | 1463 | 688 | 549 (37.5%) | 312 (21.3%) | 602 (41.1%) |
  | dev | 272 | 121 | 112 (41.2%) | 52 (19.1%) | 108 (39.7%) |
  | **validation (held out)** | **628** | **300** | 235 (37.4%) | 131 (20.9%) | 262 (41.7%) |

  🔴 **TASKLIST was wrong about the loading path, and it would have blocked the task.** This file says to use `scifact_entailment` *because* plain `allenai/scifact` is script-based — **`scifact_entailment` is script-based too**, and `datasets>=4` refuses it outright with `RuntimeError: Dataset scripts are no longer supported`. The 2026-08-25 pre-check passed because it probed the datasets-server API, not `load_dataset`. **Fix: read the Hub auto-converted parquet branch `refs/convert/parquet`** — identical rows, no script, no token. Both the module and the Kaggle notebook use it.

  **Row shape re-verified rather than trusted** (all 1,259 rows): zero out-of-range evidence indices, zero NEI rows carrying evidence, abstracts 3–25 sentences.

  ⚠️ **The train/dev split groups by `claim_id`, not by row.** One claim appears in up to **5** rows with different abstracts, so a row-level split puts the same claim text on both sides and inflates the dev score — the identical failure mode this file already warns about for T-330. Asserted in code and regression-tested.

  *Deliberately not done:* mining extra NEI pairs from the non-evidence sentences of SUPPORT/CONTRADICT abstracts. Those sentences sit in an abstract that *does* support the claim, so a near-paraphrase of the evidence would be labelled NEI and teach the model the opposite of its job.
- [x] **T-302** 🧠 Write the Kaggle training notebook. ✅ **Warm-start checkpoint verified available 2026-08-25: `cross-encoder/nli-deberta-v3-small`** (ungated, ships safetensors, 475k downloads). Use it rather than bare `microsoft/deberta-v3-small`, which has **no safetensors** and would need a `.bin` load. `cross-encoder/nli-deberta-v3-base` is the verified escalation target for T-307. Three-way head, 2–3 epochs, cross-entropy, fixed seed. *Claude Code writes this — the warm-start detail is easy to get wrong and expensive to redo.* ✅ **DONE 2026-08-27** — `notebook-kaggle-traning/01_train_verifier_scifact.ipynb` (23 cells) + `notebook-kaggle-traning/README.md`.

  **The warm-start detail, spelled out, because it was indeed easy to get wrong.** The stock head is `{0: contradiction, 1: entailment, 2: neutral}`; ours is `(SUPPORT, CONTRADICT, NEI)` = `(entailment, contradiction, neutral)`. The notebook **permutes the trained head by `[1, 0, 2]` rather than reinitialising it**, so the fine-tune starts from a model that already solves two thirds of the problem. The permutation is derived from the checkpoint own `config.id2label` and raises rather than guessing. *The same permutation is what makes T-305 stock arm a fair baseline instead of a near-chance strawman.*

  **Also pinned: pair order is `(evidence, claim)`** — premise then hypothesis. Reversing it silently trains a different task. One `encode_pair()` helper owns the decision and a test asserts it.

  ⚠️ **`accelerate>=0.26` is a hard requirement of `Trainer` and is not implied by `transformers`.** Found by running the notebook cells locally; section 2 now installs it.

  **The notebook was smoke-tested, not just written.** All 11 code cells were executed locally on CPU against a 48-pair subset — data build, tokenization, head permutation, stock baseline, training loop, T-305 table, T-307 gate and save all ran clean. Kaggle supplies the GPU, not the first syntax check.

  **The notebook carries a mirror of the T-301 pairing code** (Kaggle cannot import this repo). `tests/test_phase3_acceptance.py` execs the notebook own cells and asserts byte-identical pairs, split and constants against the module — **verified to fail** when the notebook sampling rule or `SEED` is altered.
- [x] **T-303** 👤 Run it on Kaggle GPU. *Done when: held-out P/R/F1 per class is printed and the checkpoint downloaded. Expect under an hour.* **READY — this is the one Phase 3 step only you can do.** Upload `notebook-kaggle-traning/01_train_verifier_scifact.ipynb`, set **Accelerator = GPU T4 x2** and **Internet = On** in the Settings panel (Kaggle ignores the notebook own request on import), Run All, ~10–20 min. Download `verifier-scifact.zip` **and** `verifier_metrics.json`. Step-by-step in `notebook-kaggle-traning/README.md`.

  ✅ **RUN 2026-08-27 by Sreekaran. Checkpoint + metrics delivered.** Training took **306 s** on a T4. Held-out P/R/F1 per class is in `verifier_metrics.json` and reproduced under T-305 below. Checkpoint unzipped to `data/models/verifier-scifact/`.

  **Sanity check passed, and it is the one that mattered:** the run's own stock row printed **accuracy 0.5525, macro-F1 0.5155** against the **0.553 / 0.516** measured locally beforehand. Matching to three decimals proves the notebook rebuilt the identical pairs from the identical seed *and* applied the label permutation correctly — so the stock-vs-tuned delta is a real comparison rather than two different tasks silently scored against each other.

  ⚠️ **Deviation from spec, recorded so the report does not misstate it: `EPOCHS` was changed 3 → 15.** Verified from `training_args.bin` that this was the *only* change — seed, learning rate, batch size, warmup, weight decay and the best-checkpoint criterion are all as authored. **The result stands:** `load_best_model_at_end=True` on dev macro-F1 means 15 epochs behaves as "up to 15, selected early", and the held-out `validation` split was never touched during training, so 0.769 is not inflated by the extra epochs. **The report, deck and `TRAINING_SPEC.md` must say 15 epochs, not the 2–3 this file specifies.**
- [x] **T-304** ⌨️ Export to **ONNX + int8 dynamic quantization** for CPU inference. *Done when: the ONNX model reproduces PyTorch logits within tolerance on 20 held-out examples.* ✅ **DONE 2026-08-27** — `src/researchgpt/verify/export_onnx.py`, verified end-to-end on the stock checkpoint (the fine-tuned one runs through the identical path).

  **RE-RUN 2026-08-27 on the real fine-tuned checkpoint. The conclusion reversed, and the shipped artefact is fp32, not int8.**

  | arm | accuracy | macro-F1 | vs T-307 gate 0.75 | claims/sec | size |
  |---|---|---|---|---|---|
  | PyTorch | 0.788 | 0.769 | — | (torch, not shipped) | 568 MB |
  | **ONNX fp32 — SHIPPED** | **0.788** | **0.769** | **PASS** | **25.4** | 568 MB |
  | ONNX int8 `per_channel=True` | 0.758 | 0.741 | **FAIL** | 45.7 | 173 MB |
  | ONNX int8 `per_channel=False` | 0.764 | 0.741 | **FAIL** | 20.5 | 172 MB |

  **Export correctness: PASS.** ONNX fp32 vs PyTorch is max abs delta-logit **9e-6**, argmax **20/20**, and macro-F1 identical to six decimals. The export is faithful; nothing below is an export bug.

  🔴 **int8 drops the *deployed* model below the T-307 gate that the *trained* model passes** — 0.769 → 0.741 against a 0.75 threshold. On the **stock** checkpoint int8 had been free (macro-F1 actually rose 0.516 → 0.539), so this reversed once the model was fine-tuned: the trained weights are quantization-sensitive in a way the stock ones were not. **Do not generalise a quantization result measured on a different checkpoint.**

  ⚠️ **This also exposed an ambiguity in T-307 / `decisions.txt` D-09: neither says *which artefact* the gate applies to.** Resolved here as **the artefact that actually runs in the pipeline**, because a gate on a model you do not deploy measures nothing. Under that reading int8 fails and fp32 passes.

  **Decision: ship fp32.** All int8 buys is ~35 s per run (79 s vs 44 s for 2,000 claims, against a ~30-minute budget) and 400 MB of disk. §0.2 and `PROJECT_PLAN §4.2` both govern exactly this trade — *"trade latency, not accuracy — the verifier is the graded component"* — so this follows the project's own stated rule rather than a preference. **Escalating to `deberta-v3-base` (T-307) would have been the wrong fix**: capacity is not the problem, quantization is, and a bigger model quantized the same way would likely lose a similar slice.

  `export_onnx.py` now keeps **both** graphs, gates each against T-307 independently, and writes `recommended_model` / `recommended_path` into `export_report.json`. **T-502 must load the path that report names**, not a hard-coded filename — which artefact wins is a property of the checkpoint and has already flipped once. *(`per_channel=False` is strictly dominated: identical accuracy, half the speed.)*

  🔴 **The stated acceptance criterion — "reproduces PyTorch logits within tolerance on 20 held-out examples" — is the wrong test, in both directions.** On the stock checkpoint it flagged a quantization that was demonstrably free (2/20 argmax flips, yet +0.022 macro-F1 over the full set — the flips cancel). On the tuned checkpoint 17/20 argmax agreement understates a real 0.027 macro-F1 loss. **Twenty per-pair comparisons cannot measure an aggregate property.** The 20-pair logit check is retained only as an *export-correctness* test, where a tight tolerance genuinely belongs; the ship/no-ship decision is now made on macro-F1 over all 628 held-out pairs.

  `avx2` not `avx512_vnni` — VNNI is faster but silently unsupported on older cores, and a demo that will not start on the examiner machine is worse than one that is slow.
- [x] **T-305** 🧠 ★ **Stock-vs-fine-tuned table** on the same held-out set. *This is the headline result that justifies the training component, and a graded deliverable in its own right.* **HARNESS DONE, awaiting T-303.** `src/researchgpt/verify/evaluate.py`; the notebook also computes the table on Kaggle so you see it immediately.

  **The `stock` row is already measured** (2026-08-27, 628 held-out pairs, `cross-encoder/nli-deberta-v3-small` zero-shot through the label permutation):

  ✅ **COMPLETE 2026-08-27**, 628 held-out pairs, both arms scored through the identical code path and label permutation:

  | arm | accuracy | macro-F1 | SUPPORT F1 | CONTRADICT F1 | NEI F1 |
  |---|---|---|---|---|---|
  | stock (`nli-deberta-v3-small`, zero-shot) | 0.553 | 0.516 | 0.370 | 0.542 | 0.634 |
  | **fine-tuned (SciFact, 15 epochs)** | **0.788** | **0.769** | **0.783** | **0.672** | **0.851** |
  | **delta** | **+0.235** | **+0.253** | +0.412 | +0.130 | +0.217 |

  ★ **Lead the report with the failure mode, not the delta.** Stock SUPPORT **recall is 0.234** — it predicts NEI for **158 of 235** true SUPPORT pairs while holding SUPPORT precision at 0.887. Untuned, the verifier is a filter that discards two thirds of all true claims: perfectly safe, and useless. Fine-tuning takes SUPPORT recall to **0.766** and pays only 0.887 → 0.800 in precision to do it.

  *That is the argument for the training component in one sentence: the stock model is not merely weaker, it is unusable in the intended role, because a claim filter that drops most true claims produces a survey with nothing left in it.* A bare "+0.25 macro-F1" does not carry that.

  **CONTRADICT stays the weakest class (F1 0.672)** and is also the rarest (131 of 628). Worth one line in Limitations: contradiction detection is the hardest of the three and the one with least training signal — SciFact has 194 CONTRADICT claims against 370 SUPPORT.
- [x] **T-306** ⌨️ ⚠️ **Run `pip install -e ".[verify]"` before starting.** Pre-checked 2026-08-25: **`sentencepiece` and `protobuf` are MISSING on this machine**, and DeBERTa-v3 uses a SentencePiece tokenizer — without them it fails with a misleading conversion error. **Kaggle ships them, so T-303 is unaffected; only the local steps (T-304/T-306) break.** Both are now in the `verify` extra along with `optimum[onnxruntime]` for the export. ✅ **DONE 2026-08-27** — extras installed, `src/researchgpt/verify/benchmark.py`. Measure **per-claim CPU latency** for the int8 model. *Done when: claims/sec is recorded. A run makes ~1.5–2k forward passes, so even 20/sec is a couple of minutes.*

  Measured on the **shipped fp32** model (see T-304 for why fp32 and not int8):

  | batch | fp32 claims/sec | int8 claims/sec |
  |---|---|---|
  | **1** | **25.4** | **45.7** |
  | 8 | 23.2 | 24.1 |
  | 16 | 14.4 | 19.9 |
  | 32 | 7.7 | 16.1 |

  **25.4 claims/sec** — a 2,000-forward-pass run spends **~79 s** in the verifier, against int8's ~44 s. Both are comfortably above the 20/sec reference point, so **verification is not a schedule risk either way**, which is exactly why the 0.027 macro-F1 was not worth trading for the 35 s (T-304).

  ⚠️ **Batching makes it SLOWER — 3.3x slower at batch=32 (fp32), 2.8x (int8). Confirmed on three separate models, so it is not an artefact. This is a design instruction for T-502, not a curiosity.** Two causes compound: padding (pairs average 59 tokens against a 121-token batch max, so a padded batch wastes over half its compute) and the fact that ONNX Runtime int8 CPU kernels are already internally threaded, so a bigger batch buys no parallelism and only pays the padding. Tokenization is 2% of wall time, so it is not the bottleneck either. **T-502 must feed the verifier one pair at a time** — the "always batch" instinct from GPU training is actively wrong here.

  ⚠️ **Dependency note:** installing the `verify` extra pins `transformers` down to 4.57.6 (via `optimum`), which pip reports as conflicting with `sentence-transformers 6.0.0`. **Verified harmless** — the Phase 2 embedder and reranker both still work and all 26 pre-existing tests pass. Do not "fix" the warning by upgrading `transformers`; that breaks the ONNX export path instead.
- [x] **T-307** 🧠 **Escalation gate.** If held-out F1 is poor, retrain `deberta-v3-base` (~184M) and quantize harder. **Trade latency, not accuracy** — the verifier is the graded thing. **§0.2 makes this trade nearly free: lean toward escalating rather than defending `small`.** The only real cost is Kaggle time, and both models train in well under an hour. ✅ **THRESHOLD FIXED 2026-08-27, BEFORE ANY TRAINING RUN** — `decisions.txt` D-09: **escalate if held-out macro-F1 < 0.75.** Implemented in `evaluate.escalation_verdict()` and applied mechanically by the notebook section 10, so the call cannot be rationalised after seeing the number. A test asserts the constant is still 0.75, which fails if anyone edits it post-hoc. Escalation target `cross-encoder/nli-deberta-v3-base` is verified loadable; escalating is a one-line change in the notebook section 1. ✅ **GATE APPLIED 2026-08-27: PASS — do NOT escalate.** Held-out macro-F1 **0.769 ≥ 0.75**. `deberta-v3-small` stays. **Consequence: the Kaggle quota is free for T-332 (reranker fine-tune)**, which is what Phase 3C needs and what the D-01 full-scope decision committed to.

---

## 5.1 Phase 3B — SciReviewGen integration ★ (parallel data track, Days 2–4: Aug 27–29)

**Reinstated 2026-08-25 by explicit decision, +2 days authorised.** This is a *data* track: it needs no pipeline, no LLM and no API budget, so it runs alongside Phase 2 and the unattended Kaggle training without competing for the critical path. Only T-325 needs the trained verifier.

**Why it earns its place.** `PROJECT_PLAN.md §9.6` names two credibility traps, and the first is fatal if unanswered: *"The groundedness metric is circular. The system enforces groundedness, then measures it. Groundedness = 0.98 proves only that the filter ran."* The prescribed fix is two independent measurements — the 50-claim human spot-check (T-705) **and** the SciReviewGen citing-sentence cross-check. Without this track, T-705's 50 hand-checked claims are the *entire* non-circular evidence base. With it, you add thousands of human-authored claim→evidence pairs that neither you nor your system produced. **That is the difference between "we checked 50 of our own claims" and "we validated against human-written survey text at scale."**

**What the mirror actually contains** (inspected 2026-08-25, `kejian/SciReviewGen`): 84,705 train / 4,410 validation / 4,457 test rows, two columns. `reference` = survey title `<s>` chapter `<s>` cited-paper abstract `<s> BIBnnn </s>`, repeated per cited paper. `target` = the human-written survey chapter, with inline `BIBnnn` citation markers. Both intended uses are recoverable from these two columns by parsing — no S2ORC access needed.

- [x] **T-320** ⌨️ Download `kejian/SciReviewGen` via the HF token (T-003) into `data/scireviewgen/`. Record split row counts and mirror provenance. *Done when: all five parquet shards load and the row counts match 84,705 / 4,410 / 4,457.* ✅ **DONE 2026-08-27** — `src/researchgpt/eval/scireviewgen.py`. All five shards load; **84,705 / 4,410 / 4,457 exact match**. Provenance written to `data/scireviewgen/provenance.json`. No HF token needed — the mirror is ungated. 507 MB.
- [x] **T-321** ⌨️ ⛔ `eval/scireviewgen_parser.py` — split `reference` into `(survey_title, chapter_id, [{bib_id, abstract}])` on the `<s>` / `</s>` delimiters. **⚠️ Verify on FULL rows that every `BIBnnn` marker appearing in `target` resolves to a bib block in `reference`.** *I checked this on the datasets-server preview and the API truncates long cells, so the alignment could not be confirmed — it is the one unproven assumption in this track and everything downstream rests on it.* *Done when: bib-resolution rate is measured over ≥500 full rows and printed. **Gate: ≥ 0.95.*** If it is lower, the delimiter parse is wrong — fix the parser, do not silently drop the unresolved markers. ✅ **DONE 2026-08-27 — GATE PASSES PERFECTLY. Resolution rate 1.0000.**

  | split | rows | BIB markers | resolved | rate |
  |---|---|---|---|---|
  | validation | 1,000 | 8,019 | 8,019 | **1.0000** |
  | test | 1,500 | 13,393 | 13,393 | **1.0000** |

  **21,412 markers checked on FULL rows. Zero malformed blocks, zero inconsistent headers, zero empty abstracts, zero cited-but-never-marked blocks.** The delimiter grammar is perfectly regular: every one of 6,284 probed blocks is exactly four fields ending in `BIBnnn`.

  ✅ **This closes the concern this task was written around** — *"the one unproven assumption in this track and everything downstream rests on it."* It could only be checked against the datasets-server preview, which truncates long cells. On full rows it holds exactly. **The Aug 28 kill switch does not fire; the `kdercksen` fallback is not needed.**

  The parser is defensive where it costs nothing: a block whose last field is not a `BIBnnn` is counted malformed rather than parsed, and an abstract containing a literal `<s>` is rejoined rather than shifting every field left. Neither case occurs in the data; both are regression-tested.
- [x] **T-322** ⌨️ ★ `eval/scireviewgen_pairs.py` — emit human-authored claim→evidence pairs to JSONL: for each sentence in `target` containing `BIBnnn`, pair it with that bib's abstract from `reference`. Schema `{claim, evidence, bib_id, survey_title, chapter_id}`. *Done when: a 500-chapter sample yields a JSONL whose pair count and per-chapter distribution are reported.* ✅ **DONE 2026-08-27** — `src/researchgpt/eval/scireviewgen_pairs.py`. **1,665 pairs** from 500 validation chapters (436 distinct chapters, 63 distinct surveys).

  | sentence outcome | n |
  |---|---|
  | no citation | 9,672 |
  | **multi-cite → dropped (D-07a)** | **644** |
  | too short / too long | 44 |
  | dangling reference → dropped (T-323) | 144 |
  | meta-sentence → dropped (T-323) | 48 |
  | **KEPT** | **1,665** |

  **25.3% of citing sentences are multi-cite and were dropped** per `decisions.txt` D-07(a). That cost is the price of clean attribution and belongs in the report's method section, not in a footnote.

  ⚠️ **Only 63 distinct surveys across 436 chapters.** Chapters cluster heavily by survey — **direct confirmation of T-330's warning** that the Phase 3C split must dedupe by `survey_title`, never by row.
- [x] **T-323** 🧠 **Sample and QA.** Draw ~200 chapters, hand-inspect 20 pairs. Discard chapters whose bib mapping is ambiguous. *A claim sentence citing three papers is not cleanly attributable to one — decide the rule (drop multi-cite sentences, or pair against the union) and write it down, because it changes what the cross-check measures.* ✅ **DONE 2026-08-27. Rule decided in `decisions.txt` D-07(a): drop multi-cite sentences.** Written down here, in the module docstring, and in `DATA_PROVENANCE.md`.

  🔴 **The hand-inspection earned its place — it found a defect no count would have surfaced.** Stripping the citation marker can destroy the sentence: *"An integrated inverter and LIM loss model is proposed in BIB018."* becomes *"...is proposed in."* — grammatical debris with no proposition left to verify. **11% of the first 1,857-pair build was degenerate this way**: 7.3% ending on a dangling preposition, 1.1% carrying punctuation wreckage (`"Recently,, see also, Harrison 1999)"`), 2.8% meta-sentences about the survey itself rather than the cited work.

  *Left in, these would have surfaced later as verifier "errors" that were really data defects — the worst kind of measurement bug in a track whose entire purpose is an honest cross-check.* The build now repairs what it can and drops the rest, reporting both counts. Verified: zero dangling and zero debris remain.
- [x] **T-324** 🧠 **Retrieval gold sets** — chapter topic → query; cited abstracts → gold set. **SciReviewGen carries no DOIs**, so mapping onto live OpenAlex retrieval needs fuzzy title matching. *Done when: the title-match rate onto OpenAlex is measured and reported. This number is itself a limitation to state in the report, not a detail to bury.* Feeds T-212b.

  🔴 **This task as written cannot be done: SciReviewGen carries no TITLES for the cited papers either.** The `reference` column holds only `(survey_title, chapter_heading, abstract, BIBnnn)`. TASKLIST correctly flags the missing DOIs but assumes titles survive — they do not. Verified 2026-08-27.

  **Resolution: match on the abstract**, the only identifying text present. First ~18 words → OpenAlex `title_and_abstract.search`, accepted only at Jaccard ≥ 0.5 against the source abstract. Probed before building: **7 of 8 resolved**, median Jaccard **1.00**, and the distribution is bimodal (true matches 0.52–1.00, the miss 0.00) so the threshold is not delicately placed. The verification step is what makes it safe: a bare search returns plausible neighbours and would quietly build a gold set of *wrong* papers, which then reads as a retrieval failure in T-212b rather than the matching failure it is.

  🔴 **The first full run reported an 18.6% match rate. That number is VOID and must not be quoted.** The keyless OpenAlex budget expired around request ~100; every chapter from ~34 onward resolved zero. The figure was quota exhaustion wearing the costume of a measurement. **Artefacts quarantined to `eval/quarantine/`.**

  *Root cause was mine, and it is the generalisable lesson:* `resolve_abstract` caught `Exception` and returned `None`, which the caller counted as "no match". **A silent failure that is indistinguishable from a negative result will fabricate a measurement.** Fixed in two places — `search_openalex` now raises `OpenAlexBudgetExhausted` on 429 instead of letting it look like an empty result set, and T-324 stops on it, flags `partial_run_budget_exhausted` in both artefacts, and prints that the rate is unfinished.

  ✅ **Unblocked by the `OPENALEX_API_KEY` (§0.2) and re-run clean 2026-08-27** (`partial_run_budget_exhausted: false`).

  | | |
  |---|---|
  | cited papers attempted | 291 |
  | resolved onto OpenAlex | 205 |
  | **MATCH RATE** | **70.4%** |
  | median Jaccard of matches | **1.00** |
  | gold papers carrying a DOI | 189 / 205 |
  | chapters with ≥3 gold papers | 33 of 60 |

  **The median match is an exact abstract match (Jaccard 1.00)**, so the 29.6% that fail are genuine absences from OpenAlex or extraction differences, not a loose threshold letting through near-misses. Compare the void keyless figure: **18.6% → 70.4%** once the quota was real.

  ⚠️ **T-212b's recall is BOUNDED at 0.704 by construction** — 86 of 291 cited papers have no OpenAlex identity, so they can never be retrieved regardless of how good retrieval is. **Quote the two numbers together or the recall figure is meaningless.** This is the limitation TASKLIST asks to be stated rather than buried.
- [x] **T-325** 🧠 ★★ **THE VERIFIER CROSS-CHECK — the reason this track exists.** Run the fine-tuned verifier (T-304) over the T-322 pairs. These are claims humans wrote and citations humans chose, so agreement is genuinely independent of your pipeline. *Done when: agreement rate is reported alongside the SciFact held-out numbers (T-305) and the 50-claim spot-check (T-705).* **Expect it to look worse than SciFact** — SciFact is expert-curated single-sentence evidence, this is real survey prose. Sarol et al. measured 0.59 micro-F1 on real citations against much higher curated-benchmark scores. **A drop here is the honest finding, not a failure** (`SESSION_CONTEXT.md §5.2`).

  ✅ **COMPLETE 2026-08-27.** `src/researchgpt/eval/scireviewgen_crosscheck.py`, run over the **1,665 T-322 pairs** with the shipped fp32 verifier.

  ### T-325 AGREEMENT RATE: **38.3%** (637 of 1,665)

  | scoring | SUPPORT | CONTRADICT | NEI | agreement |
  |---|---|---|---|---|
  | **span-level** (max over evidence sentences — matches T-502) | 637 | 44 | 984 | **38.3%** |
  | whole-abstract (naive, one truncated window) | 582 | 49 | 1,034 | 35.0% |

  **Span-level scoring is worth +3.3 points**, so the deployment-faithful framing is also the better-scoring one. T-502 should score claims against *spans*, not documents — this is now measured, not assumed.

  ⚠️ **The 0.7 support threshold (T-503) is currently a NO-OP.** Thresholded and argmax agreement are **identical to the pair** (637 both ways): every case where SUPPORT is the top class also clears 0.7. The verifier is confident when it says SUPPORT. *Consequence for T-503: the threshold is not doing the precision work it was introduced to do on this distribution. Tune it against real pipeline output (T-702/T-705), not against a number that cannot move.*

  🔴 **A hypothesis of mine was refuted by the data, and is recorded so it is not retried.** Reading a sample of disagreements, many were of the form *"Zhang et al. proposed a robot finger…"* or *"Shi and Malik proposed…"* — where the abstract supports the *content* but never names its authors, so a strict NLI model correctly refuses to entail the attribution. I predicted these were inflating the disagreement rate. **Measured across all 1,665 pairs, the opposite holds:** attribution claims are **more** common among agreements (20.6%) than disagreements (15.4%), and so are "headless" claims whose subject was the stripped citation (9.6% vs 5.6%). **Excluding both patterns *lowers* agreement to 35.3%.** *Eight examples suggested a mechanism that 1,665 refuted; the artefact explanation is dead and the 38.3% is genuine signal.*

  ★ **What it actually means, and this is the line for the report.** Disagreement is overwhelmingly **NEI (59.1%), not CONTRADICT (2.6%)**. The verifier is not calling human citations wrong — it is saying *the abstract does not contain enough to support the citing sentence*. That is a direct empirical measurement of **the abstract-only limitation T-505 already legislates for**, where Li et al. measured abstract-conditioned faithfulness at 0.745 against 0.94–0.96 with full context (`SESSION_CONTEXT §5.7`). **T-325 turns T-505 from a borrowed citation into our own finding**, on 1,665 human-authored pairs.

  **Report it beside the other two lenses (T-705b), never alone**, and do not compare it to SciFact's 0.769 as though they measured the same thing: SciFact is expert-curated, single-sentence, deliberately-entailing evidence; this is whole abstracts standing in for papers, cited by humans for background and contrast as well as support. Sarol et al.'s 0.59 micro-F1 on real citations is the right order-of-magnitude comparator, and even that differs in metric.
- [x] **T-326** 🧠 **Licence and citation compliance.** The original dataset is **CC BY-NC 4.0** (`PROJECT_PLAN.md §5.3`) — non-commercial only, which an academic project satisfies. **The mirrors' licence metadata is unreliable**: `pat-jj/SciReviewGen` declares MIT, which a mirror of S2ORC-derived data cannot grant; the other two declare nothing. **Cite Kasanishi et al., Findings of ACL 2023 (arXiv:2305.15186) and state CC BY-NC in the report regardless of what the mirror card says.** *Done when: the citation is in `refs.bib` and the licence line is in the report's data section.* ✅ **DONE 2026-08-27.** `refs.bib` **created** (it did not exist) with `kasanishi2023scireviewgen`, plus `wadden2020scifact` and `lo2020s2orc` since the licence chain runs through S2ORC. `DATA_PROVENANCE.md` **created** as the source the report's data section draws from — every dataset with its licence, what it was used for, and the limitation it carries into the results.

  The mirror-licence trap is written down rather than merely known: `pat-jj/SciReviewGen` declares **MIT**, which a mirror of S2ORC-derived data cannot grant; the other two declare nothing. **Cite Kasanishi et al. and state CC BY-NC 4.0 regardless of any mirror card.** A test asserts both files still say so.

---

## 5.2 Phase 3C — Reranker fine-tune ★ (second trained model, Days 4–5: Aug 29–30)

**Added 2026-08-25 by decision: a second fine-tuned model alongside the verifier.** Full specification in **`TRAINING_SPEC.md` §2** — read that before starting; the tasks below are the schedule, not the design.

**This was the original training proposal.** `PROJECT_PLAN.md §2.2` records the reranker fine-tune as **Cut**, and the stated reason (`SESSION_CONTEXT.md §4.1`) was S2ORC access latency — *"the single biggest schedule risk."* **Phase 3B removed that blocker.** The cut was about access, never about merit.

**Why the reranker and not the Writer or the Extractor:** zero new inference cost (it already runs on CPU at T-210 — this is a weight swap, not an architectural change); it is **off the M1 critical path**, so a failed training run breaks nothing; it answers Ammann et al.'s warning that gains *"rely on a strong, domain-aligned cross-encoder reranker"* when yours is a 22M web-search MiniLM (`SESSION_CONTEXT.md §5.6`); and retrieval recall is a hard ceiling on verification, so it lifts the graded metric indirectly. `TRAINING_SPEC.md §4` records why the Writer and Extractor were rejected.

- [x] **T-330** ⌨️ Build training triples from the SciReviewGen `train` split, reusing the T-321 parser. Query = `survey_title + chapter_heading`; positives = the `BIBnnn` abstracts. Sample 3,000 chapters, cap 8 positives each. *Done when: pair counts are reported and **the split is deduplicated by `survey_title`, not by row**.* ⚠️ **A row-level split puts chapters of the same survey on both sides and silently inflates the tuned score.** ✅ **DONE 2026-08-27** — `src/researchgpt/rerank/triples.py`.

  | | |
  |---|---|
  | chapters | 3,000 sampled from a 20,000-row pool |
  | **distinct surveys** | **1,381** (2.2 chapters per survey) |
  | unique cited abstracts | 13,929 |
  | **pairs** | **75,395** — 15,079 positive / 60,316 negative, exactly **1:4** |

  ⚠️ **Sequential reading would have wrecked survey diversity.** Chapters of one survey sit adjacent in the parquet, so the *first* N rows span almost no surveys — measured: **150 rows → 13 surveys**. Sampling across a 20,000-row pool instead gives **1,381 surveys from 3,000 chapters**. Survey diversity is precisely what the reranker has to generalise over, so this is not a cosmetic change.

  *Fewer pairs than `TRAINING_SPEC`'s ~120k estimate (75k) because the mean chapter cites ~5 papers, not the 8-per-chapter cap.* Ample for a 22M cross-encoder.
- [x] **T-331** ⌨️ ★ **BM25 hard-negative mining** — for each query take BM25 top-50 from the pooled split corpus, drop true positives, sample at 1 positive : 4 negatives. *Done when: a spot-check of 20 negatives confirms they are topically plausible, not random.* ⚠️ **Hard negatives are the whole point. Random negatives make the task trivial — the model learns topic matching, which BM25 already does, and stock-vs-tuned will show no gain. If T-334 shows ~0 improvement, suspect this task first.** ✅ **DONE 2026-08-27, and the diagnostic this warning asks for is now built in.**

  | | |
  |---|---|
  | BM25 depth mined | top-50 |
  | mean hard candidates per query | **47.6** |
  | queries short of hard negatives | **0** |
  | **random-fallback negatives** | **0 (0.0%)** |

  **Every negative in the training set is a genuine BM25 hard negative** — a document BM25 already ranks highly and is wrong about. Nothing was padded at random.

  ★ **`random_fallback_share_of_negatives` is recorded in `eval/rerank_triples_t330.json` specifically so T-334's null result, if it comes, is diagnosable rather than mysterious.** If that share is high, BM25 could not find confusable documents and the model was handed a task it could already do. On this build it is 0.0, so a null T-334 would *not* be explained here — look at the training config or accept the honest negative.

  Regression-tested: a true positive can never be sampled as a negative for its own query, and a corpus too small to supply negatives emits **fewer** rather than inventing them, flagging the shortfall.
- [x] **T-332** 🧠 Kaggle notebook: `cross-encoder/ms-marco-MiniLM-L-6-v2`, binary cross-entropy, max_len 512, lr 2e-5, batch 32, 2 epochs, fixed seed. *Expect 20–30 minutes on a T4.* **Train the verifier (T-303) first — it is the graded component and takes priority on the quota.** ✅ **NOTEBOOK DONE 2026-08-27** — `notebook-kaggle-traning/02_train_reranker_scireviewgen.ipynb` (17 cells) + README section. **The verifier ran first and passed T-307 at 0.769, so the quota is free.**

  **Smoke-tested, not just written.** All 8 code cells were executed locally on CPU against a 600-pair subset — data load, survey-grouped split, CrossEncoder build, stock baseline, `fit()`, the ranking comparison and save all ran clean.

  ⚠️ **One thing the smoke test nearly hid.** Stock and fine-tuned printed *identical* metrics to four decimals, which looks exactly like a no-op trainer. Verified directly that `CrossEncoder.fit()` does mutate the model — raw scores moved by up to **3.49** — so the identical metrics were coarse metrics over 2 dev queries, not broken training. *Worth knowing before someone reads a flat table on Kaggle and concludes the run failed.*

  🔴 **FAILED ON THE FIRST REAL KAGGLE RUN, and it is a failure the local CPU smoke test could not have caught.** `AttributeError: 'DataParallel' object has no attribute 'preprocess'` — Kaggle's **GPU T4 x2 exposes two devices**, so `sentence-transformers` wraps the model in `torch.nn.DataParallel`, and `BinaryCrossEntropyLoss` then calls `self.model.preprocess(...)`, which the wrapper does not forward. Training dies partway through `model.fit()`. *No single-GPU or CPU test can reproduce this; it needs two visible devices.*

  **Fixed** by setting `CUDA_VISIBLE_DEVICES=0` as the very first statement of section 1 — **before torch initialises CUDA** — plus an assert in section 2 that only one device is visible. A 22M cross-encoder gains nothing from a second GPU; DataParallel would mostly add transfer overhead. ⚠️ On recurrence the kernel must be **restarted**: the pin has no effect once CUDA is initialised.

  ⚠️ **This notebook needs a data upload**, unlike the verifier one: BM25 hard-negative mining needs the whole pooled corpus, so `data/rerank/train_triples.jsonl` (~99 MB) must be attached as a Kaggle Dataset. The notebook globs `/kaggle/input/**/train_triples.jsonl`, so the dataset name does not matter. Steps are in the README.
- [x] **T-333** ⌨️ ONNX export + int8 dynamic quantization, matching the verifier's deployment path. *Done when: the quantized model reproduces float logits within tolerance and per-query CPU latency is measured.* **HARNESS DONE 2026-08-27, awaiting the trained checkpoint** — `src/researchgpt/rerank/export_onnx.py`.

  ⚠️ **The stated criterion — "reproduces float logits within tolerance" — is the wrong test for a *reranker*.** Only the induced **ordering** matters: a model whose scores all shift by a constant ranks identically and is perfectly usable. So the export checks (a) ONNX fp32 vs PyTorch on raw scores, which is the genuine *export-correctness* test, and (b) **Kendall tau ≥ 0.9** for int8, which asks whether quantization *reshuffled the ranking* rather than whether it moved the numbers.

  ✅ **RUN 2026-08-27 on both checkpoints: PASS.** fp32 vs PyTorch max |Δscore| **5e-6**; int8 **Kendall τ 0.960** (10-epoch) / **0.968** (2-epoch, the shipped build) vs torch, so quantization preserves rank order. Size **91 MB → 23 MB**. *int8 is NOT the problem with this model — tuned-pytorch and tuned-int8 score within ~0.1 of each other throughout.*

  🔴 **`TRAINING_SPEC §2.5` warns "quantization must not be assumed free", and that warning already fired once** — T-304 measured int8 as free on the *stock* verifier (macro-F1 rose 0.516 → 0.539) and then as a 0.027 **loss** on the *fine-tuned* one, dropping it below its own T-307 gate. **A quantization result measured on one checkpoint says nothing about another.** Which graph ships is therefore decided by T-335 on ranking quality, not here.
- [x] **T-334** 🧠 ★ **Stock vs fine-tuned**, on **two** sets: the SciReviewGen `test` split (in-domain) and **your own 25-paper bibliography** (out-of-domain, CS). Report Recall@20, nDCG@10, Precision@12 and rerank latency. *Reuses T-212's harness.* **Lead with the out-of-domain number** — SciReviewGen is frozen mid-2020 and skews biomedical, so a large in-domain gain with no out-of-domain gain means you fitted the benchmark, not the task. **HARNESS DONE 2026-08-27, awaiting the trained checkpoint** — `src/researchgpt/rerank/evaluate.py`.

  **Stock baseline on the out-of-domain set is already measured** (own bibliography, 15 sub-questions, 501 candidates, 19 gold hits pooled):

  | arm | nDCG@10 | Recall@20 | Precision@12 |
  |---|---|---|---|
  | stock `ms-marco-MiniLM-L-6-v2` | **0.2277** | **0.4815** | **0.0926** |
  | fine-tuned | — | — | — |

  **Self-tested**: running the harness with stock in *both* arms returns delta **exactly 0.0000** on all three metrics, so a non-zero delta later is a real difference and not harness noise.

  ✅ **Costs no OpenAlex budget** — it reuses T-212's cached pool (`eval/cache/pool_mps25.json`). That matters now that OpenAlex is metered (§0.2).

  **MEASURED 2026-08-27** against both Kaggle checkpoints, int8 (i.e. what ships). The **2-epoch** build was adopted; the 10-epoch numbers below are near-identical:

  | | stock | fine-tuned | delta |
  |---|---|---|---|
  | **out-of-domain nDCG@10** | 0.2277 | 0.2583 | **+0.0306** |
  | **out-of-domain Recall@20** | 0.4815 | 0.6481 | **+0.1667** |
  | out-of-domain Precision@12 | 0.0926 | 0.0926 | +0.0000 |
  | in-domain nDCG@10 | 0.2646 | 0.7500 | **+0.4854** |

  ⚠️ **The in-domain gain is 16x the out-of-domain gain.** Exactly the pattern this task warns about.

  ⚠️ **And the out-of-domain average hides how thin it is.** Only **9 of 15** sub-questions have any gold paper pooled, and per-query the result is **3 improved, 5 unchanged, 1 regressed** — with the regression losing its only gold paper outright (`scientific information extraction`, Recall@20 1.000 → 0.000). Two of the three "wins" are a single gold paper flipping 0 → 1. *Four queries of evidence.*

  ⚠️ **Harness limitation to state if these latencies are quoted:** the stock arm runs through sentence-transformers/PyTorch and the tuned arm through onnxruntime, so the ms/query column compares **runtimes**, not models. It is not an apples-to-apples latency measurement.
- [x] **T-335** 🧠 **Adoption gate.** Promote the tuned model into `configs/default.yaml` **only if it beats stock on your own bibliography, measured after int8 quantization.** An in-domain-only win is a reportable finding, not a reason to ship. *If it does not pass, keep the stock reranker and report the negative result — that is an honest contribution, and the pipeline is unaffected.* **IMPLEMENTED 2026-08-27** as a mechanical gate in `rerank/evaluate.py`, decided on out-of-domain nDCG@10 and Recall@20.

  🔴 **REVERTED 2026-08-27 by the first real pipeline run (M1). `configs/default.yaml` names the STOCK reranker.**

  The adoption below rested on condition 2 — *the live pool is 98.2% on-topic, so there is little for a miscalibrated model to mis-promote*. **That measurement did not generalise.** It came from T-212's *cached* pool, built from 15 hand-written, tightly-scoped queries. The Planner (T-402) emits 20+ broader queries and produces a far more heterogeneous pool.

  M1's ranked top-10 contained **edge-server RL, IoT monitoring and US biodiversity specimens**. A/B on the same live pool, query `multi agent retrieval literature review`:

  | rank | stock | tuned |
  |---|---|---|
  | 1 | LiRA (multi-agent literature review) **+7.77** | **IoT behavioural monitoring +4.77** |
  | 2 | LatteReview (systematic review) +5.43 | LiRA, demoted to **+2.10** |
  | 3 | MARS (multi-agent retrieval) +5.36 | LatteReview +0.35 |

  **The tuned model ranks an IoT paper above the single most relevant paper in the pool.** The relevance control flagged exactly this and was right; my condition-2 evidence was drawn from an unrepresentative pool. *Two reversals on this decision is not a good look, but the final state rests on production output rather than a proxy, and the lesson is specific: a "the pool is clean" argument must be measured on the pool the PLANNER builds, not on a hand-curated one.*

  **Fix before re-adopting:** retrain with **mixed negatives** (~3 hard : 1 random). Training on 100% BM25 hard negatives is what removed the model's ability to recognise irrelevance (T-331). ✅ **Implemented 2026-08-28 as T-332R** — `notebook-kaggle-traning/03_train_reranker_mixed_negatives.ipynb`. **Awaiting the Kaggle run.**

  <details><summary>Superseded adoption reasoning, kept for the report</summary>

  ✅ **RUN 2026-08-27. VERDICT: PROMOTE WITH CONDITIONS. The tuned reranker is adopted** — `configs/default.yaml` now names `data/models/reranker-onnx` (the **2-epoch**, int8 ONNX build).

  | | stock | **adopted (2-epoch, int8)** | delta |
  |---|---|---|---|
  | **out-of-domain Recall@20** | 0.4815 | **0.6481** | **+0.1667** (+35% rel.) |
  | out-of-domain nDCG@10 | 0.2277 | 0.2577 | +0.0300 |
  | in-domain nDCG@10 | 0.4524 | 0.7828 | +0.3304 |
  | relevance control | **0/15** | **11/15 FAIL** | — |

  **Why the 2-epoch build and not the 10-epoch one:** identical in-domain performance (0.7828 vs 0.7840 — it had converged by epoch 2, so 49 further GPU-minutes moved it −0.001), identical out-of-domain gain, but materially better calibrated (11/15 control violations vs 15/15; off-topic scores +2.9…+5.0 vs +6.8…+9.7). It also matches the 2 epochs `TRAINING_SPEC §2.3` specifies.

  🔴 **The model's ABSOLUTE scores are broken, and it was adopted anyway — deliberately, on measured evidence.** It rates unrelated documents (wind-turbine fatigue, soil nitrogen, opera libretti) at **+3…+5** where stock gives **≈ −11**. Root cause is T-331: *every* negative is a BM25 hard negative from SciReviewGen's own cited-abstract pool, so the model was only ever asked *"which of these topically-adjacent scientific abstracts belongs to this chapter?"*, never *"is this relevant at all?"*. **T-331's warning that "random negatives make the task trivial" is right about necessity but wrong at 100%** — the fix is a mixture (~3 hard : 1 random), not a switch. Not spent; M1 took priority.

  ★ **Two conditions were measured before promoting, and both must keep holding:**
  1. **Nothing consumes the score as a value.** `hybrid_retriever` fuses by **RRF over ranks**; the only other consumer is the eval harness. Enforced in code: `Reranker.filter_by_score()` raises `UncalibratedScoreError` on a fine-tuned model, so a future author reaching for a score cutoff hits a loud explanation instead of a silent bug. **This matters for Phase 5** — if T-506's Critic ever thresholds on retrieval score, it must use the stock model or a recalibrated one.
  2. **The live pool is 98.2% on-topic** (9 of 493 papers clearly off-domain), because T-201 already searches `title_and_abstract` with a date window. On real candidates the tuned model promoted **0** off-topic papers into a top-12, against stock's **1**.

  ⚠️ **RE-RUN THIS GATE if either condition could change** — notably if `max_per_source` rises to 100 (`decisions.txt` D-05), which admits more marginal papers, or if a new source widens the pool.

  ⚠️ **An earlier verdict here read "DO NOT PROMOTE — catastrophically broken". That was an overcorrection and is retracted.** The relevance control was first wired as a hard veto; it measures a real property, but whether that property *matters* depends on the two facts above, which had not been measured when the veto was written. The gate now reports **PROMOTE WITH CONDITIONS** and prints them. *Ranking gains remain a hard requirement — the control cannot rescue a model that does not rank better.*

  </details>

  **Honest reporting line for T-705b / the deck:** *"the fine-tuned reranker raised Recall@20 by 35% on a curated bibliography and improved every in-domain ranking metric, yet we rejected it: a relevance control showed it had stopped recognising irrelevance, and on the first real pipeline run it ranked an IoT-monitoring paper above the most relevant paper in the pool. We traced the cause to training exclusively on BM25 hard negatives."*

  ⚠️ **The gate refuses to be quietly satisfied on the wrong artefact.** Run without `--tuned-onnx` it still reports, but prints that it judged the **unquantized** model and that `TRAINING_SPEC §2.5` requires the decision be made after int8. *That is the exact mistake T-304 made on the verifier — passing a gate on the model that trained rather than the model that ships.*
- [x] **T-332R** ⌨️ ★ **Reranker retrain with MIXED negatives** — ✅ **RUN 2026-08-28 at 3 hard : 2 random. ADOPTED.** — the remediation T-335 specified when it reverted the tuned model. **NOTEBOOK DONE 2026-08-28** — `notebook-kaggle-traning/03_train_reranker_mixed_negatives.ipynb` (23 cells) + README section 03. *Done when: the Kaggle run completes and section 10 prints its verdict.*

  **Changes exactly one variable.** Base model, seed, epochs, lr, batch size, max length, warmup, weight decay, dev fraction **and the survey split** are all held identical to T-332, so the two runs are directly comparable. `tests/test_phase3c_acceptance.py::test_mixed_notebook_changes_only_the_negatives` fails if any of them drift.

  | | T-332 (notebook 02) | **T-332R (notebook 03)** |
  |---|---|---|
  | pairs | 75,395 | **75,395** |
  | positive : negative | 1 : 4 | **1 : 4** |
  | negative composition | **4 hard** | **3 hard + 1 random** |
  | training pairs | 68,380 | **68,380** |

  ✅ **Needs no new upload.** All 13,929 cited abstracts already appear in the uploaded `train_triples.jsonl` — every document is a positive for some chapter, because the corpus *is* the set of cited abstracts. The notebook recovers the pool and does the mixing itself. *Verified locally on the real file: 75.0% hard / 25.0% random, ratio 1:4.0 exactly.*

  ★ **The relevance control now runs INSIDE the notebook, before the download.** The diagnostic that caught the previous model only caught it after that model had been quantized, evaluated and adopted. It uses the same four probe texts as `rerank/evaluate.py` (a test enforces they stay identical), so the notebook's violation rate and the local T-335 gate's violation rate mean the same thing.

  **Section 10 is a pre-filter, not the decision** — both thresholds fixed in section 1 *before* the run, per `decisions.txt` D-09's discipline: `nDCG@10` gain ≥ 0.001 **and** control violation rate ≤ 20% (the previous model was at ~73%). **T-335 still decides**, locally, out-of-domain, after int8.

  **Smoke-tested, not just written.** All 11 code cells executed locally on CPU against the real 75,395-pair file with a 200-example stand-in for training. The stock relevance control printed an off-topic score of **−10.74**, matching the local harness's ≈ −11 — confirming the notebook reads un-activated logits exactly as the gate does.

  ⚠️ **Still off the critical path.** The pipeline ships with the stock reranker either way; this remains a weight swap. If the run fails both gate conditions, the Aug 30 kill switch applies — keep stock, report the negative result, move on.

  🔴 **THE NOTEBOOK'S OWN GATE SAID STOP, AND IT WAS WRONG.** Section 10 reported a **44% control violation rate** and printed `STOP - relevance prior still broken`. The local T-335 gate, run on the same checkpoint, reports **0/15 violations** and **PROMOTE**. Both numbers are correct; they measure different pools.

  **Why they disagree, because this will come up again.** The notebook's control runs on the **SciReviewGen dev pool**, where every candidate is either a true positive or a *BM25 hard negative* — so the "median candidate" it must beat is itself a topically adjacent document. On a real 493-paper retrieval pool that is ~98% on-topic, the median is an ordinary paper and the bar is the one that matters. **T-335 on the project's own bibliography is the authority** (`TRAINING_SPEC §2.4`); the notebook gate is a pre-filter and it was tuned too strict. *Do not re-revert on the notebook number.*

  **T-334/T-335 measured on the int8 ONNX build — what actually ships:**

  | arm | nDCG@10 | Recall@20 | Precision@12 | relevance control |
  |---|---|---|---|---|
  | stock | 0.2277 | 0.4815 | 0.0926 | **0/15 PASS** |
  | **tuned (3:2 mixed)** | **0.2425** | **0.5926** | **0.1019** | **0/15 PASS** |
  | delta | +0.0149 | **+0.1111** | +0.0093 | — |

  In-domain nDCG@10 **0.2646 → 0.6545**. T-333 export clean: fp32 max |Δ| 5e-6, int8 Kendall τ **0.9637**, 90.96 MB → 23.16 MB.

  ★ **The M1 failure case is fixed, and there is now a regression test for it** (`test_adopted_reranker_ranks_the_m1_failure_case_correctly`). On the query that caused the revert, *"multi agent retrieval literature review"*: the new model puts **2 gold papers in the top 10 (best rank 9)** where stock puts **0 (best rank 39)**, and ranks LiRA first with the wind-turbine control at −5.44. On *"automated literature review generation"* and *"scientific claim verification"* its top-5 is topically correct on every row — where the OLD tuned model returned marketing decision-making and computational mechanics. Full A/B: `eval/reranker_ab_probe_t335.json`.

  ⚠️ **The ratio that shipped is 3 hard : 2 random (60/40), not the 3:1 the notebook defaults to.** The metrics JSON reports `random_per_positive: 3` from the config cell while the data was built at 2 — cells were re-run out of order across several attempts. **The artefact is what counts and it is consistent**: 75,395 negatives = 45,237 hard + 30,158 random, `hard_share_of_negatives` 0.60. Rebuild at exactly 3:2 if this is ever re-run.

  ⚠️ **Condition 1 still binds and now matters more.** This model's scores are **compressed** (+1…+3.7 where stock gives +9). Ordering is correct; absolute values are not comparable to stock and must never be thresholded. `Reranker.filter_by_score()` raises `UncalibratedScoreError` on any non-stock model, which covers this one automatically. **Phase 5: if T-506's Critic wants a retrieval-score cutoff, it must use the stock model or a recalibrated one.**
- [ ] **T-336** 🧠 **UNBLOCKED 2026-08-28 (re-confirmed)** — T-332R's model was adopted, so this ablation now has two real arms to compare. *The 2026-08-27 unblock was withdrawn when T-335 reverted; it is live again.* **Ablation 5 — stock vs fine-tuned reranker**, full system otherwise unchanged, `max_papers=25`. Closes `SESSION_CONTEXT.md §5.6`'s instruction to *"measure reranking's contribution separately."* **Lower priority than ablation 2; must never displace it.**

---

## 6. Phase 4 — Agents and the first survey (Days 4–6: Aug 29–31) 🔴 M1

- [x] **T-401** 🧠 `agents/base.py` — the agent ABC, the partial-state-return contract (`SPEC §14.3`), and the trace hook. ✅ **DONE 2026-08-27** — `agents/base.py`. Centralises the partial-state contract, the trace hook and `fail_soft`. **The contract is enforced, not documented**: an agent returning the state it was handed re-adds every paper (the `add` reducers) and doubles the corpus on iteration 2 of the Critic loop, so `__call__` refuses it; unknown state keys are refused too, because LangGraph keeps them and nothing reads them. *Design change made while testing: agents re-raise their own exception type rather than being wrapped — a uniform `AgentError` destroyed the type-based handling `OpenAlexBudgetExhausted` and `PlanValidationError` need, and the trace already records which agent failed.*
- [x] **T-402** ⌨️ `agents/planner.py` — research question → 4–8 sub-questions + search plan, on the free-tier LLM. (`SPEC §7.1`) *Done when: a real question yields a validated plan object.* ✅ **DONE 2026-08-27** — `agents/planner.py` + a worked example in `planner_v1.md`. **This is the agent T-212 diagnosed as the binding constraint.** The measured query rules are now *enforced in validation*, not merely requested: 3–5 terms (OpenAlex ANDs them, so 6+ returns nothing), ≥3 of 4 facets, every sub-question carrying a query. Live run: **18 queries, mean 3.6 terms, all four facets**, naming specific systems (`SciFact hallucination benchmark`, `PubMedQA grounding evaluation`, `CORD-19 citation consistency`) against the 15 generic stand-ins that scored 0.371. **Repair, not retry** — a repair pass sends the model its own broken output plus the parse error. NOT fail-soft: a run with no plan writes a survey about nothing.

  🔴 **SUPERSEDED IN PART BY T-409's MEASUREMENT (2026-08-28).** The claim above that naming specific systems beats “the 15 generic stand-ins that scored 0.371” is **contradicted by the first end-to-end measurement**: the Planner's queries scored union recall **0.000**. Specificity is the defect, not the fix — invented proper nouns (`FAIRScore`, `BLEU factuality assessment`) ANDed by OpenAlex return nothing on-topic. Validation enforces query shape but not groundedness. See T-409.
- [x] **T-403** ⌨️ `agents/retriever.py` — the node wrapper around Phase 2. No LLM call. (`SPEC §7.2`) ✅ **DONE 2026-08-27** — `agents/retriever.py`. Owns the dedup the reducers deliberately do not do: normalised DOI, then a ≥25-char title key to bridge an arXiv preprint to its published version (different DOIs, same title). Richer record wins a collision, so an abstract-less duplicate cannot silently downgrade a paper under T-505. **Also drops `abstracts` that are really author lists** — measured **1.9%** of the T-212 pool (e.g. Wadden's SciFact record), each costing a wasted extraction call and an empty insight row. Detected on name-list *shape*, not length, because short real abstracts exist and dropping one is worse than the waste.
- [x] **T-404** ⌨️ ★ `agents/extractor.py` — per paper: `methodology / advantages / disadvantages / critique`, plus `datasets`, `metrics`, `evidence_spans`. **Strict Pydantic + retry-with-repair, max 2, then `None` + `extraction_note`. Never abort a run on a parse failure.** **Strip markdown fences before parsing** — §0.1 measured that Gemma returns fenced JSON despite `responseSchema`, so fenced output is the normal case, not the error case. (`SPEC §7.3`, `§14.2`) *Done when: 10 papers all produce a valid `Insight`, including at least one that needed a repair.* ✅ **DONE 2026-08-27** — `agents/extractor.py`. Measured **5.08/8 fields** on the M1 run, above T-004's 4.6. `fail_soft`: with ~60 papers one unparseable response would otherwise destroy a 30-minute pipeline at paper 47. **Strips echoed schema placeholders** — T-004 measured one model emitting the literal `string` into `datasets`/`metrics` on 2 of 5 papers, output that parses, validates and injects fabricated content into a hallucination-graded pipeline. **Takes the RANKED prefix** and traces a warning when the ranking is absent: insertion order is *whichever query ran first*, the defect that made the T-212 harness read 0.029 instead of 0.057. *The ~20 few-shot expansion is still open — 5.08/8 is measured, not final.*
- [x] **T-405** 🧠 `graph/build.py` — wire **linearly** first: PLANNER → RETRIEVER → INGEST → RANK → EXTRACTOR → WRITER. No critic loop yet. *Done when: the graph runs start to finish on a real question.* ✅ **DONE 2026-08-27** — `graph/build.py` plus `agents/ranker.py` for the INGEST/RANK stage. Sequential runner for M1 **and** a compiled LangGraph for the Phase 5 loop to attach to; they share node functions so they cannot drift, and the sequential `_merge` applies the **same reducer rules** rather than merging naively — a naive merge would hide the accumulate/replace distinction until the Critic loop turned it into a duplication bug.
- [x] **T-406** ⌨️ `agents/writer.py` — thematic synthesis with IEEE `[n]` citations. **Evidence-first: the Writer may cite only what it was given.** ALCE measured post-hoc citation attachment costing 47% of citation recall (`SESSION_CONTEXT.md §5.10`). (`SPEC §7.6`) ✅ **DONE 2026-08-27** — `agents/writer.py`. Evidence-first: ALCE measured post-hoc citation attachment costing **47% of citation recall**, so the model writes `[n]` with the sentence and never sees a paper it may not cite. Every marker is resolved against the evidence block and unresolvable ones dropped and counted. **M1 result: 9 references, 0 unresolvable citations.** Abstract-only papers are flagged in the evidence block per T-505. See T-408 for the uncited-section defect this run exposed.
- [x] **T-407** ⌨️ `output/markdown_writer.py`, `output/bibtex_writer.py`, `output/insight_table.py` (CSV). *Done when: `outputs/runs/<run_id>/` contains `review.md`, `refs.bib`, `insights.csv`, `trace.jsonl`, `config.yaml`.* ✅ **DONE 2026-08-27** — `output/writers.py`. `review.md`, `refs.bib`, `insights.csv`, `config.json`. **No writer raises into the pipeline**: a 30-minute run that completes and then dies formatting a CSV has lost everything for no reason. `@misc` rather than `@article` when there is no venue — claiming a journal we do not know is a small fabrication in a project about citation accuracy.
- [x] **T-408** 🔴 **MILESTONE M1 — a complete cited literature survey from the CLI.** *The insurance policy. If everything after this collapses, there is still something to submit.* **Hard date: 2026-08-31.** ✅ **LANDED 2026-08-27, four days early.** `outputs/runs/m1_first/`

  | | |
  |---|---|
  | papers retrieved | **179** (603 chunks, 152 with abstracts) |
  | corpus extracted | 12 (`max_papers=12`) |
  | **extraction coverage** | **5.08 / 8 fields** — above T-004's 4.6 baseline |
  | extraction failures | **0**; 1 repair pass across 12 papers; 0 placeholder echoes |
  | sections | 3 (Methods, Evaluation, Limitations) |
  | review | 16,183 chars, **9 references**, **0 unresolvable citations** |
  | LLM requests | **16** for the whole run |
  | artefacts | `review.md`, `refs.bib`, `insights.csv`, `config.json`, `trace.jsonl` |

  **The four-field schema populated**: 12/12 papers carry a `critique`, 10/12 a `methodology`, 6/12 `datasets`. That table is the concrete answer to SurveyGen's *"limited critical analysis"*.

  🔴 **Two real defects surfaced, both now fixed and regression-tested. Neither would have been found without a live run.**

  1. **A 6,751-character section with ZERO citations.** "Methods and Architectures" came back as a numbered book chapter (*"3.1 Methodological Trends", "3.1.1 CTDE versus…"*) and dropped the citation instruction entirely. **Nothing caught it, because zero markers means zero *dropped* markers — every integrity counter read clean.** Uncited prose is the exact failure this system exists to prevent. The Writer now retries once with an explicit correction and then **rejects** the section: the Verifier drops unsupported claims, so the Writer must not emit unsupported sections. A pipeline-level guard also refuses to exit 0 with an empty `review.md`.
  2. **The circuit breaker disabled the wrong source.** Its first version tripped on three consecutive empty responses and killed **arXiv** — which is unmetered and answers instantly. It now trips on **wall-clock wasted**, which is the property that actually hurt (Semantic Scholar keyless burns up to 60s per miss; the first M1 attempt was killed at 10 min having done 38 of 72 source-queries).

  ⚠️ **Timing, for the T-610 demo decision:** retrieval dominates. 26 source-queries took most of the run; extraction was 12 LLM calls. A 60-paper run will be well past the ~30-minute §0.2 tolerance, which is exactly why T-610 pre-bakes the showcase run.

- [x] **T-409** 🧠 Run the **flagship query** — the system surveys *its own topic*, agentic RAG for automated literature review. The 25-paper bibliography is the answer key. Keep the output: after a human edit pass it becomes the report's literature-survey chapter (T-807).

  **RE-RUN 2026-08-28 after the Planner prompt fix, `max_papers=10`, six-agent loop.** Union recall **0.057 (2/35)**, up from **0.000** but still well under the **0.371** stand-in baseline. The prompt fix removed the invented proper nouns completely — 0 acronym/CamelCase names across 12 queries, against 5 in the previous run — and the topic drift into clinical guidelines and policy analysis is gone. So the *mechanism* identified was real and is fixed; the *recall* is not. **Tuning deliberately deferred** on the human's instruction: the objective of this run was an end-to-end output, not a good number. Extraction: field coverage 4.40/8, 0 placeholder echoes, 1 blank of 10.

  ✅ **RAN 2026-08-28, 5.8 min, 0 retries, 0 errors, 30 requests.** Artefacts in `outputs/runs/flagship/`. ⚠️ **Produced on a PAID provider (Baseten) after Groq's free tier hit its 200,000-token DAILY cap on both gpt-oss models** — same open-weight `gpt-oss-120b` the T-004 bake-off selected, so output is comparable rather than better. Provider is stamped in `config.json` and in every cache entry; this run may not be reported as a $0 artefact.

  **Extraction quality PASSES the T-004 criteria** (applied post hoc, since 120b-on-Baseten was never probed): field coverage **5.32/8** against the 4.6 baseline, **0** placeholder echoes, **0** blank extractions, 25/25 abstract-only (so T-505's cap applies to every claim). `review.md` is 22,025 chars, 5 sections, 50 citation markers, 11 references.

  🔴 **BUT THE RECALL GATE FAILED OUTRIGHT: union recall 0.000 (0 of 35), against a 0.371 baseline. The Planner made retrieval WORSE, not better — the opposite of T-213's diagnosis.** Verified as a real result, not a measurement bug: 318 retrieved papers share **zero** DOIs and **zero** normalised titles with the 35-paper answer key, while T-212's cached pool from 15 hand-written queries overlaps on 13.

  **Cause — the Planner invents specific proper nouns, and OpenAlex ANDs query terms.** It emitted `FAIRScore systematic review`, `MARS multi-agent retrieval` and `BLEU factuality assessment` (BLEU is a translation metric, misapplied), plus drift into `clinical guideline generation RAG` and `policy analysis literature synthesis` — not this project's topic. One non-existent or niche term ANDed into a query returns nothing on-topic. The gold papers (*“Can large language models replace humans in systematic reviews?”*, *“A survey on LLM-based multi-agent systems”*) are reached by **broad canonical phrases**, which is exactly what the 15 stand-ins were.

  🔴 **This contradicts T-402's own note, which treated “naming specific systems” as the improvement over “the 15 generic stand-ins that scored 0.371”. Measured, the specificity is the defect.** T-402's validation enforces query *shape* (3–5 terms, ≥3 of 4 facets) but nothing enforces *groundedness*, so plausible-sounding invented names pass validation and retrieve nothing.

  ⚠️ **Confound to state before quoting the delta:** this run planned with `gpt-oss-120b`, the earlier ones with `20b`, so 0.371 → 0.000 is not a clean single-variable comparison. The *mechanism* — invented terms + AND semantics — is independent of which model invented them.

  **Consequence: this run must NOT become the T-807 report chapter or the T-610 demo as it stands.** The prose is good and the citations resolve, but the corpus is off-target (multimodal RAG, knowledge graphs, KG-MARS) rather than about this project's question. **Fix the Planner before re-running**: constrain queries to broad topical phrases and forbid invented proper nouns, then re-measure against the same answer key.

---

## 7. Phase 5 — Verification and the critic loop ★ (Days 7–8: Sep 1–2)

The centrepiece. Objective 2 lives here.

- [x] **T-501** ⌨️ ★ `agents/verifier.py` part 1 — atomic claim decomposition from the drafted text. *Done when: a 20-sentence draft yields a list of atomic claims, each with a source-sentence pointer.*  ✅ **DONE 2026-08-28** — `agents/verifier.py`. Sentence-level, **rule-based, no LLM call**: FActScore decomposes with a model, we do not, because the token budget is the binding constraint (T-409 exhausted a 200,000-token daily quota four times in one afternoon), a deterministic splitter is auditable, and a generative step here can *invent* a claim the draft never made. Only sentences carrying a `[n]` marker become claims; markers resolve through the Writer's global `reference_order`. The cost is recorded honestly in `DECOMPOSITION_NOTE` for T-806.
- [x] **T-502** ⌨️ ★ ONNX runtime wrapper: `(claim, evidence_span) → softmax`. *Done when: it runs on CPU at the T-306 measured rate.*  ✅ **DONE 2026-08-28** — `VerifierModel`. **44.7 claims/sec measured on the int8 build against T-306's 25.4** (that figure was fp32). Batch size defaults to **1** because T-306 measured batching as *slower* on this CPU (25.4/s at batch 1 vs 7.7/s at 32). 🔴 **Config defect fixed**: `verifier.onnx_path` named `data/models/verifier-int8.onnx`, a file that never existed — T-304 exports a directory. Nothing loaded it until Phase 5, so it sat wrong for three days.
- [x] **T-503** 🧠 ★ Verdict mapping and thresholds per `PROJECT_PLAN.md §4.2`: `SUPPORT` high-confidence → `SUPPORTED`; `SUPPORT` low-confidence → `PARTIAL`; `NOT_ENOUGH_INFO` → `UNSUPPORTED`; `CONTRADICT` → `CONTRADICTED`. `support_score` = softmax probability, threshold 0.7. **Weight the `SUPPORTED` threshold toward precision** — CliVER measured a 21% false-Support rate, and over-predicting "supported" is the dangerous direction for a hallucination-graded project (`SESSION_CONTEXT.md §5.10`).  ✅ **DONE 2026-08-28** — `verdict_for()`. `support_score` is the SUPPORT probability in **every** branch, so one number means one thing across the whole report. ⚠️ **Our own measured SUPPORT precision is 0.800** (T-305 confusion matrix: 45 false SUPPORTs in 225 predicted), independently reproducing CliVER's 21% false-Support rate — the exact reason the threshold is biased to precision.
- [x] **T-504** ⌨️ ★ Unsupported-claim **dropping**, drop-logging to `trace.jsonl`, and `contradiction_pairs`. *Done when: a run reports "N claims dropped" and every drop is inspectable in the trace.*  ✅ **DONE 2026-08-28** — drops, `claim_dropped` trace events carrying verdict / score / section / evidence chunk, and `contradiction_pairs`. Evidence is drawn **only from the papers a sentence actually cited**; scoring against the whole corpus would let an unrelated paper rescue a miscited sentence, which is the ALCE error mode. A claim citing a paper we hold no text for is dropped, not passed.
- [x] **T-505** 🧠 **Apply the abstract-only rule.** Papers with `text_availability == abstract_only` **may be cited as existing but may not supply verified claims.** Li et al. measured abstract-conditioned faithfulness at 0.745 against 0.94–0.96 for full context — abstract-conditioned models "learn to hallucinate" (`SESSION_CONTEXT.md §5.7`).  ✅ **DONE 2026-08-28 — implemented as a CAP, not a ban, and that is a judgement call worth reviewing.** Read as a ban it empties the corpus: the M1 run was **100% abstract-only**. Read as a cap it matches the evidence — Li et al. measured abstract-conditioned faithfulness at **0.745 against 0.94–0.96**, a degradation rather than a disqualification. A claim whose only support is abstract-only is capped at `PARTIAL` and can never reach `SUPPORTED`; the cap is counted per run so the report can state how many claims it bit.
- [x] **T-506** ⌨️ `agents/critic.py` — coverage / grounding / paper-count gates → `RETRIEVE | REPLAN | WRITE`. (`SPEC §7.5`)  ✅ **DONE 2026-08-28** — `agents/critic.py`, **deterministic, no LLM call**. Every `SPEC §7.5` gate is arithmetic; a loop that spends tokens deciding whether to spend tokens is the worst possible place for a generative call, and an LLM router turns an oscillating loop into an unreproducible bug. Escalates RETRIEVE → REPLAN only *after* a RETRIEVE failed to close the gap. ⚠️ Coverage is attributed via `retrieval_log.sq_id`, which **under-counts** — a deliberately conservative bias that can only trigger an extra RETRIEVE, never wave a thin review through.
- [x] **T-507** 🧠 `graph/routing.py` — conditional edges, **hard `max_iterations=3`, forced WRITE on the final iteration, mandatory plan-diff on replan.** *Done when: the loop demonstrably fires on an under-covered query **and terminates**.*  ✅ **DONE 2026-08-28** — `graph/routing.py` + `build_loop_graph()`. The cap is enforced **twice, independently**: the Critic's is policy, routing's is the safety bound that keeps the graph terminating if a gate above it is wrong. `assert_plan_changed()` refuses a REPLAN returning an identical plan, compared on content since the Planner rebuilds the objects every pass. 🔴 **A real bug was caught here by an unused-import lint rather than by a test: nothing was incrementing `iteration`**, so both caps compared against a permanently-zero counter and could never fire. The Critic now owns the counter and advances it on loop-backs only — it is visited twice per iteration, so counting both visits would halve the budget.
- [x] **T-508** ⌨️ `graph/checkpoint.py` — SQLite checkpointer so a run can resume.  ✅ **DONE 2026-08-28** — `graph/checkpoint.py`, wired into `build_loop_graph(checkpointer=...)`. One SQLite file keyed by `thread_id` = `run_id`, so the checkpoint and `outputs/runs/<run_id>/` name the same run.

  **Proven, not asserted**: a graph is crashed mid-run in the tests, resumed, and the completed node is asserted **not** to have re-run. A second invocation returning a result would look identical whether or not the checkpoint did anything.

  ⚠️ **Know what this recovers, because the honest answer is “not the thing that broke on 2026-08-28”.** LangGraph checkpoints **between** nodes. The Extractor is one node, so a run that dies at paper 18 of 25 resumes at the *start* of extraction. What makes resume genuinely cheap is the **pairing**: the checkpoint skips Planner/Retriever/Ranker (~6–7 min of CPU, network, and OpenAlex budget), and the T-104 prompt cache skips already-completed extractions at **zero tokens**. Neither is sufficient alone, and the report should say so rather than claim node-level checkpointing solves a mid-node failure.

  ⚠️ **The cache half is only free while the request is identical.** The cache key includes model, temperature, `max_tokens` and `reasoning_effort` — all four of which moved during the 2026-08-28 debugging — so a “resumed” run re-pays for every extraction across a config change. Correct behaviour, but do not expect resume to be free after tuning.

  `resume_report()` reports **quantities, not a boolean**: “resumable” does not tell you whether resuming is worth it or whether this is the checkpoint you meant. Keyed on a field being *present* rather than truthy — a node that ran and legitimately wrote an empty list has still run, and truthiness reported `resumable: True` with an empty `skips`.

  ⭐ **Worth more now than when it was written.** A T-409 run costs ~25 minutes and a large slice of a 200,000-token daily budget; four attempts on 2026-08-28 exhausted that budget on **both** gpt-oss models. Resuming a run that died at paper 18 is the difference between a lost afternoon and a five-minute top-up.
- [x] **T-509** 🔴 **MILESTONE M2 — the full six-agent graph runs with the loop firing and terminating.**

  ✅ **M2 DEMONSTRATED 2026-08-28.** `outputs/runs/loop_demo/`, exit 0, 6.3 min. The loop **fired, escalated and terminated** on real state:

  ```
  iter=0  CRITIC -> RETRIEVE   271 papers, below min_papers=5000
  iter=1  CRITIC -> REPLAN     a previous RETRIEVE left the corpus at 271 (was 271);
                               searching harder is not working, so the plan is the problem
  iter=2  CRITIC -> WRITE      iteration 2 is the last of 3; forcing WRITE per SPEC 7.5
  ```

  **How it was forced, stated plainly:** `min_papers` was raised to an unreachable 5,000. Retrieval, state and the gate are all real; only the threshold was set to a standard this corpus cannot meet — which is exactly what a genuinely thin topic would produce.

  ✅ **ALL EDGES TRAVERSED — re-run at `max_iterations=4`, `outputs/runs/loop_demo4/`, exit 0, 11.7 min:**

  ```
  iter=0  papers=271  RETRIEVE
  iter=1  papers=271  REPLAN   a previous RETRIEVE left the corpus at 271 (was 271)
          >>> PLANNER REPLANNING (12 tried queries, 184 chars of critique)
  iter=2  papers=551  RETRIEVE
  iter=3  papers=551  WRITE    last of 4; forcing WRITE per SPEC 7.5
  ```

  ★ **The replan did real work: the corpus went 271 → 551 papers**, and the Critic then chose RETRIEVE rather than REPLAN *because it had grown*. The escalation guard behaves correctly in both directions on live data — escalate when stuck, keep retrieving while it is still helping.

  ★ **The plan genuinely changed: 12 new queries, ZERO repeated** from the rejected plan, so `SPEC §7.5`'s “mandatory plan diff on replan” is satisfied on real data. The T-409 prompt fix survives replanning — all 12 are ordinary technical vocabulary, no invented proper nouns.

  ⚠️ *Why `max_iterations=3` was not enough:* the Critic advances the counter on every loop-back, so RETRIEVE + REPLAN consumed the whole budget and routing forced WRITE before the Planner could re-run. The safety bound was correct; the budget was simply too small to show the edge.

  🔴 **A defect found while setting this up, without which the demo would have been hollow: the Planner never read `critic_feedback`.** Its prompt was built from `research_question` + `constraints` alone, neither of which changes between iterations — so a REPLAN produced an identical prompt, hit the T-104 cache, and returned **the same plan**. The loop would have re-run identical queries and stood still, which is exactly what `assert_plan_changed` exists to catch and it was never called. The Planner now receives the critique and the already-tried queries on a replan.

  Also verified in the same run: the **embedding cache** (0/640 hits then **640/640**, `embed_ms` 32,096 → **206**) and the **checkpointer** (17 MB `checkpoints.sqlite`, `resumable_runs: ['loop_demo']`, all five stages listed as skippable).

  🔴 **Forward-compat warning to fix before submission:** LangGraph logs *“Deserializing unregistered type researchgpt.core.models.Paper from checkpoint. This will be blocked in a future version”* for all six of our Pydantic models. Checkpoints still load today, but a LangGraph upgrade would break resume. Register the models via `allowed_msgpack_modules`.

  ⚠️ **PARTIALLY DEMONSTRATED 2026-08-28. Do not tick yet.** The full six-agent graph ran end to end for the first time — `run_pipeline(use_loop=True)`, exit 0, 5.3 min, `max_papers=10`, on the paid host. Every agent fired: Planner → Retriever → Ranker → Extractor → **Critic** → Writer → **Verifier** → **Critic** → END.

  **What is proven:** the Critic is genuinely visited **twice per iteration** as designed — once after the Extractor with `grounding_score: null`, once after the Verifier with `grounding_score: 0.818` — and the second visit routed to **END** rather than back to the Writer. That is the `writer → verifier → critic → writer` spin the `final_review` check exists to prevent, and it did not happen. Verifier output: **33 claims decomposed, 27 verified, 6 dropped UNSUPPORTED, 0 contradicted, grounding 0.8182**.

  🔴 **What is NOT proven: the loop never FIRED.** `iterations: 0`, `decisions: ["WRITE", "WRITE"]`. Coverage came out at 1.00 and the corpus at 271 papers, so every gate passed on the first pass and no RETRIEVE or REPLAN was ever issued. T-509 requires the loop *firing* **and** terminating; only termination is demonstrated on real data. The firing path is covered by `test_loop_fires_on_an_under_covered_query_and_terminates`, which is a simulation, not a run. **To close M2, force a fire** — run a deliberately under-covered query (T-704's hallucination stress test is the natural candidate) and show RETRIEVE → REPLAN → forced WRITE in a real trace.

  🔴 **Every claim came back PARTIAL. Zero SUPPORTED.** `abstract_only_capped: 25` — T-505's cap fired on 25 of the 33 claims because **10 of 10 papers are abstract-only**, which is the standing reality of an OpenAlex corpus. *The system cannot currently emit a SUPPORTED claim at all.* This is the cap working exactly as designed, but it means the grounding figure is entirely made of PARTIALs and the report must say so rather than quoting 0.82 unqualified.

---

## 8. Phase 6 — API and the Vue app (Days 8–10: Sep 2–4)

Grading is weighted to the system visibly working. Build the panels in order; **1–3 alone are a strong demo.**

- [x] **T-601** ⌨️ `api/app.py` + `api/schemas.py` — the five endpoints from `PROJECT_PLAN.md §7.2`. *Done when: all five respond.*  ✅ **DONE 2026-08-28** — `api/app.py` + `api/schemas.py`, all five responding. ⚠️ **The filesystem is the source of truth, and `T-625` says it must stay that way** even once Phase 6B lands: the registry is an index over `outputs/runs/`, never the record. `POST /api/review` returns **202** and runs on a worker thread — a run is minutes long and blocking would time out every proxy in between. Artefact downloads use a **closed allowlist** rather than path sanitising, and `run_id` is resolved-then-contained, because both arrive from the URL. Tested: traversal, unknown artefact and missing run all refuse rather than 500.
- [x] **T-602** ⌨️ SSE progress stream — one event per agent transition, carrying iteration count and the Critic's decision.  ✅ **DONE 2026-08-28** — SSE over `sse-starlette`. ★ **`trace.jsonl` IS the event stream**, tailed from disk rather than a second in-memory bus: T-904 fixes that schema and every report figure already depends on it, so a panel in the browser and a figure in the report cannot disagree about what happened; a *finished* run replays identically to a live one, which is exactly what T-610 needs; and a crashed run still has its events. The stream **replays history before following the tail** (a late client sees the whole story) and **terminates** on a finished run rather than holding the connection open forever.
- [x] **T-603** 🧠 ★ **Record a fixture run** (result JSON + SSE event log to disk) and add a `--fixture` flag. *This decouples all frontend work from backend readiness and costs zero API calls. It saves a full day. Do it before writing any Vue.*  ✅ **DONE 2026-08-28, at zero API cost** — `outputs/runs/fixture/`, a full artefact set from the M2 loop run (4 Critic decisions, 19 verified claims with evidence spans, 3 dropped). ★ **Built from the T-508 checkpoint, not from a new run**: `loop_demo4`'s claims were still in `checkpoints.sqlite`, so the fixture cost no tokens and no waiting — the checkpointer paid for itself the day it was wired in.

  **No special serving path exists, deliberately**: the artefact directory already *is* the fixture, so `/result` and `/events` replay it byte-identically to a live run. `RESEARCHGPT_FIXTURE=1` makes `POST /api/review` return **409** rather than quietly serving the recording — substituting yesterday's answer for today's question is how a demo lies without anyone noticing. `/api/health` reports `fixture_mode` so the UI can say so on screen.
  🔴 **`claims.json` was missing and blocked Panel 3.** The Verifier's `verified_claims` and their evidence spans lived only in graph state and vanished at run end: `review.md` kept the prose and `trace.jsonl` kept a `claim_dropped` event per drop, but the *verified* claims and the spans justifying them were never written anywhere. T-607 is “click any sentence → see its supporting evidence span”, which cannot be built over data the pipeline throws away. `output/writers.py::write_claims` now emits `claims.json` (verified **and** dropped in one file, since Panel 4 is only persuasive next to Panel 3).

- [x] **T-604** ⌨️ Vue 3 + Vite scaffold, Composition API, scoped CSS, **no Pinia** (one page, one run — a store is ceremony).  ✅ **DONE 2026-08-28** — `frontend/`, Vue 3 + Vite, Composition API, scoped CSS, **no Pinia**. Builds clean (113 KB JS / 42 KB gzipped, 734 ms). Vite proxies `/api` to `127.0.0.1:8000` so the browser stays on one origin and `EventSource` does not depend on the API's permissive CORS — that CORS is a localhost convenience, not something the app should rest on. ⚠️ Vite binds **IPv6 `[::1]:5173`**, not `127.0.0.1`, so `curl 127.0.0.1:5173` refuses; use `localhost` or `[::1]`.
- [x] **T-605** ⌨️ **Panel 1** — query input, `max_papers`, run button.  ✅ **DONE 2026-08-28** — Panel 1. Question, `max_papers` (defaulting to **10**, since a 25-paper run is minutes long against a metered tier), run button, plus the previous-runs list the T-610 demo replays from. The run button is disabled in fixture mode.
- [x] **T-606** ⌨️ **Panel 2** — live agent progress: the six agents lighting up as SSE events arrive, showing iteration count and Critic decisions. *Makes the "agentic" claim visible in the first thirty seconds.*  ✅ **DONE 2026-08-28** — Panel 2. Seven nodes lighting up from the SSE stream, with a re-run count badge when the loop re-enters an agent. ★ **The Critic decisions render as a visible chain**, not a log line: on the M2 fixture that reads `RETRIEVE → REPLAN → RETRIEVE → WRITE`, which *is* the agentic claim made visible.
- [x] **T-607** ⌨️ ★ **Panel 3 — evidence inspection.** Rendered review; **click any sentence → see its supporting evidence span and source paper.** *The money shot: direct visual proof of the anti-hallucination claim. If one panel survives, it is this one.*  ✅ **DONE 2026-08-28 — and verified on real data, not just built.** Panel 3 renders the review as prose and marks every sentence the Verifier ruled on; clicking one shows the evidence span it was scored against, the score, and the source paper (flagged *abstract only* where T-505 applies).

  ★ **Measured against the fixture: 19 of 19 verified claims located in the review, 0 misses, 19/19 carrying an evidence span.**

  🔴 **Sentences are matched to claims by NORMALISED TEXT, not by offset, and that is load-bearing.** The Verifier strips `[n]` markers when it decomposes while the Writer's markdown carries them, so a byte offset into `review.md` points at the wrong place. If the two normalisations ever drift, the panel silently highlights **nothing** and the graded money shot renders as plain prose — with no error anywhere. `test_verified_claims_are_locatable_in_the_review` asserts the contract from the Python side so a pipeline change cannot break the front end unnoticed. An unmatched sentence renders as plain prose rather than being dropped: showing less beats showing something misattributed.
- [x] **T-608** ⌨️ **Panel 4 — dropped-claims panel** plus artefact downloads. *"14 claims were removed as unsupported."* Showing what the system **refused** to say is more persuasive than showing what it said.  ✅ **DONE 2026-08-28** — Panel 4, dropped claims with verdict and score, plus artefact downloads. Leads with the count and the percentage, because *“3 claims were removed as unsupported”* is the sentence that sells the architecture.
- [x] **T-609** ⌨️ ★ **Human-in-the-loop control** — confirm/override on dropped claims, written back to the trace via `human_overrides` (already in `graph/state.py`). **REQUIRED — T-007 decided 2026-08-25 that HITL is mandatory.** ~half a day on top of Panel 4. *This is the concrete implementation of Objective 2's "and Human-in-the-loop" clause; without it that objective is unmet and the claim on slide 5 is false.*  ✅ **UI DONE 2026-08-28** — confirm / override on every dropped claim, click-again to clear so a mis-click cannot leave a judgement nobody meant in the log. ⚠️ **An override does NOT edit the review, deliberately**: it records a human judgement *about* a claim the Verifier dropped, which is a different and more honest thing than reinstating text. Putting dropped prose back into `review.md` on a click would quietly destroy the very property the panel exists to prove. ✅ **CLOSED 2026-08-28 — overrides now persist.** `POST /api/runs/{id}/overrides` appends a `human_override` event to `trace.jsonl`, and `GET /result` replays them, so a judgement survives a reload — the criterion that separates *a UI control* from HITL being implemented.

  **The trace is the single source of truth, not a side file.** T-904 fixes its schema and the report's override count will be derived from it; a second store would create two answers to “what did the human decide?”. Appends rather than rewrites, so a changed mind is history. Last write per claim wins, and a `null` decision clears it — a mis-click must be undoable or the audit record keeps a judgement nobody meant. An override against an unknown claim is refused (404).

  🔴 **A real bug the test caught:** appending blind to a trace that does not end in a newline concatenates the record onto the last line and **destroys both** — in the file every report figure comes from. The write now checks the final byte first.
- [x] **T-610** 🧠 **Pre-bake the showcase run.** A 60-paper run is 20–40 minutes on CPU against a rate-limited API — far too slow to run live in front of an examiner. Ship a completed run that replays instantly via `GET /api/runs`, and demo *live* execution only at `max_papers=10`. **Decide this now, not the night before.**  ✅ **DONE 2026-08-28** — `SHOWCASE.md`, the demo runbook. `decisions.txt` **D-11** had already chosen option (a): pre-bake a run that replays instantly, demo live only at `max_papers=10`, and justify it as demo **reliability** rather than a latency workaround.

  The pre-baked run is `outputs/runs/fixture/` — the M2 loop run: `RETRIEVE → REPLAN → RETRIEVE → WRITE`, 551 papers, 19 verified claims with evidence, 3 dropped, grounding 0.8636. **No separate recording format exists**: the artefact directory *is* the fixture, so re-baking is `cp -r outputs/runs/<better_run> outputs/runs/fixture`.

  With `RESEARCHGPT_FIXTURE=1` the API **refuses** to start live runs, so nothing can be accidentally triggered mid-demo, and the graded moment has no network dependency at all.

  ⚠️ **The runbook says two things out loud before an examiner can find them first**: zero claims reached SUPPORTED (all 19 are PARTIAL because every paper is abstract-only and T-505 caps that by design, so the 0.86 grounding figure is made *entirely* of PARTIALs), and union recall is **0.057**. **Re-bake once retrieval improves** — the current run is honest but thin.

---

## 8.1 Phase 6B — Postgres run registry (Sep 3–4, after T-607)

**Added 2026-08-25 by decision.** Full schema, DDL, SQLAlchemy models and failure semantics in **`DB_SCHEMA.md`** — read that first; the tasks below are the schedule, not the design.

**Stack: PostgreSQL + plain SQLAlchemy 2.0, in-process inside the existing FastAPI backend.** No Flask, no Flask-SQLAlchemy — one web framework, one ORM.

**It also fixes a real inconsistency.** `SESSION_CONTEXT.md §7.2` flags Review-1 slides 3, 8 and 9 as claiming **PostgreSQL** while every other document says Chroma + SQLite. That was logged as a slide error to correct; building this makes the claim true instead.

> ⛔ **Sequenced after T-607 (evidence-inspection panel).** That panel is the graded money shot. The registry must never displace it.
>
> ★ **The load-bearing rule: the registry is best-effort and never blocks a run.** The pipeline writes artefacts to `outputs/runs/<run_id>/` and completes even if Postgres is down, unreachable, or never installed. Same discipline as `TraceLogger`, which never raises into its caller. *A registry bug must not be able to kill a 30-minute run four days before submission.*

- [x] **T-620** 👤 Install PostgreSQL locally, create the `researchgpt` role and database, put `DATABASE_URL` in `.env` and an empty key in `.env.example`. Add a `db = ["sqlalchemy>=2.0", "psycopg[binary]>=3.1"]` extra to `pyproject.toml` so the project still installs without Postgres. *Done when: `psql` connects and `CREATE EXTENSION pgcrypto` succeeds.*

  ✅ **DONE 2026-08-28** — PostgreSQL **18.6** on `localhost:5432`, database `major_project`, user `postgres`. `DATABASE_URL` is in `.env` (gitignored, verified with `git check-ignore`) and `.env.example` carries the empty placeholder. The `db` extra is in `pyproject.toml`.

  Schema created by `Base.metadata.create_all` per `DB_SCHEMA §8` — no Alembic. Verified against `\d runs`: all 10 columns, PK on `id`, UNIQUE on `run_id`, **GIN index on `artefacts`**, DESC index on `created_at`, and the `ck_runs_status` CHECK constraint. `session.py` now calls `load_dotenv()`, without which the registry was silently disabled on every plain `pytest` run while a working database sat there.



  ⚠️ **Still yours — nothing here installs PostgreSQL.** The rest of Phase 6B (T-621–T-625) is **built and tested without it**, because the design requires the registry to be absent-tolerant. ✅ The `db = ["sqlalchemy>=2.0", "psycopg[binary]>=3.1"]` extra is added to `pyproject.toml` and `DATABASE_URL=` is in `.env.example`. When you install Postgres, set `DATABASE_URL` and the registry activates with no code change — two currently skipped tests (`test_round_trip_against_a_real_database`, T-626's live half) will start running.
- [x] **T-621** 🧠 `src/researchgpt/db/models.py` — the `Run` model per `DB_SCHEMA.md §7`. **Claude Code writes this by hand**, same reasoning as T-102: it is a schema, and `MutableList.as_mutable(JSONB)` is a correctness requirement rather than a style choice. ⚠️ **Without the `Mutable*` wrappers, `run.artefacts.append(...)` followed by `commit()` silently emits no UPDATE** — the row is never marked dirty, the artefact vanishes, and there is no error to debug.  ✅ **DONE 2026-08-28** — `db/models.py`, hand-written per `DB_SCHEMA §7`. 🔴 **`MutableList` / `MutableDict` are load-bearing and there is a behavioural test for them.** With a bare JSONB column, `run.artefacts.append(...)` then `commit()` leaves the object identical to the one loaded, so the row is never marked dirty, **no UPDATE is emitted, and the artefact vanishes with no error**. The test asserts the *runtime type* of the attribute, not the column type — `as_mutable` does not change the column type, so a type assertion passes either way and proves nothing. *(My first attempt at that test was exactly that tautology.)*
- [x] **T-622** ⌨️ `src/researchgpt/db/session.py` — engine with `pool_pre_ping=True`, sessionmaker, and a `create_all` bootstrap. *No Alembic: one table, no production data, and every run is reconstructible from `outputs/runs/`.* *Done when: importing the module with `DATABASE_URL` unset does not raise — it disables the registry.*  ✅ **DONE 2026-08-28** — `db/session.py`. Importing with `DATABASE_URL` unset does not raise (the stated criterion), an empty value counts as unset, and the engine is built lazily so a missing driver is not an ImportError for every consumer.
- [x] **T-623** ⌨️ ★ `src/researchgpt/db/registry.py` — `register_run`, `mark_running`, `attach_artefact`, `complete_run`, `fail_run`. **Every one goes through the single `_safe()` wrapper from `DB_SCHEMA.md §9`** that catches broadly, logs a warning and returns `None`. *Done when: every public function returns cleanly with Postgres stopped.*  ✅ **DONE 2026-08-28** — `db/registry.py`. Every public function goes through the single `_safe()` wrapper and returns `None` on failure; none can raise. `list_runs()` returns **`None` when unavailable and `[]` when empty** — the distinction T-625 needs, or an empty database would look exactly like an empty disk.
- [x] **T-624** ⌨️ Wire best-effort hooks into `cli.py` and the FastAPI run path: register at `run_start`, attach each artefact as it is written (with `bytes` and `sha256`), complete with `metrics` read from `trace.jsonl`.  ✅ **DONE 2026-08-28** — hooks in `run_pipeline`: register at start, mark running, attach each artefact with its **size and sha256**, complete with metrics read from state, and `fail_run` on the no-review path. Imported *inside* the function, with a test enforcing it, so `sqlalchemy` stays optional.
- [x] **T-625** ⌨️ `GET /api/runs` reads the registry, **falling back to a filesystem scan of `outputs/runs/` when the registry is unavailable.** *The Vue run-list and the T-610 pre-baked demo both depend on this endpoint, so it must work with no database at all.*  ✅ **DONE 2026-08-28** — `GET /api/runs` reads the registry and falls back to a filesystem scan. **Verified working with no database at all**, which the Vue run list and the T-610 demo both depend on.
- [x] **T-626** 🧠 ★ **Verification: stop the Postgres service mid-run and confirm the run completes with every artefact on disk.** *If this test does not pass, the non-blocking rule is not implemented, whatever the code looks like.* Also confirm `GET /api/runs` still returns rows via the filesystem fallback.  ✅ **VERIFIED 2026-08-28, by simulation** — with the registry pointed at a dead host, all five calls plus artefact writing complete and `review.md` is on disk. The live half (stop the real service mid-run) is skipped pending T-620.

  🔴 **Two real defects this verification exposed, both of which would have broken the non-blocking rule in production:**

  1. **`_safe()` catches exceptions but not TIME.** A host that *drops* packets rather than refusing them — a suspended VM, a slept laptop, a firewalled port — left `connect()` blocking for the OS default, minutes on Windows, with the pipeline sitting there. **Hanging a run is exactly as bad as breaking it.** Found because these very tests hung instead of failing. Fixed with `connect_timeout=3`.
  2. **Bounded is not free.** A run makes register + mark_running + one attach *per artefact* + complete, so at 3 s apiece a dead database added **~12.6 s to every run** (measured). A process-scoped circuit breaker takes that to **3.5 s**: the first call proves it unreachable, the rest are no-ops. The registry is an index over data the filesystem already holds — it does not deserve a retry budget.

---

## 9. Phase 7 — Evaluation (Days 10–12: Sep 4–6)

- [ ] **T-701** ⌨️ `eval/metrics.py` — citation accuracy (every `[n]` resolves to a real DOI in the metadata DB), groundedness, coverage, **claims dropped per run**, latency, request count. All computed from `trace.jsonl`.
- [ ] **T-702** 🧠 ★ **Ablation 2 (− Verifier).** **Run this first, before any other ablation.** It quantifies hallucination with and without the filter — precisely the graded property. `max_papers=25`, launched overnight.
- [ ] **T-703** 🧠 Ablation 1 (full system) at `max_papers=25` for comparison.
- [ ] **T-704** 🧠 ★ **Hallucination stress test.** Deliberately query a topic the corpus does not cover and show the system **refuses rather than invents**: claims dropped, Critic reports the coverage gap, output carries an explicit Limitations section instead of fabricated content. Two hours of work, and the most convincing possible answer to *"how do I know it isn't making things up?"* Wire the result into Panel 4 so it is demoable, not merely reportable.
- [ ] **T-705** 👤 ★ **50-claim verifier spot-check** on real output. *This is the non-circular evidence. Groundedness measured by the system that enforces groundedness proves only that the filter ran (`PROJECT_PLAN.md §9.6`).*
- [ ] **T-705b** 🧠 ★ **Report the three verifier measurements side by side**: SciFact held-out (T-305, curated benchmark), SciReviewGen cross-check (T-325, human-authored at scale), and the 50-claim spot-check (T-705, your own domain). *Three independent lenses on one component. This table is the single strongest page in the evaluation, and it closes `PROJECT_PLAN.md §9.6`'s circularity trap outright — no reviewer can say the groundedness number only proves the filter ran.*
- [ ] **T-706b** 🧠 **Ablation 5 — stock vs fine-tuned reranker** (T-336), if Phase 3C passed its adoption gate. Isolates the reranker's contribution to end-to-end grounding.
- [ ] **T-706** 🧠 Ablations 3 (− Critic loop) and 4 (vanilla RAG ≈ base-paper configuration) — **only if time remains.** Use Ammann et al.'s configuration as a stronger ablation-4 baseline than vanilla RAG (`SESSION_CONTEXT.md §5.6`).
- [ ] **T-707** 🧠 **Revise the target numbers downward before writing any results.** `PROJECT_PLAN.md §9` targets groundedness ≥ 0.9. Nothing peer-reviewed reaches that on realistic scientific verification — Sarol et al. 0.59 micro-F1, CliVER 0.797 against clinicians, SurveyGen 35.84% citation accuracy, SciReviewGen ~30% of chapters at human quality. **If the verifier reports 0.9+ against real citations, suspect the measurement, not a breakthrough** (`SESSION_CONTEXT.md §5.2`).

---

## 10. Phase 8 — Documents, deck, submission (Days 12–13: Sep 6–7)

- [ ] **T-801** 🧠 ★ **Rewrite `RESEARCHGPT_SPEC.md` §1.2 and §1.3 around SurveyGen** (T-005 approved the switch 2026-08-25). §1.2 currently describes Aytar et al. and mis-states even that — its real title is *"A synergistic multi-stage RAG architecture for boosting context relevance in data science literature."* §1.3's *"fixed single-pass pipeline"* row is **factually wrong** about Aytar and must go regardless. **New framing:** SurveyGen is the same task (survey generation) with quality-aware retrieval that maps onto your venue tiering, and its authors state your problem statement for you. Aytar et al. becomes a *related* work, cited for the multi-stage retrieval design, not the base paper.
- [ ] **T-802** 🧠 Update `SPEC §3` (architecture diagram → the draw.io file), `§4` (relabel it "Package Dependency Map" and add the real MCD — **add the persistence subsystem if Phase 6B ships**), `§7.5` (add HITL to the Critic), `§9` (revised targets from T-707).
- [ ] **T-803** 🧠 Report — **Introduction**: lead with the four independent measurements of the same failure (Sarol 39.18% of citation instances contain accuracy errors; ALCE, best models "lack complete citation support 50% of the time"; FActScore, ChatGPT factually correct on 58% of atomic claims; SurveyGen 35.84%). Then FActScore's killer statistic: **36.0% of supported and 37.6% of unsupported sentences carried citations — statistically indistinguishable.** The presence of a citation carries almost no information; that is the justification for claim-level verification.
- [ ] **T-804** 🧠 Report — **Related Work**: quote Ammann et al.'s own Limitations item 6 verbatim (*"Lack of iterative retrieval. Our pipeline operates in a single-shot manner... This limits its ability to support adaptive multi-step reasoning."*) — your closest competitor names your contribution as its own limitation. Use SciReviewGen's limitations list as a requirements table (`SESSION_CONTEXT.md §5.9`).
- [ ] **T-805** 🧠 Report — **Discussion**: Valsci Table 3 — GPT-4o-mini *inside* their architecture scores F1 0.720; bare GPT-4o scores 0.706. **Architecture beats model scale, measured.** This converts the $0 constraint from an apology into a hypothesis: *the architecture is a correctness filter, not a correctness source.*
- [ ] **T-806** 🧠 Report — **Limitations**, written honestly: SciFact's biomedical skew against a CS corpus (domain shift), SciReviewGen's frozen-2020 biomedical skew against the reranker's CS target domain, human κ of 0.18–0.42 on exactly the thing you measure, retrieval recall as a hard ceiling on verification, and the abstract-only paper split. *Naming a limitation is stronger than hiding it.* **Include the Writer future-work paragraph** — the fine-tuning option that was evaluated and rejected on inference cost, drafted verbatim in `TRAINING_SPEC.md §4`.
- [ ] **T-807** 🧠 Report — literature-survey chapter: **hand-edit the T-409 generated survey.** One flagship run yields both the automated artefact and a human-checked chapter.
- [ ] **T-808** 👤 **Fix the two visible errors in `Review-1 dsc06.pptx`** if that deck is shown again: slide 6 says *"GPU: 8GB Minimum"* on a CPU-only machine, and slide 8 says *"Extractor chunks and embeds them"* — that is the Ingestor's job, and as written the system has **no structured extraction at all**, which deletes a main contribution.
- [ ] **T-809** 👤 Final deck: swap in real screenshots, **the two-row trained-model table from `TRAINING_SPEC.md §3`** (verifier stock-vs-tuned from T-305, reranker stock-vs-tuned from T-334), the ablation-2 numbers (T-702), and the dropped-claims count. *That table is the answer to "where is the machine learning in this project?" — `SESSION_CONTEXT.md §7.2` flags slide 5 as needing it.*
- [ ] **T-810** ⌨️ `README.md` + `make reproduce` — one command that regenerates a run from a cached config. *Reproducibility is `SPEC §14.10`, and it is cheap.*

  ✅ **README half DONE 2026-08-28.** Covers the architecture and why two components are deliberately deterministic, the two trained models with their measured stock-vs-tuned numbers, install/run for CLI + API + UI, the artefact set, and the layout.

  ★ **It states the two weaknesses up front rather than burying them** — union recall 0.057, and zero SUPPORTED claims because every paper is abstract-only and T-505 caps that by design. They read far worse when a reviewer finds them first. Every metric in it was fact-checked against `eval/*.json` before commit; a first draft had mixed the flagship run's claim counts with the loop demo's decision chain, which the check caught.

  ⚠️ **`make reproduce` is still outstanding** — the other half of T-810. `SPEC §14.10` wants one command that regenerates a run from a cached config; the pieces exist (`config.json` per run, the T-104 prompt cache, `run_pipeline(run_id=...)`) but nothing ties them together yet.
- [ ] **T-811** 👤 **Obtain the PDF of Li et al., *Information Processing & Management*** (DOI `10.1016/j.ipm.2025.104369`) through the library. ScienceDirect returns HTTP 403 to automated access, so it is the one paper in the set written from its title alone. *"Evidence-aware" + "self-corrective" describes your Verifier and Critic — **it may be a competitor to differentiate from, not a supporting citation.*** Also resolve its year (OpenAlex says 2025, Semantic Scholar 2026) before it enters the reference list.
- [ ] **T-812** 👤 Verify **Vicinagearth** (paper C3-11) is Scopus-indexed. If not, substitute Wang et al. 2024, *Frontiers of Computer Science*, DOI `10.1007/s11704-024-40231-1`.
- [ ] **T-813** 🧠 **Re-verify every DOI** before submission. Indexes and publication years change.

---

## 11. Cross-cutting — continuous, not a phase

- [x] **T-901** ⌨️ Unit tests alongside each module. Cursor writes the test in the same prompt as the module; the acceptance criterion *is* the test.  ✅ **SATISFIED CONTINUOUSLY** — **284 tests** across 8 acceptance suites, one per phase. The convention held: the acceptance criterion *is* the test, and several of the most valuable defects this project found were found by writing one — the trace-append corruption (T-609), the unbounded registry connect (T-626), and the registry hiding 58 runs on disk (T-625).
- [ ] **T-902** 🧠 Review every Cursor diff before commit. Assume hallucinated imports until proven otherwise.

  ⚠️ **Not applicable as written.** The two-agent split in §1 assumed Cursor would write the code; in practice Claude Code wrote it directly, so there were no Cursor diffs to review. The underlying risk — unreviewed generated code — was covered instead by T-901's acceptance tests and by `ruff`. Left unticked because the task as phrased never happened.
- [x] **T-903** 🧠 Commit at every completed task. `git log` is the project timeline evidence.  ✅ **SATISFIED CONTINUOUSLY** — a commit per completed task, each carrying the measurement that justified it. 🔴 **But they are all still LOCAL:** `master` is ~25 commits ahead of `origin/master`, so the entire project lives on one disk and neither co-author can see any of it. This is the cheapest outstanding risk to close.
- [x] **T-904** 🧠 Keep the `trace.jsonl` schema stable from T-107 onward. Every report figure depends on it.  ✅ **HELD** — the `trace.jsonl` schema is unchanged since T-107, and the decision to keep it stable paid off twice in Phase 6: **SSE tails the trace directly** rather than maintaining a second event bus (T-602), and **HITL overrides are appended to it** rather than to a side file (T-609). One definition of “what happened”, so a browser panel and a report figure cannot disagree.

---

## 12. Critical path

> ✅ **RESOLVED 2026-08-28. Both milestones landed early: M1 on 08-27 (4 days early), M2 on 08-28 (5 days early).** The diagram below is kept as the record of what gated what.
>
> 🔴 **The critical path has moved.** Nothing on this diagram is blocking any more; **T-212/T-213 (retrieval recall) now gates Phase 7**, because T-702's ablation — the graded claim — is measured on the corpus retrieval produces, and that corpus currently misses 33 of the 35 gold papers.

Only these gate M2. Everything else can slip.

```
T-001/002 ─▶ T-104 (llm.py + cache) ─▶ T-201..210 (retrieval) ─▶ T-212 (recall gate ≥ 0.80)
                                                                        │
T-301 ─▶ T-302 ─▶ T-303 (Kaggle) ─▶ T-304 (ONNX int8) ──────────┐      │
        (parallel, unattended)                                    │      ▼
                                                                  │  T-402..407 ─▶ 🔴 M1 (Aug 31)
T-320 ─▶ T-321 ⛔ ─▶ T-322 ─▶ T-323 ─▶ T-324 ────────┐            │                    │
        (Phase 3B — parallel data track, no API,      │            │                    │
         no pipeline, does NOT gate M1 or M2)         │            └──▶ T-501..507 ─────┴─▶ 🔴 M2 (Sep 2)
                                                       │                                     │
                                                       │                       T-603 (fixture) ─▶ T-607 (Panel 3)
                                                       │                                     │
                                       T-304 ─────────▶ T-325 ★★ ──▶ T-705b ◀── T-705   T-702 (Ablation 2)
                                              (verifier cross-check)      (three-lens table)

T-330 ─▶ T-331 ─▶ T-332 (Kaggle) ─▶ T-333 ─▶ T-334 ─▶ T-335 (adoption gate)
        (Phase 3C — reranker fine-tune. NOT on the critical path at all:
         the pipeline ships with the stock reranker and T-335 is a weight
         swap. A failed run here costs nothing downstream.)

Phase 3B joins the critical path only at T-325, which needs the trained verifier.
Everything before it is independent parsing work. T-321 is the internal blocker:
if the bib-resolution gate fails, T-322..T-325 cannot proceed.

Phase 3C touches the critical path nowhere. It reuses T-321's parser and
T-212's eval harness, and its output is optional by construction (T-335).

Phase 6B (Postgres registry) is likewise off the critical path by design: the
pipeline writes to disk regardless and T-625 falls back to a filesystem scan.
```

---

## 13. Kill switches — decide these on the date, not in hindsight

> **Outcome as of 2026-08-28** — recorded so a passed date is not silently forgotten:
>
> | date | switch | what actually happened |
> |---|---|---|
> | Aug 28 | Recall@20 < 0.80 | 🔴 **FIRED, and is still unanswered.** Union recall is **0.057**. The prescribed response — escalate `bge-small` → `bge-base` and spend a day on retrieval — has **not** been done. The “push M1 to Sep 1” clause is moot: M1 landed Aug 27. |
> | Aug 28 | T-321 gate < 0.95 | Did not fire. Resolution rate **1.0000**. |
> | Aug 29 | Kaggle verifier not trained | Did not fire. Trained Aug 27, macro-F1 **0.769**. |
> | Aug 30 | T-322 pairs not produced | Did not fire. Phase 3B complete. |
> | Aug 30 | Reranker not trained / no gain | Did not fire, but *did* need the retrain: the first fine-tune was reverted, then T-332R's mixed-negative build passed T-335 and was adopted. |
> | Aug 31 | M1 not landed | Did not fire. **Landed Aug 27.** |
> | Sep 2 | M2 not landed | Did not fire. **Landed Aug 28.** |
> | Sep 4 | Vue not started | Did not fire. **Phase 6 complete Aug 28**, all four panels + HITL. |
> | Sep 4 | Phase 6B registry not working | Did not fire. **Complete Aug 28** against PostgreSQL 18.6. |
> | Sep 6 | Ablations not run | **Still live.** Phase 7 has not started, and it is now the critical path. |

| Date | If this has not happened | Do this |
|---|---|---|
| **Aug 28** | Recall@20 < 0.80 | Escalate `bge-small` → `bge-base`. Spend all of Aug 29 on retrieval. Push M1 to Sep 1. |
| **Aug 28** | T-321 bib-resolution gate < 0.95 | The delimiter parse is wrong. Spend half a day fixing it. If it still fails, fall back to **`kdercksen/scireviewgen-csv`** (same splits) before abandoning — do not lose T-325 to one bad mirror. |
| **Aug 29** | Kaggle verifier not trained | Fall back to a **stock** NLI checkpoint in the pipeline and report stock-vs-tuned as future work. The pipeline must never block on training. |
| **Aug 30** | T-322 pairs not produced | Drop the T-324 retrieval gold sets (T-212b) and keep **only** the T-325 cross-check. The cross-check is why this track exists; the retrieval breadth check is a bonus. |
| **Aug 30** | Reranker fine-tune (T-332) not trained, or T-334 shows no out-of-domain gain | **Keep the stock reranker and move on.** The pipeline is unaffected — this was always a weight swap, never a dependency. Report the negative result; a fine-tune that did not help is an honest finding, and the verifier still satisfies the training requirement on its own. |
| **Aug 31** | M1 not landed | **Stop building forward.** Stabilise the linear pipeline, ship the survey, cut the Critic loop to a single pass. |
| **Sep 2** | M2 not landed | Ship the five-agent system without the Critic loop. **The Verifier stays** — it is the graded component; the loop is not. |
| **Sep 4** | Vue not started | Ship Panels 1–3 against the fixture, **plus the minimum HITL surface** — a dropped-claims list with confirm/override writing to `human_overrides`. ⚠️ **HITL can no longer be dropped (T-007, 2026-08-25).** Cut Panel 4's *styling and artefact-download chrome* instead, not its function. |
| **Sep 4** | Phase 6B registry not working | **Cut it entirely.** `GET /api/runs` falls back to a filesystem scan and loses nothing the demo needs — the filesystem already holds everything the registry would store. Revert the deck to Chroma + SQLite instead (`SESSION_CONTEXT.md §7.2`). |
| **Sep 6** | Ablations not run | Ship ablation 2 alone. It is the graded claim. Report the rest as future work. |

---

## 14. Open items only you can close

Carried forward from `SESSION_CONTEXT.md §8`, plus new ones. All appear in Phase 0 or Phase 8 above; repeated here so none is lost:

**Closed since this list was written:** T-005 (base-paper switch approved), T-006 (MCD notation),
T-007 (HITL confirmed mandatory — and now implemented and persisted, T-609), T-620 (PostgreSQL 18.6
installed and connected 2026-08-28).

**Still only you can do these:**

1. **T-705** — the 50-claim spot-check. *Not your only non-circular evidence now that T-325 exists,
   but still the only one measured in **your own domain**: SciReviewGen is biomedical-and-CS survey
   prose, your corpus is agentic RAG. Both are needed; they answer different objections.*
   ⚠️ Needs real output, and the current flagship run has **0 SUPPORTED claims and 0.057 recall** —
   spot-checking that corpus measures the wrong thing. **Fix retrieval first, then run this.**
2. **T-811** — obtain the Li et al. IPM PDF and resolve its publication year.
3. **T-812** — verify *Vicinagearth* is Scopus-indexed.
4. **T-215** — the free Semantic Scholar API key. Cheap, and it widens retrieval, which is now the
   binding constraint.
5. 🔴 **Push these commits.** `master` is ~25 commits ahead of `origin/master` and everything
   — M1, M2, the whole application — exists on one disk, invisible to both co-authors.

---

*Derived from `PROJECT_PLAN.md` (rev 3), `RESEARCHGPT_SPEC.md`, `SESSION_CONTEXT.md`, `ARCHITECTURE_REVIEW.md`, `LITERATURE_REVIEW.md`, `PAPER_DEEP_DIVE.md`, and the 2026-08-09 and 2026-08-20 sessions. Amend in place.*
