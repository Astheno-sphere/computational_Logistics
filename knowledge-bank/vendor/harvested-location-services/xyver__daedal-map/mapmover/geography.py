"""
Geography and regional grouping functions.
Handles country codes, region lookups, and coordinate fallbacks.
"""

import logging
from .runtime.geography_reference import (
    load_capital_coordinates_by_iso3,
    load_conversions as load_conversions_impl,
    load_iso_codes as load_iso_codes_impl,
)

# Compatibility alias backed by the shared runtime loader.
CONVERSIONS_DATA = load_conversions_impl() or {}

logger = logging.getLogger("mapmover")


def load_conversions():
    """Load conversions.json through the shared runtime loader path."""
    global CONVERSIONS_DATA
    try:
        CONVERSIONS_DATA = load_conversions_impl() or {}
        logger.debug(
            "Loaded conversions.json with %d regional groupings",
            len(CONVERSIONS_DATA.get("regional_groupings", {})),
        )
    except Exception as e:
        logger.warning("Failed to load conversions.json: %s", e)
        CONVERSIONS_DATA = {}
    return CONVERSIONS_DATA


def get_conversions_data():
    """Get conversions data through the shared runtime loader path."""
    global CONVERSIONS_DATA
    CONVERSIONS_DATA = load_conversions_impl() or {}
    return CONVERSIONS_DATA


def load_iso_codes():
    """Load ISO codes through the shared runtime loader path."""
    data = load_iso_codes_impl()
    if isinstance(data, dict):
        logger.debug("Loaded iso_codes.json with %d countries", len(data.get("iso3_to_name", {})))
        return data
    logger.warning("iso_codes.json not found")
    return {}


def get_iso_codes():
    """Get ISO codes through the shared runtime loader path."""
    return load_iso_codes()


def get_countries_in_region(region_name, query=None, dataset=None):
    """
    Get list of country codes for a region name (e.g., 'Europe', 'EU', 'G7').
    Returns list of ISO 3-letter country codes or empty list if not found.

    Args:
        region_name: The region to look up (e.g., 'Europe', 'Asia', 'G7')
        query: Optional - the user query for logging purposes
        dataset: Optional - the dataset being queried for logging purposes
    """
    conversions = get_conversions_data()

    # Check aliases first (e.g., "Europe" -> "WHO_European_Region")
    aliases = conversions.get('region_aliases', {})
    groupings = conversions.get('regional_groupings', {})

    logger.debug(f"Looking up region: '{region_name}'")

    # Try direct match first
    region_key = region_name
    if region_name in aliases:
        region_key = aliases[region_name]
        logger.debug(f"  Alias match: '{region_name}' -> '{region_key}'")

    # Try case-insensitive match
    if region_key not in groupings:
        for alias, key in aliases.items():
            if alias.lower() == region_name.lower():
                region_key = key
                logger.debug(f"  Case-insensitive alias match: '{alias}' -> '{key}'")
                break

    if region_key not in groupings:
        for group_name in groupings.keys():
            if group_name.lower().replace('_', ' ') == region_name.lower().replace('_', ' '):
                region_key = group_name
                logger.debug(f"  Grouping name match: '{group_name}'")
                break

    if region_key in groupings:
        countries = groupings[region_key].get('countries', [])
        logger.debug(f"  Found {len(countries)} countries in '{region_key}'")
        return countries

    # No match found - log this gap for tracking
    logger.warning(f"  No match found for region '{region_name}' (final key: '{region_key}')")
    # Import here to avoid circular imports
    from .logging_analytics import log_missing_region_to_cloud
    log_missing_region_to_cloud(region_name, query=query, dataset=dataset)
    return []


def get_country_names_from_codes(country_codes):
    """Convert ISO 3-letter codes to country names."""
    iso_data = get_iso_codes()
    iso3_to_name = iso_data.get('iso3_to_name', {})

    names = []
    for code in country_codes:
        if code in iso3_to_name:
            names.append(iso3_to_name[code])
        else:
            names.append(code)  # Fallback to code if not found
    return names


def get_limited_geometry_countries():
    """
    Get list of country codes that have limited or no polygon geometry.
    These countries may display as points instead of polygons.
    """
    limited_geom = get_conversions_data().get('limited_geometry_countries', {})
    # The fallback_coordinates dict keys are the country codes (only 3 truly missing)
    return set(limited_geom.get('fallback_coordinates', {}).keys())


def get_fallback_coordinates(country_code, log_missing=True):
    """
    Get fallback coordinates for countries missing from the shared world
    bootstrap geometry layer.
    First checks Populated Places capitals, then conversions.json fallback.
    Returns (lat, lon) tuple or None if not found.

    Args:
        country_code: ISO-3 country code
        log_missing: If True, log missing places to the hosted control plane for tracking
    """
    if not country_code:
        return None

    # 1. First try the shared runtime capital-coordinate spine
    capitals = load_capital_coordinates_by_iso3()
    if country_code in capitals:
        cap = capitals[country_code]
        if cap.get('lat') and cap.get('lon'):
            return (cap['lat'], cap['lon'])

    # 2. Fall back to conversions.json (only 3 countries: COK, NIU, NRU)
    limited_geom = get_conversions_data().get('limited_geometry_countries', {})
    coords_data = limited_geom.get('fallback_coordinates', {})

    if country_code in coords_data:
        coords = coords_data[country_code].get('coords')
        if coords and len(coords) == 2:
            # coords is [lon, lat] format (GeoJSON standard)
            return (coords[1], coords[0])  # Return as (lat, lon)

    # 3. Not found anywhere - log to the hosted control plane if enabled
    if log_missing:
        try:
            from .logging_analytics import log_data_quality_issue_to_cloud

            log_data_quality_issue_to_cloud(
                issue_type="missing_geometry",
                name=country_code,
                metadata={"source": "get_fallback_coordinates"},
            )
        except Exception as e:
            logging.debug(f"Could not log missing geometry: {e}")

    return None


def get_region_patterns():
    """
    Build region pattern dictionary dynamically from conversions.json.
    Returns dict mapping lowercase patterns to normalized region names.
    """
    conversions = get_conversions_data()
    patterns = {}

    # Add patterns from regional_groupings
    groupings = conversions.get('regional_groupings', {})
    for group_name in groupings.keys():
        # Convert "WHO_European_Region" to "Europe", "European_Union" to "EU", etc.
        normalized = group_name.replace('_', ' ')
        # Common simplifications
        if 'WHO_' in group_name and '_Region' in group_name:
            # WHO_European_Region -> Europe
            simple = group_name.replace('WHO_', '').replace('_Region', '').replace('_', ' ')
            patterns[simple.lower()] = simple
            patterns[simple.lower().replace(' ', '')] = simple  # "southeast asia" variant
        else:
            patterns[normalized.lower()] = normalized

    # Add patterns from region_aliases
    aliases = conversions.get('region_aliases', {})
    for alias, target in aliases.items():
        patterns[alias.lower()] = alias  # Use the alias as the display name
        # Also add variant without spaces
        patterns[alias.lower().replace(' ', '')] = alias

    # Add some common variants manually
    extra_patterns = {
        "european": "Europe",
        "african": "Africa",
        "asian": "Asia",
        "american": "Americas",
        "scandinavia": "Nordic Countries",
        "scandinavian": "Nordic Countries",
    }
    patterns.update(extra_patterns)

    return patterns


def get_supported_regions_text():
    """
    Generate human-readable list of supported regions for LLM prompt.
    Reads from conversions.json dynamically.
    """
    conversions = get_conversions_data()
    groupings = conversions.get('regional_groupings', {})
    aliases = conversions.get('region_aliases', {})

    # Categorize regions
    who_regions = []
    political_groups = []
    sub_regions = []

    for group_name in groupings.keys():
        if 'WHO_' in group_name:
            # Convert to friendly name
            friendly = group_name.replace('WHO_', '').replace('_Region', '').replace('_', ' ')
            who_regions.append(friendly)
        elif group_name in ['G7', 'G20', 'NATO', 'ASEAN', 'BRICS', 'European_Union', 'Arab_League', 'African_Union', 'Commonwealth']:
            friendly = group_name.replace('_', ' ')
            political_groups.append(friendly)
        else:
            friendly = group_name.replace('_', ' ')
            sub_regions.append(friendly)

    # Add aliases that point to different names
    for alias in aliases.keys():
        if alias not in who_regions and alias not in political_groups and alias not in sub_regions:
            # Check where it should go
            if 'EU' in alias or 'Union' in alias:
                if alias not in political_groups:
                    political_groups.append(alias)

    lines = []
    if who_regions:
        lines.append(f"- Continents/WHO Regions: {', '.join(sorted(set(who_regions)))}")
    if political_groups:
        lines.append(f"- Political/Economic: {', '.join(sorted(set(political_groups)))}")
    if sub_regions:
        lines.append(f"- Sub-regions: {', '.join(sorted(set(sub_regions)))}")

    return "\n".join(lines)
