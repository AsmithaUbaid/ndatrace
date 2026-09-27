"""
E10/E11 (reconstruction-v2) -- the NEW bounded selective agent (A3) prototype: routing trigger,
strict agent-action schema/validation, a finite bounded loop, hard limits enforced OUTSIDE the
model, duplicate-call protection, and a fallback-to-A2 policy. Does NOT modify or import
`pipeline/agent.py`/`pipeline/agent_tools.py`/`pipeline/confidence.py` (T-series, historical,
byte-unchanged).

Frozen per E10 Stage A (experiments/E10_agent_design/summary.md) -- nothing here is tuned on E11
outcomes, since E11 has not run yet.

Makes NO model calls itself: the model interface is injected via a callable
(`model_call: Callable[[str, str], str]` -- system prompt, user prompt -> raw response text) so
this module can be exercised entirely offline with a deterministic stub (see
tests/test_agent_v2.py), and later wired to a real `ModelGateway` call by E11's runner without any
change to this module.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pipeline.agent_tools_v2 import (
    ToolResult,
    follow_cross_reference,
    get_more_candidates,
)

# =============================================================================
# Hard limits (frozen, E10 Stage A section 12) -- enforced in code, never left to the model.
# =============================================================================
MAX_AGENT_STEPS = 3
MAX_TOOL_CALLS = 2
MAX_IDENTICAL_CALL_REPEATS = 1  # a 2nd identical call forces FINAL immediately
MAX_CUMULATIVE_ADDED_CONTEXT_CHARS = 2000 * 4  # ~2000 tokens, 4 chars/token approximation
MAX_TOTAL_MODEL_CALLS_PER_CASE = 4  # 1 baseline A2 (already made, not repeated) + up to 3 loop steps
MAX_WALL_CLOCK_SECONDS = 60
MAX_ESTIMATED_AGENT_COST_USD = 0.01  # circuit breaker, not an expected value

VALID_ACTIONS = {"FINAL", "FOLLOW_CROSS_REFERENCE", "GET_MORE_CANDIDATES"}
VALID_LABELS = {"Entailment", "Contradiction", "NotMentioned"}

STOP_REASONS = {
    "final", "not_triggered", "max_steps", "max_tool_calls", "duplicate_tool_call",
    "context_budget", "cost_budget", "wall_clock", "invalid_action", "tool_failure_exhausted",
}

CONTROL_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "agent_v2_control.txt"


# =============================================================================
# Routing trigger (frozen, E10 Stage A section 5) -- the ONLY real runtime trigger. Never uses
# gold labels/evidence/known-error status. Do NOT broaden without a new design pass.
# =============================================================================
CROSS_REFERENCE_PATTERNS = (
    "of the definition of", "as defined in", "pursuant to section", "pursuant to clause",
    "under clause", "under section", "as set forth in section", "as provided in section",
    "in accordance with section", "paragraph (a)", "paragraphs (a)",
)


def cross_reference_to_named_provision_cue(context_chunks: list[str]) -> bool:
    """The single frozen E10/E11 runtime trigger. Fires on a small fixed set of cross-reference
    phrase patterns in the final top-5 context shown to A2 -- exactly the detector E09 evaluated
    across all 150 TRAIN_ARCH_v1 cases (TP=1, FP=14, FN=0, TN=135, 6.7% precision, 100% recall,
    ~10% expected escalation rate). Does NOT use gold labels, gold evidence, evaluator failure
    buckets, or "known wrong prediction" -- context text only, exactly as A2 would see it."""
    ctx = " ".join(context_chunks).lower()
    return any(p in ctx for p in CROSS_REFERENCE_PATTERNS)


# =============================================================================
# Agent action schema + strict (non-permissive) parsing
# =============================================================================

@dataclass
class AgentAction:
    action: str
    arguments: dict = field(default_factory=dict)
    label: str | None = None
    evidence: list[str] = field(default_factory=list)


class MalformedActionError(Exception):
    """Raised by parse_agent_action; callers must catch this and force FINAL -- never propagate
    to a crash."""


def parse_agent_action(raw_response: str) -> AgentAction:
    """Strict JSON parsing only -- no permissive free-text action parsing, no recovery-scan
    fallback (unlike evaluation.structured_output's classification parser, which exists to
    tolerate trailing prose on a FINAL answer; an agent ACTION is a control-flow decision, and an
    ambiguous one must fail closed, not be guessed at)."""
    try:
        obj = json.loads(raw_response.strip())
    except (json.JSONDecodeError, ValueError) as e:
        raise MalformedActionError(f"not valid JSON: {e}") from e

    if not isinstance(obj, dict):
        raise MalformedActionError("action is not a JSON object")

    action = obj.get("action")
    if action not in VALID_ACTIONS:
        raise MalformedActionError(f"unknown or missing action: {action!r}")

    arguments = obj.get("arguments", {})
    if not isinstance(arguments, dict):
        raise MalformedActionError("arguments must be an object")

    if action == "FINAL":
        label = obj.get("label")
        if label not in VALID_LABELS:
            raise MalformedActionError(f"FINAL requires a valid label, got {label!r}")
        evidence = obj.get("evidence", [])
        if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
            raise MalformedActionError("evidence must be a list of strings")
        return AgentAction(action=action, arguments={}, label=label, evidence=evidence)

    if action == "FOLLOW_CROSS_REFERENCE":
        if "reference" not in arguments or not isinstance(arguments["reference"], str):
            raise MalformedActionError("FOLLOW_CROSS_REFERENCE requires a string 'reference' argument")
    # GET_MORE_CANDIDATES takes no meaningful model-supplied argument -- the window is tracked by
    # the loop's own state, per the frozen design (prevents the model from requesting an
    # arbitrary/duplicate rank window).

    return AgentAction(action=action, arguments=arguments)


def _normalize_signature(action: AgentAction) -> tuple:
    """(action, canonicalized arguments) -- whitespace/case-normalized for string arguments,
    tighter than the historical agent's plain exact-string match."""
    norm_args = {}
    for k, v in sorted(action.arguments.items()):
        norm_args[k] = v.strip().lower() if isinstance(v, str) else v
    return (action.action, tuple(sorted(norm_args.items())))


# =============================================================================
# Result trace (frozen fields, E10 Stage A section 16 / this stage's section 16)
# =============================================================================

@dataclass
class AgentTrace:
    case_id: str
    triggered: bool
    trigger_reasons: list[str] = field(default_factory=list)
    a2_label: str | None = None
    a2_evidence: list[str] = field(default_factory=list)
    agent_steps: int = 0
    tool_calls: int = 0
    tool_names: list[str] = field(default_factory=list)
    tool_call_arguments: list[dict] = field(default_factory=list)
    tool_results_summary: list[dict] = field(default_factory=list)
    duplicate_count: int = 0
    added_context_chars: int = 0
    agent_model_calls: int = 0
    final_label: str | None = None
    final_evidence: list[str] = field(default_factory=list)
    fallback_to_a2: bool = False
    stop_reason: str = ""
    latency_increment_s: float = 0.0
    invalid_action_count: int = 0
    tool_error_count: int = 0

    def to_dict(self) -> dict:
        return dict(self.__dict__)


# =============================================================================
# The bounded loop
# =============================================================================

def run_selective_agent(
    case_id: str,
    doc_text: str,
    hypothesis_text: str,
    a2_context_chunks: list[str],
    a2_label: str,
    a2_evidence: list[str],
    model_call: Callable[[str, str], str],
) -> AgentTrace:
    """Runs the bounded selective agent for ONE case. `model_call(system_prompt, user_prompt)`
    is injected so this function makes zero real model calls in E10's offline verification --
    E11's runner supplies a real ModelGateway-backed callable. Never raises: every failure mode
    (malformed action, tool failure, any hard limit) is caught and resolved via the fallback
    policy below.
    """
    trace = AgentTrace(case_id=case_id, triggered=False, a2_label=a2_label, a2_evidence=a2_evidence)

    triggered = cross_reference_to_named_provision_cue(a2_context_chunks)
    trace.triggered = triggered
    if triggered:
        trace.trigger_reasons = ["cross_reference_to_named_provision_cue"]
    if not triggered:
        trace.final_label = a2_label
        trace.final_evidence = a2_evidence
        trace.stop_reason = "not_triggered"
        return trace

    control_prompt = CONTROL_PROMPT_PATH.read_text()
    seen_signatures: set[tuple] = set()
    already_revealed_candidates = len(a2_context_chunks)  # starts at 5 (A2's top-5)
    context_so_far = list(a2_context_chunks)
    start_time = time.perf_counter()

    def _fallback(reason: str) -> AgentTrace:
        trace.fallback_to_a2 = True
        trace.final_label = a2_label
        trace.final_evidence = a2_evidence
        trace.stop_reason = reason
        trace.latency_increment_s = time.perf_counter() - start_time
        return trace

    for step in range(MAX_AGENT_STEPS):
        elapsed = time.perf_counter() - start_time
        if elapsed > MAX_WALL_CLOCK_SECONDS:
            return _fallback("wall_clock")
        if trace.added_context_chars > MAX_CUMULATIVE_ADDED_CONTEXT_CHARS:
            return _fallback("context_budget")
        # Estimated cost circuit breaker -- approximated per-step at the observed A2 baseline
        # mean ($0.0017/call, E08B measurement); a real per-call cost is recorded by E11's runner.
        # Projects the cost of the CALL ABOUT TO BE MADE (agent_model_calls + 1), not just calls
        # already made -- otherwise a limit of $0 could never actually block the first call, since
        # $0 already spent never exceeds $0 either.
        projected_cost_after_next_call = (trace.agent_model_calls + 1) * 0.0017
        if projected_cost_after_next_call > MAX_ESTIMATED_AGENT_COST_USD:
            return _fallback("cost_budget")

        user_prompt = _build_user_prompt(hypothesis_text, context_so_far)
        trace.agent_model_calls += 1
        raw_response = model_call(control_prompt, user_prompt)
        trace.agent_steps += 1

        try:
            action = parse_agent_action(raw_response)
        except MalformedActionError:
            trace.invalid_action_count += 1
            return _fallback("invalid_action")

        if action.action == "FINAL":
            trace.final_label = action.label
            trace.final_evidence = action.evidence
            trace.stop_reason = "final"
            trace.latency_increment_s = time.perf_counter() - start_time
            return trace

        # Tool call.
        if trace.tool_calls >= MAX_TOOL_CALLS:
            return _fallback("max_tool_calls")

        signature = _normalize_signature(action)
        if signature in seen_signatures:
            trace.duplicate_count += 1
            return _fallback("duplicate_tool_call")
        seen_signatures.add(signature)

        tool_result = _dispatch_tool(action, doc_text, hypothesis_text, already_revealed_candidates)
        trace.tool_calls += 1
        trace.tool_names.append(action.action)
        trace.tool_call_arguments.append(action.arguments)
        trace.tool_results_summary.append(tool_result.to_dict())

        if not tool_result.success:
            trace.tool_error_count += 1
            # A failed tool call still becomes a structured observation appended to context (so
            # the model can adapt), not an immediate fallback -- only step/tool-call/duplicate
            # limits force termination. If this was the last allowed tool call, the loop's own
            # step-count/tool-call-count limits will catch it on the next iteration.
        else:
            if action.action == "GET_MORE_CANDIDATES":
                already_revealed_candidates += len(tool_result.results)

        new_text_chars = tool_result.total_text_chars()
        trace.added_context_chars += new_text_chars
        context_so_far.append(_format_tool_observation(tool_result))

    # Exhausted MAX_AGENT_STEPS without a FINAL action.
    return _fallback("max_steps")


def _dispatch_tool(action: AgentAction, doc_text: str, hypothesis_text: str,
                    already_revealed_candidates: int) -> ToolResult:
    """Deterministic dispatch -- no free-form tool execution, no arbitrary tool names reachable
    (VALID_ACTIONS is closed, parse_agent_action already rejected anything else)."""
    if action.action == "FOLLOW_CROSS_REFERENCE":
        return follow_cross_reference(doc_text, action.arguments["reference"])
    if action.action == "GET_MORE_CANDIDATES":
        return get_more_candidates(doc_text, hypothesis_text, already_revealed_candidates)
    raise AssertionError(f"unreachable: {action.action}")  # VALID_ACTIONS already excludes this


def _format_tool_observation(tool_result: ToolResult) -> str:
    """Compact, structured -- never the raw tool dict dumped verbatim into the prompt."""
    if not tool_result.success:
        return f"[{tool_result.tool}] not found for {tool_result.query_or_target!r} ({tool_result.error})"
    texts = "; ".join(r["text"] for r in tool_result.results if r.get("text"))
    return f"[{tool_result.tool}] {texts}"


def _build_user_prompt(hypothesis_text: str, context_chunks: list[str]) -> str:
    context_text = "\n\n---\n\n".join(context_chunks)
    return f"Requirement: {hypothesis_text}\n\nCurrent evidence: {context_text}"


def demo() -> None:
    """Smallest runnable self-check -- no network, no model calls (uses a deterministic stub)."""
    doc = "1. Definitions.\n\n" + '"Confidential Information" means information.' * 20

    def stub_immediate_final(_system: str, _user: str) -> str:
        return json.dumps({"action": "FINAL", "label": "Entailment", "evidence": ["quote"]})

    trace = run_selective_agent(
        case_id="demo::1", doc_text=doc, hypothesis_text="req",
        a2_context_chunks=["pursuant to section 4, the term shall apply"],
        a2_label="NotMentioned", a2_evidence=[], model_call=stub_immediate_final,
    )
    assert trace.triggered is True
    assert trace.stop_reason == "final"
    assert trace.final_label == "Entailment"

    trace_not_triggered = run_selective_agent(
        case_id="demo::2", doc_text=doc, hypothesis_text="req",
        a2_context_chunks=["a plain clause with no cross-reference at all"],
        a2_label="NotMentioned", a2_evidence=[], model_call=stub_immediate_final,
    )
    assert trace_not_triggered.triggered is False
    assert trace_not_triggered.stop_reason == "not_triggered"
    assert trace_not_triggered.final_label == "NotMentioned"
    assert trace_not_triggered.agent_model_calls == 0

    print("pipeline/agent_v2.py self-check OK")


if __name__ == "__main__":
    demo()
