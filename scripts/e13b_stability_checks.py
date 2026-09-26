#!/usr/bin/env python3
"""E13B: OFFLINE re-application of the already-FROZEN E13 / E12B / E12C / E11 decision rules with evaluator v1 vs v2 numbers. NOT new benchmarks; no model calls."""
import json
from pathlib import Path
from scipy import stats

REPO = Path(__file__).resolve().parent.parent
R = REPO / "experiments/E13B_evidence_evaluator_hardening/results"
recs = json.load(open(R / "rescoring_case_records.json")); units = {f"{u['exp']}::{u['arm']}": u for u in json.load(open(R / "rescoring_summary.json"))["units"]}
E13 = json.load(open(REPO / "experiments/E13_gpt_context_architecture/results/e13_analysis.json"))
E12B = json.load(open(REPO / "experiments/E12B_gpt_prompt_optimization/results/e12b_analysis.json"))
E12C = json.load(open(REPO / "experiments/E12C_gpt_prompt_confirmation/results/e12c_analysis.json"))


def e13_rule(jf, jr, erf, err, epf, epr, dC, dF):
    net = jr - jf
    g = {"contradiction_ge3_below": dC <= -3, "macro_f1_below_0.03": dF < -0.03, "evidence_recall_below_3pp": err - erf < -0.03, "evidence_precision_below_3pp": epr - epf < -0.03}
    fails = any(g.values())
    o = "A" if net >= 5 and not fails else "B" if net <= -5 or (fails and net <= 0) else "C" if -4 <= net <= 4 and not fails else "D"
    return {"net_joint": net, "guards_fail": g, "outcome": o, "evidence_recall_delta_pp": (err - erf) * 100, "evidence_precision_delta_pp": (epr - epf) * 100}


def main():
    out = {}
    # ---- E13
    f, r = units["E13::full_context"], units["E13::rag_top5"]
    dC = E13["contradiction"]["rag"]["correct"] - E13["contradiction"]["full"]["correct"]; dF = E13["summary"]["rag"]["macro_f1"] - E13["summary"]["full"]["macro_f1"]
    v1 = e13_rule(f["joint_v1"], r["joint_v1"], f["evidence_recall_v1"], r["evidence_recall_v1"], f["evidence_precision_v1"], r["evidence_precision_v1"], dC, dF)
    v2 = e13_rule(f["joint_v2"], r["joint_v2"], f["evidence_recall_v2"], r["evidence_recall_v2"], f["evidence_precision_v2"], r["evidence_precision_v2"], dC, dF)
    out["E13"] = {"v1": v1, "v2": v2, "stored_outcome": E13["outcome"], "v1_reproduces_stored_outcome": v1["outcome"] == E13["outcome"][0], "decision_changes_under_v2": v1["outcome"] != v2["outcome"],
                  "FULL": {k: f[k] for k in ("joint_v1", "joint_v2", "evidence_recall_v1", "evidence_recall_v2", "evidence_precision_v1", "evidence_precision_v2")},
                  "RAG": {k: r[k] for k in ("joint_v1", "joint_v2", "evidence_recall_v1", "evidence_recall_v2", "evidence_precision_v1", "evidence_precision_v2")}}
    # ---- E12B (frozen: guard contradiction >=3 cases below P0 disqualifies; adoption needs net>=+9 & F1 ok; near-tie +1..+8; <=0 no benefit; <=-5 harmful)
    def e12b_status(net, dC_, dF_):
        if dC_ <= -3: return "DISQUALIFIED"
        if net >= 9 and dF_ >= -0.03: return "ADOPTION-ELIGIBLE"
        if 1 <= net <= 8 or (net >= 9 and dF_ < -0.03): return "NEAR-TIE"
        return "NO BENEFIT" if net > -5 else "HARMFUL"
    b = {}
    for arm in ("gpt_p1", "gpt_p2", "gpt_p3"):
        u0, u = units["E12B::gpt_p0"], units[f"E12B::{arm}"]; sel = E12B["selection_rule"][arm]
        b[arm] = {"stored_status": sel["status"], "v1_net": u["joint_v1"] - u0["joint_v1"], "v2_net": u["joint_v2"] - u0["joint_v2"],
                  "v1_status_recomputed": e12b_status(u["joint_v1"] - u0["joint_v1"], sel["contradiction_delta_cases"], sel["macro_f1_delta"]),
                  "v2_status": e12b_status(u["joint_v2"] - u0["joint_v2"], sel["contradiction_delta_cases"], sel["macro_f1_delta"]),
                  "evidence_recall_delta_pp_v1_v2": [(u["evidence_recall_v1"] - u0["evidence_recall_v1"]) * 100, (u["evidence_recall_v2"] - u0["evidence_recall_v2"]) * 100],
                  "evidence_precision_delta_pp_v1_v2": [(u["evidence_precision_v1"] - u0["evidence_precision_v1"]) * 100, (u["evidence_precision_v2"] - u0["evidence_precision_v2"]) * 100]}
    out["E12B"] = b
    # ---- E12C (frozen: 5 confirmation criteria; net<=0 or any guard fail -> NO CONFIRMATION; +1..+4 weak; >=+5 strong)
    p0, p3 = units["E12C::gpt_p0"], units["E12C::gpt_p3"]
    def e12c_band(net, er, ep, dC_, dF_):
        ok = dC_ > -3 and net > 0 and dF_ >= -0.03 and er >= -0.03 and ep >= -0.03
        return "STRONG" if ok and net >= 5 else "WEAK" if ok else "NO CONFIRMATION"
    dC_c = E12C["contradiction"]["p3"]["correct"] - E12C["contradiction"]["p0"]["correct"]; dF_c = E12C["E12C_standalone"]["p3"]["macro_f1"] - E12C["E12C_standalone"]["p0"]["macro_f1"]
    c1 = {"net": p3["joint_v1"] - p0["joint_v1"], "er": p3["evidence_recall_v1"] - p0["evidence_recall_v1"], "ep": p3["evidence_precision_v1"] - p0["evidence_precision_v1"]}
    c2 = {"net": p3["joint_v2"] - p0["joint_v2"], "er": p3["evidence_recall_v2"] - p0["evidence_recall_v2"], "ep": p3["evidence_precision_v2"] - p0["evidence_precision_v2"]}
    B12, B12p = units["E12B::gpt_p0"], units["E12B::gpt_p3"]
    pooled = {"v1": [B12["joint_v1"] + p0["joint_v1"], B12p["joint_v1"] + p3["joint_v1"]], "v2": [B12["joint_v2"] + p0["joint_v2"], B12p["joint_v2"] + p3["joint_v2"]]}
    out["E12C"] = {"v1": c1 | {"band": e12c_band(c1["net"], c1["er"], c1["ep"], dC_c, dF_c), "evidence_guards_fail": [c1["er"] < -0.03, c1["ep"] < -0.03]},
                   "v2": c2 | {"band": e12c_band(c2["net"], c2["er"], c2["ep"], dC_c, dF_c), "evidence_guards_fail": [c2["er"] < -0.03, c2["ep"] < -0.03]},
                   "E12B_delta_v1_v2": [B12p["joint_v1"] - B12["joint_v1"], B12p["joint_v2"] - B12["joint_v2"]], "E12C_delta_v1_v2": [c1["net"], c2["net"]], "pooled_joint_P0_P3_of_300": pooled,
                   "manifest_direction_reversal_v2": (B12p["joint_v2"] - B12["joint_v2"]) > 0 and c2["net"] <= 0, "final_decision_KEEP_P0_unchanged": e12c_band(c2["net"], c2["er"], c2["ep"], dC_c, dF_c) == "NO CONFIRMATION"}
    # ---- E11 (A2 vs A3 joint transitions)
    a2, a3 = recs["E11::A2_control"], recs["E11::A3_selective_agent"]
    def tr(key):
        x = [r_[key] for r_ in a2]; y = [r_[key] for r_ in a3]
        b_ = sum(p and not q for p, q in zip(x, y)); c_ = sum(q and not p for p, q in zip(x, y))
        return {"a2_success": sum(x), "a3_success": sum(y), "net_joint": sum(y) - sum(x), "joint_fail_to_success": c_, "joint_success_to_fail": b_,
                "mcnemar_p": 1.0 if b_ + c_ == 0 else float(stats.binomtest(min(b_, c_), b_ + c_, .5).pvalue)}
    out["E11"] = {"v1": tr("joint_v1"), "v2": tr("joint_v2"), "e11_decision_C_rests_on": "net joint exactly zero (one recovery cancelled by one regression), no tools exercised"}
    json.dump(out, open(R / "stability_checks.json", "w"), indent=1, default=str); print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
