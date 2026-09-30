# E17B — Full TEST Completion

Pre-run commit `3b2167a`. Post-freeze completion of TEST coverage using the IDENTICAL E17 system (model, prompt sha1 3fcc7c95…, FULL context, parser, runtime validator v2, evidence_evaluator_v2, no routing). E17's original 150 hosted predictions were not rerun and are unchanged. No system component changed after seeing E17 results. Two API credentials were used only to split execution load (3+3 concurrency); credential identity is not recorded anywhere in any artifact, log, or result (verified by test).

## Complement construction
1,941 = 2,091 − 150. Label counts: Entailment 918, Contradiction 170, NotMentioned 853 (matches official TEST minus the 150 sampled). Intersection with E17's 150 is empty; union equals all 2,091 TEST case IDs. Manifest `E17B_REMAINING_v1` sha256 `7eef3e77…`; request artifact sha256 `5a2c54e4…`.

## Preflight
1,941 requests: mean 2,274 tokens, median 1,956, p90 4,209, p95 4,769, max 7,932 — all well inside the 400,000-token model context limit; 0 cases exceeding it, no truncation.

## Execution
1,941/1,941 calls completed, 0 provider errors, 4 parse failures (counted as benchmark failures, not rerun). Wall time 39.7 min. Spend **$3.9035**. Pre-run ledger $3.51797 → **final ledger $7.42152**.

## Merge integrity (all assertions passed before any headline metric)
Merged rows 2,091; unique case IDs 2,091; duplicates 0; missing 0; extra 0; gold-label counts exactly Entailment 968 / Contradiction 220 / NotMentioned 903.

## Full GPT-5-mini metrics (n=2,091; frozen before failure inspection — sha256 in `final_full_test_metrics.sha256`)
| Metric | Value |
|---|---|
| Accuracy | 77.6% |
| Macro-F1 | 0.727 |
| Entailment recall | 92.0% (891/968, Wilson 90.2–93.6) |
| **Contradiction recall** | **75.5% (166/220, Wilson 69.4–80.7)** |
| NotMentioned recall | 62.7% (566/903, Wilson 59.5–65.8) |
| Joint success | **74.6% (1,560/2,091)** |
| Joint by class | E 86.5% · C 71.8% · NM 62.6% |
| Evidence recall / precision | 93.3% / 74.7% |
| Source-valid quote rate | 98.0% |
| Parse | 2,087 strict / 0 recovered / **4 invalid** |
| Ops | input tok mean 2,279 · output tok mean 729 · latency mean 7,312 ms · cost/case $0.00202 |

## Full Contradiction result (all 220)
Correct 166/220, recall 75.5%; joint correct 158/220; C→E 50, C→NM 4, invalid 0. 62 joint failures; of the 50 C→E misclassifications with any quoted evidence, 38 quoted a clause overlapping the gold span (correct clause, wrong label) — consistent with E17's 150-case pattern, now confirmed at full scale.

## Direct full-population comparison (n=2,091, identical TEST cases)
| | Accuracy | Macro-F1 | E recall | C recall | NM recall | Joint | Evidence R/P | Source-valid | Runtime | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| Rule | 59.0% | 0.479 | 39.3% | 16.8% | 90.5% | 50.1% | 29.3%/60.8% | n/a | 0.18s | $0 |
| Qwen ctx16k | 49.9% | 0.431 | 46.3% | 25.5% | 59.7% | 39.7% | 35.3%/35.9% | 70.3% | 7.13h | $0 (API; local compute/time NOT monetized) |
| **GPT-5-mini FULL** | **77.6%** | **0.727** | **92.0%** | **75.5%** | **62.7%** | **74.6%** | 93.3%/74.7% | 98.0% | ~40 min (this run) | **$4.23 total** ($0.00202/case) |

## Paired GPT vs Qwen (n=2,091, identical cases)
Classification: both correct 780, GPT-only correct 843, Qwen-only correct 263, both wrong 205. **McNemar exact p ≈ 2.8×10⁻⁷¹** — GPT's advantage is not noise.
Joint: both correct 579, GPT-only 981, Qwen-only 251, both wrong 280. **p ≈ 3.1×10⁻¹⁰²**.
By class:
- Entailment (n=968): classification p≈1.4×10⁻¹⁰³; joint p≈2.7×10⁻¹⁴⁶ — GPT dominates.
- Contradiction (n=220): classification both-correct 37, GPT-only 129, Qwen-only 19, both-wrong 35, p≈2.8×10⁻²¹; joint p≈2.8×10⁻²⁷ — GPT clearly stronger, but Qwen recovers 19 cases GPT misses.
- NotMentioned (n=903): both-correct 325, GPT-only 241, Qwen-only 214, both-wrong 123, **p≈0.22–0.24 — not significant**; the two systems are roughly comparable on NotMentioned, each with a real but similarly-sized set of unique correct/wrong cases.

## E17 sample vs. full population — how representative was the 150-case balanced sample?
| | Accuracy | Joint | E recall | C recall | NM recall |
|---|---|---|---|---|---|
| A. E17 balanced n=150 | 78.0% | 76.7% | 92.0% | 78.0% | 64.0% |
| B. E17 standardized estimate | 78.4% | 78.0% | — | — | — |
| C. Merged full population n=2,091 | 77.6% | 74.6% | 92.0% | 75.5% | 62.7% |
The balanced sample and its standardized estimate were close to the full-population result (within ~1–3.4 points on every headline number) — the original 150-case protocol was reasonably representative, though it slightly overestimated joint success (76.7%/78.0% vs the true 74.6%).

## Failure taxonomy (full population, n=531 joint failures; analysis-only, after metrics were frozen)
NotMentioned over-inference 323; correct-label/evidence-mismatch 43; source-validation issue 36; reasoning failure or missed provision (Contradiction) 48; missed provision (Entailment/no evidence) 39; other reasoning failure (Entailment) 42. Consistent in shape with E17's 150-case taxonomy (NotMentioned over-inference was the largest bucket there too) — the pattern generalizes.

## E15 / E16 disclosures (unchanged)
E15: no effective selective routing policy met the frozen workload/safety criteria; R3 remains unused on TEST. E16: the candidate remains "evidence-grounded but not prompt-injection-hardened"; no patch was made before, during, or after E17B.

## Methodological disclosure
The original 150 hosted TEST predictions were obtained in E17 under the predeclared balanced sampling protocol and were never rerun. After E17 completed, additional budget was made available and the remaining 1,941 TEST cases were evaluated under the identical frozen system to permit a direct full-population comparison with the existing rule and Qwen runs. No system component (model, prompt, architecture, parser, evaluator, validator, routing) was changed after seeing E17's results. The merged 2,091-case result is therefore a **post-freeze completion of TEST coverage**, not a newly blind evaluation and not a tuning run.

## Protocol deviations
None to the frozen model/prompt/architecture/parser/evaluator/validator/routing. Two API credentials were used purely to share execution load (never an experimental arm, never recorded per-case, never persisted to any file — verified by `tests/test_e17b_full_test_completion.py`). No prior $5 budget plan applied to this run per explicit user authorization (real spend tracked and reported in full: $3.9035, final project ledger $7.42152).
