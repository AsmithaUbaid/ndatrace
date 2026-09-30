#!/usr/bin/env python3
"""
E11 pre-run forecast (reconstruction-v2) -- constructs the EXACT step-1 agent messages for all
15 triggered cases (real control prompt + real requirement + real A2 context, via the same
pipeline.agent_v2._build_user_prompt function E11's real runner would call) and measures their
real token counts. Also exercises both tools locally (zero model calls) on the real triggered
cases to measure real added-context token distributions after each tool. No GPT/Qwen/Gemini call
anywhere in this script.
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
from pipeline.agent_tools_v2 import follow_cross_reference, get_more_candidates  # noqa: E402
from pipeline.agent_v2 import CONTROL_PROMPT_PATH, _build_user_prompt, cross_reference_to_named_provision_cue  # noqa: E402

E07_DIR = REPO / "experiments/E07_standard_rag"
E08B_DIR = REPO / "experiments/E08B_stronger_model_diagnostic"
E05_DIR = REPO / "experiments/E05_full_context"

PLANNING_BUDGET_USD = 5.00
PROTECTED_RESERVE_FRACTION = 0.25
INPUT_PRICE_PER_MILLION = 0.25
OUTPUT_PRICE_PER_MILLION = 2.00

ENC = tiktoken.get_encoding("cl100k_base")


def _tokens(text: str) -> int:
    return len(ENC.encode(text))


def main() -> int:
    gpt_cases = {json.loads(l)["case_id"]: json.loads(l)
                 for l in open(E08B_DIR / "results/run_E08B_A2_gpt5mini_train_cases.jsonl")}
    assert len(gpt_cases) == 150, "baseline A2 availability check: expected all 150 cases present"
    for cid, c in gpt_cases.items():
        assert c.get("predicted_label") is not None, f"{cid} missing A2 label"
        assert "evidence" in c, f"{cid} missing A2 evidence field"
        assert c.get("input_tokens") is not None and c.get("cost_usd") is not None, \
            f"{cid} missing A2 token/cost baseline metadata"
    print("Baseline A2 availability: 150/150 cases have label, evidence, and token/cost metadata.")

    retrieved = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    chunk_text_by_case = {c["case_id"]: c["ranked_chunk_text"] for c in retrieved["cases"]}
    manifest = json.load(open(E05_DIR / "TRAIN_ARCH_v1.json"))
    hypothesis_by_case = {c["case_id"]: c["hypothesis_text"] for c in manifest["cases"]}
    doc_id_by_case = {c["case_id"]: c["document_id"] for c in manifest["cases"]}
    train = json.load(open(REPO / "data/contractnli/train.json"))
    doc_text_by_id = {d["id"]: d["text"] for d in train["documents"]}

    triggered_ids = sorted(cid for cid, chunks in chunk_text_by_case.items()
                            if cross_reference_to_named_provision_cue(chunks))
    assert len(triggered_ids) == 15
    print(f"\nExact 15 triggered cases: {triggered_ids}")

    control_prompt = CONTROL_PROMPT_PATH.read_text()
    control_prompt_tokens = _tokens(control_prompt)
    print(f"\nControl prompt: {control_prompt_tokens} tokens")

    step1_input_tokens = []
    added_context_follow_ref = []
    added_context_get_more = []

    for cid in triggered_ids:
        hyp = hypothesis_by_case[cid]
        chunks = chunk_text_by_case[cid]
        doc_id = doc_id_by_case[cid]
        doc_text = doc_text_by_id[doc_id]

        user_prompt = _build_user_prompt(hyp, chunks)
        total_step1 = control_prompt_tokens + _tokens(user_prompt)
        step1_input_tokens.append(total_step1)

        # Real (local, zero-cost) tool exercise to measure actual added-context size -- extracts
        # the actual matched phrase PLUS trailing characters (e.g. a section number/letter) from
        # the real context, mirroring what a real agent would read and pass as `reference` (not
        # just the bare trigger keyword, which would never resolve to a real numbered provision).
        ctx_lower = " ".join(chunks).lower()
        ctx_original = " ".join(chunks)
        cross_ref_phrase = None
        for p in ("pursuant to section", "pursuant to clause", "under clause", "under section",
                  "as set forth in section", "as provided in section", "in accordance with section",
                  "of the definition of", "as defined in", "paragraph (a)", "paragraphs (a)"):
            idx = ctx_lower.find(p)
            if idx != -1:
                cross_ref_phrase = ctx_original[idx: idx + len(p) + 15]  # include trailing number/letter
                break
        follow_result = follow_cross_reference(doc_text, cross_ref_phrase or "paragraph (a)")
        follow_text = " ".join(r.get("text", "") for r in follow_result.results)
        added_context_follow_ref.append(_tokens(follow_text))

        more_result = get_more_candidates(doc_text, hyp, already_revealed_count=len(chunks))
        more_text = " ".join(r.get("text", "") for r in more_result.results)
        added_context_get_more.append(_tokens(more_text))

    def _stats(vals: list[int]) -> dict:
        s = sorted(vals)
        n = len(s)
        p90_idx = min(int(n * 0.9), n - 1)
        return {"mean": statistics.mean(s), "median": statistics.median(s), "p90": s[p90_idx], "max": max(s)}

    step1_stats = _stats(step1_input_tokens)
    follow_ref_stats = _stats(added_context_follow_ref)
    get_more_stats = _stats(added_context_get_more)
    both_tools_added = [a + b for a, b in zip(added_context_follow_ref, added_context_get_more)]
    both_stats = _stats(both_tools_added)

    print(f"\nStep-1 input-token distribution (control prompt + real requirement + real A2 context), "
          f"n=15: {json.dumps(step1_stats, indent=2)}")
    print(f"\nAdded-context tokens after follow_cross_reference: {json.dumps(follow_ref_stats, indent=2)}")
    print(f"Added-context tokens after get_more_candidates: {json.dumps(get_more_stats, indent=2)}")
    print(f"Added-context tokens after BOTH tool calls (max path): {json.dumps(both_stats, indent=2)}")

    # --- Output-token assumption ---
    e08b_summary = json.load(open(E08B_DIR / "results/run_E08B_A2_gpt5mini_train.json"))
    a2_output_tokens = e08b_summary["output_tokens"]
    print(f"\nE08B A2 real output-token reference: mean={a2_output_tokens['mean']:.1f}, "
          f"median={a2_output_tokens['median']}, p90={a2_output_tokens['p90']}, max={a2_output_tokens['max']}")
    # The agent action schema is a strict subset of A2's task per step (either a short tool-call
    # JSON with 1-2 fields, or the same FINAL {label, evidence} shape as A2) -- expected LOWER per
    # intermediate step, similar-or-lower on the concluding FINAL step. No calibration run made;
    # this is a disclosed estimate, not a measurement.
    expected_output_tokens_per_call = a2_output_tokens["mean"]  # conservative: assume parity with A2
    conservative_output_tokens_per_call = a2_output_tokens["max"]  # worst plausible, matches A2's own max
    print(f"Expected output tokens/call (assumed parity with A2 mean): {expected_output_tokens_per_call:.1f}")
    print(f"Conservative output tokens/call (A2's own observed max): {conservative_output_tokens_per_call}")

    # --- Hosted call count forecast ---
    n_triggered = 15
    min_calls = n_triggered * 1  # every escalated case concludes on its first agent-loop call
    max_calls = n_triggered * 3  # every escalated case exhausts all 3 allowed steps
    # Expected: informed by the offline reachability check (all 15 have a resolvable reference
    # and available candidates) -- assume most cases need exactly 1 tool call + 1 FINAL (2 calls),
    # a minority conclude immediately (1 call) or need both tools (3 calls). Disclosed assumption,
    # not a measurement -- consistent with MAX_TOOL_CALLS=2 making a 2-call path the modal case.
    expected_calls = n_triggered * 2
    print(f"\nHosted call count -- minimum: {min_calls}, expected (assumed): {expected_calls}, "
          f"maximum (worst allowed): {max_calls}")
    print("A forced fallback (max_steps/max_tool_calls/duplicate/invalid_action/context_budget/"
          "cost_budget) NEVER requires an additional model call beyond the one that triggered the "
          "limit check -- the fallback itself is a pure code branch, not a model call.")

    # --- Cost forecast ---
    def _cost(n_calls: int, mean_input_tokens: float, mean_output_tokens: float) -> float:
        return n_calls * (mean_input_tokens / 1e6 * INPUT_PRICE_PER_MILLION
                           + mean_output_tokens / 1e6 * OUTPUT_PRICE_PER_MILLION)

    # Minimum: 15 calls, step-1 input only (no tool context added), expected output.
    min_cost = _cost(min_calls, step1_stats["mean"], expected_output_tokens_per_call)
    # Expected: 30 calls, blend of step-1 and one-tool-added-context input, expected output.
    expected_mean_input = statistics.mean([step1_stats["mean"],
                                            step1_stats["mean"] + follow_ref_stats["mean"]])
    expected_cost = _cost(expected_calls, expected_mean_input, expected_output_tokens_per_call)
    # Conservative: 45 calls, worst-case (both tools added) input, conservative (max) output.
    conservative_mean_input = step1_stats["max"] + both_stats["max"]
    conservative_cost = _cost(max_calls, conservative_mean_input, conservative_output_tokens_per_call)

    print(f"\nProjected incremental E11 spend:")
    print(f"  minimum:     ${min_cost:.4f}")
    print(f"  expected:    ${expected_cost:.4f}")
    print(f"  conservative: ${conservative_cost:.4f}")

    pre_run_ledger = reconstruction_spend_so_far()
    print(f"\nCurrent reconstruction ledger (read from real ledger, not assumed): ${pre_run_ledger:.4f}")
    post_run_min = pre_run_ledger + min_cost
    post_run_expected = pre_run_ledger + expected_cost
    post_run_conservative = pre_run_ledger + conservative_cost
    print(f"Projected post-E11 ledger total -- minimum: ${post_run_min:.4f}, "
          f"expected: ${post_run_expected:.4f}, conservative: ${post_run_conservative:.4f}")

    gate = check_budget_against_ledger(
        projected_experiment_cost_usd=conservative_cost,
        planning_budget_usd=PLANNING_BUDGET_USD,
        protected_reserve_fraction=PROTECTED_RESERVE_FRACTION,
    )
    print(f"\nBudget gate (conservative estimate ${conservative_cost:.4f}): {gate.reason}")
    print(f"GATE RESULT: {'PASS' if gate.allowed else 'FAIL'}")

    # --- Runtime forecast ---
    e08b_latency = e08b_summary["generation_latency_ms"]
    mean_latency_s = e08b_latency["mean"] / 1000
    p90_latency_s = e08b_latency["p90"] / 1000
    min_runtime_s = n_triggered * mean_latency_s  # 1 call each
    expected_runtime_s = n_triggered * 2 * mean_latency_s  # 2 calls each
    max_runtime_s = n_triggered * 3 * p90_latency_s  # 3 calls each at p90 latency
    print(f"\nRuntime forecast for the 15 escalated cases (non-triggered cases require no model runtime):")
    print(f"  minimum:  {min_runtime_s:.1f}s")
    print(f"  expected: {expected_runtime_s:.1f}s")
    print(f"  maximum:  {max_runtime_s:.1f}s")

    out = {
        "triggered_case_ids": triggered_ids,
        "baseline_a2_availability": "150/150 verified",
        "step1_input_token_distribution": step1_stats,
        "added_context_follow_cross_reference": follow_ref_stats,
        "added_context_get_more_candidates": get_more_stats,
        "added_context_both_tools": both_stats,
        "output_token_assumption": {
            "reference_a2_mean": a2_output_tokens["mean"], "reference_a2_max": a2_output_tokens["max"],
            "expected_per_call": expected_output_tokens_per_call,
            "conservative_per_call": conservative_output_tokens_per_call,
        },
        "hosted_call_forecast": {"minimum": min_calls, "expected": expected_calls, "maximum": max_calls},
        "cost_forecast_usd": {"minimum": min_cost, "expected": expected_cost, "conservative": conservative_cost},
        "pre_run_ledger_usd": pre_run_ledger,
        "post_run_ledger_projection_usd": {"minimum": post_run_min, "expected": post_run_expected,
                                            "conservative": post_run_conservative},
        "budget_gate": {"allowed": gate.allowed, "reason": gate.reason},
        "runtime_forecast_seconds": {"minimum": min_runtime_s, "expected": expected_runtime_s,
                                      "maximum": max_runtime_s},
    }
    out_path = REPO / "experiments/E11_selective_agent_evaluation/results/pre_run_forecast.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
