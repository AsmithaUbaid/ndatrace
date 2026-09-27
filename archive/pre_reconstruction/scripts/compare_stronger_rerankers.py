#!/usr/bin/env python3
"""
Round 10 (docs/decisions.md's retrieval revisit condition, finally
tried): T023 round 4 found the reranker size matters more than the
embedding model or hybrid retrieval - upgrading L-6 -> L-12 was the
single biggest win after the initial reranking round. The Decisions Log
flagged "a legal-domain-tuned embedding/reranker model, never yet tried"
as the next lever to close the RAG-vs-full-context accuracy gap
(2026-09-24, user pushback that the gap should be closed further, not
just architecturally justified).

No off-the-shelf legal-domain cross-encoder reranker exists on HuggingFace
in the CrossEncoder-compatible format this project uses (checked) - the
closest real lever is a STRONGER GENERAL reranker than the current
ms-marco-MiniLM-L-12-v2. Two credible candidates:
  - cross-encoder/ms-marco-electra-base (same MS MARCO training data,
    larger ELECTRA backbone instead of MiniLM)
  - BAAI/bge-reranker-base (a different, widely-used reranker family,
    trained on broader passage-ranking data, not MS MARCO-only)

Methodology matches scripts/compare_rule_boosted_retrieval.py (round 7)
exactly - same 614-case dev pool, same rule-boost fusion, same top_k=7 -
so results are directly comparable to the existing 0.645 MRR baseline
(dense_mpnet + rerankL12 + rule-boost + top7), at zero LLM cost (retrieval
metrics only, no classification).
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
from pipeline.chunker import Chunk
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.reranker import rerank
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_with_span
from pipeline.sparse_retriever import reciprocal_rank_fusion

CANDIDATE_POOL_SIZE = 20
FINAL_TOP_K = 7

RERANKERS = {
    "current_L12": "cross-encoder/ms-marco-MiniLM-L-12-v2",
    "electra_base": "cross-encoder/ms-marco-electra-base",
    "bge_reranker_base": "BAAI/bge-reranker-base",
}


def find_matching_chunk(chunks: list[Chunk], span: tuple[int, int]) -> Chunk | None:
    span_start, span_end = span
    best_chunk, best_overlap = None, 0
    for chunk in chunks:
        overlap = min(chunk.end_char, span_end) - max(chunk.start_char, span_start)
        if overlap > best_overlap:
            best_chunk, best_overlap = chunk, overlap
    return best_chunk


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    golds: list[GoldCase] = []
    preds_by_reranker: dict[str, list[Prediction]] = {name: [] for name in RERANKERS}

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

            _, span = classify_with_span(ann.hypothesis_id, doc.text)
            rule_chunk = find_matching_chunk(retriever.chunks, span) if span is not None else None

            for name, model_name in RERANKERS.items():
                reranked = rerank(ann.hypothesis_text, candidates, top_k=CANDIDATE_POOL_SIZE,
                                   model_name=model_name)
                reranked_chunks = [r.chunk for r in reranked]

                if rule_chunk is not None:
                    fused = reciprocal_rank_fusion(reranked_chunks, [rule_chunk])
                    final_chunks = [c for c, _ in fused[:FINAL_TOP_K]]
                else:
                    final_chunks = reranked_chunks[:FINAL_TOP_K]

                preds_by_reranker[name].append(Prediction(
                    doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                    predicted_label=Label(ann.label),
                    retrieved_span_indices=map_chunks_to_gold_span_indices(doc.spans, final_chunks),
                ))

            n_done += 1
            if n_done % 100 == 0:
                print(f"  {n_done} cases done, {time.time()-start:.0f}s elapsed", flush=True)

    print(f"\nEvaluated on {len(golds)} cases (rule-boosted, top_k={FINAL_TOP_K})\n")
    results = []
    for name, preds in preds_by_reranker.items():
        r = evidence_recall_at_k(preds, golds)
        p = evidence_precision(preds, golds)
        m = mean_reciprocal_rank(preds, golds)
        print(f"{name:<20}  recall={r:.3f}  precision={p:.3f}  mrr={m:.3f}")
        results.append({"reranker": name, "model_name": RERANKERS[name],
                         "recall": r, "precision": p, "mrr": m, "n_cases": len(golds)})

    Path("data/stronger_reranker_comparison.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
