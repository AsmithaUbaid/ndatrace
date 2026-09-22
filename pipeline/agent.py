"""
Selective agent router (WBS T029, Section 6 "Agent Core").

Called when pipeline/confidence.py (T027) routes a case to REVIEW (the
rule-based baseline disagreed with the standard RAG prediction - T026
found this bucket is only weakly, not strongly, more likely to be
wrong). The agent gets a further, bounded investigation budget: at each
step it either calls one tool (pipeline/agent_tools.py, T028) to gather
more evidence, or concludes with a final classification.

Stops on: a conclusion, the step limit (settings.agent_max_steps), the
time limit (settings.agent_max_seconds), or a duplicate tool call (the
exact same action+query already tried - the model looping without
making progress). If none of those trigger, falls back to a plain
classify() call over everything gathered rather than returning nothing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.agent_tools import (
    find_defined_term,
    inspect_neighbouring_clauses,
    retrieve_more_evidence,
    search_clauses,
    search_exceptions,
)
from pipeline.chunker import Chunk
from pipeline.classifier import VALID_LABELS, classify
from pipeline.config import settings
from pipeline.logging_config import get_logger
from pipeline.model_gateway import ModelGateway
from pipeline.retriever import Retriever

logger = get_logger("agent")

AGENT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "agent_step_v1.txt"
VALID_ACTIONS = {
    "search_clauses", "find_defined_term", "search_exceptions",
    "retrieve_more_evidence", "inspect_neighbouring_clauses", "conclude",
}


@dataclass
class AgentStep:
    step_number: int
    action: str
    query: str
    result_summary: str


@dataclass
class AgentTrace:
    steps: list[AgentStep] = field(default_factory=list)
    stopped_reason: str = ""


@dataclass
class AgentResult:
    label: str
    confidence: float
    evidence: list[str]
    explanation: str
    trace: AgentTrace
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float


def _load_agent_prompt() -> str:
    return AGENT_PROMPT_PATH.read_text()


def _format_evidence(chunks: list[Chunk]) -> str:
    return "\n".join(f"[{i}] {c.text}" for i, c in enumerate(chunks))


def _decide_next_action(hypothesis: str, chunks: list[Chunk], gateway: ModelGateway):
    system_prompt = _load_agent_prompt()
    user_message = (
        f'Requirement to classify:\n"{hypothesis}"\n\n'
        f'Evidence gathered so far:\n"""\n{_format_evidence(chunks)}\n"""'
    )
    response = gateway.complete(
        system_prompt=system_prompt, user_prompt=user_message,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(response.content)
    except (json.JSONDecodeError, TypeError):
        data = None
    if not isinstance(data, dict):
        data = None
    return data, response


def _execute_tool(action: str, query: str, chunk_index: int, retriever: Retriever,
                   evidence_chunks: list[Chunk]) -> list[Chunk]:
    if action == "search_clauses":
        return [r.chunk for r in search_clauses(retriever, query)]
    if action == "find_defined_term":
        return [r.chunk for r in find_defined_term(retriever, query)]
    if action == "search_exceptions":
        return search_exceptions(retriever)
    if action == "retrieve_more_evidence":
        return [r.chunk for r in retrieve_more_evidence(retriever, query, exclude_chunks=evidence_chunks)]
    if action == "inspect_neighbouring_clauses":
        if 0 <= chunk_index < len(evidence_chunks):
            return inspect_neighbouring_clauses(retriever, evidence_chunks[chunk_index])
        return []
    return []


def run_agent(
    retriever: Retriever,
    hypothesis_id: str,
    hypothesis_text: str,
    initial_chunks: list[Chunk],
    gateway: ModelGateway,
    max_steps: int | None = None,
    max_seconds: int | None = None,
) -> AgentResult:
    max_steps = settings.agent_max_steps if max_steps is None else max_steps
    max_seconds = settings.agent_max_seconds if max_seconds is None else max_seconds

    start = time.time()
    evidence_chunks: list[Chunk] = list(initial_chunks)
    seen_calls: set[tuple[str, str]] = set()
    steps: list[AgentStep] = []
    total_cost = 0.0
    total_tokens_in = 0
    total_tokens_out = 0
    stopped_reason = "step_limit"

    for step_num in range(1, max_steps + 1):
        if time.time() - start > max_seconds:
            stopped_reason = "time_limit"
            break

        decision, response = _decide_next_action(hypothesis_text, evidence_chunks, gateway)
        total_cost += response.cost_usd
        total_tokens_in += response.tokens_in
        total_tokens_out += response.tokens_out

        if decision is None or decision.get("action") not in VALID_ACTIONS:
            logger.warning("Agent: invalid or unparseable action, stopping")
            stopped_reason = "invalid_action"
            break

        action = decision["action"]

        if action == "conclude":
            label = decision.get("label")
            if label not in VALID_LABELS:
                logger.warning(f"Agent: conclude with invalid label {label!r}, stopping")
                stopped_reason = "invalid_conclusion"
                break
            steps.append(AgentStep(step_num, "conclude", "", f"Concluded: {label}"))
            return AgentResult(
                label=label, confidence=float(decision.get("confidence", 0.5)),
                evidence=list(decision.get("evidence", [])),
                explanation=str(decision.get("explanation", "")),
                trace=AgentTrace(steps=steps, stopped_reason="concluded"),
                tokens_in=total_tokens_in, tokens_out=total_tokens_out,
                cost_usd=total_cost, latency_ms=(time.time() - start) * 1000,
            )

        query = str(decision.get("query", ""))
        call_key = (action, query)
        if call_key in seen_calls:
            logger.info(f"Agent: duplicate call to {action!r} with same query, stopping")
            stopped_reason = "duplicate_loop"
            break
        seen_calls.add(call_key)

        new_chunks = _execute_tool(action, query, int(decision.get("chunk_index", 0) or 0),
                                    retriever, evidence_chunks)
        added = [c for c in new_chunks if c not in evidence_chunks]
        evidence_chunks.extend(added)
        steps.append(AgentStep(step_num, action, query, f"Added {len(added)} new chunk(s)"))
    else:
        stopped_reason = "step_limit"

    # Fell through without a "conclude" action - fall back to a plain
    # classify() call over everything gathered rather than returning
    # nothing. Whether this counts as a case the agent should have
    # abstained on is decided upstream by pipeline/confidence.py, not here.
    context = " ".join(c.text for c in evidence_chunks)
    fallback = classify(context, hypothesis_text, gateway)
    total_cost += fallback.cost_usd
    total_tokens_in += fallback.tokens_in
    total_tokens_out += fallback.tokens_out
    steps.append(AgentStep(len(steps) + 1, "fallback_classify", "", f"Fallback: {fallback.label}"))

    return AgentResult(
        label=fallback.label, confidence=fallback.confidence,
        evidence=fallback.evidence, explanation=fallback.explanation,
        trace=AgentTrace(steps=steps, stopped_reason=stopped_reason),
        tokens_in=total_tokens_in, tokens_out=total_tokens_out,
        cost_usd=total_cost, latency_ms=(time.time() - start) * 1000,
    )
