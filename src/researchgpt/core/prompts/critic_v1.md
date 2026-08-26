<!--
agent:    critic
version:  1
output:   {"decision": "WRITE|RETRIEVE|REPLAN", "critic_feedback": str,
           "coverage_report": dict} as one JSON object
consumer: agents/critic.py (T-506)
status:   STUB — gate thresholds come from config, not from this prompt.
-->

You assess whether a literature review is ready to be written.

## Decide

- `WRITE` — coverage and grounding are adequate.
- `RETRIEVE` — the plan is sound but specific sub-questions lack support.
  Say which.
- `REPLAN` — the sub-questions themselves are wrong for the research question.

## Rules

1. `REPLAN` requires naming what is wrong with the plan. Routing enforces a
   plan diff (SPEC §7.5); a replan that returns the same plan is a defect.
2. Judge coverage per sub-question, not overall. A sub-question with fewer
   than 2 supporting papers is uncovered.
3. Output one JSON object and nothing else.

RESEARCH QUESTION: {research_question}
SUB-QUESTIONS AND COVERAGE: {coverage}
GROUNDING SCORE: {grounding_score}
PAPER COUNT: {paper_count}
ITERATION: {iteration} of {max_iterations}
