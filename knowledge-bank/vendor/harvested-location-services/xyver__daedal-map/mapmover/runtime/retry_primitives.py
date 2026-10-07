from __future__ import annotations


def resolve_event_sibling_source(
    catalog: dict,
    item: dict,
    *,
    scope_matches_region_func,
) -> str | None:
    pack_id = item.get("pack_id")
    if not pack_id:
        source_id = str(item.get("source_id") or "").strip()
        for source in catalog.get("sources", []):
            if source.get("source_id") == source_id:
                pack_id = source.get("pack_id")
                if pack_id:
                    item["pack_id"] = pack_id
                break
    if not pack_id:
        return None

    region = item.get("region")
    pack_sources = [
        s for s in catalog.get("sources", [])
        if s.get("pack_id") == pack_id and s.get("geojson_shape") == "event_shape"
    ]
    if not pack_sources:
        return None

    exact_matches = [
        s for s in pack_sources
        if s.get("scope") != "global" and scope_matches_region_func(s.get("scope", "global"), region)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0].get("source_id")

    global_matches = [s for s in pack_sources if s.get("scope") == "global"]
    if len(global_matches) == 1:
        return global_matches[0].get("source_id")

    if len(pack_sources) == 1:
        return pack_sources[0].get("source_id")
    return None


def reroute_item_to_event_sibling(
    item: dict,
    catalog: dict,
    *,
    resolve_pack_source_by_shape_func,
) -> bool:
    pack_id = item.get("pack_id")
    if not pack_id:
        return False
    event_source_id = resolve_pack_source_by_shape_func(catalog, pack_id, item.get("region"), "event_shape")
    if not event_source_id:
        return False
    item["source_id"] = event_source_id
    item["_resolved_from_pack"] = True
    item["mode"] = "events"
    item["event_file"] = "events"
    for field in (
        "aggregate_use_rolling",
        "aggregate_window_years",
        "aggregate_rollup_level",
        "aggregate_all_years",
    ):
        item.pop(field, None)
    return True


def reroute_item_to_aggregate_sibling(
    item: dict,
    catalog: dict,
    *,
    resolve_pack_aggregate_source_func,
) -> bool:
    pack_id = item.get("pack_id")
    if not pack_id:
        return False
    aggregate_source_id = resolve_pack_aggregate_source_func(catalog, pack_id, item.get("region"))
    if not aggregate_source_id:
        return False
    if str(item.get("source_id") or "").strip() == str(aggregate_source_id).strip():
        return False
    item["source_id"] = aggregate_source_id
    item["_resolved_from_pack"] = True
    item["_lock_source_id"] = True
    item.pop("mode", None)
    item.pop("event_file", None)
    item.pop("metric_label", None)
    return True


def build_event_retry_order(
    order: dict,
    items: list,
    catalog: dict,
    *,
    query_prefers_event_retry_func,
    scope_matches_region_func,
) -> dict | None:
    rebuilt_items = []
    for item in items:
        query = str(((item.get("_hints") or {}).get("original_query")) or "")
        if not query_prefers_event_retry_func(query):
            return None
        event_source_id = resolve_event_sibling_source(
            catalog,
            item,
            scope_matches_region_func=scope_matches_region_func,
        )
        if not event_source_id:
            return None
        rebuilt = dict(item)
        rebuilt["source_id"] = event_source_id
        rebuilt["mode"] = "events"
        rebuilt["event_file"] = "events"
        for field in (
            "aggregate_use_rolling",
            "aggregate_window_years",
            "aggregate_rollup_level",
            "aggregate_all_years",
        ):
            rebuilt.pop(field, None)
        rebuilt_items.append(rebuilt)
    if not rebuilt_items:
        return None
    return {**order, "items": rebuilt_items}


def execute_event_retry_fallback(
    order: dict,
    items: list,
    *,
    query_prefers_event_retry_func,
    scope_matches_region_func,
    execute_order_func,
    load_catalog_func,
) -> dict | None:
    """Run the shared aggregate-to-event retry path and decorate success."""
    if order.get("_event_retry_attempted"):
        return None

    retry_order = build_event_retry_order(
        order,
        items,
        load_catalog_func(),
        query_prefers_event_retry_func=query_prefers_event_retry_func,
        scope_matches_region_func=scope_matches_region_func,
    )
    if not retry_order:
        return None

    retry_result = execute_order_func({**retry_order, "_event_retry_attempted": True})
    if int(retry_result.get("count") or 0) <= 0:
        return None

    retry_result["fallback_used"] = True
    retry_result.setdefault(
        "fallback_note",
        "Initial aggregate execution returned no results, so the runtime retried the pack's event lane.",
    )
    return retry_result
