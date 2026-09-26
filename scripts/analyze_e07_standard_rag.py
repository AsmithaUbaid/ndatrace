#!/usr/bin/env python3
"""
E07 standard RAG (A2) analysis (reconstruction-v2) -- Stage B, evaluator-side only.

Mirrors scripts/analyze_e05_full_context.py's structure (classification/structured-output/
evidence/joint metrics, length-bucket-free here since RAG context size barely varies), plus the
NEW retrieval-aware failure taxonomy E07 needs and E05 didn't (A retrieval-limited / B
reasoning-limited / C evidence-selection / D structured-output / E mixed).

Evaluator-side only: gold_span_indices are used here to determine whether the frozen retrieved
context actually contained the gold evidence -- this was NEVER passed to the model at inference
time (the model only ever saw the retrieved chunk text, per the frozen retrieval-context
artifact).
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
RESULTS_DIR = E07_DIR / "results"
CASES_PATH = RESULTS_DIR / "run_E07_A2_train_cases.jsonl"
TAU_EVIDENCE = 0.5

EXCEPTION_KEYWORDS = ("except", "provided that", "unless", "notwithstanding", "other than",
                      "carve-out", "carve out")


def load_cases() -> list[dict]:
    return [json.loads(line) for line in open(CASES_PATH)]


def load_gold_span_indices() -> dict[str, list[int]]:
    gold = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json"))
    return {c["case_id"]: c["gold_span_indices"] for c in gold["cases"]}


def load_retrieved_chunk_text() -> dict[str, list[str]]:
    """The exact chunk text shown to the model, from the frozen retrieval-context artifact --
    needed to re-localize evidence quotes to absolute document offsets (the JSONL run records
    store retrieved_chunk_offsets but not the chunk text itself)."""
    retrieved = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    return {c["case_id"]: c["ranked_chunk_text"] for c in retrieved["cases"]}


def load_doc_spans() -> dict[int, list[list[int]]]:
    train = json.load(open(REPO / "data/contractnli/train.json"))
    return {d["id"]: d["spans"] for d in train["documents"]}


def evidence_to_span_indices(evidence: list[str], chunk_texts: list[str],
                              chunk_offsets: list[list[int]],
                              doc_spans: list[list[int]]) -> list[int]:
    """Maps verbatim evidence quotes to doc.spans indices. The model saw retrieved-chunk text
    (already extracted from the document); a quote's absolute document location is resolved by
    searching within each chunk's own text and mapping back using that chunk's real document
    offset (chunk_offsets), then overlap-testing against the document's annotated span list --
    the same interval-overlap semantics used throughout reconstruction-v2 (E04, E05, E06)."""
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
    """None for NotMentioned (no gold evidence exists by construction, E00 semantics)."""
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
    """A/B/C/D/E taxonomy -- new for E07 (E05 had no retrieval step)."""
    if row["parse_status"] == "invalid":
        return "D_structured_output_failure"
    gold, pred = row["gold_label"], row["predicted_label"]
    if gold == pred:
        if gold in ("Entailment", "Contradiction") and row.get("evidence_valid") is False:
            return "C_evidence_selection_failure"
        return "n/a (correct)"
    # Wrong label.
    if row["retrieval_contains_gold"] is False:
        return "A_retrieval_limited"
    if row["retrieval_contains_gold"] is True:
        return "B_reasoning_limited"
    # retrieval_contains_gold is None -> gold is NotMentioned, wrong label with no evidence to miss.
    return "B_reasoning_limited"


def classify_failure_family(row: dict) -> str:
    gold, pred = row["gold_label"], row["predicted_label"]
    if row["parse_status"] == "invalid":
        return "structured_output_issue"
    if gold == pred:
        return "n/a (correct)"
    if pred == "NotMentioned" and gold in ("Entailment", "Contradiction"):
        if row["retrieval_contains_gold"] is False:
            return "retrieval_miss (NotMentioned overprediction, evidence absent)"
        return "NotMentioned_overprediction (evidence was present)"
    if row.get("evidence") and row.get("evidence_all_verbatim") is False:
        return "evidence_paraphrasing"
    ctx_lower = row.get("_context_lower") or ""
    if gold == "Contradiction" and any(k in ctx_lower for k in EXCEPTION_KEYWORDS):
        return "exception_carveout_candidate"
    if row["retrieval_contains_gold"] is False:
        return "retrieval_miss"
    return "reasoning_failure_evidence_present"


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
    gen_lat, retr_lat, e2e_lat = [], [], []

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
        if not correct and c.get("evidence_valid") is True and c["gold_label"] in ("Entailment", "Contradiction"):
            wrong_label_valid_evidence += 1
        if c.get("evidence") and c.get("evidence_all_verbatim") is False:
            paraphrased_count += 1

        if c.get("input_tokens"):
            input_token_lengths.append(c["input_tokens"])
        if c.get("generation_latency_ms"):
            gen_lat.append(c["generation_latency_ms"])
        if c.get("total_retrieval_latency_ms") is not None:
            retr_lat.append(c["total_retrieval_latency_ms"])
        if c.get("end_to_end_latency_ms") is not None:
            e2e_lat.append(c["end_to_end_latency_ms"])

        row = dict(c)
        row["retrieval_contains_gold"] = contains_gold
        row["evidence_hit"] = e_hit
        row["joint_success"] = j_ok
        row["_context_lower"] = " ".join(chunk_texts).lower()
        row["retrieval_aware_family"] = classify_retrieval_aware_failure(row)
        row["failure_family"] = classify_failure_family(row)
        rows.append(row)

    evidence_recall = evidence_bearing_hits / evidence_bearing_total if evidence_bearing_total else 0.0
    evidence_precision = sum(precision_claims) / len(precision_claims) if precision_claims else 0.0
    joint_overall = joint_hits / n
    joint_by_class_rate = {label: (h / t if t else 0.0) for label, (h, t) in joint_by_class.items()}

    retrieval_aware_counts = Counter(r["retrieval_aware_family"] for r in rows)
    retrieval_aware_contradiction_counts = Counter(
        r["retrieval_aware_family"] for r in rows if r["gold_label"] == "Contradiction")
    failure_families = Counter(r["failure_family"] for r in rows if r["failure_family"] != "n/a (correct)")

    csv_fields = ["case_id", "document_id", "hypothesis_id", "gold_label", "predicted_label",
                  "parse_status", "evidence_valid", "retrieval_contains_gold", "joint_success",
                  "retrieval_aware_family", "failure_family", "input_tokens",
                  "generation_latency_ms", "total_retrieval_latency_ms", "notes"]
    with open(RESULTS_DIR / "rag_failure_analysis.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            out_row = {k: r.get(k) for k in csv_fields if k != "notes"}
            out_row["notes"] = ""
            writer.writerow(out_row)

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
        "joint": {"overall": joint_overall, "by_class": joint_by_class_rate},
        "retrieval_aware_failure_counts": dict(retrieval_aware_counts),
        "retrieval_aware_failure_counts_contradiction": dict(retrieval_aware_contradiction_counts),
        "failure_family_counts": dict(failure_families),
        "input_tokens": {
            "mean": statistics.mean(input_token_lengths) if input_token_lengths else None,
            "median": statistics.median(input_token_lengths) if input_token_lengths else None,
            "p90": sorted(input_token_lengths)[int(0.9 * len(input_token_lengths))] if input_token_lengths else None,
            "max": max(input_token_lengths) if input_token_lengths else None,
        },
        "generation_latency_ms": latency_stats(gen_lat),
        "retrieval_latency_ms": latency_stats(retr_lat),
        "end_to_end_latency_ms": latency_stats(e2e_lat),
        "cost_usd": 0.0,
    }
    with open(RESULTS_DIR / "run_E07_A2_train.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"wrote {RESULTS_DIR / 'rag_failure_analysis.csv'}")
    print(f"wrote {RESULTS_DIR / 'run_E07_A2_train.json'}")
    print(f"accuracy={accuracy:.4f} macro_f1={macro_f1:.4f} contradiction_recall={c_recall:.4f}")
    print(f"strict={strict_n} recovered={recovered_n} invalid={invalid_n}")
    print(f"evidence_recall={evidence_recall:.4f} evidence_precision={evidence_precision:.4f}")
    print(f"joint_overall={joint_overall:.4f}")
    print(f"retrieval_aware_counts={dict(retrieval_aware_counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
