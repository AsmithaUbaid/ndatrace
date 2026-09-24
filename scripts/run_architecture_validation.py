#!/usr/bin/env python3
"""
ARCHITECTURE-VALIDATION RUN (AV01) - the untouched, one-time check the
architecture freeze (docs/decisions.md ADR-009) never actually had.

THIS IS NOT T041. T041 is the official ContractNLI test-set evaluation and
is never re-run or re-tuned (docs/evaluation_protocol.md). This script runs
against data/architecture_validation_manifest.json instead - 340 cases
across 20 whole documents from ContractNLI's TRAIN split, verified by
scripts/build_architecture_validation_set.py to have zero overlap with the
150-case dev sample, retrieval tuning, regression/robustness cases, or the
official test split. See docs/decisions.md ADR-009's 2026-09-25 update and
docs/evaluation_protocol.md's "What's missing" section for why this exists:
every prior architecture comparison (Rule/Full-context/RAG/RAG+agent) reused
the same adaptively-tuned 150-case dev sample, so the freeze itself was
never checked against anything genuinely independent.

Runs the three candidate architectures EXACTLY as currently frozen/shipped -
no parameter is touched here relative to production:
  - full_context: pipeline/classifier.py's classify() on the whole document,
    default prompt_version ("v6", the current shipped default).
  - rag: pipeline/retriever.py's Retriever.query_rerank_and_boost() (current
    frozen config: sentence chunking, mpnet, retrieve-20, rerank L-12,
    top-7, rule-boost RRF fusion) + classify(), same v6 default.
  - rag_agent: pipeline/orchestrator.py's review_requirement() unmodified -
    the exact same function the live backend calls, including the
    routing-independence fix (two classifications) and the agent
    (agent_step_v2.txt, the current shipped default).

Uses the hosted default gateway (ModelGateway(), google/gemini-2.5-flash-lite)
- the model the architecture freeze itself was actually compared under, not
local Llama (used only for the separate hosted-vs-local question, C02).

The joint label+evidence correctness metric is populated correctly from the
start in every architecture below (never left as an empty
retrieved_span_indices list) - the exact bug found in scripts/
run_final_test_evaluation.py (docs/decisions.md ADR-010) and independently
confirmed to ALSO affect scripts/run_full_context_baseline.py (found during
the 2026-09-25 verification pass). Verified locally against 3 known dev-split
cases before being trusted here (see the verification transcript in this
project's session log / docs/decisions.md - zero new LLM calls were made for
that verification, only local deterministic retrieval).

THIS SCRIPT HAS NOT BEEN RUN. Per the explicit instruction that created it:
do not let it call any model until the split-overlap audit above is
independently re-confirmed and a human has reviewed
data/architecture_validation_manifest.json. Once run, per the same
instruction: do not tune the architecture again based on its results, and
do not re-run it after seeing results (only re-run to recover from a crash,
via the same checkpoint/resume mechanism every other script in this project
uses - resuming is not re-tuning).

Usage (NOT executed by the agent that wrote this - run manually when ready):
    python scripts/run_architecture_validation.py                       # all 3 architectures
    python scripts/run_architecture_validation.py --architecture rag    # one only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from evaluation.metrics import mcnemar_test
from evaluation.schemas import CostLatencyRecord, ExperimentConfig, GoldCase, Label, Prediction
from evaluation.scorer import map_chunks_to_gold_span_indices
from pipeline.classifier import classify
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.orchestrator import review_requirement
from pipeline.retriever import Retriever

ARCHITECTURES = ["full_context", "rag", "rag_agent"]
MANIFEST_PATH = Path("data/architecture_validation_manifest.json")
SPLIT_LABEL = "architecture_validation"  # deliberately distinct from "dev" and "test"


def load_validation_cases():
    """Re-parses train.json for the exact doc_ids in the manifest, rather
    than trusting only the manifest's flattened case list, so the full
    document text/spans (needed by classify()/Retriever, not stored in the
    manifest) come from the same real source the manifest was built from."""
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"{MANIFEST_PATH} not found - run scripts/build_architecture_validation_set.py first."
        )
    manifest = json.loads(MANIFEST_PATH.read_text())

    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from pipeline.config import settings
    from pipeline.parser import parse_contractnli_file

    train = parse_contractnli_file(settings.data_path / "train.json")
    doc_lookup = {d.doc_id: d for d, _ in train.all_cases()}

    manifest_doc_ids = set(manifest["doc_ids"])
    parsed_doc_ids = set(doc_lookup)
    missing = manifest_doc_ids - parsed_doc_ids
    if missing:
        raise ValueError(f"Manifest references doc_ids not found in train.json: {missing}")

    cases = []
    for c in manifest["cases"]:
        doc = doc_lookup[c["doc_id"]]
        ann = doc.annotations[c["hypothesis_id"]]
        cases.append((doc, ann))

    print(f"Loaded {len(cases)} cases across {len(manifest_doc_ids)} untouched documents "
          f"(manifest built {manifest.get('selection_method')}).")
    print(f"Overlap verification recorded in manifest: {manifest['overlap_verification_result']}")
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


def run_full_context(cases, golds, harness: EvaluationHarness, gateway: ModelGateway) -> None:
    experiment_id = "AV01_architecture_validation_full_context"
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
    experiment_id = "AV01_architecture_validation_rag"
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
    experiment_id = "AV01_architecture_validation_rag_agent"
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

    rag_results = harness.load_results("runs/run_AV01_architecture_validation_rag.jsonl")
    baseline_predictions = rag_results[-1].predictions if rag_results else None
    if baseline_predictions is None:
        print("  WARNING: no saved AV01 rag result found - run rag before rag_agent for "
              "agent_recovery_rate/agent_regression_rate to populate correctly.")

    _finalize(harness, experiment_id, "RAG + selective agent", gateway.model, golds,
              baseline_predictions=baseline_predictions)


def _finalize(harness: EvaluationHarness, experiment_id: str, arch_name: str, model: str,
              golds: list[GoldCase], baseline_predictions: list[Prediction] | None = None) -> None:
    all_predictions = harness.load_checkpoint(experiment_id)
    config = ExperimentConfig(
        experiment_id=experiment_id, experiment_name=arch_name,
        model=model, prompt_version="v6", architecture=experiment_id,
        split=SPLIT_LABEL, sample_size=len(all_predictions), seed=99,
    )
    result = harness.evaluate(all_predictions, config, baseline_predictions=baseline_predictions)
    harness.save_result(result, filename=f"runs/run_{experiment_id}.jsonl")
    harness.clear_checkpoint(experiment_id)

    m = result.metrics
    print(f"\n--- ARCHITECTURE VALIDATION (untouched, one-time): {arch_name} ---")
    print(f"  Accuracy:              {m.accuracy:.3f}")
    print(f"  Macro-F1:              {m.macro_f1:.3f}")
    print(f"  Contradiction recall:  {m.contradiction_recall:.3f} (n={m.contradiction_n}, "
          f"95% CI [{m.contradiction_recall_ci_low:.3f}, {m.contradiction_recall_ci_high:.3f}])")
    print(f"  Joint label+evidence:  {m.joint_label_evidence_correctness:.3f}")
    if baseline_predictions is not None:
        print(f"  Agent recovery rate:   {m.agent_recovery_rate:.3f}")
        print(f"  Agent regression rate: {m.agent_regression_rate:.3f}")
    print(f"  Total cost: ${m.total_cost_usd:.4f}\n")


def run_paired_comparisons(golds: list[GoldCase]) -> None:
    """Loads all three finalized results and runs every pairwise McNemar
    comparison + a full correct/incorrect breakdown - written once all
    three architectures have a saved result file."""
    harness = EvaluationHarness(gold_cases=golds)
    files = {
        "full_context": "runs/run_AV01_architecture_validation_full_context.jsonl",
        "rag": "runs/run_AV01_architecture_validation_rag.jsonl",
        "rag_agent": "runs/run_AV01_architecture_validation_rag_agent.jsonl",
    }
    preds = {}
    for arch, path in files.items():
        results = harness.load_results(path)
        if not results:
            print(f"Skipping paired comparison: {path} not found yet.")
            return
        preds[arch] = results[-1].predictions

    gold_lookup = {(g.doc_id, g.hypothesis_id): g.gold_label for g in golds}
    report = {}
    pairs = [("full_context", "rag"), ("rag", "rag_agent"), ("full_context", "rag_agent")]
    for a_name, b_name in pairs:
        a_map = {(p.doc_id, p.hypothesis_id): p for p in preds[a_name]}
        b_map = {(p.doc_id, p.hypothesis_id): p for p in preds[b_name]}
        common = set(a_map) & set(b_map)
        both_correct = both_wrong = a_only = b_only = 0
        for key in common:
            gold = gold_lookup[key]
            a_ok = a_map[key].predicted_label == gold
            b_ok = b_map[key].predicted_label == gold
            if a_ok and b_ok: both_correct += 1
            elif not a_ok and not b_ok: both_wrong += 1
            elif a_ok and not b_ok: a_only += 1
            else: b_only += 1

        mcnemar = mcnemar_test(preds[a_name], preds[b_name], golds)
        pair_key = f"{a_name}_vs_{b_name}"
        report[pair_key] = {
            "both_correct": both_correct, "both_wrong": both_wrong,
            f"{a_name}_only_correct": a_only, f"{b_name}_only_correct": b_only,
            "mcnemar": mcnemar,
        }
        print(f"\n{pair_key}: both_correct={both_correct} both_wrong={both_wrong} "
              f"{a_name}_only={a_only} {b_name}_only={b_only} "
              f"p={mcnemar['p_value']:.4f} significant={mcnemar['significant_at_0.05']}")

    out_path = Path("data/architecture_validation_paired_comparison.json")
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=ARCHITECTURES, default=None,
                         help="Run only this architecture (default: all three, in order)")
    args = parser.parse_args()

    cases = load_validation_cases()
    golds = build_golds(cases)
    harness = EvaluationHarness(gold_cases=golds)

    try:
        gateway = ModelGateway()  # hosted default: google/gemini-2.5-flash-lite
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"Model: {gateway.model} (hosted default - same model the architecture freeze was made under)")

    to_run = [args.architecture] if args.architecture else ARCHITECTURES
    retrievers: dict[str, Retriever] = {}

    if "full_context" in to_run:
        run_full_context(cases, golds, harness, gateway)
    if "rag" in to_run:
        run_rag(cases, golds, harness, gateway, retrievers)
    if "rag_agent" in to_run:
        run_rag_agent(cases, golds, harness, gateway, retrievers)

    if args.architecture is None:
        run_paired_comparisons(golds)

    print("\n=== ARCHITECTURE VALIDATION RUN COMPLETE ===")
    print("This was a ONE-TIME check. Do not tune the architecture further based on these")
    print("results, and do not re-run this script except to resume after a crash.")
    print("T041 remains the separate, historical official-test result - not superseded by this.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
