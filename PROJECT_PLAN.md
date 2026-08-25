# ResearchGPT — Execution Plan (30-Day Delivery, Zero-Cost, CPU-Only)

> **What this file is.** The delivery companion to `RESEARCHGPT_SPEC.md`. The spec says *what the ideal system is*. This file says *what we actually build in one month*, at zero API cost, on CPU-only hardware, with a Vue frontend.
>
> **Where they conflict, this file wins on scope; the spec wins on design.**
>
> **Revision 3 (2026-08-06).** Changes from revision 2: **Vue.js frontend is mandatory** → Streamlit is out, FastAPI is back in (§7). **Development machine is CPU-only** → every local model is resized and the Ollama fallback is demoted (§4.2, §6.3, §11). Remaining open questions are **closed by decision** (§12) — no further input needed to start.

---

## 1. Executive summary

Four constraints drive everything: **zero API spend**, **CPU-only local hardware**, **grading on working behaviour and factual accuracy**, and **a required training component**. Plus one stack mandate: **Vue.js frontend, backend free choice**.

These fit together better than they look:

- **The Verifier is the centrepiece, not the Critic.** The grading criterion is "does not hallucinate" — the Verifier *is* the hallucination filter. It gets the most time, an independent evaluation, and the most visible position in the UI.
- **The trained component is the claim verifier** — a small NLI cross-encoder fine-tuned on SciFact, trained on Kaggle GPU, exported to ONNX int8 and run locally on CPU (§4). It satisfies the training requirement and the accuracy requirement at once.
- **Zero cost works because most inference leaves the API.** Embeddings, reranking and verification all run locally. Only four generative agents call a hosted free tier, and only one of those scales with paper count (§6).
- **CPU-only is survivable, but it sets the model sizes.** Every local model is picked for CPU inference speed, not peak quality (§6.1). The one place this bites is demo latency — solved by pre-baking a run (§7.3).
- **A weak free model is the paper's story, not its apology.** The architecture is a correctness *filter*. Showing that verification lets a small free model produce grounded output is a stronger result than "a frontier model worked."
- **Demoable end-to-end system by Day 12**, before the Verifier and Critic are finished. That is the insurance policy if weeks 3–4 slip.

**Flagship run:** the system generates a literature survey on *its own topic* — agentic RAG for automated literature review. Your existing 25-paper review (spec §1.5) is then a defensible gold set, and the generated survey becomes the literature-survey chapter of your report after a manual review pass. A system that writes its own related-work section is the best single thing you can put in front of an examiner.

---

## 2. Scope decisions

### 2.1 Keep (load-bearing)

| Component | Why it survives |
|---|---|
| All six agents | The architecture *is* the contribution. |
| **Verifier + claim→span grounding** | **The graded criterion. Highest-priority component.** |
| **Trained NLI claim verifier (§4)** | Satisfies training requirement *and* accuracy requirement together. |
| LangGraph conditional edges + bounded loop | Clearest differentiator vs. the base paper. |
| 4-field insight schema + strict Pydantic | Cheap, and directly determines summary accuracy. |
| Hybrid retrieval (dense + BM25 + RRF + rerank) | Bad retrieval → bad grounding → failed grading criterion. |
| **Vue SPA + FastAPI, with evidence inspection** | Mandated stack; grading is weighted to working behaviour. |
| Trace logging (`trace.jsonl`) | Free on Day 1, impossible to retrofit. Every figure comes from it. |
| Markdown + BibTeX + CSV output | Hours of work; examiners judge artefacts they can open. |

### 2.2 Cut

| Spec item | Decision | Rationale |
|---|---|---|
| 10 source connectors | **Cut to 2: OpenAlex + arXiv** | OpenAlex covers metadata, venue, citations, OA links. Crossref redundant; S2 rate-limited; IEEE/Scopus need institutional keys. |
| GROBID | **Cut** | Docker service, hours of setup, marginal gain over PyMuPDF + a section-header regex. |
| Qdrant | **Cut** | ~3k vectors. Chroma is not the bottleneck. Closes spec §16. |
| ~~FastAPI~~ | **RESTORED** | Required as the Vue backend. Reversal of revision 1. |
| vcrpy cassettes | **Cut → JSON response cache** | Prompt-hash-keyed dict on disk, ~20 lines. Now essential for rate-limit conservation, not just determinism. |
| RAGAS | **Cut entirely** | Needs API calls the free-tier budget cannot spare. |
| `bge-large-en-v1.5` | **→ `bge-small-en-v1.5`** | CPU-only. See §6.1. |
| `bge-reranker-v2-m3` (568M) | **→ MiniLM cross-encoder (~22M)** | CPU-only. 568M cross-encoder scoring is too slow per query. |
| 3 annotators / Krippendorff's α | **→ 2 annotators / Cohen's κ** | Scheduling problem, not a technical one. |
| Extraction F1 vs 20 papers | **→ 10 papers** | State the sample size honestly. |
| 7 ablations | **→ 4** (§9.4) | Rate limits make each run expensive in wall clock. |
| §4.3 reranker fine-tune | **Cut** (was optional) | The Vue frontend consumes the days this would have used. The verifier already satisfies the training requirement. |
| DOCX output | **Demoted to Week 4 filler** | Markdown + PDF-from-Markdown suffices if time is short. |
| Notebooks | **Cut** | Kaggle notebooks for training only. |

---

## 3. Architecture

Full detail in `RESEARCHGPT_SPEC.md` §3–§9. What gets built, annotated with **where each piece runs**:

```
                       ┌──────────────────────────────┐
                       │  Vue 3 SPA (Vite)            │
                       │  query · live progress ·     │
                       │  evidence inspector ·        │
                       │  dropped-claims panel        │
                       └──────────────┬───────────────┘
                            REST + SSE│
                       ┌──────────────┴───────────────┐
                       │  FastAPI  (thin wrapper)     │
                       └──────────────┬───────────────┘
                                      │
research_question ────────────────────┘
      │
      ▼
  [Planner]     ── free-tier hosted LLM ── 4–8 sub-questions + search plan
      │
      ▼
  [Retriever]   ── LOCAL CPU, no LLM ── OpenAlex + arXiv → DOI dedup → OA PDF fetch
      │             → PyMuPDF parse → chunk (1200/200) → bge-small embed
      │             → Chroma dense k=30 + BM25 k=30 → RRF → MiniLM rerank → top-12
      ▼
  [Extractor]   ── free-tier hosted LLM ── per paper: methodology / advantages /
      │             disadvantages / critique + datasets, metrics, evidence_spans
      ▼
  [Verifier]    ── LOCAL CPU, FINE-TUNED NLI (ONNX int8) ── ★ graded component ★
      │             atomic claims → evidence → SUPPORTED / PARTIAL /
      │             UNSUPPORTED / CONTRADICTED + support_score
      │             → unsupported claims DROPPED, logged, surfaced in the UI
      ▼
  [Critic]      ── free-tier hosted LLM ── coverage / grounding / paper-count gates
      │             ├── RETRIEVE ──┐
      │             ├── REPLAN ────┼── max 3 iterations, forced WRITE on the last
      │             └── WRITE ─────┘
      ▼
  [Writer]      ── free-tier hosted LLM ── thematic synthesis, IEEE [n] citations
      │
      ▼
outputs/runs/<run_id>/{review.md, insights.csv, refs.bib, trace.jsonl, config.yaml}
```

**Key consequence of $0 + CPU-only:** the three highest-volume operations — embedding, reranking, verification — never touch an API and never need a GPU. Only four generative calls per run scale with the corpus, and only the Extractor is per-paper. That is what makes free-tier rate limits survivable.

---

## 4. Model training — CONFIRMED IN SCOPE

### 4.1 What the spec has: nothing

`RESEARCHGPT_SPEC.md` is entirely inference-only — LLMs prompted through LiteLLM, `bge-*` models frozen. No loss function, no gradient step. The component below is an **addition to the spec**.

### 4.2 Training target: the claim verifier (NLI cross-encoder)

**Why this and not the reranker:**

1. **It sits on the graded critical path.** You are graded on "does not hallucinate." The verifier *is* that mechanism. Training it aligns the trained component with the project's purpose.
2. **No access lead time.** SciFact downloads straight from Hugging Face. The reranker route depends on SciReviewGen → S2ORC, which may need a multi-day access request.
3. **It is fast to train.** SciFact is small (~1.4k expert-written claims with sentence-level evidence over ~5k abstracts). Well under an hour on a Kaggle P100.
4. **It removes API load.** An LLM verifier would cost one call per atomic claim — hundreds per run, straight into the rate limit. A local cross-encoder does it free, deterministically, in milliseconds.

**Recipe:**

| Item | Choice |
|---|---|
| Base model | `microsoft/deberta-v3-small` (~44M backbone) — chosen for **CPU inference**, not peak accuracy. Warm-start from an existing NLI checkpoint (e.g. a `nli-deberta-v3-*` model) rather than from scratch |
| Task | 3-way: `(claim, evidence_sentence) → SUPPORT / CONTRADICT / NOT_ENOUGH_INFO` |
| Data | **SciFact** (`allenai/scifact`) |
| Hardware | Kaggle GPU (P100 / 2×T4), free weekly quota — training only |
| Training | 2–3 epochs, cross-entropy, < 1 hour |
| **Deployment** | **Export to ONNX, int8 dynamic quantization, run on local CPU.** Typically 2–4× faster than raw PyTorch CPU with negligible accuracy loss |
| Mapping to spec verdicts | `SUPPORT` high-confidence → `SUPPORTED`; `SUPPORT` low-confidence → `PARTIAL`; `NOT_ENOUGH_INFO` → `UNSUPPORTED`; `CONTRADICT` → `CONTRADICTED`. Softmax probability becomes `support_score ∈ [0,1]`, threshold 0.7 per spec §7.4 |
| Evaluation | SciFact held-out P/R/F1 per class, **plus stock-vs-tuned** — the comparison that justifies the training |
| Deliverable | ONNX checkpoint + confusion matrix + stock-vs-tuned table + latency measurement on your CPU |

**Escalation rule:** if `deberta-v3-small` scores poorly on SciFact held-out, train `deberta-v3-base` (~184M) instead and quantize harder. Verifier *quality* is the graded thing — if you must trade, trade latency, not accuracy. Measure per-claim CPU latency before deciding; a run makes roughly 1.5–2k forward passes, so even 20 passes/sec is a couple of minutes.

---

## 5. Datasets

### 5.1 SciFact — verifier training data ★ (primary dependency)

Expert-written scientific claims with sentence-level evidence labels over abstracts. Available directly from Hugging Face (`allenai/scifact`) — **no access request, no lead time.** Confirm licence terms on the dataset card. Provides both the training set and the held-out evaluation for §9.1.

### 5.2 Your own 25-paper review — the primary gold set ★

Spec §1.5: a 25-paper survey in six clusters plus a 10-paper IEEE addendum, DOI-verified. **Domain-matched, free, and defensible in a viva because you can justify every gold label yourself.** Since the flagship run surveys this project's own topic, this bibliography is exactly the right answer key. Standing end-to-end test from Day 5 onward.

### 5.3 SciReviewGen — retrieval benchmark (optional, access-gated)

Kasanishi et al., Findings of ACL 2023 — [arXiv:2305.15186](https://arxiv.org/abs/2305.15186) · [github.com/tetsu9923/SciReviewGen](https://github.com/tetsu9923/SciReviewGen). >10,000 reviews, ~690,000 cited papers, from S2ORC (2020-07-05). **CC BY-NC 4.0**, non-commercial only.

Two remaining uses now that the reranker fine-tune is cut: (a) retrieval gold sets at scale — chapter topic → query, cited papers → gold set; (b) `bib_citing_sentences` as human-authored claim→paper pairs for an **independent** verifier cross-check (§9.6). Not a live retrieval source (frozen mid-2020) and no 4-field labels.

**Access:** distributed as preprocessing scripts over S2ORC, historically requiring an AI2 access request with days of latency. Check for a preprocessed mirror first; file the request on Day 1 if none. **Nothing critical depends on this** — it is a bonus, and §5.2 covers the same need.

### 5.4 Hand-annotated extraction set

10 papers × 4 fields, annotated by you in Week 4, for Extraction F1. Sample from §5.2 — you already know those papers.

### 5.5 Live retrieval corpus

OpenAlex + arXiv, fetched per run. Only OA PDFs stored locally (spec §14.9).

---

## 6. Zero-cost, CPU-only model strategy

### 6.1 Local models — sized for CPU

| Function | Model | Size | Notes |
|---|---|---|---|
| Embeddings | `BAAI/bge-small-en-v1.5` | ~33M | Downgraded from `bge-large`. ~3k chunks embeds in a couple of minutes on CPU. Modest retrieval loss at this corpus size |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | ~22M | Downgraded from `bge-reranker-v2-m3` (568M). Cross-encoders score every (query, doc) pair, so size hurts far more here than in the bi-encoder |
| **Claim verification** | **fine-tuned `deberta-v3-small`, ONNX int8** | **~44M** | §4.2. The graded component |
| PDF parsing | PyMuPDF | — | CPU-native, fast |

**Rule:** every local model is chosen for CPU throughput. If retrieval quality measures poorly on Day 5, escalate the *embedding* model first (`bge-base`, ~109M) — bi-encoders embed once and cache, so size costs you ingestion time only, not per-query time.

### 6.2 Free-tier hosted API — the four generative agents

**Decision (you asked me to choose): commit to Google AI Studio's Gemini free tier as primary, with Groq registered as a backup on Day 1.** Rationale: reliable structured JSON output (the property that actually matters — the Extractor's 4-field schema must parse), a large context window for the Writer's cross-chunk synthesis, and generous free limits. Groq as backup because it is fast and its free tier is separately administered, so both failing at once is unlikely.

**Verify current limits and terms on Day 1** — free tiers change, and some train on free-tier inputs. For an academic project over public papers that is normally fine, but check it against your institution's rules. Spend thirty minutes running the Extractor prompt against both and pick on **JSON-parse reliability, not benchmark scores**.

**Mandatory engineering around the rate limit — all on Day 1:**

- **Response cache** keyed by prompt hash → disk. Development re-runs then cost zero requests. **The single highest-leverage thing in the entire build.**
- **Exponential backoff + retry** on 429s, plus a requests-per-minute throttle in `core/llm.py`.
- **Rate-limit guardrail** replacing the spec's `max_cost_usd` (§14.8): abort with a clear error on sustained 429s rather than looping silently.
- **`max_papers=25` for ablation runs.** Ablations compare configurations; 25 papers compares them just as validly as 60, at 40% of the request budget.

### 6.3 Ollama fallback — demoted to a footnote

On a CPU-only machine a 7B model runs at roughly 3–8 tokens/sec, which makes a full run take hours. **It is not a viable working path and should not be planned around.** Real redundancy comes from having *two free tiers* registered (§6.2), and LiteLLM makes switching a config change.

If you want the offline-operation ablation row anyway, run it at `max_papers=5` purely to report a number, and label it a feasibility probe rather than a comparison. Only if Week 4 has slack.

### 6.4 The narrative

Do not apologise for the free model in the write-up. Frame it as the finding:

> *The architecture is a correctness filter, not a correctness source. We show that claim-level verification lets a small, freely-available model produce grounded review output, decoupling review quality from model scale.*

Directly supported by ablation 2 (− Verifier).

---

## 7. Frontend and backend

### 7.1 Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | **Vue 3 + Vite**, Composition API, plain scoped CSS | Mandated. Vite for zero-config dev server and instant HMR |
| State | Component-local `ref`/`reactive` — **no Pinia** | One page, one run. A store is ceremony you do not need |
| Styling | Scoped CSS, or Tailwind if you already know it | Do not learn a component library this month |
| Backend | **FastAPI** | Same language as the pipeline, so it wraps the compiled LangGraph in-process. No serialisation boundary, no second runtime |
| Transport | **REST + Server-Sent Events** | SSE for one-way progress streaming. Simpler than WebSockets and enough for this |

### 7.2 API surface — deliberately tiny

```
POST   /api/review                    → { run_id }        start a run
GET    /api/runs/{id}/events          → SSE stream        live agent progress
GET    /api/runs/{id}/result          → full result JSON  review + evidence map + dropped claims
GET    /api/runs/{id}/artifact/{name} → file download     review.md · insights.csv · refs.bib
GET    /api/runs                      → [ run summaries ] for replaying pre-baked runs
```

Five endpoints. Roughly half a day including the SSE plumbing.

### 7.3 The Vue app — one page, four panels

Build in this priority order; if time runs out, panels 1–3 alone are a strong demo:

1. **Query input** — question, `max_papers`, run button.
2. **Live agent progress** — the six agents as a pipeline, lighting up as SSE events arrive, showing iteration count and Critic decisions. *Makes the "agentic" claim visible in the first thirty seconds.*
3. **Review output with evidence inspection** — rendered review; **click any sentence → see its supporting evidence span and source paper.** ★ The money shot. Direct visual proof of the anti-hallucination claim.
4. **Dropped-claims panel** — *"14 claims were removed as unsupported."* Showing what the system **refused** to say is more persuasive than showing what it said. Plus artefact download buttons.

**Two things that will save you a full day each:**

- **Build the frontend against a recorded fixture.** Save one completed run's result JSON and SSE event log to disk, serve them from a `--fixture` flag, and develop the whole UI with no live pipeline and zero API calls. Decouples frontend work from backend readiness entirely.
- **Pre-bake the demo run.** A full 60-paper run is roughly 20–40 minutes on CPU-only hardware with a rate-limited API — far too slow to run live in front of an examiner. Ship a completed run that replays instantly via `GET /api/runs`, and demo *live* execution only at `max_papers=10`. Decide this now, not the night before.

---

## 8. Build timeline — 30 days

Critical checkpoint is **Day 12**, not Day 30.

### Week 1 (Days 1–7) — Foundation and retrieval

| Day | Work | Done when |
|---|---|---|
| 1 | `git init`. Scaffold, `pyproject.toml`, config loader, `core/llm.py` **with cache + throttle + backoff from the start**, `core/models.py`, trace logger, CLI stub. Register **two** free tiers, test both on the Extractor prompt. **Download SciFact.** Check for a SciReviewGen mirror | `researchgpt --version` runs; adapter returns a completion; cache hits on re-run |
| 2–3 | OpenAlex + arXiv connectors, DOI dedup, OA PDF fetch, PyMuPDF parse, section-aware chunker, Chroma + BM25, `bge-small` embeddings on CPU | Query returns ranked chunks with correct span offsets |
| 4 | RRF fusion, MiniLM reranker on CPU, venue tiering | Sensible top-12; per-query rerank latency measured |
| 5 | Retrieval eval against **your own 25-paper bibliography** (§5.2) | Recall@20 measured; spec Phase 2 gate ≥ 0.8 |
| 6–7 | **Buffer.** Retrieval quality fixes | Retrieval is trustworthy |

> Do not skip Days 6–7. Bad retrieval silently poisons grounding — the graded criterion — and is hardest to debug once six agents sit on top of it.

### Week 2 (Days 8–14) — Agents, first output, verifier training

| Day | Work | Done when |
|---|---|---|
| 8–9 | Planner + Retriever nodes; LangGraph wired **linearly** | Graph runs start to finish |
| 10–11 | Extractor: 4-field schema, strict Pydantic, retry-with-repair (max 2). **In parallel: train the NLI verifier on Kaggle** — unattended, then export ONNX int8 | Structured insights for every paper; quantized checkpoint on disk with measured CPU latency |
| 12 | Writer: thematic synthesis, IEEE citations, `review.md` | **🔴 MILESTONE: first complete cited survey. The submittable fallback exists.** |
| 13–14 | Verifier part 1: claim decomposition, wire in the ONNX model, support scoring | Claims classified end to end |

### Week 3 (Days 15–21) — Verification, loop, and the app

| Day | Work | Done when |
|---|---|---|
| 15 | Verifier part 2: unsupported-claim filtering, dropped-claim logging, contradiction pairs. Plus CSV + BibTeX writers (~2 h) | Groundedness ≥ 0.9 on a sample; drops visible in the trace |
| 16–17 | Critic + conditional edges + checkpointing + iteration cap | Loop demonstrably fires **and terminates** on an under-covered query |
| 18 | FastAPI wrapper + SSE progress + artifact endpoints. **Save a fixture run.** Hallucination stress test (§9.5) | API serves a completed run; fixture replays |
| 19–20 | Vue 3 app, panels 1–4, developed against the fixture | Demo drivable in the browser with evidence inspection |
| 21 | Buffer / demo polish / pre-bake the showcase run | — |

### Week 4 (Days 22–30) — Evaluation and report

| Day | Work |
|---|---|
| 22–23 | `eval/metrics.py` + ablation runner at `max_papers=25`. **Launch sweep overnight** |
| 24 | Verifier spot-check (50 claims) + 10-paper extraction annotation + 2-annotator Likert |
| 25–28 | Write the report: figures from real traces, results tables, limitations. **Manually review and edit the generated survey**, then use it as the literature-survey chapter |
| 29–30 | Buffer, `make reproduce`, DOCX writer if time permits, final polish, submission |

---

## 9. Evaluation design

Reweighted for the grading criterion: **verifier quality and factual accuracy first; the ablation table is supporting evidence.**

### 9.1 Verifier evaluation ★ highest priority

| Metric | Source | Why it matters |
|---|---|---|
| P/R/F1 per class | SciFact held-out | Does the trained model detect unsupported claims? |
| **Stock vs. fine-tuned** | Same test set | Justifies the training component — the headline training result |
| **Verifier precision on real output** | 50 hand-checked claims from a live run | Does it work on *your* domain, not just SciFact? |
| Agreement with human authors | SciReviewGen `bib_citing_sentences`, if available | Independent, non-circular check |
| CPU latency per claim | Local measurement | Justifies the ONNX/quantization choices |

### 9.2 Retrieval metrics

Against your own bibliography (§5.2), and SciReviewGen if access lands: Recall@20 ≥ 0.80, Precision@k ≥ 0.70, nDCG@10 reported.

### 9.3 Automated grounding and citation metrics

| Metric | How computed |
|---|---|
| Citation accuracy | Every `[n]` resolves to a real DOI in the metadata DB — fully automatable |
| Groundedness | Fraction of output sentences with ≥1 supporting span |
| Coverage | Sub-questions with ≥2 supporting papers |
| **Claims dropped per run** | From `trace.jsonl` — **the real measure of what the architecture buys** |
| Latency / request count | From `trace.jsonl` |

### 9.4 Ablations — 4 configurations

| # | Configuration | Isolates |
|---|---|---|
| 1 | Full system | — |
| 2 | **− Verifier (no grounding filter)** | **The graded claim. Run this first.** |
| 3 | − Critic loop (single pass) | Value of the feedback loop |
| 4 | Vanilla RAG ≈ base-paper configuration | Value of the whole architecture |

*(+ optional: stock vs. tuned verifier; local Ollama feasibility probe at `max_papers=5`.)*

Ablation 2 quantifies hallucination with and without the filter — precisely the graded property. Run all four at `max_papers=25`.

### 9.5 Hallucination stress test — build this, it demos well

Deliberately query a topic the corpus does not cover, and show the system **refuses rather than invents**: claims get dropped, the Critic reports the coverage gap, and the output carries an explicit Limitations section instead of fabricated content. Two hours of work, and it is the most convincing possible answer to *"how do I know it isn't making things up?"* Wire the result into the Vue dropped-claims panel so it is demoable, not just reportable.

### 9.6 Two credibility traps to defuse

1. **The groundedness metric is circular.** The system enforces groundedness, then measures it. "Groundedness = 0.98" proves only that the filter ran. **Fix:** report it as measured *independently* — the 50-claim human spot-check and the SciReviewGen citing-sentence cross-check — never solely by the Verifier's own output.

2. **"Hallucination rate: 0 by construction" (spec §12) is unfalsifiable.** **Fix:** report falsifiable numbers instead — claims caught and dropped per run, verifier precision from the spot-check, and ablation 2's with/without comparison. Together they tell a reader both *what the filter removed* and *whether the filter can be trusted*.

---

## 10. Descope ladder

Grading favours working behaviour over paper artefacts, so the app outranks the eval table. Cut top-down:

1. **SciReviewGen integration entirely** — fall back to your own bibliography (§5.2) as the sole gold set.
2. **Ollama feasibility probe.**
3. **DOCX output** — Markdown suffices.
4. **2-annotator Likert study** — the verifier spot-check matters more and is faster.
5. **Vue panel 4** (dropped claims) — fold the count into panel 3 as a summary line.
6. **Ablations 3 and 4** — keep ablation 2 at all costs; it is the graded claim.
7. **Extraction F1 annotation** — report qualitative examples instead.

**Never cut:** the six agents, the trained verifier, the evidence-inspection panel, ablation 2, the trace log, or the Day 12 milestone. Those six are the project.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| **Free-tier rate limit throttles development** | Response cache from Day 1 — the highest-leverage mitigation. `max_papers=25` for ablations. Overnight sweeps |
| **Free tier withdrawn or terms change mid-project** | Two tiers registered on Day 1; LiteLLM makes the swap a config change. Ollama is *not* a real fallback on CPU-only hardware |
| **CPU-only makes runs too slow to demo live** | Pre-baked showcase run replayed via `GET /api/runs`; live demo only at `max_papers=10`. Decide this on Day 18, not the night before |
| **CPU verification latency too high** | ONNX int8 export; `deberta-v3-small` over `base`. Measure per-claim latency on Day 11 and escalate deliberately if quality is short (§4.2) |
| **Free model emits unparseable JSON** | Strict Pydantic + retry-with-repair (max 2) → `null` + `extraction_note`. Never abort a run on a parse failure. Choose the tier on JSON reliability (§6.2) |
| **Verifier underperforms on your domain** | SciFact skews biomedical; your corpus is CS. Add SciReviewGen citing-sentence pairs if access lands, and **report the domain shift honestly** — naming a limitation is stronger than hiding it |
| **Vue work overruns and squeezes evaluation** | Fixture-driven development decouples it from the backend; panels are prioritised so 1–3 alone still demo well |
| Retrieval quality poisons grounding | Days 6–7 reserved buffer. Do not spend them on features |
| Critic loop oscillates | Hard `max_iterations=3`, forced WRITE on the final iteration, mandatory plan-diff on replan |
| Paywalled PDFs limit full text | Abstract-only degraded mode; flag `text_availability` and **report the split** — a finding, not an embarrassment |

---

## 12. Decisions — all closed

Everything needed to start is now settled. For the record:

| Question | Resolution |
|---|---|
| Training component required? | **Yes** → NLI claim verifier on SciFact (§4.2) |
| Grading weight | **Working system + no hallucination** → Verifier is the centrepiece; demo outranks eval table |
| Budget | **$0** → free tiers for 4 agents; everything else local (§6) |
| Hardware | **CPU-only** → all local models resized (§6.1); Ollama demoted (§6.3) |
| Frontend | **Vue 3 + Vite** → Streamlit dropped, FastAPI restored (§7) |
| Which free tier | **Decided: Gemini free tier primary, Groq backup.** Validate on Day 1 with a thirty-minute JSON-reliability test (§6.2) |
| Literature survey (the question you asked about) | **Resolved both ways, so it no longer matters.** The system generates a survey of its own topic; you then hand-review and edit it, and it becomes the literature-survey chapter of your report. You get the automated artefact *and* a human-checked chapter, from one flagship run |

**Nothing is blocking. Day 1 can start.**

---

*Companion to `RESEARCHGPT_SPEC.md`. Created 2026-08-06, revised twice the same day. Amend this file for scope and schedule changes; amend the spec for design changes.*
