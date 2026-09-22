#!/usr/bin/env python3
"""
Confidence & abstention analysis (WBS T026, experiments F01/F02/F04/F05/F06).

Entirely free - reuses the already-collected "Best RAG" predictions
(results/runs/run_T018_prompt_v2.jsonl, the adopted v2 prompt, T018) and
re-derives retrieval scores by re-running the (deterministic, local,
no-LLM-cost) retrieval pipeline on the same 150-case sample. No new API
calls.

F01 (self-confidence): does the model's own reported `confidence` field
predict whether it got the label right? Scored with AUROC.
F02 (retrieval-score confidence): does the top retrieved chunk's score
predict correctness? Caveat: when the rule-based match fires (T023 round
7), the top score comes from Reciprocal Rank Fusion (a small ~1/60-scale
number), not the cross-encoder's logit score used otherwise - the two
are not on a comparable scale, which likely weakens this signal. Reported
honestly, not smoothed over.
F04 (threshold sweep): for confidence thresholds 0.50-0.95, what's the
selective accuracy (accuracy among accepted cases) and coverage (%
accepted)?
F05 (abstention effectiveness): at the selected threshold, what fraction
of abstained cases would actually have been wrong? Target from the
planning doc: >70%.
F06: the accuracy-coverage curve itself (data for the notebook to plot).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.metrics import roc_auc_score

from evaluation.harness import EvaluationHarness
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_by_keywords
from scripts.run_oracle_experiment import SEED, stratified_sample


def main() -> int:
    harness = EvaluationHarness()
    rag = harness.load_results("runs/run_T018_prompt_v2.jsonl")[0]

    dataset = parse_contractnli_file(settings.data_path / "dev.json")
    sample = stratified_sample(dataset, 150, SEED)
    gold_by_key = {(doc.doc_id, ann.hypothesis_id): ann.label for doc, ann in sample}
    hyp_text_by_key = {(doc.doc_id, ann.hypothesis_id): ann.hypothesis_text for doc, ann in sample}
    doc_by_id = {doc.doc_id: doc for doc, _ in sample}

    cases = []
    retrievers: dict[str, Retriever] = {}
    for pred in rag.predictions:
        key = (pred.doc_id, pred.hypothesis_id)
        gold_label = gold_by_key[key]
        correct = pred.predicted_label.value == gold_label

        if pred.doc_id not in retrievers:
            retrievers[pred.doc_id] = Retriever(doc_by_id[pred.doc_id].text, chunk_method="sentence")
        retriever = retrievers[pred.doc_id]
        retrieved = retriever.query_rerank_and_boost(pred.hypothesis_id, hyp_text_by_key[key])
        top_score = retrieved[0].score if retrieved else 0.0
        score_margin = (retrieved[0].score - retrieved[1].score) if len(retrieved) >= 2 else 0.0

        rule_label = classify_by_keywords(pred.hypothesis_id, doc_by_id[pred.doc_id].text)
        rule_agrees = float(rule_label == pred.predicted_label.value)

        cases.append({
            "doc_id": pred.doc_id, "hypothesis_id": pred.hypothesis_id,
            "gold_label": gold_label, "predicted_label": pred.predicted_label.value,
            "correct": correct, "self_confidence": pred.confidence, "top_retrieval_score": top_score,
            "score_margin": score_margin, "rule_agrees": rule_agrees,
        })

    print(f"Analyzed {len(cases)} cases ({sum(c['correct'] for c in cases)} correct)\n")

    correct_flags = [c["correct"] for c in cases]
    self_conf = [c["self_confidence"] for c in cases]
    retrieval_scores = [c["top_retrieval_score"] for c in cases]

    # --- F01: self-reported confidence vs correctness ---
    f01_auroc = roc_auc_score(correct_flags, self_conf)
    print(f"F01 - Self-confidence AUROC: {f01_auroc:.3f} (target ~0.7 per planning doc)")

    # Calibration: bucket by confidence, compare empirical accuracy per bucket.
    bins = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01)]
    calibration = []
    for lo, hi in bins:
        bucket = [c for c in cases if lo <= c["self_confidence"] < hi]
        if bucket:
            acc = sum(c["correct"] for c in bucket) / len(bucket)
            calibration.append({"bin": f"[{lo:.2f}, {hi:.2f})", "n": len(bucket),
                                 "avg_confidence": sum(c["self_confidence"] for c in bucket) / len(bucket),
                                 "empirical_accuracy": acc})
    print("Calibration:")
    for row in calibration:
        print(f"  {row['bin']:16} n={row['n']:3}  avg_conf={row['avg_confidence']:.3f}  "
              f"empirical_acc={row['empirical_accuracy']:.3f}")

    # --- F02: retrieval score vs correctness ---
    f02_auroc = roc_auc_score(correct_flags, retrieval_scores)
    print(f"\nF02 - Retrieval-score AUROC: {f02_auroc:.3f} "
          f"(caveat: mixes RRF-fused and raw reranker score scales - see module docstring)")

    # --- Extra candidate signals (not in the plan's original F01/F02, but
    # self-confidence and retrieval score both failed - worth checking
    # whether any other free-to-compute signal actually discriminates) ---
    score_margins = [c["score_margin"] for c in cases]
    rule_agrees = [c["rule_agrees"] for c in cases]
    f_margin_auroc = roc_auc_score(correct_flags, score_margins)
    f_rule_auroc = roc_auc_score(correct_flags, rule_agrees)
    print(f"\nExtra signal - Retrieval score margin (top1-top2) AUROC: {f_margin_auroc:.3f}")
    print(f"Extra signal - Rule-baseline agreement AUROC:              {f_rule_auroc:.3f}")

    # Best available signal decides what F04/F05 actually sweep on - no
    # point thresholding a signal that already failed AUROC.
    signal_options = {
        "self_confidence": (f01_auroc, "self_confidence"),
        "top_retrieval_score": (f02_auroc, "top_retrieval_score"),
        "score_margin": (f_margin_auroc, "score_margin"),
        "rule_agrees": (f_rule_auroc, "rule_agrees"),
    }
    best_signal_name = max(signal_options, key=lambda k: signal_options[k][0])
    best_auroc = signal_options[best_signal_name][0]
    print(f"\nBest available signal: {best_signal_name} (AUROC={best_auroc:.3f})")

    sweep_values = [c[best_signal_name] for c in cases]
    lo, hi = min(sweep_values), max(sweep_values)
    sweep_thresholds = [lo + (hi - lo) * i / 9 for i in range(10)] if hi > lo else [lo]

    # --- F04: threshold sweep on the best available signal ---
    print(f"\nF04 - Threshold sweep (signal: {best_signal_name}):")
    sweep = []
    for t in sweep_thresholds:
        accepted = [c for c in cases if c[best_signal_name] >= t]
        abstained = [c for c in cases if c[best_signal_name] < t]
        coverage = len(accepted) / len(cases)
        selective_accuracy = sum(c["correct"] for c in accepted) / len(accepted) if accepted else float("nan")
        abstention_effectiveness = (
            sum(not c["correct"] for c in abstained) / len(abstained) if abstained else float("nan")
        )
        sweep.append({
            "threshold": t, "coverage": coverage, "selective_accuracy": selective_accuracy,
            "abstention_rate": 1 - coverage, "abstention_effectiveness": abstention_effectiveness,
            "n_accepted": len(accepted), "n_abstained": len(abstained),
        })
        print(f"  t={t:.2f}  coverage={coverage:.3f}  selective_acc={selective_accuracy:.3f}  "
              f"abstention_rate={1-coverage:.3f}  abstention_effectiveness={abstention_effectiveness:.3f}")

    # --- F05: pick a threshold and report abstention effectiveness ---
    # Practical pick: the lowest threshold where abstention_effectiveness
    # clears the planning doc's 70% target, to abstain on as few cases as
    # possible while still being right to abstain on most of them.
    candidates = [s for s in sweep if s["abstention_effectiveness"] >= 0.70 and s["n_abstained"] > 0]
    selected = min(candidates, key=lambda s: s["threshold"]) if candidates else sweep[-1]
    print(f"\nF05 - Selected threshold: {selected['threshold']:.2f} "
          f"(abstention_effectiveness={selected['abstention_effectiveness']:.3f}, "
          f"target >0.70; coverage={selected['coverage']:.3f})")

    # --- Combined heuristic: since no single signal hit the target AUROC,
    # does requiring BOTH self-confidence==1.0 AND rule agreement (the two
    # best-behaved signals) do better than either alone? ---
    combined_accept = [c for c in cases if c["self_confidence"] >= 1.0 and c["rule_agrees"] == 1.0]
    combined_reject = [c for c in cases if not (c["self_confidence"] >= 1.0 and c["rule_agrees"] == 1.0)]
    combined_coverage = len(combined_accept) / len(cases)
    combined_selective_acc = sum(c["correct"] for c in combined_accept) / len(combined_accept) if combined_accept else float("nan")
    combined_effectiveness = sum(not c["correct"] for c in combined_reject) / len(combined_reject) if combined_reject else float("nan")
    print(f"\nCombined (self_confidence==1.0 AND rule_agrees==1): coverage={combined_coverage:.3f} "
          f"selective_acc={combined_selective_acc:.3f} abstention_effectiveness={combined_effectiveness:.3f} "
          f"(n_accept={len(combined_accept)}, n_reject={len(combined_reject)})")

    output = {
        "f01_self_confidence_auroc": f01_auroc,
        "f01_calibration": calibration,
        "f02_retrieval_score_auroc": f02_auroc,
        "extra_score_margin_auroc": f_margin_auroc,
        "extra_rule_agrees_auroc": f_rule_auroc,
        "best_signal": best_signal_name,
        "best_signal_auroc": best_auroc,
        "f04_threshold_sweep": sweep,
        "f05_selected_threshold": selected["threshold"],
        "f05_abstention_effectiveness": selected["abstention_effectiveness"],
        "combined_coverage": combined_coverage,
        "combined_selective_accuracy": combined_selective_acc,
        "combined_abstention_effectiveness": combined_effectiveness,
        "cases": cases,
    }
    Path("data/confidence_analysis.json").write_text(json.dumps(output, indent=2))
    print("\nWrote data/confidence_analysis.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
