#!/usr/bin/env python3
"""Approved, scorer-free runner for the frozen E11 agent-controller Prompt V2 ablation."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.budget import record_spend  # noqa: E402
import pipeline.agent_v2 as agent_v2  # noqa: E402
from pipeline.config import settings  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

EXPERIMENT_ID = "E11_addendum_agent_prompt_v2_ablation"
MODEL = "openai/gpt-5-mini"
PROVIDER = "openrouter"
TEMPERATURE = 0.0
MAX_RETRIES = 1
REQUEST_TIMEOUT_SECONDS = 30
RUN_COST_CEILING_USD = 3.00
BALANCE_RESERVE_USD = 0.25
# The existing controller's own estimated per-case circuit breaker is $0.01. Keeping that much
# unspent before each request makes the run-level check conservative rather than retrospective.
NEXT_CALL_COST_HEADROOM_USD = 0.01

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
RETRIEVAL_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
BASE_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"
PROMPT_V2_PATH = REPO / "experiments/E11_selective_agent_evaluation/addendum_agent_prompt_ablation/prompt_v2.txt"
CONFIG_PATH = REPO / "experiments/E11_selective_agent_evaluation/addendum_agent_prompt_ablation/config.json"
OUT = REPO / "experiments/E11_selective_agent_evaluation/addendum_agent_prompt_ablation"
RESULTS = OUT / "results"
TRACE_PATH = RESULTS / "raw_v2.jsonl"
STATE_PATH = RESULTS / "run_state.json"
EXECUTION_MANIFEST_PATH = OUT / "execution_manifest.json"

EXPECTED_SHA1 = {
    MANIFEST_PATH: "3a5491ab0de1c101b8d1043ff4dffa21029a58f6",
    RETRIEVAL_PATH: "af5b07ebff19f596375cfdea6f25530d4511c903",
    BASE_PATH: "c1f801adfe6864884341db5d1d11919f18abfec2",
    PROMPT_V2_PATH: "d3c059dca56300825c788c6653c3752470fe74ed",
    REPO / "prompts/reconstruction_v2/gpt_p0.txt": "3fcc7c95cf1287c292e403f12b307c9d912278ce",
    REPO / "pipeline/agent_v2.py": "6f7290f9402ced36da83723c9880c59b50a89041",
    REPO / "pipeline/agent_tools_v2.py": "f44ac1f35bbdbf65d266d70914b683a312e42130",
}


class RunBudgetExceeded(RuntimeError):
    pass


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def provider_key_status() -> dict:
    request = urllib.request.Request(
        settings.openrouter_base_url.rstrip("/") + "/auth/key",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())["data"]


def verify_frozen_preflight() -> tuple[list[dict], dict[str, dict], dict[str, dict], dict[int, str]]:
    config = json.loads(CONFIG_PATH.read_text())
    for path, expected in EXPECTED_SHA1.items():
        actual = sha1(path)
        assert actual == expected, f"frozen artifact changed: {path}: {actual} != {expected}"
    assert config["experimental_variable"]["v2_prompt_sha1"] == EXPECTED_SHA1[PROMPT_V2_PATH]
    assert config["population"]["manifest_sha1"] == EXPECTED_SHA1[MANIFEST_PATH]
    assert config["forecast"]["hard_run_cost_ceiling_usd"] == RUN_COST_CEILING_USD == 3.00
    assert agent_v2.MAX_AGENT_STEPS == config["frozen_agent"]["max_agent_steps"] == 3
    assert agent_v2.MAX_TOOL_CALLS == config["frozen_agent"]["max_tool_calls"] == 2
    assert MAX_RETRIES == config["frozen_agent"]["max_retries"] == 1

    manifest = json.loads(MANIFEST_PATH.read_text())["cases"]
    assert len(manifest) == 150
    assert all(row["case_id"].startswith("train::") for row in manifest)
    assert sum(row["case_id"].startswith("test::") for row in manifest) == 0
    assert "test" not in str(MANIFEST_PATH).lower()

    retrieved = {row["case_id"]: row for row in json.loads(RETRIEVAL_PATH.read_text())["cases"]}
    base = {}
    for row in load_jsonl(BASE_PATH):
        # Remove scorer fields immediately. Gold never enters the execution manifest or loop.
        base[row["case_id"]] = {key: row.get(key) for key in (
            "case_id", "document_id", "hypothesis_id", "predicted_label", "evidence",
            "parse_status", "error_type",
        )}
    train_docs = {
        row["id"]: row["text"]
        for row in json.loads((REPO / "data/contractnli/train.json").read_text())["documents"]
    }
    ids = [row["case_id"] for row in manifest]
    assert len(set(ids)) == 150 and set(ids) == set(retrieved) == set(base)
    return manifest, retrieved, base, train_docs


def main() -> int:
    manifest, retrieved, base, train_docs = verify_frozen_preflight()
    # Experiment-only prompt selection. No repository or production-runtime file is modified.
    agent_v2.CONTROL_PROMPT_PATH = PROMPT_V2_PATH

    execution_cases = [{
        "case_id": row["case_id"],
        "document_id": row["document_id"],
        "hypothesis_id": row["hypothesis_id"],
        "hypothesis_text": row["hypothesis_text"],
    } for row in manifest]
    execution_manifest = {
        "status": "FROZEN_AGENT_PROMPT_V2",
        "split": "TRAIN",
        "test_cases": 0,
        "n": 150,
        "contains_gold": False,
        "model": MODEL,
        "provider": PROVIDER,
        "temperature": TEMPERATURE,
        "force_agent": True,
        "prompt_v2_sha1": sha1(PROMPT_V2_PATH),
        "manifest_sha1": sha1(MANIFEST_PATH),
        "max_steps": agent_v2.MAX_AGENT_STEPS,
        "max_tool_calls": agent_v2.MAX_TOOL_CALLS,
        "retry_limit": MAX_RETRIES,
        "hard_run_budget_usd": RUN_COST_CEILING_USD,
        "cases": execution_cases,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    if EXECUTION_MANIFEST_PATH.exists():
        assert json.loads(EXECUTION_MANIFEST_PATH.read_text()) == execution_manifest
    else:
        EXECUTION_MANIFEST_PATH.write_text(json.dumps(execution_manifest, indent=2) + "\n")

    traces = load_jsonl(TRACE_PATH)
    completed = {row["case_id"] for row in traces}
    assert len(completed) == len(traces), "duplicate completed case in V2 trace"
    assert completed <= {row["case_id"] for row in manifest}
    spent = sum(call.get("cost_usd") or 0.0 for row in traces for call in row["call_log"])

    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text())
        run_id = state["run_id"]
    else:
        run_id = uuid.uuid4().hex[:12]
        state = {"run_id": run_id, "started_at": datetime.now(timezone.utc).isoformat()}
        STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")

    key = provider_key_status()
    remaining_balance = float(key["limit_remaining"])
    required_balance = (RUN_COST_CEILING_USD + BALANCE_RESERVE_USD if not traces
                        else max(0.0, RUN_COST_CEILING_USD - spent) + BALANCE_RESERVE_USD)
    print("PREFLIGHT PASS: V2 SHA-1", sha1(PROMPT_V2_PATH), flush=True)
    print("PREFLIGHT PASS: manifest SHA-1", sha1(MANIFEST_PATH), flush=True)
    print("PREFLIGHT PASS: TEST cases=0, max_steps=3, max_tool_calls=2, retries=1, budget=$3.00", flush=True)
    print(f"OpenRouter balance ${remaining_balance:.6f}; required ${required_balance:.6f}", flush=True)
    if remaining_balance < required_balance:
        print("BUDGET PREFLIGHT FAILED before hosted calls", flush=True)
        return 2
    print("BALANCE PREFLIGHT PASS", flush=True)

    gateway = ModelGateway(model=MODEL, max_retries=MAX_RETRIES, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    for index, row in enumerate(execution_cases, 1):
        cid = row["case_id"]
        if cid in completed:
            continue
        # Fail closed if the only treatment or tool implementation changes during a long run.
        assert sha1(PROMPT_V2_PATH) == EXPECTED_SHA1[PROMPT_V2_PATH]
        assert sha1(REPO / "pipeline/agent_tools_v2.py") == EXPECTED_SHA1[REPO / "pipeline/agent_tools_v2.py"]
        call_log = []

        def model_call(system_prompt: str, user_prompt: str) -> str:
            nonlocal spent
            assert system_prompt == PROMPT_V2_PATH.read_text()
            if spent + NEXT_CALL_COST_HEADROOM_USD > RUN_COST_CEILING_USD:
                raise RunBudgetExceeded(
                    f"next-call headroom would threaten ${RUN_COST_CEILING_USD:.2f} run ceiling"
                )
            try:
                response = gateway.complete(system_prompt, user_prompt, temperature=TEMPERATURE)
            except ModelError as exc:
                call_log.append({
                    "error": type(exc).__name__, "input_tokens": 0, "output_tokens": 0,
                    "latency_ms": 0.0, "cost_usd": 0.0, "retry_count": MAX_RETRIES,
                    "raw_response": "",
                })
                return ""
            record = {
                "input_tokens": response.tokens_in,
                "output_tokens": response.tokens_out,
                "latency_ms": response.latency_ms,
                "cost_usd": response.cost_usd,
                "retry_count": response.num_retries,
                "raw_response": response.content,
                "error": None,
            }
            if spent + response.cost_usd > RUN_COST_CEILING_USD:
                raise RunBudgetExceeded("provider response would exceed run ceiling")
            call_log.append(record)
            spent += response.cost_usd
            record_spend(
                experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL,
                input_tokens=response.tokens_in, output_tokens=response.tokens_out,
                cost_usd=response.cost_usd, run_id=run_id,
            )
            return response.content

        b = base[cid]
        started = time.perf_counter()
        try:
            trace = agent_v2.run_selective_agent(
                case_id=cid,
                doc_text=train_docs[row["document_id"]],
                hypothesis_text=row["hypothesis_text"],
                a2_context_chunks=retrieved[cid]["ranked_chunk_text"],
                a2_label=b["predicted_label"],
                a2_evidence=b.get("evidence") or [],
                model_call=model_call,
                force_agent=True,
            )
        except RunBudgetExceeded as exc:
            print(f"SAFE ABORT: {exc}", flush=True)
            return 3
        record = {
            **trace.to_dict(),
            "run_id": run_id,
            "experiment_id": EXPERIMENT_ID,
            "prompt_version": "agent_prompt_v2",
            "prompt_sha1": EXPECTED_SHA1[PROMPT_V2_PATH],
            "document_id": row["document_id"],
            "hypothesis_id": row["hypothesis_id"],
            "base_parse_status": b["parse_status"],
            "call_log": call_log,
            "total_input_tokens": sum(call["input_tokens"] for call in call_log),
            "total_output_tokens": sum(call["output_tokens"] for call in call_log),
            "total_incremental_cost_usd": sum(call["cost_usd"] for call in call_log),
            "wall_seconds": time.perf_counter() - started,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with TRACE_PATH.open("a") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
        completed.add(cid)
        print(
            f"[{index}/150] {cid} final={trace.final_label} steps={trace.agent_steps} "
            f"tools={trace.tool_calls} fallback={trace.fallback_to_a2} "
            f"cost=${record['total_incremental_cost_usd']:.4f} spent=${spent:.4f} "
            f"wall={record['wall_seconds']:.1f}s",
            flush=True,
        )

    state.update({
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "completed_cases": len(completed),
        "total_incremental_cost_usd": spent,
    })
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    print(f"V2 run complete: {len(completed)}/150, incremental cost ${spent:.6f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
