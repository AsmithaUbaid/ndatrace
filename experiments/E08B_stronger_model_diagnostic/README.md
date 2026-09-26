```
Experiment ID: E08B
Question: How much of A2 Standard RAG's remaining failure is attributable to the base model
    rather than the retrieval architecture?
Hypothesis: not pre-assumed -- this is a controlled model-substitution diagnostic. E08 found
    the largest single failure bucket (49.2% overall, 65.5% for Contradiction) is
    MODEL_REASONING_LIMITED with no identified information-acquisition fix; if a stronger model
    resolves most of that bucket, a model upgrade may be a simpler, cheaper intervention than a
    selective agent (E09/A3). If it does not, the reasoning limitation is more likely intrinsic
    to the task/prompt rather than Qwen-specific, strengthening the case for agentic
    investigation instead.
Why this experiment exists: E08's own recommended next diagnostic, required before E09 makes a
    final agent-justification decision -- isolates model capability from architecture, changing
    exactly one variable (qwen2.5:7b-instruct-ctx16k -> openai/gpt-5-mini) and nothing else.
Input dataset/split: The IDENTICAL frozen TRAIN_ARCH_v1 manifest and
    TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json artifact E07 used (150 cases). No DEV, no TEST, no
    retrieval rerun (integrity-verified this pass: 150/150 present, ordering matches, zero gold
    leakage, config confirmed).
Frozen dependencies: classification_prompt_v1 (=P0, unchanged, no GPT-specific variant),
    retrieval_v1 (unmodified, not re-invoked -- reads the frozen artifact only),
    evaluation.structured_output.parse_structured_output (unchanged),
    pipeline.evidence_validator.validate_evidence (unchanged), compact
    {"label": ..., "evidence": [...]} output schema (unchanged), temperature 0 (OpenRouter
    default unless the provider requires otherwise -- checked this pass, see summary.md
    section 4).
Independent variable: model only (qwen2.5:7b-instruct-ctx16k -> openai/gpt-5-mini via
    OpenRouter). Everything else -- prompt, context, schema, parser, validator -- held fixed.
Controlled variables: manifest, case ordering, retrieved context, prompt wording, output
    schema, parser, evidence validator, evidence instruction.
Metrics: the full matched A2-Qwen vs. A2-GPT comparison (accuracy, Macro-F1, per-class recall,
    joint success, strict/usable parse validity, evidence validity, tokens, latency, cost),
    case-level transitions, E08 bucket-recovery mapping, wrong-evidence subgroup re-analysis,
    paired McNemar + bootstrap statistics, and cost-effectiveness (cost per additional correct/
    joint-success case).
Expected cost: projected ~$0.09-0.38 for 150 real GPT-5 mini calls (see summary.md's budget
    gate section for the full input/output cost breakdown and uncertainty bounds) -- well
    within the available budget headroom (~$3.63 of the $3.75 allowed-spend ceiling).
Expected runtime: dominated by 150 real hosted API calls -- OpenRouter/GPT-5-mini latency is
    typically sub-2s per call based on historical E01 Oracle data, so a full run should complete
    in a few minutes; not yet measured for this specific task shape.
Stop condition: Stage A ends at this proposal -- no GPT-5 mini call has been made. Stage B
    begins only after explicit approval.
Result: PENDING -- Stage A only.
Decision: PENDING -- one of the four valid outcomes (A/B/C/D per the brief), not a final A3
    architecture decision.
What becomes frozen after this: PENDING -- an evidence base for E09's final agent-justification
    decision, not an architecture change itself.
```

## Stage A vs. Stage B

Same two-stage structure as every prior reconstruction-v2 experiment. **Stage A (this commit's
state): audit the current GPT-5 mini provider/pricing/config, verify the frozen A2 input
artifact's integrity, read the real reconstruction-v2 spend ledger and apply the existing
budget gate (`evaluation.budget.check_budget_against_ledger`), project the 150-case cost using
real historical GPT-5-mini output-token data (not a guess), and propose the exact matched-
comparison, bucket-recovery, and statistical analysis plan.** No GPT-5 mini call has been made.
**Stage B (after explicit approval): execute the run.**

Full Stage A audit and proposal: `summary.md`.
