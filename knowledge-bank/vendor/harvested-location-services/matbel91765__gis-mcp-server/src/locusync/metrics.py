"""Lightweight in-process metrics for observability.

Tracks per-tool call counts, error counts and cumulative latency, and renders
the Prometheus text exposition format (no external dependency). Exposed at
``/metrics`` (HTTP transport) and via the ``health`` MCP tool.
"""

import functools
import threading
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class Metrics:
    """Thread-safe counters (mutated from worker threads via to_thread tools)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: dict[str, int] = defaultdict(int)
        self.errors: dict[str, int] = defaultdict(int)
        self.duration_s: dict[str, float] = defaultdict(float)

    def record(self, tool: str, seconds: float, *, is_error: bool) -> None:
        with self._lock:
            self.calls[tool] += 1
            self.duration_s[tool] += seconds
            if is_error:
                self.errors[tool] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            tools = {}
            for tool in sorted(self.calls):
                calls = self.calls[tool]
                tools[tool] = {
                    "calls": calls,
                    "errors": self.errors.get(tool, 0),
                    "avg_ms": round(self.duration_s[tool] / calls * 1000, 2) if calls else 0.0,
                }
            return {"tools": tools}

    def reset(self) -> None:
        with self._lock:
            self.calls.clear()
            self.errors.clear()
            self.duration_s.clear()


metrics = Metrics()


def instrument(name: str) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorate an async tool to record call count, errors and latency.

    A returned response with ``success is False`` counts as an error.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            is_error = False
            try:
                result = await func(*args, **kwargs)
                if isinstance(result, dict) and result.get("success") is False:
                    is_error = True
                return result
            except Exception:
                is_error = True
                raise
            finally:
                metrics.record(name, time.perf_counter() - start, is_error=is_error)

        return wrapper

    return decorator


def render_prometheus() -> str:
    """Render current metrics (plus cache stats) in Prometheus text format."""
    from locusync.cache import get_cache

    snap = metrics.snapshot()["tools"]
    lines: list[str] = []

    lines.append("# HELP locusync_tool_calls_total Total tool invocations")
    lines.append("# TYPE locusync_tool_calls_total counter")
    for tool, m in snap.items():
        lines.append(f'locusync_tool_calls_total{{tool="{tool}"}} {m["calls"]}')

    lines.append("# HELP locusync_tool_errors_total Total tool errors")
    lines.append("# TYPE locusync_tool_errors_total counter")
    for tool, m in snap.items():
        lines.append(f'locusync_tool_errors_total{{tool="{tool}"}} {m["errors"]}')

    lines.append("# HELP locusync_tool_latency_ms_avg Average tool latency (ms)")
    lines.append("# TYPE locusync_tool_latency_ms_avg gauge")
    for tool, m in snap.items():
        lines.append(f'locusync_tool_latency_ms_avg{{tool="{tool}"}} {m["avg_ms"]}')

    cache = get_cache()
    if cache is not None:
        stats = cache.stats()
        lines.append("# HELP locusync_cache_hits_total Result cache hits")
        lines.append("# TYPE locusync_cache_hits_total counter")
        lines.append(f'locusync_cache_hits_total {stats["hits"]}')
        lines.append("# HELP locusync_cache_misses_total Result cache misses")
        lines.append("# TYPE locusync_cache_misses_total counter")
        lines.append(f'locusync_cache_misses_total {stats["misses"]}')

    return "\n".join(lines) + "\n"
