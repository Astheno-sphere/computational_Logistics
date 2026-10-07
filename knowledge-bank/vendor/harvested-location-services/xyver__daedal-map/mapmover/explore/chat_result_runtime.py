"""Explore lane result-adaptation helpers shared by chat endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from mapmover.catalog_surface import catalog_surface_scope
from mapmover.explore.chat_lane_runtime import (
    build_chat_payload,
    build_clarify_payload,
    build_navigate_payload,
)


def _valid_year(value) -> int | None:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None


def _maybe_build_overlay_range_order_response(
    *,
    finalized_order: dict,
    hints: dict,
    load_source_metadata_func,
) -> dict | None:
    """Adapt a validated one-source order to an authored range-overlay action.

    Some event registries render through a source-owned timeline controller
    rather than generic GeoJSON event ingestion. Keep the interpretation and
    validation shared, then make the final display choice from metadata.
    """
    items = finalized_order.get("items") if isinstance(finalized_order, dict) else None
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return None
    item = items[0]
    source_id = str(item.get("source_id") or "").strip()
    if not source_id:
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

    time_hints = hints.get("time_hints") if isinstance(hints, dict) else {}
    start_year = _valid_year(item.get("year_start")) or _valid_year(item.get("year")) or _valid_year(time_hints.get("year_start"))
    end_year = _valid_year(item.get("year_end")) or _valid_year(item.get("year")) or _valid_year(time_hints.get("year_end"))
    if start_year is None or end_year is None:
        return None
    start_year, end_year = sorted((start_year, end_year))
    source_name = str(metadata.get("source_name") or source_id).strip()
    return {
        "type": "overlay_range_load",
        "overlay_id": overlay_id,
        "start_ms": int(datetime(start_year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000),
        "end_ms": int(datetime(end_year, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc).timestamp() * 1000),
        "message": f"Showing all compatible {source_name} records for {start_year}-{end_year}.",
        "source_id": source_id,
    }


def build_explore_final_result(
    *,
    result: dict,
    query: str,
    hints: dict,
    auth_user: dict | None,
    catalog_surface: str | None,
    force_metrics: bool,
    explore_orchestrator,
    build_clarify_response_func,
    build_metric_warning_response_func,
    build_order_response_func,
    build_navigate_response_func,
    execute_geometry_overlay_func,
    build_disambiguate_response_func,
    build_filter_update_response_func,
    build_overlay_toggle_response_func,
    build_chat_response_func,
    load_source_metadata_func,
    load_source_reference_func,
) -> tuple[str, dict, str | None]:
    result_type = result.get("type") or "chat"
    if result_type == "order":
        with catalog_surface_scope(catalog_surface):
            response_tag, final_result = explore_orchestrator.finalize_order(
                result=result,
                hints=hints,
                force_metrics=force_metrics,
                build_clarify_response_func=build_clarify_response_func,
                build_metric_warning_response_func=build_metric_warning_response_func,
                build_order_response_func=build_order_response_func,
            )
            if response_tag == "order":
                overlay_range = _maybe_build_overlay_range_order_response(
                    finalized_order=final_result.get("order") or {},
                    hints=hints,
                    load_source_metadata_func=load_source_metadata_func,
                )
                if overlay_range is not None:
                    return "overlay_range_load", overlay_range, None
        return response_tag, final_result, None

    if result_type == "navigate":
        return (
            "navigate",
            build_navigate_payload(
                result,
                query=query,
                build_navigate_response_func=build_navigate_response_func,
                execute_geometry_overlay_func=execute_geometry_overlay_func,
            ),
            None,
        )

    if result_type == "disambiguate":
        return "disambiguate", build_disambiguate_response_func(result, original_query=query), None

    if result_type == "filter_update":
        return "filter_update", build_filter_update_response_func(result), None

    if result_type == "overlay_toggle":
        return "overlay_toggle", build_overlay_toggle_response_func(result), None

    if result_type == "clarify":
        return (
            "clarify",
            build_clarify_payload(result, compact_followup_func=explore_orchestrator.compact_followup),
            None,
        )

    final_result, chat_message = build_chat_payload(
        result,
        query=query,
        hints=hints,
        auth_user=auth_user,
        compact_followup_func=explore_orchestrator.compact_followup,
        maybe_build_explainer_response_func=explore_orchestrator.maybe_build_explainer_response,
        build_chat_response_func=build_chat_response_func,
        load_source_metadata_func=load_source_metadata_func,
        load_source_reference_func=load_source_reference_func,
    )
    return "chat", final_result, chat_message
