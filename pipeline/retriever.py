"""
Retriever (WBS T022) - given a document, chunk + embed + index it once,
then answer top-K queries against that index cheaply.

One Retriever is built per document (chunking/embedding/indexing all
happen once in __init__), then .query() is called once per hypothesis -
matches how a real NDA review works: parse the document once, ask it 17
questions.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.chunker import Chunk, clause_aware_chunk, fixed_size_chunk, sentence_chunk
from pipeline.embedder import embed_query, embed_texts
from pipeline.indexer import ChunkIndex, build_index, search
from pipeline.rule_baseline import classify_with_span
from pipeline.sparse_retriever import SparseIndex, reciprocal_rank_fusion


@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float


class Retriever:
    def __init__(
        self,
        doc_text: str,
        chunk_method: str = "clause",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        embedding_model: str | None = None,
    ):
        if chunk_method == "clause":
            self.chunks: list[Chunk] = clause_aware_chunk(doc_text, chunk_size)
        elif chunk_method == "fixed":
            self.chunks = fixed_size_chunk(doc_text, chunk_size, chunk_overlap)
        elif chunk_method == "sentence":
            self.chunks = sentence_chunk(doc_text)
        else:
            raise ValueError(f"Unknown chunk_method: {chunk_method!r} (expected 'clause', 'fixed', or 'sentence')")

        self.doc_text = doc_text
        self.embedding_model = embedding_model
        self.chunk_method = chunk_method
        embeddings = embed_texts([c.text for c in self.chunks], embedding_model)
        self._index: ChunkIndex = build_index(embeddings, self.chunks)

    def query(self, query_text: str, top_k: int = 5) -> list[RetrievalResult]:
        if not self.chunks:
            return []
        query_embedding = embed_query(query_text, self.embedding_model)
        hits = search(self._index, query_embedding, top_k)
        return [RetrievalResult(chunk=chunk, score=score) for chunk, score in hits]

    def query_and_rerank(
        self, query_text: str, candidate_pool_size: int = 20, top_k: int = 7
    ) -> list[RetrievalResult]:
        """
        Dense retrieve-then-rerank (CLAUDE.md Decisions Log, T023 rounds 3-5):
        retrieve a wide candidate pool cheaply with the bi-encoder, then
        rerank down to top_k with a cross-encoder (default: the larger
        ms-marco-MiniLM-L-12-v2, see pipeline/reranker.py). Improved
        recall, precision, and MRR simultaneously over plain top-k
        retrieval. top_k=7: round 5's sweep over k=[3,5,7,10] found MRR is
        nearly flat past k=5 (0.602->0.608 all the way to k=10 - reranking
        already puts real evidence near the top for cases it finds at
        all), while recall keeps climbing with k (74.5%->78.5%->82.8%).
        k=7 buys a real recall gain (+4pt over k=5) without reopening the
        "k=10 is too much context" call - recall never reaches ~90% even
        at k=10, so the remaining miss rate is a retrieval ceiling for
        this method, not a k-tuning problem (see confidence/abstention,
        T026-T027).

        Prefer `query_rerank_and_boost()` over this when a `hypothesis_id`
        is available (round 7 found fusing in the rule-based match is a
        further, real win) - this method stays for cases without a rule
        (e.g. testing embedding/reranker changes in isolation).
        """
        from pipeline.reranker import rerank  # local import: avoids a retriever<->reranker import cycle

        if not self.chunks:
            return []
        candidates = self.query(query_text, top_k=candidate_pool_size)
        return rerank(query_text, candidates, top_k=top_k)

    def query_rerank_and_boost(
        self, hypothesis_id: str, query_text: str, candidate_pool_size: int = 20, top_k: int = 7
    ) -> list[RetrievalResult]:
        """
        Production retrieval path (CLAUDE.md Decisions Log, T023 round 7):
        dense retrieve-then-rerank (see query_and_rerank), then fuse in the
        rule-based keyword match (pipeline/rule_baseline.py) via the same
        Reciprocal Rank Fusion used for BM25+dense, whenever the rule
        fires for this hypothesis_id. Round 7 found this improves recall,
        precision, and MRR simultaneously over rerank-only (recall
        78.5%->80.1%, precision 12.4%->12.6%, MRR 0.605->0.645) - the rule
        is high-precision when it matches (72.6% standalone), so treating
        its match as a rank-1 vote is a real signal, not noise.
        """
        from pipeline.reranker import rerank  # local import: avoids a retriever<->reranker import cycle

        if not self.chunks:
            return []
        candidates = self.query(query_text, top_k=candidate_pool_size)
        reranked = rerank(query_text, candidates, top_k=candidate_pool_size)
        reranked_chunks = [r.chunk for r in reranked]

        _, span = classify_with_span(hypothesis_id, self.doc_text)
        rule_chunk = self._find_rule_chunk(span) if span is not None else None
        if rule_chunk is None:
            return reranked[:top_k]

        fused = reciprocal_rank_fusion(reranked_chunks, [rule_chunk])
        return [RetrievalResult(chunk=chunk, score=score) for chunk, score in fused[:top_k]]

    def _find_rule_chunk(self, span: tuple[int, int]) -> Chunk | None:
        """Chunk with the largest character overlap with the rule's matched span, or None if none overlaps at all."""
        span_start, span_end = span
        best_chunk, best_overlap = None, 0
        for chunk in self.chunks:
            overlap = min(chunk.end_char, span_end) - max(chunk.start_char, span_start)
            if overlap > best_overlap:
                best_chunk, best_overlap = chunk, overlap
        return best_chunk


class HybridRetriever:
    """
    Combines dense (semantic) and sparse (BM25) retrieval via Reciprocal
    Rank Fusion (pipeline/sparse_retriever.py) - a chunk either method
    considers relevant gets credit, rather than betting entirely on one
    strategy's blind spots (BM25 misses paraphrases; dense search is less
    discriminating on exact terms).
    """

    def __init__(
        self,
        doc_text: str,
        chunk_method: str = "sentence",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        embedding_model: str | None = None,
    ):
        self._dense = Retriever(doc_text, chunk_method, chunk_size, chunk_overlap, embedding_model)
        self._sparse = SparseIndex(self._dense.chunks)

    @property
    def chunks(self) -> list[Chunk]:
        return self._dense.chunks

    def query(self, query_text: str, candidate_pool_size: int = 20, top_k: int = 10) -> list[RetrievalResult]:
        if not self.chunks:
            return []
        dense_hits = [r.chunk for r in self._dense.query(query_text, top_k=candidate_pool_size)]
        sparse_hits = [c for c, _ in self._sparse.search(query_text, top_k=candidate_pool_size)]
        fused = reciprocal_rank_fusion(dense_hits, sparse_hits)
        return [RetrievalResult(chunk=chunk, score=score) for chunk, score in fused[:top_k]]

    def query_and_rerank(self, query_text: str, candidate_pool_size: int = 20, top_k: int = 10) -> list[RetrievalResult]:
        """Hybrid retrieval followed by cross-encoder reranking - see Retriever.query_and_rerank."""
        from pipeline.reranker import rerank

        if not self.chunks:
            return []
        candidates = self.query(query_text, candidate_pool_size=candidate_pool_size, top_k=candidate_pool_size)
        return rerank(query_text, candidates, top_k=top_k)
