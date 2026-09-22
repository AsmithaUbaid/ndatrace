"""
Agent tools (WBS T028, Section 6 "Agent Tools").

Five tools a selective agent (pipeline/agent.py, T029) can call when a
case is routed to REVIEW (pipeline/confidence.py, T027) - each does one
narrow, well-defined kind of digging beyond the standard retrieve-rerank-
boost pass, targeting failure modes already found in earlier experiments:

- search_clauses: issue a fresh semantic query, not tied to the original
  hypothesis text - lets the agent reformulate when the first pass missed.
- find_defined_term: look up how a specific term is defined elsewhere in
  the document (NDAs commonly define terms like "Confidential
  Information" once, then use them throughout without repeating context).
- search_exceptions: keyword scan (not semantic) for carve-out/exception
  language - T018 found Contradiction cases are frequently established
  via a narrow exception clause that semantic search under-weights.
- retrieve_more_evidence: widen the search beyond chunks already seen,
  for cases where the standard top-7 window missed the real evidence
  (T024's second-largest failure mode).
- inspect_neighbouring_clauses: pull the sentences immediately before/
  after a given chunk - addresses the "does the chunk contain everything
  needed" boundary-spanning-evidence concern raised during T024.

All tools are local/free (retrieval only, no LLM calls) - the agent
router (T029) decides when to call them and when to stop.
"""

from __future__ import annotations

from pipeline.chunker import Chunk
from pipeline.retriever import RetrievalResult, Retriever

# Carve-out/exception markers - matches the proxies used in
# scripts/build_negative_cases.py's "conflicting clauses" category, since
# those are exactly the constructs this tool needs to surface.
EXCEPTION_MARKERS = (
    "except", "notwithstanding", "provided that", "provided, however",
    "unless", "other than", "excluding", "save for",
)

DEFINITION_MARKERS = ("means", "is defined as", "shall mean", "refers to")


def search_clauses(retriever: Retriever, query: str, top_k: int = 5) -> list[RetrievalResult]:
    """Issue a fresh semantic query against the document, independent of the original hypothesis."""
    return retriever.query_and_rerank(query, top_k=top_k)


def find_defined_term(retriever: Retriever, term: str, top_k: int = 3) -> list[RetrievalResult]:
    """Search for where/how `term` is defined in the document."""
    query = f'"{term}" ' + " ".join(DEFINITION_MARKERS)
    return retriever.query_and_rerank(query, top_k=top_k)


def search_exceptions(retriever: Retriever, top_k: int = 5) -> list[Chunk]:
    """
    Keyword scan (not semantic) for carve-out/exception language across
    every chunk in the document. Deterministic and precise where semantic
    search is fuzzy - exception phrasing is fairly fixed in NDAs.
    """
    matches = [
        chunk for chunk in retriever.chunks
        if any(marker in chunk.text.lower() for marker in EXCEPTION_MARKERS)
    ]
    return matches[:top_k]


def retrieve_more_evidence(
    retriever: Retriever, query: str, exclude_chunks: list[Chunk], top_k: int = 5,
) -> list[RetrievalResult]:
    """
    Retrieve additional chunks beyond ones already seen - widens the pool
    and filters out anything in `exclude_chunks`, for cases where the
    standard top-k window missed the real evidence.
    """
    excluded_texts = {c.text for c in exclude_chunks}
    wide_pool = retriever.query_and_rerank(query, candidate_pool_size=40, top_k=top_k + len(excluded_texts))
    fresh = [r for r in wide_pool if r.chunk.text not in excluded_texts]
    return fresh[:top_k]


def inspect_neighbouring_clauses(retriever: Retriever, chunk: Chunk, window: int = 1) -> list[Chunk]:
    """
    Return the `window` chunks immediately before and after `chunk` in
    document order (by chunk_index) - context that a single retrieved
    chunk alone might be missing (e.g. an exception in the next sentence).
    """
    ordered = sorted(retriever.chunks, key=lambda c: c.chunk_index)
    try:
        idx = next(i for i, c in enumerate(ordered) if c.chunk_index == chunk.chunk_index)
    except StopIteration:
        return []
    lo, hi = max(0, idx - window), min(len(ordered), idx + window + 1)
    return [c for c in ordered[lo:hi] if c.chunk_index != chunk.chunk_index]
