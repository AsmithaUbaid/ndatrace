# Model configs

One file per candidate model to be screened in E02 (model screening) — provider, model id,
context window, and which pricing config (`configs/pricing/`) it pairs with. No models are
selected yet; this directory is a placeholder for E02's output, not an input to it.

Existing historical model wiring lives in `pipeline/model_gateway.py` (`ModelGateway.local()`,
`.groq()`, hosted OpenRouter default) — reused as-is, not duplicated here. This directory is
for the versioned, reviewable config *record* of what E02 screens and selects, once run.
