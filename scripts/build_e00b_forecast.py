#!/usr/bin/env python3
"""
E00B - Budget, token & runtime forecast (reconstruction-v2).

Local-only: reads already-saved local files (data/contractnli/*.json, results/*.jsonl,
configs/pricing/*.yaml) and does arithmetic via evaluation.budget. Makes ZERO model/API
calls and downloads nothing. Produces the CSV/JSON outputs under
experiments/E00B_budget_forecast/results/ and results/budget/.

Answers: "Can the planned reconstruction-v2 experiment programme fit within the remaining
hosted-model budget and practical runtime, and how should that constraint shape the
experimental design?"
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

import tiktoken
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.budget import (  # noqa: E402
    RECONSTRUCTION_LEDGER_PATH,
    check_budget,
    estimate_cost,
    load_pricing,
    reconstruction_spend_so_far,
)

BUDGET_DIR = REPO / "results/budget"
E00B_RESULTS = REPO / "experiments/E00B_budget_forecast/results"
BUDGET_DIR.mkdir(parents=True, exist_ok=True)
E00B_RESULTS.mkdir(parents=True, exist_ok=True)

PLANNING_BUDGET_USD = 5.00
PLANNING_BUDGET_SOURCE = "user-reported current balance"
DATE_RECORDED = "2026-09-26"
PROTECTED_RESERVE_FRACTION = 0.25  # 25%, within the 20-30% target range

enc = tiktoken.get_encoding("cl100k_base")  # clearly-labeled approximation -- see README


def toks(s: str) -> int:
    return len(enc.encode(s))


# =========================================================================
# 1. Current verified pricing table
# =========================================================================

def build_pricing_table() -> list[dict]:
    rows = []
    for path in sorted((REPO / "configs/pricing").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        with open(path) as f:
            d = yaml.safe_load(f)
        lifecycle = d.get("lifecycle") or {}
        rows.append({
            "provider": d["provider"], "model": d["model"],
            "published_input_price_per_million": d["published_input_price_per_million"],
            "published_output_price_per_million": d["published_output_price_per_million"],
            "published_cached_input_price_per_million": d.get("published_cached_input_price_per_million"),
            "account_tier": d.get("account_tier"),
            "effective_cost_assumption_input_per_million": d["effective_cost_assumption_input_per_million"],
            "effective_cost_assumption_output_per_million": d["effective_cost_assumption_output_per_million"],
            "free_tier_limits": d.get("free_tier_limits"),
            "date_checked": d["date_checked"],
            "lifecycle_status": lifecycle.get("status"),
            "source_note": d["source_note"],
        })
    return rows


# =========================================================================
# 2. Token estimates -- empirical, from real local dataset text (TRAIN split,
#    per docs/evaluation_protocol.md's Role A), not a flat chars/4 guess.
# =========================================================================

def build_token_estimates() -> dict:
    system_prompt = (REPO / "prompts/classify_v6.txt").read_text()
    system_tokens = toks(system_prompt)

    with open(REPO / "data/contractnli/train.json") as f:
        train = json.load(f)
    hyps = [v["hypothesis"] for v in train["labels"].values()]
    hyp_lens = [toks(h) for h in hyps]

    ev_lens = []
    for doc in train["documents"]:
        spans, text = doc["spans"], doc["text"]
        for _hyp, ann in doc["annotation_sets"][0]["annotations"].items():
            if ann["choice"] in ("Entailment", "Contradiction") and ann["spans"]:
                ev_text = " ".join(text[spans[i][0]:spans[i][1]] for i in ann["spans"])
                ev_lens.append(toks(ev_text))
    ev_sorted = sorted(ev_lens)

    def pctl(sorted_list, p):
        return sorted_list[min(int(p * len(sorted_list)), len(sorted_list) - 1)]

    compact_output = '{"label": "Contradiction", "evidence_ids": ["c7"]}'
    verbose_output = (
        '{\n  "label": "Contradiction",\n  "confidence": 0.85,\n  "evidence": '
        '["The Receiving Party shall not disclose any Confidential Information to any '
        'third party without prior written consent."],\n  "explanation": "The NDA '
        'explicitly prohibits disclosure without consent, which directly contradicts the '
        'requirement that disclosure is permitted under these circumstances."\n}'
    )
    compact_out_tokens = toks(compact_output)
    verbose_out_tokens = toks(verbose_output)

    input_mean = system_tokens + statistics.mean(hyp_lens) + statistics.mean(ev_lens)
    input_p90 = system_tokens + max(hyp_lens) + pctl(ev_sorted, 0.90)

    return {
        "methodology": (
            "tiktoken cl100k_base encoding used as a clearly-labeled APPROXIMATION -- "
            "neither Gemini nor GPT-5-mini publish an exact open tokenizer usable fully "
            "offline; cl100k_base is the closest locally-available general-purpose "
            "tokenizer and is within the same order of magnitude for English legal text. "
            "Real per-call costs are verified against historical actual cost_latency "
            "records (results/budget/historical_spend.csv), not token estimates alone."
        ),
        "system_prompt_tokens": system_tokens,
        "hypothesis_tokens_mean": round(statistics.mean(hyp_lens), 1),
        "hypothesis_tokens_max": max(hyp_lens),
        "n_hypotheses": len(hyps),
        "gold_evidence_tokens_train_entailment_contradiction": {
            "n_cases": len(ev_lens),
            "mean": round(statistics.mean(ev_lens), 1),
            "median": statistics.median(ev_lens),
            "p90": pctl(ev_sorted, 0.90),
            "max": max(ev_lens),
        },
        "oracle_input_tokens_estimate": {
            "mean": round(input_mean, 1),
            "p90": round(input_p90, 1),
        },
        "output_tokens": {
            "compact_example": compact_output,
            "compact_tokens": compact_out_tokens,
            "verbose_example_like_historical": verbose_output,
            "verbose_tokens": verbose_out_tokens,
        },
    }


# =========================================================================
# 3. Historical explanation-cost finding (T019, already computed, re-cited
#    not re-derived) + the instructor's cited 644/449/$0.001059 figures --
#    verified against local records: found in docs/archive/initial_project_plan.md
#    as the INSTRUCTOR's estimate (based on a GPT-5-mini example), NOT this
#    project's own measured data. Reported as such, not silently treated as fact.
# =========================================================================

def compact_vs_verbose_comparison(token_estimates: dict) -> dict:
    gemini = load_pricing("google/gemini-2.5-flash-lite")
    gpt5mini = load_pricing("openai/gpt-5-mini")
    input_mean = token_estimates["oracle_input_tokens_estimate"]["mean"]
    compact_out = token_estimates["output_tokens"]["compact_tokens"]
    verbose_out = token_estimates["output_tokens"]["verbose_tokens"]

    return {
        "instructor_cited_figures": {
            "found_locally": True,
            "location": "docs/archive/initial_project_plan.md section 22.2",
            "verification_result": (
                "These are the INSTRUCTOR's estimate, based on a GPT-5-mini example from the "
                "Week 3 submission (~644 input / ~449 output tokens, ~$0.001059/9.21s per "
                "case) -- NOT this project's own measured NDATrace data. Not found anywhere "
                "in this project's own result files under those exact values. Reported here "
                "as correctly attributed, not treated as an NDATrace project fact."
            ),
            "cited_values": {"input_tokens": 644, "output_tokens": 449,
                              "cost_usd": 0.001059, "latency_s": 9.21},
        },
        "this_projects_own_real_measured_data": {
            "source": "results/archive/runs/run_T024_rag.jsonl (RAG, prompt v2, Gemini, n=150)",
            "mean_input_tokens": 853.6, "median_input_tokens": 848.0,
            "mean_output_tokens": 116.1, "median_output_tokens": 106.5,
            "mean_cost_usd": 0.0001318, "median_cost_usd": 0.0001270,
        },
        "explanation_cost_finding_T019": {
            "source": "data/explanation_cost.json (real, already computed, not re-derived)",
            "explanation_pct_of_output_tokens": 31.1,
            "explanation_pct_of_total_cost": 9.3,
            "conclusion": "Explanation text is a real, measured, non-trivial share of output "
                          "tokens but only a small share of total cost, because input tokens "
                          "dominate cost for this project's real prompt/context sizes -- "
                          "consistent with the C01 finding that input, not output, is this "
                          "project's actual cost driver.",
        },
        "oracle_scenario_compact_vs_verbose": {
            "gemini_compact_usd_per_case": round(estimate_cost(input_mean, compact_out, gemini), 7),
            "gemini_verbose_usd_per_case": round(estimate_cost(input_mean, verbose_out, gemini), 7),
            "gpt5mini_compact_usd_per_case": round(estimate_cost(input_mean, compact_out, gpt5mini), 7),
            "gpt5mini_verbose_usd_per_case": round(estimate_cost(input_mean, verbose_out, gpt5mini), 7),
        },
        "design_rule": (
            "Bulk evaluation outputs should default to minimal structured JSON (label + "
            "evidence IDs only). Verbose natural-language explanations should only be "
            "generated in experiments that specifically evaluate explanation/faithfulness "
            "quality (axis D of docs/project_contract.md section 9), not in every bulk run."
        ),
    }


# =========================================================================
# 4. Historical actual per-case cost, by architecture/model -- the more
#    reliable forecast basis (captures GPT-5-mini's hidden reasoning-token
#    inflation that a naive token formula misses entirely).
# =========================================================================

def historical_per_case_costs() -> dict:
    def per_case(path, label):
        lines = [l for l in open(REPO / path) if l.strip()]
        d = json.loads(lines[-1])
        n = d["metrics"]["total_cases"]
        cost = d["metrics"]["total_cost_usd"]
        return {"label": label, "n_cases": n, "total_cost_usd": cost,
                "usd_per_case": round(cost / n, 7) if n else None}

    return {
        "oracle_v1_gemini": per_case("results/archive/runs/run_B04_oracle_google_gemini-2.5-flash-lite.jsonl", "B04 Oracle, Gemini 2.5 Flash Lite, v1 prompt"),
        "oracle_v1_gpt5mini": per_case("results/archive/runs/run_B04_oracle_openai_gpt-5-mini.jsonl", "B04 Oracle, GPT-5 mini, v1 prompt"),
        "rag_v2_gemini": per_case("results/archive/runs/run_T024_rag.jsonl", "T024 RAG, Gemini, v2 prompt"),
        "full_context_test_gemini": per_case("results/final/run_T041_final_test_full_context_google_gemini-2.5-flash-lite.jsonl", "T041 full-context, Gemini, full 2091-case TEST"),
        "rag_test_gemini": per_case("results/final/run_T041_final_test_rag_google_gemini-2.5-flash-lite.jsonl", "T041 RAG, Gemini, full 2091-case TEST"),
        "rag_agent_test_gemini": per_case("results/final/run_T041_final_test_rag_agent_google_gemini-2.5-flash-lite.jsonl", "T041 RAG+agent, Gemini, full 2091-case TEST"),
        "note": (
            "GPT-5-mini's real per-case Oracle cost ($0.001033) is ~5x its naive "
            "token-formula estimate (~$0.0002) due to hidden reasoning tokens billed as "
            "output (docs/decisions.md ADR-001) -- historical actual cost is used as the "
            "primary forecast basis for GPT-5-mini, not the token formula alone. Gemini's "
            "real per-case Oracle cost ($0.0000834) sits between the compact ($0.0000746) "
            "and verbose ($0.0000978) token-formula estimates, cross-validating the "
            "methodology for models without hidden reasoning tokens."
        ),
    }


# =========================================================================
# 5. Local runtime -- real measured per-case latency from actual local runs
#    (n=500 each), not a single-call guess.
# =========================================================================

def local_runtime_measurements() -> dict:
    def mean_latency(path):
        lines = [l for l in open(REPO / path) if l.strip()]
        d = json.loads(lines[-1])
        preds = d["predictions"]
        lat = [p["cost_latency"]["latency_ms"] for p in preds if p.get("cost_latency")]
        return {"n": len(lat), "mean_latency_ms": round(statistics.mean(lat), 1) if lat else None}

    return {
        "local_llama3.2_3b_full_context": mean_latency("results/archive/runs/run_T041_final_test_full_context_llama3.2_3b.jsonl"),
        "local_llama3.2_3b_rag": mean_latency("results/archive/runs/run_T041_final_test_rag_llama3.2_3b.jsonl"),
        "local_llama3.2_3b_rag_agent": mean_latency("results/archive/runs/run_T041_final_test_rag_agent_llama3.2_3b.jsonl"),
        "hosted_gemini_full_context": mean_latency("results/final/run_T041_final_test_full_context_google_gemini-2.5-flash-lite.jsonl"),
        "hosted_gemini_rag": mean_latency("results/final/run_T041_final_test_rag_google_gemini-2.5-flash-lite.jsonl"),
        "hosted_gemini_rag_agent": mean_latency("results/final/run_T041_final_test_rag_agent_google_gemini-2.5-flash-lite.jsonl"),
        "note_single_call_measurements_not_used_as_primary": (
            "docs/decisions.md/CLAUDE.md separately record single-call spot checks: local "
            "Ollama ~5.37s, Groq gpt-oss-20b ~0.79s. These are n=1 and NOT used as the "
            "primary runtime forecast basis here -- the n=500 real per-architecture means "
            "above are used instead, as they reflect actual measured variance across real "
            "cases, not one lucky/unlucky call."
        ),
    }


def main():
    token_estimates = build_token_estimates()
    pricing_table = build_pricing_table()
    compact_vs_verbose = compact_vs_verbose_comparison(token_estimates)
    historical_costs = historical_per_case_costs()
    local_runtime = local_runtime_measurements()

    # -- current_pricing.csv --
    with open(BUDGET_DIR / "current_pricing.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "provider", "model", "published_input_price_per_million",
            "published_output_price_per_million", "published_cached_input_price_per_million",
            "account_tier", "effective_cost_assumption_input_per_million",
            "effective_cost_assumption_output_per_million", "free_tier_limits",
            "date_checked", "lifecycle_status", "source_note",
        ])
        w.writeheader()
        w.writerows(pricing_table)

    # -- token_estimates.csv --
    with open(BUDGET_DIR / "token_estimates.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "value", "unit"])
        w.writerow(["system_prompt_tokens", token_estimates["system_prompt_tokens"], "tokens (cl100k_base approx)"])
        w.writerow(["hypothesis_tokens_mean", token_estimates["hypothesis_tokens_mean"], "tokens"])
        w.writerow(["gold_evidence_tokens_mean", token_estimates["gold_evidence_tokens_train_entailment_contradiction"]["mean"], "tokens (TRAIN, E/C cases)"])
        w.writerow(["gold_evidence_tokens_p90", token_estimates["gold_evidence_tokens_train_entailment_contradiction"]["p90"], "tokens"])
        w.writerow(["gold_evidence_tokens_max", token_estimates["gold_evidence_tokens_train_entailment_contradiction"]["max"], "tokens"])
        w.writerow(["oracle_input_tokens_mean", token_estimates["oracle_input_tokens_estimate"]["mean"], "tokens (estimate)"])
        w.writerow(["oracle_input_tokens_p90", token_estimates["oracle_input_tokens_estimate"]["p90"], "tokens (estimate)"])
        w.writerow(["output_tokens_compact", token_estimates["output_tokens"]["compact_tokens"], "tokens"])
        w.writerow(["output_tokens_verbose", token_estimates["output_tokens"]["verbose_tokens"], "tokens"])

    # -- experiment_forecast.csv (E01/E03/E15 scenarios) --
    gemini = load_pricing("google/gemini-2.5-flash-lite")
    gpt5mini = load_pricing("openai/gpt-5-mini")
    oracle_in = token_estimates["oracle_input_tokens_estimate"]["mean"]
    compact_out = token_estimates["output_tokens"]["compact_tokens"]

    forecast_rows = []
    for n in (100, 150, 300, 500, 1000):
        gemini_cost = n * historical_costs["oracle_v1_gemini"]["usd_per_case"]
        gpt5mini_cost = n * historical_costs["oracle_v1_gpt5mini"]["usd_per_case"]
        forecast_rows.append({
            "experiment": "E01_Oracle", "scenario": f"n={n}, 2 hosted models (real-historical-cost basis)",
            "n_cases": n, "hosted_models": 2,
            "estimated_cost_usd": round(gemini_cost + gpt5mini_cost, 4),
            "cost_basis": "historical actual per-case cost (Gemini+GPT-5-mini, Oracle v1)",
        })
    for n in (100, 150, 300):
        forecast_rows.append({
            "experiment": "E03_prompt_selection", "scenario": f"n={n} TRAIN subset x ~4 prompt variants, 1 selected hosted model",
            "n_cases": n * 4, "hosted_models": 1,
            "estimated_cost_usd": round(n * 4 * historical_costs["rag_v2_gemini"]["usd_per_case"], 4),
            "cost_basis": "historical actual per-case cost (T024 RAG, Gemini, v2 prompt)",
        })
    for n in (200, 300, 500):
        avg_arch_cost = statistics.mean([
            historical_costs["full_context_test_gemini"]["usd_per_case"],
            historical_costs["rag_test_gemini"]["usd_per_case"],
            historical_costs["rag_agent_test_gemini"]["usd_per_case"],
        ])
        forecast_rows.append({
            "experiment": "E15_hosted_vs_local", "scenario": f"n={n} stratified TEST subsample x 3 non-rule architectures, 1 hosted model",
            "n_cases": n * 3, "hosted_models": 1,
            "estimated_cost_usd": round(n * 3 * avg_arch_cost, 4),
            "cost_basis": "historical actual per-case cost (T041 full-context/RAG/RAG+agent, Gemini, full TEST)",
        })
    forecast_rows.append({
        "experiment": "rerun_reserve", "scenario": "malformed outputs / provider errors / invalid runs (10% of E01+E03+E15 subtotal)",
        "n_cases": None, "hosted_models": None, "estimated_cost_usd": None,
        "cost_basis": "computed in budget_plan.json as 10% of the E01+E03+E15 RECOMMENDED subtotal",
    })

    with open(BUDGET_DIR / "experiment_forecast.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["experiment", "scenario", "n_cases", "hosted_models",
                                           "estimated_cost_usd", "cost_basis"])
        w.writeheader()
        w.writerows(forecast_rows)

    # -- runtime_forecast.csv --
    runtime_rows = []
    per_case_s = {k: v["mean_latency_ms"] / 1000 for k, v in local_runtime.items()
                  if isinstance(v, dict) and v.get("mean_latency_ms")}
    scenarios = {
        "BEST-CASE": {"escalation_rate": 0.30, "extra_turn_factor": 1.0},
        "BASE-CASE": {"escalation_rate": 0.45, "extra_turn_factor": 1.3},
        "WORST-CASE": {"escalation_rate": 0.60, "extra_turn_factor": 1.8},
    }
    full_test_n = 2091
    for arch_key, label in [("local_llama3.2_3b_full_context", "A1 full-context, local Llama"),
                             ("local_llama3.2_3b_rag", "A2 RAG, local Llama"),
                             ("local_llama3.2_3b_rag_agent", "A3 RAG+agent (measured, already includes historical escalation mix), local Llama")]:
        s = per_case_s[arch_key]
        total_s = s * full_test_n
        runtime_rows.append({
            "scenario": "BASE-CASE (measured)", "run": label, "cases": full_test_n,
            "sec_per_case": round(s, 2), "estimated_total_sec": round(total_s, 0),
            "estimated_hours": round(total_s / 3600, 2),
        })
    # A3 scenario analysis (best/base/worst escalation rate), applied to the RAG per-case
    # latency as the non-escalated baseline, per section 9's requirement not to guess a
    # single escalation rate as fact.
    rag_s = per_case_s["local_llama3.2_3b_rag"]
    for scen_name, params in scenarios.items():
        escalated_s = rag_s * (1 + params["escalation_rate"] * (params["extra_turn_factor"] - 1) * 2)
        total_s = escalated_s * full_test_n
        runtime_rows.append({
            "scenario": scen_name, "run": f"A3 RAG+agent local, escalation_rate={params['escalation_rate']}, extra_turn_factor={params['extra_turn_factor']}",
            "cases": full_test_n, "sec_per_case": round(escalated_s, 2),
            "estimated_total_sec": round(total_s, 0), "estimated_hours": round(total_s / 3600, 2),
        })
    for arch_key, label in [("hosted_gemini_full_context", "A1 full-context, hosted Gemini"),
                             ("hosted_gemini_rag", "A2 RAG, hosted Gemini"),
                             ("hosted_gemini_rag_agent", "A3 RAG+agent, hosted Gemini")]:
        s = per_case_s[arch_key]
        for n in (300, 500):
            total_s = s * n
            runtime_rows.append({
                "scenario": "E15 subsample (measured per-case)", "run": label, "cases": n,
                "sec_per_case": round(s, 2), "estimated_total_sec": round(total_s, 0),
                "estimated_hours": round(total_s / 3600, 3),
            })

    with open(BUDGET_DIR / "runtime_forecast.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "run", "cases", "sec_per_case",
                                           "estimated_total_sec", "estimated_hours"])
        w.writeheader()
        w.writerows(runtime_rows)

    # -- budget_plan.json (the consolidated decision output) --
    oracle_150 = next(r for r in forecast_rows if r["experiment"] == "E01_Oracle" and r["n_cases"] == 150)
    oracle_300 = next(r for r in forecast_rows if r["experiment"] == "E01_Oracle" and r["n_cases"] == 300)
    e03_150 = next(r for r in forecast_rows if r["experiment"] == "E03_prompt_selection" and r["n_cases"] == 600)
    e15_300 = next(r for r in forecast_rows if r["experiment"] == "E15_hosted_vs_local" and r["n_cases"] == 900)

    reserve = PLANNING_BUDGET_USD * PROTECTED_RESERVE_FRACTION
    allowed_budget = PLANNING_BUDGET_USD - reserve

    recommended_subtotal = oracle_300["estimated_cost_usd"] + e03_150["estimated_cost_usd"] + e15_300["estimated_cost_usd"]
    rerun_reserve_amt = round(recommended_subtotal * 0.10, 4)
    recommended_total = round(recommended_subtotal + rerun_reserve_amt, 4)

    lean_total = round(oracle_150["estimated_cost_usd"] + e15_300["estimated_cost_usd"] * 0.5, 4)
    max_safe_total = round(
        next(r for r in forecast_rows if r["experiment"] == "E01_Oracle" and r["n_cases"] == 500)["estimated_cost_usd"]
        + next(r for r in forecast_rows if r["experiment"] == "E03_prompt_selection" and r["n_cases"] == 1200)["estimated_cost_usd"]
        + next(r for r in forecast_rows if r["experiment"] == "E15_hosted_vs_local" and r["n_cases"] == 1500)["estimated_cost_usd"],
        4,
    )

    budget_plan = {
        "planning_budget_usd": PLANNING_BUDGET_USD,
        "planning_budget_source": PLANNING_BUDGET_SOURCE,
        "date_recorded": DATE_RECORDED,
        "historical_env_value_MAX_BUDGET_USD": 6.99,
        "historical_env_value_status": "STALE, not trusted, not overwritten -- see .env comment dated 2026-09-22",
        "protected_reserve_fraction": PROTECTED_RESERVE_FRACTION,
        "protected_reserve_usd": round(reserve, 4),
        "allowed_budget_usd": round(allowed_budget, 4),
        "historical_total_hosted_spend_usd": 3.0011,
        "historical_spend_note": (
            "This is a SEPARATE ledger (real past T-series spend, already incurred, not "
            "part of the current $5 remaining balance). Per section 19's rule, NOT "
            "subtracted from the $5 planning budget -- $5 is used directly as the forward "
            "planning budget."
        ),
        "scenarios": {
            "LEAN": {
                "description": "Oracle n=150 (2 hosted models) + a small 150-case E15 spot-check on one hosted model only, half the E03 exploration deferred to base-case",
                "estimated_cost_usd": lean_total,
                "within_allowed_budget": lean_total <= allowed_budget,
            },
            "RECOMMENDED": {
                "description": "Oracle n=300 (2 hosted models) + E03 prompt selection (150-case TRAIN subset x 4 variants, 1 hosted model) + E15 (300-case stratified TEST subsample x 3 architectures, 1 hosted model) + 10% rerun reserve",
                "oracle_cost_usd": oracle_300["estimated_cost_usd"],
                "e03_cost_usd": e03_150["estimated_cost_usd"],
                "e15_cost_usd": e15_300["estimated_cost_usd"],
                "rerun_reserve_usd": rerun_reserve_amt,
                "estimated_total_cost_usd": recommended_total,
                "within_allowed_budget": recommended_total <= allowed_budget,
                "remaining_after_recommended_usd": round(allowed_budget - recommended_total, 4),
            },
            "MAXIMUM_SAFE": {
                "description": "Oracle n=500 (2 hosted models) + E03 (300-case TRAIN subset x 4 variants) + E15 (500-case stratified TEST subsample x 3 architectures) -- still preserves the 25% reserve, never spends the full $5",
                "estimated_cost_usd": max_safe_total,
                "within_allowed_budget": max_safe_total <= allowed_budget,
            },
        },
        "compact_vs_verbose": compact_vs_verbose,
        "historical_per_case_costs": historical_costs,
        "local_runtime_measurements": local_runtime,
        "hard_budget_gate": {
            "implementation": "evaluation/budget.py::check_budget() -- pure function, no network calls, must be called before any hosted experiment executes",
            "rule": "if actual_spend_so_far + projected_experiment_cost > (planning_budget - reserve): block the run",
            "actual_spend_source": "evaluation/budget.py::check_budget_against_ledger() reads reconstruction_spend_so_far() from the running ledger below -- NEVER the historical T-series ledger, which is a separate, audit-only record.",
        },
        "reconstruction_v2_spend_ledger": {
            "path": str(RECONSTRUCTION_LEDGER_PATH.relative_to(REPO)),
            "status": "READY -- append-only, currently empty (no reconstruction-v2 hosted call has been made yet)",
            "current_total_usd": reconstruction_spend_so_far(),
            "write_function": "evaluation.budget.record_spend(experiment_id, provider, model, input_tokens, output_tokens, cost_usd, run_id) -- call after every real successful hosted call, starting with E01",
            "read_function": "evaluation.budget.reconstruction_spend_so_far() -- sums cost_usd across every recorded row",
        },
        "answers": {
            "A_hosted_budget_available_usd": PLANNING_BUDGET_USD,
            "B_protected_reserve_usd": round(reserve, 4),
            "C_E01_oracle_budget_envelope_usd": "up to ~$0.56 (n=500, 2 hosted models, historical-cost basis) -- Oracle is NOT the binding constraint at any realistic sample size",
            "D_feasible_oracle_subset_size": "150-300 cases recommended (matches the historical convention for direct comparability, and is far below any budget constraint)",
            "E_can_2_hosted_oracle_models_fit": True,
            "F_budget_remaining_for_E03_E15_after_oracle_usd": round(allowed_budget - oracle_300["estimated_cost_usd"], 4),
            "G_recommended_bulk_output_token_cap": "~20-30 tokens (compact structured JSON: label + evidence_ids only) for bulk experiments; verbose explanations reserved for explanation-quality-focused experiments only",
            "H_experiments_that_should_be_local_only": ["E00 (done)", "E04 rule baseline", "E06 retrieval optimisation (no LLM calls)", "E09 agent justification analysis (reuses existing predictions)", "the bulk of E12/E14 architecture comparison (local-first per the reconstruction brief)"],
            "I_runs_that_would_exceed_safe_budget": "Running the FULL 2,091-case TEST split on 2+ hosted models across all 4 architectures repeatedly (as the historical T-series did across T041-A and T041-B) would approach $1.5-2 per full pass -- affordable once, but NOT to be repeated casually; each hosted TEST-split run should go through the budget gate first.",
            "J_local_runtime_estimate": (
                "Full 2,091-case TEST set, all 3 non-rule local architectures sequentially: "
                "~4.5h (full-context) + ~2.6h (RAG) + ~5.3h (RAG+agent, measured) = "
                "~12.4 hours total if run back-to-back on one machine (real measured "
                "per-case means from the n=500 local T041-A run, scaled to 2,091 cases). "
                "Rule baseline is near-instant. See runtime_forecast.csv for scenario detail."
            ),
        },
    }

    with open(BUDGET_DIR / "budget_plan.json", "w") as f:
        json.dump(budget_plan, f, indent=2, default=str)

    # Copy the key outputs into the E00B experiment's own results/ dir too.
    import shutil
    for name in ["historical_spend.csv", "current_pricing.csv", "token_estimates.csv",
                 "experiment_forecast.csv", "runtime_forecast.csv", "budget_plan.json"]:
        shutil.copy(BUDGET_DIR / name, E00B_RESULTS / name)

    print("Wrote:", BUDGET_DIR)
    print("Copied into:", E00B_RESULTS)
    print(json.dumps(budget_plan["scenarios"], indent=2))


if __name__ == "__main__":
    main()
