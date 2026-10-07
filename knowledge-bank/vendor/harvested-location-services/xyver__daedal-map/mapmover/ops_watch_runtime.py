"""Lane-owned watch-scope preload helpers for Ops mode."""

from __future__ import annotations

from mapmover.ops_preprocessor import preprocess_ops_query


def preload_ops_watch_scope(*, query: str, watch_context: dict | None = None) -> dict:
    """Prepare the Ops watch bundle before a live watch or triage turn."""
    normalized_watch_context = watch_context if isinstance(watch_context, dict) else {}
    return {
        "watch_context": normalized_watch_context,
        "hints": preprocess_ops_query(query, watch_context=normalized_watch_context),
    }
