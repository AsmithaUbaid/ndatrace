#!/usr/bin/env python3
"""
Rule-based keyword matching vs. semantic (embedding) retrieval, compared
on evidence-finding quality alone (not final label accuracy - that
comparison already exists as B02 vs B04/Oracle).

The rule baseline was never designed to point at evidence - it only ever
returned a label. classify_with_span (pipeline/rule_baseline.py) exposes
the character span of whichever keyword phrase triggered the match, which
is treated as the rule baseline's single, rank-1 "retrieved chunk" -
scored with the exact same Evidence Recall@K / Precision / MRR formulas
used for the semantic retriever (T023), via the same
map_chunks_to_gold_span_indices bridge.

Both are evaluated on the same 614 Entailment/Contradiction dev cases,
so this is a genuine apples-to-apples comparison, not just two
differently-scoped experiments.
"""

from __future__ import annotations

import sys
from collections import defaultdict, namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.metrics import evidence_precision, evidence_recall_at_k, mean_reciprocal_rank
from evaluation.schemas import GoldCase, Label, Prediction
from evaluation.scorer import map_chunks_to_gold_span_indices
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_with_span

FakeChunk = namedtuple("FakeChunk", ["start_char", "end_char"])

# Best config from T023 (highest MRR, see docs/decisions.md).
SEMANTIC_CHUNK_METHOD, SEMANTIC_CHUNK_SIZE, SEMANTIC_TOP_K = "clause", 256, 5


def score_method(predictions: list[Prediction], golds: list[GoldCase], label: str) -> dict:
    recall = evidence_recall_at_k(predictions, golds)
    precision = evidence_precision(predictions, golds)
    mrr = mean_reciprocal_rank(predictions, golds)
    print(f"{label:30} recall={recall:.3f}  precision={precision:.3f}  mrr={mrr:.3f}  ({len(predictions)} cases)")
    return {"label": label, "recall": recall, "precision": precision, "mrr": mrr, "n_cases": len(predictions)}


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    rule_preds, semantic_preds, golds = [], [], []

    for doc_id, cases in cases_by_doc.items():
        doc = cases[0][0]
        retriever = Retriever(doc.text, chunk_method=SEMANTIC_CHUNK_METHOD, chunk_size=SEMANTIC_CHUNK_SIZE)

        for _, ann in cases:
            gold_span_indices = [s.span_index for s in ann.evidence_spans]
            golds.append(GoldCase(doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                                   gold_label=Label(ann.label), gold_span_indices=gold_span_indices))

            # --- Rule-based: single keyword-match span, or none ---
            _, span = classify_with_span(ann.hypothesis_id, doc.text)
            rule_chunks = [FakeChunk(*span)] if span else []
            rule_preds.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(doc.spans, rule_chunks),
            ))

            # --- Semantic: top-5 embedding-retrieved chunks ---
            results = retriever.query(ann.hypothesis_text, top_k=SEMANTIC_TOP_K)
            semantic_preds.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(
                    doc.spans, [r.chunk for r in results]),
            ))

    print(f"Evaluated on {len(golds)} dev cases (Entailment/Contradiction only)\n")
    rule_result = score_method(rule_preds, golds, "Rule-based keyword match")
    semantic_result = score_method(semantic_preds, golds, "Semantic retrieval (clause_256_k5)")

    print("\n--- Verdict ---")
    if semantic_result["recall"] > rule_result["recall"]:
        print(f"  Semantic retrieval finds MORE real evidence: {semantic_result['recall']:.1%} "
              f"vs {rule_result['recall']:.1%} recall.")
    else:
        print(f"  Rule-based finds MORE real evidence: {rule_result['recall']:.1%} "
              f"vs {semantic_result['recall']:.1%} recall.")
    if rule_result["precision"] > semantic_result["precision"]:
        print(f"  But rule-based is FAR more precise when it does match: {rule_result['precision']:.1%} "
              f"vs {semantic_result['precision']:.1%} - a keyword hit is a tiny, specific span; "
              f"a retrieved chunk is a whole paragraph.")

    import json
    Path("data/rule_vs_semantic_retrieval.json").write_text(
        json.dumps({"rule_based": rule_result, "semantic": semantic_result}, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
