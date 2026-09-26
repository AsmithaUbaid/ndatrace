#!/usr/bin/env python3
"""
Generates TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json -- runs the frozen retrieval_v1 config
(BM25 -> clause_256 -> top-20 -> cross-encoder rerank -> top-5, UNCHANGED from E06/E03) over all
150 TRAIN_ARCH_v1 cases (including NotMentioned -- retrieval never sees the gold label, so
NotMentioned gets whatever retrieval_v1 naturally returns, exactly as E03's equivalent artifact
did). No LLM calls. The model-facing artifact contains NO gold label, gold relevance flag, gold
span ID, or expected answer -- gold truth is kept in a separate file, mirroring E03's pattern
(scripts/generate_e03_retrieved_context.py) exactly, just retargeted at TRAIN_ARCH_v1.

Also captures BOTH the BM25 candidate-pool score and the final cross-encoder rerank score per
chunk (E03's equivalent artifact discarded these) -- E07's Stage A report asks for "retrieval
scores" and "candidate/rerank metadata," so this is captured now rather than added later.

retrieval_v1 itself is NOT modified, retuned, or re-evaluated for a different config here --
this is characterization/context-generation on a new manifest using the exact frozen pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.reranker import rerank as cross_encoder_rerank  # noqa: E402
from pipeline.retriever import RetrievalResult  # noqa: E402
from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

RETRIEVAL_V1 = dict(method="bm25", chunk_method="clause", chunk_size=256, chunk_overlap=50,
                     embedding_model=None)
CANDIDATE_POOL_SIZE = 20
TOP_K = 5
RERANKING = True
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
OUT_MODEL_FACING = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
OUT_GOLD_SIDE = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json"


def retrieve_and_rerank(index, query_text: str) -> list[dict]:
    """Returns the final top-5 chunks with BOTH the BM25 candidate score and the rerank score
    preserved (pipeline.reranker.rerank overwrites RetrievalResult.score with the rerank score,
    so the candidate score must be captured before reranking)."""
    hits = index.search(query_text, top_k=CANDIDATE_POOL_SIZE)
    candidate_score_by_chunk_index = {c.chunk_index: s for c, s in hits}
    candidates = [RetrievalResult(chunk=c, score=s) for c, s in hits]
    reranked = cross_encoder_rerank(query_text, candidates, top_k=TOP_K)
    return [
        {"chunk": r.chunk, "rerank_score": r.score,
         "bm25_candidate_score": candidate_score_by_chunk_index[r.chunk.chunk_index]}
        for r in reranked
    ]


def main():
    manifest = json.load(open(MANIFEST_PATH))
    train = json.load(open(REPO / "data/contractnli/train.json"))
    doc_lookup = {doc["id"]: doc for doc in train["documents"]}

    model_facing = []
    gold_side = []

    for case in manifest["cases"]:
        doc_id = case["document_id"]
        doc = doc_lookup[doc_id]
        chunks, index = build_or_load_index(doc_id, doc["text"], **RETRIEVAL_V1)
        ranked = retrieve_and_rerank(index, case["hypothesis_text"])

        model_facing.append({
            "case_id": case["case_id"],
            "document_id": doc_id,
            "hypothesis_id": case["hypothesis_id"],
            "hypothesis_text": case["hypothesis_text"],
            "retrieval_config_version": "retrieval_v1",
            "ranked_chunk_ids": [r["chunk"].chunk_index for r in ranked],
            "ranked_chunk_text": [r["chunk"].text for r in ranked],
            "ranked_chunk_offsets": [[r["chunk"].start_char, r["chunk"].end_char] for r in ranked],
            "ranked_chunk_bm25_candidate_scores": [r["bm25_candidate_score"] for r in ranked],
            "ranked_chunk_rerank_scores": [r["rerank_score"] for r in ranked],
            # No score field beyond the above kept as a separate "confidence" signal to the
            # model -- rank order IS the primary signal shown; scores are evaluator-side metadata.
        })

        # Gold truth lives ONLY here, never in the model-facing file above.
        ann = doc["annotation_sets"][0]["annotations"][case["hypothesis_id"]]
        gold_side.append({
            "case_id": case["case_id"],
            "gold_label": ann["choice"],
            "gold_span_indices": ann["spans"],
        })

    with open(OUT_MODEL_FACING, "w") as f:
        json.dump({"manifest_id": "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1",
                    "retrieval_config": RETRIEVAL_V1 | {
                        "candidate_pool_size": CANDIDATE_POOL_SIZE, "top_k": TOP_K,
                        "reranking": RERANKING, "reranker_model": RERANKER_MODEL,
                    },
                    "source_manifest": "TRAIN_ARCH_v1", "total_cases": len(model_facing),
                    "cases": model_facing}, f, indent=2)

    with open(OUT_GOLD_SIDE, "w") as f:
        json.dump({"manifest_id": "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD",
                    "note": "Scorer-side only. Never pass this file's contents to a classifier.",
                    "cases": gold_side}, f, indent=2)

    label_counts = {}
    for g in gold_side:
        label_counts[g["gold_label"]] = label_counts.get(g["gold_label"], 0) + 1
    print(f"wrote {OUT_MODEL_FACING} ({len(model_facing)} cases)")
    print(f"wrote {OUT_GOLD_SIDE} (gold-side only)")
    print("label counts in this manifest:", label_counts)


if __name__ == "__main__":
    main()
