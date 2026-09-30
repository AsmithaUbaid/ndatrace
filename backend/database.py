"""
NDATrace SQLite persistence (WBS T032).

Stores live review requests/results only - offline experiment records
stay in results/runs/*.jsonl (append-only, Section 0A), never duplicated
here. Plain stdlib sqlite3 is deliberate: Section 1's "Do Not Build" list
rules out managed/heavier databases (Postgres/pgvector) for this project's
scope, and there's no concurrent-writer need that would justify an ORM.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from pipeline.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    model TEXT NOT NULL,
    total_cost_usd REAL NOT NULL,
    total_latency_ms REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id TEXT NOT NULL REFERENCES reviews(review_id),
    hypothesis_id TEXT NOT NULL,
    hypothesis_text TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL NOT NULL,
    confidence_available INTEGER NOT NULL DEFAULT 1,
    explanation TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    source_valid INTEGER,
    needs_human_review INTEGER NOT NULL DEFAULT 0,
    review_reason TEXT,
    sources_json TEXT NOT NULL DEFAULT '[]',
    retrieved_chunks_json TEXT NOT NULL DEFAULT '[]',
    agent_used INTEGER NOT NULL,
    agent_steps INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    latency_ms REAL NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_review_items_review_id ON review_items(review_id);

-- Reviewer decisions (human-oversight authority to intervene). Append-only: a
-- reviewer may record more than one decision for the same item (e.g. change
-- their mind after re-reading the evidence); get_review() below returns only
-- the latest per item, but nothing is ever overwritten or deleted, so the
-- full decision history stays auditable in this table.
CREATE TABLE IF NOT EXISTS review_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_item_id INTEGER NOT NULL REFERENCES review_items(id),
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'overridden', 'rejected')),
    note TEXT,
    reviewer TEXT,
    decided_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_review_decisions_item ON review_decisions(review_item_id);
"""


def _db_path() -> str:
    # settings.database_url is "sqlite:///ndatrace.db" (relative) or
    # "sqlite:////abs/path.db" (absolute) - strip the sqlite:/// prefix.
    url = settings.database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError(f"Only sqlite:/// URLs are supported, got: {url!r}")
    return url[len(prefix):]


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    Path(_db_path()).parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        # Additive migration for databases created by the earlier batch UI.
        existing = {row[1] for row in conn.execute("PRAGMA table_info(review_items)")}
        additions = {
            "confidence_available": "INTEGER NOT NULL DEFAULT 1",
            "source_valid": "INTEGER",
            "needs_human_review": "INTEGER NOT NULL DEFAULT 0",
            "review_reason": "TEXT",
            "sources_json": "TEXT NOT NULL DEFAULT '[]'",
            "retrieved_chunks_json": "TEXT NOT NULL DEFAULT '[]'",
            # E22 LLM01 remediation.
            "security_review_required": "INTEGER NOT NULL DEFAULT 0",
            "security_flags_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        for name, definition in additions.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE review_items ADD COLUMN {name} {definition}")


def save_review(review_id: str, doc_id: str, created_at: str, model: str,
                 total_cost_usd: float, total_latency_ms: float, items: list[dict]) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO reviews (review_id, doc_id, created_at, model, total_cost_usd, total_latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (review_id, doc_id, created_at, model, total_cost_usd, total_latency_ms),
        )
        conn.executemany(
            "INSERT INTO review_items (review_id, hypothesis_id, hypothesis_text, label, confidence, "
            "confidence_available, explanation, evidence_json, source_valid, needs_human_review, "
            "review_reason, sources_json, retrieved_chunks_json, agent_used, agent_steps, cost_usd, "
            "latency_ms, error, security_review_required, security_flags_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    review_id, it["hypothesis_id"], it["hypothesis_text"], it.get("label") or "",
                    it.get("confidence") or 0.0, int(it.get("confidence_available", True)),
                    it["explanation"], json.dumps(it["evidence"]),
                    None if it.get("source_valid") is None else int(it["source_valid"]),
                    int(it.get("needs_human_review", False)), it.get("review_reason"),
                    json.dumps(it.get("sources", [])), json.dumps(it.get("retrieved_chunks", [])),
                    int(it.get("agent_used", False)), it.get("agent_steps", 0),
                    it["cost_usd"], it["latency_ms"], it.get("error"),
                    int(it.get("security_review_required", False)), json.dumps(it.get("security_flags", [])),
                )
                for it in items
            ],
        )


def record_decision(review_item_id: int, decision: str, note: str | None, reviewer: str | None) -> dict:
    """Record a human reviewer's decision (approve/override/reject) on one review item.
    This is the persisted form of the reviewer's authority to intervene - distinct from
    needs_human_review, which only flags that a case warrants a look."""
    decided_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM review_items WHERE id = ?", (review_item_id,)
        ).fetchone()
        if exists is None:
            raise KeyError(f"No review item with id={review_item_id}")
        conn.execute(
            "INSERT INTO review_decisions (review_item_id, decision, note, reviewer, decided_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (review_item_id, decision, note, reviewer, decided_at),
        )
    return {"review_item_id": review_item_id, "decision": decision, "note": note,
            "reviewer": reviewer, "decided_at": decided_at}


def _latest_decisions(conn: sqlite3.Connection, review_id: str) -> dict[int, dict]:
    rows = conn.execute(
        "SELECT d.* FROM review_decisions d "
        "JOIN review_items i ON i.id = d.review_item_id "
        "WHERE i.review_id = ? "
        "AND d.id = (SELECT MAX(id) FROM review_decisions WHERE review_item_id = d.review_item_id)",
        (review_id,),
    ).fetchall()
    return {row["review_item_id"]: dict(row) for row in rows}


def get_review(review_id: str) -> dict | None:
    with get_connection() as conn:
        review_row = conn.execute(
            "SELECT * FROM reviews WHERE review_id = ?", (review_id,)
        ).fetchone()
        if review_row is None:
            return None
        item_rows = conn.execute(
            "SELECT * FROM review_items WHERE review_id = ? ORDER BY id", (review_id,)
        ).fetchall()
        decisions = _latest_decisions(conn, review_id)

    return {
        **dict(review_row),
        "items": [
            {
                **dict(row),
                "label": row["label"] or None,
                "confidence": row["confidence"] if row["confidence_available"] else None,
                "confidence_available": bool(row["confidence_available"]),
                "evidence": json.loads(row["evidence_json"]),
                "source_valid": None if row["source_valid"] is None else bool(row["source_valid"]),
                "needs_human_review": bool(row["needs_human_review"]),
                "sources": json.loads(row["sources_json"]),
                "retrieved_chunks": json.loads(row["retrieved_chunks_json"]),
                "agent_used": bool(row["agent_used"]),
                "security_review_required": bool(row["security_review_required"]),
                "security_flags": json.loads(row["security_flags_json"]),
                "decision": (decisions.get(row["id"]) or {}).get("decision"),
                "decision_note": (decisions.get(row["id"]) or {}).get("note"),
                "decision_reviewer": (decisions.get(row["id"]) or {}).get("reviewer"),
                "decided_at": (decisions.get(row["id"]) or {}).get("decided_at"),
            }
            for row in item_rows
        ],
    }


def list_reviews(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT r.review_id, r.doc_id, r.created_at, r.model, r.total_cost_usd, "
            "COUNT(i.id) AS num_requirements "
            "FROM reviews r LEFT JOIN review_items i ON i.review_id = r.review_id "
            "GROUP BY r.review_id ORDER BY r.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
