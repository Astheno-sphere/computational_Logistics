"""Shared disaster semantic-filter helpers extracted from postprocessor."""

from __future__ import annotations

import re


def load_disaster_overlays(*, load_reference_json_func) -> dict:
    """Load shared disaster overlay reference data from reference/disasters.json."""
    data = load_reference_json_func("disasters.json")
    overlays = data.get("overlays", {}) if isinstance(data, dict) else {}
    return overlays if isinstance(overlays, dict) else {}


def item_disaster_key(
    item: dict,
    catalog_source: dict | None,
    *,
    overlays: dict,
    load_source_metadata_func,
) -> str | None:
    metadata = load_source_metadata_func(item.get("source_id")) or {}
    for candidate in (
        metadata.get("event_type"),
        (catalog_source or {}).get("event_type"),
        item.get("pack_id"),
    ):
        text = str(candidate or "").strip().lower()
        if not text:
            continue
        if text in overlays:
            return text
        plural = f"{text}s"
        if plural in overlays:
            return plural
    return None


def query_semantic_filter_tokens(query: str, disaster_key: str | None, *, overlays: dict) -> list[tuple[str, dict]]:
    if not disaster_key:
        return []
    overlay = overlays.get(disaster_key) or {}
    semantic_filters = overlay.get("semantic_filters") or {}
    if not isinstance(semantic_filters, dict):
        return []
    query_lower = str(query or "").strip().lower()
    matched = []
    for token, spec in semantic_filters.items():
        if not isinstance(spec, dict):
            continue
        if re.search(rf"\b{re.escape(str(token).lower())}\b", query_lower):
            matched.append((str(token), spec))
    return matched


def apply_disaster_semantic_filters(
    item: dict,
    catalog_source: dict | None,
    query: str,
    *,
    overlays: dict,
    item_disaster_key_func,
    query_semantic_filter_tokens_func,
) -> None:
    disaster_key = item_disaster_key_func(item, catalog_source)
    matched = query_semantic_filter_tokens_func(query, disaster_key)
    if not matched:
        return

    filters = item.get("filters")
    if not isinstance(filters, dict):
        filters = {}

    for _, spec in matched:
        field = str(spec.get("field") or "").strip()
        if not field or field in filters:
            continue
        if "min" in spec:
            filters[field] = {"min": spec.get("min")}
        elif "max" in spec:
            filters[field] = {"max": spec.get("max")}

    if filters:
        item["filters"] = filters
