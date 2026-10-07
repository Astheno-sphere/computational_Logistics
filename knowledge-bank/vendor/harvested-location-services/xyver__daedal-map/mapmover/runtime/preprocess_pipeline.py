"""Shared pipeline assembly helpers for preprocessor output."""


def resolve_navigation_and_location(
    *,
    query: str,
    viewport: dict | None = None,
    detect_navigation_intent,
    extract_multiple_locations,
    detect_source_candidates,
    extract_country_from_query,
    load_reference_file,
    reference_dir,
    get_countries_in_viewport,
    logger,
    extract_query_constraints,
):
    """Resolve navigation, disambiguation, detected source, and location context."""
    nav_intent = detect_navigation_intent(query)
    navigation = None
    disambiguation = None

    if nav_intent.get("is_navigation") and nav_intent.get("location_text"):
        location_result = extract_multiple_locations(nav_intent["location_text"], viewport)
        locations = location_result.get("locations", [])
        if locations:
            if location_result.get("needs_disambiguation"):
                disambiguation = {
                    "needed": True,
                    "query_term": location_result.get("query_term", "location"),
                    "options": locations,
                    "count": len(locations)
                }
            else:
                navigation = {
                    "is_navigation": True,
                    "pattern": nav_intent.get("pattern"),
                    "locations": locations,
                    "count": len(locations)
                }

    source_candidates = detect_source_candidates(query)
    detected_source = source_candidates.get("best")
    location = None
    query_constraints = extract_query_constraints(query)

    if not navigation and not disambiguation:
        if isinstance(query_constraints.get("location"), dict):
            location = dict(query_constraints["location"])
        location_result = {} if location else extract_country_from_query(query, viewport=viewport)

        if detected_source and location_result.get("match"):
            source_name_lower = detected_source.get("source_name", "").lower()
            matched_term = location_result["match"][0].lower()
            if matched_term in source_name_lower:
                location_result = {}

        if location_result.get("match"):
            matched_term, iso3, is_subregion = location_result["match"]
            iso_data = load_reference_file(reference_dir / "iso_codes.json")
            country_name = iso_data.get("iso3_to_name", {}).get(iso3, matched_term.title()) if iso_data else matched_term.title()
            location = {
                "matched_term": matched_term,
                "iso3": iso3,
                "loc_id": iso3,
                "country_name": country_name,
                "is_subregion": is_subregion,
                "source": location_result.get("source"),
            }

            if location_result.get("ambiguous") and location_result.get("matches"):
                matches = location_result["matches"]
                resolved_by_viewport = False
                if viewport:
                    filtered_matches = matches

                    current_admin_level = viewport.get("adminLevel")
                    if current_admin_level is not None and current_admin_level >= 0:
                        for check_level in range(current_admin_level, -1, -1):
                            level_matches = [
                                m for m in filtered_matches
                                if m.get("admin_level", 0) == check_level
                            ]
                            if level_matches:
                                filtered_matches = level_matches
                                logger.debug(
                                    f"Admin level filter: {len(level_matches)} matches at level {check_level} "
                                    f"(viewing level {current_admin_level})"
                                )
                                break

                    if len(filtered_matches) > 1 and viewport.get("bounds"):
                        countries_in_view = get_countries_in_viewport(viewport["bounds"])
                        if countries_in_view:
                            country_matches = [
                                m for m in filtered_matches
                                if m.get("iso3", "").split("-")[0] in countries_in_view
                            ]
                            if country_matches:
                                filtered_matches = country_matches

                    if len(filtered_matches) == 1:
                        match = filtered_matches[0]
                        location = {
                            "matched_term": match.get("matched_term", matched_term),
                            "iso3": match.get("iso3", iso3),
                            "loc_id": match.get("loc_id"),
                            "country_name": match.get("country_name", country_name),
                            "is_subregion": match.get("is_subregion", is_subregion),
                            "source": "viewport_resolved",
                        }
                        resolved_by_viewport = True
                        logger.info(f"Viewport auto-resolved '{matched_term}' to {match.get('loc_id')}")
                    elif len(filtered_matches) > 1:
                        disambiguation = {
                            "needed": True,
                            "query_term": matched_term,
                            "options": filtered_matches,
                            "count": len(filtered_matches)
                        }
                        resolved_by_viewport = True

                if not resolved_by_viewport:
                    disambiguation = {
                        "needed": True,
                        "query_term": matched_term,
                        "options": matches,
                        "count": len(matches)
                    }

    return {
        "nav_intent": nav_intent,
        "navigation": navigation,
        "disambiguation": disambiguation,
        "source_candidates": source_candidates,
        "detected_source": detected_source,
        "location": location,
        "query_constraints": query_constraints,
    }


def build_preprocessor_hints(
    *,
    query: str,
    viewport: dict | None = None,
    show_borders: dict | None = None,
    navigation: dict | None = None,
    address_prompt: dict | None = None,
    topics: list | None = None,
    regions: list | None = None,
    location: dict | None = None,
    disambiguation: dict | None = None,
    time_hints: dict | None = None,
    reference_lookup: dict | None = None,
    derived_intent: dict | None = None,
    tutorial_mode: dict | None = None,
    detected_source: dict | None = None,
    active_overlays: dict | None = None,
    cache_stats: dict | None = None,
    filter_intent: dict | None = None,
    overlay_intent: dict | None = None,
    candidates: dict | None = None,
    saved_order_names: list | None = None,
    time_state: dict | None = None,
    loaded_data: list | None = None,
    query_constraints: dict | None = None,
) -> dict:
    return {
        "original_query": query,
        "viewport": viewport,
        "show_borders": show_borders if show_borders and show_borders.get("is_show_borders") else None,
        "navigation": navigation,
        "address_prompt": address_prompt,
        "topics": topics or [],
        "regions": regions or [],
        "location": location,
        "disambiguation": disambiguation,
        "time": time_hints or {},
        "reference_lookup": reference_lookup,
        "derived_intent": derived_intent,
        "tutorial_mode": tutorial_mode,
        "detected_source": detected_source,
        "active_overlays": active_overlays,
        "cache_stats": cache_stats,
        "filter_intent": filter_intent,
        "overlay_intent": overlay_intent,
        "candidates": candidates or {},
        "saved_order_names": saved_order_names or [],
        "time_state": time_state,
        "loaded_data": loaded_data or [],
        "query_constraints": query_constraints or {},
    }


def build_candidate_bundle(
    *,
    query: str,
    viewport: dict | None = None,
    source_candidates: dict,
    detect_location_candidates,
    detect_intent_candidates,
    adjust_scores_with_context,
) -> dict:
    """Build the cross-scored candidate bundle for source/location/intent hints."""
    location_candidates = detect_location_candidates(query, viewport)
    intent_candidates = detect_intent_candidates(query, source_candidates, location_candidates)
    adjusted = adjust_scores_with_context(source_candidates, location_candidates, intent_candidates)
    return {
        "sources": adjusted["sources"],
        "locations": adjusted["locations"],
        "intents": adjusted["intents"],
    }
