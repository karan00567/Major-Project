"""T-404 ★ — the Extractor. One paper in, one validated ``PaperInsight`` out.

`SPEC §7.3`. This is the agent that turns papers into the four graded fields
(``methodology`` / ``advantages`` / ``disadvantages`` / ``critique``) plus
datasets, metrics and evidence spans. Two properties matter more than accuracy
here, and both are enforced in code rather than requested in the prompt:

**1. A parse failure must never abort the run.** `SPEC §14.2` and TASKLIST
T-404 are explicit. With ~60 papers per run, a single malformed response would
otherwise destroy a 30-minute pipeline at paper 47. So: at most
:data:`MAX_REPAIRS` repair passes, then a ``PaperInsight`` with ``None`` fields
and an ``extraction_note`` saying what happened. **The paper still exists in
the corpus and can still be cited as existing** — it simply supplies no claims.
``fail_soft = True``.

**2. Never fabricate.** An unresolvable field is ``None``, never a plausible
sentence. T-004 measured why this is a live risk rather than a principle:
``qwen/qwen3.6-27b`` echoed the literal schema placeholder ``"string"`` into
``datasets``/``metrics`` on **2 of 5** papers — output that parses, validates,
and silently injects fabricated content into a hallucination-graded pipeline.
:func:`_strip_placeholders` removes those echoes, and the count is traced.

⚠️ **Fenced JSON is the normal case, not the error case.** Measured 2026-08-25:
Gemma accepts ``responseSchema`` and ignores it, returning markdown-fenced
JSON. ``core.llm.extract_json`` handles the fences; do not "fix" this by asking
harder in the prompt.

⚠️ **Known open item.** T-004 measured the winning model populating only
**4.6 of 8** content fields, and attributed it to the prompt shipping 3
few-shot examples against the ~20 Dagdelen et al. measured as the stabilisation
point (`SESSION_CONTEXT §5.10`). :func:`field_coverage` exists so that number is
tracked on every real run instead of being rediscovered later.
"""

from __future__ import annotations

from string import Template
from typing import Any

from researchgpt.agents.base import Agent
from researchgpt.core.llm import LLMClient, extract_json
from researchgpt.core.models import EvidenceSpan, Paper, PaperInsight
from researchgpt.core.prompts import load, version
from researchgpt.graph.state import ReviewState

MAX_REPAIRS = 2

#: The eight content fields T-004 scores coverage over.
CONTENT_FIELDS = (
    "methodology", "advantages", "disadvantages", "critique",
    "datasets", "metrics", "results", "limitations",
)

#: Literal schema placeholders a model may echo instead of extracting. Dropping
#: these is not cosmetic: they are fabricated content in a pipeline graded on
#: not fabricating. Measured on 2 of 5 papers for one T-004 arm.
_PLACEHOLDERS = {"string", "string | null", "null", "none", "n/a", "na", "...",
                 "example", "text", "value", "<string>"}

_REPAIR_PROMPT = """Your previous response could not be used.

ERROR: $error

YOUR PREVIOUS RESPONSE:
$previous

Return the corrected JSON object and nothing else. Same schema as before.
Remember: a field you cannot support from the text must be null, not invented.
"""


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() in _PLACEHOLDERS:
        return None
    return text


def _strip_placeholders(values: Any) -> tuple[list[str], int]:
    """Clean a list field. Returns (kept, n_placeholder_echoes_removed)."""
    if not isinstance(values, list):
        return [], 0
    kept, echoes = [], 0
    for item in values:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        if text.lower() in _PLACEHOLDERS:
            echoes += 1
            continue
        kept.append(text)
    return kept, echoes


def field_coverage(insight: PaperInsight) -> int:
    """How many of the eight content fields carry real content (T-004's metric)."""
    filled = 0
    for name in CONTENT_FIELDS:
        value = getattr(insight, name, None)
        if isinstance(value, list):
            filled += 1 if value else 0
        elif value:
            filled += 1
    return filled


class Extractor(Agent):
    name = "extractor"
    #: SPEC 14.2 / T-404: one unparseable paper must never abort a 60-paper run.
    fail_soft = True

    def __init__(self, llm: LLMClient, cfg: Any, trace: Any = None) -> None:
        super().__init__(trace=trace)
        self._llm = llm
        self._cfg = cfg

    # -- one paper ---------------------------------------------------------

    def extract_one(self, paper: Paper, text: str) -> tuple[PaperInsight, dict[str, Any]]:
        """Extract from a single paper. Always returns an insight, never raises."""
        prompt = load(
            "extractor_v1",
            title=paper.title or "",
            text_availability=paper.text_availability,
            text=text,
        )
        stats: dict[str, Any] = {"repairs": 0, "placeholder_echoes": 0, "failed": False}
        last_error, raw = None, ""

        for attempt in range(MAX_REPAIRS + 1):
            sent = prompt if attempt == 0 else prompt + "\n\n" + Template(
                _REPAIR_PROMPT
            ).substitute(error=last_error or "", previous=raw[:3000])
            try:
                raw = self._llm.complete(sent)
                payload = extract_json(raw)
                insight, echoes = self._to_insight(paper, payload)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                stats["repairs"] = attempt + 1
                continue
            stats["repairs"] = attempt
            stats["placeholder_echoes"] = echoes
            stats["fields"] = field_coverage(insight)
            return insight, stats

        # Exhausted repairs: an empty-but-honest insight, not a dropped paper.
        stats["failed"] = True
        stats["fields"] = 0
        return (
            PaperInsight(
                paper_id=paper.paper_id,
                extraction_note=(
                    f"extraction failed after {MAX_REPAIRS} repair passes; "
                    f"last error: {last_error}. Paper may be cited as existing but "
                    f"supplies no verified claims (T-505)."
                ),
            ),
            stats,
        )

    def _to_insight(self, paper: Paper, payload: dict) -> tuple[PaperInsight, int]:
        if not isinstance(payload, dict):
            raise ValueError(f"expected a JSON object, got {type(payload).__name__}")

        datasets, e1 = _strip_placeholders(payload.get("datasets"))
        metrics, e2 = _strip_placeholders(payload.get("metrics"))

        spans: list[EvidenceSpan] = []
        for raw_span in payload.get("evidence_spans") or []:
            if not isinstance(raw_span, dict):
                continue
            quote = _clean_str(raw_span.get("quote"))
            if not quote:
                continue
            # Offsets are resolved against the source text by T-501/T-607, which
            # need a real span to highlight. A quote that is not in the text is
            # a fabrication, so it is dropped rather than stored with offset 0.
            spans.append(EvidenceSpan(chunk_id=paper.paper_id, quote=quote,
                                      start_char=0, end_char=len(quote)))

        insight = PaperInsight(
            paper_id=paper.paper_id,
            methodology=_clean_str(payload.get("methodology")),
            advantages=_clean_str(payload.get("advantages")),
            disadvantages=_clean_str(payload.get("disadvantages")),
            critique=_clean_str(payload.get("critique")),
            datasets=datasets,
            metrics=metrics,
            results=_clean_str(payload.get("results")),
            limitations=_clean_str(payload.get("limitations")),
            evidence_spans=spans,
            extraction_note=_clean_str(payload.get("extraction_note")),
        )
        return insight, e1 + e2

    # -- run ---------------------------------------------------------------

    def run(self, state: ReviewState) -> dict[str, Any]:
        papers: list[Paper] = list(state.get("papers") or [])
        if not papers:
            raise ValueError("no papers in state - the Retriever must run first.")

        max_papers = self._cfg.review.max_papers

        # ★ Take the RANKED top-N, never insertion order.
        #
        # `papers` accumulates through an `add` reducer, so the Ranker cannot
        # hand back a reordered list without duplicating the corpus. It
        # publishes the order in artefacts instead, and this is where it is
        # applied. Falling back to insertion order when the key is absent is
        # deliberate but dangerous: insertion order is "whichever query ran
        # first", which is exactly the defect that made the T-212 harness read
        # 0.029 instead of 0.057 on 2026-08-26. So the fallback is traced.
        order = (state.get("artefacts") or {}).get("ranked_paper_ids")
        if order:
            by_id = {p.paper_id: p for p in papers}
            selected = [by_id[i] for i in order if i in by_id][:max_papers]
        else:
            self._emit(
                "unranked_corpus_warning",
                {"papers": len(papers), "taking": min(max_papers, len(papers)),
                 "why": "artefacts['ranked_paper_ids'] absent - the Ranker did not "
                        "run, so this prefix is insertion order, not the top-N."},
                state.get("iteration", 0),
            )
            selected = papers[:max_papers]
        iteration = state.get("iteration", 0)

        insights: list[PaperInsight] = []
        totals = {"repairs": 0, "echoes": 0, "failed": 0, "fields": 0, "no_text": 0}

        for i, paper in enumerate(selected, 1):
            text = (paper.abstract or "").strip()
            if not text:
                totals["no_text"] += 1
                insights.append(PaperInsight(
                    paper_id=paper.paper_id,
                    extraction_note="no abstract or full text available; "
                                    "citable as existing only (T-505).",
                ))
                continue

            insight, stats = self.extract_one(paper, text)
            insights.append(insight)
            totals["repairs"] += stats["repairs"]
            totals["echoes"] += stats["placeholder_echoes"]
            totals["failed"] += int(stats["failed"])
            totals["fields"] += stats["fields"]
            if i % 10 == 0 or i == len(selected):
                self._emit("extract_progress",
                           {"done": i, "of": len(selected)}, iteration)

        scored = [i for i in insights if not i.extraction_note or field_coverage(i)]
        mean_fields = totals["fields"] / max(len(scored), 1)
        self._emit(
            "extract_summary",
            {
                "papers": len(selected), "skipped_no_text": totals["no_text"],
                "failed_after_repairs": totals["failed"],
                "repair_passes": totals["repairs"],
                "placeholder_echoes_removed": totals["echoes"],
                "mean_fields_of_8": round(mean_fields, 2),
                "prompt_version": version("extractor_v1"),
            },
            iteration,
        )
        return {"paper_insights": insights}


__all__ = ["Extractor", "field_coverage", "CONTENT_FIELDS"]
