#!/usr/bin/env python3
"""
One-off, verbose, REAL end-to-end trace of a single (document, hypothesis)
pair through the actual production pipeline - prints the exact context/
prompt the LLM consumes at every step, and the exact real response, for
both classifier calls and every agent step (if the case routes to REVIEW).

Uses the SAME real functions pipeline/orchestrator.py calls (imported
directly, nothing duplicated or reimplemented) - this makes REAL API calls
and is for one-off human inspection only, not part of any experiment or
result file. Not wired into any test, notebook, or doc.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.agent import AGENT_PROMPT_PATH, VALID_ACTIONS, _decide_next_action, _execute_tool, _format_evidence
from pipeline.classifier import classify, load_prompt_template, _build_user_message
from pipeline.config import settings
from pipeline.confidence import Route, route
from pipeline.model_gateway import ModelGateway
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever
from pipeline.rule_baseline import classify_by_keywords

DOC_ID = "56"
HYPOTHESIS_ID = "nda-16"
SPLIT = "dev"


def hr(title: str) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / f"{SPLIT}.json")
    doc = dataset.get_document(DOC_ID)
    ann = doc.annotations[HYPOTHESIS_ID]

    hr("INPUT")
    print(f"doc_id={DOC_ID}  hypothesis_id={HYPOTHESIS_ID}  gold_label={ann.label}")
    print(f"Hypothesis: {ann.hypothesis_text}")
    print(f"NDA length: {len(doc.text)} chars, {len(doc.spans)} spans")

    gateway = ModelGateway()
    print(f"Model: {gateway.model}")

    retriever = Retriever(doc.text, chunk_method="sentence")

    # --- Path A: rule-boosted retrieval + classify (the production answer if ACCEPTed) ---
    hr("STEP 1: Retrieval (rule-boosted) - real, local, free")
    retrieved_a = retriever.query_rerank_and_boost(HYPOTHESIS_ID, ann.hypothesis_text)
    context_a = " ".join(r.chunk.text for r in retrieved_a)
    print(f"{len(retrieved_a)} chunks retrieved. Context handed to classify() ({len(context_a)} chars):")
    print(context_a)

    hr("STEP 2: classify() call A (rule-boosted context) - REAL API CALL")
    system_prompt = load_prompt_template("v6")
    print("--- SYSTEM PROMPT (sent to LLM) ---")
    print(system_prompt)
    print("\n--- USER MESSAGE (sent to LLM, real _build_user_message output) ---")
    print(_build_user_message(context_a, ann.hypothesis_text))
    result_a = classify(context_a, ann.hypothesis_text, gateway, doc_id=DOC_ID, hypothesis_id=HYPOTHESIS_ID)
    print("\n--- REAL RESPONSE ---")
    print(f"label={result_a.label}  confidence={result_a.confidence}  evidence={result_a.evidence}")
    print(f"explanation={result_a.explanation}")
    print(f"cost=${result_a.cost_usd:.6f}  tokens_in={result_a.tokens_in}  tokens_out={result_a.tokens_out}")

    # --- Path B: plain retrieval (routing-independence check only) ---
    hr("STEP 3: Retrieval (plain, no rule fusion) - real, local, free")
    retrieved_b = retriever.query_and_rerank(ann.hypothesis_text)
    context_b = " ".join(r.chunk.text for r in retrieved_b)
    print(f"{len(retrieved_b)} chunks retrieved. Context ({len(context_b)} chars):")
    print(context_b)

    hr("STEP 4: classify() call B (plain context, for routing only) - REAL API CALL")
    print("Same system prompt as Step 2 (v6, unchanged). Real user message this call:")
    print(_build_user_message(context_b, ann.hypothesis_text))
    result_b = classify(context_b, ann.hypothesis_text, gateway, doc_id=DOC_ID, hypothesis_id=HYPOTHESIS_ID)
    print("\n--- REAL RESPONSE ---")
    print(f"label={result_b.label}  confidence={result_b.confidence}  evidence={result_b.evidence}")
    print(f"explanation={result_b.explanation}")
    print(f"cost=${result_b.cost_usd:.6f}  tokens_in={result_b.tokens_in}  tokens_out={result_b.tokens_out}")

    hr("STEP 5: Rule baseline + routing decision")
    rule_label = classify_by_keywords(HYPOTHESIS_ID, doc.text)
    print(f"Rule-based keyword label: {rule_label}")
    print(f"Plain classification (Step 4) label: {result_b.label}")
    agree = rule_label == result_b.label
    decision = route(self_confidence=result_a.confidence, rule_agrees=agree)
    print(f"Rule and plain classification agree: {agree}")
    print(f"ROUTING DECISION: {decision.route}")

    if decision.route != Route.REVIEW:
        hr("FINAL OUTPUT (ACCEPTed - no agent invoked)")
        print(f"label={result_a.label}  confidence={result_a.confidence}")
        print(f"evidence={result_a.evidence}")
        print(f"Correct vs gold ({ann.label}): {result_a.label == ann.label}")
        return 0

    # --- Agent loop, manually stepped through with the SAME real functions ---
    hr("STEP 6+: Selective agent loop - REAL API CALLS, one per step")
    print(f"Agent prompt file: {AGENT_PROMPT_PATH}")
    evidence_chunks = [r.chunk for r in retrieved_a]
    seen_calls = set()
    step_num = 0
    max_steps = settings.agent_max_steps

    while step_num < max_steps:
        step_num += 1
        hr(f"AGENT STEP {step_num}")
        print("--- SYSTEM PROMPT (sent to LLM, same file every step) ---")
        print(AGENT_PROMPT_PATH.read_text())
        user_message = (
            f'Requirement to classify:\n"{ann.hypothesis_text}"\n\n'
            f'Evidence gathered so far:\n"""\n{_format_evidence(evidence_chunks)}\n"""'
        )
        print("\n--- USER MESSAGE (sent to LLM this step) ---")
        print(user_message)

        decision_data, response = _decide_next_action(ann.hypothesis_text, evidence_chunks, gateway, AGENT_PROMPT_PATH)
        print("\n--- REAL RESPONSE ---")
        print(json.dumps(decision_data, indent=2))
        print(f"cost=${response.cost_usd:.6f}  tokens_in={response.tokens_in}  tokens_out={response.tokens_out}")

        if decision_data is None or decision_data.get("action") not in VALID_ACTIONS:
            print("\nInvalid/unparseable action - stopping.")
            break

        action = decision_data["action"]
        if action == "conclude":
            label = decision_data.get("label")
            hr("FINAL OUTPUT (agent concluded)")
            print(f"label={label}  confidence={decision_data.get('confidence')}")
            print(f"evidence={decision_data.get('evidence', [])}")
            print(f"explanation={decision_data.get('explanation', '')}")
            print(f"Correct vs gold ({ann.label}): {label == ann.label}")
            return 0

        query = str(decision_data.get("query", ""))
        call_key = (action, query)
        if call_key in seen_calls:
            print(f"\nDuplicate call to {action!r} with same query - stopping (duplicate_loop).")
            break
        seen_calls.add(call_key)

        new_chunks = _execute_tool(action, query, int(decision_data.get("chunk_index", 0) or 0),
                                    retriever, evidence_chunks)
        added = [c for c in new_chunks if c not in evidence_chunks]
        evidence_chunks.extend(added)
        print(f"\nTool executed: {action}(query={query!r}) -> {len(added)} new chunk(s) added")
        for c in added:
            print(f"  NEW CHUNK: {c.text.strip()[:200]}")

    hr("Step limit reached without a conclusion - would fall back to plain classify() over everything gathered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
