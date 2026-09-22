"""
Classifier (WBS T011, T012) - builds the classification prompt, calls the
model gateway, and parses the structured JSON output into a
ClassificationResult.

Takes nda_text as plain context, not a template slot: the NDA text is
concatenated into the user message directly (never passed through
str.format on the instruction template), since real NDA text can contain
literal curly braces (defined-term lists, cross-references) that would
break Python's str.format if the whole prompt were templated as one string.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pipeline.logging_config import get_logger
from pipeline.model_gateway import ModelGateway

logger = get_logger("classifier")

VALID_LABELS = {"Entailment", "Contradiction", "NotMentioned"}
PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    evidence: list[str]
    explanation: str
    valid_json: bool
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    raw_output: str


def load_prompt_template(version: str = "v1") -> str:
    path = PROMPT_DIR / f"classify_{version}.txt"
    return path.read_text()


def _build_user_message(nda_text: str, hypothesis: str) -> str:
    return (
        f'NDA text:\n"""\n{nda_text}\n"""\n\n'
        f'Requirement to classify:\n"{hypothesis}"'
    )


def _parse_response(content: str) -> dict | None:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _fallback_result(response, reason: str) -> ClassificationResult:
    """Safe default when structured output can't be recovered - never
    silently claim Entailment/Contradiction on a parse failure."""
    logger.error(f"Classifier: {reason}")
    return ClassificationResult(
        label="NotMentioned",
        confidence=0.0,
        evidence=[],
        explanation=reason,
        valid_json=False,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        latency_ms=response.latency_ms,
        raw_output=response.content,
    )


def classify(
    nda_text: str,
    hypothesis: str,
    gateway: ModelGateway,
    prompt_version: str = "v1",
) -> ClassificationResult:
    """
    Classify one (NDA, hypothesis) pair.

    `nda_text` is whatever context the caller wants classified against -
    the full document (full-context baseline), gold evidence spans
    (Oracle), or retrieved chunks (RAG). This function has no opinion on
    where the text came from.
    """
    system_prompt = load_prompt_template(prompt_version)
    user_message = _build_user_message(nda_text, hypothesis)

    response = gateway.complete(
        system_prompt=system_prompt,
        user_prompt=user_message,
        response_format={"type": "json_object"},
    )

    data = _parse_response(response.content)

    if data is None:
        logger.warning("Classifier: invalid JSON on first attempt, retrying with explicit instruction")
        retry_message = user_message + (
            "\n\nYour previous response was not valid JSON. "
            "Respond with ONLY the JSON object, nothing else."
        )
        response = gateway.complete(
            system_prompt=system_prompt,
            user_prompt=retry_message,
            response_format={"type": "json_object"},
        )
        data = _parse_response(response.content)

    if data is None:
        return _fallback_result(response, "Model did not return valid JSON after retry.")

    label = data.get("label")
    if label not in VALID_LABELS:
        return _fallback_result(response, f"Model returned invalid label: {label!r}")

    return ClassificationResult(
        label=label,
        confidence=float(data.get("confidence", 0.5)),
        evidence=list(data.get("evidence", [])),
        explanation=str(data.get("explanation", "")),
        valid_json=True,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        latency_ms=response.latency_ms,
        raw_output=response.content,
    )
