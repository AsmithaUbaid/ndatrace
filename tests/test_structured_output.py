"""Unit tests for evaluation/structured_output.py -- deterministic JSON recovery (E05/E07)."""

from __future__ import annotations

from evaluation.structured_output import parse_structured_output


def test_pure_valid_json():
    r = parse_structured_output('{"label": "Entailment", "evidence": ["exact quote"]}')
    assert r.parse_status == "strict"
    assert r.strict_parse_valid is True
    assert r.recovered_parse_valid is False
    assert r.predicted_label == "Entailment"
    assert r.evidence == ["exact quote"]


def test_valid_json_plus_trailing_commentary():
    raw = ('{"label": "Contradiction"}\n'
           '证据: []\n解释：文本中没有提到。')
    r = parse_structured_output(raw)
    assert r.parse_status == "recovered"
    assert r.strict_parse_valid is False
    assert r.recovered_parse_valid is True
    assert r.predicted_label == "Contradiction"


def test_leading_commentary_plus_valid_json():
    raw = 'Based on the text, here is my answer: {"label": "NotMentioned", "evidence": []}'
    r = parse_structured_output(raw)
    assert r.parse_status == "recovered"
    assert r.predicted_label == "NotMentioned"
    assert r.evidence == []


def test_malformed_json_is_invalid():
    raw = "The label is Entailment, evidence: none provided."
    r = parse_structured_output(raw)
    assert r.parse_status == "invalid"
    assert r.strict_parse_valid is False
    assert r.recovered_parse_valid is False
    assert r.predicted_label is None
    assert r.error_type == "NO_VALID_JSON"


def test_two_conflicting_json_objects_not_recovered():
    """The parser must never arbitrate between multiple candidate objects."""
    raw = '{"label": "Entailment"} but actually reconsidering: {"label": "Contradiction"}'
    r = parse_structured_output(raw)
    assert r.parse_status == "invalid"
    assert r.predicted_label is None
    assert r.error_type == "AMBIGUOUS_OUTPUT"


def test_invalid_label_value_not_recovered():
    raw = '{"label": "Maybe", "evidence": []}'
    r = parse_structured_output(raw)
    assert r.parse_status == "invalid"
    assert r.predicted_label is None


def test_evidence_wrong_type_not_recovered():
    """evidence must be a list of strings -- a bare string or a list of non-strings fails
    schema validation even though the JSON itself is syntactically valid."""
    raw = '{"label": "Entailment", "evidence": "not a list"}'
    r = parse_structured_output(raw)
    assert r.parse_status == "invalid"

    raw2 = '{"label": "Entailment", "evidence": [1, 2, 3]}'
    r2 = parse_structured_output(raw2)
    assert r2.parse_status == "invalid"


def test_missing_evidence_key_defaults_and_is_valid():
    """E03's compact schema has no evidence field at all -- this must still parse as strict-valid."""
    r = parse_structured_output('{"label": "Entailment"}')
    assert r.parse_status == "strict"
    assert r.evidence == []


def test_braces_inside_quoted_evidence_text_do_not_break_balancing():
    raw = ('{"label": "Entailment", "evidence": '
           '["as defined in Exhibit A {Schedule 1} of this Agreement"]}')
    r = parse_structured_output(raw)
    assert r.parse_status == "strict"
    assert r.evidence == ["as defined in Exhibit A {Schedule 1} of this Agreement"]


def test_braces_inside_evidence_text_with_trailing_commentary_recovers_correctly():
    raw = ('{"label": "Contradiction", "evidence": ["see Section 2(a) {defined term}"]}\n'
           'Additional note: this appears to conflict with the requirement.')
    r = parse_structured_output(raw)
    assert r.parse_status == "recovered"
    assert r.evidence == ["see Section 2(a) {defined term}"]


def test_code_fenced_json_is_strict_not_recovered():
    """Markdown fencing is a serialization formality (same tolerance as
    evaluation.oracle.parse_oracle_output), not content recovery -- still counts as strict."""
    raw = '```json\n{"label": "NotMentioned", "evidence": []}\n```'
    r = parse_structured_output(raw)
    assert r.parse_status == "strict"


def test_empty_response_is_invalid():
    r = parse_structured_output("")
    assert r.parse_status == "invalid"
    assert r.error_type == "NO_VALID_JSON"


def test_raw_response_always_preserved_verbatim():
    raw = "garbage output with no json at all"
    r = parse_structured_output(raw)
    assert r.raw_response == raw
