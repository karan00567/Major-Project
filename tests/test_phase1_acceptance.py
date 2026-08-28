"""Phase 1 acceptance checks from handoffs/phase1.md."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from pydantic import ValidationError

from researchgpt.core.config import load_config
from researchgpt.core.llm import (
    LLMClient,
    ModelNotAllowed,
    RateLimitExceeded,
    extract_json,
)
from researchgpt.core.logging import TraceLogger
from researchgpt.core.models import ALLOWED_MODELS, IMPLEMENTED_SOURCES, LLMConfig, SourcesConfig


def test_t107_trace_logger() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with TraceLogger("run-t107", runs_dir=tmp) as log:
            log.event("planner", "start", {"n": 1}, iteration=0)
            log.event("extractor", "done", {"ok": True}, iteration=1)
            # Non-serialisable payload must still write a line.
            log.event("llm", "bad", {"fh": open(__file__, "rb")})  # noqa: SIM115
            path = log.run_dir / "trace.jsonl"
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3, lines
        for line in lines:
            rec = json.loads(line)
            assert list(rec.keys()) == [
                "ts",
                "run_id",
                "agent",
                "event",
                "iteration",
                "payload",
            ]
        bad = json.loads(lines[2])
        assert "serialisation_error" in bad["payload"]
        assert "repr" in bad["payload"]
    print("T-107 OK")


def test_t104_extract_json() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json(' {"a": 1}\n```') == {"a": 1}
    assert extract_json('{"a": 1}') == {"a": 1}
    print("T-104 extract_json OK")


def test_t104_allowlist() -> None:
    cfg = LLMConfig(model="gemma-4-31b-it", cache_dir=tempfile.mkdtemp())
    client = LLMClient(cfg)
    try:
        client.complete("hi", model="gpt-4o-mini")
        raise AssertionError("expected ModelNotAllowed")
    except ModelNotAllowed:
        pass
    assert client.request_count == 0
    print("T-104 allowlist OK")


def test_t104_cache() -> None:
    cache_dir = tempfile.mkdtemp()
    cfg = LLMConfig(
        model="gemma-4-31b-it",
        cache_dir=cache_dir,
        requests_per_minute=600,
        max_retries=2,
    )
    client = LLMClient(cfg)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"thought": True, "text": "IGNORE"},
                        {"text": "hello-world"},
                    ]
                }
            }
        ]
    }

    with patch("httpx.Client") as ClientCls:
        inst = ClientCls.return_value.__enter__.return_value
        inst.post.return_value = mock_resp
        a = client.complete("prompt-cache-test", use_cache=True)
        b = client.complete("prompt-cache-test", use_cache=True)
        assert a == "hello-world"
        assert b == "hello-world"
        assert client.request_count == 1
        assert client.cache_hits == 1
        assert inst.post.call_count == 1
        # thought parts must be skipped
        assert a == "hello-world"
    print("T-104 cache + thought filter OK")


def test_t104_rate_limit() -> None:
    cache_dir = tempfile.mkdtemp()
    cfg = LLMConfig(
        model="gemma-4-31b-it",
        cache_dir=cache_dir,
        requests_per_minute=6000,
        max_retries=2,
    )
    client = LLMClient(cfg)

    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {}
    err = httpx.HTTPStatusError(
        "429",
        request=httpx.Request("POST", "https://example.com"),
        response=resp,
    )
    resp.raise_for_status.side_effect = err

    with patch("httpx.Client") as ClientCls:
        inst = ClientCls.return_value.__enter__.return_value
        inst.post.return_value = resp
        with patch("time.sleep"):  # do not actually wait
            try:
                client.complete("rate-limit-storm", use_cache=False)
                raise AssertionError("expected RateLimitExceeded")
            except RateLimitExceeded as e:
                assert "gemma-4-31b-it" in str(e)
    print("T-104 RateLimitExceeded OK")


def test_t105_config() -> None:
    cfg = load_config("configs/default.yaml")
    # Assert the CONTRACT, not the current value: default.yaml's model is
    # explicitly pending the T-004 bake-off and is expected to change. Pinning
    # the literal here made a config edit look like a loader regression.
    assert cfg.llm.model in ALLOWED_MODELS
    assert cfg.llm.planner_model in ALLOWED_MODELS
    # Same reasoning as the model above, and it bit for the same reason: this
    # pinned the literal 60 and started failing when max_papers was lowered to
    # 25 on 2026-08-28 for the flagship and ablation runs. The loader is what is
    # under test, not the tuning decision, which travels in default.yaml with
    # its own comment.
    assert cfg.review.max_papers > 0

    try:
        load_config("configs/default.yaml", overrides={"no_such_section": {}})
        raise AssertionError("expected ValidationError for unknown key")
    except ValidationError:
        pass

    # 40 deliberately: the probe used to be 25, which became the file's own
    # value on 2026-08-28 and made this assertion pass without the override
    # doing anything. It must differ from whatever default.yaml says.
    assert cfg.review.max_papers != 40, "pick another probe; this one is now vacuous"
    os.environ["RESEARCHGPT__REVIEW__MAX_PAPERS"] = "40"
    try:
        cfg2 = load_config("configs/default.yaml")
        assert cfg2.review.max_papers == 40
    finally:
        del os.environ["RESEARCHGPT__REVIEW__MAX_PAPERS"]

    try:
        load_config(
            "configs/default.yaml",
            overrides={"llm": {"model": "gpt-4o"}},
        )
        raise AssertionError("expected ValidationError for gpt-4o")
    except ValidationError:
        pass
    print("T-105 OK")


def test_t108_cli() -> None:
    from typer.testing import CliRunner

    from researchgpt.cli import app

    runner = CliRunner()
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0, r.output
    assert "0.1.0" in r.output

    r2 = runner.invoke(app, ["run", "-q", "test"])
    assert r2.exit_code == 0, r2.output
    assert "run_id=" in r2.output
    # Find the run dir from output
    run_dir = None
    for line in r2.output.splitlines():
        if line.startswith("run_dir="):
            run_dir = Path(line.split("=", 1)[1].strip())
    assert run_dir is not None and run_dir.is_dir()
    trace = run_dir / "trace.jsonl"
    events = [json.loads(x) for x in trace.read_text().splitlines() if x.strip()]
    names = [e["event"] for e in events]
    assert "run_start" in names and "run_end" in names
    print("T-108 OK")


def test_sources_enabled_must_be_implemented() -> None:
    """A config may not name a source that has no connector.

    This is the failure that let T-214 go missing: `configs/default.yaml`
    listed `semantic_scholar` in `sources.enabled` for a day while no such
    function existed anywhere in `src/`. Nothing failed, because nothing
    checked - the config was simply wrong and silent about it.
    """
    cfg = load_config("configs/default.yaml")
    assert set(cfg.sources.enabled) <= IMPLEMENTED_SOURCES, cfg.sources.enabled

    try:
        SourcesConfig(enabled=["openalex", "crossref"])
        raise AssertionError("expected ValidationError for unimplemented source")
    except ValidationError as exc:
        assert "crossref" in str(exc)

    print(f"sources guard OK (implemented={sorted(IMPLEMENTED_SOURCES)})")


if __name__ == "__main__":
    test_t107_trace_logger()
    test_t104_extract_json()
    test_t104_allowlist()
    test_t104_cache()
    test_t104_rate_limit()
    test_t105_config()
    test_t108_cli()
    test_sources_enabled_must_be_implemented()
    print("ALL PHASE-1 ACCEPTANCE CHECKS PASSED")


# --------------------------------------------------------------------------
# T-104 — token budgeting. Added 2026-08-28 after T-409 was throttled to a halt.
#
# The adapter paced REQUESTS while the provider limited TOKENS. Groq's free
# tier is 8,000 TPM against 1,000 requests/day, so the run was refused
# constantly while holding 999 unused requests. Worse, `prompt + max_tokens` is
# reserved at admission, so the largest requests exceeded the whole bucket and
# could never succeed at any rate - they burned 5 retries x 60 s and were then
# written as blank insights.
# --------------------------------------------------------------------------


def _llm_cfg(**over):
    from researchgpt.core.models import LLMConfig

    base = dict(model="openai/gpt-oss-120b", requests_per_minute=0,
                tokens_per_minute=8000, max_tokens=2048, cache_dir="data/llm_cache")
    base.update(over)
    return LLMConfig(**base)


def test_estimate_tokens_rounds_up() -> None:
    """Under-estimating costs a 429 storm; over-estimating costs a little
    throughput. The error is priced asymmetrically, so it must never round
    down to zero."""
    from researchgpt.core.llm import estimate_tokens

    assert estimate_tokens("") >= 1
    assert estimate_tokens("a" * 400) >= 100
    assert estimate_tokens("a" * 4000) > estimate_tokens("a" * 400)


def test_request_larger_than_the_whole_budget_fails_before_any_http() -> None:
    """The T-409 bug. This must raise instantly, not retry.

    No network is configured in this test; if the guard did not fire first, the
    call would attempt a real request and fail differently.
    """
    from researchgpt.core.llm import LLMClient, TokenBudgetExceeded

    client = LLMClient(_llm_cfg(tokens_per_minute=8000, max_tokens=4096))
    huge = "word " * 5000  # ~6,250 tokens; + 4,096 max_tokens = over 8,000

    try:
        client.complete(huge, use_cache=False)
        raise AssertionError("expected TokenBudgetExceeded")
    except TokenBudgetExceeded as exc:
        msg = str(exc)
        # The message must name the knobs, or the next person re-lives this.
        assert "can NEVER succeed" in msg
        assert "max_tokens" in msg
        assert "8,000" in msg
    print("T-104 TokenBudgetExceeded OK")


def test_token_guard_accounts_for_max_tokens_not_just_the_prompt() -> None:
    """A prompt that fits alone but not once max_tokens is reserved.

    This is the exact subtlety that made the bug invisible: the prompt looked
    comfortably under the limit.
    """
    from researchgpt.core.llm import LLMClient, TokenBudgetExceeded, estimate_tokens

    prompt = "word " * 1200                      # ~1,500 tokens
    assert estimate_tokens(prompt) < 8000, "prompt alone must fit, or the test is void"

    client = LLMClient(_llm_cfg(tokens_per_minute=8000, max_tokens=7000))
    try:
        client.complete(prompt, use_cache=False)
        raise AssertionError("expected TokenBudgetExceeded once max_tokens is counted")
    except TokenBudgetExceeded:
        pass


def test_token_ledger_paces_within_the_rolling_window() -> None:
    """Requests that fit are admitted without sleeping; the ledger records them."""
    from researchgpt.core.llm import LLMClient

    client = LLMClient(_llm_cfg(tokens_per_minute=8000))
    t0 = time.monotonic()
    for _ in range(3):
        client._throttle_tokens(1000)          # 3,000 of 8,000 - all fit
    assert time.monotonic() - t0 < 1.0, "requests inside the budget must not sleep"
    assert sum(n for _, n in client._token_ledger) == 3000


def test_token_pacing_disabled_when_tokens_per_minute_is_zero() -> None:
    """Escape hatch: a paid tier or a local model should not be paced."""
    from researchgpt.core.llm import LLMClient

    client = LLMClient(_llm_cfg(tokens_per_minute=0))
    t0 = time.monotonic()
    client._throttle_tokens(999_999)
    assert time.monotonic() - t0 < 1.0
    assert client._token_ledger == []


def test_agent_output_budgets_fit_groqs_bucket() -> None:
    """Every agent's worst-case request must fit in 8,000 TPM.

    Sized from measurement, not round numbers: extractor responses were a
    median of 571 tokens and a max of 1,682 over 55 cached calls.
    """
    from researchgpt.agents.extractor import MAX_COMPLETION_TOKENS as EXTRACT_OUT
    from researchgpt.agents.extractor import MAX_PROMPT_CHARS
    from researchgpt.agents.writer import MAX_COMPLETION_TOKENS as WRITE_OUT
    from researchgpt.core.llm import estimate_tokens

    budget = 8000
    worst_extract = estimate_tokens("x" * MAX_PROMPT_CHARS) + EXTRACT_OUT
    assert worst_extract <= budget, (
        f"worst-case extraction is {worst_extract} tokens against a {budget} "
        f"budget - it can never be served. Lower MAX_PROMPT_CHARS or "
        f"MAX_COMPLETION_TOKENS."
    )
    # The largest extractor response ever observed was 1,682 tokens.
    assert EXTRACT_OUT >= 1682, "output budget is below an observed real response"
    assert WRITE_OUT > EXTRACT_OUT, "sections are prose and need more room than JSON"


def test_rate_limit_reason_is_captured_from_the_429_body() -> None:
    """WHICH limit was hit must reach the trace.

    🔴 Diagnosing this from headers alone cost a day on 2026-08-28. The
    x-ratelimit-* headers report only the per-MINUTE bucket and read a healthy
    8000/8000 while the run was being refused on the DAILY budget. The daily
    limit appears nowhere except the body of a 429.
    """
    from researchgpt.core.llm import rate_limit_reason

    resp = MagicMock()
    resp.json.return_value = {
        "error": {
            "message": (
                "Rate limit reached for model `openai/gpt-oss-120b` in "
                "organization `org_x` service tier `on_demand` on tokens per "
                "day (TPD): Limit 200000, Used 197751, Requested 5520."
            ),
            "type": "tokens",
            "code": "rate_limit_exceeded",
        }
    }
    reason = rate_limit_reason(resp)
    assert "tokens per day" in reason
    assert "200000" in reason

    # A body that is not JSON must not crash the retry path.
    broken = MagicMock()
    broken.json.side_effect = ValueError("not json")
    assert rate_limit_reason(broken) == "(no error body)"


def test_rate_limit_error_message_names_the_limit_that_was_hit() -> None:
    """RateLimitExceeded must carry the provider's own explanation."""
    from researchgpt.core.llm import LLMClient, RateLimitExceeded

    cfg = LLMConfig(model="gemma-4-31b-it", cache_dir=tempfile.mkdtemp(),
                    requests_per_minute=0, tokens_per_minute=0, max_retries=1)
    client = LLMClient(cfg)

    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {}
    resp.json.return_value = {
        "error": {"message": "... on tokens per day (TPD): Limit 200000, Used 199999."}
    }
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=httpx.Request("POST", "https://example.com"), response=resp
    )

    with patch("httpx.Client") as ClientCls:
        ClientCls.return_value.__enter__.return_value.post.return_value = resp
        with patch("time.sleep"):
            try:
                client.complete("storm", use_cache=False)
                raise AssertionError("expected RateLimitExceeded")
            except RateLimitExceeded as exc:
                assert "tokens per day" in str(exc), (
                    "the error must say WHICH limit, or the next person "
                    "re-diagnoses it from headers that cannot show it"
                )
