"""
Confidence / abstention routing (WBS T027, Section 6 component).

Built from T026's analysis (scripts/run_confidence_analysis.py,
data/confidence_analysis.json) on the 150-case "Best RAG" sample
(v2 prompt, T018). The plan's original design (Section 8's F01/F02/F04/F05)
assumed a single confidence signal would clear ~0.7 AUROC and let hard
abstention hit >70% effectiveness. Neither held here:

  - Self-reported confidence: AUROC 0.554 (near-random). The model reports
    confidence=1.0 on 132/150 cases (88%) regardless of correctness - it
    is not usefully calibrated, a known failure mode for LLMs asked to
    self-report certainty in structured output.
  - Retrieval score (top-1): AUROC 0.464 (below chance).
  - Rule-baseline agreement (does pipeline/rule_baseline.py's keyword
    classifier reach the same label?): AUROC 0.657 - the best of the
    signals tried, but still short of 0.7.
  - Combining self-confidence and rule-agreement did not improve on
    rule-agreement alone.

Critically, at the practical decision point (rule disagrees with RAG),
the "disagreement" bucket is still 80.6% correct - abstaining there
would discard far more right answers than wrong ones. None of the
tested signals clear the bar for hard abstention (F05's >70%
effectiveness target). Given that, this module implements a routing
function using rule-agreement as a soft signal - flagging the ~45% of
cases where signals disagree for further review, rather than either
accepting them blindly or abstaining on them outright. On disagreement,
`route()` returns "review", which corresponds to where a selective
agent (T028-T030, not yet built) should take over: it is exactly the
right place to spend an extra, more expensive investigation step,
because the flagged cases are only weakly, not strongly, likely to be
wrong (higher error concentration than the base rate, not proof of error).

Revisit if T028-T030's agent experiments find "review" cases behave
differently than expected, or if a better confidence signal is found later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Route(str, Enum):
    ACCEPT = "accept"
    REVIEW = "review"  # hand off to the selective agent once T028-T030 exists


@dataclass
class RoutingDecision:
    route: Route
    self_confidence: float
    rule_agrees: bool
    reason: str


def route(self_confidence: float, rule_agrees: bool) -> RoutingDecision:
    """
    Decide whether a RAG prediction should be accepted as-is or flagged
    for further review.

    Self-confidence is intentionally NOT used as a gating signal (T026
    found it near-random, AUROC 0.554) - it's still recorded on the
    decision for visibility/logging, but rule_agrees is what actually
    drives the route, since it's the only tested signal with any real
    discriminating power.
    """
    if rule_agrees:
        return RoutingDecision(
            route=Route.ACCEPT, self_confidence=self_confidence, rule_agrees=rule_agrees,
            reason="Rule-based baseline agrees with the RAG prediction (measured selective "
                   "accuracy 94.0% on this subset, T026).",
        )
    return RoutingDecision(
        route=Route.REVIEW, self_confidence=self_confidence, rule_agrees=rule_agrees,
        reason="Rule-based baseline disagrees with the RAG prediction - flagged for further "
               "investigation, not abstained (T026 found this bucket is still 80.6% correct, "
               "too weak a signal to justify outright abstention).",
    )
