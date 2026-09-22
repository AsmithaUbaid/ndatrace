"""
Unit tests for pipeline/indexer.py - pure numpy logic, no real embedding
model needed.
"""

from __future__ import annotations

import numpy as np

from pipeline.chunker import Chunk
from pipeline.indexer import build_index, search


def make_chunk(i: int, text: str = "text") -> Chunk:
    return Chunk(text=text, start_char=0, end_char=len(text), chunk_index=i, method="fixed")


def test_build_index_empty():
    idx = build_index(np.zeros((0, 0), dtype="float32"), [])
    assert idx.index.ntotal == 0
    assert search(idx, np.zeros(4, dtype="float32"), top_k=5) == []


def test_search_returns_best_match_first():
    chunks = [make_chunk(0, "a"), make_chunk(1, "b"), make_chunk(2, "c")]
    # Orthogonal-ish unit vectors; query closest to chunk 1.
    embeddings = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype="float32")
    idx = build_index(embeddings, chunks)

    query = np.array([0.1, 0.9, 0.0], dtype="float32")
    results = search(idx, query, top_k=3)

    assert len(results) == 3
    assert results[0][0].chunk_index == 1  # closest to the [0,1,0] chunk
    # Scores must be sorted descending.
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


def test_search_respects_top_k():
    chunks = [make_chunk(i) for i in range(10)]
    embeddings = np.random.RandomState(0).rand(10, 8).astype("float32")
    idx = build_index(embeddings, chunks)

    results = search(idx, embeddings[0], top_k=3)
    assert len(results) == 3


def test_search_top_k_larger_than_index_size():
    chunks = [make_chunk(i) for i in range(2)]
    embeddings = np.random.RandomState(0).rand(2, 8).astype("float32")
    idx = build_index(embeddings, chunks)

    results = search(idx, embeddings[0], top_k=10)
    assert len(results) == 2  # capped at actual chunk count, no crash
