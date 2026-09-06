---
name: researchgpt-review2-deck
description: "ResearchGPT major project — state as of 2026-08-29: Phases 0-6B done, M1+M2 landed, pushed to GitHub; the binding constraint is now RANKING, and Phase 7 (evals/ablations) + Phase 8 (report) are what remain"
metadata:
  node_type: memory
  type: project
  originSessionId: 1225dca5-d8e7-4b16-bacf-99bb0c81d2b4
  modified: 2026-08-29T12:30:00.000Z
---

ResearchGPT (Major Project, GRIET DSC06, target submission **~2026-09-07**).

**Status 2026-08-29** — Phases 0, 1, 2*, 3, 3B, 3C, 4, 5, 6 and 6B are complete.
**M1 landed 2026-08-27, M2 2026-08-28**, both days early. 89 of 117 TASKLIST tasks
ticked, **333 tests passing**, and the repo now has a remote —
`github.com/karan00567/Major-Project`, `master` pushed through `cc200be`.
Working branch as of 2026-08-29: **`web-extrator`** (spelled without the second
"c"), cut from `master` at `cc200be`.

**Why:** `TASKLIST.md` (project root) is still the operative backlog — update its
checkboxes in place, never rewrite it. `documents/decisions.txt` holds the human's
answers to D-01..D-16. Working practice: **Claude Code plans/specs/reviews/integrates,
Cursor+Groq writes single-file code, the human does 👤 tasks**. Hard constraint:
**$0 — free open-weight models only** (`TASKLIST §0.1`, enforced by `ALLOWED_MODELS`
in `core/llm.py`). One documented breach — a paid Baseten host for a single T-409 run
on 2026-08-28 — was **reverted 2026-08-29**; the model stayed open-weight throughout.

**How to apply:** the graded work left is **Phase 7 (T-701..T-707: ablation 2 −Verifier,
hallucination stress test, the 50-claim spot-check) and Phase 8 (T-801..T-813, the report)**.
The blocker under all of it is measured in `eval/metrics_evaluated.md` (2026-08-29,
gitignored): **the binding constraint moved from retrieval to ranking.** Query widening
(2-term subsets) lifted union recall 0.057 → 0.257, but **corpus recall is 0.000 in every
run** — the answer key sits at ranks 49–2,098 against a `max_papers` cut-off of 10, so no
gold paper ever reaches the Extractor and no run has yet produced a better survey.
`max_per_source: 100` is **rejected** (one extra paper for +33 min, and worse ranking).
Never cut: the six agents, the trained verifier, the evidence panel (T-607), ablation 2,
`trace.jsonl`, HITL (T-609), and the T-325 cross-check.
