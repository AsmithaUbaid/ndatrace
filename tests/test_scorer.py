"""Unit tests for evaluation/scorer.py."""

from __future__ import annotations

from dataclasses import dataclass

from evaluation.scorer import map_chunks_to_gold_span_indices


@dataclass
class FakeChunk:
    start_char: int
    end_char: int


def test_no_overlap_returns_empty():
    doc_spans = [(0, 10), (20, 30)]
    chunks = [FakeChunk(100, 200)]
    assert map_chunks_to_gold_span_indices(doc_spans, chunks) == []


def test_single_chunk_covers_multiple_spans():
    doc_spans = [(0, 10), (15, 25), (50, 60)]
    chunks = [FakeChunk(0, 30)]  # covers spans 0 and 1, not 2
    assert map_chunks_to_gold_span_indices(doc_spans, chunks) == [0, 1]


def test_order_follows_chunk_rank_not_span_index():
    doc_spans = [(0, 10), (50, 60)]
    # Rank 1 chunk covers span 1 (index 1) but not span 0; rank 2 covers span 0.
    chunks = [FakeChunk(50, 60), FakeChunk(0, 10)]
    assert map_chunks_to_gold_span_indices(doc_spans, chunks) == [1, 0]


def test_span_not_duplicated_if_covered_by_multiple_chunks():
    doc_spans = [(0, 10)]
    chunks = [FakeChunk(0, 20), FakeChunk(5, 15)]  # both overlap the same span
    assert map_chunks_to_gold_span_indices(doc_spans, chunks) == [0]


def test_partial_overlap_counts_as_covered():
    doc_spans = [(5, 15)]
    chunks = [FakeChunk(10, 20)]  # only partially overlaps [5,15), still covered
    assert map_chunks_to_gold_span_indices(doc_spans, chunks) == [0]


def test_adjacent_non_overlapping_not_covered():
    doc_spans = [(0, 10)]
    chunks = [FakeChunk(10, 20)]  # touches but doesn't overlap (end == start)
    assert map_chunks_to_gold_span_indices(doc_spans, chunks) == []


def test_empty_inputs():
    assert map_chunks_to_gold_span_indices([], []) == []
    assert map_chunks_to_gold_span_indices([(0, 10)], []) == []
    assert map_chunks_to_gold_span_indices([], [FakeChunk(0, 10)]) == []
