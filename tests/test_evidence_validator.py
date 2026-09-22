"""Unit tests for pipeline/evidence_validator.py (WBS T025)."""

from __future__ import annotations

from pipeline.evidence_validator import validate_evidence


def test_verbatim_quote_passes():
    context = "Receiving Party shall not disclose Confidential Information to any third party."
    result = validate_evidence(context, ["Receiving Party shall not disclose Confidential Information"], "Entailment")
    assert result.is_valid
    assert result.all_verbatim
    assert result.hallucinated_quotes == []


def test_paraphrased_quote_is_flagged_as_hallucinated():
    context = "Receiving Party shall not disclose Confidential Information to any third party."
    result = validate_evidence(context, ["Receiving Party must keep information secret"], "Entailment")
    assert not result.is_valid
    assert not result.all_verbatim
    assert result.hallucinated_quotes == ["Receiving Party must keep information secret"]


def test_fabricated_quote_not_in_context_is_flagged():
    context = "Receiving Party shall not disclose Confidential Information."
    result = validate_evidence(context, ["This clause does not exist anywhere"], "Entailment")
    assert not result.is_valid
    assert result.hallucinated_quotes == ["This clause does not exist anywhere"]


def test_mixed_verbatim_and_hallucinated_quotes_separates_correctly():
    context = "Clause A states X. Clause B states Y."
    result = validate_evidence(context, ["Clause A states X", "Clause C states Z (fabricated)"], "Entailment")
    assert not result.is_valid
    assert result.verbatim_quotes == ["Clause A states X"]
    assert result.hallucinated_quotes == ["Clause C states Z (fabricated)"]


def test_not_mentioned_with_empty_evidence_is_consistent():
    result = validate_evidence("Some NDA text.", [], "NotMentioned")
    assert result.is_valid
    assert result.label_evidence_consistent


def test_not_mentioned_with_nonempty_evidence_is_inconsistent():
    context = "Receiving Party shall not disclose Confidential Information."
    result = validate_evidence(context, ["Receiving Party shall not disclose Confidential Information"], "NotMentioned")
    assert not result.is_valid
    assert not result.label_evidence_consistent
    # the quote itself is still verbatim - the inconsistency is about the label/evidence pairing, not the quote
    assert result.all_verbatim


def test_empty_evidence_list_on_entailment_has_no_hallucinations():
    result = validate_evidence("Some NDA text.", [], "Entailment")
    assert result.all_verbatim
    assert result.hallucinated_quotes == []


def test_empty_string_quote_is_hallucinated_not_verbatim():
    context = "Any non-empty context."
    result = validate_evidence(context, [""], "Entailment")
    assert not result.all_verbatim
    assert result.hallucinated_quotes == [""]


def test_quote_must_match_case_and_whitespace_exactly():
    context = "Receiving Party shall not disclose Confidential Information."
    # Different case - not an exact substring, so flagged (verbatim means verbatim).
    result = validate_evidence(context, ["receiving party shall not disclose confidential information"], "Entailment")
    assert not result.all_verbatim
