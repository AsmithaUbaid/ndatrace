"""
Structured JSON logging with request/trace IDs.

Built on Day 1 per Section 0B of the planning document.
Every log line is a JSON object written to logs/ndatrace.jsonl.
request_id links all log lines from one user request.
trace_id links a parent request to agent sub-calls.

NEVER log: raw NDA text, prompts containing NDA text, API keys,
           user-uploaded file contents, gold labels during prediction.
DO log:    request_id, trace_id, component, stage, latency_ms,
           token counts, cost estimate, error codes, model name, config hash.
"""

import logging
import json
import uuid
import time
import contextvars
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any


# ---------------------------------------------------------------------------
# Context variables -- set once per request, visible everywhere in that call
# ---------------------------------------------------------------------------
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="no-request"
)
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default="no-trace"
)


def new_request_id() -> str:
    """Generate a new request ID and set it in the context."""
    rid = f"req-{uuid.uuid4().hex[:12]}"
    request_id_var.set(rid)
    return rid


def new_trace_id() -> str:
    """Generate a new trace ID and set it in the context."""
    tid = f"trace-{uuid.uuid4().hex[:12]}"
    trace_id_var.set(tid)
    return tid


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------
_EXTRA_FIELDS = (
    "stage", "latency_ms", "tokens_in", "tokens_out",
    "cost_usd", "model", "config_hash", "error_code",
    "doc_id", "hypothesis_id", "label", "confidence",
)


class JSONFormatter(logging.Formatter):
    """Formats each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self._iso_time(record),
            "level": record.levelname,
            "request_id": request_id_var.get(),
            "trace_id": trace_id_var.get(),
            "component": record.name,
            "message": record.getMessage(),
        }

        # Attach extra structured fields if present
        for key in _EXTRA_FIELDS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)

    @staticmethod
    def _iso_time(record: logging.LogRecord) -> str:
        """ISO-8601 timestamp with milliseconds."""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"


# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------
_configured = False


def setup_logging(
    log_dir: str = "logs",
    log_file: str = "ndatrace.jsonl",
    level: str = "INFO",
    also_console: bool = True,
) -> None:
    """
    Configure the root logger for NDATrace.

    Call once at startup.  Subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return
    _configured = True

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # File handler -- append-only JSONL
    fh = logging.FileHandler(log_path / log_file, encoding="utf-8")
    fh.setFormatter(JSONFormatter())
    root.addHandler(fh)

    # Optional console handler (human-readable, not JSON)
    if also_console:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        ch.setLevel(logging.INFO)
        root.addHandler(ch)


def reset_logging() -> None:
    """
    Reset logging state (for tests). Also strips handlers from the root
    logger, not just the `_configured` flag - otherwise a FileHandler
    from an earlier test (pointing at that test's own tmp_path) stays
    attached and a later test's log lines silently go to the wrong file.
    """
    global _configured
    _configured = False
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()


def get_logger(component: str) -> logging.Logger:
    """
    Return a logger named after the pipeline component.

    Ensures setup_logging() has run first (idempotent - see its
    `_configured` guard) so every module that calls get_logger() gets
    real JSONL output without having to remember a separate setup call.
    Found the hard way: setup_logging() existed but nothing ever called
    it, so every structured log line this session went nowhere.
    """
    if not _configured:
        from pipeline.config import settings
        setup_logging(level=settings.log_level)
    return logging.getLogger(f"ndatrace.{component}")


# ---------------------------------------------------------------------------
# Timing context manager
# ---------------------------------------------------------------------------
class log_stage:
    """
    Context manager that logs stage entry and exit with latency.

    Usage:
        with log_stage(logger, "retrieval", doc_id="nda_42"):
            results = retriever.retrieve(query)
    """

    def __init__(self, logger: logging.Logger, stage: str, **extra: Any):
        self.logger = logger
        self.stage = stage
        self.extra = extra
        self.start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "log_stage":
        self.start = time.perf_counter()
        self.logger.info(
            f"Starting {self.stage}",
            extra={"stage": self.stage, **self.extra},
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self.start) * 1000
        if exc_type is not None:
            self.logger.error(
                f"Failed {self.stage} after {self.elapsed_ms:.1f}ms: {exc_val}",
                extra={
                    "stage": self.stage,
                    "latency_ms": round(self.elapsed_ms, 1),
                    "error_code": exc_type.__name__,
                    **self.extra,
                },
            )
        else:
            self.logger.info(
                f"Completed {self.stage} in {self.elapsed_ms:.1f}ms",
                extra={
                    "stage": self.stage,
                    "latency_ms": round(self.elapsed_ms, 1),
                    **self.extra,
                },
            )
