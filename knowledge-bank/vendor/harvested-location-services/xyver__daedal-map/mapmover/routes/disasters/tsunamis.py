"""Tsunami disaster endpoints."""

from fastapi import APIRouter

from mapmover.disaster_filters import apply_location_filters, get_default_min_year
from mapmover.duckdb_helpers import (
    duckdb_available,
    is_default_preload_range,
    make_cache_key,
    make_preload_cache_key,
    parquet_available,
    parquet_columns,
    select_filtered_event_rows,
    select_filtered_event_rows_cached,
    select_linked_loc_ids,
    select_linked_values,
    select_rows_by_exact_value,
)
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
    safe_float,
    safe_int,
    safe_str,
)


router = APIRouter()


def get_tsunami_property_builders():
    """Return property builders dict for tsunami source event GeoJSON features."""
    return {
        "event_id": lambda r: r.get("event_id", ""),
        "year": lambda r: safe_int(r, "year"),
        "timestamp": lambda r: safe_str(r, "timestamp", None),
        "country": lambda r: r.get("country", ""),
        "location": lambda r: safe_str(r, "location", None),
        "cause": lambda r: r.get("cause", ""),
        "cause_code": lambda r: safe_int(r, "cause_code"),
        "eq_magnitude": lambda r: safe_float(r, "eq_magnitude"),
        "max_water_height_m": lambda r: safe_float(r, "max_water_height_m"),
        "intensity": lambda r: safe_float(r, "intensity"),
        "runup_count": lambda r: safe_int(r, "runup_count", 0),
        "deaths": lambda r: safe_int(r, "deaths"),
        "damage_millions": lambda r: safe_float(r, "damage_millions"),
        "loc_id": lambda r: r.get("loc_id", ""),
        # ``loc_id`` above is the one geometry-spine key. These generic
        # provenance fields explain its point-in-polygon derivation without
        # introducing a second marine-specific location namespace.
        "geometry_assignment_kind": lambda r: safe_str(r, "geometry_assignment_kind", None),
        "geometry_family": lambda r: safe_str(r, "geometry_family", None),
        "geometry_bank": lambda r: safe_str(r, "geometry_bank", None),
        "geometry_candidate_count": lambda r: safe_int(r, "geometry_candidate_count"),
        "physical_surface": lambda r: safe_str(r, "physical_surface", None),
        "latitude": lambda r: safe_float(r, "latitude"),
        "longitude": lambda r: safe_float(r, "longitude"),
        "is_source": lambda r: True,
    }


@router.get("/api/tsunamis/geojson")
async def get_tsunamis_geojson(
    year: int = None,
    start: str = None,
    end: str = None,
    min_height_m: float = None,
    min_year: int = None,
    cause: str = None,
    loc_prefix: str = None,
    affected_loc_id: str = None,
):
    """Get tsunami source events as GeoJSON points for map display."""
    import pandas as pd

    if min_year is None:
        min_year = get_default_min_year("tsunamis", fallback=1900)

    try:
        events_path = GLOBAL_DIR / "disasters/tsunamis/events.parquet"
        if not parquet_available(events_path):
            return msgpack_error("Tsunami data not available", 404)

        use_duckdb = duckdb_available()
        if use_duckdb:
            if year is not None:
                df = select_filtered_event_rows_cached(
                    events_path,
                    cache_key=make_cache_key("tsunamis", year=year, min_height_m=min_height_m),
                    year=year,
                    min_value_filters={"max_water_height_m": min_height_m} if min_height_m is not None else None,
                )
            elif start is not None or end is not None:
                if (
                    loc_prefix is None and affected_loc_id is None and cause is None
                    and is_default_preload_range(start, end)
                ):
                    df = select_filtered_event_rows_cached(
                        events_path,
                        cache_key=make_preload_cache_key("tsunamis", min_height_m=min_height_m),
                        permanent=True,
                        start=start,
                        end=end,
                        min_value_filters={"max_water_height_m": min_height_m} if min_height_m is not None else None,
                    )
                else:
                    df = select_filtered_event_rows(
                        events_path,
                        start=start,
                        end=end,
                        min_value_filters={"max_water_height_m": min_height_m} if min_height_m is not None else None,
                    )
            else:
                min_filters = {}
                if min_year is not None:
                    min_filters["year"] = min_year
                if min_height_m is not None:
                    min_filters["max_water_height_m"] = min_height_m
                df = select_filtered_event_rows_cached(
                    events_path,
                    cache_key=make_cache_key("tsunamis", min_year=min_year, min_height_m=min_height_m),
                    min_value_filters=min_filters or None,
                )
        else:
            df = pd.read_parquet(events_path)

        if not use_duckdb:
            if year is not None:
                df = df[df["year"] == year]
            elif start is not None or end is not None:
                df = filter_by_time_range(df, start, end)
            elif min_year is not None:
                df = df[df["year"] >= min_year]
        if min_height_m is not None and "max_water_height_m" in df.columns:
            df = df[df["max_water_height_m"] >= min_height_m]
        if cause is not None:
            df = df[df["cause"].str.lower() == cause.lower()]

        df = apply_location_filters(
            df,
            "tsunamis",
            loc_prefix=loc_prefix,
            affected_loc_id=affected_loc_id,
            event_id_col="event_id",
        )

        features = build_geojson_features(df, get_tsunami_property_builders())
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
        logger.error(f"Error fetching tsunamis GeoJSON: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/tsunamis/{event_id}/runups")
async def get_tsunami_runups(event_id: str):
    """Get runup observations for a specific tsunami event."""
    import pandas as pd

    try:
        runups_path = GLOBAL_DIR / "disasters/tsunamis/runups.parquet"
        events_path = GLOBAL_DIR / "disasters/tsunamis/events.parquet"

        if not parquet_available(runups_path):
            return msgpack_error("Runup data not available", 404)

        if duckdb_available():
            runups_df = select_rows_by_exact_value(runups_path, "event_id", event_id)
        else:
            runups_df = pd.read_parquet(runups_path)
            runups_df = runups_df[runups_df["event_id"] == event_id]
        if len(runups_df) == 0:
            return msgpack_error(f"No runups found for event {event_id}", 404)

        source_event = None
        if parquet_available(events_path):
            if duckdb_available():
                event_row = select_rows_by_exact_value(events_path, "event_id", event_id)
            else:
                events_df = pd.read_parquet(events_path)
                event_row = events_df[events_df["event_id"] == event_id]
            if len(event_row) > 0:
                row = event_row.iloc[0]
                source_event = {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]},
                    "properties": {
                        "event_id": event_id,
                        "year": int(row["year"]) if pd.notna(row.get("year")) else None,
                        "timestamp": str(row["timestamp"]) if pd.notna(row.get("timestamp")) else None,
                        "cause": row.get("cause", ""),
                        "eq_magnitude": float(row["eq_magnitude"]) if pd.notna(row.get("eq_magnitude")) else None,
                        "max_water_height_m": float(row["max_water_height_m"]) if pd.notna(row.get("max_water_height_m")) else None,
                        "_isSource": True,
                        "is_source": True,
                    },
                }

        features = []
        for _, row in runups_df.iterrows():
            if pd.isna(row["latitude"]) or pd.isna(row["longitude"]):
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]},
                    "properties": {
                        "runup_id": row.get("runup_id", ""),
                        "event_id": event_id,
                        "year": int(row["year"]) if pd.notna(row.get("year")) else None,
                        "country": row.get("country", ""),
                        "location_name": row.get("location", "") if pd.notna(row.get("location")) else None,
                        "water_height_m": float(row["water_height_m"]) if pd.notna(row.get("water_height_m")) else None,
                        "dist_from_source_km": float(row["dist_from_source_km"]) if pd.notna(row.get("dist_from_source_km")) else None,
                        "travel_time_hours": float(row["arrival_travel_time_min"]) / 60 if pd.notna(row.get("arrival_travel_time_min")) else None,
                        "deaths": int(row["deaths"]) if pd.notna(row.get("deaths")) else None,
                        "_isSource": False,
                        "is_source": False,
                    },
                }
            )

        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "source": source_event,
                "metadata": {
                    "event_id": event_id,
                    "event_type": "tsunami",
                    "total_count": len(features),
                    "runup_count": len(features),
                },
            }
        )
    except Exception as e:
        logger.error(f"Error fetching tsunami runups: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/tsunamis/{event_id}/animation")
async def get_tsunami_animation_data(event_id: str):
    """Get combined source + runups data formatted for radial animation."""
    import pandas as pd

    try:
        runups_path = GLOBAL_DIR / "disasters/tsunamis/runups.parquet"
        events_path = GLOBAL_DIR / "disasters/tsunamis/events.parquet"
        if not parquet_available(events_path) or not parquet_available(runups_path):
            return msgpack_error("Tsunami data not available", 404)

        if duckdb_available():
            event_row = select_rows_by_exact_value(events_path, "event_id", event_id)
        else:
            events_df = pd.read_parquet(events_path)
            event_row = events_df[events_df["event_id"] == event_id]
        if len(event_row) == 0:
            return msgpack_error(f"Event {event_id} not found", 404)
        row = event_row.iloc[0]

        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]},
                "properties": {
                    "event_id": event_id,
                    "year": int(row["year"]) if pd.notna(row.get("year")) else None,
                    "timestamp": str(row["timestamp"]) if pd.notna(row.get("timestamp")) else None,
                    "cause": row.get("cause", ""),
                    "eq_magnitude": float(row["eq_magnitude"]) if pd.notna(row.get("eq_magnitude")) else None,
                    "max_water_height_m": float(row["max_water_height_m"]) if pd.notna(row.get("max_water_height_m")) else None,
                    "deaths": int(row["deaths"]) if pd.notna(row.get("deaths")) else None,
                    "is_source": True,
                },
            }
        ]

        if duckdb_available():
            runups_df = select_rows_by_exact_value(runups_path, "event_id", event_id)
        else:
            runups_df = pd.read_parquet(runups_path)
            runups_df = runups_df[runups_df["event_id"] == event_id]
        for _, rrow in runups_df.iterrows():
            if pd.isna(rrow["latitude"]) or pd.isna(rrow["longitude"]):
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(rrow["longitude"]), float(rrow["latitude"])]},
                    "properties": {
                        "runup_id": rrow.get("runup_id", ""),
                        "event_id": event_id,
                        "country": rrow.get("country", ""),
                        "location_name": rrow.get("location", "") if pd.notna(rrow.get("location")) else None,
                        "water_height_m": float(rrow["water_height_m"]) if pd.notna(rrow.get("water_height_m")) else None,
                        "dist_from_source_km": float(rrow["dist_from_source_km"]) if pd.notna(rrow.get("dist_from_source_km")) else None,
                        "arrival_travel_time_min": float(rrow["arrival_travel_time_min"]) if pd.notna(rrow.get("arrival_travel_time_min")) else None,
                        "timestamp": str(rrow["timestamp"]) if pd.notna(rrow.get("timestamp")) else None,
                        "deaths": int(rrow["deaths"]) if pd.notna(rrow.get("deaths")) else None,
                        "is_source": False,
                    },
                }
            )

        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "event_id": event_id,
                    "event_type": "tsunami",
                    "total_count": len(features),
                    "source_timestamp": str(row["timestamp"]) if pd.notna(row.get("timestamp")) else None,
                    "runup_count": len(features) - 1,
                    "animation_mode": "radial",
                },
            }
        )
    except Exception as e:
        logger.error(f"Error fetching tsunami animation data: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/events/nearby-tsunamis")
async def get_nearby_tsunamis(
    lat: float,
    lon: float,
    timestamp: str = None,
    year: int = None,
    radius_km: float = 300.0,
    days_before: int = 1,
    days_after: int = 30,
):
    """Find tsunamis near a location within a time window."""
    import pandas as pd

    try:
        tsunamis_path = GLOBAL_DIR / "disasters/tsunamis/events.parquet"
        if not parquet_available(tsunamis_path):
            return msgpack_error("Tsunami data not available", 404)

        if timestamp:
            df = select_filtered_event_rows(tsunamis_path, start=timestamp)
            if df.empty and not duckdb_available():
                df = pd.read_parquet(tsunamis_path)
        elif year:
            df = select_filtered_event_rows(tsunamis_path, year=year)
            if df.empty and not duckdb_available():
                df = pd.read_parquet(tsunamis_path)
        else:
            df = select_filtered_event_rows(tsunamis_path)
            if df.empty and not duckdb_available():
                df = pd.read_parquet(tsunamis_path)

        df = filter_by_proximity(df, lat, lon, radius_km)

        if timestamp:
            df = filter_by_time_window(df, timestamp, days_before, days_after)
        elif year:
            df = ensure_year_column(df)
            df = df[df["year"] == year]

        if len(df) == 0:
            return msgpack_response(
                {
                    "type": "FeatureCollection",
                    "features": [],
                    "count": 0,
                    "search_params": {"lat": lat, "lon": lon, "radius_km": radius_km},
                }
            )

        features = build_geojson_features(df, get_tsunami_property_builders())
        logger.info(f"Found {len(features)} tsunamis within {radius_km}km of ({lat}, {lon})")
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
                    "days_after": days_after,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error finding nearby tsunamis: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/tsunamis/{event_id}/related-earthquakes")
async def get_related_earthquakes_for_tsunami(event_id: str):
    """Return earthquake events linked to a tsunami through links.parquet."""
    import pandas as pd

    try:
        tsunami_path = GLOBAL_DIR / "disasters/tsunamis/events.parquet"
        eq_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
        links_path = GLOBAL_DIR / "disasters/links.parquet"
        if not parquet_available(tsunami_path) or not parquet_available(eq_path) or not parquet_available(links_path):
            return msgpack_error("Linked disaster data not available", 404)

        tsunami_df = select_rows_by_exact_value(tsunami_path, "event_id", event_id)
        if tsunami_df.empty and not duckdb_available():
            tsunami_df = pd.read_parquet(tsunami_path)
            tsunami_df = tsunami_df[tsunami_df["event_id"] == event_id]
        if tsunami_df.empty:
            return msgpack_error(f"Tsunami event {event_id} not found", 404)

        event_row = tsunami_df.iloc[0]
        source_loc_id = event_row.get("loc_id")
        source_event_id = event_row.get("event_id") or event_id
        if not source_loc_id and not source_event_id:
            return msgpack_response({"event_id": event_id, "related_earthquakes": [], "count": 0})

        link_columns = parquet_columns(links_path)
        target_event_ids: list[str] = []
        target_loc_ids: list[str] = []
        if "child_event_id" in link_columns and "parent_event_id" in link_columns and source_event_id:
            target_event_ids = select_linked_values(
                links_path,
                source_column="child_event_id",
                source_value=source_event_id,
                target_column="parent_event_id",
                link_type="triggered",
            )
        if not target_event_ids and source_loc_id:
            target_loc_ids = select_linked_loc_ids(
                links_path,
                source_column="child_loc_id",
                source_loc_id=source_loc_id,
                target_column="parent_loc_id",
                link_type="triggered",
            )
        if not target_event_ids and not target_loc_ids:
            return msgpack_response({"event_id": event_id, "related_earthquakes": [], "count": 0})

        eq_df = select_filtered_event_rows(
            eq_path,
            in_filters={"event_id": target_event_ids} if target_event_ids else {"loc_id": target_loc_ids},
            order_by_desc="magnitude",
        )
        if eq_df.empty and not duckdb_available():
            eq_df = pd.read_parquet(eq_path)
            if target_event_ids and "event_id" in eq_df.columns:
                eq_df = eq_df[eq_df["event_id"].isin(target_event_ids)]
            else:
                eq_df = eq_df[eq_df["loc_id"].isin(target_loc_ids)]

        related = []
        for _, row in eq_df.iterrows():
            related.append(
                {
                    "event_id": row.get("event_id"),
                    "loc_id": row.get("loc_id"),
                    "year": safe_int(row, "year"),
                    "magnitude": safe_float(row, "magnitude"),
                    "place": row.get("place"),
                }
            )

        return msgpack_response(
            {
                "event_id": event_id,
                "tsunami_loc_id": source_loc_id,
                "related_earthquakes": related,
                "count": len(related),
            }
        )
    except Exception as e:
        logger.error(f"Error fetching related earthquakes for tsunami {event_id}: {e}")
        return msgpack_error(str(e), 500)
