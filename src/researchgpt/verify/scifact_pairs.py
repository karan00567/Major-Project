"""T-301 — build ``(claim, evidence_sentence) -> SUPPORT | CONTRADICT | NEI`` pairs.

Source: ``allenai/scifact_entailment`` (919 train / 340 validation rows).

⚠️ **Two loading facts, both found the hard way.**

1. TASKLIST T-301 says to use ``scifact_entailment`` because plain
   ``allenai/scifact`` is script-based and returns HTTP 501. **That is only half
   right — verified 2026-08-27: ``scifact_entailment`` is *also* script-based**,
   and ``datasets>=4`` refuses it outright with
   ``RuntimeError: Dataset scripts are no longer supported``. The 2026-08-25
   pre-check passed because it probed the datasets-server API, not
   ``load_dataset``.
2. The fix is the Hub's **auto-converted parquet branch**,
   ``refs/convert/parquet``, which carries the identical rows with no script.
   That is what :func:`load_split` reads. It needs no token for this dataset and
   works the same on Kaggle.

**Row shape** (verified 2026-08-27, not copied from the card)::

    claim_id     int         # repeats: one claim pairs with up to 5 abstracts
    claim        str
    abstract_id  int
    title        str
    abstract     list[str]   # the abstract already split into sentences
    verdict      str         # SUPPORT | CONTRADICT | NEI
    evidence     list[int]   # sentence indices into `abstract`; [] iff NEI

Checked over all 1,259 rows: zero out-of-range evidence indices, zero NEI rows
carrying evidence, abstracts run 3–25 sentences.

**Pairing rule** (TASKLIST T-301):

* ``SUPPORT`` / ``CONTRADICT`` — pair the claim with *each* sentence named in
  ``evidence``. A 3-sentence evidence set becomes 3 training pairs.
* ``NEI`` — ``evidence`` is empty, so sample ``nei_per_claim`` sentences from
  that row's abstract. The abstract is a genuine retrieved-but-non-supporting
  abstract for that claim, so its sentences really are "not enough info".

Deliberately **not** done: mining extra NEI pairs from the *non*-evidence
sentences of SUPPORT/CONTRADICT abstracts. Those sentences sit in an abstract
that does support the claim, so a near-paraphrase of the evidence would be
labelled NEI and teach the model the opposite of its job. The cheap volume is
not worth the label noise.

⚠️ **The internal split groups by ``claim_id``.** One claim appears in up to 5
rows, so a row-level split puts the same claim on both sides and inflates the
dev score — the identical failure mode TASKLIST flags for T-330. The reported
held-out set (T-305) is the untouched ``validation`` split; ``dev`` exists only
for tuning.

Run::

    python -m researchgpt.verify.scifact_pairs
    python -m researchgpt.verify.scifact_pairs --nei-per-claim 3 --out data/scifact
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
from collections import Counter
from typing import Any

from researchgpt.verify.labels import LABELS

#: The dataset repo and the parquet branch the loader actually reads.
_REPO = "allenai/scifact_entailment"
_REVISION = "refs/convert/parquet"
_PARQUET = "default/{split}/0000.parquet"

#: Row counts published on the dataset card. :func:`load_split` checks against
#: these and warns on a mismatch — a silently re-converted parquet branch would
#: otherwise change the training set without changing any code.
EXPECTED_ROWS: dict[str, int] = {"train": 919, "validation": 340}

#: One seed for every sampling decision in this module, so two machines building
#: the pairs independently (your laptop and the Kaggle notebook) get byte-identical
#: JSONL. Changing it changes the training set.
SEED = 20260827

DEFAULT_OUT = pathlib.Path("data/scifact")


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_split(split: str) -> list[dict[str, Any]]:
    """Read one SciFact split from the Hub's parquet conversion.

    Imports are function-local: ``huggingface_hub`` and ``pyarrow`` arrive with
    the ``scireviewgen`` extra, and importing this module must not require them
    (``labels.py`` consumers and the acceptance tests do not need a network).
    """
    import pyarrow.parquet as pq  # noqa: PLC0415
    from huggingface_hub import hf_hub_download  # noqa: PLC0415

    path = hf_hub_download(
        _REPO,
        _PARQUET.format(split=split),
        repo_type="dataset",
        revision=_REVISION,
    )
    rows: list[dict[str, Any]] = pq.read_table(path).to_pylist()

    expected = EXPECTED_ROWS.get(split)
    if expected is not None and len(rows) != expected:
        print(
            f"  WARNING: {split}: got {len(rows)} rows, expected {expected}. The parquet "
            f"conversion may have been rebuilt; re-check the pairing before training."
        )
    return rows


# --------------------------------------------------------------------------
# Pairing
# --------------------------------------------------------------------------


def build_pairs(
    rows: list[dict[str, Any]],
    *,
    nei_per_claim: int = 2,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    """Apply the T-301 pairing rule. Deterministic given ``seed``.

    Rows are processed in file order and the RNG is seeded once, so the output
    is a pure function of ``(rows, nei_per_claim, seed)``.
    """
    rng = random.Random(seed)
    pairs: list[dict[str, Any]] = []

    for row in rows:
        verdict = row["verdict"]
        sentences: list[str] = list(row["abstract"])
        if not sentences:
            continue

        if verdict == "NEI":
            # No annotated evidence: sample sentences from this abstract.
            k = min(nei_per_claim, len(sentences))
            indices = sorted(rng.sample(range(len(sentences)), k))
        else:
            # Every annotated evidence sentence becomes its own pair.
            indices = [i for i in row["evidence"] if 0 <= i < len(sentences)]
            if not indices:
                # Defensive: a non-NEI row with no usable evidence would be an
                # unlabelled pair. Verified to occur 0 times, but silently
                # emitting a mislabelled pair is the worse failure.
                continue

        for i in indices:
            pairs.append(
                {
                    "claim": row["claim"],
                    "evidence": sentences[i],
                    "label": verdict,
                    "claim_id": row["claim_id"],
                    "abstract_id": row["abstract_id"],
                    "sentence_index": i,
                }
            )

    return pairs


def split_by_claim(
    pairs: list[dict[str, Any]],
    *,
    dev_frac: float = 0.15,
    seed: int = SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split ``pairs`` into (train, dev) **grouped by claim_id**.

    ⚠️ Never split these row-wise. One claim spans up to 5 abstracts and
    therefore many pairs; a row-level split leaks the claim text across the
    boundary and the dev score stops meaning anything.
    """
    claim_ids = sorted({p["claim_id"] for p in pairs})
    rng = random.Random(seed)
    rng.shuffle(claim_ids)

    n_dev = int(round(len(claim_ids) * dev_frac))
    dev_ids = set(claim_ids[:n_dev])

    dev = [p for p in pairs if p["claim_id"] in dev_ids]
    train = [p for p in pairs if p["claim_id"] not in dev_ids]
    return train, dev


# --------------------------------------------------------------------------
# Reporting and IO
# --------------------------------------------------------------------------


def class_counts(pairs: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(p["label"] for p in pairs)
    return {label: counter.get(label, 0) for label in LABELS}


def write_jsonl(pairs: list[dict[str, Any]], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for pair in pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _report(name: str, pairs: list[dict[str, Any]]) -> None:
    counts = class_counts(pairs)
    total = sum(counts.values()) or 1
    claims = len({p["claim_id"] for p in pairs})
    breakdown = "  ".join(f"{k} {v:5d} ({v / total:.1%})" for k, v in counts.items())
    print(f"  {name:12s} pairs {total:5d}  claims {claims:4d}  |  {breakdown}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="T-301 — build SciFact entailment pairs.")
    ap.add_argument("--nei-per-claim", type=int, default=2,
                    help="sentences sampled per NEI row (default 2, roughly class-balancing)")
    ap.add_argument("--dev-frac", type=float, default=0.15,
                    help="fraction of TRAIN claims held out for tuning (default 0.15)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    # NB: printed strings stay ASCII. Windows consoles default to cp1252 and a
    # stray emoji raises UnicodeEncodeError *after* the work is done, which
    # looks like a crash in the pairing. Docstrings are unaffected.
    print(f"T-301 - SciFact pairs  (seed={args.seed}, nei_per_claim={args.nei_per_claim})\n")

    raw_train = load_split("train")
    raw_val = load_split("validation")
    print(f"  loaded {len(raw_train)} train rows, {len(raw_val)} validation rows\n")

    all_train = build_pairs(raw_train, nei_per_claim=args.nei_per_claim, seed=args.seed)
    val = build_pairs(raw_val, nei_per_claim=args.nei_per_claim, seed=args.seed)
    train, dev = split_by_claim(all_train, dev_frac=args.dev_frac, seed=args.seed)

    print("class counts per split:")
    _report("train", train)
    _report("dev", dev)
    _report("validation", val)

    # The claim-grouped split is the one thing here that fails silently, so it
    # is asserted rather than trusted.
    overlap = {p["claim_id"] for p in train} & {p["claim_id"] for p in dev}
    assert not overlap, f"claim_id leaked across the train/dev split: {sorted(overlap)[:5]}"
    print("\n  OK: no claim_id appears in both train and dev")

    for name, pairs in (("train", train), ("dev", dev), ("validation", val)):
        path = args.out / f"pairs_{name}.jsonl"
        write_jsonl(pairs, path)
        print(f"  wrote {path}  ({len(pairs)} pairs)")

    meta = {
        "task": "T-301",
        "source": f"{_REPO}@{_REVISION}",
        "seed": args.seed,
        "nei_per_claim": args.nei_per_claim,
        "dev_frac": args.dev_frac,
        "labels": list(LABELS),
        "counts": {
            "train": class_counts(train),
            "dev": class_counts(dev),
            "validation": class_counts(val),
        },
        "note": (
            "validation is the untouched held-out set reported by T-305; dev is "
            "carved from train by claim_id for tuning only."
        ),
    }
    meta_path = args.out / "pairs_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  wrote {meta_path}")


if __name__ == "__main__":
    main()
