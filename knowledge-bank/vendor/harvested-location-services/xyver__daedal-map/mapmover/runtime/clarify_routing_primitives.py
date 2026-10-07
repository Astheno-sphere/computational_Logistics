"""Shared clarify and pack-routing helpers for postprocessing."""

from __future__ import annotations

from .order_execution_policy import MAX_EVENT_LIMIT
from .source_hints import get_routing_hints


def build_pack_load_clarify(item: dict, pack: dict) -> str:
    load_policy = pack.get("load_policy") or {}
    pack_name = pack.get("pack_name") or pack.get("pack_id") or "this pack"
    source_count = pack.get("source_count", 0)
    size_mb = pack.get("file_size_mb_total", 0)
    row_count = pack.get("row_count_total", 0)
    reason = load_policy.get("reason") or "it is too large to load safely in one step"
    return (
        f"{pack_name} is too large to load all at once right now. "
        f"It has {source_count} sources, about {size_mb} MB, and {row_count:,} rows. "
        f"{reason}. Please narrow it to a source, geography level, metric, or time range."
    )


def detect_full_pack_load_clarify(
    items: list,
    catalog: dict,
    *,
    is_full_pack_load_func,
    get_catalog_pack_func,
    build_pack_load_clarify_func,
) -> str | None:
    for item in items:
        if not is_full_pack_load_func(item):
            continue
        pack = get_catalog_pack_func(catalog, item.get("pack_id"))
        if not pack:
            return f"Pack '{item.get('pack_id')}' was not found."
        if not (pack.get("load_policy") or {}).get("can_load_all_sources"):
            return build_pack_load_clarify_func(item, pack)
    return None


def expand_full_pack_loads(
    items: list,
    catalog: dict,
    *,
    is_full_pack_load_func,
    catalog_sources_func,
    get_catalog_pack_func,
    source_supports_events_func,
    source_has_metrics_func,
) -> list:
    expanded = []
    source_lookup = {
        src.get("source_id"): src
        for src in catalog_sources_func(catalog)
        if src.get("source_id")
    }

    for item in items:
        if not is_full_pack_load_func(item):
            expanded.append(item)
            continue

        pack = get_catalog_pack_func(catalog, item.get("pack_id"))
        if not pack:
            expanded.append(item)
            continue

        pack_source_ids = pack.get("source_ids", [])
        event_source_ids = [
            sid for sid in pack_source_ids
            if source_supports_events_func(source_lookup.get(sid) or {})
        ]
        # Events-first: a full pack load on an event pack means "show the
        # events", not one choropleth per aggregate metric. Only fan out to
        # the non-event sources when the pack has no event source at all.
        target_source_ids = event_source_ids or pack_source_ids

        for source_id in target_source_ids:
            source = source_lookup.get(source_id) or {}
            new_item = {k: v for k, v in item.items() if k not in {"load_scope", "all_sources"}}
            new_item["source_id"] = source_id
            new_item["_expanded_from_pack"] = item.get("pack_id")
            if source_supports_events_func(source):
                new_item.setdefault("mode", "events")
                new_item.pop("metric", None)
                # "Load all" should cover the full archive, not just the
                # default slice of the most significant events.
                new_item.setdefault("limit", MAX_EVENT_LIMIT)
            elif not new_item.get("metric") and source_has_metrics_func(source):
                new_item["metric"] = "*"
            elif not source_has_metrics_func(source):
                new_item.pop("metric", None)
            expanded.append(new_item)

    return expanded


def build_multiple_paths_clarify(item: dict, metadata: dict) -> str:
    """Build a grounded clarify message for metadata-declared multi-path ambiguity."""
    routing_hints = get_routing_hints(metadata)
    summary = str(routing_hints.get("clarify_multiple_paths_summary") or "").strip()
    dimensions = routing_hints.get("clarify_path_dimensions") or []
    options = []

    if "view_mode" in dimensions:
        options = [str(v).strip() for v in (routing_hints.get("view_mode_options") or []) if str(v).strip()]

    source_name = metadata.get("source_name") or item.get("source_id") or item.get("pack_id") or "this source"
    if not summary:
        if options:
            summary = f"{source_name} supports multiple valid views for this request."
        else:
            summary = f"{source_name} supports multiple valid paths for this request."

    if options:
        options_text = " or ".join(options)
        return f"{summary} Would you like {options_text}?"
    return f"{summary} Which path would you like?"


def detect_multiple_path_clarify(
    items: list,
    catalog: dict,
    *,
    hints: dict | None = None,
    query_explicit_view_mode_func,
    get_item_source_metadata_func,
    build_multiple_paths_clarify_func,
) -> str | None:
    """Return a clarify message when metadata declares an ambiguous multi-path request."""
    query = (hints or {}).get("original_query", "")
    explicit_events, explicit_aggregate = query_explicit_view_mode_func(query)

    for item in items:
        metadata = get_item_source_metadata_func(item, catalog)
        routing_hints = get_routing_hints(metadata)
        if not routing_hints.get("clarify_on_multiple_paths"):
            continue

        dimensions = routing_hints.get("clarify_path_dimensions") or []
        if "view_mode" not in dimensions:
            continue

        if explicit_events == explicit_aggregate:
            return build_multiple_paths_clarify_func(item, metadata)

    return None
