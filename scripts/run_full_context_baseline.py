#!/usr/bin/env python3
"""
Full-context LLM baseline (WBS T015, experiment B03) - the missing rung
in the architecture ablation ladder (E07: rule -> full-context -> RAG ->
RAG+agent). Sends the ENTIRE NDA document (no retrieval at all) plus the
hypothesis to the classifier, to answer the plan's own framing question:
"Is retrieval needed?"

Runs on the identical 150-case stratified sample used for Oracle/RAG/
agent (seed=42), with the same adopted prompt (v2), so all four rungs of
the ablation ladder are directly comparable:
  - Rule-based (B02): 59.9% accuracy, $0 cost
  - Full-context (this script, B03): whole document, no retrieval
  - RAG (T018 v2): 88.0% accuracy, retrieved top-7 chunks (~312 tokens avg)
  - RAG+agent (T030): 90.0% accuracy, RAG + selective investigation
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.schemas import CostLatencyRecord, ExperimentConfig, GoldCase, Label, Prediction
from pipeline.classifier import classify
from pipeline.config import settings
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import parse_contractnli_file
from scripts.run_oracle_experiment import SEED, stratified_sample

EXPERIMENT_ID = "B03_full_context"
SAMPLE_SIZE = 150


def main() -> int:
    dev_path = settings.data_path / "dev.json"
    dataset = parse_contractnli_file(dev_path)

    sample = stratified_sample(dataset, SAMPLE_SIZE, SEED)
    label_counts: dict[str, int] = {}
    for _, ann in sample:
        label_counts[ann.label] = label_counts.get(ann.label, 0) + 1
    print(f"Sampled {len(sample)} cases (seed={SEED}, identical to B04/T018/T024/T030): {label_counts}")

    golds = [
        GoldCase(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            gold_label=Label(ann.label),
            gold_span_indices=[s.span_index for s in ann.evidence_spans],
        )
        for doc, ann in sample
    ]

    try:
        gateway = ModelGateway()
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"Model: {gateway.model}, prompt: v2 (adopted default)")

    harness = EvaluationHarness(gold_cases=golds)
    checkpoint_keys = harness.completed_case_keys(EXPERIMENT_ID)
    if checkpoint_keys:
        print(f"Resuming: {len(checkpoint_keys)} cases already done in a previous run")

    start = time.time()
    for i, (doc, ann) in enumerate(sample, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue

        result = classify(doc.text, ann.hypothesis_text, gateway,  # whole document, no retrieval
                          doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id)

        pred = Prediction(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            predicted_label=Label(result.label), confidence=result.confidence,
            explanation=result.explanation,
            cost_latency=CostLatencyRecord(
                latency_ms=result.latency_ms, tokens_in=result.tokens_in,
                tokens_out=result.tokens_out, cost_usd=result.cost_usd,
            ),
        )
        harness.save_prediction_checkpoint(EXPERIMENT_ID, pred)

        elapsed = time.time() - start
        mark = "OK" if result.label == ann.label else "X "
        print(f"[{i}/{len(sample)}] {mark} {doc.doc_id}/{ann.hypothesis_id}: "
              f"gold={ann.label} pred={result.label} (${result.cost_usd:.5f}, {elapsed:.0f}s elapsed)")

    all_predictions = harness.load_checkpoint(EXPERIMENT_ID)

    config = ExperimentConfig(
        experiment_id=EXPERIMENT_ID, experiment_name="Full-context LLM baseline",
        model=gateway.model, prompt_version="v2", architecture="full_context",
        split="dev", sample_size=len(sample), seed=SEED,
    )
    result = harness.evaluate(all_predictions, config)
    harness.save_result(result, filename=f"runs/run_{EXPERIMENT_ID}.jsonl")
    harness.clear_checkpoint(EXPERIMENT_ID)

    m = result.metrics
    print("\n--- B03: Full-context LLM baseline ---")
    print(f"  Accuracy:              {m.accuracy:.3f}")
    print(f"  Macro-F1:              {m.macro_f1:.3f}")
    print(f"  Risk-sensitive recall: {m.risk_sensitive_recall:.3f}")
    for label, pc in m.per_class.items():
        print(f"    {label:14} precision={pc['precision']:.3f} recall={pc['recall']:.3f} f1={pc['f1']:.3f}")
    print(f"\n  Total cost: ${m.total_cost_usd:.4f}")
    print(f"  p50 latency: {m.p50_latency_ms:.0f}ms")

    print("\n--- Architecture ablation ladder (E07) ---")
    print("  Rule-based (B02):      59.9% accuracy, $0 cost")
    print(f"  Full-context (B03):    {m.accuracy:.1%} accuracy, ${m.total_cost_usd:.4f}/150 cases, {m.p50_latency_ms:.0f}ms p50")
    print("  RAG (T018 v2):         88.0% accuracy, $0.0216/150 cases, ~1000ms p50")
    print("  RAG+agent (T030):      90.0% accuracy on full sample (net effect)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
