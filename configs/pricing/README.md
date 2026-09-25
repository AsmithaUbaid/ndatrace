# Pricing configs

One file per provider/model, verified against the provider's live pricing page before use —
**never trust a remembered or historical price.** `docs/decisions.md`'s ADR-001 already found
hosted pricing drifted mid-project once; treat every price as stale until re-checked on the
day it's used.

Schema (see `_schema_example.yaml` — placeholder values only, not real prices):

```yaml
provider:                          # e.g. openrouter, groq, ollama
model:                              # e.g. google/gemini-2.5-flash-lite
input_price_per_million:            # USD
output_price_per_million:           # USD
cached_input_price_if_known:        # USD, or null
reasoning_token_notes_if_applicable: # free text, or null
date_checked:                       # YYYY-MM-DD, the day this was verified live
source_note:                        # where this was checked (URL or "OpenRouter pricing page")
```

No real pricing values are populated yet — that happens in E00B/E02, against live-verified
numbers, not carried over from the historical `pipeline/model_gateway.py` `PRICING_PER_MILLION`
table without re-checking.
