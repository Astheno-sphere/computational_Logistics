"""Shared aggregate-loading helpers extracted from the main executor."""

from __future__ import annotations

import re

import pandas as pd

from mapmover.runtime.geography_reference import canonicalize_loc_id


def _normalize_loc_id_like_token(value) -> str:
    text = canonicalize_loc_id(value)
    if not text:
        return ""
    if text.startswith("EEZ-") or re.fullmatch(r"X[A-Z0-9]{1,7}", text):
        return text

    parts = [segment for segment in text.split("-") if segment]
    if not parts or len(parts[0]) not in {2, 3} or not parts[0].isalpha():
        return ""

    for segment in parts[1:]:
        if segment.startswith("G") and segment[1:].isdigit():
            continue
        if segment.isdigit():
            continue
        if segment.isalnum() and len(segment) <= 5:
            continue
        return ""

    return text


def _normalize_loc_id_filter_values(values, *, translate_loc_id_to_geometry_id_func) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        bridged = translate_loc_id_to_geometry_id_func(text)
        for candidate in (bridged, text):
            candidate_text = str(candidate or "").strip()
            if candidate_text and candidate_text not in normalized:
                normalized.append(candidate_text)
    return normalized


def aggregate_metric_frame(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Aggregate a disaster metric frame to a coarser spatial level."""
    agg_map = {}
    for col in df.columns:
        if col in group_cols or col == "source":
            continue
        if col in {"year", "window_end_year"}:
            continue
        if col.startswith("max_"):
            agg_map[col] = "max"
        elif col.startswith("avg_"):
            agg_map[col] = "mean"
        elif col in {"event_count", "deaths", "injuries", "damage_usd", "damage_millions"}:
            agg_map[col] = "sum"
        elif col.startswith("total_"):
            agg_map[col] = "sum"
        elif col in {"years_observed"}:
            agg_map[col] = "max"
        elif col in {"window_start_year", "window_years"}:
            agg_map[col] = "first"
        else:
            if pd.api.types.is_numeric_dtype(df[col]):
                agg_map[col] = "sum"

    if not agg_map:
        return df[group_cols].drop_duplicates().reset_index(drop=True)

    out = df.groupby(group_cols, as_index=False).agg(agg_map)
    if "source" in df.columns:
        out["source"] = df["source"].iloc[0]
    return out


def infer_implicit_aggregate_rollup_level(item: dict, *, expand_region_func) -> str | None:
    """Infer an aggregate rollup level when the order did not state one."""
    if item.get("aggregate_rollup_level"):
        return None
    region = item.get("region")
    filters = item.get("filters") if isinstance(item.get("filters"), dict) else {}
    filter_loc_id = filters.get("loc_id")
    filter_loc_id_prefix = _normalize_loc_id_like_token(filters.get("loc_id_prefix"))
    if not region and filter_loc_id:
        return None
    if not region and filter_loc_id_prefix:
        return None
    if not region:
        if item.get("aggregate_all_years") or item.get("aggregate_use_rolling"):
            return "admin_0"
        year = item.get("year")
        year_start = item.get("year_start")
        year_end = item.get("year_end")
        if year_start is not None or year_end is not None:
            if year is None or year_start != year_end:
                return "admin_0"
        return None
    region_codes = expand_region_func(region)
    if len(region_codes) <= 1:
        return None

    normalized = [str(code) for code in region_codes if isinstance(code, str)]
    if not normalized:
        return None

    if all("-" not in code for code in normalized):
        return "admin_0"

    country_prefixes = {code.split("-")[0] for code in normalized if "-" in code}
    if len(country_prefixes) == 1 and all(code.count("-") >= 1 for code in normalized):
        return "admin_1"

    return None


def derive_event_metric_aggregate_data(
    source_id: str,
    item: dict,
    requested_metric: str,
    *,
    load_event_data_func,
) -> tuple[pd.DataFrame | None, dict | None]:
    """Fallback: derive a yearly country-level aggregate metric from raw events."""
    event_df, metadata = load_event_data_func(source_id)
    if event_df is None or event_df.empty:
        return None, None
    if requested_metric not in event_df.columns or "timestamp" not in event_df.columns:
        return None, None

    df = event_df.copy()
    timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df[timestamps.notna()].copy()
    if df.empty:
        return None, None
    df["year"] = timestamps[timestamps.notna()].dt.year.astype("Int64")
    df = df[df["year"].notna()].copy()
    if df.empty:
        return None, None

    df["loc_id"] = df["loc_id"].astype(str).str.split("-").str[0]
    df["event_count"] = 1

    group_cols = ["loc_id", "year"]
    agg_map = {requested_metric: "sum"}
    if requested_metric != "event_count":
        agg_map["event_count"] = "sum"
    out = df.groupby(group_cols, as_index=False).agg(agg_map)
    out["source"] = source_id

    fallback_metadata = dict(metadata or {})
    fallback_metadata["geographic_level"] = "admin_0"
    fallback_metadata["aggregate_parquet"] = "event_metric_fallback"
    return out, fallback_metadata


def load_disaster_aggregate_data_impl(
    source_id: str,
    item: dict,
    *,
    get_source_path_func,
    resolve_aggregate_admin2_dir_func,
    normalize_year_filters_func,
    parquet_columns_func,
    select_rows_func,
    is_cloud_mode_func,
    load_source_metadata_func,
    infer_implicit_aggregate_rollup_level_func,
    derive_event_metric_aggregate_data_func,
    aggregate_metric_frame_func,
    translate_loc_id_to_geometry_id_func,
    translate_geometry_id_to_local_id_func,
    path_to_uri_func,
    logger,
) -> tuple[pd.DataFrame | None, dict | None]:
    """Load disaster aggregate parquet data for aggregate/choropleth execution."""
    source_dir = get_source_path_func(source_id)
    agg_dir = resolve_aggregate_admin2_dir_func(source_dir)
    use_rolling = bool(item.get("aggregate_use_rolling"))
    requested_window = item.get("aggregate_window_years")

    candidates = []
    if use_rolling and requested_window:
        candidates.append(agg_dir / f"rolling_{int(requested_window)}y.parquet")
    if use_rolling:
        candidates.extend([agg_dir / "rolling_20y.parquet", agg_dir / "rolling_10y.parquet"])
    candidates.append(agg_dir / "yearly.parquet")
    # Some sources (for example FEMA county-year declarations) are already
    # canonical geographic aggregates and intentionally do not duplicate that
    # parquet into ``aggregates/admin2/yearly.parquet``.  An explicit aggregate
    # order should be able to roll up that canonical source rather than silently
    # falling back to the ordinary annual/timeline loader.
    canonical_candidate = source_dir / f"{source_id}.parquet"
    if canonical_candidate not in candidates:
        candidates.append(canonical_candidate)

    parquet_path = None
    df = None
    last_error = None
    year, year_start, year_end = normalize_year_filters_func(item)
    region = item.get("region")
    filters = item.get("filters") if isinstance(item.get("filters"), dict) else {}
    filter_loc_id_prefix = str(filters.get("loc_id_prefix") or "").strip()
    filter_loc_id = filters.get("loc_id")
    for candidate in candidates:
        if parquet_path is not None:
            break
        if not is_cloud_mode_func() and not candidate.exists():
            continue
        try:
            exact_filters = {}
            compare_filters = []
            starts_with_filters = {}
            available_cols = parquet_columns_func(candidate)
            aggregate_year_col = "year" if "year" in available_cols else ("window_end_year" if "window_end_year" in available_cols else None)
            if aggregate_year_col:
                if year is not None:
                    exact_filters[aggregate_year_col] = year
                elif year_start is not None and year_end is not None:
                    compare_filters.extend(
                        [
                            (aggregate_year_col, ">=", year_start),
                            (aggregate_year_col, "<=", year_end),
                        ]
                    )
            if "loc_id" in available_cols:
                normalized_region_prefix = _normalize_loc_id_like_token(region)
                if normalized_region_prefix:
                    starts_with_filters["loc_id"] = translate_loc_id_to_geometry_id_func(normalized_region_prefix)
                elif filter_loc_id_prefix:
                    starts_with_filters["loc_id"] = translate_loc_id_to_geometry_id_func(filter_loc_id_prefix)
                if filter_loc_id:
                    loc_id_values = _normalize_loc_id_filter_values(
                        [filter_loc_id] if not isinstance(filter_loc_id, (list, tuple, set)) else list(filter_loc_id),
                        translate_loc_id_to_geometry_id_func=translate_loc_id_to_geometry_id_func,
                    )
                    if loc_id_values:
                        if len(loc_id_values) == 1:
                            exact_filters["loc_id"] = loc_id_values[0]
                        else:
                            maybe_df = select_rows_func(
                                candidate,
                                exact_filters=exact_filters or None,
                                in_filters={"loc_id": loc_id_values},
                                compare_filters=compare_filters or None,
                                starts_with_filters=starts_with_filters or None,
                            )
                            if maybe_df.empty and candidate.exists():
                                maybe_df = pd.read_parquet(candidate)
                                maybe_df = maybe_df[maybe_df["loc_id"].astype(str).isin(loc_id_values)]
                            parquet_path = candidate
                            df = maybe_df
                            continue
            maybe_df = select_rows_func(
                candidate,
                exact_filters=exact_filters or None,
                compare_filters=compare_filters or None,
                starts_with_filters=starts_with_filters or None,
            )
            if maybe_df.empty and candidate.exists():
                maybe_df = pd.read_parquet(candidate)
            parquet_path = candidate
            df = maybe_df
        except Exception as exc:
            last_error = exc
            continue

    if parquet_path is None or df is None:
        if last_error:
            logger.warning(f"[aggregate] failed to load aggregate parquet for {source_id}: {last_error}")
        return None, None

    metadata = load_source_metadata_func(source_id) or {}
    metadata = dict(metadata)
    implicit_rollup_level = infer_implicit_aggregate_rollup_level_func(item)
    rollup_level = item.get("aggregate_rollup_level") or implicit_rollup_level or "admin_2"
    metadata["geographic_level"] = rollup_level
    metadata["aggregate_parquet"] = str(parquet_path)

    if "window_end_year" in df.columns and "year" not in df.columns:
        df = df.rename(columns={"window_end_year": "year"})

    requested_metric = str(item.get("metric") or "").strip()
    if requested_metric and requested_metric not in df.columns:
        fallback_df, fallback_metadata = derive_event_metric_aggregate_data_func(source_id, item, requested_metric)
        if fallback_df is not None and fallback_metadata is not None:
            df = fallback_df
            metadata = fallback_metadata
            rollup_level = "admin_0"
            logger.info(
                f"[aggregate] fallback {source_id}: derived metric='{requested_metric}' from event rows at admin_0"
            )

    year, year_start, year_end = normalize_year_filters_func(item)
    if "year" in df.columns and use_rolling and year is None and year_start is None and year_end is None:
        df = df.sort_values(["loc_id", "year"]).groupby("loc_id", as_index=False).tail(1)

    if item.get("aggregate_all_years") and "year" in df.columns:
        df = aggregate_metric_frame_func(df, ["loc_id"])

    if rollup_level == "admin_0" and "loc_id" in df.columns:
        df = df.copy()
        df["loc_id"] = df["loc_id"].astype(str).str.split("-").str[0]
        group_cols = ["loc_id"]
        if "year" in df.columns:
            group_cols.append("year")
        df = aggregate_metric_frame_func(df, group_cols)
        metadata["geographic_level"] = "admin_0"
    elif rollup_level == "admin_1" and "loc_id" in df.columns:
        df = df.copy()
        df["loc_id"] = (
            df["loc_id"]
            .astype(str)
            .map(translate_geometry_id_to_local_id_func)
            .str.split("-")
            .str[:2]
            .str.join("-")
        )
        group_cols = ["loc_id"]
        if "year" in df.columns:
            group_cols.append("year")
        df = aggregate_metric_frame_func(df, group_cols)
        metadata["geographic_level"] = "admin_1"

    logger.info(
        f"[aggregate] load {source_id}: path={path_to_uri_func(parquet_path) if is_cloud_mode_func() else parquet_path} "
        f"rows={len(df)} level={metadata.get('geographic_level')}"
    )
    return df, metadata
