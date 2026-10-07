"""Shared alternate execution capabilities used by orchestrator-specific dispatch."""

from __future__ import annotations


def execute_remove_if_requested(
    *,
    action: str,
    order: dict,
    items: list,
    primary_source_id: str | None,
    execute_removal_order_func,
) -> dict | None:
    """Run the removal executor when the order action explicitly requests it."""
    if action != "remove":
        return None
    return execute_removal_order_func(order, items, primary_source_id)


def execute_mixed_if_applicable(
    *,
    order: dict,
    items: list,
    primary_source_id: str | None,
    execute_mixed_order_if_needed_func,
) -> dict | None:
    """Run the shared mixed-order capability if the items qualify."""
    return execute_mixed_order_if_needed_func(order, items, primary_source_id)


def execute_layered_if_applicable(
    *,
    order: dict,
    items: list,
    execute_multi_layer_order_if_needed_func,
) -> dict | None:
    """Run the shared multi-layer capability if the items qualify."""
    return execute_multi_layer_order_if_needed_func(order, items)


def select_event_items(*, items: list, get_source_from_catalog_func) -> list:
    """Return the subset of items that should execute through the event path."""

    def is_event_item(item: dict) -> bool:
        source_id = item.get("source_id")
        source_info = get_source_from_catalog_func(source_id) if source_id else None
        source_data_type = (source_info or {}).get("data_type", "metrics")
        if isinstance(source_data_type, list):
            supports_events = "events" in source_data_type
        else:
            supports_events = source_data_type == "events"
        if item.get("mode") == "aggregate":
            return False
        if item.get("mode") == "events":
            return supports_events
        return supports_events

    return [item for item in items if is_event_item(item)]


def execute_event_items_if_applicable(
    *,
    order: dict,
    event_items: list,
    execute_event_order_func,
) -> dict | None:
    """Run the shared event capability for the selected event items."""
    if not event_items:
        return None
    event_order = {**order, "items": event_items}
    result = execute_event_order_func(event_order)
    result["data_type"] = "events"
    result["source_id"] = event_items[0].get("source_id")
    return result


def route_default_special_order(
    *,
    order: dict,
    items: list,
    action: str,
    primary_source_id: str | None,
    get_source_from_catalog_func,
    execute_removal_order_func,
    execute_mixed_order_if_needed_func,
    execute_multi_layer_order_if_needed_func,
    execute_event_order_func,
) -> dict | None:
    """Shared default dispatch policy for alternate execution capabilities."""
    remove_result = execute_remove_if_requested(
        action=action,
        order=order,
        items=items,
        primary_source_id=primary_source_id,
        execute_removal_order_func=execute_removal_order_func,
    )
    if remove_result is not None:
        return remove_result

    mixed_result = execute_mixed_if_applicable(
        order=order,
        items=items,
        primary_source_id=primary_source_id,
        execute_mixed_order_if_needed_func=execute_mixed_order_if_needed_func,
    )
    if mixed_result is not None:
        return mixed_result

    layered_result = execute_layered_if_applicable(
        order=order,
        items=items,
        execute_multi_layer_order_if_needed_func=execute_multi_layer_order_if_needed_func,
    )
    if layered_result is not None:
        return layered_result

    event_items = select_event_items(
        items=items,
        get_source_from_catalog_func=get_source_from_catalog_func,
    )
    return execute_event_items_if_applicable(
        order=order,
        event_items=event_items,
        execute_event_order_func=execute_event_order_func,
    )
