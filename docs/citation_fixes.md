# Citation Fixes for the Final Report

Precision issues to fix before/while drafting the final report. Items 1–3 are the original
citation-precision issues flagged in instructor feedback on the Week 3 Problem Statement
(`PE6201_Project_Problem_Statement_Asmitha.pdf`); items 4–5 were updated after final
completed, since the model/architecture identity they describe changed. These are report-writing
fixes, not code changes — items 1–3's original context is the instructor's Week 3 feedback on the
Problem Statement's citation precision.

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

## 4. Pricing — cite the model actually used in the final result, not an intermediate one

**Status update (post-final): the final report's cost analysis should lead with
`openai/gpt-5-mini` pricing and the real measured cost of the final TEST run, not Gemini's.**

The history here has two steps, and the final report should reflect the *last* one, not the
middle one:

1. The original Problem Statement's GPT-5-mini pricing reference ($0.25/M input, $2/M output) was
   flagged by the instructor as not-yet-current at the time.
2. The legacy pipeline's own C01 model bake-off moved to
   `google/gemini-2.5-flash-lite` for cost/latency reasons — that model was used throughout the
   **legacy** work (T018 onward), but **final re-derived the model choice
   independently (E01) and selected `openai/gpt-5-mini`** as the final, selected architecture's
   model. Gemini is not part of the final result and should not be presented as the cost-analysis
   reference point.

**Fix:** cite `openai/gpt-5-mini`'s real, live-verified OpenRouter pricing and the real measured
total cost of the full n=2,091 final TEST run (**≈$4.23 total, ≈$0.0020/case** — see
`results/final/v2/gpt_full_test_metrics.json`'s `ops` block, and
`experiments/E18_business_course_synthesis/` for the full cost-to-serve business analysis). Gemini
pricing may still be cited as historical context for the legacy pipeline (see
`docs/architecture_decisions/INDEX.md`'s ADR-001), but must be clearly labeled as such, not as the
current reference point.

## 5. Local/hosted comparison — cite Qwen, not Llama/Groq

The Problem Statement's hosted-vs-local commitment ("Llama 3.2 3B Instruct locally") went through
two substitutions during the **legacy** pipeline (local Llama 3.2 3B via Ollama, then
a Groq-hosted `openai/gpt-oss-20b` fallback after Llama stopped being available free-tier — see
`pipeline/model_gateway.py`'s `ModelGateway.groq()`) — neither of these is final's
local-model arm.

**Final's actual local/free-tier comparison is `qwen2.5:7b-instruct` (ctx16k,
via Ollama)**, run on the full n=2,091 official TEST set: accuracy 49.9%, macro-F1 0.431, joint
39.7%, Contradiction recall 25.5%, $0 API cost (local compute/wall-time not monetized — see
`results/final/v2/qwen_full_test_metrics.json`). The final report's hosted-vs-local
section should cite Qwen as the local comparator, not Llama or Groq's `gpt-oss-20b` — those remain
accurate as legacy historical record but are not part of the final result.
