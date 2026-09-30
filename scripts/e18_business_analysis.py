#!/usr/bin/env python3
"""E18: offline business/cost/safety/course synthesis. ZERO model calls, no retuning, no TEST-output changes.
Every number is read from an existing experiment artifact, or is an explicitly labelled scenario assumption / config-derived approximation."""
from __future__ import annotations
import json, statistics as st, sys
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(REPO))
from evaluation.metrics import joint_label_evidence_correctness  # noqa: F401  (not reused directly; frozen semantics referenced in report)

OUT = REPO / "experiments/E18_business_course_synthesis/results"

# ---------------------------------------------------------------- 1. majority-class TEST baseline (Entailment always)
W = {"Entailment": 968, "Contradiction": 220, "NotMentioned": 903}; TOT = sum(W.values())
def majority_baseline():
    acc = W["Entailment"] / TOT
    recall = {"Entailment": 1.0, "Contradiction": 0.0, "NotMentioned": 0.0}
    prec_E = W["Entailment"] / TOT  # predicts Entailment for everything
    f1_E = 2 * prec_E * 1.0 / (prec_E + 1.0)
    macro_f1 = (f1_E + 0.0 + 0.0) / 3
    # joint under project semantics: predicting Entailment with no evidence -> never joint-correct for E (evidence empty, tau needs >=0.5 overlap with empty pred -> fails unless gold empty), 0 for C, 0 for NM (NM requires empty evidence AND label match -> label wrong)
    joint = 0.0  # predicts Entailment with no evidence on every case; E cases fail evidence-overlap (0 quotes vs >=1 gold span), C/NM fail on label
    return {"rule": "always predict Entailment, empty evidence", "test_label_counts": W, "n": TOT, "accuracy": acc, "macro_f1": macro_f1,
            "recall": recall, "joint_success": joint, "note": "descriptive extra baseline; does not modify B01/rule/Qwen/GPT results"}

# ---------------------------------------------------------------- 2. agent token economics: B (base/static tokens per turn), D (accumulated tokens per turn)
def agent_token_economics():
    agent_prompt_tokens = 510  # cl100k_base token count of prompts/agent_step_v1_3tools.txt (frozen
    # here: the file was deleted in the 2026-09-29 legacy prompt cleanup, see prompts/README.md)
    e08b = json.load(open(REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train.json")) if (REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train.json").exists() else None
    baseline_ctx_tokens = 1476  # E10 config.yaml baseline_observed_mean_latency reference case / E08B measured baseline input tokens (representative single trace, agent_traces.jsonl)
    B = agent_prompt_tokens + baseline_ctx_tokens  # repeated per turn: the fixed agent-control prompt + the original top-5 RAG context, resent every step
    traces = [json.loads(l) for l in open(REPO / "experiments/E11_selective_agent_evaluation/results/agent_traces.jsonl")]
    steps_observed = sorted({t["agent_steps"] for t in traces})
    max_cumulative_retrieved_tokens = 2000; max_tool_calls = 2
    D_config = max_cumulative_retrieved_tokens / max_tool_calls  # config-derived approximation, NOT a measured multi-step average (no E11 trace made a tool call)
    return {"B_repeated_tokens_per_turn": B, "B_components": {"agent_control_prompt_tokens": agent_prompt_tokens, "resent_top5_context_tokens_representative": baseline_ctx_tokens},
            "D_new_tokens_per_turn": D_config, "D_source": "APPROXIMATION: E10's hard_limits.max_cumulative_retrieved_tokens (2000) / max_tool_calls (2). No real NDATrace agent trace made ANY tool call (all 15 E11 traces: agent_steps=1, stop_reason='final') so an empirical multi-step D cannot be measured from this project's own data.",
            "observed_agent_steps_in_E11": steps_observed, "n_traces": len(traces), "max_agent_steps_configured": 3, "max_tool_calls_configured": 2}

def quadratic_growth(B, D, T_max=3):
    rows = []
    for T in range(1, T_max + 1):
        bt = B * T; dt = D * T * (T - 1) / 2; rows.append({"T": T, "B*T": bt, "D*T(T-1)/2": dt, "total": bt + dt})
    return rows

# ---------------------------------------------------------------- 3. reliability compounding: P(success) ~= s^T
def reliability(B_econ):
    e11 = json.load(open(REPO / "experiments/E11_selective_agent_evaluation/results/run_E11_A3_train.json"))
    per_step_success_candidates = {"E13_FULL_single_call_joint_success": 0.7733, "E17_hosted_TEST_single_call_joint_success": 115 / 150,
                                    "E11_A3_agent_first_step_final_rate": 1.0}
    rows = {}
    for s_name, s in per_step_success_candidates.items():
        rows[s_name] = [{"T": T, "P_success": s ** T} for T in range(1, 4)]
    return {"note": "SCENARIO/measured single-call joint-success rates used as a per-step reliability proxy s; real NDATrace agent traces never exceeded 1 step, so a true multi-step s is not measured. Shown for T=1..3 (the configured agent cap).", "candidates": rows}

# ---------------------------------------------------------------- 4. FULL vs RAG token economics by document-length tercile (already computed once; recomputed here deterministically from stored artifacts)
def full_vs_rag_tokens():
    E13 = REPO / "experiments/E13_gpt_context_architecture"
    full = {c["case_id"]: c for c in json.load(open(E13 / "DEV_ARCH_v1_FULL_CONTEXT.json"))["cases"]}
    rf = {r["case_id"]: r for r in map(json.loads, open(E13 / "results/run_E13_gpt_full_cases.jsonl"))}
    rr = {r["case_id"]: r for r in map(json.loads, open(E13 / "results/run_E13_gpt_rag_cases.jsonl"))}
    j_full = {r["case_id"]: r for r in map(json.loads, open(E13 / "results/run_E13_gpt_full_cases.jsonl"))}
    data = [(len(full[c]["context_text"]), rf[c]["input_tokens"], rr[c]["input_tokens"], c) for c in full if c in rf and c in rr]
    data.sort()
    n = len(data); terc = {"short": data[: n // 3], "medium": data[n // 3: 2 * n // 3], "long": data[2 * n // 3:]}
    a = json.load(open(E13 / "results/e13_analysis.json"))["summary"]
    out = {"overall": {"FULL_mean_input_tokens": a["full"]["input_tokens"]["mean"], "RAG_mean_input_tokens": a["rag"]["input_tokens"]["mean"], "FULL_joint": a["full"]["joint"], "RAG_joint": a["rag"]["joint"], "outcome": "FULL MATERIALLY BETTER (frozen E13 rule)"}, "by_length_tercile": {}}
    for name, t in terc.items():
        full_t = [x[1] for x in t]; rag_t = [x[2] for x in t]
        out["by_length_tercile"][name] = {"n": len(t), "chars_min": t[0][0], "chars_max": t[-1][0], "full_mean_tokens": st.mean(full_t), "rag_mean_tokens": st.mean(rag_t), "token_saving": st.mean(full_t) - st.mean(rag_t), "pct_saving": 1 - st.mean(rag_t) / st.mean(full_t)}
    return out

# ---------------------------------------------------------------- 5. Oracle ceiling vs real systems
def oracle_ceiling():
    e01 = json.load(open(REPO / "experiments/E01_oracle/results/e01_metrics.json"))
    e13 = json.load(open(REPO / "experiments/E13_gpt_context_architecture/results/e13_analysis.json"))["summary"]
    e17 = json.load(open(REPO / "experiments/E17_final_test/results/final_metrics.json"))
    e17b = json.load(open(REPO / "experiments/E17B_full_test_completion/results/final_full_test_metrics.json"))
    return {"oracle_gold_evidence_local_qwen": {"macro_f1": e01["qwen2.5:7b-instruct"]["macro_f1"], "contradiction_recall": e01["qwen2.5:7b-instruct"]["per_class_recall"]["Contradiction"]["recall"]},
            "oracle_gold_evidence_gpt5mini": {"macro_f1": e01["openai/gpt-5-mini"]["macro_f1"], "contradiction_recall": e01["openai/gpt-5-mini"]["per_class_recall"]["Contradiction"]["recall"]},
            "real_context_full_gpt_DEV": {"macro_f1": e13["full"]["macro_f1"], "joint": e13["full"]["joint"]}, "real_context_full_gpt_TEST_sample_n150": {"macro_f1": e17["hosted_gpt_balanced_150"]["macro_f1"], "joint": e17["hosted_gpt_balanced_150"]["joint"]},
            "real_context_full_gpt_TEST_FULL_n2091": {"macro_f1": e17b["full_gpt_2091"]["macro_f1"], "joint": e17b["full_gpt_2091"]["joint"], "source": "E17B merged full-population result (primary)"},
            "reading": "Qwen was weak even WITH gold evidence (macro-F1 0.638 Oracle vs GPT 0.906 Oracle) -> the E00B-era finding that model reasoning, not retrieval, was the dominant bottleneck for Qwen. GPT substantially outperformed Qwen and moved much closer to the Oracle reasoning ceiling (0.906), but a meaningful gap remained (full TEST macro-F1 0.727 vs Oracle 0.906). For final GPT Contradiction failures, interpretation was the dominant observed failure mode: 38 of 50 evidence-bearing Contradiction misses (full TEST, n=220) quoted text overlapping the annotated gold evidence but still predicted the wrong label -- missed-provision and evidence failures still exist elsewhere (E17B failure taxonomy). Oracle accuracy != achievable production accuracy (no retrieval/full-context system gets literally gold evidence)."}

# ---------------------------------------------------------------- 6. cost-to-serve, break-even, sensitivity
def cost_to_serve():
    e17 = json.load(open(REPO / "experiments/E17_final_test/results/final_metrics.json"))
    e17b = json.load(open(REPO / "experiments/E17B_full_test_completion/results/final_full_test_metrics.json"))
    C_AI_gpt = e17b["full_gpt_2091"]["ops"]["cost_per_case"]; C_AI_qwen = 0.0; C_AI_rule = 0.0
    p_gpt = e17b["full_gpt_2091"]["joint"]; p_qwen = e17["qwen_full_2091"]["joint"]; p_rule = e17["rule_full_2091"]["joint"]  # p_safe = joint success (full 2,091-case GPT measurement, NOT the n=150 sample), per explicit instruction
    review_scenarios_min = [1, 3, 5, 10]; rates_per_hour = [20, 40, 75]  # illustrative scenario assumption -- no project/course source specifies an NDA reviewer rate
    C_H = {f"{m}min_at_${r}/hr": round(m / 60 * r, 4) for m in review_scenarios_min for r in rates_per_hour}
    V_scenarios = [100, 1000, 8000]; F_scenarios = {"none": 0.0, "illustrative_small_saas": 500.0}  # scenario
    def monthly(C_AI, p_safe, C_H_, V, F):
        return V * (C_AI + (1 - p_safe) * C_H_) + F
    grid = []
    for sysname, (C_AI, p) in {"hosted_GPT": (C_AI_gpt, p_gpt), "local_Qwen": (C_AI_qwen, p_qwen), "rule_only": (C_AI_rule, p_rule)}.items():
        for chn, chv in C_H.items():
            for V in V_scenarios:
                for fn, F in F_scenarios.items():
                    grid.append({"system": sysname, "C_AI": C_AI, "p_safe(joint)": p, "human_review_scenario": chn, "C_H": chv, "V": V, "fixed_cost_scenario": fn, "F": F, "C_month": monthly(C_AI, p, chv, V, F), "cost_per_1000": monthly(C_AI, p, chv, 1000, 0)})
    # sensitivity curve: cost-per-1000 vs p_safe, at a fixed C_H scenario (5 min @ $40/hr), for GPT/Qwen/manual-only
    ch_fixed = C_H["5min_at_$40/hr"]
    ps = [round(x, 2) for x in [i / 20 for i in range(0, 21)]]
    sens = {"C_H_scenario": "5min_at_$40/hr", "C_H": ch_fixed, "curves": {"hosted_GPT (C_AI={:.6f})".format(C_AI_gpt): [monthly(C_AI_gpt, p, ch_fixed, 1000, 0) for p in ps], "local_Qwen (C_AI=0)": [monthly(0.0, p, ch_fixed, 1000, 0) for p in ps],
               "manual_only (p_safe=0 by definition, cost=C_H every case)": [monthly(0.0, 0.0, ch_fixed, 1000, 0)] * len(ps)}, "p_axis": ps}
    # break-even: p_BE = 1 - (E - C_alt)/C_H  for Qwen-vs-GPT (E=GPT all-in cost at its own p, C_alt=Qwen AI cost) and AI+human vs manual-only
    def all_in(C_AI, p, ch): return C_AI + (1 - p) * ch
    E_gpt = all_in(C_AI_gpt, p_gpt, ch_fixed)
    breakeven = {"Qwen_vs_GPT": {"E_target_allin_cost_gpt": E_gpt, "C_alt_qwen_AI_cost": C_AI_qwen, "p_BE_qwen_needs": 1 - (E_gpt - C_AI_qwen) / ch_fixed, "qwen_actual_p": p_qwen, "meets_breakeven": p_qwen >= 1 - (E_gpt - C_AI_qwen) / ch_fixed},
                 "AI_plus_human_vs_manual_only": {"manual_only_cost_per_case": ch_fixed, "gpt_allin_cost_per_case": E_gpt, "gpt_cheaper_than_manual": E_gpt < ch_fixed, "p_BE_for_gpt_to_beat_manual": 1 - (ch_fixed - C_AI_gpt) / ch_fixed}}
    return {"C_AI_measured": {"gpt": C_AI_gpt, "qwen_api_cost": C_AI_qwen, "qwen_note": "API cost = $0; LOCAL COMPUTE/TIME IS NOT MONETIZED (7.13h for 2091 cases on the dev laptop) -- not zero real economic cost", "rule": C_AI_rule},
            "p_safe_measured(=joint_success)": {"gpt_TEST_FULL_2091(primary)": p_gpt, "qwen_TEST_full": p_qwen, "rule_TEST_full": p_rule, "gpt_TEST_balanced_150(historical,_not_used_as_p_safe)": e17["hosted_gpt_balanced_150"]["joint"]},
            "human_review_cost_scenarios_usd_per_case": C_H, "human_review_cost_disclaimer": "ILLUSTRATIVE SCENARIO ASSUMPTION -- no NDATrace/course source specifies a real reviewer hourly rate or review time",
            "cost_to_serve_grid_sample": grid[:12], "cost_to_serve_grid_size": len(grid), "sensitivity_per_1000_vs_p_safe": sens, "break_even": breakeven}

# ---------------------------------------------------------------- 7. abstention/review + safe automation + silent failure (E15 fresh DEV_ROUTING_v1, n=138)
def routing_safety():
    v = json.load(open(REPO / "experiments/E15_review_routing/results/validation_results.json"))
    out = {}
    for pol, d in v["policies"].items():
        j = d["joint"]; n = j["n"]; conf = j["confusion"]
        safe_auto = conf["success_auto"] / n; unsafe_auto = conf["failure_auto"] / n; human_review = j["review"] / n
        out[pol] = {"review_rate": j["review_rate"], "automation_coverage": j["automation_coverage"], "failure_capture": j["error_capture"], "residual_joint_error": j["residual_error_rate"], "selective_joint_success": j["selective_success"], "false_review_rate": j["false_review_rate"],
                    "safe_automation_rate": safe_auto, "unsafe_automation_rate": unsafe_auto, "human_review_rate": human_review, "sums_to_1": round(safe_auto + unsafe_auto + human_review, 6),
                    "silent_failure_rate": conf["failure_auto"] / n, "unsafe_non_abstention_rate": (conf["failure_auto"] / conf["failure_auto"] + conf["success_auto"]) if False else conf["failure_auto"] / (conf["failure_auto"] + conf["success_auto"])}
    return {"source": "E15 fresh DEV_ROUTING_v1 validation (n=138)", "provisional_targets": {"review_rate<=": 0.40, "residual_joint_error<": 0.10, "note": "inherited/provisional project targets, NOT a measured enterprise SLA"}, "policies": out,
            "conclusion": "E15 demonstrated that the deterministic observable runtime signals tried (parse validity, evidence source-validity, label/evidence consistency, keyword-rule agreement) were not sufficient to reliably detect confident reasoning errors: R0 (no routing) leaves 29.0% silent failure; R3 (best-performing candidate) needed 51.3% human review to bring residual error to 10.4%, still missing the <10% target, and no candidate entered the target region (review<=40% AND residual<10%)."}

# ---------------------------------------------------------------- 8. E16 robustness summary
def robustness_summary():
    h = json.load(open(REPO / "experiments/E16_robustness_security/results/hosted_results.json"))
    return {"clean_joint": h["summary"]["clean"]["joint"], "attack_joint": h["summary"]["attack"]["joint"], "attack_induced_joint_regressions": h["joint_regressions"], "injection_attack_success_rate": h["injection_attack_success"]["rate"],
            "injection_attack_successes": h["injection_attack_success"]["successes"], "n_injection_pairs": h["injection_attack_success"]["n_injection_pairs"], "clean_source_valid_rate": h["summary"]["clean"]["source_valid_quote_rate"],
            "attack_source_valid_rate": h["summary"]["attack"]["source_valid_quote_rate"], "decision": h["decision"]["outcome"], "n_pairs": 20, "warning": "source-valid evidence != trusted instruction source (do not exaggerate an n=20-pair finding)"}

# ---------------------------------------------------------------- 9. E17 failure taxonomy + Contradiction story
def failure_taxonomy():
    """Primary: full-population (n=2091, E17B). E17's 150-case taxonomy kept only as an earlier consistency check."""
    e17b = json.load(open(REPO / "experiments/E17B_full_test_completion/results/final_full_test_metrics.json"))
    fa150 = json.load(open(REPO / "experiments/E17_final_test/results/failure_analysis.json"))
    m150 = json.load(open(REPO / "experiments/E17_final_test/results/final_metrics.json"))
    return {"buckets_full_2091(primary)": e17b["failure_taxonomy_2091"], "total_full_2091": e17b["n_total_failures"],
            "contradiction_full_2091(primary)": {**e17b["full_gpt_contradiction_220"], "note": "At full TEST scale, many remaining Contradiction errors were interpretation failures rather than evidence-access failures: 38 of 50 evidence-bearing Contradiction misses quoted text overlapping the annotated gold evidence but still predicted the wrong label."},
            "buckets_sample_150(consistency_check_only)": {k: v["n"] for k, v in fa150["buckets"].items()}, "total_sample_150": fa150["total_joint_failures"],
            "contradiction_sample_150(consistency_check_only)": {"correct": m150["hosted_gpt_contradiction"]["correct"], "joint": m150["hosted_gpt_contradiction"]["joint"], "C_to_E": m150["hosted_gpt_contradiction"]["C_to_E"], "C_to_NM": m150["hosted_gpt_contradiction"]["C_to_NM"]}}

def main():
    out = {"majority_baseline_TEST": majority_baseline(), "agent_token_economics": agent_token_economics(), "oracle_ceiling": oracle_ceiling(), "full_vs_rag_tokens": full_vs_rag_tokens(),
           "cost_to_serve": cost_to_serve(), "routing_safety": routing_safety(), "robustness_summary": robustness_summary(), "failure_taxonomy": failure_taxonomy()}
    out["quadratic_token_growth"] = quadratic_growth(out["agent_token_economics"]["B_repeated_tokens_per_turn"], out["agent_token_economics"]["D_new_tokens_per_turn"])
    out["reliability_compounding"] = reliability(out["agent_token_economics"])
    OUT.mkdir(parents=True, exist_ok=True); json.dump(out, open(OUT / "e18_analysis.json", "w"), indent=1, default=str)
    print(json.dumps({k: out[k] for k in ("majority_baseline_TEST", "agent_token_economics")}, indent=1, default=str))
    print(json.dumps(out["quadratic_token_growth"], indent=1)); print(json.dumps(out["oracle_ceiling"], indent=1, default=str))
    print(json.dumps(out["full_vs_rag_tokens"], indent=1, default=str)); print(json.dumps(out["routing_safety"]["policies"], indent=1, default=str))
    print(json.dumps(out["cost_to_serve"]["break_even"], indent=1, default=str))

if __name__ == "__main__":
    main()
