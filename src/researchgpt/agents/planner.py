"""T-402 — the Planner. Research question -> sub-questions + search plan.

`SPEC §7.1`. This is the agent that decides what the system will look for, and
**the measurements say it is the binding constraint on the whole pipeline**:

* T-212 measured retrieval recall at **0.371** union / **0.057** Recall@60 using
  15 hand-written stand-in queries. The diagnosis (T-213,
  ``eval/diagnose_misses_t213.json``) was unambiguous: of the gold papers never
  retrieved, **10/10 exist in OpenAlex**, **0** were excluded by the date
  window, and **9/10 are findable by the short-query shape already in use**.
  They were not unreachable. *They were never asked for.*
* Retrieval recall is in turn a hard ceiling on verification, so a weak plan
  caps the graded groundedness metric no matter how good the Verifier is.

So the prompt carries the two measured query rules (3–5 terms because OpenAlex
ANDs them; specific over topical) plus a worked example, and this module's job
is to make the model's output *usable* — parsed, validated, repaired if
necessary, and never silently empty.

**Repair, not retry.** `SPEC §14` allows max 2 repair passes. A plain retry
resends the same prompt and usually gets the same malformed answer; a repair
pass sends the model **its own broken output plus the parse error**, which is
measurably more likely to converge. T-004 measured the winning model
(``openai/gpt-oss-120b``) at 100% clean-parse on the Extractor prompt, so this
should rarely fire — but "rarely" is not "never", and an empty plan produces a
confidently empty survey.

**This agent is NOT fail-soft.** A run with no plan retrieves nothing and
writes a survey about nothing. Contrast the Extractor (T-404), where one
unparseable paper must never abort the run.
"""

from __future__ import annotations

import json
from typing import Any

from researchgpt.agents.base import Agent
from researchgpt.core.llm import LLMClient, extract_json
from researchgpt.core.models import SearchTask, SubQuestion
from researchgpt.core.prompts import load, version
from researchgpt.graph.state import ReviewState

#: SPEC 14: at most two repair passes, then give up loudly.
MAX_REPAIRS = 2

#: SPEC 7.1 / planner_v1.md rule 1.
MIN_SUB_QUESTIONS = 4
MAX_SUB_QUESTIONS = 8
FACETS = {"method", "application", "evaluation", "limitation"}
MIN_FACETS_COVERED = 3

#: Measured 2026-08-25: OpenAlex ANDs every term in `title_and_abstract.search`,
#: so a 6-term query returns 0 results where a 3-term one returns thousands.
#: Enforced here rather than only requested in the prompt, because a plan that
#: silently retrieves nothing is the exact failure T-212 diagnosed.
MAX_QUERY_TERMS = 6
MIN_QUERY_TERMS = 2

_REPAIR_PROMPT = """Your previous response could not be used.

ERROR: $error

YOUR PREVIOUS RESPONSE:
$previous

Return the corrected JSON object and nothing else. Same schema as before.
"""


class PlanValidationError(ValueError):
    """The model returned parseable JSON that is not a usable plan."""


class Planner(Agent):
    name = "planner"
    fail_soft = False  # see module docstring

    def __init__(self, llm: LLMClient, cfg: Any, trace: Any = None) -> None:
        super().__init__(trace=trace)
        self._llm = llm
        self._cfg = cfg

    # -- validation --------------------------------------------------------

    @staticmethod
    def _validate(payload: dict) -> tuple[list[SubQuestion], list[SearchTask], list[str]]:
        """Turn raw JSON into typed objects, or say precisely what is wrong.

        The error strings are fed back to the model verbatim as the repair
        prompt, so they are written to be actionable by a reader who cannot see
        this code.
        """
        raw_sqs = payload.get("sub_questions")
        if not isinstance(raw_sqs, list) or not raw_sqs:
            raise PlanValidationError("'sub_questions' must be a non-empty list.")
        if not (MIN_SUB_QUESTIONS <= len(raw_sqs) <= MAX_SUB_QUESTIONS):
            raise PlanValidationError(
                f"Produced {len(raw_sqs)} sub-questions; need between "
                f"{MIN_SUB_QUESTIONS} and {MAX_SUB_QUESTIONS}."
            )

        sub_questions: list[SubQuestion] = []
        for i, item in enumerate(raw_sqs, 1):
            if not isinstance(item, dict):
                raise PlanValidationError(f"sub_questions[{i - 1}] is not an object.")
            facet = str(item.get("facet", "")).strip().lower()
            if facet not in FACETS:
                raise PlanValidationError(
                    f"sub_questions[{i - 1}].facet is {item.get('facet')!r}; "
                    f"must be one of {sorted(FACETS)}."
                )
            text = str(item.get("text", "")).strip()
            if not text:
                raise PlanValidationError(f"sub_questions[{i - 1}].text is empty.")
            sub_questions.append(
                SubQuestion(sq_id=str(item.get("sq_id") or f"SQ{i}"), text=text, facet=facet)
            )

        covered = {s.facet for s in sub_questions}
        if len(covered) < MIN_FACETS_COVERED:
            raise PlanValidationError(
                f"Sub-questions cover only {sorted(covered)}; at least "
                f"{MIN_FACETS_COVERED} of {sorted(FACETS)} must be covered."
            )

        raw_tasks = payload.get("search_plan")
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise PlanValidationError("'search_plan' must be a non-empty list.")

        known = {s.sq_id for s in sub_questions}
        search_plan: list[SearchTask] = []
        for i, item in enumerate(raw_tasks):
            if not isinstance(item, dict):
                raise PlanValidationError(f"search_plan[{i}] is not an object.")
            query = " ".join(str(item.get("query", "")).split())
            n_terms = len(query.split())
            if not query:
                raise PlanValidationError(f"search_plan[{i}].query is empty.")
            if n_terms > MAX_QUERY_TERMS:
                raise PlanValidationError(
                    f"search_plan[{i}].query has {n_terms} terms: {query!r}. OpenAlex "
                    f"ANDs every term, so queries longer than {MAX_QUERY_TERMS} return "
                    f"nothing. Shorten it to 3-5 specific terms."
                )
            if n_terms < MIN_QUERY_TERMS:
                raise PlanValidationError(
                    f"search_plan[{i}].query {query!r} is a single term - far too broad."
                )
            sq_id = str(item.get("sq_id") or "")
            if sq_id not in known:
                raise PlanValidationError(
                    f"search_plan[{i}].sq_id is {sq_id!r}, which is not one of "
                    f"{sorted(known)}. Every search task must attach to a sub-question."
                )
            sources = item.get("sources") or ["openalex", "arxiv"]
            search_plan.append(
                SearchTask(
                    sq_id=sq_id,
                    query=query,
                    sources=[str(s).strip().lower() for s in sources],
                    year_min=item.get("year_min"),
                    max_results=int(item.get("max_results") or 25),
                )
            )

        uncovered = known - {t.sq_id for t in search_plan}
        if uncovered:
            raise PlanValidationError(
                f"Sub-question(s) {sorted(uncovered)} have no search task. Every "
                f"sub-question needs at least one query."
            )

        criteria = [str(c).strip() for c in (payload.get("inclusion_criteria") or []) if c]
        return sub_questions, search_plan, criteria

    # -- run ---------------------------------------------------------------

    def run(self, state: ReviewState) -> dict[str, Any]:
        question = (state.get("research_question") or "").strip()
        if not question:
            raise PlanValidationError("state['research_question'] is empty.")

        constraints = dict(state.get("constraints") or {})
        constraints.setdefault("year_min", self._cfg.review.year_min)
        constraints.setdefault("max_papers", self._cfg.review.max_papers)
        constraints.setdefault(
            "sources", list(getattr(self._cfg.sources, "enabled", ["openalex", "arxiv"]))
        )

        prompt = load(
            "planner_v1",
            research_question=question,
            constraints=json.dumps(constraints, sort_keys=True),
        )
        model = self._cfg.llm.planner_model or self._cfg.llm.model

        last_error: str | None = None
        raw = ""
        for attempt in range(MAX_REPAIRS + 1):
            if attempt == 0:
                sent = prompt
            else:
                # Repair: show the model its own output and the exact failure.
                from string import Template

                sent = prompt + "\n\n" + Template(_REPAIR_PROMPT).substitute(
                    error=last_error or "", previous=raw[:4000]
                )
            raw = self._llm.complete(sent, model=model)
            try:
                payload = extract_json(raw)
                sub_questions, search_plan, criteria = self._validate(payload)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._emit(
                    "plan_repair",
                    {"attempt": attempt + 1, "error": last_error,
                     "prompt_version": version("planner_v1")},
                    state.get("iteration", 0),
                )
                continue

            self._emit(
                "plan_ready",
                {
                    "model": model,
                    "prompt_version": version("planner_v1"),
                    "repairs_used": attempt,
                    "n_sub_questions": len(sub_questions),
                    "n_search_tasks": len(search_plan),
                    "facets": sorted({s.facet for s in sub_questions}),
                    "mean_query_terms": round(
                        sum(len(t.query.split()) for t in search_plan) / len(search_plan), 2
                    ),
                    "queries": [t.query for t in search_plan],
                },
                state.get("iteration", 0),
            )
            return {
                "sub_questions": sub_questions,
                "search_plan": search_plan,
                "inclusion_criteria": criteria,
            }

        raise PlanValidationError(
            f"Planner produced no usable plan after {MAX_REPAIRS} repair passes. "
            f"Last error: {last_error}. Refusing to continue: a run with no plan "
            f"retrieves nothing and writes a survey about nothing."
        )


__all__ = ["Planner", "PlanValidationError", "MAX_QUERY_TERMS"]
