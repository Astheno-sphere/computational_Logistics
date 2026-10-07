"""
Shared runtime implementation for confirmed order execution.

This module holds the real executor wiring while `mapmover.order_executor`
remains as the stable public import surface.
"""

import logging
import pandas as pd
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mapmover")

from .geography_reference import (
    canonicalize_loc_id,
    resolve_country_subdivision_slug_loc_id,
    translate_geometry_id_to_local_id,
    translate_loc_id_to_geometry_id,
)
from ..geometry_handlers import (
    load_country_parquet,
    load_geometry_rows_by_loc_ids,
    load_subcounty_geometry,
    df_to_geojson,
)

from ..paths import DATA_ROOT
from ..data_loading import load_source_metadata
from ..source_time_contract import available_years_for_range, metadata_metric_year_range
from ..aggregation_system import build_aggregation_spec, apply_temporal_aggregation
from ..foundation_helpers import load_runtime_result_cap_helpers
from ..foundation_helpers import load_global_country_display_frame
from ..duckdb_helpers import (
    can_query_event_source,
    count_rows,
    is_cloud_mode,
    parquet_columns,
    path_to_uri,
    quote_ident,
    run_df,
    select_columns_from_parquet,
    select_event_ids_by_regions,
    select_peak_positions_by_storm_ids,
    select_rows,
)
from ..execution.event_loading import (
    load_event_data as load_event_data_impl,
    load_event_data_duckdb as load_event_data_duckdb_impl,
    resolve_event_parquet_path_for_source,
    resolve_event_source_id as resolve_event_source_id_impl,
)
from ..execution.source_loading import (
    candidate_parquet_paths as candidate_parquet_paths_impl,
    get_source_path as get_source_path_impl,
    load_source_data as load_source_data_impl,
)
from ..execution.special_order_capabilities import (
    route_default_special_order,
)
from ..execution.event_execution import (
    execute_event_order_impl,
    get_coordinate_columns as get_coordinate_columns_impl,
    get_id_column as get_id_column_impl,
    get_time_column as get_time_column_impl,
)
from ..execution.aggregate_loading import (
    aggregate_metric_frame as aggregate_metric_frame_impl,
    derive_event_metric_aggregate_data as derive_event_metric_aggregate_data_impl,
    infer_implicit_aggregate_rollup_level as infer_implicit_aggregate_rollup_level_impl,
    load_disaster_aggregate_data_impl,
)
from ..execution.geometry_execution import (
    execute_geometry_order_impl,
    execute_geometry_overlay_impl,
)
from ..execution.order_execution_runtime import (
    execute_order_impl,
)
from ..execution.multi_order_execution import (
    classify_execution_family_impl,
    execute_mixed_order_if_needed_impl,
    execute_multi_layer_order_if_needed_impl,
    execute_split_order_impl,
)
from ..execution.removal_execution import (
    execute_removal_order_impl,
)
from ..execution.region_selection import (
    find_source_files as find_source_files_impl,
    get_event_ids_by_region as get_event_ids_by_region_impl,
    get_loc_ids_by_region as get_loc_ids_by_region_impl,
    get_source_from_catalog as get_source_from_catalog_impl,
)
from ..execution.geometry_loading import (
    find_geometry_source_for_level as find_geometry_source_for_level_impl,
    has_geometry_data_type as has_geometry_data_type_impl,
    load_geometry_from_source as load_geometry_from_source_impl,
)
from ..execution.fx_loading import (
    load_fx_with_aggregation as load_fx_with_aggregation_impl,
)
from .query_intent_primitives import (
    query_prefers_event_retry as query_prefers_event_retry_impl,
)
from .order_semantics import (
    resolve_pack_source as resolve_pack_source_impl,
    scope_matches_region as scope_matches_region_impl,
)
from .order_routing import (
    normalize_order_items as normalize_order_items_impl,
    resolve_source_for_item as resolve_source_for_item_impl,
)
from .aggregate_primitives import (
    resolve_aggregate_admin2_dir as resolve_aggregate_admin2_dir_impl,
    source_has_aggregate_files as source_has_aggregate_files_impl,
    source_supports_disaster_aggregates as source_supports_disaster_aggregates_impl,
)
from .sparse_year_clarify import (
    check_sparse_year as check_sparse_year_impl,
)
from .derived_results import (
    apply_derived_fields as apply_derived_fields_impl,
)
from .execution_primitives import (
    build_metrics_response,
    collect_source_metadata,
    load_order_item_dataframe,
    process_metric_items,
    prepare_execution_items,
)
from .filter_primitives import (
    append_duckdb_filter_clause as append_duckdb_filter_clause_impl,
    apply_dataframe_filters as apply_dataframe_filters_impl,
    normalize_sort_spec as normalize_sort_spec_impl,
)
from .order_validation import (
    execution_requires_metric as execution_requires_metric_impl,
    validate_execution_items as validate_execution_items_impl,
)
from .execution_normalization import (
    coerce_date_year as coerce_date_year_impl,
    coerce_year as coerce_year_impl,
    extract_date_window as extract_date_window_impl,
    normalize_geo_level as normalize_geo_level_impl,
    normalize_year_filters as normalize_year_filters_impl,
)
from .source_capabilities import (
    get_source_data_type as get_source_data_type_impl,
)
from .metric_alias_registry import find_runtime_metric_column
from .geography_reference import (
    load_conversions as load_conversions_impl,
    load_iso_codes as load_iso_codes_impl,
    load_usa_admin as load_usa_admin_impl,
)
from .order_geo_runtime import (
    expand_order_region,
)
from .order_execution_support import (
    build_runtime_source_path,
    load_runtime_catalog,
    validate_runtime_execution_items,
)
from .order_executor_runtime_surface import (
    execute_geometry_order_runtime,
    execute_geometry_overlay_runtime,
    expand_runtime_region,
    load_disaster_aggregate_data_runtime,
    load_runtime_source_data,
)
from .order_execution_policy import (
    DEFAULT_EVENT_LIMIT,
    MAX_EVENT_LIMIT,
    SPECIAL_GEOMETRY_LEVELS,
    executor_log,
    executor_trace_id,
)
_country_subdivision_slug_cache = {}

def _load_catalog() -> dict:
    return load_runtime_catalog()

def _validate_execution_items(items: list) -> str | None:
    return validate_runtime_execution_items(
        items,
        get_source_from_catalog_func=lambda source_id: get_source_from_catalog_impl(source_id, load_catalog_func=_load_catalog),
        execution_requires_metric_func=execution_requires_metric_impl,
        validate_execution_items_func=validate_execution_items_impl,
    )


def _load_disaster_aggregate_data(source_id: str, item: dict) -> tuple[Optional[pd.DataFrame], Optional[dict]]:
    return load_disaster_aggregate_data_runtime(
        source_id,
        item,
        load_disaster_aggregate_data_func=load_disaster_aggregate_data_impl,
        get_source_path_func=_get_source_path,
        resolve_aggregate_admin2_dir_func=resolve_aggregate_admin2_dir_impl,
        normalize_year_filters_func=normalize_year_filters_impl,
        parquet_columns_func=parquet_columns,
        select_rows_func=select_rows,
        is_cloud_mode_func=is_cloud_mode,
        load_source_metadata_func=load_source_metadata,
        infer_implicit_aggregate_rollup_level_func=lambda item: infer_implicit_aggregate_rollup_level_impl(
            item,
            expand_region_func=expand_region,
        ),
        derive_event_metric_aggregate_data_func=lambda source_id, item, requested_metric: derive_event_metric_aggregate_data_impl(
            source_id,
            item,
            requested_metric,
            load_event_data_func=load_event_data,
        ),
        aggregate_metric_frame_func=aggregate_metric_frame_impl,
        translate_loc_id_to_geometry_id_func=translate_loc_id_to_geometry_id,
        translate_geometry_id_to_local_id_func=translate_geometry_id_to_local_id,
        path_to_uri_func=path_to_uri,
        logger=logger,
    )


def load_event_data(source_id: str, event_file_key: str = "events") -> tuple[pd.DataFrame, dict]:
    return load_event_data_impl(
        source_id,
        event_file_key,
        get_source_path_func=_get_source_path,
        load_source_metadata_func=load_source_metadata,
        is_cloud_mode_func=is_cloud_mode,
        select_rows_func=select_rows,
    )


def execute_geometry_overlay(geometry_overlay: dict, filter_loc_ids: list = None) -> dict:
    return execute_geometry_overlay_runtime(
        geometry_overlay,
        execute_geometry_overlay_func=execute_geometry_overlay_impl,
        filter_loc_ids=filter_loc_ids,
        get_source_path_func=_get_source_path,
        parquet_columns_func=parquet_columns,
        select_columns_from_parquet_func=select_columns_from_parquet,
        df_to_geojson_func=df_to_geojson,
    )


def execute_geometry_order(order: dict) -> dict:
    return execute_geometry_order_runtime(
        order,
        execute_geometry_order_func=execute_geometry_order_impl,
        execute_geometry_overlay_func=execute_geometry_overlay,
        load_source_metadata_func=load_source_metadata,
    )


def _get_source_path(source_id: str) -> Path:
    return build_runtime_source_path(
        source_id,
        get_source_path_func=get_source_path_impl,
        load_catalog_func=_load_catalog,
        data_root=DATA_ROOT,
    )


def load_source_data(
    source_id: str,
    *,
    year: int | None = None,
    loc_id_prefix: str | None = None,
    exact_filters: dict | None = None,
    in_filters: dict | None = None,
    compare_filters: list[tuple[str, str, object]] | None = None,
    columns: list[str] | None = None,
    prefer_latest_year_when_unspecified: bool = False,
    requested_limit: int | None = None,
    data_file: str | None = None,
) -> tuple:
    return load_runtime_source_data(
        source_id,
        load_source_data_func=load_source_data_impl,
        year=year,
        loc_id_prefix=loc_id_prefix,
        exact_filters=exact_filters,
        in_filters=in_filters,
        compare_filters=compare_filters,
        columns=columns,
        prefer_latest_year_when_unspecified=prefer_latest_year_when_unspecified,
        requested_limit=requested_limit,
        data_file=data_file,
        get_source_path_func=_get_source_path,
        load_source_metadata_func=load_source_metadata,
        candidate_parquet_paths_func=candidate_parquet_paths_impl,
        is_cloud_mode_func=is_cloud_mode,
        path_to_uri_func=path_to_uri,
        select_rows_func=select_rows,
        count_rows_func=count_rows,
        logger=logger,
    )


def expand_region(region: str, prefer_water_body: bool = False) -> set:
    return expand_runtime_region(
        region,
        expand_order_region_func=expand_order_region,
        resolve_country_subdivision_slug_loc_id_func=lambda region: resolve_country_subdivision_slug_loc_id(
            region,
            cache_dict=_country_subdivision_slug_cache,
        ),
        load_conversions_func=load_conversions_impl,
        load_iso_codes_func=load_iso_codes_impl,
        load_usa_admin_func=load_usa_admin_impl,
        prefer_water_body=prefer_water_body,
    )


def find_metric_column(df: pd.DataFrame, metric: str, metadata: Optional[dict] = None) -> Optional[str]:
    return find_runtime_metric_column(df, metric, metadata)

# =============================================================================
# Event Mode Execution (for disaster/event data)
# =============================================================================

def _execute_removal_order(order: dict, items: list, source_id: str) -> dict:
    from ..session_cache import session_manager

    return execute_removal_order_impl(
        order,
        items,
        source_id,
        get_source_data_type_func=lambda source_id: get_source_data_type_impl(
            source_id,
            load_catalog_func=_load_catalog,
        ),
        get_source_from_catalog_func=lambda source_id: get_source_from_catalog_impl(
            source_id,
            load_catalog_func=_load_catalog,
        ),
        expand_region_func=expand_region,
        get_loc_ids_by_region_func=lambda source_id, regions: get_loc_ids_by_region_impl(
            source_id,
            regions,
            find_source_files_func=lambda source_id: find_source_files_impl(
                source_id,
                get_source_from_catalog_func=lambda source_id: get_source_from_catalog_impl(
                    source_id,
                    load_catalog_func=_load_catalog,
                ),
                data_root=DATA_ROOT,
            ),
            select_columns_from_parquet_func=select_columns_from_parquet,
            logger=logging.getLogger(__name__),
        ),
        get_event_ids_by_region_func=lambda source_id, regions: get_event_ids_by_region_impl(
            source_id,
            regions,
            find_source_files_func=lambda source_id: find_source_files_impl(
                source_id,
                get_source_from_catalog_func=lambda source_id: get_source_from_catalog_impl(
                    source_id,
                    load_catalog_func=_load_catalog,
                ),
                data_root=DATA_ROOT,
            ),
            duckdb_can_query_events_func=can_query_event_source,
            select_event_ids_by_regions_func=select_event_ids_by_regions,
            select_columns_from_parquet_func=select_columns_from_parquet,
            logger=logging.getLogger(__name__),
        ),
        session_manager=session_manager,
        coerce_year_func=coerce_year_impl,
    )


def execute_order(order: dict) -> dict:
    return execute_order_impl(
        order,
        executor_trace_id_func=executor_trace_id,
        executor_log_func=lambda trace_id, stage, started_at, extra="": executor_log(
            trace_id,
            stage,
            started_at,
            extra,
            logger=logger,
        ),
        perf_counter_func=time.perf_counter,
        logger=logger,
        prepare_execution_items_func=lambda items: prepare_execution_items(
            items=items,
            load_catalog_func=_load_catalog,
            normalize_order_items_func=lambda items, catalog: normalize_order_items_impl(
                items,
                catalog,
                resolve_source_for_item_func=lambda item, catalog: resolve_source_for_item_impl(
                    item,
                    catalog,
                    resolve_pack_source_func=resolve_pack_source_impl,
                ),
                logger=logger,
            ),
            get_source_data_type_func=lambda source_id: get_source_data_type_impl(
                source_id,
                load_catalog_func=_load_catalog,
            ),
            source_supports_disaster_aggregates_func=lambda source_id: source_supports_disaster_aggregates_impl(
                source_id,
                get_source_from_catalog_func=lambda source_id: get_source_from_catalog_impl(
                    source_id,
                    load_catalog_func=_load_catalog,
                ),
                is_cloud_mode_func=is_cloud_mode,
                source_has_aggregate_files_func=source_has_aggregate_files_impl,
                resolve_aggregate_admin2_dir_func=resolve_aggregate_admin2_dir_impl,
                parquet_columns_func=parquet_columns,
                data_root=DATA_ROOT,
            ),
            validate_execution_items_func=_validate_execution_items,
        ),
        get_source_data_type_func=lambda source_id: get_source_data_type_impl(
            source_id,
            load_catalog_func=_load_catalog,
        ),
        route_special_order_func=lambda **kwargs: route_default_special_order(
            get_source_from_catalog_func=lambda source_id: get_source_from_catalog_impl(
                source_id,
                load_catalog_func=_load_catalog,
            ),
            execute_removal_order_func=_execute_removal_order,
            execute_mixed_order_if_needed_func=lambda order, items, source_id: execute_mixed_order_if_needed_impl(
                order,
                items,
                source_id,
                execute_split_order_func=lambda order, add_items, remove_items, source_id: execute_split_order_impl(
                    order,
                    add_items,
                    remove_items,
                    source_id,
                    execute_removal_order_func=_execute_removal_order,
                    execute_order_func=execute_order,
                    logger=logging.getLogger(__name__),
                ),
                logger=logging.getLogger(__name__),
            ),
            execute_multi_layer_order_if_needed_func=lambda order, items: execute_multi_layer_order_if_needed_impl(
                order,
                items,
                classify_execution_family_func=lambda item: classify_execution_family_impl(
                    item,
                    get_source_from_catalog_func=lambda source_id: get_source_from_catalog_impl(
                        source_id,
                        load_catalog_func=_load_catalog,
                    ),
                    special_geometry_levels=SPECIAL_GEOMETRY_LEVELS,
                    has_geometry_data_type_func=has_geometry_data_type_impl,
                ),
                execute_geometry_order_func=execute_geometry_order,
                execute_order_func=execute_order,
            ),
            execute_event_order_func=lambda order: execute_event_order_impl(
                order,
                normalize_year_filters_func=normalize_year_filters_impl,
                normalize_sort_spec_func=normalize_sort_spec_impl,
                resolve_event_source_id_func=lambda source_id: resolve_event_source_id_impl(
                    source_id,
                    load_source_metadata_func=load_source_metadata,
                    load_catalog_func=_load_catalog,
                ),
                duckdb_can_query_events_func=can_query_event_source,
                load_event_data_duckdb_func=lambda source_id, item, event_file_key="events": load_event_data_duckdb_impl(
                    source_id,
                    item,
                    event_file_key,
                    resolve_event_parquet_path_func=lambda source_id, event_file_key="events": resolve_event_parquet_path_for_source(
                        source_id,
                        event_file_key,
                        get_source_path_func=_get_source_path,
                        load_source_metadata_func=load_source_metadata,
                        is_cloud_mode_func=is_cloud_mode,
                    ),
                    parquet_columns_func=parquet_columns,
                    normalize_year_filters_func=normalize_year_filters_impl,
                    normalize_sort_spec_func=normalize_sort_spec_impl,
                    expand_region_func=expand_region,
                    load_iso_codes_func=load_iso_codes_impl,
                    load_usa_admin_func=load_usa_admin_impl,
                    append_duckdb_filter_clause_func=lambda where_clauses, params, available_cols, field, value: append_duckdb_filter_clause_impl(
                        where_clauses,
                        params,
                        available_cols,
                        field,
                        value,
                        quote_ident_func=quote_ident,
                    ),
                    path_to_uri_func=path_to_uri,
                    quote_ident_func=quote_ident,
                    run_df_func=run_df,
                    default_event_limit=DEFAULT_EVENT_LIMIT,
                    max_event_limit=MAX_EVENT_LIMIT,
                ),
                load_event_data_func=lambda source_id, event_file_key="events": load_event_data_impl(
                    source_id,
                    event_file_key,
                    get_source_path_func=_get_source_path,
                    load_source_metadata_func=load_source_metadata,
                    is_cloud_mode_func=is_cloud_mode,
                    select_rows_func=select_rows,
                ),
                get_source_from_catalog_func=lambda source_id: get_source_from_catalog_impl(
                    source_id,
                    load_catalog_func=_load_catalog,
                ),
                load_source_metadata_func=load_source_metadata,
                resolve_event_parquet_path_func=lambda source_id, event_file_key="events": resolve_event_parquet_path_for_source(
                    source_id,
                    event_file_key,
                    get_source_path_func=_get_source_path,
                    load_source_metadata_func=load_source_metadata,
                    is_cloud_mode_func=is_cloud_mode,
                ),
                select_peak_positions_by_storm_ids_func=select_peak_positions_by_storm_ids,
                get_coordinate_columns_func=get_coordinate_columns_impl,
                get_time_column_func=get_time_column_impl,
                get_id_column_func=get_id_column_impl,
                load_geometry_rows_by_loc_ids_func=load_geometry_rows_by_loc_ids,
                expand_region_func=expand_region,
                default_event_limit=DEFAULT_EVENT_LIMIT,
                max_event_limit=MAX_EVENT_LIMIT,
            ),
            **kwargs,
        ),
        collect_source_metadata_func=lambda items, trace_id: collect_source_metadata(
            items=items,
            expand_region_func=expand_region,
            load_disaster_aggregate_data_func=_load_disaster_aggregate_data,
            load_source_metadata_func=load_source_metadata,
            logger=logger,
            trace_id=trace_id,
        ),
        process_metric_items_func=lambda **kwargs: process_metric_items(
            **kwargs,
            logger=logger,
            executor_log_func=lambda trace_id, stage, started_at, extra="": executor_log(
                trace_id,
                stage,
                started_at,
                extra,
                logger=logger,
            ),
            perf_counter_func=time.perf_counter,
            normalize_year_filters_func=normalize_year_filters_impl,
            normalize_geo_level_func=normalize_geo_level_impl,
            normalize_sort_spec_func=normalize_sort_spec_impl,
            load_order_item_dataframe_func=lambda **inner_kwargs: load_order_item_dataframe(
                **inner_kwargs,
                load_disaster_aggregate_data_func=_load_disaster_aggregate_data,
                load_source_data_func=load_source_data,
                expand_region_func=expand_region,
                load_source_metadata_func=load_source_metadata,
            ),
            load_fx_with_aggregation_func=lambda source_id, item, metadata: load_fx_with_aggregation_impl(
                source_id,
                item,
                metadata,
                build_aggregation_spec_func=build_aggregation_spec,
                apply_temporal_aggregation_func=apply_temporal_aggregation,
                get_source_path_func=_get_source_path,
                select_columns_from_parquet_func=select_columns_from_parquet,
                extract_date_window_func=lambda item: extract_date_window_impl(
                    item,
                    normalize_year_filters_func=normalize_year_filters_impl,
                ),
            ),
            find_metric_column_func=find_metric_column,
            check_sparse_year_func=check_sparse_year_impl,
            expand_region_func=expand_region,
            canonicalize_loc_id_func=canonicalize_loc_id,
            translate_loc_id_to_geometry_id_func=translate_loc_id_to_geometry_id,
            translate_geometry_id_to_local_id_func=translate_geometry_id_to_local_id,
            apply_dataframe_filters_func=apply_dataframe_filters_impl,
            get_coordinate_columns_func=get_coordinate_columns_impl,
            available_years_for_range_func=available_years_for_range,
            metadata_metric_year_range_func=metadata_metric_year_range,
            apply_derived_fields_func=apply_derived_fields_impl,
            apply_runtime_result_cap_func=load_runtime_result_cap_helpers()["apply_runtime_result_cap"],
            merge_cap_info_func=load_runtime_result_cap_helpers()["merge_cap_info"],
        ),
        build_metrics_response_func=lambda **kwargs: build_metrics_response(
            **kwargs,
            logger=logger,
            executor_log_func=lambda trace_id, stage, started_at, extra="": executor_log(
                trace_id,
                stage,
                started_at,
                extra,
                logger=logger,
            ),
            perf_counter_func=time.perf_counter,
            special_geometry_levels=SPECIAL_GEOMETRY_LEVELS,
            find_geometry_source_for_level_func=lambda geo_level, scope=None: find_geometry_source_for_level_impl(
                geo_level,
                load_catalog_func=_load_catalog,
                has_geometry_data_type_func=has_geometry_data_type_impl,
                scope=scope,
            ),
            load_geometry_from_source_func=lambda source_info, filter_regions=None: load_geometry_from_source_impl(
                source_info,
                data_root=DATA_ROOT,
                select_columns_from_parquet_func=select_columns_from_parquet,
                logger=logging.getLogger(__name__),
                filter_regions=filter_regions,
            ),
            # This frame is serialized into response GeoJSON. Keep exact
            # Admin0 Full geometry confined to containment/query helpers.
            load_global_countries_func=load_global_country_display_frame,
            load_subcounty_geometry_func=load_subcounty_geometry,
            load_geometry_rows_by_loc_ids_func=load_geometry_rows_by_loc_ids,
            load_country_parquet_func=load_country_parquet,
            query_prefers_event_retry_func=query_prefers_event_retry_impl,
            scope_matches_region_func=scope_matches_region_impl,
            execute_order_func=execute_order,
            load_catalog_func=_load_catalog,
        ),
    )
