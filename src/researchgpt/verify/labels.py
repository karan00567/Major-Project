"""The three-way verdict vocabulary, in one place.

Everything downstream keys off this ordering: the training notebook's
classification head, the ONNX export, the softmax column indices in
``agents/verifier.py`` and the T-305 report all assume ``LABELS`` order.
Changing it silently invalidates a trained checkpoint, so it is isolated here
rather than being re-declared per module.

⚠️ SciFact spells the third class ``NEI``, not ``NOT_ENOUGH_INFO``. The SPEC §8
``Verdict`` vocabulary is a different, wider thing (it has ``PARTIAL``, which no
classifier predicts — T-503 derives it from ``support_score``). Do not conflate
the two: this is the *model's* label set, not the pipeline's verdict set.
"""

from __future__ import annotations

#: Canonical order. The trained head's logit columns follow this exactly.
LABELS: tuple[str, ...] = ("SUPPORT", "CONTRADICT", "NEI")

LABEL2ID: dict[str, int] = {label: i for i, label in enumerate(LABELS)}
ID2LABEL: dict[int, str] = {i: label for i, label in enumerate(LABELS)}

#: Maps the *stock* ``cross-encoder/nli-deberta-v3-*`` head onto ours, for the
#: T-305 stock-vs-fine-tuned comparison. Those checkpoints are trained on
#: SNLI/MNLI and emit lowercase NLI names in a different order, so a naive
#: argmax comparison would score the stock model at near chance for the wrong
#: reason. Verified against the checkpoint's own ``config.id2label`` at load
#: time by ``evaluate.py`` — this table is the expectation, not a guess.
NLI_TO_VERDICT: dict[str, str] = {
    "entailment": "SUPPORT",
    "contradiction": "CONTRADICT",
    "neutral": "NEI",
}

__all__ = ["LABELS", "LABEL2ID", "ID2LABEL", "NLI_TO_VERDICT"]
