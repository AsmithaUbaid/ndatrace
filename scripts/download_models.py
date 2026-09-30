#!/usr/bin/env python3
"""Download the two public Hugging Face models used by NDATrace.

This performs no hosted LLM calls. The files are stored in the normal
Hugging Face cache and are intentionally not committed to the repository.
"""

import sys
from pathlib import Path

from sentence_transformers import CrossEncoder, SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import settings
from pipeline.reranker import DEFAULT_RERANKER_MODEL


def main() -> None:
    print(f"Downloading embedding model: {settings.embedding_model}")
    SentenceTransformer(settings.embedding_model)
    print(f"Downloading reranker: {DEFAULT_RERANKER_MODEL}")
    CrossEncoder(DEFAULT_RERANKER_MODEL)
    print("Model downloads complete.")


if __name__ == "__main__":
    main()
