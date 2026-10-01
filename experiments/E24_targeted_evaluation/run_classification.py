#!/usr/bin/env python3
"""E24: Rule / FULL / RAG on the same 49 checked-in cases (45 golden+negative classification
cases, plus 4 real evidence_quality cases), under the current frozen final architecture.

Architectures frozen BEFORE this script runs, asserted at startup -- not tuned afterward:
  - Rule:  pipeline/rule_baseline.py's classify_with_span() -- unmodified, $0, deterministic.
  - FULL:  openai/gpt-5-mini + the frozen GPT-P0 prompt (prompts/final/gpt_p0.txt) over the
           FULL NDA document text -- identical recipe to scripts/e17_common.py's load_frozen(),
           asserted via the same prompt sha1 this script checks before any call.
  - RAG:   pipeline/final_review.py's review_final() -- the real, frozen, served production
           function (BM25 top-20 -> rerank -> top-5 -> GPT-5-mini + P0), not a reimplementation.

Default mode is --dry-run (stub gateway, $0, same fixed response every case -- smoke-test only).
--live makes real hosted calls and is required for results usable in any report/README claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from evaluation.budget import record_spend, final_spend_so_far  # noqa: E402
from evaluation.structured_output import parse_structured_output  # noqa: E402
from pipeline.evidence_validator import validate_evidence  # noqa: E402
from pipeline.final_review import review_final  # noqa: E402
from pipeline.model_gateway import ModelError, ModelGateway  # noqa: E402
from pipeline.rule_baseline import classify_with_span  # noqa: E402
import pipeline.frozen_rag as frozen_rag  # noqa: E402

MANIFEST_PATH = HERE / "manifests" / "case_manifest.json"
OUT_PATH = HERE / "results" / "run_E24_predictions.jsonl"
WALL_PATH = HERE / "results" / "run_E24_wall.json"
RUN_ID = "e24_targeted_evaluation"
MODEL = "openai/gpt-5-mini"

SYSTEM_PROMPT_PATH = REPO / "prompts/final/gpt_p0.txt"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text()
FROZEN_PROMPT_SHA1 = "3fcc7c95cf1287c292e403f12b307c9d912278ce"
FULL_TEMPLATE = "Requirement: {hypothesis_text}\n\nNDA context: {context_text}"


def assert_frozen() -> None:
    """Fail closed if any frozen value this script depends on has drifted."""
    actual = hashlib.sha1(SYSTEM_PROMPT.encode()).hexdigest()
    assert actual == FROZEN_PROMPT_SHA1, f"GPT-P0 prompt sha1 drifted: {actual}"
    assert frozen_rag.CHUNK_SIZE == 256 and frozen_rag.TOP_K == 5 and frozen_rag.CANDIDATE_POOL_SIZE == 20, \
        "pipeline/frozen_rag.py config drifted from the E20 frozen values"
    assert frozen_rag.RERANKER_MODEL == "cross-encoder/ms-marco-MiniLM-L-12-v2", "reranker model drifted"


@dataclass
class _StubResponse:
    content: str
    model: str = "stub-dry-run"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    num_retries: int = 0


class _StubGateway:
    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> _StubResponse:
        return _StubResponse(content=json.dumps({"label": "Entailment", "evidence": ["[stub dry-run response]"]}))


def run_rule(case: dict) -> dict:
    label, span = classify_with_span(case["hypothesis_id"], case["nda_text"])
    evidence = [case["nda_text"][span[0]:span[1]]] if span else []
    return {
        "case_id": case["case_id"], "system": "rule", "predicted_label": label, "evidence": evidence,
        "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.0, "cost_usd": 0.0, "parse_status": "n/a",
        "source_valid": True, "error": None,
    }


def run_full(case: dict, dry_run: bool) -> dict:
    gw = _StubGateway() if dry_run else ModelGateway(model=MODEL, max_retries=3, timeout_seconds=60)
    user_prompt = FULL_TEMPLATE.format(hypothesis_text=case["hypothesis_text"], context_text=case["nda_text"])
    t0 = time.perf_counter()
    try:
        r = gw.complete(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, temperature=0.0)
        p = parse_structured_output(r.content)
        ev = validate_evidence(case["nda_text"], p.evidence, p.predicted_label or "")
        return {
            "case_id": case["case_id"], "system": "full", "predicted_label": p.predicted_label, "evidence": p.evidence,
            "input_tokens": r.tokens_in, "output_tokens": r.tokens_out,
            "latency_ms": r.latency_ms, "cost_usd": r.cost_usd, "parse_status": p.parse_status,
            "source_valid": ev.is_valid, "error": None,
        }
    except ModelError as e:
        return {
            "case_id": case["case_id"], "system": "full", "predicted_label": None, "evidence": [],
            "input_tokens": None, "output_tokens": None, "latency_ms": (time.perf_counter() - t0) * 1000,
            "cost_usd": None, "parse_status": "invalid", "source_valid": None, "error": str(e),
        }


def run_rag(case: dict, dry_run: bool) -> dict:
    gateway = _StubGateway() if dry_run else None  # None -> review_final builds its own real ModelGateway
    result = review_final(case["nda_text"], case["hypothesis_text"], gateway=gateway)
    return {
        "case_id": case["case_id"], "system": "rag", "predicted_label": result.label, "evidence": result.evidence,
        "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms, "cost_usd": result.cost_usd, "parse_status": result.parse_status,
        "source_valid": result.source_valid, "error": result.error,
        "security_review_required": result.security_review_required,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="make real hosted calls (required for usable results)")
    args = parser.parse_args()
    dry_run = not args.live

    assert_frozen()
    manifest = json.loads(MANIFEST_PATH.read_text())
    cases = manifest["cases"]
    assert len(cases) == 49

    if OUT_PATH.exists():
        raise SystemExit(f"{OUT_PATH} already exists -- refusing to overwrite a real run. "
                          f"Move or delete it first if you intend to re-run.")

    pre_ledger = final_spend_so_far() if not dry_run else 0.0
    spend = 0.0
    t_start = time.perf_counter()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as out:
        for i, case in enumerate(cases, 1):
            for fn in (run_rule, lambda c: run_full(c, dry_run), lambda c: run_rag(c, dry_run)):
                rec = fn(case)
                rec.update({
                    "run_id": RUN_ID, "group": case["group"], "gold_label": case["gold_label"],
                    "doc_id": case["doc_id"], "hypothesis_id": case["hypothesis_id"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                out.write(json.dumps(rec) + "\n")
                out.flush()
                if not dry_run and rec["system"] != "rule" and rec.get("cost_usd"):
                    record_spend(experiment_id="E24_targeted_evaluation", provider="openrouter",
                                 model=MODEL, input_tokens=rec["input_tokens"] or 0,
                                 output_tokens=rec["output_tokens"] or 0, cost_usd=rec["cost_usd"], run_id=RUN_ID)
                    spend += rec["cost_usd"]
            print(f"[{i}/{len(cases)}] {case['case_id']} ({case['group']}) done"
                  f"{'' if dry_run else f', spend so far ${spend:.4f}'}", flush=True)

    wall = {
        "mode": "live" if not dry_run else "dry_run_stub_NOT_VALID_FOR_REPORTING",
        "n_cases": len(cases), "spend_usd_this_run": spend,
        "wall_seconds": time.perf_counter() - t_start,
        "pre_run_ledger_usd": pre_ledger, "post_run_ledger_usd": final_spend_so_far() if not dry_run else None,
    }
    WALL_PATH.write_text(json.dumps(wall, indent=2))
    print(json.dumps(wall, indent=2))


if __name__ == "__main__":
    main()
