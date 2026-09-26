```
Experiment ID: E12A
Question: Can deterministic expansion of the final retrieved context recover the retrieval/
    filtering failures identified after GPT-5-mini without introducing enough distractor
    regressions, context growth, latency, or cost to negate the benefit?
Hypothesis: not pre-assumed. E09 found 6/39 residual GPT joint failures are
    RETRIEVAL_FILTERING_LIMITED (gold in the BM25 top-20 pool, cut by the reranker before the
    final top-5), with a Static Pipeline Opportunity Ceiling of +4.0pp joint success -- ~6x larger
    than the Oracle Agent ceiling (+0.67pp). E10/E11 completed as a controlled agent comparison
    and A3 was rejected; this experiment tests the cheaper deterministic alternative E09
    recommended instead. More context may equally introduce distractors, spurious contradictions,
    or weaker evidence precision -- not assumed to help.
Why this experiment exists: test the cheapest deterministic fix (one fixed final-K change) before
    any prompt work. One experiment = one question: this is NOT prompt engineering, NOT retrieval
    re-optimisation, NOT agent work, and NOT model selection.
Input dataset/split: TRAIN_ARCH_v1, n=150, same case IDs and order as E05/E07/E08/E08B/E09/E10/E11.
    No DEV, no TEST.
Frozen CONTROL: E08B's A2 GPT-RAG architecture, unaltered -- BM25 -> clause_256 -> top-20
    candidate pool -> ms-marco-MiniLM-L-12-v2 rerank -> final top-5 -> classification_prompt_v1
    -> openai/gpt-5-mini -> same parser -> same evidence validator.
Independent variable: final retrieved-context size only. top-5 -> top-K where K=11 (see below).
    Same candidate pool, same reranker, same order, same model, same prompt, same schema, same
    parser, same evidence validator.
Why K=11 and not top-10: the kickoff proposed top-10, conditional on verifying it covers all six
    RETRIEVAL_FILTERING_LIMITED cases from existing artifacts. It does not -- a direct
    re-verification (matching E08's own stored ranks exactly) found gold evidence at reranked
    ranks {11, 9, 9, 8, 8, 9} for the six cases; train::160::nda-10 sits at rank 11. K=11 is the
    smallest fixed K covering all six. No K sweep was performed. Applied identically to all 150
    cases -- never case-selective.
Metrics (frozen now, measured in Stage B): see config.yaml -- classification (accuracy, Macro-F1,
    per-class recall), evidence (Evidence Recall/Precision, source-valid rate, gold-overlap rate,
    joint success overall and by class), operational (input/output tokens, latency, cost), paired
    classification and joint transitions, targeted subgroup analysis (6 retrieval-filtering, 6
    evidence-selection, 26 reasoning-limited, Contradiction residuals), distractor/regression
    inspection, exact McNemar + 10,000-resample paired bootstrap.
Expected cost: ~$0.28 (expected) to ~$0.47 (conservative) for a full 150-case GPT-5-mini run --
    see config.yaml and summary.md for the full forecast. Budget gate PASSES.
Stop condition: Stage A ends at this proposal -- no GPT call has been made.
Result: PENDING -- Stage A only.
Decision: PENDING -- one of A (static expansion earns adoption) / B (limited or neutral value,
    keep top-5) / C (static expansion hurts, keep top-5), predeclared before any result exists.
What becomes frozen after this: PENDING -- either static_context_candidate_v1 (K=11) adopted as
    the new context policy, or top-5 retained.
```

## Stage A vs. Stage B

**Stage A (this commit's state): verify the six retrieval-filtering cases' reranked gold ranks
against existing artifacts, choose the single fixed K, build the candidate context artifact
offline from the frozen top-20 pool, forecast token/cost/runtime, and freeze the metrics/analysis
plan.** No GPT/Qwen/Gemini call made.

**Stage B (after explicit approval): run the full 150-case GPT-5-mini candidate, analyze paired
transitions/subgroups/regressions, and reach the A/B/C adoption decision.**

Full Stage A audit and design: `summary.md`.
