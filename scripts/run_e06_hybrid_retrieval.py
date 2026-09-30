#!/usr/bin/env python3
"""
E06 hybrid retrieval (final) — the missing arm of the lexical/dense/hybrid/
reranked comparison. R0/R2/R4 (BM25, dense-mpnet, dense-bge) and the matched
lexical-vs-dense-rerank control already exist under the frozen protocol (clause_256, K=5,
4,371-case evidence-bearing TRAIN universe); hybrid (BM25+dense via Reciprocal Rank Fusion)
was never run under final's protocol, only hypothesised from legacy
work. This script fills that one gap, reusing the exact same population/chunking/scorer/
metrics as every other E06 run and pipeline/sparse_retriever.py's existing
reciprocal_rank_fusion (rank-based, not raw-score averaging, per that module's own docstring
on why BM25/cosine scores aren't comparable).

Two arms, both fused from the same two top-20 candidate pools:
  - hybrid_plain: RRF-fused top-5, no reranker (component C in the retrieval-architecture brief)
  - hybrid_plus_rerank: RRF-fused top-20 pool -> cross-encoder rerank -> top-5 (component E,
    included since it reuses existing rerank/RRF code with no new logic)

No LLM/API call anywhere. No DEV/TEST access — TRAIN only, same as every other E06 run.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.retrieval_eval import (  # noqa: E402
    build_evidence_bearing_train_cases,
    compute_retrieval_metrics,
    context_size_stats,
    score_retrieval,
)
from pipeline.embedder import embed_query  # noqa: E402
from pipeline.indexer import search  # noqa: E402
from pipeline.reranker import rerank as cross_encoder_rerank  # noqa: E402
from pipeline.retriever import RetrievalResult  # noqa: E402
from pipeline.sparse_retriever import reciprocal_rank_fusion  # noqa: E402
from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

CHUNK_CONFIG = dict(chunk_method="clause", chunk_size=256, chunk_overlap=50)
DENSE_EMBEDDING = "BAAI/bge-base-en-v1.5"  # R4's frozen embedding winner, same as the matched control
CANDIDATE_POOL_SIZE = 20
FINAL_TOP_K = 5
RESULTS_DIR = REPO / "experiments/E06_retrieval_optimisation/results"


def lat_stats(vals):
    vals = sorted(vals)
    n = len(vals)
    if n == 0:
        return {"mean": None, "median": None, "p90": None}
    return {"mean": sum(vals) / n, "median": vals[n // 2], "p90": vals[int(0.9 * n)]}


def main():
    cases = build_evidence_bearing_train_cases()
    by_doc: dict[int, list[dict]] = {}
    for c in cases:
        by_doc.setdefault(c["document_id"], []).append(c)

    plain_pairs, rerank_pairs = [], []
    plain_chunks_all, rerank_chunks_all = [], []
    bm25_cand_lat, dense_cand_lat, fusion_lat, rerank_lat = [], [], [], []
    per_case = []

    t_start = time.perf_counter()

    for doc_id, doc_cases in by_doc.items():
        doc_text = doc_cases[0]["doc_text"]
        bm25_chunks, bm25_index = build_or_load_index(
            doc_id, doc_text, method="bm25", embedding_model=None, **CHUNK_CONFIG)
        dense_chunks, dense_index = build_or_load_index(
            doc_id, doc_text, method="dense", embedding_model=DENSE_EMBEDDING, **CHUNK_CONFIG)

        for case in doc_cases:
            query = case["hypothesis_text"]

            t0 = time.perf_counter()
            bm25_ranked = [c for c, _ in bm25_index.search(query, top_k=CANDIDATE_POOL_SIZE)]
            bm25_cand_lat.append((time.perf_counter() - t0) * 1000)

            t1 = time.perf_counter()
            query_embedding = embed_query(query, DENSE_EMBEDDING)
            dense_ranked = [c for c, _ in search(dense_index, query_embedding, top_k=CANDIDATE_POOL_SIZE)]
            dense_cand_lat.append((time.perf_counter() - t1) * 1000)

            t2 = time.perf_counter()
            fused = reciprocal_rank_fusion(bm25_ranked, dense_ranked)  # [(chunk, rrf_score), ...] desc
            fusion_lat.append((time.perf_counter() - t2) * 1000)

            hybrid_plain_top5 = [c for c, _ in fused[:FINAL_TOP_K]]

            t3 = time.perf_counter()
            fused_pool = [RetrievalResult(chunk=c, score=s) for c, s in fused[:CANDIDATE_POOL_SIZE]]
            hybrid_reranked = cross_encoder_rerank(query, fused_pool, top_k=FINAL_TOP_K)
            rerank_lat.append((time.perf_counter() - t3) * 1000)
            hybrid_rerank_top5 = [r.chunk for r in hybrid_reranked]

            plain_chunks_all.append(hybrid_plain_top5)
            rerank_chunks_all.append(hybrid_rerank_top5)

            pred_p, gold_p = score_retrieval(case, hybrid_plain_top5)
            pred_r, gold_r = score_retrieval(case, hybrid_rerank_top5)
            plain_pairs.append((pred_p, gold_p))
            rerank_pairs.append((pred_r, gold_r))

            per_case.append({
                "case_id": case["case_id"], "gold_label": case["gold_label"],
                "hybrid_plain_hit": bool(set(pred_p.retrieved_span_indices) & set(gold_p.gold_span_indices)),
                "hybrid_rerank_hit": bool(set(pred_r.retrieved_span_indices) & set(gold_r.gold_span_indices)),
            })

    wall_seconds = time.perf_counter() - t_start

    plain_metrics = compute_retrieval_metrics(plain_pairs)
    rerank_metrics = compute_retrieval_metrics(rerank_pairs)

    result = {
        "config": {
            "chunking": CHUNK_CONFIG, "candidate_pool_size": CANDIDATE_POOL_SIZE,
            "final_top_k": FINAL_TOP_K, "fusion": "reciprocal_rank_fusion (RRF, k=60)",
            "bm25": "rank_bm25.BM25Okapi (pipeline/sparse_retriever.py)",
            "dense_embedding": DENSE_EMBEDDING,
            "reranker": "cross-encoder/ms-marco-MiniLM-L-12-v2 (hybrid_plus_rerank arm only)",
        },
        "n_documents": len(by_doc), "n_cases": len(plain_pairs),
        "hybrid_plain": {
            "metrics": plain_metrics,
            "context_size": vars(context_size_stats(plain_chunks_all)),
        },
        "hybrid_plus_rerank": {
            "metrics": rerank_metrics,
            "context_size": vars(context_size_stats(rerank_chunks_all)),
        },
        "latency_ms": {
            "bm25_candidate_generation": lat_stats(bm25_cand_lat),
            "dense_candidate_generation": lat_stats(dense_cand_lat),
            "rrf_fusion": lat_stats(fusion_lat),
            "cross_encoder_reranking": lat_stats(rerank_lat),
        },
        "experiment_wall_seconds_this_run": wall_seconds,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "run_E06_hybrid_rrf.json", "w") as f:
        json.dump(result, f, indent=2)
    with open(RESULTS_DIR / "run_E06_hybrid_rrf_cases.jsonl", "w") as f:
        for o in per_case:
            f.write(json.dumps(o) + "\n")

    print(json.dumps({k: v for k, v in result.items()
                       if k not in ("hybrid_plain", "hybrid_plus_rerank")}, indent=2))
    print("Hybrid (plain RRF, no rerank) overall:", json.dumps(plain_metrics["overall"], indent=2))
    print("Hybrid (plain RRF) contradiction:", json.dumps(plain_metrics["contradiction"], indent=2))
    print("Hybrid + rerank overall:", json.dumps(rerank_metrics["overall"], indent=2))
    print("Hybrid + rerank contradiction:", json.dumps(rerank_metrics["contradiction"], indent=2))


if __name__ == "__main__":
    main()
