"""Explore request-context helpers."""

from __future__ import annotations


def extract_chat_request_context(body: dict) -> dict:
    """Extract the Explore chat request fields used by the route workflow."""
    return {
        "query": body.get("query", ""),
        "chat_history": body.get("chatHistory", []),
        "viewport": body.get("viewport"),
        "resolved_location": body.get("resolved_location"),
        "active_overlays": body.get("activeOverlays"),
        "cache_stats": body.get("cacheStats"),
        "time_state": body.get("timeState"),
        "saved_order_names": body.get("savedOrderNames", []),
        "loaded_data": body.get("loadedData", []),
        "selected_popup": body.get("selectedPopup"),
        "tutorial_mode": body.get("tutorialMode", {}),
        "previous_disambiguation_options": body.get("previous_disambiguation_options", []),
    }


def apply_resolved_location_override(hints: dict, resolved_location: dict | None) -> dict:
    """Merge an explicit frontend disambiguation selection into Explore hints."""
    if not resolved_location:
        return hints

    hints["location"] = {
        "matched_term": resolved_location.get("matched_term"),
        "iso3": resolved_location.get("iso3"),
        "country_name": resolved_location.get("country_name"),
        "loc_id": resolved_location.get("loc_id"),
        "is_subregion": resolved_location.get("loc_id") != resolved_location.get("iso3"),
        "source": "disambiguation_selection",
    }
    hints["disambiguation"] = None
    return hints


def apply_selected_popup_override(hints: dict, selected_popup: dict | None) -> dict:
    """Attach compact popup-selection context to Explore hints."""
    if not isinstance(selected_popup, dict):
        return hints

    properties = selected_popup.get("properties") if isinstance(selected_popup.get("properties"), dict) else {}
    popup_context = {
        "kind": selected_popup.get("kind"),
        "event_type": selected_popup.get("event_type"),
        "event_id": selected_popup.get("event_id"),
        "loc_id": selected_popup.get("loc_id") or properties.get("loc_id"),
        "name": selected_popup.get("name") or properties.get("name"),
        "country_name": selected_popup.get("country_name") or properties.get("country_name"),
        "iso3": selected_popup.get("iso3") or properties.get("iso3") or properties.get("country_code") or properties.get("iso_a3"),
        "properties": properties,
    }
    hints["selected_popup"] = popup_context

    if not hints.get("location") and popup_context.get("loc_id"):
        iso3 = popup_context.get("iso3") or str(popup_context["loc_id"]).split("-")[0]
        country_name = popup_context.get("country_name") or iso3
        matched_term = popup_context.get("name") or country_name
        hints["location"] = {
            "matched_term": matched_term,
            "iso3": iso3,
            "country_name": country_name,
            "loc_id": popup_context["loc_id"],
            "is_subregion": popup_context["loc_id"] != iso3,
            "source": "popup_selection",
        }
        hints["disambiguation"] = None
    return hints
