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
        self, query_text: str, candidate_pool_size: int = 20, top_k: int = 10
    ) -> list[RetrievalResult]:
        """
        Production retrieval path (CLAUDE.md Decisions Log, T023 round 3):
        retrieve a wide candidate pool cheaply with the bi-encoder, then
        rerank down to top_k with a cross-encoder. Improved recall,
        precision, and MRR simultaneously over plain top-k retrieval in
        the T023 experiments - use this over .query() unless there's a
        specific reason not to pay for the extra reranking pass.
        """
        from pipeline.reranker import rerank  # local import: avoids a retriever<->reranker import cycle

        if not self.chunks:
            return []
        candidates = self.query(query_text, top_k=candidate_pool_size)
        return rerank(query_text, candidates, top_k=top_k)
