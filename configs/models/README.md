# Model configs

**E02 (model screening) was SKIPPED** — E01 (Oracle) already performed a controlled comparison of
2 local and 2 hosted models using the same manifest, prompt semantics, and output schema, so a
separate model-screening experiment would have duplicated a question E01 already answered. Frozen
from E01: primary local model `qwen2.5:7b-instruct`, hosted model `openai/gpt-5-mini` (the final
selected model). See `docs/experiment_registry.md`'s E02 row and `experiments/E01_oracle/summary.md`.

This directory therefore never received the per-candidate-model config files it was originally
scaffolded for. Model wiring lives in `pipeline/model_gateway.py` (`ModelGateway.local()`,
`.groq()`, hosted OpenRouter default) and `configs/pricing/` — this directory is kept empty
(besides this README) as a record of that decision, not as a gap to fill.
