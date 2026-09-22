"""
Data leakage prevention checks (WBS T026-adjacent, Category 8 of
NDATrace_100_eval_cases.md, eval cases 086-090). Deterministic code
checks, $0 cost - no LLM calls.

Case 088 (test/dev split leakage) is already covered by
tests/test_parser.py's test_check_split_leakage_* tests, reusing
pipeline/parser.py's check_split_leakage - not duplicated here.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.classifier import classify
from pipeline.config import settings

REPO_ROOT = Path(__file__).resolve().parent.parent
LABEL_STRINGS = ("Entailment", "Contradiction", "NotMentioned")

# Production modules that must never reference gold evidence directly -
# scripts/run_oracle_experiment.py is the one deliberate, gated exception.
PRODUCTION_MODULES = [
    "pipeline/classifier.py",
    "pipeline/retriever.py",
    "pipeline/chunker.py",
    "pipeline/embedder.py",
    "pipeline/reranker.py",
    "pipeline/indexer.py",
    "pipeline/model_gateway.py",
]


def _fake_gateway(response_json: str):
    """A ModelGateway stand-in that records the exact prompts it was called with."""
    gateway = MagicMock()
    response = MagicMock()
    response.content = response_json
    response.tokens_in = 10
    response.tokens_out = 10
    response.cost_usd = 0.0001
    response.latency_ms = 100.0
    gateway.complete.return_value = response
    return gateway


# --- 086: Gold labels never appear in any prompt sent to the model ---

def test_classify_signature_has_no_gold_label_parameter():
    """classify() structurally cannot leak a gold label - it isn't a parameter at all."""
    params = inspect.signature(classify).parameters
    assert not any("gold" in name.lower() or "label" in name.lower() for name in params)


def test_classify_prompt_never_contains_gold_label_strings():
    """
    Build a real prompt for a case whose (unused) gold label is known to
    the test but never passed to classify() - confirms it can't leak into
    the constructed user message regardless of what the caller happens to know.
    """
    nda_text = "Receiving Party shall keep all proprietary drawings confidential for two years."
    hypothesis = "Receiving Party must not disclose Confidential Information to any third party."
    gateway = _fake_gateway('{"label": "Entailment", "confidence": 0.9, "evidence": [], "explanation": "ok"}')

    classify(nda_text, hypothesis, gateway)

    user_prompt = gateway.complete.call_args.kwargs["user_prompt"]
    # The label vocabulary legitimately appears in the SYSTEM prompt (it
    # names the three allowed output labels) - the leakage risk is the
    # USER message (built only from nda_text/hypothesis) hinting at the
    # answer for this specific case, which it structurally cannot do.
    for label in LABEL_STRINGS:
        assert label not in user_prompt


# --- 087: Gold evidence never used as retrieval input except Oracle (gated) ---

@pytest.mark.parametrize("module_path", PRODUCTION_MODULES)
def test_production_modules_never_reference_gold_evidence_spans(module_path):
    source = (REPO_ROOT / module_path).read_text()
    assert "evidence_spans" not in source, (
        f"{module_path} references 'evidence_spans' (gold evidence) - "
        "only scripts/run_oracle_experiment.py may do this, and only "
        "behind settings.oracle_mode"
    )


# --- 089: Test set metrics never used for threshold tuning - only dev set ---

@pytest.mark.parametrize("module_path", PRODUCTION_MODULES + ["evaluation/harness.py", "evaluation/scorer.py"])
def test_no_current_module_reads_the_test_split(module_path):
    source = (REPO_ROOT / module_path).read_text()
    assert "test.json" not in source, (
        f"{module_path} references 'test.json' (the held-out test split) - "
        "the test split must stay untouched until the final locked evaluation (T041)"
    )


# --- 090: Oracle experiment gated by explicit config flag ---

def test_oracle_context_refuses_gold_evidence_when_oracle_mode_is_off():
    from scripts.run_oracle_experiment import build_oracle_context

    original = settings.oracle_mode
    settings.oracle_mode = False
    try:
        fake_ann = MagicMock(evidence_spans=[MagicMock(text="secret evidence")])
        with pytest.raises(RuntimeError, match="oracle_mode"):
            build_oracle_context(fake_ann)
    finally:
        settings.oracle_mode = original


def test_oracle_context_allows_gold_evidence_when_oracle_mode_is_explicitly_on():
    from scripts.run_oracle_experiment import build_oracle_context

    original = settings.oracle_mode
    settings.oracle_mode = True
    try:
        fake_ann = MagicMock(evidence_spans=[MagicMock(text="the evidence text")])
        assert build_oracle_context(fake_ann) == "the evidence text"
    finally:
        settings.oracle_mode = original


def test_oracle_mode_defaults_to_false():
    """Never let the gate default to open."""
    from pipeline.config import Settings
    assert Settings().oracle_mode is False
