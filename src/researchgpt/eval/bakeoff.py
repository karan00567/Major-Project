"""T-004 — Extractor JSON-reliability bake-off across the §0.1 allowlist.

Measures, per model, on real paper abstracts through the real extractor prompt
and the real LLMClient:

  * clean-parse rate  (after fence stripping - Gemma ignores responseSchema)
  * Pydantic validation rate against PaperInsight
  * field population  (how many of the 9 content fields came back non-null)
  * schema-echo failures (a model returning the literal placeholder "string")
  * latency

TASKLIST §0.2 makes this a QUALITY decision, not a speed one - but an arm that
cannot finish in reasonable wall clock is disqualified regardless, so each arm
carries a cumulative time budget.

Run:  python -m researchgpt.eval.bakeoff
"""

from __future__ import annotations

import json
import pathlib
import time
from typing import Any

import httpx

from researchgpt.core.config import load_config
from researchgpt.core.llm import LLMClient, LLMError, RateLimitExceeded, extract_json
from researchgpt.core.models import PaperInsight

#: Arms actually run. The Gemma arms are DISQUALIFIED ON MEASURED LATENCY -
#: see DISQUALIFIED below. Re-add them only if the latency picture changes.
ARMS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
]

#: Measured 2026-08-25 and recorded rather than silently dropped.
DISQUALIFIED = {
    "gemma-4-31b-it": (
        "Latency. 84.5s on a 100-char probe; on real ~1,900-char abstracts a "
        "5-paper arm had not completed after >60 min of wall clock (process "
        "alive, 1.2s CPU - blocked on generation, not compute). At ~1 call per "
        "paper and ~70 papers per run this cannot finish a real run."
    ),
    "gemma-4-26b-a4b-it": (
        "Hard failure. Returns HTTP 200 with every output part flagged "
        "thought=true and no text part, so the entire output budget is spent "
        "on reasoning. LLMError: 'all parts were thought-only or missing text'."
    ),
}

#: Cumulative seconds per arm before it is abandoned and marked disqualified.
ARM_BUDGET_S = 300.0

CONTENT_FIELDS = (
    "methodology", "advantages", "disadvantages", "critique",
    "datasets", "metrics", "results", "limitations",
)
INSIGHT_FIELDS = set(CONTENT_FIELDS) | {"extraction_note"}

GOLD = pathlib.Path("eval/gold_sets/own_bibliography.json")
PROMPT = pathlib.Path("src/researchgpt/core/prompts/extractor_v1.md")
OUT = pathlib.Path("eval/bakeoff_t004.json")


def deinvert(idx: dict | None) -> str:
    if not idx:
        return ""
    return " ".join(w for _, w in sorted((p, w) for w, ps in idx.items() for p in ps))


SAMPLES = pathlib.Path("eval/bakeoff_samples.json")


def fetch_samples(n: int = 5) -> list[dict[str, str]]:
    """Real abstracts for the first n gold-set DOIs that have one.

    Cached to eval/bakeoff_samples.json. A live re-fetch uses a SHORT timeout:
    a 30s timeout let a stalled OpenAlex connection hang the whole bake-off
    twice on 2026-08-25.
    """
    if SAMPLES.is_file():
        cached = json.loads(SAMPLES.read_text(encoding="utf-8"))
        if len(cached) >= n:
            return cached[:n]
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    out: list[dict[str, str]] = []
    with httpx.Client(headers={"User-Agent": "ResearchGPT/0.1"}, timeout=8.0) as c:
        for paper in gold["papers"]:
            if len(out) >= n:
                break
            r = c.get(
                f"https://api.openalex.org/works/doi:{paper['doi']}",
                params={"mailto": "sreekaran005@gmail.com"},
            )
            if r.status_code != 200:
                continue
            abstract = deinvert(r.json().get("abstract_inverted_index"))
            if len(abstract) < 400:
                continue
            out.append({"title": paper["title"], "abstract": abstract})
            time.sleep(0.15)
    return out


def score_one(raw: str) -> dict[str, Any]:
    """Grade one model response."""
    res: dict[str, Any] = {
        "parse_ok": False, "validate_ok": False,
        "fields_populated": 0, "schema_echo": False,
    }
    try:
        obj = extract_json(raw)
    except ValueError:
        return res
    res["parse_ok"] = True

    # qwen was observed returning the literal placeholder "string"
    flat = json.dumps(obj).lower()
    res["schema_echo"] = '"string"' in flat

    try:
        spans = [
            {
                "chunk_id": "c0",
                "quote": str(sp.get("quote", ""))[:400],
                "start_char": 0,
                "end_char": len(str(sp.get("quote", ""))[:400]),
            }
            for sp in (obj.get("evidence_spans") or [])
            if isinstance(sp, dict)
        ]
        ins = PaperInsight(
            paper_id="bakeoff",
            **{k: v for k, v in obj.items() if k in INSIGHT_FIELDS},
            evidence_spans=spans,
        )
        res["validate_ok"] = True
        res["fields_populated"] = sum(
            1 for f in CONTENT_FIELDS if getattr(ins, f) not in (None, [], "")
        )
    except Exception as exc:  # pydantic or shape errors
        res["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return res


def main() -> None:
    cfg = load_config("configs/default.yaml")
    tpl = PROMPT.read_text(encoding="utf-8")
    samples = fetch_samples(5)
    print(f"fetched {len(samples)} real abstracts from the gold set\n")

    client = LLMClient(cfg.llm)
    results: dict[str, Any] = {}

    for arm in ARMS:
        print(f"=== {arm} ===", flush=True)
        rows, spent, disqualified = [], 0.0, None
        for i, s in enumerate(samples, 1):
            if spent > ARM_BUDGET_S:
                disqualified = f"exceeded {ARM_BUDGET_S:.0f}s budget after {i-1} papers"
                print(f"  ABANDONED: {disqualified}")
                break
            prompt = (
                tpl.replace("{title}", s["title"])
                .replace("{text_availability}", "abstract_only")
                .replace("{text}", s["abstract"])
            )
            t0 = time.time()
            try:
                raw = client.complete(prompt, model=arm, use_cache=False)
                dt = time.time() - t0
                row = score_one(raw)
            except (LLMError, RateLimitExceeded) as exc:
                dt = time.time() - t0
                row = {
                    "parse_ok": False, "validate_ok": False, "fields_populated": 0,
                    "schema_echo": False, "error": f"{type(exc).__name__}: {str(exc)[:90]}",
                }
            spent += dt
            row["latency_s"] = round(dt, 1)
            rows.append(row)
            flag = "OK " if row["validate_ok"] else "FAIL"
            echo = " SCHEMA-ECHO" if row.get("schema_echo") else ""
            print(f"  [{i}/{len(samples)}] {flag} {dt:6.1f}s  fields={row['fields_populated']}/8{echo}"
                  f"{'  ' + row.get('error', '') if row.get('error') else ''}", flush=True)

        n = len(rows) or 1
        results[arm] = {
            "n": len(rows),
            "disqualified": disqualified,
            "parse_rate": sum(r["parse_ok"] for r in rows) / n,
            "validate_rate": sum(r["validate_ok"] for r in rows) / n,
            "avg_fields": sum(r["fields_populated"] for r in rows) / n,
            "schema_echoes": sum(r["schema_echo"] for r in rows),
            "avg_latency_s": round(sum(r["latency_s"] for r in rows) / n, 1),
            "total_s": round(spent, 1),
            "rows": rows,
        }
        print()

    for arm, reason in DISQUALIFIED.items():
        results[arm] = {"n": 0, "disqualified": reason}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("=" * 78)
    print(f"{'model':24s} {'parse':>6s} {'valid':>6s} {'fields':>7s} {'echo':>5s} {'lat':>7s}  note")
    print("-" * 78)
    for arm, r in results.items():
        if not r.get("n"):
            print(f"{arm:24s} {'DISQUALIFIED':>32s}  {r['disqualified'][:60]}")
            continue
        note = r["disqualified"] or ""
        print(f"{arm:24s} {r['parse_rate']:6.0%} {r['validate_rate']:6.0%} "
              f"{r['avg_fields']:5.1f}/8 {r['schema_echoes']:5d} {r['avg_latency_s']:6.1f}s  {note}")
    print("=" * 78)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
