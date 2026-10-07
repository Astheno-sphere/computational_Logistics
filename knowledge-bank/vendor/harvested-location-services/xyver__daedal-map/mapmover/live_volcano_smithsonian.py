from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import os
from typing import Any
from urllib.parse import urlencode

import requests

from mapmover.runtime.result_cap import apply_row_count_cap_to_payload


GVP_WFS = "https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows"
GVP_ERUPTIONS_TYPENAME = "GVP-VOTW:Smithsonian_VOTW_Holocene_Eruptions"
DEFAULT_DAYS = 365
MAX_DAYS = 730
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
DEFAULT_TIMEOUT_SECONDS = 120


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _max_days() -> int:
    return _env_int("LIVE_VOLCANO_MAX_DAYS", MAX_DAYS)


def _max_limit() -> int:
    return _env_int("LIVE_VOLCANO_MAX_LIMIT", MAX_LIMIT)


def _timeout_seconds() -> int:
    return _env_int("LIVE_VOLCANO_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)


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
            try:
                dt = datetime.strptime(raw, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"{field_name} must be ISO-8601 datetime text") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_output_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    utc_value = value.astimezone(timezone.utc)
    return (
        f"{utc_value.year:04d}-{utc_value.month:02d}-{utc_value.day:02d} "
        f"{utc_value.hour:02d}:{utc_value.minute:02d}:{utc_value.second:02d}"
    )


def _coerce_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def _calculate_radius(vei: Any) -> tuple[float, float]:
    vei_float = _coerce_float(vei)
    if vei_float is None:
        return 5.0, 1.0
    if vei_float <= 0:
        return 5.0, 1.0
    if vei_float == 1:
        return 10.0, 2.0
    if vei_float == 2:
        return 25.0, 5.0
    if vei_float == 3:
        return 50.0, 10.0
    if vei_float == 4:
        return 100.0, 25.0
    if vei_float == 5:
        return 200.0, 50.0
    if vei_float == 6:
        return 500.0, 100.0
    if vei_float == 7:
        return 1000.0, 300.0
    return 2000.0, 500.0


def _build_date(year: Any, month: Any, day: Any, *, default_month: int, default_day: int) -> datetime | None:
    parsed_year = _coerce_int(year)
    if parsed_year is None:
        return None
    if parsed_year < 1:
        return None
    parsed_month = _coerce_int(month) or default_month
    parsed_day = _coerce_int(day) or default_day
    if parsed_month == 0:
        parsed_month = default_month
    if parsed_day == 0:
        parsed_day = default_day
    try:
        return datetime(parsed_year, parsed_month, parsed_day, tzinfo=timezone.utc)
    except ValueError:
        return datetime(parsed_year, default_month, default_day, tzinfo=timezone.utc)


def _event_id(eruption_id: Any) -> str:
    parsed = _coerce_int(eruption_id)
    if parsed is not None:
        return f"VE{parsed:06d}"
    return f"VE{str(eruption_id or '').strip()}"


def _fetch_gvp_eruptions() -> tuple[list[dict[str, Any]], str]:
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": GVP_ERUPTIONS_TYPENAME,
        "outputFormat": "application/json",
    }
    response = requests.get(GVP_WFS, params=params, timeout=_timeout_seconds())
    response.raise_for_status()
    body = response.json()
    features = body.get("features") if isinstance(body, dict) else []
    if not isinstance(features, list):
        features = []
    fallback_url = f"{GVP_WFS}?{urlencode(params)}"
    return features, response.url or fallback_url


def _normalize_event(feature: dict[str, Any]) -> dict[str, Any] | None:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
    coords = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []

    eruption_id = props.get("Eruption_Number")
    start_dt = _build_date(
        props.get("StartDateYear"),
        props.get("StartDateMonth"),
        props.get("StartDateDay"),
        default_month=1,
        default_day=1,
    )
    if not eruption_id or start_dt is None:
        return None

    end_dt = _build_date(
        props.get("EndDateYear"),
        props.get("EndDateMonth"),
        props.get("EndDateDay"),
        default_month=12,
        default_day=28,
    )
    duration_days = (end_dt - start_dt).days if end_dt else None
    is_ongoing = props.get("EndDateDayModifier") == "continuing"
    vei = props.get("ExplosivityIndexMax")
    felt_radius, damage_radius = _calculate_radius(vei)

    return {
        "loc_id": "",
        "source": "smithsonian_gvp",
        "event_id": _event_id(eruption_id),
        "eruption_id": _coerce_int(eruption_id),
        "event_type": "volcano",
        "year": start_dt.year,
        "timestamp": _format_output_time(start_dt),
        "end_year": end_dt.year if end_dt else None,
        "end_timestamp": _format_output_time(end_dt),
        "duration_days": duration_days,
        "is_ongoing": is_ongoing,
        "latitude": float(coords[1]) if len(coords) > 1 and coords[1] is not None else None,
        "longitude": float(coords[0]) if len(coords) > 0 and coords[0] is not None else None,
        "containing_loc_id": "",
        "sibling_level": "",
        "iso3": "",
        "felt_radius_km": felt_radius,
        "damage_radius_km": damage_radius,
        "volcano_number": _coerce_int(props.get("Volcano_Number")),
        "volcano_name": str(props.get("Volcano_Name") or ""),
        "activity_type": str(props.get("Activity_Type") or ""),
        "activity_area": str(props.get("ActivityArea") or ""),
        "VEI": _coerce_float(vei),
        "country": "",
        "region": "",
        "triggered_by": "",
        "triggered": "",
        "link_type": "",
        "earthquake_event_ids": "",
        "tsunami_event_ids": "",
        "data_quality": "preliminary",
    }


def fetch_live_volcanoes(
    *,
    request_id: str | None = None,
    days: int | None = None,
    start_time: Any = None,
    end_time: Any = None,
    min_vei: float | None = None,
    ongoing_only: bool = False,
    limit: int | None = None,
    orderby: str | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now()
    normalized_days = int(days or DEFAULT_DAYS)
    max_days = _max_days()
    if normalized_days < 1 or normalized_days > max_days:
        raise ValueError(f"days must be between 1 and {max_days}")

    end_dt = _parse_datetime(end_time, "end_time") if end_time else generated_at
    start_dt = _parse_datetime(start_time, "start_time") if start_time else end_dt - timedelta(days=normalized_days)
    if start_dt >= end_dt:
        raise ValueError("start_time must be before end_time")
    if (end_dt - start_dt).days > max_days:
        raise ValueError(f"time range must be {max_days} days or less")

    normalized_limit = int(limit or DEFAULT_LIMIT)
    max_limit = _max_limit()
    if normalized_limit < 1 or normalized_limit > max_limit:
        raise ValueError(f"limit must be between 1 and {max_limit}")

    normalized_orderby = str(orderby or "time").strip().lower()
    if normalized_orderby not in {"time", "time-asc", "vei", "vei-asc"}:
        raise ValueError("orderby must be one of time, time-asc, vei, vei-asc")

    features, upstream_url = _fetch_gvp_eruptions()
    rows = [row for feature in features if isinstance(feature, dict) for row in [_normalize_event(feature)] if row]
    rows = [
        row
        for row in rows
        if row.get("timestamp")
        and start_dt <= _parse_datetime(row["timestamp"], "timestamp") <= end_dt
    ]
    if min_vei is not None:
        rows = [row for row in rows if row.get("VEI") is not None and float(row["VEI"]) >= float(min_vei)]
    if _coerce_bool(ongoing_only):
        rows = [row for row in rows if row.get("is_ongoing") is True]

    reverse = not normalized_orderby.endswith("-asc")
    if normalized_orderby.startswith("vei"):
        rows.sort(key=lambda row: (-1 if row.get("VEI") is None else float(row["VEI"])), reverse=reverse)
    else:
        rows.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=reverse)

    total_row_count = len(rows)
    truncated = total_row_count > normalized_limit
    rows = rows[:normalized_limit]
    live_watermark = max((str(row["timestamp"]) for row in rows if row.get("timestamp")), default=None)

    return apply_row_count_cap_to_payload({
        "request_id": request_id,
        "capability_id": "live_volcano_events",
        "pack_id": "volcanoes",
        "source_id": "volcanoes_events_live",
        "data_mode": "live",
        "data_quality": "preliminary",
        "query_mode": "upstream_live_wrapper",
        "filters_applied": {
            "time": {
                "start_time": _format_output_time(start_dt),
                "end_time": _format_output_time(end_dt),
                "days": normalized_days if not start_time else None,
            },
            "min_vei": min_vei,
            "ongoing_only": bool(ongoing_only),
        },
        "sort": [{"field": "VEI" if normalized_orderby.startswith("vei") else "timestamp", "direction": "asc" if normalized_orderby.endswith("-asc") else "desc"}],
        "limit": normalized_limit,
        "row_count": total_row_count,
        "truncated": truncated,
        "rows": rows,
        "provenance": {
            "upstream": "Smithsonian Institution Global Volcanism Program WFS",
            "upstream_url": upstream_url,
            "source_ids": ["volcanoes_events_live"],
        },
        "freshness": {
            "live_watermark_utc": live_watermark,
            "generated_at_utc": generated_at.isoformat(),
            "processing_state": "not_enriched",
        },
        "warnings": [
            {
                "code": "preliminary_live_data",
                "message": "Live rows are direct Smithsonian/GVP WFS responses normalized to DaedalMap event fields; loc_id, event areas, links, and aggregates are not applied.",
            },
            {
                "code": "low_frequency_source",
                "message": "Smithsonian/GVP eruption updates are low-frequency official updates, not minute-by-minute operational alerts.",
            },
        ],
    }, cap_reason="live_wrapper_limit")
