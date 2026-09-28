"""In-process sliding-window limiter for public POST gates."""

from __future__ import annotations

import os
import threading
import time
from typing import Any


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    return int(raw) if raw else default


class SlidingWindowLimiter:
    def __init__(self, max_hits: int, window_sec: float) -> None:
        self.max_hits = max(1, max_hits)
        self.window_sec = max(0.1, window_sec)
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = [t for t in self._hits.get(key, []) if now - t < self.window_sec]
            if len(q) >= self.max_hits:
                self._hits[key] = q
                return False
            q.append(now)
            self._hits[key] = q
            return True


def limiter_from_env() -> SlidingWindowLimiter:
    return SlidingWindowLimiter(
        max_hits=_int_env("SENTINEL_POST_RATE_LIMIT", 30),
        window_sec=float(_int_env("SENTINEL_POST_RATE_WINDOW", 60)),
    )


POST_LIMITER = limiter_from_env()


def client_key(handler: Any) -> str:
    if (os.environ.get("SENTINEL_TRUST_PROXY") or "").strip() == "1":
        forwarded = (handler.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return handler.address_string()


def reset_limiter_from_env() -> SlidingWindowLimiter:
    """Tests / process start — rebuild from current env."""
    global POST_LIMITER
    POST_LIMITER = limiter_from_env()
    return POST_LIMITER
