# Full-Text Deep Dive — 25 Papers + Base Paper

> **What this is.** An extensive summary of *what is actually inside each paper* — architecture details, experimental setup, every reported number, ablations, and the authors' own verbatim limitations. This goes beyond `PAPER_ANALYSIS.md`, which was written from abstracts.
>
> **How the papers were obtained.** PDFs downloaded from ACL Anthology, Springer, Nature and BMC; full text for two paywalled biomedical papers retrieved from **Europe PMC** (`PMC11231046`, `PMC10919922`); TACL located on ACL Anthology (`2023.tacl-1.1`). Text extracted with PyMuPDF, reference lists trimmed.
>
> ### ⚠️ Coverage — read this first
>
> **18 of 26 papers were obtained in full text.** The remaining **8 are abstract-only** because the publisher blocked automated access (HTTP 403) or the paper is paywalled with no OA route:
>
> | Abstract-only | Reason |
> |---|---|
> | **BASE** Aytar et al. | Elsevier, no OA |
> | **C1-01** Huang & Huang (ACM CSUR) | ACM DL 403 |
> | **C1-02** Peng et al. (ACM TOIS) | ACM DL 403 |
> | **C1-03** Lyu et al. (ACM TOIS) | ACM DL 403 |
> | **C2-07** Jeong et al. (Bioinformatics) | OUP 403; not OA in Europe PMC |
> | **C2-08** Li et al. (IP&M) | Elsevier, **no abstract anywhere** |
> | **C3-12** Yang et al. (IEEE TCCN) | IEEE paywall |
> | **C6-24** Huang et al. (ACM TOIS) | ACM DL 403 |
>
> Entries for those 8 are explicitly marked **[ABSTRACT ONLY]** and are necessarily thinner. Everything else below is from the full paper. Sections labelled **"Relevance to ResearchGPT"** are my analysis; everything else is the paper's own content.
>
> *Compiled 2026-08-06. Companion to `LITERATURE_REVIEW.md` and `PAPER_ANALYSIS.md`.*

---

## The five most important things the full texts revealed

These did not appear in any abstract and change decisions in `PROJECT_PLAN.md`.

**1. Your closest competitor names your contribution as its own limitation.** Ammann et al. (C2-09) — the paper whose pipeline most resembles your Planner+Retriever — list under Limitations: *"Lack of iterative retrieval. Our pipeline operates in a single-shot manner: subqueries are generated once and not updated based on retrieved evidence. This limits its ability to support adaptive multi-step reasoning."* That is exactly what your Critic loop does. **Quote it verbatim in your Introduction.**

**2. Humans barely agree on citation accuracy.** Sarol et al. (C4-14) report inter-annotator agreement of **0.18–0.31** on accuracy labels and **0.20–0.37** on evidence sentences — "fair" at best, between trained annotators on a carefully designed task. This reframes your entire evaluation: if expert humans agree only ~0.3, a verifier scoring 0.59 F1 against them is not obviously worse than a human, and your own 2-annotator Likert study (`PROJECT_PLAN.md §9.5`) should report agreement, not just means.

**3. Abstract-only conditioning costs 21 points of faithfulness — measured.** Li et al. (C4-15) report ANLI faithfulness of generated citations: **Abstract 0.745 vs. Context-CTS 0.959, Oracle-CTS 0.940, Keyword-CTS 0.941.** Your abstract-only degraded mode is not a mild compromise; it is the single largest faithfulness regression in this literature.

**4. Structured extraction needs ~20 examples to stabilise.** Dagdelen et al. (C4-13) found *"output sequences are not properly structured for training set sizes below ~10 samples, but there is a sharp increase in the number of correctly structured outputs at ~20 samples, which seems to be the minimum number of examples GPT-3 needs to learn a desired output format."* Directly sets the few-shot example count for your Extractor prompt.

**5. Adaptive-RAG's classifier is the weak link, by their own admission.** They report a measurable gap between their trained classifier and an oracle classifier, and state *"there is still room to improve the effectiveness of the classifier."* If you build a router, expect it — not the retrieval — to be your bottleneck.

---

# BASE PAPER

## Aytar, Kaya & Kılıç (2025) — Synergistic Multi-Stage RAG **[ABSTRACT ONLY]**

**Citation.** Aytar, A. Y., Kaya, K., & Kılıç, K. (2025). "A synergistic multi-stage RAG architecture for boosting context relevance in data science literature." *Natural Language Processing Journal* (Elsevier).
**DOI.** [10.1016/j.nlp.2025.100179](https://doi.org/10.1016/j.nlp.2025.100179) · Scopus-indexed · 2 citations · 11 references

**Problem.** Data science literature is voluminous and fast-moving; *"Standard Retrieval-Augmented Generation (RAG) systems often struggle with retrieving precisely relevant context from this dense academic corpus."*

**Methodology.** Four coordinated stages: (1) **GROBID** structured document parsing; (2) **domain-specific embedding fine-tuning derived from textbooks**; (3) **semantic chunking** for coherence; (4) a novel **"Abstract First"** retrieval strategy prioritising *"concise, high-signal summaries."* Evaluated with **RAGAS** on a custom data-science query set, with ablations against *"configurations using only subsets of these enhancements."*

**Results.** *"Boosts Context Relevance by over 15-fold compared to baseline RAG, surpassing configurations using only subsets of these enhancements."*

**Advantages.** Ablation-driven; the "Abstract First" result is counter-intuitive and useful; Scopus-indexed Elsevier venue.

**Disadvantages.** Single metric (Context Relevance only); bespoke unreleased query set, so the 15× is not independently comparable and implies a weak baseline; domain-locked by textbook-derived fine-tuning; heavy infrastructure; only 11 references and 2 citations.

**Datasets.** Custom data-science query set (unnamed); textbook corpus for fine-tuning (unnamed). No public benchmark.

**Relevance to ResearchGPT.** ⚠️ `RESEARCHGPT_SPEC.md §1.2` mis-describes this as "RAG-based literature assistance" — it is a retrieval-precision architecture for data science and does not generate reviews. Worse, §1.3's extension table calls it a *"Fixed single-pass pipeline"* when it is explicitly **multi-stage**. Rewrite that row: the honest contrast is **static multi-stage vs. dynamic agentic control with verification**. Also note it depends on **GROBID**, which `PROJECT_PLAN.md §2.2` cuts — a conflict you must justify if this stays your base paper. See `LITERATURE_REVIEW.md §2` for why SurveyGen (C5-17) is the better choice.

---

# C1 — RAG FOUNDATIONS

## C1-01 · Huang & Huang (2026) — Survey on Retrieval-Augmented Text Generation **[ABSTRACT ONLY]**

**Citation.** Huang, Y., & Huang, J. X. (2026). *ACM Computing Surveys.* DOI [10.1145/3805774](https://doi.org/10.1145/3805774) · 34 citations · 30 references

**Problem.** RAG has fragmented as it has grown; no shared organising vocabulary.

**Methodology.** Organises RAG into **four sequential stages from the retrieval viewpoint: pre-retrieval → retrieval → post-retrieval → generation**, analyses significant studies per stage, then surveys evaluation methods and open challenges.

**Advantages.** *ACM Computing Surveys* authority; the four-stage structure maps directly onto implementation; covers evaluation as well as method.

**Disadvantages.** Survey with no new results; retrieval-centric framing under-weights agentic control — exactly where your contribution sits; only 30 references recorded, modest for CSUR.

**Datasets.** None.

**Relevance.** The default scaffold for your System Design chapter: Planner → pre-retrieval, Retriever → retrieval, rerank/verify → post-retrieval, Writer → generation. Borrowing a CSUR taxonomy costs nothing and makes your design instantly legible.

---

## C1-02 · Peng et al. (2025) — Graph RAG: A Survey **[ABSTRACT ONLY]**

**Citation.** Peng, B., Zhu, Y., Liu, Y., Bo, X., Shi, H., Hong, C., Zhang, Y., & Tang, S. (2025). *ACM TOIS.* DOI [10.1145/3777378](https://doi.org/10.1145/3777378) · 66 citations

**Problem.** Flat vector retrieval discards relational structure; *"the complex structure of relationships among different entities in databases presents challenges for RAG systems."*

**Methodology.** First comprehensive GraphRAG survey. Formalises **Graph-Based Indexing → Graph-Guided Retrieval → Graph-Enhanced Generation**, covering core technologies, training methods, downstream tasks, evaluation, and industrial use cases. Live repository maintained.

**Advantages.** First systematic treatment; clean three-stage formalisation; covers industrial deployments.

**Disadvantages.** Young area (authors note its *"novelty"*); graph construction cost understated by survey framing; **no comparative benchmarking of GraphRAG vs flat RAG**, so the actual benefit is unquantified.

**Datasets.** None.

**Relevance.** Cite as a **deliberate non-choice**. At ~60 papers / ~3k chunks, graph indexing cost is not repaid. Naming the frontier alternative and explaining the trade-off reads as judgement; ignoring it reads as unawareness. Also your clearest Future Work item.

---

## C1-03 · Lyu et al. (2024) — CRUD-RAG **[ABSTRACT ONLY]**

**Citation.** Lyu, Y., Li, Z., Niu, S., Xiong, F., Tang, B., Wang, W., Wu, H., Liu, H., Xu, T., & Chen, E. (2024). *ACM TOIS.* DOI [10.1145/3701228](https://doi.org/10.1145/3701228) · 88 citations

**Problem.** RAG benchmarks *"focus primarily on question-answering applications"* and *"often assess only the LLM components of the RAG pipeline or the retriever... overlooking the impact of external knowledge base construction and the retrieval component."*

**Methodology.** Categorises RAG applications by **CRUD**: **Create** (original varied content), **Read** (knowledge-intensive QA), **Update** (correcting inaccuracies in existing text), **Delete** (summarising long text). Separate dataset per category. Analyses the effect of *"the retriever, context length, knowledge base construction, and LLM."* Code at `github.com/IAAR-Shanghai/CRUD_RAG`.

**Advantages.** Component-wise evaluation; covers generation scenarios beyond QA including summarisation; uniquely evaluates knowledge-base construction; public code.

**Disadvantages.** **Chinese-language only** — the data is unusable for you; CRUD is borrowed from database semantics and fits generation loosely; no agentic or multi-step scenarios.

**Datasets.** CRUD-RAG (own, Chinese), four sub-datasets.

**Relevance.** Your peer-reviewed justification for **ablations 2–4**: a TOIS benchmark paper arguing that whole-pipeline evaluation hides component-level failure. Their "Delete" (long-text summarisation) is the closest published analogue to review synthesis. You can borrow the argument but not the data.

---

## C1-04 · Siriwardhana et al. (2023) — RAG-end2end ✅ FULL TEXT

**Citation.** Siriwardhana, S., Weerasekera, R., Wen, E., Kaluarachchi, T., Rana, R., & Nanayakkara, S. (2023). *TACL* 11 (ACL Anthology `2023.tacl-1.1`). DOI [10.1162/tacl_a_00530](https://doi.org/10.1162/tacl_a_00530) · 297 citations · 59 references

### Problem
RAG was only ever trained and explored on a Wikipedia knowledge base and *"is not optimized for use in other specialized domains such as healthcare and news."* Off-the-shelf RAG degrades badly on specialist corpora.

### Methodology
**RAG-end2end** makes two modifications to original RAG:

1. **Joint end-to-end training of retriever and generator**, including *"updating all components of the external knowledge base during training"* — the passage encoder, the question encoder, **and periodic re-indexing of the knowledge base** as embeddings shift. Both the passage encoder and question encoder of the DPR retriever are fine-tuned, which is what original RAG does not do.
2. **An auxiliary reconstruction training signal** that *"forces RAG-end2end to reconstruct a given sentence by accessing the relevant information from the external knowledge base,"* injecting domain knowledge beyond the QA objective.

Trained for **ten epochs** per variant, selecting *"the final checkpoint with the highest validation accuracy."* Metrics: **Exact Match (EM), F1, and Top-5 / Top-20 retrieval accuracy.** Open-sourced into HuggingFace Transformers.

### Results
- **Table 1: RAG-end2end-QA significantly outperforms RAG-original-QA on all metrics — EM, F1, Top-5, Top-20 — across all three domains.**
- EM improvements ranged **+1.13 points (News) to +12.16 points (Conversation)**.
- A second reported range: **+1.7 (Conversation) to +8.39 (News)**; **Top-20 retrieval accuracy up 3.2–8 points.**
- Reconstruction signal alone (without end2end): *"improves the performance moderately"* — EM gains **+0.84 (COVID-19) to +3.12 (Conversation)**.
- Highlighted single result: **13-point EM improvement in the Conversation domain.**
- **Table 5, SQuAD open-domain:** RAG-original **EM 28.12 / F1 39.42 / Top-5 59.64 / Top-20 72.38** → RAG-end2end **EM 40.02 / F1 52.63 / Top-5 75.79 / Top-20 85.57**. A ~12-point EM and ~13-point F1 gain.
- Fine-tuning DPR on its original loss with domain data also improves retrieval, but RAG-end2end *"significantly improves the DPR's domain adaptation for all three domains."*

### Advantages
Large, consistent gains across three domains and on open-domain SQuAD; the auxiliary reconstruction objective is elegant and reusable; strong evidence that **a domain-specific retriever is the key driver** — the authors *"argue... that when adapting RAG to various domains, having a domain-specific retriever plays a key role"*; shipped in HuggingFace Transformers, unusually strong reproducibility evidence.

### Disadvantages
Requires **full end-to-end training with periodic knowledge-base re-encoding** — very heavy. Their own stated failure mode: *"If the knowledge base is not entirely updated with the new embeddings, the re-indexing process fails."* Restricted to open-domain QA, not long-form generation. Pre-dates instruction-tuned LLMs, so baselines are dated.

### Datasets
**COVID-19** (CORD-19), **News**, **Conversations**; plus **SQuAD** open-domain. Also references Natural Questions and TriviaQA. Models: DPR, BART, BERT, BM25.

### Relevance to ResearchGPT
This is your **defence for a frozen retriever**. It is the strongest evidence that joint retriever–generator training is the most effective domain-adaptation route, and it is flatly infeasible at $0 on CPU. Naming the superior method you rejected, with the reason, converts a resource limit into a scope decision.

It also sharpens your **trained verifier's** contribution: you adapt the *verification* component to the domain instead of the retriever — the cheap end of the same idea. And their re-indexing failure mode is a concrete argument for why your frozen `bge-small` index is operationally simpler, not merely cheaper. Put this in both Limitations and Future Work.

---

# C2 — AGENTIC & SELF-REFLECTIVE RAG

## C2-05 · Jeong et al. (2024) — Adaptive-RAG ✅ FULL TEXT

**Citation.** Jeong, S., Baek, J., Cho, S., Hwang, S. J., & Park, J. C. (2024). *NAACL-HLT 2024*, pp. 7036–7050. KAIST. DOI [10.18653/v1/2024.naacl-long.389](https://doi.org/10.18653/v1/2024.naacl-long.389) · 182 citations

### Problem
Existing retrieval strategies *"either handle simple queries with unnecessary computational overhead or fail to adequately address complex multi-step queries; yet, not all user requests fall into only one of the simple or complex categories."*

The paper's framing question is worth quoting: *"In a real-world scenario, are all the requests from users complex? Instead, users might often ask simple and straightforward questions, while only occasionally asking complex ones."* They also critique existing adaptive methods directly — entity-frequency approaches *"are overly simplistic, failing to consider multi-hop queries,"* while multi-step-output approaches are *"excessively complex, terminating answer solving steps after several rounds of module access."*

### Methodology
Three strategies selected per query by a classifier (Figure 2 in the paper):

- **(A) No retrieval** — for straightforward queries answerable from parametric memory ("Paris is the capital of what?").
- **(B) Single-step retrieval** — one retrieval, then answer.
- **(C) Multi-step / iterative retrieval** — repeated retrieval and intermediate answers, *k* times.

The **complexity classifier is a smaller LM** trained to predict complexity level. Its training data is built **without human labelling**, via two strategies: (i) **predicted outcomes** — which models actually answer which queries correctly; and (ii) **inherent dataset bias** — *"samples in the datasets are designed either for single-step or for multi-step QA scenarios."* Classifier training queries do not overlap with test queries.

Metrics: **F1, EM, and Accuracy (Acc)** where *"Acc measures whether the predicted answer contains the ground-truth answer"*; plus **Time per Query** and **Step** count for efficiency.

### Results
- Figure 1 plots **F1 (47–51 range) against Time per Query (0.5–3.5s)** with GPT-3.5-Turbo-Instruct, showing Adaptive-RAG dominating the efficiency/accuracy frontier versus No Retrieval, Single-step, Adaptive Retrieval, and Multi-step.
- *"The classification accuracy of our Adaptive-RAG is better than those of the other adaptive retrieval baselines, which leads to overall QA performance improvements."*
- **Classifier ablation (their table):** Adaptive-RAG **F1 46.94, Step 1084**, with per-class accuracy All 54.52 / No 30.52 / One 66.28 / Multi 65.45. **w/o Binary:** F1 43.43, Step 640. **w/o Silver:** F1 48.79, Step 1464 — higher F1 but **35% more steps**, and No-retrieval accuracy collapses to 0.00.
- An **oracle classifier** *"achieves the best performance while being much more efficient"* than the trained classifier — quantifying the headroom.
- Classifier size ablation: *"no significant performance differences among classifiers of various sizes, even with reduced complexity and fewer parameters in smaller classifiers."*

### Advantages
Improves **both** efficiency and accuracy rather than trading them; automatic label collection removes the annotation bottleneck; **smaller classifiers work as well as larger ones**, so routing is genuinely cheap; validated on GPT-3.5 and FLAN-T5 series; beats other adaptive-retrieval baselines, not just static RAG.

### Disadvantages (their own Limitations, verbatim highlights)
*"As there are no available datasets for training the query-complexity classifier, we automatically create new data based on the model prediction outcomes and the inductive dataset biases. However, our labeling process is one specific instantiation of labeling the query complexity, and it may have the potential to label queries incorrectly despite its effectiveness."*

And on the oracle gap: *"as the performance gap between the ideal classifier in Table 1 and the current classifier in Figure 3 indicates, there is still room to improve the effectiveness of the classifier."* They describe their design as *"the initial, simplest instantiation."*

### Datasets
Single-hop: **SQuAD, Natural Questions, TriviaQA**. Multi-hop: **MuSiQue, HotpotQA, 2WikiMultiHopQA**. Models: GPT-3.5, FLAN-T5 series, T5-based classifier, BM25 retriever.

### Relevance to ResearchGPT
**The strongest published precedent for your Planner**, with three concrete transfers:

1. **Design justification.** "One retrieval strategy does not fit all sub-questions" is not your assumption — it is their empirically supported thesis, at a NAACL main track with 182 citations.
2. **A cheaper Planner.** Their finding that **small classifiers match large ones** is directly actionable: under your rate-limited free tier, routing sub-questions with a small *local* classifier instead of an API call would cut request volume with no measured loss.
3. **Expect the router to be your bottleneck.** They state it themselves — the oracle-vs-trained gap is the dominant error source. If you build routing logic, instrument it and report its accuracy separately.

**The architectural contrast that sharpens your contribution:** Adaptive-RAG routes **once, before retrieval, on the query alone**. Your Critic re-routes **after seeing what came back**. That is a real difference and it is `LITERATURE_REVIEW.md §5 Gap 3`.

---

## C2-06 · Yu et al. (2024) — Chain-of-Note ✅ FULL TEXT

**Citation.** Yu, W., Zhang, H., Pan, X., Cao, P., Ma, K., Li, J., Wang, H., & Yu, D. (2024). *EMNLP 2024*, p. 14679. DOI [10.18653/v1/2024.emnlp-main.813](https://doi.org/10.18653/v1/2024.emnlp-main.813) · 41 citations

### Problem
Two distinct failure modes: *"the reliability of the retrieved information is not always guaranteed, and the retrieval of irrelevant data can mislead the response generation"*; and *"standard RALMs frequently neglect their intrinsic knowledge due to the interference from retrieved information."* Desired behaviour: use intrinsic knowledge when retrieval is poor, and *"in the absence of both intrinsic and retrieved knowledge, opt to respond with 'unknown' to avoid hallucination."*

### Methodology
**CHAIN-OF-NOTE (CON)** generates *"sequential reading notes for each retrieved document,"* assessing each document's relevance before integrating anything. Two deployment modes: (a) prompting GPT-4 with CON; (b) distillation — *"we utilized GPT-4 to create 10K CON data, subsequently trained on LLaMa-2 7B model."*

Metrics: **EM** (normalised per Karpukhin et al.) and **F1** for open-domain QA; **Rejection Rate (RR)** for unanswerable/real-time questions. GPT-4 is scored with **Accuracy rather than EM**, because *"since GPT-4 is not directly trained on open-domain QA benchmarks, employing EM / F1 for evaluation is challenging."*

### Results
- **+7.9 EM** on fully noisy documents, averaged across three open-domain QA datasets.
- **+10.5 increase in rejection rate** for real-time questions beyond the pre-training knowledge scope.
- **+1.97 average EM** across all three datasets using **LLaMa-2** as backbone.
- **Table 4 (RealTimeQA, unknown robustness):** Retrieve-Read **EM 15.6 / F1 19.9 / RR 6.1** → + CHAIN-OF-NOTE **EM 15.7 / F1 20.3 / RR 13.0**. Note the RR **more than doubles** while EM/F1 barely move — the gain is almost entirely *knowing when to refuse*.
- GPT-4 with CON outperforms chain-of-thought prompting.
- Improvement *"varies depending on whether DPR successfully retrieves relevant documents."*

### Advantages
Explicit, measurable **refusal capability** — rare in this literature; distillation into a 7B model works; per-document notes are inherently interpretable; robustness gains under noisy retrieval are the largest reported effect.

### Disadvantages (their Limitations, verbatim)
*"One major limitation of the CHAIN-OF-NOTE (CON) approach is its increased inference cost due to the sequential generation of notes. While CON is beneficial for assessing the relevance and integrating external knowledge, it results in longer response times, which is problematic for time-sensitive applications. Moreover, the system's efficiency depends on the conciseness and relevance of the generated notes, which can fluctuate based on the complexity of the retrieved documents."*

Also: distillation requires GPT-4 access; the four benchmarks are not all named in-text; note quality is itself unverified LLM output.

### Datasets
**TriviaQA** and **RealTimeQA** named explicitly; three open-domain QA datasets for the main results plus a fourth for fine-tuning experiments. 10K GPT-4-generated CON training set. Models: GPT-4, LLaMa-2 7B, DPR.

### Relevance to ResearchGPT
**The intellectual precedent for your hallucination stress test** (`PROJECT_PLAN.md §9.5`), and the RealTimeQA result is the template: RR **6.1 → 13.0** while EM barely moves. That is exactly the shape of result your stress test should produce — *the system refuses more, without getting worse at what it can answer*. Report it the same way.

**But read the limitation as a budget warning.** Sequential note generation is one LLM call per retrieved document. With top-12 chunks per sub-question across 4–8 sub-questions, CON would be hundreds of extra calls per run — impossible on a rate-limited free tier. Your **local NLI verifier is the cost-appropriate substitute**: same goal (filter unreliable retrieved content before it reaches the output), radically cheaper mechanism, and unlike CON's notes it is independently auditable. Make that comparison explicitly in your Design chapter — it shows you understood the technique and chose deliberately.

---

## C2-07 · Jeong et al. (2024) — Self-BioRAG **[ABSTRACT ONLY]**

**Citation.** Jeong, M., Sohn, J., Sung, M., & Kang, J. (2024). *Bioinformatics* 40(Suppl 1). DOI [10.1093/bioinformatics/btae238](https://doi.org/10.1093/bioinformatics/btae238) · 115 citations

**Problem.** *"When applying existing methods to different domain-specific problems, poor generalization becomes apparent, leading to fetching incorrect documents or making inaccurate judgments."*

**Methodology.** **Self-BioRAG** specialises in *"generating explanations, retrieving domain-specific documents, and self-reflecting generated responses."* Trained on **84k filtered biomedical instruction sets** so the model *"can assess its generated explanations with customized reflective tokens"* — reflection is a learned in-model behaviour, not an external check. Weights (7B, 13B), data and code released at `github.com/dmis-lab/self-biorag`.

**Results.** **+7.2% absolute average improvement** over the state-of-the-art open foundation model at ≤7B parameters, across three medical QA benchmarks. **+8% ROUGE-1 over RAG** on two long-form QA benchmarks.

**Advantages.** The long-form QA gain matters most for you — closer to review writing than multiple-choice. Full artefact release. Demonstrates domain-specific retriever + corpus + instructions are *jointly* necessary.

**Disadvantages.** Requires 84k domain instructions you cannot construct at $0; biomedical only; **reflection is internal to the model, so its judgements cannot be independently audited**; 7B inference impractical on CPU.

**Datasets.** 84k biomedical instruction sets; three medical QA benchmarks and two long-form QA benchmarks (not named in abstract).

**Relevance.** Peer-reviewed evidence that self-reflection improves RAG, *and that the gain holds for long-form output*. But the more important reading is the contrast: Self-BioRAG bakes reflection into the model; you externalise it into a separate trained verifier. **That is arguably the better design for your purpose — an external verifier can be ablated, audited and reported on; reflective tokens cannot be separated from the generator.** This is the argument that justifies ablation 2 as your headline experiment.

---

## C2-08 · Li et al. (2025) — Evidence-Aware RAG via Self-Corrective CoT **[NO ABSTRACT AVAILABLE]**

**Citation.** Li, Y., Ke, W., Liu, J., Wang, P., Liu, J., & He, Y. (2025). *Information Processing & Management.* DOI [10.1016/j.ipm.2025.104369](https://doi.org/10.1016/j.ipm.2025.104369) · 10 citations · 43 references

### ⚠️ Cannot be summarised — action required
The **bibliographic record is verified** in OpenAlex and Semantic Scholar (DOI, title, six authors, journal, 43 references). But **no abstract exists in OpenAlex, Crossref or Semantic Scholar**, and ScienceDirect returns **HTTP 403** to automated access. There is a **year discrepancy**: OpenAlex says 2025, Semantic Scholar says 2026.

Everything that could be said about this paper would be inferred from its title, so nothing is asserted here.

**Why it matters.** "Evidence-aware" and "self-corrective" describe your Verifier and Critic almost exactly, in a **top-tier Q1 IR journal**. It may be a *competitor* you must differentiate from rather than a supporting citation — which is important to establish early, not late.

**Action:** retrieve the PDF through your institution's library and write this entry yourself. This is the only gap in this document that I cannot close.

---

## C2-09 · Ammann, Golde & Akbik (2025) — Question Decomposition for RAG ✅ FULL TEXT

**Citation.** Ammann, P., Golde, J., & Akbik, A. (2025). *ACL 2025: Student Research Workshop*, p. 501. Humboldt-Universität zu Berlin. DOI [10.18653/v1/2025.acl-srw.32](https://doi.org/10.18653/v1/2025.acl-srw.32) · 9 citations

### Problem
Multi-hop questions defeat standard RAG because *"relevant facts are often distributed across multiple documents rather than co-occurring in one source."* Semantic similarity to the whole question retrieves no single passage that answers it.

### Methodology
Three stages: **(i)** an LLM decomposes the query into sub-questions; **(ii)** passages retrieved per sub-question; **(iii)** *"the merged candidate pool is reranked."* A filtering step retains *"only passages that clearly address distinct aspects of the original question, improving precision in the final evidence set."*

Four configurations compared: **Naive RAG**, **QD** (decomposition only), **RR** (reranking only), **QD+RR** (both). Generation with **Qwen2.5-32B-Instruct** in bfloat16, temperature 0.8, nucleus sampling top-p 0.8. Metrics: **Hits@4, Hits@10, MAP@10, MRR@10** for retrieval; **F1, EM, precision, recall** plus supporting-fact and joint metrics for answers. Code released.

The authors are explicit about novelty: *"Although reranking itself is standard, we show that pairing an off-the-shelf cross-encoder reranker with LLM-driven question decomposition bridges the retrieval gap on multi-hop questions and provides a practical, drop-in enhancement, without any extra training or specialized indexing."*

### Results
**MultiHop-RAG (retrieval):**
- **QD alone:** +4.4 points Hits@4, +2.9 Hits@10.
- **RR alone:** +7.6 points Hits@4; *"substantially improves MAP@10 and MRR@10."*
- **QD+RR:** best overall — **87.2% Hits@10 and 0.635 MRR@10**.
- Against the dataset's published baseline (**74.7% Hits@10, 0.586 MRR@10**): *"our QD+RR thus improves Hits@10 by 16.5% and MRR@10 by 8.4%"* — **achieved "despite using a smaller embedding model."**
- MAP@10 rises to 0.322 with QD+RR vs 0.274 for RR alone, *"suggesting that reranking not only filters noise but leverages the broader context to prioritize relevant passages."*

**HotpotQA dev (Table 2):**

| System | F1 | P | R | EM |
|---|---|---|---|---|
| Naive RAG | 31.3 | 33.1 | 31.2 | 25.4 |
| QD | 32.3 | 34.3 | 32.0 | 26.1 |
| RR | 32.9 | 35.0 | 32.7 | 26.4 |
| **QD+RR** | **35.0** | **37.1** | **34.8** | **28.1** |

Supporting-fact metrics: Naive 18.4/12.0/42.8 · QD 17.0/10.6/44.1 · RR **19.6**/**12.9**/44.9 · QD+RR 17.9/11.2/**46.8**. Joint: Naive 8.7/5.9/20.2 · QD 8.0/5.2/20.7 · RR **9.5**/**6.4**/21.4 · QD+RR 8.9/5.8/**23.1**.

Note the nuance: **QD+RR wins on precision (46.8 supporting-fact, 23.1 joint) but RR alone wins on supporting-fact EM/F1** — decomposition trades some exactness for coverage. Their summary: *"the former improves coverage, while the latter restores precision."*

**Ablation:** comparing sub-query count to gold evidence count, *"both Pearson and Spearman coefficients are near zero... indicating no correlation"* — the decomposer does not learn how many hops a question actually needs.

### Advantages
Large retrieval gains with **no training and no specialised indexing**; two public named benchmarks; genuinely careful about which component contributes what; unusually honest about its own novelty.

### Disadvantages (their Limitations, verbatim — all six)
1. **Single-hop and adverse cases.** *"Question decomposition can be counterproductive when the original query is already specific. In such cases, subqueries may introduce noise or distract from the original intent."*
2. **Prompt and model sensitivity.** *"The quality of subqueries is sensitive to both the prompt design and the underlying LLM."*
3. **Computational overhead.** *"Generating M subqueries and reranking M × k candidate passages substantially increases latency and GPU requirements."*
4. **Pipeline complexity.** *"Every extra component increases engineering overhead, latency, and potential points of failure."*
5. **Reranker and domain dependence.** *"The observed gains rely on a strong, domain-aligned cross-encoder reranker. When the reranker is mismatched with the retrieval or task domain, the benefits of decomposition may diminish or vanish entirely."*
6. **Lack of iterative retrieval.** *"Our pipeline operates in a single-shot manner: subqueries are generated once and not updated based on retrieved evidence. This limits its ability to support adaptive multi-step reasoning."*

Plus: SRW venue (lighter review), 9 citations.

### Datasets
**MultiHop-RAG** and **HotpotQA**. Model: Qwen2.5-32B-Instruct.

### Relevance to ResearchGPT
**Your single closest methodological relative — and now, after reading the full text, also your best Introduction quote.**

**Their limitation #6 is your contribution.** *"Subqueries are generated once and not updated based on retrieved evidence"* is precisely what your Critic loop fixes: your Critic sees retrieval results, assesses coverage, and sends control back to the Planner or Retriever. Quote it verbatim, cite it, and your bounded feedback loop stops being a design preference and becomes a documented open problem you address.

**Their limitation #5 is a warning you must act on.** *"The observed gains rely on a strong, domain-aligned cross-encoder reranker"* — and `PROJECT_PLAN.md §6.1` downgrades your reranker to a **22M MiniLM** for CPU speed, which is neither strong nor domain-aligned. Their gains may not replicate at your model scale. Two responses: measure reranking's contribution separately on Day 4, and treat the cut §4.3 reranker fine-tune as the mitigation if the measured gain is poor.

**Three more transfers:**
- **A Day-5 sanity check.** Decomposition + reranking should yield a large retrieval gain. If yours is far below their +16.5% Hits@10, suspect a bug rather than a finding.
- **It bounds your novelty, usefully.** Query decomposition + reranking is published and quantified. Your contribution is what happens *after*: structured extraction, verification, the loop. Being precise here makes your claims more credible.
- **A better ablation-4 baseline.** "Decomposition + rerank, no verification, no loop" is a competitive published configuration — far stronger than a vanilla-RAG strawman.

---

# C3 — MULTI-AGENT LLM SYSTEMS

## C3-10 · Qian et al. (2024) — ChatDev ✅ FULL TEXT

**Citation.** Qian, C., Liu, W., Liu, H., Chen, N., Dang, Y., Li, J., Yang, C., Chen, W., Su, Y., Cong, X., Xu, J., Li, D., Liu, Z., & Sun, M. (2024). *ACL 2024 (Long Papers)*. Tsinghua University. DOI [10.18653/v1/2024.acl-long.810](https://doi.org/10.18653/v1/2024.acl-long.810) · 279 citations (OpenAlex) / 1,043 (Semantic Scholar)

### Problem
Phase-specific models fragment multi-stage workflows: *"the deep learning model in each phase requires unique designs, leading to technical inconsistencies across various phases, which results in a fragmented and ineffective development process."*

### Methodology
**ChatDev** is *"a chat-powered software-development framework integrating multiple 'software agents' for active involvement in three core phases of the software lifecycle: design, coding, and testing."* Two named control mechanisms:

- **Chat chain** — governs *what* agents communicate; structures the sequence of agent interactions.
- **Communicative dehallucination** — governs *how* they communicate. It *"encourages the assistant to actively seek more detailed suggestions from the instructor before delivering a formal response."* Note the mechanism: hallucination is reduced by making the receiving agent **ask for clarification before committing**, rather than by checking output afterwards.

A reported qualitative finding: natural language suits system design, while programming language suits debugging — the communication medium should match the sub-task.

Evaluation dimensions: **completeness, executability, consistency, and overall quality**.

### Advantages
The canonical peer-reviewed demonstration that role specialisation with structured communication beats monolithic prompting. **Communicative dehallucination explicitly recognises that multi-agent systems create new hallucination surfaces at agent interfaces** — a failure mode most multi-agent papers ignore entirely. Very high citation count; ACL long paper.

### Disadvantages (their Limitations, verbatim highlights)
- *"The capabilities of autonomous agents in software production might be overestimated. While they enhance development quality, agents often implement simple logic, resulting in low information density. Without clear, detailed requirements, agents struggle to grasp task ideas."*
- *"Currently, these technologies are more suitable for prototype systems rather than complex real-world applications."*
- *"Automating the evaluation of general-purpose software is highly complex... manual verification for large datasets is impractical."*
- *"Compared to single-agent approaches, multiple agents require more tokens and time, increasing computational demands and environmental impact. Future research should aim to enhance agent capabilities with fewer interactions."*

Plus: software-engineering domain with no retrieval or evidence grounding; **no quantitative results extractable from the main text** — the paper's contribution is architectural and qualitative.

### Datasets
**None** — evaluated on software-development tasks, not a public benchmark. Models: ChatGPT, GPT-4.

### Relevance to ResearchGPT
**Your primary citation for "role decomposition works,"** and the answer to "why not one big prompt?"

But the more valuable transfer is **communicative dehallucination**. ChatDev found multi-agent systems hallucinate *at agent boundaries* — one agent's imprecise output becomes another's confident input. Your pipeline has five such handoffs (Planner→Retriever→Extractor→Verifier→Critic→Writer) and errors compound along them. `RESEARCHGPT_SPEC.md` addresses grounding of the *final output* but never inter-agent drift. Two consequences:

- **Your Verifier already mitigates this by construction** — it re-grounds Extractor output against source chunks, breaking the drift chain mid-pipeline. Claim that explicitly; it is a design strength currently unstated.
- **Your `trace.jsonl` is the instrument to measure it.** Logging per-agent input/output as the spec requires lets you actually observe boundary drift — a cheap, interesting minor finding.

Their token-cost admission (*"multiple agents require more tokens and time"*) is also the honest framing for your own cost table — pair it with AutoHMA-LLM (C3-12), which shows tiered model assignment can *reduce* cost.

---

## C3-11 · Li et al. (2024) — Survey on LLM-Based Multi-Agent Systems ✅ FULL TEXT

**Citation.** Li, X., Wang, S., Zeng, S., Wu, Y., & Yang, Y. (2024). *Vicinagearth* 1(9). Wuhan University / Zhejiang University. DOI [10.1007/s44336-024-00009-2](https://doi.org/10.1007/s44336-024-00009-2) · 307 citations · **254 references** · 43 pages

### Problem
LLM-based multi-agent systems have proliferated without a unifying account, making architectures hard to compare.

### Methodology
Systematic survey synthesising **five key components: profile, perception, self-action, mutual interaction, and evolution**. The **self-action** module is decomposed further, including a **memory** module — *"serving as the storage and recall unit for the agent... instrumental in allowing it to leverage existing cognitive and experiential knowledge to adapt to dynamic interactions with the environment or other agents."* Applications split into **problem-solving** and **world simulation**.

### Content relevant to your system
The survey's treatment of **hallucination mitigation in multi-agent settings** is the most useful part:

- It distinguishes **intrinsic hallucinations** (*"text generation that contradicts input logic"*) from **extrinsic hallucinations** (*"text generation containing information that cannot be verified with existing information"*). Your Verifier targets the extrinsic kind.
- Mitigation families it catalogues: *"integrate external knowledge bases and fact-checking systems to verify the accuracy of generated content"*; **RAG** methods that provide *"mechanisms to check for inconsistencies between the generated response and the source material"*; and **decoding strategies** that balance *"diversity and factual accuracy."*
- **CoVe** is described as a direct analogue of your design: it *"encourages models to generate initial responses, followed by verification queries to check the draft's factual accuracy before producing a refined response."*
- **Multi-agent debate** for factuality: *"deploys multiple instances of LLMs in debates to achieve consensus, thereby enhancing reasoning and factual accuracy"*; **ChatEval** *"simulates the collective wisdom and cognitive collaboration of human evaluators by constructing a multi-agent debate system."*
- **Plan revision on failure** — DEPS-style systems where *"agents initiate action planning for a specific task and proceed with execution unless indications of plan failure emerge during the process,"* and prerequisite errors *"prompt the LLM to revise the plan accordingly."* This is the closest published description of your Critic→Planner edge.
- **Reflection on past failures** — Retroformer *"enables an agent to reflect on its past failures, integrating these reflections into prompts to guide future actions."*

### Advantages
254 references — genuinely comprehensive; the five-component framework gives standard vocabulary; 307 citations despite a young venue; the problem-solving vs. world-simulation split cleanly locates your system.

### Disadvantages
Survey with no evaluation or empirical comparison. The five components are **descriptive rather than prescriptive** — they classify systems without predicting which designs work. General MAS framing with no document- or retrieval-specific content. It also flags a structural risk that applies to you: centralised designs are *"susceptible to single points of failure and communication delays"* — in your graph, the Critic is that central point.

⚠️ **Venue caution.** *Vicinagearth* launched in 2024. **Verify it is Scopus-indexed before relying on it in a Scopus-constrained bibliography.** If not, substitute **Wang et al. (2024), *Frontiers of Computer Science*, [10.1007/s11704-024-40231-1](https://doi.org/10.1007/s11704-024-40231-1)** — 1,320 citations, established venue.

### Datasets
**None** — survey. Models discussed: GPT-3/3.5/4, ChatGPT, LLaMA, Llama2, PaLM, BERT.

### Relevance to ResearchGPT
Use it to **describe your architecture in the field's own vocabulary**, and note honestly where you don't fit: four of the five components map cleanly onto your system, but **"evolution" does not** — your agents don't learn across runs. Your adaptation is *within-run* (the Critic loop). Naming that gap reads as rigour and gives you a clean Future Work item.

The DEPS description (plan revision when *"indications of plan failure emerge"*) and CoVe (*"verification queries to check the draft's factual accuracy before producing a refined response"*) are the two closest published analogues to your Critic and Verifier respectively. Cite both — they show your design pattern is recognised, while neither has been applied to literature review.

---

## C3-12 · Yang et al. (2025) — AutoHMA-LLM **[ABSTRACT ONLY]**

**Citation.** Yang, T., Feng, P., Guo, Q., Zhang, J., Zhang, X., Ning, J., Wang, X., & Mao, Z. (2025). *IEEE Transactions on Cognitive Communications and Networking.* DOI [10.1109/tccn.2025.3528892](https://doi.org/10.1109/tccn.2025.3528892) · 38 citations

**Problem.** Coordinating heterogeneous agents in *"complex, dynamic environments"* is expensive and unstable; coordination overhead becomes the bottleneck.

**Methodology.** Multi-tier hybrid architecture: *"a cloud-based LLM as the central planner alongside device-specific LLMs and Generative Agents,"* combined with classical control algorithms. Improves execution through *"refined task scheduling and real-time feedback mechanisms."*

**Results.** **+5.7% task completion accuracy, −46% communication steps, −31% token usage and API calls** versus baselines, across logistics, inspection, and search & rescue scenarios.

**Advantages.** **Reports the efficiency numbers almost every multi-agent paper omits.** Validates tiered model assignment (strong central planner + smaller device models) as a cost-control pattern. IEEE Q1.

**Disadvantages.** Robotics/IoT domain — transfer is architectural only. Requires cloud LLM for the planner. Scenario-based evaluation with no public benchmark. "Heterogeneous" means heterogeneous *hardware*, whereas your agents are heterogeneous in *role* — a weaker analogy than it looks.

**Datasets.** Logistics, inspection, search & rescue scenarios. No public dataset.

**Relevance.** **Your defence against "six agents is over-engineering — what does it cost?"** This is peer-reviewed evidence that a well-designed multi-agent system can *reduce* token usage and API calls (−31%) by routing work to appropriately-sized models — precisely your design (`PROJECT_PLAN.md §6.1`: free-tier frontier model for Planner/Critic, small model for extraction, local CPU models for embedding/reranking/verification). Report your own `trace.jsonl` token counts alongside theirs; a published comparison point turns your cost table from a footnote into a result. Pair with ChatDev's contrary admission that multi-agent costs more — the difference is tiering.

---

# C4 — SCIENTIFIC DOCUMENT UNDERSTANDING & IE

## C4-13 · Dagdelen et al. (2024) — Structured Information Extraction from Scientific Text ✅ FULL TEXT

**Citation.** Dagdelen, J., Dunn, A., Lee, S., Walker, N., Rosen, A. S., Ceder, G., Persson, K. A., & Jain, A. (2024). *Nature Communications* 15. LBNL / UC Berkeley. DOI [10.1038/s41467-024-45563-x](https://doi.org/10.1038/s41467-024-45563-x) · **645 citations** · 68 references

### Problem
*"Extracting structured knowledge from scientific text remains a challenging task for machine learning models."* Scientific facts live in prose that resists conversion into database records.

### Methodology
**LLM-NERRE**: joint named entity recognition and relation extraction by fine-tuning **GPT-3** and **Llama-2** (the **70B** version, `llama-2-70b-hf`, with **8-bit quantization**). Three materials-chemistry tasks: **host–dopant linking**, **metal-organic framework (MOF) cataloguing**, and **general composition/phase/morphology/application extraction**.

Critically, they compare **output schema formats**: a **JSON schema** versus **English-sentence schemas** (`Doping-English`, `DopingExtra-English`). For `DopingExtra-English` they *"introduce two additional entities: modifiers and result, without explicit linking (i.e., NER only)."*

**Two scoring regimes**, which is the methodologically interesting part:
1. *"A relation F1 computed on a stringent exact word-match basis (i.e., how many words are correctly linked together exactly as they appear in the source text prompt)."*
2. *"A holistic information extraction F1 based on manual inspection by a domain expert, which doesn't require words to match exactly"* — they call this the **"manual score."**

Their justification for the second is important: *"'Bi2Te3 nanoparticles' and 'Bi2Se3 nanoparticles' have very high similarities via Jaro-Winkler (0.977) and character-level BLEU-4 (0.858), but these two phrases mean entirely different things—the material's chemistry is wrong."* Surface-similarity metrics are actively misleading for scientific extraction.

Evaluation: hold-out test set for doping (77 sentences); five-fold cross-validation for general and MOF tasks.

### Results
- **Dopant task:** **Llama-2 achieves precision 0.836, recall 0.807, F1 0.821** — *"an improvement of 13% over GPT-3."*
- **General and MOF tasks:** exact-match F1 *"generally ~30% lower than in the host-dopant task"*, landing in the **0.3–0.6** range. Best relations: general **formula–application F1 = 0.537**; MOF **name–application F1 = 0.573**, **name–guest species F1 = 0.616**. *"Formula-acronym and formula-description relationships are much less reliable."*
- **GPT-3 achieves the highest F1 for the General and MOF tasks**; Llama-2 wins the dopant task — no single model dominates.
- **Baselines:** seq2rel **precision 0.420 / recall 0.605 / F1 0.496**; MatBERT-Proximity **0.390**. Both *"substantially lower than any of the LLM-NERRE models."*
- **Schema format interacts with model:** for GPT-3, `DopingExtra-English` and `Doping-English` schemas score highest; *"the opposite observation is true of the Llama-2 models, where the JSON format outperforms both English schemas and the DopingExtra-English schema suffers from low precision (0.694)."*
- **Training-set size (Fig. 4):** *"output sequences are not properly structured for training set sizes below ~10 samples, but there is a sharp increase in the number of correctly structured outputs at ~20 samples, which seems to be the minimum number of examples GPT-3 needs to learn a desired output format when using simple sentence-type schemas."*
- Including **corrected formulae** in training outputs *"results in LLMs that automatically resolve extracted entities to cleaner forms."*
- The authors defend the apparently low scores: F1 of 0.3–0.6 is *"on first inspection, seemingly too low to be useful for a large scale information extraction task"* — but the manual score shows *"some of the best features of this method are not directly shown by F1 scores."*

### Advantages
Direct precedent for **LLM-generated structured JSON from scientific text**; Nature Communications with 645 citations; substantially beats both a seq2rel and a domain-BERT baseline; flexible across three distinct schemas; **the dual scoring regime is a methodological contribution you can reuse**.

### Disadvantages (their own)
- *"One limitation of our model is that valid output schema formatting is not rigorously enforced in the generation step."*
- *"Failures predominantly occur when the sample exceeds the prompt-completion token limit of the LLM (early termination), which in this work was 512–1024 tokens."*
- *"Another limitation is the tendency of LLMs to generate or invent information that is not actually present in the input text"* — hallucination, in an extraction task.
- *"Scientific information often cannot be modeled as simple pairwise relations between entities."*
- Reproducibility and security concerns with hosted models: *"the models cannot be shared, and the entity controlling the LLM may at any time change the model, amend the fine-tuning method, or revoke access."*
- Requires fine-tuning; zero-shot *"may make scientific information extraction more accessible at the expense of accuracy."*
- **No evidence-span or provenance mechanism** — records are extracted without linking back to source text.

### Datasets
Three materials-chemistry tasks (dopant/host, MOF, general composition-phase-morphology-application); 77-sentence hold-out for doping; PubMed referenced. Models: GPT-3, Llama-2-70B, SciBERT, PubMedBERT, MatBERT, seq2rel.

### Relevance to ResearchGPT
**Your strongest citation for the four-field schema** — Nature-family validation that structured JSON extraction from papers is an established technique.

Four concrete, actionable transfers from the full text that the abstract did not contain:

1. **Use ~20 few-shot examples in your Extractor prompt.** Their sharp structural-reliability threshold at ~20 samples is the best available empirical guidance, and it costs you nothing to follow.
2. **Adopt their dual scoring regime for Extraction F1.** Report both exact-match F1 *and* a manual/expert score. Their Bi2Te3/Bi2Se3 example is the perfect justification — and your fields (*methodology*, *critique*) are **far more paraphrase-prone** than chemical formulae, so exact match will understate your system badly. This is a well-evidenced way to make your 10-paper annotation exercise more informative.
3. **Expect F1 in the 0.3–0.6 band, and defend it as they do.** They explicitly argue those numbers are more useful than they look. You can cite a Nature Communications paper making that argument rather than making it unaided.
4. **Schema format matters and interacts with the model.** JSON was best for Llama-2, English-sentence schemas for GPT-3. Worth a quick A/B on your chosen free-tier model in Week 2 — it is cheap and could materially improve parse reliability, which `PROJECT_PLAN.md §11` flags as a key risk.

Finally, note the honest boundary: their entities are **objective and nominal** (a dopant is or isn't present); yours are **interpretive** (*disadvantages*, *critique* are judgements). Expect lower agreement and say so before a reviewer does. And their missing **evidence-span mechanism** is precisely the gap your `evidence_spans` design fills — with C4-15 below supplying the evidence for why it matters.

---

## C4-14 · Sarol et al. (2024) — Assessing Citation Integrity in Biomedical Publications ✅ FULL TEXT (Europe PMC)

**Citation.** Sarol, M. J., Ming, S., Radhakrishna, S., Schneider, J., & Kilicoglu, H. (2024). *Bioinformatics* 40(7). University of Illinois. DOI [10.1093/bioinformatics/btae420](https://doi.org/10.1093/bioinformatics/btae420) · PMC11231046 · 8 citations · 38 references

### Problem
**Quotation errors** — citations that point to a real paper which does not support the claim made. Prior work distinguishes *"citation accuracy and quotation accuracy errors,"* and *"a meta-analysis in 2008 found that quotation accuracy studies reported a median error rate of 20%."* The authors note *"citation integrity has not been studied from a NLP perspective."*

### Methodology

**Corpus construction.** 100 highly-cited biomedical publications and the citations to them. For annotation *"we extracted the paragraph containing the citation marker and highlighted the citation marker of interest."* Three-part task: **citation context identification → evidence segment identification → citation accuracy classification.** Labels extend prior quotation-error classifications, and they *"propose an additional minor error category, ETIQUETTE, and extend the definition of INDIRECT."* One category definition worth noting: **NOT_SUBSTANTIATE** — *"the citation is relevant to the content of the reference article but the cited reference fails to substantiate all statements made in the citing paper."* A final reviewer pass ensured consistency.

**NLP pipeline.** Because *"reference articles are longer than 512 tokens (the maximum number of tokens allowed by models like PubMedBERT),"* they *"first identified relevant sentences from the reference article using a sentence retriever model and trained models that used the citation context along with the retrieved sentences to assess citation accuracy in a single step."* Retrieval: **BM25 + MonoT5 reranker**, top-20. Classification: fine-tuned **MultiVerS**. Also evaluated **GPT-3.5-turbo-0613 and GPT-4** few-shot in-context learning (tested February 2024). Metrics: precision, recall, F1; **recall@k and MRR** for retrieval, where *"high recall@k and low MRR are preferred."*

### Results

**Corpus statistics.** *"A total of 3063 citation instances corresponding 3420 citation context sentences and 3791 evidence sentences were annotated (1.12 context and 1.24 evidence sentences per citation)."* **39.18% contained accuracy errors.**

**⚠️ Inter-annotator agreement — the most important number in this paper.** *"Agreement was lower on evidence sentence and accuracy label annotations, although the agreement improved in the second phase to fair agreement levels (evidence sentence: 0.20 in the first phase to 0.37 in the second; accuracy labels: 0.18–0.31)."*

**Citation context identification.** *"The baseline method (simply labeling the citance as the citation context) yields perfect precision, because citation context always includes the citance, and leads to our best results (0.94 F1)."* — the trivial baseline wins.

**Evidence retrieval.** *"Retrieving top-20 sentences with BM25 + MonoT5 reranker has a recall of 0.53, which indicates significant differences between the annotated and automatically retrieved sentences."* **Nearly half the gold evidence is never retrieved.**

**Accuracy classification.** Best model (citation sentences as context + BM25/MonoT5 top-20 + fine-tuned MultiVerS): **0.59 micro-F1, 0.52 macro-F1.** GPT-4 ICL: **0.65 micro-F1, 0.45 macro-F1** — and *"GPT-4 has a strong performance with 0.80 F1 score and 0.90 recall"* on the ACCURATE class, but *"these models perform poorly on the NOT_ACCURATE category, identifying only a few cases of this category leading to very low recall and F1."*

**Error propagation.** *"In cases where some gold evidence sentences are retrieved by the sentence retriever, 63% of the predictions are correct... when no gold evidence sentence is retrieved, 51% are correctly predicted."* Using gold citation contexts *and* gold evidence segments *"did improve citation accuracy classification, suggesting that span-level citation context classification could benefit the accuracy classification task."*

### Advantages
Architecturally near-identical to your Verifier, with per-stage numbers; **exceptionally honest reporting**; first NLP-focused citation-integrity corpus; public corpus and model at `github.com/ScienceNLP-Lab/Citation-Integrity/`; the 39.18% error rate is a striking motivating statistic.

### Disadvantages
Absolute performance is low (0.59 micro-F1 is not deployable as an autonomous filter); *"citation quotation errors are often subtle, and it is currently challenging for NLP models to identify erroneous citations"*; fair-only inter-annotator agreement, which the authors flag as a limitation of their own annotation; biomedical domain with a biomedically-pretrained MultiVerS; modest corpus (100 reference articles); requires fine-tuning plus a MonoT5 reranker — heavier than your CPU budget.

### Datasets
Own annotated corpus (100 publications, 3,063 citation instances, 39.18% erroneous). MultiVerS model; PubMed source. Models: BM25, MonoT5, PubMedBERT, MultiVerS, GPT-3.5, GPT-4.

### Relevance to ResearchGPT
**The most important calibration reference in this entire document. Read it before you set a single verifier target.**

**1. The 0.31 inter-annotator agreement reframes your whole evaluation.** Trained annotators on a carefully designed task, with a final consistency review, agreed only 0.18–0.31 on accuracy labels. Three implications:
- A verifier at 0.59 F1 is **not obviously worse than a human**, because humans don't agree with each other either. That is a *defence*, not an excuse — but you must present the agreement figure to make it.
- Your 50-claim human spot-check (`PROJECT_PLAN.md §9.1`) should use **two annotators and report agreement**, not one annotator treated as ground truth. A single annotator's labels at κ≈0.3 reliability is a weak measuring instrument.
- Your 2-annotator Likert study should report **Cohen's κ alongside means**, as already planned — this paper is the justification for why that matters.

**2. Recalibrate your targets.** `PROJECT_PLAN.md §9` targets groundedness ≥ 0.9. A careful fine-tuned pipeline reaches 0.59 micro-F1 on real citations. Those measure different things, and the mismatch is the trap: 0.9 is defensible only as *"fraction of sentences carrying ≥1 supporting span"* — which measures that the filter ran, i.e. the circularity trap in `§9.6`. **Verifier precision against human judgement is the real number, and 0.59 is what good looks like.**

**3. Your retrieval will cap your verifier.** Their BM25+MonoT5 top-20 recall is **0.53**, and accuracy drops from 63% to 51% when gold evidence isn't retrieved. Your Verifier searches your *own* retrieved chunks — so **retrieval recall is an upper bound on verification quality**. This is the strongest argument for not skipping the Day 6–7 retrieval buffer, and it means you should report retrieval recall and verifier accuracy *together*.

**4. Train, don't prompt.** GPT-4 in-context learning was better on accurate citations (0.80 F1, 0.90 recall) but **poor at detecting erroneous ones** — the exact failure mode you cannot afford, since catching bad citations is the entire point. This is direct peer-reviewed support for `PROJECT_PLAN.md §4.2`'s decision to fine-tune a verifier rather than prompt an LLM.

**5. Your Introduction statistic.** 39.18% of citation instances in highly-cited biomedical papers contain accuracy errors, against a historical median of 20%. One sentence, and the project is motivated.

---

## C4-15 · Li, Lee & Ouyang (2024) — Cited Text Spans for Citation Text Generation ✅ FULL TEXT

**Citation.** Li, X., Lee, Y., & Ouyang, J. (2024). *4th Workshop on Scholarly Document Processing (SDP) @ ACL 2024*, pp. 90–97. UT Dallas. DOI [10.18653/v1/2024.sdp-1.9](https://doi.org/10.18653/v1/2024.sdp-1.9) · 3 citations

### Problem
Citation generation must *"ground its outputs to the content of the cited paper to avoid nonfactual hallucinations,"* but because scientific documents are long, *"existing abstractive approaches have conditioned only on cited paper abstracts."* Their central claim: **that shortcut teaches models to hallucinate.**

They add a second problem with existing work: *"existing CTS retrieval systems are inappropriate for the citation generation task because they use the gold citation text as the retrieval query"* — a form of leakage that makes published CTS retrievers unusable in a real setting. And *"automatic CTS retrieval systems trained on these datasets give low performance (F1 < 0.2)."*

### Methodology
Condition generation on the **cited text span (CTS)** rather than the abstract. Since manual CTS annotation is prohibitive and existing datasets are too small, they use **distant labelling**: ROUGE-based retrieval scoring candidate sentences by *"the average of the ROUGE-1 and -2 recall scores,"* with NLTK stop-word removal. They note ROUGE-based retrieval *"does not use GPUs, and thus computationally more efficient"* than dense retrieval, and that BERTScore *"slightly underperforms ROUGE in all our experiments."*

**Four input settings compared:** **Abstract** (the existing approach), **Context CTS** (retrieved using only citation context sentences — the realistic setting), **Oracle CTS** (retrieved using the gold citation text — an upper bound), and **Keyword CTS** (their proposed **human-in-the-loop, keyword-based** retrieval).

**Generators:** RAG-FiD and LED. **Faithfulness metrics:** **QuestEval** and **ANLI** entailment. ~12,000 CTS retrieved in total.

### Results

**Table 3 — quality of the generation *input* (token coverage and faithfulness w.r.t. target citation):**

| Setting | ROUGE-L | QuestEval | ANLI |
|---|---|---|---|
| Abstract | 0.290 | 0.263 | 0.868 |
| Context CTS | 0.400 | 0.265 | **0.964** |
| Oracle CTS | **0.533** | **0.271** | 0.955 |
| Keyword CTS | 0.440 | **0.271** | 0.949 |

**Table 4 — generation quality:**

| Setting | RAG-FiD BLEU | METEOR | R-L | LED BLEU | METEOR | R-L |
|---|---|---|---|---|---|---|
| Abstract | 0.214 | 0.397 | 0.194 | 0.142 | 0.380 | 0.189 |
| Context | 0.216 | 0.397 | 0.197 | 0.163 | 0.359 | 0.194 |
| Oracle | **0.258** | **0.461** | 0.292 | **0.216** | **0.450** | **0.312** |
| Keyword | 0.239 | 0.437 | 0.262 | 0.182 | 0.404 | 0.270 |

**⚠️ Table 6 — faithfulness of the *generated* citation w.r.t. its input (the decisive result):**

| Setting | RAG-FiD R-L | **RAG-FiD ANLI** | LED R-L | **LED ANLI** |
|---|---|---|---|---|
| Abstract | 0.556 | **0.745** | 0.591 | **0.744** |
| Context | 0.641 | **0.959** | 0.626 | **0.954** |
| Oracle | 0.726 | 0.940 | 0.682 | 0.950 |
| Keyword | 0.630 | 0.941 | 0.604 | 0.946 |

**Abstract-conditioned generation scores ~0.745 ANLI faithfulness; every CTS variant scores ~0.94–0.96.** A gap of **~21 points**, consistent across two different generators.

Their interpretation: *"CTS-based generations are more similar to their inputs, suggesting that models trained on CTS are more extractive. From this finding, along with the lower faithfulness scores in Table 6, we can infer that Abstract produces more non-factual hallucinations that distort the ideas of the cited paper."*

Distant labelling validation: top-40 distantly-labelled CTS achieve high recall against human-labelled CTS, and are *"of comparable quality to existing human-annotated datasets."*

### Advantages
**Empirically demonstrates — twice, across two generators — that abstract-only conditioning causes hallucination.** Distant labelling removes the annotation bottleneck. ROUGE-based retrieval is CPU-friendly. Identifies and avoids the gold-citation-as-query leakage in prior work. Human-in-the-loop keyword retrieval is a realistic deployment compromise.

### Disadvantages (their Limitations, verbatim highlights)
- **CTS retrieval remains unsolved.** *"CTS retrieved with only the citation context sentences is not satisfactory... the automated retrieval part requires further investigation."* Note the tension: Context CTS scores best on ANLI but worst among CTS variants on ROUGE-L.
- **Human-in-the-loop is a barrier.** *"This human-in-the-loop setting might be unfriendly to less-experienced researchers who are not sure what keyword to use."*
- **ROUGE labelling is lexical.** *"ROUGE-based labeling selects CTS with high lexical overlap with the target citation and may miss CTS that are semantically relevant but less lexically similar."*
- They explicitly **do not claim SOTA**: *"we simply claim that using CTS can improve citation text generation performance over using cited paper abstracts."*
- **Plagiarism risk.** More extractive generation *"does not explicitly address the plagiarism issue; additional post-processing, such as a rewriting module, should be used."*
- Workshop venue; 3 citations. OpenAlex's stored abstract for this paper has body-text fragments appended — read the PDF, not the metadata.

### Datasets
**S2ORC**-derived; **ANLI** and **QuestEval** as faithfulness evaluators; ~12,000 retrieved CTS; 239 cited papers from AbuRa'ed et al. (45 excluded for XML errors). Models: RAG-FiD, LED, BART, BERT, SciBERT, RoBERTa, T5, BM25, DPR.

### Relevance to ResearchGPT
**This paper turns two of your design decisions from preferences into evidence-backed choices, and flags one as a genuine risk.**

**1. It justifies `evidence_spans`.** `RESEARCHGPT_SPEC.md §7.3` requires every extracted field to carry chunk ID and character offsets — span-level rather than document-level grounding. Li et al. show why: models conditioned on whole abstracts **learn to hallucinate**, with a measured 21-point faithfulness penalty. That is far stronger than "spans are more precise."

**2. ⚠️ It seriously undermines your abstract-only degraded mode.** `PROJECT_PLAN.md §11` proposes falling back to abstracts for paywalled papers. This paper measures that fallback's cost: **ANLI faithfulness 0.745 vs ~0.95**. Since your graded criterion is not hallucinating, this is not a minor degradation. Three options, in order of preference:
   1. **Abstract-only papers may be cited as existing but may not supply verified claims** — they enter the reference list and the insight table, never the claim-verified write path.
   2. Flag them via `text_availability` and **report the split**, as the plan already suggests.
   3. Exclude them entirely.

   Whichever you pick, cite this paper as the reason — it converts an awkward limitation into an evidence-based design decision.

**3. Note the tension with your base paper.** Aytar et al.'s **"Abstract First"** strategy prioritises abstracts and reports a 15× Context Relevance gain; Li et al. show abstracts are the *worst* grounding input. Both can be true — **abstracts may be good for *finding* the right paper and bad for *grounding a claim* about it.** That distinction is worth a paragraph in your Discussion, and it is exactly the kind of synthesis across sources that a literature review chapter is supposed to produce.

**4. A cheap practical borrow.** Their ROUGE-based distant labelling *"does not use GPUs"* and matched dense retrieval. If your CPU-only reranking proves too slow on Day 4, ROUGE-based candidate scoring is a validated fallback.

---

# C5 — AUTOMATED SURVEY & REVIEW GENERATION

## C5-16 · Kasanishi et al. (2023) — SciReviewGen ✅ FULL TEXT

**Citation.** Kasanishi, T., Isonuma, M., Mori, J., & Sakata, I. (2023). *Findings of ACL 2023*, p. 6700. University of Tokyo / RIKEN AIP. DOI [10.18653/v1/2023.findings-acl.418](https://doi.org/10.18653/v1/2023.findings-acl.418) · 71 references

### Problem
*"Automatic literature review generation is one of the most challenging tasks in natural language processing,"* and progress was blocked by data: *"the absence of large-scale datasets has been a stumbling block."*

### Methodology

**Dataset construction.** *"We release SciReviewGen, which consists of over 10,000 literature reviews **in the field of computer science** and 690,000 papers cited in the reviews"* — built from S2ORC. **Note the domain: this is a CS dataset, which matters for you.**

Quality control was two-stage and is worth knowing because it validates the data: human annotators screened candidate reviews — *"the annotators classified 583 of 889 candidate papers as suitable and 306 as unsuitable, resulting in Cohen's kappa = 0.66"* — and those labels trained a **SciBERT classifier** which *"achieved precision = 88%, recall = 97%, and f1 = 92% on the test split"* to filter the remainder automatically.

**Model.** They propose **QFiD (Query-weighted Fusion-in-Decoder)**, *"a simple extension of FiD for query-focused MDS"* that weights each input document by its relevance to the query. Baselines: LEAD, LexRank, **Ext-oracle** (*"greedily selects l sentences that maximize the ROUGE-2 scores between the selected sentences and the target summary"*), Big Bird, and vanilla FiD. Trained **ten epochs, single run**, checkpoint selected on validation ROUGE-2, decoded with **beam search, beam_size = 4**.

### Results

**Table 3 — ROUGE on SciReviewGen:**

| Model | ROUGE-1 | ROUGE-2 | ROUGE-L |
|---|---|---|---|
| LEAD | 23.09 | 4.68 | 11.72 |
| LexRank | 24.40 | 5.02 | 12.52 |
| Ext-oracle | 29.43 | **10.13** | 14.88 |
| Big Bird | 24.25 | 4.08 | 15.30 |
| FiD | 32.40 | 6.75 | 16.17 |
| **QFiD (ours)** | **34.00** | 7.75 | **16.52** |

A striking observation they draw out: *"FiD-based models outperform ext-oracle regarding ROUGE-1 and ROUGE-L, which shows the difficulty of our task since **simply copying sentences from the cited papers does not work well**."* Review generation is genuinely abstractive — extraction is not enough.

**Human evaluation.** Ground-truth chapters were rated superior / comparable / inferior to QFiD output. Result: *"approximately **30% of the generated chapters are competitive or superior to human-written reviews** concerning overall"* — but also that automatic generation *"does not achieve human-level performance."* **Inter-annotator agreement: Cohen's kappa = 0.212**, which they defend as *"reasonable because the number of categories is three."*

Their honest conclusion: *"Currently, automatic literature review generation can be effectively utilized with human revision, such as writing assistance tools, by providing drafts of literature reviews."*

### Advantages
The field's reference dataset, at scale, **in computer science**; rigorous two-stage quality control with reported agreement; a genuinely informative baseline set (the ext-oracle comparison is the useful one); honest human evaluation that reports the negative result alongside the positive; CC BY-NC 4.0 release with code.

### Disadvantages (their Limitations, verbatim — and this list is essentially a specification for your system)
- **Abstract-only inputs.** *"In our experiment, we use only abstract text as the input text for literature review generation. However, in writing literature reviews, a writer reads the full text of each cited paper... Therefore, the input data are insufficient to write a complete literature review."*
- **Limited full-text coverage.** *"As only 70% of the cited papers have access to the body text in our SciReviewGen, a dataset containing full-text information is required for further research."*
- **No cross-chapter coherence.** *"As our QFiD and baseline models generate each chapter independently, they cannot consider the relationships between chapters."*
- **No inter-paper relations.** *"The relations between each cited paper are considered in the actual literature review writing process (e.g., which paper is the first on the topic and which is the following). However, these relationships are not considered in the models."*
- **Factual errors block deployment.** *"The generated text contains incorrect information to a certain extent. Therefore, we cannot publish it without human revision."*

### Datasets
**SciReviewGen** (own; 10,000+ CS reviews, 690,000 cited papers, from **S2ORC**). Also referenced: Multi-XScience, PubMed, arXiv, SPECTER, Semantic Scholar, XSum. Models: FiD, QFiD, Big Bird, BART, SciBERT, Galactica, GPT-3.

### Relevance to ResearchGPT
**Their limitations list reads like a requirements document for your system** — cite it that way.

| SciReviewGen limitation | ResearchGPT response |
|---|---|
| Only abstracts as input | Full-text PDF parsing + chunking with `evidence_spans` |
| Chapters generated independently | Writer synthesises across themes; Critic assesses global coverage |
| Inter-paper relations ignored | Thematic clustering + `contradiction_pairs` |
| Output contains incorrect information | Verifier removes unsupported claims before writing |

That is four of their five stated limitations, each mapped to a component you are already building. This is the strongest possible framing for your Introduction, and it is stronger than an abstract-level citation because these are the authors' own words about their own system.

**Three further practical notes.** (i) The dataset is **computer science**, which matches your domain — better for your gold sets than I assumed from the abstract. (ii) Their **Cohen's kappa of 0.212** on a three-way human judgement of review quality is another data point for the theme that humans agree poorly on these judgements (cf. Sarol et al. at 0.18–0.31, CiteBench at 0.18–0.42): **do not expect your own human evaluation to produce clean agreement, and report κ so the reader can calibrate.** (iii) Their ext-oracle result tells you that a purely extractive fallback would underperform — your Writer genuinely needs to abstract, which raises the stakes for verification.

---

## C5-17 · Bao et al. (2025) — SurveyGen / QUAL-SG ✅ FULL TEXT ★ RECOMMENDED BASE PAPER

**Citation.** Bao, T., Nayeem, M. T., Rafiei, D., & Zhang, C. (2025). *EMNLP 2025 (Main)*. DOI [10.18653/v1/2025.emnlp-main.136](https://doi.org/10.18653/v1/2025.emnlp-main.136)

### Problem
*"While large language models (LLMs) have shown promise in generating survey texts, the lack of standardized evaluation datasets critically hampers rigorous assessment of their performance against human-written surveys."*

### Methodology

**Dataset.** *"SurveyGen, a large-scale dataset comprising over 4,200 human-written surveys with **section-level structures**, including cited references and rich metadata capturing **citation performance, author influence, and venue reputation**"* — 242,143 cited references. Per reference they *"extracted essential bibliographic details, including the title, abstract, DOI, and citation count."* Sources include OpenAlex, Semantic Scholar, S2ORC and arXiv.

**System.** **QUAL-SG** is *"a quality-aware extension of the naive RAG framework designed to improve the quality of retrieved literature for survey generation."* It reranks retrieved literature using quality indicators derived from the metadata above — i.e. it is a **venue/citation-quality-aware reranker bolted onto RAG**.

**Three task settings** by degree of human involvement: Task 1 fully-LLM generation; **Task 2 fully automatic RAG (no human intervention)**; Task 3 human-guided (accurate references and outlines provided).

**Evaluation across three axes:** content quality (semantic similarity to human surveys + ROUGE), **citation quality** (precision/recall/F1 of citation overlap), and structural consistency. Evaluated on a subset of **120 relatively short surveys**.

### Results

**Content quality (Task 2, fully automatic).** *"LLaMA-3.1-70B achieves the highest similarity to human-written surveys (**82.43%**) and the highest ROUGE-L (**15.36%**)."*

**⚠️ The headline negative result.** *"Citation accuracy remains a major limitation: the best-performing model achieves only **35.84%**, indicating that **relying solely on LLMs for survey generation is insufficient for ensuring reliable reference generation**."*

**QUAL-SG's gain.** *"Our proposed QUAL-SG achieves the highest citation quality (F1 score of **16.73%**), outperforming Naive-RAG and Fully-LLMGen by **10.80%** and **8.97%**, respectively."*

**Table 5 — citation quality vs other ranking models:**

| Model | P% | R% | F1% |
|---|---|---|---|
| UPR (Sachan et al., 2022) | 10.28 | 10.63 | 10.45 |
| RankGPT (Sun et al., 2023) | 14.55 | 15.09 | 14.81 |
| **QUAL-SG (ours)** | **15.87** | **17.71** | **16.73** |

**Task 3 (human-guided).** LLaMA-3.1-70B reaches **84.39%** content similarity and **17.16%** ROUGE-L; Claude-3.7-Sonnet gets the highest KPR (**54.67%**). Their observation: *"when LLMs are provided with more accurate references and outlines, their generated content quality improves accordingly compared to Task 2, which involves no human intervention."*

Note the scale of the numbers: even the best citation-quality F1 is **16.73%**. Survey generation citation quality is, in absolute terms, very poor.

### Advantages
Exact task match; large recent dataset with section-level structure and quality metadata; the human-involvement gradient isolates *where* automation fails; QUAL-SG is a peer-reviewed instance of quality-aware retrieval — i.e. your venue tiering — with a measured effect size; compares against two published rankers rather than only a naive baseline.

### Disadvantages (their Limitations, verbatim)
- **Input limitation.** *"For copyright reasons, our approach is restricted to using only abstracts and bibliographic metadata of the retrieved papers, without access to full-text content. This limitation may hinder the LLM's ability to capture finer-grained details... the generated surveys may lack depth and completeness."*
- **No post-generation refinement.** *"To reduce API costs, we did not perform post-generation refinement, such as language polishing, citation formatting, structural adjustments."* No figures, tables or diagrams either.
- **Data contamination.** *"Some surveys or key references used are open access and may have been included in the training data of the LLMs."* They argue it affects all baselines equally.
- **Scope.** Evaluation limited to 120 short surveys *"selected to balance cost and feasibility in academic settings."*

### Datasets
**SurveyGen** (own; 4,200+ surveys, 242,143 references). References SciReviewGen, Multi-XScience, S2ORC, OpenAlex, Semantic Scholar, PubMed, arXiv. Models: GPT-4, Claude, Gemini, LLaMA-3.1-70B.

### Relevance to ResearchGPT
**This should be your base paper, and the full text makes the case stronger than the abstract did.**

**1. Their headline finding is your problem statement, with a number attached.** *"Citation accuracy remains a major limitation: the best-performing model achieves only 35.84%... relying solely on LLMs for survey generation is insufficient for ensuring reliable reference generation."* You are not asserting a gap — the authors of your base paper measured it.

**2. QUAL-SG is a directly comparable component, with a directly comparable number.** Their quality-aware reranking lifts citation-quality F1 to 16.73%, beating naive RAG by 10.80 points and two published rankers (UPR 10.45, RankGPT 14.81). Your venue tiering does the same job. **This means your ablation of venue tiering is not self-referential — you have three published baselines to sit beside.**

**3. Their input limitation is one you can actually beat.** They are *"restricted to using only abstracts and bibliographic metadata... without access to full-text content"* — for copyright reasons. You parse open-access PDFs and ground claims in `evidence_spans` from full text. Combined with Li et al. (C4-15), which measures a **21-point faithfulness penalty for abstract-only conditioning**, this is a concrete, defensible advantage rather than a rhetorical one. It is arguably the single clearest way your system improves on the base paper.

**4. Their Task 3 result predicts something about your Critic.** Content quality improved when models were given *"more accurate references and outlines."* Your Planner produces the outline and your Critic improves the references across iterations — so the Task 2 → Task 3 gap is, roughly, the headroom your loop is trying to capture *automatically*. That is a clean way to frame what the Critic is for, and it gives you a rough expected effect size.

**5. Set your expectations by their numbers.** Best citation-quality F1 in a peer-reviewed EMNLP system is **16.73%**. If your system reports dramatically higher on a comparable metric, check your measurement before celebrating.

**Action:** update `RESEARCHGPT_SPEC.md §1.2–§1.3` to make SurveyGen the base paper; keep Aytar et al. as related work.

---

## C5-18 · Funkquist et al. (2023) — CiteBench ✅ FULL TEXT

**Citation.** Funkquist, M., Kuznetsov, I., Hou, Y., & Gurevych, I. (2023). *EMNLP 2023*, p. 7344. UKP Lab, TU Darmstadt. DOI [10.18653/v1/2023.emnlp-main.455](https://doi.org/10.18653/v1/2023.emnlp-main.455)

### Problem
*"Existing studies are based upon widely diverging task definitions, which makes it hard to study this task systematically."* Citation-text-generation research cannot accumulate because every paper defines the task differently.

### Methodology
**CiteBench** unifies multiple diverse datasets (ABURAED, XING, CHEN Delve, LU Multi-XScience) into one benchmark with standardised evaluation. Metrics: **ROUGE-L** and **BERTScore** (both via HuggingFace implementations, *"without additional stemming and lemmatization,"* following the GEM benchmark). Baselines include LED models (`led-base`, `led-large-arxiv`) trained on 4 GPUs, with **transfer-learning experiments** — each `led-base-[X]` fine-tuned on dataset X and evaluated across all others.

Beyond the standard metrics they add **discourse-schema analysis with KL divergence** — comparing the distribution of citation intents in generated versus gold text — and a human qualitative evaluation on a 50-instance subsample.

### Results
- **Reproducibility finding.** Different ROUGE package configurations produce *"a substantial ROUGE-1/L score increase of approx. 3 points,"* leading them to conclude: *"This underlines the importance of clearly specifying the ROUGE package and configuration in future evaluations."*
- **Reference points.** Xing et al. (2020) report ROUGE-L **30.63** for their best supervised task-specific model and **18.82** for LEAD.
- **Transfer learning.** *"We observe non-trivial ability for transfer learning among the baselines"* — models do partially transfer across citation-generation datasets.
- **Metric–discourse correlation is imperfect.** *"While the two best-performing baseline models in terms of ROUGE and BERTScore also achieve the lowest KL divergence on both discourse schemata, the correlation is not perfect."*
- **⚠️ Human evaluation is the damning part.** *"None scored higher than 3 on the consistency scale: while the generated citation texts can be topically related to the gold reference, in most cases they **miss key factual details about the cited papers** and the contextual information in the reference."*
- **Human agreement.** *"The estimated Quadratic Cohen's kappa agreement between annotators on a 50-instance subsample was approx. **0.50 for readability** and ranging between **0.18 and 0.42 for consistency**, depending on the annotator pair."*
- **Dataset heterogeneity.** Self-reference keywords ("our work", "in this paper", "we present") range from *"∼1% in the single-sentence citation text datasets (ABURAED and XING) to up to 14% in CHEN Delve"* — the datasets are not measuring the same thing.
- Citation-intent classification reference points: F1 **67.9** on ACL-ARC; best model **90.8**.

### Advantages
Solves a real fragmentation problem; cross-dataset transferability testing is rare and rigorous; the discourse-schema/KL analysis goes beyond n-gram overlap; the ROUGE-configuration finding is a genuine reproducibility contribution; UKP Lab, EMNLP main, public code.

### Disadvantages
English only. Automatically inferred labels — *"the limitations of automatically inferred labels need to be taken into consideration when interpreting the results."* Data-reuse restrictions mean CiteBench ships *"instructions and a script to fetch and transform the data"* rather than the data itself. Citation text generation is a much smaller unit than a review chapter. Pre-dates current LLMs. Their own closing critique: *"the current definitions for citation text generation overly simplify the complex process of composing a related work section, which hinders the development of successful real-world applications."*

### Datasets
CiteBench (unifying ABURAED, XING, CHEN Delve, Multi-XScience); references S2ORC, KILT, SQuAD, arXiv. Models: LED, BERT.

### Relevance to ResearchGPT
Three transfers, one of them a concrete methodological warning.

**1. Specify your ROUGE configuration.** A 3-point ROUGE swing from package configuration alone is larger than many of the differences you will be reporting between ablations. State the exact package and settings in your Evaluation chapter, and cite CiteBench for why it matters. This is a cheap credibility win.

**2. Their human-evaluation finding is a prediction about your output.** *"Miss key factual details about the cited papers"* while remaining *"topically related"* is precisely the failure mode your four-field extraction schema and Verifier target — plausible-sounding, topically-correct, factually thin text. Look for it explicitly in your own qualitative review, and if you find it, you have a well-cited name for it.

**3. Their transfer-learning result predicts a discrepancy you should not panic about.** Models transfer only partially across citation-generation datasets. **Expect your system, developed against your own 25-paper bibliography, to score differently on SciReviewGen gold sets.** That is an expected, citable finding rather than a bug.

Add the **0.18–0.42 consistency agreement** to the growing pile (Sarol 0.18–0.31, SciReviewGen 0.212): across three independent studies, human agreement on the quality and accuracy of generated scientific text is *fair at best*. This is the single most important context for your own human evaluation, and it should be stated in your Evaluation chapter, not buried in Limitations.

---

## C5-19 · Bolaños et al. (2024) — AI for Literature Reviews ✅ FULL TEXT

**Citation.** Bolaños, F. J., Salatino, A. A., Osborne, F., & Motta, E. (2024). *Artificial Intelligence Review* 57. Open University, UK. DOI [10.1007/s10462-024-10902-3](https://doi.org/10.1007/s10462-024-10902-3) · 206 citations · **167 references** · 49 pages

### Problem
AI-assisted SLR tooling has proliferated with no systematic map of what exists or how tools compare.

### Methodology
Systematic review of **21 leading SLR tools** assessed on **23 traditional features + 11 AI features**, focused on the screening and extraction phases, plus **11 recent LLM-based tools** for literature search and academic writing. Their search string, reported for reproducibility:

> `("Literature Reviews" OR "Systematic Review") AND ("Tools" OR "Automation" OR "Semi-Automation" OR "Semiautomation" OR "Software")`

with the note that *"since this field lacks standardised vocabulary... we aimed to maximise recall by using broad terms, planning to refine the results at a later stage."* Tools are assessed across technical, usability and **economic** categories — *"the economic category reflects the financial considerations associated with the tools."*

### Results and recommendations
- **Three primary research challenges:** integrating advanced AI solutions (LLMs, knowledge graphs); improving usability; developing a **standardised evaluation framework**.
- **⚠️ Metric recommendation — directly actionable for you.** *"Canonical metrics like precision, recall, and F1-score may not suffice to assess these tools. For this reason, it was suggested to adopt the **F2 score** instead of the F1 score... In contrast with the F1 score, which assigns equal importance to precision and recall, the **F2 score places greater emphasis on recall** compared to precision."* The logic is that in screening, missing a relevant paper is far costlier than reviewing an irrelevant one.
- **Best practices around three aspects:** *"performance, usability, and transparency."*
- On transparency: *"we emphasise the importance of improving the trustworthiness of these tools by disclosing essential information about their capabilities and limitations, sharing knowledge bases and models, and adopting explainable AI solutions"*, and *"it is important to incorporate transparency also in the evaluation process, ensuring traceability and explainability."*
- Explicit developer guidance: *"**Clarify the Limitations:** Developers should clearly communicate the limitations of the software, indicating where the tool is expected to perform well and where it may not meet expectations."*
- They also point at fact-checking as an emerging need: *"in the appraisal phase, incorporating AI-driven scientific fact-checking tools to evaluate the accuracy of research claims could provide significant benefits."*

### Advantages
Maps the real competitive landscape (21 tools, not just papers); the 23+11 feature framework is a ready-made comparison instrument; 206 citations and 167 references; the F2 recommendation and transparency best practices are concrete and adoptable; covers economics, which academic papers usually ignore.

### Disadvantages
Tool review with no system, benchmarking or head-to-head performance data. Tool landscapes date fast. Focused on screening and extraction, lighter on synthesis and writing — the harder half of your problem. SLR-centric (healthcare-inflected) rather than CS narrative reviews. They acknowledge *"another limitation arises from the restricted range of dimensions assessed during the evaluation of SLR tools."*

### Datasets
**None** — review of 21 SLR tools + 11 LLM tools. Sources include Scopus, Semantic Scholar, PubMed, CORE, Dimensions, CSKG.

### Relevance to ResearchGPT
**Four concrete uses, and one of them changes a metric in your plan.**

**1. Use F2, not F1, for screening.** `RESEARCHGPT_SPEC.md §7.2` step 3 screens papers against inclusion criteria. Bolaños et al. give you a peer-reviewed, well-reasoned argument for weighting recall over precision at that stage — dropping a relevant paper is unrecoverable, while an irrelevant one gets filtered downstream by the reranker and Verifier. **Report F2 for screening and F1 for extraction**, and cite this paper for the distinction. It is a small change that makes your evaluation look considered rather than default.

**2. Position against real tools.** Build a table placing ResearchGPT in their 23+11 feature framework. It will show concretely that existing tools cluster on **screening and extraction** while yours targets **verified synthesis** — answering "doesn't this already exist?" with evidence instead of opinion.

**3. Their transparency best practices map onto artefacts you already produce.** *"Traceability and explainability"* is your `trace.jsonl` and `evidence_spans`; *"sharing knowledge bases and models"* is your open verifier checkpoint; *"clarify the limitations"* is your Limitations chapter. Cite this as the standard you are meeting, rather than presenting those artefacts as incidental engineering.

**4. Justify the Vue frontend.** Usability is named as one of three primary open challenges in the field. An examiner questioning why a research project needs a UI can be pointed at a Q1 review saying usability is a core unsolved problem here.

Their remark that fact-checking *"in the appraisal phase... could provide significant benefits"* is also a forward-looking endorsement of exactly what your Verifier does, from a survey that predates it.

---

## C5-20 · Edelman & Skolnick (2025) — Valsci ✅ FULL TEXT

**Citation.** Edelman, B., & Skolnick, J. (2025). *BMC Bioinformatics* 26:140. Georgia Tech. DOI [10.1186/s12859-025-06159-4](https://doi.org/10.1186/s12859-025-06159-4) · 6 citations

### Problem
*"The exponential growth of scientific publications poses a formidable challenge for researchers seeking to validate emerging hypotheses or synthesize existing evidence."* Existing frameworks *"either lack end-to-end pipelines—requiring users to manually feed abstracts—or cannot efficiently handle large numbers of claims concurrently."* And *"a major limitation of generative LLMs is their propensity for hallucination—generating plausible yet false citations, particularly in the absence of strong retrieval mechanisms."*

### Methodology
**Valsci** is open-source, self-hostable, and works with *"any OpenAI-compatible large language model."* It *"unites retrieval-augmented generation with structured bibliometric scoring and chain-of-thought prompting,"* searching Semantic Scholar. Scales via *"asynchronous parallelization,"* processing hundreds of claims per hour.

Notably for your constraints, the reported deployment target is modest: an **8 GiB memory virtual machine running Debian 12**.

The **guided prompt-flow** is explicitly structured — the paper enumerates its steps, including *"identify core concepts and their relationships in the claim"*, *"decompose complex claims into testable components"*, *"balance specificity with recall—avoid overly narrow or broad queries"*, *"consider both direct evidence and mechanistic studies"*, *"account for competing hypotheses and alternative explanations"*, *"consider study limitations and their impact on evidence quality"*, and per passage: *"explain how it relates to the claim; note whether it's direct evidence or mechanistic; include any limitations or caveats."*

Evaluation reports **precision, recall, F1, and an uncertainty rate** (abstention rate), where *"failure to annotate after maximum of 3 retries is counted as 'Uncertain'."*

### Results

**⚠️ Table 3 — the most important result in this paper for you:**

| Configuration | F1 | Uncertainty rate |
|---|---|---|
| GPT-4o alone | 0.706 | 0.360 |
| **Valsci + GPT-4o** | **0.761** | **0.267** |
| GPT-4o-mini alone | 0.597 | 0.412 |
| **Valsci + GPT-4o-mini** | **0.720** | **0.345** |

**Valsci with the small model (0.720) outperforms the frontier model used bare (0.706).** The architecture contributes more than the model upgrade does.

**Retrieval-depth ablation.** *"Increasing the maximum citation count from 9 to 49 yields respective gains in F1 from 0.655 to 0.724 and a reduction in the uncertainty rate from 0.404 to 0.331."* More retrieved evidence → better verification *and* fewer abstentions.

**Bibliometric-scoring ablation.** *"Disabling bibliometric indicators has a small but noticeable impact on performance: the system's F1 dips from 0.720 to 0.704, suggesting that weighting evidence by author impact and journal prestige can further refine final claim assessments."* — a **1.6-point** contribution from quality-aware weighting.

**Citation hallucination.** *"In a sample of 30 papers, the GPT-4o model failed to provide a single paper without a significant error."* Valsci *"successfully eliminates citation hallucinations"* by construction, since every citation is retrieved rather than generated.

### Advantages
Directly targets citation hallucination with quantified results; **evaluated on SciFact** — the dataset your verifier trains on; self-hostable, model-agnostic, and demonstrated on modest hardware (8 GiB VM); clean component ablations (retrieval depth, bibliometric scoring); high throughput; open source.

### Disadvantages
Authors describe the evaluation as *"preliminary."* Verification, not synthesis — it produces evidence reports, not literature reviews. Biomedical framing. Verification is **prompted LLM + CoT**, not a trained model, so it inherits LLM cost and variance. No agentic control or replanning — a single guided prompt-flow. Uncertainty rate remains high (0.267–0.345), meaning the system abstains on roughly a third of claims. Few citations yet.

### Datasets
**SciFact**; Semantic Scholar as live corpus; references MultiVerS and S2ORC. Models: GPT-4o, GPT-4o-mini, LLaMA, Mistral.

### Relevance to ResearchGPT
**Your most direct competitor, and — after reading the full text — also your strongest single piece of supporting evidence.**

**1. Table 3 is the empirical proof of your central narrative.** `PROJECT_PLAN.md §6.4` frames your $0 constraint as a finding: *"the architecture is a correctness filter, not a correctness source... decoupling review quality from model scale."* Valsci **measures exactly that**: GPT-4o-mini inside the architecture (F1 0.720) beats GPT-4o outside it (0.706). That is a peer-reviewed, published result showing a small cheap model plus good architecture beats a frontier model alone on scientific claim verification. **Quote this table in your Introduction and again in your Discussion.** It transforms your budget constraint from an apology into a hypothesis with prior support.

**2. Their retrieval-depth ablation predicts a tuning knob.** F1 rose 0.655 → 0.724 as citations per claim went 9 → 49. Your Verifier retrieves supporting evidence per claim; this says **evidence breadth per claim is a real performance lever**, and it is nearly free for you since retrieval is local and CPU-based. Worth an ablation of your own.

**3. Their bibliometric ablation gives your venue tiering a published effect size.** Disabling quality weighting cost 1.6 F1 points. Combined with QUAL-SG's +10.8 citation-quality F1 (C5-17), you now have **two independent measurements of what quality-aware ranking buys** — useful for setting expectations on your own venue-tier ablation, and a warning that the effect may be small.

**4. The differentiation is real but must be stated precisely:**

| | Valsci | ResearchGPT |
|---|---|---|
| Output | Per-claim evidence report | Full literature review |
| Control | Single guided prompt-flow | Agentic graph with bounded replanning |
| Verification | Prompted LLM + CoT | **Fine-tuned local NLI cross-encoder** |
| Verification cost | One+ LLM call per claim | Zero marginal cost, local CPU |
| Per-paper output | Evidence excerpts | Structured four-field schema |
| Quality gate | None | Critic loop |

**Your trained verifier is the clearest technical differentiator**, and it is also a *cost* argument — their approach needs an LLM call per claim, which is exactly what your budget forbids.

**5. A free comparison you should take.** Both systems evaluate on **SciFact**. Report your fine-tuned verifier's SciFact numbers next to Valsci's 0.720/0.761. A published comparison point on a shared benchmark is worth far more than an internal ablation, and it costs you nothing beyond running the evaluation you already planned.

---

# C6 — GROUNDING, VERIFICATION & HALLUCINATION

## C6-21 · Es et al. (2024) — RAGAs ✅ FULL TEXT

**Citation.** Es, S., James, J., Espinosa-Anke, L., & Schockaert, S. (2024). *EACL 2024: System Demonstrations*, p. 150. Cardiff University / Exploding Gradients. DOI [10.18653/v1/2024.eacl-demo.16](https://doi.org/10.18653/v1/2024.eacl-demo.16) · 330 citations

### Problem
*"Evaluating RAG architectures is challenging due to several dimensions to consider: the ability of the retrieval system to identify relevant and focused context passages, the ability of the LLM to exploit such passages faithfully, and the quality of the generation itself."* Reference-based evaluation requires human annotation that does not scale.

### Methodology
**RAGAs** is *"a framework for reference-free evaluation of Retrieval Augmented Generation pipelines"* covering *"three quality aspects, which we argue are of central importance"*: **faithfulness**, **answer relevance**, and **context relevance**.

The **faithfulness** metric is computed by decomposing the answer into statements and checking each against the context. Formally: *"the final faithfulness score, F, is then computed as **F = |V| / |S|**, where |V| is the number of statements that were supported according to the LLM and |S| is the total number of statements."* The prompt is strict about output format — *"do not deviate from the specified format"* — and for scoring, *"given an answer and context, assign a score for faithfulness in the range 0-10,"* with ties *"broken randomly."*

Validated on **WikiEval**, their own dataset, with paired high/low examples for each of the three dimensions.

Ships with integrations for **LlamaIndex and LangChain**, *"the most widely used frameworks for building RAG solutions."*

### Results
- **Human agreement.** *"For faithfulness and context relevance, the two annotators agreed in around **95%** of cases."*
- *"Our evaluation on WikiEval has shown that the predictions from RAGAS are closely aligned with human judgments, especially for faithfulness and answer relevance."*

### Advantages
Reference-free, so no human-annotated ground truth needed; decomposes evaluation into retrieval- and generation-side components; the faithfulness formula (`|V|/|S|`) is simple and directly implementable; very high human agreement on the validation set; drop-in integration with the frameworks you are using; 330 citations and de facto standard status; **used by your base paper**, so adopting it gives comparability.

### Disadvantages (their Limitations, verbatim)
> *"It relies heavily on the performance of the LLMs used for evaluating the different components. While the current set of experiments demonstrate high correlation of these metrics with human judgements, we acknowledge that relying on LLMs comes with known limitations. Therefore, careful reviewing of the suitability of LLMs (**ideally prioritizing open models over full-fledged products behind paid APIs**) is critical for RAGAS, and other contributions in this space, to nurture a healthy environment."*

Plus: system-demonstration track, so it is a tooling contribution rather than a validated measurement instrument; reference-free metrics measure internal consistency, not correctness against the world; costs API calls per evaluated sample; WikiEval is small and general-domain, not scientific.

### Datasets
**WikiEval** (own). Models: GPT-4, ChatGPT, BERT/BART referenced as baselines.

### Relevance to ResearchGPT
**Two things changed my view here after reading the full text.**

**1. The faithfulness formula is worth implementing even though you cut RAGAs.** `F = |V| / |S|` — supported statements over total statements — is exactly what your Verifier already computes when it classifies atomic claims. You can report a **RAGAs-compatible faithfulness score for free** from your existing verifier output, without any API calls, simply by using your local NLI model as the judge instead of an LLM. That gives you comparability with your base paper (which uses RAGAS) at zero cost. **This is a better decision than the blanket cut in `PROJECT_PLAN.md §2.2`** — cut the RAGAs *library* and its API calls, but keep the metric definition.

**2. The RAGAs authors themselves endorse your model choice.** Their limitation section explicitly recommends *"prioritizing open models over full-fledged products behind paid APIs."* When you disclose LLM-as-judge weaknesses in your evaluation (`PROJECT_PLAN.md §9.3`), this is the citation — the authors of the field's standard evaluation framework recommending exactly the direction your constraints push you.

Remaining caution: RAGAs is a demo-track contribution and its metrics are LLM-judged. Their 95% annotator agreement is on WikiEval, a small general-domain set — do not assume it transfers to scientific text, where every other study in this document reports agreement between 0.18 and 0.5.

---

## C6-22 · Min et al. (2023) — FActScore ✅ FULL TEXT

**Citation.** Min, S., Krishna, K., Lyu, X., Lewis, M., Yih, W., Koh, P. W., Iyyer, M., Zettlemoyer, L., & Hajishirzi, H. (2023). *EMNLP 2023*, p. 12084. UW / UMass / Allen AI / Meta. DOI [10.18653/v1/2023.emnlp-main.741](https://doi.org/10.18653/v1/2023.emnlp-main.741) · 296 citations

### Problem
Evaluating factual precision of long-form generation is hard because *"(1) generations often contain a mixture of supported and unsupported pieces of information, making binary judgments of quality inadequate, and (2) human evaluation is time-consuming and costly."*

Their illustration of why binary judgement fails: *"FACTSCORE allows a more fine-grained evaluation of factual precision, e.g., in the figure, the top model gets a score of **66.7%** and the bottom model gets **10.0%**, whereas prior work would assign **0.0 to both**."*

### Methodology
Two key ideas, stated explicitly:
- **Key Idea 1:** decompose a generation into **atomic facts** and compute the percentage supported.
- **Key Idea 2:** *"Factual precision as a function of a given knowledge source"* — deliberately contrasted with *"prior work [that] often considers factual precision as a single global truth."* Truth is relative to a named corpus, not absolute. **This is an important framing choice for you.**

**Human evaluation protocol.** Three steps ending in *"labeling factual precision & editing."* They use **people biographies** as the generation domain and **Wikipedia** as the knowledge source, chosen *"because they satisfy these assumptions to a reasonable degree."* Cost: **$4 per generation**, because *"one generation contains many (26–41) atomic facts."*

**Automated estimator.** Uses retrieval plus a strong LM. They find *"taking atomic facts generated by InstructGPT... effective and close to human."*

### Results
- **Estimator accuracy: <2% error rate** versus human evaluation.
- Applied to **6,500 generations from 13 recent LMs**, which *"would have cost $26K if evaluated by humans."*
- **ChatGPT achieves only 58%** factual precision on biographies — a task the authors describe as *"fairly easy."* They note this is *"in contrast to prior work that claims LMs approach human performance."*
- **GPT-4 and ChatGPT are comparable** in factual precision.
- **Public models vary hugely at equal size:** within 7B models, *"Alpaca and Vicuna (∼40%) are more factual than MPT-Chat (30%) and StableLM (17%)."*
- **Abstention behaviour differs:** *"Alpaca never abstains from answering while Vicuna does."*
- **Rare entities hurt, even with retrieval.** Contrary to prior work reporting retrieval-based QA is robust to entity rarity, *"FACTSCORE of PerplexityAI still significantly drops as entities are rarer: a **relative drop of 50% and 64%** observed at the atomic-level and sentence-level."*
- **⚠️ The finding most relevant to you: citations do not predict correctness.** *"Although PerplexityAI provides citations to the references, **citations have little correlation with factual precision. 36.0% and 37.6% of supported and unsupported sentences have citations, respectively**."*
- PerplexityAI's characteristic failure: it *"often directly copies search results even if they are largely irrelevant to the input prompt."*

### Advantages
The atomic-decomposition method, validated against human annotation at scale; automated estimator within 2% of human judgement; enormous cost saving demonstrated; concrete comparative findings across 13 models; installable (`pip install factscore`); rapid adoption — *"within four months since its initial release, FACTSCORE has actively been used in subsequent work."*

### Disadvantages (their Limitations, verbatim highlights)
- **Scope.** *"All of our experiments focus on people biographies and Wikipedia, because many LMs can generate biographies with objective and specific facts (rather than subjective and vague ones)."* Extension to scientific literature is described only as *"a proof of concept in Appendix B.5."*
- **Not applicable to nuanced content.** *"FACTSCORE is not applicable when the facts are more nuanced, open-ended, and debatable... or with a knowledge source whose text frequently conflicts with each other."*
- **Estimator imperfection.** *"It is not perfect in individual judgments, and the best variant depends on the degree of how close a generation is to human-written text and its linguistic complexity."*
- **Precision only, no recall.** *"FACTSCORE does not consider factual recall: the coverage of information in a generation. FACTSCORE does not penalize a model that abstains from responding too frequently or generates fewer facts, which can be unfair since there is an inherent trade-off between precision and recall."* And *"the boundary between precision and recall is often blurry."*

### Datasets
People biographies (generated by InstructGPT, ChatGPT, PerplexityAI); Wikipedia as knowledge source; 6,500 generations from 13 LMs. Models: ChatGPT, GPT-4, Alpaca, Vicuna, MPT-Chat, StableLM, T5.

### Relevance to ResearchGPT
**The methodological foundation of your Verifier — and the full text supplies three things the abstract did not.**

**1. "Citations have little correlation with factual precision" is the single best justification for your architecture.** 36.0% of *supported* sentences and 37.6% of *unsupported* sentences carried citations — statistically indistinguishable. **The presence of a citation tells you essentially nothing about whether a claim is true.** This demolishes citation-counting as a quality proxy and is the strongest possible argument for claim-level verification against retrieved spans. It also directly justifies why `PROJECT_PLAN.md §9.3`'s citation-accuracy metric (does the DOI resolve?) is *necessary but nowhere near sufficient*, and why the Verifier must exist as a separate component.

**2. Their "Key Idea 2" resolves a problem in your evaluation design.** Factual precision is *"a function of a given knowledge source"* rather than global truth. This gives you a principled framing for the circularity concern in `PROJECT_PLAN.md §9.6`: your groundedness score is explicitly *"supported by the retrieved corpus"*, not *"true."* That is a legitimate, citable definition rather than a weakness — **provided you state it that way and don't overclaim**. FActScore makes the same restriction and is widely accepted.

**3. Their scope limitation is a warning you must repeat.** *"Not applicable when the facts are more nuanced, open-ended, and debatable."* Your four-field schema extracts *disadvantages* and *critique* — which are exactly nuanced, open-ended and debatable. **FActScore's authors would say their method does not apply to half your schema.** Handle this head-on: apply strict verification to *methodology*, *datasets*, *metrics* and *results* (objective, checkable), and treat *advantages*, *disadvantages* and *critique* as interpretive fields that carry evidence spans but are not claimed as verified facts. That distinction would strengthen your design considerably, and it is the kind of nuance that separates a good report from a mechanical one.

Two smaller borrows: the **26–41 atomic facts per generation** figure lets you sanity-check your own claim-decomposition rate, and the **$4/generation human cost** is your justification for a 50-claim spot-check rather than exhaustive annotation. And ChatGPT at 58% on an "easy" task remains an excellent Introduction statistic.

---

## C6-23 · Gao et al. (2023) — ALCE ✅ FULL TEXT

**Citation.** Gao, T., Yen, H., Yu, J., & Chen, D. (2023). *EMNLP 2023*, p. 6465. Princeton NLP. DOI [10.18653/v1/2023.emnlp-main.398](https://doi.org/10.18653/v1/2023.emnlp-main.398) · 167 citations

### Problem
LLM outputs *"are prone to hallucination,"* and existing citation-generating systems *"mainly rel[y] on commercial search engines and human evaluation, making it challenging to reproduce and compare different modeling approaches."* Also: *"retrieval-augmented LMs incorporate retrieved passages during both training and inference, but do not guarantee faithfulness to retrieved passages or explicitly provide citations."*

### Methodology
**ALCE** — *"the first benchmark for Automatic LLMs' Citation Evaluation"* — with three datasets and three metric dimensions.

**Datasets:** **ASQA** (Wikipedia, 21M passages; ambiguous factoid), **QAMPARI** (list-answer questions), **ELI5** (long-form, open-ended). Retrievers: DPR, GTR, BM25.

**Three metric dimensions**, designed so *"the combination of the three metrics provides a robust evaluation"* and *"prevent[s] systems from exploiting shortcuts"*:

1. **Fluency** — MAUVE.
2. **Correctness** — dataset-specific: **exact-match recall** for ASQA; **precision/recall against the gold answer list** for QAMPARI, with an adjustment that *"considers recall to be 100% if the prediction includes at least 5 correct answers (recall-5)"*; and for ELI5, **claim recall** using **TRUE** (a **T5-11B** model fine-tuned on NLI datasets) to *"check whether the model output entails the sub-claims."* They note ROUGE, used by prior work, *"does not reflect the correctness well."*
3. **Citation quality** — two complementary metrics:
   - **Citation recall:** for statement *sᵢ*, recall is 1 iff at least one citation exists **and** the NLI model finds the concatenation of all cited passages entails the statement. *"Recall = 1 if the concatenation of all cited passages fully supports the segment."*
   - **Citation precision:** a citation *cᵢⱼ* is **"irrelevant"** iff *"(a) φ(cᵢⱼ, sᵢ) = 0, AND (b) φ(concat(Cᵢ \ {cᵢⱼ}), sᵢ) = 1"* — i.e. it alone does not support the claim, and removing it does not break the support. *"If recall = 0, then precision = 0."*

They prioritise recall: *"we prioritize citation recall as it entails a well-supported and truthful answer, [but] enhancing precision is crucial for better user satisfaction, reducing the need for human review of extraneous [citations]."*

**Methods evaluated:** VANILLA, CLOSEDBOOK+POSTCITE (generate then attach citations post-hoc), **RERANK** (*"randomly sample n=4 responses for each question, and select the best response using the automatic citation recall score"*), plus proposed **summaries/snippets** instead of full passages and **INTERACT**, *"an interactive prompting scheme to allow the model to check the full text of certain passages."* Models operate with a **4K context window, allowing 5 passages per question**.

### Results
- **Validation against humans.** *"The Cohen's kappa coefficient between human and ALCE suggests **substantial agreement for citation recall (0.698)** and **moderate agreement for citation precision (0.525)**."* Treating human annotations as gold: **85.1% accuracy for citation recall, 77.6% for citation precision.**
- **Headline failure.** On ELI5, *"even the best models lack complete citation support 50% of the time."*
- **⚠️ Post-hoc citation is catastrophic.** *"Citation recall of CLOSEDBOOK+POSTCITE is lower than VANILLA by **47%** on ASQA."* Generating text first and attaching citations afterwards destroys grounding.
- **Retrieval bounds everything.** *"Retrieval recall serves as an upper bound for model performance"*, and *"both models' correctness lags behind the corresponding retrieval recall (except for ELI5 top-5)"* — models fail to exploit even the evidence they are given.
- **More context does not help.** *"Contrary to the retrieval recall trend, more passages in context do not yield substantial improvement for ChatGPT."*
- **Reranking helps.** *"RERANK leads to consistent improvement in citation quality (on ASQA and ELI5)."*
- **Open models cite badly.** *"While the original LLaMA models are able to copy facts from the context, they struggle with accurately citing the sources or simply do not cite."*

### Advantages
The first reproducible end-to-end citation benchmark; metrics validated against human judgement with reported κ; the three-dimensional design explicitly guards against shortcut-gaming; precise, implementable metric definitions; identifies several non-obvious empirical results (post-hoc citation collapse, more-context-doesn't-help, retrieval as upper bound).

### Disadvantages (their Limitations, verbatim)
- *"MAUVE is found to be sensitive to output length and may provide unstable results."*
- *"For the ELI5's correctness evaluation, the automatically generated claims may not cover all possible answers due to the open-ended nature of the questions."*
- *"Our citation quality evaluation is limited by the accuracy of the NLI model; for citation precision, **the NLI model cannot detect the case of 'partially support'** and thus leads to a lower citation precision score than the human evaluation."*
- Coverage: *"they do not cover more challenging scenarios, such as multi-hop reasoning, math reasoning, and code completion."*
- *"We focus on prompting LLMs without updating their model weights. Training a model directly to incorporate citations remains challenging due to the lack of supervised data."*

### Datasets
**ALCE** (ASQA, QAMPARI, ELI5); Wikipedia (21M passages). Models: ChatGPT, GPT-4, LLaMA, Alpaca, Vicuna, T5-11B (TRUE), DPR, GTR, BM25, FiD.

### Relevance to ResearchGPT
**The most directly transferable evaluation design in this document. Adopt it.**

**1. Take their citation recall/precision definitions verbatim.** Both are precisely specified, NLI-computable, and validated against humans (κ 0.698 / 0.525). **Your fine-tuned NLI verifier is exactly the `φ` function these definitions require** — you can implement ALCE-style citation quality locally, at zero API cost, with the model you are already training. This is a much stronger evaluation than `PROJECT_PLAN.md §9.3`'s DOI-resolution check, and it costs almost nothing extra.

**2. Their three-dimensional structure should be your Evaluation chapter's structure.** Fluency / correctness / citation quality, with the explicit rationale that the combination *"prevent[s] systems from exploiting shortcuts."* A reader can see immediately that you cannot game one dimension without losing another.

**3. The POSTCITE result validates a core design decision.** Attaching citations after generation cost **47% of citation recall**. Your Writer is constrained so that *"no sentence may be written that is not backed by a verified_claim"* (`RESEARCHGPT_SPEC.md §7.6`) — evidence-first, not citation-after. ALCE gives you the number that justifies it. This is also a strong argument against any temptation to simplify the Writer by generating prose first and attaching citations later.

**4. "Retrieval recall is an upper bound" — say this explicitly, twice.** It appears here and in Sarol et al. (whose top-20 recall was 0.53). Your Verifier can only find evidence your Retriever surfaced. This is the strongest possible argument for protecting the Day 6–7 retrieval buffer, and for reporting retrieval recall alongside groundedness rather than separately.

**5. Their NLI limitation is your limitation too.** *"The NLI model cannot detect the case of 'partially support'."* Your verdict schema has a `PARTIAL` class (`RESEARCHGPT_SPEC.md §7.4`) — so **you should expect that class to be your weakest**, and you should report per-class performance rather than a single F1. Their honesty here tells you exactly where to look for your own failures.

Finally, their closing limitation — *"training a model directly to incorporate citations remains challenging due to the lack of supervised data"* — is a gap that LongCite (in the reserve pool) later addressed, and it is adjacent to what you are doing by training a verifier rather than a citing generator. Worth a sentence in Related Work.

---

## C6-24 · Huang et al. (2024) — Survey on Hallucination in LLMs **[ABSTRACT ONLY]**

**Citation.** Huang, L., Yu, W., Ma, W., Zhong, W., Feng, Z., Wang, H., Chen, Q., Peng, W., Feng, X., Qin, B., et al. (2024). *ACM TOIS.* DOI [10.1145/3703155](https://doi.org/10.1145/3703155) · **1,757 citations** · 214 references

**Problem.** *"LLMs are prone to hallucination, generating plausible yet nonfactual content,"* raising concerns *"over the reliability of LLMs in real-world information retrieval (IR) systems."* Because LLMs are open-ended and general-purpose, their hallucinations *"present distinct challenges that diverge from prior task-specific models."*

**Methodology.** Comprehensive survey with an *"innovative taxonomy of hallucination in the era of LLM"*, then contributing factors, detection methods and benchmarks, mitigation methodologies, and — most relevant to you — *"the current limitations faced by retrieval-augmented LLMs in combating hallucinations."* Closes on future directions including vision-language hallucination and **knowledge boundaries**.

**Advantages.** 1,757 citations; 214 references; ACM TOIS; covers detection, mitigation and benchmarks together; explicitly analyses **where RAG fails** to prevent hallucination, which almost no other source does directly.

**Disadvantages.** Survey with no method or experiments; broad coverage means shallow treatment of scientific-domain hallucination; a 2024 survey already misses recent work. (Note: OpenAlex's auto-assigned concepts for this record are wrong — *"Visual Hallucination, Psychology, Psychiatry"* — a reminder not to trust automated topic tags.)

**Datasets.** None.

**Relevance.** The definitive citation for your problem statement, and its analysis of **RAG's limitations in combating hallucination** is the peer-reviewed support for your central premise: retrieval alone is insufficient, verification is additionally required. Without it that premise is your assertion; with it, it is the field's documented position from a Q1 IR venue. Also use their taxonomy to organise your Limitations chapter — classifying the residual hallucination types you *don't* address reads as rigour. Their **knowledge-boundary** concept gives you vocabulary for the stress test: a system that recognises when its corpus doesn't cover a question is demonstrating knowledge-boundary awareness, a named research goal rather than a demo trick.

---

## C6-25 · Liu et al. (2024) — CliVER ✅ FULL TEXT (Europe PMC)

**Citation.** Liu, H., Soroush, A., Nestor, J. G., Park, E., Idnay, B., Fang, Y., Pan, J., Liao, S., Bernard, M., Peng, Y., et al. (2024). *JAMIA Open* 7(1). Columbia University / Weill Cornell. DOI [10.1093/jamiaopen/ooae021](https://doi.org/10.1093/jamiaopen/ooae021) · PMC10919922 · 8 citations

### Problem
*"To automate scientific claim verification using PubMed abstracts."* Manual verification does not scale.

### Methodology
**CliVER** is *"an automated PICO-based Claim VERification framework... that employs retrieval-augmented methodologies to verify claims and identify supporting and refuting clinical evidence from the clinical trial literature."* Pipeline: retrieve relevant clinical-trial abstracts → extract pertinent sentences → classify using the **PICO** framework.

**Classification ensemble** of three models: **RoBERTa**, **PubMedBERT**, and **T5**, combined by **majority voting**, predicting **Support / Refute / Neutral**.

**Two evaluation settings** — an **Oracle** setting (gold abstracts provided) and an **Open** setting (full retrieval from PubMed). This separation is the paper's most valuable methodological feature.

**CoVERt dataset:** 15 PICO-encoded drug claims with 96 manually selected labelled clinical trial abstracts. *"The claims were further classified as Supported, Refuted, or NotEnoughInfo, with an inter-annotator agreement of **0.6841 in Fleiss kappa**."*

Ranking evaluated with **Precision@K, MRR@K, NDCG@K**. Abstract/sentence ranking used a **T5 model fine-tuned on MS MARCO**. Human comparison: **four medical clinicians** across 6 disease domains, over **189,648 PubMed abstracts** (Jan 2010 – Oct 2021).

### Results

**Oracle setting (gold evidence provided):**
- **SciFact dev:** Majority Voting ensemble **macro-F1 0.93**. Individual models: RoBERTa **0.89**, PubMedBERT **0.87**, T5 **0.79**. The ensemble gives *"a 4% absolute increase in macro-average F1 (0.93) compared to the individual model with the best performance (0.89)."*
- **CoVERt:** ensemble **macro-F1 0.92**, beating T5-base 0.89 by 3 points.
- PubMedBERT achieved **precision 1.0 for the Neutral class** on both datasets.
- Claim formatting mattered: *"the majority voting ensemble model achieved the best performance when claims were formatted using **Template 2**, with a macro-average F1 score of 0.93."*

**Open setting (real retrieval):** *"Supplementary Table S3 shows that the Majority Voting ensemble achieved the best performance with a macro-average F1 score of **0.85**."* RoBERTa 0.82, PubMedBERT 0.79, T5 0.79.

**⚠️ Human comparison against four clinicians — the reality check:**
- **Sentence relevance, Oracle setting:** 59 of 75 sentences judged relevant → **78.7% accuracy**.
- **Sentence relevance, Open setting:** 64 of 95 → **67.4%**.
- **Label agreement, Oracle setting:** 47 of 59 → **79.7%**.
- **Label agreement varies enormously by disease domain:** *"the lowest accuracy (0.55) was for Alzheimer's disease, and the highest accuracy (0.76) was for kidney diseases"*; in a second breakdown, *"the lowest accuracy (0.44) was for Alzheimer's disease and the highest accuracy (0.80) was for the COVID-19 category."*

**⚠️ Over-prediction of "Support".** *"The Support class had a **high recall of 1.0 but a low precision of 0.79**, indicating that all the true Support cases were successfully predicted, but **21% of the cases predicted with the Support label were false Support cases**."*

### Advantages
Three-way label space matching your Verifier; ensemble gains quantified (+3–11% F1); **Oracle vs Open separation** is exactly the right experimental design; benchmarked against four human clinicians, which is rare; evaluated on SciFact, giving shared ground with your verifier; good inter-annotator agreement on their own dataset (Fleiss κ 0.684).

### Disadvantages
- *"We did not measure recall since we cannot exhaust reviewing all relevant abstracts in PubMed for each claim."*
- *"Abstract and sentence ranking modules were implemented with a T5 model fine-tuned with the MS MARCO dataset"* — a general-domain ranker on biomedical text.
- CoVERt is tiny (15 claims, 96 abstracts).
- PICO structure is biomedical-specific; the authors suggest *"leverag[ing] PICO entities in both the claim and the abstract"* as future work.
- An ensemble of three transformers is expensive — infeasible on your CPU budget.
- Authors describe the system as showing *"early potential."*

### Datasets
**CoVERt** (own; 15 claims, 96 abstracts, Fleiss κ 0.684), **SciFact**, 189,648 PubMed abstracts. References FEVER, MNLI, MS MARCO. Models: RoBERTa, PubMedBERT, T5, ColBERT, BERT.

### Relevance to ResearchGPT
**Read this with Sarol et al. (C4-14) as your calibration pair. The full text makes the lesson much sharper than the abstract did.**

**1. The degradation gradient is the finding, and you should replicate its structure.**

| Setting | Macro-F1 / accuracy |
|---|---|
| Oracle (gold evidence), SciFact | **0.93** |
| Open (real retrieval) | **0.85** |
| Label agreement vs clinicians | **0.797** |
| Worst domain (Alzheimer's) | **0.44–0.55** |

Same system, four numbers, a **49-point spread**. The gap is entirely about how realistic the evaluation is. **Adopt their Oracle/Open split in your own evaluation** — report your verifier's accuracy given gold evidence spans *and* given your actual retriever's output. The difference isolates how much of your error is retrieval versus verification, which is the most useful diagnostic you can produce and it is nearly free.

**2. The 21% false-Support rate is the failure mode you must measure.** Recall 1.0, precision 0.79 on the Support class means the system **over-predicts support** — it says "verified" when it should say "insufficient." For a project graded on not hallucinating, that is *the* dangerous direction of error. Your `SUPPORTED` class will likely behave the same way. **Report per-class precision, and weight your threshold toward precision on `SUPPORTED`** — a false `UNSUPPORTED` costs you a dropped claim; a false `SUPPORTED` costs you a hallucination in the output.

**3. Domain variance of 0.44–0.80 predicts your domain-shift risk.** Their accuracy nearly doubled between their worst and best disease domain *within* biomedicine. You are training on SciFact (biomedical) and deploying on CS — a much larger shift than Alzheimer's-to-COVID. `PROJECT_PLAN.md §11` already flags this; CliVER quantifies how bad within-domain variance alone can be. Budget for it, and consider reporting per-cluster (C1–C6) verifier accuracy.

**4. Their ensemble finding is interesting but not actionable for you.** +3–11% F1 from majority voting over three transformers. On CPU that is three times the inference cost. Note it as Future Work rather than pretending it is available.

**5. Their claim-template finding is cheap to exploit.** Formatting claims with "Template 2" gave the best results. Your claim decomposition produces the text your verifier sees — **how you phrase decomposed claims is a free tuning knob**, worth a quick A/B in Week 3.

---

# Cross-Cutting Synthesis

Patterns visible only across the full set of papers. These belong in your Discussion chapter — they are the part of a literature review that cannot be produced by summarising papers one at a time.

### 1. Four independent measurements say the same thing about citations

| Source | Measurement |
|---|---|
| Sarol et al. (C4-14) | **39.18%** of citation instances in highly-cited biomedical papers contain accuracy errors (historical median: 20%) |
| Gao et al. / ALCE (C6-23) | Best models *"lack complete citation support 50% of the time"* on ELI5 |
| Min et al. / FActScore (C6-22) | ChatGPT factually correct on only **58%** of atomic claims in long-form generation |
| Bao et al. / SurveyGen (C5-17) | Best survey-generation citation accuracy: **35.84%** |

Four venues, four methods, four tasks, one conclusion. This is your Introduction.

### 2. The presence of a citation carries almost no information

FActScore's most under-appreciated result: **36.0% of supported sentences and 37.6% of unsupported sentences carried citations.** A citation is not evidence of support. This is the deepest justification for your architecture — you cannot verify a review by counting or resolving citations, only by checking claims against retrieved spans. It also means `PROJECT_PLAN.md §9.3`'s DOI-resolution metric measures something real but shallow, and must be reported alongside claim-level grounding, never instead of it.

### 3. Benchmark numbers overstate real performance, consistently and by a lot

| System | Curated benchmark | Realistic setting |
|---|---|---|
| CliVER (C6-25) | 0.93 macro-F1 (Oracle) | 0.85 (Open) → 0.797 vs clinicians → **0.44 worst domain** |
| Sarol et al. (C4-14) | — | **0.59 micro-F1** on real citations |
| SciReviewGen (C5-16) | ROUGE-L 16.52 | **~30%** of chapters match human quality |
| SurveyGen (C5-17) | — | **16.73%** best citation-quality F1 |

Nothing in this literature achieves anything close to deployment-grade accuracy on realistic scientific verification. **Your targets in `PROJECT_PLAN.md §9` should be revised downward, and framed as measured rather than aspirational.** Reporting 0.6 with a careful Oracle/Open decomposition is a far better result than reporting 0.95 that nobody believes.

### 4. Humans agree poorly on exactly the judgements you plan to collect

| Study | Agreement |
|---|---|
| Sarol et al. (C4-14) | κ **0.18–0.31** (accuracy labels), 0.20–0.37 (evidence sentences) |
| CiteBench (C5-18) | κ **0.18–0.42** (consistency), ~0.50 (readability) |
| SciReviewGen (C5-16) | κ **0.212** (three-way review quality) |
| CliVER (C6-25) | Fleiss κ **0.684** (their own curated claims) |
| RAGAs (C6-21) | ~**95%** agreement (WikiEval, general domain) |

The pattern is clear: **agreement is fair-to-poor on nuanced scientific-quality judgements, and high only on curated or general-domain data.** Three consequences for you: (i) use **two annotators** and **report κ** — a single annotator at κ≈0.3 reliability is not ground truth; (ii) a verifier scoring 0.59 against humans who agree 0.3 with each other is not obviously failing; (iii) prefer objective checkable metrics (citation resolution, span coverage, retrieval recall) as your primary evidence, with human judgement as corroboration rather than gold.

### 5. Retrieval recall is a hard ceiling on everything downstream

Stated independently by ALCE (*"retrieval recall serves as an upper bound for model performance"*), Sarol et al. (top-20 recall **0.53**; accuracy 63% with gold evidence retrieved vs 51% without), and Valsci (F1 0.655→0.724 as citations per claim went 9→49). Your Verifier can only check claims against what your Retriever found. **Protect the Day 6–7 retrieval buffer, and report retrieval recall next to groundedness — never groundedness alone.**

### 6. Architecture beats model scale — and it has been measured

Valsci Table 3: **GPT-4o-mini inside the architecture (F1 0.720) beats GPT-4o alone (0.706).** This is the published result that turns your $0 constraint from a compromise into a hypothesis with prior support. Chain-of-Note points the same way (a distilled LLaMA-2 7B with CON beating standard fine-tuned RALMs), as does Adaptive-RAG's finding that *"no significant performance differences among classifiers of various sizes."* Your narrative — *the architecture is a correctness filter, not a correctness source* — is not wishful thinking; it is the direction three independent papers point.

### 7. Abstract-only inputs are the field's shared, unresolved constraint

SciReviewGen: *"we use only abstract text as the input text"*, with only 70% of cited papers having body text. SurveyGen: *"restricted to using only abstracts and bibliographic metadata... for copyright reasons."* Li et al. (C4-15) measured what that costs: **ANLI faithfulness 0.745 vs ~0.95**.

**This is your clearest opportunity.** You parse open-access full text and ground claims in character-level spans. That is a real, measurable improvement over both the dataset paper and your recommended base paper — and it is one of the few places where a student project can genuinely exceed a published system, because the barrier is licensing and engineering effort rather than compute.

But it cuts both ways: your own abstract-only degraded mode for paywalled papers inherits precisely the weakness you are claiming to fix. Restrict abstract-only papers to citation-level support, and say so.

### 8. Every honest paper reports where it fails

Sarol at 0.59. CliVER's 0.93→0.44 spread. SurveyGen conceding fully automatic generation is insufficient. Ammann et al. listing six limitations including the one their successors will fix. SciReviewGen stating its output *"cannot [be] publish[ed] without human revision."* FActScore excluding nuanced and debatable facts from its own scope.

These are the most useful papers in this set, and not by accident. **Write your evaluation the same way.** Under a grading criterion of "does it work and not hallucinate," a report that measures its own limits precisely is worth more than one claiming numbers that invite disbelief.

---

# Actions arising from the full texts

Ordered by how much they change what you build.

1. **Restrict abstract-only papers to citation-level support.** Li et al.'s 21-point faithfulness gap, plus SciReviewGen's and SurveyGen's shared admission, make the current degraded mode a direct threat to your graded criterion. (§C4-15, C5-16, C5-17)
2. **Adopt ALCE's citation recall/precision definitions**, computed locally with your fine-tuned NLI model. Zero API cost, human-validated (κ 0.698/0.525), and far stronger than DOI resolution alone. (§C6-23)
3. **Adopt CliVER's Oracle/Open evaluation split.** Report verifier accuracy given gold spans *and* given real retrieval. It isolates retrieval error from verification error and is nearly free. (§C6-25)
4. **Revise `PROJECT_PLAN.md §9` targets downward.** Nothing in this literature reaches 0.9 on realistic scientific verification. Reframe groundedness as *"supported by the retrieved corpus"* per FActScore's Key Idea 2, and report Oracle/Open separately. (§C4-14, C6-22, C6-25)
5. **Weight the `SUPPORTED` threshold toward precision.** CliVER's 21% false-Support rate is the dangerous direction of error for a project graded on hallucination. Report per-class precision. (§C6-25)
6. **Use ~20 few-shot examples in the Extractor prompt**, and A/B the schema format (JSON vs structured English) on your chosen free-tier model. (§C4-13)
7. **Split your four-field schema by verifiability.** Verify *methodology / datasets / metrics / results* strictly; treat *advantages / disadvantages / critique* as interpretive fields carrying spans but not claimed as verified. FActScore's scope limitation says the strict method does not apply to nuanced content. (§C6-22)
8. **Use F2 for screening, F1 for extraction.** Recall matters more than precision when discarding papers. (§C5-19)
9. **Keep the RAGAs faithfulness metric (`F = |V|/|S|`) even though you cut the library** — computable free from your verifier output, and it gives comparability with your base paper. (§C6-21)
10. **Two annotators and report Cohen's κ.** Four studies here report fair-to-poor agreement on these judgements; a single annotator is not ground truth. (§C4-14, C5-16, C5-18)
11. **Quote Ammann et al.'s limitation #6 verbatim in your Introduction** — *"subqueries are generated once and not updated based on retrieved evidence"* — and cite SciReviewGen's limitations table as your requirements list. (§C2-09, C5-16)
12. **Specify your ROUGE package and configuration.** A 3-point swing from configuration alone exceeds several of your expected ablation deltas. (§C5-18)
13. **Get the PDF of C2-08** (Li et al., IP&M) through your library. Still the only paper in this set I could not read, and possibly a direct competitor.
14. **Verify *Vicinagearth* (C3-11) is Scopus-indexed**; substitute Wang et al. 2024 (*Frontiers of Computer Science*, 1,320 citations) if not.

---

*Full text obtained for 18 of 26 papers; 8 abstract-only and marked as such. All DOIs verified via OpenAlex 2026-08-06. Every quoted passage is from the paper itself; "Relevance to ResearchGPT" sections are analysis.*
