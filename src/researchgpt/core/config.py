"""YAML config loader → validated RunConfig, with env-var overrides.

Schema validation lives in ``core.models.RunConfig`` (extra=forbid + allowlist).
This module only loads YAML, merges overrides, and constructs the model.
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

import yaml
from dotenv import load_dotenv

from researchgpt.core.models import RunConfig

_ENV_PREFIX = "RESEARCHGPT__"


def load_config(
    path: str | pathlib.Path = "configs/default.yaml",
    overrides: dict | None = None,
) -> RunConfig:
    load_dotenv()
    cfg_path = pathlib.Path(path)
    with cfg_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping, got {type(data).__name__}")

    merged = _deep_merge(data, _env_overrides())
    if overrides:
        merged = _deep_merge(merged, overrides)
    return RunConfig.model_validate(merged)


def _env_overrides() -> dict[str, Any]:
    """Parse RESEARCHGPT__SECTION__KEY env vars into a nested dict."""
    result: dict[str, Any] = {}
    for key, raw in os.environ.items():
        upper = key.upper()
        if not upper.startswith(_ENV_PREFIX):
            continue
        parts = upper[len(_ENV_PREFIX) :].split("__")
        if len(parts) < 2:
            continue
        # Map SECTION / KEY back to lowercase YAML field names.
        sections = [p.lower() for p in parts]
        value = yaml.safe_load(raw)
        cursor = result
        for section in sections[:-1]:
            nxt = cursor.setdefault(section, {})
            if not isinstance(nxt, dict):
                nxt = {}
                cursor[section] = nxt
            cursor = nxt
        cursor[sections[-1]] = value
    return result


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


__all__ = ["load_config"]
