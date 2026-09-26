# E13 — GPT Full-Context vs RAG Architecture Comparison (Stage A: design + forecast only)

```
Experiment ID: E13
Question: Under the same GPT-5-mini model, prompt, output contract, and evaluator, does retrieval_v1 RAG outperform or adequately match
    full-NDA context while reducing token use, latency, and cost?
Arms: A = FULL NDA context; B = retrieval_v1 top-5 RAG. Only the text in the context field differs.
Dataset: DEV_ARCH_v1 (150 DEV cases, 50/50/50, seed 1400, 51 docs) -- DEV is Role B; historical DEV exposure is disclosed (config.yaml).
Frozen: openai/gpt-5-mini, GPT-P0 (byte-identical system prompt), shared neutral wrapper "NDA context:", schema/parser/validator/scorer, 60s timeout.
Not in scope: top-11, agent, prompt/retrieval tuning, TEST, final-architecture claim.
Status: Stage A only -- no model call made. See summary.md and config.yaml.
```
