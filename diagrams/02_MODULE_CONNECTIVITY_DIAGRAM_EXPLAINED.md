# Module Connectivity Diagram (MCD) — Complete Walkthrough

**Companion to:** `diagrams/02_module_connectivity_diagram.drawio`
**Diagram type:** UML component diagram used as a Module Connectivity Diagram — hierarchically numbered modules, grouped into subsystem packages, connected by named interfaces.
**Purpose of this document:** if you read this file end to end, you can defend every module, every subsystem boundary, every interface name, and every arrow on that canvas.

---

## 0. How to use this document

| Section | Use it for |
|---|---|
| §1–§2 | The opening statement, and the difference between this diagram and the architecture diagram |
| §3 | Notation dictionary — shapes, stereotypes, and the solid-vs-dashed rule |
| §4 | The numbering scheme (this is what MCD marks are actually awarded for) |
| §5 | Every module, one by one |
| §6 | Every interface, one by one |
| §7 | Every connector, one by one |
| §8 | The spoken narrative |
| §9 | How this diagram maps onto the architecture diagram |
| §10 | Design decisions worth defending |
| §11 | Honest gaps — including two fixes to make before the review |
| §12 | Anticipated Q&A |

---

## 1. What this diagram is, in one sentence

It is the **structural view** of ResearchGPT: 20 numbered software modules, grouped into 4 subsystem packages under 1 top-level controller, with every inter-module connection labelled by the **named interface** and the **data or control** it carries.

## 2. How it differs from the architecture diagram — and why both exist

This is the first question a committee asks when it sees two diagrams that look like they describe the same thing. They do not.

| | `01_architecture_diagram.drawio` | `02_module_connectivity_diagram.drawio` |
|---|---|---|
| **View** | Behavioural | Structural |
| **Answers** | *What happens, in what order, under what conditions?* | *What are the parts, how are they packaged, and what do they exchange?* |
| **Notation** | UML 2.5 Activity Diagram | UML Component Diagram / Module Connectivity Diagram |
| **Primary elements** | Actions, decisions, guards, control flows | Modules, subsystems, interfaces, couples |
| **Shows loops?** | Yes — with explicit guards | Only as a single signal connector (`IReplanOrRetrieve`) |
| **Shows numbering?** | No | Yes — hierarchical, 0.0 / 1.x / 2.x.x / 3.x |
| **Shows the human step?** | Yes, as an action (`C7`) | Yes, as a boundary module (`2.2.5`) |

**The one-line answer:** *"The activity diagram tells you the order things happen in and under what conditions control loops back. The module connectivity diagram tells you what the software is actually made of, how it decomposes into subsystems, and what typed interface passes across every boundary. Behaviour and structure are two required views of one system."*

---

## 3. Notation dictionary — every mark on the canvas

| Shape as drawn | Name | Meaning |
|---|---|---|
| **Stick figure**, label below | **Actor** | An external human role. One on this canvas: `Researcher` |
| **Rectangle with two small tabs on the left edge** | **Component** (module) | A unit of software with a defined responsibility and interface. All 20 modules use this shape |
| **Folder shape** (rectangle with a tab across the top-left) | **Package / subsystem** | A grouping container. Four on this canvas. Drawn with `strokeWidth=2` — deliberately heavier than the modules inside them, so subsystem boundaries read at a glance |
| **`«component»`** | Stereotype | Marks the element as a software module |
| **`«boundary»`** | Stereotype | Marks a module that sits on the **system edge** — it touches a human or an external system rather than only other modules. Three on this canvas: `1.0`, `2.2.5`, `3.2` |
| **`«subsystem»`** | Stereotype | Marks a package as an independently deployable/testable grouping |
| **`«use»`** | Dependency stereotype | The actor depends on the interface the module offers |
| **`«signal»`** | Connector stereotype | Asynchronous / control notification rather than a data hand-off |
| **Bold module label** | — | Marks the **controller** of that subsystem (`0.0`, `1.0`, `2.1`, `2.2`, `3.0`). Bold is the only visual weight distinction between a controller and its subordinates |
| **Solid line, open arrowhead**, labelled `IXxx` | **Data couple** | A payload of information flows in the arrow's direction. 23 of the 29 connectors |
| **Dashed line, open arrowhead**, labelled `«signal» IXxx` | **Control / flag couple** | A decision, verdict, flag or acknowledgement flows — something the receiver *acts on*, not something it *processes*. 6 of the 29 connectors |
| **`I` prefix on every label** | Interface naming convention | Every connector is named for the interface it realises, not for the data informally. `IPaperInsights`, not "insights" |

### The single most important notation rule on this canvas

**Solid = data couple. Dashed «signal» = control couple.**

This is classic structured-design coupling notation, and it is the thing an examiner marks. A *data couple* is information the receiving module transforms — `IChunks` goes into the Ranker and comes out as `IRankedChunks`. A *control couple* is information that tells the receiving module **what to do** — `IDecision`, `IValidFlag`, `IHumanVerdict`, `IReplanOrRetrieve`, `IAck`. Being able to point at any dashed arrow and say "that one carries a decision, not a payload" is the difference between having drawn an MCD and having drawn a picture.

---

## 4. The numbering scheme

This is what the MCD format is really for, and it is worth 30 seconds of explanation on its own.

```
0.0   MainController                     ← top-level orchestrator
│
├── 1.0   InputController      «boundary» ← subsystem controller
│   ├── 1.1   GetQuery
│   └── 1.2   ValidateQuery
│
├── 2.1   PipelineController              ← subsystem controller
│   ├── 2.1.1  Planner
│   ├── 2.1.2  Retriever
│   ├── 2.1.3  Ingestor
│   ├── 2.1.4  Ranker
│   ├── 2.1.5  Extractor
│   └── 2.1.6  Writer
│
├── 2.2   QualityController                ← subsystem controller
│   ├── 2.2.1  ClaimDecomposer
│   ├── 2.2.2  SupportClassifier   (fine-tuned NLI, ONNX int8, CPU)
│   ├── 2.2.3  ClaimFilter
│   ├── 2.2.4  CoverageAssessor
│   └── 2.2.5  HumanReviewConsole  «boundary»
│
└── 3.0   OutputController                 ← subsystem controller
    ├── 3.1   ArtefactFormatter
    └── 3.2   ReviewPresenter      «boundary»
```

**Three properties of this numbering, each defensible:**

1. **Depth encodes decomposition.** A number's depth is how far down the hierarchy the module sits. `2.1.2` is a worker inside the pipeline subsystem, which is itself under the main controller.
2. **`2.1` and `2.2` are siblings, deliberately.** Both are level-2 controllers under `0.0`. This says the ReviewPipeline and GroundingAndQC subsystems are **peers**, not one nested in the other. That is the whole architectural argument: quality control is not a subroutine of generation, it is a co-equal subsystem that can send generation back to the start. If QC were numbered `2.1.7`, the diagram would be claiming the pipeline owns its own quality checking — which is exactly the design ResearchGPT rejects.
3. **Every module has exactly one parent.** No module is shared between subsystems. Coupling across subsystem boundaries happens only through named interfaces.

---

## 5. Module-by-module walkthrough

Exact on-canvas labels are quoted. Internal draw.io IDs are given so you can locate anything in the XML.

### 5.1 The actor and the top-level controller

| # | Label | ID | Stereotype | Responsibility |
|---|---|---|---|---|
| — | **Researcher** | `ACT` | Actor | The only external role. Appears twice in the flow: once at the start supplying the research question (`c1`), once at the end receiving the artefacts (`c29`). Drawn at the top-left so the diagram reads clockwise. |
| **0.0** | **MainController** | `MAIN` | `«component»` | The system's single entry and exit orchestrator, placed at top-centre (x = 450, y = 50) above all four subsystems. It receives the validated query from Input and dispatches it to the pipeline; at the end it receives the finished review text and dispatches it to Output. It is deliberately thin — it routes, it does not compute. In implementation terms this is the FastAPI application object plus the LangGraph graph handle. |

### 5.2 Subsystem `«subsystem» Input`  (package `PKGIN`, x = 60, y = 170)

| # | Label | ID | Stereotype | Responsibility |
|---|---|---|---|---|
| **1.0** | **InputController** | `BIN` | `«boundary» «component»` | The subsystem controller **and** a system-edge module — it is what the Researcher actually touches. Receives `IResearchQuestion` from the actor, drives `1.1` and `1.2`, and emits `IValidatedQuery` upward to `0.0`. Bold label = controller. Being both a controller and a boundary is why it carries two stereotypes. |
| **1.1** | GetQuery | `M11` | `«component»` | Captures the raw research question and the constraints — years, venues, max_papers, language. Pure acquisition, no judgement. |
| **1.2** | ValidateQuery | `M12` | `«component»` | Applies the validation rules and returns a pass/fail flag. Separated from `1.1` because acquisition and validation are different responsibilities with different failure modes and different unit tests. In implementation this is the Pydantic v2 model boundary. |

**Why validation is its own module.** A reviewer may ask why one module could not do both. Because the retry loop in the activity diagram (`e04`, `[invalid]`) needs a distinct decision point to loop back to. One combined module would hide the decision inside itself and make the loop unrepresentable.

### 5.3 Subsystem `«subsystem» ReviewPipeline`  (package `PKGP1`, x = 60, y = 560)

The generation subsystem — Objective 1.

| # | Label | ID | Responsibility |
|---|---|---|---|
| **2.1** | **PipelineController** | `PC` | Subsystem controller. Owns the graph state and dispatches the six workers. It is the module that receives results back from the chain (`c12`), hands them to Quality Control (`c13`), receives the verdict back (`c21`), receives replan/retrieve signals (`c22`), and finally releases the Writer (`c23`). In implementation this is the LangGraph state machine. |
| **2.1.1** | Planner | `M211` | Decomposes the research question into 4–8 sub-questions by facet (method / application / evaluation / limitation) and emits a search plan with per-sub-question source priorities and year filters. On replan it must emit a *different* plan and record the diff. |
| **2.1.2** | Retriever | `M212` | Federated search across source connectors; normalises hits to a `Paper` model; deduplicates by DOI with a normalised title+year fallback; screens against inclusion criteria; assigns venue tier. Rule: never fabricate metadata — an unresolvable field is `None`, never guessed. |
| **2.1.3** | Ingestor | `M213` | PDF parsing (PyMuPDF, optionally GROBID for section and reference structure), cleaning, **section-aware chunking** with character offsets, and embedding. The character offsets it produces are what make claim-level evidence spans possible six modules downstream. |
| **2.1.4** | Ranker | `M214` | Hybrid retrieval: BM25 sparse + dense vector, fused by Reciprocal Rank Fusion, reranked by a cross-encoder (`BAAI/bge-reranker-v2-m3`), truncated to top-12 per sub-question. |
| **2.1.5** | Extractor | `M215` | **Produces the four-field structured insight per paper** — `methodology`, `advantages`, `disadvantages`, `critique` — plus `datasets`, `metrics`, `results`, `limitations`, `cluster` (C1–C6), and `evidence_spans[]`. Rule: every field carries a chunk_id and character offsets; a field with no locatable span is `null` with an `extraction_note`. This module is one of the five claimed contributions and is the source of `insights.csv`. |
| **2.1.6** | Writer | `M216` | Thematic synthesis into the final review with IEEE numeric citations `[n]`, preprints labelled `[preprint]`. Consumes `IVerifiedClaims` **only**. Rule: no sentence may be written that is not backed by a verified claim. |

**Why Ingestor and Ranker are separate modules when the spec folds them into the Retriever agent.** Because MCD requires single-responsibility modules and because the evaluation protocol ablates them independently — there is an ablation row for "− hybrid retrieval (dense only)" and a separate one for "− reranker". A module you ablate separately must be drawn separately. Say it as: **"six agents, nine pipeline-side modules; Ingestor and Ranker are sub-modules of the Retriever agent, drawn separately because they are independently testable and independently ablated."**

### 5.4 Subsystem `«subsystem» GroundingAndQC`  (package `PKGP2`, x = 900, y = 60)

The quality subsystem — Objective 2. It is the widest package (460 px) and is placed on the **right-hand side, level with the top of the canvas**, deliberately opposite the pipeline rather than below it — reinforcing the peer relationship established by the `2.1` / `2.2` numbering.

| # | Label | ID | Responsibility |
|---|---|---|---|
| **2.2** | **QualityController** | `QC` | Subsystem controller. Receives `IPaperInsights` from `2.1`, drives the five QC workers, and returns either `IVerifiedClaims` (proceed) or an `IReplanOrRetrieve` signal (loop) to `2.1`. It is the module that owns the iteration counter and enforces the 3-iteration bound. |
| **2.2.1** | ClaimDecomposer | `M221` | Breaks each structured insight into **atomic claims** — independently checkable single assertions. Atomicity is a precondition for a meaningful support judgement: a compound claim can be half-supported, and half-supported is not a decidable verdict. |
| **2.2.2** | SupportClassifier<br>*fine-tuned NLI, ONNX int8, CPU* | `M222` | **The trained model.** A natural-language-inference cross-encoder scoring each (claim, evidence span) pair, emitting a verdict — SUPPORTED / PARTIAL / UNSUPPORTED / CONTRADICTED — with `support_score ∈ [0,1]`. The italic subtitle is on the canvas on purpose: *fine-tuned* (it is trained, it has precision/recall numbers, it has its own ablation row), *ONNX int8* (quantised and small), *CPU* (no GPU required anywhere in this system). This is the box to point at when asked "where is the ML?" |
| **2.2.3** | ClaimFilter | `M223` | Applies the threshold (default **0.7**) and **splits the stream in two** — the only module on the canvas with two distinct outgoing data couples. Claims at or above threshold leave as `IVerifiedClaims`; claims below leave as `IDroppedClaims`. Dropped claims are discarded from the write path and logged, never hedged into the output. |
| **2.2.4** | CoverageAssessor | `M224` | The Critic. Assesses the review as a whole against concrete thresholds: sub-question coverage ≥ 80%, ≥ 20 papers retained, grounding score ≥ 0.75, no sub-question with fewer than 2 supporting papers, plus venue-tier mix and recency window. Emits `«signal» IDecision` — WRITE / RETRIEVE / REPLAN. |
| **2.2.5** | HumanReviewConsole | `M225` | `«boundary» «component»` — the human-in-the-loop module. Receives `IDroppedClaims` and presents each one with its evidence span and support score so the analyst can **confirm or override** the machine's judgement. Returns `«signal» IHumanVerdict` to the QualityController. It carries the `«boundary»` stereotype because a human operates it directly. This module is what makes the human-in-the-loop clause of Objective 2 a real component rather than a promise. |

**The Verifier/Critic split, stated precisely.** In the six-agent naming, the **Verifier agent** = modules `2.2.1` + `2.2.2` + `2.2.3` (claim-level: is *this sentence* supported by *this span*?). The **Critic agent** = module `2.2.4` (review-level: is the review *as a whole* adequately covered and grounded?). `2.2.5` is not an agent at all — it is a human interface. Say this crisply; the mapping between "six agents" and "five QC modules" is a question you will get.

### 5.5 Subsystem `«subsystem» Output`  (package `PKGOUT`, x = 870, y = 1210)

Objective 3's delivery half.

| # | Label | ID | Responsibility |
|---|---|---|---|
| **3.0** | **OutputController** | `OC` | Subsystem controller. Note it is numbered `3.0`, not `3`, matching `1.0` — both are direct children of `0.0`. Receives `IReviewText` from `0.0` and drives formatting and presentation. |
| **3.1** | ArtefactFormatter | `M31` | Renders the review text into the four deliverable formats: `review.md`, `insights.csv`, `refs.bib` (BibTeX, IEEE style), and `trace.jsonl`. DOCX via python-docx is in the spec as a fifth. Formatting is separated from presentation because the same artefacts must be producible headlessly, without a UI. |
| **3.2** | ReviewPresenter | `M32` | `«boundary» «component»` — the results view. Displays the review with clickable evidence spans and the dropped-claims panel, and delivers `IArtefacts` to the Researcher. Returns `«signal» IAck` to the controller. |

---

## 6. Interface catalogue

Twenty named interfaces. Each is a real contract, and most correspond directly to a Pydantic model or a graph-state key in `RESEARCHGPT_SPEC.md §8`.

| Interface | Carried on | Kind | Payload |
|---|---|---|---|
| `IResearchQuestion` | `c1` | data («use») | The research question and constraints from the actor |
| `IRawQuery` | `c2`, `c3` | data | Unvalidated query text + constraints |
| `IValidFlag` | `c4` | **control** | Pass/fail result of validation |
| `IValidatedQuery` | `c5`, `c6` | data | The validated, typed query object (`:ResearchQuery [validated]` in the activity diagram) |
| `IQuery` | `c7` | data | The query as handed to the Planner |
| `ISearchPlan` | `c8` | data | `search_plan[]` — per-sub-question query, sources, year filters, max results |
| `IPapers` | `c9` | data | `papers[]` — deduplicated, screened, venue-tiered |
| `IChunks` | `c10` | data | `chunks[]` — section-tagged, with character offsets |
| `IRankedChunks` | `c11` | data | Top-12 fused and reranked chunks per sub-question |
| `IPaperInsights` | `c12`, `c13`, `c14` | data | `paper_insights[]` — the four-field schema plus evidence spans. Note it appears on three consecutive connectors as it travels Extractor → PipelineController → QualityController → ClaimDecomposer |
| `IAtomicClaims` | `c15` | data | Decomposed single assertions |
| `ISupportScores` | `c16` | data | Per-claim verdict + `support_score ∈ [0,1]` |
| `IVerifiedClaims` | `c17`, `c21`, `c23` | data | Claims at or above threshold — the only thing the Writer is permitted to consume |
| `IDroppedClaims` | `c18` | data | Claims below threshold, routed to the human console |
| `IHumanVerdict` | `c19` | **control** | The analyst's confirm-or-override decision |
| `IDecision` | `c20` | **control** | WRITE / RETRIEVE / REPLAN |
| `IReplanOrRetrieve` | `c22` | **control** | The bounded feedback signal — labelled on canvas *"bounded, max 3 iterations"* |
| `IReviewText` | `c24`, `c25`, `c26` | data | The synthesised review |
| `IArtefacts` | `c27`, `c29` | data | The formatted deliverables |
| `IAck` | `c28` | **control** | Delivery acknowledgement |

Six control couples (`IValidFlag`, `IHumanVerdict`, `IDecision`, `IReplanOrRetrieve`, `IAck`, plus the `«use»` dependency `c1`), twenty-three data couples. **A low control-couple count relative to data couples is a good structured-design property** — it means modules mostly transform information rather than instruct each other. If asked about coupling quality, this is the number to cite.

---

## 7. Connector-by-connector walkthrough

### 7.1 Input path — `c1` to `c6`

| ID | From → To | Label | Note |
|---|---|---|---|
| `c1` | Researcher → `1.0` | `«use» IResearchQuestion` | Dashed — a UML dependency, not a data flow. The actor *depends on* the interface the boundary module offers |
| `c2` | `1.0` → `1.1` | `IRawQuery` | Controller dispatches to acquisition |
| `c3` | `1.1` → `1.2` | `IRawQuery` | Acquisition hands to validation |
| `c4` | `1.2` → `1.0` | `«signal» IValidFlag` | **Dashed — control couple.** The validator returns a *flag*, not data. Routed out the right side through waypoints (430, 392) and (430, 240) so the return path is visibly distinct from the forward path |
| `c5` | `1.0` → `0.0` | `IValidatedQuery` | Subsystem hands up to the main controller |
| `c6` | `0.0` → `2.1` | `IValidatedQuery` | Main controller dispatches into the pipeline |

### 7.2 Pipeline path — `c7` to `c12`

| ID | From → To | Label |
|---|---|---|
| `c7` | `2.1` → `2.1.1` | `IQuery` |
| `c8` | `2.1.1` → `2.1.2` | `ISearchPlan` |
| `c9` | `2.1.2` → `2.1.3` | `IPapers` |
| `c10` | `2.1.3` → `2.1.4` | `IChunks` |
| `c11` | `2.1.4` → `2.1.5` | `IRankedChunks` |
| `c12` | `2.1.5` → `2.1` | `IPaperInsights` — routed out the left side through waypoints (100, 937) and (100, 580), returning up to the controller |

**Why the chain runs sibling-to-sibling but returns to the controller.** Workers `2.1.1` → `2.1.5` pass data laterally, then the *terminal* worker returns the aggregate result up to `2.1`. This is exactly how a LangGraph state machine behaves: nodes are wired to each other by graph edges, but the graph runtime — the PipelineController — owns the accumulated state and decides what happens next. Drawing every hand-off as a round trip through the controller would be structurally accurate for a pure structure chart but would misrepresent the orchestration technology and add twelve arrows for no information.

### 7.3 Quality control path — `c13` to `c20`

| ID | From → To | Label | Note |
|---|---|---|---|
| `c13` | `2.1` → `2.2` | `IPaperInsights` | **The subsystem crossing.** Generation hands off to grounding |
| `c14` | `2.2` → `2.2.1` | `IPaperInsights` | Controller dispatches |
| `c15` | `2.2.1` → `2.2.2` | `IAtomicClaims` | Decomposed for classification |
| `c16` | `2.2.2` → `2.2.3` | `ISupportScores` | Scored, awaiting the threshold |
| `c17` | `2.2.3` → `2.2.4` | `IVerifiedClaims` | The **kept** branch → the Critic |
| `c18` | `2.2.3` → `2.2.5` | `IDroppedClaims` | The **dropped** branch → the human console. Routed out the right side through waypoints (1010, 812) and (1010, 960). This one arrow is the entire human-in-the-loop input path |
| `c19` | `2.2.5` → `2.2` | `«signal» IHumanVerdict` | **Dashed — control.** The analyst's confirm/override returns to the controller, not to the filter. Routed far left through (620, 960) and (620, 580) |
| `c20` | `2.2.4` → `2.2` | `«signal» IDecision` | **Dashed — control.** WRITE / RETRIEVE / REPLAN. Routed through (640, 882) and (640, 600) — 20 px inboard of `c19` so the two control returns run parallel without overlapping |

**The `2.2.3` fork is the most information-dense point on the canvas.** One module, two outgoing data couples with different names and different destinations. That single fork is the mechanical realisation of "unverifiable claims are dropped, not softened": the two streams physically separate, and only one of them can ever reach the Writer.

### 7.4 The feedback signal — `c21` and `c22`

| ID | From → To | Label | Note |
|---|---|---|---|
| `c21` | `2.2` → `2.1` | `IVerifiedClaims` | The **approved** return path. Solid — this is data |
| `c22` | `2.2` → `2.1` | `«signal» IReplanOrRetrieve`<br>*bounded, max 3 iterations* | The **loop** return path. Dashed — this is control. Routed out the *bottom* of both controllers through waypoints (810, 1160) and (260, 1160), so it sweeps across the base of the canvas, well clear of everything else |

**These two arrows are the structural equivalent of the three-way Critic diamond in the activity diagram.** Two returns exist between the same two modules because they are different *kinds* of return: one carries a payload to proceed with, the other carries an instruction to go back. Drawing them as one arrow would collapse the entire agentic-loop contribution into an ambiguity. The iteration bound is written on the connector label for the same reason it is written on the activity-diagram guard: termination is the first thing anyone asks about an agentic system.

### 7.5 Write-out and delivery — `c23` to `c29`

| ID | From → To | Label | Note |
|---|---|---|---|
| `c23` | `2.1` → `2.1.6` | `IVerifiedClaims` | **The Writer is released.** Note the source: the controller, *after* it has received the verified claims back from QC via `c21`. The Writer is unreachable by any other path — there is no arrow from `2.1.5` Extractor to `2.1.6` Writer. That absence is intentional and is the structural guarantee that unverified content cannot be written |
| `c24` | `2.1.6` → `0.0` | `IReviewText` | Routed up the middle through (510, 1040), (530, 1040), (530, 140) into the bottom of the main controller |
| `c25` | `0.0` → `3.0` | `IReviewText` | Routed out the far left through (30, 80) and (30, 1270) — the long sweep down the left edge of the canvas |
| `c26` | `3.0` → `3.1` | `IReviewText` | Controller dispatches to formatting |
| `c27` | `3.1` → `3.2` | `IArtefacts` | Formatted artefacts to the presenter |
| `c28` | `3.2` → `3.0` | `«signal» IAck` | **Dashed — control.** Delivery acknowledgement, routed through (430, 1422) and (430, 1270) |
| `c29` | `3.2` → Researcher | `IArtefacts` | **The system closes the loop with the actor it started with.** Routed left through (150, 1422) up into the actor. A well-formed MCD begins and ends at the same actor; this arrow is what makes that true |

---

## 8. The spoken narrative

Roughly 90 seconds. Trace with a pointer.

> "This is the structural view — the module connectivity diagram. Twenty modules, hierarchically numbered, in four subsystems under one main controller. Every connector is labelled with the interface it realises. Solid arrows are data couples; dashed arrows marked «signal» are control couples — decisions and flags rather than payloads.
>
> **[Top left]** The Researcher uses interface `IResearchQuestion` on module `1.0`, the InputController — a boundary module, meaning it sits on the system edge. It drives `1.1` GetQuery and `1.2` ValidateQuery; validation returns a control flag, and the validated query goes up to `0.0` MainController.
>
> **[Left column]** `0.0` dispatches into `2.1`, the PipelineController. Planner produces a search plan, Retriever produces papers, Ingestor produces chunks with character offsets, Ranker produces the top-12 fused and reranked chunks, and Extractor produces our four-field paper insights. Those come back up to the controller.
>
> **[Across to the right]** `2.1` hands the insights across the subsystem boundary to `2.2`, the QualityController. Notice the numbering: `2.1` and `2.2` are siblings, not parent and child — quality control is a peer subsystem, not a subroutine of generation.
>
> **[Right column]** ClaimDecomposer breaks insights into atomic claims. SupportClassifier — our fine-tuned NLI cross-encoder, int8 ONNX, running on CPU — scores each claim against its evidence span. Then `2.2.3` ClaimFilter forks the stream: verified claims go up to the CoverageAssessor, dropped claims go across to `2.2.5`, the HumanReviewConsole, where an analyst confirms or overrides. Both return control signals — `IDecision` and `IHumanVerdict` — to the controller.
>
> **[The two arrows between 2.2 and 2.1]** And here is the loop. Two returns, deliberately separate. The solid one carries verified claims so the pipeline can proceed. The dashed one carries a replan-or-retrieve instruction, bounded at three iterations — that label is on the connector.
>
> **[Bottom of the left column, then across]** Only once verified claims come back does `2.1` release `2.1.6`, the Writer. There is no arrow from the Extractor to the Writer — the Writer is structurally unreachable except through quality control.
>
> **[Bottom right, then back to the actor]** The review text goes up to `0.0`, across to `3.0` OutputController, is formatted into markdown, CSV, BibTeX and the trace log by `3.1`, and delivered by `3.2` ReviewPresenter back to the same Researcher who started."

---

## 9. Mapping to the architecture diagram

Have this table ready. "Are your two diagrams consistent?" is a near-certain question.

| Activity diagram element (file 01) | MCD module (file 02) |
|---|---|
| `A1` Submit research question | `1.1` GetQuery |
| `A2` Query valid? | `1.2` ValidateQuery |
| `A3` REST POST /api/review | `1.0` InputController → `0.0` MainController |
| `B1` PLANNER | `2.1.1` Planner |
| `B2` RETRIEVER | `2.1.2` Retriever |
| `B3` INGEST | `2.1.3` Ingestor |
| `B4` RANK | `2.1.4` Ranker |
| `B5` EXTRACTOR | `2.1.5` Extractor |
| `C1` VERIFIER (decompose) | `2.2.1` ClaimDecomposer |
| `C2` CLASSIFY (fine-tuned NLI) | `2.2.2` SupportClassifier |
| `C3` / `C4` threshold + discard | `2.2.3` ClaimFilter |
| `C5` / `C6` CRITIC + decision | `2.2.4` CoverageAssessor |
| `C7` HUMAN-IN-THE-LOOP | `2.2.5` HumanReviewConsole |
| `B9` WRITER | `2.1.6` Writer |
| `A9` Display with evidence spans | `3.2` ReviewPresenter |
| `A10` Download four artefacts | `3.1` ArtefactFormatter |
| `e22` `[RETRIEVE]` + `e23` `[REPLAN]` | `c22` `«signal» IReplanOrRetrieve` |
| `e24` `[WRITE]` | `c21` `IVerifiedClaims` |
| `e25` `C7` → `B9` | `c19` → `c21` → `c23` |

**The mapping is total in one direction:** every action in the activity diagram has a module here. It is *not* total in the other — see gap 2 in §11.

---

## 10. Design decisions worth defending

| Decision | Justification |
|---|---|
| **`2.1` and `2.2` numbered as siblings** | Quality control is a peer subsystem, not a subroutine of generation. Numbering QC as `2.1.7` would misrepresent the architecture's central claim |
| **Three `«boundary»` modules** (`1.0`, `2.2.5`, `3.2`) | These are the three places a human touches the system: submitting a query, adjudicating dropped claims, and receiving results. Marking them explicitly makes the human-facing surface countable |
| **Every connector named `IXxx`** | Naming the *interface* rather than the data makes each arrow a testable contract. Each maps to a Pydantic model or a graph-state key |
| **Solid vs dashed «signal» distinction enforced throughout** | It is the coupling-quality argument. Six control couples against twenty-three data couples is a favourable ratio |
| **`c21` and `c22` drawn as two separate arrows** | They are different kinds of return — payload vs instruction. Merging them would erase the agentic-loop contribution |
| **No arrow from `2.1.5` Extractor to `2.1.6` Writer** | Deliberate absence. The Writer is reachable only via `c23`, which is only reachable after QC returns. The guarantee is structural, not procedural |
| **Ingestor and Ranker as distinct modules** | Independently testable, independently ablated in the evaluation protocol |
| **Monochrome, `fillColor=none`** | Survives greyscale print and projector washout; UML carries no semantics in colour |

---

## 11. Honest gaps — two of these should be fixed before the review

1. **The subsystem packages have lost their objective labels — fix this.** The four package headers currently read `«subsystem» Input`, `«subsystem» ReviewPipeline`, `«subsystem» GroundingAndQC`, `«subsystem» Output`. An earlier version of this file carried the objective suffixes (`— OBJECTIVE 3`, `— OBJECTIVE 1`, `— OBJECTIVE 2`, `— OBJECTIVE 3`), and the architecture diagram's swimlanes still carry theirs. Restoring them costs four label edits and restores objective traceability to the structural view. **Recommended before the review.** The intended mapping is: Input → Objective 3, ReviewPipeline → Objective 1, GroundingAndQC → Objective 2, Output → Objective 3.

2. **The real-time progress path is absent from this diagram.** The activity diagram has three `«signal»` SSE edges into `A8`, discharging the "real-time progress visibility" clause of Objective 3. There is no corresponding structure here — no progress-emitter module, and no signal connectors from `2.1.1` / `2.1.4` / `2.2.4` to a presentation module. Either add a `3.3 ProgressStreamer` boundary module with three inbound signals, or be ready to say: *"progress emission is a cross-cutting concern handled by the tracing layer, deliberately omitted here to keep the module decomposition legible."* The first is stronger. Note that `3.2` ReviewPresenter and the Output subsystem sit at the bottom of the canvas while the emitters are at the top, so adding these arrows will need care.

3. **`2.2.5` HumanReviewConsole has no arrow to or from the Researcher actor.** It carries the `«boundary»` stereotype, which by definition means an external role operates it — but no actor connection is drawn. A `«use» IClaimAdjudication` dependency from the Researcher would make the human-in-the-loop story complete and would match how `1.0` and `3.2` are wired.

4. **Persistence is not represented.** No vector store, BM25 index, paper-metadata DB, or run-state/trace store appears. The spec defines all four. If asked, either say they are a fourth `«subsystem» Persistence` intentionally deferred to a deployment diagram, or add them. Be ready — "where is your data stored?" is a standard question.

5. **The service layer is not represented.** The LLM adapter (LiteLLM), Index Service, Source Connectors, and Citation Service from `RESEARCHGPT_SPEC.md §3` are absorbed into the modules that use them rather than drawn as shared services. Defensible — an MCD shows application modules, not infrastructure — but say it deliberately rather than appearing to have forgotten them.

6. **Human-in-the-loop is still missing from the written spec.** `ARCHITECTURE_REVIEW.md` (lines 24, 239, 544) flags that HITL appears in Objective 2 and in both diagrams but not in `RESEARCHGPT_SPEC.md §7.5` or `PROJECT_PLAN.md §7.3`. **Verified as still open at the time of writing.** A reviewer who cross-reads the spec will find the inconsistency. Fix the spec.

---

## 12. Anticipated questions and prepared answers

**"Why do you have two diagrams? Isn't this the same system twice?"**
Different views of the same system. The activity diagram is behavioural — order of execution, conditions, loops, guards. This is structural — decomposition, packaging, and the typed interface across every boundary. Neither can express the other: an activity diagram cannot show that `2.1` and `2.2` are peer subsystems, and a component diagram cannot show that the loop is bounded at three iterations under a guard. §9 has the element-by-element mapping between them.

**"Why is quality control `2.2` and not `2.1.7`?"**
Because it is a peer of the pipeline, not a part of it. `2.2` can send control back to `2.1` — a subroutine cannot redirect its own caller. The numbering encodes the architectural claim.

**"What is the difference between the solid and dashed arrows?"**
Solid arrows are data couples — a payload the receiving module transforms. Dashed `«signal»` arrows are control couples — a decision or flag the receiving module acts on. There are six control couples on this canvas: `IValidFlag`, `IHumanVerdict`, `IDecision`, `IReplanOrRetrieve`, `IAck`, and the `«use»` dependency from the actor. Twenty-three data couples. A low control-to-data ratio is the coupling-quality property structured design asks for.

**"How do I know the Writer cannot write unverified content?"**
Look for an arrow from `2.1.5` Extractor to `2.1.6` Writer. There isn't one. The Writer's only inbound connector is `c23` from the PipelineController, and the controller only holds verified claims after `c21` returns them from quality control. The guarantee is structural — it does not depend on anyone remembering to check.

**"You show six agents in the spec but nine modules in the pipeline and five in QC. Which is it?"**
Agents are the orchestration units; modules are the software units, and they are a finer decomposition. Planner, Retriever, Extractor and Writer map one-to-one. The Retriever agent decomposes into `2.1.2` Retriever, `2.1.3` Ingestor and `2.1.4` Ranker because those three are independently testable and independently ablated. The Verifier agent decomposes into `2.2.1`, `2.2.2` and `2.2.3`. The Critic agent is `2.2.4`. `2.2.5` is not an agent — it is a human interface.

**"What are the `«boundary»` modules?"**
The three system-edge modules a human touches: `1.0` InputController (query submission), `2.2.5` HumanReviewConsole (claim adjudication), `3.2` ReviewPresenter (results). Everything else talks only to other modules.

**"Where is the machine learning?"**
Module `2.2.2` SupportClassifier — a fine-tuned NLI cross-encoder, exported to ONNX with int8 quantisation, running on CPU. It is the only trained component; everything else is orchestration, retrieval, or prompting. It has its own precision/recall targets and its own ablation row in the evaluation protocol.

**"Where is your data stored?"**
The spec defines four stores — vector store (Chroma → Qdrant), BM25 index, paper-metadata DB, and run-state/trace store. They are not on this canvas because an MCD shows application module decomposition; persistence belongs in a deployment or data-architecture view. *(See gap 4 — decide before the review whether to add a `«subsystem» Persistence` package or defend the omission.)*

**"How does the user see progress while this runs?"**
Over server-sent events, emitted from the Planner, the Ranker and the Critic — shown as the three dashed `«signal»` edges in the activity diagram. *(See gap 2 — that path has no counterpart on this canvas yet.)*

---

## 13. Quick reference card

**Counts:** 1 actor · 20 modules · 4 subsystem packages · 5 controllers (`0.0`, `1.0`, `2.1`, `2.2`, `3.0`) · 3 `«boundary»` modules · 29 connectors (23 data, 6 control) · 20 named interfaces.

**Layout:** `0.0` top-centre. Left column top-to-bottom: Input, then ReviewPipeline. Right column: GroundingAndQC top, Output bottom. The flow reads clockwise, starting and ending at the Researcher.

**The three things to point at if you only get 30 seconds:**
1. `2.1` and `2.2` are **siblings** — quality control is a peer subsystem, not a subroutine.
2. `2.2.3` ClaimFilter **forks** into verified and dropped, and the dropped stream goes to a human console.
3. There is **no arrow from Extractor to Writer** — the Writer is structurally unreachable except through quality control.
