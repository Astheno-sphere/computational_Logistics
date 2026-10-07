"""Weather API router endpoints."""

from datetime import datetime, timezone
from glob import glob
from pathlib import Path

from fastapi import APIRouter

from mapmover.duckdb_helpers import duckdb_available, select_columns_from_parquet
from mapmover.logging_analytics import logger
from mapmover.paths import GLOBAL_DIR
from mapmover.routes.disasters.helpers import msgpack_error, msgpack_response


router = APIRouter()


def _build_grid_payload(
    *,
    files: list[str],
    requested_vars: list[str],
    actual_tier: str,
    requested_tier: str,
    parse_timestamp,
    color_scales: dict,
):
    import numpy as np
    import pandas as pd

    timestamps = []
    all_values = {var: [] for var in requested_vars}
    grid_info = None
    columns_to_read = ["lat", "lon"] + requested_vars

    for filepath in files:
        try:
            parquet_path = Path(filepath)
            if duckdb_available():
                df = select_columns_from_parquet(parquet_path, columns_to_read)
                if df.empty:
                    df = pd.read_parquet(filepath, columns=columns_to_read)
            else:
                df = pd.read_parquet(filepath, columns=columns_to_read)

            ts = parse_timestamp(Path(filepath))
            df = df.sort_values(["lat", "lon"], ascending=[False, True])

            if grid_info is None:
                unique_lats = sorted(df["lat"].unique(), reverse=True)
                unique_lons = sorted(df["lon"].unique())
                lat_step = abs(unique_lats[1] - unique_lats[0]) if len(unique_lats) > 1 else 2
                lon_step = abs(unique_lons[1] - unique_lons[0]) if len(unique_lons) > 1 else 2
                grid_info = {
                    "lat_start": float(unique_lats[0]),
                    "lon_start": float(unique_lons[0]),
                    "lat_step": float(lat_step),
                    "lon_step": float(lon_step),
                    "rows": len(unique_lats),
                    "cols": len(unique_lons),
                }

            ts_ms = int(ts.timestamp() * 1000)
            timestamps.append(ts_ms)

            for var in requested_vars:
                values = df[var].values.tolist()
                values = [None if (isinstance(v, float) and np.isnan(v)) else v for v in values]
                all_values[var].append(values)
        except Exception as e:
            logger.warning(f"Could not read {filepath}: {e}")
            continue

    if not timestamps:
        return None

    sort_indices = sorted(range(len(timestamps)), key=lambda i: timestamps[i])
    timestamps = [timestamps[i] for i in sort_indices]
    for var in requested_vars:
        all_values[var] = [all_values[var][i] for i in sort_indices]

    if grid_info is None:
        grid_info = {"lat_start": 89, "lon_start": -179, "lat_step": 2, "lon_step": 2, "rows": 90, "cols": 180}

    return {
        "tier": actual_tier,
        "requested_tier": requested_tier,
        "variables": requested_vars,
        "timestamps": timestamps,
        "values": all_values,
        "grid": grid_info,
        "color_scales": {var: color_scales.get(var, next(iter(color_scales.values()))) for var in requested_vars},
        "count": len(timestamps),
    }


@router.get("/api/weather/grid")
async def get_weather_grid(tier: str, variables: str, year: int = None):
    """
    Get weather grid data for animation.

    Loads parquet files and pivots to wide format for efficient animation.
    Returns timestamps array + values dict (keyed by variable, 16,020 values per timestamp).
    """
    import numpy as np
    import pandas as pd

    try:
        weather_base = GLOBAL_DIR / "climate" / "weather"

        if tier not in ("hourly", "weekly", "monthly"):
            return msgpack_error(f"Invalid tier: {tier}. Must be hourly, weekly, or monthly", 400)

        valid_vars = {
            "temp_c",
            "humidity",
            "snow_depth_m",
            "precipitation_mm",
            "cloud_cover_pct",
            "pressure_hpa",
            "solar_radiation",
            "soil_temp_c",
            "soil_moisture",
        }
        requested_vars = [v.strip() for v in variables.split(",") if v.strip()]
        if not requested_vars:
            return msgpack_error("Missing variables parameter", 400)
        invalid = [v for v in requested_vars if v not in valid_vars]
        if invalid:
            return msgpack_error(f"Invalid variables: {invalid}. Must be one of: {valid_vars}", 400)

        actual_tier = tier
        files = []

        def get_files_for_tier(t, y):
            t_dir = weather_base / t
            if not t_dir.exists():
                return []

            if t == "monthly":
                if y is None:
                    return []
                y_dir = t_dir / str(y)
                if not y_dir.exists():
                    return []
                return sorted(glob(str(y_dir / "*.parquet")))

            all_files = sorted(glob(str(t_dir / "**" / "*.parquet"), recursive=True))
            if y is not None:
                return [f for f in all_files if f"/{y}/" in f.replace("\\", "/") or f"\\{y}\\" in f]
            return all_files

        files = get_files_for_tier(tier, year)

        if not files and tier == "weekly":
            logger.info(f"No weekly data for {year}, trying hourly")
            files = get_files_for_tier("hourly", year)
            if files:
                actual_tier = "hourly"
            else:
                logger.info(f"No hourly data for {year}, trying monthly")
                files = get_files_for_tier("monthly", year)
                if files:
                    actual_tier = "monthly"

        if not files and tier == "monthly":
            logger.info(f"No monthly data for {year}, trying weekly")
            files = get_files_for_tier("weekly", year)
            if files:
                actual_tier = "weekly"
            else:
                logger.info(f"No weekly data for {year}, trying hourly")
                files = get_files_for_tier("hourly", year)
                if files:
                    actual_tier = "hourly"

        if not files:
            return msgpack_error(f"No {tier} data files found for year {year}", 404)

        color_scales = {
            "temp_c": {
                "min": -40,
                "max": 45,
                "stops": [[-40, "#00008B"], [-30, "#0000FF"], [-10, "#87CEEB"], [0, "#FFFFFF"], [10, "#FFFF99"], [25, "#FFA500"], [35, "#FF0000"], [45, "#8B0000"]],
            },
            "humidity": {"min": 0, "max": 100, "stops": [[0, "#FFFFFF"], [25, "#E0FFFF"], [50, "#87CEEB"], [75, "#4682B4"], [100, "#000080"]]},
            "snow_depth_m": {"min": 0, "max": 2, "stops": [[0, "#FFFFFF"], [0.1, "#FFFFFF"], [0.5, "#E6E6FA"], [1.0, "#9370DB"], [2.0, "#4B0082"]]},
            "precipitation_mm": {
                "min": 0,
                "max": 50,
                "stops": [[0, "#FFFFFF"], [1, "#E0FFE0"], [5, "#90EE90"], [15, "#228B22"], [30, "#006400"], [50, "#00008B"]],
            },
            "cloud_cover_pct": {"min": 0, "max": 100, "stops": [[0, "#87CEEB"], [25, "#B0C4DE"], [50, "#A9A9A9"], [75, "#696969"], [100, "#404040"]]},
            "pressure_hpa": {"min": 970, "max": 1050, "stops": [[970, "#8B0000"], [990, "#FF6347"], [1010, "#FFFFFF"], [1030, "#87CEEB"], [1050, "#00008B"]]},
            "solar_radiation": {"min": 0, "max": 1000, "stops": [[0, "#000000"], [100, "#4B0082"], [300, "#FF8C00"], [600, "#FFD700"], [1000, "#FFFFFF"]]},
            "soil_temp_c": {"min": -20, "max": 40, "stops": [[-20, "#00008B"], [-10, "#0000FF"], [0, "#8B4513"], [15, "#D2691E"], [30, "#FF4500"], [40, "#8B0000"]]},
            "soil_moisture": {"min": 0, "max": 0.5, "stops": [[0, "#DEB887"], [0.1, "#D2B48C"], [0.2, "#8FBC8F"], [0.3, "#228B22"], [0.5, "#006400"]]},
        }

        payload = _build_grid_payload(
            files=files,
            requested_vars=requested_vars,
            actual_tier=actual_tier,
            requested_tier=tier,
            parse_timestamp=lambda path: (
                datetime(int(path.parts[-2]), int(path.name.replace(".parquet", "")), 1, tzinfo=timezone.utc)
                if actual_tier == "monthly"
                else datetime.strptime(
                    f"{int(path.parts[-2])}-W{int(path.name.replace('.parquet', '')):02d}-1",
                    "%G-W%V-%u",
                ).replace(tzinfo=timezone.utc)
                if actual_tier == "weekly"
                else datetime(
                    int(path.parts[-4]),
                    int(path.parts[-3]),
                    int(path.parts[-2]),
                    int(path.name.replace(".parquet", "")),
                    tzinfo=timezone.utc,
                )
            ),
            color_scales=color_scales,
        )
        if payload is None:
            return msgpack_error("No valid data files could be read", 500)
        return msgpack_response(payload)
    except Exception as e:
        logger.error(f"Error fetching weather grid: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/climate/grid")
async def get_climate_grid(source: str, variables: str, year: int = None, tier: str = "monthly"):
    try:
        source_id = str(source or "").strip().lower()
        if source_id != "ocean_sst":
            return msgpack_error(f"Unsupported climate grid source: {source}", 400)
        if tier != "monthly":
            return msgpack_error("ocean_sst grid currently supports tier=monthly only", 400)
        if year is None:
            return msgpack_error("Missing year parameter", 400)

        requested_vars = [v.strip() for v in variables.split(",") if v.strip()]
        valid_vars = {"sst_c", "sst_anom_c"}
        if not requested_vars:
            return msgpack_error("Missing variables parameter", 400)
        invalid = [v for v in requested_vars if v not in valid_vars]
        if invalid:
            return msgpack_error(f"Invalid variables: {invalid}. Must be one of: {valid_vars}", 400)

        grid_base = GLOBAL_DIR / "climate" / "ocean_sst" / "grid" / "monthly" / str(year)
        if not grid_base.exists():
            return msgpack_error(f"No monthly ocean_sst grid files found for year {year}", 404)
        files = sorted(glob(str(grid_base / "*.parquet")))
        if not files:
            return msgpack_error(f"No monthly ocean_sst grid files found for year {year}", 404)

        color_scales = {
            "sst_c": {
                "min": -2,
                "max": 36,
                "stops": [[-2, "#2b2c7f"], [0, "#2f6db3"], [10, "#5ec5ff"], [18, "#f8f7cf"], [24, "#f5a65b"], [30, "#df5b3f"], [36, "#7f0000"]],
            },
            "sst_anom_c": {
                "min": -5,
                "max": 5,
                "stops": [[-5, "#08306b"], [-2, "#4292c6"], [0, "#f7f7f7"], [2, "#fb6a4a"], [5, "#67000d"]],
            },
        }
        payload = _build_grid_payload(
            files=files,
            requested_vars=requested_vars,
            actual_tier="monthly",
            requested_tier=tier,
            parse_timestamp=lambda path: datetime(int(path.parts[-2]), int(path.name.replace(".parquet", "")), 1, tzinfo=timezone.utc),
            color_scales=color_scales,
        )
        if payload is None:
            return msgpack_error("No valid climate grid files could be read", 500)
        payload["source"] = source_id
        return msgpack_response(payload)
    except Exception as e:
        logger.error(f"Error fetching climate grid: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/weather/available")
async def get_weather_available():
    """Get available time ranges for each weather tier."""
    try:
        weather_base = GLOBAL_DIR / "climate" / "weather"
        result = {}

        hourly_dir = weather_base / "hourly"
        if hourly_dir.exists():
            files = sorted(glob(str(hourly_dir / "**" / "*.parquet"), recursive=True))
            if files:
                first = files[0]
                last = files[-1]
                fp = Path(first).parts
                lp = Path(last).parts
                first_ts = datetime(int(fp[-4]), int(fp[-3]), int(fp[-2]), int(fp[-1].replace(".parquet", "")), tzinfo=timezone.utc)
                last_ts = datetime(int(lp[-4]), int(lp[-3]), int(lp[-2]), int(lp[-1].replace(".parquet", "")), tzinfo=timezone.utc)
                result["hourly"] = {"min": first_ts.isoformat(), "max": last_ts.isoformat(), "count": len(files)}

        weekly_dir = weather_base / "weekly"
        if weekly_dir.exists():
            files = sorted(glob(str(weekly_dir / "**" / "*.parquet"), recursive=True))
            if files:
                years = set()
                for f in files:
                    years.add(int(Path(f).parts[-2]))
                result["weekly"] = {"min_year": min(years), "max_year": max(years), "count": len(files)}

        monthly_dir = weather_base / "monthly"
        if monthly_dir.exists():
            year_dirs = sorted([d for d in monthly_dir.iterdir() if d.is_dir() and d.name.isdigit()])
            if year_dirs:
                all_files = glob(str(monthly_dir / "**" / "*.parquet"), recursive=True)
                result["monthly"] = {
                    "min_year": int(year_dirs[0].name),
                    "max_year": int(year_dirs[-1].name),
                    "years": [int(d.name) for d in year_dirs],
                    "count": len(all_files),
                }

        result["default_min_year"] = 2000
        return msgpack_response(result)
    except Exception as e:
        logger.error(f"Error checking weather availability: {e}")
        return msgpack_error(str(e), 500)
