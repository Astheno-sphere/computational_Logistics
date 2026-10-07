"""One shared, human-name-to-canonical-location resolver.

Chat preprocessors, machine/API clients, and MCP tools must not each invent
their own place aliases.  This module is the small common entry point: it
normalizes text, loc_ids, regional groups, and coordinates into canonical
``loc_id`` values while preserving how the result was obtained.
"""

from __future__ import annotations

import re
from typing import Any

from .api_contract_normalization import normalize_machine_region_ids
from .geometry_catalog import expand_geometry_loc_id, is_deprecated_geometry_loc_id, resolve_geometry_name
from .geography_reference import classify_loc_id_family
from .loc_id_resolution import resolve_admin_text_to_loc_id, resolve_point_to_loc_id_stack


_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def _as_location_rows(loc_ids: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "loc_id": loc_id,
            "family": classify_loc_id_family(loc_id),
        }
        for loc_id in loc_ids
    ]


def _text_candidates(query: str) -> list[str]:
    text = str(query or "").strip()
    if not text:
        return []
    slug = _SLUG_RE.sub("_", text).strip("_")
    candidates = [text]
    if slug and slug != text:
        candidates.append(slug)
    return candidates


def resolve_geography(
    *,
    query: str | None = None,
    country_hint: str | None = None,
    longitude: float | None = None,
    latitude: float | None = None,
) -> dict[str, Any]:
    """Resolve human text or a point into canonical ``loc_id`` values.

    A success can intentionally contain many loc_ids for a documented land
    regional group or a named-geometry hierarchy. Named water bodies never
    expand to bordering countries; a broad sea such as ``Mediterranean Sea``
    resolves to its reviewed marine loc_id plus catalogued child waters.
    """
    if longitude is not None or latitude is not None:
        if longitude is None or latitude is None:
            return {
                "outcome": "error",
                "error": {"code": "invalid_coordinates", "message": "longitude and latitude must be supplied together."},
            }
        point_result = resolve_point_to_loc_id_stack(float(longitude), float(latitude))
        deepest = str(point_result.get("deepest_resolved_loc_id") or "").strip()
        if not deepest:
            return {
                "outcome": "error",
                "error": {"code": "location_not_found", "message": "No canonical geography matched those coordinates."},
            }
        stack = point_result.get("stack") or []
        loc_ids = [str(item.get("loc_id") or "").strip() for item in stack if isinstance(item, dict)]
        loc_ids = [loc_id for loc_id in loc_ids if loc_id]
        return {
            "outcome": "ok",
            "resolution_kind": "point_geometry_stack",
            "query": {"longitude": float(longitude), "latitude": float(latitude)},
            "loc_ids": loc_ids or [deepest],
            "locations": _as_location_rows(loc_ids or [deepest]),
            "deepest_loc_id": deepest,
            "provenance": "geometry_stack",
        }

    text = str(query or "").strip()
    if not text:
        return {
            "outcome": "error",
            "error": {"code": "invalid_location", "message": "query or longitude/latitude is required."},
        }

    if is_deprecated_geometry_loc_id(text):
        return {
            "outcome": "error",
            "query": text,
            "country_hint": country_hint,
            "error": {
                "code": "deprecated_geometry_id",
                "message": (
                    f"'{text}' is a legacy unknown-ocean sentinel, not a geometry-backed "
                    "location. Resolve a named ocean or sea instead."
                ),
            },
        }

    admin_result = resolve_admin_text_to_loc_id(text, country_hint=country_hint)
    direct_loc_id = str(admin_result.get("deepest_resolved_loc_id") or "").strip()
    if direct_loc_id:
        return {
            "outcome": "ok",
            "resolution_kind": str(admin_result.get("match_type") or "admin_name"),
            "query": text,
            "country_hint": country_hint,
            "loc_ids": [direct_loc_id],
            "locations": _as_location_rows([direct_loc_id]),
            "deepest_loc_id": direct_loc_id,
            "provenance": admin_result,
        }

    # Named shared geometries win over land-region aliases, but not over a
    # direct admin-spine match. "Japan" is the country; "Sea of Japan" or
    # "Japan Sea" is the named-water geometry. "Mediterranean" still resolves
    # to its IHO geometry rather than a coastal-country group.
    geometry_entry = resolve_geometry_name(text)
    if geometry_entry:
        loc_ids = [str(value).strip().upper() for value in geometry_entry.get("loc_ids") or [] if str(value).strip()]
        expanded_from_loc_id: str | None = None
        if not loc_ids:
            loc_id = str(geometry_entry.get("loc_id") or "").strip()
            loc_ids = [loc_id] if loc_id else []
            expanded = expand_geometry_loc_id(loc_id)
            if expanded:
                loc_ids = expanded
                if len(expanded) > 1:
                    expanded_from_loc_id = expanded[0]
        if not loc_ids:
            return {
                "outcome": "error",
                "query": text,
                "country_hint": country_hint,
                "error": {"code": "unresolved_named_geometry", "message": f"'{text}' has no approved geometry assignment."},
            }
        return {
            "outcome": "ok",
            "resolution_kind": "named_geometry_group" if len(loc_ids) > 1 else "named_geometry",
            "query": text,
            "country_hint": country_hint,
            "loc_ids": loc_ids,
            "locations": [{
                "loc_id": loc_id,
                "family": geometry_entry.get("family"),
                "label": geometry_entry.get("label") if loc_id == str(geometry_entry.get("loc_id") or "").strip().upper() else None,
            } for loc_id in loc_ids],
            "deepest_loc_id": loc_ids[0] if len(loc_ids) == 1 else None,
            "provenance": {
                "geometry_path": geometry_entry.get("geometry_path"),
                "provenance": geometry_entry.get("provenance"),
                "expanded_from_loc_id": expanded_from_loc_id,
            },
        }

    errors: list[str] = []
    for candidate in _text_candidates(text):
        loc_ids, error = normalize_machine_region_ids([candidate])
        if loc_ids:
            return {
                "outcome": "ok",
                "resolution_kind": "machine_region_expansion",
                "query": text,
                "normalized_input": candidate,
                "country_hint": country_hint,
                "loc_ids": loc_ids,
                "locations": _as_location_rows(loc_ids),
                "deepest_loc_id": loc_ids[0] if len(loc_ids) == 1 else None,
                "provenance": "shared_region_crosswalk",
            }
        if error:
            errors.append(error)

    return {
        "outcome": "error",
        "query": text,
        "country_hint": country_hint,
        "error": {
            "code": "invalid_region_id",
            "message": errors[-1] if errors else f"Location '{text}' is not recognized.",
        },
    }
