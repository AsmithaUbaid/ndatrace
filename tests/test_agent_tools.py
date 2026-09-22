"""
Unit tests for pipeline/agent_tools.py (WBS T028), mocking the embedding
calls (no real model download/inference needed - fast and deterministic).
"""

from __future__ import annotations

import numpy as np
import pytest

from pipeline.agent_tools import (
    find_defined_term,
    inspect_neighbouring_clauses,
    retrieve_more_evidence,
    search_clauses,
    search_exceptions,
)
from pipeline.retriever import Retriever


def fake_embed_texts(texts, model_name=None):
    vocab = ["reverse", "solicit", "destroy", "confidential", "define", "except", "notwithstanding"]
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


DOC = (
    '1. "Confidential Information" means any proprietary data disclosed by Disclosing Party.\n\n'
    "2. Receiving Party shall not reverse engineer any Confidential Information.\n\n"
    "3. Receiving Party shall not solicit employees of Disclosing Party.\n\n"
    "4. Receiving Party shall destroy all Confidential Information upon termination, "
    "except as required by law.\n\n"
    "5. This clause is entirely unrelated to confidentiality obligations."
)


def test_search_clauses_returns_relevant_chunk_first():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    results = search_clauses(retriever, "reverse engineering", top_k=3)
    assert "reverse" in results[0].chunk.text.lower()


def test_find_defined_term_locates_the_definition_clause():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    results = find_defined_term(retriever, "Confidential Information", top_k=3)
    assert any("means" in r.chunk.text.lower() for r in results)


def test_search_exceptions_finds_the_carveout_clause():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    matches = search_exceptions(retriever)
    assert any("except as required by law" in c.text.lower() for c in matches)


def test_search_exceptions_returns_no_matches_when_none_exist():
    doc = "1. A simple clause.\n\n2. Another simple clause with no carve-outs."
    retriever = Retriever(doc, chunk_method="clause", chunk_size=20)
    assert search_exceptions(retriever) == []


def test_retrieve_more_evidence_excludes_already_seen_chunks():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    already_seen = retriever.query("confidential", top_k=2)
    seen_chunks = [r.chunk for r in already_seen]

    more = retrieve_more_evidence(retriever, "confidential", exclude_chunks=seen_chunks, top_k=2)
    returned_texts = {r.chunk.text for r in more}
    seen_texts = {c.text for c in seen_chunks}
    assert returned_texts.isdisjoint(seen_texts)


def test_retrieve_more_evidence_empty_document():
    retriever = Retriever("", chunk_method="sentence")
    assert retrieve_more_evidence(retriever, "anything", exclude_chunks=[]) == []


def test_inspect_neighbouring_clauses_returns_adjacent_chunks():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    middle_chunk = retriever.chunks[2]  # the solicitation clause
    neighbours = inspect_neighbouring_clauses(retriever, middle_chunk, window=1)
    neighbour_indices = {c.chunk_index for c in neighbours}
    assert neighbour_indices == {retriever.chunks[1].chunk_index, retriever.chunks[3].chunk_index}


def test_inspect_neighbouring_clauses_at_document_start_has_no_left_neighbour():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    first_chunk = retriever.chunks[0]
    neighbours = inspect_neighbouring_clauses(retriever, first_chunk, window=1)
    assert first_chunk.chunk_index not in {c.chunk_index for c in neighbours}
    assert len(neighbours) == 1  # only the next chunk, nothing before the start


def test_inspect_neighbouring_clauses_at_document_end_has_no_right_neighbour():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    last_chunk = retriever.chunks[-1]
    neighbours = inspect_neighbouring_clauses(retriever, last_chunk, window=1)
    assert len(neighbours) == 1  # only the previous chunk, nothing after the end
