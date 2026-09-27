"""
Tests for pipeline/agent_v2.py (E10/E11, reconstruction-v2) -- the bounded selective agent (A3)
prototype. All model calls are a deterministic in-process stub -- zero hosted/local model calls
anywhere in this file. Does not import or exercise pipeline/agent.py (historical, untouched).
"""

from __future__ import annotations

import json

import pytest

from pipeline.agent_v2 import (
    MAX_AGENT_STEPS,
    MAX_TOOL_CALLS,
    STOP_REASONS,
    AgentAction,
    MalformedActionError,
    cross_reference_to_named_provision_cue,
    parse_agent_action,
    run_selective_agent,
)

FILLER = (" Additional recital language padding this individual clause out well past the two "
          "hundred fifty six token chunk budget so it cannot be merged with any neighboring "
          "clause during chunking.") * 6

DOC = (
    f"1. Definitions.{FILLER}\n\n"
    f'"Confidential Information" means any and all information disclosed by either '
    f"party.{FILLER}\n\n"
    f"4(b) The Receiving Party shall not copy Confidential Information without "
    f"consent.{FILLER}\n\n"
    f"7. This Agreement shall be governed by the laws of Delaware.{FILLER}\n"
)

TRIGGERING_CONTEXT = ["this clause is governed pursuant to section 4, see paragraph (a) for details"]
NON_TRIGGERING_CONTEXT = ["a plain confidentiality clause with no cross-reference at all"]


def _final(label="Entailment", evidence=None):
    return json.dumps({"action": "FINAL", "label": label, "evidence": evidence or []})


def _tool_call(action, arguments=None):
    return json.dumps({"action": action, "arguments": arguments or {}})


def _scripted_stub(responses):
    """Returns a model_call callable that yields each of `responses` in order, one per call."""
    it = iter(responses)

    def _call(_system, _user):
        return next(it)

    return _call


# =============================================================================
# Routing
# =============================================================================

def test_trigger_false_returns_a2_semantically_unchanged():
    trace = run_selective_agent(
        case_id="c1", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=NON_TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([_final("Entailment", ["should never be reached"])]),
    )
    assert trace.triggered is False
    assert trace.final_label == "NotMentioned"
    assert trace.final_evidence == []
    assert trace.stop_reason == "not_triggered"
    assert trace.agent_model_calls == 0  # the agent must never be invoked when not triggered


def test_trigger_true_enters_loop():
    trace = run_selective_agent(
        case_id="c2", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([_final("Contradiction", ["quote"])]),
    )
    assert trace.triggered is True
    assert trace.agent_model_calls == 1
    assert trace.final_label == "Contradiction"


def test_cross_reference_cue_detection():
    assert cross_reference_to_named_provision_cue(["pursuant to section 4"]) is True
    assert cross_reference_to_named_provision_cue(["a totally unrelated clause"]) is False


# =============================================================================
# Action parsing / tool validation
# =============================================================================

def test_parse_all_three_valid_actions():
    assert parse_agent_action(_final("Entailment")).action == "FINAL"
    assert parse_agent_action(
        _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Section 4(b)"})
    ).action == "FOLLOW_CROSS_REFERENCE"
    assert parse_agent_action(_tool_call("GET_MORE_CANDIDATES")).action == "GET_MORE_CANDIDATES"


def test_unknown_action_rejected():
    with pytest.raises(MalformedActionError):
        parse_agent_action(_tool_call("SEARCH_THE_WEB"))


def test_malformed_json_rejected():
    with pytest.raises(MalformedActionError):
        parse_agent_action("not json at all")


def test_final_missing_label_rejected():
    with pytest.raises(MalformedActionError):
        parse_agent_action(json.dumps({"action": "FINAL", "evidence": []}))


def test_final_malformed_evidence_shape_rejected():
    with pytest.raises(MalformedActionError):
        parse_agent_action(json.dumps({"action": "FINAL", "label": "Entailment", "evidence": "not a list"}))


def test_tool_call_missing_required_argument_rejected():
    with pytest.raises(MalformedActionError):
        parse_agent_action(json.dumps({"action": "FOLLOW_CROSS_REFERENCE", "arguments": {}}))


# =============================================================================
# Loop behavior
# =============================================================================

def test_final_immediately():
    trace = run_selective_agent(
        case_id="c3", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([_final("Entailment", ["q1"])]),
    )
    assert trace.stop_reason == "final"
    assert trace.agent_steps == 1
    assert trace.tool_calls == 0


def test_one_tool_then_final():
    trace = run_selective_agent(
        case_id="c4", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Section 4(b)"}),
            _final("Contradiction", ["q1"]),
        ]),
    )
    assert trace.stop_reason == "final"
    assert trace.tool_calls == 1
    assert trace.tool_names == ["FOLLOW_CROSS_REFERENCE"]
    assert trace.final_label == "Contradiction"


def test_two_tools_then_final():
    trace = run_selective_agent(
        case_id="c5", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Section 4(b)"}),
            _tool_call("GET_MORE_CANDIDATES"),
            _final("Contradiction", ["q1"]),
        ]),
    )
    assert trace.tool_calls == 2
    assert trace.stop_reason == "final"


def test_max_tool_calls_forces_fallback():
    """With the frozen limits (MAX_TOOL_CALLS=2 < MAX_AGENT_STEPS=3), a 3rd tool-call attempt
    always hits the tool-call cap before the step cap -- never fabricates a fallback FINAL."""
    trace = run_selective_agent(
        case_id="c7", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=["a2 evidence"],
        model_call=_scripted_stub([
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Section 4(b)"}),
            _tool_call("GET_MORE_CANDIDATES"),
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Article 7"}),  # 3rd tool call, over MAX_TOOL_CALLS
        ]),
    )
    assert trace.tool_calls == MAX_TOOL_CALLS
    assert trace.stop_reason == "max_tool_calls"
    assert trace.fallback_to_a2 is True
    assert trace.final_label == "NotMentioned"
    assert trace.final_evidence == ["a2 evidence"]


def test_max_steps_forces_fallback(monkeypatch):
    """Scenario F: never-final until step cap -- must fall back to A2, never fabricate. Only
    reachable as its OWN distinct stop reason (separate from max_tool_calls) when the tool-call
    budget is not the binding constraint -- tested here with a relaxed tool-call cap to isolate
    the step-cap path specifically."""
    import pipeline.agent_v2 as agent_v2_module
    monkeypatch.setattr(agent_v2_module, "MAX_TOOL_CALLS", MAX_AGENT_STEPS)
    trace = run_selective_agent(
        case_id="c6", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=["a2 evidence"],
        model_call=_scripted_stub([
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Section 4(b)"}),
            _tool_call("GET_MORE_CANDIDATES"),
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Article 7"}),
        ]),
    )
    assert trace.stop_reason == "max_steps"
    assert trace.fallback_to_a2 is True
    assert trace.final_label == "NotMentioned"
    assert trace.final_evidence == ["a2 evidence"]
    assert trace.agent_steps <= MAX_AGENT_STEPS


def test_duplicate_call_forces_fallback():
    """Scenario D: same tool call twice."""
    trace = run_selective_agent(
        case_id="c8", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Section 4(b)"}),
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "  section 4(B)  "}),  # normalizes to a duplicate
        ]),
    )
    assert trace.stop_reason == "duplicate_tool_call"
    assert trace.duplicate_count == 1
    assert trace.fallback_to_a2 is True


def test_invalid_action_forces_fallback():
    """Scenario E: invalid action."""
    trace = run_selective_agent(
        case_id="c9", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=["kept"],
        model_call=_scripted_stub(["this is not JSON and not an action at all"]),
    )
    assert trace.stop_reason == "invalid_action"
    assert trace.invalid_action_count == 1
    assert trace.fallback_to_a2 is True
    assert trace.final_evidence == ["kept"]


def test_tool_failure_is_a_structured_observation_not_a_crash():
    """Scenario G: tool failure -- must not raise, must become a structured observation, and the
    loop must still be able to conclude afterward."""
    trace = run_selective_agent(
        case_id="c10", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Article 999"}),  # will not be found
            _final("NotMentioned", []),
        ]),
    )
    assert trace.tool_error_count == 1
    assert trace.stop_reason == "final"  # recovered gracefully, not a crash


def test_context_budget_forces_fallback(monkeypatch):
    """Scenario H: context-budget overflow."""
    import pipeline.agent_v2 as agent_v2_module
    monkeypatch.setattr(agent_v2_module, "MAX_CUMULATIVE_ADDED_CONTEXT_CHARS", 1)
    trace = run_selective_agent(
        case_id="c11", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Section 4(b)"}),
            _final("Contradiction", ["q1"]),
        ]),
    )
    assert trace.stop_reason == "context_budget"
    assert trace.fallback_to_a2 is True


def test_cost_budget_forces_fallback(monkeypatch):
    """Scenario I: cost-budget overflow."""
    import pipeline.agent_v2 as agent_v2_module
    monkeypatch.setattr(agent_v2_module, "MAX_ESTIMATED_AGENT_COST_USD", 0.0)
    trace = run_selective_agent(
        case_id="c12", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([_final("Entailment", [])]),
    )
    assert trace.stop_reason == "cost_budget"
    assert trace.fallback_to_a2 is True
    assert trace.agent_model_calls == 0  # the very first budget check must block before any call


# =============================================================================
# Trace / logging
# =============================================================================

def test_trace_has_exact_stop_reason_from_allowed_set():
    trace = run_selective_agent(
        case_id="c13", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([_final("Entailment", [])]),
    )
    assert trace.stop_reason in STOP_REASONS


def test_trace_counts_are_consistent():
    trace = run_selective_agent(
        case_id="c14", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([
            _tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "Section 4(b)"}),
            _final("Contradiction", ["q1"]),
        ]),
    )
    assert trace.tool_calls == len(trace.tool_names) == len(trace.tool_call_arguments) == len(trace.tool_results_summary)
    assert trace.agent_steps == 2


def test_trace_stores_no_hidden_reasoning_field():
    trace = run_selective_agent(
        case_id="c15", doc_text=DOC, hypothesis_text="req",
        a2_context_chunks=TRIGGERING_CONTEXT, a2_label="NotMentioned", a2_evidence=[],
        model_call=_scripted_stub([_final("Entailment", [])]),
    )
    trace_dict = trace.to_dict()
    assert "reasoning" not in trace_dict and "thought" not in trace_dict and "chain_of_thought" not in trace_dict


# =============================================================================
# Safety
# =============================================================================

def test_malicious_text_cannot_create_a_new_tool_name():
    """An action string that isn't one of the 4 frozen values is always rejected -- no dynamic
    tool-name construction is possible via parse_agent_action's closed VALID_ACTIONS set."""
    with pytest.raises(MalformedActionError):
        parse_agent_action(json.dumps({"action": "RUN_SHELL_COMMAND", "arguments": {"cmd": "rm -rf /"}}))


def test_tool_args_cannot_escape_current_nda_scope():
    """follow_cross_reference/get_more_candidates only ever receive doc_text for THIS case --
    there is no argument path that accepts a different document, a file path, or a URL."""
    action = parse_agent_action(_tool_call("FOLLOW_CROSS_REFERENCE", {"reference": "../../etc/passwd"}))
    # the argument is treated as an opaque reference string to search for within doc_text, never
    # as a path -- dispatch only ever calls follow_cross_reference(doc_text, reference)
    assert action.arguments["reference"] == "../../etc/passwd"


def test_no_filesystem_shell_network_action_exposed():
    from pipeline.agent_v2 import VALID_ACTIONS
    forbidden = {"READ_FILE", "WRITE_FILE", "EXEC", "SHELL", "HTTP_GET", "SEND_EMAIL"}
    assert VALID_ACTIONS.isdisjoint(forbidden)
    assert VALID_ACTIONS == {"FINAL", "FOLLOW_CROSS_REFERENCE", "GET_MORE_CANDIDATES"}
