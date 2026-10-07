"""Summary-string helpers for Explore preprocessor hints."""


def build_preprocessor_summary(
    hints: dict,
    *,
    navigation: dict | None = None,
    location: dict | None = None,
    disambiguation: dict | None = None,
    active_overlays: dict | None = None,
    filter_intent: dict | None = None,
    overlay_intent: dict | None = None,
    time_state: dict | None = None,
    saved_order_names: list | None = None,
    loaded_data: list | None = None,
    selected_popup: dict | None = None,
    format_filter_description_func=None,
) -> str | None:
    summary_parts = []

    if navigation:
        loc_names = [loc.get("matched_term", loc.get("loc_id", "?")) for loc in navigation["locations"]]
        summary_parts.append(f"NAVIGATION: Show {navigation['count']} locations: {', '.join(loc_names[:5])}")

    if hints.get("topics"):
        summary_parts.append(f"Topics detected: {', '.join(hints['topics'])}")

    if hints.get("regions"):
        region_names = [r["match"] for r in hints["regions"]]
        summary_parts.append(f"Regions mentioned: {', '.join(region_names)}")

    if location and not navigation:
        if disambiguation:
            summary_parts.append(f"AMBIGUOUS: '{location['matched_term']}' matches {disambiguation['count']} locations")
        elif location["is_subregion"]:
            summary_parts.append(f"Location: '{location['matched_term']}' -> {location['country_name']} ({location['iso3']})")
        else:
            summary_parts.append(f"Location: {location['country_name']} ({location['iso3']})")

    time_hints = hints.get("time") or {}
    if time_hints.get("is_time_series"):
        if time_hints.get("year_start") and time_hints.get("year_end"):
            summary_parts.append(f"Time range: {time_hints['year_start']}-{time_hints['year_end']}")
        else:
            summary_parts.append("Time series requested (trend/historical)")

    if hints.get("reference_lookup"):
        summary_parts.append(f"Reference lookup: {hints['reference_lookup']['type']}")

    if hints.get("derived_intent"):
        derived = hints["derived_intent"]
        derived_parts = [str(derived.get("type") or "derived")]
        if derived.get("start_year"):
            derived_parts.append(f"since {derived['start_year']}")
        elif derived.get("window_years"):
            derived_parts.append(f"last {derived['window_years']} years")
        elif derived.get("recent"):
            derived_parts.append("recent")
        summary_parts.append(f"Derived calculation: {' '.join(derived_parts)}")

    if hints.get("tutorial_mode"):
        summary_parts.append(f"TUTORIAL_MODE: {hints['tutorial_mode']['action']}")

    if hints.get("address_prompt"):
        summary_parts.append("ADDRESS_PROMPT: open address entry UI")

    if hints.get("detected_source"):
        summary_parts.append(f"Source specified: {hints['detected_source']['source_name']}")

    if active_overlays and active_overlays.get("type"):
        overlay_type = active_overlays["type"]
        filters = active_overlays.get("filters", {})
        filter_desc = format_filter_description_func(filters, overlay_type) if format_filter_description_func else str(filters)
        summary_parts.append(f"OVERLAY: {overlay_type} ({filter_desc})")

    if filter_intent:
        if filter_intent["type"] == "read_filters":
            summary_parts.append("INTENT: Query about current filters")
        elif filter_intent["type"] == "change_filters":
            summary_parts.append(f"INTENT: Change filters ({filter_intent.get('filter_type', 'unknown')})")

    if overlay_intent:
        action = overlay_intent.get("action", "unknown")
        overlay = overlay_intent.get("overlay", "unknown")
        severity = overlay_intent.get("severity")
        if action == "enable":
            summary_parts.append(f"OVERLAY_INTENT: Enable {overlay} overlay")
        elif action == "filter":
            summary_parts.append(f"OVERLAY_INTENT: Filter {overlay} ({severity})")
        elif action == "query":
            summary_parts.append(f"OVERLAY_INTENT: Query about {overlay}")

    if time_state and time_state.get("available"):
        if time_state.get("isLiveLocked"):
            tz = time_state.get("timezone", "local")
            summary_parts.append(f"TIME: LIVE MODE (locked to current time, timezone: {tz})")
        elif time_state.get("currentTimeFormatted"):
            summary_parts.append(f"TIME: Viewing {time_state['currentTimeFormatted']}")

    if saved_order_names:
        summary_parts.append(f"SAVED_ORDERS: {', '.join(saved_order_names)}")

    if loaded_data:
        loaded_strs = []
        for entry in loaded_data:
            src = entry.get("source_id", "?")
            region = entry.get("region", "global")
            metric = entry.get("metric")
            years = entry.get("years", "")
            if metric:
                loaded_strs.append(f"{src}: {metric} in {region} ({years})")
            else:
                loaded_strs.append(f"{src}: {region} ({years})")
        summary_parts.append(f"LOADED_DATA: {'; '.join(loaded_strs)}")

    if selected_popup:
        popup_kind = selected_popup.get("kind") or "popup"
        popup_name = selected_popup.get("name") or selected_popup.get("event_id") or selected_popup.get("loc_id") or "selected item"
        popup_event_type = selected_popup.get("event_type")
        popup_bits = [f"POPUP: {popup_kind}"]
        if popup_event_type:
            popup_bits.append(f"type={popup_event_type}")
        popup_bits.append(f"item={popup_name}")
        summary_parts.append(" ".join(popup_bits))

    return "; ".join(summary_parts) if summary_parts else None
