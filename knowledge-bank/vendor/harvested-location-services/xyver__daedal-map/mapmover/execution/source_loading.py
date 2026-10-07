"""Shared source path and parquet-loading helpers extracted from the executor."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import os

from mapmover.catalog_surface import get_catalog_surface_override
from mapmover.runtime.geography_reference import translate_loc_id_to_geometry_id
from mapmover.runtime.result_cap import build_cap_info_from_counts


def _allow_local_source_fallback() -> bool:
    override = get_catalog_surface_override()
    if override in {"published", "wip"}:
        return override == "wip"
    raw = str(os.environ.get("USE_WIP_CATALOG", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def get_source_path(
    source_id: str,
    *,
    load_catalog_func,
    data_root: Path,
) -> Path:
    """Get the full local/cache path to a source directory using catalog metadata."""
    catalog = load_catalog_func() or {}
    for source in catalog.get("sources", []):
        if source.get("source_id") == source_id:
            source_path = source.get("path", f"global/{source_id}")
            return data_root / source_path
    return data_root / "global" / source_id


def candidate_parquet_paths(
    source_dir: Path,
    metadata: dict,
    preferred_file: str | None = None,
) -> list[Path]:
    """Return ordered parquet candidates for a source."""
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add_candidate(name: str | None) -> None:
        filename = str(name or "").strip()
        # Per-order display tables are data files, not paths.  Keeping this to a
        # basename prevents an order from escaping its catalogued source folder.
        if (
            not filename
            or not filename.endswith(".parquet")
            or Path(filename).name != filename
        ):
            return
        if filename in seen:
            return
        seen.add(filename)
        candidates.append(source_dir / filename)

    _add_candidate(preferred_file)

    files_section = metadata.get("files")
    if isinstance(files_section, dict):
        for info in files_section.values():
            if not isinstance(info, dict):
                continue
            _add_candidate(info.get("name") or info.get("filename"))

    primary_files = metadata.get("primary_files")
    if isinstance(primary_files, list):
        for entry in primary_files:
            _add_candidate(entry)

    for key in ("primary_file", "parquet_file", "data_file", "data_filename", "filename", "file_name"):
        _add_candidate(metadata.get(key))

    coverage = metadata.get("geographic_coverage", {}) or {}
    country_code = str(coverage.get("country", "")).strip().upper()
    if country_code:
        _add_candidate(f"{country_code}.parquet")

    source_parts = source_dir.parts
    if "countries" in source_parts:
        try:
            countries_idx = source_parts.index("countries")
            inferred_country = source_parts[countries_idx + 1].upper()
            _add_candidate(f"{inferred_country}.parquet")
        except Exception:
            pass

    for fallback_name in ("all_countries.parquet", "GLOBAL.parquet", "data.parquet"):
        _add_candidate(fallback_name)

    return candidates


def _loc_id_prefix_candidates(loc_id_prefix: str | None, metadata: dict | None = None) -> list[str | None]:
    """Return ordered namespace-aware prefix candidates for parquet pushdown.

    Runtime queries often arrive in country-local loc_id form (`USA-CA`), while
    some globally aggregated packs are stored directly on the canonical
    GeoBoundaries spine (`USA-G123331`). Try the canonical geometry translation
    first, then fall back to the original local prefix if different.
    """
    if loc_id_prefix is None:
        return [None]

    original = str(loc_id_prefix).strip()
    if not original:
        return [None]

    candidates: list[str | None] = []
    translated = translate_loc_id_to_geometry_id(original)
    admin_levels = []
    if isinstance(metadata, dict):
        coverage = metadata.get("geographic_coverage") if isinstance(metadata.get("geographic_coverage"), dict) else {}
        admin_levels = coverage.get("admin_levels") if isinstance(coverage.get("admin_levels"), list) else []
    try:
        max_admin_level = max(int(level) for level in admin_levels)
    except (TypeError, ValueError):
        max_admin_level = None

    county_bridge_candidate = ""
    original_upper = str(original).strip().upper()
    if max_admin_level is not None and max_admin_level > 2 and original_upper.startswith("USA-"):
        parts = original_upper.split("-")
        if len(parts) == 3 and parts[2].isdigit() and len(parts[2]) > 3:
            county_bridge_candidate = f"{parts[0]}-{parts[1]}-{parts[2][-3:]}"

    prefer_local_first = (
        translated != original
        and max_admin_level is not None
        and max_admin_level > 2
    )
    if prefer_local_first:
        ordered_candidates = (county_bridge_candidate, original, translated)
    else:
        ordered_candidates = (translated, county_bridge_candidate, original)

    for candidate in ordered_candidates:
        value = str(candidate).strip() if candidate is not None else ""
        if not value:
            continue
        if value not in candidates:
            candidates.append(value)
    return candidates or [original]


def _normalize_loc_id_filter_values(values) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        bridged = translate_loc_id_to_geometry_id(text)
        for candidate in (bridged, text):
            candidate_text = str(candidate or "").strip()
            if candidate_text and candidate_text not in normalized:
                normalized.append(candidate_text)
    return normalized


def load_source_data(
    source_id: str,
    *,
    year: int | None = None,
    loc_id_prefix: str | None = None,
    exact_filters: dict | None = None,
    in_filters: dict | None = None,
    compare_filters: list[tuple[str, str, object]] | None = None,
    columns: list[str] | None = None,
    prefer_latest_year_when_unspecified: bool = False,
    requested_limit: int | None = None,
    data_file: str | None = None,
    get_source_path_func,
    load_source_metadata_func,
    candidate_parquet_paths_func,
    is_cloud_mode_func,
    path_to_uri_func,
    select_rows_func,
    count_rows_func,
    logger,
) -> tuple[pd.DataFrame, dict]:
    """Load parquet and metadata for a source with optional pushed-down filters."""
    source_dir = get_source_path_func(source_id)
    metadata = load_source_metadata_func(source_id)
    if metadata is None:
        raise ValueError(f"Could not load metadata for {source_id}")

    selected_columns = [str(value).strip() for value in (columns or []) if str(value).strip()]
    metrics_section = metadata.get("metrics") if isinstance(metadata.get("metrics"), dict) else {}
    selected_columns.extend(str(metric_id).strip() for metric_id in metrics_section.keys() if str(metric_id).strip())
    selected_columns.extend(str(field).strip() for field in (exact_filters or {}).keys() if str(field).strip())
    selected_columns.extend(str(field).strip() for field in (in_filters or {}).keys() if str(field).strip())
    selected_columns.extend(str(field).strip() for field, _op, _value in (compare_filters or []) if str(field).strip())
    selected_columns.extend(["loc_id", "geo_level", "year", "timestamp", "date", "time", "month", "week"])
    selected_columns.extend(["lat", "latitude", "centroid_lat", "lon", "longitude", "centroid_lon"])
    selected_columns.extend(["end_latitude", "end_longitude"])
    selected_columns = list(dict.fromkeys(selected_columns))

    metadata = dict(metadata or {})
    resolved_exact_filters = dict(exact_filters or {})
    resolved_in_filters = dict(in_filters or {})
    if "loc_id" in resolved_exact_filters:
        loc_id_candidates = _normalize_loc_id_filter_values([resolved_exact_filters.get("loc_id")])
        resolved_exact_filters.pop("loc_id", None)
        if loc_id_candidates:
            resolved_in_filters["loc_id"] = list(
                dict.fromkeys(
                    [*loc_id_candidates, *(resolved_in_filters.get("loc_id") or [])]
                )
            )
    elif "loc_id" in resolved_in_filters:
        resolved_in_filters["loc_id"] = _normalize_loc_id_filter_values(resolved_in_filters.get("loc_id") or [])

    if year is not None:
        resolved_exact_filters["year"] = year
    elif prefer_latest_year_when_unspecified:
        # Time-before-location: when no year is requested, default to the latest
        # year and push it down BEFORE the row cap, so a broad query loads all
        # regions for the most recent year rather than an arbitrary cap-window
        # slice of the full history (which, on a loc_id-sorted table, can miss
        # whole zone families like the X* ocean basins entirely). This applies
        # to every temporal granularity, not just yearly: a monthly/daily source
        # (e.g. ocean_sst) must also collapse to its latest year first so the
        # location filter that runs afterward sees the full zone set.
        # See live_source_qa_checklist.md (time-before-location / cap-window trap).
        temporal = metadata.get("temporal_coverage") if isinstance(metadata.get("temporal_coverage"), dict) else {}
        granularity = str(temporal.get("granularity") or temporal.get("frequency") or "").strip().lower()
        # Any declared temporal granularity qualifies (yearly, monthly, daily,
        # 6h, ...): a no-year query on a time-series source should collapse to
        # the latest year first. Enumerating every granularity string is
        # fragile -- auto-detected values include "6h", "6-hourly", etc. -- so
        # gate on "this is a temporal source" (granularity declared and a
        # year-extractable end) rather than a fixed whitelist.
        if granularity:
            raw_end = temporal.get("end")
            if raw_end is not None:
                text = str(raw_end).strip()
                if len(text) >= 4 and text[:4].isdigit():
                    resolved_exact_filters.setdefault("year", int(text[:4]))
    prefix_candidates = _loc_id_prefix_candidates(loc_id_prefix, metadata)

    runtime_block = metadata.get("runtime") if isinstance(metadata.get("runtime"), dict) else {}
    try:
        default_render_cap = int(runtime_block.get("default_render_cap") or 5000)
    except (TypeError, ValueError):
        default_render_cap = 5000
    if default_render_cap <= 0:
        default_render_cap = 5000
    try:
        max_render_cap = int(runtime_block.get("max_render_cap") or 5000)
    except (TypeError, ValueError):
        max_render_cap = 5000
    if max_render_cap <= 0:
        max_render_cap = 5000
    pushdown_cap = min(default_render_cap, max_render_cap)
    if requested_limit is not None:
        try:
            requested_limit_int = int(requested_limit)
        except (TypeError, ValueError):
            requested_limit_int = 0
        if requested_limit_int > 0:
            pushdown_cap = min(requested_limit_int, max_render_cap)
    pushdown_limit = pushdown_cap + 1 if pushdown_cap > 0 else None

    runtime_block_for_file = metadata.get("runtime") if isinstance(metadata.get("runtime"), dict) else {}
    display_data_file = runtime_block_for_file.get("display_data_file")
    parquet_candidates = candidate_parquet_paths_func(
        source_dir,
        metadata,
        # A source can declare a materialized display table for values whose
        # sparse storage would otherwise be mistaken for an unknown value. An
        # explicit order file remains an escape hatch for provenance/audit use.
        preferred_file=data_file or display_data_file,
    )
    if is_cloud_mode_func():
        if not parquet_candidates:
            raise ValueError(f"Cannot determine parquet path for {source_id} in S3 mode")

        last_df = pd.DataFrame()
        for parquet_path in parquet_candidates:
            for prefix_candidate in prefix_candidates:
                starts_with_filters = {"loc_id": prefix_candidate} if prefix_candidate else {}
                if _allow_local_source_fallback() and parquet_path.exists():
                    logger.info(
                        f"[S3->LOCAL] load_source_data({source_id}): using local fallback={parquet_path} year={year} prefix={prefix_candidate}"
                    )
                else:
                    uri = path_to_uri_func(parquet_path)
                    logger.info(f"[S3] load_source_data({source_id}): trying uri={uri} year={year} prefix={prefix_candidate}")
                df = select_rows_func(
                    parquet_path,
                    columns=selected_columns or None,
                    exact_filters=resolved_exact_filters or None,
                    in_filters=resolved_in_filters or None,
                    compare_filters=compare_filters or None,
                    starts_with_filters=starts_with_filters or None,
                    limit=pushdown_limit,
                )
                if pushdown_cap > 0 and len(df) > pushdown_cap:
                    available_rows = count_rows_func(
                        parquet_path,
                        exact_filters=resolved_exact_filters or None,
                        in_filters=resolved_in_filters or None,
                        compare_filters=compare_filters or None,
                        starts_with_filters=starts_with_filters or None,
                    )
                    df = df.head(pushdown_cap)
                    metadata["_runtime_prefilter_cap_info"] = build_cap_info_from_counts(
                        returned_rows=len(df),
                        available_rows=max(available_rows, len(df) + 1),
                        cap_value=pushdown_cap,
                        cap_reason="runtime.default_render_cap",
                    )
                logger.info(
                    f"[S3] load_source_data({source_id}): candidate={parquet_path.name} prefix={prefix_candidate} rows={len(df)}"
                )
                last_df = df
                if not df.empty:
                    return df, metadata
        df = last_df
    else:
        parquet_files = list(source_dir.glob("*.parquet"))
        if not parquet_files:
            raise ValueError(f"No parquet file found for {source_id} in {source_dir}")

        parquet_path = None
        for candidate in parquet_candidates:
            if candidate.exists():
                parquet_path = candidate
                break
        if parquet_path is None:
            parquet_path = parquet_files[0]

        df = pd.DataFrame()
        for prefix_candidate in prefix_candidates:
            starts_with_filters = {"loc_id": prefix_candidate} if prefix_candidate else {}
            df = select_rows_func(
                parquet_path,
                columns=selected_columns or None,
                exact_filters=resolved_exact_filters or None,
                in_filters=resolved_in_filters or None,
                compare_filters=compare_filters or None,
                starts_with_filters=starts_with_filters or None,
                limit=pushdown_limit,
            )
            if pushdown_cap > 0 and len(df) > pushdown_cap:
                available_rows = count_rows_func(
                    parquet_path,
                    exact_filters=resolved_exact_filters or None,
                    in_filters=resolved_in_filters or None,
                    compare_filters=compare_filters or None,
                    starts_with_filters=starts_with_filters or None,
                )
                df = df.head(pushdown_cap)
                metadata["_runtime_prefilter_cap_info"] = build_cap_info_from_counts(
                    returned_rows=len(df),
                    available_rows=max(available_rows, len(df) + 1),
                    cap_value=pushdown_cap,
                    cap_reason="runtime.default_render_cap",
                )
            if not df.empty:
                break
        if df.empty and not resolved_exact_filters and not starts_with_filters and not in_filters and not compare_filters:
            df = pd.read_parquet(parquet_path, columns=selected_columns or None)

    return df, metadata
