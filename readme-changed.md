# What `demonstration-v2` changes

Branched from `demonstration` (`c05b29c`). Everything below is a difference
against that branch. Three groups: the frontend gained a `/models` route, the
`diagrams/` folder was corrected and consolidated, and the Review-3 deck was
built, merged and proof-read. The decks and the rendered slides are committed
here even though `.gitignore` excludes `*.pptx`, so the review material travels
with the code (`git add -f`).

---

## 1. Frontend — a new `/models` route

`demonstration` said *which* models were trained and what they scored. It never
said *what the model is*. `/models` answers that.

### New files

| File | What it is |
|---|---|
| `frontend/src/components/ModelsView.vue` | the page: three headline tiles, then one card per model with its architecture drawing, a structure table, a training table and a results table |
| `frontend/src/components/diagrams/ArchBox.vue` | one labelled block in a figure — title, subtitle, monospace shape line, six tones |
| `frontend/src/components/diagrams/ArchArrow.vue` | a connector with an arrowhead, orthogonal or straight, optional label |
| `frontend/src/components/diagrams/RankerArch.vue` | the cross-encoder: one sequence in, 6 encoder layers, `[CLS]` to linear to one relevance logit |
| `frontend/src/components/diagrams/SummaryArch.vue` | BART: two lanes, 6 encoder and 6 decoder layers, cross-attention between them, LM head tied to the embedding |
| `frontend/src/components/diagrams/VerifierArch.vue` | DeBERTa-v3: disentangled attention drawn as its two streams (content-to-position and position-to-content), no position embedding added at the input, 3-way softmax head |
| `frontend/ssr-diagrams.mjs` | server-renders the three figures to standalone `.svg` — `npm run diagrams [outDir]` |

### Changed files

| File | Change |
|---|---|
| `frontend/src/App.vue` | path-based routing extended: `/` and `/dashboard` to the dashboard, `/models` to the new page, anything else to the app. `boot()` no longer runs on the two public pages |
| `frontend/src/components/AppHeader.vue` | a third nav entry, "Models — the three trained models, drawn" |
| `frontend/src/style.css` | an `@layer components` block of `.arch-*` tokens (box, tones, title, sub, mono, caption, lane, line, arrowhead, group) with `.dark` variants, so the figures theme with the rest of the app |
| `frontend/package.json` | `"diagrams": "node ssr-diagrams.mjs"` |
| `frontend/src/components/DashboardView.vue` | ROUGE-L corrected 30.81 to 29.44; the word *fine-tuned* removed from the prose and the comments |

### Why inline SVG and not Mermaid

Mermaid draws a flowchart. It cannot draw a transformer — there is no
repeat-stack, no residual, and no two-lane encoder/decoder — and it arrives
with its own palette to fight the design tokens plus a re-render on every theme
change. The hand-authored SVG is about 9 kB, themes with the app, and prints.

### Every structural number is read from the checkpoint

The layer counts, hidden sizes, head counts, feed-forward widths and vocabulary
sizes in both the figures and the tables come from each checkpoint's own
`config.json`. A number on this page and a number in the checkpoint cannot
drift apart.

### Wording rules applied across the frontend

* The word **finetune / fine-tuned** does not appear anywhere. It is **trained**.
* **No cloud API provider or vendor is named anywhere.** All models are
  presented as self-hosted.
* Checkpoint labels are shortened to `macro-MiniLm`, `bart`, `deberta`.

### Metrics, aligned with the landing page

| Model | Reported |
|---|---|
| Ranker (`macro-MiniLm`, 22M) | Recall@20 0.775 · nDCG@10 0.762 · Precision@12 0.758 · nDCG@10 on the SciReviewGen test set 0.791 · relevance control violations 0 of 15 |
| Summary generation (`bart`, 139M) | ROUGE-1 33.82 · ROUGE-2 27.81 · ROUGE-L 29.44 |
| Verifier (`deberta`, 44M) | Macro-F1 0.873 · accuracy 0.881 · SUPPORT recall 0.866 · SUPPORT precision 0.884 · NOT ENOUGH INFO F1 0.859 |

Headline tiles: **3** models trained · **205M** parameters combined
(22M + 139M + 44M) · **int8** deployed precision.

### Deliberately removed from the results tables

* the **stock** column — the comparison is not the point, the measurement is;
  the remaining column is named **Measured**
* the **Train time** rows (305.8 s on free GPU) on all three models
* **BERTScore-F1**
* the **CPU inference / no GPU at run time** stat tile
* the `delta()` helper, which only existed to compute stock-versus-trained

---

## 2. Diagrams

### The authoritative set

| Figure | File |
|---|---|
| Architecture | `diagrams/researchgpt_architecture.drawio` |
| Module connectivity (MCD) | `diagrams/02_module_connectivity_diagram.drawio` |
| Class | `diagrams/class diagram - new.drawio` |
| Sequence | `diagrams/sequence diagram - new.drawio` |
| Use case | `diagrams/use-case - new.drawio` |
| Activity | `diagrams/activity diagram - new - new.drawio` |

### Planner as Mediator (GoF)

The class, sequence and module diagrams previously disagreed about who
orchestrates the run, and the class diagram had **no** edge at all from the
Planner to the agents. All three now state the same thing:

* `Planner` holds `- _stages : List<Agent> {ordered}` and exposes
  `+ dispatch(stage, state) : Dict`
* an association Planner "1" to Agent "6", labelled "«dispatches» stages",
  constrained by `{ stages excludes the Planner itself }`
* in the MCD the pipeline is ten mediator calls — the Planner calls a stage,
  the stage returns to the Planner — instead of stages handing sideways to each
  other

### Architecture diagram — corrected without moving the layout

The three bands, the input and output columns, the API and DB row and the node
styling all stay exactly where they were. What changed:

* the **Critic moved to the end** of the pipeline and the "gaps found" loop back
  to the Retriever was deleted, which is what makes the flow straight-through
* **Ranker** and **Paper Cache** added in the empty strip inside the pipeline
  band, so nothing above them had to move
* **arXiv API** added in the existing gap between the two API boxes — three
  sources now, not two
* the sources no longer write straight to the store; the Retriever collects
* five node labels rewritten to describe what the system actually does

### Module connectivity diagram

Replaced with the component diagram, then corrected: `Ranker Module`,
`Paper Cache Module` and `arXiv Client Module` added, the pipeline relaid in
execution order, the Critic's "gap-found" edge to the Retriever removed, the
missing `2.2.2 SupportClassifier` component drawn (two edges already referenced
it), and the `IReplanOrRetrieve` signal removed.

### Superseded files, kept for history

These are earlier drafts. They are **not** the diagrams in the deck:
`01_architecture_diagram.drawio`, `Mcd - new.drawio`, `class-diagram.drawio`,
`sequence-diagram.drawio`, `use-case-diagram.drawio`,
`use-case - final.drawio`, `activity-diagram.drawio`,
`researchgpt_component_diagram (1).xml`,
`01_ARCHITECTURE_DIAGRAM_EXPLAINED.md`,
`02_MODULE_CONNECTIVITY_DIAGRAM_EXPLAINED.md`.

### `.gitignore`

`.$*.bkp` added. draw.io desktop drops a `.$<name>.bkp` beside every file it
opens; they are stale copies of diagrams that are already tracked.

---

## 3. The Review-3 deck

`documents/review-3 DS C06 main file.pptx` — **82 slides**, Review-2 and
Review-3 merged into one file.

| Slides | Content |
|---|---|
| 1–4 | title, abstract, introduction |
| 5–42 | literature survey |
| 43–46 | limitations of existing systems, research gap |
| 47–51 | problem statement, objectives, software and hardware |
| 52–65 | the six diagrams, each with a description slide |
| 66–67 | dataset details |
| 68–73 | test cases (screenshot placeholders) |
| 74–75 | experimental results |
| 76–77 | significance and advantages, limitations |
| 78–82 | status and references |

### Content rules applied throughout

* **No inference provider or cloud API vendor is named anywhere in the deck.**
  Models are named; the vendor running them is not. All models are presented as
  self-hosted.
* "abstract-only conditioning" removed everywhere — the application requests the
  PDF and stores it in the cache, and the Extractor reads full text from there.
* "one in ten paper" became **one to ten ratio** (six occurrences: slides 3, 4,
  53, 57, 61, 65).
* The **Verifier** is presented as the contribution: no surveyed system does
  claim-level grounding against the cached source, and this one does.
* Summary-generation ROUGE-L is **29.44** throughout.

### References

Two papers were dropped — Li et al. (cited text spans) and Huang and Huang (RAG
survey) — including their dedicated slides, their survey-table rows and their
reference entries. Every remaining bracketed number was renumbered in one pass
to a contiguous **1–23**, and Research Gap 4, which cited one of the dropped
papers, was rewritten. All 50 citation lines verified at 16 pt.

### Every figure description matches its diagram

The six description slides were rewritten against the diagrams as they now
stand — the architecture description no longer describes activity partitions,
the MCD description describes three subsystems and a Planner that calls all six
stages, the class description no longer names classes the redrawn diagram does
not contain, and the one-to-ten cut is described as a step rather than a guarded
decision node.

### New document files

| File | What it is |
|---|---|
| `documents/REVIEW3_SCREENSHOT_LIST.md` | the figure brief — Figures 1–4 are the diagrams, Figures 5–10 are the screenshots to capture |
| `documents/figures/*.svg`, `*.png` | the three model-architecture figures, rendered from the Vue components by `npm run diagrams` — the same drawings the `/models` page shows |
| `documents/slides-png/slide-01.png` … `slide-82.png` | every slide of the merged deck as a PNG, so the deck is reviewable without PowerPoint |
| `documents/changes.txt.txt` | the change list this branch worked through |

### Decks committed over `.gitignore`

`*.pptx` is ignored by rule; these were force-added:
`review-3 DS C06 main file.pptx` (the deliverable),
`PWP1 - Review 2 - DSC06.pptx`,
`PWP1 - Review 3 - DSC06 (Slide 19 onwards).pptx`, `Review-1 dsc06.pptx`, and
the two section templates.

---

## 4. Carried along, not authored here

`documents/TRAINING_SPEC.md` gained a row splitting the Extractor and Writer out
of the prompted group and into the trained one. That edit was made on the
working tree before this branch existed and is committed here so it is not lost.

---

## 5. Known open items

Listed so a reviewer does not mistake them for oversights:

* The landing page still reads "two trained models · 66M params". There are
  three, about 205M combined.
* The landing page gives the summariser 200M; `/models` gives 139M, which is
  bart-base's real size and the number the figure is drawn from.
* Landing-page typos: `ROGUE-L` should be `ROUGE-L`;
  `Summarizer(Used across different agents)` is missing a space.
* `PaperSummary` in the class diagram declares an `evidence_spans` list of
  `EvidenceSpan`, but `EvidenceSpan` itself is no longer drawn — a dangling
  type.
* The deck's test count still reads "334 passed, 1 skipped", which predates
  `tests/test_t614_auth.py` and `tests/conftest.py`. Re-run
  `python -m pytest tests/ -q` and update slide 66 and the status slide.
* The superseded diagram files in section 2 could move to `diagrams/archive/`;
  they are left in place pending that call.
