"""Utilities to enforce Binance REST rate limits across the bot."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """Simple thread-safe rate limiter enforcing a minimum interval between calls."""

    def __init__(self, min_interval: float = 0.18):
        if min_interval <= 0:
            raise ValueError("min_interval must be positive")
        self._min_interval = float(min_interval)
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        """Block until the minimum interval has elapsed since the previous call."""
        with self._lock:
            now = time.perf_counter()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
                now = time.perf_counter()
            self._last_call = now
