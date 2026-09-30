"""E17 shared frozen-protocol guards + request builder. Fail closed if any frozen value differs. Never regenerates TEST_HOSTED_v1."""
from __future__ import annotations
import hashlib, json, sys
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(REPO))
from evaluation import evidence_matching as EM  # noqa: E402
from pipeline import evidence_validator as EV  # noqa: E402

E17 = REPO / "experiments/E17_final_test"
FROZEN = {"manifest_sha256": "a1cc8f53bb4d41c7e1c66862241cbe2892000eef9d6d27a41b7a37e072eb709a", "all_cases_manifest_sha256": "8a2f13af814951a5af682ab5acfb79ecd8a2a644f14e1bc7944a364bd5dd6be4",
          "test_json_sha256": "460267b56052a2dc5aead98eb35eadef9e6734d5723d37b4a9790e410f812387", "prompt_sha1": "3fcc7c95cf1287c292e403f12b307c9d912278ce",
          "hosted_requests_sha256": "a7c2d76985479b001cb73fc102b2c808f5a4d44ab301a6327a88f01ac1bfbd4b", "seed": 1600, "n": 150}
TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"
SYSTEM = open(REPO / "prompts/final/gpt_p0.txt", newline="").read()
LABELS = ("Entailment", "Contradiction", "NotMentioned")
W = {"Entailment": 968, "Contradiction": 220, "NotMentioned": 903}


def _sha256(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_frozen():
    """Returns dict(test_docs, hyp, hosted_cases, all_cases) after asserting every frozen value."""
    test_path = REPO / "data/contractnli/test.json"
    assert _sha256(test_path) == FROZEN["test_json_sha256"], "test.json hash differs"
    man_p = E17 / "manifests/TEST_HOSTED_v1.json"; assert _sha256(man_p) == FROZEN["manifest_sha256"], "TEST_HOSTED_v1 hash differs"
    allp = E17 / "manifests/TEST_ALL_2091_cases.json"; assert _sha256(allp) == FROZEN["all_cases_manifest_sha256"], "TEST_ALL manifest hash differs"
    man = json.load(open(man_p)); assert man["seed"] == FROZEN["seed"] == 1600 and man["n"] == len(man["cases"]) == FROZEN["n"] == 150
    assert dict(Counter(c["gold_label"] for c in man["cases"])) == {"Entailment": 50, "Contradiction": 50, "NotMentioned": 50}, "hosted labels not 50/50/50"
    assert hashlib.sha1(SYSTEM.encode()).hexdigest() == FROZEN["prompt_sha1"], "prompt sha1 differs"
    assert EM.CURRENT_EVIDENCE_EVALUATOR == EM.EVIDENCE_EVALUATOR_V2 == "evidence_evaluator_v2", "evaluator version differs"
    assert EV.CURRENT_RUNTIME_EVIDENCE_VALIDATOR == EV.RUNTIME_EVIDENCE_VALIDATOR_V2 == "runtime_evidence_validator_v2", "validator version differs"
    test = json.load(open(test_path)); docs = {d["id"]: d for d in test["documents"]}; hyp = {k: v["hypothesis"] for k, v in test["labels"].items()}
    allc = json.load(open(allp))["cases"]; assert len(allc) == 2091
    ctx = lambda c: docs[c["document_id"]]["text"]
    user = lambda c: TEMPLATE.format(hypothesis_text=hyp[c["hypothesis_id"]], context_text=ctx(c))
    req_hash = hashlib.sha256("\n\x1e".join(SYSTEM + "\x1f" + user(c) for c in man["cases"]).encode()).hexdigest()
    assert req_hash == FROZEN["hosted_requests_sha256"], "hosted request artifact hash differs"
    return {"docs": docs, "hyp": hyp, "hosted": man["cases"], "all": allc, "user": user, "ctx": ctx}
