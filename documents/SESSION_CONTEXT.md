# Session Context — ResearchGPT Major Project

> **What this file is.** A complete record of the planning session held on **2026-08-06**: every constraint established, every decision made and why, every document produced, every finding that changes the build, and everything still open.
>
> **Read this first** if you are resuming work, handing over to a teammate, or starting a fresh session. It replaces having to re-read the whole conversation.
>
> **Status at end of session: no code has been written.** Implementation is at Day 0. Everything below is planning, literature, and design artefacts.

---

## 1. Project identity

| | |
|---|---|
| **Title** | A Multi-Agent Agentic RAG Platform for Automated Literature Review |
| **Internal name** | ResearchGPT |
| **Institution** | Gokaraju Rangaraju Institute of Engineering and Technology (Autonomous), Dept. of Data Science |
| **Course** | IV Year B.Tech, I Semester — CSE (Data Science) |
| **Batch** | DSC06 |
| **Team** | Abrarullah Mohammed (23241A67D1) · G. Shashivadan Rao (23241A67F2) · P. Sreekaran Reddy (23241A67H7) |
| **Guide** | Dr. S. Govinda Rao, Head of Department, Data Science |
| **Reviews** | Review-1 completed (`Review-1 dsc06.pptx`) |
| **Deadline** | ~30 days from 2026-08-06 → target submission **~2026-09-05** |

### The three objectives (PPT slide 5 — exactly three, count is correct)

1. Automate end-to-end literature review using a multi-agent agentic RAG pipeline.
2. Ensure factual grounding and coverage completeness via verification and critique loops **and Human-in-the-loop**.
3. Deliver a usable full-stack application with real-time progress visibility.

---

## 2. The five constraints that drive every decision

These were established during the session and override the original spec wherever they conflict.

| # | Constraint | Consequence |
|---|---|---|
| 1 | **Zero API budget.** No paid services at all. | Free-tier LLM only; everything high-volume moved to local CPU. |
| 2 | **CPU-only development machine.** No GPU. | All local models resized for CPU. Ollama demoted to non-viable. Training happens on free Kaggle GPU only. |
| 3 | **A model-training component is required** (even a small one). | NLI claim verifier fine-tuned on SciFact — see §4. |
| 4 | **Grading is weighted to the system working and not hallucinating**, not to paper polish. | Verifier is the centrepiece. Demo outranks the ablation table. Descope ladder reversed. |
| 5 | **Vue.js frontend mandatory**; backend free choice. | Streamlit dropped, FastAPI restored, REST + SSE. |

---

## 3. Architecture as settled

Six agents in a LangGraph state machine with a bounded critic loop. **The design was reviewed against the literature and found sound — no structural change needed.** What changed is the surrounding stack and the diagrams.

```
Vue 3 SPA  ──REST──▶  FastAPI  ──▶  LangGraph StateGraph
    ▲                                      │
    └──────────── SSE progress ────────────┤
                                           ▼
   PLANNER → RETRIEVER → INGEST → RANK → EXTRACTOR
                                           │
                                           ▼
   VERIFIER → (NLI classify) → CRITIC → HUMAN-IN-THE-LOOP
                  │                │
                  │                ├─ RETRIEVE (coverage gap) ─┐
                  │                ├─ REPLAN (plan flawed) ────┤ max 3 iterations
                  │                └─ WRITE ───────────────────┘
                                           ▼
                                        WRITER → artefacts → Vue
```

**Where each part runs** — this is the key to the $0 constraint working:

| Function | Location | Cost |
|---|---|---|
| Embeddings (`bge-small-en-v1.5`, ~33M) | Local CPU | $0, unlimited |
| Reranking (`ms-marco-MiniLM-L-6-v2`, ~22M) | Local CPU | $0, unlimited |
| **Claim verification (fine-tuned NLI, ONNX int8)** | **Local CPU** | **$0, unlimited** |
| Planner, Extractor, Critic, Writer | Free-tier hosted LLM | $0, rate-limited |
| Model training | Kaggle GPU (~30 h/week free) | $0 |

Only four generative calls per run consume the scarce resource, and only the Extractor scales with paper count (~70 calls per run).

---

## 4. Major decisions and the reasoning

### 4.1 Training target: the claim verifier, not the reranker ⬅ changed mid-session

Originally proposed fine-tuning the cross-encoder reranker on SciReviewGen. **Switched to a claim verifier** for three reasons:

- It sits on the graded critical path — you're graded on hallucination; the verifier *is* the anti-hallucination mechanism.
- **No access lead time.** SciFact downloads straight from Hugging Face. The reranker route needed S2ORC access, historically a multi-day AI2 request — the single biggest schedule risk.
- It removes API load. An LLM verifier costs one call per atomic claim (hundreds per run). A local cross-encoder is free and deterministic.

**Recipe:** `deberta-v3-small` (~44M, warm-started from an NLI checkpoint) → 3-way classification `SUPPORT / CONTRADICT / NOT_ENOUGH_INFO` on SciFact → 2–3 epochs on Kaggle, under an hour → **export ONNX int8 for CPU inference**. Softmax probability becomes `support_score`, threshold 0.7.

*Escalate to `deberta-v3-base` if held-out F1 is poor. Trade latency, not accuracy — the verifier is the graded component.*

### 4.2 LLM: Gemini free tier primary, Groq backup

Chosen on **JSON-parse reliability** (the Extractor's 4-field schema must parse) and context window, not benchmark scores. Register both on Day 1 and spend thirty minutes testing the Extractor prompt on each.

**Mandatory Day-1 engineering:** prompt-hash **response cache** to disk (the single highest-leverage thing in the build — dev re-runs then cost zero requests), exponential backoff on 429s, requests-per-minute throttle, and a rate-limit guardrail replacing the spec's `max_cost_usd`.

### 4.3 Stack decisions vs. the original spec

| Item | Spec said | Now | Why |
|---|---|---|---|
| Vector store | Chroma → Qdrant | **Chroma, no migration** | ~3k vectors; Qdrant unjustified |
| Sources | 10 connectors | **OpenAlex + arXiv** | Crossref redundant; **Semantic Scholar hit HTTP 429 during this session** |
| PDF parsing | PyMuPDF + GROBID | **PyMuPDF only** | GROBID is a Docker service for marginal gain |
| Frontend | Streamlit (optional) | **Vue 3 + Vite, no Pinia** | Mandated; one page, one run — a store is ceremony |
| Backend | FastAPI (cut, then restored) | **FastAPI + REST + SSE** | Needed as the Vue backend |
| Determinism | vcrpy cassettes | **JSON response cache** | ~20 lines, and doubles as rate-limit protection |
| RAGAs | Full framework | **Cut the library, keep the metric** | `F = |V|/|S|` is computable free from verifier output |
| Ablations | 7 | **4** | Rate limits make each run expensive in wall clock |
| Human eval | 3 annotators, Krippendorff α | **2 annotators, Cohen κ** | Scheduling problem, not technical |

### 4.4 Base paper: switch recommended ⚠️

See §5.1 — this is the most consequential finding of the session.

---

## 5. Critical findings

### 5.1 ⚠️ The base paper is not what the spec says it is

`RESEARCHGPT_SPEC.md §1.2` describes Aytar et al. (2025) as *"RAG-based literature assistance."*

**The paper is real and correctly attributed** — DOI [10.1016/j.nlp.2025.100179](https://doi.org/10.1016/j.nlp.2025.100179), *Natural Language Processing Journal* (Elsevier, Scopus) — but its actual title is **"A synergistic multi-stage RAG architecture for boosting context relevance in data science literature."** It optimises retrieval precision in the data-science domain. It does not generate literature reviews.

Two consequences:

1. **`§1.3`'s extension table contains a factual error.** It claims the base paper uses a *"fixed single-pass pipeline."* It is explicitly **multi-stage** (GROBID parsing, fine-tuned embeddings, semantic chunking, abstract-first retrieval). That row is the foundation of the "we are more agentic" argument. **Rewrite it** — the honest contrast is *static multi-stage vs. dynamic agentic control with verification*.
2. **It also uses GROBID**, which the plan cuts. If Aytar stays as base paper, dropping GROBID becomes a deviation to defend.

**Recommendation: switch the base paper to SurveyGen** (Bao et al., EMNLP 2025, DOI `10.18653/v1/2025.emnlp-main.136`). Same task, RAG pipeline with quality-aware retrieval that maps onto your venue tiering, and — decisively — their own stated conclusion is your problem statement:

> *"Fully automatic survey generation still suffers from low citation quality and limited critical analysis."*

Low citation quality → your Verifier. Limited critical analysis → your four-field schema. You cite the base paper's authors describing the gap rather than asserting it yourself. Second choice: **Valsci** (BMC Bioinformatics 2025), SciFact-evaluated like your verifier.

### 5.2 Calibration numbers — revise your targets before building

`PROJECT_PLAN.md §9` currently targets groundedness ≥ 0.9. Nothing in the peer-reviewed literature reaches that on realistic scientific verification:

| Source | Measurement |
|---|---|
| **Sarol et al. 2024** (essentially your Verifier: BM25 + MonoT5 + fine-tuned MultiVerS) | **0.59 micro-F1** on real citations |
| **CliVER 2024** | **0.93** Oracle → **0.85** Open retrieval → **0.797** vs clinicians → **0.44** worst domain |
| **SurveyGen 2025** | Best citation accuracy **35.84%**; QUAL-SG citation-quality F1 **16.73%** |
| **SciReviewGen 2023** | ~**30%** of generated chapters match human quality |

**If your verifier reports 0.9+ against real citations, suspect your measurement, not a breakthrough.**

### 5.3 Four independent measurements of the same failure — your Introduction

| Source | Finding |
|---|---|
| Sarol et al. | **39.18%** of citation instances in highly-cited biomedical papers contain accuracy errors (historical median 20%) |
| ALCE (Gao et al.) | Best models *"lack complete citation support 50% of the time"* |
| FActScore (Min et al.) | ChatGPT factually correct on only **58%** of atomic claims in long-form generation |
| SurveyGen | Best survey-generation citation accuracy **35.84%** |

### 5.4 The presence of a citation carries almost no information

FActScore: **36.0%** of *supported* sentences and **37.6%** of *unsupported* sentences carried citations — statistically indistinguishable. This is the deepest justification for claim-level verification, and it means DOI-resolution checking is necessary but shallow.

### 5.5 Architecture beats model scale — measured

**Valsci Table 3:** GPT-4o-mini *inside* their architecture scores **F1 0.720**; bare GPT-4o scores **0.706**. A small cheap model plus good architecture beats a frontier model alone. This is published prior support for the project's narrative: *the architecture is a correctness filter, not a correctness source.* Quote it in the Introduction and again in the Discussion — it converts the $0 constraint from an apology into a hypothesis.

### 5.6 Your closest competitor names your contribution as its own limitation

**Ammann et al. (ACL SRW 2025)** — LLM query decomposition + per-sub-question retrieval + cross-encoder rerank, *"without any extra training"*, reporting +36.7% MRR@10. That is your Planner + Retriever. Their Limitations section, item 6:

> *"Lack of iterative retrieval. Our pipeline operates in a single-shot manner: subqueries are generated once and not updated based on retrieved evidence. This limits its ability to support adaptive multi-step reasoning."*

That is exactly what your Critic loop does. **Quote it verbatim.** Also treat their numbers as a Day-5 sanity check, and their configuration as a stronger ablation-4 baseline than vanilla RAG.

Their limitation #5 is a warning: *"the observed gains rely on a strong, domain-aligned cross-encoder reranker"* — and yours is a 22M MiniLM. Measure reranking's contribution separately.

### 5.7 Abstract-only conditioning costs 21 points of faithfulness

**Li et al. (SDP@ACL 2024)** measured ANLI faithfulness of generated citations: **Abstract 0.745** vs **Context-CTS 0.959 / Oracle 0.940 / Keyword 0.941**, consistent across two generators. Their conclusion: abstract-conditioned models *"learn to hallucinate."*

**This threatens the planned abstract-only degraded mode for paywalled papers.** Recommended fix: abstract-only papers may be **cited as existing but may not supply verified claims**. Note the tension with the base paper's "Abstract First" finding — abstracts may be good for *retrieval* and bad for *grounding*.

### 5.8 Humans agree poorly on exactly what you plan to measure

| Study | Agreement |
|---|---|
| Sarol et al. | κ **0.18–0.31** (accuracy labels) |
| CiteBench | κ **0.18–0.42** (consistency) |
| SciReviewGen | κ **0.212** (three-way review quality) |
| CliVER | Fleiss κ 0.684 (own curated claims) |

Consequences: use **two annotators and report κ**; a verifier at 0.59 against humans agreeing 0.3 is not obviously failing; prefer objective metrics as primary evidence.

### 5.9 SciReviewGen's limitations list is a requirements document for your system

| Their stated limitation | Your response |
|---|---|
| Only abstracts as input | Full-text parsing + `evidence_spans` |
| Chapters generated independently | Writer synthesises across themes; Critic assesses globally |
| Inter-paper relations ignored | Thematic clustering + `contradiction_pairs` |
| Output contains incorrect information | Verifier removes unsupported claims |

### 5.10 Smaller actionable findings

- **Dagdelen et al.**: structured output stabilises at **~20 few-shot examples**; below ~10 it is malformed. Sets your Extractor prompt. Also — schema format interacts with model (JSON best for Llama-2, English-sentence for GPT-3), so A/B it.
- **CliVER**: **21% false-Support rate** (recall 1.0, precision 0.79). Over-predicting "supported" is the dangerous direction for a hallucination-graded project. Weight the `SUPPORTED` threshold toward precision.
- **ALCE**: post-hoc citation attachment cost **47% of citation recall**. Validates the evidence-first Writer constraint.
- **Retrieval recall is a hard ceiling** on verification — stated independently by ALCE, Sarol (top-20 recall 0.53) and Valsci. Protect the Day 6–7 retrieval buffer.
- **Bolaños et al.**: use **F2 not F1** for screening (recall matters more than precision when discarding papers).
- **CiteBench**: ROUGE package configuration alone swings scores ~3 points — specify yours.
- **FActScore scope limit**: its method *"is not applicable when the facts are more nuanced, open-ended, and debatable."* Your `disadvantages` and `critique` fields are exactly that — consider verifying only the objective fields strictly.

---

## 6. Documents produced this session

All in `C:\Users\Sreekaran\Desktop\Major Project\`.

| File | Contents |
|---|---|
| **`PROJECT_PLAN.md`** | 30-day execution plan. Scope cuts with rationale, $0/CPU model strategy, day-by-day timeline, evaluation design, **descope ladder**, risk table. Revised three times as constraints emerged. |
| **`LITERATURE_REVIEW.md`** | 25 papers (2023–2026, peer-reviewed), comparative table across Problem/Methodology/Advantages/Disadvantages/Datasets/DOI, thematic synthesis, gaps, **3 ranked base-paper candidates**, verification report, 9-paper reserve pool. |
| **`PAPER_ANALYSIS.md`** | Per-paper extensive analysis (6 fields + relevance) written from verified abstracts. |
| **`PAPER_DEEP_DIVE.md`** | Full-text deep dive. **18 of 26 papers obtained in full text**; 8 abstract-only and marked as such. Every reported number, verbatim limitations, cross-cutting synthesis, 14 ranked actions. |
| **`ARCHITECTURE_REVIEW.md`** | Audit of the spec's architecture diagram and MCD against the three review rules. Corrected UML activity diagram, UML component diagram, UML MCD, classical structure chart alternative, PPT consistency table, objective refinements. |
| **`diagrams/01_architecture_diagram.drawio`** | UML 2.5 activity diagram, 3 swimlane partitions (one per objective), 33 vertices / 32 edges. |
| **`diagrams/02_module_connectivity_diagram.drawio`** | UML 2.5 component diagram, 4 `«subsystem»` packages, 27 vertices / 29 edges. |
| **`SESSION_CONTEXT.md`** | This file. |

Pre-existing: `RESEARCHGPT_SPEC.md`, `Review-1 dsc06.pptx`, `Literature papers/` (7 PDFs).

---

## 7. Corrections required to existing documents

### 7.1 `RESEARCHGPT_SPEC.md`

| Section | Fix |
|---|---|
| §1.2 | Base paper mis-described. Correct the title/scope, or switch to SurveyGen. |
| §1.3 | *"Fixed single-pass pipeline"* is factually wrong — Aytar et al. is multi-stage. |
| §3 | Architecture diagram: not UML, no input/output zones, **Objective 3 absent entirely** (no Vue/FastAPI), **HITL absent**. Replace with the draw.io file. |
| §4 | Package-dependency graph, not an MCD. Keep it but relabel "Package Dependency Map" and add the real MCD. |
| §7.5 | Add human-in-the-loop to the Critic. |
| §9 | Targets need revising downward per §5.2. |

### 7.2 `Review-1 dsc06.pptx`

| Slide | Problem | Severity |
|---|---|---|
| 6 | *"GPU: 8GB Minimum"* — machine is CPU-only. Specifies hardware you don't have. | ⚠️ **Visible error** |
| 8 | *"Extractor chunks and embeds them"* — that's the Ingestor's job. As written, the system has **no structured extraction**, deleting a main contribution. | ⚠️ **Visible error** |
| 3, 8, 9 | pgvector/PostgreSQL vs Chroma everywhere else. Chroma avoids running Postgres + Docker. | Medium |
| 3, 6 | Semantic Scholar as a source — rate-limited without a key (confirmed 429 this session). | Medium |
| 7 | Replace architecture diagram. | High |
| 10 | Replace MCD. | High |
| 11 | Processing-branch sentence needs the 2.1 / 2.2 split. | Medium |
| 12 | ○/● couple explanation only applies to the structure-chart version — rewrite if going UML. | Medium |
| 5 | Objectives: lowercase "to automate/ensure/deliver"; **add the trained verifier to Objective 2** so there's an answer to "where's the ML?" | Low but valuable |

---

## 8. Open items — only you can close these

1. **Get the PDF of Li et al., *Information Processing & Management*** (DOI `10.1016/j.ipm.2025.104369`) through your library. ScienceDirect returns HTTP 403 to automated access, so it is the one paper in the set written from its title alone. "Evidence-aware" + "self-corrective" describes your Verifier and Critic — **it may be a competitor to differentiate from, not a supporting citation.** Also: OpenAlex dates it 2025, Semantic Scholar 2026 — resolve before it enters your reference list.
2. **Confirm the base-paper switch with your guide** (Aytar → SurveyGen).
3. **Confirm which MCD notation the rubric means** — UML component diagram, or classical Yourdon/Constantine structure chart. Both are prepared; they need different slide 12 text.
4. **Verify *Vicinagearth* is Scopus-indexed** (paper C3-11, launched 2024). If not, substitute Wang et al. 2024, *Frontiers of Computer Science*, DOI `10.1007/s11704-024-40231-1` (1,320 citations).
5. **Decide whether Human-in-the-loop stays in Objective 2.** Keep it only if you build it — the cheapest honest version is the dropped-claims panel with confirm/override, ~half a day on top of the Vue panel already planned.
6. **File the S2ORC access request** if you want SciReviewGen gold sets (nothing critical depends on it now).

---

## 9. Environment notes discovered this session

| Tool | Status |
|---|---|
| **OpenAlex API** | ✅ Works, keyless, rich venue metadata. Primary source for verification. |
| **Crossref API** | ✅ Works, keyless. Good fallback for abstracts. |
| **Europe PMC** | ✅ Works. Full text XML for OA biomedical papers. |
| **Semantic Scholar API** | ⚠️ HTTP 429 rate-limited without a key. |
| **ScienceDirect / ACM / OUP / MIT Press / IEEE** | ❌ HTTP 403 to automated access. |
| **ACL Anthology** | ✅ PDFs download freely — best source for NLP papers. |
| **PyMuPDF (`fitz`)** | ✅ Installed. Used for all PDF text extraction. |
| **poppler / pdftoppm** | ❌ Not installed (blocks the Read tool's PDF rendering). |
| **draw.io desktop CLI** | ❌ Not installed. Blocks ELK auto-layout and PNG/SVG export. Installing it would enable `drawio -x -f svg -e -b 10 -o out.svg file.drawio`. |
| Python | 3.14, with `pip` available. |

**Search method that worked** for the literature review: OpenAlex `title_and_abstract.search` filter with a hard 2023-01-01…2026-12-31 date window, across 6 thematic clusters and 28 named-system queries — ~712 unique works screened, 26 DOIs resolved with 0 failures. Plain `search=` sorted by citations returned irrelevant high-citation medical papers; the strict title/abstract filter fixed it.

---

## 10. Where to start next session

The first working day is fully specified in `PROJECT_PLAN.md §8`. In short:

**Day 1:** `git init`. Scaffold, `pyproject.toml`, config loader, `core/llm.py` **with cache + throttle + backoff built in from the start**, `core/models.py`, trace logger, CLI stub. Register two free tiers and test both on the Extractor prompt. Download SciFact.

**The milestone that matters is Day 12**, not Day 30: a complete cited literature review from the CLI, before the Verifier and Critic exist. That is the insurance policy — if weeks 3–4 collapse, there is still something to submit.

**Never cut** (from the descope ladder): the six agents, the trained verifier, the evidence-inspection demo, ablation 2 (− Verifier), the trace log, or the Day 12 milestone.

---

*Session date: 2026-08-06. All DOIs and API results verified that day. Re-verify before submission — indexes and publication years change.*
