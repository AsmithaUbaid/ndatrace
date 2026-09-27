#!/usr/bin/env python3
"""Offline scorer for the completed E11 controller-prompt V1/V2 ablation."""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.evidence_matching import EVIDENCE_EVALUATOR_V2  # noqa: E402
from scripts.analyze_full_agent_diagnostic import (  # noqa: E402
    accessible_source, arm_metrics, delta, load_jsonl, percentile, ratio_or_message,
    score_prediction,
)

OUT = REPO / "experiments/E11_selective_agent_evaluation/addendum_agent_prompt_ablation"
RESULTS = OUT / "results"
BASE_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"
V1_PATH = REPO / "experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/raw_agent_traces.jsonl"
V2_PATH = RESULTS / "raw_v2.jsonl"
RETRIEVAL_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
GOLD_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json"
LEDGER_PATH = REPO / "results/budget/reconstruction_spend_ledger.csv"
EXPERIMENT_ID = "E11_addendum_agent_prompt_v2_ablation"


def operation_metrics(traces: list[dict]) -> dict:
    calls = sum(row["agent_model_calls"] for row in traces)
    tool_rows = [row for row in traces if row["tool_calls"]]
    latencies = [row["latency_increment_s"] for row in traces]
    tool_counts = Counter(name for row in traces for name in row["tool_names"])
    stops = Counter(row["stop_reason"] for row in traces)
    return {
        "cases": len(traces),
        "hosted_calls": calls,
        "input_tokens": sum(row["total_input_tokens"] for row in traces),
        "output_tokens": sum(row["total_output_tokens"] for row in traces),
        "cost_usd": sum(row["total_incremental_cost_usd"] for row in traces),
        "cost_per_case_usd": sum(row["total_incremental_cost_usd"] for row in traces) / len(traces),
        "total_incremental_latency_seconds": sum(latencies),
        "mean_incremental_latency_seconds": statistics.mean(latencies),
        "p95_incremental_latency_seconds": percentile(latencies, .95),
        "tool_using_cases": len(tool_rows),
        "tool_use_rate": len(tool_rows) / len(traces),
        "step1_final_without_tool_n": sum(row["agent_steps"] == 1 and row["tool_calls"] == 0 and row["stop_reason"] == "final" for row in traces),
        "step1_final_without_tool_rate": sum(row["agent_steps"] == 1 and row["tool_calls"] == 0 and row["stop_reason"] == "final" for row in traces) / len(traces),
        "mean_steps": statistics.mean(row["agent_steps"] for row in traces),
        "p95_steps": percentile([row["agent_steps"] for row in traces], .95),
        "mean_tool_calls": statistics.mean(row["tool_calls"] for row in traces),
        "tool_call_distribution": dict(Counter(str(row["tool_calls"]) for row in traces)),
        "tool_name_counts": dict(tool_counts),
        "duplicate_attempts": sum(row["duplicate_count"] for row in traces),
        "invalid_actions": sum(row["invalid_action_count"] for row in traces),
        "tool_errors": sum(row["tool_error_count"] for row in traces),
        "fallback_events": sum(row["fallback_to_a2"] for row in traces),
        "stop_reason_counts": dict(stops),
        "provider_error_calls": sum(bool(call.get("error")) for row in traces for call in row["call_log"]),
        "retry_count": sum(call.get("retry_count") or 0 for row in traces for call in row["call_log"]),
    }


def transitions(rows: list[dict], before: str, after: str) -> dict:
    cls_rec = [r["case_id"] for r in rows if not r[f"{before}_classification_correct"] and r[f"{after}_classification_correct"]]
    cls_reg = [r["case_id"] for r in rows if r[f"{before}_classification_correct"] and not r[f"{after}_classification_correct"]]
    joint_rec = [r["case_id"] for r in rows if not r[f"{before}_joint_success"] and r[f"{after}_joint_success"]]
    joint_reg = [r["case_id"] for r in rows if r[f"{before}_joint_success"] and not r[f"{after}_joint_success"]]
    c_rec = [r["case_id"] for r in rows if r["gold_label"] == "Contradiction" and not r[f"{before}_classification_correct"] and r[f"{after}_classification_correct"]]
    c_reg = [r["case_id"] for r in rows if r["gold_label"] == "Contradiction" and r[f"{before}_classification_correct"] and not r[f"{after}_classification_correct"]]
    ev_gain = [r["case_id"] for r in rows if r["gold_span_indices"] and r[f"{before}_gold_evidence_overlap"] is not True and r[f"{after}_gold_evidence_overlap"] is True]
    ev_reg = [r["case_id"] for r in rows if r["gold_span_indices"] and r[f"{before}_gold_evidence_overlap"] is True and r[f"{after}_gold_evidence_overlap"] is not True]
    return {
        "classification_recoveries": cls_rec, "classification_regressions": cls_reg,
        "net_classification": len(cls_rec) - len(cls_reg),
        "joint_recoveries": joint_rec, "joint_regressions": joint_reg,
        "net_joint": len(joint_rec) - len(joint_reg),
        "C_recoveries": c_rec, "C_regressions": c_reg, "net_C": len(c_rec) - len(c_reg),
        "evidence_recall_gains": ev_gain, "evidence_recall_regressions": ev_reg,
        "net_evidence_recall_cases": len(ev_gain) - len(ev_reg),
    }


def main() -> int:
    base = {r["case_id"]: r for r in load_jsonl(BASE_PATH)}
    v1 = {r["case_id"]: r for r in load_jsonl(V1_PATH)}
    v2 = {r["case_id"]: r for r in load_jsonl(V2_PATH)}
    retrieved = {r["case_id"]: r for r in json.loads(RETRIEVAL_PATH.read_text())["cases"]}
    gold = {r["case_id"]: r for r in json.loads(GOLD_PATH.read_text())["cases"]}
    docs = {r["id"]: r for r in json.loads((REPO / "data/contractnli/train.json").read_text())["documents"]}
    assert len(base) == len(v1) == len(v2) == len(retrieved) == len(gold) == 150
    assert set(base) == set(v1) == set(v2) == set(retrieved) == set(gold)

    rows = []
    for cid in base:
        b, one, two, ret, g = base[cid], v1[cid], v2[cid], retrieved[cid], gold[cid]
        doc_spans = docs[b["document_id"]]["spans"]
        base_context = "\n\n---\n\n".join(ret["ranked_chunk_text"])
        bscore = score_prediction(b["predicted_label"], b.get("evidence") or [], g,
                                  ret["ranked_chunk_text"], ret["ranked_chunk_offsets"], doc_spans,
                                  base_context, EVIDENCE_EVALUATOR_V2)
        one_texts, one_offsets, one_context = accessible_source(one, ret)
        one_score = score_prediction(one["final_label"], one.get("final_evidence") or [], g,
                                     one_texts, one_offsets, doc_spans, one_context, EVIDENCE_EVALUATOR_V2)
        two_texts, two_offsets, two_context = accessible_source(two, ret)
        two_score = score_prediction(two["final_label"], two.get("final_evidence") or [], g,
                                     two_texts, two_offsets, doc_spans, two_context, EVIDENCE_EVALUATOR_V2)
        row = {
            "case_id": cid, "document_id": b["document_id"], "hypothesis_id": b["hypothesis_id"],
            "gold_label": g["gold_label"], "gold_span_indices": g["gold_span_indices"],
            "base_label": b["predicted_label"], "base_evidence": b.get("evidence") or [],
            "v1_label": one["final_label"], "v1_evidence": one.get("final_evidence") or [],
            "v2_label": two["final_label"], "v2_evidence": two.get("final_evidence") or [],
            **{f"base_{k}": val for k, val in bscore.items()},
            **{f"v1_{k}": val for k, val in one_score.items()},
            **{f"v2_{k}": val for k, val in two_score.items()},
            "v1_steps": one["agent_steps"], "v1_tool_calls": one["tool_calls"], "v1_tool_names": one["tool_names"],
            "v1_final_without_tool": one["agent_steps"] == 1 and one["tool_calls"] == 0 and one["stop_reason"] == "final",
            "v1_fallback": one["fallback_to_a2"], "v1_stop_reason": one["stop_reason"],
            "v2_steps": two["agent_steps"], "v2_tool_calls": two["tool_calls"], "v2_tool_names": two["tool_names"],
            "v2_tool_arguments": two["tool_call_arguments"],
            "v2_final_without_tool": two["agent_steps"] == 1 and two["tool_calls"] == 0 and two["stop_reason"] == "final",
            "v2_fallback": two["fallback_to_a2"], "v2_stop_reason": two["stop_reason"],
            "v2_input_tokens": two["total_input_tokens"], "v2_output_tokens": two["total_output_tokens"],
            "v2_latency_seconds": two["latency_increment_s"], "v2_cost_usd": two["total_incremental_cost_usd"],
        }
        rows.append(row)

    metrics = {arm: arm_metrics(rows, arm) for arm in ("base", "v1", "v2")}
    base_v1 = transitions(rows, "base", "v1")
    base_v2 = transitions(rows, "base", "v2")
    v1_v2 = transitions(rows, "v1", "v2")
    operations = {"v1": operation_metrics(list(v1.values())), "v2": operation_metrics(list(v2.values()))}

    tool_rows = [row for row in rows if row["v2_tool_calls"]]
    no_tool_rows = [row for row in rows if not row["v2_tool_calls"]]
    tool_case_details = []
    for row in tool_rows:
        cls_rec = not row["base_classification_correct"] and row["v2_classification_correct"]
        joint_rec = not row["base_joint_success"] and row["v2_joint_success"]
        ev_rec = bool(row["gold_span_indices"]) and row["base_gold_evidence_overlap"] is not True and row["v2_gold_evidence_overlap"] is True
        harmful = ((row["base_classification_correct"] and not row["v2_classification_correct"])
                   or (row["base_joint_success"] and not row["v2_joint_success"])
                   or (bool(row["gold_span_indices"]) and row["base_gold_evidence_overlap"] is True and row["v2_gold_evidence_overlap"] is not True))
        if harmful:
            category = "harmful"
        elif cls_rec or joint_rec or ev_rec:
            category = "useful"
        else:
            category = "neutral"
        tool_case_details.append({
            "case_id": row["case_id"], "gold_label": row["gold_label"],
            "base_label": row["base_label"], "v2_label": row["v2_label"],
            "tools": row["v2_tool_names"], "tool_arguments": row["v2_tool_arguments"],
            "category": category, "classification_recovery": cls_rec,
            "joint_recovery": joint_rec, "evidence_recovery": ev_rec,
            "classification_regression": row["base_classification_correct"] and not row["v2_classification_correct"],
            "joint_regression": row["base_joint_success"] and not row["v2_joint_success"],
            "fallback": row["v2_fallback"], "stop_reason": row["v2_stop_reason"],
        })
    category_counts = Counter(row["category"] for row in tool_case_details)

    v1_wrong_v2_correct = [r["case_id"] for r in rows if not r["v1_classification_correct"] and r["v2_classification_correct"]]
    pathology_fixed = [r["case_id"] for r in rows if not r["v1_classification_correct"] and r["v1_final_without_tool"] and r["v2_tool_calls"] and r["v2_classification_correct"]]

    net_joint = base_v2["net_joint"]
    net_c = base_v2["net_C"]
    v2op = operations["v2"]
    economics = {
        "cost_per_net_joint_recovery_usd": ratio_or_message(v2op["cost_usd"], net_joint),
        "cost_per_net_C_recovery_usd": ratio_or_message(v2op["cost_usd"], net_c),
        "latency_per_net_joint_recovery_seconds": ratio_or_message(v2op["total_incremental_latency_seconds"], net_joint),
        "latency_per_net_C_recovery_seconds": ratio_or_message(v2op["total_incremental_latency_seconds"], net_c),
    }
    retention_checks = {key: bool(value) for key, value in {
        "1_joint_improves_vs_base": metrics["v2"]["joint"] > metrics["base"]["joint"],
        "2_net_joint_positive": net_joint > 0,
        "3_C_recall_or_net_C_meaningfully_positive": metrics["v2"]["recall"]["Contradiction"] > metrics["base"]["recall"]["Contradiction"] or net_c > 0,
        "4_C_regressions_controlled": len(base_v2["C_regressions"]) <= 1,
        "5_evidence_precision_drop_le_3pp": (metrics["v2"]["evidence_precision"] - metrics["base"]["evidence_precision"]) >= -.03,
        "6_evidence_recall_drop_le_3pp": (metrics["v2"]["evidence_recall"] - metrics["base"]["evidence_recall"]) >= -.03,
        "7_Entailment_recall_drop_le_3pp": (metrics["v2"]["recall"]["Entailment"] - metrics["base"]["recall"]["Entailment"]) >= -.03,
        "8_NotMentioned_recall_drop_le_3pp": (metrics["v2"]["recall"]["NotMentioned"] - metrics["base"]["recall"]["NotMentioned"]) >= -.03,
        "9_tool_use_materially_higher_than_v1": operations["v2"]["tool_use_rate"] > operations["v1"]["tool_use_rate"] + .05,
        "10_some_tool_calls_useful": category_counts["useful"] > 0,
        "11_cost_latency_acceptable": v2op["cost_usd"] < 3.0 and v2op["p95_incremental_latency_seconds"] < 60,
        "12_no_serious_safety_control_issue": v2op["provider_error_calls"] == 0 and v2op["duplicate_attempts"] == 0,
    }.items()}

    report = {
        "status": "COMPLETE_STOP_AFTER_REPORT",
        "evaluator": EVIDENCE_EVALUATOR_V2,
        "arms": metrics,
        "deltas_pp": {
            "base_to_v1": delta(metrics["v1"], metrics["base"]),
            "base_to_v2": delta(metrics["v2"], metrics["base"]),
            "v1_to_v2": delta(metrics["v2"], metrics["v1"]),
        },
        "transitions": {"base_to_v1": base_v1, "base_to_v2": base_v2, "v1_to_v2": v1_v2},
        "operations": operations,
        "tool_effectiveness": {
            "definition": "Outcome-associated proxy; a single-arm prompt ablation cannot prove tool-call causality.",
            "category_counts": dict(category_counts),
            "category_rates_among_tool_cases": {k: category_counts[k] / len(tool_rows) for k in ("useful", "neutral", "harmful")},
            "tool_cases": tool_case_details,
            "tool_used_group": {
                "n": len(tool_rows), "classification_correct_n": sum(r["v2_classification_correct"] for r in tool_rows),
                "joint_n": sum(r["v2_joint_success"] for r in tool_rows),
                "base_to_v2_net_classification": sum((not r["base_classification_correct"] and r["v2_classification_correct"]) for r in tool_rows) - sum((r["base_classification_correct"] and not r["v2_classification_correct"]) for r in tool_rows),
                "base_to_v2_net_joint": sum((not r["base_joint_success"] and r["v2_joint_success"]) for r in tool_rows) - sum((r["base_joint_success"] and not r["v2_joint_success"]) for r in tool_rows),
            },
            "no_tool_group": {
                "n": len(no_tool_rows), "classification_correct_n": sum(r["v2_classification_correct"] for r in no_tool_rows),
                "joint_n": sum(r["v2_joint_success"] for r in no_tool_rows),
                "base_to_v2_net_classification": sum((not r["base_classification_correct"] and r["v2_classification_correct"]) for r in no_tool_rows) - sum((r["base_classification_correct"] and not r["v2_classification_correct"]) for r in no_tool_rows),
                "base_to_v2_net_joint": sum((not r["base_joint_success"] and r["v2_joint_success"]) for r in no_tool_rows) - sum((r["base_joint_success"] and not r["v2_joint_success"]) for r in no_tool_rows),
            },
        },
        "posthoc": {
            "v1_wrong_to_v2_correct": v1_wrong_v2_correct,
            "v1_wrong_step1_final_to_v2_tool_to_correct": pathology_fixed,
        },
        "economics": economics,
        "retention_checks": retention_checks,
        "retention_pass": all(retention_checks.values()),
    }

    with (RESULTS / "per_case_metrics.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (RESULTS / "arm_metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    (RESULTS / "tool_usage.json").write_text(json.dumps(report["tool_effectiveness"], indent=2) + "\n")

    with LEDGER_PATH.open(newline="") as handle:
        ledger_rows = [row for row in csv.DictReader(handle) if row["experiment_id"] == EXPERIMENT_ID]
    cost_ledger = {
        "experiment_id": EXPERIMENT_ID, "record_count": len(ledger_rows), "records": ledger_rows,
        "input_tokens": sum(int(row["input_tokens"]) for row in ledger_rows),
        "output_tokens": sum(int(row["output_tokens"]) for row in ledger_rows),
        "cost_usd": sum(float(row["cost_usd"]) for row in ledger_rows),
    }
    (RESULTS / "cost_ledger.json").write_text(json.dumps(cost_ledger, indent=2) + "\n")

    print(json.dumps({
        "base": {"accuracy": metrics["base"]["accuracy"], "joint": metrics["base"]["joint"], "C": metrics["base"]["recall"]["Contradiction"]},
        "v1": {"accuracy": metrics["v1"]["accuracy"], "joint": metrics["v1"]["joint"], "C": metrics["v1"]["recall"]["Contradiction"]},
        "v2": {"accuracy": metrics["v2"]["accuracy"], "joint": metrics["v2"]["joint"], "C": metrics["v2"]["recall"]["Contradiction"]},
        "base_to_v2": base_v2, "v1_to_v2": v1_v2,
        "v2_operations": operations["v2"], "tool_categories": dict(category_counts),
        "retention_pass": report["retention_pass"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
