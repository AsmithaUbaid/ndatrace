#!/usr/bin/env python3
"""E15: freeze DEV_ROUTING_v1 (from the approved Stage A draft; NOT resampled) and build model-facing FULL-context + evaluator-only GOLD artifacts. Zero model calls."""
from __future__ import annotations
import glob, hashlib, json, sys
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(REPO))
from pipeline.parser import parse_contractnli_file  # noqa: E402
from scripts.run_oracle_experiment import stratified_sample  # noqa: E402

D = REPO / "experiments/E15_review_routing"
draft = json.load(open(D / "results/proposed_manifest_DEV_ROUTING_v1_DRAFT.json"))
dev = json.load(open(REPO / "data/contractnli/dev.json")); docs = {d["id"]: d for d in dev["documents"]}
e13 = {c["case_id"] for c in json.load(open(REPO / "experiments/E13_gpt_context_architecture/DEV_ARCH_v1.json"))["cases"]}
golden = {f"dev::{c['doc_id']}::{c['hypothesis_id']}" for f in glob.glob(str(REPO / "data/golden/*.json")) for c in json.load(open(f)) if str(c.get("doc_id", "")).isdigit() and "hypothesis_id" in c}
ds = parse_contractnli_file(REPO / "data/contractnli/dev.json")
s150 = {f"dev::{int(d.id if hasattr(d, 'id') else d.doc_id)}::{a.hypothesis_id}" for d, a in stratified_sample(ds, 150, 42)}
cases = draft["cases"]; ids = [c["case_id"] for c in cases]
ann = {f"dev::{d['id']}::{h}": a for d in dev["documents"] for h, a in d["annotation_sets"][0]["annotations"].items()}
allC = sorted(k for k, a in ann.items() if a["choice"] == "Contradiction" and k not in s150 | golden | e13)
checks = {"seed_1500": draft["seed"] == 1500, "n_138": len(cases) == 138 and len(set(ids)) == 138,
          "class_counts_60_18_60": dict(Counter(c["gold_label"] for c in cases)) == {"Entailment": 60, "Contradiction": 18, "NotMentioned": 60},
          "all_remaining_fresh_contradictions_used": sorted(c["case_id"] for c in cases if c["gold_label"] == "Contradiction") == allC and len(allC) == 18,
          "disjoint_seed42_sample": not set(ids) & s150, "disjoint_golden": not set(ids) & golden, "disjoint_E13_DEV_ARCH_v1": not set(ids) & e13,
          "gold_labels_match_dev": all(ann[c["case_id"]]["choice"] == c["gold_label"] for c in cases)}
assert all(checks.values()), checks
man = {**{k: v for k, v in draft.items() if k != "status"}, "manifest_id": "DEV_ROUTING_v1", "status": "FROZEN before any model call", "n_docs": len({c["document_id"] for c in cases})}
(D / "DEV_ROUTING_v1.json").write_text(json.dumps(man, indent=1))
full = [{"case_id": c["case_id"], "document_id": c["document_id"], "hypothesis_id": c["hypothesis_id"], "hypothesis_text": c["hypothesis_text"], "context_kind": "full_nda_text", "context_text": docs[c["document_id"]]["text"]} for c in cases]
(D / "DEV_ROUTING_v1_FULL_CONTEXT.json").write_text(json.dumps({"manifest_id": "DEV_ROUTING_v1_FULL_CONTEXT", "total_cases": 138, "cases": full}))
gold = [{"case_id": c["case_id"], "gold_label": c["gold_label"], "gold_span_indices": ann[c["case_id"]]["spans"]} for c in cases]
(D / "DEV_ROUTING_v1_GOLD.json").write_text(json.dumps({"manifest_id": "DEV_ROUTING_v1", "note": "evaluator-only", "cases": gold}))
h = hashlib.sha256((D / "DEV_ROUTING_v1.json").read_bytes()).hexdigest()
json.dump({"checks": checks, "manifest_sha256": h, "n_docs": man["n_docs"]}, open(D / "results/manifest_verification.json", "w"), indent=1)
print(json.dumps(checks), h, man["n_docs"])
