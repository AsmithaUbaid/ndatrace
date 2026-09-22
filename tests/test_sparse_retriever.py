"""
Unit tests for pipeline/sparse_retriever.py - BM25 is a classical
algorithm, no model download needed, so these run fast and for real
(not mocked).
"""

from __future__ import annotations

from pipeline.chunker import Chunk
from pipeline.sparse_retriever import SparseIndex, reciprocal_rank_fusion


def make_chunk(text: str, i: int = 0) -> Chunk:
    return Chunk(text=text, start_char=0, end_char=len(text), chunk_index=i, method="sentence")


def test_sparse_index_empty_chunks():
    idx = SparseIndex([])
    assert idx.search("query") == []


def test_sparse_index_finds_exact_keyword_match():
    chunks = [
        make_chunk("Receiving Party shall not reverse engineer the software.", 0),
        make_chunk("Receiving Party shall not solicit employees.", 1),
        make_chunk("This agreement is governed by California law.", 2),
    ]
    idx = SparseIndex(chunks)
    results = idx.search("reverse engineer", top_k=3)

    assert results[0][0].chunk_index == 0  # exact term match ranks first


def test_sparse_index_respects_top_k():
    chunks = [make_chunk(f"sentence number {i} about confidentiality", i) for i in range(10)]
    idx = SparseIndex(chunks)
    results = idx.search("confidentiality", top_k=3)
    assert len(results) == 3


def test_reciprocal_rank_fusion_agreement_boosts_score():
    a = make_chunk("chunk A")
    b = make_chunk("chunk B")
    c = make_chunk("chunk C")

    # 'a' ranks first in both lists - should win the fusion decisively.
    list1 = [a, b, c]
    list2 = [a, c, b]

    fused = reciprocal_rank_fusion(list1, list2)
    assert fused[0][0] == a


def test_reciprocal_rank_fusion_rewards_appearing_in_multiple_lists():
    a = make_chunk("chunk A")
    b = make_chunk("chunk B")
    c = make_chunk("chunk C")

    # 'b' ranks 2nd in one list only; 'c' ranks 3rd in both lists.
    list1 = [a, b, c]
    list2 = [a, c]

    fused = dict(reciprocal_rank_fusion(list1, list2))
    assert fused[c] > fused[b]  # appearing in both lists (even at lower rank) beats appearing once


def test_reciprocal_rank_fusion_empty_lists():
    assert reciprocal_rank_fusion([], []) == []


def test_reciprocal_rank_fusion_single_list_preserves_order():
    a, b, c = make_chunk("A"), make_chunk("B"), make_chunk("C")
    fused = reciprocal_rank_fusion([a, b, c])
    assert [chunk for chunk, _ in fused] == [a, b, c]
