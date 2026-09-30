```
Experiment ID: E09
Question: After upgrading Standard RAG to GPT-5 mini, do the remaining failures contain a
    meaningful, runtime-observable subset that requires case-dependent information acquisition
    and therefore justifies a selective agent?
Hypothesis: not pre-assumed. E08 (Qwen) concluded B (narrow selective agent potentially
    justified); E08B materially changed the evidence base by showing most of Qwen's
    MODEL_REASONING_LIMITED and much of its AGENTICALLY_FIXABLE bucket resolve under a stronger
    model with zero retrieval/agent change. E09 re-derives the agent-justification decision from
    GPT-5-mini's own residual failures, not Qwen's.
Why this experiment exists: this is the final justification gate before any A3 implementation
    (Section 7/17 of the reconstruction brief) -- E09 is diagnostic only, not agent
    implementation, tool-policy optimisation, prompt engineering, model selection, or retrieval
    tuning.
Input dataset/split: the IDENTICAL frozen TRAIN_ARCH_v1 manifest (150 cases) and E08B's own
    A2-GPT5mini run outputs (run_E08B_A2_gpt5mini_train_cases.jsonl,
    gpt5mini_failure_analysis.csv). No DEV, no TEST, no new model calls.
Frozen dependencies: retrieval_v1 (unmodified, not re-invoked for classification -- local BM25/
    reranker re-queries for diagnostic purposes only, same zero-cost precedent as E08's
    reranker-limited pilot), classification_prompt_v1 (unmodified), E08B's GPT-5-mini predictions
    (frozen, not rerun).
Independent variable: none -- this is a diagnostic/manual-review experiment, not a controlled
    comparison. No model or pipeline component is varied.
Metrics: failure-bucket decomposition of the 39 GPT joint failures (STATIC_PIPELINE_FIXABLE /
    DYNAMIC_INFORMATION_ACQUISITION / MODEL_REASONING_LIMITED / EVIDENCE_SELECTION_LIMITED /
    RETRIEVAL_FILTERING_LIMITED / OUTPUT_PROTOCOL / AMBIGUOUS_IRREDUCIBLE), oracle-action
    distribution, candidate runtime-observable-signal prevalence/precision/recall across all 150
    cases (not just failures), Oracle Agent Opportunity Ceiling, and a cost/complexity decision
    framework.
Expected cost: $0.00 -- Stage A is local/free (no model calls). Stage B's manual review is also
    $0.00 (no model calls; local BM25/reranker re-queries only, same as E08's zero-cost pilots).
Expected runtime: Stage A same-session. Stage B (all 39 cases, manual) is the dominant time cost,
    not compute.
Stop condition: Stage A ends at this proposal -- no model call, no agent build, no commit. Stage B
    begins only after explicit approval.
Result: PENDING -- Stage A only.
Decision: PENDING -- one of A (A3 not justified) / B (narrow selective A3 justified) / C (broader
    selective A3 justified).
What becomes frozen after this: PENDING -- the final justification decision that gates whether
    E10 (A3 implementation) proceeds at all.
```

## Stage A vs. Stage B

**Stage A (this commit's state): verify exact residual counts from E08B's raw artifacts, audit
all historical (T-series) agent-related code as hypothesis-generating prior art, propose the
failure taxonomy / manual-review population / oracle-action fields / candidate runtime signals /
signal-evaluation methodology / Oracle Agent Opportunity Ceiling calculation / cost-complexity
decision framework.** No model call, no agent build, no commit.

**Stage B (after explicit approval): manually review all 39 GPT joint failures (not a sample),
evaluate candidate signals across all 150 cases, compute the Oracle Agent Opportunity Ceiling,
and reach the final A/B/C decision.**

Full Stage A audit and proposal: `summary.md`.
