#!/usr/bin/env python3
"""
FINAL LOCKED TEST-SET EVALUATION (WBS T041) - runs exactly once, on the
held-out test split, after architecture freeze (T031, 2026-09-23:
RAG + selective agent). No re-tuning after seeing these results, per
the plan's own rule and the instructor's revised final-evaluation
strategy (CLAUDE.md's Decisions Log, 2026-09-23).

Runs all four architectures on a STRATIFIED SUBSAMPLE of the test split
(default 500 of 2,091 examples - full-set-on-Groq hit an 8K-tokens/min
free-tier cap making it slower than local despite zero heat; full-set-
on-local was ~12-15h of sustained local compute/heat. 500 examples on
local Ollama keeps runtime to ~3-4h while staying statistically
meaningful - the same scale the instructor suggested for the hosted
comparison, applied here too) using the LOCAL model (ModelGateway.local(),
$0 cost):

  1. rule       - pipeline/rule_baseline.py, no LLM calls
  2. full_context - entire document + hypothesis, no retrieval
  3. rag        - Retriever.query_rerank_and_boost + classify()
  4. rag_agent  - rag, then run_agent() on REVIEW-routed cases
     (pipeline/confidence.py's rule-agreement check)

Each architecture checkpoints every prediction (resumable) and saves a
final result file distinguishable from the earlier dev-sample runs
(`_final_test_` in the filename, never overwriting a dev result).
Experiment IDs are tagged with the model name so switching providers
mid-project (as happened here) can never silently mix predictions from
two different models into one result.

Usage:
    python scripts/run_final_test_evaluation.py                       # all 4, 500-example subsample
    python scripts/run_final_test_evaluation.py --sample-size 2091    # full test set
    python scripts/run_final_test_evaluation.py --architecture rag    # one architecture only
"""

from __future__ import annotations

import argparse
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
from pipeline.orchestrator import review_requirement
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_with_span
from scripts.run_oracle_experiment import stratified_sample

ARCHITECTURES = ["rule", "full_context", "rag", "rag_agent"]
DEFAULT_SAMPLE_SIZE = 500
SEED = 42


def load_test_cases(sample_size: int | None):
    dataset = parse_contractnli_file(settings.data_path / "test.json")
    if sample_size is not None and sample_size < len(dataset.all_cases()):
        cases = stratified_sample(dataset, sample_size, SEED)
        print(f"Test split: {dataset.num_documents} documents, {len(dataset.all_cases())} total "
              f"cases - using a stratified subsample of {len(cases)} (seed={SEED})")
        return cases
    return _load_full_test_cases(dataset)


def _load_full_test_cases(dataset):
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
        label, span = classify_with_span(ann.hypothesis_id, doc.text)
        # Real gap found and fixed 2026-09-24: retrieved_span_indices was
        # never populated anywhere in this script, silently making the
        # joint label+evidence metric equal to just "NotMentioned-correct
        # fraction" for every T041 run (confirmed: reported joint 0.334
        # exactly equals the NotMentioned-only accuracy on that same run).
        # The rule's one matched span (if it fired) IS its "evidence".
        span_indices = []
        if span is not None:
            for idx, (s_start, s_end) in enumerate(doc.spans):
                if min(s_end, span[1]) > max(s_start, span[0]):
                    span_indices.append(idx)
        pred = Prediction(doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id, predicted_label=Label(label),
                           retrieved_span_indices=span_indices)
        harness.save_prediction_checkpoint(experiment_id, pred)
        if i % 200 == 0:
            print(f"  [rule {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    _finalize(harness, experiment_id, "Rule-based (no LLM)", "none", golds)


def _model_tag(gateway: ModelGateway) -> str:
    """
    Sanitized model identifier for experiment IDs - keeps checkpoints/
    results from different providers (Groq vs local Ollama) from ever
    colliding. Found the hard way: switching providers mid-run silently
    resumed a checkpoint full of the OTHER provider's predictions, which
    would have corrupted the final locked test-set result.
    """
    return gateway.model.replace("/", "_").replace(":", "_")


def _fallback_prediction(doc_id: str, hypothesis_id: str, error: Exception) -> Prediction:
    """
    Safe default when the model fails even after retries (Section 4 Flow
    7 "External Model Failure", Section 12 Reliability Testing: "Model
    timeout handled gracefully, no crash"). Found the hard way: a real
    test-split document made local Llama loop and hit Ollama's own
    "token repeat limit" abort - deterministic given temperature=0, so
    retrying the identical request just fails the same way every time.
    Never silently claim a positive label on failure - same convention
    as pipeline/classifier.py's own _fallback_result.
    """
    print(f"  MODEL FAILURE on {doc_id}/{hypothesis_id}: {error} - recording as NotMentioned, continuing")
    return Prediction(
        doc_id=doc_id, hypothesis_id=hypothesis_id, predicted_label=Label.NOT_MENTIONED,
        confidence=0.0, explanation=f"Model call failed after retries: {error}",
        cost_latency=CostLatencyRecord(latency_ms=0.0, tokens_in=0, tokens_out=0, cost_usd=0.0),
    )


def run_full_context(cases, golds, harness: EvaluationHarness, gateway: ModelGateway) -> None:
    experiment_id = f"T041_final_test_full_context_{_model_tag(gateway)}"
    checkpoint_keys = harness.completed_case_keys(experiment_id)
    if checkpoint_keys:
        print(f"Resuming full_context: {len(checkpoint_keys)} cases already done")

    start = time.time()
    for i, (doc, ann) in enumerate(cases, 1):
        key = (doc.doc_id, ann.hypothesis_id)
        if key in checkpoint_keys:
            continue
        try:
            result = classify(doc.text, ann.hypothesis_text, gateway,
                               doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id)
            # Full-context sees the ENTIRE document, so every annotated span
            # is trivially "available" to it - not populating this (the
            # original bug) silently zeroed out the joint metric for every
            # Entailment/Contradiction case regardless of true evidence use.
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
            print(f"  [full_context {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    _finalize(harness, experiment_id, "Full-context LLM", gateway.model, golds)


def run_rag(cases, golds, harness: EvaluationHarness, gateway: ModelGateway,
            retrievers: dict[str, Retriever]) -> None:
    experiment_id = f"T041_final_test_rag_{_model_tag(gateway)}"
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
        retrieved_span_indices = map_chunks_to_gold_span_indices(doc.spans, [r.chunk for r in retrieved])
        try:
            result = classify(context, ann.hypothesis_text, gateway,
                               doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id)
            pred = Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(result.label), confidence=result.confidence,
                explanation=result.explanation, retrieved_span_indices=retrieved_span_indices,
                cost_latency=CostLatencyRecord(
                    latency_ms=result.latency_ms, tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out, cost_usd=result.cost_usd,
                ),
            )
        except ModelError as e:
            pred = _fallback_prediction(doc.doc_id, ann.hypothesis_id, e)
        harness.save_prediction_checkpoint(experiment_id, pred)
        if i % 50 == 0:
            print(f"  [rag {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    _finalize(harness, experiment_id, "Standard RAG", gateway.model, golds)


def run_rag_agent(cases, golds, harness: EvaluationHarness, gateway: ModelGateway,
                   retrievers: dict[str, Retriever]) -> None:
    """
    Uses pipeline/orchestrator.py's review_requirement() rather than
    re-implementing the retrieve->classify->route->agent logic inline
    (Section 0A: scripts import from pipeline/, never duplicate it - this
    also carries the routing-independence fix, code-audit finding C-1,
    2026-09-24: the rule-agreement check now compares against a plain,
    non-rule-boosted classification instead of the rule-boosted one).
    """
    experiment_id = f"T041_final_test_rag_agent_{_model_tag(gateway)}"
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

        try:
            result = review_requirement(doc.text, ann.hypothesis_id, ann.hypothesis_text, gateway,
                                         retriever=retriever, doc_id=doc.doc_id)
            # review_requirement() doesn't expose which chunks it used, so
            # this recomputes the SAME deterministic (free, no LLM call)
            # rule-boosted retrieval purely to record which annotated spans
            # were available to the final answer - same fix as run_rag's,
            # needed independently here since orchestrator.py's ReviewResult
            # never carried chunk info out.
            retrieved = retriever.query_rerank_and_boost(ann.hypothesis_id, ann.hypothesis_text)
            retrieved_span_indices = map_chunks_to_gold_span_indices(doc.spans, [r.chunk for r in retrieved])
            pred = Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(result.label), confidence=result.confidence,
                explanation=result.explanation, agent_used=result.agent_used,
                retrieved_span_indices=retrieved_span_indices,
                cost_latency=CostLatencyRecord(latency_ms=result.latency_ms, tokens_in=result.tokens_in,
                                                tokens_out=result.tokens_out, cost_usd=result.cost_usd),
            )
        except ModelError as e:
            pred = _fallback_prediction(doc.doc_id, ann.hypothesis_id, e)
        harness.save_prediction_checkpoint(experiment_id, pred)
        if i % 50 == 0:
            print(f"  [rag_agent {i}/{len(cases)}] {time.time()-start:.0f}s elapsed")

    # Load the already-finalized plain "rag" result as the baseline for
    # agent_recovery_rate/agent_regression_rate - without this, both metrics
    # silently default to 0.0 (evaluation/metrics.py returns 0.0 when
    # baseline_predictions is None), which was happening in every T041
    # result saved before this fix (2026-09-24 gap found alongside C-1).
    rag_experiment_id = f"T041_final_test_rag_{_model_tag(gateway)}"
    rag_results = harness.load_results(f"runs/run_{rag_experiment_id}.jsonl")
    baseline_predictions = rag_results[-1].predictions if rag_results else None
    if baseline_predictions is None:
        print(f"  WARNING: no saved rag result found for baseline - "
              f"agent_recovery_rate/agent_regression_rate will be 0.0")

    _finalize(harness, experiment_id, "RAG + selective agent", gateway.model, golds,
              baseline_predictions=baseline_predictions)


def _finalize(harness: EvaluationHarness, experiment_id: str, arch_name: str, model: str, golds: list[GoldCase],
              baseline_predictions: list[Prediction] | None = None) -> None:
    all_predictions = harness.load_checkpoint(experiment_id)
    config = ExperimentConfig(
        experiment_id=experiment_id, experiment_name=arch_name,
        model=model, prompt_version="v6", architecture=experiment_id,
        split="test", sample_size=len(all_predictions), seed=0,
    )
    result = harness.evaluate(all_predictions, config, baseline_predictions=baseline_predictions)
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
    if baseline_predictions is not None:
        print(f"  Agent recovery rate:   {m.agent_recovery_rate:.3f}")
        print(f"  Agent regression rate: {m.agent_regression_rate:.3f}")
    print(f"  Total cost: ${m.total_cost_usd:.4f}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=ARCHITECTURES, default=None,
                         help="Run only this architecture (default: all four, in order)")
    parser.add_argument("--provider", choices=["groq", "local"], default="local",
                         help="Which $0 backend to use (default: local - Groq's free tier caps "
                              "at ~8K tokens/min across all its models, making it slower overall "
                              "than local despite zero heat; falls back to local automatically "
                              "if no GROQ_API_KEY is set when --provider groq is requested)")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE,
                         help=f"Stratified subsample size (default: {DEFAULT_SAMPLE_SIZE}). "
                              f"Pass 2091 (or higher) for the full test split.")
    args = parser.parse_args()

    cases = load_test_cases(args.sample_size)
    golds = build_golds(cases)
    harness = EvaluationHarness(gold_cases=golds)

    to_run = [args.architecture] if args.architecture else ARCHITECTURES

    if "rule" in to_run:
        run_rule(cases, golds, harness)

    if any(a in to_run for a in ("full_context", "rag", "rag_agent")):
        try:
            if args.provider == "groq":
                gateway = ModelGateway.groq()
            else:
                gateway = ModelGateway.local()
        except ModelError as e:
            if args.provider == "groq":
                print(f"Groq unavailable ({e}), falling back to local Ollama.")
                gateway = ModelGateway.local()
            else:
                print(f"ERROR: {e}")
                return 1
        print(f"Model: {gateway.model} (provider: {args.provider})")

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
