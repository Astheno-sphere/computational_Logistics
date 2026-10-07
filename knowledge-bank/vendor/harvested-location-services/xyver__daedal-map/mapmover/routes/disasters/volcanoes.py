"""Volcano and eruption disaster endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import pandas as pd

from mapmover.disaster_filters import apply_location_filters
from mapmover.duckdb_helpers import (
    duckdb_available, make_cache_key, parquet_available,
    is_default_preload_range, make_preload_cache_key,
    select_filtered_event_rows, select_filtered_event_rows_cached, select_rows,
)
from mapmover.live_volcano_smithsonian import fetch_live_volcanoes
from mapmover.logging_analytics import logger
from mapmover.paths import GLOBAL_DIR

from .helpers import (
    build_geojson_features,
    ensure_year_column,
    filter_by_proximity,
    filter_by_time_range,
    filter_by_time_window,
    msgpack_error,
    msgpack_response,
    safe_bool,
    safe_float,
    safe_int,
    safe_str,
)


router = APIRouter()


@router.get("/api/volcanoes/live")
async def get_live_volcanoes(
    days: int = 365,
    start_time: str = None,
    end_time: str = None,
    min_vei: float = None,
    ongoing_only: bool = False,
    limit: int = 100,
    orderby: str = "time",
):
    """Fetch preliminary recent volcanic eruption updates directly from Smithsonian/GVP."""
    try:
        return fetch_live_volcanoes(
            days=days,
            start_time=start_time,
            end_time=end_time,
            min_vei=min_vei,
            ongoing_only=ongoing_only,
            limit=limit,
            orderby=orderby,
        )
    except ValueError as exc:
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_live_volcano_request",
                    "message": str(exc),
                }
            },
            status_code=400,
        )
    except Exception as exc:
        logger.error(f"Error fetching live volcanoes: {exc}")
        return JSONResponse(
            {
                "error": {
                    "code": "live_volcano_upstream_error",
                    "message": "Smithsonian/GVP live volcano request failed.",
                }
            },
            status_code=502,
        )


def get_eruption_property_builders():
    """Return property builders dict for volcanic eruption GeoJSON features."""
    return {
        "event_id": lambda r: r.get("event_id", ""),
        "eruption_id": lambda r: safe_int(r, "eruption_id"),
        "volcano_name": lambda r: r.get("volcano_name", ""),
        "VEI": lambda r: safe_int(r, "vei") or safe_int(r, "VEI"),
        "felt_radius_km": lambda r: safe_float(r, "felt_radius_km", 10.0),
        "damage_radius_km": lambda r: safe_float(r, "damage_radius_km", 3.0),
        "activity_type": lambda r: r.get("activity_type", ""),
        "activity_area": lambda r: safe_str(r, "activity_area", None),
        "year": lambda r: safe_int(r, "year"),
        "end_year": lambda r: safe_int(r, "end_year"),
        "timestamp": lambda r: safe_str(r, "timestamp", None),
        "end_timestamp": lambda r: safe_str(r, "end_timestamp", None),
        "duration_days": lambda r: safe_float(r, "duration_days"),
        "is_ongoing": lambda r: safe_bool(r, "is_ongoing", False),
        "loc_id": lambda r: r.get("loc_id", ""),
        "latitude": lambda r: safe_float(r, "latitude"),
        "longitude": lambda r: safe_float(r, "longitude"),
    }


def get_volcano_catalog_property_builders():
    """Return property builders dict for volcano catalog (not eruption events)."""
    return {
        "volcano_id": lambda r: r.get("volcano_id", ""),
        "volcano_name": lambda r: r.get("volcano_name", ""),
        "VEI": lambda r: safe_int(r, "last_known_VEI"),
        "eruption_count": lambda r: safe_int(r, "eruption_count", 0),
        "last_eruption_year": lambda r: safe_int(r, "last_eruption_year"),
        "loc_id": lambda r: r.get("loc_id", ""),
    }


@router.get("/api/volcanoes/geojson")
async def get_volcanoes_geojson(active_only: bool = None):
    """Get volcanoes as GeoJSON points for map display."""
    try:
        volcanoes_path = GLOBAL_DIR / "disasters/volcanoes/volcanoes.parquet"
        if not parquet_available(volcanoes_path):
            return msgpack_error("Volcano data not available", 404)

        df = select_rows(volcanoes_path)
        if df.empty:
            df = pd.read_parquet(volcanoes_path)
        features = build_geojson_features(df, get_volcano_catalog_property_builders())

        return msgpack_response({"type": "FeatureCollection", "features": features})
    except Exception as e:
        logger.error(f"Error fetching volcanoes GeoJSON: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/eruptions/geojson")
async def get_eruptions_geojson(
    year: int = None,
    start: str = None,
    end: str = None,
    min_vei: int = None,
    min_year: int = None,
    exclude_ongoing: bool = False,
    loc_prefix: str = None,
    affected_loc_id: str = None,
):
    """Get volcanic eruptions as GeoJSON points for map display."""
    try:
        eruptions_path = GLOBAL_DIR / "disasters/volcanoes/events.parquet"
        if not parquet_available(eruptions_path):
            return msgpack_error("Eruption data not available", 404)

        if year is not None and start is None and end is None and min_vei is None and loc_prefix is None:
            df = select_filtered_event_rows_cached(
                eruptions_path,
                cache_key=make_cache_key("volcanoes", year=year),
                year=year,
            )
        elif (
            start is not None and end is not None and loc_prefix is None
            and affected_loc_id is None and is_default_preload_range(start, end)
        ):
            df = select_filtered_event_rows_cached(
                eruptions_path,
                cache_key=make_preload_cache_key("volcanoes", min_vei=min_vei, exclude_ongoing=exclude_ongoing),
                permanent=True,
                start=start,
                end=end,
                min_value_filters={"VEI": min_vei} if min_vei is not None else None,
            )
        else:
            df = select_filtered_event_rows(
                eruptions_path,
                year=year,
                start=start,
                end=end,
                min_value_filters={"VEI": min_vei},
                like_filters={"loc_id": f"{loc_prefix}%"} if loc_prefix else None,
            )
        if df.empty and not duckdb_available():
            df = pd.read_parquet(eruptions_path)
            df = ensure_year_column(df)

            if year is not None and "year" in df.columns:
                df = df[df["year"] == year]
            elif start is not None or end is not None:
                df = filter_by_time_range(df, start, end)
            elif min_year is not None and "year" in df.columns:
                df = df[df["year"] >= min_year]
            if min_vei is not None and "VEI" in df.columns:
                df = df[df["VEI"] >= min_vei]
            if exclude_ongoing and "is_ongoing" in df.columns:
                df = df[df["is_ongoing"] != True]

            df = apply_location_filters(
                df,
                "volcanoes",
                loc_prefix=loc_prefix,
                affected_loc_id=affected_loc_id,
            )
        else:
            if min_year is not None and "year" in df.columns:
                df = df[df["year"] >= min_year]
            if exclude_ongoing and "is_ongoing" in df.columns:
                df = df[df["is_ongoing"] != True]
            if affected_loc_id is not None and not df.empty:
                df = apply_location_filters(
                    df,
                    "volcanoes",
                    loc_prefix=None,
                    affected_loc_id=affected_loc_id,
                )

        features = build_geojson_features(df, get_eruption_property_builders())
        return msgpack_response({"type": "FeatureCollection", "features": features})

    except Exception as e:
        logger.error(f"Error fetching eruptions GeoJSON: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/events/nearby-volcanoes")
async def get_nearby_volcanoes(
    lat: float,
    lon: float,
    timestamp: str = None,
    year: int = None,
    radius_km: float = 150.0,
    days_before: int = 30,
    min_vei: int = None,
):
    """Find volcanic eruptions near a location within a time window."""
    try:
        eruptions_path = GLOBAL_DIR / "disasters/volcanoes/events.parquet"
        if not parquet_available(eruptions_path):
            return msgpack_error("Volcano data not available", 404)

        if timestamp:
            df = select_filtered_event_rows(eruptions_path, start=timestamp)
            if df.empty and not duckdb_available():
                df = pd.read_parquet(eruptions_path)
        elif year:
            df = select_filtered_event_rows(eruptions_path, year=year)
            if df.empty and not duckdb_available():
                df = pd.read_parquet(eruptions_path)
        else:
            df = select_filtered_event_rows(eruptions_path)
            if df.empty and not duckdb_available():
                df = pd.read_parquet(eruptions_path)
        df = filter_by_proximity(df, lat, lon, radius_km)

        if timestamp:
            df = filter_by_time_window(df, timestamp, days_before, 0)
        elif year:
            df = ensure_year_column(df)
            df = df[df["year"] == year]

        if min_vei is not None:
            vei_col = "vei" if "vei" in df.columns else "VEI"
            if vei_col in df.columns:
                df = df[df[vei_col] >= min_vei]

        if len(df) == 0:
            return msgpack_response(
                {
                    "type": "FeatureCollection",
                    "features": [],
                    "count": 0,
                    "search_params": {"lat": lat, "lon": lon, "radius_km": radius_km},
                }
            )

        features = build_geojson_features(df, get_eruption_property_builders())

        logger.info(f"Found {len(features)} eruptions within {radius_km}km of ({lat}, {lon})")
        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "count": len(features),
                "search_params": {
                    "lat": lat,
                    "lon": lon,
                    "radius_km": radius_km,
                    "days_before": days_before,
                    "min_vei": min_vei,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error finding nearby volcanoes: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/volcanoes/{event_id}/related-earthquakes")
async def get_related_earthquakes_for_volcano(event_id: str):
    """Return linked earthquake event IDs stored on a volcano eruption event."""
    try:
        eruptions_path = GLOBAL_DIR / "disasters/volcanoes/events.parquet"
        if not parquet_available(eruptions_path):
            return msgpack_error("Volcano data not available", 404)

        df = select_filtered_event_rows(
            eruptions_path,
            exact_filters={"event_id": event_id},
            limit=1,
        )
        if df.empty:
            df = pd.read_parquet(eruptions_path)
            df = df[df["event_id"] == event_id].head(1)

        if df.empty:
            return msgpack_error(f"Volcano event {event_id} not found", 404)

        row = df.iloc[0]
        raw_ids = row.get("earthquake_event_ids")
        if raw_ids is None or (hasattr(pd, "isna") and pd.isna(raw_ids)):
            earthquake_ids = []
        else:
            earthquake_ids = [s.strip() for s in str(raw_ids).split(",") if s and s.strip()]

        return msgpack_response(
            {
                "event_id": event_id,
                "volcano_name": row.get("volcano_name"),
                "earthquake_event_ids": earthquake_ids,
                "count": len(earthquake_ids),
            }
        )
    except Exception as e:
        logger.error(f"Error fetching related earthquakes for volcano {event_id}: {e}")
        return msgpack_error(str(e), 500)
