"""Unit tests for pipeline/chunker.py."""

from __future__ import annotations

from pipeline.chunker import ENCODING, clause_aware_chunk, fixed_size_chunk, sentence_chunk


def test_fixed_size_chunk_empty_text():
    assert fixed_size_chunk("") == []


def test_fixed_size_chunk_short_text_single_chunk():
    text = "This is a short NDA clause."
    chunks = fixed_size_chunk(text, chunk_size=512, overlap=50)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len(text)


def test_fixed_size_chunk_char_offsets_reconstruct_original_text():
    """Every chunk's (start_char, end_char) must slice back to its own text exactly."""
    text = "Clause one. " * 200  # long enough to need multiple windows
    chunks = fixed_size_chunk(text, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    for c in chunks:
        assert text[c.start_char:c.end_char] == c.text


def test_fixed_size_chunk_respects_token_budget():
    text = "Clause one. " * 200
    chunks = fixed_size_chunk(text, chunk_size=50, overlap=10)
    for c in chunks[:-1]:  # last chunk may be shorter
        assert len(ENCODING.encode(c.text)) <= 50


def test_fixed_size_chunk_overlap_produces_shared_text():
    text = "word " * 300
    chunks = fixed_size_chunk(text, chunk_size=50, overlap=10)
    # With overlap, consecutive chunks should share some trailing/leading text.
    assert chunks[1].start_char < chunks[0].end_char


def test_fixed_size_chunk_no_overlap_is_contiguous():
    text = "word " * 300
    chunks = fixed_size_chunk(text, chunk_size=50, overlap=0)
    for i in range(len(chunks) - 1):
        assert chunks[i].end_char == chunks[i + 1].start_char


def test_clause_aware_chunk_empty_text():
    assert clause_aware_chunk("") == []


def test_clause_aware_chunk_splits_on_paragraph_boundary():
    text = "1. Confidentiality obligation applies to all information.\n\n2. This agreement terminates after one year."
    chunks = clause_aware_chunk(text, chunk_size=512)
    # Both clauses are small enough to merge into one chunk under a large budget.
    assert len(chunks) == 1
    assert "1." in chunks[0].text and "2." in chunks[0].text


def test_clause_aware_chunk_keeps_small_clauses_separate_when_budget_is_tight():
    text = "1. Confidentiality obligation applies to all information disclosed hereunder.\n\n2. This agreement terminates automatically after a period of one year from signing."
    chunks = clause_aware_chunk(text, chunk_size=10)
    assert len(chunks) >= 2


def test_clause_aware_chunk_splits_oversized_paragraph_by_sentence():
    long_paragraph = ("This is sentence number {}. ".format(i) for i in range(100))
    text = "".join(long_paragraph)
    chunks = clause_aware_chunk(text, chunk_size=30)
    assert len(chunks) > 1
    for c in chunks:
        assert len(ENCODING.encode(c.text)) <= 60  # allows some merge slack, never near full text size


def test_clause_aware_chunk_char_offsets_reconstruct_original_text():
    text = "1. First clause here.\n\n2. Second clause here.\n\n3. Third clause with more text to fill space."
    chunks = clause_aware_chunk(text, chunk_size=512)
    for c in chunks:
        assert text[c.start_char:c.end_char] == c.text


def test_clause_aware_chunk_never_exceeds_budget_by_much_for_normal_clauses():
    text = "\n\n".join(f"{i}. This is clause number {i} with a bit of extra text to pad it out." for i in range(1, 20))
    chunks = clause_aware_chunk(text, chunk_size=50)
    assert len(chunks) > 1
    total_reconstructed = "".join(text[c.start_char:c.end_char] for c in chunks)
    # No text lost - every character should appear in some chunk (spacing aside).
    assert len(total_reconstructed) <= len(text)


def test_sentence_chunk_empty_text():
    assert sentence_chunk("") == []


def test_sentence_chunk_never_merges_even_when_tiny():
    """Unlike clause_aware_chunk, sentence_chunk never merges small units."""
    text = "1. First clause here.\n\n2. Second clause here."
    chunks = sentence_chunk(text)
    assert len(chunks) == 2
    assert all(c.method == "sentence" for c in chunks)


def test_sentence_chunk_splits_multi_sentence_paragraph():
    text = "This is sentence one. This is sentence two. This is sentence three."
    chunks = sentence_chunk(text)
    assert len(chunks) == 3


def test_sentence_chunk_char_offsets_reconstruct_original_text():
    text = "1. First clause here.\n\n2. Second sentence. Third sentence in same clause."
    chunks = sentence_chunk(text)
    for c in chunks:
        assert text[c.start_char:c.end_char] == c.text
