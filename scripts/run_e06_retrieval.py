#!/usr/bin/env python3
"""
E06 retrieval optimisation runner (reconstruction-v2) — Stage B only. NOT executed during
Stage A prep.

Runs ONE retrieval configuration (chunking + embedding + retrieval method + top_k) over the
full 4,371-case evidence-bearing TRAIN universe (Entailment + Contradiction), scores it with
E00's frozen evidence-hit semantics, and saves per-case results + aggregate metrics. No LLM
call anywhere — retrieval is deterministic/local (BM25 or a local sentence-transformers
bi-encoder), per the reconstruction brief's explicit "do NOT call Qwen/GPT-5-mini/any hosted
model in E06."

Usage (Stage B only, after explicit approval), one call per configuration, e.g.:
    python scripts/run_e06_retrieval.py --run-id R0 --method bm25 \
        --chunk-method clause --chunk-size 512 --top-k 5

    python scripts/run_e06_retrieval.py --run-id R1 --method dense \
        --chunk-method clause --chunk-size 512 --embedding-model all-mpnet-base-v2 --top-k 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.retrieval_eval import (  # noqa: E402
    build_evidence_bearing_train_cases,
    cache_path,
    compute_retrieval_metrics,
    context_size_stats,
    load_cached,
    retriever_cache_key,
    save_cached,
    score_retrieval,
)
from pipeline.chunker import Chunk, clause_aware_chunk, fixed_size_chunk, sentence_chunk  # noqa: E402
from pipeline.embedder import embed_query, embed_texts  # noqa: E402
from pipeline.indexer import build_index, search  # noqa: E402
from pipeline.sparse_retriever import SparseIndex  # noqa: E402

RESULTS_DIR = REPO / "experiments/E06_retrieval_optimisation/results"


def chunk_document(text: str, chunk_method: str, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    if chunk_method == "clause":
        return clause_aware_chunk(text, chunk_size)
    if chunk_method == "fixed":
        return fixed_size_chunk(text, chunk_size, chunk_overlap)
    if chunk_method == "sentence":
        return sentence_chunk(text)
    raise ValueError(f"Unknown chunk_method: {chunk_method!r}")


def build_or_load_index(doc_id: int, doc_text: str, method: str, chunk_method: str,
                         chunk_size: int, chunk_overlap: int, embedding_model: str | None):
    """Returns (chunks, searchable_index) for one document, cached by config -- top_k is NOT
    part of the cache key (see evaluation.retrieval_eval.retriever_cache_key's docstring)."""
    key = retriever_cache_key(doc_id, chunk_method, chunk_size, chunk_overlap,
                               embedding_model or "default", method)
    cached = load_cached(key)
    if cached is not None:
        return cached

    chunks = chunk_document(doc_text, chunk_method, chunk_size, chunk_overlap)
    if method == "bm25":
        index = SparseIndex(chunks)
    elif method == "dense":
        embeddings = embed_texts([c.text for c in chunks], embedding_model)
        index = build_index(embeddings, chunks)
    else:
        raise ValueError(f"Unknown method: {method!r}")

    save_cached(key, (chunks, index))
    return chunks, index


def query_index(method: str, index, chunks: list[Chunk], query_text: str,
                 top_k: int, embedding_model: str | None) -> list[Chunk]:
    if method == "bm25":
        return [c for c, _ in index.search(query_text, top_k=top_k)]
    if method == "dense":
        query_embedding = embed_query(query_text, embedding_model)
        hits = search(index, query_embedding, top_k=top_k)
        return [c for c, _ in hits]
    raise ValueError(f"Unknown method: {method!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="e.g. R0, R1, R2_clause256")
    parser.add_argument("--method", required=True, choices=["bm25", "dense"])
    parser.add_argument("--chunk-method", required=True, choices=["clause", "fixed", "sentence"])
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    parser.add_argument("--embedding-model", default=None, help="Only used when --method dense")
    parser.add_argument("--top-k", type=int, required=True)
    parser.add_argument("--limit-docs", type=int, default=None,
                         help="For a smoke-test subset of documents only")
    args = parser.parse_args()

    cases = build_evidence_bearing_train_cases()
    doc_ids_seen = set()

    # Group cases by document so each document's (expensive) index is built exactly once,
    # then queried once per hypothesis it has an Entailment/Contradiction case for.
    by_doc: dict[int, list[dict]] = {}
    for c in cases:
        by_doc.setdefault(c["document_id"], []).append(c)

    doc_ids = sorted(by_doc.keys())
    if args.limit_docs:
        doc_ids = doc_ids[: args.limit_docs]

    t_build_start = time.perf_counter()
    pairs = []
    query_latencies = []
    all_ranked_chunks = []
    per_case_records = []

    for doc_id in doc_ids:
        doc_cases = by_doc[doc_id]
        doc_text = doc_cases[0]["doc_text"]
        chunks, index = build_or_load_index(
            doc_id, doc_text, args.method, args.chunk_method, args.chunk_size,
            args.chunk_overlap, args.embedding_model,
        )
        for case in doc_cases:
            t0 = time.perf_counter()
            ranked = query_index(args.method, index, chunks, case["hypothesis_text"],
                                  args.top_k, args.embedding_model)
            query_latencies.append((time.perf_counter() - t0) * 1000)

            pred, gold = score_retrieval(case, ranked)
            pairs.append((pred, gold))
            all_ranked_chunks.append(ranked)
            per_case_records.append({
                "case_id": case["case_id"], "document_id": doc_id,
                "hypothesis_id": case["hypothesis_id"], "gold_label": case["gold_label"],
                "retrieved_span_indices": pred.retrieved_span_indices,
                "gold_span_indices": gold.gold_span_indices,
                "top_chunk_ids": [c.chunk_index for c in ranked],
            })
        doc_ids_seen.add(doc_id)

    build_and_query_seconds = time.perf_counter() - t_build_start

    metrics = compute_retrieval_metrics(pairs)
    size_stats = context_size_stats(all_ranked_chunks)
    query_latencies.sort()

    result = {
        "run_id": args.run_id,
        "config": {
            "method": args.method, "chunk_method": args.chunk_method,
            "chunk_size": args.chunk_size, "chunk_overlap": args.chunk_overlap,
            "embedding_model": args.embedding_model, "top_k": args.top_k,
        },
        "n_documents": len(doc_ids_seen), "n_cases": len(pairs),
        "metrics": metrics,
        "context_size": vars(size_stats),
        "latency_ms": {
            "mean": sum(query_latencies) / len(query_latencies) if query_latencies else None,
            "median": query_latencies[len(query_latencies) // 2] if query_latencies else None,
            "p90": query_latencies[int(0.9 * len(query_latencies))] if query_latencies else None,
        },
        "total_build_and_query_seconds": build_and_query_seconds,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"run_E06_{args.run_id}.json", "w") as f:
        json.dump(result, f, indent=2)
    with open(RESULTS_DIR / f"run_E06_{args.run_id}_cases.jsonl", "w") as f:
        for r in per_case_records:
            f.write(json.dumps(r) + "\n")

    print(json.dumps({k: v for k, v in result.items() if k != "config"}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
