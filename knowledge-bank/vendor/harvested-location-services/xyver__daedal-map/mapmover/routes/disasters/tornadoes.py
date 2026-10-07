"""Tornado disaster endpoints."""

from fastapi import APIRouter

from mapmover.disaster_filters import apply_location_filters, get_default_min_year
from mapmover.duckdb_helpers import (
    duckdb_available, is_default_preload_range, make_cache_key, make_preload_cache_key, parquet_available,
    select_filtered_event_rows, select_filtered_event_rows_cached, select_rows_by_exact_value,
)
from mapmover.logging_analytics import logger
from mapmover.paths import GLOBAL_DIR

from .helpers import add_display_lifecycle_properties, filter_by_time_range, msgpack_error, msgpack_response


router = APIRouter()


TORNADO_MAP_COLUMNS = (
    "event_id", "tornado_scale", "tornado_length_mi", "tornado_width_yd",
    "felt_radius_km", "damage_radius_km", "timestamp", "time", "year",
    "deaths_direct", "injuries_direct", "damage_property", "location", "loc_id",
    "latitude", "longitude", "end_latitude", "end_longitude", "sequence_id",
    "sequence_position", "sequence_count", "display_start_timestamp",
    "display_end_timestamp", "display_animation_kind",
)


def parse_scale(scale_value) -> int:
    """Parse EF/F scale labels to integer for comparisons."""
    import pandas as pd

    if pd.isna(scale_value):
        return -1
    normalized = str(scale_value).upper().replace("EF", "").replace("F", "")
    try:
        return int(normalized)
    except Exception:
        return -1


@router.get("/api/tornadoes/geojson")
async def get_tornadoes_geojson(
    year: int = None,
    start: str = None,
    end: str = None,
    min_year: int = None,
    min_scale: str = None,
    loc_prefix: str = None,
    affected_loc_id: str = None,
):
    """Get tornado starter events as GeoJSON points for map display."""
    import pandas as pd

    if min_year is None:
        min_year = get_default_min_year("tornadoes", fallback=1990)

    try:
        events_path = GLOBAL_DIR / "disasters/tornadoes/events.parquet"
        if not parquet_available(events_path):
            return msgpack_error("Tornado data not available", 404)

        use_duckdb = duckdb_available()
        if use_duckdb:
            if year is not None and start is None and end is None and loc_prefix is None:
                df = select_filtered_event_rows_cached(
                    events_path,
                    columns=TORNADO_MAP_COLUMNS,
                    cache_key=make_cache_key("tornadoes", year=year, min_scale=min_scale),
                    year=year,
                )
            elif (
                start is not None and end is not None and loc_prefix is None
                and affected_loc_id is None and is_default_preload_range(start, end)
            ):
                df = select_filtered_event_rows_cached(
                    events_path,
                    columns=TORNADO_MAP_COLUMNS,
                    cache_key=make_preload_cache_key("tornadoes", min_scale=min_scale),
                    permanent=True,
                    start=start,
                    end=end,
                )
            else:
                min_filters = {"year": min_year} if year is None and (start is None and end is None) and min_year is not None else None
                df = select_filtered_event_rows(
                    events_path,
                    columns=TORNADO_MAP_COLUMNS,
                    year=year,
                    start=start,
                    end=end,
                    min_value_filters=min_filters,
                )
        else:
            df = pd.read_parquet(events_path)

        if not use_duckdb:
            if year is not None and "year" in df.columns:
                df = df[df["year"] == year]
            elif start is not None or end is not None:
                df = filter_by_time_range(df, start, end)
            elif min_year is not None and "year" in df.columns:
                df = df[df["year"] >= min_year]

        if min_scale is not None and "tornado_scale" in df.columns:
            df["_scale_num"] = df["tornado_scale"].apply(parse_scale)
            min_num = parse_scale(min_scale)
            df = df[df["_scale_num"] >= min_num]

        df = apply_location_filters(
            df,
            "tornadoes",
            loc_prefix=loc_prefix,
            affected_loc_id=affected_loc_id,
        )

        if "sequence_id" in df.columns and "sequence_position" in df.columns:
            is_standalone = df["sequence_id"].isna()
            is_sequence_start = df["sequence_position"] == 1
            df = df[is_standalone | is_sequence_start]

        valid_mask = df["latitude"].notna() & df["longitude"].notna()
        records = df[valid_mask].to_dict("records")

        features = []
        for row in records:
            time_val = row.get("timestamp") or row.get("time")
            sequence_count = int(row["sequence_count"]) if pd.notna(row.get("sequence_count")) else None
            has_sequence = sequence_count is not None and sequence_count > 1

            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(row["longitude"]), float(row["latitude"])],
                    },
                    "properties": {
                        "event_id": str(row.get("event_id", "")),
                        "tornado_scale": row.get("tornado_scale", ""),
                        "tornado_length_mi": float(row["tornado_length_mi"]) if pd.notna(row.get("tornado_length_mi")) else 0,
                        "tornado_width_yd": int(row["tornado_width_yd"]) if pd.notna(row.get("tornado_width_yd")) else 0,
                        "felt_radius_km": float(row["felt_radius_km"]) if pd.notna(row.get("felt_radius_km")) else 5,
                        "damage_radius_km": float(row["damage_radius_km"]) if pd.notna(row.get("damage_radius_km")) else 0.05,
                        "timestamp": str(time_val) if pd.notna(time_val) else None,
                        "year": int(row["year"]) if "year" in row and pd.notna(row.get("year")) else None,
                        "deaths_direct": int(row["deaths_direct"]) if pd.notna(row.get("deaths_direct")) else 0,
                        "injuries_direct": int(row["injuries_direct"]) if pd.notna(row.get("injuries_direct")) else 0,
                        "damage_property": int(row["damage_property"]) if pd.notna(row.get("damage_property")) else 0,
                        "location": row.get("location", ""),
                        "loc_id": row.get("loc_id", ""),
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "end_latitude": float(row["end_latitude"]) if pd.notna(row.get("end_latitude")) else None,
                        "end_longitude": float(row["end_longitude"]) if pd.notna(row.get("end_longitude")) else None,
                        "sequence_count": sequence_count,
                        "has_sequence": has_sequence,
                        "event_type": "tornado",
                    },
                }
            )
            add_display_lifecycle_properties(row, features[-1]["properties"])

        return msgpack_response({"type": "FeatureCollection", "features": features})
    except Exception as e:
        logger.error(f"Error fetching tornadoes GeoJSON: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/tornadoes/{event_id}")
async def get_tornado_detail(event_id: str):
    """Get detailed info for a single tornado including track endpoints."""
    import pandas as pd

    try:
        events_path = GLOBAL_DIR / "disasters/tornadoes/events.parquet"
        if not parquet_available(events_path):
            return msgpack_error("Tornado data not available", 404)

        if duckdb_available():
            tornado = select_rows_by_exact_value(events_path, "event_id", str(event_id))
        else:
            df = pd.read_parquet(events_path)
            tornado = df[df["event_id"].astype(str) == str(event_id)]
        if len(tornado) == 0:
            return msgpack_error("Tornado not found", 404)

        row = tornado.iloc[0]
        time_col = "timestamp" if "timestamp" in row.index else "time"
        time_val = row.get(time_col)
        timestamp_str = str(time_val) if pd.notna(time_val) else None
        width_km = float(row["tornado_width_yd"]) * 0.0009144 if pd.notna(row.get("tornado_width_yd")) else 0

        props = {
            "event_id": str(row["event_id"]),
            "tornado_scale": row.get("tornado_scale", ""),
            "tornado_length_mi": float(row["tornado_length_mi"]) if pd.notna(row.get("tornado_length_mi")) else 0,
            "tornado_width_yd": int(row["tornado_width_yd"]) if pd.notna(row.get("tornado_width_yd")) else 0,
            "felt_radius_km": float(row["felt_radius_km"]) if pd.notna(row.get("felt_radius_km")) else 5,
            "damage_radius_km": float(row["damage_radius_km"]) if pd.notna(row.get("damage_radius_km")) else 0.05,
            "width_km": width_km,
            "timestamp": timestamp_str,
            "deaths_direct": int(row["deaths_direct"]) if pd.notna(row.get("deaths_direct")) else 0,
            "deaths_indirect": int(row["deaths_indirect"]) if pd.notna(row.get("deaths_indirect")) else 0,
            "injuries_direct": int(row["injuries_direct"]) if pd.notna(row.get("injuries_direct")) else 0,
            "injuries_indirect": int(row["injuries_indirect"]) if pd.notna(row.get("injuries_indirect")) else 0,
            "damage_property": int(row["damage_property"]) if pd.notna(row.get("damage_property")) else 0,
            "damage_crops": int(row["damage_crops"]) if pd.notna(row.get("damage_crops")) else 0,
            "location": row.get("location", ""),
            "loc_id": row.get("loc_id", ""),
        }

        features = []
        start_lat = float(row["latitude"])
        start_lon = float(row["longitude"])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [start_lon, start_lat]},
                "properties": {**props, "point_type": "start"},
            }
        )

        end_lat = float(row["end_latitude"]) if pd.notna(row.get("end_latitude")) else None
        end_lon = float(row["end_longitude"]) if pd.notna(row.get("end_longitude")) else None
        if end_lat is not None and end_lon is not None:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[start_lon, start_lat], [end_lon, end_lat]]},
                    "properties": {**props, "geometry_type": "track"},
                }
            )

        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "event_id": str(row["event_id"]),
                    "event_type": "tornado",
                    "total_count": len(features),
                    "time_range": {"start": timestamp_str, "end": timestamp_str},
                },
            }
        )
    except Exception as e:
        logger.error(f"Error fetching tornado detail: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/tornadoes/{event_id}/sequence")
async def get_tornado_sequence(event_id: str):
    """Get a sequence of linked tornadoes (same storm system)."""
    import pandas as pd

    try:
        events_path = GLOBAL_DIR / "disasters/tornadoes/events.parquet"
        if not parquet_available(events_path):
            return msgpack_error("Tornado data not available", 404)

        use_duckdb = duckdb_available()
        if use_duckdb:
            seed = select_rows_by_exact_value(events_path, "event_id", str(event_id))
        else:
            df = pd.read_parquet(events_path)
            seed = df[df["event_id"].astype(str) == str(event_id)]
        if len(seed) == 0:
            return msgpack_error("Tornado not found", 404)

        seed_row = seed.iloc[0]
        sequence_id = seed_row.get("sequence_id")
        if pd.isna(sequence_id) or sequence_id is None:
            sequence_df = seed.copy()
        else:
            if use_duckdb:
                sequence_df = select_rows_by_exact_value(events_path, "sequence_id", sequence_id, order_by="sequence_position")
            else:
                sequence_df = df[df["sequence_id"] == sequence_id].copy()

        if "sequence_position" in sequence_df.columns and sequence_df["sequence_position"].notna().any():
            sequence_df = sequence_df.sort_values("sequence_position")
        elif "timestamp" in sequence_df.columns:
            sequence_df = sequence_df.sort_values("timestamp")

        if "year" not in sequence_df.columns and "timestamp" in sequence_df.columns:
            sequence_df["timestamp"] = pd.to_datetime(sequence_df["timestamp"], errors="coerce")
            sequence_df["year"] = sequence_df["timestamp"].dt.year

        features = []
        for pos, (_, row) in enumerate(sequence_df.iterrows(), 1):
            time_val = row.get("timestamp")
            raw_scale = row.get("tornado_scale", "")
            scale = str(raw_scale).upper() if pd.notna(raw_scale) else ""

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row["longitude"]), float(row["latitude"])],
                },
                "properties": {
                    "event_id": str(row.get("event_id", "")),
                    "tornado_scale": scale if scale else "",
                    "tornado_length_mi": float(row["tornado_length_mi"]) if pd.notna(row.get("tornado_length_mi")) else 0,
                    "tornado_width_yd": int(row["tornado_width_yd"]) if pd.notna(row.get("tornado_width_yd")) else 0,
                    "felt_radius_km": float(row["felt_radius_km"]) if pd.notna(row.get("felt_radius_km")) else 5,
                    "damage_radius_km": float(row["damage_radius_km"]) if pd.notna(row.get("damage_radius_km")) else 0.05,
                    "timestamp": str(time_val) if pd.notna(time_val) else None,
                    "year": int(row["year"]) if "year" in row and pd.notna(row["year"]) else None,
                    "deaths_direct": int(row["deaths_direct"]) if pd.notna(row.get("deaths_direct")) else 0,
                    "injuries_direct": int(row["injuries_direct"]) if pd.notna(row.get("injuries_direct")) else 0,
                    "damage_property": float(row["damage_property"]) if pd.notna(row.get("damage_property")) else 0,
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "end_latitude": float(row["end_latitude"]) if pd.notna(row.get("end_latitude")) else None,
                    "end_longitude": float(row["end_longitude"]) if pd.notna(row.get("end_longitude")) else None,
                    "is_seed": str(row.get("event_id", "")) == str(seed_row.get("event_id", "")),
                    "sequence_position": int(row["sequence_position"]) if pd.notna(row.get("sequence_position")) else pos,
                    "sequence_count": int(row["sequence_count"]) if pd.notna(row.get("sequence_count")) else len(sequence_df),
                    "event_type": "tornado",
                    "location": str(row.get("location", "")) if pd.notna(row.get("location")) else "",
                },
            }

            if pd.notna(row.get("end_latitude")) and pd.notna(row.get("end_longitude")):
                feature["properties"]["track"] = {
                    "type": "LineString",
                    "coordinates": [
                        [float(row["longitude"]), float(row["latitude"])],
                        [float(row["end_longitude"]), float(row["end_latitude"])],
                    ],
                }

            features.append(feature)

        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "event_id": str(seed_row.get("event_id", "")),
                    "event_type": "tornado",
                    "total_count": len(features),
                    "sequence_id": str(sequence_id) if pd.notna(sequence_id) else None,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error fetching tornado sequence: {e}")
        return msgpack_error(str(e), 500)
