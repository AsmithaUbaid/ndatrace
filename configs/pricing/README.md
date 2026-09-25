# Pricing configs

One file per provider/model, verified against the provider's live pricing page before use —
**never trust a remembered or historical price.** `docs/decisions.md`'s ADR-001 already found
hosted pricing drifted mid-project once; treat every price as stale until re-checked on the
day it's used.

Schema (see `_schema_example.yaml` — placeholder values only, not real prices). **Revised
after E00B review** to separate a model's canonical published rate from what cost forecasts
should actually assume, because a free/discounted tier existing does not make the model's
real price $0 or guarantee a future run stays within its limits:

```yaml
provider:                                        # e.g. openrouter, groq, local/ollama
model:                                            # e.g. google/gemini-2.5-flash-lite
published_input_price_per_million:                # USD -- the provider's real rate card, never $0 just because a free tier exists
published_output_price_per_million:               # USD
published_cached_input_price_per_million:         # USD, or null
account_tier:                                     # e.g. "pay-as-you-go", "free (rate-limited)", "local compute"
effective_cost_assumption_input_per_million:       # USD -- what forecasts actually use; usually == published, only lower when a free/discounted tier has been explicitly committed to for a specific run
effective_cost_assumption_output_per_million:      # USD
effective_cost_assumption_note:                    # free text -- why the effective rate equals or differs from published
reasoning_token_notes_if_applicable:               # free text, or null
date_checked:                                      # YYYY-MM-DD, the day this was verified live
source_note:                                       # where this was checked (URL or "OpenRouter pricing page")
free_tier_limits:                                  # dict of rate limits, or null -- a RATE LIMIT, not a price
lifecycle:                                          # dict: status, and provider-specific detail if a retirement/deprecation applies to a SPECIFIC backend NDATrace might actually hit
```

`evaluation/budget.py`'s `load_pricing()`/`Pricing` dataclass reads the
`effective_cost_assumption_*` fields for cost calculations (exposed as the familiar
`input_price_per_million`/`output_price_per_million` properties for backward compatibility),
while `published_*` stays available on the `Pricing` object for reporting/transparency.

Real entries currently on file: `openrouter_google_gemini-2.5-flash-lite.yaml`,
`openrouter_openai_gpt-5-mini.yaml`, `groq_openai_gpt-oss-20b.yaml`,
`local_ollama_llama3.2-3b.yaml` — all verified 2026-09-26, corrected once after review (GPT-5
mini's cached-input rate, Groq's canonical price vs. free-tier condition, Gemini's
provider-specific lifecycle risk). Not carried over from the historical
`pipeline/model_gateway.py` `PRICING_PER_MILLION` table without independently re-checking.
