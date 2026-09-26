"""
Canonical evidence->source-span matching (evidence_evaluator_v1 / v2). Deterministic, no model calls.

v1  (historical): exact verbatim substring match; kept as ``evidence_to_span_indices_v1`` so old results stay reproducible.
v2  (E13B):       exact-first, then a FORMATTING-normalized fallback whose match is mapped back to ORIGINAL character offsets, so the unchanged
                  gold-span overlap semantics keep operating in original-document coordinates.

Normalization (spec frozen in experiments/E13B_evidence_evaluator_hardening/config.yaml BEFORE historical re-scoring; applied identically to quote and context):
  A. Unicode NFC per base+combining-mark cluster (NOT NFKC: compatibility mappings could change numbers/semantics).
  B. delete zero-width formatting chars U+200B, U+200C, U+200D, U+2060, U+FEFF.
  C. every ``str.isspace()`` char (space, tab, CR/LF, NBSP, U+2000-200A, U+2028/9, U+202F, U+205F, U+3000, ...) -> runs collapse to ONE space.
  D. trim.
  NOT done: case-folding, punctuation edits (curly vs straight quotes stay different), word/negation edits, ellipsis segmentation, fuzzy/semantic matching.

Multiple matches: the v1 policy is preserved -- per context text only the FIRST (leftmost) occurrence is used (gold-blind, deterministic); every context text
containing the quote contributes. source-valid = at least one genuine occurrence (exact, else normalized).

Joint semantics and tau are unchanged (see ``joint_success``; identical to evaluation.metrics.joint_label_evidence_correctness).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from pipeline.evidence_text import ZERO_WIDTH, _normalize_with_map, all_occurrences as _all_occurrences, normalize_evidence_text  # noqa: F401  (shared frozen impl)

EVIDENCE_EVALUATOR_V1 = "evidence_evaluator_v1"
EVIDENCE_EVALUATOR_V2 = "evidence_evaluator_v2"
CURRENT_EVIDENCE_EVALUATOR = EVIDENCE_EVALUATOR_V2
TAU_EVIDENCE = 0.5  # frozen joint-metric evidence threshold; identical to evaluation.metrics' tau_evidence default; NOT tuned here


@dataclass(frozen=True)
class Match:
    text_index: int      # which context text (chunk) matched
    start: int           # ORIGINAL start offset within that text
    end: int             # ORIGINAL end offset (exclusive) within that text
    method: str          # "exact" | "normalized"
    n_occurrences: int   # occurrences of the (exact or normalized) quote in that text (ambiguity diagnostic)


# ---------------------------------------------------------------- matching
def find_evidence_matches(quote: str, texts: Sequence[str], offsets: Sequence[Sequence[int]], version: str = CURRENT_EVIDENCE_EVALUATOR) -> list[Match]:
    """Matches of one quote, with ABSOLUTE (offset-shifted) coordinates NOT applied; ``start``/``end`` are local to ``texts[text_index]``.
    v1: exact only. v2: exact in every text; only if none, normalized in every text. First occurrence per text (v1 policy)."""
    if not quote:
        return []
    exact = []
    for ti, text in enumerate(texts):
        pos = text.find(quote)
        if pos != -1:
            exact.append(Match(ti, pos, pos + len(quote), "exact", _all_occurrences(text, quote)))
    if exact or version == EVIDENCE_EVALUATOR_V1:
        return exact
    nq = normalize_evidence_text(quote)
    if not nq:
        return []
    out = []
    for ti, text in enumerate(texts):
        norm, starts, ends = _normalize_with_map(text)
        pos = norm.find(nq)
        if pos != -1:
            out.append(Match(ti, starts[pos], ends[pos + len(nq) - 1], "normalized", _all_occurrences(norm, nq)))
    return out


def evidence_to_span_indices(evidence: Sequence[str], chunk_texts: Sequence[str], chunk_offsets: Sequence[Sequence[int]], doc_spans: Sequence[Sequence[int]],
                             version: str = CURRENT_EVIDENCE_EVALUATOR) -> list[int]:
    """Gold-annotation span indices overlapped by the quoted evidence, in ORIGINAL document coordinates (offsets shift each text into the document)."""
    idx: set[int] = set()
    for quote in evidence:
        for m in find_evidence_matches(quote, chunk_texts, chunk_offsets, version):
            base = chunk_offsets[m.text_index][0]
            a0 = base + m.start
            a1 = a0 + len(quote) if m.method == "exact" else base + m.end   # exact keeps the v1 rule (quote length); normalized uses the recovered original range
            for k, (s0, s1) in enumerate(doc_spans):
                if min(s1, a1) > max(s0, a0):
                    idx.add(k)
    return sorted(idx)


def evidence_to_span_indices_v1(evidence, chunk_texts, chunk_offsets, doc_spans) -> list[int]:
    """Historical exact-substring mapping (identical to the copies in analyze_e05/e07/e08/e08b/e11)."""
    return evidence_to_span_indices(evidence, chunk_texts, chunk_offsets, doc_spans, EVIDENCE_EVALUATOR_V1)


def is_source_valid(quote: str, context: str, version: str = CURRENT_EVIDENCE_EVALUATOR) -> bool:
    """Is the quote genuinely present in the context (exact; v2 also formatting-normalized)?"""
    if not quote:
        return False
    if quote in context:
        return True
    return version != EVIDENCE_EVALUATOR_V1 and bool(normalize_evidence_text(quote)) and normalize_evidence_text(quote) in normalize_evidence_text(context)


def joint_success(gold_label: str, predicted_label: str | None, gold_span_idx: Sequence[int], predicted_span_idx: Sequence[int], tau: float = TAU_EVIDENCE) -> bool:
    """Per-case joint label+evidence success; identical semantics to evaluation.metrics.joint_label_evidence_correctness (tau unchanged)."""
    if predicted_label != gold_label:
        return False
    if gold_label == "NotMentioned":
        return len(predicted_span_idx) == 0
    if not gold_span_idx:
        return True
    return len(set(gold_span_idx) & set(predicted_span_idx)) / len(gold_span_idx) >= tau
