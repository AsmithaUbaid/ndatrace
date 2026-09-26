"""Unit tests for evaluation/retrieval_eval.py (E06)."""

from __future__ import annotations

from evaluation.retrieval_eval import (
    build_evidence_bearing_train_cases,
    compute_retrieval_metrics,
    context_size_stats,
    retriever_cache_key,
    score_retrieval,
)
from pipeline.chunker import Chunk


def test_evidence_bearing_train_count_is_4371():
    cases = build_evidence_bearing_train_cases()
    assert len(cases) == 4371


def test_evidence_bearing_cases_are_only_entailment_and_contradiction():
    cases = build_evidence_bearing_train_cases()
    labels = {c["gold_label"] for c in cases}
    assert labels == {"Entailment", "Contradiction"}


def test_evidence_bearing_cases_never_have_empty_gold_spans():
    cases = build_evidence_bearing_train_cases()
    assert all(c["gold_span_indices"] for c in cases)


def test_query_text_is_hypothesis_only_no_gold_leakage():
    """The case dict carries gold_label/gold_span_indices for the SCORER, but the
    hypothesis_text field (the actual query) never contains gold information."""
    cases = build_evidence_bearing_train_cases()
    case = cases[0]
    assert case["gold_label"] not in case["hypothesis_text"]


def test_cache_key_changes_with_chunking_or_embedding_not_top_k():
    k1 = retriever_cache_key(1, "clause", 512, 50, "all-mpnet-base-v2", "dense")
    k2 = retriever_cache_key(1, "clause", 512, 50, "all-mpnet-base-v2", "dense")
    k3 = retriever_cache_key(1, "clause", 256, 50, "all-mpnet-base-v2", "dense")
    k4 = retriever_cache_key(1, "clause", 512, 50, "bge-base-en-v1.5", "dense")
    assert k1 == k2  # identical config -> identical key
    assert k1 != k3  # chunk_size changed -> different key
    assert k1 != k4  # embedding model changed -> different key


def test_score_retrieval_hit():
    case = {"document_id": 1, "hypothesis_id": "nda-1", "gold_label": "Entailment",
            "gold_span_indices": [0], "doc_spans": [(0, 10), (20, 30)]}
    chunk = Chunk(text="x", start_char=0, end_char=10, chunk_index=0, method="clause")
    pred, gold = score_retrieval(case, [chunk])
    assert pred.retrieved_span_indices == [0]
    assert gold.gold_span_indices == [0]


def test_compute_retrieval_metrics_splits_by_class():
    case_e = {"document_id": 1, "hypothesis_id": "nda-1", "gold_label": "Entailment",
              "gold_span_indices": [0], "doc_spans": [(0, 10)]}
    case_c = {"document_id": 1, "hypothesis_id": "nda-2", "gold_label": "Contradiction",
              "gold_span_indices": [0], "doc_spans": [(0, 10)]}
    hit = Chunk(text="x", start_char=0, end_char=10, chunk_index=0, method="clause")
    miss = Chunk(text="y", start_char=100, end_char=110, chunk_index=1, method="clause")

    pairs = [score_retrieval(case_e, [hit]), score_retrieval(case_c, [miss])]
    metrics = compute_retrieval_metrics(pairs)
    assert metrics["entailment"]["evidence_recall_at_k"] == 1.0
    assert metrics["contradiction"]["evidence_recall_at_k"] == 0.0
    assert metrics["miss_count"] == 1


def test_context_size_stats_empty_input():
    stats = context_size_stats([])
    assert stats.mean_tokens == 0.0
