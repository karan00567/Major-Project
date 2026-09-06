from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time
from datetime import datetime, timezone
from typing import Any

from agents.ollama_client import DEFAULT_NUM_CTX, OllamaClient, OllamaError
from agents.tools import PaperInsight, extract_json, load, version

CONTENT_FIELDS = (
    "methodology", "advantages", "disadvantages", "critique",
    "datasets", "metrics", "results", "limitations",
)


PLACEHOLDERS = {
    "string", "string | null", "null", "none", "n/a", "na", "...",
    "example", "text", "value", "<string>",
}


GROQ_EQUIVALENT_SOURCE_CHARS = 3_904

OUT_DIR = pathlib.Path("agents/out")


def load_papers(run: str | None, pool: str | None, limit: int) -> list[dict[str, Any]]:
    if run:
        path = pathlib.Path("outputs/runs") / run / "corpus.json"
        if not path.is_file():
            raise SystemExit(f"No corpus at {path}. Available runs: "
                             f"{sorted(p.name for p in pathlib.Path('outputs/runs').glob('*'))[:10]}")
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else (data.get("papers") or [])
    else:
        path = pathlib.Path(pool or "eval/cache/pool_mps25.json")
        if not path.is_file():
            raise SystemExit(f"No pool at {path}.")
        data = json.loads(path.read_text(encoding="utf-8"))
        blob = data.get("pool", data)
        rows = list(blob.values()) if isinstance(blob, dict) else blob

    with_abstract = [r for r in rows if (r.get("abstract") or "").strip()]
    return with_abstract[:limit]


def count_placeholders(insight: PaperInsight) -> int:
    hits = 0
    for field in CONTENT_FIELDS:
        value = getattr(insight, field, None)
        if isinstance(value, str) and value.strip().lower() in PLACEHOLDERS:
            hits += 1
        elif isinstance(value, list):
            hits += sum(1 for v in value
                        if isinstance(v, str) and v.strip().lower() in PLACEHOLDERS)
    return hits


def filled_fields(insight: PaperInsight) -> int:
    n = 0
    for field in CONTENT_FIELDS:
        value = getattr(insight, field, None)
        if isinstance(value, str) and value.strip():
            n += 1
        elif isinstance(value, list) and value:
            n += 1
    return n


def extract_one(
    client: OllamaClient,
    paper: dict[str, Any],
    *,
    max_source_chars: int,
    max_tokens: int,
) -> dict[str, Any]:
    text = (paper.get("abstract") or "").strip()
    truncated = 0
    if len(text) > max_source_chars:
        truncated = len(text) - max_source_chars
        text = text[:max_source_chars].rsplit(" ", 1)[0] + " [truncated to fit the prompt budget]"

    prompt = load(
        "extractor_v1",
        title=paper.get("title") or "",
        text_availability=paper.get("text_availability") or "abstract_only",
        text=text,
    )

    record: dict[str, Any] = {
        "paper_id": paper.get("paper_id"),
        "title": (paper.get("title") or "")[:120],
        "prompt_chars": len(prompt),
        "source_chars": len(text),
        "source_truncated_chars": truncated,
    }

    t0 = time.monotonic()
    try:
        raw = client.complete(prompt, max_tokens=max_tokens)
    except OllamaError as exc:
        record.update(ok=False, stage="request", error=str(exc)[:400],
                      seconds=round(time.monotonic() - t0, 1))
        return record
    record["seconds"] = round(time.monotonic() - t0, 1)
    record["response_chars"] = len(raw)

    try:
        obj = extract_json(raw)
    except ValueError as exc:

        record.update(ok=False, stage="parse", error=str(exc)[:200],
                      raw_head=raw[:300])
        return record

    try:
        insight = PaperInsight(paper_id=str(paper.get("paper_id") or ""), **{
            k: v for k, v in obj.items() if k in PaperInsight.model_fields
        })
    except Exception as exc:
        record.update(ok=False, stage="validate", error=str(exc)[:300],
                      parsed_keys=sorted(obj.keys())[:16])
        return record

    record.update(
        ok=True,
        stage="done",
        fields_filled=filled_fields(insight),
        placeholder_echoes=count_placeholders(insight),
        extracted_chars=sum(
            len(getattr(insight, f) or "") if isinstance(getattr(insight, f, None), str)
            else len("; ".join(getattr(insight, f) or []))
            for f in CONTENT_FIELDS
        ),
        insight=insight.model_dump(),
    )
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract with a local Ollama model.")
    ap.add_argument("--host", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    ap.add_argument("--n", type=int, default=5, help="papers to process")
    ap.add_argument("--run", default=None, help="read outputs/runs/<run>/corpus.json")
    ap.add_argument("--pool", default=None, help="read a cached eval pool JSON")
    ap.add_argument("--max-source-chars", type=int, default=GROQ_EQUIVALENT_SOURCE_CHARS)
    ap.add_argument("--max-tokens", type=int, default=2_560)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    client = OllamaClient(host=args.host, model=args.model, num_ctx=args.num_ctx)
    health = client.health()
    if not health["ok"]:
        print(f"Ollama unreachable: {health['error']}", file=sys.stderr)
        print("Run `python -m agents.probe` first.", file=sys.stderr)
        return 1
    if not health["model_present"]:
        print(f"Model {client.model!r} not on the server. "
              f"Have: {', '.join(health['models']) or '(none)'}", file=sys.stderr)
        return 1

    papers = load_papers(args.run, args.pool, args.n)
    if not papers:
        print("No papers with abstracts found.", file=sys.stderr)
        return 1

    print(f"model      {client.model}  @ {client.host}  (num_ctx {client.num_ctx:,})")
    print(f"prompt     extractor_v1 v{version('extractor_v1')}")
    print(f"source cap {args.max_source_chars:,} chars"
          f"{'  (Groq-equivalent)' if args.max_source_chars == GROQ_EQUIVALENT_SOURCE_CHARS else '  (local-only headroom)'}")
    print(f"papers     {len(papers)}\n")

    records: list[dict[str, Any]] = []
    for i, paper in enumerate(papers, 1):
        rec = extract_one(
            client, paper,
            max_source_chars=args.max_source_chars,
            max_tokens=args.max_tokens,
        )
        records.append(rec)
        if rec["ok"]:
            print(f"  [{i}/{len(papers)}] ok    {rec['fields_filled']}/8 fields  "
                  f"{rec['extracted_chars']:>5} chars  {rec['seconds']:>6.1f}s  "
                  f"{rec['title'][:52]}")
        else:
            print(f"  [{i}/{len(papers)}] FAIL  {rec['stage']:<9} "
                  f"{str(rec.get('error', ''))[:60]}  {rec['title'][:40]}")

    ok = [r for r in records if r["ok"]]
    summary = {
        "model": client.model,
        "host": client.host,
        "num_ctx": client.num_ctx,
        "prompt_version": version("extractor_v1"),
        "max_source_chars": args.max_source_chars,
        "papers": len(records),
        "parsed_ok": len(ok),
        "parse_rate": round(len(ok) / len(records), 3) if records else 0.0,
        "mean_fields_of_8": round(statistics.mean([r["fields_filled"] for r in ok]), 2) if ok else 0.0,
        "placeholder_echoes": sum(r["placeholder_echoes"] for r in ok),
        "median_extracted_chars": statistics.median([r["extracted_chars"] for r in ok]) if ok else 0,
        "median_seconds": round(statistics.median([r["seconds"] for r in ok]), 1) if ok else None,
        "cache_hits": client.cache_hits,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    print(f"\n  parse rate         {summary['parse_rate']:.0%}  ({summary['parsed_ok']}/{summary['papers']})")
    print(f"  mean fields        {summary['mean_fields_of_8']}/8")
    print(f"  placeholder echoes {summary['placeholder_echoes']}"
          f"{'   <- FABRICATED CONTENT, this model is not usable' if summary['placeholder_echoes'] else ''}")
    print(f"  median extracted   {summary['median_extracted_chars']} chars")
    print(f"  median latency     {summary['median_seconds']}s/paper")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = client.model.replace(":", "_").replace("/", "_")
    out = OUT_DIR / f"extract_{safe}_{stamp}.json"
    out.write_text(
        json.dumps({"summary": summary, "records": records}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
