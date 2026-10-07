"""Catalog-routed Marine geometry reads.

Marine is a first-version release unit. The canonical geometry catalog selects
its immutable banks and predicate layout; this module deliberately has no
legacy-file fallback or second source of activation truth.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

from ..duckdb_helpers import (
    is_cloud_mode,
    parquet_available,
    select_columns_from_parquet,
)
from ..paths import GEOMETRY_DIR
from .geography_reference import (
    is_marine_jurisdiction_loc_id,
    is_named_water_loc_id,
    is_water_body_loc_id,
)
from .geometry_catalog import load_geometry_catalog
from .geometry_storage_layout import catalog_artifact_path
from .geometry_predicate_query import (
    read_bbox_candidates,
    read_bbox_candidates_for_points,
    read_geojson_containment_for_points,
    read_rows_by_ids,
)

_MARINE_COLUMNS = ["loc_id", "name", "geometry", "centroid_lon", "centroid_lat"]
_MARINE_POINT_COLUMNS = _MARINE_COLUMNS + [
    "geometry_wkb", "area_km2",
    "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
]
_ACTIVE_DOMAIN_CACHE_LOCK = threading.Lock()
_ACTIVE_DOMAIN_CACHE_SIGNATURE: tuple[str, str] | None = None
_ACTIVE_DOMAIN_CACHE_VALUE: Optional[dict[str, Any]] = None


def is_marine_loc_id(loc_id: str | None) -> bool:
    """True for either marine overlay family or canonical named water."""
    return is_marine_jurisdiction_loc_id(loc_id) or is_water_body_loc_id(loc_id) or is_named_water_loc_id(loc_id)


def clear_marine_geometry_cache() -> None:
    global _ACTIVE_DOMAIN_CACHE_SIGNATURE, _ACTIVE_DOMAIN_CACHE_VALUE
    with _ACTIVE_DOMAIN_CACHE_LOCK:
        _ACTIVE_DOMAIN_CACHE_SIGNATURE = None
        _ACTIVE_DOMAIN_CACHE_VALUE = None


def _active_domain_paths() -> Optional[dict[str, Any]]:
    """Resolve the active Marine banks only from the canonical runtime catalog."""
    global _ACTIVE_DOMAIN_CACHE_SIGNATURE, _ACTIVE_DOMAIN_CACHE_VALUE
    catalog = load_geometry_catalog()
    profile = next((
        item for item in catalog.get("domain_profiles") or []
        if isinstance(item, dict)
        and str(item.get("release_unit_id") or "").strip().upper() == "MARINE"
    ), None)
    active = profile.get("active_release") if isinstance(profile, dict) else None
    if not isinstance(active, dict) or active.get("publication_status") not in {
        "approved_for_publication", "published",
    }:
        return None
    artifacts = active.get("runtime_artifacts")
    if not isinstance(artifacts, dict):
        return None
    signature = (
        str(catalog.get("catalog_fingerprint") or catalog.get("generated_at") or ""),
        str(active.get("release_id") or active.get("release_version") or ""),
    )
    with _ACTIVE_DOMAIN_CACHE_LOCK:
        if signature == _ACTIVE_DOMAIN_CACHE_SIGNATURE:
            return _ACTIVE_DOMAIN_CACHE_VALUE
    paths = {
        key: catalog_artifact_path(GEOMETRY_DIR.parent, artifacts.get(key))
        for key in (
            "jurisdictions", "water_bodies", "named_water_areas", "bbox_index", "point_bank",
        )
    }
    if any(path is None for path in paths.values()):
        return None
    country_components = {
        str(country).upper(): path
        for country, record in (artifacts.get("country_components") or {}).items()
        if (path := catalog_artifact_path(GEOMETRY_DIR.parent, record)) is not None
    }
    if any(paths.get(key) is None for key in paths):
        return None
    value = {**paths, "country_components": country_components}
    with _ACTIVE_DOMAIN_CACHE_LOCK:
        _ACTIVE_DOMAIN_CACHE_SIGNATURE = signature
        _ACTIVE_DOMAIN_CACHE_VALUE = value
    return value


def marine_bank_for_loc_id(loc_id: str | None) -> Optional[Path]:
    """Return the marine geometry bank that owns this loc_id, or None."""
    value = str(loc_id or "").strip().upper()
    domain = _active_domain_paths()
    if not domain:
        return None
    if is_marine_jurisdiction_loc_id(loc_id):
        prefix = value.split("-", 1)[0]
        if is_water_body_loc_id(prefix):
            return domain["jurisdictions"]
        return domain["country_components"].get(prefix)
    if is_named_water_loc_id(loc_id):
        return domain["named_water_areas"]
    if is_water_body_loc_id(loc_id):
        return domain["water_bodies"]
    return None


def has_marine_geometry() -> bool:
    """True when the canonical catalog admits a complete Marine layout."""
    domain = _active_domain_paths()
    if domain is None:
        return False
    if is_cloud_mode():
        return True
    required = ("jurisdictions", "water_bodies", "named_water_areas", "bbox_index", "point_bank")
    return all(Path(domain[key]).is_file() for key in required)


def resolve_marine_geometry_source(loc_id: str | None) -> dict:
    """Mirror geometry_loader.resolve_country_geometry_source for marine loc_ids.

    Keys: `parquet_file` (path or None), `source_kind` (`marine_bank`/`missing`),
    `marine_kind` (`marine_eez`/`water_body`/`named_water`/None).
    """
    bank = marine_bank_for_loc_id(loc_id)
    if bank is None:
        return {"parquet_file": None, "source_kind": "missing", "marine_kind": None}
    accessible = parquet_available(bank)
    return {
        "parquet_file": bank if accessible else None,
        "source_kind": "marine_bank" if accessible else "missing",
        "marine_kind": (
            ("marine_eez" if str(loc_id or "").strip().upper().startswith("EEZ-") else "marine_jurisdiction")
            if is_marine_jurisdiction_loc_id(loc_id)
            else "named_water" if is_named_water_loc_id(loc_id)
            else "water_body"
        ),
    }


def _read_bank(path: Path, want: Optional[set], columns: Optional[list[str]] = None) -> pd.DataFrame:
    selected_columns = [column for column in (columns or _MARINE_COLUMNS) if column in _MARINE_POINT_COLUMNS]
    if "loc_id" not in selected_columns:
        selected_columns.insert(0, "loc_id")
    if not parquet_available(path):
        return pd.DataFrame(columns=selected_columns)
    if want:
        return read_rows_by_ids(
            path, want, id_column="loc_id", columns=selected_columns,
        )
    return select_columns_from_parquet(path, selected_columns)


def load_marine_geometry_at_point(lon: float, lat: float) -> pd.DataFrame:
    """Load bbox-filtered candidates from the approved marine point bank."""
    domain = _active_domain_paths()
    if domain:
        bbox_candidates = read_bbox_candidates(
            domain["bbox_index"], float(lon), float(lat), columns=["loc_id"],
        )
        jurisdiction_ids = (
            set(bbox_candidates["loc_id"].astype(str))
            if bbox_candidates is not None and not bbox_candidates.empty else set()
        )
        jurisdiction_columns = [
            "loc_id", "name", "geometry_wkb", "area_km2",
            "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
        ]
        frames = [read_rows_by_ids(
            domain["point_bank"],
            jurisdiction_ids,
            id_column="loc_id",
            columns=jurisdiction_columns,
        )]
        frames.extend([
            read_bbox_candidates(
                domain["water_bodies"], float(lon), float(lat),
                columns=["loc_id", "name", "geometry", "centroid_lon", "centroid_lat"],
            ),
            read_bbox_candidates(
                domain["named_water_areas"], float(lon), float(lat),
                columns=["loc_id", "name", "geometry", "centroid_lon", "centroid_lat"],
            ),
        ])
    else:
        return pd.DataFrame(columns=_MARINE_POINT_COLUMNS)
    frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=_MARINE_POINT_COLUMNS)
    return pd.concat(frames, ignore_index=True).reset_index(drop=True)


def load_marine_geometry_for_points(
    points: Iterable[dict],
) -> tuple[pd.DataFrame, dict[int, list[str]]] | None:
    """Hydrate unique marine candidates once for an entire point batch.

    The returned mapping associates input positions with candidate loc_ids.
    ``None`` means the catalog has not admitted a complete Marine query layout.
    """
    point_items = list(points or [])
    domain = _active_domain_paths()
    if not domain:
        return None
    if not point_items:
        return pd.DataFrame(columns=_MARINE_POINT_COLUMNS), {}

    candidate_ids: dict[int, set[str]] = {}
    frames: list[pd.DataFrame] = []

    jurisdiction_pairs = read_bbox_candidates_for_points(
        domain["bbox_index"], point_items, columns=["loc_id"],
    )
    jurisdiction_ids = set(jurisdiction_pairs["loc_id"].astype(str)) if not jurisdiction_pairs.empty else set()
    jurisdiction_frame = pd.DataFrame(columns=_MARINE_POINT_COLUMNS)
    if jurisdiction_ids:
        jurisdiction_frame = read_rows_by_ids(
            domain["point_bank"], jurisdiction_ids,
            id_column="loc_id",
            columns=[
                "name", "geometry_wkb", "area_km2",
                "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
            ],
        )
        frames.append(jurisdiction_frame)
    for position, loc_ids in _exact_jurisdiction_matches(point_items, jurisdiction_frame).items():
        candidate_ids.setdefault(position, set()).update(loc_ids)

    water_columns = ["loc_id", "name", "geometry", "centroid_lon", "centroid_lat"]
    for path in (domain["water_bodies"], domain["named_water_areas"]):
        # These are compact physical-water banks (172 total polygons). DuckDB
        # can do exact containment during each bank's only scan, leaving the
        # larger overlapping jurisdiction family on its separate path.
        pairs = read_geojson_containment_for_points(path, point_items, columns=water_columns)
        if not pairs.empty:
            frames.append(
                pairs.drop(columns=["point_position"], errors="ignore")
                .drop_duplicates(subset=["loc_id"], keep="first")
            )
        for row in pairs.to_dict("records"):
            candidate_ids.setdefault(int(row["point_position"]), set()).add(str(row["loc_id"]))

    hydrated = [frame for frame in frames if frame is not None and not frame.empty]
    combined = (
        pd.concat(hydrated, ignore_index=True).drop_duplicates(subset=["loc_id"], keep="first")
        if hydrated else pd.DataFrame(columns=_MARINE_POINT_COLUMNS)
    )
    return combined.reset_index(drop=True), {
        position: sorted(ids) for position, ids in candidate_ids.items()
    }


def _exact_jurisdiction_matches(
    points: list[dict[str, Any]],
    jurisdictions: pd.DataFrame,
) -> dict[int, set[str]]:
    """Bulk-test hydrated jurisdiction shapes once with an in-memory STRtree."""
    if jurisdictions is None or jurisdictions.empty or not points:
        return {}
    from shapely import STRtree, from_wkb, points as make_points

    shapes = jurisdictions.dropna(subset=["loc_id", "geometry_wkb"]).drop_duplicates(
        subset=["loc_id"], keep="first",
    )
    if shapes.empty:
        return {}
    shape_values = from_wkb([bytes(value) for value in shapes["geometry_wkb"]])
    point_positions: list[int] = []
    coordinates: list[tuple[float, float]] = []
    for position, point in enumerate(points):
        try:
            coordinates.append((float(point["lon"]), float(point["lat"])))
            point_positions.append(position)
        except (KeyError, TypeError, ValueError):
            continue
    if not coordinates:
        return {}
    pair_indexes = STRtree(shape_values).query(
        make_points(coordinates), predicate="covered_by",
    )

    loc_ids = shapes["loc_id"].astype(str).tolist()
    matches: dict[int, set[str]] = {}
    for point_index, shape_index in zip(pair_indexes[0], pair_indexes[1]):
        position = point_positions[int(point_index)]
        matches.setdefault(position, set()).add(loc_ids[int(shape_index)])
    return matches


def load_marine_geometry(loc_ids: Optional[Iterable[str]] = None, *, columns: Optional[list[str]] = None) -> pd.DataFrame:
    """Load marine geometry rows for the given loc_ids (or all marine geometry).

    Returns columns [loc_id, name, geometry, centroid_lon, centroid_lat]. Only
    the bank(s) actually referenced by the requested loc_ids are read, so an
    EEZ-only query never touches the water-body bank and vice versa. Callers
    that only need availability metadata can omit the heavy geometry column.
    """
    want = {str(x).strip() for x in loc_ids} if loc_ids is not None else None
    need_eez = want is None or any(is_marine_jurisdiction_loc_id(x) for x in want)
    need_wb = want is None or any(is_water_body_loc_id(x) for x in want)
    need_named_water = want is None or any(is_named_water_loc_id(x) for x in want)

    domain = _active_domain_paths()
    if not domain:
        return pd.DataFrame(columns=columns or _MARINE_COLUMNS)
    frames = []
    if need_eez:
        jurisdiction_banks = {marine_bank_for_loc_id(value) for value in want} if want is not None else {
            domain["jurisdictions"]
        }
        frames.extend(_read_bank(path, want, columns=columns) for path in jurisdiction_banks if path is not None)
    if need_wb:
        frames.append(_read_bank(domain["water_bodies"], want, columns=columns))
    if need_named_water:
        frames.append(_read_bank(domain["named_water_areas"], want, columns=columns))
    if not frames:
        return pd.DataFrame(columns=columns or _MARINE_COLUMNS)
    return pd.concat(frames, ignore_index=True).reset_index(drop=True)
