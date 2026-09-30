#!/usr/bin/env python3
"""E16 Phase B hosted runner: 40 frozen requests, ONCE. Concurrency 5, timeout 60s, 5-consecutive-failure breaker. Logs operational health only."""
from __future__ import annotations
import hashlib, json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(REPO))
from evaluation.budget import record_spend, reconstruction_spend_so_far  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

D = REPO / "experiments/E16_robustness_security"; R = D / "results"
EXPERIMENT_ID, RUN_ID = "E16_robustness_security", "e16_hosted_robustness"
MODEL, PROVIDER, TIMEOUT, CONC, BREAKER = "openai/gpt-5-mini", "openrouter", 60, 5, 5
P0_HASH = "3fcc7c95cf1287c292e403f12b307c9d912278ce"; USER_TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"
lock = threading.Lock(); now = lambda: datetime.now(timezone.utc).isoformat()


def main() -> int:
    man = json.load(open(D / "E16_hosted_requests.json")); reqs = man["requests"]; gate = json.load(open(R / "budget_gate.json"))
    SYSTEM = open(REPO / "prompts/reconstruction_v2/gpt_p0.txt", newline="").read(); h = hashlib.sha1(SYSTEM.encode()).hexdigest()
    pre = reconstruction_spend_so_far(); out_path = R / "run_E16_hosted_cases.jsonl"
    checks = {"manifest_frozen_40": man["status"].startswith("FROZEN") and len(reqs) == 40 and sum(r["variant"] == "attack" for r in reqs) == 20,
              "manifest_hash_matches_gate_file": hashlib.sha256((D / "E16_hosted_requests.json").read_bytes()).hexdigest() == gate["manifest_sha256"],
              "prompt_is_gpt_p0": h == P0_HASH, "ledger_matches_gate_file": abs(pre - gate["ledger"]) < 1e-9, "budget_gate_pass": gate["pass"] and pre + gate["e16_conservative"] + gate["final_test_conservative"] + 1.25 <= 5.00,
              "no_existing_outputs": not out_path.exists(), "no_existing_e16_ledger_rows": "e16_" not in open(REPO / "results/budget/reconstruction_spend_ledger.csv").read()}
    json.dump({"checks": checks, "pre_run_ledger_usd": pre, "timestamp": now()}, open(R / "pre_run_verification.json", "w"), indent=2)
    print(json.dumps(checks, indent=1), f"\npre-run ledger ${pre:.5f}", flush=True)
    if not all(checks.values()): print("PRE-RUN VERIFICATION FAILED; no hosted call made."); return 1
    gw = ModelGateway(model=MODEL, timeout_seconds=TIMEOUT); state = {"consec": 0, "stop": None, "spend": 0.0, "done": 0}; stop = threading.Event(); t_all = time.perf_counter()

    def work(q, out):
        if stop.is_set(): return
        ctxt = q["context_text"]; user_msg = USER_TEMPLATE.format(hypothesis_text=q["hypothesis_text"], context_text=ctxt)
        rec = {"experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "request_id": q["request_id"], "pair_id": q["pair_id"], "variant": q["variant"], "family": q["family"], "gold_label": q["gold_label"], "model": MODEL, "provider": PROVIDER,
               "prompt_hash": h, "timeout_seconds": TIMEOUT, "context_chars": len(ctxt), "start_timestamp": now()}
        t0 = time.perf_counter()
        try:
            r = gw.complete(system_prompt=SYSTEM, user_prompt=user_msg, temperature=0.0); p = parse_structured_output(r.content); ev = validate_evidence(ctxt, p.evidence, p.predicted_label or "")
            rec.update({"input_tokens": r.tokens_in, "output_tokens": r.tokens_out, "generation_latency_ms": r.latency_ms, "wall_latency_s": round(time.perf_counter() - t0, 2), "retry_count": r.num_retries, "cost_usd": r.cost_usd,
                        "raw_response": p.raw_response, "strict_parse_valid": p.strict_parse_valid, "recovered_parse_valid": p.recovered_parse_valid, "parse_status": p.parse_status, "predicted_label": p.predicted_label,
                        "evidence": p.evidence, "evidence_hallucinated_count": len(ev.hallucinated_quotes), "evidence_label_consistent": ev.label_evidence_consistent, "error_type": p.error_type, "error_message": p.error_message}); ok, status = True, p.parse_status.upper()
        except ModelError as e:
            rec.update({"input_tokens": None, "output_tokens": None, "wall_latency_s": round(time.perf_counter() - t0, 2), "retry_count": getattr(e, "num_retries", None), "cost_usd": None, "raw_response": "", "parse_status": "invalid",
                        "predicted_label": None, "evidence": [], "error_type": "TIMEOUT" if "time" in str(e).lower() else "MODEL_ERROR", "error_message": str(e)}); ok, status = False, "ERROR"
        rec["end_timestamp"] = now()
        with lock:
            out.write(json.dumps(rec) + "\n"); out.flush()
            if ok: record_spend(experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL, input_tokens=r.tokens_in, output_tokens=r.tokens_out, cost_usd=r.cost_usd, run_id=RUN_ID); state["spend"] += r.cost_usd; state["consec"] = 0
            else: state["consec"] += 1
            state["done"] += 1; print(f"[{state['done']}/40] {status:9} {q['request_id']:14} ({rec['wall_latency_s']}s, ${state['spend']:.4f})", flush=True)
            if pre + state["spend"] + 0.5 + 1.25 >= 5.00 and not stop.is_set(): state["stop"] = "BUDGET SAFETY STOP"; stop.set()
            if state["consec"] >= BREAKER and not stop.is_set(): state["stop"] = f"CIRCUIT BREAKER: {BREAKER} consecutive failures"; stop.set()

    with open(out_path, "x") as out, ThreadPoolExecutor(max_workers=CONC) as ex: list(ex.map(lambda q: work(q, out), reqs))
    recs = [json.loads(l) for l in open(out_path)]; ids = [r["request_id"] for r in recs]
    verify = {"records_40": len(recs) == 40, "no_duplicates": len(set(ids)) == 40, "all_ids": set(ids) == {q["request_id"] for q in reqs}, "no_provider_errors": not any(r.get("error_type") in ("TIMEOUT", "MODEL_ERROR") for r in recs)}
    json.dump({"spend_usd": state["spend"], "wall_seconds": time.perf_counter() - t_all, "stopped": state["stop"], "api_calls_completed": sum(r.get("cost_usd") is not None for r in recs), "parse_failures": sum(r["parse_status"] == "invalid" for r in recs),
               "verify": verify, "pre_run_ledger_usd": pre, "post_run_ledger_usd": reconstruction_spend_so_far()}, open(R / "run_E16_wall_seconds.json", "w"), indent=2)
    print(f"DONE spend ${state['spend']:.4f} stop={state['stop']} verify={verify} ledger ${reconstruction_spend_so_far():.5f}", flush=True); return 0 if all(verify.values()) and not state["stop"] else 2


if __name__ == "__main__":
    sys.exit(main())
