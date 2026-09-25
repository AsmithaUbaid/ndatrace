# Test Coverage Summary

One table answering "what have we actually tested, and what did we find" without hunting across
five files. Every number below is pulled from a real saved result file, cited in
the last column — nothing here is estimated or reconstructed from memory.

**Note on scope**: this file did not exist before this pass — it is a new document, not a
correction of a prior version. It already reflects the catalogue correction (10
non-single-case aggregate/structural entries removed from Categories 4–7 — see
`docs/evaluation_case_design.md`), so the counts below are the final, corrected ones.

| Case collection | Size | Executed against current pipeline? | Result | Source |
|---|---:|---|---|---|
| Official test set (final, locked) | 2,091 | Yes | Full-context 81.2% acc / RAG 78.7% / RAG+agent 77.7%; Contradiction recall 59.1%/63.6%/60.5% | `results/final/run_T041_final_test_*.jsonl` |
| Independent validation check | 340 | Yes | Full-context 80.6% acc / RAG 80.3% / RAG+agent 77.6% (statistically indistinguishable FC vs RAG, p=1.000) | `results/final/run_AV01_architecture_validation_*.jsonl` |
| Dev sample (reused, adaptive) | 150 | Yes (repeatedly, across every tuning decision) | See `docs/decisions.md` for the full per-decision breakdown — not a single number, by design | `docs/decisions.md`, various `results/runs/*.jsonl` |
| **Cat. 1 — Benchmark/ordinary** | 30 | Yes | 24/30 = 80.0% | `data/golden_battery_pipeline_verification.json` |
| **Cat. 2 — Regression/negative** | 15 | Yes | 10/15 = 66.7%; found the 100%-failure exception/carve-out weakness (4/4 cases 034/038/039/040) | `data/golden_battery_pipeline_verification.json`, `docs/decisions.md` ADR-011 |
| **Cat. 3 — Robustness/injection** | 11 | Yes | 11/11 resisted under the current prompt (was 9/10 before the fix) | `docs/decisions.md` ADR-004 |
| **Cat. 4 — LLM behaviour** | 7 | Yes (re-run against current pipeline) | 7/7 pass | `docs/evaluation_case_design.md` §3 |
| **Cat. 5 — Agent behaviour** | 7 | Yes (re-run against current pipeline) | Consistent with the dedicated agent experiment: 6/67 recovery, 3/67 regression on real REVIEW-routed cases; no new regressions found in this re-run | `docs/evaluation_case_design.md` §4, `docs/decisions.md` ADR-007 |
| **Cat. 6 — Confidence/abstention** | 2 | No — documents a design decision, not re-run per-case | Illustrative real cases (076: high-confidence-correct; 077: high-confidence-wrong/overconfidence) backing the AUROC 0.657–0.660 finding | `docs/evaluation_case_design.md` §5, `docs/decisions.md` ADR-005 |
| **Cat. 7 — Evidence quality** | 4 | Yes (re-run against current pipeline) | 4/4 pass | `docs/evaluation_case_design.md` §5 |
| **Cat. 8 — Data leakage prevention** | 21 pytest tests | Yes (runs with every test suite execution) | All pass; static/code-level, unaffected by prompt changes | `tests/test_data_leakage.py` |
| **Cat. 9 — API & error handling** | 5 | Yes (live backend checks) | Case 092 verified live (422 on missing field); case 095 found and fixed a real gap (no per-hypothesis error isolation); 091/093/094 covered by existing retry/health tests | `docs/evaluation_case_design.md` §6 |
| **Cat. 10 — Logging & security** | 5 | Yes (real 33,231-line log audit) | 3/5 pass (0 API key exposures, 0 NDA text leaks, 100% valid JSON); 2/5 correctly blocked (request/trace ID linking not built) | `data/reliability_results.json` |

## What this leaves genuinely untested or unresolved

- **Categories 5 and 6's remaining cases were re-run/reviewed against the current pipeline, before the
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
