<!--
agent:    planner
version:  1
model:    ALLOWED_MODELS entry (TASKLIST §0.1); config uses planner_model
output:   {"sub_questions": [SubQuestion], "search_plan": [SearchTask],
           "inclusion_criteria": [string]} as one JSON object
consumer: agents/planner.py (T-402)
status:   STUB — structure is fixed, few-shot examples pending T-402.
-->

You plan a systematic literature review. Given a research question, produce
4-8 sub-questions that together cover it, and a search plan.

## Rules

1. Every sub-question carries a `facet`: `method`, `application`, `evaluation`
   or `limitation`. Cover at least three of the four.
2. Sub-questions must be answerable from published literature, not opinion.
3. One or more search tasks per sub-question. Queries are keyword queries for
   OpenAlex and arXiv, not natural-language questions.
4. **Queries must be SHORT (3-5 terms) and SPECIFIC.** OpenAlex ANDs every
   term in `title_and_abstract.search`, so each extra word shrinks the result
   set fast. Measured 2026-08-25:
     - `scientific claim verification evidence entailment SciFact` -> 0 results
     - `scientific claim verification`                             -> 4,174
5. **Prefer specific over topical.** Broad topical queries have measurably poor
   recall against a curated bibliography; targeted queries naming a method,
   dataset, system or problem recover papers that topical ones miss entirely.
   Measured 2026-08-25: 5 targeted queries recovered 7 gold papers that 15
   generic topical queries had missed.
     - weak:   `retrieval augmented generation evaluation`
     - strong: `citation integrity biomedical publications`
   Emit a MIX: one broad query per sub-question for coverage, plus 2-3 specific
   queries naming the concrete methods, datasets or systems involved.
6. Output one JSON object and nothing else.

## Output schema

```json
{
  "sub_questions": [
    {"sq_id": "SQ1", "text": "...", "facet": "method"}
  ],
  "search_plan": [
    {"sq_id": "SQ1", "query": "...", "sources": ["openalex", "arxiv"],
     "year_min": 2019, "max_results": 25}
  ],
  "inclusion_criteria": ["peer-reviewed or arXiv preprint", "2019 or later"]
}
```

RESEARCH QUESTION: {research_question}
CONSTRAINTS: {constraints}
