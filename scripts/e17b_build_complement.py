#!/usr/bin/env python3
"""E17B: build+freeze the 1,941-case TEST complement (ALL_TEST minus TEST_HOSTED_v1). No model calls. Does not touch E17's immutable files."""
from __future__ import annotations
import hashlib, json, sys
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(REPO))
import scripts.e17_common as C

E17 = REPO / "experiments/E17_final_test"; OUT = REPO / "experiments/E17B_full_test_completion"
F = C.load_frozen()  # asserts every E17 frozen hash/version unchanged
all_ids = {c["case_id"]: c for c in F["all"]}; hosted_ids = {c["case_id"] for c in F["hosted"]}
assert len(all_ids) == 2091 and len(hosted_ids) == 150 and hosted_ids <= set(all_ids)
remainder = [c for cid, c in all_ids.items() if cid not in hosted_ids]
assert len(remainder) == 1941
rc = Counter(c["gold_label"] for c in remainder); assert rc == {"Entailment": 918, "Contradiction": 170, "NotMentioned": 853}, rc
union = set(all_ids) - hosted_ids - {c["case_id"] for c in remainder}; assert not union
remainder.sort(key=lambda c: (c["document_id"], c["hypothesis_id"]))
man = {"manifest_id": "E17B_REMAINING_v1", "status": "FROZEN before any model call", "n": len(remainder), "label_counts": dict(rc), "test_json_sha256": F is not None and C.FROZEN["test_json_sha256"], "e17_hosted_manifest_sha256": C.FROZEN["manifest_sha256"], "cases": remainder}
p = OUT / "manifests/E17B_REMAINING_v1.json"; p.write_text(json.dumps(man, indent=1)); man_sha = hashlib.sha256(p.read_bytes()).hexdigest()
req_hash = hashlib.sha256("\n\x1e".join(C.SYSTEM + "\x1f" + F["user"](c) for c in remainder).encode()).hexdigest()
ver = {"pre_run_commit": None, "test_json_sha256": C.FROZEN["test_json_sha256"], "e17_hosted_manifest_sha256": C.FROZEN["manifest_sha256"], "e17b_manifest_sha256": man_sha, "e17b_request_sha256": req_hash,
       "all_test": 2091, "e17_hosted": 150, "e17b_remainder": len(remainder), "remainder_labels": dict(rc), "intersection_empty": True, "union_equals_all_test": True}
json.dump(ver, open(OUT / "results/complement_verification.json", "w"), indent=1); print(json.dumps(ver, indent=1))
