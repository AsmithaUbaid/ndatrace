"""
Unit tests for pipeline/retriever.py, mocking the embedding calls (no real
model download/inference needed for these - fast and deterministic).
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from pipeline.retriever import Retriever


def fake_embed_texts(texts, model_name=None):
    """
    Deterministic fake embeddings: each vector's direction encodes which
    word from a small vocabulary the text contains, so similarity search
    behaves predictably in tests without a real model.
    """
    vocab = ["reverse", "solicit", "destroy", "confidential"]
    vectors = []
    for text in texts:
        vec = np.array([1.0 if word in text.lower() else 0.0 for word in vocab], dtype="float32")
        norm = np.linalg.norm(vec)
        vectors.append(vec / norm if norm > 0 else vec)
    return np.array(vectors, dtype="float32") if vectors else np.zeros((0, len(vocab)), dtype="float32")


def fake_embed_query(query, model_name=None):
    return fake_embed_texts([query])[0]


@pytest.fixture(autouse=True)
def mock_embeddings(monkeypatch):
    monkeypatch.setattr("pipeline.retriever.embed_texts", fake_embed_texts)
    monkeypatch.setattr("pipeline.retriever.embed_query", fake_embed_query)


def test_retriever_returns_most_relevant_chunk_first():
    # Each clause is ~13-14 tokens; chunk_size=15 forces them to stay
    # separate rather than merging into one chunk (chunk_aware_chunk merges
    # small consecutive units up to the budget).
    doc = (
        "1. Receiving Party shall not reverse engineer any Confidential Information.\n\n"
        "2. Receiving Party shall not solicit employees of Disclosing Party.\n\n"
        "3. Receiving Party shall destroy all Confidential Information upon termination."
    )
    retriever = Retriever(doc, chunk_method="clause", chunk_size=15)
    assert len(retriever.chunks) == 3  # sanity check: clauses actually stayed separate
    results = retriever.query("reverse engineering", top_k=3)

    assert len(results) == 3
    assert "reverse" in results[0].chunk.text.lower()


def test_retriever_top_k_limits_results():
    doc = "1. Clause about reverse engineering.\n\n2. Clause about solicitation.\n\n3. Clause about destruction."
    retriever = Retriever(doc, chunk_method="clause", chunk_size=15)
    results = retriever.query("reverse", top_k=1)
    assert len(results) == 1


def test_retriever_fixed_chunking_mode():
    doc = "word " * 200
    retriever = Retriever(doc, chunk_method="fixed", chunk_size=50, chunk_overlap=10)
    assert len(retriever.chunks) > 1
    assert all(c.method == "fixed" for c in retriever.chunks)


def test_retriever_invalid_chunk_method_raises():
    with pytest.raises(ValueError, match="Unknown chunk_method"):
        Retriever("some text", chunk_method="bogus")


def test_retriever_empty_document_returns_no_results():
    retriever = Retriever("", chunk_method="clause")
    assert retriever.chunks == []
    assert retriever.query("anything") == []


def test_query_and_rerank_empty_document_returns_no_results():
    retriever = Retriever("", chunk_method="sentence")
    assert retriever.query_and_rerank("anything") == []


def test_query_and_rerank_calls_rerank_with_wide_candidate_pool():
    doc = "1. Reverse engineering clause.\n\n2. Solicitation clause.\n\n3. Destruction clause."
    retriever = Retriever(doc, chunk_method="clause", chunk_size=15)

    with patch("pipeline.reranker.rerank") as mock_rerank:
        mock_rerank.return_value = "reranked result"
        result = retriever.query_and_rerank("reverse", candidate_pool_size=2, top_k=1)

    assert result == "reranked result"
    call_args = mock_rerank.call_args
    assert call_args.args[0] == "reverse"
    assert len(call_args.args[1]) == 2  # candidate_pool_size was respected
    assert call_args.kwargs["top_k"] == 1
