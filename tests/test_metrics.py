"""
Unit tests for evaluation/metrics.py — WBS T007, experiment A08.

All tests use hand-crafted synthetic data with known correct answers,
per Section 14 ("Metric unit tests... pass on synthetic data (hand-crafted
examples with known correct results)").
"""

from __future__ import annotations

import pytest

from evaluation.metrics import (
    abstention_effectiveness,
    abstention_rate,
    agent_recovery_rate,
    agent_regression_rate,
    agent_routing_rate,
    compute_all_metrics,
    contradiction_recall_with_ci,
    coverage,
    cost_and_latency_summary,
    evidence_precision,
    evidence_recall_at_k,
    joint_label_evidence_correctness,
    label_accuracy,
    macro_f1,
    mcnemar_test,
    mean_reciprocal_rank,
    per_class_metrics,
    risk_sensitive_recall,
    selective_accuracy,
    unsafe_non_abstention_rate,
    wilson_score_interval,
)
from evaluation.schemas import CostLatencyRecord, GoldCase, Label, Prediction


def gold(doc_id, hyp_id, label, spans=None):
    return GoldCase(
        doc_id=doc_id, hypothesis_id=hyp_id, gold_label=Label(label),
        gold_span_indices=spans or [],
    )


def pred(doc_id, hyp_id, label, spans=None, abstained=False, agent_used=False,
         cost_usd=0.0, latency_ms=0.0):
    return Prediction(
        doc_id=doc_id, hypothesis_id=hyp_id, predicted_label=Label(label),
        retrieved_span_indices=spans or [], abstained=abstained,
        agent_used=agent_used,
        cost_latency=CostLatencyRecord(latency_ms=latency_ms, cost_usd=cost_usd),
    )


# A balanced 6-case gold set: 2 Entailment, 2 Contradiction, 2 NotMentioned.
BALANCED_GOLDS = [
    gold("d1", "h1", "Entailment", [0, 1]),
    gold("d1", "h2", "Contradiction", [2]),
    gold("d1", "h3", "NotMentioned"),
    gold("d2", "h1", "Entailment", [5]),
    gold("d2", "h2", "Contradiction", [6, 7]),
    gold("d2", "h3", "NotMentioned"),
]


# =========================================================================
# Classification metrics
# =========================================================================

def test_label_accuracy_all_correct():
    preds = [pred(g.doc_id, g.hypothesis_id, g.gold_label.value, g.gold_span_indices)
             for g in BALANCED_GOLDS]
    assert label_accuracy(preds, BALANCED_GOLDS) == 1.0


def test_label_accuracy_partial():
    preds = [pred(g.doc_id, g.hypothesis_id, g.gold_label.value) for g in BALANCED_GOLDS]
    # Flip one prediction to wrong.
    preds[0] = pred("d1", "h1", "NotMentioned")
    assert label_accuracy(preds, BALANCED_GOLDS) == pytest.approx(5 / 6)


def test_label_accuracy_excludes_abstained():
    preds = [pred(g.doc_id, g.hypothesis_id, g.gold_label.value) for g in BALANCED_GOLDS]
    preds[0] = pred("d1", "h1", "Entailment", abstained=True)
    # 5 non-abstained cases, all correct.
    assert label_accuracy(preds, BALANCED_GOLDS) == 1.0


def test_macro_f1_balanced():
    """Perfect predictions across three balanced classes -> macro-F1 = 1.0."""
    preds = [pred(g.doc_id, g.hypothesis_id, g.gold_label.value, g.gold_span_indices)
             for g in BALANCED_GOLDS]
    assert macro_f1(preds, BALANCED_GOLDS) == pytest.approx(1.0)


def test_macro_f1_treats_classes_equally_under_imbalance():
    """
    Macro-F1 must not equal accuracy when errors are concentrated in the
    minority class -- this is the whole point of using macro- over
    micro-averaging (Section 11: "treats all three classes equally
    regardless of frequency").
    """
    golds = [gold("d", f"h{i}", "Entailment") for i in range(8)] + [
        gold("d", "h8", "Contradiction"),
        gold("d", "h9", "NotMentioned"),
    ]
    # All 8 Entailment correct; both minority classes wrong.
    preds = [pred("d", f"h{i}", "Entailment") for i in range(8)] + [
        pred("d", "h8", "Entailment"),
        pred("d", "h9", "Entailment"),
    ]
    acc = label_accuracy(preds, golds)
    mf1 = macro_f1(preds, golds)
    assert acc == pytest.approx(0.8)
    assert mf1 < acc  # macro-F1 punishes the two failed minority classes much harder


def test_per_class_metrics_precision_recall():
    golds = [
        gold("d", "h1", "Entailment"),
        gold("d", "h2", "Entailment"),
        gold("d", "h3", "Contradiction"),
    ]
    preds = [
        pred("d", "h1", "Entailment"),
        pred("d", "h2", "Contradiction"),  # false negative for Entailment, false positive for Contradiction
        pred("d", "h3", "Contradiction"),
    ]
    pc = per_class_metrics(preds, golds)
    assert pc["Entailment"]["precision"] == pytest.approx(1.0)  # 1 TP, 0 FP
    assert pc["Entailment"]["recall"] == pytest.approx(0.5)  # 1 TP, 1 FN
    assert pc["Contradiction"]["precision"] == pytest.approx(0.5)  # 1 TP, 1 FP
    assert pc["Contradiction"]["recall"] == pytest.approx(1.0)  # 1 TP, 0 FN


def test_risk_sensitive_recall():
    """Average of Contradiction recall and NotMentioned recall only."""
    golds = [
        gold("d", "h1", "Entailment"),
        gold("d", "h2", "Contradiction"),
        gold("d", "h3", "NotMentioned"),
    ]
    # Entailment wrong (irrelevant to this metric), Contradiction and NotMentioned correct.
    preds = [
        pred("d", "h1", "NotMentioned"),
        pred("d", "h2", "Contradiction"),
        pred("d", "h3", "NotMentioned"),
    ]
    assert risk_sensitive_recall(preds, golds) == pytest.approx(1.0)


# =========================================================================
# Evidence metrics
# =========================================================================

def test_evidence_recall_at_k_full_overlap():
    golds = [gold("d", "h1", "Entailment", [0, 1, 2])]
    preds = [pred("d", "h1", "Entailment", [0, 1, 2, 9])]
    assert evidence_recall_at_k(preds, golds) == pytest.approx(1.0)


def test_evidence_recall_at_k_partial_overlap():
    golds = [gold("d", "h1", "Entailment", [0, 1, 2, 3])]
    preds = [pred("d", "h1", "Entailment", [0, 1])]
    assert evidence_recall_at_k(preds, golds) == pytest.approx(0.5)


def test_evidence_recall_at_k_excludes_not_mentioned():
    """NotMentioned cases have no gold evidence and must not affect the metric."""
    golds = [
        gold("d", "h1", "Entailment", [0]),
        gold("d", "h2", "NotMentioned"),
    ]
    preds = [
        pred("d", "h1", "Entailment", [0]),
        pred("d", "h2", "NotMentioned", [7]),  # spurious retrieval, should be ignored
    ]
    assert evidence_recall_at_k(preds, golds) == pytest.approx(1.0)


def test_evidence_precision():
    golds = [gold("d", "h1", "Entailment", [0, 1])]
    preds = [pred("d", "h1", "Entailment", [0, 1, 2, 3])]  # 2 of 4 retrieved are gold
    assert evidence_precision(preds, golds) == pytest.approx(0.5)


def test_mean_reciprocal_rank():
    golds = [gold("d", "h1", "Entailment", [5])]
    preds = [pred("d", "h1", "Entailment", [1, 2, 5])]  # gold found at rank 3
    assert mean_reciprocal_rank(preds, golds) == pytest.approx(1 / 3)


# =========================================================================
# Joint metric
# =========================================================================

def test_joint_correctness_not_mentioned():
    """
    Correct NotMentioned needs no evidence check (absence of evidence IS
    the correct finding). Wrong NotMentioned is always jointly incorrect.
    """
    golds = [
        gold("d", "h1", "NotMentioned"),
        gold("d", "h2", "NotMentioned"),
    ]
    preds = [
        pred("d", "h1", "NotMentioned"),  # correct, no evidence needed
        pred("d", "h2", "Entailment"),    # wrong label
    ]
    assert joint_label_evidence_correctness(preds, golds) == pytest.approx(0.5)


def test_joint_correctness_requires_evidence_above_tau():
    golds = [gold("d", "h1", "Entailment", [0, 1, 2, 3])]
    # Label correct, but only 1/4 gold spans retrieved (recall 0.25 < tau 0.5).
    preds = [pred("d", "h1", "Entailment", [0])]
    assert joint_label_evidence_correctness(preds, golds, tau_evidence=0.5) == 0.0


def test_joint_correctness_passes_at_tau_boundary():
    golds = [gold("d", "h1", "Entailment", [0, 1])]
    preds = [pred("d", "h1", "Entailment", [0])]  # recall exactly 0.5
    assert joint_label_evidence_correctness(preds, golds, tau_evidence=0.5) == 1.0


def test_joint_correctness_abstained_is_never_correct():
    golds = [gold("d", "h1", "Entailment", [0])]
    preds = [pred("d", "h1", "Entailment", [0], abstained=True)]
    assert joint_label_evidence_correctness(preds, golds) == 0.0


# =========================================================================
# Abstention / confidence metrics
# =========================================================================

def test_coverage_and_abstention_rate():
    preds = [
        pred("d", "h1", "Entailment"),
        pred("d", "h2", "Entailment", abstained=True),
        pred("d", "h3", "Entailment"),
        pred("d", "h4", "Entailment", abstained=True),
    ]
    assert coverage(preds) == pytest.approx(0.5)
    assert abstention_rate(preds) == pytest.approx(0.5)


def test_selective_accuracy_higher_than_overall():
    golds = [gold("d", f"h{i}", "Entailment") for i in range(4)]
    preds = [
        pred("d", "h0", "Entailment"),               # correct, answered
        pred("d", "h1", "Entailment"),               # correct, answered
        pred("d", "h2", "Contradiction", abstained=True),  # would be wrong, abstained
        pred("d", "h3", "Contradiction"),             # wrong, answered
    ]
    sel_acc = selective_accuracy(preds, golds)
    overall_acc = label_accuracy(preds, golds)
    assert sel_acc == pytest.approx(2 / 3)  # 2 correct of 3 non-abstained
    assert overall_acc == pytest.approx(2 / 3)  # label_accuracy also excludes abstentions
    assert sel_acc >= overall_acc


def test_abstention_effectiveness():
    golds = [gold("d", f"h{i}", "Entailment") for i in range(2)]
    preds = [
        pred("d", "h0", "Contradiction", abstained=True),  # abstained, would be wrong
        pred("d", "h1", "Entailment", abstained=True),      # abstained, would be right
    ]
    # 1 of 2 abstained cases would have been wrong.
    assert abstention_effectiveness(preds, golds) == pytest.approx(0.5)


def test_unsafe_non_abstention_rate():
    golds = [gold("d", f"h{i}", "Entailment") for i in range(4)]
    preds = [
        pred("d", "h0", "Entailment"),                      # correct, answered - safe
        pred("d", "h1", "Contradiction"),                    # WRONG, answered - unsafe
        pred("d", "h2", "Contradiction", abstained=True),    # wrong but abstained - safe
        pred("d", "h3", "Entailment"),                       # correct, answered - safe
    ]
    assert unsafe_non_abstention_rate(preds, golds) == pytest.approx(0.25)


# =========================================================================
# Agent metrics
# =========================================================================

def test_agent_routing_rate():
    preds = [
        pred("d", "h0", "Entailment", agent_used=True),
        pred("d", "h1", "Entailment", agent_used=False),
        pred("d", "h2", "Entailment", agent_used=True),
        pred("d", "h3", "Entailment", agent_used=False),
    ]
    assert agent_routing_rate(preds) == pytest.approx(0.5)


def test_agent_recovery_rate():
    golds = [gold("d", f"h{i}", "Entailment") for i in range(2)]
    baseline = [
        pred("d", "h0", "Contradiction"),  # baseline wrong
        pred("d", "h1", "Entailment"),     # baseline correct
    ]
    agent_preds = [
        pred("d", "h0", "Entailment", agent_used=True),  # agent fixed it -> recovery
        pred("d", "h1", "Entailment", agent_used=True),  # baseline already correct -> not a recovery
    ]
    assert agent_recovery_rate(agent_preds, golds, baseline) == pytest.approx(0.5)


def test_agent_regression_rate():
    golds = [gold("d", f"h{i}", "Entailment") for i in range(2)]
    baseline = [
        pred("d", "h0", "Entailment"),      # baseline correct
        pred("d", "h1", "Contradiction"),   # baseline wrong
    ]
    agent_preds = [
        pred("d", "h0", "Contradiction", agent_used=True),  # agent broke it -> regression
        pred("d", "h1", "Entailment", agent_used=True),      # agent fixed it -> not a regression
    ]
    assert agent_regression_rate(agent_preds, golds, baseline) == pytest.approx(0.5)


def test_agent_recovery_and_regression_without_baseline_are_zero():
    golds = [gold("d", "h0", "Entailment")]
    agent_preds = [pred("d", "h0", "Entailment", agent_used=True)]
    assert agent_recovery_rate(agent_preds, golds, None) == 0.0
    assert agent_regression_rate(agent_preds, golds, None) == 0.0


# =========================================================================
# Cost / latency metrics
# =========================================================================

def test_cost_and_latency_percentiles():
    preds = [pred("d", f"h{i}", "Entailment", latency_ms=float(i * 100), cost_usd=0.01)
             for i in range(1, 101)]  # latencies 100..10000 ms
    summary = cost_and_latency_summary(preds)
    assert summary["p50_latency_ms"] == pytest.approx(5100.0)
    assert summary["p90_latency_ms"] == pytest.approx(9100.0)
    assert summary["p95_latency_ms"] == pytest.approx(9600.0)
    assert summary["p99_latency_ms"] == pytest.approx(10000.0)
    assert summary["total_cost_usd"] == pytest.approx(1.0)


def test_cost_per_correct():
    golds = [gold("d", "h0", "Entailment"), gold("d", "h1", "Entailment")]
    preds = [
        pred("d", "h0", "Entailment", cost_usd=0.02),  # correct
        pred("d", "h1", "Contradiction", cost_usd=0.02),  # wrong
    ]
    summary = cost_and_latency_summary(preds, golds)
    # Total cost 0.04, only 1 correct non-abstained case.
    assert summary["cost_per_correct_usd"] == pytest.approx(0.04)


def test_cost_and_latency_summary_empty():
    summary = cost_and_latency_summary([])
    assert summary["total_cost_usd"] == 0.0
    assert summary["p95_latency_ms"] == 0.0


# =========================================================================
# Integration smoke test
# =========================================================================

def test_wilson_score_interval_zero_n_returns_zero():
    assert wilson_score_interval(0, 0) == (0.0, 0.0)


def test_wilson_score_interval_bounds_are_ordered_and_within_range():
    low, high = wilson_score_interval(successes=8, n=10)
    assert 0.0 <= low <= high <= 1.0


def test_wilson_score_interval_narrows_with_more_data_same_proportion():
    """Same observed recall (80%), more examples -> a tighter interval."""
    low_small, high_small = wilson_score_interval(successes=8, n=10)
    low_large, high_large = wilson_score_interval(successes=800, n=1000)
    assert (high_large - low_large) < (high_small - low_small)


def test_contradiction_recall_with_ci_all_correct():
    golds = [gold("d1", "h1", "Contradiction"), gold("d1", "h2", "Contradiction")]
    preds = [pred("d1", "h1", "Contradiction"), pred("d1", "h2", "Contradiction")]
    result = contradiction_recall_with_ci(preds, golds)
    assert result["recall"] == pytest.approx(1.0)
    assert result["n"] == 2
    assert result["correct"] == 2
    assert result["ci_low"] < 1.0  # even 2/2 correct has real uncertainty at n=2


def test_contradiction_recall_with_ci_ignores_other_classes():
    """A perfect Entailment/NotMentioned run with zero real Contradictions must not fake a 0% recall."""
    golds = [gold("d1", "h1", "Entailment"), gold("d1", "h2", "NotMentioned")]
    preds = [pred("d1", "h1", "Entailment"), pred("d1", "h2", "NotMentioned")]
    result = contradiction_recall_with_ci(preds, golds)
    assert result["n"] == 0
    assert result["recall"] == 0.0


def test_contradiction_recall_with_ci_excludes_abstained_cases():
    golds = [gold("d1", "h1", "Contradiction")]
    preds = [pred("d1", "h1", "Contradiction", abstained=True)]
    result = contradiction_recall_with_ci(preds, golds)
    assert result["n"] == 0


def test_risk_sensitive_recall_can_hide_bad_contradiction_recall():
    """
    The exact failure mode instructor feedback flagged: NotMentioned
    (the more common class here) being perfect can keep the averaged
    metric looking fine while Contradiction recall alone is bad.
    """
    golds = [
        gold("d1", "h1", "Contradiction"), gold("d1", "h2", "Contradiction"),
        gold("d1", "h3", "NotMentioned"), gold("d1", "h4", "NotMentioned"),
    ]
    preds = [
        pred("d1", "h1", "NotMentioned"),  # Contradiction missed
        pred("d1", "h2", "Contradiction"),  # Contradiction caught
        pred("d1", "h3", "NotMentioned"), pred("d1", "h4", "NotMentioned"),  # both correct
    ]
    combined = risk_sensitive_recall(preds, golds)
    contradiction_only = contradiction_recall_with_ci(preds, golds)
    assert contradiction_only["recall"] == pytest.approx(0.5)
    assert combined > contradiction_only["recall"]  # NotMentioned's 100% pulls the average up


def test_compute_all_metrics_includes_contradiction_recall_fields():
    preds = [pred(g.doc_id, g.hypothesis_id, g.gold_label.value, g.gold_span_indices)
             for g in BALANCED_GOLDS]
    result = compute_all_metrics(preds, BALANCED_GOLDS)
    assert result.contradiction_n == 2  # BALANCED_GOLDS has 2 Contradiction cases
    assert result.contradiction_recall == pytest.approx(1.0)
    assert result.contradiction_correct == 2
    assert 0.0 <= result.contradiction_recall_ci_low <= result.contradiction_recall_ci_high <= 1.0


def test_compute_all_metrics_smoke():
    """compute_all_metrics should populate every MetricResult field without error."""
    preds = [pred(g.doc_id, g.hypothesis_id, g.gold_label.value, g.gold_span_indices,
                  cost_usd=0.01, latency_ms=1500.0)
             for g in BALANCED_GOLDS]
    result = compute_all_metrics(preds, BALANCED_GOLDS)
    assert result.accuracy == pytest.approx(1.0)
    assert result.macro_f1 == pytest.approx(1.0)
    assert result.total_cases == len(BALANCED_GOLDS)
    assert result.total_cost_usd == pytest.approx(0.06)


# =========================================================================
# Significance testing (McNemar's test, T032 code-audit fix)
# =========================================================================

def test_mcnemar_identical_predictions_gives_p_value_one():
    """No discordant pairs at all - two systems that agree everywhere
    can't be shown to differ, and the test must say so (p=1.0), not
    divide by zero."""
    preds_a = [pred(g.doc_id, g.hypothesis_id, g.gold_label.value) for g in BALANCED_GOLDS]
    preds_b = [pred(g.doc_id, g.hypothesis_id, g.gold_label.value) for g in BALANCED_GOLDS]
    result = mcnemar_test(preds_a, preds_b, BALANCED_GOLDS)
    assert result["n_discordant"] == 0
    assert result["p_value"] == 1.0
    assert result["significant_at_0.05"] is False


def test_mcnemar_small_discordant_count_is_not_significant():
    """T030's exact scenario: 6 recovered vs 3 regressed out of a small
    subset. b=6, c=3 (n_discordant=9) is real-world-sized noise - the
    exact binomial test should NOT call this significant at alpha=0.05,
    confirming the code-audit's concern that '+3 cases on 150 samples is
    noise' was correct without a real test to check it."""
    wrong_golds = [gold(f"d{i}", "h1", "Entailment") for i in range(9)]
    # First 6: A right, B wrong (A's "wins"). Last 3: A wrong, B right (B's "wins").
    preds_a = (
        [pred(f"d{i}", "h1", "Entailment") for i in range(6)]
        + [pred(f"d{i}", "h1", "Contradiction") for i in range(6, 9)]
    )
    preds_b = (
        [pred(f"d{i}", "h1", "Contradiction") for i in range(6)]
        + [pred(f"d{i}", "h1", "Entailment") for i in range(6, 9)]
    )
    result = mcnemar_test(preds_a, preds_b, wrong_golds)
    assert result["b_a_only_correct"] == 6
    assert result["c_b_only_correct"] == 3
    assert result["n_discordant"] == 9
    assert result["significant_at_0.05"] is False


def test_mcnemar_large_lopsided_discordance_is_significant():
    """A system that wins nearly every discordant case over a large
    enough sample should register as a real, significant difference."""
    n = 60
    golds_n = [gold(f"d{i}", "h1", "Entailment") for i in range(n)]
    # A right on all 60; B right on only the last 5 (55 discordant pairs, all favoring A).
    preds_a = [pred(f"d{i}", "h1", "Entailment") for i in range(n)]
    preds_b = (
        [pred(f"d{i}", "h1", "Contradiction") for i in range(n - 5)]
        + [pred(f"d{i}", "h1", "Entailment") for i in range(n - 5, n)]
    )
    result = mcnemar_test(preds_a, preds_b, golds_n)
    assert result["n_discordant"] == 55
    assert result["significant_at_0.05"] is True
