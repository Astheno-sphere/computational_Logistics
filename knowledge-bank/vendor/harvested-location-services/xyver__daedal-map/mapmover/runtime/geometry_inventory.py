"""Role-aware Geometry Catalog overlay payload.

The Explore ``Geometry Catalog`` overlay answers one public question on a
world map: what administrative depth and geometry families are usable now?
Master/admin accounts receive the richer stewardship view from the same
catalog authority; ordinary users never receive its candidate or workflow
fields.

Two inputs, with a strict division of labour:

- ``geometry/global/display/admin_0.parquet`` supplies **shapes only**. It is the
  bounded 2.3 MB simplified Admin0 bootstrap the map already loads, so the
  browser never receives exact world geometry for a status view.
- ``geometry/geometry_catalog.json`` supplies **every fact**. The route then
  selects either the public capability projection or the internal lifecycle
  projection from the authenticated account context.

The hierarchy counts that ride along in the Admin0 frame
(``descendants_by_level``) describe the geoBoundaries bank only and cap at 2
for every country, including the ones with deeper adopted spines. They are
deliberately not used here. When per-country baseline depth needs to be more
precise than the global program row, the fix belongs in
``build_geometry_catalog.py`` so the catalog stays the single authority.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .geometry_catalog import load_geometry_catalog


# Lifecycle vocabulary from the geography family framework. Kept in one place
# so the overlay, its popup, and the account-page matrix speak the same words.
FAMILY_STATE_LABELS = {
    "not_inventoried": "Not inventoried",
    "not_applicable": "N/A",
    "discovered": "Discovered",
    "acquired": "Acquired",
    "staged": "Staged",
    "semantic_qa": "Semantic QA",
    "graph_admitted": "Graph admitted",
    "runtime_qa": "Runtime QA",
    "published": "Published",
    "blocked_license": "License blocked",
    "upstream_empty": "Upstream empty",
    "unavailable_machine_readable": "Unavailable",
}

# States that count as available for discovery, per the country import
# toolchain. Earlier stages stay visible in this admin view.
AVAILABLE_STATES = {"graph_admitted", "runtime_qa", "published"}

# Depth ramp, emitted with the payload so the legend and the map cannot drift
# apart. Scaled around Admin 2, which is most of the world and stays a calm
# neutral blue so the outliers read against it. Depth 3 and 4 are deliberately
# close - almost nothing lands there - while 5 and 6 brighten toward green to
# mark a country with a real national spine, and 0/1 sit warm on the other end.
DEPTH_COLORS = {
    0: "#e03131",
    1: "#9c36b5",
    2: "#5b8db8",
    3: "#1c4f8a",
    4: "#14663c",
    5: "#2f9e44",
    6: "#51cf66",
}

# Countries at or below this are hard to see at world zoom - Vatican City is
# 0.5 km2 and Bermuda 52. The overlay offers an optional marker for them rather
# than letting a country's inventory state be unreadable because the country is
# small.
#
# Country areas are close to log-continuous, so there is no natural cliff to
# snap to; this is a display choice about how many markers belong in the ocean.
# Nothing else keys off it.
SMALL_COUNTRY_AREA_KM2 = 10000.0
DEPTH_COLOR_UNKNOWN = "#6b7280"
MAX_RAMP_LEVEL = max(DEPTH_COLORS)


def family_state_label(value: Any) -> str:
    state = str(value or "not_inventoried").strip()
    if state in FAMILY_STATE_LABELS:
        return FAMILY_STATE_LABELS[state]
    return state.replace("_", " ").strip().capitalize() or "Not inventoried"


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _scope_code(value: Any) -> str:
    return str(value or "").strip().upper()


def _coverage_rows(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in (catalog.get("country_family_coverage") or [])
        if isinstance(item, dict)
    ]


def _administrative_family(row: dict[str, Any]) -> dict[str, Any]:
    for family in row.get("families") or []:
        if isinstance(family, dict) and str(family.get("family_id") or "") == "administrative":
            return family
    return {}


def _family_card(family: dict[str, Any]) -> dict[str, Any]:
    state = str(family.get("state") or "not_inventoried").strip()
    card = {
        "family_id": family.get("family_id"),
        "label": family.get("label"),
        "short_label": family.get("short_label") or family.get("label"),
        "description": family.get("description"),
        "state": state,
        "state_label": family_state_label(state),
        "available": bool(family.get("available")) or state in AVAILABLE_STATES,
        "national_authority": family.get("national_authority"),
        "national_baseline": family.get("national_baseline"),
        "gap_or_disposition": family.get("gap_or_disposition"),
        "implementation_count": _as_int(family.get("implementation_count")) or 0,
        "max_admin_level": _as_int(family.get("max_admin_level")),
        "active_admin_depth": _as_int(family.get("active_admin_depth")),
        "candidate_admin_depth": _as_int(family.get("candidate_admin_depth")),
        "candidate_admin_status": family.get("candidate_admin_status"),
        "coverage_status": family.get("coverage_status") or "unknown",
        "coverage_complete": bool(family.get("coverage_complete")),
        "coverage_basis": family.get("coverage_basis"),
        "coverage_denominator": family.get("coverage_denominator") or {},
        "hierarchy_coverage_status": family.get("hierarchy_coverage_status"),
        "hierarchy_coverage_complete": bool(family.get("hierarchy_coverage_complete")),
        "hierarchy_node_count": _as_int(family.get("hierarchy_node_count")),
    }
    for optional in (
        "source_releases",
        "source_licenses",
        "subtypes",
        "covered_jurisdictions",
        "unresolved_jurisdictions",
        "terminal_empty_or_not_applicable_jurisdictions",
        "candidate_admin_source_releases",
        "candidate_admin_source_licenses",
    ):
        values = family.get(optional)
        if isinstance(values, list) and values:
            card[optional] = [str(value) for value in values]
    return card


def _program_card(row: dict[str, Any]) -> dict[str, Any]:
    families = [
        _family_card(family)
        for family in (row.get("families") or [])
        if isinstance(family, dict)
    ]
    return {
        "country_code": _scope_code(row.get("country_code")),
        "label": row.get("label"),
        "program_scope": row.get("program_scope"),
        "strongest_claim": row.get("strongest_claim"),
        "inventory_as_of": row.get("inventory_as_of"),
        "coverage_matrix_status": row.get("coverage_matrix_status"),
        "available_family_ids": [
            str(value) for value in (row.get("available_family_ids") or [])
        ],
        "complete_family_ids": [
            str(value) for value in (row.get("complete_family_ids") or [])
        ],
        "admin_hierarchy_coverage_status": row.get("admin_hierarchy_coverage_status"),
        "admin_hierarchy_coverage_complete": bool(row.get("admin_hierarchy_coverage_complete")),
        "admin_hierarchy_node_count": _as_int(row.get("admin_hierarchy_node_count")),
        "max_admin_level": _as_int(row.get("max_admin_level")),
        "active_admin_depth": _as_int(row.get("active_admin_depth")),
        "candidate_admin_depth": _as_int(row.get("candidate_admin_depth")),
        "candidate_admin_status": row.get("candidate_admin_status"),
        "families": families,
    }


def depth_color(level: int | None) -> str:
    if level is None:
        return DEPTH_COLOR_UNKNOWN
    if level >= MAX_RAMP_LEVEL:
        return DEPTH_COLORS[MAX_RAMP_LEVEL]
    return DEPTH_COLORS.get(level, DEPTH_COLOR_UNKNOWN)


def build_depth_index(catalog: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Resolve admin depth per ISO3 entirely from the geometry catalog.

    Precedence, strongest first:

    1. the country's own coverage row (an inventoried national program);
    2. ``global_admin_baseline``, the depth the shared bank actually holds for
       that country;
    3. the GLOBAL program row, which describes the baseline program as a whole.

    Tier 2 exists because tier 3 is a claim about the program, not about a
    country: it reports Admin 2 for Aruba, which holds nothing below its own
    outline.

    Geometry products are deliberately not a depth authority. A locally built
    or half-generated product may be a useful candidate, but only a country
    inventory/admission record may raise active runtime depth above the shared
    bank. Candidate depth remains visible as separate metadata.
    """
    rows_by_code = {_scope_code(row.get("country_code")): row for row in _coverage_rows(catalog)}
    global_row = rows_by_code.get("GLOBAL") or {}
    global_depth = _as_int(global_row.get("max_admin_level"))
    if global_depth is None:
        global_depth = _as_int(_administrative_family(global_row).get("max_admin_level"))

    index: dict[str, dict[str, Any]] = {}
    for code, row in rows_by_code.items():
        if code == "GLOBAL":
            continue
        admin = _administrative_family(row)
        level = _as_int(row.get("active_admin_depth"))
        if level is None:
            level = _as_int(row.get("max_admin_level"))
        if level is None:
            level = _as_int(admin.get("active_admin_depth"))
        if level is None:
            level = _as_int(admin.get("max_admin_level"))
        index[code] = {
            "max_admin_level": level,
            "candidate_admin_depth": _as_int(row.get("candidate_admin_depth")),
            "candidate_admin_status": row.get("candidate_admin_status"),
            "depth_source": "country_program",
            "program": _program_card(row),
            "admin_family": _family_card(admin) if admin else None,
        }

    for row in catalog.get("global_admin_baseline") or []:
        if not isinstance(row, dict):
            continue
        code = _scope_code(row.get("country_code"))
        level = _as_int(row.get("max_admin_level"))
        if not code or code in index or level is None:
            continue
        index[code] = {
            "max_admin_level": level,
            "depth_source": "shared_bank_baseline",
            "program": None,
            "admin_family": None,
        }

    return index, {
        "max_admin_level": global_depth,
        "program": _program_card(global_row) if global_row else None,
        "admin_family": _family_card(_administrative_family(global_row)) if global_row else None,
    }


def country_capability_record(catalog: dict[str, Any], country_scope: str) -> dict[str, Any] | None:
    """Project one machine-readable country record from the overlay's index."""
    country_code = _scope_code(country_scope)
    if not country_code:
        return None
    depth_index, _global_entry = build_depth_index(catalog)
    resolved = depth_index.get(country_code)
    if resolved is None:
        return None
    baseline = next((
        item for item in catalog.get("global_admin_baseline") or []
        if isinstance(item, dict) and _scope_code(item.get("country_code")) == country_code
    ), {})
    profile = next((
        item for item in catalog.get("country_profiles") or []
        if isinstance(item, dict)
        and _scope_code(item.get("country_code")) == country_code
        and str(item.get("release_status") or "") in {"approved_for_publication", "published"}
    ), {})
    program = resolved.get("program") or {}
    # Shape eligibility is derived from the already-published representation
    # manifest. It is a property on the existing family cards, not a second
    # registry or another caller-facing allowlist.
    from .family_point_resolution import family_artifacts

    shape_artifacts = family_artifacts(country_code)
    available_families = [
        {
            **{
                key: family.get(key)
                for key in (
                    "family_id", "label", "short_label", "description",
                    "coverage_status", "coverage_complete", "coverage_basis",
                    "coverage_denominator", "hierarchy_coverage_status",
                    "hierarchy_coverage_complete", "hierarchy_node_count",
                    "covered_jurisdictions", "unresolved_jurisdictions",
                )
                if family.get(key) not in (None, "")
            },
            "has_shapes": (
                family.get("family_id") == "administrative"
                or bool((shape_artifacts.get(str(family.get("family_id") or "")) or {}).get("predicate_paths"))
            ),
        }
        for family in program.get("families") or []
        if isinstance(family, dict) and family.get("available") is True
    ]
    active_depth = _as_int(resolved.get("max_admin_level"))
    available_family_ids = list(program.get("available_family_ids") or [])
    if not available_family_ids and not profile and baseline:
        available_family_ids = ["administrative"]
    has_country_layout = bool(profile.get("query_layout_manifest"))
    if has_country_layout:
        deep_enabled = active_depth is not None and active_depth > 3
        query_guidance = {
            "model": "country_administrative_spine",
            "shallow_admin_levels": list(range(0, min(active_depth, 3) + 1)) if active_depth is not None else [],
            "deep_admin_levels": list(range(4, active_depth + 1)) if deep_enabled else [],
            "deep_partition_owner_level": 1 if deep_enabled else None,
            "deep_batch_rule": (
                "Resolve and group by Admin1, then make one deeper call per Admin1 group."
                if deep_enabled else "No deep partition is active for this country release."
            ),
        }
    else:
        query_guidance = {
            "model": "global_admin_baseline",
            "available_admin_levels": list(range(0, active_depth + 1)) if active_depth is not None else [],
            "deep_partition_owner_level": None,
            "deep_batch_rule": "No catalog-admitted deep country layout is active.",
        }
    return {
        "country_code": country_code,
        "label": profile.get("label") or program.get("label") or baseline.get("label") or country_code,
        "release_version": profile.get("release_version"),
        "active_admin_depth": active_depth,
        "available_family_ids": available_family_ids,
        "complete_family_ids": list(program.get("complete_family_ids") or []),
        "admin_hierarchy_coverage_status": program.get("admin_hierarchy_coverage_status"),
        "admin_hierarchy_coverage_complete": bool(program.get("admin_hierarchy_coverage_complete")),
        "admin_hierarchy_node_count": _as_int(program.get("admin_hierarchy_node_count")),
        "families": available_families,
        "query_layout_available": has_country_layout,
        "reference_graph_available": bool(profile.get("reference_graph_manifest")),
        "baseline_admin_depth": _as_int(baseline.get("max_admin_level")),
        "baseline_geometry_status": baseline.get("geometry_status"),
        "baseline_feature_counts_by_level": baseline.get("feature_counts_by_level") or {},
        "query_guidance": query_guidance,
        "reference_family_rule": "available_family_ids are independent catalog families unless explicitly admitted into the administrative spine",
    }


def depth_legend(catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Legend rows for the depth ramp, emitted with every payload."""
    labels = {
        0: "No subnational tiers",
        1: "One subnational tier",
        2: "Two subnational tiers",
        3: "Three subnational tiers",
        4: "Four subnational tiers",
        5: "Five subnational tiers",
        6: "Six or more subnational tiers",
    }
    return [
        {
            "level": level,
            "label": f"Admin {level}",
            "description": labels[level],
            "color": DEPTH_COLORS[level],
        }
        for level in sorted(DEPTH_COLORS)
    ]


def _geodesic_area_km2(shape_mapping: Any) -> float | None:
    """Area on the WGS84 ellipsoid, so a polar territory is not overstated.

    Planar degree-area would make Svalbard look enormous and Singapore tiny,
    which is exactly backwards for deciding what needs a marker.
    """
    try:
        from pyproj import Geod
        from shapely.geometry import shape as to_shape
    except ImportError:
        return None
    try:
        geometry = to_shape(shape_mapping)
        area, _perimeter = Geod(ellps="WGS84").geometry_area_perimeter(geometry)
        return abs(area) / 1_000_000.0
    except Exception:
        return None


def _feature_properties(
    loc_id: str,
    name: str,
    entry: dict[str, Any] | None,
    global_entry: dict[str, Any],
) -> dict[str, Any]:
    resolved = entry or {
        "max_admin_level": global_entry.get("max_admin_level"),
        "depth_source": "global_baseline",
        "program": None,
        "admin_family": None,
    }
    level = resolved.get("max_admin_level")
    if level is None:
        level = global_entry.get("max_admin_level")

    program = resolved.get("program")
    admin_family = resolved.get("admin_family") or global_entry.get("admin_family") or {}

    properties: dict[str, Any] = {
        "loc_id": loc_id,
        "name": name,
        "catalog_view": "internal",
        "max_admin_level": level,
        "candidate_admin_depth": resolved.get("candidate_admin_depth"),
        "candidate_admin_status": resolved.get("candidate_admin_status"),
        "depth_color": depth_color(_as_int(level)),
        "depth_source": resolved.get("depth_source") or "global_baseline",
        "has_country_program": bool(program),
        "inherits_global": not bool(program),
        "admin_state": admin_family.get("state"),
        "admin_state_label": admin_family.get("state_label"),
        "admin_authority": admin_family.get("national_authority"),
        "admin_baseline": admin_family.get("national_baseline"),
    }

    if program:
        properties.update({
            "program_label": program.get("label"),
            "program_scope": program.get("program_scope"),
            "strongest_claim": program.get("strongest_claim"),
            "inventory_as_of": program.get("inventory_as_of"),
            "coverage_matrix_status": program.get("coverage_matrix_status"),
            "available_family_count": len(program.get("available_family_ids") or []),
            "family_count": len(program.get("families") or []),
            "families": program.get("families") or [],
        })
    else:
        properties.update({
            "available_family_count": 0,
            "family_count": 0,
            "families": [],
        })
    return properties


def _public_family_card(family: dict[str, Any]) -> dict[str, Any] | None:
    """Return only capability facts that are useful to a catalog visitor."""
    if not family.get("available"):
        return None
    return {
        key: family.get(key)
        for key in (
            "family_id", "label", "short_label", "description",
            "coverage_status", "coverage_complete", "coverage_basis",
            "coverage_denominator", "hierarchy_coverage_status",
            "hierarchy_coverage_complete", "hierarchy_node_count",
        )
        if family.get(key) not in (None, "")
    } | {"available": True}


def public_geometry_inventory_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Project the operator atlas into a public, capability-only catalog.

    The public map says what works now. Candidate depth, lifecycle state,
    release identifiers, licence review, gaps, and inventory workflow remain
    confined to the operator payload.
    """
    features: list[dict[str, Any]] = []
    for feature in payload.get("features") or []:
        if not isinstance(feature, dict):
            continue
        source = feature.get("properties") or {}
        families = [
            card
            for family in (source.get("families") or [])
            if isinstance(family, dict)
            for card in [_public_family_card(family)]
            if card is not None
        ]
        properties = {
            key: source.get(key)
            for key in (
                "loc_id", "name", "max_admin_level", "depth_color",
                "area_km2", "is_small", "centroid_lon", "centroid_lat",
            )
            if source.get(key) is not None
        }
        properties.update({
            "catalog_view": "public",
            "coverage_basis": (
                "enhanced_country_coverage"
                if source.get("depth_source") == "country_program"
                else "global_baseline"
            ),
            "available_family_count": len(families),
            "families": families,
        })
        features.append({
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": properties,
        })

    return {
        "type": "FeatureCollection",
        "view": "public",
        "features": features,
        "count": len(features),
        "legend": payload.get("legend") or [],
        "small_country_area_km2": payload.get("small_country_area_km2"),
        "small_country_count": payload.get("small_country_count", 0),
        "unknown_color": payload.get("unknown_color"),
        "catalog": {
            key: (payload.get("catalog") or {}).get(key)
            for key in ("schema_version", "generated_at")
            if (payload.get("catalog") or {}).get(key) is not None
        },
    }


@lru_cache(maxsize=2)
def _build_public_geometry_inventory_payload_cached(_epoch: int) -> dict[str, Any]:
    """Build the public visual catalog from the current operator atlas."""
    return public_geometry_inventory_payload(build_geometry_inventory_payload())


def build_public_geometry_inventory_payload() -> dict[str, Any]:
    from ..catalog_cache_policy import control_catalog_cache_epoch

    return _build_public_geometry_inventory_payload_cached(control_catalog_cache_epoch())


@lru_cache(maxsize=2)
def _build_geometry_inventory_payload_cached(_epoch: int) -> dict[str, Any]:
    """Join catalog inventory facts onto the bounded Admin0 display shapes."""
    from ..foundation_helpers import load_global_country_display_frame

    catalog = load_geometry_catalog()
    depth_index, global_entry = build_depth_index(catalog)

    frame = load_global_country_display_frame()
    features: list[dict[str, Any]] = []
    if frame is not None:
        columns = set(frame.columns)
        for row in frame.itertuples(index=False):
            geometry = getattr(row, "geometry", None)
            if not geometry:
                continue
            loc_id = _scope_code(getattr(row, "loc_id", ""))
            if not loc_id:
                continue
            name = str(getattr(row, "name", "") or loc_id)
            try:
                shape = json.loads(geometry) if isinstance(geometry, str) else geometry
            except (TypeError, ValueError):
                continue
            properties = _feature_properties(loc_id, name, depth_index.get(loc_id), global_entry)
            area_km2 = _geodesic_area_km2(shape)
            if area_km2 is not None:
                properties["area_km2"] = round(area_km2, 2)
                properties["is_small"] = area_km2 <= SMALL_COUNTRY_AREA_KM2
            if "centroid_lon" in columns and "centroid_lat" in columns:
                properties["centroid_lon"] = getattr(row, "centroid_lon", None)
                properties["centroid_lat"] = getattr(row, "centroid_lat", None)
            features.append({
                "type": "Feature",
                "geometry": shape,
                "properties": properties,
            })

    features.sort(key=lambda feature: feature["properties"]["loc_id"])

    # Programs the catalog knows about that have no Admin0 shape to paint. The
    # global program is not a country, so it is reported separately below.
    rendered = {feature["properties"]["loc_id"] for feature in features}
    unrendered = sorted(code for code in depth_index if code not in rendered)

    return {
        "type": "FeatureCollection",
        "view": "internal",
        "features": features,
        "count": len(features),
        "shape_source": "geometry/global/display/admin_0.parquet",
        "data_source": "geometry/geometry_catalog.json",
        "catalog": {
            "schema_version": catalog.get("schema_version") or catalog.get("_schema_version"),
            "generated_at": catalog.get("generated_at"),
            "catalog_fingerprint": catalog.get("catalog_fingerprint"),
        },
        "legend": depth_legend(catalog),
        "small_country_area_km2": SMALL_COUNTRY_AREA_KM2,
        "small_country_count": sum(
            1 for feature in features if feature["properties"].get("is_small")
        ),
        "unknown_color": DEPTH_COLOR_UNKNOWN,
        "global_program": global_entry.get("program"),
        "country_program_count": sum(
            1 for entry in depth_index.values() if entry.get("depth_source") == "country_program"
        ),
        "unrendered_program_codes": unrendered,
    }


def build_geometry_inventory_payload() -> dict[str, Any]:
    from ..catalog_cache_policy import control_catalog_cache_epoch

    return _build_geometry_inventory_payload_cached(control_catalog_cache_epoch())


def clear_geometry_inventory_cache() -> None:
    """Drop the built payload so a rebuilt catalog is picked up in place."""
    _build_geometry_inventory_payload_cached.cache_clear()
    _build_public_geometry_inventory_payload_cached.cache_clear()
