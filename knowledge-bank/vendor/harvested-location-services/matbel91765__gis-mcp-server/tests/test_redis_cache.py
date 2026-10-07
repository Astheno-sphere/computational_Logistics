"""Tests for the Redis cache backend (with a fake async client)."""

import pytest

from locusync import cache as cache_mod
from locusync.cache import RedisCache
from locusync.config import Config, set_config


class FakeRedis:
    """Minimal async Redis stand-in (get/set with ex ignored)."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value


class TestRedisCache:
    @pytest.mark.asyncio
    async def test_set_get_roundtrip(self):
        c = RedisCache("redis://x", client=FakeRedis())
        await c.set("k", {"v": 1})
        assert await c.get("k") == {"v": 1}
        assert c.hits == 1

    @pytest.mark.asyncio
    async def test_miss(self):
        c = RedisCache("redis://x", client=FakeRedis())
        assert await c.get("absent") is None
        assert c.misses == 1

    @pytest.mark.asyncio
    async def test_prefix_applied(self):
        fake = FakeRedis()
        c = RedisCache("redis://x", client=fake)
        await c.set("mykey", 42)
        assert "locusync:mykey" in fake.store

    def test_stats_backend(self):
        c = RedisCache("redis://x", client=FakeRedis())
        assert c.stats()["backend"] == "redis"


class TestBackendSelection:
    def test_falls_back_to_inprocess_without_redis_url(self):
        cfg = Config()
        cfg.cache.enabled = True
        cfg.cache.redis_url = ""
        set_config(cfg)
        cache_mod.reset_cache()
        cache = cache_mod.get_cache()
        assert cache.__class__.__name__ == "TTLCache"
