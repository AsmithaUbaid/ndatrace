# `evaluation/` — the offline scoring harness

This is the **offline** evaluation code: it knows gold labels and gold evidence, and scores
predictions against them. It is deliberately separate from the **runtime** evidence check
(`pipeline/evidence_validator.py`), which never sees gold data — a result shown to a reviewer is
checked for internal consistency (does the cited text actually appear in the NDA?), not graded
against an answer key. Two tiers, by design: offline scoring can be wrong without affecting what
a reviewer sees; runtime validation can't rely on knowing the "right" answer because in
production there isn't one on file.

## What each metric means, and how to rerun scoring

| Metric | Definition | Why it's reported |
| --- | --- | --- |
| Accuracy | Predicted label == gold label, overall. | Standard baseline comparison point. |
| Macro-F1 | F1 averaged equally across Entailment/Contradiction/NotMentioned (not weighted by class size). | Prevents the majority class (Entailment) from hiding poor performance on the rarer, higher-stakes classes. |
| **Joint correctness** | Label correct **and** cited evidence matches a gold span (`evidence_matching.py`). | The project's primary metric — a right label with fabricated or wrong evidence is not "evidence-grounded," so plain accuracy alone overstates quality. |
| Contradiction recall | Of actual Contradiction cases, how many are correctly flagged. | Missing a real conflicting clause is the costliest failure mode for a reviewer aid — worth tracking even though it's one class among three. |

Full formal definitions, edge cases, and audit trail: `docs/evaluation_protocol.md` (sections
11–16). To rerun scoring from saved predictions (no paid calls): see the repository root
README's [Reproducibility](../README.md#reproducibility) section, or run any single script
listed below directly, e.g. `python scripts/analyze_e20_rag_test.py`.

**Target vs. achieved:** the project's pre-registered target and the measured result are compared
in the root README's ["Metrics: targeted vs. reached"](../README.md#key-results) table — not
duplicated here to avoid two copies drifting apart.

## Checked-in eval case battery

The regression/robustness/behavioural case files this harness scores live in `data/golden/`
(golden, negative, injection, LLM-behaviour, agent, confidence, evidence-quality — 76 cases
total), not in this directory. Design rationale per category: `docs/evaluation_case_design.md`.
Pass/fail results exist for every category in `docs/test_coverage_summary.md`, but those numbers
were measured against the **legacy pipeline** (RAG + selective agent), not the current final
architecture — read that distinction before citing any number from it. These case files are
development-time regression/robustness checks, not the project's headline benchmark; the headline
numbers are the official ContractNLI TEST results this harness's `harness.py`/`metrics.py`
compute (see `../README.md`'s Metrics section).

## Core harness

| Module | What it does |
| --- | --- |
| `harness.py` | Runs predictions through the metrics, stores results as append-only JSONL, snapshots config for reproducibility, supports resuming an interrupted run. |
| `metrics.py` | Pure metric functions (accuracy, macro-F1, Joint correctness, recall/precision, etc.) — predictions + gold in, numbers out. No I/O, no network calls, unit-testable on synthetic data. |
| `schemas.py` | Pydantic models for predictions, results, and configs — the contract every experiment's JSONL output is written against. |
| `scorer.py` | Normalizes whatever shape the pipeline's internal result object has into the `Prediction` schema `harness.py`/`metrics.py` expect. |
| `evidence_matching.py` | Evidence→gold-span matching used for scoring (`evidence_evaluator_v1`/`v2`). v1 is exact-substring, kept only so old results stay reproducible; v2 (frozen in E13B) adds a formatting-normalized fallback mapped back to original character offsets. Deterministic, no model calls. |

## Experiment-specific reusable logic

These hold the provider-agnostic input-construction and output-parsing logic for a few
experiments, so the real runner script and the analysis notebook for the same experiment both
import one shared implementation instead of two copies that could drift apart.

| Module | Experiment | What it does |
| --- | --- | --- |
| `oracle.py` | E01 | Builds the model-visible input for one Oracle case (gold evidence handed directly, never `gold_label`), parses the response. |
| `prompt_selection.py` | E03 | Builds the user message for a `TRAIN_PROMPT_v1` case under a given prompt version; reuses `oracle.py`'s output parser rather than duplicating it. |
| `retrieval_eval.py` | E06 | Builds the evidence-bearing TRAIN universe, runs a retrieval config against it, scores with the frozen evidence-hit semantics from E00. No model/API calls. |
| `structured_output.py` | E05/E07, **also live in production** | Deterministic parser that recovers a valid `{"label", "evidence"}` object from a response that has trailing free-text after it (a real, disclosed long-context issue in one local model) — strict parsing would otherwise reject an actually-correct classification. This is the same parser `pipeline/final_review.py` calls at runtime, not just an offline tool. |

## Other

- `budget.py` — pure cost-forecasting/pre-run gate functions; reads `configs/pricing/*.yaml`, does arithmetic, makes no network calls. Any future hosted-run script should import this to check itself against the planning budget before spending real money.

## Reading this as an AI agent

Every file above has its own module-level docstring with the same information in more depth —
this file is the index, not a replacement for reading them. Start with `schemas.py` to understand
the data shapes, then `harness.py` for how scoring actually runs, then whichever
experiment-specific module matches what you're looking at.
