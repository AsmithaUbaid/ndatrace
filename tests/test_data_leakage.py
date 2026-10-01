"""
Data leakage prevention checks (WBS T026-adjacent, Category 8 of
docs/evaluation_case_design.md, eval cases 086-090). Deterministic code
checks, $0 cost - no LLM calls.

Case 088 (test/dev split leakage) is already covered by
tests/test_parser.py's test_check_split_leakage_* tests, reusing
pipeline/parser.py's check_split_leakage - not duplicated here.

Legacy cleanup (2026-09-29): pipeline/classifier.py and scripts/run_oracle_experiment.py
(the old, gated build_oracle_context()/oracle_mode design) were deleted - neither had
any current importer besides this file and their own now-deleted legacy tests. Cases 086/
087/089 below now exercise pipeline/final_review.py's review_final(), the real current
production classification path. Case 090 (oracle gated by an explicit config flag) has no
current equivalent: the live E01 Oracle experiment (scripts/run_e01_oracle.py,
evaluation/oracle.py) uses a different design with no oracle_mode-style gate, so those
three tests were removed rather than faked against dead code.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.final_review import review_final

REPO_ROOT = Path(__file__).resolve().parent.parent
LABEL_STRINGS = ("Entailment", "Contradiction", "NotMentioned")

# Production modules that must never reference gold evidence directly -
# scripts/run_oracle_experiment.py was the one deliberate, gated exception (deleted
# 2026-09-29 along with pipeline/classifier.py; see the module docstring above).
PRODUCTION_MODULES = [
    "pipeline/final_review.py",
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


class _StubRetriever:
    """Frozen-RAG-shaped retriever stub - returns the whole nda_text as one chunk."""

    def __init__(self, nda_text: str):
        self._nda_text = nda_text

    def retrieve(self, hypothesis_text: str):
        from pipeline.frozen_rag import RetrievedChunk
        return [RetrievedChunk(
            chunk_id=0, rank=1, start_char=0, end_char=len(self._nda_text),
            bm25_score=1.0, reranker_score=1.0, text=self._nda_text,
        )]


# --- 086: Gold labels never appear in any prompt sent to the model ---

def test_review_final_signature_has_no_gold_label_parameter():
    """review_final() structurally cannot leak a gold label - it isn't a parameter at all."""
    params = inspect.signature(review_final).parameters
    assert not any("gold" in name.lower() or "label" in name.lower() for name in params)


def test_review_final_prompt_never_contains_gold_label_strings():
    """
    Build a real prompt for a case whose (unused) gold label is known to
    the test but never passed to review_final() - confirms it can't leak
    into the constructed user message regardless of what the caller happens
    to know.
    """
    nda_text = "Receiving Party shall keep all proprietary drawings confidential for two years."
    hypothesis = "Receiving Party must not disclose Confidential Information to any third party."
    gateway = _fake_gateway('{"label": "Entailment", "evidence": []}')

    review_final(nda_text, hypothesis, gateway=gateway, retriever=_StubRetriever(nda_text))

    user_prompt = gateway.complete.call_args.kwargs["user_prompt"]
    # The label vocabulary legitimately appears in the SYSTEM prompt (it
    # names the allowed output labels) - the leakage risk is the USER
    # message (built only from nda_text/hypothesis_text) hinting at the
    # answer for this specific case, which it structurally cannot do.
    for label in LABEL_STRINGS:
        assert label not in user_prompt


# --- 087: Gold evidence never used as retrieval input except Oracle (gated) ---

@pytest.mark.parametrize("module_path", PRODUCTION_MODULES)
def test_production_modules_never_reference_gold_evidence_spans(module_path):
    source = (REPO_ROOT / module_path).read_text()
    assert "evidence_spans" not in source, (
        f"{module_path} references 'evidence_spans' (gold evidence) - "
        "only the current E01 Oracle experiment (scripts/run_e01_oracle.py, "
        "evaluation/oracle.py) may do this"
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
#
# Removed 2026-09-29: this gate (settings.oracle_mode + scripts/run_oracle_experiment.py's
# build_oracle_context()) belonged to the deleted legacy B04 oracle script. The current E01
# Oracle experiment (scripts/run_e01_oracle.py, evaluation/oracle.py) uses a different
# design with no equivalent gate, so this case has no current target to test against.
