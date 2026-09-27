#!/usr/bin/env python3
"""E17 final analysis (offline; zero model calls). `--metrics` computes + persists ALL frozen quantitative metrics (no case inspection). `--failures` (run only AFTER metrics are frozen) dumps GPT failure detail for analysis-only inspection."""
import hashlib, json, sys
from collections import Counter
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e17_common as C
from evaluation import evidence_matching as EM
from pipeline.evidence_validator import validate_evidence

R = C.E17 / "results"; LABELS = C.LABELS; W = C.W; TOT = sum(W.values())
wilson = lambda k, n, z=1.96: None if not n else [round(max(0.0, (k / n + z*z/(2*n) - z*np.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))) / (1 + z*z/n)), 4), round(min(1.0, (k / n + z*z/(2*n) + z*np.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))) / (1 + z*z/n)), 4)]
dist = lambda a: {"n": len(a), "mean": float(np.mean(a)), "median": float(np.median(a)), "p90": float(np.percentile(a, 90)), "p95": float(np.percentile(a, 95)), "max": float(np.max(a))} if len(a) else None


def load(p): return [json.loads(l) for l in open(p)]


def score_rows(F, rows, kind):
    out = []
    for r in rows:
        d = F["docs"][r["document_id"]]; ann = d["annotation_sets"][0]["annotations"][r["hypothesis_id"]]; gi = ann["spans"] if ann["choice"] == "Entailment" or ann["choice"] == "Contradiction" else []
        assert ann["choice"] == r["gold_label"]; ctx = d["text"]
        if kind == "rule":
            sp = r["evidence_span"]; pi = sorted(k for k, (s0, s1) in enumerate(d["spans"]) if sp and min(s1, sp[1]) > max(s0, sp[0])); ev = []; nq = 0; nsrc = 0; has_ev = bool(sp)
        else:
            ev = r["evidence"] or []; pi = EM.evidence_to_span_indices(ev, [ctx], [[0, len(ctx)]], d["spans"]); v = validate_evidence(ctx, ev, r["predicted_label"] or ""); nq = len(ev); nsrc = len(v.hallucinated_quotes); has_ev = bool(ev)
        lab = r["predicted_label"]; joint = EM.joint_success(r["gold_label"], lab, gi, pi)
        out.append({"case_id": r["case_id"], "gold": r["gold_label"], "pred": lab, "ok": lab == r["gold_label"], "joint": bool(joint), "gold_idx": gi, "pred_idx": pi, "has_ev": has_ev, "n_quotes": nq, "n_nonsource": nsrc, "gold_overlap": bool(set(gi) & set(pi)) if gi else None,
                    "parse": r.get("parse_status", "strict"), "in_tok": r.get("input_tokens"), "out_tok": r.get("output_tokens"), "lat_ms": r.get("generation_latency_ms"), "wall_s": r.get("wall_latency_s"), "cost": r.get("cost_usd"), "error": r.get("error_type")})
    return out


def macro_f1(S):
    f = []
    for c in LABELS:
        tp = sum(s["pred"] == c and s["gold"] == c for s in S); fp = sum(s["pred"] == c and s["gold"] != c for s in S); fn = sum(s["gold"] == c and s["pred"] != c for s in S)
        f.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
    return float(np.mean(f))


def summarize(S, with_ops=True):
    n = len(S); by = {c: [s for s in S if s["gold"] == c] for c in LABELS}; conf = {g: {**{p: sum(s["pred"] == p for s in by[g]) for p in LABELS}, "invalid": sum(s["pred"] is None for s in by[g])} for g in LABELS}
    eb = [s for s in S if s["gold_idx"]]; pc = [s for s in S if s["has_ev"]]; tq = sum(s["n_quotes"] for s in S)
    res = {"n": n, "accuracy": sum(s["ok"] for s in S) / n, "macro_f1": macro_f1(S), "joint": sum(s["joint"] for s in S) / n, "joint_n": sum(s["joint"] for s in S),
           "recall": {c: sum(s["ok"] for s in by[c]) / len(by[c]) for c in LABELS}, "recall_counts": {c: [sum(s["ok"] for s in by[c]), len(by[c])] for c in LABELS}, "recall_wilson95": {c: wilson(sum(s["ok"] for s in by[c]), len(by[c])) for c in LABELS},
           "joint_by_class": {c: sum(s["joint"] for s in by[c]) / len(by[c]) for c in LABELS}, "joint_counts": {c: [sum(s["joint"] for s in by[c]), len(by[c])] for c in LABELS}, "joint_wilson95": {c: wilson(sum(s["joint"] for s in by[c]), len(by[c])) for c in LABELS},
           "confusion_rows_gold_cols_pred": conf, "evidence_recall": sum(bool(s["gold_overlap"]) for s in eb) / len(eb), "evidence_recall_counts": [sum(bool(s["gold_overlap"]) for s in eb), len(eb)],
           "evidence_precision": (sum(bool(s["gold_overlap"]) or False for s in pc) / len(pc)) if pc else None, "evidence_precision_counts": [sum(bool(s["gold_overlap"]) for s in pc), len(pc)],
           "source_valid_quote_rate": (1 - sum(s["n_nonsource"] for s in S) / tq) if tq else None, "cases_with_nonsource_quote": sum(s["n_nonsource"] > 0 for s in S), "parse_counts": dict(Counter(s["parse"] for s in S)), "errors": dict(Counter(s["error"] for s in S if s["error"]))}
    if with_ops and S[0]["in_tok"] is not None or any(s["in_tok"] for s in S):
        ok = [s for s in S if s["in_tok"]]; res["ops"] = {"input_tokens": dist([s["in_tok"] for s in ok]), "output_tokens": dist([s["out_tok"] for s in ok]), "latency_ms": dist([s["lat_ms"] for s in ok if s["lat_ms"]]), "wall_s": dist([s["wall_s"] for s in S if s["wall_s"]]),
                                                       "total_cost_usd": sum(s["cost"] or 0 for s in S), "cost_per_case": sum(s["cost"] or 0 for s in S) / n}
    return res


def boot(S, B=10000, seed=1700):
    rng = np.random.default_rng(seed); by = {c: [s for s in S if s["gold"] == c] for c in LABELS}
    ok = {c: np.array([s["ok"] for s in by[c]], float) for c in LABELS}; jt = {c: np.array([s["joint"] for s in by[c]], float) for c in LABELS}; w = np.array([W[c] for c in LABELS]) / TOT
    std_acc, std_j, bal_acc, bal_j, bal_f1 = [], [], [], [], []
    for _ in range(B):
        idx = {c: rng.integers(0, len(by[c]), len(by[c])) for c in LABELS}
        rc = np.array([ok[c][idx[c]].mean() for c in LABELS]); jc = np.array([jt[c][idx[c]].mean() for c in LABELS])
        std_acc.append(float(w @ rc)); std_j.append(float(w @ jc)); bal_acc.append(float(rc.mean())); bal_j.append(float(jc.mean()))
        samp = [by[c][i] for c in LABELS for i in idx[c]]; bal_f1.append(macro_f1(samp))
    ci = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    pt = lambda a: float(a)
    return {"B": B, "seed": seed, "standardized_accuracy_ci95": ci(std_acc), "standardized_joint_ci95": ci(std_j), "balanced_accuracy_ci95": ci(bal_acc), "balanced_joint_ci95": ci(bal_j), "balanced_macro_f1_ci95": ci(bal_f1)}


def metrics():
    F = C.load_frozen(); hosted_ids = [c["case_id"] for c in F["hosted"]]
    rule = score_rows(F, load(R / "run_E17_rule_full_test.jsonl"), "rule"); qwen = score_rows(F, load(R / "run_E17_qwen_full_test_cases.jsonl"), "llm"); gpt = score_rows(F, load(R / "run_E17_gpt_hosted_test_cases.jsonl"), "llm")
    assert len(rule) == 2091 and len(qwen) == 2091 and len(gpt) == 150 and [s["case_id"] for s in gpt] and {s["case_id"] for s in gpt} == set(hosted_ids)
    G = summarize(gpt); rr = load(R / "run_E17_rule_full_test.jsonl"); rw = json.load(open(R / "run_E17_rule_wall.json"))
    std = {"weights": {c: W[c] / TOT for c in LABELS}, "standardized_accuracy": sum(W[c] / TOT * G["recall"][c] for c in LABELS), "standardized_joint": sum(W[c] / TOT * G["joint_by_class"][c] for c in LABELS), "label": "TEST-prevalence-standardized estimates (NOT full-TEST measured GPT performance)"}
    std.update({k: v for k, v in boot(gpt).items()})
    C_ = [s for s in gpt if s["gold"] == "Contradiction"]; crow = G["confusion_rows_gold_cols_pred"]["Contradiction"]
    contra = {"correct": [G["recall_counts"]["Contradiction"][0], 50], "recall": G["recall"]["Contradiction"], "wilson95": G["recall_wilson95"]["Contradiction"], "joint": G["joint_counts"]["Contradiction"], "joint_wilson95": G["joint_wilson95"]["Contradiction"], "C_to_E": crow["Entailment"], "C_to_NM": crow["NotMentioned"], "invalid": crow["invalid"]}
    same150 = lambda S: [s for s in S if s["case_id"] in set(hosted_ids)]
    Q = summarize(qwen); Ru = summarize(rule, with_ops=False)
    rule_beh = {"predicted_label_counts": dict(Counter(r["predicted_label"] for r in rr)), "no_match_default_NM": sum(r["predicted_label"] == "NotMentioned" and not r["matched"] for r in rr), "default_NM_rate": sum(r["predicted_label"] == "NotMentioned" and not r["matched"] for r in rr) / len(rr),
                "cases_with_rule": sum(r["has_rule"] for r in rr), "latency_total_s": rw["wall_seconds"], "lowercase_offset_mismatch_docs": sum(not r["lower_len_equal"] for r in rr), "api_cost_usd": 0.0}
    qw = json.load(open(R / "run_E17_qwen_wall.json")) if (R / "run_E17_qwen_wall.json").exists() else None
    gw = json.load(open(R / "run_E17_gpt_wall.json")); pre = json.load(open(R / "gpt_pre_run.json")); n = 150; cpc = G["ops"]["cost_per_case"]
    out = {"frozen": C.FROZEN | {"evaluator": EM.CURRENT_EVIDENCE_EVALUATOR, "validator": "runtime_evidence_validator_v2"}, "hosted_gpt_balanced_150": G, "hosted_gpt_standardized": std, "hosted_gpt_contradiction": contra,
           "hosted_gpt_bootstrap_note": "stratified bootstrap 10,000 resamples within each 50-case class", "hosted_gpt_cost": {"pre_run_ledger": pre["pre_run_ledger_usd"], "expected": pre["expected_cost"], "conservative": pre["conservative_cost"], "actual": gw["spend_usd"], "post_run_ledger": gw["post_run_ledger_usd"], "cost_per_case": cpc, "projected_per_1000": cpc * 1000, "projected_per_8000": cpc * 8000},
           "hosted_gpt_run": gw, "qwen_full_2091": Q, "qwen_run": qw, "qwen_on_hosted_150": summarize(same150(qwen)), "rule_full_2091": Ru, "rule_behavior": rule_beh, "rule_on_hosted_150": summarize(same150(rule), with_ops=False),
           "qwen_contradiction_220": {"correct": Q["recall_counts"]["Contradiction"], "recall": Q["recall"]["Contradiction"], "wilson95": Q["recall_wilson95"]["Contradiction"], "joint": Q["joint_counts"]["Contradiction"], "confusion": Q["confusion_rows_gold_cols_pred"]["Contradiction"]},
           "rule_contradiction_220": {"correct": Ru["recall_counts"]["Contradiction"], "recall": Ru["recall"]["Contradiction"], "wilson95": Ru["recall_wilson95"]["Contradiction"], "joint": Ru["joint_counts"]["Contradiction"], "confusion": Ru["confusion_rows_gold_cols_pred"]["Contradiction"]},
           "claim_discipline": "GPT results are from a budget-constrained balanced stratified sample (n=150); local comparators were measured over the full 2,091-case TEST population."}
    p = R / "final_metrics.json"; p.write_text(json.dumps(out, indent=1, default=str)); (R / "final_metrics.sha256").write_text(hashlib.sha256(p.read_bytes()).hexdigest() + "\n")
    json.dump({"gpt": gpt, "qwen": qwen, "rule": rule}, open(R / "scored_cases.json", "w"))
    print(json.dumps({k: out[k] for k in ("hosted_gpt_standardized", "hosted_gpt_contradiction", "hosted_gpt_cost")}, indent=1, default=str))
    g = G; print("GPT", {k: g[k] for k in ("accuracy", "macro_f1", "joint", "recall", "joint_by_class", "evidence_recall", "evidence_precision", "source_valid_quote_rate", "parse_counts")})
    print("QWEN", {k: Q[k] for k in ("accuracy", "macro_f1", "joint", "recall", "joint_by_class", "evidence_recall", "evidence_precision", "parse_counts", "errors")}); print("RULE", {k: Ru[k] for k in ("accuracy", "macro_f1", "joint", "recall", "evidence_recall")}, rule_beh)


def failures():
    assert (R / "final_metrics.json").exists(), "metrics must be frozen first"; F = C.load_frozen(); S = json.load(open(R / "scored_cases.json"))["gpt"]; raw = {r["case_id"]: r for r in load(R / "run_E17_gpt_hosted_test_cases.jsonl")}; hyp = F["hyp"]; out = []
    for s in S:
        if s["joint"]: continue
        r = raw[s["case_id"]]; d = F["docs"][r["document_id"]]; ann = d["annotation_sets"][0]["annotations"][r["hypothesis_id"]]
        out.append({"case_id": s["case_id"], "gold": s["gold"], "pred": s["pred"], "label_ok": s["ok"], "parse": s["parse"], "hypothesis": hyp[r["hypothesis_id"]], "n_quotes": s["n_quotes"], "n_nonsource": s["n_nonsource"], "gold_idx": s["gold_idx"], "pred_idx": s["pred_idx"],
                    "gold_text": [d["text"][d["spans"][k][0]:d["spans"][k][1]] for k in s["gold_idx"]], "quotes": r["evidence"], "ctx_chars": r["context_chars"], "raw": r["raw_response"][:1500]})
    json.dump(out, open(R / "gpt_failure_dump.json", "w"), indent=1); print(len(out), "GPT joint failures dumped for analysis-only inspection")

if __name__ == "__main__":
    {"--metrics": metrics, "--failures": failures}[sys.argv[1]]()
