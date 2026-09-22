"""Unit tests for pipeline/rule_baseline.py."""

from __future__ import annotations

from pipeline.rule_baseline import RULES, classify_by_keywords, classify_with_span


def test_unknown_hypothesis_defaults_to_not_mentioned():
    assert classify_by_keywords("nda-999", "any text at all") == "NotMentioned"


def test_no_keyword_match_defaults_to_not_mentioned():
    assert classify_by_keywords("nda-11", "This document is about widgets.") == "NotMentioned"


def test_positive_keyword_triggers_entailment():
    text = "Receiving Party shall not reverse engineer any object."
    assert classify_by_keywords("nda-11", text) == "Entailment"


def test_negative_keyword_triggers_contradiction():
    text = "Receiving Party may reverse engineer the licensed software."
    assert classify_by_keywords("nda-11", text) == "Contradiction"


def test_negative_takes_priority_over_positive():
    """If both positive and negative phrases appear, negative wins."""
    text = "Recipient shall not solicit representatives, but may solicit vendors."
    assert classify_by_keywords("nda-18", text) == "Contradiction"


def test_case_insensitive_matching():
    text = "RECEIVING PARTY SHALL NOT SOLICIT ANY REPRESENTATIVES."
    assert classify_by_keywords("nda-18", text) == "Entailment"


def test_all_17_hypotheses_have_rules():
    """Every real ContractNLI hypothesis ID used in golden_cases.json must have a rule."""
    expected_ids = {f"nda-{i}" for i in [1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20]}
    assert expected_ids.issubset(RULES.keys())


def test_every_rule_has_at_least_one_positive_phrase():
    for hyp_id, rule in RULES.items():
        assert len(rule.positive) > 0, f"{hyp_id} has no positive keywords"


def test_classify_with_span_no_match_returns_none_span():
    label, span = classify_with_span("nda-11", "This document is about widgets.")
    assert label == "NotMentioned"
    assert span is None


def test_classify_with_span_positive_match_returns_correct_span():
    text = "Some preamble text. Receiving Party shall not reverse engineer the widget."
    label, span = classify_with_span("nda-11", text)
    assert label == "Entailment"
    start, end = span
    assert text.lower()[start:end] == "reverse engineer"


def test_classify_with_span_negative_match_returns_correct_span():
    text = "Recipient may reverse engineer the licensed software freely."
    label, span = classify_with_span("nda-11", text)
    assert label == "Contradiction"
    start, end = span
    assert text.lower()[start:end] == "may reverse engineer"


def test_classify_by_keywords_matches_classify_with_span_label():
    """The thin wrapper must stay behaviorally identical to the span version."""
    text = "Receiving Party shall not solicit any representatives."
    assert classify_by_keywords("nda-18", text) == classify_with_span("nda-18", text)[0]
