#!/usr/bin/env python3
"""E17: frozen local Qwen (qwen2.5:7b-instruct-ctx16k) on ALL 2,091 TEST cases, sequential, FULL context, GPT-P0 bytes + shared 'NDA context:' template, temperature 0.0, timeout 60s.
Flushes after every case. Failed/timeout/unparseable rows are recorded, never dropped or rerun. Resumable only by continuing the same frozen case order."""
import json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e17_common as C
from evaluation.structured_output import parse_structured_output
from pipeline.evidence_validator import validate_evidence
from pipeline.model_gateway import ModelError, ModelGateway

MODEL, TIMEOUT, NUM_CTX, OUT_RESERVE = "qwen2.5:7b-instruct-ctx16k", 60, 16384, 1024
now = lambda: datetime.now(timezone.utc).isoformat()

def main():
    F = C.load_frozen(); out = C.E17 / "results/run_E17_qwen_full_test_cases.jsonl"
    ol = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout; assert MODEL in ol, "ollama model missing"
    show = subprocess.run(["ollama", "show", MODEL], capture_output=True, text=True).stdout; assert "num_ctx" in show and "16384" in show, "ctx16k configuration changed"
    pf = json.load(open(C.E17 / "results/preflight.json"))["local_qwen"]; assert pf["context_safe"] and pf["max_request_plus_reserve"] < NUM_CTX and pf["cases_exceeding_context"] == 0
    from transformers import AutoTokenizer
    tk = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct"); mx = 0
    for c in F["all"]:
        ids = tk.apply_chat_template([{"role": "system", "content": C.SYSTEM}, {"role": "user", "content": F["user"](c)}], add_generation_prompt=True, tokenize=True); ids = ids["input_ids"] if hasattr(ids, "keys") else ids; mx = max(mx, len(ids))
    assert mx + OUT_RESERVE < NUM_CTX and mx == 8073, f"context re-check differs from Stage A (max {mx})"
    free = shutil.disk_usage(C.E17).free; assert free > 5e9, "insufficient disk"; assert os.access(C.E17 / "results", os.W_OK)
    done = {}
    if out.exists():
        for l in open(out): r = json.loads(l); done[r["case_id"]] = r
        order = [c["case_id"] for c in F["all"]][:len(done)]; assert list(done) == order, "resume must continue the same frozen order"
    print(f"pre-checks OK (max prompt {mx} tok, disk {free/1e9:.0f} GB free); resuming from {len(done)}", flush=True)
    gw = ModelGateway.local(model=MODEL, timeout_seconds=TIMEOUT); t_all = time.perf_counter(); n_err = 0
    with open(out, "a") as f:
        for i, c in enumerate(F["all"]):
            if c["case_id"] in done: continue
            ctx = F["ctx"](c); rec = {"run_id": "e17_qwen_full_test", "case_id": c["case_id"], "document_id": c["document_id"], "hypothesis_id": c["hypothesis_id"], "gold_label": c["gold_label"], "model": MODEL, "context_chars": len(ctx), "start_timestamp": now()}
            t0 = time.perf_counter()
            try:
                r = gw.complete(system_prompt=C.SYSTEM, user_prompt=F["user"](c), temperature=0.0); p = parse_structured_output(r.content); ev = validate_evidence(ctx, p.evidence, p.predicted_label or "")
                rec.update({"input_tokens": r.tokens_in, "output_tokens": r.tokens_out, "generation_latency_ms": r.latency_ms, "wall_latency_s": round(time.perf_counter() - t0, 2), "retry_count": r.num_retries, "cost_usd": 0.0, "raw_response": p.raw_response,
                            "strict_parse_valid": p.strict_parse_valid, "recovered_parse_valid": p.recovered_parse_valid, "parse_status": p.parse_status, "predicted_label": p.predicted_label, "evidence": p.evidence, "evidence_hallucinated_count": len(ev.hallucinated_quotes),
                            "evidence_label_consistent": ev.label_evidence_consistent, "error_type": p.error_type, "error_message": p.error_message}); status = p.parse_status.upper()
            except ModelError as e:
                n_err += 1; rec.update({"input_tokens": None, "output_tokens": None, "wall_latency_s": round(time.perf_counter() - t0, 2), "retry_count": getattr(e, "num_retries", None), "cost_usd": 0.0, "raw_response": "", "parse_status": "invalid", "predicted_label": None,
                                        "evidence": [], "evidence_hallucinated_count": 0, "error_type": "TIMEOUT" if "time" in str(e).lower() else "MODEL_ERROR", "error_message": str(e)}); status = "ERROR"
            rec["end_timestamp"] = now(); f.write(json.dumps(rec) + "\n"); f.flush(); os.fsync(f.fileno())
            if (i + 1) % 25 == 0 or status == "ERROR": print(f"[{i+1}/2091] {status} last={rec['wall_latency_s']}s errors={n_err} elapsed={(time.perf_counter()-t_all)/3600:.2f}h", flush=True)
    json.dump({"cases": len(F["all"]), "wall_seconds_this_session": time.perf_counter() - t_all, "errors_this_session": n_err, "api_cost_usd": 0.0, "completed": True}, open(C.E17 / "results/run_E17_qwen_wall.json", "w"), indent=1)
    print("QWEN DONE", flush=True)

if __name__ == "__main__":
    main()
