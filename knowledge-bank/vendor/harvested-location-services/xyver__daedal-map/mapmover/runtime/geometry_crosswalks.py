"""Internal geometry crosswalk lookup helpers.

This module keeps Census crosswalk artifacts queryable from both
local data roots and cloud/R2 runtime mode. It intentionally does not define a
public API or MCP contract; those surfaces should wrap this helper later.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from ..duckdb_helpers import is_cloud_mode, select_rows
from ..paths import DATA_ROOT
from .family_admin_crosswalk import admin_level_name


CENSUS_CROSSWALK_ROOT = (
    DATA_ROOT / "geometry" / "countries" / "USA" / "crosswalks" / "official" / "census"
)
CENSUS_ZCTA_CROSSWALK_ROOT = CENSUS_CROSSWALK_ROOT
CENSUS_ZCTA_CROSSWALK_MANIFEST = CENSUS_CROSSWALK_ROOT / "census_zcta_crosswalk_manifest.json"
CENSUS_CROSSWALK_MANIFEST = CENSUS_CROSSWALK_ROOT / "census_geometry_crosswalk_manifest.json"


_FAMILY_ALIASES = {
    "zcta": "overlay_zcta",
    "zip": "overlay_zcta",
    "zipcode": "overlay_zcta",
    "zip_code": "overlay_zcta",
    "zip code": "overlay_zcta",
    "nws_public_zone": "overlay_nws_public_zone",
    "nws public zone": "overlay_nws_public_zone",
    "nws_zone": "overlay_nws_public_zone",
    "nws zone": "overlay_nws_public_zone",
    "weather_zone": "overlay_nws_public_zone",
    "weather zone": "overlay_nws_public_zone",
    "forecast_zone": "overlay_nws_public_zone",
    "forecast zone": "overlay_nws_public_zone",
    "nws_fire_weather_zone": "overlay_nws_fire_weather_zone",
    "nws fire weather zone": "overlay_nws_fire_weather_zone",
    "fire_weather_zone": "overlay_nws_fire_weather_zone",
    "fire weather zone": "overlay_nws_fire_weather_zone",
    "red_flag_zone": "overlay_nws_fire_weather_zone",
    "red flag zone": "overlay_nws_fire_weather_zone",
    "county": "admin_2",
    "tract": "admin_3",
    "census_tract": "admin_3",
    "census tract": "admin_3",
    "blockgroup": "admin_4",
    "block_group": "admin_4",
    "block group": "admin_4",
    "block": "admin_5",
    "place": "place",
    "city": "place",
    "cousub": "county_subdivision",
    "county_subdivision": "county_subdivision",
    "county subdivision": "county_subdivision",
    "ua": "urban_area_2020",
    "urban_area": "urban_area_2020",
    "urban area": "urban_area_2020",
    "cd119": "congressional_district_119",
    "congressional_district": "congressional_district_119",
    "congressional district": "congressional_district_119",
    "state_leg_lower": "state_leg_lower_2024",
    "state legislative lower": "state_leg_lower_2024",
    "state_leg_upper": "state_leg_upper_2024",
    "state legislative upper": "state_leg_upper_2024",
    "cbsa": "cbsa_2023",
    "metro": "cbsa_2023",
    "metro_area": "cbsa_2023",
    "necta": "necta_2020",
}


def normalize_family(family: str | int | None) -> str:
    """Normalize family/admin aliases used by private geometry callers."""
    text = str(family or "").strip().lower()
    if not text:
        return ""
    if text in _FAMILY_ALIASES:
        return _FAMILY_ALIASES[text]
    if text.startswith("admin_"):
        return admin_level_name(text)
    return text


def normalize_zcta_loc_id(value: Any, *, iso3: str = "USA") -> str:
    """Accept either a 5-digit ZCTA/ZIP or a full overlay_zcta loc_id."""
    text = str(value or "").strip()
    if text.isdigit() and len(text) == 5:
        return f"{str(iso3 or 'USA').strip().upper()}-Z-{text}"
    return text


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value


def _row_payload(row: pd.Series) -> dict[str, Any]:
    return {str(key): _json_safe(value) for key, value in row.items()}


def _read_filtered_rows(path: Path, exact_filters: dict[str, Any]) -> pd.DataFrame:
    if path.exists():
        filters = [(key, "==", value) for key, value in exact_filters.items() if value is not None]
        return pd.read_parquet(path, filters=filters)
    if is_cloud_mode():
        return select_rows(path, exact_filters=exact_filters)
    return pd.DataFrame()


def _sort_limit(
    df: pd.DataFrame,
    *,
    sort_col: str,
    min_share: float | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if min_share is not None and sort_col in out.columns:
        out = out[out[sort_col] >= float(min_share)].copy()
    if out.empty:
        return out
    secondary = "intersection_area" if "intersection_area" in out.columns else sort_col
    out = out.sort_values([sort_col, secondary], ascending=[False, False])
    if limit is not None:
        out = out.head(max(1, min(int(limit), 500))).copy()
    return out.reset_index(drop=True)


def _manifest_relative_artifact(entry: dict[str, Any], root: Path) -> Path:
    artifact = Path(str(entry.get("artifact") or ""))
    if artifact.name:
        return root / artifact.name
    output_name = str(entry.get("output_name") or "").strip()
    if output_name:
        return root / f"{output_name}.parquet"
    raise ValueError("manifest entry has no artifact path or output_name")


@lru_cache(maxsize=4)
def load_census_zcta_crosswalk_manifest() -> dict[str, Any]:
    if CENSUS_ZCTA_CROSSWALK_MANIFEST.exists():
        with CENSUS_ZCTA_CROSSWALK_MANIFEST.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"schema_version": "1.0.0", "status": "missing", "artifacts": []}


@lru_cache(maxsize=4)
def load_census_crosswalk_manifest() -> dict[str, Any]:
    if CENSUS_CROSSWALK_MANIFEST.exists():
        with CENSUS_CROSSWALK_MANIFEST.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"schema_version": "1.0.0", "status": "missing", "artifacts": []}


def list_census_crosswalks() -> list[dict[str, Any]]:
    """Return compact metadata for available Census crosswalk artifacts."""
    manifest = load_census_crosswalk_manifest()
    out: list[dict[str, Any]] = []
    for entry in manifest.get("artifacts") or []:
        if not isinstance(entry, dict):
            continue
        path = _manifest_relative_artifact(entry, CENSUS_CROSSWALK_ROOT)
        out.append(
            {
                "output_name": entry.get("output_name"),
                "source_family": entry.get("source_family"),
                "target_family": entry.get("target_family"),
                "relationship_vintage": entry.get("relationship_vintage"),
                "row_count": entry.get("row_count"),
                "source_count": entry.get("source_count"),
                "target_count": entry.get("target_count"),
                "artifact_path": str(path),
            }
        )
    return out


def census_zcta_crosswalk_path(*, target_admin_level: str | int, iso3: str = "USA") -> Path:
    level = admin_level_name(target_admin_level)
    country = str(iso3 or "USA").strip().upper()
    manifest = load_census_zcta_crosswalk_manifest()
    for entry in manifest.get("artifacts") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("target_admin_level") == level:
            return _manifest_relative_artifact(entry, CENSUS_ZCTA_CROSSWALK_ROOT)
    return CENSUS_ZCTA_CROSSWALK_ROOT / f"census_zcta_to_{level}_{country}.parquet"


def census_crosswalk_path(
    *,
    source_family: str,
    target_family: str,
    output_name: str | None = None,
    relationship_vintage: str | None = None,
) -> Path:
    source = normalize_family(source_family)
    target = normalize_family(target_family)
    wanted_name = str(output_name or "").strip()
    wanted_vintage = str(relationship_vintage or "").strip()
    manifest = load_census_crosswalk_manifest()
    matches: list[dict[str, Any]] = []
    for entry in manifest.get("artifacts") or []:
        if not isinstance(entry, dict):
            continue
        if wanted_name and entry.get("output_name") != wanted_name:
            continue
        if source and entry.get("source_family") != source:
            continue
        if target and entry.get("target_family") != target:
            continue
        if wanted_vintage and entry.get("relationship_vintage") != wanted_vintage:
            continue
        matches.append(entry)
    if len(matches) == 1:
        return _manifest_relative_artifact(matches[0], CENSUS_CROSSWALK_ROOT)
    if len(matches) > 1:
        names = ", ".join(str(item.get("output_name")) for item in matches[:10])
        raise ValueError(f"ambiguous Census crosswalk request; matched: {names}")
    if wanted_name:
        return CENSUS_CROSSWALK_ROOT / f"{wanted_name}.parquet"
    raise ValueError(f"no Census crosswalk found for {source} -> {target}")


def resolve_census_zcta_to_admin(
    source_loc_id: str,
    *,
    target_admin_level: str | int,
    iso3: str = "USA",
    min_source_area_share: float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Resolve a ZCTA to ranked admin-spine matches using Census files."""
    normalized_source = normalize_zcta_loc_id(source_loc_id, iso3=iso3)
    target_level = admin_level_name(target_admin_level)
    path = census_zcta_crosswalk_path(target_admin_level=target_level, iso3=iso3)
    rows = _read_filtered_rows(path, {"source_loc_id": normalized_source})
    rows = _sort_limit(rows, sort_col="source_area_share", min_share=min_source_area_share, limit=limit)
    matches = [_row_payload(row) for _, row in rows.iterrows()]
    return {
        "ok": bool(matches),
        "direction": "source_to_target",
        "source_family": "overlay_zcta",
        "source_loc_id": normalized_source,
        "target_family": "admin",
        "target_admin_level": target_level,
        "artifact_path": str(path),
        "primary_match": matches[0] if matches else None,
        "matches": matches,
        "match_count": len(matches),
    }


def resolve_census_admin_to_zctas(
    target_loc_id: str,
    *,
    target_admin_level: str | int,
    iso3: str = "USA",
    min_target_area_share: float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Resolve an admin loc_id to ranked overlapping ZCTAs using Census files."""
    target_level = admin_level_name(target_admin_level)
    path = census_zcta_crosswalk_path(target_admin_level=target_level, iso3=iso3)
    rows = _read_filtered_rows(path, {"target_loc_id": str(target_loc_id or "").strip()})
    rows = _sort_limit(rows, sort_col="target_area_share", min_share=min_target_area_share, limit=limit)
    matches = [_row_payload(row) for _, row in rows.iterrows()]
    return {
        "ok": bool(matches),
        "direction": "target_to_source",
        "source_family": "overlay_zcta",
        "target_family": "admin",
        "target_admin_level": target_level,
        "target_loc_id": str(target_loc_id or "").strip(),
        "artifact_path": str(path),
        "primary_match": matches[0] if matches else None,
        "matches": matches,
        "match_count": len(matches),
    }


def resolve_census_crosswalk(
    *,
    source_family: str,
    target_family: str,
    source_loc_id: str | None = None,
    source_id: str | None = None,
    target_loc_id: str | None = None,
    target_id: str | None = None,
    output_name: str | None = None,
    relationship_vintage: str | None = None,
    min_share: float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Resolve one Census cross-family relationship in either direction.

    Callers must provide exactly one source or target identifier. Use source
    identifiers for source-to-target lookup and target identifiers for reverse
    lookup.
    """
    source = normalize_family(source_family)
    target = normalize_family(target_family)
    identifiers = {
        "source_loc_id": str(source_loc_id or "").strip(),
        "source_id": str(source_id or "").strip(),
        "target_loc_id": str(target_loc_id or "").strip(),
        "target_id": str(target_id or "").strip(),
    }
    populated = {key: value for key, value in identifiers.items() if value}
    if len(populated) != 1:
        return {
            "ok": False,
            "error": "provide exactly one of source_loc_id, source_id, target_loc_id, or target_id",
            "source_family": source,
            "target_family": target,
        }

    path = census_crosswalk_path(
        source_family=source,
        target_family=target,
        output_name=output_name,
        relationship_vintage=relationship_vintage,
    )
    filter_key, filter_value = next(iter(populated.items()))
    rows = _read_filtered_rows(path, {filter_key: filter_value})
    sort_col = "source_area_share" if filter_key.startswith("source_") else "target_area_share"
    rows = _sort_limit(rows, sort_col=sort_col, min_share=min_share, limit=limit)
    matches = [_row_payload(row) for _, row in rows.iterrows()]
    return {
        "ok": bool(matches),
        "direction": "source_to_target" if filter_key.startswith("source_") else "target_to_source",
        "source_family": source,
        "target_family": target,
        "filter": {filter_key: filter_value},
        "artifact_path": str(path),
        "primary_match": matches[0] if matches else None,
        "matches": matches,
        "match_count": len(matches),
    }
