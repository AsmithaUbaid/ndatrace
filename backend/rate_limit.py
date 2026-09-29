"""
E22 LLM10 remediation: concurrency and rate limits for the live review
endpoints, without adding an infrastructure dependency (no Redis, no
slowapi) - plain stdlib, in-process, deterministic, and directly testable
by calling these functions or a bounded number of TestClient requests.

Scope note: this is per-process state (a single FastAPI worker), matching
the project's existing single-process SQLite deployment model - it is not a
distributed rate limiter and would need to move to shared state (e.g. Redis)
behind multiple workers. That gap is disclosed as residual risk, not hidden.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Iterator

# Generous vs. E21's own H06 burst measurement (~30 RPM observed, 0 rate-limited)
# - this exists to catch runaway/misbehaving clients, not to throttle normal use.
MAX_CONCURRENT_REQUESTS = 3
RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_MAX_REQUESTS = 30

_concurrency_lock = threading.Lock()
_in_flight = 0

_rate_lock = threading.Lock()
_request_times: deque[float] = deque()


class ConcurrencyLimitExceeded(Exception):
    pass


class RateLimitExceeded(Exception):
    pass


@contextmanager
def concurrency_guard(max_concurrent: int = MAX_CONCURRENT_REQUESTS) -> Iterator[None]:
    global _in_flight
    with _concurrency_lock:
        if _in_flight >= max_concurrent:
            raise ConcurrencyLimitExceeded(
                f"{_in_flight} requests already in flight (limit {max_concurrent})."
            )
        _in_flight += 1
    try:
        yield
    finally:
        with _concurrency_lock:
            _in_flight -= 1


def check_rate_limit(
    max_requests: int = RATE_LIMIT_MAX_REQUESTS,
    window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
) -> None:
    """Raises RateLimitExceeded if this call would exceed `max_requests` within the
    trailing `window_seconds`. Records the call as counted only if it's allowed."""
    now = time.monotonic()
    with _rate_lock:
        while _request_times and now - _request_times[0] > window_seconds:
            _request_times.popleft()
        if len(_request_times) >= max_requests:
            raise RateLimitExceeded(
                f"{len(_request_times)} requests in the last {window_seconds:.0f}s (limit {max_requests})."
            )
        _request_times.append(now)


def _reset_for_tests() -> None:
    """Test-only helper - state is module-global and otherwise leaks between tests."""
    global _in_flight
    with _concurrency_lock:
        _in_flight = 0
    with _rate_lock:
        _request_times.clear()
