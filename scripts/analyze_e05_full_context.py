#!/usr/bin/env python3
"""
E05 full-context (A1) analysis (reconstruction-v2) -- Stage B, evaluator-side only.

Computes classification metrics, structured-output metrics (strict vs. recovered vs. invalid --
never collapsed into one number), evidence metrics (Evidence Recall/Precision using ONLY
explicit returned evidence, never full-document access), joint label+evidence correctness
(overall and by class, frozen E00 tau=0.5 rule), input-length-bucketed descriptive breakdowns,
and a case-level failure-decomposition artifact allowing primary+secondary failure categories.

Evaluator-side only: never feeds anything computed here back into a prompt or model call.
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
E05_DIR = REPO / "experiments/E05_full_context"
RESULTS_DIR = E05_DIR / "results"
CASES_PATH = RESULTS_DIR / "run_E05_A1_train_cases.jsonl"
TAU_EVIDENCE = 0.5

EXCEPTION_KEYWORDS = ("except", "provided that", "unless", "notwithstanding", "other than",
                      "carve-out", "carve out")
NEGATION_KEYWORDS = (" not ", "no obligation", "shall not", "does not", "will not")


def load_cases() -> list[dict]:
    return [json.loads(line) for line in open(CASES_PATH)]


def load_doc_spans_and_text() -> dict[int, dict]:
    train = json.load(open(REPO / "data/contractnli/train.json"))
    return {doc["id"]: {"spans": doc["spans"], "text": doc["text"]} for doc in train["documents"]}


def load_gold_span_indices() -> dict[str, list[int]]:
    manifest = json.load(open(E05_DIR / "TRAIN_ARCH_v1.json"))
    train = json.load(open(REPO / "data/contractnli/train.json"))
    doc_lookup = {d["id"]: d for d in train["documents"]}
    out = {}
    for c in manifest["cases"]:
        doc = doc_lookup[c["document_id"]]
        ann = doc["annotation_sets"][0]["annotations"][c["hypothesis_id"]]
        out[c["case_id"]] = ann["spans"]
    return out


def evidence_to_span_indices(evidence: list[str], doc_text: str, doc_spans: list[list[int]]) -> list[int]:
    """Maps each verbatim evidence quote to the doc.spans indices it overlaps -- same interval-
    overlap semantics used throughout reconstruction-v2 (E04, E06). Only quotes that are real
    verbatim substrings can be located at all; non-verbatim quotes contribute no span (they are
    already flagged separately via evidence_all_verbatim)."""
    indices: set[int] = set()
    for quote in evidence:
        if not quote:
            continue
        start = doc_text.find(quote)
        if start == -1:
            continue
        end = start + len(quote)
        for idx, (s_start, s_end) in enumerate(doc_spans):
            if min(s_end, end) > max(s_start, start):
                indices.add(idx)
    return sorted(indices)


def joint_success(gold_label: str, predicted_label: str | None, gold_span_idx: list[int],
                   predicted_span_idx: list[int]) -> bool:
    """Frozen E00 rule (evaluation.metrics.joint_label_evidence_correctness), per-case."""
    if predicted_label != gold_label:
        return False
    if gold_label == "NotMentioned":
        return len(predicted_span_idx) == 0
    if not gold_span_idx:
        return True
    recall = len(set(gold_span_idx) & set(predicted_span_idx)) / len(gold_span_idx)
    return recall >= TAU_EVIDENCE


def length_bucket(tokens: int, p50: float, p90: float) -> str:
    if tokens <= p50:
        return "<=p50"
    if tokens <= p90:
        return "p50-p90"
    return ">p90"


def classify_failure_families(row: dict) -> list[str]:
    """Observed-category tagging -- primary+secondary allowed, nothing forced. Categories per
    the reconstruction brief: A classification/reasoning, B evidence-selection, C structured-
    output, D long-context-associated (descriptive only), E exception/carve-out (only if
    observed), F definition/cross-reference/multi-clause, G NotMentioned overprediction."""
    families = []
    gold, pred = row["gold_label"], row["predicted_label"]

    if row["parse_status"] == "invalid":
        families.append("C_structured_output_failure")
        return families  # no label was even produced -- no other category applies

    if gold == pred:
        if gold in ("Entailment", "Contradiction") and row.get("evidence_valid") is False:
            families.append("B_evidence_selection_failure")
        return families  # correct label -- not a classification failure regardless of evidence

    # Wrong label from here on.
    families.append("A_classification_reasoning_failure")

    if pred == "NotMentioned" and gold in ("Entailment", "Contradiction"):
        families.append("G_notmentioned_overprediction")

    ctx_lower = (row.get("_context_lower") or "")
    if gold == "Contradiction" and any(k in ctx_lower for k in EXCEPTION_KEYWORDS):
        families.append("E_exception_carveout_candidate")

    if row.get("evidence") and row.get("evidence_valid") is False:
        families.append("B_evidence_selection_failure")

    return families


def latency_stats(values: list[float]) -> dict[str, float]:
    s = sorted(values)
    p90_idx = min(int(len(s) * 0.9), len(s) - 1)
    return {"mean": statistics.mean(s), "median": statistics.median(s), "p90": s[p90_idx],
            "max": max(s)}


def main() -> int:
    cases = load_cases()
    doc_data = load_doc_spans_and_text()
    gold_spans_by_case = load_gold_span_indices()

    n = len(cases)
    golds = [c["gold_label"] for c in cases]
    preds = [c["predicted_label"] or "PARSE_FAILED" for c in cases]

    # ---- Classification metrics ----
    accuracy = sum(1 for g, p in zip(golds, preds) if g == p) / n
    macro_f1 = f1_score(golds, preds, labels=LABELS, average="macro", zero_division=0)
    per_class_recall = dict(zip(LABELS, recall_score(golds, preds, labels=LABELS,
                                                       average=None, zero_division=0)))
    cm = confusion_matrix(golds, preds, labels=LABELS).tolist()
    c_n = sum(1 for g in golds if g == "Contradiction")
    c_hits = sum(1 for g, p in zip(golds, preds) if g == "Contradiction" and p == "Contradiction")
    c_recall = c_hits / c_n if c_n else 0.0
    c_ci = wilson_score_interval(c_hits, c_n) if c_n else (0.0, 0.0)

    # ---- Structured-output metrics ----
    strict_n = sum(1 for c in cases if c["parse_status"] == "strict")
    recovered_n = sum(1 for c in cases if c["parse_status"] == "recovered")
    invalid_n = sum(1 for c in cases if c["parse_status"] == "invalid")
    total_retries = sum(c["retry_count"] or 0 for c in cases)
    model_errors = sum(1 for c in cases if c.get("error_type") == "MODEL_ERROR")
    timeouts = sum(1 for c in cases if c.get("error_type") == "TIMEOUT")

    # ---- Per-case evidence + joint scoring ----
    rows = []
    evidence_bearing_hits = 0
    evidence_bearing_total = 0
    precision_claims: list[bool] = []
    joint_hits = 0
    joint_by_class: dict[str, list[int]] = {label: [0, 0] for label in LABELS}
    correct_label_bad_evidence = 0
    wrong_label_valid_evidence = 0
    paraphrased_count = 0
    input_token_lengths = []

    for c in cases:
        doc = doc_data[c["document_id"]]
        gold_span_idx = gold_spans_by_case[c["case_id"]]
        pred_span_idx = evidence_to_span_indices(c.get("evidence") or [], doc["text"], doc["spans"])

        e_hit = None
        if gold_span_idx:  # evidence-bearing gold (Entailment/Contradiction)
            evidence_bearing_total += 1
            e_hit = bool(set(gold_span_idx) & set(pred_span_idx))
            if e_hit:
                evidence_bearing_hits += 1

        if c.get("evidence"):
            precision_claims.append(bool(set(gold_span_idx) & set(pred_span_idx)))

        j_ok = joint_success(c["gold_label"], c["predicted_label"], gold_span_idx, pred_span_idx)
        joint_by_class[c["gold_label"]][1] += 1
        if j_ok:
            joint_hits += 1
            joint_by_class[c["gold_label"]][0] += 1

        correct = c["gold_label"] == c["predicted_label"]
        if correct and c["gold_label"] in ("Entailment", "Contradiction") and c.get("evidence_valid") is False:
            correct_label_bad_evidence += 1
        if not correct and c.get("evidence_valid") is True and c["gold_label"] in ("Entailment", "Contradiction"):
            wrong_label_valid_evidence += 1
        if c.get("evidence") and c.get("evidence_all_verbatim") is False:
            paraphrased_count += 1

        if c.get("input_tokens"):
            input_token_lengths.append(c["input_tokens"])

        row = dict(c)
        row["_context_lower"] = doc["text"].lower()
        row["predicted_span_indices"] = pred_span_idx
        row["gold_span_indices"] = gold_span_idx
        row["evidence_hit"] = e_hit
        row["joint_success"] = j_ok
        row["failure_families"] = classify_failure_families(row)
        rows.append(row)

    evidence_recall = evidence_bearing_hits / evidence_bearing_total if evidence_bearing_total else 0.0
    evidence_precision = sum(precision_claims) / len(precision_claims) if precision_claims else 0.0
    joint_overall = joint_hits / n
    joint_by_class_rate = {label: (h / t if t else 0.0) for label, (h, t) in joint_by_class.items()}

    # ---- Length-bucket analysis (descriptive, correlational only) ----
    sorted_tokens = sorted(input_token_lengths)
    p50 = sorted_tokens[len(sorted_tokens) // 2] if sorted_tokens else 0
    p90 = sorted_tokens[min(int(len(sorted_tokens) * 0.9), len(sorted_tokens) - 1)] if sorted_tokens else 0

    bucket_stats = {}
    for bucket_name in ("<=p50", "p50-p90", ">p90"):
        bucket_rows = [r for r in rows if r.get("input_tokens") and
                       length_bucket(r["input_tokens"], p50, p90) == bucket_name]
        if not bucket_rows:
            continue
        b_correct = sum(1 for r in bucket_rows if r["gold_label"] == r["predicted_label"])
        b_strict = sum(1 for r in bucket_rows if r["parse_status"] == "strict")
        b_recovered = sum(1 for r in bucket_rows if r["parse_status"] == "recovered")
        b_invalid = sum(1 for r in bucket_rows if r["parse_status"] == "invalid")
        b_ev_valid = sum(1 for r in bucket_rows if r.get("evidence_valid") is True)
        b_ev_eligible = sum(1 for r in bucket_rows if r.get("evidence_valid") is not None)
        b_lat = [r["latency_ms"] for r in bucket_rows if r.get("latency_ms")]
        bucket_stats[bucket_name] = {
            "n": len(bucket_rows),
            "accuracy": b_correct / len(bucket_rows),
            "strict_parse_rate": b_strict / len(bucket_rows),
            "recovered_parse_rate": b_recovered / len(bucket_rows),
            "invalid_parse_rate": b_invalid / len(bucket_rows),
            "evidence_valid_rate": b_ev_valid / b_ev_eligible if b_ev_eligible else None,
            "mean_latency_ms": statistics.mean(b_lat) if b_lat else None,
        }

    # ---- Failure family counts (primary+secondary) ----
    family_counts = Counter()
    for r in rows:
        for fam in r["failure_families"]:
            family_counts[fam] += 1

    # ---- CSV artifact ----
    csv_fields = ["case_id", "document_id", "hypothesis_id", "gold_label", "predicted_label",
                  "parse_status", "evidence_valid", "evidence_hit", "joint_success",
                  "failure_families", "input_tokens", "latency_ms", "notes"]
    with open(RESULTS_DIR / "full_context_failure_analysis.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            out_row = {k: r.get(k) for k in csv_fields if k != "failure_families" and k != "notes"}
            out_row["failure_families"] = ";".join(r["failure_families"])
            out_row["notes"] = ""
            writer.writerow(out_row)

    lat_values = [c["latency_ms"] for c in cases if c.get("latency_ms")]

    summary = {
        "n_cases": n,
        "classification": {
            "accuracy": accuracy, "macro_f1": macro_f1, "per_class_recall": per_class_recall,
            "contradiction_recall": c_recall, "contradiction_recall_ci95": list(c_ci),
            "contradiction_n": c_n,
            "confusion_matrix": {"labels": LABELS, "matrix": cm},
        },
        "structured_output": {
            "strict_n": strict_n, "recovered_n": recovered_n, "invalid_n": invalid_n,
            "strict_parse_validity_pct": strict_n / n * 100,
            "usable_parse_validity_pct": (strict_n + recovered_n) / n * 100,
            "total_retries": total_retries, "model_errors": model_errors, "timeouts": timeouts,
        },
        "evidence": {
            "evidence_bearing_n": evidence_bearing_total,
            "evidence_recall": evidence_recall, "evidence_precision": evidence_precision,
            "correct_label_bad_evidence_count": correct_label_bad_evidence,
            "wrong_label_valid_evidence_count": wrong_label_valid_evidence,
            "paraphrased_evidence_count": paraphrased_count,
        },
        "joint": {
            "overall": joint_overall, "by_class": joint_by_class_rate,
        },
        "length_buckets": {"p50_tokens": p50, "p90_tokens": p90, "stats": bucket_stats},
        "latency_ms": latency_stats(lat_values) if lat_values else None,
        "input_tokens": {
            "mean": statistics.mean(input_token_lengths) if input_token_lengths else None,
            "median": statistics.median(input_token_lengths) if input_token_lengths else None,
            "p90": p90, "max": max(input_token_lengths) if input_token_lengths else None,
        },
        "failure_family_counts": dict(family_counts),
        "cost_usd": 0.0,
    }
    with open(RESULTS_DIR / "run_E05_A1_train.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"wrote {RESULTS_DIR / 'full_context_failure_analysis.csv'}")
    print(f"wrote {RESULTS_DIR / 'run_E05_A1_train.json'}")
    print(f"accuracy={accuracy:.4f} macro_f1={macro_f1:.4f} contradiction_recall={c_recall:.4f}")
    print(f"strict={strict_n} recovered={recovered_n} invalid={invalid_n}  "
          f"strict_validity={strict_n/n:.1%}  usable_validity={(strict_n+recovered_n)/n:.1%}")
    print(f"evidence_recall={evidence_recall:.4f} evidence_precision={evidence_precision:.4f}")
    print(f"joint_overall={joint_overall:.4f} joint_by_class={joint_by_class_rate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
