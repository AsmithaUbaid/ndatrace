#!/usr/bin/env python3
"""
Does cross-encoder reranking actually improve retrieval, or hurt it?

Retrieves a wide candidate set (sentence-level chunks, top-20) with the
current best config, then reranks down to top-10 with a cross-encoder
(pipeline/reranker.py), and compares against the plain top-10 retrieval
(no reranking) - same 614 dev cases used for every other retrieval
experiment, so directly comparable to T023's numbers.
"""

from __future__ import annotations

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
FINAL_TOP_K = 10


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    golds: list[GoldCase] = []
    plain_preds: list[Prediction] = []
    reranked_preds: list[Prediction] = []

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

            plain_top10 = candidates[:FINAL_TOP_K]
            plain_preds.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(
                    doc.spans, [r.chunk for r in plain_top10]),
            ))

            reranked_top10 = rerank(ann.hypothesis_text, candidates, top_k=FINAL_TOP_K)
            reranked_preds.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(
                    doc.spans, [r.chunk for r in reranked_top10]),
            ))

            n_done += 1
            if n_done % 100 == 0:
                print(f"  {n_done}/{len(golds) if False else '?'} cases, {time.time()-start:.0f}s elapsed", flush=True)

    def report(label, preds):
        r = evidence_recall_at_k(preds, golds)
        p = evidence_precision(preds, golds)
        m = mean_reciprocal_rank(preds, golds)
        print(f"{label:30} recall={r:.3f}  precision={p:.3f}  mrr={m:.3f}")
        return {"recall": r, "precision": p, "mrr": m}

    print(f"\nEvaluated on {len(golds)} cases\n")
    plain_result = report("sentence_k10 (no rerank)", plain_preds)
    reranked_result = report("sentence_k20->rerank->k10", reranked_preds)

    print("\n--- Verdict ---")
    if reranked_result["mrr"] > plain_result["mrr"]:
        print(f"  Reranking HELPS: MRR {reranked_result['mrr']:.3f} vs {plain_result['mrr']:.3f}")
    else:
        print(f"  Reranking HURTS: MRR {reranked_result['mrr']:.3f} vs {plain_result['mrr']:.3f} - "
              f"the general-purpose cross-encoder (trained on web search data, not legal text) "
              f"is not a reliable relevance judge for this domain.")

    import json
    Path("data/reranking_comparison.json").write_text(json.dumps(
        {"plain": plain_result, "reranked": reranked_result}, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
