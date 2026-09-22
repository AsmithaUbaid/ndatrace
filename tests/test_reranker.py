"""
Unit tests for pipeline/reranker.py, mocking the cross-encoder (no real
model download/inference needed for these - fast and deterministic).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pipeline.chunker import Chunk
from pipeline.reranker import rerank
from pipeline.retriever import RetrievalResult


def make_result(text: str, score: float) -> RetrievalResult:
    chunk = Chunk(text=text, start_char=0, end_char=len(text), chunk_index=0, method="sentence")
    return RetrievalResult(chunk=chunk, score=score)


def test_rerank_empty_candidates_returns_empty():
    assert rerank("query", []) == []


def test_rerank_reorders_by_cross_encoder_score():
    candidates = [
        make_result("irrelevant sentence", score=0.9),   # highest bi-encoder score
        make_result("the actually relevant sentence", score=0.1),  # lowest bi-encoder score
    ]

    with patch("pipeline.reranker._get_reranker") as mock_get_model:
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.1, 0.9]  # cross-encoder disagrees with bi-encoder
        mock_get_model.return_value = mock_model

        results = rerank("query", candidates, top_k=2)

    assert results[0].chunk.text == "the actually relevant sentence"
    assert results[0].score == 0.9


def test_rerank_respects_top_k():
    candidates = [make_result(f"sentence {i}", score=float(i)) for i in range(10)]

    with patch("pipeline.reranker._get_reranker") as mock_get_model:
        mock_model = MagicMock()
        mock_model.predict.return_value = list(range(10))
        mock_get_model.return_value = mock_model

        results = rerank("query", candidates, top_k=3)

    assert len(results) == 3


def test_rerank_top_k_larger_than_candidates():
    candidates = [make_result("only one", score=1.0)]

    with patch("pipeline.reranker._get_reranker") as mock_get_model:
        mock_model = MagicMock()
        mock_model.predict.return_value = [5.0]
        mock_get_model.return_value = mock_model

        results = rerank("query", candidates, top_k=10)

    assert len(results) == 1
