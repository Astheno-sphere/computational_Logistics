"""Shared runtime assembly for preprocessor signal extraction."""

from __future__ import annotations


def build_preprocessor_signal_bundle(
    *,
    query: str,
    viewport: dict | None = None,
    active_overlays: dict | None = None,
    cache_stats: dict | None = None,
    saved_order_names: list | None = None,
    time_state: dict | None = None,
    loaded_data: list | None = None,
    detect_show_borders_intent,
    resolve_navigation_and_location,
    detect_navigation_intent,
    extract_multiple_locations,
    detect_source_candidates,
    extract_country_from_query,
    load_reference_file,
    reference_dir,
    get_countries_in_viewport,
    logger,
    detect_filter_intent,
    detect_overlay_intent,
    build_candidate_bundle,
    detect_location_candidates,
    detect_intent_candidates,
    adjust_scores_with_context,
    detect_address_prompt_intent,
    extract_topics,
    resolve_regions,
    detect_time_patterns,
    detect_reference_lookup,
    detect_derived_intent,
    detect_tutorial_mode_intent,
    build_preprocessor_hints,
    extract_query_constraints,
) -> dict:
    """Build the shared hint bundle before any lane-specific summary shaping."""
    show_borders = detect_show_borders_intent(query)
    resolution = resolve_navigation_and_location(
        query=query,
        viewport=viewport,
        detect_navigation_intent=detect_navigation_intent,
        extract_multiple_locations=extract_multiple_locations,
        detect_source_candidates=detect_source_candidates,
        extract_country_from_query=extract_country_from_query,
        load_reference_file=load_reference_file,
        reference_dir=reference_dir,
        get_countries_in_viewport=get_countries_in_viewport,
        logger=logger,
        extract_query_constraints=extract_query_constraints,
    )
    navigation = resolution["navigation"]
    disambiguation = resolution["disambiguation"]
    source_candidates = resolution["source_candidates"]
    detected_source = resolution["detected_source"]
    location = resolution["location"]

    filter_intent = detect_filter_intent(query, active_overlays) if active_overlays else None
    overlay_intent = detect_overlay_intent(query, active_overlays)

    candidates = build_candidate_bundle(
        query=query,
        viewport=viewport,
        source_candidates=source_candidates,
        detect_location_candidates=detect_location_candidates,
        detect_intent_candidates=detect_intent_candidates,
        adjust_scores_with_context=adjust_scores_with_context,
    )

    hints = build_preprocessor_hints(
        query=query,
        viewport=viewport,
        show_borders=show_borders,
        navigation=navigation,
        address_prompt=detect_address_prompt_intent(query),
        topics=extract_topics(query),
        regions=resolve_regions(query),
        location=location,
        disambiguation=disambiguation,
        time_hints=detect_time_patterns(query),
        reference_lookup=detect_reference_lookup(query),
        derived_intent=detect_derived_intent(query),
        tutorial_mode=detect_tutorial_mode_intent(query),
        detected_source=detected_source,
        active_overlays=active_overlays,
        cache_stats=cache_stats,
        filter_intent=filter_intent,
        overlay_intent=overlay_intent,
        candidates=candidates,
        saved_order_names=saved_order_names,
        time_state=time_state,
        loaded_data=loaded_data,
        query_constraints=resolution["query_constraints"],
    )
    return {
        "hints": hints,
        "navigation": navigation,
        "location": location,
        "disambiguation": disambiguation,
        "filter_intent": filter_intent,
        "overlay_intent": overlay_intent,
    }
