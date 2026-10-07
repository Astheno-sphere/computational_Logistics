"""Per-item metric processing helpers extracted from the main executor."""

from __future__ import annotations

import pandas as pd

from mapmover.runtime.source_hints import (
    derive_source_geo_level_from_loc_id,
    resolve_geo_contract,
    source_geometry_kind,
    source_geometry_subkind,
)
from mapmover.source_time_contract import coerce_temporal_key, resolve_temporal_axis

USA_STATE_ABBREVIATIONS = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}

USA_STATE_ABBREVIATION_VALUES = {value.lower(): value for value in USA_STATE_ABBREVIATIONS.values()}


def _temporal_years_for_filter(df: pd.DataFrame, temporal_field: str, temporal_granularity: str | None) -> pd.Series:
    series = df[temporal_field]
    if temporal_field == "timestamp" and pd.api.types.is_numeric_dtype(series):
        # Runtime timestamp columns can arrive as Unix seconds or milliseconds
        # depending on the execution path. Infer the unit from magnitude so
        # year filtering survives temporal aggregation.
        numeric_series = pd.to_numeric(series, errors="coerce")
        non_null = numeric_series.dropna()
        if not non_null.empty:
            sample = float(non_null.abs().max())
            if sample >= 1e17:
                unit = "ns"
            elif sample >= 1e14:
                unit = "us"
            elif sample >= 1e11:
                unit = "ms"
            else:
                unit = "s"
            return pd.to_datetime(numeric_series, errors="coerce", utc=True, unit=unit).dt.year
    return pd.to_datetime(series, errors="coerce", utc=True).dt.year


def _normalize_runtime_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is not None:
            value = value.tz_convert("UTC")
        return value.isoformat()
    return value


def _build_geom_loc_series(df: pd.DataFrame, canonicalize_loc_id_func, translate_loc_id_to_geometry_id_func):
    if "loc_id" not in df.columns or df.empty:
        return pd.Series(dtype="object")
    canonical_series = df["loc_id"].map(canonicalize_loc_id_func)
    unique_loc_ids = [value for value in pd.unique(canonical_series.dropna()) if value]
    geom_loc_map = {
        loc_id: translate_loc_id_to_geometry_id_func(loc_id)
        for loc_id in unique_loc_ids
    }
    return canonical_series.map(geom_loc_map)


def _source_max_admin_level(metadata: dict | None) -> int | None:
    if not isinstance(metadata, dict):
        return None
    coverage = metadata.get("geographic_coverage") if isinstance(metadata.get("geographic_coverage"), dict) else {}
    levels = coverage.get("admin_levels") if isinstance(coverage.get("admin_levels"), list) else []
    candidates = []
    for level in levels:
        try:
            candidates.append(int(level))
        except (TypeError, ValueError):
            pass
    geographic_level = metadata.get("geographic_level")
    values = geographic_level if isinstance(geographic_level, list) else [geographic_level]
    for value in values:
        text = str(value or "").strip().lower()
        if text.startswith("admin_") and text[6:].isdigit():
            candidates.append(int(text[6:]))
    return max(candidates) if candidates else None


def _source_country(metadata: dict | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    coverage = metadata.get("geographic_coverage") if isinstance(metadata.get("geographic_coverage"), dict) else {}
    return str(coverage.get("country") or metadata.get("country") or "").strip().upper()


def _resolve_usa_state_prefix(region: str | None) -> str:
    if not region:
        return ""
    region_text = str(region or "").strip().lower().replace("_", " ").replace("-", " ")
    for suffix in (" state", " usa", " us"):
        if region_text.endswith(suffix):
            region_text = region_text[: -len(suffix)].strip()
    abbrev = USA_STATE_ABBREVIATIONS.get(region_text) or USA_STATE_ABBREVIATION_VALUES.get(region_text)
    if abbrev:
        return f"USA-{abbrev}"
    return ""


def _build_temporal_key_series(df: pd.DataFrame, temporal_field: str | None, temporal_granularity: str | None):
    if df.empty:
        return pd.Series(dtype="float64")
    source_series = df[temporal_field] if temporal_field and temporal_field in df.columns else df.get("year")
    if source_series is None:
        return pd.Series(dtype="float64")
    unique_values = pd.unique(source_series)
    temporal_map = {
        value: coerce_temporal_key(value, temporal_granularity or "yearly")
        for value in unique_values
    }
    return source_series.map(temporal_map)


def _normalize_runtime_filters(
    filters: dict | None,
    *,
    translate_loc_id_to_geometry_id_func,
):
    if not isinstance(filters, dict) or not filters:
        return filters

    normalized = dict(filters)
    loc_id_filter = normalized.get("loc_id")

    def _expand_loc_id_values(raw_values):
        candidates = []
        for value in raw_values:
            text = str(value or "").strip()
            if not text:
                continue
            bridged = translate_loc_id_to_geometry_id_func(text)
            for candidate in (bridged, text):
                candidate_text = str(candidate or "").strip()
                if candidate_text and candidate_text not in candidates:
                    candidates.append(candidate_text)
        return candidates

    if loc_id_filter is not None:
        if isinstance(loc_id_filter, dict):
            op = str(loc_id_filter.get("op") or "").strip().lower()
            if op == "in":
                candidates = _expand_loc_id_values(loc_id_filter.get("values") or [])
                if candidates:
                    normalized["loc_id"] = {"op": "in", "values": candidates}
                else:
                    normalized.pop("loc_id", None)
            elif "value" in loc_id_filter:
                candidates = _expand_loc_id_values([loc_id_filter.get("value")])
                if not candidates:
                    normalized.pop("loc_id", None)
                elif op in {"eq", "="}:
                    if len(candidates) == 1:
                        normalized["loc_id"] = candidates[0]
                    else:
                        normalized["loc_id"] = candidates
                else:
                    updated = dict(loc_id_filter)
                    updated["value"] = candidates[0]
                    normalized["loc_id"] = updated
        else:
            raw_values = loc_id_filter if isinstance(loc_id_filter, (list, tuple, set)) else [loc_id_filter]
            candidates = _expand_loc_id_values(raw_values)
            if not candidates:
                normalized.pop("loc_id", None)
            elif len(candidates) == 1:
                normalized["loc_id"] = candidates[0]
            else:
                normalized["loc_id"] = candidates
    return normalized


def process_metric_items(
    *,
    order: dict,
    items: list,
    temporal_mode: bool,
    aggregate_item_cache: dict,
    year_data,
    boxes,
    all_years: set,
    metric_key,
    all_metrics: list,
    metric_year_ranges: dict,
    metric_source_map: dict,
    aggregation_trace: list,
    loc_level_map: dict,
    location_features: list,
    requested_year_start,
    requested_year_end,
    all_region_codes: set,
    requested_geo_levels: set,
    trace_id: str,
    logger,
    executor_log_func,
    perf_counter_func,
    normalize_year_filters_func,
    normalize_geo_level_func,
    normalize_sort_spec_func,
    load_order_item_dataframe_func,
    load_fx_with_aggregation_func,
    find_metric_column_func,
    check_sparse_year_func,
    expand_region_func,
    canonicalize_loc_id_func,
    translate_loc_id_to_geometry_id_func,
    translate_geometry_id_to_local_id_func,
    apply_dataframe_filters_func,
    get_coordinate_columns_func,
    available_years_for_range_func,
    metadata_metric_year_range_func,
    apply_derived_fields_func,
    apply_runtime_result_cap_func=None,
    merge_cap_info_func=None,
) -> dict:
    """Process all metric items and populate the executor data structures."""
    temporal_mode_active = temporal_mode
    temporal_granularity = None
    temporal_use_timestamps = False
    cap_infos = []
    for idx, item in enumerate(items, start=1):
        source_id = item.get("source_id")
        metric = item.get("metric")
        region = item.get("region")
        filters = item.get("filters") or {}
        requested_geo_level = normalize_geo_level_func(item.get("geo_level"))
        if requested_geo_level:
            requested_geo_levels.add(requested_geo_level)
        year, year_start, year_end = normalize_year_filters_func(item)
        sort_spec = normalize_sort_spec_func(item.get("sort"))

        if year_start and year_end:
            requested_year_start = year_start
            requested_year_end = year_end

        if not source_id:
            continue

        t_item_start = perf_counter_func()
        try:
            df, metadata = load_order_item_dataframe_func(
                item=item,
                temporal_mode=temporal_mode_active,
                aggregate_item_cache=aggregate_item_cache,
            )
        except Exception as exc:
            logger.error(f"Error loading {source_id}: {exc}", exc_info=True)
            continue
        t_after_load = executor_log_func(trace_id, "item_loaded", t_item_start, f"item={idx}/{len(items)} source={source_id} rows={len(df)} cols={len(df.columns)}")

        temporal_field, source_temporal_granularity, source_uses_timestamps = resolve_temporal_axis(
            metadata,
            list(df.columns),
        )
        if temporal_granularity is None and source_temporal_granularity:
            temporal_granularity = source_temporal_granularity
            temporal_use_timestamps = source_uses_timestamps

        if "geo_level" not in df.columns and "loc_id" in df.columns:
            derived_geo_levels = df["loc_id"].map(lambda value: derive_source_geo_level_from_loc_id(value, metadata))
            if derived_geo_levels.notna().any():
                df = df.copy()
                df["geo_level"] = derived_geo_levels

        if source_id in {"fx_usd_historical", "fx_usd_historical_weekly", "fx_usd_historical_monthly"}:
            fx_df, trace = load_fx_with_aggregation_func(source_id, item, metadata)
            aggregation_trace.append(trace)
            if fx_df is not None:
                df = fx_df
                effective_granularity = str(
                    ((trace.get("applied") or {}).get("requested_granularity"))
                    or (trace.get("spec") or {}).get("time_granularity")
                    or ""
                ).strip().lower()
                if effective_granularity:
                    temporal_granularity = effective_granularity
                    temporal_use_timestamps = effective_granularity in {"timestamp", "daily", "weekly", "monthly"}
                    if "timestamp" in df.columns:
                        temporal_field = "timestamp"
                    elif "date" in df.columns:
                        temporal_field = "date"
        t_after_fx = executor_log_func(trace_id, "item_aggregation_applied", t_after_load, f"item={idx}/{len(items)} source={source_id} rows={len(df)}")

        if metric:
            metric_col = find_metric_column_func(df, metric, metadata=metadata)
        else:
            metric_col = None
        executor_log_func(trace_id, "metric_resolved", t_after_fx, f"item={idx}/{len(items)} source={source_id} metric={metric_col}")

        item_label = item.get("metric_label", metric_col)
        if metric_col and item_label:
            if not metric_key:
                metric_key = item_label
            if item_label not in all_metrics:
                all_metrics.append(item_label)
            if year_start and year_end:
                metric_year_ranges[item_label] = {
                    "min": year_start,
                    "max": year_end,
                    "available_years": available_years_for_range_func(year_start, year_end),
                }
            else:
                metric_min_year, metric_max_year = metadata_metric_year_range_func(metadata, metric_col)
                if metric_min_year is not None and metric_max_year is not None:
                    metric_year_ranges[item_label] = {
                        "min": metric_min_year,
                        "max": metric_max_year,
                        "available_years": available_years_for_range_func(metric_min_year, metric_max_year),
                    }

        if (
            not temporal_mode_active
            and temporal_field
            and (
                year is None
                or temporal_use_timestamps
                or (temporal_granularity and temporal_granularity != "yearly")
            )
        ):
            temporal_mode_active = True

        if year_start and year_end and "year" in df.columns:
            df = df[(df["year"] >= year_start) & (df["year"] <= year_end)]
        elif year_start and year_end and temporal_field and temporal_field in df.columns:
            temporal_years = _temporal_years_for_filter(df, temporal_field, temporal_granularity)
            df = df[(temporal_years >= year_start) & (temporal_years <= year_end)]
        elif year and "year" in df.columns:
            df = df[df["year"] == year]
        elif year and temporal_field and temporal_field in df.columns:
            temporal_years = _temporal_years_for_filter(df, temporal_field, temporal_granularity)
            df = df[temporal_years == year]
        elif "year" in df.columns and not temporal_mode_active:
            if metric_col and metric_col in df.columns:
                years_with_data = df[df[metric_col].notna()]["year"].unique()
                if len(years_with_data) > 0:
                    selected_year = max(years_with_data)
                    sparse_clarify = check_sparse_year_func(df, metric_col, selected_year, metadata)
                    if sparse_clarify:
                        return {"early_result": sparse_clarify}
                    df = df[df["year"] == selected_year]
                else:
                    df = df[df["year"] == df["year"].max()]
            else:
                df = df[df["year"] == df["year"].max()]
        t_after_time_filter = executor_log_func(trace_id, "time_filtered", t_after_fx, f"item={idx}/{len(items)} source={source_id} rows={len(df)}")

        # Marine_zone sources (ocean_sst, ...) key on EEZ-* / X* loc_ids, so a
        # basin/sea name like "Mediterranean" must resolve to the water-body
        # code (XSM), not the land region_aliases grouping of coastal countries.
        # The order-taker emits the location as either a singular `region` or a
        # plural `regions` list; resolve both so neither phrasing is dropped.
        # See live_source_qa_checklist.md (marine region-name trap).
        _prefer_water_body = str((metadata or {}).get("geographic_level") or "").strip().lower() == "marine_zone"
        _regions_to_resolve = []
        if region:
            _regions_to_resolve.append(region)
        _plural_regions = item.get("regions")
        if isinstance(_plural_regions, (list, tuple)):
            _regions_to_resolve.extend(str(value) for value in _plural_regions if value)
        region_codes = set()
        for _region_value in _regions_to_resolve:
            resolved_codes = expand_region_func(_region_value, prefer_water_body=_prefer_water_body)
            if (
                not _prefer_water_body
                and _source_country(metadata) == "USA"
                and (_source_max_admin_level(metadata) or 0) >= 2
            ):
                usa_state_prefix = _resolve_usa_state_prefix(_region_value)
                if usa_state_prefix:
                    resolved_codes = {usa_state_prefix}
            region_codes |= resolved_codes
        if region_codes:
            all_region_codes.update(region_codes)
        if region_codes and "loc_id" in df.columns:
            loc_id_series = df["loc_id"].map(canonicalize_loc_id_func)
            normalized_region_codes = set()
            for code in region_codes:
                normalized_region_codes.add(code)
                normalized_region_codes.add(translate_loc_id_to_geometry_id_func(code))
                normalized_region_codes.add(translate_geometry_id_to_local_id_func(code))
            region_prefixes = tuple(
                str(code).strip()
                for code in normalized_region_codes
                if isinstance(code, str) and str(code).strip()
            )
            if region_prefixes:
                mask = loc_id_series.str.startswith(region_prefixes, na=False)
                df = df[mask]
        t_after_region_filter = executor_log_func(trace_id, "region_filtered", t_after_time_filter, f"item={idx}/{len(items)} source={source_id} rows={len(df)}")

        if requested_geo_level:
            geo_contract = resolve_geo_contract(requested_geo_level, metadata)
            if (
                geo_contract.hierarchy_relation == "exact"
                and geo_contract.source_filter_field == "geo_level"
                and geo_contract.filter_strategy == "equals"
                and "geo_level" in df.columns
                and geo_contract.source_level_value
            ):
                df = df[df["geo_level"] == geo_contract.source_level_value]

        normalized_filters = _normalize_runtime_filters(
            filters,
            translate_loc_id_to_geometry_id_func=translate_loc_id_to_geometry_id_func,
        )
        if isinstance(filters, dict) and filters and "geo_level" in filters:
            filter_contract = resolve_geo_contract(filters.get("geo_level"), metadata)
            normalized_filters = dict(normalized_filters or {})
            if (
                filter_contract.hierarchy_relation == "exact"
                and filter_contract.source_filter_field == "geo_level"
                and filter_contract.filter_strategy == "equals"
                and filter_contract.source_level_value
            ):
                normalized_filters["geo_level"] = filter_contract.source_level_value
            else:
                normalized_filters.pop("geo_level", None)

        df = apply_dataframe_filters_func(df, normalized_filters)
        t_after_filter = executor_log_func(trace_id, "field_filters_applied", t_after_region_filter, f"item={idx}/{len(items)} source={source_id} rows={len(df)}")

        if temporal_mode_active and not ((temporal_field and temporal_field in df.columns) or "year" in df.columns):
            temporal_mode_active = False

        if sort_spec and not temporal_mode_active:
            sort_col = sort_spec.get("by")
            matched_col = find_metric_column_func(df, sort_col or metric_col, metadata=metadata)
            if matched_col:
                ascending = sort_spec.get("order", "desc") == "asc"
                df = df.sort_values(matched_col, ascending=ascending, na_position="last")
                if sort_spec.get("limit"):
                    df = df.head(sort_spec["limit"])
        t_after_sort = executor_log_func(trace_id, "sort_applied", t_after_filter, f"item={idx}/{len(items)} source={source_id} rows={len(df)}")

        if apply_runtime_result_cap_func is not None and not temporal_mode_active:
            requested_limit = sort_spec.get("limit") if isinstance(sort_spec, dict) else None
            df, item_cap_info = apply_runtime_result_cap_func(
                df,
                source_metadata=metadata,
                requested_limit=requested_limit,
            )
            if item_cap_info:
                cap_infos.append(item_cap_info)
            t_after_sort = executor_log_func(
                trace_id,
                "runtime_cap_applied",
                t_after_sort,
                f"item={idx}/{len(items)} source={source_id} rows={len(df)} cap_hit={bool(item_cap_info)}",
            )
        elif temporal_mode_active and isinstance(metadata, dict):
            item_cap_info = metadata.get("_runtime_prefilter_cap_info")
            if isinstance(item_cap_info, dict) and item_cap_info.get("cap_hit"):
                cap_infos.append(item_cap_info)

        if source_geometry_kind(metadata) == "entity" and source_geometry_subkind(metadata) == "point":
            lat_col, lon_col = get_coordinate_columns_func(df)
            if lat_col and lon_col:
                for _, row in df.iterrows():
                    lat = row.get(lat_col)
                    lon = row.get(lon_col)
                    if pd.isna(lat) or pd.isna(lon):
                        continue

                    properties = {}
                    for col in df.columns:
                        if col.startswith("_"):
                            continue
                        val = row.get(col)
                        if pd.notna(val):
                            normalized_val = _normalize_runtime_value(val)
                            if normalized_val is not None:
                                properties[col] = normalized_val

                    location_features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                        "properties": properties,
                    })
            executor_log_func(trace_id, "location_features_built", t_after_sort, f"item={idx}/{len(items)} source={source_id} features={len(location_features)}")
            continue

        if not metric_col:
            continue

        label = item.get("metric_label", metric_col)
        if source_id and label not in metric_source_map:
            metric_source_map[label] = source_id

        geom_loc_series = _build_geom_loc_series(
            df,
            canonicalize_loc_id_func=canonicalize_loc_id_func,
            translate_loc_id_to_geometry_id_func=translate_loc_id_to_geometry_id_func,
        )
        value_series = df[metric_col].map(_normalize_runtime_value) if metric_col in df.columns else pd.Series(dtype="object")

        if temporal_mode_active:
            time_key_series = _build_temporal_key_series(df, temporal_field, temporal_granularity)
            row_geo_level_series = (
                df["geo_level"].map(_normalize_runtime_value)
                if "geo_level" in df.columns
                else pd.Series([requested_geo_level] * len(df), index=df.index, dtype="object")
            )
            frame = pd.DataFrame(
                {
                    "geom_loc_id": geom_loc_series,
                    "time_key": time_key_series,
                    "metric_value": value_series,
                    "geo_level_value": row_geo_level_series,
                },
                index=df.index,
            )
            frame = frame[
                frame["geom_loc_id"].notna()
                & frame["time_key"].notna()
                & frame["metric_value"].notna()
            ]
            if not frame.empty:
                frame = frame.drop_duplicates(subset=["geom_loc_id", "time_key"], keep="last")
                for row in frame.itertuples(index=False):
                    geom_loc_id = row.geom_loc_id
                    time_key = row.time_key
                    val = row.metric_value
                    row_geo_level = row.geo_level_value
                    all_years.add(time_key)
                    if row_geo_level:
                        loc_level_map[geom_loc_id] = row_geo_level
                    year_bucket = year_data.setdefault(time_key, {})
                    metric_bucket = year_bucket.setdefault(geom_loc_id, {})
                    metric_bucket[label] = val
        else:
            year_series = (
                df["year"].map(_normalize_runtime_value)
                if "year" in df.columns
                else pd.Series([None] * len(df), index=df.index, dtype="object")
            )
            temporal_value_series = (
                df[temporal_field].map(_normalize_runtime_value)
                if temporal_field and temporal_field in df.columns and temporal_field != "year"
                else pd.Series([None] * len(df), index=df.index, dtype="object")
            )
            geo_level_series = (
                df["geo_level"].map(_normalize_runtime_value)
                if "geo_level" in df.columns
                else pd.Series([requested_geo_level] * len(df), index=df.index, dtype="object")
            )
            frame = pd.DataFrame(
                {
                    "geom_loc_id": geom_loc_series,
                    "metric_value": value_series,
                    "year_value": year_series,
                    "temporal_value": temporal_value_series,
                    "geo_level_value": geo_level_series,
                },
                index=df.index,
            )
            frame = frame[
                frame["geom_loc_id"].notna()
                & frame["metric_value"].notna()
            ]
            if not frame.empty:
                frame = frame.drop_duplicates(subset=["geom_loc_id"], keep="last")
                for row in frame.itertuples(index=False):
                    geom_loc_id = row.geom_loc_id
                    val = row.metric_value
                    box = boxes.get(geom_loc_id)
                    if box is None:
                        box = {}
                        if row.year_value is not None:
                            box["year"] = row.year_value
                        if row.temporal_value is not None:
                            box[temporal_field] = row.temporal_value
                        if row.geo_level_value:
                            box["_geo_level"] = row.geo_level_value
                        boxes[geom_loc_id] = box
                    box[label] = val
        tracked_rows = len(df)
        box_count = len(year_data) if temporal_mode_active and year_data is not None else len(boxes or {})
        executor_log_func(trace_id, "item_values_applied", t_after_sort, f"item={idx}/{len(items)} source={source_id} metric={label} rows={tracked_rows} box_count={box_count}")

    derived_specs = order.get("derived_specs", [])
    if derived_specs and (boxes or year_data):
        calc_year = None
        if items:
            calc_year = items[0].get("year")
        if not calc_year and boxes:
            first_box = next(iter(boxes.values()))
            calc_year = first_box.get("year")

        derivation_state = apply_derived_fields_func(boxes, derived_specs, calc_year, year_data=year_data)
        derivation_warnings = derivation_state.get("warnings") or []
        if derivation_warnings:
            print(f"Derivation warnings: {derivation_warnings[:5]}")
        if derivation_state.get("produced_comparison_boxes"):
            temporal_mode_active = False
            year_data = {}
            all_years = set()

    merged_cap_info = None
    if cap_infos:
        if merge_cap_info_func is not None:
            merged_cap_info = merge_cap_info_func(*cap_infos)
        else:
            merged_cap_info = cap_infos[0]

    return {
        "year_data": year_data,
        "boxes": boxes,
        "temporal_mode": temporal_mode_active,
        "all_years": all_years,
        "temporal_granularity": temporal_granularity or "yearly",
        "temporal_use_timestamps": temporal_use_timestamps,
        "metric_key": metric_key,
        "all_metrics": all_metrics,
        "metric_year_ranges": metric_year_ranges,
        "metric_source_map": metric_source_map,
        "aggregation_trace": aggregation_trace,
        "loc_level_map": loc_level_map,
        "location_features": location_features,
        "requested_year_start": requested_year_start,
        "requested_year_end": requested_year_end,
        "all_region_codes": all_region_codes,
        "requested_geo_levels": requested_geo_levels,
        "cap_info": merged_cap_info,
    }
