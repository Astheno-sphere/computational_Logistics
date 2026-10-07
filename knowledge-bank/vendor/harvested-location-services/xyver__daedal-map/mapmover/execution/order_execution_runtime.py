from __future__ import annotations


def execute_order_impl(
    order: dict,
    *,
    executor_trace_id_func,
    executor_log_func,
    perf_counter_func,
    logger,
    prepare_execution_items_func,
    get_source_data_type_func,
    route_special_order_func,
    collect_source_metadata_func,
    process_metric_items_func,
    build_metrics_response_func,
) -> dict:
    """
    Shared deterministic execution flow for confirmed orders.
    """
    t_execute_start = perf_counter_func()
    trace_id = executor_trace_id_func(order)
    items = order.get("items", [])
    summary = order.get("summary", "")
    action = order.get("action", "add")

    logger.info(f"[executor:{trace_id}] start | items={len(items)} action={action}")

    if not items:
        return {
            "type": "error",
            "message": "No items in order",
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
        }

    items, validation_error = prepare_execution_items_func(items)
    if validation_error:
        return {
            "type": "error",
            "message": validation_error,
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
        }

    primary_source_id = items[0].get("source_id") if items else None
    order_data_type = get_source_data_type_func(primary_source_id) if primary_source_id else "metrics"

    routed_result = route_special_order_func(
        order=order,
        items=items,
        action=action,
        primary_source_id=primary_source_id,
    )
    if routed_result is not None:
        return routed_result

    temporal_mode = any(item.get("year_start") and item.get("year_end") for item in items)

    metadata_state = collect_source_metadata_func(
        items=items,
        trace_id=trace_id,
    )
    target_countries = metadata_state["target_countries"]
    geo_levels = metadata_state["geo_levels"]
    sources_used = metadata_state["sources_used"]
    aggregate_item_cache = metadata_state["aggregate_item_cache"]
    normalized_geo_levels = sorted(str(level) for level in geo_levels if level is not None)
    executor_log_func(
        trace_id,
        "source_metadata_collected",
        t_execute_start,
        f"sources={len(sources_used)} geo_levels={normalized_geo_levels}",
    )

    year_data = {}
    boxes = {}
    all_years = set()
    metric_key = None
    all_metrics = []
    metric_year_ranges = {}
    metric_source_map = {}
    aggregation_trace = []
    loc_level_map = {}
    location_features = []
    requested_year_start = None
    requested_year_end = None
    all_region_codes = set()
    requested_geo_levels = set()

    item_state = process_metric_items_func(
        order=order,
        items=items,
        temporal_mode=temporal_mode,
        aggregate_item_cache=aggregate_item_cache,
        year_data=year_data,
        boxes=boxes,
        all_years=all_years,
        metric_key=metric_key,
        all_metrics=all_metrics,
        metric_year_ranges=metric_year_ranges,
        metric_source_map=metric_source_map,
        aggregation_trace=aggregation_trace,
        loc_level_map=loc_level_map,
        location_features=location_features,
        requested_year_start=requested_year_start,
        requested_year_end=requested_year_end,
        all_region_codes=all_region_codes,
        requested_geo_levels=requested_geo_levels,
        trace_id=trace_id,
    )
    if item_state.get("early_result") is not None:
        return item_state["early_result"]

    year_data = item_state["year_data"]
    boxes = item_state["boxes"]
    temporal_mode = item_state["temporal_mode"]
    all_years = item_state["all_years"]
    temporal_granularity = item_state["temporal_granularity"]
    temporal_use_timestamps = item_state["temporal_use_timestamps"]
    metric_key = item_state["metric_key"]
    all_metrics = item_state["all_metrics"]
    metric_year_ranges = item_state["metric_year_ranges"]
    metric_source_map = item_state["metric_source_map"]
    aggregation_trace = item_state["aggregation_trace"]
    loc_level_map = item_state["loc_level_map"]
    location_features = item_state["location_features"]
    requested_year_start = item_state["requested_year_start"]
    requested_year_end = item_state["requested_year_end"]
    all_region_codes = item_state["all_region_codes"]
    requested_geo_levels = item_state["requested_geo_levels"]
    cap_info = item_state.get("cap_info")

    executor_log_func(
        trace_id,
        "data_boxes_ready",
        t_execute_start,
        f"temporal={temporal_mode} boxes={len(boxes or {})} times={len(year_data or {})}",
    )

    response = build_metrics_response_func(
        order=order,
        items=items,
        summary=summary,
        temporal_mode=temporal_mode,
        geo_levels=geo_levels,
        requested_geo_levels=requested_geo_levels,
        sources_used=sources_used,
        boxes=boxes,
        year_data=year_data,
        loc_level_map=loc_level_map,
        location_features=location_features,
        all_region_codes=all_region_codes,
        metric_source_map=metric_source_map,
        aggregation_trace=aggregation_trace,
        requested_year_start=requested_year_start,
        requested_year_end=requested_year_end,
        all_years=all_years,
        temporal_granularity=temporal_granularity,
        temporal_use_timestamps=temporal_use_timestamps,
        metric_key=metric_key,
        all_metrics=all_metrics,
        metric_year_ranges=metric_year_ranges,
        trace_id=trace_id,
        t_execute_start=t_execute_start,
        cap_info=cap_info,
    )

    if isinstance(response, dict) and "data_type" not in response:
        response["data_type"] = order_data_type
    return response
