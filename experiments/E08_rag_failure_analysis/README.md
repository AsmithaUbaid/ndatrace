```
Experiment ID: E08
Question: What failure modes remain in A2 Standard RAG, and which of them could plausibly be
    addressed by selective agentic investigation?
Hypothesis: not pre-assumed either way -- E08 is diagnostic. Two facts already known from E07
    point in different directions: retrieval_v1's coverage is high (90.9% Evidence Recall@5,
    only 6/85 errors retrieval-limited) suggesting little room for "search harder," but a Stage
    A pilot analysis (this pass) found that of the 54 "wrong-label-but-valid-evidence" cases,
    only 4 actually quote evidence overlapping the true gold span -- the other 50 are verbatim
    but point at the WRONG retrieved chunk, a distinct failure mode (evidence *selection* among
    already-retrieved candidates) that a coarse "was gold present somewhere in context" check
    cannot see, and one a follow-up action (re-examine candidates, targeted second query) could
    plausibly help with.
Why this experiment exists: determines whether E09 (agent justification) is worth pursuing at
    all, and if so, on what evidence base -- does NOT build or run an agent itself.
Input dataset/split: E07's frozen outputs on TRAIN_ARCH_v1 only (150 cases). No new model calls,
    no DEV, no TEST.
Frozen dependencies: E07's predictions, TRAIN_ARCH_v1, TRAIN_ARCH_v1_RETRIEVED_retrieval_v1
    (+GOLD), retrieval_v1 (read-only, used only for a zero-cost deeper-candidate-pool
    diagnostic query -- never modified), classification_prompt_v1 (untouched, not re-invoked).
Independent variable: none -- this is a diagnostic/analysis experiment, not a controlled
    comparison.
Controlled variables: n/a.
Metrics: case-level failure taxonomy counts, retrieval-aware and agent-fixability
    classification, oracle-action recoverability, Contradiction-specific breakdown, E05/E07
    transition diagnostics.
Expected cost: $0 (no LLM calls anywhere in E08; the one live re-query used for the retrieval-
    limited oracle-action analysis is a local, deterministic BM25 index lookup, already
    performed this pass).
Expected runtime: dominated by manual review time (proposed sample: 66 deterministically
    selected cases, summary.md section 6), not compute.
Stop condition: Stage A ends at this proposal. Stage B (manual review + full diagnostic
    artifact) begins only after explicit approval.
Result: PENDING -- Stage A only.
Decision: PENDING -- one of PROCEED TO AGENT JUSTIFICATION / PROCEED ONLY WITH NARROW SELECTIVE
    AGENT / AGENT NOT JUSTIFIED, per the brief's required end-state (not decided in Stage A).
What becomes frozen after this: PENDING -- the evidence base for E09, not an A3 architecture
    decision itself.
```

## Stage A vs. Stage B

Same two-stage structure as every prior reconstruction-v2 experiment. **Stage A (this commit's
state): audit E07's existing outputs, verify error counts, run one pilot zero-cost refinement
(evidence-overlap-with-gold vs. evidence-merely-verbatim) that materially changes how the "54
wrong-label-but-valid-evidence" figure should be read, run one zero-cost oracle-action
diagnostic for all 6 retrieval-limited cases, propose the full case-level diagnostic schema,
failure taxonomy, evaluator-only/runtime-observable signal separation, agent-candidate criteria,
and a deterministic manual-review sample.** No LLM call anywhere. **Stage B (after explicit
approval): execute the full manual review and produce the complete diagnostic artifact.**

Full Stage A audit and proposal: `summary.md`.
