"""
Redis-backed response cache with in-process fallback.

The API has several expensive read endpoints whose inputs are small and whose
results are stable for minutes at a time. This module keeps cache integration
out of endpoint bodies and degrades to local memory when Redis is not configured.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from fastapi.encoders import jsonable_encoder

try:
    from redis import Redis
    from redis.exceptions import RedisError
except ModuleNotFoundError:  # Local test environments may not install optional deps.
    Redis = None  # type: ignore[assignment]

    class RedisError(Exception):
        pass

from .cache import TTLCache
from .config import settings

logger = logging.getLogger(__name__)


class ResponseCache:
    """Cache JSON-serializable endpoint responses in Redis or local memory."""

    def __init__(self) -> None:
        self._memory = TTLCache(ttl_seconds=1)
        self._memory_ttls: dict[str, TTLCache] = {}
        self._redis: Any | None = None
        self._redis_checked = False

    def _client(self) -> Any | None:
        if not settings.CACHE_ENABLED or not settings.REDIS_URL:
            return None
        if Redis is None:
            if not self._redis_checked:
                logger.warning("Redis package is not installed; using memory fallback")
                self._redis_checked = True
            return None
        if self._redis_checked:
            return self._redis

        self._redis_checked = True
        try:
            client = Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=0.2,
                socket_timeout=0.5,
                decode_responses=True,
            )
            client.ping()
            self._redis = client
            logger.info("Redis response cache enabled")
        except RedisError as exc:
            logger.warning("Redis response cache unavailable; using memory fallback: %s", exc)
            self._redis = None
        return self._redis

    def make_key(self, namespace: str, *parts: Any) -> str:
        encoded = json.dumps(jsonable_encoder(parts), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return f"{settings.CACHE_KEY_PREFIX}:{namespace}:{digest}"

    def get(self, key: str, ttl_seconds: int) -> tuple[bool, Any]:
        if not settings.CACHE_ENABLED:
            return False, None

        client = self._client()
        if client is not None:
            try:
                raw = client.get(key)
                if raw is not None:
                    return True, json.loads(raw)
            except (RedisError, json.JSONDecodeError) as exc:
                logger.warning("Redis cache read failed for %s: %s", key, exc)

        memory = self._memory_ttls.setdefault(key, TTLCache(ttl_seconds=ttl_seconds))
        return memory.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int, *, cache_empty: bool = False) -> None:
        if not settings.CACHE_ENABLED:
            return

        payload = jsonable_encoder(value)
        if not cache_empty and (payload == [] or payload == {} or payload is None):
            return

        client = self._client()
        if client is not None:
            try:
                client.setex(key, ttl_seconds, json.dumps(payload, separators=(",", ":")))
                return
            except (RedisError, TypeError, ValueError) as exc:
                logger.warning("Redis cache write failed for %s: %s", key, exc)

        memory = self._memory_ttls.setdefault(key, TTLCache(ttl_seconds=ttl_seconds))
        memory.set(key, payload)

    def clear_namespace(self, namespace: str) -> int:
        """Best-effort namespace clear for Redis. Memory fallback is process-local."""
        client = self._client()
        if client is None:
            self._memory_ttls.clear()
            return 0

        pattern = f"{settings.CACHE_KEY_PREFIX}:{namespace}:*"
        deleted = 0
        try:
            for key in client.scan_iter(pattern):
                deleted += client.delete(key)
        except RedisError as exc:
            logger.warning("Redis namespace clear failed for %s: %s", namespace, exc)
        return deleted

    def status(self) -> dict[str, Any]:
        client = self._client()
        return {
            "enabled": settings.CACHE_ENABLED,
            "backend": "redis" if client is not None else "memory",
            "redis_configured": bool(settings.REDIS_URL),
        }


response_cache = ResponseCache()
