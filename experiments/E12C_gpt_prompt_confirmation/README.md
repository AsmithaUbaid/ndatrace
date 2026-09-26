# E12C — GPT-P0 vs GPT-P3 confirmation (Stage A: design + forecast only)

```
Experiment ID: E12C
Question: Does GPT-P3 reproduce its directional advantage over P0 on a fresh, document-disjoint TRAIN confirmation manifest?
Nature: confirmation/replication of E12B's near-tie (P3 +8 net joint, one short of +9) -- NOT another optimisation round.
Prompts: exactly GPT-P0 and GPT-P3, byte-identical to E12B. No P1/P2, no new prompts, no tuning.
Manifest: TRAIN_GPT_PROMPT_CONFIRM_v1 (150 cases, 50/50/50, seed 1300, 67 docs), disjoint from PROMPT/ARCH/ORACLE/GPT_PROMPT.
Frozen: retrieval_v1 top-5 (one shared context artifact), openai/gpt-5-mini, 60s timeout, schema/parser/validator/scorer.
Last prompt-selection experiment: no third confirmation manifest.
Status: Stage A only -- no model call made. See summary.md and config.yaml.
```
