#!/usr/bin/env python3
"""
Performance testing (WBS T039: H01, H03, H05, H06) - real measurements
against the live, running backend (must already be up at
NDATRACE_API_URL, default http://127.0.0.1:8000), the actual final
architecture (RAG + selective agent, T031), not a mock.

Found missing entirely during a 2026-09-24 plan-vs-reality audit - never
built as its own task despite being P1. H02 (per-stage latency) is
excluded: it needs timing instrumentation inside the pipeline that was
never added (CostLatencyRecord.stages is always empty in practice),
which is a real, separate gap, not something this script can measure
after the fact. H04/H07 are P2 and out of scope for T039 specifically.

Usage:
    python scripts/run_performance_tests.py [--pid <backend_pid>]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_URL = "http://127.0.0.1:8000"
TEST_NDA = (
    "This Non-Disclosure Agreement is entered into between Acme Corp and Beta LLC. "
    "Receiving Party shall not reverse engineer, decompile, or disassemble any objects "
    "which embody Disclosing Party's Confidential Information. Receiving Party may "
    "disclose Confidential Information to its employees who need to know such information "
    "for the purposes of this Agreement. Upon termination of this Agreement, Receiving "
    "Party shall return or destroy all Confidential Information in its possession."
)


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    k = (len(values) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(values) - 1)
    if f == c:
        return values[f]
    return values[f] + (values[c] - values[f]) * (k - f)


def h01_single_request_latency(client: httpx.Client, n_reps: int = 10) -> dict:
    """H01: single-requirement latency, 10 real repetitions, p50/p90/p95.
    Hypothesis under test: < 15 seconds."""
    latencies_ms = []
    for i in range(n_reps):
        start = time.time()
        r = client.post("/review", json={"nda_text": TEST_NDA, "hypothesis_ids": ["nda-11"]})
        r.raise_for_status()
        latencies_ms.append((time.time() - start) * 1000)
        print(f"  H01 rep {i+1}/{n_reps}: {latencies_ms[-1]:.0f}ms")

    result = {
        "n_reps": n_reps,
        "p50_ms": round(percentile(latencies_ms, 50), 1),
        "p90_ms": round(percentile(latencies_ms, 90), 1),
        "p95_ms": round(percentile(latencies_ms, 95), 1),
        "max_ms": round(max(latencies_ms), 1),
        "hypothesis_under_15s": max(latencies_ms) < 15000,
    }
    return result


def h03_full_nda_latency(client: httpx.Client, n_reps: int = 3) -> dict:
    """H03: full 17-requirement NDA review, 3 real repetitions.
    Hypothesis under test: 2-5 minutes total."""
    total_times_s = []
    per_req_times_ms = []
    for i in range(n_reps):
        start = time.time()
        r = client.post("/review", json={"nda_text": TEST_NDA})  # all hypotheses
        r.raise_for_status()
        elapsed = time.time() - start
        total_times_s.append(elapsed)
        n_results = len(r.json()["results"])
        per_req_times_ms.append(elapsed * 1000 / n_results)
        print(f"  H03 rep {i+1}/{n_reps}: {elapsed:.1f}s for {n_results} requirements "
              f"({elapsed*1000/n_results:.0f}ms/req)")

    return {
        "n_reps": n_reps,
        "avg_total_seconds": round(statistics.mean(total_times_s), 1),
        "avg_per_requirement_ms": round(statistics.mean(per_req_times_ms), 1),
        "hypothesis_2_to_5_min": all(120 <= t <= 300 for t in total_times_s),
        "raw_total_seconds": [round(t, 1) for t in total_times_s],
    }


def h05_memory_usage(client: httpx.Client, backend_pid: int | None) -> dict:
    """H05: peak RSS of the backend process during a full NDA review.
    Hypothesis under test: < 2GB. Skipped if the backend PID can't be found
    (e.g. running on a different machine than this script)."""
    if backend_pid is None:
        return {"skipped": True, "reason": "No backend PID found/provided"}

    proc = psutil.Process(backend_pid)
    peak_rss_mb = proc.memory_info().rss / (1024 * 1024)

    # Sample memory while a real full-NDA request is in flight.
    import threading
    stop = threading.Event()
    samples = [peak_rss_mb]

    def sample():
        while not stop.is_set():
            try:
                samples.append(proc.memory_info().rss / (1024 * 1024))
            except psutil.NoSuchProcess:
                break
            time.sleep(0.5)

    t = threading.Thread(target=sample)
    t.start()
    r = client.post("/review", json={"nda_text": TEST_NDA})
    r.raise_for_status()
    stop.set()
    t.join()

    peak = max(samples)
    return {
        "backend_pid": backend_pid,
        "peak_rss_mb": round(peak, 1),
        "peak_rss_gb": round(peak / 1024, 3),
        "hypothesis_under_2gb": peak < 2048,
    }


def h06_rate_limits(client: httpx.Client) -> dict:
    """H06: burst of 17 real requests (one full NDA's worth of individual
    single-requirement calls fired back-to-back), checking for any 429s.
    Hypothesis under test: well within limits at single-user scale."""
    statuses = []
    start = time.time()
    for hyp_id in [f"nda-{i}" for i in [1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20]]:
        r = client.post("/review", json={"nda_text": TEST_NDA, "hypothesis_ids": [hyp_id]})
        statuses.append(r.status_code)
    elapsed = time.time() - start

    n_429 = sum(1 for s in statuses if s == 429)
    return {
        "n_requests": len(statuses),
        "n_429_rate_limited": n_429,
        "elapsed_seconds": round(elapsed, 1),
        "actual_rpm": round(len(statuses) / (elapsed / 60), 1),
        "hypothesis_well_within_limits": n_429 == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, default=None, help="Backend process PID for H05 memory sampling")
    args = parser.parse_args()

    backend_pid = args.pid
    if backend_pid is None:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "uvicorn" in cmdline and "backend.app" in cmdline:
                backend_pid = proc.info["pid"]
                break

    with httpx.Client(base_url=API_URL, timeout=120.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        print(f"Backend reachable at {API_URL} (pid={backend_pid})\n")

        print("=== H01: single-request latency (10 reps) ===")
        h01 = h01_single_request_latency(client)
        print(json.dumps(h01, indent=2))

        print("\n=== H06: rate limits (burst of 17) ===")
        h06 = h06_rate_limits(client)
        print(json.dumps(h06, indent=2))

        print("\n=== H05: memory usage (during 1 full-NDA request) ===")
        h05 = h05_memory_usage(client, backend_pid)
        print(json.dumps(h05, indent=2))

        print("\n=== H03: full-NDA (17-requirement) latency (3 reps) ===")
        h03 = h03_full_nda_latency(client)
        print(json.dumps(h03, indent=2))

    result = {"H01_single_request_latency": h01, "H03_full_nda_latency": h03,
              "H05_memory_usage": h05, "H06_rate_limits": h06}
    Path("data/performance_results.json").write_text(json.dumps(result, indent=2))
    print("\nWrote data/performance_results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
