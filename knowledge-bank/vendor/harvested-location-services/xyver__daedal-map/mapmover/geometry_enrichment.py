"""
Geometry enrichment functions.
Handles loading the shared world bootstrap geometry and enriching data features
with country-level geometry when finer geometry is not available.
"""

import json
import logging
import re
import pandas as pd

from .foundation_helpers import load_global_country_display_frame, load_reference_json
from .geography import get_fallback_coordinates, get_iso_codes
from .runtime.geography_reference import load_country_name_to_iso3_map

logger = logging.getLogger("mapmover")

# Cache for geometry data to avoid repeated file reads
_geometry_cache = None

# Cache for country name aliases
_COUNTRY_ALIASES_CACHE = None


def _normalize_country_name(value: str) -> str:
    """Normalize a country label before shared ISO3 matching."""
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return _load_country_aliases().get(text, text)


def _resolve_bootstrap_country_code(row: pd.Series, name_to_iso3: dict[str, str]) -> str:
    """
    Resolve a world-bootstrap row to the ISO3 key expected by country callers.

    The Admin0 Display product is identity-shaped, and this adapter exposes only
    rows that can be addressed as a country in the shared runtime contract.
    """
    loc_id = str(row.get("loc_id") or "").strip().upper()
    if re.fullmatch(r"[A-Z]{3}", loc_id):
        return loc_id

    normalized_name = _normalize_country_name(row.get("name"))
    if not normalized_name:
        return ""
    return str(name_to_iso3.get(normalized_name) or "").strip().upper()


def _load_country_aliases() -> dict:
    """Load country name aliases from reference file."""
    global _COUNTRY_ALIASES_CACHE
    if _COUNTRY_ALIASES_CACHE is not None:
        return _COUNTRY_ALIASES_CACHE

    data = load_reference_json("country_aliases.json")
    if isinstance(data, dict):
        _COUNTRY_ALIASES_CACHE = data.get("aliases", {})
        logger.debug(f"Loaded {len(_COUNTRY_ALIASES_CACHE)} country aliases from reference file")
    else:
        logger.warning("Error loading country_aliases.json")
        _COUNTRY_ALIASES_CACHE = {}
    return _COUNTRY_ALIASES_CACHE


def get_geometry_lookup():
    """
    Load the shared world bootstrap geometry into a lookup dictionary.

    Returns dict mapping country_code (ISO3) -> geometry dict.
    The backing data source is the bounded Admin0 Display artifact because these
    polygons are attached to client response features. It is not an authority
    source for containment or derivation.
    """
    global _geometry_cache
    if _geometry_cache is not None:
        return _geometry_cache

    df = load_global_country_display_frame()
    if df is None or df.empty:
        logger.warning("Shared global bootstrap geometry is not available")
        return {}

    try:
        _geometry_cache = {}
        name_to_iso3 = load_country_name_to_iso3_map()

        for _, row in df.iterrows():
            code = _resolve_bootstrap_country_code(row, name_to_iso3)
            geom_str = row.get('geometry')

            if code and geom_str and pd.notna(geom_str):
                try:
                    geom = json.loads(geom_str) if isinstance(geom_str, str) else geom_str
                    _geometry_cache[code] = {
                        'geometry': geom,
                        'country_name': row.get('name') or row.get('country_name', ''),
                        'latitude': row.get('centroid_lat') if pd.notna(row.get('centroid_lat')) else row.get('latitude'),
                        'longitude': row.get('centroid_lon') if pd.notna(row.get('centroid_lon')) else row.get('longitude'),
                        'continent': row.get('continent', ''),
                        'subregion': row.get('subregion', '')
                    }
                except (json.JSONDecodeError, TypeError):
                    continue

        logger.info(f"Loaded geometry for {len(_geometry_cache)} countries from shared global bootstrap geometry")
        return _geometry_cache

    except Exception as e:
        logger.error(f"Error loading shared global bootstrap geometry: {e}")
        return {}


def get_country_coordinates(country_name, country_code=None):
    """
    Get approximate coordinates for a country by name or code.
    First checks the shared world bootstrap geometry lookup, then falls back to
    shared capital/fallback coordinates for countries missing from the bootstrap
    layer.

    Args:
        country_name: Name of the country
        country_code: Optional ISO 3-letter code for faster/more accurate lookup

    Returns:
        Tuple (lat, lon) or None if not found
    """
    # First try: Use country code with fallback coordinates (fastest for known missing countries)
    if country_code:
        fallback = get_fallback_coordinates(country_code)
        if fallback:
            return fallback

    # Second try: Look up in the shared world bootstrap geometry lookup
    geometry_lookup = get_geometry_lookup()
    if geometry_lookup:
        name_lower = country_name.lower().strip()

        for code, data in geometry_lookup.items():
            stored_name = data.get('country_name', '').lower().strip()
            if stored_name == name_lower or code == country_code:
                lat = data.get('latitude')
                lon = data.get('longitude')
                if lat is not None and lon is not None and pd.notna(lat) and pd.notna(lon):
                    return (float(lat), float(lon))

    # Third try: Find code by name and check fallback coordinates
    if not country_code:
        # Try to find the country code from the name
        iso_data = get_iso_codes()
        iso3_to_name = iso_data.get('iso3_to_name', {})
        name_lower = country_name.lower().strip()
        for code, name in iso3_to_name.items():
            if name.lower() == name_lower:
                fallback = get_fallback_coordinates(code)
                if fallback:
                    return fallback
                break

    return None


# Country name aliases - loaded from reference/country_aliases.json
# Use _load_country_aliases() to access


def enrich_with_geometry(features, name_col='country_name', code_col='country_code'):
    """
    Enrich GeoJSON features with geometry from the shared world bootstrap layer.

    For features missing geometry, looks up by country_code or country_name.
    Returns tuple: (enriched_features, missing_count, missing_names)
    """
    geometry_lookup = get_geometry_lookup()
    if not geometry_lookup:
        return features, len(features), []

    enriched = []
    missing_names = []

    for feature in features:
        props = feature.get('properties', {})
        geom = feature.get('geometry')

        # Already has geometry? Keep it
        if geom and geom.get('coordinates'):
            enriched.append(feature)
            continue

        # Try to find geometry by country code
        code = props.get(code_col) or props.get('country_code') or props.get('iso_code')
        if code and code in geometry_lookup:
            geo_data = geometry_lookup[code]
            feature['geometry'] = geo_data['geometry']
            enriched.append(feature)
            continue

        # Code exists but not in geometry_lookup - try fallback coordinates
        if code:
            fallback = get_fallback_coordinates(code)
            if fallback:
                lat, lon = fallback
                feature['geometry'] = {"type": "Point", "coordinates": [float(lon), float(lat)]}
                feature['properties']['_geometry_type'] = 'point'
                enriched.append(feature)
                continue

        # Try by country name (with alias support)
        name = props.get(name_col) or props.get('country_name') or props.get('country')
        if name:
            name_lower = name.lower().strip()
            # Apply alias if exists
            country_aliases = _load_country_aliases()
            lookup_name = country_aliases.get(name_lower, name_lower)

            # Direct lookup by iterating geometry cache
            found = False
            for geo_code, geo_data in geometry_lookup.items():
                geo_name = geo_data.get('country_name', '').lower()
                if geo_name == lookup_name or geo_name == name_lower:
                    feature['geometry'] = geo_data['geometry']
                    enriched.append(feature)
                    found = True
                    break

            if not found:
                # No polygon geometry found - try to create point marker
                lat = props.get('latitude') or props.get('lat')
                lon = props.get('longitude') or props.get('lon') or props.get('lng')

                # If no lat/lon in data, try to get coordinates from lookup or fallback
                if not (lat and lon):
                    coords = get_country_coordinates(name, country_code=code)
                    if coords:
                        lat, lon = coords

                if lat and lon:
                    try:
                        feature['geometry'] = {"type": "Point", "coordinates": [float(lon), float(lat)]}
                        feature['properties']['_geometry_type'] = 'point'  # Mark as point for UI
                        enriched.append(feature)
                    except (ValueError, TypeError):
                        if name not in missing_names:
                            missing_names.append(name)
                else:
                    if name not in missing_names:
                        missing_names.append(name)
        else:
            unknown_name = str(props.get(name_col, 'Unknown'))
            if unknown_name not in missing_names:
                missing_names.append(unknown_name)

    return enriched, len(missing_names), missing_names


def detect_missing_geometry(df):
    """
    Check if a DataFrame has a geometry column.

    Returns:
        bool: True if geometry column is missing, False if present
    """
    return 'geometry' not in df.columns


def get_geometry_source(geographic_level, data_catalog):
    """
    Select appropriate geometry dataset based on geographic level.

    Args:
        geographic_level: string - 'country', 'county', 'state', etc.
        data_catalog: list of catalog items

    Returns:
        dict: catalog item for the geometry source, or None if not found
    """
    # Map geographic levels to preferred geometry sources
    geometry_sources = {
        'country': 'geometry/global/display/admin_0.parquet',
        'county': 'usplaces.csv',
        'state': 'usplaces.csv',  # Can filter to state level
        'city': 'Populated Places.csv',
        'place': 'usplaces.csv'
    }

    preferred_file = geometry_sources.get(geographic_level.lower())
    if not preferred_file:
        print(f"Warning: No known geometry source for geographic level '{geographic_level}'")
        return None

    # Find the file in data catalog
    for item in data_catalog:
        if item['filename'] == preferred_file:
            return item

    print(f"Warning: Geometry source '{preferred_file}' not found in catalog")
    return None
