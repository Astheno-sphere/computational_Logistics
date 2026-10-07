"""
Live point-feed Ops overlays (location with updating data).

Reusable backend for Ops map overlays whose collector snapshot carries a list of
fixed locations, each with current readings -- ocean buoys, weather stations,
sensors, points of interest. One generic builder + a per-feed registry entry, so
adding the next station feed is config, not code.

A point feed is a Type B (live_only) collector whose snapshot payload_summary
holds `items_key` -> [ {lat_key, lon_key, ...props} ]. The builder reads that
collector's current-state snapshot, shapes a GeoJSON FeatureCollection of points,
and caches it on snapshot identity (rebuilds once per collector poll, not per
read). Served generically via GET /api/ops/points/{overlay_id}.

See county-map-private/docs/CLIMATE_DISPLAY.md (Live Point Feeds).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from typing import Optional

from mapmover.ops_ticker import (
    get_cached_live_snapshot,
    _get_cached_view,
    _snapshot_identity,
)

_POINT_FEED_CACHE_TTL_SECONDS = 60.0


@dataclass(frozen=True)
class PointFeedSpec:
    """How to turn one collector's snapshot into a GeoJSON point overlay."""
    collector: str                       # collector name (snapshot source)
    items_key: str                       # payload_summary key holding the point list
    lat_key: str = "lat"
    lon_key: str = "lon"
    property_keys: tuple[str, ...] = field(default_factory=tuple)  # props to carry per point
    row_schema: tuple[str, ...] = field(default_factory=tuple)  # compact collector rows, when used
    wip_only: bool = False


# Registry of live point feeds. Add an entry to surface a new station/sensor feed.
POINT_FEEDS: dict[str, PointFeedSpec] = {
    "buoys": PointFeedSpec(
        collector="noaa_ndbc",
        items_key="buoys",
        lat_key="lat",
        lon_key="lon",
        property_keys=("station_id", "sst_c", "air_c", "wave_m", "wind_mps", "obs_utc"),
    ),
    "airnow": PointFeedSpec(
        collector="airnow",
        items_key="reporting_areas",
        lat_key="lat",
        lon_key="lon",
        property_keys=(
            "reporting_area", "state", "parameter", "aqi", "category", "observed_at",
            "agency", "action_day",
        ),
        row_schema=(
            "reporting_area", "state", "parameter", "aqi", "category", "lat", "lon",
            "observed_at", "agency", "action_day",
        ),
        wip_only=True,
    ),
    "openaq": PointFeedSpec(
        collector="openaq", items_key="samples",
        property_keys=("location_id", "station_name", "locality", "country", "provider", "owner", "license", "license_policy", "license_status", "attribution", "is_mobile", "measurements", "observed_at"),
        row_schema=("location_id", "station_name", "locality", "country", "provider", "owner", "license", "license_policy", "license_status", "attribution", "is_mobile", "lat", "lon", "measurements", "observed_at"),
        wip_only=True,
    ),
}


def is_point_feed(overlay_id: str) -> bool:
    return str(overlay_id or "").strip() in POINT_FEEDS


def _assemble_points_geojson(spec: PointFeedSpec, summary: dict) -> dict:
    items = summary.get(spec.items_key) or []
    features = []
    for item in items:
        if not isinstance(item, dict) and spec.row_schema and isinstance(item, (list, tuple)):
            item = dict(zip(spec.row_schema, item))
        if not isinstance(item, dict):
            continue
        lat = item.get(spec.lat_key)
        lon = item.get(spec.lon_key)
        if lat is None or lon is None:
            continue
        props = {key: item.get(key) for key in spec.property_keys}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props,
        })
    return {"type": "FeatureCollection", "features": features, "count": len(features)}


def build_point_overlay_for_snapshot(overlay_id: str, snapshot: dict | None) -> dict:
    """Render one retained collector snapshot as a point-overlay frame.

    The same shape is used for the live view and the Ops cursor.  Keeping this
    conversion here prevents historical point frames from dropping fields or
    silently using today's readings while the cursor is in the past.
    """
    spec = POINT_FEEDS.get(str(overlay_id or "").strip())
    summary = snapshot.get("payload_summary") if isinstance(snapshot, dict) else {}
    return _assemble_points_geojson(spec, summary if isinstance(summary, dict) else {}) if spec else {
        "type": "FeatureCollection", "features": [], "count": 0,
    }


def build_cached_point_overlay(
    overlay_id: str,
    *,
    bbox: Optional[tuple[float, float, float, float]] = None,
    zoom: Optional[float] = None,
) -> dict:
    """Response-cached GeoJSON point overlay for a registered live point feed."""
    overlay_id = str(overlay_id or "").strip()
    if overlay_id == "air_quality_stations":
        return _visible_air_quality_stations(_build_air_quality_stations(), bbox=bbox, zoom=zoom)
    spec = POINT_FEEDS.get(overlay_id)
    if spec is None:
        return {"type": "FeatureCollection", "features": [], "count": 0}
    snap = get_cached_live_snapshot(spec.collector)
    snapshot = snap if isinstance(snap, dict) else {}

    def _builder() -> dict:
        return build_point_overlay_for_snapshot(overlay_id, snapshot)

    return _get_cached_view(
        f"ops_points_{overlay_id}",
        cache_identity=_snapshot_identity(snapshot),
        ttl_seconds=_POINT_FEED_CACHE_TTL_SECONDS,
        builder=_builder,
    )


def _aqi_color(value) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "#9aa4bf"
    for threshold, color in ((301, "#7e0023"), (201, "#8f3f97"), (151, "#ff0000"), (101, "#ff7e00"), (51, "#ffff00")):
        if value >= threshold:
            return color
    return "#00e400"


def _build_air_quality_stations() -> dict:
    """One selector family, with source-native point semantics preserved."""
    airnow = get_cached_live_snapshot("airnow") or {}
    openaq = get_cached_live_snapshot("openaq") or {}
    openaq_licences = get_cached_live_snapshot("openaq_license_index") or {}
    identity = json.dumps([_snapshot_identity(airnow), _snapshot_identity(openaq), _snapshot_identity(openaq_licences)])

    def _builder() -> dict:
        features = []
        for feature in _assemble_points_geojson(POINT_FEEDS["airnow"], airnow.get("payload_summary") or {}).get("features") or []:
            props = feature["properties"]
            props.update({"source_label": "AirNow", "station_name": props.get("reporting_area"), "station_kind": "Agency reporting area", "value": props.get("aqi"), "unit": "AQI", "provider": props.get("agency"), "marker_color": _aqi_color(props.get("aqi")), "source_url": "https://www.airnow.gov/"})
            features.append(feature)
        for feature in _assemble_points_geojson(POINT_FEEDS["openaq"], openaq.get("payload_summary") or {}).get("features") or []:
            props = feature["properties"]
            location_id = props.get("location_id")
            provenance = ((openaq_licences.get("payload_summary") or {}).get("locations") or {}).get(str(location_id))
            if isinstance(provenance, dict):
                # The VPS provenance pager is authoritative for provider terms.
                # It overlays compact current observations without making the
                # Railway two-hour collector perform thousands of detail calls.
                props.update({key: provenance.get(key) for key in (
                    "station_name", "locality", "country", "provider", "owner", "license",
                    "license_policy", "license_status", "attribution", "is_mobile",
                ) if provenance.get(key) is not None})
            source_url = f"https://explore.openaq.org/locations/{location_id}" if location_id else "https://openaq.org/"
            props.update({"source_label": "OpenAQ", "station_kind": "Monitor (six-pollutant WIP index)", "marker_color": "#6a5acd", "source_url": source_url})
            features.append(feature)
        return {"type": "FeatureCollection", "features": features, "count": len(features), "total_count": len(features)}

    return _get_cached_view("ops_points_air_quality_stations", cache_identity=identity,
                            ttl_seconds=_POINT_FEED_CACHE_TTL_SECONDS, builder=_builder)


def _in_bbox(lon: float, lat: float, bbox: Optional[tuple[float, float, float, float]]) -> bool:
    if bbox is None:
        return True
    west, south, east, north = bbox
    if not south <= lat <= north:
        return False
    # A bounds box crossing the antimeridian has west > east.
    return west <= lon <= east if west <= east else lon >= west or lon <= east


def _visible_air_quality_stations(base: dict, *, bbox, zoom) -> dict:
    """Viewport-filter with gentle, source-separated low/mid-zoom merging."""
    visible = []
    for feature in base.get("features") or []:
        try:
            lon, lat = feature["geometry"]["coordinates"]
            lon, lat = float(lon), float(lat)
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if _in_bbox(lon, lat, bbox):
            visible.append(feature)
    # Preserve individual locations once a user is looking at a city/region.
    # Below that, use progressively smaller degree cells. This keeps the
    # global monitor layer legible without pretending a cluster is one station.
    if zoom is not None and zoom >= 6:
        return {"type": "FeatureCollection", "features": visible, "count": len(visible), "total_count": base.get("count", 0), "merged": False}

    zoom_value = float(zoom) if zoom is not None else 0.0
    cell_size = 5.0 if zoom_value < 2 else 2.0 if zoom_value < 3.5 else 0.75
    groups: dict[tuple[str, int, int], list[dict]] = {}
    for feature in visible:
        lon, lat = feature["geometry"]["coordinates"]
        source = str((feature.get("properties") or {}).get("source_label") or "Unknown")
        key = (source, math.floor((float(lon) + 180) / cell_size), math.floor((float(lat) + 90) / cell_size))
        groups.setdefault(key, []).append(feature)

    result = []
    for (source, _x, _y), members in groups.items():
        if len(members) == 1:
            result.append(members[0])
            continue
        coords = [item["geometry"]["coordinates"] for item in members]
        props = dict(members[0].get("properties") or {})
        props.update({
            "station_name": f"{len(members):,} {source} stations",
            "station_kind": "Map cluster — zoom in for individual stations",
            "station_count": len(members), "is_cluster": True, "location_id": None,
            "measurements": [], "value": None, "unit": None, "category": None, "parameter": None,
            "observed_at": max((str((item.get("properties") or {}).get("observed_at") or "") for item in members), default=None),
        })
        result.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [sum(float(c[0]) for c in coords) / len(coords), sum(float(c[1]) for c in coords) / len(coords)]},
            "properties": props,
        })
    return {"type": "FeatureCollection", "features": result, "count": len(result), "total_count": base.get("count", 0), "merged": True}
