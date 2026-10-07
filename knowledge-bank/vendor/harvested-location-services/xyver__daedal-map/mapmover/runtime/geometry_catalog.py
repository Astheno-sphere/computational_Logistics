"""Runtime discovery for named, shared geometry families.

Geometry is not a pack and should not be copied into every source catalog.
This module reads the generated geometry catalog once and gives every chat,
API, and MCP path the same name -> canonical ``loc_id`` lookup.
"""

from __future__ import annotations

import json
import re
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..paths import GEOMETRY_DIR
from ..catalog_cache_policy import control_catalog_cache_epoch
from ..runtime_config import force_remote_data_reads, get_data_plane_mode
from .published_artifacts import read_artifact_json
from geometry_catalog_shared import (
    build_geometry_capability_summary,
    merge_crosswalk_catalog,
    published_geometry_catalog_records,
    public_geometry_catalog_records,
)
from material_policy_shared import combine_material_access
from .geometry_storage_layout import country_catalog_relative


CATALOG_PATH = GEOMETRY_DIR / "geometry_catalog.json"
CROSSWALK_CATALOG_PATH = GEOMETRY_DIR / "crosswalk_catalog.json"


def _empty_country_catalog(country: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "country_code": country,
        "geometry_banks": [],
        "reference_systems": [],
        "crosswalks": [],
        "supporting_crosswalk_assets": [],
        "orphaned_geometry_correspondences": [],
        "summary": {},
    }


def _merge_crosswalks(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("crosswalks"):
        return payload
    crosswalks = None
    if _is_cloud_mode():
        try:
            crosswalks = read_artifact_json("geometry/crosswalk_catalog.json", lane="active")
        except Exception:
            crosswalks = None
    if not isinstance(crosswalks, dict) and not force_remote_data_reads():
        try:
            crosswalks = json.loads(CROSSWALK_CATALOG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            crosswalks = None
    return merge_crosswalk_catalog(payload, crosswalks)


def _normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _is_cloud_mode() -> bool:
    return get_data_plane_mode() == "cloud"


def _fetch_geometry_catalog_from_s3() -> dict[str, Any] | None:
    # The runtime-selected immutable lane is normally published. Release smoke
    # deliberately selects staging and must evaluate that catalog as one
    # coherent activation snapshot.
    payload = read_artifact_json("geometry/geometry_catalog.json", lane="active")
    return payload if isinstance(payload, dict) else None


def _catalog_cache_epoch() -> int:
    return control_catalog_cache_epoch()


@lru_cache(maxsize=2)
def _load_geometry_catalog_cached(_epoch: int) -> dict[str, Any]:
    """Load the generated schema-1.1 geometry catalog."""
    if _is_cloud_mode():
        try:
            payload = _fetch_geometry_catalog_from_s3()
            if isinstance(payload, dict):
                return _merge_crosswalks(payload)
        except Exception:
            pass

    if not force_remote_data_reads():
        try:
            payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return _merge_crosswalks(payload)
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "schema_version": "1.1.0",
        "geometry_collections": [],
        "geometry_families": [],
        "geometry_banks": [],
        "geometry_products": [],
        "release_packages": [],
        "crosswalk_artifacts": [],
        "resolver_groups": [],
        "named_reference_objects": [],
    }


def load_geometry_catalog() -> dict[str, Any]:
    """Load the sole runtime authority, revalidating its cloud object periodically."""
    return _load_geometry_catalog_cached(_catalog_cache_epoch())


@lru_cache(maxsize=128)
def _load_country_geometry_catalog_cached(country: str, _epoch: int) -> dict[str, Any]:
    """Load the additive detailed catalog for one maintained country."""
    if not re.fullmatch(r"[A-Z]{3}", country):
        return _empty_country_catalog(country)
    relative = country_catalog_relative(country)
    if _is_cloud_mode():
        try:
            payload = read_artifact_json(relative, lane="active")
            if isinstance(payload, dict) and str(payload.get("country_code") or "").upper() == country:
                return payload
        except Exception:
            pass
    if not force_remote_data_reads():
        for path in (
            GEOMETRY_DIR.parent / relative,
            GEOMETRY_DIR / "countries" / country / f"{country}_catalog.json",
        ):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and str(payload.get("country_code") or "").upper() == country:
                    return payload
            except (OSError, json.JSONDecodeError):
                continue
    return _empty_country_catalog(country)


def load_country_geometry_catalog(country_scope: str) -> dict[str, Any]:
    country = str(country_scope or "").strip().upper()
    return _load_country_geometry_catalog_cached(country, _catalog_cache_epoch())


def clear_geometry_catalog_cache() -> None:
    _load_geometry_catalog_cached.cache_clear()
    _load_country_geometry_catalog_cached.cache_clear()
    _named_index.cache_clear()
    _named_group_index.cache_clear()
    # Imported late: geometry_inventory reads this module's catalog loader.
    from .geometry_inventory import clear_geometry_inventory_cache

    clear_geometry_inventory_cache()
    from .admin_spine_query import clear_admin_spine_query_cache
    from .global_admin0_query import clear_global_admin0_query_cache
    from .marine_geometry import clear_marine_geometry_cache
    from .reference_graph import clear_reference_graph_cache
    from ..duckdb_helpers import clear_parquet_metadata_cache

    clear_admin_spine_query_cache()
    clear_global_admin0_query_cache()
    clear_marine_geometry_cache()
    clear_reference_graph_cache()
    clear_parquet_metadata_cache()


def geometry_capability_summary(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read the generated capability contract, deriving it for older catalogs."""
    payload = catalog if isinstance(catalog, dict) else load_geometry_catalog()
    summary = payload.get("capability_summary") if isinstance(payload, dict) else None
    if isinstance(summary, dict) and summary:
        return dict(summary)
    return build_geometry_capability_summary(payload if isinstance(payload, dict) else {})


@lru_cache(maxsize=2)
def _named_index(_epoch: int) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    catalog = load_geometry_catalog()
    for entry in catalog.get("named_reference_objects") or []:
        if not isinstance(entry, dict):
            continue
        loc_id = str(entry.get("loc_id") or "").strip().upper()
        label = str(entry.get("label") or "").strip()
        if not loc_id or not label:
            continue
        normalized_entry = dict(entry)
        normalized_entry["loc_id"] = loc_id
        for alias in [loc_id, label, *(entry.get("aliases") or [])]:
            key = _normalize(str(alias))
            if key:
                index.setdefault(key, normalized_entry)
        # “Mediterranean” is a natural request for “Mediterranean Sea”.
        for suffix in (" sea", " ocean", " waters"):
            key = _normalize(label)
            if key.endswith(suffix):
                index.setdefault(key[: -len(suffix)].strip(), normalized_entry)
    return index


@lru_cache(maxsize=2)
def _named_group_index(_epoch: int) -> dict[str, dict[str, Any]]:
    """Index explicit human-name groups before individual geometry aliases.

    A whole-ocean name can represent multiple IHO polygons (Pacific and
    Arctic). It is not safe to select whichever individual polygon happens to
    be first, nor to substitute a legacy X* SST product zone.
    """
    index: dict[str, dict[str, Any]] = {}
    catalog = load_geometry_catalog()
    for entry in catalog.get("resolver_groups") or []:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        loc_ids = [str(value).strip().upper() for value in entry.get("loc_ids") or [] if str(value).strip()]
        if not label:
            continue
        normalized = dict(entry)
        normalized["label"] = label
        normalized["loc_ids"] = loc_ids
        for alias in [label, *(entry.get("aliases") or [])]:
            key = _normalize(str(alias))
            if key:
                index.setdefault(key, normalized)
    return index


def resolve_geometry_name(value: str | None) -> dict[str, Any] | None:
    """Resolve a named shared geometry without falling back to land aliases."""
    key = _normalize(value)
    epoch = _catalog_cache_epoch()
    group = _named_group_index(epoch).get(key)
    if group:
        # Return an explicitly unresolved group as well. Callers can then give
        # a truthful "no approved geometry" result instead of treating a known
        # ocean name as an unknown place or falling back to an X* SST zone.
        return dict(group)
    entry = _named_index(epoch).get(key)
    if not entry or not bool(entry.get("resolvable", True)):
        return None
    return dict(entry)


def expand_geometry_loc_id(value: str | None) -> list[str]:
    """Return a resolvable geometry id plus all catalogued descendants.

    Named-water source rows use the smallest containing polygon. This shared
    expansion makes a parent selection include its detailed child waters.
    """
    root = str(value or "").strip().upper()
    if not root:
        return []
    catalog = load_geometry_catalog()
    entries = [
        entry
        for entry in catalog.get("named_reference_objects") or []
        if isinstance(entry, dict)
    ]
    known = {str(entry.get("loc_id") or "").strip().upper() for entry in entries if bool(entry.get("resolvable", True))}
    if root not in known:
        return []
    children: dict[str, list[str]] = {}
    for entry in entries:
        loc_id = str(entry.get("loc_id") or "").strip().upper()
        parent = str(entry.get("parent_loc_id") or "").strip().upper()
        if loc_id and parent:
            children.setdefault(parent, []).append(loc_id)
    expanded: list[str] = []
    pending = [root]
    while pending:
        loc_id = pending.pop(0)
        if loc_id in expanded:
            continue
        expanded.append(loc_id)
        pending.extend(sorted(children.get(loc_id) or []))
    return expanded


def is_known_geometry_loc_id(value: str | None) -> bool:
    entry = _named_index(_catalog_cache_epoch()).get(_normalize(value))
    return bool(entry and entry.get("loc_id") == str(value or "").strip().upper() and entry.get("resolvable", True))


def geometry_bank_access_facts(
    *,
    scopes: set[str] | None = None,
    families: set[str] | None = None,
    bank_ids: set[str] | None = None,
    surface: str = "hosted_results",
) -> tuple[set[str], bool]:
    """Return commercial-use permissions and hosted publication clearance.

    Every matched bank must carry the generated material-policy contract.
    Missing policy fails closed instead of reconstructing a decision from
    source envelopes at request time.
    """
    catalog = load_geometry_catalog() or {}
    banks = catalog.get("geometry_banks") or {}
    if isinstance(banks, dict):
        banks = list(banks.values())
    if not isinstance(banks, list):
        return set(), False

    normalized_scopes = {str(value).strip().upper() for value in (scopes or set()) if str(value).strip()}
    normalized_families = {str(value).strip().lower() for value in (families or set()) if str(value).strip()}
    normalized_bank_ids = {str(value).strip() for value in (bank_ids or set()) if str(value).strip()}
    valid_surfaces = {"hosted_results", "server_rendered_display", "client_geometry", "download"}
    if surface not in valid_surfaces:
        return set(), False
    matched_banks: list[dict[str, Any]] = []
    partition_permissions: set[str] = set()
    partition_surface_decisions: list[bool] = []
    for bank in banks:
        if not isinstance(bank, dict):
            continue
        bank_scope = str(bank.get("scope") or "").strip().upper()
        bank_family = str(bank.get("family") or "").strip().lower()
        bank_id = str(bank.get("bank_id") or bank.get("id") or "").strip()
        if normalized_bank_ids:
            geometry_path = str(bank.get("geometry_path") or "").replace("\\", "/").strip("/")
            package_manifest = str(bank.get("package_manifest") or "").replace("\\", "/").strip("/")
            package_root = package_manifest.rsplit("/", 1)[0] if "/" in package_manifest else ""
            aliases = {bank_id, geometry_path, package_root}
            aliases.discard("")
            matched = False
            for requested in normalized_bank_ids:
                normalized = requested.replace("\\", "/").strip("/")
                if normalized in aliases or any(
                    normalized and alias.startswith(normalized + "/")
                    for alias in aliases
                ):
                    matched = True
                    break
            if not matched:
                continue
        partition_contract = (
            bank.get("partition_surface_contract")
            if isinstance(bank.get("partition_surface_contract"), dict) else {}
        )
        if normalized_scopes and bank_scope not in normalized_scopes:
            allowlist = set((partition_contract.get("allowed_partitions") or {}).get(surface) or [])
            known = set().union(*(
                set(values or [])
                for values in (partition_contract.get("allowed_partitions") or {}).values()
            )) if partition_contract else set()
            if not normalized_scopes.issubset(known):
                continue
            partition_surface_decisions.append(normalized_scopes.issubset(allowlist))
            if surface == "hosted_results":
                lane_map = partition_contract.get("hosted_permission_partitions") or {}
                for lane in ("free", "paid"):
                    if normalized_scopes.issubset(set(lane_map.get(lane) or [])):
                        partition_permissions.add(lane)
        if normalized_families and bank_family not in normalized_families:
            continue
        matched_banks.append(bank)
    combined = combine_material_access(matched_banks)
    if partition_surface_decisions:
        permissions = partition_permissions or set(combined.get("permissions") or set())
        return permissions, all(partition_surface_decisions)
    return (
        set(combined.get("permissions") or set()),
        bool((combined.get("surface_access") or {}).get(surface)),
    )


def geometry_bank_id_map_for_metadata(rows: list[dict[str, Any]]) -> dict[str, str]:
    """Resolve exact catalog bank ids by loc_id from geometry-row provenance.

    Query-layout Parquet files intentionally store their immutable bank path,
    while the catalog owns the source-granular bank id.  Resolve the path with
    scope and admin level so a shared multi-level file does not broaden the
    material decision to unrelated source records.
    """
    catalog = load_geometry_catalog() or {}
    banks = catalog.get("geometry_banks") or []
    if isinstance(banks, dict):
        banks = list(banks.values())
    banks = [bank for bank in banks if isinstance(bank, dict)]
    known_ids = {
        str(bank.get("bank_id") or bank.get("id") or "").strip()
        for bank in banks
    }
    known_ids.discard("")
    resolved: dict[str, str] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        loc_id = str(row.get("loc_id") or "").strip().upper()
        if not loc_id:
            continue
        explicit_bank_id = str(row.get("bank_id") or "").strip()
        reference = str(row.get("geometry_bank") or explicit_bank_id).replace("\\", "/").strip("/")
        if explicit_bank_id and "/" not in explicit_bank_id and "\\" not in explicit_bank_id:
            # The material gate will still fail closed if this declared id is
            # absent from the catalog. Preserve it here so tests and older
            # banks with a canonical id do not need path reconstruction.
            resolved[loc_id] = explicit_bank_id
            continue
        if reference in known_ids:
            resolved[loc_id] = reference
            continue
        scope = str(row.get("iso_a3") or (loc_id.split("-", 1)[0] if loc_id else "")).strip().upper()
        try:
            admin_level = int(row.get("admin_level"))
        except (TypeError, ValueError):
            admin_level = None
        candidates: list[str] = []
        for bank in banks:
            bank_id = str(bank.get("bank_id") or bank.get("id") or "").strip()
            bank_scope = str(bank.get("scope") or "").strip().upper()
            if scope and bank_scope != scope:
                continue
            if admin_level is not None:
                try:
                    if int(bank.get("admin_level")) != admin_level:
                        continue
                except (TypeError, ValueError):
                    continue
            pattern = str(bank.get("geometry_path") or "").replace("\\", "/").strip("/")
            if reference and pattern and not fnmatchcase(reference, pattern):
                continue
            if bank_id:
                candidates.append(bank_id)
        if len(candidates) == 1:
            resolved[loc_id] = candidates[0]
    return resolved


def geometry_bank_ids_for_metadata(rows: list[dict[str, Any]]) -> set[str]:
    """Return the exact source-granular catalog bank ids for metadata rows."""
    return set(geometry_bank_id_map_for_metadata(rows).values())


def geometry_bank_lineage(bank_reference: str | None) -> dict[str, Any]:
    """Resolve a runtime bank id/path to catalog source/material lineage."""
    requested = str(bank_reference or "").replace("\\", "/").strip("/")
    if not requested:
        return {}
    catalog = load_geometry_catalog() or {}
    banks = catalog.get("geometry_banks") or []
    if isinstance(banks, dict):
        banks = list(banks.values())
    matches: list[dict[str, Any]] = []
    for bank in banks if isinstance(banks, list) else []:
        if not isinstance(bank, dict):
            continue
        geometry_path = str(bank.get("geometry_path") or "").replace("\\", "/").strip("/")
        package_manifest = str(bank.get("package_manifest") or "").replace("\\", "/").strip("/")
        package_root = package_manifest.rsplit("/", 1)[0] if "/" in package_manifest else ""
        aliases = {
            str(bank.get("bank_id") or "").strip(), geometry_path, package_root,
        }
        aliases.discard("")
        if requested in aliases or any(
            alias.startswith(requested + "/") for alias in aliases if requested
        ):
            matches.append(bank)
    if not matches:
        return {}
    source_ids = sorted({
        str(source_id).strip()
        for bank in matches
        for source_id in (
            (bank.get("source_material_identity") or {}).get("source_ids")
            or bank.get("source_ids") or []
        )
        if str(source_id).strip()
    })
    material_ids = sorted({
        str(bank.get("material_id") or bank.get("bank_id") or "").strip()
        for bank in matches
        if str(bank.get("material_id") or bank.get("bank_id") or "").strip()
    })
    release_ids = sorted({
        str(bank.get("release_id") or "").strip()
        for bank in matches if str(bank.get("release_id") or "").strip()
    })
    lineage: dict[str, Any] = {
        "source_ids": source_ids,
        "material_ids": material_ids,
        "bank_ids": sorted({
            str(bank.get("bank_id")) for bank in matches if bank.get("bank_id")
        }),
        "release_ids": release_ids,
    }
    for plural, singular in (
        ("source_ids", "source_id"), ("material_ids", "material_id"),
        ("bank_ids", "bank_id"), ("release_ids", "release_id"),
    ):
        if len(lineage[plural]) == 1:
            lineage[singular] = lineage[plural][0]
    return {key: value for key, value in lineage.items() if value}


def is_deprecated_geometry_loc_id(value: str | None) -> bool:
    entry = _named_index(_catalog_cache_epoch()).get(_normalize(value))
    return bool(entry and entry.get("loc_id") == str(value or "").strip().upper() and not entry.get("resolvable", True))
