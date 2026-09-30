"""Unit tests for evaluation/prompt_selection.py (E03)."""

from __future__ import annotations

from evaluation.prompt_selection import build_classification_user_message, load_prompt_config

TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA text: {context_text}"


def test_message_contains_requirement_and_context_not_label():
    case = {"case_id": "c1", "hypothesis_text": "req text", "context_text": "the full NDA text",
            "gold_label": "Contradiction"}
    msg = build_classification_user_message(case, TEMPLATE)
    assert "req text" in msg
    assert "the full NDA text" in msg
    assert "Contradiction" not in msg
    assert "gold_label" not in msg


def test_load_prompt_config_p00():
    cfg = load_prompt_config("p00")
    assert cfg["version"] == "p00"
    assert cfg["model"] == "qwen2.5:7b-instruct"
    assert cfg["temperature"] == 0.0


def test_load_prompt_config_p01_has_label_definitions():
    cfg = load_prompt_config("p01")
    assert "Entailment" in cfg["system_prompt"]
    assert "state or clearly imply" in cfg["system_prompt"]


def test_load_prompt_config_p02_has_decision_procedure():
    cfg = load_prompt_config("p02")
    assert "Follow this procedure" in cfg["system_prompt"]
    assert "Do not infer facts" in cfg["system_prompt"]


def test_prompt_token_overhead_is_monotonically_increasing():
    """P0 < P1 < P2 in system-prompt length, per the recorded cl100k approximations --
    regression guard so a future edit can't silently invert the ladder's ordering."""
    p0 = load_prompt_config("p00")["system_prompt_tokens_cl100k_approx"]
    p1 = load_prompt_config("p01")["system_prompt_tokens_cl100k_approx"]
    p2 = load_prompt_config("p02")["system_prompt_tokens_cl100k_approx"]
    assert p0 < p1 < p2
