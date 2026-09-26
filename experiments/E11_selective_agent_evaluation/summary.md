# E11 — Selective Agent Evaluation — COMPLETE

**Real execution**: 15 real `openai/gpt-5-mini` calls through the frozen E10 agent path
(`pipeline/agent_v2.py`, unmodified). 135 non-triggered cases reuse E08B's frozen A2 output
directly — zero new hosted calls for them. Trigger, tools, hard limits, fallback policy, model,
and final-output schema are all exactly as frozen in E10; none were changed before, during, or
after this run.

## Research question

Does the frozen bounded selective agent improve evidence-grounded NDA review enough over frozen
GPT-RAG (A2) to justify its added cost, latency, complexity, and failure surface?

## Result

| Metric | A2 GPT-RAG | A3 Selective Agent | Δ |
|---|---|---|---|
| Accuracy | 78.67% | 79.33% | +0.67pp |
| Macro-F1 | 0.787 | 0.794 | +0.007 |
| Contradiction Recall | 76.0% | 76.0% | 0 |
| Evidence Recall | 86.0% | 84.0% | **−2.0pp** |
| Evidence Precision | 83.5% | 82.4% | **−1.1pp** |
| Joint success | 74.0% | 74.0% | **0.0pp** |

**Classification transitions** (150 cases): 1 recovery (`train::328::nda-1`, NotMentioned), 0
regressions. **Joint transitions**: 1 recovery, **1 regression** (`train::316::nda-2` kept the
same label but its evidence quality regressed) — **net zero**. McNemar: not significant on either
classification (p=1.0, 1 discordant pair) or joint (p=1.0, 2 discordant pairs) — expected at this
scale (only 15 cases could possibly differ).

## Agent behavior — the central finding

**Zero tool calls were made across all 15 triggered cases.** `FOLLOW_CROSS_REFERENCE`: 0 calls.
`GET_MORE_CANDIDATES`: 0 calls. Every routed case concluded `FINAL` on step 1 (mean/median steps
= 1, mean model calls = 1, mean tool calls = 0). Zero fallbacks, zero invalid actions, zero tool
errors, zero cap hits — the agent ran cleanly and exactly as designed; **the frozen agent
controller elected not to invoke its available information-acquisition tools on any routed
case.** This is not a claim that the tools failed, that agents never work, or that no agent could
ever help — it is a specific, observed behavior of this specific frozen controller on this
specific 15-case sample.

**Special case A — `train::273::nda-1`** (E09's one confirmed genuinely-dynamic case, whose gold
evidence is an unresolved cross-reference): triggered, `FOLLOW_CROSS_REFERENCE` was available,
**not invoked**. Concluded FINAL=NotMentioned immediately, unchanged from A2 — still wrong (gold
is Entailment).

**Special case B — `train::518::nda-10`** (the only one of E09's 6 retrieval-filtering cases
reachable by the frozen trigger): triggered, `GET_MORE_CANDIDATES` was available, **not
invoked**. Concluded FINAL=NotMentioned immediately, unchanged from A2 — still wrong.

**Remaining 13 triggered cases**: 10/13 were already A2-correct and A2-joint-success; 12/13
labels stayed unchanged; 1 improved, 0 regressed. Real cost was incurred on this subgroup
(~$0.0015/case average) for essentially no net effect, consistent with E09's own 6.7%
trigger-precision estimate.

## Operational

Real incremental E11 spend: **$0.0218** (15 calls, ledger $0.3872 → **$0.4090**). Mean incremental
latency on escalated cases: ~6.4s. Blended deployment cost (A2 mean + escalation-rate-weighted A3
incremental) increases only marginally over A2 alone (see notebook section 17 for the exact
1,000/8,000-case projections).

## Final decision: C — A3 CONFIRMS E09 NO-GO

For this tested, frozen configuration: real cost was incurred, zero information-acquisition tools
were ever exercised, and net joint-success benefit across all transitions is exactly zero (one
recovery cancelled by one unrelated regression). This confirms E09's original diagnostic
conclusion with a real, bounded, honestly-executed prototype rather than resting on E09's
estimate alone — a valid and useful course result, not an experiment failure.

Full artifacts: `results/agent_traces.jsonl` (15 full traces, raw responses preserved, no hidden
reasoning stored), `results/run_E11_A3_train_cases.jsonl` (150 rows), `results/run_E11_A3_train.json`,
`results/a2_vs_a3_paired_comparison.json`, `E11_selective_agent_evaluation.ipynb` (executed,
0 errors). Not committed until this pass — see git history for the commit.
