"""
Backend tests - TTLCache
========================
Tests for the time-to-live response cache used to make the expensive
/api/v1/safety/index/ endpoint cheap on repeat calls.
"""


class FakeClock:
    """A controllable monotonic clock for deterministic TTL tests."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class TestTTLCache:
    def test_get_returns_miss_for_unknown_key(self):
        from app.core.cache import TTLCache

        cache = TTLCache(ttl_seconds=60)
        hit, value = cache.get("nope")
        assert hit is False
        assert value is None

    def test_get_returns_stored_value_within_ttl(self):
        from app.core.cache import TTLCache

        clock = FakeClock()
        cache = TTLCache(ttl_seconds=60, clock=clock)
        cache.set("k", {"score": 42})

        clock.advance(59)  # still inside the TTL window
        hit, value = cache.get("k")
        assert hit is True
        assert value == {"score": 42}

    def test_get_returns_miss_after_ttl_expiry(self):
        from app.core.cache import TTLCache

        clock = FakeClock()
        cache = TTLCache(ttl_seconds=60, clock=clock)
        cache.set("k", "v")

        clock.advance(61)  # past the TTL window
        hit, value = cache.get("k")
        assert hit is False
        assert value is None

    def test_set_overwrites_existing_key(self):
        from app.core.cache import TTLCache

        clock = FakeClock()
        cache = TTLCache(ttl_seconds=60, clock=clock)
        cache.set("k", "first")
        cache.set("k", "second")

        hit, value = cache.get("k")
        assert hit is True
        assert value == "second"

    def test_clear_drops_all_entries(self):
        from app.core.cache import TTLCache

        cache = TTLCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()

        assert cache.get("a") == (False, None)
        assert cache.get("b") == (False, None)

    def test_distinct_keys_are_independent(self):
        from app.core.cache import TTLCache

        cache = TTLCache(ttl_seconds=60)
        cache.set(("alpha", 0.7), "blended")
        cache.set(("alpha", 1.0), "pure-rtsi")

        assert cache.get(("alpha", 0.7)) == (True, "blended")
        assert cache.get(("alpha", 1.0)) == (True, "pure-rtsi")
