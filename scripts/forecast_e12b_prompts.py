#!/usr/bin/env python3
"""E12B Stage A: prompt stats/diffs, context-artifact verification, cost/budget/runtime forecast. Zero model calls."""
import difflib, hashlib, json, statistics, sys
from pathlib import Path
import tiktoken

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from evaluation.budget import check_budget_against_ledger, final_spend_so_far  # noqa: E402
from evaluation.prompt_selection import load_prompt_config  # noqa: E402

E12B = REPO / "experiments/E12B_gpt_prompt_optimization"
E08B = REPO / "experiments/E08B_stronger_model_diagnostic/results"
E12A = REPO / "experiments/E12A_static_context_expansion/results"
PROMPTS = ["gpt_p0", "gpt_p1", "gpt_p2", "gpt_p3"]
ADDED = {"gpt_p0": 0, "gpt_p1": 3, "gpt_p2": 3 + 6, "gpt_p3": 3 + 4}  # definitions / +decision steps / +guidance rules
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nRetrieved NDA excerpts: {context_text}"
LEAK = {"gold_label", "gold_span_indices", "choice", "relevance_flag", "expected_prediction", "failure_bucket"}
enc = tiktoken.get_encoding("cl100k_base"); tok = lambda s: len(enc.encode(s))
st = lambda v: {"mean": statistics.mean(v), "median": statistics.median(v), "p90": sorted(v)[int(.9 * len(v))], "max": max(v)}


def main():
    P = {k: open(REPO / f"prompts/final/{k}.txt", newline="").read() for k in PROMPTS}
    EV = ' Also return the exact sentence(s) from the text that support your label, verbatim, as a list under "evidence". Return an empty list for NotMentioned.'
    eff = load_prompt_config("p00")["system_prompt"].rstrip() + "\n" + EV
    integ = {"gpt_p0_byte_identical_to_E08B_effective_system_prompt": P["gpt_p0"] == eff,
             "gpt_p0_sha1_matches_E08B_prompt_config_hash_dec7527f24c9":
                 hashlib.sha1((P["gpt_p0"] + USER_TEMPLATE).encode()).hexdigest()[:12] == "dec7527f24c9"}
    stats = {}
    for k, v in P.items():
        diff = [l for l in difflib.unified_diff(P["gpt_p0"].splitlines(), v.splitlines(), lineterm="", n=0)
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        stats[k] = {"chars": len(v), "tokens_cl100k": tok(v), "added_instructions_vs_P0": ADDED[k],
                    "diff_added_lines": sum(l[0] == "+" for l in diff), "diff_removed_lines": sum(l[0] == "-" for l in diff)}
    man = json.load(open(E12B / "TRAIN_GPT_PROMPT_v1.json")); ctx = json.load(open(E12B / "TRAIN_GPT_PROMPT_v1_RETRIEVED_retrieval_v1.json"))
    ids = [c["case_id"] for c in man["cases"]]
    ctx_checks = {"150_cases": len(ctx["cases"]) == 150, "same_ids_order_as_manifest": [c["case_id"] for c in ctx["cases"]] == ids,
                  "top5_only": all(len(c["ranked_chunk_ids"]) <= 5 for c in ctx["cases"]) and ctx["retrieval_config"]["top_k"] == 5,
                  "retrieval_config_equals_E07": ctx["retrieval_config"] == json.load(open(REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))["retrieval_config"],
                  "no_gold_leakage": not any(LEAK & set(c) for c in ctx["cases"]),
                  "rerank_order_non_increasing": all(all(a >= b for a, b in zip(c["ranked_chunk_rerank_scores"], c["ranked_chunk_rerank_scores"][1:])) for c in ctx["cases"])}
    # tokens: calibrate cl100k against E08B real API input tokens (P0 on the ARCH manifest)
    e07 = {c["case_id"]: c for c in json.load(open(REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))["cases"]}
    e08 = [json.loads(l) for l in open(E08B / "run_E08B_A2_gpt5mini_train_cases.jsonl")]
    est = lambda sysp, c: tok(sysp) + tok(USER_TEMPLATE.format(hypothesis_text=c["hypothesis_text"], context_text="\n\n---\n\n".join(c["ranked_chunk_text"])))
    ratio = sum(r["input_tokens"] for r in e08) / sum(est(P["gpt_p0"], e07[r["case_id"]]) for r in e08)
    intok = {k: [est(P[k], c) * ratio for c in ctx["cases"]] for k in PROMPTS}
    ctx_only = [tok("\n\n---\n\n".join(c["ranked_chunk_text"])) for c in ctx["cases"]]
    o8, o12 = json.load(open(E08B / "run_E08B_A2_gpt5mini_train.json"))["output_tokens"], json.load(open(E12A / "run_E12A_top11_gpt5mini_train.json"))["output_tokens"]
    out_mean = statistics.mean([o8["mean"], o12["mean"]]); out_p90 = max(o8["p90"], o12["p90"])
    PI, PO = 0.25 / 1e6, 2.0 / 1e6
    exp = {k: sum(x * PI + out_mean * PO for x in intok[k]) for k in PROMPTS}
    cons = {k: sum(x * PI + out_p90 * PO for x in intok[k]) for k in PROMPTS}
    ledger = final_spend_so_far(); ce = sum(cons.values())
    gate = check_budget_against_ledger(ce, 5.00, 0.25)
    lat = statistics.mean([json.load(open(E08B / "run_E08B_A2_gpt5mini_train.json"))["generation_latency_ms"]["mean"],
                           json.load(open(E12A / "run_E12A_top11_gpt5mini_train.json"))["latency_ms"]["mean"]]) / 1000
    res = {"integrity": integ, "prompt_stats": stats, "context_checks": ctx_checks, "calibration_ratio": ratio,
           "retrieved_text_tokens_cl100k": st(ctx_only), "input_tokens_per_prompt_calibrated": {k: st(v) for k, v in intok.items()},
           "output_token_assumption": {"mean_used": out_mean, "p90_used": out_p90, "sources": "E08B and E12A real GPT-5-mini distributions"},
           "cost_usd": {"expected_per_prompt": exp, "expected_total": sum(exp.values()), "conservative_per_prompt": cons, "conservative_total": ce},
           "ledger_now": ledger, "ledger_after": {"expected": ledger + sum(exp.values()), "conservative": ledger + ce},
           "budget_gate": {"rule": "ledger + conservative + $1.25 reserve <= $5.00", "allowed": bool(gate.allowed), "reason": gate.reason,
                           "arithmetic": ledger + ce + 1.25},
           "runtime": {"calls_per_prompt": 150, "total_calls": 600, "mean_latency_s_assumed": lat,
                       "minutes_per_prompt": 150 * lat / 60, "total_minutes_sequential": 600 * lat / 60}}
    json.dump(res, open(E12B / "results/pre_run_forecast.json", "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
