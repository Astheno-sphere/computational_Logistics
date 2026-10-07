"""Shared request-risk gate helpers.

This module provides a normalized result shape for lane-specific request gates.
It does not impose one global threshold policy. Instead, each lane can attach its
own thresholds and consequences while still reporting risk in one shared format.
"""

from __future__ import annotations


def build_gate_result(
    *,
    status: str,
    lane: str,
    reason: str,
    soft_cap: int | float | None = None,
    hard_cap: int | float | None = None,
    estimated_count: int | None = None,
    estimated_size_mb: float | None = None,
    override_allowed: bool = False,
    suggested_narrowing: list[str] | None = None,
    fallback_strategy: str | None = None,
    measure: str | None = None,
    details: dict | None = None,
) -> dict:
    gate = {
        "status": str(status or "safe"),
        "lane": str(lane or "unknown"),
        "reason": str(reason or "").strip(),
        "soft_cap": soft_cap,
        "hard_cap": hard_cap,
        "estimated_count": estimated_count,
        "estimated_size_mb": estimated_size_mb,
        "override_allowed": bool(override_allowed),
        "suggested_narrowing": [str(item).strip() for item in (suggested_narrowing or []) if str(item).strip()],
        "fallback_strategy": str(fallback_strategy).strip() if fallback_strategy else None,
        "measure": str(measure).strip() if measure else None,
        "details": details or {},
    }
    return gate


def safe_gate(**kwargs) -> dict:
    return build_gate_result(status="safe", **kwargs)


def warn_gate(**kwargs) -> dict:
    return build_gate_result(status="warn", **kwargs)


def block_gate(**kwargs) -> dict:
    return build_gate_result(status="block", **kwargs)
