"""E17B guards: complement integrity, frozen hashes, merge integrity, no persisted credentials."""
import glob
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
E17B = REPO / "experiments/E17B_full_test_completion"


def test_complement_verification():
    v = json.load(open(E17B / "results/complement_verification.json"))
    assert v["all_test"] == 2091 and v["e17_hosted"] == 150 and v["e17b_remainder"] == 1941
    assert v["remainder_labels"] == {"Entailment": 918, "Contradiction": 170, "NotMentioned": 853}
    assert v["intersection_empty"] and v["union_equals_all_test"]


def test_frozen_hashes_match_protocol():
    proto = open(E17B / "frozen_protocol.yaml").read()
    v = json.load(open(E17B / "results/complement_verification.json"))
    assert v["e17b_manifest_sha256"] in proto and v["e17b_request_sha256"] in proto and v["test_json_sha256"] in proto


def test_merge_integrity():
    m = json.load(open(E17B / "results/final_full_test_metrics.json"))["integrity"]
    assert m["merged_row_count"] == 2091 and m["unique_case_ids"] == 2091 and m["duplicate_case_ids"] == 0
    assert m["missing_test_case_ids"] == 0 and m["extra_case_ids"] == 0
    assert m["gold_label_counts"] == {"Entailment": 968, "Contradiction": 220, "NotMentioned": 903}


def test_no_credentials_persisted_anywhere_in_e17b():
    needle = "sk-or-v1"
    files = list(glob.glob(str(E17B / "**/*"), recursive=True)) + [str(REPO / "scripts/run_e17b_hosted_test.py"), str(REPO / "scripts/e17b_build_complement.py"), str(REPO / "scripts/e17b_merge_and_analyze.py"), str(REPO / "results/budget/reconstruction_spend_ledger.csv")]
    for f in files:
        p = Path(f)
        if p.is_file() and p.stat().st_size < 50_000_000:
            try:
                assert needle not in p.read_text(errors="ignore"), f"credential-looking string found in {f}"
            except UnicodeDecodeError:
                pass


def test_e17_immutable_150_untouched():
    e17 = REPO / "experiments/E17_final_test/results/run_E17_gpt_hosted_test_cases.jsonl"
    rows = [json.loads(l) for l in open(e17)]
    assert len(rows) == 150 and len({r["case_id"] for r in rows}) == 150
