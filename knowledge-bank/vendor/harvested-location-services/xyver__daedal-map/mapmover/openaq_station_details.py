"""On-demand OpenAQ station details for the private WIP Ops overlay.

The two-hour collector deliberately stores a compact, six-pollutant location
index.  This module fetches fuller metadata only after an operator selects one
OpenAQ location, avoiding a global provider/licence enrichment pull.
"""
from __future__ import annotations

import json
import os
import threading
import time
from urllib.request import Request, urlopen


API_ROOT = "https://api.openaq.org/v3"
DETAIL_CACHE_SECONDS = 15 * 60
_CACHE_LOCK = threading.Lock()
_DETAIL_CACHE: dict[int, tuple[float, dict]] = {}


def _request_json(path: str) -> dict:
    api_key = str(os.environ.get("OPENAQ_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OpenAQ station details are not configured")
    request = Request(
        f"{API_ROOT}{path}",
        headers={"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "DaedalMap/1.0 (Ops station details)"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _first_result(payload: dict) -> dict:
    results = payload.get("results")
    return results[0] if isinstance(results, list) and results and isinstance(results[0], dict) else {}


def _licence_text(licenses) -> str | None:
    """Keep the shared point-popup contract scalar; never render [object Object]."""
    if not isinstance(licenses, list):
        return None
    names = [str(item.get("name") or item.get("id") or "").strip()
             for item in licenses if isinstance(item, dict)]
    names = [name for name in names if name]
    return "; ".join(dict.fromkeys(names)) or None


def get_station_detail(location_id: int) -> dict:
    """Return metadata plus all latest source-native readings for one location."""
    if location_id <= 0:
        raise ValueError("Invalid OpenAQ location id")
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _DETAIL_CACHE.get(location_id)
        if cached and now - cached[0] < DETAIL_CACHE_SECONDS:
            return cached[1]

    location = _first_result(_request_json(f"/locations/{location_id}"))
    if not location:
        raise LookupError("OpenAQ location was not found")
    latest = _request_json(f"/locations/{location_id}/latest").get("results") or []
    sensors = location.get("sensors") if isinstance(location.get("sensors"), list) else []
    sensor_info = {
        item.get("id"): item for item in sensors
        if isinstance(item, dict) and item.get("id") is not None
    }
    readings = []
    for item in latest:
        if not isinstance(item, dict):
            continue
        sensor = sensor_info.get(item.get("sensorsId"), {})
        parameter = sensor.get("parameter") if isinstance(sensor.get("parameter"), dict) else {}
        observed = item.get("datetime") if isinstance(item.get("datetime"), dict) else {}
        readings.append({
            "sensor_id": item.get("sensorsId"),
            "parameter_id": parameter.get("id"),
            "parameter": parameter.get("name") or parameter.get("displayName") or "unknown",
            "value": item.get("value"),
            "unit": parameter.get("units") or parameter.get("unit") or None,
            "observed_at": observed.get("utc") or observed.get("local"),
        })
    readings.sort(key=lambda item: (str(item.get("parameter") or ""), str(item.get("observed_at") or "")))
    coordinates = location.get("coordinates") if isinstance(location.get("coordinates"), dict) else {}
    detail = {
        "location_id": location.get("id") or location_id,
        "station_name": location.get("name") or f"OpenAQ location {location_id}",
        "locality": location.get("locality"),
        "country": location.get("country"),
        "provider": location.get("provider"),
        "owner": location.get("owner"),
        "license": _licence_text(location.get("licenses")),
        "is_mobile": location.get("isMobile"),
        "is_monitor": location.get("isMonitor"),
        "lat": coordinates.get("latitude"),
        "lon": coordinates.get("longitude"),
        "measurements": readings,
        "source_url": f"https://explore.openaq.org/locations/{location_id}",
    }
    with _CACHE_LOCK:
        _DETAIL_CACHE[location_id] = (now, detail)
    return detail
