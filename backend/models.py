"""
NDATrace API Pydantic request/response schemas (WBS T032).

Shapes here mirror pipeline/orchestrator.py's ReviewResult and
evaluation/schemas.py's experiment-result JSON (Section 19) - kept
consistent rather than inventing a third, parallel shape per module.
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


class ReviewSummary(BaseModel):
    """Lightweight row for listing past reviews (GET /results)."""
    review_id: str
    doc_id: str
    created_at: str
    num_requirements: int
    total_cost_usd: float
    model: str


class CostEstimate(BaseModel):
    """Real, measured average per-requirement cost for the production
    architecture (RAG + selective agent, T031) - computed live from the
    most recent matching experiment record, never hardcoded, so it can't
    silently go stale as the model/architecture changes."""
    avg_cost_per_requirement_usd: float
    source_experiment_id: str
    source_sample_size: int
    model: str


class ExperimentSummary(BaseModel):
    """One row from an offline results/runs/*.jsonl experiment record."""
    experiment_id: str
    experiment_name: str
    model: str
    split: str | None = None
    sample_size: int | None = None
    accuracy: float | None = None
    macro_f1: float | None = None
    contradiction_recall: float | None = None
    contradiction_recall_ci_low: float | None = None
    contradiction_recall_ci_high: float | None = None
    joint_label_evidence_correctness: float | None = None
    total_cost_usd: float | None = None
    timestamp: str | None = None
