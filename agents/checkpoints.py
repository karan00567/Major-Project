from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass
from typing import Any

CHECKPOINT_DIR = pathlib.Path(
    os.getenv("RESEARCHGPT_CHECKPOINT_DIR", "data")
)


@dataclass(frozen=True)
class Spec:

    filename: str


    base: str

    task: str
    role: str


    labels: tuple[str, ...] = ()


SPECS: dict[str, Spec] = {
    "ranker": Spec(
        filename="model-1.pth",
        base=os.getenv("RESEARCHGPT_BASE_1", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        task="pair-score",
        role="scores a (query, paper) pair for relevance",
    ),
    "extractor": Spec(
        filename="model-2.pth",
        base=os.getenv("RESEARCHGPT_BASE_2", "facebook/bart-base"),
        task="seq2seq",
        role="summarises a paper",
    ),
    "verifier": Spec(
        filename="model-3.pth",
        base=os.getenv("RESEARCHGPT_BASE_3", "microsoft/deberta-v3-small"),
        task="nli",
        role="scores a claim against evidence",
        labels=("SUPPORT", "CONTRADICT", "NEI"),
    ),
}


class CheckpointError(RuntimeError):
    pass


def checkpoint_path(name: str) -> pathlib.Path:
    return CHECKPOINT_DIR / SPECS[name].filename


def _load_state(path: pathlib.Path) -> dict[str, Any]:
    import torch

    if not path.is_file():
        raise CheckpointError(
            f"{path} not found. Put the checkpoint there, or set "
            f"RESEARCHGPT_CHECKPOINT_DIR to the directory that holds it."
        )


    try:
        state = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        state = torch.load(path, map_location="cpu", weights_only=False)


    for key in ("state_dict", "model_state_dict", "module"):
        if isinstance(state, dict) and key in state and isinstance(state[key], dict):
            state = state[key]
            break
    if not isinstance(state, dict):
        raise CheckpointError(f"{path} did not contain a state dict.")


    cleaned = {}
    for k, v in state.items():
        for prefix in ("module.", "model.", "_orig_mod."):
            if k.startswith(prefix):
                k = k[len(prefix):]
        cleaned[k] = v
    return cleaned


_LOADED: dict[str, tuple[Any, Any]] = {}


def load(name: str, *, strict: bool = False) -> tuple[Any, Any]:
    from transformers import AutoConfig, AutoTokenizer

    if name in _LOADED:
        return _LOADED[name]

    spec = SPECS[name]
    path = checkpoint_path(name)
    state = _load_state(path)

    tokenizer = AutoTokenizer.from_pretrained(spec.base)

    if spec.task == "seq2seq":
        from transformers import AutoModelForSeq2SeqLM

        model = AutoModelForSeq2SeqLM.from_pretrained(spec.base)
    else:
        from transformers import AutoModelForSequenceClassification

        n_labels = len(spec.labels) if spec.labels else 1
        config = AutoConfig.from_pretrained(spec.base, num_labels=n_labels)
        model = AutoModelForSequenceClassification.from_pretrained(
            spec.base, config=config, ignore_mismatched_sizes=True
        )

    result = model.load_state_dict(state, strict=strict)
    missing = list(getattr(result, "missing_keys", []))
    unexpected = list(getattr(result, "unexpected_keys", []))
    if missing or unexpected:
        print(
            f"  [warn] {path.name} did not fit {spec.base} cleanly: "
            f"{len(missing)} missing, {len(unexpected)} unexpected keys.\n"
            f"         First missing: {missing[:3]}\n"
            f"         First unexpected: {unexpected[:3]}\n"
            f"         If these are not just the classifier head, the base is "
            f"wrong — set RESEARCHGPT_BASE_* and reload."
        )
    model.eval()
    _LOADED[name] = (model, tokenizer)
    return model, tokenizer


def available() -> dict[str, bool]:
    return {name: checkpoint_path(name).is_file() for name in SPECS}


__all__ = ["SPECS", "Spec", "CheckpointError", "load", "available",
           "checkpoint_path", "CHECKPOINT_DIR"]
