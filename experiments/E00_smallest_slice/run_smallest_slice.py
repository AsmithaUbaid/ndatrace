"""E00 — smallest working slice.

Documents/demonstrates the minimum end-to-end path: one NDA + one requirement
-> one model call/inference path -> one structured classification -> one
evidence result. Reuses the frozen production runtime (pipeline/final_review.py's
review_final), not a separate/duplicated implementation.

This is NOT a new evaluation experiment and does not change any reported metric.

Default mode is --dry-run: no hosted model call is made (a stub gateway
returns a fixed, deterministic response), so this script never silently
incurs API cost when run as part of routine checks. Pass --live to make one
real hosted call instead (requires OPENROUTER_API_KEY in .env).

Success is defined as: a requirement is successfully processed when the
system returns a valid label and source-grounded evidence that a reviewer
can inspect.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.final_review import review_final  # noqa: E402
INPUT_PATH = HERE / "example_input.json"
OUTPUT_PATH = HERE / "example_output.json"

# The one deterministic fixture this script demonstrates against.
_DRY_RUN_EVIDENCE = (
    "shall not disclose the Confidential Information to any third party "
    "without the prior written consent of the Disclosing Party."
)
_DRY_RUN_RESPONSE = json.dumps({"label": "Entailment", "evidence": [_DRY_RUN_EVIDENCE]})


@dataclass
class _StubResponse:
    content: str
    model: str = "stub-dry-run"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    num_retries: int = 0


class _StubGateway:
    """Same interface pipeline/final_review.py's review_final() calls
    (.complete only) — used by tests/test_e22_security_remediation.py too.
    Makes zero network calls, so --dry-run never costs money."""

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> _StubResponse:
        return _StubResponse(content=_DRY_RUN_RESPONSE)


def run(dry_run: bool = True) -> dict:
    example = json.loads(INPUT_PATH.read_text())
    gateway = _StubGateway() if dry_run else None  # None -> review_final builds a real ModelGateway
    result = review_final(example["nda_text"], example["hypothesis_text"], gateway=gateway)

    output = {
        "mode": "dry_run" if dry_run else "live",
        "input": example,
        "label": result.label,
        "evidence": result.evidence,
        "explanation": result.explanation,
        "source_valid": result.source_valid,
        "needs_human_review": result.needs_human_review,
        "review_reason": result.review_reason,
        "model": result.model,
        "success": bool(result.label and result.source_valid),
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="make one real hosted model call instead of the dry-run stub")
    args = parser.parse_args()

    output = run(dry_run=not args.live)
    print(json.dumps(output, indent=2))

    # The smallest slice succeeded: a valid label plus evidence a reviewer can inspect.
    assert output["label"] in {"Entailment", "Contradiction", "NotMentioned"}, "invalid label"
    if output["label"] != "NotMentioned":
        assert output["source_valid"] is True, "evidence must be a genuine verbatim quote from the NDA text"
    print(f"\nSmallest slice: {'PASS' if output['success'] else 'REVIEW NEEDED'}")


if __name__ == "__main__":
    main()
