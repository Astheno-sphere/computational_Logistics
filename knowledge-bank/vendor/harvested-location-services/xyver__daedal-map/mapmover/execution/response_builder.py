"""Response-building helpers extracted from the main executor."""

from __future__ import annotations

import json

import pandas as pd

from mapmover.runtime.result_cap import apply_cap_info_to_payload
from mapmover.runtime.retry_primitives import execute_event_retry_fallback
from mapmover.data_loading import source_data_version


def _build_default_time_note(items: list) -> str | None:
    defaulted_ranges = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        defaulted = item.get("_defaulted_time_range")
        if isinstance(defaulted, dict):
            defaulted_ranges.append(defaulted)

    if not defaulted_ranges:
        return None

    first = defaulted_ranges[0]
    same_ranges = all(
        entry.get("year_start") == first.get("year_start")
        and entry.get("year_end") == first.get("year_end")
        and entry.get("available_start") == first.get("available_start")
        and entry.get("available_end") == first.get("available_end")
        for entry in defaulted_ranges[1:]
    )

    if same_ranges:
        shown = f"{first.get('year_start')}-{first.get('year_end')}"
        available_start = first.get("available_start")
        available_end = first.get("available_end")
        if available_start and available_end:
            return f"Showing {shown} by default; data available for {available_start}-{available_end} if you want more history."
        return f"Showing {shown} by default because no time range was specified."

    return "Showing default 10-year windows for items without a time range. Ask for a broader period if you want more history."


def _source_info_entry(source_id: str, metadata: dict) -> dict:
    """Build one confirmed-order 'sources' entry, stamping data_version
    (Task L5 activation) from the metadata already loaded for this source."""
    entry = {
        "id": source_id,
        "name": metadata.get("source_name", source_id),
        "url": metadata.get("source_url", ""),
        "category": metadata.get("category", "general"),
    }
    version = source_data_version(metadata)
    if version:
        entry["data_version"] = version
    return entry


def build_metrics_response(
    *,
    order: dict,
    items: list,
    summary: str,
    temporal_mode: bool,
    geo_levels: set,
    requested_geo_levels: set,
    sources_used: dict,
    boxes,
    year_data,
    loc_level_map: dict,
    location_features: list,
    all_region_codes: set,
    metric_source_map: dict,
    aggregation_trace: list,
    requested_year_start,
    requested_year_end,
    all_years: set,
    temporal_granularity: str,
    temporal_use_timestamps: bool,
    metric_key,
    all_metrics: list,
    metric_year_ranges: dict,
    trace_id: str,
    t_execute_start: float,
    logger,
    executor_log_func,
    perf_counter_func,
    special_geometry_levels,
    find_geometry_source_for_level_func,
    load_geometry_from_source_func,
    load_global_countries_func,
    load_subcounty_geometry_func,
    load_geometry_rows_by_loc_ids_func,
    load_country_parquet_func,
    query_prefers_event_retry_func,
    scope_matches_region_func,
    execute_order_func,
    load_catalog_func,
    cap_info=None,
):
    """Build the final non-event executor response."""
    admin_numbered = sorted(
        [level for level in geo_levels if isinstance(level, str) and level.startswith("admin_") and level[6:].isdigit()],
        key=lambda level: int(level[6:]),
    )
    is_multi_level = any(
        isinstance(metadata.get("geographic_level"), list)
        for metadata in sources_used.values()
    )
    requested_admin_numbered = sorted(
        [level for level in requested_geo_levels if isinstance(level, str) and level.startswith("admin_") and level[6:].isdigit()],
        key=lambda level: int(level[6:]),
    )
    if requested_admin_numbered:
        primary_level = requested_admin_numbered[0]
    elif admin_numbered:
        primary_level = admin_numbered[0]
    elif "country" in geo_levels:
        primary_level = "country"
    else:
        primary_level = list(geo_levels)[0] if geo_levels else "country"
    uses_global_country_geometry = primary_level in {"country", "admin_0"}
    primary_admin_num = None
    if isinstance(primary_level, str) and primary_level.startswith("admin_") and primary_level[6:].isdigit():
        primary_admin_num = int(primary_level[6:])

    if is_multi_level and boxes:
        boxes = {
            loc_id: box for loc_id, box in boxes.items()
            if box.get("_geo_level") == primary_level or "_geo_level" not in box
        }
    if is_multi_level and year_data:
        filtered_year_data = {}
        for year, loc_map in year_data.items():
            kept_loc_map = {
                loc_id: metrics
                for loc_id, metrics in loc_map.items()
                if loc_level_map.get(loc_id) == primary_level
            }
            if kept_loc_map:
                filtered_year_data[year] = kept_loc_map
        year_data = filtered_year_data

    loc_ids_to_check = set(boxes.keys()) if boxes else set()
    if year_data:
        for year_locs in year_data.values():
            loc_ids_to_check = loc_ids_to_check | set(year_locs.keys())

    if location_features and not loc_ids_to_check and not year_data:
        source_info = [
            _source_info_entry(source_id, metadata)
            for source_id, metadata in sources_used.items()
        ]
        primary_source = list(sources_used.keys())[0] if sources_used else None
        response = {
            "type": "data",
            "data_type": "geometry",
            "geographic_level": "points",
            "available_geo_levels": ["points"],
            "source_id": primary_source,
            "geojson": {
                "type": "FeatureCollection",
                "features": location_features,
            },
            "summary": summary or f"Showing {len(location_features)} locations",
            "count": len(location_features),
            "sources": source_info,
            "metric_sources": metric_source_map,
            "aggregation_trace": aggregation_trace,
        }
        response = apply_cap_info_to_payload(response, cap_info)
        executor_log_func(trace_id, "complete", t_execute_start, f"features={len(location_features)} source={primary_source} response_type={response.get('type')}")
        return response

    geometry_df = None

    if primary_level == "marine_zone":
        # Marine overlay sources (EEZ-*, X* water bodies) load from the marine
        # geometry banks via the shared resolver, not the country/admin grouping
        # (their loc_ids do not split into ISO3 country codes).
        from ..runtime.marine_geometry import load_marine_geometry
        marine_geom = load_marine_geometry(list(loc_ids_to_check))
        if marine_geom is not None and not marine_geom.empty:
            keep_cols = [col for col in ["loc_id", "name", "geometry"] if col in marine_geom.columns]
            geometry_df = marine_geom[keep_cols]

    elif primary_level in special_geometry_levels:
        geometry_source = find_geometry_source_for_level_func(primary_level)
        if geometry_source:
            geometry_df = load_geometry_from_source_func(geometry_source, filter_regions=all_region_codes if all_region_codes else None)
        else:
            print(f"Warning: No geometry source found for special level: {primary_level}")

    elif uses_global_country_geometry:
        geometry_df = load_global_countries_func()
        logger.info(f"[DEBUG] load_global_countries returned: {len(geometry_df) if geometry_df is not None else None} rows")
        logger.info(f"[DEBUG] all_region_codes sample: {list(all_region_codes)[:5]}, year_data years: {list(year_data.keys())[:3] if year_data else []}")
        if all_region_codes and geometry_df is not None and "loc_id" in geometry_df.columns:
            geometry_df = geometry_df[geometry_df["loc_id"].isin(all_region_codes)]
            logger.info(f"[DEBUG] After region filter: {len(geometry_df)} rows")
    elif primary_admin_num is not None and primary_admin_num >= 3:
        geometry_rows = []
        loc_ids_by_state: dict[tuple[str, str], list[str]] = {}

        for loc_id in loc_ids_to_check:
            parts = loc_id.split("-")
            if len(parts) < 2:
                continue
            iso3 = parts[0]
            state_abbrev = parts[1]
            loc_ids_by_state.setdefault((iso3, state_abbrev), []).append(loc_id)

        for (iso3, state_abbrev), state_loc_ids in loc_ids_by_state.items():
            state_geom = load_subcounty_geometry_func(iso3, admin_level=primary_admin_num, state_abbrev=state_abbrev)
            if state_geom is None or state_geom.empty:
                continue

            filtered_geom = state_geom[state_geom["loc_id"].isin(state_loc_ids)]
            if filtered_geom is None or filtered_geom.empty:
                continue

            keep_cols = [col for col in ["loc_id", "name", "geometry"] if col in filtered_geom.columns]
            geometry_rows.append(filtered_geom[keep_cols])

        geometry_df = pd.concat(geometry_rows, ignore_index=True) if geometry_rows else None

    else:
        iso3_codes = set()
        for loc_id in loc_ids_to_check:
            iso3 = loc_id.split("-")[0] if "-" in loc_id else loc_id
            iso3_codes.add(iso3)

        geometry_rows = []
        for iso3 in iso3_codes:
            country_loc_ids = sorted(
                loc_id for loc_id in loc_ids_to_check
                if (loc_id.split("-")[0] if "-" in loc_id else loc_id) == iso3
            )
            if not country_loc_ids:
                continue

            country_geom = load_geometry_rows_by_loc_ids_func(iso3, country_loc_ids)
            if country_geom is None or country_geom.empty:
                country_geom = load_country_parquet_func(iso3, admin_level=primary_admin_num)
                if country_geom is not None and not country_geom.empty:
                    country_geom = country_geom[country_geom["loc_id"].isin(country_loc_ids)]

            if country_geom is not None and not country_geom.empty:
                keep_cols = [col for col in ["loc_id", "name", "geometry"] if col in country_geom.columns]
                geometry_rows.append(country_geom[keep_cols])

        geometry_df = pd.concat(geometry_rows, ignore_index=True) if geometry_rows else None

    if is_multi_level and geometry_df is not None and loc_ids_to_check:
        relevant_loc_ids = set(loc_ids_to_check)
        geometry_df = geometry_df[geometry_df["loc_id"].isin(relevant_loc_ids)]

    if geometry_df is not None and not geometry_df.empty and "loc_id" in geometry_df.columns:
        geometry_df = geometry_df.drop_duplicates(subset=["loc_id"], keep="first")

    executor_log_func(trace_id, "geometry_loaded", t_execute_start, f"level={primary_level} geometry_rows={len(geometry_df) if geometry_df is not None else 0}")

    features = []
    if geometry_df is not None and not geometry_df.empty and "loc_id" in geometry_df.columns:
        t_geom_lookup = perf_counter_func()
        geom_lookup = geometry_df.set_index("loc_id")[["name", "geometry"]].to_dict("index")
        t_after_geom_lookup = executor_log_func(trace_id, "geometry_lookup_built", t_geom_lookup, f"entries={len(geom_lookup)}")

        if temporal_mode:
            for loc_id in geom_lookup.keys():
                geom_data = geom_lookup.get(loc_id)
                if not geom_data:
                    continue

                geom_str = geom_data.get("geometry")
                if pd.isna(geom_str) or not geom_str:
                    continue

                try:
                    geom = json.loads(geom_str) if isinstance(geom_str, str) else geom_str
                except (json.JSONDecodeError, TypeError):
                    continue

                properties = {"loc_id": loc_id, "name": geom_data.get("name", loc_id)}
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": properties,
                })
        else:
            for loc_id in geom_lookup.keys():
                geom_data = geom_lookup.get(loc_id)
                if not geom_data:
                    continue

                geom_str = geom_data.get("geometry")
                if pd.isna(geom_str) or not geom_str:
                    continue

                try:
                    geom = json.loads(geom_str) if isinstance(geom_str, str) else geom_str
                except (json.JSONDecodeError, TypeError):
                    continue

                properties = {"loc_id": loc_id, "name": geom_data.get("name", loc_id)}
                if boxes and loc_id in boxes:
                    properties.update(boxes[loc_id])

                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": properties,
                })
        executor_log_func(trace_id, "features_built", t_after_geom_lookup, f"features={len(features)} temporal={temporal_mode}")
    else:
        executor_log_func(trace_id, "geometry_lookup_skipped", t_execute_start, "no_geometry_rows")

    source_info = [
        _source_info_entry(source_id, metadata)
        for source_id, metadata in sources_used.items()
    ]
    primary_source = list(sources_used.keys())[0] if sources_used else None
    response_data_type = "geometry" if primary_level in special_geometry_levels else "metrics"
    # ``year_data`` is keyed by time bucket, not geography.  Reporting its
    # length made a 2015-2025 FEMA timeline appear in chat as "Loaded 11
    # locations" even though it contained county features.  The response
    # count is always the number of rendered geographic features; time bounds
    # remain available separately in the temporal payload below.
    data_feature_count = len(features)

    response = {
        "type": "data",
        "data_type": response_data_type,
        "geographic_level": primary_level,
        "available_geo_levels": admin_numbered if admin_numbered else sorted([str(level) for level in geo_levels if level]),
        "source_id": primary_source,
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
        "summary": summary or f"Showing {len(features)} locations",
        "count": data_feature_count,
        "sources": source_info,
        "metric_sources": metric_source_map,
        "aggregation_trace": aggregation_trace,
    }
    # A narrowed/latest-time metric response may not build a time slider, but
    # it is still a choropleth. Preserve its selected metric and available
    # fields so the browser can color it instead of falling back to base
    # geography.
    if response_data_type == "metrics":
        response["metric_key"] = metric_key
        response["available_metrics"] = all_metrics
        response["metric_time_ranges"] = metric_year_ranges
        response["metric_year_ranges"] = metric_year_ranges
    response = apply_cap_info_to_payload(response, cap_info)

    default_time_note = _build_default_time_note(items)
    if default_time_note:
        response["data_note"] = default_time_note

    if response["count"] == 0:
        retry_result = execute_event_retry_fallback(
            order,
            items,
            query_prefers_event_retry_func=query_prefers_event_retry_func,
            scope_matches_region_func=scope_matches_region_func,
            execute_order_func=execute_order_func,
            load_catalog_func=load_catalog_func,
        )
        if retry_result:
            return retry_result

    if temporal_mode and year_data:
        sorted_years = sorted(all_years)
        actual_min = sorted_years[0] if sorted_years else 0
        actual_max = sorted_years[-1] if sorted_years else 0
        is_bucketed_yearly = not bool(temporal_use_timestamps) and (temporal_granularity or "yearly") == "yearly"

        canonical_time_range = {
            "min": actual_min,
            "max": actual_max,
            "available": sorted_years,
            "granularity": temporal_granularity or "yearly",
            "useTimestamps": bool(temporal_use_timestamps),
        }

        # TEMPORARY MIRROR: keep legacy year_* fields only while frontend and
        # auxiliary tools are still finishing the time_* migration.
        response["time_data"] = year_data
        response["time_range"] = canonical_time_range
        response["multi_year"] = True
        response["year_data"] = year_data
        response["year_range"] = {
            "min": actual_min,
            "max": actual_max,
            "available_years": sorted_years,
        }
        response["metric_key"] = metric_key
        response["available_metrics"] = all_metrics
        response["metric_time_ranges"] = metric_year_ranges
        response["metric_year_ranges"] = metric_year_ranges

        data_notes = []
        if requested_year_start and requested_year_end:
            if is_bucketed_yearly:
                if actual_min != requested_year_start or actual_max != requested_year_end:
                    data_notes.append(f"Note: Data available for {actual_min}-{actual_max} (requested {requested_year_start}-{requested_year_end})")
                expected_years = set(range(actual_min, actual_max + 1))
                missing_years = expected_years - all_years
                if missing_years:
                    data_notes.append(f"Some years have no data: {sorted(missing_years)[:5]}{'...' if len(missing_years) > 5 else ''}")
        if data_notes:
            prior_note = response.get("data_note")
            joined_note = " | ".join(data_notes)
            response["data_note"] = f"{prior_note} | {joined_note}" if prior_note else joined_note

    executor_log_func(trace_id, "complete", t_execute_start, f"features={len(features)} source={primary_source} response_type={response.get('type')}")
    return response
