"""
Utility functions for normalization, unit conversion, and data cleaning.
"""

import re
import json
import unicodedata
import pandas as pd
from pathlib import Path
import logging

from .constants import UNIT_MULTIPLIERS
from .foundation_helpers import load_reference_json

logger = logging.getLogger(__name__)

# Cached reference data
_STATE_ABBREVS_CACHE = None
_UNIT_CONVERSIONS_CACHE = None


def _load_unit_conversions():
    """Load unit conversions from reference file (cached)."""
    global _UNIT_CONVERSIONS_CACHE
    if _UNIT_CONVERSIONS_CACHE is None:
        data = load_reference_json("unit_conversions.json")
        if isinstance(data, dict):
            _UNIT_CONVERSIONS_CACHE = data
        else:
            logger.warning("Could not load unit_conversions.json")
            _UNIT_CONVERSIONS_CACHE = {}
    return _UNIT_CONVERSIONS_CACHE

def _get_state_abbreviations():
    """Load state abbreviations from usa_admin.json reference file."""
    global _STATE_ABBREVS_CACHE
    if _STATE_ABBREVS_CACHE is None:
        data = load_reference_json("usa/usa_admin.json")
        if isinstance(data, dict):
            abbrevs = data.get("state_abbreviations", {})
            _STATE_ABBREVS_CACHE = {k: v for k, v in abbrevs.items() if not k.startswith("_")}
        else:
            _STATE_ABBREVS_CACHE = {}
    return _STATE_ABBREVS_CACHE


def normalize_unit_name(unit_str):
    """
    Normalize a unit string to its canonical form using aliases.

    Args:
        unit_str: User-provided unit string (e.g., "square miles", "kg")

    Returns:
        Canonical unit name (e.g., "sq_mi", "kg") or original if not found
    """
    if not unit_str:
        return unit_str

    unit_lower = unit_str.lower().strip()
    conversions = _load_unit_conversions()
    aliases = conversions.get("unit_aliases", {})

    # Direct match
    if unit_lower in aliases:
        return aliases[unit_lower]

    # Already canonical
    return unit_lower


def convert_temperature(value, from_unit, to_unit):
    """
    Convert temperature between celsius, fahrenheit, and kelvin.
    Temperature requires formulas, not simple multipliers.

    Args:
        value: Temperature value
        from_unit: Source unit (celsius, fahrenheit, kelvin)
        to_unit: Target unit

    Returns:
        Converted value or None if conversion not possible
    """
    from_unit = normalize_unit_name(from_unit)
    to_unit = normalize_unit_name(to_unit)

    if from_unit == to_unit:
        return float(value)

    v = float(value)

    # Convert to celsius first (as intermediate)
    if from_unit == "fahrenheit":
        celsius = (v - 32) * 5 / 9
    elif from_unit == "kelvin":
        celsius = v - 273.15
    elif from_unit == "celsius":
        celsius = v
    else:
        return None

    # Convert from celsius to target
    if to_unit == "celsius":
        return celsius
    elif to_unit == "fahrenheit":
        return celsius * 9 / 5 + 32
    elif to_unit == "kelvin":
        return celsius + 273.15
    else:
        return None


def convert_unit(value, from_unit, to_unit, metadata=None):
    """
    Convert a numerical value from one unit to another.

    Conversion priority:
    1. Per-metric conversions from metadata (if provided)
    2. Centralized unit_conversions.json reference
    3. Temperature special handling (formula-based)

    Args:
        value: Numerical value to convert
        from_unit: Original unit (from metadata or data)
        to_unit: Target unit (from user query)
        metadata: Optional column metadata with per-metric conversions

    Returns:
        Converted value or None if conversion not possible
    """
    if value is None:
        return None

    # Normalize unit names
    from_unit = normalize_unit_name(from_unit)
    to_unit = normalize_unit_name(to_unit)

    if from_unit == to_unit:
        return float(value)

    # Priority 1: Check per-metric conversions from metadata
    if metadata:
        conversions = metadata.get("conversions", {})
        if to_unit in conversions:
            return float(value) * conversions[to_unit]

    # Priority 2: Check centralized unit conversions reference
    unit_ref = _load_unit_conversions()
    all_conversions = unit_ref.get("conversions", {})

    # Build conversion key (e.g., "km_to_mi")
    conversion_key = f"{from_unit}_to_{to_unit}"

    # Search all categories for the conversion
    for category, category_conversions in all_conversions.items():
        if conversion_key in category_conversions:
            factor = category_conversions[conversion_key]
            return float(value) * factor

    # Priority 3: Temperature special handling
    temp_units = {"celsius", "fahrenheit", "kelvin"}
    if from_unit in temp_units and to_unit in temp_units:
        return convert_temperature(value, from_unit, to_unit)

    # Could not convert
    return None


def get_unit_display_format(unit):
    """
    Get display formatting info for a unit.

    Args:
        unit: Canonical unit name

    Returns:
        Dict with 'symbol' and 'decimals' or None if not found
    """
    unit = normalize_unit_name(unit)
    unit_ref = _load_unit_conversions()
    formats = unit_ref.get("display_formats", {})
    return formats.get(unit)


def format_value_with_unit(value, unit, use_symbol=True):
    """
    Format a value with its unit for display.

    Args:
        value: Numerical value
        unit: Unit name
        use_symbol: If True, use short symbol; if False, use full name

    Returns:
        Formatted string (e.g., "1,234.5 km2")
    """
    if value is None:
        return "N/A"

    unit = normalize_unit_name(unit)
    fmt = get_unit_display_format(unit)

    if fmt:
        decimals = fmt.get("decimals", 2)
        symbol = fmt.get("symbol", unit) if use_symbol else unit
        formatted_value = f"{value:,.{decimals}f}"
        return f"{formatted_value} {symbol}"

    # Default formatting
    return f"{value:,.2f} {unit}"


def state_from_abbr(name):
    """Convert state abbreviation to full state name."""
    return _get_state_abbreviations().get(name.upper(), "Unknown")


def normalize(name: str) -> str:
    """
    Normalize place names for fuzzy matching.
    Removes accents, county suffixes, punctuation, etc.
    """
    name = name.strip()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))  # remove accents
    name = name.lower()
    name = re.sub(r'\bsaint\b', 'st', name)  # fix saint
    name = re.sub(r'\b(county|borough|census|area|city|and|municipality|gateway|municipio)\b', '', name)  # remove common fluff
    name = re.sub(r'[^\w\s]', '', name)  # remove punctuation
    name = re.sub(r'\s+', ' ', name)  # collapse multiple spaces
    return name.strip()


def parse_year_value(year_val):
    """
    Parse a year value that might be a range like '2022-2023' or a single year.
    Returns an integer year, or None if unparseable.
    For ranges, returns the end year (most recent).
    """
    if year_val is None:
        return None
    year_str = str(year_val).strip()
    # Try direct integer conversion first
    try:
        return int(float(year_str))
    except (ValueError, TypeError):
        pass
    # Try parsing as a range like "2022-2023"
    if '-' in year_str:
        parts = year_str.split('-')
        if len(parts) == 2:
            try:
                # Return the end year (most recent)
                return int(parts[1].strip())
            except (ValueError, TypeError):
                pass
            try:
                # Fall back to start year if end year fails
                return int(parts[0].strip())
            except (ValueError, TypeError):
                pass
    # Try extracting any 4-digit year from the string
    match = re.search(r'\b(19|20)\d{2}\b', year_str)
    if match:
        return int(match.group())
    return None


def clean_nans(obj):
    """
    Recursively clean NaN values from nested data structures.
    Converts NaN/None to None for JSON serialization.
    """
    if isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(item) for item in obj]
    elif isinstance(obj, float) and (pd.isna(obj) or obj != obj):
        return None
    return obj


def apply_unit_multiplier(filter_spec):
    """
    Apply unit multiplier to filter value if unit is specified.
    Modifies filter_spec in place.

    Args:
        filter_spec: Dict with 'value' and optionally 'unit' keys
    """
    if not filter_spec:
        return

    unit = (filter_spec.get("unit") or "").lower()
    value = filter_spec.get("value")

    if unit in UNIT_MULTIPLIERS and value is not None:
        filter_spec["value"] = value * UNIT_MULTIPLIERS[unit]
        filter_spec["unit"] = ""
