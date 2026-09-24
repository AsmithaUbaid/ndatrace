#!/usr/bin/env python3
"""
Comprehensive retrieval comparison - the "try everything" pass.

Rounds 1-3 (see docs/experiments.md, docs/decisions.md) established:
sentence-level chunking beats clause/fixed, and cross-encoder reranking
helps. This round asks what's left: does a different embedding model do
better than the default (all-mpnet-base-v2)? Does hybrid BM25+dense
retrieval help? Does a bigger reranker help further?

All configs use sentence-level chunking (the established winner) and are
scored on the identical 614 dev Entailment/Contradiction cases used by
every other retrieval experiment in this project, so all results here are
directly comparable to the round 1-3 numbers.
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
from pipeline.sparse_retriever import SparseIndex, reciprocal_rank_fusion

EMBEDDING_MODELS = {
    "mpnet": None,  # None -> settings.embedding_model default (all-mpnet-base-v2)
    "bge": "BAAI/bge-base-en-v1.5",
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
}

# (label, kind, embedding_key, rerank_model_or_None, candidate_pool_size, top_k)
# Final top_k lowered to 5, not 10 - less context handed to the classifier
# per case (less prompt cost, less noise). A dedicated top-k sweep on the
# winning config runs afterward to find the actual best k.
FINAL_TOP_K = 5

CONFIGS = [
    ("dense_mpnet_k5", "dense", "mpnet", None, None, FINAL_TOP_K),
    ("dense_mpnet_rerankL6_k5 (round 3 shape)", "dense", "mpnet", "cross-encoder/ms-marco-MiniLM-L-6-v2", 20, FINAL_TOP_K),
    ("dense_bge_k5", "dense", "bge", None, None, FINAL_TOP_K),
    ("dense_bge_rerankL6_k5", "dense", "bge", "cross-encoder/ms-marco-MiniLM-L-6-v2", 20, FINAL_TOP_K),
    ("dense_minilm_k5", "dense", "minilm", None, None, FINAL_TOP_K),
    ("dense_minilm_rerankL6_k5", "dense", "minilm", "cross-encoder/ms-marco-MiniLM-L-6-v2", 20, FINAL_TOP_K),
    ("bm25_only_k5", "sparse", None, None, None, FINAL_TOP_K),
    ("hybrid_mpnet_bm25_k5", "hybrid", "mpnet", None, 20, FINAL_TOP_K),
    ("hybrid_mpnet_bm25_rerankL6_k5", "hybrid", "mpnet", "cross-encoder/ms-marco-MiniLM-L-6-v2", 20, FINAL_TOP_K),
    ("dense_mpnet_rerankL12_k5", "dense", "mpnet", "cross-encoder/ms-marco-MiniLM-L-12-v2", 20, FINAL_TOP_K),
]


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    golds: list[GoldCase] = []
    predictions_by_config: dict[str, list[Prediction]] = {label: [] for label, *_ in CONFIGS}

    start = time.time()
    n_done = 0
    for doc_id, cases in cases_by_doc.items():
        doc = cases[0][0]

        # Build each distinct dense retriever (per embedding model) and the
        # sparse index ONCE per document, reused across every config that needs it.
        dense_retrievers = {
            key: Retriever(doc.text, chunk_method="sentence", embedding_model=model_name)
            for key, model_name in EMBEDDING_MODELS.items()
            if any(cfg[2] == key for cfg in CONFIGS)
        }
        sparse_index = SparseIndex(dense_retrievers["mpnet"].chunks)  # chunks identical across embedding models

        for _, ann in cases:
            golds.append(GoldCase(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                gold_label=Label(ann.label),
                gold_span_indices=[s.span_index for s in ann.evidence_spans],
            ))

            for label, kind, embedding_key, rerank_model, pool_size, top_k in CONFIGS:
                if kind == "dense":
                    pool = pool_size or top_k
                    candidates = dense_retrievers[embedding_key].query(ann.hypothesis_text, top_k=pool)
                elif kind == "sparse":
                    hits = sparse_index.search(ann.hypothesis_text, top_k=top_k)
                    from pipeline.retriever import RetrievalResult
                    candidates = [RetrievalResult(chunk=c, score=s) for c, s in hits]
                elif kind == "hybrid":
                    pool = pool_size or top_k
                    dense_hits = [r.chunk for r in dense_retrievers[embedding_key].query(ann.hypothesis_text, top_k=pool)]
                    sparse_hits = [c for c, _ in sparse_index.search(ann.hypothesis_text, top_k=pool)]
                    fused = reciprocal_rank_fusion(dense_hits, sparse_hits)
                    from pipeline.retriever import RetrievalResult
                    candidates = [RetrievalResult(chunk=c, score=s) for c, s in fused]
                else:
                    raise ValueError(kind)

                if rerank_model:
                    final = rerank(ann.hypothesis_text, candidates, top_k=top_k, model_name=rerank_model)
                else:
                    final = candidates[:top_k]

                predictions_by_config[label].append(Prediction(
                    doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                    predicted_label=Label(ann.label),
                    retrieved_span_indices=map_chunks_to_gold_span_indices(doc.spans, [r.chunk for r in final]),
                ))

            n_done += 1
            if n_done % 50 == 0:
                print(f"  {n_done} cases done, {time.time()-start:.0f}s elapsed", flush=True)

    print(f"\nEvaluated on {len(golds)} cases\n")
    results = []
    for label, *_ in CONFIGS:
        preds = predictions_by_config[label]
        r = evidence_recall_at_k(preds, golds)
        p = evidence_precision(preds, golds)
        m = mean_reciprocal_rank(preds, golds)
        print(f"{label:42} recall={r:.3f}  precision={p:.3f}  mrr={m:.3f}")
        results.append({"label": label, "recall": r, "precision": p, "mrr": m, "n_cases": len(preds)})

    Path("data/full_retrieval_comparison.json").write_text(json.dumps(results, indent=2))

    best = max(results, key=lambda x: x["mrr"])
    print(f"\nBest MRR: {best['label']} ({best['mrr']:.3f})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
