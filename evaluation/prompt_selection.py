"""
E03 controlled prompt selection — reusable, provider-agnostic logic (reconstruction-v2).

Pure functions: build the model-visible user message for one TRAIN_PROMPT_v1 case, and load a
versioned prompt config. Output parsing and result-record shape are identical to E01's compact
`{"label": ...}` schema, so they are reused directly from evaluation.oracle
(parse_oracle_output, build_result_record) — not duplicated here.

E03 resumed after E06 froze retrieval_v1 (BM25 -> clause_256 -> top-20 -> rerank -> top-5).
`case["context_text"]` is now built by the runner from retrieval_v1's reranked top-5 chunks
(joined), not the full NDA document text used in the original, superseded pre-E06 attempt —
this function itself is agnostic to that distinction, it just renders whatever context_text
it's given.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROMPT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs" / "prompts" / "classification"


def load_prompt_config(version: str) -> dict[str, Any]:
    """Load one configs/prompts/classification/classification_{version}.yaml file."""
    path = PROMPT_CONFIG_DIR / f"classification_{version}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def build_classification_user_message(case: dict[str, Any], user_template: str) -> str:
    """
    Render the user message for one TRAIN_PROMPT_v1 case from the prompt config's
    `user_template` (e.g. "Requirement: {hypothesis_text}\n\nNDA text: {context_text}").

    `case["context_text"]` is caller-provided (the frozen retrieval_v1 reranked top-5 context,
    per the resumed E03 design — see docs/experiment_registry.md). `gold_label` is never read
    here.
    """
    return user_template.format(
        hypothesis_text=case["hypothesis_text"],
        context_text=case["context_text"],
    )


def demo() -> None:
    """Smallest runnable self-check — no network, no model calls."""
    case = {"case_id": "train::1::nda-1", "hypothesis_text": "Some requirement.",
            "context_text": "Full NDA text goes here.", "gold_label": "Entailment"}
    template = "Requirement: {hypothesis_text}\n\nNDA text: {context_text}"
    msg = build_classification_user_message(case, template)
    assert "Some requirement." in msg
    assert "Full NDA text goes here." in msg
    assert "Entailment" not in msg  # gold_label must never leak

    cfg = load_prompt_config("p00")
    assert cfg["version"] == "p00"
    assert "system_prompt" in cfg and "user_template" in cfg

    print("evaluation/prompt_selection.py self-check OK")


if __name__ == "__main__":
    demo()
