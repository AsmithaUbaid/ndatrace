#!/usr/bin/env python3
"""
Hybrid architecture: RAG for most cases, full-context only as a fallback
on the cases pipeline/confidence.py routes to REVIEW (rule-baseline
disagrees with RAG) - rather than either pure RAG+agent or paying
full-context's cost on every case.

Motivated directly by pushback on T015's full-context result: full-
context's win (91.3%) is likely an artifact of this dataset's short,
curated NDAs (~2,300 tokens avg) - real documents could be longer and
noisier, where feeding the WHOLE document dilutes the signal with
irrelevant content. This hybrid keeps the large majority of cases on
cheap, targeted RAG, and only pays full-context's cost on the minority
where signals actually disagree - limiting exposure to that risk while
still capturing most of full-context's accuracy advantage.

Entirely free to compute - reuses three already-collected real result
sets (run_T018_prompt_v2.jsonl for RAG, run_B03_full_context.jsonl for
full-context, data/agent_experiment.json for which cases were routed to
REVIEW), no new API calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from scripts.run_oracle_experiment import SEED, stratified_sample


def main() -> int:
    harness = EvaluationHarness()
    rag = harness.load_results("runs/run_T018_prompt_v2.jsonl")[0]
    fullctx = harness.load_results("runs/run_B03_full_context.jsonl")[0]
    agent_data = json.loads(Path("data/agent_experiment.json").read_text())
    review_keys = {(o["doc_id"], o["hypothesis_id"]) for o in agent_data["outcomes"]}

    dataset = parse_contractnli_file(settings.data_path / "dev.json")
    sample = stratified_sample(dataset, 150, SEED)
    gold_by_key = {(doc.doc_id, ann.hypothesis_id): ann.label for doc, ann in sample}

    fc_by_key = {(p.doc_id, p.hypothesis_id): p.predicted_label.value for p in fullctx.predictions}
    fc_cost_by_key = {
        (p.doc_id, p.hypothesis_id): (p.cost_latency.cost_usd if p.cost_latency else 0.0)
        for p in fullctx.predictions
    }
    rag_cost_by_key = {
        (p.doc_id, p.hypothesis_id): (p.cost_latency.cost_usd if p.cost_latency else 0.0)
        for p in rag.predictions
    }

    hybrid_correct = 0
    hybrid_cost = 0.0
    n_fullctx_calls = 0

    for p in rag.predictions:
        key = (p.doc_id, p.hypothesis_id)
        hybrid_cost += rag_cost_by_key[key]  # RAG always runs first (routing needs its output)
        if key in review_keys:
            pred = fc_by_key[key]
            hybrid_cost += fc_cost_by_key[key]
            n_fullctx_calls += 1
        else:
            pred = p.predicted_label.value
        if pred == gold_by_key[key]:
            hybrid_correct += 1

    n = len(rag.predictions)
    print(f"Hybrid (RAG for {n - n_fullctx_calls}/{n} easy cases, "
          f"full-context fallback for {n_fullctx_calls}/{n} REVIEW cases)")
    print(f"  Accuracy: {hybrid_correct}/{n} = {hybrid_correct/n:.3f}")
    print(f"  Total cost: ${hybrid_cost:.4f} (RAG-only would be ~$0.0216, "
          f"full-context-on-everything would be ~$0.0506)")
    print(f"  Full-context calls needed: {n_fullctx_calls}/{n} ({n_fullctx_calls/n:.1%})")

    print("\n--- Comparison ---")
    print(f"  RAG alone:                       88.0%")
    print(f"  RAG+agent:                        90.0%")
    print(f"  RAG + full-context fallback:      {hybrid_correct/n:.1%}  <- this experiment")
    print(f"  Full-context alone:               91.3%")

    Path("data/hybrid_fallback_experiment.json").write_text(json.dumps({
        "accuracy": hybrid_correct / n, "total_cost_usd": hybrid_cost,
        "n_fullctx_calls": n_fullctx_calls, "n_total": n,
    }, indent=2))
    print("\nWrote data/hybrid_fallback_experiment.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
