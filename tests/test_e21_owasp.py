"""
E21 -- OWASP LLM Top 10 deterministic regression tests.

Exercises the $0 (STATIC / DETERMINISTIC_RUNTIME) parts of E21 as pytest
assertions so a future change that breaks these safe-failure guarantees is
caught in CI-less local test runs, not only in the one-off experiment
script. Deliberately makes NO hosted model calls -- the hosted-adversarial
parts of E21 (LLM01's RAG-path check, LLM07) are run once by
scripts/run_e21_owasp.py, not re-run here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.structured_output import parse_structured_output
from pipeline.evidence_validator import validate_evidence
from pipeline.frozen_rag import FrozenRagRetriever

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "experiments" / "E21_owasp_llm_top10" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# ---------------------------------------------------------------------------
# LLM05 -- Improper Output Handling
# ---------------------------------------------------------------------------

def test_llm05_malformed_outputs_never_silently_yield_a_label():
    fixtures = _load("output_handling.json")
    unsafe_kinds = {"invalid_json", "two_conflicting_json_objects", "unsupported_label",
                     "wrong_field_type", "evidence_as_scalar", "deeply_nested_json"}
    for case in fixtures["cases"]:
        if case["kind"] not in unsafe_kinds:
            continue
        parsed = parse_structured_output(case["raw_response"])
        assert parsed.predicted_label is None, f"{case['test_id']} should not have produced a label"
        assert parsed.parse_status == "invalid"


def test_llm05_notmentioned_with_evidence_is_flagged_inconsistent():
    fixtures = _load("output_handling.json")
    context = fixtures["context"]
    case = next(c for c in fixtures["cases"] if c["kind"] == "notmentioned_with_nonempty_evidence")
    parsed = parse_structured_output(case["raw_response"])
    assert parsed.predicted_label == "NotMentioned"
    result = validate_evidence(context, parsed.evidence, parsed.predicted_label)
    assert result.label_evidence_consistent is False


def test_llm05_non_source_evidence_is_flagged_hallucinated():
    fixtures = _load("output_handling.json")
    context = fixtures["context"]
    case = next(c for c in fixtures["cases"] if c["kind"] == "non_source_evidence")
    parsed = parse_structured_output(case["raw_response"])
    result = validate_evidence(context, parsed.evidence, parsed.predicted_label)
    assert result.all_verbatim is False
    assert result.hallucinated_quotes


def test_llm05_extra_unexpected_keys_are_dropped_not_propagated():
    fixtures = _load("output_handling.json")
    case = next(c for c in fixtures["cases"] if c["kind"] == "extra_unexpected_keys")
    parsed = parse_structured_output(case["raw_response"])
    assert parsed.predicted_label == "Entailment"
    # StructuredParseResult only ever carries label + evidence -- there is no field an
    # attacker-supplied extra key (e.g. "notes" containing a canary) could land in.
    assert not hasattr(parsed, "notes")
    assert not hasattr(parsed, "internal")


def test_llm05_oversized_evidence_list_still_parses_without_crashing():
    raw = json.dumps({"label": "Entailment", "evidence": ["prior written consent"] * 5000})
    parsed = parse_structured_output(raw)
    assert parsed.predicted_label == "Entailment"
    assert len(parsed.evidence) == 5000  # documents the real gap: no cap enforced here


def test_llm05_html_and_script_content_in_evidence_fails_verbatim_match():
    fixtures = _load("output_handling.json")
    context = fixtures["context"]
    for kind in ("html_in_evidence", "script_tag_in_evidence", "shell_like_string"):
        case = next(c for c in fixtures["cases"] if c["kind"] == kind)
        parsed = parse_structured_output(case["raw_response"])
        result = validate_evidence(context, parsed.evidence, parsed.predicted_label)
        assert result.all_verbatim is False, f"{kind} should not verbatim-match the clean context"


# ---------------------------------------------------------------------------
# LLM04 / LLM08 -- retrieval poisoning
# ---------------------------------------------------------------------------

def test_llm04_genuine_clause_is_never_fully_displaced_from_top5():
    fixtures = _load("data_poisoning.json")
    requirement = fixtures["requirement"]
    genuine = fixtures["genuine_clause"]
    filler = fixtures["filler_clauses"]
    for case in fixtures["poison_cases"]:
        sections = list(filler) + [genuine] + [case["poison_clause"]] * case["repeat_count"]
        nda_text = "\n\n".join(f"Section {i+1}. {s}" for i, s in enumerate(sections))
        retriever = FrozenRagRetriever(nda_text)
        chunks = retriever.retrieve(requirement)
        assert any(genuine[:40] in c.text for c in chunks), (
            f"{case['test_id']}: genuine clause displaced entirely from top-5 -- this would be a "
            f"severe regression beyond the already-disclosed 'poison often ranks #1' finding"
        )


# ---------------------------------------------------------------------------
# LLM10 -- safe local resource tests
# ---------------------------------------------------------------------------

def test_llm10_extremely_long_document_completes_and_returns_bounded_top5():
    long_nda = "Filler clause about governing law and notices. " * 20000
    retriever = FrozenRagRetriever(long_nda)
    chunks = retriever.retrieve("Receiving Party shall not disclose Confidential Information.")
    assert len(chunks) <= 5


def test_llm10_duplicate_clauses_do_not_break_retrieval():
    dup = "Receiving Party shall not disclose Confidential Information to any third party. "
    nda_text = "\n\n".join([dup] * 50 + ["This Agreement is governed by Delaware law."])
    retriever = FrozenRagRetriever(nda_text)
    chunks = retriever.retrieve("Receiving Party shall not disclose Confidential Information.")
    assert len(chunks) <= 5
    assert len(chunks) > 0


# ---------------------------------------------------------------------------
# LLM06 -- excessive agency (static)
# ---------------------------------------------------------------------------

def test_llm06_backend_review_routes_never_report_agent_usage():
    review_py = (ROOT / "backend/routes/review.py").read_text()
    assert '"agent_used": False' in review_py
    assert '"agent_steps": 0' in review_py


def test_llm06_backend_does_not_import_any_agent_module():
    import ast

    for path in (ROOT / "backend").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "agent" not in node.module, f"{path} imports an agent module: {node.module}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "agent" not in alias.name, f"{path} imports an agent module: {alias.name}"


# ---------------------------------------------------------------------------
# LLM02 -- no auth is a documented, not silently-passed, finding
# ---------------------------------------------------------------------------

def test_llm02_results_and_review_endpoints_have_no_auth_dependency():
    """This intentionally asserts the CURRENT (gap) behaviour, so a future auth fix must
    update this test deliberately rather than the gap silently disappearing unnoticed."""
    from fastapi.testclient import TestClient
    from backend.app import app

    with TestClient(app) as client:
        resp = client.get("/results")
    assert resp.status_code == 200  # no 401/403 -- documents the LLM02 gap, not a desired end state


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
