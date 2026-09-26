```
Experiment ID: E05
Question: How well does qwen2.5:7b-instruct classify NDA requirements when given the full NDA
    text, with retrieval removed from the pipeline?
Hypothesis: Full-context input removes retrieval's evidence-recall ceiling (~92%, E06) entirely
    -- every relevant clause is always present -- but may introduce a long-context "needle in a
    haystack" reasoning cost that retrieval's compact, pre-filtered context doesn't have. Net
    effect on accuracy/Contradiction Recall relative to E03's retrieved-context result is not
    assumed in advance.
Why this experiment exists: isolates the effect of retrieval by holding model and prompt fixed
    and changing only the input-construction architecture (A1: full document vs. later A2: RAG).
    Not a prompt experiment (classification_prompt_v1 is frozen and unmodified), not a model
    experiment (model was frozen in E01/E02).
Input dataset/split: Official TRAIN only. Proposed: TRAIN_ARCH_v1 (new, 150 cases, 50/50/50
    balanced, seed=700), NOT TRAIN_PROMPT_v1 -- see summary.md section 9 for why a fresh,
    disjoint manifest is proposed instead of reusing E03's set.
Frozen dependencies: qwen2.5:7b-instruct (local only), classification_prompt_v1 (= P0, system
    prompt and output-schema semantics byte-for-byte unchanged), temperature 0.0. retrieval_v1
    is NOT used -- A1 is retrieval-free by design.
Independent variable: input representation (full NDA document text, vs. E03's retrieved
    excerpts, vs. E07's future retrieval_v1 context) -- the ONLY thing this experiment changes
    relative to E03's classification mechanism.
Controlled variables: model, prompt wording/semantics/output schema (extended additively for
    evidence, not changed -- see section 5), temperature, parser, case ordering, retry policy.
Metrics: Accuracy, Macro-F1, per-class recall (Contradiction Recall + CI), confusion matrix,
    Evidence Recall/Precision, joint label+evidence correctness, input/output token stats,
    latency stats, parse-valid rate, retry count, cost ($0).
Expected cost: $0 (local-only, no hosted calls).
Expected runtime: NOT YET ESTIMATED WITH CONFIDENCE -- full-context inputs are 1.7-5x longer
    than E03's retrieved-context inputs (mean ~2,084 vs ~1,150-1,245 tokens; max 5,581 vs ~1,300
    tokens in TRAIN_ARCH_v1). Stage A proposes a small real calibration run (5-10 cases spanning
    the length distribution) before committing to the full 150-case runtime estimate, rather
    than extrapolating from E03's much-shorter-context timing.
Stop condition: Stage A ends at this proposal -- no benchmark has been run, no Qwen call made.
    Stage B begins only after explicit approval, and only after two disclosed blocking
    technical risks (context-window truncation, request timeout) are resolved -- see
    summary.md sections 4-6.
Result: PENDING -- Stage A only.
Decision: PENDING.
What becomes frozen after this: PENDING -- A1 architecture definition and TRAIN-only metrics,
    to be later compared against E07 (matched manifest) and Oracle (E01) for the three-point
    decomposition described in the brief.
```

## Stage A vs. Stage B

Same two-stage structure as E00/E01/E03/E04/E06. **Stage A (this commit's state): audit
existing full-context implementations, define A1's architecture wrapper around the frozen
`classification_prompt_v1`, propose an evidence-output extension, measure the real token-length
distribution, identify context-window/timeout risks, and propose a fresh matched-comparison
manifest.** No benchmark has been run, no Qwen call made. **Stage B (after explicit approval):
execution.**

Full Stage A audit and proposal: `summary.md`. New artifact created this pass (deterministic,
local-only, zero model calls, same precedent as E01/E03's manifest-building Stage A step):
`experiments/E05_full_context/TRAIN_ARCH_v1.json` (`scripts/build_train_arch_manifest.py`).
