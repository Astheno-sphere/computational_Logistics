import json
import re

import pandas as pd

from mapmover.runtime.filter_primitives import (
    partition_region_filter_codes,
    resolve_exact_id_filter_field,
)
from mapmover.data_loading import source_data_version


def _format_event_timestamp_utc(value) -> str:
    if value is None or pd.isna(value):
        return ""
    timestamp = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(timestamp):
        return ""
    return timestamp.strftime("%b %d, %Y UTC")


def _build_single_event_message(
    event_type: str,
    properties: dict,
    *,
    query_text: str = "",
) -> str | None:
    if not isinstance(properties, dict) or not properties:
        return None

    lowered_query = str(query_text or "").strip().lower()
    if not lowered_query:
        return None

    qualifier = None
    for token in (
        "least severe",
        "most severe",
        "smallest",
        "largest",
        "strongest",
        "highest",
        "lowest",
        "biggest",
        "worst",
    ):
        if token in lowered_query:
            qualifier = token
            break

    prefix = "The selected event was"
    if qualifier:
        qualifier_word = {
            "biggest": "largest",
            "largest": "largest",
            "strongest": "strongest",
            "highest": "highest",
            "worst": "worst",
            "most severe": "most severe",
            "smallest": "smallest",
            "lowest": "lowest",
            "least severe": "least severe",
        }.get(qualifier, qualifier)
        if qualifier in {"smallest", "lowest", "least severe"}:
            prefix = f"The {qualifier_word} {event_type} was"
        else:
            prefix = f"The {event_type} was"
        match = re.search(r"\b(?:in|during|for)\s+(\d{4})\b", lowered_query)
        if match:
            if qualifier in {"smallest", "lowest", "least severe"}:
                prefix = f"The {qualifier_word} {event_type} in {match.group(1)} was"
            else:
                prefix = f"The {event_type} in {match.group(1)} was"

    timestamp_text = _format_event_timestamp_utc(
        properties.get("timestamp")
        or properties.get("time")
        or properties.get("start_time")
        or properties.get("start_timestamp")
        or properties.get("date")
    )

    if event_type == "earthquake":
        magnitude = properties.get("magnitude")
        place = str(properties.get("place") or properties.get("location") or "").strip()
        detail = []
        if magnitude not in (None, "") and not pd.isna(magnitude):
            detail.append(f"M {float(magnitude):.1f}")
        if place:
            detail.append(place)
        if timestamp_text:
            detail.append(timestamp_text)
        if detail:
            return f"{prefix} {' - '.join(detail)}."

    if event_type == "hurricane":
        name = str(properties.get("name") or properties.get("storm_name") or "").strip()
        category = properties.get("category")
        detail = []
        if name:
            detail.append(name)
        if category not in (None, "") and not pd.isna(category):
            detail.append(f"Category {category}")
        if timestamp_text:
            detail.append(timestamp_text)
        if detail:
            return f"{prefix} {' - '.join(detail)}."

    if event_type == "tornado":
        rating = str(properties.get("ef_rating") or properties.get("rating") or "").strip()
        place = str(properties.get("place") or properties.get("county") or properties.get("state") or "").strip()
        detail = []
        if rating:
            detail.append(rating)
        if place:
            detail.append(place)
        if timestamp_text:
            detail.append(timestamp_text)
        if detail:
            return f"{prefix} {' - '.join(detail)}."

    if event_type == "wildfire":
        name = str(properties.get("fire_name") or properties.get("name") or properties.get("event_id") or "").strip()
        area_km2 = properties.get("area_km2")
        area_acres = properties.get("area_acres") or properties.get("burned_area_acres")
        detail = []
        if name:
            detail.append(name)
        if area_km2 not in (None, "") and not pd.isna(area_km2):
            detail.append(f"{float(area_km2):,.0f} km2")
        elif area_acres not in (None, "") and not pd.isna(area_acres):
            detail.append(f"{float(area_acres):,.0f} acres")
        if timestamp_text:
            detail.append(timestamp_text)
        if detail:
            return f"{prefix} {' - '.join(detail)}."

    if event_type == "tsunami":
        height = properties.get("max_height_m") or properties.get("wave_height_m") or properties.get("runup_m")
        place = str(properties.get("place") or properties.get("location_name") or "").strip()
        detail = []
        if height not in (None, "") and not pd.isna(height):
            detail.append(f"{float(height):.1f} m")
        if place:
            detail.append(place)
        if timestamp_text:
            detail.append(timestamp_text)
        if detail:
            return f"{prefix} {' - '.join(detail)}."

    if event_type == "volcano":
        name = str(properties.get("volcano_name") or properties.get("name") or "").strip()
        vei = properties.get("vei")
        detail = []
        if name:
            detail.append(name)
        if vei not in (None, "") and not pd.isna(vei):
            detail.append(f"VEI {vei}")
        if timestamp_text:
            detail.append(timestamp_text)
        if detail:
            return f"{prefix} {' - '.join(detail)}."

    if event_type == "flood":
        name = str(properties.get("event_name") or properties.get("name") or properties.get("event_id") or "").strip()
        severity = properties.get("severity")
        detail = []
        if name:
            detail.append(name)
        if severity not in (None, "") and not pd.isna(severity):
            detail.append(f"severity {severity}")
        if timestamp_text:
            detail.append(timestamp_text)
        if detail:
            return f"{prefix} {' - '.join(detail)}."

    name = str(
        properties.get("name")
        or properties.get("title")
        or properties.get("event_name")
        or properties.get("event_id")
        or ""
    ).strip()
    detail = [part for part in (name, timestamp_text) if part]
    if detail:
        return f"{prefix} {' - '.join(detail)}."
    return None


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


def _split_packed_loc_ids(value) -> list[str]:
    if value is None or pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    loc_ids: list[str] = []
    for part in text.split("|"):
        loc_id = str(part or "").strip()
        if loc_id and loc_id not in loc_ids:
            loc_ids.append(loc_id)
    return loc_ids


def _build_footprint_geometry_response(
    df: pd.DataFrame,
    *,
    source_id: str,
    event_type: str,
    summary: str,
    metadata: dict,
    load_geometry_rows_by_loc_ids_func,
) -> dict | None:
    if df is None or df.empty:
        return None

    loc_ids: list[str] = []
    for _, row in df.iterrows():
        for field_name in ("affected_loc_ids", "loc_ids", "affected_state_loc_ids"):
            for loc_id in _split_packed_loc_ids(row.get(field_name)):
                if loc_id not in loc_ids:
                    loc_ids.append(loc_id)
    if not loc_ids:
        return None

    geometry_frames = []
    loc_ids_by_iso3: dict[str, list[str]] = {}
    for loc_id in loc_ids:
        iso3 = str(loc_id).split("-", 1)[0].strip().upper()
        if not iso3:
            continue
        loc_ids_by_iso3.setdefault(iso3, [])
        if loc_id not in loc_ids_by_iso3[iso3]:
            loc_ids_by_iso3[iso3].append(loc_id)

    for iso3, country_loc_ids in loc_ids_by_iso3.items():
        geometry_df = load_geometry_rows_by_loc_ids_func(iso3, country_loc_ids)
        if geometry_df is None or geometry_df.empty:
            continue
        keep_cols = [col for col in ["loc_id", "name", "geometry"] if col in geometry_df.columns]
        if keep_cols:
            geometry_frames.append(geometry_df[keep_cols].copy())

    if not geometry_frames:
        return None

    geometry_df = pd.concat(geometry_frames, ignore_index=True)
    geometry_df = geometry_df.drop_duplicates(subset=["loc_id"], keep="first")

    primary_row = df.iloc[0].to_dict() if len(df) == 1 else {}
    shared_properties = {}
    for field_name in (
        "disasterNumber",
        "femaDeclarationString",
        "declarationTitle",
        "declarationType",
        "incidentType",
        "incidentId",
        "canonical_event_id",
        "suggested_event_id",
    ):
        value = primary_row.get(field_name)
        if value is None or pd.isna(value):
            continue
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, pd.Timestamp):
            value = value.isoformat()
        shared_properties[field_name] = value

    features = []
    for _, row in geometry_df.iterrows():
        geom_str = row.get("geometry")
        if pd.isna(geom_str) or not geom_str:
            continue
        try:
            geom = json.loads(geom_str) if isinstance(geom_str, str) else geom_str
        except (json.JSONDecodeError, TypeError):
            continue
        properties = {
            "loc_id": row.get("loc_id"),
            "name": row.get("name") or row.get("loc_id"),
        }
        properties.update(shared_properties)
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": properties,
        })

    if not features:
        return None

    source_info = [{
        "id": source_id,
        "name": metadata.get("source_name", source_id),
        "url": metadata.get("source_url", ""),
    }]
    data_version = source_data_version(metadata)
    if data_version:
        source_info[0]["data_version"] = data_version
    return {
        "type": "data",
        "data_type": "geometry",
        "source_id": source_id,
        "event_type": event_type,
        "geojson": {"type": "FeatureCollection", "features": features},
        "summary": summary or f"Showing {len(features)} affected areas",
        "count": len(features),
        "sources": source_info,
    }


def detect_event_type(source_id: str, *, get_source_from_catalog_func, load_source_metadata_func, resolve_event_source_id_func) -> str:
    source = get_source_from_catalog_func(source_id)
    if source.get("event_type"):
        return source.get("event_type")
    metadata = load_source_metadata_func(resolve_event_source_id_func(source_id)) or {}
    return metadata.get("event_type", "unknown")


def get_significance_column(source_id: str, *, get_source_from_catalog_func) -> str:
    source = get_source_from_catalog_func(source_id)
    return source.get("significance_column")


def get_coordinate_columns(df: pd.DataFrame) -> tuple:
    lat_candidates = ["lat", "latitude", "centroid_lat"]
    lon_candidates = ["lon", "longitude", "centroid_lon"]

    lat_col = None
    lon_col = None

    for col in lat_candidates:
        if col in df.columns:
            lat_col = col
            break

    for col in lon_candidates:
        if col in df.columns:
            lon_col = col
            break

    return lat_col, lon_col


def get_time_column(df: pd.DataFrame) -> str:
    time_candidates = ["time", "timestamp", "event_date", "date", "ignition_date"]
    for col in time_candidates:
        if col in df.columns:
            return col
    return None


def get_id_column(df: pd.DataFrame, event_type: str) -> str:
    id_candidates = ["event_id", f"{event_type}_id", "id", "storm_id", "fire_id"]
    for col in id_candidates:
        if col in df.columns:
            return col
    return None


def order_item_original_query(item: dict | None) -> str:
    if not isinstance(item, dict):
        return ""
    hints = item.get("_hints") if isinstance(item.get("_hints"), dict) else {}
    return str(hints.get("original_query") or item.get("summary") or "").strip()


def build_empty_wildfire_perimeter_response(
    order: dict,
    item: dict,
    source_id: str,
    *,
    get_source_from_catalog_func,
) -> dict | None:
    query_text = " ".join(
        part for part in (
            order_item_original_query(item),
            str(order.get("summary") or "").strip(),
        )
        if part
    ).lower()
    if "wildfire" not in query_text and "fire" not in query_text:
        return None
    if "perimeter" not in query_text:
        return None

    source_note = (
        "The published USA and Canada wildfire event sources do not reliably include perimeter polygons for every named fire."
        if source_id in {"wildfires_usa", "can_wildfires"}
        else "Perimeter coverage in this wildfire source is incomplete, and this specific fire does not have a published perimeter polygon."
    )
    message = (
        f"{source_note} I could not draw a perimeter for this request from the current published data. "
        "I can still help with the fire's event details, affected areas, or a different wildfire that has perimeter coverage."
    )
    return {
        "type": "chat",
        "data_type": "events",
        "source_id": source_id,
        "geojson": {"type": "FeatureCollection", "features": []},
        "summary": order.get("summary") or "Wildfire perimeter not available in the current published data",
        "message": message,
        "count": 0,
        "sources": [{
            "id": source_id,
            "name": get_source_from_catalog_func(source_id).get("source_name", source_id),
            "url": get_source_from_catalog_func(source_id).get("source_url", ""),
        }],
    }


def execute_event_order_impl(
    order: dict,
    *,
    normalize_year_filters_func,
    normalize_sort_spec_func,
    resolve_event_source_id_func,
    duckdb_can_query_events_func,
    load_event_data_duckdb_func,
    load_event_data_func,
    get_source_from_catalog_func,
    load_source_metadata_func,
    resolve_event_parquet_path_func,
    select_peak_positions_by_storm_ids_func,
    get_coordinate_columns_func,
    get_time_column_func,
    get_id_column_func,
    load_geometry_rows_by_loc_ids_func,
    expand_region_func,
    default_event_limit,
    max_event_limit,
) -> dict:
    items = order.get("items", [])
    summary = order.get("summary", "")

    if not items:
        return {
            "type": "error",
            "message": "No items in order",
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
        }

    item = items[0]
    source_id = item.get("source_id")
    resolved_source_id = resolve_event_source_id_func(source_id)
    event_file_key = item.get("event_file", "events")
    region = item.get("region")
    year, year_start, year_end = normalize_year_filters_func(item)
    filters = item.get("filters", {})
    requested_limit = item.get("limit")
    sort_spec = normalize_sort_spec_func(item.get("sort"))

    try:
        if duckdb_can_query_events_func(source_id):
            df, metadata = load_event_data_duckdb_func(resolved_source_id, item, event_file_key)
        else:
            df, metadata = load_event_data_func(resolved_source_id, event_file_key)
    except Exception as e:
        return {
            "type": "error",
            "message": f"Failed to load event data: {e}",
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
        }

    event_type = detect_event_type(
        source_id,
        get_source_from_catalog_func=get_source_from_catalog_func,
        load_source_metadata_func=load_source_metadata_func,
        resolve_event_source_id_func=resolve_event_source_id_func,
    )
    print(f"Event mode: {resolved_source_id} -> {event_type}, {len(df)} raw events")

    if (
        source_id == "hurricanes"
        and event_file_key in {"events", "storms"}
        and ("latitude" not in df.columns or "longitude" not in df.columns)
    ):
        positions_path, _ = resolve_event_parquet_path_func(source_id, "positions")
        peak_positions = select_peak_positions_by_storm_ids_func(positions_path, df.get("storm_id", []).tolist())
        if not peak_positions.empty:
            df = df.merge(
                peak_positions[["storm_id", "latitude", "longitude"]],
                on="storm_id",
                how="left",
                suffixes=("", "_pos"),
            )
        elif df.empty:
            # Storm-level hurricane queries may legitimately filter down to zero
            # rows before any representative track point can be attached. Keep
            # the response empty instead of turning that into a coordinate error.
            df = df.copy()
            df["latitude"] = pd.Series(dtype="float64")
            df["longitude"] = pd.Series(dtype="float64")

    time_col = get_time_column_func(df)
    id_col = get_id_column_func(df, event_type)

    if not duckdb_can_query_events_func(source_id):
        if year_start and year_end:
            if "year" in df.columns:
                df = df[(df["year"] >= year_start) & (df["year"] <= year_end)]
            elif time_col:
                df["_year"] = pd.to_datetime(df[time_col]).dt.year
                df = df[(df["_year"] >= year_start) & (df["_year"] <= year_end)]
        elif year:
            if "year" in df.columns:
                df = df[df["year"] == year]
            elif time_col:
                df["_year"] = pd.to_datetime(df[time_col]).dt.year
                df = df[df["_year"] == year]

        region_codes = expand_region_func(region)
        if region_codes and "loc_id" in df.columns:
            loc_prefixes, country_codes = partition_region_filter_codes(region_codes)

            if loc_prefixes:
                mask = df["loc_id"].str.startswith(tuple(loc_prefixes), na=False)
                df = df[mask]
            elif country_codes:
                df["_country"] = df["loc_id"].str.split("-").str[0]
                df = df[df["_country"].isin(country_codes)]

        for field, value in filters.items():
            resolved_field = resolve_exact_id_filter_field(
                field,
                df.columns,
                metadata=metadata,
                event_type=event_type,
            )
            if resolved_field.endswith("_min"):
                col = resolved_field[:-4]
                if col in df.columns:
                    df = df[df[col] >= value]
            elif resolved_field.endswith("_max"):
                col = resolved_field[:-4]
                if col in df.columns:
                    df = df[df[col] <= value]
            elif resolved_field in df.columns:
                df = df[df[resolved_field] == value]

        print(f"  After filters: {len(df)} events")

        limit = min(requested_limit or default_event_limit, max_event_limit)

        sort_col = None
        ascending = False
        if sort_spec:
            requested_sort_col = str(sort_spec.get("by") or "").strip()
            if requested_sort_col in df.columns:
                sort_col = requested_sort_col
            elif requested_sort_col in {"date", "time"} and "timestamp" in df.columns:
                sort_col = "timestamp"
            ascending = str(sort_spec.get("order", "desc")).lower() == "asc"

        if not sort_col:
            sig_col = get_significance_column(
                source_id,
                get_source_from_catalog_func=get_source_from_catalog_func,
            )
            if sig_col and sig_col in df.columns:
                sort_col = sig_col

        if sort_col and sort_col in df.columns:
            df = df.sort_values(sort_col, ascending=ascending, na_position="last")

        if len(df) > limit:
            df = df.head(limit)
            print(f"  Limited to {limit} events (sorted by {sort_col or 'order'})")
    else:
        print(f"  DuckDB filtered to {len(df)} events")

    lat_col, lon_col = get_coordinate_columns_func(df)
    if not lat_col or not lon_col:
        footprint_response = _build_footprint_geometry_response(
            df,
            source_id=source_id,
            event_type=event_type,
            summary=summary,
            metadata=metadata,
            load_geometry_rows_by_loc_ids_func=load_geometry_rows_by_loc_ids_func,
        )
        if footprint_response is not None:
            default_time_note = _build_default_time_note(items)
            if default_time_note:
                footprint_response["data_note"] = default_time_note
            return footprint_response
        return {
            "type": "error",
            "message": f"No coordinate columns found in {source_id}",
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
        }

    features = []
    for idx, row in df.iterrows():
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
                if hasattr(val, "item"):
                    val = val.item()
                if isinstance(val, pd.Timestamp):
                    val = val.isoformat()
                properties[col] = val

        if "event_id" not in properties and id_col:
            properties["event_id"] = properties.get(id_col, idx)
        elif "event_id" not in properties:
            properties["event_id"] = idx

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": properties,
        })

    time_range = {"min": None, "max": None, "granularity": "daily"}
    if time_col and len(df) > 0:
        times = pd.to_datetime(df[time_col])
        time_range["min"] = int(times.min().timestamp() * 1000)
        time_range["max"] = int(times.max().timestamp() * 1000)

    primary_item = items[0] if items else {}
    if not features and event_type == "wildfire":
        perimeter_gap = build_empty_wildfire_perimeter_response(
            order,
            primary_item,
            source_id,
            get_source_from_catalog_func=get_source_from_catalog_func,
        )
        if perimeter_gap:
            return perimeter_gap

    source_info = [{
        "id": source_id,
        "name": metadata.get("source_name", source_id),
        "url": metadata.get("source_url", ""),
    }]
    data_version = source_data_version(metadata)
    if data_version:
        source_info[0]["data_version"] = data_version

    response = {
        "type": "events",
        "data_type": "events",
        "source_id": source_id,
        "event_type": event_type,
        "geojson": {"type": "FeatureCollection", "features": features},
        "time_range": time_range,
        "summary": summary or f"Showing {len(features)} {event_type} events",
        "count": len(features),
        "sources": source_info,
    }
    if len(features) == 1:
        query_text = " ".join(
            part for part in (
                str(order.get("summary") or "").strip(),
                order_item_original_query(primary_item),
            )
            if part
        ).strip()
        message = _build_single_event_message(
            event_type,
            features[0].get("properties") or {},
            query_text=query_text,
        )
        if message:
            response["message"] = message
    default_time_note = _build_default_time_note(items)
    if default_time_note:
        response["data_note"] = default_time_note
    return response
