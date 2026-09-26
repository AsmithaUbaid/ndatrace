#!/usr/bin/env python3
"""
E06 R5 — controlled reranking comparison (reconstruction-v2).

CONTROL: dense top-20 candidates (frozen clause_256 + bge-base-en-v1.5) -> take original top-5.
RERANK:  the SAME exact top-20 candidates -> cross-encoder rerank (ms-marco-MiniLM-L-12-v2,
         already cached) -> take reranked top-5.

The candidate pool is identical between arms -- only the final re-ordering/truncation to top-5
differs. No LLM calls. Reuses the same cached dense index as R2/R3/R4 (same cache key).
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

CONFIG = dict(method="dense", chunk_method="clause", chunk_size=256, chunk_overlap=50,
              embedding_model="BAAI/bge-base-en-v1.5")
CANDIDATE_POOL_SIZE = 20
FINAL_TOP_K = 5
RESULTS_DIR = REPO / "experiments/E06_retrieval_optimisation/results"


def main():
    cases = build_evidence_bearing_train_cases()
    by_doc: dict[int, list[dict]] = {}
    for c in cases:
        by_doc.setdefault(c["document_id"], []).append(c)

    control_pairs, rerank_pairs = [], []
    control_chunks_all, rerank_chunks_all = [], []
    candidate_gen_latencies, rerank_latencies = [], []
    per_case_outcomes = []

    for doc_id, doc_cases in by_doc.items():
        doc_text = doc_cases[0]["doc_text"]
        chunks, index = build_or_load_index(doc_id, doc_text, **CONFIG)

        for case in doc_cases:
            t0 = time.perf_counter()
            query_embedding = embed_query(case["hypothesis_text"], CONFIG["embedding_model"])
            hits = search(index, query_embedding, top_k=CANDIDATE_POOL_SIZE)
            candidate_gen_latencies.append((time.perf_counter() - t0) * 1000)

            candidates = [RetrievalResult(chunk=c, score=s) for c, s in hits]
            control_top5 = [r.chunk for r in candidates[:FINAL_TOP_K]]

            t1 = time.perf_counter()
            reranked = cross_encoder_rerank(case["hypothesis_text"], candidates, top_k=FINAL_TOP_K)
            rerank_latencies.append((time.perf_counter() - t1) * 1000)
            rerank_top5 = [r.chunk for r in reranked]

            pred_c, gold_c = score_retrieval(case, control_top5)
            pred_r, gold_r = score_retrieval(case, rerank_top5)
            control_pairs.append((pred_c, gold_c))
            rerank_pairs.append((pred_r, gold_r))
            control_chunks_all.append(control_top5)
            rerank_chunks_all.append(rerank_top5)

            control_hit = bool(set(pred_c.retrieved_span_indices) & set(gold_c.gold_span_indices))
            rerank_hit = bool(set(pred_r.retrieved_span_indices) & set(gold_r.gold_span_indices))
            per_case_outcomes.append({
                "case_id": case["case_id"], "gold_label": case["gold_label"],
                "control_hit": control_hit, "rerank_hit": rerank_hit,
                "recovered": (not control_hit) and rerank_hit,
                "regressed": control_hit and (not rerank_hit),
            })

    control_metrics = compute_retrieval_metrics(control_pairs)
    rerank_metrics = compute_retrieval_metrics(rerank_pairs)
    control_size = context_size_stats(control_chunks_all)
    rerank_size = context_size_stats(rerank_chunks_all)

    recovered = [o for o in per_case_outcomes if o["recovered"]]
    regressed = [o for o in per_case_outcomes if o["regressed"]]
    recovered_contradiction = [o for o in recovered if o["gold_label"] == "Contradiction"]
    regressed_contradiction = [o for o in regressed if o["gold_label"] == "Contradiction"]

    def lat_stats(vals):
        vals = sorted(vals)
        n = len(vals)
        return {"mean": sum(vals) / n, "median": vals[n // 2], "p90": vals[int(0.9 * n)]}

    result = {
        "candidate_pool_size": CANDIDATE_POOL_SIZE, "final_top_k": FINAL_TOP_K,
        "control": {"metrics": control_metrics, "context_size": vars(control_size)},
        "rerank": {"metrics": rerank_metrics, "context_size": vars(rerank_size)},
        "recovered_count": len(recovered), "regressed_count": len(regressed),
        "net_gain": len(recovered) - len(regressed),
        "contradiction_recovered": len(recovered_contradiction),
        "contradiction_regressed": len(regressed_contradiction),
        "candidate_generation_latency_ms": lat_stats(candidate_gen_latencies),
        "reranking_latency_ms": lat_stats(rerank_latencies),
        "total_query_latency_ms": lat_stats(
            [a + b for a, b in zip(candidate_gen_latencies, rerank_latencies)]
        ),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "run_E06_R5_rerank_comparison.json", "w") as f:
        json.dump(result, f, indent=2)
    with open(RESULTS_DIR / "run_E06_R5_per_case_outcomes.jsonl", "w") as f:
        for o in per_case_outcomes:
            f.write(json.dumps(o) + "\n")

    print(json.dumps({k: v for k, v in result.items()
                       if k not in ("control", "rerank")}, indent=2))
    print("control overall:", json.dumps(control_metrics["overall"], indent=2))
    print("rerank overall:", json.dumps(rerank_metrics["overall"], indent=2))
    print("control contradiction:", json.dumps(control_metrics["contradiction"], indent=2))
    print("rerank contradiction:", json.dumps(rerank_metrics["contradiction"], indent=2))


if __name__ == "__main__":
    main()
