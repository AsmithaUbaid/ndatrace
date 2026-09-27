#!/usr/bin/env python3
"""Stage E1: resumable full-agent diagnostic over frozen TRAIN_ARCH_v1.

The runner is deliberately scorer-free: it never loads gold labels/evidence, correctness,
failure taxonomy, or TEST.  It appends one raw trace per completed case and records every
successful hosted call in the existing reconstruction spend ledger.
"""

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
from pipeline.agent_v2 import CROSS_REFERENCE_PATTERNS, run_selective_agent  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402
from pipeline.config import settings  # noqa: E402

EXPERIMENT_ID = "E11_addendum_full_agent_E1"
MODEL = "openai/gpt-5-mini"
PROVIDER = "openrouter"
MAX_RETRIES = 1
REQUEST_TIMEOUT_SECONDS = 30
RUN_COST_CEILING_USD = 2.10
CONSERVATIVE_FORECAST_USD = 1.95075
BALANCE_RESERVE_USD = 0.25

MANIFEST_PATH = REPO / "experiments/E05_full_context/TRAIN_ARCH_v1.json"
RETRIEVAL_PATH = REPO / "experiments/E07_standard_rag/TRAIN_ARCH_v1_RETRIEVED_retrieval_v1.json"
BASE_PATH = REPO / "experiments/E08B_stronger_model_diagnostic/results/run_E08B_A2_gpt5mini_train_cases.jsonl"
OUT = REPO / "experiments/E11_selective_agent_evaluation/addendum_selective_vs_full_agent"
RESULTS = OUT / "results"
TRACE_PATH = RESULTS / "raw_agent_traces.jsonl"
STATE_PATH = RESULTS / "run_state.json"
EXECUTION_MANIFEST_PATH = OUT / "execution_manifest.json"

EXPECTED_SHA1 = {
    MANIFEST_PATH: "3a5491ab0de1c101b8d1043ff4dffa21029a58f6",
    RETRIEVAL_PATH: "af5b07ebff19f596375cfdea6f25530d4511c903",
    BASE_PATH: "c1f801adfe6864884341db5d1d11919f18abfec2",
    REPO / "prompts/reconstruction_v2/gpt_p0.txt": "3fcc7c95cf1287c292e403f12b307c9d912278ce",
    REPO / "prompts/agent_v2_control.txt": "30781d7cac504c7887f2ae0dc63c1564f5430df9",
    REPO / "pipeline/agent_tools_v2.py": "f44ac1f35bbdbf65d266d70914b683a312e42130",
}


class RunBudgetExceeded(RuntimeError):
    pass


def sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def provider_key_status() -> dict:
    req = urllib.request.Request(
        settings.openrouter_base_url.rstrip("/") + "/auth/key",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read())["data"]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def r5_q10(base: dict, retrieved: dict) -> tuple[bool, list[str]]:
    context = "\n\n---\n\n".join(retrieved["ranked_chunk_text"])
    evidence = base.get("evidence") or []
    label = base.get("predicted_label")
    validation = validate_evidence(context, evidence, label or "")
    reasons = []
    if base.get("parse_status") not in ("strict", "recovered") or label is None or base.get("error_type"):
        reasons.append("unusable_parse_or_error")
    if label in ("Entailment", "Contradiction") and not evidence:
        reasons.append("EC_without_evidence")
    if validation.hallucinated_quotes:
        reasons.append("source_invalid_evidence")
    if label == "NotMentioned" and evidence:
        reasons.append("NotMentioned_with_evidence")
    scores = retrieved["ranked_chunk_rerank_scores"]
    if scores[0] <= -0.5165155708789826:
        reasons.append("weak_top1_reranker_score")
    if len(scores) < 2 or scores[0] - scores[1] <= 0.1690671443939209:
        reasons.append("ambiguous_top1_top2_margin")
    lowered = " ".join(retrieved["ranked_chunk_text"]).lower()
    if any(pattern in lowered for pattern in CROSS_REFERENCE_PATTERNS):
        reasons.append("cross_reference_cue")
    return bool(reasons), reasons


def main() -> int:
    for path, expected in EXPECTED_SHA1.items():
        actual = sha1(path)
        assert actual == expected, f"frozen artifact changed: {path} {actual} != {expected}"

    manifest = json.loads(MANIFEST_PATH.read_text())["cases"]
    retrieved = {row["case_id"]: row for row in json.loads(RETRIEVAL_PATH.read_text())["cases"]}
    # Immediately strip the historical row down to runtime fields; gold_label is never retained.
    base = {}
    for row in load_jsonl(BASE_PATH):
        base[row["case_id"]] = {key: row.get(key) for key in (
            "case_id", "document_id", "hypothesis_id", "predicted_label", "evidence",
            "parse_status", "error_type", "input_tokens", "output_tokens", "cost_usd",
            "generation_latency_ms",
        )}
    train_docs = {row["id"]: row["text"] for row in json.loads((REPO / "data/contractnli/train.json").read_text())["documents"]}

    assert len(manifest) == len(base) == len(retrieved) == 150
    ordered_ids = [row["case_id"] for row in manifest]
    assert set(ordered_ids) == set(base) == set(retrieved)

    execution_rows = []
    for row in manifest:
        cid = row["case_id"]
        routed, route_reasons = r5_q10(base[cid], retrieved[cid])
        execution_rows.append({
            "case_id": cid,
            "document_id": row["document_id"],
            "hypothesis_id": row["hypothesis_id"],
            "hypothesis_text": row["hypothesis_text"],
            "r5_q10": routed,
            "r5_q10_reasons": route_reasons,
        })
    assert sum(row["r5_q10"] for row in execution_rows) == 41
    assert all("gold" not in key.lower() for row in execution_rows for key in row)

    RESULTS.mkdir(parents=True, exist_ok=True)
    execution_manifest = {
        "status": "FROZEN_BEFORE_E1_HOSTED_CALLS",
        "split": "TRAIN",
        "n": 150,
        "contains_gold": False,
        "model": MODEL,
        "force_agent": True,
        "cases": execution_rows,
    }
    if EXECUTION_MANIFEST_PATH.exists():
        assert json.loads(EXECUTION_MANIFEST_PATH.read_text()) == execution_manifest
    else:
        EXECUTION_MANIFEST_PATH.write_text(json.dumps(execution_manifest, indent=2) + "\n")

    traces = load_jsonl(TRACE_PATH)
    completed = {row["case_id"] for row in traces}
    assert len(completed) == len(traces), "duplicate completed case in raw trace"
    spent = sum(call.get("cost_usd") or 0 for row in traces for call in row["call_log"])

    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text())
        run_id = state["run_id"]
    else:
        run_id = uuid.uuid4().hex[:12]
        state = {"run_id": run_id, "started_at": datetime.now(timezone.utc).isoformat()}
        STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")

    key = provider_key_status()
    remaining = float(key["limit_remaining"])
    required = max(0.0, CONSERVATIVE_FORECAST_USD - spent) + BALANCE_RESERVE_USD
    print(f"Provider balance ${remaining:.4f}; required for remaining conservative run+reserve ${required:.4f}")
    if remaining < required:
        print("BUDGET PREFLIGHT FAILED before hosted calls")
        return 2
    if spent >= RUN_COST_CEILING_USD and len(completed) < 150:
        print("RUN COST CEILING already reached; cannot resume")
        return 3

    gateway = ModelGateway(model=MODEL, max_retries=MAX_RETRIES, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
    run_start = time.perf_counter()

    for index, row in enumerate(execution_rows, 1):
        cid = row["case_id"]
        if cid in completed:
            continue
        call_log = []

        def model_call(system_prompt: str, user_prompt: str) -> str:
            nonlocal spent
            if spent >= RUN_COST_CEILING_USD:
                raise RunBudgetExceeded(f"run cost ceiling ${RUN_COST_CEILING_USD:.2f} reached")
            try:
                response = gateway.complete(system_prompt, user_prompt, temperature=0.0)
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
            call_log.append(record)
            spent += response.cost_usd
            record_spend(
                experiment_id=EXPERIMENT_ID, provider=PROVIDER, model=MODEL,
                input_tokens=response.tokens_in, output_tokens=response.tokens_out,
                cost_usd=response.cost_usd, run_id=run_id,
            )
            return response.content

        base_row = base[cid]
        started = time.perf_counter()
        try:
            trace = run_selective_agent(
                case_id=cid,
                doc_text=train_docs[row["document_id"]],
                hypothesis_text=row["hypothesis_text"],
                a2_context_chunks=retrieved[cid]["ranked_chunk_text"],
                a2_label=base_row["predicted_label"],
                a2_evidence=base_row["evidence"] or [],
                model_call=model_call,
                force_agent=True,
            )
        except RunBudgetExceeded as exc:
            print(str(exc))
            return 4
        wall_seconds = time.perf_counter() - started
        record = {
            **trace.to_dict(),
            "run_id": run_id,
            "experiment_id": EXPERIMENT_ID,
            "arm_source": "FULL_AGENT",
            "document_id": row["document_id"],
            "hypothesis_id": row["hypothesis_id"],
            "r5_q10": row["r5_q10"],
            "base_parse_status": base_row["parse_status"],
            "call_log": call_log,
            "total_input_tokens": sum(c["input_tokens"] for c in call_log),
            "total_output_tokens": sum(c["output_tokens"] for c in call_log),
            "total_incremental_cost_usd": sum(c["cost_usd"] for c in call_log),
            "wall_seconds": wall_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with TRACE_PATH.open("a") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
        completed.add(cid)
        print(
            f"[{index}/150] {cid} final={trace.final_label} steps={trace.agent_steps} "
            f"tools={trace.tool_calls} fallback={trace.fallback_to_a2} "
            f"cost=${record['total_incremental_cost_usd']:.4f} spent=${spent:.4f} wall={wall_seconds:.1f}s",
            flush=True,
        )

    state.update({
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "n_completed": len(completed),
        "incremental_cost_usd": spent,
        "last_session_wall_seconds": time.perf_counter() - run_start,
    })
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
    assert len(completed) == 150
    print(f"E1 full-agent run complete: 150/150, incremental cost ${spent:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
