#!/usr/bin/env python3
"""
E03 controlled prompt selection runner (reconstruction-v2) — resumed after E06 froze
retrieval_v1.

Runs the frozen TRAIN_PROMPT_v1 case set (n=150) through one fixed model
(qwen2.5:7b-instruct, local only — no hosted calls) under one prompt version at a time
(p00/p01/p02). Model, manifest, context, temperature, output schema, parser, and scoring
logic are all held fixed across prompt versions — only the system prompt changes.

Context: each case's `context_text` is built here by joining the frozen retrieval_v1 top-5
reranked chunks from TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json (BM25 -> clause_256 ->
top-20 -> rerank(ms-marco-MiniLM-L-12-v2) -> top-5) — NOT full document text (that was the
original, superseded pre-E06 design; see results/SUPERSEDED_run_E03_prompt_selection_p00.md).
gold_label comes only from TRAIN_PROMPT_v1.json (the evaluator-side manifest) and is never
included in the retrieved-context file or the model-visible message.

Usage:
    python scripts/run_e03_prompt_selection.py --prompt-version p00
    python scripts/run_e03_prompt_selection.py --prompt-version p01
    python scripts/run_e03_prompt_selection.py --prompt-version p02
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
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
RETRIEVAL_CONFIG_VERSION = "retrieval_v1"  # frozen in E06 -- BM25/clause_256/top-20/rerank/top-5
MANIFEST_PATH = REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1.json"
RETRIEVED_CONTEXT_PATH = REPO / "experiments/E03_prompt_selection/TRAIN_PROMPT_v1_RETRIEVED_retrieval_v1.json"
RESULTS_DIR = REPO / "experiments/E03_prompt_selection/results"
CHUNK_SEPARATOR = "\n\n---\n\n"  # identical for every case and every prompt variant


def load_cases_with_retrieved_context() -> list[dict]:
    """
    Merge the evaluator-side manifest (gold_label) with the frozen retrieval_v1 context
    (ranked_chunk_text) by case_id, in the manifest's original order. Asserts hypothesis_text
    agrees between the two files as a structural-integrity check, not a retrieval re-run.
    """
    with open(MANIFEST_PATH) as f:
        manifest_cases = json.load(f)["cases"]
    with open(RETRIEVED_CONTEXT_PATH) as f:
        retrieved = json.load(f)
    retrieval_config = retrieved["retrieval_config"]
    if retrieval_config["method"] != "bm25" or retrieval_config["top_k"] != 5:
        raise ValueError(f"Retrieved-context file's config {retrieval_config!r} does not "
                          f"match the frozen retrieval_v1 spec -- refusing to run.")
    retrieved_by_id = {c["case_id"]: c for c in retrieved["cases"]}

    merged = []
    for m in manifest_cases:
        r = retrieved_by_id[m["case_id"]]
        assert r["hypothesis_text"] == m["hypothesis_text"], (
            f"hypothesis_text mismatch for {m['case_id']!r} between manifest and "
            f"retrieved-context file")
        merged.append({
            "case_id": m["case_id"],
            "document_id": m["document_id"],
            "hypothesis_id": m["hypothesis_id"],
            "hypothesis_text": m["hypothesis_text"],
            "gold_label": m["gold_label"],
            "context_text": CHUNK_SEPARATOR.join(r["ranked_chunk_text"]),
        })
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-version", required=True, choices=["p00", "p01", "p02"])
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

    prompt_config_hash = hashlib.sha1(
        json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:12]

    cases = load_cases_with_retrieved_context()
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
                record["retrieval_config_version"] = RETRIEVAL_CONFIG_VERSION
                record["prompt_config_hash"] = prompt_config_hash
                record["timestamp"] = datetime.now(timezone.utc).isoformat()
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
                record["retrieval_config_version"] = RETRIEVAL_CONFIG_VERSION
                record["prompt_config_hash"] = prompt_config_hash
                record["timestamp"] = datetime.now(timezone.utc).isoformat()
            out_f.write(json.dumps(record) + "\n")
            out_f.flush()

    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
