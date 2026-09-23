"""
Metric computation functions — Section 11 of the planning document.

All metrics are pure functions: they take predictions + gold data and
return numbers.  No side effects, no file I/O, no network calls.
This makes them easy to unit-test with synthetic data.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from evaluation.schemas import GoldCase, Label, MetricResult, Prediction


# =========================================================================
# Classification Metrics
# =========================================================================

def label_accuracy(predictions: Sequence[Prediction], golds: Sequence[GoldCase]) -> float:
    """Simple accuracy: correct / total (excludes abstentions)."""
    matched = _match_predictions_to_golds(predictions, golds)
    non_abstained = [(p, g) for p, g in matched if not p.abstained]
    if not non_abstained:
        return 0.0
    correct = sum(1 for p, g in non_abstained if p.predicted_label == g.gold_label)
    return correct / len(non_abstained)


def per_class_metrics(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> dict[str, dict[str, float]]:
    """
    Per-class precision, recall, F1 for each label.

    Returns:
        {"Entailment": {"precision": .., "recall": .., "f1": ..}, ...}
    """
    matched = _match_predictions_to_golds(predictions, golds)
    non_abstained = [(p, g) for p, g in matched if not p.abstained]

    classes = [Label.ENTAILMENT, Label.CONTRADICTION, Label.NOT_MENTIONED]
    result: dict[str, dict[str, float]] = {}

    for cls in classes:
        tp = sum(1 for p, g in non_abstained
                 if p.predicted_label == cls and g.gold_label == cls)
        fp = sum(1 for p, g in non_abstained
                 if p.predicted_label == cls and g.gold_label != cls)
        fn = sum(1 for p, g in non_abstained
                 if p.predicted_label != cls and g.gold_label == cls)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)

        result[cls.value] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

    return result


def macro_f1(predictions: Sequence[Prediction], golds: Sequence[GoldCase]) -> float:
    """Macro-F1: average of per-class F1 scores."""
    pc = per_class_metrics(predictions, golds)
    f1_scores = [v["f1"] for v in pc.values()]
    return sum(f1_scores) / len(f1_scores) if f1_scores else 0.0


def risk_sensitive_recall(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> float:
    """
    Average of Contradiction recall and NotMentioned recall.
    These are the two classes where a miss is dangerous.

    NOT a substitute for reporting Contradiction recall on its own
    (see contradiction_recall_with_ci below) - Contradiction is only
    ~11% of the label distribution vs NotMentioned's ~40%, so this
    average can look fine while Contradiction detection alone is bad
    (e.g. one prompt variant this project tested had Contradiction
    recall crash to 21.4% while barely moving the combined number).
    A system can hit a target on this metric purely by improving on
    the easier, more common class - instructor feedback (CLAUDE.md's
    Decisions Log, 2026-09-23) flagged exactly this.
    """
    pc = per_class_metrics(predictions, golds)
    recall_c = pc.get(Label.CONTRADICTION.value, {}).get("recall", 0.0)
    recall_nm = pc.get(Label.NOT_MENTIONED.value, {}).get("recall", 0.0)
    return (recall_c + recall_nm) / 2


def wilson_score_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """
    Wilson score interval for a binomial proportion - more reliable than
    a normal-approximation interval at small n (e.g. Contradiction is a
    minority class, ~234 examples on the full ContractNLI test split).
    z=1.96 is the default (95% confidence).
    """
    if n == 0:
        return (0.0, 0.0)
    p_hat = successes / n
    denom = 1 + z**2 / n
    center = p_hat + z**2 / (2 * n)
    half_width = z * ((p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) ** 0.5)
    low = (center - half_width) / denom
    high = (center + half_width) / denom
    return (max(0.0, low), min(1.0, high))


def contradiction_recall_with_ci(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> dict[str, float]:
    """
    Contradiction recall reported as its OWN headline metric, with raw
    counts and a 95% Wilson interval - not folded into
    risk_sensitive_recall's average. Instructor feedback (2026-09-23):
    "Report Contradiction recall separately and make it the headline;
    note it is ~234 test examples, so report counts and an interval."
    """
    matched = _match_predictions_to_golds(predictions, golds)
    non_abstained = [(p, g) for p, g in matched if not p.abstained]
    contradiction_golds = [(p, g) for p, g in non_abstained if g.gold_label == Label.CONTRADICTION]

    n = len(contradiction_golds)
    correct = sum(1 for p, g in contradiction_golds if p.predicted_label == Label.CONTRADICTION)
    recall = correct / n if n > 0 else 0.0
    ci_low, ci_high = wilson_score_interval(correct, n)

    return {
        "recall": recall, "n": n, "correct": correct,
        "ci_low": ci_low, "ci_high": ci_high,
    }


# =========================================================================
# Evidence Metrics
# =========================================================================

def evidence_recall_at_k(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> float:
    """
    Evidence Recall@K: fraction of gold evidence spans retrieved.
    Computed only for Entailment and Contradiction (NotMentioned has no gold evidence).
    """
    total_recall = 0.0
    count = 0

    matched = _match_predictions_to_golds(predictions, golds)
    for pred, gold in matched:
        if gold.gold_label == Label.NOT_MENTIONED or not gold.gold_span_indices:
            continue
        if pred.abstained:
            continue

        gold_set = set(gold.gold_span_indices)
        retrieved_set = set(pred.retrieved_span_indices)
        overlap = gold_set & retrieved_set

        recall = len(overlap) / len(gold_set) if gold_set else 0.0
        total_recall += recall
        count += 1

    return total_recall / count if count > 0 else 0.0


def evidence_precision(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> float:
    """
    Evidence Precision: among retrieved chunks, how many contain gold evidence.
    Computed only for Entailment and Contradiction.
    """
    total_precision = 0.0
    count = 0

    matched = _match_predictions_to_golds(predictions, golds)
    for pred, gold in matched:
        if gold.gold_label == Label.NOT_MENTIONED or not gold.gold_span_indices:
            continue
        if pred.abstained or not pred.retrieved_span_indices:
            continue

        gold_set = set(gold.gold_span_indices)
        retrieved_set = set(pred.retrieved_span_indices)
        overlap = gold_set & retrieved_set

        prec = len(overlap) / len(retrieved_set) if retrieved_set else 0.0
        total_precision += prec
        count += 1

    return total_precision / count if count > 0 else 0.0


def mean_reciprocal_rank(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> float:
    """
    MRR: for each query, 1/rank of the first retrieved chunk that overlaps gold.
    """
    total_rr = 0.0
    count = 0

    matched = _match_predictions_to_golds(predictions, golds)
    for pred, gold in matched:
        if gold.gold_label == Label.NOT_MENTIONED or not gold.gold_span_indices:
            continue
        if pred.abstained or not pred.retrieved_span_indices:
            continue

        gold_set = set(gold.gold_span_indices)
        rr = 0.0
        for rank, span_idx in enumerate(pred.retrieved_span_indices, start=1):
            if span_idx in gold_set:
                rr = 1.0 / rank
                break
        total_rr += rr
        count += 1

    return total_rr / count if count > 0 else 0.0


# =========================================================================
# Joint Metric (Professor's Key Metric)
# =========================================================================

def joint_label_evidence_correctness(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
    tau_evidence: float = 0.5,
) -> float:
    """
    Joint Label-and-Evidence Correctness.

    A case is jointly correct if:
    - predicted_label == gold_label AND evidence_recall@K >= tau_evidence
      (for Entailment/Contradiction)
    - predicted_label == NotMentioned AND gold_label == NotMentioned
      (no evidence check needed)
    """
    matched = _match_predictions_to_golds(predictions, golds)
    if not matched:
        return 0.0

    joint_correct = 0
    total = len(matched)

    for pred, gold in matched:
        if pred.abstained:
            continue

        if pred.predicted_label != gold.gold_label:
            continue

        if gold.gold_label == Label.NOT_MENTIONED:
            # Correct NotMentioned — no evidence check needed
            joint_correct += 1
        else:
            # Entailment or Contradiction — need evidence recall check
            gold_set = set(gold.gold_span_indices)
            if not gold_set:
                # No gold evidence to check — label match is enough
                joint_correct += 1
            else:
                retrieved_set = set(pred.retrieved_span_indices)
                overlap = gold_set & retrieved_set
                recall = len(overlap) / len(gold_set)
                if recall >= tau_evidence:
                    joint_correct += 1

    return joint_correct / total


# =========================================================================
# Abstention / Confidence Metrics
# =========================================================================

def coverage(predictions: Sequence[Prediction]) -> float:
    """Fraction of cases where the system provides a label (not abstained)."""
    if not predictions:
        return 0.0
    non_abstained = sum(1 for p in predictions if not p.abstained)
    return non_abstained / len(predictions)


def abstention_rate(predictions: Sequence[Prediction]) -> float:
    """Fraction of cases where the system abstained."""
    return 1.0 - coverage(predictions)


def selective_accuracy(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> float:
    """Accuracy only among cases the system chose to answer."""
    matched = _match_predictions_to_golds(predictions, golds)
    non_abstained = [(p, g) for p, g in matched if not p.abstained]
    if not non_abstained:
        return 0.0
    correct = sum(1 for p, g in non_abstained if p.predicted_label == g.gold_label)
    return correct / len(non_abstained)


def abstention_effectiveness(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> float:
    """
    Of abstained cases, what fraction would have been wrong?
    Higher = system correctly identifies its failures.
    """
    matched = _match_predictions_to_golds(predictions, golds)
    abstained = [(p, g) for p, g in matched if p.abstained]
    if not abstained:
        return 0.0

    # "Would be wrong" = predicted label (even though abstained) != gold
    would_be_wrong = sum(
        1 for p, g in abstained if p.predicted_label != g.gold_label
    )
    return would_be_wrong / len(abstained)


def unsafe_non_abstention_rate(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> float:
    """
    Cases where the system confidently gave the wrong answer.
    This is the most dangerous metric — represents silent failures.
    Target: < 10%.
    """
    matched = _match_predictions_to_golds(predictions, golds)
    if not matched:
        return 0.0

    wrong_and_confident = sum(
        1 for p, g in matched
        if not p.abstained and p.predicted_label != g.gold_label
    )
    return wrong_and_confident / len(matched)


# =========================================================================
# Agent Metrics
# =========================================================================

def mcnemar_test(
    predictions_a: Sequence[Prediction],
    predictions_b: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> dict:
    """
    McNemar's test on paired correct/incorrect outcomes for two systems
    over the SAME cases (WBS T032 support; added 2026-09-24 - a
    code-audit finding was that the agent's claimed +N-case gain
    (T030: 6 recovered / 3 regressed of 67) had no significance test, so
    "noise vs. real effect" was never actually checked).

    Only the discordant pairs matter: b = A right, B wrong; c = A wrong,
    B right. Uses the exact binomial test (recommended whenever b+c < 25,
    per Edwards 1948) rather than the chi-square approximation, since
    T030's agent-routed subset (67 cases) produces a small discordant
    count either way.
    """
    from scipy import stats

    matched_a = {(p.doc_id, p.hypothesis_id): p for p, _ in _match_predictions_to_golds(predictions_a, golds)}
    matched_b = {(p.doc_id, p.hypothesis_id): p for p, _ in _match_predictions_to_golds(predictions_b, golds)}
    gold_lookup = {(g.doc_id, g.hypothesis_id): g for g in golds}

    common_keys = set(matched_a) & set(matched_b)
    b = 0  # A correct, B incorrect
    c = 0  # A incorrect, B correct
    for key in common_keys:
        gold = gold_lookup[key]
        a_correct = not matched_a[key].abstained and matched_a[key].predicted_label == gold.gold_label
        b_correct = not matched_b[key].abstained and matched_b[key].predicted_label == gold.gold_label
        if a_correct and not b_correct:
            b += 1
        elif b_correct and not a_correct:
            c += 1

    n_discordant = b + c
    if n_discordant == 0:
        p_value = 1.0
    else:
        # Two-sided exact binomial test: under H0, each discordant pair is
        # equally likely to favor A or B, so min(b, c) ~ Binomial(n, 0.5).
        p_value = stats.binomtest(min(b, c), n_discordant, 0.5, alternative="two-sided").pvalue

    return {
        "n_common": len(common_keys), "b_a_only_correct": b, "c_b_only_correct": c,
        "n_discordant": n_discordant, "p_value": float(p_value),
        "significant_at_0.05": bool(p_value < 0.05),
    }


def agent_routing_rate(predictions: Sequence[Prediction]) -> float:
    """Fraction of cases sent to the agent."""
    if not predictions:
        return 0.0
    return sum(1 for p in predictions if p.agent_used) / len(predictions)


def agent_recovery_rate(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
    baseline_predictions: Sequence[Prediction] | None = None,
) -> float:
    """
    Among agent-routed cases: fraction where agent got it right
    AND the baseline (initial RAG) was wrong or abstained.
    Requires baseline_predictions for comparison.
    """
    if baseline_predictions is None:
        return 0.0

    matched_agent = _match_predictions_to_golds(predictions, golds)
    matched_base = _match_predictions_to_golds(baseline_predictions, golds)
    base_lookup = {(p.doc_id, p.hypothesis_id): p for p, _ in matched_base}

    agent_routed = [(p, g) for p, g in matched_agent if p.agent_used]
    if not agent_routed:
        return 0.0

    recovered = 0
    for pred, gold in agent_routed:
        key = (pred.doc_id, pred.hypothesis_id)
        base_pred = base_lookup.get(key)
        if base_pred is None:
            continue
        base_wrong = base_pred.abstained or base_pred.predicted_label != gold.gold_label
        agent_right = pred.predicted_label == gold.gold_label
        if base_wrong and agent_right:
            recovered += 1

    return recovered / len(agent_routed)


def agent_regression_rate(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
    baseline_predictions: Sequence[Prediction] | None = None,
) -> float:
    """
    Among agent-routed cases: fraction where the agent produced a wrong
    label AND the baseline (initial RAG) was correct. This is the cost of
    routing to the agent — cases it made worse.
    """
    if baseline_predictions is None:
        return 0.0

    matched_agent = _match_predictions_to_golds(predictions, golds)
    matched_base = _match_predictions_to_golds(baseline_predictions, golds)
    base_lookup = {(p.doc_id, p.hypothesis_id): p for p, _ in matched_base}

    agent_routed = [(p, g) for p, g in matched_agent if p.agent_used]
    if not agent_routed:
        return 0.0

    regressed = 0
    for pred, gold in agent_routed:
        key = (pred.doc_id, pred.hypothesis_id)
        base_pred = base_lookup.get(key)
        if base_pred is None:
            continue
        base_correct = not base_pred.abstained and base_pred.predicted_label == gold.gold_label
        agent_wrong = pred.abstained or pred.predicted_label != gold.gold_label
        if base_correct and agent_wrong:
            regressed += 1

    return regressed / len(agent_routed)


# =========================================================================
# Cost / Latency Metrics
# =========================================================================

def cost_and_latency_summary(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase] | None = None,
) -> dict[str, float]:
    """Compute aggregate cost and latency statistics."""
    costs = []
    latencies = []

    for p in predictions:
        if p.cost_latency:
            costs.append(p.cost_latency.cost_usd)
            latencies.append(p.cost_latency.latency_ms)

    if not costs:
        return {
            "total_cost_usd": 0.0,
            "mean_cost_per_req_usd": 0.0,
            "cost_per_correct_usd": 0.0,
            "p50_latency_ms": 0.0,
            "p90_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "p99_latency_ms": 0.0,
        }

    latencies.sort()
    n = len(latencies)

    def _percentile(pct: float) -> float:
        idx = min(int(n * pct), n - 1)
        return latencies[idx]

    total_cost = sum(costs)
    correct_non_abstained = 0
    if golds is not None:
        matched = _match_predictions_to_golds(predictions, golds)
        correct_non_abstained = sum(
            1 for p, g in matched if not p.abstained and p.predicted_label == g.gold_label
        )

    return {
        "total_cost_usd": total_cost,
        "mean_cost_per_req_usd": total_cost / len(costs),
        "cost_per_correct_usd": (
            total_cost / correct_non_abstained if correct_non_abstained > 0 else 0.0
        ),
        "p50_latency_ms": _percentile(0.50),
        "p90_latency_ms": _percentile(0.90),
        "p95_latency_ms": _percentile(0.95),
        "p99_latency_ms": _percentile(0.99),
    }


# =========================================================================
# Compute All Metrics
# =========================================================================

def compute_all_metrics(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
    tau_evidence: float = 0.5,
    baseline_predictions: Sequence[Prediction] | None = None,
) -> MetricResult:
    """Compute every metric and return a MetricResult."""
    pc = per_class_metrics(predictions, golds)
    cost_lat = cost_and_latency_summary(predictions, golds)
    matched = _match_predictions_to_golds(predictions, golds)
    non_abstained = [(p, g) for p, g in matched if not p.abstained]
    contradiction = contradiction_recall_with_ci(predictions, golds)

    return MetricResult(
        # Classification
        accuracy=label_accuracy(predictions, golds),
        macro_f1=macro_f1(predictions, golds),
        risk_sensitive_recall=risk_sensitive_recall(predictions, golds),
        contradiction_recall=contradiction["recall"],
        contradiction_n=contradiction["n"],
        contradiction_correct=contradiction["correct"],
        contradiction_recall_ci_low=contradiction["ci_low"],
        contradiction_recall_ci_high=contradiction["ci_high"],
        per_class=pc,

        # Evidence
        evidence_recall_at_k=evidence_recall_at_k(predictions, golds),
        evidence_precision=evidence_precision(predictions, golds),
        mrr=mean_reciprocal_rank(predictions, golds),

        # Joint
        joint_label_evidence_correctness=joint_label_evidence_correctness(
            predictions, golds, tau_evidence
        ),

        # Abstention
        coverage=coverage(predictions),
        selective_accuracy=selective_accuracy(predictions, golds),
        abstention_rate=abstention_rate(predictions),
        abstention_effectiveness=abstention_effectiveness(predictions, golds),
        unsafe_non_abstention_rate=unsafe_non_abstention_rate(predictions, golds),

        # Agent
        agent_routing_rate=agent_routing_rate(predictions),
        agent_recovery_rate=agent_recovery_rate(
            predictions, golds, baseline_predictions
        ),
        agent_regression_rate=agent_regression_rate(
            predictions, golds, baseline_predictions
        ),

        # Cost/latency
        total_cost_usd=cost_lat["total_cost_usd"],
        mean_cost_per_req_usd=cost_lat["mean_cost_per_req_usd"],
        cost_per_correct_usd=cost_lat["cost_per_correct_usd"],
        p50_latency_ms=cost_lat["p50_latency_ms"],
        p90_latency_ms=cost_lat["p90_latency_ms"],
        p95_latency_ms=cost_lat["p95_latency_ms"],
        p99_latency_ms=cost_lat["p99_latency_ms"],

        # Counts
        total_cases=len(matched),
        correct_cases=sum(
            1 for p, g in non_abstained if p.predicted_label == g.gold_label
        ),
        abstained_cases=sum(1 for p in predictions if p.abstained),
    )


# =========================================================================
# Helpers
# =========================================================================

def _match_predictions_to_golds(
    predictions: Sequence[Prediction],
    golds: Sequence[GoldCase],
) -> list[tuple[Prediction, GoldCase]]:
    """Match predictions to gold cases by (doc_id, hypothesis_id)."""
    gold_lookup = {(g.doc_id, g.hypothesis_id): g for g in golds}
    matched = []
    for pred in predictions:
        key = (pred.doc_id, pred.hypothesis_id)
        gold = gold_lookup.get(key)
        if gold is not None:
            matched.append((pred, gold))
    return matched
