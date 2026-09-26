```
Experiment ID: E04
Question: How far can a cheap deterministic rule-based classifier go on NDA compliance
    classification before using an LLM?
Hypothesis: A small set of per-hypothesis positive/negative keyword rules over full NDA text
    sets a real but modest non-AI floor -- strong on Entailment (literal phrase matches),
    structurally advantaged on NotMentioned (default fallback), weak on Contradiction (no
    negation/exception reasoning) -- that every LLM-based architecture (A1/A2/A3) must clear
    to justify its cost.
Why this experiment exists: establishes the cheapest possible classification baseline before
    E05 (full-context LLM) and E07 (RAG), so later architecture comparisons have a $0,
    zero-latency floor to measure against (reconstruction brief, architecture comparison E12).
Input dataset/split: Official TRAIN only, full universe (423 docs x 17 hypotheses = 7,191
    cases, natural class distribution 3,530 Entailment / 2,820 NotMentioned / 841
    Contradiction) -- see summary.md section 8 for why no subsampling is proposed.
Frozen dependencies: NONE yet -- this is a rule-only experiment, no model, no prompt, no
    retrieval config is invoked. classification_prompt_v1 and retrieval_v1 are untouched by
    E04.
Independent variable: rule family (R0 baseline; R1+ only if a specific observed TRAIN failure
    justifies one -- see summary.md section 9-10).
Controlled variables: input representation (full NDA text, never retrieved excerpts -- see
    summary.md section 3), evidence-span mechanism, scorer/metrics, TRAIN-only development.
Metrics: Accuracy, Macro-F1, per-class recall (esp. Contradiction Recall + CI), confusion
    matrix, Evidence Recall/Precision, joint label+evidence correctness, rule-fire rate vs.
    default-fallback rate, mean/p90 latency, cost ($0).
Expected cost: $0 (no LLM/API calls at any point in E04).
Expected runtime: single-digit seconds for the full 7,191-case TRAIN universe (pure
    deterministic substring search, no model inference).
Stop condition: Stage A ends at this proposal -- no benchmark has been run. Stage B begins
    only after explicit approval.
Result: COMPLETE. Accuracy 56.8%, Macro-F1 0.471, Contradiction Recall 17.2% [95% CI
    14.8-19.9%], NotMentioned Recall 92.2%. Evidence Recall 29.0%, Evidence Precision 64.8%,
    joint label+evidence correctness 48.2% overall. Dominant failure mode (84.9% of all errors):
    plain lexical coverage -- the hypothesis's keyword list never matched anything in the
    document, not exception/carve-out or negation-specific failures.
Decision: `pipeline/rule_baseline.py` frozen unmodified as `A0_rule_baseline_v1`. No rule
    tuning, no new rule family -- reuse-with-disclosure, per approved Stage A recommendation.
What becomes frozen after this: `A0_rule_baseline_v1` (source, input representation, rule and
    evidence semantics, TRAIN-only metrics) as the non-AI floor for E12's architecture
    comparison.
```

## Stage A vs. Stage B

Same two-stage structure as E00/E01/E03/E06. **Stage A (frozen earlier): audit existing
`pipeline/rule_baseline.py`, define input representation, define TRAIN-only development
universe, propose the simplest R0 baseline.** **Stage B (this run, complete): execution** -- R0
run on the full TRAIN universe (7,191 cases), failure analysis complete. Per the approved
design decision, R1+ is explicitly NOT justified or run -- the dominant observed failure mode
is plain lexical coverage, and the user's frozen decision (no rule tuning, no new rule family)
holds regardless of what the failure data showed.

Full Stage A audit and Stage B results: `summary.md`. Existing reusable code:
`pipeline/rule_baseline.py` (`classify_by_keywords`, `classify_with_span`) -- historical
(T-series pre-reconstruction), frozen unmodified as `A0_rule_baseline_v1`
(source commit `7d33d038f81a1b0da093bce70cb22e267c552f91`, confirmed unmodified by empty
`git diff` at run time). New Stage B code: `scripts/run_e04_rule_baseline.py` (runner),
`scripts/analyze_e04_rule_baseline.py` (metrics + failure analysis).
