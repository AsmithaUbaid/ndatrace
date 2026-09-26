"""
Deterministic structured-output parser for E05/E07 (reconstruction-v2).

Motivation: E05's calibration found that qwen2.5:7b-instruct sometimes emits a well-formed
`{"label": ..., "evidence": [...]}` object followed by trailing free-text commentary (once in
Chinese) -- a real, disclosed long-context instruction-following issue, not truncation and not
malformed JSON. A strict "the entire response must be exactly one JSON object" parser
(evaluation.oracle.parse_oracle_output) correctly rejects this as invalid, which is safe but
throws away an otherwise perfectly good classification. This module adds one narrow, fully
deterministic recovery step on top of that strict behavior -- no LLM repair, no inference of
missing fields, no arbitration between multiple candidate JSON objects.

Two-stage parse, in order:
  A. Strict -- the whole response (after stripping an optional markdown code fence, the same
     tolerance evaluation.oracle.parse_oracle_output already applies) parses as exactly one
     JSON object. parse_status="strict".
  B. Recovery -- only if strict parsing fails. Scan the raw text for balanced top-level `{...}`
     spans (respecting string literals, so braces inside quoted evidence text are not treated
     as structural). If exactly one such span parses as valid JSON AND satisfies the required
     schema (label is one of the three canonical labels, evidence is a list of strings),
     parse_status="recovered". Two or more parseable candidates, or a sole candidate that fails
     schema validation, is NOT recovered -- parse_status="invalid". This is deliberately
     conservative: the brief this module was built against is explicit that ambiguous output
     must never be arbitrated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

VALID_LABELS = {"Entailment", "Contradiction", "NotMentioned"}


@dataclass
class StructuredParseResult:
    raw_response: str
    strict_parse_valid: bool
    recovered_parse_valid: bool
    parse_status: str  # "strict" | "recovered" | "invalid"
    predicted_label: str | None
    evidence: list[str] = field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None


def _strip_code_fence(text: str) -> str:
    """Same tolerance as evaluation.oracle.parse_oracle_output -- a serialization formality
    (markdown fencing), not semantic repair of content."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def _validate_schema(obj: dict) -> tuple[str, list[str]] | None:
    """Returns (label, evidence) if `obj` satisfies the required schema, else None. Required:
    label is one of the three canonical labels; evidence (if present) is a list whose entries
    are all strings. evidence defaults to [] if absent -- E03's compact schema has no evidence
    field at all, and that must still validate."""
    if not isinstance(obj, dict):
        return None
    label = obj.get("label")
    if label not in VALID_LABELS:
        return None
    evidence = obj.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
        return None
    return label, evidence


def _find_balanced_json_objects(text: str) -> list[str]:
    """Finds every substring that is a balanced top-level {...} span, tracking string
    literals (with escape handling) so braces inside quoted evidence text are never treated as
    structural. Returns the raw substrings -- callers still need to json.loads() each one,
    since a balanced-brace span is not guaranteed to be valid JSON (e.g. trailing garbage
    inside, single quotes, etc.)."""
    spans = []
    depth = 0
    start = None
    in_string = False
    escape = False

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    spans.append(text[start:i + 1])
                    start = None

    return spans


def parse_structured_output(raw_response: str) -> StructuredParseResult:
    """The single entry point E05/E07 runners should call instead of
    evaluation.oracle.parse_oracle_output when deterministic recovery is wanted."""
    stripped = _strip_code_fence(raw_response)

    # A. Strict.
    try:
        parsed = json.loads(stripped)
        validated = _validate_schema(parsed)
        if validated is not None:
            label, evidence = validated
            return StructuredParseResult(
                raw_response=raw_response, strict_parse_valid=True,
                recovered_parse_valid=False, parse_status="strict",
                predicted_label=label, evidence=evidence,
            )
    except (json.JSONDecodeError, ValueError):
        pass

    # B. Recovery -- only reached if strict parsing failed or the whole-response object
    # didn't satisfy the schema.
    candidates = _find_balanced_json_objects(raw_response)
    valid_candidates: list[tuple[str, list[str]]] = []
    for span in candidates:
        try:
            obj = json.loads(span)
        except (json.JSONDecodeError, ValueError):
            continue
        validated = _validate_schema(obj)
        if validated is not None:
            valid_candidates.append(validated)

    if len(valid_candidates) == 1:
        label, evidence = valid_candidates[0]
        return StructuredParseResult(
            raw_response=raw_response, strict_parse_valid=False,
            recovered_parse_valid=True, parse_status="recovered",
            predicted_label=label, evidence=evidence,
        )

    if len(valid_candidates) > 1:
        return StructuredParseResult(
            raw_response=raw_response, strict_parse_valid=False,
            recovered_parse_valid=False, parse_status="invalid",
            predicted_label=None, evidence=[],
            error_type="AMBIGUOUS_OUTPUT",
            error_message=f"{len(valid_candidates)} conflicting valid JSON objects found -- "
                          f"refusing to arbitrate between them.",
        )

    return StructuredParseResult(
        raw_response=raw_response, strict_parse_valid=False,
        recovered_parse_valid=False, parse_status="invalid",
        predicted_label=None, evidence=[],
        error_type="NO_VALID_JSON",
        error_message="No complete, schema-valid JSON object could be found in the response.",
    )


def demo() -> None:
    """Smallest runnable self-check -- no network, no model calls."""
    strict = parse_structured_output('{"label": "Entailment", "evidence": ["quote"]}')
    assert strict.parse_status == "strict" and strict.predicted_label == "Entailment"

    trailing = parse_structured_output(
        '{"label": "Contradiction"}\n证据: []\n解释：这是个矛盾。')
    assert trailing.parse_status == "recovered" and trailing.predicted_label == "Contradiction"

    ambiguous = parse_structured_output(
        '{"label": "Entailment"} some text {"label": "Contradiction"}')
    assert ambiguous.parse_status == "invalid" and ambiguous.error_type == "AMBIGUOUS_OUTPUT"

    print("evaluation/structured_output.py self-check OK")


if __name__ == "__main__":
    demo()
