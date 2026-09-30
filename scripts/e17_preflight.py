#!/usr/bin/env python3
"""E17 Stage A preflight: exact frozen requests for hosted GPT (150) and local Qwen (2,091); token distributions; Qwen context safety; runtime + cost forecasts; budget gate. ZERO model calls; no predictions."""
from __future__ import annotations
import csv, hashlib, json, statistics as st, sys
from pathlib import Path
import numpy as np
import tiktoken
from transformers import AutoTokenizer
REPO = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(REPO))
OUT = REPO / "experiments/E17_final_test"
test = json.load(open(REPO / "data/contractnli/test.json")); DOC = {d["id"]: d["text"] for d in test["documents"]}; HYP = {k: v["hypothesis"] for k, v in test["labels"].items()}
SYS = open(REPO / "prompts/reconstruction_v2/gpt_p0.txt", newline="").read(); P0 = hashlib.sha1(SYS.encode()).hexdigest(); assert P0 == "3fcc7c95cf1287c292e403f12b307c9d912278ce"
TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"   # identical shared template used by E13/E15/E16 GPT runs
user = lambda c: TEMPLATE.format(hypothesis_text=HYP[c["hypothesis_id"]], context_text=DOC[c["document_id"]])
D = lambda a: {"n": len(a), "mean": float(np.mean(a)), "median": float(np.median(a)), "p90": float(np.percentile(a, 90)), "p95": float(np.percentile(a, 95)), "max": float(max(a))}
hosted = json.load(open(OUT / "manifests/TEST_HOSTED_v1.json"))["cases"]; allc = json.load(open(OUT / "manifests/TEST_ALL_2091_cases.json"))["cases"]

# ---- hosted GPT: exact 150 requests
enc = tiktoken.get_encoding("cl100k_base"); gtok = [int((len(enc.encode(SYS)) + len(enc.encode(user(c)))) * 0.9907) for c in hosted]   # 0.9907 = calibration measured on E12B real API tokens
req_hash = hashlib.sha256("\n\x1e".join(SYS + "\x1f" + user(c) for c in hosted).encode()).hexdigest()
def outs(p): return [json.loads(l)["output_tokens"] for l in open(p)]
o_hist = outs(REPO / "experiments/E13_gpt_context_architecture/results/run_E13_gpt_full_cases.jsonl") + outs(REPO / "experiments/E15_review_routing/results/run_E15_validation_cases.jsonl")
OUT_MEAN, OUT_P90 = float(np.mean(o_hist)), float(np.percentile(o_hist, 90)); IN_P, OUT_P = 0.25e-6, 2.00e-6
exp = sum(t * IN_P + OUT_MEAN * OUT_P for t in gtok); cons = sum(t * IN_P + OUT_P90 * OUT_P for t in gtok)
led = sum(float(x["cost_usd"] or 0) for x in csv.DictReader(open(REPO / "results/budget/reconstruction_spend_ledger.csv")))
gate = {"ledger": led, "conservative_hosted": cons, "reserve": 1.25, "sum": led + cons + 1.25, "plan": 5.0, "pass": led + cons + 1.25 <= 5.0, "headroom_under_plan": 5.0 - (led + cons + 1.25), "max_allowed_conservative": 5.0 - 1.25 - led}
gpt = {"n_requests": 150, "requests_sha256": req_hash, "system_prompt_sha1": P0, "model": "openai/gpt-5-mini", "request_tokens": D(gtok), "output_tokens_hist_288_calls": {"mean": OUT_MEAN, "p90": OUT_P90}, "expected_cost": exp, "expected_cost_per_call": exp / 150,
       "conservative_cost": cons, "conservative_cost_per_call": cons / 150, "pricing_per_million": {"input": 0.25, "output": 2.00}, "hist_cost_per_call_E13_E15_mean": 0.002152, "budget_gate": gate}

# ---- Qwen: exact 2,091 requests through the real Qwen2.5 tokenizer + chat template
tk = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct"); qtok = []
for c in allc:
    ids = tk.apply_chat_template([{"role": "system", "content": SYS}, {"role": "user", "content": user(c)}], add_generation_prompt=True, tokenize=True)
    qtok.append(len(ids["input_ids"]) if hasattr(ids, "keys") else len(ids))
NUM_CTX, OUT_RESERVE = 16384, 1024
qmax = max(qtok); over = [c["case_id"] for c, t in zip(allc, qtok) if t + OUT_RESERVE > NUM_CTX]
# runtime from historical E05 local-Qwen (150 TRAIN, sequential): latency vs Ollama-reported input tokens
e05 = [json.loads(l) for l in open(REPO / "experiments/E05_full_context/results/run_E05_A1_train_cases.jsonl")]; e05 = [x for x in e05 if x.get("wall_latency_s") and x.get("input_tokens")]
x = np.array([r["input_tokens"] for r in e05], float); y = np.array([r["wall_latency_s"] for r in e05], float); b, a = np.polyfit(x, y, 1); res = y - (a + b * x)
pred = a + b * np.array(qtok, float); exp_s = float(pred.sum()); cons_s = float((pred + np.percentile(res, 90)).sum())
mean_s = float(y.mean()) * len(qtok); p90_s = float(np.percentile(y, 90)) * len(qtok)
qwen = {"n_requests": 2091, "model": "qwen2.5:7b-instruct-ctx16k (num_ctx=16384 baked into Modelfile)", "system_prompt_sha1": P0, "request_tokens_qwen_tokenizer": D(qtok), "num_ctx": NUM_CTX, "output_reserve_tokens": OUT_RESERVE,
        "max_request_plus_reserve": qmax + OUT_RESERVE, "cases_exceeding_context": len(over), "context_safe": not over, "context_headroom_tokens_at_max": NUM_CTX - qmax - OUT_RESERVE,
        "runtime_forecast_hours": {"expected_regression": exp_s / 3600, "conservative_regression_plus_p90_resid": cons_s / 3600, "hist_mean_latency_x_n": mean_s / 3600, "hist_p90_latency_x_n": p90_s / 3600},
        "hist_E05": {"n": len(e05), "mean_s": float(y.mean()), "median_s": float(np.median(y)), "p90_s": float(np.percentile(y, 90)), "max_s": float(y.max()), "fit_s_per_1k_tokens": float(b * 1000), "fit_intercept_s": float(a)}}
json.dump({"hosted_gpt": gpt, "local_qwen": qwen, "shared_template": TEMPLATE, "note": "no model calls; TEST content used only to construct requests and count tokens"}, open(OUT / "results/preflight.json", "w"), indent=1)
print(json.dumps({"hosted_gpt": gpt, "local_qwen": qwen}, indent=1))
