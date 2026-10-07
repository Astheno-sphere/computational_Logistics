"""Shared payload helpers for confirmed-order route responses."""

from __future__ import annotations

from mapmover.runtime.result_cap import copy_cap_fields_to_payload


def build_confirmed_order_response_payload(
    result: dict,
    *,
    geojson: dict,
    count: int,
    year_data: dict | None = None,
) -> dict:
    response = {
        "type": result.get("type", "data"),
        "data_type": result.get("data_type"),
        "source_id": result.get("source_id"),
        # These are display semantics, not optional UI hints.  They must
        # survive dedupe/confirmed-order shaping so a fresh browser can render
        # the same layer from an otherwise cached backend result.
        "geographic_level": result.get("geographic_level"),
        "metric_key": result.get("metric_key"),
        "available_metrics": result.get("available_metrics", []),
        "metric_time_ranges": result.get("metric_time_ranges") or result.get("metric_year_ranges", {}),
        "popup_family": result.get("popup_family"),
        "point_display": result.get("point_display"),
        "available_geo_levels": result.get("available_geo_levels", []),
        "geojson": geojson,
        "summary": result.get("summary", ""),
        "count": result.get("count", count),
        "sources": result.get("sources", []),
    }
    response = copy_cap_fields_to_payload(response, result)

    if result.get("type") == "events":
        response["event_type"] = result.get("event_type")
        response["time_range"] = result.get("time_range")
    if result.get("data_type") == "geometry":
        geo_level = result.get("geographic_level") or result.get("overlay_type", "zcta")
        response["overlay_type"] = geo_level
        response["geographic_level"] = geo_level
    if result.get("multi_year"):
        # TEMPORARY MIRROR: confirmed-order responses should expose canonical
        # time_* fields now. Legacy year_* aliases remain only for the cleanup
        # pass after all consumers move over.
        response["time_range"] = result.get("time_range") or result.get("year_range")
        response["time_data"] = year_data if year_data else result.get("time_data", {})
        response["multi_year"] = True
        response["year_range"] = result["year_range"]
        response["metric_year_ranges"] = result.get("metric_year_ranges", {})
        response["year_data"] = year_data if year_data else {}
    return response
