#!/usr/bin/env python3
"""
E11 (reconstruction-v2) -- A3 (selective agent) analysis, evaluator-side only. Mirrors
scripts/analyze_e08b_stronger_model.py's classification/evidence/joint metric methodology exactly
(same joint_success()/evidence_to_span_indices()/retrieval_contains_gold() functions), applied to
the full 150-row A3 result table built by scripts/run_e11_selective_agent.py.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from sklearn.metrics import confusion_matrix, f1_score, recall_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.metrics import wilson_score_interval  # noqa: E402

LABELS = ["Entailment", "Contradiction", "NotMentioned"]
E07_DIR = REPO / "experiments/E07_standard_rag"
E11_DIR = REPO / "experiments/E11_selective_agent_evaluation"
RESULTS_DIR = E11_DIR / "results"
CASES_PATH = RESULTS_DIR / "run_E11_A3_train_cases.jsonl"
TAU_EVIDENCE = 0.5


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


def main() -> int:
    cases = [json.loads(l) for l in open(CASES_PATH)]
    assert len(cases) == 150
    gold_spans_by_case = load_gold_span_indices()
    doc_spans_by_doc = load_doc_spans()
    chunk_text_by_case = load_retrieved_chunk_text()
    retrieved = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    offsets_by_case = {c["case_id"]: c["ranked_chunk_offsets"] for c in retrieved["cases"]}
    manifest = json.load(open(REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"))
    doc_id_by_case = {c["case_id"]: c["document_id"] for c in manifest["cases"]}

    n = len(cases)
    golds = [c["gold_label"] for c in cases]
    preds = [c["a3_label"] or "PARSE_FAILED" for c in cases]

    accuracy = sum(1 for g, p in zip(golds, preds) if g == p) / n
    macro_f1 = f1_score(golds, preds, labels=LABELS, average="macro", zero_division=0)
    per_class_recall = dict(zip(LABELS, recall_score(golds, preds, labels=LABELS,
                                                       average=None, zero_division=0)))
    cm = confusion_matrix(golds, preds, labels=LABELS).tolist()
    c_n = sum(1 for g in golds if g == "Contradiction")
    c_hits = sum(1 for g, p in zip(golds, preds) if g == "Contradiction" and p == "Contradiction")
    c_recall = c_hits / c_n if c_n else 0.0
    c_ci = wilson_score_interval(c_hits, c_n) if c_n else (0.0, 0.0)

    evidence_bearing_hits = 0
    evidence_bearing_total = 0
    precision_claims: list[bool] = []
    joint_hits = 0
    joint_by_class: dict[str, list[int]] = {label: [0, 0] for label in LABELS}
    rows = []

    for c in cases:
        cid = c["case_id"]
        doc_id = doc_id_by_case[cid]
        doc_spans = doc_spans_by_doc[doc_id]
        gold_span_idx = gold_spans_by_case[cid]
        chunk_offsets = offsets_by_case[cid]
        chunk_texts = chunk_text_by_case[cid]

        pred_span_idx = evidence_to_span_indices(c.get("a3_evidence") or [], chunk_texts,
                                                  chunk_offsets, doc_spans)
        e_hit = bool(set(gold_span_idx) & set(pred_span_idx)) if gold_span_idx else None

        if gold_span_idx:
            evidence_bearing_total += 1
            if e_hit:
                evidence_bearing_hits += 1
        if c.get("a3_evidence"):
            precision_claims.append(bool(set(gold_span_idx) & set(pred_span_idx)))

        j_ok = joint_success(c["gold_label"], c["a3_label"], gold_span_idx, pred_span_idx)
        joint_by_class[c["gold_label"]][1] += 1
        if j_ok:
            joint_hits += 1
            joint_by_class[c["gold_label"]][0] += 1

        row = dict(c)
        row["a3_gold_evidence_overlap"] = e_hit
        row["a3_joint_success"] = j_ok
        rows.append(row)

    evidence_recall = evidence_bearing_hits / evidence_bearing_total if evidence_bearing_total else 0.0
    evidence_precision = sum(precision_claims) / len(precision_claims) if precision_claims else 0.0
    joint_overall = joint_hits / n
    joint_by_class_rate = {label: (h / t if t else 0.0) for label, (h, t) in joint_by_class.items()}

    with open(RESULTS_DIR / "a3_scored_cases.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")

    triggered_rows = [r for r in rows if r["triggered"]]
    total_incremental_cost = sum(r["incremental_cost_usd"] for r in triggered_rows)
    total_incremental_input_tokens = sum(r["incremental_input_tokens"] for r in triggered_rows)
    total_incremental_output_tokens = sum(r["incremental_output_tokens"] for r in triggered_rows)

    summary = {
        "n_cases": n,
        "classification": {
            "accuracy": accuracy, "macro_f1": macro_f1, "per_class_recall": per_class_recall,
            "contradiction_recall": c_recall, "contradiction_recall_ci95": list(c_ci),
            "contradiction_n": c_n,
            "confusion_matrix": {"labels": LABELS, "matrix": cm},
        },
        "evidence": {
            "evidence_bearing_n": evidence_bearing_total,
            "evidence_recall": evidence_recall, "evidence_precision": evidence_precision,
        },
        "joint": {"overall": joint_overall, "by_class": joint_by_class_rate},
        "agent_behavior": {
            "n_triggered": len(triggered_rows),
            "escalation_rate": len(triggered_rows) / n,
            "mean_steps": statistics.mean(r["agent_steps"] for r in triggered_rows),
            "median_steps": statistics.median(r["agent_steps"] for r in triggered_rows),
            "mean_model_calls": statistics.mean(r["agent_model_calls"] for r in triggered_rows),
            "mean_tool_calls": statistics.mean(r["tool_calls"] for r in triggered_rows),
            "tool_usage_counts": {
                "FOLLOW_CROSS_REFERENCE": sum(r["tool_names"].count("FOLLOW_CROSS_REFERENCE") for r in triggered_rows),
                "GET_MORE_CANDIDATES": sum(r["tool_names"].count("GET_MORE_CANDIDATES") for r in triggered_rows),
            },
            "cases_no_tool_before_final": sum(1 for r in triggered_rows if r["tool_calls"] == 0),
            "fallback_count": sum(1 for r in triggered_rows if r["fallback_to_a2"]),
            "fallback_rate": sum(1 for r in triggered_rows if r["fallback_to_a2"]) / len(triggered_rows),
            "stop_reason_distribution": {
                reason: sum(1 for r in triggered_rows if r["stop_reason"] == reason)
                for reason in set(r["stop_reason"] for r in triggered_rows)
            },
        },
        "incremental_cost_usd": {
            "total": total_incremental_cost,
            "per_escalated_case": total_incremental_cost / len(triggered_rows) if triggered_rows else 0.0,
            "per_agent_call": total_incremental_cost / sum(r["agent_model_calls"] for r in triggered_rows)
                if sum(r["agent_model_calls"] for r in triggered_rows) else 0.0,
        },
        "incremental_tokens": {
            "total_input": total_incremental_input_tokens,
            "total_output": total_incremental_output_tokens,
        },
        "incremental_latency_s": {
            "mean": statistics.mean(r["incremental_latency_s"] for r in triggered_rows),
            "median": statistics.median(r["incremental_latency_s"] for r in triggered_rows),
            "p90": sorted(r["incremental_latency_s"] for r in triggered_rows)[int(0.9 * len(triggered_rows))],
            "max": max(r["incremental_latency_s"] for r in triggered_rows),
        },
    }
    with open(RESULTS_DIR / "run_E11_A3_train.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"wrote {RESULTS_DIR / 'a3_scored_cases.jsonl'}")
    print(f"wrote {RESULTS_DIR / 'run_E11_A3_train.json'}")
    print(f"accuracy={accuracy:.4f} macro_f1={macro_f1:.4f} contradiction_recall={c_recall:.4f}")
    print(f"evidence_recall={evidence_recall:.4f} evidence_precision={evidence_precision:.4f}")
    print(f"joint_overall={joint_overall:.4f}")
    print(json.dumps(summary["agent_behavior"], indent=2, default=str))
    print(json.dumps(summary["incremental_cost_usd"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
