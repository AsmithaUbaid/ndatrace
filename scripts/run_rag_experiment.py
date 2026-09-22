#!/usr/bin/env python3
"""
Standard RAG end-to-end experiment (WBS T024) - the real test of whether
retrieved chunks contain everything the classifier needs, not just
whether they overlap the gold evidence span.

Oracle (B04) fed the model gold evidence directly, bypassing retrieval
entirely - it measures the model's reasoning ceiling, not whether our
actual retrieval pipeline (sentence chunking -> retrieve-20 ->
rerank(L-12) -> top-7 -> rule-boost via RRF, CLAUDE.md's Decisions Log)
gives the model *sufficient, complete* context to classify correctly.
Evidence Recall@K/Precision/MRR (T023, all 9 retrieval rounds) only check
character-span overlap with ContractNLI's annotated spans - they can't
tell us if a small sentence-level chunk, taken alone, is missing context
a human (or the model) would need to get the classification right.

This experiment runs the real, full pipeline - retriever ->
classifier - on the identical 150-case stratified sample used for
Oracle (same seed=42), so RAG's accuracy is directly comparable to
Oracle's ceiling: the gap between them is exactly what retrieval
imperfection costs in real classification terms, not a proxy metric.

Unlike Oracle (which special-cased NotMentioned as empty context), this
runs every case through the *real* retrieval pipeline regardless of
label - retrieval has no way to know the gold label in advance, and
part of what's being tested is whether the pipeline correctly returns
"nothing relevant" often enough for genuinely-absent topics.
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
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

EXPERIMENT_ID = "T024_rag"
SAMPLE_SIZE = 150


def main() -> int:
    dev_path = settings.data_path / "dev.json"
    dataset = parse_contractnli_file(dev_path)

    sample = stratified_sample(dataset, SAMPLE_SIZE, SEED)
    label_counts: dict[str, int] = {}
    for _, ann in sample:
        label_counts[ann.label] = label_counts.get(ann.label, 0) + 1
    print(f"Sampled {len(sample)} cases (seed={SEED}, identical to B04 Oracle): {label_counts}")

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
    checkpoint_keys = harness.completed_case_keys(EXPERIMENT_ID)
    if checkpoint_keys:
        print(f"Resuming: {len(checkpoint_keys)} cases already done in a previous run")

    # Build the retriever once per distinct document, reused across every
    # hypothesis sampled for that document (matches how a real NDA review
    # works - parse/embed/index once, ask it many questions).
    retrievers: dict[str, Retriever] = {}
    docs_by_id = {}

    start = time.time()
    for i, (doc, ann) in enumerate(sample, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue

        if doc.doc_id not in retrievers:
            retrievers[doc.doc_id] = Retriever(doc.text, chunk_method="sentence")
            docs_by_id[doc.doc_id] = doc
        retriever = retrievers[doc.doc_id]

        retrieved = retriever.query_rerank_and_boost(ann.hypothesis_id, ann.hypothesis_text)
        context = " ".join(r.chunk.text for r in retrieved)
        retrieved_span_indices = map_chunks_to_gold_span_indices(doc.spans, [r.chunk for r in retrieved])

        result = classify(context, ann.hypothesis_text, gateway, doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id)

        pred = Prediction(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            predicted_label=Label(result.label),
            confidence=result.confidence,
            retrieved_span_indices=retrieved_span_indices,
            retrieved_texts=[r.chunk.text for r in retrieved],
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
              f"gold={ann.label} pred={result.label} ({len(retrieved)} chunks, "
              f"${result.cost_usd:.5f}, {elapsed:.0f}s elapsed)")

    all_predictions = harness.load_checkpoint(EXPERIMENT_ID)

    config = ExperimentConfig(
        experiment_id=EXPERIMENT_ID, experiment_name="Standard RAG end-to-end",
        model=gateway.model, prompt_version="v1", architecture="rag",
        split="dev", sample_size=len(sample), seed=SEED,
    )
    result = harness.evaluate(all_predictions, config)
    harness.save_result(result, filename=f"runs/run_{EXPERIMENT_ID}.jsonl")
    harness.clear_checkpoint(EXPERIMENT_ID)

    m = result.metrics
    print("\n--- T024: Standard RAG end-to-end ---")
    print(f"  Accuracy:                    {m.accuracy:.3f}")
    print(f"  Macro-F1:                    {m.macro_f1:.3f}")
    print(f"  Risk-sensitive recall:       {m.risk_sensitive_recall:.3f}")
    print(f"  Joint label+evidence correct:{m.joint_label_evidence_correctness:.3f}")
    print(f"  Evidence recall@k:           {m.evidence_recall_at_k:.3f}")
    print(f"  Evidence precision:          {m.evidence_precision:.3f}")
    print(f"  MRR:                         {m.mrr:.3f}")
    for label, pc in m.per_class.items():
        print(f"    {label:14} precision={pc['precision']:.3f} recall={pc['recall']:.3f} f1={pc['f1']:.3f}")
    print(f"\n  Total cost: ${m.total_cost_usd:.4f}")
    print(f"  p50 latency: {m.p50_latency_ms:.0f}ms")

    print("\n--- Comparison to Oracle (same 150-case sample) ---")
    print("  Oracle (gold evidence):  accuracy 95.3% (Gemini) / 96.7% (GPT-5 mini)")
    print(f"  RAG (real retrieval):    accuracy {m.accuracy:.1%}")
    print(f"  Gap (retrieval cost):    {0.953 - m.accuracy:+.1%} vs Gemini Oracle")

    return 0


if __name__ == "__main__":
    sys.exit(main())
