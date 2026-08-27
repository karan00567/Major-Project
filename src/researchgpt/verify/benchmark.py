"""T-306 — per-claim CPU latency for the int8 verifier.

TASKLIST's framing: a full run makes roughly 1,500–2,000 verifier forward
passes, so the number that matters is **claims/sec on this machine**, not
milliseconds in isolation. At 20/sec the verification stage is ~100 s; at 2/sec
it is ~15 minutes and starts to compete with the ~30-minute budget in §0.2.

Measures three things, because they answer different questions:

* **batch=1 latency** — what a single interactive verification costs, which is
  what the Vue evidence panel (T-607) would pay on a click.
* **batched throughput** — what the pipeline actually gets, since T-504 verifies
  a whole draft's claims at once and can batch freely.
* **tokenization share** — DeBERTa's SentencePiece tokenizer is not free, and if
  it dominates then batching the *model* is the wrong optimisation.

Measured 2026-08-27 (this machine, CPU, int8, ``max_length=256``)::

    batch   claims/sec   ms/claim
        1         33.3      30.07
        8         14.9      67.19
       16         12.9      77.71
       32         10.0      99.82

**33.3 claims/sec at batch=1**, so a 2,000-forward-pass run spends about a
minute in the verifier — comfortably inside §0.2's budget.

⚠️ **Batching makes it slower — 3.3x slower at batch=32. This is a design
instruction for T-502, not a curiosity.** Two reasons compound: padding (pairs
average 59 tokens against a 121-token max, so a padded batch wastes over half
its compute) and the fact that ONNX Runtime's int8 CPU kernels are already
internally threaded, so a larger batch buys no extra parallelism and only pays
the padding. Tokenization is 2% of wall time, so it is not the bottleneck
either.

**T-502 should feed the verifier one pair at a time.** The intuition carried
over from GPU training — "always batch" — is actively wrong here.

Run::

    python -m researchgpt.verify.benchmark --model data/models/verifier-onnx
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import time
from typing import Any

from researchgpt.verify.evaluate import encode_pair
from researchgpt.verify.scifact_pairs import read_jsonl

DEFAULT_PAIRS = pathlib.Path("data/scifact/pairs_validation.jsonl")


def _find_onnx(model_dir: pathlib.Path) -> pathlib.Path:
    candidate = next(model_dir.glob("*quantized*.onnx"), None) or next(
        model_dir.glob("*.onnx"), None
    )
    if candidate is None:
        raise SystemExit(f"no .onnx file under {model_dir}")
    return candidate


def benchmark(
    model_dir: pathlib.Path,
    pairs: list[dict[str, Any]],
    *,
    batch_sizes: tuple[int, ...] = (1, 8, 16, 32),
    max_length: int = 256,
    warmup: int = 3,
) -> dict[str, Any]:
    import numpy as np
    import onnxruntime as ort
    from transformers import AutoTokenizer

    onnx_path = _find_onnx(model_dir)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

    # Default session options: one intra-op thread pool sized by ORT. The
    # pipeline shares the CPU with embedding and reranking, so pinning threads
    # here would just move the contention somewhere less visible.
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_names = {i.name for i in session.get_inputs()}

    print(f"model : {onnx_path.name}  ({onnx_path.stat().st_size / 1e6:.1f} MB)")
    print(f"pairs : {len(pairs)}  max_length={max_length}")
    print(f"onnxruntime {ort.__version__}, providers={session.get_providers()}\n")

    def tokenize(batch: list[dict[str, Any]]) -> dict[str, Any]:
        enc = tokenizer(
            [encode_pair(p)[0] for p in batch],
            [encode_pair(p)[1] for p in batch],
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="np",
        )
        return {k: v.astype(np.int64) for k, v in enc.items() if k in input_names}

    # Warm up: the first few calls pay graph-init and allocator costs that would
    # otherwise be charged to the batch=1 arm and make it look 3x worse.
    for _ in range(warmup):
        session.run(None, tokenize(pairs[:8]))

    results: dict[str, Any] = {}
    print(f"  {'batch':>6s} {'claims/sec':>11s} {'ms/claim':>10s} {'ms/batch p50':>13s}")
    for batch_size in batch_sizes:
        batches = [pairs[i : i + batch_size] for i in range(0, len(pairs), batch_size)]
        # batch=1 over the whole set is slow and adds nothing after ~200 samples.
        if batch_size == 1:
            batches = batches[:200]

        times: list[float] = []
        tokenize_time = 0.0
        start_all = time.perf_counter()
        n_claims = 0
        for batch in batches:
            t0 = time.perf_counter()
            feeds = tokenize(batch)
            t1 = time.perf_counter()
            session.run(None, feeds)
            t2 = time.perf_counter()
            tokenize_time += t1 - t0
            times.append(t2 - t0)
            n_claims += len(batch)
        elapsed = time.perf_counter() - start_all

        per_sec = n_claims / elapsed
        results[str(batch_size)] = {
            "claims_per_sec": per_sec,
            "ms_per_claim": 1000 * elapsed / n_claims,
            "ms_per_batch_p50": 1000 * statistics.median(times),
            "tokenize_share": tokenize_time / elapsed,
            "n_claims": n_claims,
        }
        print(
            f"  {batch_size:6d} {per_sec:11.1f} {1000 * elapsed / n_claims:10.2f} "
            f"{1000 * statistics.median(times):13.2f}"
        )

    best = max(results.values(), key=lambda r: r["claims_per_sec"])
    print(f"\n  tokenization is {best['tokenize_share']:.0%} of wall time at the best batch size")
    return results


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-306 - CPU throughput of the int8 verifier.")
    ap.add_argument("--model", type=pathlib.Path, required=True,
                    help="directory holding the quantized .onnx and its tokenizer")
    ap.add_argument("--pairs", type=pathlib.Path, default=DEFAULT_PAIRS)
    ap.add_argument("--limit", type=int, default=256)
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("eval/verifier_latency_t306.json"))
    args = ap.parse_args(argv)

    pairs = read_jsonl(args.pairs)[: args.limit]
    print("T-306 - verifier CPU throughput\n")
    results = benchmark(args.model, pairs, max_length=args.max_length)

    best_bs, best = max(results.items(), key=lambda kv: kv[1]["claims_per_sec"])
    rate = best["claims_per_sec"]
    # TASKLIST's own sizing: a full run is ~1.5-2k forward passes.
    print("\n" + "=" * 66)
    print(f"BEST: {rate:.1f} claims/sec at batch={best_bs}")
    for passes in (1500, 2000):
        print(f"  a {passes}-claim run spends {passes / rate:6.1f} s "
              f"({passes / rate / 60:.1f} min) in the verifier")
    print("=" * 66)
    if rate < 20:
        print("NOTE: below TASKLIST T-306's 20/sec reference point. Verification becomes a "
              "visible share of the ~30 min budget (0.2); consider batching harder in T-502.")
    else:
        print("Comfortably above T-306's 20/sec reference point.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"task": "T-306", "model": str(args.model), "results": results}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
