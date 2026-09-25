# NDATrace — Project Contract

Status: **PROPOSED, not yet approved.** This document freezes the project's definition
before any reconstruction work. It supersedes ad hoc framing in `CLAUDE.md`/planning-doc
prose where the two conflict — see Contradictions section at the end.

## 1. Problem Definition

Enterprise legal teams review NDAs against a fixed checklist of confidentiality
requirements. Given one NDA and one requirement, a reviewer must decide whether the NDA
satisfies it, conflicts with it, or never addresses it — and must be able to point to the
exact clause that justifies the call. This is slow, repetitive, and evidence-heavy: exactly
the shape of task an LLM pipeline can accelerate, provided it never hides its reasoning
behind an unverifiable answer.

## 2. Intended User

A human legal reviewer (or paralegal) performing first-pass NDA triage, who remains
accountable for the final decision. NDATrace is their aid, not their replacement.

## 3. Input

- One NDA / confidentiality agreement (document text).
- One predefined confidentiality requirement, drawn from a fixed set (ContractNLI's 17
  hypotheses in this project).

## 4. Output

1. A classification: **Entailment / Contradiction / Not Mentioned**.
2. The NDA clause(s) — verbatim evidence — supporting that classification.
3. An abstention / human-review flag when evidence is insufficient or the system cannot
   make a defensible call.

## 5. Product Promise

> For each NDA requirement, NDATrace produces a reviewable classification that is tied to
> traceable NDA evidence, or explicitly abstains.

**Not** a legal-advice system, autonomous approver, redlining engine, negotiation agent,
contract-signing system, multi-agent legal platform, or generic document chatbot.

## 6. Central Research Question

> Does each additional architectural layer improve evidence-grounded NDA review enough to
> justify its additional cost, latency, complexity, and failure surface?

The project evaluates progressively more capable architectures rather than assuming the
most complex one wins.

## 7. Four Architectures (fixed, no others)

- **A0 — Rule-Based / Keyword Baseline.**
- **A1 — Full-Context LLM.** Entire NDA + requirement given directly to the model.
- **A2 — Standard RAG.** Retrieve relevant passages, then classify.
- **A3 — Selective Agentic RAG Investigation.** A2 handles ordinary cases; only cases the
  system flags as low-confidence, conflicting, or incomplete may enter a bounded, read-only
  iterative retrieval loop.

Oracle experiments, prompt versions, embedding/chunking/reranker choices, confidence
thresholds, security tests, and performance tests are **experiments or component choices**,
not separate headline architectures, and must not be reported as if they were.

## 8. Architecture Escalation Principle

"Cheapest sufficient rung" — every layer must earn itself empirically. At each transition,
ask: *what failure in the previous rung justifies adding this capability?* Valid project
conclusions include: rules are insufficient; full-context is good enough that RAG adds
little; RAG materially improves grounding; agentic investigation helps only a narrow
subset; agentic investigation's gain doesn't justify its cost and should be dropped. The
final architecture is selected from evidence, not assumed in advance.

## 9. Definition of Success (provisional, per-case)

A case is successful only if **all** hold:
- the classification is correct;
- required supporting evidence is correctly identified;
- the returned evidence actually supports the classification (not fabricated or
  paraphrased past what the source says);
- the output satisfies the required schema;
- the system abstains rather than inventing unsupported facts where abstention is the
  correct behavior.

A correct label without correct supporting evidence is **not** a full success. The project
tracks these as separate, named axes, not folded into one number:
- (A) Classification correctness
- (B) Evidence retrieval correctness
- (C) Joint label + evidence correctness — headline metric
- (D) Explanation / faithfulness quality

Exact scoring logic is frozen later, in the Dataset & Evaluation Protocol phase — this
section fixes the *shape* of success, not the formulas.

## 10. Human Review Contract

- **WINDOW:** the reviewer intervenes after NDATrace returns a classification for a
  requirement — before that determination is treated as final for the NDA under review.
  Every REVIEW-routed or abstained case is surfaced for mandatory review; ACCEPT-routed
  cases are available for spot-check but not blocking.
- **EVIDENCE:** the reviewer sees the classification, the confidence/routing signal, the
  cited clause(s) verbatim, and — for agent-investigated cases — the investigation trail
  (which tools were called and what they found).
- **AUTHORITY:** the reviewer can override the label, reject the evidence as insufficient,
  or approve the determination. The reviewer is the final authority; NDATrace never
  auto-finalizes a requirement determination.

## 11. Risk Priorities

- **Contradiction Recall is tracked and reported separately and prominently** — never
  averaged into a combined "risk" metric that can hide it. Contradiction is the minority
  class and represents direct conflict with a requirement; missing one is the costliest
  failure mode.
- **Not Mentioned is also tracked separately**, not merged into Contradiction's number.

## 12. Role and Limitations of the Agentic Component (A3)

- Selective escalation only — never the default path for all cases.
- Triggers: evidence spread across clauses, definitions located elsewhere, an apparent
  exception/carve-out modifying a relevant clause, cross-references to follow, conflicting
  retrieved clauses, or otherwise insufficient evidence for a defensible call.
- **Strictly read-only.** May search and retrieve more evidence. Must never send
  communications, modify contracts, write to production legal systems, approve agreements,
  negotiate terms, or take any irreversible action. This keeps NDATrace on the read-only
  side of the governance cliff.

## 13. Research vs. Production Boundary

- **Research question:** which architecture gives the best evidence-grounded review
  trade-off?
- **Product question:** how should the selected architecture later be exposed through a
  production-style application (API, UI, persistence)?
- Frontend, API, deployment, observability, and UI decisions must not influence the
  architecture experiment. Architecture selection is frozen before those concerns are
  built out or allowed to feed back into it.

## 14. Budget Constraint

Hosted-model spend is a hard experimental constraint, not an afterthought:
- local-first experimentation;
- no unnecessary hosted API calls;
- no repeated full-dataset hosted runs;
- short, structured outputs during experiments;
- estimate spend before every hosted experiment and record it.

Oracle-stage model screening compares **2 local models + 2 hosted models** under identical
Oracle conditions. Exact models are not selected in this document — that belongs to a later
experiment phase. (See Contradictions — this repo's actual Oracle run and remaining-balance
figure differ from the values given for this phase and need reconciling, not silently
overwritten.)

## 15. Explicit Non-Goals

Kubernetes, multi-region deployment, enterprise SSO/RBAC/multi-tenancy, CI/CD pipelines,
managed vector DBs, Celery/Redis-style workers, microservices, model training/fine-tuning,
SOC 2 compliance, automatic NDA approval, non-NDA contract types, real confidential NDA
processing, legal-advice output, full production observability stacks, Postgres/pgvector
migration, formal AI-governance frameworks, multi-agent systems, orchestration frameworks
added for sophistication rather than need, knowledge graphs without an observed need,
autonomous contract actions, unneeded vector DBs/rerankers beyond what's measured to help,
multiple frontends, real legal-system integrations, complex account management, production
deployment before architecture selection. Any later addition must be justified by an
observed failure or explicit product requirement, not adopted speculatively.

## 16. Open Questions for Later Phases

- Exact scoring formulas/thresholds for the four success axes (§9) — Dataset & Evaluation
  Protocol phase.
- Which 2 local + 2 hosted models fill the Oracle screening slots (§14), and how that
  reconciles with the 2 hosted models (GPT-5-mini, Gemini 2.5 Flash Lite) and later
  Ollama/Groq substitutions already present in this repo.
- Confirmed current hosted-model remaining balance (§14/Contradictions) before any further
  hosted spend is authorized.
- How re-classifying the existing repo's already-completed work against this contract's A0
  –A3 framing should be handled: re-labeled in place, or re-run for genuine freshness.

---

## Summary

### What was frozen by this document
- The central research question, exactly as specified.
- The four-architecture ladder (A0–A3) as the only headline architectures, with
  everything else demoted to "experiment/component choice."
- The product promise and explicit non-goal list.
- The four-axis definition of success (label / evidence / joint / explanation), with joint
  label+evidence correctness as the headline metric and label accuracy alone ruled
  insufficient.
- Contradiction Recall and Not Mentioned as separately-reported metrics, never merged into
  one combined risk number.
- The agent's role as strictly read-only, selective escalation, never the default path.
- The human-review contract's three axes: window, evidence, authority.
- The research/production boundary: frontend/API/UI must not influence architecture
  selection.
- The full non-goals list.

### What is deliberately NOT frozen yet
- Exact metric formulas, thresholds, and scoring logic for the four success axes.
- Which specific models fill the "2 local + 2 hosted" Oracle screening slots.
- Dataset splits, evaluation protocol mechanics, retrieval configuration, prompt versions.
- Any code, file moves, or repository reconstruction — this document is contract-only.

### Contradictions found between the current repository and this contract

This repository is **not** at the pre-reconstruction stage the source instructions assume
— it is already far past it. Flagging these plainly rather than silently reconciling them:

1. **Project maturity mismatch.** The instructions frame this as defining a contract
   "before any reconstruction work begins," with repository reconstruction as a not-yet-
   started Part 2. In reality, per `CLAUDE.md`, the project has already: built the full
   pipeline, run Oracle (B04), selected a model (Gemini 2.5 Flash Lite) via an ADR, run all
   nine rounds of retrieval experiments, frozen the architecture (RAG + selective agent,
   T031, 2026-09-23), built backend + frontend, run performance/reliability tests, and run
   the final locked test-set evaluation (T041) twice — including finding and fixing a
   critical joint-metric bug in that evaluation on 2026-09-24. Treating this document as
   "before reconstruction" would misrepresent where the project actually stands.

2. **Architecture count/framing is actually consistent, once relabeled.** The existing
   decisions log already runs a four-rung ladder — Rule / Full-context / RAG / RAG+agent —
   functionally identical to A0–A3 here. No real conflict, just no A0–A3 naming applied
   retroactively yet. Low-risk to adopt this document's naming going forward.

3. **Oracle model-screening design doesn't match what was actually run.** This contract's
   §14 specifies "2 local + 2 hosted" under identical Oracle conditions. The repo's actual
   Oracle experiment (B04) compared exactly 2 **hosted** models (GPT-5 mini, Gemini) — no
   local model was in the Oracle screening. Local model support (`ModelGateway.local()`,
   Ollama Llama 3.2 3B, later Groq) was added afterward, in response to separate instructor
   feedback (Week 3), as a hosted-vs-local comparison arm on the already-frozen
   architecture — not as part of an Oracle-stage 2-local+2-hosted screen. If this
   document's Oracle design is adopted, it implies redoing Oracle-stage screening with 2
   local models included, which was never done.

4. **Budget figure differs from the repo's own recorded state.** This document's source
   material states "~US$5" remaining. `ndatrace/.env`'s `MAX_BUDGET_USD` (last verified
   2026-09-22) is $6.99, and the decisions log records real spend since then (T041 alone:
   $0.685 for the full 2,091-case hosted full-context run, plus RAG/agent runs, plus
   multiple smaller experiments). Neither figure is necessarily the current true balance —
   $6.99 is stale (pre-T041 spend) and "~$5" is unsourced in this repo. **The real
   remaining OpenRouter balance should be re-verified before any further hosted spend is
   authorized under this contract**, not assumed from either number.

5. **"No model calls / no dataset changes" during this phase is honored.** No pipeline
   code, dataset, or experiment files were touched producing this document — only this new
   `docs/project_contract.md` was written, consistent with the stop condition.

No files were moved, renamed, or altered; no code was run; no dataset was changed. Waiting
for approval before any reconstruction work.
