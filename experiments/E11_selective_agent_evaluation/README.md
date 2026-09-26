```
Experiment ID: E11
Question: Does the bounded selective agent (A3) designed and offline-verified in E10 provide
    enough measurable benefit over frozen GPT-RAG (A2) to justify its additional complexity?
Hypothesis: not pre-assumed. E09 concluded A3 is not justified as the likely final architecture;
    E11 exists to empirically test that no-go conclusion against E10's real, bounded prototype,
    not to force an agent win.
Status: COMPLETE. 15 real openai/gpt-5-mini calls executed through the frozen E10 agent path;
    135 non-triggered cases reused E08B's frozen A2 output directly (zero new hosted calls).
Input dataset/split: TRAIN_ARCH_v1, the same 150 cases used by E05/E07/E08/E08B/E09/E10. No DEV,
    no TEST.
Frozen dependencies (from E10, NOT to be re-tuned here): the cross_reference_to_named_provision_cue
    routing trigger, the 2-tool set (follow_cross_reference, get_more_candidates), all hard limits
    (max 3 agent steps, max 2 tool calls, duplicate-call detection, 2000-char context cap, 4 total
    model calls/case, 60s wall-clock cap, $0.01 cost circuit-breaker), the agent action schema, the
    fallback-to-A2 policy, and openai/gpt-5-mini as the sole agent model. E11 must not modify any
    of these based on its own outcomes -- that would be tuning on the test result E11 exists to
    produce.
Independent variable: architecture (A2 alone vs. A2 + E10's selective agent) on the identical 150
    cases, with A2's own frozen first-pass results (E08B's output) reused directly for every
    non-triggered case.
Metrics (frozen by E10, to be measured here): see config.yaml's `metrics_plan` -- quality
    (accuracy, Macro-F1, per-class recall, Evidence Recall/Precision, joint success), transitions
    (classification and joint, both directions), agent behavior (escalation rate, steps/tool-calls
    per escalated case, tool distribution, duplicate/fallback rates, stop-reason distribution),
    operational (incremental tokens/cost/latency), safety (invalid actions, tool failures, cap
    hits).
Expected cost: only the ~15 triggered cases (10% of 150, per E10's offline verification) incur any
    extra hosted GPT-5-mini calls -- E10's Stage A cost forecast projected $0.00187-$0.00306
    blended cost/case across 5-20% escalation scenarios; the measured 10% escalation rate implies
    roughly the middle of that range for the actual E11 run.
Stop condition: this experiment does not begin until separately authorized. When it does, it must
    follow E10's frozen configuration exactly (config.yaml) and report course-comparison outcome
    A/B/C (does A3 empirically earn reconsideration, show limited benefit, or confirm E09's no-go)
    without forcing an agent win.
Result: A3 accuracy 79.33% vs A2's 78.67% (+0.67pp); joint success unchanged at 74.0% (1 recovery,
    1 regression -- net zero); zero tool calls made across all 15 triggered cases, including both
    predeclared special cases. McNemar not significant on either metric.
Decision: C -- A3 CONFIRMS E09 NO-GO for this tested configuration. See summary.md for full detail.
```

## Relationship to E09/E10

E09 concluded **A — A3 not justified** as the likely final production architecture (0.67% of all
150 cases genuinely dynamic, a 6x smaller opportunity ceiling than a free static fix). E10 designed
and offline-verified (zero model calls) a minimal, bounded, read-only agent prototype anyway, for
course completeness and empirical comparison. **E11 is the only experiment in this sequence
authorized to make real model calls for this purpose** — and even then, only after separate,
explicit authorization distinct from E10's own approval.
