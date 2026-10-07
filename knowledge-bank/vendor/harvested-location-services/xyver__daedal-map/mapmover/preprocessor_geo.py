"""Geometry and parquet-backed lookup helpers extracted from preprocessor.py."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from .foundation_helpers import load_global_country_display_frame
_PARQUET_NAMES_CACHE = {}
_PARQUET_SORTED_NAMES_CACHE = {}


def get_countries_in_viewport(bounds: dict, *, geometry_dir: Path, logger) -> list:
    """Get ISO3 codes visible in a viewport from stored Admin0 bounding boxes.

    This reads four numeric columns and never touches a polygon, so it uses the
    bounded Display bank rather than the exact one. The exact bank also merges
    its supplemental territories at runtime with null bboxes, which silently
    dropped Hong Kong, Macao, Puerto Rico, Gibraltar, Jersey, Svalbard, and the
    rest of that set from every viewport.
    """
    if not bounds:
        return []
    df = load_global_country_display_frame()
    if df is None or df.empty:
        return []
    try:
        v_west = bounds.get("west", -180)
        v_south = bounds.get("south", -90)
        v_east = bounds.get("east", 180)
        v_north = bounds.get("north", 90)
        if "bbox_min_lon" in df.columns:
            mask = (
                (df["bbox_max_lon"] >= v_west)
                & (df["bbox_min_lon"] <= v_east)
                & (df["bbox_max_lat"] >= v_south)
                & (df["bbox_min_lat"] <= v_north)
            )
            df = df[mask]
        return df["loc_id"].tolist() if "loc_id" in df.columns else []
    except Exception as e:
        logger.warning(f"Error getting countries in viewport: {e}")
        return []


def load_parquet_names(iso3: str, *, geometry_dir: Path, logger) -> dict:
    """Load location names from a country's parquet file."""
    global _PARQUET_NAMES_CACHE
    if iso3 in _PARQUET_NAMES_CACHE:
        return _PARQUET_NAMES_CACHE[iso3]

    parquet_file = geometry_dir / f"{iso3}.parquet"
    if not parquet_file.exists():
        _PARQUET_NAMES_CACHE[iso3] = {}
        return {}

    try:
        import pandas as pd
        from .duckdb_helpers import duckdb_available, select_columns_from_parquet

        columns = ["loc_id", "name", "parent_id", "admin_level"]
        if duckdb_available():
            df = select_columns_from_parquet(parquet_file, columns)
            if df.empty:
                df = pd.read_parquet(parquet_file, columns=columns)
        else:
            df = pd.read_parquet(parquet_file, columns=columns)

        names_dict = {}
        for _, row in df.iterrows():
            name = row.get("name")
            if name and isinstance(name, str):
                name_lower = name.lower()
                info = {"loc_id": row.get("loc_id"), "parent_id": row.get("parent_id"), "admin_level": row.get("admin_level")}
                names_dict.setdefault(name_lower, []).append(info)

        _PARQUET_NAMES_CACHE[iso3] = names_dict
        logger.debug(f"Loaded {len(names_dict)} unique location names from {iso3}.parquet")
        return names_dict
    except Exception as e:
        logger.warning(f"Error loading parquet names for {iso3}: {e}")
        _PARQUET_NAMES_CACHE[iso3] = {}
        return {}


def get_sorted_location_names(iso3: str, *, load_parquet_names_func: Callable[[str], dict], logger) -> list:
    """Get pre-sorted list of location names for a country."""
    global _PARQUET_SORTED_NAMES_CACHE
    if iso3 in _PARQUET_SORTED_NAMES_CACHE:
        return _PARQUET_SORTED_NAMES_CACHE[iso3]

    names = load_parquet_names_func(iso3)
    if not names:
        _PARQUET_SORTED_NAMES_CACHE[iso3] = []
        return []

    sorted_names = sorted([n for n in names.keys() if not n.isdigit() and len(n) >= 2], key=len, reverse=True)
    _PARQUET_SORTED_NAMES_CACHE[iso3] = sorted_names
    logger.debug(f"Cached {len(sorted_names)} sorted location names for {iso3}")
    return sorted_names


def search_locations_globally(
    name: str,
    admin_level: int | None = None,
    limit_countries: list | None = None,
    *,
    geometry_dir: Path,
    reference_dir: Path,
    load_reference_file: Callable[[Path], Optional[dict]],
    load_parquet_names_func: Callable[[str], dict],
) -> list:
    """Search for exact location-name matches across country parquet files."""
    name_lower = name.lower().strip()
    all_matches = []
    if limit_countries:
        countries = limit_countries
    else:
        priority_countries = ["USA", "CAN", "GBR", "AUS", "DEU", "FRA", "IND", "BRA", "MEX"]
        other_countries = []
        if geometry_dir.exists():
            for f in geometry_dir.glob("*.parquet"):
                iso3 = f.stem
                if iso3 not in priority_countries:
                    other_countries.append(iso3)
        countries = priority_countries + other_countries

    iso_data = load_reference_file(reference_dir / "iso_codes.json") or {}
    for iso3 in countries:
        names = load_parquet_names_func(iso3)
        if not names or name_lower not in names:
            continue
        country_name = iso_data.get("iso3_to_name", {}).get(iso3, iso3)
        for info in names[name_lower]:
            if admin_level is not None and info.get("admin_level") != admin_level:
                continue
            all_matches.append(
                {
                    "matched_term": name_lower,
                    "iso3": iso3,
                    "country_name": country_name,
                    "loc_id": info.get("loc_id"),
                    "parent_id": info.get("parent_id"),
                    "admin_level": info.get("admin_level", 0),
                    "is_subregion": info.get("admin_level", 0) > 0,
                }
            )
    return all_matches


def lookup_location_in_viewport(
    query: str,
    viewport: dict | None = None,
    *,
    get_countries_in_viewport_func: Callable[[dict], list],
    load_parquet_names_func: Callable[[str], dict],
    load_reference_file: Callable[[Path], Optional[dict]],
    get_sorted_location_names_func: Callable[[str], list],
    reference_dir: Path,
) -> dict:
    """Search for a location name in parquet files, scoped by viewport."""
    query_lower = query.lower()
    result = {"match": None, "matches": [], "ambiguous": False}
    if not viewport or not viewport.get("bounds"):
        return result

    countries_to_search = get_countries_in_viewport_func(viewport["bounds"])
    if not countries_to_search:
        return result

    all_matches = []
    for iso3 in countries_to_search:
        names = load_parquet_names_func(iso3)
        if not names:
            continue
        iso_data = load_reference_file(reference_dir / "iso_codes.json") or {}
        country_name = iso_data.get("iso3_to_name", {}).get(iso3, iso3)
        sorted_names = get_sorted_location_names_func(iso3)
        for name in sorted_names:
            pattern = r"\b" + re.escape(name) + r"\b"
            if re.search(pattern, query_lower):
                for info in names[name]:
                    all_matches.append(
                        {
                            "matched_term": name,
                            "iso3": iso3,
                            "country_name": country_name,
                            "loc_id": info.get("loc_id"),
                            "admin_level": info.get("admin_level", 0),
                            "is_subregion": info.get("admin_level", 0) > 0,
                        }
                    )

    if len(all_matches) == 1:
        match = all_matches[0]
        result["match"] = (match["matched_term"], match["iso3"], match["is_subregion"])
        result["matches"] = all_matches
    elif len(all_matches) > 1:
        result["matches"] = all_matches
        result["ambiguous"] = True
        match = all_matches[0]
        result["match"] = (match["matched_term"], match["iso3"], match["is_subregion"])
    return result
