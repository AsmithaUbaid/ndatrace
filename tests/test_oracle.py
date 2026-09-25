"""Unit tests for evaluation/oracle.py (E01)."""

from __future__ import annotations

from evaluation.oracle import (
    FORBIDDEN_SUBSTRINGS,
    build_oracle_user_message,
    build_result_record,
    parse_oracle_output,
)


def test_entailment_message_renders_evidence_as_a_json_list():
    case = {"case_id": "c1", "document_id": 1, "hypothesis_id": "nda-1",
            "hypothesis_text": "req text", "gold_label": "Entailment",
            "gold_evidence_text": "the evidence sentence"}
    msg = build_oracle_user_message(case)
    assert "the evidence sentence" in msg
    assert '["the evidence sentence"]' in msg
    assert "Entailment" not in msg
    assert "gold_label" not in msg


def test_not_mentioned_renders_empty_evidence_list_with_no_leaking_phrase():
    """Deterministic regression test for the rendering correction: a NotMentioned case must
    render the SAME evidence field/structure as Entailment/Contradiction -- an empty JSON
    list, `Evidence: []` -- never an explanatory phrase (which would itself be a
    label-revealing shortcut a model could key off instead of reasoning)."""
    case = {"case_id": "c2", "document_id": 2, "hypothesis_id": "nda-2",
            "hypothesis_text": "req text", "gold_label": "NotMentioned",
            "gold_evidence_text": ""}
    msg = build_oracle_user_message(case)
    assert msg.endswith("Evidence: []")
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden.lower() not in msg.lower(), f"leaked forbidden substring: {forbidden!r}"


def test_entailment_and_not_mentioned_messages_use_identical_field_structure():
    """Both must follow the exact same 'Requirement: ...\\n\\nEvidence: [...]' template --
    the only difference should be the JSON list's contents, never a different sentence shape
    that a model could learn to distinguish structurally."""
    ec_case = {"case_id": "c1", "document_id": 1, "hypothesis_id": "nda-1",
               "hypothesis_text": "req text", "gold_label": "Entailment",
               "gold_evidence_text": "some evidence"}
    nm_case = {"case_id": "c2", "document_id": 2, "hypothesis_id": "nda-2",
               "hypothesis_text": "req text", "gold_label": "NotMentioned",
               "gold_evidence_text": ""}
    ec_msg = build_oracle_user_message(ec_case)
    nm_msg = build_oracle_user_message(nm_case)
    assert ec_msg.startswith("Requirement: req text\n\nEvidence: ")
    assert nm_msg.startswith("Requirement: req text\n\nEvidence: ")


def test_no_forbidden_substrings_leak_for_any_label():
    """No model-visible message, for any of the three labels, may contain any forbidden
    substring -- covers the full FORBIDDEN_SUBSTRINGS list, not just the NotMentioned case."""
    for label, evidence_text in [
        ("Entailment", "some evidence text"),
        ("Contradiction", "some other evidence text"),
        ("NotMentioned", ""),
    ]:
        case = {"case_id": "c", "document_id": 1, "hypothesis_id": "nda-1",
                "hypothesis_text": "req text", "gold_label": label,
                "gold_evidence_text": evidence_text}
        msg = build_oracle_user_message(case)
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden.lower() not in msg.lower(), f"{label}: leaked {forbidden!r}"


def test_parse_valid_json():
    result = parse_oracle_output('{"label": "Contradiction"}')
    assert result.parse_valid is True
    assert result.label == "Contradiction"


def test_parse_tolerates_markdown_fence():
    result = parse_oracle_output('```json\n{"label": "NotMentioned"}\n```')
    assert result.parse_valid is True
    assert result.label == "NotMentioned"


def test_parse_rejects_unrecognized_label():
    result = parse_oracle_output('{"label": "Unsure"}')
    assert result.parse_valid is False
    assert result.label is None


def test_parse_rejects_non_json_text():
    result = parse_oracle_output("I think it's Entailment.")
    assert result.parse_valid is False


def test_parse_rejects_json_array():
    result = parse_oracle_output('["Entailment"]')
    assert result.parse_valid is False


def test_build_result_record_shape():
    case = {"case_id": "c1", "document_id": 1, "hypothesis_id": "nda-1", "gold_label": "Entailment"}
    record = build_result_record(
        run_id="run1", experiment_id="E01_oracle", case=case,
        predicted_label="Entailment", parse_valid=True,
        input_tokens=100, output_tokens=5, latency_ms=200.0,
        provider="openrouter", model="test/model", prompt_version="oracle_v1",
        raw_output='{"label": "Entailment"}',
    )
    assert record["case_id"] == "c1"
    assert record["gold_label"] == "Entailment"
    assert record["error"] is None
    # Defaults for a clean success -- no retries, no error classification.
    assert record["retry_count"] == 0
    assert record["error_type"] is None
    assert record["error_message"] is None


def test_build_result_record_carries_retry_and_error_classification():
    case = {"case_id": "c2", "document_id": 2, "hypothesis_id": "nda-2", "gold_label": "Contradiction"}
    record = build_result_record(
        run_id="run1", experiment_id="E01_oracle", case=case,
        predicted_label=None, parse_valid=False,
        input_tokens=None, output_tokens=None, latency_ms=None,
        provider="local", model="test/model", prompt_version="oracle_v1",
        raw_output="", error="timeout after 3 retries",
        retry_count=3, error_type="MODEL_ERROR", error_message="timeout after 3 retries",
    )
    assert record["retry_count"] == 3
    assert record["error_type"] == "MODEL_ERROR"
    assert record["error_message"] == "timeout after 3 retries"
