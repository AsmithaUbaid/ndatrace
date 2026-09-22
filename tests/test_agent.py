"""
Unit tests for pipeline/agent.py (WBS T029). Mocks the model gateway
(pre-scripted decision sequences) and embeddings (no real inference) -
fast, deterministic, no API cost.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from pipeline.agent import run_agent
from pipeline.retriever import Retriever


def fake_embed_texts(texts, model_name=None):
    vocab = ["reverse", "solicit", "destroy", "confidential", "define", "except"]
    vectors = []
    for text in texts:
        vec = np.array([1.0 if word in text.lower() else 0.0 for word in vocab], dtype="float32")
        norm = np.linalg.norm(vec)
        vectors.append(vec / norm if norm > 0 else vec)
    return np.array(vectors, dtype="float32") if vectors else np.zeros((0, len(vocab)), dtype="float32")


def fake_embed_query(query, model_name=None):
    return fake_embed_texts([query])[0]


@pytest.fixture(autouse=True)
def mock_embeddings(monkeypatch):
    monkeypatch.setattr("pipeline.retriever.embed_texts", fake_embed_texts)
    monkeypatch.setattr("pipeline.retriever.embed_query", fake_embed_query)


DOC = (
    '1. "Confidential Information" means any proprietary data disclosed by Disclosing Party.\n\n'
    "2. Receiving Party shall not reverse engineer any Confidential Information.\n\n"
    "3. Receiving Party shall not solicit employees of Disclosing Party."
)


def _mock_response(payload: dict, cost=0.0001, tokens_in=50, tokens_out=20):
    response = MagicMock()
    response.content = json.dumps(payload)
    response.cost_usd = cost
    response.tokens_in = tokens_in
    response.tokens_out = tokens_out
    return response


def test_agent_concludes_immediately_when_confident():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    gateway.complete.return_value = _mock_response({
        "action": "conclude", "query": "", "chunk_index": 0,
        "label": "Entailment", "confidence": 0.9,
        "evidence": ["Receiving Party shall not reverse engineer"], "explanation": "Clear match.",
    })

    result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[], gateway=gateway)

    assert result.label == "Entailment"
    assert result.confidence == 0.9
    assert result.trace.stopped_reason == "concluded"
    assert len(result.trace.steps) == 1
    assert gateway.complete.call_count == 1


def test_agent_calls_a_tool_then_concludes():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    gateway.complete.side_effect = [
        _mock_response({"action": "search_exceptions", "query": "", "chunk_index": 0,
                         "label": "", "confidence": 0.0, "evidence": [], "explanation": ""}),
        _mock_response({"action": "conclude", "query": "", "chunk_index": 0,
                         "label": "NotMentioned", "confidence": 0.7,
                         "evidence": [], "explanation": "No exception found."}),
    ]

    result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[], gateway=gateway)

    assert result.label == "NotMentioned"
    assert len(result.trace.steps) == 2
    assert result.trace.steps[0].action == "search_exceptions"
    assert result.trace.stopped_reason == "concluded"


def test_agent_stops_on_duplicate_tool_call_and_falls_back():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    same_action = {"action": "search_clauses", "query": "reverse engineering", "chunk_index": 0,
                    "label": "", "confidence": 0.0, "evidence": [], "explanation": ""}
    gateway.complete.side_effect = [_mock_response(same_action), _mock_response(same_action)]

    with patch("pipeline.agent.classify") as mock_classify:
        mock_classify.return_value = MagicMock(
            label="Entailment", confidence=0.6, evidence=[], explanation="fallback",
            cost_usd=0.0001, tokens_in=10, tokens_out=10,
        )
        result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[], gateway=gateway)

    assert result.trace.stopped_reason == "duplicate_loop"
    assert result.label == "Entailment"  # from the fallback classify() call
    mock_classify.assert_called_once()


def test_agent_hits_step_limit_and_falls_back():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    # A different query each time, so it never triggers duplicate detection,
    # and never concludes - should run out the step budget.
    gateway.complete.side_effect = [
        _mock_response({"action": "search_clauses", "query": f"query {i}", "chunk_index": 0,
                         "label": "", "confidence": 0.0, "evidence": [], "explanation": ""})
        for i in range(10)
    ]

    with patch("pipeline.agent.classify") as mock_classify:
        mock_classify.return_value = MagicMock(
            label="NotMentioned", confidence=0.5, evidence=[], explanation="fallback",
            cost_usd=0.0001, tokens_in=10, tokens_out=10,
        )
        result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[],
                            gateway=gateway, max_steps=3)

    assert result.trace.stopped_reason == "step_limit"
    assert len(result.trace.steps) == 4  # 3 tool-call steps + 1 fallback_classify step
    assert gateway.complete.call_count == 3


def test_agent_stops_on_invalid_action_and_falls_back():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    gateway.complete.return_value = _mock_response({"action": "not_a_real_tool", "query": ""})

    with patch("pipeline.agent.classify") as mock_classify:
        mock_classify.return_value = MagicMock(
            label="NotMentioned", confidence=0.5, evidence=[], explanation="fallback",
            cost_usd=0.0001, tokens_in=10, tokens_out=10,
        )
        result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[], gateway=gateway)

    assert result.trace.stopped_reason == "invalid_action"
    mock_classify.assert_called_once()


def test_agent_stops_on_unparseable_json_and_falls_back():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    bad_response = MagicMock(content="not valid json{{{", cost_usd=0.0001, tokens_in=10, tokens_out=10)
    gateway.complete.return_value = bad_response

    with patch("pipeline.agent.classify") as mock_classify:
        mock_classify.return_value = MagicMock(
            label="NotMentioned", confidence=0.5, evidence=[], explanation="fallback",
            cost_usd=0.0001, tokens_in=10, tokens_out=10,
        )
        result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[], gateway=gateway)

    assert result.trace.stopped_reason == "invalid_action"


def test_agent_respects_token_limit():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    gateway.complete.side_effect = [
        _mock_response({"action": "search_clauses", "query": f"query {i}", "chunk_index": 0,
                         "label": "", "confidence": 0.0, "evidence": [], "explanation": ""},
                        tokens_in=100, tokens_out=50)
        for i in range(10)
    ]

    with patch("pipeline.agent.classify") as mock_classify:
        mock_classify.return_value = MagicMock(
            label="NotMentioned", confidence=0.5, evidence=[], explanation="fallback",
            cost_usd=0.0001, tokens_in=10, tokens_out=10,
        )
        # Each step costs 150 tokens; the limit is checked at the top of
        # the loop against tokens spent SO FAR, so step 1 (0 < 200) and
        # step 2 (150 < 200) both proceed - the limit trips before step 3
        # (300 > 200), not preemptively before the call that would exceed it.
        result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[],
                            gateway=gateway, max_steps=10, max_tokens=200)

    assert result.trace.stopped_reason == "token_limit"
    assert gateway.complete.call_count == 2


def test_agent_step_records_per_step_latency_cost_and_tokens():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    gateway.complete.side_effect = [
        _mock_response({"action": "search_exceptions", "query": "", "chunk_index": 0,
                         "label": "", "confidence": 0.0, "evidence": [], "explanation": ""},
                        cost=0.0002, tokens_in=100, tokens_out=30),
        _mock_response({"action": "conclude", "query": "", "chunk_index": 0,
                         "label": "NotMentioned", "confidence": 0.7, "evidence": [], "explanation": "ok"},
                        cost=0.0003, tokens_in=150, tokens_out=40),
    ]

    result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[], gateway=gateway)

    assert len(result.trace.steps) == 2
    step1, step2 = result.trace.steps
    assert step1.tokens_in == 100 and step1.tokens_out == 30 and step1.cost_usd == 0.0002
    assert step2.tokens_in == 150 and step2.tokens_out == 40 and step2.cost_usd == 0.0003
    assert step1.latency_ms >= 0 and step2.latency_ms >= 0


def test_agent_logs_a_structured_line_per_step_without_raw_text(caplog):
    import logging
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    gateway.model = "test-model"
    gateway.complete.return_value = _mock_response({
        "action": "conclude", "query": "", "chunk_index": 0,
        "label": "Entailment", "confidence": 0.9,
        "evidence": ["Receiving Party shall not reverse engineer"], "explanation": "Clear match.",
    })

    with caplog.at_level(logging.INFO, logger="ndatrace.agent"):
        run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[],
                  gateway=gateway, doc_id="doc-42")

    agent_records = [r for r in caplog.records if r.name == "ndatrace.agent"]
    assert len(agent_records) == 1
    record = agent_records[0]
    assert record.doc_id == "doc-42"
    assert record.hypothesis_id == "nda-11"
    assert record.stage == "conclude"
    assert record.label == "Entailment"
    assert hasattr(record, "latency_ms") and hasattr(record, "cost_usd")
    # Never log NDA text or chunk content, only identifiers/metrics.
    assert "reverse engineer" not in record.getMessage()
    assert not hasattr(record, "query")
    assert not hasattr(record, "evidence")


def test_agent_records_cost_and_tokens_across_steps():
    retriever = Retriever(DOC, chunk_method="clause", chunk_size=20)
    gateway = MagicMock()
    gateway.complete.side_effect = [
        _mock_response({"action": "search_exceptions", "query": "", "chunk_index": 0,
                         "label": "", "confidence": 0.0, "evidence": [], "explanation": ""},
                        cost=0.0002, tokens_in=100, tokens_out=30),
        _mock_response({"action": "conclude", "query": "", "chunk_index": 0,
                         "label": "NotMentioned", "confidence": 0.7, "evidence": [], "explanation": "ok"},
                        cost=0.0003, tokens_in=150, tokens_out=40),
    ]

    result = run_agent(retriever, "nda-11", "reverse engineering", initial_chunks=[], gateway=gateway)

    assert result.cost_usd == pytest.approx(0.0005)
    assert result.tokens_in == 250
    assert result.tokens_out == 70
