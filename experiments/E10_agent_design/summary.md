# E10 — Bounded Selective Agent Design — STAGE A (audit + design freeze only)

**No model call has been made. No `agent_v2` code has been written. `retrieval_v1` and
`classification_prompt_v1` are unmodified.** This document audits historical (T-series) agent
code as read-only prior art, and proposes/freezes the minimal tool surface, runtime routing
trigger, hard limits, agent loop, action schema, output schema, and E11's matched-comparison plan
for a bounded selective agent (A3) that will be prototyped for course completeness, despite E09's
own A3-not-justified conclusion.

## Explicit framing (preserved verbatim intent)

E09 concluded **A — A3 NOT JUSTIFIED** as the likely final production architecture: only 1/39
residual GPT failures (0.67% of all 150 `TRAIN_ARCH_v1` cases) passed the strict
dynamic-information-acquisition test, and the deterministic Static Pipeline Opportunity Ceiling
(+4.0pp joint success) was ~6x larger than the Oracle Agent Opportunity Ceiling (+0.67pp). **E10
and E11 proceed anyway** — for course completeness, empirical architecture comparison, and to
validate (or contradict) E09's no-go conclusion with a real, bounded prototype rather than resting
solely on a diagnostic estimate. This is not a reversal of E09's finding.

## 1. Historical agent architecture audited

`pipeline/agent.py` (bounded ReAct loop, step/time/token limits, duplicate-call detection,
fallback-to-classify), `pipeline/agent_tools.py` (5 read-only tools), `pipeline/confidence.py`
(rule-agreement routing), `prompts/agent_step_v1.txt`/`agent_step_v2.txt`, and
`data/agent_experiment.json`'s result schema — the same inventory E09 already produced via a
read-only audit, extended here with an explicit keep/rewrite/discard call per component.

## 2-4. Components reusable / rejected, and why

| Component | Reusable? | Decision | Why |
|---|---|---|---|
| Agent loop control-flow shape (step/time/token limits + duplicate detection + fallback) | Pattern only | **Rewrite** | Its own dev-sample inclusion decision reversed at full test-set scale (E09 finding); E10's limits are tighter (2-3 steps vs. 5) |
| 5-tool set | Pattern only | **Discard and rebuild from evidence** | 2 of 5 tools (`search_exceptions`, `inspect_neighbouring_clauses`) have no evidentiary support from E08/E09's own GPT-5-mini failure analysis; `search_exceptions` has a documented 100% (4/4) failure rate on exactly the cases it targets |
| Confidence/rule-agreement routing | Not reusable | **Discard** | Task/dataset-specific to that lineage's own rule baseline; best AUROC ever achieved was 0.660, and it was found circular once (C-1) before a costly fix |
| Injection-detection prompt paragraph | Inspiration only | **Reuse pattern, reword** | Good template for E10's own agent-control prompt, adapted to the new tool set |
| Agent experiment result schema | Directly reusable | **Reuse for E11 logging** | Field shape (`n_recovery`, `n_regression`, `stopped_reasons`, per-case `outcomes[]`) is generic enough to carry forward unchanged |

## 5. Proposed real runtime trigger

**`cross_reference_to_named_provision_cue`** — the same phrase-pattern detector E09 evaluated
across all 150 cases (not a new detector invented for E10). Fires on phrases like "of the
definition of," "as defined in," "pursuant to section/clause," "paragraph (a)," etc. in the final
top-5 context. This is the only candidate signal E09 found with non-zero recall for the one
confirmed genuinely-dynamic case.

**Explicitly excluded** (per direct instruction, both shown weak by E09): exception/carve-out cue
alone (99.1%/100% prevalence in successes/failures — non-selective) and raw reranker score margin
alone (means 1.584 vs. 1.705 — not discriminating). Neither gold labels, gold evidence, nor
"known wrong prediction" are ever used as a runtime trigger.

## 6. Expected escalation rate

**~10% (15/150)**, measured directly from the frozen trigger's own prevalence on `TRAIN_ARCH_v1`
(the same TP=1/FP=14/FN=0/TN=135 breakdown E09 computed). This is a TRAIN-split estimate, not
guaranteed to generalize — flagged in unresolved issues.

## 7. Exact minimal tool set (2 tools, revised from an initial 3-tool draft, not the historical 5)

| Tool | Justification | Excluded alternative and why |
|---|---|---|
| `follow_cross_reference` | Direct evidence: the one confirmed dynamic case needs exactly this | — |
| `get_more_candidates` | Direct evidence: all 6 RETRIEVAL_FILTERING_LIMITED cases had gold in the BM25 top-20 but cut before top-5 — **though E09 already classified this as better solved by a static top-k increase**; included here only so E11 can empirically compare a runtime-triggered expansion against that cheaper static fix | `search_clauses` (redundant with this), `inspect_neighbouring_clauses` (no evidenced need), `compare_clauses` (no evidenced need — MODEL_REASONING_LIMITED failures were single-clause reasoning errors, not multi-clause comparison failures) |

## 8. Tool schemas

Both tools: read-only, deterministic dispatch, capped output size (500 chars for
`follow_cross_reference`, 1,500 chars for `get_more_candidates`), never raise (return
`success=false`/empty results on a miss). `get_more_candidates` takes no model-supplied argument
at all — the loop's own state tracks how many candidate-pool ranks have already been revealed and
requests the next window automatically, so the model cannot request an arbitrary or duplicate
window. Duplicate-call protection is enforced once, at the agent-loop level (an exact repeated
`(action, arguments)` signature immediately forces FINAL), not via a separate per-tool cache. Full
input/output schemas in `config.yaml`'s `proposed_tool_surface`.

## 9. Agent action schema

```
{"action": "FINAL" | "FOLLOW_CROSS_REFERENCE" | "GET_MORE_CANDIDATES",
 "arguments": {...tool-specific, empty {} for FINAL},
 "label": "Entailment|Contradiction|NotMentioned (only when action=FINAL)",
 "evidence": ["..."] (only when action=FINAL)}
```

Deterministic schema validation (reuses `evaluation.structured_output`'s strict/recovery parser).
An out-of-schema action or malformed tool argument is a `MALFORMED_ACTION` → immediately forced
FINAL with whatever has been gathered, never a crash, never an unrestricted retry. **No
chain-of-thought field** — the prompt asks for the structured action only.

## 10. Agent loop design

A2's frozen first pass (already computed, E08B's own output — never re-run) → routing trigger
checked against the same top-5 context → **not triggered: return the A2 result unchanged, zero
extra cost** → **triggered: enter a bounded loop**, at most 3 steps, each step is one
`gpt-5-mini` call given the requirement + current context (initial top-5 + any appended tool
results) that returns one action; a tool-call action executes exactly one read-only tool and
appends its compact result; a FINAL action stops the loop. This is a fixed, capped
enumerate-with-break — never an unrestricted `while True`.

## 11. Hard limits (enforced outside the model)

`max_agent_steps=3`, `max_tool_calls=2` (the 3rd step is forced toward FINAL),
`max_repeated_identical_calls=1` (immediate forced FINAL on the 2nd occurrence),
`max_cumulative_retrieved_tokens=2000` (across all tool results combined),
`max_total_model_calls_per_case=4` (1 baseline + up to 3 loop steps),
`max_wall_clock_seconds_per_case=60`, `max_estimated_hosted_cost_per_escalated_case_usd=0.01` (a
circuit breaker, not an expected value). None of these are left to the model to decide.

## 12. Duplicate-loop protection

Normalized `(action, sorted(arguments))` signature (whitespace/case-normalized — tighter than the
historical agent's plain exact-string match). An exact repeat within the same case's step history
forces FINAL immediately and is logged per-case in the `stopped_reasons` field (reusing
`data/agent_experiment.json`'s field name for continuity with E11's planned logging).

## 13. Model choice

**`openai/gpt-5-mini`** — E08B showed the large original failure buckets (E08's
MODEL_REASONING_LIMITED/AGENTICALLY_FIXABLE) were dominated by Qwen-specific reasoning weakness,
not a task-intrinsic ceiling. Building the agent around Qwen would risk re-discovering a
model-capability gap E08B already closed, rather than testing genuine information-acquisition
value. No other agent model is compared in E10.

## 14. Prompt/control design

A **new, separate agent-control prompt** — `classification_prompt_v1` is NOT reused as the whole
agent prompt (it already runs, unchanged, for A2's first pass). The control prompt's job is
strictly: given current context and any prior tool results, decide whether more information is
needed and choose exactly one allowed tool, or conclude. Includes an explicit "choose FINAL if
context is already sufficient — do not investigate merely because investigation is available"
instruction, a reworded injection-detection paragraph (from `agent_step_v2.txt`'s pattern), and an
explicit "no chain-of-thought" instruction. Temperature 0.0, matching every other
reconstruction-v2 classification call.

## 15. Final output schema

Identical to A2's: `{"label": ..., "evidence": [...]}` — required for a fair E11 comparison, no
additional fields.

## 16. Estimated cost scenarios (forecast only, zero model calls made)

| Escalation rate | Extra GPT calls/escalated case | Blended cost/case | Per 1,000 cases | Per 8,000 cases |
|---|---|---|---|---|
| 5% | 1 | $0.00187 | $1.87 | $14.96 |
| **10% (measured)** | 2 | $0.00221 | $2.21 | $17.68 |
| 20% | 3 (worst allowed path) | $0.00306 | $3.06 | $24.48 |

Baseline observed: $0.0017046/case (E08B's real measurement). Each agent-loop step's cost is
approximated as similar to a baseline call — a disclosed approximation, not a measurement.

## 17. Estimated latency scenarios (forecast only)

Non-escalated case: **~7.4s** (unchanged — agent never invoked). One-step escalated case:
**~14.8s** (baseline + 1 extra step at mean latency). Max-step escalated case: **~29.8s** (baseline
+ 3 extra steps at p90 latency + tool overhead) — within the 60s hard limit.

## 18. E11 matched comparison plan (designed now, not executed)

Same 150 `TRAIN_ARCH_v1` cases, A2's frozen first-pass results reused directly for non-escalated
cases (not re-run). Quality metrics (accuracy, Macro-F1, Contradiction Recall, joint success),
agent-behavior metrics (escalation rate, tool-calls/case, steps/case, duplicate-call rate, stop
reasons, recovery/regression counts — classification AND joint, reported separately per the
explicit historical-reversal caution), operational metrics (latency, cost, tokens), safety metrics
(invalid actions, step/loop-cap hits). Same statistical methodology as E08B (exact McNemar +
10,000-resample paired bootstrap, effect size always alongside any p-value).

## 19. Predeclared A3 rejection criteria (frozen before E11 runs)

Negligible net joint-success gain relative to the already-small +0.67pp Oracle ceiling; recoveries
offset/exceeded by regressions (the historical T-series full-scale reversal pattern); trigger
precision confirms the known 6.7% estimate with no compensating quality gain; escalation rate
materially exceeding the 10-20% scenarios without proportional gain; high duplicate-loop rate;
material latency/cost increase without compensating quality gain, especially relative to the
already-available +4.0pp static ceiling; no Contradiction-specific benefit; unstable tool usage
(frequent `found=false`). No numeric threshold invented beyond what existing evidence supports.

## Files to create / change

**Stage A (this commit)**: `experiments/E10_agent_design/{README.md, config.yaml, summary.md}`.
No code touched, no model call made.

**Future E11 only (not created here)**: `pipeline/agent_v2.py`, `pipeline/agent_tools_v2.py`,
`prompts/agent_v2_control.txt`, `scripts/run_e11_selective_agent.py`,
`experiments/E11_selective_agent_evaluation/`.

## Unresolved issues

1. The 6.7% trigger precision is a 150-case TRAIN-split estimate; E11 running on the same 150
   cases cannot independently validate generalization — a true out-of-sample check would need
   DEV/TEST, not authorized here or in E11 without separate approval.
2. `get_definition` was dropped as a standalone action before implementation, per review —
   E09 found no direct residual case requiring a definition-lookup action distinct from
   cross-reference resolution; it is retained only as an internal helper.
3. Cost/latency scenarios approximate each agent-loop step as similar to a baseline `classify()`
   call — real agent-step costs/latencies are unknown until E11 actually runs.
4. `get_more_candidates` deliberately tests a bucket E09 already classified as better solved
   statically — informative for the course-comparison goal, but a success here should not be read
   as recommending an agent over the cheaper static fix.

Stage A ends here. No model call has been made, no `agent_v2` code has been written. Awaiting
explicit approval to proceed to E11.

## Stage B result (implementation + offline verification — no model calls made)

Implemented `pipeline/agent_v2.py` (routing trigger, action schema/validation, bounded loop, hard
limits, duplicate protection, fallback policy, result trace) and `pipeline/agent_tools_v2.py`
(the 2 frozen tools) as entirely new files — `pipeline/agent.py`/`agent_tools.py`/`confidence.py`
untouched. `prompts/agent_v2_control.txt` written separately from `classification_prompt_v1`.

**Tool set finalized at 2, not 3**: `get_definition` was dropped as a standalone action before
implementation (see `config.yaml`'s `revision_note`) — kept only as an internal helper
`follow_cross_reference` delegates to for "definition of X"-style references.

**Offline trigger verification** (`scripts/verify_e10_trigger_offline.py`, zero model calls): the
real implementation run over all 150 `TRAIN_ARCH_v1` cases reproduces E09's frozen prevalence
**exactly** — 15/150 triggered (10.0%), TP=1, FP=14, FN=0, TN=135. No mismatch to explain.

**Tool-reachability analysis over the 15 triggered cases**: 15/15 have a resolvable
cross-reference phrase present and 15/15 have ranks 6-10 available for `get_more_candidates`. Of
E09's 6 `RETRIEVAL_FILTERING_LIMITED` cases, only **1/6** (`train::518::nda-10`) is actually
triggered by the frozen routing policy. **Stated explicitly, per instruction, without broadening
routing to fix it: selective A3 does not test recovery of the full static-retrieval bucket — only
the triggered subset of it is ever reachable by this agent.**

**Offline mock test harness + tests**: 25 new tests in `tests/test_agent_v2.py` covering all 9
required mock scenarios (immediate FINAL, one-tool→FINAL, two-tool→FINAL, duplicate call,
invalid action, never-final-until-step-cap, tool failure, context-budget overflow, cost-budget
overflow) plus routing, action-validation, trace, and safety tests; 20 new tests in
`tests/test_agent_tools_v2.py` covering both tools' exact-match/ambiguous/not-found/malformed/
truncation/rank-progression/hard-maximum behavior. **Two real implementation bugs were found and
fixed by this test suite before being finalized**: (1) `follow_cross_reference`'s numbering
regex incorrectly required a non-alphanumeric character before a parenthetical locator like
`(b)`, which fails on the very common combined form `4(b)` — fixed to skip the boundary check for
parenthetical locators specifically; (2) the cost-budget circuit breaker checked cost already
spent (which is $0 before any call, so a $0 limit could never actually block the first call) —
fixed to project the cost of the call about to be made, not just calls already completed.

**Total test count**: 338/338 passing (293 pre-existing + 20 tool tests + 25 loop tests), 0
failures.

**Fallback policy verified**: every forced-fallback path (`max_steps`, `max_tool_calls`,
`duplicate_tool_call`, `invalid_action`, `context_budget`, `cost_budget`) returns the original
frozen A2 label/evidence unchanged and sets `fallback_to_a2=true` — never fabricates a new answer.

**Safety boundaries verified**: `VALID_ACTIONS` is a closed 3-member set (`FINAL`,
`FOLLOW_CROSS_REFERENCE`, `GET_MORE_CANDIDATES`) with no path to a dynamically-constructed tool
name, no filesystem/shell/network action exposed, and both tools only ever receive `doc_text` for
the current case — there is no argument path to a different document, file path, or URL.

Full results: `experiments/E10_agent_design/results/trigger_verification_and_reachability.json`.
Not committed — awaiting review.
