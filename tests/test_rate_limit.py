"""Sliding-window limiter tests."""

from __future__ import annotations

from sentinel_stack.rate_limit import SlidingWindowLimiter


def test_allows_under_cap() -> None:
    limiter = SlidingWindowLimiter(max_hits=3, window_sec=60)
    assert limiter.allow("a")
    assert limiter.allow("a")
    assert limiter.allow("a")
    assert limiter.allow("a") is False


def test_keys_are_independent() -> None:
    limiter = SlidingWindowLimiter(max_hits=1, window_sec=60)
    assert limiter.allow("one")
    assert limiter.allow("two")
    assert limiter.allow("one") is False
