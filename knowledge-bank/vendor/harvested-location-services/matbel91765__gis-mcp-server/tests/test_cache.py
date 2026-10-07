"""Tests for the TTL/LRU cache and the @cached decorator."""

import asyncio

import pytest

from locusync import cache as cache_mod
from locusync.cache import TTLCache, cached, make_key
from locusync.config import Config, set_config


class TestMakeKey:
    def test_stable_and_order_independent(self):
        assert make_key("ns", a=1, b=2) == make_key("ns", b=2, a=1)

    def test_namespace_and_values_change_key(self):
        assert make_key("ns", a=1) != make_key("ns", a=2)
        assert make_key("ns1", a=1) != make_key("ns2", a=1)


class TestTTLCache:
    @pytest.mark.asyncio
    async def test_set_get(self):
        c = TTLCache()
        await c.set("k", {"v": 1})
        assert await c.get("k") == {"v": 1}
        assert c.hits == 1 and c.misses == 0

    @pytest.mark.asyncio
    async def test_miss(self):
        c = TTLCache()
        assert await c.get("absent") is None
        assert c.misses == 1

    @pytest.mark.asyncio
    async def test_expiry(self):
        c = TTLCache(ttl=0.05)
        await c.set("k", 1)
        await asyncio.sleep(0.07)
        assert await c.get("k") is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        c = TTLCache(maxsize=2)
        await c.set("a", 1)
        await c.set("b", 2)
        await c.get("a")          # 'a' now most-recently used
        await c.set("c", 3)       # evicts least-recently used ('b')
        assert await c.get("b") is None
        assert await c.get("a") == 1
        assert await c.get("c") == 3

    @pytest.mark.asyncio
    async def test_stats(self):
        c = TTLCache()
        await c.set("k", 1)
        await c.get("k")
        await c.get("miss")
        stats = c.stats()
        assert stats["hits"] == 1 and stats["misses"] == 1
        assert stats["hit_rate"] == 0.5


class TestCachedDecorator:
    def _enable_cache(self):
        cfg = Config()
        cfg.cache.enabled = True
        set_config(cfg)
        cache_mod.reset_cache()

    @pytest.mark.asyncio
    async def test_caches_success_only(self):
        self._enable_cache()
        calls = {"n": 0}

        @cached("t", key_args=("x",))
        async def fn(x, ok=True):
            calls["n"] += 1
            return {"success": ok, "data": x}

        await fn(1)
        await fn(1)
        assert calls["n"] == 1  # second call served from cache

        # Errors are never cached.
        await fn(2, ok=False)
        await fn(2, ok=False)
        assert calls["n"] == 3

    @pytest.mark.asyncio
    async def test_bypassed_when_disabled(self):
        cfg = Config()
        cfg.cache.enabled = False
        set_config(cfg)
        cache_mod.reset_cache()
        calls = {"n": 0}

        @cached("t", key_args=("x",))
        async def fn(x):
            calls["n"] += 1
            return {"success": True, "data": x}

        await fn(1)
        await fn(1)
        assert calls["n"] == 2
