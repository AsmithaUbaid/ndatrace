#!/usr/bin/env python3
"""Single-command reproducibility check.

Runs everything a grader needs to trust the repository, in one pass, with a
clear PASS/FAIL summary at the end:

  1. ContractNLI dataset present and checksum-verified.
  2. Full pytest suite (zero paid calls - mocked model calls).
  3. Every offline analysis script that recomputes metrics from saved
     predictions (not re-running paid inference).
  4. git diff --exit-code on the files those scripts write, to prove the
     recomputation is byte-for-byte identical to what's committed - not
     just "the script didn't crash."
  5. The actual FastAPI backend, in-process (no separate server, no paid
     calls): /health, /hypotheses, /experiments, /experiments/e20 all
     return real, non-empty, correctly-shaped data computed from the
     files this script just re-verified in step 4.

Exit code 0 only if every step passes. Does not touch git state (no commits,
no stashes) and makes zero hosted-model calls.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REPRO_SCRIPTS = [
    "experiments/E04B_majority_baseline/run_majority_baseline.py",
    "scripts/e17_analyze_final_test.py --metrics",
    "scripts/e17b_merge_and_analyze.py",
    "scripts/analyze_e20_rag_test.py",
    "scripts/analyze_e11_selective_agent.py",
    "scripts/analyze_e15_validation.py",
    "scripts/e18_business_analysis.py",
]

GIT_DIFF_PATHS = [
    "experiments/E04B_majority_baseline",
    "experiments/E11_selective_agent_evaluation/results",
    "experiments/E15_review_routing/results",
    "experiments/E17_final_test/results",
    "experiments/E17B_full_test_completion/results",
    "experiments/E18_business_course_synthesis/results",
    "experiments/E20_final_rag_test/results",
]

results: list[tuple[str, bool, str]] = []


def step(name: str):
    def decorator(fn):
        def wrapped():
            print(f"\n=== {name} ===")
            try:
                ok, detail = fn()
            except Exception as e:  # noqa: BLE001 - report, don't crash the summary
                ok, detail = False, f"{type(e).__name__}: {e}"
            results.append((name, ok, detail))
            print(("PASS" if ok else "FAIL") + (f" - {detail}" if detail else ""))
            return ok
        return wrapped
    return decorator


@step("1. Dataset present and checksum-verified")
def check_dataset():
    proc = subprocess.run(["bash", "scripts/download_data.sh"], cwd=ROOT,
                           capture_output=True, text=True)
    ok = proc.returncode == 0
    return ok, proc.stdout.strip().splitlines()[-1] if proc.stdout else proc.stderr.strip()[:200]


@step("2. Full test suite (zero paid calls)")
def check_tests():
    proc = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=ROOT,
                           capture_output=True, text=True)
    ok = proc.returncode == 0
    last_line = [l for l in proc.stdout.splitlines() if l.strip()][-1] if proc.stdout else ""
    return ok, last_line


@step("3. Offline analysis scripts recompute without error")
def check_analysis_scripts():
    failures = []
    for cmd in REPRO_SCRIPTS:
        proc = subprocess.run([sys.executable, *cmd.split()], cwd=ROOT,
                               capture_output=True, text=True)
        if proc.returncode != 0:
            failures.append(f"{cmd} (exit {proc.returncode}): {proc.stderr.strip()[:200]}")
    return (not failures), "; ".join(failures) if failures else f"{len(REPRO_SCRIPTS)} scripts ran clean"


@step("4. Recomputed results match committed files exactly (git diff --exit-code)")
def check_no_drift():
    proc = subprocess.run(["git", "diff", "--exit-code", "--", *GIT_DIFF_PATHS], cwd=ROOT,
                           capture_output=True, text=True)
    ok = proc.returncode == 0
    detail = "no drift" if ok else f"DRIFT DETECTED:\n{proc.stdout[:1000]}"
    return ok, detail


@step("5. Backend serves real computed data (in-process, no paid calls)")
def check_backend():
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from backend.app import app

    with TestClient(app) as client:
        checks = {
            "/health": lambda r: r.json().get("status") == "ok",
            "/hypotheses": lambda r: len(r.json()) == 17,
            "/experiments": lambda r: len(r.json()) >= 2 and r.json()[0]["n"] == 2091,
            "/experiments/e20": lambda r: any("rag" in row.get("system", "").lower() for row in r.json()),
        }
        failures = []
        for path, assertion in checks.items():
            resp = client.get(path)
            if resp.status_code != 200 or not assertion(resp):
                failures.append(f"{path} (status {resp.status_code})")
        return (not failures), "; ".join(failures) if failures else f"{len(checks)} endpoints verified"


def main() -> int:
    check_dataset()
    check_tests()
    check_analysis_scripts()
    check_no_drift()
    check_backend()

    print("\n" + "=" * 60)
    print("REPRODUCIBILITY CHECK SUMMARY")
    print("=" * 60)
    all_ok = True
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            all_ok = False
    print("=" * 60)
    print("ALL CHECKS PASSED" if all_ok else "ONE OR MORE CHECKS FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
