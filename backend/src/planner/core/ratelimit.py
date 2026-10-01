"""Per-client request limits (Level 3 D-7, NFR-01).

A sliding one-minute window per (route, client IP), answered with 429
RATE_LIMITED. It sits in front of the per-account lockout in
users/features/login/service.py (5 failures -> 15 minutes): the lockout stops
guessing one password, this stops spraying many accounts or flooding uploads.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from planner.core.config import settings
from planner.core.errors import AppError

# ponytail: in-process memory, so each API worker counts on its own; move the
# counters to Redis (INCR + EXPIRE) when the API runs more than one process.
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def rate_limit(name: str, per_minute: Callable[[], int]) -> Callable[[Request], None]:
    """FastAPI dependency: at most per_minute() requests per client IP per minute."""

    def _guard(request: Request) -> None:
        limit = per_minute()
        if limit <= 0:
            return
        # Behind a trusted proxy the socket address is the proxy's, so the real client
        # comes from a header the proxy sets. Only trusted when configured: a direct
        # caller could otherwise spoof it to dodge the limit.
        header = settings.rate_limit_client_header
        client = (header and request.headers.get(header)) or (
            request.client.host if request.client else "unknown"
        )
        window = _hits[(name, client)]
        now = time.monotonic()
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            raise AppError("RATE_LIMITED")
        window.append(now)

    return _guard
