# Test Coverage Summary

One table answering "what have we actually tested, and what did we find" without hunting across
five files. Every number below is pulled from a real saved result file, cited in
the last column — nothing here is estimated or reconstructed from memory.

**Note on scope**: this file did not exist before this pass — it is a new document, not a
correction of a prior version. It already reflects the catalogue correction (10
non-single-case aggregate/structural entries removed from Categories 4–7 — see
`docs/evaluation_case_design.md`), so the counts below are the final, corrected ones.

**Note on era**: the "Reconstruction-v2 final TEST result" row below is the current, canonical,
locked result. Every row after it (the independent validation check, the dev sample, and Categories
1–10) documents the **pre-reconstruction pipeline's** own test-coverage story (RAG + selective
agent, `google/gemini-2.5-flash-lite`) — real, historically meaningful work, but **not** the final
selected architecture. See `docs/decisions.md`/`docs/experiments.md` for that lineage in full, and
`docs/architecture.md` for why RAG/the agent were not selected for reconstruction-v2.

| Case collection | Size | Executed against current pipeline? | Result | Source |
|---|---:|---|---|---|
| **Reconstruction-v2 final TEST result** | **2,091** | Yes | **GPT-5-mini + P0 + FULL: accuracy 77.6%, macro-F1 0.727, joint 74.6%, Contradiction recall 75.5%, NotMentioned recall 62.7%.** Comparators (same population): Rule 59.0%/joint 50.1%/C-recall 16.8%; local Qwen (ctx16k) 49.9%/joint 39.7%/C-recall 25.5%. The original E17 run used a balanced n=150 hosted sample (now superseded for headline metrics); E17B completed the remaining 1,941 TEST cases to produce this full-population result. | `results/final/reconstruction_v2/{gpt,rule,qwen}_full_test_metrics.json`, `full_test_comparison.csv` |
| *Pre-reconstruction* official test set (historical, superseded) | 2,091 | Yes (pre-reconstruction pipeline) | Full-context 81.2% acc / RAG 78.7% / RAG+agent 77.7%; Contradiction recall 59.1%/63.6%/60.5% | `results/final/legacy/run_T041_final_test_*.jsonl` |
| *Pre-reconstruction* independent validation check | 340 | Yes (pre-reconstruction pipeline) | Full-context 80.6% acc / RAG 80.3% / RAG+agent 77.6% (statistically indistinguishable FC vs RAG, p=1.000) | `results/final/legacy/run_AV01_architecture_validation_*.jsonl` |
| Dev sample (reused, adaptive) | 150 | Yes (repeatedly, across every tuning decision) | See `docs/decisions.md` for the full per-decision breakdown — not a single number, by design | `docs/decisions.md`, various `results/runs/*.jsonl` |
| **Cat. 1 — Benchmark/ordinary** | 30 | Yes (pre-reconstruction pipeline) | 24/30 = 80.0% | `data/golden_battery_pipeline_verification.json` |
| **Cat. 2 — Regression/negative** | 15 | Yes (pre-reconstruction pipeline) | 10/15 = 66.7%; found the 100%-failure exception/carve-out weakness (4/4 cases 034/038/039/040) | `data/golden_battery_pipeline_verification.json`, `docs/decisions.md` ADR-011 |
| **Cat. 3 — Robustness/injection** | 11 | Yes (pre-reconstruction pipeline) | 11/11 resisted under the pre-reconstruction prompt (was 9/10 before the fix) | `docs/decisions.md` ADR-004 |
| **Cat. 4 — LLM behaviour** | 7 | Yes (re-run against the pre-reconstruction pipeline) | 7/7 pass | `docs/evaluation_case_design.md` §3 |
| **Cat. 5 — Agent behaviour** | 7 | Yes (re-run against the pre-reconstruction pipeline) | Consistent with the dedicated agent experiment: 6/67 recovery, 3/67 regression on real REVIEW-routed cases; no new regressions found in this re-run | `docs/evaluation_case_design.md` §4, `docs/decisions.md` ADR-007 |
| **Cat. 6 — Confidence/abstention** | 2 | No — documents a design decision, not re-run per-case | Illustrative real cases (076: high-confidence-correct; 077: high-confidence-wrong/overconfidence) backing the AUROC 0.657–0.660 finding | `docs/evaluation_case_design.md` §5, `docs/decisions.md` ADR-005 |
| **Cat. 7 — Evidence quality** | 4 | Yes (re-run against the pre-reconstruction pipeline) | 4/4 pass | `docs/evaluation_case_design.md` §5 |
| **Cat. 8 — Data leakage prevention** | 21 pytest tests | Yes (runs with every test suite execution) | All pass; static/code-level, unaffected by prompt changes | `tests/test_data_leakage.py` |
| **Cat. 9 — API & error handling** | 5 | Yes (live backend checks, pre-reconstruction pipeline) | Case 092 verified live (422 on missing field); case 095 found and fixed a real gap (no per-hypothesis error isolation); 091/093/094 covered by existing retry/health tests | `docs/evaluation_case_design.md` §6 |
| **Cat. 10 — Logging & security** | 5 | Yes (real 33,231-line log audit, pre-reconstruction pipeline) | 3/5 pass (0 API key exposures, 0 NDA text leaks, 100% valid JSON); 2/5 correctly blocked (request/trace ID linking not built) | `data/reliability_results.json` |

> **Security note:** Cat. 3 (Robustness/injection) and Cat. 10 (Logging & security) above are **pre-reconstruction pipeline** results and must not be interpreted as the current reconstruction-v2 security result. The current red-team result is **E16: 4/11 injection-type attacks succeeded** (2 label hijacks, 2 output-format compliances; clean Joint 85% -> attacked Joint 75%) -- see `docs/experiment_registry.md`'s E16 row and `docs/decisions.md`'s E16 entry. Source-valid evidence does not imply trusted evidence.

## What this leaves genuinely untested or unresolved

- **Categories 5 and 6's remaining cases were re-run/reviewed against the pre-reconstruction pipeline, before the
  catalogue correction** — they were not re-verified again after the 10 aggregate/structural entries
  were removed, though removing those entries doesn't change what the remaining real cases found.
- **Long-document scalability** — no case collection here, or anywhere in the project, tests
  documents longer than ContractNLI's own NDAs.
- **The selective agent's net effect is still unresolved** — Category 5's real re-run and the
  official test set (2,091 cases) point in different directions on whether the agent helps or hurts;
  see `docs/decisions.md` ADR-007 for the full, unresolved picture.
- **Categories 1, 2, 4, 5, 6, 7 all draw exclusively from the development split** — none have an
  equivalent on the official test split, so their findings (especially the exception/carve-out
  weakness) are not yet confirmed to generalize to held-out documents.
