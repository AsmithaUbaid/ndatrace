#!/usr/bin/env python3
"""
Top-k sweep on the winning retrieval config (sentence chunking, mpnet
embeddings, rerank with ms-marco-MiniLM-L-12-v2) - how much recall do we
actually give up by keeping the final context small?

Answers directly: what's the real recall-vs-context trade-off, so the
final top_k is a deliberate choice, not a guess.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.metrics import evidence_precision, evidence_recall_at_k, mean_reciprocal_rank
from evaluation.schemas import GoldCase, Label, Prediction
from evaluation.scorer import map_chunks_to_gold_span_indices
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.reranker import rerank
from pipeline.retriever import Retriever

CANDIDATE_POOL_SIZE = 20
TOP_K_VALUES = [3, 5, 7, 10]


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    golds: list[GoldCase] = []
    predictions_by_k: dict[int, list[Prediction]] = {k: [] for k in TOP_K_VALUES}

    start = time.time()
    n_done = 0
    for doc_id, cases in cases_by_doc.items():
        doc = cases[0][0]
        retriever = Retriever(doc.text, chunk_method="sentence")

        for _, ann in cases:
            golds.append(GoldCase(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                gold_label=Label(ann.label),
                gold_span_indices=[s.span_index for s in ann.evidence_spans],
            ))

            candidates = retriever.query(ann.hypothesis_text, top_k=CANDIDATE_POOL_SIZE)
            reranked = rerank(ann.hypothesis_text, candidates, top_k=CANDIDATE_POOL_SIZE,
                               model_name="cross-encoder/ms-marco-MiniLM-L-12-v2")

            for k in TOP_K_VALUES:
                final = reranked[:k]
                predictions_by_k[k].append(Prediction(
                    doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                    predicted_label=Label(ann.label),
                    retrieved_span_indices=map_chunks_to_gold_span_indices(
                        doc.spans, [r.chunk for r in final]),
                ))

            n_done += 1
            if n_done % 100 == 0:
                print(f"  {n_done} cases done, {time.time()-start:.0f}s elapsed", flush=True)

    print(f"\nEvaluated on {len(golds)} cases\n")
    results = []
    for k in TOP_K_VALUES:
        preds = predictions_by_k[k]
        r = evidence_recall_at_k(preds, golds)
        p = evidence_precision(preds, golds)
        m = mean_reciprocal_rank(preds, golds)
        print(f"top_k={k:<3}  recall={r:.3f}  precision={p:.3f}  mrr={m:.3f}")
        results.append({"top_k": k, "recall": r, "precision": p, "mrr": m})

    Path("data/top_k_sweep.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
