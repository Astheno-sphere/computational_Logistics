"""Country family-to-admin crosswalk lookups.

Crosswalk Parquets are built by:
  county-map-private/build/geometry/build_family_admin_crosswalk.py

This module is intentionally internal. Public MCP/API tools should wrap this
shared helper later instead of implementing ZIP/ZCTA-specific conversion logic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..duckdb_helpers import is_cloud_mode, select_rows
from ..paths import DATA_ROOT


def admin_level_name(admin_level: int | str) -> str:
    text = str(admin_level if admin_level is not None else "").strip().lower()
    aliases = {
        "country": "admin_0",
        "nation": "admin_0",
        "state": "admin_1",
        "province": "admin_1",
        "region": "admin_1",
        "county": "admin_2",
        "district": "admin_2",
        "tract": "admin_3",
        "census_tract": "admin_3",
        "census tract": "admin_3",
        "blockgroup": "admin_4",
        "block_group": "admin_4",
        "block group": "admin_4",
        "block": "admin_5",
    }
    if text in aliases:
        return aliases[text]
    if text.startswith("admin_"):
        return text
    try:
        return f"admin_{int(text)}"
    except ValueError:
        return text


def default_crosswalk_path(
    *,
    source_family: str,
    target_admin_level: int | str,
    iso3: str = "USA",
) -> Path:
    level = admin_level_name(target_admin_level)
    filename = f"{str(source_family).strip()}_to_{level}_{str(iso3).strip().upper()}.parquet"
    return (
        DATA_ROOT / "geometry" / "countries" / str(iso3).strip().upper()
        / "crosswalks" / "measured" / filename
    )


def _read_crosswalk_rows(
    crosswalk_path: Path,
    *,
    exact_filters: dict[str, Any] | None = None,
    in_filters: dict[str, list[Any]] | None = None,
) -> pd.DataFrame:
    if not is_cloud_mode() and not crosswalk_path.exists():
        return pd.DataFrame()
    return select_rows(crosswalk_path, exact_filters=exact_filters, in_filters=in_filters)


def _shape_overlap(row: pd.Series, *, direction: str) -> dict[str, Any]:
    source = {
        "family": row.get("source_family"),
        "loc_id": row.get("source_loc_id"),
        "name": row.get("source_name"),
    }
    target = {
        "family": row.get("target_family"),
        "admin_level": row.get("target_admin_level"),
        "loc_id": row.get("target_loc_id"),
        "name": row.get("target_name"),
    }
    payload = {
        "source": source,
        "target": target,
        "intersection_area": row.get("intersection_area"),
        "source_area_share": row.get("source_area_share"),
        "target_area_share": row.get("target_area_share"),
        "rank_by_source_area": row.get("rank_by_source_area"),
        "rank_by_target_area": row.get("rank_by_target_area"),
        "is_primary": bool(row.get("is_primary")),
        "primary_policy": row.get("primary_policy"),
        "relationship_vintage": row.get("relationship_vintage"),
    }
    if direction == "source_to_admin":
        payload["match_loc_id"] = target["loc_id"]
        payload["match_share"] = row.get("source_area_share")
        payload["match_rank"] = row.get("rank_by_source_area")
    else:
        payload["match_loc_id"] = source["loc_id"]
        payload["match_share"] = row.get("target_area_share")
        payload["match_rank"] = row.get("rank_by_target_area")
    return payload


def _filter_and_sort(
    df: pd.DataFrame,
    *,
    sort_col: str,
    min_share: float | None,
    limit: int | None,
) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if min_share is not None and sort_col in out.columns:
        out = out[out[sort_col] >= float(min_share)].copy()
    if out.empty:
        return out
    sort_columns = [column for column in (sort_col, "intersection_area") if column in out.columns]
    if not sort_columns and "is_primary" in out.columns:
        sort_columns = ["is_primary"]
    if sort_columns:
        out = out.sort_values(sort_columns, ascending=[False] * len(sort_columns))
    if limit is not None:
        out = out.head(max(1, int(limit))).copy()
    return out.reset_index(drop=True)


def resolve_family_to_admin(
    source_loc_id: str,
    *,
    source_family: str,
    target_admin_level: int | str,
    iso3: str = "USA",
    crosswalk_path: Path | None = None,
    min_source_area_share: float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return the primary admin match and weighted overlaps for a side-chain loc_id."""
    source_loc_id = str(source_loc_id or "").strip()
    source_family = str(source_family or "").strip()
    target_level = admin_level_name(target_admin_level)
    path = crosswalk_path or default_crosswalk_path(
        source_family=source_family,
        target_admin_level=target_level,
        iso3=iso3,
    )
    if not source_loc_id:
        return {"ok": False, "error": "source_loc_id is required"}

    rows = _read_crosswalk_rows(path, exact_filters={"source_loc_id": source_loc_id})
    rows = _filter_and_sort(
        rows,
        sort_col="source_area_share",
        min_share=min_source_area_share,
        limit=limit,
    )
    overlaps = [_shape_overlap(row, direction="source_to_admin") for _, row in rows.iterrows()]
    primary = overlaps[0] if overlaps else None
    return {
        "ok": bool(overlaps),
        "direction": "source_to_admin",
        "source_family": source_family,
        "source_loc_id": source_loc_id,
        "target_family": "admin",
        "target_admin_level": target_level,
        "crosswalk_path": str(path),
        "primary_match": primary,
        "overlaps": overlaps,
        "overlap_count": len(overlaps),
    }


def resolve_family_ids_to_admin(
    source_loc_ids: list[str],
    *,
    source_family: str,
    target_admin_level: int | str,
    iso3: str = "USA",
    crosswalk_path: Path | None = None,
    min_source_area_share: float | None = None,
    limit: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Resolve many source identities with one predicate-pushed crosswalk scan."""
    ordered_ids = list(dict.fromkeys(str(value or "").strip() for value in source_loc_ids if str(value or "").strip()))
    if not ordered_ids:
        return {}
    source_family = str(source_family or "").strip()
    target_level = admin_level_name(target_admin_level)
    path = crosswalk_path or default_crosswalk_path(
        source_family=source_family,
        target_admin_level=target_level,
        iso3=iso3,
    )
    rows = _read_crosswalk_rows(path, in_filters={"source_loc_id": ordered_ids})
    results: dict[str, dict[str, Any]] = {}
    for source_loc_id in ordered_ids:
        source_rows = rows[rows["source_loc_id"] == source_loc_id] if not rows.empty and "source_loc_id" in rows else pd.DataFrame()
        source_rows = _filter_and_sort(
            source_rows,
            sort_col="source_area_share",
            min_share=min_source_area_share,
            limit=limit,
        )
        overlaps = [_shape_overlap(row, direction="source_to_admin") for _, row in source_rows.iterrows()]
        results[source_loc_id] = {
            "ok": bool(overlaps),
            "direction": "source_to_admin",
            "source_family": source_family,
            "source_loc_id": source_loc_id,
            "target_family": "admin",
            "target_admin_level": target_level,
            "crosswalk_path": str(path),
            "primary_match": overlaps[0] if overlaps else None,
            "overlaps": overlaps,
            "overlap_count": len(overlaps),
        }
    return results


def resolve_admin_to_family(
    target_loc_id: str,
    *,
    source_family: str,
    target_admin_level: int | str,
    iso3: str = "USA",
    crosswalk_path: Path | None = None,
    min_target_area_share: float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return side-chain polygons that overlap an admin loc_id."""
    target_loc_id = str(target_loc_id or "").strip()
    source_family = str(source_family or "").strip()
    target_level = admin_level_name(target_admin_level)
    path = crosswalk_path or default_crosswalk_path(
        source_family=source_family,
        target_admin_level=target_level,
        iso3=iso3,
    )
    if not target_loc_id:
        return {"ok": False, "error": "target_loc_id is required"}

    rows = _read_crosswalk_rows(path, exact_filters={"target_loc_id": target_loc_id})
    rows = _filter_and_sort(
        rows,
        sort_col="target_area_share",
        min_share=min_target_area_share,
        limit=limit,
    )
    overlaps = [_shape_overlap(row, direction="admin_to_source") for _, row in rows.iterrows()]
    primary = overlaps[0] if overlaps else None
    return {
        "ok": bool(overlaps),
        "direction": "admin_to_source",
        "source_family": source_family,
        "target_family": "admin",
        "target_admin_level": target_level,
        "target_loc_id": target_loc_id,
        "crosswalk_path": str(path),
        "primary_match": primary,
        "overlaps": overlaps,
        "overlap_count": len(overlaps),
    }


def resolve_admin_ids_to_family(
    target_loc_ids: list[str],
    *,
    source_family: str,
    target_admin_level: int | str,
    iso3: str = "USA",
    crosswalk_path: Path | None = None,
    min_target_area_share: float | None = None,
    limit: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Resolve many admin identities with one predicate-pushed crosswalk scan."""
    ordered_ids = list(dict.fromkeys(str(value or "").strip() for value in target_loc_ids if str(value or "").strip()))
    if not ordered_ids:
        return {}
    source_family = str(source_family or "").strip()
    target_level = admin_level_name(target_admin_level)
    path = crosswalk_path or default_crosswalk_path(
        source_family=source_family,
        target_admin_level=target_level,
        iso3=iso3,
    )
    rows = _read_crosswalk_rows(path, in_filters={"target_loc_id": ordered_ids})
    results: dict[str, dict[str, Any]] = {}
    for target_loc_id in ordered_ids:
        target_rows = rows[rows["target_loc_id"] == target_loc_id] if not rows.empty and "target_loc_id" in rows else pd.DataFrame()
        target_rows = _filter_and_sort(
            target_rows,
            sort_col="target_area_share",
            min_share=min_target_area_share,
            limit=limit,
        )
        overlaps = [_shape_overlap(row, direction="admin_to_source") for _, row in target_rows.iterrows()]
        results[target_loc_id] = {
            "ok": bool(overlaps),
            "direction": "admin_to_source",
            "source_family": source_family,
            "target_family": "admin",
            "target_admin_level": target_level,
            "target_loc_id": target_loc_id,
            "crosswalk_path": str(path),
            "primary_match": overlaps[0] if overlaps else None,
            "overlaps": overlaps,
            "overlap_count": len(overlaps),
        }
    return results
