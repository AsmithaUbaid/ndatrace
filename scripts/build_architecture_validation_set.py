#!/usr/bin/env python3
"""
Builds the untouched architecture-validation set (per the user's explicit
methodology, 2026-09-25 - see docs/decisions.md ADR-009's update and
docs/evaluation_protocol.md's "What's missing" section for why this exists).

This is a real, previously-missing gap: every architecture comparison this
project ever made (Rule/Full-context/RAG/RAG+agent, docs/decisions.md
ADR-007/ADR-008/ADR-009) used the same repeatedly-tuned 150-case dev sample.
This script selects a genuinely untouched batch of documents - never used in
the 150-case dev sample, prompt tuning, retrieval tuning, regression cases,
or agent experiments - to give the frozen architecture freeze one honest,
independent check before ever touching the official test set again.

Source pool: data/contractnli/train.json (423 documents). Verified in this
same run (not assumed) that:
  - train.json has zero doc-level overlap with dev.json or test.json
    (ContractNLI's own split design - checked directly, not trusted blindly).
  - train.json has never been referenced by any tuning/experiment script in
    this repository (grepped for "train.json"/"train_split" across
    scripts/, pipeline/, tests/ - the only real hits are pipeline/parser.py's
    generic split-name handling and scripts/validate_dataset.py's read-only
    structural validation, A01-A07 - neither selects cases or tunes anything).
  - zero overlap between any data/golden/*.json case file's doc_id and
    train.json's doc_ids.

Split at the DOCUMENT level, not individual cases (explicit instruction,
2026-09-25): selects N whole documents and includes ALL 17 of their
hypotheses, rather than cherry-picking scattered individual cases the way
the 150-case dev sample was built. This avoids a subtler version of the same
reuse problem - touching a little of many documents rather than none of some.

This script ONLY builds and verifies the manifest. It makes ZERO model/API
calls and does not run any architecture. See scripts/run_architecture_validation.py
for the (separately prepared, not-yet-run) frozen evaluation script that
will consume this manifest.

Usage:
    python scripts/build_architecture_validation_set.py [--n-docs 20] [--seed 99]
"""

from __future__ import annotations

import argparse
import glob
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings
from pipeline.parser import parse_contractnli_file

MANIFEST_PATH = Path("data/architecture_validation_manifest.json")


def touched_doc_ids() -> dict[str, set[str]]:
    """Every doc_id this project has ever used for tuning/regression/robustness,
    grouped by source, so the overlap report names exactly what was checked."""
    dev = parse_contractnli_file(settings.data_path / "dev.json")
    test = parse_contractnli_file(settings.data_path / "test.json")

    dev_ids = {d.doc_id for d, _ in dev.all_cases()}
    test_ids = {d.doc_id for d, _ in test.all_cases()}

    golden_ids: set[str] = set()
    for f in sorted(glob.glob("data/golden/*.json")):
        for case in json.load(open(f)):
            if isinstance(case, dict) and case.get("doc_id"):
                golden_ids.add(case["doc_id"])

    return {
        "dev.json (150-case dev sample + retrieval tuning + regression/robustness cases are all subsets of this)": dev_ids,
        "test.json (T041 official test - reserved separately, never for architecture validation)": test_ids,
        "data/golden/*.json case files (explicit doc_id field)": golden_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-docs", type=int, default=20,
                         help="Number of whole documents to select from train.json (default: 20, "
                              "matching ~340 cases at 17 hypotheses/doc - comparable scale to the "
                              "150-case dev sample, cheap given this project's measured per-case cost)")
    parser.add_argument("--seed", type=int, default=99,
                         help="Random seed for document selection (default: 99, deliberately "
                              "distinct from seed=42 used everywhere else in this project, so this "
                              "sample can never be confused with a re-derivation of the old one)")
    args = parser.parse_args()

    train = parse_contractnli_file(settings.data_path / "train.json")
    train_ids = {d.doc_id for d, _ in train.all_cases()}
    print(f"train.json: {train.num_documents} documents, {len(train.all_cases())} total cases "
          f"(expected {train.num_documents} x 17 = {train.num_documents * 17})")

    # --- Verify zero overlap (do not assume - check) ---
    touched = touched_doc_ids()
    print("\n=== Overlap verification (train.json vs. every touched source) ===")
    any_overlap = False
    for name, ids in touched.items():
        overlap = train_ids & ids
        status = "OK - zero overlap" if not overlap else f"*** OVERLAP: {sorted(overlap)} ***"
        print(f"  {name}: {len(ids)} doc_ids -> {status}")
        if overlap:
            any_overlap = True
    if any_overlap:
        print("\nABORTING: overlap detected - refusing to build a manifest that isn't genuinely "
              "untouched. Investigate before re-running.")
        return 1
    print("\nConfirmed: train.json is disjoint from every dev/test/golden-case doc_id set checked.")

    # --- Select N whole documents (document-level split, not individual cases) ---
    rng = random.Random(args.seed)
    all_train_docs = sorted(train_ids)  # sorted first for reproducibility, then shuffled by seed
    selected_doc_ids = sorted(rng.sample(all_train_docs, args.n_docs))

    doc_lookup = {d.doc_id: d for d, _ in train.all_cases()}
    manifest_cases = []
    label_counts = Counter()
    for doc_id in selected_doc_ids:
        doc = doc_lookup[doc_id]
        for hyp_id, ann in doc.annotations.items():
            manifest_cases.append({
                "doc_id": doc.doc_id,
                "hypothesis_id": ann.hypothesis_id,
                "hypothesis_text": ann.hypothesis_text,
                "gold_label": ann.label,
                "gold_span_indices": [s.span_index for s in ann.evidence_spans],
            })
            label_counts[ann.label] += 1

    print(f"\n=== Selected {args.n_docs} untouched documents (seed={args.seed}) ===")
    print(f"doc_ids: {selected_doc_ids}")
    print(f"Total cases: {len(manifest_cases)} (all 17 hypotheses per document, no per-case cherry-picking)")
    print(f"Realized label distribution: {dict(label_counts)} "
          f"({ {k: f'{v/len(manifest_cases):.1%}' for k, v in label_counts.items()} })")
    print("(Not force-stratified - this is plain random document sampling, which is the correct, "
          "unbiased way to build an untouched validation set. The realized distribution is reported "
          "as-is, not adjusted to match any target.)")

    manifest = {
        "purpose": "Untouched architecture-validation set - never used in the 150-case dev sample, "
                   "prompt tuning, retrieval tuning, regression cases, or agent experiments. "
                   "See docs/evaluation_protocol.md and docs/decisions.md ADR-009's 2026-09-25 update.",
        "source_split": "train.json",
        "selection_method": "plain random sample of whole documents (document-level, not individual "
                             "cases), seed=99, deliberately distinct from seed=42 used elsewhere",
        "n_documents": args.n_docs,
        "n_cases": len(manifest_cases),
        "doc_ids": selected_doc_ids,
        "label_distribution": dict(label_counts),
        "overlap_verification": {
            name.split(" (")[0]: len(ids) for name, ids in touched.items()
        },
        "overlap_verification_result": "zero overlap confirmed against dev.json, test.json, and every data/golden/*.json case file",
        "cases": manifest_cases,
    }

    MANIFEST_PATH.parent.mkdir(exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {MANIFEST_PATH} ({len(manifest_cases)} cases across {args.n_docs} documents).")
    print("\nNo model or API calls were made. Nothing has been run yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
