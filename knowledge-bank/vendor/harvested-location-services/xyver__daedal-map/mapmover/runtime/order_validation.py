"""Shared execution-item validation helpers extracted from the executor."""

from __future__ import annotations

from .source_hints import source_geometry_kind, source_geometry_subkind


def execution_requires_metric(item: dict, source_info: dict | None) -> bool:
    if item.get("type") in {"derived", "derived_result"}:
        return False
    if item.get("mode") == "events":
        return False
    if source_geometry_kind(source_info) == "entity" and source_geometry_subkind(source_info) == "point":
        return False

    data_type = (source_info or {}).get("data_type", "metrics")
    if isinstance(data_type, list):
        if "events" in data_type and item.get("mode") != "aggregate":
            return False
        return "metrics" in data_type
    return data_type == "metrics"


def validate_execution_items(
    items: list,
    *,
    get_source_from_catalog_func,
    execution_requires_metric_func,
) -> str | None:
    for idx, item in enumerate(items, start=1):
        source_id = item.get("source_id")
        pack_id = item.get("pack_id")
        if not source_id:
            if pack_id:
                return f"Item {idx} could not resolve pack_id '{pack_id}' to a concrete source_id"
            return f"Item {idx} is missing source_id"

        source_info = get_source_from_catalog_func(source_id)
        if not source_info:
            return f"Item {idx} references unknown source_id '{source_id}'"

        if execution_requires_metric_func(item, source_info) and not item.get("metric"):
            return f"Item {idx} for source '{source_id}' is missing a concrete metric"

    return None
