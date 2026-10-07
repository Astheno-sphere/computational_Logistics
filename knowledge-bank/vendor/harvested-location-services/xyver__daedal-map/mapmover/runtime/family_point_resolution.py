"""Resolve points against explicitly requested canonical geometry families.

The representation manifest is the physical routing authority: its compact
predicate Parquets choose canonical loc_ids, and the reference graph routes
those ids to the authoritative exact shape banks. Crosswalks are deliberately
not part of this path.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from shapely.geometry import Point, shape

from ..catalog_cache_policy import control_catalog_cache_epoch
from ..paths import DATA_ROOT
from ..runtime_config import force_remote_data_reads, get_data_plane_mode
from .geometry_catalog import load_geometry_catalog
from .geometry_inventory import country_capability_record
from .geometry_predicate_query import read_bbox_candidates_for_points
from .published_artifacts import read_artifact_json
from .reference_geometry_bank import load_reference_graph_geometry
from .reference_graph import identity


PREDICATE_ROLE = "query_exact_predicate_index"
EXACT_ROLE = "query_exact_geometry"

# Representation manifests retain a few publisher-facing family labels that
# predate the public geometry catalog.  Route those physical labels through
# the catalog's canonical family ids at the manifest boundary.
MANIFEST_FAMILY_ALIASES = {
    "map_grid": "reference_grid",
    "named_geographical_feature": "named_feature",
}


def normalize_requested_family(value: Any) -> tuple[str, dict[str, str] | None]:
    """Validate one public canonical family without legacy aliasing."""
    family = str(value or "administrative").strip()
    if not family or family.lower() != family or any(
        not (character.islower() or character.isdigit() or character == "_")
        for character in family
    ):
        return "", {
            "code": "invalid_family_id",
            "message": "family must be one lowercase canonical family ID from the geometry catalog.",
        }
    return family, None


def shallow_scope(shallow_loc_id: str) -> tuple[str, str | None, dict[str, str] | None]:
    """Validate a canonical Admin 1-3 loc_id and find its Admin 1 owner."""
    requested = str(shallow_loc_id or "").strip().upper()
    node = identity(requested)
    if not node:
        return "", None, {
            "code": "invalid_shallow_loc_id",
            "message": "shallow_loc_id must be a canonical administrative loc_id returned by resolve_point.",
        }
    try:
        level = int(node.get("admin_level"))
    except (TypeError, ValueError):
        level = -1
    if level < 1 or level > 3:
        return "", None, {
            "code": "invalid_shallow_loc_id",
            "message": "shallow_loc_id must identify an Admin 1, 2, or 3 result from resolve_point.",
        }
    country = requested.split("-", 1)[0]
    current = node
    while int(current.get("admin_level")) > 1:
        parent_id = str(current.get("parent_loc_id") or "").strip()
        current = identity(parent_id) if parent_id else None
        if not current:
            return "", None, {
                "code": "shallow_scope_unresolved",
                "message": "The Admin 1 owner of shallow_loc_id could not be resolved.",
            }
    return country, str(current.get("loc_id") or "").strip(), None


def _manifest_relative_path(country: str) -> str:
    return f"geometry/countries/{country}/downloadable_inputs/representation_manifest.json"


@lru_cache(maxsize=32)
def _representation_manifest_cached(country: str, _epoch: int) -> dict[str, Any]:
    relative = _manifest_relative_path(country)
    local_path = DATA_ROOT / Path(relative)
    if get_data_plane_mode() != "cloud" and not force_remote_data_reads():
        try:
            payload = json.loads(local_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            pass
    try:
        payload = read_artifact_json(relative, lane="active")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def representation_manifest(country: str) -> dict[str, Any]:
    country = str(country or "").strip().upper()
    if len(country) != 3 or not country.isalpha():
        return {}
    return _representation_manifest_cached(country, control_catalog_cache_epoch())


def family_artifacts(country: str) -> dict[str, dict[str, Any]]:
    """Return current predicate/exact artifacts grouped by canonical family."""
    grouped: dict[str, dict[str, Any]] = {}
    for artifact in representation_manifest(country).get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        physical_family = str(artifact.get("family") or "").strip()
        family = MANIFEST_FAMILY_ALIASES.get(physical_family, physical_family)
        role = str(artifact.get("role") or "").strip()
        path = str(artifact.get("path") or "").strip()
        if not family or not path or role not in {PREDICATE_ROLE, EXACT_ROLE}:
            continue
        card = grouped.setdefault(family, {"predicate_paths": [], "exact_paths": [], "shape_count": 0})
        key = "predicate_paths" if role == PREDICATE_ROLE else "exact_paths"
        card[key].append(path)
        if role == PREDICATE_ROLE:
            try:
                card["shape_count"] += int(artifact.get("rows") or 0)
            except (TypeError, ValueError):
                pass

    # Hosted publication deliberately excludes ``downloadable_inputs`` build
    # state.  Every admitted exact family bank already carries the same bbox
    # columns as the compact predicate derivative, so it is a valid (if less
    # compact) predicate source when the representation manifest is absent.
    # This keeps family lookup available from the published catalog closure
    # instead of making a downloadable-package sidecar a runtime dependency.
    manifest_backed = {
        family for family, card in grouped.items()
        if card["predicate_paths"] and card["exact_paths"]
    }
    fallback_families: set[str] = set()
    catalog = load_geometry_catalog()
    for bank in catalog.get("geometry_banks") or []:
        if not isinstance(bank, dict):
            continue
        if str(bank.get("scope") or "").strip().upper() != country:
            continue
        hosted_access = ((bank.get("material_policy") or {}).get("hosted_access") or {})
        if (
            str(bank.get("bank_role") or "") != "graph_ready_sidechain"
            or hosted_access.get("publication_ready") is not True
            or hosted_access.get("paid_allowed") is not True
        ):
            continue
        physical_family = str(bank.get("family") or "").strip()
        family = MANIFEST_FAMILY_ALIASES.get(physical_family, physical_family)
        path = str(bank.get("geometry_path") or "").strip().replace("\\", "/")
        if not family or family.startswith("admin_") or not path.lower().endswith(".parquet"):
            continue
        if family in manifest_backed:
            continue
        if family not in fallback_families:
            grouped[family] = {"predicate_paths": [], "exact_paths": [], "shape_count": 0}
            fallback_families.add(family)
        card = grouped[family]
        if path not in card["predicate_paths"]:
            card["predicate_paths"].append(path)
        if path not in card["exact_paths"]:
            card["exact_paths"].append(path)
        try:
            card["shape_count"] += int(bank.get("row_count") or 0)
        except (TypeError, ValueError):
            pass
    return grouped


def shape_backed_family_ids(country: str) -> set[str]:
    return {
        family for family, card in family_artifacts(country).items()
        if card.get("predicate_paths") and card.get("exact_paths")
    }


def _public_match(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "loc_id", "name", "family", "subtype", "parent_id",
            "source_id", "source_system", "source_vintage",
        )
        if row.get(key) not in (None, "")
    }


def resolve_family_points(
    country: str,
    families: Iterable[str],
    points: Iterable[dict[str, Any]],
) -> list[dict[str, dict[str, Any]]]:
    """Resolve a point batch, returning one explicit outcome per family/point."""
    country = str(country or "").strip().upper()
    requested = list(dict.fromkeys(str(item).strip() for item in families if str(item).strip()))
    point_rows = list(points)
    results: list[dict[str, dict[str, Any]]] = [dict() for _ in point_rows]
    if not requested or not point_rows:
        return results

    capability = country_capability_record(load_geometry_catalog(), country) or {}
    available = set(capability.get("available_family_ids") or [])
    artifacts = family_artifacts(country)

    for family in requested:
        if family not in available:
            for result in results:
                result[family] = {
                    "family": family,
                    "status": "family_not_available",
                    "matches": [],
                }
            continue

        family_files = artifacts.get(family) or {}
        predicate_paths = family_files.get("predicate_paths") or []
        exact_paths = family_files.get("exact_paths") or []
        if not predicate_paths or not exact_paths:
            for result in results:
                result[family] = {
                    "family": family,
                    "status": "family_lookup_error",
                    "matches": [],
                    "error": {
                        "code": "family_shape_index_missing",
                        "message": "The published family is missing its predicate or exact-shape artifact.",
                    },
                }
            continue

        started = time.perf_counter()
        candidates_by_point: list[set[str]] = [set() for _ in point_rows]
        try:
            for relative_path in predicate_paths:
                candidates = read_bbox_candidates_for_points(
                    DATA_ROOT / Path(relative_path),
                    point_rows,
                    columns=["loc_id"],
                )
                for row in candidates.to_dict("records"):
                    position = int(row.get("point_position"))
                    loc_id = str(row.get("loc_id") or "").strip()
                    if 0 <= position < len(point_rows) and loc_id:
                        candidates_by_point[position].add(loc_id)

            candidate_ids = sorted(set().union(*candidates_by_point)) if candidates_by_point else []
            shapes_by_id: dict[str, tuple[dict[str, Any], Any]] = {}
            shape_records = (
                load_reference_graph_geometry(candidate_ids).to_dict("records")
                if candidate_ids else []
            )
            for row in shape_records:
                loc_id = str(row.get("loc_id") or "").strip()
                if not loc_id or not row.get("geometry"):
                    continue
                shapes_by_id[loc_id] = (row, shape(row["geometry"]))

            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            for position, point_row in enumerate(point_rows):
                point = Point(float(point_row["lon"]), float(point_row["lat"]))
                matches = [
                    _public_match(shapes_by_id[loc_id][0])
                    for loc_id in sorted(candidates_by_point[position])
                    if loc_id in shapes_by_id and shapes_by_id[loc_id][1].covers(point)
                ]
                results[position][family] = {
                    "family": family,
                    "status": "matched" if matches else "no_point_overlap",
                    "matches": matches,
                    "candidate_count": len(candidates_by_point[position]),
                    "timing_ms": elapsed_ms,
                }
        except Exception as exc:
            for result in results:
                result[family] = {
                    "family": family,
                    "status": "family_lookup_error",
                    "matches": [],
                    "error": {"code": "family_lookup_failed", "message": str(exc)},
                }
    return results


def resolve_marine_points(points: Iterable[dict[str, Any]]) -> list[dict[str, dict[str, Any]]]:
    """Project the existing direct Marine resolver into the family contract."""
    from .loc_id_resolution import _resolve_points_to_marine_stacks

    point_rows = list(points)
    resolved = _resolve_points_to_marine_stacks(point_rows, include_geometry=False)
    results: list[dict[str, dict[str, Any]]] = []
    for raw in resolved:
        matches: list[dict[str, Any]] = []
        if isinstance(raw, dict) and isinstance(raw.get("matched"), dict):
            matches.append(_public_match(raw["matched"]))
            matches.extend(
                _public_match(row)
                for row in raw.get("overlap_families") or []
                if isinstance(row, dict)
            )
        results.append({
            "marine": {
                "family": "marine",
                "status": "matched" if matches else "no_point_overlap",
                "matches": matches,
            }
        })
    return results
