#!/usr/bin/env python3
"""
Builds TRAIN_ORACLE_v1 -- the frozen E01 Oracle manifest (WBS reconstruction-v2).

Deterministic, document-diverse, class-balanced diagnostic sample from official TRAIN only
(docs/evaluation_protocol.md Part 1 Role A). Generated ONCE, before any model result exists,
per docs/experiment_protocol.md's manifest-generation rule -- never resampled because a
result is inconvenient.

Local-only: reads data/contractnli/train.json, makes zero model/API calls.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED = 300  # distinct from seed=42 (historical dev sample), 99 (AV01), 123 (PVAL01)
TARGET_PER_CLASS = 100
MAX_CASES_PER_DOC_PER_CLASS = 2  # caps concentration -- no single NDA dominates a class
OUT_PATH = REPO / "experiments/E01_oracle/TRAIN_ORACLE_v1.json"


def build_manifest() -> dict:
    with open(REPO / "data/contractnli/train.json") as f:
        train = json.load(f)

    hyp_text = {k: v["hypothesis"] for k, v in train["labels"].items()}

    # doc_id -> list of (hypothesis_id, choice, gold_span_indices, doc index) per class
    cases_by_class: dict[str, list[tuple]] = defaultdict(list)
    doc_lookup = {doc["id"]: doc for doc in train["documents"]}

    for doc in train["documents"]:
        doc_id = doc["id"]
        for hyp_id, ann in doc["annotation_sets"][0]["annotations"].items():
            cases_by_class[ann["choice"]].append((doc_id, hyp_id, ann["spans"]))

    rng = random.Random(SEED)
    selected_cases = []
    per_class_doc_counts = {}
    per_class_case_counts = {}

    for cls in ("Entailment", "Contradiction", "NotMentioned"):
        pool = cases_by_class[cls]
        # Group by document, shuffle DOCUMENT order (not case order) for diversity,
        # then take up to MAX_CASES_PER_DOC_PER_CLASS cases per doc, in deterministic
        # (sorted) hypothesis order within a doc, until TARGET_PER_CLASS is reached.
        by_doc: dict[int, list[tuple]] = defaultdict(list)
        for doc_id, hyp_id, spans in pool:
            by_doc[doc_id].append((hyp_id, spans))
        for doc_id in by_doc:
            by_doc[doc_id].sort(key=lambda x: x[0])  # deterministic within-doc order

        doc_ids = sorted(by_doc.keys())  # sort first for reproducibility, then shuffle
        rng.shuffle(doc_ids)

        chosen = []
        docs_used = set()
        for doc_id in doc_ids:
            if len(chosen) >= TARGET_PER_CLASS:
                break
            take = by_doc[doc_id][:MAX_CASES_PER_DOC_PER_CLASS]
            for hyp_id, spans in take:
                if len(chosen) >= TARGET_PER_CLASS:
                    break
                chosen.append((doc_id, hyp_id, cls, spans))
                docs_used.add(doc_id)

        per_class_case_counts[cls] = len(chosen)
        per_class_doc_counts[cls] = len(docs_used)
        selected_cases.extend(chosen)

    # Final deterministic ordering: sorted by (class, doc_id, hypothesis_id), independent
    # of dict/shuffle iteration order, so the manifest is byte-for-byte reproducible.
    selected_cases.sort(key=lambda c: (c[2], c[0], c[1]))

    records = []
    all_docs_used = set()
    for doc_id, hyp_id, cls, spans in selected_cases:
        doc = doc_lookup[doc_id]
        evidence_text = " ".join(
            doc["text"][doc["spans"][i][0]:doc["spans"][i][1]] for i in spans
        ) if spans else ""
        records.append({
            "case_id": f"train::{doc_id}::{hyp_id}",
            "split": "train",
            "document_id": doc_id,
            "hypothesis_id": hyp_id,
            "hypothesis_text": hyp_text[hyp_id],
            "gold_label": cls,
            "gold_span_indices": spans,
            "gold_evidence_text": evidence_text,  # empty string for NotMentioned, by construction (E00 section 10)
        })
        all_docs_used.add(doc_id)

    manifest = {
        "manifest_id": "TRAIN_ORACLE_v1",
        "source_split": "train",
        "seed": SEED,
        "sampling_algorithm": (
            "Deterministic, document-diverse, class-balanced diagnostic sample. For each "
            "class (Entailment/Contradiction/NotMentioned): group TRAIN cases by document, "
            "sort documents by ID then shuffle with random.Random(SEED), take up to "
            f"{MAX_CASES_PER_DOC_PER_CLASS} cases per document (deterministic hypothesis-ID "
            f"order within a doc) walking the shuffled document order until {TARGET_PER_CLASS} "
            "cases are selected for that class. Final manifest ordering is sorted by "
            "(class, document_id, hypothesis_id), independent of shuffle iteration order, "
            "for byte-for-byte reproducibility."
        ),
        "max_cases_per_doc_per_class": MAX_CASES_PER_DOC_PER_CLASS,
        "target_per_class": TARGET_PER_CLASS,
        "total_cases": len(records),
        "per_class_case_counts": per_class_case_counts,
        "per_class_unique_document_counts": per_class_doc_counts,
        "total_unique_documents": len(all_docs_used),
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


if __name__ == "__main__":
    main()
