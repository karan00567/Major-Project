"""T-406 — the Writer. Verified insights in, cited markdown out.

`SPEC §7.6`. One section per theme, then a stitched review.

★ **Evidence-first, and this is the one rule that must not bend.** ALCE
measured post-hoc citation attachment costing **47% of citation recall**
(`SESSION_CONTEXT §5.10`): a model that writes prose and then has citations
bolted on cites the wrong papers about half the time. So the Writer is handed
a numbered evidence block and writes ``[n]`` markers *with* the sentence. It
never sees a paper it is not allowed to cite.

**Citation integrity is enforced after generation, not trusted.** The model
will occasionally emit ``[9]`` for a theme with six sources.
:meth:`Writer._resolve_citations` drops every marker that does not resolve and
counts it, because an unresolvable ``[n]`` in a survey about citation accuracy
is the most embarrassing possible defect. The count goes to the trace and, via
T-701, into the report's citation-accuracy figure.

**Themes are derived, not generated.** Grouping comes from the sub-question
facets the Planner already produced. A second LLM clustering pass would cost
requests against a hard free-tier quota and add a failure mode for something
the plan already encodes.

⚠️ **The abstract-only rule (T-505) is applied at prompt level here and
enforced properly by the Verifier in Phase 5.** Papers whose
``text_availability`` is not ``full`` are marked in the evidence block so the
model is told it may cite them as existing but not as the sole support for a
specific technical claim. Li et al. measured abstract-conditioned faithfulness
at 0.745 against 0.94–0.96 with full context.
"""

from __future__ import annotations

import re
from typing import Any

from researchgpt.agents.base import Agent
from researchgpt.core.llm import LLMClient
from researchgpt.core.models import Paper, PaperInsight
from researchgpt.core.prompts import load, version
from researchgpt.graph.state import ReviewState

_CITE = re.compile(r"\[(\d+)\]")

#: Facet -> section heading. Order is the order of the review.
THEME_ORDER: tuple[tuple[str, str], ...] = (
    ("method", "Methods and Architectures"),
    ("application", "Applications"),
    ("evaluation", "Evaluation and Benchmarks"),
    ("limitation", "Limitations and Open Problems"),
)

#: Papers offered to the model per section. Beyond this the evidence block
#: stops fitting usefully in one prompt and citation precision degrades.
MAX_EVIDENCE_PER_THEME = 14

#: A section this long with no citation at all is unverifiable prose, not a
#: literature review.
#:
#: 🔴 **Observed on the first M1 run**: "Methods and Architectures" came back as
#: **6,751 characters with zero `[n]` markers** - the model wrote a numbered
#: book chapter ("3.1 Methodological Trends", "3.1.1 CTDE versus...") and
#: dropped the citation instruction entirely while doing it. Nothing caught it,
#: because zero markers means zero DROPPED markers, so every integrity counter
#: read clean.
#:
#: Uncited prose is the exact failure this system exists to prevent, so a
#: section that produces none is retried once with an explicit correction and
#: then rejected. Rejecting is consistent with the rest of the architecture:
#: the Verifier drops unsupported claims, so the Writer must not emit
#: unsupported sections.
MIN_CITED_SECTION_CHARS = 400

_UNCITED_RETRY = """Your previous section contained NO [n] citations at all.

Every factual sentence must carry at least one [n] marker pointing at the
numbered EVIDENCE above. Do not write a numbered chapter outline; write cited
prose. If you cannot support a sentence from the evidence, delete the sentence.

Rewrite the section now, with citations."""


class Writer(Agent):
    name = "writer"
    #: A failed section costs one section, not the run. The stitched review is
    #: still produced from whatever sections succeeded.
    fail_soft = True

    def __init__(self, llm: LLMClient, cfg: Any, trace: Any = None) -> None:
        super().__init__(trace=trace)
        self._llm = llm
        self._cfg = cfg

    # -- evidence ----------------------------------------------------------

    @staticmethod
    def _evidence_block(
        papers: list[Paper], insights: dict[str, PaperInsight]
    ) -> tuple[str, list[Paper]]:
        """Numbered evidence. The numbers ARE the citation keys for this section."""
        lines, cited = [], []
        for n, paper in enumerate(papers, 1):
            insight = insights.get(paper.paper_id)
            bits = [f"[{n}] {paper.title or 'Untitled'}"]
            if paper.year:
                bits.append(f"({paper.year})")
            if paper.text_availability != "full":
                bits.append("[ABSTRACT ONLY - may be cited as existing, but not as "
                            "the sole support for a specific technical claim]")
            body = []
            if insight:
                for field in ("methodology", "results", "advantages",
                              "disadvantages", "limitations"):
                    value = getattr(insight, field, None)
                    if value:
                        body.append(f"  {field}: {value}")
                if insight.datasets:
                    body.append(f"  datasets: {', '.join(insight.datasets[:6])}")
                if insight.metrics:
                    body.append(f"  metrics: {', '.join(insight.metrics[:6])}")
            if not body:
                body.append("  (no extracted content; cite as existing only)")
            lines.append(" ".join(bits) + "\n" + "\n".join(body))
            cited.append(paper)
        return "\n\n".join(lines), cited

    @staticmethod
    def _resolve_citations(text: str, n_sources: int) -> tuple[str, int, set[int]]:
        """Drop markers that point at nothing. Returns (text, n_dropped, used)."""
        dropped, used = 0, set()

        def repl(match: re.Match) -> str:
            nonlocal dropped
            index = int(match.group(1))
            if 1 <= index <= n_sources:
                used.add(index)
                return match.group(0)
            dropped += 1
            return ""

        cleaned = _CITE.sub(repl, text)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r" +([.,;:])", r"\1", cleaned)
        return cleaned, dropped, used

    # -- run ---------------------------------------------------------------

    def run(self, state: ReviewState) -> dict[str, Any]:
        papers: list[Paper] = list(state.get("papers") or [])
        insights = {i.paper_id: i for i in state.get("paper_insights") or []}
        if not papers:
            raise ValueError("no papers to write from.")
        iteration = state.get("iteration", 0)

        # Restrict to the corpus the Extractor actually read, in ranked order.
        order = (state.get("artefacts") or {}).get("ranked_paper_ids")
        if order:
            by_id = {p.paper_id: p for p in papers}
            papers = [by_id[i] for i in order if i in by_id]
        papers = [p for p in papers if p.paper_id in insights] or papers
        papers = papers[: self._cfg.review.max_papers]

        # Facet -> the papers that answered its sub-questions. Without a
        # per-paper facet label, every paper is eligible for every theme and
        # the reranked order decides which ones a section actually gets.
        facets = {sq.facet for sq in state.get("sub_questions") or []}
        themes = [(f, title) for f, title in THEME_ORDER if f in facets] or [
            ("method", "Findings")
        ]

        sections: dict[str, str] = {}
        theme_meta: list[dict[str, Any]] = []
        global_sources: list[Paper] = []

        for facet, heading in themes:
            subset = papers[:MAX_EVIDENCE_PER_THEME]
            if not subset:
                continue
            evidence, cited = self._evidence_block(subset, insights)
            prompt = load("writer_v1", theme=f"{heading} - {facet}", evidence=evidence)
            try:
                raw = self._llm.complete(prompt)
            except Exception as exc:
                self._emit("section_failed",
                           {"theme": heading, "error": f"{type(exc).__name__}: {exc}"},
                           iteration)
                continue

            text, dropped, used = self._resolve_citations(raw.strip(), len(cited))

            # Retry once if the model wrote prose and forgot to cite anything.
            if not used and len(text) >= MIN_CITED_SECTION_CHARS:
                self._emit("section_uncited_retry",
                           {"theme": heading, "chars": len(text)}, iteration)
                try:
                    raw = self._llm.complete(prompt + "\n\n" + _UNCITED_RETRY)
                    text, dropped, used = self._resolve_citations(
                        raw.strip(), len(cited))
                except Exception as exc:
                    self._emit("section_failed",
                               {"theme": heading,
                                "error": f"retry: {type(exc).__name__}: {exc}"},
                               iteration)
                    continue

            if not used and len(text) >= MIN_CITED_SECTION_CHARS:
                # Still uncited after an explicit correction. Drop it: the
                # Verifier drops unsupported claims, so the Writer must not
                # emit unsupported sections.
                self._emit("section_rejected_uncited",
                           {"theme": heading, "chars": len(text),
                            "why": "no [n] citations after a retry; unverifiable "
                                   "prose is worse than a missing section."},
                           iteration)
                continue
            # Renumber to the global reference list so [n] is stable across
            # sections in the stitched document.
            remap: dict[int, int] = {}
            for local in sorted(used):
                paper = cited[local - 1]
                if paper not in global_sources:
                    global_sources.append(paper)
                remap[local] = global_sources.index(paper) + 1
            # Bind `remap` explicitly: re.sub runs inside this iteration, so a
            # closure would work today, but a late-bound loop variable in a
            # renumbering function is a bug waiting for the next refactor.
            def _renumber(match: re.Match, table: dict[int, int] = remap) -> str:
                local_index = int(match.group(1))
                return f"[{table[local_index]}]" if local_index in table else ""

            text = _CITE.sub(_renumber, text)

            sections[heading] = text
            theme_meta.append({"facet": facet, "heading": heading,
                               "sources_offered": len(cited), "sources_cited": len(used),
                               "citations_dropped": dropped})
            self._emit("section_written",
                       {"theme": heading, "chars": len(text), "sources_cited": len(used),
                        "citations_dropped": dropped}, iteration)

        if not sections:
            raise ValueError(
                "every section was rejected or failed. A review with no cited "
                "section is not a review."
            )

        review = self._stitch(state, sections, global_sources)
        self._emit(
            "review_written",
            {"sections": len(sections), "references": len(global_sources),
             "chars": len(review), "prompt_version": version("writer_v1"),
             "citations_dropped": sum(t["citations_dropped"] for t in theme_meta)},
            iteration,
        )
        return {"themes": theme_meta, "draft_sections": sections, "final_review": review,
                "artefacts": {"reference_order": [p.paper_id for p in global_sources]}}

    def _stitch(self, state: ReviewState, sections: dict[str, str],
                sources: list[Paper]) -> str:
        question = state.get("research_question", "")
        out = [f"# Literature Review: {question}", ""]
        for heading, body in sections.items():
            out += [f"## {heading}", "", body, ""]
        out += ["## References", ""]
        for n, paper in enumerate(sources, 1):
            authors = ", ".join(paper.authors[:3]) + (
                " et al." if len(paper.authors) > 3 else "")
            venue = f", {paper.venue}" if paper.venue else ""
            year = f", {paper.year}" if paper.year else ""
            doi = f". doi:{paper.doi}" if paper.doi else ""
            out.append(f"[{n}] {authors or 'Anon.'}, \"{paper.title}\"{venue}{year}{doi}")
        return "\n".join(out)


__all__ = ["Writer", "THEME_ORDER", "MIN_CITED_SECTION_CHARS"]
