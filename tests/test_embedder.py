"""
Unit tests for pipeline/embedder.py (WBS T021 - found missing entirely
during a 2026-09-24 plan-vs-reality audit; embedder was only ever
exercised indirectly through Retriever, never tested in isolation).

Uses the real local sentence-transformers model (no API calls, no cost -
same as every other real-embedding test in this suite, e.g.
test_retriever.py) rather than mocking it, since the whole point is to
verify the actual embedding behavior (normalization, determinism, shape).
"""

from __future__ import annotations

import numpy as np

from pipeline.embedder import _get_model, embed_query, embed_texts


def test_embed_texts_empty_list_returns_empty_array():
    result = embed_texts([])
    assert result.shape == (0, 0)


def test_embed_texts_returns_correct_shape():
    result = embed_texts(["Receiving Party shall not disclose Confidential Information."])
    assert result.shape[0] == 1
    assert result.dtype == np.float32


def test_embed_texts_handles_multiple_texts():
    result = embed_texts(["First clause about confidentiality.", "Second clause about termination."])
    assert result.shape[0] == 2


def test_embed_texts_is_l2_normalized():
    result = embed_texts(["Some NDA clause text for normalization check."])
    norm = np.linalg.norm(result[0])
    assert abs(norm - 1.0) < 1e-5


def test_embed_texts_is_deterministic():
    text = "Receiving Party shall return all Confidential Information upon termination."
    a = embed_texts([text])
    b = embed_texts([text])
    np.testing.assert_array_almost_equal(a, b)


def test_embed_texts_different_texts_produce_different_vectors():
    a = embed_texts(["Confidentiality obligations survive termination."])
    b = embed_texts(["Governing law is the State of Delaware."])
    assert not np.allclose(a[0], b[0])


def test_embed_query_matches_embed_texts_single_row():
    query = "No reverse engineering"
    from_query = embed_query(query)
    from_texts = embed_texts([query])[0]
    np.testing.assert_array_almost_equal(from_query, from_texts)
    assert from_query.ndim == 1


def test_embed_query_is_cached():
    embed_query.cache_clear()
    embed_query("a fixed hypothesis text for cache testing")
    info_after_first = embed_query.cache_info()
    embed_query("a fixed hypothesis text for cache testing")
    info_after_second = embed_query.cache_info()
    assert info_after_second.hits == info_after_first.hits + 1


def test_get_model_caches_model_instances():
    model_a = _get_model("all-mpnet-base-v2")
    model_b = _get_model("all-mpnet-base-v2")
    assert model_a is model_b
