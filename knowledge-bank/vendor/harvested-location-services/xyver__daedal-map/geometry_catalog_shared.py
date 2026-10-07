"""Pure projections shared by geometry catalog builders and consumers.

The generated ``geometry/geometry_catalog.json`` is the capability authority.
This module contains only deterministic projections of that document so build,
runtime, and website code do not maintain parallel country lists or depth
claims.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


GEOMETRY_CATALOG_RECORD_KEYS = (
    "country_profiles",
    "domain_profiles",
    "geometry_collections",
    "geometry_families",
    "geometry_banks",
    "geometry_products",
    "release_packages",
    "crosswalk_artifacts",
    "reference_systems",
    "crosswalks",
    "external_reference_bridges",
    "compatibility_releases",
    "resolver_groups",
    "named_reference_objects",
)

# The composed catalog is also an internal release/audit artifact.  These
# fields are intentionally retained there, but are duplicated many times and
# do not belong in the public directory fetched by browsers and discovery
# clients.  Their authoritative copies remain in country catalogs and source
# or release metadata.
_PUBLIC_BANK_DETAIL_FIELDS = {
    "attribution_lines",
    "citation",
    "license_conditions",
    "provenance",
    "source_licenses",
}
_PUBLIC_PRODUCT_DETAIL_FIELDS = {"source_licenses"}
_PUBLIC_FAMILY_DETAIL_FIELDS = {
    "admin_1_branch_coverage",
    "coverage_scopes",
    "nesting_dispositions",
    "source_license_details",
    "source_licenses",
    "source_releases",
}
_PUBLIC_COVERAGE_DETAIL_FIELDS = {
    "admin_1_branch_coverage",
    "implementation_subfamily_coverage",
    "jurisdiction_rows",
}
_PUBLIC_CROSSWALK_ARTIFACT_DETAIL_FIELDS = {
    "_source_geometry_bank",
    "_target_geometry_bank",
    "source_license",
}


def merge_crosswalk_catalog(
    geometry_catalog: dict[str, Any], crosswalk_catalog: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach the separately generated canonical crosswalk contract."""
    if not isinstance(crosswalk_catalog, dict) or not crosswalk_catalog:
        return geometry_catalog
    result = dict(geometry_catalog)
    result["reference_systems"] = list(crosswalk_catalog.get("reference_systems") or [])
    result["crosswalks"] = list(crosswalk_catalog.get("crosswalks") or [])
    result["crosswalk_summary"] = dict(crosswalk_catalog.get("summary") or {})
    result["crosswalk_registry_fingerprint"] = crosswalk_catalog.get("registry_fingerprint")
    return result


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _country_code(value: Any) -> str:
    return str(value or "").strip().upper()


def public_geometry_catalog_records(catalog: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return admitted/current records without exposing internal release lanes."""
    hidden_states = {
        "blocked", "candidate", "candidate_blocked", "in_preparation",
        "preparing", "researching", "wip",
    }
    rows = []
    for item in catalog.get(key) or []:
        if not isinstance(item, dict):
            continue
        states = {
            str(item.get(field) or "").strip().lower()
            for field in ("status", "release_state", "publication_status")
            if str(item.get(field) or "").strip()
        }
        has_hidden_candidate = any(
            state.startswith("candidate") and state not in {"candidate_pass", "candidate_published"}
            for state in states
        )
        if states & hidden_states or has_hidden_candidate or any("blocked" in state for state in states):
            continue
        public_item = dict(item)
        if key == "country_profiles":
            for field in (
                "release_status", "release_id", "graph_release_id",
                "candidate_state", "publication_status", "runtime_state",
                "profile_required", "active_runtime_unchanged",
            ):
                public_item.pop(field, None)
            public_item["qa_highlights"] = [
                str(value).replace("adopted local ", "maintained ").replace("local Census", "Census")
                for value in (item.get("qa_highlights") or [])
                if "candidate" not in str(value).lower()
                and "unpublished" not in str(value).lower()
            ]
            public_item["family_coverage"] = [
                {
                    field: value
                    for field, value in family.items()
                    if field not in {"state", "included", "implementation_ids", "source_ids"}
                }
                for family in (item.get("family_coverage") or [])
                if isinstance(family, dict) and family.get("available") is True
            ]
            public_item["package_recipes"] = [
                dict(recipe)
                for recipe in (item.get("package_recipes") or [])
                if isinstance(recipe, dict) and recipe.get("download_available") is True
            ]
        elif key == "country_family_coverage":
            public_item = {
                field: value
                for field, value in public_item.items()
                if not field.startswith("candidate_")
                and field not in {
                    "release_status", "release_id", "graph_release_id",
                    "publication_status", "runtime_state", "profile_required",
                    "active_runtime_unchanged",
                }
            }
        rows.append(public_item)
    return rows


def published_geometry_catalog_records(catalog: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return records admitted to the public MCP and download surfaces."""
    filtered_catalog = dict(catalog)
    filtered_rows: list[dict[str, Any]] = []
    for item in catalog.get(key) or []:
        if not isinstance(item, dict):
            continue
        states = {
            str(item.get(field) or "").strip().lower()
            for field in (
                "status", "release_state", "release_status",
                "publication_status", "runtime_state", "candidate_state",
            )
            if str(item.get(field) or "").strip()
        }
        if any("candidate" in state for state in states):
            continue
        if any(
            token in state
            for state in states
            for token in ("staged", "prepar", "research", "blocked", "in_progress", "wip")
        ):
            continue
        if key in {"country_profiles", "domain_profiles"}:
            release_status = str(item.get("release_status") or "").strip().lower()
            if release_status and release_status not in {"approved_for_publication", "published"}:
                continue
        if key in {"crosswalks", "reference_systems"} and item.get("callable") is not True:
            continue
        filtered_rows.append(item)
    filtered_catalog[key] = filtered_rows
    return public_geometry_catalog_records(filtered_catalog, key)


def _without_candidate_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_candidate_fields(item)
            for key, item in value.items()
            if not str(key).startswith("candidate_")
        }
    if isinstance(value, list):
        return [_without_candidate_fields(item) for item in value]
    return value


def _without_fields(record: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in fields}


def _compact_material_policy(value: Any) -> dict[str, Any] | None:
    """Keep public legal/citation facts while dropping repeated source receipts."""
    if not isinstance(value, dict):
        return None
    return {
        key: item
        for key, item in value.items()
        if key not in {"provenance", "object_license_policy"}
    }


def _compact_family_rows(rows: Any) -> list[dict[str, Any]]:
    return [
        _without_fields(row, _PUBLIC_FAMILY_DETAIL_FIELDS)
        for row in (rows or [])
        if isinstance(row, dict)
    ]


def _compact_public_record(key: str, record: dict[str, Any]) -> dict[str, Any]:
    """Keep discovery facts while referring detailed evidence to its owner."""
    result = dict(record)
    if key == "geometry_banks":
        result = _without_fields(result, _PUBLIC_BANK_DETAIL_FIELDS)
    elif key == "geometry_products":
        result = _without_fields(result, _PUBLIC_PRODUCT_DETAIL_FIELDS)
    elif key == "crosswalk_artifacts":
        result = _without_fields(result, _PUBLIC_CROSSWALK_ARTIFACT_DETAIL_FIELDS)
    elif key in {"country_profiles", "domain_profiles"}:
        result["family_coverage"] = _compact_family_rows(result.get("family_coverage"))
        if key == "country_profiles" and isinstance(result.get("active_release"), dict):
            result["active_release"] = _without_fields(
                result["active_release"],
                {
                    "source_pointer_path",
                    "source_pointer_sha256",
                    "version_manifest_path",
                    "version_manifest_sha256",
                },
            )
        country = _country_code(result.get("country_code"))
        if country:
            result["country_catalog_path"] = (
                f"geometry/countries/{country}/{country}_catalog.json"
            )
    compact_policy = _compact_material_policy(result.get("material_policy"))
    if compact_policy is not None:
        result["material_policy"] = compact_policy
    return result


def build_published_geometry_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    """Build the compact public directory without internal lifecycle records.

    The global document answers what exists and where its deeper catalog lives.
    Complete provenance/license closures stay in the composed internal catalog,
    country catalogs, and referenced source/release metadata.
    """
    result = {
        key: value
        for key, value in catalog.items()
        if key not in GEOMETRY_CATALOG_RECORD_KEYS
        and key not in {"reference_systems", "crosswalks"}
    }
    for key in GEOMETRY_CATALOG_RECORD_KEYS:
        if key in {"reference_systems", "crosswalks"}:
            continue
        result[key] = [
            _compact_public_record(key, record)
            for record in published_geometry_catalog_records(catalog, key)
        ]

    published_country_codes = {
        _country_code(item.get("country_code"))
        for item in result.get("country_profiles") or []
        if isinstance(item, dict) and _country_code(item.get("country_code"))
    }
    coverage_rows: list[dict[str, Any]] = []
    for raw_row in public_geometry_catalog_records(catalog, "country_family_coverage"):
        country_code = _country_code(raw_row.get("country_code"))
        if country_code != "GLOBAL" and country_code not in published_country_codes:
            continue
        row = _without_fields(
            _without_candidate_fields(raw_row), _PUBLIC_COVERAGE_DETAIL_FIELDS,
        )
        families = [
            _without_fields(
                _without_candidate_fields(family), _PUBLIC_FAMILY_DETAIL_FIELDS,
            )
            for family in raw_row.get("families") or []
            if isinstance(family, dict) and family.get("available") is True
        ]
        row["families"] = families
        row["available_family_ids"] = sorted({
            str(family.get("family_id") or "").strip()
            for family in families
            if str(family.get("family_id") or "").strip()
        })
        row["complete_family_ids"] = sorted({
            str(family.get("family_id") or "").strip()
            for family in families
            if str(family.get("family_id") or "").strip()
            and family.get("coverage_complete") is True
        })
        coverage_rows.append(row)
    result["country_family_coverage"] = coverage_rows
    result = _without_candidate_fields(result)
    result["crosswalk_catalog_path"] = "geometry/crosswalk_catalog.json"
    result["detail_model"] = {
        "global": "directory",
        "country": "geometry/countries/{ISO3}/{ISO3}_catalog.json",
        "source_and_release": "referenced metadata and version manifests",
    }
    result["purpose"] = (
        "Published geometry capability and discovery catalog. Internal candidate and WIP "
        "lifecycle records are excluded."
    )
    result["capability_summary"] = build_geometry_capability_summary(result)
    result["source_catalog_fingerprint"] = catalog.get("catalog_fingerprint")
    fingerprint_payload = {
        key: value for key, value in result.items()
        if key not in {"generated_at", "catalog_fingerprint"}
    }
    result["catalog_fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return result


def build_geometry_capability_summary(catalog: dict[str, Any]) -> dict[str, Any]:
    """Return the public global-baseline plus country-enrichment contract."""
    baseline_rows = [
        item for item in (catalog.get("global_admin_baseline") or [])
        if isinstance(item, dict) and _country_code(item.get("country_code"))
    ]
    baseline_depth_by_country = {
        _country_code(item.get("country_code")): _as_int(item.get("max_admin_level"))
        for item in baseline_rows
    }
    depth_counts: dict[str, int] = {}
    for depth in baseline_depth_by_country.values():
        key = "unknown" if depth is None else str(depth)
        depth_counts[key] = depth_counts.get(key, 0) + 1
    known_depths = [value for value in baseline_depth_by_country.values() if value is not None]

    profiles = {
        _country_code(item.get("country_code")): item
        for item in (catalog.get("country_profiles") or [])
        if isinstance(item, dict) and _country_code(item.get("country_code"))
    }
    enhanced: list[dict[str, Any]] = []
    for item in catalog.get("country_family_coverage") or []:
        if not isinstance(item, dict):
            continue
        code = _country_code(item.get("country_code"))
        if not code or code == "GLOBAL":
            continue
        active_depth = _as_int(item.get("active_admin_depth"))
        if active_depth is None:
            active_depth = _as_int(item.get("max_admin_level"))
        baseline_depth = baseline_depth_by_country.get(code)
        if active_depth is None:
            active_depth = baseline_depth
        family_ids = sorted({
            str(value).strip()
            for value in (item.get("available_family_ids") or [])
            if str(value).strip()
        })
        complete_family_ids = sorted({
            str(value).strip()
            for value in (item.get("complete_family_ids") or [])
            if str(value).strip()
        })
        added_families = [value for value in family_ids if value != "administrative"]
        reasons = []
        if active_depth is not None and (baseline_depth is None or active_depth > baseline_depth):
            reasons.append("deeper_admin_spine")
        if added_families:
            reasons.append("additional_reference_families")
        profile = profiles.get(code) or {}
        row = {
            "country_code": code,
            "label": item.get("label") or profile.get("label") or code,
            "baseline_admin_depth": baseline_depth,
            "active_admin_depth": active_depth,
            "available_family_ids": family_ids,
            "complete_family_ids": complete_family_ids,
            "admin_hierarchy_coverage_status": item.get("admin_hierarchy_coverage_status"),
            "admin_hierarchy_coverage_complete": bool(item.get("admin_hierarchy_coverage_complete")),
            "enrichment_reasons": reasons,
            "profile_id": profile.get("profile_id"),
            "release_status": profile.get("release_status"),
        }
        if reasons:
            enhanced.append(row)

    enhanced.sort(key=lambda item: (str(item.get("label") or ""), item["country_code"]))
    baseline_max = max(known_depths) if known_depths else None
    enhanced_labels = [str(item.get("label") or item["country_code"]) for item in enhanced]
    baseline_phrase = f"a cataloged baseline of {len(baseline_rows)} geographic entities"
    if baseline_max is not None:
        baseline_phrase += f", reaching up to Admin {baseline_max}"
    enrichment_phrase = (
        f" Additional detail is currently available for {', '.join(enhanced_labels)}."
        if enhanced_labels else ""
    )
    return {
        "model": "global_baseline_plus_catalog_admitted_country_enrichment",
        "public_claim": (
            f"The same geography tools work worldwide across {baseline_phrase}. Where additional "
            f"country releases are available, the same calls automatically return deeper administrative "
            f"tiers or maintained reference families.{enrichment_phrase}"
        ),
        "global_baseline": {
            "geographic_entity_count": len(baseline_rows),
            "max_admin_depth": baseline_max,
            "depth_counts": depth_counts,
        },
        "enhanced_country_count": len(enhanced),
        "enhanced_country_codes": [item["country_code"] for item in enhanced],
        "enhanced_countries": enhanced,
    }
