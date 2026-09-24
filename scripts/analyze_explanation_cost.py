#!/usr/bin/env python3
"""
Explanation cost analysis (WBS T019, C10) - measures explanation tokens
as a % of total output cost. Never done as its own task originally
(found as a real gap during a 2026-09-24 plan-vs-reality audit) - $0 to
run, since it's a pure re-analysis of already-saved predictions
(run_T018_prompt_v6.jsonl, the currently-adopted prompt/model), no new
API calls.

Method: tiktoken-count the `explanation` field of every saved prediction
(same encoding pipeline/chunker.py already uses project-wide), compare
against the real total output tokens and real total cost recorded for
that same prediction, using the real per-model output price
(pipeline/model_gateway.py's PRICING_PER_MILLION) to attribute a dollar
figure to the explanation specifically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.model_gateway import PRICING_PER_MILLION

ENCODING = tiktoken.get_encoding("cl100k_base")
RESULTS_FILE = "results/runs/run_T018_prompt_v6.jsonl"


def main() -> int:
    with open(RESULTS_FILE) as f:
        lines = [l for l in f if l.strip()]
    record = json.loads(lines[-1])
    model = record["config"]["model"]
    pricing = PRICING_PER_MILLION.get(model, {"input": 0.0, "output": 0.0})
    output_price_per_token = pricing["output"] / 1_000_000

    total_output_tokens = 0
    total_explanation_tokens = 0
    total_cost = 0.0
    total_explanation_cost = 0.0
    n = 0

    for pred in record["predictions"]:
        explanation = pred.get("explanation", "") or ""
        explanation_tokens = len(ENCODING.encode(explanation))
        cl = pred.get("cost_latency") or {}
        output_tokens = cl.get("tokens_out", 0) or 0
        cost = cl.get("cost_usd", 0.0) or 0.0

        total_explanation_tokens += explanation_tokens
        total_output_tokens += output_tokens
        total_cost += cost
        total_explanation_cost += explanation_tokens * output_price_per_token
        n += 1

    pct_of_output_tokens = (total_explanation_tokens / total_output_tokens * 100) if total_output_tokens else 0.0
    pct_of_total_cost = (total_explanation_cost / total_cost * 100) if total_cost else 0.0

    result = {
        "source": RESULTS_FILE,
        "model": model,
        "n_cases": n,
        "total_output_tokens": total_output_tokens,
        "total_explanation_tokens": total_explanation_tokens,
        "avg_explanation_tokens_per_case": round(total_explanation_tokens / n, 1) if n else 0.0,
        "explanation_pct_of_output_tokens": round(pct_of_output_tokens, 1),
        "total_cost_usd": round(total_cost, 6),
        "explanation_cost_usd": round(total_explanation_cost, 6),
        "explanation_pct_of_total_cost": round(pct_of_total_cost, 1),
    }
    print(json.dumps(result, indent=2))

    Path("data/explanation_cost.json").write_text(json.dumps(result, indent=2))
    print("\nWrote data/explanation_cost.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
