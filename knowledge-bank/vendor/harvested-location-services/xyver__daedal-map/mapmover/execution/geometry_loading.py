"""Shared geometry-loading helpers."""

from __future__ import annotations

from typing import Optional

import pandas as pd


def has_geometry_data_type(data_type) -> bool:
    """Check if data_type includes geometry."""
    if data_type is None:
        return False
    if isinstance(data_type, list):
        return "geometry" in data_type
    return data_type == "geometry"


def find_geometry_source_for_level(
    geo_level: str,
    *,
    load_catalog_func,
    has_geometry_data_type_func,
    scope: str = None,
) -> Optional[dict]:
    """Find a catalog source that provides geometry for a geographic level."""
    catalog = load_catalog_func()
    for src in catalog.get("sources", []):
        if src.get("geographic_level") != geo_level:
            continue
        if not has_geometry_data_type_func(src.get("data_type")):
            continue
        if scope and src.get("scope", "").lower() != scope.lower():
            continue
        return src
    return None


def load_geometry_from_source(
    source_info: dict,
    *,
    data_root,
    select_columns_from_parquet_func,
    logger,
    filter_regions: set = None,
) -> Optional[pd.DataFrame]:
    """Load geometry dataframe from a catalog source, optionally filtered by region."""
    source_path = source_info.get("path")
    if not source_path:
        return None

    full_path = data_root / source_path
    parquet_files = list(full_path.glob("*.parquet")) if full_path.is_dir() else []

    if not parquet_files:
        logger.warning(f"No parquet files found in {full_path}")
        return None

    parquet_path = parquet_files[0]
    logger.info(f"Loading geometry from dual source: {parquet_path}")

    try:
        columns = ["loc_id", "name", "geometry", "parent_id"]
        df = select_columns_from_parquet_func(parquet_path, columns)
        if df.empty:
            df = pd.read_parquet(parquet_path, columns=columns)

        if filter_regions and "parent_id" in df.columns:
            prefixes = tuple(f"{region}-" for region in filter_regions)
            mask = df["parent_id"].str.startswith(prefixes, na=False) | df["parent_id"].isin(filter_regions)
            df = df[mask]
            logger.info(f"Filtered to {len(df)} features matching regions: {filter_regions}")

        cols = ["loc_id", "name", "geometry", "parent_id"]
        available_cols = [col for col in cols if col in df.columns]
        if "loc_id" not in available_cols or "geometry" not in available_cols:
            logger.warning(f"Missing required columns in {parquet_path}")
            return None
        return df[available_cols]
    except Exception as exc:
        logger.error(f"Error loading geometry from {parquet_path}: {exc}")
        return None
