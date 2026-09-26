"""Unit tests for evaluation.evidence_matching (evidence_evaluator_v1 / v2). Fixtures only; no model calls, no TEST data."""
import random
import sys
from pathlib import Path

import pytest

from evaluation.evidence_matching import (
    EVIDENCE_EVALUATOR_V1, EVIDENCE_EVALUATOR_V2, TAU_EVIDENCE, evidence_to_span_indices, evidence_to_span_indices_v1, find_evidence_matches,
    is_source_valid, joint_success, normalize_evidence_text,
)

SRC = "Recipient shall not disclose Confidential Information to any third party within 30 days."


def spans(text):  # one annotated span covering the whole text
    return [[0, len(text)]]


def match_v2(quote, source=SRC):
    return find_evidence_matches(quote, [source], [[0, len(source)]], EVIDENCE_EVALUATOR_V2)


# ---------------- exact match unchanged
def test_exact_match_unchanged_and_method_exact():
    m = match_v2("Recipient shall not disclose")
    assert len(m) == 1 and m[0].method == "exact" and (m[0].start, m[0].end) == (0, len("Recipient shall not disclose"))


def test_v1_and_v2_identical_when_exact_matches():
    ev = ["Recipient shall not disclose", "within 30 days."]
    assert evidence_to_span_indices(ev, [SRC], [[0, len(SRC)]], [[0, 30], [50, len(SRC)]]) == evidence_to_span_indices_v1(ev, [SRC], [[0, len(SRC)]], [[0, 30], [50, len(SRC)]])


# ---------------- whitespace variants
@pytest.mark.parametrize("source", [
    "Recipient  shall   not disclose Confidential Information to any third party within 30 days.",       # multiple spaces
    "Recipient shall not disclose\nConfidential Information to any third party within 30 days.",          # line break
    "Recipient shall not\tdisclose Confidential Information to any third party within 30 days.",          # tab
    "Recipient shall not disclose\r\nConfidential Information to any third party within 30 days.",        # CRLF
    "Recipient shall not disclose Confidential Information to any third party within 30 days.",     # NBSP
    "Recipient shall not disclose Confidential Information to any third party within 30 days.",     # thin space
])
def test_whitespace_variants_match_only_in_v2(source):
    assert find_evidence_matches(SRC, [source], [[0, len(source)]], EVIDENCE_EVALUATOR_V1) == []
    m = match_v2(SRC, source)
    assert len(m) == 1 and m[0].method == "normalized"
    assert (m[0].start, m[0].end) == (0, len(source))                      # original span recovered exactly


def test_quote_side_whitespace_merging_matches():
    source = "Recipient shall not disclose\nConfidential Information."
    assert match_v2("Recipient shall not disclose Confidential Information.", source)[0].method == "normalized"
    assert match_v2("  Recipient shall not disclose\n\n  Confidential Information.  ", source)[0].method == "normalized"


# ---------------- zero-width characters
@pytest.mark.parametrize("zw", ["​", "‌", "‍", "⁠", "﻿"])
def test_zero_width_in_source_matches(zw):
    source = f"Recipient shall not disclose{zw} Confidential Information."
    assert find_evidence_matches("Recipient shall not disclose Confidential Information.", [source], [[0, len(source)]], EVIDENCE_EVALUATOR_V1) == []
    assert match_v2("Recipient shall not disclose Confidential Information.", source)[0].method == "normalized"


def test_zero_width_runs_between_spaces_collapse_like_e13_case():
    source = "information, whether visual, written, electronic or ​ ​ ​ oral, (including"
    q = "whether visual, written, electronic or oral, (including"
    m = match_v2(q, source)
    assert len(m) == 1 and source[m[0].start:m[0].end] == source[source.index("whether"):]


# ---------------- unicode
def test_nfc_equivalent_representation_matches():
    composed, decomposed = "café terms apply", "café terms apply"
    assert find_evidence_matches(composed, [decomposed], [[0, len(decomposed)]], EVIDENCE_EVALUATOR_V1) == []
    m = find_evidence_matches(composed, [decomposed], [[0, len(decomposed)]], EVIDENCE_EVALUATOR_V2)
    assert len(m) == 1 and (m[0].start, m[0].end) == (0, len(decomposed))


def test_nfkc_only_differences_are_NOT_matched():
    # compatibility characters (ligature, superscript) are deliberately outside v2
    assert match_v2("ofﬁce", "office") == [] and match_v2("clause 2", "clause ²") == []


# ---------------- negative controls: formatting tolerance is not semantic tolerance
@pytest.mark.parametrize("quote", [
    "Recipient shall disclose Confidential Information",                    # removed negation
    "Recipient shall not not disclose Confidential Information",            # added negation
    "Recipient shall not disclose Confidential Information to any party",   # missing word (third)
    "Recipient shall not disclose Confidential Data to any third party",    # changed legal term
    "Recipient shall not disclose Confidential Information to any third party within 60 days",  # changed number
    "Discloser shall not disclose Confidential Information",                # changed party
    "The Recipient must never reveal Confidential Information to anyone",   # paraphrase
    "recipient shall not disclose confidential information",                # case change (case is NOT normalized)
    "Recipient shall not disclose Confidential Information “to” any third party",  # inserted punctuation
])
def test_semantic_changes_do_not_match(quote):
    source = "Recipient shall not disclose Confidential Information to any third party within 30 days."
    assert match_v2(quote, source) == []
    assert not is_source_valid(quote, source)


def test_adversarial_spec_examples():
    assert match_v2("Recipient shall disclose Confidential Information.", "Recipient shall not disclose Confidential Information.") == []
    assert match_v2("within 60 days", "within 30 days") == []
    assert match_v2("shall disclose", "may disclose") == []


def test_whitespace_normalization_does_not_bridge_word_boundaries():
    assert match_v2("foo bar", "foobar") == [] and match_v2("foobar", "foo bar") == []


def test_curly_vs_straight_quotes_not_unified_by_v2():
    assert match_v2('"Confidential Information" means', "“Confidential Information” means") == []


def test_ellipsis_joined_quotes_not_segmented_by_v2():
    assert match_v2("Recipient shall not ... within 30 days", SRC) == []


# ---------------- multiple occurrences
def test_multiple_occurrences_exact_first_then_leftmost_and_diagnostic():
    loose, tight = "The  Recipient shall keep it secret.", "The Recipient shall keep it secret."
    source = loose + " Other text. " + tight
    m = find_evidence_matches(tight, [source], [[0, len(source)]], EVIDENCE_EVALUATOR_V2)
    # exact-first: the exactly-formatted (second) occurrence matches exactly, so the normalized fallback (which would hit the first) is not used
    assert len(m) == 1 and m[0].method == "exact" and m[0].start == len(loose) + len(" Other text. ") and m[0].n_occurrences == 1
    # two normalized-only occurrences: leftmost is used and the ambiguity is reported
    src2 = loose + " X. " + loose
    m2 = find_evidence_matches(tight, [src2], [[0, len(src2)]], EVIDENCE_EVALUATOR_V2)
    assert len(m2) == 1 and m2[0].method == "normalized" and m2[0].start == 0 and m2[0].n_occurrences == 2


def test_multiple_occurrences_gold_on_second_only_uses_first_occurrence_like_v1():
    a = "Recipient may retain one copy."
    source = a + " Filler filler. " + a
    doc_spans = [[len(a) + 16, len(source)]]        # gold = second occurrence only
    got = evidence_to_span_indices([a], [source], [[0, len(source)]], doc_spans)
    assert got == evidence_to_span_indices_v1([a], [source], [[0, len(source)]], doc_spans) == []   # v1 policy preserved: leftmost occurrence, gold-blind


def test_source_valid_if_any_genuine_occurrence():
    assert is_source_valid("a  b", "x a b y") and not is_source_valid("a  c", "x a b y") and not is_source_valid("", "x")


# ---------------- offsets and gold overlap in original coordinates
def test_recovered_span_maps_to_original_offsets_and_gold_overlap():
    doc = "Preamble. " + "Recipient  shall not\ndisclose Confidential Information." + " Trailer."
    s = doc.index("Recipient"); e = doc.index(" Trailer.")
    gold_spans = [[s, e]]
    got = evidence_to_span_indices(["Recipient shall not disclose Confidential Information."], [doc], [[0, len(doc)]], gold_spans)
    assert got == [0]
    m = find_evidence_matches("Recipient shall not disclose Confidential Information.", [doc], [[0, len(doc)]])[0]
    assert doc[m.start:m.end] == doc[s:e]


def test_chunk_offsets_shift_recovered_span_into_document_coordinates():
    chunk = "Alpha.\nRecipient shall not\ndisclose data."
    base = 1000
    span_start = base + chunk.index("Recipient")
    got = evidence_to_span_indices(["Recipient shall not disclose data."], [chunk], [[base, base + len(chunk)]], [[span_start, base + len(chunk)], [0, 10]])
    assert got == [0]


def test_leading_trailing_whitespace_in_quote_trimmed():
    assert match_v2("\n  Recipient shall not disclose \t")[0].start == 0


# ---------------- backward compatibility with historical duplicated implementations
def test_v1_equals_historical_script_implementation_on_random_data():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import analyze_e08b_stronger_model as old
    rng = random.Random(7)
    words = ["Recipient", "shall", "not", "disclose", "Confidential", "Information", "third", "party", "days", "30", "may"]
    for _ in range(200):
        text = " ".join(rng.choice(words) for _ in range(60)); base = rng.randrange(0, 500)
        ev = [" ".join(text.split()[i:i + 6]) for i in rng.sample(range(50), 3)] + ["not in text at all"]
        spans_ = [[base + rng.randrange(0, 100), base + rng.randrange(100, 300)] for _ in range(5)]
        assert old.evidence_to_span_indices(ev, [text], [[base, base + len(text)]], spans_) == evidence_to_span_indices_v1(ev, [text], [[base, base + len(text)]], spans_)
        assert set(evidence_to_span_indices_v1(ev, [text], [[base, base + len(text)]], spans_)) <= set(evidence_to_span_indices(ev, [text], [[base, base + len(text)]], spans_))


# ---------------- joint semantics unchanged
def test_joint_success_matches_canonical_metric_semantics():
    from evaluation.metrics import joint_label_evidence_correctness
    from evaluation.schemas import GoldCase, Label, Prediction
    import inspect
    assert inspect.signature(joint_label_evidence_correctness).parameters["tau_evidence"].default == TAU_EVIDENCE == 0.5
    cases = [("Entailment", "Entailment", [1, 2], [1]), ("Entailment", "Entailment", [1, 2], [3]), ("Contradiction", "Entailment", [1], [1]),
             ("NotMentioned", "NotMentioned", [], []), ("NotMentioned", "NotMentioned", [], [4]), ("Entailment", "Entailment", [], [1]),
             ("Entailment", "Entailment", [1, 2, 3, 4], [1, 2])]
    for i, (g, p, gs, ps) in enumerate(cases):
        want = joint_label_evidence_correctness(
            [Prediction(case_id=f"c{i}", doc_id="1", hypothesis_id="nda-1", predicted_label=Label(p), retrieved_span_indices=ps)],
            [GoldCase(case_id=f"c{i}", doc_id="1", hypothesis_id="nda-1", gold_label=Label(g), gold_span_indices=gs)]) == 1.0
        assert joint_success(g, p, gs, ps) == want, (g, p, gs, ps)


def test_notmentioned_rule_unchanged_evidence_claimed_fails():
    assert joint_success("NotMentioned", "NotMentioned", [], []) and not joint_success("NotMentioned", "NotMentioned", [], [3])


def test_normalization_spec_examples():
    assert normalize_evidence_text("  a  b\t\tc\r\nd​ e ​") == "a b c d e"
    assert normalize_evidence_text("A b") == "A b"       # case preserved
