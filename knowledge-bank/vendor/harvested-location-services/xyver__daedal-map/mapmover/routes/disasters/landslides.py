"""Landslide disaster endpoints."""

from fastapi import APIRouter

from mapmover.duckdb_helpers import duckdb_available, parquet_available, select_filtered_event_rows
from mapmover.logging_analytics import logger
from mapmover.paths import GLOBAL_DIR

from .helpers import (
    build_geojson_features,
    filter_by_time_range,
    msgpack_error,
    msgpack_response,
    safe_float,
    safe_int,
    safe_str,
)


router = APIRouter()


def get_landslide_property_builders():
    """Return property builders dict for landslide GeoJSON features."""
    import math

    return {
        "event_id": lambda r: r.get("event_id", ""),
        "year": lambda r: safe_int(r, "year"),
        "timestamp": lambda r: safe_str(r, "timestamp", None),
        "event_name": lambda r: safe_str(r, "event_name", None),
        "deaths": lambda r: safe_int(r, "deaths", 0),
        "injuries": lambda r: safe_int(r, "injuries", 0),
        "missing": lambda r: safe_int(r, "missing", 0),
        "affected": lambda r: safe_int(r, "affected", 0),
        "houses_destroyed": lambda r: safe_int(r, "houses_destroyed", 0),
        "damage_usd": lambda r: safe_float(r, "damage_usd"),
        "source": lambda r: r.get("source", ""),
        "loc_id": lambda r: r.get("loc_id", ""),
        "latitude": lambda r: safe_float(r, "latitude"),
        "longitude": lambda r: safe_float(r, "longitude"),
        "intensity": lambda r: min(5, 1 + math.log10(max(1, safe_int(r, "deaths", 0) or 1))),
        "felt_radius_km": lambda r: 5 + 5 * min(5, math.log10(max(1, safe_int(r, "deaths", 0) or 1))),
        "damage_radius_km": lambda r: 2 + 3 * min(5, math.log10(max(1, safe_int(r, "deaths", 0) or 1))),
    }


@router.get("/api/landslides/geojson")
async def get_landslides_geojson(
    year: int = None,
    start: str = None,
    end: str = None,
    min_deaths: int = 1,
    require_coords: bool = True,
):
    """Get landslide events as GeoJSON points for map display."""
    import pandas as pd

    try:
        events_path = GLOBAL_DIR / "disasters/landslides/events.parquet"
        if not parquet_available(events_path):
            return msgpack_error("Landslide data not available", 404)

        use_duckdb = duckdb_available()
        if use_duckdb:
            min_filters = {"deaths": min_deaths} if min_deaths > 0 else None
            df = select_filtered_event_rows(
                events_path,
                year=year,
                start=start,
                end=end,
                min_value_filters=min_filters,
            )
        else:
            df = pd.read_parquet(events_path)

        if require_coords:
            df = df[df["latitude"].notna() & df["longitude"].notna()]

        if not use_duckdb:
            if year is not None:
                df = df[df["year"] == year]
            elif start is not None or end is not None:
                df = filter_by_time_range(df, start, end)

        if min_deaths > 0 and not use_duckdb:
            df["deaths_val"] = df["deaths"].fillna(0)
            df = df[df["deaths_val"] >= min_deaths]
            df = df.drop(columns=["deaths_val"])

        features = build_geojson_features(df, get_landslide_property_builders())

        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "count": len(features),
                    "year_range": [int(df["year"].min()), int(df["year"].max())] if len(df) > 0 else None,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error fetching landslides GeoJSON: {e}")
        return msgpack_error(str(e), 500)
