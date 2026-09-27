"""
Final frozen product pipeline (E19) - the reconstruction-v2 candidate that
completed the one-shot TEST evaluation (E17/E17B): openai/gpt-5-mini + the
frozen GPT-P0 prompt + FULL NDA context + the shared structured-output parser
+ the runtime evidence-source validator (v2). No retrieval, no agent, no
routing - this is the exact architecture E17/E17B measured, wired up for
live single-request use instead of a benchmark harness.

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
from pipeline.evidence_validator import validate_evidence
from pipeline.model_gateway import ModelError, ModelGateway

MODEL = "openai/gpt-5-mini"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts/reconstruction_v2/gpt_p0.txt"
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"  # frozen, identical to E13/E15/E16/E17/E17B

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


def review_final(nda_text: str, hypothesis_text: str, gateway: ModelGateway | None = None) -> FinalReviewResult:
    """One requirement, one NDA, the frozen final architecture. `gateway` is
    injectable for tests; production callers should pass none and get the
    real ModelGateway(model=MODEL)."""
    gw = gateway or ModelGateway(model=MODEL)
    system_prompt = PROMPT_PATH.read_text()
    user_prompt = USER_TEMPLATE.format(hypothesis_text=hypothesis_text, context_text=nda_text)

    try:
        r = gw.complete(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0)
    except ModelError as e:
        return FinalReviewResult(label=None, needs_human_review=True, review_reason=f"Model provider error: {e}", model=MODEL, error=str(e))

    p = parse_structured_output(r.content)
    if p.parse_status == "invalid" or p.predicted_label is None:
        return FinalReviewResult(
            label=None, parse_status=p.parse_status, needs_human_review=True,
            review_reason="The model's response could not be parsed into a valid classification.",
            input_tokens=r.tokens_in, output_tokens=r.tokens_out, latency_ms=r.latency_ms, cost_usd=r.cost_usd,
            model=MODEL, error=p.error_type,
        )

    ev = validate_evidence(nda_text, p.evidence, p.predicted_label)
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
    )
