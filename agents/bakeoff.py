"""T-004-shaped bake-off across local Ollama models, on the same papers.

    python -m agents.bakeoff --models qwen2.5:3b-instruct llama3.2:3b phi3.5:3.8b
    python -m agents.bakeoff --models qwen2.5:3b-instruct --n 5 --json

Scores every arm on the four criteria T-004 used to pick ``gpt-oss-120b``, in
the order that decided it:

  1. **placeholder echo** - a field returned as the literal schema string
     ("string", "null", ...). Disqualifying, not a deduction. It parses, it
     validates, and it silently injects fabricated content into a pipeline
     graded on not fabricating. This is what removed ``qwen3.6-27b`` from the
     hosted allowlist despite the best field coverage in the field.
  2. **clean parse rate** - JSON recovered without ``format: json`` help.
  3. **field coverage** - mean of 8 content fields populated.
  4. **latency** - per paper.

The hosted baseline is printed alongside so the local arm is read against
something real rather than in isolation. Those numbers are from
``configs/default.yaml`` (T-004, 2026-08-25) and ``eval/metrics_evaluated.md``
(2026-08-29), both measured on this repo.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
from datetime import datetime, timezone
from typing import Any

from agents.extract import (
    GROQ_EQUIVALENT_SOURCE_CHARS,
    extract_one,
    load_papers,
)
from agents.ollama_client import DEFAULT_NUM_CTX, OllamaClient

OUT_DIR = pathlib.Path("agents/out")

#: Measured on this repo, hosted arm. Printed for comparison only - never
#: recomputed here, because a local run cannot re-measure a hosted provider.
HOSTED_BASELINE = {
    "openai/gpt-oss-120b (Groq, T-004)": {
        "parse_rate": 1.00, "mean_fields": 4.6, "echoes": 0, "seconds": 26.6,
        "note": "PRIMARY - the arm the pipeline uses",
    },
    "qwen/qwen3.6-27b (Groq, T-004)": {
        "parse_rate": 1.00, "mean_fields": 7.0, "echoes": 2, "seconds": 41.8,
        "note": "REJECTED - echoed placeholders on 2 of 5 papers",
    },
    "openai/gpt-oss-20b (Groq, t410_cap25)": {
        "parse_rate": 1.00, "mean_fields": 4.8, "echoes": 0, "seconds": 42.1,
        "note": "in use since 2026-08-28 (120b daily budget exhausted)",
    },
}


def run_arm(
    model: str,
    papers: list[dict[str, Any]],
    *,
    host: str | None,
    num_ctx: int,
    max_source_chars: int,
    max_tokens: int,
) -> dict[str, Any]:
    """One model over every paper. A dead arm is a result, not a crash."""
    client = OllamaClient(host=host, model=model, num_ctx=num_ctx)
    health = client.health()
    if not health["ok"]:
        return {"model": model, "available": False, "error": health["error"]}
    if not health["model_present"]:
        return {"model": model, "available": False,
                "error": f"not pulled on the server (have: {', '.join(health['models']) or 'none'})"}

    records = []
    for i, paper in enumerate(papers, 1):
        rec = extract_one(client, paper,
                          max_source_chars=max_source_chars, max_tokens=max_tokens)
        records.append(rec)
        status = "ok" if rec["ok"] else f"FAIL/{rec['stage']}"
        print(f"    [{i}/{len(papers)}] {status:<12} {rec.get('seconds', 0):>6.1f}s  "
              f"{rec['title'][:46]}")

    ok = [r for r in records if r["ok"]]
    echoes = sum(r["placeholder_echoes"] for r in ok)
    return {
        "model": model,
        "available": True,
        "papers": len(records),
        "parse_rate": round(len(ok) / len(records), 3) if records else 0.0,
        "mean_fields": round(statistics.mean([r["fields_filled"] for r in ok]), 2) if ok else 0.0,
        "echoes": echoes,
        "echo_papers": sum(1 for r in ok if r["placeholder_echoes"]),
        "median_seconds": round(statistics.median([r["seconds"] for r in ok]), 1) if ok else None,
        "median_extracted_chars": statistics.median([r["extracted_chars"] for r in ok]) if ok else 0,
        # T-004's rule: an echo disqualifies regardless of every other number.
        "verdict": _verdict(len(ok), len(records), echoes),
        "records": records,
    }


def _verdict(ok: int, total: int, echoes: int) -> str:
    if total and ok == 0:
        return "UNUSABLE - nothing parsed"
    if echoes:
        return "DISQUALIFIED - placeholder echo (fabricated content)"
    if total and ok / total < 0.8:
        return "WEAK - parse rate below 80%"
    return "CANDIDATE"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bake off local Ollama models.")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--host", default=None)
    ap.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    ap.add_argument("--n", type=int, default=5, help="papers per arm")
    ap.add_argument("--run", default=None)
    ap.add_argument("--pool", default=None)
    ap.add_argument("--max-source-chars", type=int, default=GROQ_EQUIVALENT_SOURCE_CHARS)
    ap.add_argument("--max-tokens", type=int, default=2_560)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    papers = load_papers(args.run, args.pool, args.n)
    if not papers:
        print("No papers with abstracts found.", file=sys.stderr)
        return 1

    #  Same papers for every arm, or the comparison means nothing.
    print(f"{len(papers)} paper(s), identical across arms, "
          f"source cap {args.max_source_chars:,} chars\n")

    arms = []
    for model in args.models:
        print(f"  == {model}")
        arms.append(run_arm(
            model, papers,
            host=args.host, num_ctx=args.num_ctx,
            max_source_chars=args.max_source_chars, max_tokens=args.max_tokens,
        ))
        print()

    if args.json:
        print(json.dumps({"arms": arms, "hosted_baseline": HOSTED_BASELINE}, indent=2))
    else:
        print(f"  {'arm':<34} {'parse':>6} {'fields':>7} {'echo':>5} {'sec':>7}   verdict")
        print(f"  {'-' * 34} {'-' * 6} {'-' * 7} {'-' * 5} {'-' * 7}   {'-' * 40}")
        for a in arms:
            if not a["available"]:
                print(f"  {a['model']:<34} {'-':>6} {'-':>7} {'-':>5} {'-':>7}   "
                      f"UNAVAILABLE: {a['error'][:44]}")
                continue
            print(f"  {a['model']:<34} {a['parse_rate']:>5.0%} {a['mean_fields']:>6.2f}/8 "
                  f"{a['echoes']:>5} {str(a['median_seconds']):>7}   {a['verdict']}")

        print(f"\n  hosted baseline, measured on this repo (not re-run here):")
        for name, b in HOSTED_BASELINE.items():
            print(f"  {name:<38} {b['parse_rate']:>5.0%} {b['mean_fields']:>6.1f}/8 "
                  f"{b['echoes']:>5} {b['seconds']:>7}   {b['note']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"bakeoff_{stamp}.json"
    out.write_text(
        json.dumps({"arms": arms, "hosted_baseline": HOSTED_BASELINE,
                    "papers": len(papers), "max_source_chars": args.max_source_chars,
                    "ts": stamp}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
