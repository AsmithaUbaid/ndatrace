#!/usr/bin/env python3
"""
Does fusing the rule-based keyword match (pipeline/rule_baseline.py) into
the winning semantic retrieval pipeline help - "combine rule-based +
semantic" as the obvious next lever after round 6 confirmed pool_size=20?

Rule-based alone is high-precision, low-recall (72.6% precision, 20.4%
recall, MRR 0.726 when it matches at all - see docs/experiments.md's
un-numbered rule-vs-semantic row). The idea: when the keyword rule fires,
it's very likely right - so treat its matched span as a rank-1 vote and
fuse it with the dense+rerank ranking via the same Reciprocal Rank Fusion
already used for BM25+dense (pipeline/sparse_retriever.py), rather than
trusting semantic search alone.

Compares, on the same 614-case dev set, at the current default top_k=7:
  A) baseline: dense (mpnet) retrieve-20 -> rerank (L-12) -> top-7
  B) rule-boosted: same, but if the keyword rule fires for this
     hypothesis, fuse its matched chunk in via RRF before truncating
     to top-7 (the rule's chunk gets an RRF vote at rank 1, exactly
     like a second retrieval method would)
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
from pipeline.chunker import Chunk
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.reranker import rerank
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_with_span
from pipeline.sparse_retriever import reciprocal_rank_fusion

CANDIDATE_POOL_SIZE = 20
FINAL_TOP_K = 7


def find_matching_chunk(chunks: list[Chunk], span: tuple[int, int]) -> Chunk | None:
    """Chunk with the largest character overlap with the rule's matched span."""
    span_start, span_end = span
    best_chunk, best_overlap = None, 0
    for chunk in chunks:
        overlap = min(chunk.end_char, span_end) - max(chunk.start_char, span_start)
        if overlap > best_overlap:
            best_chunk, best_overlap = chunk, overlap
    return best_chunk


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    golds: list[GoldCase] = []
    preds_baseline: list[Prediction] = []
    preds_boosted: list[Prediction] = []
    n_rule_fired = 0

    start = time.time()
    n_done = 0
    for doc_id, cases in cases_by_doc.items():
        doc = cases[0][0]
        retriever = Retriever(doc.text, chunk_method="sentence")

        for _, ann in cases:
            golds.append(GoldCase(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                gold_label=Label(ann.label),
                gold_span_indices=[s.span_index for s in ann.evidence_spans],
            ))

            candidates = retriever.query(ann.hypothesis_text, top_k=CANDIDATE_POOL_SIZE)
            reranked = rerank(ann.hypothesis_text, candidates, top_k=CANDIDATE_POOL_SIZE,
                               model_name="cross-encoder/ms-marco-MiniLM-L-12-v2")
            reranked_chunks = [r.chunk for r in reranked]

            preds_baseline.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(
                    doc.spans, reranked_chunks[:FINAL_TOP_K]),
            ))

            _, span = classify_with_span(ann.hypothesis_id, doc.text)
            if span is not None:
                rule_chunk = find_matching_chunk(retriever.chunks, span)
            else:
                rule_chunk = None

            if rule_chunk is not None:
                n_rule_fired += 1
                fused = reciprocal_rank_fusion(reranked_chunks, [rule_chunk])
                boosted_chunks = [c for c, _ in fused[:FINAL_TOP_K]]
            else:
                boosted_chunks = reranked_chunks[:FINAL_TOP_K]

            preds_boosted.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(
                    doc.spans, boosted_chunks),
            ))

            n_done += 1
            if n_done % 100 == 0:
                print(f"  {n_done} cases done, {time.time()-start:.0f}s elapsed", flush=True)

    print(f"\nEvaluated on {len(golds)} cases; rule fired on {n_rule_fired} of them\n")
    results = []
    for label, preds in [("baseline_rerankL12_top7", preds_baseline),
                          ("rule_boosted_rerankL12_top7", preds_boosted)]:
        r = evidence_recall_at_k(preds, golds)
        p = evidence_precision(preds, golds)
        m = mean_reciprocal_rank(preds, golds)
        print(f"{label:<30}  recall={r:.3f}  precision={p:.3f}  mrr={m:.3f}")
        results.append({"label": label, "recall": r, "precision": p, "mrr": m,
                         "n_rule_fired": n_rule_fired, "n_cases": len(golds)})

    Path("data/rule_boosted_retrieval.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
