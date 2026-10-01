#!/usr/bin/env python3
"""E24: build the case manifest -- the 45 checked-in golden+negative cases, plus the 4
real (non-synthetic) evidence_quality cases, with real NDA text pulled from dev.json.

Zero model calls. All 49 cases are drawn from the project's existing, pre-registered case
files (data/golden/*.json) -- not newly selected or cherry-picked for this experiment.

injection_cases.json (11) and llm_behaviour_cases.json (7) are deliberately NOT included:
every entry in both files has doc_id/hypothesis_id == "synthetic" with no stored source
text, just a text description of an earlier ad hoc check -- there is nothing reproducible
to replay. agent_cases.json and confidence_cases.json are also excluded: both test features
(the selective agent, an automatic confidence gate) that are not part of the shipped
architecture (see docs/experiment_registry.md's E11/E15 entries).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "manifests" / "case_manifest.json"

GOLDEN = json.loads((ROOT / "data/golden/golden_cases.json").read_text())
NEGATIVE = json.loads((ROOT / "data/golden/negative_cases.json").read_text())
EVIDENCE_QUALITY = json.loads((ROOT / "data/golden/evidence_quality_cases.json").read_text())
DEV = json.loads((ROOT / "data/contractnli/dev.json").read_text())
DOCS = {str(d["id"]): d for d in DEV["documents"]}


def span_text(doc: dict, idx: int) -> str:
    start, end = doc["spans"][idx]
    return doc["text"][start:end]


def build_entry(case: dict, source_file: str, group: str) -> dict:
    doc = DOCS[str(case["doc_id"])]
    spans = case.get("gold_span_indices", [])
    return {
        "case_id": case["case_id"],
        "group": group,
        "source_file": source_file,
        "doc_id": case["doc_id"],
        "document_file_name": doc["file_name"],
        "hypothesis_id": case["hypothesis_id"],
        "hypothesis_text": DEV["labels"][case["hypothesis_id"]]["hypothesis"],
        "nda_text": doc["text"],
        "doc_spans": doc["spans"],
        "gold_label": case["gold_label"],
        "gold_span_indices": spans,
        "gold_evidence": [span_text(doc, i) for i in spans],
        "description": case.get("description", ""),
    }


def main() -> None:
    entries = (
        [build_entry(c, "golden_cases.json", "golden") for c in GOLDEN]
        + [build_entry(c, "negative_cases.json", "negative") for c in NEGATIVE]
        + [build_entry(c, "evidence_quality_cases.json", "evidence_quality") for c in EVIDENCE_QUALITY]
    )
    label_counts: dict[str, int] = {}
    for e in entries:
        label_counts[e["gold_label"]] = label_counts.get(e["gold_label"], 0) + 1

    manifest = {
        "manifest_id": "E24_targeted_evaluation_v1",
        "n_cases": len(entries),
        "label_counts": label_counts,
        "group_sizes": {"golden": len(GOLDEN), "negative": len(NEGATIVE), "evidence_quality": len(EVIDENCE_QUALITY)},
        "excluded": {
            "injection_cases.json (11)": "all entries are synthetic with no stored source text -- not replayable",
            "llm_behaviour_cases.json (7)": "all entries are synthetic with no stored source text -- not replayable",
            "agent_cases.json (7)": "tests the selective agent, not part of the shipped architecture (E11: rejected)",
            "confidence_cases.json (2)": "tests an automatic confidence gate, not part of the shipped architecture (E15: rejected)",
        },
        "source_split": "dev.json (same split every golden/negative/evidence_quality case was always drawn from)",
        "cases": entries,
    }
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT} ({len(entries)} cases, label_counts={label_counts})")


if __name__ == "__main__":
    main()
