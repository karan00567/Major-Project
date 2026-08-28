# Literature Review — Multi-Agent Agentic RAG for Automated Literature Review

> **Scope.** 25 papers, published 2023–2026, on agentic/multi-agent RAG, scientific document synthesis, automated review generation, and claim-level grounding. Plus 3 ranked candidate base papers (2024–2026 only).
>
> **Verification.** Every entry below was resolved against the **OpenAlex** and **Crossref** APIs by DOI; abstracts were pulled from OpenAlex, Semantic Scholar, or the ACL Anthology record. No citation in this document was written from memory. Where an abstract did not state something (e.g. dataset names), the field says so rather than guessing.
>
> **Venue policy.** In computer science the leading venues are conferences, not journals — ACL, NAACL, EMNLP, EACL and AAAI proceedings are Scopus-indexed and are treated here as peer-reviewed. Every paper in the main table appeared in a peer-reviewed journal or Scopus-indexed proceedings. **There are no arXiv-only preprints in the main table** (see §6).
>
> *Compiled 2026-08-06. Companion to `RESEARCHGPT_SPEC.md` and `PROJECT_PLAN.md`.*

---

## 1. ⚠️ Finding that affects your spec: the base paper is not what §1.2 says it is

`RESEARCHGPT_SPEC.md §1.2` describes the base paper as *"Aytar et al. (2025), Natural Language Processing Journal — RAG-based literature assistance."*

The paper is real and correctly attributed, but its actual content differs:

> **Aytar, A. Y., Kaya, K., & Kılıç, K. (2025).** "A synergistic multi-stage RAG architecture for boosting context relevance in data science literature." *Natural Language Processing Journal*, Elsevier. DOI: [10.1016/j.nlp.2025.100179](https://doi.org/10.1016/j.nlp.2025.100179)

From the verified abstract, the system integrates **GROBID structured parsing, domain-specific embedding fine-tuning from textbooks, semantic chunking, and an "Abstract First" retrieval strategy**, evaluated with **RAGAS** on a custom data-science query set, reporting a **>15-fold improvement in Context Relevance** over baseline RAG.

Two consequences you must act on:

1. **Your extension table (§1.3) contains a factual error.** It claims the base paper's retrieval control is a *"fixed single-pass pipeline."* It is explicitly a **multi-stage** architecture. A reviewer who reads the base paper will catch this immediately, and it is the row your whole "we are more agentic" narrative rests on. Rewrite that row.
2. **The task doesn't match.** Aytar et al. improve *context relevance for retrieval in the data-science domain*. They do not generate literature reviews. Positioning ResearchGPT as an extension means arguing across a task boundary, which is harder than it needs to be — see §2 for two better-fitting candidates.

Note also that Aytar et al. use **GROBID**, which `PROJECT_PLAN.md §2.2` cuts. If you keep Aytar as the base paper, dropping GROBID becomes a deviation you must defend rather than a free simplification.

---

## 2. Base paper candidates (2024–2026), ranked

### 🥇 Rank 1 — SurveyGen / QUAL-SG

**Bao, T., Nayeem, M. T., Rafiei, D., & Zhang, C. (2025).** "SurveyGen: Quality-Aware Scientific Survey Generation with Large Language Models." *Proceedings of EMNLP 2025 (Main)*. DOI: [10.18653/v1/2025.emnlp-main.136](https://doi.org/10.18653/v1/2025.emnlp-main.136)
**Venue:** EMNLP main conference · ACL Anthology · Scopus-indexed proceedings · verified via OpenAlex + ACL Anthology

**Why it is the cleanest extension target.** Same task as yours — automatic scientific survey generation. They build QUAL-SG, which *"enhances the standard Retrieval-Augmented Generation (RAG) pipeline by incorporating quality-aware indicators into literature retrieval to assess and select higher-quality source papers"* — which is precisely your venue-tier ranking (spec §11), meaning you have a directly comparable component rather than an analogy.

Decisively, **their own stated conclusion is your problem statement**: *"fully automatic survey generation still suffers from low citation quality and limited critical analysis."* Your Verifier attacks low citation quality; your Critic and four-field extraction schema attack limited critical analysis. You are not asserting a gap — you are citing the base paper's authors asserting it. That is the strongest possible extension narrative.

They also release **4,200+ human-written surveys and 242,143 cited references**, giving you an evaluation resource with the same provenance as your base paper.

*Extension claim:* QUAL-SG is a single-pass quality-aware RAG pipeline. ResearchGPT adds (a) agentic replanning, (b) claim-level verification with unsupported-claim removal, (c) a bounded critic loop, (d) structured per-paper extraction — each targeting a deficiency they report.

### 🥈 Rank 2 — Valsci

**Edelman, B., & Skolnick, J. (2025).** "Valsci: an open-source, self-hostable literature review utility for automated large-batch scientific claim verification using large language models." *BMC Bioinformatics*, 26. DOI: [10.1186/s12859-025-06159-4](https://doi.org/10.1186/s12859-025-06159-4)
**Venue:** BMC Bioinformatics · Springer Nature · Scopus-indexed journal (Q1/Q2) · verified via OpenAlex

**Why it fits.** It unites *"retrieval-augmented generation with structured bibliometric scoring and chain-of-thought prompting"* for literature-based claim verification, evaluated on **SciFact** — the exact dataset `PROJECT_PLAN.md §4.2` uses to train your verifier. It reports outperforming base GPT-4o *"in citation hallucination rate while maintaining a low misclassification rate,"* giving you a published anti-hallucination baseline to beat on shared data.

*Extension claim:* Valsci verifies claims but does not synthesise a review; it is a single guided prompt-flow, not a multi-agent graph, and its verifier is a prompted LLM rather than a trained model. ResearchGPT adds review synthesis, agentic control, and a fine-tuned local verifier.

*Weakness as base paper:* biomedical framing, and the output is a verification report rather than a literature review.

### 🥉 Rank 3 — Aytar et al. (your spec's current choice)

**Aytar, A. Y., Kaya, K., & Kılıç, K. (2025).** *Natural Language Processing Journal.* DOI: [10.1016/j.nlp.2025.100179](https://doi.org/10.1016/j.nlp.2025.100179)
**Venue:** Elsevier · Scopus-indexed journal · verified via Crossref + OpenAlex

Retained because it is Scopus-indexed, Elsevier-published, recent, and already embedded in your spec. But it ranks third: the task is context-relevance optimisation, not review generation; it is already multi-stage, which blunts the "we are more agentic" claim; and at the time of checking it had very few citations, so it carries less weight as a foundation than an EMNLP main-conference paper.

**Recommendation:** switch the base paper to **SurveyGen (Rank 1)** and demote Aytar et al. to a closely-related work you compare against. If your supervisor has already approved Aytar, keep it but **fix the §1.3 table row** and add SurveyGen as the primary comparison point.

---

## 3. Comparative table — 25 papers

`J` = journal · `C` = Scopus-indexed conference proceedings. Cells are compressed; full annotations in §4.

| # | Paper (first author, year) | Venue | Problem | Methodology | Advantages | Disadvantages | Dataset(s) | DOI |
|---|---|---|---|---|---|---|---|---|
| **C1 — RAG foundations** |
| 1 | Huang & Huang 2026 | ACM Comput. Surv. `J` | RAG research fragmented across sub-stages | Survey; 4-stage taxonomy: pre-retrieval / retrieval / post-retrieval / generation | Gives the stage vocabulary your architecture chapter needs | Survey — no new system or results | None | [10.1145/3805774](https://doi.org/10.1145/3805774) |
| 2 | Peng et al. 2025 | ACM TOIS `J` | Flat retrieval ignores entity relations | Survey of GraphRAG: graph indexing, graph-guided retrieval, graph-enhanced generation | Justifies why you did *not* need a graph store | Survey; GraphRAG immature | None | [10.1145/3777378](https://doi.org/10.1145/3777378) |
| 3 | Lyu et al. 2024 | ACM TOIS `J` | RAG benchmarks only test QA, ignore other uses | CRUD taxonomy (create/read/update/delete); benchmarks all pipeline components | Evaluates retriever + KB construction, not just the LLM | Chinese-language only; limits transfer | CRUD-RAG (own) | [10.1145/3701228](https://doi.org/10.1145/3701228) |
| 4 | Siriwardhana et al. 2023 | TACL `J` | RAG tuned on Wikipedia fails in specialist domains | RAG-end2end: joint retriever+generator training, auxiliary reconstruction signal | Real domain-adaptation gains; open-sourced in HuggingFace | Requires end-to-end training — infeasible at $0/CPU | COVID-19, News, Conversations | [10.1162/tacl_a_00530](https://doi.org/10.1162/tacl_a_00530) |
| **C2 — Agentic & self-reflective RAG** |
| 5 | Jeong et al. 2024 (Adaptive-RAG) | NAACL `C` | One retrieval strategy can't fit all query complexities | Classifier (small LM) routes queries to no-retrieval / single-step / iterative | Directly models your Planner's routing decision; auto-labelled training data | Classifier needs labels; abstract names no datasets | Open-domain QA sets (*unnamed in abstract*) | [10.18653/v1/2024.naacl-long.389](https://doi.org/10.18653/v1/2024.naacl-long.389) |
| 6 | Yu et al. 2024 (Chain-of-Note) | EMNLP `C` | Irrelevant retrieved docs mislead generation | Sequential "reading notes" per retrieved doc before answering; can answer "unknown" | Explicit refusal behaviour — the same property your §9.5 stress test demonstrates | Extra generation pass per document = costly under rate limits | 4 open-domain QA benchmarks (*unnamed*); 10K CoN set; LLaMa-2 7B | [10.18653/v1/2024.emnlp-main.813](https://doi.org/10.18653/v1/2024.emnlp-main.813) |
| 7 | Jeong et al. 2024 (Self-BioRAG) | Bioinformatics `J` | Generic RAG generalises poorly to specialist domains | Self-reflection via reflective tokens; domain retriever + 84k instruction set | +7.2% absolute over comparable ≤7B models; +8% ROUGE-1 vs RAG | Needs 84k domain instructions; biomedical only | 3 medical QA benchmarks (*unnamed*); 84k instructions | [10.1093/bioinformatics/btae238](https://doi.org/10.1093/bioinformatics/btae238) |
| 8 | Li et al. 2025 | Inf. Process. Manag. `J` | RAG not evidence-aware; errors propagate | Self-corrective chain-of-thought for evidence-aware RAG | Q1 IR journal; self-correction ≈ your Critic loop | ⚠️ **Abstract unavailable in OpenAlex/S2 — claims below unverified** | *Not verifiable from abstract* | [10.1016/j.ipm.2025.104369](https://doi.org/10.1016/j.ipm.2025.104369) |
| 9 | Ammann et al. 2025 | ACL SRW `C` | Multi-hop facts scattered across documents | LLM decomposes query → per-sub-question retrieval → cross-encoder rerank of merged pool | **Closest analogue to your Planner+Retriever.** MRR@10 +36.7%, F1 +11.6%; no extra training | Student Research Workshop (lighter review); gains are pipeline-specific | MultiHop-RAG, HotpotQA | [10.18653/v1/2025.acl-srw.32](https://doi.org/10.18653/v1/2025.acl-srw.32) |
| **C3 — Multi-agent LLM systems** |
| 10 | Qian et al. 2024 (ChatDev) | ACL `C` | Phase-specific models fragment multi-stage workflows | Role-specialised LLM agents; "chat chain" control + communicative dehallucination | Canonical evidence that role decomposition works; 1000+ citations | Software-engineering domain; no retrieval grounding | None named | [10.18653/v1/2024.acl-long.810](https://doi.org/10.18653/v1/2024.acl-long.810) |
| 11 | Li et al. 2024 | Vicinagearth (Springer) `J` | No unified account of LLM multi-agent systems | Survey; 5-component structure: profile, perception, self-action, mutual interaction, evolution | Gives you a citable vocabulary for your six-agent design chapter | Survey; young venue | None | [10.1007/s44336-024-00009-2](https://doi.org/10.1007/s44336-024-00009-2) |
| 12 | Yang et al. 2025 (AutoHMA-LLM) | IEEE TCCN `J` | Coordinating heterogeneous agents is costly | Multi-tier: cloud LLM planner + device-level LLMs; real-time feedback | Reports the efficiency numbers you'll want: −46% communication steps, −31% tokens/API calls, +5.7% accuracy | Robotics/IoT domain, not document synthesis | Logistics, inspection, search & rescue (no public set) | [10.1109/tccn.2025.3528892](https://doi.org/10.1109/tccn.2025.3528892) |
| **C4 — Scientific document understanding & IE** |
| 13 | Dagdelen et al. 2024 | Nature Communications `J` | Structured knowledge extraction from papers is hard | Fine-tuned GPT-3 / Llama-2 for joint NER + relation extraction; **outputs JSON** | **Direct precedent for your 4-field schema.** Nature-family venue, 645+ citations | Requires fine-tuning; materials-chemistry domain | Dopant–host, MOF, composition/phase/morphology tasks | [10.1038/s41467-024-45563-x](https://doi.org/10.1038/s41467-024-45563-x) |
| 14 | Sarol et al. 2024 | Bioinformatics `J` | Citations misrepresent what the cited paper said | BM25 + MonoT5 reranker retrieval → fine-tuned MultiVerS claim verification; 3-way labels | **The closest published analogue to your Verifier.** Honest numbers | Best model only 0.59 micro-F1 — a sober warning for your own targets | Own corpus: 100 papers, 3,063 annotated citation instances | [10.1093/bioinformatics/btae420](https://doi.org/10.1093/bioinformatics/btae420) |
| 15 | Li et al. 2024 | SDP @ ACL `C` | Citation generation conditioned on abstracts hallucinates | Condition on **cited text spans** instead of abstracts; distant labelling for CTS | Empirically shows abstract-only conditioning *teaches* hallucination | Distant labels are noisy; workshop venue | CTS-annotated data (*not named in abstract*) | [10.18653/v1/2024.sdp-1.9](https://doi.org/10.18653/v1/2024.sdp-1.9) |
| **C5 — Automated survey / review generation** |
| 16 | Kasanishi et al. 2023 (SciReviewGen) | ACL Findings `C` | No large-scale dataset for review generation | 10,000+ reviews, 690,000 cited papers from S2ORC; QFiD baseline | The field's reference dataset; chapter→cited-papers gives free gold sets | CC BY-NC; frozen mid-2020; needs S2ORC access | SciReviewGen (own), S2ORC | [10.18653/v1/2023.findings-acl.418](https://doi.org/10.18653/v1/2023.findings-acl.418) |
| 17 | Bao et al. 2025 (SurveyGen) | EMNLP `C` | No standard dataset to judge generated surveys | 4,200+ surveys, 242,143 refs; QUAL-SG adds quality-aware retrieval to RAG | **Base-paper candidate #1.** States your exact gap | Fully automatic generation still weak — which is the opening | SurveyGen (own) | [10.18653/v1/2025.emnlp-main.136](https://doi.org/10.18653/v1/2025.emnlp-main.136) |
| 18 | Funkquist et al. 2023 (CiteBench) | EMNLP `C` | Citation-text-generation task definitions diverge | Unifies multiple datasets into one benchmark; tests transferability | Standardised evaluation you can adopt instead of inventing metrics | Citation text ≠ full review; older task framing | Multiple unified datasets (*not individually named*) | [10.18653/v1/2023.emnlp-main.455](https://doi.org/10.18653/v1/2023.emnlp-main.455) |
| 19 | Bolaños et al. 2024 | Artif. Intell. Rev. `J` | No systematic map of AI-assisted SLR tooling | Reviews 21 SLR tools on 23 traditional + 11 AI features, plus 11 LLM tools | **Positions your system against real tools**; names the three open challenges | Tool review, not a system; no benchmarking | None | [10.1007/s10462-024-10902-3](https://doi.org/10.1007/s10462-024-10902-3) |
| 20 | Edelman & Skolnick 2025 (Valsci) | BMC Bioinformatics `J` | LLM literature tools hallucinate citations | RAG + bibliometric scoring + CoT; self-hostable; OpenAI-compatible | **Base-paper candidate #2.** Beats GPT-4o on citation hallucination; SciFact-evaluated | "Preliminary" evaluation; verification not synthesis | SciFact, Semantic Scholar | [10.1186/s12859-025-06159-4](https://doi.org/10.1186/s12859-025-06159-4) |
| **C6 — Grounding, verification & hallucination** |
| 21 | Es et al. 2024 (RAGAs) | EACL Demo `C` | RAG evaluation needs costly human references | Reference-free metric suite over retrieval and generation dimensions | The standard RAG eval framework; **used by your base paper** | Demo track; LLM-judged metrics inherit judge bias | None named in abstract | [10.18653/v1/2024.eacl-demo.16](https://doi.org/10.18653/v1/2024.eacl-demo.16) |
| 22 | Min et al. 2023 (FActScore) | EMNLP `C` | Binary factuality judgements are inadequate for long text | Decompose generation into **atomic facts**; % supported by a knowledge source | **The method your Verifier implements.** Automated estimator <2% error | Needs a reliable knowledge source; biography domain | People biographies; 13 LMs, 6,500 generations | [10.18653/v1/2023.emnlp-main.741](https://doi.org/10.18653/v1/2023.emnlp-main.741) |
| 23 | Gao et al. 2023 (ALCE) | EMNLP `C` | No reproducible benchmark for citation quality | ALCE benchmark; automatic metrics for fluency / correctness / citation quality | Correlates with human judgement; gives you a citation-accuracy metric | **Best models lack full citation support 50% of the time** — sobering | ELI5 (named); ALCE benchmark | [10.18653/v1/2023.emnlp-main.398](https://doi.org/10.18653/v1/2023.emnlp-main.398) |
| 24 | Huang et al. 2024 | ACM TOIS `J` | Hallucination literature lacks a unified taxonomy | Survey: taxonomy, causes, detection methods, benchmarks, mitigation | 1,700+ citations; explicitly covers RAG's *limits* in fighting hallucination | Survey; no new method | None | [10.1145/3703155](https://doi.org/10.1145/3703155) |
| 25 | Liu et al. 2024 (CliVER) | JAMIA Open `J` | Scientific claim verification is manual | Retrieve abstracts → extract sentences → PICO framing → 3-model ensemble (support/refute/neutral) | F1 0.92 on own set; **benchmarked against 4 clinicians** | Drops to 63.2% label accuracy vs clinicians on real claims | CoVERt (own), SciFact, 189,648 PubMed abstracts | [10.1093/jamiaopen/ooae021](https://doi.org/10.1093/jamiaopen/ooae021) |

---

## 4. Thematic synthesis

### C1 — RAG foundations (papers 1–4)
Huang & Huang's four-stage taxonomy (pre-retrieval / retrieval / post-retrieval / generation) is the cleanest scaffold for describing your pipeline, and using a *Computing Surveys* taxonomy rather than inventing your own strengthens the design chapter. Peng et al. matter mainly as a **negative justification**: GraphRAG is the current frontier in structural retrieval, and citing it lets you explain why a flat hybrid index is adequate at your corpus size instead of looking unaware. Lyu et al. is the argument that evaluating only the generator is insufficient — support for your component-wise ablations. Siriwardhana et al. shows joint retriever–generator training is the strongest domain-adaptation route and that **you are explicitly not taking it** ($0, CPU-only); cite it when defending frozen retrieval.

### C2 — Agentic and self-reflective RAG (papers 5–9)
This cluster establishes that adaptive control beats fixed pipelines. **Adaptive-RAG** is the strongest precedent for your Planner: a small classifier routing between no-retrieval, single-step and iterative strategies. **Ammann et al. is your single closest methodological relative** — LLM query decomposition, per-sub-question retrieval, cross-encoder reranking of a merged pool, explicitly *"without any extra training or specialized indexing."* That is your Planner + Retriever, and their +36.7% MRR@10 / +11.6% F1 gives you a published expectation to compare against. Treat it as a baseline, not just a citation. **Chain-of-Note** contributes the refusal behaviour your §9.5 stress test demonstrates: a system that answers "unknown" rather than inventing. Li et al. (IP&M) appears methodologically close, but **its abstract could not be retrieved and its claims are unverified** — read it before relying on it.

### C3 — Multi-agent LLM systems (papers 10–12)
Thinner than the other clusters, and honestly so: rigorous peer-reviewed multi-agent work is concentrated in software engineering and robotics, not document synthesis. ChatDev is the canonical demonstration that role specialisation plus structured communication outperforms monolithic prompting. Li et al.'s five-component framework gives you standard vocabulary. AutoHMA-LLM is the most useful of the three for your report because it publishes the *efficiency* numbers multi-agent systems are usually criticised for hiding (−46% communication steps, −31% token usage) — exactly the objection a reviewer will raise about six agents. **The absence of peer-reviewed multi-agent work on literature review is itself a gap you should claim (§5).**

### C4 — Scientific document understanding (papers 13–15)
Dagdelen et al. in *Nature Communications* is the strongest possible precedent for structured JSON extraction from scientific text, and it validates your four-field schema as an established design rather than an invention. **Sarol et al. is the most important paper in this document for calibrating your expectations**: it is essentially your Verifier, built carefully with BM25 + MonoT5 + fine-tuned MultiVerS, and it reaches only **0.59 micro-F1**. If your fine-tuned verifier reports 0.9+ on real citations, something is wrong with your evaluation. Li et al. proves empirically that conditioning on abstracts rather than full-text spans *teaches models to hallucinate* — a direct argument for your `evidence_spans` design and against the abstract-only degraded mode in `PROJECT_PLAN.md`.

### C5 — Automated survey generation (papers 16–20)
The cluster your work sits in. SciReviewGen supplies the dataset; SurveyGen supplies both a newer dataset and the quality-aware retrieval baseline; CiteBench supplies evaluation discipline. Bolaños et al. is strategically valuable because it maps 21 existing SLR tools — use it to position ResearchGPT against real systems rather than against a strawman. Valsci is the most direct competitor: open-source, self-hostable, SciFact-evaluated, explicitly targeting citation hallucination. **You must cite and compare against Valsci or a reviewer will ask why you didn't.**

### C6 — Grounding and verification (papers 21–25)
This cluster underwrites your graded criterion. FActScore is the method your Verifier implements — atomic decomposition plus per-fact support checking — and citing it means your design is a recognised technique, not an ad-hoc filter. ALCE supplies the citation-quality metrics and the sobering finding that top systems fail full citation support half the time. Huang et al.'s survey covers the limits of RAG as a hallucination remedy, which you need for an honest limitations section. CliVER is the most useful methodologically: a three-way ensemble reaching F1 0.92 on its own data but only **63.2% against clinicians on real claims** — the clearest available evidence that in-domain benchmark scores overstate real-world verification accuracy.

---

## 5. Research gaps

Ordered by how directly ResearchGPT addresses them. Gaps 1–3 are defensible contribution claims; 4–5 are honest openings you may not fill this cycle.

**Gap 1 — No peer-reviewed multi-agent architecture for literature review generation.**
C3 demonstrates role specialisation in software engineering (ChatDev) and robotics (AutoHMA-LLM). C5 shows review generation is done with single-pass RAG pipelines (SurveyGen's QUAL-SG, Valsci's guided prompt-flow). **The intersection is empty in the peer-reviewed 2023–2026 literature.** This is your primary claim, and this review is the evidence for it.

**Gap 2 — Verification is a separate literature from review generation.**
C6 develops claim-level grounding (FActScore, ALCE) and C4 applies it to citations (Sarol et al.), but no C5 system embeds atomic-claim verification as a *control mechanism* that removes unsupported content before writing. Valsci verifies claims but doesn't synthesise; SurveyGen synthesises but reports low citation quality. ResearchGPT's Verifier-as-filter sits exactly in that gap.

**Gap 3 — No bounded feedback loop with explicit stop criteria.**
Adaptive-RAG routes *once*, per query. Self-BioRAG self-reflects *within* a generation. Neither implements an iteration-capped outer loop that can send control back to planning based on a coverage assessment. Your Critic with `max_iterations=3` and forced-WRITE termination is genuinely unoccupied territory.

**Gap 4 — Structured per-paper extraction is not applied to review generation.**
Dagdelen et al. show LLMs can produce structured JSON records from scientific text; C5 systems still emit free text. Your four-field schema bridges these, though the contribution is smaller than 1–3 since it is an application of an established technique.

**Gap 5 — Evaluation of generated reviews is unsettled and partly circular.**
RAGAs is reference-free but LLM-judged; ALCE needs annotated corpora; SurveyGen relies on human evaluation. Nobody has a trusted automatic measure of review quality. This gap constrains *you* as much as it opens an opportunity — it is why `PROJECT_PLAN.md §9.6` insists your groundedness number be measured independently rather than by your own Verifier.

**Two absences worth naming honestly in your Limitations section:**
- **Cost- and hardware-constrained agentic RAG is essentially unstudied.** Every system above assumes frontier-model API access. Your $0, CPU-only constraint is unusual — which makes it a modest novelty, but also means there is no baseline to compare against.
- **Domain shift in scientific claim verification is under-reported.** SciFact and CliVER are biomedical; your corpus is CS. CliVER's 0.92→63.2% drop is the warning sign, and no paper in this set measures cross-domain verifier transfer.

---

## 6. Verification report

**Method.** Each DOI was resolved through the OpenAlex works API; the base paper was additionally confirmed via Crossref author+container query. Abstracts came from OpenAlex `abstract_inverted_index`, Semantic Scholar, or the ACL Anthology record. Search used OpenAlex `title_and_abstract.search` with a hard `2023-01-01 … 2026-12-31` publication-date filter, across 6 thematic clusters and 28 named-system queries (~712 unique works screened).

**Results.** 35 DOIs fetched, **0 resolution failures**. All 25 main-table papers resolved to a peer-reviewed journal or Scopus-indexed proceedings. **All are within the 2023–2026 window.**

**⚠️ Flagged — verified record, unverified content (1 paper):**

| Paper | Issue |
|---|---|
| #8 Li et al. 2025, *Inf. Process. Manag.*, [10.1016/j.ipm.2025.104369](https://doi.org/10.1016/j.ipm.2025.104369) | DOI, title, authors, venue and year confirmed in OpenAlex **and** Semantic Scholar. **Abstract absent from both.** Its Problem/Methodology/Dataset cells derive from the title only. **Read the paper before citing it.** Note: Semantic Scholar dates it 2026, OpenAlex 2025 — confirm the year before it enters your reference list. |

**Excluded — preprint-only (not in main table).** The sweep found ~70 arXiv-only works, including several the field treats as canonical — Self-RAG, Corrective RAG, RAPTOR, AutoSurvey, MetaGPT, the Gao et al. RAG survey. Per your constraint these are omitted from the main table. Two consequences worth weighing:

- Self-RAG and Corrective RAG are the most-cited self-reflective RAG systems in existence. A reviewer may expect them. If you cite them, label `[preprint]` as your constraint requires and keep them out of the comparative table.
- Your spec §1.5 notes Self-RAG was resolved "via OpenReview." **ICLR/NeurIPS OpenReview papers are peer-reviewed and Scopus-indexed** — if Self-RAG's ICLR 2024 version is what you cite, it is *not* a preprint and belongs in the main table. Worth confirming; I could not establish a non-arXiv DOI for it via OpenAlex.

**Verified reserve pool (9 papers).** Fully resolved, in-window, peer-reviewed, but cut for balance. Use as substitutes:

| Paper | Venue | DOI |
|---|---|---|
| Zhang et al. 2025, LongCite (sentence-level citations) | ACL Findings | [10.18653/v1/2025.findings-acl.264](https://doi.org/10.18653/v1/2025.findings-acl.264) |
| Yan et al. 2025, Atomic Fact Decomposition for Attributed QA | IEEE TKDE | [10.1109/tkde.2025.3608716](https://doi.org/10.1109/tkde.2025.3608716) |
| Zhang et al. 2025, Siren's Song: hallucination survey | Computational Linguistics | [10.1162/coli.a.16](https://doi.org/10.1162/coli.a.16) |
| Malin et al. 2025, Faithfulness metrics review | IEEE JSTSP | [10.1109/jstsp.2025.3579203](https://doi.org/10.1109/jstsp.2025.3579203) |
| Ofori-Boateng et al. 2024, SR automation review | Artif. Intell. Rev. | [10.1007/s10462-024-10844-w](https://doi.org/10.1007/s10462-024-10844-w) |
| Khraisha et al. 2024, Can LLMs replace humans in SRs? | Research Synthesis Methods | [10.1002/jrsm.1715](https://doi.org/10.1002/jrsm.1715) |
| Luo et al. 2023, CitationSum | ACM (WWW) | [10.1145/3543507.3583505](https://doi.org/10.1145/3543507.3583505) |
| Wu et al. 2026, RAG for NLP survey (retrieval-fusion taxonomy) | Artif. Intell. Rev. | [10.1007/s10462-026-11605-7](https://doi.org/10.1007/s10462-026-11605-7) |
| Wang et al. 2024, LLM autonomous agents survey | Front. Comput. Sci. | [10.1007/s11704-024-40231-1](https://doi.org/10.1007/s11704-024-40231-1) |

---

## 7. Three things to act on

1. **Fix `RESEARCHGPT_SPEC.md §1.2 and §1.3.** The base paper is a multi-stage data-science RAG architecture, not literature assistance, and the "fixed single-pass pipeline" row is wrong.
2. **Switch the base paper to SurveyGen (Bao et al. 2025)** — same task, and its stated conclusion *is* your problem statement.
3. **Recalibrate your verifier target using Sarol et al. (0.59 micro-F1) and CliVER (0.92 in-domain → 63.2% against clinicians).** `PROJECT_PLAN.md` currently targets groundedness ≥ 0.9. Against real citations that would be an outlier, not a success — so measure it independently, or you will be defending a number that looks too good.

---

*All DOIs resolvable as of 2026-08-06. Re-verify before submission — DOI records and publication years can change, and one entry (#8) has a year discrepancy across sources.*
