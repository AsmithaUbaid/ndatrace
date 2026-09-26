```
Experiment ID: E10
Question: What is the smallest read-only selective-agent design that can fairly test whether
    runtime information-gathering improves frozen GPT-RAG (A2)?
Hypothesis: not pre-assumed. E09 found only 1/39 residual GPT failures (0.67% of all 150 cases)
    passes the strict dynamic-information-acquisition test, with a 6x larger static opportunity
    ceiling available. This experiment is a DESIGN/FREEZE step, not a performance claim -- it
    exists to give the no-go conclusion a fair, bounded empirical test (E11) rather than resting
    solely on E09's diagnostic estimate.
Why this experiment exists: course completeness and empirical architecture comparison. **E09's
    conclusion is NOT reversed by this experiment's existence** -- A3 is being prototyped despite
    a no-go recommendation, specifically to validate (or contradict) that recommendation with a
    real, bounded implementation, not because E09 approved it.
Input dataset/split: same frozen TRAIN_ARCH_v1 manifest (150 cases) E11 will use for the matched
    A2-vs-A3 comparison. No DEV, no TEST.
Frozen dependencies: retrieval_v1 (unmodified), classification_prompt_v1 (unmodified, used
    unchanged for A2's first pass only -- NOT reused as the agent's own control prompt), A2's
    frozen result schema ({"label":..., "evidence":[...]}), openai/gpt-5-mini (per E08B's own
    result -- Qwen is explicitly not used here, since E08B showed Qwen-specific weakness, not a
    task-intrinsic one, dominated the original failure picture).
Independent variable: none in E10 itself -- this is a design/freeze experiment. E11 will vary
    architecture (A2 alone vs. A2+selective-agent) on the identical cases.
Metrics (planned for E11, not measured here): accuracy, Macro-F1, Contradiction Recall, joint
    success, escalation rate, tool-calls/case, steps/case, duplicate-call rate, stop reasons,
    recovery/regression counts (classification AND joint), latency, cost, invalid-action count,
    step-cap/loop-cap hit counts.
Expected cost: $0.00 -- Stage A is local/free (no model calls, no implementation).
Expected runtime: same-session design work.
Stop condition: Stage A ends at this proposal -- no agent_v2 code, no model call, no E11 run.
Result: PENDING -- Stage A only.
Decision: PENDING -- E10 freezes the design; E11 measures it; only then is a final "does A3 earn
    its complexity" call made, feeding back into (not overriding) E09's existing no-go finding.
What becomes frozen after this: the routing trigger, tool surface, hard limits, agent action
    schema, and E11's comparison plan -- explicitly BEFORE E11 runs, so nothing is tuned on
    outcomes.
```

## Stage A vs. Stage B

**Stage A (this commit's state): audit historical (T-series) agent code as read-only prior art,
propose and FREEZE the minimal tool surface / runtime trigger / hard limits / agent loop / action
schema / output schema, estimate cost and latency scenarios, and design (but do not execute) E11's
matched comparison plan.** No model call, no `agent_v2` implementation, no E11 run.

**Stage B does not exist for E10** — Stage A's design proposal, once approved, is directly
implemented as `pipeline/agent_v2.py`/`pipeline/agent_tools_v2.py` under a SEPARATE experiment
(E11's own authorization), not executed here.

Full Stage A audit and design: `summary.md`.
