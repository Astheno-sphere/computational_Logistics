"""Explore response-shaping helpers for route adapters."""

from __future__ import annotations

from mapmover.runtime.result_cap import apply_cap_info_to_payload


def build_clarify_response(message: str, *, summary: str | None = None, full_order: dict | None = None) -> dict:
    """Build a clarify response payload."""
    response = {
        "type": "clarify",
        "message": message,
    }
    if summary is not None:
        response["summary"] = summary
    if full_order is not None:
        response["full_order"] = full_order
    return response


def build_order_response(
    order: dict,
    processed: dict,
    *,
    display_items: list,
    summary: str,
) -> dict:
    """Build the Explore order response payload."""
    return {
        "type": "order",
        "order": {**order, "items": display_items, "derived_specs": processed.get("derived_specs", [])},
        "full_order": processed,
        "summary": summary,
        "validation_summary": processed.get("validation_summary"),
        "all_valid": processed.get("all_valid", True),
    }

def build_navigate_response(
    result: dict,
    *,
    loc_ids: list,
    original_query: str,
    geojson: dict,
) -> dict:
    """Build a navigate response payload."""
    return {
        "type": "navigate",
        "data_type": "geometry" if result.get("geometry_overlay") else None,
        "message": result.get("message", f"Showing {len(result.get('locations', []))} location(s)"),
        "locations": result.get("locations", []),
        "loc_ids": loc_ids,
        "original_query": original_query,
        "geojson": geojson,
        "geometry_overlay": result.get("geometry_overlay"),
    }


def build_disambiguate_response(result: dict, *, original_query: str) -> dict:
    """Build a disambiguation response payload."""
    return {
        "type": "disambiguate",
        "message": result.get("message", "Multiple locations found. Please select one."),
        "query_term": result.get("query_term", "location"),
        "original_query": original_query,
        "options": result.get("options", []),
        "geojson": {"type": "FeatureCollection", "features": []},
    }


def build_filter_update_response(result: dict) -> dict:
    """Build a filter update payload."""
    return {
        "type": "filter_update",
        "overlay": result.get("overlay", ""),
        "filters": result.get("filters", {}),
        "message": result.get("message", "Updating filters"),
    }


def build_overlay_toggle_response(result: dict) -> dict:
    """Build an overlay toggle payload."""
    return {
        "type": "overlay_toggle",
        "overlay": result.get("overlay", ""),
        "enabled": result.get("enabled", True),
        "message": result.get("message", "Toggling overlay"),
    }


def build_chat_response(
    message: str,
    *,
    auth_user: dict | None = None,
    source_id: str | None = None,
    pack_id: str | None = None,
    explainer_sections: dict | None = None,
    stub_order: dict | None = None,
    cap_info: dict | None = None,
) -> dict:
    """Build a plain chat response payload."""
    response = {
        "type": "chat",
        "message": message,
        "geojson": {"type": "FeatureCollection", "features": []},
        "auth_user": {"id": auth_user.get("id"), "email": auth_user.get("email")} if auth_user else None,
        "needsMoreInfo": False,
    }
    if source_id:
        response["source_id"] = source_id
    if pack_id:
        response["pack_id"] = pack_id
    if isinstance(explainer_sections, dict) and explainer_sections:
        response["explainer_sections"] = explainer_sections
    if isinstance(stub_order, dict) and stub_order:
        response["stub_order"] = stub_order
    return apply_cap_info_to_payload(response, cap_info)
