"""Offline tests for the frozen E20 product runtime. No provider calls."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from pipeline.chunker import Chunk
from pipeline.final_review import review_final
from pipeline.frozen_rag import (
    CANDIDATE_POOL_SIZE,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    RERANKER_MODEL,
    TOP_K,
    FrozenRagRetriever,
    RetrievedChunk,
)
from pipeline.model_gateway import ModelResponse
from pipeline.retriever import RetrievalResult


def test_frozen_retrieval_is_bm25_top20_reranked_to_top5():
    chunks = [
        Chunk(
            text=f"confidential information clause {i}",
            start_char=i * 40,
            end_char=i * 40 + 35,
            chunk_index=i,
            method="clause",
        )
        for i in range(25)
    ]

    def fake_rerank(query, candidates, top_k, model_name):
        assert len(candidates) == CANDIDATE_POOL_SIZE == 20
        assert top_k == TOP_K == 5
        assert model_name == RERANKER_MODEL == "cross-encoder/ms-marco-MiniLM-L-12-v2"
        return [RetrievalResult(chunk=item.chunk, score=float(100 - i)) for i, item in enumerate(candidates[:5])]

    with patch("pipeline.frozen_rag.clause_aware_chunk", return_value=chunks) as chunker, patch(
        "pipeline.frozen_rag.rerank", side_effect=fake_rerank
    ):
        retrieved = FrozenRagRetriever("document").retrieve("confidential information")

    chunker.assert_called_once_with("document", CHUNK_SIZE)
    assert CHUNK_SIZE == 256
    assert CHUNK_OVERLAP == 50
    assert len(retrieved) == 5
    assert [item.rank for item in retrieved] == [1, 2, 3, 4, 5]


def test_classifier_receives_only_retrieved_top5_not_full_document():
    full_only_sentinel = "FULL_ONLY_SECRET_SENTINEL"
    nda_text = f"introductory text {full_only_sentinel}"
    chunks = [
        RetrievedChunk(
            chunk_id=i,
            rank=i + 1,
            start_char=i * 10,
            end_char=i * 10 + len(f"retrieved clause {i}"),
            bm25_score=1.0,
            reranker_score=5.0 - i,
            text=f"retrieved clause {i}",
        )
        for i in range(5)
    ]
    retriever = MagicMock()
    retriever.retrieve.return_value = chunks
    gateway = MagicMock()
    gateway.complete.return_value = ModelResponse(
        content=json.dumps({"label": "NotMentioned", "evidence": []}),
        model="openai/gpt-5-mini",
        tokens_in=20,
        tokens_out=5,
        cost_usd=0.001,
        latency_ms=10.0,
    )

    result = review_final(nda_text, "requirement", gateway=gateway, retriever=retriever)

    prompt = gateway.complete.call_args.kwargs["user_prompt"]
    assert full_only_sentinel not in prompt
    assert all(chunk.text in prompt for chunk in chunks)
    assert len(result.retrieved_chunks) == TOP_K


def test_retrieval_failure_requires_review_and_never_calls_classifier():
    retriever = MagicMock()
    retriever.retrieve.side_effect = RuntimeError("reranker unavailable")
    gateway = MagicMock()

    result = review_final("nda", "requirement", gateway=gateway, retriever=retriever)

    assert result.label is None
    assert result.needs_human_review is True
    assert result.error == "retrieval_error: RuntimeError"
    gateway.complete.assert_not_called()
