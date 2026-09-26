#!/usr/bin/env python3
"""E13 Stage A: build the two model-facing artifacts for DEV_ARCH_v1 offline (zero model calls):
  DEV_ARCH_v1_FULL_CONTEXT.json        -- complete NDA text per case
  DEV_ARCH_v1_RETRIEVED_retrieval_v1.json -- frozen retrieval_v1 top-5 (BM25 -> clause_256 -> top-20 -> ms-marco-MiniLM-L-12-v2 rerank -> top-5), UNCHANGED
plus a separate evaluator-side _GOLD.json. Model-facing files carry no gold label/span/relevance/expected-result fields."""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.generate_e07_retrieved_context import RERANKER_MODEL, TOP_K, CANDIDATE_POOL_SIZE, RETRIEVAL_V1, retrieve_and_rerank  # noqa: E402
from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

D = REPO / "experiments/E13_gpt_context_architecture"


def main():
    man = json.load(open(D / "DEV_ARCH_v1.json")); dev = json.load(open(REPO / "data/contractnli/dev.json"))
    docs = {d["id"]: d for d in dev["documents"]}
    full, rag, gold = [], [], []
    for c in man["cases"]:
        doc = docs[c["document_id"]]; base = {"case_id": c["case_id"], "document_id": c["document_id"], "hypothesis_id": c["hypothesis_id"], "hypothesis_text": c["hypothesis_text"]}
        full.append(base | {"context_kind": "full_nda_text", "context_text": doc["text"], "context_chars": len(doc["text"])})
        chunks, index = build_or_load_index(c["document_id"], doc["text"], **RETRIEVAL_V1)
        ranked = retrieve_and_rerank(index, c["hypothesis_text"])
        rag.append(base | {"retrieval_config_version": "retrieval_v1", "ranked_chunk_ids": [r["chunk"].chunk_index for r in ranked],
                           "ranked_chunk_text": [r["chunk"].text for r in ranked], "ranked_chunk_offsets": [[r["chunk"].start_char, r["chunk"].end_char] for r in ranked],
                           "ranked_chunk_bm25_candidate_scores": [r["bm25_candidate_score"] for r in ranked], "ranked_chunk_rerank_scores": [r["rerank_score"] for r in ranked]})
        a = doc["annotation_sets"][0]["annotations"][c["hypothesis_id"]]
        gold.append({"case_id": c["case_id"], "gold_label": a["choice"], "gold_span_indices": a["spans"], "gold_label_matches_manifest": a["choice"] == c["gold_label"]})
    cfg = RETRIEVAL_V1 | {"candidate_pool_size": CANDIDATE_POOL_SIZE, "top_k": TOP_K, "reranking": True, "reranker_model": RERANKER_MODEL}
    json.dump({"manifest_id": "DEV_ARCH_v1_FULL_CONTEXT", "source_manifest": "DEV_ARCH_v1", "total_cases": 150, "cases": full}, open(D / "DEV_ARCH_v1_FULL_CONTEXT.json", "w"), indent=2)
    json.dump({"manifest_id": "DEV_ARCH_v1_RETRIEVED_retrieval_v1", "source_manifest": "DEV_ARCH_v1", "retrieval_config": cfg, "total_cases": 150, "cases": rag}, open(D / "DEV_ARCH_v1_RETRIEVED_retrieval_v1.json", "w"), indent=2)
    json.dump({"manifest_id": "DEV_ARCH_v1_GOLD", "note": "Scorer-side only. Never pass to a model.", "cases": gold}, open(D / "DEV_ARCH_v1_GOLD.json", "w"), indent=2)
    print("wrote artifacts; gold/manifest label agreement:", all(g["gold_label_matches_manifest"] for g in gold))


if __name__ == "__main__":
    main()
