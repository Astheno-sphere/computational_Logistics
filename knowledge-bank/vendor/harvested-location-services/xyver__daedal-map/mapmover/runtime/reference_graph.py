"""Read the integrated geographic reference graph selected for this runtime.

Hosted deployments use their configured published data tree. Local processes
may point ``GEOGRAPHY_REFERENCE_GRAPH_ROOT`` at one unpublished candidate or
a JSON array of candidate roots for a country batch without uploading data.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from functools import lru_cache

import pyarrow.parquet as pq
from pathlib import Path
from typing import Any, Callable

from ..duckdb_helpers import is_cloud_mode, lease_query_connection, parquet_columns, path_to_uri, select_rows
from ..paths import DATA_ROOT
from ..runtime_config import get_runtime_config
from .published_artifacts import read_artifact_json, relative_data_path
from .geometry_catalog import load_geometry_catalog
from .geometry_storage_layout import (
    country_reference_root,
    country_release_manifest_relative,
    released_artifact_path,
    released_artifact_paths_by_hash,
)


ENV_NAME = "GEOGRAPHY_REFERENCE_GRAPH_ROOT"
PUBLIC_ALIAS_TYPE = "preferred_public_loc_id"
PUBLIC_REFERENCE_PREFIX = "public."
LEGACY_PUBLIC_REFERENCE_PREFIX = "daedalmap.public."

#: Every country publishes its graph in the same place and the same shape.
#: There is one format - a hash-pinned partition index - so this module never
#: branches on generation. A country is discovered by its directory, not by a
#: hardcoded default, which is what lets families and countries be added one at
#: a time without touching the runtime.
COUNTRY_GRAPH_GLOB = "geometry/countries/*/reference_graph"
GLOBAL_GRAPH_RELATIVE = Path("geometry/global/reference_graph")
COUNTRY_REQUIRED_FILES = (
    "identity_partitions.parquet", "endpoint_families.parquet", "manifest.json",
)
FULL_GRAPH_FILES = (
    "identity_partitions.parquet", "alias_partitions.parquet",
    "shape_partitions.parquet", "relationship_partitions.parquet",
    "endpoint_families.parquet", "source_manifests.parquet", "manifest.json",
)
IDENTITY_ROUTE_INDEX = "identity_routes.parquet"
ALIAS_SYSTEM_ROUTE_INDEX = "alias_system_routes.parquet"
GLOBAL_DISCOVERY_RELATIVE = Path("geometry/global/reference_discovery/identifier_index.parquet")
GLOBAL_DISCOVERY_MANIFEST = Path("geometry/global/reference_discovery/manifest.json")

#: Identity columns read from partitions. Partitions span countries and
#: families with differing schemas, and some carry a GEOMETRY column DuckDB
#: cannot return through ``SELECT *``. Naming the columns keeps the result
#: stable; ``union_by_name`` fills a missing one with NULL.
IDENTITY_COLUMNS = (
    "loc_id", "family", "geography_family", "native_id", "name", "parent_loc_id", "admin_level",
    "namespace_release", "valid_from", "valid_to", "frame_id", "has_shape", "geometry_bank",
    "geometry_status", "source_system", "source_vintage", "geometry_loc_id",
    "source_loc_id", "sibling_level", "sibling_anchor_loc_id",
    "smallest_full_container_loc_id", "crosses_sibling_boundaries_at_or_above_anchor",
    "source_area_sq_km", "assignment_method",
)

#: Index file naming the partitions for each logical table.
PARTITION_INDEXES = {
    "identities": "identity_partitions.parquet",
    "identity_versions": "identity_partitions.parquet",
    "aliases": "alias_partitions.parquet",
    "relationships": "relationship_partitions.parquet",
}

IDENTITY_RECENCY_ORDER = (
    "CASE WHEN valid_to IS NULL OR CAST(valid_to AS VARCHAR) = '' THEN 0 ELSE 1 END ASC, "
    "NULLIF(CAST(valid_from AS VARCHAR), '') DESC NULLS LAST, "
    "NULLIF(CAST(namespace_release AS VARCHAR), '') DESC NULLS LAST, "
    "NULLIF(CAST(source_vintage AS VARCHAR), '') DESC NULLS LAST, "
    "NULLIF(CAST(geography_family AS VARCHAR), '') DESC NULLS LAST, "
    "NULLIF(CAST(family AS VARCHAR), '') DESC NULLS LAST"
)


def _sql_path(path: Path) -> str:
    return path_to_uri(path).replace("'", "''")


def _connection():
    return lease_query_connection()


def _relative_data_path(path: Path) -> str:
    return relative_data_path(path, data_root=DATA_ROOT)


@lru_cache(maxsize=16)
def _load_graph_json(path_text: str, cloud_mode: bool) -> dict[str, Any] | None:
    path = Path(path_text)
    if not cloud_mode:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    try:
        # Keep JSON sidecars on the same configured immutable lane as the
        # Parquet graph files. Production's active lane is ``published``;
        # isolated operator QA may explicitly select ``staging``.
        payload = read_artifact_json(_relative_data_path(path), lane="active")
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _graph_json(path: Path) -> dict[str, Any] | None:
    return _load_graph_json(str(path.resolve()), is_cloud_mode())


@lru_cache(maxsize=16)
def _missing_graph_files(
    root_text: str,
    cloud_mode: bool,
    required_files: tuple[str, ...] = COUNTRY_REQUIRED_FILES,
) -> tuple[str, ...]:
    root = Path(root_text)
    missing: list[str] = []
    for filename in required_files:
        path = root / filename
        if filename.endswith(".json"):
            available = _load_graph_json(str(path.resolve()), cloud_mode) is not None
        elif cloud_mode:
            try:
                available = bool(parquet_columns(path))
            except Exception:
                available = False
        else:
            available = path.is_file()
        if not available:
            missing.append(filename)
    return tuple(missing)


@lru_cache(maxsize=4)
def _discover_roots(data_root_text: str, override: str, cloud_mode: bool) -> tuple[tuple[str, str], ...]:
    data_root = Path(data_root_text)
    if override:
        if override.startswith("["):
            if cloud_mode:
                raise ValueError("multi-country graph override is local-only")
            values = json.loads(override)
            if not isinstance(values, list) or not values or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError("candidate graph override must be a nonempty path array")
            selected: list[tuple[str, str]] = []
            seen: set[str] = set()
            for value in values:
                path = Path(value)
                resolved = path.resolve() if path.is_absolute() else (data_root / path).resolve()
                if data_root.resolve() not in resolved.parents:
                    raise ValueError("candidate graph root escaped DATA_ROOT")
                if _missing_graph_files(str(resolved), cloud_mode):
                    raise ValueError(f"candidate graph root is incomplete: {resolved}")
                country = _country_for_root(resolved)
                if not country or country in seen:
                    raise ValueError("candidate graph roots have missing or duplicate countries")
                seen.add(country)
                selected.append((country, str(resolved)))
            return tuple(sorted(selected))
        path = Path(override)
        resolved = path.resolve() if path.is_absolute() else (data_root / path).resolve()
        country = _country_for_root(resolved)
        return ((country, str(resolved)),) if country else (("", str(resolved)),)
    found: list[tuple[str, str]] = []
    for profile in load_geometry_catalog().get("country_profiles") or []:
        if not isinstance(profile, dict):
            continue
        country = str(profile.get("country_code") or "").strip().upper()
        status = str(profile.get("release_status") or "")
        if len(country) != 3 or status not in {"approved_for_publication", "published"}:
            continue
        try:
            clean_candidate = country_reference_root(data_root, country, profile).resolve()
        except ValueError:
            continue
        if cloud_mode:
            candidate = clean_candidate
        else:
            # Local authoring uses the admitted builder output. Published cloud
            # has exactly one supported path: the contained reference root.
            relative = str(profile.get("reference_graph_manifest") or "").replace("\\", "/")
            candidate = (data_root / relative).parent.resolve() if relative.endswith("/manifest.json") else clean_candidate
        if not _missing_graph_files(str(candidate), cloud_mode):
            found.append((country, str(candidate)))
    if cloud_mode:
        return tuple(found)
    admitted = {country for country, _ in found}
    for candidate in sorted(data_root.glob(COUNTRY_GRAPH_GLOB)):
        if _missing_graph_files(str(candidate.resolve()), cloud_mode):
            continue
        manifest = _graph_json(candidate / "manifest.json") or {}
        if manifest.get("graph_scope") not in (None, "", "country"):
            continue
        if str(manifest.get("completeness_status") or "").startswith("partial"):
            continue
        country = _country_for_root(candidate.resolve())
        if country and country not in admitted:
            found.append((country, str(candidate.resolve())))
    return tuple(found)


def _country_for_root(root: Path) -> str:
    manifest = _graph_json(root / "manifest.json") or {}
    country = str(manifest.get("country") or "").strip().upper()
    if country:
        return country
    # Fall back to the owning directory so a graph is still selectable when its
    # manifest predates the country field.
    parts = root.parts
    return parts[parts.index("countries") + 1].upper() if "countries" in parts else ""


def reference_graph_roots() -> dict[str, Path]:
    """Return every discoverable country graph, keyed by ISO3."""
    override = str(os.getenv(ENV_NAME, "")).strip()
    return {
        country: Path(path)
        for country, path in _discover_roots(str(DATA_ROOT), override, is_cloud_mode())
    }


def clear_reference_graph_cache() -> None:
    _load_graph_json.cache_clear()
    _missing_graph_files.cache_clear()
    _discover_roots.cache_clear()
    _global_discovery_index_current.cache_clear()
    _country_discovery_index_current.cache_clear()
    _country_release_paths.cache_clear()
    _partition_source_map.cache_clear()


@lru_cache(maxsize=32)
def _country_release_paths(country: str) -> dict[str, tuple[str, ...]]:
    """Load the one hash-to-clean-path authority for a contained country."""
    profile = next(
        (
            item for item in load_geometry_catalog().get("country_profiles") or []
            if isinstance(item, dict)
            and str(item.get("country_code") or "").upper() == country
            and str(item.get("release_status") or "") in {"approved_for_publication", "published"}
        ),
        None,
    )
    if profile is None:
        return {}
    try:
        relative = country_release_manifest_relative(country, profile)
        manifest = read_artifact_json(relative, lane="active") if is_cloud_mode() else _graph_json(DATA_ROOT / relative)
    except Exception:
        return {}
    expected_reference = f"geometry/countries/{country}/reference/"
    if str(((manifest or {}).get("runtime") or {}).get("reference") or "") != expected_reference:
        return {}
    return released_artifact_paths_by_hash(manifest or {})


def _published_partition_path(root: Path, source: Any, sha256: Any) -> Path:
    original = str(source or "")
    if not is_cloud_mode():
        return DATA_ROOT / original
    country = _country_for_root(root)
    relative = released_artifact_path(original, str(sha256 or ""), _country_release_paths(country))
    return DATA_ROOT / relative


@lru_cache(maxsize=2)
def _global_discovery_index_current(cloud_mode: bool) -> bool:
    """Return whether the compact discovery index matches active graph roots."""
    index_path = DATA_ROOT / GLOBAL_DISCOVERY_RELATIVE
    manifest_path = DATA_ROOT / GLOBAL_DISCOVERY_MANIFEST
    manifest = _graph_json(manifest_path) or {}
    if str(manifest.get("status") or "").upper() != "PASS":
        return False
    try:
        available = bool(parquet_columns(index_path)) if cloud_mode else index_path.is_file()
    except Exception:
        return False
    if not available:
        return False
    expected = manifest.get("source_graphs") or {}
    current: dict[str, str] = {}
    for country, root in reference_graph_roots().items():
        current[country] = str((_graph_json(root / "manifest.json") or {}).get("release_id") or "")
    global_root = global_reference_graph_root()
    if global_root is not None:
        current["__global__"] = str(
            (_graph_json(global_root / "manifest.json") or {}).get("release_id") or ""
        )
    declared = {
        str(key): str((value or {}).get("release_id") or "")
        for key, value in expected.items() if isinstance(value, dict)
    }
    # The compact index may be built from the complete authoring graph while a
    # hosted deployment intentionally serves only catalog-admitted country
    # graphs. An unavailable global fallback does not make the country rows
    # stale; every graph that is actually active must still match exactly, and
    # extra/removed country scopes remain a hard mismatch.
    if "__global__" not in current:
        declared.pop("__global__", None)
    return bool(current) and declared == current


@lru_cache(maxsize=64)
def _country_discovery_index_current(country: str, cloud_mode: bool, root_text: str) -> bool:
    """A country slice stays valid when another country's graph changes."""
    manifest = _graph_json(DATA_ROOT / GLOBAL_DISCOVERY_MANIFEST) or {}
    if str(manifest.get("status") or "").upper() != "PASS":
        return False
    expected = (manifest.get("source_graphs") or {}).get(country) or {}
    release_id = str(expected.get("release_id") or "")
    if not release_id or release_id != str(
        (_graph_json(Path(root_text) / "manifest.json") or {}).get("release_id") or ""
    ):
        return False
    index_path = DATA_ROOT / GLOBAL_DISCOVERY_RELATIVE
    try:
        return bool(parquet_columns(index_path)) if cloud_mode else index_path.is_file()
    except Exception:
        return False


def global_reference_graph_root() -> Path | None:
    """Return the complete global graph used after country authority."""
    root = (DATA_ROOT / GLOBAL_GRAPH_RELATIVE).resolve()
    if _missing_graph_files(str(root), is_cloud_mode(), FULL_GRAPH_FILES):
        return None
    manifest = _graph_json(root / "manifest.json") or {}
    if manifest.get("graph_scope") != "global":
        return None
    if str(manifest.get("completeness_status") or "").startswith("partial"):
        return None
    return root


def graph_root_for_loc_id(loc_id: str | None) -> Path | None:
    """Pick the graph owning a loc_id, using its country prefix."""
    roots = reference_graph_roots()
    if loc_id:
        country = str(loc_id).split("-", 1)[0].strip().upper()
        if country in roots:
            return roots[country]
    return global_reference_graph_root()


def graph_roots_for_loc_id(loc_id: str | None) -> list[Path]:
    """Prefer country authority, then retain the global fallback."""
    roots: list[Path] = []
    country_roots = reference_graph_roots()
    prefix = str(loc_id or "").split("-", 1)[0].strip().upper()
    if prefix in country_roots:
        roots.append(country_roots[prefix])
    elif loc_id:
        # Some authority-owned namespaces are intentionally not ISO-prefixed.
        # Search admitted country graphs deterministically; admission requires
        # singular identity ownership within each graph.
        roots.extend(country_roots[key] for key in sorted(country_roots))
    global_root = global_reference_graph_root()
    if global_root is not None and global_root not in roots:
        roots.append(global_root)
    return roots


def active_reference_graph_root() -> Path | None:
    """Kept for callers that still expect a single root."""
    roots = reference_graph_roots()
    return next(iter(roots.values()), global_reference_graph_root())


def _partition_records(root: Path, table: str) -> list[dict[str, Any]]:
    index_name = PARTITION_INDEXES.get(table)
    if not index_name:
        return []
    index_path = root / index_name
    try:
        if index_path.is_file():
            rows = pq.read_table(index_path, columns=["path", "sha256"]).to_pylist()
        elif is_cloud_mode():
            frame = select_rows(index_path, columns=["path", "sha256"])
            rows = frame.to_dict(orient="records") if "path" in frame.columns else []
        else:
            return []
    except Exception:
        return []
    return rows


@lru_cache(maxsize=128)
def _partition_source_map(root_text: str, table: str) -> dict[str, Path]:
    root = Path(root_text)
    return {
        str(row.get("path")): _published_partition_path(root, row.get("path"), row.get("sha256"))
        for row in _partition_records(root, table)
        if row.get("path")
    }


def _partition_paths(root: Path, table: str) -> list[Path]:
    """Resolve one logical table to the partition files backing it."""
    rows = _partition_records(root, table)
    return list(dict.fromkeys(
        _published_partition_path(root, row.get("path"), row.get("sha256"))
        for row in rows if row.get("path")
    ))


def _route_paths(
    root: Path, index_name: str, key: str, values: list[str],
) -> list[Path]:
    """Resolve optional exact routes without weakening older graph releases."""
    index_path = root / index_name
    if not values:
        return []
    try:
        if index_path.is_file():
            rows = pq.read_table(
                index_path, columns=["path"], filters=[(key, "in", values)],
            ).to_pydict().get("path", [])
        elif is_cloud_mode():
            frame = select_rows(index_path, columns=["path"], in_filters={key: values})
            rows = frame["path"].tolist() if "path" in frame.columns else []
        else:
            return []
    except Exception:
        return []
    table = next((name for name, filename in PARTITION_INDEXES.items() if filename == index_name), "")
    path_map = _partition_source_map(str(root), table)
    return list(dict.fromkeys(path_map.get(str(value), DATA_ROOT / str(value)) for value in rows if value))


def _relationship_route_paths(
    root: Path, family: str, endpoint_column: str,
) -> list[Path]:
    if endpoint_column not in {"source_family", "target_family"} or not family:
        return []
    index_path = root / PARTITION_INDEXES["relationships"]
    try:
        if index_path.is_file():
            rows = pq.read_table(
                index_path, columns=["path"], filters=[(endpoint_column, "=", family)],
            ).to_pydict().get("path", [])
        elif is_cloud_mode():
            frame = select_rows(
                index_path, columns=["path"], exact_filters={endpoint_column: family},
            )
            rows = frame["path"].tolist() if "path" in frame.columns else []
        else:
            return []
    except Exception:
        return []
    path_map = _partition_source_map(str(root), "relationships")
    return list(dict.fromkeys(path_map.get(str(value), DATA_ROOT / str(value)) for value in rows if value))


def _table_source(table: str, *, loc_id: str | None = None) -> str:
    """Build the DuckDB read_parquet argument spanning the relevant graphs.

    A loc_id narrows to its owning country; without one every discovered graph
    is searched, so a lookup still works before the country is known.
    """
    roots = (
        graph_roots_for_loc_id(loc_id)
        if loc_id else
        [*reference_graph_roots().values(), *([global_reference_graph_root()] if global_reference_graph_root() else [])]
    )
    return _table_source_for_roots(table, roots)


def _table_source_for_roots(
    table: str,
    roots: list[Path],
    *,
    loc_ids: list[str] | None = None,
    reference_system: str | None = None,
    relationship_family: str | None = None,
    relationship_endpoint: str | None = None,
) -> str:
    paths: list[str] = []
    for root in roots:
        routed: list[Path] = []
        if table in {"identities", "identity_versions"} and loc_ids:
            routed = _route_paths(root, IDENTITY_ROUTE_INDEX, "loc_id", loc_ids)
        elif table == "aliases" and reference_system:
            routed = _route_paths(
                root, ALIAS_SYSTEM_ROUTE_INDEX, "reference_system", [reference_system],
            )
        elif table == "relationships" and relationship_family and relationship_endpoint:
            routed = _relationship_route_paths(
                root, relationship_family, relationship_endpoint,
            )
        selected = routed or _partition_paths(root, table)
        paths.extend(
            _sql_path(path)
            for path in selected
            if is_cloud_mode() or path.is_file()
        )
    if not paths:
        return ""
    joined = ", ".join(f"'{path}'" for path in paths)
    return f"[{joined}]"


def _identity_columns(loc_id: str | None = None) -> str:
    """Select the stable identity surface even when every partition omits a field."""
    roots = graph_roots_for_loc_id(loc_id) if loc_id else [
        *reference_graph_roots().values(),
        *([global_reference_graph_root()] if global_reference_graph_root() else []),
    ]
    return _identity_columns_for_roots(roots)


def _identity_columns_for_roots(
    roots: list[Path], partition_paths: list[Path] | None = None,
) -> str:
    available: set[str] = set()
    path_groups = [partition_paths] if partition_paths is not None else [
        _partition_paths(root, "identities") for root in roots
    ]
    for paths in path_groups:
        for path in paths:
            try:
                available.update(parquet_columns(path))
            except Exception:
                continue
    expressions: list[str] = []
    for column in IDENTITY_COLUMNS:
        if column == "family" and "admin_level" in available:
            expressions.append(
                "COALESCE(family, 'admin_' || CAST(CAST(admin_level AS BIGINT) AS VARCHAR)) AS family"
                if "family" in available else
                "'admin_' || CAST(CAST(admin_level AS BIGINT) AS VARCHAR) AS family"
            )
        elif column == "parent_loc_id" and "parent_id" in available:
            expressions.append(
                "COALESCE(parent_loc_id, parent_id) AS parent_loc_id"
                if "parent_loc_id" in available else
                "parent_id AS parent_loc_id"
            )
        else:
            expressions.append(column if column in available else f"NULL AS {column}")
    return ", ".join(expressions)


def reference_graph_available() -> bool:
    return bool(reference_graph_roots() or global_reference_graph_root())


def where_is_geography_data(loc_id: str | None = None) -> dict[str, Any]:
    matching_roots = graph_roots_for_loc_id(loc_id) if loc_id else []
    root = matching_roots[0] if matching_roots else active_reference_graph_root()
    configured = str(os.getenv(ENV_NAME, "")).strip()
    available = reference_graph_available()
    result: dict[str, Any] = {
        "ok": available,
        "mode": "explicit_runtime_selection" if configured else "default_runtime_selection",
        "data_root": str(DATA_ROOT),
        "graph_root": str(root) if root else None,
        "country_graph_roots": {country: str(path) for country, path in reference_graph_roots().items()},
        "global_graph_root": str(global_reference_graph_root()) if global_reference_graph_root() else None,
        "selection_variable": ENV_NAME,
        "local_data_uploaded": False,
        "missing_files": list(_missing_graph_files(str(root), is_cloud_mode())) if root else list(COUNTRY_REQUIRED_FILES),
    }
    if available:
        # Report every discovered graph rather than one. A single release id
        # would have to pick a country arbitrarily now that several are served.
        countries: dict[str, Any] = {}
        for country, country_root in reference_graph_roots().items():
            manifest = _graph_json(country_root / "manifest.json") or {}
            countries[country] = {
                "release_id": manifest.get("release_id"),
                "status": manifest.get("status"),
                "publication_status": manifest.get("publication_status"),
                "families": manifest.get("converted_families") or manifest.get("admitted_families"),
                "totals": manifest.get("metrics"),
            }
        result["countries"] = countries
        global_root = global_reference_graph_root()
        if global_root:
            global_manifest = _graph_json(global_root / "manifest.json") or {}
            result["global"] = {
                "release_id": global_manifest.get("release_id"),
                "status": global_manifest.get("status"),
                "publication_status": global_manifest.get("publication_status"),
                "totals": global_manifest.get("metrics"),
            }
        primary = countries.get(_country_for_root(root), {}) if root else {}
        if not primary and global_root:
            primary = result.get("global", {})
        result.update({
            "release_id": primary.get("release_id"),
            "status": primary.get("status"),
            "scope": ",".join([*sorted(countries), *(["GLOBAL"] if global_root else [])]),
            "totals": primary.get("totals"),
        })
    return result


def reference_graph_families() -> list[dict[str, Any]]:
    """List catalog-admitted canonical families, enriched with graph counts.

    ``geometry_catalog.json`` owns discovery. Partition indexes may enrich a
    catalog family with an identity count, but they never independently expose
    a family. This keeps MCP discovery current when one catalog activation adds
    a country or family, including in cloud mode where graph paths are virtual.
    """
    catalog = load_geometry_catalog()
    catalog_families = {
        str(family_id).strip()
        for country in catalog.get("country_family_coverage") or []
        if isinstance(country, dict)
        for family_id in country.get("available_family_ids") or []
        if str(family_id).strip()
    }
    totals = {family: 0 for family in catalog_families}
    scope_by_family = {
        family: {"available": set(), "complete": set(), "partial": set()}
        for family in catalog_families
    }
    for country in catalog.get("country_family_coverage") or []:
        if not isinstance(country, dict):
            continue
        country_code = str(country.get("country_code") or "").strip().upper()
        if not country_code or country_code == "GLOBAL":
            continue
        for family_id in country.get("available_family_ids") or []:
            family_id = str(family_id or "").strip()
            if family_id in scope_by_family:
                scope_by_family[family_id]["available"].add(country_code)
                scope_by_family[family_id]["partial"].add(country_code)
        for family in country.get("families") or []:
            if not isinstance(family, dict) or family.get("available") is not True:
                continue
            family_id = str(family.get("family_id") or "").strip()
            if family_id not in scope_by_family:
                continue
            scope_by_family[family_id]["available"].add(country_code)
            complete = family.get("coverage_complete") is True
            if family_id == "administrative":
                complete = complete and family.get("hierarchy_coverage_complete") is True
            if complete:
                scope_by_family[family_id]["partial"].discard(country_code)
                scope_by_family[family_id]["complete"].add(country_code)
    roots = list(reference_graph_roots().values())
    global_root = global_reference_graph_root()
    if global_root:
        roots.append(global_root)
    for root in roots:
        index_path = root / PARTITION_INDEXES["identities"]
        try:
            if index_path.is_file():
                rows = pq.read_table(index_path, columns=["family", "row_count"]).to_pydict()
            elif is_cloud_mode():
                frame = select_rows(index_path, columns=["family", "row_count"])
                rows = frame.to_dict(orient="list")
            else:
                continue
        except Exception:
            continue
        for family, count in zip(rows.get("family", []), rows.get("row_count", [])):
            name = str(family or "")
            if not name or name not in catalog_families:
                continue
            try:
                rows_count = int(count)
            except (TypeError, ValueError):
                rows_count = 0
            totals[name] += rows_count
    return [
        {
            "family": name,
            "identity_count": identity_count,
            "available_country_codes": sorted(scope_by_family[name]["available"]),
            "complete_country_codes": sorted(scope_by_family[name]["complete"]),
            "partial_country_codes": sorted(scope_by_family[name]["partial"]),
        }
        for name, identity_count in sorted(totals.items())
    ]


def identity(loc_id: str) -> dict[str, Any] | None:
    if not reference_graph_available():
        return None
    connection = _connection()
    try:
        # Query roots one at a time so country authority wins deterministically
        # when its Admin0 loc_id is also present in the global fallback.
        for root in graph_roots_for_loc_id(loc_id):
            partition_paths = (
                _route_paths(root, IDENTITY_ROUTE_INDEX, "loc_id", [str(loc_id)])
                or _partition_paths(root, "identities")
            )
            source = _table_source_for_roots("identities", [root], loc_ids=[str(loc_id)])
            if not source:
                continue
            cursor = connection.execute(
                f"SELECT * FROM (SELECT {_identity_columns_for_roots([root], partition_paths)} "
                f"FROM read_parquet({source}, union_by_name=True)) AS candidates "
                f"WHERE loc_id = ? ORDER BY {IDENTITY_RECENCY_ORDER} LIMIT 1",
                [str(loc_id)],
            )
            row = cursor.fetchone()
            if row is not None:
                return dict(zip([item[0] for item in cursor.description], row))
        return None
    finally:
        connection.close()


def identity_at(loc_id: str, as_of: date | None = None) -> dict[str, Any] | None:
    """Return the graph identity state selected for a requested date.

    ``identity_versions`` may contain several releases for a durable loc_id.
    A dated lookup selects the row whose half-open validity window contains
    the date; an undated lookup retains the canonical ``identities`` behavior.
    """
    if as_of is None:
        return identity(loc_id)
    if not reference_graph_available():
        return None
    connection = _connection()
    try:
        # Country authority wins over the global fallback. Within that graph,
        # an explicit temporal version outranks an undated current-spine row;
        # otherwise the latter would mask every historical frame for an ID
        # shared with the current admin spine.
        for root in graph_roots_for_loc_id(loc_id):
            partition_paths = (
                _route_paths(root, IDENTITY_ROUTE_INDEX, "loc_id", [str(loc_id)])
                or _partition_paths(root, "identity_versions")
            )
            source = _table_source_for_roots(
                "identity_versions", [root], loc_ids=[str(loc_id)],
            )
            if not source:
                continue
            selected = _identity_columns_for_roots([root], partition_paths)
            cursor = connection.execute(
                f"""SELECT * FROM (
                        SELECT {selected}
                        FROM read_parquet({source}, union_by_name=True)
                    ) AS candidates
                    WHERE loc_id = ?
                    ORDER BY
                      CASE
                        WHEN (NULLIF(CAST(valid_from AS VARCHAR), '') IS NOT NULL
                              OR NULLIF(CAST(valid_to AS VARCHAR), '') IS NOT NULL)
                         AND (TRY_CAST(NULLIF(CAST(valid_from AS VARCHAR), '') AS DATE) IS NULL
                              OR TRY_CAST(NULLIF(CAST(valid_from AS VARCHAR), '') AS DATE) <= ?)
                         AND (TRY_CAST(NULLIF(CAST(valid_to AS VARCHAR), '') AS DATE) IS NULL
                              OR TRY_CAST(NULLIF(CAST(valid_to AS VARCHAR), '') AS DATE) > ?)
                          THEN 0
                        WHEN (NULLIF(CAST(valid_from AS VARCHAR), '') IS NOT NULL
                              OR NULLIF(CAST(valid_to AS VARCHAR), '') IS NOT NULL)
                          THEN 1
                        ELSE 2
                      END,
                      {IDENTITY_RECENCY_ORDER}
                    LIMIT 1""",
                [str(loc_id), as_of, as_of],
            )
            row = cursor.fetchone()
            if row is not None:
                return dict(zip([item[0] for item in cursor.description], row))
        return None
    finally:
        connection.close()


def identities(loc_ids: list[str]) -> list[dict[str, Any]]:
    """Return graph identities in caller order with one predicate-pushed scan."""
    requested = list(dict.fromkeys(str(item).strip() for item in loc_ids if str(item).strip()))
    if not requested or not reference_graph_available():
        return []
    # Resolve the shared source before opening DuckDB.  A graph can be
    # discoverable through its catalog while its identity partition index is
    # empty or unavailable; that is a clean fail-closed result, not a reason
    # to construct a connection (or issue a broad fallback query).
    if not _table_source("identities"):
        return []
    # Query roots in authority order.  Combining a country graph with the
    # global fallback in one UNION makes their shared Admin IDs peers and lets
    # physical scan order decide which metadata wins.
    remaining = requested[:]
    found: dict[str, dict[str, Any]] = {}
    connection = _connection()
    try:
        roots: list[Path] = []
        for loc_id in requested:
            for root in graph_roots_for_loc_id(loc_id):
                if root not in roots:
                    roots.append(root)
        selected_columns = ", ".join(f'"{column}"' for column in IDENTITY_COLUMNS)
        for root in roots:
            if not remaining:
                break
            partition_paths = (
                _route_paths(root, IDENTITY_ROUTE_INDEX, "loc_id", remaining)
                or _partition_paths(root, "identities")
            )
            source = _table_source_for_roots("identities", [root], loc_ids=remaining)
            if not source:
                continue
            placeholders = ", ".join("?" for _ in remaining)
            cursor = connection.execute(
                f"""WITH candidates AS (
                        SELECT {_identity_columns_for_roots([root], partition_paths)}
                        FROM read_parquet({source}, union_by_name=True)
                        WHERE loc_id IN ({placeholders})
                    ), ranked AS (
                        SELECT *, row_number() OVER (
                            PARTITION BY loc_id ORDER BY {IDENTITY_RECENCY_ORDER}
                        ) AS __identity_rank
                        FROM candidates
                    )
                    SELECT {selected_columns} FROM ranked WHERE __identity_rank = 1""",
                remaining,
            )
            columns = [item[0] for item in cursor.description]
            for row in cursor.fetchall():
                item = dict(zip(columns, row))
                found[str(item["loc_id"])] = item
            remaining = [loc_id for loc_id in remaining if loc_id not in found]
        return [found[loc_id] for loc_id in requested if loc_id in found]
    finally:
        connection.close()


def aliases_for_loc_id(loc_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    if not reference_graph_available():
        return []
    root = active_reference_graph_root()
    connection = _connection()
    try:
        cursor = connection.execute(
            f"""SELECT * FROM read_parquet({_table_source('aliases')}, union_by_name=True)
                WHERE loc_id = ? ORDER BY reference_system, external_id LIMIT ?""",
            [str(loc_id), max(1, int(limit))],
        )
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def resolve_alias(
    reference_system: str,
    external_id: str,
    *,
    limit: int = 25,
    iso3: str | None = None,
) -> list[dict[str, Any]]:
    if not reference_graph_available():
        return []
    roots = reference_graph_roots()
    country = str(iso3 or "").strip().upper()
    selected_roots = [roots[country]] if country in roots else ([] if country else list(roots.values()))
    global_root = global_reference_graph_root()
    if global_root and not country:
        selected_roots.append(global_root)
    source = _table_source_for_roots(
        "aliases", selected_roots, reference_system=str(reference_system),
    )
    if not source:
        return []
    connection = _connection()
    try:
        cursor = connection.execute(
            f"""SELECT * FROM read_parquet({source}, union_by_name=True)
                WHERE lower(reference_system) = lower(?) AND external_id = ?
                ORDER BY loc_id LIMIT ?""",
            [str(reference_system), str(external_id), max(1, int(limit))],
        )
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def resolve_public_loc_id(loc_id: str) -> dict[str, Any]:
    """Resolve one public loc_id alias to its canonical graph identity.

    Canonical identities always win.  Public aliases are deliberately narrower
    than the graph's general alias surface: only ``preferred_public_loc_id``
    rows in a ``public.*`` reference system may stand in for a
    loc_id.  More than one distinct target fails closed instead of choosing a
    target by partition or row order.
    """
    requested = str(loc_id or "").strip().upper()
    base = {
        "requested_loc_id": requested,
        "loc_id": requested,
        "resolved_from_public_alias": False,
    }
    if not requested or not reference_graph_available():
        return {"ok": True, "status": "unchanged", **base}
    if identity(requested):
        return {"ok": True, "status": "canonical", **base}

    roots = graph_roots_for_loc_id(requested)
    source = _table_source_for_roots("aliases", roots)
    if not source:
        return {"ok": True, "status": "unchanged", **base}
    connection = _connection()
    try:
        cursor = connection.execute(
            f"""SELECT * FROM read_parquet({source}, union_by_name=True)
                WHERE upper(external_id) = ?
                  AND lower(alias_type) = ?
                  AND (lower(reference_system) LIKE ? OR lower(reference_system) LIKE ?)
                ORDER BY reference_system, loc_id""",
            [
                requested,
                PUBLIC_ALIAS_TYPE,
                f"{PUBLIC_REFERENCE_PREFIX}%",
                f"{LEGACY_PUBLIC_REFERENCE_PREFIX}%",
            ],
        )
        columns = [item[0] for item in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()
    if not rows:
        # ZCTA public IDs originally used ``USA-Z-12345``. Current releases
        # publish opaque preferred-public IDs, but the exact Census reference
        # remains durable. Resolve the retired namespace through that official
        # identifier rather than fabricating a canonical loc_id from the code.
        legacy_zcta = re.fullmatch(r"USA-Z-(\d{5})", requested)
        if legacy_zcta:
            rows = resolve_alias(
                "usa.census.2020.zcta5.geoid",
                legacy_zcta.group(1),
                iso3="USA",
                limit=25,
            )
        legacy_tribal = re.fullmatch(r"USA-TRIBAL-(\d{4})", requested)
        if legacy_tribal:
            rows = resolve_alias(
                "usa.census.2025.aiannhce",
                legacy_tribal.group(1),
                iso3="USA",
                limit=25,
            )
    if not rows:
        return {"ok": True, "status": "unchanged", **base}

    targets = sorted({str(row.get("loc_id") or "").strip() for row in rows if str(row.get("loc_id") or "").strip()})
    systems = sorted({str(row.get("reference_system") or "").strip() for row in rows if str(row.get("reference_system") or "").strip()})
    if len(targets) != 1:
        return {
            "ok": False,
            "status": "ambiguous",
            **base,
            "loc_id": None,
            "candidate_loc_ids": targets,
            "reference_systems": systems,
            "error": {
                "code": "ambiguous_public_loc_id",
                "message": "preferred public loc_id resolves to more than one canonical identity",
            },
        }
    target = targets[0]
    if not identity(target):
        return {
            "ok": False,
            "status": "invalid_target",
            **base,
            "loc_id": None,
            "candidate_loc_ids": targets,
            "reference_systems": systems,
            "error": {
                "code": "invalid_public_loc_id_target",
                "message": "preferred public loc_id points to an identity absent from the active graph",
            },
        }
    return {
        "ok": True,
        "status": "resolved",
        **base,
        "loc_id": target,
        "resolved_from_public_alias": True,
        "public_alias": requested,
        "reference_system": systems[0] if len(systems) == 1 else None,
        "reference_systems": systems,
    }


def resolve_public_loc_ids(loc_ids: list[str]) -> list[dict[str, Any]]:
    """Resolve public loc_id aliases in bulk while preserving caller order."""
    requested = [str(loc_id or "").strip().upper() for loc_id in loc_ids]
    unique = list(dict.fromkeys(value for value in requested if value))
    unchanged = {
        value: {
            "ok": True, "status": "unchanged", "requested_loc_id": value,
            "loc_id": value, "resolved_from_public_alias": False,
        }
        for value in unique
    }
    if not unique or not reference_graph_available():
        return [unchanged.get(value, {
            "ok": True, "status": "unchanged", "requested_loc_id": value,
            "loc_id": value, "resolved_from_public_alias": False,
        }) for value in requested]

    canonical = {str(row.get("loc_id") or "") for row in identities(unique)}
    results = dict(unchanged)
    for value in canonical:
        results[value] = {**unchanged[value], "status": "canonical"}
    remaining = [value for value in unique if value not in canonical]
    aliases_by_id: dict[str, list[dict[str, Any]]] = {value: [] for value in remaining}
    groups: dict[tuple[Path, ...], list[str]] = {}
    for value in remaining:
        groups.setdefault(tuple(graph_roots_for_loc_id(value)), []).append(value)

    connection = _connection()
    try:
        for roots, values in groups.items():
            source = _table_source_for_roots("aliases", list(roots))
            if not source:
                continue
            placeholders = ", ".join("?" for _ in values)
            cursor = connection.execute(
                f"""SELECT * FROM read_parquet({source}, union_by_name=True)
                    WHERE upper(external_id) IN ({placeholders})
                      AND lower(alias_type) = ?
                      AND (lower(reference_system) LIKE ? OR lower(reference_system) LIKE ?)
                    ORDER BY external_id, reference_system, loc_id""",
                [*values, PUBLIC_ALIAS_TYPE, f"{PUBLIC_REFERENCE_PREFIX}%", f"{LEGACY_PUBLIC_REFERENCE_PREFIX}%"],
            )
            columns = [item[0] for item in cursor.description]
            for row in cursor.fetchall():
                item = dict(zip(columns, row))
                aliases_by_id.setdefault(str(item.get("external_id") or "").upper(), []).append(item)
    finally:
        connection.close()

    legacy_zcta = {
        match.group(1): value for value in remaining
        if not aliases_by_id.get(value) and (match := re.fullmatch(r"USA-Z-(\d{5})", value))
    }
    legacy_tribal = {
        match.group(1): value for value in remaining
        if not aliases_by_id.get(value) and (match := re.fullmatch(r"USA-TRIBAL-(\d{4})", value))
    }
    for system, values in (
        ("usa.census.2020.zcta5.geoid", legacy_zcta),
        ("usa.census.2025.aiannhce", legacy_tribal),
    ):
        if not values:
            continue
        for row in identify_aliases(list(values), iso3="USA", reference_system=system, limit=max(25, len(values) * 5)):
            requested_id = values.get(str(row.get("external_id") or ""))
            if requested_id:
                aliases_by_id[requested_id].append(row)

    target_ids = list(dict.fromkeys(
        str(row.get("loc_id") or "").strip()
        for rows in aliases_by_id.values() for row in rows
        if str(row.get("loc_id") or "").strip()
    ))
    valid_targets = {str(row.get("loc_id") or "") for row in identities(target_ids)}
    for value in remaining:
        rows = aliases_by_id.get(value) or []
        if not rows:
            continue
        targets = sorted({str(row.get("loc_id") or "").strip() for row in rows if str(row.get("loc_id") or "").strip()})
        systems = sorted({str(row.get("reference_system") or "").strip() for row in rows if str(row.get("reference_system") or "").strip()})
        if len(targets) != 1:
            results[value] = {
                **unchanged[value], "ok": False, "status": "ambiguous", "loc_id": None,
                "candidate_loc_ids": targets, "reference_systems": systems,
                "error": {"code": "ambiguous_public_loc_id", "message": "preferred public loc_id resolves to more than one canonical identity"},
            }
        elif targets[0] not in valid_targets:
            results[value] = {
                **unchanged[value], "ok": False, "status": "invalid_target", "loc_id": None,
                "candidate_loc_ids": targets, "reference_systems": systems,
                "error": {"code": "invalid_public_loc_id_target", "message": "preferred public loc_id points to an identity absent from the active graph"},
            }
        else:
            results[value] = {
                **unchanged[value], "ok": True, "status": "resolved", "loc_id": targets[0],
                "resolved_from_public_alias": True, "public_alias": value,
                "reference_system": systems[0] if len(systems) == 1 else None,
                "reference_systems": systems,
            }
    return [results.get(value, unchanged.get(value, {
        "ok": True, "status": "unchanged", "requested_loc_id": value,
        "loc_id": value, "resolved_from_public_alias": False,
    })) for value in requested]


def public_alias_reference_systems(*, iso3: str | None = None) -> list[dict[str, Any]]:
    """Describe callable preferred-public alias systems in active graphs."""
    roots_by_country = reference_graph_roots()
    country = str(iso3 or "").strip().upper()
    roots = [roots_by_country[country]] if country in roots_by_country else ([] if country else list(roots_by_country.values()))
    source = _table_source_for_roots("aliases", roots)
    if not source:
        return []
    connection = _connection()
    try:
        cursor = connection.execute(
            f"""SELECT reference_system,
                       count(*) AS alias_count,
                       count(DISTINCT external_id) AS public_id_count,
                       count(DISTINCT loc_id) AS identity_count
                FROM read_parquet({source}, union_by_name=True)
                WHERE lower(alias_type) = ?
                  AND (lower(reference_system) LIKE ? OR lower(reference_system) LIKE ?)
                GROUP BY reference_system
                ORDER BY reference_system""",
            [
                PUBLIC_ALIAS_TYPE,
                f"{PUBLIC_REFERENCE_PREFIX}%",
                f"{LEGACY_PUBLIC_REFERENCE_PREFIX}%",
            ],
        )
        return [
            {
                "system": row[0],
                "alias_count": int(row[1]),
                "public_id_count": int(row[2]),
                "identity_count": int(row[3]),
            }
            for row in cursor.fetchall()
        ]
    finally:
        connection.close()


def identify_aliases(
    external_ids: list[str], *, limit: int = 500, iso3: str | None = None,
    reference_system: str | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Return exact aliases while opening only one physical file at a time."""
    requested = list(dict.fromkeys(str(item).strip() for item in external_ids if str(item).strip()))
    if not requested or not reference_graph_available():
        return []
    country = str(iso3 or "").strip().upper()
    roots_by_country = reference_graph_roots()
    roots = [roots_by_country[country]] if country in roots_by_country else (
        [] if country else [
            *roots_by_country.values(),
            *([global_reference_graph_root()] if global_reference_graph_root() else []),
        ]
    )
    placeholders = ", ".join("?" for _ in requested)
    connection = _connection()
    try:
        system_filter = " AND lower(reference_system) = lower(?)" if reference_system else ""
        maximum = max(1, int(limit))
        rows: list[dict[str, Any]] = []
        # Unknown-country discovery normally touches one compact, release-pinned
        # file. A missing/stale derivative falls back safely to graph partitions
        # but still reads them sequentially instead of constructing one huge
        # read_parquet list.
        discovery = DATA_ROOT / GLOBAL_DISCOVERY_RELATIVE
        if country in roots_by_country:
            use_discovery_index = _country_discovery_index_current(
                country, is_cloud_mode(), str(roots_by_country[country]),
            )
        else:
            use_discovery_index = not country and _global_discovery_index_current(is_cloud_mode())
        if use_discovery_index:
            paths = [discovery]
        else:
            paths = []
            for root in roots:
                routed = (
                    _route_paths(
                        root, ALIAS_SYSTEM_ROUTE_INDEX, "reference_system", [str(reference_system)],
                    )
                    if reference_system else []
                )
                paths.extend(routed or _partition_paths(root, "aliases"))
            paths = list(dict.fromkeys(paths))
        for path in paths:
            if cancelled:
                cancelled()
            if not is_cloud_mode() and not path.is_file():
                continue
            parameters = [path_to_uri(path), *requested]
            scope_filter = " AND country_scope = ?" if use_discovery_index and country else ""
            if scope_filter:
                parameters.append(country)
            if reference_system:
                parameters.append(str(reference_system))
            parameters.append(maximum)
            cursor = connection.execute(
                f"""SELECT * FROM read_parquet(?)
                    WHERE external_id IN ({placeholders}){scope_filter}{system_filter}
                    ORDER BY reference_system, external_id, loc_id LIMIT ?""",
                parameters,
            )
            columns = [item[0] for item in cursor.description]
            rows.extend(dict(zip(columns, row)) for row in cursor.fetchall())
        rows.sort(key=lambda row: (
            str(row.get("reference_system") or ""),
            str(row.get("external_id") or ""),
            str(row.get("loc_id") or ""),
        ))
        return rows[:maximum]
    finally:
        connection.close()


def relationships_for_loc_id(
    loc_id: str, *, direction: str = "both", limit: int = 100
) -> list[dict[str, Any]]:
    if not reference_graph_available():
        return []
    direction = str(direction).strip().lower()
    roots = graph_roots_for_loc_id(loc_id)
    node = identity(loc_id) or {}
    implementation_family = str(node.get("family") or "")
    family = (
        implementation_family
        if implementation_family.startswith("admin_")
        else str(node.get("geography_family") or implementation_family)
    )
    connection = _connection()
    try:
        requested_limit = max(1, int(limit))
        def selected_rows(column: str) -> list[dict[str, Any]]:
            endpoint = "source_family" if column == "source_loc_id" else "target_family"
            path = _table_source_for_roots(
                "relationships", roots,
                relationship_family=family or None,
                relationship_endpoint=endpoint,
            )
            if not path:
                return []
            cursor = connection.execute(
                f"SELECT * FROM read_parquet({path}, union_by_name=True) WHERE {column} = ? LIMIT ?",
                [str(loc_id), requested_limit],
            )
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

        if direction == "outgoing":
            rows = selected_rows("source_loc_id")
        elif direction == "incoming":
            rows = selected_rows("target_loc_id")
        else:
            rows = selected_rows("source_loc_id") + selected_rows("target_loc_id")
            rows = list({str(row.get("relationship_id")): row for row in rows}.values())

        rows.sort(key=lambda row: (
            str(row.get("relationship_type") or ""),
            str(row.get("relationship_vintage") or ""),
            str(row.get("relationship_id") or ""),
        ))
        return rows[:requested_limit]
    finally:
        connection.close()
