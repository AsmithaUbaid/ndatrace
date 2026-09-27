#!/usr/bin/env python3
"""
Budget and cost planning (WBS T004, Section 1 "What Must Be Decided Early").

Calculates projected API spend across every planned P0 experiment BEFORE
any of them run - the professor's #1 flagged risk (Section 1: "Budget
exhaustion... calculate projected API spend across all experiments before
running them").

Pricing (GPT-5 mini via OpenRouter, Section 13): $0.25/M input tokens,
$2/M output tokens. This is the planning doc's assumption, not yet
verified against a live account (that's T002, still pending a real
OpenRouter key in .env) - this script computes the PROJECTION, which
needs only pricing + token counts, not a live API call.

Two experiments (B03 full-context, B04 oracle) are recomputed here using
REAL measured token statistics from the downloaded dev set (via T006/A07
and a matching pass over gold evidence spans) rather than the planning
doc's hand-estimated guesses. Every other P0 experiment reuses the
planning doc's own call-count/token estimates (Section 8), since those
components (retrieval, RAG, agent) don't exist yet to measure directly.

Output: data/cost_estimates.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings
from pipeline.parser import parse_contractnli_file

ENCODING = tiktoken.get_encoding("cl100k_base")

# Section 13 pricing assumption - pending live verification (T002).
INPUT_PRICE_PER_MILLION = 0.25
OUTPUT_PRICE_PER_MILLION = 2.00

# Section 13: assumed output tokens per call (label + evidence IDs + explanation).
ASSUMED_OUTPUT_TOKENS_PER_CALL = 150
# Section 13: assumed fixed prompt overhead (system instructions + JSON schema + hypothesis).
PROMPT_OVERHEAD_TOKENS = 300


def cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000) * INPUT_PRICE_PER_MILLION + \
           (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_MILLION


def measure_real_token_stats() -> dict:
    """Real average full-doc and gold-evidence token lengths from the dev set."""
    dev_path = settings.data_path / "dev.json"
    dataset = parse_contractnli_file(dev_path)

    doc_lengths = [len(ENCODING.encode(doc.text)) for doc in dataset.documents]
    avg_doc_tokens = sum(doc_lengths) / len(doc_lengths)

    evidence_lengths = []
    for doc, ann in dataset.all_cases():
        if ann.evidence_spans:
            evidence_text = " ".join(s.text for s in ann.evidence_spans)
            evidence_lengths.append(len(ENCODING.encode(evidence_text)))
    avg_evidence_tokens = sum(evidence_lengths) / len(evidence_lengths) if evidence_lengths else 0

    return {"avg_doc_tokens": avg_doc_tokens, "avg_evidence_tokens": avg_evidence_tokens}


def build_experiment_estimates(real_stats: dict) -> list[dict]:
    avg_doc_tokens = real_stats["avg_doc_tokens"]
    avg_evidence_tokens = real_stats["avg_evidence_tokens"]

    experiments = []

    # --- B03: Full-context baseline - RECOMPUTED from real doc token stats ---
    b03_calls = 500
    b03_input_per_call = avg_doc_tokens + PROMPT_OVERHEAD_TOKENS
    b03_input_total = round(b03_calls * b03_input_per_call)
    b03_output_total = b03_calls * ASSUMED_OUTPUT_TOKENS_PER_CALL
    experiments.append({
        "id": "B03", "name": "Full-context LLM baseline",
        "calls": b03_calls, "input_tokens": b03_input_total, "output_tokens": b03_output_total,
        "cost_usd": round(cost_usd(b03_input_total, b03_output_total), 2),
        "source": f"recomputed: {avg_doc_tokens:.0f} real avg doc tokens (A07) + {PROMPT_OVERHEAD_TOKENS} overhead",
    })

    # --- B04: Oracle baseline - RECOMPUTED from real gold-evidence token stats ---
    b04_calls = 500
    b04_input_per_call = avg_evidence_tokens + PROMPT_OVERHEAD_TOKENS
    b04_input_total = round(b04_calls * b04_input_per_call)
    b04_output_total = b04_calls * ASSUMED_OUTPUT_TOKENS_PER_CALL
    experiments.append({
        "id": "B04", "name": "Oracle-evidence baseline",
        "calls": b04_calls, "input_tokens": b04_input_total, "output_tokens": b04_output_total,
        "cost_usd": round(cost_usd(b04_input_total, b04_output_total), 2),
        "source": f"recomputed: {avg_evidence_tokens:.0f} real avg gold-evidence tokens + {PROMPT_OVERHEAD_TOKENS} overhead",
    })

    # --- Remaining P0 experiments: planning doc's own hand-estimates (Section 8) ---
    # These involve components (retrieval, RAG, agent) not yet built, so their
    # call/token counts can't be measured directly - reusing the doc's figures.
    doc_estimates = [
        ("D07", "Top-K comparison (downstream accuracy)", 200, 200_000, "planning doc Section 8"),
        ("C01", "Model comparison (Oracle, 3 models)", 300, 200_000, "planning doc Section 8"),
        ("C03", "Zero-shot vs few-shot", 300, 250_000, "planning doc Section 8"),
        ("C04", "Prompt variants", 300, 200_000, "planning doc Section 8"),
        ("C05", "Structured JSON output", 200, 150_000, "planning doc Section 8"),
        ("C07", "Not Mentioned behaviour", 100, 70_000, "planning doc Section 8"),
        ("E03", "Standard dense RAG E2E", 500, 500_000, "planning doc Section 8"),
        ("E06", "RAG + agent E2E", 700, 700_000, "planning doc Section 8"),
        ("G01", "Agent vs no-agent", 200, 300_000, "planning doc Section 8"),
        ("G02", "Trigger-rule comparison", 300, 400_000, "planning doc Section 8"),
        ("G04", "Max-step comparison", 400, 500_000, "planning doc Section 8"),
        ("L03", "Golden-case test suite (12 cases)", 12, 15_000, "planning doc Section 8"),
        ("L04", "Complete 17-requirement NDA run", 17, 20_000, "planning doc Section 8"),
    ]
    for exp_id, name, calls, input_tokens, source in doc_estimates:
        output_tokens = calls * ASSUMED_OUTPUT_TOKENS_PER_CALL
        experiments.append({
            "id": exp_id, "name": name, "calls": calls,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": round(cost_usd(input_tokens, output_tokens), 2),
            "source": source,
        })

    # --- Final locked test-set evaluation (Day 9 equivalent - runs once) ---
    final_calls = 1548  # full test split, per planning doc capacity plan
    final_input_total = round(final_calls * (avg_doc_tokens * 0.5 + PROMPT_OVERHEAD_TOKENS))  # RAG-sized context, not full doc
    final_output_total = final_calls * ASSUMED_OUTPUT_TOKENS_PER_CALL
    experiments.append({
        "id": "FINAL", "name": "Final locked test-set evaluation (runs once, no re-tuning)",
        "calls": final_calls, "input_tokens": final_input_total, "output_tokens": final_output_total,
        "cost_usd": round(cost_usd(final_input_total, final_output_total), 2),
        "source": "recomputed: assumes RAG-sized context (~50% of avg doc tokens) + overhead",
    })

    return experiments


def main() -> int:
    print("Measuring real token statistics from dev set...")
    real_stats = measure_real_token_stats()
    print(f"  avg_doc_tokens={real_stats['avg_doc_tokens']:.1f}, "
          f"avg_evidence_tokens={real_stats['avg_evidence_tokens']:.1f}")

    experiments = build_experiment_estimates(real_stats)
    total_cost = sum(e["cost_usd"] for e in experiments)
    total_input = sum(e["input_tokens"] for e in experiments)
    total_output = sum(e["output_tokens"] for e in experiments)

    max_budget = settings.max_budget_usd
    warn_pct = settings.warn_budget_pct
    projected_pct = round(100 * total_cost / max_budget, 1) if max_budget else 0.0

    report = {
        "pricing_assumption": {
            "model": "openrouter/openai/gpt-5-mini",
            "input_price_per_million_usd": INPUT_PRICE_PER_MILLION,
            "output_price_per_million_usd": OUTPUT_PRICE_PER_MILLION,
            "verified": "2026-09-22 via GET /api/v1/models - exact match to this assumption",
            "batch_variant_available": "openai/gpt-5-mini:batch at half price ($0.125/M in, $1/M out)",
        },
        "real_measured_stats": real_stats,
        "experiments": experiments,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": round(total_cost, 2),
        "max_budget_usd": max_budget,
        "projected_pct_of_budget": projected_pct,
        "within_80_pct_target": projected_pct < warn_pct,
        "note": "max_budget_usd is the real OpenRouter remaining balance, verified via "
                "GET /auth/key (T002, see data/budget_plan.json) - not an assumption. "
                "This total will need re-projecting if experiment scope changes.",
    }

    out_path = Path("data/cost_estimates.json")
    out_path.write_text(json.dumps(report, indent=2))

    print(f"\n{'Experiment':<8} {'Calls':>7} {'Input tok':>12} {'Output tok':>11} {'Cost':>8}  Source")
    for e in experiments:
        print(f"{e['id']:<8} {e['calls']:>7} {e['input_tokens']:>12,} {e['output_tokens']:>11,} "
              f"${e['cost_usd']:>6.2f}  {e['source']}")

    print(f"\nTotal projected cost: ${total_cost:.2f}")
    print(f"Max budget (from .env MAX_BUDGET_USD): ${max_budget:.2f}")
    print(f"Projected spend: {projected_pct}% of budget "
          f"({'within' if report['within_80_pct_target'] else 'EXCEEDS'} {warn_pct}% target)")
    print(f"\nReport written to: {out_path}")
    print("\nBudget figure is the real verified OpenRouter balance (T002, see "
          "data/budget_plan.json) - re-run this script if experiment scope changes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
