"""Unit tests for pipeline/confidence.py (WBS T027)."""

from __future__ import annotations

from pipeline.confidence import Route, route


def test_rule_agreement_routes_to_accept():
    decision = route(self_confidence=1.0, rule_agrees=True)
    assert decision.route == Route.ACCEPT


def test_rule_disagreement_routes_to_review():
    decision = route(self_confidence=1.0, rule_agrees=False)
    assert decision.route == Route.REVIEW


def test_high_self_confidence_does_not_override_rule_disagreement():
    """
    T026 found self-confidence is near-random (AUROC 0.554) - a
    confidently-stated wrong answer must still be flagged, not waved
    through just because the model claims certainty.
    """
    decision = route(self_confidence=1.0, rule_agrees=False)
    assert decision.route == Route.REVIEW


def test_low_self_confidence_does_not_force_review_when_rule_agrees():
    """Low self-confidence alone isn't a gating signal here - only rule agreement is."""
    decision = route(self_confidence=0.1, rule_agrees=True)
    assert decision.route == Route.ACCEPT


def test_decision_records_inputs_and_reason():
    decision = route(self_confidence=0.8, rule_agrees=True)
    assert decision.self_confidence == 0.8
    assert decision.rule_agrees is True
    assert decision.reason  # non-empty, human-readable
