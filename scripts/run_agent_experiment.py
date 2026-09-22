#!/usr/bin/env python3
"""
Agent experiment (WBS T030, experiments G01/G07/G08) - does the selective
agent actually help on the cases pipeline/confidence.py (T027) routes to
REVIEW, or does it introduce regressions (eval case 074's critical
failure mode: RAG already right, agent flips it to wrong)?

Runs the real agent (pipeline/agent.py, T029) on every REVIEW-routed case
from the same 150-case sample used throughout (v2-prompt RAG results,
T018, seed=42) - real API calls, real cost, unlike T026's free reuse.

For each REVIEW case, classifies the outcome as:
  - recovery:    RAG was wrong, agent got it right
  - regression:  RAG was right, agent got it wrong (the critical failure mode)
  - no_change:   agent agrees with RAG's original correctness (right stays
                 right, or wrong stays wrong)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from pipeline.agent import run_agent
from pipeline.config import settings
from pipeline.confidence import Route, route
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_by_keywords
from scripts.run_oracle_experiment import SEED, stratified_sample


def main() -> int:
    harness = EvaluationHarness()
    rag = harness.load_results("runs/run_T018_prompt_v2.jsonl")[0]

    dataset = parse_contractnli_file(settings.data_path / "dev.json")
    sample = stratified_sample(dataset, 150, SEED)
    gold_by_key = {(doc.doc_id, ann.hypothesis_id): ann.label for doc, ann in sample}
    hyp_text_by_key = {(doc.doc_id, ann.hypothesis_id): ann.hypothesis_text for doc, ann in sample}
    doc_by_id = {doc.doc_id: doc for doc, _ in sample}

    try:
        gateway = ModelGateway()
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"Model: {gateway.model}")

    review_cases = []
    for pred in rag.predictions:
        key = (pred.doc_id, pred.hypothesis_id)
        rule_label = classify_by_keywords(pred.hypothesis_id, doc_by_id[pred.doc_id].text)
        decision = route(self_confidence=pred.confidence, rule_agrees=(rule_label == pred.predicted_label.value))
        if decision.route == Route.REVIEW:
            review_cases.append(pred)

    print(f"{len(review_cases)} of {len(rag.predictions)} cases routed to REVIEW\n")

    retrievers: dict[str, Retriever] = {}
    outcomes = []
    total_cost = 0.0
    start = time.time()

    for i, pred in enumerate(review_cases, 1):
        key = (pred.doc_id, pred.hypothesis_id)
        gold_label = gold_by_key[key]
        rag_correct = pred.predicted_label.value == gold_label

        if pred.doc_id not in retrievers:
            retrievers[pred.doc_id] = Retriever(doc_by_id[pred.doc_id].text, chunk_method="sentence")
        retriever = retrievers[pred.doc_id]

        initial = retriever.query_rerank_and_boost(pred.hypothesis_id, hyp_text_by_key[key])
        initial_chunks = [r.chunk for r in initial]

        result = run_agent(retriever, pred.hypothesis_id, hyp_text_by_key[key], initial_chunks, gateway,
                            doc_id=pred.doc_id)
        total_cost += result.cost_usd
        agent_correct = result.label == gold_label

        if rag_correct and not agent_correct:
            outcome = "regression"
        elif not rag_correct and agent_correct:
            outcome = "recovery"
        else:
            outcome = "no_change"

        outcomes.append({
            "doc_id": pred.doc_id, "hypothesis_id": pred.hypothesis_id, "gold_label": gold_label,
            "rag_label": pred.predicted_label.value, "agent_label": result.label,
            "rag_correct": rag_correct, "agent_correct": agent_correct, "outcome": outcome,
            "n_steps": len(result.trace.steps), "stopped_reason": result.trace.stopped_reason,
            "cost_usd": result.cost_usd,
            "steps": [{"action": s.action, "query": s.query, "summary": s.result_summary}
                      for s in result.trace.steps],
        })

        elapsed = time.time() - start
        print(f"[{i}/{len(review_cases)}] {outcome:10} rag={pred.predicted_label.value:13} "
              f"agent={result.label:13} gold={gold_label:13} steps={len(result.trace.steps)} "
              f"({result.trace.stopped_reason}, ${result.cost_usd:.5f}, {elapsed:.0f}s elapsed)")

    n = len(outcomes)
    n_recovery = sum(o["outcome"] == "recovery" for o in outcomes)
    n_regression = sum(o["outcome"] == "regression" for o in outcomes)
    n_no_change = sum(o["outcome"] == "no_change" for o in outcomes)
    rag_accuracy_on_review = sum(o["rag_correct"] for o in outcomes) / n
    agent_accuracy_on_review = sum(o["agent_correct"] for o in outcomes) / n
    avg_steps = sum(o["n_steps"] for o in outcomes) / n
    stopped_reasons = {}
    for o in outcomes:
        stopped_reasons[o["stopped_reason"]] = stopped_reasons.get(o["stopped_reason"], 0) + 1

    print(f"\n--- T030: Agent experiment ({n} REVIEW-routed cases) ---")
    print(f"  RAG accuracy on REVIEW subset:   {rag_accuracy_on_review:.3f}")
    print(f"  Agent accuracy on REVIEW subset: {agent_accuracy_on_review:.3f}")
    print(f"  Recovery (RAG wrong -> agent right):   {n_recovery}/{n} ({n_recovery/n:.1%})")
    print(f"  Regression (RAG right -> agent wrong): {n_regression}/{n} ({n_regression/n:.1%})  <- critical failure mode")
    print(f"  No change:                             {n_no_change}/{n} ({n_no_change/n:.1%})")
    print(f"  Avg steps per case: {avg_steps:.2f}")
    print(f"  Stopped-reason distribution: {stopped_reasons}")
    print(f"  Total cost: ${total_cost:.4f}")

    # Net effect on the full 150-case sample if the agent replaced the
    # RAG prediction on every REVIEW case.
    overall_rag_correct = sum(p.predicted_label.value == gold_by_key[(p.doc_id, p.hypothesis_id)]
                               for p in rag.predictions)
    overall_with_agent = overall_rag_correct - n_regression + n_recovery
    print(f"\n  Overall accuracy without agent: {overall_rag_correct}/{len(rag.predictions)} "
          f"({overall_rag_correct/len(rag.predictions):.3f})")
    print(f"  Overall accuracy with agent:     {overall_with_agent}/{len(rag.predictions)} "
          f"({overall_with_agent/len(rag.predictions):.3f})")

    output = {
        "n_review_cases": n, "rag_accuracy_on_review": rag_accuracy_on_review,
        "agent_accuracy_on_review": agent_accuracy_on_review,
        "n_recovery": n_recovery, "n_regression": n_regression, "n_no_change": n_no_change,
        "avg_steps": avg_steps, "stopped_reasons": stopped_reasons, "total_cost_usd": total_cost,
        "overall_rag_correct": overall_rag_correct, "overall_with_agent": overall_with_agent,
        "n_total_sample": len(rag.predictions),
        "outcomes": outcomes,
    }
    Path("data/agent_experiment.json").write_text(json.dumps(output, indent=2))
    print("\nWrote data/agent_experiment.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
