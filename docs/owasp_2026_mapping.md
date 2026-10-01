# OWASP LLM Top 10: 2025 to 2026 mapping

E21 and E22 (September 2026) assessed NDATrace against the **2025** edition of the OWASP Top 10
for LLM Applications, the edition that existed at the time. OWASP published a **2026** edition on
4 August 2026, after E21/E22 had already run. This file maps the existing, already-measured
findings onto the 2026 numbering. **It is a relabeling exercise, not a new assessment** — the
2026 edition keeps the same ten underlying risks (reordered, one renamed), so nothing here required
a new test or a paid model call. If you're looking for the actual test methodology and raw
findings, they're in `experiments/E21_owasp_llm_top10/summary.md` (original numbering, left
unmodified) and `experiments/E22_targeted_security_remediation/summary.md` (the two FAILs'
remediation). This file does not restate that evidence, only re-sorts it.

## Why there's a mapping instead of a rerun

The 2026 edition's ten categories are the same ten risks as 2025, reordered by updated incident
data, plus one rename (System Prompt Leakage → Hidden Context Exposure, same underlying risk: can
an attacker extract instructions/context the system wasn't meant to reveal). Nothing was added,
nothing was dropped. Re-testing would mean re-running checks against risks that haven't changed —
remapping the existing results is the accurate description of what changed, which is the category
numbers, not the product.

## The mapping, with final status (post-E22)

| 2026 | 2026 name | 2025 | 2025 name | Status (post-E22 remediation) |
| --- | --- | --- | --- | --- |
| LLM01 | Prompt Injection | LLM01 | Prompt Injection | PARTIAL (E22: detection 4/11, below the pre-declared ≥8/11 bar) |
| LLM02 | Sensitive Information Disclosure | LLM02 | Sensitive Information Disclosure | PARTIAL (no auth on `GET /results`/`GET /review/{id}`, not remediated) |
| LLM03 | Excessive Agency | LLM06 | Excessive Agency | PASS (no agent code reachable from the backend) |
| LLM04 | Supply Chain | LLM03 | Supply Chain | PARTIAL (38 known CVEs across 5 packages at baseline; 2 low-risk patched in E22, see citation below) |
| LLM05 | Data and Model Poisoning | LLM04 | Data and Model Poisoning | PARTIAL (adversarial clause ranks #1 ahead of genuine evidence in 8/8 constructed cases) |
| LLM06 | Unbounded Consumption | LLM10 | Unbounded Consumption | PASS (E22: real cost/rate/length limits now enforced, closing the E21 gap) |
| LLM07 | Misinformation | LLM09 | Misinformation | PARTIAL (reframes E20's measured ~23% label error rate; no correctness guarantee surfaced to the user) |
| LLM08 | Hidden Context Exposure | LLM07 | System Prompt Leakage | PASS (0/10 fresh hosted attacks leaked, small-sample caveat applies) |
| LLM09 | Vector and Embedding Weaknesses | LLM08 | Vector and Embedding Weaknesses | PARTIAL (no vector DB in the frozen BM25-only runtime; same ranking-robustness finding as LLM05 above) |
| LLM10 | Improper Output Handling | LLM05 | Improper Output Handling | PASS (15/15 malformed-output cases handled safely) |

**Totals: 4 PASS, 6 PARTIAL, 0 FAIL** (both of the original 2 FAILs were remediated in E22: Unbounded
Consumption to PASS, Prompt Injection to PARTIAL — not rounded up to PASS, since the pre-declared
detection bar wasn't met).

## Source for the 2026 category list

OWASP published the 2026 edition on 4 August 2026. Category list and reordering verified via live
web search at the time this mapping was written (this project's AI-assistant knowledge cutoff
predates the 2026 edition's publication, so this was checked, not recalled):
- [OWASP LLM Top 10 2026: The Full List and What Changed](https://www.superblocks.com/blog/owasp-llm-top-10)
- [OWASP Releases GenAI LLM Top 10 2026](https://cybersecuritynews.com/owasp-genai-llm-top-10-2026/)
- [OWASP Top 10 for Large Language Model Applications (official project page)](https://owasp.github.io/www-project-top-10-for-large-language-model-applications/)
