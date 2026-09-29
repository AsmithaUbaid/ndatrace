"""
NDATrace API Pydantic request/response schemas (WBS T032).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HypothesisInfo(BaseModel):
    hypothesis_id: str
    short_description: str
    hypothesis_text: str


# E22 LLM10 remediation: the ContractNLI dataset's real observed max NDA
# length is 54,571 chars (train+dev+test); NDA_TEXT_MAX_LENGTH gives ~3x
# headroom above that for real-world variance while still bounding
# pathological/DoS-scale input before it reaches parsing/chunking/indexing.
# REQUIREMENT_MAX_LENGTH gives ~12x headroom over the longest of the 17
# fixed hypothesis texts (162 chars) for free-text custom requirements.
NDA_TEXT_MAX_LENGTH = 150_000
REQUIREMENT_MAX_LENGTH = 2_000


class ReviewRequest(BaseModel):
    nda_text: str = Field(..., min_length=1, max_length=NDA_TEXT_MAX_LENGTH, description="Full NDA document text to review.")
    hypothesis_ids: list[str] | None = Field(
        default=None,
        description="Subset of the 17 standard requirement IDs to check (e.g. ['nda-1', 'nda-11']). "
                    "Omit to check all available requirements.",
    )


class RetrievedChunkMetadata(BaseModel):
    chunk_id: int
    rank: int
    start_char: int
    end_char: int
    bm25_score: float
    reranker_score: float
    text: str


class RequirementResult(BaseModel):
    hypothesis_id: str
    hypothesis_text: str
    label: str | None
    confidence: float | None = None
    confidence_available: bool = False
    explanation: str
    evidence: list[str]
    source_valid: bool | None = None
    needs_human_review: bool = False
    review_reason: str | None = None
    sources: list[RetrievedChunkMetadata] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunkMetadata] = Field(default_factory=list)
    # Compatibility fields for historical rows. The current runtime never
    # invokes an agent and always returns false/zero here.
    agent_used: bool = False
    agent_steps: int = 0
    cost_usd: float
    latency_ms: float
    error: str | None = None
    # E22 LLM01 remediation: see pipeline/final_review.py's injection_guard wiring.
    security_review_required: bool = False
    security_flags: list[str] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    review_id: str
    doc_id: str
    created_at: str
    results: list[RequirementResult]
    total_cost_usd: float
    total_latency_ms: float
    model: str


class FinalReviewRequest(BaseModel):
    """One NDA and one requirement for the frozen top-5 RAG product path."""
    nda_text: str = Field(..., min_length=1, max_length=NDA_TEXT_MAX_LENGTH, description="Full NDA document text to review.")
    requirement: str = Field(..., min_length=1, max_length=REQUIREMENT_MAX_LENGTH, description="Confidentiality requirement to check, in free text.")


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
    sources: list[RetrievedChunkMetadata] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunkMetadata] = Field(default_factory=list)
    # E22 LLM01 remediation.
    security_review_required: bool = False
    security_flags: list[str] = Field(default_factory=list)


class ReviewSummary(BaseModel):
    """Lightweight row for listing past reviews (GET /results)."""
    review_id: str
    doc_id: str
    created_at: str
    num_requirements: int
    total_cost_usd: float
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
    architecture_status: str | None = None
