"""Shared helpers for mixed-order and multi-layer execution."""

from __future__ import annotations


def execute_split_order_impl(
    order: dict,
    add_items: list,
    remove_items: list,
    source_id: str | None,
    *,
    execute_removal_order_func,
    execute_order_func,
    logger,
) -> dict:
    """Execute a split add/remove order and combine the results."""
    results = []

    if remove_items:
        remove_order = {
            **order,
            "action": "remove",
            "items": remove_items,
            "summary": f"Removing {len(remove_items)} region(s)",
        }
        remove_result = execute_removal_order_func(remove_order, remove_items, source_id)
        results.append(remove_result)
        logger.info(f"Split order: removed {remove_result.get('count', 0)} items")

    add_result = None
    if add_items:
        add_order = {
            **order,
            "action": "add",
            "items": add_items,
        }
        add_result = execute_order_func(add_order)
        results.append(add_result)
        logger.info(f"Split order: added {add_result.get('count', 0)} items")

    if len(results) == 1:
        return results[0]

    return {
        "type": "mixed_order",
        "results": results,
        "summary": order.get("summary", f"Processed {len(add_items)} adds and {len(remove_items)} removes"),
        "add_count": add_result.get("count", 0) if add_result else 0,
        "remove_count": results[0].get("count", 0) if remove_items else 0,
    }


def execute_mixed_order_if_needed_impl(
    order: dict,
    items: list,
    source_id: str | None,
    *,
    execute_split_order_func,
    logger,
) -> dict | None:
    """Check for explicit mixed add/remove items and execute the split path."""
    add_items = []
    remove_items = []

    for item in items:
        item_action = item.get("action", "add")
        if item_action == "remove":
            remove_items.append(item)
        else:
            add_items.append(item)

    if remove_items:
        logger.info(f"Mixed order detected: {len(add_items)} adds, {len(remove_items)} removes")
        return execute_split_order_func(order, add_items, remove_items, source_id)

    return None


def classify_execution_family_impl(
    item: dict,
    *,
    get_source_from_catalog_func,
    special_geometry_levels,
    has_geometry_data_type_func,
) -> str:
    """Classify an item into geometry/events/metrics execution families."""
    source_id = item.get("source_id")
    source_info = get_source_from_catalog_func(source_id) if source_id else {}
    data_type = (source_info or {}).get("data_type", "metrics")
    geo_level = str((source_info or {}).get("geographic_level") or "").strip().lower()

    if item.get("overlay_type") or (geo_level in special_geometry_levels and has_geometry_data_type_func(data_type)):
        return "geometry"

    if item.get("mode") == "aggregate":
        return "metrics"

    if isinstance(data_type, list):
        supports_events = "events" in data_type
    else:
        supports_events = data_type == "events"

    if item.get("mode") == "events" or supports_events:
        return "events"

    return "metrics"


def execute_multi_layer_order_if_needed_impl(
    order: dict,
    items: list,
    *,
    classify_execution_family_func,
    execute_geometry_order_func,
    execute_order_func,
) -> dict | None:
    """Execute multi-item orders as independent shared layers."""
    if len(items) <= 1:
        return None

    results = []
    for item in items:
        family = classify_execution_family_func(item)
        sub_order = {**order, "items": [item]}
        if family == "geometry":
            result = execute_geometry_order_func(sub_order)
        else:
            result = execute_order_func(sub_order)
        if isinstance(result, dict):
            result.setdefault("layer_source_id", item.get("source_id"))
            result.setdefault("layer_family", family)
        results.append(result)

    return {
        "type": "mixed_order",
        "results": results,
        "summary": order.get("summary", f"Rendered {len(results)} map layers"),
        "layer_count": len(results),
    }
