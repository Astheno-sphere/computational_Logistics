from pathlib import Path

from mapmover.runtime.source_hints import source_geometry_kind, source_geometry_subkind


def resolve_aggregate_admin2_dir(source_path: str | Path, *, data_root: Path | None = None) -> Path:
    """Resolve the canonical admin2 aggregate directory for a source path."""
    source_dir = Path(source_path)
    if data_root is not None and not source_dir.is_absolute():
        source_dir = data_root / source_dir

    if (
        source_dir.name.lower() == "admin2"
        and source_dir.parent.name.lower() == "aggregates"
        and source_dir.parent.parent.name.lower() == "sources"
    ):
        return source_dir.parent.parent.parent / "aggregates" / "admin2"
    if source_dir.name.lower() == "aggregates" and source_dir.parent.name.lower() == "sources":
        return source_dir.parent.parent / "aggregates" / "admin2"
    if source_dir.name.lower() == "admin2" and source_dir.parent.name.lower() == "aggregates":
        return source_dir
    if source_dir.name.lower() == "aggregates":
        return source_dir / "admin2"
    return source_dir / "aggregates" / "admin2"


def source_has_metrics(catalog_source: dict | None) -> bool:
    metrics = (catalog_source or {}).get("metrics") or {}
    if isinstance(metrics, dict) and metrics:
        return True
    if isinstance(metrics, list) and metrics:
        return True
    metric_count = (catalog_source or {}).get("metric_count")
    try:
        if int(metric_count or 0) > 0:
            return True
    except Exception:
        pass
    return False


def source_geojson_shape(catalog_source: dict | None) -> str:
    return str((catalog_source or {}).get("geojson_shape") or "").strip().lower()


def source_is_location_shape(catalog_source: dict | None) -> bool:
    return source_geometry_kind(catalog_source) == "entity" and source_geometry_subkind(catalog_source) == "point"


def source_has_aggregate_files(
    catalog_source: dict | None,
    *,
    data_root: Path,
) -> bool:
    files = (catalog_source or {}).get("files") or {}
    if not isinstance(files, dict):
        files = {}
    if any(key in files for key in ("yearly", "rolling_10y", "rolling_20y")):
        return True

    source_path = (catalog_source or {}).get("path")
    if not source_path:
        return False
    aggregate_dir = resolve_aggregate_admin2_dir(source_path, data_root=data_root)
    candidates = (
        aggregate_dir / "yearly.parquet",
        aggregate_dir / "rolling_10y.parquet",
        aggregate_dir / "rolling_20y.parquet",
    )
    return any(path.exists() for path in candidates)


def get_disaster_aggregate_metric_columns(
    catalog_source: dict | None,
    *,
    data_root: Path,
    parquet_columns_func,
) -> set[str]:
    """Return metric columns exposed by a disaster aggregate parquet family."""
    source_path = str((catalog_source or {}).get("path") or "").strip()
    if not source_path:
        return set()

    aggregate_dir = resolve_aggregate_admin2_dir(source_path, data_root=data_root)
    candidates = [
        aggregate_dir / "yearly.parquet",
        aggregate_dir / "rolling_10y.parquet",
        aggregate_dir / "rolling_20y.parquet",
    ]
    excluded = {"loc_id", "year", "window_end_year", "window_start_year", "window_years", "source"}
    metric_cols: set[str] = set()

    for candidate in candidates:
        try:
            if not candidate.exists():
                continue
            cols = parquet_columns_func(candidate)
            metric_cols.update(str(col) for col in cols if str(col) not in excluded)
        except Exception:
            continue

    return metric_cols


def source_supports_aggregate_mode(
    catalog_source: dict | None,
    *,
    source_has_aggregate_files_func,
) -> bool:
    if source_geometry_kind(catalog_source) == "entity":
        return False
    data_type = (catalog_source or {}).get("data_type")
    if isinstance(data_type, list):
        if "events" in data_type and "metrics" not in data_type:
            return False
    elif data_type == "events":
        return False
    return source_has_aggregate_files_func(catalog_source)


def source_supports_disaster_aggregates(
    source_id: str,
    *,
    get_source_from_catalog_func,
    is_cloud_mode_func,
    source_has_aggregate_files_func,
    resolve_aggregate_admin2_dir_func,
    parquet_columns_func,
    data_root: Path,
) -> bool:
    """Return whether a source exposes disaster aggregate parquet families."""
    catalog_source = get_source_from_catalog_func(source_id)
    if not catalog_source:
        return False

    if not is_cloud_mode_func():
        return source_has_aggregate_files_func(
            catalog_source,
            data_root=data_root,
        )

    files = (catalog_source or {}).get("files") or {}
    if not isinstance(files, dict):
        files = {}
    if any(key in files for key in ("yearly", "rolling_10y", "rolling_20y")):
        return True

    source_path = (catalog_source or {}).get("path")
    if not source_path:
        return False
    agg_dir = resolve_aggregate_admin2_dir_func(source_path, data_root=data_root)
    candidates = (
        agg_dir / "yearly.parquet",
        agg_dir / "rolling_10y.parquet",
        agg_dir / "rolling_20y.parquet",
    )
    for path in candidates:
        try:
            if parquet_columns_func(path):
                return True
        except Exception:
            continue
    return False


def apply_aggregate_query_hints(item: dict, query: str) -> None:
    item["mode"] = "aggregate"
    item.pop("event_file", None)

    if item.get("aggregate_use_rolling") is None and ("rolling" in query or "last 10 years" in query or "past 10 years" in query):
        item["aggregate_use_rolling"] = True
        item["aggregate_window_years"] = 10
    elif item.get("aggregate_use_rolling") is None and ("last 20 years" in query or "past 20 years" in query):
        item["aggregate_use_rolling"] = True
        item["aggregate_window_years"] = 20
    elif item.get("aggregate_use_rolling") is None and ("last 30 years" in query or "past 30 years" in query):
        item["aggregate_use_rolling"] = True
        item["aggregate_window_years"] = 30

    if "historically" in query:
        item["aggregate_all_years"] = True

    if "countries" in query or "country" in query:
        item["aggregate_rollup_level"] = "admin_0"
    elif "counties" in query or "county" in query:
        item["aggregate_rollup_level"] = "admin_2"
    elif not item.get("region") and not item.get("aggregate_rollup_level"):
        geo_terms = (
            "county", "counties", "state", "states", "province", "provinces",
            "district", "districts", "tract", "tracts", "admin_1", "admin_2", "admin_3",
        )
        if not any(term in query for term in geo_terms):
            item["aggregate_rollup_level"] = "admin_0"
