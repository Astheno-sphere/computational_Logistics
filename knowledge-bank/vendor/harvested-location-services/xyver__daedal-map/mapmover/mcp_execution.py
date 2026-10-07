"""Bounded worker isolation for synchronous MCP tool work.

Most geography helpers are intentionally synchronous because they are also used
by the REST and local runtimes.  Calling them directly from an ``async`` MCP
route blocks the ASGI event loop while DuckDB, pandas, or object storage is
working.  This module provides one small, shared boundary for those calls.

The worker semaphore is retained until the underlying future actually finishes,
including after the HTTP-facing timeout.  Python cannot safely kill an
arbitrary thread, so this prevents timed-out work from turning into an
unbounded background pile while keeping health and unrelated app routes alive.
"""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar


T = TypeVar("T")


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(str(os.environ.get(name, default)).strip()))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return max(0.0, float(str(os.environ.get(name, default)).strip()))
    except (TypeError, ValueError):
        return default


class MCPExecutionCapacityError(RuntimeError):
    """Raised when every isolated MCP worker is still occupied."""


class MCPExecutionTimeoutError(TimeoutError):
    """Raised when a tool exceeds its hosted response budget."""


_MAX_WORKERS = _env_int("MCP_EXECUTION_MAX_WORKERS", 2)
# Full country reference graphs can require roughly a minute for the first
# object-store/DuckDB read.  Keep the response budget aligned with the cloud
# geography smoke while retaining the bounded worker pool and fail-fast
# capacity guard; timed-out work still holds its slot until it really exits.
_DEFAULT_TIMEOUT_SECONDS = _env_int("MCP_EXECUTION_TIMEOUT_SECONDS", 120)
_CAPACITY_WAIT_SECONDS = _env_float("MCP_EXECUTION_CAPACITY_WAIT_SECONDS", 2.0)
_EXECUTOR = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="mcp-tool")
_CAPACITY = threading.BoundedSemaphore(_MAX_WORKERS)
_STATE_LOCK = threading.Lock()
_ACTIVE_WORKERS = 0


def _increment_active_workers() -> None:
    global _ACTIVE_WORKERS
    with _STATE_LOCK:
        _ACTIVE_WORKERS += 1


def _decrement_active_workers() -> None:
    global _ACTIVE_WORKERS
    with _STATE_LOCK:
        _ACTIVE_WORKERS = max(0, _ACTIVE_WORKERS - 1)


def _release_capacity(_future: Future[Any]) -> None:
    _decrement_active_workers()
    _CAPACITY.release()


async def run_mcp_blocking(
    tool_name: str,
    function: Callable[..., T],
    /,
    *args: Any,
    timeout_seconds: float | None = None,
    capacity_wait_seconds: float | None = None,
    cancellation_event: threading.Event | None = None,
    **kwargs: Any,
) -> T:
    """Run synchronous tool work off-loop with fail-fast bounded capacity.

    The timeout bounds the caller's wait, not the underlying thread.  Capacity
    remains charged until that thread exits so retries cannot multiply work
    that the first caller abandoned.
    """

    wait_budget = max(
        0.0,
        float(_CAPACITY_WAIT_SECONDS if capacity_wait_seconds is None else capacity_wait_seconds),
    )
    deadline = asyncio.get_running_loop().time() + wait_budget
    while not _CAPACITY.acquire(blocking=False):
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise MCPExecutionCapacityError(
                f"MCP execution capacity is busy; retry {tool_name} shortly"
            )
        await asyncio.sleep(min(0.025, remaining))
    _increment_active_workers()

    try:
        future = _EXECUTOR.submit(partial(function, *args, **kwargs))
    except BaseException:
        _decrement_active_workers()
        _CAPACITY.release()
        raise
    future.add_done_callback(_release_capacity)

    wrapped = asyncio.wrap_future(future)
    budget = max(0.001, float(timeout_seconds or _DEFAULT_TIMEOUT_SECONDS))
    try:
        return await asyncio.wait_for(asyncio.shield(wrapped), timeout=budget)
    except asyncio.TimeoutError as exc:
        if cancellation_event is not None:
            cancellation_event.set()
        raise MCPExecutionTimeoutError(
            f"{tool_name} exceeded the hosted execution budget of {budget:g} seconds"
        ) from exc


def execution_status() -> dict[str, int]:
    """Return non-sensitive configuration for diagnostics and readiness logs."""

    with _STATE_LOCK:
        active_workers = _ACTIVE_WORKERS
    return {
        "max_workers": _MAX_WORKERS,
        "active_workers": active_workers,
        "default_timeout_seconds": _DEFAULT_TIMEOUT_SECONDS,
    }
