# E20 — Final RAG TEST comparator (same-population head-to-head with E17B's FULL)

**This is the headline result the README and final report both cite.** Frozen top-5
`retrieval_v1` RAG (BM25 top-20 → cross-encoder rerank → top-5 → GPT-5-mini + GPT-P0,
temperature 0, single-shot, zero tuning after freeze) run on the **full official TEST split**
(123 documents, 2,091 cases: 968 Entailment / 220 Contradiction / 903 NotMentioned) — the same
population E17B used for FULL, enabling paired significance testing that E13's earlier dev-sample
comparison never had. Config hash `97afd5c7…`; GPT-P0 sha1 `3fcc7c95…` (same frozen prompt as
E17/E17B). Source: `results/E20_final_report.json`.

## A. RAG metrics (n=2,091; measured, not sampled)
| Metric | Value |
|---|---|
| Accuracy | 76.76% |
| Macro-F1 | 0.7228 |
| Joint (label + evidence) | 72.45% (1,515/2,091) |
| Entailment recall | 89.26% (864/968) |
| **Contradiction recall** | **77.27% (170/220)**, Wilson 95% [71.3, 82.3] |
| NotMentioned recall | 63.23% (571/903) |
| Joint by class | E 81.71% · C 69.55% (153/220) · NM 63.23% |
| Evidence recall / precision | 88.97% / 72.45% |
| Source-valid quote rate | 99.23% |
| Parse | 2,089 strict / 0 recovered / 2 invalid |

Confusion (gold→pred): E 864/50/54 (0 invalid) · C 45/170/5 (0 invalid) · NM 192/138/571 (2 invalid).

## B. FULL vs RAG, same 2,091 cases (paired)
| Metric | FULL (E17B) | RAG (E20) | Δ (FULL−RAG) |
|---|---:|---:|---:|
| Accuracy | 77.62% | 76.76% | +0.86pp |
| Macro-F1 | 0.7270 | 0.7228 | +0.0042 |
| Joint | 74.61% | 72.45% | +2.15pp |
| Contradiction recall | 75.45% | 77.27% | −1.82pp |
| Input tokens/case | 2,279 | 1,131 | −50.4% (RAG) |
| Cost/case | $0.002023 | $0.001682 | −16.8% (RAG) |

**Paired McNemar** (identical cases, not independent samples): classification accuracy difference
NOT significant (p=0.2174, 104 FULL-only-correct vs 86 RAG-only-correct). Joint difference IS
significant (p=0.0047, 144 FULL-only-joint vs 99 RAG-only-joint) — FULL's evidence-grounding edge
is real, not noise, even though raw label accuracy is statistically indistinguishable between the
two architectures.

## C. Retrieval diagnostics (why RAG loses the cases it loses)
recall@5 95.37%, recall@20-pool 100% (candidate pool always contains the gold evidence),
precision@5 22.93%, MRR@5 0.7715. Of RAG's 576 non-joint cases, the failure taxonomy is:
retrieval-limited 55 (9.5%), reasoning/classification 448 (77.8%), evidence-selection 59 (10.2%),
runtime parser/source-validity 14 (2.4%). **Reasoning, not retrieval, dominates the residual
error** — more retrieval depth alone would not close most of this gap.

## D. Length-band analysis (predeclared terciles on full-NDA token count, outcome-independent)
| Band | n | Accuracy | Joint |
|---|---:|---:|---:|
| Short | 714 | 74.51% | 72.55% |
| Medium | 697 | 78.48% | 74.89% |
| Long | 680 | 77.35% | 69.85% |

Joint degrades on the longest band even though this TEST population's documents (median 1,836,
max 7,861 tokens) are nowhere near a real 50–100 page enterprise contract — a caveat on how far
this result generalizes to longer documents.

## E. Operational / cost
Input tokens mean 1,131; output tokens mean 701; latency mean 7,141 ms (p95 13,435 ms). 2,091/2,091
calls succeeded, 0 provider errors, 0 parse failures beyond the 2 invalid-but-recovered cases,
0 budget/circuit-breaker trips. Run spend $3.5177 (pre-run ledger $8.0475 → post-run $11.5652);
wall time 2,997 s (~50 min) at the configured concurrency. Cost per joint success $0.002322.
Multi-requirement projection: $0.0286/document (17 requirements) at RAG rates vs $0.0344/document
at FULL rates — $28.60 vs $34.39 per 1,000 documents, API cost only.

## F. Illustrative cost-to-serve (sensitivity analysis, not a measured savings result)
Using the disclosed, unvalidated assumption of 5 minutes of manual review at $40/hour ($3.3333
per case) charged only against non-joint outcomes: RAG all-in $0.9199/case, FULL all-in
$0.8485/case — **FULL is cheaper all-in despite costing more per API call**, because FULL's
higher joint-success rate (74.61% vs 72.45%) avoids more of the $3.33 review cost than RAG saves
on tokens. Both remain far cheaper than the $3.33 manual-only baseline. This model has not been
validated with real reviewers; see the final report's "Business impact" section for the full
caveat.

## G. Interpretation (frozen as ADR-012)
FULL remains the stronger quality-reference configuration on ContractNLI (statistically
significant joint advantage, cheaper all-in under the illustrative cost model). RAG is retained
as the production-oriented direction for larger/repeated-query deployments given its bounded
per-call token cost — an explicit engineering trade-off made with the measured numbers in view,
not a reversal of the FULL-architecture freeze from E19. See `docs/architecture_decisions/INDEX.md`
ADR-012 for the full decision record.

## H. Limitations
Single run at temperature 0 on one official TEST split; no repeated-sampling variance estimate;
ContractNLI document lengths are shorter than a typical real enterprise NDA (see D); the
cost-to-serve model in F is illustrative, not measured; E15's routing and E16's injection-guard
limitations (carried forward from earlier experiments) both still apply to this architecture —
see E15 and E16/E21/E22 for the review-routing and security findings respectively.
