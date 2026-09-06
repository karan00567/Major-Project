# Literature Review: How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?

## Methods and Architectures

### 3.1 Methodological Trends in Multi‑Agent Architectures for Knowledge‑Intensive Tasks 

Recent work on multi‑agent systems (MAS) for complex information‑processing problems converges on three complementary design axes: **training‑execution coordination**, **modular specialization**, and **information‑propagation control**. 

| Design axis | Representative approaches | Core methodological idea |
|-------------|---------------------------|--------------------------|
| **Centralized training / decentralized execution (CTDE)** | MAPPO for edge‑server monitoring | A Multi‑Agent Proximal Policy Optimization algorithm is trained centrally while each dispatcher executes its learned query‑and‑dispatch policy using only locally stale observations, thereby reconciling global optimality with on‑device autonomy【1】. |
| **Modular agent specialization** | LiRA literature‑review framework; MARS misinformation detector; CoTHSSum summarizer | Separate agents are assigned distinct sub‑tasks (e.g., outlining, fact‑checking, style analysis, hierarchical segmentation) and their outputs are later fused by a “judge” or decoder, enabling parallel reasoning and richer feature fusion【2】【12】【5】. |
| **Information‑propagation control via topology design** | EIB‑LEARNER topology; SAFE‑CARE benchmark layers | A causal framework evaluates how sparse versus dense communication graphs affect error diffusion, leading to a hybrid topology that balances robustness and bandwidth cost【11】; the benchmark isolates the impact of adding retrieval, guardrails, or memory layers on safety and user experience【8】. |

#### 3.1.1 CTDE versus Fully Decentralized Policies 

CTDE remains attractive for domains where global performance metrics (e.g., throughput‑cost trade‑offs) are hard to observe locally. MAPPO demonstrates that centralized policy gradients can be leveraged without requiring each agent to maintain a full view of the system state【1】. In contrast, fully decentralized reinforcement learning often suffers from non‑stationarity and limited credit assignment, prompting researchers to embed lightweight coordination mechanisms (e.g., periodic state broadcasts) as an alternative to full CTDE【7】. The survey on agentic LLMs notes that “retrieval enables tool use” and that “reflection improves multi‑agent collaboration,” suggesting that decentralized agents can compensate for limited training signals by augmenting inference with external knowledge sources【7】.

#### 3.1.2 Specialized Agent Pipelines 

LiRA’s pipeline partitions the literature‑review task into outlining, subsection drafting, editing, and final review agents, each fine‑tuned on a dedicated sub‑dataset (SciReviewGen and a proprietary ScienceDirect corpus)【2】. A similar modular philosophy underlies MARS, which deploys four domain‑specific agents (Fact Checker, Emotion Analyzer, Intent Recognizer, Style Analyzer) to extract orthogonal features before a cross‑agent review and a final Judge Agent synthesize the verdict【12】. CoTHSSum extends this idea to long‑form summarization by first segmenting documents hierarchically and then applying chain‑of‑thought prompting within each segment, yielding interpretable intermediate reasoning steps that are later combined through structure‑guided decoding【5】. Across these systems, the common advantage is **parallelizable reasoning** and **transparent intermediate artifacts**, which the Agentic LLMs survey identifies as a cross‑category benefit of multi‑agent collaboration【7】.

#### 3.1.3 Retrieval‑Augmented Interaction 

Retrieval‑augmented generation (RAG) appears both as a stand‑alone pipeline (e.g., an academic‑services chatbot that builds a domain‑specific knowledge base via hierarchical chunking and query reranking【10】) and as an auxiliary layer in multi‑agent setups (e.g., the retrieval component in SAFE‑CARE that isolates its safety impact【8】). Qlarify introduces *recursively expandable abstracts*, allowing users to iteratively request deeper context while the system retrieves and synthesizes additional passages on demand【4】. These approaches share the premise that **dynamic information retrieval can reduce the need for exhaustive model memorization**, a point echoed in the Agentic LLMs survey’s observation that “retrieval enables tool use”【7】.

#### 3.1.4 Topology‑Driven Information Diffusion 

The effectiveness of multi‑agent communication is not solely a function of agent competence but also of the underlying graph structure. EIB‑LEARNER proposes a hybrid topology that fuses dense connectivity (to promote beneficial information spread) with sparse links (to suppress error propagation), achieving lower communication cost and higher robustness in empirical evaluations【11】. The SAFE‑CARE benchmark complements this line of work by providing a controlled ablation environment where the addition or removal of a single architectural layer (e.g., memory or profile write‑back) can be directly linked to changes in safety and user‑experience metrics【8】. Together, these studies illustrate a **design tension**: dense graphs maximize knowledge sharing but increase the risk of cascading mistakes, whereas sparse graphs improve fault tolerance at the expense of slower convergence.

#### 3.1.5 Synthesis and Open Disagreements 

- **Training coordination**: While CTDE (MAPPO) is praised for achieving superior system‑level trade‑offs, the Agentic LLMs survey cautions that centralized training may limit scalability and adaptability in rapidly evolving domains【1】【7】. 
- **Modularity versus end‑to‑end learning**: Specialized pipelines (LiRA, MARS, CoTHSSum) report qualitative gains in interpretability and cross‑domain performance, yet the survey highlights that “reflection improves multi‑agent collaboration,” implying that end‑to‑end reflective mechanisms could replace explicit modularization in some settings【2】【12】【5】【7】. 
- **Topology design**: EIB‑LEARNER’s hybrid graphs are shown to outperform both purely dense and purely sparse configurations, but the SAFE‑CARE benchmark reveals that the *optimal* topology may be task‑dependent, as safety‑critical layers sometimes require denser communication to propagate guardrails effectively【11】【8】.

Overall, the emerging consensus is that **methodological diversity—spanning CTDE, modular specialization, retrieval augmentation, and topology engineering—offers a richer toolbox for building robust, scalable multi‑agent systems**. Future research will need to reconcile these strands, perhaps by developing adaptive architectures that can switch between centralized and decentralized modes, reconfigure agent specializations on the fly, and dynamically adjust communication graphs in response to observed error patterns.

## Evaluation and Benchmarks

### Evaluation and Benchmarks for Multi‑Agent and Retrieval‑Augmented Systems 

Recent work has introduced a variety of benchmark suites that target distinct evaluation dimensions of multi‑agent and retrieval‑augmented language‑model systems. SAFE‑CARE Bench provides a reproducible, tiered ablation framework that isolates the impact of individual architectural components (e.g., retrieval, guardrails, memory) on safety, user experience, and conversational coherence in multi‑turn healthcare dialogues [4]. In contrast, the MAPPO‑based edge‑server monitoring study evaluates policies through **throughput‑cost trade‑offs**, reporting performance across a range of query costs and job arrival rates [1]. Both benchmarks share a controlled experimental design, yet they differ in their primary metrics: SAFE‑CARE relies on Likert‑scale human‑like judgments (medical accuracy, safety, empathy), whereas MAPPO reports system‑level efficiency measures. 

Summarization research has also adopted rigorous quantitative metrics. CoTHSSum combines hierarchical segmentation with chain‑of‑thought prompting and is assessed with a suite of lexical and semantic scores—including ROUGE, BLEU, BERTScore, and factual‑consistency metrics—where it consistently outperforms prior state‑of‑the‑art baselines [2]. This contrasts with the evaluation of retrieval‑augmented generation (RAG) chatbots, which emphasizes **faithfulness** (0.91 on factual queries) and **context recall** (0.59 on reasoning tasks), alongside an out‑of‑context refusal rate of 81 % [5]. While CoTHSSum’s metrics capture content quality and factuality, the RAG evaluation foregrounds the system’s ability to refuse inappropriate queries, highlighting divergent priorities across tasks. 

Multi‑agent misinformation detection (MARS) and communication‑topology analysis (EIB‑LEARNER) further illustrate the breadth of evaluation strategies. MARS measures cross‑domain detection performance by comparing against three public misinformation benchmarks, demonstrating gains from multi‑dimensional feature fusion [7]. EIB‑LEARNER, on the other hand, assesses **task performance**, communication cost, and robustness under varying graph sparsities, reporting that moderately sparse topologies achieve optimal results [6]. Both studies employ comparative baselines, yet MARS focuses on classification accuracy across domains, whereas EIB‑LEARNER emphasizes system‑level efficiency and error propagation. 

Across these benchmarks, several common limitations emerge. SAFE‑CARE acknowledges that its LLM judge is not calibrated against human scores and that scenario coverage is confined to a single clinical domain [4]. The MAPPO evaluation, while thorough in throughput‑cost analysis, does not address safety or ethical considerations inherent to autonomous dispatch decisions [1]. CoTHSSum’s reliance on automatic metrics may overlook nuanced factual errors that human evaluation could reveal [2]. The RAG chatbot’s performance drops markedly on reasoning queries, indicating a gap between factual recall and deeper inference [5]. These shortcomings echo concerns raised in broader surveys of agentic LLMs, which highlight open problems in safety, liability, and the need for calibrated human‑in‑the‑loop evaluation [3]. 

Collectively, the literature demonstrates a move toward **task‑specific, multi‑metric benchmarking** that isolates component contributions (e.g., SAFE‑CARE’s tiered ablations) while also exposing trade‑offs between efficiency, safety, and factuality. Future benchmark design will likely need to integrate human calibration, broader domain coverage, and unified evaluation frameworks that can compare heterogeneous objectives across multi‑agent, summarization, and retrieval‑augmented paradigms.

## Limitations and Open Problems

### Safety and Liability 

Despite notable performance gains, current multi‑agent LLM frameworks still lack robust safety guarantees. Surveys of agentic LLMs explicitly identify safety, liability, and security risks associated with agents that take real‑world actions as open problems that have not been resolved [3].

### Evaluation and Benchmarking Gaps 

Benchmarks designed to assess safety in multi‑turn healthcare conversations reveal several methodological shortcomings. The SAFE‑CARE Bench reports that its LLM judge is not calibrated against human scores, that scenario coverage is confined to a single clinical domain, and that gold‑standard answers have not been independently reviewed by clinicians, preventing any claim of certified safety for deployment [4]. Moreover, the benchmark does not provide a turnkey runner, further limiting its reproducibility and practical utility [4].

### Reasoning Limitations in Retrieval‑Augmented Systems 

Retrieval‑augmented generation (RAG) chatbots can achieve high factual faithfulness (faithfulness = 0.91) but exhibit a pronounced drop in performance on reasoning queries, with Context Recall falling to 0.59 [5]. This disparity highlights a persistent limitation in handling complex inference despite strong factual retrieval capabilities [5].

### User‑Interface Accessibility 

Large digitized scientific repositories remain largely inaccessible to non‑specialist users. The Extended Specimen Network notes that existing portals are designed primarily for biodiversity scientists and collections professionals, limiting broader community use and underscoring the need for redesigned interfaces that support a wider audience [8].

### Ethical and Regulatory Gaps 

AI‑assisted scientific writing introduces ethical challenges such as fabricated citations, unintentional plagiarism, bias in training data, and factual inaccuracies that can erode scientific integrity [9]. Compounding these issues, industry‑wide standards for AI use in manuscript preparation are still under development, and current policies explicitly forbid applying AI to previously published material, leaving the practice under‑regulated [9].

### Communication‑Topology Design 

In multi‑agent LLM systems, the structure of communication topologies critically influences error propagation and beneficial information diffusion. Empirical studies show that moderately sparse topologies often yield optimal task performance, while overly dense or overly sparse graphs can respectively amplify errors or suppress useful signals, indicating that topology design remains an open research problem across diverse tasks [6].

### Need for Standardized, Domain‑Diverse Benchmarks 

The scarcity of reproducible, domain‑spanning evaluation suites hampers systematic comparison of multi‑agent LLM approaches. The SAFE‑CARE Bench’s limited clinical scope and lack of a turnkey execution framework exemplify this gap, emphasizing the necessity for broader, clinically validated benchmarks that can reliably certify safety and effectiveness [4].

### Summary 

Collectively, these findings expose a constellation of open problems: insufficient safety assurances, incomplete and narrowly scoped evaluation benchmarks, degraded reasoning performance in retrieval‑augmented pipelines, limited accessibility of scientific data interfaces, unresolved ethical and regulatory frameworks, and unresolved challenges in communication‑topology optimization. Addressing these limitations is essential for the trustworthy and widespread deployment of multi‑agent LLM systems [3],[4],[9],[5],[6],[8].

## References

[1] Samuel Chamoun, Christian McDowell, Robin Buchanan et al., "MAPPO for Edge Server Monitoring", 2025. doi:10.1109/milcom64451.2025.11310582
[2] Xiaoyong Chen, Zhiqiang Chen, Shi Cheng, "CoTHSSum: Structured long-document summarization via chain-of-thought reasoning and hierarchical segmentation", Journal of King Saud University - Computer and Information Sciences, 2025. doi:10.1007/s44443-025-00041-2
[3] Aske Plaat, Max van Duijn, Bas van Stein et al., "Agentic Large Language Models, a Survey", Journal of Artificial Intelligence Research, 2025. doi:10.1613/jair.1.18675
[4] Yassen Eltayeb, Monzir Hafez, "SAFE-CARE Bench: A Reproducible Benchmark for Safety, Guardrails, and User Experience in Multi-Turn Healthcare AI Agent Conversations", Open MIND, 2026. doi:10.5281/zenodo.21444598
[5] M. N. Husain, Yudi Wibisono, Ani Anisyah, "Development of an Academic Services Chatbot Based on Retrieval-Augmented Generation (RAG)", Brilliance Research of Artificial Intelligence, 2025. doi:10.47709/brilliance.v5i2.6719
[6] Xu Shen, Yixin Liu, Yiwei Dai et al., "Understanding the Information Propagation Effects of Communication Topologies in LLM-based Multi-Agent Systems", 2025. doi:10.18653/v1/2025.emnlp-main.623
[7] Shengyuan Dai, "MARS: Multi-Agent Retrieval-Augmented Synergy for Cross-Domain Misinformation Detection", Zenodo (CERN European Organization for Nuclear Research), 2026. doi:10.5281/zenodo.19071537
[8] James C. Lendemer, Barbara M. Thiers, Anna Monfils et al., "The Extended Specimen Network: A Strategy to Enhance US Biodiversity Collections, Promote Research and Education", BioScience, 2019. doi:10.1093/biosci/biz140
[9] Muhammad Nadeem Yousaf, "Practical Considerations and Ethical Implications of Using Artificial Intelligence in Writing Scientific Manuscripts", ACG Case Reports Journal, 2025. doi:10.14309/crj.0000000000001629