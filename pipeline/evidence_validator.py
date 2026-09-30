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
string either is or isn't a genuine occurrence in the context the model
saw. No LLM call, no cost.

RUNTIME_EVIDENCE_VALIDATOR_V1: exact substring only (historical).
RUNTIME_EVIDENCE_VALIDATOR_V2 (E14, current): exact first, then the frozen
evidence_evaluator_v2 formatting fallback (NFC, zero-width removal,
whitespace collapse) via pipeline.evidence_text - the SAME implementation
the offline evaluator uses. Source-grounding only: no gold, no labels, no
semantic tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.evidence_text import locate_quote

RUNTIME_EVIDENCE_VALIDATOR_V1 = "runtime_evidence_validator_v1"
RUNTIME_EVIDENCE_VALIDATOR_V2 = "runtime_evidence_validator_v2"
CURRENT_RUNTIME_EVIDENCE_VALIDATOR = RUNTIME_EVIDENCE_VALIDATOR_V2


@dataclass
class EvidenceValidationResult:
    verbatim_quotes: list[str]
    hallucinated_quotes: list[str]
    label_evidence_consistent: bool  # False if label=="NotMentioned" but evidence is non-empty
    # additive (v2) metadata, defaults keep old constructors working: quotes accepted only via the formatting fallback,
    # and each verbatim quote's first-occurrence (start, end) in the ORIGINAL context.
    normalized_quotes: list[str] = field(default_factory=list)
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def all_verbatim(self) -> bool:
        return not self.hallucinated_quotes

    @property
    def is_valid(self) -> bool:
        return self.all_verbatim and self.label_evidence_consistent


def validate_evidence(context: str, evidence: list[str], label: str, version: str = CURRENT_RUNTIME_EVIDENCE_VALIDATOR) -> EvidenceValidationResult:
    """
    Check the classifier's cited evidence against the context it was
    actually given.

    `context` must be the exact text handed to the classifier (the
    retrieved chunks joined, gold evidence, or full document - whatever
    the caller used) - checking against anything else (e.g. the full
    document when only retrieved chunks were shown) would silently pass
    quotes the model couldn't have legitimately seen from that context.
    """
    verbatim, hallucinated, normalized, spans = [], [], [], {}
    for q in evidence:
        if version == RUNTIME_EVIDENCE_VALIDATOR_V1:
            pos = context.find(q) if q else -1
            hit = (pos, pos + len(q), "exact") if pos != -1 else None
        else:
            hit = locate_quote(q, context)
        if hit is None:
            hallucinated.append(q)
            continue
        verbatim.append(q)
        spans.setdefault(q, (hit[0], hit[1]))
        if hit[2] == "normalized":
            normalized.append(q)

    # prompts/classify_v*.txt's own rule: NotMentioned must carry no evidence.
    label_evidence_consistent = not (label == "NotMentioned" and len(evidence) > 0)

    return EvidenceValidationResult(
        verbatim_quotes=verbatim,
        hallucinated_quotes=hallucinated,
        label_evidence_consistent=label_evidence_consistent,
        normalized_quotes=normalized,
        spans=spans,
    )
