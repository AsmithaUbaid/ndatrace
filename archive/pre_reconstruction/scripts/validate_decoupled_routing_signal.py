#!/usr/bin/env python3
"""
Validates the routing-independence fix (code-audit finding C-1, 2026-09-24)
on the cheap 150-case dev sample BEFORE committing to a full test-set
re-run: does "rule agrees with a PLAIN (non-rule-boosted) classification"
still predict whether the production (rule-boosted) RAG answer is
correct, once the circularity from T026's original measurement is
removed?

T026 computed rule_agrees against results/runs/run_T018_prompt_v2.jsonl's
predictions - which were classified over rule-boosted retrieval
(pipeline/retriever.py's query_rerank_and_boost, per T023 round 7) - so
comparing the SAME rule against that prediction was circular. This script
reuses those existing boosted predictions (no new cost there) but adds
ONE new classify() call per case over a plain, non-boosted context
(Retriever.query_and_rerank()) to compute a decoupled agreement signal,
then reports both AUROCs side by side.

Cost: ~150 extra Gemini calls (~$0.02-0.04), not the full re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.metrics import roc_auc_score

from evaluation.harness import EvaluationHarness
from pipeline.classifier import classify
from pipeline.config import settings
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_by_keywords
from scripts.run_oracle_experiment import SEED, stratified_sample


def main() -> int:
    harness = EvaluationHarness()
    rag = harness.load_results("runs/run_T018_prompt_v2.jsonl")[0]

    dataset = parse_contractnli_file(settings.data_path / "dev.json")
    sample = stratified_sample(dataset, 150, SEED)
    hyp_text_by_key = {(doc.doc_id, ann.hypothesis_id): ann.hypothesis_text for doc, ann in sample}
    gold_by_key = {(doc.doc_id, ann.hypothesis_id): ann.label for doc, ann in sample}
    doc_by_id = {doc.doc_id: doc for doc, _ in sample}

    try:
        gateway = ModelGateway()
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1

    retrievers: dict[str, Retriever] = {}
    correct_flags, rule_agrees_boosted, rule_agrees_plain = [], [], []
    total_cost = 0.0

    for i, pred in enumerate(rag.predictions, 1):
        key = (pred.doc_id, pred.hypothesis_id)
        gold_label = gold_by_key[key]
        boosted_correct = pred.predicted_label.value == gold_label

        if pred.doc_id not in retrievers:
            retrievers[pred.doc_id] = Retriever(doc_by_id[pred.doc_id].text, chunk_method="sentence")
        retriever = retrievers[pred.doc_id]

        rule_label = classify_by_keywords(pred.hypothesis_id, doc_by_id[pred.doc_id].text)

        # OLD (circular) signal: rule vs. the boosted prediction already saved from T018.
        agrees_boosted = float(rule_label == pred.predicted_label.value)

        # NEW (decoupled) signal: rule vs. a FRESH classification over plain,
        # non-rule-boosted retrieval - this is the only new API call here.
        plain_retrieved = retriever.query_and_rerank(hyp_text_by_key[key])
        plain_context = " ".join(r.chunk.text for r in plain_retrieved)
        try:
            plain_result = classify(plain_context, hyp_text_by_key[key], gateway,
                                     doc_id=pred.doc_id, hypothesis_id=pred.hypothesis_id)
        except ModelError as e:
            print(f"  skip {key}: {e}")
            continue
        total_cost += plain_result.cost_usd
        agrees_plain = float(rule_label == plain_result.label)

        correct_flags.append(float(boosted_correct))
        rule_agrees_boosted.append(agrees_boosted)
        rule_agrees_plain.append(agrees_plain)

        if i % 25 == 0:
            print(f"  {i}/{len(rag.predictions)} processed, cost so far ${total_cost:.4f}")

    auroc_old = roc_auc_score(correct_flags, rule_agrees_boosted)
    auroc_new = roc_auc_score(correct_flags, rule_agrees_plain)

    n_agree_old = sum(rule_agrees_boosted)
    n_agree_new = sum(rule_agrees_plain)
    sel_acc_old = (sum(c for c, a in zip(correct_flags, rule_agrees_boosted) if a) / n_agree_old
                   if n_agree_old else 0.0)
    sel_acc_new = (sum(c for c, a in zip(correct_flags, rule_agrees_plain) if a) / n_agree_new
                   if n_agree_new else 0.0)

    print(f"\nn={len(correct_flags)} cases, extra validation cost: ${total_cost:.4f}")
    print(f"\n{'Signal':<45}{'AUROC':>10}{'Coverage':>12}{'Sel.Acc':>10}")
    print(f"{'OLD (rule vs. rule-boosted prediction)':<45}{auroc_old:>10.3f}"
          f"{n_agree_old/len(correct_flags):>12.1%}{sel_acc_old:>10.1%}")
    print(f"{'NEW (rule vs. plain/decoupled prediction)':<45}{auroc_new:>10.3f}"
          f"{n_agree_new/len(correct_flags):>12.1%}{sel_acc_new:>10.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
