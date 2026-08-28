"""Phase 3C acceptance tests — the reranker fine-tune (T-330..T-335).

Offline against synthetic rows. The things worth testing here are not the
happy paths but the two failure modes that would silently invalidate the
result: leaked surveys, and negatives that are not actually hard.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from researchgpt.rerank.evaluate import ndcg_at_k, ranking_metrics
from researchgpt.rerank.triples import (
    MIN_ABSTRACT_CHARS,
    NEGATIVES_PER_POSITIVE,
    build_corpus,
    mine_hard_negatives,
    split_by_survey,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
NOTEBOOK = REPO / "notebook-kaggle-traning" / "02_train_reranker_scireviewgen.ipynb"


def make_reference(title, chapter, blocks):
    return " ".join(
        f"{title} <s> {chapter} <s> {abstract} <s> {bib} </s>" for bib, abstract in blocks
    )


def row(title, chapter, n_bibs=4, topic="retrieval augmented generation"):
    blocks = [
        (f"BIB{i:03d}", f"An abstract about {topic} number {i}. " * 4)
        for i in range(1, n_bibs + 1)
    ]
    return {"reference": make_reference(title, chapter, blocks), "target": ""}


# --------------------------------------------------------------------------
# T-330 — corpus construction
# --------------------------------------------------------------------------


def test_t330_query_is_survey_title_plus_chapter():
    """TRAINING_SPEC 2.2: the query mirrors what the live Retriever sees - a
    topic, not a natural-language question."""
    _, positives = build_corpus([row("Survey X", "Chapter Y")])
    assert list(positives) == ["Survey X Chapter Y"]


def test_t330_positives_are_the_cited_abstracts():
    documents, positives = build_corpus([row("S", "C", n_bibs=3)])
    assert len(documents) == 3
    assert len(positives["S C"]) == 3


def test_t330_deduplicates_identical_abstracts_across_chapters():
    """The same paper is cited by many chapters. Left duplicated in the pool, a
    true positive could reappear as a 'negative' under a different id."""
    shared = [("BIB001", "A shared abstract about retrieval. " * 5)]
    rows = [
        {"reference": make_reference("S", "Chapter 1", shared), "target": ""},
        {"reference": make_reference("S", "Chapter 2", shared), "target": ""},
    ]
    documents, positives = build_corpus(rows)
    assert len(documents) == 1, "identical abstracts must collapse to one document"
    assert len(positives) == 2, "but both chapters still claim it as a positive"


def test_t330_drops_abstracts_below_the_length_floor():
    """A stub abstract would teach the model that length predicts irrelevance."""
    blocks = [("BIB001", "short"), ("BIB002", "A proper abstract. " * 10)]
    documents, positives = build_corpus(
        [{"reference": make_reference("S", "C", blocks), "target": ""}]
    )
    assert len(documents) == 1
    assert all(len(d["text"]) >= MIN_ABSTRACT_CHARS for d in documents)


def test_t330_split_by_survey_groups_chapters_together():
    rows = [row("Survey A", f"Chapter {i}") for i in range(5)] + [row("Survey B", "Only")]
    groups = split_by_survey(rows)
    assert set(groups) == {"Survey A", "Survey B"}
    assert len(groups["Survey A"]) == 5


# --------------------------------------------------------------------------
# T-331 — hard negatives, the part that decides whether this task works
# --------------------------------------------------------------------------


def _varied_rows(n_queries=12):
    """Every abstract must be textually unique.

    Learned from a first version of these tests: `build_corpus` deduplicates by
    abstract text (correctly - the same paper is cited by many chapters), so a
    fixture that repeats text silently shrinks the pool below what the 1:4 ratio
    needs, and the ratio assertions fail for a reason that has nothing to do
    with the code under test.
    """
    topics = ["neural retrieval", "graph databases", "protein folding", "wind turbines"]
    return [
        {
            "reference": make_reference(
                f"Survey {i}", f"Chapter {i}",
                [(f"BIB{j:03d}",
                  f"Abstract q{i} b{j} on {topics[i % len(topics)]}. " * 5)
                 for j in range(1, 4)],
            ),
            "target": "",
        }
        for i in range(n_queries)
    ]


def test_t331_ratio_is_one_positive_to_four_negatives():
    documents, positives = build_corpus(_varied_rows())
    pairs, _ = mine_hard_negatives(documents, positives)
    pos = sum(1 for p in pairs if p["label"] == 1)
    neg = sum(1 for p in pairs if p["label"] == 0)
    assert neg == pos * NEGATIVES_PER_POSITIVE


def test_t331_never_samples_a_true_positive_as_a_negative():
    """The failure that would quietly teach the model the opposite of its job."""
    documents, positives = build_corpus(_varied_rows())
    pairs, _ = mine_hard_negatives(documents, positives)
    negatives_by_query: dict[str, set[str]] = {}
    for pair in pairs:
        if pair["label"] == 0:
            negatives_by_query.setdefault(pair["query"], set()).add(pair["doc_id"])
    for query, negs in negatives_by_query.items():
        assert not (negs & positives[query]), f"positive leaked into negatives for {query}"


def test_t331_reports_random_fallback_share():
    """If BM25 cannot supply confusable documents the negatives are not hard, and
    T-334 showing no gain would be explained here. It must be measurable."""
    documents, positives = build_corpus(_varied_rows())
    _, diag = mine_hard_negatives(documents, positives)
    assert "random_fallback_share_of_negatives" in diag
    assert 0.0 <= diag["random_fallback_share_of_negatives"] <= 1.0
    assert diag["queries"] == len(positives)


def test_t331_degrades_honestly_when_the_corpus_cannot_supply_enough():
    """A corpus whose every document is a positive for the only query has no
    negatives to give. It must emit fewer rather than invent them, and it must
    SAY so - a silent shortfall is how "the negatives were not hard" hides."""
    documents, positives = build_corpus([row("S", "C", n_bibs=2)])
    pairs, diag = mine_hard_negatives(documents, positives)
    assert sum(1 for p in pairs if p["label"] == 1) == 2
    assert sum(1 for p in pairs if p["label"] == 0) == 0
    assert diag["queries_short_of_hard_negatives"] == 1


def test_t331_tops_up_from_the_wider_pool_when_bm25_is_short():
    """With other documents available, a shortfall is padded at random and the
    padding is counted - that count is what T-334 diagnoses a null result with."""
    documents, positives = build_corpus(_varied_rows(n_queries=8))
    # One query, many documents: BM25 will not return 50 scoring candidates.
    single = {next(iter(positives)): positives[next(iter(positives))]}
    pairs, diag = mine_hard_negatives(documents, single)
    pos = sum(1 for p in pairs if p["label"] == 1)
    neg = sum(1 for p in pairs if p["label"] == 0)
    assert neg == pos * NEGATIVES_PER_POSITIVE
    assert diag["random_fallback_negatives"] >= 0


def test_t331_is_deterministic():
    documents, positives = build_corpus(_varied_rows())
    a, _ = mine_hard_negatives(documents, positives, seed=5)
    b, _ = mine_hard_negatives(documents, positives, seed=5)
    assert a == b


# --------------------------------------------------------------------------
# T-334 — ranking metrics
# --------------------------------------------------------------------------


def test_ndcg_is_one_for_a_perfect_ranking():
    assert ndcg_at_k([1, 1, 1, 0, 0], k=10) == pytest.approx(1.0)


def test_ndcg_penalises_a_reversed_ranking():
    assert ndcg_at_k([0, 0, 1, 1], k=10) < ndcg_at_k([1, 1, 0, 0], k=10)


def test_ndcg_is_zero_when_there_are_no_positives():
    assert ndcg_at_k([0, 0, 0], k=10) == 0.0


def test_ranking_metrics_skip_queries_with_no_positives():
    """A query with no gold paper has undefined recall; averaging a 0 into the
    mean would understate the model rather than exclude the query."""
    result = ranking_metrics([[1, 0, 0], [0, 0, 0]])
    assert result["queries"] == 1


def test_ranking_metrics_recall_at_20_is_relative_to_available_positives():
    labels = [1, 1] + [0] * 30
    assert ranking_metrics([labels])["Recall@20"] == pytest.approx(1.0)


def test_ranking_metrics_precision_at_12_uses_a_fixed_denominator():
    labels = [1] * 6 + [0] * 20
    assert ranking_metrics([labels])["Precision@12"] == pytest.approx(0.5)


# --------------------------------------------------------------------------
# T-332 — the notebook
# --------------------------------------------------------------------------


def test_notebook_exists_and_requests_gpu_and_internet():
    assert NOTEBOOK.exists(), f"{NOTEBOOK} is missing"
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert nb["metadata"]["accelerator"] == "GPU"
    assert nb["metadata"]["kaggle"]["isInternetEnabled"] is True
    assert [c for c in nb["cells"] if c["cell_type"] == "code"]


def _notebook_config() -> dict:
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    config = next(s for s in sources if "BASE_MODEL" in s)
    namespace: dict = {}
    exec(compile(config, "<nb2-config>", "exec"), namespace)
    return namespace


def test_notebook_config_matches_training_spec():
    """TRAINING_SPEC 2.3 fixes these. Drift here changes what was trained
    without changing anything that documents it."""
    cfg = _notebook_config()
    assert cfg["BASE_MODEL"] == "cross-encoder/ms-marco-MiniLM-L-6-v2"
    assert cfg["EPOCHS"] == 2
    assert cfg["LEARNING_RATE"] == 2e-5
    assert cfg["BATCH_SIZE"] == 32
    assert cfg["MAX_LENGTH"] == 512


def test_notebook_seed_matches_the_triples_builder():
    """The triples were built with this seed; a mismatch trains on a different
    set than the local artefacts claim."""
    from researchgpt.rerank.triples import SEED

    assert _notebook_config()["SEED"] == SEED


def test_notebook_asserts_no_survey_leaks_across_the_split():
    """The leakage guard must be IN the notebook, not merely in the README."""
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    source = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    assert "survey leaked across the split" in source
    assert "assert" in source


def test_notebook_tells_the_user_the_gate_is_out_of_domain():
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    text = "\n".join("".join(c["source"]) for c in nb["cells"])
    assert "IN-DOMAIN" in text
    assert "T-335" in text


# --------------------------------------------------------------------------
# Artefacts, when the pipeline has been run
# --------------------------------------------------------------------------


def test_t330_artefact_records_hard_negative_quality():
    path = REPO / "eval" / "rerank_triples_t330.json"
    if not path.exists():
        pytest.skip("T-330 has not been run in this checkout")
    stats = json.loads(path.read_text(encoding="utf-8"))
    assert stats["negatives"] == stats["positives"] * NEGATIVES_PER_POSITIVE
    assert stats["random_fallback_share_of_negatives"] < 0.25, (
        "over a quarter of negatives are random, not hard - T-334 would show no "
        "gain and T-331 is the reason"
    )
    assert stats["distinct_surveys"] > 100, "too few surveys; sampling is not working"


# --------------------------------------------------------------------------
# T-335 relevance control — added after it caught a nearly-shipped broken model
# --------------------------------------------------------------------------


class _FakeScorer:
    """Scores by a rule, so the control can be tested without a real model."""

    def __init__(self, rule):
        self.rule = rule

    def score(self, query, texts):
        return [self.rule(query, t) for t in texts]


def _one_query_pool():
    return {"retrieval augmented generation": [
        {"text": f"a relevant paper about retrieval number {i}", "label": 1}
        for i in range(6)
    ]}


def test_relevance_control_passes_a_model_that_knows_irrelevance():
    from researchgpt.rerank.evaluate import OFF_TOPIC_CONTROLS, relevance_control

    controls = set(OFF_TOPIC_CONTROLS)
    healthy = _FakeScorer(lambda q, t: -10.0 if t in controls else 5.0)
    result = relevance_control(healthy, _one_query_pool())
    assert result["violations"] == 0
    assert result["pass"] is True
    assert result["mean_margin"] > 0


def test_relevance_control_catches_a_model_that_scores_everything_high():
    """The real failure of 2026-08-27: a reranker that lost its relevance prior
    and scored wind turbines, soil nitrogen and opera libretti at +7..+9.7 for
    retrieval queries. nDCG and Recall could not see it, because the eval pool
    is already topically filtered."""
    from researchgpt.rerank.evaluate import relevance_control

    broken = _FakeScorer(lambda q, t: 8.0)
    result = relevance_control(broken, _one_query_pool())
    assert result["violations"] == result["queries"]
    assert result["violation_rate"] == 1.0
    assert result["pass"] is False
    assert result["worst_examples"]


def test_relevance_control_tolerates_a_single_noisy_query():
    """One violation is noise; a quarter of queries is a broken model. The
    threshold has to distinguish them or it will block good models too."""
    from researchgpt.rerank.evaluate import OFF_TOPIC_CONTROLS, relevance_control

    controls = set(OFF_TOPIC_CONTROLS)
    pool = {f"query {i}": [{"text": f"doc {j}", "label": 1} for j in range(5)]
            for i in range(8)}
    mostly_ok = _FakeScorer(
        lambda q, t: (9.0 if q == "query 0" else -10.0) if t in controls else 5.0
    )
    result = relevance_control(mostly_ok, pool)
    assert result["violations"] == 1
    assert result["pass"] is True


def test_off_topic_controls_are_long_enough_to_be_in_distribution():
    """A short control could be scored low for its length rather than its
    irrelevance, which would make the check meaningless."""
    from researchgpt.rerank.evaluate import OFF_TOPIC_CONTROLS

    assert len(OFF_TOPIC_CONTROLS) >= 3
    assert all(len(t) > 300 for t in OFF_TOPIC_CONTROLS)


def test_reranker_falls_back_when_a_configured_model_is_missing():
    """The tuned weights live under gitignored data/, so a fresh clone has a
    config naming a path that does not exist. That must warn, not crash."""
    from researchgpt.tools.reranker import STOCK_MODEL, Reranker

    r = Reranker(model_name="data/models/definitely-not-here")
    assert r._model_name == STOCK_MODEL


# --------------------------------------------------------------------------
# T-335 promotion conditions — enforced, not merely documented
# --------------------------------------------------------------------------


def test_stock_reranker_scores_are_calibrated():
    from researchgpt.tools.reranker import STOCK_MODEL, Reranker

    assert Reranker(model_name=STOCK_MODEL).scores_are_calibrated is True


def test_filter_by_score_works_on_a_calibrated_model():
    from researchgpt.core.models import Chunk
    from researchgpt.tools.reranker import STOCK_MODEL, Reranker

    r = Reranker(model_name=STOCK_MODEL)
    c = Chunk(chunk_id="a", paper_id="a", text="x", start_char=0, end_char=1)
    assert r.filter_by_score([(c, 0.9), (c, 0.1)], 0.5) == [(c, 0.9)]


def test_condition_1_score_thresholding_is_blocked_on_a_tuned_model():
    """T-335 condition 1. The tuned reranker rates unrelated documents
    positively, so a score cutoff would silently admit them. A future author
    reaching for one must hit a loud error, not a subtle behaviour change."""
    import pathlib

    import pytest as _pytest

    from researchgpt.tools.reranker import Reranker, UncalibratedScoreError

    tuned = pathlib.Path("data/models/reranker-onnx")
    if not tuned.exists():
        _pytest.skip("tuned reranker not built in this checkout")
    r = Reranker(model_name=str(tuned))
    assert r.scores_are_calibrated is False
    with _pytest.raises(UncalibratedScoreError, match="ordering-only"):
        r.filter_by_score([], 0.5)


def test_nothing_in_the_pipeline_thresholds_on_a_reranker_score():
    """T-335 condition 1, checked against the source rather than assumed.
    RRF fuses by RANK; if a score comparison ever appears next to a rerank
    call, the promotion's premise has quietly expired."""
    import pathlib

    src = pathlib.Path("src/researchgpt")
    offenders = []
    for path in src.rglob("*.py"):
        if path.name in {"evaluate.py", "reranker.py", "retrieval_eval.py"}:
            continue  # eval harnesses and the guard itself legitimately see scores
        text = path.read_text(encoding="utf-8")
        if ".rerank(" in text and any(
            op in text for op in ("min_score", "score >", "score >=", "score <")
        ):
            offenders.append(str(path))
    assert not offenders, (
        f"{offenders} appears to threshold on a reranker score. The adopted model "
        f"is ordering-only (T-335); use top_k or switch to the stock model."
    )


def test_config_names_the_stock_reranker_after_the_t335_revert():
    """T-335 adopted the tuned reranker, then REVERTED it on M1 evidence.

    The adoption rested on "the live pool is 98.2% on-topic", measured on
    T-212's cached pool of 15 hand-written, tightly-scoped queries. The Planner
    generates 20+ broader queries, and on the first real run the tuned model
    ranked an IoT-monitoring paper above the single most relevant paper in the
    pool. The condition did not generalise; the relevance control was right.

    The reason travels with the config so the next reader does not re-adopt it
    from the in-domain numbers alone.
    """
    import pathlib

    cfg = pathlib.Path("configs/default.yaml").read_text(encoding="utf-8")
    assert "reranker: cross-encoder/ms-marco-MiniLM-L-6-v2" in cfg
    assert "T-335 REVERTED" in cfg
    assert "mixed negatives" in cfg.lower() or "MIXED negatives" in cfg


# --------------------------------------------------------------------------
# T-332R — the mixed-negative retrain notebook (03)
#
# Written after T-335 was reverted on M1 evidence. The first fine-tune won every
# ranking metric and was rejected anyway, because 100% BM25 hard negatives left
# it unable to recognise irrelevance. Notebook 03 changes exactly one variable:
# the composition of the negatives. These tests hold everything else still, so a
# later reader can trust that the comparison isolates that one change.
# --------------------------------------------------------------------------

NOTEBOOK_MIXED = REPO / "notebook-kaggle-traning" / "03_train_reranker_mixed_negatives.ipynb"


def _config_of(notebook: pathlib.Path) -> dict:
    nb = json.loads(notebook.read_text(encoding="utf-8"))
    sources = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    config = next(s for s in sources if "BASE_MODEL" in s)
    namespace: dict = {}
    exec(compile(config, "<nb-config>", "exec"), namespace)
    return namespace


def _code_of(notebook: pathlib.Path) -> str:
    nb = json.loads(notebook.read_text(encoding="utf-8"))
    return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")


def test_mixed_notebook_exists_and_requests_gpu_and_internet():
    assert NOTEBOOK_MIXED.exists(), f"{NOTEBOOK_MIXED} is missing"
    nb = json.loads(NOTEBOOK_MIXED.read_text(encoding="utf-8"))
    assert nb["metadata"]["accelerator"] == "GPU"
    assert nb["metadata"]["kaggle"]["isInternetEnabled"] is True
    assert [c for c in nb["cells"] if c["cell_type"] == "code"]


def test_mixed_notebook_changes_only_the_negatives():
    """Every training hyper-parameter must equal notebook 02's.

    If any of these drift, the run stops being an ablation of the negatives and
    becomes an uncontrolled second experiment - and the in-domain numbers of the
    two runs can no longer be compared.
    """
    old, new = _config_of(NOTEBOOK), _config_of(NOTEBOOK_MIXED)
    for key in ("BASE_MODEL", "SEED", "EPOCHS", "LEARNING_RATE", "BATCH_SIZE",
                "MAX_LENGTH", "WARMUP_RATIO", "WEIGHT_DECAY", "DEV_FRAC"):
        assert new[key] == old[key], (
            f"{key} differs from notebook 02 ({new[key]} vs {old[key]}). The "
            "retrain must isolate the negatives, not confound them."
        )


def test_mixed_notebook_uses_three_hard_to_one_random():
    """The fix T-335 specified: ~3 hard : 1 random, not a switch to random."""
    cfg = _config_of(NOTEBOOK_MIXED)
    assert cfg["HARD_PER_POSITIVE"] == 3
    assert cfg["RANDOM_PER_POSITIVE"] == 1
    total = cfg["HARD_PER_POSITIVE"] + cfg["RANDOM_PER_POSITIVE"]
    assert total == NEGATIVES_PER_POSITIVE, (
        f"{total} negatives per positive; the uploaded triples carry "
        f"{NEGATIVES_PER_POSITIVE}, and changing the ratio as well as the "
        "composition would confound the comparison."
    )
    # Hard negatives are the only signal a cross-encoder adds over BM25, so they
    # must stay in the majority. T-331's warning is right about necessity.
    assert cfg["HARD_PER_POSITIVE"] > cfg["RANDOM_PER_POSITIVE"]


def test_mixed_notebook_seed_matches_the_triples_builder():
    from researchgpt.rerank.triples import SEED

    cfg = _config_of(NOTEBOOK_MIXED)
    assert cfg["SEED"] == SEED
    assert cfg["MIX_SEED"] != SEED, (
        "the mixing seed must be distinct, so the survey split stays identical "
        "to notebook 02's and the two runs remain comparable"
    )


def test_mixed_notebook_needs_no_new_upload():
    """It reads the SAME train_triples.jsonl and does the mixing in-notebook.

    Every document in the corpus appears in that file as a positive for some
    chapter, so the random negatives can be drawn from it without re-uploading
    99 MB.
    """
    assert _config_of(NOTEBOOK_MIXED)["TRIPLES_GLOB"].endswith("train_triples.jsonl")


def test_mixed_notebook_asserts_no_survey_leaks_across_the_split():
    source = _code_of(NOTEBOOK_MIXED)
    assert "survey leaked across the split" in source
    assert "assert" in source


def test_mixed_notebook_asserts_a_random_negative_is_never_a_positive():
    """The one way in-notebook negative mixing can silently corrupt the data."""
    source = _code_of(NOTEBOOK_MIXED)
    assert "a random negative is a true positive for its own query" in source


def test_mixed_notebook_runs_the_relevance_control():
    """The diagnostic that caught the previous model - now BEFORE the download.

    Same four probe texts as the local T-335 gate, or the notebook's number and
    the gate's number would not mean the same thing.
    """
    import ast

    from researchgpt.rerank.evaluate import OFF_TOPIC_CONTROLS

    source = _code_of(NOTEBOOK_MIXED)
    assert "relevance_control" in source
    assert "OFF_TOPIC_CONTROLS" in source

    # Evaluate the notebook's own literal rather than substring-matching it:
    # the probes are written as concatenated literals times three, so the source
    # text and the resulting string are not the same thing.
    node = next(
        n for n in ast.parse(source).body
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", None) == "OFF_TOPIC_CONTROLS" for t in n.targets)
    )
    namespace: dict = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<controls>", "exec"), namespace)

    assert namespace["OFF_TOPIC_CONTROLS"] == list(OFF_TOPIC_CONTROLS), (
        "a probe text differs from researchgpt.rerank.evaluate; the notebook's "
        "control and the local gate's control must be identical, or the two "
        "violation rates do not mean the same thing"
    )


def test_mixed_notebook_gate_thresholds_are_fixed_before_the_run():
    """decisions.txt D-09's discipline: fix the number before seeing it.

    Both live in the config cell, which executes before any measurement.
    """
    cfg = _config_of(NOTEBOOK_MIXED)
    assert 0 < cfg["MAX_CONTROL_VIOLATION_RATE"] <= 0.25, (
        "the previous model violated on ~73% of live queries; a threshold above "
        "0.25 would have passed it"
    )
    assert cfg["MIN_NDCG_GAIN"] > 0, (
        "restoring calibration at the cost of the ranking gain is not progress"
    )


def test_mixed_notebook_tells_the_user_the_gate_is_out_of_domain():
    """Its own gate is a pre-filter. T-335 still decides, locally, after int8."""
    nb = json.loads(NOTEBOOK_MIXED.read_text(encoding="utf-8"))
    text = "\n".join("".join(c["source"]) for c in nb["cells"])
    assert "IN-DOMAIN" in text
    assert "T-335" in text
    assert "PRE-FILTER" in text.upper()
