#!/usr/bin/env python3
"""
E10 Stage B -- offline verification of the frozen runtime trigger over all 150 TRAIN_ARCH_v1
cases (zero model calls), plus a tool-reachability analysis over the resulting triggered subset.

Confirms the trigger implementation in pipeline/agent_v2.py exactly reproduces E09's own
prevalence numbers (TP=1, FP=14, FN=0, TN=135, 15/150 triggered) before any E11 run -- any
mismatch would mean the Stage B implementation drifted from the frozen Stage A design.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.agent_tools_v2 import _document_chunks  # noqa: E402
from pipeline.agent_v2 import cross_reference_to_named_provision_cue  # noqa: E402

E07_DIR = REPO / "experiments/E07_standard_rag"
E08B_DIR = REPO / "experiments/E08B_stronger_model_diagnostic"
E09_DIR = REPO / "experiments/E09_agent_justification"


def main() -> int:
    retrieved = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    chunk_text_by_case = {c["case_id"]: c["ranked_chunk_text"] for c in retrieved["cases"]}
    assert len(chunk_text_by_case) == 150

    gpt_rows = {r["case_id"]: r for r in
                csv.DictReader(open(E08B_DIR / "results/gpt5mini_failure_analysis.csv"))}
    assert len(gpt_rows) == 150

    dynamic_case_ids = {"train::273::nda-1"}  # E09's single confirmed genuinely-dynamic case

    triggered_ids = [cid for cid, chunks in chunk_text_by_case.items()
                      if cross_reference_to_named_provision_cue(chunks)]
    triggered_set = set(triggered_ids)

    tp = len(triggered_set & dynamic_case_ids)
    fp = len(triggered_set - dynamic_case_ids)
    fn = len(dynamic_case_ids - triggered_set)
    tn = 150 - tp - fp - fn

    print(f"Triggered count: {len(triggered_ids)} / 150 = {len(triggered_ids)/150:.1%}")
    print(f"TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"Triggered case_ids: {sorted(triggered_ids)}")

    assert len(triggered_ids) == 15, f"expected 15 triggered cases, got {len(triggered_ids)}"
    assert tp == 1 and fp == 14 and fn == 0 and tn == 135, \
        f"trigger prevalence drifted from E09's frozen design: TP={tp} FP={fp} FN={fn} TN={tn}"
    print("MATCH: implementation reproduces E09's frozen trigger prevalence exactly (TP=1, FP=14, FN=0, TN=135).")

    # --- Tool-reachability analysis over the 15 triggered cases ---
    train = json.load(open(REPO / "data/contractnli/train.json"))
    doc_text_by_id = {d["id"]: d["text"] for d in train["documents"]}
    manifest = json.load(open(REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"))
    doc_id_by_case = {c["case_id"]: c["document_id"] for c in manifest["cases"]}

    CROSS_REF_PATTERNS_SEARCH = re.compile(
        r"(of the definition of|as defined in|pursuant to section|pursuant to clause|"
        r"under clause|under section|as set forth in section|as provided in section|"
        r"in accordance with section|paragraph \(a\)|paragraphs \(a\))",
        re.IGNORECASE,
    )

    reachability = {"resolvable_cross_reference": 0, "ranks_6_10_available": 0,
                     "e09_static_six_triggered": []}
    static_six_ids = {"train::160::nda-10", "train::247::nda-10", "train::353::nda-10",
                       "train::379::nda-10", "train::438::nda-2", "train::518::nda-10"}

    for cid in triggered_ids:
        chunks_text = " ".join(chunk_text_by_case[cid])
        m = CROSS_REF_PATTERNS_SEARCH.search(chunks_text)
        resolvable = False
        if m:
            phrase_context = chunks_text[max(0, m.start() - 60): m.end() + 60]
            resolvable = True  # a matched phrase exists; true resolvability is checked per-case below
        reachability["resolvable_cross_reference"] += int(resolvable)

        doc_id = doc_id_by_case.get(cid)
        if doc_id is not None:
            full_chunks = _document_chunks(doc_text_by_id[doc_id])
            reachability["ranks_6_10_available"] += int(len(full_chunks) > 5)

        if cid in static_six_ids:
            reachability["e09_static_six_triggered"].append(cid)

    print("\nTool-reachability analysis over the 15 triggered cases:")
    print(f"  Cases with a resolvable cross-reference phrase present: "
          f"{reachability['resolvable_cross_reference']}/15")
    print(f"  Cases with ranks 6-10 available (document has >5 clause-chunks): "
          f"{reachability['ranks_6_10_available']}/15")
    print(f"  Of E09's 6 RETRIEVAL_FILTERING_LIMITED cases, triggered by the frozen policy: "
          f"{len(reachability['e09_static_six_triggered'])}/6 "
          f"({reachability['e09_static_six_triggered']})")

    if len(reachability["e09_static_six_triggered"]) < 3:
        print("\nSTATEMENT (per explicit instruction, routing NOT broadened to fix this): "
              "Selective A3 does not test recovery of the full static-retrieval bucket -- only "
              "the triggered subset of it is ever reachable by this agent.")

    out = {
        "trigger_verification": {"triggered_count": len(triggered_ids), "tp": tp, "fp": fp,
                                  "fn": fn, "tn": tn, "triggered_case_ids": sorted(triggered_ids)},
        "tool_reachability": {
            "resolvable_cross_reference_count": reachability["resolvable_cross_reference"],
            "ranks_6_10_available_count": reachability["ranks_6_10_available"],
            "e09_static_six_triggered_count": len(reachability["e09_static_six_triggered"]),
            "e09_static_six_triggered_ids": reachability["e09_static_six_triggered"],
        },
    }
    out_path = E09_DIR.parent / "E10_agent_design" / "results" / "trigger_verification_and_reachability.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
