"""Async-safe TTL + LRU cache for cacheable network results.

Geocoding, routing and elevation lookups are highly cacheable: the same address
or coordinate pair returns the same answer for a long time. This in-process
cache cuts latency to zero on repeats and protects rate-limited upstreams
(Nominatim allows 1 req/s).

The cache is intentionally dependency-free (no Redis required). A distributed
backend can be added later behind the same ``get``/``set`` interface.
"""

import asyncio
import functools
import hashlib
import inspect
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ParamSpec, TypeVar, cast

logger = logging.getLogger(__name__)


def make_key(namespace: str, **parts: Any) -> str:
    """Build a stable cache key from a namespace and keyword parts."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{namespace}:{digest}"


class TTLCache:
    """Async-safe cache with per-entry TTL and global LRU eviction."""

    def __init__(self, maxsize: int = 2048, ttl: float = 86400.0):
        self.maxsize = maxsize
        self.ttl = ttl
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0

    async def get(self, key: str) -> Any | None:
        """Return the cached value or ``None`` if missing/expired."""
        async with self._lock:
            item = self._store.get(key)
            if item is None:
                self.misses += 1
                return None
            expires, value = item
            if expires < time.monotonic():
                del self._store[key]
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
            return value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value with an optional per-entry TTL override."""
        async with self._lock:
            effective_ttl = self.ttl if ttl is None else ttl
            self._store[key] = (time.monotonic() + effective_ttl, value)
            self._store.move_to_end(key)
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self._store),
            "maxsize": self.maxsize,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }


class RedisCache:
    """Shared/persistent cache backed by Redis (same interface as TTLCache).

    Values are JSON-serialized; each key gets a TTL. Hit/miss counters are
    process-local (approximate across replicas).
    """

    def __init__(self, url: str, ttl: float = 86400.0, client: Any = None):
        self.ttl = ttl
        self.prefix = "locusync:"
        self.hits = 0
        self.misses = 0
        if client is not None:
            self._redis = client
        else:  # pragma: no cover - requires the redis package + a server
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(url)

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(self.prefix + key)
        if raw is None:
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        effective_ttl = self.ttl if ttl is None else ttl
        await self._redis.set(
            self.prefix + key, json.dumps(value), ex=int(effective_ttl)
        )

    async def clear(self) -> None:  # pragma: no cover - destructive, rarely used
        await self._redis.flushdb()

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "backend": "redis",
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }


_cache: "TTLCache | RedisCache | None" = None


def get_cache() -> "TTLCache | RedisCache | None":
    """Return the global cache, or ``None`` when caching is disabled.

    Uses Redis when ``cache.redis_url`` is set and the ``redis`` package is
    importable; otherwise an in-process TTL/LRU cache.
    """
    global _cache
    # Imported lazily to avoid a circular import at module load time.
    from locusync.config import get_config

    cache_cfg = get_config().cache
    if not cache_cfg.enabled:
        return None
    if _cache is None:
        if cache_cfg.redis_url:
            try:
                _cache = RedisCache(cache_cfg.redis_url, ttl=cache_cfg.ttl)
                logger.info("Using Redis cache backend")
            except Exception as e:  # pragma: no cover - import/connection failure
                logger.warning(f"Redis cache unavailable ({e}); using in-process cache")
                _cache = TTLCache(maxsize=cache_cfg.maxsize, ttl=cache_cfg.ttl)
        else:
            _cache = TTLCache(maxsize=cache_cfg.maxsize, ttl=cache_cfg.ttl)
    return _cache


def reset_cache() -> None:
    """Drop the global cache instance (used by tests)."""
    global _cache
    _cache = None


P = ParamSpec("P")
T = TypeVar("T")


def cached(
    namespace: str,
    *,
    key_args: Sequence[str] | None = None,
    ttl: float | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator caching the result of an async tool function.

    Only responses with ``success is True`` are cached, so transient errors are
    never persisted. The cache key is derived from the selected arguments
    (``key_args``) or from all arguments when omitted.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        signature = inspect.signature(func)

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            cache = get_cache()
            if cache is None:
                return await func(*args, **kwargs)

            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            params = dict(bound.arguments)
            if key_args is not None:
                params = {name: params.get(name) for name in key_args}

            key = make_key(namespace, **params)
            hit = await cache.get(key)
            if hit is not None:
                return cast(T, hit)

            result = await func(*args, **kwargs)
            if isinstance(result, dict) and result.get("success"):
                await cache.set(key, result, ttl=ttl)
            return result

        return wrapper

    return decorator
