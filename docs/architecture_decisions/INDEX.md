# Architecture Decision Records — Index

Distinguishes historical ADRs (already-run T-series work) from reconstruction-v2 ADRs
(independently re-derived under `docs/experiment_registry.md`'s E-series). No historical ADR
is rewritten here.

## Historical ADRs (all in `docs/decisions.md`, unmodified)

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

None recorded yet. Per the current phase's stop condition, no new architecture decision is
made here — this index exists so future ADRs have a clear, separate home distinct from the
historical record above.
