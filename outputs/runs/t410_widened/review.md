# Literature Review: How do multi-agent retrieval-augmented systems reduce hallucination in automated literature review?

## Methods and Architectures

### Methods and Architectures – Method

Recent work has explored how to adapt large language models (LLMs) to serve as dense retrievers and rerankers within multi‑stage retrieval pipelines. Fine‑tuning the open‑source LLaMA‑2 model as a dense retriever (repLLaMA) and a pointwise reranker (rankLLaMA) yields a repLLaMA‑rankLLaMA pipeline that performs competitively on MS MARCO and BEIR, demonstrating that a single fine‑tuned LLM can replace a collection of smaller, hand‑crafted retrieval components while directly handling long documents without heuristic segmentation [1].

In the domain of factuality verification, a weakly‑supervised, model‑based approach has been proposed that generates training data via rule‑based transformations of source sentences and jointly trains a single model on three tasks: (1) determining factual consistency after transformation, (2) extracting a supporting span in the source, and (3) extracting an inconsistent span in the summary if present. This multi‑task formulation substantially outperforms prior models on factual consistency verification, and the auxiliary span‑extraction tasks aid human verification [2].

For agent‑based simulation of social systems, the MBSSM architecture offers an object‑oriented framework that encodes social mechanisms as individual behaviour components. By expressing mechanisms in UML diagrams, the framework enables systematic comparison and integration of theory families, facilitating empirical testing of social explanations within agent‑based models [3].

In multimodal answer localization, the DLaVA pipeline demonstrates that a training‑free, OCR‑free approach can achieve competitive performance on benchmark datasets. By assigning unique bounding‑box IDs to text regions, DLaVA preserves spatial context without iterative OCR or chain‑of‑thought reasoning, yielding lower computational complexity and improved interpretability and trustworthiness [4].

Finally, the TaxoBench benchmark evaluates deep research agents on both retrieval and hierarchical organization. Results show that even state‑of‑the‑art LLMs retrieve only a fraction of expert‑cited papers and fail to match the depth of expert taxonomies, highlighting the need to calibrate hierarchy metrics before comparing models [5].

## Evaluation and Benchmarks

### Evaluation and Benchmarks – Evaluation

The design of evaluation protocols for large‑language‑model (LLM) systems is increasingly recognized as a critical bottleneck in the field. Recent work has highlighted that the choice of benchmark, the granularity of metrics, and the construction of test data can all profoundly influence reported performance. Below we synthesize the main insights from the literature, grouping them by theme and contrasting methodological choices.

#### 1. Benchmark Construction and Data Diversity 
A recurring theme is the need for datasets that reflect realistic usage scenarios and controlled linguistic properties. The RiDiC pipeline demonstrates how a configurable generator can produce multilingual entity sets with specified popularity distributions, enabling systematic probing of hallucination rates across entity fame levels [6]. Similarly, the SciFactCheck benchmark introduces a modular evaluation framework that spans five scientific domains and three hallucination types (unverifiability, overclaim, attribution) [7]. Both studies underscore that benchmark diversity—spanning domains, languages, and entity characteristics—provides a more nuanced view of model reliability than single‑task or single‑domain tests.

#### 2. Metric Selection and Calibration 
Metrics that capture different aspects of model behavior often yield divergent conclusions. In the TaxoBench study, leaf‑level assignments are evaluated with Adjusted Rand Index (ARI) and V‑Measure, while hierarchy‑level structure is assessed via US‑TED, US‑NTED, and Sem‑Path [5]. The authors argue that hierarchy metrics must be calibrated against expert taxonomies before they can be meaningfully compared across models, as raw Sem‑Path scores can remain near a no‑organization floor even when newer model generations improve ARI. This highlights the importance of aligning evaluation metrics with the specific cognitive or organizational goals of the system.

#### 3. Evaluation of Retrieval and Ranking Pipelines 
Fine‑tuning dense retrievers and rerankers on standard retrieval benchmarks (MS MARCO, BEIR) has become a common practice. The repLLaMA‑rankLLaMA pipeline shows that fine‑tuned LLM retrieval models outperform smaller models and generalize better, while also handling longer documents without heuristic segmentation [1]. Although specific numbers are not reported, the study illustrates that end‑to‑end fine‑tuning can simplify training pipelines and improve retrieval effectiveness.

#### 4. Factual Consistency and Human‑Centric Evaluation 
Assessing factual consistency in abstractive summarization remains challenging. A weakly‑supervised, model‑based approach that jointly trains on consistency detection and span extraction has been shown to outperform prior models on factual consistency verification, and the auxiliary span tasks aid human verification [2]. This dual‑task strategy demonstrates that incorporating human‑interpretable signals (supporting and inconsistent spans) can bridge the gap between automated metrics and expert judgment.

#### 5. Limitations of Current Evaluation Practices 
Several studies point to systemic shortcomings in existing evaluation frameworks. The SciFactCheck benchmark reveals that scientifically fine‑tuned models exhibit degraded factual reliability across all hallucination types, and that human agreement with automated fact‑checking tools is only modest [7]. Moreover, the TaxoBench results show that even state‑of‑the‑art agents retrieve a small fraction of expert‑cited papers and fail to match expert taxonomy depth, indicating that retrieval and organization remain significant bottlenecks [5]. These findings collectively suggest that current benchmarks may not fully capture the complexities of real‑world LLM deployment.

In summary, the literature emphasizes that robust evaluation requires carefully constructed datasets, calibrated metrics, and evaluation protocols that reflect both system‑level objectives and human interpretability. Future work must continue to refine these components to ensure that reported performance translates into reliable, trustworthy AI systems.

## Limitations and Open Problems

### Limitations and Open Problems

Despite recent progress in fine‑tuning large language models (LLMs) for retrieval and summarization, several fundamental limitations persist. First, fine‑tuned dense retrievers such as repLLaMA and rankLLaMA, while outperforming smaller baselines, still exhibit a gap between their performance on benchmark datasets (MS MARCO, BEIR) and real‑world retrieval scenarios, particularly when documents vary widely in length and topicality [1]. The lack of explicit numerical results in the study underscores the need for more comprehensive evaluation protocols that capture diverse retrieval challenges.

Second, factual consistency remains a critical bottleneck for abstractive summarization. Even weakly‑supervised models that jointly predict consistency and extract supporting spans outperform prior approaches, yet they still struggle with nuanced factual errors that require deep world knowledge or external verification [2]. The reliance on rule‑based transformations for training data generation limits the coverage of complex factual scenarios, suggesting that future work should explore more sophisticated data augmentation or multi‑task learning frameworks.

Third, the evaluation of LLM hallucinations in scientific domains reveals a paradox: models fine‑tuned on domain‑specific data exhibit *degraded* factual reliability across all hallucination types (unverifiability, overclaim, attribution) compared to their general‑purpose counterparts [7]. This counterintuitive result highlights an open problem in balancing domain specialization with factual fidelity, and points to the necessity of developing fine‑tuning objectives that explicitly penalize hallucinations.

Fourth, the scarcity of high‑quality, controlled factuality datasets hampers progress. The RiDiC pipeline demonstrates that even frontier models hallucinate when confronted with entities of varying popularity and multilingual contexts [6]. However, the current datasets are limited to a few languages and entity types, leaving open questions about how popularity distribution and linguistic diversity affect hallucination rates across broader LLMs.

Finally, the synthesis of research knowledge by deep research agents remains far from expert performance. TaxoBench shows that even state‑of‑the‑art agents retrieve only about 21 % of expert‑cited papers and fail to achieve the depth of expert taxonomies, revealing that retrieval and hierarchical organization are distinct bottlenecks that current benchmarks and metrics do not fully disentangle [5]. This gap underscores the need for more nuanced evaluation frameworks that separately assess retrieval accuracy, organization quality, and alignment with expert taxonomies.

Addressing these limitations will require coordinated efforts across model architecture, training objectives, dataset construction, and evaluation methodology, with a particular focus on transparent reporting and reproducibility.

## References

[1] Xueguang Ma, Liang Wang, Nan Yang et al., "Fine-Tuning LLaMA for Multi-Stage Text Retrieval", 2024. doi:10.1145/3626772.3657951
[2] Wojciech Kryściński, Bryan McCann, Caiming Xiong et al., "Evaluating the Factual Consistency of Abstractive Text Summarization", 2020. doi:10.18653/v1/2020.emnlp-main.750
[3] Tuong Manh Vu, Charlotte Probst, Alexandra Nielsen et al., "A Software Architecture for Mechanism-Based Social Systems Modelling in Agent-Based Simulation Models", Journal of Artificial Societies and Social Simulation, 2020. doi:10.18564/jasss.4282
[4] Ahmad Mohammadshirazi, Pinaki Prasad Guha Neogi, Ser-Nam Lim et al., "DLaVA: Document Language and Vision Assistant for Answer Localization with Enhanced Interpretability and Trustworthiness", arXiv (Cornell University), 2024. doi:10.48550/arxiv.2412.00151
[5] Ming Zhang, Jiabao Zhuang, Wenqing Jing et al., "Can Deep Research Agents Retrieve and Organize? Evaluating the Synthesis Gap with Expert Taxonomies", arXiv, 2026. doi:10.48550/arxiv.2601.12369
[6] Pavel Braslavski, Dmitrii Iarosh, Nikita Sushko et al., "The Chronicles of RiDiC: Generating Datasets with Controlled Popularity Distribution for Long-form Factuality Evaluation", arXiv, 2026. doi:10.48550/arxiv.2604.00019
[7] Raia Abu Ahmad, Nikolas Rauscher, Ekaterina Borisova et al., "Finetuning with Scientific Data Increases Hallucinations: A Multi-domain Factuality Evaluation of LLMs", arXiv, 2026. doi:10.48550/arxiv.2606.21359