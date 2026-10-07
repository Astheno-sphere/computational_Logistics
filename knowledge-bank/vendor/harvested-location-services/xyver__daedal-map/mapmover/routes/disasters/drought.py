"""Drought disaster endpoints."""

from fastapi import APIRouter

from mapmover.duckdb_helpers import duckdb_available, parquet_available, select_filtered_event_rows
from mapmover.logging_analytics import logger
from mapmover.paths import COUNTRIES_DIR

from .helpers import filter_by_time_range, msgpack_error, msgpack_response


router = APIRouter()


@router.get("/api/drought/geojson")
async def get_drought_geojson(
    country: str = "CAN",
    year: int = None,
    start: str = None,
    end: str = None,
    month: int = None,
    severity: str = None,
    min_year: int = None,
    max_year: int = None,
):
    """Get drought monitoring data as GeoJSON for choropleth animation."""
    import json as json_lib
    import pandas as pd

    try:
        if country == "CAN":
            data_path = COUNTRIES_DIR / "CAN" / "drought/snapshots.parquet"
        else:
            return msgpack_error(f"Drought data not available for country: {country}", 404)

        if not parquet_available(data_path):
            return msgpack_error("Drought data not available", 404)

        use_duckdb = duckdb_available()
        if use_duckdb:
            df = select_filtered_event_rows(
                data_path,
                year=year,
                start=start,
                end=end,
                min_value_filters={"year": min_year} if year is None and start is None and end is None and min_year else None,
                exact_filters={"severity": severity.upper()} if severity else None,
            )
            if max_year and "year" in df.columns:
                df = df[df["year"] <= max_year]
        else:
            df = pd.read_parquet(data_path)

            if year is not None:
                df = df[df["year"] == year]
            elif start is not None or end is not None:
                df = filter_by_time_range(df, start, end)
            else:
                if min_year:
                    df = df[df["year"] >= min_year]
                if max_year:
                    df = df[df["year"] <= max_year]

        if month is not None:
            df = df[df["month"] == month]
        if severity and not use_duckdb:
            df = df[df["severity"] == severity.upper()]

        df = df.sort_values("severity_code")

        def to_python(val):
            if pd.isna(val):
                return None
            if hasattr(val, "item"):
                return val.item()
            return val

        records = df.to_dict("records")
        features = []
        for row in records:
            geom = None
            geom_val = row.get("geometry")
            if pd.notna(geom_val):
                try:
                    geom = json_lib.loads(geom_val)
                except Exception as e:
                    logger.warning(f"Failed to parse drought geometry for {row.get('snapshot_id')}: {e}")
                    continue
            if not geom:
                continue

            ts = row.get("timestamp")
            ts_str = ts.isoformat() if ts is not None and pd.notna(ts) and hasattr(ts, "isoformat") else None
            end_ts = row.get("end_timestamp")
            end_ts_str = end_ts.isoformat() if end_ts is not None and pd.notna(end_ts) and hasattr(end_ts, "isoformat") else None

            props = {
                "snapshot_id": str(row.get("snapshot_id", "")),
                "timestamp": ts_str,
                "end_timestamp": end_ts_str,
                "duration_days": to_python(row.get("duration_days")),
                "year": to_python(row.get("year")),
                "month": to_python(row.get("month")),
                "severity": str(row.get("severity", "")),
                "severity_code": to_python(row.get("severity_code")),
                "severity_name": str(row.get("severity_name", "")),
                "area_km2": to_python(row.get("area_km2")),
                "iso3": str(row.get("iso3", "")),
                "provinces_affected": str(row.get("provinces_affected", "")) if pd.notna(row.get("provinces_affected")) else None,
            }

            features.append({"type": "Feature", "geometry": geom, "properties": props})

        max_year_value = None
        if max_year:
            max_year_value = max_year
        elif len(df) > 0:
            max_year_value = int(df["year"].max())

        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "count": len(features),
                    "country": country,
                    "min_year": min_year or 2019,
                    "max_year": max_year_value,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error fetching drought data: {e}")
        return msgpack_error(str(e), 500)
