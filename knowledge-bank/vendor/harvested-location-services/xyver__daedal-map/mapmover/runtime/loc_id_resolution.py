from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from ..duckdb_helpers import is_cloud_mode
from ..geometry_handlers import (
    get_selection_geometries,
    load_country_parquet,
    load_global_country_display_frame,
    load_subcounty_geometry,
    resolve_point_to_location as legacy_resolve_point_to_location,
)
from ..name_standardizer import NameStandardizer
from ..paths import GEOMETRY_DIR
from ..reference.usa.location_lookup import by_zip as usa_zip_lookup
from .admin_hierarchy import get_parent_loc_id, infer_admin_level_from_loc_id
from .admin_spine_query import shallow_identity_level_rows
from .country_geography import get_country_location_aliases
from .geography_reference import (
    canonicalize_loc_id,
    classify_loc_id_family,
    is_named_water_loc_id,
    load_conversions,
    translate_geometry_id_to_local_id,
)
from .marine_geometry import load_marine_geometry_at_point, load_marine_geometry_for_points
from .place_lookup import resolve_populated_place

_LOC_ID_RE = re.compile(r"^[A-Z]{3}(?:-[A-Z0-9]+)+$|^[A-Z]{3}$")
_USA_ZIP_RE = re.compile(r"^\d{5}$")
_NAME_STANDARDIZER: NameStandardizer | None = None
_TEXT_COLLAPSE_RE = re.compile(r"[^a-z0-9]+")
_USA_TRIBAL_ALIAS_SUFFIX_RE = re.compile(
    r"\b(indian reservation and off reservation trust land|indian reservation|off reservation trust land|reservation|nation|tribe|tribal community|community|pueblo|village|native village)\b",
    re.IGNORECASE,
)
_ADMIN_TEXT_SUFFIX_RE = re.compile(
    r"\b(county|parish|borough|municipality|municipio|district|region|province|state|prefecture|department|departement|oblast|county of)\b",
    re.IGNORECASE,
)
_ADMIN_TEXT_ALIASES = {
    "bavaria": "bayern",
    "hesse": "hessen",
    "lower saxony": "niedersachsen",
    "north rhine westphalia": "nordrhein westfalen",
    "north rhine-westphalia": "nordrhein westfalen",
    "rhineland palatinate": "rheinland pfalz",
    "saxony": "sachsen",
    "saxony anhalt": "sachsen anhalt",
    "saxony-anhalt": "sachsen anhalt",
    "thuringia": "thuringen",
    "baden wurttemberg": "baden wurttemberg",
    "baden-wurttemberg": "baden wurttemberg",
    "mecklenburg western pomerania": "mecklenburg vorpommern",
    "mecklenburg-western pomerania": "mecklenburg vorpommern",
}
_COUNTRY_DIRECT_LOCATION_ALIAS_CACHE: dict[str, dict[str, str]] = {}
_COUNTRY_FALLBACK_LOCATION_ALIAS_CACHE: dict[str, dict[str, str]] = {}


def _explicit_admin_level_from_text(value: str) -> int | None:
    """Return a conservative level hint only for unambiguous grain words."""
    text = str(value or "").strip().lower()
    if re.search(r"\b(state|province)\b", text):
        return 1
    if re.search(r"\b(county|parish|municipio|county of)\b", text):
        return 2
    return None


def normalize_geometry_longitude(value: float) -> float:
    """Normalize a wrapped map longitude to the GeoJSON/geometry convention.

    MapLibre may report an equivalent wrapped longitude such as ``200.8`` for
    a Pacific click. Geometry banks use the conventional ``[-180, 180)``
    domain, so containment must use the normalized coordinate. The caller may
    still retain the original requested longitude for display/audit.
    """
    longitude = float(value)
    return ((longitude + 180.0) % 360.0) - 180.0


def _attach_requested_point(payload: dict[str, Any], *, lon: float, lat: float, normalized_lon: float) -> dict[str, Any]:
    if normalized_lon != lon:
        payload["requested_point"] = {"lon": lon, "lat": lat}
        payload["point"] = {"lon": normalized_lon, "lat": lat}
    return payload


def _resolve_point_to_marine_stack(
    lon: float,
    lat: float,
    *,
    include_geometry: bool = False,
    marine_df: pd.DataFrame | None = None,
    candidate_loc_ids: set[str] | None = None,
    candidates_are_exact: bool = False,
    geometry_cache: dict[str, Any] | None = None,
    marine_rows_by_loc_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if marine_df is None:
        marine_df = load_marine_geometry_at_point(lon, lat)
    if marine_df is None or marine_df.empty:
        return None

    try:
        from shapely.geometry import Point, shape
    except Exception:
        return None

    point = None if candidates_are_exact else Point(float(lon), float(lat))
    candidate_rows: list[Any] | None = None
    if marine_rows_by_loc_id is not None and candidate_loc_ids is not None:
        candidate_rows = [
            marine_rows_by_loc_id[loc_id]
            for loc_id in candidate_loc_ids
            if loc_id in marine_rows_by_loc_id
        ]
        if not candidate_rows:
            return None
    candidates = marine_df
    if candidate_rows is None and candidate_loc_ids is not None:
        candidates = candidates[candidates["loc_id"].astype(str).isin(candidate_loc_ids)]
        if candidates.empty:
            return None
    bbox_cols = {"bbox_min_lon", "bbox_max_lon", "bbox_min_lat", "bbox_max_lat"}
    if candidate_rows is None and bbox_cols.issubset(set(candidates.columns)):
        candidates = candidates[
            (candidates["bbox_max_lon"] >= lon) &
            (candidates["bbox_min_lon"] <= lon) &
            (candidates["bbox_max_lat"] >= lat) &
            (candidates["bbox_min_lat"] <= lat)
        ]
    if candidate_rows is None and candidates.empty:
        return None

    # A reviewed named IHO water polygon is the location answer. Legacy X*
    # water zones are SST product aggregates, not point-location geography;
    # retain them nowhere in the returned location stack. EEZs are genuine
    # overlapping jurisdictions, but not the physical water-body answer.
    family_order = {"named_water": 0, "marine_jurisdiction": 1, "marine_eez": 1, "water_body": 2}
    matches: list[dict[str, Any]] = []
    rows = candidate_rows if candidate_rows is not None else (
        row for _, row in candidates.iterrows()
    )
    for row in rows:
        loc_id = str(row.get("loc_id") or "").strip()
        if not loc_id:
            continue
        family = classify_loc_id_family(loc_id)
        named_water = is_named_water_loc_id(loc_id)
        wkb_value = row.get("geometry_wkb")
        geom_value = wkb_value if isinstance(wkb_value, (bytes, bytearray, memoryview)) else row.get("geometry")
        if not geom_value and not candidates_are_exact:
            continue
        exact_shape = None
        try:
            area_value = row.get("area_km2")
            geometry_area = float(area_value) if pd.notna(area_value) else None
            if not candidates_are_exact or geometry_area is None:
                exact_shape = geometry_cache.get(loc_id) if geometry_cache is not None else None
            if exact_shape is None and (not candidates_are_exact or geometry_area is None):
                if isinstance(geom_value, (bytes, bytearray, memoryview)):
                    from shapely import wkb

                    exact_shape = wkb.loads(bytes(geom_value))
                else:
                    geometry = json.loads(geom_value) if isinstance(geom_value, str) else geom_value
                    if not geometry or geometry.get("type") == "Point":
                        continue
                    exact_shape = shape(geometry)
                if geometry_cache is not None:
                    geometry_cache[loc_id] = exact_shape
            if not candidates_are_exact and (
                exact_shape.geom_type == "Point" or not exact_shape.covers(point)
            ):
                continue
            if geometry_area is None:
                geometry_area = float(exact_shape.area)
        except Exception:
            continue
        matches.append({
            "loc_id": loc_id,
            "name": row.get("name"),
            "family": family,
            "family_rank": family_order["named_water"] if named_water else family_order.get(family, 99),
            "geometry_area": geometry_area,
            "named_water": named_water,
        })

    if not matches:
        return None

    matches.sort(key=lambda item: (item["family_rank"], item["geometry_area"], str(item.get("loc_id") or "")))
    deepest = matches[0]
    overlap_families = []
    for entry in matches:
        if entry["loc_id"] == deepest["loc_id"]:
            continue
        if entry.get("named_water") and deepest.get("named_water"):
            relationship = "broader_water_body"
        elif entry.get("family") in {"marine_jurisdiction", "marine_eez"}:
            relationship = "marine_jurisdiction"
        else:
            # X* zones are valid SST aggregation geometry, but not a second
            # answer to "what location contains this point?"
            continue
        overlap_families.append({
            "loc_id": entry["loc_id"],
            "name": entry.get("name"),
            "family": entry.get("family"),
            "admin_level": None,
            "relationship": relationship,
        })
    stack = [
        {
            "loc_id": deepest["loc_id"],
            "name": deepest.get("name"),
            "admin_level": None,
            "family": deepest.get("family"),
        }
    ]

    result = {
        "point": {"lon": float(lon), "lat": float(lat)},
        "country": None,
        "matched": {
            "loc_id": deepest["loc_id"],
            "name": deepest.get("name"),
            "admin_level": None,
            "country_name": None,
            "iso3": None,
            "family": deepest.get("family"),
        },
        "stack": stack,
        "matches": {},
        "deepest_resolved_loc_id": deepest["loc_id"],
        "deepest_resolved_admin_level": None,
        "deepest_resolved_family": deepest.get("family"),
        "overlap_families": overlap_families,
        "should_persist_deepest_loc_id": True,
        "legacy_payload": {
            "point": {"lon": float(lon), "lat": float(lat)},
            "matched": {
                "loc_id": deepest["loc_id"],
                "name": deepest.get("name"),
                "family": deepest.get("family"),
            },
            "stack": stack,
            "overlap_families": overlap_families,
            "resolution_family": "marine",
        },
        "resolution_family": "marine",
    }
    if include_geometry:
        result["geojson"] = get_selection_geometries([deepest["loc_id"]])
    return result


def _resolve_points_to_marine_stacks(
    points: list[dict[str, Any]],
    *,
    include_geometry: bool = False,
) -> list[dict[str, Any] | None]:
    """Resolve Marine overlaps with one candidate/hydration pass per batch."""
    point_items = list(points or [])
    batch = load_marine_geometry_for_points(point_items)
    if batch is None:
        return [
            _resolve_point_to_marine_stack(
                float(point["lon"]), float(point["lat"]),
                include_geometry=include_geometry,
            )
            for point in point_items
        ]
    marine_df, candidate_ids = batch
    geometry_cache: dict[str, Any] = {}
    marine_rows_by_loc_id = {
        str(row.get("loc_id") or ""): row for row in marine_df.to_dict("records")
    }
    return [
        _resolve_point_to_marine_stack(
            float(point["lon"]), float(point["lat"]),
            include_geometry=include_geometry,
            marine_df=marine_df,
            candidate_loc_ids=set(candidate_ids.get(position, [])),
            candidates_are_exact=True,
            geometry_cache=geometry_cache,
            marine_rows_by_loc_id=marine_rows_by_loc_id,
        )
        for position, point in enumerate(point_items)
    ]


def _get_name_standardizer() -> NameStandardizer:
    global _NAME_STANDARDIZER
    if _NAME_STANDARDIZER is None:
        _NAME_STANDARDIZER = NameStandardizer()
    return _NAME_STANDARDIZER


def _normalize_admin_text(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return ""
    except Exception:
        if value is None:
            return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = text.replace("&", " and ")
    text = _ADMIN_TEXT_SUFFIX_RE.sub(" ", text)
    text = text.replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("ß", "ss")
    text = _TEXT_COLLAPSE_RE.sub(" ", text)
    text = " ".join(text.split())
    return _ADMIN_TEXT_ALIASES.get(text, text)


def _resolve_country_geometry_name(
    query: str,
    *,
    country_hint: str,
    admin_level: int,
) -> dict[str, Any] | None:
    country = str(country_hint or "").strip().upper()
    # Hosted point resolution already selects and queries the admitted exact
    # Admin0-3 spine. Reuse that same lightweight identity lane for names;
    # loading through the generic geometry path made this lookup depend on a
    # second cloud-accessibility probe and could return no frame even while
    # point resolution for the country was healthy.
    df = (
        shallow_identity_level_rows(country, admin_level)
        if is_cloud_mode() and 0 <= int(admin_level) <= 3
        else None
    )
    if df is None:
        df = load_country_parquet(country, admin_level=admin_level)
    if df is None or df.empty:
        return None

    normalized_query = _normalize_admin_text(query)
    if not normalized_query:
        return None

    candidates: list[tuple[str, str | None]] = []
    for _, row in df.iterrows():
        loc_id = str(row.get("loc_id") or "").strip()
        if not loc_id:
            continue
        for field in ("name", "name_local", "iso_3166_2", "code"):
            value = row.get(field)
            normalized_value = _normalize_admin_text(value)
            if normalized_value and normalized_value == normalized_query:
                candidates.append((loc_id, row.get("name")))
                break

    if not candidates:
        return None

    unique_candidates = []
    seen_loc_ids: set[str] = set()
    for loc_id, name in candidates:
        if loc_id in seen_loc_ids:
            continue
        seen_loc_ids.add(loc_id)
        unique_candidates.append((loc_id, name))

    if len(unique_candidates) != 1:
        return None

    loc_id, name = unique_candidates[0]
    return _build_match_entry(
        loc_id,
        admin_level=admin_level,
        name=name,
        method="geometry_name_lookup",
        source_loc_id=loc_id,
    )


def _resolve_country_name_from_global_geometry(query: str) -> dict[str, Any] | None:
    # Name-to-loc_id matching reads the name column only. The Display bank
    # carries every Admin0 name and costs ~5 MB against the exact bank's
    # 400 MB+, which this path never needed.
    df = load_global_country_display_frame()
    if df is None or df.empty:
        return None

    normalized_query = _normalize_admin_text(query)
    if not normalized_query:
        return None

    known_loc_ids: dict[str, Any] = {}
    for _, row in df.iterrows():
        loc_id = str(row.get("loc_id") or "").strip()
        if not loc_id:
            continue
        name = row.get("name")
        if _normalize_admin_text(name) == normalized_query:
            return _build_match_entry(
                loc_id,
                admin_level=0,
                name=name,
                method="geometry_name_lookup",
                source_loc_id=loc_id,
            )
        known_loc_ids.setdefault(loc_id.upper(), name)

    # Fall back to the shared synonym crosswalk only after every formal
    # geometry name has failed, so an exact geometry match always wins. The
    # standardizer already indexes common names, abbreviations, and codes, so
    # country synonyms stay in one place instead of being duplicated here.
    alias_iso3 = _get_name_standardizer().get_country_code(query)
    if alias_iso3 and alias_iso3 in known_loc_ids:
        return _build_match_entry(
            alias_iso3,
            admin_level=0,
            name=known_loc_ids[alias_iso3],
            method="country_synonym_lookup",
            source_loc_id=alias_iso3,
        )
    return None


def _build_usa_tribal_aliases() -> tuple[dict[str, str], dict[str, str]]:
    """Return (exact_aliases, derived_aliases) for USA tribal areas.

    Exact names ("Onondaga Nation Reservation") are unambiguous and may resolve
    ahead of the admin spine. Suffix-stripped names ("Onondaga") are a guess and
    routinely collide with county names, so they are kept separate and consulted
    only after admin resolution fails. Tribal areas are a sidechain; a sidechain
    guess must never shadow the admin spine.
    """
    alias_map: dict[str, str] = {}
    derived_map: dict[str, str] = {}
    file_path = GEOMETRY_DIR / "countries" / "USA" / "tribal" / "USA.parquet"
    if not file_path.exists():
        return alias_map, derived_map

    try:
        df = pd.read_parquet(file_path, columns=["loc_id", "name"])
    except Exception:
        return alias_map, derived_map

    stripped_candidates: dict[str, set[str]] = {}
    for row in df.itertuples(index=False):
        loc_id = str(getattr(row, "loc_id", "") or "").strip()
        name = str(getattr(row, "name", "") or "").strip()
        if not loc_id or not name:
            continue
        normalized_name = _normalize_admin_text(name)
        if normalized_name:
            alias_map.setdefault(normalized_name, loc_id)
        stripped = _normalize_admin_text(_USA_TRIBAL_ALIAS_SUFFIX_RE.sub(" ", name))
        if stripped and stripped != normalized_name:
            stripped_candidates.setdefault(stripped, set()).add(loc_id)

    for alias_text, loc_ids in stripped_candidates.items():
        if len(loc_ids) == 1 and alias_text not in alias_map:
            derived_map[alias_text] = next(iter(loc_ids))
    return alias_map, derived_map


def _load_country_direct_location_aliases(country_hint: str | None) -> dict[str, str]:
    iso3 = str(country_hint or "").strip().upper()
    if not iso3:
        return {}
    cached = _COUNTRY_DIRECT_LOCATION_ALIAS_CACHE.get(iso3)
    if cached is not None:
        return cached

    alias_map: dict[str, str] = {}
    for alias, loc_id in get_country_location_aliases(iso3).items():
        alias_text = _normalize_admin_text(alias)
        loc_id_text = str(loc_id or "").strip()
        if alias_text and loc_id_text:
            alias_map.setdefault(alias_text, loc_id_text)

    if iso3 == "USA":
        for alias_text, loc_id in _build_usa_tribal_aliases()[0].items():
            alias_map.setdefault(alias_text, loc_id)

    _COUNTRY_DIRECT_LOCATION_ALIAS_CACHE[iso3] = alias_map
    return alias_map


def _load_country_fallback_location_aliases(country_hint: str | None) -> dict[str, str]:
    """Sidechain aliases that are only safe once admin resolution has failed."""
    iso3 = str(country_hint or "").strip().upper()
    if not iso3:
        return {}
    cached = _COUNTRY_FALLBACK_LOCATION_ALIAS_CACHE.get(iso3)
    if cached is not None:
        return cached

    alias_map: dict[str, str] = {}
    if iso3 == "USA":
        alias_map.update(_build_usa_tribal_aliases()[1])

    _COUNTRY_FALLBACK_LOCATION_ALIAS_CACHE[iso3] = alias_map
    return alias_map


def _resolve_country_direct_location_alias(query: str, *, country_hint: str | None) -> str | None:
    normalized_query = _normalize_admin_text(query)
    if not normalized_query:
        return None
    return _load_country_direct_location_aliases(country_hint).get(normalized_query)


def _resolve_country_fallback_location_alias(query: str, *, country_hint: str | None) -> str | None:
    normalized_query = _normalize_admin_text(query)
    if not normalized_query:
        return None
    return _load_country_fallback_location_aliases(country_hint).get(normalized_query)


def _prefer_same_name_ancestor(
    local_loc_id: str,
    query: str,
    *,
    country: str | None,
    matched_level: int | None,
    standardizer,
) -> str:
    """Prefer a shallower ancestor that carries the identical name.

    Name lookup runs deepest-level-first so "Harris County" resolves to the
    county rather than the state. That ordering misfires when a region has a
    single subdivision of the same name: "Fukuoka Prefecture" and "Australian
    Capital Territory" each exist at admin_1 and again at admin_2, and the
    deeper row is a structural artifact rather than what the caller meant.
    Only an exact parent carrying the exact same name wins, so genuinely
    distinct deeper places are untouched.
    """
    if not local_loc_id or matched_level is None or matched_level < 1:
        return local_loc_id

    shallower_level = int(matched_level) - 1
    shallower_local = ""
    try:
        shallower = standardizer.get_loc_id_from_name(
            query, country=country, admin_level=shallower_level
        )
        if shallower:
            shallower_local = translate_geometry_id_to_local_id(shallower)
    except Exception:
        shallower_local = ""

    if not shallower_local and country and shallower_level in {1, 2}:
        # The standardizer and the geometry-name index cover different rows, so
        # a shallower match may only exist in the geometry names.
        fallback = _resolve_country_geometry_name(
            query, country_hint=country, admin_level=shallower_level
        )
        if fallback:
            shallower_local = str(fallback.get("loc_id") or "")

    if not shallower_local or shallower_local == local_loc_id:
        return local_loc_id

    parent = get_parent_loc_id(local_loc_id)
    if not parent:
        return local_loc_id
    # Compare in the same namespace: the parent edge may still be a geometry id
    # while the shallower match has already been translated to local form.
    parent_local = translate_geometry_id_to_local_id(str(parent))
    candidates = {
        str(parent).strip().upper(),
        str(parent_local).strip().upper(),
    }
    if str(shallower_local).strip().upper() in candidates:
        return shallower_local
    return local_loc_id


def _level_key(admin_level: int | None) -> str | None:
    if admin_level is None or admin_level < 0:
        return None
    return f"admin_{int(admin_level)}"


def _build_match_entry(
    loc_id: str,
    *,
    admin_level: int | None,
    name: str | None = None,
    method: str,
    confidence: float = 1.0,
    canonical_match: bool = True,
    source_loc_id: str | None = None,
) -> dict[str, Any]:
    canonical_loc_id = canonicalize_loc_id(loc_id)
    inferred_level = infer_admin_level_from_loc_id(canonical_loc_id)
    return {
        "loc_id": canonical_loc_id,
        "admin_level": int(admin_level if admin_level is not None else inferred_level or 0),
        "name": str(name).strip() if isinstance(name, str) and str(name).strip() else None,
        "method": method,
        "confidence": float(confidence),
        "canonical_match": bool(canonical_match),
        "source_loc_id": source_loc_id or canonical_loc_id,
    }


def _resolve_local_deep_geometry_name(loc_id: str, admin_level: int) -> str | None:
    """Read one canonical Admin 3+ row to label a derived point-result parent.

    Deep point resolution deliberately derives its parent chain from the
    canonical loc_id rather than loading whole state files.  That made the
    parent IDs correct but left their display names blank in the point popup.
    This is a projected, exact-ID read of a single partition row.
    """
    if admin_level < 3:
        return None
    parts = canonicalize_loc_id(loc_id).split("-")
    if len(parts) < 2:
        return None
    iso3 = parts[0]
    state_abbrev = parts[1] if iso3 == "USA" else None
    try:
        frame = load_subcounty_geometry(
            iso3,
            admin_level=admin_level,
            state_abbrev=state_abbrev,
            loc_ids=[loc_id],
            columns=["loc_id", "name"],
        )
    except Exception:
        return None
    if frame is None or frame.empty:
        return None
    value = frame.iloc[0].get("name")
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_bbox(payload: dict[str, Any]) -> dict[str, float] | None:
    bounds = payload.get("bbox") or payload.get("bounds")
    if not isinstance(bounds, dict):
        return None
    west = _coerce_float(bounds.get("west") or bounds.get("min_lon") or bounds.get("xmin"))
    south = _coerce_float(bounds.get("south") or bounds.get("min_lat") or bounds.get("ymin"))
    east = _coerce_float(bounds.get("east") or bounds.get("max_lon") or bounds.get("xmax"))
    north = _coerce_float(bounds.get("north") or bounds.get("max_lat") or bounds.get("ymax"))
    if None in {west, south, east, north}:
        return None
    return {"west": west, "south": south, "east": east, "north": north}


def _normalize_place_components(payload: dict[str, Any]) -> dict[str, Any]:
    components = payload.get("components")
    if not isinstance(components, dict):
        components = {}
    out = {
        "street_number": components.get("street_number") or payload.get("street_number"),
        "route": components.get("route") or payload.get("route"),
        "locality": components.get("locality") or payload.get("locality") or payload.get("city"),
        "admin_2_name": components.get("admin_2_name") or components.get("county") or payload.get("county"),
        "admin_1_name": components.get("admin_1_name") or components.get("admin_area") or payload.get("state") or payload.get("province"),
        "postal_code": components.get("postal_code") or payload.get("postal_code") or payload.get("zip"),
        "country_name": components.get("country_name") or components.get("country") or payload.get("country"),
        "country_code": (
            components.get("country_code")
            or payload.get("country_code")
            or payload.get("country_iso2")
            or payload.get("country_iso3")
        ),
    }
    return {key: value for key, value in out.items() if isinstance(value, str) and value.strip()}


def _normalize_resolved_place(
    resolved_place: dict[str, Any] | None,
    *,
    query: str,
    provider: str,
) -> dict[str, Any] | None:
    payload = resolved_place if isinstance(resolved_place, dict) else {}
    lat = _coerce_float(payload.get("lat"))
    lng = _coerce_float(payload.get("lng") or payload.get("lon"))

    geometry = payload.get("geometry")
    if isinstance(geometry, dict):
        location = geometry.get("location")
        if isinstance(location, dict):
            lat = lat if lat is not None else _coerce_float(location.get("lat"))
            lng = lng if lng is not None else _coerce_float(location.get("lng") or location.get("lon"))

    label = (
        payload.get("formatted_address")
        or payload.get("label")
        or payload.get("address")
        or payload.get("query")
        or query
    )
    place_type = (
        payload.get("place_type")
        or payload.get("type")
        or ("street_address" if payload.get("place_id") else "place")
    )
    normalized = {
        "query": str(query or "").strip(),
        "provider": str(provider or payload.get("provider") or "").strip() or "unknown",
        "resolved_place": {
            "label": str(label or "").strip(),
            "place_id": str(payload.get("place_id") or "").strip() or None,
            "place_type": str(place_type or "").strip() or None,
            "lat": lat,
            "lng": lng,
            "bbox": _extract_bbox(payload),
            "components": _normalize_place_components(payload),
        },
    }
    if normalized["resolved_place"]["lat"] is None or normalized["resolved_place"]["lng"] is None:
        return normalized
    return normalized


def _looks_like_us_zip(query: str, country_hint: str | None = None) -> bool:
    value = str(query or "").strip()
    if not _USA_ZIP_RE.fullmatch(value):
        return False
    if not country_hint:
        return True
    hint = str(country_hint).strip().upper()
    return hint in {"USA", "US", "UNITED STATES", "UNITED STATES OF AMERICA"}


def _resolve_us_zip_to_stack(query: str) -> dict[str, Any]:
    value = str(query or "").strip()
    if not _looks_like_us_zip(value):
        return {}

    row = usa_zip_lookup(value)
    if not isinstance(row, dict):
        return {
            "query": value,
            "match_type": "postal_code",
            "matches": {},
            "deepest_resolved_loc_id": None,
            "deepest_resolved_admin_level": None,
            "should_persist_deepest_loc_id": False,
            "error": "no ZIP crosswalk match found",
        }

    matches: dict[str, dict[str, Any]] = {
        "admin_0": _build_match_entry(
            row.get("country_loc_id") or "USA",
            admin_level=0,
            method="postal_crosswalk",
        )
    }
    state_loc_id = str(row.get("state_loc_id") or "").strip()
    county_loc_id = str(row.get("county_loc_id") or "").strip()
    if state_loc_id:
        matches["admin_1"] = _build_match_entry(
            state_loc_id,
            admin_level=1,
            name=row.get("state_abbrev"),
            method="postal_crosswalk",
        )
    if county_loc_id:
        matches["admin_2"] = _build_match_entry(
            county_loc_id,
            admin_level=2,
            name=row.get("county_name"),
            method="postal_crosswalk",
        )

    deepest_loc_id = county_loc_id or state_loc_id or "USA"
    deepest_level = _level_key(infer_admin_level_from_loc_id(deepest_loc_id))
    return {
        "query": value,
        "match_type": "postal_code",
        "postal_code": value,
        "postal_system": "usa_zip_crosswalk",
        "postal_metadata": {
            "county_count": row.get("county_count"),
            "all_counties": row.get("all_counties") or [],
        },
        "matches": matches,
        "deepest_resolved_loc_id": deepest_loc_id,
        "deepest_resolved_admin_level": deepest_level,
        "should_persist_deepest_loc_id": bool(deepest_loc_id),
    }


def _iter_parent_chain(loc_id: str, stop_level_inclusive: int) -> list[tuple[int, str]]:
    current = canonicalize_loc_id(loc_id)
    current_level = infer_admin_level_from_loc_id(current)
    if current_level is None:
        return []

    out: list[tuple[int, str]] = []
    while current_level is not None and current_level > stop_level_inclusive:
        out.append((current_level, current))
        parent = get_parent_loc_id(current)
        if not parent:
            break
        current = parent
        current_level = infer_admin_level_from_loc_id(current)
    if current_level is not None and current_level >= stop_level_inclusive:
        out.append((current_level, current))
    return out


def resolve_admin_text_to_loc_id(
    query: str,
    *,
    country_hint: str | None = None,
    admin_level_hint: int | None = None,
) -> dict[str, Any]:
    value = str(query or "").strip()
    if not value:
        return {"query": value, "error": "query is required", "matches": {}}

    postal_match = _resolve_us_zip_to_stack(value)
    if postal_match.get("match_type") == "postal_code":
        return postal_match

    if _LOC_ID_RE.match(value):
        family = classify_loc_id_family(value)
        if family == "event_or_entity":
            return {
                "query": value,
                "match_type": "non_geometry_identifier",
                "matches": {},
                "deepest_resolved_loc_id": None,
                "deepest_resolved_admin_level": None,
                "should_persist_deepest_loc_id": False,
                "loc_id_family": family,
                "error": "non-geometry identifier requires exact event or entity routing",
            }
        loc_id = translate_geometry_id_to_local_id(value)
        admin_level = infer_admin_level_from_loc_id(loc_id)
        key = _level_key(admin_level)
        entry = _build_match_entry(
            loc_id,
            admin_level=admin_level,
            method="loc_id_passthrough",
            source_loc_id=value,
        )
        return {
            "query": value,
            "match_type": "direct_loc_id",
            "loc_id_family": family,
            "matches": {key: entry} if key else {},
            "deepest_resolved_loc_id": loc_id,
            "deepest_resolved_admin_level": key,
            "should_persist_deepest_loc_id": True,
        }

    aliased_loc_id = _resolve_country_direct_location_alias(value, country_hint=country_hint)
    if not aliased_loc_id:
        normalized_value = _normalize_admin_text(value)
        reviewed_aliases = (load_conversions() or {}).get("location_aliases", {})
        for alias, candidate_loc_id in reviewed_aliases.items():
            if _normalize_admin_text(alias) == normalized_value:
                aliased_loc_id = canonicalize_loc_id(candidate_loc_id)
                break
    if aliased_loc_id:
        family = classify_loc_id_family(aliased_loc_id)
        admin_level = infer_admin_level_from_loc_id(aliased_loc_id) if family in {"admin_0", "admin_local", "admin_geometry"} else None
        key = _level_key(admin_level)
        entry = None
        if key:
            entry = _build_match_entry(
                aliased_loc_id,
                admin_level=admin_level,
                name=value,
                method="country_location_alias",
                source_loc_id=aliased_loc_id,
            )
        result = {
            "query": value,
            "match_type": "direct_location_alias",
            "loc_id_family": family,
            "matches": {key: entry} if key and entry else {},
            "deepest_resolved_loc_id": aliased_loc_id,
            "deepest_resolved_admin_level": key,
            "should_persist_deepest_loc_id": True,
        }
        if key is None:
            result["deepest_resolved_family"] = family
        return result

    standardizer: NameStandardizer | None = None

    def get_standardizer() -> NameStandardizer:
        nonlocal standardizer
        if standardizer is None:
            standardizer = _get_name_standardizer()
        return standardizer

    country = str(country_hint or "").strip().upper() or None

    explicit_text_level = _explicit_admin_level_from_text(value)
    effective_level_hint = admin_level_hint if admin_level_hint is not None else explicit_text_level
    level_order: list[int | None]
    if effective_level_hint is not None:
        level_order = [int(effective_level_hint)]
    elif country:
        # Let the shared country geometry spine resolve the deepest matching
        # admin level first instead of assuming province/state or county only.
        level_order = [2, 1, None, 0]
    else:
        level_order = [0]

    for admin_level in level_order:
        fallback_entry = None
        # Country-scoped exact identities are cheaper and more authoritative
        # than booting the general name standardizer. The maintained USA
        # Admin0-2 slice is already a required Railway prewarm task.
        if country and admin_level in {1, 2, 3} and is_cloud_mode():
            fallback_entry = _resolve_country_geometry_name(
                value,
                country_hint=country,
                admin_level=int(admin_level),
            )
        resolved = (
            None
            if fallback_entry is not None
            else get_standardizer().get_loc_id_from_name(
                value, country=country, admin_level=admin_level,
            )
        )
        if not resolved:
            if fallback_entry is not None:
                pass
            elif admin_level == 0:
                fallback_entry = _resolve_country_name_from_global_geometry(value)
            elif country and admin_level in {1, 2}:
                fallback_entry = _resolve_country_geometry_name(
                    value,
                    country_hint=country,
                    admin_level=int(admin_level),
                )
            if fallback_entry is None:
                continue
            fallback_loc_id = str(fallback_entry.get("loc_id") or "")
            preferred_loc_id = fallback_loc_id
            if effective_level_hint is None:
                preferred_loc_id = _prefer_same_name_ancestor(
                    fallback_loc_id,
                    value,
                    country=country,
                    matched_level=fallback_entry.get("admin_level"),
                    standardizer=get_standardizer(),
                )
            if preferred_loc_id != fallback_loc_id:
                fallback_entry = _build_match_entry(
                    preferred_loc_id,
                    admin_level=infer_admin_level_from_loc_id(preferred_loc_id),
                    name=value,
                    method="geometry_name_lookup",
                    source_loc_id=preferred_loc_id,
                )
            key = _level_key(fallback_entry.get("admin_level"))
            return {
                "query": value,
                "match_type": "direct_admin_name",
                "matches": {key: fallback_entry} if key else {},
                "deepest_resolved_loc_id": fallback_entry.get("loc_id"),
                "deepest_resolved_admin_level": key,
                "should_persist_deepest_loc_id": True,
            }
        local_loc_id = translate_geometry_id_to_local_id(resolved)
        if effective_level_hint is None:
            local_loc_id = _prefer_same_name_ancestor(
                local_loc_id,
                value,
                country=country,
                matched_level=admin_level,
                standardizer=get_standardizer(),
            )
        resolved_level = infer_admin_level_from_loc_id(local_loc_id)
        key = _level_key(resolved_level)
        entry = _build_match_entry(
            local_loc_id,
            admin_level=resolved_level,
            method="name_lookup",
            source_loc_id=resolved,
        )
        return {
            "query": value,
            "match_type": "direct_admin_name",
            "matches": {key: entry} if key else {},
            "deepest_resolved_loc_id": local_loc_id,
            "deepest_resolved_admin_level": key,
            "should_persist_deepest_loc_id": True,
        }

    # Admin resolution failed, so a derived sidechain alias is now safe to use.
    fallback_loc_id = _resolve_country_fallback_location_alias(value, country_hint=country)
    if fallback_loc_id:
        family = classify_loc_id_family(fallback_loc_id)
        admin_level = (
            infer_admin_level_from_loc_id(fallback_loc_id)
            if family in {"admin_0", "admin_local", "admin_geometry"}
            else None
        )
        key = _level_key(admin_level)
        entry = (
            _build_match_entry(
                fallback_loc_id,
                admin_level=admin_level,
                name=value,
                method="country_location_alias_fallback",
                source_loc_id=fallback_loc_id,
            )
            if key
            else None
        )
        result = {
            "query": value,
            "match_type": "direct_location_alias",
            "loc_id_family": family,
            "matches": {key: entry} if key and entry else {},
            "deepest_resolved_loc_id": fallback_loc_id,
            "deepest_resolved_admin_level": key,
            "should_persist_deepest_loc_id": True,
        }
        if key is None:
            result["deepest_resolved_family"] = family
        return result

    return {
        "query": value,
        "match_type": "direct_admin_name",
        "matches": {},
        "deepest_resolved_loc_id": None,
        "deepest_resolved_admin_level": None,
        "should_persist_deepest_loc_id": False,
        "error": "no direct admin-name match found",
    }


def resolve_place_to_point(
    query: str,
    *,
    resolved_place: dict[str, Any] | None = None,
    provider: str = "google",
    country_hint: str | None = None,
) -> dict[str, Any]:
    value = str(query or "").strip()
    if resolved_place is None:
        local_place = resolve_populated_place(value, country_hint=country_hint)
        if local_place and local_place.get("status") == "ambiguous":
            return {
                "query": value,
                "provider": "daedalmap_place_index",
                "error": "place name is ambiguous; provide a country or region qualifier",
                "candidates": local_place.get("candidates") or [],
            }
        if local_place and local_place.get("status") == "matched":
            match = local_place["match"]
            normalized = _normalize_resolved_place(
                {
                    "label": match.get("display_name") or match.get("matched_name") or value,
                    "place_id": match.get("loc_id"),
                    "place_type": "populated_place",
                    "lat": match.get("latitude"),
                    "lng": match.get("longitude"),
                    "state": match.get("region_label"),
                    "country_code": match.get("country_code"),
                },
                query=value,
                provider="daedalmap_place_index",
            )
            if normalized is not None:
                normalized["resolved_place"]["canonical_place_loc_id"] = match.get("loc_id")
                normalized["resolved_place"]["feature_subtype"] = match.get("subtype")
                normalized["resolved_place"]["matched_name"] = match.get("matched_name")
                normalized["resolved_place"]["source_system"] = match.get("source_system")
                normalized["resolved_place"]["source_release"] = match.get("source_release")
                return normalized

    direct_match = resolve_admin_text_to_loc_id(value, country_hint=country_hint)
    if direct_match.get("matches"):
        return {
            "query": value,
            "provider": "direct_admin_text",
            "resolved_place": None,
            "direct_admin_match": direct_match,
        }

    normalized = _normalize_resolved_place(resolved_place, query=value, provider=provider)
    if normalized is None:
        return {
            "query": value,
            "provider": provider,
            "error": "resolved_place payload is required when no direct admin-text match exists",
        }
    if normalized["resolved_place"].get("lat") is None or normalized["resolved_place"].get("lng") is None:
        normalized["error"] = "resolved_place payload does not include a usable point"
    return normalized


def resolve_point_to_loc_id_stack(
    lon: float,
    lat: float,
    *,
    include_geometry: bool = False,
) -> dict[str, Any]:
    requested_lon = float(lon)
    requested_lat = float(lat)
    normalized_lon = normalize_geometry_longitude(requested_lon)
    raw = legacy_resolve_point_to_location(normalized_lon, requested_lat, include_geometry=include_geometry)
    if not isinstance(raw, dict):
        return _attach_requested_point(
            {"point": {"lon": normalized_lon, "lat": requested_lat}, "error": "point resolver returned invalid payload"},
            lon=requested_lon,
            lat=requested_lat,
            normalized_lon=normalized_lon,
        )
    if raw.get("error"):
        marine_result = _resolve_point_to_marine_stack(normalized_lon, requested_lat, include_geometry=include_geometry)
        if marine_result is not None:
            return _attach_requested_point(marine_result, lon=requested_lon, lat=requested_lat, normalized_lon=normalized_lon)
        return _attach_requested_point(raw, lon=requested_lon, lat=requested_lat, normalized_lon=normalized_lon)

    matches: dict[str, dict[str, Any]] = {}
    for item in raw.get("stack") or []:
        source_loc_id = str(item.get("loc_id") or "").strip()
        if not source_loc_id:
            continue
        local_loc_id = translate_geometry_id_to_local_id(source_loc_id)
        admin_level = item.get("admin_level")
        resolved_level = int(admin_level) if admin_level is not None else infer_admin_level_from_loc_id(local_loc_id)
        key = _level_key(resolved_level)
        if not key:
            continue
        matches[key] = _build_match_entry(
            local_loc_id,
            admin_level=resolved_level,
            name=item.get("name"),
            method="point_containment",
            source_loc_id=source_loc_id,
        )

    matched = raw.get("matched") or {}
    deepest_source_loc_id = str(matched.get("loc_id") or "").strip()
    deepest_local_loc_id = translate_geometry_id_to_local_id(deepest_source_loc_id) if deepest_source_loc_id else None
    deepest_level = matched.get("admin_level")
    deepest_level = int(deepest_level) if deepest_level is not None else infer_admin_level_from_loc_id(deepest_local_loc_id)

    if deepest_local_loc_id and deepest_level is not None:
        for level_value, loc_id_value in _iter_parent_chain(deepest_local_loc_id, 3):
            key = _level_key(level_value)
            if not key or key in matches:
                continue
            matches[key] = _build_match_entry(
                loc_id_value,
                admin_level=level_value,
                name=_resolve_local_deep_geometry_name(loc_id_value, level_value),
                method="derived_parent_chain",
                canonical_match=True,
            )

        deepest_key = _level_key(deepest_level)
        if deepest_key:
            existing = matches.get(deepest_key)
            name = (existing or {}).get("name") or matched.get("name")
            matches[deepest_key] = _build_match_entry(
                deepest_local_loc_id,
                admin_level=deepest_level,
                name=name,
                method=(existing or {}).get("method") or "point_containment",
                source_loc_id=deepest_source_loc_id or deepest_local_loc_id,
            )

    ordered_matches = {
        key: matches[key]
        for key in sorted(matches.keys(), key=lambda value: int(value.split("_", 1)[1]))
    }

    normalized_stack = [
        {
            "loc_id": entry["loc_id"],
            "name": entry.get("name"),
            "admin_level": int(entry["admin_level"]),
        }
        for entry in ordered_matches.values()
    ]
    deepest_entry = ordered_matches.get(_level_key(deepest_level) or "")
    join_keys = {
        f"{key}_loc_id": entry["loc_id"]
        for key, entry in ordered_matches.items()
        if entry.get("loc_id")
    }

    result = {
        "resolution_schema_version": "1.0.0",
        "point": raw.get("point") or {"lon": float(lon), "lat": float(lat)},
        "country": raw.get("country"),
        "matched": {
            "loc_id": deepest_local_loc_id,
            "name": (deepest_entry or {}).get("name") or matched.get("name"),
            "admin_level": int(deepest_level) if deepest_level is not None else None,
            "country_name": (raw.get("country") or {}).get("name"),
            "iso3": (raw.get("country") or {}).get("loc_id") or matched.get("iso3"),
        },
        "stack": normalized_stack,
        "matches": ordered_matches,
        "deepest_resolved_loc_id": deepest_local_loc_id,
        "deepest_resolved_admin_level": _level_key(deepest_level),
        # Flat, stable columns for CSV/Parquet/manual joins. Consumers do not
        # need geometry—or an LLM—to recover every maintained admin grain from
        # a coordinate result.
        "join_keys": join_keys,
        "join_grain": _level_key(deepest_level),
        "overlap_families": raw.get("overlap_families") or [],
        "should_persist_deepest_loc_id": bool(deepest_local_loc_id),
        "legacy_payload": raw,
    }
    if include_geometry and "geojson" in raw:
        result["geojson"] = raw["geojson"]
    return _attach_requested_point(result, lon=requested_lon, lat=requested_lat, normalized_lon=normalized_lon)


def resolve_place_to_loc_id_stack(
    query: str,
    *,
    resolved_place: dict[str, Any] | None = None,
    provider: str = "google",
    country_hint: str | None = None,
    admin_level_hint: int | None = None,
    include_geometry: bool = False,
) -> dict[str, Any]:
    value = str(query or "").strip()

    # A maintained administrative name/code is authoritative and must win
    # before a same-named city or gazetteer point. For example, "Virginia"
    # resolves to the USA Admin1; a city lookup remains available when the
    # administrative resolver has no unique match.
    direct_match = resolve_admin_text_to_loc_id(
        value,
        country_hint=country_hint,
        admin_level_hint=admin_level_hint,
    )
    if direct_match.get("matches"):
        direct_match["resolution_mode"] = "direct_admin_text"
        return direct_match

    local_place = resolve_populated_place(value, country_hint=country_hint) if resolved_place is None else None
    if local_place:
        point_payload = resolve_place_to_point(
            value,
            resolved_place=resolved_place,
            provider=provider,
            country_hint=country_hint,
        )
        if point_payload.get("error"):
            point_payload["resolution_mode"] = "populated_place_index"
            return point_payload
        place = point_payload.get("resolved_place") or {}
        stack_payload = resolve_point_to_loc_id_stack(
            place.get("lng"), place.get("lat"), include_geometry=include_geometry
        )
        stack_payload["query"] = value
        stack_payload["provider"] = point_payload.get("provider")
        stack_payload["resolved_place"] = place
        stack_payload["resolution_mode"] = "populated_place_index"
        return stack_payload

    point_payload = resolve_place_to_point(
        value,
        resolved_place=resolved_place,
        provider=provider,
        country_hint=country_hint,
    )
    if point_payload.get("error"):
        point_payload["resolution_mode"] = "place_payload"
        return point_payload

    place = point_payload.get("resolved_place") or {}
    lat = place.get("lat")
    lng = place.get("lng")
    if lat is None or lng is None:
        point_payload["resolution_mode"] = "place_payload"
        point_payload["error"] = point_payload.get("error") or "resolved place does not include a usable point"
        return point_payload

    stack_payload = resolve_point_to_loc_id_stack(lng, lat, include_geometry=include_geometry)
    stack_payload["query"] = value
    stack_payload["provider"] = point_payload.get("provider")
    stack_payload["resolved_place"] = place
    stack_payload["resolution_mode"] = "place_payload"
    return stack_payload
