"""Connectivity and fit probe - run this FIRST, before anything else here.

    python -m agents.probe
    python -m agents.probe --host http://192.168.1.7:8080 --model qwen2.5:3b-instruct

Answers four questions in order, and stops at the first one that fails:

  1. Is an Ollama server reachable at the host?
  2. Does it hold the model we intend to use?
  3. Does that model honour a long prompt? (the num_ctx trap - see below)
  4. How fast is it, in tokens/second?

Question 3 is the one worth the file. Ollama's default context is 2048 tokens
and the extractor prompt is ~3,530 before any paper text. A model that silently
truncates the prompt still returns confident JSON, so this probe plants a
canary near the START of a long prompt and asks the model to repeat it back. If
the canary comes back, the whole prompt survived. If it does not, num_ctx is
too small and every extraction from this server is being answered from a
half-read prompt.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid

from agents.ollama_client import (
    DEFAULT_NUM_CTX,
    OllamaClient,
    OllamaError,
)

#: Rough q4_K_M weight footprints, for a 5 GB card. The KV cache for
#: num_ctx 8192 adds roughly 0.3-0.8 GB on top of the weights, which is why the
#: 7B row is marked tight rather than comfortable: it fits the card but not the
#: card plus a useful context window.
VRAM_GUIDE = [
    ("llama3.2:3b",             2.0, "comfortable at num_ctx 8192"),
    ("qwen2.5:3b-instruct",     1.9, "comfortable at num_ctx 8192  <- recommended"),
    ("phi3.5:3.8b",             2.2, "comfortable at num_ctx 8192"),
    ("gemma2:2b",               1.6, "comfortable; weakest of the set"),
    ("qwen2.5:7b-instruct",     4.7, "TIGHT - fits weights, spills KV cache; use num_ctx 4096"),
    ("gemma2:9b",               5.4, "does NOT fit 5 GB; partial CPU offload, very slow"),
    ("gpt-oss:20b",            13.0, "does NOT fit 5 GB - not usable on this machine"),
]


def _fmt_guide() -> str:
    lines = ["", "  Model sizing for a 5 GB card (q4_K_M weights):", ""]
    lines.append(f"    {'model':<24} {'~VRAM':>7}   note")
    lines.append(f"    {'-' * 24} {'-' * 7}   {'-' * 44}")
    for name, gb, note in VRAM_GUIDE:
        lines.append(f"    {name:<24} {gb:>5.1f}GB   {note}")
    return "\n".join(lines)


def probe_context(client: OllamaClient, num_ctx: int) -> dict:
    """Plant a canary at the front of a long prompt and ask for it back.

    The filler sits BETWEEN the canary and the question, so the only way to
    answer is to have read past roughly ``num_ctx`` tokens of input. A model
    whose context silently truncated will have lost the canary and will make
    something up - which is precisely the failure this detects.
    """
    canary = uuid.uuid4().hex[:8]
    # ~4 chars/token, filled to about 85% of the window so the answer has room.
    filler_tokens = int(num_ctx * 0.85)
    filler = ("The quick brown fox jumps over the lazy dog. " * (filler_tokens // 11))

    prompt = (
        f"MEMO CODE: {canary}\n\n"
        f"{filler}\n\n"
        "Ignore everything between the memo code and this line. "
        "Reply with the memo code and nothing else."
    )
    approx_tokens = len(prompt) // 4

    t0 = time.monotonic()
    try:
        out = client.complete(prompt, max_tokens=32, use_cache=False)
    except OllamaError as exc:
        return {"ok": False, "error": str(exc), "approx_prompt_tokens": approx_tokens}
    elapsed = time.monotonic() - t0

    found = canary in out
    return {
        "ok": found,
        "canary": canary,
        "returned": out.strip()[:120],
        "approx_prompt_tokens": approx_tokens,
        "num_ctx": num_ctx,
        "seconds": round(elapsed, 1),
    }


def probe_speed(client: OllamaClient) -> dict:
    """One short generation, timed. Tokens/sec is what decides feasibility."""
    prompt = (
        "In three sentences, explain what a cross-encoder reranker does "
        "in a retrieval pipeline."
    )
    t0 = time.monotonic()
    try:
        out = client.complete(prompt, max_tokens=192, use_cache=False)
    except OllamaError as exc:
        return {"ok": False, "error": str(exc)}
    elapsed = time.monotonic() - t0
    approx_out = max(1, len(out) // 4)
    return {
        "ok": True,
        "seconds": round(elapsed, 1),
        "approx_output_tokens": approx_out,
        "tokens_per_second": round(approx_out / elapsed, 1) if elapsed else None,
        "sample": out.strip()[:200],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Probe a local Ollama server.")
    ap.add_argument("--host", default=None, help="e.g. http://192.168.1.7:8080")
    ap.add_argument("--model", default=None, help="e.g. qwen2.5:3b-instruct")
    ap.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    client = OllamaClient(host=args.host, model=args.model, num_ctx=args.num_ctx)
    report: dict = {"host": client.host, "model": client.model, "num_ctx": client.num_ctx}

    # 1. reachable ---------------------------------------------------------
    health = client.health()
    report["health"] = health
    if not health["ok"]:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"[1/4] server      FAIL  {health['error']}")
            if health.get("hint"):
                print(f"\n  {health['hint']}")
        return 1
    if not args.json:
        print(f"[1/4] server      OK    {client.host}")
        print(f"                        {len(health['models'])} model(s): "
              f"{', '.join(health['models'][:6]) or '(none)'}")

    # 2. model present -----------------------------------------------------
    if not health["model_present"]:
        report["model_present"] = False
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"[2/4] model       FAIL  {client.model!r} is not on the server")
            print(f"\n  On the serving machine:  ollama pull {client.model}")
            print(_fmt_guide())
        return 1
    if not args.json:
        print(f"[2/4] model       OK    {client.model}")

    # 3. context honoured --------------------------------------------------
    ctx = probe_context(client, client.num_ctx)
    report["context"] = ctx
    if not args.json:
        if ctx["ok"]:
            print(f"[3/4] context     OK    canary survived "
                  f"~{ctx['approx_prompt_tokens']:,} prompt tokens "
                  f"at num_ctx {ctx['num_ctx']:,} ({ctx['seconds']}s)")
        else:
            print(f"[3/4] context     FAIL  canary {ctx.get('canary')!r} did not come back")
            print(f"                        model returned: {ctx.get('returned')!r}")
            print("\n  The prompt is being silently truncated. Every extraction from")
            print("  this server is being answered from a half-read prompt. Either the")
            print("  model's own context is smaller than num_ctx, or the server is")
            print("  clamping it. Try a smaller --num-ctx, or a model with a larger")
            print("  native window.")
            if args.json:
                print(json.dumps(report, indent=2))
            return 1

    # 4. speed -------------------------------------------------------------
    speed = probe_speed(client)
    report["speed"] = speed
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if speed["ok"] else 1

    if not speed["ok"]:
        print(f"[4/4] speed       FAIL  {speed['error']}")
        return 1

    tps = speed["tokens_per_second"]
    print(f"[4/4] speed       OK    ~{tps} tok/s "
          f"({speed['approx_output_tokens']} tokens in {speed['seconds']}s)")

    # A full extraction is ~3,900 prompt tokens in and ~571 out (the measured
    # median on the Groq arm). Output dominates on a local GPU.
    if tps:
        est = 571 / tps
        print(f"\n  Estimated per-paper extraction: ~{est:.0f}s "
              f"(median 571 output tokens at {tps} tok/s)")
        print(f"  Ten papers: ~{est * 10 / 60:.0f} min, before prompt-eval time.")
    print(_fmt_guide())
    return 0


if __name__ == "__main__":
    sys.exit(main())
