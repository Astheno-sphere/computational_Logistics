"""Shared event source/path/loading helpers extracted from the main executor."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from mapmover.runtime.filter_primitives import (
    partition_region_filter_codes,
    resolve_exact_id_filter_field,
)


def resolve_event_source_id(
    source_id: str,
    *,
    load_source_metadata_func,
    load_catalog_func,
) -> str:
    """Resolve a human-facing event pack alias to its canonical event source id."""
    normalized = str(source_id or "").strip()
    if not normalized:
        return normalized
    if load_source_metadata_func(normalized) is not None:
        return normalized

    catalog = load_catalog_func() or {}
    event_sources = [
        str(src.get("source_id") or "").strip()
        for src in catalog.get("sources", [])
        if str(src.get("pack_id") or "").strip() == normalized
        and str(src.get("data_type") or "").strip() == "events"
    ]
    event_sources = [source for source in event_sources if source]
    if len(event_sources) == 1:
        return event_sources[0]
    return normalized


def resolve_event_parquet_path_for_source(
    source_id: str,
    event_file_key: str = "events",
    *,
    get_source_path_func,
    load_source_metadata_func,
    is_cloud_mode_func,
) -> tuple[Path, dict]:
    """Resolve event parquet path from source metadata without loading data."""
    source_dir = get_source_path_func(source_id)
    metadata = load_source_metadata_func(source_id)
    if metadata is None:
        raise ValueError(f"Could not load metadata for {source_id}")

    files_section = metadata.get("files")
    files_info = files_section if isinstance(files_section, dict) else {}
    file_info = files_info.get(event_file_key)
    if not isinstance(file_info, dict):
        file_info = None

    if not file_info:
        fallback_names = [
            f"{event_file_key}.parquet",
            "events.parquet",
            "fires.parquet",
            "positions.parquet",
            "storms.parquet",
        ]
        for name in fallback_names:
            candidate = source_dir / name
            if is_cloud_mode_func() or candidate.exists():
                return candidate, metadata
        if not is_cloud_mode_func():
            parquet_candidates = sorted(source_dir.glob("*.parquet"))
            for candidate in parquet_candidates:
                if candidate.name in ("all_countries.parquet", "all_regions.parquet"):
                    continue
                return candidate, metadata
        raise ValueError(f"No event file '{event_file_key}' found in {source_dir}")

    filename = file_info.get("name") or file_info.get("filename")
    if not filename:
        raise ValueError(f"No filename specified for '{event_file_key}' in {source_dir}")

    parquet_path = source_dir / filename
    if not is_cloud_mode_func() and not parquet_path.exists():
        raise ValueError(f"Event file not found: {parquet_path}")
    return parquet_path, metadata


def load_event_data(
    source_id: str,
    event_file_key: str = "events",
    *,
    get_source_path_func,
    load_source_metadata_func,
    is_cloud_mode_func,
    select_rows_func,
) -> tuple[pd.DataFrame, dict]:
    """Load event-level parquet data for a source."""
    parquet_path, metadata = resolve_event_parquet_path_for_source(
        source_id,
        event_file_key,
        get_source_path_func=get_source_path_func,
        load_source_metadata_func=load_source_metadata_func,
        is_cloud_mode_func=is_cloud_mode_func,
    )
    df = select_rows_func(parquet_path)
    if df.empty:
        df = pd.read_parquet(parquet_path)
    return df, metadata


def load_event_data_duckdb(
    source_id: str,
    item: dict,
    event_file_key: str = "events",
    *,
    resolve_event_parquet_path_func,
    parquet_columns_func,
    normalize_year_filters_func,
    normalize_sort_spec_func,
    expand_region_func,
    load_iso_codes_func,
    load_usa_admin_func,
    append_duckdb_filter_clause_func,
    path_to_uri_func,
    quote_ident_func,
    run_df_func,
    default_event_limit: int,
    max_event_limit: int,
) -> tuple[pd.DataFrame, dict]:
    """Load and filter event data with DuckDB for first-pass migration sources."""
    parquet_path, metadata = resolve_event_parquet_path_func(source_id, event_file_key)
    available_cols = parquet_columns_func(parquet_path)

    region = item.get("region")
    year, year_start, year_end = normalize_year_filters_func(item)
    filters = item.get("filters", {}) or {}
    requested_limit = item.get("limit")
    sort_spec = normalize_sort_spec_func(item.get("sort"))
    time_col = "year" if "year" in available_cols else ("timestamp" if "timestamp" in available_cols else None)
    loc_id_col = "loc_id" if "loc_id" in available_cols else None

    where_clauses = []
    params = [path_to_uri_func(parquet_path)]

    if year_start is not None and year_end is not None:
        if time_col == "year":
            where_clauses.append('"year" BETWEEN ? AND ?')
            params.extend([year_start, year_end])
        elif time_col:
            where_clauses.append(f"year({quote_ident_func(time_col)}) BETWEEN ? AND ?")
            params.extend([year_start, year_end])
    elif year is not None:
        if time_col == "year":
            where_clauses.append('"year" = ?')
            params.append(year)
        elif time_col:
            where_clauses.append(f"year({quote_ident_func(time_col)}) = ?")
            params.append(year)

    region_codes = expand_region_func(region)
    if region_codes:
        loc_prefixes, country_codes = partition_region_filter_codes(region_codes)
        us_state_prefixes = [code for code in loc_prefixes if code.startswith("USA-")]
        region_parts = []

        if loc_id_col:
            for prefix in sorted(loc_prefixes):
                region_parts.append(f"{quote_ident_func(loc_id_col)} LIKE ?")
                params.append(f"{prefix}%")

            if country_codes:
                placeholders = ", ".join("?" for _ in country_codes)
                region_parts.append(f"split_part({quote_ident_func(loc_id_col)}, '-', 1) IN ({placeholders})")
                params.extend(country_codes)

        country_name_cols = [col for col in ("country", "country_name") if col in available_cols]
        if country_codes and country_name_cols:
            iso3_to_name = load_iso_codes_func().get("iso3_to_name", {})
            country_names = sorted(
                {
                    str(iso3_to_name.get(code, "")).strip().upper()
                    for code in country_codes
                    if str(iso3_to_name.get(code, "")).strip()
                }
            )
            for col in country_name_cols:
                if country_names:
                    placeholders = ", ".join("?" for _ in country_names)
                    region_parts.append(f"upper({quote_ident_func(col)}) IN ({placeholders})")
                    params.extend(country_names)

        state_abbrevs = load_usa_admin_func().get("state_abbreviations", {})
        state_name_cols = [col for col in ("state", "state_name", "admin1_name") if col in available_cols]
        state_text_cols = [col for col in ("place", "location", "name", "title") if col in available_cols]
        for prefix in us_state_prefixes:
            state_abbrev = prefix.split("-")[1]
            state_name = str(state_abbrevs.get(state_abbrev, "")).strip().upper()
            if state_name:
                for col in state_name_cols:
                    region_parts.append(f"upper({quote_ident_func(col)}) = ?")
                    params.append(state_name)
                for col in state_text_cols:
                    region_parts.append(f"upper({quote_ident_func(col)}) LIKE ?")
                    params.append(f"%{state_name}%")

        if region_parts:
            where_clauses.append("(" + " OR ".join(region_parts) + ")")

    for field, value in filters.items():
        resolved_field = resolve_exact_id_filter_field(
            field,
            available_cols,
            metadata=metadata,
            event_type=str(metadata.get("event_type") or ""),
        )
        append_duckdb_filter_clause_func(where_clauses, params, available_cols, resolved_field, value)

    sql = "SELECT * FROM read_parquet(?)"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    limit = min(requested_limit or default_event_limit, max_event_limit)
    sort_col = None
    sort_order = "DESC"
    if sort_spec:
        requested_sort_col = str(sort_spec.get("by") or "").strip()
        if requested_sort_col in available_cols:
            sort_col = requested_sort_col
            sort_order = "ASC" if str(sort_spec.get("order", "desc")).lower() == "asc" else "DESC"
        elif requested_sort_col in {"date", "time"} and "timestamp" in available_cols:
            sort_col = "timestamp"
            sort_order = "ASC" if str(sort_spec.get("order", "desc")).lower() == "asc" else "DESC"
    if not sort_col:
        sig_col = metadata.get("significance_column")
        if sig_col and sig_col in available_cols:
            sort_col = sig_col
            sort_order = "DESC"
    if sort_col:
        sql += f" ORDER BY {quote_ident_func(sort_col)} {sort_order} NULLS LAST"
    sql += " LIMIT ?"
    params.append(limit)

    df = run_df_func(sql, params)
    return df, metadata
