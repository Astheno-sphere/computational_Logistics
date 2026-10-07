"""Internal geographic reference exchange helpers.

This module treats ``loc_id`` as the reserve geographic identifier and every
external or adjacent geography family as a reference system that can be connected
to or from it. Public MCP tools should wrap these functions instead of carrying
their own ZIP, NWS, tribal, or admin-specific conversion logic.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..duckdb_helpers import is_cloud_mode, path_to_uri, quote_ident, run_df, select_rows
from ..geometry_handlers import get_location_info, get_selection_geometries, get_selection_geometry_metadata
from ..paths import DATA_ROOT
from .admin_hierarchy import infer_admin_level_from_loc_id
from .geography_reference import (
    canonicalize_loc_id,
    classify_loc_id_family,
    legacy_geometry_ids_for_local_id,
    translate_geometry_id_to_local_id,
    translate_loc_id_to_geometry_id,
)
from .geometry_catalog import (
    geometry_capability_summary,
    load_country_geometry_catalog,
    load_geometry_catalog,
    published_geometry_catalog_records,
    public_geometry_catalog_records,
    resolve_geometry_name,
)
from .external_reference_adapters import (
    GERS_SYSTEM,
    adapter_available,
    adapter_public_entry,
    admitted_external_adapters,
    edge_dict,
    external_primary_loc_ids,
    external_system_aliases,
    get_external_adapter,
    lookup_external_edges,
    lookup_external_edges_batch,
    lookup_loc_id_edges,
    lookup_loc_id_edges_batch,
)
from .geography_relationships import resolve_historical_country_reference
from .loc_id_resolution import resolve_admin_text_to_loc_id
from .family_admin_crosswalk import (
    admin_level_name,
    resolve_admin_ids_to_family,
    resolve_admin_to_family,
    resolve_family_to_admin,
    resolve_family_ids_to_admin,
)


LOC_ID_SYSTEM = "daedalmap.loc_id"
ADMIN_SYSTEM = "admin_boundary"
FAMILY_DEFAULT_SYSTEMS = {
    "marine_jurisdiction": "marine_eez",
}
US_ZCTA_GEOID_SYSTEM = "usa.census.2020.zcta5.geoid"
PUBLIC_ZIP_ALIASES = frozenset({"zcta", "zip", "zip_code", "zipcode", "postal_code"})

SYSTEM_ALIASES = {
    "loc_id": LOC_ID_SYSTEM,
    "locid": LOC_ID_SYSTEM,
    "daedalmap": LOC_ID_SYSTEM,
    "daedalmap_loc_id": LOC_ID_SYSTEM,
    "admin": ADMIN_SYSTEM,
    "admin_name": ADMIN_SYSTEM,
    "admin_geometry": ADMIN_SYSTEM,
    "administrative_boundary": ADMIN_SYSTEM,
    "administrative_boundaries": ADMIN_SYSTEM,
    "zcta": "overlay_zcta",
    "zip": "overlay_zcta",
    "zip_code": "overlay_zcta",
    "zipcode": "overlay_zcta",
    "postal_code": "overlay_zcta",
    "nws_zone": "overlay_nws_public_zone",
    "nws_public": "overlay_nws_public_zone",
    "nws_public_zone": "overlay_nws_public_zone",
    "nws_fire": "overlay_nws_fire_weather_zone",
    "nws_fire_zone": "overlay_nws_fire_weather_zone",
    "nws_fire_weather": "overlay_nws_fire_weather_zone",
    "fire_weather_zone": "overlay_nws_fire_weather_zone",
    "tribal": "overlay_tribal",
    "tribal_area": "overlay_tribal",
    "tribal_lands": "overlay_tribal",
    "eez": "marine_eez",
    "exclusive_economic_zone": "marine_eez",
    "iho": "water_body",
    "iho_water_body": "water_body",
    "nuts": "regional_base",
    "eurostat_nuts": "regional_base",
    "historical": "historical_country",
    "historical_country_name": "historical_country",
    "iso3166_3": "historical_country",
    "iso_3166_3": "historical_country",
    "geoid": "us_census_geoid",
    "census_geoid": "us_census_geoid",
    "census_2020_geoid": "us_census_geoid",
    "us_census_2020_geoid": "us_census_geoid",
    "fips": "us_census_geoid",
    "us_fips": "us_census_geoid",
    "census_fips": "us_census_geoid",
    **external_system_aliases(),
}


def _normalize_system(system: str | None) -> str:
    value = str(system or "").strip().lower().replace("-", "_").replace(" ", "_")
    return SYSTEM_ALIASES.get(value, value)


def _unique_catalog_country_for_reference_system(system: str) -> str | None:
    """Infer scope only when the published catalog declares one country.

    This keeps generic batch conversion fast for country-owned systems such as
    ZCTA without encoding their country in the tool. A system published by
    multiple countries remains ambiguous until the caller supplies a scope.
    """
    normalized = _normalize_system(system)
    countries = {
        str(entry.get("country_code") or "").strip().upper()
        for entry in (load_geometry_catalog().get("reference_systems") or [])
        if isinstance(entry, dict)
        and _normalize_system(entry.get("system")) == normalized
        and bool(entry.get("callable"))
        and str(entry.get("publication_status") or "").strip().lower()
        in {"published", "approved_for_publication"}
        and len(str(entry.get("country_code") or "").strip()) == 3
    }
    return next(iter(countries)) if len(countries) == 1 else None


def verify_loc_ids(values: Any) -> set[str]:
    """Return the canonical subset of ``values`` that name a maintained identity.

    Two independent sources of evidence, because neither is complete on its own.
    The reference graph knows shapeless families such as ``can_economic_region``
    that carry no polygon, while the geometry banks cover countries the active
    country-scoped graph does not reach. A value confirmed by either is real; a
    value confirmed by neither is not a loc_id we hold.

    This exists because string shape is not identity. A dash-separated token
    looks exactly like a loc_id whether or not it is one, so echoing it back
    fabricates an identifier the caller cannot tell from a real one until it
    fails downstream. The marine EEZ branch already refuses on that principle;
    this helper lets every other passthrough refuse the same way.
    """
    candidates: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        canonical = canonicalize_loc_id(str(value or "").strip())
        if canonical and canonical not in seen:
            seen.add(canonical)
            candidates.append(canonical)
    if not candidates:
        return set()

    verified: set[str] = set()
    try:
        payload = get_geometry_references(candidates, include_polygon=False, include_info=False)
    except Exception:
        payload = {}
    for row in payload.get("results") or []:
        if not isinstance(row, dict) or not row.get("has_shape"):
            continue
        row_loc_id = canonicalize_loc_id(str(row.get("loc_id") or ""))
        if row_loc_id:
            verified.add(row_loc_id)

    remaining = [value for value in candidates if value not in verified]
    if not remaining:
        return verified
    try:
        from .reference_graph import identity as graph_identity
    except Exception:
        return verified
    for value in remaining:
        try:
            if graph_identity(value):
                verified.add(value)
        except Exception:
            continue
    return verified


def resolve_external_reference(
    system: str,
    value: str,
    *,
    country_scope: str | None = None,
    source_release: str | None = None,
    internal_release: str | None = None,
    limit: int | None = 10,
) -> dict[str, Any]:
    """Resolve an admitted external id through typed relationship edges.

    Only an explicit ``equivalent_identity`` edge may recommend a loc_id.
    ``contained_by`` and ``overlaps`` edges remain visible without becoming an
    identity claim. No target-admin argument exists on this boundary.
    """
    adapter = get_external_adapter(system)
    text = str(value or "").strip()
    normalized_system = adapter.system if adapter else _normalize_system(system)
    if adapter is None:
        return {"ok": False, "from_system": normalized_system, "input": value,
                "error": {"code": "external_system_not_admitted", "message": "external reference system is not admitted"}}
    if not text:
        return {"ok": False, "from_system": normalized_system, "input": value,
                "error": {"code": "external_id_required", "message": "value is required"}}
    if not adapter_available(adapter):
        return {"ok": False, "from_system": adapter.system, "input": value,
                "error": {"code": "external_system_unavailable", "message": "external reference system has no admitted, verified crosswalk"}}
    edges = lookup_external_edges(
        adapter.system,
        text,
        source_release=source_release,
        internal_release=internal_release,
        country_scope=country_scope,
    )
    return _external_reference_payload(adapter, value, text, edges, limit=limit)


def _external_reference_payload(
    adapter,
    original_value: Any,
    text: str,
    edges: list[Any],
    *,
    limit: int | None,
) -> dict[str, Any]:
    """Shape one external-reference result after a shared edge query."""
    if not edges:
        return {"ok": False, "from_system": adapter.system, "input": original_value,
                "error": {"code": "external_reference_not_found", "message": "no admitted typed edge matches that external identifier"}}
    equivalences = [edge for edge in edges if edge.is_equivalence]
    relationships = [edge for edge in edges if not edge.is_equivalence]
    relationships.sort(key=lambda edge: (-(edge.geometry_confidence or 0.0), edge.loc_id))
    if limit is not None:
        relationships = relationships[: max(0, int(limit) - (1 if equivalences else 0))]
    relationship_rows = [edge_dict(edge) for edge in relationships]
    if not equivalences:
        return _clean_json({
            "ok": False,
            "status": "relationship_only",
            "from_system": adapter.system,
            "input": original_value,
            "resolved_loc_id": None,
            "error": {
                "code": "external_reference_has_no_equivalence",
                "message": "maintained containment or overlap edges exist, but none asserts identity equivalence",
            },
            "relationships": relationship_rows,
            "relationship_count": len(relationships),
            "source_releases": sorted({edge.source_release for edge in edges if edge.source_release}),
            "internal_releases": sorted({edge.internal_release for edge in edges if edge.internal_release}),
        })
    equivalent_loc_ids = sorted({edge.loc_id for edge in equivalences})
    if len(equivalent_loc_ids) != 1:
        return _clean_json({
            "ok": False,
            "status": "conflicting_equivalence",
            "from_system": adapter.system,
            "input": original_value,
            "resolved_loc_id": None,
            "error": {
                "code": "external_reference_conflicting_equivalence",
                "message": "the admitted crosswalk asserts equivalence to more than one loc_id",
            },
            "relationships": [edge_dict(edge) for edge in equivalences] + relationship_rows,
            "relationship_count": len(edges),
        })
    equivalences.sort(key=lambda edge: (edge.partition_id or "", edge.edge_id or ""))
    primary = equivalences[0]
    return _clean_json({
        "ok": True,
        "from_system": adapter.system,
        "input": original_value,
        "resolved_loc_id": primary.loc_id,
        "resolved_family": _reference_family(primary.loc_id),
        "match_type": "exact_identifier_equivalence",
        "relationship_type": primary.relationship_type,
        "identity_confidence": primary.identity_confidence,
        "geometry_confidence": primary.geometry_confidence,
        "source_level": primary.source_level,
        "external_subtype": primary.external_subtype,
        "edge_id": primary.edge_id,
        "partition_id": primary.partition_id,
        "bridge_generation_id": primary.bridge_generation_id,
        "edge_content_hash": primary.edge_content_hash,
        "country": primary.country,
        "source_release": primary.source_release,
        "internal_release": primary.internal_release,
        "relationships": relationship_rows,
        "relationship_count": len(relationships),
    })


def resolve_gers_division(value: str, *, limit: int | None = 10) -> dict[str, Any]:
    """Compatibility wrapper for the generic admitted external adapter."""
    payload = resolve_external_reference(GERS_SYSTEM, value, limit=limit)
    # Preserve the pre-registry response vocabulary while callers migrate to
    # source_release/internal_release/external_subtype/source_level.
    payload.setdefault("overture_release", payload.get("source_release"))
    payload.setdefault("spine_vintage", payload.get("internal_release"))
    payload.setdefault("overture_subtype", payload.get("external_subtype"))
    payload.setdefault("admin_level", payload.get("source_level"))
    payload.setdefault("iso3", payload.get("country"))
    payload.setdefault("overlaps", payload.get("relationships") or [])
    payload.setdefault("overlap_count", payload.get("relationship_count") or 0)
    if payload.get("match_type") == "exact_identifier_equivalence":
        payload["match_type"] = "exact_identifier_crosswalk"
    if payload.get("relationship_type") == "equivalent_identity":
        payload["relationship_type"] = "equivalence"
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    compatibility_codes = {
        "external_id_required": "gers_id_required",
        "external_reference_not_found": "gers_division_not_found",
        "external_reference_has_no_equivalence": "gers_division_has_no_primary_match",
    }
    if error.get("code") in compatibility_codes:
        payload["error"] = {**error, "code": compatibility_codes[error["code"]]}
    return payload


def gers_primary_loc_ids(values: Any) -> dict[str, list[str]]:
    """Compatibility wrapper; only equivalence edges participate."""
    return external_primary_loc_ids(GERS_SYSTEM, list(values or []))


def _reference_family(loc_id: str, *, admin_level: Any = None) -> str | None:
    if admin_level is not None:
        return classify_loc_id_family(loc_id)
    try:
        from .reference_graph import identity as graph_identity

        row = graph_identity(loc_id) or {}
        family = row.get("geography_family") or row.get("family")
        if family:
            return family
    except Exception:
        pass
    return classify_loc_id_family(loc_id)


def _canonical_graph_loc_id(loc_id: str) -> str:
    """Resolve a preferred public loc_id without guessing between targets."""
    canonical = canonicalize_loc_id(loc_id)
    try:
        from .reference_graph import resolve_public_loc_id

        resolved = resolve_public_loc_id(canonical)
        if resolved.get("ok") and resolved.get("loc_id"):
            return str(resolved["loc_id"])
    except Exception:
        pass
    return canonical


def resolve_loc_id_input(loc_id: str) -> dict[str, Any]:
    """Return canonical input metadata for any runtime accepting a loc_id."""
    canonical = canonicalize_loc_id(loc_id)
    fallback = {
        "ok": True,
        "status": "unchanged",
        "requested_loc_id": canonical,
        "loc_id": canonical,
        "resolved_from_public_alias": False,
    }
    try:
        from .reference_graph import resolve_public_loc_id

        return resolve_public_loc_id(canonical)
    except Exception:
        # A graph outage must not disable canonical geometry-bank lookup.
        return fallback


def resolve_loc_id_inputs(loc_ids: list[str]) -> list[dict[str, Any]]:
    """Batch form of :func:`resolve_loc_id_input` for geometry tool paths."""
    canonical = [canonicalize_loc_id(loc_id) for loc_id in loc_ids]
    try:
        from .reference_graph import resolve_public_loc_ids

        return resolve_public_loc_ids(canonical)
    except Exception:
        return [{
            "ok": True, "status": "unchanged", "requested_loc_id": value,
            "loc_id": value, "resolved_from_public_alias": False,
        } for value in canonical]


def _public_alias_error(resolution: dict[str, Any], *, shape: bool = False) -> dict[str, Any]:
    result = {
        "ok": False,
        "loc_id": resolution.get("requested_loc_id"),
        "requested_loc_id": resolution.get("requested_loc_id"),
        "canonical_loc_id": None,
        "error": resolution.get("error") or {
            "code": "public_loc_id_resolution_failed",
            "message": "preferred public loc_id could not be resolved safely",
        },
    }
    if resolution.get("candidate_loc_ids"):
        result["candidate_loc_ids"] = resolution.get("candidate_loc_ids")
    if resolution.get("reference_systems"):
        result["reference_systems"] = resolution.get("reference_systems")
    if shape:
        result["has_shape"] = False
    return result


def _attach_public_alias_resolution(result: dict[str, Any], resolution: dict[str, Any]) -> dict[str, Any]:
    if not resolution.get("resolved_from_public_alias"):
        return result
    return {
        **result,
        "requested_loc_id": resolution.get("requested_loc_id"),
        "resolved_from_public_alias": True,
        "public_alias": resolution.get("public_alias"),
        "public_alias_reference_system": resolution.get("reference_system"),
    }


def _clean_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if hasattr(value, "item"):
        try:
            return _clean_json(value.item())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_json(item) for item in value]
    return str(value)


def geometry_supersession_notice(
    loc_id: str,
    record: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Describe an evidenced successor without substituting or fetching it."""
    item = record if isinstance(record, dict) else {}
    requested = canonicalize_loc_id(loc_id)
    raw_targets: list[Any] = []
    for key in ("superseded_by", "successor_loc_id", "successor_loc_ids"):
        value = item.get(key)
        if isinstance(value, (list, tuple, set)):
            raw_targets.extend(value)
        elif value not in (None, ""):
            raw_targets.append(value)

    lifecycle = str(item.get("lifecycle_status") or item.get("status") or "").strip().lower()
    valid_to = item.get("valid_to") or item.get("valid_to_date")
    relationship_evidence: list[str] = []
    if not raw_targets and (valid_to not in (None, "") or lifecycle in {
        "historical", "retired", "superseded",
    }):
        try:
            from .reference_graph import relationships_for_loc_id

            for edge in relationships_for_loc_id(requested, direction="both", limit=100):
                relationship_type = str(
                    edge.get("relationship_type") or edge.get("semantic_type") or ""
                ).strip().lower().replace("-", "_").replace(" ", "_")
                source = canonicalize_loc_id(str(edge.get("source_loc_id") or ""))
                target = canonicalize_loc_id(str(edge.get("target_loc_id") or ""))
                successor = None
                if source == requested and relationship_type in {
                    "superseded_by", "replaced_by", "successor", "became",
                }:
                    successor = target
                elif target == requested and relationship_type in {
                    "supersedes", "replaces", "successor_of",
                }:
                    successor = source
                if successor:
                    raw_targets.append(successor)
                    evidence_id = str(edge.get("relationship_id") or "").strip()
                    if evidence_id:
                        relationship_evidence.append(evidence_id)
        except Exception:
            # Historical data remains usable even if optional relationship
            # discovery is unavailable. Never turn a successor hint into a
            # requirement for serving the requested record.
            pass

    targets = sorted({
        canonicalize_loc_id(str(value))
        for value in raw_targets
        if str(value or "").strip() and canonicalize_loc_id(str(value)) != requested
    })
    if not targets:
        return None
    successor_text = targets[0] if len(targets) == 1 else ", ".join(targets)
    notice: dict[str, Any] = {
        "status": "superseded",
        "requested_loc_id": requested,
        "successor_loc_ids": targets,
        "successor_included": False,
        "requires_explicit_selection": True,
        "prompt": f"This has been superseded by {successor_text}. Would you like that instead?",
    }
    if len(targets) == 1:
        notice["successor_loc_id"] = targets[0]
    if relationship_evidence:
        notice["relationship_evidence"] = sorted(set(relationship_evidence))
    return notice


def _attach_geometry_supersession(
    result: dict[str, Any],
    requested_loc_id: str,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    notice = geometry_supersession_notice(requested_loc_id, record or result)
    if notice:
        return {**result, "supersession": notice}
    return result


def _first_populated(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"nan", "nat", "<na>"}:
            return value
    return None


def _catalog_crosswalk_path(artifact: dict[str, Any]) -> Path | None:
    rel = str(artifact.get("artifact_path") or "").strip()
    if not rel:
        return None
    from .geometry_storage_layout import country_crosswalk_artifact_path

    return country_crosswalk_artifact_path(
        Path(DATA_ROOT), rel, cloud_mode=is_cloud_mode(),
    )


def _crosswalk_source_names(artifact: dict[str, Any]) -> set[str]:
    """Return every normalized family name that may select a crosswalk."""
    values = [artifact.get("source_family"), *(artifact.get("source_family_aliases") or [])]
    return {
        _normalize_system(str(value))
        for value in values
        if str(value or "").strip()
    }


def _crosswalk_artifacts(
    *,
    source_family: str | None = None,
    target_admin_level: int | str | None = None,
    iso3: str | None = None,
    relationship_vintage: str | None = None,
) -> list[dict[str, Any]]:
    source = _normalize_system(source_family) if source_family else None
    level = admin_level_name(target_admin_level) if target_admin_level not in (None, "") else None
    country = str(iso3 or "").strip().upper()
    vintage = str(relationship_vintage or "").strip()
    out: list[dict[str, Any]] = []
    for artifact in load_geometry_catalog().get("crosswalk_artifacts") or []:
        if not isinstance(artifact, dict) or str(artifact.get("status") or "") != "complete":
            continue
        if source and source not in _crosswalk_source_names(artifact):
            continue
        if level and str(artifact.get("target_admin_level") or "").strip().lower() != level:
            continue
        path = _catalog_crosswalk_path(artifact)
        if country and path and f"_{country.lower()}.parquet" not in path.name.lower():
            continue
        if vintage and str(artifact.get("relationship_vintage") or "") != vintage:
            continue
        if path and (path.exists() or is_cloud_mode()):
            out.append(artifact)
    out.sort(
        key=lambda item: (
            str(item.get("relationship_vintage") or "") != "usa_geometry_current",
            -int(item.get("row_count") or 0),
            str(item.get("artifact_path") or ""),
        )
    )
    return out


def _first_crosswalk_artifact(**filters: Any) -> dict[str, Any] | None:
    artifacts = _crosswalk_artifacts(**filters)
    return artifacts[0] if artifacts else None


def _normalize_source_loc_id(source_family: str, value: str, iso3: str) -> str:
    text = str(value or "").strip()
    family = _normalize_system(source_family)
    country = str(iso3 or "USA").strip().upper() or "USA"
    if family == "overlay_zcta" and text.isdigit() and len(text) == 5:
        return f"{country}-Z-{text}"
    if family == "overlay_nws_public_zone" and len(text) == 6 and text[:2].isalpha() and text[2].upper() == "Z":
        return f"{country}-NWSZ-{text.upper()}"
    if family == "overlay_nws_fire_weather_zone" and len(text) == 6 and text[:2].isalpha() and text[2].upper() == "Z":
        return f"{country}-NWSFZ-{text.upper()}"
    if family in {"usa.census.2025.aiannhce", "usa.census.aiannhce"} and text.isdigit() and len(text) <= 4:
        return text.zfill(4)
    return text


"""Resolvers that reach loc_id on their own, without a crosswalk artifact.

A family carrying one of these answers name and point lookups directly, so it
stays exchangeable even though it owns no crosswalk row. Every other geometry or
reference-graph family needs a built crosswalk before a conversion can succeed.
"""
SELF_RESOLVING_RESOLVERS = frozenset({
    "named geometry catalog",
    "admin geometry name and point resolver",
})

_ALWAYS_EXCHANGEABLE_ROLES = frozenset({
    "reserve", "exact_identifier_system", "external_reference_bridge", "canonical_reference_system",
    "preferred_public_loc_id",
})


def _mark_exchangeability(system: dict[str, Any], crosswalk_systems: set[str]) -> None:
    """Record whether a listed system can actually be converted through loc_id.

    Listing a family the conversion tools will refuse sends agents into
    guaranteed failures, so state the resolution path instead of implying one
    exists for everything in the catalog.
    """
    role = str(system.get("role") or "")
    resolver = str(system.get("resolver") or "").strip().lower()
    name = str(system.get("system") or "")
    if name in crosswalk_systems:
        system["exchangeable"] = True
        system["exchange_via"] = "crosswalk_artifact"
        return
    if resolver in SELF_RESOLVING_RESOLVERS:
        system["exchangeable"] = True
        system["exchange_via"] = "self_resolving_geometry"
        return
    if role in _ALWAYS_EXCHANGEABLE_ROLES:
        system["exchangeable"] = True
        system["exchange_via"] = (
            "reserve" if role == "reserve" else
            "preferred_public_loc_id" if role == "preferred_public_loc_id" else
            "canonical_crosswalk" if role == "canonical_reference_system" else
            "typed_external_reference_edges" if role == "external_reference_bridge" else
            "exact_identifier_crosswalk"
        )
        return
    system["exchangeable"] = False
    system["exchange_via"] = None
    system["exchange_status"] = "no_crosswalk_artifact"


def _resolve_eez_by_country(text: str) -> dict[str, Any] | None:
    """Resolve a country name or ISO3 code to its maintained EEZ.

    EEZ ids carry the owning ISO3, so the country crosswalk already answers
    this; only the name-to-code step was missing. Returns the sovereign zone
    and lists any dependency zones separately rather than guessing between
    them - Australia owns five, and picking one silently would be wrong.
    """
    from .geography_reference import load_country_name_to_iso3_map

    candidate = str(text or "").strip()
    if not candidate:
        return None
    iso3 = candidate.upper() if len(candidate) == 3 and candidate.isalpha() else ""
    if not iso3:
        iso3 = str(load_country_name_to_iso3_map().get(candidate.casefold(), "")).upper()
    if not iso3:
        return None

    catalog = load_geometry_catalog()
    objects = {
        str(entry.get("loc_id")): entry
        for entry in catalog.get("named_reference_objects") or []
        if isinstance(entry, dict) and str(entry.get("family")) == "marine_eez"
    }
    primary = objects.get(f"EEZ-{iso3}")
    if not primary:
        return None
    return {
        "loc_id": primary.get("loc_id"),
        "label": primary.get("label"),
        "family": "marine_eez",
        "country_iso3": iso3,
        "resolved_from": "country_iso3_crosswalk",
    }


def _catalog_crosswalks(
    *, country_scope: str | None = None, read_wip: bool = False,
) -> list[dict[str, Any]]:
    """Return canonical crosswalk records; source manifests never reach callers."""
    country = str(country_scope or "").strip().upper()
    global_catalog = load_geometry_catalog()
    has_profile = any(
        isinstance(item, dict)
        and str(item.get("country_code") or "").upper() == country
        for item in global_catalog.get("country_profiles") or []
    )
    source_catalog = (
        load_country_geometry_catalog(country) if country and has_profile else global_catalog
    )
    if country and not source_catalog.get("crosswalks"):
        source_catalog = global_catalog
    records = []
    for item in source_catalog.get("crosswalks") or []:
        if not isinstance(item, dict):
            continue
        if not read_wip and (
            item.get("publication_status") != "published" or item.get("callable") is not True
        ):
            continue
        if country and str(item.get("country_code") or "").upper() != country:
            continue
        record = dict(item)
        path = _direct_crosswalk_path(record)
        record["available_in_active_data_plane"] = bool(
            record.get("callable")
            and (is_cloud_mode() or (path is not None and path.is_file()))
        )
        records.append(record)
    return records


def _direct_crosswalk_path(record: dict[str, Any]) -> Path | None:
    path = str(record.get("artifact_path") or "").strip()
    return DATA_ROOT / path if path else None


def _direct_crosswalk_matches(
    *, from_system: str, value: str, to_system: str | None, iso3: str, limit: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Execute one typed relationship artifact in either direction."""
    source_system = _normalize_system(from_system)
    target_system = _normalize_system(to_system) if to_system else None
    text = str(value or "").strip()
    normalized = _normalize_source_loc_id(source_system, text, iso3)
    catalog_records = _catalog_crosswalks(country_scope=iso3)
    ordered_records = sorted(
        catalog_records,
        key=lambda item: str(item.get("source_system") or "") != source_system,
    )
    for record in ordered_records:
        if record.get("execution_strategy") not in {"direct_relationship_artifact", "measured_relationship_artifact"}:
            continue
        forward = str(record.get("source_system") or "") == source_system
        reverse = str(record.get("target_system") or "") == source_system
        if target_system:
            forward = forward and str(record.get("target_system") or "") == target_system
            reverse = reverse and str(record.get("source_system") or "") == target_system
        if not forward and not reverse:
            continue
        path = _direct_crosswalk_path(record)
        if path is None or (not is_cloud_mode() and not path.is_file()):
            continue
        input_prefix = "source" if forward else "target"
        output_prefix = "target" if forward else "source"
        frame = select_rows(
            path,
            exact_filters={f"{input_prefix}_loc_id": normalized},
            order_by=f"rank_by_{input_prefix}_area",
            limit=max(1, min(int(limit or 10), 100)),
        )
        if frame.empty:
            frame = select_rows(
                path,
                exact_filters={f"{input_prefix}_id": text},
                order_by=f"rank_by_{input_prefix}_area",
                limit=max(1, min(int(limit or 10), 100)),
            )
        if frame.empty:
            continue
        return record, _shape_direct_crosswalk_rows(record, frame.to_dict(orient="records"), forward=forward)
    return None, []


def _shape_direct_crosswalk_rows(
    record: dict[str, Any], raw_rows: list[dict[str, Any]], *, forward: bool,
) -> list[dict[str, Any]]:
    input_prefix = "source" if forward else "target"
    output_prefix = "target" if forward else "source"
    return [{
        "system": record.get(f"{'target' if forward else 'source'}_system"),
        "value": raw.get(f"{output_prefix}_loc_id") or raw.get(f"{output_prefix}_id"),
        "reference_id": raw.get(f"{output_prefix}_id"),
        "name": raw.get(f"{output_prefix}_name"),
        "source_area_share": raw.get("source_area_share"),
        "target_area_share": raw.get("target_area_share"),
        "is_primary": raw.get("is_primary"),
        "relationship_vintage": raw.get("relationship_vintage") or record.get("relationship_vintage"),
        "crosswalk_id": record.get("crosswalk_id"),
        "direction": "forward" if forward else "reverse",
        "input_loc_id": raw.get(f"{input_prefix}_loc_id"),
        "input_reference_id": raw.get(f"{input_prefix}_id"),
        "input_name": raw.get(f"{input_prefix}_name"),
        "input_family_id": record.get(f"{'source' if forward else 'target'}_family_id"),
    } for raw in raw_rows]


def _select_direct_crosswalk_rows(
    path: Path, *, input_column: str, values: list[str], rank_column: str, limit: int,
):
    """Read only the top ranked rows for each requested relationship ID."""
    requested = list(dict.fromkeys(value for value in values if value))
    if not requested:
        return None
    placeholders = ", ".join("?" for _ in requested)
    sql = (
        f"SELECT * FROM read_parquet(?) WHERE {quote_ident(input_column)} IN ({placeholders}) "
        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY {quote_ident(input_column)} "
        f"ORDER BY {quote_ident(rank_column)} ASC NULLS LAST) <= ?"
    )
    return run_df(sql, [path_to_uri(path), *requested, limit])


def _direct_crosswalk_matches_batch(
    *, from_system: str, values: list[str], to_system: str, iso3: str, limit: int,
) -> dict[str, tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Match a homogeneous conversion group with one scan per candidate artifact."""
    source_system = _normalize_system(from_system)
    target_system = _normalize_system(to_system)
    requested = list(dict.fromkeys(str(value or "").strip() for value in values if str(value or "").strip()))
    unresolved = set(requested)
    matches: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    maximum = max(1, min(int(limit or 10), 100))
    catalog_records = sorted(
        _catalog_crosswalks(country_scope=iso3),
        key=lambda item: str(item.get("source_system") or "") != source_system,
    )
    for record in catalog_records:
        if not unresolved or record.get("execution_strategy") not in {"direct_relationship_artifact", "measured_relationship_artifact"}:
            continue
        forward = (
            str(record.get("source_system") or "") == source_system
            and str(record.get("target_system") or "") == target_system
        )
        reverse = (
            str(record.get("target_system") or "") == source_system
            and str(record.get("source_system") or "") == target_system
        )
        if not forward and not reverse:
            continue
        path = _direct_crosswalk_path(record)
        if path is None or (not is_cloud_mode() and not path.is_file()):
            continue
        input_prefix = "source" if forward else "target"
        rank_column = f"rank_by_{input_prefix}_area"
        pending = [value for value in requested if value in unresolved]
        normalized = {value: _normalize_source_loc_id(source_system, value, iso3) for value in pending}
        frame = _select_direct_crosswalk_rows(
            path,
            input_column=f"{input_prefix}_loc_id",
            values=list(normalized.values()),
            rank_column=rank_column,
            limit=maximum,
        )
        raw_rows = [] if frame is None or frame.empty else frame.to_dict(orient="records")
        by_normalized: dict[str, list[dict[str, Any]]] = {}
        for raw in raw_rows:
            by_normalized.setdefault(str(raw.get(f"{input_prefix}_loc_id") or ""), []).append(raw)
        missing = [value for value in pending if not by_normalized.get(normalized[value])]
        by_reference: dict[str, list[dict[str, Any]]] = {}
        if missing:
            frame = _select_direct_crosswalk_rows(
                path,
                input_column=f"{input_prefix}_id",
                values=missing,
                rank_column=rank_column,
                limit=maximum,
            )
            for raw in ([] if frame is None or frame.empty else frame.to_dict(orient="records")):
                by_reference.setdefault(str(raw.get(f"{input_prefix}_id") or ""), []).append(raw)
        for value in pending:
            selected = by_normalized.get(normalized[value]) or by_reference.get(value) or []
            if not selected:
                continue
            selected.sort(key=lambda raw: (raw.get(rank_column) is None, raw.get(rank_column) or 0))
            matches[value] = (
                record,
                _shape_direct_crosswalk_rows(record, selected[:maximum], forward=forward),
            )
            unresolved.discard(value)
    return matches


def list_reference_systems(
    *, country_scope: str | None = None, include_crosswalks: bool = False,
    read_wip: bool = False,
) -> dict[str, Any]:
    """Return the currently discoverable reference systems and crosswalks."""
    country = str(country_scope or "").strip().upper()
    global_catalog = load_geometry_catalog()
    has_profile = any(
        isinstance(item, dict)
        and str(item.get("country_code") or "").upper() == country
        for item in global_catalog.get("country_profiles") or []
    )
    catalog = load_country_geometry_catalog(country) if country and has_profile else global_catalog
    if country and not catalog.get("country_profile") and has_profile:
        catalog = global_catalog
    systems: dict[str, dict[str, Any]] = {
        LOC_ID_SYSTEM: {
            "system": LOC_ID_SYSTEM,
            "label": "DaedalMap loc_id",
            "role": "reserve",
            "bidirectional": True,
        },
    }
    if not country or country == "USA":
        systems["us_census_geoid"] = {
            "system": "us_census_geoid",
            "label": "US Census GEOID",
            "role": "exact_identifier_system",
            "country_scope": "USA",
            "supported_geo_levels": ["admin_1", "admin_2", "admin_3", "admin_4", "admin_5"],
            "supported_vintages": ["2020"],
            "resolver": "exact_identifier_crosswalk",
            "bidirectional": False,
        }
    # The default list is a discovery index, so do not materialize more than a
    # thousand rich crosswalk records (or probe their local artifact paths).
    # Callers opt into that detail after selecting a country/system.
    canonical_crosswalks = (
        _catalog_crosswalks(country_scope=country, read_wip=read_wip)
        if include_crosswalks else []
    )
    if include_crosswalks:
        available_crosswalk_count = len(canonical_crosswalks)
    else:
        available_crosswalk_count = sum(
            1
            for item in catalog.get("crosswalks") or []
            if isinstance(item, dict)
            and (read_wip or (item.get("publication_status") == "published" and item.get("callable") is True))
            and (not country or str(item.get("country_code") or "").upper() == country)
        )
    canonical_systems = [
        item for item in catalog.get("reference_systems") or []
        if isinstance(item, dict)
        and (not country or str(item.get("country_code") or "").upper() == country)
        and (read_wip or item.get("callable") is True)
    ]
    for entry in canonical_systems:
        system = str(entry.get("system") or "").strip()
        if not system:
            continue
        entry_country = str(entry.get("country_code") or "").strip().upper()
        current = systems.get(system)
        if current and current.get("role") != "canonical_reference_system":
            scopes = set(current.get("country_scopes") or [])
            if entry_country:
                scopes.add(entry_country)
            current["country_scopes"] = sorted(scopes)
            continue
        if current:
            scopes = set(current.get("country_scopes") or [])
            if current.get("country_scope"):
                scopes.add(str(current["country_scope"]))
            if entry_country:
                scopes.add(entry_country)
            current.update({
                "country_scope": entry_country if len(scopes) == 1 else None,
                "country_scopes": sorted(scopes),
                "exchangeable": bool(current.get("exchangeable") or entry.get("callable")),
                "exchange_via": "canonical_crosswalk" if current.get("exchangeable") or entry.get("callable") else None,
                "input_crosswalk_count": int(current.get("input_crosswalk_count") or 0) + int(entry.get("input_crosswalk_count") or 0),
                "output_crosswalk_count": int(current.get("output_crosswalk_count") or 0) + int(entry.get("output_crosswalk_count") or 0),
            })
            continue
        systems[system] = {
            "system": system,
            "label": entry.get("label") or system.replace("_", " ").title(),
            "role": "canonical_reference_system",
            "country_scope": entry_country or None,
            "country_scopes": [entry_country] if entry_country else [],
            "family_id": entry.get("family_id"),
            "exchangeable": bool(entry.get("callable")),
            "exchange_via": "canonical_crosswalk" if entry.get("callable") else None,
            "input_crosswalk_count": entry.get("input_crosswalk_count"),
            "output_crosswalk_count": entry.get("output_crosswalk_count"),
        }
    for adapter in admitted_external_adapters():
        if adapter_available(adapter):
            systems[adapter.system] = adapter_public_entry(adapter)
    if include_crosswalks or country:
        try:
            from .reference_graph import public_alias_reference_systems

            for entry in public_alias_reference_systems(iso3=country or None):
                system = str(entry.get("system") or "").strip()
                if not system:
                    continue
                systems[system] = {
                    **entry,
                    "label": "DaedalMap preferred public loc_id",
                    "role": "preferred_public_loc_id",
                    "country_scope": country or (system.split(".")[2].upper() if len(system.split(".")) > 2 else None),
                    "bidirectional": True,
                    "resolver": "preferred_public_loc_id",
                }
        except Exception:
            pass
    for family in catalog.get("geometry_families") or []:
        if not isinstance(family, dict):
            continue
        if country:
            continue
        system = str(family.get("family") or "").strip()
        if not system:
            continue
        # External identifier systems are advertised only through their
        # admitted typed adapter. Legacy geometry-family names must not create
        # a second, target-admin-steerable authority path.
        if get_external_adapter(system):
            continue
        existing = systems.get(system)
        if existing:
            if family.get("resolver"):
                existing["resolver"] = family.get("resolver")
            if family.get("feature_count") is not None:
                existing["feature_count"] = family.get("feature_count")
            continue
        systems[system] = {
            "system": system,
            "label": family.get("label") or system,
            "role": "geometry_family",
            "feature_count": family.get("feature_count"),
            "resolver": family.get("resolver"),
        }
    if include_crosswalks:
        try:
            from .reference_graph import reference_graph_families

            for family in reference_graph_families():
                if country:
                    continue
                system = str(family.get("family") or "").strip()
                if not system:
                    continue
                if get_external_adapter(system):
                    continue
                systems.setdefault(system, {
                    "system": system,
                    "label": system.replace("_", " ").title(),
                    "role": "reference_graph_family",
                    "identity_count": family.get("identity_count"),
                    "shape_count": family.get("shape_count"),
                })
        except Exception:
            pass

    crosswalks = []
    crosswalk_systems: set[str] = set()
    for artifact in catalog.get("crosswalk_artifacts") or []:
        if not isinstance(artifact, dict) or str(artifact.get("status") or "") != "complete":
            continue
        artifact_path = str(artifact.get("artifact_path") or "")
        if country and f"_{country}.parquet" not in artifact_path:
            continue
        source = str(artifact.get("source_family") or "").strip()
        if get_external_adapter(source):
            continue
        level = str(artifact.get("target_admin_level") or "").strip()
        # A family renamed by the area-depth migration answers to both names.
        # Without this the canonical name looks unreachable even though its
        # crosswalk exists and is complete.
        for alias in artifact.get("source_family_aliases") or []:
            alias_name = str(alias).strip()
            if alias_name:
                crosswalk_systems.add(alias_name)
        if source:
            crosswalk_systems.add(source)
            systems.setdefault(source, {
                "system": source,
                "label": source.replace("_", " ").title(),
                "role": "reference_system",
            })
        if include_crosswalks:
            crosswalks.append({
                "source_system": source,
                "target_system": LOC_ID_SYSTEM,
                "target_family": artifact.get("target_family"),
                "target_admin_level": level,
                "relationship_vintage": artifact.get("relationship_vintage"),
                "row_count": artifact.get("row_count"),
                "source_count": artifact.get("source_count"),
                "target_count": artifact.get("target_count"),
                "artifact_path": artifact.get("artifact_path"),
                "license": artifact.get("source_license"),
            })

    for system in systems.values():
        _mark_exchangeability(system, crosswalk_systems)
    ordered = sorted(systems.values(), key=lambda row: (not row.get("exchangeable"), str(row.get("system") or "")))
    if not include_crosswalks:
        lite_keys = {
            "system", "label", "role", "country_scope", "country_scopes",
            "family_id", "exchangeable", "exchange_via", "resolver",
            "exchange_status", "bidirectional", "supported_geo_levels",
            "supported_vintages",
        }
        ordered = [
            {key: value for key, value in row.items() if key in lite_keys and value is not None}
            for row in ordered
        ]
    exchangeable_count = sum(1 for row in ordered if row.get("exchangeable"))
    return _clean_json({
        "ok": True,
        "reserve_system": LOC_ID_SYSTEM,
        "systems": ordered,
        "system_count": len(ordered),
        "exchangeable_count": exchangeable_count,
        "listed_only_count": len(ordered) - exchangeable_count,
        "exchangeability_note": (
            "A system is exchangeable only when it has a real resolution path: the loc_id reserve, an exact "
            "identifier crosswalk, a self-resolving named or admin geometry resolver, or a complete crosswalk "
            "artifact to loc_id. Systems with exchangeable=false are discoverable geometry or reference-graph "
            "families with no built crosswalk; resolve_reference and convert_reference will refuse them."
        ),
        "detail": "full" if include_crosswalks else "lite",
        "crosswalks_included": include_crosswalks,
        "next_call": ({
            "tool": "list_reference_systems",
            "arguments": {
                **({"country_scope": country} if country else {}),
                "include_crosswalks": True,
            },
        } if not include_crosswalks else None),
        "crosswalk_artifacts": crosswalks if include_crosswalks else [],
        "country_scope": country or None,
        "active_data_plane": "cloud" if is_cloud_mode() else "local",
        "crosswalks": canonical_crosswalks if include_crosswalks else [],
        "crosswalk_count": available_crosswalk_count,
        "returned_crosswalk_count": len(canonical_crosswalks),
        "active_data_plane_crosswalk_count": sum(
            1 for item in canonical_crosswalks if item.get("available_in_active_data_plane")
        ),
    })


def _public_catalog_records(catalog: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return the MCP published lane, excluding every candidate lifecycle."""
    return published_geometry_catalog_records(catalog, key)


def _geometry_catalog_records(
    catalog: dict[str, Any], key: str, *, read_wip: bool,
) -> list[dict[str, Any]]:
    if not read_wip:
        return _public_catalog_records(catalog, key)
    return [dict(item) for item in catalog.get(key) or [] if isinstance(item, dict)]


def _geometry_catalog_counts(catalog: dict[str, Any], *, read_wip: bool = False) -> dict[str, int]:
    counts = {
        key: len(_geometry_catalog_records(catalog, key, read_wip=read_wip))
        for key in (
            "geometry_collections",
            "geometry_banks",
            "geometry_families",
            "crosswalk_artifacts",
            "crosswalks",
            "reference_systems",
            "geometry_products",
            "release_packages",
            "resolver_groups",
            "named_reference_objects",
        )
    }
    counts["country_profiles"] = len(_geometry_catalog_records(catalog, "country_profiles", read_wip=read_wip))
    return counts


def _geometry_catalog_countries(catalog: dict[str, Any], *, read_wip: bool = False) -> list[dict[str, Any]]:
    """Project the catalog-owned active country and family inventory."""
    coverage_by_country = {
        str(item.get("country_code") or "").strip().upper(): item
        for item in catalog.get("country_family_coverage") or []
        if isinstance(item, dict) and str(item.get("country_code") or "").strip()
    }
    countries: list[dict[str, Any]] = []
    for profile in _geometry_catalog_records(catalog, "country_profiles", read_wip=read_wip):
        country_code = str(profile.get("country_code") or "").strip().upper()
        if not country_code:
            continue
        coverage = coverage_by_country.get(country_code) or {}
        levels = [
            int(item["level"])
            for item in profile.get("admin_levels") or []
            if isinstance(item, dict) and str(item.get("level", "")).isdigit()
        ]
        families = [
            {
                "family_id": family.get("family_id"),
                "label": family.get("label"),
                "publication_status": family.get("publication_status"),
                "native_tier_names": family.get("native_tier_names") or [],
                "gap_or_disposition": family.get("gap_or_disposition"),
                "coverage_status": family.get("coverage_status") or "unknown",
                "coverage_complete": bool(family.get("coverage_complete")),
                "coverage_basis": family.get("coverage_basis"),
                "coverage_denominator": family.get("coverage_denominator") or {},
                "covered_jurisdictions": family.get("covered_jurisdictions") or [],
                "unresolved_jurisdictions": family.get("unresolved_jurisdictions") or [],
                "hierarchy_coverage_status": family.get("hierarchy_coverage_status"),
                "hierarchy_coverage_complete": bool(family.get("hierarchy_coverage_complete")),
                "hierarchy_node_count": family.get("hierarchy_node_count"),
            }
            for family in coverage.get("families") or []
            if isinstance(family, dict) and (read_wip or family.get("available") is True)
        ]
        country = {
            "country_code": country_code,
            "label": profile.get("label") or coverage.get("label") or country_code,
            "release_version": profile.get("release_version"),
            "active_admin_depth": coverage.get("active_admin_depth") if coverage.get("active_admin_depth") is not None else (max(levels) if levels else None),
            "available_family_ids": list(coverage.get("available_family_ids") or []),
            "complete_family_ids": list(coverage.get("complete_family_ids") or []),
            "admin_hierarchy_coverage_status": coverage.get("admin_hierarchy_coverage_status"),
            "admin_hierarchy_coverage_complete": bool(coverage.get("admin_hierarchy_coverage_complete")),
            "admin_hierarchy_node_count": coverage.get("admin_hierarchy_node_count"),
            "families": families,
            "query_layout_available": bool(profile.get("query_layout_manifest")),
            "reference_graph_available": bool(profile.get("reference_graph_manifest")),
        }
        if read_wip:
            country.update({
                "release_status": profile.get("release_status"),
                "publication_status": profile.get("publication_status"),
                "runtime_state": profile.get("runtime_state"),
                "candidate_state": profile.get("candidate_state"),
            })
        countries.append(country)
    return sorted(countries, key=lambda item: (str(item.get("label") or ""), item["country_code"]))


def _geometry_catalog_admin_coverage(catalog: dict[str, Any], *, read_wip: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    assets = _geometry_catalog_records(catalog, "geometry_products", read_wip=read_wip)
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        coverage = asset.get("admin_coverage")
        if not isinstance(coverage, dict):
            continue
        levels = coverage.get("levels") if isinstance(coverage.get("levels"), list) else []
        rows.append({
            "product_id": asset.get("product_id"),
            "label": asset.get("label"),
            "scope": asset.get("scope") or coverage.get("scope"),
            "family": asset.get("family"),
            "feature_count": asset.get("feature_count"),
            "has_shapes": bool(asset.get("has_shapes")),
            "min_admin_level": coverage.get("min_admin_level"),
            "max_admin_level": coverage.get("max_admin_level"),
            "levels": [
                {
                    "admin_level": item.get("admin_level"),
                    "label": item.get("label"),
                    "row_count": item.get("row_count"),
                    "file_count": item.get("file_count"),
                }
                for item in levels
                if isinstance(item, dict)
            ],
        })
    rows.sort(key=lambda item: (str(item.get("scope") or ""), str(item.get("product_id") or "")))
    return rows


def _geometry_catalog_crosswalk_artifacts(catalog: dict[str, Any], *, read_wip: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in _geometry_catalog_records(catalog, "crosswalk_artifacts", read_wip=read_wip):
        if not isinstance(artifact, dict):
            continue
        source_license = artifact.get("source_license") if isinstance(artifact.get("source_license"), dict) else {}
        rows.append({
            "source_system": artifact.get("source_family"),
            "target_system": LOC_ID_SYSTEM,
            "target_family": artifact.get("target_family"),
            "target_admin_level": artifact.get("target_admin_level"),
            "relationship_vintage": artifact.get("relationship_vintage"),
            "status": artifact.get("status"),
            "row_count": artifact.get("row_count"),
            "source_count": artifact.get("source_count"),
            "target_count": artifact.get("target_count"),
            "license": source_license.get("license"),
            "license_review_status": source_license.get("license_review_status"),
        })
    return rows


def _geometry_catalog_products(catalog: dict[str, Any], *, read_wip: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for package in _geometry_catalog_records(catalog, "geometry_products", read_wip=read_wip):
        if not isinstance(package, dict):
            continue
        coverage = package.get("admin_coverage") if isinstance(package.get("admin_coverage"), dict) else {}
        rows.append({
            "product_id": package.get("product_id"),
            "label": package.get("label"),
            "group": package.get("product_group") or package.get("group"),
            "family": package.get("family"),
            "scope": package.get("scope"),
            "summary": package.get("summary"),
            "feature_count": package.get("feature_count"),
            "has_shapes": bool(package.get("has_shapes")),
            "artifact_kind": package.get("artifact_kind"),
            "max_admin_level": coverage.get("max_admin_level"),
            "cloud_probe_path": package.get("cloud_probe_path"),
        })
    return rows


def _geometry_catalog_domains(catalog: dict[str, Any], *, read_wip: bool = False) -> list[dict[str, Any]]:
    """Project independently versioned non-country geometry activation."""
    rows: list[dict[str, Any]] = []
    for profile in _geometry_catalog_records(catalog, "domain_profiles", read_wip=read_wip):
        active = profile.get("active_release") if isinstance(profile.get("active_release"), dict) else {}
        artifacts = active.get("runtime_artifacts") if isinstance(active.get("runtime_artifacts"), dict) else {}
        country_components = artifacts.get("country_components") if isinstance(artifacts.get("country_components"), dict) else {}
        rows.append({
            "release_unit_id": profile.get("release_unit_id"),
            "release_unit_kind": profile.get("release_unit_kind"),
            "label": profile.get("label"),
            "family_ids": profile.get("family_ids") or [],
            "release_id": active.get("release_id") or profile.get("release_id"),
            "release_version": active.get("release_version") or profile.get("release_version"),
            "publication_status": active.get("publication_status") or profile.get("release_status"),
            "version_manifest_path": active.get("version_manifest_path"),
            "version_manifest_sha256": active.get("version_manifest_sha256"),
            "runtime_artifacts": {
                key: value for key, value in artifacts.items()
                if key != "country_components"
            },
            "country_component_count": len(country_components),
        })
    return sorted(rows, key=lambda item: str(item.get("release_unit_id") or ""))


def _geometry_catalog_named_reference_objects(
    catalog: dict[str, Any], *, limit: int, read_wip: bool = False,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    items = [
        item
        for item in _geometry_catalog_records(catalog, "named_reference_objects", read_wip=read_wip)
    ]
    for item in items[: max(0, limit)]:
        rows.append({
            "loc_id": item.get("loc_id"),
            "label": item.get("label"),
            "family": item.get("family"),
            "resolvable": item.get("resolvable"),
            "parent_loc_id": item.get("parent_loc_id"),
            "geometry_path": item.get("geometry_path"),
            "bank_id": item.get("bank_id"),
        })
    return {"items": rows, "returned": len(rows), "total": len(items), "truncated": len(rows) < len(items)}


def _published_geometry_family_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index published families by family id and retain only available countries."""
    # This is also the vocabulary rendered by docs_geometry_families.html. It is
    # the naming authority; source-specific reference-system IDs must never be
    # promoted into the top-level family list.
    definitions = {
        str(item.get("family_id") or "").strip(): item
        for item in catalog.get("geometry_family_definitions") or []
        if isinstance(item, dict) and str(item.get("family_id") or "").strip()
    }
    families: dict[str, dict[str, Any]] = {}
    for coverage in _public_catalog_records(catalog, "country_family_coverage"):
        country_code = str(coverage.get("country_code") or "").strip().upper()
        if not country_code:
            continue
        country_label = str(coverage.get("label") or country_code)
        for raw_family in coverage.get("families") or []:
            if not isinstance(raw_family, dict) or raw_family.get("available") is not True:
                continue
            family_id = str(raw_family.get("family_id") or "").strip()
            if not family_id or family_id not in definitions:
                continue
            definition = definitions[family_id]
            entry = families.setdefault(family_id, {
                "family_id": family_id,
                "label": definition.get("label") or family_id.replace("_", " ").title(),
                "short_label": definition.get("short_label"),
                "description": definition.get("description"),
                "examples": list(definition.get("examples") or []),
                "search_terms": list(definition.get("search_terms") or []),
                "countries": [],
                "scopes": [],
                "domain_units": [],
            })
            if country_code == "GLOBAL":
                entry["scopes"].append("GLOBAL")
                entry["domain_units"].append({
                    "unit_id": "GLOBAL",
                    "kind": "global_domain",
                    "domain_type": "baseline",
                    "label": "Global baseline",
                })
            else:
                entry["countries"].append({
                    "country_code": country_code,
                    "label": country_label,
                    "coverage_status": raw_family.get("coverage_status"),
                    "coverage_complete": bool(raw_family.get("coverage_complete")),
                })

    for profile in _public_catalog_records(catalog, "domain_profiles"):
        scope = str(profile.get("release_unit_id") or "").strip().upper()
        active = profile.get("active_release") if isinstance(profile.get("active_release"), dict) else {}
        publication_status = str(active.get("publication_status") or profile.get("release_status") or "").lower()
        if not scope or publication_status not in {
            "published", "approved_for_publication", "active", "current",
        }:
            continue
        for family_id in profile.get("family_ids") or []:
            family_id = str(family_id or "").strip()
            # Physical masks and raster surfaces are products, not loc_id
            # reference families. They remain in the downloadable catalog.
            if family_id not in definitions or family_id == "physical_surface":
                continue
            definition = definitions[family_id]
            entry = families.setdefault(family_id, {
                "family_id": family_id,
                "label": definition.get("label") or family_id.replace("_", " ").title(),
                "short_label": definition.get("short_label"),
                "description": definition.get("description"),
                "examples": list(definition.get("examples") or []),
                "search_terms": list(definition.get("search_terms") or []),
                "countries": [],
                "scopes": [],
                "domain_units": [],
            })
            if scope not in entry["scopes"]:
                entry["scopes"].append(scope)
            if scope not in {item["unit_id"] for item in entry["domain_units"]}:
                entry["domain_units"].append({
                    "unit_id": scope,
                    "kind": "global_domain",
                    "domain_type": scope.lower(),
                    "label": profile.get("label") or scope,
                })

    for entry in families.values():
        entry["countries"] = sorted(entry["countries"], key=lambda item: item["country_code"])
        entry["scopes"] = sorted(entry.get("scopes") or [])
        entry["domain_units"] = sorted(entry.get("domain_units") or [], key=lambda item: item["unit_id"])
    return families


def geometry_catalog_discovery(
    *, detail: str = "lite", country_scope: str | None = None,
) -> dict[str, Any]:
    """Return the agent-facing geometry catalog used by the unified get_catalog."""
    catalog = load_geometry_catalog()
    selected_country = str(country_scope or "").strip().upper()
    family_index = _published_geometry_family_index(catalog)
    families = []
    for family_id, entry in sorted(family_index.items()):
        countries = entry["countries"]
        if selected_country:
            countries = [item for item in countries if item["country_code"] == selected_country]
            if not countries:
                continue
        row = {
            "pack_id": family_id,
            "label": entry["label"],
            "short_label": entry.get("short_label"),
            "countries": [item["country_code"] for item in countries],
            "country_count": len(countries),
            "scopes": entry.get("scopes") or [],
            "release_units": [
                {"unit_id": item["country_code"], "kind": "country", "label": item["label"]}
                for item in countries
            ] + list(entry.get("domain_units") or []),
            "next_call": {
                "tool": "get_pack",
                "arguments": {"catalog": "geometry", "pack_id": family_id, "detail": "lite"},
            },
        }
        if selected_country:
            row["next_call"]["arguments"]["country_scope"] = selected_country
        if detail == "full":
            row.update({
                "description": entry.get("description"),
                "examples": entry.get("examples") or [],
                "search_terms": entry.get("search_terms") or [],
                "country_details": countries,
                "reference_systems": sorted({
                    str(item.get("system") or "")
                    for item in _public_catalog_records(catalog, "reference_systems")
                    if item.get("callable") is True
                    and str(item.get("family_id") or "") == family_id
                    and (not selected_country or str(item.get("country_code") or "").upper() == selected_country)
                    and str(item.get("system") or "")
                }),
            })
        families.append(_clean_json(row))
    return _clean_json({
        "ok": True,
        "catalog": "geometry",
        "detail": detail,
        "country_scope": selected_country or None,
        "family_count": len(families),
        "families": families,
        "usage": {
            "meaning": "A listed family release unit exists and can be used through loc_id. Release units are countries or global domains.",
            "next_step": "Call get_pack for a family. Add country_scope for a country or release_unit for a global domain when versions, vintages, levels, or artifacts are needed.",
        },
        "download": {
            "download_url": "https://app.daedalmap.com/api/v1/geometry/catalog/download",
            "media_type": "application/json",
        },
    })


def geometry_pack_detail(
    pack_id: str, *, country_scope: str | None = None,
    release_unit: str | None = None, detail: str = "lite",
) -> dict[str, Any]:
    """Describe one geometry family globally or within one selected country."""
    catalog = load_geometry_catalog()
    requested = str(pack_id or "").strip()
    selected_country = str(country_scope or "").strip().upper()
    selected_unit = str(release_unit or "").strip().upper()
    family_index = _published_geometry_family_index(catalog)
    references = _public_catalog_records(catalog, "reference_systems")

    normalized = SYSTEM_ALIASES.get(requested.lower(), requested.lower())
    family_id = normalized if normalized in family_index else ""
    if not family_id:
        family_id = next((
            candidate for candidate, system in FAMILY_DEFAULT_SYSTEMS.items()
            if normalized == system and candidate in family_index
        ), "")
    if not family_id:
        for system in references:
            identifiers = {
                str(system.get("system") or "").strip().lower(),
                str(system.get("reference_system_id") or "").strip().lower(),
            }
            if normalized in identifiers or requested.lower() in identifiers:
                family_id = str(system.get("family_id") or "").strip()
                break
    family = family_index.get(family_id)
    if not family:
        return {
            "ok": False,
            "catalog": "geometry",
            "pack_id": requested,
            "error": {
                "code": "geometry_family_not_found",
                "message": f"Geometry family or reference system '{requested}' is not published.",
            },
        }

    countries = family["countries"]
    domain_units = list(family.get("domain_units") or [])
    if selected_country:
        countries = [item for item in countries if item["country_code"] == selected_country]
        if not countries:
            return {
                "ok": False,
                "catalog": "geometry",
                "pack_id": family_id,
                "country_scope": selected_country,
                "error": {
                    "code": "geometry_family_not_found_for_country",
                    "message": f"Family '{family_id}' is not published for {selected_country}.",
                },
            }
    if selected_unit and selected_unit not in {item["unit_id"] for item in domain_units}:
        return {
            "ok": False,
            "catalog": "geometry",
            "pack_id": family_id,
            "release_unit": selected_unit,
            "error": {
                "code": "geometry_family_not_found_for_release_unit",
                "message": f"Family '{family_id}' is not published in release unit {selected_unit}.",
            },
        }

    base = {
        "ok": True,
        "catalog": "geometry",
        "kind": "geometry_family",
        "pack_id": family_id,
        "requested_as": requested if requested != family_id else None,
        "label": family.get("label"),
        "short_label": family.get("short_label"),
        "description": family.get("description"),
        "country_scope": selected_country or None,
        "release_unit": selected_unit or None,
        "country_count": len(countries),
        "countries": [item["country_code"] for item in countries],
        "scopes": family.get("scopes") or [],
        "release_units": [
            {"unit_id": item["country_code"], "kind": "country", "label": item["label"]}
            for item in countries
        ] + domain_units,
        "detail": detail,
        "next_step": {
            "tool": "convert_reference",
            "arguments": {
                "from_system": "<system listed by this family>",
                "value": "<identifier>",
                "to_system": "daedalmap.loc_id",
            },
        },
    }
    if not selected_country and not selected_unit and countries:
        base["next_step"] = {
            "tool": "get_pack",
            "arguments": {
                "catalog": "geometry",
                "pack_id": family_id,
                "country_scope": "<ISO3 from countries>",
                "detail": "full",
            },
        }
        base["usage"] = (
            "This family-level view answers where the family exists. Call get_pack again with "
            "country_scope for country-specific versions, vintages, levels, and artifacts."
        )
        base["country_detail_call"] = {
            "tool": "get_pack",
            "arguments": {
                "catalog": "geometry",
                "pack_id": family_id,
                "country_scope": "<ISO3 from countries>",
                "detail": "full",
            },
        }
        base["release_unit_detail_calls"] = [
            {
                "tool": "get_pack",
                "arguments": {
                    "catalog": "geometry",
                    "pack_id": family_id,
                    "release_unit": item["unit_id"],
                    "detail": "full",
                },
            }
            for item in domain_units
        ]
        return _clean_json(base)

    if not selected_country:
        default_system = FAMILY_DEFAULT_SYSTEMS.get(family_id, family_id)
        domains = []
        for profile in _public_catalog_records(catalog, "domain_profiles"):
            if selected_unit and str(profile.get("release_unit_id") or "").upper() != selected_unit:
                continue
            if family_id not in {str(value or "") for value in profile.get("family_ids") or []}:
                continue
            active = profile.get("active_release") if isinstance(profile.get("active_release"), dict) else {}
            domain = {
                "scope": profile.get("release_unit_id"),
                "label": profile.get("label"),
                "release_id": active.get("release_id") or profile.get("release_id"),
                "release_version": active.get("release_version") or profile.get("release_version"),
                "publication_status": active.get("publication_status") or profile.get("release_status"),
            }
            if detail == "full":
                domain["family"] = next((
                    dict(item) for item in profile.get("family_coverage") or []
                    if isinstance(item, dict) and str(item.get("family_id") or "") == family_id
                ), {})
                domain["package_recipes"] = list(profile.get("package_recipes") or [])
            domains.append(domain)
        base["domains"] = domains
        base["next_step"] = {
            "tool": "convert_reference",
            "arguments": {
                "from_system": default_system,
                "value": "<identifier>",
                "to_system": "daedalmap.loc_id",
            },
        }
        base["usage"] = (
            "This is a published non-country geometry release unit; no ISO3 country drill-down is required."
            if selected_unit else
            "This family is published only in non-country geometry release units; select release_unit if more than one is listed."
        )
        return _clean_json(base)

    coverage_record: dict[str, Any] = {}
    for coverage in _public_catalog_records(catalog, "country_family_coverage"):
        if str(coverage.get("country_code") or "").upper() != selected_country:
            continue
        coverage_record = next((
            dict(item) for item in coverage.get("families") or []
            if isinstance(item, dict)
            and item.get("available") is True
            and str(item.get("family_id") or "") == family_id
        ), {})
        break
    family_systems = [
        dict(item) for item in references
        if item.get("callable") is True
        and str(item.get("country_code") or "").upper() == selected_country
        and str(item.get("family_id") or "") == family_id
    ]
    if family_systems:
        base["next_step"]["arguments"]["from_system"] = family_systems[0].get("system") or family_id
    profile = next((
        dict(item) for item in _public_catalog_records(catalog, "country_profiles")
        if str(item.get("country_code") or "").upper() == selected_country
    ), {})
    base["reference_systems"] = family_systems
    base["country_details"] = countries
    base["release"] = {
        key: profile.get(key)
        for key in ("release_id", "release_version", "graph_release_id", "release_status")
        if profile.get(key) is not None
    }
    if detail == "full":
        base["family"] = coverage_record
        systems = {str(item.get("system") or "") for item in family_systems}
        base["crosswalks"] = [
            dict(item) for item in _public_catalog_records(catalog, "crosswalks")
            if str(item.get("country_code") or "").upper() == selected_country
            and (
                str(item.get("source_family_id") or "") == family_id
                or str(item.get("target_family_id") or "") == family_id
                or str(item.get("source_system") or "") in systems
                or str(item.get("target_system") or "") in systems
            )
        ]
    else:
        base["family"] = {
            key: coverage_record.get(key)
            for key in (
                "family_id", "label", "publication_status", "coverage_status",
                "coverage_complete", "max_admin_level", "native_tier_names",
                "subtypes", "source_ids", "source_releases",
            )
            if coverage_record.get(key) is not None
        }
    return _clean_json(base)


def read_geometry_catalog(
    *, view: str = "capabilities", limit: int | None = 50, country_scope: str | None = None,
    read_wip: bool = False,
) -> dict[str, Any]:
    """Return an agent-oriented published or explicitly authorized WIP view."""
    catalog = load_geometry_catalog()
    selected_country = str(country_scope or "").strip().upper()
    country_catalog = load_country_geometry_catalog(selected_country) if selected_country else {}
    has_country_catalog = bool(country_catalog.get("country_profile"))
    selected_view = str(view or "capabilities").strip().lower().replace("-", "_")
    row_limit = max(1, min(int(limit or 50), 500))
    base = {
        "ok": True,
        "view": selected_view,
        "catalog_surface": "wip" if read_wip else "published",
        "schema_version": catalog.get("schema_version") or catalog.get("_schema_version"),
        "generated_at": catalog.get("generated_at"),
        "app_summary_endpoint": "https://app.daedalmap.com/api/v1/geometry/catalog",
        "download_url": "https://app.daedalmap.com/api/v1/geometry/catalog/download",
        "catalog_path": "geometry/geometry_catalog.json",
        "counts": _geometry_catalog_counts(catalog, read_wip=read_wip),
        "capabilities": geometry_capability_summary(catalog),
        "country_catalog": ({
            "path": f"geometry/countries/{selected_country}/reference/catalog.json",
            "catalog_fingerprint": country_catalog.get("catalog_fingerprint"),
            "summary": country_catalog.get("summary") or {},
        } if has_country_catalog else None),
        "usage": {
            "start_here": "Use capabilities for the concise current coverage model. Use summary or a focused inventory view only when more catalog detail is needed.",
            "loc_id_rule": "Shape and data tools are keyed to DaedalMap loc_id. If an input is not a loc_id, call resolve_reference first.",
            "bulk_rule": "Prepared bulk point requests should provide country_scope and target_admin_level; geometry exports should preflight before create.",
            "wip_rule": (
                "This local-only view may contain staged, blocked, incomplete, or otherwise non-callable records. Use full to inspect complete lifecycle detail."
                if read_wip else
                "This is the published projection. Staged, blocked, and in-progress records are excluded."
            ),
        },
    }
    if selected_view == "capabilities" and selected_country:
        from .geometry_inventory import country_capability_record

        country = country_capability_record(catalog, selected_country)
        if country is None:
            return _clean_json({
                **base,
                "ok": False,
                "country_scope": selected_country,
                "error": {
                    "code": "country_not_found",
                    "message": f"Country {selected_country} is not present in the active geometry catalog.",
                },
            })
        return _clean_json({**base, "country_scope": selected_country, "country": country})
    if selected_view == "capabilities":
        return _clean_json(base)
    if selected_view == "summary":
        if has_country_catalog:
            return _clean_json({
                **base,
                "country_scope": selected_country,
                "country_profile": country_catalog.get("country_profile"),
                "family_coverage": country_catalog.get("family_coverage"),
                "reference_system_count": len(country_catalog.get("reference_systems") or []),
                "crosswalk_count": len(country_catalog.get("crosswalks") or []),
            })
        return _clean_json({
            **base,
            "collections": [
                {key: item.get(key) for key in ("collection_id", "label", "family_count", "feature_count") if item.get(key) is not None}
                for item in _geometry_catalog_records(catalog, "geometry_collections", read_wip=read_wip)
            ],
            "families": [
                {key: item.get(key) for key in ("family", "family_id", "label", "feature_count", "resolver") if item.get(key) is not None}
                for item in _geometry_catalog_records(catalog, "geometry_families", read_wip=read_wip)
            ],
            "admin_coverage": _geometry_catalog_admin_coverage(catalog, read_wip=read_wip),
            "next_calls": {
                "reference_systems": {"tool": "list_reference_systems", "arguments": {"include_crosswalks": False}},
                "shape": {"tool": "get_geometry", "arguments": {"loc_id": "<selected loc_id>", "detail": "lite"}},
            },
        })
    if selected_view == "admin_coverage":
        return _clean_json({**base, "admin_coverage": _geometry_catalog_admin_coverage(catalog, read_wip=read_wip)})
    if selected_view == "countries":
        return _clean_json({**base, "countries": _geometry_catalog_countries(catalog, read_wip=read_wip)})
    if selected_view == "crosswalk_artifacts":
        return _clean_json({
            **base,
            "crosswalk_artifacts": _geometry_catalog_crosswalk_artifacts(catalog, read_wip=read_wip),
        })
    if selected_view == "crosswalks":
        source = country_catalog if has_country_catalog else catalog
        records = _geometry_catalog_records(source, "crosswalks", read_wip=read_wip)
        if selected_country:
            records = [
                item for item in records
                if str(item.get("country_code") or "").upper() == selected_country
            ]
        return _clean_json({
            **base,
            "country_scope": selected_country or None,
            "crosswalks": records[:row_limit],
            "returned": min(len(records), row_limit),
            "total": len(records),
            "truncated": len(records) > row_limit,
        })
    if selected_view == "products":
        return _clean_json({**base, "products": _geometry_catalog_products(catalog, read_wip=read_wip)})
    if selected_view == "domains":
        return _clean_json({**base, "domains": _geometry_catalog_domains(catalog, read_wip=read_wip)})
    if selected_view == "named_reference_objects":
        return _clean_json({**base, "named_reference_objects": _geometry_catalog_named_reference_objects(catalog, limit=row_limit, read_wip=read_wip)})
    if selected_view == "full":
        if not read_wip:
            return _clean_json({
                **base,
                "view": "full_redirect",
                "guidance": "Download the full catalog directly. Use summary, capabilities, or a focused view for MCP discovery.",
            })
        if has_country_catalog:
            return _clean_json({**base, "country_scope": selected_country, "catalog": country_catalog})
        return _clean_json({**base, "catalog": catalog})
    return _clean_json({
        **base,
        "ok": False,
        "error": {
            "code": "invalid_view",
            "message": "view must be one of capabilities, summary, countries, domains, admin_coverage, crosswalk_artifacts, crosswalks, products, named_reference_objects, or full",
        },
    })


def _direct_loc_id_result(value: str, *, request_system: str) -> dict[str, Any]:
    resolution = resolve_loc_id_input(value)
    if not resolution.get("ok"):
        return {
            **_public_alias_error(resolution),
            "from_system": request_system,
            "input": value,
            "resolved_loc_id": None,
        }
    loc_id = str(resolution.get("loc_id") or canonicalize_loc_id(value))
    if not loc_id:
        return {
            "ok": False,
            "from_system": request_system,
            "input": value,
            "resolved_loc_id": None,
            "error": {
                "code": "loc_id_required",
                "message": "value is not a parseable loc_id",
            },
        }
    # Passthrough normalizes case; it does not confer existence. Without this
    # check an Overture GERS UUID, or any dash-separated token, came back as a
    # confirmed loc_id purely because it had the right punctuation.
    if not verify_loc_ids([loc_id]):
        return {
            "ok": False,
            "from_system": request_system,
            "input": value,
            "normalized_input": loc_id,
            "resolved_loc_id": None,
            "error": {
                "code": "loc_id_not_found",
                "message": "no maintained identity or geometry matches that loc_id",
            },
        }
    return _attach_public_alias_resolution({
        "ok": True,
        "from_system": request_system,
        "input": value,
        "resolved_loc_id": loc_id,
        "resolved_family": classify_loc_id_family(loc_id),
        "match_type": "loc_id_passthrough",
        "references": [{"system": LOC_ID_SYSTEM, "value": loc_id, "role": "reserve"}],
    }, resolution)


def _admin_text_result(value: str, *, country_hint: str | None, admin_level_hint: int | None, request_system: str) -> dict[str, Any]:
    raw = resolve_admin_text_to_loc_id(value, country_hint=country_hint, admin_level_hint=admin_level_hint)
    loc_id = raw.get("deepest_resolved_loc_id")
    return {
        "ok": bool(loc_id) and not raw.get("error"),
        "from_system": request_system,
        "input": value,
        "resolved_loc_id": loc_id,
        "resolved_family": classify_loc_id_family(loc_id),
        "match_type": raw.get("match_type"),
        "admin_level": raw.get("deepest_resolved_admin_level"),
        "matches": raw.get("matches") or {},
        "error": raw.get("error"),
    }


def _global_admin0_identity_result(
    value: str,
    identity: Any | None,
) -> dict[str, Any]:
    """Return the tiny exact-code result used by single and batch resolution."""
    normalized = str(value or "").strip().upper()
    if identity is None:
        return {
            "ok": False,
            "from_system": "geoboundaries.code",
            "input": value,
            "normalized_input": normalized,
            "error": {
                "code": "admin_spine_match_not_found",
                "message": "identifier did not match the maintained global Admin0 identity index",
            },
        }
    return {
        "ok": True,
        "from_system": "geoboundaries.code",
        "input": value,
        "normalized_input": normalized,
        "resolved_loc_id": normalized,
        "resolved_family": "admin_boundary",
        "admin_level": "admin_0",
        "match_type": "admin_spine_exact",
        "name": identity.get("name") if hasattr(identity, "get") else None,
        "source_system": identity.get("source_system") if hasattr(identity, "get") else None,
    }


def resolve_reference(
    *,
    from_system: str,
    value: str,
    iso3: str | None = None,
    target_admin_level: int | str | None = "admin_2",
    relationship_vintage: str | None = None,
    min_share: float | None = None,
    limit: int | None = 10,
    country_hint: str | None = None,
    admin_level_hint: int | None = None,
    as_of: str | None = None,
    source_release: str | None = None,
    internal_release: str | None = None,
) -> dict[str, Any]:
    """Resolve a reference-system value into one or more ``loc_id`` matches."""
    system = _normalize_system(from_system)
    text = str(value or "").strip()
    if not text:
        return {"ok": False, "from_system": system, "input": value, "error": "value is required"}
    if system in {LOC_ID_SYSTEM, "admin_local", "admin_geometry"} or system.startswith(
        ("public.", "daedalmap.public.")
    ):
        return _clean_json(_direct_loc_id_result(text, request_system=system))
    if get_external_adapter(system):
        # External edges own their typed relationship and two release clocks.
        # An admin level is observed metadata, never caller-steerable input.
        payload = resolve_external_reference(
            system,
            text,
            # Only an explicit country hint may constrain an external adapter.
            country_scope=country_hint or None,
            source_release=source_release,
            internal_release=internal_release,
            limit=limit,
        )
        if system == GERS_SYSTEM:
            # Transitional aliases only; source_level/source_release/
            # internal_release are the canonical generic fields.
            payload.setdefault("admin_level", payload.get("source_level"))
            payload.setdefault("overture_subtype", payload.get("external_subtype"))
            payload.setdefault("overture_release", payload.get("source_release"))
            payload.setdefault("spine_vintage", payload.get("internal_release"))
        return _clean_json(payload)
    if system == "us_census_geoid":
        from .reference_identification import census_geoid_level, census_geoid_to_loc_id

        loc_id = census_geoid_to_loc_id(text)
        level = census_geoid_level(text)
        if not loc_id:
            return {
                "ok": False,
                "from_system": system,
                "input": value,
                "error": {
                    "code": "invalid_census_geoid",
                    "message": "expected a maintained 2, 5, 11, 12, or 15 digit US Census GEOID",
                },
            }
        availability = get_geometry_availability([loc_id])
        item = (availability.get("items") or [{}])[0]
        return _clean_json({
            "ok": True,
            "from_system": system,
            "input": value,
            "normalized_input": text,
            "resolved_loc_id": loc_id,
            "resolved_family": "admin_boundary",
            "admin_level": level,
            "match_type": "exact_identifier_crosswalk",
            "geometry_available": bool(item.get("has_shape")),
            "geometry": item,
            "source_vintage": "census_2020",
        })
    if system == "geoboundaries.code":
        # geoBoundaries Admin0 codes are already canonical ISO3 loc_ids.  A
        # compact identity-index membership test is the entire conversion;
        # opening the all-country reference graph here turns a tiny join into
        # a multi-second scan and adds no evidence.
        from .global_admin0_query import load_global_admin0_identities

        normalized = text.upper()
        identities = load_global_admin0_identities([normalized])
        if identities is not None:
            return _clean_json(_global_admin0_identity_result(text, identities.get(normalized)))
    if system == ADMIN_SYSTEM:
        # Numeric US administrative identifiers are Census/FIPS GEOIDs, not
        # postal text.  Only accept this interpretation when the maintained
        # geometry exists; otherwise preserve the general admin-text path.
        country = str(country_hint or iso3 or "").strip().upper()
        if country == "USA" and text.isdigit() and len(text) in {2, 5, 11, 12, 15}:
            census_result = resolve_reference(from_system="us_census_geoid", value=text, iso3="USA")
            if census_result.get("ok") and census_result.get("geometry_available"):
                census_result["from_system"] = system
                census_result["match_type"] = "fips_exact_identifier_crosswalk"
                return _clean_json(census_result)
        return _clean_json(_admin_text_result(text, country_hint=country_hint or iso3, admin_level_hint=admin_level_hint, request_system=system))
    if system == "historical_country":
        historical = resolve_historical_country_reference(text, as_of=as_of)
        if historical:
            return _clean_json(historical)
        return {
            "ok": False,
            "from_system": system,
            "input": value,
            "as_of": as_of,
            "error": {"code": "historical_reference_not_found", "message": "no maintained historical country assertion matched the value"},
        }
    if system in {"water_body", "marine_eez", "regional_base"}:
        named = resolve_geometry_name(text)
        if named and named.get("loc_id"):
            return _clean_json({
                "ok": True,
                "from_system": system,
                "input": value,
                "resolved_loc_id": named.get("loc_id"),
                "resolved_family": named.get("family") or classify_loc_id_family(named.get("loc_id")),
                "match_type": "named_geometry",
                "match": named,
            })
        if system == "marine_eez":
            # EEZ ids are ISO3-suffixed, but the bank labels them "Australian
            # Exclusive Economic Zone" with no aliases, so a country name never
            # matches by name. Resolve the country first, then the zone.
            eez = _resolve_eez_by_country(text)
            if eez:
                return _clean_json({
                    "ok": True,
                    "from_system": system,
                    "input": value,
                    "resolved_loc_id": eez["loc_id"],
                    "resolved_family": "marine_eez",
                    "match_type": "country_to_eez",
                    "match": eez,
                })
            # Never echo the input back as a loc_id. A fabricated identifier is
            # worse than a refusal because the caller cannot tell it apart from
            # a real one until it fails downstream.
            return _clean_json({
                "ok": False,
                "from_system": system,
                "input": value,
                "error": {
                    "code": "marine_eez_not_found",
                    "message": "no maintained EEZ matched that name, country, or ISO3 code",
                },
            })
        return _clean_json(_direct_loc_id_result(text, request_system=system))

    level = admin_level_name(target_admin_level or "admin_2")
    artifact = _first_crosswalk_artifact(
        source_family=system,
        target_admin_level=level,
        iso3=iso3,
        relationship_vintage=relationship_vintage,
    )
    if not artifact:
        direct_record, direct_matches = _direct_crosswalk_matches(
            from_system=system,
            value=text,
            to_system=None,
            iso3=iso3,
            limit=limit or 10,
        )
        if direct_record and direct_matches:
            primary = direct_matches[0]
            return _clean_json({
                "ok": True,
                "from_system": system,
                "input": value,
                "normalized_input": primary.get("input_reference_id") or text,
                "resolved_loc_id": primary.get("input_loc_id"),
                "resolved_family": primary.get("input_family_id"),
                "match_type": "canonical_crosswalk_identity",
                "crosswalk_id": direct_record.get("crosswalk_id"),
                "relationship_vintage": direct_record.get("relationship_vintage"),
                "lineage": direct_record.get("source_material_identity"),
                "matches": direct_matches,
                "match_count": len(direct_matches),
            })
        try:
            from .reference_graph import identity as graph_identity, resolve_alias

            normalized_alias = _normalize_source_loc_id(system, text, iso3 or "")
            graph_matches = resolve_alias(system, normalized_alias, limit=limit or 10, iso3=iso3)
        except Exception:
            graph_matches = []
        if graph_matches:
            primary = graph_matches[0]
            graph_node = graph_identity(str(primary.get("loc_id") or "")) or {}
            return _clean_json({
                "ok": True,
                "from_system": system,
                "input": value,
                "normalized_input": normalized_alias,
                "resolved_loc_id": primary.get("loc_id"),
                "resolved_family": graph_node.get("family") or classify_loc_id_family(primary.get("loc_id")),
                "match_type": "reference_graph_alias",
                "matches": graph_matches,
                "match_count": len(graph_matches),
            })
        return {
            "ok": False,
            "from_system": system,
            "input": value,
            "error": f"no crosswalk artifact found for {system} -> {level}",
        }
    source_loc_id = _normalize_source_loc_id(system, text, iso3)
    result = resolve_family_to_admin(
        source_loc_id,
        source_family=system,
        target_admin_level=level,
        iso3=iso3,
        crosswalk_path=_catalog_crosswalk_path(artifact),
        min_source_area_share=min_share,
        limit=limit,
    )
    primary = result.get("primary_match") or {}
    return _clean_json({
        "ok": bool(result.get("ok")),
        "from_system": system,
        "input": value,
        "normalized_input": source_loc_id,
        "resolved_loc_id": primary.get("match_loc_id"),
        "resolved_family": "admin_boundary" if primary.get("match_loc_id") else None,
        "match_type": (
            "crosswalk_overlap"
            if primary.get("source_area_share") is not None
            else "crosswalk_identity"
        ),
        "crosswalk": {
            "artifact_path": artifact.get("artifact_path"),
            "relationship_vintage": artifact.get("relationship_vintage"),
            "target_admin_level": level,
        },
        "primary_match": primary,
        "matches": result.get("overlaps") or [],
        "match_count": result.get("overlap_count") or 0,
        "error": result.get("error"),
    })


def resolve_references_batch(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve reference requests with one lookup per shared identity source.

    Census GEOIDs are matched together against the admin identity spine.
    Homogeneous family-to-admin crosswalk work is also coalesced. Other direct,
    alias, historical, and family-to-family requests retain their established
    single-request paths.
    """
    results: list[dict[str, Any] | None] = [None] * len(requests)
    groups: dict[tuple[Any, ...], list[tuple[int, dict[str, Any]]]] = {}
    census_candidates: list[tuple[int, dict[str, Any], str, str | None, str | None]] = []
    global_admin0_candidates: list[tuple[int, dict[str, Any], str]] = []
    external_groups: dict[tuple[Any, ...], list[tuple[int, dict[str, Any], str]]] = {}
    native_admin_groups: dict[str, list[tuple[int, dict[str, Any], str]]] = {}
    unscoped_alias_groups: dict[str, list[tuple[int, dict[str, Any], str]]] = {}
    for index, request in enumerate(requests):
        if request.get("to_system"):
            results[index] = convert_reference(**request)
            continue
        system = _normalize_system(request.get("from_system"))
        if system == "us_census_geoid":
            from .reference_identification import census_geoid_level, census_geoid_to_loc_id

            value = str(request.get("value") or "").strip()
            loc_id = census_geoid_to_loc_id(value)
            census_candidates.append((index, request, value, loc_id, census_geoid_level(value)))
            continue
        if system == "geoboundaries.code":
            value = str(request.get("value") or "").strip()
            global_admin0_candidates.append((index, request, value))
            continue
        if system == "admin.native_id":
            country = str(request.get("iso3") or "").strip().upper()
            value = str(request.get("value") or "").strip()
            native_admin_groups.setdefault(country, []).append((index, request, value))
            continue
        if get_external_adapter(system):
            key = (
                system,
                str(request.get("country_hint") or "").strip().upper(),
                str(request.get("source_release") or "").strip(),
                str(request.get("internal_release") or "").strip(),
                request.get("limit", 10),
            )
            external_groups.setdefault(key, []).append(
                (index, request, str(request.get("value") or "").strip())
            )
            continue
        requested_country = str(request.get("iso3") or "").strip().upper()
        if not requested_country:
            requested_country = _unique_catalog_country_for_reference_system(system) or ""
        if not requested_country:
            # Dataset identification may deliberately return no single country
            # for a global column (for example, ISO/geoBoundaries Admin0
            # codes). Resolve those exact graph aliases in one batched scan;
            # never invent a USA scope in the transport layer.
            value = str(request.get("value") or "").strip()
            unscoped_alias_groups.setdefault(system, []).append((index, request, value))
            continue
        level = admin_level_name(request.get("target_admin_level") or "admin_2")
        iso3 = requested_country
        artifact = _first_crosswalk_artifact(
            source_family=system,
            target_admin_level=level,
            iso3=iso3,
            relationship_vintage=request.get("relationship_vintage"),
        )
        if not artifact:
            results[index] = resolve_reference(**request)
            continue
        key = (
            system,
            level,
            iso3,
            str(_catalog_crosswalk_path(artifact) or ""),
            request.get("min_share"),
            int(request.get("limit") or 10),
        )
        groups.setdefault(key, []).append((index, request))

    if external_groups:
        # External bridges are already partitioned by system/release/country.
        # Query all requested identifiers in a group together instead of
        # reopening the same bridge partition once per conversion row.
        for (system, country, source_release, internal_release, limit), members in external_groups.items():
            adapter = get_external_adapter(system)
            requested = list(dict.fromkeys(text for _index, _request, text in members if text))
            by_value = lookup_external_edges_batch(
                system,
                requested,
                source_release=source_release or None,
                internal_release=internal_release or None,
                country_scope=country or None,
            )
            if adapter is None or by_value is None:
                for index, request, _text in members:
                    results[index] = resolve_reference(**request)
                continue
            for index, request, text in members:
                if not text:
                    results[index] = resolve_reference(**request)
                    continue
                payload = _external_reference_payload(
                    adapter, request.get("value"), text, by_value.get(text, []), limit=limit,
                )
                if system == GERS_SYSTEM:
                    payload.setdefault("admin_level", payload.get("source_level"))
                    payload.setdefault("overture_subtype", payload.get("external_subtype"))
                    payload.setdefault("overture_release", payload.get("source_release"))
                    payload.setdefault("spine_vintage", payload.get("internal_release"))
                results[index] = _clean_json(payload)

    if census_candidates:
        from .admin_spine_query import cached_shallow_identity_rows, load_rows_by_loc_ids

        candidate_ids = list(dict.fromkeys(
            loc_id for _, _, _, loc_id, _ in census_candidates if loc_id
        ))
        maximum_level = max(
            (int(str(level).replace("admin_", "")) for _, _, _, loc_id, level in census_candidates if loc_id and level),
            default=0,
        )
        cached = (
            cached_shallow_identity_rows(
                "USA", candidate_ids, maximum_level=maximum_level, columns=["admin_level"]
            )
            if maximum_level <= 2
            else None
        )
        identity_rows = cached if cached is not None else load_rows_by_loc_ids(
            "USA", candidate_ids, columns=["admin_level"]
        )
        matched_ids = {
            str(value)
            for value in identity_rows.get("loc_id", [])
            if value
        }
        for index, request, value, loc_id, level in census_candidates:
            if loc_id and loc_id in matched_ids:
                results[index] = {
                    "ok": True,
                    "from_system": "us_census_geoid",
                    "input": request.get("value"),
                    "normalized_input": value,
                    "resolved_loc_id": loc_id,
                    "resolved_family": "admin_boundary",
                    "admin_level": level,
                    "match_type": "admin_spine_exact",
                    "source_vintage": "census_2020",
                }
            else:
                results[index] = {
                    "ok": False,
                    "from_system": "us_census_geoid",
                    "input": request.get("value"),
                    "normalized_input": value,
                    "error": {
                        "code": "admin_spine_match_not_found" if loc_id else "invalid_census_geoid",
                        "message": "identifier did not match the selected country admin spine" if loc_id else "expected a 2, 5, 11, 12, or 15 digit US Census GEOID",
                    },
                }

    if global_admin0_candidates:
        from .global_admin0_query import load_global_admin0_identities

        values = list(dict.fromkeys(
            value.upper() for _, _, value in global_admin0_candidates if value
        ))
        identities = load_global_admin0_identities(values)
        if identities is None:
            # A legacy/local layout without the compact identity index retains
            # the established graph fallback. Production published layouts are
            # required to expose the index and never enter this branch.
            for index, request, value in global_admin0_candidates:
                unscoped_alias_groups.setdefault("geoboundaries.code", []).append(
                    (index, request, value)
                )
        else:
            for index, request, value in global_admin0_candidates:
                normalized = value.upper()
                results[index] = _clean_json(
                    _global_admin0_identity_result(value, identities.get(normalized))
                )

    if native_admin_groups:
        from .admin_spine_query import load_route_rows_by_loc_ids
        from .reference_graph import identify_aliases

        for country, members in native_admin_groups.items():
            values = list(dict.fromkeys(value for _, _, value in members if value))
            aliases = identify_aliases(
                values,
                iso3=country or None,
                reference_system="admin.native_id",
                limit=max(500, len(values) * 10),
            )
            by_value: dict[str, list[dict[str, Any]]] = {}
            for alias in aliases:
                if str(alias.get("reference_system") or "").lower() != "admin.native_id":
                    continue
                by_value.setdefault(str(alias.get("external_id") or ""), []).append(alias)
            candidate_ids = list(dict.fromkeys(
                str(alias.get("loc_id") or "")
                for matches in by_value.values()
                for alias in matches
                if alias.get("loc_id")
            ))
            route_frame = load_route_rows_by_loc_ids(country, candidate_ids)
            identity_by_id = {
                str(row.get("loc_id") or ""): row
                for row in route_frame.to_dict("records")
                if row.get("loc_id")
            }
            for index, request, value in members:
                expected_level = int(str(admin_level_name(
                    request.get("target_admin_level") or "admin_2"
                )).removeprefix("admin_"))
                matches = [
                    alias for alias in by_value.get(value, [])
                    if str(alias.get("loc_id") or "") in identity_by_id
                    and int(identity_by_id[str(alias.get("loc_id") or "")]["admin_level"]) == expected_level
                ]
                if len(matches) == 1:
                    loc_id = str(matches[0].get("loc_id") or "")
                    node = identity_by_id[loc_id]
                    results[index] = {
                        "ok": True,
                        "from_system": "admin.native_id",
                        "input": request.get("value"),
                        "normalized_input": value,
                        "resolved_loc_id": loc_id,
                        "resolved_family": "admin_boundary",
                        "admin_level": admin_level_name(node.get("admin_level")),
                        "match_type": "admin_spine_exact",
                    }
                else:
                    results[index] = {
                        "ok": False,
                        "from_system": "admin.native_id",
                        "input": request.get("value"),
                        "normalized_input": value,
                        "error": {
                            "code": "admin_spine_match_ambiguous" if len(matches) > 1 else "admin_spine_match_not_found",
                            "message": "identifier matched more than one admin-spine identity" if len(matches) > 1 else "identifier did not match the selected country admin spine",
                        },
                    }

    if unscoped_alias_groups:
        from .reference_graph import identify_aliases, identities

        for system, members in unscoped_alias_groups.items():
            values = list(dict.fromkeys(value for _, _, value in members if value))
            aliases = identify_aliases(
                values,
                iso3=None,
                reference_system=system,
                limit=max(500, len(values) * 10),
            )
            by_value: dict[str, list[dict[str, Any]]] = {}
            for alias in aliases:
                if str(alias.get("reference_system") or "").lower() != system:
                    continue
                by_value.setdefault(str(alias.get("external_id") or ""), []).append(alias)
            candidate_ids = list(dict.fromkeys(
                str(alias.get("loc_id") or "")
                for matches in by_value.values()
                for alias in matches
                if alias.get("loc_id")
            ))
            identity_by_id = {
                str(row.get("loc_id") or ""): row
                for row in identities(candidate_ids)
                if isinstance(row, dict) and row.get("loc_id")
            }
            for index, request, value in members:
                matches = [
                    alias for alias in by_value.get(value, [])
                    if str(alias.get("loc_id") or "") in identity_by_id
                ]
                loc_ids = list(dict.fromkeys(str(alias.get("loc_id") or "") for alias in matches))
                if len(loc_ids) == 1:
                    loc_id = loc_ids[0]
                    node = identity_by_id[loc_id]
                    results[index] = {
                        "ok": True,
                        "from_system": system,
                        "input": request.get("value"),
                        "normalized_input": value,
                        "resolved_loc_id": loc_id,
                        "resolved_family": node.get("family") or classify_loc_id_family(loc_id),
                        "admin_level": admin_level_name(node.get("admin_level")),
                        "match_type": "reference_graph_alias",
                    }
                else:
                    results[index] = {
                        "ok": False,
                        "from_system": system,
                        "input": request.get("value"),
                        "normalized_input": value,
                        "error": {
                            "code": "reference_alias_ambiguous" if len(loc_ids) > 1 else "reference_alias_not_found",
                            "message": "identifier matched more than one maintained identity" if len(loc_ids) > 1 else "identifier did not match the maintained identity graph",
                        },
                    }
    for (system, level, iso3, artifact_path, min_share, limit), members in groups.items():
        normalized = [
            _normalize_source_loc_id(system, str(request.get("value") or "").strip(), iso3)
            for _, request in members
        ]
        batched = resolve_family_ids_to_admin(
            normalized,
            source_family=system,
            target_admin_level=level,
            iso3=iso3,
            crosswalk_path=Path(artifact_path),
            min_source_area_share=min_share,
            limit=limit,
        )
        for (index, request), source_loc_id in zip(members, normalized):
            crosswalk_result = batched.get(source_loc_id) or {}
            primary = crosswalk_result.get("primary_match") or {}
            results[index] = _clean_json({
                "ok": bool(crosswalk_result.get("ok")),
                "from_system": system,
                "input": request.get("value"),
                "normalized_input": source_loc_id,
                "resolved_loc_id": primary.get("match_loc_id"),
                "resolved_family": "admin_boundary" if primary.get("match_loc_id") else None,
                "match_type": "crosswalk_overlap",
                "crosswalk": {
                    "artifact_path": str(Path(artifact_path).relative_to(DATA_ROOT)).replace("\\", "/") if artifact_path else None,
                    "relationship_vintage": (primary or {}).get("relationship_vintage"),
                    "target_admin_level": level,
                },
                "primary_match": primary,
                "matches": crosswalk_result.get("overlaps") or [],
                "match_count": crosswalk_result.get("overlap_count") or 0,
                "error": crosswalk_result.get("error"),
            })
    return [result or {"ok": False, "error": "batch resolution produced no result"} for result in results]


def _external_edge_reference(system: str, edge: Any) -> dict[str, Any]:
    return {
        "system": system,
        "value": edge.external_id,
        "name": edge.external_name,
        "role": edge.relationship_type,
        "is_identity_equivalence": edge.is_equivalence,
        "is_primary": edge.is_primary,
        "source_release": edge.source_release,
        "internal_release": edge.internal_release,
        "country": edge.country,
        "source_level": edge.source_level,
        "external_subtype": edge.external_subtype,
        "edge_id": edge.edge_id,
        "partition_id": edge.partition_id,
        "bridge_generation_id": edge.bridge_generation_id,
        "edge_content_hash": edge.edge_content_hash,
        "identity_confidence": edge.identity_confidence,
        "geometry_confidence": edge.geometry_confidence,
    }


def loc_id_references(
    loc_id: str,
    *,
    systems: list[str] | None = None,
    iso3: str | None = None,
    target_admin_level: int | str | None = None,
    min_share: float | None = None,
    limit_per_system: int | None = 10,
    source_release: str | None = None,
    internal_release: str | None = None,
) -> dict[str, Any]:
    """Return known references that point at a ``loc_id``."""
    resolution = resolve_loc_id_input(loc_id)
    if not resolution.get("ok"):
        return _public_alias_error(resolution)
    canonical = str(resolution.get("loc_id") or canonicalize_loc_id(loc_id))
    family = classify_loc_id_family(canonical)
    try:
        from .reference_graph import identity as graph_identity

        family = (graph_identity(canonical) or {}).get("family") or family
    except Exception:
        pass
    requested = {_normalize_system(system) for system in systems or [] if str(system or "").strip()}
    references: list[dict[str, Any]] = [
        {"system": LOC_ID_SYSTEM, "value": canonical, "role": "reserve", "family": family},
    ]
    geometry_id = translate_loc_id_to_geometry_id(canonical)
    local_id = translate_geometry_id_to_local_id(canonical)
    if geometry_id and geometry_id != canonical:
        references.append({"system": "admin_geometry", "value": geometry_id, "role": "geometry_join_id"})
    for legacy_geometry_id in legacy_geometry_ids_for_local_id(canonical):
        references.append({"system": "legacy_admin_geometry", "value": legacy_geometry_id, "role": "accepted_storage_alias"})
    if local_id and local_id != canonical:
        references.append({"system": "admin_local", "value": local_id, "role": "preferred_local_id"})

    inferred_level = infer_admin_level_from_loc_id(canonical)
    level = admin_level_name(target_admin_level if target_admin_level not in (None, "") else inferred_level)
    # The reserve id is authoritative for its own country. `iso3` retains a
    # historical USA default for crosswalk calls and must not filter a CAN/BRA
    # reverse external-reference lookup out of existence.
    loc_country = canonical.split("-", 1)[0] if "-" in canonical else ""
    country = str(loc_country or iso3 or "").strip().upper()
    for adapter in admitted_external_adapters():
        if requested and adapter.system not in requested:
            continue
        for edge in lookup_loc_id_edges(
            adapter.system,
            canonical,
            country_scope=country or None,
            source_release=source_release,
            internal_release=internal_release,
            limit=limit_per_system,
        ):
            references.append(_external_edge_reference(adapter.system, edge))
    if family in {"admin_0", "admin_local", "admin_geometry"} or inferred_level is not None:
        for artifact in _crosswalk_artifacts(target_admin_level=level, iso3=country or None):
            source = str(artifact.get("source_family") or "").strip()
            if get_external_adapter(source):
                continue
            source_names = _crosswalk_source_names(artifact)
            requested_names = sorted(requested & source_names)
            if requested and not requested_names:
                continue
            output_system = requested_names[0] if requested_names else source
            result = resolve_admin_to_family(
                canonical,
                source_family=source,
                target_admin_level=level,
                iso3=country or "USA",
                crosswalk_path=_catalog_crosswalk_path(artifact),
                min_target_area_share=min_share,
                limit=limit_per_system,
            )
            for overlap in result.get("overlaps") or []:
                source_ref = overlap.get("source") or {}
                references.append({
                    "system": output_system,
                    "crosswalk_source_system": source,
                    "value": source_ref.get("loc_id"),
                    "name": source_ref.get("name"),
                    "role": "crosswalk_overlap",
                    "relationship_vintage": overlap.get("relationship_vintage"),
                    "match_share": overlap.get("match_share"),
                    "match_rank": overlap.get("match_rank"),
                    "is_primary": overlap.get("is_primary"),
                })
    try:
        from .reference_graph import aliases_for_loc_id, relationships_for_loc_id

        for alias in aliases_for_loc_id(canonical, limit=limit_per_system or 10):
            system = str(alias.get("reference_system") or "").strip()
            if get_external_adapter(system):
                continue
            if requested and system not in requested:
                continue
            references.append({
                "system": system,
                "value": alias.get("external_id"),
                "role": alias.get("alias_type") or "reference_graph_alias",
                "source_system": alias.get("source_system"),
                "source_vintage": alias.get("source_vintage"),
            })
        graph_limit = max(1, min(int(limit_per_system or 10) * 10, 100))
        for edge in relationships_for_loc_id(canonical, limit=graph_limit):
            outgoing = str(edge.get("source_loc_id") or "") == canonical
            system = str(edge.get("target_family") if outgoing else edge.get("source_family") or "").strip()
            if get_external_adapter(system):
                continue
            if requested and system not in requested:
                continue
            references.append({
                "system": system,
                "value": edge.get("target_loc_id") if outgoing else edge.get("source_loc_id"),
                "name": edge.get("target_name") if outgoing else edge.get("source_name"),
                "role": edge.get("relationship_type"),
                "relationship_id": edge.get("relationship_id"),
                "direction": "outgoing" if outgoing else "incoming",
                "relationship_subtype": edge.get("relationship_subtype"),
                "relationship_vintage": edge.get("relationship_vintage"),
                "valid_from": edge.get("valid_from"),
                "valid_to": edge.get("valid_to"),
                "source_area_share": edge.get("source_area_share"),
                "target_area_share": edge.get("target_area_share"),
                "is_primary": edge.get("is_primary"),
                "method": edge.get("method"),
                "authority": edge.get("authority"),
            })
    except Exception:
        pass
    if requested:
        references = [ref for ref in references if ref.get("system") in requested or ref.get("system") == LOC_ID_SYSTEM]
    return _clean_json(_attach_public_alias_resolution(
        {"ok": bool(canonical), "loc_id": canonical, "family": family, "references": references, "reference_count": len(references)},
        resolution,
    ))


def convert_reference(
    *,
    from_system: str,
    value: str,
    to_system: str = LOC_ID_SYSTEM,
    iso3: str = "USA",
    target_admin_level: int | str | None = "admin_2",
    relationship_vintage: str | None = None,
    min_share: float | None = None,
    limit: int | None = 10,
    source_release: str | None = None,
    internal_release: str | None = None,
    country_hint: str | None = None,
    admin_level_hint: int | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Convert a value from one reference system to another through ``loc_id``."""
    source = _normalize_system(from_system)
    target = _normalize_system(to_system)
    requested_source = str(from_system or "").strip().lower().replace("-", "_").replace(" ", "_")
    if requested_source in PUBLIC_ZIP_ALIASES and target in {LOC_ID_SYSTEM, "admin_local", "admin_geometry"}:
        resolved = resolve_reference(
            from_system=US_ZCTA_GEOID_SYSTEM,
            value=value,
            iso3=iso3,
            limit=limit,
        )
        loc_id = resolved.get("resolved_loc_id")
        if not loc_id:
            return _clean_json({"ok": False, "from": resolved, "to_system": target, "error": "source reference did not resolve to loc_id"})
        return _clean_json({"ok": True, "from": resolved, "to_system": target, "results": [{"system": target, "value": loc_id}]})
    target_adapter = get_external_adapter(target)
    if source in {LOC_ID_SYSTEM, "admin_local", "admin_geometry"} and target_adapter:
        # A typed external bridge is already a loc_id <-> external-id index.
        # Do not scan the general crosswalk catalog or reference graph for this
        # explicit reverse lookup: besides adding no evidence, that work can
        # turn a millisecond Parquet predicate into a hosted timeout.
        canonical = canonicalize_loc_id(value)
        loc_country = canonical.split("-", 1)[0] if "-" in canonical else ""
        edges = lookup_loc_id_edges(
            target_adapter.system,
            canonical,
            country_scope=loc_country or None,
            source_release=source_release,
            internal_release=internal_release,
            limit=limit,
        )
        results = [_external_edge_reference(target_adapter.system, edge) for edge in edges]
        if results:
            return _clean_json({
                "ok": True,
                "from": {
                    "ok": True,
                    "from_system": source,
                    "input": value,
                    "resolved_loc_id": canonical,
                    "match_type": "loc_id_bridge_lookup",
                },
                "to_system": target_adapter.system,
                "results": results,
                "loc_id": canonical,
            })
        return _clean_json({
            "ok": False,
            "from_system": source,
            "input": value,
            "to_system": target_adapter.system,
            "results": [],
            "loc_id": canonical,
            "error": {
                "code": "external_reference_not_found",
                "message": f"no {target_adapter.system} reference is published for that loc_id",
            },
        })
    direct_record, direct_results = _direct_crosswalk_matches(
        from_system=from_system,
        value=value,
        to_system=target,
        iso3=iso3,
        limit=limit or 10,
    )
    if direct_record and direct_results:
        return _clean_json({
            "ok": True,
            "from_system": _normalize_system(from_system),
            "input": value,
            "to_system": target,
            "loc_id": direct_results[0].get("input_loc_id"),
            "results": direct_results,
            "crosswalk": {
                "crosswalk_id": direct_record.get("crosswalk_id"),
                "relationship_vintage": direct_record.get("relationship_vintage"),
                "cardinality": direct_record.get("cardinality"),
                "lineage": direct_record.get("source_material_identity"),
            },
        })
    resolved = resolve_reference(
        from_system=from_system,
        value=value,
        iso3=iso3,
        target_admin_level=target_admin_level,
        relationship_vintage=relationship_vintage,
        min_share=min_share,
        limit=limit,
        source_release=source_release,
        internal_release=internal_release,
        country_hint=country_hint,
        admin_level_hint=admin_level_hint,
        as_of=as_of,
    )
    loc_id = resolved.get("resolved_loc_id")
    if not loc_id:
        return _clean_json({"ok": False, "from": resolved, "to_system": target, "error": "source reference did not resolve to loc_id"})
    if target in {LOC_ID_SYSTEM, "admin_local", "admin_geometry"}:
        return _clean_json({"ok": True, "from": resolved, "to_system": target, "results": [{"system": target, "value": loc_id}]})
    references = loc_id_references(
        loc_id,
        systems=[target],
        iso3=iso3,
        target_admin_level=target_admin_level,
        min_share=min_share,
        limit_per_system=limit,
        source_release=source_release,
        internal_release=internal_release,
    )
    results = [ref for ref in references.get("references") or [] if ref.get("system") == target]
    if not results:
        return _clean_json({
            "ok": False,
            "from": resolved,
            "to_system": target,
            "results": [],
            "loc_id": loc_id,
            "error": {
                "code": "unsupported_target_system",
                "message": f"no references found from loc_id to {target}",
            },
        })
    return _clean_json({
        "ok": True,
        "from": resolved,
        "to_system": target,
        "results": results,
        "loc_id": loc_id,
    })


def convert_references_batch(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert many references with grouped source and target crosswalk scans."""
    results: list[dict[str, Any] | None] = [None] * len(requests)
    source_requests: list[dict[str, Any]] = []
    source_indexes: list[int] = []
    direct_groups: dict[tuple[str, str, str, int], list[tuple[int, dict[str, Any]]]] = {}

    catalog_by_country: dict[str, list[dict[str, Any]]] = {}
    for index, request in enumerate(requests):
        from_system = _normalize_system(request.get("from_system"))
        target = _normalize_system(request.get("to_system") or LOC_ID_SYSTEM)
        requested_source = str(request.get("from_system") or "").strip().lower().replace("-", "_").replace(" ", "_")
        if requested_source in PUBLIC_ZIP_ALIASES and target in {LOC_ID_SYSTEM, "admin_local", "admin_geometry"}:
            results[index] = convert_reference(**request)
            continue
        iso3 = str(request.get("iso3") or "USA").strip().upper()
        if iso3 not in catalog_by_country:
            catalog_by_country[iso3] = _catalog_crosswalks(country_scope=iso3)
        records = catalog_by_country[iso3]
        has_direct_pair = any(
            record.get("execution_strategy") in {"direct_relationship_artifact", "measured_relationship_artifact"}
            and (
                (
                    str(record.get("source_system") or "") == from_system
                    and str(record.get("target_system") or "") == target
                )
                or (
                    str(record.get("target_system") or "") == from_system
                    and str(record.get("source_system") or "") == target
                )
            )
            for record in records
        )
        if has_direct_pair:
            key = (from_system, target, iso3, int(request.get("limit") or 10))
            direct_groups.setdefault(key, []).append((index, request))
            continue
        source_indexes.append(index)
        source_requests.append({key: value for key, value in request.items() if key != "to_system"})

    for (from_system, target, iso3, limit), members in direct_groups.items():
        direct = _direct_crosswalk_matches_batch(
            from_system=from_system,
            values=[str(request.get("value") or "") for _index, request in members],
            to_system=target,
            iso3=iso3,
            limit=limit,
        )
        for index, request in members:
            value = str(request.get("value") or "").strip()
            match = direct.get(value)
            if match:
                record, direct_results = match
                results[index] = _clean_json({
                    "ok": True,
                    "from_system": from_system,
                    "input": request.get("value"),
                    "to_system": target,
                    "loc_id": direct_results[0].get("input_loc_id"),
                    "results": direct_results,
                    "crosswalk": {
                        "crosswalk_id": record.get("crosswalk_id"),
                        "relationship_vintage": record.get("relationship_vintage"),
                        "cardinality": record.get("cardinality"),
                        "lineage": record.get("source_material_identity"),
                    },
                })
                continue
            source_indexes.append(index)
            source_requests.append({key: value for key, value in request.items() if key != "to_system"})

    resolved_sources = resolve_references_batch(source_requests) if source_requests else []
    reverse_groups: dict[tuple[Any, ...], list[tuple[int, dict[str, Any], dict[str, Any], str]]] = {}
    external_reverse_groups: dict[tuple[Any, ...], list[tuple[int, dict[str, Any], dict[str, Any], str]]] = {}
    for index, request, resolved in zip(source_indexes, (requests[i] for i in source_indexes), resolved_sources):
        target = _normalize_system(request.get("to_system") or LOC_ID_SYSTEM)
        loc_id = str(resolved.get("resolved_loc_id") or "").strip()
        if not loc_id:
            results[index] = _clean_json({
                "ok": False,
                "from": resolved,
                "to_system": target,
                "error": "source reference did not resolve to loc_id",
            })
            continue
        if target in {LOC_ID_SYSTEM, "admin_local", "admin_geometry"}:
            results[index] = _clean_json({
                "ok": True,
                "from": resolved,
                "to_system": target,
                "results": [{"system": target, "value": loc_id}],
            })
            continue
        if get_external_adapter(target):
            country = loc_id.split("-", 1)[0] if "-" in loc_id else str(request.get("iso3") or "").strip().upper()
            key = (
                target,
                country,
                str(request.get("source_release") or "").strip(),
                str(request.get("internal_release") or "").strip(),
                int(request.get("limit") or 10),
            )
            external_reverse_groups.setdefault(key, []).append((index, request, resolved, loc_id))
            continue
        level = admin_level_name(request.get("target_admin_level") or "admin_2")
        iso3 = str(request.get("iso3") or "USA").strip().upper()
        artifact = _first_crosswalk_artifact(
            source_family=target,
            target_admin_level=level,
            iso3=iso3,
            relationship_vintage=request.get("relationship_vintage"),
        )
        if not artifact:
            references = loc_id_references(
                loc_id,
                systems=[target],
                iso3=iso3,
                target_admin_level=level,
                min_share=request.get("min_share"),
                limit_per_system=request.get("limit"),
                source_release=request.get("source_release"),
                internal_release=request.get("internal_release"),
            )
            matches = [ref for ref in references.get("references") or [] if ref.get("system") == target]
            results[index] = _conversion_result_from_references(resolved, target, loc_id, matches)
            continue
        key = (
            target,
            level,
            iso3,
            str(_catalog_crosswalk_path(artifact) or ""),
            request.get("min_share"),
            int(request.get("limit") or 10),
        )
        reverse_groups.setdefault(key, []).append((index, request, resolved, loc_id))

    for (target, country, source_release, internal_release, limit), members in external_reverse_groups.items():
        by_loc_id = lookup_loc_id_edges_batch(
            target,
            [loc_id for _index, _request, _resolved, loc_id in members],
            country_scope=country or None,
            source_release=source_release or None,
            internal_release=internal_release or None,
            limit=limit,
        )
        if by_loc_id is None:
            for index, request, _resolved, _loc_id in members:
                results[index] = convert_reference(**request)
            continue
        for index, _request, resolved, loc_id in members:
            references = [
                _external_edge_reference(target, edge)
                for edge in by_loc_id.get(loc_id, [])
            ]
            results[index] = _conversion_result_from_references(resolved, target, loc_id, references)

    for (target, level, iso3, artifact_path, min_share, limit), members in reverse_groups.items():
        loc_ids = [loc_id for _index, _request, _resolved, loc_id in members]
        batched = resolve_admin_ids_to_family(
            loc_ids,
            source_family=target,
            target_admin_level=level,
            iso3=iso3,
            crosswalk_path=Path(artifact_path),
            min_target_area_share=min_share,
            limit=limit,
        )
        for index, _request, resolved, loc_id in members:
            references = []
            for overlap in (batched.get(loc_id) or {}).get("overlaps") or []:
                source_ref = overlap.get("source") or {}
                references.append({
                    "system": target,
                    "crosswalk_source_system": target,
                    "value": source_ref.get("loc_id"),
                    "name": source_ref.get("name"),
                    "role": "crosswalk_overlap",
                    "relationship_vintage": overlap.get("relationship_vintage"),
                    "match_share": overlap.get("match_share"),
                    "match_rank": overlap.get("match_rank"),
                    "is_primary": overlap.get("is_primary"),
                })
            results[index] = _conversion_result_from_references(resolved, target, loc_id, references)
    return [result or {"ok": False, "error": "batch conversion produced no result"} for result in results]


def _conversion_result_from_references(
    resolved: dict[str, Any], target: str, loc_id: str, references: list[dict[str, Any]],
) -> dict[str, Any]:
    if not references:
        return _clean_json({
            "ok": False,
            "from": resolved,
            "to_system": target,
            "results": [],
            "loc_id": loc_id,
            "error": {
                "code": "unsupported_target_system",
                "message": f"no references found from loc_id to {target}",
            },
        })
    return _clean_json({
        "ok": True,
        "from": resolved,
        "to_system": target,
        "results": references,
        "loc_id": loc_id,
    })


def _geometry_lineage(record: dict[str, Any]) -> dict[str, Any]:
    """Return bounded source/material lineage without changing legacy fields."""
    explicit = record.get("lineage")
    if isinstance(explicit, dict) and explicit:
        return explicit
    lineage = {
        "material_id": record.get("material_id") or record.get("bank_id"),
        "bank_id": record.get("bank_id"),
        "release_id": record.get("release_id"),
        "source_id": record.get("source_id"),
        "source_ids": record.get("source_ids"),
        "source_system": record.get("source_system"),
        "source_vintage": record.get("source_vintage") or record.get("source_release"),
        "geometry_source": record.get("geometry_source"),
        "geometry_vintage": record.get("geometry_vintage"),
    }
    return {key: value for key, value in lineage.items() if value not in (None, "")}


def _shape_geometry_reference(
    loc_id: str,
    feature: dict[str, Any] | None,
    *,
    include_polygon: bool = False,
    include_info: bool = True,
) -> dict[str, Any]:
    canonical = canonicalize_loc_id(loc_id)
    if not feature:
        return {"ok": False, "loc_id": canonical, "has_shape": False, "error": "no geometry found"}
    props = feature.get("properties") or {}
    family = _reference_family(canonical, admin_level=props.get("admin_level"))
    payload = {
        "ok": True,
        "has_shape": True,
        "loc_id": props.get("local_loc_id") or canonical,
        "name": props.get("name"),
        "family": family,
        "admin_level": props.get("admin_level"),
        "centroid": {"lon": props.get("centroid_lon"), "lat": props.get("centroid_lat")},
        "bbox": [
            props.get("bbox_min_lon"),
            props.get("bbox_min_lat"),
            props.get("bbox_max_lon"),
            props.get("bbox_max_lat"),
        ],
        "valid_from": _first_populated(props, "valid_from", "valid_from_date"),
        "valid_to": _first_populated(props, "valid_to", "valid_to_date"),
        "geometry_vintage": props.get("geometry_vintage"),
        "bank_id": props.get("bank_id"),
        "lineage": _geometry_lineage(props),
    }
    if include_info:
        payload["info"] = get_location_info(canonical)
    if include_polygon:
        payload["geometry"] = feature.get("geometry")
    return _clean_json(payload)


def _metadata_geometry_reference(
    loc_id: str,
    row: dict[str, Any] | None,
    *,
    include_info: bool = True,
) -> dict[str, Any]:
    canonical = canonicalize_loc_id(loc_id)
    if not row:
        return {"ok": False, "loc_id": canonical, "has_shape": False, "error": "no geometry found"}
    family = _reference_family(canonical, admin_level=row.get("admin_level"))
    has_shape = bool(row.get("has_polygon", True))
    payload = {
        "ok": has_shape,
        "has_shape": has_shape,
        "loc_id": row.get("loc_id") or row.get("source_loc_id") or canonical,
        "name": row.get("name"),
        "family": family,
        "admin_level": row.get("admin_level"),
        "centroid": {"lon": row.get("centroid_lon"), "lat": row.get("centroid_lat")},
        "bbox": [
            row.get("bbox_min_lon"),
            row.get("bbox_min_lat"),
            row.get("bbox_max_lon"),
            row.get("bbox_max_lat"),
        ],
        "valid_from": row.get("valid_from"),
        "valid_to": row.get("valid_to"),
        "geometry_vintage": row.get("geometry_vintage"),
        "bank_id": row.get("bank_id"),
        "lineage": _geometry_lineage(row),
    }
    if include_info:
        payload["info"] = get_location_info(canonical)
    return _clean_json(payload)


def get_geometry_references(
    loc_ids: list[str],
    *,
    include_polygon: bool = False,
    include_info: bool = True,
) -> dict[str, Any]:
    """Return geometry metadata for one or more loc_ids using one geometry fetch pipeline."""
    # Current administrative geometry is already keyed by the canonical loc_id
    # in the geometry bank.  Check that exact key first so a normal geometry
    # request does not open the reference graph merely to prove that its input
    # is unchanged.  Inputs that miss the exact bank still go through the graph
    # resolver, which preserves preferred-public-loc_id aliases.
    requested_ids = [canonicalize_loc_id(str(loc_id)) for loc_id in loc_ids if str(loc_id).strip()]
    retired_public_ids = {
        value for value in requested_ids
        if (
            value.startswith("USA-Z-") and len(value) == 11 and value[6:].isdigit()
        ) or (
            value.startswith("USA-TRIBAL-") and len(value) == 15 and value[11:].isdigit()
        )
    }
    direct_features: list[dict[str, Any]] = []
    if include_polygon:
        direct_features = (get_selection_geometries(requested_ids) or {}).get("features") or []
        direct_rows = []
    else:
        direct_rows = get_selection_geometry_metadata(requested_ids)
    direct_ids = {
        canonicalize_loc_id(str(row.get("loc_id") or row.get("source_loc_id") or ""))
        for row in direct_rows
        if (row.get("loc_id") or row.get("source_loc_id"))
        and row.get("admin_level") is not None
        and _reference_family(
            canonicalize_loc_id(str(row.get("loc_id") or row.get("source_loc_id") or "")),
            admin_level=row.get("admin_level"),
        ) in {"admin_0", "admin_local", "admin_geometry"}
    }
    if include_polygon:
        direct_ids = {
            canonicalize_loc_id(str((feature.get("properties") or {}).get("local_loc_id") or (feature.get("properties") or {}).get("loc_id") or ""))
            for feature in direct_features
            if (feature.get("properties") or {}).get("local_loc_id") or (feature.get("properties") or {}).get("loc_id")
        }
    else:
        # An explicit sidechain bank is just as authoritative for its own IDs
        # as an admin layout. Do not query the graph once per ZCTA/zone/etc.
        direct_ids.update({
            canonicalize_loc_id(str(row.get("loc_id") or row.get("source_loc_id") or ""))
            for row in direct_rows if row.get("loc_id") or row.get("source_loc_id")
        })
    pending_resolution_ids = [
        requested for requested in requested_ids
        if requested not in direct_ids or requested in retired_public_ids
    ]
    pending_resolutions = iter(resolve_loc_id_inputs(pending_resolution_ids))
    resolutions = [
        {
            "ok": True,
            "status": "unchanged",
            "requested_loc_id": requested,
            "loc_id": requested,
            "resolved_from_public_alias": False,
        }
        if requested in direct_ids and requested not in retired_public_ids else next(pending_resolutions)
        for requested in requested_ids
    ]
    canonical_ids = [str(item.get("loc_id")) for item in resolutions if item.get("ok") and item.get("loc_id")]
    if not include_polygon:
        fetched_ids = {
            canonicalize_loc_id(str(row.get("loc_id") or row.get("source_loc_id") or ""))
            for row in direct_rows
            if row.get("loc_id") or row.get("source_loc_id")
        }
        attempted_ids = set(requested_ids)
        missing_ids = [
            loc_id
            for loc_id in canonical_ids
            if canonicalize_loc_id(loc_id) not in fetched_ids
            and canonicalize_loc_id(loc_id) not in attempted_ids
        ]
        rows = [*direct_rows, *(get_selection_geometry_metadata(missing_ids) if missing_ids else [])]
        by_loc_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_loc_id = row.get("loc_id") or row.get("source_loc_id")
            if row_loc_id:
                by_loc_id[canonicalize_loc_id(str(row_loc_id))] = row
        results = []
        for resolution in resolutions:
            if not resolution.get("ok"):
                results.append(_public_alias_error(resolution, shape=True))
                continue
            canonical = str(resolution.get("loc_id"))
            row = by_loc_id.get(canonical)
            result = _metadata_geometry_reference(canonical, row, include_info=include_info)
            result = _attach_geometry_supersession(result, canonical, row)
            results.append(_attach_public_alias_resolution(result, resolution))
        available = sum(1 for result in results if result.get("has_shape"))
        return _clean_json(
            {
                "ok": bool(results),
                "requested": len(resolutions),
                "available": available,
                "missing": len(resolutions) - available,
                "results": results,
            }
        )

    missing_canonical_ids = [loc_id for loc_id in canonical_ids if canonicalize_loc_id(loc_id) not in direct_ids]
    alias_features = (
        (get_selection_geometries(missing_canonical_ids) or {}).get("features") or []
        if missing_canonical_ids else []
    )
    features = [*direct_features, *alias_features]
    by_loc_id: dict[str, dict[str, Any]] = {}
    for feature in features:
        props = feature.get("properties") or {}
        feature_loc_id = props.get("local_loc_id") or props.get("loc_id")
        if feature_loc_id:
            by_loc_id[canonicalize_loc_id(str(feature_loc_id))] = feature
    results = []
    for resolution in resolutions:
        if not resolution.get("ok"):
            results.append(_public_alias_error(resolution, shape=True))
            continue
        canonical = str(resolution.get("loc_id"))
        feature = by_loc_id.get(canonical)
        result = _shape_geometry_reference(canonical, feature, include_polygon=include_polygon, include_info=include_info)
        props = (feature or {}).get("properties") if isinstance(feature, dict) else None
        result = _attach_geometry_supersession(result, canonical, props)
        results.append(_attach_public_alias_resolution(result, resolution))
    available = sum(1 for result in results if result.get("has_shape"))
    return _clean_json(
        {
            "ok": bool(results),
            "requested": len(resolutions),
            "available": available,
            "missing": len(resolutions) - available,
            "results": results,
        }
    )


def get_geometry_availability(loc_ids: list[str]) -> dict[str, Any]:
    """Return a lightweight shape-availability preflight for one or more loc_ids."""
    requested_ids = [canonicalize_loc_id(str(loc_id)) for loc_id in loc_ids if str(loc_id).strip()]
    retired_public_ids = {
        value for value in requested_ids
        if (
            value.startswith("USA-Z-") and len(value) == 11 and value[6:].isdigit()
        ) or (
            value.startswith("USA-TRIBAL-") and len(value) == 15 and value[11:].isdigit()
        )
    }
    rows = get_selection_geometry_metadata(requested_ids)
    direct_ids = {
        canonicalize_loc_id(str(row.get("loc_id") or row.get("source_loc_id") or ""))
        for row in rows if row.get("loc_id") or row.get("source_loc_id")
    }
    pending_resolution_ids = [
        requested for requested in requested_ids
        if requested not in direct_ids or requested in retired_public_ids
    ]
    pending_resolutions = iter(resolve_loc_id_inputs(pending_resolution_ids))
    resolutions = [
        {
            "ok": True,
            "status": "unchanged",
            "requested_loc_id": requested,
            "loc_id": requested,
            "resolved_from_public_alias": False,
        }
        if requested in direct_ids and requested not in retired_public_ids else next(pending_resolutions)
        for requested in requested_ids
    ]
    canonical_ids = [str(item.get("loc_id")) for item in resolutions if item.get("ok") and item.get("loc_id")]
    attempted_ids = set(requested_ids)
    alias_targets = [
        loc_id for loc_id in canonical_ids
        if canonicalize_loc_id(loc_id) not in direct_ids
        and canonicalize_loc_id(loc_id) not in attempted_ids
    ]
    if alias_targets:
        rows = [*rows, *get_selection_geometry_metadata(alias_targets)]
    by_loc_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_loc_id = row.get("loc_id") or row.get("source_loc_id")
        if row_loc_id:
            by_loc_id[canonicalize_loc_id(str(row_loc_id))] = row
    items = []
    for resolution in resolutions:
        if not resolution.get("ok"):
            items.append(_public_alias_error(resolution, shape=True))
            continue
        loc_id = str(resolution.get("loc_id"))
        result = by_loc_id.get(loc_id)
        has_shape = bool(result and result.get("has_polygon", True))
        item = {
            "loc_id": loc_id,
            "has_shape": has_shape,
            "name": result.get("name") if result else None,
            "family": _reference_family(loc_id, admin_level=result.get("admin_level")) if has_shape else None,
            "admin_level": result.get("admin_level") if result else None,
            "centroid": {"lon": result.get("centroid_lon"), "lat": result.get("centroid_lat")} if has_shape else None,
            "bbox": [
                result.get("bbox_min_lon"),
                result.get("bbox_min_lat"),
                result.get("bbox_max_lon"),
                result.get("bbox_max_lat"),
            ] if has_shape else None,
        }
        if not item["has_shape"]:
            item["error"] = "no geometry found"
        item = _attach_geometry_supersession(item, loc_id, result)
        items.append(_attach_public_alias_resolution(item, resolution))
    available = sum(1 for item in items if item.get("has_shape"))
    return _clean_json(
        {
            "ok": bool(resolutions),
            "requested": len(resolutions),
            "available": available,
            "missing": len(resolutions) - available,
            "items": items,
            "results": items,
        }
    )


def get_geometry_reference(
    loc_id: str, *, include_polygon: bool = False, include_info: bool = False,
) -> dict[str, Any]:
    """Return geometry metadata, and optionally polygon, for an exchange loc_id."""
    payload = get_geometry_references(
        [loc_id], include_polygon=include_polygon, include_info=include_info,
    )
    results = payload.get("results") or []
    if not results:
        return {"ok": False, "loc_id": canonicalize_loc_id(loc_id), "has_shape": False, "error": "no geometry found"}
    return results[0]
