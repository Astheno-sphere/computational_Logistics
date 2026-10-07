"""Tests for the metrics registry, instrument decorator and Prometheus render."""

import pytest

from locusync import cache as cache_mod
from locusync.config import Config, set_config
from locusync.metrics import Metrics, instrument, metrics, render_prometheus


class TestMetricsRegistry:
    def test_record_and_snapshot(self):
        m = Metrics()
        m.record("geocode", 0.1, is_error=False)
        m.record("geocode", 0.3, is_error=True)
        snap = m.snapshot()["tools"]["geocode"]
        assert snap["calls"] == 2
        assert snap["errors"] == 1
        assert snap["avg_ms"] == pytest.approx(200.0, abs=1)

    def test_reset(self):
        m = Metrics()
        m.record("x", 0.01, is_error=False)
        m.reset()
        assert m.snapshot()["tools"] == {}


class TestInstrument:
    @pytest.mark.asyncio
    async def test_counts_calls_and_errors(self):
        metrics.reset()

        @instrument("mytool")
        async def tool(ok=True):
            return {"success": ok}

        await tool()
        await tool(ok=False)
        snap = metrics.snapshot()["tools"]["mytool"]
        assert snap["calls"] == 2
        assert snap["errors"] == 1

    @pytest.mark.asyncio
    async def test_exception_counts_as_error(self):
        metrics.reset()

        @instrument("boom")
        async def tool():
            raise ValueError("nope")

        with pytest.raises(ValueError):
            await tool()
        assert metrics.snapshot()["tools"]["boom"]["errors"] == 1


class TestRenderPrometheus:
    def test_exposition_format(self):
        metrics.reset()
        metrics.record("route", 0.05, is_error=False)
        # Enable cache so cache metrics are included.
        cfg = Config()
        cfg.cache.enabled = True
        set_config(cfg)
        cache_mod.reset_cache()

        text = render_prometheus()
        assert "# TYPE locusync_tool_calls_total counter" in text
        assert 'locusync_tool_calls_total{tool="route"} 1' in text
        assert "locusync_cache_hits_total" in text
        assert text.endswith("\n")
