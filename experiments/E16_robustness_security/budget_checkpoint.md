# Budget checkpoint before E16 / final TEST (offline; no model calls; TEST content not accessed)

Ledger (actual, append-only): **$3.1121157** (E15 spend $0.3077 included). Plan $5.00; protected reserve $1.25.
Remaining total: **$1.8879**. Remaining before reserve: **$0.6379** (forward-spendable without touching the reserve).

## Per-case cost basis (GPT-5-mini + GPT-P0 + FULL; E13 n=150 + E15 n=138 = 288 real calls)
mean $0.002152 · median $0.002032 · p90 $0.003353 · p95 $0.003875 · max $0.005867. (RAG arm, E13: mean $0.001738, p90 $0.002758.)
Caveat: TEST document-length distribution is unknown to this checkpoint (TEST not accessed); a ×1.25 length sensitivity is shown.

## Hosted GPT-5-mini FULL forecast
| n | expected | expected ×1.25 | conservative (p90 every call) | stress (p90 ×1.5) | fits $0.638 pre-reserve? | fits $1.888 total (reserve consumed)? |
|---|---|---|---|---|---|---|
| 150 | $0.323 | $0.403 | $0.503 | $0.754 | yes (expected & conservative) | yes |
| 300 | $0.646 | $0.807 | $1.006 | $1.509 | **no** (marginally over even expected) | conservative yes |
| 450 | $0.968 | $1.210 | $1.509 | $2.263 | no | conservative yes, stress no |
| **2,091 (full TEST)** | **$4.50** | $5.62 | $7.01 | $10.52 | **no** | **no — exceeds the whole $5 plan** |
Largest n inside the pre-reserve allowance: ~296 expected, ~190 conservative. Full-TEST RAG alone would be ~$3.63 expected / $5.77 conservative — also unaffordable. **A full hosted GPT TEST run is not affordable under the $5 plan.**
Any E16 hosted robustness calls (Stage B) draw from the same $0.638 — every dollar there reduces the hosted TEST subset.

## Documented final-evaluation plan (verified in docs)
- `docs/project_contract.md` §14: local-first; no repeated full-dataset hosted runs; estimate before every hosted run.
- `experiments/E00B_budget_forecast/summary.md` §12–14: the recommended plan was a **300-case stratified TEST subsample × non-rule architectures on ONE hosted model**, with the **full 2,091-case final pass run locally** (local runtime, not dollars, was the constraint: ~12.4 h for three local architectures with Llama 3.2 3B; A1 full-context ~4.5 h).
- `docs/evaluation_protocol.md` §17/§19–20: TEST = Role C, 2,091 cases (968 E / 220 C / 903 NM), run once after everything is frozen; the current reconstruction-v2 has not touched TEST. (Historical pre-reconstruction T041 used Gemini/Llama; it is not this candidate.)
Note: E00B's "E15 hosted-vs-local" is the OLD numbering; the current E15 is routing.

## Locally / free-runnable options already supported
- Rule baseline: $0, seconds, full 2,091 (already a reference arm).
- Ollama: `llama3.2:3b` (E00B: ~7.7 s/case FULL → ~4.5 h for 2,091; previously overheated the laptop), `qwen2.5:7b-instruct` / `-ctx16k` (used in E05/E07 as a local full-context comparator; slower than Llama 3B — not measured here). `ModelGateway.local()`.
- Groq free tier (`gpt-oss-20b`, `ModelGateway.groq()`, key present): $0 but rate-limited and a different model than the frozen candidate (disclose as substitution, per docs/citation_fixes.md).
None of these is the frozen candidate; they are comparators/fallbacks.

## Proposed final-evaluation strategy (needs your approval; the $5 plan is NOT changed)
1. **Frozen candidate (GPT-5-mini + P0 + FULL): hosted, stratified TEST subsample, once.** Recommended n=150 (expected $0.32, conservative $0.50) if E16 hosted spend is kept ≤ ~$0.10; n≈190 is the ceiling with conservative pricing. n=300 needs about $0.65–1.01, which needs your explicit decision to dip into the reserve or raise the budget — not assumed.
2. **Full 2,091-case TEST on $0 arms only:** rule baseline (seconds) and one local full-context comparator (Llama 3.2 3B, ~4.5 h, thermal caution) or Groq free tier — reports the whole test set including all 220 Contradictions where hosted can't.
3. Report the hosted subsample with Wilson CIs; note Contradiction n≈16 at n=150 (≈32 at n=300) makes the hosted Contradiction estimate descriptive. Optionally oversample Contradiction in the subsample (stratified, frozen seed) — needs approval since it changes the "stratified natural mix" design.
4. Routing: no policy adopted (E15 C), so TEST reports raw model outputs + R1 integrity flags only.
Decision needed: hosted subset size (150 vs up to ~190 vs 300 with reserve use) and whether to run the local/Groq full-TEST comparator.
