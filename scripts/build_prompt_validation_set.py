#!/usr/bin/env python3
"""
Builds PVAL01 - the untouched prompt-validation set (2026-09-25).

Purpose: compare prompt versions v2 / v5 / v6 under ONE fixed architecture
(Full-context, chosen specifically to isolate reasoning quality from
retrieval luck) on documents no prompt-tuning decision has ever seen - the
150-case dev sample that drove v1-v6 was reused adaptively across every
prompt comparison so far (docs/evaluation_protocol.md's development-reuse
warning), so no prompt version has ever been checked against genuinely
independent data.

Source pool: data/contractnli/train.json (423 documents). This script
excludes every prior experiment pool - including AV01's 20 documents,
which is new relative to scripts/build_architecture_validation_set.py and
is exactly why that script is not reused unmodified here.

Split at the DOCUMENT level (whole NDAs), matching the AV01 manifest's
methodology (scripts/build_architecture_validation_set.py) - never
individual cases scattered across many documents.

MANIFEST + OVERLAP VERIFICATION ONLY. This script makes ZERO model/API
calls and does not compare prompt versions - see
scripts/run_prompt_validation.py (not yet written) for that, once this
manifest is reviewed.

Usage:
    python scripts/build_prompt_validation_set.py [--n-docs 26] [--seed 123]
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

MANIFEST_PATH = Path("data/prompt_validation_manifest.json")
AV01_MANIFEST_PATH = Path("data/architecture_validation_manifest.json")


def touched_doc_ids() -> dict[str, set[str]]:
    """Every doc_id any prior prompt/model/retrieval/architecture decision
    has ever been influenced by, grouped by source so the overlap report
    names exactly what was checked. Reconstructed from real saved files,
    not assumed."""
    dev = parse_contractnli_file(settings.data_path / "dev.json")
    test = parse_contractnli_file(settings.data_path / "test.json")

    dev_ids = {d.doc_id for d, _ in dev.all_cases()}
    test_ids = {d.doc_id for d, _ in test.all_cases()}

    golden_ids: set[str] = set()
    for f in sorted(glob.glob("data/golden/*.json")):
        for case in json.load(open(f)):
            if isinstance(case, dict) and case.get("doc_id"):
                golden_ids.add(case["doc_id"])

    av01_ids: set[str] = set()
    if AV01_MANIFEST_PATH.exists():
        av01_manifest = json.loads(AV01_MANIFEST_PATH.read_text())
        av01_ids = set(av01_manifest["doc_ids"])

    return {
        "150-case dev sample + full dev/retrieval-tuning pool (both are subsets of dev.json)": dev_ids,
        "data/golden/*.json (regression/robustness/agent-behaviour case files)": golden_ids,
        "AV01 architecture-validation documents": av01_ids,
        "official test split (test.json)": test_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-docs", type=int, default=26,
                         help="Number of whole documents to select from train.json (default: 26, "
                              "targeting ~400-500 cases at 17 hypotheses/doc)")
    parser.add_argument("--seed", type=int, default=123,
                         help="Random seed (default: 123 - distinct from seed=42 used for the dev "
                              "sample and seed=99 used for AV01, so this set can never be confused "
                              "with either)")
    args = parser.parse_args()

    train = parse_contractnli_file(settings.data_path / "train.json")
    train_ids = {d.doc_id for d, _ in train.all_cases()}
    print(f"train.json: {train.num_documents} documents, {len(train.all_cases())} total cases")

    # --- Verify overlap against every prior pool (do not assume) ---
    # AV01's documents are EXPECTED to be a subset of train.json (AV01 was itself built from
    # train.json) - that overlap is handled below by excluding those doc_ids from the sampling
    # pool, not an error. Every OTHER pool (dev.json-derived, golden cases, test.json) must show
    # genuinely zero overlap with train.json as a whole, since those splits are disjoint by
    # ContractNLI's own design - any overlap there would be a real, unexpected problem.
    touched = touched_doc_ids()
    print("\n=== Overlap verification (train.json vs. every touched source) ===")
    any_unexpected_overlap = False
    for name, ids in touched.items():
        overlap = train_ids & ids
        is_av01 = name.startswith("AV01")
        if is_av01:
            status = (f"EXPECTED - AV01 was built from train.json; these {len(overlap)} doc_ids "
                       "will be excluded from the sampling pool below")
        else:
            status = "OK - zero overlap" if not overlap else f"*** UNEXPECTED OVERLAP: {sorted(overlap)} ***"
            if overlap:
                any_unexpected_overlap = True
        print(f"  {name}: {len(ids)} doc_ids -> {status}")
    if any_unexpected_overlap:
        print("\nABORTING: unexpected overlap detected against train.json as a whole.")
        return 1
    print("\nConfirmed: train.json is disjoint from dev.json, golden/*.json, and test.json.")
    print("AV01's 20 documents (a real train.json subset) will be excluded from sampling next.")

    # --- Select N whole documents, excluding AV01's 20 explicitly (belt-and-braces: ---
    # --- train.json is already disjoint from AV01 by the check above, but AV01's docs ---
    # --- ARE drawn from train.json, so they must be excluded from the sampling pool too) ---
    av01_ids = touched["AV01 architecture-validation documents"]
    available_ids = sorted(train_ids - av01_ids)
    print(f"\nAvailable train.json documents after excluding AV01's {len(av01_ids)}: {len(available_ids)}")

    rng = random.Random(args.seed)
    selected_doc_ids = sorted(rng.sample(available_ids, args.n_docs))

    # Final, explicit re-check: selected set must not intersect AV01 or anything else.
    overlap_with_av01 = set(selected_doc_ids) & av01_ids
    assert not overlap_with_av01, f"Selection overlaps AV01: {overlap_with_av01}"

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
                "source_split": "train",
                "selection_seed": args.seed,
            })
            label_counts[ann.label] += 1

    print(f"\n=== Selected {args.n_docs} untouched documents (seed={args.seed}) ===")
    print(f"doc_ids: {selected_doc_ids}")
    print(f"Total cases: {len(manifest_cases)}")
    print(f"Realized label distribution: {dict(label_counts)} "
          f"({ {k: f'{v/len(manifest_cases):.1%}' for k, v in label_counts.items()} })")

    # --- Internal consistency checks ---
    keys = [(c["doc_id"], c["hypothesis_id"]) for c in manifest_cases]
    n_dupes = len(keys) - len(set(keys))
    all_in_train = all(c["doc_id"] in train_ids for c in manifest_cases)
    cases_per_doc = Counter(c["doc_id"] for c in manifest_cases)
    consistent_per_doc = all(n == 17 for n in cases_per_doc.values())
    all_have_gold = all(c["gold_label"] for c in manifest_cases)
    print(f"\n=== Internal consistency checks ===")
    print(f"  duplicate (doc_id, hypothesis_id) pairs: {n_dupes} -> {'PASS' if n_dupes == 0 else 'FAIL'}")
    print(f"  all doc_ids actually in train.json: {'PASS' if all_in_train else 'FAIL'}")
    print(f"  every selected doc contributes all 17 hypotheses (no partial docs): "
          f"{'PASS' if consistent_per_doc else 'FAIL'}")
    print(f"  every case has a gold label: {'PASS' if all_have_gold else 'FAIL'}")

    manifest = {
        "purpose": "PVAL01 - untouched prompt-validation set. Compares prompt versions v2/v5/v6 "
                   "under a FIXED architecture (Full-context) on documents no prompt-tuning "
                   "decision has ever seen. See docs/evaluation_protocol.md.",
        "source_split": "train.json",
        "selection_method": "plain random sample of whole documents (document-level, not "
                             "individual cases), excluding AV01's 20 documents from the candidate "
                             "pool before sampling",
        "selection_seed": args.seed,
        "n_documents": args.n_docs,
        "n_cases": len(manifest_cases),
        "doc_ids": selected_doc_ids,
        "label_distribution": dict(label_counts),
        "overlap_verification": {
            name.split(" (")[0]: len(ids) for name, ids in touched.items()
        },
        "overlap_verification_result": "zero overlap confirmed against dev.json (150-case dev "
                                        "sample + full retrieval-tuning pool), golden/*.json "
                                        "(regression/robustness/agent-behaviour cases), AV01's 20 "
                                        "architecture-validation documents, and test.json",
        "reproducibility": "random.Random(123).sample(sorted(train_doc_ids - av01_doc_ids), 26) "
                            "- deterministic given the same train.json and AV01 manifest",
        "cases": manifest_cases,
    }

    MANIFEST_PATH.parent.mkdir(exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {MANIFEST_PATH} ({len(manifest_cases)} cases across {args.n_docs} documents).")
    print("\nNo model or API calls were made. No prompt versions were compared. Nothing has been run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
