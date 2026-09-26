#!/usr/bin/env python3
"""
E08B (A2-GPT5mini) analysis (reconstruction-v2) -- Stage B, evaluator-side only.

Mirrors scripts/analyze_e07_standard_rag.py's structure exactly (same classification/
structured-output/evidence/joint metrics, same retrieval-aware failure taxonomy) so the two
runs' aggregate JSON files are directly comparable by scripts/compare_qwen_gpt_e08b.py.

Evaluator-side only: gold_span_indices/doc.spans are used here to score evidence -- never sent
to the model at inference time.
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
E07_DIR = REPO / "experiments/E07_standard_rag"
E08B_DIR = REPO / "experiments/E08B_stronger_model_diagnostic"
RESULTS_DIR = E08B_DIR / "results"
CASES_PATH = RESULTS_DIR / "run_E08B_A2_gpt5mini_train_cases.jsonl"
TAU_EVIDENCE = 0.5


def load_cases() -> list[dict]:
    return [json.loads(line) for line in open(CASES_PATH)]


def load_gold_span_indices() -> dict[str, list[int]]:
    gold = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json"))
    return {c["case_id"]: c["gold_span_indices"] for c in gold["cases"]}


def load_retrieved_chunk_text() -> dict[str, list[str]]:
    retrieved = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    return {c["case_id"]: c["ranked_chunk_text"] for c in retrieved["cases"]}


def load_doc_spans() -> dict[int, list[list[int]]]:
    train = json.load(open(REPO / "data/contractnli/train.json"))
    return {d["id"]: d["spans"] for d in train["documents"]}


def evidence_to_span_indices(evidence: list[str], chunk_texts: list[str],
                              chunk_offsets: list[list[int]],
                              doc_spans: list[list[int]]) -> list[int]:
    indices: set[int] = set()
    for quote in evidence:
        if not quote:
            continue
        for chunk_text, (c_start, c_end) in zip(chunk_texts, chunk_offsets):
            local_pos = chunk_text.find(quote)
            if local_pos == -1:
                continue
            abs_start = c_start + local_pos
            abs_end = abs_start + len(quote)
            for idx, (s_start, s_end) in enumerate(doc_spans):
                if min(s_end, abs_end) > max(s_start, abs_start):
                    indices.add(idx)
    return sorted(indices)


def retrieval_contains_gold(gold_span_idx: list[int], doc_spans: list[list[int]],
                             chunk_offsets: list[list[int]]) -> bool | None:
    if not gold_span_idx:
        return None
    gold_char_spans = [doc_spans[i] for i in gold_span_idx]
    for g_start, g_end in gold_char_spans:
        for c_start, c_end in chunk_offsets:
            if g_start < c_end and g_end > c_start:
                return True
    return False


def joint_success(gold_label: str, predicted_label: str | None, gold_span_idx: list[int],
                   predicted_span_idx: list[int]) -> bool:
    if predicted_label != gold_label:
        return False
    if gold_label == "NotMentioned":
        return len(predicted_span_idx) == 0
    if not gold_span_idx:
        return True
    recall = len(set(gold_span_idx) & set(predicted_span_idx)) / len(gold_span_idx)
    return recall >= TAU_EVIDENCE


def classify_retrieval_aware_failure(row: dict) -> str:
    if row["parse_status"] == "invalid":
        return "D_structured_output_failure"
    gold, pred = row["gold_label"], row["predicted_label"]
    if gold == pred:
        if gold in ("Entailment", "Contradiction") and row.get("evidence_valid") is False:
            return "C_evidence_selection_failure"
        return "n/a (correct)"
    if row["retrieval_contains_gold"] is False:
        return "A_retrieval_limited"
    if row["retrieval_contains_gold"] is True:
        return "B_reasoning_limited"
    return "B_reasoning_limited"


def latency_stats(values: list[float]) -> dict[str, float]:
    s = sorted(v for v in values if v is not None)
    if not s:
        return {"mean": None, "median": None, "p90": None, "max": None}
    p90_idx = min(int(len(s) * 0.9), len(s) - 1)
    return {"mean": statistics.mean(s), "median": statistics.median(s), "p90": s[p90_idx],
            "max": max(s)}


def main() -> int:
    cases = load_cases()
    gold_spans_by_case = load_gold_span_indices()
    doc_spans_by_doc = load_doc_spans()
    chunk_text_by_case = load_retrieved_chunk_text()

    n = len(cases)
    golds = [c["gold_label"] for c in cases]
    preds = [c["predicted_label"] or "PARSE_FAILED" for c in cases]

    accuracy = sum(1 for g, p in zip(golds, preds) if g == p) / n
    macro_f1 = f1_score(golds, preds, labels=LABELS, average="macro", zero_division=0)
    per_class_recall = dict(zip(LABELS, recall_score(golds, preds, labels=LABELS,
                                                       average=None, zero_division=0)))
    cm = confusion_matrix(golds, preds, labels=LABELS).tolist()
    c_n = sum(1 for g in golds if g == "Contradiction")
    c_hits = sum(1 for g, p in zip(golds, preds) if g == "Contradiction" and p == "Contradiction")
    c_recall = c_hits / c_n if c_n else 0.0
    c_ci = wilson_score_interval(c_hits, c_n) if c_n else (0.0, 0.0)

    strict_n = sum(1 for c in cases if c["parse_status"] == "strict")
    recovered_n = sum(1 for c in cases if c["parse_status"] == "recovered")
    invalid_n = sum(1 for c in cases if c["parse_status"] == "invalid")
    total_retries = sum(c["retry_count"] or 0 for c in cases)
    model_errors = sum(1 for c in cases if c.get("error_type") == "MODEL_ERROR")
    timeouts = sum(1 for c in cases if c.get("error_type") == "TIMEOUT")

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
    output_token_lengths = []
    gen_lat = []
    costs = []

    for c in cases:
        doc_spans = doc_spans_by_doc[c["document_id"]]
        gold_span_idx = gold_spans_by_case[c["case_id"]]
        chunk_offsets = c["retrieved_chunk_offsets"]
        chunk_texts = chunk_text_by_case[c["case_id"]]

        contains_gold = retrieval_contains_gold(gold_span_idx, doc_spans, chunk_offsets)
        pred_span_idx = evidence_to_span_indices(c.get("evidence") or [], chunk_texts,
                                                  chunk_offsets, doc_spans)
        e_hit = bool(set(gold_span_idx) & set(pred_span_idx)) if gold_span_idx else None

        if gold_span_idx:
            evidence_bearing_total += 1
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
        source_valid = c.get("evidence_valid") is True and c["gold_label"] in ("Entailment", "Contradiction")
        if not correct and source_valid:
            wrong_label_valid_evidence += 1
        if c.get("evidence") and c.get("evidence_all_verbatim") is False:
            paraphrased_count += 1

        if c.get("input_tokens"):
            input_token_lengths.append(c["input_tokens"])
        if c.get("output_tokens"):
            output_token_lengths.append(c["output_tokens"])
        if c.get("generation_latency_ms"):
            gen_lat.append(c["generation_latency_ms"])
        if c.get("cost_usd") is not None:
            costs.append(c["cost_usd"])

        row = dict(c)
        row["retrieval_contains_gold"] = contains_gold
        row["evidence_hit"] = e_hit
        row["gold_evidence_overlap"] = bool(e_hit) if gold_span_idx else None
        row["source_valid_evidence"] = c.get("evidence_valid")
        row["joint_success"] = j_ok
        row["retrieval_aware_family"] = classify_retrieval_aware_failure(row)
        rows.append(row)

    evidence_recall = evidence_bearing_hits / evidence_bearing_total if evidence_bearing_total else 0.0
    evidence_precision = sum(precision_claims) / len(precision_claims) if precision_claims else 0.0
    joint_overall = joint_hits / n
    joint_by_class_rate = {label: (h / t if t else 0.0) for label, (h, t) in joint_by_class.items()}

    retrieval_aware_counts = Counter(r["retrieval_aware_family"] for r in rows)
    retrieval_aware_contradiction_counts = Counter(
        r["retrieval_aware_family"] for r in rows if r["gold_label"] == "Contradiction")

    csv_fields = ["case_id", "document_id", "hypothesis_id", "gold_label", "predicted_label",
                  "parse_status", "source_valid_evidence", "gold_evidence_overlap",
                  "retrieval_contains_gold", "joint_success", "retrieval_aware_family",
                  "input_tokens", "output_tokens", "generation_latency_ms", "cost_usd", "notes"]
    with open(RESULTS_DIR / "gpt5mini_failure_analysis.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            out_row = {k: r.get(k) for k in csv_fields if k != "notes"}
            out_row["notes"] = ""
            writer.writerow(out_row)

    total_cost = sum(costs)
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
            "wrong_label_source_valid_evidence_count": wrong_label_valid_evidence,
            "paraphrased_evidence_count": paraphrased_count,
        },
        "joint": {"overall": joint_overall, "by_class": joint_by_class_rate},
        "retrieval_aware_failure_counts": dict(retrieval_aware_counts),
        "retrieval_aware_failure_counts_contradiction": dict(retrieval_aware_contradiction_counts),
        "input_tokens": {
            "mean": statistics.mean(input_token_lengths) if input_token_lengths else None,
            "median": statistics.median(input_token_lengths) if input_token_lengths else None,
            "p90": sorted(input_token_lengths)[int(0.9 * len(input_token_lengths))] if input_token_lengths else None,
            "max": max(input_token_lengths) if input_token_lengths else None,
        },
        "output_tokens": {
            "mean": statistics.mean(output_token_lengths) if output_token_lengths else None,
            "median": statistics.median(output_token_lengths) if output_token_lengths else None,
            "p90": sorted(output_token_lengths)[int(0.9 * len(output_token_lengths))] if output_token_lengths else None,
            "max": max(output_token_lengths) if output_token_lengths else None,
        },
        "generation_latency_ms": latency_stats(gen_lat),
        "cost_usd": {
            "total": total_cost,
            "mean_per_case": total_cost / len(costs) if costs else 0.0,
            "median_per_case": statistics.median(costs) if costs else 0.0,
            "p90_per_case": sorted(costs)[int(0.9 * len(costs))] if costs else 0.0,
            "max_per_case": max(costs) if costs else 0.0,
        },
    }
    with open(RESULTS_DIR / "run_E08B_A2_gpt5mini_train.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"wrote {RESULTS_DIR / 'gpt5mini_failure_analysis.csv'}")
    print(f"wrote {RESULTS_DIR / 'run_E08B_A2_gpt5mini_train.json'}")
    print(f"accuracy={accuracy:.4f} macro_f1={macro_f1:.4f} contradiction_recall={c_recall:.4f}")
    print(f"strict={strict_n} recovered={recovered_n} invalid={invalid_n}")
    print(f"evidence_recall={evidence_recall:.4f} evidence_precision={evidence_precision:.4f}")
    print(f"joint_overall={joint_overall:.4f}")
    print(f"total_cost=${total_cost:.4f} mean_output_tokens={summary['output_tokens']['mean']:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
