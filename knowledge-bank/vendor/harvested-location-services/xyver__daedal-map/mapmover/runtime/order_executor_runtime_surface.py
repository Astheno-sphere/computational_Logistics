"""Shared runtime surface helpers used by order execution wiring."""

from __future__ import annotations


def load_disaster_aggregate_data_runtime(
    source_id: str,
    item: dict,
    *,
    load_disaster_aggregate_data_func,
    get_source_path_func,
    resolve_aggregate_admin2_dir_func,
    normalize_year_filters_func,
    parquet_columns_func,
    select_rows_func,
    is_cloud_mode_func,
    load_source_metadata_func,
    infer_implicit_aggregate_rollup_level_func,
    derive_event_metric_aggregate_data_func,
    aggregate_metric_frame_func,
    translate_loc_id_to_geometry_id_func,
    translate_geometry_id_to_local_id_func,
    path_to_uri_func,
    logger,
):
    return load_disaster_aggregate_data_func(
        source_id,
        item,
        get_source_path_func=get_source_path_func,
        resolve_aggregate_admin2_dir_func=resolve_aggregate_admin2_dir_func,
        normalize_year_filters_func=normalize_year_filters_func,
        parquet_columns_func=parquet_columns_func,
        select_rows_func=select_rows_func,
        is_cloud_mode_func=is_cloud_mode_func,
        load_source_metadata_func=load_source_metadata_func,
        infer_implicit_aggregate_rollup_level_func=infer_implicit_aggregate_rollup_level_func,
        derive_event_metric_aggregate_data_func=derive_event_metric_aggregate_data_func,
        aggregate_metric_frame_func=aggregate_metric_frame_func,
        translate_loc_id_to_geometry_id_func=translate_loc_id_to_geometry_id_func,
        translate_geometry_id_to_local_id_func=translate_geometry_id_to_local_id_func,
        path_to_uri_func=path_to_uri_func,
        logger=logger,
    )


def execute_geometry_overlay_runtime(
    geometry_overlay: dict,
    *,
    execute_geometry_overlay_func,
    filter_loc_ids=None,
    get_source_path_func,
    parquet_columns_func,
    select_columns_from_parquet_func,
    df_to_geojson_func,
):
    return execute_geometry_overlay_func(
        geometry_overlay,
        filter_loc_ids=filter_loc_ids,
        get_source_path_func=get_source_path_func,
        parquet_columns_func=parquet_columns_func,
        select_columns_from_parquet_func=select_columns_from_parquet_func,
        df_to_geojson_func=df_to_geojson_func,
    )


def execute_geometry_order_runtime(
    order: dict,
    *,
    execute_geometry_order_func,
    execute_geometry_overlay_func,
    load_source_metadata_func,
):
    return execute_geometry_order_func(
        order,
        execute_geometry_overlay_func=execute_geometry_overlay_func,
        load_source_metadata_func=load_source_metadata_func,
    )


def load_runtime_source_data(
    source_id: str,
    *,
    load_source_data_func,
    year=None,
    loc_id_prefix=None,
    exact_filters=None,
    in_filters=None,
    compare_filters=None,
    columns=None,
    prefer_latest_year_when_unspecified=False,
    requested_limit=None,
    data_file=None,
    get_source_path_func,
    load_source_metadata_func,
    candidate_parquet_paths_func,
    is_cloud_mode_func,
    path_to_uri_func,
    select_rows_func,
    count_rows_func,
    logger,
):
    return load_source_data_func(
        source_id,
        year=year,
        loc_id_prefix=loc_id_prefix,
        exact_filters=exact_filters,
        in_filters=in_filters,
        compare_filters=compare_filters,
        columns=columns,
        prefer_latest_year_when_unspecified=prefer_latest_year_when_unspecified,
        requested_limit=requested_limit,
        data_file=data_file,
        get_source_path_func=get_source_path_func,
        load_source_metadata_func=load_source_metadata_func,
        candidate_parquet_paths_func=candidate_parquet_paths_func,
        is_cloud_mode_func=is_cloud_mode_func,
        path_to_uri_func=path_to_uri_func,
        select_rows_func=select_rows_func,
        count_rows_func=count_rows_func,
        logger=logger,
    )


def expand_runtime_region(
    region: str,
    *,
    expand_order_region_func,
    resolve_country_subdivision_slug_loc_id_func,
    load_conversions_func,
    load_iso_codes_func,
    load_usa_admin_func,
    prefer_water_body: bool = False,
):
    return expand_order_region_func(
        region,
        resolve_country_subdivision_slug_loc_id_func=resolve_country_subdivision_slug_loc_id_func,
        load_conversions_func=load_conversions_func,
        load_iso_codes_func=load_iso_codes_func,
        load_usa_admin_func=load_usa_admin_func,
        prefer_water_body=prefer_water_body,
    )
