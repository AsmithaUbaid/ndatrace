"""
Chunker (WBS T020) - splits a parsed NDA document into retrievable chunks.

Two strategies, per Section 8's D01 experiment (does respecting clause
boundaries beat naive fixed windows?):

- fixed_size_chunk: slides a fixed-size token window with overlap, with no
  awareness of sentence/clause boundaries. Simple, always produces
  uniform-size chunks, but can cut a clause mid-sentence.
- clause_aware_chunk: splits on paragraph/clause boundaries first, merging
  small paragraphs up to the token budget and further splitting any
  paragraph that alone exceeds it. Never a chunk boundary falls mid-sentence
  unless a single sentence itself exceeds the budget.

Chunk character offsets are always tracked (start_char, end_char) so
retrieval results can be checked for overlap with gold evidence spans
(Evidence Recall@K, evaluation/metrics.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")

# Splits on blank lines, or a newline immediately followed by a numbered/
# lettered clause marker (e.g. "1.", "2.1", "(a)") - common NDA structure.
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n|\n(?=\s*(?:\d+[.)]|\(?[a-zA-Z]\)))")
# Sentence boundary: end punctuation followed by whitespace and a capital
# letter or digit - a simple heuristic, good enough for splitting an
# oversized paragraph without pulling in a full NLP sentence tokenizer.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass(frozen=True)
class Chunk:
    """One retrievable piece of a document."""
    text: str
    start_char: int
    end_char: int
    chunk_index: int
    method: str  # "fixed" or "clause"


def _token_count(text: str) -> int:
    return len(ENCODING.encode(text))


def fixed_size_chunk(text: str, chunk_size: int = 512, overlap: int = 50) -> list[Chunk]:
    """Slide a fixed-size token window over the document, with overlap."""
    if not text:
        return []

    tokens = ENCODING.encode(text)
    chunks: list[Chunk] = []
    start = 0
    index = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))

        # Decoding the prefix up to a token boundary reproduces the exact
        # original text (tiktoken encode/decode is lossless), so its length
        # is a reliable character offset - no separate char<->token mapping needed.
        char_start = len(ENCODING.decode(tokens[:start]))
        char_end = len(ENCODING.decode(tokens[:end]))

        chunks.append(Chunk(
            text=text[char_start:char_end],
            start_char=char_start, end_char=char_end,
            chunk_index=index, method="fixed",
        ))
        index += 1

        if end == len(tokens):
            break
        start = end - overlap

    return chunks


def _split_paragraphs(text: str) -> list[tuple[str, int, int]]:
    """Split into (text, start_char, end_char) paragraphs, offsets preserved."""
    paragraphs = []
    pos = 0
    for part in _PARAGRAPH_SPLIT.split(text):
        if not part:
            continue
        idx = text.index(part, pos)
        stripped = part.strip()
        if stripped:
            offset = idx + part.index(stripped)
            paragraphs.append((stripped, offset, offset + len(stripped)))
        pos = idx + len(part)
    return paragraphs


# A clause/sub-clause marker on its own ("1.", "12.", "(a)", "b)") - the
# sentence splitter's punctuation+space+capital heuristic mistakes a
# numbered marker's period for a sentence end, splitting "1." away from
# its own clause text. Any fragment that's ONLY a bare marker gets
# reattached to the sentence that follows it.
_BARE_MARKER = re.compile(r"^\s*(?:\d+[.)]|\(?[a-zA-Z]\))\s*$")


def _split_sentences(text: str, base_offset: int) -> list[tuple[str, int, int]]:
    """Split an oversized paragraph into sentences, offsets relative to the full document."""
    raw: list[tuple[str, int, int]] = []
    pos = 0
    for part in _SENTENCE_SPLIT.split(text):
        if not part:
            continue
        idx = text.index(part, pos)
        raw.append((part, base_offset + idx, base_offset + idx + len(part)))
        pos = idx + len(part)

    sentences: list[tuple[str, int, int]] = []
    i = 0
    while i < len(raw):
        part, start, end = raw[i]
        if _BARE_MARKER.match(part) and i + 1 < len(raw):
            next_part, _, next_end = raw[i + 1]
            sentences.append((f"{part} {next_part}", start, next_end))
            i += 2
        else:
            sentences.append((part, start, end))
            i += 1
    return sentences


def sentence_chunk(text: str) -> list[Chunk]:
    """
    Split into one chunk per sentence/clause fragment, no merging at all -
    maximal granularity. Unlike clause_aware_chunk (which merges small
    units up to a token budget), every unit becomes its own chunk.

    Useful when the retrieval unit needs to closely match a fine-grained
    annotation scheme (ContractNLI's candidate evidence spans are often
    sentence-fragment sized) - a big aggregated chunk necessarily drags in
    many unrelated candidate spans alongside the real evidence, which
    tanks precision regardless of whether the right sentence was found.
    """
    if not text:
        return []

    paragraphs = _split_paragraphs(text)
    chunks: list[Chunk] = []
    index = 0

    for para_text, para_start, para_end in paragraphs:
        sentences = _split_sentences(para_text, para_start)
        units = sentences if sentences else [(para_text, para_start, para_end)]
        for sent_text, sent_start, sent_end in units:
            chunks.append(Chunk(
                text=sent_text, start_char=sent_start, end_char=sent_end,
                chunk_index=index, method="sentence",
            ))
            index += 1

    return chunks


def clause_aware_chunk(text: str, chunk_size: int = 512) -> list[Chunk]:
    """
    Split on paragraph/clause boundaries, merging small ones up to the
    token budget and splitting any paragraph that alone exceeds it.
    """
    if not text:
        return []

    paragraphs = _split_paragraphs(text)

    # Expand any oversized paragraph into sentence-level pieces first.
    units: list[tuple[str, int, int]] = []
    for para_text, para_start, para_end in paragraphs:
        if _token_count(para_text) <= chunk_size:
            units.append((para_text, para_start, para_end))
        else:
            sentences = _split_sentences(para_text, para_start)
            units.extend(sentences if sentences else [(para_text, para_start, para_end)])

    # Merge consecutive small units up to the token budget.
    chunks: list[Chunk] = []
    buffer_text = ""
    buffer_start: int | None = None
    buffer_end: int | None = None
    index = 0

    def flush():
        nonlocal buffer_text, buffer_start, buffer_end, index
        if buffer_text:
            # Use the exact source substring, not the space-joined buffer -
            # buffer_text is only an approximation used for the token-budget
            # check above; the stored chunk must be losslessly sliceable
            # from (start_char, end_char), same guarantee fixed_size_chunk gives.
            chunks.append(Chunk(
                text=text[buffer_start:buffer_end], start_char=buffer_start, end_char=buffer_end,
                chunk_index=index, method="clause",
            ))
            index += 1
        buffer_text, buffer_start, buffer_end = "", None, None

    for unit_text, unit_start, unit_end in units:
        candidate = f"{buffer_text} {unit_text}".strip() if buffer_text else unit_text
        if buffer_text and _token_count(candidate) > chunk_size:
            flush()
            buffer_text, buffer_start, buffer_end = unit_text, unit_start, unit_end
        else:
            buffer_text = candidate
            buffer_start = unit_start if buffer_start is None else buffer_start
            buffer_end = unit_end

    flush()
    return chunks
