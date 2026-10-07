from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager


API_QUERY_MAX_CONCURRENCY_PER_CALLER = int(os.getenv("API_QUERY_MAX_CONCURRENCY_PER_CALLER", "4"))
API_QUERY_MAX_CONCURRENCY_GLOBAL = int(os.getenv("API_QUERY_MAX_CONCURRENCY_GLOBAL", "24"))

_active_by_caller: dict[str, int] = {}
_active_global = 0
_lock = asyncio.Lock()


@asynccontextmanager
async def acquire_query_slot(caller_key: str):
    global _active_global

    caller_key = (caller_key or "anonymous").strip() or "anonymous"
    async with _lock:
        caller_active = _active_by_caller.get(caller_key, 0)
        if caller_active >= API_QUERY_MAX_CONCURRENCY_PER_CALLER:
            raise QueryConcurrencyLimitError(
                code="rate_limited",
                message=(
                    f"Caller concurrency exceeded the current limit of "
                    f"{API_QUERY_MAX_CONCURRENCY_PER_CALLER}."
                ),
                details={
                    "scope": "caller",
                    "limit": API_QUERY_MAX_CONCURRENCY_PER_CALLER,
                    "active": caller_active,
                },
            )
        if _active_global >= API_QUERY_MAX_CONCURRENCY_GLOBAL:
            raise QueryConcurrencyLimitError(
                code="rate_limited",
                message=(
                    f"Global query concurrency exceeded the current limit of "
                    f"{API_QUERY_MAX_CONCURRENCY_GLOBAL}."
                ),
                details={
                    "scope": "global",
                    "limit": API_QUERY_MAX_CONCURRENCY_GLOBAL,
                    "active": _active_global,
                },
            )
        _active_by_caller[caller_key] = caller_active + 1
        _active_global += 1

    try:
        yield
    finally:
        async with _lock:
            current_caller_active = _active_by_caller.get(caller_key, 0)
            if current_caller_active <= 1:
                _active_by_caller.pop(caller_key, None)
            else:
                _active_by_caller[caller_key] = current_caller_active - 1
            _active_global = max(0, _active_global - 1)


class QueryConcurrencyLimitError(Exception):
    def __init__(self, *, code: str, message: str, details: dict[str, int | str]):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
