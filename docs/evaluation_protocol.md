# Evaluation Protocol

This document defines what each dataset/case collection in NDATrace is for, whether it's still
open for tuning, and what the metrics mean. It exists because the project reused one 150-case dev
sample adaptively across many experiments, and reviewers need to know exactly which numbers are
"we tuned against this" vs. "this is the untouched, final answer."

## Dataset roles

| Data | Source | Role | Can tune on it? |
|---|---|---|---|
| Dev split (full) | `data/contractnli/dev.json`, 614 Entailment/Contradiction cases used for retrieval sweeps | Retrieval-only experiments (chunking, reranking, top-K) — no LLM calls | Yes — this is exploration |
| 150-case dev sample (seed=42) | Stratified sample of `dev.json` | Oracle, model selection, RAG e2e, prompt tuning (v1–v6), confidence/abstention, agent experiments | **Yes, repeatedly reused** — see the warning below |
| Golden regression battery (`data/golden/golden_cases.json`, `negative_cases.json`, 45 cases) | Hand-picked `dev.json` documents | Catches known behavioural regressions after a change (e.g. a prompt version) | Yes — these exist to be run after every change, by design |
| Robustness/system cases (`data/golden/injection_cases.json`, `llm_behaviour_cases.json`, `agent_cases.json`, `confidence_cases.json`, `evidence_quality_cases.json`, `logging_security_cases.json`) | Synthetic or hand-picked `dev.json` cases | Tests system *behaviour* (injection resistance, error isolation, log hygiene), not benchmark accuracy | Yes — same reasoning as regression cases |
| Architecture-validation set | — | An independent sample, untouched by any tuning decision, used once to confirm the frozen architecture choice before the final test run | **Does not currently exist.** Every architecture comparison in `docs/decisions.md` (ADR-007, ADR-008, ADR-009) was run on the same 150-case dev sample used for every earlier tuning decision. This is a real, open gap — see "What's missing" below. |
| Official test split (`data/contractnli/test.json`, 2,091 cases) | ContractNLI's own test partition | The final, locked evaluation (T041), run once after architecture freeze | **No — never tune on this.** Any change made after looking at a test-set result invalidates the freeze. |

### What's missing: an architecture-validation set

The plan called for the architecture freeze (ADR-009) to be confirmed by evidence not used for any
of the tuning decisions that led to it. In practice, every one of Rule/Full-context/RAG/RAG+agent's
compared numbers (59.9% / 91.3% / 88.0% / 90.0%) came from the same 150-case dev sample that also
drove the model choice, prompt version, and retrieval configuration decisions. There is no
untouched intermediate sample between "development" and "final locked test." This is disclosed
here rather than glossed over — it means the architecture freeze itself rests on adaptively-reused
development evidence, and the test-set run (T041) is the first genuinely independent check of it.

## Freeze protocol

Before the final test-set run (T041), the following were locked and not changed based on test-set
results:

- Model: `google/gemini-2.5-flash-lite` (hosted), Llama 3.2 3B via Ollama (local)
- Prompt version: at the time T041 first ran, this was v2/`agent_step_v1.txt` — **not** the current
  v6/`agent_step_v2.txt` default (the v6 security fix was found and adopted the same day T041 ran,
  after the run had started). See `docs/decisions.md` ADR-004 and ADR-010 for the exact timeline.
  This means the T041 numbers currently in the repository predate the security fix and should be
  read as "final under the pre-v6 configuration," not "final under everything currently shipped."
- Retrieval configuration: sentence chunking → mpnet → retrieve-20 → rerank L-12 → top-7 →
  rule-boost RRF fusion (ADR-002)
- Routing: rule-agreement-based ACCEPT/REVIEW (ADR-005), with the decoupled independent signal
  fix already in place (ADR-006)
- Agent: 5 tools, bounded ReAct loop (ADR-007)
- Evaluation scripts: `scripts/run_final_test_evaluation.py`

## Metrics

| Metric | Definition | Used for |
|---|---|---|
| Accuracy | Fraction of exactly-correct 3-way labels | Headline comparison across architectures |
| Macro-F1 | Unweighted average F1 across Entailment/Contradiction/NotMentioned | Guards against a majority-class-dominated accuracy number |
| Contradiction recall (+ 95% Wilson CI) | Recall on the Contradiction class alone, with a confidence interval given the small class size (~11% of labels) | Headline risk metric — added after instructor feedback flagged that the earlier averaged "risk-sensitive recall" hid Contradiction-specific weakness |
| Risk-sensitive recall | (recall_Contradiction + recall_NotMentioned) / 2 | Superseded as the headline risk metric by Contradiction recall alone; still recorded |
| Evidence Recall@K / Precision / MRR | Retrieval-only metrics: does the retrieved set contain the gold span, how much of it is relevant, how high does it rank | Retrieval configuration decisions (ADR-002) |
| Joint label+evidence correctness | Label is correct AND the retrieved/available spans overlap the gold evidence span | The metric this project's rubric weighs most heavily. **Was silently broken for the entire T041 run until 2026-09-24 — see `docs/decisions.md` ADR-010.** |
| Cost (USD), latency (ms) | Real measured API cost and wall-clock latency per case | Architecture/model tradeoff discussion |
| AUROC (confidence/routing signal) | Discriminative power of a candidate routing signal for correct vs. incorrect predictions | Confidence/abstention design (ADR-005) |
| McNemar's exact test | Paired significance test for two classifiers on the same cases | Agent include/exclude decision (ADR-007); do not report a small-sample accuracy delta without it |

## Development reuse warning

Because the 150-case dev sample was reused adaptively across the Oracle experiment, model
selection, every retrieval round, every prompt version, confidence/abstention design, and the
agent experiment, **development-sample metrics should be interpreted as exploratory evidence, not
as an unbiased estimate of final generalization.** Each individual decision was validated
reasonably (same sample, same seed, controlled comparisons), but the cumulative effect of many
decisions being tuned against the same 150 cases means the dev-sample numbers likely overstate
true held-out performance to an unknown degree. This is exactly why the official test split (T041)
exists and why it must never be used to make further tuning decisions.

## Case-category taxonomy

See `docs/evaluation_case_design.md` for the full breakdown of the 100-case catalogue into
benchmark, regression, robustness, agent-behaviour, and system/API categories — these are not one
homogeneous benchmark and should not be reported as a single pass rate.

## Current evaluation status (as of 2026-09-25)

- Architecture: **frozen** (ADR-009), on repeatedly-reused development evidence (see "What's
  missing" above) — no independent architecture-validation run exists. **A real, unresolved
  contradiction was found 2026-09-25** while reconstructing `notebooks/07_selective_agent_
  experiments.ipynb`: on the full 2,091-case hosted test set, the selective agent's accuracy
  (77.7%) is now *below* plain RAG's (78.7%), reversing the dev-sample and 500-case-subsample
  finding that justified including the agent (`docs/decisions.md` ADR-007). Not statistically
  significant either way (p=0.088), but the point estimate has flipped. This is disclosed as an
  open question, not resolved by re-freezing the architecture as part of this documentation pass.
- Final test (T041): **run**, but with two important caveats:
  1. Used prompt v2/`agent_step_v1.txt`, not the current v6/`agent_step_v2.txt` default.
  2. **Verified directly against the result files on 2026-09-25**: of the 7 T041 result files, only
     `run_T041_final_test_full_context_google_gemini-2.5-flash-lite.jsonl` (the hosted full-context
     architecture, full 2,091-case set) has a corrected, trustworthy joint value (0.812, matching
     accuracy as it must for full-context). The hosted `rag` and `rag_agent` files have since
     completed their full 2,091-case runs (`sample_size: 2091` in the latest record) but their
     latest `joint_label_evidence_correctness` values (0.327 and 0.342) are in the same range as
     the pre-fix, known-broken numbers — the backfill script was not re-run against these newer,
     larger result files. All three local-Llama files (`full_context`, `rag`, `rag_agent`, still at
     `sample_size: 500`) show the same pattern (0.31 / 0.304 / 0.316) and have not been backfilled
     at all. **Treat every T041 joint value except hosted full-context's 0.812 as unverified until
     `scripts/backfill_joint_metric.py` is re-run against these files** — not attempted as part of
     this documentation cleanup, since it would change reported numbers and this pass is scoped to
     documentation, not further data correction.
- Long-document stress test (RAG vs. full-context scalability): **proposed, not yet run** — see
  `docs/architecture.md`'s open questions.
