"""
Self-check for the reviewer-decision persistence path (human oversight: authority
to intervene). Uses an isolated sqlite file so it never touches the real ndatrace.db.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("pipeline.config.settings.database_url", f"sqlite:///{tmp_path / 'test.db'}")
    from backend import database
    importlib.reload(database)
    database.init_db()
    return database


def _item(hypothesis_id="nda-1"):
    return {
        "hypothesis_id": hypothesis_id, "hypothesis_text": "Confidentiality survives termination.",
        "label": "Entailment", "explanation": "...", "evidence": ["clause 4"],
        "cost_usd": 0.001, "latency_ms": 900.0,
    }


def test_decision_recorded_and_returned(db):
    db.save_review("rev-1", "doc-1", "2026-09-30T00:00:00Z", "openai/gpt-5-mini", 0.001, 900.0, [_item()])
    review = db.get_review("rev-1")
    item_id = review["items"][0]["id"]
    assert review["items"][0]["decision"] is None  # no decision yet, not defaulted to "approved"

    db.record_decision(item_id, "overridden", "Retention clause is ambiguous.", "asmitha")
    updated = db.get_review("rev-1")["items"][0]
    assert updated["decision"] == "overridden"
    assert updated["decision_note"] == "Retention clause is ambiguous."
    assert updated["decision_reviewer"] == "asmitha"
    assert updated["decided_at"]


def test_latest_decision_wins_and_history_is_kept(db):
    db.save_review("rev-2", "doc-2", "2026-09-30T00:00:00Z", "openai/gpt-5-mini", 0.001, 900.0, [_item()])
    item_id = db.get_review("rev-2")["items"][0]["id"]

    db.record_decision(item_id, "approved", None, "asmitha")
    db.record_decision(item_id, "rejected", "Changed my mind after re-reading.", "asmitha")

    assert db.get_review("rev-2")["items"][0]["decision"] == "rejected"
    with db.get_connection() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM review_decisions WHERE review_item_id = ?", (item_id,)
        ).fetchone()[0]
    assert n == 2  # both decisions kept, not overwritten


def test_decision_on_unknown_item_raises(db):
    with pytest.raises(KeyError):
        db.record_decision(999999, "approved", None, None)


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
