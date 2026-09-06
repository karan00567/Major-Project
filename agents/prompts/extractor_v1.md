<!--
agent:    extractor
version:  1
model:    any ALLOWED_MODELS entry (TASKLIST §0.1)
output:   PaperInsight (core/models.py) as a single JSON object
consumer: agents/extractor.py (T-404)

few-shot count. Dagdelen et al. measured structured output stabilising at
~20 examples and malformed below ~10 (SESSION_CONTEXT.md §5.10). This file
shipped THREE until 2026-08-27 and now ships SIX, added for T-409 because
TASKLIST requires the expansion before the Extractor is trusted for a real run.

The three new examples target failure modes measured on the M1 run, which
averaged 5.08/8 fields with `datasets` filled on only 6 of 12 papers:
  4  a SURVEY - models return all-nulls because there are no experiments, but
     a survey has a methodology (how it searched), results (its taxonomy) and
     stated advantages/disadvantages of the field it reviews
  5  a system paper with named components, where datasets/metrics ARE stated
  7  a thin abstract, where RESTRAINT is correct - included so the other four
     do not push the model toward padding

The thin-abstract example is load-bearing: adding examples that fill more fields, without one
that fills few, trades under-extraction for fabrication - the worse defect in a
hallucination-graded pipeline.

SIZE CEILING. Groq's free tier rejects a request body over ~20 KB with HTTP
413. Measured 2026-08-27: eight examples plus a real abstract sat right on that
edge and 413'd, which the Extractor absorbed as a parse failure and reported as
0/8 fields - a hard limit masquerading as a quality collapse. So Dagdelen's
~20 examples is NOT reachable on the zero-cost tier (TASKLIST 0.1), and six is chosen
to leave headroom for a long abstract. agents/extractor.py enforces the budget
explicitly rather than letting it surface as a 413.

WARNING — fenced output. Gemma ignores responseSchema and returns
markdown-fenced JSON (measured 2026-08-25). The caller must strip fences
before parsing. Do not "fix" this by asking harder in the prompt; handle it in
code.
-->

You extract structured information from a single research paper. You are part
of an automated literature-review system whose output is checked against the
source text by a claim verifier.

## Rules

1. Use **only** what appears in the provided text. Do not use prior knowledge
   about this paper, its authors, or its venue.
2. If the text does not support a field, set it to `null`. **Never guess.** A
   `null` is correct and costs nothing; an invented sentence is a defect that
   the verifier will drop and that will count against the system.
3. When you set a field, ground it: `evidence_spans` must quote the exact
   substring of the source text that supports it.
4. `advantages` and `disadvantages` are the paper's *own* claims and *own*
   stated limitations. `critique` is your assessment of a weakness the paper
   does not acknowledge — that is the one field where you may reason beyond
   the text, and it must be clearly analytical rather than factual.
5. Output **one JSON object and nothing else**. No prose before or after.

## Output schema

```json
{
  "methodology":   "string | null",
  "advantages":    "string | null",
  "disadvantages": "string | null",
  "critique":      "string | null",
  "datasets":      ["string"],
  "metrics":       ["string"],
  "results":       "string | null",
  "limitations":   "string | null",
  "evidence_spans": [
    {"quote": "exact substring from the source", "field": "methodology"}
  ],
  "extraction_note": "string | null"
}
```

Set `extraction_note` when the text was insufficient — e.g. `"abstract only, no
methods section"`. Leave it `null` otherwise.

## Examples

### Example 1 — full text available

SOURCE: "We evaluate citation accuracy in biomedical review articles. Using
BM25 retrieval followed by a MonoT5 reranker and a fine-tuned MultiVerS
entailment model, we classify each citation instance as supported or not. On a
set of highly cited papers we find 39.18% of citation instances contain
accuracy errors, against a historical median of 20%. Our pipeline reaches 0.59
micro-F1. Top-20 retrieval recall is 0.53, which bounds end-to-end
performance."

```json
{
  "methodology": "Three-stage pipeline: BM25 retrieval, MonoT5 reranking, then a fine-tuned MultiVerS entailment model classifying each citation instance as supported or unsupported.",
  "advantages": "Quantifies citation accuracy on real published review articles rather than synthetic claims.",
  "disadvantages": "Top-20 retrieval recall of 0.53 bounds end-to-end performance, so over 40% of relevant evidence is never seen by the entailment stage.",
  "critique": "Reporting a single micro-F1 conflates the retrieval ceiling with entailment quality; the two error sources cannot be separated from the numbers given.",
  "datasets": ["highly cited biomedical review articles"],
  "metrics": ["micro-F1", "top-20 recall", "citation accuracy error rate"],
  "results": "0.59 micro-F1; 39.18% of citation instances contain accuracy errors against a historical median of 20%; top-20 retrieval recall 0.53.",
  "limitations": "Retrieval recall of 0.53 is a hard ceiling on verification performance.",
  "evidence_spans": [
    {"quote": "Using BM25 retrieval followed by a MonoT5 reranker and a fine-tuned MultiVerS entailment model", "field": "methodology"},
    {"quote": "Our pipeline reaches 0.59 micro-F1", "field": "results"},
    {"quote": "Top-20 retrieval recall is 0.53, which bounds end-to-end performance", "field": "limitations"}
  ],
  "extraction_note": null
}
```

### Example 2 — a field genuinely absent

SOURCE: "We present a claim-verification service for scientific text. The
system decomposes an input claim, retrieves candidate abstracts, and scores
each with an entailment model. Evaluated on SciFact, GPT-4o-mini inside our
architecture reaches F1 0.720 while bare GPT-4o reaches 0.706."

Note: the source states no limitation, so `limitations` and `disadvantages`
are `null` rather than invented.

```json
{
  "methodology": "Claim decomposition, retrieval of candidate abstracts, then entailment scoring of each retrieved abstract against the claim.",
  "advantages": "A small model inside the architecture outperforms a larger model used bare, indicating the architecture contributes accuracy independently of model scale.",
  "disadvantages": null,
  "critique": "The comparison holds model family constant but not cost or latency, so the practical trade-off of the extra architectural stages is unquantified.",
  "datasets": ["SciFact"],
  "metrics": ["F1"],
  "results": "GPT-4o-mini within the architecture: F1 0.720. Bare GPT-4o: F1 0.706.",
  "limitations": null,
  "evidence_spans": [
    {"quote": "decomposes an input claim, retrieves candidate abstracts, and scores each with an entailment model", "field": "methodology"},
    {"quote": "GPT-4o-mini inside our architecture reaches F1 0.720 while bare GPT-4o reaches 0.706", "field": "results"}
  ],
  "extraction_note": null
}
```

### Example 3 — abstract only, degraded mode

SOURCE: "Abstract: We decompose queries with an LLM and retrieve per
sub-question, reranking with a cross-encoder without any additional training.
We report a 36.7% improvement in MRR@10."

```json
{
  "methodology": "LLM query decomposition into sub-questions, per-sub-question retrieval, and cross-encoder reranking, with no additional training.",
  "advantages": "Reports a 36.7% MRR@10 improvement without any training cost.",
  "disadvantages": null,
  "critique": "A relative improvement without an absolute baseline value cannot be compared against other systems.",
  "datasets": [],
  "metrics": ["MRR@10"],
  "results": "36.7% improvement in MRR@10.",
  "limitations": null,
  "evidence_spans": [
    {"quote": "decompose queries with an LLM and retrieve per sub-question, reranking with a cross-encoder", "field": "methodology"},
    {"quote": "36.7% improvement in MRR@10", "field": "results"}
  ],
  "extraction_note": "abstract only; no methods, dataset or limitations section available"
}
```

### Example 4 — a SURVEY paper (do not return all nulls)

A survey has no experiments, and models routinely conclude it therefore has no
extractable content. **That is wrong.** A survey's *methodology* is how it
searched and organised the literature; its *results* are the taxonomy or
findings it reports; its *advantages/disadvantages* are its own claims about
the field it reviews. `datasets` and `metrics` are legitimately empty.

SOURCE: "Large Language Models have advanced text generation, but reliance on
static training data produces outdated outputs. Retrieval-Augmented Generation
addresses this by grounding responses in retrieved evidence. This survey traces
the evolution from single-pass RAG to agentic RAG, in which autonomous agents
plan, retrieve iteratively and self-correct. We organise the field into a
taxonomy of single-agent, multi-agent and hierarchical designs, and review
applications across healthcare, finance and education. We find that agentic
designs improve adaptability on multi-step queries, but that evaluation remains
fragmented, with no shared benchmark across the surveyed systems."

```json
{
  "methodology": "Survey. Traces the evolution from single-pass RAG to agentic RAG and organises the field into a taxonomy of single-agent, multi-agent and hierarchical designs, with an application review across healthcare, finance and education.",
  "advantages": "Agentic designs improve adaptability on multi-step queries relative to single-pass RAG.",
  "disadvantages": "Evaluation across the surveyed systems is fragmented, with no shared benchmark.",
  "critique": "The taxonomy is descriptive rather than empirical: without a common benchmark the survey cannot say which of the three design families actually performs better, only that they differ structurally.",
  "datasets": [],
  "metrics": [],
  "results": "A three-way taxonomy of agentic RAG designs (single-agent, multi-agent, hierarchical); agentic designs adapt better to multi-step queries; evaluation is fragmented across the field.",
  "limitations": "No shared benchmark exists across the surveyed systems, so cross-system comparison is not possible.",
  "evidence_spans": [
    {"quote": "We organise the field into a taxonomy of single-agent, multi-agent and hierarchical designs", "field": "methodology"},
    {"quote": "agentic designs improve adaptability on multi-step queries", "field": "advantages"},
    {"quote": "evaluation remains fragmented, with no shared benchmark across the surveyed systems", "field": "limitations"}
  ],
  "extraction_note": "survey paper; no experimental datasets or metrics of its own"
}
```

### Example 5 — a system paper with named components

Name the concrete parts. `datasets` and `metrics` are usually recoverable from
a systems abstract even when results are summarised loosely.

SOURCE: "We present HM-RAG, a hierarchical multi-agent multimodal RAG
framework. A Decomposition Agent splits the query, three parallel Retrieval
Agents search vector, graph and web sources, and a Decision Agent fuses their
outputs by consistency voting. On ScienceQA and CrisisMMD, HM-RAG improves
answer accuracy by 12.1% and F1 by 3.8% over the strongest single-agent
baseline, without task-specific fine-tuning."

```json
{
  "methodology": "Hierarchical three-tier multi-agent framework: a Decomposition Agent splits the query, three parallel Retrieval Agents cover vector, graph and web sources, and a Decision Agent fuses their outputs by consistency voting.",
  "advantages": "Improves over the strongest single-agent baseline without task-specific fine-tuning, so the gain comes from the architecture rather than from training.",
  "disadvantages": null,
  "critique": "Three parallel retrieval agents plus a fusion stage multiply inference cost, and the abstract reports no latency or cost figure against the single-agent baseline it beats.",
  "datasets": ["ScienceQA", "CrisisMMD"],
  "metrics": ["answer accuracy", "F1"],
  "results": "+12.1% answer accuracy and +3.8% F1 over the strongest single-agent baseline.",
  "limitations": null,
  "evidence_spans": [
    {"quote": "A Decomposition Agent splits the query, three parallel Retrieval Agents search vector, graph and web sources, and a Decision Agent fuses their outputs by consistency voting", "field": "methodology"},
    {"quote": "improves answer accuracy by 12.1% and F1 by 3.8% over the strongest single-agent baseline", "field": "results"},
    {"quote": "without task-specific fine-tuning", "field": "advantages"}
  ],
  "extraction_note": null
}
```

### Example 6 — a thin abstract: restraint is the correct answer

**Do not pad.** Most fields here are genuinely unsupported, and inventing them
is a defect the verifier will catch. Extract only the two things stated.

SOURCE: "This paper explores the emerging field of agentic retrieval-augmented
generation. Building on traditional RAG, agentic RAG incorporates goal
reasoning and self-direction, enabling systems to make informed decisions about
what to retrieve. We discuss the implications for AI-driven information
retrieval and outline directions for future work."

```json
{
  "methodology": "Discussion paper on agentic RAG, framed as an extension of traditional RAG with goal reasoning and self-direction.",
  "advantages": "Goal reasoning and self-direction let the system decide what to retrieve rather than retrieving once against the original query.",
  "disadvantages": null,
  "critique": "The abstract asserts capability without describing an implementation or any evaluation, so the claimed benefit is positional rather than demonstrated.",
  "datasets": [],
  "metrics": [],
  "results": null,
  "limitations": null,
  "evidence_spans": [
    {"quote": "agentic RAG incorporates goal reasoning and self-direction, enabling systems to make informed decisions about what to retrieve", "field": "advantages"}
  ],
  "extraction_note": "abstract only; discussion paper with no implementation, evaluation or results reported"
}
```

## Now extract

PAPER TITLE: $title
TEXT AVAILABILITY: $text_availability

SOURCE:
$text
