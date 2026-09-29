# E22 — Targeted Security Remediation Verification

Post-remediation verification for the two categories E21 marked **FAIL**: LLM01 (Prompt Injection)
and LLM10 (Unbounded Consumption). E21 is the frozen baseline and was not modified, rescored, or
rewritten by this experiment. E22 does not rerun the full OWASP suite.

**E21 found the weakness. E22 verifies the mitigation independently — it does not claim E21 "now
passes."**

## Controls added

- **LLM01**: `pipeline/injection_guard.py`, a deterministic regex-based detector wired into
  `pipeline/final_review.py`. When the retrieved NDA context contains instruction-override,
  fake-role-marker, or response-format-hijacking text, the result is flagged
  `security_review_required=True` and forced to `needs_human_review=True`. The model call is NOT
  blocked — this fails **closed** to human review, it does not claim to prevent the attack.
- **LLM10**: `backend/models.py` (request length caps), `pipeline/cost_guard.py` (per-request cost
  ceiling + a real, enforced `settings.max_budget_usd` check — the exact "declared but never
  enforced" gap E21 found), `backend/rate_limit.py` (in-process concurrency cap + sliding-window
  rate limit, no new infrastructure dependency).
- **LLM03 (optional)**: `python-dotenv` 1.0.1→1.2.2, `python-multipart` 0.0.20→0.0.22 (low-risk
  patch/minor bumps). CVE count 38→34. Remains PARTIAL — three packages with real compatibility
  risk (`starlette`, `pytest`, `transformers`) were deliberately NOT upgraded.
- **LLM02**: not remediated this pass — see `test_plan.md` for why.

## Files

- `manifest.json` — freeze record for this remediation pass (git SHA, live budget check).
- `test_plan.md` — pass criteria, fixed BEFORE any hosted confirmation call.
- `results/llm01_prompt_injection.json` — local ($0) regression + hosted confirmation.
- `results/llm10_unbounded_consumption.json` — 17 local ($0) checks.
- `results/llm03_supply_chain.json` — before/after CVE delta.
- `results/hosted_confirmation.jsonl` — the 5 real hosted calls made by this experiment.
- `results/final_report.json` — everything above, merged.
- `summary.md` — narrative write-up.

## Reproducing

```
python scripts/run_e22_security_remediation.py   # re-runs everything; 5 small, budget-capped hosted calls
pytest tests/test_e22_security_remediation.py -v # no hosted calls
```

## Headline result

- **LLM01 targeted regression: PARTIAL.** The guard has 0/32 false positives (never flags ordinary
  legal language) and correctly quarantined all 5 hosted confirmation cases (including the exact
  case that succeeded in E21). Against E16's more varied real attack corpus (F1–F4, 11 cases) it
  detects 4/11 — including both of E16's two actual documented attack successes — but misses 7/11
  that use phrasing outside its pattern set (e.g. ChatML-style role tags, "Reviewer request:").
  This is honestly reported as PARTIAL, not rounded up.
- **LLM10 targeted regression: PASS.** All 17 local checks (length caps, cost ceiling, budget
  enforcement, rate limit, concurrency) behave as specified, with zero model calls made for any
  rejected request.
- New hosted spend: **~$0.012 total** across all runs (ceiling $0.10; live remaining balance was
  ~$0.84–0.87 throughout, checked before each run).
