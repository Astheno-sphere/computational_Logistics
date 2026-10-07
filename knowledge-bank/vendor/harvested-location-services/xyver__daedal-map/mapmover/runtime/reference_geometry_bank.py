"""Resolve shape-backed reference-graph identities to their adopted banks.

Reference families do not all live in one global marine file. An identity row
names its geometry-bank directory; that bank's identity-version row names the
partition containing the shape. This module follows that stored contract and
returns the same normalized frame consumed by the existing geometry tools.
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from pyproj import CRS, Transformer
from pyproj.exceptions import ProjError
from shapely.geometry import mapping, shape
from shapely.ops import transform as transform_geometry, unary_union
from shapely.wkb import loads as load_wkb

from ..duckdb_helpers import parquet_available, parquet_columns, path_to_uri, run_df, select_rows
from ..paths import DATA_ROOT
from .reference_graph import identities, identity_at
from .geometry_catalog import geometry_bank_lineage


IDENTITY_VERSION_COLUMNS = ["loc_id", "geometry_partition", "shape_storage"]
DIRECT_ADMIN_PARTITION_BANKS = {"dissemination_area", "dissemination_block", "deep"}


@lru_cache(maxsize=256)
def _geoparquet_crs(path_text: str) -> CRS | None:
    """Return the declared primary-geometry CRS through the DuckDB read path.

    Geometry-bank paths are logical DATA_ROOT paths.  In hosted mode the
    corresponding file normally exists only in object storage, so opening the
    logical path with PyArrow races temporary hydration or fails outright.
    DuckDB's parquet metadata function follows the same stable local-cache or
    S3 URI selected for the actual filtered geometry query.
    """
    try:
        uri = path_to_uri(Path(path_text))
        rows = run_df(
            "SELECT value FROM parquet_kv_metadata(?) WHERE key = ? LIMIT 1",
            [uri, b"geo"],
        )
        if rows.empty:
            return None
        raw = rows.iloc[0]["value"]
        payload = json.loads(bytes(raw).decode("utf-8"))
        primary = str(payload.get("primary_column") or "geometry")
        crs_value = (payload.get("columns") or {}).get(primary, {}).get("crs")
        return CRS.from_user_input(crs_value) if crs_value else None
    except Exception:
        return None


def _parquet_geometry_type(path: Path) -> str:
    """Return DuckDB's physical geometry-column type without a local open."""
    try:
        rows = run_df(
            "SELECT duckdb_type FROM parquet_schema(?) WHERE name = ? LIMIT 1",
            [path_to_uri(path), "geometry"],
        )
        if not rows.empty:
            return str(rows.iloc[0]["duckdb_type"] or "").strip().upper()
    except Exception:
        pass
    return ""


def _safe_bank_root(value: str | None) -> Path | None:
    text = str(value or "").strip().replace("\\", "/")
    if not text or Path(text).is_absolute():
        return None
    root = (DATA_ROOT / text).resolve()
    try:
        root.relative_to(DATA_ROOT.resolve())
    except ValueError:
        return None
    return root


def _safe_partition_path(bank_root: Path, value: str | None) -> Path | None:
    text = str(value or "").strip().replace("\\", "/")
    if not text or Path(text).is_absolute() or not text.lower().endswith(".parquet"):
        return None
    path = (bank_root / text).resolve()
    try:
        path.relative_to(bank_root.resolve())
    except ValueError:
        return None
    return path


def _read_shape_partition(path: Path, loc_ids: list[str]) -> pd.DataFrame:
    if not loc_ids or not parquet_available(path):
        return pd.DataFrame()
    available = parquet_columns(path)
    if "loc_id" not in available or "geometry" not in available:
        return pd.DataFrame()
    ordinary = [
        column for column in (
            "loc_id", "name", "name_en", "name_fr", "family", "subtype",
            "source_id", "source_release", "area_square_km", "frame_id",
            "frame_part_id", "valid_from", "valid_to", "validity_status",
        ) if column in available
    ]
    if _geoparquet_crs(str(path.resolve())) is not None:
        geometry_expression = 'ST_AsWKB("geometry") AS __geometry_wkb'
    elif _parquet_geometry_type(path) in {"BLOB", "BYTEA", "VARBINARY"}:
        geometry_expression = '"geometry" AS __geometry_wkb'
    else:
        geometry_expression = '"geometry"'
    selected = ", ".join(f'"{column}"' for column in ordinary)
    placeholders = ", ".join("?" for _ in loc_ids)
    sql = (
        f"SELECT {selected}, {geometry_expression} "
        f"FROM read_parquet(?) WHERE \"loc_id\" IN ({placeholders})"
    )
    try:
        return run_df(
            sql,
            [path_to_uri(path), *loc_ids],
            raw_geoparquet=geometry_expression.startswith('"geometry" AS'),
        )
    except Exception as exc:
        if "Out of Memory" not in str(exc):
            raise
        # A few official Canadian partitions contain single 100MB+ geometry
        # cells. DuckDB's guarded 512MB runtime connection can exhaust its
        # allocation while converting an otherwise small filtered result.
        # PyArrow applies the same loc_id predicate without weakening the
        # caller's bank/partition boundary.
        return pd.read_parquet(
            path, columns=[*ordinary, "geometry"],
            filters=[("loc_id", "in", loc_ids)],
        )


def _read_single_file_bank(path: Path, loc_ids: list[str]) -> pd.DataFrame:
    """Read a legacy/adopted bank whose polygons live in one Parquet file."""
    if _geoparquet_crs(str(path.resolve())) is not None:
        # Avoid DuckDB attempting to materialize a projected GeoParquet
        # extension type directly into NumPy/Pandas.
        return _read_shape_partition(path, loc_ids)
    if not loc_ids or not parquet_available(path):
        return pd.DataFrame()
    available = parquet_columns(path)
    if "loc_id" not in available or "geometry" not in available:
        return pd.DataFrame()
    columns = [
        column for column in (
            "loc_id", "name", "name_en", "name_fr", "family", "subtype",
            "source_id", "source_release", "area_square_km", "geometry",
        ) if column in available
    ]
    try:
        return select_rows(path, columns=columns, in_filters={"loc_id": loc_ids})
    except Exception as exc:
        message = str(exc)
        if "Unsupported type" in message and "GEOMETRY" in message:
            return _read_shape_partition(path, loc_ids)
        if "Out of Memory" not in message:
            raise
        return pd.read_parquet(
            path, columns=columns, filters=[("loc_id", "in", loc_ids)],
        )


def _direct_admin_partitions(bank_root: Path, loc_ids: list[str]) -> dict[Path, list[str]]:
    """Map deep Canada admin ids to their province-sharded Parquet banks."""
    if bank_root.name not in DIRECT_ADMIN_PARTITION_BANKS:
        return {}
    partitions: dict[Path, list[str]] = {}
    for loc_id in loc_ids:
        parts = str(loc_id).split("-")
        if len(parts) < 2 or parts[0] != "CAN" or len(parts[1]) != 2:
            continue
        partitions.setdefault(bank_root / f"CAN-{parts[1]}.parquet", []).append(loc_id)
    return partitions


def _normalized_row(
    row: dict[str, Any], identity: dict[str, Any], *, source_crs: CRS | None = None,
) -> dict[str, Any] | None:
    raw_wkb = row.get("__geometry_wkb")
    raw_geometry = row.get("geometry")
    try:
        if raw_wkb:
            geometry = load_wkb(bytes(raw_wkb))
        elif isinstance(raw_geometry, str):
            geometry = shape(json.loads(raw_geometry))
        elif isinstance(raw_geometry, dict):
            geometry = shape(raw_geometry)
        elif raw_geometry:
            geometry = load_wkb(bytes(raw_geometry))
        else:
            return None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if source_crs is not None and not source_crs.equals(CRS.from_epsg(4326)):
        try:
            transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
            geometry = transform_geometry(transformer.transform, geometry)
        except (ValueError, TypeError, ProjError):
            return None
    if geometry.is_empty:
        return None
    min_lon, min_lat, max_lon, max_lat = geometry.bounds
    centroid = geometry.centroid
    bank = str(identity.get("geometry_bank") or "").strip()
    lineage = geometry_bank_lineage(bank)
    return {
        # The graph identity is canonical. ``geometry_loc_id`` may point at an
        # immutable shape row retained under a retired identifier.
        "loc_id": identity.get("loc_id") or row.get("loc_id"),
        "name": row.get("name") or row.get("name_en") or identity.get("name"),
        "name_local": row.get("name_fr"),
        # ``family`` is the public semantic family.  Shape partitions may
        # retain a source/package implementation family (for example a
        # vintage-specific Canadian water-body family), so it must not
        # override the graph's reviewed geography-family classification.
        "family": (
            identity.get("geography_family")
            or row.get("geography_family")
            or identity.get("family")
            or row.get("family")
        ),
        "subtype": row.get("subtype") or identity.get("subtype") or identity.get("source_native_subtype"),
        "source_native_subtype": identity.get("source_native_subtype"),
        "admin_level": identity.get("admin_level"),
        "parent_id": identity.get("parent_loc_id"),
        "centroid_lon": float(centroid.x),
        "centroid_lat": float(centroid.y),
        "bbox_min_lon": float(min_lon),
        "bbox_min_lat": float(min_lat),
        "bbox_max_lon": float(max_lon),
        "bbox_max_lat": float(max_lat),
        "has_polygon": True,
        "geometry": mapping(geometry),
        "source_id": row.get("source_id") or identity.get("native_id"),
        "source_system": identity.get("source_system"),
        "source_vintage": identity.get("source_vintage") or row.get("source_release"),
        "geometry_vintage": identity.get("source_vintage") or row.get("source_release"),
        "geometry_source": identity.get("source_system"),
        "bank_id": bank,
        "lineage": lineage,
        "frame_id": row.get("frame_id") or identity.get("frame_id"),
        "frame_part_id": row.get("frame_part_id"),
        "valid_from": row.get("valid_from") or identity.get("valid_from"),
        "valid_to": row.get("valid_to") or identity.get("valid_to"),
        "validity_status": row.get("validity_status"),
    }


def _merge_frame_parts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one rendered geometry per logical loc/frame selection."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("loc_id") or ""), str(row.get("frame_id") or ""))
        grouped.setdefault(key, []).append(row)
    merged: list[dict[str, Any]] = []
    for parts in grouped.values():
        item = dict(parts[0])
        item["frame_part_count"] = len(parts)
        if len(parts) > 1:
            geometry = unary_union([shape(part["geometry"]) for part in parts])
            min_lon, min_lat, max_lon, max_lat = geometry.bounds
            centroid = geometry.centroid
            item.update({
                "geometry": mapping(geometry),
                "centroid_lon": float(centroid.x), "centroid_lat": float(centroid.y),
                "bbox_min_lon": float(min_lon), "bbox_min_lat": float(min_lat),
                "bbox_max_lon": float(max_lon), "bbox_max_lat": float(max_lat),
                "frame_part_id": None,
            })
        merged.append(item)
    return merged


def load_reference_graph_geometry(
    loc_ids: Iterable[str],
    *,
    columns: list[str] | None = None,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Load shapes for graph identities whose bank owns a shape partition."""
    requested = list(dict.fromkeys(str(item).strip() for item in loc_ids if str(item).strip()))
    if not requested:
        return pd.DataFrame(columns=columns or [])
    identity_rows = (
        [row for loc_id in requested if (row := identity_at(loc_id, as_of)) is not None]
        if as_of is not None else identities(requested)
    )
    by_id = {
        str(row.get("loc_id")): row
        for row in identity_rows
        if row.get("has_shape") is True and row.get("geometry_bank")
    }
    by_bank: dict[Path, list[str]] = {}
    bank_identities: dict[Path, dict[str, list[dict[str, Any]]]] = {}
    for loc_id in requested:
        identity_row = by_id.get(loc_id) or {}
        bank_root = _safe_bank_root(identity_row.get("geometry_bank"))
        if bank_root is not None:
            geometry_loc_id = str(identity_row.get("geometry_loc_id") or loc_id).strip()
            if not geometry_loc_id:
                geometry_loc_id = loc_id
            by_bank.setdefault(bank_root, []).append(geometry_loc_id)
            bank_identities.setdefault(bank_root, {}).setdefault(
                geometry_loc_id, [],
            ).append(identity_row)

    normalized: list[dict[str, Any]] = []
    for bank_root, bank_ids in by_bank.items():
        bank_ids = list(dict.fromkeys(bank_ids))
        identities_by_geometry_id = bank_identities[bank_root]
        if bank_root.suffix.lower() == ".parquet":
            shape_rows = _read_single_file_bank(bank_root, bank_ids)
            source_crs = _geoparquet_crs(str(bank_root.resolve()))
            for row in shape_rows.to_dict("records"):
                for identity_row in identities_by_geometry_id.get(str(row.get("loc_id")), []):
                    selected_frame = str(identity_row.get("frame_id") or "")
                    if selected_frame and str(row.get("frame_id") or "") != selected_frame:
                        continue
                    item = _normalized_row(row, identity_row, source_crs=source_crs)
                    if item is not None:
                        normalized.append(item)
            continue
        direct_partitions = _direct_admin_partitions(bank_root, bank_ids)
        if direct_partitions:
            for partition, partition_ids in direct_partitions.items():
                shape_rows = _read_single_file_bank(partition, partition_ids)
                source_crs = _geoparquet_crs(str(partition.resolve()))
                for row in shape_rows.to_dict("records"):
                    for identity_row in identities_by_geometry_id.get(str(row.get("loc_id")), []):
                        selected_frame = str(identity_row.get("frame_id") or "")
                        if selected_frame and str(row.get("frame_id") or "") != selected_frame:
                            continue
                        item = _normalized_row(row, identity_row, source_crs=source_crs)
                        if item is not None:
                            normalized.append(item)
            continue
        versions_path = bank_root / "identity_versions.parquet"
        version_rows = select_rows(
            versions_path,
            columns=IDENTITY_VERSION_COLUMNS,
            in_filters={"loc_id": bank_ids},
        )
        if version_rows is None or version_rows.empty:
            continue
        partitions: dict[Path, list[str]] = {}
        for row in version_rows.to_dict("records"):
            partition = _safe_partition_path(bank_root, row.get("geometry_partition"))
            if partition is not None and str(row.get("shape_storage") or "").strip() != "identity_only":
                partitions.setdefault(partition, []).append(str(row.get("loc_id")))
        for partition, partition_ids in partitions.items():
            shape_rows = _read_shape_partition(partition, partition_ids)
            source_crs = _geoparquet_crs(str(partition.resolve()))
            for row in shape_rows.to_dict("records"):
                for identity_row in identities_by_geometry_id.get(str(row.get("loc_id")), []):
                    selected_frame = str(identity_row.get("frame_id") or "")
                    if selected_frame and str(row.get("frame_id") or "") != selected_frame:
                        continue
                    item = _normalized_row(row, identity_row, source_crs=source_crs)
                    if item is not None:
                        normalized.append(item)

    frame = pd.DataFrame(_merge_frame_parts(normalized))
    if frame.empty:
        return pd.DataFrame(columns=columns or [])
    if columns:
        keep = [column for column in columns if column in frame.columns]
        if "loc_id" not in keep:
            keep.insert(0, "loc_id")
        return frame[keep].copy()
    return frame
