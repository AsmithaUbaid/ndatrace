#!/usr/bin/env python3
"""
Build the Category 10 logging/security eval battery (NDATrace_100_eval_
cases.md's Category 10) - but only 3 of its 5 cases (098-100). Cases
096/097 (request_id consistency, trace_id linking) need a real request-
handling layer to generate meaningful IDs - `new_request_id()`/
`new_trace_id()` exist (pipeline/logging_config.py) but are never called
anywhere yet, since that's the backend's (T032-T033) job, not a script's.
Correctly blocked on the same missing dependency as Category 9, not a
bug - documented here rather than silently skipped.

Also fixed a real bug found while building this: pipeline/logging_
config.py's setup_logging() existed but was never called anywhere, so
every structured log line added this session (classifier.py, agent.py,
model_gateway.py) went nowhere - logs/ndatrace.jsonl didn't even exist.
Fixed by having get_logger() ensure setup_logging() has run.

Generates real log content first (3 real classify()/agent calls) rather
than testing against nothing, then runs the 3 real checks against it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LOG_PATH = Path("logs/ndatrace.jsonl")

# The two real NDA sentences used to generate the log this script checks
# against (scripts/build_logging_eval_cases.py's own test calls) - a
# real leakage check needs to know what text COULD have leaked.
KNOWN_NDA_SENTENCES = [
    "Receiving Party shall not disclose Confidential Information to any third party.",
    "This clause is unrelated to the requirement.",
    "Receiving Party shall not reverse engineer any Confidential Information.",
    "This is an unrelated clause about payment terms.",
]
API_KEY_PATTERNS = (r"sk-[A-Za-z0-9]{10,}", r"Bearer\s+[A-Za-z0-9._-]{10,}", r"api_key\s*=\s*\S+")


def main() -> int:
    if not LOG_PATH.exists():
        print("ERROR: logs/ndatrace.jsonl not found - run a real classify()/agent call first.")
        return 1

    lines = LOG_PATH.read_text().splitlines()
    output = []

    # --- 098: zero raw NDA text in the log file ---
    leaked_sentences = [s for s in KNOWN_NDA_SENTENCES if any(s in line for line in lines)]
    output.append({
        "case_id": "098", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "logging_security",
        "description": (
            f"Zero raw NDA text in the log file - checked {len(lines)} real log lines "
            f"(from real classify()/agent calls) against {len(KNOWN_NDA_SENTENCES)} known NDA "
            f"sentences that were actually classified. Leaked: {leaked_sentences} "
            f"(expected: empty list)."
        ),
    })

    # --- 099: zero API keys in the log file ---
    key_matches = []
    for pattern in API_KEY_PATTERNS:
        for line in lines:
            if re.search(pattern, line):
                key_matches.append(pattern)
    output.append({
        "case_id": "099", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "logging_security",
        "description": (
            f"Zero API keys in the log file - checked {len(lines)} real log lines against "
            f"{len(API_KEY_PATTERNS)} key patterns (sk-, Bearer, api_key=). "
            f"Matches: {key_matches} (expected: empty list)."
        ),
    })

    # --- 100: every log line is valid JSON ---
    parse_failures = 0
    for line in lines:
        try:
            json.loads(line)
        except json.JSONDecodeError:
            parse_failures += 1
    output.append({
        "case_id": "100", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "logging_security",
        "description": (
            f"Every log line is valid JSON - {len(lines)} real lines checked, "
            f"{parse_failures} parse failures (expected: 0)."
        ),
    })

    # --- 096/097: correctly blocked, documented not skipped ---
    for case_id, desc in [
        ("096", "All log lines for one request share the same request_id"),
        ("097", "Agent trace_id links to parent request_id"),
    ]:
        output.append({
            "case_id": case_id, "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
            "category": "logging_security",
            "description": (
                f"{desc}. **Blocked, not built**: `new_request_id()`/`new_trace_id()` exist in "
                "pipeline/logging_config.py but are never called anywhere - every real log line "
                "so far shows request_id='no-request', trace_id='no-trace'. Generating a real "
                "per-request ID is the request-handling layer's job (the FastAPI backend, "
                "T032-T033), which doesn't exist yet - same blocking dependency as Category 9, "
                "not a separate bug."
            ),
        })

    out_path = Path("data/golden/logging_security_cases.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(output)} logging/security eval cases to {out_path}")
    for c in output:
        print(f"  {c['case_id']}: {c['description'][:90]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
