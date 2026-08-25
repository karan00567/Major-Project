# Architecture Diagram — Complete Walkthrough

**Companion to:** `diagrams/01_architecture_diagram.drawio`
**Diagram title on canvas:** *ResearchGPT — System Architecture (UML 2.5 Activity Diagram with Activity Partitions)*
**Purpose of this document:** if you read this file end to end, you can stand in front of the review committee and defend every single mark on that canvas — every box, every diamond, every arrow, every guard label, and every deliberate omission.

---

## 0. How to use this document

| Section | Use it for |
|---|---|
| §1–§2 | The 60-second opening statement when the diagram first goes on screen |
| §3 | Notation dictionary — what each *shape* means in UML 2.5 |
| §4 | Every element, one by one, with the exact on-canvas text |
| §5 | Every arrow, one by one, including the three feedback edges |
| §6 | The end-to-end spoken narrative (this is what you actually say) |
| §7 | Objective traceability — the question the committee *will* ask |
| §8 | Design decisions and their justification |
| §9 | Honest gaps — say these before the committee finds them |
| §10 | Anticipated Q&A with prepared answers |

---

## 1. What this diagram is, in one sentence

It is a **UML 2.5 Activity Diagram** that shows the complete runtime behaviour of ResearchGPT — from the researcher typing a question to the researcher downloading the finished literature review — partitioned into **three vertical swimlanes, one per project objective**, so that the behaviour and the objectives are provably the same thing.

## 2. Why an Activity Diagram and not a block diagram

State this early; it pre-empts the first methodological question.

1. **The system is a control-flow system, not a data-flow system.** The core contribution is that the Critic can *send control backwards* to the Planner or Retriever. A block diagram cannot express a loop with a bound; an activity diagram can, with decision nodes and guards.
2. **Activity partitions (swimlanes) give free traceability.** UML activity partitions exist to answer "who is responsible for this action". By naming the partitions after the three project objectives, every action on the canvas is automatically owned by an objective. There is no action anywhere on the canvas that does not sit inside an objective.
3. **It is a behavioural view, and the committee also has a structural view.** The Module Connectivity Diagram (file 02) is the structural counterpart. Together they satisfy the standard "one behavioural + one structural view" expectation.

**The one-line answer if challenged:** *"An activity diagram was chosen because the defining feature of this architecture is a bounded feedback loop with guard conditions, and UML activity semantics — decision nodes, merge nodes, guards — are the standard notation for exactly that. The partitions are mapped to objectives so the diagram doubles as an objective-traceability artefact."*

---

## 3. Notation dictionary — every shape on the canvas

This is the content of the **legend box** at the bottom of the canvas (element `lgbox`, spanning the full 1280 px width at y = 2050), expanded.

| Shape as drawn | UML 2.5 name | Meaning | Where it appears here |
|---|---|---|---|
| **Solid filled black circle** (small) | **Initial node** | Where the activity starts. Exactly one per activity. | `S`, top of Lane A |
| **Circle with a filled centre** (bullseye) | **Activity final node** | Terminates the whole activity. Drawn as two elements: outer ring `Zout` + inner filled dot `Zin` | Bottom of Lane A |
| **Rounded rectangle** | **Action** (executable node) | A unit of work the system performs | All the PLANNER/RETRIEVER/…/WRITER boxes, and all user-side actions |
| **Rounded rectangle, dashed border** | **Accept Event Action** | An action that waits for an asynchronous event rather than being invoked in sequence | `A8` — Accept progress event (SSE) |
| **Plain rectangle** (square corners) | **Object node** (data) | A data object flowing between actions, with its state in brackets | `objQ` `:ResearchQuery [validated]`, `objArt` `:ReviewArtefacts [generated]` |
| **Large diamond with text inside** | **Decision node** | One input, several mutually exclusive guarded outputs | `A2`, `C3`, `C6` |
| **Small empty diamond, no text** | **Merge node** | Several inputs, one output. Does *not* synchronise — it just re-joins branches | `mrgA`, `mrgB1`, `mrgB2`, `mrgC` |
| **Solid line, open arrowhead** | **Control flow** | Sequencing: when the source finishes, the target starts | 26 of the 29 flow edges |
| **Dashed line, open arrowhead, «signal»** | **Signal flow** | Asynchronous notification; the sender does not block | `e30`, `e31`, `e32` — the SSE progress stream |
| **`[text]` on an arrow** | **Guard condition** | The branch is only taken if this predicate is true | `[valid]`, `[invalid]`, `[yes]`, `[no]`, `[RETRIEVE: coverage gap]`, `[REPLAN: plan flawed]`, `[WRITE: approved or max 3 iterations]` |
| **Tall vertical box with a header band** | **Activity partition (swimlane)** | Responsibility grouping | The three lanes |

**Critical distinction the committee may probe — decision vs merge.**
A decision node is a *branch* (1 in, N out, guards on the outputs). A merge node is a *join of alternative paths* (N in, 1 out, no guards, no waiting). A merge node is **not** a join/synchronisation bar — it does not wait for all inputs, because the incoming paths are alternatives, not parallel threads. This diagram uses no fork/join bars at all, because the pipeline is strictly sequential; the only concurrency is the asynchronous SSE signal, which is correctly drawn as signal flow, not as a fork.

**Why everything is black-and-white with `fillColor=none`.** Deliberate. The diagram is designed to survive greyscale printing and projector washout, and UML carries no semantics in colour — meaning is carried by shape, line style, and guard text alone. If a reviewer asks "why no colour", that is the answer.

---

## 4. The three swimlanes (activity partitions)

The canvas is 1400 × 2200 px. The three lanes each run 1990 px tall from y = 40, so all three are read top-to-bottom in parallel.

### Lane A — `laneA`
> **PRESENTATION — OBJECTIVE 3: usable full-stack application with real-time progress visibility**
> x = 40, width = 400

Everything the human sees or touches. Contains the start node, the end node, query entry, validation, the API invocation, the live progress receiver, the results view, and the download step. This is the Vue + FastAPI surface.

### Lane B — `laneB`
> **AUTOMATED MULTI-AGENT PIPELINE — OBJECTIVE 1: automate end-to-end literature review**
> x = 440, width = 400

The forward-generation path: Planner → Retriever → Ingest → Rank → Extractor, and — far down the lane — the Writer. This is the LangGraph orchestrated agent chain.

### Lane C — `laneC`
> **GROUNDING AND QUALITY CONTROL — OBJECTIVE 2: factual grounding, coverage completeness, human-in-the-loop**
> x = 840, width = 480

Everything that checks, filters, gates, or overrides. Verifier, the fine-tuned classifier, the claim filter, the Critic, and the human step. It is the widest lane (480 vs 400) because it carries the most text-heavy boxes and all three feedback edges leave from it.

**The single most important visual fact about this diagram:** the Writer (`B9`, in Lane B) sits *below* the human-in-the-loop step (`C7`, in Lane C). Control physically flows right-to-left from Lane C back into Lane B at the very bottom. That geometry is the argument: **nothing is written until quality control and the human have both signed off.**

---

## 5. Element-by-element walkthrough

Exact on-canvas text is quoted. IDs are the internal draw.io identifiers — invisible in the render, but useful when someone points at a box and asks "which one".

### 5.1 Title and legend

| ID | On-canvas text | Notes |
|---|---|---|
| `title` | "ResearchGPT — System Architecture (UML 2.5 Activity Diagram with Activity Partitions)" | 18 pt bold, centred across the full width. Naming the UML version is deliberate — it tells the committee the notation is standards-conformant rather than ad hoc. |
| `lgbox` | The 4-line LEGEND block | Placed *below* the lanes at y = 2050 so it never overlaps content. Contains the full shape dictionary reproduced in §3. Always point at it once, early — a legend on the canvas removes an entire class of notation objections. |

### 5.2 Lane A — Presentation (Objective 3)

| ID | On-canvas text | Shape | What it means and why it is there |
|---|---|---|---|
| `S` | *(no text)* | Initial node | Entry point of the whole activity. UML requires exactly one per activity; there is exactly one. |
| `mrgA` | *(no text)* | Merge node | Re-joins two paths: the first-time entry from `S`, and the re-entry from a rejected query. Without it, the `[invalid]` arrow would have to point at an action that already has an incoming edge from the start node — which is legal but muddier. The merge makes the retry loop explicit. |
| `A1` | "Submit research question and constraints" | Action | The researcher enters the question plus constraints. In the spec, "constraints" is a typed dict: years, venues, max_papers, language. |
| `A2` | "Query valid?" | Decision | Client- and server-side validation gate. Two guarded exits. |
| `objQ` | ":ResearchQuery [validated]" | Object node | The data object produced by validation, shown in its `[validated]` state. UML object-node convention is `:TypeName [state]` — the leading colon means "an anonymous instance of this type". Drawing it as an object node rather than an action is the point: it shows that a *typed, validated artefact* — not raw text — crosses into the pipeline. This maps to Pydantic v2 validation in the spec. |
| `A3` | "Invoke review service — REST POST /api/review" | Action | The concrete transport is named on the canvas. This is the FastAPI entry point. Naming the HTTP verb and route makes the diagram implementable rather than abstract. |
| `A8` | "Accept progress event — Server-Sent Events stream" | **Accept Event Action** (dashed) | The live-progress receiver. It is dashed and it is a *sink for three signal arrows*, not a link in the sequential chain — nothing flows out of it. That is the correct modelling of an asynchronous push channel: it fires whenever an event arrives, independent of where the main control flow currently is. This box alone satisfies the "real-time progress visibility" clause of Objective 3. |
| `objArt` | ":ReviewArtefacts [generated]" | Object node | The Writer's output as a typed object in the `[generated]` state, handed back across the lane boundary into Presentation. |
| `A9` | "Display review with clickable evidence spans and dropped-claims panel" | Action | The results view. Two features are named for a reason: **clickable evidence spans** = every sentence traces to a source chunk (Objective 2 made visible); **dropped-claims panel** = the UI surface through which the human-in-the-loop step is actually performed. |
| `A10` | "Download review.md, insights.csv, refs.bib, trace.jsonl" | Action | The four deliverable artefacts, named explicitly. `trace.jsonl` matters most for the paper — it is the run log that makes the evaluation section reproducible. |
| `Zout` + `Zin` | *(no text)* | Activity final node | Drawn as an outer ring (`Zout`, 30 px, stroke width 2) with a concentric filled dot (`Zin`, 16 px) — the standard bullseye. Terminates the entire activity. |

> **Note on IDs:** the identifiers jump from `A3` to `A8`, and in Lane B from `B5` to `B9`. These are naming leftovers from an earlier draft, not missing boxes. Nothing is absent from the diagram; the numbering is simply not contiguous. Mention this only if someone reads the XML.

### 5.3 Lane B — Automated multi-agent pipeline (Objective 1)

| ID | On-canvas text | Shape | What it means and why it is there |
|---|---|---|---|
| `mrgB1` | *(no text)* | Merge node | Entry point to the Planner. Joins two paths: the first invocation from `A3`, and the **REPLAN** feedback edge from the Critic. This is what makes the Planner re-enterable. |
| `B1` | "**PLANNER** — decompose into 4–8 sub-questions, build search plan" | Action | Agent 1. Splits the research question by facet (method / application / evaluation / limitation) and emits a per-sub-question search plan with source priorities and year filters. The range "4–8" is on the canvas because it is a real, defensible design bound, not a vague "several". Spec rule: on replan the Planner *must* emit a different plan and record the diff — it may never re-emit an identical plan, which is what guarantees the loop makes progress. |
| `mrgB2` | *(no text)* | Merge node | Entry point to the Retriever. Joins the normal path from the Planner and the **RETRIEVE** feedback edge from the Critic. This is the tighter of the two loops — it widens the search without re-planning. |
| `B2` | "**RETRIEVER** — federated search OpenAlex + arXiv, dedup by DOI, screen" | Action | Agent 2. Three named responsibilities: (a) federated search across multiple sources, (b) deduplication keyed on DOI with a normalised title+year fallback, (c) screening against inclusion criteria to drop out-of-scope hits cheaply. OpenAlex and arXiv are named because they are keyless and free — the system works with zero API keys, and keyed sources (IEEE Xplore, Scopus) sit behind feature flags. Spec rule: never fabricate metadata — an unresolvable field is `None`, never guessed. |
| `B3` | "**INGEST** — PDF parse, section-aware chunk, embed on CPU" | Action | PDF parsing (PyMuPDF, optionally GROBID for section and reference structure), **section-aware** chunking, and embedding. "Section-aware" is the load-bearing word: chunks carry which section they came from (abstract / methods / results), which is what later lets the Extractor find *methodology* text specifically instead of guessing. "on CPU" is a deliberate feasibility claim — no GPU is required. |
| `B4` | "**RANK** — BM25 + dense, RRF fusion, cross-encoder rerank, top-12" | Action | The hybrid retrieval stack, fully specified: sparse lexical BM25 and dense vector retrieval run in parallel, their result lists are combined by **Reciprocal Rank Fusion**, a cross-encoder reranker (`BAAI/bge-reranker-v2-m3`) re-scores the fused list, and the top 12 chunks per sub-question survive. Every one of those four stages is a separately ablatable component in the evaluation protocol. |
| `B5` | "**EXTRACTOR** — 4-field insight schema plus evidence spans" | Action | Agent 3, and **one of the five claimed contributions**. Produces one structured record per paper: `methodology`, `advantages`, `disadvantages`, `critique` — plus `datasets`, `metrics`, `results`, `limitations`, `cluster` (C1–C6), and `evidence_spans[]`. Hard rule: every field carries evidence spans (chunk_id + character offsets); a field with no locatable span is emitted as `null` with an `extraction_note`, never invented. This is the box that turns free-text summarisation into a comparable, tabular, at-scale extraction — and it is what makes `insights.csv` possible. |
| `B9` | "**WRITER** — thematic synthesis, IEEE numeric citations" | Action | Agent 6, and the last action in the pipeline. Consumes *verified* state only. Produces the review structured as: Abstract · Introduction · Methodology of the review · Thematic sections (one per cluster) · Comparative insight table · Contradictions & open problems · Research gaps · Conclusion · References. IEEE numeric style `[n]`; preprints are labelled `[preprint]` in the reference list. **The hard rule that defines this box: no sentence may be written that is not backed by a verified claim.** Its position — below the human step, reached by an arrow that crosses back from Lane C — is the visual proof of that rule. |

### 5.4 Lane C — Grounding and quality control (Objective 2)

| ID | On-canvas text | Shape | What it means and why it is there |
|---|---|---|---|
| `C1` | "**VERIFIER** — decompose insights into atomic claims" | Action | Agent 4, stage 1. Breaks each extracted insight into atomic, independently checkable claims. Atomicity matters: a compound sentence can be half-true, and half-true is unverifiable. Splitting first is what makes a binary support judgement meaningful. |
| `C2` | "**CLASSIFY** claim against evidence span — fine-tuned NLI cross-encoder, ONNX int8, CPU" | Action | **This is the trained-model box — point at it when anyone asks "where is the machine learning in this project?"** A natural-language-inference cross-encoder judges each (claim, evidence span) pair and emits a verdict — SUPPORTED / PARTIAL / UNSUPPORTED / CONTRADICTED — with a continuous `support_score ∈ [0,1]`. Three engineering facts are on the canvas: it is **fine-tuned** (so it has its own precision/recall figures and its own ablation row), exported to **ONNX with int8 quantisation** (so it is small and fast), and it runs on **CPU** (so the whole system needs no GPU). |
| `C3` | "support score above threshold?" | Decision | The grounding gate. Default threshold **0.7**. Two guarded exits, `[yes]` and `[no]`. |
| `C4` | "Discard claim, log to trace" | Action | The `[no]` branch. The wording is precise and worth quoting verbatim to the committee: the claim is **discarded**, not softened, not hedged, not re-worded with a "may" — and it is **logged**, so it is recoverable, auditable, and displayable in the dropped-claims panel. This is the mechanism behind the "hallucination rate: 0 by construction" claim in the evaluation protocol. |
| `mrgC` | *(no text)* | Merge node | Re-joins the kept path (`[yes]`) and the discarded path (from `C4`) before the Critic runs. Both branches must reconvene because the Critic assesses the *whole* state — including how much was dropped, which is itself a quality signal. |
| `C5` | "**CRITIC** — assess coverage, grounding, paper count, venue mix" | Action | Agent 5. Four named checks, each with a concrete threshold in the spec: sub-question coverage ≥ 80%; ≥ 20 papers retained (`min_papers`); grounding score ≥ 0.75; no sub-question with fewer than 2 supporting papers; plus venue-tier mix and recency window. Venue mix is the source-discipline check — peer-reviewed Scopus/IEEE/ACL sources outrank preprints. |
| `C6` | "Critic decision" | Decision | The three-way control gate — the structural heart of the whole architecture. Three guarded exits: RETRIEVE, REPLAN, WRITE. |
| `C7` | "**HUMAN-IN-THE-LOOP** — analyst confirms or overrides flagged and dropped claims" | Action | The human gate. The analyst reviews what the automated verifier flagged or dropped and either confirms the machine's judgement or overrides it. Concretely this is the dropped-claims panel named in `A9`. It sits **after** the Critic and **before** the Writer — the last checkpoint before any prose is generated. This single box is what makes the "human-in-the-loop" clause of Objective 2 real rather than aspirational. |

---

## 6. Edge-by-edge walkthrough

29 flow edges (`e01`–`e29`) plus 3 signal edges (`e30`–`e32`).

### 6.1 The main forward path (13 edges, `e01`–`e16`)

```
S → mrgA → A1 → A2 --[valid]--> objQ → A3 → mrgB1 → B1 → mrgB2 → B2 → B3 → B4 → B5 → C1 → C2 → C3
```

| Edge | From → To | Guard | Note |
|---|---|---|---|
| `e01` | `S` → `mrgA` | — | Start |
| `e02` | `mrgA` → `A1` | — | |
| `e03` | `A1` → `A2` | — | |
| `e05` | `A2` → `objQ` | `[valid]` | Produces the typed validated object |
| `e06` | `objQ` → `A3` | — | |
| `e07` | `A3` → `mrgB1` | — | **Lane A → Lane B crossing.** The HTTP request enters the pipeline here |
| `e08` | `mrgB1` → `B1` | — | |
| `e09` | `B1` → `mrgB2` | — | |
| `e10` | `mrgB2` → `B2` | — | |
| `e11`–`e13` | `B2` → `B3` → `B4` → `B5` | — | Retrieve → ingest → rank → extract |
| `e14` | `B5` → `C1` | — | **Lane B → Lane C crossing.** Generation hands off to verification |
| `e15`, `e16` | `C1` → `C2` → `C3` | — | Decompose, classify, gate |

### 6.2 The validation retry loop (1 edge)

| Edge | From → To | Guard | Note |
|---|---|---|---|
| `e04` | `A2` → `mrgA` | `[invalid]` | Routed left out of the decision, up the outside of the lane through waypoints (60, 320) and (60, 155), and back into the merge node. An invalid query never reaches the pipeline; the researcher is returned to the input step. Drawing it as an explicit loop rather than an "error" terminator is correct — the user is not ejected from the system. |

### 6.3 The claim-filter branch (3 edges)

| Edge | From → To | Guard | Note |
|---|---|---|---|
| `e17` | `C3` → `C4` | `[no]` | Below threshold → discard and log |
| `e18` | `C3` → `mrgC` | `[yes]` | At or above threshold → kept |
| `e19` | `C4` → `mrgC` | — | The discarded path rejoins so the Critic sees the full picture |

### 6.4 The three Critic decision edges — the core of the architecture

These three edges out of `C6` are the single most important thing on the canvas. If you explain nothing else, explain these.

| Edge | From → To | Guard on canvas | What it means |
|---|---|---|---|
| `e22` | `C6` → `mrgB2` | `[RETRIEVE: coverage gap]` | **The tight loop.** The plan is sound but the evidence is thin. Control jumps back to the Retriever's merge node — search wider, retrieve more, re-verify. Routed far right through waypoints (1350, 1475) and (1350, 605), so the backward flow is unmistakable at a glance. |
| `e23` | `C6` → `mrgB1` | `[REPLAN: plan flawed]` | **The wide loop.** The problem is not the evidence, it is the question decomposition itself. Control jumps all the way back to the Planner, which must produce a *different* plan. Routed slightly further right, at x = 1375, so the two backward edges never overlap. |
| `e24` | `C6` → `C7` | `[WRITE: approved or max 3 iterations]` | **The exit.** Two ways to take it: the Critic approves, **or** the iteration cap is hit. The guard text names the bound on the canvas. |

**Why the bound is written on the diagram.** `max_iterations = 3`. On the third iteration the system *forces* WRITE and records the unresolved gaps in the review's Limitations section rather than looping forever. Two properties follow, and both are worth saying out loud:

- **Termination is guaranteed.** The agentic loop cannot run away. Any reviewer worried about an unbounded LLM loop is answered by the guard text itself.
- **Failure is reported, not hidden.** An unresolved coverage gap becomes a written limitation in the output, not a silent omission.

This three-way branch is precisely what separates ResearchGPT from the base paper's fixed single-pass pipeline. That distinction is the project's headline contribution, and it is one diamond with three labelled arrows.

### 6.5 The human gate and the write-out path (5 edges)

| Edge | From → To | Note |
|---|---|---|
| `e25` | `C7` → `B9` | **Lane C → Lane B crossing, at the very bottom of the canvas.** The human's confirmation is what releases the Writer. Trace this arrow with your finger during the presentation — it is the visual proof that no prose is generated before a human has signed off. |
| `e26` | `B9` → `objArt` | **Lane B → Lane A crossing.** The Writer's output becomes the typed `:ReviewArtefacts [generated]` object |
| `e27` | `objArt` → `A9` | Artefacts are displayed |
| `e28` | `A9` → `A10` | Display, then download |
| `e29` | `A10` → `Zout` | Terminate |

### 6.6 The three signal edges — real-time progress (Objective 3)

All three are **dashed, labelled «signal», and terminate on `A8`**, the dashed accept-event action.

| Edge | From → To | Progress reported |
|---|---|---|
| `e30` | `B1` (Planner) → `A8` | "Planning complete — N sub-questions" |
| `e31` | `B4` (Rank) → `A8` | "Retrieval and ranking complete — N papers" |
| `e32` | `C5` (Critic) → `A8` | "Quality assessment complete — iteration N" |

**Why exactly three, and why these three.** They are the three points where a user waiting on a long-running job most needs reassurance, and they are spread across all three lanes' worth of work — one early (planning), one mid (retrieval), one late (critique). Emitting from every action would clutter the diagram without adding information.

**Why dashed and why they carry no return arrow.** Signal flow is asynchronous and one-way. The pipeline emits an event and continues immediately; it never waits for the UI to acknowledge. If these were drawn as solid control flows, the diagram would be claiming the backend blocks on the frontend — architecturally wrong, and a legitimate thing for a reviewer to catch. The dashed «signal» notation is what makes the SSE stream correct rather than merely present.

---

## 7. The spoken narrative — what you actually say

Roughly 90 seconds. Trace the path with a pointer as you speak.

> "This is a UML 2.5 activity diagram. The three vertical partitions are the three project objectives, so every action on this canvas is owned by an objective.
>
> **[Lane A, top]** The researcher submits a question with constraints. It is validated; if it fails, control loops straight back to the input step. If it passes, we produce a typed, validated ResearchQuery object and POST it to the review service.
>
> **[Lane B]** That enters the automated pipeline. The Planner decomposes the question into four to eight sub-questions and builds a search plan. The Retriever runs a federated search across OpenAlex and arXiv, deduplicates by DOI and screens against inclusion criteria. Ingest parses the PDFs and chunks them section-aware, so we know which chunk came from a methods section. Rank runs BM25 and dense retrieval in parallel, fuses them with reciprocal rank fusion, reranks with a cross-encoder, and keeps the top twelve. The Extractor then produces our structured four-field insight per paper — methodology, advantages, disadvantages, critique — and every field carries an evidence span with character offsets.
>
> **[Lane C]** Now grounding. The Verifier breaks each insight into atomic claims. Each claim is classified against its evidence span by a fine-tuned NLI cross-encoder — this is the model we train, it is quantised to int8 ONNX and runs on CPU. If the support score falls below threshold, the claim is discarded and logged — not hedged, discarded. The Critic then assesses coverage, grounding, paper count and venue mix.
>
> **[The three arrows out of the Critic diamond]** And this is the heart of it. If coverage is thin, control goes back to the Retriever. If the plan itself was wrong, control goes all the way back to the Planner. Only when the Critic approves — or we hit the three-iteration bound, which guarantees termination — do we move on.
>
> **[C7 → B9, bottom, right to left]** And even then, not straight to writing. A human analyst confirms or overrides the flagged and dropped claims first. Only then does the Writer run, and the Writer cannot write a sentence that is not backed by a verified claim.
>
> **[Lane A, bottom]** The artefacts come back to the presentation layer, are displayed with clickable evidence spans and a dropped-claims panel, and are downloadable as markdown, CSV, BibTeX and a JSONL trace.
>
> **[The three dashed arrows]** Throughout, these dashed signal arrows push progress events to the UI over server-sent events, so the user is never staring at a spinner."

---

## 8. Objective traceability

The committee will ask how the architecture maps to the objectives. The diagram answers structurally — the lanes *are* the objectives.

| Objective | Lane | Elements that discharge it |
|---|---|---|
| **1. Automate end-to-end literature review using a multi-agent agentic RAG pipeline** | Lane B | `B1` Planner, `B2` Retriever, `B3` Ingest, `B4` Rank, `B5` Extractor, `B9` Writer — plus the two backward edges `e22`/`e23` that make it *agentic* rather than a fixed pipeline |
| **2. Ensure factual grounding and coverage completeness via a fine-tuned claim-verification model, a bounded critique loop, and human-in-the-loop confirmation** | Lane C | `C1` Verifier, `C2` fine-tuned NLI classifier, `C3`/`C4` threshold filter, `C5`/`C6` Critic with bounded loop, `C7` human-in-the-loop |
| **3. Deliver a usable full-stack application with real-time progress visibility and traceable, downloadable artefacts** | Lane A | `A1`–`A3` input and API, `A8` SSE receiver + edges `e30`–`e32`, `A9` evidence-span display, `A10` four downloadable artefacts |

**The strong claim you can make:** there is no action anywhere on this canvas that falls outside an objective, and no objective without at least five actions discharging it. The mapping is total in both directions.

---

## 9. Design decisions worth defending

| Decision | Justification |
|---|---|
| **Activity diagram, not block/flowchart** | The architecture's defining feature is a guarded feedback loop; UML activity semantics are the standard notation for guarded control flow. A block diagram cannot express `[REPLAN: plan flawed]`. |
| **Partitions named after objectives, not layers** | Layer-based partitions (Orchestrator / Service / Persistence) would group by technology and leave objective coverage unprovable. Objective-based partitions make traceability structural. |
| **Ingest and Rank drawn as separate actions** | The spec folds both into the Retriever agent (§7.2). They are drawn separately because they are separately *ablatable* — the evaluation protocol has an ablation row for "− hybrid retrieval" and one for "− reranker", so they must be visible as distinct units of work. Six agents, nine actions. |
| **`max 3 iterations` written on the guard** | Termination is the first thing anyone asks about an agentic loop. Putting the bound in the guard text answers it before it is asked. |
| **Object nodes for `:ResearchQuery` and `:ReviewArtefacts` only** | Object nodes are used at the two lane-crossing boundaries where a *typed contract* matters most. Showing an object node between every pair of actions would triple the element count for no analytical gain. |
| **Threshold value not printed on `C3`** | The canvas says "above threshold?" rather than "≥ 0.7" because the threshold is a tunable configuration value, not an architectural constant. If asked, the default is 0.7. |
| **CPU / ONNX int8 called out on `C2`** | Deployment feasibility is a standing committee concern for LLM projects. Stating "no GPU required" on the diagram closes it. |
| **Monochrome** | Survives greyscale printing and projector washout; UML carries no semantics in colour. |

---

## 10. Honest gaps — say these before the committee finds them

Volunteering a limitation reads as rigour; being caught by one reads as oversight.

1. **The human-in-the-loop step is in the diagrams but not yet in the written spec.** `ARCHITECTURE_REVIEW.md` records this (items at lines 24, 239, 544): HITL appears in Objective 2 and in both diagrams, but `RESEARCHGPT_SPEC.md §7.5` (Critic) and `PROJECT_PLAN.md §7.3` have not been updated. **Verified as still open at the time of writing.** Fix the spec before the review so all three documents agree — a reviewer who cross-checks will find the inconsistency.
2. **No fork/join concurrency is shown.** The pipeline is drawn as strictly sequential. In practice, ingestion of many PDFs is parallelisable. This is a deliberate simplification for legibility; if asked, say the parallelism is an implementation detail within the `B3` action, not an architectural fork.
3. **Persistence is not on this canvas.** No vector store, BM25 index, metadata DB or run-state store appears here. That is correct for an activity diagram — those are structural, not behavioural — but be ready to say "they are in the structural view" and point at the Module Connectivity Diagram.
4. **The retry loop `e04` has no attempt limit.** An invalid query can be resubmitted indefinitely. Harmless (it is a human at a keyboard, not an automated loop), but the asymmetry with the bounded Critic loop is fair game for a sharp reviewer.
5. **Only two source connectors are named on the canvas** (OpenAlex, arXiv). The spec lists ten (Semantic Scholar, Crossref, PubMed, ACL Anthology, OpenReview, PMLR, IEEE Xplore, Scopus). The two named are the free/keyless ones that ship first; the rest sit behind feature flags. Say this rather than letting it look like a thin source strategy.

---

## 11. Anticipated questions and prepared answers

**"Why is the Writer at the bottom of the middle lane instead of at the end of the pipeline?"**
Because it *is* at the end. It is drawn below the human step to make a structural guarantee visible: control reaches the Writer only by crossing back from the quality-control lane, after both the Critic and the human have approved. If the Writer sat directly under the Extractor, the diagram would be describing a system that can write unverified text.

**"What stops this looping forever?"**
The guard on the exit edge: `max 3 iterations`. On the third pass the system forces WRITE and records unresolved gaps in the Limitations section. Termination is guaranteed by construction, and unresolved gaps are reported rather than hidden.

**"Where is the machine learning? This looks like API calls."**
Box `C2`. A fine-tuned NLI cross-encoder that classifies each claim against its evidence span, exported to ONNX with int8 quantisation, running on CPU. It is trained by us, it has its own precision and recall figures, and it has a dedicated ablation row ("− Verifier") in the evaluation protocol.

**"What is the difference between the Verifier and the Critic?"**
Scope. The Verifier (`C1`–`C4`) works at **claim level** — is *this specific sentence* supported by *this specific span*? The Critic (`C5`, `C6`) works at **review level** — is the review as a whole adequately covered, adequately grounded, built on enough papers, with an acceptable venue mix? Claim-level filtering, then review-level gating.

**"Why does the discarded-claim path rejoin before the Critic instead of just ending?"**
Because how much was dropped is itself a quality signal. If the filter discarded most claims from a sub-question, that sub-question is now under-supported — and only the Critic, seeing the whole state, can detect that and trigger a RETRIEVE. If the discarded path simply terminated, that information would be lost.

**"What does the human actually do at `C7`?"**
They open the dropped-claims panel in the results view, see each claim the verifier flagged or discarded together with its evidence span and support score, and either confirm the machine's judgement or override it. It is a bounded, concrete task over a specific queue — not "read the whole review".

**"Why is `A8` dashed and why does nothing flow out of it?"**
It is an accept-event action — it waits for asynchronous events rather than being invoked in sequence. Nothing flows out because receiving a progress event does not advance the main control flow; it only updates the display. Drawing it in the sequential chain would falsely imply the pipeline blocks on the UI.

**"Is this diagram consistent with the Module Connectivity Diagram?"**
Yes, and they are deliberately different views. This is the **behavioural** view — what happens, in what order, under what conditions. File 02 is the **structural** view — what the modules are, how they are packaged into subsystems, and what interfaces they exchange. Every action here maps to a numbered module there; the mapping table is in the file-02 explainer.

---

## 12. Quick reference card

**Counts:** 3 partitions · 1 initial node · 1 activity final node · 4 merge nodes · 3 decision nodes · 18 actions (1 of them an accept-event action) · 2 object nodes · 29 control-flow edges · 3 signal edges · 1 legend box.

**The six agents on the canvas:** PLANNER (`B1`) · RETRIEVER (`B2`, with INGEST `B3` and RANK `B4` as its sub-stages) · EXTRACTOR (`B5`) · VERIFIER (`C1`+`C2`) · CRITIC (`C5`) · WRITER (`B9`).

**The three things to point at if you only get 30 seconds:**
1. The three lanes = the three objectives.
2. The three arrows out of the Critic diamond = agentic, not a fixed pipeline, and bounded at 3 iterations.
3. The arrow from HUMAN-IN-THE-LOOP back to WRITER = nothing is written before a human signs off.
