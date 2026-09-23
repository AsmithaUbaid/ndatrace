#!/usr/bin/env python3
"""
FINAL LOCKED TEST-SET EVALUATION (WBS T041) - runs exactly once, on the
held-out test split, after architecture freeze (T031, 2026-09-23:
RAG + selective agent). No re-tuning after seeing these results, per
the plan's own rule and the instructor's revised final-evaluation
strategy (CLAUDE.md's Decisions Log, 2026-09-23).

Runs all four architectures on the FULL test split (123 documents x 17
hypotheses = 2,091 examples, verified) using the LOCAL model
(ModelGateway.local(), Llama 3.2 3B via Ollama - $0 cost, since the
hosted-vs-local comparison only needs a stratified subsample on Gemini,
built separately in scripts/run_hosted_vs_local_subsample.py):

  1. rule       - pipeline/rule_baseline.py, no LLM calls
  2. full_context - entire document + hypothesis, no retrieval
  3. rag        - Retriever.query_rerank_and_boost + classify()
  4. rag_agent  - rag, then run_agent() on REVIEW-routed cases
     (pipeline/confidence.py's rule-agreement check)

Each architecture checkpoints every prediction (resumable - this will
run for many hours) and saves a final result file distinguishable from
the earlier dev-sample runs (`_final_test_` in the filename, never
overwriting a dev result).

Usage:
    python scripts/run_final_test_evaluation.py                  # all 4, in order
    python scripts/run_final_test_evaluation.py --architecture rag  # one only
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.schemas import CostLatencyRecord, ExperimentConfig, GoldCase, Label, Prediction
from pipeline.agent import run_agent
from pipeline.classifier import classify
from pipeline.confidence import Route, route
from pipeline.config import settings
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_by_keywords

ARCHITECTURES = ["rule", "full_context", "rag", "rag_agent"]


def load_test_cases():
    dataset = parse_contractnli_file(settings.data_path / "test.json")
    cases = dataset.all_cases()
    print(f"Test split: {dataset.num_documents} documents, {len(cases)} cases "
          f"(expected 123 x 17 = 2091)")
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


def run_rule(cases, golds, harness: EvaluationHarness) -> None:
    experiment_id = "T041_final_test_rule"
    checkpoint_keys = harness.completed_case_keys(experiment_id)
    if checkpoint_keys:
        print(f"Resuming rule: {len(checkpoint_keys)} cases already done")

    start = time.time()
    for i, (doc, ann) in enumerate(cases, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue
        label = classify_by_keywords(ann.hypothesis_id, doc.text)
        pred = Prediction(doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id, predicted_label=Label(label))
        harness.save_prediction_checkpoint(experiment_id, pred)
        if i % 200 == 0:
            print(f"  [rule {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    _finalize(harness, experiment_id, "Rule-based (no LLM)", "none", golds)


def run_full_context(cases, golds, harness: EvaluationHarness, gateway: ModelGateway) -> None:
    experiment_id = "T041_final_test_full_context"
    checkpoint_keys = harness.completed_case_keys(experiment_id)
    if checkpoint_keys:
        print(f"Resuming full_context: {len(checkpoint_keys)} cases already done")

    start = time.time()
    for i, (doc, ann) in enumerate(cases, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue
        result = classify(doc.text, ann.hypothesis_text, gateway,
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
        harness.save_prediction_checkpoint(experiment_id, pred)
        if i % 50 == 0:
            print(f"  [full_context {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    _finalize(harness, experiment_id, "Full-context LLM", gateway.model, golds)


def run_rag(cases, golds, harness: EvaluationHarness, gateway: ModelGateway,
            retrievers: dict[str, Retriever]) -> None:
    experiment_id = "T041_final_test_rag"
    checkpoint_keys = harness.completed_case_keys(experiment_id)
    if checkpoint_keys:
        print(f"Resuming rag: {len(checkpoint_keys)} cases already done")

    start = time.time()
    for i, (doc, ann) in enumerate(cases, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue
        if doc.doc_id not in retrievers:
            retrievers[doc.doc_id] = Retriever(doc.text, chunk_method="sentence")
        retriever = retrievers[doc.doc_id]

        retrieved = retriever.query_rerank_and_boost(ann.hypothesis_id, ann.hypothesis_text)
        context = " ".join(r.chunk.text for r in retrieved)
        result = classify(context, ann.hypothesis_text, gateway,
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
        harness.save_prediction_checkpoint(experiment_id, pred)
        if i % 50 == 0:
            print(f"  [rag {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    _finalize(harness, experiment_id, "Standard RAG", gateway.model, golds)


def run_rag_agent(cases, golds, harness: EvaluationHarness, gateway: ModelGateway,
                   retrievers: dict[str, Retriever]) -> None:
    experiment_id = "T041_final_test_rag_agent"
    checkpoint_keys = harness.completed_case_keys(experiment_id)
    if checkpoint_keys:
        print(f"Resuming rag_agent: {len(checkpoint_keys)} cases already done")

    start = time.time()
    for i, (doc, ann) in enumerate(cases, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue
        if doc.doc_id not in retrievers:
            retrievers[doc.doc_id] = Retriever(doc.text, chunk_method="sentence")
        retriever = retrievers[doc.doc_id]

        retrieved = retriever.query_rerank_and_boost(ann.hypothesis_id, ann.hypothesis_text)
        context = " ".join(r.chunk.text for r in retrieved)
        rag_result = classify(context, ann.hypothesis_text, gateway,
                               doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id)

        rule_label = classify_by_keywords(ann.hypothesis_id, doc.text)
        decision = route(self_confidence=rag_result.confidence, rule_agrees=(rule_label == rag_result.label))

        if decision.route == Route.REVIEW:
            initial_chunks = [r.chunk for r in retrieved]
            agent_result = run_agent(retriever, ann.hypothesis_id, ann.hypothesis_text, initial_chunks,
                                      gateway, doc_id=doc.doc_id)
            final_label, final_conf = agent_result.label, agent_result.confidence
            final_explanation = agent_result.explanation
            cost = rag_result.cost_usd + agent_result.cost_usd
            tin = rag_result.tokens_in + agent_result.tokens_in
            tout = rag_result.tokens_out + agent_result.tokens_out
            latency = rag_result.latency_ms + agent_result.latency_ms
        else:
            final_label, final_conf = rag_result.label, rag_result.confidence
            final_explanation = rag_result.explanation
            cost, tin, tout, latency = rag_result.cost_usd, rag_result.tokens_in, rag_result.tokens_out, rag_result.latency_ms

        pred = Prediction(
            doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
            predicted_label=Label(final_label), confidence=final_conf,
            explanation=final_explanation, agent_used=(decision.route == Route.REVIEW),
            cost_latency=CostLatencyRecord(latency_ms=latency, tokens_in=tin, tokens_out=tout, cost_usd=cost),
        )
        harness.save_prediction_checkpoint(experiment_id, pred)
        if i % 50 == 0:
            print(f"  [rag_agent {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    _finalize(harness, experiment_id, "RAG + selective agent", gateway.model, golds)


def _finalize(harness: EvaluationHarness, experiment_id: str, arch_name: str, model: str, golds: list[GoldCase]) -> None:
    all_predictions = harness.load_checkpoint(experiment_id)
    config = ExperimentConfig(
        experiment_id=experiment_id, experiment_name=arch_name,
        model=model, prompt_version="v2", architecture=experiment_id,
        split="test", sample_size=len(all_predictions), seed=0,
    )
    result = harness.evaluate(all_predictions, config)
    harness.save_result(result, filename=f"runs/run_{experiment_id}.jsonl")
    harness.clear_checkpoint(experiment_id)

    m = result.metrics
    print(f"\n--- T041 FINAL TEST: {arch_name} ---")
    print(f"  Accuracy:              {m.accuracy:.3f}")
    print(f"  Macro-F1:              {m.macro_f1:.3f}")
    print(f"  Risk-sensitive recall: {m.risk_sensitive_recall:.3f}")
    print(f"  Contradiction recall:  {m.contradiction_recall:.3f} (n={m.contradiction_n}, "
          f"95% CI [{m.contradiction_recall_ci_low:.3f}, {m.contradiction_recall_ci_high:.3f}])")
    print(f"  Joint label+evidence:  {m.joint_label_evidence_correctness:.3f}")
    print(f"  Total cost: ${m.total_cost_usd:.4f}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=ARCHITECTURES, default=None,
                         help="Run only this architecture (default: all four, in order)")
    args = parser.parse_args()

    cases = load_test_cases()
    golds = build_golds(cases)
    harness = EvaluationHarness(gold_cases=golds)

    to_run = [args.architecture] if args.architecture else ARCHITECTURES

    if "rule" in to_run:
        run_rule(cases, golds, harness)

    if any(a in to_run for a in ("full_context", "rag", "rag_agent")):
        try:
            gateway = ModelGateway.local()
        except ModelError as e:
            print(f"ERROR: {e}")
            return 1
        print(f"Local model: {gateway.model}")

    if "full_context" in to_run:
        run_full_context(cases, golds, harness, gateway)

    retrievers: dict[str, Retriever] = {}
    if "rag" in to_run:
        run_rag(cases, golds, harness, gateway, retrievers)
    if "rag_agent" in to_run:
        run_rag_agent(cases, golds, harness, gateway, retrievers)

    print("=== FINAL TEST-SET EVALUATION COMPLETE ===")
    print("Per the plan's rule: no re-tuning based on these results. "
          "Architecture was frozen (T031) before this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
