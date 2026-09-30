# Agent Prompt V1 versus V2 — final report

Status: **COMPLETE; V2 REJECTED. Agent and routing work remain closed.**

Run ID `ed0e321165da` executed from 2026-09-27T15:09:22Z through 15:35:17Z. All 150 frozen
TRAIN cases completed. TEST cases: 0. Actual incremental V2 cost was $0.398776, below the $3.00
hard ceiling. No production runtime, routing, retrieval, base prompt, tools, evaluator, or final
architecture was changed.

## 1. Prompt ablation

The exact byte-preserved V1 prompt is `prompt_v1.txt` (SHA-1
`30781d7cac504c7887f2ae0dc63c1564f5430df9`). The frozen V2 prompt is `prompt_v2.txt` (SHA-1
`d3c059dca56300825c788c6653c3752470fe74ed`).

V2 removed V1's “most cases should conclude immediately” bias and added silent, mandatory
checks for unresolved cross-references, qualifications, incomplete clauses, plausible evidence
outside top five, and Contradiction-specific reversal risk. It broadened the stated use of the
same `GET_MORE_CANDIDATES` tool, required reassessment after tool output, and retained the same
two actions, JSON schema, evidence rule, and injection defense. The full section comparison and
rationale remain frozen in `pre_run_plan.md`.

## 2. Quality results

Primary evaluator: `evidence_evaluator_v2`, tau 0.5.

| Metric | Base RAG | Agent V1 | Agent V2 | V1→V2 | Base→V2 |
|---|---:|---:|---:|---:|---:|
| Accuracy | 118/150 (78.7%) | 117/150 (78.0%) | 111/150 (74.0%) | -4.0 pp | -4.7 pp |
| Macro-F1 | 78.69% | 77.93% | 74.04% | -3.90 pp | -4.65 pp |
| Joint | 113/150 (75.3%) | 110/150 (73.3%) | 103/150 (68.7%) | -4.7 pp | **-6.7 pp** |
| Entailment Recall | 41/50 (82%) | 42/50 (84%) | 37/50 (74%) | -10 pp | -8 pp |
| Contradiction Recall | 38/50 (76%) | 35/50 (70%) | 37/50 (74%) | +4 pp | **-2 pp** |
| NotMentioned Recall | 39/50 (78%) | 40/50 (80%) | 37/50 (74%) | -6 pp | -4 pp |
| Evidence Recall | 88/100 (88%) | 83/100 (83%) | 83/100 (83%) | 0 pp | -5 pp |
| Evidence Precision | 88/103 (85.4%) | 83/99 (83.8%) | 83/104 (79.8%) | -4.03 pp | -5.63 pp |
| Source-valid cases | 147/150 (98%) | 141/150 (94%) | 141/150 (94%) | 0 pp | -4 pp |
| Source-valid quotes | 190/193 (98.4%) | 170/181 (93.9%) | 190/202 (94.1%) | +0.14 pp | -4.39 pp |

V2's Joint counts by class were Entailment 30/50, Contradiction 36/50, and NotMentioned 37/50.
The apparent +1 Contradiction Joint case versus base comes from evidence selection, not improved
Contradiction classification: label Recall still fell from 38/50 to 37/50.

## 3. Recoveries and regressions

### Base RAG → V2

- Classification: 1 recovery, 8 regressions, net **-7**.
- Joint: 2 recoveries, 12 regressions, net **-10**.
- Contradiction classification: 0 recoveries, 1 regression, net **-1**.
- Evidence overlap: 3 gains, 8 regressions, net **-5** cases.

The only classification recovery was `train::466::nda-15`; it was not Joint-recovered because
V2 evidence was not source-valid. Joint recoveries were `train::318::nda-2` and
`train::515::nda-2`.

The Contradiction regression was `train::300::nda-20`. The remaining classification regressions
were five Entailment cases (`train::265::nda-15`, `train::271::nda-15`,
`train::375::nda-15`, `train::457::nda-4`, `train::484::nda-8`) and two NotMentioned cases
(`train::86::nda-1`, `train::280::nda-1`).

### V1 → V2

- Classification: 3 recoveries, 9 regressions, net **-6**.
- Joint: 6 recoveries, 13 regressions, net **-7**.
- Contradiction classification: 2 recoveries, 0 regressions, net **+2**.

V2 recovered two of V1's three Contradiction regressions (`train::373::nda-11` and
`train::473::nda-7`), explaining the +4 pp V1→V2 Contradiction change. It still did not recover
any base Contradiction failure and remained 2 pp below base.

## 4. Tool-use behavior

| Behavior | V1 | V2 | Change |
|---|---:|---:|---:|
| Cases using ≥1 tool | 2/150 (1.3%) | 30/150 (20.0%) | +18.7 pp |
| Step-one FINAL without tool | 148/150 (98.7%) | 117/150 (78.0%) | -20.7 pp |
| Mean steps | 1.013 | 1.260 | +0.247 |
| p95 steps | 1 | 3 | +2 |
| Mean tool calls | 0.013 | 0.260 | +0.247 |
| Tool-call distribution | 148 zero; 2 one | 120 zero; 21 one; 9 two | — |
| `GET_MORE_CANDIDATES` | 1 | 23 | +22 |
| `FOLLOW_CROSS_REFERENCE` | 1 | 16 | +15 |

V2 clearly changed controller behavior, so V1's near-universal zero-tool pattern was partly
prompt-sensitive. However, behavior change did not translate into value.

## 5. Tool effectiveness

Using the preregistered outcome proxy against base RAG:

- Useful: **0/30 (0%)**.
- Neutral: 29/30 (96.7%).
- Harmful: 1/30 (3.3%), `train::484::nda-8`.

Tool-used cases achieved 22/30 classification correctness and 20/30 Joint, with net -1
classification and net -1 Joint transition versus base. No-tool cases achieved 89/120
classification correctness and 83/120 Joint, with net -6 classification and net -9 Joint.

This classification is an outcome-associated proxy: a one-run prompt ablation cannot establish
counterfactual causality for an individual tool call. Importantly, no case followed the target
path `V1 wrong + step-one FINAL → V2 tool use → V2 correct`. Three V1-wrong cases became
V2-correct, but none used a V2 tool.

## 6. Control and safety behavior

There were no provider errors, retries, timeouts, unsafe actions, external-knowledge tools, or
budget violations. The hard controls failed closed as designed. Operationally, however, V2
created substantial control friction:

- 25 fallbacks versus 1 under V1.
- 11 duplicate attempts versus 1.
- 6 invalid actions versus 0.
- 8 `max_tool_calls` stops.
- 10 tool errors versus 1.
- Stop reasons: 125 FINAL, 6 invalid action, 11 duplicate call, 8 maximum tools.

These guarded failures did not escape the controller, but they are serious evidence that the
stronger prompt and the existing controller/tool protocol are poorly aligned.

## 7. Cost and latency

| Operational metric | V1 | V2 | V2−V1 |
|---|---:|---:|---:|
| Hosted calls | 152 | 189 | +37 |
| Input tokens | 214,369 | 355,792 | +141,423 |
| Output tokens | 86,805 | 154,914 | +68,109 |
| Incremental cost | $0.227202 | $0.398776 | +$0.171574 |
| Cost/case | $0.001515 | $0.002659 | +$0.001144 |
| Mean latency/case | 5.87 s | 10.36 s | +4.48 s |
| p95 latency | 10.05 s | 22.98 s | +12.94 s |
| Sequential latency | 880.81 s | 1,553.50 s | +672.69 s |

V2's incremental cost versus reused base RAG is $0.398776. Because Base→V2 net Joint recovery
is -10 and net Contradiction recovery is -1, cost per net Joint recovery, cost per net
Contradiction recovery, latency per net Joint recovery, and latency per net Contradiction
recovery are all **not meaningful / no net recovery**.

## 8. Retention decision

V2 passes only the behavioral manipulation check, the dollar/latency ceiling, and the narrow
“at most one Contradiction regression” check. It fails the decisive criteria:

- Joint does not improve versus base; net Joint is -10.
- Contradiction Recall does not improve versus base; net Contradiction is -1.
- No tool-using case is useful by the outcome proxy.
- Evidence Precision falls 5.63 pp and Evidence Recall falls 5 pp versus base.
- Entailment Recall falls 8 pp and NotMentioned Recall falls 4 pp versus base.
- Control fallbacks increase to 25/150.

This corresponds primarily to diagnostic outcome **B**—V2 uses tools more but quality does not
improve—with an additional element of **D**, because the overall result materially regresses.

**Conclusion:** zero-tool behavior was partly a prompt-behavior problem, but tool underuse was
not the main quality bottleneck. The tested Prompt V2 increases investigation without producing
useful recoveries and substantially worsens overall quality. No further agent experiment is
justified on this framework without a separately approved redesign. The agent remains rejected,
and R6 or other routing work remains closed. No final architecture change or commit is made.
