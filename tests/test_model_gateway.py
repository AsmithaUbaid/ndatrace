"""
Unit tests for pipeline/model_gateway.py.

All tests mock the OpenAI client's chat.completions.create - no real
network calls, no API cost, per Section 14 Level 2 ("component tests...
mocked model responses for fast tests").
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest

from pipeline.model_gateway import ModelError, ModelGateway, estimate_cost


def fake_request():
    return httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")


def fake_response(status_code: int):
    return httpx.Response(status_code, request=fake_request())


def fake_completion(content="Entailment", tokens_in=100, tokens_out=20):
    """Build a fake object matching the shape of an OpenAI ChatCompletion."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out),
    )


@pytest.fixture
def gateway():
    with patch("pipeline.model_gateway.OpenAI"):
        gw = ModelGateway(model="openai/gpt-5-mini", api_key="sk-test-key", max_retries=2)
        yield gw


def test_missing_api_key_raises_immediately(monkeypatch):
    # api_key="" falls back to settings.openrouter_api_key, which is real in
    # this environment - patch it too so the "no key anywhere" case is genuine.
    monkeypatch.setattr("pipeline.model_gateway.settings.openrouter_api_key", "")
    with pytest.raises(ModelError, match="No OPENROUTER_API_KEY"):
        ModelGateway(api_key="")


def test_complete_success(gateway):
    gateway._client.chat.completions.create = MagicMock(return_value=fake_completion())

    result = gateway.complete("system", "user")

    assert result.content == "Entailment"
    assert result.tokens_in == 100
    assert result.tokens_out == 20
    assert result.num_retries == 0
    assert result.cost_usd == pytest.approx(100 / 1_000_000 * 0.25 + 20 / 1_000_000 * 2.00)


def test_retries_on_rate_limit_then_succeeds(gateway, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)  # skip real backoff delay

    gateway._client.chat.completions.create = MagicMock(
        side_effect=[
            openai.RateLimitError("rate limited", response=fake_response(429), body=None),
            fake_completion(),
        ]
    )

    result = gateway.complete("system", "user")

    assert result.content == "Entailment"
    assert result.num_retries == 1
    assert gateway._client.chat.completions.create.call_count == 2


def test_all_retries_exhausted_raises_model_error(gateway, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    gateway._client.chat.completions.create = MagicMock(
        side_effect=openai.APITimeoutError(request=fake_request())
    )

    with pytest.raises(ModelError, match="All 3 attempts failed"):
        gateway.complete("system", "user")

    assert gateway._client.chat.completions.create.call_count == 3  # max_retries=2 -> 3 total attempts


def test_authentication_error_raises_immediately_no_retry(gateway):
    gateway._client.chat.completions.create = MagicMock(
        side_effect=openai.AuthenticationError("bad key", response=fake_response(401), body=None)
    )

    with pytest.raises(ModelError, match="Authentication failed"):
        gateway.complete("system", "user")

    assert gateway._client.chat.completions.create.call_count == 1  # no retry


def test_bad_request_error_raises_immediately_no_retry(gateway):
    gateway._client.chat.completions.create = MagicMock(
        side_effect=openai.BadRequestError("malformed", response=fake_response(400), body=None)
    )

    with pytest.raises(ModelError, match="Bad request"):
        gateway.complete("system", "user")

    assert gateway._client.chat.completions.create.call_count == 1  # no retry


def test_server_error_retries_then_raises(gateway, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    gateway._client.chat.completions.create = MagicMock(
        side_effect=openai.InternalServerError("server error", response=fake_response(500), body=None)
    )

    with pytest.raises(ModelError):
        gateway.complete("system", "user")

    assert gateway._client.chat.completions.create.call_count == 3


def test_estimate_cost_known_model():
    cost = estimate_cost("openai/gpt-5-mini", tokens_in=1_000_000, tokens_out=1_000_000)
    assert cost == pytest.approx(0.25 + 2.00)


def test_estimate_cost_unknown_model_returns_zero():
    assert estimate_cost("some/unknown-model", tokens_in=1000, tokens_out=1000) == 0.0
