#!/usr/bin/env python3
"""
Smallest vertical slice (WBS T012): one NDA + one hypothesis -> classify
-> compare with gold. This is the project's first real proof-of-life
through the full stack (real document, real prompt, real model call, real
scoring) - no retrieval or chunking yet, just the full document text fed
directly to the classifier.

Acceptance (Section 15): correct label on at least one easy case.
Uses golden case 001 (easy entailment) from data/golden/golden_cases.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.classifier import classify
from pipeline.config import settings
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.parser import parse_contractnli_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", default="002",
        help="Golden case ID to run (default: 002 - a genuinely clean reverse-engineering "
             "entailment. Case 001's gold evidence turned out to be about export control "
             "compliance, essentially unrelated to its hypothesis - a heuristic-selection "
             "artifact, not a good easy case).",
    )
    args = parser.parse_args()

    golden_path = Path("data/golden/golden_cases.json")
    cases = json.loads(golden_path.read_text())
    case = next((c for c in cases if c["case_id"] == args.case), None)
    if case is None:
        print(f"ERROR: golden case {args.case} not found in data/golden/golden_cases.json")
        return 1

    print(f"Case {case['case_id']}: {case['description']}")
    print(f"  doc_id={case['doc_id']} hypothesis_id={case['hypothesis_id']} gold_label={case['gold_label']}")

    dataset = parse_contractnli_file(settings.data_path / "dev.json")
    doc = dataset.get_document(case["doc_id"])
    if doc is None:
        print(f"ERROR: document {case['doc_id']} not found in dev split")
        return 1

    hypothesis_text = doc.annotations[case["hypothesis_id"]].hypothesis_text
    print(f"  hypothesis: {hypothesis_text}")
    print(f"  document length: {len(doc.text)} chars")

    try:
        gateway = ModelGateway()
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1

    print("\nCalling model (full document text, no retrieval)...")
    result = classify(doc.text, hypothesis_text, gateway)

    print(f"\nPredicted label: {result.label} (confidence {result.confidence:.2f})")
    print(f"Gold label:      {case['gold_label']}")
    print(f"Evidence:        {result.evidence}")
    print(f"Explanation:     {result.explanation}")
    print(f"Valid JSON:      {result.valid_json}")
    print(f"Tokens in/out:   {result.tokens_in}/{result.tokens_out}")
    print(f"Cost:            ${result.cost_usd:.6f}")
    print(f"Latency:         {result.latency_ms:.0f} ms")

    correct = result.label == case["gold_label"]
    print(f"\n{'PASS' if correct else 'FAIL'}: prediction {'matches' if correct else 'does NOT match'} gold label")

    return 0 if correct else 1


if __name__ == "__main__":
    sys.exit(main())
