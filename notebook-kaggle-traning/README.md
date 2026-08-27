# Kaggle training notebooks

Every GPU training run in ResearchGPT lives here. Each notebook is
self-contained: it downloads its own data, trains, evaluates, applies its
adoption/escalation gate and writes a metrics JSON. Nothing in this folder
needs the `researchgpt` package to be installed on Kaggle.

| Notebook | Task | Trains | Status |
|---|---|---|---|
| `01_train_verifier_scifact.ipynb` | **T-302 / T-303** | The claim verifier (`deberta-v3-small`, 3-way NLI) | **Ready to run** |
| `02_train_reranker_scireviewgen.ipynb` | T-332 | The cross-encoder reranker | Blocked — needs Phase 3B (T-330/T-331 build its triples) |

> **Why the verifier goes first.** It is the graded component *and* the
> required training component. TASKLIST T-332 says so explicitly: *"Train the
> verifier (T-303) first — it is the graded component and takes priority on the
> quota."* The reranker is a weight swap that the pipeline never depends on.

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
