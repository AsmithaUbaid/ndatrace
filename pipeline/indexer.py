"""
Indexer (WBS T021) - builds and queries a FAISS index over chunk embeddings.

Uses IndexFlatIP (exact inner-product search) rather than an approximate
index: per-document chunk counts here are small (tens, not millions), so
exact search is cheap and avoids the recall loss an approximate index
would introduce. Embeddings are L2-normalised (embedder.py), so inner
product is equivalent to cosine similarity.
"""

from __future__ import annotations

from dataclasses import dataclass

import faiss
import numpy as np

from pipeline.chunker import Chunk


@dataclass
class ChunkIndex:
    """A FAISS index over one document's chunks, plus the chunks themselves."""
    index: faiss.Index
    chunks: list[Chunk]


def build_index(embeddings: np.ndarray, chunks: list[Chunk]) -> ChunkIndex:
    """Build a FAISS index from chunk embeddings. embeddings.shape == (len(chunks), dim)."""
    if embeddings.shape[0] == 0:
        return ChunkIndex(index=faiss.IndexFlatIP(1), chunks=[])

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return ChunkIndex(index=index, chunks=chunks)


def search(chunk_index: ChunkIndex, query_embedding: np.ndarray, top_k: int = 5) -> list[tuple[Chunk, float]]:
    """Return up to top_k (chunk, similarity_score) pairs, best first."""
    if chunk_index.index.ntotal == 0:
        return []

    k = min(top_k, chunk_index.index.ntotal)
    scores, indices = chunk_index.index.search(query_embedding.reshape(1, -1), k)

    results = []
    for idx, score in zip(indices[0], scores[0]):
        if idx == -1:
            continue
        results.append((chunk_index.chunks[idx], float(score)))
    return results
