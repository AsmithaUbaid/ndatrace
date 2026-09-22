#!/usr/bin/env python3
"""
Oracle experiment (WBS T016, experiment B04) - the single most important
measurement in the whole plan.

Feeds gold evidence directly to the model (bypassing retrieval entirely)
to answer: is the reasoning ceiling set by retrieval quality, or by the
model itself? Per the planning doc's Oracle Decision Tree (Section 10):
if Oracle accuracy < 75%, the model is too weak and must be swapped
before building anything else on top. If > 90%, the model reasons well
and retrieval is the real bottleneck worth investing in.

For Entailment/Contradiction cases, the model sees only the gold evidence
spans - exactly what a perfect retriever would return. For NotMentioned
cases, gold evidence is empty by definition, so the model sees empty
context, simulating what a perfect retriever returns for a genuinely
absent topic.

Since the model is given exactly the gold evidence, retrieved_span_indices
is set equal to gold_span_indices by construction (evaluation.scorer's
make_oracle_prediction does this) - evidence metrics are trivially perfect
here, so joint correctness collapses to label accuracy for this experiment.

Runs a stratified sample (not the full dev set) to keep cost and wall-clock
time reasonable for a first pass; sample proportions match the real dev
label distribution. Checkpoints each prediction (T007/A09 resumption) so a
crash mid-run doesn't lose progress.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.schemas import ExperimentConfig, GoldCase, Label
from evaluation.scorer import make_oracle_prediction
from pipeline.classifier import classify
from pipeline.config import settings
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import parse_contractnli_file

EXPERIMENT_ID = "B04_oracle"
SAMPLE_SIZE = 150
SEED = 42


def stratified_sample(dataset, sample_size: int, seed: int) -> list:
    """Sample (doc, annotation) pairs proportional to the real label distribution."""
    all_cases = dataset.all_cases()
    by_label: dict[str, list] = {"Entailment": [], "Contradiction": [], "NotMentioned": []}
    for doc, ann in all_cases:
        by_label[ann.label].append((doc, ann))

    total = len(all_cases)
    rng = random.Random(seed)
    sampled = []
    for label, cases in by_label.items():
        n = round(sample_size * len(cases) / total)
        sampled.extend(rng.sample(cases, min(n, len(cases))))
    rng.shuffle(sampled)
    return sampled


def build_oracle_context(ann) -> str:
    """What a perfect retriever would hand the classifier."""
    if not ann.evidence_spans:
        return ""
    return " ".join(s.text for s in ann.evidence_spans)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int, default=SAMPLE_SIZE,
                         help=f"Number of cases to sample (default: {SAMPLE_SIZE})")
    parser.add_argument("--model", default=None,
                         help="Override the model (default: settings.default_model). "
                              "Sample selection uses the same seed regardless of model, "
                              "for a fair apples-to-apples comparison across models.")
    args = parser.parse_args()

    model_tag = (args.model or settings.default_model).replace("/", "_")
    experiment_id = f"{EXPERIMENT_ID}_{model_tag}"

    dev_path = settings.data_path / "dev.json"
    dataset = parse_contractnli_file(dev_path)

    sample = stratified_sample(dataset, args.sample_size, SEED)
    label_counts: dict[str, int] = {}
    for _, ann in sample:
        label_counts[ann.label] = label_counts.get(ann.label, 0) + 1
    print(f"Sampled {len(sample)} cases (seed={SEED}): {label_counts}")

    golds = [
        GoldCase(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            gold_label=Label(ann.label),
            gold_span_indices=[s.span_index for s in ann.evidence_spans],
        )
        for doc, ann in sample
    ]

    try:
        gateway = ModelGateway(model=args.model)
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1

    print(f"Model: {gateway.model}")

    harness = EvaluationHarness(gold_cases=golds)
    checkpoint_keys = harness.completed_case_keys(experiment_id)
    if checkpoint_keys:
        print(f"Resuming: {len(checkpoint_keys)} cases already done in a previous run")

    start = time.time()
    for i, (doc, ann) in enumerate(sample, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue

        oracle_context = build_oracle_context(ann)
        result = classify(oracle_context, ann.hypothesis_text, gateway)

        pred = make_oracle_prediction(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            label=result.label, confidence=result.confidence,
            gold_span_indices=[s.span_index for s in ann.evidence_spans],
            explanation=result.explanation, latency_ms=result.latency_ms,
            tokens_in=result.tokens_in, tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
        )
        harness.save_prediction_checkpoint(experiment_id, pred)

        elapsed = time.time() - start
        mark = "OK" if result.label == ann.label else "X "
        print(f"[{i}/{len(sample)}] {mark} {doc.doc_id}/{ann.hypothesis_id}: "
              f"gold={ann.label} pred={result.label} "
              f"(${result.cost_usd:.5f}, {elapsed:.0f}s elapsed)")

    all_predictions = harness.load_checkpoint(experiment_id)

    config = ExperimentConfig(
        experiment_id=experiment_id, experiment_name="Oracle-evidence baseline",
        model=gateway.model, prompt_version="v1", architecture="oracle",
        split="dev", sample_size=len(sample), seed=SEED,
    )
    result = harness.evaluate(all_predictions, config)
    harness.save_result(result, filename=f"runs/run_{experiment_id}.jsonl")
    harness.clear_checkpoint(experiment_id)

    m = result.metrics
    print("\n--- B04: Oracle-evidence baseline ---")
    print(f"  Accuracy:               {m.accuracy:.3f}")
    print(f"  Macro-F1:               {m.macro_f1:.3f}")
    print(f"  Risk-sensitive recall:  {m.risk_sensitive_recall:.3f}")
    print(f"  Joint correctness:      {m.joint_label_evidence_correctness:.3f} "
          f"(should ~= accuracy - evidence is trivially perfect here)")
    for label, pc in m.per_class.items():
        print(f"    {label:14} precision={pc['precision']:.3f} recall={pc['recall']:.3f} f1={pc['f1']:.3f}")
    print(f"\n  Total cost: ${m.total_cost_usd:.4f}")
    print(f"  p50 latency: {m.p50_latency_ms:.0f}ms")

    print("\n--- Decision Gate (Section 10, Oracle Decision Tree) ---")
    if m.accuracy < 0.75:
        print(f"  Oracle accuracy {m.accuracy:.1%} < 75% -> MODEL TOO WEAK. "
              f"Consider switching models before building retrieval/RAG on top.")
    elif m.accuracy > 0.90:
        print(f"  Oracle accuracy {m.accuracy:.1%} > 90% -> model reasons well. "
              f"Retrieval quality is the real bottleneck - invest there.")
    else:
        print(f"  Oracle accuracy {m.accuracy:.1%} is 75-90% -> proceed, "
              f"but both retrieval and reasoning likely matter.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
