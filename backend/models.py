"""
NDATrace API Pydantic request/response schemas (WBS T032).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HypothesisInfo(BaseModel):
    hypothesis_id: str
    short_description: str
    hypothesis_text: str


class ReviewRequest(BaseModel):
    nda_text: str = Field(..., min_length=1, description="Full NDA document text to review.")
    hypothesis_ids: list[str] | None = Field(
        default=None,
        description="Subset of the 17 standard requirement IDs to check (e.g. ['nda-1', 'nda-11']). "
                    "Omit to check all available requirements.",
    )


class RequirementResult(BaseModel):
    hypothesis_id: str
    hypothesis_text: str
    label: str
    confidence: float
    explanation: str
    evidence: list[str]
    agent_used: bool
    agent_steps: int
    cost_usd: float
    latency_ms: float
    error: str | None = None


class ReviewResponse(BaseModel):
    review_id: str
    doc_id: str
    created_at: str
    results: list[RequirementResult]
    total_cost_usd: float
    total_latency_ms: float
    model: str


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


class ReviewSummary(BaseModel):
    """Lightweight row for listing past reviews (GET /results)."""
    review_id: str
    doc_id: str
    created_at: str
    num_requirements: int
    total_cost_usd: float
    model: str


class CostEstimate(BaseModel):
    """Real, measured average per-requirement cost for the legacy RAG +
    selective-agent architecture (T031) - computed live from the most
    recent matching experiment record, never hardcoded."""
    avg_cost_per_requirement_usd: float
    source_experiment_id: str
    source_sample_size: int
    model: str


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
