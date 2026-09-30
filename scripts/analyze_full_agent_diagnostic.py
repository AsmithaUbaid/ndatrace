#!/usr/bin/env python3
"""Score the scorer-free Stage E1 full-agent trace after execution is complete.

Primary scoring uses the frozen evidence_evaluator_v2.  A v1 bridge is also emitted because
the Stage C2 routing report's stated 111/150 baseline Joint count was calculated with the
historical exact-only evaluator; the bridge makes that pre-existing discrepancy explicit.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

from sklearn.metrics import confusion_matrix, f1_score, recall_score

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.evidence_matching import (  # noqa: E402
    EVIDENCE_EVALUATOR_V1,
    EVIDENCE_EVALUATOR_V2,
    evidence_to_span_indices,
    joint_success,
)
from pipeline.evidence_validator import validate_evidence  # noqa: E402

LABELS = ["Entailment", "Contradiction", "NotMentioned"]
OUT = REPO / "experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent"
RESULTS = OUT / "results"
BASE_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"
RETRIEVAL_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
GOLD_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json"
TRACE_PATH = RESULTS / "raw_agent_traces.jsonl"
LEDGER_PATH = REPO / "results/budget/reconstruction_spend_ledger.csv"
EXPERIMENT_ID = "E11_addendum_full_agent_E1"

LEGAL_CUES = (
    "except", "unless", "notwithstanding", "subject to", "provided that", "as defined in",
    "pursuant to", "section ", "clause ", "not ", "no ", "definition", "means ",
)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def tool_observation(summary: dict) -> str:
    if not summary.get("success"):
        return f"[{summary['tool']}] not found for {summary.get('query_or_target')!r} ({summary.get('error')})"
    texts = "; ".join(row["text"] for row in summary.get("results", []) if row.get("text"))
    return f"[{summary['tool']}] {texts}"


def accessible_source(trace: dict, retrieved: dict) -> tuple[list[str], list[list[int]], str]:
    texts = list(retrieved["ranked_chunk_text"])
    offsets = list(retrieved["ranked_chunk_offsets"])
    observations = []
    for summary in trace.get("tool_results_summary", []):
        observations.append(tool_observation(summary))
        for result in summary.get("results", []):
            if result.get("text") and result.get("source_start") is not None:
                texts.append(result["text"])
                offsets.append([result["source_start"], result["source_end"]])
    exact_prompt_context = "\n\n---\n\n".join(
        list(retrieved["ranked_chunk_text"]) + observations
    )
    return texts, offsets, exact_prompt_context


def score_prediction(label: str | None, evidence: list[str], gold: dict, texts: list[str],
                     offsets: list[list[int]], doc_spans: list[list[int]], context: str,
                     version: str) -> dict:
    pred_spans = evidence_to_span_indices(evidence, texts, offsets, doc_spans, version)
    overlap = bool(set(gold["gold_span_indices"]) & set(pred_spans)) if gold["gold_span_indices"] else None
    validation = validate_evidence(context, evidence, label or "")
    return {
        "classification_correct": label == gold["gold_label"],
        "predicted_span_indices": pred_spans,
        "gold_evidence_overlap": overlap,
        "joint_success": joint_success(
            gold["gold_label"], label, gold["gold_span_indices"], pred_spans
        ),
        "source_valid": validation.is_valid,
        "source_valid_quote_count": len(validation.verbatim_quotes),
        "source_invalid_quote_count": len(validation.hallucinated_quotes),
        "label_evidence_consistent": validation.label_evidence_consistent,
    }


def arm_metrics(rows: list[dict], prefix: str) -> dict:
    gold = [row["gold_label"] for row in rows]
    pred = [row[f"{prefix}_label"] or "PARSE_FAILED" for row in rows]
    recalls = dict(zip(LABELS, recall_score(gold, pred, labels=LABELS, average=None, zero_division=0)))
    evidence_cases = [row for row in rows if row["gold_span_indices"]]
    claims = [row for row in rows if row[f"{prefix}_evidence"]]
    quote_total = sum(len(row[f"{prefix}_evidence"]) for row in rows)
    valid_quote_total = sum(row[f"{prefix}_source_valid_quote_count"] for row in rows)
    return {
        "n": len(rows),
        "classification_correct_n": sum(row[f"{prefix}_classification_correct"] for row in rows),
        "accuracy": sum(row[f"{prefix}_classification_correct"] for row in rows) / len(rows),
        "macro_f1": f1_score(gold, pred, labels=LABELS, average="macro", zero_division=0),
        "recall": recalls,
        "recall_counts": {
            label: [sum(g == label and p == label for g, p in zip(gold, pred)), sum(g == label for g in gold)]
            for label in LABELS
        },
        "confusion_matrix_rows_gold_cols_pred": confusion_matrix(gold, pred, labels=LABELS).tolist(),
        "joint_n": sum(row[f"{prefix}_joint_success"] for row in rows),
        "joint": sum(row[f"{prefix}_joint_success"] for row in rows) / len(rows),
        "joint_by_class_counts": {
            label: [sum(row[f"{prefix}_joint_success"] for row in rows if row["gold_label"] == label),
                    sum(row["gold_label"] == label for row in rows)]
            for label in LABELS
        },
        "evidence_recall_counts": [sum(row[f"{prefix}_gold_evidence_overlap"] is True for row in evidence_cases), len(evidence_cases)],
        "evidence_recall": sum(row[f"{prefix}_gold_evidence_overlap"] is True for row in evidence_cases) / len(evidence_cases),
        "evidence_precision_counts": [sum(row[f"{prefix}_gold_evidence_overlap"] is True for row in claims), len(claims)],
        "evidence_precision": (sum(row[f"{prefix}_gold_evidence_overlap"] is True for row in claims) / len(claims)) if claims else None,
        "source_valid_case_counts": [sum(row[f"{prefix}_source_valid"] for row in rows), len(rows)],
        "source_valid_case_rate": sum(row[f"{prefix}_source_valid"] for row in rows) / len(rows),
        "source_valid_quote_counts": [valid_quote_total, quote_total],
        "source_valid_quote_rate": valid_quote_total / quote_total if quote_total else None,
    }


def delta(after: dict, before: dict) -> dict:
    return {
        "accuracy_pp": (after["accuracy"] - before["accuracy"]) * 100,
        "macro_f1_pp": (after["macro_f1"] - before["macro_f1"]) * 100,
        "joint_pp": (after["joint"] - before["joint"]) * 100,
        "Entailment_recall_pp": (after["recall"]["Entailment"] - before["recall"]["Entailment"]) * 100,
        "Contradiction_recall_pp": (after["recall"]["Contradiction"] - before["recall"]["Contradiction"]) * 100,
        "NotMentioned_recall_pp": (after["recall"]["NotMentioned"] - before["recall"]["NotMentioned"]) * 100,
        "evidence_recall_pp": (after["evidence_recall"] - before["evidence_recall"]) * 100,
        "evidence_precision_pp": (after["evidence_precision"] - before["evidence_precision"]) * 100,
        "source_valid_case_pp": (after["source_valid_case_rate"] - before["source_valid_case_rate"]) * 100,
        "source_valid_quote_pp": (after["source_valid_quote_rate"] - before["source_valid_quote_rate"]) * 100,
    }


def ratio_or_message(numerator: float, denominator: int) -> float | str:
    if denominator <= 0:
        return "not meaningful / no net recovery"
    return numerator / denominator


def main() -> int:
    traces = load_jsonl(TRACE_PATH)
    base = {row["case_id"]: row for row in load_jsonl(BASE_PATH)}
    retrieved = {row["case_id"]: row for row in json.loads(RETRIEVAL_PATH.read_text())["cases"]}
    gold = {row["case_id"]: row for row in json.loads(GOLD_PATH.read_text())["cases"]}
    docs = {row["id"]: row for row in json.loads((REPO / "data/contractnli/train.json").read_text())["documents"]}
    assert len(traces) == len({row["case_id"] for row in traces}) == 150
    assert set(base) == set(retrieved) == set(gold) == {row["case_id"] for row in traces}

    rows_by_version: dict[str, list[dict]] = {}
    for version in (EVIDENCE_EVALUATOR_V2, EVIDENCE_EVALUATOR_V1):
        rows = []
        for trace in traces:
            cid = trace["case_id"]
            b, r, g = base[cid], retrieved[cid], gold[cid]
            doc = docs[trace["document_id"]]
            base_context = "\n\n---\n\n".join(r["ranked_chunk_text"])
            agent_texts, agent_offsets, agent_context = accessible_source(trace, r)
            bs = score_prediction(b["predicted_label"], b.get("evidence") or [], g,
                                  r["ranked_chunk_text"], r["ranked_chunk_offsets"], doc["spans"],
                                  base_context, version)
            ag = score_prediction(trace["final_label"], trace.get("final_evidence") or [], g,
                                  agent_texts, agent_offsets, doc["spans"], agent_context, version)
            scores = r["ranked_chunk_rerank_scores"]
            context_lower = " ".join(r["ranked_chunk_text"]).lower()
            row = {
                "case_id": cid,
                "document_id": trace["document_id"],
                "hypothesis_id": trace["hypothesis_id"],
                "gold_label": g["gold_label"],
                "gold_span_indices": g["gold_span_indices"],
                "base_label": b["predicted_label"],
                "agent_label": trace["final_label"],
                "base_evidence": b.get("evidence") or [],
                "agent_evidence": trace.get("final_evidence") or [],
                **{f"base_{key}": value for key, value in bs.items()},
                **{f"agent_{key}": value for key, value in ag.items()},
                "classification_recovery": not bs["classification_correct"] and ag["classification_correct"],
                "classification_regression": bs["classification_correct"] and not ag["classification_correct"],
                "joint_recovery": not bs["joint_success"] and ag["joint_success"],
                "joint_regression": bs["joint_success"] and not ag["joint_success"],
                "C_recovery": g["gold_label"] == "Contradiction" and not bs["classification_correct"] and ag["classification_correct"],
                "C_regression": g["gold_label"] == "Contradiction" and bs["classification_correct"] and not ag["classification_correct"],
                "evidence_recovery": bool(g["gold_span_indices"]) and bs["gold_evidence_overlap"] is not True and ag["gold_evidence_overlap"] is True,
                "r5_q10": trace["r5_q10"],
                "agent_steps": trace["agent_steps"],
                "model_calls": trace["agent_model_calls"],
                "tool_calls": trace["tool_calls"],
                "tool_names": trace["tool_names"],
                "tool_arguments": trace["tool_call_arguments"],
                "final_without_tool": trace["stop_reason"] == "final" and trace["tool_calls"] == 0,
                "input_tokens": trace["total_input_tokens"],
                "output_tokens": trace["total_output_tokens"],
                "latency_seconds": trace["wall_seconds"],
                "incremental_latency_seconds": trace["latency_increment_s"],
                "incremental_cost_usd": trace["total_incremental_cost_usd"],
                "base_parse_status": trace["base_parse_status"],
                "agent_parse_status": "fallback_to_base" if trace["fallback_to_a2"] else "strict_agent_action",
                "fallback": trace["fallback_to_a2"],
                "stop_reason": trace["stop_reason"],
                "retrieval_top1": scores[0],
                "retrieval_top2": scores[1],
                "retrieval_margin": scores[0] - scores[1],
                "retrieval_top5_spread": scores[0] - scores[-1],
                "retrieved_section_count": len(r["ranked_chunk_ids"]),
                "retrieved_chunk_ids": r["ranked_chunk_ids"],
                "retrieved_source_positions": r["ranked_chunk_offsets"],
                "document_chars": len(doc["text"]),
                "document_span_count": len(doc["spans"]),
                "base_evidence_count": len(b.get("evidence") or []),
                "base_evidence_chars": sum(len(x) for x in (b.get("evidence") or [])),
                "legal_cues": [cue.strip() for cue in LEGAL_CUES if cue in context_lower],
            }
            rows.append(row)
        rows_by_version[version] = rows

    rows = rows_by_version[EVIDENCE_EVALUATOR_V2]
    before = arm_metrics(rows, "base")
    after = arm_metrics(rows, "agent")
    classification_recoveries = [row["case_id"] for row in rows if row["classification_recovery"]]
    classification_regressions = [row["case_id"] for row in rows if row["classification_regression"]]
    joint_recoveries = [row["case_id"] for row in rows if row["joint_recovery"]]
    joint_regressions = [row["case_id"] for row in rows if row["joint_regression"]]
    c_recoveries = [row["case_id"] for row in rows if row["C_recovery"]]
    c_regressions = [row["case_id"] for row in rows if row["C_regression"]]
    net_joint = len(joint_recoveries) - len(joint_regressions)
    net_c = len(c_recoveries) - len(c_regressions)

    tool_rows = [row for row in rows if row["tool_calls"]]
    total_cost = sum(row["incremental_cost_usd"] for row in rows)
    total_calls = sum(row["model_calls"] for row in rows)
    total_tool_calls = sum(row["tool_calls"] for row in rows)
    latencies = [row["incremental_latency_seconds"] for row in rows]
    tool_name_counts = Counter(name for trace in traces for name in trace["tool_names"])
    useful_tools = sum(row["joint_recovery"] for row in tool_rows)
    unnecessary_tools = sum(row["base_joint_success"] and row["agent_joint_success"] for row in tool_rows)
    harmful_tools = sum(row["joint_regression"] for row in tool_rows)

    recoverable_runtime = []
    for row in rows:
        if row["classification_recovery"]:
            recoverable_runtime.append({
                key: row[key] for key in (
                    "case_id", "base_label", "agent_label", "r5_q10", "tool_calls", "tool_names",
                    "retrieval_top1", "retrieval_top2", "retrieval_margin", "retrieval_top5_spread",
                    "retrieved_chunk_ids", "retrieved_source_positions", "document_chars",
                    "document_span_count", "base_evidence_count", "base_evidence_chars", "legal_cues",
                    "joint_recovery", "C_recovery", "evidence_recovery",
                )
            })
    pattern_summary = {
        "classification_recoverable_n": len(recoverable_runtime),
        "r5_q10_n": sum(row["r5_q10"] for row in recoverable_runtime),
        "tool_used_n": sum(row["tool_calls"] > 0 for row in recoverable_runtime),
        "base_label_counts": dict(Counter(row["base_label"] for row in recoverable_runtime)),
        "legal_cue_counts": dict(Counter(cue for row in recoverable_runtime for cue in row["legal_cues"])),
        "assessment": "No meaningful tool-recoverability pattern: recoveries did not use tools." if recoverable_runtime and not any(row["tool_calls"] for row in recoverable_runtime) else "Review recoverable_runtime_features before any router proposal.",
    }

    v1_rows = rows_by_version[EVIDENCE_EVALUATOR_V1]
    v1_before, v1_after = arm_metrics(v1_rows, "base"), arm_metrics(v1_rows, "agent")
    report = {
        "status": "E1_COMPLETE_STOP_BEFORE_E2",
        "primary_evaluator": EVIDENCE_EVALUATOR_V2,
        "baseline": before,
        "full_agent": after,
        "delta": delta(after, before),
        "paired_transitions": {
            "classification_recoveries": classification_recoveries,
            "classification_regressions": classification_regressions,
            "net_classification_recoveries": len(classification_recoveries) - len(classification_regressions),
            "joint_recoveries": joint_recoveries,
            "joint_regressions": joint_regressions,
            "net_joint_recoveries": net_joint,
            "C_recoveries": c_recoveries,
            "C_regressions": c_regressions,
            "net_C_recoveries": net_c,
        },
        "tool_use": {
            "cases_using_tool": len(tool_rows), "case_tool_use_rate": len(tool_rows) / len(rows),
            "step1_FINAL_without_tool_n": sum(row["final_without_tool"] and row["agent_steps"] == 1 for row in rows),
            "step1_FINAL_without_tool_rate": sum(row["final_without_tool"] and row["agent_steps"] == 1 for row in rows) / len(rows),
            "mean_agent_steps": statistics.mean(row["agent_steps"] for row in rows),
            "p95_agent_steps": percentile([row["agent_steps"] for row in rows], .95),
            "mean_tool_calls": statistics.mean(row["tool_calls"] for row in rows),
            "tool_call_distribution": dict(Counter(row["tool_calls"] for row in rows)),
            "tool_name_counts": dict(tool_name_counts),
            "most_used_tools": ([name for name, count in tool_name_counts.items()
                                 if count == max(tool_name_counts.values())]
                                if tool_name_counts else []),
            "useful_tool_case_counts": [useful_tools, len(tool_rows)],
            "useful_tool_case_rate": useful_tools / len(tool_rows) if tool_rows else None,
            "unnecessary_tool_case_counts": [unnecessary_tools, len(tool_rows)],
            "unnecessary_tool_case_rate": unnecessary_tools / len(tool_rows) if tool_rows else None,
            "harmful_tool_case_counts": [harmful_tools, len(tool_rows)],
            "harmful_tool_case_rate": harmful_tools / len(tool_rows) if tool_rows else None,
        },
        "operations": {
            "new_hosted_calls": total_calls,
            "incremental_input_tokens": sum(row["input_tokens"] for row in rows),
            "incremental_output_tokens": sum(row["output_tokens"] for row in rows),
            "incremental_cost_usd": total_cost,
            "mean_incremental_cost_usd_per_case": total_cost / len(rows),
            "total_incremental_latency_seconds_sequential": sum(latencies),
            "mean_incremental_latency_seconds_per_case": statistics.mean(latencies),
            "p95_incremental_latency_seconds": percentile(latencies, .95),
            "cost_per_net_joint_recovery_usd": ratio_or_message(total_cost, net_joint),
            "cost_per_net_C_recovery_usd": ratio_or_message(total_cost, net_c),
            "latency_per_net_C_recovery_seconds": ratio_or_message(sum(latencies), net_c),
            "model_calls_per_net_C_recovery": ratio_or_message(total_calls, net_c),
            "tool_calls_per_net_C_recovery": ratio_or_message(total_tool_calls, net_c),
        },
        "recoverable_runtime_pattern_summary": pattern_summary,
        "recoverable_runtime_features": recoverable_runtime,
        "evaluator_bridge": {
            "reason": "Stage C2's published 111/150 baseline Joint used exact-only v1; E1's frozen current evaluator is v2.",
            "v1_baseline_joint": [v1_before["joint_n"], v1_before["n"]],
            "v1_full_agent_joint": [v1_after["joint_n"], v1_after["n"]],
            "v1_net_joint": v1_after["joint_n"] - v1_before["joint_n"],
            "v2_baseline_joint": [before["joint_n"], before["n"]],
            "v2_full_agent_joint": [after["joint_n"], after["n"]],
            "v2_net_joint": after["joint_n"] - before["joint_n"],
        },
    }

    with (RESULTS / "per_case_metrics.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (RESULTS / "arm_metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    with (RESULTS / "comparison_table.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "base_RAG", "full_agent", "delta_pp"])
        for name, bval, aval in (
            ("Accuracy", before["accuracy"], after["accuracy"]),
            ("Macro-F1", before["macro_f1"], after["macro_f1"]),
            ("Joint", before["joint"], after["joint"]),
            ("Entailment Recall", before["recall"]["Entailment"], after["recall"]["Entailment"]),
            ("Contradiction Recall", before["recall"]["Contradiction"], after["recall"]["Contradiction"]),
            ("NotMentioned Recall", before["recall"]["NotMentioned"], after["recall"]["NotMentioned"]),
            ("Evidence Recall", before["evidence_recall"], after["evidence_recall"]),
            ("Evidence Precision", before["evidence_precision"], after["evidence_precision"]),
            ("Source-valid case rate", before["source_valid_case_rate"], after["source_valid_case_rate"]),
        ):
            writer.writerow([name, bval, aval, (aval - bval) * 100])

    with LEDGER_PATH.open(newline="") as handle:
        ledger_rows = [row for row in csv.DictReader(handle) if row["experiment_id"] == EXPERIMENT_ID]
    ledger_snapshot = {
        "experiment_id": EXPERIMENT_ID,
        "records": ledger_rows,
        "record_count": len(ledger_rows),
        "input_tokens": sum(int(row["input_tokens"]) for row in ledger_rows),
        "output_tokens": sum(int(row["output_tokens"]) for row in ledger_rows),
        "cost_usd": sum(float(row["cost_usd"]) for row in ledger_rows),
        "commit_at_analysis": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
    }
    (RESULTS / "cost_ledger_snapshot.json").write_text(json.dumps(ledger_snapshot, indent=2) + "\n")

    print(json.dumps({
        "baseline": {"accuracy": before["accuracy"], "joint": before["joint"], "C_recall": before["recall"]["Contradiction"]},
        "agent": {"accuracy": after["accuracy"], "joint": after["joint"], "C_recall": after["recall"]["Contradiction"]},
        "classification": [len(classification_recoveries), len(classification_regressions)],
        "joint": [len(joint_recoveries), len(joint_regressions)],
        "C": [len(c_recoveries), len(c_regressions)],
        "cost": total_cost, "calls": total_calls, "tools": len(tool_rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
