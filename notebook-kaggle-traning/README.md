# Kaggle training notebooks

Every GPU training run in ResearchGPT lives here. Each notebook trains,
evaluates, applies its adoption/escalation gate and writes a metrics JSON.
Neither needs the `researchgpt` package installed on Kaggle.

They differ in one way that matters: **notebook 01 builds its own data from the
Hub; notebook 02 needs `train_triples.jsonl` uploaded as a Kaggle Dataset**,
because BM25 hard-negative mining needs the whole pooled corpus. **Notebook 03
reuses that same upload** — it rebuilds the negatives in-notebook.

| Notebook | Task | Trains | Status |
|---|---|---|---|
| `01_train_verifier_scifact.ipynb` | **T-302 / T-303** | The claim verifier (`deberta-v3-small`, 3-way NLI) | ✅ **Run 2026-08-27** — macro-F1 0.516 → 0.769, passed T-307 |
| `02_train_reranker_scireviewgen.ipynb` | **T-332 / T-333** | The cross-encoder reranker, **4 hard negatives** | ⚠️ **Run 2026-08-27, model REVERTED** — won on ranking, lost its relevance prior (T-335) |
| `03_train_reranker_mixed_negatives.ipynb` | **T-332R** | The same reranker, **3 hard : 1 random** | ⭐ **RUN THIS ONE** — reuses notebook 02's upload, no new dataset |

> **Run notebook 03, not notebook 02.** Notebook 02 is kept because its run is
> reported in the evaluation chapter — a fine-tune that won every ranking metric
> and was rejected on a calibration control is a finding, not a dead end — but
> its negatives are the thing notebook 03 exists to fix.

> **Verifier first, and that ordering is not arbitrary.** TASKLIST T-332: *"Train
> the verifier (T-303) first — it is the graded component and takes priority on
> the quota."* The verifier passed its T-307 gate at macro-F1 0.769 on
> 2026-08-27, so the quota is now free for the reranker.

---

## Notebooks 04–07 — the local `qwen2.5:3b-instruct` arm

Added 2026-08-29. A **separate track** from 01–03, serving the local-inference
side-car in `agents/`: models small enough to run on a 5 GB card through Ollama.

| Notebook | Task | Trains | Data it needs |
|---|---|---|---|
| `04_train_extractor_qwen3b.ipynb` | **T-337** | Extractor, **distilled from `gpt-oss`** | `data/llm_cache/` — 162 cached calls, 134 usable |
| `05_train_writer_qwen3b.ipynb` | **T-338** | Writer, on SciReviewGen `reference → target` | none — streams from the Hub |
| `06_train_verifier_qwen3b.ipynb` | **T-339** | Verifier, **generative arm** vs the DeBERTa incumbent | `data/scifact/pairs_*.jsonl` |
| `07_train_critic_qwen3b_ablation.ipynb` | **T-340** | Critic router — **an ablation expected to fail** | `outputs/runs/*/trace.jsonl` |

All four are QLoRA (4-bit NF4, LoRA r=16) on `Qwen/Qwen2.5-3B-Instruct`, sized
for a **free Kaggle T4**, and all four end by exporting GGUF `q4_K_M` plus an
Ollama `Modelfile`. **Train on Kaggle, run on the 5 GB card** — a 3B QLoRA does
not fit in 5 GB of VRAM.

### Two agents are missing from that list, deliberately

| agent | why there is no notebook |
|---|---|
| **Planner** | excluded by request |
| **Retriever** | **there is no model to train.** It is HTTP calls to OpenAlex / arXiv / Semantic Scholar plus DOI-and-title dedup. Nothing in it is learned |
| **Ranker** | it *has* a trained model, but it is a **22M cross-encoder**, not a 3B generative model — and it is already covered by notebooks 02 and 03. Replacing a 22M reranker with a 3B one would make ranking, already the pipeline's slowest stage at 1,130 s/run, dramatically worse |

### Read the header of each before running

Three of the four contradict something already recorded in the project, and each
notebook says so at the top rather than burying it:

* **04** — `TRAINING_SPEC.md §4` says the Extractor *"cannot be fine-tuned at
  all: it needs 4-field labels that do not exist."* True for **human** labels.
  The cache now holds 134 **teacher** labels, which is distillation, not
  annotation. A distilled student's ceiling is the teacher, including its
  errors — amend §4 before citing this.
* **05** — the Writer fine-tune was **evaluated and rejected on 2026-08-25**, on
  deployment cost. One of the three objections has weakened (a GPU exists now);
  the context objection stands and is binding: `num_ctx 8192` holds ~25 papers'
  insights, not 60.
* **06** — **does not replace the Verifier.** The DeBERTa model is one of the
  seven things `TASKLIST §0` never cuts. This is a comparison arm for T-705b,
  and the most useful outcome is a *negative* one: a 3B failing to beat a 44M
  model is direct evidence for "architecture beats model scale".
* **07** — **expected to be rejected, and written that way.** There are only
  **17 recorded routing decisions** across all 78 runs, so it trains on
  synthetic data generated from the gates themselves, which proves only that a
  network can fit three thresholds. Its real finding is that two of the three
  gates escalate on *prior decisions*, so a stateless router cannot express the
  policy at all.

### Kaggle gotchas specific to these four

* **The T4 is sm_75 and has no bf16.** Every cell uses `fp16`. Setting `bf16=True`
  does not error — it silently falls back and doubles step time.
* **Merge the adapter in fp16, never in 4-bit.** `merge_and_unload()` on a 4-bit
  model produces garbage weights; the dequantise–merge–requantise round trip
  destroys deltas as small as LoRA's. Notebook cells reload the base in fp16 for
  this reason, which is why that step is slow.
* **`num_ctx` on the Ollama side defaults to 2048** and the extractor prompt is
  ~3,530 tokens before any paper text. Every `Modelfile` emitted here sets 8192.
  See `agents/README.md`; `python -m agents.probe` verifies it with a canary.

---

## 01 — Verifier fine-tune (T-302 / T-303)

Trains the three-way claim verifier that decides `SUPPORT` / `CONTRADICT` /
`NEI` for a drafted claim against a retrieved evidence sentence.

### Before you start

Nothing. The notebook builds its own data from the Hugging Face Hub. You do
**not** need to upload the local `data/scifact/*.jsonl` — those are built by the
same code with the same seed, so the notebook reproduces them exactly (and
`tests/test_phase3_acceptance.py` fails if the two ever drift apart).

### Steps

1. Go to <https://www.kaggle.com/code> → **New Notebook** → **File → Import
   Notebook** → upload `01_train_verifier_scifact.ipynb`.

2. Open the right-hand **Settings** panel and set **both**:

   | Setting | Value | Why |
   |---|---|---|
   | **Accelerator** | `GPU T4 x2` | Only one GPU is used; T4 x2 is simply the quota-friendly option. On CPU this takes hours instead of minutes. |
   | **Internet** | **On** | It fetches SciFact and the base checkpoint from the Hub. |

   ⚠️ Kaggle silently ignores a notebook's requested accelerator on import. **Set
   it in the panel yourself and confirm it says GPU before you run**, or you
   will wait an hour to discover it ran on CPU.

3. **Run All.** Expect **10–20 minutes** end to end on a T4.

4. Watch three things as it runs:
   - **Section 3** prints the pair counts. They must read
     `train 1463 / dev 272 / validation 628` and end with
     `OK: no claim_id appears in both train and dev`.
   - **Section 7** prints the stock baseline. On the untouched held-out set that
     is **accuracy 0.553, macro-F1 0.516** (measured locally 2026-08-27). If it
     differs materially, the data or the label permutation changed — stop and
     find out why before trusting the trained number.
   - **Section 9** prints the T-305 table. That is the deliverable.

5. From the **Output** tab, download **both**:
   - `verifier-scifact.zip` (~500 MB) — the checkpoint
   - `verifier_metrics.json` (a few KB) — the T-305 numbers

   > 500 MB is the fp32 checkpoint. It shrinks to ~170 MB once T-304 quantizes
   > it, which happens locally, not here.

6. Read the **T-307 verdict** printed in section 10:
   - **PASS** (macro-F1 ≥ 0.75) → keep `deberta-v3-small`, and spend the
     remaining Kaggle quota on the reranker (T-332).
   - **ESCALATE** (macro-F1 < 0.75) → change one line in **section 1** to
     `BASE_MODEL = "cross-encoder/nli-deberta-v3-base"` and **Run All** again.
     It is ~4x the parameters and still well under an hour. §0.2 of TASKLIST
     says latency is not a constraint and to lean toward escalating.

   The 0.75 threshold was fixed in `decisions.txt` **D-09 before this notebook
   ever ran**, deliberately, so the decision cannot be rationalised after seeing
   the number.

### Then, locally

```bash
# unzip the Kaggle output somewhere, e.g. data/models/verifier-scifact/
python -m researchgpt.verify.export_onnx --checkpoint data/models/verifier-scifact
python -m researchgpt.verify.benchmark   --model      data/models/verifier-onnx
python -m researchgpt.verify.evaluate    --tuned      data/models/verifier-scifact
```

Those are T-304 (ONNX int8 export + parity check), T-306 (CPU throughput) and
T-305 (the stock-vs-tuned table written to `eval/verifier_t305.json`).

---

## Things that will bite you

**The dataset cannot be loaded with `load_dataset`.**
`allenai/scifact_entailment` is a *script-based* dataset and `datasets>=4`
refuses it outright with `RuntimeError: Dataset scripts are no longer
supported`. TASKLIST T-301 records this as true of plain `allenai/scifact`
only — verified 2026-08-27, it is true of `scifact_entailment` too. The
notebook reads the Hub's auto-converted parquet branch
(`refs/convert/parquet`) instead. Don't "fix" it back to `load_dataset`.

**The stock head is in a different order from ours.**
`cross-encoder/nli-deberta-v3-*` emits `{0: contradiction, 1: entailment,
2: neutral}`; ours is `(SUPPORT, CONTRADICT, NEI)`. The notebook **permutes**
the trained head rather than reinitialising it, so the fine-tune starts from a
model that already knows entailment. The same permutation is what makes the
stock arm of T-305 a fair comparison instead of a near-chance strawman.

**Pair order is `(evidence, claim)`.**
Premise then hypothesis. Reversing them trains a subtly different task and
costs several F1 points with no visible error.

**The train/dev split groups by `claim_id`.**
One claim appears in up to five rows with different abstracts. A row-level
split puts the same claim text on both sides and inflates the dev score. The
notebook asserts this; do not remove the assert.

**`accelerate>=0.26` is a hard requirement of `Trainer`** and is not implied by
installing `transformers`. Section 2 installs it if it is missing.

---

## Reproducibility

`SEED = 20260827` fixes the NEI sampling, the train/dev split and the training
run. It must stay equal to `researchgpt.verify.scifact_pairs.SEED` — the local
JSONL files under `data/scifact/` and the notebook's in-memory pairs are then
byte-identical, and `tests/test_phase3_acceptance.py` enforces it.

Changing the seed changes the training set. That is fine, but re-run the local
`python -m researchgpt.verify.scifact_pairs` too, or the two stop matching.


---

## 02 — Reranker fine-tune (T-332 / T-333)

Fine-tunes the cross-encoder that reranks retrieved papers at T-210. This is the
**second** trained model and it is the one that answers Ammann et al.'s warning,
quoted in your own literature review, that their gains *"rely on a strong,
domain-aligned cross-encoder reranker"* — while ours is a 22M MiniLM trained on
**web search**, not science (`SESSION_CONTEXT §5.6`).

### ⚠️ Before you start — this notebook needs a data upload

Unlike the verifier notebook, **this one cannot rebuild its own training data**.
The BM25 hard-negative mining needs the whole pooled corpus, which is not
something to redo inside a training notebook.

Build the triples locally, then upload them:

```bash
python -m researchgpt.rerank.triples --chapters 3000
# -> data/rerank/train_triples.jsonl   (~99 MB, 75,395 pairs)
```

Then on Kaggle: **Datasets → New Dataset → upload `train_triples.jsonl`**, give
it any name, and in the notebook use **Add Input → Datasets** to attach it. The
notebook globs `/kaggle/input/**/train_triples.jsonl`, so the dataset name does
not matter.

Already built, from the 2026-08-27 run:

| | |
|---|---|
| pairs | **75,395** (15,079 positive / 60,316 negative, exactly 1:4) |
| queries | 3,000 chapters, **1,381 distinct surveys** |
| unique cited abstracts | 13,929 |
| **random-fallback negatives** | **0.0%** — every negative is a genuine BM25 hard negative |

### 🔴 Known Kaggle failure this notebook now guards against

**`AttributeError: 'DataParallel' object has no attribute 'preprocess'`**

Kaggle's *GPU T4 x2* exposes **two** devices. `sentence-transformers` then wraps
the model in `torch.nn.DataParallel`, and `BinaryCrossEntropyLoss` calls
`self.model.preprocess(...)` — an attribute `DataParallel` does not forward. The
run dies partway through `model.fit()`. Hit on 2026-08-27.

Section 1 now sets `CUDA_VISIBLE_DEVICES=0` **before torch initialises CUDA**,
and section 2 asserts only one GPU is visible. A 22M cross-encoder gains nothing
from a second GPU anyway.

⚠️ If you ever hit this again, **restart the kernel** and Run All — the pin only
works if it executes before CUDA is initialised, so re-running section 1 alone
on a live kernel will not help.

### Steps

1. Import `02_train_reranker_scireviewgen.ipynb` at
   <https://www.kaggle.com/code>.
2. **Add Input → Datasets** → attach the dataset holding `train_triples.jsonl`.
3. Settings: **Accelerator = GPU T4 x2**, **Internet = On**. (Kaggle ignores the
   notebook's own request on import — set it yourself and confirm.)
4. **Run All.** Expect **20–30 minutes**.
5. Watch section 3: it must end `OK: N survey groups, M held out, none on both
   sides`. If that assert ever fires, stop — the split leaked.
6. Download **`reranker-scireviewgen.zip`** and **`reranker_metrics.json`**.

### Then, locally

```bash
python -m researchgpt.rerank.export_onnx --checkpoint data/models/reranker-scireviewgen
python -m researchgpt.rerank.evaluate    --tuned-onnx data/models/reranker-onnx
```

That is T-333 (ONNX + int8) and T-334/T-335 (the adoption gate). The evaluation
uses T-212's **cached** pool, so it costs no OpenAlex budget.

### The two things that decide whether this ships

**1. The gate is out-of-domain, and the notebook cannot run it.**
Section 7 prints an *in-domain* comparison on SciReviewGen. **That is not the
decision.** SciReviewGen is frozen at S2ORC 2020-07-05 and skews biomedical;
your corpus is CS/agentic-RAG. A large in-domain gain with no out-of-domain gain
means you **fitted the benchmark, not the task** (`TRAINING_SPEC §2.4`). T-335
decides on your own 25-paper bibliography, locally, after quantization.

Current stock baseline on that set, for comparison: **nDCG@10 0.2277,
Recall@20 0.4815, Precision@12 0.0926**.

**2. If it does not beat stock, keep stock and report the negative result.**
That is not a failure — the pipeline is unaffected because this was always a
weight swap, and the verifier already satisfies the training requirement on its
own. TASKLIST's Aug 30 kill switch says exactly this. *A fine-tune that did not
help is an honest contribution.*

### If the gain is ~0

Suspect **the hard negatives (T-331) first**, before the training config —
TASKLIST says so directly. Check
`eval/rerank_triples_t330.json → random_fallback_share_of_negatives`. If it is
high, BM25 could not find confusable documents and the model was handed an easy
task it could already do. On the current build that value is **0.0**, so this is
not the explanation unless the triples are rebuilt smaller.

---

## 03 — Reranker **retrain** with mixed negatives (T-332R)

A re-run of notebook 02 that changes **exactly one variable**: what the
negatives are made of. Everything else — base model, seed, epochs, learning
rate, batch size, max length, warmup, weight decay, dev fraction, and the
survey split itself — is held identical, and
`tests/test_phase3c_acceptance.py::test_mixed_notebook_changes_only_the_negatives`
fails if any of them drift.

### Why there is a third notebook

Notebook 02's model **won on every ranking metric and was rejected anyway.**

| | stock | notebook 02's model |
|---|---|---|
| out-of-domain Recall@20 | 0.4815 | **0.6481** (+35% rel.) |
| in-domain nDCG@10 | 0.2646 | **0.7500** |
| **live relevance-control violations** | **0 / 15** | **11 / 15** |
| **off-topic absolute score** | **≈ −11** | **+3 … +5** |

On the first real pipeline run (M1) it ranked an **IoT-monitoring paper above
LiRA** — the single most relevant paper in the pool — for the query
`multi agent retrieval literature review`. It had not learned to rank better; it
had stopped being able to recognise irrelevance.

**Cause:** T-331 mined **100% BM25 hard negatives**. Every negative was a
topically adjacent scientific abstract, so the model was only ever asked *"which
of these plausible science abstracts belongs to this chapter?"* and never *"is
this relevant at all?"*. T-331's warning that *"random negatives make the task
trivial"* is right about **necessity** and wrong at **100%**. The fix is a
mixture, not a switch.

### ✅ No new upload — attach the same Kaggle Dataset

Unlike notebook 02, this one needs **nothing new uploaded**. It reads the
identical `train_triples.jsonl` and rebuilds the negatives in-notebook.

That works because **every one of the 13,929 cited abstracts already appears in
that file** — each document is a positive for at least one chapter, since the
corpus *is* the set of cited abstracts. Verified locally before the notebook was
written.

| | notebook 02 | notebook 03 |
|---|---|---|
| queries | 3,000 | 3,000 |
| positives | 15,079 | 15,079 |
| negatives | 60,316 | **60,316** |
| positive : negative | 1 : 4 | **1 : 4** |
| negative composition | **4 hard** | **3 hard + 1 random** |

Measured locally on the real file: **75.0% hard / 25.0% random, ratio 1:4.0
exactly, 68,380 training pairs** — the same 68,380 the previous Kaggle run
reported, which confirms the split did not move.

**Which hard negatives are dropped:** the weakest one per positive. The file
preserves BM25 rank order, so the three that stay are the highest-ranked and
most confusable.

### Steps

1. Import `03_train_reranker_mixed_negatives.ipynb` at
   <https://www.kaggle.com/code>.
2. **Add Input → Datasets** → attach **the same dataset as notebook 02**.
3. Settings: **Accelerator = GPU T4 x2**, **Internet = On**. (Kaggle ignores the
   notebook's own request on import — set it yourself and confirm.)
4. **Run All.** Expect **30–45 minutes** end to end — ~20–30 min of training plus
   the before/after ranking and relevance measurements.
5. Watch three things:
   - **Section 4** must print `OK: 1:4 ratio held, composition is 75% hard /
     25% random`. Its spot-check prints one hard and one random negative for the
     same query — the hard one should look topically adjacent, the random one
     should not.
   - **Section 5** must end `OK: N survey groups, M held out, none on both
     sides`. If that assert fires, stop — the split leaked.
   - **Section 10** prints the verdict.
6. Download **`reranker-mixed-negatives.zip`** and
   **`reranker_metrics_mixed.json`** — but only if section 10 says `PROCEED`.

### Section 10's gate is a pre-filter, not the decision

Two conditions, both fixed in section 1 **before** the run — the same discipline
`decisions.txt` D-09 applied to the verifier's 0.75 threshold:

| condition | threshold | why |
|---|---|---|
| ranking gain | `nDCG@10` delta ≥ 0.001 | losing the discriminative signal along with the miscalibration is not progress |
| relevance retained | control violation rate ≤ 20% | notebook 02's model was at ~73% |

**The adoption decision is still T-335**, run locally against your own 25-paper
bibliography, after int8 quantization. All the notebook gate does is stop you
spending a 91 MB download and a local eval cycle on a model that already failed
the one property it was retrained to fix.

The relevance control uses the **same four probe texts** as
`researchgpt.rerank.evaluate.OFF_TOPIC_CONTROLS` — wind-turbine fatigue, soil
nitrogen, opera libretti, beta-lactamase crystallography — so the notebook's
number and the local gate's number mean the same thing. A test enforces that
they stay identical.

### Then, locally

```bash
# unzip to data/models/reranker-mixed/
python -m researchgpt.rerank.export_onnx --checkpoint data/models/reranker-mixed
python -m researchgpt.rerank.evaluate    --tuned-onnx data/models/reranker-mixed-onnx
```

### If section 10 says STOP

The notebook prints which way to move, and it is not the same direction in each
case:

* **ranks better but still fails the control** → too few random negatives. Set
  `RANDOM_PER_POSITIVE = 2` (3:2) and re-run.
* **passes the control but the gain vanished** → too many. Set
  `HARD_PER_POSITIVE = 5` (5:1) and re-run.
* **failed both** → TASKLIST's Aug 30 kill switch applies. **Keep the stock
  reranker and report the negative result.** The pipeline is unaffected — this
  was always a weight swap — and the verifier satisfies the training requirement
  on its own. *A fine-tune that did not help, diagnosed and reported, is an
  honest contribution.*

### Smoke-tested before it was handed over

All 11 code cells were executed locally on CPU against the real 75,395-pair
file, with a 200-example stand-in for the training cell: data load, the mix and
its invariants, the survey split, the stock baselines, `fit()`, the comparison
tables, the gate and the save all ran clean. The stock relevance control printed
an off-topic score of **−10.74**, matching the local harness's ≈ −11, which
confirms the notebook reads un-activated logits exactly as the gate does.
