"""
Rule-based keyword baseline classifier (WBS T014, experiment B02, Section 8).

For each of the 17 ContractNLI hypotheses, a small set of positive/negative
keyword phrases approximates whether the NDA text entails or contradicts
the requirement. This is deliberately crude - Section 8 expects 30-50%
accuracy from it. Its purpose is to set the non-AI floor that every later
architecture (full-context LLM, RAG, RAG+agent) must clear; it is not
meant to be a good classifier.

Rule: if any negative phrase is found, predict Contradiction. Else if any
positive phrase is found, predict Entailment. Else predict NotMentioned.
Keywords were written against the actual hypothesis text pulled from
data/contractnli/dev.json's `labels` field, not guessed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeywordRule:
    positive: tuple[str, ...]
    negative: tuple[str, ...]


RULES: dict[str, KeywordRule] = {
    # nda-1: Explicit identification - Confidential Info must be expressly identified
    "nda-1": KeywordRule(
        positive=("expressly identif", "marked as confidential", "designated as confidential",
                  "identified in writing", "clearly marked", "marked confidential"),
        negative=("need not be marked", "regardless of whether it is marked", "without any marking"),
    ),
    # nda-2: Confidential Info shall ONLY include technical information
    "nda-2": KeywordRule(
        positive=("only include technical", "limited to technical information", "technical information only"),
        negative=("not limited to technical", "business, financial", "financial, business",
                  "technical or non-technical", "financial information", "business information"),
    ),
    # nda-3: May include verbally conveyed information
    "nda-3": KeywordRule(
        positive=("orally disclosed", "verbally disclosed", "orally or in writing",
                  "verbal disclosure", "disclosed orally"),
        negative=("in writing only", "must be in writing", "written form only", "excludes oral"),
    ),
    # nda-4: Limited use - only for purposes stated in the agreement
    "nda-4": KeywordRule(
        positive=("solely for the purpose", "only for the purpose", "for no other purpose",
                  "used only for", "purposes contemplated by"),
        negative=("for any purpose", "without restriction on use"),
    ),
    # nda-5: May share with some employees
    "nda-5": KeywordRule(
        positive=("employees who need to know", "need-to-know employees", "disclose to its employees",
                  "share with its employees", "employees with a need"),
        negative=("shall not disclose to any employee", "no employee shall"),
    ),
    # nda-7: May share with some third-parties (consultants, agents, advisors)
    "nda-7": KeywordRule(
        positive=("consultants", "professional advisors", "agents and professional",
                  "representatives", "third-parties (including"),
        negative=("shall not disclose to any third party", "no third party shall", "shall not disclose to third"),
    ),
    # nda-8: Must notify on compelled disclosure
    "nda-8": KeywordRule(
        positive=("required by law", "court order", "legal process", "shall notify",
                  "judicial process", "subpoena", "compelled to disclose"),
        negative=(),
    ),
    # nda-10: Confidentiality of the Agreement itself
    "nda-10": KeywordRule(
        positive=("existence of this agreement", "fact that this agreement", "terms of this agreement shall not",
                  "negotiat", "fact that discussions"),
        negative=(),
    ),
    # nda-11: No reverse engineering
    "nda-11": KeywordRule(
        positive=("reverse engineer", "decompile", "disassemble"),
        negative=("may reverse engineer", "permitted to reverse engineer"),
    ),
    # nda-12: May independently develop similar information
    "nda-12": KeywordRule(
        positive=("independently develop", "independent development"),
        negative=("shall not independently develop", "may not independently develop"),
    ),
    # nda-13: May acquire similar information from a third party
    "nda-13": KeywordRule(
        positive=("receives from a third party", "obtained from another source",
                  "rightfully obtain", "already known to", "lawfully in its possession"),
        negative=(),
    ),
    # nda-15: Agreement shall NOT grant any right/license
    "nda-15": KeywordRule(
        positive=("no license", "shall not grant any right", "no right or license",
                  "does not grant", "not be construed to grant"),
        negative=("grants a license", "license is hereby granted", "hereby grants"),
    ),
    # nda-16: Shall return or destroy upon termination
    "nda-16": KeywordRule(
        positive=("return or destroy", "shall return", "shall destroy",
                  "upon termination shall", "return all confidential"),
        negative=("not obligated to return", "no obligation to return or destroy"),
    ),
    # nda-17: May create a copy in some circumstances
    "nda-17": KeywordRule(
        positive=("may make copies", "permitted to copy", "reasonable number of copies",
                  "may reproduce"),
        negative=("shall not copy", "no copies shall be made", "may not reproduce",
                  "will not make any copy"),
    ),
    # nda-18: No solicitation of representatives
    "nda-18": KeywordRule(
        positive=("shall not solicit", "non-solicitation", "will not solicit", "agrees not to solicit"),
        negative=("may solicit",),
    ),
    # nda-19: Some obligations survive termination
    "nda-19": KeywordRule(
        positive=("survive termination", "survive the termination", "shall survive", "survive expiration"),
        negative=("shall not survive", "obligations terminate upon", "terminate upon expiration"),
    ),
    # nda-20: May retain some info even after return/destruction (e.g. archival/legal copies)
    "nda-20": KeywordRule(
        positive=("retain a copy", "archival purposes", "for archival", "backup",
                  "legal or regulatory", "one copy for its records"),
        negative=("shall not retain", "must destroy all copies without exception"),
    ),
}


def classify_with_span(hypothesis_id: str, doc_text: str) -> tuple[str, tuple[int, int] | None]:
    """
    Classify a (document, hypothesis) pair using keyword rules, also
    returning the character span of the matching phrase (the rule
    baseline's implicit "evidence") so it can be scored with the same
    Evidence Recall@K/Precision/MRR formulas used for real retrieval
    (evaluation.scorer.map_chunks_to_gold_span_indices treats it as a
    single rank-1 "chunk"). Returns (label, None) when nothing matched.
    """
    rule = RULES.get(hypothesis_id)
    if rule is None:
        return "NotMentioned", None

    text = doc_text.lower()

    for neg in rule.negative:
        idx = text.find(neg)
        if idx != -1:
            return "Contradiction", (idx, idx + len(neg))

    for pos in rule.positive:
        idx = text.find(pos)
        if idx != -1:
            return "Entailment", (idx, idx + len(pos))

    return "NotMentioned", None


def classify_by_keywords(hypothesis_id: str, doc_text: str) -> str:
    """
    Classify a (document, hypothesis) pair using keyword rules.

    Returns one of "Entailment", "Contradiction", "NotMentioned".
    Unknown hypothesis IDs default to "NotMentioned" (no rule = no evidence).
    """
    label, _ = classify_with_span(hypothesis_id, doc_text)
    return label
