"""Shared helpers for disaster API routers."""

from __future__ import annotations

from fastapi import Response
import msgpack


def msgpack_response(data: dict, status_code: int = 200, headers: dict | None = None) -> Response:
    """Standard MessagePack response for API endpoints."""
    return Response(
        content=msgpack.packb(data, use_bin_type=True),
        media_type="application/msgpack",
        status_code=status_code,
        headers=headers,
    )


def msgpack_error(message: str, status_code: int = 500) -> Response:
    """Standard MessagePack error response."""
    return msgpack_response({"error": message}, status_code)


def ensure_year_column(df):
    """Extract year from timestamp column if needed."""
    import pandas as pd

    if "year" not in df.columns and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["year"] = df["timestamp"].dt.year
    return df


def filter_by_proximity(df, lat: float, lon: float, radius_km: float, lat_col: str = "latitude", lon_col: str = "longitude"):
    """Filter DataFrame to rows within radius_km of a point."""
    import numpy as np

    lat_range = radius_km / 111.0
    lon_range = radius_km / (111.0 * max(0.01, np.cos(np.radians(lat))))

    return df[
        (df[lat_col] >= lat - lat_range)
        & (df[lat_col] <= lat + lat_range)
        & (df[lon_col] >= lon - lon_range)
        & (df[lon_col] <= lon + lon_range)
    ]


def filter_by_time_window(df, timestamp: str, days_before: int, days_after: int, time_col: str = "timestamp"):
    """Filter DataFrame to rows within a time window around a timestamp."""
    import pandas as pd
    from datetime import timedelta

    try:
        event_time = pd.to_datetime(timestamp)
        if event_time.tzinfo is not None:
            event_time = event_time.tz_convert("UTC").tz_localize(None)

        start_time = event_time - timedelta(days=days_before)
        end_time = event_time + timedelta(days=days_after)

        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        if df[time_col].dt.tz is not None:
            df[time_col] = df[time_col].dt.tz_convert("UTC").dt.tz_localize(None)

        return df[(df[time_col] >= start_time) & (df[time_col] <= end_time)]
    except Exception:
        return df


def filter_by_time_range(df, start: str = None, end: str = None, time_col: str = "timestamp"):
    """Filter DataFrame by start/end timestamp range."""
    import pandas as pd

    if start is None and end is None:
        return df

    try:
        def parse_ts(val):
            if val is None:
                return None
            if str(val).isdigit():
                return pd.Timestamp(int(val), unit="ms")
            return pd.to_datetime(val)

        start_ts = parse_ts(start)
        end_ts = parse_ts(end)

        if start_ts and start_ts.tzinfo is not None:
            start_ts = start_ts.tz_convert("UTC").tz_localize(None)
        if end_ts and end_ts.tzinfo is not None:
            end_ts = end_ts.tz_convert("UTC").tz_localize(None)

        if time_col in df.columns:
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
            if df[time_col].dt.tz is not None:
                df[time_col] = df[time_col].dt.tz_convert("UTC").dt.tz_localize(None)
            if start_ts is not None:
                df = df[df[time_col] >= start_ts]
            if end_ts is not None:
                df = df[df[time_col] <= end_ts]
        elif "year" in df.columns:
            if start_ts is not None:
                df = df[df["year"] >= start_ts.year]
            if end_ts is not None:
                df = df[df["year"] <= end_ts.year]

        return df
    except Exception:
        return df


def safe_float(row, col, default=None):
    """Safely read optional float field from a row dict-like object."""
    import pandas as pd

    val = row.get(col)
    return float(val) if pd.notna(val) else default


def safe_int(row, col, default=None):
    """Safely read optional int field from a row dict-like object."""
    import pandas as pd

    val = row.get(col)
    return int(val) if pd.notna(val) else default


def safe_str(row, col, default=""):
    """Safely read optional string field from a row dict-like object."""
    import pandas as pd

    val = row.get(col)
    return str(val) if pd.notna(val) else default


def safe_bool(row, col, default=False):
    """Safely read optional bool field from a row dict-like object."""
    import pandas as pd

    val = row.get(col)
    return bool(val) if pd.notna(val) else default


DISPLAY_LIFECYCLE_FIELDS = (
    "display_start_timestamp",
    "display_end_timestamp",
    "display_animation_kind",
    "display_wave_speed_km_per_ms",
    "display_max_radius_km",
)


def add_display_lifecycle_properties(row, props: dict) -> dict:
    """Copy prepared presentation timing into a GeoJSON feature payload.

    These fields are authored during source preparation. Routes only serialize
    them; the browser must not recreate them from an event-type heuristic.
    """
    import pandas as pd

    for field in DISPLAY_LIFECYCLE_FIELDS:
        value = row.get(field)
        if value is None or pd.isna(value):
            continue
        props[field] = value.isoformat() if hasattr(value, "isoformat") else value.item() if hasattr(value, "item") else value
    return props


def build_geojson_features(df, property_builders: dict, lat_col: str = "latitude", lon_col: str = "longitude"):
    """Build GeoJSON point features from a DataFrame."""
    if df.empty or lat_col not in df.columns or lon_col not in df.columns:
        return []
    valid_mask = df[lat_col].notna() & df[lon_col].notna()
    valid_df = df[valid_mask]

    if valid_df.empty:
        return []

    records = valid_df.to_dict("records")

    features = []
    for row in records:
        props = {name: builder(row) for name, builder in property_builders.items()}
        add_display_lifecycle_properties(row, props)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row[lon_col]), float(row[lat_col])],
                },
                "properties": props,
            }
        )

    return features
