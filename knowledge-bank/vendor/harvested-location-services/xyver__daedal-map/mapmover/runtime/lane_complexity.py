"""Shared lane-complexity helpers.

These helpers let lanes keep shared-default protection logic below the
orchestrator boundary while still allowing lane-owned thresholds and messages.
"""

from __future__ import annotations


def distinct_runtime_sources(processed_order: dict | None) -> list[str]:
    """Return ordered distinct concrete source_ids from a processed order."""
    items = (processed_order or {}).get("items") or []
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        ordered.append(source_id)
    return ordered


def evaluate_source_count_handoff(
    processed_order: dict | None,
    *,
    max_distinct_sources: int,
) -> dict | None:
    """Return handoff info when a processed order exceeds the lane source cap."""
    sources = distinct_runtime_sources(processed_order)
    if len(sources) <= int(max_distinct_sources):
        return None
    return {
        "distinct_sources": sources,
        "distinct_source_count": len(sources),
        "max_distinct_sources": int(max_distinct_sources),
    }
