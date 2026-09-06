# Literature Review: How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?

## Methods and Architectures

### Methods and Architectures for Knowledge‑Intensive Text Generation 

Recent work on automated scientific writing has explored a spectrum of methodological paradigms, ranging from formal multi‑agent systems to neural summarization pipelines augmented with factual‑consistency checks. 

**Formal multi‑agent architectures.** A 2023 study introduced a formally verified multi‑agent framework that decomposes rule extraction and knowledge interpretation into five specialized agents using closed‑path rules and predicate logic [1]. By encoding relevance criteria directly into the formal model, the system can automatically discard irrelevant fragments, thereby improving scalability when processing extensive knowledge repositories. The authors argue that the decentralized, autonomous nature of the agent‑based paradigm enables dynamic interpretation of large, complex knowledge bases, a property that contrasts with monolithic neural models that lack explicit modularity. 

**Neural abstractive summarization with factual supervision.** Weakly‑supervised approaches have been proposed to improve factual consistency in generated summaries. One method creates synthetic training data through rule‑based transformations of source sentences and jointly trains a model to (i) detect factual drift, (ii) extract supporting spans, and (iii) locate inconsistent spans in the summary [2]. This auxiliary span‑extraction task not only boosts factual‑consistency performance relative to prior supervised baselines but also provides interpretable evidence for human verification. A complementary study on long‑document summarization reported that fine‑grained continuous consistency scores are more reliable than binary judgments, highlighting the importance of nuanced evaluation metrics for large‑scale scientific texts [6]. 

**Domain‑specific neural pipelines.** Experiments on biomedical systematic reviews demonstrated that modern neural multi‑document summarizers can produce fluent, relevant narratives, yet factual errors remain a concern [4]. Incorporating domain‑specific strategies—such as leveraging trial conclusions as target summaries—yields modest gains in factual accuracy, suggesting that task‑tailored data curation can partially mitigate hallucination. 

**Retrieval‑augmented generation (RAG).** Comparative evaluations of literature‑review automation revealed that a RAG system built on GPT‑3.5‑turbo outperforms both a frequency‑based spaCy pipeline and a vanilla transformer (Simple T5) on the SciTLDR benchmark, achieving the highest ROUGE‑1 score (0.364) [3]. The RAG approach benefits from external knowledge retrieval, which can ground generated text in up‑to‑date sources, thereby addressing the factual‑consistency challenges observed in purely generative models. 

**Hybrid ethical‑technical considerations.** While methodological advances enhance automation, recent analyses stress the necessity of ethical safeguards. Tools that detect AI‑generated manuscript sections achieve >99 % accuracy on scientific perspectives and 98–100 % on chemistry introductions, underscoring the feasibility of monitoring model output without impeding legitimate use [5]. Moreover, practical guidelines emphasize maintaining human oversight to preserve accountability and prevent ethical breaches such as undisclosed AI assistance or self‑plagiarism [7]. 

Collectively, these studies illustrate a convergence toward hybrid architectures that combine formal reasoning, modular agent design, and neural generation with explicit factual‑consistency supervision. The emerging consensus is that integrating retrieval mechanisms and fine‑grained evaluation metrics can substantially improve the reliability of automated scientific writing, provided that robust ethical frameworks accompany technical deployment.

## Evaluation and Benchmarks

### Evaluation and Benchmarks in Automated Scientific Writing 

The reliability of automated literature‑review and summarisation systems is typically assessed with reference‑based metrics such as ROUGE‑1, which quantifies n‑gram overlap with human‑written abstracts. In a comparative study of three generation pipelines—frequency‑based spaCy, a transformer‑based Simple T5, and a retrieval‑augmented generation (RAG) approach using GPT‑3.5‑turbo—ROUGE‑1 scores revealed a clear hierarchy, with the RAG system achieving the highest score of 0.364, followed by the transformer model and finally the spaCy baseline [3]. 

Beyond surface overlap, factual consistency has emerged as a critical dimension of evaluation, especially for abstractive summarisation of biomedical evidence. A weakly‑supervised framework that creates training data through rule‑based sentence transformations and jointly learns to (i) detect factual drift, (ii) extract supporting source spans, and (iii) pinpoint inconsistent summary spans, demonstrated substantial gains over prior models and provided auxiliary span extraction that aids human verification [2]. Complementary work on long‑document summarisation confirmed that fine‑grained continuous consistency scores are more reliable than binary judgments, although advanced systems still suffer from false positives and limited error granularity [6]. 

Empirical analyses of neural multi‑document summarisation for randomised controlled trials (RCTs) further illustrate the trade‑off between fluency and factuality. While modern abstractive models produce fluent and relevant narratives, their factual accuracy remains imperfect; domain‑specific strategies can modestly improve correctness but do not eliminate errors [4]. This aligns with observations that factual consistency evaluation systems exhibit higher recall on older summaries yet struggle with precise error detection [6]. 

Benchmark datasets underpin these evaluations. The SciTLDR corpus, used to assess literature‑review generation pipelines, provides a standardized testbed for ROUGE‑based comparison [3]. In the biomedical domain, Cochrane systematic‑review abstracts serve as source material for RCT summarisation experiments, enabling measurement of fluency, relevance, and factual accuracy [4]. 

To support reproducibility and provenance of evaluation artifacts, versioned repository frameworks such as QIK‑VRT record repository states, checksums, and audit metadata, thereby facilitating external review and citation of benchmark results [8]. 

Collectively, these studies highlight a multi‑faceted evaluation landscape: surface‑level overlap metrics, fine‑grained factual consistency scoring, and robust provenance tracking are all essential for trustworthy assessment of automated scientific writing tools.

## Limitations and Open Problems

### Limitations and Open Problems

The decentralised, multi‑agent architecture proposed for rule extraction and knowledge interpretation, while offering scalability, remains largely untested on heterogeneous real‑world knowledge bases, and its formal guarantees have not been empirically validated beyond synthetic datasets [1]. 

Factual consistency remains a persistent bottleneck for abstractive summarisation systems. Weakly‑supervised consistency models improve detection of inconsistencies, yet they still rely on auxiliary span‑extraction tasks that can miss subtle errors, especially in long‑form documents [2, 7]. Moreover, neural multi‑document summarisation of biomedical trials produces fluent narratives but frequently introduces factual inaccuracies that domain‑specific heuristics only modestly mitigate [4]. 

Efforts to automate literature reviews with retrieval‑augmented generation achieve higher ROUGE scores than traditional transformers, but the reliance on surface‑level lexical overlap does not guarantee factual correctness or comprehensive coverage of the source literature [3]. 

Concise scientific writing guidelines highlight a trade‑off between brevity and clarity: excessive condensation can obscure essential information, leading to ambiguity and reduced interpretability [9]. This inherent tension suggests that any automated system aiming to enforce conciseness must balance brevity with the preservation of critical content. 

Detection tools for LLM‑generated text attain near‑perfect accuracy on specific corpora (e.g., Science Perspective articles and chemistry introductions), yet their generalisability to broader article types and to future, more sophisticated models (e.g., GPT‑4) is uncertain [5]. The limited evaluation scope raises concerns about the robustness of such detectors in diverse publishing contexts. 

Practical and ethical guidelines for AI‑assisted manuscript drafting acknowledge the absence of industry‑wide standards, which hampers consistent attribution, accountability, and reproducibility across institutions [7]. Without clear policies, the risk of undisclosed AI use, self‑plagiarism, and compromised data integrity persists. 

Finally, versioned repository frameworks that capture epistemic state and provenance improve reproducibility, but they do not address the semantic validation of the stored artefacts; ensuring that persisted evidence remains factually accurate and contextually relevant remains an open challenge [8]. 

Collectively, these findings underscore that while current methodologies advance automation, scalability, and formalisation, substantial gaps remain in factual reliability, generalisability, ethical governance, and the balance between conciseness and clarity.

## References

[1] Oleksandr Karataiev, Igor Shubin, "Formal model of multi-agent architecture of a software system based on knowledge interpretation", RADIOELECTRONIC AND COMPUTER SYSTEMS, 2023. doi:10.32620/reks.2023.4.05
[2] Wojciech Kryściński, Bryan McCann, Caiming Xiong et al., "Evaluating the Factual Consistency of Abstractive Text Summarization", 2020. doi:10.18653/v1/2020.emnlp-main.750
[3] Nurshat Fateh Ali, Md. Mahdi Mohtasim, Shakil Mosharrof et al., "Automated Literature Review Using NLP Techniques and LLM-Based Retrieval-Augmented Generation", 2024. doi:10.1109/iciset62123.2024.10939517
[4] Byron Wallace, Sayantan Saha, Frank Soboczenski et al., "Generating (Factual?) Narrative Summaries of RCTs: Experiments with\n Neural Multi-Document Summarization", arXiv (Cornell University), 2020. doi:10.48550/arxiv.2008.11293
[5] Nader Rifai, "Large Language Models for Scientific Publishing: Please, Do Not Make Them a Foe", Clinical Chemistry, 2024. doi:10.1093/clinchem/hvad219
[6] Yang Zhong, Diane Litman, "A Tale of Evaluating Factual Consistency: Case Study on Long Document Summarization Evaluation", 2025. doi:10.18653/v1/2025.findings-acl.648
[7] Muhammad Nadeem Yousaf, "Practical Considerations and Ethical Implications of Using Artificial Intelligence in Writing Scientific Manuscripts", ACG Case Reports Journal, 2025. doi:10.14309/crj.0000000000001629
[8] Ingolf Lohmann, "QIK-VRT: Operationalisierte epistemische Zustandskontrolle und schichtgebundene Evidenzpersistenz", Open MIND, 2026. doi:10.5281/zenodo.20712301
[9] Scott Hotaling, "Simple rules for concise scientific writing", Limnology and Oceanography Letters, 2020. doi:10.1002/lol2.10165