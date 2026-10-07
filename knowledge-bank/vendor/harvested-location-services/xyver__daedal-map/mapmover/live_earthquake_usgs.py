from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

import requests

from mapmover.runtime.result_cap import apply_row_count_cap_to_payload


USGS_EVENTS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
DEFAULT_HOURS = 24
MAX_HOURS = 24 * 7
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
DEFAULT_MIN_MAGNITUDE = 2.5
DEFAULT_TIMEOUT_SECONDS = 20


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _max_hours() -> int:
    return _env_int("LIVE_EARTHQUAKE_MAX_HOURS", MAX_HOURS)


def _max_limit() -> int:
    return _env_int("LIVE_EARTHQUAKE_MAX_LIMIT", MAX_LIMIT)


def _timeout_seconds() -> int:
    return _env_int("LIVE_EARTHQUAKE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError(f"{field_name} is blank")
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be ISO-8601 datetime text") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_usgs_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _format_output_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _coerce_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _coerce_optional_float(value: Any, field_name: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return _coerce_float(value, field_name)


def _calculate_felt_radius(magnitude: float) -> float:
    if magnitude < 3:
        return 10.0
    if magnitude < 4:
        return 30.0
    if magnitude < 5:
        return 100.0
    if magnitude < 6:
        return 300.0
    if magnitude < 7:
        return 500.0
    return 1000.0


def _calculate_damage_radius(magnitude: float) -> float:
    if magnitude < 5:
        return 0.0
    if magnitude < 6:
        return 20.0
    if magnitude < 7:
        return 50.0
    if magnitude < 8:
        return 150.0
    return 300.0


def _normalize_event(feature: dict[str, Any]) -> dict[str, Any] | None:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
    coords = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []
    if len(coords) < 2:
        return None

    timestamp_ms = props.get("time")
    magnitude = props.get("mag")
    if timestamp_ms is None or magnitude is None:
        return None

    timestamp = datetime.fromtimestamp(float(timestamp_ms) / 1000, tz=timezone.utc)
    mag_float = float(magnitude)
    usgs_id = str(feature.get("id") or "").strip()
    event_id = f"us{usgs_id}" if usgs_id and not usgs_id.startswith("us") else usgs_id

    return {
        "event_id": event_id,
        "timestamp": _format_output_time(timestamp),
        "year": timestamp.year,
        "latitude": float(coords[1]),
        "longitude": float(coords[0]),
        "magnitude": mag_float,
        "depth_km": float(coords[2]) if len(coords) > 2 and coords[2] is not None else 0.0,
        "felt_radius_km": _calculate_felt_radius(mag_float),
        "damage_radius_km": _calculate_damage_radius(mag_float),
        "place": str(props.get("place") or ""),
        "loc_id": "",
        "country": "",
        "deaths": None,
        "injuries": None,
        "damage_millions": None,
        "houses_destroyed": None,
        "intensity": props.get("mmi"),
        "mainshock_id": "",
        "sequence_id": "",
        "is_mainshock": None,
        "aftershock_count": None,
        "tsunami_event_id": "",
        "volcano_event_id": "",
        "source": "usgs",
        "data_quality": "preliminary",
        "event_url": str(props.get("url") or ""),
        "updated_at": _format_output_time(datetime.fromtimestamp(float(props["updated"]) / 1000, tz=timezone.utc))
        if props.get("updated") is not None
        else None,
    }


def fetch_live_earthquakes(
    *,
    request_id: str | None = None,
    hours: int | None = None,
    start_time: Any = None,
    end_time: Any = None,
    min_magnitude: float | None = None,
    limit: int | None = None,
    orderby: str | None = None,
    min_latitude: float | None = None,
    max_latitude: float | None = None,
    min_longitude: float | None = None,
    max_longitude: float | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now()
    normalized_hours = int(hours or DEFAULT_HOURS)
    max_hours = _max_hours()
    if normalized_hours < 1 or normalized_hours > max_hours:
        raise ValueError(f"hours must be between 1 and {max_hours}")

    end_dt = _parse_datetime(end_time, "end_time") if end_time else generated_at
    start_dt = _parse_datetime(start_time, "start_time") if start_time else end_dt - timedelta(hours=normalized_hours)
    if start_dt >= end_dt:
        raise ValueError("start_time must be before end_time")

    normalized_limit = int(limit or DEFAULT_LIMIT)
    max_limit = _max_limit()
    if normalized_limit < 1 or normalized_limit > max_limit:
        raise ValueError(f"limit must be between 1 and {max_limit}")
    probe_limit = min(normalized_limit + 1, max_limit)

    normalized_min_magnitude = DEFAULT_MIN_MAGNITUDE if min_magnitude is None else float(min_magnitude)
    normalized_orderby = str(orderby or "time").strip().lower()
    if normalized_orderby not in {"time", "time-asc", "magnitude", "magnitude-asc"}:
        raise ValueError("orderby must be one of time, time-asc, magnitude, magnitude-asc")

    params: dict[str, Any] = {
        "format": "geojson",
        "starttime": _format_usgs_time(start_dt),
        "endtime": _format_usgs_time(end_dt),
        "minmagnitude": normalized_min_magnitude,
        "orderby": normalized_orderby,
        "limit": probe_limit,
    }
    bounds = {
        "minlatitude": _coerce_optional_float(min_latitude, "min_latitude"),
        "maxlatitude": _coerce_optional_float(max_latitude, "max_latitude"),
        "minlongitude": _coerce_optional_float(min_longitude, "min_longitude"),
        "maxlongitude": _coerce_optional_float(max_longitude, "max_longitude"),
    }
    for key, value in bounds.items():
        if value is not None:
            params[key] = value

    response = requests.get(USGS_EVENTS_API, params=params, timeout=_timeout_seconds())
    response.raise_for_status()
    body = response.json()
    features = body.get("features") if isinstance(body, dict) else []
    if not isinstance(features, list):
        features = []

    rows = [row for feature in features if isinstance(feature, dict) for row in [_normalize_event(feature)] if row]
    upstream_returned_count = len(rows)
    confirmed_truncated = upstream_returned_count > normalized_limit
    if confirmed_truncated:
        rows = rows[:normalized_limit]
    live_watermark = max((str(row["timestamp"]) for row in rows if row.get("timestamp")), default=None)
    payload = {
        "request_id": request_id,
        "capability_id": "live_earthquake_events",
        "pack_id": "earthquakes",
        "source_id": "earthquakes_events_live",
        "data_mode": "live",
        "data_quality": "preliminary",
        "query_mode": "upstream_live_wrapper",
        "filters_applied": {
            "time": {
                "start_time": _format_usgs_time(start_dt),
                "end_time": _format_usgs_time(end_dt),
                "hours": normalized_hours if not start_time else None,
            },
            "min_magnitude": normalized_min_magnitude,
            "bounds": {key: value for key, value in bounds.items() if value is not None},
        },
        "sort": [{"field": normalized_orderby.replace("-asc", ""), "direction": "asc" if normalized_orderby.endswith("-asc") else "desc"}],
        "limit": normalized_limit,
        "row_count": upstream_returned_count if confirmed_truncated else len(rows),
        "truncated": confirmed_truncated,
        "rows": rows,
        "provenance": {
            "upstream": "USGS FDSN Event Web Service",
            "upstream_url": response.url,
            "source_ids": ["earthquakes_events_live"],
        },
        "freshness": {
            "live_watermark_utc": live_watermark,
            "generated_at_utc": generated_at.isoformat(),
            "processing_state": "not_enriched",
        },
        "warnings": [
            {
                "code": "preliminary_live_data",
                "message": "Live rows are direct USGS responses normalized to DaedalMap event fields; loc_id, event areas, links, and aggregates are not applied.",
            }
        ],
    }
    if not confirmed_truncated and probe_limit == normalized_limit and len(rows) >= normalized_limit:
        payload["warnings"].append(
            {
                "code": "upstream_limit_ambiguous",
                "message": "Upstream limit reached at the configured maximum, so additional matching rows may exist even though truncation could not be confirmed exactly.",
            }
        )
    if confirmed_truncated:
        return apply_row_count_cap_to_payload(payload, cap_reason="live_wrapper_limit")
    return payload
