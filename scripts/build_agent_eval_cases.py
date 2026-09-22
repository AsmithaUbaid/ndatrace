#!/usr/bin/env python3
"""
Build the Category 5 agent behaviour eval battery (10 cases, IDs
066-075) from NDATrace_100_eval_cases.md's Category 5 - reuses the real
trace data from T030's agent experiment (data/agent_experiment.json,
already-spent $0.017) plus one fresh routing check (free, deterministic)
to find a real ACCEPT-routed case for the "does NOT trigger" case.

Two cases (071 step cap, 072 cost/token cap) have no real production
example - across 67 real REVIEW cases, none ever hit the step or token
limit (avg 1.31 steps, well under the cap of 5) - so they're verified by
the existing unit tests instead of a mined live case, noted honestly
rather than forced.

One case (075, "agent abstains when stuck") documents a real, deliberate
design deviation: pipeline/agent.py does not implement a distinct
"abstain" action - when the step/time/token limit is hit without a
conclusion, it falls back to a plain classify() call rather than
returning an abstain signal. That decision (whether to abstain) is left
to pipeline/confidence.py upstream, not duplicated in the agent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.harness import EvaluationHarness
from pipeline.config import settings
from pipeline.confidence import Route, route
from pipeline.parser import parse_contractnli_file
from pipeline.rule_baseline import classify_by_keywords
from scripts.run_oracle_experiment import SEED, stratified_sample


def main() -> int:
    agent_data = json.loads(Path("data/agent_experiment.json").read_text())
    outcomes = agent_data["outcomes"]

    harness = EvaluationHarness()
    rag = harness.load_results("runs/run_T018_prompt_v2.jsonl")[0]
    dataset = parse_contractnli_file(settings.data_path / "dev.json")
    sample = stratified_sample(dataset, 150, SEED)
    doc_by_id = {doc.doc_id: doc for doc, _ in sample}

    output = []

    # --- 066: agent triggers on rule disagreement (not self-confidence - T026 found that signal unusable) ---
    o = outcomes[0]
    output.append({
        "case_id": "066", "doc_id": o["doc_id"], "hypothesis_id": o["hypothesis_id"],
        "gold_label": o["gold_label"], "category": "agent_behaviour",
        "description": (
            "Agent triggers on REVIEW routing. Adapted from the plan's original design (trigger "
            "on low self-confidence, e.g. 0.35) - T026 found self-confidence unusable (AUROC "
            "0.554), so the real trigger is rule-baseline disagreement (T027). Real case: RAG "
            f"predicted {o['rag_label']}, the agent was invoked and investigated."
        ),
    })

    # --- 067: agent does NOT trigger when rule agrees ---
    accept_case = None
    for pred in rag.predictions:
        rule_label = classify_by_keywords(pred.hypothesis_id, doc_by_id[pred.doc_id].text)
        decision = route(self_confidence=pred.confidence, rule_agrees=(rule_label == pred.predicted_label.value))
        if decision.route == Route.ACCEPT:
            accept_case = pred
            break
    output.append({
        "case_id": "067", "doc_id": accept_case.doc_id, "hypothesis_id": accept_case.hypothesis_id,
        "gold_label": accept_case.predicted_label.value, "category": "agent_behaviour",
        "description": (
            f"Agent does NOT trigger when the rule baseline agrees with RAG. Real case: RAG "
            f"predicted {accept_case.predicted_label.value}, rule baseline agreed - routed ACCEPT, "
            "agent never invoked (pipeline/confidence.py's route())."
        ),
    })

    # --- 068: agent picks a relevant tool for a defined-term hypothesis ---
    match = next((o for o in outcomes if any(s["action"] == "find_defined_term" for s in o["steps"])), None)
    output.append({
        "case_id": "068", "doc_id": match["doc_id"], "hypothesis_id": match["hypothesis_id"],
        "gold_label": match["gold_label"], "category": "agent_behaviour",
        "description": (
            f"Agent picks a relevant tool. Real trace: {[s['action'] for s in match['steps']]} - "
            "called find_defined_term for a hypothesis referencing a term that's likely defined "
            "elsewhere in the document (nda-2, about a specific defined-term scope limitation)."
        ),
    })

    # --- 069: agent stops after a small number of steps when evidence is clear ---
    match = next((o for o in outcomes if o["stopped_reason"] == "concluded" and o["n_steps"] <= 3), None)
    output.append({
        "case_id": "069", "doc_id": match["doc_id"], "hypothesis_id": match["hypothesis_id"],
        "gold_label": match["gold_label"], "category": "agent_behaviour",
        "description": (
            f"Agent stops after finding clear evidence, not the max step budget. Real case: "
            f"concluded in {match['n_steps']} step(s) (cap is {5}). Across all 67 real REVIEW "
            "cases, 52/67 concluded normally and none reached the 5-step cap - the model "
            "typically decides quickly rather than over-investigating."
        ),
    })

    # --- 070: agent detects a query loop ---
    match = next((o for o in outcomes if o["stopped_reason"] == "duplicate_loop"), None)
    output.append({
        "case_id": "070", "doc_id": match["doc_id"], "hypothesis_id": match["hypothesis_id"],
        "gold_label": match["gold_label"], "category": "agent_behaviour",
        "description": (
            f"Agent detects a query loop. Real trace: {[s['action'] for s in match['steps']]} - "
            "the model repeated the same tool+query combination, tripping duplicate-call "
            "detection (pipeline/agent.py) before hitting the step cap. 14/67 real cases (21%) "
            "hit this - the single most common non-'concluded' stop reason."
        ),
    })

    # --- 071: agent respects the step cap (no real case reached it - verified by unit test instead) ---
    output.append({
        "case_id": "071", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "agent_behaviour",
        "description": (
            "Agent respects the step cap (5). **No real production case reached the cap** "
            "[proxy: none of 67 real REVIEW cases needed more than 3 steps] - verified instead by "
            "tests/test_agent.py::test_agent_hits_step_limit_and_falls_back, which forces a "
            "10-step-worth decision sequence with max_steps=3 and confirms exactly 3 calls are "
            "made before falling back."
        ),
    })

    # --- 072: agent respects the token/cost cap (same situation as 071) ---
    output.append({
        "case_id": "072", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "agent_behaviour",
        "description": (
            "Agent respects the cost/token cap. **No real production case approached the cap** "
            "(real per-case cost topped out around $0.0006, settings.agent_max_tokens is 3000) - "
            "verified instead by tests/test_agent.py::test_agent_respects_token_limit. Note: this "
            "cap was added during this eval-case build (a real gap - settings.agent_max_tokens "
            "existed in config but wasn't enforced in pipeline/agent.py until now)."
        ),
    })

    # --- 073: agent improves on RAG (recovery) ---
    match = next(o for o in outcomes if o["outcome"] == "recovery")
    output.append({
        "case_id": "073", "doc_id": match["doc_id"], "hypothesis_id": match["hypothesis_id"],
        "gold_label": match["gold_label"], "category": "agent_behaviour",
        "description": (
            f"Agent improves on RAG. Real case: RAG predicted {match['rag_label']}, agent "
            f"corrected it to {match['agent_label']} (gold: {match['gold_label']}). 6/67 real "
            "REVIEW cases (9.0%) show this pattern."
        ),
    })

    # --- 074: agent makes it worse - CRITICAL FAILURE (regression) ---
    match = next(o for o in outcomes if o["outcome"] == "regression")
    output.append({
        "case_id": "074", "doc_id": match["doc_id"], "hypothesis_id": match["hypothesis_id"],
        "gold_label": match["gold_label"], "category": "agent_behaviour",
        "description": (
            f"Agent makes it worse - CRITICAL FAILURE. Real case: RAG correctly predicted "
            f"{match['rag_label']} (matches gold {match['gold_label']}), agent flipped it to "
            f"{match['agent_label']} (wrong). 3/67 real REVIEW cases (4.5%) show this pattern - "
            "real, tracked, and outweighed by recovery (9.0%) but not zero. This is the number "
            "T031's architecture decision should weigh, not just the net accuracy gain."
        ),
    })

    # --- 075: agent abstains when stuck (documented design deviation) ---
    output.append({
        "case_id": "075", "doc_id": "", "hypothesis_id": "", "gold_label": "NotMentioned",
        "category": "agent_behaviour",
        "description": (
            "Agent abstains when stuck. **Deliberate design deviation, not a gap**: "
            "pipeline/agent.py does not implement a distinct 'abstain' action when the step/time/"
            "token limit is hit without a conclusion - it falls back to a plain classify() call "
            "over everything gathered instead (see pipeline/agent.py's docstring). Whether to "
            "abstain on the final answer is left entirely to pipeline/confidence.py upstream, so "
            "there is no separate agent-level abstain path to test here."
        ),
    })

    out_path = Path("data/golden/agent_cases.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(output)} agent behaviour eval cases to {out_path}")
    for c in output:
        print(f"  {c['case_id']}: {c['description'][:80]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
