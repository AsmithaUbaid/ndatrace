#!/usr/bin/env python3
"""
E04 rule baseline analysis (reconstruction-v2) — Stage B, evaluator-side only.

Computes classification metrics (accuracy, macro-F1, per-class recall, confusion matrix),
evidence metrics (evidence recall/precision, joint label+evidence correctness, overall and by
class), rule-fire/default coverage (overall and by gold class), and latency stats from the raw
per-case JSONL written by scripts/run_e04_rule_baseline.py. Builds the case-level failure
artifact (results/rule_failure_analysis.csv). Uses the frozen E00 evidence-hit semantics
(interval overlap against gold span indices) and the same joint-metric tau=0.5 rule already
frozen in evaluation.metrics.joint_label_evidence_correctness — reimplemented per-case here
(not calling that function directly) only because it needs a case-level breakdown, not just an
aggregate; the decision rule itself is unchanged from the frozen definition.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from sklearn.metrics import confusion_matrix, f1_score, recall_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.metrics import wilson_score_interval  # noqa: E402

LABELS = ["Entailment", "Contradiction", "NotMentioned"]
E04_DIR = REPO / "experiments/E04_rule_baseline"
RESULTS_DIR = E04_DIR / "results"
CASES_PATH = RESULTS_DIR / "run_E04_R0_train_cases.jsonl"
TAU_EVIDENCE = 0.5  # frozen joint-metric threshold, evaluation.metrics.joint_label_evidence_correctness


def load_cases() -> list[dict]:
    return [json.loads(line) for line in open(CASES_PATH)]


def evidence_hit(gold_span_indices: list[int], predicted_span_indices: list[int]) -> bool | None:
    """None for NotMentioned (no gold evidence exists by construction, E00 semantics)."""
    if not gold_span_indices:
        return None
    return bool(set(gold_span_indices) & set(predicted_span_indices))


def evidence_recall(gold_span_indices: list[int], predicted_span_indices: list[int]) -> float | None:
    if not gold_span_indices:
        return None
    overlap = set(gold_span_indices) & set(predicted_span_indices)
    return len(overlap) / len(gold_span_indices)


def joint_success(gold_label: str, predicted_label: str, gold_span_indices: list[int],
                   predicted_span_indices: list[int]) -> bool:
    """Exact reimplementation of evaluation.metrics.joint_label_evidence_correctness's
    per-case rule (frozen, E00) -- see module docstring."""
    if predicted_label != gold_label:
        return False
    if gold_label == "NotMentioned":
        return len(predicted_span_indices) == 0
    if not gold_span_indices:
        return True
    recall = evidence_recall(gold_span_indices, predicted_span_indices)
    return recall >= TAU_EVIDENCE


def classify_failure_family(row: dict) -> str:
    """Observed-category tagging from the actual case data -- no family is assumed ahead of
    time (per the instruction not to force exception/carve-out or any other predefined
    category just because E03 found it relevant on a different model)."""
    gold, pred = row["gold_label"], row["predicted_label"]
    rule_polarity = row["rule_polarity"]

    if gold == pred:
        # Correct label -- only a possible evidence-alignment issue remains.
        if gold in ("Entailment", "Contradiction") and row["evidence_hit"] is False:
            return "correct label, misaligned/wrong evidence span"
        return "n/a (fully correct)"

    if gold in ("Entailment", "Contradiction") and rule_polarity == "none_fired":
        return f"default NotMentioned overuse ({gold}->NotMentioned, no phrase matched)"

    if gold == "NotMentioned" and rule_polarity != "none_fired":
        return f"rule fired on distractor/false-positive text ({gold}->{pred}, matched " \
               f"phrase {row['matched_phrase']!r})"

    if gold == "Entailment" and pred == "Contradiction":
        return "positive case matched a negative phrase (or vice versa) -- possible conflicting/ambiguous phrasing"

    if gold == "Contradiction" and pred == "Entailment":
        return "negative case matched a positive phrase -- possible conflicting/ambiguous phrasing"

    return f"unclassified ({gold}->{pred}, rule_polarity={rule_polarity})"


def latency_stats(values: list[float]) -> dict[str, float]:
    s = sorted(values)
    p90_idx = min(int(len(s) * 0.9), len(s) - 1)
    return {"mean": statistics.mean(s), "median": statistics.median(s), "p90": s[p90_idx]}


def main() -> int:
    cases = load_cases()
    golds = [c["gold_label"] for c in cases]
    preds = [c["predicted_label"] for c in cases]

    accuracy = sum(1 for g, p in zip(golds, preds) if g == p) / len(cases)
    macro_f1 = f1_score(golds, preds, labels=LABELS, average="macro", zero_division=0)
    per_class_recall = dict(zip(LABELS, recall_score(golds, preds, labels=LABELS,
                                                       average=None, zero_division=0)))
    cm = confusion_matrix(golds, preds, labels=LABELS).tolist()

    c_successes = sum(1 for g, p in zip(golds, preds) if g == "Contradiction" and p == "Contradiction")
    c_n = sum(1 for g in golds if g == "Contradiction")
    c_recall = c_successes / c_n if c_n else 0.0
    c_ci = wilson_score_interval(c_successes, c_n) if c_n else (0.0, 0.0)

    # Rule-fire / default coverage, overall and by gold class.
    polarity_counts = Counter(c["rule_polarity"] for c in cases)
    coverage_by_gold: dict[str, Counter] = {label: Counter() for label in LABELS}
    for c in cases:
        coverage_by_gold[c["gold_label"]][c["rule_polarity"]] += 1

    # Evidence metrics -- only meaningful for evidence-bearing (Entailment/Contradiction) cases.
    rows = []
    evidence_bearing_hits = 0
    evidence_bearing_total = 0
    recalls_for_precision: list[float] = []
    joint_hits = 0
    joint_by_class: dict[str, list[int]] = {label: [0, 0] for label in LABELS}  # [hits, n]

    for c in cases:
        e_hit = evidence_hit(c["gold_span_indices"], c["predicted_span_indices"])
        j_ok = joint_success(c["gold_label"], c["predicted_label"], c["gold_span_indices"],
                              c["predicted_span_indices"])
        if j_ok:
            joint_hits += 1
        joint_by_class[c["gold_label"]][1] += 1
        if j_ok:
            joint_by_class[c["gold_label"]][0] += 1

        if e_hit is not None:
            evidence_bearing_total += 1
            if e_hit:
                evidence_bearing_hits += 1

        if c["predicted_span_indices"]:
            # Precision: of every evidence claim the rule made (including on truly
            # NotMentioned documents where a false-positive rule fire wrongly claims
            # evidence that doesn't exist), how many overlap a real gold span. Deliberately
            # NOT restricted to evidence-bearing gold cases -- a claim on a true-NotMentioned
            # case is exactly the false-positive this metric must catch.
            overlap = set(c["gold_span_indices"]) & set(c["predicted_span_indices"])
            recalls_for_precision.append(1.0 if overlap else 0.0)

        row = dict(c)
        row["correct"] = c["gold_label"] == c["predicted_label"]
        row["rule_fired"] = c["rule_polarity"] != "none_fired"
        row["evidence_hit"] = e_hit
        row["joint_success"] = j_ok
        row["failure_family"] = classify_failure_family(row)
        row["notes"] = ""
        rows.append(row)

    evidence_recall_overall = evidence_bearing_hits / evidence_bearing_total if evidence_bearing_total else 0.0
    evidence_precision_overall = (sum(recalls_for_precision) / len(recalls_for_precision)
                                   if recalls_for_precision else 0.0)
    joint_overall = joint_hits / len(cases)
    joint_by_class_rate = {label: (hits / n if n else 0.0) for label, (hits, n) in joint_by_class.items()}

    lat = latency_stats([c["latency_ms"] for c in cases])

    csv_path = RESULTS_DIR / "rule_failure_analysis.csv"
    csv_fields = ["case_id", "document_id", "hypothesis_id", "gold_label", "predicted_label",
                  "correct", "rule_fired", "rule_polarity", "matched_phrase",
                  "matched_span_start", "matched_span_end", "evidence_hit", "joint_success",
                  "failure_family", "notes"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    failure_families = Counter(r["failure_family"] for r in rows if not r["correct"])

    summary = {
        "n_cases": len(cases),
        "verified_class_balance": dict(Counter(golds)),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class_recall": per_class_recall,
        "contradiction_recall": c_recall,
        "contradiction_recall_ci95": list(c_ci),
        "contradiction_n": c_n,
        "confusion_matrix": {"labels": LABELS, "matrix": cm},
        "rule_polarity_counts": dict(polarity_counts),
        "rule_polarity_rate": {k: v / len(cases) for k, v in polarity_counts.items()},
        "coverage_by_gold_class": {label: dict(counts) for label, counts in coverage_by_gold.items()},
        "evidence_bearing_n": evidence_bearing_total,
        "evidence_recall": evidence_recall_overall,
        "evidence_precision": evidence_precision_overall,
        "joint_label_evidence_correctness_overall": joint_overall,
        "joint_label_evidence_correctness_by_class": joint_by_class_rate,
        "latency_ms": lat,
        "total_wall_seconds": json.load(open(RESULTS_DIR / "run_E04_R0_train_wall_seconds.json"))["total_wall_seconds"],
        "cost_usd": 0.0,
        "failure_families": dict(failure_families),
    }
    with open(RESULTS_DIR / "run_E04_R0_train.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"wrote {csv_path}")
    print(f"wrote {RESULTS_DIR / 'run_E04_R0_train.json'}")
    print(f"accuracy={accuracy:.4f} macro_f1={macro_f1:.4f} contradiction_recall={c_recall:.4f}")
    print(f"evidence_recall={evidence_recall_overall:.4f} evidence_precision={evidence_precision_overall:.4f} "
          f"joint={joint_overall:.4f}")
    print(f"rule_polarity_counts={dict(polarity_counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
