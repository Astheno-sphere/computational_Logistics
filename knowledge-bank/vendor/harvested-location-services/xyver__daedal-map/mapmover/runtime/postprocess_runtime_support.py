"""Shared assembly helpers for postprocess runtime wiring."""

from __future__ import annotations


def expand_full_pack_loads_runtime(
    items: list,
    catalog: dict,
    *,
    expand_full_pack_loads_func,
    is_full_pack_load_func,
    catalog_sources_func,
    get_catalog_pack_func,
    source_supports_events_func,
    source_has_metrics_func,
) -> list:
    return expand_full_pack_loads_func(
        items,
        catalog,
        is_full_pack_load_func=is_full_pack_load_func,
        catalog_sources_func=catalog_sources_func,
        get_catalog_pack_func=get_catalog_pack_func,
        source_supports_events_func=source_supports_events_func,
        source_has_metrics_func=source_has_metrics_func,
    )


def expand_wildcard_metrics_runtime(
    items: list,
    *,
    expand_wildcard_metrics_func,
    load_catalog_func,
    resolve_pack_source_func,
    load_source_metadata_func,
    metadata_metric_year_range_func,
) -> list:
    return expand_wildcard_metrics_func(
        items,
        load_catalog_func=load_catalog_func,
        resolve_pack_source_func=resolve_pack_source_func,
        load_source_metadata_func=load_source_metadata_func,
        metadata_metric_year_range_func=metadata_metric_year_range_func,
    )


def expand_all_derived_fields_runtime(
    items: list,
    *,
    expand_all_derived_fields_func,
    derived_expansions,
    resolve_population_dependency_func,
    get_source_admin_levels_func,
    metric_display_name_func,
    population_family: str,
) -> list:
    return expand_all_derived_fields_func(
        items,
        derived_expansions=derived_expansions,
        resolve_population_dependency_func=resolve_population_dependency_func,
        get_source_admin_levels_func=get_source_admin_levels_func,
        metric_display_name_func=metric_display_name_func,
        population_family=population_family,
    )


def detect_multiple_path_clarify_runtime(
    items: list,
    catalog: dict,
    *,
    hints: dict | None,
    detect_multiple_path_clarify_func,
    query_explicit_view_mode_func,
    get_item_source_metadata_func,
    build_multiple_paths_clarify_func,
):
    return detect_multiple_path_clarify_func(
        items,
        catalog,
        hints=hints,
        query_explicit_view_mode_func=query_explicit_view_mode_func,
        get_item_source_metadata_func=get_item_source_metadata_func,
        build_multiple_paths_clarify_func=build_multiple_paths_clarify_func,
    )


def detect_full_pack_load_clarify_runtime(
    items: list,
    catalog: dict,
    *,
    detect_full_pack_load_clarify_func,
    is_full_pack_load_func,
    get_catalog_pack_func,
    build_pack_load_clarify_func,
):
    return detect_full_pack_load_clarify_func(
        items,
        catalog,
        is_full_pack_load_func=is_full_pack_load_func,
        get_catalog_pack_func=get_catalog_pack_func,
        build_pack_load_clarify_func=build_pack_load_clarify_func,
    )


def validate_postprocess_item_runtime(
    item: dict,
    catalog: dict,
    *,
    validate_item_func,
    resolve_pack_source_func,
    get_catalog_pack_func,
    catalog_sources_func,
    get_catalog_source_func,
    normalize_item_filters_func,
    normalize_location_shape_metric_func,
    apply_disaster_semantic_filters_func,
    source_has_metrics_func,
    source_supports_aggregate_mode_func,
    apply_aggregate_query_hints_func,
    source_supports_events_func,
    query_prefers_event_source_func,
    query_requests_short_current_window_func,
    reroute_item_to_event_sibling_func,
    reroute_item_to_aggregate_sibling_func,
    resolve_pack_source_by_shape_func,
    resolve_pack_aggregate_source_func,
    load_source_metadata_func,
    expand_filter_value_aliases_func,
    source_requires_metric_func,
    get_disaster_aggregate_metric_columns_func,
    format_metric_label_func,
    resolve_pack_source_for_metric_func,
    clamp_item_years_to_metric_func,
    select_query_guided_metric_func,
) -> dict:
    def recurse_validate_item(next_item: dict, next_catalog: dict) -> dict:
        return validate_postprocess_item_runtime(
            next_item,
            next_catalog,
            validate_item_func=validate_item_func,
            resolve_pack_source_func=resolve_pack_source_func,
            get_catalog_pack_func=get_catalog_pack_func,
            catalog_sources_func=catalog_sources_func,
            get_catalog_source_func=get_catalog_source_func,
            normalize_item_filters_func=normalize_item_filters_func,
            normalize_location_shape_metric_func=normalize_location_shape_metric_func,
            apply_disaster_semantic_filters_func=apply_disaster_semantic_filters_func,
            source_has_metrics_func=source_has_metrics_func,
            source_supports_aggregate_mode_func=source_supports_aggregate_mode_func,
            apply_aggregate_query_hints_func=apply_aggregate_query_hints_func,
            source_supports_events_func=source_supports_events_func,
            query_prefers_event_source_func=query_prefers_event_source_func,
            query_requests_short_current_window_func=query_requests_short_current_window_func,
            reroute_item_to_event_sibling_func=reroute_item_to_event_sibling_func,
            reroute_item_to_aggregate_sibling_func=reroute_item_to_aggregate_sibling_func,
            resolve_pack_source_by_shape_func=resolve_pack_source_by_shape_func,
            resolve_pack_aggregate_source_func=resolve_pack_aggregate_source_func,
            load_source_metadata_func=load_source_metadata_func,
            expand_filter_value_aliases_func=expand_filter_value_aliases_func,
            source_requires_metric_func=source_requires_metric_func,
            get_disaster_aggregate_metric_columns_func=get_disaster_aggregate_metric_columns_func,
            format_metric_label_func=format_metric_label_func,
            resolve_pack_source_for_metric_func=resolve_pack_source_for_metric_func,
            clamp_item_years_to_metric_func=clamp_item_years_to_metric_func,
            select_query_guided_metric_func=select_query_guided_metric_func,
        )

    return validate_item_func(
        item,
        catalog,
        validate_item_func=recurse_validate_item,
        resolve_pack_source_func=resolve_pack_source_func,
        get_catalog_pack_func=get_catalog_pack_func,
        catalog_sources_func=catalog_sources_func,
        get_catalog_source_func=get_catalog_source_func,
        normalize_item_filters_func=normalize_item_filters_func,
        normalize_location_shape_metric_func=normalize_location_shape_metric_func,
        apply_disaster_semantic_filters_func=apply_disaster_semantic_filters_func,
        source_has_metrics_func=source_has_metrics_func,
        source_supports_aggregate_mode_func=source_supports_aggregate_mode_func,
        apply_aggregate_query_hints_func=apply_aggregate_query_hints_func,
        source_supports_events_func=source_supports_events_func,
        query_prefers_event_source_func=query_prefers_event_source_func,
        query_requests_short_current_window_func=query_requests_short_current_window_func,
        reroute_item_to_event_sibling_func=reroute_item_to_event_sibling_func,
        reroute_item_to_aggregate_sibling_func=reroute_item_to_aggregate_sibling_func,
        resolve_pack_source_by_shape_func=resolve_pack_source_by_shape_func,
        resolve_pack_aggregate_source_func=resolve_pack_aggregate_source_func,
        load_source_metadata_func=load_source_metadata_func,
        expand_filter_value_aliases_func=expand_filter_value_aliases_func,
        source_requires_metric_func=source_requires_metric_func,
        get_disaster_aggregate_metric_columns_func=get_disaster_aggregate_metric_columns_func,
        format_metric_label_func=format_metric_label_func,
        resolve_pack_source_for_metric_func=resolve_pack_source_for_metric_func,
        clamp_item_years_to_metric_func=clamp_item_years_to_metric_func,
        select_query_guided_metric_func=select_query_guided_metric_func,
    )
