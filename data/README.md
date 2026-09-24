# NDATrace Data

## ContractNLI Dataset

- **Source:** https://stanfordnlp.github.io/contract-nli/
- **License:** CC BY-SA 4.0
- **Size:** 607 NDAs with 17 confidentiality hypotheses each. Splits: dev (used for all development
  experiments), test (2,091 examples — 123 documents × 17 hypotheses — reserved for the final
  locked evaluation only, see `../docs/evaluation_protocol.md`).
- **Download:** Run `bash scripts/download_data.sh`
- **Location:** `data/contractnli/` (`dev.json`, `test.json`, `train.json`)

## Golden / regression / robustness case files (`data/golden/`)

The dataset role and purpose of each category is documented in full in
`../docs/evaluation_case_design.md` — this section only lists what actually exists and its real
case count, since an earlier version of this file undercounted it (it described a "12 hand-picked
regression test cases" set that predates the current, larger case collection):

| File | Cases | Category |
|---|---|---|
| `golden_cases.json` | 30 | Benchmark/regression — ordinary cases |
| `negative_cases.json` | 15 | Regression — wrong-behaviour-catching |
| `injection_cases.json` | 11 | Robustness — prompt injection (grew from 10 to 11 after a real vulnerability was found in production use, see `../docs/decisions.md` ADR-004) |
| `llm_behaviour_cases.json` | 10 | LLM output-quality behaviour |
| `agent_cases.json` | 10 | Selective-agent behaviour |
| `confidence_cases.json` | 5 | Confidence/abstention calibration |
| `evidence_quality_cases.json` | 5 | Evidence-quality checks |
| `logging_security_cases.json` | 5 | Logging/security checks |

**Legacy note:** an earlier, smaller 12-case regression set (referenced in older project notes) was
superseded by the current 30-case `golden_cases.json` battery — the old set was never checked into
this repository under its own filename, so there is no separate legacy file to preserve here; this
note exists so the discrepancy between old documentation and the current file isn't mistaken for
data loss.

Two further categories (data-leakage prevention, API/error handling) are implemented as code-level
tests rather than JSON case files — see `../docs/evaluation_case_design.md`'s "Where each category
lives now" table.

## Split membership discipline

Every file above draws exclusively from `data/contractnli/dev.json`. None reference or were built
from `test.json` — see `../docs/evaluation_protocol.md` for why the test split is reserved for the
one-time final evaluation only, and `tests/test_data_leakage.py` for the automated checks that
enforce dev/test separation.

## Other files in this directory

Everything else under `data/` (`*.json` files not in `golden/`, e.g. `agent_experiment.json`,
`retrieval_experiment_results.json`, `performance_results.json`) is a saved output of a specific
experiment or audit script, referenced by name from `docs/decisions.md` and `docs/experiments.md`
alongside the script that produced it. `data/contractnli/README.md` documents the raw dataset
files themselves.
