"""Shared region-based identifier selection helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def get_source_from_catalog(source_id: str, *, load_catalog_func) -> dict:
    """Get source info from catalog by source_id."""
    catalog = load_catalog_func()
    if not catalog:
        return {}
    for source in catalog.get("sources", []):
        if source.get("source_id") == source_id:
            return source
    return {}


def find_source_files(source_id: str, *, get_source_from_catalog_func, data_root) -> list:
    """Find parquet files for a source_id."""
    source = get_source_from_catalog_func(source_id)
    if not source:
        return []

    source_path = source.get("path")
    if not source_path:
        return []

    full_path = data_root / source_path
    if full_path.is_dir():
        return list(full_path.glob("*.parquet"))
    parquet_path = full_path.with_suffix(".parquet")
    if parquet_path.exists():
        return [parquet_path]
    return []


def get_event_ids_by_region(
    source_id: str,
    regions: list,
    *,
    find_source_files_func,
    duckdb_can_query_events_func,
    select_event_ids_by_regions_func,
    select_columns_from_parquet_func,
    logger,
) -> list:
    """Query source data to get event_ids matching region prefixes."""
    try:
        parquet_files = find_source_files_func(source_id)
        if not parquet_files:
            return []

        if duckdb_can_query_events_func(source_id):
            event_ids = select_event_ids_by_regions_func(parquet_files[0], regions)
            logger.info(f"Found {len(event_ids)} event_ids matching regions {regions} in {source_id} via DuckDB")
            return event_ids

        columns = ["loc_id", "parent_id"]
        df = select_columns_from_parquet_func(parquet_files[0], columns)
        if df.empty:
            df = pd.read_parquet(parquet_files[0], columns=columns)

        if "event_id" not in df.columns:
            return []

        if "loc_id" in df.columns and regions:
            prefixes = tuple(f"{region}-" for region in regions)
            region_set = set(regions)
            mask = df["loc_id"].str.startswith(prefixes, na=False) | df["loc_id"].isin(region_set)
            matching = df[mask]
        else:
            matching = df

        event_ids = matching["event_id"].tolist()
        logger.info(f"Found {len(event_ids)} event_ids matching regions {regions} in {source_id}")
        return event_ids
    except Exception as exc:
        logger.error(f"Error getting event_ids by region: {exc}")
        return []


def get_loc_ids_by_region(
    source_id: str,
    regions: list,
    *,
    find_source_files_func,
    select_columns_from_parquet_func,
    logger,
) -> list:
    """Query source data to get loc_ids matching parent_id region prefixes."""
    try:
        parquet_files = find_source_files_func(source_id)
        if not parquet_files:
            logger.warning(f"No parquet files found for source: {source_id}")
            return []

        columns = ["loc_id", "parent_id"]
        df = select_columns_from_parquet_func(parquet_files[0], columns)
        if df.empty:
            df = pd.read_parquet(parquet_files[0], columns=columns)

        if "parent_id" not in df.columns:
            logger.warning(f"No parent_id column in {source_id}")
            return []

        prefixes = tuple(f"{region}-" for region in regions)
        region_set = set(regions)
        mask = df["parent_id"].str.startswith(prefixes, na=False) | df["parent_id"].isin(region_set)
        matching = df[mask]

        loc_ids = matching["loc_id"].tolist() if "loc_id" in matching.columns else []
        logger.info(f"Found {len(loc_ids)} loc_ids matching regions {regions} in {source_id}")
        return loc_ids
    except Exception as exc:
        logger.error(f"Error getting loc_ids by region: {exc}")
        return []
