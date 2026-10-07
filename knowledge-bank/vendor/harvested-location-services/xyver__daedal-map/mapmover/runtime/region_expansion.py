"""Shared region-expansion helpers extracted from the executor."""

from __future__ import annotations

from mapmover.runtime.geography_reference import is_eez_loc_id, is_water_body_loc_id
from mapmover.runtime.grid_loc_id_resolution import load_water_body_codes


def _normalize_region_text(value: str | None) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _water_body_label_variants(label: str) -> set[str]:
    normalized = _normalize_region_text(label)
    variants = {normalized}
    for suffix in (" sea", " ocean", " waters"):
        if normalized.endswith(suffix):
            variants.add(normalized[: -len(suffix)].strip())
    return {value for value in variants if value}


def _resolve_country_waters(region: str, iso3_to_name: dict[str, str]) -> str | None:
    normalized = _normalize_region_text(region)
    stems = [normalized]

    if normalized.endswith("'s waters"):
        stems.append(normalized[: -len("'s waters")].strip())
    if normalized.endswith(" waters"):
        stems.append(normalized[: -len(" waters")].strip())
    if normalized.startswith("waters around "):
        stems.append(normalized[len("waters around ") :].strip())

    for stem in stems:
        if not stem:
            continue
        for code, name in iso3_to_name.items():
            if _normalize_region_text(name) == stem:
                return f"EEZ-{code}"
    return None


def _resolve_marine_region(region_text: str, *, load_iso_codes_func) -> set[str]:
    """Resolve a region name to marine loc_ids only: X* water-body codes or
    EEZ-<ISO3> national waters. Returns an empty set when the name is not a
    recognized water body / country-waters phrase.

    This is the marine-source counterpart to the land resolution in
    expand_region. For a marine_zone source, basin/sea names like
    "Mediterranean" MUST resolve to the water-body code (XSM), not to the
    land region_aliases grouping of coastal countries (which would yield bare
    ISO3 codes that never match EEZ-* / X* loc_ids). See
    live_source_qa_checklist.md (marine region-name trap)."""
    region_text = str(region_text or "").strip()
    if not region_text:
        return set()
    region_upper = region_text.upper()
    if is_water_body_loc_id(region_upper) or is_eez_loc_id(region_upper):
        return {region_upper}
    # Accept common phrasings the order-taker emits: "the Mediterranean",
    # "Mediterranean basin", "Mediterranean waters" all mean the basin code.
    normalized_region = _normalize_region_text(region_text)
    region_candidates = {normalized_region}
    if normalized_region.startswith("the "):
        region_candidates.add(normalized_region[len("the "):].strip())
    for value in list(region_candidates):
        for suffix in (" basin", " region", " sea area", " waters"):
            if value.endswith(suffix):
                region_candidates.add(value[: -len(suffix)].strip())
    region_candidates = {value for value in region_candidates if value}
    for code, label in load_water_body_codes().items():
        if region_candidates & _water_body_label_variants(label):
            return {code}
    iso3_to_name = (load_iso_codes_func() or {}).get("iso3_to_name", {})
    eez_loc_id = _resolve_country_waters(region_text, iso3_to_name)
    if eez_loc_id:
        return {eez_loc_id}
    return set()


def expand_region(
    region: str,
    *,
    resolve_country_subdivision_slug_loc_id_func,
    regional_groups: dict[str, set[str]],
    load_conversions_func,
    load_iso_codes_func,
    load_usa_admin_func,
    prefer_water_body: bool = False,
) -> set[str]:
    """Expand a region name to a set of country or loc_id prefixes.

    When ``prefer_water_body`` is set (marine_zone sources), marine resolution
    runs first so basin/sea names resolve to X*/EEZ-* loc_ids instead of the
    land region_aliases grouping of coastal countries.
    """
    if not region or region.lower() in ("global", "all", "world"):
        return set()

    region_text = str(region).strip()
    region_upper = region_text.upper()
    if is_water_body_loc_id(region_upper) or is_eez_loc_id(region_upper):
        return {region_upper}

    if prefer_water_body:
        marine_codes = _resolve_marine_region(region_text, load_iso_codes_func=load_iso_codes_func)
        if marine_codes:
            return marine_codes

    subdivision_loc_id = resolve_country_subdivision_slug_loc_id_func(region)
    if subdivision_loc_id:
        return {subdivision_loc_id}

    normalized_region = _normalize_region_text(region_text)
    if normalized_region in regional_groups:
        return set(regional_groups[normalized_region])
    if normalized_region in {"puerto rico", "puerto rico usa"}:
        return {"USA-PR"}

    region_parts = [part for part in region_text.split("-") if part]
    if (
        len(region_parts) >= 2
        and len(region_parts[0]) == 3
        and region_parts[0].isalpha()
        and all(part.replace("_", "").isalnum() for part in region_parts[1:])
    ):
        return {"-".join(part.upper() for part in region_parts)}

    conversions = load_conversions_func()
    region_lower = region.lower()
    region_normalized = region_lower.replace("_", " ").replace("-", " ")

    # Reviewed, direct loc_id aliases are deliberately separate from broad
    # regional groupings. They let an unambiguous administrative name such as
    # "British Columbia" become CAN-BC without teaching the runtime to guess
    # that every place-shaped proper noun (notably "New York") means Admin1.
    location_aliases = conversions.get("location_aliases", {})
    for alias, loc_id in location_aliases.items():
        alias_lower = str(alias).lower()
        if alias_lower == region_lower or alias_lower.replace("_", " ").replace("-", " ") == region_normalized:
            canonical = str(loc_id or "").strip().upper()
            if canonical:
                return {canonical}

    region_aliases = conversions.get("region_aliases", {})
    for alias, grouping_key in region_aliases.items():
        alias_lower = alias.lower()
        if alias_lower == region_lower or alias_lower.replace("_", " ").replace("-", " ") == region_normalized:
            grouping = conversions.get("regional_groupings", {}).get(grouping_key, {})
            return set(grouping.get("countries", []))

    regional_groupings = conversions.get("regional_groupings", {})
    for key, grouping in regional_groupings.items():
        key_lower = key.lower()
        if key_lower == region_lower or key_lower.replace("_", " ").replace("-", " ") == region_normalized:
            return set(grouping.get("countries", []))

    water_body_codes = load_water_body_codes()
    for code, label in water_body_codes.items():
        if normalized_region in _water_body_label_variants(label):
            return {code}

    iso_data = load_iso_codes_func()
    iso3_to_name = iso_data.get("iso3_to_name", {})
    for code, name in iso3_to_name.items():
        if name.lower() == region_lower:
            return {code}

    if region.upper() in iso3_to_name:
        return {region.upper()}

    # Only resolve plain country names to EEZ-* when the caller explicitly
    # requested marine semantics. Land queries like "Canada" or "Australia"
    # should stay on CAN/AUS rather than silently switching to national waters.
    if prefer_water_body:
        eez_loc_id = _resolve_country_waters(region_text, iso3_to_name)
        if eez_loc_id:
            return {eez_loc_id}

    usa_admin = load_usa_admin_func()
    state_abbrevs = usa_admin.get("state_abbreviations", {})
    for abbrev, name in state_abbrevs.items():
        if name.lower() == region_lower or abbrev.lower() == region_lower:
            return {f"USA-{abbrev}"}

    return set()
