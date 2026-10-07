"""Intent-detection helpers extracted from preprocessor.py."""

from __future__ import annotations

import re
from typing import Callable, Optional


DERIVED_PATTERNS = {
    "per_capita": [
        r"per capita",
        r"per person",
        r"per head",
        r"per inhabitant",
    ],
    "density": [
        r"density",
        r"per square",
        r"per km",
        r"per sq",
    ],
    "per_1000": [
        r"per 1000",
        r"per thousand",
    ],
    "ratio": [
        r"ratio of",
        r"(\w+)\s*/\s*(\w+)",
        r"(\w+)\s+to\s+(\w+)\s+ratio",
    ],
}

COMPARISON_PATTERNS = {
    "volatility": [
        r"\bvolatility\b",
        r"\bvolatile\b",
        r"\bbiggest swings?\b",
        r"\bsharpest (?:moves|move)\b",
        r"\bmost volatile\b",
    ],
    "improvement": [
        r"\bimprovement\b",
        r"\bimprove(?:d|ment|s)?\b",
        r"\bprogress\b",
        r"\bbiggest gains?\b",
        r"\bmade the biggest progress\b",
        r"\breducing\b",
    ],
    "decline": [
        r"\bdecline\b",
        r"\bdeclines\b",
        r"\bdeteriorat(?:e|ed|ing|ion)\b",
        r"\bgot worse\b",
        r"\bworsen(?:ed|ing)?\b",
        r"\bbiggest drops?\b",
    ],
    "change": [
        r"\bchange\b",
        r"\bchanged\b",
        r"\bgrowth\b",
        r"\bincrease\b",
        r"\bdecrease\b",
        r"\bover time\b",
    ],
}

FILTER_READ_PATTERNS = [
    r"what.*(magnitude|power|size|strength|category|scale).*(?:displayed|showing|on|visible)",
    r"what.*filters?",
    r"what.*(earthquakes?|volcanoes?|fires?|storms?|hurricanes?|tornadoes?|floods?).*showing",
    r"current filters?",
    r"how many.*(earthquakes?|events?|fires?|storms?).*showing",
    r"what.*range.*(magnitude|power|size)",
]

FILTER_CHANGE_PATTERNS = [
    (r"(?:show|display).*mag(?:nitude)?[\s:]*(\d+\.?\d*)[\s-]+(?:to|-)[\s]*(\d+\.?\d*)", "magnitude_range"),
    (r"(?:show|display).*mag(?:nitude)?[\s:]*(\d+\.?\d*)\s*\+", "magnitude_min"),
    (r"(?:show|display).*(?:>=?|above|over)\s*(\d+\.?\d*)\s*mag", "magnitude_min"),
    (r"(?:show|display).*(?:<=?|under|below)\s*(\d+\.?\d*)\s*mag", "magnitude_max"),
    (r"(?:all|any|clear|reset|remove)\s*(?:earthquakes?|filters?|magnitude)", "clear"),
    (r"(?:show|display).*vei\s*(\d+)\s*(?:\+|and\s*above|or\s*higher)", "vei_min"),
    (r"(?:show|display).*category\s*(\d+)\s*(?:\+|and\s*above|or\s*higher)", "category_min"),
    (r"(?:show|display).*(?:ef|scale)\s*(\d+)\s*(?:\+|and\s*above|or\s*higher)", "scale_min"),
    (r"(?:show|display).*(?:over|above|>=?)\s*(\d+)\s*(?:km2|sq\s*km|square\s*km)", "area_min"),
    (r"(?:show|display).*(?:over|above|>=?)\s*(\d+)\s*acres?", "acres_min"),
]

_DATA_KEYWORDS = r"data|from|gdp|population|earthquake|volcano|hurricane|storm|wildfire|fire|flood|drought|tornado|tsunami|emission|income|health|mortality"

NAVIGATION_PATTERNS = [
    rf"^show me\b(?!.*(?:{_DATA_KEYWORDS}))",
    r"^where is\b",
    r"^where are\b",
    r"^locate\b",
    rf"^find\b(?!.*(?:{_DATA_KEYWORDS}))",
    r"^zoom to\b",
    r"^go to\b",
    r"^take me to\b",
    rf"^show\b(?!.*(?:{_DATA_KEYWORDS}))",
]

SHOW_BORDERS_PATTERNS = [
    r"^(?:just\s+)?show\s+(?:me\s+)?(?:them|all|all\s+of\s+them)\b",
    r"^display\s+(?:them|all|all\s+of\s+them)\b",
    r"^(?:just\s+)?show\s+(?:me\s+)?(?:the\s+)?(?:borders?|geometr(?:y|ies)|outlines?|boundaries?)\b",
    r"^(?:put|display|show)\s+(?:them\s+)?(?:all\s+)?on\s+(?:the\s+)?map\b",
    r"^(?:just\s+)?the\s+(?:borders?|geometr(?:y|ies)|locations?)\b",
]


def detect_derived_intent(query: str) -> Optional[dict]:
    """Detect if query is asking for derived/calculated fields."""
    query_lower = query.lower()

    for comparison_type, patterns in COMPARISON_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if not match:
                continue

            result = {"type": comparison_type, "match": match.group(0), "family": "comparison"}

            since_match = re.search(r"\bsince\s+(19|20)\d{2}\b", query_lower)
            if since_match:
                year_match = re.search(r"(19|20)\d{2}", since_match.group(0))
                if year_match:
                    result["start_year"] = int(year_match.group(0))

            last_years_match = re.search(r"\bover\s+the\s+last\s+(\d{1,3})\s+years?\b", query_lower)
            if last_years_match:
                result["window_years"] = int(last_years_match.group(1))

            recent_match = re.search(r"\brecent(?:ly)?\b", query_lower)
            if recent_match:
                result["recent"] = True

            return result

    for derived_type, patterns in DERIVED_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                result = {"type": derived_type, "match": match.group(0)}
                if derived_type == "ratio" and len(match.groups()) >= 2:
                    result["numerator_hint"] = match.group(1)
                    result["denominator_hint"] = match.group(2)
                return result

    return None


def detect_filter_intent(query: str, active_overlays: dict) -> Optional[dict]:
    """Detect if user is asking about or changing overlay filters."""
    if not active_overlays:
        return None

    query_lower = query.lower()
    overlay_type = active_overlays.get("type")

    for pattern in FILTER_READ_PATTERNS:
        if re.search(pattern, query_lower):
            return {"type": "read_filters", "overlay": overlay_type, "pattern": pattern}

    for pattern, filter_type in FILTER_CHANGE_PATTERNS:
        match = re.search(pattern, query_lower)
        if match:
            result = {
                "type": "change_filters",
                "overlay": overlay_type,
                "filter_type": filter_type,
                "raw_match": match.group(0),
            }
            if filter_type == "magnitude_range":
                result["minMagnitude"] = float(match.group(1))
                result["maxMagnitude"] = float(match.group(2))
            elif filter_type == "magnitude_min":
                result["minMagnitude"] = float(match.group(1))
            elif filter_type == "magnitude_max":
                result["maxMagnitude"] = float(match.group(1))
            elif filter_type == "vei_min":
                result["minVei"] = int(match.group(1))
            elif filter_type == "category_min":
                result["minCategory"] = int(match.group(1))
            elif filter_type == "scale_min":
                result["minScale"] = int(match.group(1))
            elif filter_type == "area_min":
                result["minAreaKm2"] = float(match.group(1))
            elif filter_type == "acres_min":
                result["minAreaKm2"] = float(match.group(1)) * 0.00404686
            elif filter_type == "clear":
                result["clear"] = True
            return result

    return None


def detect_overlay_intent(
    query: str,
    *,
    load_disaster_overlays: Callable[[], dict],
    detect_filter_intent_func: Callable[[str, dict], Optional[dict]],
    active_overlays: dict | None = None,
) -> Optional[dict]:
    """Detect if user is asking about a disaster overlay."""
    query_lower = query.lower()
    detected_overlay = None
    disaster_overlays = load_disaster_overlays()
    for overlay_id, keywords in disaster_overlays.items():
        for keyword in keywords:
            if keyword in query_lower:
                detected_overlay = overlay_id
                break
        if detected_overlay:
            break

    if not detected_overlay:
        return None

    is_overlay_active = False
    if active_overlays:
        active_type = active_overlays.get("type", "")
        all_active = active_overlays.get("allActive", [])
        is_overlay_active = active_type == detected_overlay or detected_overlay in all_active

    severity = {}
    filter_result = detect_filter_intent_func(query, {"type": detected_overlay})
    if filter_result and filter_result.get("type") == "change_filters":
        for key in ["minMagnitude", "maxMagnitude", "minCategory", "minVei", "minScale", "minAreaKm2"]:
            if key in filter_result:
                severity[key] = filter_result[key]

    if is_overlay_active:
        action = "filter" if severity else "query"
    else:
        action = "enable"

    return {
        "overlay": detected_overlay,
        "action": action,
        "severity": severity if severity else None,
        "is_active": is_overlay_active,
    }


def detect_show_borders_intent(query: str) -> dict:
    """Detect if query is asking to display geometry/borders without data."""
    result = {"is_show_borders": False, "pattern": None}
    query_lower = query.lower().strip()
    for pattern in SHOW_BORDERS_PATTERNS:
        if re.match(pattern, query_lower):
            result["is_show_borders"] = True
            result["pattern"] = pattern
            return result
    return result


def detect_navigation_intent(query: str) -> dict:
    """Detect if query is asking to navigate to or view locations."""
    result = {"is_navigation": False, "pattern": None, "location_text": None}
    query_lower = query.lower().strip()
    for pattern in NAVIGATION_PATTERNS:
        match = re.match(pattern, query_lower)
        if match:
            result["is_navigation"] = True
            result["pattern"] = pattern
            result["location_text"] = query_lower[match.end() :].strip()
            return result
    return result
