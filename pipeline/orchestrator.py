"""
Orchestrator (WBS T032 support) - single reusable entry point for the
frozen production architecture (T031: RAG + selective agent): retrieve
-> rerank -> rule-boost -> classify -> confidence-route -> selective
agent.

This mirrors the per-case logic in scripts/run_final_test_evaluation.py's
run_rag_agent(), extracted into pipeline/ so the backend (and any future
notebook or script) calls one real implementation instead of
re-implementing the routing decision (Section 0A: notebooks/scripts
import from pipeline/, never duplicate its logic).
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.agent import run_agent
from pipeline.classifier import classify
from pipeline.confidence import Route, route
from pipeline.logging_config import get_logger
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_by_keywords

logger = get_logger("orchestrator")


@dataclass
class ReviewResult:
    hypothesis_id: str
    hypothesis_text: str
    label: str
    confidence: float
    explanation: str
    evidence: list[str]
    agent_used: bool
    agent_steps: int
    cost_usd: float
    latency_ms: float
    tokens_in: int
    tokens_out: int
    error: str | None = None


def review_requirement(
    doc_text: str,
    hypothesis_id: str,
    hypothesis_text: str,
    gateway: ModelGateway,
    retriever: Retriever | None = None,
    doc_id: str = "",
) -> ReviewResult:
    """
    Run the frozen production pipeline on one (document, hypothesis)
    pair. Pass a shared `retriever` when reviewing the same document
    against multiple hypotheses, so its embeddings are built once.

    Routing independence fix (code-audit finding C-1, 2026-09-24): the
    rule-based keyword match is used TWICE in this design - once to boost
    a matched chunk into the retrieval context (Retriever.
    query_rerank_and_boost, T023 round 7), and once again to decide
    whether to escalate to the agent (pipeline/confidence.py's route(),
    "does the rule agree with RAG?"). Comparing the rule against a
    prediction that may have already seen the rule's own picked chunk is
    circular - "agreement" partly measures whether the LLM noticed the
    chunk we handed it, not independent corroboration.

    Fix: classify a SEPARATE, plain dense+rerank-only context (no rule
    fusion - Retriever.query_and_rerank(), already built as the
    no-rule-boost path) purely to compute the routing signal. The
    rule-boosted classification (rag_result, better evidence quality per
    T023 round 7) is still what's returned as the final answer whenever
    the case is accepted - only the AGREEMENT CHECK is decoupled from the
    rule's influence on retrieval, not the production answer itself.
    """
    if retriever is None:
        retriever = Retriever(doc_text, chunk_method="sentence")

    retrieved = retriever.query_rerank_and_boost(hypothesis_id, hypothesis_text)
    context = " ".join(r.chunk.text for r in retrieved)
    rag_result = classify(context, hypothesis_text, gateway, doc_id=doc_id, hypothesis_id=hypothesis_id)

    plain_retrieved = retriever.query_and_rerank(hypothesis_text)
    plain_context = " ".join(r.chunk.text for r in plain_retrieved)
    plain_result = classify(plain_context, hypothesis_text, gateway, doc_id=doc_id, hypothesis_id=hypothesis_id)

    rule_label = classify_by_keywords(hypothesis_id, doc_text)
    decision = route(self_confidence=rag_result.confidence, rule_agrees=(rule_label == plain_result.label))

    if decision.route == Route.REVIEW:
        initial_chunks = [r.chunk for r in retrieved]
        agent_result = run_agent(retriever, hypothesis_id, hypothesis_text, initial_chunks,
                                  gateway, doc_id=doc_id)
        label, confidence = agent_result.label, agent_result.confidence
        explanation = agent_result.explanation
        evidence = agent_result.evidence
        cost = rag_result.cost_usd + plain_result.cost_usd + agent_result.cost_usd
        tin = rag_result.tokens_in + plain_result.tokens_in + agent_result.tokens_in
        tout = rag_result.tokens_out + plain_result.tokens_out + agent_result.tokens_out
        latency = rag_result.latency_ms + plain_result.latency_ms + agent_result.latency_ms
        agent_used = True
        agent_steps = len(agent_result.trace.steps)
    else:
        label, confidence = rag_result.label, rag_result.confidence
        explanation = rag_result.explanation
        evidence = rag_result.evidence
        cost = rag_result.cost_usd + plain_result.cost_usd
        tin = rag_result.tokens_in + plain_result.tokens_in
        tout = rag_result.tokens_out + plain_result.tokens_out
        latency = rag_result.latency_ms + plain_result.latency_ms
        agent_used = False
        agent_steps = 0

    logger.info("Orchestrator: reviewed requirement", extra={
        "stage": "review_requirement", "doc_id": doc_id, "hypothesis_id": hypothesis_id,
        "label": label, "confidence": confidence, "agent_used": agent_used,
        "cost_usd": cost, "latency_ms": round(latency, 1), "model": gateway.model,
    })

    return ReviewResult(
        hypothesis_id=hypothesis_id, hypothesis_text=hypothesis_text, label=label,
        confidence=confidence, explanation=explanation, evidence=evidence,
        agent_used=agent_used, agent_steps=agent_steps, cost_usd=cost,
        latency_ms=latency, tokens_in=tin, tokens_out=tout,
    )


def review_document(
    doc_text: str,
    hypotheses: dict[str, str],
    gateway: ModelGateway,
    doc_id: str = "",
) -> list[ReviewResult]:
    """
    Review a document against every given hypothesis (hypothesis_id ->
    hypothesis_text), reusing one Retriever (and its embeddings) across
    all of them rather than re-chunking/re-embedding per hypothesis.

    Each hypothesis is isolated: a ModelError on one (e.g. a transient
    provider failure that exhausts all retries) produces an error-flagged
    ReviewResult for that hypothesis only, never aborting the rest (WBS
    T032 code-audit finding, 2026-09-24 - eval case 095, "1 of 17 fails ->
    other 16 succeed" - the original version had no per-hypothesis
    isolation at all, so any single failure discarded every result).
    """
    retriever = Retriever(doc_text, chunk_method="sentence")
    results = []
    for hyp_id, hyp_text in hypotheses.items():
        try:
            results.append(review_requirement(doc_text, hyp_id, hyp_text, gateway,
                                                retriever=retriever, doc_id=doc_id))
        except ModelError as e:
            logger.error("Orchestrator: model call failed for one hypothesis, continuing", extra={
                "stage": "review_requirement_failed", "doc_id": doc_id, "hypothesis_id": hyp_id,
                "error_code": "model_error", "model": gateway.model,
            })
            results.append(ReviewResult(
                hypothesis_id=hyp_id, hypothesis_text=hyp_text, label="NotMentioned", confidence=0.0,
                explanation="", evidence=[], agent_used=False, agent_steps=0, cost_usd=0.0,
                latency_ms=0.0, tokens_in=0, tokens_out=0, error=str(e),
            ))
    return results
