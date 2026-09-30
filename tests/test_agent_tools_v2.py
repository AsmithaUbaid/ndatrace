"""
Tests for pipeline/agent_tools_v2.py (E10/E11, reconstruction-v2). No model calls, no network --
purely deterministic tool logic. Does not import or exercise pipeline/agent_tools.py (historical,
untouched).
"""

from __future__ import annotations

from pipeline.agent_tools_v2 import (
    CANDIDATE_POOL_SIZE,
    MAX_CANDIDATE_RESULTS,
    MAX_RESULT_TEXT_CHARS,
    follow_cross_reference,
    get_definition,
    get_more_candidates,
)

FILLER = (" Additional recital language padding this individual clause out well past the two "
          "hundred fifty six token chunk budget so it cannot be merged with any neighboring "
          "clause during chunking.") * 6

DOC = (
    f"1. Definitions.{FILLER}\n\n"
    f'"Confidential Information" means any and all information disclosed by either '
    f"party.{FILLER}\n\n"
    f"4(b) The Receiving Party shall not copy Confidential Information without "
    f"consent.{FILLER}\n\n"
    f"7. This Agreement shall be governed by the laws of Delaware.{FILLER}\n"
)


# --- follow_cross_reference ---

def test_follow_cross_reference_exact_section_match():
    r = follow_cross_reference(DOC, "Section 4(b)")
    assert r.success
    assert r.tool == "follow_cross_reference"
    assert "Receiving Party" in r.results[0]["text"]


def test_follow_cross_reference_paragraph_match():
    r = follow_cross_reference(DOC, "(b)")
    assert r.success
    assert "Receiving Party" in r.results[0]["text"]


def test_follow_cross_reference_unresolved():
    r = follow_cross_reference(DOC, "Article 99")
    assert not r.success and r.error == "NOT_FOUND"


def test_follow_cross_reference_ambiguous():
    doc_two_matches = DOC + f"\n\n4(b) A second, conflicting clause 4(b).{FILLER}\n"
    r = follow_cross_reference(doc_two_matches, "Section 4(b)")
    assert not r.success and r.error == "AMBIGUOUS_REFERENCE"
    assert len(r.results) >= 2


def test_follow_cross_reference_malformed():
    r = follow_cross_reference(DOC, "???")
    assert not r.success and r.error == "MALFORMED_REFERENCE"


def test_follow_cross_reference_empty():
    r = follow_cross_reference(DOC, "")
    assert not r.success and r.error == "EMPTY_REFERENCE"


def test_follow_cross_reference_output_truncation():
    huge_doc = f"9(z) Start.{' word' * 1000}{FILLER}\n\n" + DOC
    r = follow_cross_reference(huge_doc, "Section 9(z)")
    assert r.success
    assert len(r.results[0]["text"]) <= MAX_RESULT_TEXT_CHARS


def test_follow_cross_reference_delegates_definition_pattern():
    r = follow_cross_reference(DOC, "the definition of Confidential Information")
    assert r.success
    assert "means" in r.results[0]["text"]


# --- get_definition (internal helper, still directly testable) ---

def test_get_definition_exact_term():
    r = get_definition(DOC, "Confidential Information")
    assert r.success and "means any and all information" in r.results[0]["text"]


def test_get_definition_case_variation():
    r = get_definition(DOC, "confidential information")
    assert r.success


def test_get_definition_quoted_term():
    r = get_definition(DOC, '"Confidential Information"')
    assert r.success


def test_get_definition_absent_term():
    r = get_definition(DOC, "Nonexistent Term")
    assert not r.success and r.error == "NOT_FOUND"


def test_get_definition_ambiguous_multiple():
    doc_two_defs = DOC + f'\n\n"Confidential Information" means something else entirely.{FILLER}\n'
    r = get_definition(doc_two_defs, "Confidential Information")
    assert not r.success and r.error == "AMBIGUOUS_DEFINITION"


def test_get_definition_output_cap():
    huge_term_doc = f'"Widget" means {"word " * 500}.{FILLER}\n\n' + DOC
    r = get_definition(huge_term_doc, "Widget")
    assert r.success
    assert len(r.results[0]["text"]) <= MAX_RESULT_TEXT_CHARS


def test_get_definition_empty_term():
    r = get_definition(DOC, "")
    assert not r.success and r.error == "EMPTY_TERM"


# --- get_more_candidates ---

def _bigger_doc(n_clauses: int) -> str:
    return "\n\n".join(
        f"{i}. Clause number {i} discusses confidential information obligations.{FILLER}"
        for i in range(1, n_clauses + 1)
    )


def test_get_more_candidates_rank_progression_no_duplicates():
    big_doc = _bigger_doc(12)
    r1 = get_more_candidates(big_doc, "confidential information obligations", already_revealed_count=5)
    assert r1.success
    chunk_ids_1 = {r["chunk_id"] for r in r1.results}

    r2 = get_more_candidates(big_doc, "confidential information obligations",
                              already_revealed_count=5 + len(r1.results))
    if r2.success:
        chunk_ids_2 = {r["chunk_id"] for r in r2.results}
        assert chunk_ids_1.isdisjoint(chunk_ids_2)


def test_get_more_candidates_hard_maximum():
    r = get_more_candidates(DOC, "confidential information", already_revealed_count=CANDIDATE_POOL_SIZE)
    assert not r.success and r.error == "POOL_EXHAUSTED"


def test_get_more_candidates_empty_exhaustion_near_pool_size():
    # DOC only has 4 chunks, so any window beyond that returns empty results gracefully.
    r = get_more_candidates(DOC, "confidential information", already_revealed_count=4)
    assert r.success or r.error == "POOL_EXHAUSTED"


def test_get_more_candidates_deterministic_order():
    r1 = get_more_candidates(DOC, "governing law delaware", already_revealed_count=0)
    r2 = get_more_candidates(DOC, "governing law delaware", already_revealed_count=0)
    assert [x["chunk_id"] for x in r1.results] == [x["chunk_id"] for x in r2.results]


def test_get_more_candidates_result_cap():
    r = get_more_candidates(DOC, "confidential information", already_revealed_count=0)
    assert len(r.results) <= MAX_CANDIDATE_RESULTS
