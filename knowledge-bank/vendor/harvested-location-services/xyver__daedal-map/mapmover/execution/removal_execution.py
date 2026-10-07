"""Shared removal execution helpers."""

from __future__ import annotations

import logging


def execute_removal_order_impl(
    order: dict,
    items: list,
    source_id: str,
    *,
    get_source_data_type_func,
    get_source_from_catalog_func,
    expand_region_func,
    get_loc_ids_by_region_func,
    get_event_ids_by_region_func,
    session_manager,
    coerce_year_func,
) -> dict:
    """
    Execute a removal order and return minimal identifiers for frontend removal.
    """
    logger = logging.getLogger(__name__)

    data_type = get_source_data_type_func(source_id) if source_id else "metrics"
    source_info = get_source_from_catalog_func(source_id)
    geo_level = source_info.get("geographic_level") if source_info else None

    if geo_level in ("zcta", "tribal", "watershed", "park"):
        data_type = "geometry"

    regions = []
    for item in items:
        region = item.get("region")
        if region:
            regions.extend(expand_region_func(region))
    regions = list(set(regions))

    metric_to_remove = None
    years_to_remove = []
    for item in items:
        if item.get("metric"):
            metric_to_remove = item.get("metric")
        item_year = coerce_year_func(item.get("year"))
        item_year_start = coerce_year_func(item.get("year_start"))
        item_year_end = coerce_year_func(item.get("year_end"))
        if item_year is not None:
            years_to_remove.append(item_year)
        if item_year_start is not None and item_year_end is not None:
            years_to_remove.extend(range(item_year_start, item_year_end + 1))
    years_to_remove = list(set(years_to_remove))

    session_id = order.get("session_id")
    cache = session_manager.get(session_id) if session_id else None

    response = {
        "data_type": data_type,
        "action": "remove",
        "source_id": source_id,
        "regions": regions,
    }

    if data_type == "geometry":
        loc_ids = get_loc_ids_by_region_func(source_id, regions) if regions else []
        response["loc_ids"] = loc_ids
        response["geographic_level"] = geo_level
        response["count"] = len(loc_ids)
        response["summary"] = order.get("summary", f"Removed {len(loc_ids)} areas from {', '.join(regions)}")

        if cache and loc_ids:
            removed = cache.remove_geometry_by_loc_ids(source_id, loc_ids)
            logger.info(f"Removed {removed} geometry items from session cache")

    elif data_type == "events":
        event_ids = get_event_ids_by_region_func(source_id, regions) if regions else []
        response["event_ids"] = event_ids
        response["count"] = len(event_ids)
        response["summary"] = order.get("summary", f"Removed {len(event_ids)} events from {', '.join(regions)}")

        if cache and event_ids:
            for eid in event_ids:
                cache._sent_all.discard(eid)
            source_set = cache._sent_by_source.get(source_id, set())
            for eid in event_ids:
                source_set.discard(eid)
            logger.info(f"Removed {len(event_ids)} event items from session cache")

    else:
        loc_ids = get_loc_ids_by_region_func(source_id, regions) if regions else []
        response["loc_ids"] = loc_ids
        response["years"] = years_to_remove
        response["metric"] = metric_to_remove
        response["count"] = len(loc_ids) * max(len(years_to_remove), 1)
        response["summary"] = order.get(
            "summary",
            f"Removed {metric_to_remove or 'data'} from {', '.join(regions) or 'selection'}",
        )

        if cache and metric_to_remove:
            removed = cache.clear_source(metric_to_remove)
            logger.info(f"Removed {removed} metric items from session cache")

    return response
