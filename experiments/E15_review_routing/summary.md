# E15 summary — Outcome C: NO EFFECTIVE SELECTIVE ROUTING (R1 retained as a structural source-integrity safeguard only)

Deterministic observable runtime signals were insufficient to achieve the predeclared safety target within the provisional review-rate ceiling. (Ceiling 40% and residual-error target 10% are provisional project-level values inherited from the earlier abstention plan; not measured capacity, an SLA, a customer requirement, or a validated legal-risk threshold.)
Zero policy tuning; validation run once. No TEST. Not committed.

## Development (Stage A, E13 FULL, 150 cases; preserved unchanged)
R1 review 2.7% / joint capture 6.7% · R2 34.7% / 40% · R3 57.3% / 90% / residual 4.7%.

## Fresh validation: DEV_ROUTING_v1 (frozen; seed 1500; 60 E / 18 C / 60 NM; 41 docs; case-disjoint from seed-42 sample, golden cases, DEV_ARCH_v1)
Execution: 138/138 API calls completed once (concurrency 5, 60s timeout, no retries/outage), spend $0.3077, ledger $2.8044 -> $3.1121. 137 strict-parse; 1 response (dev::406::nda-1) had malformed JSON escaping -> unusable parse (not rerun; counts as a failure and is routed by R1).
Model (GPT-5-mini + P0 + FULL): accuracy 73.9%, macro-F1 0.721, **joint 71.0% (98/138)**, Contradiction recall 77.8% (14/18, 95% CI 54.8–91.0, descriptive). Lower than E13 (accuracy 83.3%/joint ~77–80%): fresh DEV is harder or E13 was optimistic (NotMentioned recall 61.7%; 16 NM predicted E, 7 predicted C). 40 joint failures, 5 source-invalid-quote cases.

| Policy | Raw review | DEV-std review | Joint capture | Cls capture | Residual joint err (raw / std) | Sel. joint success | False review | Precision |
|---|---|---|---|---|---|---|---|---|
| R0 | 0/138 | 0% | 0/40 | 0 | 29.0% / 28.5% | 71.0% | 0% | – |
| R1 | 6 (4.3%) | 4.5% | 5/40 (12.5%) | 5.6% | 26.5% / 25.7% | 73.5% | 1.0% | 83% |
| R2 | 29 (21.0%) | 18.6% | 15/40 (37.5%) | 33.3% | 22.9% / 21.0% | 77.1% | 14.3% | 52% |
| R3 | 71 (51.4%) | **51.3%** | 33/40 (82.5%) | 80.6% | **10.4% / 10.7%** | 89.6% | 38.8% | 46% |
Confusion (failure/success × review/auto): R1 5/35, 1/97 · R2 15/25, 14/84 · R3 33/7, 38/60.
95% Wilson: R3 review 43.2–59.6%, capture 68.1–91.3%, residual 5.2–20.0%. Workload per 100/1,000/8,000 (DEV-standardized, evaluation-only estimate, not a production forecast): R1 4.5/45/362 · R2 18.6/186/1,485 · R3 51.3/513/4,102 (raw: R3 51.4/515/4,116).
Class-conditional R3 (review rate / failures / caught / residual): E 58%/13/9/4 · C 78%/4/3/1 · NM 37%/23/21/2.

## Frozen selection rule for R3
1 std review <=40%: **FAIL (51.3%)** · 2 residual <10%: **FAIL, marginally (10.4% raw; 10.7% std)** · 3 capture >= R1 +20pp: pass (82.5% vs 12.5%) · 4 no Contradiction regression: pass · 5 no structural problem: pass. R3 not selected.
R1: useful only as a structural guard — it flags 6 cases (5 non-source-quote cases + the 1 unusable parse), 5 of them real failures, but captures only 12.5% of failures and leaves 26.5% residual error; it is not an uncertainty detector. Hence C, not B.
R2 (reference): residual 22.9%, captures 0/4 Contradiction failures while reviewing all 14 correct Contradictions (misses arise where the model predicts Entailment). It fired more usefully than in Stage A (lift ~1.8 vs 1.15, via NotMentioned over-inferred as Contradiction) but still fails both targets. Closed.

## Contradiction (18; DESCRIPTIVE only)
Failures 4. Reviewed: R0 0, R1 0, R2 0, R3 3 (residual 1). Correct Contradictions unnecessarily reviewed: R1 1/14, R2 14/14, R3 11/14.

## Generalization of R3 (Stage A -> validation)
Review 57.3% -> 51.4%; capture 90.0% -> 82.5%; residual 4.7% -> 10.4%; precision 31.4% -> 46.5%; false review 49.2% -> 38.8%. Same broad direction, no collapse, workload stable ~50–57% — but the workload never approaches the 40% ceiling. Rule agreement: agree rate 49%; joint success 88% when the rule agrees vs 54% when it disagrees. R3 disclosure stands: the keyword rules have historical DEV exposure (written against DEV hypothesis text in the old project); this was a case-level-disjoint test of whether the lift generalizes, and the lift did generalize, at unacceptable workload.

## Residual failures under R3 (7, each inspected; analysis-only buckets)
- Missed Contradiction (1): dev::586::nda-4 — "Notwithstanding any other provision…" carve-out negates the general use restriction; model quoted the general clauses -> Entailment; rule also said Entailment (the known exception/carve-out weakness).
- Entailment predicted NotMentioned, no evidence (4): dev::72::nda-16, 381::nda-1, 411::nda-4, 605::nda-10 — real supporting clauses exist in the gold spans; model missed them; the rule also said NotMentioned, so disagreement routing could not see it.
- NotMentioned over-inferred as Entailment (2): dev::37::nda-10, 590::nda-16 — superficially related clauses quoted; rule agreed.
R1 residuals (35): 22 over-inference, 8 Entailment reasoning/missed-evidence, 4 missed Contradiction, 1 label-right/evidence-wrong.
Takeaway: rule disagreement catches failures where the model and keyword rule diverge; failures where both are wrong the same way (mostly NotMentioned-side agreement) are invisible to it.

## Limitations
n=138 (18 C; Contradiction descriptive); DEV with disclosed historical exposure; standardization assumes validation within-class mix ≈ DEV; provisional constraints not validated; model performance dropped vs E13 (variance/difficulty); one unusable parse; residual 10.4% vs 10% is marginal and CI is wide (5.2–20.0%) — the workload failure (51% vs 40%) is the clearer reason for outcome C.

## Closure (approved)
Final outcome C is approved; E15 is closed. No routing policy is adopted. R1 may remain only as a structural/source-integrity safeguard and must not be described as an uncertainty detector.
Additional recorded limitations: no confidence/logprob signal exists in the current candidate; no verifier model or second LLM was tested; the keyword rules carry prior DEV exposure; no further routing-rule tuning, R4, confidence prompt, verifier, agent routing, or extra DEV confirmation is permitted.
