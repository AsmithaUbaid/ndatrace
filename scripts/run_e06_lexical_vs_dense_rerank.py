#!/usr/bin/env python3
"""
E06 final matched control (reconstruction-v2): LEXICAL+RERANK vs DENSE+RERANK.

Both arms: chunking=clause_256, candidate pool=top-20, reranker=ms-marco-MiniLM-L-12-v2,
final K=5, identical 4,371-case universe, identical query/scorer/metrics. The ONLY changed
capability is the candidate generator: BM25 vs. BAAI/bge-base-en-v1.5. This isolates whether
dense candidate generation earns its complexity ONCE a reranker is already in the pipeline --
the historical project hypothesis was that embedding choice barely matters post-reranking; R6
already found the opposite pre-reranking (R4), so this checks the post-reranking case directly.

No LLM calls. Reuses the same cached dense index (R4/R5) and builds a matching cached BM25
index for a fair comparison.
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
from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

CHUNK_CONFIG = dict(chunk_method="clause", chunk_size=256, chunk_overlap=50)
DENSE_EMBEDDING = "BAAI/bge-base-en-v1.5"
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

    bm25_pool_pairs, dense_pool_pairs = [], []
    bm25_rerank_pairs, dense_rerank_pairs = [], []
    bm25_rerank_chunks_all, dense_rerank_chunks_all = [], []
    bm25_cand_lat, dense_cand_lat = [], []
    bm25_rerank_lat, dense_rerank_lat = [], []
    per_case = []

    t_bm25_build_start = time.perf_counter()
    t_dense_build_start = None  # dense index already built/cached from R4/R5 -- measured separately below

    for doc_id, doc_cases in by_doc.items():
        doc_text = doc_cases[0]["doc_text"]
        bm25_chunks, bm25_index = build_or_load_index(
            doc_id, doc_text, method="bm25", embedding_model=None, **CHUNK_CONFIG)
        dense_chunks, dense_index = build_or_load_index(
            doc_id, doc_text, method="dense", embedding_model=DENSE_EMBEDDING, **CHUNK_CONFIG)

        for case in doc_cases:
            # --- BM25 candidate pool ---
            t0 = time.perf_counter()
            bm25_hits = bm25_index.search(case["hypothesis_text"], top_k=CANDIDATE_POOL_SIZE)
            bm25_cand_lat.append((time.perf_counter() - t0) * 1000)
            bm25_candidates = [RetrievalResult(chunk=c, score=s) for c, s in bm25_hits]
            bm25_pool_chunks = [r.chunk for r in bm25_candidates]

            # --- Dense candidate pool ---
            t1 = time.perf_counter()
            query_embedding = embed_query(case["hypothesis_text"], DENSE_EMBEDDING)
            dense_hits = search(dense_index, query_embedding, top_k=CANDIDATE_POOL_SIZE)
            dense_cand_lat.append((time.perf_counter() - t1) * 1000)
            dense_candidates = [RetrievalResult(chunk=c, score=s) for c, s in dense_hits]
            dense_pool_chunks = [r.chunk for r in dense_candidates]

            # --- Rerank both pools with the SAME cross-encoder ---
            t2 = time.perf_counter()
            bm25_reranked = cross_encoder_rerank(case["hypothesis_text"], bm25_candidates, top_k=FINAL_TOP_K)
            bm25_rerank_lat.append((time.perf_counter() - t2) * 1000)
            t3 = time.perf_counter()
            dense_reranked = cross_encoder_rerank(case["hypothesis_text"], dense_candidates, top_k=FINAL_TOP_K)
            dense_rerank_lat.append((time.perf_counter() - t3) * 1000)

            bm25_top5 = [r.chunk for r in bm25_reranked]
            dense_top5 = [r.chunk for r in dense_reranked]

            # Pool-level (top-20, pre-rerank) recall -- upstream coverage check
            bm25_pool_pairs.append(score_retrieval(case, bm25_pool_chunks))
            dense_pool_pairs.append(score_retrieval(case, dense_pool_chunks))

            pred_b, gold_b = score_retrieval(case, bm25_top5)
            pred_d, gold_d = score_retrieval(case, dense_top5)
            bm25_rerank_pairs.append((pred_b, gold_b))
            dense_rerank_pairs.append((pred_d, gold_d))
            bm25_rerank_chunks_all.append(bm25_top5)
            dense_rerank_chunks_all.append(dense_top5)

            bm25_hit = bool(set(pred_b.retrieved_span_indices) & set(gold_b.gold_span_indices))
            dense_hit = bool(set(pred_d.retrieved_span_indices) & set(gold_d.gold_span_indices))
            per_case.append({
                "case_id": case["case_id"], "gold_label": case["gold_label"],
                "bm25_rerank_hit": bm25_hit, "dense_rerank_hit": dense_hit,
            })

    bm25_build_seconds = time.perf_counter() - t_bm25_build_start

    bm25_pool_metrics = compute_retrieval_metrics(bm25_pool_pairs)
    dense_pool_metrics = compute_retrieval_metrics(dense_pool_pairs)
    bm25_rerank_metrics = compute_retrieval_metrics(bm25_rerank_pairs)
    dense_rerank_metrics = compute_retrieval_metrics(dense_rerank_pairs)

    both_hit = sum(1 for o in per_case if o["bm25_rerank_hit"] and o["dense_rerank_hit"])
    both_miss = sum(1 for o in per_case if not o["bm25_rerank_hit"] and not o["dense_rerank_hit"])
    bm25_only = sum(1 for o in per_case if o["bm25_rerank_hit"] and not o["dense_rerank_hit"])
    dense_only = sum(1 for o in per_case if o["dense_rerank_hit"] and not o["bm25_rerank_hit"])

    contradiction_cases = [o for o in per_case if o["gold_label"] == "Contradiction"]
    c_both_hit = sum(1 for o in contradiction_cases if o["bm25_rerank_hit"] and o["dense_rerank_hit"])
    c_bm25_only = sum(1 for o in contradiction_cases if o["bm25_rerank_hit"] and not o["dense_rerank_hit"])
    c_dense_only = sum(1 for o in contradiction_cases if o["dense_rerank_hit"] and not o["bm25_rerank_hit"])
    c_both_miss = sum(1 for o in contradiction_cases if not o["bm25_rerank_hit"] and not o["dense_rerank_hit"])

    result = {
        "config": {"chunking": CHUNK_CONFIG, "candidate_pool_size": CANDIDATE_POOL_SIZE,
                   "final_top_k": FINAL_TOP_K, "reranker": "ms-marco-MiniLM-L-12-v2",
                   "dense_embedding": DENSE_EMBEDDING},
        "bm25_pool_recall_at_20": bm25_pool_metrics["overall"]["evidence_recall_at_k"],
        "dense_pool_recall_at_20": dense_pool_metrics["overall"]["evidence_recall_at_k"],
        "bm25_plus_rerank": {"metrics": bm25_rerank_metrics,
                              "context_size": vars(context_size_stats(bm25_rerank_chunks_all))},
        "dense_plus_rerank": {"metrics": dense_rerank_metrics,
                               "context_size": vars(context_size_stats(dense_rerank_chunks_all))},
        "overlap_analysis": {
            "both_hit": both_hit, "both_miss": both_miss,
            "bm25_only_hit": bm25_only, "dense_only_hit": dense_only,
            "note": "bm25_only_hit = cases BM25+rerank solved that dense+rerank missed, and vice versa",
        },
        "contradiction_overlap_analysis": {
            "both_hit": c_both_hit, "both_miss": c_both_miss,
            "bm25_only_hit": c_bm25_only, "dense_only_hit": c_dense_only,
        },
        "latency_ms": {
            "bm25_candidate_generation": lat_stats(bm25_cand_lat),
            "dense_candidate_generation": lat_stats(dense_cand_lat),
            "bm25_reranking": lat_stats(bm25_rerank_lat),
            "dense_reranking": lat_stats(dense_rerank_lat),
        },
        # NOTE: t_bm25_build_start is set before the per-document loop that runs BOTH candidate
        # generators and BOTH rerankers, so this is total script wall time, not isolated BM25
        # index-build time. Isolated BM25 build time (~1.9s across all 423 docs) was measured
        # separately during Stage A calibration.
        "experiment_wall_seconds_this_run": bm25_build_seconds,
        "bm25_index_build_seconds_isolated": 1.9,  # from Stage A calibration, all 423 docs
    }

    with open(RESULTS_DIR / "run_E06_lexical_vs_dense_rerank.json", "w") as f:
        json.dump(result, f, indent=2)
    with open(RESULTS_DIR / "run_E06_lexical_vs_dense_rerank_cases.jsonl", "w") as f:
        for o in per_case:
            f.write(json.dumps(o) + "\n")

    print(json.dumps({k: v for k, v in result.items()
                       if k not in ("bm25_plus_rerank", "dense_plus_rerank")}, indent=2))
    print("BM25+rerank overall:", json.dumps(bm25_rerank_metrics["overall"], indent=2))
    print("Dense+rerank overall:", json.dumps(dense_rerank_metrics["overall"], indent=2))
    print("BM25+rerank contradiction:", json.dumps(bm25_rerank_metrics["contradiction"], indent=2))
    print("Dense+rerank contradiction:", json.dumps(dense_rerank_metrics["contradiction"], indent=2))


if __name__ == "__main__":
    main()
