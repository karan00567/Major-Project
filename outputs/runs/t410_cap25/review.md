# Literature Review: How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?

## Methods and Architectures

### Methods and Architectures – Method

Fine‑tuning large language models (LLMs) as dense retrievers has emerged as a scalable alternative to traditional embedding‑based pipelines. In one recent study, the open‑source LLaMA‑2 model was fine‑tuned to serve both as a dense retriever (repLLaMA) and a pointwise reranker (rankLLaMA) within a multi‑stage ranking pipeline, achieving strong performance on MS MARCO and BEIR without the need for heuristic document segmentation [1]. The authors argue that finetuned LLM retrieval models outperform smaller models, generalise better, and require only a straightforward training strategy, thereby simplifying deployment in real‑world retrieval settings [1].

A complementary line of work focuses on improving factual consistency in abstractive summarisation. By generating weakly‑supervised training data through rule‑based transformations and jointly training a single model on consistency detection, span extraction, and inconsistency extraction, the proposed approach substantially outperforms prior models on factual consistency verification and aids human verification through auxiliary span‑extraction tasks [2].

In the domain of automated ablation planning, a benchmark suite called AblationBench was introduced to evaluate language‑model agents on author‑ and reviewer‑style ablation tasks. The best‑performing LM system identified only 45 % of the original ablations on average, revealing a significant gap to human performance and highlighting the need for more sophisticated planning capabilities [3].

For cross‑modal retrieval, a multi‑pathway generative adversarial hashing framework was proposed to exploit the underlying manifold structure across modalities. The generative model selects informative data from other modalities to challenge a discriminative model, leading to improved retrieval accuracy as demonstrated on three widely used datasets [4].

Mechanistic interpretability studies of GenIR models have dissected the internal retrieval process using patching and vocabulary projections. These analyses revealed that the decoder is the primary component for successful retrieval, with query‑document interaction occurring only in the interaction stage of the retrieval pipeline [5].

To mitigate hallucinations in large language models, a knowledge‑graph‑based retrofitting (KGR) framework was introduced. KGR retrofits initial draft responses by extracting, selecting, validating, and retrofitting factual statements from knowledge graphs, significantly improving performance on factual QA benchmarks, especially for complex reasoning tasks [6].

In multi‑agent reinforcement learning, a joint attention mechanism was employed to align the visual attention of agents with that of their peers. This incentive reduced the exponential cost of exploring the joint action space, improved coordination performance, and enabled agents to learn from experts present in the environment, outperforming a competitive centralized critic baseline across multiple environments [7].

Finally, a retrieval‑governed, graph‑augmented RAG architecture (GRACE‑RAG) was proposed for canonical evidence synthesis in closed‑domain institutional settings. By externalising structural reasoning to a structured retrieval layer, the architecture achieved consistent improvements in completeness, depth, and anticipatory coverage, with overall quality gains of up to 20 % under mid‑scale models while reducing computational and latency footprints [8].

## Evaluation and Benchmarks

## Evaluation and Benchmarks – Evaluation

Evaluating retrieval‑augmented language models (RAG) and related retrieval pipelines requires metrics that capture both retrieval quality and downstream task performance. Recent work has introduced multi‑stage benchmarks that combine passage‑level and document‑level retrieval, as well as task‑specific factual consistency checks.

### Multi‑stage retrieval pipelines

Fine‑tuning large language models (LLMs) as dense retrievers and rerankers has become a common strategy. In a recent study, the authors fine‑tuned the open‑source LLaMA‑2 model to serve as both a dense retriever (repLLaMA) and a pointwise reranker (rankLLaMA) within a multi‑stage ranking pipeline. The repLLaMA‑rankLLaMA pipeline achieved high effectiveness on the MS MARCO and BEIR benchmarks, demonstrating that finetuned LLM retrieval models outperform smaller models, generalise better, and can directly encode longer documents without heuristic segmentation [1].

### Factual consistency evaluation

For abstractive summarisation, a weakly‑supervised, model‑based approach was proposed that generates training data via rule‑based transformations and jointly trains a model to (1) detect factual consistency, (2) extract supporting spans, and (3) extract inconsistent spans. This method substantially outperformed prior models on factual consistency verification, and the auxiliary span‑extraction tasks aid human verification of factual consistency [2].

### Ablation planning benchmarks

A new benchmark suite, AblationBench, evaluates language‑model agents on ablation planning in empirical AI research. The benchmark comprises two tasks—AuthorAblation and ReviewerAblation—using LM‑based judges for automatic evaluation. The best‑performing LM system identifies only 45 % of the original ablations on average, highlighting a gap to human performance and the need for better evaluation metrics in this domain [3].

### Retrieval‑specific interpretability

Reverse‑engineering studies of GenIR models apply mechanistic interpretability techniques such as patching and vocabulary projections to dissect the internal retrieval process. The decoder is identified as the primary component for successful retrieval, with retrieval divided into priming, bridging (cross‑attention), and interaction stages. These insights inform the design of evaluation protocols that isolate the contribution of each component [5].

### Knowledge‑graph retrofitting

Knowledge‑graph‑based retrofitting (KGR) retrofits initial draft responses of LLMs with factual knowledge extracted from knowledge graphs. KGR significantly improves performance on factual QA benchmarks, especially for complex reasoning tasks, suggesting that evaluation should include knowledge‑grounded reasoning metrics [6].

### Retrieval‑governed architectures

The GRACE‑RAG architecture externalises structural reasoning to a structured retrieval layer, enabling lightweight deployment in closed‑domain settings. Evaluation on three model capacities shows consistent improvements in completeness, depth, and anticipatory coverage, with overall quality gains of up to 20 % under mid‑scale models. These results demonstrate that evaluation metrics should capture not only retrieval accuracy but also the quality of the generated content in terms of completeness and depth [8].

---

These studies collectively illustrate the evolving landscape of evaluation for retrieval‑augmented systems, emphasizing multi‑stage pipelines, factual consistency, component‑level interpretability, knowledge grounding, and domain‑specific quality metrics.

## Limitations and Open Problems

### Limitations and Open Problems

Despite recent progress in leveraging large language models (LLMs) for retrieval, summarization, and multimodal reasoning, several fundamental limitations persist across the literature.

1. **Retrieval‑by‑LLM Bottlenecks** 
 Fine‑tuning LLMs as dense retrievers (repLLaMA) and rerankers (rankLLaMA) yields strong performance on benchmark corpora such as MS MARCO and BEIR, yet the approach remains constrained by the inherent scalability of transformer‑based encoders. The abstract of the repLLaMA‑rankLLaMA study notes that the decoder is the primary component for successful retrieval, but it does not quantify the computational overhead or memory footprint required for large‑scale deployment [5]. Moreover, the lack of explicit failure modes or error analyses limits our understanding of when and why these models mis‑rank relevant passages.

2. **Hallucination and Factual Consistency** 
 Even with weakly‑supervised consistency verification models that jointly predict factuality and extract supporting spans, the approach still relies on rule‑based data generation and does not fully address the root cause of hallucinations in open‑ended generation. The Knowledge‑Graph‑Based Retrofitting (KGR) framework demonstrates significant gains on factual QA benchmarks, yet it is unclear how well it generalizes to complex, multi‑step reasoning tasks or to domains with sparse graph coverage [6]. The absence of a systematic evaluation of KGR’s impact on hallucination rates in free‑form summarization remains an open question.

3. **Agent‑Based Ablation Planning** 
 AblationBench reveals that state‑of‑the‑art language‑model agents identify only 45 % of original ablations, falling short of human performance. The benchmark highlights an inverse performance trend between author and reviewer tasks, suggesting that current prompting strategies are insufficiently grounded in domain knowledge. The study does not explore whether incorporating external knowledge bases or structured reasoning modules could bridge this gap [3].

4. **Multimodal Hallucinations** 
 The review of multimodal hallucinations underscores the difficulty of reliably distinguishing genuine multimodal signals from spurious correlations. While the review proposes future research directions, it does not provide empirical evidence on the effectiveness of proposed assessment tools or on the extent to which current multimodal models (e.g., generative adversarial hashing) mitigate hallucinations. The lack of quantitative benchmarks for multimodal hallucination detection remains a critical limitation [10].

5. **Governance and Deployment Constraints** 
 The GRACE‑RAG architecture offers a promising avenue for lightweight, closed‑domain deployment by externalizing structural reasoning to a retrieval layer. However, the reported 20 % quality gain is limited to mid‑scale models, and the approach still depends on a well‑curated graph that may not exist in many institutional settings. The scalability of this governance framework to larger, more heterogeneous knowledge graphs is yet to be demonstrated [8].

6. **Transparency and Accountability** 
 The International Committee of Medical Journal Editors’ 2023 recommendations mandate disclosure of AI assistance in manuscript preparation, yet they explicitly prohibit listing chatbots as authors due to their lack of responsibility. This policy highlights a broader issue: current AI systems lack mechanisms for accountability and traceability of generated content, which hampers their adoption in high‑stakes domains such as medical research [9].

In summary, while fine‑tuned LLMs and auxiliary frameworks (e.g., KGR, GRACE‑RAG) show promise, they are still limited by scalability, hallucination control, lack of structured reasoning, and governance challenges. Addressing these open problems will require integrated approaches that combine mechanistic interpretability, knowledge‑graph augmentation, and robust evaluation benchmarks.

## References

[1] Xueguang Ma, Liang Wang, Nan Yang et al., "Fine-Tuning LLaMA for Multi-Stage Text Retrieval", 2024. doi:10.1145/3626772.3657951
[2] Wojciech Kryściński, Bryan McCann, Caiming Xiong et al., "Evaluating the Factual Consistency of Abstractive Text Summarization", 2020. doi:10.18653/v1/2020.emnlp-main.750
[3] Talor Abramovich, Gal Chechik, "AblationBench: Evaluating Automated Planning of Ablations in Empirical AI Research", arXiv, 2025. doi:10.48550/arxiv.2507.08038
[4] Jian Zhang, Yuxin Peng, "Multi-Pathway Generative Adversarial Hashing for Unsupervised Cross-Modal Retrieval", IEEE Transactions on Multimedia, 2019. doi:10.1109/tmm.2019.2922128
[5] Anja Reusch, Yonatan Belinkov, "Reverse-Engineering the Retrieval Process in GenIR Models", arXiv, 2025. doi:10.48550/arxiv.2503.19715
[6] Xinyan Guan, Yanjiang Liu, Hongyu Lin et al., "Mitigating Large Language Model Hallucinations via Autonomous Knowledge Graph-Based Retrofitting", Proceedings of the AAAI Conference on Artificial Intelligence, 2024. doi:10.1609/aaai.v38i16.29770
[7] Dennis Lee, Natasha Jaques, Chase Kew et al., "Joint Attention for Multi-Agent Coordination and Social Learning", arXiv, 2021. doi:10.48550/arxiv.2104.07750
[8] Asit Desai, Aman Kumar, Prashant Devadiga, "GRACE-RAG: Governed Retrieval Architecture for Canonical Evidence Synthesis, Enabling Lightweight Deployment in Closed-Domain Institutional Settings", arXiv, 2026. doi:10.48550/arxiv.2607.00013
[9] Fernándo Alfonso, Filippo Crea, "New recommendations of the International Committee of Medical Journal Editors: use of artificial intelligence", European Heart Journal, 2023. doi:10.1093/eurheartj/ehad448
[10] Marcella Montagnese, Pantelis Leptourgos, Charles Fernyhough et al., "A Review of Multimodal Hallucinations: Categorization, Assessment, Theoretical Perspectives, and Clinical Recommendations", Schizophrenia Bulletin, 2020. doi:10.1093/schbul/sbaa101