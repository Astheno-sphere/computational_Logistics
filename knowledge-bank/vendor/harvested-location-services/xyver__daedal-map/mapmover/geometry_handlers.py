"""
Geometry endpoint handlers.
Handles loading geometry files and country hierarchy for drill-down navigation.

Data sources (resolved via paths.py DATA_ROOT):
  geometry/global/display/admin_0.parquet - bounded Admin0 map/display geometry
  geometry/global/exact/admin_0.parquet - full-detail Admin0 product
  geometry/{ISO3}.parquet          - global-fallback Admin0-2 country shards

Schema (13 columns):
  loc_id, parent_id, admin_level, name, name_local, code, iso_3166_2,
  centroid_lon, centroid_lat, has_polygon, geometry, timezone, iso_a3
"""

import json
import logging
import os
import threading
import time
import pandas as pd
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

# Try orjson for faster JSON parsing (3-10x faster than stdlib json)
try:
    import orjson
    def fast_json_loads(s):
        return orjson.loads(s)
except ImportError:
    def fast_json_loads(s):
        return json.loads(s)

from .paths import COUNTRY_GEOMETRY_DIR, GEOMETRY_DIR, DATA_ROOT, COUNTRIES_DIR
from .duckdb_helpers import is_cloud_mode, parquet_columns, select_rows
from .foundation_helpers import (
    load_country_crosswalk,
    load_global_country_display_frame,
    load_global_countries_frame,
    load_reference_json,
    load_world_factbook_static_frame,
)
from .runtime.geography_reference import (
    build_crosswalk_maps,
    canonicalize_loc_id,
    classify_loc_id_family,
    translate_geometry_id_to_local_id,
    translate_loc_id_to_geometry_id,
)
from .runtime.country_geography import (
    get_country_level_config,
    get_country_sub_admin_levels,
    get_country_supported_deep_admin_levels,
)
from .runtime.admin_spine_query import (
    layout_available as admin_spine_layout_available,
    load_rows_by_loc_ids as load_admin_spine_query_rows,
    resolve_point as resolve_admin_spine_query_point,
    resolve_points as resolve_admin_spine_query_points,
)
from .runtime.geometry_loader import (
    resolve_country_display_geometry_source,
    resolve_country_display_geometry_sources,
    resolve_country_geometry_source,
)
from .runtime.geometry_compatibility import (
    load_current_alias_target_rows,
    load_legacy_geometry_rows,
    requested_aliases,
    retained_legacy_loc_ids,
)
from .runtime.geometry_spine import geometry_spine_index_for_frame, match_point_in_frame
from .runtime.global_admin0_query import (
    load_global_admin0_geometries,
    load_global_admin0_identities,
    resolve_global_admin0_query_points,
)
from .runtime.marine_geometry import load_marine_geometry
from .runtime.reference_geometry_bank import load_reference_graph_geometry
from .runtime.read_posture import geometry_read_mode, prefer_local_geometry_reads

logger = logging.getLogger("mapmover")

# Cache for country parquet data - keyed by (iso3, admin_level) or just iso3 for full
_country_parquet_cache = OrderedDict()
_country_parquet_cache_lock = threading.Lock()
_country_parquet_inflight = set()  # keys currently being fetched from R2
_country_parquet_waiters = {}  # key -> Event for concurrent waiters

# Cache for country bounding boxes (for viewport filtering)
_country_bounds_cache = None

_GEOMETRY_CACHE_MAX_BYTES = max(32 * 1024 * 1024, int(float(os.environ.get("GEOMETRY_CACHE_MAX_MB", "256")) * 1024 * 1024))
GEOMETRY_INDEX_COLUMNS = [
    "loc_id",
    "local_loc_id",
    "source_loc_id",
    "parent_id",
    "admin_level",
    "name",
    "code",
    "iso_3166_2",
    "bbox_min_lon",
    "bbox_min_lat",
    "bbox_max_lon",
    "bbox_max_lat",
    "centroid_lon",
    "centroid_lat",
    "has_polygon",
    "iso_a3",
]

# Smallest physical projection that can resolve a point and return a useful
# hierarchy row.  In particular, do not use ``SELECT *`` against monolithic
# country spines: Australia stores all seven admin levels in one ~938 MB
# parquet and several optional metadata columns are much wider than a point
# lookup needs.
POINT_RESOLUTION_COLUMNS = list(GEOMETRY_INDEX_COLUMNS)
POINT_RESOLUTION_COLUMNS.append("geometry")

GEOMETRY_METADATA_COLUMNS = list(GEOMETRY_INDEX_COLUMNS)
GEOMETRY_METADATA_COLUMNS.extend([
    "subtype",
    "source_native_subtype",
    "children_count",
    "children_by_level",
    "descendants_count",
    "descendants_by_level",
    "land_area",
    "water_area",
    "valid_from",
    "valid_to",
    "valid_from_date",
    "valid_to_date",
    "geometry_vintage",
    "source_vintage",
    "reference_date",
    "source_id",
    "source_system",
    "geometry_source",
    "geometry_bank",
    "bank_id",
    "release_id",
    "geography_release_id",
    "lifecycle_status",
    "superseded_by",
    "successor_loc_id",
    "lineage",
])


def _project_frame(df, columns: list[str] | None):
    if df is None or not columns:
        return df
    available = [column for column in columns if column in df.columns]
    return df[available].copy() if available else pd.DataFrame(columns=columns)


def _ensure_loc_id_projection(columns: list[str] | None) -> list[str] | None:
    if not columns:
        return None
    selected = list(dict.fromkeys(columns))
    if "loc_id" not in selected:
        selected.insert(0, "loc_id")
    return selected


def _physical_parquet_columns(path: Path, columns: list[str] | None) -> list[str] | None:
    if not columns:
        return None
    try:
        available_columns = parquet_columns(path)
    except Exception:
        return columns
    return [column for column in columns if column in available_columns]


def _frame_bytes(df) -> int:
    try:
        return int(df.memory_usage(index=True, deep=True).sum())
    except Exception:
        return 0


def _cache_country_frame(cache_key, df) -> None:
    """Insert a geometry frame and evict least-recently-used frames by size."""
    _country_parquet_cache[cache_key] = df
    _country_parquet_cache.move_to_end(cache_key)
    total = sum(_frame_bytes(value) for value in _country_parquet_cache.values())
    while total > _GEOMETRY_CACHE_MAX_BYTES and len(_country_parquet_cache) > 1:
        _, evicted = _country_parquet_cache.popitem(last=False)
        total -= _frame_bytes(evicted)


def _cached_country_admin_frame(iso3: str, admin_level: int):
    """Return an already-warmed complete admin-level frame when available.

    Bulk point resolution previously bypassed the DataFrame cache by always
    issuing a viewport query.  That meant the startup-warmed USA county bank
    could help map/NWS calls but not MCP or REST reverse geocoding.  Only known
    complete-frame keys are eligible here; viewport fragments are never stored
    under these keys and therefore cannot poison later requests.
    """
    normalized = str(iso3 or "").strip().upper()
    keys = [(normalized, int(admin_level))]
    if normalized == "USA" and int(admin_level) == 2:
        keys.insert(0, ("exact_county", "USA"))
    with _country_parquet_cache_lock:
        for key in keys:
            cached = _country_parquet_cache.get(key)
            if cached is not None:
                _country_parquet_cache.move_to_end(key)
                return cached
    return None


def _geometry_read_mode() -> str:
    return geometry_read_mode()


def _prefer_local_geometry_reads() -> bool:
    return prefer_local_geometry_reads()

def _parquet_accessible(path: Path) -> bool:
    """Returns True if a parquet file exists locally or is accessible via S3/DuckDB."""
    if path.exists():
        return True
    if not is_cloud_mode():
        return False
    try:
        cols = parquet_columns(path)
        return bool(cols)
    except Exception:
        return False


def get_geometry_path():
    """Get the geometry folder path using centralized path resolution."""
    if GEOMETRY_DIR.exists():
        return GEOMETRY_DIR
    return None


def load_country_parquet(iso3: str, admin_level: int = None, columns: list[str] | None = None):
    """
    Load country geometry parquet file into cache.
    Returns DataFrame or None if file doesn't exist.

    Priority order:
    1. geometry/countries/{ISO3}/admin_spine/admin_0_3.parquet - released country authority
    2. geometry/countries/{ISO3}/geometry.parquet - legacy country-specific geometry
    3. geometry/countries/{ISO3}/crosswalk.json + geometry/{ISO3}.parquet
    4. geometry/{ISO3}.parquet - global GeoBoundaries fallback

    If admin_level is specified, uses predicate pushdown for efficiency.
    """
    columns = _ensure_loc_id_projection(columns)
    projected_read = bool(columns)

    # Check cache - if admin_level specified, cache by (iso3, level). Projected
    # reads get their own cache key so they never masquerade as full geometry.
    full_cache_key = (iso3, admin_level) if admin_level is not None else iso3
    cache_key = (
        (full_cache_key, tuple(columns))
        if projected_read and columns
        else full_cache_key
    )
    wait_event = None
    owns_fetch = False

    with _country_parquet_cache_lock:
        if cache_key in _country_parquet_cache:
            _country_parquet_cache.move_to_end(cache_key)
            return _country_parquet_cache[cache_key]

        if projected_read and full_cache_key in _country_parquet_cache:
            _country_parquet_cache.move_to_end(full_cache_key)
            return _project_frame(_country_parquet_cache[full_cache_key], columns)

        # If we have the full dataframe cached, filter from it
        if admin_level is not None and iso3 in _country_parquet_cache:
            full_df = _country_parquet_cache[iso3]
            filtered = full_df[full_df['admin_level'] == admin_level]
            if not projected_read:
                _cache_country_frame(full_cache_key, filtered)
            return _project_frame(filtered, columns)

        # If another thread is already fetching this key, wait for it to finish
        # so repeated hot geometry requests reuse the same cold-load work.
        if cache_key in _country_parquet_inflight:
            wait_event = _country_parquet_waiters.get(cache_key)
        else:
            _country_parquet_inflight.add(cache_key)
            wait_event = threading.Event()
            _country_parquet_waiters[cache_key] = wait_event
            owns_fetch = True

    if not owns_fetch:
        if wait_event is not None:
            wait_event.wait(timeout=15.0)
        with _country_parquet_cache_lock:
            if cache_key in _country_parquet_cache:
                _country_parquet_cache.move_to_end(cache_key)
                return _country_parquet_cache[cache_key]
            if projected_read and full_cache_key in _country_parquet_cache:
                _country_parquet_cache.move_to_end(full_cache_key)
                return _project_frame(_country_parquet_cache[full_cache_key], columns)
            if admin_level is not None and iso3 in _country_parquet_cache:
                full_df = _country_parquet_cache[iso3]
                filtered = full_df[full_df['admin_level'] == admin_level]
                if not projected_read:
                    _cache_country_frame(full_cache_key, filtered)
                return _project_frame(filtered, columns)
        return None

    resolved = resolve_country_geometry_source(iso3, admin_level=admin_level)
    parquet_file = resolved["parquet_file"]
    crosswalk_data = resolved["crosswalk"]

    if parquet_file is None:
        logger.debug(f"No geometry file found for {iso3}")
        with _country_parquet_cache_lock:
            _country_parquet_inflight.discard(cache_key)
            waiter = _country_parquet_waiters.pop(cache_key, None)
        if waiter is not None:
            waiter.set()
        return None
    logger.debug(f"Using {resolved['source_kind']} geometry: {parquet_file}")
    read_columns = None
    if columns:
        try:
            available_columns = parquet_columns(parquet_file)
            read_columns = [column for column in columns if column in available_columns]
        except Exception:
            read_columns = columns

    try:
        # Use predicate pushdown if admin_level specified
        if admin_level is not None:
            if parquet_file.exists():
                df = pd.read_parquet(
                    parquet_file,
                    columns=read_columns,
                    filters=[('admin_level', '==', admin_level)]
                )
            else:
                df = select_rows(
                    parquet_file,
                    columns=read_columns,
                    exact_filters={"admin_level": admin_level},
                )
        else:
            if parquet_file.exists():
                df = pd.read_parquet(parquet_file, columns=read_columns)
            else:
                if is_cloud_mode():
                    df = select_rows(parquet_file, columns=read_columns)
                else:
                    df = pd.read_parquet(parquet_file, columns=read_columns)

        # If a crosswalk exists, add the reverse mapping so country-family
        # loc_ids can resolve against the admitted global-baseline bank.
        if crosswalk_data:
            _, reverse_map = build_crosswalk_maps(crosswalk_data)
            # Add local_loc_id column for joining
            if "loc_id" in df.columns:
                df['local_loc_id'] = df['loc_id'].map(reverse_map)
            logger.debug(f"Applied crosswalk: {len(reverse_map)} mappings")

        # In S3 mode, do not cache empty DataFrames - an empty result from a cold
        # DuckDB/R2 fetch is likely a transient failure, not "this country has no data".
        # Caching empty would poison the cache and serve 0 features for the rest of
        # the container's lifetime. Local mode is fine to cache empty (data truly absent).
        if df.empty and is_cloud_mode():
            logger.warning(f"Empty geometry result for {iso3} (level={admin_level}) in S3 mode - not caching")
            with _country_parquet_cache_lock:
                _country_parquet_inflight.discard(cache_key)
                waiter = _country_parquet_waiters.pop(cache_key, None)
            if waiter is not None:
                waiter.set()
            return df  # Return empty but do NOT cache, so next request retries

        with _country_parquet_cache_lock:
            _cache_country_frame(cache_key, df)
            _country_parquet_inflight.discard(cache_key)
            waiter = _country_parquet_waiters.pop(cache_key, None)
        if waiter is not None:
            waiter.set()
        logger.debug(f"Loaded {len(df)} features for {iso3} (level={admin_level}) from {parquet_file.name}")
        return df
    except Exception as e:
        logger.error(f"Error loading geometry for {iso3}: {e}")
        with _country_parquet_cache_lock:
            _country_parquet_inflight.discard(cache_key)
            waiter = _country_parquet_waiters.pop(cache_key, None)
        if waiter is not None:
            waiter.set()
        return None


def load_country_parquet_viewport(iso3: str, admin_level: int | None, bbox: tuple, columns: list[str] | None = None):
    """
    Load only geometry rows that intersect a viewport bbox.

    This is stricter than load_country_parquet(): it pushes bbox filtering into DuckDB so
    large countries like USA admin_2 do not need to load the whole level slice first.
    Passing ``admin_level=None`` performs one bounded scan across all levels, which is
    substantially cheaper for a monolithic multi-level spine than reopening it once
    per level.
    """
    min_lon, min_lat, max_lon, max_lat = bbox

    resolved = resolve_country_geometry_source(iso3, admin_level=admin_level)
    parquet_file = resolved["parquet_file"]
    crosswalk_data = resolved["crosswalk"]
    if parquet_file is None:
        return None


    columns = _ensure_loc_id_projection(columns)

    try:
        available_cols = parquet_columns(parquet_file)
        read_columns = [column for column in (columns or []) if column in available_cols] or None
        has_bbox = all(
            col in available_cols
            for col in ("bbox_min_lon", "bbox_max_lon", "bbox_min_lat", "bbox_max_lat")
        )
        has_centroid = "centroid_lon" in available_cols and "centroid_lat" in available_cols

        compare_filters = []
        if has_bbox:
            compare_filters = [
                ("bbox_max_lon", ">=", min_lon),
                ("bbox_min_lon", "<=", max_lon),
                ("bbox_max_lat", ">=", min_lat),
                ("bbox_min_lat", "<=", max_lat),
            ]
        elif has_centroid:
            compare_filters = [
                ("centroid_lon", ">=", min_lon),
                ("centroid_lon", "<=", max_lon),
                ("centroid_lat", ">=", min_lat),
                ("centroid_lat", "<=", max_lat),
            ]

        # PyArrow can stream-filter very wide local row groups without first
        # constructing DuckDB's full VARCHAR vector.  This matters for the
        # adopted AUS spine whose first mixed-level row group is ~577 MB
        # uncompressed: a bounded three-row point query otherwise requests a
        # 512 MB allocation under the runtime's 488 MB DuckDB ceiling.
        # Always use Arrow for a real local file. New authority releases use
        # GeoParquet's native GEOMETRY logical type; current DuckDB can query
        # it, but converting that typed column directly to a NumPy-backed frame
        # raises ``Unsupported type GEOMETRY``. Arrow preserves the geometry
        # payload and predicate pushdown for both small and large local banks.
        # DuckDB remains the bounded path for cloud URIs/non-local sources.
        use_local_pushdown = parquet_file.exists()
        if use_local_pushdown:
            filters = []
            if admin_level is not None:
                filters.append(("admin_level", "==", admin_level))
            if has_bbox:
                filters.extend([
                    ("bbox_max_lon", ">=", min_lon),
                    ("bbox_min_lon", "<=", max_lon),
                    ("bbox_max_lat", ">=", min_lat),
                    ("bbox_min_lat", "<=", max_lat),
                ])
            elif has_centroid:
                filters.extend([
                    ("centroid_lon", ">=", min_lon),
                    ("centroid_lon", "<=", max_lon),
                    ("centroid_lat", ">=", min_lat),
                    ("centroid_lat", "<=", max_lat),
                ])
            df = pd.read_parquet(parquet_file, columns=read_columns, filters=filters)
        else:
            df = select_rows(
                parquet_file,
                columns=read_columns,
                exact_filters={"admin_level": admin_level} if admin_level is not None else None,
                compare_filters=compare_filters,
            )

        if crosswalk_data and not df.empty:
            _, reverse_map = build_crosswalk_maps(crosswalk_data)
            if "loc_id" in df.columns:
                df['local_loc_id'] = df['loc_id'].map(reverse_map)

        return df
    except Exception as e:
        logger.error(f"Error loading viewport geometry for {iso3} level={admin_level}: {e}")
        return None


def _display_owner_for_loc_id(loc_id: str | None) -> str | None:
    """Return the first-level physical shard owner used by Display releases."""
    parts = str(loc_id or "").strip().split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else None


def _country_display_sources(
    iso3: str,
    *,
    admin_level: int | None = None,
    parent_ids: set[str] | None = None,
    loc_ids: list[str] | None = None,
) -> tuple[list[Path], dict | None, str]:
    """Select admitted Display banks, then the GeoBoundaries display fallback.

    The fallback is intentionally the legacy ``geometry/{ISO3}.parquet``
    display shard. It never consults ``admin_spine`` or a Full release.
    """
    owners = {
        owner
        for owner in (
            _display_owner_for_loc_id(value)
            for value in [*(parent_ids or set()), *(loc_ids or [])]
        )
        if owner
    }
    release_paths: list[Path] = []
    root_only = bool(parent_ids) and all("-" not in str(value) for value in parent_ids)
    if root_only:
        release_paths = resolve_country_display_geometry_sources(
            iso3, admin_level=admin_level, physical_owner="national"
        )
    elif len(owners) == 1:
        release_paths = resolve_country_display_geometry_sources(
            iso3, admin_level=admin_level, physical_owner=next(iter(owners))
        )
    if not release_paths:
        release_paths = resolve_country_display_geometry_sources(iso3, admin_level=admin_level)
    if release_paths:
        return release_paths, None, "country_display_release"

    fallback = GEOMETRY_DIR / f"{str(iso3).upper()}.parquet"
    if _parquet_accessible(fallback):
        return [fallback], load_country_crosswalk(iso3), "geoboundaries_display_fallback"
    return [], None, "missing"


def load_country_display_rows(
    iso3: str,
    *,
    admin_level: int | None = None,
    parent_ids: set[str] | None = None,
    loc_ids: list[str] | None = None,
    bbox: tuple | None = None,
    columns: list[str] | None = None,
):
    """Read simplified rows for a browser/display payload only.

    Active country Display releases own enriched countries. The original
    GeoBoundaries country shard remains the global default for countries that
    do not yet publish a Display family. Full/query banks are never candidates.
    """
    normalized = str(iso3 or "").strip().upper()
    requested_ids = [canonicalize_loc_id(value) for value in (loc_ids or []) if value]
    if requested_ids:
        requested_set = set(requested_ids)
        cached_frames = []
        with _country_parquet_cache_lock:
            for key, cached in _country_parquet_cache.items():
                if not (
                    isinstance(key, tuple)
                    and len(key) == 3
                    and key[0] == "display_admin"
                    and key[1] == normalized
                ):
                    continue
                if cached is not None and "loc_id" in cached.columns:
                    rows = cached[cached["loc_id"].isin(requested_set)]
                    if not rows.empty:
                        cached_frames.append(rows)
        if cached_frames:
            cached_result = pd.concat(cached_frames, ignore_index=True).drop_duplicates(subset=["loc_id"])
            if requested_set.issubset(set(cached_result["loc_id"].astype(str))):
                cached_result.attrs["geometry_source_kind"] = "country_display_release_cache"
                return _project_frame(cached_result, columns)
    paths, crosswalk_data, source_kind = _country_display_sources(
        normalized,
        admin_level=admin_level,
        parent_ids=parent_ids,
        loc_ids=requested_ids,
    )
    if not paths:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for parquet_file in paths:
        try:
            available = parquet_columns(parquet_file, raw_geoparquet=True)
            read_columns = [column for column in (columns or []) if column in available] or None
            in_filters = {}
            if parent_ids:
                query_parents = sorted(parent_ids)
                if crosswalk_data:
                    local_to_geo, _ = build_crosswalk_maps(crosswalk_data)
                    query_parents = [local_to_geo.get(value, value) for value in query_parents]
                in_filters["parent_id"] = query_parents
            if requested_ids:
                query_ids = requested_ids
                if crosswalk_data:
                    local_to_geo, _ = build_crosswalk_maps(crosswalk_data)
                    query_ids = [local_to_geo.get(value, value) for value in requested_ids]
                in_filters["loc_id"] = query_ids
            compare_filters = None
            if bbox:
                min_lon, min_lat, max_lon, max_lat = bbox
                if all(column in available for column in ("bbox_min_lon", "bbox_max_lon", "bbox_min_lat", "bbox_max_lat")):
                    compare_filters = [
                        ("bbox_max_lon", ">=", min_lon),
                        ("bbox_min_lon", "<=", max_lon),
                        ("bbox_max_lat", ">=", min_lat),
                        ("bbox_min_lat", "<=", max_lat),
                    ]
            if parquet_file.exists():
                filters = []
                if admin_level is not None:
                    filters.append(("admin_level", "==", admin_level))
                for column, values in in_filters.items():
                    filters.append((column, "in", list(values)))
                filters.extend(compare_filters or [])
                frame = pd.read_parquet(parquet_file, columns=read_columns, filters=filters)
            else:
                frame = select_rows(
                    parquet_file,
                    columns=read_columns,
                    exact_filters={"admin_level": admin_level} if admin_level is not None else None,
                    in_filters=in_filters or None,
                    compare_filters=compare_filters,
                    raw_geoparquet=True,
                )
            if frame is not None and not frame.empty:
                frames.append(frame)
        except Exception:
            logger.warning("Display geometry read failed for %s from %s", normalized, parquet_file, exc_info=True)

    nonempty = [frame for frame in frames if frame is not None and not frame.empty]
    result = pd.concat(nonempty, ignore_index=True).drop_duplicates(subset=["loc_id"]) if nonempty else pd.DataFrame()
    if result.empty:
        return result
    if crosswalk_data and "loc_id" in result.columns:
        _, geo_to_local = build_crosswalk_maps(crosswalk_data)
        result = result.copy()
        result["source_loc_id"] = result["loc_id"]
        result["local_loc_id"] = result["loc_id"].map(geo_to_local)
        result["loc_id"] = result["local_loc_id"].fillna(result["loc_id"])
    result.attrs["geometry_source_kind"] = source_kind
    return result


def _resolve_geometry_source(iso3: str):
    """Resolve the parquet source and optional crosswalk for a country geometry lookup."""
    country_geom_file = DATA_ROOT / "geometry" / "countries" / iso3 / "geometry.parquet"
    crosswalk_file = DATA_ROOT / "geometry" / "countries" / iso3 / "crosswalk.json"
    global_geom_file = GEOMETRY_DIR / f"{iso3}.parquet"

    if _parquet_accessible(country_geom_file):
        return country_geom_file, None

    if crosswalk_file.exists() and _parquet_accessible(global_geom_file):
        crosswalk_data = load_country_crosswalk(iso3)
        return global_geom_file, crosswalk_data

    if _parquet_accessible(global_geom_file):
        return global_geom_file, None

    return None, None


def _concat_geometry_frames(frames: list[pd.DataFrame], requested_ids: list[str]) -> pd.DataFrame:
    nonempty = [frame for frame in frames if frame is not None and not frame.empty]
    if not nonempty:
        return pd.DataFrame()
    combined = pd.concat(nonempty, ignore_index=True)
    if "loc_id" not in combined.columns:
        return combined
    requested_set = {str(loc_id).strip() for loc_id in requested_ids if str(loc_id).strip()}
    if requested_set:
        combined = combined[combined["loc_id"].astype(str).isin(requested_set)]
    if combined.empty:
        return combined
    return combined.drop_duplicates(subset=["loc_id"]).reset_index(drop=True)


def _direct_family_bank_path(family: str | None, iso3: str) -> Path | None:
    family_value = str(family or "").strip().lower()
    iso3_value = str(iso3 or "").strip().upper()
    if family_value == "overlay_zcta" and iso3_value:
        return DATA_ROOT / "geometry" / "countries" / iso3_value / "zcta" / f"{iso3_value}.parquet"
    if family_value == "overlay_tribal" and iso3_value:
        return DATA_ROOT / "geometry" / "countries" / iso3_value / "tribal" / f"{iso3_value}.parquet"
    if family_value == "overlay_nws_public_zone" and iso3_value:
        return DATA_ROOT / "geometry" / "countries" / iso3_value / "nws_public_zone" / f"{iso3_value}.parquet"
    if family_value == "overlay_nws_fire_weather_zone" and iso3_value:
        return DATA_ROOT / "geometry" / "countries" / iso3_value / "nws_fire_weather_zone" / f"{iso3_value}.parquet"
    if family_value == "can_federal_electoral_district_2013" and iso3_value == "CAN":
        return DATA_ROOT / "geometry" / "countries" / "CAN" / "federal_electoral_district_2013" / "CAN.parquet"
    if family_value == "can_designated_place" and iso3_value == "CAN":
        return DATA_ROOT / "geometry" / "countries" / "CAN" / "designated_place" / "CAN.parquet"
    return None


def _is_marine_family(family: str | None) -> bool:
    return str(family or "").strip().lower() in {"marine_eez", "water_body"}


@lru_cache(maxsize=65536)
def _geometry_family_for_loc_id(loc_id: str) -> str | None:
    """Prefer an explicit graph family, then fall back to legacy prefixes."""
    # Explicit namespaces are authoritative and free to classify. Consulting
    # a multi-million-row reference graph once per requested ID defeats every
    # benefit of a set-based Parquet query (notably 10k ZCTA shape batches).
    syntactic_family = classify_loc_id_family(loc_id)
    if syntactic_family not in {None, "admin_local", "admin_geometry"}:
        return syntactic_family
    try:
        from .runtime.reference_graph import identity as graph_identity

        row = graph_identity(loc_id) or {}
        family = str(row.get("geography_family") or row.get("family") or "").strip()
        if family:
            return family
    except Exception:
        pass
    return syntactic_family


_UNSET_GEOMETRY_COLUMNS = object()


def _load_marine_or_reference_geometry(loc_ids: list[str], columns=_UNSET_GEOMETRY_COLUMNS) -> pd.DataFrame:
    """Load established marine banks, then graph-owned banks for unresolved ids."""
    marine = (
        load_marine_geometry(loc_ids, columns=columns)
        if columns is not _UNSET_GEOMETRY_COLUMNS
        else load_marine_geometry(loc_ids)
    )
    found = set(marine["loc_id"].astype(str)) if marine is not None and not marine.empty and "loc_id" in marine else set()
    missing = [loc_id for loc_id in loc_ids if loc_id not in found]
    reference_columns = None if columns is _UNSET_GEOMETRY_COLUMNS else columns
    reference = load_reference_graph_geometry(missing, columns=reference_columns) if missing else pd.DataFrame()
    return _concat_geometry_frames([marine, reference], loc_ids)


def load_geometry_rows_by_loc_ids(iso3: str, loc_ids: list[str], columns: list[str] | None = None):
    """
    Load exact geometry rows for a country by loc_id list.

    This is the robust exact-fetch path used by diff loading:
    - no full country parquet load
    - loc_id exact-match pushdown in DuckDB / parquet filters
    """
    requested_ids = [canonicalize_loc_id(loc_id) for loc_id in loc_ids if loc_id]
    if not requested_ids:
        return pd.DataFrame()
    columns = _ensure_loc_id_projection(columns)

    # Released GeoBoundaries v2 ids remain valid after the exact-2026 bank
    # promotion. Resolve deterministic aliases through the active bank and
    # source-only gbOpen features through the small exact compatibility bank.
    alias_requests = requested_aliases(requested_ids)
    legacy_ids = retained_legacy_loc_ids()
    requested_legacy = [loc_id for loc_id in requested_ids if loc_id in legacy_ids]
    if alias_requests or requested_legacy:
        compatibility_sources = set(alias_requests) | set(requested_legacy)
        direct_requests = [loc_id for loc_id in requested_ids if loc_id not in compatibility_sources]
        frames: list[pd.DataFrame] = []
        if direct_requests:
            direct_rows = load_geometry_rows_by_loc_ids(iso3, direct_requests, columns=columns)
            if direct_rows is not None and not direct_rows.empty:
                frames.append(direct_rows)
        if alias_requests:
            target_rows = load_current_alias_target_rows(alias_requests.values(), columns=columns)
            if target_rows is not None and not target_rows.empty and "loc_id" in target_rows:
                for source_loc_id, target_loc_id in alias_requests.items():
                    matched_target = target_rows[
                        target_rows["loc_id"].astype(str).eq(target_loc_id)
                    ].copy()
                    if matched_target.empty:
                        continue
                    matched_target["source_loc_id"] = target_loc_id
                    matched_target["loc_id"] = source_loc_id
                    matched_target["compatibility_target_loc_id"] = target_loc_id
                    frames.append(matched_target)
        legacy_rows = load_legacy_geometry_rows(requested_legacy, columns=columns)
        if legacy_rows is not None and not legacy_rows.empty:
            frames.append(legacy_rows)
        return _concat_geometry_frames(frames, requested_ids)

    prefer_local = _prefer_local_geometry_reads()

    families = {_geometry_family_for_loc_id(loc_id) for loc_id in requested_ids}
    families.discard(None)

    if len(families) > 1:
        family_groups: dict[str | None, list[str]] = {}
        for loc_id in requested_ids:
            family_groups.setdefault(_geometry_family_for_loc_id(loc_id), []).append(loc_id)

        frames: list[pd.DataFrame] = []
        for family, family_ids in family_groups.items():
            if not family_ids or family == "event_or_entity":
                continue
            if _is_marine_family(family):
                frames.append(_load_marine_or_reference_geometry(family_ids, columns=columns))
                continue
            frames.append(load_geometry_rows_by_loc_ids(iso3, family_ids, columns=columns))
        return _concat_geometry_frames(frames, requested_ids)

    def _load_direct_family_bank(parquet_file: Path) -> pd.DataFrame:
        read_columns = _physical_parquet_columns(parquet_file, columns)
        try:
            # Keep local and cloud execution on the same DuckDB planner. A
            # pandas/PyArrow local shortcut hides row-group and predicate
            # regressions from the very benchmarks intended to catch them.
            df = select_rows(
                parquet_file,
                columns=read_columns,
                in_filters={"loc_id": requested_ids},
            )
        except Exception as e:
            logger.error(f"Error loading geometry rows from {parquet_file}: {e}")
            df = pd.DataFrame()
        return df if df is not None else pd.DataFrame()

    direct_family = next(iter(families), None) if len(families) == 1 else None
    direct_family_bank = _direct_family_bank_path(direct_family, iso3)
    if direct_family_bank is not None:
        if (prefer_local and direct_family_bank.exists()) or _parquet_accessible(direct_family_bank):
            return _load_direct_family_bank(direct_family_bank)
        return pd.DataFrame()

    if _is_marine_family(direct_family):
        return _load_marine_or_reference_geometry(requested_ids, columns=columns)

    # Any graph identity may own a partitioned reference-family bank. Consult
    # that explicit identity -> bank -> partition contract before falling back
    # to the country's administrative geometry. This keeps new semantic
    # families data-driven instead of extending a country/family allowlist.
    reference = load_reference_graph_geometry(requested_ids, columns=columns)
    if reference is not None and not reference.empty:
        is_admin_request = all(
            classify_loc_id_family(loc_id) in {"admin_geometry", "admin_local"}
            for loc_id in requested_ids
        )
        if is_admin_request and "local_loc_id" not in reference.columns:
            reference = reference.copy()
            reference["local_loc_id"] = reference["loc_id"]
        return reference

    admin_source = resolve_country_geometry_source(iso3, admin_level=2)
    county_geom_file = admin_source["parquet_file"]
    crosswalk_data = load_country_crosswalk(iso3) or {}
    local_to_geo, geo_to_local = build_crosswalk_maps(crosswalk_data)
    requested_set = set(requested_ids)

    # Query the shared authority spine in canonical/local id space, translating
    # a legacy global G-ID through the crosswalk only when the caller supplied
    # one. Exact graph-owned family geometry was already attempted above.
    if county_geom_file is not None and (
        (prefer_local and county_geom_file.exists()) or _parquet_accessible(county_geom_file)
    ):
        county_query_ids = []
        for loc_id in requested_ids:
            local_id = geo_to_local.get(loc_id, loc_id)
            if isinstance(local_id, str) and local_id.count("-") == 2:
                county_query_ids.append(local_id)

        if county_query_ids:
            try:
                # The live NWS overlay repeatedly resolves US county ids. A
                # bounded Railway prewarm can hold the Admin2 authority slice,
                # while every other caller still uses predicate pushdown.
                county_cache_key = ("exact_county", iso3)
                with _country_parquet_cache_lock:
                    cached_counties = _country_parquet_cache.get(county_cache_key)
                    if cached_counties is not None:
                        _country_parquet_cache.move_to_end(county_cache_key)
                if cached_counties is not None:
                    df = cached_counties[cached_counties["loc_id"].isin(county_query_ids)].copy()
                    df = _project_frame(df, columns)
                elif prefer_local and county_geom_file.exists():
                    read_columns = _physical_parquet_columns(county_geom_file, columns)
                    df = pd.read_parquet(
                        county_geom_file,
                        columns=read_columns,
                        filters=[("loc_id", "in", county_query_ids)],
                    )
                else:
                    read_columns = _physical_parquet_columns(county_geom_file, columns)
                    df = select_rows(
                        county_geom_file,
                        columns=read_columns,
                        in_filters={"loc_id": county_query_ids},
                    )

                if not df.empty:
                    df = df.copy()
                    df["source_loc_id"] = df["loc_id"]

                    def resolve_requested_county_id(source_value):
                        geo_value = local_to_geo.get(source_value)
                        if geo_value in requested_set:
                            return geo_value
                        if source_value in requested_set:
                            return source_value
                        return geo_value or source_value

                    df["loc_id"] = df["source_loc_id"].map(resolve_requested_county_id)
                    df = df[
                        df["loc_id"].isin(requested_set) |
                        df["source_loc_id"].isin(requested_set)
                    ]
                    if not df.empty:
                        return df
            except Exception as e:
                logger.error(f"Error loading county geometry rows for {iso3}: {e}")

    if prefer_local:
        country_geom_file = DATA_ROOT / "geometry" / "countries" / iso3 / "geometry.parquet"
        crosswalk_file = DATA_ROOT / "geometry" / "countries" / iso3 / "crosswalk.json"
        global_geom_file = GEOMETRY_DIR / f"{iso3}.parquet"
        if country_geom_file.exists():
            parquet_file, crosswalk_data = country_geom_file, None
        elif crosswalk_file.exists() and global_geom_file.exists():
            parquet_file, crosswalk_data = global_geom_file, load_country_crosswalk(iso3)
        elif global_geom_file.exists():
            parquet_file, crosswalk_data = global_geom_file, None
        else:
            parquet_file, crosswalk_data = None, None
    else:
        parquet_file, crosswalk_data = _resolve_geometry_source(iso3)
    if parquet_file is None:
        return pd.DataFrame()

    query_ids = requested_ids
    reverse_map = None

    if crosswalk_data:
        local_to_geo, reverse_map = build_crosswalk_maps(crosswalk_data)
        query_ids = [local_to_geo.get(loc_id, loc_id) for loc_id in requested_ids]

    try:
        if prefer_local and parquet_file.exists():
            read_columns = _physical_parquet_columns(parquet_file, columns)
            df = pd.read_parquet(
                parquet_file,
                columns=read_columns,
                filters=[("loc_id", "in", query_ids)],
            )
        else:
            read_columns = _physical_parquet_columns(parquet_file, columns)
            df = select_rows(
                parquet_file,
                columns=read_columns,
                in_filters={"loc_id": query_ids},
            )

        # A country-specific spine has priority, but it is not necessarily a
        # complete replacement for the global GeoBoundaries namespace. Data
        # packs can intentionally retain global Admin1/Admin2 affected-area
        # ids. Resolve only the rows the adopted country bank did not contain
        # from the global bank, preserving the caller's requested id space.
        # This is a row-level fallback; it never lets global geometry shadow a
        # country row that was found successfully.
        found_ids = set(df["loc_id"].astype(str)) if not df.empty and "loc_id" in df else set()
        missing_global_ids = [
            loc_id
            for loc_id in query_ids
            if loc_id not in found_ids and classify_loc_id_family(loc_id) == "admin_geometry"
        ]
        global_geom_file = GEOMETRY_DIR / f"{iso3}.parquet"
        if missing_global_ids and global_geom_file != parquet_file and (
            (prefer_local and global_geom_file.exists()) or _parquet_accessible(global_geom_file)
        ):
            global_columns = _physical_parquet_columns(global_geom_file, columns)
            if prefer_local and global_geom_file.exists():
                global_df = pd.read_parquet(
                    global_geom_file,
                    columns=global_columns,
                    filters=[("loc_id", "in", missing_global_ids)],
                )
            else:
                global_df = select_rows(
                    global_geom_file,
                    columns=global_columns,
                    in_filters={"loc_id": missing_global_ids},
                )
            if global_df is not None and not global_df.empty:
                df = pd.concat([df, global_df], ignore_index=True)

        if df.empty:
            # Shared fallback for admin-spine ids that have a dedicated cached
            # level loader but are not present on the exact-row path in cloud
            # mode. This is currently important for USA admin_1 loc_ids such as
            # USA-CA, where the shared hierarchy knows the id but the direct
            # selection path can miss the state row.
            admin_levels = {
                len(str(loc_id).split("-")) - 1
                for loc_id in requested_ids
                if isinstance(loc_id, str) and loc_id.count("-") >= 1
            }
            if len(admin_levels) == 1:
                fallback_level = next(iter(admin_levels))
                if fallback_level in {1, 2}:
                    level_df = load_country_parquet(iso3, admin_level=fallback_level, columns=columns)
                    if level_df is not None and not level_df.empty:
                        fallback = level_df.copy()
                        if "local_loc_id" not in fallback.columns:
                            fallback["local_loc_id"] = fallback["loc_id"]
                        fallback = fallback[
                            fallback["loc_id"].isin(requested_set)
                            | fallback["local_loc_id"].isin(requested_set)
                        ]
                        if not fallback.empty:
                            fallback["source_loc_id"] = fallback["loc_id"]

                            def resolve_requested_id(source_value, local_value):
                                if local_value in requested_set:
                                    return local_value
                                if source_value in requested_set:
                                    return source_value
                                return local_value or source_value

                            fallback["loc_id"] = [
                                resolve_requested_id(source_value, local_value)
                                for source_value, local_value in zip(
                                    fallback["source_loc_id"],
                                    fallback["local_loc_id"],
                                )
                            ]
                            return fallback
            return df

        if reverse_map:
            df["source_loc_id"] = df["loc_id"]
            df["local_loc_id"] = df["loc_id"].map(lambda value: reverse_map.get(value, value))

            # Preserve the caller's id space. If the request asked for local ids,
            # return local ids; if it asked for source geometry ids, keep those.
            def resolve_requested_id(source_value):
                local_value = reverse_map.get(source_value)
                if local_value in requested_set:
                    return local_value
                return source_value

            df["loc_id"] = df["source_loc_id"].map(resolve_requested_id)
            df = df[
                df["loc_id"].isin(requested_set) |
                df["source_loc_id"].isin(requested_set)
            ]
        else:
            df = df[df["loc_id"].isin(requested_set)]
        return df
    except Exception as e:
        logger.error(f"Error loading exact geometry rows for {iso3}: {e}")
        return pd.DataFrame()


def _load_subcounty_rows_by_loc_ids(iso3: str, loc_ids: list[str], columns: list[str] | None = None):
    """
    Load exact deep-admin geometry rows for canonical local loc_ids.

    Reuses the established subcounty geometry system documented in crosswalk
    `sub_admin_levels` instead of falling back to the country-level geometry bank.
    """
    requested_ids = [canonicalize_loc_id(loc_id) for loc_id in loc_ids if loc_id]
    if not requested_ids:
        return pd.DataFrame()
    columns = _ensure_loc_id_projection(columns)

    sub_admin_levels = get_country_sub_admin_levels(iso3)
    if not sub_admin_levels:
        return pd.DataFrame()

    # A loc_id path is an identity namespace, not a promise that hyphen count
    # equals admin_level. Canada intentionally embeds its CD prefix inside CSD
    # and finer source codes, so admin_4/admin_5 IDs are one segment shallower
    # than a generic path counter expects. Probe the country's declared deep
    # banks by exact ID instead of guessing the bank from string depth.
    grouped: dict[tuple[int, str | None], list[str]] = {}
    configured_levels = sorted(
        int(key.split("_", 1)[1])
        for key in sub_admin_levels
        if str(key).startswith("admin_") and str(key).split("_", 1)[1].isdigit()
    )
    by_state: dict[str | None, list[str]] = {}
    for loc_id in requested_ids:
        parts = str(loc_id).split("-")
        if not parts or parts[0] != iso3:
            continue
        state_abbrev = parts[1] if len(parts) >= 2 else None
        by_state.setdefault(state_abbrev, []).append(loc_id)
    for admin_level in configured_levels:
        for state_abbrev, state_ids in by_state.items():
            grouped[(admin_level, state_abbrev)] = state_ids

    frames = []
    for (admin_level, state_abbrev), group_ids in grouped.items():
        df = load_subcounty_geometry(
            iso3, admin_level=admin_level, state_abbrev=state_abbrev,
            loc_ids=group_ids,
            columns=columns,
        )
        if df is None or df.empty:
            continue
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _load_deep_geometry_index_rows(
    iso3: str,
    admin_level: int,
    parent_loc_id: str | None = None,
    bbox: tuple | None = None,
):
    """
    Load lightweight index rows for canonical deep admin levels.

    This keeps admin_3/admin_4/admin_5 on the same path as the working
    subcounty geometry loaders instead of falling back to country parquet files
    that stop at admin_2 for countries like USA.
    """
    frames = []
    index_columns = [
        "loc_id", "parent_id", "admin_level", "name", "code",
        "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
        "centroid_lon", "centroid_lat",
    ]

    if parent_loc_id:
        parts = parent_loc_id.split("-")
        state_abbrev = parts[1] if len(parts) >= 2 else None
        df = load_subcounty_geometry(
            iso3, admin_level=admin_level, state_abbrev=state_abbrev,
            parent_loc_id=parent_loc_id, columns=index_columns,
        )
        if df is None or df.empty:
            return pd.DataFrame()
        return df

    if bbox is None:
        return pd.DataFrame()

    regions = get_regions_in_bbox(iso3, *bbox)
    for region_code in regions:
        df = load_subcounty_geometry(
            iso3, admin_level=admin_level, state_abbrev=region_code,
            bbox=bbox, columns=index_columns,
        )
        if df is None or df.empty:
            continue
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


# Display polygons are simplified, so their stored bounding boxes sit slightly
# inside the exact ones - the observed gap is under 0.04 degrees for every
# country whose territory attribution matches between the two banks. Country
# bounds are only ever used to shortlist candidates, and a shortlist must
# over-select rather than under-select, so pad each edge past that gap.
COUNTRY_BOUNDS_DISPLAY_PAD_DEG = 0.05


def load_country_bounds():
    """
    Load country bounding boxes for query filtering.
    Returns dict of iso3 -> (min_lon, min_lat, max_lon, max_lat).

    Bounds come from the bounded Admin0 Display bank, which stores them as
    columns. The exact global bank is a 400 MB+ CSV whose polygons had to be
    parsed with shapely just to recover numbers the Display bank already
    carries, and loading it here pulled exact geometry into ordinary viewport
    and map requests. Point containment still uses the exact bank; see
    resolve_point_to_location and resolve_points_to_locations.
    """
    global _country_bounds_cache
    if _country_bounds_cache is not None:
        return _country_bounds_cache

    _country_bounds_cache = {}

    df = load_global_country_display_frame()
    if df is None or df.empty:
        logger.warning("Country bounds unavailable: Admin0 Display bank not loaded")
        return _country_bounds_cache

    bbox_columns = ("bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat")
    if not all(column in df.columns for column in bbox_columns):
        logger.warning("Admin0 Display bank is missing bbox columns; country bounds empty")
        return _country_bounds_cache

    pad = COUNTRY_BOUNDS_DISPLAY_PAD_DEG
    for row in df[["loc_id", *bbox_columns]].to_dict("records"):
        loc_id = row.get("loc_id")
        if not loc_id:
            continue
        try:
            min_lon = float(row["bbox_min_lon"])
            min_lat = float(row["bbox_min_lat"])
            max_lon = float(row["bbox_max_lon"])
            max_lat = float(row["bbox_max_lat"])
        except (TypeError, ValueError):
            continue
        if any(pd.isna(value) for value in (min_lon, min_lat, max_lon, max_lat)):
            continue
        _country_bounds_cache[loc_id] = (
            max(min_lon - pad, -180.0),
            max(min_lat - pad, -90.0),
            min(max_lon + pad, 180.0),
            min(max_lat + pad, 90.0),
        )

    logger.info("Loaded bounds for %d countries from Admin0 Display bank", len(_country_bounds_cache))
    return _country_bounds_cache


def get_geometry_index(parent_loc_id: str | None = None, admin_level: int | None = None, bbox: tuple | None = None):
    """
    Return lightweight geometry index rows without polygon payloads.

    Intended for client-side diff loading. Returns loc_id hierarchy + bbox/centroid
    metadata so the browser can compute which loc_ids are visible and still missing.
    """
    if parent_loc_id:
        parts = parent_loc_id.split("-")
        iso3 = parts[0]
        if parent_loc_id == iso3:
            target_level = admin_level if admin_level is not None else 1
        else:
            target_level = admin_level if admin_level is not None else len(parts)

        df = load_country_display_rows(
            iso3,
            admin_level=target_level,
            parent_ids={parent_loc_id},
            columns=GEOMETRY_INDEX_COLUMNS,
        )
        if df is None or df.empty:
            return {"rows": [], "count": 0, "parent_loc_id": parent_loc_id, "admin_level": target_level}

        if target_level < 3 and "parent_id" in df.columns:
            df = df[df["parent_id"] == parent_loc_id]
    else:
        target_level = admin_level if admin_level is not None else 0
        if target_level == 0:
            df = load_global_country_display_frame()
        elif bbox is not None:
            countries = get_countries_in_bbox(*bbox)
            frames = []
            for iso3 in countries:
                viewport_df = load_country_display_rows(
                    iso3,
                    admin_level=target_level,
                    bbox=bbox,
                    columns=GEOMETRY_INDEX_COLUMNS,
                )
                if viewport_df is not None and not viewport_df.empty:
                    frames.append(viewport_df)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        else:
            return {
                "rows": [],
                "count": 0,
                "parent_loc_id": None,
                "admin_level": target_level,
                "error": "parent_loc_id required for sub-country index queries",
            }
        if df is None or df.empty:
            return {"rows": [], "count": 0, "parent_loc_id": parent_loc_id, "admin_level": target_level}

    if bbox is not None and df is not None and not df.empty:
        min_lon, min_lat, max_lon, max_lat = bbox
        if all(col in df.columns for col in ["bbox_min_lon", "bbox_max_lon", "bbox_min_lat", "bbox_max_lat"]):
            has_bbox = df[["bbox_min_lon", "bbox_max_lon", "bbox_min_lat", "bbox_max_lat"]].notna().all(axis=1)
            intersects = (
                (df["bbox_max_lon"] >= min_lon) &
                (df["bbox_min_lon"] <= max_lon) &
                (df["bbox_max_lat"] >= min_lat) &
                (df["bbox_min_lat"] <= max_lat)
            )
            # Country Display banks are not yet schema-identical. Some (for
            # example CAN) intentionally omit bbox metadata. After frames are
            # concatenated, those rows carry NaNs and must stay eligible;
            # treating NaN as non-intersection silently removed the country.
            df = df[~has_bbox | intersects]
        elif "centroid_lon" in df.columns and "centroid_lat" in df.columns:
            has_centroid = df[["centroid_lon", "centroid_lat"]].notna().all(axis=1)
            inside = (
                (df["centroid_lon"] >= min_lon) &
                (df["centroid_lon"] <= max_lon) &
                (df["centroid_lat"] >= min_lat) &
                (df["centroid_lat"] <= max_lat)
            )
            df = df[~has_centroid | inside]

    index_columns = GEOMETRY_INDEX_COLUMNS
    available = [col for col in index_columns if col in df.columns]
    rows = df[available].to_dict("records") if df is not None and not df.empty else []

    return {
        "rows": rows,
        "count": len(rows),
        "parent_loc_id": parent_loc_id,
        "admin_level": target_level,
    }


def get_countries_in_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    """
    Return ISO3 codes whose bounds intersect the query bbox.
    """
    bounds = load_country_bounds()
    result = []
    broad_country_rows = None
    viewport_polygon = None

    for iso3, (c_min_lon, c_min_lat, c_max_lon, c_max_lat) in bounds.items():
        # Check bbox intersection
        if (c_max_lon >= min_lon and c_min_lon <= max_lon and
            c_max_lat >= min_lat and c_min_lat <= max_lat):
            # Multi-part countries spanning the antimeridian or distant
            # territories can have an almost-worldwide bounding box. Confirm
            # those coarse candidates against the country outline so Russia,
            # France, or the USA do not make every mid-latitude viewport load
            # unrelated country banks. The Display outline is the right
            # precision for a shortlist: being wrong here loads one extra
            # country bank, and reading the exact bank instead pulled 400 MB+
            # of query geometry into a map request.
            if c_max_lon - c_min_lon >= 300:
                try:
                    from shapely.geometry import box, shape

                    if broad_country_rows is None:
                        broad_country_rows = load_global_country_display_frame()
                        viewport_polygon = box(min_lon, min_lat, max_lon, max_lat)
                    row = broad_country_rows[broad_country_rows["loc_id"] == iso3]
                    if not row.empty:
                        raw_geometry = row.iloc[0].get("geometry")
                        geometry = shape(json.loads(raw_geometry) if isinstance(raw_geometry, str) else raw_geometry)
                        if not geometry.intersects(viewport_polygon):
                            continue
                except Exception:
                    logger.debug("Display-outline country shortlist failed for %s", iso3, exc_info=True)
            result.append(iso3)

    return result


def _filter_df_for_point(df, lon: float, lat: float):
    """Filter candidate rows that could contain a point using bbox columns."""
    if df is None:
        return pd.DataFrame()
    try:
        if len(df) == 0:
            return pd.DataFrame()
    except TypeError:
        # Lightweight frame-like test/provider objects may only implement the
        # containment contract. Preserve the legacy path when no tabular bbox
        # surface is available.
        return df

    result = df
    if all(col in result.columns for col in ("bbox_min_lon", "bbox_max_lon", "bbox_min_lat", "bbox_max_lat")):
        result = result[
            (result["bbox_max_lon"] >= lon) &
            (result["bbox_min_lon"] <= lon) &
            (result["bbox_max_lat"] >= lat) &
            (result["bbox_min_lat"] <= lat)
        ]
    return result


def _find_containing_row(df, lon: float, lat: float):
    """Return the smallest geometry-spine row whose polygon covers the point."""
    if df is None or len(df) == 0:
        return None

    try:
        return match_point_in_frame(df, lon, lat)
    except Exception:
        logger.warning("geometry spine point resolution failed", exc_info=True)
        return None


def _find_containing_country_with_fallback(country_df, lon: float, lat: float):
    """Resolve a containing country, falling back to the country bank's admin_0 row.

    The shared Admin0 predicate layout is the fast country layer, but it may occasionally miss
    a coastal/island point if its simplified ADM0 outline drifted slightly from
    the per-country geometry bank. In that case, use the global bbox shortlist
    and check the country parquet's admin_0 geometry before declaring failure.
    """
    # The shared Admin0 bank contains hundreds of detailed polygons. Its bbox
    # columns are a cheap spatial index; shortlist first so a point lookup does
    # not parse and STRtree-index the entire world's geometry on cold start.
    candidates = _filter_df_for_point(country_df, lon, lat)
    direct_match = _find_containing_row(candidates, lon, lat)
    if direct_match is not None:
        return direct_match

    if candidates.empty:
        return None

    for _, row in candidates.iterrows():
        iso3 = _row_text(row, "loc_id")
        if not iso3:
            continue
        admin0_df = load_country_parquet(iso3, admin_level=0)
        admin0_match = _find_containing_row(admin0_df, lon, lat)
        if admin0_match is not None:
            return admin0_match
    return None


def _resolve_deepest_point_match(
    iso3: str,
    lon: float,
    lat: float,
    admin1_row=None,
    admin2_row=None,
    point_candidates: pd.DataFrame | None = None,
):
    """Attempt admin_3+ point resolution where country-specific deep geometry exists."""
    deep_levels = get_country_supported_deep_admin_levels(iso3)
    if not deep_levels:
        return None

    admin1_local = translate_geometry_id_to_local_id(admin1_row.get("loc_id")) if admin1_row is not None else None
    admin2_local = translate_geometry_id_to_local_id(admin2_row.get("loc_id")) if admin2_row is not None else None

    state_abbrev = _state_code_from_row(admin2_row) or _state_code_from_row(admin1_row)
    if not state_abbrev:
        for local_value in (admin2_local, admin1_local):
            if isinstance(local_value, str):
                parts = local_value.split("-")
                if len(parts) >= 2:
                    state_abbrev = parts[1]
                    break

    deepest_match = None
    parent_scope = admin2_local or admin1_local

    for admin_level in deep_levels:
        if point_candidates is not None and "admin_level" in point_candidates.columns:
            df = point_candidates[point_candidates["admin_level"] == admin_level]
        else:
            level_config = get_country_level_config(iso3, admin_level) or {}
            if str(level_config.get("folder") or "").strip() == ".":
                df = load_subcounty_geometry(
                    iso3, admin_level=admin_level,
                    bbox=(lon, lat, lon, lat),
                )
            else:
                df = load_subcounty_geometry(
                    iso3, admin_level=admin_level, state_abbrev=state_abbrev,
                    bbox=(lon, lat, lon, lat),
                )
                if (df is None or df.empty) and not state_abbrev:
                    regions = get_regions_in_bbox(iso3, lon, lat, lon, lat)
                    frames = []
                    for region_code in regions:
                        region_df = load_subcounty_geometry(
                            iso3, admin_level=admin_level, state_abbrev=region_code,
                            bbox=(lon, lat, lon, lat),
                        )
                        if region_df is not None and not region_df.empty:
                            frames.append(region_df)
                    df = pd.concat(frames, ignore_index=True) if frames else None
        if df is None or df.empty:
            continue

        candidates = _filter_df_for_point(df, lon, lat)
        if candidates.empty:
            continue

        if parent_scope and "parent_id" in candidates.columns:
            parent_mask = (
                (candidates["parent_id"] == parent_scope) |
                candidates["parent_id"].astype(str).str.startswith(parent_scope + "-", na=False)
            )
            scoped = candidates[parent_mask]
            if not scoped.empty:
                candidates = scoped

        match_row = _find_containing_row(candidates, lon, lat)
        if match_row is not None:
            deepest_match = match_row
            parent_scope = canonicalize_loc_id(match_row.get("loc_id"))

    return deepest_match


def _merge_point_geometry_reviews(*reviews: dict | None) -> dict | None:
    conflicts: dict[str, set[str]] = {}
    for review in reviews:
        for conflict in (review or {}).get("conflicts") or []:
            level = str(conflict.get("admin_level") or "")
            if level:
                conflicts.setdefault(level, set()).update(conflict.get("candidate_loc_ids") or [])
    if not conflicts:
        return None
    return {
        "geometry_review_required": True,
        "geometry_review_notice": "Double-check boundary",
        "reason": "multiple_admin_matches_same_level",
        "conflicts": [
            {"admin_level": level, "candidate_loc_ids": sorted(loc_ids)}
            for level, loc_ids in sorted(conflicts.items())
        ],
    }


def resolve_point_to_location(lon: float, lat: float, include_geometry: bool = True):
    """Resolve a point to the deepest available location."""
    lon = float(lon)
    lat = float(lat)

    indexed_matches = resolve_global_admin0_query_points([{"lon": lon, "lat": lat}])
    if indexed_matches is None:
        country_df = load_global_countries_frame()
        if country_df is None or country_df.empty:
            return {"error": "No global geometry available"}
        country_match = _find_containing_country_with_fallback(country_df, lon, lat)
    else:
        country_match = indexed_matches[0]
    if country_match is None:
        return {"error": "No containing country found", "point": {"lon": lon, "lat": lat}}

    iso3 = country_match.get("loc_id")
    country_name = country_match.get("name") or iso3

    query_layout_match = resolve_admin_spine_query_point(iso3, lon, lat)
    if query_layout_match is not None:
        matched = query_layout_match["matched"]
        stack = [
            _compact_point_stack_entry(row)
            for row in (query_layout_match.get("stack") or [])
        ]
        result = {
            "point": {"lon": lon, "lat": lat},
            "country": {"loc_id": iso3, "name": country_name},
            "matched": {
                "loc_id": matched.get("loc_id"),
                "name": matched.get("name"),
                "admin_level": int(matched.get("admin_level", 0)),
                "country_name": country_name,
                "iso3": iso3,
            },
            "stack": stack,
            "query_layout": "admin_0_3_plus_admin_1_deep",
        }
        geometry_review = _merge_point_geometry_reviews(
            country_match.get("geometry_review"), query_layout_match.get("geometry_review")
        )
        if geometry_review:
            result["geometry_review"] = geometry_review
        if include_geometry:
            result["geojson"] = get_selection_geometries([matched.get("loc_id")])
        return result

    point_bbox = (lon, lat, lon, lat)
    deep_levels = get_country_supported_deep_admin_levels(iso3)
    monolithic_levels = bool(deep_levels) and all(
        str((get_country_level_config(iso3, level) or {}).get("folder") or "").strip() == "."
        for level in deep_levels
    )
    point_candidates = None
    if monolithic_levels:
        point_candidates = load_country_parquet_viewport(
            iso3, None, point_bbox, columns=POINT_RESOLUTION_COLUMNS,
        )

    if point_candidates is not None and "admin_level" in point_candidates.columns:
        admin1_df = point_candidates[point_candidates["admin_level"] == 1]
    else:
        admin1_df = load_country_parquet_viewport(
            iso3, 1, point_bbox, columns=POINT_RESOLUTION_COLUMNS,
        )
    admin1_match = _find_containing_row(admin1_df, lon, lat)

    if point_candidates is not None and "admin_level" in point_candidates.columns:
        admin2_df = point_candidates[point_candidates["admin_level"] == 2]
    else:
        admin2_df = load_country_parquet_viewport(
            iso3, 2, point_bbox, columns=POINT_RESOLUTION_COLUMNS,
        )
    admin2_match = _find_containing_row(admin2_df, lon, lat)

    if admin2_match is not None:
        deepest_row = admin2_match
    elif admin1_match is not None:
        deepest_row = admin1_match
    else:
        deepest_row = country_match
    deep_match = _resolve_deepest_point_match(
        iso3,
        lon,
        lat,
        admin1_row=admin1_match,
        admin2_row=admin2_match,
        point_candidates=point_candidates,
    )
    if deep_match is not None:
        deepest_row = deep_match

    deepest_loc_id = deepest_row.get("loc_id") if deepest_row is not None else iso3
    deepest_name = deepest_row.get("name") if deepest_row is not None else country_name
    deepest_level = int(deepest_row.get("admin_level", 0)) if deepest_row is not None else 0

    stack = []
    for row in (country_match, admin1_match, admin2_match):
        if row is None:
            continue
        stack.append({
            "loc_id": row.get("loc_id"),
            "name": row.get("name"),
            "admin_level": int(row.get("admin_level", 0)),
        })
    if deepest_level >= 3 and deepest_row is not None:
        stack.append({
            "loc_id": deepest_loc_id,
            "name": deepest_name,
            "admin_level": deepest_level,
        })

    result = {
        "point": {"lon": lon, "lat": lat},
        "country": {"loc_id": iso3, "name": country_name},
        "matched": {
            "loc_id": deepest_loc_id,
            "name": deepest_name,
            "admin_level": deepest_level,
            "country_name": country_name,
            "iso3": iso3,
        },
        "stack": stack,
    }
    if country_match.get("geometry_review"):
        result["geometry_review"] = country_match["geometry_review"]
    if include_geometry:
        result["geojson"] = get_selection_geometries([deepest_loc_id])
    return result


def _row_state_abbrev(row) -> str | None:
    if row is None:
        return None
    return _state_code_from_row(row)


def _compact_point_stack_entry(row) -> dict:
    """Return the intentionally small public point-chain representation."""
    entry = {
        "loc_id": row.get("loc_id"),
        "name": row.get("name"),
        "admin_level": int(row.get("admin_level", 0)),
    }
    vintage = _geometry_metadata_value(
        row,
        "reference_date",
        "source_vintage",
        "geometry_vintage",
    )
    if vintage is not None:
        entry["vintage"] = vintage
    lineage = row.get("lineage") if isinstance(row.get("lineage"), dict) else {
        "material_id": _geometry_metadata_value(row, "material_id", "bank_id"),
        "bank_id": _geometry_metadata_value(row, "bank_id"),
        "release_id": _geometry_metadata_value(row, "release_id"),
        "source_id": _geometry_metadata_value(row, "source_id"),
        "source_system": _geometry_metadata_value(row, "source_system"),
        "source_vintage": _geometry_metadata_value(row, "source_vintage", "source_release"),
        "geometry_source": _geometry_metadata_value(row, "geometry_source"),
        "geometry_vintage": _geometry_metadata_value(row, "geometry_vintage"),
    }
    lineage = {key: value for key, value in lineage.items() if value not in (None, "", [])}
    if lineage:
        entry["lineage"] = lineage
    if row.get("identity_only"):
        entry["identity_only"] = True
    return entry


def _add_timing_ms(timing_ms: dict[str, int] | None, key: str, started_at: float) -> None:
    if timing_ms is None:
        return
    timing_ms[key] = timing_ms.get(key, 0) + int((time.perf_counter() - started_at) * 1000)


def resolve_points_to_locations(
    points: list[dict],
    include_geometry: bool = False,
    timing_ms: dict[str, int] | None = None,
    target_admin_level: int | None = None,
    max_admin_level: int | None = None,
    country_scope: str | None = None,
    admin_1_scope: str | None = None,
    include_marine_context: bool = True,
    shallow_banks_only: bool = False,
):
    """Resolve multiple points through one shared geometry-loading pass.

    The single-point resolver is intentionally exact, but calling it in a loop
    reloads the same country/state/deep-admin sources for every point in hosted
    cloud mode. This helper keeps the result shape compatible while grouping
    geometry reads by country/state and admin level.
    """
    # ``target_admin_level`` is exact: callers asking for Admin 3 receive an
    # error when that tier is unavailable. ``max_admin_level`` is an I/O
    # ceiling: return the deepest available match at or below it. Keeping the
    # concepts separate lets global shallow bulk stop before every deep shard
    # without falsely rejecting countries whose maintained spine ends at 0-2.
    requested_target_admin_level = target_admin_level
    io_admin_level = (
        target_admin_level if target_admin_level is not None else max_admin_level
    )
    scope_iso3 = str(country_scope or "").strip().upper()
    if scope_iso3 == "CAN" and not shallow_banks_only:
        from .runtime.canada_exact_geometry import (
            canada_query_exact_enabled,
            resolve_canada_query_exact_points,
        )

        if canada_query_exact_enabled():
            if include_geometry:
                raise ValueError(
                    "resolve_point exact mode returns loc_ids only; fetch or export the selected geometry separately"
                )
            return resolve_canada_query_exact_points(
                points, target_admin_level=io_admin_level,
            )
    normalized_points: list[dict] = []
    for index, point in enumerate(points or []):
        try:
            lon = float(point.get("lon"))
            lat = float(point.get("lat"))
        except Exception:
            normalized_points.append({"index": index, "error": "invalid point"})
            continue
        normalized_points.append({"index": index, "lon": lon, "lat": lat})

    # Collapse exact duplicate coordinates before resolution. Event data repeats
    # the same point constantly (one storm cell, many rows), and each duplicate
    # previously paid full containment cost. create_conversion_job already
    # deduplicates by identifier; this is the same saving for coordinates.
    original_point_count = len(normalized_points)
    duplicate_targets: dict[int, list[int]] = {}
    seen_coords: dict[tuple[float, float], int] = {}
    deduped_points: list[dict] = []
    for item in normalized_points:
        if item.get("error"):
            deduped_points.append(item)
            continue
        key = (item["lon"], item["lat"])
        first = seen_coords.get(key)
        if first is None:
            seen_coords[key] = item["index"]
            deduped_points.append(item)
        else:
            duplicate_targets.setdefault(first, []).append(item["index"])
    distinct_point_count = len(seen_coords)
    normalized_points = deduped_points

    def _deduplicated_error_results(message: str) -> list[dict]:
        early: list[dict | None] = [None] * original_point_count
        for item in normalized_points:
            early[item["index"]] = {
                "error": item.get("error") or message,
                "point": {"lon": item.get("lon"), "lat": item.get("lat")},
            }
        for source_index, target_indexes in duplicate_targets.items():
            source_result = early[source_index]
            for target_index in target_indexes:
                early[target_index] = dict(source_result) if isinstance(source_result, dict) else source_result
        return [item or {"error": message} for item in early]

    results: list[dict | None] = [None] * original_point_count
    by_country: dict[str, list[dict]] = {}
    stage_started = time.perf_counter()
    if scope_iso3:
        identities = load_global_admin0_identities([scope_iso3])
        if identities is None:
            country_df = load_global_countries_frame()
            _add_timing_ms(timing_ms, "global_country_fallback_load_ms", stage_started)
            if country_df is None or country_df.empty:
                return _deduplicated_error_results("No global geometry available")
            scoped_rows = country_df[
                country_df["loc_id"].astype(str).str.upper() == scope_iso3
            ] if "loc_id" in country_df.columns else pd.DataFrame()
            country_match = None if scoped_rows.empty else scoped_rows.iloc[0]
        else:
            country_match = identities.get(scope_iso3)
        if country_match is None:
            return _deduplicated_error_results(f"Unknown country_scope {scope_iso3}")
        for item in normalized_points:
            if item.get("error"):
                results[item["index"]] = {"error": item["error"]}
                continue
            item["country_match"] = country_match
            item["iso3"] = scope_iso3
            by_country.setdefault(scope_iso3, []).append(item)
        _add_timing_ms(timing_ms, "country_scope_ms", stage_started)
    else:
        country_matches = resolve_global_admin0_query_points(normalized_points)
        used_predicate_layout = country_matches is not None
        if country_matches is None:
            country_df = load_global_countries_frame()
            _add_timing_ms(timing_ms, "global_country_fallback_load_ms", stage_started)
            if country_df is None or country_df.empty:
                return _deduplicated_error_results("No global geometry available")
            if len(normalized_points) <= 8:
                country_matches = [
                    _find_containing_country_with_fallback(
                        country_df, float(item.get("lon", 0)), float(item.get("lat", 0)),
                    ) if not item.get("error") else None
                    for item in normalized_points
                ]
                used_global_index = False
            else:
                country_index = geometry_spine_index_for_frame(country_df)
                spine_matches = country_index.match_points(normalized_points) if country_index is not None else [None] * len(normalized_points)
                country_matches = [match.row if match is not None else None for match in spine_matches]
                used_global_index = True
        else:
            used_global_index = False
        for item, country_match in zip(normalized_points, country_matches):
            if item.get("error"):
                results[item["index"]] = {"error": item["error"]}
                continue
            lon = float(item["lon"])
            lat = float(item["lat"])
            if country_match is None:
                # A bbox/index miss is normally offshore. Resolve the compact
                # Marine predicate index before invoking the expensive legacy
                # country-bank fallback; land still wins whenever the global
                # Admin0 spine contains the point.
                from .runtime.loc_id_resolution import _resolve_point_to_marine_stack

                marine_result = _resolve_point_to_marine_stack(
                    lon, lat, include_geometry=include_geometry,
                )
                if marine_result is not None:
                    results[item["index"]] = marine_result
                    continue
                if used_global_index and not used_predicate_layout:
                    country_match = _find_containing_country_with_fallback(country_df, lon, lat)
            if country_match is None:
                results[item["index"]] = {"error": "No containing country found", "point": {"lon": lon, "lat": lat}}
                continue
            iso3 = str(country_match.get("loc_id") or "").strip()
            item["country_match"] = country_match
            item["iso3"] = iso3
            by_country.setdefault(iso3, []).append(item)
        _add_timing_ms(timing_ms, "country_match_ms", stage_started)

    for iso3, country_items in by_country.items():
        # The adopted query layout is the primary country-spine reader. It is
        # deliberately attempted before any legacy country bank so a country's
        # maintained spine always outranks the GeoBoundaries/global fallback.
        # Failed/unavailable layout lookups remain eligible for the legacy path.
        unresolved_items: list[dict] = []
        stage_started = time.perf_counter()
        query_matches = resolve_admin_spine_query_points(
            iso3, country_items, target_admin_level=io_admin_level,
            admin_1_scope=admin_1_scope,
            stage_timing_ms=timing_ms,
        )
        if query_matches is None:
            query_matches = [None] * len(country_items)
        # Standard point resolution intentionally opens only the national
        # Admin 0-3 bank.  Its returned stack therefore cannot by itself say
        # whether the country has Admin1-owned Admin 4-6 banks.  The country
        # profile declares those levels without opening their geometry, so use
        # it to advertise the deep follow-up tools accurately.
        declared_deep_levels = (
            get_country_supported_deep_admin_levels(iso3)
            if shallow_banks_only
            else []
        )
        for item, query_match in zip(country_items, query_matches):
            if query_match is None:
                unresolved_items.append(item)
                continue
            if query_match.get("error"):
                country_match = item["country_match"]
                results[item["index"]] = {
                    "point": {"lon": float(item["lon"]), "lat": float(item["lat"])},
                    "country": {
                        "loc_id": iso3,
                        "name": country_match.get("name") or iso3,
                    },
                    "admin_1_scope": admin_1_scope,
                    "error": query_match["error"],
                }
                continue
            full_stack = list(query_match.get("stack") or [])
            available_levels = sorted({int(row.get("admin_level", 0)) for row in full_stack})
            selected_stack = full_stack
            if io_admin_level is not None:
                selected_stack = [
                    row for row in full_stack
                    if int(row.get("admin_level", 0)) <= io_admin_level
                ]
            exact_target = (
                requested_target_admin_level is None
                or any(
                    int(row.get("admin_level", 0)) == requested_target_admin_level
                    for row in selected_stack
                )
            )
            selected = selected_stack[-1] if selected_stack else None
            country_match = item["country_match"]
            country_name = country_match.get("name") or iso3
            if not exact_target or selected is None:
                max_level = max(available_levels or [0])
                error_code = (
                    "target_admin_level_unavailable"
                    if requested_target_admin_level is not None and requested_target_admin_level > max_level
                    else "no_match_at_target_admin_level"
                )
                results[item["index"]] = {
                    "point": {"lon": float(item["lon"]), "lat": float(item["lat"])},
                    "country": {"loc_id": iso3, "name": country_name},
                    "target_admin_level": f"admin_{requested_target_admin_level}",
                    "max_available_admin_level": f"admin_{max_level}",
                    "available_admin_levels": [f"admin_{level}" for level in available_levels],
                    "query_layout": (
                        "admin_0_3" if shallow_banks_only
                        else "admin_0_3_plus_admin_1_deep"
                    ),
                    "error": {
                        "code": error_code,
                        "message": f"Point did not match admin_{requested_target_admin_level} in {iso3}",
                    },
                }
                continue
            selected_level = int(selected.get("admin_level", 0))
            deeper_levels = [
                level
                for level in sorted(set(available_levels + declared_deep_levels))
                if level > selected_level
            ]
            results[item["index"]] = {
                "point": {"lon": float(item["lon"]), "lat": float(item["lat"])},
                "country": {"loc_id": iso3, "name": country_name},
                "matched": {
                    "loc_id": selected.get("loc_id"), "name": selected.get("name"),
                    "admin_level": selected_level, "country_name": country_name, "iso3": iso3,
                },
                "stack": [_compact_point_stack_entry(row) for row in selected_stack],
                "resolution_mode": "latest_available_per_depth",
                "target_admin_level": (
                    f"admin_{requested_target_admin_level}"
                    if requested_target_admin_level is not None
                    else (f"up_to_admin_{io_admin_level}" if io_admin_level is not None else "deepest")
                ),
                "deeper_available": bool(deeper_levels),
                "available_deeper_admin_levels": [f"admin_{level}" for level in deeper_levels],
                "query_layout": (
                    "admin_0_3" if shallow_banks_only
                    else "admin_0_3_plus_admin_1_deep"
                ),
            }
            geometry_review = _merge_point_geometry_reviews(
                country_match.get("geometry_review"), query_match.get("geometry_review")
            )
            if geometry_review:
                results[item["index"]]["geometry_review"] = geometry_review
            if include_geometry:
                results[item["index"]]["geojson"] = get_selection_geometries([selected.get("loc_id")])
        _add_timing_ms(timing_ms, f"{iso3}_query_layout_ms", stage_started)
        country_items = unresolved_items
        if not country_items:
            continue

        min_lon = min(float(item["lon"]) for item in country_items)
        max_lon = max(float(item["lon"]) for item in country_items)
        min_lat = min(float(item["lat"]) for item in country_items)
        max_lat = max(float(item["lat"]) for item in country_items)
        bbox = (min_lon, min_lat, max_lon, max_lat)

        admin1_df = pd.DataFrame()
        admin2_df = pd.DataFrame()
        if io_admin_level is None or io_admin_level >= 1:
            stage_started = time.perf_counter()
            admin1_df = _cached_country_admin_frame(iso3, 1)
            if admin1_df is None:
                admin1_df = load_country_parquet_viewport(iso3, 1, bbox)
            if admin1_df is None or admin1_df.empty:
                admin1_df = load_country_parquet(iso3, admin_level=1)
            _add_timing_ms(timing_ms, f"{iso3}_admin1_load_ms", stage_started)

        if io_admin_level is None or io_admin_level >= 2:
            stage_started = time.perf_counter()
            admin2_df = _cached_country_admin_frame(iso3, 2)
            if admin2_df is None:
                admin2_df = load_country_parquet_viewport(iso3, 2, bbox)
            if admin2_df is None or admin2_df.empty:
                admin2_df = load_country_parquet(iso3, admin_level=2)
            _add_timing_ms(timing_ms, f"{iso3}_admin2_load_ms", stage_started)

        stage_started = time.perf_counter()
        admin1_index = geometry_spine_index_for_frame(admin1_df)
        admin2_index = geometry_spine_index_for_frame(admin2_df)
        admin1_matches = admin1_index.match_points(country_items) if admin1_index is not None else [None] * len(country_items)
        admin2_matches = admin2_index.match_points(country_items) if admin2_index is not None else [None] * len(country_items)
        for item, admin1_spine_match, admin2_spine_match in zip(country_items, admin1_matches, admin2_matches):
            admin1_match = admin1_spine_match.row if admin1_spine_match is not None else None
            admin2_match = admin2_spine_match.row if admin2_spine_match is not None else None
            item["admin1_match"] = admin1_match
            item["admin2_match"] = admin2_match
            item["matches_by_level"] = {
                0: item["country_match"],
                **({1: admin1_match} if admin1_match is not None else {}),
                **({2: admin2_match} if admin2_match is not None else {}),
            }
            if io_admin_level is not None and io_admin_level <= 0:
                item["deepest_row"] = item["country_match"]
            elif io_admin_level == 1:
                item["deepest_row"] = admin1_match if admin1_match is not None else item["country_match"]
            elif admin2_match is not None:
                item["deepest_row"] = admin2_match
            elif admin1_match is not None:
                item["deepest_row"] = admin1_match
            else:
                item["deepest_row"] = item["country_match"]
            item["parent_scope"] = (
                translate_geometry_id_to_local_id(admin2_match.get("loc_id")) if admin2_match is not None else
                translate_geometry_id_to_local_id(admin1_match.get("loc_id")) if admin1_match is not None else
                None
            )
        _add_timing_ms(timing_ms, f"{iso3}_admin_match_ms", stage_started)

        stage_started = time.perf_counter()
        # Standard resolution may fall back to the global per-country baseline
        # when a country has no adopted Admin 0-3 query bank.  That baseline is
        # deliberately bounded to Admin 1-2 here: it restores useful worldwide
        # resolution without opening any country-owned Admin 3-6 partitions.
        supported_deep_levels = (
            [] if shallow_banks_only
            else get_country_supported_deep_admin_levels(iso3)
        )
        for item in country_items:
            item["supported_deep_levels"] = supported_deep_levels
            max_available_admin_level = max(
                [0]
                + ([1] if admin1_df is not None and not admin1_df.empty else [])
                + ([2] if admin2_df is not None and not admin2_df.empty else [])
                + [level for level in supported_deep_levels if level >= 3]
            )
            item["max_available_admin_level"] = max_available_admin_level
            item["available_admin_levels"] = list(range(0, max_available_admin_level + 1))
        deep_levels = supported_deep_levels
        if io_admin_level is not None:
            deep_levels = [level for level in deep_levels if level <= io_admin_level]
        if io_admin_level is not None and io_admin_level < 3:
            deep_levels = []
        _add_timing_ms(timing_ms, f"{iso3}_deep_config_ms", stage_started)
        for admin_level in deep_levels:
            groups: dict[str, list[dict]] = {}
            for item in country_items:
                state_abbrev = _row_state_abbrev(item.get("admin2_match")) or _row_state_abbrev(item.get("admin1_match"))
                if not state_abbrev:
                    continue
                groups.setdefault(state_abbrev, []).append(item)
            for state_abbrev, grouped_items in groups.items():
                group_bbox = (
                    min(float(item["lon"]) for item in grouped_items),
                    min(float(item["lat"]) for item in grouped_items),
                    max(float(item["lon"]) for item in grouped_items),
                    max(float(item["lat"]) for item in grouped_items),
                )
                stage_started = time.perf_counter()
                df = load_subcounty_geometry(iso3, admin_level=admin_level, state_abbrev=state_abbrev, bbox=group_bbox)
                _add_timing_ms(timing_ms, f"{iso3}_admin{admin_level}_load_ms", stage_started)
                if df is None or df.empty:
                    continue
                stage_started = time.perf_counter()
                deep_index = geometry_spine_index_for_frame(df)

                # Point context is resolved independently at every depth. This is
                # deliberately not filtered through the preceding row's strict
                # parent_id: the latest available fine tier can be older than a
                # newly published shallow tier. Strict parent traversal belongs
                # to one pinned release and is exposed by get_loc_id_info/scope tools.
                deep_matches = deep_index.match_points(grouped_items) if deep_index is not None else [None] * len(grouped_items)
                for item, deep_spine_match in zip(grouped_items, deep_matches):
                    match_row = deep_spine_match.row if deep_spine_match is not None else None
                    if match_row is not None:
                        item["deepest_row"] = match_row
                        item.setdefault("matches_by_level", {})[admin_level] = match_row
                        item["parent_scope"] = canonicalize_loc_id(match_row.get("loc_id"))
                _add_timing_ms(timing_ms, f"{iso3}_admin{admin_level}_match_ms", stage_started)

        for item in country_items:
            lon = float(item["lon"])
            lat = float(item["lat"])
            country_match = item["country_match"]
            country_name = country_match.get("name") or iso3
            deepest_row = item.get("deepest_row")
            if deepest_row is None:
                deepest_row = country_match
            deepest_loc_id = deepest_row.get("loc_id") if deepest_row is not None else iso3
            deepest_name = deepest_row.get("name") if deepest_row is not None else country_name
            deepest_level = int(deepest_row.get("admin_level", 0)) if deepest_row is not None else 0
            supported_deep_levels = item.get("supported_deep_levels") or []
            available_admin_levels = sorted(set(item.get("available_admin_levels") or [0]))
            max_available_admin_level = int(item.get("max_available_admin_level") or max(available_admin_levels or [0]))
            available_deeper_levels = [
                f"admin_{level}"
                for level in supported_deep_levels
                if requested_target_admin_level is not None and level > requested_target_admin_level
            ]
            if requested_target_admin_level is not None and deepest_level != requested_target_admin_level:
                error_code = (
                    "target_admin_level_unavailable"
                    if requested_target_admin_level > max_available_admin_level
                    else "no_match_at_target_admin_level"
                )
                results[item["index"]] = {
                    "point": {"lon": lon, "lat": lat},
                    "country": {"loc_id": iso3, "name": country_name},
                    "matched": {
                        "loc_id": deepest_loc_id,
                        "name": deepest_name,
                        "admin_level": deepest_level,
                        "country_name": country_name,
                        "iso3": iso3,
                    },
                    "target_admin_level": f"admin_{requested_target_admin_level}",
                    "max_available_admin_level": f"admin_{max_available_admin_level}",
                    "available_admin_levels": [f"admin_{level}" for level in available_admin_levels],
                    "deeper_available": bool(available_deeper_levels),
                    "available_deeper_admin_levels": available_deeper_levels,
                    "error": {
                        "code": error_code,
                        "message": (
                            f"{iso3} currently serves through admin_{max_available_admin_level}, not admin_{requested_target_admin_level}"
                            if error_code == "target_admin_level_unavailable"
                            else f"Point did not match an admin_{requested_target_admin_level} geometry in {iso3}"
                        ),
                    },
                }
                continue
            stack = [
                _compact_point_stack_entry(row)
                for level, row in sorted((item.get("matches_by_level") or {}).items())
                if row is not None and level <= deepest_level
            ]
            result = {
                "point": {"lon": lon, "lat": lat},
                "country": {"loc_id": iso3, "name": country_name},
                "matched": {
                    "loc_id": deepest_loc_id,
                    "name": deepest_name,
                    "admin_level": deepest_level,
                    "country_name": country_name,
                    "iso3": iso3,
                },
                "stack": stack,
                "resolution_mode": "latest_available_per_depth",
                "target_admin_level": (
                    f"admin_{requested_target_admin_level}"
                    if requested_target_admin_level is not None
                    else (f"up_to_admin_{io_admin_level}" if io_admin_level is not None else "deepest")
                ),
                "deeper_available": bool(available_deeper_levels),
                "available_deeper_admin_levels": available_deeper_levels,
                "query_layout": (
                    "global_admin0_2_baseline"
                    if shallow_banks_only
                    else "legacy_country_admin"
                ),
            }
            if include_geometry:
                result["geojson"] = get_selection_geometries([deepest_loc_id])
            results[item["index"]] = result

    # Country geometry intentionally excludes marine jurisdiction. Give every
    # otherwise-unresolved offshore point the same marine resolver used by the
    # single-point loc_id stack so the map, JSON API, and MCP batch path do not
    # fail merely because no land Admin0 contains the coordinate.
    marine_candidates = [
        item for item in normalized_points
        if not item.get("error")
        and isinstance(results[item["index"]], dict)
        and results[item["index"]].get("error") == "No containing country found"
    ]
    if marine_candidates:
        from .runtime.loc_id_resolution import _resolve_points_to_marine_stacks

        stage_started = time.perf_counter()
        marine_results = _resolve_points_to_marine_stacks(
            marine_candidates, include_geometry=include_geometry,
        )
        for item, marine_result in zip(marine_candidates, marine_results):
            if marine_result is not None:
                results[item["index"]] = marine_result
        _add_timing_ms(timing_ms, "marine_match_ms", stage_started)

    # A coastal coordinate can truthfully match both a land/admin polygon and
    # marine families (for example a census water polygon plus an EEZ). Keep
    # the admin spine as the primary answer, but expose the marine context as
    # parallel overlaps instead of making callers choose one geometry domain.
    # A country-scoped bulk request is deliberately one physical/semantic
    # query group. Do not silently open Marine banks after the selected
    # country's admin file has answered it; callers can run a separate Marine
    # scope. Unscoped interactive resolution still includes truthful coastal
    # overlaps such as EEZ context.
    admin_candidates = [
        item for item in normalized_points
        if not item.get("error")
        and isinstance(results[item["index"]], dict)
        and not results[item["index"]].get("error")
        and results[item["index"]].get("country")
    ]
    if admin_candidates and not scope_iso3 and include_marine_context:
        from .runtime.loc_id_resolution import _resolve_points_to_marine_stacks

        stage_started = time.perf_counter()
        marine_results = _resolve_points_to_marine_stacks(
            admin_candidates, include_geometry=False,
        )
        for item, marine_result in zip(admin_candidates, marine_results):
            if marine_result is None:
                continue
            result = results[item["index"]]
            marine_matched = marine_result.get("matched") or {}
            context: list[dict] = []
            marine_family = marine_matched.get("family")
            if marine_matched.get("loc_id") and marine_family in {
                "marine_eez", "marine_jurisdiction",
            }:
                context.append({
                    "loc_id": marine_matched.get("loc_id"),
                    "name": marine_matched.get("name"),
                    "family": marine_family,
                    "admin_level": None,
                    "relationship": "marine_jurisdiction",
                })
            context.extend(
                entry for entry in marine_result.get("overlap_families") or []
                if entry.get("family") in {"marine_eez", "marine_jurisdiction"}
                or entry.get("relationship") == "marine_jurisdiction"
            )
            if not context:
                continue
            seen: set[str] = set()
            result["overlap_families"] = [
                entry for entry in [*(result.get("overlap_families") or []), *context]
                if entry.get("loc_id") and not (entry["loc_id"] in seen or seen.add(entry["loc_id"]))
            ]
            result["marine_context"] = {
                "matched": context[0],
                "resolution_family": "marine",
            }
        _add_timing_ms(timing_ms, "marine_context_ms", stage_started)

    # Global Admin0 ambiguity also applies when the selected country has only
    # the compatibility reader rather than an admitted country query layout.
    for item in normalized_points:
        country_match = item.get("country_match")
        result = results[item["index"]]
        if country_match is None or not isinstance(result, dict) or result.get("error"):
            continue
        geometry_review = _merge_point_geometry_reviews(
            result.get("geometry_review"), country_match.get("geometry_review")
        )
        if geometry_review:
            result["geometry_review"] = geometry_review

    # Fan the representative result back out to the duplicates it stood in for.
    for source_index, target_indexes in duplicate_targets.items():
        source_result = results[source_index]
        for target_index in target_indexes:
            results[target_index] = dict(source_result) if isinstance(source_result, dict) else source_result
    if timing_ms is not None:
        timing_ms["distinct_points_resolved"] = distinct_point_count
        timing_ms["duplicate_points_collapsed"] = sum(len(v) for v in duplicate_targets.values())
    return [result or {"error": "point did not resolve"} for result in results]


def calculate_coverage_from_parquet(iso3: str, from_level: int = 1):
    """
    Calculate coverage stats on-the-fly from actual parquet data.

    Args:
        iso3: Country ISO3 code
        from_level: Start counting from this level (default 1, excludes country level)

    Returns:
        dict with level_counts, geometry_counts, coverage, actual_depth, drillable_depth
    """
    # Load full parquet for the country
    df = load_country_parquet(iso3)
    if df is None or len(df) == 0:
        return {
            "level_counts": {},
            "geometry_counts": {},
            "coverage": 0,
            "actual_depth": 0,
            "drillable_depth": 0
        }

    # Calculate stats from actual data
    level_counts = {}
    geometry_counts = {}

    for level in df['admin_level'].unique():
        level = int(level)
        if level < from_level:
            continue
        level_df = df[df['admin_level'] == level]
        level_counts[str(level)] = len(level_df)
        # Count rows with actual geometry (not null/empty)
        has_geom = level_df['geometry'].notna() & (level_df['geometry'] != '')
        geometry_counts[str(level)] = int(has_geom.sum())

    # Calculate coverage
    total = sum(level_counts.values())
    with_geom = sum(geometry_counts.values())
    coverage = with_geom / total if total > 0 else 0

    # Calculate depth
    if level_counts:
        max_level = max(int(k) for k in level_counts.keys())
        min_level = min(int(k) for k in level_counts.keys())
        actual_depth = max_level - min_level + 1
        # Drillable depth = deepest level with geometry
        levels_with_geom = [int(k) for k, v in geometry_counts.items() if v > 0]
        drillable_depth = max(levels_with_geom) if levels_with_geom else min_level
    else:
        actual_depth = 0
        drillable_depth = 0

    return {
        "level_counts": level_counts,
        "geometry_counts": geometry_counts,
        "coverage": coverage,
        "actual_depth": actual_depth,
        "drillable_depth": drillable_depth
    }


def df_to_geojson(df, polygon_only=False):
    """
    Convert a DataFrame with geometry column to GeoJSON FeatureCollection.

    Args:
        df: DataFrame with geometry column (GeoJSON string)
        polygon_only: If True, skip Point geometries

    Performance notes:
        - Uses to_dict('records') instead of iterrows() (10-100x faster)
        - Uses orjson for JSON parsing when available (3-10x faster)
        - Pre-computes column list to avoid repeated lookups
    """
    if df is None or len(df) == 0:
        return {"type": "FeatureCollection", "features": []}

    # Get property columns once (all except geometry)
    prop_cols = [c for c in df.columns if c != 'geometry']

    # Convert to list of dicts - MUCH faster than iterrows()
    records = df.to_dict('records')

    features = []
    for row in records:
        geom_str = row.get('geometry')
        if not geom_str or (isinstance(geom_str, float) and pd.isna(geom_str)):
            continue

        try:
            if isinstance(geom_str, str):
                geometry = fast_json_loads(geom_str)
            elif isinstance(geom_str, (bytes, bytearray, memoryview)):
                from shapely import from_wkb
                from shapely.geometry import mapping
                geometry = mapping(from_wkb(bytes(geom_str)))
            elif hasattr(geom_str, "__geo_interface__"):
                geometry = geom_str.__geo_interface__
            else:
                geometry = geom_str
        except (ValueError, TypeError):
            continue

        if not isinstance(geometry, dict):
            continue

        # Skip Point geometries if polygon_only
        if polygon_only and geometry.get('type') == 'Point':
            continue

        # Build properties - only include non-null values
        properties = {col: row[col] for col in prop_cols
                      if row.get(col) is not None and not (isinstance(row[col], float) and pd.isna(row[col]))}
        # USA Admin 5 rows are converted directly from the locally staged
        # Census 2024 TABBLOCK20 source.  Preserve that provenance on the
        # returned feature so a popup never borrows a stale source label from
        # whatever global layer was displayed before viewport loading.
        if properties.get("iso_a3") == "USA" and int(properties.get("admin_level") or -1) == 5:
            properties["geometry_source"] = "U.S. Census Bureau TIGER/Line 2024 TABBLOCK20"

        features.append({
            "type": "Feature",
            "properties": properties,
            "geometry": geometry
        })

    return {"type": "FeatureCollection", "features": features}


def get_countries_geometry(debug: bool = False):
    """
    Get bounded country geometries for initial map display.

    This endpoint is a visual payload. Full `geometry/global/exact/admin_0.parquet` polygons are
    reserved for containment and compatibility query paths and must not leak
    into the browser bootstrap.
    Returns a GeoJSON FeatureCollection with polygon countries only.

    If debug=True, calculates coverage info on-the-fly from parquet files.
    """
    df = load_global_country_display_frame()

    if df is None:
        return {
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
            "level": "country",
            "debug": debug,
            "error": "No geometry data available. Configure backup path in settings."
        }

    # Convert to GeoJSON (polygons only)
    geojson = df_to_geojson(df, polygon_only=True)

    # If debug mode, calculate coverage info on-the-fly from parquet
    if debug:
        for feature in geojson.get("features", []):
            loc_id = feature.get("properties", {}).get("loc_id")
            if loc_id:
                # Calculate from actual parquet data, starting from level 1
                cov_info = calculate_coverage_from_parquet(loc_id, from_level=1)
                feature["properties"]["actual_depth"] = cov_info.get("actual_depth", 0)
                feature["properties"]["expected_depth"] = cov_info.get("actual_depth", 0)
                feature["properties"]["coverage"] = cov_info.get("coverage", 0)
                feature["properties"]["level_counts"] = cov_info.get("level_counts", {})
                feature["properties"]["geometry_counts"] = cov_info.get("geometry_counts", {})
                feature["properties"]["drillable_depth"] = cov_info.get("drillable_depth", 0)
            else:
                feature["properties"]["actual_depth"] = 0
                feature["properties"]["expected_depth"] = 0
                feature["properties"]["coverage"] = 0
                feature["properties"]["level_counts"] = {}
                feature["properties"]["geometry_counts"] = {}
                feature["properties"]["drillable_depth"] = 0

    return {
        "geojson": geojson,
        "count": len(geojson.get("features", [])),
        "level": "country",
        "debug": debug
    }


def get_location_children(loc_id: str):
    """
    Get child geometries for a location (drill-down).
    Uses parquet files with parent_id filtering.

    If direct children have no geometry (hierarchy-only levels),
    recursively finds the first descendant level with geometry.

    Examples:
    - loc_id="USA" -> Returns US counties (skips admin_1 which has no geometry)
    - loc_id="USA-CA" -> Returns California counties (admin_2)
    - loc_id="FRA" -> Returns French communes (skips intermediate levels)
    """
    # Extract country code from loc_id
    parts = loc_id.split("-")
    if not parts:
        return {
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
            "level": "none",
            "parent_loc_id": loc_id,
            "error": "Invalid loc_id format"
        }

    iso3 = parts[0]

    display_paths, _crosswalk, _source_kind = _country_display_sources(
        iso3, parent_ids={loc_id}
    )
    if not display_paths:
        return {
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
            "level": "none",
            "parent_loc_id": loc_id,
            "error": f"No display geometry data for {iso3}."
        }

    # Find children with geometry, drilling through hierarchy-only levels
    current_parents = {loc_id}
    children = pd.DataFrame()
    max_depth = 10  # Safety limit

    for _ in range(max_depth):
        # Get all direct children of current parent set
        children = load_country_display_rows(iso3, parent_ids=current_parents)

        if len(children) == 0:
            return {
                "geojson": {"type": "FeatureCollection", "features": []},
                "count": 0,
                "level": "none",
                "parent_loc_id": loc_id,
                "message": f"No child locations for {loc_id}"
            }

        # Check if these children have geometry
        children_with_geom = children[children["geometry"].notna()]

        if len(children_with_geom) > 0:
            # Found children with geometry
            children = children_with_geom
            break

        # No geometry at this level - drill down further
        # Use these children as the new parent set
        current_parents = set(children["loc_id"].tolist())
        logger.debug(f"Level has no geometry, drilling to {len(current_parents)} children")

    # Determine child level name
    child_level = int(children["admin_level"].iloc[0])
    level_names = {0: "country", 1: "state", 2: "county", 3: "place", 4: "locality", 5: "neighborhood"}
    level_name = level_names.get(child_level, f"admin_{child_level}")

    # Convert to GeoJSON
    geojson = df_to_geojson(children)

    return {
        "geojson": geojson,
        "count": len(geojson.get("features", [])),
        "level": level_name,
        "admin_level": child_level,
        "parent_loc_id": loc_id
    }


def get_location_places(loc_id: str):
    """
    Get places (cities/towns) for a location as a separate overlay layer.
    Used to display city markers on top of county boundaries.

    Returns the deepest admin level available for this location.
    """
    parts = loc_id.split("-")
    if not parts:
        return {
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
            "level": "none",
            "parent_loc_id": loc_id
        }

    iso3 = parts[0]

    # This is a visual endpoint; use the admitted Display family (or the
    # GeoBoundaries display fallback), never a Full/query spine.
    df = load_country_display_rows(iso3)
    if df is None:
        return {
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
            "level": "none",
            "parent_loc_id": loc_id,
            "error": f"No geometry data for {iso3}"
        }

    # Find the deepest admin level that has this loc_id as ancestor
    # Get all features where parent_id starts with loc_id
    if len(parts) == 1:
        # Country level - find all places in country
        descendants = df[df["iso_a3"] == iso3]
    else:
        # Sub-national - find descendants
        # Match either exact parent_id or parent_id starting with loc_id-
        mask = (df["parent_id"] == loc_id) | (df["parent_id"].str.startswith(loc_id + "-", na=False))
        descendants = df[mask]

    if len(descendants) == 0:
        return {
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
            "level": "none",
            "parent_loc_id": loc_id
        }

    # Get the deepest level available
    max_level = descendants["admin_level"].max()
    places = descendants[descendants["admin_level"] == max_level]

    # Convert to GeoJSON
    geojson = df_to_geojson(places)

    level_names = {0: "country", 1: "state", 2: "county", 3: "place", 4: "locality", 5: "neighborhood"}
    level_name = level_names.get(int(max_level), f"admin_{max_level}")

    return {
        "geojson": geojson,
        "count": len(geojson.get("features", [])),
        "level": level_name,
        "admin_level": int(max_level),
        "parent_loc_id": loc_id
    }


def _append_location_version_metadata(result: dict, row) -> dict:
    field_aliases = {
        "valid_from": ("valid_from", "valid_from_date"),
        "valid_to": ("valid_to", "valid_to_date"),
        "geometry_vintage": ("geometry_vintage",),
        "source_vintage": ("source_vintage", "reference_date"),
        "source_id": ("source_id",),
        "source_system": ("source_system",),
        "geometry_source": ("geometry_source",),
        "bank_id": ("bank_id",),
        "release_id": ("geography_release_id", "release_id"),
        "lifecycle_status": ("lifecycle_status",),
        "superseded_by": ("superseded_by", "successor_loc_id"),
    }
    for output_key, input_keys in field_aliases.items():
        value = _geometry_metadata_value(row, *input_keys)
        if value is not None:
            result[output_key] = value
    return result


def _location_row_has_polygon(row) -> bool:
    declared = _geometry_metadata_value(row, "has_polygon")
    if declared is not None:
        return bool(declared)
    geometry = _geometry_metadata_value(row, "geometry")
    return geometry is not None and str(geometry).strip() not in {"", "null", "None"}


def _reference_graph_location_info(loc_id: str) -> dict | None:
    """Return the active integrated-graph identity when geometry banks miss."""
    try:
        from .runtime.reference_graph import identity, where_is_geography_data

        row = identity(loc_id)
        if not row:
            return None
        source = where_is_geography_data(loc_id)
        return {
            "loc_id": row.get("loc_id") or loc_id,
            "name": row.get("name"),
            "admin_level": row.get("admin_level"),
            "parent_id": row.get("parent_loc_id"),
            "family": row.get("geography_family") or row.get("family"),
            "iso3": str(row.get("loc_id") or loc_id).split("-", 1)[0],
            "has_polygon": bool(row.get("has_shape")),
            "valid_from": row.get("valid_from"),
            "valid_to": row.get("valid_to"),
            "source_vintage": row.get("source_vintage"),
            "source_id": row.get("native_id"),
            "source_system": row.get("source_system"),
            "geometry_source": row.get("geometry_bank"),
            "release_id": source.get("release_id"),
            "reference_graph_status": source.get("status"),
            "children_count": 0,
            "descendants_count": 0,
        }
    except Exception:
        return None


def get_location_info(loc_id: str, *, include_memberships: bool = True):
    """
    Get detailed information about a specific location for popup display.

    Returns:
        - Basic info: loc_id, name, admin_level, parent_id
        - Children counts: children_count, children_by_level, descendants_count, descendants_by_level
        - Memberships: regional groupings (G20, BRICS, etc.) for countries
        - Dataset count: number of datasets available for this location

    Uses pre-computed children counts from parquet when available.
    """
    parts = loc_id.split("-")
    if not parts:
        return {"error": "Invalid loc_id"}

    from .runtime.admin_hierarchy import infer_admin_level_from_loc_id

    iso3 = parts[0]
    inferred_admin_level = infer_admin_level_from_loc_id(loc_id)
    namespace_family = classify_loc_id_family(loc_id)
    if (
        not admin_spine_layout_available(iso3)
        or (namespace_family and not str(namespace_family).startswith("admin"))
    ):
        graph_info = _reference_graph_location_info(loc_id)
        if graph_info and not str(graph_info.get("family") or "").startswith("admin"):
            # A declared sidechain namespace belongs to the reference graph.
            # Do not let an admin-depth-looking identifier hydrate a geometry
            # metadata row first and thereby lose graph identity fields.
            return graph_info
    if inferred_admin_level is not None:
        metadata = _get_selection_metadata_for_loc_id(loc_id)
        if metadata:
            return _build_metadata_based_location_info(
                loc_id,
                metadata,
                include_memberships=include_memberships,
            )

    graph_info = _reference_graph_location_info(loc_id)
    if graph_info and not str(graph_info.get("family") or "").startswith("admin"):
        # A real admitted admin query-layout row wins first. On an authoritative
        # admin miss, the graph family then rescues sidechain IDs whose stable
        # code components happen to resemble a deep admin ID.
        return graph_info
    family = _geometry_family_for_loc_id(loc_id)
    if graph_info and not str(family or "").startswith("admin"):
        # Reference-sidechain metadata already lives in the graph identity row.
        # Avoid opening a potentially huge geometry partition merely to answer
        # name/family/parent/source questions.
        return graph_info
    if family in {"overlay_zcta", "overlay_tribal", "overlay_nws_public_zone", "overlay_nws_fire_weather_zone", "can_federal_electoral_district_2013", "can_designated_place", "marine_eez", "water_body", "regional_base"}:
        metadata = _get_selection_metadata_for_loc_id(loc_id)
        if metadata:
            return _build_metadata_based_location_info(
                loc_id,
                metadata,
                include_memberships=include_memberships,
            )

    result = {
        "loc_id": loc_id,
        "admin_level": inferred_admin_level if inferred_admin_level is not None else len(parts) - 1,
        "memberships": [],
        "dataset_count": 0,
        "family": family,
    }

    # Country metadata is available in the bounded Display bootstrap.
    if len(parts) == 1:
        df = load_global_country_display_frame()
        if df is not None:
            location = df[df["loc_id"] == loc_id]
            if len(location) > 0:
                row = location.iloc[0]
                result["name"] = row.get("name")
                result["admin_level"] = 0

                # Get children info from country parquet
                country_df = load_country_parquet(iso3)
                if country_df is not None and len(country_df) > 0:
                    country_row = country_df[country_df["loc_id"] == loc_id]
                    if len(country_row) > 0:
                        cr = country_row.iloc[0]
                        result["children_count"] = int(cr.get("children_count", 0)) if pd.notna(cr.get("children_count")) else 0
                        result["children_by_level"] = cr.get("children_by_level", "{}")
                        result["descendants_count"] = int(cr.get("descendants_count", 0)) if pd.notna(cr.get("descendants_count")) else 0
                        result["descendants_by_level"] = cr.get("descendants_by_level", "{}")
                    else:
                        # Calculate from parquet if not in parquet (country-only entry)
                        children = country_df[country_df["parent_id"] == loc_id]
                        result["children_count"] = len(children)
                        result["descendants_count"] = len(country_df) - 1  # Exclude country itself
                    result["max_depth"] = int(country_df['admin_level'].max())
                    result["has_children"] = result.get("children_count", 0) > 0 or result["max_depth"] > 0
                else:
                    result["children_count"] = 0
                    result["descendants_count"] = 0
                    result["max_depth"] = 0
                    result["has_children"] = False

                # Get memberships from conversions.json
                result["memberships"] = _get_country_memberships(iso3)

                # Add a few lightweight static country facts for navigation popups
                static_df = load_world_factbook_static_frame()
                if static_df is not None:
                    static_row = static_df[static_df["loc_id"] == loc_id]
                    if len(static_row) > 0:
                        sr = static_row.iloc[0]
                        result["capital_name"] = sr.get("capital_name")
                        area_total = sr.get("area_total_sq_km")
                        coastline = sr.get("coastline_km")
                        if pd.notna(area_total):
                            result["area_total_sq_km"] = float(area_total)
                        if pd.notna(coastline):
                            result["coastline_km"] = float(coastline)

                # Get dataset counts by level
                result["dataset_counts"] = _get_dataset_counts_by_level(loc_id)
                result["dataset_count"] = sum(result["dataset_counts"].values())

                # Get country-specific level names
                result["level_names"] = _get_level_names(iso3)
                result["centroid"] = {"lon": row.get("centroid_lon"), "lat": row.get("centroid_lat")}
                result["bbox"] = _bbox_from_feature_props(row.to_dict())
                result["has_polygon"] = _location_row_has_polygon(row)
                result["iso3"] = row.get("iso_a3") or iso3

                return _append_location_version_metadata(result, row)

    # For sub-national, check country parquet
    df = load_country_parquet(iso3)
    if df is None:
        metadata = _get_selection_metadata_for_loc_id(loc_id)
        if metadata:
            return _build_metadata_based_location_info(
                loc_id,
                metadata,
                include_memberships=include_memberships,
            )
        graph_info = _reference_graph_location_info(loc_id)
        if graph_info:
            return graph_info
        return {"error": f"No data for {iso3}"}

    location = df[df["loc_id"] == loc_id]
    if len(location) == 0:
        metadata = _get_selection_metadata_for_loc_id(loc_id)
        if metadata:
            return _build_metadata_based_location_info(
                loc_id,
                metadata,
                include_memberships=include_memberships,
            )
        graph_info = _reference_graph_location_info(loc_id)
        if graph_info:
            return graph_info
        return {"error": f"Location not found: {loc_id}"}

    row = location.iloc[0]
    result["name"] = row.get("name")
    result["admin_level"] = int(row.get("admin_level", 0))
    result["parent_id"] = row.get("parent_id")

    # Get parent name for "Part of" display
    parent_id = row.get("parent_id")
    if parent_id:
        parent_names = _get_parent_hierarchy(df, parent_id, iso3)
        result["memberships"] = [f"Part of: {', '.join(parent_names)}"] if parent_names else []
    else:
        result["memberships"] = []

    # Use pre-computed children counts if available
    result["children_count"] = int(row.get("children_count", 0)) if pd.notna(row.get("children_count")) else 0
    result["children_by_level"] = row.get("children_by_level", "{}")
    result["descendants_count"] = int(row.get("descendants_count", 0)) if pd.notna(row.get("descendants_count")) else 0
    result["descendants_by_level"] = row.get("descendants_by_level", "{}")
    result["has_children"] = result["children_count"] > 0

    # Get dataset counts by level
    result["dataset_counts"] = _get_dataset_counts_by_level(loc_id)
    result["dataset_count"] = sum(result["dataset_counts"].values())

    # Get country-specific level names
    result["level_names"] = _get_level_names(iso3)
    result["centroid"] = {"lon": row.get("centroid_lon"), "lat": row.get("centroid_lat")}
    result["bbox"] = _bbox_from_feature_props(row.to_dict())
    result["has_polygon"] = _location_row_has_polygon(row)
    result["iso3"] = row.get("iso_a3") or iso3

    return _append_location_version_metadata(result, row)


def _get_country_memberships(iso3: str) -> list:
    """
    Get regional grouping memberships for a country from conversions.json.
    Returns list of group names this country belongs to.

    Regional groupings are stored as {group_name: {code, countries}} in conversions.json.
    """
    try:
        from .geography import get_conversions_data
        conversions = get_conversions_data()
        if not conversions:
            return []

        regional_groupings = conversions.get("regional_groupings", {})
        memberships = []

        # Priority groups to show first (most recognizable)
        priority_groups = ['G7', 'G20', 'European_Union', 'NATO', 'BRICS', 'OECD', 'OPEC', 'ASEAN']

        for group_name, group_data in regional_groupings.items():
            # Handle both dict format {code, countries} and list format
            if isinstance(group_data, dict):
                countries = group_data.get("countries", [])
            else:
                countries = group_data if isinstance(group_data, list) else []

            if iso3 in countries:
                # Use code if available, otherwise format group_name
                if isinstance(group_data, dict) and group_data.get("code"):
                    display_name = group_data["code"]
                else:
                    display_name = group_name.replace("_", " ")
                memberships.append((group_name, display_name))

        # Sort: priority groups first, then alphabetically
        def sort_key(item):
            group_name, display_name = item
            if group_name in priority_groups:
                return (0, priority_groups.index(group_name))
            return (1, display_name)

        memberships.sort(key=sort_key)
        return [display_name for _, display_name in memberships]
    except Exception:
        return []


def _get_dataset_counts_by_level(loc_id: str) -> dict:
    """
    Count datasets by geographic level for this location.
    Returns dict like {"country": 20, "state": 0, "county": 3}
    """
    try:
        from .data_loading import get_data_catalog
        catalog = get_data_catalog()
        if not catalog:
            return {}

        # Extract country code from loc_id
        iso3 = loc_id.split("-")[0] if "-" in loc_id else loc_id

        counts = {}
        for source in catalog.get("sources", []):
            geo_coverage = source.get("geographic_coverage", {})
            country_codes = geo_coverage.get("country_codes_all", [])
            geo_level = source.get("geographic_level", "country")

            if iso3 in country_codes:
                counts[geo_level] = counts.get(geo_level, 0) + 1

        return counts
    except Exception:
        return {}


def _get_dataset_count(loc_id: str) -> int:
    """
    Count how many datasets in the catalog cover this location.
    Uses geographic_coverage.country_codes_all field from catalog.json.
    """
    counts = _get_dataset_counts_by_level(loc_id)
    return sum(counts.values())


def _bbox_from_feature_props(props: dict) -> list[float] | None:
    keys = ("bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat")
    if all(props.get(key) is not None for key in keys):
        return [props[keys[0]], props[keys[1]], props[keys[2]], props[keys[3]]]
    return None


def _get_selection_feature_for_loc_id(loc_id: str) -> dict | None:
    payload = get_selection_geometries([loc_id])
    features = (payload or {}).get("features") or []
    return features[0] if features else None


def _get_selection_metadata_for_loc_id(loc_id: str) -> dict | None:
    rows = get_selection_geometry_metadata([loc_id])
    return rows[0] if rows else None


def _build_metadata_based_location_info(
    loc_id: str,
    props: dict,
    *,
    include_memberships: bool = True,
) -> dict:
    """Build loc_id information without reading or materializing polygon payloads."""
    family = (
        classify_loc_id_family(loc_id)
        if props.get("admin_level") is not None
        else _geometry_family_for_loc_id(loc_id)
    )
    memberships = []
    if include_memberships:
        ancestor_ids = []
        current_id = str(props.get("parent_id") or "").strip()
        while current_id:
            ancestor_ids.append(current_id)
            if "-" not in current_id:
                break
            current_id = current_id.rsplit("-", 1)[0]
        ancestor_rows = get_selection_geometry_metadata(ancestor_ids) if ancestor_ids else []
        ancestor_names = {
            str(item.get("loc_id") or ""): item.get("name")
            for item in ancestor_rows
        }
        for parent_id in ancestor_ids:
            if ancestor_names.get(parent_id):
                continue
            parent_info = get_location_info(parent_id)
            if isinstance(parent_info, dict) and parent_info.get("name"):
                ancestor_names[parent_id] = parent_info["name"]
        memberships = [
            f"Part of: {', '.join(str(ancestor_names.get(parent_id) or parent_id) for parent_id in ancestor_ids)}"
        ] if ancestor_ids else []
    result = {
        "loc_id": props.get("loc_id") or loc_id,
        "name": props.get("name"),
        "admin_level": props.get("admin_level"),
        "parent_id": props.get("parent_id"),
        "family": family,
        "subtype": props.get("subtype") or props.get("source_native_subtype"),
        "children_count": props.get("children_count") or 0,
        "children_by_level": props.get("children_by_level", "{}"),
        "descendants_count": props.get("descendants_count") or 0,
        "descendants_by_level": props.get("descendants_by_level", "{}"),
        "has_children": bool(props.get("children_count")),
        "memberships": memberships,
        "dataset_count": 0,
        "dataset_counts": {},
        "centroid": {"lon": props.get("centroid_lon"), "lat": props.get("centroid_lat")},
        "bbox": _bbox_from_feature_props(props),
        "has_polygon": bool(props.get("has_polygon")),
        # Sidechain geometry metadata does not always repeat the country
        # column. loc_id owns the country namespace, so preserve the stable
        # response contract without forcing a second graph lookup.
        "iso3": props.get("iso_a3") or str(props.get("loc_id") or loc_id).split("-", 1)[0],
        "land_area": props.get("land_area"),
        "water_area": props.get("water_area"),
        "geometry_source": props.get("geometry_source"),
    }
    return _append_location_version_metadata(result, props)


def get_location_infos(
    loc_ids: list[str],
    *,
    include_memberships: bool = False,
    fallback: bool = True,
) -> list[dict]:
    """Return location metadata with one grouped geometry-metadata pipeline.

    The popup-oriented singular helper has several compatibility branches.
    MCP batches should not repeat those branches for every identifier when the
    exact metadata banks can answer the whole request together.
    """
    requested = [str(loc_id or "").strip() for loc_id in loc_ids if str(loc_id or "").strip()]
    if not requested:
        return []
    unique = list(dict.fromkeys(requested))
    rows = get_selection_geometry_metadata(unique)
    by_loc_id = {
        str(row.get("loc_id") or row.get("source_loc_id") or "").strip(): row
        for row in rows
        if str(row.get("loc_id") or row.get("source_loc_id") or "").strip()
    }
    info_by_loc_id: dict[str, dict] = {}
    for loc_id in unique:
        row = by_loc_id.get(loc_id)
        if row is not None:
            info_by_loc_id[loc_id] = _build_metadata_based_location_info(
                loc_id,
                row,
                include_memberships=include_memberships,
            )
            continue
        if not fallback:
            info_by_loc_id[loc_id] = {"loc_id": loc_id, "error": "no geometry metadata found"}
            continue
        # Retain compatibility for graph-only or legacy identities while
        # ensuring duplicate inputs pay this fallback at most once.
        try:
            info_by_loc_id[loc_id] = get_location_info(
                loc_id,
                include_memberships=include_memberships,
            )
        except Exception as exc:
            info_by_loc_id[loc_id] = {"loc_id": loc_id, "error": str(exc)}
    return [info_by_loc_id[loc_id] for loc_id in requested]


def _build_feature_based_location_info(loc_id: str, feature: dict) -> dict:
    props = feature.get("properties") or {}
    family = _geometry_family_for_loc_id(loc_id)
    # Deep local rows live in state-partitioned files, so the normal
    # country-parquet parent lookup cannot see them.  Resolve this compact
    # exact-ID ancestor chain for the same human-readable "Part of" context
    # used by Admin 0–2 popups.
    ancestor_ids = []
    current_id = str(props.get("parent_id") or "").strip()
    while current_id:
        ancestor_ids.append(current_id)
        if "-" not in current_id:
            break
        current_id = current_id.rsplit("-", 1)[0]
    ancestor_features = get_selection_geometries(ancestor_ids).get("features", []) if ancestor_ids else []
    ancestor_names = {
        str(item.get("properties", {}).get("loc_id") or ""): item.get("properties", {}).get("name")
        for item in ancestor_features
    }
    for parent_id in ancestor_ids:
        if ancestor_names.get(parent_id):
            continue
        # The legacy Admin 1 bridge can translate a local USA state ID to a
        # GeoBoundaries row, while selection intentionally avoids loading a
        # full state frame.  Its normal location-info lookup is exact and
        # gives the same human label without exposing the raw local ID.
        parent_info = get_location_info(parent_id)
        if parent_info.get("name"):
            ancestor_names[parent_id] = parent_info["name"]
    memberships = [
        f"Part of: {', '.join(str(ancestor_names.get(parent_id) or parent_id) for parent_id in ancestor_ids)}"
    ] if ancestor_ids else []
    result = {
        "loc_id": props.get("local_loc_id") or loc_id,
        "name": props.get("name"),
        "admin_level": props.get("admin_level"),
        "parent_id": props.get("parent_id"),
        "family": family,
        "subtype": props.get("subtype") or props.get("source_native_subtype"),
        "children_count": props.get("children_count") or 0,
        "children_by_level": props.get("children_by_level", "{}"),
        "descendants_count": props.get("descendants_count") or 0,
        "descendants_by_level": props.get("descendants_by_level", "{}"),
        "has_children": bool(props.get("children_count")),
        "memberships": memberships,
        "dataset_count": 0,
        "dataset_counts": {},
        "centroid": {"lon": props.get("centroid_lon"), "lat": props.get("centroid_lat")},
        "bbox": _bbox_from_feature_props(props),
        # A successfully materialized selection feature is authoritative even
        # when its legacy metadata row omitted ``has_polygon``.
        "has_polygon": bool(feature.get("geometry")) or bool(props.get("has_polygon")),
        "iso3": props.get("iso_a3"),
        "land_area": props.get("land_area"),
        "water_area": props.get("water_area"),
        "geometry_source": props.get("geometry_source"),
    }
    return _append_location_version_metadata(result, props)


# Default level names (fallback if conversions.json unavailable)
DEFAULT_LEVEL_NAMES = {
    1: "first-level divisions",
    2: "second-level divisions",
    3: "third-level divisions",
    4: "localities",
    5: "neighborhoods",
    6: "blocks"
}

# Cache for canonical deep admin geometry files (admin_3+ such as tracts,
# block groups, and blocks). Parallel geometry tracks like ZCTA or tribal
# should not be routed through this admin hierarchy.
_subcounty_geometry_cache = {}


def _read_subcounty_geometry(
    file_path: Path,
    *,
    loc_ids: list[str] | None = None,
    parent_loc_id: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Read only the deep-geometry rows needed by the current request.

    State block files can contain millions of features.  They must never be
    loaded into an application-wide DataFrame cache merely to serve a viewport
    or selection request.  Both local PyArrow reads and cloud DuckDB/R2 reads
    receive the same predicates and projection here.
    """
    exact_filters = {"parent_id": parent_loc_id} if parent_loc_id else None
    in_filters = {"loc_id": loc_ids} if loc_ids else None
    compare_filters = None
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        compare_filters = [
            ("bbox_max_lon", ">=", min_lon),
            ("bbox_min_lon", "<=", max_lon),
            ("bbox_max_lat", ">=", min_lat),
            ("bbox_min_lat", "<=", max_lat),
        ]

    read_columns = _physical_parquet_columns(file_path, columns)

    if _prefer_local_geometry_reads() and file_path.exists():
        filters = []
        if parent_loc_id:
            filters.append(("parent_id", "==", parent_loc_id))
        if loc_ids:
            filters.append(("loc_id", "in", loc_ids))
        if compare_filters:
            filters.extend(compare_filters)
        return pd.read_parquet(file_path, columns=read_columns, filters=filters or None)

    return select_rows(
        file_path,
        columns=read_columns,
        exact_filters=exact_filters,
        in_filters=in_filters,
        compare_filters=compare_filters,
    )


def _apply_subcounty_filters(
    df: pd.DataFrame,
    *,
    loc_ids: list[str] | None = None,
    parent_loc_id: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=columns or None)

    filtered = df
    if loc_ids and "loc_id" in filtered.columns:
        wanted = {canonicalize_loc_id(value) for value in loc_ids if value}
        filtered = filtered[filtered["loc_id"].astype(str).str.upper().isin(wanted)]
    if parent_loc_id and "parent_id" in filtered.columns:
        parent = canonicalize_loc_id(parent_loc_id)
        filtered = filtered[filtered["parent_id"].astype(str).str.upper() == parent]
    if bbox and all(column in filtered.columns for column in ("bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat")):
        min_lon, min_lat, max_lon, max_lat = bbox
        filtered = filtered[
            (filtered["bbox_max_lon"] >= min_lon)
            & (filtered["bbox_min_lon"] <= max_lon)
            & (filtered["bbox_max_lat"] >= min_lat)
            & (filtered["bbox_min_lat"] <= max_lat)
        ]
    if columns:
        available = [column for column in columns if column in filtered.columns]
        filtered = filtered[available]
    return filtered


def _row_text(row, field: str) -> str:
    """Return a row field as text, tolerating pandas missing values.

    ``row.get(field) or ""`` looks safe but raises on pandas ``NA``, because
    ``bool(pd.NA)`` is deliberately ambiguous rather than falsey. Parquet-backed
    admin rows carry ``NA`` in optional columns such as ``iso_3166_2``, so the
    plain ``or`` idiom crashes point resolution for any country where that
    column is unset. Venice was the reported case.
    """
    if row is None:
        return ""
    value = row.get(field)
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        # Array-like values are not missing; fall through and stringify.
        pass
    return str(value).strip()


def _state_code_from_row(row) -> str | None:
    if row is None:
        return None
    for field in ("loc_id", "parent_id"):
        value = _row_text(row, field).upper()
        parts = value.split("-")
        if len(parts) >= 2 and parts[0].isalpha() and len(parts[1]) <= 3 and not parts[1].startswith("G"):
            return parts[1]
    iso_3166_2 = _row_text(row, "iso_3166_2").upper()
    if "-" in iso_3166_2:
        return iso_3166_2.rsplit("-", 1)[-1]
    return None


def load_subcounty_geometry(
    iso3: str,
    admin_level: int,
    state_abbrev: str = None,
    *,
    loc_ids: list[str] | None = None,
    parent_loc_id: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    columns: list[str] | None = None,
):
    """
    Load canonical deep-admin geometry for admin_3+.

    Supports tiered geometry files stored in:
    - geometry_{type}.parquet (national files when a country stores deep
      admin geometry in one file)
    - geometry_{type}/{ISO3}-{region}.parquet (regional files)

    For USA, the structure is:
    - Level 3 (admin_3): tract
    - Level 4 (admin_4): block group
    - Level 5 (admin_5): block

    Parallel geometry tracks such as ZCTA, tribal, watersheds, or parks are
    handled elsewhere and are not part of the admin_0..admin_5 path.

    Args:
        iso3: Country code
        admin_level: Canonical admin level (3+)
        state_abbrev: Region/state code (required for state-partitioned levels)

    Returns:
        DataFrame or None
    """
    countries_dir = COUNTRY_GEOMETRY_DIR / iso3

    level_config = get_country_level_config(iso3, admin_level)

    if not level_config:
        return None

    geom_type = level_config.get("folder") or level_config.get("name")
    if str(geom_type or "").strip() == ".":
        if bbox is not None:
            df = load_country_parquet_viewport(
                iso3,
                admin_level,
                bbox,
                columns=columns or POINT_RESOLUTION_COLUMNS,
            )
        else:
            df = load_country_parquet(iso3, admin_level=admin_level, columns=columns)
        return _apply_subcounty_filters(
            df,
            loc_ids=loc_ids,
            parent_loc_id=parent_loc_id,
            bbox=bbox,
            columns=columns,
        )

    is_partitioned = bool(state_abbrev or iso3 == "USA")

    if not is_partitioned:
        # National file
        cache_key = f"{iso3}_{geom_type}"
        filtered_request = bool(loc_ids or parent_loc_id or bbox or columns)
        if not filtered_request and cache_key in _subcounty_geometry_cache:
            return _subcounty_geometry_cache[cache_key]

        file_path = countries_dir / f"{geom_type}.parquet"
        if not is_cloud_mode() and not file_path.exists():
            logger.debug(f"Sub-county geometry not found: {file_path}")
            return None

        try:
            df = _read_subcounty_geometry(
                file_path, loc_ids=loc_ids, parent_loc_id=parent_loc_id,
                bbox=bbox, columns=columns,
            )
            if not filtered_request:
                _subcounty_geometry_cache[cache_key] = df
            logger.debug(f"Loaded {len(df)} features from {file_path}")
            return df
        except Exception as e:
            logger.error(f"Error loading sub-county geometry: {e}")
            return None

    else:
        # Partitioned by region/state
        if not state_abbrev:
            logger.warning(f"Region/state code required for {iso3} admin level {admin_level}")
            return None

        subdir = geom_type  # e.g., "tract", "blockgroup", "block"
        file_path = countries_dir / subdir / f"{iso3}-{state_abbrev}.parquet"
        if not is_cloud_mode() and not file_path.exists():
            logger.debug(f"Sub-county geometry not found: {file_path}")
            return None

        try:
            df = _read_subcounty_geometry(
                file_path, loc_ids=loc_ids, parent_loc_id=parent_loc_id,
                bbox=bbox, columns=columns,
            )
            logger.debug(f"Loaded {len(df)} requested features for {state_abbrev} level {admin_level}")
            return df
        except Exception as e:
            logger.error(f"Error loading sub-county geometry: {e}")
            return None


def get_states_in_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    """
    Return state abbreviations whose bounds intersect the query bbox.
    Uses the USA Display release to find states (admin_level=1).
    """
    df = load_country_display_rows("USA", admin_level=1)
    if df is None or len(df) == 0:
        return []

    result = []
    for _, row in df.iterrows():
        # Check bbox intersection
        if 'bbox_min_lon' in df.columns:
            c_min_lon = row.get('bbox_min_lon')
            c_min_lat = row.get('bbox_min_lat')
            c_max_lon = row.get('bbox_max_lon')
            c_max_lat = row.get('bbox_max_lat')

            if pd.notna(c_min_lon) and pd.notna(c_max_lon):
                if (c_max_lon >= min_lon and c_min_lon <= max_lon and
                    c_max_lat >= min_lat and c_min_lat <= max_lat):
                    # Extract state abbrev from loc_id (e.g., "USA-CA" -> "CA")
                    loc_id = row.get('loc_id', '')
                    if '-' in loc_id:
                        state_abbrev = loc_id.split('-')[1]
                        result.append(state_abbrev)

    return result


def _extract_display_name(value):
    """Extract display name from level name value (handles both string and array formats)."""
    if isinstance(value, list) and len(value) > 0:
        return value[0]  # First element is display name
    return value  # Already a string


def _load_admin_levels():
    """Load admin level names from reference/admin_levels.json."""
    data = load_reference_json("admin_levels.json")
    if isinstance(data, dict):
        return data
    return {}


def _get_level_names(iso3: str) -> dict:
    """
    Get country-specific level names from reference/admin_levels.json.
    Returns dict like {1: "states", 2: "counties", 3: "places"} for USA.

    Format in admin_levels.json is array: [display_name, synonym1, synonym2, ...]
    This function extracts only the display name (first element).

    Falls back to DEFAULT_LEVEL_NAMES if country not found.
    """
    try:
        admin_levels = _load_admin_levels()
        if not admin_levels:
            return DEFAULT_LEVEL_NAMES

        # Get country-specific names
        country_names = admin_levels.get(iso3)
        if country_names:
            # Convert string keys to int keys, extract display name from arrays
            return {int(k): _extract_display_name(v) for k, v in country_names.items() if not k.startswith("_")}

        # Use _default from admin_levels.json if available
        default_names = admin_levels.get("_default")
        if default_names:
            return {int(k): _extract_display_name(v) for k, v in default_names.items() if not k.startswith("_")}

        return DEFAULT_LEVEL_NAMES
    except Exception as e:
        logger.debug(f"Error loading level names for {iso3}: {e}")
        return DEFAULT_LEVEL_NAMES


def _get_parent_hierarchy(df, parent_id: str, iso3: str) -> list:
    """
    Get list of parent names from immediate parent up to country.
    Returns list like ["California", "United States of America"].
    """
    names = []
    current_id = parent_id
    max_depth = 5  # Safety limit

    for _ in range(max_depth):
        if not current_id:
            break

        # Check if it's the country level
        # Names come from the Display bank. This needs one string, and the
        # exact bank would cost a 400 MB+ read to supply it.
        if current_id == iso3:
            global_df = load_global_country_display_frame()
            if global_df is not None:
                country_row = global_df[global_df["loc_id"] == iso3]
                if len(country_row) > 0:
                    names.append(country_row.iloc[0].get("name", iso3))
            else:
                names.append(iso3)
            break

        # Find in country parquet
        parent_row = df[df["loc_id"] == current_id]
        if len(parent_row) == 0:
            break

        parent_name = parent_row.iloc[0].get("name", current_id)
        names.append(parent_name)

        # Move up to next parent
        current_id = parent_row.iloc[0].get("parent_id")

    return names


def _load_subcounty_for_viewport(iso3: str, admin_level: int, buffered_bbox: tuple, debug: bool = False):
    """
    Load sub-county geometry (levels 3+) from tiered files for a specific country.

    Args:
        iso3: Country code
        admin_level: Target admin level (3+)
        buffered_bbox: (min_lon, min_lat, max_lon, max_lat) with buffer
        debug: If True, add debug properties

    Returns:
        List of GeoJSON features
    """
    all_features = []
    logger.info(f"Loading subcounty geometry for {iso3} level {admin_level}, bbox={buffered_bbox}")

    # Check if this country has sub-county geometry at this level
    # First try non-partitioned (national file)
    df = load_subcounty_geometry(iso3, admin_level=admin_level)

    if df is not None and len(df) > 0:
        # National file exists - filter by bbox
        logger.info(f"Found national file with {len(df)} features for {iso3} level {admin_level}")
        df_filtered = _filter_df_by_bbox(df, buffered_bbox)
        logger.info(f"After bbox filter: {len(df_filtered)} features")
        geojson = df_to_geojson(df_filtered, polygon_only=True)
        if debug:
            for feature in geojson.get("features", []):
                feature["properties"]["current_admin_level"] = admin_level
        all_features.extend(geojson.get("features", []))

    else:
        # Try partitioned files (by state/region)
        # Get regions that intersect the bbox
        logger.info(f"No national file for {iso3} level {admin_level}, trying partitioned files")
        regions = get_regions_in_bbox(iso3, *buffered_bbox)
        logger.info(f"Regions in bbox: {regions}")

        if regions:
            for region_code in regions:
                df = load_subcounty_geometry(
                    iso3, admin_level=admin_level, state_abbrev=region_code,
                    bbox=buffered_bbox,
                )
                if df is None or len(df) == 0:
                    logger.debug(f"No data for {iso3}-{region_code} level {admin_level}")
                    continue

                logger.info(f"Loaded {len(df)} features for {iso3}-{region_code} level {admin_level}")
                logger.info(f"Viewport query returned {len(df)} features")
                geojson = df_to_geojson(df, polygon_only=True)
                if debug:
                    for feature in geojson.get("features", []):
                        feature["properties"]["current_admin_level"] = admin_level
                all_features.extend(geojson.get("features", []))
        else:
            logger.warning(f"No regions found in bbox for {iso3}")

    logger.info(f"Total subcounty features for {iso3} level {admin_level}: {len(all_features)}")
    return all_features


def _filter_df_by_bbox(df, buffered_bbox):
    """Filter DataFrame by bounding box using bbox or centroid columns."""
    if 'bbox_min_lon' in df.columns:
        mask = (
            (df['bbox_max_lon'] >= buffered_bbox[0]) &
            (df['bbox_min_lon'] <= buffered_bbox[2]) &
            (df['bbox_max_lat'] >= buffered_bbox[1]) &
            (df['bbox_min_lat'] <= buffered_bbox[3])
        )
        return df[mask]
    elif 'centroid_lon' in df.columns:
        mask = (
            (df['centroid_lon'] >= buffered_bbox[0]) &
            (df['centroid_lon'] <= buffered_bbox[2]) &
            (df['centroid_lat'] >= buffered_bbox[1]) &
            (df['centroid_lat'] <= buffered_bbox[3])
        )
        return df[mask]
    return df


_crosswalk_reverse_cache: dict = {}


def _get_crosswalk_reverse(iso3: str) -> dict:
    """
    Load crosswalk.json for iso3 and return a reverse map:
      geo_loc_id -> local_abbrev  (e.g. "USA-G109436" -> "NY")

    Result is cached in memory. Returns empty dict if no crosswalk exists.
    """
    if iso3 in _crosswalk_reverse_cache:
        return _crosswalk_reverse_cache[iso3]

    cw = load_country_crosswalk(iso3)
    if not cw:
        _crosswalk_reverse_cache[iso3] = {}
        return {}

    try:
        _, geo_to_local = build_crosswalk_maps(cw)
        reverse = {}
        for geo_loc_id, local_loc_id in geo_to_local.items():
            parts = str(local_loc_id).split("-", 1)
            if len(parts) == 2:
                reverse[geo_loc_id] = parts[1]
        _crosswalk_reverse_cache[iso3] = reverse
        return reverse
    except Exception as e:
        logger.warning(f"Failed to load crosswalk for {iso3}: {e}")
        _crosswalk_reverse_cache[iso3] = {}
        return {}


def get_regions_in_bbox(iso3: str, min_lon: float, min_lat: float, max_lon: float, max_lat: float):
    """
    Return local region/state codes whose bounds intersect the query bbox.
    Uses the country's active Display family to find admin_level=1 regions, then
    resolves geo loc_ids back to local codes via the crosswalk reverse map.
    """
    df = load_country_display_rows(iso3, admin_level=1)
    if df is None or len(df) == 0:
        logger.debug(f"No admin_level=1 data found for {iso3}")
        return []

    crosswalk_reverse = _get_crosswalk_reverse(iso3)

    def resolve_region_code(loc_id: str) -> str:
        """Convert a geo loc_id to a local region code via crosswalk, or fall back to raw segment."""
        if loc_id in crosswalk_reverse:
            return crosswalk_reverse[loc_id]
        # No crosswalk entry - extract second segment as-is
        parts = loc_id.split("-", 1)
        return parts[1] if len(parts) == 2 else loc_id

    result = []
    has_bbox = 'bbox_min_lon' in df.columns
    has_centroid = 'centroid_lon' in df.columns

    if not has_bbox and not has_centroid:
        logger.warning(f"No bbox or centroid columns in {iso3} admin_level=1 parquet")
        for _, row in df.iterrows():
            loc_id = row.get('loc_id', '')
            if loc_id:
                result.append(resolve_region_code(loc_id))
        logger.debug(f"Returning all {len(result)} regions for {iso3} (no spatial filter)")
        return result

    for _, row in df.iterrows():
        intersects = False

        if has_bbox:
            c_min_lon = row.get('bbox_min_lon')
            c_min_lat = row.get('bbox_min_lat')
            c_max_lon = row.get('bbox_max_lon')
            c_max_lat = row.get('bbox_max_lat')

            if pd.notna(c_min_lon) and pd.notna(c_max_lon):
                intersects = (c_max_lon >= min_lon and c_min_lon <= max_lon and
                              c_max_lat >= min_lat and c_min_lat <= max_lat)
        elif has_centroid:
            c_lon = row.get('centroid_lon')
            c_lat = row.get('centroid_lat')
            if pd.notna(c_lon) and pd.notna(c_lat):
                intersects = (c_lon >= min_lon and c_lon <= max_lon and
                              c_lat >= min_lat and c_lat <= max_lat)

        if intersects:
            loc_id = row.get('loc_id', '')
            if loc_id:
                result.append(resolve_region_code(loc_id))

    logger.debug(f"Found {len(result)} regions in bbox for {iso3}: {result}")
    return result


def get_viewport_geometry(admin_level: int, bbox: tuple, debug: bool = False):
    """
    Load features at admin_level within bounding box.

    Args:
        admin_level: Target admin level (0=countries, 1=states, 2=counties, 3=ZCTAs,
                     4=census tracts, 5=block groups, 6=blocks)
        bbox: (min_lon, min_lat, max_lon, max_lat)
        debug: If True, add coverage info for level 0 features

    Returns:
        GeoJSON FeatureCollection with features in viewport
    """
    min_lon, min_lat, max_lon, max_lat = bbox

    # Buffer for smooth panning - proportional to viewport size.
    # Cloud/S3 mode: all levels at 1% to keep feature caps focused on visible area.
    # Local mode (restore when switching back): smart scaling by level:
    #   level 0-1: 0.50  (world/country - few large shapes, prefetch aggressively)
    #   level 2:   0.30  (county/district view)
    #   level 3+:  0.15  (tracts/blocks - many small shapes, tight budget)
    if admin_level >= 3:
        buffer_factor = 0.01
    elif admin_level == 2:
        buffer_factor = 0.01
    else:
        buffer_factor = 0.01
    viewport_width = max_lon - min_lon
    viewport_height = max_lat - min_lat
    buffer_lon = viewport_width * buffer_factor
    buffer_lat = viewport_height * buffer_factor
    buffered_bbox = (
        min_lon - buffer_lon,
        min_lat - buffer_lat,
        max_lon + buffer_lon,
        max_lat + buffer_lat
    )

    # Level 0 is an interactive map payload, so use Display geometry.
    if admin_level == 0:
        df = load_global_country_display_frame()
        if df is None:
            return {"type": "FeatureCollection", "features": []}

        # Filter by bbox if bbox columns exist
        if 'bbox_min_lon' in df.columns:
            mask = (
                (df['bbox_max_lon'] >= buffered_bbox[0]) &
                (df['bbox_min_lon'] <= buffered_bbox[2]) &
                (df['bbox_max_lat'] >= buffered_bbox[1]) &
                (df['bbox_min_lat'] <= buffered_bbox[3])
            )
            df = df[mask]

        geojson = df_to_geojson(df, polygon_only=True)

        # Add coverage info for debug mode (calculate on-the-fly from parquet)
        if debug:
            for feature in geojson.get("features", []):
                loc_id = feature.get("properties", {}).get("loc_id")
                feature["properties"]["current_admin_level"] = admin_level

                if loc_id:
                    # Calculate from actual parquet data, starting from level 1
                    cov_info = calculate_coverage_from_parquet(loc_id, from_level=1)
                    feature["properties"]["actual_depth"] = cov_info.get("actual_depth", 0)
                    feature["properties"]["expected_depth"] = cov_info.get("actual_depth", 0)
                    feature["properties"]["coverage"] = cov_info.get("coverage", 0)
                    feature["properties"]["level_counts"] = cov_info.get("level_counts", {})
                    feature["properties"]["geometry_counts"] = cov_info.get("geometry_counts", {})
                    feature["properties"]["drillable_depth"] = cov_info.get("drillable_depth", 0)
                else:
                    feature["properties"]["actual_depth"] = 0
                    feature["properties"]["expected_depth"] = 0
                    feature["properties"]["coverage"] = 0
                    feature["properties"]["level_counts"] = {}
                    feature["properties"]["geometry_counts"] = {}
                    feature["properties"]["drillable_depth"] = 0

        return geojson

    # Find countries that intersect the viewport
    countries = get_countries_in_bbox(*buffered_bbox)

    if not countries:
        return {"type": "FeatureCollection", "features": []}

    all_features = []

    for iso3 in countries:
        # Browser rendering always follows the active simplified Display
        # release; countries without one retain the GeoBoundaries display bank.
        df = load_country_display_rows(iso3, admin_level=admin_level, bbox=buffered_bbox)

        if df is None or len(df) == 0:
            # Fallback: try one level up if no data at this level
            if admin_level > 0:
                df = load_country_display_rows(iso3, admin_level=admin_level - 1, bbox=buffered_bbox)
            if df is None or len(df) == 0:
                continue

        # Convert to features
        geojson = df_to_geojson(df, polygon_only=True)

        # Add debug info for sub-country levels (calculate on-the-fly from parquet)
        if debug:
            # Calculate from actual parquet data, starting from current admin_level
            cov_info = calculate_coverage_from_parquet(iso3, from_level=admin_level)

            for feature in geojson.get("features", []):
                feature["properties"]["current_admin_level"] = admin_level
                feature["properties"]["actual_depth"] = cov_info.get("actual_depth", 0)
                feature["properties"]["expected_depth"] = cov_info.get("actual_depth", 0)
                feature["properties"]["coverage"] = cov_info.get("coverage", 0)
                feature["properties"]["level_counts"] = cov_info.get("level_counts", {})
                feature["properties"]["geometry_counts"] = cov_info.get("geometry_counts", {})
                feature["properties"]["drillable_depth"] = cov_info.get("drillable_depth", 0)

        all_features.extend(geojson.get("features", []))

    # Per-level feature cap to limit browser memory and S3 transfer volume.
    # Tighter caps at deep zoom where shapes are small and viewport covers fewer.
    MAX_FEATURES_BY_LEVEL = {
        0: 300,   # Countries - compact global Admin0 Display bootstrap
        1: 500,   # States / provinces
        2: 1000,  # Counties / districts
        3: 500,   # Tracts / ZCTAs
        4: 300,   # Block groups
        5: 200,   # Blocks
    }
    MAX_FEATURES = MAX_FEATURES_BY_LEVEL.get(admin_level, 200)
    truncated = False
    if len(all_features) > MAX_FEATURES:
        logger.warning(f"Truncating {len(all_features)} features to {MAX_FEATURES} for admin level {admin_level}")

        # Calculate viewport center
        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2

        # Pre-compute distances once (O(n)) instead of during sort (O(n log n) function calls)
        distances = []
        for f in all_features:
            props = f.get("properties", {})
            f_lon = props.get("centroid_lon")
            f_lat = props.get("centroid_lat")
            if f_lon is None or f_lat is None:
                # Fallback to bbox center
                b1, b2 = props.get("bbox_min_lon"), props.get("bbox_max_lon")
                b3, b4 = props.get("bbox_min_lat"), props.get("bbox_max_lat")
                if b1 is not None and b2 is not None:
                    f_lon, f_lat = (b1 + b2) / 2, (b3 + b4) / 2
                else:
                    distances.append(float('inf'))
                    continue
            distances.append((f_lon - center_lon) ** 2 + (f_lat - center_lat) ** 2)

        # Sort indices by distance, take first N
        sorted_indices = sorted(range(len(all_features)), key=lambda i: distances[i])
        all_features = [all_features[i] for i in sorted_indices[:MAX_FEATURES]]
        truncated = True

    return {
        "type": "FeatureCollection",
        "features": all_features,
        "metadata": {
            "admin_level": admin_level,
            "countries_searched": len(countries),
            "feature_count": len(all_features),
            "truncated": truncated
        }
    }


def clear_cache():
    """Clear all cached geometry data. Useful when data files are updated."""
    global _country_parquet_cache, _global_countries_cache, _country_bounds_cache, _subcounty_geometry_cache, _country_parquet_waiters
    with _country_parquet_cache_lock:
        _country_parquet_cache = OrderedDict()
        _country_parquet_inflight.clear()
        for waiter in _country_parquet_waiters.values():
            waiter.set()
        _country_parquet_waiters = {}
    _global_countries_cache = None
    _country_bounds_cache = None
    _subcounty_geometry_cache = {}
    from .runtime.geometry_loader import resolve_country_display_release
    resolve_country_display_release.cache_clear()
    logger.info("Geometry cache cleared")


def prewarm_geometry() -> None:
    """Pre-warm the global country Display geometry into memory.

    The global country layer is always warm.  In cloud mode the USA county
    bank is also warmed because live NWS frames repeatedly resolve county ids;
    it remains subject to the same bounded LRU budget as all other geometry.
    """
    import time as _time

    if not is_cloud_mode():
        return

    t0 = _time.monotonic()
    try:
        df = load_global_country_display_frame()
        elapsed = _time.monotonic() - t0
        if df is not None and not df.empty:
            logger.info("prewarm geometry Admin0 Display: %d rows in %.1fs", len(df), elapsed)
        else:
            logger.warning("prewarm geometry Admin0 Display: empty result in %.1fs", elapsed)
    except Exception as exc:
        logger.warning("prewarm geometry Admin0 Display failed: %s", exc)

    # NWS is the only current live feed with a repeatedly reused national
    # county display set. Follow the admitted Display release; never hydrate
    # the larger Full authority spine merely to draw an Ops overlay.
    county_geom_file = resolve_country_display_geometry_source("USA")
    county_cache_key = ("display_admin", "USA", 2)
    try:
        with _country_parquet_cache_lock:
            cached = _country_parquet_cache.get(county_cache_key)
        if cached is None and county_geom_file is not None:
            counties = select_rows(
                county_geom_file,
                exact_filters={"admin_level": 2},
                raw_geoparquet=True,
            )
            if counties is not None and not counties.empty:
                with _country_parquet_cache_lock:
                    _cache_country_frame(county_cache_key, counties)
                logger.info("prewarm geometry USA Admin2 Display: %d rows in %.1fs", len(counties), _time.monotonic() - t0)
            else:
                logger.warning("prewarm geometry USA Admin2 Display: empty result")
        elif cached is not None:
            logger.info("prewarm geometry USA Admin2 Display: reused %d rows", len(cached))
        else:
            logger.warning("prewarm geometry USA Admin2 Display release unavailable")
    except Exception as exc:
        logger.warning("prewarm geometry USA Admin2 Display failed: %s", exc)

    logger.info("Geometry pre-warmer complete")


def get_selection_geometries(loc_ids: list):
    """
    Get geometries for specific loc_ids for disambiguation selection mode.

    Args:
        loc_ids: List of location IDs to fetch geometries for

    Returns:
        GeoJSON FeatureCollection with requested geometries
    """
    if not loc_ids:
        return {"type": "FeatureCollection", "features": []}

    features = []
    requested_ids = [str(loc_id).strip() for loc_id in loc_ids if str(loc_id).strip()]

    # The query layout owns both directions of the point -> loc_id -> shape
    # contract. Fetch these rows before graph discovery so get_geometry can
    # always serve an admin loc_id returned by resolve_point without opening
    # the (potentially large) reference graph first.
    query_layout_ids: set[str] = set()
    by_iso3: dict[str, list[str]] = {}
    for loc_id in requested_ids:
        if not str(classify_loc_id_family(loc_id) or "").startswith("admin"):
            continue
        by_iso3.setdefault(loc_id.split("-", 1)[0].upper(), []).append(loc_id)
    for iso3, country_ids in by_iso3.items():
        query_rows = load_admin_spine_query_rows(iso3, country_ids)
        if query_rows is not None and not query_rows.empty:
            query_layout_ids.update(query_rows["loc_id"].astype(str))
            query_geojson = df_to_geojson(query_rows, polygon_only=True)
            features.extend(query_geojson.get("features", []))
        if admin_spine_layout_available(iso3):
            # The admitted layout is authoritative for admin IDs, including
            # exact misses. Probe only the misses for an explicit graph-owned
            # sidechain; otherwise do not guess a deep partition from hyphens.
            unresolved = [loc_id for loc_id in country_ids if loc_id not in query_layout_ids]
            graph_shape_ids = _reference_graph_shape_owned_ids(unresolved) if unresolved else set()
            query_layout_ids.update(set(country_ids) - graph_shape_ids)

    # Explicit family namespaces route straight to their single physical bank.
    # A 10k ZCTA request must be one projected ``loc_id IN`` query, not 10k
    # reference-graph identity probes followed by the same bank query.
    direct_family_ids: set[str] = set()
    direct_groups: dict[tuple[str, str], list[str]] = {}
    for loc_id in requested_ids:
        if loc_id in query_layout_ids:
            continue
        iso3 = loc_id.split("-", 1)[0].upper()
        family = classify_loc_id_family(loc_id)
        if _direct_family_bank_path(family, iso3) is not None:
            direct_groups.setdefault((iso3, str(family)), []).append(loc_id)
    for (iso3, _family), family_ids in direct_groups.items():
        frame = load_geometry_rows_by_loc_ids(iso3, family_ids)
        if frame is not None and not frame.empty:
            direct_family_ids.update(frame["loc_id"].astype(str))
            features.extend(df_to_geojson(frame, polygon_only=True).get("features", []))

    # Graph-owned semantic-family partitions are authoritative for unresolved
    # IDs whose namespace did not select an admitted admin/direct-family bank.
    graph_requests = [
        loc_id for loc_id in requested_ids
        if loc_id not in query_layout_ids and loc_id not in direct_family_ids
    ]
    reference_df = load_reference_graph_geometry(graph_requests) if graph_requests else pd.DataFrame()
    reference_ids: set[str] = set()
    if reference_df is not None and not reference_df.empty:
        reference_ids = set(reference_df["loc_id"].astype(str))
        reference_geojson = df_to_geojson(reference_df, polygon_only=False)
        features.extend(reference_geojson.get("features", []))

    marine_ids = [
        loc_id for loc_id in requested_ids
        if loc_id not in query_layout_ids
        if loc_id not in reference_ids
        if _geometry_family_for_loc_id(loc_id) in {"marine_eez", "water_body"}
    ]
    claimed_ids = query_layout_ids | direct_family_ids | reference_ids | set(marine_ids)
    remaining_ids = [loc_id for loc_id in requested_ids if loc_id not in claimed_ids]

    if marine_ids:
        marine_df = _load_marine_or_reference_geometry(marine_ids)
        if marine_df is not None and len(marine_df) > 0:
            marine_geojson = df_to_geojson(marine_df, polygon_only=True)
            features.extend(marine_geojson.get("features", []))

    # Resolve all country roots in one pass. The world-view Admin Layers load
    # requests every Admin0 id together; filtering and converting the shared
    # display frame once avoids repeating that work for each country.
    country_level_ids = [loc_id for loc_id in remaining_ids if "-" not in loc_id]
    if country_level_ids:
        # Shape tools require Full geometry. The simplified Admin0 frame is a
        # display derivative and cannot answer exact retrieval or border work.
        global_df = load_global_admin0_geometries(country_level_ids)
        if global_df is None:
            global_df = load_global_countries_frame()
        if global_df is not None:
            country_rows = global_df[global_df["loc_id"].isin(country_level_ids)]
            if len(country_rows) > 0:
                country_geojson = df_to_geojson(country_rows, polygon_only=True)
                features.extend(country_geojson.get("features", []))

    # Group sub-country ids by country for efficient display-bank loading.
    by_country = {}
    for loc_id in remaining_ids:
        if loc_id in country_level_ids:
            continue
        parts = loc_id.split("-")
        iso3 = parts[0]
        if iso3 not in by_country:
            by_country[iso3] = []
        by_country[iso3].append(loc_id)

    # For each country, load parquet and filter to requested loc_ids
    for iso3, country_loc_ids in by_country.items():
        sub_level_ids = list(country_loc_ids)
        deep_level_ids = []
        regular_sub_level_ids = []
        if sub_level_ids:
            sub_admin_levels = get_country_sub_admin_levels(iso3)
            for lid in sub_level_ids:
                family = _geometry_family_for_loc_id(lid)
                parts = str(lid).split("-")
                segment_count = len(parts)
                if family in {"overlay_zcta", "overlay_tribal", "overlay_nws_public_zone", "overlay_nws_fire_weather_zone", "can_federal_electoral_district_2013", "can_designated_place", "regional_base"}:
                    regular_sub_level_ids.append(lid)
                elif segment_count >= 4 and sub_admin_levels:
                    deep_level_ids.append(lid)
                else:
                    regular_sub_level_ids.append(lid)

        # Fetch canonical deep sub-country levels from the existing subcounty geometry system.
        if deep_level_ids:
            deep_df = _load_subcounty_rows_by_loc_ids(iso3, deep_level_ids)
            if deep_df is not None and len(deep_df) > 0:
                deep_geojson = df_to_geojson(deep_df, polygon_only=True)
                features.extend(deep_geojson.get("features", []))

        # Fetch remaining sub-country levels from the standard country/crosswalk path.
        if regular_sub_level_ids:
            country_df = load_geometry_rows_by_loc_ids(iso3, regular_sub_level_ids)
            if country_df is not None and len(country_df) > 0:
                sub_geojson = df_to_geojson(country_df, polygon_only=True)
                features.extend(sub_geojson.get("features", []))

    logger.debug(f"Loaded {len(features)} geometries for selection from {len(requested_ids)} loc_ids")

    return {"type": "FeatureCollection", "features": features}


def get_display_geometries(loc_ids: list):
    """Return reusable browser shapes without opening Full/query geometry.

    Administrative country roots use the compact global Admin0 bank. Enriched
    sub-country ids follow their admitted Display release; all other countries
    use the GeoBoundaries display shard. Explicit sidechain families keep their
    own already-display-oriented banks.
    """
    requested_ids = list(dict.fromkeys(
        canonicalize_loc_id(value) for value in (loc_ids or []) if str(value or "").strip()
    ))
    if not requested_ids:
        return {"type": "FeatureCollection", "features": []}

    features: list[dict] = []
    found: set[str] = set()
    country_ids = [value for value in requested_ids if "-" not in value]
    if country_ids:
        frame = load_global_country_display_frame()
        if frame is not None and not frame.empty:
            rows = frame[frame["loc_id"].isin(country_ids)]
            features.extend(df_to_geojson(rows, polygon_only=True).get("features", []))
            found.update(rows["loc_id"].astype(str))

    by_country: dict[str, list[str]] = {}
    for loc_id in requested_ids:
        if loc_id in found or "-" not in loc_id:
            continue
        family = classify_loc_id_family(loc_id)
        if family in {"admin_geometry", "admin_local"}:
            by_country.setdefault(loc_id.split("-", 1)[0].upper(), []).append(loc_id)

    for iso3, country_ids in by_country.items():
        rows = load_country_display_rows(iso3, loc_ids=country_ids)
        if rows is not None and not rows.empty:
            features.extend(df_to_geojson(rows, polygon_only=True).get("features", []))
            found.update(rows["loc_id"].astype(str))

    # Overlay/reference families are already visual banks and are not members
    # of a country's Admin Display release.
    sidechain_ids = [
        value for value in requested_ids
        if value not in found and classify_loc_id_family(value) not in {"admin_geometry", "admin_local"}
    ]
    sidechains_by_country: dict[str, list[str]] = {}
    for loc_id in sidechain_ids:
        sidechains_by_country.setdefault(loc_id.split("-", 1)[0].upper(), []).append(loc_id)
    for iso3, family_ids in sidechains_by_country.items():
        rows = load_geometry_rows_by_loc_ids(iso3, family_ids)
        if rows is not None and not rows.empty:
            features.extend(df_to_geojson(rows, polygon_only=True).get("features", []))

    return {"type": "FeatureCollection", "features": features}


def _geometry_metadata_value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        if str(value).strip():
            return value
    return None


def _geometry_metadata_row(row) -> dict:
    """Return loc_id geometry metadata without polygon payload."""
    declared_has_polygon = _geometry_metadata_value(row, "has_polygon", "has_shape")
    item = {
        "loc_id": row.get("local_loc_id") or row.get("loc_id"),
        "source_loc_id": row.get("source_loc_id"),
        "name": row.get("name"),
        "subtype": _geometry_metadata_value(row, "subtype", "source_native_subtype"),
        "source_native_subtype": row.get("source_native_subtype"),
        "admin_level": row.get("admin_level"),
        "parent_id": row.get("parent_id"),
        "centroid_lon": row.get("centroid_lon"),
        "centroid_lat": row.get("centroid_lat"),
        "bbox_min_lon": row.get("bbox_min_lon"),
        "bbox_min_lat": row.get("bbox_min_lat"),
        "bbox_max_lon": row.get("bbox_max_lon"),
        "bbox_max_lat": row.get("bbox_max_lat"),
        # Reaching this function means an exact row was returned by a geometry
        # bank. Older banks may omit the availability boolean even though the
        # shape column is present; do not force a polygon read just to rediscover
        # that attachment.
        "has_polygon": bool(declared_has_polygon) if declared_has_polygon is not None else True,
        "iso_a3": row.get("iso_a3"),
        "valid_from": _geometry_metadata_value(row, "valid_from", "valid_from_date"),
        "valid_to": _geometry_metadata_value(row, "valid_to", "valid_to_date"),
        "geometry_vintage": row.get("geometry_vintage"),
        "source_vintage": _geometry_metadata_value(row, "source_vintage", "reference_date"),
        "source_id": row.get("source_id"),
        "source_system": row.get("source_system"),
        "geometry_source": row.get("geometry_source"),
        "geometry_bank": row.get("geometry_bank"),
        "bank_id": row.get("bank_id"),
        "release_id": _geometry_metadata_value(row, "geography_release_id", "release_id"),
        "children_count": row.get("children_count"),
        "children_by_level": row.get("children_by_level"),
        "descendants_count": row.get("descendants_count"),
        "descendants_by_level": row.get("descendants_by_level"),
        "land_area": row.get("land_area"),
        "water_area": row.get("water_area"),
    }
    lineage = row.get("lineage")
    if isinstance(lineage, dict) and lineage:
        item["lineage"] = lineage
    return item


def _reference_graph_shape_owned_ids(loc_ids: list[str]) -> set[str]:
    """Return IDs whose active graph identity owns an exact shape bank.

    Sidechain IDs intentionally reuse stable authority-code components and can
    therefore look like deep administrative IDs to the legacy prefix parser.
    The integrated graph is the semantic authority: an explicit ``has_shape``
    plus ``geometry_bank`` declaration must win before an admitted admin query
    layout claims a syntactic lookalike as an authoritative miss.
    """
    requested = [str(loc_id).strip() for loc_id in loc_ids if str(loc_id).strip()]
    if not requested:
        return set()
    try:
        from .runtime.reference_graph import identities

        return {
            str(row.get("loc_id"))
            for row in identities(requested)
            if row.get("has_shape") is True
            and str(row.get("geometry_bank") or "").strip()
            and not str(
                row.get("geography_family") or row.get("family") or ""
            ).strip().lower().startswith("admin")
        }
    except Exception:
        # Graph discovery is an optional fast semantic discriminator here. The
        # existing bounded admin and legacy routing remains the safe fallback.
        return set()


def get_selection_geometry_metadata(loc_ids: list) -> list[dict]:
    """
    Get exact loc_id geometry metadata for lightweight availability checks.

    This deliberately skips GeoJSON feature construction and never returns the
    polygon geometry field. It reuses the same exact-row loaders as
    get_selection_geometries so check/preflight tools stay aligned with the
    runtime geometry spine.
    """
    if not loc_ids:
        return []

    rows: list[dict] = []
    requested_ids = [str(loc_id).strip() for loc_id in loc_ids if str(loc_id).strip()]
    requested_set = set(requested_ids)
    # Query-layout admin IDs should use the same bounded country/Admin1 shard
    # path as polygon retrieval. This avoids a broad reference-graph or legacy
    # bank search merely to answer has-shape and bbox questions.
    query_layout_ids: set[str] = set()
    query_metadata_columns = [
        "loc_id", "parent_id", "admin_level", "name",
        "source_id", "source_system", "source_vintage", "geometry_source",
        "geometry_bank",
        "iso_a3", "has_polygon", "centroid_lon", "centroid_lat",
        "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat",
    ]
    by_iso3: dict[str, list[str]] = {}
    for loc_id in requested_ids:
        if not str(classify_loc_id_family(loc_id) or "").startswith("admin"):
            continue
        by_iso3.setdefault(loc_id.split("-", 1)[0].upper(), []).append(loc_id)
    for iso3, country_ids in by_iso3.items():
        query_rows = load_admin_spine_query_rows(iso3, country_ids, columns=query_metadata_columns)
        if query_rows is not None and not query_rows.empty:
            query_layout_ids.update(query_rows["loc_id"].astype(str))
            for _, query_row in query_rows.iterrows():
                item = _geometry_metadata_row(query_row)
                if item.get("loc_id"):
                    rows.append(item)
        if admin_spine_layout_available(iso3):
            # Keep an explicit graph-owned sidechain eligible while treating
            # every other route miss as an authoritative admin miss.
            unresolved = [loc_id for loc_id in country_ids if loc_id not in query_layout_ids]
            graph_shape_ids = _reference_graph_shape_owned_ids(unresolved) if unresolved else set()
            query_layout_ids.update(set(country_ids) - graph_shape_ids)

    direct_family_ids: set[str] = set()
    direct_groups: dict[tuple[str, str], list[str]] = {}
    for loc_id in requested_ids:
        if loc_id in query_layout_ids:
            continue
        iso3 = loc_id.split("-", 1)[0].upper()
        family = classify_loc_id_family(loc_id)
        if _direct_family_bank_path(family, iso3) is not None:
            direct_groups.setdefault((iso3, str(family)), []).append(loc_id)
    for (iso3, _family), family_ids in direct_groups.items():
        frame = load_geometry_rows_by_loc_ids(
            iso3, family_ids, columns=GEOMETRY_METADATA_COLUMNS,
        )
        if frame is not None and not frame.empty:
            direct_family_ids.update(frame["loc_id"].astype(str))
            for _, row in frame.iterrows():
                item = _geometry_metadata_row(row)
                if item.get("loc_id"):
                    rows.append(item)

    graph_requests = [
        loc_id for loc_id in requested_ids
        if loc_id not in query_layout_ids and loc_id not in direct_family_ids
    ]
    reference_df = (
        load_reference_graph_geometry(graph_requests, columns=GEOMETRY_METADATA_COLUMNS)
        if graph_requests else
        pd.DataFrame(columns=GEOMETRY_METADATA_COLUMNS)
    )
    reference_ids: set[str] = set()
    if reference_df is not None and not reference_df.empty:
        reference_ids = set(reference_df["loc_id"].astype(str))
        for _, row in reference_df.iterrows():
            item = _geometry_metadata_row(row)
            if item.get("loc_id"):
                rows.append(item)

    marine_ids = [
        loc_id for loc_id in requested_ids
        if loc_id not in query_layout_ids
        if loc_id not in reference_ids
        if _geometry_family_for_loc_id(loc_id) in {"marine_eez", "water_body"}
    ]
    claimed_ids = query_layout_ids | direct_family_ids | reference_ids | set(marine_ids)
    remaining_ids = [loc_id for loc_id in requested_ids if loc_id not in claimed_ids]

    if marine_ids:
        marine_df = _load_marine_or_reference_geometry(marine_ids, columns=GEOMETRY_METADATA_COLUMNS)
        if marine_df is not None and not marine_df.empty:
            for _, row in marine_df.iterrows():
                item = _geometry_metadata_row(row)
                if item.get("loc_id"):
                    rows.append(item)

    by_country = {}
    for loc_id in remaining_ids:
        parts = loc_id.split("-")
        iso3 = parts[0]
        by_country.setdefault(iso3, []).append(loc_id)

    for iso3, country_loc_ids in by_country.items():
        country_level_ids = [lid for lid in country_loc_ids if lid == iso3]
        sub_level_ids = [lid for lid in country_loc_ids if lid != iso3]
        deep_level_ids = []
        regular_sub_level_ids = []
        if sub_level_ids:
            sub_admin_levels = get_country_sub_admin_levels(iso3)
            for lid in sub_level_ids:
                family = _geometry_family_for_loc_id(lid)
                segment_count = len(str(lid).split("-"))
                if family in {"overlay_zcta", "overlay_tribal", "overlay_nws_public_zone", "overlay_nws_fire_weather_zone", "can_federal_electoral_district_2013", "can_designated_place", "regional_base"}:
                    regular_sub_level_ids.append(lid)
                elif segment_count >= 4 and sub_admin_levels:
                    deep_level_ids.append(lid)
                else:
                    regular_sub_level_ids.append(lid)

        if country_level_ids:
            # Metadata only; the Display bank carries every column this row
            # builder reads and covers the territories the exact bank folds
            # into their parent country.
            global_df = load_global_country_display_frame()
            if global_df is not None and not global_df.empty:
                country_rows = global_df[global_df["loc_id"].isin(country_level_ids)]
                for _, row in country_rows.iterrows():
                    item = _geometry_metadata_row(row)
                    if item.get("loc_id") in requested_set:
                        rows.append(item)

        if deep_level_ids:
            deep_df = _load_subcounty_rows_by_loc_ids(iso3, deep_level_ids, columns=GEOMETRY_METADATA_COLUMNS)
            if deep_df is not None and not deep_df.empty:
                for _, row in deep_df.iterrows():
                    item = _geometry_metadata_row(row)
                    if item.get("loc_id") in requested_set:
                        rows.append(item)

        if regular_sub_level_ids:
            country_df = load_geometry_rows_by_loc_ids(iso3, regular_sub_level_ids, columns=GEOMETRY_METADATA_COLUMNS)
            if country_df is not None and not country_df.empty:
                for _, row in country_df.iterrows():
                    item = _geometry_metadata_row(row)
                    if item.get("loc_id") in requested_set or item.get("source_loc_id") in requested_set:
                        rows.append(item)

    seen = set()
    deduped = []
    for row in rows:
        loc_id = _row_text(row, "loc_id")
        if not loc_id or loc_id in seen:
            continue
        seen.add(loc_id)
        deduped.append(row)
    logger.debug("Loaded %s geometry metadata rows for %s loc_ids", len(deduped), len(requested_ids))
    return deduped
