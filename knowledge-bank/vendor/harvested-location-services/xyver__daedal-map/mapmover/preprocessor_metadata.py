"""Metadata/topic/region/time helpers extracted from preprocessor.py."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

from .runtime.geography_reference import load_conversions as load_conversions_impl


_COUNTRY_INDEX_CACHE = {}
_REGION_ALIASES_CACHE = None


def load_country_index(iso3: str, *, countries_dir: Path, logger) -> Optional[dict]:
    """Load a country's index.json file for context injection."""
    global _COUNTRY_INDEX_CACHE
    iso3_upper = iso3.upper()
    if iso3_upper in _COUNTRY_INDEX_CACHE:
        return _COUNTRY_INDEX_CACHE[iso3_upper]

    index_path = countries_dir / iso3_upper / "index.json"
    if index_path.exists():
        try:
            with open(index_path, encoding="utf-8") as f:
                data = json.load(f)
            _COUNTRY_INDEX_CACHE[iso3_upper] = data
            logger.debug(f"Cached country index: {iso3_upper}")
            return data
        except Exception:
            pass

    _COUNTRY_INDEX_CACHE[iso3_upper] = None
    return None


def get_relevant_sources_with_metrics(
    topics: list,
    iso3: str | None = None,
    *,
    load_catalog: Callable[[], dict],
    load_source_metadata: Callable[[str], Optional[dict]],
    load_country_index_func: Callable[[str], Optional[dict]],
) -> dict:
    """Find relevant sources based on detected topics and location."""
    result = {"sources": [], "country_summary": None, "country_index": None}
    if iso3:
        country_index = load_country_index_func(iso3)
        if country_index:
            result["country_summary"] = country_index.get("llm_summary")
            result["country_index"] = {
                "datasets": country_index.get("datasets", []),
                "admin_levels": country_index.get("admin_levels", []),
                "admin_counts": country_index.get("admin_counts", {}),
            }

    catalog = load_catalog()
    sources = catalog.get("sources", [])
    relevant = []
    topic_keywords = {
        "demographics": ["population", "demographics", "census", "age", "birth", "death"],
        "economy": ["economic", "economy", "gdp", "income", "trade"],
        "health": ["health", "disease", "mortality", "medical"],
        "environment": ["environment", "climate", "emissions", "co2", "energy"],
        "education": ["education", "literacy", "school"],
        "development": ["sdg", "development", "sustainable"],
        "hazard": ["earthquake", "volcano", "hurricane", "cyclone", "wildfire", "fire", "flood", "tsunami", "storm", "disaster", "hazard"],
    }

    keywords_to_match = []
    for topic in topics:
        keywords_to_match.extend(topic_keywords.get(topic, [topic]))

    for source in sources:
        source_id = source.get("source_id", "")
        scope = source.get("scope", "global")
        topic_tags = source.get("topic_tags", [])
        source_keywords = source.get("keywords", [])
        metrics = source.get("metrics", {})

        include_source = False
        is_country_source = iso3 and scope.lower() == iso3.lower()
        is_global_source = scope == "global"
        topic_matches = False
        if keywords_to_match:
            all_source_keywords = [t.lower() for t in topic_tags + source_keywords]
            for kw in keywords_to_match:
                if any(kw.lower() in sk for sk in all_source_keywords):
                    topic_matches = True
                    break

        if iso3:
            if is_country_source:
                include_source = True
            elif is_global_source and topic_matches:
                include_source = True
        else:
            if topic_matches:
                include_source = True

        if not include_source:
            continue

        metric_list = []
        if is_country_source:
            full_metadata = load_source_metadata(source_id)
            if full_metadata:
                full_metrics = full_metadata.get("metrics", {})
                for metric_key, metric_info in full_metrics.items():
                    metric_list.append(
                        {
                            "column": metric_key,
                            "name": metric_info.get("name", metric_key),
                            "unit": metric_info.get("unit", ""),
                        }
                    )
            else:
                for metric_key, metric_info in metrics.items():
                    metric_list.append(
                        {
                            "column": metric_key,
                            "name": metric_info.get("name", metric_key),
                            "unit": metric_info.get("unit", ""),
                        }
                    )
        else:
            for metric_key, metric_info in metrics.items():
                metric_list.append(
                    {
                        "column": metric_key,
                        "name": metric_info.get("name", metric_key),
                        "unit": metric_info.get("unit", ""),
                    }
                )

        if metric_list:
            relevant.append(
                {
                    "source_id": source_id,
                    "source_name": source.get("source_name", source_id),
                    "scope": scope,
                    "metrics": metric_list,
                    "is_country_source": is_country_source,
                }
            )

    result["sources"] = relevant
    return result


def extract_topics(query: str, *, load_topics: Callable[[], dict]) -> list:
    """Extract topic categories from query based on keywords."""
    query_lower = query.lower()
    matched_topics = []
    topics = load_topics()
    for topic, keywords in topics.items():
        if any(kw in query_lower for kw in keywords):
            matched_topics.append(topic)
    return matched_topics


def get_region_aliases() -> dict:
    """Load region aliases from conversions.json."""
    global _REGION_ALIASES_CACHE
    if _REGION_ALIASES_CACHE is not None:
        return _REGION_ALIASES_CACHE

    conversions = load_conversions_impl() or {}
    regions = conversions.get("regions", {})
    aliases = {}
    for region_key, region_data in regions.items():
        if isinstance(region_data, dict):
            display_name = region_data.get("name", region_key).lower()
            aliases[display_name] = region_key
            for synonym in region_data.get("synonyms", []):
                aliases[synonym.lower()] = region_key

    aliases.update(
        {
            "europe": "WHO_European_Region",
            "european": "WHO_European_Region",
            "africa": "WHO_African_Region",
            "african": "WHO_African_Region",
            "sub-saharan africa": "Sub_Saharan_Africa",
            "asia": "WHO_South_East_Asia_Region",
            "middle east": "WHO_Eastern_Mediterranean_Region",
            "americas": "WHO_Region_of_the_Americas",
            "latin america": "Latin_America",
            "south america": "South_America",
            "north america": "North_America",
            "g7": "G7",
            "g20": "G20",
            "oecd": "OECD",
            "eu": "European_Union",
            "european union": "European_Union",
            "nordic": "Nordic_Countries",
            "brics": "BRICS",
            "developed": "High_Income",
            "developing": "Lower_Middle_Income",
            "high income": "High_Income",
            "low income": "Low_Income",
        }
    )
    _REGION_ALIASES_CACHE = aliases
    return _REGION_ALIASES_CACHE


def resolve_regions(query: str, *, get_region_aliases_func: Callable[[], dict] | None = None) -> list:
    """Detect region mentions in query and resolve to grouping names."""
    query_lower = query.lower()
    conversions = load_conversions_impl() or {}
    groupings = conversions.get("regional_groupings", {})
    resolved = []
    alias_loader = get_region_aliases_func or get_region_aliases

    for alias, grouping_name in alias_loader().items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, query_lower) and grouping_name in groupings:
            group_data = groupings[grouping_name]
            resolved.append(
                {
                    "match": alias,
                    "grouping": grouping_name,
                    "code": group_data.get("code"),
                    "countries": group_data.get("countries", []),
                    "count": len(group_data.get("countries", [])),
                }
            )

    for grouping_name, group_data in groupings.items():
        name_lower = grouping_name.lower().replace("_", " ")
        name_pattern = r"\b" + re.escape(name_lower) + r"\b"
        code = group_data.get("code", "").lower()
        code_matched = False
        if code and len(code) >= 3:
            code_pattern = r"\b" + re.escape(code) + r"\b"
            code_matched = bool(re.search(code_pattern, query_lower))
        if re.search(name_pattern, query_lower) or code_matched:
            if not any(r["grouping"] == grouping_name for r in resolved):
                resolved.append(
                    {
                        "match": grouping_name,
                        "grouping": grouping_name,
                        "code": group_data.get("code"),
                        "countries": group_data.get("countries", []),
                        "count": len(group_data.get("countries", [])),
                    }
                )

    return resolved


TIME_PATTERNS = {
    "year_range": [
        r"from\s+(\d{4})\s+to\s+(\d{4})",
        r"between\s+(\d{4})\s+and\s+(\d{4})",
        r"(\d{4})\s*[-to]+\s*(\d{4})",
    ],
    "year_to_now": [
        r"from\s+(\d{4})\s+(?:to|until)\s+(?:now|present|today|current)",
        r"(\d{4})\s+(?:to|until)\s+(?:now|present|today|current)",
    ],
    "trend_indicators": [
        r"\btrend\b",
        r"\bover time\b",
        r"\bhistor(?:y|ical)\b",
        r"\bchange\b",
        r"\bgrowth\b",
        r"\bdecline\b",
        r"\ball\s+(?:the\s+)?years?\b",
        r"\bevery\s+year\b",
        r"\bacross\s+(?:all\s+)?years?\b",
    ],
    "last_n_years": [
        r"last\s+(\d+)\s+years?",
        r"past\s+(\d+)\s+years?",
    ],
    "since_year": [
        r"since\s+(\d{4})",
        r"from\s+(\d{4})",
    ],
    "single_year": [
        r"\bin\s+(\d{4})\b",
        r"\bfor\s+(\d{4})\b",
        r"\bover\s+(\d{4})\b",
        r"\bduring\s+(\d{4})\b",
        r"\b(\d{4})\s+data\b",
    ],
}


def detect_time_patterns(query: str) -> dict:
    """Detect time-related patterns in query."""
    result = {
        "is_time_series": False,
        "year_start": None,
        "year_end": None,
        "pattern_type": None,
        "time_granularity": None,
    }
    query_lower = query.lower()

    if re.search(r"\bdaily\b|\bday by day\b", query_lower):
        result["time_granularity"] = "daily"
    elif re.search(r"\bweekly\b|\bweek by week\b", query_lower):
        result["time_granularity"] = "weekly"
    elif re.search(r"\bmonthly\b|\bmonth by month\b", query_lower):
        result["time_granularity"] = "monthly"
    elif re.search(r"\byearly\b|\bannual(?:ly)?\b|\byear by year\b", query_lower):
        result["time_granularity"] = "yearly"

    for pattern in TIME_PATTERNS["year_range"]:
        match = re.search(pattern, query_lower)
        if match:
            result["is_time_series"] = True
            result["year_start"] = int(match.group(1))
            result["year_end"] = int(match.group(2))
            result["pattern_type"] = "year_range"
            return result
    for pattern in TIME_PATTERNS["year_to_now"]:
        match = re.search(pattern, query_lower)
        if match:
            result["is_time_series"] = True
            result["year_start"] = int(match.group(1))
            result["year_end"] = 2024
            result["pattern_type"] = "year_to_now"
            return result
    for pattern in TIME_PATTERNS["trend_indicators"]:
        if re.search(pattern, query_lower):
            result["is_time_series"] = True
            result["pattern_type"] = "trend"
            break
    for pattern in TIME_PATTERNS["last_n_years"]:
        match = re.search(pattern, query_lower)
        if match:
            n_years = int(match.group(1))
            result["is_time_series"] = True
            result["year_end"] = 2024
            result["year_start"] = 2024 - n_years
            result["pattern_type"] = "last_n_years"
            return result
    for pattern in TIME_PATTERNS["since_year"]:
        match = re.search(pattern, query_lower)
        if match:
            result["is_time_series"] = True
            result["year_start"] = int(match.group(1))
            result["year_end"] = 2024
            result["pattern_type"] = "since_year"
            return result
    for pattern in TIME_PATTERNS["single_year"]:
        match = re.search(pattern, query_lower)
        if match:
            year = int(match.group(1))
            if 1900 < year < 2100:
                result["is_time_series"] = True
                result["year_start"] = year
                result["year_end"] = year
                result["pattern_type"] = "single_year"
                return result
    return result
