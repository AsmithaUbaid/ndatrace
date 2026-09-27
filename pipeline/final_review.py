"""Interactive product review using the frozen E20 top-5 RAG architecture.

The benchmark conclusion remains separate: FULL-context GPT-5-mini is the
strongest measured ContractNLI TEST configuration.  The product runtime uses
E20's bounded-context retrieval configuration as an engineering decision for
interactive review.  There is no agent, routing, or silent FULL fallback.

This module knows nothing about gold labels, evaluator versions, or TEST
manifests - see pipeline/evidence_validator.py's own note: it asks only
"did this evidence quote actually come from the provided NDA text?", never
whether the label is correct. Offline scoring lives in evaluation/, not here.

GPT-P0 requests only {label, evidence} (evaluation/structured_output.py's
schema has no explanation/confidence field) - there is no calibrated
confidence to report, so none is fabricated here. The one-line explanation
below is a fixed, deterministic template keyed on the label, not a model
claim, and it never asserts anything the evidence doesn't literally show.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from evaluation.structured_output import parse_structured_output
from pipeline.evidence_text import locate_quote
from pipeline.evidence_validator import validate_evidence
from pipeline.frozen_rag import FrozenRagRetriever, RetrievedChunk, join_context
from pipeline.model_gateway import ModelError, ModelGateway

MODEL = "openai/gpt-5-mini"
MODEL_MAX_RETRIES = 1
MODEL_TIMEOUT_SECONDS = 60
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts/reconstruction_v2/gpt_p0.txt"
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"  # frozen; identical to E13/E15/E16/E17/E20

_EXPLANATION = {
    "Entailment": "The quoted clause(s) above support this requirement.",
    "Contradiction": "The quoted clause(s) above conflict with this requirement.",
    "NotMentioned": "No explicit supporting or contradicting provision was identified in the agreement.",
}


@dataclass
class FinalReviewResult:
    label: str | None
    evidence: list[str] = field(default_factory=list)
    explanation: str = ""
    source_valid: bool | None = None  # None only when there's nothing to validate (e.g. a model/parse failure)
    needs_human_review: bool = False
    review_reason: str | None = None  # set only for a real deterministic failure (parse/source-validation/provider)
    parse_status: str = "invalid"
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    cost_usd: float | None = None
    model: str = MODEL
    error: str | None = None
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    sources: list[RetrievedChunk] = field(default_factory=list)


def _failure(reason: str, *, error: str, model: str = MODEL) -> FinalReviewResult:
    return FinalReviewResult(
        label=None,
        needs_human_review=True,
        review_reason=reason,
        model=model,
        error=error,
    )


def _source_chunks(evidence: list[str], chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Return retrieved chunks that contain at least one cited quote."""
    matched: list[RetrievedChunk] = []
    for chunk in chunks:
        if any(locate_quote(quote, chunk.text) is not None for quote in evidence):
            matched.append(chunk)
    return matched


def review_final(
    nda_text: str,
    hypothesis_text: str,
    gateway: ModelGateway | None = None,
    retriever: FrozenRagRetriever | None = None,
) -> FinalReviewResult:
    """Review one requirement using only the frozen retrieved top-5 context."""
    gw = gateway or ModelGateway(
        model=MODEL,
        max_retries=MODEL_MAX_RETRIES,
        timeout_seconds=MODEL_TIMEOUT_SECONDS,
    )
    system_prompt = PROMPT_PATH.read_text()

    try:
        active_retriever = retriever or FrozenRagRetriever(nda_text)
        retrieved = active_retriever.retrieve(hypothesis_text)
    except Exception as exc:
        return _failure(
            "Relevant clauses could not be retrieved. Human review is required.",
            error=f"retrieval_error: {type(exc).__name__}",
        )

    if not retrieved:
        return _failure(
            "No clauses could be retrieved from the submitted agreement. Human review is required.",
            error="retrieval_error: no_chunks",
        )

    context = join_context(retrieved)
    user_prompt = USER_TEMPLATE.format(hypothesis_text=hypothesis_text, context_text=context)

    try:
        r = gw.complete(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0)
    except ModelError as e:
        result = _failure(f"Model provider error: {e}", error=str(e))
        result.retrieved_chunks = retrieved
        return result

    p = parse_structured_output(r.content)
    if p.parse_status == "invalid" or p.predicted_label is None:
        return FinalReviewResult(
            label=None, parse_status=p.parse_status, needs_human_review=True,
            review_reason="The model's response could not be parsed into a valid classification.",
            input_tokens=r.tokens_in, output_tokens=r.tokens_out, latency_ms=r.latency_ms, cost_usd=r.cost_usd,
            model=MODEL, error=p.error_type,
            retrieved_chunks=retrieved,
        )

    # Validate against the exact bounded context shown to the model, not the
    # full NDA. A quote outside the retrieved top five must never pass.
    ev = validate_evidence(context, p.evidence, p.predicted_label)
    needs_review = not ev.is_valid
    reason = None
    if not ev.all_verbatim:
        reason = "One or more quoted evidence passages could not be verified against the NDA text."
    elif not ev.label_evidence_consistent:
        reason = "The evidence returned is inconsistent with the predicted label."

    return FinalReviewResult(
        label=p.predicted_label, evidence=p.evidence, explanation=_EXPLANATION.get(p.predicted_label, ""),
        source_valid=ev.all_verbatim, needs_human_review=needs_review, review_reason=reason,
        parse_status=p.parse_status, input_tokens=r.tokens_in, output_tokens=r.tokens_out,
        latency_ms=r.latency_ms, cost_usd=r.cost_usd, model=MODEL,
        retrieved_chunks=retrieved, sources=_source_chunks(p.evidence, retrieved),
    )


def review_final_document(
    nda_text: str,
    hypotheses: dict[str, str],
    gateway: ModelGateway,
) -> dict[str, FinalReviewResult]:
    """Batch adapter for the UI; one index, one frozen RAG call per requirement."""
    try:
        retriever = FrozenRagRetriever(nda_text)
    except Exception as exc:
        return {
            hypothesis_id: _failure(
                "Relevant clauses could not be indexed. Human review is required.",
                error=f"retrieval_error: {type(exc).__name__}",
            )
            for hypothesis_id in hypotheses
        }

    return {
        hypothesis_id: review_final(
            nda_text,
            hypothesis_text,
            gateway=gateway,
            retriever=retriever,
        )
        for hypothesis_id, hypothesis_text in hypotheses.items()
    }
