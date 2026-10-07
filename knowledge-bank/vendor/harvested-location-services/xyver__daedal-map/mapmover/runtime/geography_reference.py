from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from ..foundation_helpers import load_country_crosswalk, load_country_json_asset, load_reference_json
from .geometry_compatibility import translate_compatibility_loc_id

_BASE_DIR = Path(__file__).resolve().parent.parent
_CONVERSIONS_PATH = _BASE_DIR / "conversions.json"

_CONVERSIONS_CACHE: dict[str, Any] | None = None
_ISO_CODES_CACHE: dict[str, Any] | None = None
_USA_ADMIN_CACHE: dict[str, Any] | None = None
_COUNTRY_METADATA_CACHE: dict[str, Any] | None = None
_COUNTRY_NAME_TO_ISO3_CACHE: dict[str, str] | None = None
_CAPITAL_TO_ISO3_CACHE: dict[str, str] | None = None
_CAPITAL_COORDINATES_CACHE: dict[str, dict[str, Any]] | None = None
_COUNTRY_SUBDIVISION_SLUG_CACHE: dict[tuple[str, str], str | None] = {}
_WATER_BODY_CODES_CACHE: set[str] | None = None
_USA_LEGACY_GEOMETRY_TO_LOCAL_CACHE: dict[str, str] | None = None

_EVENT_ENTITY_MARKER_SEGMENTS = {
    "EQ",
    "FIRE",
    "FLOOD",
    "HRCN",
    "TORN",
    "TSUN",
    "VOLC",
}

USA_COUNTY_EQUIVALENT_SUFFIXES = (
    " city and borough",
    " county",
    " parish",
    " borough",
    " census area",
    " municipality",
    " city",
)


def canonicalize_loc_id(loc_id: str) -> str:
    """Return runtime loc_ids in canonical form for shared spine comparisons."""
    return str(loc_id or "").strip().upper()


def _load_water_body_loc_ids() -> set[str]:
    global _WATER_BODY_CODES_CACHE
    if _WATER_BODY_CODES_CACHE is not None:
        return _WATER_BODY_CODES_CACHE
    payload = load_reference_json("water_body_codes.json")
    codes: set[str] = set()
    if isinstance(payload, dict):
        all_codes = payload.get("all_codes")
        if isinstance(all_codes, dict):
            for key in all_codes.keys():
                code = str(key or "").strip().upper()
                if code:
                    codes.add(code)
    _WATER_BODY_CODES_CACHE = codes
    return codes


def is_water_body_loc_id(loc_id: str | None) -> bool:
    value = str(loc_id or "").strip().upper()
    return bool(value) and value in _load_water_body_loc_ids()


def is_eez_loc_id(loc_id: str | None) -> bool:
    value = str(loc_id or "").strip().upper()
    return bool(
        value.startswith("EEZ-")
        or re.fullmatch(r"[A-Z]{3}-EEZ(?:-[A-Z0-9]+(?:-[A-Z0-9]+)*)?", value)
    )


def is_marine_jurisdiction_loc_id(loc_id: str | None) -> bool:
    """True for legacy EEZ ids and country/ocean-scoped Marine releases."""
    value = str(loc_id or "").strip().upper()
    return is_eez_loc_id(value) or bool(
        re.fullmatch(r"[A-Z]{3}-(?:TS|CZ|IW|AW|HS|ECS)(?:-[A-Z0-9]+(?:-[A-Z0-9]+)*)?", value)
    )


def is_named_water_loc_id(loc_id: str | None) -> bool:
    """True for canonical individual ocean/sea identifiers.

    The geometry catalog decides whether a specific id is resolvable. This
    classifier only identifies the namespace so every runtime caller routes it
    through the named-water bank instead of an admin fallback.
    """
    return bool(re.fullmatch(r"(?:MRGID|IHO1953)-\d+", str(loc_id or "").strip().upper()))


def _looks_like_geometry_admin_loc_id(value: str) -> bool:
    parts = value.split("-")
    return len(parts) > 1 and all(str(part).startswith("G") for part in parts[1:])


def _looks_like_event_or_entity_loc_id(value: str) -> bool:
    parts = [segment for segment in str(value or "").strip().upper().split("-") if segment]
    if not parts:
        return False
    if parts[0] in _EVENT_ENTITY_MARKER_SEGMENTS:
        return True
    return any(segment in _EVENT_ENTITY_MARKER_SEGMENTS for segment in parts[1:])


def _looks_like_zcta_loc_id(value: str) -> bool:
    return bool(re.fullmatch(r"USA-Z-\d{5}", value))


def _looks_like_tribal_loc_id(value: str) -> bool:
    parts = [segment for segment in str(value or "").strip().upper().split("-") if segment]
    return "TRIBAL" in parts


def _looks_like_nws_public_zone_loc_id(value: str) -> bool:
    return bool(re.fullmatch(r"USA-NWSZ-[A-Z]{2}Z\d{3}", value))


def _looks_like_nws_fire_weather_zone_loc_id(value: str) -> bool:
    return bool(re.fullmatch(r"USA-NWSFZ-[A-Z]{2}Z\d{3}", value))


def _looks_like_can_federal_electoral_district_loc_id(value: str) -> bool:
    return bool(re.fullmatch(r"CAN-FED-2013-\d{5}", value))


def _looks_like_can_designated_place_loc_id(value: str) -> bool:
    return bool(re.fullmatch(r"CAN-DPL-21-\d{6}", value))


def classify_loc_id_family(loc_id: str | None) -> str | None:
    """Classify the shared runtime loc_id family.

    Family classification is the default seam that runtime and QA should share.
    Metadata may refine behavior later, but it should not decide whether the
    seam exists at all.
    """
    value = str(loc_id or "").strip().upper()
    if not value:
        return None
    if is_water_body_loc_id(value):
        return "water_body"
    if is_marine_jurisdiction_loc_id(value):
        return "marine_eez" if value.startswith("EEZ-") else "marine_jurisdiction"
    if is_named_water_loc_id(value):
        return "water_body"
    if re.fullmatch(r"[A-Z]{3}", value):
        return "admin_0"
    if _looks_like_zcta_loc_id(value):
        return "overlay_zcta"
    if _looks_like_tribal_loc_id(value):
        return "overlay_tribal"
    if _looks_like_nws_public_zone_loc_id(value):
        return "overlay_nws_public_zone"
    if _looks_like_nws_fire_weather_zone_loc_id(value):
        return "overlay_nws_fire_weather_zone"
    if _looks_like_can_federal_electoral_district_loc_id(value):
        return "can_federal_electoral_district_2013"
    if _looks_like_can_designated_place_loc_id(value):
        return "can_designated_place"
    if derive_eurostat_geo_level(value):
        return "regional_base"
    if _looks_like_event_or_entity_loc_id(value):
        return "event_or_entity"
    if _looks_like_geometry_admin_loc_id(value):
        return "admin_geometry"
    if re.fullmatch(r"[A-Z]{3}(?:-[A-Z0-9]+)+", value):
        return "admin_local"
    return None


def build_crosswalk_maps(crosswalk_data: dict[str, Any] | None) -> tuple[dict[str, str], dict[str, str]]:
    """
    Build local->geometry and geometry->preferred-local maps from crosswalk data.

    Includes:
    - admin_1 `mappings`
    - admin_2 FIPS bridge `admin_2_fips`
    """
    local_to_geo: dict[str, str] = {}
    geo_to_local: dict[str, str] = {}
    if not crosswalk_data:
        return local_to_geo, geo_to_local

    for local_loc_id, geo_loc_id in (crosswalk_data.get("mappings") or {}).items():
        local_norm = canonicalize_loc_id(local_loc_id)
        local_to_geo[local_norm] = geo_loc_id
        geo_to_local.setdefault(geo_loc_id, local_norm)

    for local_loc_id, geo_loc_id in (crosswalk_data.get("admin_2_fips") or {}).items():
        local_norm = canonicalize_loc_id(local_loc_id)
        local_to_geo[local_norm] = geo_loc_id
        geo_to_local.setdefault(geo_loc_id, local_norm)

    return local_to_geo, geo_to_local


def _load_usa_legacy_geometry_to_local_map() -> dict[str, str]:
    """Return legacy bundled USA GeoBoundaries ids mapped back to loc_id.

    The generated country crosswalk points at the current geometry bank. Older
    runtime payloads and reference fixtures can still contain the previous
    shorter GeoBoundaries ids. Keep those ids resolvable through loc_id without
    treating them as the current storage id.
    """
    global _USA_LEGACY_GEOMETRY_TO_LOCAL_CACHE
    if _USA_LEGACY_GEOMETRY_TO_LOCAL_CACHE is not None:
        return _USA_LEGACY_GEOMETRY_TO_LOCAL_CACHE

    payload = load_reference_json("usa/usa_counties.json")
    rows = (payload or {}).get("counties") if isinstance(payload, dict) else {}
    out: dict[str, str] = {}
    if isinstance(rows, dict):
        for item in rows.values():
            if not isinstance(item, dict):
                continue
            local = canonicalize_loc_id(str(item.get("loc_id") or ""))
            geometry = canonicalize_loc_id(str(item.get("geometry_loc_id") or ""))
            state = str(item.get("state_abbr") or "").strip().upper()
            if local and geometry:
                out.setdefault(geometry, local)
                parts = geometry.split("-")
                if len(parts) >= 2 and state:
                    out.setdefault(f"{parts[0]}-{parts[1]}", f"USA-{state}")

    _USA_LEGACY_GEOMETRY_TO_LOCAL_CACHE = out
    return _USA_LEGACY_GEOMETRY_TO_LOCAL_CACHE


def translate_loc_id_to_geometry_id(loc_id: str) -> str:
    """
    Translate a dataset loc_id into the geometry join id used by runtime geometry rows.

    - admin_1 local ids can map to GeoBoundaries G-IDs via `mappings`
    - admin_2 USA FIPS bridge ids can map via `admin_2_fips`
    - admin_3+ local ids stay local after canonicalization
    """
    canonical = canonicalize_loc_id(loc_id)
    if not isinstance(canonical, str) or "-" not in canonical:
        return canonical

    compatibility_target = translate_compatibility_loc_id(canonical)
    if compatibility_target != canonical:
        return compatibility_target

    iso3 = canonical.split("-", 1)[0]
    crosswalk = load_country_crosswalk(iso3)
    local_to_geo, _ = build_crosswalk_maps(crosswalk)
    direct = local_to_geo.get(canonical)
    if direct:
        return direct

    if iso3 == "USA":
        parts = canonical.split("-")
        if len(parts) == 3 and parts[2].isdigit() and len(parts[2]) > 3:
            county_only = f"{parts[0]}-{parts[1]}-{parts[2][-3:]}"
            bridged = local_to_geo.get(county_only)
            if bridged:
                return bridged

    return canonical


def translate_geometry_id_to_local_id(loc_id: str) -> str:
    """
    Translate a geometry-side loc_id back to its preferred local/canonical id.
    """
    canonical = canonicalize_loc_id(loc_id)
    if not isinstance(canonical, str) or "-" not in canonical:
        return canonical

    iso3 = canonical.split("-", 1)[0]
    crosswalk = load_country_crosswalk(iso3)
    local_to_geo, geo_to_local = build_crosswalk_maps(crosswalk)
    direct = geo_to_local.get(canonical)
    if direct:
        return direct

    if iso3 == "USA":
        legacy_direct = _load_usa_legacy_geometry_to_local_map().get(canonical)
        if legacy_direct:
            return legacy_direct

        parts = canonical.split("-")
        if len(parts) == 3 and parts[2].isdigit() and len(parts[2]) > 3:
            county_only = f"{parts[0]}-{parts[1]}-{parts[2][-3:]}"
            if county_only in local_to_geo:
                return county_only

    return canonical


def legacy_geometry_ids_for_local_id(loc_id: str | None) -> list[str]:
    """Return accepted legacy geometry ids that resolve to a local loc_id."""
    canonical = canonicalize_loc_id(loc_id or "")
    if not canonical or not canonical.startswith("USA"):
        return []
    aliases = [
        geometry_id
        for geometry_id, local_id in _load_usa_legacy_geometry_to_local_map().items()
        if local_id == canonical and geometry_id != canonical
    ]
    return sorted(set(aliases))


def load_conversions() -> dict[str, Any]:
    """Load shared regional grouping and alias helpers from conversions.json."""
    global _CONVERSIONS_CACHE
    if _CONVERSIONS_CACHE is not None:
        return _CONVERSIONS_CACHE

    if not _CONVERSIONS_PATH.exists():
        _CONVERSIONS_CACHE = {}
        return _CONVERSIONS_CACHE

    with open(_CONVERSIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    _CONVERSIONS_CACHE = data if isinstance(data, dict) else {}
    return _CONVERSIONS_CACHE


def load_iso_codes() -> dict[str, Any]:
    """Load shared ISO code helpers from reference/iso_codes.json."""
    global _ISO_CODES_CACHE
    if _ISO_CODES_CACHE is not None:
        return _ISO_CODES_CACHE

    data = load_reference_json("iso_codes.json")
    _ISO_CODES_CACHE = data if isinstance(data, dict) else {}
    return _ISO_CODES_CACHE


def load_usa_admin() -> dict[str, Any]:
    """Load shared USA admin helpers from reference/usa/usa_admin.json."""
    global _USA_ADMIN_CACHE
    if _USA_ADMIN_CACHE is not None:
        return _USA_ADMIN_CACHE

    data = load_reference_json("usa/usa_admin.json")
    _USA_ADMIN_CACHE = data if isinstance(data, dict) else {}
    return _USA_ADMIN_CACHE


def load_country_metadata() -> dict[str, Any]:
    """Load shared country metadata helpers such as capitals/currencies/timezones."""
    global _COUNTRY_METADATA_CACHE
    if _COUNTRY_METADATA_CACHE is not None:
        return _COUNTRY_METADATA_CACHE

    data = load_reference_json("country_metadata.json")
    _COUNTRY_METADATA_CACHE = data if isinstance(data, dict) else {}
    return _COUNTRY_METADATA_CACHE


def load_country_name_to_iso3_map() -> dict[str, str]:
    """Return the shared country-name alias map used by runtime location adapters."""
    global _COUNTRY_NAME_TO_ISO3_CACHE
    if _COUNTRY_NAME_TO_ISO3_CACHE is not None:
        return _COUNTRY_NAME_TO_ISO3_CACHE

    iso_data = load_iso_codes()
    mapping: dict[str, str] = {}
    for iso3, name in (iso_data.get("iso3_to_name") or {}).items():
        clean_iso3 = str(iso3 or "").strip().upper()
        clean_name = str(name or "").strip().lower()
        if not clean_iso3 or not clean_name:
            continue
        mapping[clean_name] = clean_iso3
        for suffix in (" islands", " island", " republic", " federation"):
            if clean_name.endswith(suffix):
                mapping.setdefault(clean_name[: -len(suffix)].strip(), clean_iso3)

    mapping.update(
        {
            "usa": "USA",
            "us": "USA",
            "united states": "USA",
            "america": "USA",
            "uk": "GBR",
            "britain": "GBR",
            "england": "GBR",
            "russia": "RUS",
            "ussr": "RUS",
            "korea": "KOR",
            "south korea": "KOR",
            "north korea": "PRK",
            "dprk": "PRK",
            "taiwan": "TWN",
            "republic of china": "TWN",
            "iran": "IRN",
            "persia": "IRN",
            "syria": "SYR",
            "uae": "ARE",
            "emirates": "ARE",
            "vietnam": "VNM",
            "viet nam": "VNM",
            "congo": "COD",
            "drc": "COD",
            "ivory coast": "CIV",
            "cote d'ivoire": "CIV",
            "turkey": "TUR",
            "turkiye": "TUR",
            "holland": "NLD",
            "netherlands": "NLD",
            "czech republic": "CZE",
            "czechia": "CZE",
        }
    )
    _COUNTRY_NAME_TO_ISO3_CACHE = mapping
    return _COUNTRY_NAME_TO_ISO3_CACHE


def load_capital_to_iso3_map() -> dict[str, str]:
    """Return the shared capital-name to ISO3 fallback map."""
    global _CAPITAL_TO_ISO3_CACHE
    if _CAPITAL_TO_ISO3_CACHE is not None:
        return _CAPITAL_TO_ISO3_CACHE

    capitals = load_country_metadata().get("capitals") or {}
    mapping: dict[str, str] = {}
    for iso3, capital in capitals.items():
        clean_iso3 = str(iso3 or "").strip().upper()
        clean_capital = str(capital or "").strip().lower()
        if not clean_iso3 or not clean_capital or clean_capital.startswith("_"):
            continue
        mapping[clean_capital] = clean_iso3
    _CAPITAL_TO_ISO3_CACHE = mapping
    return _CAPITAL_TO_ISO3_CACHE


def load_capital_coordinates_by_iso3() -> dict[str, dict[str, Any]]:
    """Load capital fallback coordinates from the shared populated-places asset."""
    global _CAPITAL_COORDINATES_CACHE
    if _CAPITAL_COORDINATES_CACHE is not None:
        return _CAPITAL_COORDINATES_CACHE

    capitals_path = _BASE_DIR / "data_pipeline" / "data_cleaned" / "Populated Places.csv"
    capital_map: dict[str, dict[str, Any]] = {}
    if not capitals_path.exists():
        _CAPITAL_COORDINATES_CACHE = capital_map
        return _CAPITAL_COORDINATES_CACHE

    try:
        df = pd.read_csv(capitals_path)
        capitals = df[df["level"] == "capital"]
        for _, row in capitals.iterrows():
            iso3 = str(row.get("code") or "").strip().upper()
            if not iso3:
                continue
            capital_map[iso3] = {
                "name": row.get("name"),
                "lat": row.get("latitude"),
                "lon": row.get("longitude"),
            }
    except Exception:
        capital_map = {}

    _CAPITAL_COORDINATES_CACHE = capital_map
    return _CAPITAL_COORDINATES_CACHE


def normalize_subdivision_slug(value: str, *, strip_suffixes: tuple[str, ...] = ()) -> str:
    """Normalize a user-facing subdivision slug to a stable lookup key."""
    text = str(value or "").strip().lower()
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"[^\w\s]+", " ", text)
    text = " ".join(text.split())
    for suffix in strip_suffixes:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return " ".join(text.split())


def normalize_county_slug(value: str) -> str:
    """Normalize US county/parish/borough-style slug text for lookup."""
    return normalize_subdivision_slug(value, strip_suffixes=USA_COUNTY_EQUIVALENT_SUFFIXES)


def derive_eurostat_geo_level(loc_id: str | None) -> str | None:
    """
    Infer canonical admin level from a Eurostat/NUTS loc_id shape.

    Format:
    - `ISO3` -> admin_0
    - `ISO3-NNN` (3-char NUTS) -> admin_1
    - `ISO3-NNNN` (4-char NUTS) -> admin_2
    - `ISO3-NNNNN` (5-char NUTS) -> admin_3

    This keeps the shared runtime aware of Eurostat's fixed-length hierarchy
    instead of scattering one-off NUTS logic into callers.
    """
    value = str(loc_id or "").strip().upper()
    if not value:
        return None
    if re.fullmatch(r"[A-Z]{3}", value):
        return "admin_0"

    match = re.fullmatch(r"([A-Z]{3})-([A-Z0-9]+)", value)
    if not match:
        return None

    iso3, nuts_code = match.groups()
    iso_codes = load_iso_codes()
    iso2_to_iso3 = iso_codes.get("iso2_to_iso3") or {}
    iso3_to_iso2 = {
        str(mapped_iso3).upper(): str(iso2).upper()
        for iso2, mapped_iso3 in iso2_to_iso3.items()
    }
    # Length alone is not a NUTS namespace. Without this guard ordinary local
    # IDs such as AUS-ACT, AUS-NSW, and AUS-QLD are misclassified as the shared
    # European regional base. NUTS codes begin with the authority's two-letter
    # country code, with Eurostat's EL/UK conventions as explicit exceptions.
    nuts_prefix = {"GRC": "EL", "GBR": "UK"}.get(iso3, iso3_to_iso2.get(iso3))
    if not nuts_prefix or not nuts_code.startswith(nuts_prefix):
        return None
    if len(nuts_code) == 3:
        return "admin_1"
    if len(nuts_code) == 4:
        return "admin_2"
    if len(nuts_code) == 5:
        return "admin_3"
    return None


def _country_subdivision_lookup_candidates(region: str) -> list[str]:
    value = str(region or "").strip()
    if not value:
        return []

    raw_key = value.lower()
    parts = [segment for segment in value.split("-") if segment]
    candidates = [raw_key]
    if len(parts) < 3:
        return candidates

    prefix = "-".join(parts[:2]).lower()
    slug = "-".join(parts[2:])
    normalized_slug = normalize_subdivision_slug(slug).replace(" ", "-")
    if normalized_slug:
        normalized_key = f"{prefix}-{normalized_slug}"
        if normalized_key not in candidates:
            candidates.append(normalized_key)
    return candidates


def resolve_country_subdivision_slug_loc_id(
    region: str,
    *,
    cache_dict: dict[tuple[str, str], str | None] | None = None,
) -> str | None:
    """Resolve `ISO3-parent-slug` subdivision aliases via country-owned reference data."""
    value = str(region or "").strip()
    match = re.fullmatch(r"([A-Z]{3})-([A-Za-z0-9]+)-([A-Za-z0-9._-]+)", value)
    if not match:
        return None

    iso3 = match.group(1)
    target_cache = cache_dict if cache_dict is not None else _COUNTRY_SUBDIVISION_SLUG_CACHE
    cache_key = (iso3, value.lower())
    if cache_key in target_cache:
        return target_cache[cache_key]

    alias_asset = load_country_json_asset(iso3, "subdivision_slug_aliases.json")
    if not isinstance(alias_asset, dict):
        return None

    aliases = alias_asset.get("aliases")
    if not isinstance(aliases, dict) or not aliases:
        return None

    for candidate in _country_subdivision_lookup_candidates(value):
        loc_id = aliases.get(candidate)
        if isinstance(loc_id, str) and loc_id:
            target_cache[cache_key] = loc_id
            return loc_id

    target_cache[cache_key] = None
    return None


def resolve_us_county_slug_loc_id(
    region: str,
    *,
    load_country_parquet_func=None,
    cache_dict: dict[tuple[str, str], str | None] | None = None,
) -> str | None:
    """Compatibility wrapper for the shared country subdivision slug resolver."""
    return resolve_country_subdivision_slug_loc_id(region, cache_dict=cache_dict)
