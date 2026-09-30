#!/usr/bin/env python3
"""E12C Stage A: verify P0/P3 hashes, context artifact, and forecast cost/budget/runtime from REAL E12B distributions. Zero model calls."""
import hashlib, json, statistics, sys
from pathlib import Path
import tiktoken

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation.budget import check_budget_against_ledger, final_spend_so_far  # noqa: E402

C = REPO / "experiments/E12C_gpt_prompt_confirmation"; B = REPO / "experiments/E12B_gpt_prompt_optimization/results"
ARMS = ["gpt_p0", "gpt_p3"]
UT = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"
LEAK = {"gold_label", "gold_span_indices", "choice", "relevance_flag", "expected_prediction", "failure_bucket"}
enc = tiktoken.get_encoding("cl100k_base"); tok = lambda s: len(enc.encode(s))
st = lambda v: {"mean": statistics.mean(v), "median": statistics.median(v), "p90": sorted(v)[int(.9 * len(v))], "max": max(v)}
sha = lambda p: hashlib.sha1(open(p, "rb").read()).hexdigest()


def main():
    P = {k: open(REPO / f"prompts/final/{k}.txt", newline="").read() for k in ARMS}
    h = {k: sha(REPO / f"prompts/final/{k}.txt") for k in ARMS}
    e12b = {"gpt_p0": [json.loads(l) for l in open(B / "run_E12B_gpt_p0_cases.jsonl")], "gpt_p3": [json.loads(l) for l in open(B / "run_E12B_gpt_p3_cases.jsonl")]}
    hash_checks = {k: {r["prompt_hash"] for r in e12b[k]} == {h[k]} for k in ARMS}
    man = json.load(open(C / "TRAIN_GPT_PROMPT_CONFIRM_v1.json")); ctx = json.load(open(C / "TRAIN_GPT_PROMPT_CONFIRM_v1_RETRIEVED_retrieval_v1.json"))
    ids = [c["case_id"] for c in man["cases"]]; hyp = {c["case_id"]: c["hypothesis_text"] for c in man["cases"]}
    e12b_ctx = json.load(open(REPO / "experiments/E12B_gpt_prompt_optimization/TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1.json"))
    checks = {"150_cases": len(ctx["cases"]) == 150, "same_ids_order": [c["case_id"] for c in ctx["cases"]] == ids,
              "top5_only": all(len(c["ranked_chunk_ids"]) <= 5 for c in ctx["cases"]),
              "retrieval_config_equals_E12B": ctx["retrieval_config"] == e12b_ctx["retrieval_config"],
              "no_gold_leakage": not any(LEAK & set(c) for c in ctx["cases"]),
              "rerank_order_non_increasing": all(all(a >= b for a, b in zip(c["ranked_chunk_rerank_scores"], c["ranked_chunk_rerank_scores"][1:])) for c in ctx["cases"]),
              "case_overlap_with_E12B_manifest": len(set(ids) & {c["case_id"] for c in e12b_ctx["cases"]}) == 0}
    est = lambda sp, c: tok(sp) + tok(UT.format(hypothesis_text=hyp[c["case_id"]], context_text="\n\n---\n\n".join(c["ranked_chunk_text"])))
    # calibrate cl100k -> real API tokens on E12B (same prompts, same wrapper)
    e12b_by = {c["case_id"]: c for c in e12b_ctx["cases"]}; e12b_hyp = {c["case_id"]: c["hypothesis_text"] for c in json.load(open(REPO / "experiments/E12B_gpt_prompt_optimization/TRAIN_GPT_PROMPT_v1.json"))["cases"]}
    def est_b(sp, c): return tok(sp) + tok(UT.format(hypothesis_text=e12b_hyp[c["case_id"]], context_text="\n\n---\n\n".join(c["ranked_chunk_text"])))
    ratio = {k: sum(r["input_tokens"] for r in e12b[k]) / sum(est_b(P[k], e12b_by[r["case_id"]]) for r in e12b[k]) for k in ARMS}
    intok = {k: [est(P[k], c) * ratio[k] for c in ctx["cases"]] for k in ARMS}
    out = {k: [r["output_tokens"] for r in e12b[k]] for k in ARMS}; lat = {k: [r["generation_latency_ms"] for r in e12b[k]] for k in ARMS}
    PI, PO = .25 / 1e6, 2.0 / 1e6
    exp = {k: sum(x * PI + statistics.mean(out[k]) * PO for x in intok[k]) for k in ARMS}
    cons = {k: sum(x * PI + st(out[k])["p90"] * PO for x in intok[k]) for k in ARMS}
    real_e12b = {k: sum(r["cost_usd"] for r in e12b[k]) for k in ARMS}
    led = final_spend_so_far(); ce = sum(cons.values()); gate = check_budget_against_ledger(ce, 5.0, 0.25)
    mean_lat = statistics.mean(statistics.mean(v) for v in lat.values()) / 1000
    res = {"prompt_hashes": h, "hashes_match_E12B_records": hash_checks, "context_checks": checks, "calibration_ratio": ratio,
           "input_tokens_calibrated": {k: st(v) for k, v in intok.items()}, "e12b_real_output_tokens": {k: st(v) for k, v in out.items()},
           "e12b_real_cost_150": real_e12b, "cost_usd": {"expected": exp, "expected_total": sum(exp.values()), "conservative": cons, "conservative_total": ce},
           "ledger_now": led, "ledger_after": {"expected": led + sum(exp.values()), "conservative": led + ce},
           "budget_gate": {"allowed": bool(gate.allowed), "reason": gate.reason, "arithmetic": led + ce + 1.25},
           "runtime": {"total_calls": 300, "mean_per_call_latency_s_E12B": mean_lat, "sequential_minutes": 300 * mean_lat / 60,
                       "concurrency5_minutes_est": 300 * mean_lat / 5 / 60, "note": "E12B P1-P3 at concurrency 5 took 3.6-4.0 min/arm"}}
    json.dump(res, open(C / "results/pre_run_forecast.json", "w"), indent=1, default=str); print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
