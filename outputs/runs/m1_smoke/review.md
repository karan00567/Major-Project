# Literature Review: How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?

## Methods and Architectures

### Methodological Trends in Agentic Systems 

Recent work on agentic architectures reveals a convergence toward **semantic structuring**, **graph‑augmented memory**, and **iterative test‑driven refinement** as complementary strategies for improving reliability, interpretability, and coverage. 

| Theme | Representative Approaches | Core Mechanisms |
|-------|---------------------------|-----------------|
| **Semantic rule‑based scaffolding** | Semantic Crosswalk and Type‑Separation Canon Locks [1] | Consolidates a domain‑specific lexicon, separates authority and phase types, and records a non‑substitution canon that makes substitution defects explicit. |
| **Graph‑centric memory and retrieval** | Silent Multi‑Agent Recommendation Engine [2]; MM‑Mem multimodal memory [6] | Employs a directed‑acyclic LangGraph to orchestrate agentic RAG, dense vector retrieval (Qdrant), and knowledge‑graph traversal (Apache AGE); hierarchically distills perceptual traces into symbolic schemas via a semantic information bottleneck. |
| **Test‑driven iterative generation** | TDD‑Agent [3] | Generates executable tests first, then refines code and tests in a dual‑track loop guided by execution feedback. |
| **Deterministic pipeline enforcement** | Completeness Gap study [4] | Replaces self‑directed LLM search with deterministic pre‑fetch and reconciliation checklists, and later with a “most‑recently‑filed wins” heuristic to close coverage gaps. |
| **Systematic evaluation of linking methods** | Entity‑Linking with Wikidata review [5] | Maps eight dimensions of entity‑linking research, highlighting the need for hybrid rule‑learning pipelines and robust handling of ambiguity. |

#### 1. Semantic Structuring as a Guardrail 
The Semantic Crosswalk framework demonstrates that **explicitly codifying domain semantics**—through load‑bearing terms, phase boundaries, and non‑substitution rules—can surface hidden defects without altering the underlying doctrine [1]. This mirrors findings from the Wikidata entity‑linking review, which stresses the importance of **rule‑based components** to mitigate ambiguity and data noise across heterogeneous knowledge bases [5]. Both lines of work argue that a **semantic scaffold** improves interpretability and error detection, albeit the Crosswalk approach focuses on legal corpora while the entity‑linking survey targets broader NLP tasks.

#### 2. Graph‑Augmented and Hierarchical Memory 
Graph‑augmented architectures have emerged as a unifying substrate for multi‑agent reasoning. The Silent Multi‑Agent Recommendation Engine integrates **agentic retrieval‑augmented generation** with persistent graph storage, enabling deterministic constraint verification (e.g., stock availability) and sub‑4‑second latency when semantic justification is omitted [2]. Complementarily, MM‑Mem introduces a **pyramidal multimodal memory** that progressively abstracts raw perceptual inputs into high‑level symbolic schemas, guided by a semantic information bottleneck objective [6]. While the former emphasizes **knowledge‑graph traversal for external data grounding**, the latter focuses on **internal hierarchical compression** to reduce redundancy. Together they illustrate a spectrum where **graph structures serve both external retrieval and internal abstraction**.

#### 3. Iterative Test‑Driven Refinement 
TDD‑Agent operationalizes **test‑driven development** within code‑generation pipelines, first eliciting executable specifications before iteratively refining both code and tests using execution feedback [3]. Empirical results show consistent gains over pure reasoning‑based prompting and retrieval‑augmented baselines on LiveCodeBench and RepoEval, suggesting that **closed‑loop verification** can be a universal augment for agentic outputs, regardless of domain (e.g., code vs. recommendation). This aligns with the broader observation that **deterministic checks**—whether test suites or reconciliation checklists—enhance downstream reliability.

#### 4. Deterministic Pipeline Interventions for Coverage 
The Completeness Gap analysis uncovers systematic **coverage failures** at every layer of a typical LLM‑centric research pipeline [4]. By substituting the self‑directed LLM search with a deterministic pre‑fetch of authoritative sources and a mandatory reconciliation checklist, coverage more than triples (from 9 to 28 captured events). However, even the subsequent deterministic heuristic (“most‑recently filed wins”) exhibits severe under‑coverage (3.8 % of true portfolio value), underscoring that **determinism alone does not guarantee completeness** and must be coupled with robust selection criteria.

#### 5. Emerging Consensus and Open Disagreements 
Across these studies, a **consensus** emerges that **explicit semantic constraints** (rule‑based locks, test suites, reconciliation checklists) improve agentic trustworthiness. Conversely, **disagreements** persist regarding the optimal granularity of such constraints: the Semantic Crosswalk advocates a **domain‑specific canon**, whereas the Completeness Gap work favors **generic deterministic pre‑fetch** without domain tailoring. Moreover, the trade‑off between **latency and semantic justification** highlighted in the recommendation engine (fast execution when justification is bypassed) contrasts with MM‑Mem’s emphasis on **semantic abstraction** as a prerequisite for long‑horizon understanding, suggesting divergent priorities between **real‑time operational constraints** and **deep reasoning fidelity**.

#### 6. Outlook 
Future architectures are likely to **hybridize these strands**, embedding semantic rule layers within graph‑augmented memories while employing test‑driven loops to validate both retrieval and reasoning steps. Such integration could address the completeness gaps identified in pipeline studies while preserving the low‑latency, high‑accuracy characteristics demonstrated in multi‑agent recommendation systems.

## Applications

### Applications of Agentic and Semantic Architectures 

Recent literature demonstrates an expanding portfolio of applications for agentic and semantic frameworks, ranging from legal doctrine management to immersive video agents, and from law‑enforcement decision support to automated code synthesis [1][2][3][4][6].

**Legal and policy domains.** 
A consolidated semantic architecture for the Applicability Boundary Doctrine introduces a load‑bearing lexicon, separates authority and phase types, and records a non‑substitution canon that makes substitution defects visible, while deliberately avoiding runtime enforcement mechanisms and new doctrinal introductions [1]. Parallel work on law‑enforcement agents underscores that officers’ internal convictions—shaped by early‑life worldviews—can bias discretionary decisions, suggesting that application‑level interventions should incorporate value‑based assessments when designing decision‑support tools [7].

**Enterprise recommendation and commerce.** 
In B2B e‑commerce, a silent multi‑agent recommendation engine employs graph‑augmented memory and retrieval‑augmented generation to infer implicit user preferences without explicit textual input. The system achieves high retrieval accuracy, strict stock‑availability verification, and sub‑4‑second end‑to‑end latency when the generative justification step is omitted, all without reliance on external APIs [2].

**Software engineering and code generation.** 
Test‑driven reasoning agents operationalize test‑driven development for code synthesis: they first generate executable tests to clarify expected behavior, then iteratively refine both tests and code using execution feedback. This approach consistently outperforms reasoning‑only prompting and retrieval‑based baselines on benchmarks such as LiveCodeBench and RepoEval, yielding higher pass rates, coverage, and mutation scores [3].

**Completeness and coverage in LLM pipelines.** 
Empirical analyses of agentic LLM research pipelines reveal a persistent “completeness gap” across system layers. Introducing deterministic pre‑fetch with a reconciliation checklist more than triples measured coverage (from 9 to 28 captured events), yet even the most recent deterministic heuristic captures only a small fraction of true holdings, highlighting the need for application‑aware completeness strategies throughout the pipeline [4].

**Entity linking and knowledge‑graph grounding.** 
A systematic review of Wikidata‑based entity linking identifies that current datasets focus on question‑answering and news, while underutilizing Wikidata’s strengths in hyper‑relations, multilingualism, and temporal reasoning. The authors call for richer datasets and hybrid rule‑learning methods to support applications demanding robust semantic grounding [5].

**Ethical governance of scholarly dissemination.** 
The lack of uniform regulation across preprint servers enables duplicated or cloned submissions, which can inflate citation counts and enhance curricula vitae without substantive contribution, pointing to a pressing need for application‑level ethical oversight mechanisms [8].

**Long‑horizon multimodal video agents.** 
A pyramidal multimodal memory architecture inspired by fuzzy‑trace theory hierarchically distills fine‑grained perceptual traces into high‑level semantic schemas. This semantic information bottleneck reduces redundancy and enables efficient long‑horizon video understanding, opening avenues for applications in surveillance, autonomous navigation, and content summarization [6].

## Evaluation and Benchmarks

### Evaluation Practices and Benchmark Gaps in Agentic LLM Systems 

The empirical assessment of agentic language‑model pipelines has coalesced around three complementary dimensions: **functional correctness**, **coverage/completeness**, and **efficiency**. 

*Functional correctness* is most often quantified with task‑specific benchmarks. In code‑generation settings, the **LiveCodeBench** and **RepoEval** suites provide pass‑rate, test‑coverage, and mutation‑score metrics that capture both syntactic validity and semantic fidelity of generated programs. Test‑driven agents that first synthesize executable tests and then iteratively refine code achieve consistently higher pass rates, broader coverage, and superior mutation scores than reasoning‑only or retrieval‑augmented baselines [3]. 

*Coverage*—the proportion of relevant information retrieved or processed—has emerged as a critical yet under‑addressed evaluation axis. A systematic case study of a three‑stage LLM research pipeline revealed that a self‑directed LLM search captured only **56 %** of known events and **0 %** of structured table entries, whereas inserting a deterministic pre‑fetch step with a reconciliation checklist more than **tripled** measured coverage (from 9 to 28 events) [4]. Nevertheless, even the most deterministic third‑generation heuristic recovered merely **3.8 %** of true portfolio value, underscoring a persistent “completeness gap” that recurs at every architectural layer [4]. 

*Efficiency* is evaluated through retrieval accuracy, constraint adherence, and latency. A silent multi‑agent recommendation engine that couples graph‑augmented memory with agentic retrieval‑augmented generation attains **high retrieval accuracy** and strict **stock‑availability constraint adherence**, while delivering **sub‑4‑second** end‑to‑end latency when the generative semantic justification step is omitted [2]. These results illustrate that latency budgets can be met without sacrificing correctness, provided that the evaluation explicitly measures both retrieval fidelity and operational constraints. 

Across domains, the **choice of benchmark datasets** shapes reported performance and reveals systematic blind spots. Entity‑linking research, for example, has highlighted a reliance on question‑answering and news corpora while under‑utilizing Wikidata’s rich hyper‑relational, multilingual, and temporal dimensions; this mismatch points to a need for more diverse, knowledge‑graph‑centric evaluation suites [5]. Similarly, multimodal video agents are assessed on a quartet of benchmarks that test both offline and streaming scenarios; the pyramidal memory architecture grounded in the Semantic Information Bottleneck achieves state‑of‑the‑art scores, demonstrating that hierarchical, cognition‑inspired evaluation metrics (e.g., entropy‑driven retrieval quality) can capture long‑horizon understanding more effectively than flat accuracy measures [6]. 

Collectively, these studies suggest a **convergence toward multi‑metric evaluation frameworks** that balance correctness, completeness, and efficiency. However, disagreements remain regarding the optimal trade‑off: deterministic pre‑fetch mechanisms dramatically improve coverage but may limit adaptability, whereas fully LLM‑driven searches preserve flexibility at the cost of severe coverage loss [4]. Future benchmark design should therefore incorporate **coverage‑sensitive metrics** (e.g., event‑capture rate, portfolio‑value recall) alongside traditional correctness scores to surface these trade‑offs and guide the development of more robust agentic systems.

## Limitations and Open Problems

### Limitations and Open Problems 

Recent work on agentic and semantic systems repeatedly highlights structural gaps that impede reliable deployment. A common shortcoming is the **absence of runtime enforcement mechanisms**. The *Semantic Crosswalk* framework makes substitution defects visible but deliberately introduces no controller or enforcement layer, leaving the doctrine vulnerable to unchecked violations [1]. A parallel observation emerges from the *TDD‑Agent* pipeline, where test‑driven refinement improves pass rates yet still depends on the model’s ability to generate correct tests, offering no external guard against logical errors [3]. Together, these studies expose a broader need for **formal verification or monitoring components** that can intervene during execution rather than merely flagging defects post‑hoc. 

Another persistent limitation concerns **coverage and completeness** across multi‑stage pipelines. The *Completeness Gap* analysis demonstrates that even deterministic pre‑fetch with a reconciliation checklist only triples event capture (from 9 to 28 events) but still fails to achieve acceptable recall, and the subsequent “most‑recent‑wins” heuristic drops coverage to a negligible 3.8 % [4]. This mirrors findings from the *Entity Linking* review, which identifies chronic dataset sparsity, ambiguous entity types, and noisy knowledge‑graph evolution as barriers that prevent comprehensive linking [5]. Both lines of evidence converge on the conclusion that **pipeline‑level heuristics alone cannot guarantee exhaustive information retrieval**, and that richer, dynamically updated corpora are required. 

The **dependence on synthetic or narrowly scoped datasets** further restricts generalizability. The *Silent Multi‑Agent Recommendation Engine* achieves sub‑4‑second latency and high retrieval accuracy on a synthetic B2B product catalog, yet its evaluation does not extend to heterogeneous real‑world inventories, raising concerns about scalability [2]. Similarly, the *From Verbatim to Gist* memory architecture reports state‑of‑the‑art performance on four benchmarks, but its hierarchical abstraction may discard fine‑grained details essential for tasks that demand verbatim recall [6]. These complementary observations suggest an open problem: **balancing efficiency‑driven abstraction with fidelity to raw data** in long‑horizon agents. 

Human factors also surface as a source of limitation. The study on **worldview influences** reveals that law‑enforcement agents’ discretionary decisions are heavily shaped by childhood‑formed values, potentially leading to procedural outcomes that diverge from case facts [7]. This sociotechnical insight underscores a gap in current system designs, which largely ignore the **ethical and psychological dimensions** of autonomous decision‑making. 

Finally, the **lack of uniform ethical regulation** for preprint dissemination creates avenues for citation manipulation and CV inflation, as highlighted in the discussion of duplicated or cloned preprints [8]. The absence of cross‑platform oversight compounds the reproducibility challenges already noted in the empirical case studies above. 

Collectively, these strands point to several open research directions: (i) integrating runtime verification and controller modules into semantic doctrines; (ii) developing statistically robust benchmarks that capture full‑pipeline coverage; (iii) curating diverse, real‑world datasets to test abstraction‑heavy memory models; (iv) embedding ethical and psychological safeguards into autonomous agents; and (v) establishing standardized governance for preprint ecosystems. Addressing these limitations will be essential for moving from proof‑of‑concept prototypes to trustworthy, production‑grade agentic systems.

## References

[1] Vadym Partasyuk, "Semantic Crosswalk and Type-Separation Canon Locks: Load-Bearing Terms, Phase Boundaries, and Non-Substitution Rules for the Applicability Boundary Doctrine", Zenodo (CERN European Organization for Nuclear Research), 2026. doi:10.5281/zenodo.21985437
[2] Davi Silva Eleuterio, Pedro Filipe Oliveira, Paulo Matos, "A Silent Multi-Agent Recommendation Engine with Graph-Augmented Memory for Immersive B2B E-Commerce", DROPS (Schloss Dagstuhl – Leibniz Center for Informatics), 2026. doi:10.4230/oasics.slate.2026.15
[3] Hongyue Yu, Kefan Li, Jiakun Li et al., "TDD-Agent: Test-Driven Reasoning for Code Generation", arXiv (Cornell University), 2026. doi:10.48550/arxiv.2608.16742
[4] Ritik Sharma, Balveer Singh Thakur, "The Completeness Gap: Coverage Failures at Every Layer of an Agentic LLM Research Pipeline", Open MIND, 2026. doi:10.5281/zenodo.21992671
[5] Philipp Scharpf, Corinna Breitinger, Spitz Andreas et al., "Entity Linking with Wikidata: A Systematic Literature Review", ACM Computing Surveys, 2026. doi:10.1145/3795134
[6] Niu Lian, Yuting Wang, Hanshu Yao et al., "From Verbatim to Gist: Distilling Pyramidal Multimodal Memory via Semantic Information Bottleneck for Long-Horizon Video Agents", arXiv (Cornell University), 2026. doi:10.48550/arxiv.2603.01455
[7] Roman VANDZHURAK, "The worldview influence on the internal beliefs of law enforcement agents in the context of exercising their discretionary powers", Ûridičnij časopis Nacìonalʹnoï akademìï vnutrìšnìh sprav, 2024. doi:10.56215/naia-chasopis/1.2024.60
[8] J. A. Teixeira da Silva, "Duplicated or cloned preprints: the lack of across-the-board ethical regulation of preprint servers may risk leading to citation-abusive and curriculum vitae-enhancing practices", Читалиште, 2025. doi:10.19090/cit.2025.46.79-85