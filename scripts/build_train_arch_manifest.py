#!/usr/bin/env python3
"""
Builds TRAIN_ARCH_v1 -- a FRESH, deterministic, class-balanced TRAIN manifest for the matched
E05 (full-context) vs. E07 (standard RAG) architecture comparison.

Why a fresh manifest instead of reusing TRAIN_PROMPT_v1 (E03's 150-case set): E03 evaluated
P0/P1/P2 on TRAIN_PROMPT_v1 and SELECTED classification_prompt_v1 (= P0) based on its accuracy/
Contradiction-Recall/Macro-F1 on exactly that population. Reusing the same 150 cases for the
architecture comparison the selected prompt now feeds into would mean the prompt was chosen to
do well on precisely the population being used to judge architecture, a real (if likely mild,
given P0's decisive margin) selection-bias exposure. A fresh, disjoint set avoids the question
entirely rather than requiring a judgment call about how much it matters -- reconstruction-v2's
own culture (E00/E01/E03/E04) prefers disclosure-and-avoid over disclosure-and-hope-it's-fine
when avoiding is this cheap.

Identical sampling algorithm to scripts/build_train_prompt_manifest.py (TRAIN_PROMPT_v1) and
scripts/build_train_oracle_manifest.py (TRAIN_ORACLE_v1): deterministic, document-diverse,
class-balanced. Only the seed changes (700 -- distinct from every prior project seed: 42, 99,
123, 300, 500). Verifies zero case_id overlap with TRAIN_PROMPT_v1 before writing.

context_text carries the FULL NDA document text (same field E03's TRAIN_PROMPT_v1 already used)
-- E05 uses it directly as full-context input; E07 will build retrieval_v1 context from the
same case_id/document_id/hypothesis_id triples, exactly as E03's
generate_e03_retrieved_context.py did for TRAIN_PROMPT_v1.

Local-only, deterministic, zero model/API calls.
"""

from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SEED = 700
TARGET_PER_CLASS = 50
MAX_CASES_PER_DOC_PER_CLASS = 2
OUT_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
TRAIN_PROMPT_V1_PATH = REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1.json"


def build_manifest() -> dict:
    with open(REPO / "data/contractnli/train.json") as f:
        train = json.load(f)
    with open(TRAIN_PROMPT_V1_PATH) as f:
        excluded_case_ids = {c["case_id"] for c in json.load(f)["cases"]}

    hyp_text = {k: v["hypothesis"] for k, v in train["labels"].items()}
    doc_lookup = {doc["id"]: doc for doc in train["documents"]}

    # Exclude every TRAIN_PROMPT_v1 case from the candidate pool BEFORE sampling --
    # disjointness by construction, not by hoping a given seed happens to avoid overlap.
    cases_by_class: dict[str, list[tuple]] = defaultdict(list)
    for doc in train["documents"]:
        doc_id = doc["id"]
        for hyp_id, ann in doc["annotation_sets"][0]["annotations"].items():
            if f"train::{doc_id}::{hyp_id}" in excluded_case_ids:
                continue
            cases_by_class[ann["choice"]].append((doc_id, hyp_id))

    rng = random.Random(SEED)
    selected_cases = []
    per_class_doc_counts = {}
    per_class_case_counts = {}

    for cls in ("Entailment", "Contradiction", "NotMentioned"):
        pool = cases_by_class[cls]
        by_doc: dict[int, list[str]] = defaultdict(list)
        for doc_id, hyp_id in pool:
            by_doc[doc_id].append(hyp_id)
        for doc_id in by_doc:
            by_doc[doc_id].sort()

        doc_ids = sorted(by_doc.keys())
        rng.shuffle(doc_ids)

        chosen = []
        docs_used = set()
        for doc_id in doc_ids:
            if len(chosen) >= TARGET_PER_CLASS:
                break
            for hyp_id in by_doc[doc_id][:MAX_CASES_PER_DOC_PER_CLASS]:
                if len(chosen) >= TARGET_PER_CLASS:
                    break
                chosen.append((doc_id, hyp_id, cls))
                docs_used.add(doc_id)

        per_class_case_counts[cls] = len(chosen)
        per_class_doc_counts[cls] = len(docs_used)
        selected_cases.extend(chosen)

    selected_cases.sort(key=lambda c: (c[2], c[0], c[1]))

    records = []
    all_docs_used = set()
    for doc_id, hyp_id, cls in selected_cases:
        doc = doc_lookup[doc_id]
        records.append({
            "case_id": f"train::{doc_id}::{hyp_id}",
            "split": "train",
            "document_id": doc_id,
            "hypothesis_id": hyp_id,
            "hypothesis_text": hyp_text[hyp_id],
            "gold_label": cls,
            "context_text": doc["text"],  # FULL NDA document text
        })
        all_docs_used.add(doc_id)

    # Verify zero overlap with TRAIN_PROMPT_v1 (E03's prompt-selection population) -- the
    # entire point of building a fresh manifest.
    with open(TRAIN_PROMPT_V1_PATH) as f:
        train_prompt_v1_ids = {c["case_id"] for c in json.load(f)["cases"]}
    new_ids = {r["case_id"] for r in records}
    overlap = train_prompt_v1_ids & new_ids
    if overlap:
        raise ValueError(f"TRAIN_ARCH_v1 overlaps TRAIN_PROMPT_v1 on {len(overlap)} cases -- "
                          f"seed {SEED} does not guarantee disjointness, refusing to write.")

    manifest = {
        "manifest_id": "TRAIN_ARCH_v1",
        "purpose": "matched E05 (full-context) vs. E07 (standard RAG) architecture comparison "
                   "-- deliberately disjoint from TRAIN_PROMPT_v1 (E03's prompt-selection set)",
        "source_split": "train",
        "seed": SEED,
        "context_condition": "full_context_nda_text",
        "sampling_algorithm": (
            "Identical algorithm to TRAIN_PROMPT_v1/TRAIN_ORACLE_v1: for each class, group "
            "TRAIN cases by document, sort then shuffle documents with "
            f"random.Random(seed={SEED}), take up to {MAX_CASES_PER_DOC_PER_CLASS} cases per "
            f"document until {TARGET_PER_CLASS} cases are selected for that class. Final "
            "ordering sorted by (class, document_id, hypothesis_id) for reproducibility."
        ),
        "max_cases_per_doc_per_class": MAX_CASES_PER_DOC_PER_CLASS,
        "target_per_class": TARGET_PER_CLASS,
        "total_cases": len(records),
        "per_class_case_counts": per_class_case_counts,
        "per_class_unique_document_counts": per_class_doc_counts,
        "total_unique_documents": len(all_docs_used),
        "verified_zero_overlap_with_TRAIN_PROMPT_v1": True,
        "cases": records,
    }
    return manifest


def main():
    manifest = build_manifest()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {OUT_PATH}")
    print("per_class_case_counts:", manifest["per_class_case_counts"])
    print("per_class_unique_document_counts:", manifest["per_class_unique_document_counts"])
    print("total_unique_documents:", manifest["total_unique_documents"])
    print("total_cases:", manifest["total_cases"])
    print("verified_zero_overlap_with_TRAIN_PROMPT_v1:", manifest["verified_zero_overlap_with_TRAIN_PROMPT_v1"])


if __name__ == "__main__":
    main()
