"""Postprocessing helpers for Research mode."""

from __future__ import annotations

from copy import deepcopy


_TOP_LEVEL_DISPLAY_KEYS = (
    "action",
    "geojson",
    "loc_ids",
    "years",
    "data_type",
    "source_id",
    "artifact_id",
    "geographic_level",
    "fit",
    "context_visibility",
    "style",
    "raster",
    "metric",
    "metric_key",
    "available_metrics",
    "metric_year_ranges",
    "scene_periods",
    "raster_clip_levels",
)


def _extract_top_level_display(payload: dict) -> dict | None:
    display = {key: payload.get(key) for key in _TOP_LEVEL_DISPLAY_KEYS if key in payload}
    if not display:
        return None
    if not any(key in display for key in ("geojson", "raster", "action")):
        return None
    return display


def _coerce_display(display: dict, research_hints: dict | None) -> dict | None:
    geojson = display.get("geojson") or {}
    features = geojson.get("features") or []
    loc_ids = display.get("loc_ids") or []
    action = str(display.get("action") or "").strip()
    raster = display.get("raster")
    has_raster = isinstance(raster, dict) and str(raster.get("provider") or "").strip()
    if action != "highlight_features" and not has_raster:
        return None
    if action == "highlight_features" and (not features or not loc_ids):
        return None

    display["fit"] = bool(display.get("fit", True))
    display["context_visibility"] = str(display.get("context_visibility") or "keep")
    style = display.get("style")
    if isinstance(style, dict):
        normalized_style = {}
        fill_color = str(style.get("fill_color") or "").strip()
        stroke_color = str(style.get("stroke_color") or "").strip()
        if fill_color:
            normalized_style["fill_color"] = fill_color
        if stroke_color:
            normalized_style["stroke_color"] = stroke_color
        if normalized_style:
            display["style"] = normalized_style
        else:
            display.pop("style", None)
    else:
        display.pop("style", None)

    hint_time = (research_hints or {}).get("time") or {}
    specific_year = hint_time.get("specific_year")
    if isinstance(raster, dict):
        source_id = str(raster.get("source_id") or raster.get("provider") or "").strip()
        if source_id:
            normalized_raster = {"source_id": source_id}
            period = str(raster.get("period") or "").strip()
            if period:
                normalized_raster["period"] = period
            visibility = str(raster.get("visibility") or "").strip().lower()
            if visibility in {"show", "hide"}:
                normalized_raster["visibility"] = visibility
            year = raster.get("year")
            if isinstance(year, int):
                normalized_raster["year"] = year
            elif isinstance(specific_year, int):
                normalized_raster["year"] = specific_year
            display["raster"] = normalized_raster
        else:
            display.pop("raster", None)
    else:
        display.pop("raster", None)

    return display


def normalize_research_result(result: dict | None, *, lane: str = "research") -> dict:
    """Normalize a Research response into a frontend-safe shape."""
    payload = deepcopy(result or {})
    display = payload.get("display")
    displays = payload.get("displays")
    research_hints = payload.get("research_hints")

    if not isinstance(display, dict):
        extracted_display = _extract_top_level_display(payload)
        if extracted_display:
            payload["display"] = extracted_display
            display = extracted_display

    if isinstance(display, dict):
        display["lane"] = lane
        normalized = _coerce_display(display, research_hints)
        if not normalized:
            payload.pop("display", None)
        else:
            payload["display"] = normalized

    if isinstance(displays, list):
        normalized_displays = []
        for display_item in displays:
            if not isinstance(display_item, dict):
                continue
            next_display = dict(display_item)
            next_display["lane"] = lane
            normalized = _coerce_display(next_display, research_hints)
            if normalized:
                normalized_displays.append(normalized)
        if normalized_displays:
            payload["displays"] = normalized_displays
            payload["display"] = normalized_displays[-1]
        else:
            payload.pop("displays", None)

    return payload
