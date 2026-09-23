"""
Sparse (BM25) retrieval and hybrid fusion with dense retrieval.

The rule-based-vs-semantic comparison (T023) already showed exact/keyword
matching and semantic search fail in very different ways: keyword matching
(rule-based, and BM25 here) is precise when it hits but misses paraphrased
or synonym-based evidence entirely; dense semantic search catches
paraphrases but is less discriminating overall. Hybrid retrieval fuses
both signals so a chunk that either method considers relevant gets
credit, rather than betting entirely on one strategy's blind spots.

Uses Reciprocal Rank Fusion (RRF) to combine rankings rather than
combining raw scores - BM25 scores and cosine similarities are on
different, incomparable scales, but rank position is always comparable.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from pipeline.chunker import Chunk

RRF_K = 60  # standard constant from the original RRF paper (Cormack et al. 2009)

# Word-boundary tokenizer, not .split() - a plain .lower().split() (code-audit
# finding, 2026-09-24) treats "confidential," and "confidential" as different
# tokens, since trailing punctuation from real NDA prose never gets stripped.
# Legal text is punctuation-heavy (commas, semicolons, parentheticals), so this
# silently fragmented BM25's vocabulary. Fixed here even though hybrid
# BM25+dense retrieval isn't the adopted production path (Decisions Log:
# "no measured benefit over dense+rerank") - it's still real, reachable code
# (scripts/run_full_retrieval_comparison.py exercises it) and shouldn't ship
# with a known correctness bug just because it lost the architecture bake-off.
_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


class SparseIndex:
    """BM25 index over one document's chunks."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._bm25 = BM25Okapi([_tokenize(c.text) for c in chunks]) if chunks else None

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.chunks, scores), key=lambda pair: pair[1], reverse=True)
        return ranked[:top_k]


def reciprocal_rank_fusion(
    *ranked_chunk_lists: list[Chunk],
    k: int = RRF_K,
) -> list[tuple[Chunk, float]]:
    """
    Fuse multiple ranked chunk lists (each already sorted best-first, e.g.
    from dense search and BM25 search separately) into one ranking.

    fused_score(chunk) = sum over each list containing it of 1 / (k + rank)

    A chunk appearing near the top of either list scores highly; a chunk
    both methods agree on scores higher still.
    """
    scores: dict[Chunk, float] = {}
    for ranked_list in ranked_chunk_lists:
        for rank, chunk in enumerate(ranked_list, start=1):
            scores[chunk] = scores.get(chunk, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
