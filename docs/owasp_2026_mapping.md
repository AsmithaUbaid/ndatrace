# OWASP LLM Top 10 (2026): category-by-category results

E21/E22 assessed NDATrace against all 10 categories of the OWASP Top 10 for LLM Applications,
2026 edition. Raw test methodology and findings are in
`experiments/E21_owasp_llm_top10/summary.md` and
`experiments/E22_targeted_security_remediation/summary.md` (the two FAILs' remediation); this file
is the category-by-category scorecard.

## Results, with final status (post-E22)

| Category | Name | Status (post-E22 remediation) |
| --- | --- | --- |
| LLM01 | Prompt Injection | PARTIAL (E22: detection 4/11, below the pre-declared ≥8/11 bar) |
| LLM02 | Sensitive Information Disclosure | PARTIAL (no auth on `GET /results`/`GET /review/{id}`, not remediated) |
| LLM03 | Excessive Agency | PASS (no agent code reachable from the backend) |
| LLM04 | Supply Chain | PARTIAL (38 known CVEs across 5 packages at baseline; 2 low-risk patched in E22, see citation below) |
| LLM05 | Data and Model Poisoning | PARTIAL (adversarial clause ranks #1 ahead of genuine evidence in 8/8 constructed cases) |
| LLM06 | Unbounded Consumption | PASS (E22: real cost/rate/length limits now enforced, closing the baseline gap) |
| LLM07 | Misinformation | PARTIAL (reframes E20's measured ~23% label error rate; no correctness guarantee surfaced to the user) |
| LLM08 | Hidden Context Exposure | PASS (0/10 fresh hosted attacks leaked, small-sample caveat applies) |
| LLM09 | Vector and Embedding Weaknesses | PARTIAL (no vector DB in the frozen BM25-only runtime; same ranking-robustness finding as LLM05 above) |
| LLM10 | Improper Output Handling | PASS (15/15 malformed-output cases handled safely) |

**Totals: 4 PASS, 6 PARTIAL, 0 FAIL** (both of the original 2 FAILs were remediated in E22: Unbounded
Consumption to PASS, Prompt Injection to PARTIAL, not rounded up to PASS since the pre-declared
detection bar wasn't met).

## Source for the 2026 category list

Category list, ordering, and the LLM08 naming (Hidden Context Exposure) verified via live web
search at the time this file was written:
- [OWASP LLM Top 10 2026: The Full List and What Changed](https://www.superblocks.com/blog/owasp-llm-top-10)
- [OWASP Releases GenAI LLM Top 10 2026](https://cybersecuritynews.com/owasp-genai-llm-top-10-2026/)
- [OWASP Top 10 for Large Language Model Applications (official project page)](https://owasp.github.io/www-project-top-10-for-large-language-model-applications/)
