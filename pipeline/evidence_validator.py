"""
Evidence validator (WBS T025, Section 6 component "Citation verification").

The classifier's prompt (prompts/classify_v*.txt) instructs the model to
return "evidence" as exact verbatim substrings of the context it was
given - "Never invent or paraphrase a quote." Nothing before this module
actually checks that the model followed that rule. A model can produce
plausible-looking output where the label is right but the cited "quote"
is fabricated or paraphrased - hallucinated citations - which would go
undetected by every metric used so far (Evidence Recall@K/Precision/MRR
score retrieval, not what the model claims to quote from it).

This is a deterministic string check, not a judgment call: each evidence
string either is or isn't an exact substring of the context the model
saw. No LLM call, no cost.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvidenceValidationResult:
    verbatim_quotes: list[str]
    hallucinated_quotes: list[str]
    label_evidence_consistent: bool  # False if label=="NotMentioned" but evidence is non-empty

    @property
    def all_verbatim(self) -> bool:
        return not self.hallucinated_quotes

    @property
    def is_valid(self) -> bool:
        return self.all_verbatim and self.label_evidence_consistent


def validate_evidence(context: str, evidence: list[str], label: str) -> EvidenceValidationResult:
    """
    Check the classifier's cited evidence against the context it was
    actually given.

    `context` must be the exact text handed to the classifier (the
    retrieved chunks joined, gold evidence, or full document - whatever
    the caller used) - checking against anything else (e.g. the full
    document when only retrieved chunks were shown) would silently pass
    quotes the model couldn't have legitimately seen from that context.
    """
    verbatim = [q for q in evidence if q and q in context]
    hallucinated = [q for q in evidence if not q or q not in context]

    # prompts/classify_v*.txt's own rule: NotMentioned must carry no evidence.
    label_evidence_consistent = not (label == "NotMentioned" and len(evidence) > 0)

    return EvidenceValidationResult(
        verbatim_quotes=verbatim,
        hallucinated_quotes=hallucinated,
        label_evidence_consistent=label_evidence_consistent,
    )
