#!/usr/bin/env python3
"""
E06 real failure analysis on the selected retrieval config (reconstruction-v2).

For every miss (zero overlap between top-K retrieved chunks and gold spans) at the frozen
retrieval_v1 config, re-queries the SAME cached index with a much larger K (50, effectively
"how far would we have to go to find it at all") to distinguish:
  - RANKING FAILURE: gold evidence chunk exists and is findable, just ranked outside top-5
  - RETRIEVAL ABSENCE: gold evidence chunk never appears even at K=50 (a real miss the
    embedding space itself doesn't support, e.g. severe paraphrase, or a genuine chunk-
    boundary split that fragments the gold span across pieces, no single chunk covering it)

No LLM calls. Reuses the exact same cached index built during R4 (same cache key -- top_k is
not part of the key, so this reuses the build for free).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.retrieval_eval import build_evidence_bearing_train_cases  # noqa: E402
from scripts.run_e06_retrieval import build_or_load_index, query_index  # noqa: E402

CONFIG = dict(method="dense", chunk_method="clause", chunk_size=256, chunk_overlap=50,
              embedding_model="BAAI/bge-base-en-v1.5")
FROZEN_TOP_K = 5
DEEP_K = 50
OUT_CSV = REPO / "experiments/E06_retrieval_optimisation/results/retrieval_failure_analysis.csv"


def classify_failure_family(case: dict, deep_rank: int | None, gold_span_count: int) -> str:
    """A first-pass, data-driven family label -- refined by hand-inspection of the qualitative
    examples in the notebook, not treated as final/authoritative on its own."""
    if deep_rank is None:
        if gold_span_count > 1:
            return "multiple_evidence_spans_not_jointly_retrieved"
        return "retrieval_absence_semantic_or_lexical_mismatch"
    if deep_rank > FROZEN_TOP_K:
        return "ranking_failure_gold_beyond_top_k"
    return "unclassified"


def main():
    cases = build_evidence_bearing_train_cases()
    by_doc: dict[int, list[dict]] = {}
    for c in cases:
        by_doc.setdefault(c["document_id"], []).append(c)

    rows = []
    n_ranking_failure = 0
    n_retrieval_absence = 0
    n_multi_span = 0

    for doc_id, doc_cases in by_doc.items():
        doc_text = doc_cases[0]["doc_text"]
        chunks, index = build_or_load_index(doc_id, doc_text, **CONFIG)

        for case in doc_cases:
            ranked_shallow = query_index(CONFIG["method"], index, chunks, case["hypothesis_text"],
                                          FROZEN_TOP_K, CONFIG["embedding_model"])
            gold_set = set(case["gold_span_indices"])

            def covers(chunk):
                return any(
                    case["doc_spans"][i][0] < chunk.end_char and case["doc_spans"][i][1] > chunk.start_char
                    for i in gold_set
                )

            hit_shallow = any(covers(c) for c in ranked_shallow)
            if hit_shallow:
                continue  # not a miss at the frozen K -- nothing to analyze

            ranked_deep = query_index(CONFIG["method"], index, chunks, case["hypothesis_text"],
                                       DEEP_K, CONFIG["embedding_model"])
            deep_rank = None
            for rank, c in enumerate(ranked_deep, start=1):
                if covers(c):
                    deep_rank = rank
                    break

            family = classify_failure_family(case, deep_rank, len(gold_set))
            if family == "ranking_failure_gold_beyond_top_k":
                n_ranking_failure += 1
            elif family == "multiple_evidence_spans_not_jointly_retrieved":
                n_multi_span += 1
            else:
                n_retrieval_absence += 1

            gold_excerpt = " ".join(
                doc_text[case["doc_spans"][i][0]:case["doc_spans"][i][1]] for i in gold_set
            )[:300]
            top_excerpt = ranked_shallow[0].text[:300] if ranked_shallow else ""

            rows.append({
                "case_id": case["case_id"], "label": case["gold_label"],
                "requirement": case["hypothesis_text"],
                "gold_span_count": len(gold_set),
                "gold_evidence_excerpt": gold_excerpt,
                "top_retrieved_chunk_ids": ",".join(str(c.chunk_index) for c in ranked_shallow),
                "top_retrieved_excerpt": top_excerpt,
                "gold_best_rank": deep_rank if deep_rank is not None else f">{DEEP_K}",
                "failure_family": family,
                "notes": "",
            })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "label", "requirement", "gold_span_count",
                                           "gold_evidence_excerpt", "top_retrieved_chunk_ids",
                                           "top_retrieved_excerpt", "gold_best_rank",
                                           "failure_family", "notes"])
        w.writeheader()
        w.writerows(rows)

    summary = {
        "total_misses_analyzed": len(rows),
        "ranking_failure_gold_beyond_top_k": n_ranking_failure,
        "retrieval_absence_semantic_or_lexical_mismatch": n_retrieval_absence,
        "multiple_evidence_spans_not_jointly_retrieved": n_multi_span,
        "misses_by_label": {
            "Entailment": sum(1 for r in rows if r["label"] == "Entailment"),
            "Contradiction": sum(1 for r in rows if r["label"] == "Contradiction"),
        },
    }
    with open(REPO / "experiments/E06_retrieval_optimisation/results/failure_analysis_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"wrote {OUT_CSV} ({len(rows)} rows)")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
