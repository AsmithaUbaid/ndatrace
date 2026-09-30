#!/usr/bin/env python3
"""
Matched paired E05 (full-context) vs. E07 (standard RAG) comparison (reconstruction-v2).

Both experiments ran the identical 150 TRAIN_ARCH_v1 cases in identical order, same model
family, same prompt, same schema, same parser -- only the input-construction architecture
differs (full document vs. retrieval_v1 top-5). This script produces the matched metric table,
case-level transition counts, McNemar's exact test, and a paired bootstrap CI on metric
differences.

Does NOT declare a winner from raw difference or p-value alone -- reports point estimates, CIs,
and effect size together, per the reconstruction brief's explicit instruction.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

from scipy import stats

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

E05_CASES_PATH = REPO / "experiments/E05_full_context/results/run_E05_A1_train_cases.jsonl"
E07_CASES_PATH = REPO / "experiments/E07_standard_rag/results/run_E07_A2_train_cases.jsonl"
E05_SUMMARY_PATH = REPO / "experiments/E05_full_context/results/run_E05_A1_train.json"
E07_SUMMARY_PATH = REPO / "experiments/E07_standard_rag/results/run_E07_A2_train.json"
OUT_PATH = REPO / "experiments/E07_standard_rag/results/e05_vs_e07_paired_comparison.json"

N_BOOTSTRAP = 10_000
SEED = 900  # distinct from every prior project seed


def load_by_case_id(path: Path) -> dict[str, dict]:
    return {json.loads(l)["case_id"]: json.loads(l) for l in open(path)}


def mcnemar_exact(a_correct: list[bool], b_correct: list[bool]) -> dict:
    """Exact two-sided binomial McNemar test on paired correctness -- same methodology as
    evaluation.metrics.mcnemar_test, computed directly on aligned boolean lists."""
    b = sum(1 for a, bb in zip(a_correct, b_correct) if a and not bb)  # A-only correct
    c = sum(1 for a, bb in zip(a_correct, b_correct) if bb and not a)  # B-only correct
    n_discordant = b + c
    if n_discordant == 0:
        p = 1.0
    else:
        p = stats.binomtest(min(b, c), n_discordant, 0.5, alternative="two-sided").pvalue
    return {"b_e05_only_correct": b, "c_e07_only_correct": c, "n_discordant": n_discordant,
            "p_value": float(p), "significant_at_0.05": bool(p < 0.05)}


def paired_bootstrap_delta(e05_vals: list[float], e07_vals: list[float],
                            n_resamples: int = N_BOOTSTRAP, seed: int = SEED) -> dict:
    """95% CI for mean(e07_vals) - mean(e05_vals) via paired resampling (same case indices
    resampled together for both arms, preserving the pairing)."""
    rng = random.Random(seed)
    n = len(e05_vals)
    deltas = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        e05_mean = statistics.mean(e05_vals[i] for i in idx)
        e07_mean = statistics.mean(e07_vals[i] for i in idx)
        deltas.append(e07_mean - e05_mean)
    deltas.sort()
    point = statistics.mean(e07_vals) - statistics.mean(e05_vals)
    lo = deltas[int(0.025 * n_resamples)]
    hi = deltas[int(0.975 * n_resamples)]
    return {"point_estimate": point, "ci95_low": lo, "ci95_high": hi}


def main() -> int:
    e05 = load_by_case_id(E05_CASES_PATH)
    e07 = load_by_case_id(E07_CASES_PATH)
    common_ids = sorted(set(e05) & set(e07))
    assert len(common_ids) == 150, f"expected 150 common cases, found {len(common_ids)}"
    assert set(e05) == set(e07), "E05 and E07 case sets differ -- not a valid matched comparison"

    e05_summary = json.load(open(E05_SUMMARY_PATH))
    e07_summary = json.load(open(E07_SUMMARY_PATH))

    gold = {cid: e05[cid]["gold_label"] for cid in common_ids}
    e05_correct = [e05[cid]["predicted_label"] == gold[cid] for cid in common_ids]
    e07_correct = [e07[cid]["predicted_label"] == gold[cid] for cid in common_ids]
    e05_joint = None  # computed from the analyze scripts' per-case CSVs if needed; using summary aggregates for the table

    # --- Matched metric table (from each experiment's own aggregate summary) ---
    e05_cls, e07_cls = e05_summary["classification"], e07_summary["classification"]
    e05_so, e07_so = e05_summary["structured_output"], e07_summary["structured_output"]
    e05_ev, e07_ev = e05_summary["evidence"], e07_summary["evidence"]
    metric_table = {
        "accuracy": {"E05": e05_cls["accuracy"], "E07": e07_cls["accuracy"]},
        "macro_f1": {"E05": e05_cls["macro_f1"], "E07": e07_cls["macro_f1"]},
        "entailment_recall": {"E05": e05_cls["per_class_recall"]["Entailment"],
                               "E07": e07_cls["per_class_recall"]["Entailment"]},
        "contradiction_recall": {"E05": e05_cls["contradiction_recall"],
                                  "E07": e07_cls["contradiction_recall"]},
        "notmentioned_recall": {"E05": e05_cls["per_class_recall"]["NotMentioned"],
                                 "E07": e07_cls["per_class_recall"]["NotMentioned"]},
        "joint_overall": {"E05": e05_summary["joint"]["overall"], "E07": e07_summary["joint"]["overall"]},
        "strict_parse_rate": {"E05": e05_so["strict_parse_validity_pct"] / 100,
                               "E07": e07_so["strict_parse_validity_pct"] / 100},
        "usable_parse_rate": {"E05": e05_so["usable_parse_validity_pct"] / 100,
                               "E07": e07_so["usable_parse_validity_pct"] / 100},
        "evidence_recall": {"E05": e05_ev["evidence_recall"], "E07": e07_ev["evidence_recall"]},
        "mean_input_tokens": {"E05": e05_summary["input_tokens"]["mean"],
                               "E07": e07_summary["input_tokens"]["mean"]},
        "median_input_tokens": {"E05": e05_summary["input_tokens"]["median"],
                                 "E07": e07_summary["input_tokens"]["median"]},
        "p90_input_tokens": {"E05": e05_summary["input_tokens"]["p90"],
                              "E07": e07_summary["input_tokens"]["p90"]},
        "mean_generation_latency_ms": {"E05": e05_summary["latency_ms"]["mean"],
                                        "E07": e07_summary["generation_latency_ms"]["mean"]},
        "median_generation_latency_ms": {"E05": e05_summary["latency_ms"]["median"],
                                          "E07": e07_summary["generation_latency_ms"]["median"]},
        "p90_generation_latency_ms": {"E05": e05_summary["latency_ms"]["p90"],
                                       "E07": e07_summary["generation_latency_ms"]["p90"]},
    }
    for k, v in metric_table.items():
        v["delta_E07_minus_E05"] = (v["E07"] - v["E05"]) if isinstance(v["E07"], (int, float)) and isinstance(v["E05"], (int, float)) else None

    # --- Case-level transitions ---
    both_correct = sum(1 for a, b in zip(e05_correct, e07_correct) if a and b)
    both_wrong = sum(1 for a, b in zip(e05_correct, e07_correct) if not a and not b)
    e05_wrong_e07_correct = sum(1 for a, b in zip(e05_correct, e07_correct) if not a and b)
    e05_correct_e07_wrong = sum(1 for a, b in zip(e05_correct, e07_correct) if a and not b)
    transitions_overall = {
        "e05_wrong_e07_correct": e05_wrong_e07_correct,
        "e05_correct_e07_wrong": e05_correct_e07_wrong,
        "both_correct": both_correct, "both_wrong": both_wrong,
    }

    contradiction_ids = [cid for cid in common_ids if gold[cid] == "Contradiction"]
    c_e05_correct = [e05[cid]["predicted_label"] == gold[cid] for cid in contradiction_ids]
    c_e07_correct = [e07[cid]["predicted_label"] == gold[cid] for cid in contradiction_ids]
    transitions_contradiction = {
        "e05_wrong_e07_correct": sum(1 for a, b in zip(c_e05_correct, c_e07_correct) if not a and b),
        "e05_correct_e07_wrong": sum(1 for a, b in zip(c_e05_correct, c_e07_correct) if a and not b),
        "both_correct": sum(1 for a, b in zip(c_e05_correct, c_e07_correct) if a and b),
        "both_wrong": sum(1 for a, b in zip(c_e05_correct, c_e07_correct) if not a and not b),
    }

    # --- McNemar (overall + Contradiction subset) ---
    mcnemar_overall = mcnemar_exact(e05_correct, e07_correct)
    mcnemar_contradiction = mcnemar_exact(c_e05_correct, c_e07_correct)

    # --- Paired bootstrap deltas ---
    e05_acc_vals = [1.0 if x else 0.0 for x in e05_correct]
    e07_acc_vals = [1.0 if x else 0.0 for x in e07_correct]
    accuracy_delta = paired_bootstrap_delta(e05_acc_vals, e07_acc_vals)

    c_e05_vals = [1.0 if x else 0.0 for x in c_e05_correct]
    c_e07_vals = [1.0 if x else 0.0 for x in c_e07_correct]
    contradiction_recall_delta = paired_bootstrap_delta(c_e05_vals, c_e07_vals)

    result = {
        "n_common_cases": len(common_ids),
        "metric_table": metric_table,
        "transitions_overall": transitions_overall,
        "transitions_contradiction": transitions_contradiction,
        "mcnemar_overall": mcnemar_overall,
        "mcnemar_contradiction": mcnemar_contradiction,
        "bootstrap_accuracy_delta_E07_minus_E05": accuracy_delta,
        "bootstrap_contradiction_recall_delta_E07_minus_E05": contradiction_recall_delta,
        "token_reduction": {
            "mean_pct": (e05_summary["input_tokens"]["mean"] - e07_summary["input_tokens"]["mean"]) / e05_summary["input_tokens"]["mean"] * 100,
            "median_pct": (e05_summary["input_tokens"]["median"] - e07_summary["input_tokens"]["median"]) / e05_summary["input_tokens"]["median"] * 100,
            "p90_pct": (e05_summary["input_tokens"]["p90"] - e07_summary["input_tokens"]["p90"]) / e05_summary["input_tokens"]["p90"] * 100,
        },
    }
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"wrote {OUT_PATH}")
    print(f"McNemar overall: {mcnemar_overall}")
    print(f"McNemar Contradiction: {mcnemar_contradiction}")
    print(f"Accuracy delta (E07-E05): {accuracy_delta}")
    print(f"Contradiction recall delta (E07-E05): {contradiction_recall_delta}")
    print(f"Transitions overall: {transitions_overall}")
    print(f"Transitions Contradiction: {transitions_contradiction}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
