"""
NDATrace API Pydantic request/response schemas (WBS T032).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HypothesisInfo(BaseModel):
    hypothesis_id: str
    short_description: str
    hypothesis_text: str


class FinalReviewRequest(BaseModel):
    """Request for the final, frozen product pipeline (E19: GPT-5-mini + P0 + FULL context).
    One NDA, one requirement - the primary reviewer-facing workflow, not the batch/experimental path."""
    nda_text: str = Field(..., min_length=1, description="Full NDA document text to review.")
    requirement: str = Field(..., min_length=1, description="Confidentiality requirement to check, in free text.")


class FinalReviewResponse(BaseModel):
    label: str | None
    evidence: list[str]
    explanation: str
    source_valid: bool | None
    needs_human_review: bool
    review_reason: str | None
    model: str
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    trace_id: str


class FinalTestResult(BaseModel):
    """One row of the reconstruction-v2 final held-out TEST comparison
    (E17/E17B), read directly from
    results/final/reconstruction_v2/full_test_comparison.csv - never
    recomputed, never a live experiment log."""
    system: str
    n: int
    accuracy: float
    macro_f1: float
    joint: float
    entailment_recall: float
    contradiction_recall: float
    notmentioned_recall: float
    evidence_recall: float | None = None
    evidence_precision: float | None = None
    source_valid_quote_rate: float | None = None
    api_cost_usd: float
