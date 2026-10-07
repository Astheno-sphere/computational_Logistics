"""Explore-specific confirmed-order cache delta helpers."""

from __future__ import annotations

from mapmover import logger
from mapmover.runtime.confirmed_order_response_runtime import (
    build_confirmed_order_response_payload,
)


_EVENT_TYPE_TO_OVERLAY = {
    "earthquake": "earthquakes",
    "volcano": "volcanoes",
    "tsunami": "tsunamis",
    "hurricane": "hurricanes",
    "wildfire": "wildfires",
    "tornado": "tornadoes",
    "flood": "floods",
    "drought": "drought",
    "landslide": "landslides",
}


def shape_confirmed_order_delta_response(result: dict, cache) -> dict | None:
    is_events = result.get("type") == "events"
    is_geometry = result.get("data_type") == "geometry"
    event_type = str(result.get("event_type") or "").strip()
    source_id = (
        _EVENT_TYPE_TO_OVERLAY.get(event_type, event_type)
        if is_events
        else result.get("metric_key", "data")
    )
    geojson = result["geojson"]
    features = geojson.get("features", [])
    original_count = len(features)

    new_features, filtered_geojson, filtered_time_data = _filter_confirmed_order_payload(
        result=result,
        cache=cache,
        features=features,
        geojson=geojson,
        is_events=is_events,
        is_geometry=is_geometry,
    )
    delta_count = len(new_features)

    if delta_count == 0 and original_count > 0:
        if is_geometry:
            # Backend session dedupe outlives the disposable browser view.
            # Geometry/point layers do not have a universal OverlayController
            # cache to rebuild from, so return the canonical payload for a
            # renderer recovery rather than strand a fresh map with an
            # `already_loaded` acknowledgement and no visible layer.
            logger.debug("Dedup: restoring %s cached geometry features to the browser", original_count)
            return build_confirmed_order_response_payload(
                result,
                geojson=geojson,
                count=original_count,
            )
        logger.debug("Dedup: all %s features already sent, returning already_loaded", original_count)
        return {
            "type": "already_loaded",
            "message": f"This data ({original_count} features) is already loaded on your map.",
            "summary": result.get("summary", ""),
        }

    response = build_confirmed_order_response_payload(
        result,
        geojson=filtered_geojson,
        count=delta_count,
        year_data=filtered_time_data,
    )
    _register_confirmed_order_delta(
        result=result,
        cache=cache,
        new_features=new_features,
        filtered_time_data=filtered_time_data,
        source_id=source_id,
        is_events=is_events,
        is_geometry=is_geometry,
    )

    if delta_count < original_count:
        logger.info(
            "Delta sent: %s/%s features (%s deduped)",
            delta_count,
            original_count,
            original_count - delta_count,
        )
    return response


def _filter_confirmed_order_payload(
    *,
    result: dict,
    cache,
    features: list,
    geojson: dict,
    is_events: bool,
    is_geometry: bool,
) -> tuple[list, dict, dict | None]:
    if is_events:
        new_features = cache.filter_events(features)
        return new_features, {"type": "FeatureCollection", "features": new_features}, None
    if is_geometry:
        new_features = cache.filter_geometry_features(features)
        return new_features, {"type": "FeatureCollection", "features": new_features}, None
    temporal_data = result.get("time_data") or result.get("year_data")
    if result.get("multi_year") and temporal_data:
        filtered_time_data = cache.filter_time_data(temporal_data)
        new_loc_ids = {
            loc_id
            for loc_data in filtered_time_data.values()
            for loc_id in loc_data.keys()
        }
        new_features = [
            feature
            for feature in features
            if (feature.get("properties", {}).get("loc_id") or feature.get("id")) in new_loc_ids
        ]
        return (
            new_features,
            {"type": "FeatureCollection", "features": new_features},
            filtered_time_data,
        )
    return features, geojson, None


def _register_confirmed_order_delta(
    *,
    result: dict,
    cache,
    new_features: list,
    filtered_time_data: dict | None,
    source_id,
    is_events: bool,
    is_geometry: bool,
) -> None:
    if is_events and new_features:
        cache.register_sent_events(new_features, source_id)
        return
    if is_geometry and new_features:
        geo_source_id = result.get("source_id") or "geometry_zcta"
        cache.register_sent_geometry(new_features, geo_source_id)
        return
    if filtered_time_data:
        cache.register_sent_time_data(filtered_time_data)
