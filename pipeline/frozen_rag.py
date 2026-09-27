"""Frozen E20 retrieval runtime used by the interactive product.

This is the production form of E20's already-evaluated ``retrieval_v1``:
clause-aware 256-token chunks, BM25 top-20 candidates, the frozen L-12
cross-encoder, and up to five chunks of model context.  It deliberately
contains no routing, agent, rule boost, dense retrieval, or fallback to the
full document.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.chunker import clause_aware_chunk
from pipeline.reranker import DEFAULT_RERANKER_MODEL, rerank
from pipeline.retriever import RetrievalResult
from pipeline.sparse_retriever import SparseIndex

CHUNK_METHOD = "clause"
CHUNK_SIZE = 256
CHUNK_OVERLAP = 50  # frozen E20 config; clause-aware chunking does not consume overlap
CANDIDATE_POOL_SIZE = 20
TOP_K = 5
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"
CONTEXT_JOIN = "\n\n---\n\n"

assert DEFAULT_RERANKER_MODEL == RERANKER_MODEL


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    rank: int
    start_char: int
    end_char: int
    bm25_score: float
    reranker_score: float
    text: str


class FrozenRagRetriever:
    """Build one BM25 index per NDA and reuse it across requirement queries."""

    def __init__(self, nda_text: str):
        self.chunks = clause_aware_chunk(nda_text, CHUNK_SIZE)
        self._index = SparseIndex(self.chunks)

    def retrieve(self, requirement: str) -> list[RetrievedChunk]:
        hits = self._index.search(requirement, top_k=CANDIDATE_POOL_SIZE)
        bm25_by_chunk = {chunk.chunk_index: float(score) for chunk, score in hits}
        candidates = [RetrievalResult(chunk=chunk, score=float(score)) for chunk, score in hits]
        reranked = rerank(
            requirement,
            candidates,
            top_k=TOP_K,
            model_name=RERANKER_MODEL,
        )
        return [
            RetrievedChunk(
                chunk_id=hit.chunk.chunk_index,
                rank=rank,
                start_char=hit.chunk.start_char,
                end_char=hit.chunk.end_char,
                bm25_score=bm25_by_chunk[hit.chunk.chunk_index],
                reranker_score=float(hit.score),
                text=hit.chunk.text,
            )
            for rank, hit in enumerate(reranked, start=1)
        ]


def join_context(chunks: list[RetrievedChunk]) -> str:
    return CONTEXT_JOIN.join(chunk.text for chunk in chunks)
