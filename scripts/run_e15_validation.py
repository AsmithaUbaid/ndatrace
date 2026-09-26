#!/usr/bin/env python3
"""E15 fresh-DEV validation: 138 GPT-5-mini + GPT-P0 + FULL-context calls, ONCE. Concurrency 5, timeout 60s, 5-consecutive-failure circuit breaker.
Logs operational health only (no labels/metrics). Policies are applied OFFLINE afterwards (scripts/analyze_e15_validation.py)."""
from __future__ import annotations
import hashlib, json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(REPO))
from evaluation.budget import check_budget_against_ledger, record_spend, reconstruction_spend_so_far  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

D = REPO / "experiments/E15_review_routing"; R = D / "results"
EXPERIMENT_ID, RUN_ID = "E15_review_routing", "e15_dev_routing_validation"
MODEL, PROVIDER, TIMEOUT, CONC, BREAKER = "openai/gpt-5-mini", "openrouter", 60, 5, 5
P0_HASH = "3fcc7c95cf1287c292e403f12b307c9d912278ce"; CONSERVATIVE, PLANNING, RESERVE_FRAC = 0.4582, 5.00, 0.25
USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"
LEAK = {"gold_label", "gold_span_indices", "choice", "relevance_flag", "expected_prediction", "failure_bucket"}
lock = threading.Lock(); now = lambda: datetime.now(timezone.utc).isoformat()


def main() -> int:
    man = json.load(open(D / "DEV_ROUTING_v1.json")); cases = man["cases"]
    full = {c["case_id"]: c for c in json.load(open(D / "DEV_ROUTING_v1_FULL_CONTEXT.json"))["cases"]}
    dev = {d["id"]: d["text"] for d in json.load(open(REPO / "data/contractnli/dev.json"))["documents"]}
    SYSTEM = open(REPO / "prompts/reconstruction_v2/gpt_p0.txt", newline="").read(); h = hashlib.sha1(SYSTEM.encode()).hexdigest()
    pre = reconstruction_spend_so_far(); gate = check_budget_against_ledger(CONSERVATIVE, PLANNING, RESERVE_FRAC)
    out_path = R / "run_E15_validation_cases.jsonl"
    checks = {"manifest_frozen_138": man["status"].startswith("FROZEN") and len(cases) == 138 and man["seed"] == 1500,
              "full_ids_same_order": list(full) == [c["case_id"] for c in cases], "full_context_is_complete_dev_doc": all(full[c["case_id"]]["context_text"] == dev[c["document_id"]] for c in cases),
              "no_truth_in_model_facing": not any(LEAK & set(c) for c in full.values()), "prompt_is_gpt_p0": h == P0_HASH,
              "ledger_approx_2_8044": abs(pre - 2.8044) < 0.001, "no_existing_e15_outputs": not out_path.exists(), "no_existing_e15_ledger_rows": "e15_" not in open(REPO / "results/budget/reconstruction_spend_ledger.csv").read(),
              "budget_gate_pass": bool(gate.allowed)}
    json.dump({"checks": checks, "pre_run_ledger_usd": pre, "gate_arithmetic": pre + CONSERVATIVE + 1.25, "max_concurrency": CONC, "timeout_seconds": TIMEOUT, "timestamp": now()}, open(R / "pre_run_verification.json", "w"), indent=2)
    print(json.dumps(checks, indent=1), f"\npre-run ledger ${pre:.5f}; gate {pre + CONSERVATIVE + 1.25:.3f} <= 5.00", flush=True)
    if not all(checks.values()): print("PRE-RUN VERIFICATION FAILED; no hosted call made."); return 1
    gw = ModelGateway(model=MODEL, timeout_seconds=TIMEOUT); state = {"consec": 0, "stop": None, "spend": 0.0, "done": 0}; stop = threading.Event(); t_all = time.perf_counter()

    def work(case, out):
        if stop.is_set(): return
        ctxt = full[case["case_id"]]["context_text"]; user_msg = USER_TEMPLATE.format(hypothesis_text=case["hypothesis_text"], context_text=ctxt)
        rec = {"experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "arm": "full", "context_mode": "full_nda_text", "prompt_id": "gpt_p0", "prompt_hash": h, "case_id": case["case_id"], "document_id": case["document_id"],
               "hypothesis_id": case["hypothesis_id"], "gold_label": case["gold_label"], "model": MODEL, "provider": PROVIDER, "timeout_seconds": TIMEOUT, "execution": {"mode": "bounded_concurrency", "max_concurrency": CONC},
               "context_chars": len(ctxt), "model_input_user": user_msg, "start_timestamp": now()}
        t0 = time.perf_counter()
        try:
            r = gw.complete(system_prompt=SYSTEM, user_prompt=user_msg, temperature=0.0); p = parse_structured_output(r.content); ev = validate_evidence(ctxt, p.evidence, p.predicted_label or "")
            rec.update({"input_tokens": r.tokens_in, "output_tokens": r.tokens_out, "generation_latency_ms": r.latency_ms, "wall_latency_s": round(time.perf_counter() - t0, 2), "retry_count": r.num_retries, "cost_usd": r.cost_usd,
                        "raw_response": p.raw_response, "strict_parse_valid": p.strict_parse_valid, "recovered_parse_valid": p.recovered_parse_valid, "parse_status": p.parse_status, "predicted_label": p.predicted_label,
                        "evidence": p.evidence, "evidence_valid": ev.is_valid, "evidence_all_verbatim": ev.all_verbatim, "evidence_label_consistent": ev.label_evidence_consistent,
                        "evidence_hallucinated_count": len(ev.hallucinated_quotes), "error_type": p.error_type, "error_message": p.error_message}); ok, status = True, p.parse_status.upper()
        except ModelError as e:
            rec.update({"input_tokens": None, "output_tokens": None, "generation_latency_ms": None, "wall_latency_s": round(time.perf_counter() - t0, 2), "retry_count": getattr(e, "num_retries", None), "cost_usd": None,
                        "raw_response": "", "strict_parse_valid": False, "recovered_parse_valid": False, "parse_status": "invalid", "predicted_label": None, "evidence": [], "evidence_valid": None,
                        "evidence_all_verbatim": None, "evidence_label_consistent": None, "evidence_hallucinated_count": None, "error_type": "TIMEOUT" if "time" in str(e).lower() else "MODEL_ERROR", "error_message": str(e)}); ok, status = False, "ERROR"
        rec["end_timestamp"] = now()
        with lock:
            out.write(json.dumps(rec) + "\n"); out.flush()
            if ok:
                record_spend(experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL, input_tokens=r.tokens_in, output_tokens=r.tokens_out, cost_usd=r.cost_usd, run_id=RUN_ID); state["spend"] += r.cost_usd; state["consec"] = 0
            else: state["consec"] += 1
            state["done"] += 1; print(f"[{state['done']}/138] {status:9} {case['case_id']:22} ({rec['wall_latency_s']}s, ${state['spend']:.4f})", flush=True)
            if pre + state["spend"] >= PLANNING * (1 - RESERVE_FRAC) * 0.90 and not stop.is_set(): state["stop"] = "BUDGET SAFETY STOP"; stop.set()
            if state["consec"] >= BREAKER and not stop.is_set(): state["stop"] = f"CIRCUIT BREAKER: {BREAKER} consecutive failures"; stop.set()

    with open(out_path, "x") as out, ThreadPoolExecutor(max_workers=CONC) as ex: list(ex.map(lambda c: work(c, out), cases))
    recs = [json.loads(l) for l in open(out_path)]; ids = [r["case_id"] for r in recs]
    verify = {"records_138": len(recs) == 138, "no_duplicates": len(set(ids)) == len(ids), "all_ids": set(ids) == {c["case_id"] for c in cases}, "all_successful": not any(r.get("error_type") for r in recs)}
    json.dump({"spend_usd": state["spend"], "wall_seconds": time.perf_counter() - t_all, "stopped": state["stop"], "successful_calls": sum(not r.get("error_type") for r in recs), "failed_calls": sum(bool(r.get("error_type")) for r in recs),
               "verify": verify, "pre_run_ledger_usd": pre, "post_run_ledger_usd": reconstruction_spend_so_far(), "completed": not state["stop"] and all(verify.values())}, open(R / "run_E15_wall_seconds.json", "w"), indent=2)
    print(f"DONE spend ${state['spend']:.4f} stop={state['stop']} verify={verify} ledger ${reconstruction_spend_so_far():.5f}", flush=True); return 0 if all(verify.values()) and not state["stop"] else 2


if __name__ == "__main__":
    sys.exit(main())
