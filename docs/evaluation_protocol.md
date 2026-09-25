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

**T041 is not one run at two sample sizes — it is two distinct configurations, corrected and named
here 2026-09-25 after a forensic timestamp/git-history review (`docs/decisions.md` ADR-010):**

- **T041-A** (interim, 500-case stratified subsample, 2026-09-23 between 11:14 and 17:56 UTC): model
  `google/gemini-2.5-flash-lite` / local Llama, **prompt v2** / `agent_step_v1.txt`, and for RAG+agent
  the **original inline, circular routing signal** (pre-C1-fix).
- **T041-B** (the full 2,091-case test set, 2026-09-24 between 03:00 and 05:31 UTC — **these are the
  numbers cited everywhere in this repo as "the T041 result"**): model unchanged, **prompt v6** /
  `agent_step_v2.txt` (the current shipped default), and for RAG+agent the **decoupled routing fix**
  via `pipeline/orchestrator.py::review_requirement()` (ADR-006).

**A previously-stated caveat here was wrong and is retracted**: earlier versions of this document
said "T041 used prompt v2, not the current v6 default." That was true only for T041-A. **T041-B's
numbers — the full 2,091-case results (81.2% / 78.7% / 77.7% accuracy for full-context / RAG /
RAG+agent) — are already v6, already using the decoupled routing fix, and already reflect
everything currently shipped.** Do not describe them as predating the security fix.

What was genuinely locked before T041-B and not changed based on its results:
- Model: `google/gemini-2.5-flash-lite` (hosted), Llama 3.2 3B via Ollama (local)
- Prompt version: v6 / `agent_step_v2.txt` (already in place before T041-B started — see above)
- Retrieval configuration: sentence chunking → mpnet → retrieve-20 → rerank L-12 → top-7 →
  rule-boost RRF fusion (ADR-002)
- Routing: rule-agreement-based ACCEPT/REVIEW (ADR-005), with the decoupled independent signal
  fix already in place (ADR-006)
- Agent: 5 tools, bounded ReAct loop (ADR-007)
- Evaluation scripts: `scripts/run_final_test_evaluation.py`

**A real qualification that remains, correctly stated rather than overstated**: T041-B is not a
pristine first exposure to the test split — T041-A had already scored a 500-case subsample of the
same split before T041-B ran. The v2→v6 and routing changes were triggered by an independently
discovered live security issue and a code-audit finding, not by looking at T041-A's scores, so this
is not test-set tuning in the overfitting sense — but the split had genuinely been partially
observed before T041-B's numbers were produced, and that should be disclosed, not implied away.

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
  missing" above) — no independent architecture-validation run existed until AV01 (below). **A
  real, unresolved finding, and now a stronger one than first stated**: on T041-B (the full
  2,091-case hosted test set, already v6 + decoupled routing — see the Freeze protocol section
  above), the selective agent's accuracy (77.7%) is *below* plain RAG's (78.7%), reversing the
  dev-sample finding that justified including the agent (`docs/decisions.md` ADR-007). McNemar's
  test on T041-B: b=87, c=65, p=0.088 — not significant, but the point estimate favors plain RAG.
  **Because T041-B already uses the current shipped prompt and routing configuration, this cannot
  be explained away as "it was still running the old v2/circular-routing setup" — it wasn't.** An
  independent architecture-validation run (AV01, `data/architecture_validation_manifest.json`) has
  since produced the same qualitative finding on untouched data — see `docs/decisions.md` ADR-009's
  update and the AV01 analysis for the full breakdown.
- Official test evaluation: **run, in two distinct configurations (T041-A and T041-B — see the
  Freeze protocol section above), not one run at two sample sizes.** T041-B (full 2,091 cases,
  already v6 + decoupled routing) is what's cited as "the T041 result" throughout this repo.
  Caveats that actually apply to T041-B:
  1. **Not a pristine first exposure to the test split** — T041-A had already scored a 500-case
     subsample of the same split before T041-B ran (see the Freeze protocol section for why this
     is disclosed rather than treated as invalidating).
  2. **Joint label+evidence correctness was broken in the code that executed both phases.**
     Fixed and fully backfilled 2026-09-25 (`scripts/backfill_joint_metric.py --write`, re-run
     against all 7 T041 result files — zero LLM/API calls, retrieval is deterministic). All three
     hosted T041-B files (full 2,091-case set) now carry a corrected, trustworthy joint value:
     full-context 0.812 (matching accuracy, as it must for full-context), RAG 0.754, RAG+agent
     0.747. The local-Llama files (T041-A-scale, `sample_size: 500`) are also now corrected: rule
     0.494, full-context 0.492, RAG 0.524, RAG+agent 0.532. **Every one of these corrected values is
     a post-hoc backfilled metric** (`scripts/backfill_joint_metric.py`, applied after the fact to
     already-saved predictions), not something the original run computed correctly — that provenance
     should always be stated alongside the number, not silently presented as if the run itself got
     it right the first time. Result files: the three hosted files now live in `results/final/`; the
     local-Llama and superseded 500-case rule files moved to `results/archive/runs/` (2026-09-25
     results/ reorganization).
- Long-document stress test (RAG vs. full-context scalability): **proposed, not yet run** — see
  `docs/architecture.md`'s open questions.
- Architecture-validation run (AV01): **complete** — 340 cases, 20 documents from ContractNLI's
  training split, verified zero overlap with every prior pool (dev sample, retrieval tuning,
  golden/regression cases, agent experiment, and the official test split). Frozen at the current
  shipped configuration (v6, decoupled routing) throughout — never used to compare prompt versions
  or architectures against each other before freezing, avoiding the exact contamination this
  document warns about elsewhere. Full-context and RAG were statistically indistinguishable
  (McNemar p=1.000); RAG+agent underperformed both, with a 6.6% correction precision against a
  12.5% harm rate on routed cases.
