# Literature Review: How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?

## Methods and Architectures

### Methods and Architectures for Detecting, Generating, and Verifying LLM‑Produced Content 

A growing body of work investigates how architectural choices and methodological levers shape the reliability of large‑language‑model (LLM) outputs across scientific writing, code generation, and fact‑checking pipelines.

#### 1. Feature‑Based Detection of Synthetic Text 
One concrete approach to identifying LLM‑generated scientific prose relies on handcrafted stylistic cues. By manually selecting 20 predictive features—such as paragraph length, sentence complexity, punctuation density, and lexical diversity—the authors trained a binary classifier on a balanced corpus of 64 *Science* Perspective articles and 128 ChatGPT‑generated drafts, achieving >99 % accuracy on full documents and 98–100 % accuracy on chemistry‑journal introductions [1]. The strength of this method lies in its interpretability and extremely high detection rates within the evaluated domains. However, its generalizability is limited to the specific article types and to the generation models represented in the training set; future, more capable LLMs (e.g., GPT‑4) may narrow the stylistic gap, reducing the classifier’s effectiveness [1].

#### 2. Multi‑Agent Systems for Knowledge Extraction and Interpretation 
Formal methods can be leveraged to construct decentralized architectures that distribute rule‑mining and knowledge‑interpretation tasks among specialized agents. Using closed‑path rules and predicate‑logic specifications, a five‑agent system was built to extract rules from large datasets, automatically filter irrelevant fragments, and interpret the resulting knowledge base [3]. This agent‑centric paradigm offers scalability and autonomy, enabling dynamic handling of extensive knowledge repositories. The approach contrasts with monolithic pipelines by emphasizing modularity and formal verification of each agent’s behavior.

#### 3. Retrieval‑Augmented Generation (RAG) Tuning 
Retrieval can both empower and impair LLM reasoning, depending on how aggressively context is injected. Four control levers—similarity score cutoffs, dynamic top‑k selection, model‑gated retrieval, and prompt framing that preserves generative agency—have been proposed to balance these effects [5]. Conservative settings (e.g., high similarity thresholds or model‑gated retrieval) tend to preserve the model’s intrinsic reasoning capabilities, avoiding a shift toward a “search‑engine” mode. Conversely, over‑retrieval (low thresholds, large top‑k) can overwhelm the model with extraneous information, degrading performance on tasks that require novel synthesis [5]. Although empirical results are not detailed, the framework highlights the importance of architectural safeguards when integrating external knowledge sources.

#### 4. Coding Agents and Multi‑Agent Coordination 
In the domain of program synthesis, diverse coding agents—lexical, hybrid, AST/graph‑based, and multi‑agent ensembles—have been evaluated on a single repository task. While AST/graph methods showed tentative performance advantages, multi‑agent setups achieved lower token consumption at the cost of coordination overhead and reduced transparency [4]. These findings illustrate a trade‑off between efficiency (token usage) and the interpretability of agent interactions, suggesting that multi‑agent orchestration may be beneficial when resource constraints dominate, but that careful design is needed to mitigate coordination bottlenecks.

#### 5. Fact‑Consistency Evaluation for Long‑Document Summarization 
Assessing factual consistency of generated summaries can be approached with either binary classification or fine‑grained continuous scoring. Systematic experiments across four long‑document datasets revealed that continuous scores provide more reliable diagnostics, while advanced classifiers achieve higher recall on older summaries but suffer from false positives and limited sensitivity to subtle errors [2]. This methodological insight underscores the need for evaluation architectures that capture nuance rather than coarse correctness, especially when summaries are used for decision‑critical scientific communication.

#### 6. Multi‑Agent Fact‑Checking Pipelines 
A recent multi‑agent pipeline integrates dense retrieval, reranking, balanced source selection, structured fact planning, and a gated self‑critique stage, culminating in an NLI‑grounded citation auditor that repairs missing citations and removes unsupported statements [7]. By chaining retrieval, generation, and verification agents, the system aims to produce fully fact‑checked articles. The architecture exemplifies how modular agents can be orchestrated to enforce factual grounding at multiple stages, contrasting with single‑pass generation models that lack explicit verification components.

#### 7. Comparative Human–AI Summarization for Exploratory Data Analysis 
When summarizing exploratory data analyses, AI‑generated narratives offer speed and scalability, yet often lag behind human analysts in interpretive accuracy, uncertainty expression, and trustworthiness [6]. Hybrid workflows that combine human oversight with AI drafting can mitigate these shortcomings, suggesting an architectural pattern where AI serves as a first‑draft generator followed by human validation.

#### Synthesis 

Across these studies, a common theme emerges: **architectural modularity coupled with carefully tuned methodological levers improves reliability**. Feature‑based detectors excel in narrow, well‑characterized domains but require continual adaptation to evolving LLMs. Formal multi‑agent designs provide scalability and formal guarantees for knowledge‑intensive tasks, while retrieval‑augmented pipelines must balance context richness against cognitive overload. Evaluation methods that capture fine‑grained factual consistency are essential for validating any of these architectures. Collectively, these works illustrate that the choice of method—whether handcrafted feature extraction, formal multi‑agent reasoning, or controlled retrieval—must be aligned with the target task’s constraints and the desired trade‑offs between accuracy, interpretability, and resource efficiency.

## Evaluation and Benchmarks

### Evaluation Practices and Benchmark Design for LLM‑Assisted Scientific Tasks 

The community has begun to construct task‑specific benchmarks that expose distinct failure modes of large language models (LLMs) in scholarly contexts. In the domain of scientific writing detection, a handcrafted feature‑based classifier achieved **>99 % accuracy on full‑text Science Perspective articles** and **98–100 % accuracy on chemistry‑journal introductions**, demonstrating that fine‑grained stylistic cues can be leveraged for reliable provenance assessment [1]. However, the authors caution that the evaluation is confined to a narrow set of article types and may not generalize to newer LLM generations such as GPT‑4, highlighting the need for **broader, continuously updated test suites** [1].

Parallel efforts in factual‑consistency evaluation for long‑document summarization reveal that **continuous, fine‑grained scoring metrics outperform binary classification** in reliability across four benchmark datasets [2]. While advanced evaluators attain higher recall on legacy summaries, they also generate **false positives and struggle with detecting subtle factual errors**, underscoring a trade‑off between sensitivity and precision that benchmark designers must consider [2]. This insight aligns with findings from biomedical multi‑document summarization, where modern neural abstractive models produce **fluent and relevant synopses but exhibit non‑negligible factual inaccuracies**, and where domain‑specific strategies only modestly improve factual correctness [8]. Together, these studies suggest that **benchmark metrics should capture both surface fluency and deep factual fidelity** rather than relying on a single aggregate score.

In the emerging area of code‑centric LLM evaluation, structured experiments on a single coding task reported **no clear superiority of semantic search over lexical baselines**, and observed that **multi‑agent configurations reduce token consumption at the cost of coordination overhead** [4]. The authors also note that **AST/graph‑based retrieval methods appear promising**, yet the limited scope and lack of standardized retrieval metrics impede definitive conclusions [4]. These observations echo broader concerns about **over‑retrieval in retrieval‑augmented generation (RAG)**, where aggressive similarity thresholds and high top‑k settings can flood the model with context, suppressing its reasoning abilities and degrading performance on tasks that require novel synthesis [5]. Conversely, **conservative retrieval strategies (e.g., model‑gated retrieval) preserve the model’s generative agency**, a principle that should be reflected in benchmark designs that vary retrieval aggressiveness as a controlled factor [5].

Human‑vs‑AI comparative studies of exploratory data analysis (EDA) summaries further illustrate the multidimensional nature of evaluation. AI‑generated summaries achieve **speed and scalability advantages**, yet they often lag behind human analysts in **interpretive accuracy, completeness, and explicit expression of uncertainty**, which can diminish perceived trustworthiness and lead to decision bias [6]. This suggests that **benchmark suites for scientific communication should incorporate user‑centric metrics such as perceived analytical trustworthiness alongside traditional factual accuracy** [6].

Finally, multi‑agent pipelines for fact‑checking and citation auditing demonstrate the feasibility of **integrating retrieval, structured planning, self‑critique, and natural‑language inference (NLI) components** to improve grounding of generated articles [7]. Although quantitative results are not reported, the architecture itself serves as a **prototype benchmark scenario** where each module can be individually evaluated for contribution to overall factual correctness and citation quality.

Collectively, these works converge on several best‑practice recommendations for evaluation and benchmarking of LLMs in scientific settings:

| Recommendation | Supporting Evidence |
|----------------|----------------------|
| Use **fine‑grained, continuous metrics** to capture subtle factual errors rather than binary judgments [2]. |
| Combine **fluency, relevance, and factual accuracy** in multi‑dimensional scorecards for summarization tasks [8]. |
| Design benchmarks that **vary retrieval aggressiveness** to expose over‑retrieval pitfalls and validate conservative retrieval benefits [5]. |
| Include **user‑centric measures** (e.g., trust, uncertainty communication) when assessing AI‑generated scientific narratives [6]. |
| Provide **modular evaluation points** for multi‑agent pipelines to isolate the impact of retrieval, planning, and self‑critique components [7]. |
| Ensure **diverse document types and domains** to avoid overfitting to narrow corpora, as highlighted by detection studies limited to Science Perspective articles [1]. |

By adhering to these principles, future benchmarks can more faithfully reflect the complex demands of scientific writing, reasoning, and decision support, fostering the development of LLM systems that are both powerful and trustworthy.

## Limitations and Open Problems

### Limitations and Open Problems

Despite rapid progress in applying large language models (LLMs) to scientific tasks, several recurring limitations hinder reliable deployment.

**Domain‑specific generalisation gaps** – Detection tools that rely on handcrafted stylistic cues achieve near‑perfect accuracy on the specific corpora they are trained on (e.g., Science *Perspective* articles and chemistry‑journal introductions) [1], yet their applicability to the broader spectrum of research articles remains unproven. The authors explicitly note that the limited scope of training data may prevent the model from generalising to other article types or to newer LLMs such as GPT‑4, which could close the stylistic gap that the detector exploits [1].

**Factual consistency in long‑form generation** – Fine‑grained, continuous evaluation metrics have been shown to be more reliable than binary judgments for assessing factual consistency [2]. However, even the most advanced systems still produce false positives and struggle to detect subtle, fine‑grained errors, indicating that current evaluation frameworks are insufficient for guaranteeing factual correctness in extensive summaries or generated manuscripts [2].

**Hallucinations in code‑related generation** – Exploratory studies of coding agents reveal that multi‑agent setups can reduce token consumption but introduce coordination overhead, and that semantic search does not consistently improve retrieval quality [4]. The lack of standardized retrieval metrics, statistical significance testing, and controlled ablations limits confidence in these findings and highlights the need for more rigorous benchmarking of code‑generation pipelines [4].

**Retrieval‑augmented generation (RAG) trade‑offs** – Conservative retrieval strategies (e.g., similarity thresholds, model‑gated retrieval) preserve the model’s reasoning abilities, whereas aggressive retrieval (low thresholds, high top‑k) can overwhelm the generator and degrade performance on reasoning‑heavy tasks [5]. The absence of empirical results, datasets, and quantitative analyses in the current literature leaves open the question of how to optimally balance retrieval aggressiveness across diverse downstream applications [5].

**Uncertainty communication and trust** – AI‑generated exploratory‑data‑analysis summaries offer speed and scalability but often omit nuanced expressions of uncertainty, leading to lower interpretive accuracy and potential decision bias [6]. While hybrid human‑AI workflows can mitigate some risks, systematic methods for embedding uncertainty cues and evaluating their impact on user trust remain under‑explored [6].

**Multi‑agent knowledge interpretation scalability** – Formal multi‑agent architectures provide a decentralized framework for rule extraction and knowledge interpretation [3]. Nevertheless, the scalability of such systems to real‑world, heterogeneous knowledge bases has not been empirically validated, and the overhead of coordinating multiple agents may offset the theoretical benefits of autonomy and decentralisation [3].

Collectively, these observations underscore open research problems: (i) developing detection and evaluation methods that generalise beyond narrow domains and adapt to evolving LLM capabilities; (ii) establishing robust, fine‑grained factual consistency metrics with low false‑positive rates; (iii) creating standardized, statistically sound benchmarks for code‑generation and retrieval‑augmented pipelines; and (iv) designing mechanisms for transparent uncertainty communication to sustain user trust in AI‑assisted scientific workflows.

## References

[1] Nader Rifai, "Large Language Models for Scientific Publishing: Please, Do Not Make Them a Foe", Clinical Chemistry, 2024. doi:10.1093/clinchem/hvad219
[2] Yang Zhong, Diane Litman, "A Tale of Evaluating Factual Consistency: Case Study on Long Document Summarization Evaluation", 2025. doi:10.18653/v1/2025.findings-acl.648
[3] Oleksandr Karataiev, Igor Shubin, "Formal model of multi-agent architecture of a software system based on knowledge interpretation", RADIOELECTRONIC AND COMPUTER SYSTEMS, 2023. doi:10.32620/reks.2023.4.05
[4] Alexandre CERVEAU AUDEBEAU, "Structured PREreview of "An Exploratory Study of Code Retrieval Techniques in Coding Agents"", Zenodo (CERN European Organization for Nuclear Research), 2025. doi:10.5281/zenodo.17536688
[5] Daniel Rosehill, Gemini 3.1 (Flash), Chatterbox TTS, "Tuning RAG: When Retrieval Helps vs. Hurts", Open MIND, 2026. doi:10.5281/zenodo.19583123
[6] Sai Lalitesh Pothukuchi, "Human Vs AI Summaries of Exploratory Data Analysis: Trust, Accuracy, And Decision Impact", Iconic Research and Engineering Journals, 2023. doi:10.64388/irev6i11-1716723
[7] Farhan Sharukh Hasan, Anirban Saha Anik, Eric Liu et al., "SourceMinds at CheckThat! 2026: NLI-Grounded Citation Auditing in a Multi-Agent Pipeline for Full Fact-Checking Article Generation", arXiv (Cornell University), 2026. doi:10.48550/arxiv.2607.24802
[8] Byron Wallace, Sayantan Saha, Frank Soboczenski et al., "Generating (Factual?) Narrative Summaries of RCTs: Experiments with\n Neural Multi-Document Summarization", arXiv (Cornell University), 2020. doi:10.48550/arxiv.2008.11293