# Stage E1 — full-agent diagnostic

Status: **COMPLETE; NO-GO. STOP before Stage E2.**

The bounded agent does not add value on the frozen 150-case TRAIN population. Under the frozen
current `evidence_evaluator_v2`, it reduces Joint success from 113/150 (75.3%) to 110/150
(73.3%), reduces Contradiction Recall from 38/50 (76.0%) to 35/50 (70.0%), and degrades both
evidence recall and evidence precision. It used a tool on only 2/150 cases and neither tool-using
case was recovered.

## Reconciliation with the Stage C2 number

Stage C2 published 111/150 (74.0%) baseline Joint using the historical exact-only evidence
evaluator. The Stage D1 frozen configuration specifies the current v2 evaluator. The E1 primary
result therefore uses v2. As a transparent bridge, exact-only v1 gives 111/150 for base RAG and
106/150 for full agent, a net loss of five. The no-go conclusion is identical under both
evaluators. Classification metrics are unaffected by this distinction.

## Base RAG versus full agent

| Metric | Base RAG | Full agent | Delta |
|---|---:|---:|---:|
| Accuracy | 118/150 (78.7%) | 117/150 (78.0%) | -0.7 pp |
| Macro-F1 | 78.69% | 77.93% | -0.75 pp |
| Joint | 113/150 (75.3%) | 110/150 (73.3%) | -2.0 pp |
| Entailment Recall | 41/50 (82.0%) | 42/50 (84.0%) | +2.0 pp |
| Contradiction Recall | 38/50 (76.0%) | 35/50 (70.0%) | **-6.0 pp** |
| NotMentioned Recall | 39/50 (78.0%) | 40/50 (80.0%) | +2.0 pp |
| Evidence Recall | 88/100 (88.0%) | 83/100 (83.0%) | -5.0 pp |
| Evidence Precision | 88/103 (85.4%) | 83/99 (83.8%) | -1.60 pp |
| Source-valid cases | 147/150 (98.0%) | 141/150 (94.0%) | -4.0 pp |
| Source-valid quotes | 190/193 (98.4%) | 170/181 (93.9%) | -4.52 pp |

Joint counts by class changed from E 39/50, C 35/50, NM 39/50 to E 38/50, C 32/50,
NM 40/50.

## Paired recoveries and regressions

- Classification: 5 wrong→correct, 6 correct→wrong; net **-1**.
- Joint: 5 failures→successes, 8 successes→failures; net **-3**.
- Contradiction classification: **0 recoveries, 3 regressions; net -3**.
- Absolute Contradiction Recall: 76.0% before and 70.0% after; delta **-6.0 pp**.

Classification recoveries (the exact scorer-side `AGENT-RECOVERABLE` set):

1. `train::466::nda-15` — not a Joint recovery because final evidence was not source-valid
2. `train::603::nda-15`
3. `train::94::nda-13`
4. `train::279::nda-1`
5. `train::320::nda-1`

Classification regressions:

- `train::300::nda-20`
- `train::373::nda-11`
- `train::473::nda-7`
- `train::484::nda-8`
- `train::86::nda-1`
- `train::159::nda-1`

Joint recoveries were `train::515::nda-2`, `train::603::nda-15`, `train::94::nda-13`,
`train::279::nda-1`, and `train::320::nda-1`. Joint regressions were `train::88::nda-1`,
`train::300::nda-20`, `train::373::nda-11`, `train::473::nda-7`, `train::379::nda-12`,
`train::484::nda-8`, `train::86::nda-1`, and `train::159::nda-1`.

The three Contradiction regressions were `train::300::nda-20`, `train::373::nda-11`, and
`train::473::nda-7`. There were no Contradiction recoveries.

## Tool behavior

- Tool-use rate: 2/150 (1.3%).
- Step-1 FINAL without a tool: 148/150 (98.7%).
- Mean agent steps: 1.013; p95: 1.
- Mean tool calls: 0.013; distribution: 148 cases with zero, 2 with one.
- `FOLLOW_CROSS_REFERENCE` and `GET_MORE_CANDIDATES` were each used once.
- Useful tool-call case rate: 0/2 (0%).
- Unnecessary tool-call case rate: 1/2 (50%): the base result was already Joint-correct and
  remained correct.
- Harmful tool-call case rate: 0/2 (0%). The other tool case was wrong before and remained wrong.

The controller therefore behaved almost entirely as a second-pass classifier, not as a
tool-using agent. This reproduces, rather than resolves, the earlier “entered but did nothing”
failure mode.

## Cost and latency

- New hosted calls: 152.
- Incremental tokens: 214,369 input and 86,805 output.
- Total incremental cost: **$0.22720225**.
- Mean incremental cost: **$0.001515/case**.
- Total sequential incremental latency: 880.81 seconds (14.68 minutes).
- Mean incremental latency: 5.87 seconds/case; p95: 10.05 seconds.

Net Joint recovery is -3 and net Contradiction recovery is -3. Consequently, cost per net Joint
recovery, cost per net Contradiction recovery, latency per net Contradiction recovery, model
calls per net Contradiction recovery, and tool calls per net Contradiction recovery are all
**not meaningful / no net recovery**. Reporting a positive cost-per-recovery ratio with a
negative denominator would be misleading.

## E1 go/no-go answers

A. Did full-agent improve Joint? **No; -2.0 pp and -3 net cases.**

B. Did full-agent improve Contradiction Recall? **No; -6.0 pp.**

C. Were net Contradiction recoveries positive? **No; 0 recovered, 3 regressed, net -3.**

D. Did evidence quality stay within guardrails? **No.** Evidence Recall fell 5.0 pp, Evidence
Precision fell 1.60 pp, and case-level source validity fell 4.0 pp.

E. Did tool use occur? **Technically yes, but only on 2/150 cases, with zero useful recoveries.**

F. Was cost/latency reasonable? The dollar cost was low, but 152 calls and 14.68 sequential
minutes bought negative net value. It is not operationally reasonable to retain on these results.

## Recoverability-pattern assessment and decision

Five classification recoveries exist, but none invoked a tool; only two were in R5_q10; none
was a Contradiction recovery; and six classification regressions outweighed them. Although all
five recovery contexts contain broad exception/negation terms, those cues are common and this
small net-negative result does not establish a meaningful runtime-observable pattern tied to
what the agent tools can fix. Per-case runtime features are preserved in `arm_metrics.json` and
`per_case_metrics.jsonl` for audit, but no R6 rule is proposed.

**Conclusion: Agent has insufficient value even without routing constraints; further routing
optimization is not justified.** Stage E2 is not started, no R6 is invented, and no agent
retention/business-case analysis can pass because the primary quality and Contradiction gates
both fail before human-review economics are considered.
