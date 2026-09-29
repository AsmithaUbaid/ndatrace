# E21 — OWASP LLM Top 10 (2025) Security Evaluation

Baseline security evaluation of the **frozen** NDATrace RAG runtime (BM25 top-20 → L-12
cross-encoder rerank → top-5 context → `openai/gpt-5-mini` + `prompts/reconstruction_v2/gpt_p0.txt`
→ deterministic parser → evidence validator → human reviewer) against all ten OWASP LLM Top 10
(2025) categories. This is a project security evaluation, not an OWASP certification.

No frozen-runtime code, prompt, or config was changed as part of this experiment. Nothing was
committed or pushed.

## Files

- `manifest.json` — freeze record: git branch/SHA, model, prompt path+SHA1, retrieval
  hyperparameters, parser/validator identifiers, agent status, live OpenRouter budget check.
- `test_plan.md` — per-category test design.
- `fixtures/` — attack/test fixtures (prompt injection, system-prompt leakage, retrieval
  poisoning, malformed-output, resource-exhaustion checklist).
- `results/static_results.json` — LLM03, LLM06 (code/config inspection, $0).
- `results/deterministic_results.json` — LLM02, LLM04, LLM05, LLM08, LLM09, LLM10 ($0, local
  compute or reused evidence only).
- `results/hosted_results.jsonl` — every new paid model call made by this experiment (LLM01
  RAG-path check + LLM07), one JSON line per call.
- `results/category_summary.json` — the 10-row OWASP category table.
- `results/final_report.json` — everything above, merged, plus the budget ledger for this run.
- `summary.md` — narrative write-up, findings, remediation backlog.

## Reproducing

```
python scripts/run_e21_owasp.py   # re-runs everything; makes new (small, budget-capped) hosted calls
pytest tests/test_e21_owasp.py -v # deterministic-only regression tests, no hosted calls
```

## Headline result

**10/10 OWASP categories assessed; 3 PASS, 5 PARTIAL, 2 FAIL, 0 NOT APPLICABLE.**
(See `results/category_summary.json` / `summary.md` for the full table.) This is not "10/10
secure" — it is a count of how many categories were assessed, with real, disclosed outcomes per
category.

## Hosted spend

Live OpenRouter balance was checked (`GET /auth/key`, free) before any call:
$10.00 limit, ~$9.13 already used project-wide, **~$0.87 remaining**. This experiment enforced its
own hard ceiling of $0.30 in code (`HOSTED_HARD_CEILING_USD` in `scripts/run_e21_owasp.py`) and
actually spent **~$0.055 total across all runs of the script** — reusing E16 and E20 evidence for
everything that didn't need a fresh call.
