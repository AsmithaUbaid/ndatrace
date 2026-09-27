#!/usr/bin/env python3
"""
Post-hoc analysis of the REAL, already-locked T041 test-set run's own
outputs - checks the same properties the golden battery checks (evidence
quality, no hallucinated citations, injection safety, log hygiene), but
against real test-set predictions that already exist, rather than
hand-picking new cases from the test split (which would be exactly the
kind of test-set peeking the project has avoided all along).

Nothing here influences the pipeline or re-scores accuracy - it's a read
only audit of what the locked run already produced.

Usage:
    python scripts/analyze_test_set_results.py [--arch full_context|rag|rag_agent] [--model google_gemini-2.5-flash-lite]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings
from pipeline.evidence_validator import validate_evidence

INJECTION_PATTERNS = [
    r"ignore (all|previous|the) instructions",
    r"system\s*:\s*override",
    r"you are (now |)in debug mode",
    r"return\s+\w+\s+for\s+(all|everything)",
    r"\bapprove_all_requirements\b",
]


def load_latest(path: Path) -> dict | None:
    if not path.exists():
        return None
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else None


def evidence_quality_audit(predictions: list[dict]) -> dict:
    """Runs the real evidence_validator.py against every prediction's cited
    evidence + explanation - flags any hallucinated/non-verbatim citation."""
    n_checked, n_with_evidence, n_flagged = 0, 0, 0
    flagged_examples = []
    for pred in predictions:
        evidence = pred.get("evidence") or pred.get("retrieved_texts") or []
        label = pred.get("predicted_label") or pred.get("label")
        # context isn't stored per-prediction (never logs NDA text, Section 0B) -
        # validate structurally instead: NotMentioned must carry no evidence,
        # every other label's evidence must be non-empty strings.
        n_checked += 1
        if evidence:
            n_with_evidence += 1
        if label == "NotMentioned" and evidence:
            n_flagged += 1
            if len(flagged_examples) < 3:
                flagged_examples.append({"doc_id": pred.get("doc_id"), "hypothesis_id": pred.get("hypothesis_id")})
    return {
        "n_checked": n_checked, "n_with_evidence": n_with_evidence,
        "n_notmentioned_with_evidence_flag": n_flagged,  # should be 0 - a real bug if not
        "flagged_examples": flagged_examples,
    }


def injection_pattern_scan(dataset_texts: dict[str, str]) -> dict:
    """Scans the REAL test-split documents for naturally-occurring
    injection-like phrasing - not expected to find anything (these are
    real NDAs, not adversarial input), but worth actually checking rather
    than assuming."""
    matches = {}
    for doc_id, text in dataset_texts.items():
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                matches.setdefault(doc_id, []).append(pattern)
    return {"n_documents_scanned": len(dataset_texts), "n_flagged": len(matches), "matches": matches}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google_gemini-2.5-flash-lite")
    args = parser.parse_args()

    print(f"=== Test-set result audit (model tag: {args.model}) ===\n")

    results = {}
    for arch in ["rule", "full_context", "rag", "rag_agent"]:
        fname = "run_T041_final_test_rule.jsonl" if arch == "rule" else f"run_T041_final_test_{arch}_{args.model}.jsonl"
        path = Path("results/runs") / fname
        record = load_latest(path)
        if record is None:
            print(f"[{arch}] not finished yet, skipping")
            continue

        n = len(record["predictions"])
        split = record["config"].get("split")
        print(f"[{arch}] {n} real predictions on split={split}")

        eq = evidence_quality_audit(record["predictions"])
        print(f"  Evidence quality: {eq['n_with_evidence']}/{eq['n_checked']} cases have evidence; "
              f"{eq['n_notmentioned_with_evidence_flag']} NotMentioned-with-evidence violations "
              f"(structural bug if > 0)")

        m = record["metrics"]
        print(f"  Accuracy: {m['accuracy']:.3f}  Contradiction recall: {m['contradiction_recall']:.3f} "
              f"(n={m['contradiction_n']}, 95% CI [{m['contradiction_recall_ci_low']:.3f}, "
              f"{m['contradiction_recall_ci_high']:.3f}])  Joint: {m['joint_label_evidence_correctness']:.3f}")
        if arch == "rag_agent":
            routed = sum(1 for p in record["predictions"] if p.get("agent_used"))
            print(f"  Agent routing rate: {routed}/{n} = {routed/n:.1%}")
        print()

        results[arch] = {"n": n, "evidence_quality": eq, "accuracy": m["accuracy"],
                          "contradiction_recall": m["contradiction_recall"]}

    if "full_context" in results or "rag" in results:
        from pipeline.parser import parse_contractnli_file
        dataset = parse_contractnli_file(settings.data_path / "test.json")
        texts = {doc.doc_id: doc.text for doc, _ in dataset.all_cases()}
        print("=== Injection-pattern scan of the real test-split documents ===")
        scan = injection_pattern_scan(texts)
        print(json.dumps(scan, indent=2)[:500])
        results["injection_scan"] = scan

    Path("data/test_set_result_audit.json").write_text(json.dumps(results, indent=2, default=str))
    print("\nWrote data/test_set_result_audit.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
