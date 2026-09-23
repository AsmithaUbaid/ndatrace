"""
Unit tests for pipeline/logging_config.py - specifically that get_logger()
actually configures logging, since setup_logging() existing but never
being called was a real bug found while building Category 10's eval
cases (every structured log line this session had been going nowhere).
"""

from __future__ import annotations

import json
import logging

import pytest

import pipeline.logging_config as logging_config


@pytest.fixture(autouse=True)
def reset_logging_state():
    logging_config.reset_logging()
    yield
    logging_config.reset_logging()


def test_get_logger_auto_configures_root_logger(tmp_path, monkeypatch):
    """get_logger() must not require a separate setup_logging() call."""
    monkeypatch.chdir(tmp_path)
    logging_config.get_logger("test_component")
    root = logging.getLogger()
    assert any(isinstance(h, logging.FileHandler) for h in root.handlers)


def test_get_logger_writes_real_jsonl_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = logging_config.get_logger("test_component")
    logger.info("hello", extra={"stage": "test", "doc_id": "d1"})

    log_file = tmp_path / "logs" / "ndatrace.jsonl"
    assert log_file.exists()
    lines = log_file.read_text().splitlines()
    assert len(lines) >= 1
    record = json.loads(lines[-1])
    assert record["message"] == "hello"
    assert record["stage"] == "test"
    assert record["doc_id"] == "d1"


def test_setup_logging_is_idempotent(tmp_path, monkeypatch):
    """Calling get_logger() many times must not stack duplicate handlers."""
    monkeypatch.chdir(tmp_path)
    for _ in range(5):
        logging_config.get_logger("test_component")
    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
