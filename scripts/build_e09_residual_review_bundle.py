#!/usr/bin/env python3
"""
E09 Stage B -- build the manual-review data bundle for all 39 GPT joint failures.

Zero model calls: local BM25 re-query only (same free/deterministic precedent as E08's
reranker-limited pilot diagnostic), plus reads of already-saved E05/E07/E08B outputs. This
script does NOT assign the failure taxonomy -- it only assembles everything a human/evaluator
needs to make that judgment, per case: requirement, GPT prediction/evidence, final top-5 context,
BM25 top-20 candidate pool + ranks, gold label, gold evidence text (evaluator-side), E05
full-context outcome, E07 Qwen-RAG outcome.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.run_e06_retrieval import build_or_load_index  # noqa: E402

RETRIEVAL_V1_CONFIG = dict(method="bm25", chunk_method="clause", chunk_size=256, chunk_overlap=50,
                            embedding_model=None)
CANDIDATE_POOL_SIZE = 20

E08B_DIR = REPO / "experiments/E08B_stronger_model_diagnostic"
E07_DIR = REPO / "experiments/E07_standard_rag"
E05_DIR = REPO / "experiments/E05_full_context"
OUT_PATH = REPO / "experiments/E09_agent_justification/results/residual_review_bundle.json"


def main() -> int:
    import csv

    gpt_cases = {json.loads(l)["case_id"]: json.loads(l)
                 for l in open(E08B_DIR / "results/run_E08B_A2_gpt5mini_train_cases.jsonl")}
    qwen_cases = {json.loads(l)["case_id"]: json.loads(l)
                  for l in open(E07_DIR / "results/run_E07_A2_train_cases.jsonl")}
    e05_cases = {json.loads(l)["case_id"]: json.loads(l)
                 for l in open(E05_DIR / "results/run_E05_A1_train_cases.jsonl")}
    retrieved = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    retrieved_by_id = {c["case_id"]: c for c in retrieved["cases"]}
    gold = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1_GOLD.json"))
    gold_by_id = {c["case_id"]: c for c in gold["cases"]}
    manifest = json.load(open(E05_DIR / "TRAIN_ARCH_v1.json"))
    hypothesis_text_by_id = {c["case_id"]: c["hypothesis_text"] for c in manifest["cases"]}
    train = json.load(open(REPO / "data/contractnli/train.json"))
    doc_text_by_id = {d["id"]: d["text"] for d in train["documents"]}
    doc_spans_by_id = {d["id"]: d["spans"] for d in train["documents"]}

    # joint_success isn't stored in the raw run jsonl -- read it from the already-computed
    # analysis CSV, which uses the identical scorer as E07 (AST-verified in the prior review).
    failure_rows = {r["case_id"]: r for r in
                     csv.DictReader(open(E08B_DIR / "results/gpt5mini_failure_analysis.csv"))}
    residual_ids = [cid for cid, r in failure_rows.items() if r["joint_success"] != "True"]
    assert len(residual_ids) == 39, f"expected 39 residuals, found {len(residual_ids)}"

    bundle = []
    for cid in sorted(residual_ids):
        g = gpt_cases[cid]
        q = qwen_cases.get(cid)
        e05 = e05_cases.get(cid)
        rc = retrieved_by_id[cid]
        gold_c = gold_by_id[cid]
        fr = failure_rows[cid]

        doc_id = g["document_id"]
        doc_spans = doc_spans_by_id[doc_id]
        gold_span_idx = gold_c["gold_span_indices"]
        gold_evidence_text = [
            doc_text_by_id[doc_id][s:e] for i in gold_span_idx for (s, e) in [doc_spans[i]]
        ]

        # Local, free BM25 top-20 re-query for candidate-pool visibility (same precedent as E08's
        # reranker-limited pilot diagnostic) -- checks whether gold evidence exists anywhere in
        # the BM25 candidate pool the reranker chose from, and at what rank.
        hypothesis_text = hypothesis_text_by_id[cid]
        chunks, index = build_or_load_index(doc_id, doc_text_by_id[doc_id], **RETRIEVAL_V1_CONFIG)
        hits = index.search(hypothesis_text, top_k=CANDIDATE_POOL_SIZE)
        gold_span_set = set(gold_span_idx)

        def _chunk_overlaps_gold(chunk) -> bool:
            for idx in gold_span_set:
                s, e = doc_spans[idx]
                if chunk.start_char < e and chunk.end_char > s:
                    return True
            return False

        bm25_top20_gold_rank = None
        for rank, (chunk, _score) in enumerate(hits, start=1):
            if gold_span_set and _chunk_overlaps_gold(chunk):
                bm25_top20_gold_rank = rank
                break

        bundle.append({
            "case_id": cid,
            "document_id": doc_id,
            "hypothesis_id": g["hypothesis_id"],
            "gold_label": g["gold_label"],
            "gpt_predicted_label": g["predicted_label"],
            "gpt_evidence": g.get("evidence"),
            "gpt_source_valid_evidence": fr["source_valid_evidence"],
            "gpt_gold_evidence_overlap": fr["gold_evidence_overlap"],
            "classification_correct": g["gold_label"] == g["predicted_label"],
            "final_top5_context": rc["ranked_chunk_text"],
            "final_top5_rerank_scores": rc["ranked_chunk_rerank_scores"],
            "final_top5_bm25_scores": rc["ranked_chunk_bm25_candidate_scores"],
            "gold_span_indices": gold_span_idx,
            "gold_evidence_text": gold_evidence_text,
            "bm25_top20_gold_rank": bm25_top20_gold_rank,  # None = not in top-20 pool at all
            "retrieval_contains_gold_in_final_top5": (
                bool(gold_span_set & {idx for c_off in rc["ranked_chunk_offsets"]
                                       for idx in range(len(doc_spans))
                                       if doc_spans[idx][0] < c_off[1] and doc_spans[idx][1] > c_off[0]})
                if gold_span_set else None
            ),
            "qwen_predicted_label": q["predicted_label"] if q else None,
            "qwen_evidence": q.get("evidence") if q else None,
            "e05_full_context_predicted_label": e05["predicted_label"] if e05 else None,
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"n_residuals": len(bundle), "cases": bundle}, f, indent=2, default=str)
    print(f"wrote {OUT_PATH} ({len(bundle)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
