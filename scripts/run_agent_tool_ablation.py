#!/usr/bin/env python3
"""
Agent tool ablation - does the agent need all 5 tools (T028), or do the
two rarely-used ones (find_defined_term, search_exceptions - 2 uses
each across 67 real REVIEW cases, T030) actually pull their weight?

Re-runs the identical 67 REVIEW-routed cases with only 3 tools enabled
(search_clauses, retrieve_more_evidence, inspect_neighbouring_clauses -
the ones that were actually used more than twice), using a matching
3-tool prompt (prompts/agent_step_v1_3tools.txt) so the model isn't
told about tools it can't call. Compares net outcome against the
already-recorded 5-tool result (data/agent_experiment.json).
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

THREE_TOOLS = {"search_clauses", "retrieve_more_evidence", "inspect_neighbouring_clauses"}
THREE_TOOL_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "agent_step_v1_3tools.txt"


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
    print(f"Model: {gateway.model} | tools enabled: {sorted(THREE_TOOLS)}\n")

    review_cases = []
    for pred in rag.predictions:
        rule_label = classify_by_keywords(pred.hypothesis_id, doc_by_id[pred.doc_id].text)
        decision = route(self_confidence=pred.confidence, rule_agrees=(rule_label == pred.predicted_label.value))
        if decision.route == Route.REVIEW:
            review_cases.append(pred)

    print(f"{len(review_cases)} REVIEW-routed cases (identical set to the 5-tool run)\n")

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
                            doc_id=pred.doc_id, allowed_actions=THREE_TOOLS, prompt_path=THREE_TOOL_PROMPT)
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
        })

        elapsed = time.time() - start
        print(f"[{i}/{len(review_cases)}] {outcome:10} rag={pred.predicted_label.value:13} "
              f"agent={result.label:13} gold={gold_label:13} steps={len(result.trace.steps)} "
              f"({result.trace.stopped_reason}, ${result.cost_usd:.5f}, {elapsed:.0f}s elapsed)")

    n = len(outcomes)
    n_recovery = sum(o["outcome"] == "recovery" for o in outcomes)
    n_regression = sum(o["outcome"] == "regression" for o in outcomes)
    agent_accuracy_on_review = sum(o["agent_correct"] for o in outcomes) / n

    overall_rag_correct = sum(p.predicted_label.value == gold_by_key[(p.doc_id, p.hypothesis_id)]
                               for p in rag.predictions)
    overall_with_3tool_agent = overall_rag_correct - n_regression + n_recovery

    print(f"\n--- 3-tool ablation ({n} REVIEW-routed cases) ---")
    print(f"  Agent accuracy on REVIEW subset: {agent_accuracy_on_review:.3f}  (5-tool run: 0.851)")
    print(f"  Recovery:   {n_recovery}/{n} ({n_recovery/n:.1%})  (5-tool run: 6/67, 9.0%)")
    print(f"  Regression: {n_regression}/{n} ({n_regression/n:.1%})  (5-tool run: 3/67, 4.5%)")
    print(f"  Total cost: ${total_cost:.4f}  (5-tool run: $0.0169)")
    print(f"\n  Overall accuracy with 3-tool agent: {overall_with_3tool_agent}/{len(rag.predictions)} "
          f"({overall_with_3tool_agent/len(rag.predictions):.3f})  (5-tool run: 135/150, 0.900)")

    Path("data/agent_tool_ablation.json").write_text(json.dumps({
        "n_review_cases": n, "agent_accuracy_on_review": agent_accuracy_on_review,
        "n_recovery": n_recovery, "n_regression": n_regression, "total_cost_usd": total_cost,
        "overall_with_3tool_agent": overall_with_3tool_agent, "n_total_sample": len(rag.predictions),
        "outcomes": outcomes,
    }, indent=2))
    print("\nWrote data/agent_tool_ablation.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
