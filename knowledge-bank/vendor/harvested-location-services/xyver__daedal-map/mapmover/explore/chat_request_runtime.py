"""Explore lane request-preparation helpers shared by chat endpoints."""

from __future__ import annotations

from mapmover.catalog_surface import catalog_surface_scope
import re


_EXACT_EVENT_MISS_RE = re.compile(
    r"\bcould not find exact event\s+([A-Za-z0-9._:-]+)\s+in\s+([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def _normalize_history_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text)
            elif isinstance(item, str) and item.strip():
                parts.append(item)
        return " ".join(parts)
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text
    return ""


def _sanitize_chat_history(chat_history: list, query: str) -> list:
    if not isinstance(chat_history, list) or not chat_history:
        return chat_history or []

    current_query = str(query or "").strip().lower()
    if not current_query:
        return chat_history

    sanitized = list(chat_history)
    while sanitized:
        last_message = sanitized[-1]
        if not isinstance(last_message, dict):
            break
        if str(last_message.get("role") or "").strip().lower() != "assistant":
            break
        assistant_text = _normalize_history_text(last_message.get("content")).strip()
        match = _EXACT_EVENT_MISS_RE.search(assistant_text)
        if not match:
            break

        missed_identifier = str(match.group(1) or "").strip().lower()
        if not missed_identifier or missed_identifier in current_query:
            break

        sanitized.pop()
        if sanitized:
            previous_message = sanitized[-1]
            if isinstance(previous_message, dict) and str(previous_message.get("role") or "").strip().lower() == "user":
                sanitized.pop()
        continue

    return sanitized


def prepare_explore_request(
    *,
    body: dict,
    route_context,
    explore_orchestrator,
    extract_chat_request_context_func,
    maybe_build_shortcut_payload_func,
    address_prompt_response_func,
    build_show_borders_response_func,
    build_drilldown_response_func,
    fetch_geometries_by_loc_ids_func,
    apply_selected_popup_override_func,
    auth_user=None,
    load_source_metadata_func=None,
    load_source_reference_func=None,
    build_chat_response_func=None,
) -> dict:
    request_context = extract_chat_request_context_func(body)
    query = request_context["query"]
    chat_history = _sanitize_chat_history(request_context["chat_history"], query)
    viewport = request_context["viewport"]
    resolved_location = request_context["resolved_location"]
    active_overlays = request_context["active_overlays"]
    cache_stats = request_context["cache_stats"]
    time_state = request_context["time_state"]
    saved_order_names = request_context["saved_order_names"]
    loaded_data = request_context["loaded_data"]
    selected_popup = request_context.get("selected_popup")

    if not query:
        return {
            "request_context": request_context,
            "query": query,
            "chat_history": chat_history,
            "hints": {},
            "shortcut_payload": None,
        }

    with catalog_surface_scope(route_context.catalog_surface):
        hints = explore_orchestrator.preprocess(
            query=query,
            viewport=viewport,
            active_overlays=active_overlays,
            cache_stats=cache_stats,
            saved_order_names=saved_order_names,
            time_state=time_state,
            loaded_data=loaded_data,
            resolved_location=resolved_location,
            selected_popup=selected_popup,
        )
        if selected_popup:
            hints = apply_selected_popup_override_func(hints, selected_popup)

    shortcut_payload = maybe_build_shortcut_payload_func(
        hints=hints,
        request_context=request_context,
        query=query,
        address_prompt_response_func=address_prompt_response_func,
        build_show_borders_response_func=build_show_borders_response_func,
        build_drilldown_response_func=build_drilldown_response_func,
        fetch_geometries_by_loc_ids_func=fetch_geometries_by_loc_ids_func,
        auth_user=auth_user,
        load_source_metadata_func=load_source_metadata_func,
        load_source_reference_func=load_source_reference_func,
        build_chat_response_func=build_chat_response_func,
    )
    return {
        "request_context": request_context,
        "query": query,
        "chat_history": chat_history,
        "hints": hints,
        "shortcut_payload": shortcut_payload,
    }
