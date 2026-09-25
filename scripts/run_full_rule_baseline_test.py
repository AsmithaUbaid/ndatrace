#!/usr/bin/env python3
"""
Rule baseline (pipeline/rule_baseline.py) on the FULL 2,091-case official
test set. No LLM/API calls - classify_with_span is deterministic keyword
matching only.

The existing run_T041_final_test_rule.jsonl was built on a 500-case
stratified subsample (see docs/decisions.md's T041-A/T041-B history) and is
deliberately NOT overwritten here - this saves to a new file so both
remain available and comparable.

Mirrors run_final_test_evaluation.py's run_rule() logic exactly (including
the retrieved_span_indices fix), just retargeted at the full test set and a
non-colliding output filename.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.schemas import ExperimentConfig, GoldCase, Label, Prediction
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.rule_baseline import classify_with_span

OUTPUT_FILENAME = "runs/run_T041_final_test_rule_full.jsonl"


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "test.json")
    cases = dataset.all_cases()
    print(f"Test split: {dataset.num_documents} documents, {len(cases)} cases "
          f"(expected 123 x 17 = 2091)")

    golds = [
        GoldCase(doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id, gold_label=Label(ann.label),
                  gold_span_indices=[s.span_index for s in ann.evidence_spans])
        for doc, ann in cases
    ]
    harness = EvaluationHarness(gold_cases=golds)

    predictions = []
    for doc, ann in cases:
        label, span = classify_with_span(ann.hypothesis_id, doc.text)
        span_indices = []
        if span is not None:
            for idx, (s_start, s_end) in enumerate(doc.spans):
                if min(s_end, span[1]) > max(s_start, span[0]):
                    span_indices.append(idx)
        predictions.append(Prediction(doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                                       predicted_label=Label(label), retrieved_span_indices=span_indices))

    config = ExperimentConfig(
        experiment_id="T041_final_test_rule_full", experiment_name="Rule-based (no LLM), full test set",
        model="none", prompt_version="n/a", architecture="rule",
        split="test", sample_size=len(predictions), seed=0,
    )
    result = harness.evaluate(predictions, config)
    harness.save_result(result, filename=OUTPUT_FILENAME)

    m = result.metrics
    print(f"\n--- Rule baseline, full 2,091-case official test set ---")
    print(f"  Accuracy: {m.accuracy:.3f}  Macro-F1: {m.macro_f1:.3f}")
    print(f"  Contradiction recall: {m.contradiction_recall:.3f} (n={m.contradiction_n})")
    print(f"  Joint label+evidence: {m.joint_label_evidence_correctness:.3f}")
    print(f"\nSaved to results/{OUTPUT_FILENAME} (existing 500-case run_T041_final_test_rule.jsonl untouched)")
    print("No LLM/API calls were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
