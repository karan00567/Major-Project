"""T-410 — every metric a completed run can be scored on, in one report.

``flagship_recall.py`` answers one question (did retrieval find the gold
papers at all). This answers the rest, from the same two files every run
already writes — ``corpus.json`` and ``trace.jsonl`` — so it can be pointed at
any past run and produce a comparable row. Nothing here re-runs the pipeline
and nothing here calls a model.

**On precision.** Two different precisions get called by that name here and
they are NOT interchangeable:

* **retrieval precision@k** — of the top *k* ranked papers, how many are in
  the answer key. With a 35-paper key against a pool in the thousands this is
  necessarily tiny, and it is *not* a quality verdict: a paper absent from one
  researcher's bibliography is not thereby irrelevant. Report it as ranking
  behaviour, never as "the system is 3% accurate".
* **grounding precision** — of the claims the Writer made, how many the
  Verifier could support against the cited paper. This one *is* a quality
  measure, and it is the one `SPEC §14.2` cares about.

**Ranking order.** ``corpus.json`` lists papers in the order the Ranker left
them (``agents/ranker.py`` reorders ``state['papers']`` in place), so index
position IS rank. If that ever stops being true, every @k number here silently
becomes insertion order — the defect that made the T-212 harness read 0.029
instead of 0.057 — so the report prints the check rather than assuming it.

Run::

    python -m researchgpt.eval.run_metrics --run t410_cap100
    python -m researchgpt.eval.run_metrics --run flagship --compare t410_cap100
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
from datetime import datetime
from typing import Any

from researchgpt.eval.flagship_recall import load_gold, match

AT_K = (10, 20, 40, 60, 100, 250, 500)


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------


def load_run(run_dir: pathlib.Path) -> tuple[dict, list[dict]]:
    corpus_path = run_dir / "corpus.json"
    trace_path = run_dir / "trace.jsonl"
    if not corpus_path.exists():
        raise SystemExit(f"{corpus_path} missing - did the run finish?")
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    rows = []
    if trace_path.exists():
        for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return corpus, rows


def last_payload(rows: list[dict], event: str) -> dict:
    for row in reversed(rows):
        if row.get("event") == event:
            return row.get("payload") or {}
    return {}


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------


def retrieval_metrics(corpus: dict) -> dict[str, Any]:
    by_doi, by_title = load_gold()
    n_gold = len(by_doi)
    papers = corpus["papers"]
    extracted = set(corpus.get("extracted_paper_ids") or [])

    # rank position (1-indexed) of every gold paper, first occurrence wins
    ranks: dict[str, int] = {}
    in_corpus: set[str] = set()
    for i, record in enumerate(papers, 1):
        gold_doi = match(record, by_doi, by_title)
        if not gold_doi:
            continue
        ranks.setdefault(gold_doi, i)
        if record.get("paper_id") in extracted:
            in_corpus.add(gold_doi)

    at_k = {}
    for k in AT_K:
        if k > len(papers):
            continue
        hits = sum(1 for r in ranks.values() if r <= k)
        at_k[k] = {"hits": hits, "recall": hits / n_gold, "precision": hits / k}

    mrr = sum(1 / r for r in ranks.values()) / n_gold if ranks else 0.0
    return {
        "gold_papers": n_gold,
        "pool_size": len(papers),
        "corpus_size": len(extracted),
        "union_recall": len(ranks) / n_gold,
        "corpus_recall": len(in_corpus) / n_gold,
        "mrr": mrr,
        "best_rank": min(ranks.values()) if ranks else None,
        "median_rank": sorted(ranks.values())[len(ranks) // 2] if ranks else None,
        "at_k": at_k,
        "gold_ranks": dict(sorted(ranks.items(), key=lambda kv: kv[1])),
        "missed": sorted(set(by_doi) - set(ranks)),
    }


def source_metrics(corpus: dict, rows: list[dict]) -> dict[str, Any]:
    log = corpus.get("retrieval_log") or []
    by_source = collections.Counter()
    returned = collections.Counter()
    errors = collections.Counter()
    for entry in log:
        by_source[entry["source"]] += entry.get("new") or 0
        returned[entry["source"]] += entry.get("returned") or 0
        if entry.get("error"):
            errors[entry["source"]] += 1
    planned = {e.get("planned_query", e.get("query")) for e in log}
    issued = {e["query"] for e in log}
    return {
        "planned_queries": len(planned),
        "issued_queries": len(issued),
        "widening_factor": round(len(issued) / len(planned), 2) if planned else None,
        "source_queries": len(log),
        "new_papers_by_source": dict(by_source),
        "returned_by_source": dict(returned),
        "errors_by_source": dict(errors),
        "papers_by_source": dict(collections.Counter(
            p.get("source") for p in corpus["papers"])),
    }


def quality_metrics(rows: list[dict]) -> dict[str, Any]:
    extract = last_payload(rows, "extract_summary")
    verify = last_payload(rows, "verification_summary")
    review = last_payload(rows, "review_written")
    decisions = [r["payload"].get("decision") for r in rows
                 if r.get("event") == "critic_decision"]
    claims = verify.get("claims") or 0
    supported = verify.get("supported") or 0
    partial = verify.get("partial") or 0
    dropped = verify.get("dropped") or 0
    return {
        "extraction": {
            "papers": extract.get("papers"),
            "mean_fields_of_8": extract.get("mean_fields_of_8"),
            "repair_passes": extract.get("repair_passes"),
            "failed_after_repairs": extract.get("failed_after_repairs"),
            "placeholder_echoes_removed": extract.get("placeholder_echoes_removed"),
            "skipped_no_text": extract.get("skipped_no_text"),
        },
        "writing": {
            "sections": review.get("sections"),
            "references": review.get("references"),
            "chars": review.get("chars"),
            "citations_dropped": review.get("citations_dropped"),
        },
        "verification": {
            "claims": claims,
            "supported": supported,
            "partial": partial,
            "unsupported_dropped": dropped,
            "contradicted": verify.get("contradicted"),
            "abstract_only_capped": verify.get("abstract_only_capped"),
            "grounding_score": verify.get("grounding_score"),
            # The headline quality number: of the claims written, the share the
            # Verifier could stand behind at all (SUPPORTED or PARTIAL).
            "grounding_precision": (claims - dropped) / claims if claims else None,
            # And the strict one: full support, not partial.
            "strict_precision": supported / claims if claims else None,
        },
        "loop": {
            "critic_decisions": decisions,
            "iterations": max((r.get("iteration") or 0) for r in rows) if rows else 0,
            "replans": sum(1 for d in decisions if d == "REPLAN"),
        },
    }


def cost_metrics(rows: list[dict], cache_dir: pathlib.Path) -> dict[str, Any]:
    from researchgpt.core.llm import estimate_tokens

    requests = [r for r in rows if r.get("event") == "request"]
    prompt_tokens = response_tokens = 0
    for req in requests:
        digest = (req.get("payload") or {}).get("prompt_hash")
        path = cache_dir / f"{digest}.json"
        if not path.exists():
            continue
        entry = json.loads(path.read_text(encoding="utf-8"))
        prompt_tokens += estimate_tokens(entry.get("prompt") or "")
        response_tokens += estimate_tokens(entry.get("response") or "")

    per_agent: dict[str, float] = {}
    started: dict[str, datetime] = {}
    for row in rows:
        when = datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
        if row.get("event") == "agent_start":
            started[row["agent"]] = when
        elif row.get("event") == "agent_end" and row["agent"] in started:
            per_agent[row["agent"]] = round(
                per_agent.get(row["agent"], 0.0)
                + (when - started[row["agent"]]).total_seconds(), 1)
    wall = 0.0
    if rows:
        wall = (datetime.fromisoformat(rows[-1]["ts"].replace("Z", "+00:00"))
                - datetime.fromisoformat(rows[0]["ts"].replace("Z", "+00:00"))
                ).total_seconds()
    return {
        "llm_requests": len(requests),
        "prompt_tokens_est": prompt_tokens,
        "response_tokens_est": response_tokens,
        "total_tokens_est": prompt_tokens + response_tokens,
        # What the provider actually reserves per request at admission, which is
        # the number that exhausts a daily budget (measured from a Groq 429:
        # "Requested 5520" = a 3,472-token prompt + max_tokens 2048).
        "reserved_tokens_est": prompt_tokens + 2048 * len(requests),
        "wall_seconds": round(wall, 1),
        "seconds_by_agent": per_agent,
    }


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------


def collect(run: str, runs_dir: pathlib.Path, cache_dir: pathlib.Path) -> dict[str, Any]:
    corpus, rows = load_run(runs_dir / run)
    return {
        "run": run,
        "retrieval": retrieval_metrics(corpus),
        "sources": source_metrics(corpus, rows),
        "quality": quality_metrics(rows),
        "cost": cost_metrics(rows, cache_dir),
        "ranking_order_verified": bool(
            last_payload(rows, "rank_summary")), # a rank_summary means the
        # Ranker ran; without it corpus.json is insertion order and every @k
        # below is meaningless (the T-212 defect).
    }


def render(m: dict[str, Any], base: dict[str, Any] | None = None) -> None:
    r, s, q, c = m["retrieval"], m["sources"], m["quality"], m["cost"]

    def delta(new, old, fmt="{:+.3f}"):
        if base is None or old is None or new is None:
            return ""
        return "   " + fmt.format(new - old)

    br = base["retrieval"] if base else None
    print(f"\n{'=' * 74}\nRUN METRICS - {m['run']}\n{'=' * 74}")
    if base:
        print(f"(deltas against {base['run']})")
    if not m["ranking_order_verified"]:
        print("\n  !! no rank_summary in the trace - corpus.json is INSERTION "
              "order, so every @k number below is meaningless")

    print(f"\n-- retrieval, against a {r['gold_papers']}-paper answer key "
          f"{'-' * 22}")
    print(f"  pool size            {r['pool_size']:6d}"
          + (f"   ({base['retrieval']['pool_size']} before)" if base else ""))
    print(f"  UNION RECALL         {r['union_recall']:6.3f}   "
          f"({len(r['gold_ranks'])}/{r['gold_papers']})"
          + delta(r["union_recall"], br and br["union_recall"]))
    print(f"  corpus recall        {r['corpus_recall']:6.3f}   "
          f"(bounded by max_papers/{r['gold_papers']})"
          + delta(r["corpus_recall"], br and br["corpus_recall"]))
    print(f"  MRR                  {r['mrr']:6.3f}"
          + delta(r["mrr"], br and br["mrr"]))
    print(f"  best / median rank   {r['best_rank']} / {r['median_rank']}")
    print(f"\n  {'k':>6}  {'recall@k':>9}  {'precision@k':>12}  {'gold in top k':>14}")
    for k, row in r["at_k"].items():
        print(f"  {k:6d}  {row['recall']:9.3f}  {row['precision']:12.4f}"
              f"  {row['hits']:14d}")

    print(f"\n-- sources {'-' * 62}")
    print(f"  planned queries      {s['planned_queries']}")
    print(f"  issued queries       {s['issued_queries']}  "
          f"(widening x{s['widening_factor']})")
    print(f"  source-queries       {s['source_queries']}")
    print(f"  papers by source     {s['papers_by_source']}")
    if any(s["errors_by_source"].values()):
        print(f"  ERRORS by source     {s['errors_by_source']}")

    e, v, w, loop = q["extraction"], q["verification"], q["writing"], q["loop"]
    print(f"\n-- extraction {'-' * 59}")
    print(f"  papers extracted     {e['papers']}")
    print(f"  mean fields of 8     {e['mean_fields_of_8']}")
    print(f"  repairs / failures   {e['repair_passes']} / {e['failed_after_repairs']}")
    print(f"  placeholder echoes   {e['placeholder_echoes_removed']}")

    print(f"\n-- writing and verification {'-' * 45}")
    print(f"  sections / refs      {w['sections']} / {w['references']}  "
          f"({w['chars']} chars, {w['citations_dropped']} citations dropped)")
    print(f"  claims               {v['claims']}")
    print(f"  supported            {v['supported']}")
    print(f"  partial              {v['partial']}")
    print(f"  dropped UNSUPPORTED  {v['unsupported_dropped']}")
    print(f"  contradicted         {v['contradicted']}")
    print(f"  abstract-only capped {v['abstract_only_capped']}")
    if v["grounding_score"] is not None:
        print(f"  GROUNDING SCORE      {v['grounding_score']:.4f}")
    if v["grounding_precision"] is not None:
        print(f"  grounding precision  {v['grounding_precision']:.4f}"
              f"   (kept claims / written claims)")
    if v["strict_precision"] is not None:
        print(f"  strict precision     {v['strict_precision']:.4f}"
              f"   (SUPPORTED only - 0 while every paper is abstract-only)")

    print(f"\n-- loop and cost {'-' * 56}")
    print(f"  critic decisions     {loop['critic_decisions']}  "
          f"(replans {loop['replans']})")
    print(f"  llm requests         {c['llm_requests']}")
    print(f"  tokens (est)         {c['total_tokens_est']:,} used, "
          f"{c['reserved_tokens_est']:,} reserved against a 200,000/day budget")
    print(f"  wall clock           {c['wall_seconds']:.0f}s "
          f"({c['wall_seconds']/60:.1f} min)")
    print(f"  by agent             {c['seconds_by_agent']}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-410 - full metrics for one run.")
    ap.add_argument("--run", required=True)
    ap.add_argument("--compare", help="baseline run to show deltas against")
    ap.add_argument("--runs-dir", type=pathlib.Path, default=pathlib.Path("outputs/runs"))
    ap.add_argument("--cache-dir", type=pathlib.Path,
                    default=pathlib.Path("data/llm_cache"))
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args(argv)

    metrics = collect(args.run, args.runs_dir, args.cache_dir)
    base = (collect(args.compare, args.runs_dir, args.cache_dir)
            if args.compare else None)
    render(metrics, base)

    out = args.out or pathlib.Path(f"eval/run_metrics_{args.run}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"metrics": metrics}
    if base:
        payload["baseline"] = base
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
