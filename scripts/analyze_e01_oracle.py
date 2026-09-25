#!/usr/bin/env python3
"""
E01 Oracle — evaluation (reconstruction-v2). Reads the 4 saved run_E01_oracle_*.jsonl result
files, computes per-model metrics via evaluation/metrics.py (reused, not reimplemented), and
writes experiments/E01_oracle/results/e01_metrics.json. No model calls -- pure local analysis
of already-saved results.

Deliberately does NOT compute retrieval metrics (Evidence Recall@K, MRR, the joint metric) --
Oracle has no retrieval step, per the reconstruction brief section 20.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import sys
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.metrics import (  # noqa: E402
    contradiction_recall_with_ci,
    macro_f1,
    per_class_metrics,
    recall_with_ci,
)
from evaluation.schemas import GoldCase, Label, Prediction  # noqa: E402

RESULTS_DIR = REPO / "experiments/E01_oracle/results"
RUN_FILES = {
    "llama3.2:3b": ("local", RESULTS_DIR / "run_E01_oracle_local_llama3.2_3b.jsonl"),
    "qwen2.5:7b-instruct": ("local", RESULTS_DIR / "run_E01_oracle_local_qwen2.5_7b-instruct.jsonl"),
    "google/gemini-2.5-flash-lite": ("openrouter", RESULTS_DIR / "run_E01_oracle_openrouter_google_gemini-2.5-flash-lite.jsonl"),
    "openai/gpt-5-mini": ("openrouter", RESULTS_DIR / "run_E01_oracle_openrouter_openai_gpt-5-mini.jsonl"),
}
LABELS = ["Entailment", "Contradiction", "NotMentioned"]


def load_records(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def to_pred_gold(records: list[dict]) -> tuple[list[Prediction], list[GoldCase]]:
    preds, golds = [], []
    for r in records:
        golds.append(GoldCase(doc_id=str(r["document_id"]), hypothesis_id=r["hypothesis_id"],
                               gold_label=Label(r["gold_label"])))
        # parse_valid=False (or a genuine infra error) => treat as abstained: never scored as
        # "correct" by accident just because Prediction defaults predicted_label somewhere.
        if r["parse_valid"] and r["predicted_label"] in LABELS:
            preds.append(Prediction(doc_id=str(r["document_id"]), hypothesis_id=r["hypothesis_id"],
                                     predicted_label=Label(r["predicted_label"]), abstained=False))
        else:
            preds.append(Prediction(doc_id=str(r["document_id"]), hypothesis_id=r["hypothesis_id"],
                                     predicted_label=Label.NOT_MENTIONED, abstained=True))
    return preds, golds


def confusion_matrix(records: list[dict]) -> dict:
    cm = {g: {p: 0 for p in LABELS + ["parse_error/other"]} for g in LABELS}
    for r in records:
        gold = r["gold_label"]
        pred = r["predicted_label"] if (r["parse_valid"] and r["predicted_label"] in LABELS) else "parse_error/other"
        cm[gold][pred] += 1
    return cm


def latency_stats(records: list[dict]) -> dict:
    lat = [r["latency_ms"] for r in records if r.get("latency_ms") is not None]
    if not lat:
        return {"mean_ms": None, "median_ms": None, "p90_ms": None}
    lat_sorted = sorted(lat)
    return {
        "mean_ms": round(statistics.mean(lat), 1),
        "median_ms": round(statistics.median(lat), 1),
        "p90_ms": round(lat_sorted[int(0.9 * len(lat_sorted))], 1),
        "n": len(lat),
    }


def token_stats(records: list[dict], key: str) -> dict:
    vals = [r[key] for r in records if r.get(key) is not None]
    if not vals:
        return {"total": None, "mean": None, "n_available": 0, "n_missing": len(records)}
    return {"total": sum(vals), "mean": round(statistics.mean(vals), 1),
            "n_available": len(vals), "n_missing": len(records) - len(vals)}


def main():
    results = {}
    for model, (provider, path) in RUN_FILES.items():
        records = load_records(path)
        preds, golds = to_pred_gold(records)

        parse_valid_count = sum(1 for r in records if r["parse_valid"])
        error_count = sum(1 for r in records if r.get("error"))
        retry_count = sum(1 for r in records if r.get("retry_count"))  # field not populated by this runner -> 0

        cls_metrics = per_class_metrics(preds, golds)
        contradiction = contradiction_recall_with_ci(preds, golds)
        entailment_recall = recall_with_ci(Label.ENTAILMENT, preds, golds)
        not_mentioned_recall = recall_with_ci(Label.NOT_MENTIONED, preds, golds)

        correct = sum(1 for r in records if r["parse_valid"] and r["predicted_label"] == r["gold_label"])
        balanced_accuracy = correct / len(records)

        hosted_cost = sum(r.get("cost_usd") or 0 for r in records) if provider == "openrouter" else None
        # cost_usd isn't in the saved per-case record (it's in the ledger) -- recompute from ledger for hosted.

        results[model] = {
            "provider": provider,
            "n_cases": len(records),
            "parse_valid_count": parse_valid_count,
            "parse_valid_rate": round(parse_valid_count / len(records), 4),
            "infra_error_count": error_count,
            "macro_f1": round(macro_f1(preds, golds), 4),
            "balanced_oracle_diagnostic_accuracy": round(balanced_accuracy, 4),
            "per_class_recall": {
                "Entailment": {"recall": round(entailment_recall["recall"], 4), "n": entailment_recall["n"], "correct": entailment_recall["correct"]},
                "Contradiction": {"recall": round(contradiction["recall"], 4), "n": contradiction["n"], "correct": contradiction["correct"],
                                   "ci_low": round(contradiction["ci_low"], 4), "ci_high": round(contradiction["ci_high"], 4)},
                "NotMentioned": {"recall": round(not_mentioned_recall["recall"], 4), "n": not_mentioned_recall["n"], "correct": not_mentioned_recall["correct"]},
            },
            "per_class_precision_f1": {k: {"precision": round(v["precision"], 4), "f1": round(v["f1"], 4)} for k, v in cls_metrics.items()},
            "confusion_matrix": confusion_matrix(records),
            "latency": latency_stats(records),
            "input_tokens": token_stats(records, "input_tokens"),
            "output_tokens": token_stats(records, "output_tokens"),
        }

    # Hosted cost, read from the real ledger (authoritative), not recomputed.
    ledger_path = REPO / "results/budget/reconstruction_spend_ledger.csv"
    import csv
    hosted_cost_by_model = {}
    with open(ledger_path) as f:
        for row in csv.DictReader(f):
            hosted_cost_by_model.setdefault(row["model"], 0.0)
            hosted_cost_by_model[row["model"]] += float(row["cost_usd"])
    for model, cost in hosted_cost_by_model.items():
        if model in results:
            results[model]["hosted_cost_usd"] = round(cost, 6)
            results[model]["cost_source"] = "provider-reported (via OpenRouter usage field, pipeline/model_gateway.py)"
    for model in results:
        if "hosted_cost_usd" not in results[model]:
            results[model]["hosted_cost_usd"] = 0.0
            results[model]["cost_source"] = "local compute, $0 by construction"

    out_path = RESULTS_DIR / "e01_metrics.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"wrote {out_path}")
    for model, m in results.items():
        print(f"\n{model}: MacroF1={m['macro_f1']} balanced_acc={m['balanced_oracle_diagnostic_accuracy']} "
              f"parse_valid={m['parse_valid_rate']} cost=${m['hosted_cost_usd']}")


if __name__ == "__main__":
    main()
