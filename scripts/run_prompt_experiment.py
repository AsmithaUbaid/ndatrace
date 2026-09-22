#!/usr/bin/env python3
"""
Prompt tuning experiment (WBS T018) - does making the prompt more
explicit about "don't guess from a thin/tangential excerpt" reduce the
dominant RAG failure mode found in T024 (NotMentioned false-positived as
Entailment/Contradiction on a superficially-relevant retrieved chunk,
57% of RAG's 21 errors)?

Compares two new prompt variants against the v1 baseline (already run
as T024, results/runs/run_T024_rag.jsonl - reused here, not re-run, to
save cost):
  - v2 (explicit-conservative): adds an instruction to default to
    NotMentioned unless the excerpt clearly and directly addresses the
    requirement, warning against inferring from shared vocabulary/topic.
  - v3 (few-shot): same instruction, demonstrated with three worked
    examples, including one showing a topically-related-but-irrelevant
    excerpt correctly labeled NotMentioned.

Same 150-case stratified sample (seed=42) as Oracle/RAG, same real
retrieval pipeline (Retriever.query_rerank_and_boost) - only the prompt
changes, so any accuracy difference is attributable to the prompt, not
retrieval variance (retrieval here is fully deterministic).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.schemas import CostLatencyRecord, ExperimentConfig, GoldCase, Label, Prediction
from evaluation.scorer import map_chunks_to_gold_span_indices
from pipeline.classifier import classify
from pipeline.config import settings
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from scripts.run_oracle_experiment import SEED, stratified_sample

PROMPT_VERSIONS = ["v5"]
SAMPLE_SIZE = 150


def main() -> int:
    dev_path = settings.data_path / "dev.json"
    dataset = parse_contractnli_file(dev_path)

    sample = stratified_sample(dataset, SAMPLE_SIZE, SEED)
    print(f"Sampled {len(sample)} cases (seed={SEED}, identical to B04 Oracle / T024 RAG)")

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

    print(f"Model: {gateway.model}")

    harness = EvaluationHarness(gold_cases=golds)
    retrievers: dict[str, Retriever] = {}

    # Precompute retrieval once per case (deterministic, shared across all
    # prompt versions) so only the classify() call differs per version.
    contexts: dict[tuple[str, str], tuple[str, list[int]]] = {}
    start = time.time()
    for doc, ann in sample:
        if doc.doc_id not in retrievers:
            retrievers[doc.doc_id] = Retriever(doc.text, chunk_method="sentence")
        retriever = retrievers[doc.doc_id]

        retrieved = retriever.query_rerank_and_boost(ann.hypothesis_id, ann.hypothesis_text)
        context = " ".join(r.chunk.text for r in retrieved)
        retrieved_span_indices = map_chunks_to_gold_span_indices(doc.spans, [r.chunk for r in retrieved])
        contexts[(doc.doc_id, ann.hypothesis_id)] = (context, retrieved_span_indices)
    print(f"Retrieval precomputed for {len(contexts)} cases in {time.time()-start:.0f}s")

    for prompt_version in PROMPT_VERSIONS:
        experiment_id = f"T018_prompt_{prompt_version}"
        checkpoint_keys = harness.completed_case_keys(experiment_id)
        if checkpoint_keys:
            print(f"Resuming {prompt_version}: {len(checkpoint_keys)} cases already done")

        start = time.time()
        for i, (doc, ann) in enumerate(sample, 1):
            key = (doc.doc_id, ann.hypothesis_id)
            if key in checkpoint_keys:
                continue

            context, retrieved_span_indices = contexts[key]
            result = classify(context, ann.hypothesis_text, gateway, prompt_version=prompt_version)

            pred = Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(result.label),
                confidence=result.confidence,
                retrieved_span_indices=retrieved_span_indices,
                explanation=result.explanation,
                cost_latency=CostLatencyRecord(
                    latency_ms=result.latency_ms, tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out, cost_usd=result.cost_usd,
                ),
            )
            harness.save_prediction_checkpoint(experiment_id, pred)

            elapsed = time.time() - start
            mark = "OK" if result.label == ann.label else "X "
            print(f"[{prompt_version} {i}/{len(sample)}] {mark} {doc.doc_id}/{ann.hypothesis_id}: "
                  f"gold={ann.label} pred={result.label} (${result.cost_usd:.5f}, {elapsed:.0f}s elapsed)")

        all_predictions = harness.load_checkpoint(experiment_id)
        config = ExperimentConfig(
            experiment_id=experiment_id, experiment_name=f"Prompt tuning - {prompt_version}",
            model=gateway.model, prompt_version=prompt_version, architecture="rag",
            split="dev", sample_size=len(sample), seed=SEED,
        )
        result = harness.evaluate(all_predictions, config)
        harness.save_result(result, filename=f"runs/run_{experiment_id}.jsonl")
        harness.clear_checkpoint(experiment_id)

        m = result.metrics
        print(f"\n--- T018: prompt {prompt_version} ---")
        print(f"  Accuracy:              {m.accuracy:.3f}")
        print(f"  Macro-F1:              {m.macro_f1:.3f}")
        print(f"  Risk-sensitive recall: {m.risk_sensitive_recall:.3f}")
        for label, pc in m.per_class.items():
            print(f"    {label:14} precision={pc['precision']:.3f} recall={pc['recall']:.3f} f1={pc['f1']:.3f}")
        print(f"  Total cost: ${m.total_cost_usd:.4f}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
