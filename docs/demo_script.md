# NDATrace demo script

Target: 5-8 minutes. No slides — the `/project` web UI is the presentation surface throughout.
Seed cases referenced below live in `frontend/data/demo_cases.json`; each one points at a real
saved case, not a synthetic happy path.

| # | Section | What to show | What to say (1-2 sentences) | ~sec |
|---|---|---|---|---|
| 1 | Problem + persona | `/project` Overview, opening section | "An enterprise legal analyst reviews an NDA against 17 standard confidentiality requirements by hand. NDATrace automates the check and shows the exact clause behind every answer." | 25 |
| 2 | Joint / L1 / L2 | Overview, headline Joint metric card | "We score two things: is the label right, and is the evidence right. Joint requires both — a right label with fabricated evidence doesn't count as a success." | 25 |
| 3 | Oracle / model choice | Overview, Oracle Macro-F1 table (E01) | "Before touching retrieval, we fed the model gold evidence directly to isolate reasoning quality. GPT-5-mini scored the strongest ceiling, 0.906 Macro-F1 — that's a diagnostic number, not a TEST accuracy." | 30 |
| 4 | Prompt selection | Overview, prompt comparison chart (E12) | "We compared prompt variants on a controlled sample; more instruction actually weakened Contradiction handling, so we froze the simplest one, P0." | 25 |
| 5 | Retrieval tuning | Overview, retrieval design chain (E06) | "Chunking, BM25 top-20, and a cross-encoder reranker down to top-5 were each tested and justified with real recall/precision numbers, not assumed." | 25 |
| 6 | FULL vs RAG trade-off | Overview, headline FULL-vs-RAG comparison table | "On the full TEST set, FULL is the stronger quality reference — its Joint advantage is statistically significant, p=0.0047. RAG is close on accuracy and much cheaper in context, so it ships as the prototype runtime." | 35 |
| 7 | Real successful RAG case | Case Explorer, seed case `test::2::nda-19` | "Here's a real case where RAG matches the gold label and returns evidence that's both source-verified and semantically correct." | 25 |
| 8 | Real L1-pass/L2-fail case | Case Explorer, seed case `test::1::nda-3` (reasoning failure) or the silent-failure card on Overview | "This is the important one: the output is structurally valid — a real quote from the document — but the label is semantically wrong. That's a silent failure, and it's why a human still checks every answer." | 35 |
| 9 | Residual failure breakdown | Overview, failure taxonomy chart | "Most residual errors aren't retrieval misses — the right clause was often available. That shifted our next investment from retrieval to reasoning." | 25 |
| 10 | Agent experiment + saved trace | Overview → Case Explorer agent tab, seed case `train::160::nda-10` | "Here I compare the same 150 cases under base RAG, Agent V1, and Agent V2. Joint moved 75.3 → 73.3 → 68.7; tool use rose 1.3% → 20%, but useful recoveries stayed 0 → 0. Added latency rose +5.87s → +10.36s and cost +$0.001515 → +$0.002659 per case. Tool use increased, but measurable value did not. I therefore rejected the tested agent configuration." | 45 |
| 11 | Security E21 → E22 | Overview, Security section | "We ran all 10 OWASP LLM Top 10 categories (E21): 3 pass, 5 partial, 2 fail. We then targeted the two most actionable failures — unbounded consumption is now PASS under targeted verification, prompt injection improved to PARTIAL. We do not claim OWASP compliance." | 35 |
| 12 | Cost-to-serve | Overview, cost curve chart (E18) | "This is a modeled scenario, not realized savings: C_total = C_AI + (1 − p_joint) × C_human. RAG is cheaper per call, but FULL's higher Joint rate can make it cheaper all-in once human fallback is priced in." | 30 |
| 13 | Live prototype runtime | The actual `/review` product flow (backend + frontend) | "This is the live interactive prototype: submit an NDA and a requirement, get a label, cited evidence, and — if something looks structurally wrong — a mandatory human-review flag." | 30 |
| 14 | Final architecture + limitations | Overview, final architecture diagram + Limitations section | "Rule is the baseline, FULL is the quality reference, RAG is the prototype runtime, the agent is a rejected tested configuration, and the human reviewer is always the final authority. Limitations are disclosed, not hidden: ContractNLI scope, no proven generalization to messy real NDAs, no reliable automatic semantic-uncertainty routing, residual injection risk." | 35 |

Total: ~6 minutes of talk time at the pacing above, leaving 2-3 minutes for live interaction or
questions.
