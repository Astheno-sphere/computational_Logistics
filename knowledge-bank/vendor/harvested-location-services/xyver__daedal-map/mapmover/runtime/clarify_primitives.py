"""Shared clarify payload helpers."""

from __future__ import annotations


def build_clarify_result(order: dict, items: list, clarify_message: str) -> dict:
    """Build the standard early-return payload for grounded clarify responses."""
    return {
        "items": items,
        "derived_specs": [],
        "validation_summary": clarify_message,
        "all_valid": False,
        "needs_clarify": True,
        "clarify_message": clarify_message,
        "summary": order.get("summary"),
        "region": order.get("region"),
        "year": order.get("year"),
        "year_start": order.get("year_start"),
        "year_end": order.get("year_end"),
    }
