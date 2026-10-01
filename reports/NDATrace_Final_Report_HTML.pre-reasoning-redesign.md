# NDATrace: Does Additional AI Complexity Earn Its Place?

*Ubaidulla Asmitha | PE6201 Emerging AI Technologies | Final analytical report | 1 October 2026*

<!-- report-body-start -->

## 1. Problem and business significance

Tina, an enterprise legal-operations analyst, reviews vendor NDAs against 17 confidentiality requirements before lawyer approval. Today that means keyword search over unindexed prose, with no standard evidence trail; a misread clause stays invisible until a dispute surfaces it. NDATrace classifies each requirement as Entailment, Contradiction or NotMentioned and returns its supporting clause, shifting the reviewer's task from re-reading whole documents to verifying specific, checkable claims — a change in the task, not yet a proven time saving. A correct label based on the wrong clause is not a defensible result, so the system assists Tina rather than approving, rejecting or negotiating on its own. A vendor survey of 286 legal professionals reported that 52% of organisations handle 101-1,000 contracts annually and most spend 2-4 hours per contract [1], motivating the workload; NDATrace has not measured productivity savings against it.

## 2. Proposed solution and architecture

I implemented a hybrid system because semantic interpretation and operational control require different mechanisms. Deterministic software performs clause-aware chunking, retrieval, reranking, schema parsing, evidence-source validation, injection flagging and resource limits; GPT-5-mini performs the bounded semantic classification (Figure 1). The reviewer receives the label, verbatim evidence and flags, then records the final decision. Renting the model avoided training and serving infrastructure; building the retrieval, evaluation and workflow layers preserved control over project-specific evidence semantics and reviewer authority. This division makes model outputs checkable without implying that a valid quotation guarantees a correct interpretation.

![Deployed NDATrace architecture](figures/submission_architecture.png)

*Figure 1. Frozen prototype path: 256-token chunks, BM25 top-20, cross-encoder top-5, GPT-5-mini, deterministic controls and mandatory human review.*

| Layer | Build / rent / use | Actual prototype decision |
| --- | --- | --- |
| Compute | Rent | OpenRouter-hosted inference; local Ollama retained for the measured comparator |
| Model | Rent | GPT-5-mini; avoid training and model-serving overhead |
| Data and retrieval | Use + build | Public ContractNLI; build per-document BM25/reranking pipeline using existing libraries/models |
| Orchestration | Build | One bounded classification path; no agent loop or automatic confidence gate |
| Evaluation | Build | Gold-aware offline harness separated from the gold-blind runtime validator |
| Serving | Build | FastAPI, Next.js evidence display, review history and recorded reviewer decisions |
| Governance | Build / incomplete | Guards, limits and human authority exist; enterprise identity and access controls do not |

## 3. Experimental methodology and progression

I assigned the official ContractNLI splits before comparison: TRAIN for component development, DEV for validation, and TEST for the final frozen evaluation. Gold labels and evidence were withheld from inference and used only for scoring. A prior superseded lineage had partially observed TEST, so I describe the final split as not tuned against in this re-derived sequence rather than perfectly blind. The final official population contains 2,091 requirement-document cases; the separate 49-case curated DEV battery concentrates known difficult mechanisms and is not a second benchmark. Each experiment changed one decision layer or supplied a diagnostic: Oracle evidence separated retrieval from reasoning, controlled prompts and retrieval sweeps froze simple components, and later comparisons tested whether RAG, an agent or automatic routing earned added complexity. The decisive FULL/RAG comparison held model, prompt, evaluator and case population constant and used paired significance tests. Two problems were caught before they could silently distort a headline metric: an exact-substring evidence evaluator initially miscounted valid paraphrased citations as failures, hardened before the TEST run; and a local inference server silently ignored a context-length setting, which calibration caught before it could make the full-context baseline look permanently weaker than it is. The eight rows below shaped the final architecture; the complete sequence is in the appendix table that follows.

| Experiment / research question | Key measured finding | Architectural decision or lesson |
| --- | --- | --- |
| Oracle: what remains difficult with gold evidence? | On 300 balanced TRAIN cases, GPT-5-mini reached 0.906 macro-F1 and 82% Contradiction recall; local Qwen reached 0.638 and 30% | Use the hosted model for final semantic quality; evidence access is not the only bottleneck |
| Model selection: local or hosted? | Hosted GPT-5-mini had the strongest reasoning ceiling; local Qwen remained a zero-API-cost comparator | Rent the stronger model; disclose provider dependency and measured cost |
| Prompt engineering: does more instruction help? | On 150 retrieved-context TRAIN cases, the minimal prompt led on macro-F1 (0.507 vs 0.448/0.403) and Contradiction recall (22% vs 6%/2%) | Freeze the minimal prompt |
| Retrieval optimisation: which evidence path? | On 4,371 TRAIN cases, BM25, dense and hybrid candidate generation converged near 92.2% Recall@5 after reranking; BM25 and dense differed on one case | Freeze simpler BM25 top-20 plus cross-encoder top-5 |
| FULL versus RAG: does bounded context preserve quality? | On matched TEST, RAG cut input tokens 50.4% and API cost 16.8%, but FULL led Joint correctness by 2.2 points | Keep FULL as quality reference; serve RAG as an explicit efficiency trade-off |
| Selective agent: do tools recover failures? | Fifteen escalations produced zero tool calls and 0.0-point net Joint gain, with $0.0218 added spend | Reject the tested agent from runtime |
| Confidence routing: can errors be isolated cheaply? | The strongest policy reviewed 51.4% of 138 DEV cases yet left 10.4% residual Joint error, missing both provisional targets | Keep every case subject to human review |
| Robustness and security: do controls withstand attacks? | Four of 11 injection-pattern pairs succeeded; later guards caught known attacks but only 4/11 patterns, while resource-limit tests passed | Quarantine detected patterns, retain human review and disclose residual injection risk |

| Full experiment sequence (appendix) | Question it answered | Outcome |
| --- | --- | --- |
| Dataset and split validation | Are the official splits usable as-is? | Confirmed; no rebuild needed |
| Budget and runtime forecast | Can the planned run sequence stay inside budget? | Forecast built and approved before any paid call |
| Majority-class baseline | What does a trivial always-Entailment guess score? | 46.3% accuracy, 0% Joint; a floor, not an architecture rung |
| Oracle reasoning ceiling | With gold evidence handed to the model, what is still hard? | Contradiction reasoning is the bottleneck even with perfect evidence |
| Model screening | Is a separate model bake-off needed? | No; the Oracle run already answered it |
| Prompt selection | Does more explicit instruction help? | No; the minimal prompt wins on every priority metric |
| Rule baseline | What can a $0 keyword baseline reach? | 48.2% joint; sets the non-AI floor |
| Full-context baseline (local model) | What does a local model do with the whole document? | 28.0% joint; a context-window truncation bug was found and fixed first |
| Retrieval optimisation | Which retrieval setup is both accurate and simple? | BM25 top-20 plus reranking; dense embeddings add nothing once reranking exists |
| Standard RAG (local model) | Does bounded retrieval beat full context on a local model? | Directionally yes on every metric, not significant at this sample size |
| RAG failure analysis | What is actually wrong when RAG fails? | Mostly reasoning limits, not retrieval; a narrow agent opportunity looks plausible but unconfirmed |
| Stronger hosted model diagnostic | Does a stronger model close the gap alone? | Yes, sharply (joint 33%->74%), with zero retrieval or agent change |
| Agent justification after stronger model | Does the agent opportunity survive a stronger model? | Mostly no; only 1 of 39 residual failures passes a strict dynamic-information test |
| Bounded selective-agent design | What is the cheapest real test of that one-case opportunity? | A 2-tool, hard-capped agent frozen before any run (a drafted third tool was dropped before implementation) |
| Selective-agent empirical evaluation | Does the frozen agent recover any value in practice? | No; net Joint change is zero (see the agent table below) |
| Static context expansion | Would a larger fixed context window help instead of an agent? | Small, inconclusive gain at real added cost; not adopted |
| GPT-specific prompt tuning | Does a GPT-tuned prompt beat the frozen minimal one? | Near-tie, one case short of the adoption threshold |
| Confirmation re-test of that near-tie | Does the near-tie replicate on a fresh sample? | No; direction reverses. Minimal prompt kept |
| Full-context vs RAG (GPT, DEV sample) | Which architecture is stronger on a held-out sample? | FULL wins on the predeclared rule; first signal of a real quality cost to bounded context |
| Evidence evaluator hardening | Is the evidence-matching logic itself trustworthy? | A mapping bug was found and fixed before the TEST run, not after |
| Runtime validator alignment | Does the live validator match the hardened evaluator? | Aligned; no live code path was affected |
| Human review routing | Can cheap signals safely cut the review workload? | No; the best policy still missed both the workload and error targets |
| Robustness and security validation | Do the guardrails survive adversarial input? | Partially; 4 of 11 attack patterns still succeed, disclosed rather than hidden |
| Final TEST evaluation (sample) | Does a 150-case sample match the eventual full result? | Yes, within noise; superseded by the full run below |
| Full TEST completion | What is the final, full-population result? | Headline number for this report: 77.6% accuracy, 74.6% joint on all 2,091 cases |
| Business and cost synthesis | What does this mean for cost and the course deliverable? | Offline synthesis only; no new model calls |
| Final product integration | Does the product run the frozen architecture end to end? | Yes; frontend and backend wired to the final pipeline |
| Final RAG vs FULL comparator (TEST) | How does RAG compare to FULL on the identical final population? | FULL's Joint edge is statistically significant; RAG is a disclosed efficiency trade-off |
| OWASP LLM Top 10 assessment | Where does the system stand against the standard security checklist? | 4 pass, 6 partial, 0 fail after remediation; real gaps disclosed, not claimed solved |
| Targeted security remediation | Can the two failing categories be fixed? | Partially; one closes fully, one improves honestly short of its own bar |
| Injection guard live-fire check | Does the shipped guard actually fire on a real adversarial call? | Yes, on this one scenario; not a new coverage claim |
| Targeted evaluation (curated battery) | How does the current architecture do on the hardest hand-picked cases? | Lower in absolute terms by design, same FULL-ahead pattern as TEST; surfaces a persistent exception-handling weakness |

### Why the tested agent was rejected

| Stage | Question | Finding |
| --- | --- | --- |
| Initial failure diagnostic | Could a narrow agent plausibly recover RAG's failures? | 41% of errors looked agent-fixable by a runtime cue, but 49% were plain reasoning failures with no agent fix |
| Reassessment after a stronger model | Does that opportunity survive switching to the stronger hosted model? | Almost entirely no: of 39 residual failures, only 1 (2.6%) passed a strict, pre-declared dynamic-information-acquisition test |
| Bounded design freeze | What is the cheapest real test of that single-case opportunity? | A 2-tool agent (a third, `get_definition`, was drafted then dropped before implementation), hard capped at 3 steps and $0.01/case, triggered only by the one validated cue |
| Empirical test of the frozen design | Does the built agent recover value in practice? | 15 of 150 cases were routed to it; it never invoked its own tools, including on the case it was built for. One recovery, one regression, net zero, for $0.0218 spent |

This table is the project's standard for adopting complexity in practice: freeze a bounded design before seeing outcomes, then adopt only if it clears a predeclared bar. It did not say agents cannot help NDA review in general, only that this narrowly-triggered design did not, on the one opportunity the diagnostics could find; the static alternative, a larger fixed context window, was tested separately and also not adopted.

## 4. Quality evaluation and architecture trade-offs

Classification accuracy asks only whether the label is right. Joint correctness additionally requires sufficient gold-evidence overlap, so it exposes answers that sound right but cannot be substantiated. On official TEST, FULL achieved 77.6% accuracy and 74.6% Joint correctness; RAG achieved 76.8% and 72.5%. Their accuracy difference was not significant (paired McNemar p=0.217), while FULL's Joint advantage was significant (p=0.0047). The wider label-to-Joint drop for RAG shows why accuracy alone obscures evidence coverage and selection weaknesses. FULL therefore remains the strongest evidence-grounded quality reference, although neither architecture reaches a level that supports unsupervised legal decisions. Joint correctness is itself a project choice, not a law: its 50% gold-span-overlap threshold is predeclared but arbitrary, and a different threshold could shift both architectures' absolute numbers without necessarily changing the ranking — an untested sensitivity, flagged as a real gap.

The original Problem Statement (Section 7) specifies the success criterion as a minimum five-percentage-point improvement in risk-sensitive recall over FULL-context LLM processing. Measured against FULL, the gain is only +1.2 points (Table 2), so the originally proposed target was not achieved; measured against the rule-based, non-AI baseline named separately in the Problem Statement, RAG shows a +16.6-point gain over a cheap deterministic floor — both reported rather than one chosen to look favorable. RAG was nevertheless retained as the bounded-context prototype: it halves input context, lowers measured inference cost, and its narrower retrieved context avoided a distractor clause that FULL did not (case 038, Section 5) — efficiency and individual-case benefits, not evidence that RAG met the original target or is the stronger architecture overall. The curated results point the same direction on Joint correctness but are too small for a significance claim.

| Metric | Rule | FULL | RAG |
| --- | ---: | ---: | ---: |
| **Official TEST benchmark - 2,091 cases** |  |  |  |
| Accuracy | 59.0% | 77.6% | 76.8% |
| Macro-F1 | 0.479 | 0.727 | 0.723 |
| Joint correctness | 50.1% | 74.6% | 72.5% |
| Contradiction recall | 16.8% | 75.5% | 77.3% |
| NotMentioned recall | 90.5% | 62.7% | 63.2% |
| Risk-sensitive recall (C/NM mean) | 53.6% | 69.1% | 70.3% |
| **Curated development evaluation - 49 cases** |  |  |  |
| Accuracy | 51.0% | 73.5% | 71.4% |
| Macro-F1 | 0.457 | 0.720 | 0.708 |
| Joint correctness | 44.9% | 73.5% | 67.3% |
| Contradiction recall | 13.3% | 46.7% | 53.3% |
| Golden / ordinary (n=30): accuracy / Joint | 60.0% / 56.7% | 80.0% / 80.0% | 76.7% / 73.3% |
| Difficult / negative (n=15): accuracy / Joint | 46.7% / 33.3% | 53.3% / 53.3% | 53.3% / 46.7% |

![Accuracy and Joint correctness](figures/submission_quality.png)

*Figure 2. Official TEST comparison. Accuracy alone obscures evidence-selection failures; the curated DEV scores are deliberately excluded from this population-level chart.*

## 5. Failure analysis and robustness

Aggregate performance does not explain mechanism. On official TEST, 448 of RAG's 576 non-Joint cases were reasoning or classification failures despite retrievable gold evidence; 59 were evidence-selection failures, 55 retrieval-limited and 14 parser/source-validity failures. The curated diagnosis complements those population counts without estimating frequencies. In cases 007 and 043, RAG omitted some gold spans from retrieval and failed to cite some that were present. Cases 034, 039 and 040 show that both architectures still misread documented exception clauses. In case 038, FULL over-weighted a permissive distractor that RAG did not retrieve. Case 001 raises a substantive annotation concern. More context or retrieval depth alone is therefore not a general remedy.

| Verified mechanism | Case-level observation | Engineering implication |
| --- | --- | --- |
| Partial retrieval plus incomplete evidence selection | Cases 007 and 043: some gold spans absent from top-five context and some retrieved spans left uncited | Measure retrieval coverage and multi-span citation separately |
| Exception / carve-out interpretation | Cases 034, 039 and 040 failed under both FULL and RAG | Build an independent exception-reasoning evaluation before changing prompts |
| Distractor-clause interference | Case 038: FULL followed a permissive clause; narrower RAG context supported the correct contradiction | Selective context can help in individual cases, not establish population superiority |
| Annotation ambiguity | Case 001's annotated evidence is substantively debatable | Audit benchmark ground truth alongside model errors |

![RAG failure distribution](figures/submission_failures.png)

*Figure 3. Canonical official TEST taxonomy; denominator is exactly 576 non-Joint RAG cases. Targeted case mechanisms are not mixed into these counts.*

In the small robustness study, Joint correctness fell from 85% on clean inputs to 75% under attack, and source-validity checks did not stop injected text from becoming valid quoted evidence. Length caps, spend ceilings, rate limits and a pattern guard now constrain resource use and quarantine detected instructions, but detection covered only 4 of 11 known patterns — detection, model resistance and human review remain distinct, incomplete safeguards.

## 6. Cost-to-serve and business trade-offs

RAG's mean output tokens barely changed, approximately 727 to 701 (Table 4); the input-token and cost savings below come from context, not generation. Because FULL retains higher Joint correctness, selecting the cheaper inference path could increase potential review work; model price alone cannot establish lower operating cost.

| Measure | FULL | RAG |
| --- | ---: | ---: |
| Mean input tokens per case | 2,279 | 1,131 |
| Mean output tokens per case | 727 | 701 |
| Measured API inference cost per case | $0.00202 | $0.00168 |
| Mean latency | 7.31 s | 7.14 s |
| Official TEST Joint correctness | 74.6% | 72.5% |

![Quality-cost frontier](figures/submission_frontier.png)

*Figure 4. Measured API inference economics on the same 2,091 TEST cases. Rule, RAG and FULL are comparable; local compute cost is not monetised.*

| Cost-model input | Value used | Evidence status |
| --- | ---: | --- |
| Common volume | 1,000 requirement reviews | Scenario input |
| Base verification | 5 minutes per case | Assumption; applied to every architecture |
| Reviewer rate | $40 per hour | Assumption reused from saved business scenario |
| Derived verification cost | $3.33 per case | 5/60 x $40 |
| FULL / RAG API cost | $0.00202 / $0.00168 per case | Measured on official TEST |
| Rule API cost | $0; local compute not monetised | Measured API spend only |
| Incremental rework | Omitted | No defensible non-overlapping estimate |
| Fixed operating cost | Omitted | Not measured; must be added for deployment planning |

At this scale the $3.33 verification cost per case (no case skips review) dwarfs the sub-cent
API difference between architectures (Rule $3,333.33, FULL $3,335.36, RAG $3,335.02 at 1,000
cases); a bar chart of these totals was omitted as visually indistinguishable and misleading.
The table above states the same numbers.

![Cost-to-serve sensitivity](figures/submission_cost_sensitivity.png)

*Figure 5. Hypothetical RAG operating scenarios across review time/rate, volume and assumed successful-review rate. AI cost is measured; every other operating input is an explicit assumption.*

The sensitivity model shows how review time, hourly cost, volume and the assumed share of cases avoiding fallback can dominate sub-cent inference. Joint correctness is shown only as a possible quality proxy, not a validated automation rate. The deployed prototype requires human verification for every case, so its current operating model adds measured inference cost to the existing review process rather than automatically avoiding review. If workload does not fall, potential labour savings disappear; if it falls only slightly, quality-related rework can outweigh the small RAG price advantage. No workplace study, realised saving or ROI is claimed.

## 7. Governance, limitations and prioritised improvements

NDATrace remains a reviewer-assistance prototype because its largest failure class is incorrect interpretation, not merely missing retrieval. It also has incomplete multi-span evidence, benchmark ambiguity, partial injection detection and no validation on confidential enterprise NDAs. Neither the tested agent nor confidence routing (Section 3) earned control over reviewer access, so every result remains subject to human verification. I would prioritise exception and polarity reasoning first, since it is the dominant failure family, then multi-span citation, then retrieval depth. Security and access controls are deployment prerequisites, not accuracy enhancements. The improvements below are proposals tied to observed mechanisms, not demonstrated benefits. ContractNLI is public, uses fixed requirements and ordinary-length NDAs, so its scores cannot establish performance on an organisation's templates, risk tolerance, jurisdictions or long confidential agreements.

| Observed risk | Implemented safeguard | Next proposed improvement |
| --- | --- | --- |
| Scattered or missing evidence | BM25 top-20, reranking and visible sources | Test coverage on longer documents and cross-references |
| Incomplete evidence selection | Joint metric, verbatim validation and human verification | Evaluate multi-span citation recall independently |
| Contractual exceptions | Mandatory human review | Build a larger independent exception/polarity set |
| Prompt injection | Pattern guard, quarantine flag and resource limits | Broaden novel attack coverage; separate detection from resistance testing |
| Incorrect automatic escalation | No confidence gate; every case remains reviewable | Validate stronger signals before selective automation |
| Sensitive enterprise documents | Prototype restricted to public data | Add authentication, access control, confidentiality and provider assessment |

## 8. Conclusion

Additional AI complexity did not consistently deliver additional value. Hosted semantic classification substantially improved on keyword rules. Retrieval halved input context and reduced measured inference cost, but FULL retained stronger overall Joint correctness. The tested selective agent added no net evidence-grounded benefit, and confidence routing did not justify selective autonomous processing. The evidence therefore supports bounded reviewer assistance, not autonomous review. NDATrace remains a prototype with explicit human authority and known interpretation, evidence and security limitations; human verification is necessary.

<!-- report-body-end -->

## References

[1] LegalOn Technologies and In-House Connect. "2025 State of Contracting Survey," 15 January 2025. Vendor research; LegalOn sells contract-review software. https://www.legalontech.com/press-releases/2025-survey.

[2] Yuta Koreeda and Christopher D. Manning. "ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts." Findings of EMNLP 2021, pp. 1907-1919. https://aclanthology.org/2021.findings-emnlp.164/.

## Report evidence map

| Report item | Canonical source | Population / status |
| --- | --- | --- |
| Architecture and Figure 1 | `pipeline/frozen_rag.py`; `pipeline/final_review.py`; `docs/architecture.md` | Current interactive runtime, source-verified |
| Table 1 and appendix experiment table - experimental progression | All 31 experiment summaries; `docs/experiment_registry.md` | Mixed diagnostic populations, identified in each row |
| Agent investigation table | `experiments/E08_rag_failure_analysis/summary.md`; `experiments/E09_agent_justification/summary.md`; `experiments/E10_agent_design/summary.md`; `experiments/E11_selective_agent_evaluation/summary.md` | Matched 150-case TRAIN_ARCH_v1 population for the empirical stage |
| Table 2 and Figure 2 - quality | `experiments/E20_final_rag_test/results/E20_final_report.json`; `results/final/v2/full_test_comparison.csv`; `experiments/E24_targeted_evaluation/results/e24_analysis.json` | Official TEST n=2,091 kept separate from curated DEV n=49 |
| Table 3 and Figure 3 - failures | `experiments/E20_final_rag_test/results/E20_final_report.json`; `experiments/E24_targeted_evaluation/summary.md` | TEST taxonomy n=576 failures; small case-level DEV diagnosis |
| Table 4 and Figure 4 - measured economics | Official TEST artifacts above; FULL output tokens recomputed from the two saved hosted prediction files | Matched TEST n=2,091; measured inference only |
| Table 5 - current cost model | Official TEST costs; `results/business_economics_scenario.json`; explicit inputs stated in the table | Current workflow; 1,000-case scenario; human verification applied to all systems; no chart (see Section 6) |
| Figure 5 - sensitivity | `experiments/E18_business_course_synthesis/summary.md`; `results/business_economics_scenario.json` | Hypothetical selective-review scenarios; not deployed behaviour |
| Table 6 - governance | `docs/failure_analysis.md`; routing, robustness and security summaries; `docs/production_backlog.md` | Safeguards measured where stated; improvements are proposals |

## Quality-control summary

The final HTML is generated from this editable source. Offline verification recomputes official and targeted metrics from saved artifacts, checks population labels, tokens, costs, failures, cost-model arithmetic and local links, validates five figure files, checks that internal experiment identifiers do not appear in the main narrative, and confirms the declared word count. The targeted notebook contains eight executed code cells and saved outputs. No paid inference or frozen-result modification was performed for this report.

## Remaining methodological and submission limitations

- The official TEST split was not tuned against in the final re-derived sequence, but a superseded earlier lineage had partially observed it; the report does not call it perfectly blind.
- The curated 49-case DEV battery was designed to be difficult and cannot establish statistical significance or population failure rates.
- The economic model is hypothetical because review-time reduction, enterprise operating cost and safe automation rate were not measured.
- Long confidential enterprise contracts, authentication, distributed controls and novel adversarial attacks remain unvalidated.
- The HTML links to local figure files in `reports/figures/`; keep that folder beside the report when moving it.
