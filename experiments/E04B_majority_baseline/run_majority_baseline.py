#!/usr/bin/env python3
"""Compute the frozen majority-class floor on official ContractNLI TEST."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/contractnli/test.json"
OUTPUT = Path(__file__).with_name("summary.json")
LABELS = ("Entailment", "Contradiction", "NotMentioned")


def main() -> None:
    dataset = json.loads(DATA.read_text())
    gold = [
        annotation["choice"]
        for document in dataset["documents"]
        for annotation_set in document["annotation_sets"]
        for annotation in annotation_set["annotations"].values()
    ]
    counts = Counter(gold)
    majority = max(LABELS, key=counts.get)
    n = len(gold)
    true_positive = counts[majority]
    precision = true_positive / n
    recall = 1.0
    majority_f1 = 2 * precision * recall / (precision + recall)
    result = {
        "experiment_id": "E04B_majority_baseline",
        "role": "TRIVIAL BASELINE — not an architecture rung",
        "split": "official ContractNLI TEST",
        "n": n,
        "label_distribution": dict(counts),
        "predicted_label": majority,
        "accuracy": true_positive / n,
        "macro_f1": majority_f1 / len(LABELS),
        "contradiction_recall": 0.0,
        "joint": 0.0,
        "joint_note": "Joint is valid and zero: every Entailment prediction has empty evidence, while every non-Entailment label is wrong.",
        "hosted_calls": 0,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
