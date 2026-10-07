"""Explore-lane route helpers shared across chat endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import re

from mapmover.routes.disasters.related import search_named_event_candidates
from mapmover.runtime.explainer_response import (
    build_explainer_response,
    build_view_orientation_response,
    looks_like_orientation_question,
)


_EXACT_EVENT_MISS_RE = re.compile(r"\bcould not find exact event\b", re.IGNORECASE)


def _event_search_pack_hint(query: str, hints: dict) -> str | None:
    detected_source = hints.get("detected_source") if isinstance(hints, dict) else None
    if isinstance(detected_source, dict):
        pack_id = str(detected_source.get("pack_id") or "").strip().lower()
        if pack_id:
            return pack_id

    query_text = str(query or "").lower()
    if any(token in query_text for token in ("volcano", "volcanoes", "volcanos", "eruption", "eruptions")):
        return "volcanoes"
    if any(token in query_text for token in ("hurricane", "storm", "cyclone", "typhoon")):
        return "hurricanes"
    return None


def maybe_build_named_event_search_response(
    *,
    result: dict,
    query: str,
    hints: dict,
    build_chat_response_func,
) -> dict | None:
    message = str(result.get("message") or "").strip()
    if not _EXACT_EVENT_MISS_RE.search(message):
        return None

    pack_hint = _event_search_pack_hint(query, hints)
    matches = search_named_event_candidates(query, pack_id=pack_hint, limit=5)
    if not matches:
        return None

    lines = ["I found named event matches you can open directly:"]
    for match in matches[:5]:
        label = str(match.get("label") or match.get("event_id") or "Unnamed event").strip()
        event_id = str(match.get("event_id") or "").strip()
        extras: list[str] = []
        if match.get("country"):
            extras.append(str(match["country"]).strip())
        if match.get("year") is not None:
            extras.append(str(match["year"]))
        suffix = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"{label}: {event_id}{suffix}")

    lines.append("Use the event id directly, or ask me to load one of those on the map.")
    return build_chat_response_func("\n".join(lines), pack_id=pack_hint)


def build_tutorial_mode_payload(hints: dict, tutorial_mode: dict | None) -> dict:
    action = hints["tutorial_mode"].get("action", "toggle")
    current_enabled = bool((tutorial_mode or {}).get("enabled"))
    enabled = (not current_enabled) if action == "toggle" else (action == "on")
    message = (
        "Tutorial mode on. Hover or tap a help marker to see what that part of the app does."
        if enabled
        else "Tutorial mode off."
    )
    return {
        "type": "tutorial_mode",
        "action": action,
        "enabled": enabled,
        "message": message,
    }


def _orientation_source_id(hints: dict, request_context: dict, query: str) -> str | None:
    """Choose a source named in the question, or the unambiguous active data."""
    detected = hints.get("detected_source") if isinstance(hints, dict) else None
    if isinstance(detected, dict) and str(detected.get("source_id") or "").strip():
        return str(detected["source_id"]).strip()
    if not looks_like_orientation_question(query):
        return None
    source_ids = []
    for item in request_context.get("loaded_data") or []:
        source_id = str((item or {}).get("source_id") or "").strip()
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
    # Contextual questions with multiple layers receive an honest shared
    # context response below, rather than silently choosing one source.
    return source_ids[0] if len(source_ids) == 1 else None


def maybe_build_orientation_payload(
    *,
    hints: dict,
    request_context: dict,
    query: str,
    auth_user: dict | None,
    load_source_metadata_func,
    load_source_reference_func,
    build_chat_response_func,
) -> dict | None:
    """Return curated source orientation before invoking the order-taking LLM."""
    source_id = _orientation_source_id(hints, request_context, query)
    if not looks_like_orientation_question(query):
        return None
    if not source_id:
        explainer = build_view_orientation_response(request_context, lane="explore")
        if not isinstance(explainer, dict):
            return None
        return build_chat_response_func(
            explainer["text"], auth_user=auth_user, explainer_sections=explainer.get("sections"),
        )
    metadata = load_source_metadata_func(source_id) or {}
    if not isinstance(metadata, dict):
        return None
    metadata.setdefault("source_id", source_id)
    reference = load_source_reference_func(source_id) or {}
    explainer = build_explainer_response(
        metadata,
        query,
        reference,
        lane="explore",
        view_context=request_context,
        # We already cleared looks_like_orientation_question above and resolved
        # the single loaded source, so context-orientation phrasing is in scope.
        allow_orientation=True,
    )
    if not isinstance(explainer, dict):
        return None
    return build_chat_response_func(
        explainer.get("text") or "I do not have a fuller source description yet.",
        auth_user=auth_user,
        source_id=explainer.get("source_id"),
        pack_id=explainer.get("pack_id"),
        explainer_sections=explainer.get("sections"),
        stub_order=explainer.get("stub_order"),
    )


def maybe_build_explicit_overlay_range_payload(
    *,
    hints: dict,
    load_source_metadata_func,
) -> dict | None:
    """Turn an explicit source time range into its authored overlay action.

    This is intentionally metadata-driven: a source that declares an
    ``overlay_range_load`` default uses the same map action whether the range
    arrived from chat, a share URL, or a catalog entry. The default range is
    only a starting view; it never replaces an explicit user range.
    """
    detected = hints.get("detected_source") if isinstance(hints, dict) else None
    time_hints = hints.get("time_hints") if isinstance(hints, dict) else None
    if not isinstance(detected, dict) or not isinstance(time_hints, dict):
        return None
    source_id = str(detected.get("source_id") or "").strip()
    start_year = time_hints.get("year_start")
    end_year = time_hints.get("year_end")
    if not source_id or not isinstance(start_year, int) or not isinstance(end_year, int):
        return None

    metadata = load_source_metadata_func(source_id) or {}
    default_load = metadata.get("default_load") if isinstance(metadata, dict) else None
    if not isinstance(default_load, dict):
        return None
    if str(default_load.get("kind") or default_load.get("type") or "").strip() != "overlay_range_load":
        return None
    overlay_id = str(default_load.get("overlay_id") or "").strip()
    if not overlay_id:
        return None

    start_year, end_year = sorted((start_year, end_year))
    source_name = str(metadata.get("source_name") or detected.get("source_name") or source_id).strip()
    return {
        "type": "overlay_range_load",
        "overlay_id": overlay_id,
        "start_ms": int(datetime(start_year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000),
        "end_ms": int(datetime(end_year, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc).timestamp() * 1000),
        "message": f"Showing all compatible {source_name} records for {start_year}-{end_year}.",
        "source_id": source_id,
    }


def maybe_build_shortcut_payload(
    *,
    hints: dict,
    request_context: dict,
    query: str,
    address_prompt_response_func,
    build_show_borders_response_func,
    build_drilldown_response_func,
    fetch_geometries_by_loc_ids_func,
    auth_user=None,
    load_source_metadata_func=None,
    load_source_reference_func=None,
    build_chat_response_func=None,
):
    if all((load_source_metadata_func, load_source_reference_func, build_chat_response_func)):
        explicit_overlay_range = maybe_build_explicit_overlay_range_payload(
            hints=hints,
            load_source_metadata_func=load_source_metadata_func,
        )
        if explicit_overlay_range is not None:
            return explicit_overlay_range
        orientation = maybe_build_orientation_payload(
            hints=hints,
            request_context=request_context,
            query=query,
            auth_user=auth_user,
            load_source_metadata_func=load_source_metadata_func,
            load_source_reference_func=load_source_reference_func,
            build_chat_response_func=build_chat_response_func,
        )
        if orientation is not None:
            return orientation

    if hints.get("tutorial_mode"):
        return build_tutorial_mode_payload(hints, request_context.get("tutorial_mode"))

    if hints.get("address_prompt"):
        return address_prompt_response_func(hints.get("address_prompt"))

    if hints.get("show_borders"):
        previous_options = request_context.get("previous_disambiguation_options")
        loc_ids_to_show = [opt.get("loc_id") for opt in previous_options if opt.get("loc_id")] if previous_options else []
        if loc_ids_to_show:
            geojson = fetch_geometries_by_loc_ids_func(loc_ids_to_show)
            return build_show_borders_response_func(previous_options, original_query=query, geojson=geojson)

    navigation = hints.get("navigation")
    if navigation and navigation.get("is_navigation"):
        locations = navigation.get("locations", [])
        if len(locations) == 1 and locations[0].get("drill_to_level"):
            return build_drilldown_response_func(locations[0], original_query=query)
    return None


def build_navigate_payload(
    result: dict,
    *,
    query: str,
    build_navigate_response_func,
    execute_geometry_overlay_func,
) -> dict:
    locations = result.get("locations", [])
    loc_ids = [loc.get("loc_id") for loc in locations if loc.get("loc_id")]
    geometry_overlay = result.get("geometry_overlay")
    geojson = {"type": "FeatureCollection", "features": []}
    if geometry_overlay:
        geojson = execute_geometry_overlay_func(geometry_overlay, loc_ids)
    return build_navigate_response_func(result, loc_ids=loc_ids, original_query=query, geojson=geojson)


def build_clarify_payload(result: dict, *, compact_followup_func) -> dict:
    return {
        "type": "clarify",
        "message": compact_followup_func(result.get("message", "")),
        "geojson": {"type": "FeatureCollection", "features": []},
        "needsMoreInfo": True,
    }


def build_chat_payload(
    result: dict,
    *,
    query: str,
    hints: dict,
    auth_user,
    compact_followup_func,
    maybe_build_explainer_response_func,
    build_chat_response_func,
    load_source_metadata_func,
    load_source_reference_func,
) -> tuple[dict, str]:
    named_event_search_result = maybe_build_named_event_search_response(
        result=result,
        query=query,
        hints=hints,
        build_chat_response_func=build_chat_response_func,
    )
    if named_event_search_result is not None:
        chat_result = named_event_search_result.get("message", "")
        return named_event_search_result, chat_result

    explainer_result = maybe_build_explainer_response_func(
        query=query,
        hints=hints,
        build_chat_response_func=build_chat_response_func,
        auth_user=auth_user,
        load_source_metadata_func=load_source_metadata_func,
        load_source_reference_func=load_source_reference_func,
    )
    if explainer_result is not None:
        chat_payload = explainer_result
        chat_result = chat_payload.get("message", "")
        return chat_payload, chat_result
    chat_result = compact_followup_func(result.get("message", "I'm not sure how to help with that."))
    return build_chat_response_func(chat_result, auth_user=auth_user), chat_result
