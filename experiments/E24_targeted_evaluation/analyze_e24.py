#!/usr/bin/env python3
"""E24: score the saved Rule/FULL/RAG predictions against gold, using the project's existing
evidence-matching implementation (evaluation/evidence_matching.py) -- no alternative metric
logic. Zero model calls; reads only results/run_E24_predictions.jsonl (already executed) and
the case manifest (gold labels/evidence).

Evidence scoring for all three systems uses the identical method: each system's cited
evidence string(s) are matched back to gold span indices via
evaluation.evidence_matching.evidence_to_span_indices against the FULL NDA text as the single
context window (offsets [0, len(doc_text)]) -- the same mapping E04's rule baseline and
E17B/E20's GPT scoring both use. This means Rule's single matched-keyword span is scored on
equal footing with FULL/RAG's model-cited quotes -- not a more lenient or stricter standard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from evaluation import evidence_matching as EM  # noqa: E402

MANIFEST_PATH = HERE / "manifests" / "case_manifest.json"
PRED_PATH = HERE / "results" / "run_E24_predictions.jsonl"
OUT_PATH = HERE / "results" / "e24_analysis.json"
LABELS = ("Entailment", "Contradiction", "NotMentioned")


def score_case(case: dict, pred: dict) -> dict:
    doc_text = case["nda_text"]
    doc_spans = case["doc_spans"]
    gold_idx = case["gold_span_indices"]
    pred_label = pred["predicted_label"]
    evidence = pred.get("evidence") or []
    # Identical method E17B/E20 use: map cited quotes back to gold-annotation span indices
    # against the full document, via evaluation.evidence_matching.evidence_to_span_indices,
    # then evaluation.evidence_matching.joint_success -- not a reimplementation.
    pred_idx = EM.evidence_to_span_indices(evidence, [doc_text], [[0, len(doc_text)]], doc_spans)
    label_correct = pred_label == case["gold_label"]
    joint = EM.joint_success(case["gold_label"], pred_label, gold_idx, pred_idx)
    return {
        "case_id": case["case_id"], "group": case["group"], "gold_label": case["gold_label"],
        "predicted_label": pred_label, "label_correct": label_correct,
        "predicted_span_idx": pred_idx, "joint_correct": bool(joint),
        "n_evidence_cited": len(evidence), "source_valid": pred.get("source_valid"),
        "cost_usd": pred.get("cost_usd"), "latency_ms": pred.get("latency_ms"),
        "input_tokens": pred.get("input_tokens"), "output_tokens": pred.get("output_tokens"),
        "error": pred.get("error"),
    }


def summarize(scored: list[dict]) -> dict:
    n = len(scored)
    acc = sum(s["label_correct"] for s in scored) / n
    joint = sum(s["joint_correct"] for s in scored) / n
    f1s = []
    for c in LABELS:
        tp = sum(s["predicted_label"] == c and s["gold_label"] == c for s in scored)
        fp = sum(s["predicted_label"] == c and s["gold_label"] != c for s in scored)
        fn = sum(s["gold_label"] == c and s["predicted_label"] != c for s in scored)
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    contra = [s for s in scored if s["gold_label"] == "Contradiction"]
    nm = [s for s in scored if s["gold_label"] == "NotMentioned"]
    return {
        "n": n, "accuracy": round(acc, 4), "macro_f1": round(sum(f1s) / 3, 4), "joint_correctness": round(joint, 4),
        "contradiction_recall": round(sum(s["label_correct"] for s in contra) / len(contra), 4) if contra else None,
        "notmentioned_recall": round(sum(s["label_correct"] for s in nm) / len(nm), 4) if nm else None,
        "total_cost_usd": round(sum(s["cost_usd"] or 0 for s in scored), 6),
        "mean_latency_ms": round(sum(s["latency_ms"] or 0 for s in scored) / n, 1),
        "mean_input_tokens": round(sum(s["input_tokens"] or 0 for s in scored) / n, 1),
    }


def main() -> None:
    manifest = {c["case_id"]: c for c in json.loads(MANIFEST_PATH.read_text())["cases"]}
    preds = [json.loads(l) for l in open(PRED_PATH)]
    by_system: dict[str, dict[str, dict]] = {"rule": {}, "full": {}, "rag": {}}
    for p in preds:
        by_system[p["system"]][p["case_id"]] = p

    scored = {sysname: [score_case(manifest[cid], pred) for cid, pred in cases.items()]
              for sysname, cases in by_system.items()}
    for sysname in scored:
        scored[sysname].sort(key=lambda s: s["case_id"])

    summary = {sysname: summarize(rows) for sysname, rows in scored.items()}

    by_case = {cid: {sysname: next(s for s in scored[sysname] if s["case_id"] == cid) for sysname in scored}
               for cid in manifest}

    all_wrong = [cid for cid, d in by_case.items() if not any(d[s]["label_correct"] for s in ("rule", "full", "rag"))]
    full_right_rag_wrong = [cid for cid, d in by_case.items() if d["full"]["label_correct"] and not d["rag"]["label_correct"]]
    rag_right_full_wrong = [cid for cid, d in by_case.items() if d["rag"]["label_correct"] and not d["full"]["label_correct"]]
    correct_label_bad_evidence = {
        sysname: [cid for cid, d in by_case.items() if d[sysname]["label_correct"] and not d[sysname]["joint_correct"]]
        for sysname in ("full", "rag")
    }

    out = {
        "manifest_id": "E24_targeted_evaluation_v1", "n_cases": len(manifest),
        "summary_by_system": summary,
        "failure_analysis": {
            "all_three_wrong": all_wrong,
            "full_right_rag_wrong": full_right_rag_wrong,
            "rag_right_full_wrong": rag_right_full_wrong,
            "correct_label_incorrect_evidence": correct_label_bad_evidence,
        },
        "case_level": by_case,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(json.dumps(summary, indent=2))
    print("\nfailure_analysis:", json.dumps(out["failure_analysis"], indent=2))


if __name__ == "__main__":
    main()
