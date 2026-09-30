# E12B — GPT-Specific Prompt Optimisation (Stage A: design + forecast only)

```
Experiment ID: E12B
Question: Can a compact GPT-specific classification prompt materially improve evidence-grounded NDA
    classification over the current Qwen-selected P0 without changing model, retrieval, context size,
    output schema, or evaluator?
Why: P0 (classification_prompt_v1) was selected for Qwen2.5-7B in E03 (where richer prompts pushed
    Contradictions toward NotMentioned). E08B showed GPT-5-mini is far stronger on the same RAG
    architecture, so P0 is a valid GPT baseline but has never been optimised for GPT.
Manifest: TRAIN_GPT_PROMPT_v1 (150 cases, 50/50/50, seed 1200, 74 docs), document-disjoint from TRAIN_PROMPT_v1,
    TRAIN_ARCH_v1 and TRAIN_ORACLE_v1. No DEV, no TEST.
Frozen: retrieval_v1 top-5 (one shared context artifact), openai/gpt-5-mini, schema, parser, validator, scorer.
Independent variable: system prompt (GPT-P0 control, P1 definitions, P2 decision order, P3 failure-informed).
Not in scope: few-shot, chain-of-thought, retrieval, K, agents, model change.
Status: Stage A only -- no model call made. See summary.md and config.yaml.
```
