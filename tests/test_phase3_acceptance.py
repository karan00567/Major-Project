"""Phase 3 acceptance tests — the verifier training track (T-301..T-307).

Everything here runs offline against synthetic rows except the tests marked
``network``, so the suite stays fast and works on a plane. The synthetic rows
mirror the real SciFact shape verified on 2026-08-27:

    claim_id repeats across rows, `abstract` is a sentence list, `evidence`
    holds indices into it and is empty exactly when verdict == "NEI".
"""

from __future__ import annotations

import json
import pathlib

import pytest

from researchgpt.verify.evaluate import (
    ESCALATION_THRESHOLD,
    encode_pair,
    escalation_verdict,
    label_permutation,
    score,
)
from researchgpt.verify.labels import ID2LABEL, LABEL2ID, LABELS
from researchgpt.verify.scifact_pairs import build_pairs, class_counts, split_by_claim

REPO = pathlib.Path(__file__).resolve().parents[1]
NOTEBOOK = REPO / "notebook-kaggle-traning" / "01_train_verifier_scifact.ipynb"


def _row(claim_id, verdict, evidence, n_sents=6, abstract_id=None):
    return {
        "claim_id": claim_id,
        "claim": f"claim number {claim_id}",
        "abstract_id": abstract_id if abstract_id is not None else claim_id * 10,
        "title": "t",
        "abstract": [f"sentence {i}" for i in range(n_sents)],
        "verdict": verdict,
        "evidence": evidence,
    }


# --------------------------------------------------------------------------
# T-301 — pairing
# --------------------------------------------------------------------------


def test_t301_support_emits_one_pair_per_evidence_sentence():
    pairs = build_pairs([_row(1, "SUPPORT", [0, 3, 5])])
    assert len(pairs) == 3
    assert [p["sentence_index"] for p in pairs] == [0, 3, 5]
    assert {p["evidence"] for p in pairs} == {"sentence 0", "sentence 3", "sentence 5"}
    assert all(p["label"] == "SUPPORT" for p in pairs)


def test_t301_nei_samples_from_the_abstract():
    """NEI rows carry no evidence, so sentences are sampled — `nei_per_claim` of them."""
    pairs = build_pairs([_row(1, "NEI", [])], nei_per_claim=2)
    assert len(pairs) == 2
    assert all(p["label"] == "NEI" for p in pairs)
    assert all(p["evidence"].startswith("sentence ") for p in pairs)
    assert len({p["sentence_index"] for p in pairs}) == 2, "sampled without replacement"


def test_t301_nei_sampling_is_capped_by_abstract_length():
    pairs = build_pairs([_row(1, "NEI", [], n_sents=1)], nei_per_claim=5)
    assert len(pairs) == 1


def test_t301_is_deterministic_under_a_fixed_seed():
    rows = [_row(i, "NEI", []) for i in range(20)]
    assert build_pairs(rows, seed=7) == build_pairs(rows, seed=7)
    assert build_pairs(rows, seed=7) != build_pairs(rows, seed=8)


def test_t301_out_of_range_evidence_index_is_dropped_not_crashed():
    """Defensive: an index past the end of `abstract` must not raise or emit junk."""
    pairs = build_pairs([_row(1, "SUPPORT", [0, 99])])
    assert len(pairs) == 1
    assert pairs[0]["sentence_index"] == 0


def test_t301_non_nei_row_with_no_usable_evidence_emits_nothing():
    """Better to drop the row than to emit a pair whose label is unsupported by
    any sentence — that would be a silently mislabelled training example."""
    assert build_pairs([_row(1, "SUPPORT", [])]) == []
    assert build_pairs([_row(1, "SUPPORT", [42])]) == []


def test_t301_split_never_leaks_a_claim_across_the_boundary():
    """The regression that matters. One claim spans several rows, so a row-level
    split puts the same claim text on both sides and inflates the dev score."""
    rows = []
    for claim_id in range(40):
        for abstract in range(3):  # same claim, three different abstracts
            rows.append(_row(claim_id, "SUPPORT", [0, 1], abstract_id=claim_id * 10 + abstract))
    pairs = build_pairs(rows)
    train, dev = split_by_claim(pairs, dev_frac=0.25)

    assert train and dev
    assert not ({p["claim_id"] for p in train} & {p["claim_id"] for p in dev})
    assert len(train) + len(dev) == len(pairs)


def test_t301_split_keeps_every_pair_of_a_held_out_claim_together():
    rows = [_row(1, "SUPPORT", [0, 1, 2]), _row(1, "SUPPORT", [3], abstract_id=99)]
    pairs = build_pairs(rows)
    train, dev = split_by_claim(pairs, dev_frac=1.0)
    assert len(dev) == len(pairs) and not train


def test_t301_class_counts_cover_every_label():
    counts = class_counts(build_pairs([_row(1, "SUPPORT", [0])]))
    assert set(counts) == set(LABELS)
    assert counts["CONTRADICT"] == 0, "absent classes report 0, not a missing key"


# --------------------------------------------------------------------------
# Label vocabulary and the head permutation
# --------------------------------------------------------------------------


def test_labels_round_trip():
    assert LABELS == ("SUPPORT", "CONTRADICT", "NEI")
    for i, label in enumerate(LABELS):
        assert LABEL2ID[label] == i and ID2LABEL[i] == label


def test_permutation_maps_the_stock_nli_head_onto_our_order():
    """The stock checkpoint is {0: contradiction, 1: entailment, 2: neutral}.
    Verified live against `cross-encoder/nli-deberta-v3-small` on 2026-08-27."""
    stock = {0: "contradiction", 1: "entailment", 2: "neutral"}
    assert label_permutation(stock) == [1, 0, 2]


def test_permutation_is_identity_for_a_checkpoint_already_in_our_vocabulary():
    assert label_permutation({0: "SUPPORT", 1: "CONTRADICT", 2: "NEI"}) == [0, 1, 2]


def test_permutation_refuses_to_guess_on_an_unknown_head():
    """A wrong permutation is invisible in the output and poisons every number
    downstream, so an unrecognised head must raise rather than default."""
    with pytest.raises(ValueError, match="Cannot map checkpoint label"):
        label_permutation({0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"})


def test_permutation_rejects_an_incomplete_head():
    with pytest.raises(ValueError, match="missing"):
        label_permutation({0: "entailment", 1: "neutral"})


def test_encode_pair_puts_evidence_first():
    """Premise = evidence, hypothesis = claim. Reversing them silently trains a
    different task, so the order is pinned by a test rather than a comment."""
    premise, hypothesis = encode_pair({"claim": "C", "evidence": "E"})
    assert (premise, hypothesis) == ("E", "C")


# --------------------------------------------------------------------------
# T-305 scoring
# --------------------------------------------------------------------------


def test_score_is_perfect_on_perfect_predictions():
    y = [0, 1, 2, 0, 1, 2]
    result = score(y, y)
    assert result["accuracy"] == 1.0
    assert result["macro_f1"] == 1.0
    assert all(m["f1"] == 1.0 for m in result["per_class"].values())


def test_score_reports_zero_not_nan_for_a_class_never_predicted():
    """A model that never predicts CONTRADICT must score 0 there, not NaN —
    NaN would silently poison the macro average the T-307 gate reads."""
    y_true = [0, 1, 2]
    y_pred = [0, 0, 2]
    result = score(y_true, y_pred)
    assert result["per_class"]["CONTRADICT"]["f1"] == 0.0
    assert result["macro_f1"] == result["macro_f1"]  # not NaN


def test_score_confusion_matrix_orientation():
    """Rows are true, columns predicted. Getting this backwards inverts every
    precision/recall pair, which reads as plausible but is wrong."""
    result = score([0, 0], [2, 2])
    assert result["confusion"][0][2] == 2
    assert result["confusion"][2][0] == 0
    assert result["per_class"]["SUPPORT"]["recall"] == 0.0


def test_score_support_counts_are_true_class_totals():
    result = score([0, 0, 0, 1], [0, 1, 2, 1])
    assert result["per_class"]["SUPPORT"]["support"] == 3
    assert result["per_class"]["CONTRADICT"]["support"] == 1


def test_score_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        score([0, 1], [0])


# --------------------------------------------------------------------------
# T-307 escalation gate
# --------------------------------------------------------------------------


def test_t307_gate_threshold_matches_the_recorded_decision():
    """decisions.txt D-09 fixed this at 0.75 BEFORE the first training run.
    If someone edits the constant after seeing a result, this fails."""
    assert ESCALATION_THRESHOLD == 0.75


def test_t307_gate_escalates_below_threshold_and_passes_at_it():
    assert "ESCALATE" in escalation_verdict(0.74)
    assert "PASS" in escalation_verdict(0.75)
    assert "PASS" in escalation_verdict(0.90)


# --------------------------------------------------------------------------
# T-302 — the notebook must not drift from the module
# --------------------------------------------------------------------------


def test_notebook_exists_and_is_valid_json():
    assert NOTEBOOK.exists(), f"{NOTEBOOK} is missing"
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    assert [c for c in nb["cells"] if c["cell_type"] == "code"], "no code cells"


def test_notebook_requests_a_gpu_and_internet():
    """Both are Kaggle *settings*, not code. If the metadata is wrong the run
    silently falls back to CPU and takes hours, or fails to reach the Hub."""
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert nb["metadata"].get("accelerator") == "GPU"
    assert nb["metadata"]["kaggle"]["isInternetEnabled"] is True


def _notebook_pairing_namespace():
    """Exec just the notebook's data cell, with its config, and return the namespace."""
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    config = next(s for s in sources if "BASE_MODEL =" in s)
    pairing = next(s for s in sources if "def build_pairs" in s)
    # Drop the lines that hit the network; only the pure pairing logic is needed.
    pairing = pairing.split("raw_train, raw_val = load_split")[0]

    namespace: dict = {}
    exec(compile(config, "<nb-config>", "exec"), namespace)
    exec(compile(pairing, "<nb-pairing>", "exec"), namespace)
    return namespace


def test_notebook_pairing_matches_the_module_exactly():
    """The notebook carries a mirror of `scifact_pairs.build_pairs` because
    Kaggle cannot import this repo. This test is what stops the two copies from
    drifting — which would train on different data than the local JSONL claims.
    """
    namespace = _notebook_pairing_namespace()
    rows = (
        [_row(i, "SUPPORT", [0, 2]) for i in range(10)]
        + [_row(100 + i, "CONTRADICT", [1]) for i in range(10)]
        + [_row(200 + i, "NEI", []) for i in range(10)]
    )
    from researchgpt.verify.scifact_pairs import SEED

    mine = build_pairs(rows, nei_per_claim=2, seed=SEED)
    theirs = namespace["build_pairs"](rows, nei_per_claim=2, seed=SEED)
    assert mine == theirs, "notebook and module pairing have drifted apart"


def test_notebook_split_matches_the_module_exactly():
    namespace = _notebook_pairing_namespace()
    from researchgpt.verify.scifact_pairs import SEED

    rows = [_row(i, "SUPPORT", [0, 1]) for i in range(60)]
    pairs = build_pairs(rows, seed=SEED)
    mine = split_by_claim(pairs, dev_frac=0.15, seed=SEED)
    theirs = namespace["split_by_claim"](pairs, dev_frac=0.15, seed=SEED)
    assert mine == theirs, "notebook and module claim-grouped split have drifted apart"


def test_notebook_constants_match_the_module():
    namespace = _notebook_pairing_namespace()
    from researchgpt.verify.scifact_pairs import SEED

    assert namespace["SEED"] == SEED, "notebook would train on a different pairing"
    assert tuple(namespace["LABELS"]) == LABELS
    assert namespace["ESCALATION_THRESHOLD"] == ESCALATION_THRESHOLD


# --------------------------------------------------------------------------
# Live checks — skipped without a network
# --------------------------------------------------------------------------


@pytest.mark.network
def test_t301_live_scifact_has_the_expected_shape():
    """Guards the one assumption the whole track rests on: that the parquet
    branch still carries the rows the pairing rule was written against."""
    pytest.importorskip("pyarrow")
    from researchgpt.verify.scifact_pairs import EXPECTED_ROWS, load_split

    rows = load_split("validation")
    assert len(rows) == EXPECTED_ROWS["validation"]
    assert {"claim", "abstract", "verdict", "evidence", "claim_id"} <= set(rows[0])
    assert all(isinstance(r["abstract"], list) for r in rows[:20])
    assert all(r["evidence"] == [] for r in rows if r["verdict"] == "NEI")
    assert all(r["evidence"] for r in rows if r["verdict"] != "NEI")
