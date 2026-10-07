"""Shared policy and logging helpers for order execution."""

from __future__ import annotations

import hashlib
import time


DEFAULT_EVENT_LIMIT = 1000
MAX_EVENT_LIMIT = 5000
SPECIAL_GEOMETRY_LEVELS = {"zcta", "tribal"}


def executor_trace_id(order: dict) -> str:
    summary = order.get("summary", "") or ""
    items = order.get("items", []) or []
    lead = items[0].get("source_id", "") if items else ""
    seed = f"{summary[:80]}|{lead}|{len(items)}"
    return hashlib.md5(seed.encode()).hexdigest()[:10]


def executor_log(trace_id: str, stage: str, started_at: float, extra: str = "", *, logger=None) -> float:
    now = time.perf_counter()
    elapsed_ms = (now - started_at) * 1000
    suffix = f" | {extra}" if extra else ""
    if logger is not None:
        logger.info(f"[executor:{trace_id}] {stage}: {elapsed_ms:.1f}ms{suffix}")
    return now
