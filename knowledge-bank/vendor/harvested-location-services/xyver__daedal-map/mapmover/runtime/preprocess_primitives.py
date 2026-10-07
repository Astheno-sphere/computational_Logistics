"""Shared preprocessing primitives promoted out of lane-local ownership.

This module does not move behavior yet. It provides one explicit shared-core
surface for the leaf parsing and normalization helpers that were previously
only reachable through Explore-centric imports.
"""

from __future__ import annotations

from mapmover.preprocessor_geo import (
    get_countries_in_viewport,
    get_sorted_location_names,
    load_parquet_names,
    lookup_location_in_viewport,
    search_locations_globally,
)
from mapmover.preprocessor_intents import (
    detect_derived_intent,
    detect_filter_intent,
    detect_navigation_intent,
    detect_overlay_intent,
    detect_show_borders_intent,
)
from mapmover.preprocessor_locations import (
    build_name_to_iso3,
    build_subregion_to_iso3,
    detect_drilldown_pattern,
    detect_location_candidates,
    extract_country_from_query,
    extract_multiple_locations,
)
from mapmover.preprocessor_metadata import (
    detect_time_patterns,
    extract_topics,
    get_region_aliases,
    get_relevant_sources_with_metrics,
    load_country_index,
    resolve_regions,
)
from mapmover.preprocessor_reference import (
    detect_reference_lookup,
    lookup_country_specific_data,
)

__all__ = [
    "build_name_to_iso3",
    "build_subregion_to_iso3",
    "detect_derived_intent",
    "detect_drilldown_pattern",
    "detect_filter_intent",
    "detect_location_candidates",
    "detect_navigation_intent",
    "detect_overlay_intent",
    "detect_reference_lookup",
    "detect_show_borders_intent",
    "detect_time_patterns",
    "extract_country_from_query",
    "extract_multiple_locations",
    "extract_topics",
    "get_countries_in_viewport",
    "get_region_aliases",
    "get_relevant_sources_with_metrics",
    "get_sorted_location_names",
    "load_country_index",
    "load_parquet_names",
    "lookup_country_specific_data",
    "lookup_location_in_viewport",
    "resolve_regions",
    "search_locations_globally",
]
