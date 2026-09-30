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


# ======================= E14: runtime validator v2 (aligned to frozen evidence_evaluator_v2) =======================
import pytest

from evaluation.evidence_matching import is_source_valid
from pipeline.evidence_validator import RUNTIME_EVIDENCE_VALIDATOR_V1, RUNTIME_EVIDENCE_VALIDATOR_V2, CURRENT_RUNTIME_EVIDENCE_VALIDATOR

SRC = "Recipient shall not disclose Confidential Information to any third party within 30 days."

# (name, source, quote, expected_valid)  -- expected == frozen evaluator_v2 source validity
CORPUS = [
    ("exact", SRC, "Recipient shall not disclose Confidential Information", True),
    ("line_break", "Recipient shall not disclose\nConfidential Information to any third party within 30 days.", "Recipient shall not disclose Confidential Information", True),
    ("multi_space", "Recipient  shall   not disclose Confidential Information", "Recipient shall not disclose Confidential Information", True),
    ("tab", "Recipient shall not\tdisclose Confidential Information", "Recipient shall not disclose Confidential Information", True),
    ("crlf", "Recipient shall not disclose\r\nConfidential Information", "Recipient shall not disclose Confidential Information", True),
    ("nbsp", "Recipient shall not disclose Confidential Information", "Recipient shall not disclose Confidential Information", True),
    ("quote_has_nbsp", SRC, "Recipient shall not disclose", True),
    ("zwsp", "Recipient shall not dis​close Confidential Information", "Recipient shall not disclose Confidential Information", True),
    ("zwnj", "Recipient shall not dis‌close Confidential Information", "Recipient shall not disclose Confidential Information", True),
    ("zwj", "Recipient shall not dis‍close Confidential Information", "Recipient shall not disclose Confidential Information", True),
    ("word_joiner", "Recipient shall not dis⁠close Confidential Information", "Recipient shall not disclose Confidential Information", True),
    ("bom", "Recipient shall not dis﻿close Confidential Information", "Recipient shall not disclose Confidential Information", True),
    ("nfc", "Café rules apply", "Café rules apply", True),
    # negatives: semantics must never be tolerated
    ("negation_changed", "Recipient shall not disclose Confidential Information.", "Recipient shall disclose Confidential Information.", False),
    ("number_changed", "within 30 days", "within 60 days", False),
    ("modal_changed", "Recipient may disclose", "Recipient shall disclose", False),
    ("party_changed", SRC, "Discloser shall not disclose Confidential Information", False),
    ("legal_term_changed", SRC, "Recipient shall not disclose Trade Secrets", False),
    ("missing_word", SRC, "Recipient shall disclose Confidential Information", False),
    ("paraphrase", SRC, "The recipient must keep information secret", False),
    ("case_only", SRC, "recipient shall not disclose", False),
    # intentional non-coverage (frozen v2 rejects)
    ("curly_quote", "Party’s obligations apply", "Party's obligations apply", False),
    ("ellipsis_join", SRC, "Recipient shall not ... within 30 days.", False),
    ("empty", SRC, "", False),
]


@pytest.mark.parametrize("name,source,quote,expected", CORPUS, ids=[c[0] for c in CORPUS])
def test_runtime_v2_matches_evaluator_v2_on_corpus(name, source, quote, expected):
    assert (quote in validate_evidence(source, [quote], "Entailment").verbatim_quotes) == expected
    assert is_source_valid(quote, source) == expected  # differential: evaluator agrees


def test_current_version_is_v2_and_v1_still_selectable():
    assert CURRENT_RUNTIME_EVIDENCE_VALIDATOR == RUNTIME_EVIDENCE_VALIDATOR_V2
    src = "a\nb c"
    assert validate_evidence(src, ["a b"], "Entailment", RUNTIME_EVIDENCE_VALIDATOR_V1).hallucinated_quotes == ["a b"]
    assert validate_evidence(src, ["a b"], "Entailment").verbatim_quotes == ["a b"]


def test_v1_and_v2_identical_when_exact():
    a = validate_evidence(SRC, ["within 30 days."], "Entailment", RUNTIME_EVIDENCE_VALIDATOR_V1)
    b = validate_evidence(SRC, ["within 30 days."], "Entailment")
    assert (a.verbatim_quotes, a.hallucinated_quotes, a.spans) == (b.verbatim_quotes, b.hallucinated_quotes, b.spans) and b.normalized_quotes == []


def test_normalized_match_recovers_original_span_and_is_flagged():
    src = "X. Recipient shall\nnot disclose it. Y."
    r = validate_evidence(src, ["Recipient shall not disclose it."], "Entailment")
    s, e = r.spans["Recipient shall not disclose it."]
    assert src[s:e] == "Recipient shall\nnot disclose it." and r.normalized_quotes == ["Recipient shall not disclose it."]


def test_multiple_occurrences_first_wins_and_valid():
    src = "dup\nclause. other. dup  clause."
    r = validate_evidence(src, ["dup clause."], "Entailment")
    assert r.all_verbatim and r.spans["dup clause."][0] == 0


def test_exact_preferred_over_normalized_occurrence():
    src = "dup\nclause. later dup clause."
    r = validate_evidence(src, ["dup clause."], "Entailment")
    assert r.spans["dup clause."][0] == src.rindex("dup clause.") and r.normalized_quotes == []


def test_label_consistency_unchanged_by_normalization():
    src = "Recipient shall\nnot disclose."
    assert not validate_evidence(src, ["Recipient shall not disclose."], "NotMentioned").label_evidence_consistent
    assert validate_evidence(src, ["Recipient shall not disclose."], "Contradiction").is_valid
