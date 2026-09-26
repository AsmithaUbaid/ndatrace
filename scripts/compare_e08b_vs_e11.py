#!/usr/bin/env python3
"""
Matched paired A2 (E08B GPT-RAG) vs. A3 (E11 selective agent) comparison (reconstruction-v2).

Both use the IDENTICAL 150 TRAIN_ARCH_v1 cases; 135 of them are byte-identical (A3 reuses A2
exactly for non-triggered cases). Produces the matched metric table, case-level transitions
(overall + triggered-only, classification + joint), McNemar's exact test, and a paired bootstrap
CI on metric deltas -- same methodology as scripts/compare_qwen_gpt_e08b.py.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

from scipy import stats
from sklearn.metrics import f1_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

E08B_SUMMARY_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train.json"
E11_DIR = REPO / "experiments/E11_selective_agent_evaluation"
A3_SCORED_PATH = E11_DIR / "results/a3_scored_cases.jsonl"
E11_SUMMARY_PATH = E11_DIR / "results/run_E11_A3_train.json"
OUT_PATH = E11_DIR / "results/a2_vs_a3_paired_comparison.json"

N_BOOTSTRAP = 10_000
SEED = 900
LABELS = ["Entailment", "Contradiction", "NotMentioned"]


def mcnemar_exact(a_correct: list[bool], b_correct: list[bool]) -> dict:
    b = sum(1 for a, bb in zip(a_correct, b_correct) if a and not bb)
    c = sum(1 for a, bb in zip(a_correct, b_correct) if bb and not a)
    n_discordant = b + c
    p = 1.0 if n_discordant == 0 else stats.binomtest(min(b, c), n_discordant, 0.5, alternative="two-sided").pvalue
    return {"b_a2_only_correct": b, "c_a3_only_correct": c, "n_discordant": n_discordant,
            "p_value": float(p), "significant_at_0.05": bool(p < 0.05)}


def paired_bootstrap_delta(a2_vals, a3_vals, n_resamples=N_BOOTSTRAP, seed=SEED) -> dict:
    rng = random.Random(seed)
    n = len(a2_vals)
    deltas = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        a2_mean = statistics.mean(a2_vals[i] for i in idx)
        a3_mean = statistics.mean(a3_vals[i] for i in idx)
        deltas.append(a3_mean - a2_mean)
    deltas.sort()
    point = statistics.mean(a3_vals) - statistics.mean(a2_vals)
    return {"point_estimate": point, "ci95_low": deltas[int(0.025 * n_resamples)],
            "ci95_high": deltas[int(0.975 * n_resamples)]}


def transitions(a: list[bool], b: list[bool]) -> dict:
    return {
        "a2_wrong_a3_correct": sum(1 for x, y in zip(a, b) if not x and y),
        "a2_correct_a3_wrong": sum(1 for x, y in zip(a, b) if x and not y),
        "both_correct": sum(1 for x, y in zip(a, b) if x and y),
        "both_wrong": sum(1 for x, y in zip(a, b) if not x and not y),
    }


def main() -> int:
    rows = [json.loads(l) for l in open(A3_SCORED_PATH)]
    assert len(rows) == 150

    gold = {r["case_id"]: r["gold_label"] for r in rows}
    a2_correct = [r["a2_label"] == r["gold_label"] for r in rows]
    a3_correct = [r["a3_label"] == r["gold_label"] for r in rows]

    e08b_summary = json.load(open(E08B_SUMMARY_PATH))
    e11_summary = json.load(open(E11_SUMMARY_PATH))
    a2_cls, a3_cls = e08b_summary["classification"], e11_summary["classification"]
    a2_ev, a3_ev = e08b_summary["evidence"], e11_summary["evidence"]

    metric_table = {
        "accuracy": {"A2": a2_cls["accuracy"], "A3": a3_cls["accuracy"]},
        "macro_f1": {"A2": a2_cls["macro_f1"], "A3": a3_cls["macro_f1"]},
        "entailment_recall": {"A2": a2_cls["per_class_recall"]["Entailment"], "A3": a3_cls["per_class_recall"]["Entailment"]},
        "contradiction_recall": {"A2": a2_cls["contradiction_recall"], "A3": a3_cls["contradiction_recall"]},
        "notmentioned_recall": {"A2": a2_cls["per_class_recall"]["NotMentioned"], "A3": a3_cls["per_class_recall"]["NotMentioned"]},
        "evidence_recall": {"A2": a2_ev["evidence_recall"], "A3": a3_ev["evidence_recall"]},
        "evidence_precision": {"A2": a2_ev["evidence_precision"], "A3": a3_ev["evidence_precision"]},
        "joint_overall": {"A2": e08b_summary["joint"]["overall"], "A3": e11_summary["joint"]["overall"]},
        "joint_entailment": {"A2": e08b_summary["joint"]["by_class"]["Entailment"], "A3": e11_summary["joint"]["by_class"]["Entailment"]},
        "joint_contradiction": {"A2": e08b_summary["joint"]["by_class"]["Contradiction"], "A3": e11_summary["joint"]["by_class"]["Contradiction"]},
        "joint_notmentioned": {"A2": e08b_summary["joint"]["by_class"]["NotMentioned"], "A3": e11_summary["joint"]["by_class"]["NotMentioned"]},
        "total_cost_usd": {"A2": e08b_summary["cost_usd"]["total"], "A3": e08b_summary["cost_usd"]["total"] + e11_summary["incremental_cost_usd"]["total"]},
        "mean_generation_latency_ms": {"A2": e08b_summary["generation_latency_ms"]["mean"], "A3": e08b_summary["generation_latency_ms"]["mean"] + (e11_summary["incremental_latency_s"]["mean"] * 1000 * e11_summary["agent_behavior"]["escalation_rate"])},
    }
    for k, v in metric_table.items():
        v["delta_A3_minus_A2"] = (v["A3"] - v["A2"]) if isinstance(v["A3"], (int, float)) and isinstance(v["A2"], (int, float)) else None

    transitions_overall = transitions(a2_correct, a3_correct)

    triggered_idx = [i for i, r in enumerate(rows) if r["triggered"]]
    t_a2_correct = [a2_correct[i] for i in triggered_idx]
    t_a3_correct = [a3_correct[i] for i in triggered_idx]
    transitions_triggered = transitions(t_a2_correct, t_a3_correct)

    contradiction_idx = [i for i, r in enumerate(rows) if r["gold_label"] == "Contradiction"]
    c_a2 = [a2_correct[i] for i in contradiction_idx]
    c_a3 = [a3_correct[i] for i in contradiction_idx]
    transitions_contradiction = transitions(c_a2, c_a3)

    a3_joint = [r["a3_joint_success"] for r in rows]
    # A2's real joint value is reused directly from E08B's own gpt5mini_failure_analysis.csv
    # (the authoritative, already-computed per-case joint_success column), not re-derived here.
    import csv
    a2_failure_rows = {r["case_id"]: r for r in
                        csv.DictReader(open(REPO / "experiments/E08B_stronger_model_diagnostic/results/gpt5mini_failure_analysis.csv"))}
    a2_joint = [a2_failure_rows[r["case_id"]]["joint_success"] == "True" for r in rows]

    transitions_joint_overall = transitions(a2_joint, a3_joint)
    t_a2_joint = [a2_joint[i] for i in triggered_idx]
    t_a3_joint = [a3_joint[i] for i in triggered_idx]
    transitions_joint_triggered = transitions(t_a2_joint, t_a3_joint)

    mcnemar_overall = mcnemar_exact(a2_correct, a3_correct)
    mcnemar_joint = mcnemar_exact(a2_joint, a3_joint)
    mcnemar_contradiction = mcnemar_exact(c_a2, c_a3)

    acc_delta = paired_bootstrap_delta([1.0 if x else 0.0 for x in a2_correct],
                                        [1.0 if x else 0.0 for x in a3_correct])
    joint_delta = paired_bootstrap_delta([1.0 if x else 0.0 for x in a2_joint],
                                          [1.0 if x else 0.0 for x in a3_joint])
    contradiction_recall_delta = paired_bootstrap_delta([1.0 if x else 0.0 for x in c_a2],
                                                          [1.0 if x else 0.0 for x in c_a3])

    gold_list = [r["gold_label"] for r in rows]
    a2_pred_list = [r["a2_label"] for r in rows]
    a3_pred_list = [r["a3_label"] for r in rows]

    def macro_f1_of(g, p):
        return f1_score(g, p, labels=LABELS, average="macro", zero_division=0)

    rng = random.Random(SEED)
    n = len(rows)
    f1_deltas = []
    for _ in range(N_BOOTSTRAP):
        idx = [rng.randrange(n) for _ in range(n)]
        g_sub = [gold_list[i] for i in idx]
        a2_sub = [a2_pred_list[i] for i in idx]
        a3_sub = [a3_pred_list[i] for i in idx]
        f1_deltas.append(macro_f1_of(g_sub, a3_sub) - macro_f1_of(g_sub, a2_sub))
    f1_deltas.sort()
    macro_f1_delta = {"point_estimate": macro_f1_of(gold_list, a3_pred_list) - macro_f1_of(gold_list, a2_pred_list),
                       "ci95_low": f1_deltas[int(0.025 * N_BOOTSTRAP)], "ci95_high": f1_deltas[int(0.975 * N_BOOTSTRAP)]}

    result = {
        "n_cases": 150,
        "metric_table": metric_table,
        "transitions_overall": transitions_overall,
        "transitions_triggered_only": transitions_triggered,
        "transitions_contradiction": transitions_contradiction,
        "transitions_joint_overall": transitions_joint_overall,
        "transitions_joint_triggered_only": transitions_joint_triggered,
        "mcnemar_overall": mcnemar_overall,
        "mcnemar_joint": mcnemar_joint,
        "mcnemar_contradiction": mcnemar_contradiction,
        "bootstrap_accuracy_delta_A3_minus_A2": acc_delta,
        "bootstrap_macro_f1_delta_A3_minus_A2": macro_f1_delta,
        "bootstrap_joint_delta_A3_minus_A2": joint_delta,
        "bootstrap_contradiction_recall_delta_A3_minus_A2": contradiction_recall_delta,
    }
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"wrote {OUT_PATH}")
    print(f"Transitions overall: {transitions_overall}")
    print(f"Transitions triggered-only (15): {transitions_triggered}")
    print(f"Transitions joint overall: {transitions_joint_overall}")
    print(f"Transitions joint triggered-only: {transitions_joint_triggered}")
    print(f"McNemar overall: {mcnemar_overall}")
    print(f"McNemar joint: {mcnemar_joint}")
    print(f"Accuracy delta: {acc_delta}")
    print(f"Joint delta: {joint_delta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
