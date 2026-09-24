"""
Evaluation data schemas — Pydantic models for predictions, results, and configs.

These schemas define the contract between the pipeline and the evaluation harness.
All experiment results are stored as JSONL using these models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Label(str, Enum):
    """Classification labels."""
    ENTAILMENT = "Entailment"
    CONTRADICTION = "Contradiction"
    NOT_MENTIONED = "NotMentioned"


class CostLatencyRecord(BaseModel):
    """Per-request cost and latency tracking."""
    latency_ms: float = Field(description="End-to-end latency in milliseconds")
    tokens_in: int = Field(default=0, description="Total input tokens across all LLM calls")
    tokens_out: int = Field(default=0, description="Total output tokens across all LLM calls")
    cost_usd: float = Field(default=0.0, description="Estimated cost in USD")
    num_llm_calls: int = Field(default=1, description="Number of LLM API calls")
    stages: dict[str, float] = Field(
        default_factory=dict,
        description="Per-stage latency breakdown in ms",
    )


class Prediction(BaseModel):
    """A single prediction from the pipeline."""
    doc_id: str = Field(description="Document ID from ContractNLI")
    hypothesis_id: str = Field(description="Hypothesis ID (e.g., nda-1)")
    predicted_label: Label = Field(description="Model's predicted label")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Model's confidence in the prediction",
    )
    abstained: bool = Field(
        default=False,
        description="Whether the system abstained from giving a label",
    )
    retrieved_span_indices: list[int] = Field(
        default_factory=list,
        description="Indices of retrieved evidence spans (into doc.spans)",
    )
    retrieved_texts: list[str] = Field(
        default_factory=list,
        description="Text of retrieved evidence chunks",
    )
    explanation: str = Field(
        default="",
        description="Model's explanation for its classification",
    )
    agent_used: bool = Field(
        default=False,
        description="Whether the selective agent was invoked",
    )
    agent_steps: int = Field(
        default=0,
        description="Number of agent steps if agent was used",
    )
    cost_latency: Optional[CostLatencyRecord] = Field(
        default=None,
        description="Cost and latency for this prediction",
    )
    raw_model_output: str = Field(
        default="",
        description="Raw model response (for debugging; never log NDA text)",
    )


class GoldCase(BaseModel):
    """A ground-truth case for evaluation."""
    doc_id: str
    hypothesis_id: str
    gold_label: Label
    gold_span_indices: list[int] = Field(
        default_factory=list,
        description="Indices of gold evidence spans",
    )
    category: str = Field(
        default="golden_battery",
        description="Eval case category (golden_battery, negative, injection, etc.)",
    )
    case_id: str = Field(
        default="",
        description="Eval case ID (e.g., 001, 042)",
    )
    description: str = Field(
        default="",
        description="Human-readable description of what this case tests",
    )


class ExperimentConfig(BaseModel):
    """Snapshot of the configuration used for an experiment run."""
    # extra="forbid": an unknown field (e.g. a typo, or a field the caller
    # assumed existed) must raise immediately, not silently vanish. This
    # schema had exactly that bug - sample_size was passed by a caller but
    # not declared here, so pydantic's default extra="ignore" behavior
    # dropped it with no error, permanently losing it from saved results.
    model_config = ConfigDict(extra="forbid")

    experiment_id: str = Field(description="Unique experiment identifier")
    experiment_name: str = Field(default="", description="Human-readable name")
    description: str = Field(default="", description="What this experiment tests")
    model: str = Field(default="", description="LLM model used")
    prompt_version: str = Field(default="", description="Prompt template version")
    chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=50)
    top_k: int = Field(default=5)
    embedding_model: str = Field(default="all-mpnet-base-v2")
    temperature: float = Field(default=0.0)
    confidence_threshold: float = Field(default=0.7)
    agent_enabled: bool = Field(default=False)
    agent_max_steps: int = Field(default=5)
    architecture: str = Field(
        default="rag",
        description="Architecture variant: rule, full_context, oracle, rag, rag_agent",
    )
    split: str = Field(default="dev", description="Dataset split used")
    sample_size: int = Field(default=0, description="Number of cases in this run (0 = full split)")
    seed: int = Field(default=42, description="Random seed for reproducibility (A12)")
    extra: dict = Field(default_factory=dict, description="Any additional config")


class MetricResult(BaseModel):
    """Container for computed metrics."""
    # Classification
    accuracy: float = 0.0
    macro_f1: float = 0.0
    risk_sensitive_recall: float = 0.0

    # Contradiction recall, reported as its own headline metric (not
    # folded into risk_sensitive_recall's average) with a 95% Wilson
    # interval, since it's a minority class (~11% of labels) where the
    # combined metric above can hide poor performance. Instructor
    # feedback, 2026-09-23 - see docs/decisions.md.
    contradiction_recall: float = 0.0
    contradiction_n: int = 0
    contradiction_correct: int = 0
    contradiction_recall_ci_low: float = 0.0
    contradiction_recall_ci_high: float = 0.0

    # Per-class
    per_class: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Per-class precision/recall/F1",
    )

    # Evidence
    evidence_recall_at_k: float = 0.0
    evidence_precision: float = 0.0
    mrr: float = 0.0

    # Joint
    joint_label_evidence_correctness: float = 0.0

    # Abstention
    coverage: float = 1.0
    selective_accuracy: float = 0.0
    abstention_rate: float = 0.0
    abstention_effectiveness: float = 0.0
    unsafe_non_abstention_rate: float = 0.0

    # Agent
    agent_routing_rate: float = 0.0
    agent_recovery_rate: float = 0.0
    agent_regression_rate: float = 0.0

    # Cost / Latency
    mean_cost_per_req_usd: float = 0.0
    cost_per_correct_usd: float = 0.0
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    total_cost_usd: float = 0.0

    # Counts
    total_cases: int = 0
    correct_cases: int = 0
    abstained_cases: int = 0


class ExperimentResult(BaseModel):
    """Complete result of one experiment run."""
    config: ExperimentConfig
    metrics: MetricResult
    predictions: list[Prediction] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    duration_seconds: float = Field(default=0.0)
    error: Optional[str] = Field(default=None, description="Error if run failed")
