#!/usr/bin/env python3
"""
E11 Stage B -- runs the frozen E10 selective agent (pipeline/agent_v2.py) against the 15
triggered TRAIN_ARCH_v1 cases via real openai/gpt-5-mini calls, then constructs the full
150-row A3 result table (135 non-triggered rows reuse A2 exactly, zero new hosted calls).

Frozen exactly per E10 -- this script does NOT modify the trigger, tools, limits, fallback
policy, or model. It only wires pipeline.agent_v2.run_selective_agent's injected model_call
interface to a real ModelGateway call and records the resulting traces/spend.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.budget import check_budget_against_ledger, record_spend, reconstruction_spend_so_far  # noqa: E402
from pipeline.agent_v2 import cross_reference_to_named_provision_cue, run_selective_agent  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

E07_DIR = REPO / "experiments/E07_standard_rag"
E08B_DIR = REPO / "experiments/E08B_stronger_model_diagnostic"
E05_DIR = REPO / "experiments/E05_full_context"
E11_DIR = REPO / "experiments/E11_selective_agent_evaluation"
RESULTS_DIR = E11_DIR / "results"

EXPERIMENT_ID = "E11_selective_agent_evaluation"
MODEL = "openai/gpt-5-mini"
PROVIDER = "openrouter"
REQUEST_TIMEOUT_SECONDS = 30
PLANNING_BUDGET_USD = 5.00
PROTECTED_RESERVE_FRACTION = 0.25
CONSERVATIVE_PROJECTED_USD = 0.1931  # from scripts/forecast_e11_agent_tokens.py's pre-run forecast


def main() -> int:
    gpt_cases = {json.loads(l)["case_id"]: json.loads(l)
                 for l in open(E08B_DIR / "results/run_E08B_A2_gpt5mini_train_cases.jsonl")}
    assert len(gpt_cases) == 150

    retrieved = json.load(open(E07_DIR / "TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"))
    chunk_text_by_case = {c["case_id"]: c["ranked_chunk_text"] for c in retrieved["cases"]}
    manifest = json.load(open(E05_DIR / "TRAIN_ARCH_v1.json"))
    hypothesis_by_case = {c["case_id"]: c["hypothesis_text"] for c in manifest["cases"]}
    doc_id_by_case = {c["case_id"]: c["document_id"] for c in manifest["cases"]}
    train = json.load(open(REPO / "data/contractnli/train.json"))
    doc_text_by_id = {d["id"]: d["text"] for d in train["documents"]}

    triggered_ids = sorted(cid for cid, chunks in chunk_text_by_case.items()
                            if cross_reference_to_named_provision_cue(chunks))
    assert len(triggered_ids) == 15, f"expected 15 triggered cases, got {len(triggered_ids)}"
    print(f"Pre-run safety check: 15/15 triggered cases confirmed: {triggered_ids}")

    pre_run_ledger = reconstruction_spend_so_far()
    gate = check_budget_against_ledger(CONSERVATIVE_PROJECTED_USD, PLANNING_BUDGET_USD,
                                        PROTECTED_RESERVE_FRACTION)
    print(f"Pre-run ledger: ${pre_run_ledger:.4f}. Budget gate: {gate.reason}")
    if not gate.allowed:
        print("BUDGET GATE BLOCKED. Aborting before any hosted call.")
        return 1

    gateway = ModelGateway(model=MODEL, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    run_id = uuid.uuid4().hex[:12]

    def make_model_call(call_log: list[dict]):
        def _call(system_prompt: str, user_prompt: str) -> str:
            try:
                response = gateway.complete(system_prompt=system_prompt, user_prompt=user_prompt,
                                              temperature=0.0)
            except ModelError as e:
                # Frozen fallback policy is NOT altered here -- returning invalid JSON causes
                # agent_v2's EXISTING parse_agent_action to raise MalformedActionError, which the
                # unmodified loop already handles via its own invalid_action fallback path.
                call_log.append({"error": str(e), "input_tokens": None, "output_tokens": None,
                                  "latency_ms": None, "cost_usd": None, "retry_count": None,
                                  "raw_response": ""})
                return ""
            call_log.append({
                "input_tokens": response.tokens_in, "output_tokens": response.tokens_out,
                "latency_ms": response.latency_ms, "cost_usd": response.cost_usd,
                "retry_count": response.num_retries, "raw_response": response.content,
            })
            record_spend(experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL,
                          input_tokens=response.tokens_in, output_tokens=response.tokens_out,
                          cost_usd=response.cost_usd, run_id=run_id)
            return response.content
        return _call

    agent_traces = []
    run_start = time.perf_counter()
    for i, cid in enumerate(triggered_ids, 1):
        a2 = gpt_cases[cid]
        doc_id = doc_id_by_case[cid]
        call_log: list[dict] = []
        t0 = time.perf_counter()
        trace = run_selective_agent(
            case_id=cid, doc_text=doc_text_by_id[doc_id],
            hypothesis_text=hypothesis_by_case[cid],
            a2_context_chunks=chunk_text_by_case[cid],
            a2_label=a2["predicted_label"], a2_evidence=a2.get("evidence") or [],
            model_call=make_model_call(call_log),
        )
        wall_s = time.perf_counter() - t0

        record = trace.to_dict()
        record["run_id"] = run_id
        record["experiment_id"] = EXPERIMENT_ID
        record["model"] = MODEL
        record["provider"] = PROVIDER
        record["gold_label"] = a2["gold_label"]
        record["call_log"] = call_log
        record["total_incremental_cost_usd"] = sum(c["cost_usd"] or 0 for c in call_log)
        record["total_input_tokens"] = sum(c["input_tokens"] or 0 for c in call_log)
        record["total_output_tokens"] = sum(c["output_tokens"] or 0 for c in call_log)
        record["wall_seconds"] = wall_s
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        agent_traces.append(record)

        print(f"[{i}/15] {cid:22} gold={a2['gold_label']:14} a2={a2['predicted_label']:14} "
              f"a3={trace.final_label:14} stop={trace.stop_reason:18} steps={trace.agent_steps} "
              f"tools={trace.tool_calls} fallback={trace.fallback_to_a2} "
              f"cost=${record['total_incremental_cost_usd']:.4f} ({wall_s:.1f}s)")

    total_wall_s = time.perf_counter() - run_start
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "agent_traces.jsonl", "w") as f:
        for r in agent_traces:
            f.write(json.dumps(r, default=str) + "\n")

    # --- Build the full 150-row A3 result table ---
    triggered_final = {t["case_id"]: t for t in agent_traces}
    a3_rows = []
    for cid, a2 in gpt_cases.items():
        if cid in triggered_final:
            t = triggered_final[cid]
            a3_rows.append({
                "case_id": cid, "gold_label": a2["gold_label"], "triggered": True,
                "a2_label": a2["predicted_label"], "a2_evidence": a2.get("evidence") or [],
                "a3_label": t["final_label"], "a3_evidence": t["final_evidence"],
                "fallback_to_a2": t["fallback_to_a2"], "stop_reason": t["stop_reason"],
                "agent_steps": t["agent_steps"], "tool_calls": t["tool_calls"],
                "tool_names": t["tool_names"], "agent_model_calls": t["agent_model_calls"],
                "incremental_cost_usd": t["total_incremental_cost_usd"],
                "incremental_input_tokens": t["total_input_tokens"],
                "incremental_output_tokens": t["total_output_tokens"],
                "incremental_latency_s": t["wall_seconds"],
            })
        else:
            a3_rows.append({
                "case_id": cid, "gold_label": a2["gold_label"], "triggered": False,
                "a2_label": a2["predicted_label"], "a2_evidence": a2.get("evidence") or [],
                "a3_label": a2["predicted_label"], "a3_evidence": a2.get("evidence") or [],
                "fallback_to_a2": False, "stop_reason": "not_triggered",
                "agent_steps": 0, "tool_calls": 0, "tool_names": [], "agent_model_calls": 0,
                "incremental_cost_usd": 0.0, "incremental_input_tokens": 0,
                "incremental_output_tokens": 0, "incremental_latency_s": 0.0,
            })
    assert len(a3_rows) == 150
    with open(RESULTS_DIR / "run_E11_A3_train_cases.jsonl", "w") as f:
        for r in a3_rows:
            f.write(json.dumps(r, default=str) + "\n")

    post_run_ledger = reconstruction_spend_so_far()
    total_incremental_spend = post_run_ledger - pre_run_ledger
    with open(RESULTS_DIR / "run_E11_wall_seconds.json", "w") as f:
        json.dump({"total_wall_seconds": total_wall_s, "n_triggered": 15, "run_id": run_id,
                    "pre_run_ledger_usd": pre_run_ledger, "post_run_ledger_usd": post_run_ledger,
                    "total_incremental_spend_usd": total_incremental_spend}, f, indent=2)

    print(f"\nwrote {RESULTS_DIR / 'agent_traces.jsonl'} (15 cases)")
    print(f"wrote {RESULTS_DIR / 'run_E11_A3_train_cases.jsonl'} (150 cases)")
    print(f"Total wall time: {total_wall_s:.1f}s. Incremental spend: ${total_incremental_spend:.4f}. "
          f"Ledger: ${pre_run_ledger:.4f} -> ${post_run_ledger:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
