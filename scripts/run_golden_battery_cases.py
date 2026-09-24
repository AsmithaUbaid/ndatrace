#!/usr/bin/env python3
"""
Runs Category 1 (golden_cases.json, 30 ordinary cases) and Category 2
(negative_cases.json, 15 wrong-behavior-catching cases) through the REAL,
CURRENT production pipeline (pipeline/orchestrator.py's review_requirement,
T031 architecture, current default prompt) - found missing entirely
during a 2026-09-24 plan-vs-reality audit.

Both case files were only ever built as case SELECTIONS (real dev-split
documents + gold labels chosen for a qualitative property, e.g. "buried
in sub-clause") - scripts/build_golden_cases.py and
scripts/build_negative_cases.py both make ZERO classify()/run_agent()
calls. Nobody had ever actually run the pipeline against these specific
45 cases and checked the real predictions against gold, at any point in
the project, on any pipeline version.

Real cost: 45 cases through the current pipeline, ~$0.01-0.02 (most
route ACCEPT with 2 classify calls each; some may escalate to the agent).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings
from pipeline.model_gateway import ModelError, ModelGateway
from pipeline.orchestrator import review_requirement
from pipeline.parser import parse_contractnli_file
from pipeline.retriever import Retriever


def run_case_file(path: str, dataset, gateway: ModelGateway) -> dict:
    cases = json.loads(Path(path).read_text())
    retrievers: dict[str, Retriever] = {}
    results = []
    n_correct = 0

    for case in cases:
        doc = dataset.get_document(case["doc_id"])
        if doc is None:
            results.append({**case, "error": f"doc_id {case['doc_id']} not found in dev split"})
            continue
        ann = doc.annotations.get(case["hypothesis_id"])
        hyp_text = ann.hypothesis_text if ann else None
        if hyp_text is None:
            results.append({**case, "error": f"hypothesis {case['hypothesis_id']} not found for doc"})
            continue

        if doc.doc_id not in retrievers:
            retrievers[doc.doc_id] = Retriever(doc.text, chunk_method="sentence")

        try:
            outcome = review_requirement(doc.text, case["hypothesis_id"], hyp_text, gateway,
                                          retriever=retrievers[doc.doc_id], doc_id=doc.doc_id)
            correct = outcome.label == case["gold_label"]
            n_correct += correct
            results.append({
                "case_id": case["case_id"], "doc_id": case["doc_id"], "hypothesis_id": case["hypothesis_id"],
                "gold_label": case["gold_label"], "predicted_label": outcome.label, "correct": correct,
                "agent_used": outcome.agent_used, "description": case.get("description", ""),
            })
            mark = "OK" if correct else "X "
            print(f"  {mark} {case['case_id']}: gold={case['gold_label']} pred={outcome.label} "
                  f"({case.get('description', '')[:50]})")
        except ModelError as e:
            results.append({**case, "error": str(e)})

    n_scored = sum(1 for r in results if "error" not in r)
    return {
        "file": path, "n_cases": len(cases), "n_scored": n_scored,
        "n_correct": n_correct, "accuracy": round(n_correct / n_scored, 3) if n_scored else 0.0,
        "results": results,
    }


def main() -> int:
    dataset = parse_contractnli_file(settings.data_path / "dev.json")
    try:
        gateway = ModelGateway()
    except ModelError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"Model: {gateway.model}\n")

    print("=== Category 1: golden_cases.json (30 ordinary cases) ===")
    cat1 = run_case_file("data/golden/golden_cases.json", dataset, gateway)
    print(f"\nAccuracy: {cat1['n_correct']}/{cat1['n_scored']} = {cat1['accuracy']:.1%}\n")

    print("=== Category 2: negative_cases.json (15 wrong-behavior-catching cases) ===")
    cat2 = run_case_file("data/golden/negative_cases.json", dataset, gateway)
    print(f"\nAccuracy: {cat2['n_correct']}/{cat2['n_scored']} = {cat2['accuracy']:.1%}\n")

    Path("data/golden_battery_pipeline_verification.json").write_text(
        json.dumps({"category_1_golden": cat1, "category_2_negative": cat2}, indent=2)
    )
    print("Wrote data/golden_battery_pipeline_verification.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
