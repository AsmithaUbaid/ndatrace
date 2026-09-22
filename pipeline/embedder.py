"""
Embedder (WBS T021) - generates dense embeddings for text chunks using a
local sentence-transformers model. No API calls, no per-embedding cost -
the model runs on-device once downloaded (cached under ~/.cache).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from pipeline.config import settings


@lru_cache(maxsize=2)
def _get_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], model_name: str | None = None) -> np.ndarray:
    """
    Embed a list of texts. Returns an (N, dim) float32 array, L2-normalised
    so inner product == cosine similarity (matches indexer.py's IndexFlatIP).
    """
    if not texts:
        return np.zeros((0, 0), dtype="float32")

    model = _get_model(model_name or settings.embedding_model)
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.astype("float32")


def embed_query(query: str, model_name: str | None = None) -> np.ndarray:
    """Embed a single query string. Returns a (dim,) float32 vector."""
    return embed_texts([query], model_name)[0]
