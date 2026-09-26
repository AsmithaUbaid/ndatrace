#!/usr/bin/env python3
"""
Matched paired E07 (Qwen A2) vs. E08B (GPT-5-mini A2) comparison (reconstruction-v2).

Both runs used the IDENTICAL 150 TRAIN_ARCH_v1 cases, identical retrieved context, identical
prompt/schema/parser/validator -- only the model differs. Produces: the matched metric table,
case-level transitions (overall + Contradiction + joint), the E08 failure-bucket recovery mapping
(MODEL_REASONING_LIMITED / AGENTICALLY_FIXABLE / STATIC_PIPELINE_FIXABLE), the 54-case
wrong-evidence subgroup re-analysis (split into the 4 gold-overlap / 50 non-overlap groups),
McNemar's exact test (overall + Contradiction), and a paired bootstrap CI on metric deltas.

Does NOT declare a final production decision -- reports point estimates, CIs, and effect sizes
together, per the brief's explicit instruction (no significance manufactured, no purchasing
decision made here).
"""

from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from pathlib import Path

from scipy import stats

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

E07_CASES_PATH = REPO / "experiments/E07_standard_rag/results/run_E07_A2_train_cases.jsonl"
E08B_CASES_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"
E07_SUMMARY_PATH = REPO / "experiments/E07_standard_rag/results/run_E07_A2_train.json"
E08B_SUMMARY_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train.json"
E08_BUCKET_CSV = REPO / "experiments/E08_rag_failure_analysis/results/rag_failure_analysis.csv"
E07_FULL_JOINT_CSV = REPO / "experiments/E07_standard_rag/results/rag_failure_analysis.csv"
GPT_FAILURE_CSV = REPO / "experiments/E08B_stronger_model_diagnostic/results/gpt5mini_failure_analysis.csv"
OUT_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/qwen_vs_gpt_paired_comparison.json"
OUT_BUCKET_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/e08_bucket_recovery.json"

N_BOOTSTRAP = 10_000
SEED = 900  # same seed used by compare_e05_e07.py, distinct from every prior project seed


def load_by_case_id(path: Path) -> dict[str, dict]:
    return {json.loads(l)["case_id"]: json.loads(l) for l in open(path)}


def mcnemar_exact(a_correct: list[bool], b_correct: list[bool]) -> dict:
    b = sum(1 for a, bb in zip(a_correct, b_correct) if a and not bb)
    c = sum(1 for a, bb in zip(a_correct, b_correct) if bb and not a)
    n_discordant = b + c
    if n_discordant == 0:
        p = 1.0
    else:
        p = stats.binomtest(min(b, c), n_discordant, 0.5, alternative="two-sided").pvalue
    return {"b_qwen_only_correct": b, "c_gpt_only_correct": c, "n_discordant": n_discordant,
            "p_value": float(p), "significant_at_0.05": bool(p < 0.05)}


def paired_bootstrap_delta(qwen_vals: list[float], gpt_vals: list[float],
                            n_resamples: int = N_BOOTSTRAP, seed: int = SEED) -> dict:
    rng = random.Random(seed)
    n = len(qwen_vals)
    deltas = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        q_mean = statistics.mean(qwen_vals[i] for i in idx)
        g_mean = statistics.mean(gpt_vals[i] for i in idx)
        deltas.append(g_mean - q_mean)
    deltas.sort()
    point = statistics.mean(gpt_vals) - statistics.mean(qwen_vals)
    lo = deltas[int(0.025 * n_resamples)]
    hi = deltas[int(0.975 * n_resamples)]
    return {"point_estimate": point, "ci95_low": lo, "ci95_high": hi}


def main() -> int:
    qwen = load_by_case_id(E07_CASES_PATH)
    gpt = load_by_case_id(E08B_CASES_PATH)
    common_ids = sorted(set(qwen) & set(gpt))
    assert len(common_ids) == 150, f"expected 150 common cases, found {len(common_ids)}"
    assert set(qwen) == set(gpt), "E07 and E08B case sets differ -- not a valid matched comparison"

    qwen_summary = json.load(open(E07_SUMMARY_PATH))
    gpt_summary = json.load(open(E08B_SUMMARY_PATH))

    gold = {cid: qwen[cid]["gold_label"] for cid in common_ids}
    qwen_correct = [qwen[cid]["predicted_label"] == gold[cid] for cid in common_ids]
    gpt_correct = [gpt[cid]["predicted_label"] == gold[cid] for cid in common_ids]

    gpt_failure_rows = {r["case_id"]: r for r in csv.DictReader(open(GPT_FAILURE_CSV))}
    # E08's rag_failure_analysis.csv only covers the 73 manually-reviewed cases -- used below for
    # the bucket-recovery / wrong-evidence-subgroup analyses, which are scoped to those cases by
    # definition. For joint success, E07's OWN rag_failure_analysis.csv (produced by
    # scripts/analyze_e07_standard_rag.py) already computed joint_success for ALL 150 cases -- use
    # that as the full-150 Qwen joint source instead of the 73-case E08 subset.
    qwen_bucket_rows = {r["case_id"]: r for r in csv.DictReader(open(E08_BUCKET_CSV))}
    qwen_full_joint_rows = {r["case_id"]: r for r in csv.DictReader(open(E07_FULL_JOINT_CSV))}
    assert len(qwen_full_joint_rows) == 150
    assert sum(1 for r in qwen_full_joint_rows.values() if r["joint_success"] == "True") == 50, \
        "Qwen full-150 joint-success marginal must be 50 (33.3%), matching E07's own summary"

    def qwen_joint_success(cid: str) -> bool:
        return qwen_full_joint_rows[cid]["joint_success"] == "True"

    gpt_joint = {cid: gpt_failure_rows[cid]["joint_success"] == "True" for cid in common_ids}

    # --- Matched metric table (from each run's own aggregate summary) ---
    q_cls, g_cls = qwen_summary["classification"], gpt_summary["classification"]
    q_so, g_so = qwen_summary["structured_output"], gpt_summary["structured_output"]
    q_ev, g_ev = qwen_summary["evidence"], gpt_summary["evidence"]
    q_cost, g_cost = qwen_summary.get("cost_usd", 0.0), gpt_summary["cost_usd"]["total"]
    metric_table = {
        "accuracy": {"Qwen": q_cls["accuracy"], "GPT-5-mini": g_cls["accuracy"]},
        "macro_f1": {"Qwen": q_cls["macro_f1"], "GPT-5-mini": g_cls["macro_f1"]},
        "entailment_recall": {"Qwen": q_cls["per_class_recall"]["Entailment"],
                               "GPT-5-mini": g_cls["per_class_recall"]["Entailment"]},
        "contradiction_recall": {"Qwen": q_cls["contradiction_recall"],
                                  "GPT-5-mini": g_cls["contradiction_recall"]},
        "notmentioned_recall": {"Qwen": q_cls["per_class_recall"]["NotMentioned"],
                                 "GPT-5-mini": g_cls["per_class_recall"]["NotMentioned"]},
        "joint_overall": {"Qwen": qwen_summary["joint"]["overall"], "GPT-5-mini": gpt_summary["joint"]["overall"]},
        "joint_entailment": {"Qwen": qwen_summary["joint"]["by_class"]["Entailment"],
                              "GPT-5-mini": gpt_summary["joint"]["by_class"]["Entailment"]},
        "joint_contradiction": {"Qwen": qwen_summary["joint"]["by_class"]["Contradiction"],
                                 "GPT-5-mini": gpt_summary["joint"]["by_class"]["Contradiction"]},
        "joint_notmentioned": {"Qwen": qwen_summary["joint"]["by_class"]["NotMentioned"],
                                "GPT-5-mini": gpt_summary["joint"]["by_class"]["NotMentioned"]},
        "evidence_recall": {"Qwen": q_ev["evidence_recall"], "GPT-5-mini": g_ev["evidence_recall"]},
        "evidence_precision": {"Qwen": q_ev["evidence_precision"], "GPT-5-mini": g_ev["evidence_precision"]},
        "strict_parse_rate": {"Qwen": q_so["strict_parse_validity_pct"] / 100,
                               "GPT-5-mini": g_so["strict_parse_validity_pct"] / 100},
        "usable_parse_rate": {"Qwen": q_so["usable_parse_validity_pct"] / 100,
                               "GPT-5-mini": g_so["usable_parse_validity_pct"] / 100},
        "mean_input_tokens": {"Qwen": qwen_summary["input_tokens"]["mean"],
                               "GPT-5-mini": gpt_summary["input_tokens"]["mean"]},
        "mean_output_tokens": {"Qwen": None, "GPT-5-mini": gpt_summary["output_tokens"]["mean"]},
        "mean_generation_latency_ms": {"Qwen": qwen_summary["generation_latency_ms"]["mean"],
                                        "GPT-5-mini": gpt_summary["generation_latency_ms"]["mean"]},
        "total_cost_usd": {"Qwen": q_cost, "GPT-5-mini": g_cost},
    }
    for k, v in metric_table.items():
        v["delta_GPT_minus_Qwen"] = (
            v["GPT-5-mini"] - v["Qwen"]
            if isinstance(v["GPT-5-mini"], (int, float)) and isinstance(v["Qwen"], (int, float))
            else None
        )

    # --- Case-level transitions (classification) ---
    def transitions(a: list[bool], b: list[bool]) -> dict:
        return {
            "qwen_wrong_gpt_correct": sum(1 for x, y in zip(a, b) if not x and y),
            "qwen_correct_gpt_wrong": sum(1 for x, y in zip(a, b) if x and not y),
            "both_correct": sum(1 for x, y in zip(a, b) if x and y),
            "both_wrong": sum(1 for x, y in zip(a, b) if not x and not y),
        }

    transitions_overall = transitions(qwen_correct, gpt_correct)

    contradiction_ids = [cid for cid in common_ids if gold[cid] == "Contradiction"]
    c_qwen_correct = [qwen[cid]["predicted_label"] == gold[cid] for cid in contradiction_ids]
    c_gpt_correct = [gpt[cid]["predicted_label"] == gold[cid] for cid in contradiction_ids]
    transitions_contradiction = transitions(c_qwen_correct, c_gpt_correct)

    # --- Joint transitions over the FULL 150 matched cases ---
    q_joint_vals = [qwen_joint_success(cid) for cid in common_ids]
    g_joint_vals = [gpt_joint[cid] for cid in common_ids]
    assert sum(q_joint_vals) == 50, f"Qwen joint marginal must be 50, got {sum(q_joint_vals)}"
    assert sum(g_joint_vals) == 111, f"GPT joint marginal must be 111, got {sum(g_joint_vals)}"
    transitions_joint = transitions(q_joint_vals, g_joint_vals)
    assert sum(transitions_joint.values()) == 150
    joint_common = common_ids  # kept for the bootstrap block below, now the full 150

    # --- McNemar (overall + Contradiction) ---
    mcnemar_overall = mcnemar_exact(qwen_correct, gpt_correct)
    mcnemar_contradiction = mcnemar_exact(c_qwen_correct, c_gpt_correct)

    # --- Paired bootstrap deltas ---
    q_acc = [1.0 if x else 0.0 for x in qwen_correct]
    g_acc = [1.0 if x else 0.0 for x in gpt_correct]
    accuracy_delta = paired_bootstrap_delta(q_acc, g_acc)

    c_q_vals = [1.0 if x else 0.0 for x in c_qwen_correct]
    c_g_vals = [1.0 if x else 0.0 for x in c_gpt_correct]
    contradiction_recall_delta = paired_bootstrap_delta(c_q_vals, c_g_vals)

    q_joint_bin = [1.0 if x else 0.0 for x in q_joint_vals]
    g_joint_bin = [1.0 if x else 0.0 for x in g_joint_vals]
    joint_delta = paired_bootstrap_delta(q_joint_bin, g_joint_bin) if joint_common else None

    # --- Macro-F1 delta via per-resample recomputation (needs per-class breakdown, not just a
    # scalar mean) -- approximate via resampling the (gold,pred) pairs and recomputing macro-F1
    # each time, consistent with the "effect size + CI always reported" requirement.
    from sklearn.metrics import f1_score
    LABELS = ["Entailment", "Contradiction", "NotMentioned"]
    gold_list = [gold[cid] for cid in common_ids]
    qwen_pred_list = [qwen[cid]["predicted_label"] or "PARSE_FAILED" for cid in common_ids]
    gpt_pred_list = [gpt[cid]["predicted_label"] or "PARSE_FAILED" for cid in common_ids]

    def macro_f1_of(golds_, preds_) -> float:
        return f1_score(golds_, preds_, labels=LABELS, average="macro", zero_division=0)

    rng = random.Random(SEED)
    n = len(common_ids)
    f1_deltas = []
    for _ in range(N_BOOTSTRAP):
        idx = [rng.randrange(n) for _ in range(n)]
        g_sub = [gold_list[i] for i in idx]
        q_sub = [qwen_pred_list[i] for i in idx]
        gpt_sub = [gpt_pred_list[i] for i in idx]
        f1_deltas.append(macro_f1_of(g_sub, gpt_sub) - macro_f1_of(g_sub, q_sub))
    f1_deltas.sort()
    macro_f1_delta = {
        "point_estimate": macro_f1_of(gold_list, gpt_pred_list) - macro_f1_of(gold_list, qwen_pred_list),
        "ci95_low": f1_deltas[int(0.025 * N_BOOTSTRAP)],
        "ci95_high": f1_deltas[int(0.975 * N_BOOTSTRAP)],
    }

    # =====================================================================
    # E08 failure-bucket recovery
    # =====================================================================
    bucket_recovery = {}
    for bucket in ("model_reasoning_limited", "agentically_fixable", "static_pipeline_fixable"):
        bucket_case_ids = [cid for cid, r in qwen_bucket_rows.items()
                            if r["quantification_bucket"] == bucket]
        n_bucket = len(bucket_case_ids)
        gpt_correct_n = sum(1 for cid in bucket_case_ids if gpt[cid]["predicted_label"] == gold[cid])
        gpt_joint_n = sum(1 for cid in bucket_case_ids if gpt_joint.get(cid))
        qwen_to_gpt_fixes = sum(1 for cid in bucket_case_ids if gpt[cid]["predicted_label"] == gold[cid])
        # every case in these buckets is, by construction, a Qwen ERROR (quantification_bucket is
        # only assigned to wrong-label cases) -- so "fixes" == gpt_correct_n exactly, and there are
        # no "regressions" possible within this bucket definition (Qwen was already wrong on all
        # of them). Reported explicitly to avoid double-counting the same number under two names.
        bucket_recovery[bucket] = {
            "n": n_bucket,
            "gpt_classification_correct_count": gpt_correct_n,
            "gpt_classification_correct_pct": gpt_correct_n / n_bucket * 100 if n_bucket else None,
            "gpt_joint_success_count": gpt_joint_n,
            "gpt_joint_success_pct": gpt_joint_n / n_bucket * 100 if n_bucket else None,
            "qwen_to_gpt_fixes": qwen_to_gpt_fixes,
            "qwen_to_gpt_regressions": 0,
            "note": "All cases in this bucket are, by E08's own construction, Qwen ERRORS -- "
                    "'fixes' and 'gpt_classification_correct_count' are therefore the same number; "
                    "regressions are structurally impossible within this bucket definition.",
        }

    # Contradiction-restricted bucket recovery (the 29 reviewed Contradiction failures)
    contradiction_reviewed_ids = [cid for cid, r in qwen_bucket_rows.items()
                                   if r["gold_label"] == "Contradiction"]
    n_c_reviewed = len(contradiction_reviewed_ids)
    gpt_c_correct = sum(1 for cid in contradiction_reviewed_ids if gpt[cid]["predicted_label"] == gold[cid])
    bucket_recovery["contradiction_reviewed_failures"] = {
        "n": n_c_reviewed,
        "gpt_classification_correct_count": gpt_c_correct,
        "gpt_classification_correct_pct": gpt_c_correct / n_c_reviewed * 100 if n_c_reviewed else None,
    }

    # =====================================================================
    # 54-case wrong-evidence subgroup (Group A: 4 gold-overlap, Group B: 50 non-overlap)
    # =====================================================================
    group_a_ids = [cid for cid, r in qwen_bucket_rows.items()
                   if r["source_valid_evidence"] == "True" and r["correct"] == "False"
                   and r["gold_label"] in ("Entailment", "Contradiction")
                   and r["gold_evidence_overlap"] == "True"]
    group_b_ids = [cid for cid, r in qwen_bucket_rows.items()
                   if r["source_valid_evidence"] == "True" and r["correct"] == "False"
                   and r["gold_label"] in ("Entailment", "Contradiction")
                   and r["gold_evidence_overlap"] == "False"]
    assert len(group_a_ids) == 4 and len(group_b_ids) == 50, \
        f"expected 4/50 split, got {len(group_a_ids)}/{len(group_b_ids)}"

    def subgroup_stats(ids: list[str]) -> dict:
        n_ = len(ids)
        correct_n = sum(1 for cid in ids if gpt[cid]["predicted_label"] == gold[cid])
        gpt_rows = [gpt_failure_rows[cid] for cid in ids]
        gold_overlap_n = sum(1 for r in gpt_rows if r["gold_evidence_overlap"] == "True")
        source_valid_n = sum(1 for r in gpt_rows if r["source_valid_evidence"] == "True")
        still_wrong_source_valid = sum(
            1 for cid, r in zip(ids, gpt_rows)
            if gpt[cid]["predicted_label"] != gold[cid] and r["source_valid_evidence"] == "True"
        )
        still_wrong_non_gold = sum(
            1 for cid, r in zip(ids, gpt_rows)
            if gpt[cid]["predicted_label"] != gold[cid] and r["source_valid_evidence"] == "True"
            and r["gold_evidence_overlap"] != "True"
        )
        joint_n = sum(1 for cid in ids if gpt_joint.get(cid))
        return {
            "n": n_, "gpt_classification_correct_count": correct_n,
            "gpt_classification_correct_pct": correct_n / n_ * 100 if n_ else None,
            "gpt_joint_success_count": joint_n,
            "gpt_source_valid_evidence_count": source_valid_n,
            "gpt_gold_overlap_evidence_count": gold_overlap_n,
            "gpt_still_wrong_and_source_valid_count": still_wrong_source_valid,
            "gpt_still_wrong_and_non_gold_evidence_count": still_wrong_non_gold,
        }

    wrong_evidence_subgroup = {
        "group_a_gold_overlap_4cases": subgroup_stats(group_a_ids),
        "group_b_no_gold_overlap_50cases": subgroup_stats(group_b_ids),
        "combined_54cases": subgroup_stats(group_a_ids + group_b_ids),
    }

    # =====================================================================
    # Static six (reranker-limited) -- report outcomes, preserve interpretation
    # =====================================================================
    static_six_ids = [cid for cid, r in qwen_bucket_rows.items()
                       if r["quantification_bucket"] == "static_pipeline_fixable"]
    assert len(static_six_ids) == 6
    static_six = {
        "case_ids": static_six_ids,
        "gpt_outcomes": [
            {"case_id": cid, "gold_label": gold[cid], "gpt_predicted_label": gpt[cid]["predicted_label"],
             "gpt_correct": gpt[cid]["predicted_label"] == gold[cid]}
            for cid in static_six_ids
        ],
        "gpt_correct_count": sum(1 for cid in static_six_ids if gpt[cid]["predicted_label"] == gold[cid]),
        "interpretation_note": (
            "Gold evidence was excluded from the final top-5 context by the frozen retrieval "
            "pipeline for ALL 6 of these cases (E08's own reranker-limited diagnostic, verified "
            "via BM25 top-50 re-query). A GPT failure here is NOT evidence of poor reasoning -- "
            "the information genuinely was not in the context shown to either model. A GPT "
            "success may indicate the remaining (gold-absent) context was sufficient for a "
            "stronger model to still reach the right label despite the omission, not that the "
            "omission didn't matter."
        ),
    }

    with open(OUT_BUCKET_PATH, "w") as f:
        json.dump({
            "e08_bucket_recovery": bucket_recovery,
            "wrong_evidence_subgroup_54cases": wrong_evidence_subgroup,
            "static_six_reranker_limited": static_six,
        }, f, indent=2, default=str)

    result = {
        "n_common_cases": len(common_ids),
        "metric_table": metric_table,
        "transitions_overall": transitions_overall,
        "transitions_contradiction": transitions_contradiction,
        "transitions_joint_full150": transitions_joint,
        "mcnemar_overall": mcnemar_overall,
        "mcnemar_contradiction": mcnemar_contradiction,
        "bootstrap_accuracy_delta_GPT_minus_Qwen": accuracy_delta,
        "bootstrap_macro_f1_delta_GPT_minus_Qwen": macro_f1_delta,
        "bootstrap_contradiction_recall_delta_GPT_minus_Qwen": contradiction_recall_delta,
        "bootstrap_joint_delta_GPT_minus_Qwen_full150": joint_delta,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"wrote {OUT_PATH}")
    print(f"wrote {OUT_BUCKET_PATH}")
    print(f"McNemar overall: {mcnemar_overall}")
    print(f"McNemar Contradiction: {mcnemar_contradiction}")
    print(f"Accuracy delta (GPT-Qwen): {accuracy_delta}")
    print(f"Macro-F1 delta (GPT-Qwen): {macro_f1_delta}")
    print(f"Contradiction recall delta (GPT-Qwen): {contradiction_recall_delta}")
    print(f"Transitions overall: {transitions_overall}")
    print(f"Transitions Contradiction: {transitions_contradiction}")
    print(f"Bucket recovery: {json.dumps(bucket_recovery, indent=2, default=str)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
