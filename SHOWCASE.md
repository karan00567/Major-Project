# Demo runbook (T-610)

`decisions.txt` **D-11** chose option (a): **pre-bake a full showcase run that
replays instantly, and demo LIVE only at `max_papers=10`.** Justify it as demo
**reliability**, not as a latency workaround — a run against a rate-limited free
tier cannot be run in front of an examiner.

## Before the room

```bash
# 1. API, fixture mode ON — live runs are refused, so nothing can be
#    accidentally started mid-demo.
RESEARCHGPT_FIXTURE=1 python -m uvicorn researchgpt.api.app:app --port 8000

# 2. UI
cd frontend && npm run dev      # http://localhost:5173/
```

The page opens straight onto the pre-baked run. Nothing is fetched from
OpenAlex, no tokens are spent, and there is no network dependency in the graded
moment.

> ⚠️ Vite binds IPv6 `[::1]:5173`. `http://localhost:5173/` works;
> `http://127.0.0.1:5173/` is refused.

## The pre-baked run

`outputs/runs/fixture/` — the M2 loop run of 2026-08-28.

| | |
|---|---|
| Critic decisions | `RETRIEVE → REPLAN → RETRIEVE → WRITE` |
| iterations | 3 of 4 |
| corpus | 551 papers (271 → 551 after the replan) |
| claims verified | 19 (all PARTIAL) |
| claims dropped | 3 |
| grounding | 0.8636 |

## What to say, in order

1. **Panel 2 first.** The decision chain `RETRIEVE → REPLAN → RETRIEVE → WRITE`
   is the agentic claim made visible — the system searched, judged its own
   coverage inadequate, **rewrote its plan**, searched again, then wrote.
2. **Panel 3, the money shot.** Click a marked sentence. The evidence span the
   Verifier actually scored it against appears, with the source paper. Every
   one of the 19 verified claims is locatable and carries its evidence.
3. **Panel 4.** *"3 claims were removed as unsupported."* What the system
   **refused** to say. Then use the confirm/override control — that is
   Objective 2's Human-in-the-loop clause, and the judgement is written back to
   `trace.jsonl`.

## Say these before you are asked

Both are real and both read badly if a reviewer finds them first.

- **Zero claims reached SUPPORTED.** All 19 are PARTIAL because all 10 papers
  are abstract-only, and T-505 caps abstract-only support at PARTIAL by design
  (Li et al.: abstract-conditioned faithfulness 0.745 against 0.94–0.96 with
  full text). The cap is the system working, not failing — but the 0.86
  grounding figure is made **entirely of PARTIALs** and must be quoted that way.
- **Union recall against the 35-paper answer key is 0.057.** Retrieval is the
  binding constraint, and it caps everything downstream: the Verifier cannot
  ground a claim against a paper that was never fetched.

## Live demo, if asked

`max_papers=10`, fixture mode off. Budget **6–12 minutes** and expect to talk
over it. Never run this as the primary demo — a single 429 ends it in front of
the committee, which is exactly what D-11 rejected.

## Re-baking

Any completed run in `outputs/runs/` is a valid fixture; the artefact directory
*is* the fixture, so there is no separate recording format.

```bash
cp -r outputs/runs/<better_run> outputs/runs/fixture
```

**Re-bake once retrieval improves.** The current run is honest but thin, and a
showcase built on 0.057 recall undersells the architecture.
