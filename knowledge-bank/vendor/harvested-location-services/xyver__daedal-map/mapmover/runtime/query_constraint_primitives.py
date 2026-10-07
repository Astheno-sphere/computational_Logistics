"""Deterministic query-constraint extraction shared by chat preprocessing and repair."""

from __future__ import annotations

import re
from pathlib import Path


_AREA_THRESHOLD_RE = re.compile(
    r"\b(?:bigger(?:\s+than)?|larger(?:\s+than)?|greater(?:\s+than)?|over|above|at\s+least|minimum\s+of|more\s+than)\s+"
    r"(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*"
    r"(?P<unit>km2|km\^2|sq\.?\s*km|square\s*km|acres?|ac|hectares?|ha)\b",
    re.IGNORECASE,
)
_REGION_SEGMENT_RE = re.compile(
    r"\b(?:in|within|across|throughout|for)\s+"
    r"(?P<region>.+?)"
    r"(?=\s*(?:,?\s+(?:from|since|between|during|over|before|after|bigger|larger|greater|above|at\s+least|minimum|more\s+than)\b|[?.!]?$))",
    re.IGNORECASE,
)
_REGION_SUFFIX_RE = re.compile(
    r"\b(county|parish|borough|municipality|municipio|district|region|province|state|prefecture|department|departement|oblast)\b",
    re.IGNORECASE,
)
def _parse_area_threshold(query_text: str) -> dict | None:
    if not query_text:
        return None
    match = _AREA_THRESHOLD_RE.search(query_text)
    if not match:
        return None

    try:
        raw_value = float(str(match.group("value") or "").replace(",", ""))
    except (TypeError, ValueError):
        return None

    source_unit = str(match.group("unit") or "").strip().lower()
    normalized_value = raw_value
    if source_unit in {"ac", "acre", "acres"}:
        normalized_value = raw_value * 0.00404686
    elif source_unit in {"ha", "hectare", "hectares"}:
        normalized_value = raw_value * 0.01

    return {
        "source_value": raw_value,
        "source_unit": source_unit,
        "normalized_field": "area_km2_min",
        "normalized_unit": "km2",
        "normalized_value": normalized_value,
    }


def _resolve_location_constraint(query_text: str, *, resolve_admin_text_to_loc_id_func, load_reference_file_func, reference_dir) -> dict | None:
    if not query_text:
        return None
    match = _REGION_SEGMENT_RE.search(query_text)
    if not match:
        return None

    raw_region = str(match.group("region") or "").strip(" ,.?")
    if not raw_region:
        return None

    iso3_to_name = {}
    if reference_dir and load_reference_file_func:
        iso_path = Path(reference_dir) / "iso_codes.json"
        iso_data = load_reference_file_func(iso_path) or {}
        iso3_to_name = iso_data.get("iso3_to_name", {})

    parts = [part.strip(" ,.?\t") for part in raw_region.split(",") if part.strip(" ,.?\t")]
    country_hint = None
    country_term = None

    def _resolve_country(value: str) -> str | None:
        maybe_country = resolve_admin_text_to_loc_id_func(value, admin_level_hint=0)
        country_loc_id = str(maybe_country.get("deepest_resolved_loc_id") or "").strip()
        return country_loc_id or None

    if parts:
        country_hint = _resolve_country(parts[-1])
        if country_hint:
            country_term = parts[-1]

    if not country_hint and len(parts) == 1:
        tokens = [token for token in raw_region.split() if token]
        for start_index in range(1, len(tokens)):
            maybe_country_term = " ".join(tokens[start_index:]).strip(" ,.?\t")
            maybe_region_term = " ".join(tokens[:start_index]).strip(" ,.?\t")
            if not maybe_country_term or not maybe_region_term:
                continue
            resolved_country = _resolve_country(maybe_country_term)
            if not resolved_country:
                continue
            country_hint = resolved_country
            country_term = maybe_country_term
            parts = [maybe_region_term, maybe_country_term]
            break

    search_parts = parts[:-1] if len(parts) >= 2 and country_hint else parts
    if not search_parts and country_hint:
        return {
            "matched_term": country_term or raw_region,
            "loc_id": country_hint,
            "iso3": country_hint.split("-", 1)[0],
            "country_name": iso3_to_name.get(country_hint.split("-", 1)[0], country_hint),
            "is_subregion": False,
            "source": "query_region_constraint",
        }

    for part in search_parts:
        resolved = resolve_admin_text_to_loc_id_func(part, country_hint=country_hint)
        loc_id = str(resolved.get("deepest_resolved_loc_id") or "").strip()
        if not loc_id and country_hint:
            simplified_part = _REGION_SUFFIX_RE.sub(" ", part)
            simplified_part = " ".join(str(simplified_part or "").split())
            if simplified_part and simplified_part != part:
                resolved = resolve_admin_text_to_loc_id_func(simplified_part, country_hint=country_hint)
                loc_id = str(resolved.get("deepest_resolved_loc_id") or "").strip()
        if not loc_id:
            continue
        iso3 = loc_id.split("-", 1)[0]
        return {
            "matched_term": part,
            "loc_id": loc_id,
            "iso3": iso3,
            "country_name": iso3_to_name.get(iso3, iso3),
            "is_subregion": loc_id != iso3,
            "source": "query_region_constraint",
        }

    return None


def extract_query_constraints(
    query_text: str,
    *,
    resolve_admin_text_to_loc_id_func,
    load_reference_file_func,
    reference_dir,
) -> dict:
    """Extract canonical region and normalized numeric filters from free text."""
    text = str(query_text or "").strip()
    area_constraint = _parse_area_threshold(text)
    location_constraint = _resolve_location_constraint(
        text,
        resolve_admin_text_to_loc_id_func=resolve_admin_text_to_loc_id_func,
        load_reference_file_func=load_reference_file_func,
        reference_dir=reference_dir,
    )

    filters = {}
    if area_constraint:
        filters[area_constraint["normalized_field"]] = area_constraint["normalized_value"]

    return {
        "region_loc_id": location_constraint.get("loc_id") if location_constraint else None,
        "country_iso3": location_constraint.get("iso3") if location_constraint else None,
        "location": location_constraint,
        "area_constraint": area_constraint,
        "filters": filters,
    }
