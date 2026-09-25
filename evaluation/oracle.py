"""
E01 Oracle — reusable, provider-agnostic logic (reconstruction-v2).

Pure functions: build the model-visible input for one Oracle case, and parse/validate the
model's compact JSON response. No network calls, no model calls. Used by both
scripts/run_e01_oracle.py (the real runner, Stage B) and the E01 analysis notebook, so the
input-construction and parsing rules exist in exactly one place.

CRITICAL INVARIANT: the model must never see `gold_label`, and every case — regardless of
label — uses EXACTLY THE SAME evidence field/structure. A NotMentioned case renders as an
empty evidence list (`Evidence: []`), never as an explanatory phrase — any such phrase (e.g.
"no supporting evidence was identified") is itself a label-revealing shortcut a model could
learn to key off, not neutral framing. See build_oracle_user_message().

KNOWN INTERPRETIVE LIMITATION (documented, not hidden): NotMentioned Oracle performance is
partly STRUCTURALLY easier than Entailment/Contradiction, because ContractNLI provides no
annotated evidence for NotMentioned by definition (E00, docs/evaluation_protocol.md Part 1
section 10) — every NotMentioned case renders with an empty evidence list, which is itself a
distinguishing structural signal the model can use, separate from actually reasoning about
requirement content. NotMentioned Oracle recall must be interpreted separately from
Entailment/Contradiction reasoning performance, not folded into one combined "Oracle accuracy"
number as if all three labels were equally hard to reach from the rendered input alone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

VALID_LABELS = {"Entailment", "Contradiction", "NotMentioned"}

# Substrings that must never appear in model-visible text — each one either names the harness
# concept a model shouldn't see (gold/annotation), leaks the answer outright (NotMentioned,
# expected label), or is an explanatory-phrase shortcut a model could key off instead of
# reasoning (no supporting evidence). Checked by test_oracle.py's leakage regression test.
FORBIDDEN_SUBSTRINGS = (
    "gold", "NotMentioned", "no supporting evidence", "annotation", "expected label",
)


def build_oracle_user_message(case: dict[str, Any]) -> str:
    """
    Build the model-visible user message for one TRAIN_ORACLE_v1 case.

    `case` is one record from TRAIN_ORACLE_v1.json — it DOES contain `gold_label` (the
    harness/manifest may know it), but this function never reads or emits that field.

    Evidence renders as a JSON list, identically structured for every label: the gold
    evidence text as a single-element list for Entailment/Contradiction, or an empty list for
    NotMentioned (empty by construction, E00 §10) — never an explanatory phrase. This is a
    deliberate correction: an earlier version of this function rendered NotMentioned cases
    with a "no supporting evidence was identified" sentence, which — even without using the
    word "NotMentioned" — was itself a label-revealing shortcut (a model could learn "sentence
    present -> not NotMentioned" without reasoning about the requirement at all). Structural
    parity across all three labels removes that shortcut.
    """
    requirement = case["hypothesis_text"]
    evidence_text = case.get("gold_evidence_text", "")
    evidence_list = [evidence_text] if evidence_text else []

    return f"Requirement: {requirement}\n\nEvidence: {json.dumps(evidence_list)}"


@dataclass
class OracleParseResult:
    label: str | None
    parse_valid: bool
    raw_output: str


def parse_oracle_output(raw_output: str) -> OracleParseResult:
    """
    Parse a model's compact Oracle response. Strict: must be a JSON object with exactly a
    "label" field whose value is one of the three canonical labels. Anything else —
    malformed JSON, missing field, extra prose, an unrecognized label string — is
    parse_valid=False. No deterministic repair/inference of the intended label from
    malformed text (reconstruction brief section 16) — that policy was not frozen before
    this run, so it is not applied here.
    """
    text = raw_output.strip()
    # Tolerate a model wrapping the JSON in a markdown code fence — a serialization
    # formality, not a semantic repair of the label itself.
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return OracleParseResult(label=None, parse_valid=False, raw_output=raw_output)

    if not isinstance(parsed, dict):
        return OracleParseResult(label=None, parse_valid=False, raw_output=raw_output)

    label = parsed.get("label")
    if label not in VALID_LABELS:
        return OracleParseResult(label=None, parse_valid=False, raw_output=raw_output)

    return OracleParseResult(label=label, parse_valid=True, raw_output=raw_output)


def build_result_record(
    run_id: str,
    experiment_id: str,
    case: dict[str, Any],
    predicted_label: str | None,
    parse_valid: bool,
    input_tokens: int | None,
    output_tokens: int | None,
    latency_ms: float | None,
    provider: str,
    model: str,
    prompt_version: str,
    raw_output: str,
    error: str | None = None,
    retry_count: int = 0,
    error_type: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """
    One structured record per model x case, per reconstruction brief section 15.

    `retry_count`/`error_type`/`error_message` were added after E01's first run (the original
    schema only had a single `error` string) — `error_type` distinguishes MODEL ERROR
    (provider timeout/local runtime failure) from PARSE ERROR (schema violation) per the
    reconstruction brief's failure-policy split; `error_message` carries the human-readable
    detail. `retry_count` records how many transient-failure retries ModelGateway performed
    before this result (0 = succeeded on the first attempt).
    """
    return {
        "run_id": run_id,
        "experiment_id": experiment_id,
        "case_id": case["case_id"],
        "document_id": case["document_id"],
        "hypothesis_id": case["hypothesis_id"],
        "gold_label": case["gold_label"],
        "predicted_label": predicted_label,
        "parse_valid": parse_valid,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "raw_output": raw_output,
        "error": error,
        "retry_count": retry_count,
        "error_type": error_type,
        "error_message": error_message,
    }


def demo() -> None:
    """Smallest runnable self-check — no network, no model calls."""
    ec_case = {
        "case_id": "train::1::nda-1", "document_id": 1, "hypothesis_id": "nda-1",
        "hypothesis_text": "Some obligation survives termination.",
        "gold_label": "Entailment", "gold_evidence_text": "This obligation survives termination.",
    }
    msg = build_oracle_user_message(ec_case)
    assert "gold_label" not in msg
    assert "Entailment" not in msg  # the label must never leak into the model-visible text
    assert "This obligation survives termination." in msg
    assert '["This obligation survives termination."]' in msg  # evidence rendered as a JSON list

    nm_case = {
        "case_id": "train::2::nda-2", "document_id": 2, "hypothesis_id": "nda-2",
        "hypothesis_text": "Some other requirement.",
        "gold_label": "NotMentioned", "gold_evidence_text": "",
    }
    nm_msg = build_oracle_user_message(nm_case)
    assert nm_msg.endswith("Evidence: []")  # same structure, empty list -- no explanatory phrase
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden.lower() not in nm_msg.lower(), f"leaked: {forbidden!r}"

    ok = parse_oracle_output('{"label": "Contradiction"}')
    assert ok.parse_valid and ok.label == "Contradiction"

    fenced = parse_oracle_output('```json\n{"label": "Entailment"}\n```')
    assert fenced.parse_valid and fenced.label == "Entailment"

    bad_label = parse_oracle_output('{"label": "Maybe"}')
    assert not bad_label.parse_valid

    malformed = parse_oracle_output("The answer is Entailment.")
    assert not malformed.parse_valid

    print("evaluation/oracle.py self-check OK")


if __name__ == "__main__":
    demo()
