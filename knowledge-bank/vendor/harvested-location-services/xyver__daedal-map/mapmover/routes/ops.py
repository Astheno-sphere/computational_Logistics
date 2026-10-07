"""Ops mode API router endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from mapmover import logger
from mapmover.logging_analytics import hash_ip_for_analytics, log_app_error, log_conversation
from mapmover.ops_route_runtime import (
    prepare_ops_chat_route_context,
    prepare_ops_view_route_context,
    build_ops_orientation_payload,
    setup_required_ops_message,
    snapshot_ops_report,
)
from mapmover.ops_orchestrator_runtime import (
    WILDFIRE_LIVE_FEED,
    _wildfire_perimeter_geometry,
    build_ops_timeline_payload,
    load_current_state_history,
    load_current_state_snapshot,
    load_current_state_timeline_frame,
    load_current_state_timeline_index,
    load_nws_recent_timeline_bundle,
    ops_timeline_preload_history_contract,
)
from mapmover.ops_ticker import (
    build_cached_aurora_payload,
    build_cached_aurora_frames_payload,
    build_cached_nws_alerts_payload,
    build_nws_alerts_payload_for_snapshot,
    _nws_alert_loc_ids,
    build_cached_ticker_payload,
)
from mapmover.ops_point_feeds import (
    POINT_FEEDS,
    build_cached_point_overlay,
    build_point_overlay_for_snapshot,
    is_point_feed,
)
from mapmover.openaq_station_details import get_station_detail
from mapmover.auth_context import get_authenticated_user
from mapmover.catalog_surface import request_uses_wip_catalog
from mapmover.orchestrator_registry import get_orchestrator
from mapmover.routes.chat_shared import build_chat_error_payload, build_provider_error_payload, decode_json_or_msgpack_body, decode_request_body
from mapmover.routes.disasters.helpers import msgpack_error, msgpack_response
from mapmover.runtime.chat_route_support import (
    anonymous_turn_limit_rejection_payload,
    build_chat_gate_log_metadata,
    build_usage_recorder,
    register_anonymous_chat_turn,
)
from mapmover.runtime.sse import SSE_HEADERS, encode_sse, stage_payload


router = APIRouter()
ops_orchestrator = get_orchestrator("ops")


def _ops_report_payload(route_context) -> dict:
    report = snapshot_ops_report(
        cache=route_context.cache,
        watch=route_context.watch,
        effective_feeds=route_context.effective_feeds,
    )
    return {
        "type": "ops_report",
        "watch_id": route_context.watch.get("watch_id"),
        "watch": route_context.watch,
        "effective_feeds": route_context.effective_feeds,
        "ops_report": report,
    }


def _requested_timeline_feeds(requested_timeline_feeds, route_context) -> list[str]:
    feed_aliases = {
        "nws_alerts": "usa_nws_alerts",
        "hurricanes": "hurricanes_live",
        "aurora": "noaa_aurora",
        "cams-air-quality-grid": "cams_air_quality",
        "ocean-sst-grid": "ocean_sst",
        "buoys": "noaa_ndbc",
    }
    requested = [
        feed_aliases.get(str(feed or "").strip(), str(feed or "").strip())
        for feed in (requested_timeline_feeds if isinstance(requested_timeline_feeds, list) else [])
    ]
    timeline_feed_scope = set(route_context.effective_feeds or route_context.allowed_feeds or [])
    return list(dict.fromkeys(
        feed for feed in requested
        if feed and feed in timeline_feed_scope
    ))


def _replace_timeline_provider_frames(timeline: dict, feed: str, frames: list[dict]) -> None:
    """Install lazy-provider frames without dropping their cache contract."""
    if not frames:
        return
    timeline.setdefault("feeds", {})[feed] = frames
    contract = ops_timeline_preload_history_contract(feed)
    if contract is not None:
        timeline.setdefault("preload_history", {})[feed] = contract


def _snapshot_time(snapshot: dict) -> datetime | None:
    for key in ("published_at", "fetched_at", "last_checked_at"):
        value = str(snapshot.get(key) or "").replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            continue
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    return None


def _snapshot_timeline_history_hours(snapshot: dict | None) -> int:
    try:
        history_hours = int((snapshot or {}).get("ops_history_display_hours") or 72)
        timeline_hours = int((snapshot or {}).get("ops_timeline_display_hours") or history_hours)
        return max(1, min(timeline_hours, history_hours))
    except (TypeError, ValueError):
        return 72


def _local_nws_timeline_entries() -> list[dict]:
    """Return independently renderable retained NWS alert snapshots.

    Old retained delta entries remain reconstructible while they age out. New
    collector snapshots already contain each moment's complete alert state.
    """
    index = load_current_state_timeline_index("usa_nws_alerts")
    indexed_frames = index.get("frames") if isinstance(index, dict) else None
    if isinstance(indexed_frames, list) and indexed_frames:
        # The compact index is the normal deployed path.  Do not read the
        # 60-day archive just to build metadata for the shared 72-hour cursor.
        entries = []
        for frame in indexed_frames:
            if not isinstance(frame, dict):
                continue
            start_at = str(frame.get("start_at") or "").strip()
            frame_key = str(frame.get("frame_key") or "").strip()
            payload_hash = str(frame.get("payload_hash") or "").strip()
            if start_at and frame_key and payload_hash:
                entries.append({
                    "published_at": start_at,
                    "payload_hash": payload_hash,
                    "timeline_frame_key": frame_key,
                })
        entries.sort(key=lambda entry: _snapshot_time(entry) or datetime.min.replace(tzinfo=timezone.utc))
        return entries

    current = load_current_state_snapshot("usa_nws_alerts")
    raw_entries = [entry for entry in load_current_state_history("usa_nws_alerts") if isinstance(entry, dict)]
    raw_entries.sort(key=lambda entry: _snapshot_time(entry) or datetime.min.replace(tzinfo=timezone.utc))

    active_alerts: dict[str, dict] = {}
    entries: list[dict] = []
    for entry in raw_entries:
        summary = entry.get("payload_summary") if isinstance(entry.get("payload_summary"), dict) else None
        if summary is not None:
            active_alerts = {
                str(alert.get("alert_id") or "").strip(): dict(alert)
                for alert in (summary.get("alerts") or [])
                if isinstance(alert, dict) and str(alert.get("alert_id") or "").strip()
            }
            entries.append(entry)
            continue

        delta = entry.get("delta") if isinstance(entry.get("delta"), dict) else None
        if delta is None:
            continue
        for removed in delta.get("removed") or []:
            if isinstance(removed, dict):
                active_alerts.pop(str(removed.get("alert_id") or "").strip(), None)
        for change_key in ("added", "updated"):
            for changed in delta.get(change_key) or []:
                if not isinstance(changed, dict):
                    continue
                alert_id = str(changed.get("alert_id") or "").strip()
                if not alert_id:
                    continue
                # Updated deltas omit unchanged geometry to stay compact. Merge
                # into the prior alert so its source geometry remains usable.
                active_alerts[alert_id] = {**active_alerts.get(alert_id, {}), **changed}
        compact_summary = entry.get("summary") if isinstance(entry.get("summary"), dict) else {}
        entries.append({
            **entry,
            "payload_summary": {**compact_summary, "alerts": list(active_alerts.values())},
        })

    if isinstance(current, dict):
        entries.append(current)
    deduped = {}
    for entry in entries:
        at = _snapshot_time(entry)
        if at is not None:
            deduped[(at.isoformat(), str(entry.get("payload_hash") or ""))] = entry
    ordered = sorted(deduped.values(), key=lambda entry: _snapshot_time(entry) or datetime.min.replace(tzinfo=timezone.utc))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_snapshot_timeline_history_hours(current))
    return [
        entry for entry in ordered
        if (_snapshot_time(entry) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    ]


def _materialize_nws_timeline_entry(entry: dict | None) -> dict | None:
    if not isinstance(entry, dict):
        return None
    frame_key = entry.get("timeline_frame_key")
    if frame_key:
        frame = load_current_state_timeline_frame("usa_nws_alerts", frame_key)
        return frame if isinstance(frame, dict) else None
    return entry


def _local_nws_timeline_frames() -> list[dict]:
    """Return NWS cursor metadata without bulk-transferring warning geometry.

    A long NWS history can contain thousands of county and
    native warning polygons.  The browser receives this compact index once and
    requests only the frame it lands on; the runtime's short cloud-history cache
    supplies the matching retained snapshot.
    """
    ordered = _local_nws_timeline_entries()
    frames = []
    for index, entry in enumerate(ordered):
        start = _snapshot_time(entry)
        if start is None:
            continue
        next_start = _snapshot_time(ordered[index + 1]) if index + 1 < len(ordered) else None
        frames.append({
            "start_at": start.isoformat(),
            "end_at": next_start.isoformat() if next_start is not None else None,
            "payload_hash": entry.get("payload_hash"),
            "timeline_provider": "nws_alerts",
        })
    return frames


def _local_nws_timeline_frame_at(raw_at: object) -> dict | None:
    """Build one display frame selected from the already-retained NWS history."""
    try:
        target = datetime.fromisoformat(str(raw_at or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    target = target.replace(tzinfo=timezone.utc) if target.tzinfo is None else target.astimezone(timezone.utc)
    selected = None
    for entry in _local_nws_timeline_entries():
        at = _snapshot_time(entry)
        if at is not None and at <= target:
            selected = entry
        elif at is not None:
            break
    if selected is None:
        return None
    materialized = _materialize_nws_timeline_entry(selected)
    if not isinstance(materialized, dict):
        return None
    return {
        "payload_hash": selected.get("payload_hash"),
        "start_at": (_snapshot_time(selected) or target).isoformat(),
        "geojson": build_nws_alerts_payload_for_snapshot(materialized),
    }


def _local_nws_timeline_frame_by_hash(raw_hash: object) -> dict | None:
    """Build one NWS display frame without re-reading its timeline index."""
    payload_hash = str(raw_hash or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", payload_hash):
        return None
    stored = load_current_state_timeline_frame(
        "usa_nws_alerts", f"timeline_frames/{payload_hash}.json"
    )
    if not isinstance(stored, dict):
        return None
    observed_at = _snapshot_time(stored)
    return {
        "payload_hash": payload_hash,
        "start_at": observed_at.isoformat() if observed_at is not None else None,
        "geojson": build_nws_alerts_payload_for_snapshot(stored),
    }


def _local_nws_timeline_frames_at(raw_values: object) -> list[dict]:
    """Build a bounded batch of retained compact NWS map frames.

    Background browser hydration uses this instead of hundreds of individual
    requests. Full bulletin prose remains out-of-band on the clicked-alert
    endpoint, and county geometry remains separately cacheable.
    """
    if not isinstance(raw_values, list):
        return []
    requested = {
        str(value or "").replace("Z", "+00:00")
        for value in raw_values
        if str(value or "").strip()
    }
    if not requested:
        return []
    frames = []
    for entry in _local_nws_timeline_entries():
        at = _snapshot_time(entry)
        if at is None or at.isoformat() not in requested:
            continue
        materialized = _materialize_nws_timeline_entry(entry)
        if not isinstance(materialized, dict):
            continue
        frames.append({
            "payload_hash": entry.get("payload_hash"),
            "start_at": at.isoformat(),
            "geojson": build_nws_alerts_payload_for_snapshot(materialized),
        })
    return frames


def _local_nws_alert_detail_at(raw_at: object, alert_id: object) -> dict | None:
    """Return full retained bulletin text only for a clicked Ops alert."""
    try:
        target = datetime.fromisoformat(str(raw_at or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    target = target.replace(tzinfo=timezone.utc) if target.tzinfo is None else target.astimezone(timezone.utc)
    selected = None
    for entry in _local_nws_timeline_entries():
        at = _snapshot_time(entry)
        if at is not None and at <= target:
            selected = entry
        elif at is not None:
            break
    if not isinstance(selected, dict):
        return None
    wanted = str(alert_id or "").strip()
    materialized = _materialize_nws_timeline_entry(selected)
    summary = materialized.get("payload_summary") if isinstance((materialized or {}).get("payload_summary"), dict) else {}
    for alert in summary.get("alerts") or []:
        if isinstance(alert, dict) and str(alert.get("alert_id") or "").strip() == wanted:
            return {
                "alert_id": wanted,
                "headline": alert.get("headline"),
                "area": alert.get("area"),
                "description": alert.get("description"),
                "instruction": alert.get("instruction"),
                "source_product_url": alert.get("source_product_url"),
            }
    return None


def _point_overlay_id_for_collector(collector: str) -> str | None:
    normalized = str(collector or "").strip()
    for overlay_id, spec in POINT_FEEDS.items():
        if spec.collector == normalized:
            return overlay_id
    return None


def _local_point_timeline_entries(overlay_id: str) -> list[dict]:
    """Return complete retained states for one reusable live-point overlay."""
    spec = POINT_FEEDS.get(str(overlay_id or "").strip())
    if spec is None:
        return []
    current = load_current_state_snapshot(spec.collector)
    entries = [entry for entry in load_current_state_history(spec.collector) if isinstance(entry, dict)]
    if isinstance(current, dict):
        entries.append(current)
    deduped: dict[tuple[str, str], dict] = {}
    for entry in entries:
        at = _snapshot_time(entry)
        if at is not None:
            deduped[(at.isoformat(), str(entry.get("payload_hash") or ""))] = entry
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_snapshot_timeline_history_hours(current))
    return [
        entry for entry in sorted(
            deduped.values(), key=lambda item: _snapshot_time(item) or datetime.min.replace(tzinfo=timezone.utc)
        )
        if (_snapshot_time(entry) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
    ]


def _local_point_timeline_frames(overlay_id: str) -> list[dict]:
    entries = _local_point_timeline_entries(overlay_id)
    frames = []
    for index, entry in enumerate(entries):
        start = _snapshot_time(entry)
        if start is None:
            continue
        next_start = _snapshot_time(entries[index + 1]) if index + 1 < len(entries) else None
        frames.append({
            "start_at": start.isoformat(),
            "end_at": next_start.isoformat() if next_start is not None else None,
            "payload_hash": entry.get("payload_hash"),
            "timeline_provider": "live_point",
            "overlay_id": overlay_id,
        })
    return frames


def _local_point_timeline_frame_at(overlay_id: str, raw_at: object) -> dict | None:
    try:
        target = datetime.fromisoformat(str(raw_at or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    target = target.replace(tzinfo=timezone.utc) if target.tzinfo is None else target.astimezone(timezone.utc)
    selected = None
    for entry in _local_point_timeline_entries(overlay_id):
        at = _snapshot_time(entry)
        if at is not None and at <= target:
            selected = entry
        elif at is not None:
            break
    if selected is None:
        return None
    return {
        "payload_hash": selected.get("payload_hash"),
        "start_at": (_snapshot_time(selected) or target).isoformat(),
        "geojson": build_point_overlay_for_snapshot(overlay_id, selected),
    }


def _local_point_timeline_frames_at(overlay_id: str, raw_values: object) -> list[dict]:
    """Return a bounded generic batch of retained point-reading frames."""
    if not isinstance(raw_values, list):
        return []
    frames = []
    for value in raw_values:
        frame = _local_point_timeline_frame_at(overlay_id, value)
        if frame is not None:
            frames.append(frame)
    return frames


@router.get("/api/ops/ticker")
async def ops_ticker_endpoint(req: Request):
    """Live announcement ticker items (space weather, etc.). Public, read-only.

    Open in all modes - the ticker is a standalone announcement bar, not tied to
    a watch or the chat ops_report.
    """
    try:
        return msgpack_response(build_cached_ticker_payload())
    except Exception as exc:
        logger.exception("Ops ticker error")
        return msgpack_error(str(exc), 500)


@router.get("/api/ops/aurora")
async def ops_aurora_endpoint(req: Request):
    """Latest OVATION aurora model band for the map overlay. Public, read-only.

    Returns the renderable cells [[lon, lat, probability], ...] plus the forecast
    timestamps, straight from the noaa_aurora live snapshot.
    """
    try:
        return msgpack_response(build_cached_aurora_payload())
    except Exception as exc:
        logger.exception("Ops aurora error")
        return msgpack_error(str(exc), 500)


@router.get("/api/ops/aurora/frames")
async def ops_aurora_frames_endpoint(req: Request):
    """Rolling, compact Aurora model frames for the real-history loop."""
    try:
        return msgpack_response(build_cached_aurora_frames_payload())
    except Exception as exc:
        logger.exception("Ops aurora frame history error")
        return msgpack_error(str(exc), 500)


@router.get("/api/ops/nws-alerts")
async def ops_nws_alerts_endpoint(req: Request):
    """NWS active alerts as a GeoJSON overlay. Public, read-only.

    Each alert renders as its exact warning polygon when the feed provided one,
    else the highlighted affected county polygons, else a pin at the centroid.
    """
    try:
        return msgpack_response(build_cached_nws_alerts_payload())
    except Exception as exc:
        logger.exception("Ops NWS alerts error")
        return msgpack_error(str(exc), 500)


@router.get("/api/ops/wildfires/perimeters")
async def ops_wildfire_perimeters_endpoint(
    req: Request,
    bbox: str | None = None,
    min_area_km2: float = 50.0,
):
    """Return simplified current fire perimeters only for a close viewport.

    The normal wildfire snapshot remains compact marker state. Perimeters are
    stable detail geometry, requested only after an operator has zoomed in and
    only for incidents whose supplied point lies inside the current viewport.
    """
    try:
        bounds = _optional_bbox(bbox)
        if bounds is None:
            return msgpack_error("A valid west,south,east,north bbox is required", 400)
        west, south, east, north = bounds
        threshold = max(0.0, float(min_area_km2))
        snapshot = load_current_state_snapshot(WILDFIRE_LIVE_FEED)
        summary = snapshot.get("payload_summary") if isinstance(snapshot, dict) else {}
        features = []
        for event in summary.get("events") or []:
            if not isinstance(event, dict):
                continue
            try:
                area = float(event.get("area_km2"))
                longitude = float(event.get("longitude"))
                latitude = float(event.get("latitude"))
            except (TypeError, ValueError):
                continue
            if area < threshold or not (west <= longitude <= east and south <= latitude <= north):
                continue
            geometry = _wildfire_perimeter_geometry(event, max_positions=300)
            if geometry is None:
                continue
            properties = {key: value for key, value in event.items() if key != "perimeter"}
            features.append({"type": "Feature", "geometry": geometry, "properties": properties})
            if len(features) >= 120:
                break
        return msgpack_response({
            "type": "FeatureCollection",
            "features": features,
            "snapshot_hash": snapshot.get("payload_hash") if isinstance(snapshot, dict) else None,
            "min_area_km2": threshold,
        })
    except Exception as exc:
        logger.exception("Ops wildfire perimeter error")
        return msgpack_error(str(exc), 500)


def _optional_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    try:
        west, south, east, north = (float(value) for value in raw.split(","))
    except (TypeError, ValueError):
        return None
    if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= 90 and -90 <= north <= 90 and south <= north):
        return None
    return west, south, east, north


@router.get("/api/ops/points/{overlay_id}")
async def ops_points_endpoint(overlay_id: str, req: Request, bbox: str | None = None, zoom: float | None = None):
    """Generic live point-feed overlay (GeoJSON points). Public, read-only.

    One endpoint for every registered "location with updating data" feed (ocean
    buoys, weather stations, sensors): each point carries its latest reading for
    the click popup. See mapmover/ops_point_feeds.py POINT_FEEDS.
    """
    if not is_point_feed(overlay_id) and overlay_id != "air_quality_stations":
        return msgpack_error(f"Unknown point feed: {overlay_id}", 404)
    spec = POINT_FEEDS.get(str(overlay_id or "").strip())
    if (overlay_id == "air_quality_stations" or (spec and spec.wip_only)) and not request_uses_wip_catalog(req, get_authenticated_user(req)):
        # Do not advertise an unreviewed Ops feed through a public endpoint.
        return msgpack_error(f"Unknown point feed: {overlay_id}", 404)
    try:
        return msgpack_response(build_cached_point_overlay(overlay_id, bbox=_optional_bbox(bbox), zoom=zoom))
    except Exception as exc:
        logger.exception("Ops point feed error: %s", overlay_id)
        return msgpack_error(str(exc), 500)


@router.get("/api/ops/openaq/stations/{location_id}")
async def openaq_station_detail_endpoint(location_id: int, req: Request):
    """Fetch one OpenAQ station's complete current metadata/readings on demand."""
    if not request_uses_wip_catalog(req, get_authenticated_user(req)):
        return msgpack_error("Unknown OpenAQ station", 404)
    try:
        return msgpack_response(get_station_detail(location_id))
    except LookupError as exc:
        return msgpack_error(str(exc), 404)
    except ValueError as exc:
        return msgpack_error(str(exc), 400)
    except Exception as exc:
        logger.exception("OpenAQ station detail error: %s", location_id)
        return msgpack_error(str(exc), 502)


@router.post("/api/ops/report")
async def ops_report_endpoint(req: Request):
    try:
        body = await decode_request_body(req)
        route_context, route_error, rejection_payload, rejection_status, rejection_headers = await prepare_ops_view_route_context(req, body)
        if route_error:
            return route_error
        if rejection_payload is not None:
            log_conversation(
                route_context.frontend_session_id if route_context else body.get("sessionId", "anonymous"),
                query,
                rejection_payload.get("message", ""),
                surface="ops",
                intent=rejection_payload.get("error_code") or "anonymous_budget_blocked",
                metadata=build_chat_gate_log_metadata(
                    rejection_payload,
                    gate_kind="anonymous_daily_budget",
                ),
            )
            return msgpack_response(
                rejection_payload,
                status_code=rejection_status or 400,
                headers=rejection_headers or {},
            )
        assert route_context is not None
        payload = _ops_report_payload(route_context)
        if not route_context.allowed_feeds:
            payload["warning"] = setup_required_ops_message(route_context.auth_user)
        return msgpack_response(payload)
    except Exception as exc:
        logger.exception("Ops report snapshot error")
        return msgpack_error(str(exc), 500)


@router.post("/api/ops/load-watch")
async def ops_load_watch_endpoint(req: Request):
    try:
        body = await decode_request_body(req)
        route_context, route_error, rejection_payload, rejection_status, rejection_headers = await prepare_ops_view_route_context(req, body)
        if route_error:
            return route_error
        if rejection_payload is not None:
            return msgpack_response(
                rejection_payload,
                status_code=rejection_status or 400,
                headers=rejection_headers or {},
            )
        assert route_context is not None
        payload = _ops_report_payload(route_context)
        payload["type"] = "ops_watch_loaded"
        payload["message"] = (
            f'Loaded "{route_context.watch.get("label") or "Ops watch"}" with '
            f"{len(route_context.effective_feeds)} feed"
            f"{'' if len(route_context.effective_feeds) == 1 else 's'}."
        )
        if not route_context.allowed_feeds:
            payload["warning"] = setup_required_ops_message(route_context.auth_user)
        return msgpack_response(payload)
    except Exception as exc:
        logger.exception("Ops watch load error")
        return msgpack_error(str(exc), 500)


@router.post("/api/local/ops/timeline")
async def local_ops_timeline_endpoint(req: Request):
    """Return retained Ops snapshots for the shared Ops time cursor."""
    try:
        body = await decode_request_body(req)
        # Timeline selection is display-local.  Keep it outside watch_context
        # so opening the scrubber cannot rewrite the account watch's active
        # feed set (selected feeds and active overlays are different states).
        requested_timeline_feeds = body.pop("timeline_feeds", [])
        route_context, route_error, rejection_payload, rejection_status, rejection_headers = await prepare_ops_view_route_context(req, body)
        if route_error:
            return route_error
        if rejection_payload is not None:
            return msgpack_response(
                rejection_payload,
                status_code=rejection_status or 400,
                headers=rejection_headers or {},
            )
        assert route_context is not None
        timeline_feeds = _requested_timeline_feeds(requested_timeline_feeds, route_context)
        timeline = build_ops_timeline_payload(effective_feeds=timeline_feeds)
        if "usa_nws_alerts" in timeline_feeds:
            frames = _local_nws_timeline_frames()
            _replace_timeline_provider_frames(timeline, "usa_nws_alerts", frames)
        for feed in timeline_feeds:
            overlay_id = _point_overlay_id_for_collector(feed)
            if not overlay_id:
                continue
            frames = _local_point_timeline_frames(overlay_id)
            _replace_timeline_provider_frames(timeline, feed, frames)
        return msgpack_response({
            "type": "local_ops_timeline",
            "watch_id": route_context.watch.get("watch_id"),
            "effective_feeds": route_context.effective_feeds,
            "timeline": timeline,
        })
    except Exception as exc:
        logger.exception("Local Ops timeline error")
        return msgpack_error(str(exc), 500)


@router.post("/api/local/ops/timeline/nws-frame")
async def local_ops_timeline_nws_frame_endpoint(req: Request):
    """Return one retained NWS display frame for the shared Ops cursor."""
    try:
        body = await decode_request_body(req)
        # The timeline metadata already gives the browser an immutable frame
        # hash. Prefer it so an interactive scrub does one hot-store lookup,
        # rather than fetching and scanning the full timeline index again.
        frame = (
            _local_nws_timeline_frame_by_hash(body.get("payload_hash"))
            if body.get("payload_hash")
            else _local_nws_timeline_frame_at(body.get("at"))
        )
        if frame is None:
            return msgpack_error("No retained NWS frame at that time", 404)
        return msgpack_response({"type": "local_ops_nws_frame", "frame": frame})
    except Exception as exc:
        logger.exception("Local Ops NWS timeline frame error")
        return msgpack_error(str(exc), 500)


@router.post("/api/local/ops/timeline/nws-frames")
async def local_ops_timeline_nws_frames_endpoint(req: Request):
    """Return up to 24 compact retained NWS frames for background hydration."""
    try:
        body = await decode_request_body(req)
        values = body.get("at")
        if not isinstance(values, list) or len(values) > 24:
            return msgpack_error("at must be a list of at most 24 retained frame timestamps", 413)
        return msgpack_response({"type": "local_ops_nws_frames", "frames": _local_nws_timeline_frames_at(values)})
    except Exception as exc:
        logger.exception("Local Ops NWS timeline batch error")
        return msgpack_error(str(exc), 500)


@router.post("/api/local/ops/timeline/nws-bundle")
async def local_ops_timeline_nws_bundle_endpoint(req: Request):
    """Return the compact 72-hour NWS lifecycle projection in one request."""
    try:
        # Decode so the endpoint remains inside the normal authenticated/request
        # codec boundary even though the projection itself needs no parameters.
        await decode_request_body(req)
        bundle = load_nws_recent_timeline_bundle()
        if bundle is None:
            return msgpack_error("NWS playback bundle is not available yet", 404)
        # The compactor preserves source SAME codes; convert them once at the
        # API boundary to the reusable browser geometry-cache namespace.
        definitions = bundle.get("definitions") if isinstance(bundle.get("definitions"), dict) else {}
        for definition in definitions.values():
            if isinstance(definition, dict) and "loc_ids" not in definition:
                definition["loc_ids"] = _nws_alert_loc_ids(definition.get("same"))
        return msgpack_response({"type": "local_ops_nws_bundle", "bundle": bundle})
    except Exception as exc:
        logger.exception("Local Ops NWS timeline bundle error")
        return msgpack_error(str(exc), 500)


@router.post("/api/local/ops/timeline/nws-alert-detail")
async def local_ops_timeline_nws_alert_detail_endpoint(req: Request):
    """Load one selected retained NWS alert's full bulletin text."""
    try:
        body = await decode_request_body(req)
        detail = _local_nws_alert_detail_at(body.get("at"), body.get("alert_id"))
        if detail is None:
            return msgpack_error("NWS alert detail is unavailable for that retained frame", 404)
        return msgpack_response({"type": "local_ops_nws_alert_detail", "detail": detail})
    except Exception as exc:
        logger.exception("Ops NWS alert detail error")
        return msgpack_error(str(exc), 500)


@router.post("/api/local/ops/timeline/point-frame")
async def local_ops_timeline_point_frame_endpoint(req: Request):
    """Return one retained generic point-overlay frame for the Ops cursor."""
    try:
        body = await decode_request_body(req)
        overlay_id = str(body.get("overlay_id") or "").strip()
        frame = _local_point_timeline_frame_at(overlay_id, body.get("at"))
        if frame is None:
            return msgpack_error("No retained point-overlay frame at that time", 404)
        return msgpack_response({"type": "ops_live_point_frame", "frame": frame})
    except Exception as exc:
        logger.exception("Ops point timeline frame error")
        return msgpack_error(str(exc), 500)


@router.post("/api/local/ops/timeline/point-frames")
async def local_ops_timeline_point_frames_endpoint(req: Request):
    """Return generic retained point-reading frames for silent hydration."""
    try:
        body = await decode_request_body(req)
        overlay_id = str(body.get("overlay_id") or "").strip()
        values = body.get("at")
        if not is_point_feed(overlay_id):
            return msgpack_error("Unknown live point overlay", 404)
        if not isinstance(values, list) or len(values) > 24:
            return msgpack_error("at must be a list of at most 24 retained frame timestamps", 413)
        return msgpack_response({
            "type": "ops_live_point_frames",
            "overlay_id": overlay_id,
            "frames": _local_point_timeline_frames_at(overlay_id, values),
        })
    except Exception as exc:
        logger.exception("Ops point timeline batch error")
        return msgpack_error(str(exc), 500)


@router.post("/chat/ops")
async def ops_chat_endpoint(req: Request):
    try:
        body = await decode_request_body(req)
        query = body.get("query", "")
        if not query:
            return msgpack_error("No query provided", 400)
        route_context, route_error, rejection_payload, rejection_status, rejection_headers = await prepare_ops_chat_route_context(
            req,
            body,
            query=query,
        )
        if route_error:
            return route_error
        if rejection_payload is not None:
            return msgpack_response(
                rejection_payload,
                status_code=rejection_status or 400,
                headers=rejection_headers or {},
            )
        assert route_context is not None
        if not route_context.allowed_feeds:
            payload = {
                "type": "chat",
                "message": setup_required_ops_message(route_context.auth_user),
                "watch_id": route_context.watch.get("watch_id"),
                "watch_context": route_context.watch,
                "effective_feeds": [],
            }
            return msgpack_response(payload)
        orientation = build_ops_orientation_payload(
            query=query,
            effective_feeds=route_context.effective_feeds,
            selected_popup=body.get("selectedPopup"),
        )
        if orientation is not None:
            return msgpack_response(orientation)
        turn_limit_payload, turn_limit_status, turn_limit_headers = anonymous_turn_limit_rejection_payload(
            session_id=route_context.session_id,
            caller_ctx=route_context.caller_ctx,
            lane="ops",
        )
        if turn_limit_payload is not None:
            log_conversation(
                route_context.frontend_session_id,
                query,
                turn_limit_payload.get("message", ""),
                surface="ops",
                intent=turn_limit_payload.get("error_code") or "anonymous_turn_limit_reached",
                metadata=build_chat_gate_log_metadata(
                    turn_limit_payload,
                    gate_kind="anonymous_turn_limit",
                ),
            )
            return msgpack_response(
                turn_limit_payload,
                status_code=turn_limit_status or 429,
                headers=turn_limit_headers or {},
            )
        register_anonymous_chat_turn(
            session_id=route_context.session_id,
            caller_ctx=route_context.caller_ctx,
            lane="ops",
        )

        usage_recorder = build_usage_recorder(
            surface="ops",
            call_kind="ops_main",
            session_id=route_context.session_id,
            request_id=route_context.request_id,
            caller_ctx=route_context.caller_ctx,
            qa_suite_metadata=route_context.qa_suite_metadata,
        )
        try:
            result = await ops_orchestrator.run(
                query=query,
                chat_history=body.get("chatHistory", []),
                watch=route_context.watch,
                effective_feeds=route_context.effective_feeds,
                usage_recorder=usage_recorder,
                catalog_surface=route_context.catalog_surface,
                cache=route_context.cache,
                selected_popup=body.get("selectedPopup"),
            )
        finally:
            usage_recorder.flush()
        log_conversation(
            route_context.frontend_session_id,
            query,
            result.get("message", ""),
            surface="ops",
            intent=result.get("type"),
            ip_hash=hash_ip_for_analytics(route_context.client_ip),
            user_agent=(req.headers.get("user-agent") or "")[:300] or None,
        )
        return msgpack_response(result)
    except Exception as exc:
        logger.exception("Ops chat error")
        log_app_error(type(exc).__name__, str(exc), surface="human_app", path="/chat/ops")
        return msgpack_response(
            build_provider_error_payload(
                exc,
                lane="ops",
                request_id=getattr(getattr(req, "state", None), "analytics_request_id", None),
            )
            or build_chat_error_payload(
                lane="ops",
                message="Ops mode hit an internal error.",
                error_code="ops_internal_error",
                request_id=getattr(getattr(req, "state", None), "analytics_request_id", None),
                stage="route",
                retry_hint="Retry the watch question. If it keeps failing, ask about one feed at a time."
            ),
            status_code=500,
        )


@router.post("/chat/ops/stream")
async def ops_chat_stream_endpoint(req: Request):
    body = await decode_json_or_msgpack_body(req)

    async def generate_events():
        try:
            query = body.get("query", "")
            if not query:
                yield encode_sse(stage_payload("complete", result={"type": "error", "message": "No query provided"}))
                return
            route_context, route_error, rejection_payload, _rejection_status, _rejection_headers = await prepare_ops_chat_route_context(
                req,
                body,
                query=query,
            )
            if route_error or rejection_payload is not None:
                payload = rejection_payload or {"type": "error", "message": "Ops request could not be prepared."}
                if rejection_payload is not None and route_context is not None:
                    log_conversation(
                        route_context.frontend_session_id,
                        query,
                        rejection_payload.get("message", ""),
                        surface="ops",
                        intent=rejection_payload.get("error_code") or "anonymous_budget_blocked",
                        metadata=build_chat_gate_log_metadata(
                            rejection_payload,
                            gate_kind="anonymous_daily_budget",
                        ),
                    )
                yield encode_sse(stage_payload("complete", result=payload))
                return
            assert route_context is not None
            if not route_context.allowed_feeds:
                yield encode_sse(stage_payload("complete", result={
                    "type": "chat",
                    "message": setup_required_ops_message(route_context.auth_user),
                    "watch_id": route_context.watch.get("watch_id"),
                    "watch_context": route_context.watch,
                    "effective_feeds": [],
                }))
                return
            orientation = build_ops_orientation_payload(
                query=query,
                effective_feeds=route_context.effective_feeds,
                selected_popup=body.get("selectedPopup"),
            )
            if orientation is not None:
                yield encode_sse(stage_payload("complete", result=orientation))
                return
            turn_limit_payload, _turn_limit_status, _turn_limit_headers = anonymous_turn_limit_rejection_payload(
                session_id=route_context.session_id,
                caller_ctx=route_context.caller_ctx,
                lane="ops",
            )
            if turn_limit_payload is not None:
                log_conversation(
                    route_context.frontend_session_id,
                    query,
                    turn_limit_payload.get("message", ""),
                    surface="ops",
                    intent=turn_limit_payload.get("error_code") or "anonymous_turn_limit_reached",
                    metadata=build_chat_gate_log_metadata(
                        turn_limit_payload,
                        gate_kind="anonymous_turn_limit",
                    ),
                )
                yield encode_sse(stage_payload("complete", result=turn_limit_payload))
                return
            register_anonymous_chat_turn(
                session_id=route_context.session_id,
                caller_ctx=route_context.caller_ctx,
                lane="ops",
            )

            usage_recorder = build_usage_recorder(
                surface="ops",
                call_kind="ops_main",
                session_id=route_context.session_id,
                request_id=route_context.request_id,
                caller_ctx=route_context.caller_ctx,
                qa_suite_metadata=route_context.qa_suite_metadata,
            )
            try:
                yield encode_sse(stage_payload("analyzing", message="Reviewing the Ops watch..."))
                yield encode_sse(stage_payload("thinking", message="Reading the current Ops report..."))
                result = await ops_orchestrator.run(
                    query=query,
                    chat_history=body.get("chatHistory", []),
                    watch=route_context.watch,
                    effective_feeds=route_context.effective_feeds,
                    usage_recorder=usage_recorder,
                    catalog_surface=route_context.catalog_surface,
                    cache=route_context.cache,
                    selected_popup=body.get("selectedPopup"),
                )
            finally:
                usage_recorder.flush()
            yield encode_sse(stage_payload("complete", result=result))
        except Exception as exc:
            logger.exception("Ops streaming chat error")
            log_app_error(type(exc).__name__, str(exc), surface="human_app", path="/chat/ops/stream")
            yield encode_sse(
                stage_payload(
                    "complete",
                    result=build_provider_error_payload(
                        exc,
                        lane="ops",
                        request_id=getattr(getattr(req, "state", None), "analytics_request_id", None),
                        stage="llm_call",
                    )
                    or build_chat_error_payload(
                        lane="ops",
                        message="Ops mode hit an internal error.",
                        error_code="ops_internal_error",
                        request_id=getattr(getattr(req, "state", None), "analytics_request_id", None),
                        stage="stream_route",
                        retry_hint="Retry the watch question. If it keeps failing, ask about one feed at a time."
                    ),
                )
            )

    return StreamingResponse(generate_events(), media_type="text/event-stream", headers=SSE_HEADERS)
