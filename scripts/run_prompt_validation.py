#!/usr/bin/env python3
"""
PVAL01 - prompt-validation run (2026-09-25). Compares prompt versions v2,
v5, v6 under ONE FIXED architecture (Full-context - no retrieval, isolates
prompt reasoning quality from retrieval luck) on data/prompt_validation_
manifest.json's 442 cases across 26 documents, verified to have zero
document-level overlap with every prior tuning/validation pool including
AV01 (scripts/build_prompt_validation_set.py).

Model, decoding, evaluator, and case order are identical across all three
runs - prompt_version is the ONLY variable. Each version gets its own
result file (never overwritten), so no run's outcome can influence
another's before this frozen evaluation completes.

No prompt or code changes are made based on intermediate results - all
three runs execute back-to-back from the same frozen manifest and script.

Usage:
    python scripts/run_prompt_validation.py                    # all three: v2, v5, v6
    python scripts/run_prompt_validation.py --version v6       # one only
"""

from __future__ import annotations

import argparse
import json
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

PROMPT_VERSIONS = ["v2", "v5", "v6"]
MANIFEST_PATH = Path("data/prompt_validation_manifest.json")
SPLIT_LABEL = "prompt_validation"


def load_pval01_cases():
    manifest = json.loads(MANIFEST_PATH.read_text())
    train = parse_contractnli_file(settings.data_path / "train.json")
    doc_lookup = {d.doc_id: d for d, _ in train.all_cases()}

    cases = []
    for c in manifest["cases"]:
        doc = doc_lookup[c["doc_id"]]
        ann = doc.annotations[c["hypothesis_id"]]
        cases.append((doc, ann))
    print(f"Loaded {len(cases)} cases across {len(manifest['doc_ids'])} untouched documents "
          f"(manifest seed={manifest['selection_seed']}).")
    return cases


def build_golds(cases) -> list[GoldCase]:
    return [
        GoldCase(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            gold_label=Label(ann.label),
            gold_span_indices=[s.span_index for s in ann.evidence_spans],
        )
        for doc, ann in cases
    ]


def _fallback_prediction(doc_id: str, hypothesis_id: str, error: Exception) -> Prediction:
    print(f"  MODEL FAILURE on {doc_id}/{hypothesis_id}: {error} - recording as NotMentioned, continuing")
    return Prediction(
        doc_id=doc_id, hypothesis_id=hypothesis_id, predicted_label=Label.NOT_MENTIONED,
        confidence=0.0, explanation=f"Model call failed after retries: {error}",
        cost_latency=CostLatencyRecord(latency_ms=0.0, tokens_in=0, tokens_out=0, cost_usd=0.0),
    )


def run_one_version(prompt_version: str, cases, golds, harness: EvaluationHarness, gateway: ModelGateway) -> None:
    experiment_id = f"PVAL01_full_context_{prompt_version}"
    checkpoint_keys = harness.completed_case_keys(experiment_id)
    if checkpoint_keys:
        print(f"Resuming {prompt_version}: {len(checkpoint_keys)} cases already done")

    start = time.time()
    for i, (doc, ann) in enumerate(cases, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue
        try:
            result = classify(doc.text, ann.hypothesis_text, gateway, prompt_version=prompt_version,
                               doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id)
            # Full-context sees the entire document - every annotated span is trivially
            # "available" to it, correct by construction (same convention as AV01/T041-B).
            pred = Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(result.label), confidence=result.confidence,
                explanation=result.explanation, retrieved_span_indices=list(range(len(doc.spans))),
                cost_latency=CostLatencyRecord(
                    latency_ms=result.latency_ms, tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out, cost_usd=result.cost_usd,
                ),
            )
        except ModelError as e:
            pred = _fallback_prediction(doc.doc_id, ann.hypothesis_id, e)
        harness.save_prediction_checkpoint(experiment_id, pred)
        if i % 50 == 0:
            print(f"  [{prompt_version} {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    all_predictions = harness.load_checkpoint(experiment_id)
    config = ExperimentConfig(
        experiment_id=experiment_id, experiment_name=f"PVAL01 Full-context, prompt {prompt_version}",
        model=gateway.model, prompt_version=prompt_version, architecture="full_context",
        split=SPLIT_LABEL, sample_size=len(all_predictions), seed=123,
    )
    result = harness.evaluate(all_predictions, config)
    harness.save_result(result, filename=f"runs/run_{experiment_id}.jsonl")
    harness.clear_checkpoint(experiment_id)

    m = result.metrics
    print(f"\n--- PVAL01 Full-context, prompt {prompt_version} ---")
    print(f"  Accuracy:              {m.accuracy:.3f}")
    print(f"  Macro-F1:              {m.macro_f1:.3f}")
    print(f"  Contradiction recall:  {m.contradiction_recall:.3f} (n={m.contradiction_n})")
    print(f"  Total cost: ${m.total_cost_usd:.4f}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=PROMPT_VERSIONS, default=None,
                         help="Run only this prompt version (default: all three, in order v2, v5, v6)")
    args = parser.parse_args()

    cases = load_pval01_cases()
    golds = build_golds(cases)
    harness = EvaluationHarness(gold_cases=golds)

    try:
        gateway = ModelGateway()  # hosted default: google/gemini-2.5-flash-lite
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"Model: {gateway.model} (identical across all versions - prompt_version is the only variable)")

    to_run = [args.version] if args.version else PROMPT_VERSIONS
    for version in to_run:
        run_one_version(version, cases, golds, harness, gateway)

    print("=== PVAL01 PROMPT-VALIDATION RUN COMPLETE ===")
    print("No prompt or code changes were made based on intermediate results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
