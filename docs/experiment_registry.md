# Experiment Registry — Reconstruction-v2

Rules for using this registry are in `docs/experiment_protocol.md`. Every experiment here
starts `PLANNED` and is not authorized to run by virtue of being listed — see
`docs/project_contract.md` for what's actually approved to proceed.

## Reconstruction-v2 sequence (provisional IDs)

| ID | Name | Status |
|---|---|---|
| E00 | Dataset and split validation | **COMPLETE** — local-only, no model calls; see `experiments/E00_dataset_validation/summary.md` |
| E00B | Budget, token and runtime forecast | **COMPLETE** — live pricing verified, historical ledger + token estimates + hosted forecast + runtime forecast + budget plan all produced, zero model calls; see `experiments/E00B_budget_forecast/summary.md` |
| E01 | Oracle reasoning ceiling | **COMPLETE** — all 4 frozen models (llama3.2:3b, qwen2.5:7b-instruct, gemini-2.5-flash-lite, gpt-5-mini) ran the full 300-case TRAIN_ORACLE_v1 manifest; Contradiction confirmed as the clearest reasoning bottleneck (25-82% recall across models, even with perfect evidence) — Entailment reasoning relatively strong, NotMentioned structurally advantaged and not a reasoning-ceiling measure; primary local model **frozen** (qwen2.5:7b-instruct); hosted reference **gpt-5-mini** (stronger reasoning ceiling), with gemini-2.5-flash-lite preserved as the economical hosted candidate; total hosted spend $0.1178; see `experiments/E01_oracle/summary.md` |
| E02 | Model screening | **SKIPPED / SATISFIED BY E01** — E01 already performed a controlled comparison of 2 local and 2 hosted models using the same Oracle manifest, prompt semantics, and output schema; a separate model-screening experiment would duplicate the question already answered. Frozen from E01: primary local model `qwen2.5:7b-instruct`, hosted model for later comparison `openai/gpt-5-mini`. Gemini 2.5 Flash Lite preserved only as an economical hosted candidate/result from E01 — not carried into core downstream experiments unless a later cost-quality experiment explicitly requires it. See `experiments/E01_oracle/summary.md`. |
| E03 | Prompt selection | **PENDING — resequenced after E06.** Stage B began under a full-context condition (P0: 88/150 cases run, then stopped cleanly; P1/P2 never started) — SUPERSEDED/INVALIDATED BEFORE COMPLETION, no metric computed or used. Reason: full-context is valid for A1 but doesn't establish transfer to A2/A3's fragmented retrieved-chunk context, and no retrieval config is frozen yet. E03 resumes after E06 freezes retrieval, using identical frozen retrieved context across P0/P1/P2. Manifest (TRAIN_PROMPT_v1) and prompt files (P0/P1/P2) retained for reuse. See `experiments/E03_prompt_selection/summary.md`. |
| E04 | Rule baseline (A0) | PLANNED |
| E05 | Full-context baseline (A1) | PLANNED |
| E06 | Retrieval optimisation | PLANNED |
| E07 | Standard RAG (A2) | PLANNED |
| E08 | RAG failure analysis | PLANNED |
| E09 | Agent justification | PLANNED |
| E10 | Agent/tool-policy selection | PLANNED |
| E11 | Selective agent evaluation (A3) | PLANNED |
| E12 | Four-architecture comparison (A0–A3) | PLANNED |
| E13 | Abstention / review-routing calibration | PLANNED |
| E14 | Full local blind evaluation | PLANNED |
| E15 | Hosted-vs-local comparison | PLANNED |
| E16 | Robustness evaluation | PLANNED |
| E17 | Security / red-team evaluation | PLANNED |
| E18 | Production / load / observability tests | PLANNED |

These IDs are provisional labels for future work, not permission to run anything. Each
becomes non-`PLANNED` only when it actually runs, per the protocol.

## Historical evidence / prior experiments (T-series — not reconstruction-v2)

The following already-completed work is preserved as historical exploratory evidence. It
informed the project contract but is **not** the reconstruction-v2 record, and reconstruction
experiments (above) must independently re-derive their own conclusions rather than assume
these:

| Historical area | Where recorded |
|---|---|
| Dataset/harness (T005–T008) | `docs/decisions.md`, `results/runs/run_B0*` |
| Oracle + model bake-off (T016–T017, ADR-001) | `docs/decisions.md` ADR-001 |
| Retrieval tuning, 10 rounds (T020–T023, ADR-002) | `docs/decisions.md` ADR-002 |
| Standard RAG E2E (T024, ADR-003) | `docs/decisions.md` ADR-003 |
| Prompt versions v1–v6 (T018, ADR-004) | `docs/decisions.md` ADR-004 |
| Confidence/abstention design (T026–T027, ADR-005) | `docs/decisions.md` ADR-005 |
| Routing-signal independence fix (ADR-006) | `docs/decisions.md` ADR-006 |
| Agent include/exclude (T028–T030, ADR-007) | `docs/decisions.md` ADR-007 |
| Full-context ceiling (T015, ADR-008) | `docs/decisions.md` ADR-008 |
| Architecture freeze — historical only (T031, ADR-009) | `docs/decisions.md` ADR-009 |
| Final locked test-set eval (T041, ADR-010) | `docs/decisions.md` ADR-010, `results/final/run_T041_*.jsonl` |
| Golden battery Categories 1–2 (ADR-011) | `docs/decisions.md` ADR-011 |
| Full chronological ledger | `docs/experiments.md` |
| Original day-by-day planning (not used for execution order) | `docs/archive/initial_project_plan.md` |

**ADR-009 in particular is historical evidence only** — per `docs/project_contract.md`, it is
not treated as the architecture freeze for reconstruction-v2. E12 independently re-evaluates
A0–A3.
