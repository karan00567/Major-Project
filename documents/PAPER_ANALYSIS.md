# Extensive Paper Analysis — 25 Papers + Base Paper

> **Purpose.** Per-paper deep dive for the Literature Survey chapter. Each entry covers **Problem · Methodology · Advantages · Disadvantages · Dataset(s) · Relevance to ResearchGPT**.
>
> **Provenance.** All 26 records re-fetched 2026-08-06 from the **OpenAlex** works API by DOI (0 failures), with **Crossref** fallback for abstracts and the **ACL Anthology** record used where OpenAlex stored a citation stub instead of an abstract. Every quoted claim and number below comes from the paper's own abstract. Where an abstract does not state something, the entry says **"not stated in abstract"** rather than guessing.
>
> **Reading the fields.** *Problem / Methodology / Advantages / Disadvantages / Datasets* are drawn from the source. **Relevance to ResearchGPT is my analysis, not the authors' claim** — treat it as an argument to check, not a fact to cite.
>
> **Citation counts** are OpenAlex as of 2026-08-06 and are conservative; Semantic Scholar reports higher figures for several papers (ChatDev: 279 in OpenAlex vs 1,043 in S2). Use one source consistently in your report.
>
> *Companion to `LITERATURE_REVIEW.md` (comparative table, gaps, base-paper ranking). Cluster codes follow `RESEARCHGPT_SPEC.md §1.6`.*

---

## Contents

| Cluster | Papers | Theme |
|---|---|---|
| **BASE** | Aytar et al. 2025 | The spec's nominated base paper |
| **C1** | 01–04 | RAG foundations and advances |
| **C2** | 05–09 | Agentic and self-reflective RAG |
| **C3** | 10–12 | Multi-agent LLM systems |
| **C4** | 13–15 | Scientific document understanding and IE |
| **C5** | 16–20 | Automated survey and review generation |
| **C6** | 21–25 | Grounding, verification and hallucination |

---

# BASE PAPER

## Aytar, Kaya & Kılıç (2025) — Synergistic Multi-Stage RAG

**Full citation.** Aytar, A. Y., Kaya, K., & Kılıç, K. (2025). "A synergistic multi-stage RAG architecture for boosting context relevance in data science literature." *Natural Language Processing Journal*, Elsevier.
**DOI.** [10.1016/j.nlp.2025.100179](https://doi.org/10.1016/j.nlp.2025.100179) · Elsevier · Scopus-indexed journal · 3 authors · 2 citations · 11 references

### Problem
Data science literature is voluminous and fast-moving, creating a navigation bottleneck. The specific technical failure the paper targets: *"Standard Retrieval-Augmented Generation (RAG) systems often struggle with retrieving precisely relevant context from this dense academic corpus."* The problem is framed as **retrieval precision within a specialist academic corpus** — not review generation.

### Methodology
A four-component multi-stage architecture, each stage addressing a different retrieval failure:
1. **Structured document parsing via GROBID** — recovers section and reference structure from PDFs rather than treating them as flat text.
2. **Domain-specific embedding fine-tuning derived from textbooks** — adapts the embedding space to data-science vocabulary using textbook material as the training signal.
3. **Semantic chunking for coherence** — chunk boundaries follow meaning rather than fixed character counts.
4. **"Abstract First" retrieval strategy** — a novel strategy prioritising *"concise, high-signal summaries"* over full-text passages.

Evaluated with the **RAGAS** framework against a custom data-science query set, including ablations against *"configurations using only subsets of these enhancements."*

### Advantages
- Reports a **>15-fold improvement in Context Relevance** over baseline RAG — a very large effect.
- Ablation-driven: shows the *combination* beats any subset, supporting the "synergistic" claim.
- The "Abstract First" finding is genuinely counter-intuitive and useful: abstracts outperform full-text chunks for retrieval in specialist academic domains.
- Published in a Scopus-indexed Elsevier journal.

### Disadvantages
- **Single metric.** Context Relevance only; no end-to-end answer quality, faithfulness, or downstream task evaluation reported in the abstract.
- **Custom, unreleased query set.** A bespoke evaluation set means the 15× figure is not independently comparable — and a 15× gain suggests a weak baseline as much as a strong system.
- **Domain-locked.** Textbook-derived embedding fine-tuning does not transfer without equivalent textbook material.
- **Heavy infrastructure.** GROBID plus embedding fine-tuning is a substantial stack.
- **Very low citation count** (2 at time of check) — limited external validation so far.

### Dataset(s)
Custom data-science query set (not publicly named). Textbook corpus for embedding fine-tuning (not named). Evaluation framework: RAGAS. **No public benchmark used.**

### Relevance to ResearchGPT
⚠️ **Two problems you must address before building on this paper.**

**First, `RESEARCHGPT_SPEC.md §1.2` mis-describes it.** The spec calls it "RAG-based literature assistance." It is a retrieval-precision architecture for data science. It does not generate literature reviews.

**Second, your extension table (§1.3) is factually wrong about it.** The table claims the base paper's retrieval control is a *"Fixed single-pass pipeline."* It is explicitly a **multi-stage** architecture with four coordinated stages. That row is the foundation of your "we are more agentic" argument, and any reviewer who opens the base paper will see it. **Rewrite it.** The defensible contrast is not multi-stage vs. single-stage — it is **static multi-stage vs. dynamic agentic control with replanning and verification**. That is still a real difference, but it is a narrower and more honest one.

Third, a practical conflict: Aytar et al. rely on **GROBID**, which `PROJECT_PLAN.md §2.2` cuts for setup cost. If this remains your base paper, dropping GROBID becomes a deviation you must justify rather than a free simplification. If you switch to SurveyGen (see `LITERATURE_REVIEW.md §2`), that conflict disappears.

**Genuinely useful takeaway regardless:** the "Abstract First" result supports your degraded abstract-only mode for paywalled papers (`PROJECT_PLAN.md §11`) — it suggests abstract-only retrieval may be a reasonable default, not merely a fallback.

---

# C1 — RAG FOUNDATIONS

## 01 · Huang & Huang (2026) — Survey on Retrieval-Augmented Text Generation

**Citation.** Huang, Y., & Huang, J. X. (2026). "A Survey on Retrieval-Augmented Text Generation for Large Language Models." *ACM Computing Surveys*.
**DOI.** [10.1145/3805774](https://doi.org/10.1145/3805774) · ACM · Scopus-indexed Q1 journal · 34 citations

### Problem
RAG research has fragmented as the paradigm has grown: *"As RAG grows in complexity and incorporates multiple concepts that can influence its performance,"* there is no shared organising vocabulary, so studies are hard to compare.

### Methodology
Systematic survey organising RAG into **four sequential categories from the retrieval viewpoint**: (1) pre-retrieval, (2) retrieval, (3) post-retrieval, (4) generation. Analyses significant studies within each stage, then surveys evaluation methods and open challenges.

### Advantages
- Published in *ACM Computing Surveys* — among the highest-authority venues for a taxonomy citation.
- The four-stage structure maps almost directly onto a RAG system's implementation, making it immediately usable as a document structure.
- Explicitly covers evaluation methods, so it supports both your design and evaluation chapters.

### Disadvantages
- Survey — no new system, no experiments, no empirical claims of its own.
- Retrieval-centric framing under-weights generation-side and agentic-control concerns, which is exactly where your contribution lies.
- Only 30 references recorded in OpenAlex, which is modest for a *Computing Surveys* article; verify coverage depth before leaning on it as comprehensive.

### Dataset(s)
**None** — survey.

### Relevance to ResearchGPT
The **default organising scaffold for your System Design chapter.** Rather than inventing your own decomposition, map your components onto their four stages: Planner → pre-retrieval; Retriever → retrieval; reranking/verification → post-retrieval; Writer → generation. Borrowing a *Computing Surveys* taxonomy makes your design chapter legible to reviewers instantly and costs nothing. Also your best single citation for the sentence "RAG mitigates but does not eliminate hallucination."

---

## 02 · Peng et al. (2025) — Graph Retrieval-Augmented Generation: A Survey

**Citation.** Peng, B., Zhu, Y., Liu, Y., Bo, X., Shi, H., Hong, C., Zhang, Y., & Tang, S. (2025). "Graph Retrieval-Augmented Generation: A Survey." *ACM Transactions on Information Systems*.
**DOI.** [10.1145/3777378](https://doi.org/10.1145/3777378) · ACM TOIS · Scopus-indexed Q1 · 66 citations

### Problem
Flat vector retrieval discards relational structure: *"the complex structure of relationships among different entities in databases presents challenges for RAG systems."* Standard RAG cannot follow entity relationships across documents.

### Methodology
First comprehensive survey of GraphRAG. Formalises a three-stage workflow — **Graph-Based Indexing → Graph-Guided Retrieval → Graph-Enhanced Generation** — then covers core technologies and training methods per stage, downstream tasks, application domains, evaluation methodologies, and industrial use cases. Maintains a live repository.

### Advantages
- First systematic treatment of GraphRAG; ACM TOIS venue.
- The three-stage formalisation is clean and citable.
- Covers industrial deployments, not just academic prototypes.

### Disadvantages
- Survey of a young area — the authors themselves note its *"novelty."*
- Graph construction cost is a serious practical barrier that a survey framing tends to understate.
- No comparative benchmarking of GraphRAG against flat RAG, so the actual benefit remains unquantified.

### Dataset(s)
**None** — survey.

### Relevance to ResearchGPT
Cite this as a **deliberate non-choice**, which is more valuable than it sounds. GraphRAG is the current frontier in structural retrieval, and a reviewer may ask why a system built on a *citation graph domain* doesn't use one. Having this citation lets you answer: at ~60 papers and ~3k chunks, graph indexing cost is not repaid, and `PROJECT_PLAN.md §2.2` cuts it for that reason. Naming the alternative and explaining the trade-off reads as engineering judgement; ignoring it reads as unawareness. It is also the obvious **Future Work** item — a citation-graph-aware retriever is the natural next version of your system.

---

## 03 · Lyu et al. (2024) — CRUD-RAG

**Citation.** Lyu, Y., Li, Z., Niu, S., Xiong, F., Tang, B., Wang, W., Wu, H., Liu, H., Xu, T., & Chen, E. (2024). "CRUD-RAG: A Comprehensive Chinese Benchmark for Retrieval-Augmented Generation of Large Language Models." *ACM Transactions on Information Systems*.
**DOI.** [10.1145/3701228](https://doi.org/10.1145/3701228) · ACM TOIS · Scopus-indexed Q1 · 88 citations

### Problem
RAG benchmarks are too narrow. They *"focus primarily on question-answering applications, neglecting other potential scenarios,"* and critically they *"often assess only the LLM components of the RAG pipeline or the retriever... overlooking the impact of external knowledge base construction and the retrieval component on the entire RAG pipeline."* Evaluating the generator alone hides where systems actually fail.

### Methodology
Categorises RAG applications by **CRUD operations**: **Create** (generating original varied content), **Read** (knowledge-intensive QA), **Update** (correcting inaccuracies in existing text), **Delete** (summarising long text). Builds a separate dataset per category, then analyses the effect of individual components — *"the retriever, context length, knowledge base construction, and LLM."* Code released.

### Advantages
- **Component-wise evaluation** — directly supports the argument that ablation is necessary, not optional.
- Covers generation scenarios beyond QA, including summarisation, which is closer to review writing.
- Explicitly evaluates knowledge-base construction, a stage almost every other benchmark ignores.
- Public code.

### Disadvantages
- **Chinese-language only** — results may not transfer to English scientific text, and you cannot reuse the data.
- CRUD is borrowed from database semantics and fits generation tasks somewhat loosely.
- No agentic or multi-step retrieval scenarios.

### Dataset(s)
**CRUD-RAG** (own, Chinese) — four sub-datasets, one per CRUD category.

### Relevance to ResearchGPT
Your **methodological justification for ablations 2–4** (`PROJECT_PLAN.md §9.4`). When a reviewer asks why you ablate components instead of just reporting end-to-end quality, this is the peer-reviewed answer: a TOIS benchmark paper arguing that whole-pipeline evaluation obscures component-level failure. Their "Delete" category (summarising long text) is also the closest published analogue to review synthesis. Note the language limitation honestly — you cannot reuse their data, only their argument.

---

## 04 · Siriwardhana et al. (2023) — RAG-end2end

**Citation.** Siriwardhana, S., Weerasekera, R., Wen, E., Kaluarachchi, T., Rana, R., & Nanayakkara, S. (2023). "Improving the Domain Adaptation of Retrieval Augmented Generation (RAG) Models for Open Domain Question Answering." *Transactions of the Association for Computational Linguistics*, 11.
**DOI.** [10.1162/tacl_a_00530](https://doi.org/10.1162/tacl_a_00530) · TACL (MIT Press) · Scopus-indexed Q1 · 297 citations

### Problem
*"RAG has only been trained and explored with a Wikipedia-based external knowledge base and is not optimized for use in other specialized domains such as healthcare and news."* Off-the-shelf RAG degrades on specialist corpora.

### Methodology
**RAG-end2end** extends RAG with **joint training of retriever and generator** for the end QA task, updating *"all components of the external knowledge base during training"* — including re-encoding the knowledge base as the retriever changes. Adds an **auxiliary reconstruction signal** that *"forces RAG-end2end to reconstruct a given sentence by accessing the relevant information from the external knowledge base,"* injecting domain knowledge beyond the QA objective. Open-sourced into HuggingFace Transformers.

### Advantages
- Significant gains over original RAG across three distinct domains.
- The auxiliary reconstruction objective is an elegant, reusable idea.
- TACL venue and 297 citations — well validated.
- Shipped in HuggingFace Transformers, which is unusually strong evidence of reproducibility.

### Disadvantages
- **Requires end-to-end training including periodic knowledge-base re-encoding** — computationally heavy.
- **Flatly infeasible for your project**: $0 budget, CPU-only.
- Restricted to open-domain QA, not long-form generation.
- Pre-dates the instruction-tuned LLM era; the baseline is now dated.

### Dataset(s)
Three domain datasets: **COVID-19**, **News**, **Conversations**.

### Relevance to ResearchGPT
Cite this to **defend your frozen retriever**. It is the strongest evidence that joint retriever–generator training is the most effective domain-adaptation route — and you are not taking it. Naming the superior approach you rejected, with the reason (CPU-only, $0, `PROJECT_PLAN.md §6.1`), converts a resource limitation into a stated scope decision. It also sharpens the contribution of your **trained verifier**: you adapt the *verification* component to the domain rather than the retriever, which is the cheap end of the same idea. Put this paper in Limitations *and* Future Work.

---

# C2 — AGENTIC & SELF-REFLECTIVE RAG

## 05 · Jeong et al. (2024) — Adaptive-RAG

**Citation.** Jeong, S., Baek, J., Cho, S., Hwang, S. J., & Park, J. C. (2024). "Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity." *Proceedings of NAACL-HLT 2024 (Long Papers)*.
**DOI.** [10.18653/v1/2024.naacl-long.389](https://doi.org/10.18653/v1/2024.naacl-long.389) · ACL Anthology · Scopus-indexed · 182 citations
*(Abstract from ACL Anthology; OpenAlex holds only a citation stub.)*

### Problem
Retrieval strategies are applied uniformly regardless of need. Existing approaches *"either handle simple queries with unnecessary computational overhead or fail to adequately address complex multi-step queries; yet, not all user requests fall into only one of the simple or complex categories."* The binary framing is itself the flaw.

### Methodology
An **adaptive QA framework** that dynamically selects among three strategies by query complexity: **no retrieval → single-step retrieval → iterative multi-step retrieval**. Routing is performed by *"a classifier, which is a smaller LM trained to predict the complexity level of incoming queries."* Training labels are collected automatically from *"actual predicted outcomes of models and inherent inductive biases in datasets"* — no manual annotation. Code released.

### Advantages
- **Automatic label collection** removes the main cost of training a router.
- A small LM as router is cheap at inference — architecturally compatible with your constraints.
- Improves both efficiency *and* accuracy, rather than trading one for the other.
- Beats other adaptive-retrieval baselines, not just static RAG.
- 182 citations; NAACL main conference.

### Disadvantages
- Router quality caps system quality — a misrouted query fails silently.
- Complexity labels derived from model outcomes risk encoding the base model's weaknesses as ground truth.
- **The abstract names no datasets** — only *"a set of open-domain QA datasets."*
- Single-turn QA, not multi-document synthesis.

### Dataset(s)
Open-domain QA datasets covering multiple query complexities — **specific datasets not named in the abstract.** Verify from the paper before citing dataset names.

### Relevance to ResearchGPT
**The strongest published precedent for your Planner.** Your Planner decides how to decompose and route retrieval; Adaptive-RAG shows a learned router doing exactly this and quantifies the benefit. Two concrete uses:

1. **Design justification.** Your claim that "one retrieval strategy does not fit all sub-questions" is not an assumption — it is Adaptive-RAG's empirically supported thesis.
2. **A cheaper design you should consider.** Their router is a *small LM*, not a frontier model. Under your rate-limited free tier (`PROJECT_PLAN.md §6.2`), routing sub-questions with a small local classifier rather than an API call is directly in the spirit of this paper and would cut request volume.

Also note the contrast that sharpens your contribution: Adaptive-RAG routes **once per query, before retrieval**. Your Critic re-routes **after seeing results**. That is a genuine architectural difference and it is exactly the gap in `LITERATURE_REVIEW.md §5 Gap 3`.

---

## 06 · Yu et al. (2024) — Chain-of-Note

**Citation.** Yu, W., Zhang, H., Pan, X., Cao, P., Ma, K., Li, J., Wang, H., & Yu, D. (2024). "Chain-of-Note: Enhancing Robustness in Retrieval-Augmented Language Models." *Proceedings of EMNLP 2024 (Main)*.
**DOI.** [10.18653/v1/2024.emnlp-main.813](https://doi.org/10.18653/v1/2024.emnlp-main.813) · ACL Anthology · Scopus-indexed · 41 citations

### Problem
Two failure modes of retrieval-augmented LMs. First, *"the reliability of the retrieved information is not always guaranteed, and the retrieval of irrelevant data can mislead the response generation."* Second, *"standard RALMs frequently neglect their intrinsic knowledge due to the interference from retrieved information."* The desired behaviour: fall back on intrinsic knowledge when retrieval is poor, and *"in the absence of both intrinsic and retrieved knowledge, opt to respond with 'unknown' to avoid hallucination."*

### Methodology
**CHAIN-OF-NOTE (CON)** generates *"sequential reading notes for each retrieved document,"* assessing each document's relevance to the question before integrating anything into an answer. Evaluated in two modes: prompting GPT-4 with CON, and distilling — *"we utilized GPT-4 to create 10K CON data, subsequently trained on LLaMa-2 7B model."*

### Advantages
- **Explicit refusal capability** — the system can say "unknown" rather than fabricate. Rare and valuable.
- GPT-4 with CON outperforms chain-of-thought prompting.
- Distillation works: fine-tuned RALMs with CON *"significantly outperform standard fine-tuned RALMs"* across four ODQA benchmarks.
- Per-document notes are inherently interpretable — you can see why a document was used or discarded.

### Disadvantages
- **One generation pass per retrieved document** — with top-12 chunks per sub-question this is a severe cost multiplier, and under a rate-limited free tier it is close to prohibitive.
- Distillation needs GPT-4 access to build training data.
- Four benchmarks referenced but **not named in the abstract**.
- Note quality is unverified — the notes are themselves LLM output.

### Dataset(s)
Four open-domain QA benchmarks (**not named in abstract**); 10K GPT-4-generated CON training set; LLaMa-2 7B base model.

### Relevance to ResearchGPT
**The intellectual precedent for your hallucination stress test** (`PROJECT_PLAN.md §9.5`). Your planned demo — query an uncovered topic and show the system refuses rather than invents — is CON's core contribution, and citing it means you are implementing a published behaviour rather than improvising a demo trick.

But read it as a **warning too**. Per-document note generation is what your Extractor already does per *paper*; doing it per *chunk* would multiply your API calls past your rate budget. The design lesson is that CON buys robustness with generation calls, and you cannot afford that currency. Your equivalent is the **local NLF verifier** — same goal (filter unreliable retrieved content), radically cheaper mechanism. That contrast is worth a paragraph in your Design chapter: it shows you understood the technique and chose a cost-appropriate substitute.

---

## 07 · Jeong et al. (2024) — Self-BioRAG

**Citation.** Jeong, M., Sohn, J., Sung, M., & Kang, J. (2024). "Improving medical reasoning through retrieval and self-reflection with retrieval-augmented large language models." *Bioinformatics*, 40(Suppl 1).
**DOI.** [10.1093/bioinformatics/btae238](https://doi.org/10.1093/bioinformatics/btae238) · Oxford University Press · Scopus-indexed Q1 · 115 citations

### Problem
Generic RAG methods generalise poorly to specialist domains: *"when applying existing methods to different domain-specific problems, poor generalization becomes apparent, leading to fetching incorrect documents or making inaccurate judgments."*

### Methodology
**Self-BioRAG** combines three capabilities — generating explanations, retrieving domain-specific documents, and **self-reflecting on generated responses**. Trained on *"84k filtered biomedical instruction sets"* so the model *"can assess its generated explanations with customized reflective tokens."* Reflection is thus a learned, in-model behaviour expressed through special tokens, not an external checking step. Model weights (7B and 13B), data and code released.

### Advantages
- **+7.2% absolute average improvement** over the state-of-the-art open foundation model at ≤7B parameters.
- **+8% ROUGE-1 over RAG** on two long-form QA benchmarks — notable because long-form generation is closer to review writing than multiple-choice QA.
- Full artefact release (7B and 13B weights, data, code) — strong reproducibility.
- Demonstrates that *domain-specific* retriever + corpus + instructions are jointly necessary, an empirically supported architectural claim.

### Disadvantages
- **Requires 84k domain instruction sets** — you have nothing comparable for CS literature and cannot construct it at $0.
- Biomedical only; transfer to CS is untested.
- Self-reflection is *internal* to the model, so its judgements cannot be independently audited — a real weakness if grounding must be demonstrable.
- 7B inference is impractical on your CPU-only machine (`PROJECT_PLAN.md §6.3`).

### Dataset(s)
84k filtered biomedical instruction sets (training); three major medical QA benchmarks and two long-form QA benchmarks (**not named in abstract**).

### Relevance to ResearchGPT
Two uses, one of them a caution.

**As support:** it is peer-reviewed evidence in a Q1 journal that self-reflection improves retrieval-augmented generation, and that the gain holds for *long-form* output. Your Critic and Verifier rest on that premise.

**As a caution — and this is the more important reading:** Self-BioRAG bakes reflection *into the model* via 84k domain instructions. You cannot do that. Your architecture externalises the same function into a separate, independently-trained verifier. That is a defensible and arguably better design — an external verifier can be **audited, ablated, and reported on**, whereas reflective tokens cannot be separated from the generator. Make that argument explicitly; it converts a constraint into a design rationale, and it directly supports keeping ablation 2 (− Verifier) as your headline experiment.

---

## 08 · Li et al. (2025) — Evidence-Aware RAG via Self-Corrective Chain-of-Thought

**Citation.** Li, Y., Ke, W., Liu, J., Wang, P., Liu, J., & He, Y. (2025). "Towards evidence-aware retrieval-augmented generation via self-corrective chain-of-thought." *Information Processing & Management*.
**DOI.** [10.1016/j.ipm.2025.104369](https://doi.org/10.1016/j.ipm.2025.104369) · Elsevier · Scopus-indexed Q1 · 10 citations · 43 references

### ⚠️ Verification status — read before citing
The **bibliographic record is fully verified**: DOI resolves, title, six authors, journal and reference count confirmed in both OpenAlex and Semantic Scholar. But **the abstract is absent from OpenAlex, Crossref and Semantic Scholar**, and ScienceDirect returns HTTP 403 to automated access. Everything below is inferred **from the title alone**.

There is also a **year discrepancy**: OpenAlex records 2025, Semantic Scholar records 2026. Resolve this before it enters your reference list.

### Problem *(inferred from title — unverified)*
RAG systems are not "evidence-aware" — they generate without tracking whether retrieved evidence actually supports each reasoning step, allowing errors to propagate through a chain of thought.

### Methodology *(inferred from title — unverified)*
A self-corrective chain-of-thought mechanism that detects and repairs unsupported reasoning steps against retrieved evidence.

### Advantages
- *Information Processing & Management* is a **top-tier Q1 IR journal** — high venue authority.
- Recent, with 43 references, suggesting substantial engagement with related work.
- Topically the closest journal paper to your Critic loop.

### Disadvantages
- **Content unverifiable through open channels.** No abstract available anywhere I could reach.
- Year ambiguity across indexes.
- Only 10 citations.

### Dataset(s)
**Not determinable** without access to the paper.

### Relevance to ResearchGPT
Potentially high — "evidence-aware" and "self-corrective" describe your Verifier and Critic almost exactly, and a Q1 IR journal citation would strengthen your Related Work. **But do not cite it on the strength of its title.** Get the PDF through your institution's library access, read it, and then write this entry properly. If it turns out to be very close to your design, that is important for you to know early — it may be a competitor you must differentiate from, not just a supporting citation. **This is the one action item in this document that only you can complete.**

---

## 09 · Ammann, Golde & Akbik (2025) — Question Decomposition for RAG

**Citation.** Ammann, P., Golde, J., & Akbik, A. (2025). "Question Decomposition for Retrieval-Augmented Generation." *Proceedings of the 63rd Annual Meeting of the ACL: Student Research Workshop*.
**DOI.** [10.18653/v1/2025.acl-srw.32](https://doi.org/10.18653/v1/2025.acl-srw.32) · ACL Anthology · Scopus-indexed · 9 citations

### Problem
Multi-hop questions defeat standard RAG because *"relevant facts are often distributed across multiple documents rather than co-occurring in one source, making it difficult for standard RAG to retrieve sufficient information."* Semantic similarity to the *whole* question retrieves no single passage that answers it.

### Methodology
A three-stage pipeline: **(i)** an LLM decomposes the original query into sub-questions; **(ii)** passages are retrieved for each sub-question independently; **(iii)** *"the merged candidate pool is reranked to improve the coverage and precision of the retrieved evidence."* The authors are careful about their own novelty: *"Although reranking itself is standard, we show that pairing an off-the-shelf cross-encoder reranker with LLM-driven question decomposition bridges the retrieval gap on multi-hop questions and provides a practical, drop-in enhancement, without any extra training or specialized indexing."*

### Advantages
- **MRR@10 +36.7%** retrieval improvement and **F1 +11.6%** answer accuracy over standard RAG baselines.
- **No training and no specialised indexing** — an off-the-shelf cross-encoder, exactly your setup.
- Evaluated on two named public benchmarks, so the numbers are reproducible and comparable.
- Unusually honest about which part is novel.

### Disadvantages
- **Student Research Workshop** — lighter peer review than a main conference track, and only 9 citations.
- Decomposition quality bounds everything downstream; no analysis of failure cases in the abstract.
- One LLM call per query added, plus reranking over a larger merged pool.
- Multi-hop QA, not long-form synthesis.

### Dataset(s)
**MultiHop-RAG** and **HotpotQA** — both public and named.

### Relevance to ResearchGPT
**Your closest methodological relative in this entire set — treat it as a baseline, not just a citation.**

Their pipeline *is* your Planner + Retriever: LLM decomposes into sub-questions → per-sub-question retrieval → cross-encoder rerank of the merged pool. `RESEARCHGPT_SPEC.md §7.2` step 5 describes the same merge-and-rerank operation. And they achieve it *"without any extra training or specialized indexing"* — the precise constraint set you operate under.

Three concrete consequences:

1. **You have a published expected effect size.** +36.7% MRR@10 from decomposition + reranking. If your Phase 2 retrieval evaluation shows a far smaller gain, you have a bug, not a finding. This is a free sanity check for Day 5.
2. **It bounds your novelty claim, usefully.** Query decomposition plus reranking is now published and quantified. Your contribution is *not* decomposition — it is what happens after: structured extraction, claim verification, and the critic loop. Being precise about this makes your contribution claims more credible, not less.
3. **It is the ideal ablation-4 baseline.** Your "vanilla RAG" comparison would be stronger as "decomposition + rerank, no verification, no loop" — a genuinely competitive published configuration rather than a strawman.

---

# C3 — MULTI-AGENT LLM SYSTEMS

## 10 · Qian et al. (2024) — ChatDev

**Citation.** Qian, C., Liu, W., Liu, H., Chen, N., Dang, Y., Li, J., Yang, C., Chen, W., Su, Y., Cong, X., Xu, J., Li, D., Liu, Z., & Sun, M. (2024). "ChatDev: Communicative Agents for Software Development." *Proceedings of ACL 2024 (Long Papers)*.
**DOI.** [10.18653/v1/2024.acl-long.810](https://doi.org/10.18653/v1/2024.acl-long.810) · ACL Anthology · Scopus-indexed · 279 citations (OpenAlex) / 1,043 (Semantic Scholar)
*(Abstract from Semantic Scholar; OpenAlex holds a citation stub.)*

### Problem
Multi-stage workflows handled by phase-specific models fragment: *"the deep learning model in each phase requires unique designs, leading to technical inconsistencies across various phases, which results in a fragmented and ineffective development process."* The problem is **inconsistency across specialised stages** — which is precisely the risk in any six-agent pipeline, including yours.

### Methodology
**ChatDev** is a chat-powered framework in which *"specialized agents driven by large language models (LLMs) are guided in what to communicate (via chat chain) and how to communicate (via communicative dehallucination)."* Two named mechanisms: the **chat chain** structures the sequence of agent interactions; **communicative dehallucination** addresses hallucination arising in inter-agent communication. Agents span design, coding and testing, deriving solutions through multi-turn dialogue. Notably, the authors report that natural language suits system design while programming language suits debugging — the communication medium should match the sub-task. Code and data released.

### Advantages
- The canonical peer-reviewed demonstration that **role specialisation with structured communication** outperforms monolithic prompting.
- **"Communicative dehallucination"** explicitly recognises that multi-agent systems create *new* hallucination surfaces at the interfaces — a failure mode most multi-agent papers ignore.
- ACL long paper with very high citation count.
- Unified language-based communication solves the technical-inconsistency problem it identifies.

### Disadvantages
- **Software engineering domain** — no retrieval, no external evidence grounding, no citation requirements.
- Multi-turn dialogue between agents is token-expensive; the abstract reports no cost analysis.
- Correctness in software has an oracle (does it run?) that literature review lacks — the evaluation story does not transfer.
- No ablation in the abstract isolating chat chain vs. dehallucination.

### Dataset(s)
**None named** — evaluated on software development tasks.

### Relevance to ResearchGPT
**Your primary citation for the claim that role decomposition works**, and the answer to the "why not just one big prompt?" question. Its 1,000+ citations make it hard to dismiss.

The more valuable transfer is **communicative dehallucination**. ChatDev found that multi-agent systems introduce hallucination *at agent boundaries* — one agent's imprecise output becomes another's confident input. Your pipeline has five such handoffs (Planner→Retriever→Extractor→Verifier→Critic→Writer), and errors compound along them. `RESEARCHGPT_SPEC.md` addresses grounding of the *final output* but does not address inter-agent drift. Two things follow:

- Your **Verifier partly mitigates this by construction** — it re-grounds Extractor output against source chunks, breaking the drift chain mid-pipeline. Say so; it is a design strength you have not yet claimed.
- Your **trace log** (`trace.jsonl`) is the instrument for observing it. If you log per-agent input/output hashes as the spec requires, you can *measure* boundary drift, which would be a genuinely interesting minor finding.

Cite ChatDev's domain limitation honestly: software has a correctness oracle, literature review does not, and that is why your evaluation is harder than theirs.

---

## 11 · Li et al. (2024) — Survey on LLM-Based Multi-Agent Systems

**Citation.** Li, X., Wang, S., Zeng, S., Wu, Y., & Yang, Y. (2024). "A survey on LLM-based multi-agent systems: workflow, infrastructure, and challenges." *Vicinagearth*, 1(1).
**DOI.** [10.1007/s44336-024-00009-2](https://doi.org/10.1007/s44336-024-00009-2) · Springer Nature · 307 citations · **254 references**

### Problem
LLM-based multi-agent systems have proliferated without a unifying account, making it hard to compare architectures or identify what is actually novel in any given system.

### Methodology
Systematic survey synthesising *"a general structure encompassing five key components: profile, perception, self-action, mutual interaction, and evolution."* Organised around MAS workflow, and covering two application areas — problem-solving and world simulation — before discussing challenges and future directions. 254 references.

### Advantages
- **Five-component framework** gives you standard vocabulary for describing your agents.
- 254 references — genuinely comprehensive coverage.
- 307 citations despite the young venue, indicating the framework is being adopted.
- The problem-solving vs. world-simulation split is a clean way to locate your system (firmly problem-solving).

### Disadvantages
- **Young, low-profile venue** (*Vicinagearth*, launched 2024) — verify its Scopus indexing status before relying on it in a Scopus-constrained bibliography. This is the one paper in the set where venue standing is genuinely uncertain.
- Survey — no evaluation or empirical comparison.
- The five components are descriptive rather than prescriptive; they classify systems without predicting which designs work.
- General MAS framing, no document- or retrieval-specific content.

### Dataset(s)
**None** — survey.

### Relevance to ResearchGPT
Use it to **describe your architecture in the field's own vocabulary**. Mapping your six agents onto profile / perception / self-action / mutual interaction / evolution makes your System Design chapter legible to a multi-agent reviewer and demonstrates you know the literature's framing rather than inventing private terminology.

The mapping is also **diagnostically useful**. Four of the five components map cleanly onto your system; **"evolution" does not** — your agents do not learn or adapt across runs. Rather than hiding that, name it: your system's adaptation is *within-run* (the Critic loop) rather than *across-run*, and cross-run evolution is Future Work. Reviewers respect a system that knows what it is not.

⚠️ **Check the venue.** If *Vicinagearth* is not Scopus-indexed, substitute Wang et al. (2024), *Frontiers of Computer Science*, [10.1007/s11704-024-40231-1](https://doi.org/10.1007/s11704-024-40231-1) — 1,320 citations, established venue, from the reserve pool in `LITERATURE_REVIEW.md §6`.

---

## 12 · Yang et al. (2025) — AutoHMA-LLM

**Citation.** Yang, T., Feng, P., Guo, Q., Zhang, J., Zhang, X., Ning, J., Wang, X., & Mao, Z. (2025). "AutoHMA-LLM: Efficient Task Coordination and Execution in Heterogeneous Multi-Agent Systems Using Hybrid Large Language Models." *IEEE Transactions on Cognitive Communications and Networking*.
**DOI.** [10.1109/tccn.2025.3528892](https://doi.org/10.1109/tccn.2025.3528892) · IEEE · Scopus-indexed Q1 · 38 citations

### Problem
Coordinating heterogeneous agents with specialised functions is expensive and unstable in *"complex, dynamic environments"* — the coordination overhead itself becomes the bottleneck.

### Methodology
A **multi-tier hybrid architecture**: *"a cloud-based LLM as the central planner alongside device-specific LLMs and Generative Agents."* Combines LLMs with classical control algorithms rather than replacing them. Improves execution through *"refined task scheduling and real-time feedback mechanisms."* Evaluated across logistics, inspection, and search & rescue scenarios.

### Advantages
- **Reports the efficiency numbers most multi-agent papers omit**: +5.7% task completion accuracy, **−46% communication steps**, **−31% token usage and API calls** versus baselines.
- The **tiered model assignment** — a strong central planner plus smaller device-level models — is a validated cost-control pattern.
- Hybrid LLM + classical control shows agents need not do everything.
- IEEE Q1 journal.

### Disadvantages
- **Robotics/IoT domain** — physical task coordination, not document synthesis. The transfer is architectural only.
- Requires cloud LLM access for the central planner.
- Scenario-based evaluation with no public benchmark, so results are not independently comparable.
- "Heterogeneous" means heterogeneous *hardware*, whereas your agents are heterogeneous in *role* — a weaker analogy than it first appears.

### Relevance to ResearchGPT
This is your **defence against the strongest objection to your architecture**: *"six agents is over-engineering — what does it cost?"* Every multi-agent paper claims capability gains; almost none reports overhead. AutoHMA-LLM reports both, and shows a well-designed multi-agent system can *reduce* token usage and API calls (−31%) rather than inflate them, by routing work to appropriately-sized models.

That is **exactly your architecture** (`PROJECT_PLAN.md §6.1`): frontier free-tier model for Planner and Critic, small model for high-volume extraction, local CPU models for embedding, reranking and verification. AutoHMA-LLM is peer-reviewed evidence that tiered assignment is a recognised efficiency pattern, not a budget compromise.

Concretely: report your own token/request counts from `trace.jsonl` alongside theirs. Having a published comparison point turns your cost table from a footnote into a result.

### Dataset(s)
Logistics, inspection, and search & rescue scenarios — **no public dataset**.

---

# C4 — SCIENTIFIC DOCUMENT UNDERSTANDING & IE

## 13 · Dagdelen et al. (2024) — Structured Information Extraction from Scientific Text

**Citation.** Dagdelen, J., Dunn, A., Lee, S., Walker, N., Rosen, A. S., Ceder, G., Persson, K. A., & Jain, A. (2024). "Structured information extraction from scientific text with large language models." *Nature Communications*, 15.
**DOI.** [10.1038/s41467-024-45563-x](https://doi.org/10.1038/s41467-024-45563-x) · Nature Portfolio · Scopus-indexed Q1 · **645 citations**

### Problem
*"Extracting structured knowledge from scientific text remains a challenging task for machine learning models."* Scientific facts are expressed in prose that resists conversion into database records.

### Methodology
Joint **named entity recognition and relation extraction** by fine-tuning pretrained LLMs (**GPT-3, Llama-2**). Three representative materials-chemistry tasks: linking dopants and host materials, cataloguing metal-organic frameworks, and general composition/phase/morphology/application extraction. Records extracted from *"single sentences or entire paragraphs,"* with output *"as simple English sentences or a more structured format such as a list of JSON objects."*

### Advantages
- **Direct precedent for LLM-generated structured JSON records from scientific text** — the core mechanism of your Extractor.
- *Nature Communications*, 645 citations — very high authority.
- Deliberately simple and flexible: *"a simple, accessible, and highly flexible route."*
- Handles both sentence- and paragraph-level extraction, matching your chunk granularity.
- Demonstrated across three distinct schemas, showing schema-generality.

### Disadvantages
- **Requires fine-tuning** — you use prompting with a free-tier model, so their reliability figures do not transfer.
- Materials chemistry, where entities are far more standardised than the concepts your four-field schema targets (methodology, advantages, disadvantages, critique are interpretive, not nominal).
- **No evidence-span or provenance mechanism** — extracts records without linking them back to source text, which is the central requirement of your design.
- Their entities are objective; your fields require judgement, so extraction reliability will be lower.

### Dataset(s)
Three materials-chemistry tasks: dopant–host linking, metal-organic framework cataloguing, composition/phase/morphology/application extraction. Domain corpora **not named** in the abstract.

### Relevance to ResearchGPT
**Your strongest citation for the four-field extraction schema.** It establishes structured-JSON extraction from scientific papers as a validated technique in a Nature-family venue, so your schema is an application of accepted method rather than an invention you must defend from scratch.

But be precise about the difference, because a careful reviewer will press on it. Dagdelen et al. extract **objective, nominal** entities — a dopant is or is not present. Your schema extracts **interpretive** content: "disadvantages" and "critique" are judgements, not facts on the page. Expect materially lower agreement, and set your Extraction F1 expectations accordingly (`PROJECT_PLAN.md §9`). Saying this yourself is far stronger than having it pointed out.

The gap they leave is also your opening: **they have no evidence-span mechanism.** Your `evidence_spans` requirement — every field traceable to `chunk_id` + character offsets — is a genuine addition, and paper 15 below shows why it matters.

---

## 14 · Sarol et al. (2024) — Assessing Citation Integrity in Biomedical Publications

**Citation.** Sarol, M. J., Ming, S., Radhakrishna, S., Schneider, J., & Kilicoglu, H. (2024). "Assessing citation integrity in biomedical publications: corpus annotation and NLP models." *Bioinformatics*, 40(7).
**DOI.** [10.1093/bioinformatics/btae420](https://doi.org/10.1093/bioinformatics/btae420) · Oxford University Press · Scopus-indexed Q1 · 8 citations

### Problem
**Quotation errors** — *"errors in citation content that can distort the scientific evidence and that are hard to detect for humans."* A citation may point to a real paper that does not support the claim made. This is exactly the failure your Verifier exists to catch, and note the phrasing: *hard to detect for humans*.

### Methodology
Two contributions. **Corpus:** manual annotation of 100 highly-cited biomedical publications and citations to them, labelling *"citation context in the citing article, relevant evidence sentences in the reference article, and the accuracy of the citation."* **3,063 citation instances annotated, of which 39.18% contained accuracy errors.**

**Models:** a sentence retriever combined with a fine-tuned claim-verification model, labelling each citation `ACCURATE` / `NOT_ACCURATE` / `IRRELEVANT`. The best configuration used *"citation sentences as citation context, the BM25 model with MonoT5 reranker for retrieving top-20 sentences, and a fine-tuned MultiVerS model for accuracy label classification."* Few-shot GPT-4 in-context learning tested as an alternative. Corpus and best model released publicly.

### Advantages
- **Architecturally near-identical to your Verifier**: sparse retrieval → neural reranking → fine-tuned claim-verification classifier → three-way label.
- **Rigorously honest reporting.** Best model: **0.59 micro-F1 / 0.52 macro-F1**. GPT-4 ICL: 0.65 micro-F1 / 0.45 macro-F1 — better on accurate citations, worse on erroneous ones.
- The **39.18% error rate** in real published citations is a striking, quotable motivation.
- Public corpus and model.
- Explicit conclusion that the task remains unsolved: *"it is currently challenging for NLP models to identify erroneous citations."*

### Disadvantages
- **Performance is low in absolute terms** — 0.59 micro-F1 is not deployable as an autonomous filter.
- Biomedical domain; MultiVerS is biomedically pretrained.
- Corpus is modest (100 reference articles).
- Requires fine-tuning and a MonoT5 reranker — heavier than your CPU budget comfortably allows.

### Dataset(s)
Own annotated corpus: **100 highly-cited biomedical publications, 3,063 annotated citation instances (39.18% erroneous)**. Public at `github.com/ScienceNLP-Lab/Citation-Integrity/`.

### Relevance to ResearchGPT
**The single most important calibration reference in this document.** Read it before you set any verifier target.

This is a careful, well-resourced, peer-reviewed attempt at your Verifier's exact task — sparse retrieval, neural reranking, a *fine-tuned* domain-appropriate claim-verification model — and it reaches **0.59 micro-F1**. Your plan (`PROJECT_PLAN.md §9`) targets groundedness ≥ 0.9. Those numbers measure related but different things, and the mismatch is a trap:

- If your verifier reports ~0.9 **against real citations in your own output**, the most likely explanation is a measurement artefact, not a breakthrough. Sarol et al. give you the prior to be suspicious with.
- Your 0.9 target is defensible only as *"fraction of output sentences carrying at least one supporting span,"* which measures whether the filter ran — the circularity trap flagged in `PROJECT_PLAN.md §9.6`. **Verifier precision measured against human judgement is the number that matters, and Sarol et al. tell you what good looks like there.**

Two further uses. The **39.18% error rate** is your Introduction's opening statistic — nearly two in five citations in highly-cited biomedical papers misrepresent their source, which motivates the entire project in one sentence. And their finding that **GPT-4 in-context learning was worse at detecting erroneous citations** is direct evidence for training a dedicated verifier instead of prompting an LLM — precisely the choice in `PROJECT_PLAN.md §4.2`.

---

## 15 · Li, Lee & Ouyang (2024) — Cited Text Spans for Scientific Citation Text Generation

**Citation.** Li, X., Lee, Y., & Ouyang, J. (2024). "Cited Text Spans for Scientific Citation Text Generation." *Proceedings of the 4th Workshop on Scholarly Document Processing (SDP) @ ACL 2024*.
**DOI.** [10.18653/v1/2024.sdp-1.9](https://doi.org/10.18653/v1/2024.sdp-1.9) · ACL Anthology · Scopus-indexed · 3 citations

### Problem
Citation generation systems must *"ground [their] outputs to the content of the cited paper to avoid nonfactual hallucinations,"* but because scientific documents are long, *"existing abstractive approaches have conditioned only on cited paper abstracts."* The paper's central empirical claim: **that shortcut teaches hallucination.**

### Methodology
Proposes conditioning on the **cited text span (CTS)** — the specific passage in the cited paper being referred to — instead of the abstract. Since manual CTS annotation is *"extremely time- and labor-intensive,"* they use **distant labelling** of candidate CTS sentences, and report it performs well enough *"to substitute for expensive human annotations in model training."* Adds a **human-in-the-loop, keyword-based CTS retrieval** approach for practical deployment.

### Advantages
- **Empirically demonstrates that abstract-only conditioning causes hallucination** — not asserted, shown.
- Distant labelling removes the annotation bottleneck, making the approach practical.
- Human-in-the-loop retrieval is realistic about deployment.
- Directly addresses grounding *granularity*, a question most work skips.

### Disadvantages
- **Workshop paper**, 3 citations — lightest peer review in this set.
- Distant labels are inherently noisy.
- Human-in-the-loop conflicts with full automation.
- OpenAlex's stored abstract has **fragments of body text appended** ("Automatic summary generation has been Traditional data-to-text generation approaches Related Work…"), indicating an imperfect extraction — read the PDF before quoting.

### Dataset(s)
CTS-annotated data with distant labelling; specific corpora **not named in the abstract**.

### Relevance to ResearchGPT
**The direct empirical justification for your `evidence_spans` design** — and, importantly, a warning about one of your own fallbacks.

`RESEARCHGPT_SPEC.md §7.3` requires every extracted field to carry `evidence_spans` with chunk ID and character offsets, i.e. grounding at span rather than document granularity. This paper shows *why*: models conditioned on abstracts alone **learn to hallucinate**. That is a stronger argument than "spans are more precise."

**But it also undercuts a fallback you have planned.** `PROJECT_PLAN.md §11` proposes an abstract-only degraded mode for paywalled papers. Li et al. is evidence that abstract-only conditioning is not merely *less precise* but *actively induces hallucination*. Since your graded criterion is not hallucinating, this matters. Three options, in order of preference:

1. **Restrict abstract-only papers to citation-level support** — they can be cited as existing, but cannot supply verified claims.
2. **Flag them** in `insights.csv` via `text_availability` and report the split, as the plan already suggests.
3. **Exclude them** from the write path entirely.

Whichever you choose, cite this paper as the reason. It converts an awkward limitation into an evidence-based design decision — and note the tension with your base paper's "Abstract First" finding, which is worth a sentence in Discussion: abstracts may be good for *retrieval* while being poor for *grounding*.

---

# C5 — AUTOMATED SURVEY & REVIEW GENERATION

## 16 · Kasanishi et al. (2023) — SciReviewGen

**Citation.** Kasanishi, T., Isonuma, M., Mori, J., & Sakata, I. (2023). "SciReviewGen: A Large-scale Dataset for Automatic Literature Review Generation." *Findings of ACL 2023*.
**DOI.** [10.18653/v1/2023.findings-acl.418](https://doi.org/10.18653/v1/2023.findings-acl.418) · ACL Anthology · Scopus-indexed · 71 references

### Problem
*"Automatic literature review generation is one of the most challenging tasks in natural language processing."* Progress was blocked by data: *"the absence of large-scale datasets has been a stumbling block to the progress."*

### Methodology
Releases **SciReviewGen: over 10,000 literature reviews and 690,000 cited papers**, constructed from S2ORC. Benchmarks transformer-based summarisation models, *"including Fusion-in-Decoder extended for literature review generation"* (QFiD). Human evaluation compares machine output against human-written reviews.

### Advantages
- **The field's reference dataset** for this exact task.
- Scale (10k reviews / 690k cited papers) enables data-driven work.
- Chapter-level structure with `bib_titles`, `bib_abstracts` and `bib_citing_sentences` gives free query→gold-paper mappings.
- **Honest headline finding**: some machine summaries are comparable to human reviews, *"while revealing the challenges of automatic literature review generation such as hallucinations and a lack of detailed information."*
- Public dataset and code.

### Disadvantages
- **CC BY-NC 4.0** — non-commercial only, inherited from S2ORC.
- **Frozen at the S2ORC 2020-07-05 snapshot** — unusable as a live source and blind to everything since.
- Requires S2ORC access, which historically involves a multi-day AI2 request.
- QFiD is a fine-tuned summariser — a different paradigm from prompted agents.
- Notably low OpenAlex citation count for a dataset paper; verify against another index if citation count matters to your framing.

### Dataset(s)
**SciReviewGen** (own): 10,000+ reviews, 690,000 cited papers, derived from **S2ORC**.

### Relevance to ResearchGPT
Three specific uses, already analysed in `PROJECT_PLAN.md §5.3`:

1. **Retrieval gold sets** — chapter topic as query, its cited papers as the gold relevant set, giving Recall@k at scale without hand-curation. Static data, so it satisfies your "no live API in CI" rule for free.
2. **Verifier cross-check** — `bib_citing_sentences` are human-authored claim→paper pairs, giving you an *independent* check on your Verifier that breaks the circularity trap (`PROJECT_PLAN.md §9.6`).
3. **Motivation** — the authors identify **hallucination** as a central obstacle. Your Verifier targets the obstacle the field's own dataset paper names.

Its stated limitations are your opening: hallucination and lack of detail are what claim verification and structured four-field extraction address. Cite it in both Introduction (problem) and Evaluation (data).

---

## 17 · Bao et al. (2025) — SurveyGen / QUAL-SG ★ RECOMMENDED BASE PAPER

**Citation.** Bao, T., Nayeem, M. T., Rafiei, D., & Zhang, C. (2025). "SurveyGen: Quality-Aware Scientific Survey Generation with Large Language Models." *Proceedings of EMNLP 2025 (Main)*.
**DOI.** [10.18653/v1/2025.emnlp-main.136](https://doi.org/10.18653/v1/2025.emnlp-main.136) · ACL Anthology · Scopus-indexed · EMNLP main track

### Problem
*"While large language models (LLMs) have shown promise in generating survey texts, the lack of standardized evaluation datasets critically hampers rigorous assessment of their performance against human-written surveys."* An evaluation problem first, a generation problem second.

### Methodology
**Dataset:** SurveyGen — *"over 4,200 human-written surveys across diverse scientific domains, along with 242,143 cited references and extensive quality-related metadata for both the surveys and the cited papers."*

**System:** **QUAL-SG**, a *"quality-aware framework for survey generation that enhances the standard Retrieval-Augmented Generation (RAG) pipeline by incorporating quality-aware indicators into literature retrieval to assess and select higher-quality source papers."*

**Study design:** evaluates state-of-the-art LLMs *"under varying levels of human involvement — from fully automatic generation to human-guided writing,"* with human evaluation.

### Advantages
- **Exact task match** — scientific survey generation.
- Quality-aware retrieval is a peer-reviewed instance of your venue-tier ranking (`RESEARCHGPT_SPEC.md §11`), giving you a directly comparable component.
- The human-involvement gradient is a sophisticated design that reveals *where* automation fails, not just that it does.
- Large, recent dataset with quality metadata.
- EMNLP main track.

### Disadvantages
- Recent, so few citations yet.
- Quality indicators are bibliometric proxies (venue, citations), which correlate imperfectly with relevance.
- Semi-automatic pipelines only *"achieve partially competitive outcomes"* — a sober result.
- Abstract does not specify which quality indicators are used.

### Dataset(s)
**SurveyGen** (own): 4,200+ human-written surveys, 242,143 cited references, with quality metadata.

### Relevance to ResearchGPT
**This should be your base paper.** The argument, from `LITERATURE_REVIEW.md §2`, in short:

The single most valuable sentence in this entire document is their conclusion: **"fully automatic survey generation still suffers from low citation quality and limited critical analysis."**

That is your problem statement, written by the authors of the paper you are extending. You do not have to argue a gap exists — you cite them stating it. Then:

- **"Low citation quality"** → your Verifier, which removes claims lacking supporting spans.
- **"Limited critical analysis"** → your four-field extraction schema, which forces per-paper *disadvantages* and *critique* rather than neutral summary.

That is the cleanest extension narrative available to you, and it is far stronger than the Aytar route, which requires arguing across a task boundary (data-science retrieval → literature review) while also correcting your spec's mischaracterisation of it.

Additional advantages: QUAL-SG's quality-aware retrieval gives you a **published baseline for venue-tier ranking**, so ablating it becomes a comparison rather than a self-referential exercise. And their dataset provides evaluation material with the same provenance as your base paper.

**Action:** update `RESEARCHGPT_SPEC.md §1.2–§1.3` to make SurveyGen the base paper, keeping Aytar et al. as related work.

---

## 18 · Funkquist et al. (2023) — CiteBench

**Citation.** Funkquist, M., Kuznetsov, I., Hou, Y., & Gurevych, I. (2023). "CiteBench: A Benchmark for Scientific Citation Text Generation." *Proceedings of EMNLP 2023*.
**DOI.** [10.18653/v1/2023.emnlp-main.455](https://doi.org/10.18653/v1/2023.emnlp-main.455) · ACL Anthology · Scopus-indexed · UKP Lab, TU Darmstadt

### Problem
*"Existing studies are based upon widely diverging task definitions, which makes it hard to study this task systematically."* Citation text generation research cannot accumulate because every paper defines the task differently.

### Methodology
**CiteBench** unifies multiple diverse datasets into one benchmark *"and enables standardized evaluation of citation text generation models across task designs and domains."* Evaluates multiple strong baselines and **tests transferability between datasets** — whether a model trained on one citation-generation dataset works on another. Public code.

### Advantages
- Solves a real fragmentation problem with a standard.
- **Cross-dataset transferability testing** is methodologically rigorous and rarely done.
- Frames citation generation as a window onto *"how humans aggregate and synthesize textual knowledge from sources"* — a useful conceptual framing for your Writer.
- UKP Lab; EMNLP main; public code.

### Disadvantages
- **Citation text generation ≠ full review generation.** A citation sentence is a much smaller unit than a survey chapter.
- Constituent datasets **not individually named** in the abstract.
- Pre-dates the current LLM generation; baselines are dated.
- Low OpenAlex citation count.

### Dataset(s)
Multiple unified datasets — **not individually named in the abstract.** Check the paper before listing them.

### Relevance to ResearchGPT
Two uses.

**Methodological cover for your evaluation design.** You are inventing metrics for a task without settled standards. CiteBench lets you say the field acknowledges this fragmentation and has begun standardising, so your evaluation choices are a considered position rather than an ad-hoc invention.

**A warning about transferability.** Their finding that models transfer poorly across citation-generation datasets predicts something for you: **your system tuned on your own 25-paper bibliography (`PROJECT_PLAN.md §5.2`) may not transfer to SciReviewGen gold sets.** Do not treat a discrepancy between those two evaluations as a bug — it is an expected, publishable finding, and CiteBench is the citation that makes it expected rather than embarrassing.

---

## 19 · Bolaños et al. (2024) — AI for Literature Reviews

**Citation.** Bolaños, F. J., Salatino, A. A., Osborne, F., & Motta, E. (2024). "Artificial intelligence for literature reviews: opportunities and challenges." *Artificial Intelligence Review*, 57.
**DOI.** [10.1007/s10462-024-10902-3](https://doi.org/10.1007/s10462-024-10902-3) · Springer · Scopus-indexed Q1 · 206 citations · 167 references

### Problem
AI-assisted systematic literature review tooling has proliferated with no systematic map of what exists, what each tool does, or how they compare.

### Methodology
Reviews **21 leading SLR tools** using a framework combining **23 traditional features with 11 AI features**, focused on the screening and extraction phases. Separately analyses **11 recent LLM-based tools** for literature search and academic writing. Identifies three primary research challenges and proposes evaluation best practices.

### Advantages
- **Maps the actual competitive landscape** — 21 real tools, not just papers.
- The 23+11 feature framework is a **ready-made comparison instrument**: you can position ResearchGPT against real systems feature by feature.
- Names three challenges that are almost a specification for your project: *"integrating advanced AI solutions, such as large language models and knowledge graphs, improving usability, and developing a standardised evaluation framework."*
- Proposes evaluation best practices for *"performance, usability, and transparency."*
- 206 citations, 167 references, Q1 journal.

### Disadvantages
- Tool review — no system, no benchmarking, no head-to-head performance data.
- Tool landscapes date quickly.
- Focused on screening and extraction, lighter on synthesis and writing — the harder half of your problem.
- SLR-centric (healthcare-inflected methodology) rather than CS narrative reviews.

### Dataset(s)
**None** — review of 21 SLR tools plus 11 LLM-based tools.

### Relevance to ResearchGPT
**Your Related Work chapter's backbone, and your defence against "does this already exist?"**

Every project of this kind faces the question of whether commercial tools (Elicit, Rayyan, ASReview) already solve the problem. This paper lets you answer with a peer-reviewed feature-level comparison instead of an opinion. Build a table placing ResearchGPT in their 23+11 framework — it will show concretely that existing tools cluster on **screening and extraction** while yours targets **verified synthesis**.

Their three named challenges are also a gift for your Introduction: two of them (integrating LLMs, standardised evaluation) are what you do, and you can cite a Q1 review saying the field needs it. Their **usability** challenge is the strongest external justification for your Vue frontend — an examiner asking why a research project needs a UI can be pointed at a peer-reviewed review naming usability as a primary open challenge in this exact field.

---

## 20 · Edelman & Skolnick (2025) — Valsci

**Citation.** Edelman, B., & Skolnick, J. (2025). "Valsci: an open-source, self-hostable literature review utility for automated large-batch scientific claim verification using large language models." *BMC Bioinformatics*, 26.
**DOI.** [10.1186/s12859-025-06159-4](https://doi.org/10.1186/s12859-025-06159-4) · Springer Nature · Scopus-indexed · 6 citations

### Problem
*"The exponential growth of scientific publications poses a formidable challenge for researchers seeking to validate emerging hypotheses or synthesize existing evidence."* And specifically: *"conventional standalone LLMs... often suffer from hallucinations and unreliable citations."*

### Methodology
**Valsci** is open-source and self-hostable, working with *"any OpenAI-compatible large language model."* It *"unites retrieval-augmented generation with structured bibliometric scoring and chain-of-thought prompting,"* searching the **Semantic Scholar** database. A **guided prompt-flow** generates query expansions, retrieves relevant excerpts, and synthesises evidence-based reports. Scales through *"asynchronous parallelization,"* processing hundreds of claims per hour.

### Advantages
- **Directly targets citation hallucination** and reports *"significantly outperform[ing] base GPT-4o outputs in citation hallucination rate while maintaining a low misclassification rate."*
- **Evaluated on SciFact** — the same dataset your verifier trains on (`PROJECT_PLAN.md §4.2`), so comparison is genuinely possible.
- **Self-hostable and model-agnostic** — the same portability principle as your LiteLLM layer, and evidence the design is practical.
- Open source; high throughput.
- Bibliometric scoring parallels your venue tiering.

### Disadvantages
- Authors describe evaluation as **"preliminary"**.
- **Verification, not synthesis** — produces evidence reports, not literature reviews.
- Biomedical framing (Semantic Scholar-centric, BMC venue).
- Prompted LLM verification, not a trained verifier — so it inherits LLM cost and variance.
- No agentic control or replanning; a single guided prompt-flow.
- Few citations yet.

### Dataset(s)
**SciFact**; Semantic Scholar database as the live corpus.

### Relevance to ResearchGPT
**Your most direct competitor — cite and differentiate, or a reviewer will ask why you didn't.**

Valsci is open-source, self-hostable, model-agnostic, grounded, SciFact-evaluated, and explicitly aimed at citation hallucination. That is a lot of overlap with your positioning. The differentiation is real but must be stated precisely:

| | Valsci | ResearchGPT |
|---|---|---|
| Output | Evidence report per claim | Full literature review |
| Control | Single guided prompt-flow | Agentic graph with replanning |
| Verification | Prompted LLM + CoT | **Fine-tuned local NLI cross-encoder** |
| Per-paper output | Evidence excerpts | Structured four-field schema |
| Quality gate | None | Critic loop with bounded iteration |

The **trained verifier is your clearest technical differentiator** — Valsci verifies by prompting; you verify with a model trained for it, running locally at zero marginal cost. That is also a *cost* argument: their approach requires an LLM call per claim, yours does not, which matters under your $0 constraint.

**Practical opportunity:** since both systems evaluate on SciFact, you can compare your fine-tuned verifier against their reported citation-hallucination performance on shared data. A published comparison point on a common benchmark is worth far more than an internal ablation, and it is nearly free to obtain.

---

# C6 — GROUNDING, VERIFICATION & HALLUCINATION

## 21 · Es et al. (2024) — RAGAs

**Citation.** Es, S., James, J., Espinosa-Anke, L., & Schockaert, S. (2024). "RAGAs: Automated Evaluation of Retrieval Augmented Generation." *Proceedings of EACL 2024: System Demonstrations*.
**DOI.** [10.18653/v1/2024.eacl-demo.16](https://doi.org/10.18653/v1/2024.eacl-demo.16) · ACL Anthology · Scopus-indexed · 330 citations
*(Abstract from ACL Anthology; OpenAlex holds a citation stub.)*

### Problem
*"Evaluating RAG architectures is challenging due to several dimensions to consider: the ability of the retrieval system to identify relevant and focused context passages, the ability of the LLM to exploit such passages faithfully, and the quality of the generation itself."* Human reference annotation is the bottleneck.

### Methodology
**RAGAs** is *"a framework for reference-free evaluation of Retrieval Augmented Generation pipelines"* — a metric suite covering retrieval and generation dimensions that *"can evaluate these different dimensions without relying on ground truth human annotations."* Motivated by enabling *"faster evaluation cycles of RAG architectures."* Open source.

### Advantages
- **Reference-free** — no human-annotated ground truth needed, which is decisive when you have no budget and no annotators.
- Evaluates retrieval and generation separately, aligning with component-wise ablation.
- The de facto standard: 330 citations and wide adoption.
- **Used by your base paper**, so adopting it makes your evaluation directly comparable to Aytar et al.

### Disadvantages
- **System demonstration track** — a tooling contribution, not a validated measurement instrument.
- Metrics are **LLM-judged**, so they inherit the judge model's biases — and under your $0 constraint, your judge would be a small free-tier model, weakening the metric further.
- Reference-free metrics measure internal consistency, not correctness against the world.
- Costs API calls per evaluated sample — which is exactly why `PROJECT_PLAN.md §2.2` cuts it.
- No named benchmark in the abstract.

### Dataset(s)
**None named in abstract.**

### Relevance to ResearchGPT
An **informed rejection**, which is worth writing up. `PROJECT_PLAN.md §2.2` cuts RAGAs because it consumes API calls you cannot spare. Because Aytar et al. use RAGAs as their primary instrument, you should state this explicitly rather than let it look like an oversight — and note the specific weakness that makes the trade acceptable: RAGAs is LLM-judged, so running it through a small free-tier model would produce a *noisier* number than the local, deterministic measurements you use instead (citation resolution, span coverage, trained-verifier precision).

If your Week 4 has slack, running RAGAs on a **small sample** would buy comparability with the base paper cheaply. Treat it as a stretch goal, not a dependency.

Also relevant to `PROJECT_PLAN.md §9.3`: your LLM-as-judge evaluation has the same weakness. RAGAs' demo-track status and judge-bias limitation are the honest caveats to cite when you disclose it.

---

## 22 · Min et al. (2023) — FActScore

**Citation.** Min, S., Krishna, K., Lyu, X., Lewis, M., Yih, W., Koh, P. W., Iyyer, M., Zettlemoyer, L., & Hajishirzi, H. (2023). "FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation." *Proceedings of EMNLP 2023*.
**DOI.** [10.18653/v1/2023.emnlp-main.741](https://doi.org/10.18653/v1/2023.emnlp-main.741) · ACL Anthology · Scopus-indexed · 296 citations
*(Abstract from ACL Anthology; OpenAlex holds a citation stub.)*

### Problem
Evaluating factuality of long-form generation is hard for two reasons: *"(1) generations often contain a mixture of supported and unsupported pieces of information, making binary judgments of quality inadequate, and (2) human evaluation is time-consuming and costly."* A whole paragraph is neither true nor false — it is partly both.

### Methodology
**FACTSCORE** *"breaks a generation into a series of atomic facts and computes the percentage of atomic facts supported by a reliable knowledge source."*

Two evaluations. **Human:** extensive human evaluation of biographies generated by InstructGPT, ChatGPT, and retrieval-augmented PerplexityAI — *"ChatGPT only achieves 58%."* **Automated:** a model estimating FActScore *"using retrieval and a strong language model, with less than a 2% error rate,"* then applied to *"6,500 generations from a new set of 13 recent LMs that would have cost $26K if evaluated by humans."* Released as `pip install factscore`.

### Advantages
- **The atomic-decomposition method your Verifier implements**, validated at scale.
- Automated estimator within **<2% error** of human judgement — unusually strong validation for an automatic metric.
- Demonstrates enormous cost savings ($26K of human evaluation avoided).
- Concrete comparative findings (GPT-4 and ChatGPT more factual than public models).
- 296 citations; EMNLP main; installable package.

### Disadvantages
- **Requires a reliable knowledge source** to check facts against. FActScore uses Wikipedia; your equivalent is your own retrieved chunks — which is weaker, since a claim can be "supported" by a chunk that is itself wrong or misread.
- **Biography domain** — atomic facts about people are far more separable than claims about methodology or a paper's limitations.
- Atomic decomposition is itself LLM-performed and can err.
- Precision only — says nothing about recall or completeness.

### Dataset(s)
People biographies generated by InstructGPT, ChatGPT and PerplexityAI; 6,500 generations from 13 LMs.

### Relevance to ResearchGPT
**The methodological foundation of your Verifier.** `RESEARCHGPT_SPEC.md §7.4` specifies decomposing insights into atomic claims and judging each for support — that is FActScore, applied to review generation instead of biographies. Citing it means your Verifier implements a validated, widely-adopted technique rather than an ad-hoc filter, which is worth a great deal when the verifier is your graded component.

Two things to handle carefully.

**Your knowledge source is weaker than theirs.** FActScore checks against Wikipedia — an external, independent reference. You check against *your own retrieved chunks*. A claim can be marked SUPPORTED because a chunk appears to support it while the chunk was retrieved wrongly or read wrongly. This is a real limitation and it is closely related to the circularity trap in `PROJECT_PLAN.md §9.6`. **Name it in Limitations before a reviewer names it for you.**

**Their domain is easier than yours.** Atomic facts about a person's biography are crisply separable; "the paper's main disadvantage is limited generalisability" is not obviously atomic. Expect noisier decomposition, and consider reporting decomposition quality separately from verification accuracy.

Finally, FActScore's ChatGPT-at-58% result is a useful Introduction statistic: a leading model is factually correct in well under two-thirds of atomic claims in long-form generation, which motivates verification as a *necessary* component rather than a refinement.

---

## 23 · Gao et al. (2023) — ALCE

**Citation.** Gao, T., Yen, H., Yu, J., & Chen, D. (2023). "Enabling Large Language Models to Generate Text with Citations." *Proceedings of EMNLP 2023*.
**DOI.** [10.18653/v1/2023.emnlp-main.398](https://doi.org/10.18653/v1/2023.emnlp-main.398) · ACL Anthology · Scopus-indexed · 167 citations · Princeton NLP

### Problem
LLM outputs *"are prone to hallucination,"* and while citation-generating systems exist, *"existing work mainly relies on commercial search engines and human evaluation, making it challenging to reproduce and compare different modeling approaches."* A reproducibility problem as much as a capability one.

### Methodology
**ALCE** — *"the first benchmark for Automatic LLMs' Citation Evaluation."* Collects diverse questions and retrieval corpora and *"requires building end-to-end systems to retrieve supporting evidence and generate answers with citations."* Develops automatic metrics along **three dimensions — fluency, correctness, and citation quality** — and demonstrates *"their strong correlation with human judgements."* Tests state-of-the-art LLMs with novel prompting strategies.

### Advantages
- **Automatic metrics validated against human judgement** — the property RAGAs lacks.
- **Three-dimensional evaluation** separates writing quality, factual correctness and citation quality, which is exactly the separation your report needs.
- **End-to-end requirement** (retrieval *and* generation) matches your system boundary.
- Sobering, quotable headline: *"even the best models lack complete citation support 50% of the time"* on ELI5.
- Names the right future directions: better retrievers, long-context models, multi-source synthesis.

### Disadvantages
- Question-answering with citations, not long-form review generation — shorter outputs, simpler citation structure.
- ELI5 is a general-knowledge dataset, not scientific literature.
- Metrics require a defined retrieval corpus, so they do not transfer directly to open-ended literature search.
- Pre-dates current long-context models.

### Dataset(s)
**ALCE** benchmark; **ELI5** named explicitly. (The abstract names only ELI5; verify the full dataset list in the paper.)

### Relevance to ResearchGPT
**Your citation-accuracy metric comes from here.** `PROJECT_PLAN.md §9.3` measures citation accuracy by DOI resolution — checking a citation points at a *real* paper. ALCE's citation-quality metric is stricter: does the cited source actually *support* the statement? That is the metric you want, and it is validated against human judgement.

Consider **adopting ALCE's three dimensions as your output-evaluation structure** — fluency, correctness, citation quality. It is a ready-made, peer-reviewed framework, and using it saves you inventing one and defending it.

The 50% finding is one of your best Introduction statistics: state-of-the-art systems fail to fully support their citations half the time on ELI5. Combined with Sarol et al.'s 39.18% real-world citation error rate and FActScore's ChatGPT-at-58%, you have **three independent peer-reviewed measurements of the same failure**, from three different angles. That is a genuinely strong opening — far more persuasive than one statistic repeated.

---

## 24 · Huang et al. (2024) — Survey on Hallucination in LLMs

**Citation.** Huang, L., Yu, W., Ma, W., Zhong, W., Feng, Z., Wang, H., Chen, Q., Peng, W., Feng, X., Qin, B., et al. (2024). "A Survey on Hallucination in Large Language Models: Principles, Taxonomy, Challenges, and Open Questions." *ACM Transactions on Information Systems*.
**DOI.** [10.1145/3703155](https://doi.org/10.1145/3703155) · ACM TOIS · Scopus-indexed Q1 · **1,757 citations** · 214 references

### Problem
*"LLMs are prone to hallucination, generating plausible yet nonfactual content,"* raising concerns *"over the reliability of LLMs in real-world information retrieval (IR) systems."* Because LLMs are open-ended and general-purpose, *"LLM hallucinations present distinct challenges that diverge from prior task-specific models."*

### Methodology
Comprehensive survey with **an innovative taxonomy of LLM-era hallucination**, then: contributing factors; a thorough overview of **detection methods and benchmarks**; representative **mitigation** methodologies; and — most relevant to you — an examination of *"the current limitations faced by retrieval-augmented LLMs in combating hallucinations."* Closes on future directions including vision-language hallucination and knowledge boundaries.

### Advantages
- **1,757 citations** — the authoritative reference on hallucination.
- 214 references; ACM TOIS.
- Covers detection *and* mitigation *and* benchmarks — all three chapters you need.
- **Explicitly analyses where RAG fails to prevent hallucination**, which almost no other source does directly.
- Introduces the **knowledge-boundary** concept: when a model should recognise it does not know.

### Disadvantages
- Survey — no method, no experiments.
- Broad coverage means shallow treatment of scientific-domain hallucination specifically.
- Fast-moving area; a 2024 survey already misses recent work.
- OpenAlex's auto-assigned concepts for this record are wrong (*"Visual Hallucination, Psychology, Psychiatry"*) — a reminder not to trust automated topic tags.

### Dataset(s)
**None** — survey.

### Relevance to ResearchGPT
**The definitive citation for your problem statement**, and with 1,757 citations it cannot be dismissed as a fringe concern.

Its most valuable section for you is the analysis of **RAG's limitations in combating hallucination**. Your entire architecture rests on the premise that retrieval alone is insufficient — that you additionally need claim-level verification. This survey is the peer-reviewed support for that premise, from a Q1 IR venue. Without it, "RAG isn't enough" is your assertion; with it, it is the field's documented position.

Two further uses:

- **Taxonomy for your Limitations chapter.** Classify the residual hallucination types your system does *not* address (intrinsic hallucination in the Writer's prose, hallucination inside the extraction step itself) using their categories. A limitations section organised by an established taxonomy reads as rigour rather than apology.
- **The knowledge-boundary concept** gives you vocabulary for your stress test (`PROJECT_PLAN.md §9.5`): a system that recognises when the retrieved corpus does not cover a question is demonstrating knowledge-boundary awareness — a named research goal, not just a demo feature.

---

## 25 · Liu et al. (2024) — CliVER: Retrieval Augmented Scientific Claim Verification

**Citation.** Liu, H., Soroush, A., Nestor, J. G., Park, E., Idnay, B., Fang, Y., Pan, J., Liao, S., Bernard, M., Peng, Y., et al. (2024). "Retrieval augmented scientific claim verification." *JAMIA Open*, 7(1).
**DOI.** [10.1093/jamiaopen/ooae021](https://doi.org/10.1093/jamiaopen/ooae021) · Oxford University Press · Scopus-indexed · 8 citations

### Problem
*"To automate scientific claim verification using PubMed abstracts."* Verifying a claim against the published literature is currently manual, slow, and does not scale.

### Methodology
**CliVER**, an end-to-end system that *"leverages retrieval-augmented techniques to automatically retrieve relevant clinical trial abstracts, extract pertinent sentences, and use the PICO framework to support or refute a scientific claim."* Three-stage: retrieve → extract sentences → classify. Classification uses *"an ensemble of three state-of-the-art deep learning models to classify rationale of support, refute, and neutral."*

Also releases **CoVERt**: *"15 PICO-encoded drug claims accompanied by 96 manually selected and labeled clinical trial abstracts."* Evaluated on CoVERt and **SciFact**, then benchmarked against clinicians on 19 claims across 6 disease domains using **189,648 PubMed abstracts**.

### Advantages
- **Three-way classification (support / refute / neutral)** — the same label space as your Verifier.
- **Ensemble beats individual models by 3–11% absolute F1** — useful evidence if you consider ensembling.
- **F1 0.92** on CoVERt.
- **Benchmarked against four human clinicians**, which is rare and valuable.
- Evaluated on SciFact — shared ground with your verifier.
- Full pipeline decomposition (retrieval → sentence selection → classification) mirrors yours, with per-stage numbers.

### Disadvantages
- **The stage-wise numbers against clinicians are sobering**: 79.0% precision for abstract retrieval, 67.4% for sentence selection, **63.2% for label prediction**. Errors compound down the pipeline.
- **The 0.92 vs 63.2% gap is the real finding** — in-domain benchmark performance drastically overstates real-world accuracy.
- CoVERt is tiny (15 claims, 96 abstracts).
- Biomedical, PICO-structured — PICO gives claim structure that CS papers lack entirely.
- Ensemble of three deep models is expensive; infeasible on your CPU budget.
- Authors describe it as *"early potential."*

### Dataset(s)
**CoVERt** (own): 15 PICO-encoded drug claims, 96 labelled clinical trial abstracts. **SciFact**. 189,648 PubMed abstracts (Jan 2010 – Oct 2021).

### Relevance to ResearchGPT
**The most important paper here for setting honest expectations — read it alongside Sarol et al. (#14).**

Its central lesson is the gap between **F1 0.92 on its own curated benchmark** and **63.2% label accuracy against clinicians on real claims**. Same system, same task; the difference is whether the evaluation is in-domain and curated or real and open-ended. Your verifier will face exactly this gap: it trains on SciFact (curated, biomedical) and deploys on CS literature (open-ended, out-of-domain, and shifted in domain as `PROJECT_PLAN.md §11` already flags).

Three concrete consequences:

1. **Report both numbers.** SciFact held-out F1 *and* precision against your 50-claim human spot-check. Reporting only the first would repeat the error CliVER's authors were honest enough to expose. Reporting both, and discussing the gap, is what a good evaluation chapter looks like.
2. **Expect error compounding.** CliVER's per-stage figures (79.0% → 67.4% → 63.2%) show accuracy decaying through a three-stage pipeline. Yours has the same shape — retrieve chunks → select evidence → classify support. Your end-to-end grounding accuracy will be **materially lower than your verifier's standalone accuracy**, and you should measure and report per-stage numbers as they do.
3. **PICO has no CS equivalent.** CliVER exploits a structured claim framework (Population, Intervention, Comparison, Outcome) that biomedical claims naturally fit. CS papers have no such structure, which makes your claim decomposition harder than theirs. Note it as a limitation — and as one reason your four-field schema exists, since it imposes structure where the domain provides none.

The ensemble finding (+3–11% F1 over single models) is worth knowing but probably not actionable: three deep models on CPU is outside your budget. Mention it as Future Work.

---

# Cross-Cutting Observations

Five patterns visible only across the full set. These are the observations most worth putting in your Discussion chapter, because they are not available from any single paper.

**1. Three independent measurements of the same failure.** Sarol et al. find **39.18%** of citation instances in highly-cited biomedical papers contain accuracy errors. ALCE finds top systems *"lack complete citation support 50% of the time."* FActScore finds ChatGPT factually correct on only **58%** of atomic claims in long-form generation. Different tasks, different methods, different venues, converging conclusion. Together they make an opening paragraph that is very hard to argue with.

**2. Benchmark performance systematically overstates real performance.** CliVER: 0.92 → 63.2%. Sarol et al.: a carefully fine-tuned pipeline reaching only 0.59 micro-F1 on real citations. Khraisha et al. (reserve pool) found GPT-4's apparent parity with humans *"skewed by chance agreement and dataset imbalance,"* with scores dropping once corrected. **Your evaluation should assume this pattern applies to you.**

**3. Everyone assumes frontier-model API access.** Every system here — Valsci, QUAL-SG, CliVER, Self-BioRAG, Chain-of-Note — assumes hosted frontier models, fine-tuning compute, or both. Your $0, CPU-only constraint is genuinely unusual. That cuts two ways: a modest novelty (verification-driven quality at near-zero cost), but **no baseline to compare against**, so you must construct your own.

**4. Verification and synthesis are separate literatures.** C6 develops sophisticated verification (FActScore, ALCE) and C4 applies it to citations (Sarol et al.), while C5 builds review generators (SurveyGen, SciReviewGen) that report citation quality as their main weakness. Valsci is the closest bridge and it verifies without synthesising. **The intersection is where ResearchGPT sits, and this document is the evidence that it is unoccupied.**

**5. The most useful papers are the honest ones.** Sarol et al. publishing 0.59 F1, CliVER publishing its 63.2% clinician comparison, SurveyGen publishing that fully automatic generation still fails — these are more valuable to you than any paper claiming success, because they tell you what the real ceiling is. **Write your evaluation the same way.** Under a "does it work and not hallucinate" grading criterion, a report that names its own limits and measures them precisely is worth more than one claiming 0.95 groundedness that nobody believes.

---

## Immediate actions

1. **Get the PDF of paper #8** (Li et al., IP&M) through your library. It is the only entry in this document written from a title, and it may be a close competitor rather than a supporting citation.
2. **Fix `RESEARCHGPT_SPEC.md §1.2 and §1.3`** — the base paper is a multi-stage data-science RAG architecture, and the "fixed single-pass pipeline" claim is wrong.
3. **Switch the base paper to SurveyGen (#17)** and keep Aytar as related work.
4. **Recalibrate verifier targets** using #14 (0.59 micro-F1) and #25 (0.92 → 63.2%). Adjust `PROJECT_PLAN.md §9` before you build, not after.
5. **Verify the venue for #11** (*Vicinagearth*) is Scopus-indexed; substitute Wang et al. 2024 (*Frontiers of Computer Science*) if not.
6. **Add Ammann et al. (#9) as an explicit baseline** — same constraints, published numbers, directly comparable.

---

*All records verified 2026-08-06 via OpenAlex (26/26 resolved), with Crossref and ACL Anthology fallbacks. Citation counts are OpenAlex and are conservative. Re-verify before submission.*
