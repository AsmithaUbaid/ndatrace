"""Unit tests for pipeline/classifier.py, using a mocked ModelGateway."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from pipeline.classifier import _build_user_message, classify, load_prompt_template
from pipeline.model_gateway import ModelResponse


def fake_gateway(*responses: ModelResponse) -> MagicMock:
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=list(responses))
    return gw


def make_response(content: str, tokens_in=200, tokens_out=50) -> ModelResponse:
    return ModelResponse(
        content=content, model="openai/gpt-5-mini",
        tokens_in=tokens_in, tokens_out=tokens_out,
        cost_usd=0.0001, latency_ms=500.0,
    )


def test_load_prompt_template_v1_exists():
    template = load_prompt_template("v1")
    assert "Entailment" in template
    assert "Contradiction" in template
    assert "NotMentioned" in template


def test_build_user_message_survives_curly_braces_in_nda_text():
    """
    Real NDA text can contain literal { } (defined-term lists, cross-refs).
    The system prompt template must never be str.format()-ed with raw NDA
    text as a slot value - this proves the user message is built by plain
    concatenation, not templating.
    """
    tricky_text = 'Confidential Information means {data, code, designs} as defined in Section 2.'
    message = _build_user_message(tricky_text, "Some requirement")
    assert tricky_text in message


def test_classify_valid_json_first_try():
    response_json = json.dumps({
        "label": "Entailment", "confidence": 0.9,
        "evidence": ["Receiving Party shall keep this confidential."],
        "explanation": "The clause directly states the obligation.",
    })
    gw = fake_gateway(make_response(response_json))

    result = classify("NDA text here", "Some requirement", gw)

    assert result.label == "Entailment"
    assert result.confidence == 0.9
    assert result.valid_json is True
    assert gw.complete.call_count == 1


def test_classify_invalid_json_then_retry_succeeds():
    bad = make_response("not valid json at all")
    good = make_response(json.dumps({
        "label": "NotMentioned", "confidence": 0.7, "evidence": [], "explanation": "Absent.",
    }))
    gw = fake_gateway(bad, good)

    result = classify("NDA text", "requirement", gw)

    assert result.label == "NotMentioned"
    assert result.valid_json is True
    assert gw.complete.call_count == 2


def test_classify_invalid_json_both_attempts_falls_back_safely():
    gw = fake_gateway(make_response("garbage"), make_response("still garbage"))

    result = classify("NDA text", "requirement", gw)

    assert result.label == "NotMentioned"  # safe default, never Entailment/Contradiction
    assert result.valid_json is False
    assert gw.complete.call_count == 2


def test_classify_invalid_label_falls_back_safely():
    response_json = json.dumps({
        "label": "MaybeSortOf", "confidence": 0.5, "evidence": [], "explanation": "?",
    })
    gw = fake_gateway(make_response(response_json))

    result = classify("NDA text", "requirement", gw)

    assert result.label == "NotMentioned"
    assert result.valid_json is False


def test_classify_missing_optional_fields_use_defaults():
    response_json = json.dumps({"label": "Contradiction"})
    gw = fake_gateway(make_response(response_json))

    result = classify("NDA text", "requirement", gw)

    assert result.label == "Contradiction"
    assert result.confidence == 0.5
    assert result.evidence == []
    assert result.explanation == ""
