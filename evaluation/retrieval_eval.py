"""
E06 retrieval optimisation — reusable, LLM-free logic (reconstruction-v2).

Pure/local functions only: build the evidence-bearing TRAIN universe, run a retrieval
configuration against it, and score results using the evidence-hit semantics already
audited and frozen in E00 (evaluation.scorer.map_chunks_to_gold_span_indices,
evaluation.metrics's evidence_recall_at_k / evidence_precision / mean_reciprocal_rank /
recall_with_ci) — NOT a new evidence definition. No model/API calls anywhere in this module.

Does NOT use the not-yet-frozen classification joint-metric threshold tau — retrieval
relevance here is exact gold-span overlap only (evaluation.scorer's existing rule), per the
reconstruction brief's explicit instruction not to substitute one for the other.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation.metrics import (
    evidence_precision,
    evidence_recall_at_k,
    mean_reciprocal_rank,
    recall_with_ci,
)
from evaluation.schemas import GoldCase, Label, Prediction
from evaluation.scorer import map_chunks_to_gold_span_indices
from pipeline.chunker import Chunk

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "cache" / "indexes" / "e06"


# =========================================================================
# 1. Evidence-bearing TRAIN universe (Entailment + Contradiction only —
#    NotMentioned has no gold evidence to retrieve against, E00 section 10).
# =========================================================================

def build_evidence_bearing_train_cases(
    train_path: Path = REPO_ROOT / "data/contractnli/train.json",
) -> list[dict[str, Any]]:
    """
    Every Entailment/Contradiction case in official TRAIN, with its document's full text and
    span list attached (needed for chunk-to-gold-span mapping). Query text is the
    hypothesis/requirement only — never gold evidence, never the gold label — the query the
    real system would actually issue.
    """
    with open(train_path) as f:
        train = json.load(f)

    hyp_text = {k: v["hypothesis"] for k, v in train["labels"].items()}
    cases = []
    for doc in train["documents"]:
        for hyp_id, ann in doc["annotation_sets"][0]["annotations"].items():
            if ann["choice"] not in ("Entailment", "Contradiction"):
                continue
            cases.append({
                "case_id": f"train::{doc['id']}::{hyp_id}",
                "document_id": doc["id"],
                "hypothesis_id": hyp_id,
                "hypothesis_text": hyp_text[hyp_id],
                "gold_label": ann["choice"],
                "gold_span_indices": ann["spans"],
                "doc_text": doc["text"],
                "doc_spans": [tuple(s) for s in doc["spans"]],
            })
    return cases


# =========================================================================
# 2. Retriever caching — keyed on the exact config that changes the index
#    (chunking + embedding), NOT on top_k (a query-time parameter that
#    never requires rebuilding the index).
# =========================================================================

def retriever_cache_key(document_id: int, chunk_method: str, chunk_size: int,
                         chunk_overlap: int, embedding_model: str, retrieval_method: str) -> str:
    """
    Cache key for one document's built index. Does NOT include top_k -- changing top_k only
    changes how many results are read off an already-built index/BM25 table, never requires
    re-chunking or re-embedding. Invalidates automatically whenever chunking or embedding
    config changes (they're part of the key), so a stale cache can never be silently reused
    across a real config change.
    """
    raw = f"{document_id}|{chunk_method}|{chunk_size}|{chunk_overlap}|{embedding_model}|{retrieval_method}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.pkl"


def load_cached(key: str):
    path = cache_path(key)
    if path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def save_cached(key: str, obj) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path(key), "wb") as f:
        pickle.dump(obj, f)


# =========================================================================
# 3. Scoring — reuses E00's frozen evidence-hit semantics exactly.
# =========================================================================

def score_retrieval(
    case: dict[str, Any],
    ranked_chunks: list[Chunk],
) -> tuple[Prediction, GoldCase]:
    """
    Converts one case's ranked retrieval result into (Prediction, GoldCase) using the SAME
    chunk-to-gold-span mapping already audited/frozen in E00
    (evaluation.scorer.map_chunks_to_gold_span_indices) -- not a new evidence definition.
    """
    retrieved_span_indices = map_chunks_to_gold_span_indices(case["doc_spans"], ranked_chunks)
    pred = Prediction(
        doc_id=str(case["document_id"]), hypothesis_id=case["hypothesis_id"],
        predicted_label=Label(case["gold_label"]),  # not used by retrieval metrics; placeholder
        retrieved_span_indices=retrieved_span_indices,
    )
    gold = GoldCase(
        doc_id=str(case["document_id"]), hypothesis_id=case["hypothesis_id"],
        gold_label=Label(case["gold_label"]), gold_span_indices=case["gold_span_indices"],
    )
    return pred, gold


def compute_retrieval_metrics(pairs: list[tuple[Prediction, GoldCase]]) -> dict[str, Any]:
    """Aggregate Evidence Recall@K / Precision / MRR overall and per-class (Entailment vs
    Contradiction), reusing evaluation.metrics's existing, already-audited implementations."""
    preds = [p for p, _ in pairs]
    golds = [g for _, g in pairs]

    def subset(cls: Label):
        idx = [i for i, g in enumerate(golds) if g.gold_label == cls]
        return [preds[i] for i in idx], [golds[i] for i in idx]

    ent_preds, ent_golds = subset(Label.ENTAILMENT)
    con_preds, con_golds = subset(Label.CONTRADICTION)

    return {
        "n_cases": len(pairs),
        "overall": {
            "evidence_recall_at_k": evidence_recall_at_k(preds, golds),
            "evidence_precision": evidence_precision(preds, golds),
            "mrr": mean_reciprocal_rank(preds, golds),
        },
        "entailment": {
            "n": len(ent_golds),
            "evidence_recall_at_k": evidence_recall_at_k(ent_preds, ent_golds),
            "evidence_precision": evidence_precision(ent_preds, ent_golds),
            "mrr": mean_reciprocal_rank(ent_preds, ent_golds),
        },
        "contradiction": {
            "n": len(con_golds),
            "evidence_recall_at_k": evidence_recall_at_k(con_preds, con_golds),
            "evidence_precision": evidence_precision(con_preds, con_golds),
            "mrr": mean_reciprocal_rank(con_preds, con_golds),
        },
        "miss_count": sum(
            1 for p, g in pairs
            if not (set(p.retrieved_span_indices) & set(g.gold_span_indices))
        ),
    }


@dataclass
class ContextSizeStats:
    mean_chunks: float
    mean_chars: float
    mean_tokens: float
    median_tokens: float
    p90_tokens: float
    max_tokens: float


def context_size_stats(chunk_lists: list[list[Chunk]]) -> ContextSizeStats:
    """Context-size metrics for the returned chunks per case -- this becomes E03's model
    input once retrieval_v1 is frozen, so its size matters as much as its recall."""
    import statistics
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")

    n_chunks = [len(cl) for cl in chunk_lists]
    char_lens = [sum(len(c.text) for c in cl) for cl in chunk_lists]
    tok_lens = [len(enc.encode(" ".join(c.text for c in cl))) for cl in chunk_lists]
    tok_sorted = sorted(tok_lens)

    return ContextSizeStats(
        mean_chunks=statistics.mean(n_chunks) if n_chunks else 0.0,
        mean_chars=statistics.mean(char_lens) if char_lens else 0.0,
        mean_tokens=statistics.mean(tok_lens) if tok_lens else 0.0,
        median_tokens=statistics.median(tok_lens) if tok_lens else 0.0,
        p90_tokens=tok_sorted[int(0.9 * len(tok_sorted))] if tok_sorted else 0.0,
        max_tokens=max(tok_lens) if tok_lens else 0.0,
    )


def demo() -> None:
    """Smallest runnable self-check — no network, no model calls, no full-dataset run."""
    cases = build_evidence_bearing_train_cases()
    assert len(cases) == 4371, f"expected 4371 evidence-bearing TRAIN cases, got {len(cases)}"
    assert all(c["gold_label"] in ("Entailment", "Contradiction") for c in cases)
    assert all(c["gold_span_indices"] for c in cases)  # E00: E/C always has non-empty spans

    key = retriever_cache_key(1, "clause", 512, 50, "all-mpnet-base-v2", "dense")
    assert load_cached(key) is None  # nothing cached yet in this fresh check

    # Hand-built retrieval scoring sanity check (no model/embedding call).
    case = {"document_id": 1, "hypothesis_id": "nda-1", "gold_label": "Entailment",
            "gold_span_indices": [0], "doc_spans": [(0, 10), (20, 30)]}
    chunk_hit = Chunk(text="x", start_char=0, end_char=10, chunk_index=0, method="clause")
    pred, gold = score_retrieval(case, [chunk_hit])
    assert pred.retrieved_span_indices == [0]
    metrics = compute_retrieval_metrics([(pred, gold)])
    assert metrics["overall"]["evidence_recall_at_k"] == 1.0

    print("evaluation/retrieval_eval.py self-check OK (4,371 evidence-bearing cases verified)")


if __name__ == "__main__":
    demo()
