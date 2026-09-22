#!/usr/bin/env python3
"""
Dataset validation gate (WBS T006, experiments A01-A07).

Runs all Section 8 "Dataset and Harness Experiments" checks against the
downloaded ContractNLI splits and writes a single consolidated report to
data/validation_report.json.  This is a go/no-go gate: everything downstream
(chunking, retrieval, classification) depends on this data being clean and
the splits being leakage-free.

Usage:
    python scripts/validate_dataset.py
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings
from pipeline.parser import check_split_leakage, load_all_splits

VALID_LABELS = {"Entailment", "Contradiction", "NotMentioned"}


def a01_schema_validation(data_dir: Path, splits: dict) -> dict:
    """Are all NDAs parseable? Compare raw doc count vs successfully parsed count."""
    result = {}
    total_raw = 0
    total_parsed = 0
    for split_name in ("train", "dev", "test"):
        filepath = data_dir / f"{split_name}.json"
        if not filepath.exists():
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        raw_count = len(raw.get("documents", []))
        parsed_count = splits[split_name].num_documents if split_name in splits else 0
        total_raw += raw_count
        total_parsed += parsed_count
        result[split_name] = {"raw_count": raw_count, "parsed_count": parsed_count}
    result["total_raw"] = total_raw
    result["total_parsed"] = total_parsed
    result["parse_success_rate"] = round(total_parsed / total_raw, 4) if total_raw else 0.0
    result["pass"] = result["parse_success_rate"] > 0.99
    return result


def a02_missing_corrupt(splits: dict) -> dict:
    """Any missing labels, empty documents?"""
    result = {}
    total_docs = 0
    total_corrupt = 0
    for split_name, dataset in splits.items():
        empty_text = 0
        no_annotations = 0
        for doc in dataset.documents:
            if not doc.text or not doc.text.strip():
                empty_text += 1
            if doc.num_annotations == 0:
                no_annotations += 1
        corrupt = empty_text + no_annotations
        total_docs += dataset.num_documents
        total_corrupt += corrupt
        result[split_name] = {
            "empty_text": empty_text,
            "no_annotations": no_annotations,
        }
    result["total_docs"] = total_docs
    result["total_corrupt"] = total_corrupt
    result["corrupt_rate"] = round(total_corrupt / total_docs, 4) if total_docs else 0.0
    result["pass"] = result["corrupt_rate"] < 0.01
    return result


def a03_duplicate_detection(splits: dict) -> dict:
    """Any duplicate NDAs (by exact text hash)?"""
    hash_to_docs: dict[str, list[str]] = {}
    total_docs = 0
    for split_name, dataset in splits.items():
        for doc in dataset.documents:
            h = hashlib.sha256(doc.text.encode("utf-8")).hexdigest()
            hash_to_docs.setdefault(h, []).append(f"{split_name}/{doc.doc_id}")
            total_docs += 1

    duplicate_groups = [ids for ids in hash_to_docs.values() if len(ids) > 1]
    duplicate_doc_count = sum(len(ids) for ids in duplicate_groups)

    return {
        "total_docs": total_docs,
        "duplicate_groups": len(duplicate_groups),
        "duplicate_doc_count": duplicate_doc_count,
        "duplicate_rate": round(duplicate_doc_count / total_docs, 4) if total_docs else 0.0,
        "example_groups": duplicate_groups[:5],
        "pass": (duplicate_doc_count / total_docs if total_docs else 0.0) < 0.02,
    }


def a04_leakage_test(splits: dict) -> dict:
    """Do any NDAs appear in both dev and test (or any two splits)?"""
    leaked = check_split_leakage(splits)
    return {
        "leaked_doc_count": len(leaked),
        "leaked_doc_ids": leaked[:20],
        "pass": len(leaked) == 0,
    }


def a05_label_distribution(splits: dict) -> dict:
    """What is the class balance, per split and overall?"""
    result = {}
    overall = {"Entailment": 0, "Contradiction": 0, "NotMentioned": 0}
    for split_name, dataset in splits.items():
        dist = dataset.label_distribution()
        result[split_name] = dist
        for label, count in dist.items():
            overall[label] += count
    total = sum(overall.values())
    result["overall"] = overall
    result["overall_proportions"] = (
        {k: round(v / total, 4) for k, v in overall.items()} if total else {}
    )
    return result


def a06_evidence_span_validation(splits: dict) -> dict:
    """Are gold evidence spans valid text ranges?"""
    total_spans = 0
    invalid_spans = 0
    examples: list[str] = []
    for split_name, dataset in splits.items():
        for doc in dataset.documents:
            for start, end in doc.spans:
                total_spans += 1
                valid = 0 <= start < end <= len(doc.text)
                if not valid:
                    invalid_spans += 1
                    if len(examples) < 5:
                        examples.append(f"{split_name}/{doc.doc_id}: ({start}, {end})")
    return {
        "total_spans": total_spans,
        "invalid_spans": invalid_spans,
        "invalid_rate": round(invalid_spans / total_spans, 4) if total_spans else 0.0,
        "examples": examples,
        "pass": (invalid_spans / total_spans if total_spans else 0.0) < 0.01,
    }


def a07_token_length_analysis(splits: dict) -> dict:
    """How many tokens per NDA (min/max/mean/median/p95)?"""
    encoding = tiktoken.get_encoding("cl100k_base")
    result = {}
    all_lengths: list[int] = []
    for split_name, dataset in splits.items():
        lengths = [len(encoding.encode(doc.text)) for doc in dataset.documents]
        all_lengths.extend(lengths)
        if lengths:
            sorted_lengths = sorted(lengths)
            p95_idx = min(int(len(sorted_lengths) * 0.95), len(sorted_lengths) - 1)
            result[split_name] = {
                "min": min(lengths),
                "max": max(lengths),
                "mean": round(statistics.mean(lengths), 1),
                "median": statistics.median(lengths),
                "p95": sorted_lengths[p95_idx],
            }
    if all_lengths:
        sorted_all = sorted(all_lengths)
        p95_idx = min(int(len(sorted_all) * 0.95), len(sorted_all) - 1)
        result["overall"] = {
            "min": min(all_lengths),
            "max": max(all_lengths),
            "mean": round(statistics.mean(all_lengths), 1),
            "median": statistics.median(all_lengths),
            "p95": sorted_all[p95_idx],
        }
    return result


def main() -> int:
    data_dir = settings.data_path
    print(f"Loading ContractNLI splits from {data_dir} ...")
    splits = load_all_splits(data_dir)

    if not splits:
        print(f"ERROR: no splits found in {data_dir}. Run scripts/download_data.sh first.")
        return 1

    print(f"Loaded splits: {list(splits.keys())}")
    print("Running validation checks A01-A07 ...")

    report = {
        "A01_schema_validation": a01_schema_validation(data_dir, splits),
        "A02_missing_corrupt": a02_missing_corrupt(splits),
        "A03_duplicate_detection": a03_duplicate_detection(splits),
        "A04_leakage_test": a04_leakage_test(splits),
        "A05_label_distribution": a05_label_distribution(splits),
        "A06_evidence_span_validation": a06_evidence_span_validation(splits),
        "A07_token_length_analysis": a07_token_length_analysis(splits),
    }

    gate_checks = {
        "A01": report["A01_schema_validation"]["pass"],
        "A02": report["A02_missing_corrupt"]["pass"],
        "A03": report["A03_duplicate_detection"]["pass"],
        "A04": report["A04_leakage_test"]["pass"],
        "A06": report["A06_evidence_span_validation"]["pass"],
    }
    report["overall_pass"] = all(gate_checks.values())
    report["gate_checks"] = gate_checks

    out_path = Path("data/validation_report.json")
    out_path.write_text(json.dumps(report, indent=2))

    print()
    print("=" * 50)
    print("Validation Report Summary")
    print("=" * 50)
    for check_id, passed in gate_checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {check_id}")
    print()
    print(f"Overall: {'PASS' if report['overall_pass'] else 'FAIL'}")
    print(f"Report written to: {out_path}")

    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
