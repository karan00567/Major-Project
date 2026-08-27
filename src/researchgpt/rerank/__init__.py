"""Phase 3C — the fine-tuned cross-encoder reranker (the second trained model).

Training-side only: building triples from SciReviewGen (T-330/T-331), exporting
to ONNX (T-333), and the stock-vs-tuned adoption gate (T-334/T-335). Inference
lives in ``tools/reranker.py`` (T-210) and is unchanged by any of this — the
tuned model is a weight swap, which is why `TRAINING_SPEC §2.1` calls it zero
new inference cost and off the M1 critical path.
"""
