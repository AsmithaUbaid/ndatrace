#!/usr/bin/env python3
"""
E01 Oracle runner (reconstruction-v2) — Stage B only. NOT executed during Stage A prep.

Runs the frozen TRAIN_ORACLE_v1 manifest through one model (local, Groq, or OpenRouter-hosted)
using the frozen prompts/oracle_v1.txt prompt and compact {"label": ...} schema. Before any
hosted call, checks the reconstruction-v2 budget gate (evaluation.budget.check_budget_against_ledger)
and refuses to proceed if it would exceed the protected reserve. Records every successful
hosted call to the running spend ledger (evaluation.budget.record_spend) — never the
historical T-series ledger.

Usage (Stage B only, after explicit approval):
    python scripts/run_e01_oracle.py --provider local   --model llama3.2:3b
    python scripts/run_e01_oracle.py --provider local   --model qwen2.5:7b-instruct
    python scripts/run_e01_oracle.py --provider openrouter --model google/gemini-2.5-flash-lite
    python scripts/run_e01_oracle.py --provider openrouter --model openai/gpt-5-mini
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.budget import check_budget_against_ledger, record_spend  # noqa: E402
from evaluation.oracle import (  # noqa: E402
    build_oracle_user_message,
    build_result_record,
    parse_oracle_output,
)
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

EXPERIMENT_ID = "E01_oracle"
PROMPT_VERSION = "oracle_v1"
MANIFEST_PATH = REPO / "experiments/E01_oracle/TRAIN_ORACLE_v1.json"
PROMPT_PATH = REPO / "prompts/oracle_v1.txt"
RESULTS_DIR = REPO / "experiments/E01_oracle/results"
PLANNING_BUDGET_USD = 5.00
PROTECTED_RESERVE_FRACTION = 0.25


def load_manifest() -> list[dict]:
    with open(MANIFEST_PATH) as f:
        return json.load(f)["cases"]


def make_gateway(provider: str, model: str) -> ModelGateway:
    if provider == "local":
        return ModelGateway.local(model=model)
    if provider == "groq":
        return ModelGateway.groq(model=model)
    if provider == "openrouter":
        return ModelGateway(model=model)
    raise ValueError(f"Unknown provider: {provider}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=["local", "groq", "openrouter"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--limit", type=int, default=None, help="For a smoke-test subset only")
    parser.add_argument("--smoke-test", action="store_true",
                         help="Marks this as an infrastructure smoke test -- writes to a "
                              "separate smoke_ file, excluded from E01 metrics by naming alone.")
    args = parser.parse_args()

    is_hosted = args.provider in ("openrouter",)  # Groq free tier tracked but $0-costed
    cases = load_manifest()
    if args.limit:
        cases = cases[: args.limit]

    system_prompt = PROMPT_PATH.read_text()
    run_id = uuid.uuid4().hex[:12]
    model_tag = args.model.replace("/", "_").replace(":", "_")
    prefix = "smoke_run_E01_oracle" if args.smoke_test else "run_E01_oracle"
    out_path = RESULTS_DIR / f"{prefix}_{args.provider}_{model_tag}.jsonl"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if is_hosted:
        # Rough pre-flight projection using this project's own historical Oracle per-case
        # cost as a conservative stand-in (see experiments/E00B_budget_forecast/summary.md) —
        # a real per-model number would come from evaluation.budget.load_pricing() x actual
        # token estimate; refine when Stage B actually runs.
        projected = 0.35  # ~worst-case single-model Oracle pass at n=300, from E00B
        gate = check_budget_against_ledger(
            projected_experiment_cost_usd=projected,
            planning_budget_usd=PLANNING_BUDGET_USD,
            protected_reserve_fraction=PROTECTED_RESERVE_FRACTION,
        )
        print(gate.reason)
        if not gate.allowed:
            print("BUDGET GATE BLOCKED THIS RUN. Aborting before any hosted call.")
            return 1

    gateway = make_gateway(args.provider, args.model)

    with open(out_path, "w") as out_f:
        for case in cases:
            user_msg = build_oracle_user_message(case)
            try:
                response = gateway.complete(
                    system_prompt=system_prompt, user_prompt=user_msg, temperature=0.0,
                )
                parsed = parse_oracle_output(response.content)
                record = build_result_record(
                    run_id=run_id, experiment_id=EXPERIMENT_ID, case=case,
                    predicted_label=parsed.label, parse_valid=parsed.parse_valid,
                    input_tokens=response.tokens_in or None,
                    output_tokens=response.tokens_out or None,
                    latency_ms=response.latency_ms,
                    provider=args.provider, model=args.model, prompt_version=PROMPT_VERSION,
                    raw_output=response.content, error=None,
                    retry_count=response.num_retries,
                    error_type=None if parsed.parse_valid else "PARSE_ERROR",
                    error_message=None if parsed.parse_valid else
                        f"model responded but output did not match the frozen schema: {response.content!r}",
                )
                if is_hosted:
                    record_spend(
                        experiment_id=EXPERIMENT_ID, provider=args.provider, model=args.model,
                        input_tokens=response.tokens_in, output_tokens=response.tokens_out,
                        cost_usd=response.cost_usd, run_id=run_id,
                    )
            except ModelError as e:
                record = build_result_record(
                    run_id=run_id, experiment_id=EXPERIMENT_ID, case=case,
                    predicted_label=None, parse_valid=False,
                    input_tokens=None, output_tokens=None, latency_ms=None,
                    provider=args.provider, model=args.model, prompt_version=PROMPT_VERSION,
                    raw_output="", error=str(e),
                    retry_count=getattr(e, "num_retries", 0),
                    error_type="MODEL_ERROR", error_message=str(e),
                )
            out_f.write(json.dumps(record) + "\n")
            out_f.flush()

    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
