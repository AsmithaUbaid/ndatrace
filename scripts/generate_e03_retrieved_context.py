#!/usr/bin/env python3
"""
Generates TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json -- runs the TRUE FINAL frozen
retrieval_v1 config (BM25 clause_256 -> retrieve top-20 -> cross-encoder rerank -> top-5) over
all 150 TRAIN_PROMPT_v1 cases (INCLUDING NotMentioned -- retrieval never sees the gold label,
so NotMentioned gets whatever retrieval_v1 naturally returns, removing E03's earlier
Oracle-shortcut risk). No LLM calls, no embedding model at all -- the final matched control
found BM25+rerank ties dense+rerank almost exactly (4,370/4,371 identical outcomes), so BM25 is
selected for simplicity (no embedding model/vector index needed). The model-facing artifact
contains NO gold label, gold relevance flag, gold span ID, or expected answer -- gold truth is
kept in a separate file.
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

MANIFEST_PATH = REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1.json"
OUT_MODEL_FACING = REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json"
OUT_GOLD_SIDE = REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1_GOLD.json"


def retrieve_and_rerank(index, chunks, query_text: str) -> list:
    hits = index.search(query_text, top_k=CANDIDATE_POOL_SIZE)
    candidates = [RetrievalResult(chunk=c, score=s) for c, s in hits]
    reranked = cross_encoder_rerank(query_text, candidates, top_k=TOP_K)
    return [r.chunk for r in reranked]


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
        ranked = retrieve_and_rerank(index, chunks, case["hypothesis_text"])

        model_facing.append({
            "case_id": case["case_id"],
            "document_id": doc_id,
            "hypothesis_id": case["hypothesis_id"],
            "hypothesis_text": case["hypothesis_text"],
            "retrieval_config_version": "retrieval_v1",
            "ranked_chunk_ids": [c.chunk_index for c in ranked],
            "ranked_chunk_text": [c.text for c in ranked],
            "ranked_chunk_offsets": [[c.start_char, c.end_char] for c in ranked],
            # No score field kept model-facing beyond rank order -- rank order IS the score signal.
        })

        # Gold truth lives ONLY here, never in the model-facing file above.
        ann = doc["annotation_sets"][0]["annotations"][case["hypothesis_id"]]
        gold_side.append({
            "case_id": case["case_id"],
            "gold_label": ann["choice"],
            "gold_span_indices": ann["spans"],
        })

    with open(OUT_MODEL_FACING, "w") as f:
        json.dump({"manifest_id": "TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1",
                    "retrieval_config": RETRIEVAL_V1 | {
                        "candidate_pool_size": CANDIDATE_POOL_SIZE, "top_k": TOP_K,
                        "reranking": RERANKING, "reranker_model": RERANKER_MODEL,
                    },
                    "source_manifest": "TRAIN_PROMPT_v1", "total_cases": len(model_facing),
                    "cases": model_facing}, f, indent=2)

    with open(OUT_GOLD_SIDE, "w") as f:
        json.dump({"manifest_id": "TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1_GOLD",
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
