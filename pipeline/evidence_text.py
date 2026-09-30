"""
Shared frozen evidence-text normalization (evidence_evaluator_v2 spec, experiments/E13B_evidence_evaluator_hardening/config.yaml).

Neutral home so BOTH offline scoring (evaluation.evidence_matching) and the runtime validator (pipeline.evidence_validator) use ONE implementation.
Dependency direction: evaluation -> pipeline (already the case elsewhere); pipeline never imports evaluation. Stdlib only, deterministic, no model calls.
Spec is FROZEN: NFC per cluster, delete U+200B/200C/200D/2060/FEFF, collapse str.isspace() runs to one space, trim. Nothing else.
"""

from __future__ import annotations

import unicodedata

ZERO_WIDTH = frozenset("​‌‍⁠﻿")


# ---------------------------------------------------------------- normalization with offset map
def _normalize_with_map(text: str) -> tuple[str, list[int], list[int]]:
    """Return (normalized, starts, ends): starts[k]/ends[k] are the ORIGINAL [start, end) of the cluster / whitespace run that produced normalized char k."""
    out: list[str] = []; starts: list[int] = []; ends: list[int] = []
    n, i = len(text), 0
    ws_start = ws_end = -1
    while i < n:
        ch = text[i]
        if ch in ZERO_WIDTH:
            i += 1; continue
        if ch.isspace():
            if ws_start < 0: ws_start = i
            ws_end = i + 1; i += 1; continue
        j = i + 1                                   # base char + following combining marks = one cluster
        while j < n and unicodedata.combining(text[j]) != 0:
            j += 1
        if ws_start >= 0:
            if out:                                  # leading whitespace dropped
                out.append(" "); starts.append(ws_start); ends.append(ws_end)
            ws_start = ws_end = -1
        for c in unicodedata.normalize("NFC", text[i:j]):
            out.append(c); starts.append(i); ends.append(j)
        i = j
    return "".join(out), starts, ends               # trailing whitespace never emitted (trim)


def normalize_evidence_text(text: str) -> str:
    """Normalized form of a string (no offsets), per the frozen v2 spec."""
    return _normalize_with_map(text)[0]


def all_occurrences(hay: str, needle: str) -> int:
    n, pos = 0, hay.find(needle)
    while pos != -1:
        n += 1; pos = hay.find(needle, pos + 1)
    return n


def locate_quote(quote: str, text: str) -> tuple[int, int, str] | None:
    """(start, end, method) of the FIRST occurrence of quote in text, in ORIGINAL coordinates: exact first, else formatting-normalized. None if absent."""
    if not quote:
        return None
    pos = text.find(quote)
    if pos != -1:
        return pos, pos + len(quote), "exact"
    nq = normalize_evidence_text(quote)
    if not nq:
        return None
    norm, starts, ends = _normalize_with_map(text)
    pos = norm.find(nq)
    if pos == -1:
        return None
    return starts[pos], ends[pos + len(nq) - 1], "normalized"
