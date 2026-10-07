"""
Explore lane preprocessor runtime.

This module owns the Explore-facing summary wrapper around the shared
preprocessor signal bundle while `mapmover.preprocessor` stays as the stable
public import surface.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..data_loading import get_source_path, load_catalog, load_source_metadata
from .preprocess_summary import build_preprocessor_summary
from ..foundation_helpers import load_reference_dict
from ..paths import GEOMETRY_DIR as GEOM_DIR
from ..runtime.candidate_scoring import (
    adjust_scores_with_context as adjust_scores_with_context_impl,
    detect_intent_candidates as detect_intent_candidates_impl,
    detect_source_candidates as detect_source_candidates_impl,
)
from ..runtime.preprocess_catalog import (
    load_disaster_overlays as load_disaster_overlays_impl,
    load_topics as load_topics_impl,
)
from ..runtime.preprocess_pipeline import (
    build_candidate_bundle,
    build_preprocessor_hints,
    resolve_navigation_and_location,
)
from ..runtime.preprocess_primitives import (
    detect_derived_intent as detect_derived_intent_impl,
    detect_drilldown_pattern as detect_drilldown_pattern_impl,
    detect_filter_intent as detect_filter_intent_impl,
    detect_location_candidates as detect_location_candidates_impl,
    detect_navigation_intent as detect_navigation_intent_impl,
    detect_overlay_intent as detect_overlay_intent_impl,
    detect_reference_lookup as detect_reference_lookup_impl,
    detect_show_borders_intent as detect_show_borders_intent_impl,
    detect_time_patterns as detect_time_patterns_impl,
    extract_country_from_query as extract_country_from_query_impl,
    extract_multiple_locations as extract_multiple_locations_impl,
    extract_topics as extract_topics_impl,
    get_region_aliases as get_region_aliases_impl,
    lookup_country_specific_data as lookup_country_specific_data_impl,
    lookup_location_in_viewport as lookup_location_in_viewport_impl,
    resolve_regions as resolve_regions_impl,
    search_locations_globally as search_locations_globally_impl,
)
from ..runtime.preprocess_user_intents import (
    detect_address_prompt_intent,
    detect_tutorial_mode_intent,
    normalize_query_for_location_matching,
)
from ..runtime.query_constraint_primitives import extract_query_constraints as extract_query_constraints_impl
from ..runtime.loc_id_resolution import resolve_admin_text_to_loc_id
from ..runtime.preprocessor_runtime import build_preprocessor_signal_bundle
from ..runtime.preprocessor_context_runtime import (
    format_filter_description,
    get_countries_in_viewport,
    get_relevant_sources_with_metrics,
    get_sorted_location_names,
    load_country_index,
    load_parquet_names,
)


logger = logging.getLogger(__name__)

# =============================================================================
# CONFIDENCE SCORING CONFIGURATION
# =============================================================================

SCORE_DATA_KEYWORDS = 0.4
SCORE_DATA_FROM = 0.2
SCORE_SOURCE_MENTIONED = 0.3
SCORE_METRIC_KEYWORDS = 0.2

SCORE_NAV_PATTERN = 0.5
SCORE_NAV_PENALTY_DATA = -0.3
SCORE_NAV_LOCATION_ONLY = 0.3

PENALTY_LOCATION_IN_SOURCE = -0.5
PENALTY_NAV_SOURCE_DETECTED = -0.3

SCORE_SOURCE_FULL_MATCH = 1.0
SCORE_SOURCE_ID_MATCH = 0.9
SCORE_SOURCE_PARTIAL_8 = 0.7
SCORE_SOURCE_PARTIAL_4 = 0.5

# =============================================================================

CONVERSIONS_PATH = Path(__file__).parent / "conversions.json"
REFERENCE_DIR = Path(__file__).parent / "reference"
GEOMETRY_DIR = GEOM_DIR


def _load_topics() -> dict:
    return load_topics_impl(load_catalog=load_catalog, logger=logger)


def _load_disaster_overlays() -> dict:
    return load_disaster_overlays_impl(load_reference_json=load_reference_dict, logger=logger)


def load_conversions() -> dict:
    """Load conversions.json through the shared runtime loader path."""
    from ..runtime.geography_reference import load_conversions as load_conversions_impl

    return load_conversions_impl() or {}


def load_reference_file(filepath: Path) -> Optional[dict]:
    """Compatibility shim to the shared runtime foundation helper loader."""
    return load_reference_dict(filepath)


def search_locations_globally(name: str, admin_level: int = None, limit_countries: list = None) -> list:
    return search_locations_globally_impl(
        name,
        admin_level,
        limit_countries,
        geometry_dir=GEOMETRY_DIR,
        reference_dir=REFERENCE_DIR,
        load_reference_file=load_reference_file,
        load_parquet_names_func=load_parquet_names,
    )


def lookup_location_in_viewport(query: str, viewport: dict = None) -> dict:
    return lookup_location_in_viewport_impl(
        query,
        viewport,
        get_countries_in_viewport_func=get_countries_in_viewport,
        load_parquet_names_func=load_parquet_names,
        load_reference_file=load_reference_file,
        get_sorted_location_names_func=get_sorted_location_names,
        reference_dir=REFERENCE_DIR,
    )


def extract_country_from_query(query: str, viewport: dict = None) -> dict:
    return extract_country_from_query_impl(
        query,
        normalize_query_for_location_matching=normalize_query_for_location_matching,
        reference_dir=REFERENCE_DIR,
        load_reference_file=load_reference_file,
    )


def extract_topics(query: str) -> list:
    return extract_topics_impl(query, load_topics=_load_topics)


def resolve_regions(query: str) -> list:
    return resolve_regions_impl(query, get_region_aliases_func=get_region_aliases_impl)


def detect_time_patterns(query: str) -> dict:
    return detect_time_patterns_impl(query)


def extract_query_constraints(query: str) -> dict:
    return extract_query_constraints_impl(
        query,
        resolve_admin_text_to_loc_id_func=resolve_admin_text_to_loc_id,
        load_reference_file_func=load_reference_file,
        reference_dir=REFERENCE_DIR,
    )


def lookup_country_specific_data(ref_type: str, iso3: str, country_name: str) -> Optional[dict]:
    return lookup_country_specific_data_impl(
        ref_type,
        iso3,
        country_name,
        reference_dir=REFERENCE_DIR,
        load_reference_file=load_reference_file,
    )


def detect_reference_lookup(query: str) -> Optional[dict]:
    return detect_reference_lookup_impl(
        query,
        reference_dir=REFERENCE_DIR,
        load_catalog=load_catalog,
        get_source_path=get_source_path,
        load_reference_file=load_reference_file,
        extract_country_from_query=extract_country_from_query,
    )


def detect_derived_intent(query: str) -> Optional[dict]:
    return detect_derived_intent_impl(query)


def detect_filter_intent(query: str, active_overlays: dict) -> Optional[dict]:
    return detect_filter_intent_impl(query, active_overlays)


def detect_overlay_intent(query: str, active_overlays: dict = None) -> Optional[dict]:
    return detect_overlay_intent_impl(
        query,
        load_disaster_overlays=_load_disaster_overlays,
        detect_filter_intent_func=detect_filter_intent,
        active_overlays=active_overlays,
    )


def detect_source_candidates(query: str) -> dict:
    return detect_source_candidates_impl(
        query,
        load_catalog=load_catalog,
        load_source_metadata=load_source_metadata,
        score_source_full_match=SCORE_SOURCE_FULL_MATCH,
        score_source_id_match=SCORE_SOURCE_ID_MATCH,
        score_source_partial_8=SCORE_SOURCE_PARTIAL_8,
        score_source_partial_4=SCORE_SOURCE_PARTIAL_4,
    )


def detect_location_candidates(query: str, viewport: dict = None) -> dict:
    return detect_location_candidates_impl(
        query,
        normalize_query_for_location_matching=normalize_query_for_location_matching,
        reference_dir=REFERENCE_DIR,
        load_reference_file=load_reference_file,
    )


def detect_intent_candidates(query: str, source_candidates: dict, location_candidates: dict) -> dict:
    return detect_intent_candidates_impl(
        query,
        source_candidates,
        location_candidates,
        detect_navigation_intent=detect_navigation_intent,
        detect_show_borders_intent=detect_show_borders_intent,
        detect_filter_intent=detect_filter_intent,
        score_data_keywords=SCORE_DATA_KEYWORDS,
        score_data_from=SCORE_DATA_FROM,
        score_source_mentioned=SCORE_SOURCE_MENTIONED,
        score_metric_keywords=SCORE_METRIC_KEYWORDS,
        score_nav_pattern=SCORE_NAV_PATTERN,
        score_nav_penalty_data=SCORE_NAV_PENALTY_DATA,
        score_nav_location_only=SCORE_NAV_LOCATION_ONLY,
    )


def adjust_scores_with_context(source_candidates: dict, location_candidates: dict, intent_candidates: dict) -> dict:
    return adjust_scores_with_context_impl(
        source_candidates,
        location_candidates,
        intent_candidates,
        penalty_location_in_source=PENALTY_LOCATION_IN_SOURCE,
        penalty_nav_source_detected=PENALTY_NAV_SOURCE_DETECTED,
    )


def detect_show_borders_intent(query: str) -> dict:
    return detect_show_borders_intent_impl(query)


def detect_navigation_intent(query: str) -> dict:
    return detect_navigation_intent_impl(query)


def detect_drilldown_pattern(query: str, viewport: dict = None) -> dict:
    return detect_drilldown_pattern_impl(
        query,
        extract_country_from_query_func=lambda value: extract_country_from_query(value),
    )


def extract_multiple_locations(query: str, viewport: dict = None) -> dict:
    return extract_multiple_locations_impl(
        query,
        detect_drilldown_pattern_func=lambda value: detect_drilldown_pattern(value),
        search_locations_globally=search_locations_globally,
        extract_country_from_query_func=lambda value: extract_country_from_query(value),
        logger=logger,
    )


def preprocess_query(
    query: str,
    viewport: dict = None,
    active_overlays: dict = None,
    cache_stats: dict = None,
    saved_order_names: list = None,
    time_state: dict = None,
    loaded_data: list = None,
    selected_popup: dict = None,
) -> dict:
    """Extract shared hints and attach the Explore-facing summary layer."""
    preprocessor_state = build_preprocessor_signal_bundle(
        query=query,
        viewport=viewport,
        active_overlays=active_overlays,
        cache_stats=cache_stats,
        saved_order_names=saved_order_names,
        time_state=time_state,
        loaded_data=loaded_data,
        detect_show_borders_intent=detect_show_borders_intent,
        resolve_navigation_and_location=resolve_navigation_and_location,
        detect_navigation_intent=detect_navigation_intent,
        extract_multiple_locations=extract_multiple_locations,
        detect_source_candidates=detect_source_candidates,
        extract_country_from_query=extract_country_from_query,
        load_reference_file=load_reference_file,
        reference_dir=REFERENCE_DIR,
        get_countries_in_viewport=get_countries_in_viewport,
        logger=logger,
        detect_filter_intent=detect_filter_intent,
        detect_overlay_intent=detect_overlay_intent,
        build_candidate_bundle=build_candidate_bundle,
        detect_location_candidates=detect_location_candidates,
        detect_intent_candidates=detect_intent_candidates,
        adjust_scores_with_context=adjust_scores_with_context,
        detect_address_prompt_intent=detect_address_prompt_intent,
        extract_topics=extract_topics,
        resolve_regions=resolve_regions,
        detect_time_patterns=detect_time_patterns,
        detect_reference_lookup=detect_reference_lookup,
        detect_derived_intent=detect_derived_intent,
        detect_tutorial_mode_intent=detect_tutorial_mode_intent,
        build_preprocessor_hints=build_preprocessor_hints,
        extract_query_constraints=extract_query_constraints,
    )
    hints = preprocessor_state["hints"]
    hints["summary"] = build_preprocessor_summary(
        hints,
        navigation=preprocessor_state["navigation"],
        location=preprocessor_state["location"],
        disambiguation=preprocessor_state["disambiguation"],
        active_overlays=active_overlays,
        filter_intent=preprocessor_state["filter_intent"],
        overlay_intent=preprocessor_state["overlay_intent"],
        time_state=time_state,
        saved_order_names=saved_order_names,
        loaded_data=loaded_data,
        selected_popup=selected_popup,
        format_filter_description_func=format_filter_description,
    )
    return hints
