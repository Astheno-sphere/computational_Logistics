"""Wildfire disaster endpoints."""

from fastapi import APIRouter
import pandas as pd

from mapmover.disaster_filters import apply_location_filters, get_default_min_year
from mapmover.duckdb_helpers import cache_get, cache_set, duckdb_available, is_cloud_mode, is_default_preload_range, make_cache_key, make_preload_cache_key, parquet_available, path_to_uri, select_filtered_event_rows, select_filtered_partitioned_rows, select_rows
from mapmover.logging_analytics import logger
from mapmover.paths import COUNTRIES_DIR, GLOBAL_DIR

from .helpers import add_display_lifecycle_properties, filter_by_time_range, msgpack_error, msgpack_response


router = APIRouter()


WILDFIRE_SUMMARY_SOURCES = (
    ("global_fire_atlas", GLOBAL_DIR / "disasters/wildfires/events.parquet"),
    ("wildfires_usa", GLOBAL_DIR / "disasters/wildfires/sources/usa/fires_enriched.parquet"),
    ("can_wildfires", GLOBAL_DIR / "disasters/wildfires/sources/can/fires_enriched.parquet"),
)


def _resolve_first_existing(*paths):
    """Return the first existing path from a set of data-layout candidates."""
    if is_cloud_mode():
        return paths[0] if paths else None
    for path in paths:
        if path.exists():
            return path
    return paths[0] if paths else None


def list_wildfire_year_files():
    """Return available yearly wildfire parquet files (year, path), sorted by year."""
    if is_cloud_mode():
        # In S3 mode, generate the currently published year paths.
        # This avoids probing missing future partitions like 2025 when the
        # wildfire package only goes through 2024.
        files = []
        base = GLOBAL_DIR / "disasters/wildfires/by_year_enriched"
        for yr in range(2002, 2025):
            path = base / f"fires_{yr}_enriched.parquet"
            files.append((yr, path))
        return files

    files_by_year = {}
    for base, suffix in [
        (GLOBAL_DIR / "disasters/wildfires/by_year_enriched", "_enriched.parquet"),
        (GLOBAL_DIR / "disasters/wildfires/by_year", ".parquet"),
    ]:
        if not base.exists():
            continue
        for path in base.glob(f"fires_*{suffix}"):
            stem = path.stem
            parts = stem.split("_")
            if len(parts) < 2:
                continue
            try:
                yr = int(parts[1])
                # Prefer the enriched partition when both enriched and raw
                # yearly files exist for the same year.
                if yr not in files_by_year or suffix == "_enriched.parquet":
                    files_by_year[yr] = path
            except Exception:
                continue
    return sorted(files_by_year.items(), key=lambda x: x[0])


def wildfire_year_from_path(path) -> int | None:
    """Extract 4-digit year from wildfire file names."""
    stem = path.stem
    parts = stem.split("_")
    if len(parts) < 2:
        return None
    try:
        return int(parts[2]) if parts[0] == "fire" and parts[1] == "progression" else int(parts[1])
    except Exception:
        return None


def _load_wildfire_event_record(event_id: str):
    """Return the first matching wildfire event row across all event sources."""
    normalized_event_id = str(event_id or "").strip()
    if not normalized_event_id:
        return None

    for source_id, summary_path in WILDFIRE_SUMMARY_SOURCES:
        if not parquet_available(summary_path):
            continue
        try:
            if duckdb_available():
                df = select_rows(
                    summary_path,
                    exact_filters={"event_id": normalized_event_id},
                )
            else:
                df = pd.read_parquet(summary_path, filters=[("event_id", "=", normalized_event_id)])
        except Exception:
            continue
        if df is None or df.empty:
            continue
        row = df.iloc[0].to_dict()
        row["source_id"] = source_id
        return row
    return None


def _wildfire_source_supports_progression(source_id: str, row: dict | None = None) -> bool:
    if str(source_id or "").strip() != "global_fire_atlas":
        return False
    if isinstance(row, dict):
        value = row.get("has_progression")
        if value is not None and not pd.isna(value):
            try:
                return bool(value)
            except Exception:
                return False
    return True


def _extract_wildfire_event_year(row: dict | None) -> int | None:
    if not isinstance(row, dict):
        return None
    value = row.get("year")
    if value is not None and not pd.isna(value):
        try:
            return int(value)
        except Exception:
            pass
    timestamp_value = row.get("timestamp")
    if timestamp_value is None or pd.isna(timestamp_value):
        return None
    try:
        ts = pd.to_datetime(timestamp_value, errors="coerce")
    except Exception:
        return None
    if ts is None or pd.isna(ts):
        return None
    return int(ts.year)


def _candidate_wildfire_detail_years(resolved_year: int | None) -> list[int]:
    """Return likely year partitions for detail lookups, including year edges."""
    available_years = {int(year) for year, _path in list_wildfire_year_files()}
    if resolved_year is None:
        return sorted(available_years)

    candidates: list[int] = []
    for candidate_year in (resolved_year - 1, resolved_year, resolved_year + 1):
        if candidate_year in available_years and candidate_year not in candidates:
            candidates.append(candidate_year)
    return candidates


def _split_wildfire_detail_years(resolved_year: int | None) -> tuple[list[int], list[int]]:
    """Return exact-year candidates first, with boundary years as fallback."""
    if resolved_year is None:
        return [], []
    exact_years = _candidate_wildfire_detail_years(resolved_year)
    primary = [year for year in exact_years if year == resolved_year]
    fallback = [year for year in exact_years if year != resolved_year]
    return primary, fallback


def _resolve_wildfire_event_year(event_id: str, year: int | None = None) -> int | None:
    """Resolve a wildfire event's year from summary data before scanning detail files."""
    import pandas as pd
    import pyarrow.parquet as pq

    if year is not None:
        return year

    event_row = _load_wildfire_event_record(event_id)
    resolved_from_event = _extract_wildfire_event_year(event_row)
    if resolved_from_event is not None:
        return resolved_from_event

    summary_candidates = [
        GLOBAL_DIR / "disasters/wildfires/fires.parquet",
        _resolve_first_existing(
            GLOBAL_DIR / "disasters/wildfires/sources/usa/fires_enriched.parquet",
            COUNTRIES_DIR / "USA/disasters/wildfires/fires_enriched.parquet",
        ),
        _resolve_first_existing(
            GLOBAL_DIR / "disasters/wildfires/sources/can/fires_enriched.parquet",
            COUNTRIES_DIR / "CAN/wildfires/fires_enriched.parquet",
        ),
    ]

    for summary_path in summary_candidates:
        if summary_path is None or not parquet_available(summary_path):
            continue
        try:
            if duckdb_available():
                df = select_rows(
                    summary_path,
                    columns=["event_id", "timestamp"],
                    exact_filters={"event_id": event_id},
                )
            else:
                df = pq.read_table(
                    summary_path,
                    columns=["event_id", "timestamp"],
                    filters=[("event_id", "=", event_id)],
                ).to_pandas()
            if df is None or df.empty:
                continue
            row = df.iloc[0]
            ts = pd.to_datetime(row.get("timestamp"), errors="coerce")
            if pd.notna(ts):
                return int(ts.year)
        except Exception:
            continue

    matched_years: list[int] = []
    for candidate_year, summary_path in list_wildfire_year_files():
        if not parquet_available(summary_path):
            continue
        try:
            if duckdb_available():
                df = select_rows(
                    summary_path,
                    columns=["event_id"],
                    exact_filters={"event_id": event_id},
                )
                if df is not None and not df.empty:
                    matched_years.append(candidate_year)
            else:
                table = pq.read_table(summary_path, columns=["event_id"], filters=[("event_id", "=", event_id)])
                if table.num_rows > 0:
                    matched_years.append(candidate_year)
        except Exception:
            continue

    if len(matched_years) == 1:
        return matched_years[0]
    return None


@router.get("/api/wildfires/geojson")
async def get_wildfires_geojson(
    year: int = None,
    start: str = None,
    end: str = None,
    min_year: int = None,
    max_year: int = None,
    min_area_km2: float = None,
    include_perimeter: bool = False,
    loc_prefix: str = None,
    affected_loc_id: str = None,
):
    """Get wildfires as GeoJSON for map display."""
    import json as json_lib
    import pandas as pd
    import pyarrow.parquet as pq

    if min_year is None:
        min_year = get_default_min_year("wildfires", fallback=2010)

    # Cache key for simple year+area queries (no loc filter, no date range)
    _simple_cache = (
        year is not None
        and start is None
        and end is None
        and loc_prefix is None
        and affected_loc_id is None
        and not include_perimeter
    )
    _cache_key = make_cache_key("wildfires", year=year, min_area_km2=min_area_km2) if _simple_cache else None
    _is_preload_path = False
    if (
        _cache_key is None
        and start is not None and end is not None and loc_prefix is None and affected_loc_id is None
        and is_default_preload_range(start, end)
    ):
        _cache_key = make_preload_cache_key("wildfires", min_area_km2=min_area_km2, include_perimeter=include_perimeter)
        _is_preload_path = True

    try:
        if _cache_key is not None:
            cached_df = cache_get(_cache_key)
            if _is_preload_path:
                if cached_df is not None:
                    logger.info("wildfires preload cache HIT key=%s rows=%d", _cache_key, len(cached_df))
                else:
                    logger.info("wildfires preload cache MISS key=%s (will rebuild and store)", _cache_key)
            if cached_df is not None:
                valid_mask = cached_df["latitude"].notna() & cached_df["longitude"].notna()
                records = cached_df[valid_mask].to_dict("records")
                features = []
                for row in records:
                    ts = row.get("timestamp")
                    ts_str = ts.isoformat() if ts is not None and pd.notna(ts) and hasattr(ts, "isoformat") else (str(ts) if pd.notna(ts) else None)
                    if include_perimeter and row.get("perimeter") and pd.notna(row.get("perimeter")):
                        try:
                            geom = json_lib.loads(row["perimeter"]) if isinstance(row["perimeter"], str) else row["perimeter"]
                        except Exception:
                            geom = {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]}
                    else:
                        geom = {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]}
                    features.append({
                        "type": "Feature",
                        "geometry": geom,
                        "properties": {
                            "event_id": row.get("event_id", ""),
                            "area_km2": float(row["area_km2"]) if pd.notna(row.get("area_km2")) else None,
                            "burned_acres": float(row["burned_acres"]) if pd.notna(row.get("burned_acres")) else None,
                            "duration_days": int(row["duration_days"]) if pd.notna(row.get("duration_days")) else None,
                            "year": int(row["year"]) if pd.notna(row.get("year")) else None,
                            "timestamp": ts_str,
                            "land_cover": row.get("land_cover", ""),
                            "source": row.get("source", ""),
                            "latitude": float(row["latitude"]),
                            "longitude": float(row["longitude"]),
                            "has_progression": bool(row.get("has_progression", False)),
                            "loc_id": row.get("loc_id", ""),
                            "iso3": row.get("iso3", ""),
                        },
                    })
                    add_display_lifecycle_properties(row, features[-1]["properties"])
                return msgpack_response({
                    "type": "FeatureCollection",
                    "features": features,
                    "metadata": {"count": len(features), "min_area_km2": min_area_km2, "cached": True},
                })

        usa_fires_path = _resolve_first_existing(
            GLOBAL_DIR / "disasters/wildfires/sources/usa/fires_enriched.parquet",
            COUNTRIES_DIR / "USA/disasters/wildfires/fires_enriched.parquet",
        )
        can_fires_path = _resolve_first_existing(
            GLOBAL_DIR / "disasters/wildfires/sources/can/fires_enriched.parquet",
            COUNTRIES_DIR / "CAN/wildfires/fires_enriched.parquet",
        )
        global_by_year_path = GLOBAL_DIR / "disasters/wildfires/by_year_enriched"
        global_summary_path = GLOBAL_DIR / "disasters/wildfires/events.parquet"
        if not is_cloud_mode() and not global_by_year_path.exists():
            global_by_year_path = GLOBAL_DIR / "disasters/wildfires/by_year"

        base_columns = [
            "event_id",
            "timestamp",
            "latitude",
            "longitude",
            "area_km2",
            "burned_acres",
            "duration_days",
            "source",
            "has_progression",
            "loc_id",
            "parent_loc_id",
            "sibling_level",
            "iso3",
            "loc_confidence",
            "display_start_timestamp",
            "display_end_timestamp",
            "display_animation_kind",
        ]
        query_columns = base_columns + ["land_cover"]
        if include_perimeter:
            query_columns.append("perimeter")

        start_ts_parsed = None
        end_ts_parsed = None
        if start is not None or end is not None:
            import pandas as _pd

            if start:
                start_ts_parsed = _pd.to_datetime(int(start), unit="ms") if str(start).isdigit() else _pd.to_datetime(start)
            if end:
                end_ts_parsed = _pd.to_datetime(int(end), unit="ms") if str(end).isdigit() else _pd.to_datetime(end)

        if year is not None:
            years_to_load = [year]
        elif start_ts_parsed is not None or end_ts_parsed is not None:
            s_year = start_ts_parsed.year if start_ts_parsed else min_year
            e_year = end_ts_parsed.year if end_ts_parsed else (max_year or 2025)
            years_to_load = list(range(s_year, e_year + 1))
        else:
            end_year = max_year if max_year else 2024
            years_to_load = list(range(min_year, end_year + 1))

        # Regional wildfire summaries are not partitioned by year, so push the
        # requested rolling window into DuckDB instead of downloading every
        # USA/Canada row and slicing it in pandas.
        query_start = start
        query_end = end
        if query_start is None and years_to_load:
            query_start = f"{min(years_to_load):04d}-01-01 00:00:00"
        if query_end is None and years_to_load:
            query_end = f"{max(years_to_load):04d}-12-31 23:59:59"

        all_dfs = []
        source_used = []

        if loc_prefix is None or loc_prefix.startswith("USA"):
            if parquet_available(usa_fires_path):
                try:
                    if duckdb_available():
                        usa_df = select_filtered_event_rows(
                            usa_fires_path,
                            columns=query_columns,
                            start=query_start,
                            end=query_end,
                            min_value_filters={"area_km2": min_area_km2} if min_area_km2 is not None else None,
                            like_filters={"loc_id": f"{loc_prefix}%"} if loc_prefix else None,
                        )
                    else:
                        available = set(pq.read_schema(usa_fires_path).names)
                        usa_df = pd.read_parquet(
                            usa_fires_path,
                            columns=[column for column in query_columns if column in available],
                        )
                    usa_df["timestamp"] = pd.to_datetime(usa_df["timestamp"], errors="coerce")
                    usa_df["year"] = usa_df["timestamp"].dt.year
                    if year is not None:
                        usa_df = usa_df[usa_df["year"] == year]
                    elif years_to_load:
                        usa_df = usa_df[usa_df["year"].isin(years_to_load)]

                    if min_area_km2 is not None and "area_km2" in usa_df.columns:
                        usa_df = usa_df[usa_df["area_km2"] >= min_area_km2]
                    elif min_area_km2 is not None and "burned_acres" in usa_df.columns:
                        usa_df = usa_df[usa_df["burned_acres"] * 0.00404686 >= min_area_km2]

                    if "land_cover" not in usa_df.columns:
                        usa_df["land_cover"] = ""
                    if "area_km2" not in usa_df.columns and "burned_acres" in usa_df.columns:
                        usa_df["area_km2"] = usa_df["burned_acres"] * 0.00404686
                    if "duration_days" not in usa_df.columns:
                        usa_df["duration_days"] = None
                    if "source" not in usa_df.columns:
                        usa_df["source"] = "NIFC"
                    if "has_progression" not in usa_df.columns:
                        usa_df["has_progression"] = False

                    if len(usa_df) > 0:
                        all_dfs.append(usa_df)
                        source_used.append("USA")
                except Exception as exc:
                    logger.warning("Wildfires USA source unavailable for overlay request: %s", exc)

        if loc_prefix is None or loc_prefix.startswith("CAN"):
            if parquet_available(can_fires_path):
                try:
                    if duckdb_available():
                        can_df = select_filtered_event_rows(
                            can_fires_path,
                            columns=query_columns,
                            start=query_start,
                            end=query_end,
                            min_value_filters={"area_km2": min_area_km2} if min_area_km2 is not None else None,
                            like_filters={"loc_id": f"{loc_prefix}%"} if loc_prefix else None,
                        )
                    else:
                        available = set(pq.read_schema(can_fires_path).names)
                        can_df = pd.read_parquet(
                            can_fires_path,
                            columns=[column for column in query_columns if column in available],
                        )
                    can_df["timestamp"] = pd.to_datetime(can_df["timestamp"], errors="coerce")
                    can_df["year"] = can_df["timestamp"].dt.year
                    if year is not None:
                        can_df = can_df[can_df["year"] == year]
                    elif years_to_load:
                        can_df = can_df[can_df["year"].isin(years_to_load)]

                    if min_area_km2 is not None and "area_km2" in can_df.columns:
                        can_df = can_df[can_df["area_km2"] >= min_area_km2]

                    if "land_cover" not in can_df.columns:
                        can_df["land_cover"] = ""
                    if "source" not in can_df.columns:
                        can_df["source"] = "CNFDB"

                    if len(can_df) > 0:
                        all_dfs.append(can_df)
                        source_used.append("CAN")
                except Exception as exc:
                    logger.warning("Wildfires CAN source unavailable for overlay request: %s", exc)

        if loc_prefix is None or (not loc_prefix.startswith("USA") and not loc_prefix.startswith("CAN")):
            global_df = pd.DataFrame()

            # The canonical events table is the compact overview index for the
            # Fire Atlas source. The enriched year partitions are detail assets
            # and total more than a gigabyte; only touch them when an explicit
            # caller asks to inline final perimeter geometry.
            if not include_perimeter and parquet_available(global_summary_path):
                if duckdb_available():
                    global_df = select_filtered_event_rows(
                        global_summary_path,
                        columns=query_columns,
                        start=query_start,
                        end=query_end,
                        min_value_filters={"area_km2": min_area_km2} if min_area_km2 is not None else None,
                        like_filters={"loc_id": f"{loc_prefix}%"} if loc_prefix else None,
                    )
                else:
                    filters = [("area_km2", ">=", min_area_km2)] if min_area_km2 is not None else None
                    available = set(pq.read_schema(global_summary_path).names)
                    global_df = pq.read_table(
                        global_summary_path,
                        columns=[column for column in query_columns if column in available],
                        filters=filters,
                    ).to_pandas()
            elif parquet_available(global_by_year_path) or is_cloud_mode():
                available_year_files = dict(list_wildfire_year_files())
                year_files = []
                for yr in years_to_load:
                    year_file = available_year_files.get(yr)
                    if year_file is not None:
                        year_files.append(year_file)

                if year_files and duckdb_available():
                    global_df = select_filtered_partitioned_rows(
                        year_files,
                        columns=query_columns,
                        start=start,
                        end=end,
                        min_value_filters={"area_km2": min_area_km2} if min_area_km2 is not None else None,
                    )

                if global_df.empty and year_files:
                    all_tables = []
                    for year_file in year_files:
                        filters = [("area_km2", ">=", min_area_km2)] if min_area_km2 is not None else None
                        try:
                            table = pq.read_table(
                                year_file,
                                columns=[c for c in query_columns if c != "land_cover"],
                                filters=filters,
                            )
                            if table.num_rows > 0:
                                all_tables.append(table)
                        except Exception:
                            table = pq.read_table(year_file, filters=filters)
                            if table.num_rows > 0:
                                all_tables.append(table)

                    if all_tables:
                        import pyarrow as pa

                        combined = pa.concat_tables(all_tables)
                        global_df = combined.to_pandas()

            if not global_df.empty:
                global_df["timestamp"] = pd.to_datetime(global_df["timestamp"], errors="coerce")
                global_df["year"] = global_df["timestamp"].dt.year

                if "land_cover" not in global_df.columns:
                    global_df["land_cover"] = ""
                if "source" not in global_df.columns:
                    global_df["source"] = "global_fire_atlas"

                if "iso3" in global_df.columns:
                    before_filter = len(global_df)
                    global_df = global_df[~global_df["iso3"].isin(["USA", "CAN"])]
                    filtered_out = before_filter - len(global_df)
                    if filtered_out > 0:
                        logger.debug(f"Filtered {filtered_out:,} USA/CAN fires from global data")

                all_dfs.append(global_df)
                source_used.append("global")

        if not all_dfs:
            return msgpack_response(
                {
                    "type": "FeatureCollection",
                    "features": [],
                    "metadata": {"count": 0, "min_area_km2": min_area_km2, "min_year": min_year, "sources": []},
                }
            )

        df = pd.concat(all_dfs, ignore_index=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["year"] = df["timestamp"].dt.year

        # Re-apply explicit year bounds against actual timestamps to avoid partition leakage.
        if year is not None:
            df = df[df["year"] == year]
        else:
            if min_year is not None:
                df = df[df["year"] >= min_year]
            if max_year is not None:
                df = df[df["year"] <= max_year]

        if start_ts_parsed is not None or end_ts_parsed is not None:
            if start_ts_parsed is not None:
                if start_ts_parsed.tzinfo:
                    start_ts_parsed = start_ts_parsed.tz_convert("UTC").tz_localize(None)
                df = df[df["timestamp"] >= start_ts_parsed]
            if end_ts_parsed is not None:
                if end_ts_parsed.tzinfo:
                    end_ts_parsed = end_ts_parsed.tz_convert("UTC").tz_localize(None)
                df = df[df["timestamp"] <= end_ts_parsed]

        df = apply_location_filters(df, "wildfires", loc_prefix=loc_prefix, affected_loc_id=affected_loc_id)

        if _cache_key is not None and not df.empty:
            cache_set(_cache_key, df, permanent=is_default_preload_range(start, end))

        valid_mask = df["latitude"].notna() & df["longitude"].notna()
        records = df[valid_mask].to_dict("records")

        features = []
        for row in records:
            if include_perimeter and row.get("perimeter") and pd.notna(row.get("perimeter")):
                try:
                    geom = json_lib.loads(row["perimeter"]) if isinstance(row["perimeter"], str) else row["perimeter"]
                except Exception:
                    geom = {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]}
            else:
                geom = {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]}

            ts = row.get("timestamp")
            ts_str = ts.isoformat() if ts is not None and pd.notna(ts) and hasattr(ts, "isoformat") else (str(ts) if pd.notna(ts) else None)

            features.append(
                {
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "event_id": row.get("event_id", ""),
                        "area_km2": float(row["area_km2"]) if pd.notna(row.get("area_km2")) else None,
                        "burned_acres": float(row["burned_acres"]) if pd.notna(row.get("burned_acres")) else None,
                        "duration_days": int(row["duration_days"]) if pd.notna(row.get("duration_days")) else None,
                        "year": int(row["year"]) if pd.notna(row.get("year")) else None,
                        "timestamp": ts_str,
                        "land_cover": row.get("land_cover", ""),
                        "source": row.get("source", "global_fire_atlas"),
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "has_progression": bool(row.get("has_progression", False)),
                        "loc_id": row.get("loc_id", ""),
                        "parent_loc_id": row.get("parent_loc_id", ""),
                        "sibling_level": int(row["sibling_level"]) if pd.notna(row.get("sibling_level")) else None,
                        "iso3": row.get("iso3", ""),
                        "loc_confidence": float(row["loc_confidence"]) if pd.notna(row.get("loc_confidence")) else None,
                    },
                }
            )
            add_display_lifecycle_properties(row, features[-1]["properties"])

        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "count": len(features),
                    "min_area_km2": min_area_km2,
                    "min_year": min_year,
                    "max_year": max_year or 2024,
                    "include_perimeter": include_perimeter,
                    "sources": source_used,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error fetching wildfires GeoJSON: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/wildfires/{event_id}/perimeter")
async def get_wildfire_perimeter(event_id: str, year: int = None):
    """Get perimeter polygon for a single wildfire."""
    import json as json_lib
    import pyarrow.parquet as pq

    try:
        event_row = _load_wildfire_event_record(event_id)
        if event_row is not None and event_row.get("source_id") in {"wildfires_usa", "can_wildfires"}:
            perimeter_value = event_row.get("perimeter")
            if perimeter_value is not None and not pd.isna(perimeter_value):
                perimeter = json_lib.loads(perimeter_value) if isinstance(perimeter_value, str) else perimeter_value
                props = {
                    "event_id": str(event_row.get("event_id") or event_id),
                    "source_id": str(event_row.get("source_id") or ""),
                }
                event_year = _extract_wildfire_event_year(event_row)
                if event_year is not None:
                    props["year"] = event_year
                fire_name = str(event_row.get("fire_name") or "").strip()
                if fire_name:
                    props["fire_name"] = fire_name
                return msgpack_response({"type": "Feature", "geometry": perimeter, "properties": props})

        main_path = GLOBAL_DIR / "disasters/wildfires/fires.parquet"
        year_files = list_wildfire_year_files()
        resolved_year = _resolve_wildfire_event_year(event_id, year)

        primary_years, fallback_years = _split_wildfire_detail_years(resolved_year)
        matches = []
        candidate_groups = []
        if primary_years:
            candidate_groups.append([path for yr, path in year_files if yr in primary_years])
        if fallback_years:
            candidate_groups.append([path for yr, path in year_files if yr in fallback_years])
        if not candidate_groups:
            candidate_groups = [[path for _, path in year_files]]

        for candidate_files in candidate_groups:
            for year_file in candidate_files:
                try:
                    if duckdb_available():
                        df = select_rows(
                            year_file,
                            columns=["event_id", "perimeter"],
                            exact_filters={"event_id": event_id},
                        )
                        if df.empty:
                            continue
                        perimeter_str = df.iloc[0].get("perimeter")
                    else:
                        table = pq.read_table(year_file, columns=["event_id", "perimeter"], filters=[("event_id", "=", event_id)])
                        if table.num_rows == 0:
                            continue
                        perimeter_str = table.column("perimeter")[0].as_py()
                except Exception:
                    continue
                if perimeter_str:
                    perimeter = json_lib.loads(perimeter_str) if isinstance(perimeter_str, str) else perimeter_str
                    matches.append((wildfire_year_from_path(year_file), perimeter))
            if matches:
                break

        if len(matches) > 1 and year is None:
            years = [y for y, _ in matches if y is not None]
            return msgpack_response(
                {
                    "error": "Multiple wildfire events match this event_id; specify year",
                    "event_id": event_id,
                    "candidate_years": sorted(set(years)),
                },
                409,
            )
        if len(matches) == 1:
            matched_year, perimeter = matches[0]
            props = {"event_id": event_id}
            if matched_year is not None:
                props["year"] = matched_year
            return msgpack_response({"type": "Feature", "geometry": perimeter, "properties": props})

        if parquet_available(main_path):
            if duckdb_available():
                df = select_rows(
                    main_path,
                    columns=["event_id", "perimeter"],
                    exact_filters={"event_id": event_id},
                )
                if df.empty:
                    return msgpack_error(f"Fire {event_id} not found", 404)
                perimeter_str = df.iloc[0].get("perimeter")
            else:
                table = pq.read_table(main_path, columns=["event_id", "perimeter"], filters=[("event_id", "=", event_id)])
                if table.num_rows == 0:
                    return msgpack_error(f"Fire {event_id} not found", 404)
                perimeter_str = table.column("perimeter")[0].as_py()
            if perimeter_str is None:
                return msgpack_error("No perimeter data for this fire", 404)

            perimeter = json_lib.loads(perimeter_str) if isinstance(perimeter_str, str) else perimeter_str
            return msgpack_response({"type": "Feature", "geometry": perimeter, "properties": {"event_id": event_id}})

        if event_row is not None:
            source_label = str(event_row.get("source_id") or "wildfires").strip()
            return msgpack_error(f"No perimeter data published for wildfire {event_id} in source {source_label}", 404)

        return msgpack_error("Wildfire data not available", 404)
    except Exception as e:
        logger.error(f"Error fetching wildfire perimeter: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/wildfires/{event_id}/progression")
async def get_wildfire_progression(event_id: str, year: int = None):
    """Get daily fire progression snapshots for animation."""
    import json as json_lib
    import pyarrow.parquet as pq

    try:
        event_row = _load_wildfire_event_record(event_id)
        if event_row is not None:
            source_id = str(event_row.get("source_id") or "").strip()
            if not _wildfire_source_supports_progression(source_id, event_row):
                source_note = (
                    "Daily progression is currently published for the global fire atlas lane only."
                    if source_id in {"wildfires_usa", "can_wildfires"}
                    else "No progression data available for this wildfire event."
                )
                return msgpack_response(
                    {
                        "type": "FeatureCollection",
                        "features": [],
                        "metadata": {
                            "event_id": event_id,
                            "event_type": "wildfire",
                            "source_id": source_id or None,
                            "total_count": 0,
                            "error": source_note,
                        },
                    }
                )

        progression_path = GLOBAL_DIR / "disasters/wildfires"
        resolved_year = _resolve_wildfire_event_year(event_id, year)
        if not is_cloud_mode() and not progression_path.exists():
            return msgpack_response(
                {
                    "type": "FeatureCollection",
                    "features": [],
                    "metadata": {
                        "event_id": event_id,
                        "event_type": "wildfire",
                        "total_count": 0,
                        "error": "No progression data available",
                    },
                }
            )

        primary_years, fallback_years = _split_wildfire_detail_years(resolved_year)
        matches = []
        candidate_groups = []
        if primary_years:
            candidate_groups.append([progression_path / f"fire_progression_{candidate_year}.parquet" for candidate_year in primary_years])
        if fallback_years:
            candidate_groups.append([progression_path / f"fire_progression_{candidate_year}.parquet" for candidate_year in fallback_years])
        if not candidate_groups:
            candidate_groups = [sorted(progression_path.glob("fire_progression_*.parquet"), reverse=True)]

        for candidate_files in candidate_groups:
            for prog_file in candidate_files:
                if not is_cloud_mode() and not prog_file.exists():
                    continue
                if duckdb_available():
                    current_df = select_rows(
                        prog_file,
                        exact_filters={"event_id": str(event_id)},
                    )
                    if not current_df.empty:
                        matches.append((wildfire_year_from_path(prog_file), current_df))
                else:
                    current = pq.read_table(prog_file, filters=[("event_id", "=", str(event_id))])
                    if current.num_rows > 0:
                        matches.append((wildfire_year_from_path(prog_file), current.to_pandas()))
            if matches:
                break

        if len(matches) > 1 and year is None:
            years = [y for y, _ in matches if y is not None]
            return msgpack_response(
                {
                    "error": "Multiple wildfire progressions match this event_id; specify year",
                    "event_id": event_id,
                    "candidate_years": sorted(set(years)),
                },
                409,
            )
        if len(matches) == 0:
            return msgpack_response(
                {
                    "type": "FeatureCollection",
                    "features": [],
                    "metadata": {
                        "event_id": event_id,
                        "event_type": "wildfire",
                        "total_count": 0,
                        "error": "Fire not found in progression data",
                    },
                }
            )
        matched_year, df = matches[0]
        df = df.sort_values("day_num")
        features = []
        for _, row in df.iterrows():
            perimeter = json_lib.loads(row["perimeter"]) if isinstance(row["perimeter"], str) else row["perimeter"]
            date_str = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])
            features.append(
                {
                    "type": "Feature",
                    "geometry": perimeter,
                    "properties": {
                        "date": date_str,
                        "day_num": int(row["day_num"]),
                        "area_km2": float(row["area_km2"]),
                    },
                }
            )

        time_start = df["date"].min()
        time_end = df["date"].max()
        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "event_id": event_id,
                    "event_type": "wildfire",
                    "source_id": "global_fire_atlas",
                    "total_count": len(features),
                    "year": matched_year,
                    "time_range": {
                        "start": time_start.strftime("%Y-%m-%d") if hasattr(time_start, "strftime") else str(time_start),
                        "end": time_end.strftime("%Y-%m-%d") if hasattr(time_end, "strftime") else str(time_end),
                    },
                },
            }
        )
    except Exception as e:
        logger.error(f"Error fetching wildfire progression: {e}")
        return msgpack_error(str(e), 500)
