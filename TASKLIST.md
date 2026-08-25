# ResearchGPT — Master Task List

> **What this file is.** The single executable backlog for the whole project, derived from `PROJECT_PLAN.md`, `RESEARCHGPT_SPEC.md`, `SESSION_CONTEXT.md`, `ARCHITECTURE_REVIEW.md` and the two `diagrams/*_EXPLAINED.md` files.
>
> **Two-agent workflow.** **Claude Code plans, specifies, reviews and integrates. Cursor (Groq) writes the code.** Every task below is written so it can be handed to Cursor as a self-contained unit of work with a hard acceptance test.
>
> Created 2026-08-25. Update the checkboxes in place; do not rewrite the file.

---

## 0. Reality check — read this before anything else

| | |
|---|---|
| Plan written | 2026-08-06 (30-day plan, Day 1 = 2026-08-07) |
| Today | **2026-08-25** |
| Target submission | **~2026-09-05** |
| Days actually remaining | **11** |
| Code written so far | **Zero.** No `src/`, no `pyproject.toml`, no `.py` file anywhere in the folder. |

**The 30-day plan is no longer executable as written.** Nineteen of its thirty days are gone and none of them produced code. What exists is planning, literature, design and two graded decks.

This file is therefore **not** the 30-day plan re-typed. It is a compressed 11-day plan that applies the descope ladder in `PROJECT_PLAN.md §10` **up front** rather than in a panic on Day 28. Concretely, the following are cut before starting, not deferred:

| Cut now | Was | Why |
|---|---|---|
| SciReviewGen integration | `PROJECT_PLAN.md §5.3` | Access request has multi-day latency. No time. Your own 25-paper bibliography becomes the sole gold set. |
| Ollama feasibility probe | §6.3 | Already demoted to a footnote. Dead. |
| DOCX writer | §2.2 | Markdown + PDF-from-Markdown suffices. |
| 2-annotator Likert + Cohen's κ | §9 | Scheduling cost exceeds its evidentiary value at 11 days. Replaced by the 50-claim spot-check. |
| Ablations 3 and 4 | §9.4 | Kept only if Phase 7 finishes early. **Ablation 2 is never cut.** |
| Extraction F1 annotation (10 papers) | §5.4 | Replaced by 5 qualitative examples. |

**Never cut, under any circumstance** — these six are the project: the six agents, the trained verifier, the evidence-inspection panel, ablation 2 (− Verifier), `trace.jsonl`, and the **M1 milestone** (first complete cited survey).

> If M1 has not landed by **2026-08-31**, stop building forward and stabilise what exists. A working four-agent pipeline that produces a cited survey beats a half-wired six-agent graph that runs nothing.

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

- [ ] **T-001** 👤 ⛔ Register **Google AI Studio (Gemini) free tier** and **Groq** API keys. Record both in `.env`. *Done when: both keys return a completion from a curl one-liner.*
- [ ] **T-002** 👤 ⛔ Confirm the **Kaggle** account has GPU quota available this week (Settings → phone verified → GPU hours remaining). *Done when: quota ≥ 5 h confirmed.*
- [ ] **T-003** 👤 Create a Hugging Face account + read token (needed for `allenai/scifact` and `deberta-v3-small`). *Done when: `huggingface-cli whoami` succeeds.*
- [ ] **T-004** 🧠 Run the 30-minute **JSON-reliability bake-off**: same Extractor prompt, 5 papers, Gemini vs Groq, count clean Pydantic parses. Pick the primary on parse reliability, **not benchmark scores**. *Done when: a winner is recorded at the top of `configs/default.yaml` with the parse counts as a comment.* (`PROJECT_PLAN.md §6.2`)
- [ ] **T-005** 👤 **Confirm the base-paper switch with Dr. Govinda Rao**: Aytar et al. → SurveyGen (Bao et al., EMNLP 2025). *Rationale in `SESSION_CONTEXT.md §5.1`. This is the highest-value 10-minute conversation left in the project.*
- [ ] **T-006** 👤 Confirm which **MCD notation** the rubric means — UML component diagram or classical Yourdon/Constantine structure chart. Both are already prepared in `diagrams/`; they need different slide-12 text.
- [ ] **T-007** 👤 **Decide: does Human-in-the-Loop stay in Objective 2?** It is on PPT slide 5 and in both diagrams. Keeping it costs ~half a day (T-609). Dropping it means editing the objective and both diagrams. **Recommendation: keep it** — it is cheap, it is already drawn, and it is the answer to "what stops a wrong claim getting through?"
- [x] **T-008** 🧠 `git init`, `.gitignore`, first commit of the existing markdown and diagrams. *Done when: `git log` shows one commit and `data/`, `outputs/`, `.env`, `*.pptx` are ignored.* Done 2026-08-25: repo initialised; `.gitignore` covers `data/`, `outputs/`, `.env`, `*.pptx`; first commit is the planning artefacts plus `.env.example`.

---

## 3. Phase 1 — Core skeleton (Day 1: Aug 26) ⛔

Everything else sits on this. **Do not let Cursor improvise here** — Claude Code writes the schemas, Cursor fills the bodies.

- [ ] **T-101** 🧠 Author `pyproject.toml` + the directory scaffold per `RESEARCHGPT_SPEC.md §10`, minus the cut modules (`docx_writer.py`, `ragas_runner.py`, `notebooks/`). *Done when: `pip install -e .` succeeds and `import researchgpt` works.*
- [ ] **T-102** 🧠 Write `src/researchgpt/core/models.py` — all Pydantic models from `SPEC §8`. **Claude Code writes this by hand.** Every other module imports from it; a wrong shape here costs a day downstream. *Done when: `Paper`, `Chunk`, `Insight`, `Claim`, `Verdict`, `CritiqueDecision`, `RunConfig` all instantiate and round-trip through `.model_dump_json()`.*
- [ ] **T-103** 🧠 Write `src/researchgpt/graph/state.py` — the LangGraph state per `SPEC §8.1`, with reducers. **Claude Code writes this by hand.** *Done when: a dummy two-node graph merges partial state updates correctly.*
- [ ] **T-104** ⌨️ ★ ⛔ `src/researchgpt/core/llm.py` — the LLM adapter, with **all four** of: prompt-hash disk cache, requests-per-minute throttle, exponential backoff on 429, and a rate-limit guardrail that aborts loudly instead of looping silently. *This is the highest-leverage file in the build (`PROJECT_PLAN.md §6.2`) — every dev re-run after the first costs zero API requests.* **Claude Code reviews it line by line; Cursor does not touch it again afterwards.** *Done when: calling the same prompt twice issues exactly one HTTP request, and a simulated 429 storm aborts with a named exception rather than hanging.*
- [ ] **T-105** ⌨️ `src/researchgpt/core/config.py` — YAML loader → `RunConfig`, with env-var overrides. *Done when: `load_config("configs/default.yaml")` returns a validated `RunConfig` and an unknown key raises.*
- [ ] **T-106** 🧠 `configs/default.yaml` — revised from `SPEC §10.1` for the CPU/$0 reality: `bge-small-en-v1.5`, `ms-marco-MiniLM-L-6-v2`, `sources: [openalex, arxiv]`, `max_papers: 60` (25 for ablations), no `max_cost_usd`. *Done when: it loads clean through T-105.*
- [ ] **T-107** ⌨️ ★ `src/researchgpt/core/logging.py` — the `trace.jsonl` writer. Append-only, one JSON object per agent event: `{ts, run_id, agent, event, payload, iteration}`. *Free today, impossible to retrofit. Every figure in the report comes from this file.* *Done when: a three-event dummy run produces a parseable `trace.jsonl`.*
- [ ] **T-108** ⌨️ `src/researchgpt/cli.py` — Typer stub: `researchgpt --version`, `researchgpt run --question "..." --max-papers N`. *Done when: `researchgpt --version` prints.*
- [ ] **T-109** 🧠 `src/researchgpt/core/prompts/` — one versioned file per agent, each with the header comment required by `SPEC §14.4`. Bodies may be stubs today; the **Extractor prompt must be real** — structured output stabilises at ~20 few-shot examples and is malformed below ~10 (`SESSION_CONTEXT.md §5.10`).

---

## 4. Phase 2 — Retrieval (Days 2–3: Aug 27–28)

Bad retrieval silently poisons grounding, which is the graded criterion. This phase is where Cursor earns its keep — the connectors are mechanical.

- [ ] **T-201** ⌨️ `tools/search_sources.py` — **OpenAlex** connector. Use the `title_and_abstract.search` filter with a hard date window; plain `search=` sorted by citations returns irrelevant high-citation medical papers (`SESSION_CONTEXT.md §9`). Return `Paper` objects. *Done when: a query returns ≥20 deduped `Paper`s carrying DOI, venue, year and OA link.*
- [ ] **T-202** ⌨️ Same file — **arXiv** connector via the Atom API. *Done when: it returns `Paper`s with `arxiv_id` and a PDF URL.*
- [ ] **T-203** ⌨️ DOI-based dedup + `data/metadata_db.py` (SQLite). *Done when: the same paper arriving from both sources collapses to one row.*
- [ ] **T-204** ⌨️ `tools/pdf_loader.py` — OA PDF fetch + PyMuPDF text extraction with a section-header regex. Set `text_availability` = `full` | `abstract_only`. *Done when: 10 OA PDFs parse and one paywalled paper degrades to `abstract_only` without crashing.*
- [ ] **T-205** ⌨️ `data/chunker.py` — section-aware first, then recursive character split at 1200/200. **Must preserve `start_char`/`end_char`** — grounding depends on it. Never merge across papers. *Done when: every chunk's offsets slice the original text back out exactly.*
- [ ] **T-206** ⌨️ `data/embeddings.py` — `BAAI/bge-small-en-v1.5` on CPU, batched. *Done when: 3,000 chunks embed in under 5 minutes on this machine and the wall time lands in the trace.*
- [ ] **T-207** ⌨️ `data/vectorstore.py` — Chroma persistent collection. *Done when: a dense k=30 query returns chunks with metadata intact.*
- [ ] **T-208** ⌨️ `data/bm25_index.py` — `rank_bm25` over the same chunks. *Done when: sparse k=30 returns results.*
- [ ] **T-209** ⌨️ `tools/hybrid_retriever.py` — RRF fusion, `score = Σ 1/(60 + rank_i)`. *Done when: the fused ranking differs from both inputs and is stable across runs.*
- [ ] **T-210** ⌨️ `tools/reranker.py` — `cross-encoder/ms-marco-MiniLM-L-6-v2` on CPU → top-12. **Measure and log per-query latency.** *Done when: top-12 is sensible on three hand-checked queries and the latency is in the trace.* ⚠️ Ammann et al. warn their gains "rely on a strong, domain-aligned cross-encoder reranker" — yours is a 22M MiniLM, so **measure reranking's contribution separately** (`SESSION_CONTEXT.md §5.6`).
- [ ] **T-211** ⌨️ Venue tiering in `metadata_db`, from OpenAlex venue metadata. *Done when: papers carry a tier label usable as a ranking feature.*
- [ ] **T-212** 🧠 ★ **Retrieval eval against your own 25-paper bibliography** (`PROJECT_PLAN.md §5.2`). *Done when: Recall@20 is measured. **Gate: ≥ 0.80.** If it misses, spend T-213 on it — do not build agents on bad retrieval.* Use **F2, not F1**, for screening: recall matters more than precision when discarding papers (`SESSION_CONTEXT.md §5.10`).
- [ ] **T-213** 🧠 **Buffer — retrieval quality fixes only.** First escalation if recall is short: `bge-small` → `bge-base` (~109M). Bi-encoders embed once and cache, so size costs ingestion time, not per-query time. *Do not spend this buffer on features.*

---

## 5. Phase 3 — Verifier training ★ (parallel, on Kaggle, Days 2–4)

This is the graded component *and* the required training component. **Start it the moment T-001/T-002 close — it runs unattended while Phase 2 proceeds.**

- [ ] **T-301** ⌨️ Download and inspect `allenai/scifact`; build `(claim, evidence_sentence) → SUPPORT | CONTRADICT | NOT_ENOUGH_INFO` pairs. *Done when: class counts are printed and split sizes recorded.*
- [ ] **T-302** 🧠 Write the Kaggle training notebook: `microsoft/deberta-v3-small` (~44M) **warm-started from an existing NLI checkpoint, not from scratch**, three-way head, 2–3 epochs, cross-entropy. *Claude Code writes this — the warm-start detail is easy to get wrong and expensive to redo.*
- [ ] **T-303** 👤 Run it on Kaggle GPU. *Done when: held-out P/R/F1 per class is printed and the checkpoint downloaded. Expect under an hour.*
- [ ] **T-304** ⌨️ Export to **ONNX + int8 dynamic quantization** for CPU inference. *Done when: the ONNX model reproduces PyTorch logits within tolerance on 20 held-out examples.*
- [ ] **T-305** 🧠 ★ **Stock-vs-fine-tuned table** on the same held-out set. *This is the headline result that justifies the training component, and a graded deliverable in its own right.*
- [ ] **T-306** ⌨️ Measure **per-claim CPU latency** for the int8 model on this machine. *Done when: claims/sec is recorded. A run makes ~1.5–2k forward passes, so even 20/sec is a couple of minutes.*
- [ ] **T-307** 🧠 **Escalation gate.** If held-out F1 is poor, retrain `deberta-v3-base` (~184M) and quantize harder. **Trade latency, not accuracy** — the verifier is the graded thing.

---

## 6. Phase 4 — Agents and the first survey (Days 4–6: Aug 29–31) 🔴 M1

- [ ] **T-401** 🧠 `agents/base.py` — the agent ABC, the partial-state-return contract (`SPEC §14.3`), and the trace hook.
- [ ] **T-402** ⌨️ `agents/planner.py` — research question → 4–8 sub-questions + search plan, on the free-tier LLM. (`SPEC §7.1`) *Done when: a real question yields a validated plan object.*
- [ ] **T-403** ⌨️ `agents/retriever.py` — the node wrapper around Phase 2. No LLM call. (`SPEC §7.2`)
- [ ] **T-404** ⌨️ ★ `agents/extractor.py` — per paper: `methodology / advantages / disadvantages / critique`, plus `datasets`, `metrics`, `evidence_spans`. **Strict Pydantic + retry-with-repair, max 2, then `None` + `extraction_note`. Never abort a run on a parse failure.** (`SPEC §7.3`, `§14.2`) *Done when: 10 papers all produce a valid `Insight`, including at least one that needed a repair.*
- [ ] **T-405** 🧠 `graph/build.py` — wire **linearly** first: PLANNER → RETRIEVER → INGEST → RANK → EXTRACTOR → WRITER. No critic loop yet. *Done when: the graph runs start to finish on a real question.*
- [ ] **T-406** ⌨️ `agents/writer.py` — thematic synthesis with IEEE `[n]` citations. **Evidence-first: the Writer may cite only what it was given.** ALCE measured post-hoc citation attachment costing 47% of citation recall (`SESSION_CONTEXT.md §5.10`). (`SPEC §7.6`)
- [ ] **T-407** ⌨️ `output/markdown_writer.py`, `output/bibtex_writer.py`, `output/insight_table.py` (CSV). *Done when: `outputs/runs/<run_id>/` contains `review.md`, `refs.bib`, `insights.csv`, `trace.jsonl`, `config.yaml`.*
- [ ] **T-408** 🔴 **MILESTONE M1 — a complete cited literature survey from the CLI.** *The insurance policy. If everything after this collapses, there is still something to submit.* **Hard date: 2026-08-31.**
- [ ] **T-409** 🧠 Run the **flagship query** — the system surveys *its own topic*, agentic RAG for automated literature review. The 25-paper bibliography is the answer key. Keep the output: after a human edit pass it becomes the report's literature-survey chapter (T-807).

---

## 7. Phase 5 — Verification and the critic loop ★ (Days 7–8: Sep 1–2)

The centrepiece. Objective 2 lives here.

- [ ] **T-501** ⌨️ ★ `agents/verifier.py` part 1 — atomic claim decomposition from the drafted text. *Done when: a 20-sentence draft yields a list of atomic claims, each with a source-sentence pointer.*
- [ ] **T-502** ⌨️ ★ ONNX runtime wrapper: `(claim, evidence_span) → softmax`. *Done when: it runs on CPU at the T-306 measured rate.*
- [ ] **T-503** 🧠 ★ Verdict mapping and thresholds per `PROJECT_PLAN.md §4.2`: `SUPPORT` high-confidence → `SUPPORTED`; `SUPPORT` low-confidence → `PARTIAL`; `NOT_ENOUGH_INFO` → `UNSUPPORTED`; `CONTRADICT` → `CONTRADICTED`. `support_score` = softmax probability, threshold 0.7. **Weight the `SUPPORTED` threshold toward precision** — CliVER measured a 21% false-Support rate, and over-predicting "supported" is the dangerous direction for a hallucination-graded project (`SESSION_CONTEXT.md §5.10`).
- [ ] **T-504** ⌨️ ★ Unsupported-claim **dropping**, drop-logging to `trace.jsonl`, and `contradiction_pairs`. *Done when: a run reports "N claims dropped" and every drop is inspectable in the trace.*
- [ ] **T-505** 🧠 **Apply the abstract-only rule.** Papers with `text_availability == abstract_only` **may be cited as existing but may not supply verified claims.** Li et al. measured abstract-conditioned faithfulness at 0.745 against 0.94–0.96 for full context — abstract-conditioned models "learn to hallucinate" (`SESSION_CONTEXT.md §5.7`).
- [ ] **T-506** ⌨️ `agents/critic.py` — coverage / grounding / paper-count gates → `RETRIEVE | REPLAN | WRITE`. (`SPEC §7.5`)
- [ ] **T-507** 🧠 `graph/routing.py` — conditional edges, **hard `max_iterations=3`, forced WRITE on the final iteration, mandatory plan-diff on replan.** *Done when: the loop demonstrably fires on an under-covered query **and terminates**.*
- [ ] **T-508** ⌨️ `graph/checkpoint.py` — SQLite checkpointer so a run can resume.
- [ ] **T-509** 🔴 **MILESTONE M2 — the full six-agent graph runs with the loop firing and terminating.**

---

## 8. Phase 6 — API and the Vue app (Days 8–9: Sep 2–3)

Grading is weighted to the system visibly working. Build the panels in order; **1–3 alone are a strong demo.**

- [ ] **T-601** ⌨️ `api/app.py` + `api/schemas.py` — the five endpoints from `PROJECT_PLAN.md §7.2`. *Done when: all five respond.*
- [ ] **T-602** ⌨️ SSE progress stream — one event per agent transition, carrying iteration count and the Critic's decision.
- [ ] **T-603** 🧠 ★ **Record a fixture run** (result JSON + SSE event log to disk) and add a `--fixture` flag. *This decouples all frontend work from backend readiness and costs zero API calls. It saves a full day. Do it before writing any Vue.*
- [ ] **T-604** ⌨️ Vue 3 + Vite scaffold, Composition API, scoped CSS, **no Pinia** (one page, one run — a store is ceremony).
- [ ] **T-605** ⌨️ **Panel 1** — query input, `max_papers`, run button.
- [ ] **T-606** ⌨️ **Panel 2** — live agent progress: the six agents lighting up as SSE events arrive, showing iteration count and Critic decisions. *Makes the "agentic" claim visible in the first thirty seconds.*
- [ ] **T-607** ⌨️ ★ **Panel 3 — evidence inspection.** Rendered review; **click any sentence → see its supporting evidence span and source paper.** *The money shot: direct visual proof of the anti-hallucination claim. If one panel survives, it is this one.*
- [ ] **T-608** ⌨️ **Panel 4 — dropped-claims panel** plus artefact downloads. *"14 claims were removed as unsupported."* Showing what the system **refused** to say is more persuasive than showing what it said.
- [ ] **T-609** ⌨️ **Human-in-the-loop control** — confirm/override on dropped claims, written back to the trace. *Only if T-007 keeps HITL in Objective 2. ~half a day on top of Panel 4.*
- [ ] **T-610** 🧠 **Pre-bake the showcase run.** A 60-paper run is 20–40 minutes on CPU against a rate-limited API — far too slow to run live in front of an examiner. Ship a completed run that replays instantly via `GET /api/runs`, and demo *live* execution only at `max_papers=10`. **Decide this now, not the night before.**

---

## 9. Phase 7 — Evaluation (Days 9–10: Sep 3–4)

- [ ] **T-701** ⌨️ `eval/metrics.py` — citation accuracy (every `[n]` resolves to a real DOI in the metadata DB), groundedness, coverage, **claims dropped per run**, latency, request count. All computed from `trace.jsonl`.
- [ ] **T-702** 🧠 ★ **Ablation 2 (− Verifier).** **Run this first, before any other ablation.** It quantifies hallucination with and without the filter — precisely the graded property. `max_papers=25`, launched overnight.
- [ ] **T-703** 🧠 Ablation 1 (full system) at `max_papers=25` for comparison.
- [ ] **T-704** 🧠 ★ **Hallucination stress test.** Deliberately query a topic the corpus does not cover and show the system **refuses rather than invents**: claims dropped, Critic reports the coverage gap, output carries an explicit Limitations section instead of fabricated content. Two hours of work, and the most convincing possible answer to *"how do I know it isn't making things up?"* Wire the result into Panel 4 so it is demoable, not merely reportable.
- [ ] **T-705** 👤 ★ **50-claim verifier spot-check** on real output. *This is the non-circular evidence. Groundedness measured by the system that enforces groundedness proves only that the filter ran (`PROJECT_PLAN.md §9.6`).*
- [ ] **T-706** 🧠 Ablations 3 (− Critic loop) and 4 (vanilla RAG ≈ base-paper configuration) — **only if time remains.** Use Ammann et al.'s configuration as a stronger ablation-4 baseline than vanilla RAG (`SESSION_CONTEXT.md §5.6`).
- [ ] **T-707** 🧠 **Revise the target numbers downward before writing any results.** `PROJECT_PLAN.md §9` targets groundedness ≥ 0.9. Nothing peer-reviewed reaches that on realistic scientific verification — Sarol et al. 0.59 micro-F1, CliVER 0.797 against clinicians, SurveyGen 35.84% citation accuracy, SciReviewGen ~30% of chapters at human quality. **If the verifier reports 0.9+ against real citations, suspect the measurement, not a breakthrough** (`SESSION_CONTEXT.md §5.2`).

---

## 10. Phase 8 — Documents, deck, submission (Days 10–11: Sep 4–5)

- [ ] **T-801** 🧠 ⛔ **Correct `RESEARCHGPT_SPEC.md`** per `SESSION_CONTEXT.md §7.1`. Specifically §1.2 (the base paper is mis-described — its actual title is *"A synergistic multi-stage RAG architecture for boosting context relevance in data science literature"*) and §1.3 (the *"fixed single-pass pipeline"* claim is **factually wrong**; Aytar et al. is explicitly multi-stage). **That row is the foundation of the "we are more agentic" argument, and an examiner who reads the base paper will find it.** The honest contrast is *static multi-stage vs. dynamic agentic control with verification.*
- [ ] **T-802** 🧠 Update `SPEC §3` (architecture diagram → the draw.io file), `§4` (relabel it "Package Dependency Map" and add the real MCD), `§7.5` (add HITL to the Critic), `§9` (revised targets from T-707).
- [ ] **T-803** 🧠 Report — **Introduction**: lead with the four independent measurements of the same failure (Sarol 39.18% of citation instances contain accuracy errors; ALCE, best models "lack complete citation support 50% of the time"; FActScore, ChatGPT factually correct on 58% of atomic claims; SurveyGen 35.84%). Then FActScore's killer statistic: **36.0% of supported and 37.6% of unsupported sentences carried citations — statistically indistinguishable.** The presence of a citation carries almost no information; that is the justification for claim-level verification.
- [ ] **T-804** 🧠 Report — **Related Work**: quote Ammann et al.'s own Limitations item 6 verbatim (*"Lack of iterative retrieval. Our pipeline operates in a single-shot manner... This limits its ability to support adaptive multi-step reasoning."*) — your closest competitor names your contribution as its own limitation. Use SciReviewGen's limitations list as a requirements table (`SESSION_CONTEXT.md §5.9`).
- [ ] **T-805** 🧠 Report — **Discussion**: Valsci Table 3 — GPT-4o-mini *inside* their architecture scores F1 0.720; bare GPT-4o scores 0.706. **Architecture beats model scale, measured.** This converts the $0 constraint from an apology into a hypothesis: *the architecture is a correctness filter, not a correctness source.*
- [ ] **T-806** 🧠 Report — **Limitations**, written honestly: SciFact's biomedical skew against a CS corpus (domain shift), human κ of 0.18–0.42 on exactly the thing you measure, retrieval recall as a hard ceiling on verification, and the abstract-only paper split. *Naming a limitation is stronger than hiding it.*
- [ ] **T-807** 🧠 Report — literature-survey chapter: **hand-edit the T-409 generated survey.** One flagship run yields both the automated artefact and a human-checked chapter.
- [ ] **T-808** 👤 **Fix the two visible errors in `Review-1 dsc06.pptx`** if that deck is shown again: slide 6 says *"GPU: 8GB Minimum"* on a CPU-only machine, and slide 8 says *"Extractor chunks and embeds them"* — that is the Ingestor's job, and as written the system has **no structured extraction at all**, which deletes a main contribution.
- [ ] **T-809** 👤 Final deck: swap in real screenshots, the stock-vs-tuned table (T-305), the ablation-2 numbers (T-702), and the dropped-claims count.
- [ ] **T-810** ⌨️ `README.md` + `make reproduce` — one command that regenerates a run from a cached config. *Reproducibility is `SPEC §14.10`, and it is cheap.*
- [ ] **T-811** 👤 **Obtain the PDF of Li et al., *Information Processing & Management*** (DOI `10.1016/j.ipm.2025.104369`) through the library. ScienceDirect returns HTTP 403 to automated access, so it is the one paper in the set written from its title alone. *"Evidence-aware" + "self-corrective" describes your Verifier and Critic — **it may be a competitor to differentiate from, not a supporting citation.*** Also resolve its year (OpenAlex says 2025, Semantic Scholar 2026) before it enters the reference list.
- [ ] **T-812** 👤 Verify **Vicinagearth** (paper C3-11) is Scopus-indexed. If not, substitute Wang et al. 2024, *Frontiers of Computer Science*, DOI `10.1007/s11704-024-40231-1`.
- [ ] **T-813** 🧠 **Re-verify every DOI** before submission. Indexes and publication years change.

---

## 11. Cross-cutting — continuous, not a phase

- [ ] **T-901** ⌨️ Unit tests alongside each module. Cursor writes the test in the same prompt as the module; the acceptance criterion *is* the test.
- [ ] **T-902** 🧠 Review every Cursor diff before commit. Assume hallucinated imports until proven otherwise.
- [ ] **T-903** 🧠 Commit at every completed task. `git log` is the project timeline evidence.
- [ ] **T-904** 🧠 Keep the `trace.jsonl` schema stable from T-107 onward. Every report figure depends on it.

---

## 12. Critical path

Only these gate M2. Everything else can slip.

```
T-001/002 ─▶ T-104 (llm.py + cache) ─▶ T-201..210 (retrieval) ─▶ T-212 (recall gate ≥ 0.80)
                                                                        │
T-301 ─▶ T-302 ─▶ T-303 (Kaggle) ─▶ T-304 (ONNX int8) ──────────┐      │
        (parallel, unattended)                                    │      ▼
                                                                  │  T-402..407 ─▶ 🔴 M1 (Aug 31)
                                                                  │                    │
                                                                  └──────▶ T-501..507 ─┴─▶ 🔴 M2 (Sep 2)
                                                                                          │
                                                                            T-603 (fixture) ─▶ T-607 (Panel 3)
                                                                                          │
                                                                                     T-702 (Ablation 2)
```

---

## 13. Kill switches — decide these on the date, not in hindsight

| Date | If this has not happened | Do this |
|---|---|---|
| **Aug 28** | Recall@20 < 0.80 | Escalate `bge-small` → `bge-base`. Spend all of Aug 29 on retrieval. Push M1 to Sep 1. |
| **Aug 29** | Kaggle verifier not trained | Fall back to a **stock** NLI checkpoint in the pipeline and report stock-vs-tuned as future work. The pipeline must never block on training. |
| **Aug 31** | M1 not landed | **Stop building forward.** Stabilise the linear pipeline, ship the survey, cut the Critic loop to a single pass. |
| **Sep 2** | M2 not landed | Ship the five-agent system without the Critic loop. **The Verifier stays** — it is the graded component; the loop is not. |
| **Sep 3** | Vue not started | Ship Panels 1–3 against the fixture only. Skip Panel 4 and HITL; fold the dropped-claims count into Panel 3 as a summary line. |
| **Sep 4** | Ablations not run | Ship ablation 2 alone. It is the graded claim. Report the rest as future work. |

---

## 14. Open items only you can close

Carried forward from `SESSION_CONTEXT.md §8`, plus new ones. All appear in Phase 0 or Phase 8 above; repeated here so none is lost:

1. **T-005** — confirm the base-paper switch with your guide. ⬅ *the most valuable ten minutes left*
2. **T-006** — confirm which MCD notation the rubric means.
3. **T-007** — decide whether HITL stays in Objective 2.
4. **T-811** — obtain the Li et al. IPM PDF and resolve its publication year.
5. **T-812** — verify *Vicinagearth* is Scopus-indexed.
6. **T-705** — the 50-claim spot-check. Nobody else can do it, and it is the only non-circular evidence you will have.

---

*Derived from `PROJECT_PLAN.md` (rev 3), `RESEARCHGPT_SPEC.md`, `SESSION_CONTEXT.md`, `ARCHITECTURE_REVIEW.md`, `LITERATURE_REVIEW.md`, `PAPER_DEEP_DIVE.md`, and the 2026-08-09 and 2026-08-20 sessions. Amend in place.*
