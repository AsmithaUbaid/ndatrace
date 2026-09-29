"""Tests for the batch/history API backed by the frozen product RAG path."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pipeline.frozen_rag import RetrievedChunk


@pytest.fixture(autouse=True)
def _stub_frozen_retriever(monkeypatch):
    class StubRetriever:
        def __init__(self, nda_text: str):
            self.nda_text = nda_text

        def retrieve(self, requirement: str):
            return [RetrievedChunk(
                chunk_id=0, rank=1, start_char=0, end_char=len(self.nda_text),
                bm25_score=1.0, reranker_score=2.0, text=self.nda_text,
            )]

    monkeypatch.setattr("pipeline.final_review.FrozenRagRetriever", StubRetriever)


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_ndatrace.db"
    monkeypatch.setattr("pipeline.config.settings.database_url", f"sqlite:///{db_path}")

    from backend.app import app
    with TestClient(app) as c:
        yield c


def _fake_completion(content: str, tokens_in: int = 100, tokens_out: int = 20):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out),
    )


def test_results_empty_before_any_review(client):
    r = client.get("/results")
    assert r.status_code == 200
    assert r.json() == []


def test_get_missing_review_404s(client):
    r = client.get("/review/does-not-exist")
    assert r.status_code == 404


def test_unknown_hypothesis_id_400s(client):
    r = client.post("/review", json={"nda_text": "some text", "hypothesis_ids": ["nda-999"]})
    assert r.status_code == 400


def test_review_end_to_end_with_mocked_model(client):
    entail_json = json.dumps({
        "label": "Entailment", "confidence": 0.9,
        "evidence": ["shall not reverse engineer"], "explanation": "test",
    })
    with patch("pipeline.model_gateway.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = MagicMock(
            return_value=_fake_completion(entail_json)
        )

        payload = {
            "nda_text": "Receiving Party shall not reverse engineer any objects embodying "
                        "Confidential Information. This Agreement is governed by the laws of Singapore.",
            "hypothesis_ids": ["nda-11"],
        }
        r = client.post("/review", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert len(body["results"]) == 1
        assert body["results"][0]["label"] == "Entailment"
        assert body["results"][0]["agent_used"] is False
        assert body["results"][0]["confidence"] is None
        assert body["results"][0]["confidence_available"] is False
        assert body["results"][0]["source_valid"] is True
        assert body["results"][0]["retrieved_chunks"][0]["rank"] == 1
        review_id = body["review_id"]

        r2 = client.get(f"/review/{review_id}")
        assert r2.status_code == 200
        assert r2.json()["results"][0]["label"] == "Entailment"
        assert r2.json()["results"][0]["sources"][0]["chunk_id"] == 0
        assert r2.json()["results"][0]["retrieved_chunks"][0]["reranker_score"] == 2.0

        r3 = client.get("/results")
        assert r3.status_code == 200
        assert len(r3.json()) == 1
        assert r3.json()[0]["review_id"] == review_id


def test_one_hypothesis_failure_does_not_lose_the_others(client, monkeypatch):
    """A provider failure for one requirement must not discard the others."""
    import httpx
    import openai

    monkeypatch.setattr("time.sleep", lambda s: None)  # skip real retry backoff delay

    ok_json = json.dumps({
        "label": "Entailment", "confidence": 0.9,
        "evidence": ["shall not reverse engineer"], "explanation": "test",
    })

    def timeout_error():
        return openai.APITimeoutError(request=httpx.Request("POST", "https://openrouter.ai/x"))

    with patch("pipeline.model_gateway.OpenAI") as mock_openai:
        # One frozen classifier call per requirement; retry limit is the
        # E20 value of one, so nda-5 exhausts after two attempts.
        mock_openai.return_value.chat.completions.create = MagicMock(
            side_effect=[
                _fake_completion(ok_json),
                timeout_error(), timeout_error(),
                _fake_completion(ok_json),
            ]
        )
        payload = {
            # Keyword-matches all three hypotheses' rule (rule_baseline.py's
            # RULES), so each rag prediction agrees with the rule and stays
            # on the direct-answer path (no agent escalation) - keeps this
            # test about partial-failure isolation, not routing.
            "nda_text": "Receiving Party shall not reverse engineer any Confidential Information. "
                        "Receiving Party may disclose to its employees who need to know. "
                        "Upon termination shall return or destroy all Confidential Information.",
            "hypothesis_ids": ["nda-11", "nda-5", "nda-16"],
        }
        r = client.post("/review", json=payload)
        assert r.status_code == 200  # NOT a total failure
        results = {res["hypothesis_id"]: res for res in r.json()["results"]}
        assert len(results) == 3
        assert results["nda-11"]["error"] is None
        assert results["nda-11"]["label"] == "Entailment"
        assert results["nda-16"]["error"] is None
        assert results["nda-5"]["error"] is not None  # the one that failed is flagged, not silently dropped


def test_pipeline_agent_module_does_not_exist():
    """The legacy 5-tool agent (pipeline/agent.py) was deleted 2026-09-29 - a stronger,
    still-valid version of the old 'patch pipeline.agent.run_agent and assert it's never
    called' regression check, since the module can no longer be imported at all."""
    with pytest.raises(ModuleNotFoundError):
        import pipeline.agent  # noqa: F401


def test_review_never_invokes_agent_or_routing(client):
    contradiction_json = json.dumps({
        "label": "Contradiction", "confidence": 0.6,
        "evidence": ["reverse engineer"], "explanation": "test",
    })
    with patch("pipeline.model_gateway.OpenAI") as mock_openai:
        completion = MagicMock(return_value=_fake_completion(contradiction_json))
        mock_openai.return_value.chat.completions.create = completion
        payload = {
            "nda_text": "Receiving Party shall not reverse engineer any objects embodying "
                        "Confidential Information.",
            "hypothesis_ids": ["nda-11"],
        }
        r = client.post("/review", json=payload)
        assert r.status_code == 200
        assert r.json()["results"][0]["agent_used"] is False
        assert completion.call_count == 1
