# Quarantined artefacts — void measurements, kept as evidence

Nothing in this directory is a result. These files record measurements that
turned out to be invalid, kept so the failure is auditable rather than merely
deleted.

**Do not quote any number from these files.**

## `scireviewgen_goldsets_t324.json`, `scireviewgen_chapters.json` (2026-08-27)

T-324's first full run, reporting a **match rate of 18.6%**. That figure is
**void**.

**What happened.** OpenAlex had moved to a metered daily budget ($0.10/day
keyless, ~100 searches). The run needed 291. The budget expired around request
~100 and every chapter from roughly the 34th onward resolved zero papers, so
the "match rate" is mostly a record of requests that were never served.

**Why it looked like a result.** `resolve_abstract` caught `Exception` and
returned `None`, and the caller counted `None` as "no match". A silent failure
that is indistinguishable from a genuine negative will fabricate a measurement.

**Fixed in two places** so it cannot recur:
- `search_openalex` raises `OpenAlexBudgetExhausted` on HTTP 429 instead of
  letting it look like an empty result set.
- `scireviewgen_goldsets` stops on that exception, sets
  `partial_run_budget_exhausted: true` in both artefacts, and prints that the
  rate is not a finished measurement.

**The real number is 70.4%** (`eval/scireviewgen_goldsets_t324.json`), measured
after `OPENALEX_API_KEY` raised the daily budget 10x.
