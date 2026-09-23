# Citation Fixes for the Final Report

Four precision issues flagged in instructor feedback on the Week 3 Problem Statement
(`PE6201_Project_Problem_Statement_Asmitha.pdf`), received 2026-09-23. These are report-writing
fixes, not code changes — recorded here so they aren't lost before the final report is drafted.
See `CLAUDE.md`'s Decisions Log ("Instructor feedback... Gap 3") for the original context.

## 1. Workload/staff-hours figure — label as vendor research

The "52% of organisations handle 101–1,000 contracts annually... 2–4 hours per contract" figure
comes from **LegalOn Technologies' 2025 State of Contracting Survey** (n=286, published 15 Jan
2025). The numbers themselves are accurate, but LegalOn sells AI contract review software — this
is vendor research, not neutral third-party data, and must be labeled as such wherever cited, or
triangulated against an independent source.

**Fix:** change "A 2025 survey of 286 legal professionals found..." to something like:
> "A 2025 vendor survey (LegalOn Technologies, *State of Contracting Survey*, n=286) found..."

## 2. ContractNLI follow-up citation — wrong link (whole volume, not the paper)

The Problem Statement cites `https://aclanthology.org/2024.nllp-1.pdf` — this is the **entire
NLLP 2024 proceedings volume**, not the specific paper referenced (the Contradiction F1 numbers
for GPT-4/Mixtral 8x7B vs. Span NLI BERT).

**Correct citation:** Narendra, Shetty & Ratnaparkhi, NLLP 2024 (co-located with EMNLP 2024).

**Fix:** replace the link with `https://aclanthology.org/2024.nllp-1.11/` (the specific paper's
ACL Anthology page — open it to confirm the exact title before citing, rather than guessing it).

## 3. Span NLI BERT number — wrong figure cited

The Problem Statement cites **0.389** for the original Span NLI BERT baseline. This is the
**NDA-fine-tuned ablation** result, not the paper's actual headline number.

**Correct figures** (per instructor feedback, verify against the ContractNLI paper directly
before publishing):
- **Headline Span NLI BERT result: 0.357 ± 0.039** — cite this, not 0.389.
- Best result in the paper overall: **0.405** (DeBERTa).

**Fix:** replace "0.389 for the original Span NLI BERT baseline" with "0.357 ± 0.039 for the
original Span NLI BERT baseline (best-in-paper: 0.405, DeBERTa)".

## 4. GPT-5 mini pricing — don't present as current

The Problem Statement's cost-to-serve section uses GPT-5 mini pricing ($0.25/M input, $2/M
output) as the live reference point. Two things have changed since:
- This pricing is confirmed **legacy** as of the instructor's review — don't cite it as current
  in the final report.
- This project's own C01 model bake-off (2026-09-22) already moved the default model to
  **`google/gemini-2.5-flash-lite`** ($0.10/M input, $0.40/M output, live-verified via OpenRouter)
  specifically for cost/latency reasons — that's what was actually used throughout every real
  experiment in this project (T018 onward).

**Fix:** the final report's cost analysis should lead with Gemini's verified pricing and real
measured costs (see `docs/experiments.md`'s C01/T018/T024/T030/T015 rows), not GPT-5 mini's,
which only appears now as a documented fallback in `pipeline/model_gateway.py`'s
`PRICING_PER_MILLION`.

## Also worth including (not a citation fix, but related)

**A fifth model substitution occurred later in the project** and should be disclosed the same way:
the problem statement committed to "Llama 3.2 3B Instruct locally" for the hosted-vs-local
comparison (C02). Local Llama 3.2 3B via Ollama was built and used for the bulk of the final
evaluation. Groq (a free-tier hosted alternative, tried to avoid heating the dev machine) no
longer offers a general-purpose Llama chat model on its free tier (checked live, 2026-09-23) - only
`llama-prompt-guard`, a content-moderation classifier. Where Groq is used at all in this project
(see `pipeline/model_gateway.py`'s `ModelGateway.groq()`), it runs `openai/gpt-oss-20b` instead.
The final report should state this plainly rather than let a reader assume "Llama" was used
end-to-end.
