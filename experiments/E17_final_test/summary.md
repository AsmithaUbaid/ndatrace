# E17 — Final TEST evaluation (one-shot, executed per frozen protocol)

**Candidate: evidence-grounded but not prompt-injection-hardened.** Not production-ready; not legal-approval automation; no claim of full-TEST GPT performance.
Commit at TEST start: 5717bdf. First final TEST access 2026-09-26T19:23:43Z. TEST verified: 123 documents / 2,091 cases (E 968 / C 220 / NM 903). Metrics frozen before failure inspection (`results/final_metrics.json`, sha256 in `final_metrics.sha256`).
Manifest TEST_HOSTED_v1 sha256 a1cc8f53…, hosted request artifact sha256 a7c2d769…. GPT-P0 sha1 3fcc7c95…, evidence_evaluator_v2, runtime validator v2. No selective routing.

**Wording discipline:** GPT results are from a budget-constrained balanced stratified sample (n=150); the local comparators were measured over the full 2,091-case TEST population. The 150-case GPT numbers are not more precise than the 2,091-case comparator measurements.

## A. Hosted GPT-5-mini + P0 + FULL — balanced sample (n=150; 50/50/50) — sampled estimate
| Metric | Value (95% CI, stratified bootstrap 10,000) |
|---|---|
| Joint label+evidence success | 76.7% (115/150) [70.0, 83.3] |
| Macro-F1 | 0.777 [0.710, 0.841] |
| Accuracy | 78.0% (117/150) [71.3, 84.0] |
| Entailment recall | 46/50 = 92.0% (Wilson 81.2–96.9) |
| **Contradiction recall** | **39/50 = 78.0% (Wilson 64.8–87.3)** |
| NotMentioned recall | 32/50 = 64.0% (Wilson 50.1–75.9) |
| Joint by class | E 46/50 (81.2–96.9) · C 37/50 = 74% (60.5–84.1) · NM 32/50 (50.1–75.9) |
| Evidence recall / precision | 93/100 = 93.0% · 93/114 = 81.6% |
| Source-valid quote rate | 98.7% (3 cases with a non-source quote) |
| Parse | 150 strict / 0 recovered / 0 invalid |
Confusion (gold→pred E/C/NM): E 46/1/3 · C 10/39/1 · NM 9/9/32.
Contradiction (n=50): correct 39/50, joint 37/50, C→E 10, C→NM 1 (do not extrapolate legal-risk probabilities from 50 cases).

## B. TEST-prevalence-standardized estimates (NOT measured full-TEST GPT metrics)
Weights E 968/2091 = 0.463, C 220/2091 = 0.105, NM 903/2091 = 0.432; Σ weight × sampled class rate.
Standardized accuracy **78.4%** [71.6, 85.1]; standardized joint **78.0%** [71.2, 84.8] (stratified bootstrap within each 50-case class, 10,000 resamples, seed 1700).

## C. Full-TEST comparators (all 2,091 cases; measured)
| | Accuracy | Macro-F1 | E recall | C recall (n=220) | NM recall | Joint | Ev. recall / precision |
|---|---|---|---|---|---|---|---|
| Rule baseline | 59.0% | 0.479 | 39.3% | 16.8% (37/220; 12.5–22.3) | 90.5% | 50.1% | 29.3% / 60.8% |
| Local Qwen2.5-7B ctx16k | 49.9% | 0.431 | 46.3% | 25.5% (56/220; 20.2–31.6) | 59.7% | 39.7% | 35.3% / 35.9% |
Rule: predicts NotMentioned by default on 72.6% of cases (1,519 fallback), 0.18 s total, $0. Qwen: 1,986 strict / 101 recovered / 4 invalid parses, 0 provider errors, source-valid quote rate 70.3%, joint by class E 26.6% · C 15.5% · NM 59.7%; runtime 7.13 h (mean 12.3 s/case, p90 22.4 s), $0; C outcomes: 56 correct, 25→E, 139→NM. Rule C: 37 correct, 25→E, 158→NM.
On the same 150 hosted cases: rule 47.3% acc / 40.0% joint; Qwen 44.7% acc / 34.0% joint (context only; balanced sample). Rule and Qwen are contextual comparators, not production candidates.

## D. Operational / cost (hosted GPT)
Input tokens mean 2,383 / median 1,945 / p90 4,369 / p95 4,754 / max 7,896; output mean 790 / median 722 / p90 1,318 / p95 1,478 / max 1,961; latency mean 7.0 s / median 6.5 s / p90 10.5 s / p95 11.8 s; 150/150 calls succeeded, 0 failures/retries-visible, wall 217 s at concurrency 5.
Cost: pre-run ledger $3.19157; expected $0.3216; conservative $0.4749; **actual $0.3264** ($0.002176/case); final ledger **$3.51797** (append-only, 150 rows added). Projected hosted cost: **$2.18 per 1,000 cases, $17.41 per 8,000 cases.** (Under the user-approved budget policy update the old $5/$1.25-reserve stop was not enforced; the run stayed inside it anyway: $3.52 < $3.75.)

## E. GPT failure analysis (35 joint failures; analysis-only, no rules created; `results/failure_analysis.json`)
- Reasoning failure with gold evidence found (wrong label, quoted evidence overlaps gold): **10** (9 C→E, 1 E→C).
- NotMentioned over-inference (gold NM, predicted E/C): **18** (9 E, 9 C).
- Missed provision (predicted NM, no evidence, gold text present in the full document): **4**.
- Exception/carve-out failure: **1** clear (test::565::nda-20; possible in 387::nda-7, 80::nda-7).
- Correct label but evidence not overlapping gold: **2** (both Contradiction).
- Malformed output 0; cases with a non-source quote 3 (2 among failures; one is a ligature-character formatting non-coverage); unclear 0.
Contradiction failures: 11 classification (10 C→E, 1 C→NM) and 13 joint. Evidence existed in 10/10 C→E; the relevant gold text is present in the FULL context in every case; in 9/10 C→E the quoted evidence overlapped the gold spans (right clause found, wrong polarity judgment). The single C→NM had empty evidence.

## F. Routing limitation (E15)
E15 found no effective selective routing policy that satisfies the provisional workload/safety constraints. R3 was NOT used on TEST; no abstention layer is claimed to fix residual TEST errors; R1 remains only a structural/source-integrity safeguard (no R1 result is used in the metrics above).

## G. Robustness and Prompt-Injection Limitation (E16)
20 matched clean/attack pairs (40 hosted calls). 4/11 injection-type pairs showed attack success (2 label hijacks: an instruction-only document and a fake [SYSTEM] message; 2 output-format requests honored); 2 clean-correct→attack-wrong regressions; attacked evidence stayed source-grounded; no code execution, no secret/data leakage, no malformed hosted output. Source grounding does not imply the source text is trustworthy — the validator cannot detect malicious instructions that are genuinely in the NDA. GPT-P0 has no dedicated injection-resistance instruction and no patch was introduced before TEST. Distractor padding, long context, duplicated clauses and carve-outs were robust on that small set.

## H. Protocol deviations
None to the frozen model/prompt/architecture/manifest/evaluator/validator/parser/routing/sample. One approved policy change: the budget breaker was disabled by explicit user update (spend recorded only). One process note: the analysis script's evidence-precision denominator counts cases with any quoted evidence, matching earlier analyzers.

## I. Limitations
Hosted GPT is a balanced n=150 sample (Contradiction n=50, Wilson interval ~±11 pts); standardized estimates rest on the assumption that the sampled cases represent each class; single run, temperature 0.0; DEV/TEST historical exposure of the ContractNLI benchmark family; comparator prompt is the GPT prompt (Qwen not tuned; wrapper differs from earlier E05 runs); source-validity and evidence metrics use the frozen evaluator_v2 conventions; failure buckets are analysis-only judgments.

## J. Productionization gaps (future work, not done)
Prompt-injection defense and testing at scale; selective review/abstention that meets a real capacity target (E15 found none); exception/carve-out and NotMentioned-over-inference improvements; evidence-selection on long documents; cost/latency at production volumes; monitoring, PII/confidentiality handling, legal review workflow; independent held-out validation beyond this one-shot TEST.
