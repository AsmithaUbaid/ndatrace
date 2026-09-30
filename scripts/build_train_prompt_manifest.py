#!/usr/bin/env python3
"""
Builds TRAIN_PROMPT_v1 -- the frozen E03 prompt-selection manifest (reconstruction-v2).

Deterministic, document-diverse, class-balanced diagnostic sample from official TRAIN only
(docs/evaluation_protocol.md Part 1 Role A). Generated ONCE, before any prompt result exists,
per docs/experiment_protocol.md's manifest-generation rule.

Unlike TRAIN_ORACLE_v1, this manifest carries the FULL NDA document text as context (not gold
evidence) -- E03 tests classification prompts under a full-context condition, decoupled from
both Oracle's perfect-evidence condition and from retrieval (no retrieval config has been
frozen for reconstruction-v2 yet, so using retrieved context here would smuggle in an
un-scrutinized retrieval decision).

Local-only: reads data/contractnli/train.json, makes zero model/API calls.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED = 500  # distinct from every other project seed (42, 99, 123, 300)
TARGET_PER_CLASS = 50
MAX_CASES_PER_DOC_PER_CLASS = 2
OUT_PATH = REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1.json"


def build_manifest() -> dict:
    with open(REPO / "data/contractnli/train.json") as f:
        train = json.load(f)

    hyp_text = {k: v["hypothesis"] for k, v in train["labels"].items()}
    doc_lookup = {doc["id"]: doc for doc in train["documents"]}

    cases_by_class: dict[str, list[tuple]] = defaultdict(list)
    for doc in train["documents"]:
        doc_id = doc["id"]
        for hyp_id, ann in doc["annotation_sets"][0]["annotations"].items():
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
            "context_text": doc["text"],  # FULL NDA document text -- not gold evidence
        })
        all_docs_used.add(doc_id)

    manifest = {
        "manifest_id": "TRAIN_PROMPT_v1",
        "source_split": "train",
        "seed": SEED,
        "context_condition": "full_context_nda_text",
        "sampling_algorithm": (
            "Deterministic, document-diverse, class-balanced diagnostic sample. Same "
            "algorithm as TRAIN_ORACLE_v1 (scripts/build_train_oracle_manifest.py): for each "
            "class, group TRAIN cases by document, sort then shuffle documents with "
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
