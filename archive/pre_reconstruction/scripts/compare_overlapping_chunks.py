#!/usr/bin/env python3
"""
Overlapping sentence-level chunks - one-time indexing cost, no runtime
cost. `sentence_chunk` (the winning method) never overlaps: each sentence
is its own chunk, so evidence that reads naturally across a sentence
boundary (e.g. "...as follows: (a) ...") can get split across two
chunks, neither of which alone matches the hypothesis as well as the
pair would. A sliding window over sentences (window=3, stride=1 - each
chunk is 3 consecutive sentences, chunks overlap by 2) could recover
that boundary-spanning evidence without abandoning sentence-level
granularity.

Round 1 already tested overlap, but only on *fixed-size* (512-token)
chunking, which lost outright to sentence-level chunking - this is a new
combination: overlap at sentence granularity, not token-window granularity.

Builds its own FAISS index directly (bypassing Retriever, which only
knows non-overlapping chunk methods) over sliding-window chunks, then
runs the same retrieve-20 -> rerank(L-12) -> top-7 pipeline.

Compares, on the same 614-case dev set:
  A) baseline: sentence_chunk (no overlap) -> retrieve-20 -> rerank -> top-7
  B) overlapping: sliding window (3 sentences, stride 1) -> retrieve-20 -> rerank -> top-7
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
from pipeline.chunker import Chunk, sentence_chunk
from pipeline.config import settings
from pipeline.embedder import embed_texts, embed_query
from pipeline.indexer import build_index, search
from pipeline.parser import parse_contractnli_file
from pipeline.reranker import rerank
from pipeline.retriever import Retriever, RetrievalResult

CANDIDATE_POOL_SIZE = 20
FINAL_TOP_K = 7
WINDOW = 3
STRIDE = 1


def sliding_window_chunks(base_chunks: list[Chunk]) -> list[Chunk]:
    """Group consecutive sentence chunks into overlapping windows."""
    if not base_chunks:
        return []
    windows = []
    index = 0
    i = 0
    while i < len(base_chunks):
        group = base_chunks[i:i + WINDOW]
        windows.append(Chunk(
            text=" ".join(c.text for c in group),
            start_char=group[0].start_char, end_char=group[-1].end_char,
            chunk_index=index, method="sentence_overlap",
        ))
        index += 1
        if i + WINDOW >= len(base_chunks):
            break
        i += STRIDE
    return windows


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    golds: list[GoldCase] = []
    preds_baseline: list[Prediction] = []
    preds_overlap: list[Prediction] = []

    start = time.time()
    n_done = 0
    for doc_id, cases in cases_by_doc.items():
        doc = cases[0][0]
        baseline_retriever = Retriever(doc.text, chunk_method="sentence")

        window_chunks = sliding_window_chunks(baseline_retriever.chunks)
        window_embeddings = embed_texts([c.text for c in window_chunks]) if window_chunks else None
        window_index = build_index(window_embeddings, window_chunks) if window_chunks else None

        for _, ann in cases:
            golds.append(GoldCase(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                gold_label=Label(ann.label),
                gold_span_indices=[s.span_index for s in ann.evidence_spans],
            ))

            baseline_candidates = baseline_retriever.query(ann.hypothesis_text, top_k=CANDIDATE_POOL_SIZE)
            baseline_reranked = rerank(ann.hypothesis_text, baseline_candidates, top_k=FINAL_TOP_K,
                                        model_name="cross-encoder/ms-marco-MiniLM-L-12-v2")
            preds_baseline.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(
                    doc.spans, [r.chunk for r in baseline_reranked]),
            ))

            query_embedding = embed_query(ann.hypothesis_text)
            hits = search(window_index, query_embedding, top_k=CANDIDATE_POOL_SIZE)
            window_candidates = [RetrievalResult(chunk=c, score=s) for c, s in hits]
            window_reranked = rerank(ann.hypothesis_text, window_candidates, top_k=FINAL_TOP_K,
                                      model_name="cross-encoder/ms-marco-MiniLM-L-12-v2")
            preds_overlap.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(
                    doc.spans, [r.chunk for r in window_reranked]),
            ))

            n_done += 1
            if n_done % 100 == 0:
                print(f"  {n_done} cases done, {time.time()-start:.0f}s elapsed", flush=True)

    print(f"\nEvaluated on {len(golds)} cases\n")
    results = []
    for label, preds in [("baseline_sentence_top7", preds_baseline),
                          (f"sliding_window_{WINDOW}s_stride{STRIDE}_top7", preds_overlap)]:
        r = evidence_recall_at_k(preds, golds)
        p = evidence_precision(preds, golds)
        m = mean_reciprocal_rank(preds, golds)
        print(f"{label:<35}  recall={r:.3f}  precision={p:.3f}  mrr={m:.3f}")
        results.append({"label": label, "recall": r, "precision": p, "mrr": m, "n_cases": len(golds)})

    Path("data/overlapping_chunks_comparison.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
