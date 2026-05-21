"""
TTLCache
========
A minimal, thread-safe time-to-live cache for expensive endpoint responses.

The safety-index endpoints recompute 18 intersections from scratch on every
request, even though the underlying data is only refreshed every 15 minutes.
Caching a whole response for a few minutes turns a multi-minute endpoint into
a sub-second one for all but the first request.

The clock is injectable so TTL expiry can be tested deterministically.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Hashable


class TTLCache:
    """A small key/value cache where entries expire after ``ttl_seconds``."""

    def __init__(
        self,
        ttl_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._store: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> tuple[bool, Any]:
        """
        Return ``(hit, value)``. ``hit`` is False on a miss or an expired
        entry; expired entries are evicted on access.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False, None
            stored_at, value = entry
            if self._clock() - stored_at > self._ttl:
                del self._store[key]
                return False, None
            return True, value

    def set(self, key: Hashable, value: Any) -> None:
        """Store ``value`` under ``key`` with a fresh timestamp."""
        with self._lock:
            self._store[key] = (self._clock(), value)

    def clear(self) -> None:
        """Drop every cached entry."""
        with self._lock:
            self._store.clear()
