# Stage D1 — Selective vs full-agent pre-run plan

Status: **FROZEN; awaiting approval. No hosted model calls were made in D1.**

## 1. Frozen RAG configuration

The baseline is the exact Stage C2 150-case TRAIN RAG population: clause-aware 256-token
chunking, BM25 top-20 candidate retrieval, `cross-encoder/ms-marco-MiniLM-L-12-v2` reranking,
top-5 context, `openai/gpt-5-mini`, frozen GPT-P0, existing structured parser,
`runtime_evidence_validator_v2`, and `evidence_evaluator_v2` at the existing 0.5 evidence-recall
threshold. No baseline calls will be repeated.

Key frozen hashes are in `pre_run_config.json`; GPT-P0 SHA-1 is
`3fcc7c95cf1287c292e403f12b307c9d912278ce` and the retrieval artifact SHA-1 is
`af5b07ebff19f596375cfdea6f25530d4511c903`.

## 2. Frozen agent configuration

Reuse `pipeline/agent_v2.py`, `pipeline/agent_tools_v2.py`, and
`prompts/agent_v2_control.txt` (composite SHA-1
`5717e352928b08518069cb9eb5a036ba41cd1d26`). Preserve the existing maximum 3 agent steps,
2 tool calls, duplicate-call protection, 8,000 added-context-character cap, 60-second case cap,
$0.01 estimated per-case guard, explicit FINAL action, and fallback to the base RAG result.
The only exposed actions remain `FOLLOW_CROSS_REFERENCE` and `GET_MORE_CANDIDATES`.

## 3. Exact population

Use `experiments/E05_full_context/TRAIN_ARCH_v1.json`, SHA-1
`3a5491ab0de1c101b8d1043ff4dffa21029a58f6`, in its existing order: 150 TRAIN cases, exactly
50 Entailment, 50 Contradiction, and 50 NotMentioned. The ordered case-ID list SHA-1 is
`1544a2be756c4e45128c46a0f8a363af009a6f2e`. No resampling, rebalancing, or TEST access.

## 4. Exact R5_q10 definition

R5_q10 routes when R1 fires, top-1 reranker score is at most `-0.5165155708789826`, top1–top2
margin is at most `0.1690671443939209`, or a frozen cross-reference cue appears in the retrieved
top-5. R1 is unusable parse/error, E/C without evidence, any source-invalid quote, or
NotMentioned with evidence. It routes exactly 41/150 cases. It remains a diagnostic comparator,
not an approved production router.

## 5. Arms and hosted-call reuse

| Arm | Cases | Agent runs | New base calls |
|---|---:|---:|---:|
| A — RAG only | 150 | 0 | 0 |
| B — R5_q10 selective agent | 150 | 41 | 0 |
| C — full agent | 150 | 150 | 0 |
| Oracle diagnostic | 150 | 39 base failures use C outputs | 0 additional |

Only one set of 150 agent executions will be purchased. Arm B will reuse the same agent outputs
as Arm C on its 41 routed cases and reuse Arm A on the other 109. The scorer-only oracle will use
Arm C outputs on the 39 known base Joint failures and Arm A elsewhere. This avoids 41 duplicate
selective calls plus 39 duplicate oracle calls and removes avoidable stochastic mismatch on
shared treated cases.

## 6–9. Calls, tokens, cost, and runtime

The exact first-turn input over all 150 cases is 212,685 tokens (mean 1,417.9; p90 1,571; max
2,042). E11 actually observed 538.5 output tokens, $0.001454, and 6.07 seconds per agent call.

| Scenario | Calls | Input tokens | Output tokens | Incremental cost | Sequential runtime |
|---|---:|---:|---:|---:|---:|
| Empirical one-step point estimate | 150 | 212,685 | 80,770 | $0.215 | 15.2 min |
| Two-step planning case | 300 | 575,370 | 161,540 | $0.467 | 30.4 min |
| Three-step conservative | 450 | 1,110,600 | 836,550 | $1.951 | 72.8 min at E11 p90 |

The absolute wall-clock cap is 150 minutes if every case reaches its 60-second limit. Arm B's
attributed incremental cost is approximately $0.059 for one-step behavior, $0.128 for the
two-step planning case, or $0.533 conservatively. The provider key was checked read-only at
2026-09-27T14:17:56Z: $7.7239 remained. D2 must refresh this immediately before execution and
abort if the conservative forecast plus reserve is unavailable.

## 10. Oracle diagnostic feasibility

Feasible with zero extra hosted calls. Arm C necessarily produces an agent result for every one
of the 39 base Joint failures, so the oracle arm is a scorer-only recombination. It will be
labelled **DIAGNOSTIC UPPER BOUND ONLY** and excluded from production-selection metrics.

## 11. Failure-diagnostic fields already available

Available now: predicted label, hypothesis ID, document length and span/chunk count, all final
top-5 BM25/reranker scores, top1/top2/margin/spread, evidence count and length, runtime
source-validity, chunk IDs/offsets/positions, exact evidence-to-chunk spread, cross-reference,
exception, negation, and definition cues. E09 also records scorer-only top-20 gold rank and
failure taxonomy for the 39 failures.

Not directly available as a validated runtime signal: semantic conflict between clauses and
label instability under clause-order perturbation. A deterministic lexical conflict proxy can
be reported diagnostically. No perturbation model calls are authorized in D2.

## 12. Implementation gaps

1. The existing controller hardwires its old cross-reference trigger. Add a default-off
   `force_agent=False` entry switch so the experiment can enter the unchanged bounded loop for
   Arm C. The default path must remain byte-for-byte behaviorally equivalent and be regression
   tested.
2. Implement R5_q10 inside the experiment runner from the frozen protocol; do not add it to
   production routing.
3. Build a scorer-free execution manifest. Gold must not be loaded by the runner or passed to
   the model/controller; scorer-only files are joined after raw traces are complete.
4. E11's old evidence scorer searches only the original top-5. D2 must score agent evidence
   against the exact accessible context, including recorded tool results, while retaining
   document-span overlap semantics.
5. Add resumable, append-only per-call logging and an external run-level budget check. The
   frozen per-case cost guard is estimate-based and does not replace provider-balance control.

## 13. Exact files planned for D2

Create:

- `scripts/run_selective_vs_full_agent.py`
- `scripts/analyze_selective_vs_full_agent.py`
- `scripts/analyze_agent_routing_diagnostic.py`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/execution_manifest.json`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/raw_agent_traces.jsonl`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/per_case_metrics.jsonl`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/arm_metrics.json`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/comparison_table.csv`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/routing_failure_diagnostic.json`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/human_review_comparison.json`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/results/cost_ledger_snapshot.json`
- `experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent/summary.md`

Modify only:

- `pipeline/agent_v2.py` — additive default-off force-entry switch; no loop/tool/limit change
- `tests/test_agent_v2.py` — regression coverage for default selective and forced entry

Do not modify `pipeline/final_review.py`, backend, frontend, production docs, historical E11/E15
outputs, model/prompt/retrieval/evaluator code, or TEST artifacts.

## 14. Leakage check

The execution runner will consume only case/document/hypothesis IDs and text, retrieved chunks,
base predictions/evidence, R5_q10 runtime flags, and provider telemetry. Gold label/evidence,
base correctness, Joint status, E09 taxonomy, and oracle membership are forbidden until scoring.
The oracle arm is constructed only after all 150 raw full-agent traces are frozen.

## 15. Final run order

1. Verify hashes, tests, current provider balance, and absence of TEST inputs.
2. Materialize Arm A from stored outputs and freeze a scorer-free execution manifest.
3. Run one resumable forced-agent pass over all 150 cases in source-manifest order, recording
   spend after every successful call.
4. Derive Arm B from the 41 R5_q10 traces plus 109 Arm-A cases.
5. Derive Arm C from all 150 traces.
6. Derive the scorer-only oracle arm from C outputs on the 39 base Joint failures.
7. Score all arms, compute recovery/cost/latency/human-review comparisons, analyze why R5_q10
   missed failures, write the Stage D2 report, and stop without production changes or a commit.
