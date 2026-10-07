"""Predicate-first exact global Admin0 point resolution."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from shapely.geometry import Point
from shapely.wkb import loads as load_wkb

from ..paths import GEOMETRY_DIR
from ..duckdb_helpers import is_cloud_mode
from .geometry_catalog import load_geometry_catalog
from .geometry_storage_layout import catalog_artifact_path, global_admin0_point_path
from .geometry_predicate_query import (
    read_bbox_candidates_for_points,
    read_hash_sharded_rows,
    read_rows_by_ids,
)
from .admin_spine_query import _geometry_review

logger = logging.getLogger(__name__)
_CACHE_LOCK = threading.Lock()
_CACHE_SIGNATURE: tuple[str, str] | None = None
_CACHE_LAYOUT: dict[str, Any] | None = None


def clear_global_admin0_query_cache() -> None:
    global _CACHE_SIGNATURE, _CACHE_LAYOUT
    with _CACHE_LOCK:
        _CACHE_SIGNATURE = None
        _CACHE_LAYOUT = None


def _active_layout() -> dict[str, Any] | None:
    global _CACHE_SIGNATURE, _CACHE_LAYOUT
    catalog = load_geometry_catalog()
    layout = (catalog.get("runtime_query_layouts") or {}).get("global_admin0_point")
    if not isinstance(layout, dict):
        return None
    signature = (
        str(catalog.get("catalog_fingerprint") or catalog.get("generated_at") or ""),
        str(layout.get("source_fingerprint") or ""),
    )
    with _CACHE_LOCK:
        if signature == _CACHE_SIGNATURE:
            return _CACHE_LAYOUT
    if (
        layout.get("representation") != "full"
        or layout.get("authoritative_for_containment") is not True
    ):
        return None
    point_bank = global_admin0_point_path(
        GEOMETRY_DIR.parent, layout.get("point_bank"), cloud_mode=is_cloud_mode(),
    )
    shard_count = int(layout.get("shard_count") or 0)
    bbox_index = catalog_artifact_path(GEOMETRY_DIR.parent, layout.get("bbox_index"))
    point_shards = {
        str(shard): path
        for shard, record in (layout.get("point_shards") or {}).items()
        if (path := catalog_artifact_path(GEOMETRY_DIR.parent, record)) is not None
    }
    value = None
    if point_bank is not None:
        value = {
            "layout_id": layout.get("layout_id"),
            "point_bank": point_bank,
        }
    elif (
        layout.get("shard_function") == "sha256_mod"
        and bbox_index is not None
        and shard_count > 0
        and len(point_shards) == shard_count
    ):
        value = {
            "layout_id": layout.get("layout_id"),
            "bbox_index": bbox_index,
            "point_shards": point_shards,
            "shard_count": shard_count,
        }
    with _CACHE_LOCK:
        _CACHE_SIGNATURE = signature
        _CACHE_LAYOUT = value
    return value


def resolve_global_admin0_query_points(
    points: Iterable[dict[str, Any]],
) -> list[pd.Series | None] | None:
    """Resolve points against Full-derived shards, or return None for fallback."""
    point_items = list(points)
    layout = _active_layout()
    if layout is None:
        return None
    try:
        candidate_path = layout.get("point_bank") or layout["bbox_index"]
        bbox = read_bbox_candidates_for_points(
            candidate_path, point_items,
            columns=["candidate_id", "loc_id", "name", "source_kind", "area_sq_degrees"],
        )
        candidate_ids = set(bbox["candidate_id"].astype(str)) if not bbox.empty else set()
        exact_columns = [
            "loc_id", "name", "source_kind", "area_sq_degrees", "geometry_wkb",
            "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
        ]
        exact = (
            read_rows_by_ids(
                layout["point_bank"], candidate_ids,
                id_column="candidate_id", columns=exact_columns,
            )
            if layout.get("point_bank") else
            read_hash_sharded_rows(
                layout["point_shards"], candidate_ids,
                shard_count=layout["shard_count"],
                id_column="candidate_id", columns=exact_columns,
            )
        )
    except Exception:
        logger.warning("Global Admin0 point-query layout failed; using Full CSV fallback", exc_info=True)
        return None

    rows_by_id = {
        str(row.get("candidate_id")): row
        for row in exact.to_dict("records")
    }
    geometries: dict[str, Any] = {}
    for candidate_id, row in rows_by_id.items():
        try:
            geometries[candidate_id] = load_wkb(bytes(row["geometry_wkb"]))
        except Exception:
            continue

    candidates_by_position: dict[int, list[str]] = {}
    for row in bbox.to_dict("records"):
        candidates_by_position.setdefault(int(row["point_position"]), []).append(str(row["candidate_id"]))

    results: list[pd.Series | None] = []
    for position, item in enumerate(point_items):
        try:
            point = Point(float(item["lon"]), float(item["lat"]))
        except (KeyError, TypeError, ValueError):
            results.append(None)
            continue
        matches: list[tuple[float, str, str, dict[str, Any]]] = []
        for candidate_id in candidates_by_position.get(position, []):
            row = rows_by_id.get(candidate_id)
            geometry = geometries.get(candidate_id)
            if row is None or geometry is None or not geometry.covers(point):
                continue
            matches.append((
                float(row.get("area_sq_degrees") or geometry.area),
                str(row.get("loc_id") or ""),
                candidate_id,
                row,
            ))
        if not matches:
            results.append(None)
            continue
        selected = min(matches, key=lambda value: value[:3])[3]
        geometry_review = _geometry_review({0: [match[1] for match in matches]})
        results.append(pd.Series({
            "loc_id": selected.get("loc_id"),
            "name": selected.get("name") or selected.get("loc_id"),
            "admin_level": 0,
            "source_system": selected.get("source_kind"),
            **({"geometry_review": geometry_review} if geometry_review else {}),
        }))
    return results


def load_global_admin0_identities(loc_ids: Iterable[str]) -> dict[str, pd.Series] | None:
    """Read country identity columns from the compact index, never Full CSV."""
    layout = _active_layout()
    if layout is None:
        return None
    wanted = {str(value).strip().upper() for value in loc_ids if str(value).strip()}
    try:
        rows = read_rows_by_ids(
            layout.get("point_bank") or layout["bbox_index"], wanted,
            id_column="loc_id",
            columns=["name", "source_kind"],
        )
    except Exception:
        logger.warning("Global Admin0 identity index failed; using Full CSV fallback", exc_info=True)
        return None
    identities: dict[str, pd.Series] = {}
    for row in rows.to_dict("records"):
        loc_id = str(row.get("loc_id") or "").strip().upper()
        identities.setdefault(loc_id, pd.Series({
            "loc_id": loc_id,
            "name": row.get("name") or loc_id,
            "admin_level": 0,
            "source_system": row.get("source_kind"),
        }))
    return identities


def load_global_admin0_geometries(loc_ids: Iterable[str]) -> pd.DataFrame | None:
    """Read exact Full-derived Admin0 polygons by loc_id from selected shards."""
    layout = _active_layout()
    if layout is None:
        return None
    wanted = {str(value).strip().upper() for value in loc_ids if str(value).strip()}
    if not wanted:
        return pd.DataFrame()
    try:
        index_rows = read_rows_by_ids(
            layout.get("point_bank") or layout["bbox_index"],
            wanted,
            id_column="loc_id",
            columns=["candidate_id", "name", "source_kind", "area_sq_degrees"],
        )
        candidate_ids = set(index_rows["candidate_id"].astype(str)) if not index_rows.empty else set()
        exact_columns = [
            "loc_id", "name", "source_kind", "area_sq_degrees", "geometry_wkb",
            "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
        ]
        exact = (
            read_rows_by_ids(
                layout["point_bank"], candidate_ids,
                id_column="candidate_id", columns=exact_columns,
            )
            if layout.get("point_bank") else
            read_hash_sharded_rows(
                layout["point_shards"], candidate_ids,
                shard_count=layout["shard_count"],
                id_column="candidate_id", columns=exact_columns,
            )
        )
    except Exception:
        logger.warning("Global Admin0 exact shape lookup failed; using Full CSV fallback", exc_info=True)
        return None
    if exact.empty:
        return exact
    # Overlap overrides can intentionally publish more than one candidate for
    # one loc_id. Match point resolution by selecting the smallest exact area.
    selected = (
        exact.sort_values(["loc_id", "area_sq_degrees", "candidate_id"])
        .drop_duplicates(subset=["loc_id"], keep="first")
        .rename(columns={"geometry_wkb": "geometry", "source_kind": "source_system"})
        .copy()
    )
    selected["admin_level"] = 0
    selected["has_polygon"] = True
    return selected.reset_index(drop=True)
