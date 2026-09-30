# E14 summary — Outcome A: APPROVE RUNTIME VALIDATOR V2 (approved)

Scope note: this is a runtime/analysis evidence-source validator aligned for future pipeline use. No production `pipeline/` or `backend/` execution path calls it, so E14 does not prove a live request path changed.

- Old runtime (v1): `q in context` per quote; returns verbatim/hallucinated lists + NotMentioned-consistency flag. No callers in `pipeline/` or `backend/`; only experiment/analysis scripts (E05/E07/E08B/E12A-C/E13, build_*_cases, analyze_test_set_results) call it. Validity never feeds labels or routing.
- v2: exact first, then frozen v2 formatting fallback; adds additive fields `normalized_quotes`, `spans` (first-occurrence original span). Same dataclass/properties/contract; `version=` arg selects v1.
- Shared code: new `pipeline/evidence_text.py` (normalization + offset map + `locate_quote`); `evaluation/evidence_matching.py` now imports it (definitions removed, behavior identical: E13B rescoring re-run leaves E13B results byte-identical).
- Tests: +30 (378 -> 408), all pass. Corpus of 24 fixtures (whitespace, 5 zero-width chars, NFC, negation/number/modal/party/term/missing-word/paraphrase/case negatives, curly-quote/ellipsis noncoverage): runtime == evaluator_v2 on 24/24.
- Replay: 14 arms, 2,100 cases, 2,560 quotes. v1->v2: 41 invalid->valid (33 unique per experiment, 27 unique case/quote), 0 valid->invalid. v2 vs evaluator_v2 disagreement: 0. Label/consistency changes: 0.
- Manual review of all 41: every one a TRUE FORMATTING RESCUE (line-break/space, zero-width, whitespace runs; quote == recovered source after stripping whitespace/zero-width). 0 false positives, 0 ambiguous.
- Perf (per quote, worst case = longest DEV NDA 32,359 chars, miss/fallback): v1 ~0.007 ms, v2 ~5.9 ms (p95 6.5 ms); median doc ~2 ms; exact hits unchanged (~0.002 ms). Negligible vs ~1-5 s model latency.
- Ledger $2.80439895 unchanged; no TEST read; no model calls.
- Known cost: v2 re-normalizes the context per non-exact quote (no cache); fine at these sizes.
