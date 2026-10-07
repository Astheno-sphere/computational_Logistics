"""
Shared runtime-owned helper/foundation loaders.

This module centralizes access to small always-available helper assets that should
not be modeled as pack-owned data. Explore is the first lane to formalize onto this
surface, but the intent is that Research and Ops can reuse the same helpers with
their own access patterns later.
"""

from __future__ import annotations

import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from shapely import from_wkb
from shapely.geometry import mapping

from .duckdb_helpers import is_cloud_mode, parquet_columns, path_to_uri, run_df
from .orchestrator_specs import list_orchestrator_specs
from .paths import COUNTRIES_DIR, COUNTRY_GEOMETRY_DIR, DATA_ROOT, GEOMETRY_DIR
from .runtime.explainer_response import build_explainer_response, looks_like_explainer_question
from .runtime.geometry_storage_layout import (
    global_admin0_display_path_from_geometry_root,
    global_admin0_display_relative,
    global_admin0_exact_path_from_geometry_root,
    global_admin0_exact_relative,
)
from .runtime.read_posture import prefer_local_geometry_reads
from .runtime.result_cap import (
    apply_runtime_feature_cap_to_payload,
    apply_runtime_result_cap,
    merge_cap_info,
)
from .runtime.published_artifacts import read_artifact_bytes, read_artifact_json
from .runtime_config import force_remote_data_reads

logger = logging.getLogger("mapmover")

REFERENCE_DIR = Path(__file__).parent / "reference"

FOUNDATION_HELPER_REGISTRY = {
    "reference_json": [
        "admin_levels.json",
        "country_aliases.json",
        "disaster_links.json",
        "disasters.json",
        "iso_codes.json",
        "query_synonyms.json",
        "stopwords.json",
        "unit_conversions.json",
        "water_body_codes.json",
        "usa/usa_admin.json",
    ],
    "country_crosswalks": "geometry/countries/{ISO3}/crosswalk.json",
    "country_json_assets": "countries/{ISO3}/{filename}",
    "global_country_geometry": {
        "display": global_admin0_display_relative(),
        "full": global_admin0_exact_relative(),
    },
    "world_factbook_static": "global/world_factbook_static/all_countries.parquet",
    "orchestrator_specs": "mapmover/orchestrator_specs.py",
    "runtime_result_cap": "mapmover/runtime/result_cap.py",
    "runtime_explainer_response": "mapmover/runtime/explainer_response.py",
    "mode_profiles": {
        "explore": [
            "reference_json",
            "country_crosswalks",
            "global_country_geometry",
            "world_factbook_static",
            "orchestrator_specs",
            "runtime_result_cap",
            "runtime_explainer_response",
        ],
        "research": [
            "country_crosswalks",
            "orchestrator_specs",
            "runtime_result_cap",
            "runtime_explainer_response",
        ],
        "ops": [
            "orchestrator_specs",
            "runtime_result_cap",
            "runtime_explainer_response",
        ],
    },
}

_REFERENCE_JSON_CACHE: dict[str, Any] = {}
_COUNTRY_CROSSWALK_CACHE: dict[tuple[str, str], dict | None] = {}
_COUNTRY_JSON_ASSET_CACHE: dict[tuple[str, str, str], Any] = {}
_GLOBAL_COUNTRIES_CACHE = None
_GLOBAL_COUNTRY_DISPLAY_CACHE = None
_WORLD_FACTBOOK_STATIC_CACHE = None


def clear_foundation_helper_cache() -> None:
    """Clear helper frames whose backing lane can change in local QA."""
    global _GLOBAL_COUNTRIES_CACHE, _GLOBAL_COUNTRY_DISPLAY_CACHE, _WORLD_FACTBOOK_STATIC_CACHE
    _REFERENCE_JSON_CACHE.clear()
    _COUNTRY_CROSSWALK_CACHE.clear()
    _COUNTRY_JSON_ASSET_CACHE.clear()
    _GLOBAL_COUNTRIES_CACHE = None
    _GLOBAL_COUNTRY_DISPLAY_CACHE = None
    _WORLD_FACTBOOK_STATIC_CACHE = None


# One read ladder for every runtime-owned geometry helper artifact. These
# artifacts have to agree with each other - the Admin0 Display bank, the exact
# Admin0 bank, and the per-country crosswalks all describe the same universe -
# so they must not each decide independently which lane to read. The ladder was
# written out by hand in three places and only one of them stated the
# local-verification rule, which is how the lanes drift apart.
#
# Order, strongest first:
#
#   1. localhost explicitly selected strict cloud reads, so ignore local files;
#   2. the local artifact exists, so use it;
#   3. local verification posture (DEPLOYMENT=local + STORAGE_MODE=local), which
#      must never reach the network for a missing artifact;
#   4. cloud mode, so read the published lane;
#   5. nothing to read.
#
# Step 3 cannot fire while step 4 would have succeeded, because
# `prefer_local_geometry_reads()` is false whenever the data plane is cloud. It
# is stated anyway so the posture is visible at the seam instead of implied.
READ_LOCAL = "local"
READ_REMOTE = "remote"
READ_UNAVAILABLE = "unavailable"


def resolve_artifact_read(local_path: Path) -> str:
    """Return which lane a runtime helper artifact should be read from."""
    forced_remote = force_remote_data_reads()
    if forced_remote and is_cloud_mode():
        return READ_REMOTE
    if not forced_remote and local_path.exists():
        return READ_LOCAL
    if prefer_local_geometry_reads():
        return READ_UNAVAILABLE
    if is_cloud_mode():
        return READ_REMOTE
    return READ_UNAVAILABLE


def _parquet_accessible(path: Path) -> bool:
    """Returns True if a parquet file exists locally or is accessible via S3/DuckDB."""
    if not is_cloud_mode():
        return path.exists()
    try:
        cols = parquet_columns(path)
        return bool(cols)
    except Exception:
        return False


def load_reference_json(relative_path: str | Path) -> Any:
    """
    Load a JSON helper asset from the shared runtime reference directory.

    `relative_path` may be a simple filename like `iso_codes.json`, a nested path such as
    `usa/usa_admin.json`, or an absolute Path for compatibility with older callers.
    """
    path = relative_path if isinstance(relative_path, Path) else Path(relative_path)
    if not path.is_absolute():
        path = REFERENCE_DIR / path
    cache_key = str(path.resolve()) if path.exists() else str(path)
    if cache_key in _REFERENCE_JSON_CACHE:
        return _REFERENCE_JSON_CACHE[cache_key]
    if not path.exists():
        _REFERENCE_JSON_CACHE[cache_key] = None
        return None
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        _REFERENCE_JSON_CACHE[cache_key] = data
        return data
    except Exception as e:
        logger.warning(f"Failed to load reference helper {path}: {e}")
        _REFERENCE_JSON_CACHE[cache_key] = None
        return None


def load_reference_dict(relative_path: str | Path) -> dict | None:
    """Load a reference helper asset and return it only when it is a dict."""
    data = load_reference_json(relative_path)
    return data if isinstance(data, dict) else None


def get_foundation_helper_registry() -> dict[str, Any]:
    """Return the declared runtime-owned helper assets."""
    return FOUNDATION_HELPER_REGISTRY


def load_orchestrator_specs() -> dict[str, Any]:
    """Return the shared orchestrator spec registry."""
    return list_orchestrator_specs()


def load_runtime_result_cap_helpers() -> dict[str, Any]:
    """Return the shared runtime cap helpers."""
    return {
        "apply_runtime_result_cap": apply_runtime_result_cap,
        "apply_runtime_feature_cap_to_payload": apply_runtime_feature_cap_to_payload,
        "merge_cap_info": merge_cap_info,
    }


def load_runtime_explainer_helpers() -> dict[str, Any]:
    """Return the shared explainer helpers."""
    return {
        "looks_like_explainer_question": looks_like_explainer_question,
        "build_explainer_response": build_explainer_response,
    }


def _reference_country_codes() -> set[str]:
    data = load_reference_dict("iso_codes.json") or {}
    codes: set[str] = set()
    for section in ("common_countries", "commonly_missing"):
        values = (data.get(section) or {}).get("codes") or []
        codes.update(str(value).strip().upper() for value in values if str(value).strip())
    return codes


def _admin0_country_universe() -> set[str]:
    """Admin0 identities the runtime recognizes, led by the Display bank.

    The Geometry Catalog overlay is the true read of which countries exist and
    how they are tracked, and it takes its shapes from
    `geometry/global/display/admin_0.parquet` and its facts from
    `geometry/geometry_catalog.json`. The exact bank follows that universe so a
    territory added to the published Display bank is recognized here without a
    second edit to the coverage reference.

    `iso_codes.json` stays in the union as a floor. The Display loader fails
    closed when its artifact is missing, and losing that read must not quietly
    shrink exact Admin0 containment back to the territories the shallow global
    bank folds into their parent country.
    """
    codes = _reference_country_codes()
    try:
        display = load_global_country_display_frame()
    except Exception:
        return codes
    if display is None or display.empty or "loc_id" not in display.columns:
        return codes
    codes.update(
        str(value).strip().upper()
        for value in display["loc_id"].dropna()
        if str(value).strip()
    )
    return codes


def load_country_crosswalk(iso3: str) -> dict | None:
    """Load a country crosswalk from the shared runtime helper layer."""
    iso3 = (iso3 or "").upper()
    if not iso3:
        return None
    read_mode = "local" if prefer_local_geometry_reads() else "runtime"
    cache_key = (iso3, read_mode)
    if cache_key in _COUNTRY_CROSSWALK_CACHE:
        return _COUNTRY_CROSSWALK_CACHE[cache_key]

    crosswalk_path = COUNTRY_GEOMETRY_DIR / iso3 / "crosswalk.json"
    lane = resolve_artifact_read(crosswalk_path)
    if lane == READ_LOCAL:
        try:
            with open(crosswalk_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            _COUNTRY_CROSSWALK_CACHE[cache_key] = data
            return data
        except Exception as e:
            logger.warning(f"Failed to load crosswalk for {iso3}: {e}")
            _COUNTRY_CROSSWALK_CACHE[cache_key] = None
            return None

    if lane == READ_REMOTE:
        try:
            data = read_artifact_json(f"geometry/countries/{iso3}/crosswalk.json", lane="published")
            _COUNTRY_CROSSWALK_CACHE[cache_key] = data
            return data
        except Exception as e:
            logger.warning(f"Failed to load crosswalk for {iso3} from cloud storage: {e}")

    _COUNTRY_CROSSWALK_CACHE[cache_key] = None
    return None


def load_country_json_asset(iso3: str, filename: str) -> Any:
    """Load a country-owned JSON asset from `countries/{ISO3}/`."""
    iso3 = (iso3 or "").upper()
    filename = str(filename or "").strip()
    if not iso3 or not filename:
        return None

    read_mode = "local" if prefer_local_geometry_reads() else "runtime"
    cache_key = (iso3, filename, read_mode)
    if cache_key in _COUNTRY_JSON_ASSET_CACHE:
        return _COUNTRY_JSON_ASSET_CACHE[cache_key]

    asset_path = COUNTRIES_DIR / iso3 / filename
    lane = resolve_artifact_read(asset_path)
    if lane == READ_LOCAL:
        try:
            with open(asset_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            _COUNTRY_JSON_ASSET_CACHE[cache_key] = data
            return data
        except Exception as e:
            logger.warning("Failed to load country asset %s/%s: %s", iso3, filename, e)
            _COUNTRY_JSON_ASSET_CACHE[cache_key] = None
            return None

    if lane == READ_REMOTE:
        try:
            data = read_artifact_json(f"countries/{iso3}/{filename}", lane="published")
            _COUNTRY_JSON_ASSET_CACHE[cache_key] = data
            return data
        except Exception as e:
            logger.warning("Failed to load country asset %s/%s from cloud storage: %s", iso3, filename, e)

    _COUNTRY_JSON_ASSET_CACHE[cache_key] = None
    return None


def load_global_countries_frame():
    """Load the exact global country geometry used by query paths."""
    global _GLOBAL_COUNTRIES_CACHE
    if _GLOBAL_COUNTRIES_CACHE is not None:
        return _GLOBAL_COUNTRIES_CACHE

    remote_path = global_admin0_exact_relative()
    full_file = global_admin0_exact_path_from_geometry_root(
        GEOMETRY_DIR, cloud_mode=is_cloud_mode(),
    )

    def _normalize_full(frame: pd.DataFrame) -> pd.DataFrame:
        if "geometry" in frame.columns or "geometry_wkb" not in frame.columns:
            return frame
        normalized = frame.copy()
        normalized["geometry"] = normalized["geometry_wkb"].map(
            lambda value: json.dumps(mapping(from_wkb(value)), separators=(",", ":"))
            if value is not None else None
        )
        normalized["parent_id"] = "WORLD"
        normalized["admin_level"] = 0
        normalized["type"] = "admin"
        normalized["code"] = normalized["loc_id"]
        normalized["iso_a3"] = normalized["loc_id"]
        normalized["has_polygon"] = normalized["geometry"].notna()
        return normalized

    lane = resolve_artifact_read(full_file)
    try:
        if lane == READ_LOCAL:
            frame = pd.read_parquet(full_file)
        elif lane == READ_REMOTE:
            frame = pd.read_parquet(BytesIO(read_artifact_bytes(remote_path, lane="published")))
        else:
            frame = None
        if frame is not None:
            _GLOBAL_COUNTRIES_CACHE = _normalize_full(frame)
            logger.info("Loaded %d countries from %s", len(_GLOBAL_COUNTRIES_CACHE), remote_path if lane == READ_REMOTE else full_file)
            return _GLOBAL_COUNTRIES_CACHE
    except Exception as e:
        logger.warning("Failed to load exact Admin0 geometry at %s: %s", remote_path if lane == READ_REMOTE else full_file, e)

    logger.warning("Full Admin0 geometry is unavailable")
    return None


def load_global_country_display_frame():
    """Load the bounded Admin0 Display artifact used by interactive maps.

    This is the single Admin0 display helper. Every runtime surface that needs
    a country shape, name, bounding box, or metadata column reads this frame,
    and the Geometry Catalog overlay pairs it with
    `geometry/geometry_catalog.json` for status facts. Exact global geometry is
    a compatibility fallback for point containment only; keeping this loader
    separate prevents display simplification from leaking into spatial queries.

    It resolves its lane through the same `resolve_artifact_read` ladder as the
    exact bank, the country crosswalks, and the country JSON assets, so the
    artifacts that describe one universe cannot end up on different lanes in
    the same process.
    """
    global _GLOBAL_COUNTRY_DISPLAY_CACHE
    if _GLOBAL_COUNTRY_DISPLAY_CACHE is not None:
        return _GLOBAL_COUNTRY_DISPLAY_CACHE

    remote_path = global_admin0_display_relative()
    display_file = global_admin0_display_path_from_geometry_root(
        GEOMETRY_DIR, cloud_mode=is_cloud_mode(),
    )
    lane = resolve_artifact_read(display_file)
    try:
        if lane == READ_LOCAL:
            base = pd.read_parquet(display_file)
        elif lane == READ_REMOTE:
            base = pd.read_parquet(BytesIO(read_artifact_bytes(remote_path, lane="published")))
        else:
            base = None

        if base is not None:
            # The published Display artifact is self-contained. Runtime
            # merging would hide an incomplete build and make its row
            # universe depend on a second object-store read.
            _GLOBAL_COUNTRY_DISPLAY_CACHE = base
            logger.info(
                "Loaded %d countries from self-contained Admin0 Display bootstrap at %s",
                len(_GLOBAL_COUNTRY_DISPLAY_CACHE),
                remote_path if lane == READ_REMOTE else display_file,
            )
            return _GLOBAL_COUNTRY_DISPLAY_CACHE
    except Exception as e:
        logger.warning("Failed to load Admin0 Display bootstrap at %s: %s", remote_path if lane == READ_REMOTE else display_file, e)

    # Display callers serialize this frame to clients. Failing closed prevents
    # a missing bounded artifact from silently shipping exact query polygons.
    logger.warning("Admin0 Display bootstrap unavailable")
    return None


def load_world_factbook_static_frame():
    """Load the shared static country-context helper parquet."""
    global _WORLD_FACTBOOK_STATIC_CACHE
    if _WORLD_FACTBOOK_STATIC_CACHE is not None:
        return _WORLD_FACTBOOK_STATIC_CACHE

    factbook_file = DATA_ROOT / "global" / "world_factbook_static" / "all_countries.parquet"
    if not _parquet_accessible(factbook_file):
        logger.warning("world_factbook_static parquet not accessible at %s", factbook_file)
        return None

    try:
        if is_cloud_mode():
            _WORLD_FACTBOOK_STATIC_CACHE = run_df(
                "SELECT * FROM read_parquet(?)", [path_to_uri(factbook_file)]
            )
        else:
            _WORLD_FACTBOOK_STATIC_CACHE = pd.read_parquet(factbook_file)
        logger.info("Loaded %d rows from world_factbook_static", len(_WORLD_FACTBOOK_STATIC_CACHE))
        return _WORLD_FACTBOOK_STATIC_CACHE
    except Exception as e:
        logger.warning("Error loading world_factbook_static parquet: %s", e)
        return None


def bridge_loc_id_family(loc_id: str, target_family: str = "geometry") -> str:
    """
    Translate between a local/canonical loc_id family and the geometry/global family.

    `target_family="geometry"` maps local ids toward geometry/global ids.
    `target_family="local"` maps geometry/global ids back toward preferred local ids.
    """
    canonical = str(loc_id or "").strip()
    if "-" not in canonical:
        return canonical

    iso3 = canonical.split("-", 1)[0].upper()
    crosswalk = load_country_crosswalk(iso3) or {}
    local_to_geo: dict[str, str] = {}
    geo_to_local: dict[str, str] = {}

    for source_map in (crosswalk.get("mappings") or {}, crosswalk.get("admin_2_fips") or {}):
        for local_loc_id, geo_loc_id in source_map.items():
            local_norm = str(local_loc_id or "").strip()
            geo_norm = str(geo_loc_id or "").strip()
            if not local_norm or not geo_norm:
                continue
            local_to_geo[local_norm] = geo_norm
            geo_to_local.setdefault(geo_norm, local_norm)

    if target_family == "local":
        return geo_to_local.get(canonical, canonical)
    return local_to_geo.get(canonical, canonical)
