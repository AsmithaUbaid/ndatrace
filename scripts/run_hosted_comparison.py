#!/usr/bin/env python3
"""
Hosted-vs-local comparison (C02, problem statement's "Compute: Rent +
local" commitment) - runs the same architectures on the SAME 500-case
stratified test subsample used by scripts/run_final_test_evaluation.py
(identical seed=42 selection), but on the hosted model (Gemini 2.5
Flash Lite, the adopted default - ModelGateway(), not .local()/.groq())
instead of local Llama.

Using the IDENTICAL cases (not a different subsample) makes this a
direct, case-level comparison rather than two separate samples that
happen to be the same size - the real question ("is the extra cost of
hosted worth it over local?") deserves that rigor, and Gemini's real
cost is trivial at this scale (~$0.30-0.40 total for all three
LLM-dependent architectures, based on this project's own measured
per-case costs).

Reuses run_full_context/run_rag/run_rag_agent from
run_final_test_evaluation.py directly rather than duplicating the
pipeline logic - only the gateway differs.

Usage:
    python scripts/run_hosted_comparison.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.retriever import Retriever
from scripts.run_final_test_evaluation import (
    DEFAULT_SAMPLE_SIZE,
    build_golds,
    load_test_cases,
    run_full_context,
    run_rag,
    run_rag_agent,
)


def main() -> int:
    cases = load_test_cases(DEFAULT_SAMPLE_SIZE)
    golds = build_golds(cases)
    harness = EvaluationHarness(gold_cases=golds)

    try:
        gateway = ModelGateway()  # default: google/gemini-2.5-flash-lite
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"Hosted model: {gateway.model}")

    run_full_context(cases, golds, harness, gateway)
    retrievers: dict[str, Retriever] = {}
    run_rag(cases, golds, harness, gateway, retrievers)
    run_rag_agent(cases, golds, harness, gateway, retrievers)

    print("=== HOSTED-VS-LOCAL COMPARISON COMPLETE ===")
    print("Compare against run_T041_final_test_*_llama3.2_3b.jsonl (or "
          "*_openai_gpt-oss-20b.jsonl if run via Groq) for the same 500 cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
