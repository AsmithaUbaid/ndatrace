#!/usr/bin/env python3
"""
Run the two zero-cost baselines (WBS T013, T014 / experiments B01, B02)
against the ContractNLI dev split and save results via the evaluation
harness. Neither baseline calls an LLM, so both can run without an
OpenRouter API key.

B01 - Majority-class baseline: always predict the dataset's majority
      label. Sets the absolute floor.
B02 - Rule-based keyword baseline: pipeline/rule_baseline.py's keyword
      rules per hypothesis. Sets the non-AI floor.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.schemas import ExperimentConfig, Label, Prediction
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.rule_baseline import classify_by_keywords


def run_majority_baseline(golds, majority_label: str) -> list[Prediction]:
    return [
        Prediction(doc_id=g.doc_id, hypothesis_id=g.hypothesis_id,
                   predicted_label=Label(majority_label))
        for g in golds
    ]


def run_rule_baseline(dataset) -> list[Prediction]:
    predictions = []
    for doc, ann in dataset.all_cases():
        label = classify_by_keywords(ann.hypothesis_id, doc.text)
        predictions.append(Prediction(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            predicted_label=Label(label),
        ))
    return predictions


def print_metrics(name: str, metrics) -> None:
    print(f"\n--- {name} ---")
    print(f"  Accuracy:               {metrics.accuracy:.3f}")
    print(f"  Macro-F1:               {metrics.macro_f1:.3f}")
    print(f"  Risk-sensitive recall:  {metrics.risk_sensitive_recall:.3f}")
    print(f"  Joint correctness:      {metrics.joint_label_evidence_correctness:.3f}")
    for label, pc in metrics.per_class.items():
        print(f"    {label:14} precision={pc['precision']:.3f} recall={pc['recall']:.3f} f1={pc['f1']:.3f}")


def main() -> int:
    data_dir = settings.data_path
    dev_path = data_dir / "dev.json"
    if not dev_path.exists():
        print(f"ERROR: {dev_path} not found. Run scripts/download_data.sh first.")
        return 1

    dataset = parse_contractnli_file(dev_path)
    print(f"Loaded {dataset.num_documents} dev documents, "
          f"{len(dataset.all_cases())} (doc, hypothesis) cases")

    harness = EvaluationHarness()
    golds = harness.load_gold_from_dataset(dataset.documents)

    label_dist = dataset.label_distribution()
    majority_label = max(label_dist, key=label_dist.get)
    print(f"Label distribution: {label_dist} -> majority = {majority_label}")

    # --- B01: Majority-class baseline ---
    majority_preds = run_majority_baseline(golds, majority_label)
    majority_config = ExperimentConfig(
        experiment_id="B01_majority_baseline",
        experiment_name="Majority-class baseline",
        description=f"Always predicts {majority_label} (the dev-set majority class)",
        architecture="rule",
        split="dev",
    )
    majority_result = harness.evaluate(majority_preds, majority_config)
    harness.save_result(majority_result, filename="runs/run_B01_majority_baseline.jsonl")
    print_metrics("B01: Majority-class baseline", majority_result.metrics)

    # --- B02: Rule-based keyword baseline ---
    rule_preds = run_rule_baseline(dataset)
    rule_config = ExperimentConfig(
        experiment_id="B02_rule_baseline",
        experiment_name="Rule-based keyword baseline",
        description="Per-hypothesis positive/negative keyword rules (pipeline/rule_baseline.py)",
        architecture="rule",
        split="dev",
    )
    rule_result = harness.evaluate(rule_preds, rule_config)
    harness.save_result(rule_result, filename="runs/run_B02_rule_baseline.jsonl")
    print_metrics("B02: Rule-based keyword baseline", rule_result.metrics)

    print("\nResults saved to results/runs/run_B01_majority_baseline.jsonl "
          "and results/runs/run_B02_rule_baseline.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
