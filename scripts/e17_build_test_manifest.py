#!/usr/bin/env python3
"""E17 Stage A: FIRST reconstruction-v2 access to official TEST. Deterministic manifest construction + split verification ONLY. No predictions, no model calls.
Reads test.json (structure/labels for manifest) and never inspects content for difficulty. Selection: plain seeded stratified random sampling within each label."""
from __future__ import annotations
import hashlib, json, random, subprocess, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "experiments/E17_final_test"; SEED = 1600; PER_LABEL = 50
t_access = datetime.now(timezone.utc).isoformat(); commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
raw = (REPO / "data/contractnli/test.json").read_bytes(); test = json.loads(raw)
docs = test["documents"]; cases = []
for d in docs:
    for h, a in sorted(d["annotation_sets"][0]["annotations"].items()): cases.append({"case_id": f"test::{d['id']}::{h}", "document_id": d["id"], "hypothesis_id": h, "gold_label": a["choice"]})
lab = dict(Counter(c["gold_label"] for c in cases)); EXPECTED = {"Entailment": 968, "Contradiction": 220, "NotMentioned": 903}
ver = {"documents": len(docs), "cases": len(cases), "labels": lab, "expected_documents": 123, "expected_cases": 2091, "expected_labels": EXPECTED, "matches_expected": len(docs) == 123 and len(cases) == 2091 and lab == EXPECTED, "test_json_sha256": hashlib.sha256(raw).hexdigest(), "unique_case_ids": len({c["case_id"] for c in cases}) == len(cases)}
ver["first_test_access_utc"] = t_access; ver["commit_at_first_access"] = commit
if not ver["matches_expected"]:
    json.dump(ver, open(OUT / "results/test_verification.json", "w"), indent=1); print("TEST COUNTS DIFFER - STOP", ver); sys.exit(2)
rng = random.Random(SEED); chosen = []
for l in ("Entailment", "Contradiction", "NotMentioned"):
    pool = sorted([c for c in cases if c["gold_label"] == l], key=lambda c: (c["document_id"], c["hypothesis_id"])); chosen += rng.sample(pool, PER_LABEL)
chosen.sort(key=lambda c: (c["gold_label"], c["document_id"], c["hypothesis_id"]))
man = {"manifest_id": "TEST_HOSTED_v1", "status": "FROZEN - permanent; never resampled", "seed": SEED, "sampling": "random.Random(seed).sample(sorted(cases of label by (doc,hyp)), 50) for E, C, NM in that order; no performance/difficulty/length/hypothesis-family criteria",
       "n": len(chosen), "label_counts": dict(Counter(c["gold_label"] for c in chosen)), "unique_documents": len({c["document_id"] for c in chosen}), "test_json_sha256": ver["test_json_sha256"], "cases": chosen}
p = OUT / "manifests/TEST_HOSTED_v1.json"; p.write_text(json.dumps(man, indent=1)); ver["manifest_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest(); ver["manifest_label_counts"] = man["label_counts"]; ver["manifest_unique_documents"] = man["unique_documents"]
(OUT / "manifests/TEST_ALL_2091_cases.json").write_text(json.dumps({"manifest_id": "TEST_ALL_2091", "test_json_sha256": ver["test_json_sha256"], "n": len(cases), "cases": cases}, indent=1))
ver["all_cases_manifest_sha256"] = hashlib.sha256((OUT / "manifests/TEST_ALL_2091_cases.json").read_bytes()).hexdigest()
json.dump(ver, open(OUT / "results/test_verification.json", "w"), indent=1); print(json.dumps(ver, indent=1))
