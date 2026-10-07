"""Shared catalog and source-capability helpers extracted from postprocessor."""

from __future__ import annotations


def catalog_sources(catalog: dict) -> list[dict]:
    sources = catalog.get("sources", [])
    return sources if isinstance(sources, list) else []


def get_catalog_source(catalog: dict, source_id: str | None) -> dict | None:
    if not source_id:
        return None
    for source in catalog_sources(catalog):
        if source.get("source_id") == source_id:
            return source
    return None


def is_full_pack_load(item: dict) -> bool:
    load_scope = str(item.get("load_scope") or "").strip().lower()
    return bool(item.get("pack_id")) and (
        load_scope in {"pack", "all_sources", "full_pack"}
        or item.get("all_sources") is True
    )


def source_supports_events(source: dict | None) -> bool:
    data_type = (source or {}).get("data_type")
    if isinstance(data_type, list):
        return "events" in data_type
    return data_type == "events"


def source_has_aggregate_files(
    catalog_source: dict | None,
    *,
    source_has_aggregate_files_func,
    data_root,
) -> bool:
    return source_has_aggregate_files_func(
        catalog_source,
        data_root=data_root,
    )


def source_supports_aggregate_mode(
    catalog_source: dict | None,
    *,
    source_supports_aggregate_mode_func,
    source_has_aggregate_files_func,
) -> bool:
    return source_supports_aggregate_mode_func(
        catalog_source,
        source_has_aggregate_files_func=source_has_aggregate_files_func,
    )


def source_requires_metric(
    item: dict,
    catalog_source: dict | None,
    *,
    source_is_location_shape_func,
    source_has_metrics_func,
) -> bool:
    if item.get("type") in {"derived", "derived_result"}:
        return False
    if item.get("mode") == "events":
        return False
    if source_is_location_shape_func(catalog_source):
        return False
    if not source_has_metrics_func(catalog_source):
        return False

    data_type = (catalog_source or {}).get("data_type", "metrics")
    if isinstance(data_type, list):
        if "events" in data_type and item.get("mode") != "aggregate":
            return False
        return "metrics" in data_type
    return data_type == "metrics"


def get_item_source_metadata(
    item: dict,
    catalog: dict,
    *,
    resolve_pack_source_func,
    load_source_metadata_func,
) -> dict:
    """Load source metadata for an item, resolving pack_id when needed."""
    source_id = item.get("source_id")
    if not source_id and item.get("pack_id"):
        source_id = resolve_pack_source_func(catalog, item.get("pack_id"), item.get("region"))
    if not source_id:
        return {}
    return load_source_metadata_func(source_id) or {}


def metric_display_name(
    source_id: str,
    metric_key: str,
    *,
    load_source_metadata_func,
) -> str:
    """Resolve a user-facing metric display name from source metadata."""
    metadata = load_source_metadata_func(source_id) or {}
    metric_info = (metadata.get("metrics") or {}).get(metric_key, {})
    return metric_info.get("name", metric_key) if isinstance(metric_info, dict) else metric_key
