#!/usr/bin/env python3
"""E17B: merge immutable E17 150 + new E17B 1941 into one GPT prediction per TEST case; verify integrity; compute full-population metrics; paired GPT-vs-Qwen; failure analysis (after freeze)."""
from __future__ import annotations
import hashlib, json, sys
from collections import Counter
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e17_common as C
from evaluation import evidence_matching as EM
from pipeline.evidence_validator import validate_evidence

E17 = C.REPO / "experiments/E17_final_test"; E17B = C.REPO / "experiments/E17B_full_test_completion"; R = E17B / "results"
LABELS = C.LABELS; W = C.W; TOT = sum(W.values())
wilson = lambda k, n, z=1.96: None if not n else [round(max(0.0, (k / n + z*z/(2*n) - z*np.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))) / (1 + z*z/n)), 4), round(min(1.0, (k / n + z*z/(2*n) + z*np.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))) / (1 + z*z/n)), 4)]


def macro_f1(S):
    f = []
    for c in LABELS:
        tp = sum(s["pred"] == c and s["gold"] == c for s in S); fp = sum(s["pred"] == c and s["gold"] != c for s in S); fn = sum(s["gold"] == c and s["pred"] != c for s in S)
        f.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
    return float(np.mean(f))


def score_rows(F, rows, kind):
    out = []
    for r in rows:
        d = F["docs"][r["document_id"]]; ann = d["annotation_sets"][0]["annotations"][r["hypothesis_id"]]; gi = ann["spans"] if ann["choice"] in ("Entailment", "Contradiction") else []
        assert ann["choice"] == r["gold_label"]; ctx = d["text"]
        ev = r["evidence"] or []; pi = EM.evidence_to_span_indices(ev, [ctx], [[0, len(ctx)]], d["spans"]); v = validate_evidence(ctx, ev, r["predicted_label"] or ""); nq = len(ev); nsrc = len(v.hallucinated_quotes)
        lab = r["predicted_label"]; joint = EM.joint_success(r["gold_label"], lab, gi, pi)
        out.append({"case_id": r["case_id"], "document_id": r["document_id"], "hypothesis_id": r["hypothesis_id"], "gold": r["gold_label"], "pred": lab, "ok": lab == r["gold_label"], "joint": bool(joint), "gold_idx": gi, "pred_idx": pi, "has_ev": bool(ev), "n_quotes": nq, "n_nonsource": nsrc,
                    "gold_overlap": bool(set(gi) & set(pi)) if gi else None, "parse": r.get("parse_status", "strict"), "in_tok": r.get("input_tokens"), "out_tok": r.get("output_tokens"), "lat_ms": r.get("generation_latency_ms"), "cost": r.get("cost_usd"), "error": r.get("error_type")})
    return out


def summarize(S):
    n = len(S); by = {c: [s for s in S if s["gold"] == c] for c in LABELS}
    eb = [s for s in S if s["gold_idx"]]; pc = [s for s in S if s["has_ev"]]; tq = sum(s["n_quotes"] for s in S)
    res = {"n": n, "accuracy": sum(s["ok"] for s in S) / n, "macro_f1": macro_f1(S), "joint": sum(s["joint"] for s in S) / n, "joint_n": sum(s["joint"] for s in S),
           "recall": {c: sum(s["ok"] for s in by[c]) / len(by[c]) for c in LABELS}, "recall_counts": {c: [sum(s["ok"] for s in by[c]), len(by[c])] for c in LABELS}, "recall_wilson95": {c: wilson(sum(s["ok"] for s in by[c]), len(by[c])) for c in LABELS},
           "joint_by_class": {c: sum(s["joint"] for s in by[c]) / len(by[c]) for c in LABELS}, "joint_counts": {c: [sum(s["joint"] for s in by[c]), len(by[c])] for c in LABELS},
           "confusion_rows_gold_cols_pred": {g: {**{p: sum(s["pred"] == p for s in by[g]) for p in LABELS}, "invalid": sum(s["pred"] is None for s in by[g])} for g in LABELS},
           "evidence_recall": sum(bool(s["gold_overlap"]) for s in eb) / len(eb) if eb else None, "evidence_precision": (sum(bool(s["gold_overlap"]) for s in pc) / len(pc)) if pc else None,
           "source_valid_quote_rate": (1 - sum(s["n_nonsource"] for s in S) / tq) if tq else None, "parse_counts": dict(Counter(s["parse"] for s in S))}
    ok = [s for s in S if s["in_tok"]]
    if ok: res["ops"] = {"input_tokens_mean": float(np.mean([s["in_tok"] for s in ok])), "output_tokens_mean": float(np.mean([s["out_tok"] for s in ok])), "latency_ms_mean": float(np.mean([s["lat_ms"] for s in ok if s["lat_ms"]])),
                          "total_cost_usd": sum(s["cost"] or 0 for s in S), "cost_per_case": sum(s["cost"] or 0 for s in S) / n}
    return res


def mcnemar_exact(b, c):
    from math import comb
    n = b + c
    if n == 0: return 1.0
    k = min(b, c); p = sum(comb(n, i) for i in range(0, k + 1)) * 2 / (2 ** n)
    return min(1.0, p)


def main():
    F = C.load_frozen()
    e17_150 = [json.loads(l) for l in open(E17 / "results/run_E17_gpt_hosted_test_cases.jsonl")]
    e17b_1941 = [json.loads(l) for l in open(R / "run_E17B_gpt_cases.jsonl")]
    merged = {r["case_id"]: r for r in e17_150}; before = len(merged)
    for r in e17b_1941:
        assert r["case_id"] not in merged, "E17B case overlaps immutable E17 150"; merged[r["case_id"]] = r
    all_ids = {c["case_id"] for c in F["all"]}
    integ = {"merged_row_count": len(merged), "unique_case_ids": len(set(merged)), "duplicate_case_ids": (len(e17_150) + len(e17b_1941)) - len(merged), "missing_test_case_ids": len(all_ids - set(merged)), "extra_case_ids": len(set(merged) - all_ids),
             "gold_label_counts": dict(Counter(r["gold_label"] for r in merged.values())), "expected": {"Entailment": 968, "Contradiction": 220, "NotMentioned": 903}}
    assert integ["merged_row_count"] == 2091 and integ["unique_case_ids"] == 2091 and integ["duplicate_case_ids"] == 0 and integ["missing_test_case_ids"] == 0 and integ["extra_case_ids"] == 0 and integ["gold_label_counts"] == integ["expected"], integ
    gpt_all = score_rows(F, list(merged.values()), "llm"); G = summarize(gpt_all)
    contra = G["confusion_rows_gold_cols_pred"]["Contradiction"]; contra_summary = {"correct": G["recall_counts"]["Contradiction"], "recall": G["recall"]["Contradiction"], "joint": G["joint_counts"]["Contradiction"], "C_to_E": contra["Entailment"], "C_to_NM": contra["NotMentioned"], "invalid": contra["invalid"]}

    prior = json.load(open(E17 / "results/final_metrics.json")); rule = prior["rule_full_2091"]; qwen_rows = json.load(open(R / "../../E17_final_test/results/scored_cases.json"))["qwen"] if False else score_rows(F, [json.loads(l) for l in open(E17 / "results/run_E17_qwen_full_test_cases.jsonl")], "llm")
    Q = summarize(qwen_rows)
    comparison = {"n": 2091, "rule": {"accuracy": rule["accuracy"], "macro_f1": rule["macro_f1"], "recall": rule["recall"], "joint": rule["joint"], "evidence_recall": rule["evidence_recall"], "evidence_precision": rule["evidence_precision"], "source_valid_quote_rate": None, "parse_valid_rate": 1.0, "runtime_s": 0.18, "cost_usd": 0.0},
                  "qwen": {"accuracy": Q["accuracy"], "macro_f1": Q["macro_f1"], "recall": Q["recall"], "joint": Q["joint"], "evidence_recall": Q["evidence_recall"], "evidence_precision": Q["evidence_precision"], "source_valid_quote_rate": Q["source_valid_quote_rate"], "parse_counts": Q["parse_counts"], "runtime_s": 25650.2, "cost_usd": 0.0, "note": "API cost=$0; local compute/time NOT monetized"},
                  "gpt": {"accuracy": G["accuracy"], "macro_f1": G["macro_f1"], "recall": G["recall"], "joint": G["joint"], "evidence_recall": G["evidence_recall"], "evidence_precision": G["evidence_precision"], "source_valid_quote_rate": G["source_valid_quote_rate"], "parse_counts": G["parse_counts"], "runtime_s": None, "cost_usd": G["ops"]["total_cost_usd"] + 0}}

    # paired GPT vs Qwen (case-level, joined by case_id)
    gpt_by = {s["case_id"]: s for s in gpt_all}; qwen_by = {s["case_id"]: s for s in qwen_rows}
    def paired(subset_ids, key):
        b = c = both_r = both_w = 0
        for cid in subset_ids:
            g, q = gpt_by[cid][key], qwen_by[cid][key]
            if g and q: both_r += 1
            elif g and not q: b += 1
            elif not g and q: c += 1
            else: both_w += 1
        return {"both_correct": both_r, "gpt_correct_qwen_wrong": b, "qwen_correct_gpt_wrong": c, "both_wrong": both_w, "n": len(subset_ids), "mcnemar_p": mcnemar_exact(b, c)}
    ids_all = list(merged); ids_by_class = {c: [s["case_id"] for s in gpt_all if s["gold"] == c] for c in LABELS}
    paired_cls = paired(ids_all, "ok"); paired_joint = paired(ids_all, "joint")
    paired_by_class = {c: {"classification": paired(ids_by_class[c], "ok"), "joint": paired(ids_by_class[c], "joint")} for c in LABELS}

    sample150 = {c["case_id"] for c in F["hosted"]}
    e17_sample = {"accuracy": prior["hosted_gpt_balanced_150"]["accuracy"], "joint": prior["hosted_gpt_balanced_150"]["joint"], "recall": prior["hosted_gpt_balanced_150"]["recall"]}
    e17_std = {"accuracy": prior["hosted_gpt_standardized"]["standardized_accuracy"], "joint": prior["hosted_gpt_standardized"]["standardized_joint"]}
    full_pop = {"accuracy": G["accuracy"], "joint": G["joint"], "recall": G["recall"]}
    representativeness = {"A_e17_balanced_150": e17_sample, "B_e17_standardized_estimate": e17_std, "C_merged_full_population_2091": full_pop}

    fa = json.load(open(E17 / "results/failure_analysis.json"))
    def bucket(s):
        if s["joint"]: return None
        if s["n_nonsource"] > 0: return "source_validation_issue"
        if s["ok"]:
            return "correct_label_evidence_mismatch"
        if s["gold"] == "Contradiction": return "reasoning_failure_or_missed_provision" if s["n_quotes"] else "missed_provision"
        if s["gold"] == "NotMentioned": return "notmentioned_over_inference"
        return "reasoning_failure" if s["n_quotes"] else "missed_provision"
    all_failures = [s for s in gpt_all if not s["joint"]]
    tax = dict(Counter(bucket(s) for s in all_failures))
    contra_failures = [s for s in gpt_all if s["gold"] == "Contradiction" and not s["joint"]]
    contra_detail = {"n": len(contra_failures), "gold_text_present_note": "checked below for a sample; full detail in results/full_contradiction_failures.json",
                      "quoted_correct_clause_but_wrong_label": sum(1 for s in contra_failures if s["pred"] == "Entailment" and s["n_quotes"] > 0 and bool(s["gold_overlap"]))}
    dev = F["docs"]
    contra_dump = [{"case_id": s["case_id"], "pred": s["pred"], "n_quotes": s["n_quotes"], "gold_overlap": s["gold_overlap"], "gold_idx": s["gold_idx"]} for s in contra_failures]

    out = {"integrity": integ, "hosted_e17b_run": json.load(open(R / "run_E17B_wall.json")), "full_gpt_2091": G, "full_gpt_contradiction_220": contra_summary,
           "rule_qwen_gpt_full_comparison_2091": comparison, "paired_gpt_vs_qwen_classification": paired_cls, "paired_gpt_vs_qwen_joint": paired_joint, "paired_by_class": paired_by_class,
           "e17_sample_vs_full_population": representativeness, "failure_taxonomy_2091": tax, "n_total_failures": len(all_failures), "contradiction_failure_detail": contra_detail,
           "e15_disclosure": "unchanged: no effective selective routing (E15 outcome C); R3 not used", "e16_disclosure": "unchanged: evidence-grounded but not prompt-injection-hardened (E16 outcome B)"}
    p = R / "final_full_test_metrics.json"; p.write_text(json.dumps(out, indent=1, default=str)); (R / "final_full_test_metrics.sha256").write_text(hashlib.sha256(p.read_bytes()).hexdigest() + "\n")
    json.dump(contra_dump, open(R / "full_contradiction_failures.json", "w"), indent=1)
    print(json.dumps(integ, indent=1)); print(json.dumps(G, indent=1, default=str)[:1800]); print(json.dumps(contra_summary, indent=1))
    print(json.dumps(comparison, indent=1, default=str)); print("paired cls", paired_cls); print("paired joint", paired_joint)
    for c in LABELS: print(c, paired_by_class[c])
    print(json.dumps(representativeness, indent=1, default=str)); print(json.dumps(tax, indent=1)); print(contra_detail)

if __name__ == "__main__":
    main()
