#!/usr/bin/env python3
"""
Build the Category 6 confidence/abstention eval battery (5 cases, IDs
076-080) from NDATrace_100_eval_cases.md's Category 6, entirely reusing
T026's already-computed analysis (data/confidence_analysis.json) - $0
cost, no new API calls.

Unlike Categories 1/2 (selected from ContractNLI by keyword/structural
proxy), these cases test *properties of the confidence signal itself*,
so each one pulls its example from the real per-case results already
collected during T026's analysis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    analysis = json.loads(Path("data/confidence_analysis.json").read_text())
    cases = analysis["cases"]
    output = []

    # --- 076: high confidence + correct = good calibration ---
    match = next((c for c in cases if c["self_confidence"] > 0.85 and c["correct"]), None)
    output.append({
        "case_id": "076", "doc_id": match["doc_id"], "hypothesis_id": match["hypothesis_id"],
        "gold_label": match["gold_label"], "category": "confidence_abstention",
        "description": (
            f"High confidence + correct = good calibration. Real case: self_confidence="
            f"{match['self_confidence']:.2f}, predicted={match['predicted_label']}, "
            f"gold={match['gold_label']} (correct). 123/150 cases in the full sample match "
            "this pattern - the large majority."
        ),
    })

    # --- 077: high confidence + wrong = overconfidence FAILURE ---
    match = next((c for c in cases if c["self_confidence"] > 0.85 and not c["correct"]), None)
    output.append({
        "case_id": "077", "doc_id": match["doc_id"], "hypothesis_id": match["hypothesis_id"],
        "gold_label": match["gold_label"], "category": "confidence_abstention",
        "description": (
            f"High confidence + wrong = overconfidence FAILURE. Real case: self_confidence="
            f"{match['self_confidence']:.2f}, predicted={match['predicted_label']}, "
            f"gold={match['gold_label']} (WRONG). 15/150 cases (10%) in the full sample match "
            "this pattern - this is exactly why T026 found self-confidence unusable as an "
            "abstention gate (AUROC 0.554): confidently wrong answers are common enough to "
            "matter, and indistinguishable by confidence alone from confidently right ones."
        ),
    })

    # --- 078: low confidence + wrong = good self-awareness ---
    match = next((c for c in cases if c["self_confidence"] < 0.5 and not c["correct"]), None)
    if match is None:
        output.append({
            "case_id": "078", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
            "category": "confidence_abstention",
            "description": (
                "Low confidence + wrong = good self-awareness. **No matching case exists in the "
                "150-case sample** [proxy: no case found; this is itself the finding, not a "
                "selection failure]. All 8 cases with self_confidence < 0.5 were actually "
                "CORRECT (100% empirical accuracy in that bucket, per T026's calibration table) "
                "- the model's rare low-confidence moments are, if anything, its most reliable "
                "ones, the opposite of the expected pattern. This is a real, honest data point, "
                "not a gap in case selection: it independently confirms T026's finding that "
                "self-confidence is not just weak but actively miscalibrated in places."
            ),
        })
    else:
        output.append({
            "case_id": "078", "doc_id": match["doc_id"], "hypothesis_id": match["hypothesis_id"],
            "gold_label": match["gold_label"], "category": "confidence_abstention",
            "description": f"Low confidence + wrong: self_confidence={match['self_confidence']:.2f}",
        })

    # --- 079: abstained cases are hard (>50% would be wrong, target from plan) ---
    effectiveness = analysis["f05_abstention_effectiveness"]
    output.append({
        "case_id": "079", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "confidence_abstention",
        "description": (
            f"Abstained cases are hard - aggregate check, target >50% of abstained cases would "
            f"have been wrong. **Target NOT met**: at the selected threshold "
            f"(signal={analysis['best_signal']}), abstention effectiveness is only "
            f"{effectiveness:.1%} - the 'would-abstain' bucket is still 80.6% correct on its "
            "own. This is why pipeline/confidence.py routes ACCEPT/REVIEW rather than "
            "ACCEPT/ABSTAIN (T027) - hard abstention here would discard far more right answers "
            "than wrong ones, failing this eval case's own target honestly rather than picking "
            "a threshold that makes the number look better."
        ),
    })

    # --- 080: threshold sweep - accuracy-coverage tradeoff curve ---
    sweep = analysis["f04_threshold_sweep"]
    monotonic = all(
        sweep[i]["selective_accuracy"] <= sweep[i + 1]["selective_accuracy"] + 1e-9
        for i in range(len(sweep) - 1)
        if sweep[i]["selective_accuracy"] == sweep[i]["selective_accuracy"]  # skip NaN
    )
    output.append({
        "case_id": "080", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "confidence_abstention",
        "description": (
            f"Threshold sweep - expects a clear tradeoff curve: higher threshold -> higher "
            f"selective accuracy, lower coverage. Signal used: {analysis['best_signal']} "
            f"(self-confidence excluded - already shown unusable). Sweep is "
            f"{'monotonically non-decreasing' if monotonic else 'NOT cleanly monotonic'} "
            f"in selective accuracy as threshold rises: {[round(s['selective_accuracy'], 3) for s in sweep]}. "
            "Full curve in notebooks/06_confidence_abstention.ipynb's F06 plot."
        ),
    })

    out_path = Path("data/golden/confidence_cases.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(output)} confidence/abstention eval cases to {out_path}")
    for c in output:
        print(f"  {c['case_id']}: {c['description'][:80]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
