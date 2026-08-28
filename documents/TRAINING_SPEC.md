# ResearchGPT — Training Specification

> **What this file is.** The complete specification for every **trained** component in the project. Two models are fine-tuned; everything else is prompted or frozen off-the-shelf.
>
> **Why it exists separately.** "Which model is trained, on what data?" got tangled once already during planning — the Extractor, the Writer, SciFact and SciReviewGen all got conflated. This file is the single answer. It is also the answer to the viva question *"where is the machine learning in this project?"*
>
> Created 2026-08-25. Companion to `TASKLIST.md` (schedule) and `PROJECT_PLAN.md` (scope).

---

## 0. What is trained and what is not

| Component | Trained? | Base model | Data | Runs on |
|---|---|---|---|---|
| Planner, Extractor, Critic, Writer | ❌ **prompted** | `openai/gpt-oss-120b` (free tier) | — | Groq API |
| Embeddings | ❌ frozen | `BAAI/bge-small-en-v1.5` (~33M) | — | local CPU |
| **Claim verifier** | ✅ **fine-tuned** | `microsoft/deberta-v3-small` (~44M) | **SciFact** | local CPU (ONNX int8) |
| **Cross-encoder reranker** | ✅ **fine-tuned** | `cross-encoder/ms-marco-MiniLM-L-6-v2` (~22M) | **SciReviewGen** | local CPU (ONNX int8) |

Two trained models, ~66M parameters combined, both trained on Kaggle's free GPU and both deployed quantized on a CPU-only machine. Neither generative agent is fine-tuned — that is deliberate, and §4 explains why.

**Common misconception to avoid in the write-up:** SciReviewGen is used for **two different purposes** — it trains the reranker (§2) *and* it independently validates the verifier (`TASKLIST.md` T-325). These are separate uses of separate fields. Do not describe it as "the training set" without saying for which model.

---

## 1. Model A — the claim verifier ★ (graded component)

Specified in full at `PROJECT_PLAN.md §4.2`; summarised here so this file is self-contained. Tasks: `TASKLIST.md` T-301–T-307.

| Item | Choice |
|---|---|
| Base | `microsoft/deberta-v3-small` (~44M), **warm-started from an existing NLI checkpoint**, not from scratch |
| Task | 3-way `(claim, evidence_sentence) → SUPPORT / CONTRADICT / NOT_ENOUGH_INFO` |
| Data | `allenai/scifact` — ~1.4k expert-written claims with sentence-level evidence |
| Training | 2–3 epochs, cross-entropy, < 1 hour on a Kaggle P100 |
| Deployment | ONNX + int8 dynamic quantization → local CPU |
| Verdict mapping | `SUPPORT` high-conf → `SUPPORTED`; `SUPPORT` low-conf → `PARTIAL`; `NOT_ENOUGH_INFO` → `UNSUPPORTED`; `CONTRADICT` → `CONTRADICTED`. Softmax prob = `support_score`, threshold **0.7, biased toward precision** |
| Escalation | If held-out F1 is poor, retrain `deberta-v3-base` (~184M). **Trade latency, not accuracy** |

**Why the verifier and not something else:** it sits on the graded critical path (you are graded on not hallucinating, and this *is* the anti-hallucination mechanism); SciFact needs no access request; and it removes hundreds of API calls per run that an LLM verifier would have cost.

**Evaluated three ways** (`TASKLIST.md` T-705b): SciFact held-out (curated benchmark), SciReviewGen cross-check (human-authored at scale, T-325), and a 50-claim hand spot-check in your own domain (T-705).

---

## 2. Model B — the cross-encoder reranker ★ NEW

Tasks: `TASKLIST.md` T-330–T-335. **This section is the new material; it is specified in full below.**

### 2.1 Why this model

This was the **original** training proposal. `PROJECT_PLAN.md §2.2` records it as **Cut**, and `SESSION_CONTEXT.md §4.1` gives the reason: *"The reranker route needed S2ORC access, historically a multi-day AI2 request — the single biggest schedule risk."*

**That blocker no longer exists.** Phase 3B established that SciReviewGen is available from three ungated Hugging Face mirrors with no access request (verified 2026-08-25). The cut was about access latency, never about merit.

Four independent reasons it is the right second model:

1. **It answers an objection already sitting in your literature review.** `SESSION_CONTEXT.md §5.6`: Ammann et al. warn their gains *"rely on a strong, domain-aligned cross-encoder reranker"* — and yours is a 22M MiniLM trained on web search, not science. Right now that is an unanswered weakness. Fine-tuning converts it into a contribution.
2. **Zero new inference cost.** The reranker already runs on CPU in the pipeline (T-210). Fine-tuning swaps weights; nothing architectural changes and no new latency appears.
3. **It is off the M1 critical path.** The pipeline works with the stock reranker. The tuned model is a drop-in upgrade — if training fails, nothing breaks.
4. **Retrieval recall is a hard ceiling on verification**, stated independently by ALCE, Sarol et al. (top-20 recall 0.53) and Valsci. Better reranking raises the ceiling on the graded groundedness metric.

It also closes an explicit instruction in `SESSION_CONTEXT.md §5.6`: *"Measure reranking's contribution separately."* Stock-vs-tuned is that measurement.

### 2.2 Training data construction

Source: `kejian/SciReviewGen` (84,705 train / 4,410 validation / 4,457 test rows). Parsed by `eval/scireviewgen_parser.py` (T-321), which is already being built for Phase 3B — this reuses it.

Each row gives:
- `reference` = survey title `<s>` chapter `<s>` cited-paper abstract `<s> BIBnnn </s>`, repeated
- `target` = the human-written chapter with inline `BIBnnn` markers

**Construct training triples as follows.**

| Element | Rule |
|---|---|
| **Query** | `survey_title` + `" "` + `chapter_heading`. This mirrors what the live Retriever sees: a topic, not a natural-language question. |
| **Positives** | The abstracts of every `BIBnnn` block in that row's `reference`. A human author chose to cite these for this chapter — that is the relevance label. |
| **Negatives** | **BM25 hard negatives.** For each query, retrieve top-50 abstracts from the pooled corpus of all sampled chapters, discard any that are true positives for that query, and sample from what remains. |
| **Ratio** | 1 positive : 4 negatives. |

> **Hard negatives are not optional.** Random negatives make the task trivial — the model learns topic matching, which BM25 already does, and stock-vs-tuned will show no gain. The negatives must be documents BM25 *already ranks highly and is wrong about*. That is the only signal a reranker can add.

**Sampling.** Do not use all 84,705 chapters. Sample **3,000 train chapters**, cap positives at **8 per chapter**, giving roughly 3,000 × 8 × 5 ≈ **120k pairs**. That is ample for a 22M cross-encoder and keeps Kaggle time under half an hour.

**Leakage control — this is the one that will silently invalidate your results.**

- Build training pairs **only** from the SciReviewGen `train` split; evaluate **only** on `test`.
- Deduplicate by `survey_title`: the same survey contributes multiple chapter rows, so a title-level split is required. A random row-level split puts chapters of the same survey on both sides and inflates the tuned score.
- Pool negatives **within the split being built**. Never mine train negatives from the test pool.

### 2.3 Training configuration

| Item | Value |
|---|---|
| Base | `cross-encoder/ms-marco-MiniLM-L-6-v2` (~22M) — the model already in the pipeline |
| Objective | Binary cross-entropy on `(query, abstract) → relevant / not relevant` |
| Max sequence length | 512 tokens (truncate the abstract, never the query) |
| Learning rate | 2e-5, AdamW, linear decay, 10% warmup |
| Batch size | 32 |
| Epochs | 2 |
| Hardware | Kaggle T4 or P100 — **expect 20–30 minutes** |
| Seed | Fixed and recorded; the run is reported as reproducible |

`sentence-transformers`' `CrossEncoder` class implements this directly; it needs no custom training loop.

### 2.4 Evaluation protocol

Reuses the existing retrieval eval, so almost no new evaluation code is required.

| Test set | What it measures | Task |
|---|---|---|
| SciReviewGen `test` split (title-disjoint) | In-domain gain | new |
| **Your own 25-paper bibliography** | **Out-of-domain, CS, the honest number** | reuses T-212 |

Report, for **stock vs fine-tuned**, on both sets: **Recall@20, nDCG@10, Precision@12**, plus per-query rerank latency on your CPU.

> **The out-of-domain number is the one that matters.** SciReviewGen is frozen at S2ORC 2020-07-05 and skews biomedical; your corpus is CS/agentic-RAG. A large in-domain gain with no out-of-domain gain means you fitted the benchmark, not the task. **Report both, and lead with the honest one.**

**Gate for adoption:** the fine-tuned reranker is promoted into `configs/default.yaml` only if it beats stock on **your own bibliography**. An in-domain-only win is a reportable finding, not a reason to ship it.

### 2.5 Deployment

Same path as the verifier: **ONNX export + int8 dynamic quantization**, run on local CPU via `onnxruntime`. T-210 already measures stock per-query rerank latency; re-measure after quantization and report both. Quantization must not be assumed free — verify the tuned-quantized model still beats stock on the adoption gate.

### 2.6 New ablation row

This unlocks an ablation that `SESSION_CONTEXT.md §5.6` explicitly asks for:

> **Ablation 5 — stock reranker vs fine-tuned reranker**, full system otherwise unchanged.

It isolates the reranker's contribution to end-to-end grounding, separately from the rest of the architecture. Run it at `max_papers=25` alongside the others. It is lower priority than ablation 2 (− Verifier) and must never displace it.

### 2.7 Risks

| Risk | Mitigation |
|---|---|
| **Random negatives make the task trivial** | BM25 hard negatives, §2.2. If stock-vs-tuned shows ~0 gain, suspect the negatives first. |
| **Title-level leakage inflates the result** | Split by `survey_title`, not by row. §2.2. |
| Domain shift (biomedical → CS) | Evaluate on your own bibliography and lead with that number. Report the gap as a limitation. |
| Quantization erodes the gain | Re-run the adoption gate *after* int8 export, not before. |
| Kaggle quota contention with the verifier | 22M model, 20–30 min. Train the **verifier first** — it is the graded component. |
| Scope creep into M1 | The pipeline ships with the stock reranker. This is a swap, never a dependency. |

---

## 3. Combined reporting — the "where is the ML" answer

One table, two rows, in the report and on the deck:

| Model | Params | Trained on | Metric | Stock | Fine-tuned |
|---|---|---|---|---|---|
| Claim verifier (`deberta-v3-small`) | 44M | SciFact | held-out F1 | _T-305_ | _T-305_ |
| Cross-encoder reranker (`MiniLM-L-6`) | 22M | SciReviewGen | Recall@20 (own bibliography) | _T-334_ | _T-334_ |

Both trained on free GPU, both quantized to int8, both running on a CPU-only machine at zero cost. That is a defensible ML contribution for a B.Tech major project, and it directly supports the project's thesis — `SESSION_CONTEXT.md §5.5`, Valsci: **architecture beats model scale**. Small trained components placed at the two bottlenecks (retrieval quality and claim grounding) do more than a larger generative model would.

---

## 4. Why the generative agents are NOT fine-tuned

Recorded here because it will be asked, and because it was considered and rejected on evidence.

**The Writer was evaluated for fine-tuning on 2026-08-25 and rejected.** SciReviewGen's `reference → target` pairs *are* a valid Writer training set — that part of the idea was sound. It fails on deployment, not on data:

- The Writer has the **largest context in the pipeline** — insights from up to 60 papers, ~20,000 tokens.
- On the target hardware (Intel i5-10400, 6 cores, 24 GB RAM, no usable GPU), a 1.5B model at Q4 would need **~7 minutes of prefill plus ~2.5 minutes of generation ≈ 10 minutes per Writer call**, and the Critic loop can invoke the Writer up to three times.
- The measured alternative, `openai/gpt-oss-120b` via the free tier, returns in **3.1 seconds**.
- `PROJECT_PLAN.md §6.3` already ruled out local generative inference: a 7B on CPU is 3–8 tokens/sec, *"not a viable working path and should not be planned around."*
- SciReviewGen's own fine-tuned survey generators reached only **~30% of chapters matching human quality** (`SESSION_CONTEXT.md §5.2`).

Fine-tuning the Writer would also weaken the project's central claim. The finding is that *a small, freely-available, off-the-shelf model plus claim-level verification produces grounded output*. Training the generator undercuts the demonstration that **the architecture** is doing the work.

**Report it as future work**, in T-806:

> The Writer remains an off-the-shelf prompted model. SciReviewGen's `reference → target` pairs provide a natural supervised signal for fine-tuning it, which we leave to future work; on CPU-only hardware the inference cost of a locally-hosted generator (~10 minutes per synthesis call, against 3 seconds for a hosted free-tier model) made this impractical within the project's constraints.

**The Extractor cannot be fine-tuned** at all in this project: it needs 4-field labels that do not exist. `PROJECT_PLAN.md §5.4`'s 10-paper annotation task was cut, and SciReviewGen carries no such labels.

---

*Companion to `TASKLIST.md`, `PROJECT_PLAN.md` and `SESSION_CONTEXT.md`. Amend this file for training-design changes; amend `TASKLIST.md` for schedule changes.*
