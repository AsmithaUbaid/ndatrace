#!/usr/bin/env python3
"""
E12A Stage A -- offline context-size, cost, budget-gate, and runtime forecast for the static
context expansion candidate (K=11) vs. the frozen control (top-5). Zero model calls.

Uses the ACTUAL message-construction path E08B used for A2 (classification_prompt_v1's
system_prompt + the same additive evidence instruction + the same "Retrieved NDA excerpts:"
wrapper), applied to both the control's and the candidate's retrieved chunks. cl100k_base token
estimates are calibrated against E08B's REAL OpenRouter-reported input_tokens per case (a
measured control-side ratio, applied to the candidate) rather than trusting raw cl100k counts.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import tiktoken

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.budget import check_budget_against_ledger, reconstruction_spend_so_far  # noqa: E402
from evaluation.prompt_selection import load_prompt_config  # noqa: E402

E07_DIR = REPO / "experiments/E07_standard_rag"
E08B_DIR = REPO / "experiments/E08B_stronger_model_diagnostic"
E12A_DIR = REPO / "experiments/E12A_static_context_expansion"

EVIDENCE_INSTRUCTION = (
    ' Also return the exact sentence(s) from the text that support your label, verbatim, as a '
    'list under "evidence". Return an empty list for NotMentioned.'
)
USER_TEMPLATE_A2 = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"

PLANNING_BUDGET_USD = 5.00
PROTECTED_RESERVE_FRACTION = 0.25
INPUT_PRICE_PER_MILLION = 0.25
OUTPUT_PRICE_PER_MILLION = 2.00

ENC = tiktoken.get_encoding("cl100k_base")


def _tokens(text: str) -> int:
    return len(ENC.encode(text))


def _stats(vals: list[float]) -> dict:
    s = sorted(vals)
    n = len(s)
    return {"mean": statistics.mean(s), "median": statistics.median(s),
            "p90": s[min(int(n * 0.9), n - 1)], "max": max(s)}


def main() -> int:
    cfg = load_prompt_config("p00")
    system_prompt = cfg["system_prompt"].rstrip() + "\n" + EVIDENCE_INSTRUCTION
    system_tokens = _tokens(system_prompt)

    ctrl = {c["case_id"]: c for c in json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
    cand_json = json.load(open(E12A_DIR / "TRAIN_ARCH_v1_RETRIEVED_static_context_candidate_v1.json"))
    cand = {c["case_id"]: c for c in cand_json["cases"]}
    manifest = json.load(open(REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"))
    hyp_by_case = {c["case_id"]: c["hypothesis_text"] for c in manifest["cases"]}
    e08b_cases = {json.loads(l)["case_id"]: json.loads(l)
                  for l in open(E08B_DIR / "results/run_E08B_A2_gpt5mini_train_cases.jsonl")}

    ctrl_total, ctrl_retrieved, cand_total, cand_retrieved = [], [], [], []
    ctrl_real_api_tokens, ctrl_est_tokens_for_ratio = [], []
    n_short_docs = 0

    for cid, hyp in hyp_by_case.items():
        ctrl_ctx = "\n\n---\n\n".join(ctrl[cid]["ranked_chunk_text"])
        cand_ctx = "\n\n---\n\n".join(cand[cid]["ranked_chunk_text"])
        ctrl_msg = USER_TEMPLATE_A2.format(hypothesis_text=hyp, context_text=ctrl_ctx)
        cand_msg = USER_TEMPLATE_A2.format(hypothesis_text=hyp, context_text=cand_ctx)

        ctrl_total.append(system_tokens + _tokens(ctrl_msg))
        cand_total.append(system_tokens + _tokens(cand_msg))
        ctrl_retrieved.append(_tokens(ctrl_ctx))
        cand_retrieved.append(_tokens(cand_ctx))

        real = e08b_cases[cid]["input_tokens"]
        ctrl_real_api_tokens.append(real)
        ctrl_est_tokens_for_ratio.append(system_tokens + _tokens(ctrl_msg))

        if len(cand[cid]["ranked_chunk_ids"]) < 11:
            n_short_docs += 1

    # Calibration: real OpenRouter-reported input tokens / cl100k estimate, measured on the
    # CONTROL (where both are known), then applied to the candidate estimate.
    calibration_ratio = sum(ctrl_real_api_tokens) / sum(ctrl_est_tokens_for_ratio)
    cand_total_calibrated = [t * calibration_ratio for t in cand_total]
    ctrl_total_calibrated = [t * calibration_ratio for t in ctrl_total]

    ctrl_stats = _stats(ctrl_total_calibrated)
    cand_stats = _stats(cand_total_calibrated)
    ctrl_real_stats = _stats(ctrl_real_api_tokens)

    print(f"Calibration ratio (real API input tokens / cl100k estimate, measured on control): {calibration_ratio:.4f}")
    print(f"\nCONTROL top-5 -- real API-reported input tokens (E08B): {json.dumps(ctrl_real_stats, indent=2)}")
    print(f"CONTROL top-5 -- calibrated estimate (sanity check vs real): {json.dumps(ctrl_stats, indent=2)}")
    print(f"CANDIDATE top-11 -- calibrated input tokens: {json.dumps(cand_stats, indent=2)}")
    print(f"\nRetrieved-text-only tokens (uncalibrated cl100k): control mean={statistics.mean(ctrl_retrieved):.1f}, "
          f"candidate mean={statistics.mean(cand_retrieved):.1f}")
    print(f"System-prompt tokens (cl100k): {system_tokens}")
    abs_increase = cand_stats["mean"] - ctrl_real_stats["mean"]
    pct_increase = abs_increase / ctrl_real_stats["mean"] * 100
    print(f"\nMean input-token increase (vs real control mean): +{abs_increase:.1f} tokens (+{pct_increase:.1f}%)")
    print(f"Cases where candidate has <11 chunks (short documents, fewer than 11 total): {n_short_docs}/150")

    # --- Context-window safety ---
    max_cand = cand_stats["max"]
    # UNVERIFIED ASSUMPTION, disclosed: 400,000 is the commonly cited GPT-5 mini context window,
    # but no repo file (pricing yaml, docs) records it and no provider-metadata call was made
    # (none authorized in Stage A). The safety conclusion does not depend on the exact figure --
    # the max candidate input (~3.3K tokens) is also far below any plausible modern-LLM window;
    # even against a pessimistic 16,384 (the smallest window this project has ever configured,
    # Ollama's num_ctx for Qwen -- irrelevant to a hosted call but a useful lower bound), headroom
    # would still be >80%.
    GPT5_MINI_CONTEXT_WINDOW = 400_000  # unverified, see comment above
    PESSIMISTIC_CONTEXT_WINDOW = 16_384
    print(f"\nMax candidate input tokens (calibrated): {max_cand:.0f}. "
          f"Assumed (UNVERIFIED) GPT-5 mini window: {GPT5_MINI_CONTEXT_WINDOW:,} -> "
          f"{(1 - max_cand / GPT5_MINI_CONTEXT_WINDOW) * 100:.2f}% headroom. "
          f"Against a pessimistic {PESSIMISTIC_CONTEXT_WINDOW:,} window: "
          f"{(1 - max_cand / PESSIMISTIC_CONTEXT_WINDOW) * 100:.1f}% headroom.")

    # --- Cost forecast ---
    e08b_summary = json.load(open(E08B_DIR / "results/run_E08B_A2_gpt5mini_train.json"))
    out_tok = e08b_summary["output_tokens"]
    expected_out = out_tok["mean"]
    conservative_out = out_tok["p90"]  # applied to every case -- a deliberately pessimistic bound
    n = 150

    def _cost(mean_in: float, mean_out: float) -> float:
        return n * (mean_in / 1e6 * INPUT_PRICE_PER_MILLION + mean_out / 1e6 * OUTPUT_PRICE_PER_MILLION)

    expected_cost = _cost(cand_stats["mean"], expected_out)
    conservative_cost = _cost(cand_stats["p90"], conservative_out)
    print(f"\nProjected candidate 150-case spend -- expected: ${expected_cost:.4f} "
          f"(mean/case ${expected_cost/n:.5f}), conservative: ${conservative_cost:.4f}")

    ledger = reconstruction_spend_so_far()
    print(f"Current real ledger: ${ledger:.4f}")
    print(f"Projected ledger after run -- expected: ${ledger + expected_cost:.4f}, "
          f"conservative: ${ledger + conservative_cost:.4f}")

    gate = check_budget_against_ledger(conservative_cost, PLANNING_BUDGET_USD, PROTECTED_RESERVE_FRACTION)
    print(f"\nBudget gate (conservative): {gate.reason}")
    print(f"GATE RESULT: {'PASS' if gate.allowed else 'FAIL'}")

    # --- Runtime ---
    e08b_latency = e08b_summary["generation_latency_ms"]
    # Output-token count dominates GPT-5-mini latency (hidden reasoning), input growth is a
    # secondary factor -- scale E08B's observed latency modestly by input growth as a rough,
    # disclosed estimate rather than assuming unchanged.
    latency_scale = 1 + (pct_increase / 100) * 0.25  # input contributes ~25% of latency (assumption)
    expected_runtime_s = n * (e08b_latency["mean"] / 1000) * latency_scale
    print(f"\nExpected runtime (150 calls, E08B mean latency scaled by input growth): {expected_runtime_s/60:.1f} min "
          f"(E08B's own full run took 18.5 min)")

    out = {
        "calibration_ratio": calibration_ratio,
        "system_prompt_tokens_cl100k": system_tokens,
        "control_real_api_input_tokens": ctrl_real_stats,
        "control_calibrated_estimate": ctrl_stats,
        "candidate_calibrated_input_tokens": cand_stats,
        "retrieved_text_tokens_cl100k": {"control_mean": statistics.mean(ctrl_retrieved),
                                          "candidate_mean": statistics.mean(cand_retrieved)},
        "mean_input_token_increase_abs": abs_increase, "mean_input_token_increase_pct": pct_increase,
        "cases_with_fewer_than_11_chunks": n_short_docs,
        "context_window_safety": {"max_candidate_input_tokens": max_cand,
                                    "assumed_unverified_gpt5_mini_context_window": GPT5_MINI_CONTEXT_WINDOW,
                                    "headroom_pct_vs_assumed_window": (1 - max_cand / GPT5_MINI_CONTEXT_WINDOW) * 100,
                                    "headroom_pct_vs_pessimistic_16k_window": (1 - max_cand / PESSIMISTIC_CONTEXT_WINDOW) * 100,
                                    "note": "GPT-5 mini's context window figure is an unverified assumption "
                                            "(no repo source, no provider-metadata call made in Stage A); "
                                            "safety conclusion holds even against a pessimistic 16K window."},
        "cost_forecast_usd": {"expected_total": expected_cost, "expected_mean_per_case": expected_cost / n,
                               "conservative_total": conservative_cost},
        "ledger_usd": ledger,
        "ledger_after_run_projection_usd": {"expected": ledger + expected_cost, "conservative": ledger + conservative_cost},
        "budget_gate": {"allowed": gate.allowed, "reason": gate.reason},
        "expected_runtime_minutes": expected_runtime_s / 60,
    }
    out_path = E12A_DIR / "results/pre_run_forecast.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
