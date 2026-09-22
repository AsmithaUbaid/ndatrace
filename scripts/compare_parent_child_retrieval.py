#!/usr/bin/env python3
"""
Parent-child retrieval - indexing-only change, no LLM involved. Rank at
sentence granularity (the level that won round 2's chunking comparison -
best MRR because it lets the retriever discriminate the one relevant
sentence from the rest of a clause), but hand the classifier the larger
*parent* clause each winning sentence belongs to, deduplicating repeats
so the top_k stays at distinct parents, not distinct sentences.

Hypothesis: sentence-level ranking quality (MRR) is kept, while returning
a bigger unit per hit should raise Evidence Recall@K (a parent clause is
more likely to overlap the ContractNLI gold span than a single sentence
is) - the same effect the wide clause-based chunks got in round 1, but
without paying round 1's ranking-quality cost, since ranking still
happens at the fine-grained sentence level.

Compares, on the same 614-case dev set, at the current top_k=7:
  A) baseline: dense (mpnet) retrieve-20 -> rerank (L-12) -> top-7 sentences
  B) parent-child: same ranking, but each ranked sentence is expanded to
     its containing clause (clause_aware_chunk, size=256 - round 1's
     paragraph-ish granularity), deduped, kept until 7 distinct parents
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
from pipeline.chunker import Chunk, clause_aware_chunk
from pipeline.config import settings
from pipeline.parser import parse_contractnli_file
from pipeline.reranker import rerank
from pipeline.retriever import Retriever

CANDIDATE_POOL_SIZE = 20
FINAL_TOP_K = 7
PARENT_CHUNK_SIZE = 256


def find_parent(parents: list[Chunk], child: Chunk) -> Chunk:
    """Parent clause chunk with the largest character overlap with `child`."""
    best_parent, best_overlap = parents[0], -1
    for parent in parents:
        overlap = min(parent.end_char, child.end_char) - max(parent.start_char, child.start_char)
        if overlap > best_overlap:
            best_parent, best_overlap = parent, overlap
    return best_parent


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")

    cases_by_doc = defaultdict(list)
    for doc, ann in dataset.all_cases():
        if ann.label != "NotMentioned" and ann.evidence_spans:
            cases_by_doc[doc.doc_id].append((doc, ann))

    golds: list[GoldCase] = []
    preds_baseline: list[Prediction] = []
    preds_parent_child: list[Prediction] = []

    start = time.time()
    n_done = 0
    for doc_id, cases in cases_by_doc.items():
        doc = cases[0][0]
        retriever = Retriever(doc.text, chunk_method="sentence")
        parent_chunks = clause_aware_chunk(doc.text, chunk_size=PARENT_CHUNK_SIZE)

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

            seen_parents: list[Chunk] = []
            for child in reranked_chunks:
                parent = find_parent(parent_chunks, child)
                if parent not in seen_parents:
                    seen_parents.append(parent)
                if len(seen_parents) >= FINAL_TOP_K:
                    break

            preds_parent_child.append(Prediction(
                doc_id=doc.doc_id, hypothesis_id=ann.hypothesis_id,
                predicted_label=Label(ann.label),
                retrieved_span_indices=map_chunks_to_gold_span_indices(
                    doc.spans, seen_parents),
            ))

            n_done += 1
            if n_done % 100 == 0:
                print(f"  {n_done} cases done, {time.time()-start:.0f}s elapsed", flush=True)

    print(f"\nEvaluated on {len(golds)} cases\n")
    results = []
    for label, preds in [("baseline_rerankL12_top7", preds_baseline),
                          ("parent_child_top7", preds_parent_child)]:
        r = evidence_recall_at_k(preds, golds)
        p = evidence_precision(preds, golds)
        m = mean_reciprocal_rank(preds, golds)
        print(f"{label:<30}  recall={r:.3f}  precision={p:.3f}  mrr={m:.3f}")
        results.append({"label": label, "recall": r, "precision": p, "mrr": m, "n_cases": len(golds)})

    Path("data/parent_child_retrieval.json").write_text(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
