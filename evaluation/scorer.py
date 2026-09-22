"""
Scorer — converts raw pipeline output into Prediction objects.

This module sits between the pipeline and the harness.  The pipeline
produces its own internal result format; the scorer normalises it into
the Prediction schema that the harness and metrics expect.
"""

from __future__ import annotations

from typing import Any, Optional

from evaluation.schemas import CostLatencyRecord, Label, Prediction


def map_chunks_to_gold_span_indices(doc_spans: list[tuple[int, int]], ranked_chunks: list) -> list[int]:
    """
    Map ranked retrieved chunks to the ContractNLI-annotated span indices
    they cover, in rank order.

    Retrieval-built chunks (pipeline/chunker.py) have their own character
    boundaries, which don't line up with ContractNLI's pre-annotated
    evidence spans (`doc.spans`, referenced by gold_span_indices). To reuse
    evaluation.metrics' existing index-based Evidence Recall@K / MRR
    formulas unmodified, this maps "which annotated spans does each
    retrieved chunk overlap" into a flat list of span indices, ordered by
    the rank of the chunk that first covers them - exactly the shape
    Prediction.retrieved_span_indices expects.

    `ranked_chunks` must be pre-sorted best-first (as Retriever.query()
    already returns them). Each `chunk` needs .start_char/.end_char.
    """
    covered_in_order: list[int] = []
    seen: set[int] = set()
    for chunk in ranked_chunks:
        for idx, (span_start, span_end) in enumerate(doc_spans):
            if idx in seen:
                continue
            overlaps = span_start < chunk.end_char and span_end > chunk.start_char
            if overlaps:
                covered_in_order.append(idx)
                seen.add(idx)
    return covered_in_order


def score_raw_output(
    doc_id: str,
    hypothesis_id: str,
    raw: dict[str, Any],
) -> Prediction:
    """
    Convert a raw pipeline result dict into a Prediction.

    Expected keys in `raw`:
        label: str           — predicted label
        confidence: float    — model confidence (0..1)
        explanation: str     — model explanation
        evidence_spans: list — retrieved span indices
        evidence_texts: list — retrieved evidence texts
        agent_used: bool     — whether agent was invoked
        agent_steps: int     — number of agent steps
        tokens_in: int       — input tokens
        tokens_out: int      — output tokens
        cost_usd: float      — cost estimate
        latency_ms: float    — end-to-end latency
        raw_output: str      — raw model response
    """
    # Parse label
    label_str = raw.get("label", "NotMentioned")
    try:
        label = Label(label_str)
    except ValueError:
        label = Label.NOT_MENTIONED

    confidence = float(raw.get("confidence", 1.0))

    # Build cost/latency record if data available
    cost_latency = None
    if "latency_ms" in raw or "cost_usd" in raw:
        cost_latency = CostLatencyRecord(
            latency_ms=float(raw.get("latency_ms", 0)),
            tokens_in=int(raw.get("tokens_in", 0)),
            tokens_out=int(raw.get("tokens_out", 0)),
            cost_usd=float(raw.get("cost_usd", 0)),
            num_llm_calls=int(raw.get("num_llm_calls", 1)),
            stages=raw.get("stage_latencies", {}),
        )

    return Prediction(
        doc_id=doc_id,
        hypothesis_id=hypothesis_id,
        predicted_label=label,
        confidence=confidence,
        abstained=raw.get("abstained", False),
        retrieved_span_indices=raw.get("evidence_spans", []),
        retrieved_texts=raw.get("evidence_texts", []),
        explanation=raw.get("explanation", ""),
        agent_used=raw.get("agent_used", False),
        agent_steps=raw.get("agent_steps", 0),
        cost_latency=cost_latency,
        raw_model_output=raw.get("raw_output", ""),
    )


def make_oracle_prediction(
    doc_id: str,
    hypothesis_id: str,
    label: str,
    confidence: float,
    gold_span_indices: list[int],
    explanation: str = "",
    latency_ms: float = 0.0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
) -> Prediction:
    """
    Create a Prediction for an Oracle experiment.

    Oracle predictions use gold evidence spans (perfect retrieval)
    to test the model's reasoning ceiling.
    """
    try:
        parsed_label = Label(label)
    except ValueError:
        parsed_label = Label.NOT_MENTIONED

    cost_latency = CostLatencyRecord(
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
    )

    return Prediction(
        doc_id=doc_id,
        hypothesis_id=hypothesis_id,
        predicted_label=parsed_label,
        confidence=confidence,
        abstained=False,
        retrieved_span_indices=gold_span_indices,
        explanation=explanation,
        cost_latency=cost_latency,
    )
