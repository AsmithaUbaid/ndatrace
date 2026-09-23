"""
Integration tests for the FastAPI backend (WBS T032).

Mocks the OpenAI client the same way tests/test_model_gateway.py does -
no real network calls, no API cost - and uses a temporary SQLite file so
these tests never touch the real ndatrace.db.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


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


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_hypotheses_returns_real_contractnli_labels(client):
    r = client.get("/hypotheses")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 17
    ids = {h["hypothesis_id"] for h in data}
    assert "nda-11" in ids  # "No reverse engineering"


def test_list_experiments_excludes_checkpoints(client):
    r = client.get("/experiments")
    assert r.status_code == 200
    for exp in r.json():
        assert exp["experiment_id"] != "unknown"


def test_cost_estimate_reflects_real_rag_agent_data(client):
    r = client.get("/cost-estimate")
    assert r.status_code == 200
    body = r.json()
    assert body["avg_cost_per_requirement_usd"] > 0
    assert "rag_agent" in body["source_experiment_id"].lower()
    assert body["source_sample_size"] > 0


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
        assert body["results"][0]["agent_used"] is False  # rule agrees -> no escalation
        review_id = body["review_id"]

        r2 = client.get(f"/review/{review_id}")
        assert r2.status_code == 200
        assert r2.json()["results"][0]["label"] == "Entailment"

        r3 = client.get("/results")
        assert r3.status_code == 200
        assert len(r3.json()) == 1
        assert r3.json()[0]["review_id"] == review_id


def test_one_hypothesis_failure_does_not_lose_the_others(client, monkeypatch):
    """Eval case 095 ('1 of 17 fails -> other 16 succeed'): a ModelError
    on one hypothesis must not discard results already computed for the
    others - found as a real gap during the 2026-09-24 security review,
    review_document() originally had no per-hypothesis error isolation
    at all."""
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
        # nda-11's rag classify succeeds, nda-5's rag classify exhausts all
        # 4 attempts (max_retries=3 -> ModelError), nda-16's rag classify
        # succeeds - the mock never even reaches nda-16's plain-context call
        # since nda-5 raises before that, so nda-16 needs its own 2 calls.
        mock_openai.return_value.chat.completions.create = MagicMock(
            side_effect=[
                _fake_completion(ok_json), _fake_completion(ok_json),  # nda-11 boosted + plain
                timeout_error(), timeout_error(), timeout_error(), timeout_error(),  # nda-5 exhausts retries
                _fake_completion(ok_json), _fake_completion(ok_json),  # nda-16 boosted + plain
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


def test_review_escalates_to_agent_on_rule_disagreement(client):
    # Model says Contradiction on a clause the keyword rule reads as
    # Entailment (no "may reverse engineer" carve-out phrase present) ->
    # rule disagrees -> should route to REVIEW and call the agent, which
    # will make its own further model calls against the same mock.
    contradiction_json = json.dumps({
        "label": "Contradiction", "confidence": 0.6,
        "evidence": ["reverse engineer"], "explanation": "test",
    })
    conclude_json = json.dumps({
        "label": "Contradiction", "confidence": 0.6,
        "evidence": ["reverse engineer"], "explanation": "agent test",
    })
    with patch("pipeline.model_gateway.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = MagicMock(
            side_effect=[
                _fake_completion(contradiction_json),  # rule-boosted RAG classify (final-answer candidate)
                _fake_completion(contradiction_json),  # plain (non-boosted) classify (routing-signal only)
                _fake_completion(json.dumps({"action": "conclude", "query": ""})),  # agent step
                _fake_completion(conclude_json),  # agent's final classify-over-everything
            ]
        )
        payload = {
            "nda_text": "Receiving Party shall not reverse engineer any objects embodying "
                        "Confidential Information.",
            "hypothesis_ids": ["nda-11"],
        }
        r = client.post("/review", json=payload)
        assert r.status_code == 200
        assert r.json()["results"][0]["agent_used"] is True
