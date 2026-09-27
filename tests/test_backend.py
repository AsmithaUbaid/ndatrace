"""
Integration tests for the FastAPI backend's frozen top-5 RAG product path.

Mocks the OpenAI client the same way tests/test_model_gateway.py does -
no real network calls, no API cost.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pipeline.frozen_rag import RetrievedChunk


@pytest.fixture(autouse=True)
def _stub_frozen_retriever(monkeypatch):
    class StubRetriever:
        def __init__(self, nda_text: str):
            self.nda_text = nda_text

        def retrieve(self, requirement: str):
            return [RetrievedChunk(
                chunk_id=0, rank=1, start_char=0, end_char=len(self.nda_text),
                bm25_score=1.0, reranker_score=2.0, text=self.nda_text,
            )]

    monkeypatch.setattr("pipeline.final_review.FrozenRagRetriever", StubRetriever)


@pytest.fixture
def client():
    from backend.app import app
    with TestClient(app) as c:
        yield c


def _fake_completion(content: str, tokens_in: int = 100, tokens_out: int = 20):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out),
    )


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_hypotheses_returns_real_contractnli_labels(client):
    r = client.get("/hypotheses")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 17
    ids = {h["hypothesis_id"] for h in data}
    assert "nda-11" in ids  # "No reverse engineering"


def test_list_final_test_comparison_reads_canonical_csv(client):
    """GET /experiments must be reconstruction-v2-aware: it reads the
    already-computed results/final/reconstruction_v2/full_test_comparison.csv
    (E17/E17B), never results/runs/*.jsonl (the pre-reconstruction log)."""
    r = client.get("/experiments")
    assert r.status_code == 200
    rows = {row["system"]: row for row in r.json()}
    assert {"rule", "qwen_ctx16k", "gpt5mini_p0_full"} <= rows.keys()
    for row in rows.values():
        assert row["n"] == 2091
    gpt = rows["gpt5mini_p0_full"]
    assert gpt["accuracy"] == pytest.approx(0.776183644189383)
    assert gpt["contradiction_recall"] == pytest.approx(0.7545454545454545)


def test_list_e20_architecture_comparison_includes_final_rag(client):
    r = client.get("/experiments/e20")
    assert r.status_code == 200
    rows = {row["architecture_status"]: row for row in r.json()}
    assert set(rows) == {"benchmark", "final"}
    assert rows["benchmark"]["system"] == "gpt5mini_p0_full"
    assert rows["final"]["system"] == "gpt5mini_p0_rag_top5"
    assert rows["final"]["n"] == 2091
    assert rows["final"]["accuracy"] == pytest.approx(0.7675753228120517)
    assert rows["final"]["joint"] == pytest.approx(0.7245337159253945)
    assert rows["final"]["api_cost_usd"] == pytest.approx(3.51773875)


# =========================================================================
# Reliability / document robustness (WBS T040: K04, K05, K06)
# =========================================================================

def test_empty_pdf_file_returns_422(client):
    """K04: an empty file upload should be rejected gracefully, not crash."""
    r = client.post("/extract-pdf", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert r.status_code == 422


def test_oversized_pdf_returns_413(client):
    """K05: a file over the size cap must be rejected before being fully
    processed - found missing entirely during the 2026-09-24 audit."""
    from backend.routes.review import MAX_PDF_SIZE_BYTES
    oversized = b"%PDF-1.4\n" + b"0" * (MAX_PDF_SIZE_BYTES + 1)
    r = client.post("/extract-pdf", files={"file": ("huge.pdf", oversized, "application/pdf")})
    assert r.status_code == 413


def test_unsupported_format_rejected(client):
    """K06: a non-PDF file (wrong content-type) must be rejected, not
    silently misread as if it were a PDF."""
    r = client.post(
        "/extract-pdf",
        files={"file": ("contract.docx", b"not a real docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 400


# =========================================================================
# Single-requirement endpoint - frozen retrieval + GPT-5-mini + P0
# =========================================================================

def test_final_review_end_to_end_with_mocked_model(client):
    """No provider call; mocked exactly like every other backend test here."""
    ok_json = json.dumps({"label": "Entailment", "evidence": ["shall not reverse engineer"]})
    with patch("pipeline.model_gateway.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = MagicMock(return_value=_fake_completion(ok_json))
        payload = {
            "nda_text": "Receiving Party shall not reverse engineer any objects embodying Confidential Information.",
            "requirement": "Receiving Party shall not reverse engineer Confidential Information.",
        }
        r = client.post("/api/review", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["label"] == "Entailment"
        assert body["source_valid"] is True
        assert body["needs_human_review"] is False
        assert body["model"] == "openai/gpt-5-mini"
        assert body["trace_id"]
        assert "confidence" not in body  # no fabricated confidence score
        assert body["evidence"] == ["shall not reverse engineer"]
        assert body["retrieved_chunks"][0]["rank"] == 1
        assert body["sources"][0]["chunk_id"] == 0


def test_final_review_flags_non_source_evidence_for_human_review(client):
    bad_json = json.dumps({"label": "Contradiction", "evidence": ["this quote is not in the document at all"]})
    with patch("pipeline.model_gateway.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = MagicMock(return_value=_fake_completion(bad_json))
        payload = {"nda_text": "Recipient shall keep information confidential.", "requirement": "Some requirement."}
        r = client.post("/api/review", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["needs_human_review"] is True
        assert body["source_valid"] is False
        assert body["review_reason"]


def test_final_review_flags_malformed_model_output(client):
    with patch("pipeline.model_gateway.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = MagicMock(return_value=_fake_completion("not json at all"))
        payload = {"nda_text": "Some NDA text.", "requirement": "Some requirement."}
        r = client.post("/api/review", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["label"] is None
        assert body["needs_human_review"] is True


def test_final_review_returns_503_when_provider_not_configured(client, monkeypatch):
    """Missing OPENROUTER_API_KEY must be a controlled 503, not an unhandled 500."""
    monkeypatch.setattr("pipeline.model_gateway.settings.openrouter_api_key", "")
    payload = {"nda_text": "Some NDA text.", "requirement": "Some requirement."}
    r = client.post("/api/review", json=payload)
    assert r.status_code == 503
    body = r.json()
    assert body == {"detail": "Review service is not configured."}
    assert "OPENROUTER_API_KEY" not in r.text
    assert "Traceback" not in r.text


def test_final_review_rejects_empty_nda(client):
    r = client.post("/api/review", json={"nda_text": "", "requirement": "x"})
    assert r.status_code == 422  # pydantic min_length


def test_final_review_rejects_empty_requirement(client):
    r = client.post("/api/review", json={"nda_text": "x", "requirement": ""})
    assert r.status_code == 422
