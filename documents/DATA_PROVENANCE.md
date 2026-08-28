# Data provenance and licensing

> **T-326.** This is the source for the report's data section (T-803/T-806) and
> the answer to "where did your evaluation data come from, and were you allowed
> to use it?" Every dataset the project touches appears here with its licence,
> what it was used for, and the limitation it carries into the results.
>
> Citations live in `refs.bib`. **T-813 re-verifies every DOI before
> submission** — indexes and publication years change.

---

## 1. SciFact — verifier training data (T-301, T-303, T-305)

| | |
|---|---|
| Cite | Wadden et al., EMNLP 2020 — `wadden2020scifact` |
| Accessed as | `allenai/scifact_entailment`, parquet branch `refs/convert/parquet` |
| Licence | **CC BY-NC 2.0** — non-commercial; an academic project satisfies this |
| Used for | Training and evaluating the three-way claim verifier |
| Size used | 919 train / 340 validation rows → 1,463 / 272 / 628 pairs |

**Loading note.** `allenai/scifact_entailment` is a *script-based* dataset and
`datasets>=4` refuses it (`RuntimeError: Dataset scripts are no longer
supported`). The Hub's auto-converted parquet branch carries identical rows
with no script. This is worth one line in the method section because it is the
kind of thing that silently breaks reproduction a year later.

**Limitation to state.** SciFact is **biomedical** and expert-curated:
single-sentence evidence chosen to entail or refute. Our corpus is computer
science, and our evidence is retrieved chunks of real papers. That domain shift
is why T-325 exists and why its number is expected to sit well below the
SciFact held-out score.

---

## 2. SciReviewGen — verifier cross-check and retrieval breadth (Phase 3B)

| | |
|---|---|
| Cite | Kasanishi et al., Findings of ACL 2023 — `kasanishi2023scireviewgen` |
| Accessed as | `kejian/SciReviewGen` (Hugging Face mirror) |
| Licence | **CC BY-NC 4.0** |
| Derived from | S2ORC (Lo et al., ACL 2020 — `lo2020s2orc`) |
| Used for | T-322 claim→evidence pairs, T-324 retrieval gold sets, **T-325 cross-check** |
| Size | 84,705 train / 4,410 validation / 4,457 test |

⚠️ **Cite the original paper, not the mirror, and state CC BY-NC regardless of
what the mirror card says.** The mirrors' licence metadata is unreliable:
`pat-jj/SciReviewGen` declares **MIT**, which a mirror of S2ORC-derived data
cannot grant. `kejian/SciReviewGen` and `kdercksen/scireviewgen-csv` declare
nothing. The upstream licence is CC BY-NC 4.0 and that governs.

Non-commercial use is satisfied: this is an unfunded academic project, the
data is used only for evaluation, and no derivative dataset is redistributed.

**Limitations to state — three, and all of them affect a number in the report.**

1. **Frozen at S2ORC 2020-07-05.** Live OpenAlex retrieval surfaces correct
   post-2020 papers that score as *false positives* against a 2020 gold set.
   In T-212b that is a measurement artefact of the frozen corpus, **not** a
   retrieval failure, and must be reported as such.
2. **No DOIs and no titles for cited papers.** The dataset gives only the cited
   *abstract*. T-324 therefore matches on abstract text rather than the title
   matching TASKLIST assumed, and **T-212b's recall is bounded by that match
   rate** — quote the two together or the recall number is meaningless.
3. **Skews biomedical**, against the CS domain the reranker (T-334) and the
   verifier both target. A large in-domain gain with no out-of-domain gain
   means the benchmark was fitted, not the task.

**Attribution rule used to build the pairs (`decisions.txt` D-07a).** Only
sentences citing exactly **one** paper become pairs; multi-cite sentences are
dropped, because a claim citing three papers is not cleanly attributable to any
one of them. Measured cost: **25.3% of citing sentences**. A further ~11% were
dropped as degenerate after citation markers were stripped (dangling
references, punctuation debris, meta-sentences about the survey itself). Both
numbers belong in the method section — they define what the T-325 number is
computed over.

---

## 3. OpenAlex, arXiv, Semantic Scholar — live retrieval (Phase 2)

| Source | Licence / terms | Notes |
|---|---|---|
| OpenAlex | CC0 | Primary source. Keyless; `mailto` used for the polite pool. |
| arXiv | per-paper, metadata open | Atom API. HTTPS only — HTTP returns 301 with an empty body. |
| Semantic Scholar | free API terms | Secondary (D-03). Keyless it answers ~1 query in 3; degrades to `[]`, never raises. |

No paid tier is used anywhere in this project (TASKLIST §0.1).

---

## 4. Models

| Model | Licence | Used for |
|---|---|---|
| `cross-encoder/nli-deberta-v3-small` | Apache 2.0 | Verifier warm start (T-302) |
| `BAAI/bge-small-en-v1.5` | MIT | Embeddings (T-206) |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Apache 2.0 | Reranking (T-210) |
| `openai/gpt-oss-120b` (Groq free tier) | Apache 2.0, **open weights** | Generative agents (T-004 winner) |

All open-weight, all free tier, per TASKLIST §0.1's $0 hard rule. The rule is
enforced in code: `ALLOWED_MODELS` in `core/models.py` is checked at
config-load time, before any HTTP request can be constructed.
