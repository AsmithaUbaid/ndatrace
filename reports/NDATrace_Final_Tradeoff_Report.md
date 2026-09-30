# NDATrace — Final Trade-off Report

## Purpose and decision

NDATrace is an evidence-grounded aid for legal reviewers. Given an NDA and a confidentiality requirement, it returns Entailment, Contradiction, or Not Mentioned with source evidence for human verification. It does not approve agreements or make autonomous legal decisions.

The final roles are: **Rule = baseline; FULL = quality reference; RAG = prototype runtime; Agent = tested and rejected configuration; Human = final authority.** The retained runtime is clause-aware 256-token chunking with 50-token overlap, BM25 top-20, cross-encoder reranking, top-5 context, GPT-5-mini with P0, structured parsing, verbatim evidence validation, and human review.

## Evaluation and model choice

ContractNLI contains 607 NDAs and 10,319 requirement cases. Reconstruction decisions used frozen TRAIN samples; headline evaluation used the official TEST split of 123 documents and 2,091 cases. Gold labels and evidence were never supplied at inference time.

The local comparator changed from the proposal’s Llama 3.2 3B to Qwen 2.5 7B Instruct during reconstruction. The final model set reflects the evaluated reconstruction-v2 design rather than the initial proposal. An Oracle diagnostic, where models received gold evidence, showed GPT-5-mini at 0.906 Macro-F1 and 82% Contradiction Recall on its 300-case Oracle population. These are diagnostic results, not TEST metrics. They showed that reasoning quality remained a bottleneck even with perfect evidence.

Prompt tests retained the minimal P0 prompt. Clause-aware retrieval reached 92.2% Recall@5, 93.9% Contradiction Recall@5, and 0.376 MRR on 4,371 evidence-bearing TRAIN cases. BM25 and dense candidate generation were nearly identical after the same reranker; BM25 was retained for simplicity. The current runtime uses no vector index.

## Final TEST trade-off

| Configuration | Accuracy | Macro-F1 | Joint | Contradiction Recall |
| --- | ---: | ---: | ---: | ---: |
| Rule baseline | 59.0% | 0.479 | 50.1% | 16.8% |
| FULL quality reference | **77.6%** | **0.727** | **74.6%** | 75.5% |
| RAG prototype runtime | 76.8% | 0.723 | 72.5% | **77.3%** |

FULL achieved the higher measured Joint score. Paired classification accuracy was not significantly different (`p = 0.217`), while Joint was (`p = 0.0047`). RAG reduced mean input tokens by 50.4% and raw API inference cost by 16.8%, while returning ranked clause-level provenance. Selecting RAG is therefore an explicit operability trade-off, not a claim that it is superior in quality.

A deterministic majority-class TEST sanity check always predicts Entailment and reaches 46.3% accuracy, 0.211 Macro-F1, 0% Contradiction Recall, and 0% Joint. It is a trivial baseline, not an architecture rung.

## Did agency earn its complexity?

The matched comparison used the same 150-case TRAIN_ARCH_v1 agent-evaluation population throughout. The agent exposed only two read-only, same-document tools: `FOLLOW_CROSS_REFERENCE` and `GET_MORE_CANDIDATES`.

| Metric | Base RAG | Agent V1 | Agent V2 |
| --- | ---: | ---: | ---: |
| Accuracy | 78.7% | 78.0% | 74.0% |
| Joint | 75.3% | 73.3% | 68.7% |
| Contradiction Recall | 76% | 70% | 74% |
| Tool-use rate | — | 1.3% (2/150) | 20% (30/150) |
| Useful tool recoveries | — | 0/2 | 0/30 |
| Incremental cost/case | — | +$0.001515 | +$0.002659 |
| Incremental latency/case | — | +5.87s | +10.36s |

V2 deliberately encouraged investigation, increasing tool use from 1.3% to 20%, but measurable recovery remained zero and Joint declined. Agent investigation was evaluated through tool-mediated recovery and final task success, not a directly comparable static Recall@5 metric. **Tool use increased; value did not.** This rejects the tested two-tool retrieval-agent configuration on this population, not agents in general. No agent is present in the prototype runtime.

## Routing, economics, and security

E15 tested automatic review routing but did not adopt it: the policy meeting the residual-error target required a 51.4% review workload, above the 40% ceiling. Every result therefore remains subject to human review rather than relying on a confidence router.

Workflow economics use `C_total = C_AI + (1 − p_joint) × C_human`. API price alone is not total cost because Joint failures require human handling. All business figures are **modeled scenarios**, not realized production savings.

E21 established a ten-category security baseline: 3 PASS, 5 PARTIAL, and 2 FAIL. E22 targeted the two failures. Prompt Injection moved FAIL to PARTIAL; Unbounded Consumption moved FAIL to PASS. Current controls include an injection guard, input limits, request and cumulative budget guards, rate and concurrency limits, structured parsing, evidence validation, a human-review flag, and human final authority.

Residual risks remain: injection detection is incomplete; result endpoints lack authentication; retrieval poisoning remains possible; and semantically wrong but source-grounded answers can pass structural checks. This is not a claim of compliance or production readiness.

## Limitations and conclusion

ContractNLI is a proxy dataset; generalization to long, messy enterprise agreements is unestablished. Historical TEST exposure from earlier project iterations is disclosed, although reconstruction decisions did not tune on individual TEST outcomes. Semantic uncertainty cannot be reliably detected automatically, and no autonomous legal approval is permitted.

The final contribution is a measured architecture decision: deterministic retrieval and validation around a capable model, bounded evidence context, explicit security escalation, and human authority. More context, routing, and agency were tested; only components that earned their operational cost remain.

## Evidence trail

See `docs/experiment_registry.md`, `docs/evaluation_protocol.md`, `docs/architecture_decisions/INDEX.md`, `experiments/E20_final_rag_test/`, `experiments/E21_owasp_llm_top10/`, and `experiments/E22_targeted_security_remediation/`.
