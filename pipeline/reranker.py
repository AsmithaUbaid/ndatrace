"""
Reranker (Section 6 component 8, "Optional Reranker") - re-scores a wider
set of retrieved candidates with a cross-encoder.

The bi-encoder retriever (pipeline/retriever.py) embeds the query and each
chunk SEPARATELY, then compares vectors - fast enough to search an entire
document, but a cruder relevance signal. A cross-encoder reads the query
and a candidate TOGETHER in one forward pass, which is far more accurate
at fine-grained ranking but too slow to run over every chunk in a
document. Standard pattern: retrieve a wide candidate set with the cheap
retriever, then rerank only that shortlist with the expensive-but-accurate
cross-encoder.
"""

from __future__ import annotations

from functools import lru_cache

from sentence_transformers import CrossEncoder

from pipeline.retriever import RetrievalResult

DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


# See pipeline/embedder.py's _get_model for why this is 8, not 2 - a
# too-small model cache thrashes (evict + reload a full model from disk on
# almost every call) rather than erroring, which looks like a hang.
@lru_cache(maxsize=8)
def _get_reranker(model_name: str) -> CrossEncoder:
    return CrossEncoder(model_name)


def rerank(
    query: str,
    candidates: list[RetrievalResult],
    top_k: int = 5,
    model_name: str | None = None,
) -> list[RetrievalResult]:
    """Re-score `candidates` with a cross-encoder and return the new top_k, best first."""
    if not candidates:
        return []

    model = _get_reranker(model_name or DEFAULT_RERANKER_MODEL)
    pairs = [(query, r.chunk.text) for r in candidates]
    scores = model.predict(pairs)

    reranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    return [RetrievalResult(chunk=r.chunk, score=float(s)) for r, s in reranked[:top_k]]
