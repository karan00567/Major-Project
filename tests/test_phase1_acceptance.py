"""Phase 1 acceptance checks from handoffs/phase1.md."""

from __future__ import annotations

import json
import os
import tempfile
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
from researchgpt.core.models import ALLOWED_MODELS, LLMConfig


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
    assert cfg.review.max_papers == 60

    try:
        load_config("configs/default.yaml", overrides={"no_such_section": {}})
        raise AssertionError("expected ValidationError for unknown key")
    except ValidationError:
        pass

    os.environ["RESEARCHGPT__REVIEW__MAX_PAPERS"] = "25"
    try:
        cfg2 = load_config("configs/default.yaml")
        assert cfg2.review.max_papers == 25
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


if __name__ == "__main__":
    test_t107_trace_logger()
    test_t104_extract_json()
    test_t104_allowlist()
    test_t104_cache()
    test_t104_rate_limit()
    test_t105_config()
    test_t108_cli()
    print("ALL PHASE-1 ACCEPTANCE CHECKS PASSED")
