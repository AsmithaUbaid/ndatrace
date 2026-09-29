# Architecture Decision Records — Index

Distinguishes historical ADRs (already-run T-series work) from reconstruction-v2 ADRs
(independently re-derived under `docs/experiment_registry.md`'s E-series). No historical ADR
is rewritten here.

## Historical ADRs (pre-reconstruction; original evidence archived, not carried forward as a live doc)

| ADR | Title | Status for reconstruction-v2 |
|---|---|---|
| ADR-001 | Model choice: google/gemini-2.5-flash-lite | Evidence only — E02 re-screens |
| ADR-002 | Retrieval configuration | Evidence only — E06 re-derives |
| ADR-003 | Standard RAG end-to-end (real vs. Oracle ceiling) | Evidence only — E07/E08 re-derive |
| ADR-004 | Prompt version: v6 | Evidence only — E03 re-derives |
| ADR-005 | Confidence/abstention design | Evidence only — E13 re-derives |
| ADR-006 | Routing-signal independence fix | Historical bug fix — code-level, stays fixed |
| ADR-007 | Agent include/exclude | Evidence only — E09–E11 re-derive |
| ADR-008 | Full-context baseline: diagnostic ceiling | Evidence only — E05/E12 re-derive |
| ADR-009 | Final architecture freeze: RAG + selective agent | **Historical evidence only — NOT the reconstruction-v2 freeze.** E12 independently re-evaluates A0–A3. |
| ADR-010 | Final locked test-set evaluation (T041) | Historical — E14 is the reconstruction-v2 equivalent |
| ADR-011 | Golden battery Categories 1–2 | Evidence only |

## Reconstruction-v2 ADRs

### ADR-012 — E20 same-population TEST comparator: FULL retained as benchmark winner; RAG framed as the production-oriented direction

**Status:** Accepted benchmark conclusion; updated product decision. FULL remains the benchmark
winner, while the interactive prototype now serves the frozen E20 RAG configuration for its
bounded-context product characteristics.

**Context:** ADR-009 (historical) and E19's freeze established FULL as the reconstruction-v2
architecture from E05–E13's matched *development*-sample comparisons. No reconstruction-v2
experiment had run RAG and FULL head-to-head on the full official TEST split with paired
significance testing until E20.

**Evidence (E20, n=2,091, frozen top-5 `retrieval_v1`, zero tuning after freeze):**
- Classification accuracy: FULL 77.6% vs RAG 76.8% — **not** statistically distinguishable
  (McNemar p=0.217).
- Joint (evidence-grounded) success: FULL 74.6% vs RAG 72.5% — **statistically significant**
  (McNemar p=0.0047; 144 FULL-only vs 99 RAG-only joint successes).
- RAG: −50.4% input tokens, −16.8% API cost/case, +1.8pt Contradiction recall, +1.2pt
  source-valid quote rate.
- Retrieval itself is rarely the bottleneck: only 9.5% (55/576) of RAG's non-joint failures are
  retrieval-limited; reasoning/classification dominates (448/576).
- Cost-to-serve (E18's 3-layer model, C_H = $3.33/case @ 5min/$40hr, p_safe = joint): FULL
  all-in $0.848/case vs RAG $0.920/case — FULL's higher joint success outweighs RAG's lower raw
  inference cost once human-review cost is priced in, under this illustrative scenario.
- TEST documents in this run: median 1,836 / max 7,861 tokens — far short of a real 50–100 page
  enterprise contract. RAG's cost-scaling advantage (context stays bounded regardless of source
  document length, vs FULL's linear growth) is an architectural property, not something measured
  at that scale here.

**Decision:** two conclusions held simultaneously, not collapsed into one "X is better" claim:
1. **Benchmark conclusion**: FULL is the strongest measured configuration on ContractNLI — its
   Joint-success advantage over RAG is statistically significant, not just directionally
   favorable.
2. **Production-oriented conclusion**: RAG is retained as the preferred *architectural
   direction* for future large-document / repeated-query deployment — it halves classifier
   input tokens, bounds context growth independent of document length, and lets per-document
   retrieval indexing be reused across the 17 per-document requirement checks — at a documented,
   explicit cost of ~2.2pp of Joint success on this dataset.

**Explicitly not claimed:** that RAG has been proven more accurate/reliable on long contracts
(untested — the longest TEST document here is 7,861 tokens), that FULL is unsuitable for
production, or that the E19 freeze is reversed. This ADR documents a benchmark-vs-production-
scaling distinction for the written report, not a runtime change.

**Revisit if:** a real long-document (50–100 page) evaluation set becomes available — that is
the actual test of RAG's production-scaling argument, which this ADR states as an architectural
hypothesis, not an empirical result.

**Product implementation decision (post-experiment, no retuning):** the interactive UI uses the
unchanged E20 top-5 RAG configuration. This changes the served engineering architecture only; it
does not revise the E20 metrics or the conclusion that FULL achieved higher Joint correctness.

Full numbers: `experiments/E20_final_rag_test/results/E20_final_report.json`;
`docs/experiment_registry.md`'s E20 row.
