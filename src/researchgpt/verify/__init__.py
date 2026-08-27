"""Phase 3 — the fine-tuned claim verifier.

This package owns the *training-side* of the verifier: turning SciFact into
`(claim, evidence_sentence) -> SUPPORT | CONTRADICT | NEI` pairs (T-301),
exporting the trained checkpoint to ONNX int8 (T-304), scoring it against the
stock checkpoint (T-305) and measuring CPU throughput (T-306).

Inference inside the agent graph is `agents/verifier.py` (Phase 5, T-501/502);
it consumes the artefacts produced here.
"""

from researchgpt.verify.labels import ID2LABEL, LABEL2ID, LABELS

__all__ = ["LABELS", "LABEL2ID", "ID2LABEL"]
