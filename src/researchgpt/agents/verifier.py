"""T-501..T-505 — the Verifier. The graded centrepiece.

`SPEC §7.4`, `PROJECT_PLAN §4.2`. Drafted prose in, *verified* claims out, with
everything it could not ground **dropped and counted**.

This is the component the whole architecture exists to justify. `PROJECT_PLAN
§9.6` names the trap it has to avoid: groundedness measured by the system that
enforces groundedness proves only that the filter ran. So the numbers this
agent produces are cross-checked three ways (T-705b) — SciFact held-out
(T-305), SciReviewGen human citations (T-325), and a 50-claim human spot-check
in our own domain (T-705).

**Why the decomposition is rule-based and not an LLM call.** FActScore
decomposes with a model. We do not, for three reasons that outrank fidelity to
that paper: the free-tier token budget is the project's hardest constraint
(TASKLIST §0.1, and T-409 exhausted a 200,000-token daily quota four times over
in one afternoon); a deterministic splitter is auditable, and an examiner can
re-derive our claim list by hand; and an LLM in this position can *invent* a
claim the draft never made, which in a hallucination-graded project is the
worst possible place to add a generative step. The cost is that a compound
sentence counts as one claim rather than several — recorded honestly in
:data:`DECOMPOSITION_NOTE` and in the Limitations chapter (T-806), not hidden.

**Precision over recall on SUPPORTED, deliberately.** CliVER measured a 21%
false-Support rate (`SESSION_CONTEXT §5.10`). Over-predicting "supported" is
the dangerous direction here: a false SUPPORTED ships a hallucination with a
citation attached, while a false UNSUPPORTED merely drops a true sentence and
is visible in the dropped-claims panel. The threshold is therefore applied to
the *softmax probability*, not to the argmax alone.

⚠️ **T-505, the abstract-only rule, is implemented as a CAP rather than a ban,
and that is a judgement call worth stating.** The rule says abstract-only
papers "may be cited as existing but may not supply verified claims". Read as
a ban it would empty the corpus: the M1 run was **100% abstract-only**, because
OpenAlex gives abstracts and most venues do not give us PDFs. Read as a cap it
does the work the evidence actually supports — Li et al. measured
abstract-conditioned faithfulness at **0.745 against 0.94–0.96** with full
context, which is a degradation, not a disqualification. So a claim whose only
support is abstract-only is capped at ``PARTIAL`` and can never reach
``SUPPORTED``. The cap is recorded per claim so the report can count how many
claims it bit.
"""

from __future__ import annotations

import re
from typing import Any

from researchgpt.agents.base import Agent
from researchgpt.core.models import Chunk, Claim, EvidenceSpan, Paper
from researchgpt.graph.state import ReviewState
from researchgpt.verify.labels import LABELS

_CITE = re.compile(r"\[(\d+)\]")

#: Sentence boundary: a terminator, then whitespace, then a capital/quote/digit.
#:
#: The abbreviation lookbehinds must sit AFTER ``(?<=[.!?])`` and must include
#: the dot themselves. Written before it they are evaluated at the position
#: following the terminator, so ``(?<!\bet al)`` looks back at "t al." and never
#: matches - the guard silently does nothing and "Wadden et al. built SciFact"
#: splits in two. Verified by
#: ``test_sentence_split_survives_academic_abbreviations``.
#:
#: Splitting on an abbreviation shatters one claim into fragments that the NLI
#: model then scores as unsupported, inflating the drop count for a punctuation
#: reason and understating groundedness.
_SENTENCE_END = re.compile(
    r"(?<=[.!?])"
    r"(?<!\bet al\.)(?<!\bFig\.)(?<!\bEq\.)(?<!\bNo\.)(?<!\bcf\.)(?<!\bvs\.)"
    r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bal\.)(?<!\b[A-Z]\.)"
    r"\s+(?=[\"'\(\[]?[A-Z0-9])"
)

#: A fragment shorter than this is a heading, a list bullet or a stray token,
#: not a claim. Verifying it wastes a 39 ms inference and pollutes the
#: groundedness denominator.
MIN_CLAIM_CHARS = 40

#: `PROJECT_PLAN §4.2`. Softmax probability, not logit. Biased to precision per
#: the module docstring; T-503 fixes it here rather than in the config so the
#: graded threshold cannot drift between runs without a code review.
SUPPORT_THRESHOLD = 0.7

#: Evidence passages scored per claim. Each is a ~39 ms CPU inference (T-306),
#: so 6 candidates x ~120 claims is roughly 30 s — affordable. The claim is
#: scored against its BEST evidence, so more candidates can only help recall;
#: the cap is a latency budget, not a quality choice.
MAX_EVIDENCE_PER_CLAIM = 6

DECOMPOSITION_NOTE = (
    "Claims are sentence-level. A compound sentence asserting two facts is "
    "verified as one claim against its strongest evidence, so a sentence that "
    "is half-supported can pass. Sub-sentence decomposition (FActScore-style) "
    "needs a generative pass and was rejected on token budget and on the risk "
    "of inventing claims the draft never made."
)


# --------------------------------------------------------------------------
# T-501 — decomposition
# --------------------------------------------------------------------------


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, tolerating academic abbreviations.

    Markdown structure is stripped first: headings, table rows and list bullets
    are not prose and must not become claims.
    """
    out: list[str] = []
    for block in text.split("\n"):
        line = block.strip()
        if not line or line.startswith(("#", ">", "|", "---")):
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        for piece in _SENTENCE_END.split(line):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out


def decompose(
    draft_sections: dict[str, str],
    reference_order: list[str] | None = None,
) -> list[dict[str, Any]]:
    """T-501. Drafted text -> atomic claims, each with a source pointer.

    Only sentences carrying at least one ``[n]`` marker become claims. An
    uncited sentence is either a transition ("This section reviews...") or the
    uncited-prose failure the Writer already rejects wholesale
    (``MIN_CITED_SECTION_CHARS``), so verifying it would measure the Writer's
    connective tissue rather than its factual content.

    ``reference_order`` maps a marker to a ``paper_id``. The Writer renumbers
    every section into that global order before stitching, so ``[3]`` means the
    same paper in every section.
    """
    refs = reference_order or []
    claims: list[dict[str, Any]] = []

    for heading, body in (draft_sections or {}).items():
        for index, sentence in enumerate(split_sentences(body)):
            markers = [int(m) for m in _CITE.findall(sentence)]
            if not markers:
                continue
            if len(sentence) < MIN_CLAIM_CHARS:
                continue
            paper_ids, unresolved = [], []
            for marker in dict.fromkeys(markers):  # ordered, deduplicated
                if 1 <= marker <= len(refs):
                    paper_ids.append(refs[marker - 1])
                else:
                    unresolved.append(marker)
            if not paper_ids:
                # Every marker dangling means the citation cannot be checked at
                # all. That is a Writer defect, surfaced rather than verified.
                continue
            claims.append(
                {
                    "claim_id": f"c{len(claims) + 1:04d}",
                    "text": _CITE.sub("", sentence).strip(),
                    "paper_ids": paper_ids,
                    "section": heading,
                    "sentence_index": index,
                    "markers": markers,
                    "unresolved_markers": unresolved,
                }
            )
    return claims


# --------------------------------------------------------------------------
# T-502 — the ONNX runtime wrapper
# --------------------------------------------------------------------------


class VerifierModel:
    """``(claim, evidence) -> softmax`` over ``LABELS``, on CPU.

    ⚠️ **Pair order is (evidence, claim)** — premise then hypothesis, matching
    ``verify.evaluate.encode_pair``. Reversing them trains and scores a subtly
    different task and costs several F1 points with no visible error, so the
    order is asserted by a test rather than left to memory.

    ⚠️ **Batch size defaults to 1 because that is what T-306 measured as
    fastest**, which is counter-intuitive enough to state: 25.4 claims/s at
    batch 1 against 7.7 at batch 32 on this CPU. Batching a quantized model on
    a small-core machine loses to per-batch overhead.
    """

    def __init__(
        self,
        model_dir: str,
        tokenizer: str | None = None,
        *,
        max_length: int = 512,
        batch_size: int = 1,
    ) -> None:
        import pathlib

        import onnxruntime as ort
        from transformers import AutoTokenizer

        path = pathlib.Path(model_dir)
        if path.is_dir():
            onnx_file = next(path.glob("*quantized*.onnx"), None) or next(
                path.glob("*.onnx"), None
            )
            if onnx_file is None:
                raise FileNotFoundError(f"No .onnx file in {path}")
        else:
            onnx_file = path
        if not onnx_file.exists():
            raise FileNotFoundError(
                f"Verifier model {onnx_file} not found. Export it with "
                f"`python -m researchgpt.verify.export_onnx --checkpoint <dir>` "
                f"(T-304)."
            )

        self.session = ort.InferenceSession(
            str(onnx_file), providers=["CPUExecutionProvider"]
        )
        self.input_names = {i.name for i in self.session.get_inputs()}
        # The tokenizer travels with the exported model; falling back to a Hub
        # name would silently score with a different vocabulary.
        tok_src = str(path if path.is_dir() else path.parent)
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(tok_src)
        except Exception:
            if not tokenizer:
                raise
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer)
        self.max_length = max_length
        self.batch_size = batch_size

    def score(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        """``[(evidence, claim), ...]`` -> ``[{label: probability}, ...]``."""
        import numpy as np

        if not pairs:
            return []
        out: list[dict[str, float]] = []
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start : start + self.batch_size]
            enc = self.tokenizer(
                [evidence for evidence, _ in batch],
                [claim for _, claim in batch],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="np",
            )
            feeds = {
                k: v.astype(np.int64) for k, v in enc.items() if k in self.input_names
            }
            logits = self.session.run(None, feeds)[0]
            # Subtract the row max before exp. Raw logits reach +-15 here and a
            # plain exp overflows to inf, which becomes nan after the division
            # and then silently scores every claim as UNSUPPORTED.
            shifted = logits - logits.max(axis=-1, keepdims=True)
            exp = np.exp(shifted)
            probs = exp / exp.sum(axis=-1, keepdims=True)
            out.extend(
                {label: float(row[i]) for i, label in enumerate(LABELS)} for row in probs
            )
        return out


# --------------------------------------------------------------------------
# T-503 / T-505 — verdicts
# --------------------------------------------------------------------------


def verdict_for(
    probs: dict[str, float], *, abstract_only_support: bool = False
) -> tuple[str, float, str | None]:
    """``PROJECT_PLAN §4.2`` mapping. Returns ``(verdict, score, cap_reason)``.

    ``support_score`` is the SUPPORT probability in every branch, so the number
    means one thing throughout the report rather than "confidence in whatever
    the model happened to pick".
    """
    support = probs.get("SUPPORT", 0.0)
    top = max(probs, key=lambda k: probs[k])

    if top == "CONTRADICT":
        return "CONTRADICTED", support, None
    if top == "NEI":
        return "UNSUPPORTED", support, None

    # top == SUPPORT
    if support < SUPPORT_THRESHOLD:
        return "PARTIAL", support, None
    if abstract_only_support:
        # T-505. Li et al.: abstract-conditioned faithfulness 0.745 vs
        # 0.94-0.96 with full text. Degradation, not disqualification - so the
        # claim is capped, not dropped, and the cap is counted.
        return "PARTIAL", support, "abstract_only_evidence"
    return "SUPPORTED", support, None


# --------------------------------------------------------------------------
# T-504 — the agent
# --------------------------------------------------------------------------


class Verifier(Agent):
    """Verifies the draft's claims and drops what it cannot ground."""

    name = "verifier"
    #: NOT fail-soft, deliberately. The Extractor may skip a paper because the
    #: survey survives losing one; a run whose verification step silently did
    #: nothing would publish unverified prose while every counter read clean,
    #: which is precisely the failure this project claims to prevent.
    fail_soft = False

    def __init__(self, model: VerifierModel, cfg: Any, trace: Any = None) -> None:
        super().__init__(trace=trace)
        self._model = model
        self._cfg = cfg

    # -- evidence ----------------------------------------------------------

    @staticmethod
    def _evidence_for(
        paper_ids: list[str],
        chunks_by_paper: dict[str, list[Chunk]],
        papers: dict[str, Paper],
    ) -> list[tuple[str, str]]:
        """Candidate ``(text, chunk_id)`` passages from the cited papers only.

        Evidence is never drawn from a paper the sentence did not cite. Scoring
        a claim against the whole corpus would let an unrelated paper rescue a
        miscited sentence, which is exactly the error mode ALCE describes.
        """
        out: list[tuple[str, str]] = []
        for paper_id in paper_ids:
            for chunk in chunks_by_paper.get(paper_id, []):
                if chunk.text and chunk.text.strip():
                    out.append((chunk.text, chunk.chunk_id))
            if not chunks_by_paper.get(paper_id):
                paper = papers.get(paper_id)
                if paper and paper.abstract:
                    out.append((paper.abstract, f"{paper_id}:abstract"))
        return out[:MAX_EVIDENCE_PER_CLAIM]

    def run(self, state: ReviewState) -> dict[str, Any]:
        iteration = state.get("iteration", 0)
        sections = state.get("draft_sections") or {}
        reference_order = (state.get("artefacts") or {}).get("reference_order") or []
        papers = {p.paper_id: p for p in state.get("papers") or []}

        chunks_by_paper: dict[str, list[Chunk]] = {}
        for chunk in state.get("chunks") or []:
            chunks_by_paper.setdefault(chunk.paper_id, []).append(chunk)

        raw_claims = decompose(sections, reference_order)
        self._emit(
            "claims_decomposed",
            {
                "claims": len(raw_claims),
                "sections": len(sections),
                "note": DECOMPOSITION_NOTE,
            },
            iteration,
        )

        verified: list[Claim] = []
        unsupported: list[Claim] = []
        contradictions: list[tuple[str, str]] = []
        capped = 0

        for raw in raw_claims:
            candidates = self._evidence_for(raw["paper_ids"], chunks_by_paper, papers)
            if not candidates:
                # Cited a paper we hold no text for. Not verifiable, so not
                # verified - recorded rather than quietly passed.
                claim = Claim(
                    claim_id=raw["claim_id"], text=raw["text"],
                    paper_ids=raw["paper_ids"], verdict="UNSUPPORTED",
                    support_score=0.0, evidence=[],
                )
                unsupported.append(claim)
                self._emit(
                    "claim_dropped",
                    {"claim_id": claim.claim_id, "verdict": "UNSUPPORTED",
                     "support_score": 0.0, "why": "no evidence text held for the "
                     "cited paper(s)", "section": raw["section"],
                     "text": raw["text"][:200]},
                    iteration,
                )
                continue

            scored = self._model.score([(text, raw["text"]) for text, _ in candidates])
            best_i = max(range(len(scored)), key=lambda i: scored[i]["SUPPORT"])
            probs = scored[best_i]
            best_text, best_chunk_id = candidates[best_i]

            # T-505: does ANY cited paper offer full text? The cap applies only
            # when the support rests entirely on abstracts.
            has_full = any(
                (papers.get(pid) and papers[pid].text_availability == "full")
                for pid in raw["paper_ids"]
            )
            verdict, score, cap = verdict_for(probs, abstract_only_support=not has_full)
            if cap:
                capped += 1

            claim = Claim(
                claim_id=raw["claim_id"],
                text=raw["text"],
                paper_ids=raw["paper_ids"],
                verdict=verdict,
                support_score=score,
                evidence=[
                    EvidenceSpan(
                        chunk_id=best_chunk_id,
                        quote=best_text[:600],
                        start_char=0,
                        end_char=min(len(best_text), 600),
                    )
                ],
            )

            if verdict in ("SUPPORTED", "PARTIAL"):
                verified.append(claim)
            else:
                unsupported.append(claim)
                self._emit(
                    "claim_dropped",
                    {"claim_id": claim.claim_id, "verdict": verdict,
                     "support_score": round(score, 4), "section": raw["section"],
                     "paper_ids": raw["paper_ids"], "text": raw["text"][:200],
                     "evidence_chunk": best_chunk_id},
                    iteration,
                )
            if verdict == "CONTRADICTED":
                for paper_id in raw["paper_ids"]:
                    contradictions.append((claim.claim_id, paper_id))

        total = len(verified) + len(unsupported)
        grounding = len(verified) / total if total else 0.0
        supported = sum(1 for c in verified if c.verdict == "SUPPORTED")

        self._emit(
            "verification_summary",
            {
                "claims": total,
                "supported": supported,
                "partial": len(verified) - supported,
                "dropped": len(unsupported),
                "contradicted": sum(
                    1 for c in unsupported if c.verdict == "CONTRADICTED"
                ),
                "abstract_only_capped": capped,
                "grounding_score": round(grounding, 4),
                "support_threshold": SUPPORT_THRESHOLD,
            },
            iteration,
        )

        return {
            "verified_claims": verified,
            "unsupported_claims": unsupported,
            "contradiction_pairs": contradictions,
            "grounding_score": grounding,
        }


__all__ = [
    "Verifier",
    "VerifierModel",
    "decompose",
    "split_sentences",
    "verdict_for",
    "SUPPORT_THRESHOLD",
    "MIN_CLAIM_CHARS",
    "MAX_EVIDENCE_PER_CLAIM",
    "DECOMPOSITION_NOTE",
]
