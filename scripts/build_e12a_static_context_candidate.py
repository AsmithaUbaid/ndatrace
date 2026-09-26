#!/usr/bin/env python3
"""
E12A Stage A -- builds the static_context_candidate_v1 artifact: the SAME frozen retrieval_v1
BM25 top-20 candidate pool and cross-encoder reranker, exposing the top-K=11 chunks instead of
top-5. K=11 (not top-10) because a direct re-verification of E08's own reranked-rank data found
train::160::nda-10's gold evidence at reranked rank 11 -- top-10 alone covers only 5/6 of the
RETRIEVAL_FILTERING_LIMITED cases. No BM25/embedding/reranker re-training, no new query
generation -- purely exposing more of the already-computed frozen ranking. Zero model calls.

Model-facing artifact contains ONLY: case_id, document_id, hypothesis_text, ranked_chunk_ids,
ranked_chunk_text, ranked_chunk_offsets, ranked_chunk_bm25_candidate_scores,
ranked_chunk_rerank_scores, retrieval_config_version -- NO gold label, gold evidence, relevance
flag, or failure-bucket annotation (matches E07's own frozen artifact's safety contract exactly).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.reranker import rerank  # noqa: E402
from pipeline.retriever import RetrievalResult  # noqa: E402
from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

RETRIEVAL_V1_CONFIG = dict(method="bm25", chunk_method="clause", chunk_size=256, chunk_overlap=50,
                            embedding_model=None)
CANDIDATE_POOL_SIZE = 20  # unchanged from retrieval_v1
FINAL_K = 11  # the ONLY change from retrieval_v1's frozen top-5

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
OUT_PATH = REPO / "experiments/E12A_static_context_expansion/TRAIN_ARCH_v1_RETRIEVED_static_context_candidate_v1.json"


def main() -> int:
    manifest = json.load(open(MANIFEST_PATH))
    cases = manifest["cases"]
    train = json.load(open(REPO / "data/contractnli/train.json"))
    doc_text_by_id = {d["id"]: d["text"] for d in train["documents"]}

    out_cases = []
    for case in cases:
        doc_id = case["document_id"]
        chunks, index = build_or_load_index(doc_id, doc_text_by_id[doc_id], **RETRIEVAL_V1_CONFIG)
        hits = index.search(case["hypothesis_text"], top_k=CANDIDATE_POOL_SIZE)
        candidates = [RetrievalResult(chunk=c, score=s) for c, s in hits]
        reranked = rerank(case["hypothesis_text"], candidates, top_k=FINAL_K)

        out_cases.append({
            "case_id": case["case_id"], "document_id": doc_id,
            "hypothesis_id": case["hypothesis_id"], "hypothesis_text": case["hypothesis_text"],
            "retrieval_config_version": "static_context_candidate_v1",
            "ranked_chunk_ids": [r.chunk.chunk_index for r in reranked],
            "ranked_chunk_text": [r.chunk.text for r in reranked],
            "ranked_chunk_offsets": [[r.chunk.start_char, r.chunk.end_char] for r in reranked],
            "ranked_chunk_bm25_candidate_scores": [
                next((s for c, s in hits if c.chunk_index == r.chunk.chunk_index), None)
                for r in reranked
            ],
            "ranked_chunk_rerank_scores": [r.score for r in reranked],
        })

    # Safety check: no gold-leakage keys present anywhere in the output.
    forbidden_keys = {"gold_label", "gold_span_indices", "choice", "relevance_flag",
                       "expected_prediction", "failure_bucket"}
    for c in out_cases:
        assert not (forbidden_keys & set(c.keys())), f"gold leakage detected for {c['case_id']}"

    out = {
        "retrieval_config": {**RETRIEVAL_V1_CONFIG, "candidate_pool_size": CANDIDATE_POOL_SIZE,
                              "final_k": FINAL_K, "reranker_model": "cross-encoder/ms-marco-MiniLM-L-12-v2"},
        "final_k_selection_note": (
            "K=11, not top-10, because a direct re-verification of the 6 RETRIEVAL_FILTERING_"
            "LIMITED cases found train::160::nda-10's gold evidence at reranked rank 11 -- top-10 "
            "alone covers only 5/6. No K-sweep performed; 11 is the smallest fixed K covering all "
            "6, applied identically to all 150 cases (not case-selective)."
        ),
        "total_cases": len(out_cases),
        "cases": out_cases,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"wrote {OUT_PATH} ({len(out_cases)} cases, final_k={FINAL_K})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
