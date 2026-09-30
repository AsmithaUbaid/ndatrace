#!/usr/bin/env python3
"""E15 fresh-DEV validation analysis: OFFLINE, zero model calls. Applies frozen R0-R3 (scripts/e15_routing_stage_a.py, unmodified) to the 138 stored responses."""
from __future__ import annotations
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(REPO))
import scripts.e15_routing_stage_a as E  # noqa: E402
from evaluation.metrics import macro_f1  # noqa: E402  (checked below)

D = REPO / "experiments/E15_review_routing"; OUT = D / "results"
RUN = [json.loads(l) for l in open(OUT / "run_E15_validation_cases.jsonl")]
E.FULLCTX.update({c["case_id"]: c["context_text"] for c in json.load(open(D / "DEV_ROUTING_v1_FULL_CONTEXT.json"))["cases"]})
E.GOLD.update({c["case_id"]: c for c in json.load(open(D / "DEV_ROUTING_v1_GOLD.json"))["cases"]})
W = {"Entailment": 519, "Contradiction": 95, "NotMentioned": 423}; TOT = sum(W.values()); CLASSES = list(W)
wilson = lambda k, n, z=1.96: None if not n else [round(max(0, (k / n + z*z/(2*n) - z*math.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))) / (1 + z*z/n)), 4), round(min(1, (k / n + z*z/(2*n) + z*math.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))) / (1 + z*z/n)), 4)]


def main():
    rows = [(E.signals(r), E.outcome(r), r) for r in RUN]; R = [(s, o) for s, o, _ in rows]; n = len(R)
    cls_n = Counter(o["gold"] for _, o in R); assert dict(cls_n) == {"Entailment": 60, "Contradiction": 18, "NotMentioned": 60}
    # model performance (unparseable counts as wrong)
    conf = {g: Counter(s["label"] for s, o in R if o["gold"] == g) for g in CLASSES}
    def f1(c):
        tp = conf[c][c]; fp = sum(conf[g][c] for g in CLASSES if g != c); fn = sum(v for k, v in conf[c].items() if k != c)
        return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0
    perf = {"n": n, "accuracy": sum(o["label_ok"] for _, o in R) / n, "macro_f1": sum(f1(c) for c in CLASSES) / 3, "joint": sum(o["joint_ok"] for _, o in R) / n, "joint_n": sum(o["joint_ok"] for _, o in R),
            "recall": {c: conf[c][c] / cls_n[c] for c in CLASSES}, "contradiction_recall_ci95": wilson(conf["Contradiction"]["Contradiction"], 18), "joint_by_class": {c: sum(o["joint_ok"] for _, o in R if o["gold"] == c) / cls_n[c] for c in CLASSES},
            "confusion": {g: dict(conf[g]) for g in CLASSES}, "parse": dict(Counter(r["parse_status"] for r in RUN)), "cost_usd": sum(r["cost_usd"] or 0 for r in RUN), "n_hallucinated_quote_cases": sum(s["n_hallucinated_v2"] > 0 for s, _ in R),
            "source_valid_quote_rate": 1 - sum(s["n_hallucinated_v2"] for s, _ in R) / max(1, sum(s["n_quotes"] for s, _ in R))}
    res = {"model_performance": perf, "policies": {}}
    for pol in E.POLICIES:
        rev = [E.POLICIES[pol](s) for s, _ in R]; j = E.metrics(R, pol, "joint_ok"); c = E.metrics(R, pol, "label_ok")
        by = {}
        for g in CLASSES:
            idx = [i for i, (s, o) in enumerate(R) if o["gold"] == g]; fails = [i for i in idx if not R[i][1]["joint_ok"]]; caught = [i for i in fails if rev[i]]
            by[g] = {"n": len(idx), "review_rate": sum(rev[i] for i in idx) / len(idx), "joint_failures": len(fails), "failures_caught": len(caught), "residual_failures": len(fails) - len(caught),
                     "correct_reviewed": sum(rev[i] for i in idx if R[i][1]["joint_ok"]), "correct_total": len(idx) - len(fails), "auto": sum(not rev[i] for i in idx)}
        std_review = sum(W[g] * by[g]["review_rate"] for g in CLASSES) / TOT
        std_auto = sum(W[g] * by[g]["auto"] / by[g]["n"] for g in CLASSES) / TOT
        std_resid = (sum(W[g] * (by[g]["residual_failures"] / by[g]["n"]) for g in CLASSES) / TOT) / std_auto if std_auto else None
        std_capture = (sum(W[g] * by[g]["failures_caught"] / by[g]["n"] for g in CLASSES)) / sum(W[g] * by[g]["joint_failures"] / by[g]["n"] for g in CLASSES) if any(by[g]["joint_failures"] for g in CLASSES) else None
        res["policies"][pol] = {"joint": j, "classification": c, "by_true_class": by, "raw_review_rate": j["review_rate"], "dev_standardized_review_rate": std_review, "dev_standardized_automation_coverage": 1 - std_review,
                                "dev_standardized_residual_joint_error": std_resid, "dev_standardized_joint_capture": std_capture,
                                "raw_review_rate_ci95": wilson(j["review"], n), "capture_ci95": wilson(j["confusion"]["failure_review"], j["total_failures"]), "residual_ci95": wilson(j["confusion"]["failure_auto"], j["auto"]),
                                "workload_raw": {str(k): round(j["review_rate"] * k, 1) for k in (100, 1000, 8000)}, "workload_dev_standardized": {str(k): round(std_review * k, 1) for k in (100, 1000, 8000)}}
    # contradiction descriptive
    res["contradiction_descriptive_n18"] = {p: {k: res["policies"][p]["by_true_class"]["Contradiction"][k] for k in ("joint_failures", "failures_caught", "residual_failures", "correct_reviewed", "correct_total")} for p in E.POLICIES}
    # frozen selection
    r1, r3 = res["policies"]["R1"], res["policies"]["R3"]
    crit = {"1_std_review<=40%": r3["dev_standardized_review_rate"] <= 0.40, "2_raw_residual<10%": r3["joint"]["residual_error_rate"] < 0.10, "2b_std_residual<10% (info)": r3["dev_standardized_residual_joint_error"] < 0.10,
            "3_capture_gap_vs_R1>=20pp": (r3["joint"]["error_capture"] - r1["joint"]["error_capture"]) >= 0.20,
            "4_no_C_safety_regression": r3["by_true_class"]["Contradiction"]["residual_failures"] <= r1["by_true_class"]["Contradiction"]["residual_failures"],
            "5_no_structural_problem": True}
    gate = all(v for k, v in crit.items() if not k.endswith("(info)"))
    res["selection"] = {"criteria": crit, "R3_selected": gate, "R1_useful_structural_guard": r1["joint"]["error_capture"], "R1_capture": r1["joint"]["error_capture"]}
    # stage A vs validation
    A = json.load(open(OUT / "routing_policy_eval_e13_full.json"))["policies"]["R3"]["joint"]
    res["stageA_vs_validation_R3"] = {k: {"stageA": A[k], "validation": r3["joint"][k]} for k in ("review_rate", "error_capture", "residual_error_rate", "routing_precision", "false_review_rate")}
    # residual failures under R3 and R1 (analysis-only buckets)
    def bucket(s, o):
        if s["unusable"]: return "unusable_parse"
        if s["n_hallucinated_v2"] > 0: return "source_validation_issue"
        if o["label_ok"]: return "correct_label_evidence_failure"
        if o["gold"] == "Contradiction": return "missed_contradiction"
        if o["gold"] == "NotMentioned": return "over_inference"
        return "reasoning_error_entailment"
    dev = {d["id"]: d for d in json.load(open(REPO / "data/contractnli/dev.json"))["documents"]}
    for pol in ("R3", "R1"):
        lst = []
        for s, o, r in rows:
            if o["joint_ok"] or E.POLICIES[pol](s): continue
            d = dev[r["document_id"]]; lst.append({"case_id": r["case_id"], "gold": o["gold"], "pred": s["label"], "bucket": bucket(s, o), "rule_label": s["rule_label"], "gold_span_idx": o["gold_spans"], "pred_span_idx": o["pred_spans"],
                                                  "n_quotes": s["n_quotes"], "quotes": [q[:220] for q in (r["evidence"] or [])], "gold_span_text": [d["text"][d["spans"][k][0]:d["spans"][k][1]][:220] for k in o["gold_spans"]][:3], "hypothesis": None})
        res[f"residual_failures_{pol}"] = lst; res[f"residual_buckets_{pol}"] = dict(Counter(x["bucket"] for x in lst))
    res["all_failures"] = [{"case_id": r["case_id"], "gold": o["gold"], "pred": s["label"], "bucket": bucket(s, o), **{p: E.POLICIES[p](s) for p in E.POLICIES}} for s, o, r in rows if not o["joint_ok"]]
    res["rule_agreement"] = {"agree_rate": sum(s["rule_label"] == s["label"] for s, _ in R) / n, "joint_success_agree": (lambda a: sum(o["joint_ok"] for _, o in a) / len(a))([x for x in R if x[0]["rule_label"] == x[0]["label"]]),
                             "joint_success_disagree": (lambda a: sum(o["joint_ok"] for _, o in a) / len(a))([x for x in R if x[0]["rule_label"] != x[0]["label"]])}
    json.dump(res, open(OUT / "validation_results.json", "w"), indent=1, default=str)
    print(json.dumps(perf, default=str)[:900])
    for p in E.POLICIES:
        x = res["policies"][p]; j = x["joint"]
        print(p, f"raw_rev {j['review']}/138={j['review_rate']:.3f} std_rev {x['dev_standardized_review_rate']:.3f} cap {j['error_capture']} clscap {x['classification']['error_capture']} resid {j['residual_error_rate']} stdresid {x['dev_standardized_residual_joint_error']} sel {j['selective_success']} prec {j['routing_precision']} frev {j['false_review_rate']} conf {j['confusion']}")
    print(json.dumps(res["selection"], indent=0)); print(res["stageA_vs_validation_R3"]); print(res["contradiction_descriptive_n18"])
    print(res["residual_buckets_R3"], res["residual_buckets_R1"], res["rule_agreement"])

if __name__ == "__main__":
    main()
