#!/usr/bin/env python3
"""
Pulls concrete, quotable exception/carve-out failure examples for the report
(docs/decisions.md ADR-011's "100% failure rate on exception/carve-out
reconciliation" finding), with the actual clause text and actual model
output for each - not just the aggregate failure rate.

Read-only. No LLM/API calls, no pipeline/ changes, no new experiment runs.

Note on data source (a real correction, not what was originally assumed):
`data/golden/negative_cases.json`'s documents are from the DEV split, while
T041's saved predictions are from the TEST split - by design, these two
sets have zero document overlap (verified directly - none of these doc_ids
appear in test.json). So these cases cannot be found in any T041 result
file; they were never part of T041 at all. The actual model output for
these specific cases lives in `data/golden_battery_pipeline_verification.json`
(scripts/run_golden_battery_cases.py's real run of Category 2 negative
cases against the current production pipeline) - that is the correct
source used here instead.

Usage:
    python scripts/extract_failure_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings
from pipeline.parser import parse_contractnli_file

NEGATIVE_CASES_PATH = Path("data/golden/negative_cases.json")
PIPELINE_VERIFICATION_PATH = Path("data/golden_battery_pipeline_verification.json")
OUTPUT_PATH = Path("results/final/carveout_examples.md")

# Case IDs tagged with the exception/carve-out pattern (docs/decisions.md ADR-011).
CARVEOUT_CASE_IDS = {"034", "038", "039", "040"}


def main() -> int:
    negative_cases = {c["case_id"]: c for c in json.loads(NEGATIVE_CASES_PATH.read_text())}
    verification = json.loads(PIPELINE_VERIFICATION_PATH.read_text())
    predicted_by_case = {
        r["case_id"]: r for r in verification["category_2_negative"]["results"]
    }

    dev = parse_contractnli_file(settings.data_path / "dev.json")
    doc_lookup = {d.doc_id: d for d, _ in dev.all_cases()}

    lines = [
        "# Exception/Carve-Out Failure Examples",
        "",
        "Concrete, quotable examples backing `docs/decisions.md` ADR-011's finding: every case",
        "in the golden/negative battery requiring reconciliation of an exception or carve-out",
        "clause against an apparent general rule failed (4/4). Source: `data/golden/",
        "negative_cases.json` (case selection, dev split) cross-referenced against",
        "`data/golden_battery_pipeline_verification.json` (the real, already-completed run of",
        "these cases against the current production pipeline - NOT T041, which never touches",
        "these dev-split documents at all; see this script's docstring for why).",
        "",
    ]

    n_found = 0
    for case_id in sorted(CARVEOUT_CASE_IDS):
        case = negative_cases.get(case_id)
        pred = predicted_by_case.get(case_id)
        if not case or not pred:
            lines.append(f"## Case {case_id}: NOT FOUND in one of the two source files - skipped")
            lines.append("")
            continue

        doc = doc_lookup.get(case["doc_id"])
        if doc is None:
            lines.append(f"## Case {case_id}: doc_id {case['doc_id']} not found in dev.json - skipped")
            lines.append("")
            continue

        ann = doc.annotations.get(case["hypothesis_id"])
        hypothesis_text = ann.hypothesis_text if ann else "(hypothesis text not found)"

        clause_texts = []
        for span_idx in case["gold_span_indices"]:
            if 0 <= span_idx < len(doc.spans):
                start, end = doc.spans[span_idx]
                clause_texts.append(doc.text[start:end].strip())

        n_found += 1
        lines.append(f"## Case {case_id} (doc {case['doc_id']}, hypothesis {case['hypothesis_id']})")
        lines.append("")
        lines.append(f"**Pattern**: {case['description']}")
        lines.append("")
        lines.append(f"**Hypothesis**: {hypothesis_text}")
        lines.append("")
        lines.append("**Actual clause text (gold evidence spans, verbatim from the real dev-split NDA)**:")
        for i, text in enumerate(clause_texts, 1):
            lines.append(f"> {i}. \"{text}\"")
        lines.append("")
        lines.append(f"**Gold label**: {case['gold_label']}")
        lines.append(f"**Model predicted instead**: {pred['predicted_label']}  "
                      f"(agent invoked: {pred.get('agent_used', 'unknown')})")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"Found and formatted {n_found}/{len(CARVEOUT_CASE_IDS)} cases.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines))
    print(f"Wrote {OUTPUT_PATH} ({n_found}/{len(CARVEOUT_CASE_IDS)} cases found)")
    print("No LLM/API calls were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
