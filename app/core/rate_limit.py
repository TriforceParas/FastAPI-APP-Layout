"""In-process sliding-window rate limiter (per client IP).

Limits are kept per process. The app runs as one process per container, so
this is exact for the standard deployment. If you ever start several uvicorn
workers, each keeps its own counters (the effective limit is multiplied by
the worker count); per-account lockout is stored in the database and stays
exact either way.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.request_info import client_ip

_MAX_KEYS = 50_000


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> float | None:
        """Register a hit. Returns seconds to wait when over the limit."""
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > _MAX_KEYS:
                self._prune(now, window_seconds)
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return max(1.0, window_seconds - (now - bucket[0]))
            bucket.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _prune(self, now: float, window_seconds: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - window_seconds]:
            del self._hits[key]


limiter = SlidingWindowLimiter()


def rate_limit(scope: str, limit: int, window_seconds: int) -> Callable[[Request], None]:
    """FastAPI dependency factory, keyed by client IP."""

    def dependency(request: Request) -> None:
        retry_after = limiter.hit(f"{scope}:{client_ip(request)}", limit, window_seconds)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait and try again.",
                headers={"Retry-After": str(int(retry_after))},
            )

    return dependency
