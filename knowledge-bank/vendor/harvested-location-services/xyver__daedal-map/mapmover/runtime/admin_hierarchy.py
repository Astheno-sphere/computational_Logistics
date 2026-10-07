from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from ..duckdb_helpers import duckdb_available, select_columns_from_parquet
from ..paths import GEOMETRY_DIR
from ..runtime.geography_reference import (
    canonicalize_loc_id,
    derive_eurostat_geo_level,
    translate_geometry_id_to_local_id,
    translate_loc_id_to_geometry_id,
)
from ..geometry_handlers import load_subcounty_geometry

_BASE_GEOMETRY_CACHE: dict[str, pd.DataFrame | None] = {}


def infer_admin_level_from_loc_id(loc_id: str | None) -> int | None:
    """Infer canonical admin level from a runtime loc_id."""
    value = str(loc_id or "").strip()
    if not value:
        return None

    euro_level = derive_eurostat_geo_level(value)
    if euro_level:
        try:
            return int(euro_level.split("_", 1)[1])
        except Exception:
            return None

    if "-" not in value:
        return 0 if len(value) == 3 and value.isupper() else None
    return len(value.split("-")) - 1


def get_parent_loc_id(loc_id: str) -> Optional[str]:
    """Return the canonical parent loc_id for an admin-spine location."""
    canonical = canonicalize_loc_id(loc_id)
    admin_level = infer_admin_level_from_loc_id(canonical)
    if admin_level is None or admin_level <= 0:
        return None

    euro_level = derive_eurostat_geo_level(canonical)
    if euro_level:
        iso3, nuts_code = canonical.split("-", 1)
        parent_nuts = nuts_code[:-1]
        if len(parent_nuts) == 2:
            return iso3
        return f"{iso3}-{parent_nuts}" if parent_nuts else iso3

    if "-" not in canonical:
        return None
    return canonical.rsplit("-", 1)[0]


def get_ancestors(loc_id: str) -> list[str]:
    """Return parent -> grandparent -> ... chain for a loc_id."""
    ancestors: list[str] = []
    current = canonicalize_loc_id(loc_id)
    while True:
        parent = get_parent_loc_id(current)
        if not parent:
            break
        ancestors.append(parent)
        current = parent
    return ancestors


def _load_base_geometry_frame(iso3: str) -> pd.DataFrame | None:
    iso3 = str(iso3 or "").strip().upper()
    if not iso3:
        return None
    if iso3 in _BASE_GEOMETRY_CACHE:
        return _BASE_GEOMETRY_CACHE[iso3]

    parquet_file = GEOMETRY_DIR / f"{iso3}.parquet"
    if not parquet_file.exists():
        _BASE_GEOMETRY_CACHE[iso3] = None
        return None

    columns = ["loc_id", "parent_id", "admin_level"]
    if duckdb_available():
        df = select_columns_from_parquet(parquet_file, columns)
        if df.empty:
            df = pd.read_parquet(parquet_file, columns=columns)
    else:
        df = pd.read_parquet(parquet_file, columns=columns)
    _BASE_GEOMETRY_CACHE[iso3] = df
    return df


def _stateish_region_code(local_loc_id: str) -> str | None:
    parts = str(local_loc_id or "").split("-")
    if len(parts) >= 2:
        second = str(parts[1] or "").strip()
        if second and not second.startswith("G"):
            return second
    return None


def _load_children_frame_for_parent(local_parent_loc_id: str, target_admin_level: int) -> pd.DataFrame | None:
    if target_admin_level <= 2:
        iso3 = str(local_parent_loc_id or "").split("-", 1)[0]
        return _load_base_geometry_frame(iso3)

    iso3 = str(local_parent_loc_id or "").split("-", 1)[0]
    region_code = _stateish_region_code(local_parent_loc_id)
    return load_subcounty_geometry(iso3, admin_level=target_admin_level, state_abbrev=region_code)


def get_children(loc_id: str) -> list[str]:
    """Return direct children of a canonical admin-spine loc_id."""
    canonical = canonicalize_loc_id(loc_id)
    local_parent = translate_geometry_id_to_local_id(canonical)
    admin_level = infer_admin_level_from_loc_id(local_parent)
    if admin_level is None:
        return []

    target_admin_level = admin_level + 1
    df = _load_children_frame_for_parent(local_parent, target_admin_level)
    if df is None or len(df) == 0:
        return []

    if target_admin_level <= 2:
        geometry_parent = translate_loc_id_to_geometry_id(local_parent)
        children = df[df["parent_id"] == geometry_parent]
        return [translate_geometry_id_to_local_id(value) for value in children["loc_id"].tolist()]

    children = df[df["parent_id"] == local_parent]
    return [canonicalize_loc_id(value) for value in children["loc_id"].tolist()]


def clear_admin_hierarchy_cache() -> None:
    _BASE_GEOMETRY_CACHE.clear()
