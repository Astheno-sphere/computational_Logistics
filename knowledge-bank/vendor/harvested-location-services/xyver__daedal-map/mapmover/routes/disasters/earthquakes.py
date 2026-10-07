"""Earthquake disaster endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import pandas as pd

from mapmover.disaster_filters import apply_location_filters, get_affected_event_ids
from mapmover.duckdb_helpers import (
    _normalize_ts_for_duckdb,
    cache_get,
    cache_set,
    duckdb_available,
    is_default_preload_range,
    make_cache_key,
    make_preload_cache_key,
    parquet_available,
    parquet_columns,
    path_to_uri,
    run_df,
    select_compatible_preload_slice,
    select_filtered_event_rows,
    select_filtered_event_rows_cached,
    select_linked_loc_ids,
    select_linked_values,
)
from mapmover.live_earthquake_usgs import fetch_live_earthquakes
from mapmover.logging_analytics import logger
from mapmover.paths import GLOBAL_DIR

from .helpers import (
    build_geojson_features,
    ensure_year_column,
    filter_by_time_range,
    msgpack_error,
    msgpack_response,
    safe_float,
    safe_int,
    safe_str,
)


router = APIRouter()


EARTHQUAKE_MAP_COLUMNS = (
    "event_id",
    "magnitude",
    "depth_km",
    "felt_radius_km",
    "damage_radius_km",
    "place",
    "timestamp",
    "year",
    "loc_id",
    "latitude",
    "longitude",
    "mainshock_id",
    "sequence_id",
)


@router.get("/api/earthquakes/live")
async def get_live_earthquakes(
    hours: int = 24,
    start_time: str = None,
    end_time: str = None,
    min_magnitude: float = 2.5,
    limit: int = 100,
    orderby: str = "time",
    min_latitude: float = None,
    max_latitude: float = None,
    min_longitude: float = None,
    max_longitude: float = None,
):
    """Fetch preliminary live earthquake events directly from USGS."""
    try:
        return fetch_live_earthquakes(
            hours=hours,
            start_time=start_time,
            end_time=end_time,
            min_magnitude=min_magnitude,
            limit=limit,
            orderby=orderby,
            min_latitude=min_latitude,
            max_latitude=max_latitude,
            min_longitude=min_longitude,
            max_longitude=max_longitude,
        )
    except ValueError as exc:
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_live_earthquake_request",
                    "message": str(exc),
                }
            },
            status_code=400,
        )
    except Exception as exc:
        logger.error(f"Error fetching live earthquakes: {exc}")
        return JSONResponse(
            {
                "error": {
                    "code": "live_earthquake_upstream_error",
                    "message": "USGS live earthquake request failed.",
                }
            },
            status_code=502,
        )


def get_earthquake_property_builders():
    """Return property builders dict for earthquake GeoJSON features."""
    return {
        "event_id": lambda r: r.get("event_id", ""),
        "magnitude": lambda r: safe_float(r, "magnitude"),
        "depth_km": lambda r: safe_float(r, "depth_km"),
        "felt_radius_km": lambda r: safe_float(r, "felt_radius_km", 0),
        "damage_radius_km": lambda r: safe_float(r, "damage_radius_km", 0),
        "place": lambda r: r.get("place", ""),
        "time": lambda r: safe_str(r, "timestamp", None),
        "timestamp": lambda r: safe_str(r, "timestamp", None),
        "year": lambda r: safe_int(r, "year"),
        "loc_id": lambda r: r.get("loc_id", ""),
        "latitude": lambda r: safe_float(r, "latitude"),
        "longitude": lambda r: safe_float(r, "longitude"),
        "mainshock_id": lambda r: r.get("mainshock_id") if r.get("mainshock_id") else None,
        "sequence_id": lambda r: r.get("sequence_id") if r.get("sequence_id") else None,
    }


def _load_earthquakes_duckdb(
    *,
    year: int = None,
    start: str = None,
    end: str = None,
    min_magnitude: float = None,
    limit: int = None,
    loc_prefix: str = None,
    affected_loc_id: str = None,
    sequence_id: str = None,
    event_id: str = None,
    mainshock_id: str = None,
    columns=None,
) -> pd.DataFrame:
    """Load filtered earthquake rows via DuckDB."""
    events_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
    if not duckdb_available() or not parquet_available(events_path):
        return pd.DataFrame()
    where = []
    params = [path_to_uri(events_path)]

    if year is not None:
        where.append('"year" = ?')
        params.append(year)
    if start is not None:
        where.append('"timestamp" >= CAST(? AS TIMESTAMP)')
        params.append(_normalize_ts_for_duckdb(start))
    if end is not None:
        where.append('"timestamp" <= CAST(? AS TIMESTAMP)')
        params.append(_normalize_ts_for_duckdb(end))
    if min_magnitude is not None:
        where.append('"magnitude" >= ?')
        params.append(min_magnitude)
    if loc_prefix is not None:
        where.append('"loc_id" LIKE ?')
        params.append(f"{loc_prefix}%")
    if sequence_id is not None:
        where.append('"sequence_id" = ?')
        params.append(sequence_id)
    if event_id is not None:
        where.append('"event_id" = ?')
        params.append(event_id)
    if mainshock_id is not None:
        where.append('"mainshock_id" = ?')
        params.append(mainshock_id)
    if affected_loc_id is not None:
        affected_ids = sorted(get_affected_event_ids("earthquakes", affected_loc_id))
        if not affected_ids:
            return pd.DataFrame()
        placeholders = ", ".join("?" for _ in affected_ids)
        where.append(f'"event_id" IN ({placeholders})')
        params.extend(affected_ids)

    available_cols = parquet_columns(events_path)
    selected = [str(column) for column in (columns or []) if str(column) in available_cols]
    select_expr = ", ".join(f'"{column}"' for column in dict.fromkeys(selected)) or "*"
    sql = f"SELECT {select_expr} FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)

    if limit is not None and limit > 0:
        sql += ' ORDER BY "magnitude" DESC NULLS LAST LIMIT ?'
        params.append(limit)

    return run_df(sql, params)


def _load_earthquake_event_row(event_id: str) -> pd.DataFrame:
    events_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
    if duckdb_available():
        return _load_earthquakes_duckdb(event_id=event_id)
    df = pd.read_parquet(events_path)
    return df[df["event_id"] == event_id].copy()


def _resolve_aftershock_anchor_event_id(event_id: str) -> tuple[str | None, pd.DataFrame]:
    main_df = _load_earthquake_event_row(event_id)
    if len(main_df) == 0:
        return None, main_df

    seed_row = main_df.iloc[0]
    mainshock_id = seed_row.get("mainshock_id")
    if mainshock_id:
        anchor_df = _load_earthquake_event_row(str(mainshock_id))
        if len(anchor_df) > 0:
            return str(mainshock_id), anchor_df
    return event_id, main_df


def _build_aftershock_feature_collection(event_id: str, min_magnitude: float = None) -> dict | None:
    events_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
    if not parquet_available(events_path):
        return None

    anchor_event_id, mainshock_df = _resolve_aftershock_anchor_event_id(event_id)
    if not anchor_event_id or len(mainshock_df) == 0:
        return None

    if duckdb_available():
        aftershocks_df = _load_earthquakes_duckdb(mainshock_id=anchor_event_id, min_magnitude=min_magnitude)
        result_df = pd.concat([mainshock_df, aftershocks_df], ignore_index=True)
        if min_magnitude is not None:
            result_df = result_df[(result_df["event_id"] == anchor_event_id) | (result_df["magnitude"] >= min_magnitude)]
    else:
        df = pd.read_parquet(events_path)
        aftershocks_df = df[df["mainshock_id"] == anchor_event_id]
        result_df = pd.concat([mainshock_df, aftershocks_df], ignore_index=True)
        if min_magnitude is not None:
            result_df = result_df[(result_df["event_id"] == anchor_event_id) | (result_df["magnitude"] >= min_magnitude)]

    result_df = ensure_year_column(result_df)
    features = build_geojson_features(result_df, get_earthquake_property_builders())

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "query_event_id": event_id,
            "event_id": anchor_event_id,
            "event_type": "earthquake",
            "total_count": len(features),
            "aftershock_count": max(0, len(features) - 1),
        },
    }


@router.get("/api/earthquakes/geojson")
async def get_earthquakes_geojson(
    year: int = None,
    start: str = None,
    end: str = None,
    min_magnitude: float = None,
    limit: int = None,
    loc_prefix: str = None,
    affected_loc_id: str = None,
):
    """Get earthquakes as GeoJSON points for map display."""
    try:
        events_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
        if not parquet_available(events_path):
            return msgpack_error("Earthquake data not available", 404)

        # Check the pre-warmer cache for the common animation case:
        # year + min_magnitude with no loc or limit filters.
        ck = None
        if (year is not None and start is None and end is None
                and loc_prefix is None and affected_loc_id is None and limit is None):
            ck = make_cache_key("earthquakes", year=year, min_magnitude=min_magnitude)
            cached_df = cache_get(ck)
            if cached_df is not None:
                df = cached_df
            else:
                df = _load_earthquakes_duckdb(
                    year=year, start=start, end=end, min_magnitude=min_magnitude,
                    limit=limit, loc_prefix=loc_prefix, affected_loc_id=affected_loc_id,
                    columns=EARTHQUAKE_MAP_COLUMNS,
                )
                if not df.empty:
                    cache_set(ck, df)
        elif start is not None and end is not None and limit is None and loc_prefix is None and affected_loc_id is None:
            ck = make_preload_cache_key("earthquakes", min_magnitude=min_magnitude)
            cached_slice = select_compatible_preload_slice(ck, start=start, end=end)
            if cached_slice is not None:
                df = cached_slice
            elif is_default_preload_range(start, end):
                df = select_filtered_event_rows_cached(
                    events_path,
                    cache_key=ck,
                    permanent=True,
                    columns=EARTHQUAKE_MAP_COLUMNS,
                    start=start,
                    end=end,
                    min_value_filters={"magnitude": min_magnitude} if min_magnitude is not None else None,
                )
            else:
                df = _load_earthquakes_duckdb(
                    year=year,
                    start=start,
                    end=end,
                    min_magnitude=min_magnitude,
                    limit=limit,
                    loc_prefix=loc_prefix,
                    affected_loc_id=affected_loc_id,
                    columns=EARTHQUAKE_MAP_COLUMNS,
                )
        else:
            df = _load_earthquakes_duckdb(
                year=year,
                start=start,
                end=end,
                min_magnitude=min_magnitude,
                limit=limit,
                loc_prefix=loc_prefix,
                affected_loc_id=affected_loc_id,
                columns=EARTHQUAKE_MAP_COLUMNS,
            )
        if df.empty and not duckdb_available():
            df = pd.read_parquet(events_path)
            df = ensure_year_column(df)

            if year is not None and "year" in df.columns:
                df = df[df["year"] == year]
            elif start is not None or end is not None:
                df = filter_by_time_range(df, start, end)
            if min_magnitude is not None:
                df = df[df["magnitude"] >= min_magnitude]

            df = apply_location_filters(
                df,
                "earthquakes",
                loc_prefix=loc_prefix,
                affected_loc_id=affected_loc_id,
            )

            if limit is not None and limit > 0:
                df = df.nlargest(limit, "magnitude")

        features = build_geojson_features(df, get_earthquake_property_builders())
        return msgpack_response({"type": "FeatureCollection", "features": features})

    except Exception as e:
        logger.error(f"Error fetching earthquakes GeoJSON: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/earthquakes/sequence/{sequence_id}")
async def get_earthquake_sequence(sequence_id: str, min_magnitude: float = None):
    """Get all earthquakes in a specific aftershock sequence."""
    try:
        events_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
        if not parquet_available(events_path):
            return msgpack_error("Earthquake data not available", 404)

        df = _load_earthquakes_duckdb(sequence_id=sequence_id, min_magnitude=min_magnitude)
        if df.empty and not duckdb_available():
            df = pd.read_parquet(events_path)
            df = df[df["sequence_id"] == sequence_id]
            if min_magnitude is not None:
                df = df[df["magnitude"] >= min_magnitude]

        if len(df) == 0:
            return msgpack_error(f"Sequence {sequence_id} not found", 404)

        df = ensure_year_column(df)
        features = build_geojson_features(df, get_earthquake_property_builders())

        logger.info(f"Returning {len(features)} events for sequence {sequence_id}")
        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "sequence_id": sequence_id,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching earthquake sequence {sequence_id}: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/earthquakes/aftershocks/{event_id}")
async def get_earthquake_aftershocks(event_id: str, min_magnitude: float = None):
    """Get mainshock + aftershocks for a specific event ID."""
    try:
        payload = _build_aftershock_feature_collection(event_id, min_magnitude=min_magnitude)
        if payload is None:
            return msgpack_error("Earthquake data not available", 404)
        if payload.get("metadata", {}).get("total_count", 0) == 0:
            return msgpack_error(f"Event {event_id} not found", 404)
        logger.info(
            "Returning %s events for aftershock query %s anchored at %s",
            payload["metadata"]["total_count"],
            event_id,
            payload["metadata"]["event_id"],
        )
        return msgpack_response(payload)

    except Exception as e:
        logger.error(f"Error fetching aftershocks for {event_id}: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/v1/earthquakes/aftershocks/{event_id}")
async def get_earthquake_aftershocks_json(event_id: str, min_magnitude: float = None):
    """JSON API helper for mainshock + aftershocks for any earthquake in a sequence."""
    try:
        payload = _build_aftershock_feature_collection(event_id, min_magnitude=min_magnitude)
        if payload is None:
            return JSONResponse({"error": "Earthquake data not available"}, status_code=404)
        if payload.get("metadata", {}).get("total_count", 0) == 0:
            return JSONResponse({"error": f"Event {event_id} not found"}, status_code=404)
        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"Error fetching earthquake aftershocks JSON for {event_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/earthquakes/{event_id}/related-tsunamis")
async def get_related_tsunamis_for_earthquake(event_id: str):
    """Return tsunami events linked to an earthquake through links.parquet."""
    try:
        events_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
        tsunami_path = GLOBAL_DIR / "disasters/tsunamis/events.parquet"
        links_path = GLOBAL_DIR / "disasters/links.parquet"
        if not parquet_available(events_path) or not parquet_available(tsunami_path) or not parquet_available(links_path):
            return msgpack_error("Linked disaster data not available", 404)

        eq_df = _load_earthquakes_duckdb(event_id=event_id)
        if eq_df.empty and not duckdb_available():
            eq_df = pd.read_parquet(events_path)
            eq_df = eq_df[eq_df["event_id"] == event_id]
        if eq_df.empty:
            return msgpack_error(f"Earthquake event {event_id} not found", 404)

        event_row = eq_df.iloc[0]
        source_loc_id = event_row.get("loc_id")
        source_event_id = event_row.get("event_id") or event_id
        if not source_loc_id and not source_event_id:
            return msgpack_response({"event_id": event_id, "related_tsunamis": [], "count": 0})

        link_columns = parquet_columns(links_path)
        target_event_ids: list[str] = []
        target_loc_ids: list[str] = []
        if "parent_event_id" in link_columns and "child_event_id" in link_columns and source_event_id:
            target_event_ids = select_linked_values(
                links_path,
                source_column="parent_event_id",
                source_value=source_event_id,
                target_column="child_event_id",
                link_type="triggered",
            )
        if not target_event_ids and source_loc_id:
            target_loc_ids = select_linked_loc_ids(
                links_path,
                source_column="parent_loc_id",
                source_loc_id=source_loc_id,
                target_column="child_loc_id",
                link_type="triggered",
            )
        if not target_event_ids and not target_loc_ids:
            return msgpack_response({"event_id": event_id, "related_tsunamis": [], "count": 0})

        ts_df = select_filtered_event_rows(
            tsunami_path,
            in_filters={"event_id": target_event_ids} if target_event_ids else {"loc_id": target_loc_ids},
            order_by_desc="year",
        )
        if ts_df.empty and not duckdb_available():
            ts_df = pd.read_parquet(tsunami_path)
            if target_event_ids and "event_id" in ts_df.columns:
                ts_df = ts_df[ts_df["event_id"].isin(target_event_ids)]
            else:
                ts_df = ts_df[ts_df["loc_id"].isin(target_loc_ids)]

        related = []
        for _, row in ts_df.iterrows():
            related.append(
                {
                    "event_id": row.get("event_id"),
                    "loc_id": row.get("loc_id"),
                    "year": safe_int(row, "year"),
                    "cause": row.get("cause"),
                    "max_water_height_m": safe_float(row, "max_water_height_m"),
                }
            )

        return msgpack_response(
            {
                "event_id": event_id,
                "earthquake_loc_id": source_loc_id,
                "related_tsunamis": related,
                "count": len(related),
            }
        )
    except Exception as e:
        logger.error(f"Error fetching related tsunamis for earthquake {event_id}: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/events/nearby-earthquakes")
async def get_nearby_earthquakes(
    lat: float,
    lon: float,
    timestamp: str = None,
    year: int = None,
    radius_km: float = 150.0,
    days_before: int = 30,
    days_after: int = 60,
    min_magnitude: float = 3.0,
):
    """Find earthquakes near a location within a time window."""
    try:
        events_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
        if not parquet_available(events_path):
            return msgpack_error("Earthquake data not available", 404)

        df = pd.read_parquet(events_path)
        df = filter_by_proximity(df, lat, lon, radius_km)

        if timestamp:
            df = filter_by_time_window(df, timestamp, days_before, days_after)
        elif year:
            df = ensure_year_column(df)
            df = df[df["year"] == year]

        df = df[df["magnitude"] >= min_magnitude]
        if len(df) == 0:
            return msgpack_response(
                {
                    "type": "FeatureCollection",
                    "features": [],
                    "count": 0,
                    "search_params": {"lat": lat, "lon": lon, "radius_km": radius_km},
                }
            )

        df = ensure_year_column(df)
        features = build_geojson_features(df, get_earthquake_property_builders())
        logger.info(f"Found {len(features)} earthquakes within {radius_km}km of ({lat}, {lon})")
        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "count": len(features),
                "search_params": {
                    "lat": lat,
                    "lon": lon,
                    "radius_km": radius_km,
                    "days_after": days_after,
                    "min_magnitude": min_magnitude,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error finding nearby earthquakes: {e}")
        return msgpack_error(str(e), 500)
