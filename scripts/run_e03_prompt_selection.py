#!/usr/bin/env python3
"""
E03 controlled prompt selection runner (reconstruction-v2) — Stage B only. NOT executed
during Stage A prep.

Runs the frozen TRAIN_PROMPT_v1 manifest through one fixed model (qwen2.5:7b-instruct, local
only — no hosted calls, per the reconstruction brief) under one prompt version at a time
(p00/p01/p02, and p03 only if explicitly approved). Model, manifest, context, temperature,
output schema, parser, and scoring logic are all held fixed across prompt versions — only the
system prompt changes.

Usage (Stage B only, after explicit approval):
    python scripts/run_e03_prompt_selection.py --prompt-version p00
    python scripts/run_e03_prompt_selection.py --prompt-version p01
    python scripts/run_e03_prompt_selection.py --prompt-version p02
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evaluation.oracle import build_result_record, parse_oracle_output  # noqa: E402
from evaluation.prompt_selection import (  # noqa: E402
    build_classification_user_message,
    load_prompt_config,
)
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402

EXPERIMENT_ID = "E03_prompt_selection"
MODEL = "qwen2.5:7b-instruct"  # fixed -- the frozen primary local model from E01/E02
MANIFEST_PATH = REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1.json"
RESULTS_DIR = REPO / "experiments/E03_prompt_selection/results"


def load_manifest() -> list[dict]:
    with open(MANIFEST_PATH) as f:
        return json.load(f)["cases"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-version", required=True, choices=["p00", "p01", "p02", "p03"])
    parser.add_argument("--limit", type=int, default=None, help="For a smoke-test subset only")
    parser.add_argument("--case-indices", type=str, default=None,
                         help="Comma-separated manifest indices for a representative smoke "
                              "test (e.g. '59,126,20,4,49'), overrides --limit")
    parser.add_argument("--smoke-test", action="store_true",
                         help="Marks this as an infrastructure smoke test -- writes to a "
                              "separate smoke_ file, excluded from E03 metrics by naming alone.")
    args = parser.parse_args()

    cfg = load_prompt_config(args.prompt_version)
    if cfg["model"] != MODEL:
        raise ValueError(f"Prompt config {args.prompt_version} declares model={cfg['model']!r}, "
                          f"expected the frozen E03 model {MODEL!r} -- refusing to run.")

    cases = load_manifest()
    if args.case_indices:
        idx = [int(x) for x in args.case_indices.split(",")]
        cases = [cases[i] for i in idx]
    elif args.limit:
        cases = cases[: args.limit]

    run_id = uuid.uuid4().hex[:12]
    prefix = "smoke_run_E03_prompt_selection" if args.smoke_test else "run_E03_prompt_selection"
    out_path = RESULTS_DIR / f"{prefix}_{args.prompt_version}.jsonl"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    gateway = ModelGateway.local(model=MODEL)  # local only -- E03 never calls a hosted model

    with open(out_path, "w") as out_f:
        for case in cases:
            user_msg = build_classification_user_message(case, cfg["user_template"])
            try:
                response = gateway.complete(
                    system_prompt=cfg["system_prompt"], user_prompt=user_msg,
                    temperature=cfg["temperature"],
                )
                parsed = parse_oracle_output(response.content)
                record = build_result_record(
                    run_id=run_id, experiment_id=EXPERIMENT_ID, case=case,
                    predicted_label=parsed.label, parse_valid=parsed.parse_valid,
                    input_tokens=response.tokens_in or None,
                    output_tokens=response.tokens_out or None,
                    latency_ms=response.latency_ms,
                    provider="local", model=MODEL, prompt_version=args.prompt_version,
                    raw_output=response.content, error=None,
                    retry_count=response.num_retries,
                    error_type=None if parsed.parse_valid else "PARSE_ERROR",
                    error_message=None if parsed.parse_valid else
                        f"model responded but output did not match the frozen schema: {response.content!r}",
                )
            except ModelError as e:
                record = build_result_record(
                    run_id=run_id, experiment_id=EXPERIMENT_ID, case=case,
                    predicted_label=None, parse_valid=False,
                    input_tokens=None, output_tokens=None, latency_ms=None,
                    provider="local", model=MODEL, prompt_version=args.prompt_version,
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
