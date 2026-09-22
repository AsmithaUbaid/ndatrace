#!/usr/bin/env python3
"""
Candidate-pool-size sweep on the winning retrieval config (sentence
chunking, mpnet embeddings, rerank with ms-marco-MiniLM-L-12-v2, final
top_k=7) - does giving the reranker more candidates to choose from
before truncating to top_k help?

Retrieves the widest pool once (40) per case, cross-encoder-scores all
40 once, then simulates each smaller pool size by truncating the dense
candidate list *before* reranking and taking the top_k=7 of that
truncated, re-sorted set - equivalent to actually re-running retrieval
at each pool size, without redundant reranker calls.
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
from pipeline.reranker import _get_reranker, DEFAULT_RERANKER_MODEL
from pipeline.retriever import Retriever

MAX_POOL_SIZE = 40
POOL_SIZES = [10, 20, 30, 40]
FINAL_TOP_K = 7


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    model = _get_reranker(DEFAULT_RERANKER_MODEL)

    golds: list[GoldCase] = []
    predictions_by_pool: dict[int, list[Prediction]] = {p: [] for p in POOL_SIZES}

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

            dense_hits = retriever.query(ann.hypothesis_text, top_k=MAX_POOL_SIZE)
            pairs = [(ann.hypothesis_text, r.chunk.text) for r in dense_hits]
            scores = model.predict(pairs) if pairs else []

            for pool_size in POOL_SIZES:
                subset = list(zip(dense_hits[:pool_size], scores[:pool_size]))
                subset.sort(key=lambda pair: pair[1], reverse=True)
                final_chunks = [r.chunk for r, _ in subset[:FINAL_TOP_K]]
                predictions_by_pool[pool_size].append(Prediction(
                    doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                    predicted_label=Label(ann.label),
                    retrieved_span_indices=map_chunks_to_gold_span_indices(
                        doc.spans, final_chunks),
                ))

            n_done += 1
            if n_done % 100 == 0:
                print(f"  {n_done} cases done, {time.time()-start:.0f}s elapsed", flush=True)

    print(f"\nEvaluated on {len(golds)} cases (final top_k={FINAL_TOP_K})\n")
    results = []
    for pool_size in POOL_SIZES:
        preds = predictions_by_pool[pool_size]
        r = evidence_recall_at_k(preds, golds)
        p = evidence_precision(preds, golds)
        m = mean_reciprocal_rank(preds, golds)
        print(f"pool_size={pool_size:<3}  recall={r:.3f}  precision={p:.3f}  mrr={m:.3f}")
        results.append({"pool_size": pool_size, "recall": r, "precision": p, "mrr": m})

    Path("data/pool_size_sweep.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
