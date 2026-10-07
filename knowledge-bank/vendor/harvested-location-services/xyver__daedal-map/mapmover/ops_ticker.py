"""Ops announcement ticker.

A GENERIC scrolling-announcement surface. The ticker core knows nothing about
any particular feed: it collects normalized ticker items from registered
per-source adapters, then dedupes, orders, and caps them uniformly.

To add a feed to the ticker, write an adapter and register it:

    def my_feed_adapter(snapshot: dict) -> list[dict]:
        return [make_ticker_item(source="My Feed", text="...", severity="warning",
                                 issued="2026-...", item_id="...")]
    register_ticker_adapter("my_feed", my_feed_adapter)

All source-specific formatting (severity mapping, headlines, jargon translation)
lives in the adapter. The generic core owns dedupe, ordering, and capping.

Normalized ticker item shape (use make_ticker_item to build one):
    { id, source, text, severity, scale (badge, optional), issued (iso),
      lead (bool - pins to the very top, e.g. a "current conditions" headline) }

Reads the same current_state snapshots the live collectors publish:
- cloud:  R2 published/live_state/collectors/<name>/snapshot.json

Read-only and best-effort: a missing/malformed feed is skipped, so the ticker
degrades to fewer items rather than erroring.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Callable

from mapmover import logger

# Severity vocabulary shared across all sources, ordered most -> least urgent.
# Adapters map their own concepts onto these; the core orders by this rank.
SEVERITY_ORDER = ("severe", "warning", "watch", "alert", "info")
_SEVERITY_RANK = {name: idx for idx, name in enumerate(SEVERITY_ORDER)}
# Total items the ticker will carry across all feeds after ordering.
MAX_TICKER_ITEMS = 12

_SNAPSHOT_CACHE_TTL_SECONDS = 15.0
_TICKER_CACHE_TTL_SECONDS = 30.0
_AURORA_CACHE_TTL_SECONDS = 60.0
_CACHE_LOCK = threading.Lock()
_SNAPSHOT_CACHE: dict[str, dict] = {}
_VIEW_CACHE: dict[str, dict] = {}

# feed name -> adapter(snapshot dict) -> list[ticker item]
TickerAdapter = Callable[[dict], "list[dict]"]
_TICKER_ADAPTERS: "dict[str, TickerAdapter]" = {}


# ---------------------------------------------------------------------------
# Snapshot reading + caching
# ---------------------------------------------------------------------------
def read_live_snapshot(collector: str) -> dict | None:
    """Read one collector's cloud current_state snapshot.

    Ops map overlays must use the same live-state contract as Ops chat: cloud
    object storage first, then the hosted live-state endpoint fallback. Local
    collector files are temporary test artifacts and are not runtime truth.
    """
    name = str(collector or "").strip()
    if not name:
        return None
    try:
        from mapmover.ops_orchestrator_runtime import load_current_state_snapshot
        data = load_current_state_snapshot(name)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        # A missing snapshot (collector not publishing yet) is normal; keep it
        # at debug so the ticker poll does not spam warnings every cycle.
        logger.debug("ticker: cloud live-state read failed for %s: %s", name, exc)
    return None


def _parse_issued_timestamp(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _snapshot_identity(snapshot: dict | None) -> tuple[str, str, str]:
    snap = snapshot if isinstance(snapshot, dict) else {}
    return (
        str(snap.get("payload_hash") or "").strip(),
        str(snap.get("upstream_issued_at") or "").strip(),
        str(snap.get("collector_status") or "").strip(),
    )


def get_cached_live_snapshot(collector: str, *, ttl_seconds: float = _SNAPSHOT_CACHE_TTL_SECONDS) -> dict | None:
    """Return a short-lived cached snapshot so many clients do not re-read R2."""
    now = time.time()
    with _CACHE_LOCK:
        entry = _SNAPSHOT_CACHE.get(collector)
        if entry is not None and (now - float(entry.get("cached_at") or 0.0)) < ttl_seconds:
            return entry.get("snapshot")
    snapshot = read_live_snapshot(collector)
    with _CACHE_LOCK:
        _SNAPSHOT_CACHE[collector] = {
            "cached_at": now,
            "snapshot": snapshot,
        }
    return snapshot


def _get_cached_view(cache_key: str, *, cache_identity: tuple, ttl_seconds: float, builder):
    now = time.time()
    with _CACHE_LOCK:
        entry = _VIEW_CACHE.get(cache_key)
        if (
            entry is not None
            and entry.get("identity") == cache_identity
            and (now - float(entry.get("cached_at") or 0.0)) < ttl_seconds
        ):
            return entry.get("payload")
    payload = builder()
    with _CACHE_LOCK:
        _VIEW_CACHE[cache_key] = {
            "cached_at": now,
            "identity": cache_identity,
            "payload": payload,
        }
    return payload


# ---------------------------------------------------------------------------
# Generic ticker core (source-agnostic)
# ---------------------------------------------------------------------------
def register_ticker_adapter(feed: str, adapter: TickerAdapter) -> None:
    """Register a per-source adapter. Call at import time from the adapter module."""
    _TICKER_ADAPTERS[feed] = adapter


def ticker_feeds() -> tuple[str, ...]:
    """Feeds with a registered adapter, in registration order."""
    return tuple(_TICKER_ADAPTERS.keys())


def make_ticker_item(
    *,
    source: str,
    text: str,
    severity: str = "info",
    scale: str = "",
    issued: object = "",
    item_id: str | None = None,
    lead: bool = False,
    point: object = None,
    url: str = "",
) -> dict | None:
    """Build a normalized ticker item, or None if the text is empty.

    Adapters should use this so every item has a consistent shape and a valid
    severity (anything unknown falls back to "info"). On click: a `point`
    [lon, lat] pans the map to that location; otherwise a `url` opens the source
    agency page in a new tab.
    """
    clean_text = " ".join(str(text or "").split())
    if not clean_text:
        return None
    if severity not in _SEVERITY_RANK:
        severity = "info"
    item = {
        "id": str(item_id or f"{source}:{clean_text}"),
        "source": str(source or ""),
        "text": clean_text,
        "severity": severity,
        "scale": str(scale or ""),
        "issued": str(issued or ""),
        "lead": bool(lead),
    }
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        item["point"] = [round(float(point[0]), 4), round(float(point[1]), 4)]
    if url:
        item["url"] = str(url)
    return item


def _order_items(items: "list[dict]") -> "list[dict]":
    """Dedupe, order, and cap a mixed list of items from any number of feeds.

    Order: lead items first, then by severity (severe..info), then recency.
    Stable sorts mean the recency pass is preserved within each band.
    """
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for it in items:
        if not it or not it.get("text"):
            continue
        key = (
            it.get("source"),
            it.get("id") or "",
            it.get("text"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    deduped.sort(key=lambda it: _parse_issued_timestamp(it.get("issued")), reverse=True)
    deduped.sort(key=lambda it: (
        0 if it.get("lead") else 1,
        _SEVERITY_RANK.get(str(it.get("severity") or ""), len(SEVERITY_ORDER)),
    ))
    return deduped[:MAX_TICKER_ITEMS]


def _collect_items(feeds: "tuple[str, ...]", snapshot_getter: "Callable[[str], dict | None]") -> "list[dict]":
    items: list[dict] = []
    for feed in feeds:
        adapter = _TICKER_ADAPTERS.get(feed)
        if not adapter:
            continue
        snap = snapshot_getter(feed)
        if not snap:
            continue
        try:
            adapted = adapter(snap) or []
            for item in adapted:
                if isinstance(item, dict) and not item.get("feed"):
                    item["feed"] = feed
            items.extend(adapted)
        except Exception as exc:
            logger.warning("ticker: adapter failed for %s: %s", feed, exc)
    return _order_items(items)


def build_ticker_items(feeds: "tuple[str, ...] | None" = None) -> "list[dict]":
    """Aggregate, order, and cap ticker items across the given feeds."""
    feeds = feeds or ticker_feeds()
    return _collect_items(feeds, get_cached_live_snapshot)


def build_cached_ticker_payload(feeds: "tuple[str, ...] | None" = None) -> dict:
    """Response-cached ticker payload (keyed on the feed snapshots' identity)."""
    feeds = feeds or ticker_feeds()
    snapshots: dict[str, dict] = {}
    identities: list[tuple] = []
    for feed in feeds:
        snap = get_cached_live_snapshot(feed)
        snapshots[feed] = snap if isinstance(snap, dict) else {}
        identities.append((feed, _snapshot_identity(snap)))

    def _builder() -> dict:
        items = _collect_items(feeds, lambda f: snapshots.get(f))
        return {"type": "ops_ticker", "items": items, "count": len(items)}

    return _get_cached_view(
        "ops_ticker",
        cache_identity=tuple(identities),
        ttl_seconds=_TICKER_CACHE_TTL_SECONDS,
        builder=_builder,
    )


# ---------------------------------------------------------------------------
# Source adapters
#
# Each adapter turns one feed's snapshot into normalized ticker items. All
# source-specific knowledge lives here; the core above stays generic.
# ---------------------------------------------------------------------------

# --- NOAA SWPC space-weather alerts ---
_SCALE_KIND = {"G": "geomagnetic storm", "S": "solar radiation storm", "R": "radio blackout"}
_SCALE_LEVEL = {"1": "minor", "2": "moderate", "3": "strong", "4": "severe", "5": "extreme"}


def _swpc_severity(alert_type: str | None, scale: str | None) -> str:
    s = (scale or "").upper()
    if s[:2] in ("G4", "G5", "S4", "S5", "R4", "R5"):
        return "severe"
    t = (alert_type or "").upper()
    if "WARNING" in t:
        return "warning"
    if "WATCH" in t:
        return "watch"
    if "ALERT" in t:
        return "alert"
    return "info"


def _humanize_swpc_text(alert: dict) -> str:
    summary = str(alert.get("summary") or "").strip()
    if summary:
        return " ".join(summary.split())
    alert_type = str(alert.get("alert_type") or "").strip().title()
    scale = str(alert.get("noaa_scale") or "").strip().upper()
    if alert_type and scale:
        return f"{alert_type} {scale}"
    if alert_type:
        return alert_type
    if scale:
        return f"Space weather {scale}"
    return "Space weather update"


def _swpc_conditions_item(snap: dict, summary: dict) -> dict | None:
    """Plain-language 'current conditions' headline from active NOAA scales."""
    scales = [str(s).strip().upper() for s in (summary.get("active_scales") or [])]
    scales = [s for s in scales if len(s) >= 2 and s[0] in _SCALE_KIND and s[1] in _SCALE_LEVEL]
    if not scales:
        return None
    # Collapse to the highest level per kind (G2 implies G1, so drop G1).
    by_letter: dict[str, str] = {}
    for s in scales:
        if s[0] not in by_letter or int(s[1]) > int(by_letter[s[0]][1]):
            by_letter[s[0]] = s
    ordered = sorted(by_letter.values(), key=lambda s: int(s[1]), reverse=True)
    parts = [f"{s} {_SCALE_LEVEL[s[1]]} {_SCALE_KIND[s[0]]}" for s in ordered]
    max_level = max(int(s[1]) for s in ordered)
    severity = "severe" if max_level >= 4 else "warning" if max_level >= 3 else "watch"
    return make_ticker_item(
        source="Space Weather",
        text="Active now: " + ", ".join(parts),
        severity=severity,
        scale=ordered[0],
        issued=snap.get("upstream_issued_at") or "",
        item_id="swpc-conditions",
        lead=True,
        url=_SWPC_SOURCE_URL,
    )


# Source agency page for space-weather alerts (no per-alert SWPC page exists).
_SWPC_SOURCE_URL = "https://www.swpc.noaa.gov/products/alerts-watches-and-warnings"


def swpc_ticker_adapter(snap: dict) -> "list[dict]":
    summary = snap.get("payload_summary") or {}
    items: list[dict] = []
    conditions = _swpc_conditions_item(snap, summary)
    if conditions:
        items.append(conditions)
    for alert in (summary.get("alerts") or []):
        item = make_ticker_item(
            source="Space Weather",
            text=_humanize_swpc_text(alert),
            severity=_swpc_severity(alert.get("alert_type"), alert.get("noaa_scale")),
            scale=alert.get("noaa_scale") or "",
            issued=alert.get("issued_utc"),
            item_id=alert.get("alert_id"),
            url=_SWPC_SOURCE_URL,
        )
        if item:
            items.append(item)
    return items


register_ticker_adapter("noaa_swpc", swpc_ticker_adapter)


# --- NWS active weather alerts ---
_NWS_SEVERITY = {
    "Extreme": "severe",
    "Severe": "warning",
    "Moderate": "watch",
    "Minor": "alert",
    "Unknown": "info",
}

_NWS_ALERT_FAMILY_COLORS = {
    # Shared with static/modules/overlay-nws-alerts.js. The first three match
    # the base disaster families in DISASTER_DISPLAY.md; the rest are NWS
    # operational-alert extensions.
    "tornado": "#64748b",
    "thunderstorm": "#facc15",
    "flood": "#0284c7",
    "winter": "#38bdf8",
    "heat": "#f97316",
    "fire": "#ea580c",
    "wind": "#64748b",
    "tropical": "#0ea5e9",
    "marine": "#0d9488",
    "fog": "#94a3b8",
    "dust": "#a16207",
    "other": "#a3a3a3",
}


def _nws_alert_family(event: object) -> str:
    text = str(event or "").strip().lower()
    if not text:
        return "other"
    if "tornado" in text:
        return "tornado"
    if "thunderstorm" in text:
        return "thunderstorm"
    if "flash flood" in text or "flood" in text:
        return "flood"
    if (
        "winter" in text
        or "snow" in text
        or "blizzard" in text
        or "ice" in text
        or "freezing" in text
    ):
        return "winter"
    if "heat" in text:
        return "heat"
    if "fire" in text or "red flag" in text:
        return "fire"
    if "wind" in text or "squall" in text:
        return "wind"
    if "hurricane" in text or "tropical storm" in text:
        return "tropical"
    if (
        "marine" in text
        or "coastal" in text
        or "surf" in text
        or "rip current" in text
        or "gale" in text
        or "small craft" in text
    ):
        return "marine"
    if "fog" in text:
        return "fog"
    if "dust" in text:
        return "dust"
    return "other"


def _apply_nws_ticker_accent(item: dict | None, event: object) -> dict | None:
    if not item:
        return None
    family = _nws_alert_family(event)
    item["alert_family"] = family
    item["accent_color"] = _NWS_ALERT_FAMILY_COLORS.get(family, _NWS_ALERT_FAMILY_COLORS["other"])
    return item


def _short_area(area: object) -> str:
    parts = [p.strip() for p in str(area or "").split(";") if p.strip()]
    if not parts:
        return ""
    if len(parts) <= 2:
        return "; ".join(parts)
    return "; ".join(parts[:2]) + f" +{len(parts) - 2} more"


def _nws_conditions_item(snap: dict, summary: dict) -> dict | None:
    count = int(summary.get("alert_count") or 0)
    if count <= 0:
        return None
    parts = []
    for entry in (summary.get("top_events") or [])[:4]:
        event = str(entry.get("event") or "").strip()
        if event:
            parts.append(f"{entry.get('count')} {event}")
    detail = ", ".join(parts) if parts else f"{count} active"
    by_severity = summary.get("by_severity") or {}
    severity = "severe" if by_severity.get("Extreme") else "warning"
    lead_item = make_ticker_item(
        source="NWS",
        text=f"{count} active US weather alerts: {detail}",
        severity=severity,
        issued=snap.get("upstream_issued_at") or "",
        item_id="nws-conditions",
        lead=True,
        url="https://api.weather.gov/alerts/active",
    )
    lead_family = "other"
    for entry in (summary.get("top_events") or [])[:1]:
        lead_family = _nws_alert_family(entry.get("event"))
        break
    if lead_item:
        lead_item["alert_family"] = lead_family
        lead_item["accent_color"] = _NWS_ALERT_FAMILY_COLORS.get(lead_family, _NWS_ALERT_FAMILY_COLORS["other"])
    return lead_item


def nws_alerts_ticker_adapter(snap: dict) -> "list[dict]":
    summary = snap.get("payload_summary") or {}
    items: list[dict] = []
    conditions = _nws_conditions_item(snap, summary)
    if conditions:
        items.append(conditions)
    for alert in (summary.get("alerts") or []):
        event = str(alert.get("event") or "Alert").strip()
        area = _short_area(alert.get("area"))
        text = f"{event} - {area}" if area else event
        item = make_ticker_item(
            source="NWS",
            text=text,
            severity=_NWS_SEVERITY.get(alert.get("severity"), "info"),
            issued=alert.get("issued_at") or snap.get("upstream_issued_at") or "",
            item_id=alert.get("alert_id"),
            point=alert.get("point"),
            url=alert.get("alert_id") if str(alert.get("alert_id") or "").startswith("http") else "",
        )
        if item:
            items.append(_apply_nws_ticker_accent(item, event))
    return items


register_ticker_adapter("usa_nws_alerts", nws_alerts_ticker_adapter)


# ---------------------------------------------------------------------------
# Aurora overlay payload (separate from the ticker - it is a map layer)
# ---------------------------------------------------------------------------
def build_cached_aurora_payload() -> dict:
    """Response-cached aurora overlay payload (renderable cells + forecast times)."""
    snap = get_cached_live_snapshot("noaa_aurora")
    snapshot = snap if isinstance(snap, dict) else {}
    summary = snapshot.get("payload_summary") or {}

    def _builder() -> dict:
        return {
            "type": "aurora",
            "observation_time": summary.get("observation_time"),
            "forecast_time": summary.get("forecast_time"),
            "max_probability": summary.get("max_probability"),
            "aurora_visible": summary.get("aurora_visible"),
            "visible_cell_count": summary.get("visible_cell_count"),
            "strong_cell_count": summary.get("strong_cell_count"),
            "cells_truncated": summary.get("cells_truncated"),
            "cells": summary.get("cells") or [],
        }

    return _get_cached_view(
        "ops_aurora",
        cache_identity=_snapshot_identity(snapshot),
        ttl_seconds=_AURORA_CACHE_TTL_SECONDS,
        builder=_builder,
    )


def build_cached_aurora_frames_payload() -> dict:
    """Compact rolling Aurora frames; decoded by the browser overlay."""
    from mapmover.ops_orchestrator_runtime import load_aurora_frame_bundle
    bundle = load_aurora_frame_bundle()
    frames = bundle.get("frames") if isinstance(bundle.get("frames"), list) else []
    return _get_cached_view(
        "ops_aurora_frames",
        cache_identity=(len(frames), str((frames[-1] if frames else {}).get("issued_at") or "")),
        ttl_seconds=_AURORA_CACHE_TTL_SECONDS,
        builder=lambda: {"encoding": bundle.get("encoding"), "frames": frames},
    )


# ---------------------------------------------------------------------------
# NWS alerts map overlay payload
#
# GeoJSON FeatureCollection for the NWS alerts overlay, from the usa_nws_alerts
# snapshot. Display geometry, in priority order:
#   1. the inline NWS warning polygon baked into the snapshot - used as-is, no
#      recompute (the API already gave it to us)
#   2. else the affected county polygons, resolved from FIPS via shared runtime
#      geometry
#   3. else a pin at the baked centroid
# Cached on snapshot content identity, so county resolution runs once per
# collector-produced snapshot change, not per user read.
# ---------------------------------------------------------------------------
_NWS_ALERTS_CACHE_TTL_SECONDS = 60.0

# 2-digit state FIPS -> USPS abbrev, to build USA county loc_ids from SAME codes.
_FIPS2_TO_ABBREV = {
    '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO',
    '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI',
    '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY',
    '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN',
    '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH',
    '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH',
    '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD',
    '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA',
    '54': 'WV', '55': 'WI', '56': 'WY', '60': 'AS', '66': 'GU', '69': 'MP',
    '72': 'PR', '78': 'VI',
}


def _nws_alert_loc_ids(same_codes) -> list:
    loc_ids = []
    for code in same_codes or []:
        text = str(code)
        fips5 = text[-5:] if len(text) >= 5 else text
        if len(fips5) == 5 and fips5.isdigit():
            abbrev = _FIPS2_TO_ABBREV.get(fips5[:2])
            if abbrev:
                loc_ids.append(f"USA-{abbrev}-{fips5[2:]}")
    return loc_ids


def _assemble_nws_alerts_geojson(
    summary: dict,
    *,
    compact_county_geometry: bool = False,
    compact_detail_text: bool = False,
) -> dict:
    alerts = summary.get("alerts") or []

    # Resolve county polygons only for the legacy fully-shaped form.  Ops uses
    # compact state frames: they carry stable county ids and the browser joins
    # them with the shared geometry cache once, rather than retransmitting the
    # same county polygon in every retained alert snapshot.
    needed = set()
    for alert in alerts:
        if not alert.get("geometry"):
            needed.update(_nws_alert_loc_ids(alert.get("same")))
    county_geoms: dict = {}
    if needed and not compact_county_geometry:
        try:
            from mapmover.geometry_handlers import get_selection_geometries
            collection = get_selection_geometries(list(needed))
            for feature in collection.get("features") or []:
                lid = (feature.get("properties") or {}).get("loc_id")
                if lid and feature.get("geometry"):
                    county_geoms[lid] = feature["geometry"]
        except Exception as exc:
            logger.warning("nws overlay: county geometry resolve failed: %s", exc)

    features = []
    county_references = []
    for alert in alerts:
        props = {
            "alert_id": alert.get("alert_id"),
            "event": alert.get("event"),
            "severity": alert.get("severity"),
            "urgency": alert.get("urgency"),
            "certainty": alert.get("certainty"),
            "headline": alert.get("headline"),
            "area": alert.get("area"),
            "issued_at": alert.get("issued_at"),
            "expires": alert.get("expires"),
        }
        if compact_detail_text:
            props["detail_available"] = bool(alert.get("description") or alert.get("instruction"))
        else:
            props["description"] = alert.get("description")
            props["instruction"] = alert.get("instruction")
        # Area geometry: the exact warning polygon, or the affected counties.
        geom = alert.get("geometry")
        if isinstance(geom, dict):
            features.append({"type": "Feature", "geometry": geom, "properties": {**props, "display": "polygon"}})
        else:
            loc_ids = _nws_alert_loc_ids(alert.get("same"))
            if compact_county_geometry and loc_ids:
                county_references.append({"loc_ids": loc_ids, "properties": {**props, "display": "county"}})
            else:
                for lid in loc_ids:
                    poly = county_geoms.get(lid)
                    if poly:
                        features.append({"type": "Feature", "geometry": poly, "properties": {**props, "display": "county", "loc_id": lid}})
        # ALWAYS add a center marker so every alert has a clear single target,
        # not just a spread of highlighted areas (helps the eye and the click).
        point = alert.get("point")
        if point:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": point},
                "properties": {**props, "display": "marker"},
            })
    return {
        "type": "FeatureCollection",
        "features": features,
        "county_geometry_references": county_references,
        "count": len(features),
    }


def build_cached_nws_alerts_payload() -> dict:
    """Response-cached NWS alerts overlay (GeoJSON), resolved once per snapshot."""
    snap = get_cached_live_snapshot("usa_nws_alerts")
    snapshot = snap if isinstance(snap, dict) else {}

    def _builder() -> dict:
        payload = _assemble_nws_alerts_geojson(
            snapshot.get("payload_summary") or {},
            compact_county_geometry=True,
            compact_detail_text=True,
        )
        payload["detail_at"] = snapshot.get("published_at") or snapshot.get("fetched_at")
        return payload

    return _get_cached_view(
        "ops_nws_alerts",
        cache_identity=_snapshot_identity(snapshot),
        ttl_seconds=_NWS_ALERTS_CACHE_TTL_SECONDS,
        builder=_builder,
    )


def build_nws_alerts_payload_for_snapshot(snapshot: dict) -> dict:
    """Build one retained NWS frame without using the current-snapshot cache."""
    summary = snapshot.get("payload_summary") if isinstance(snapshot, dict) else {}
    payload = _assemble_nws_alerts_geojson(
        summary if isinstance(summary, dict) else {},
        compact_county_geometry=True,
        compact_detail_text=True,
    )
    payload["detail_at"] = snapshot.get("published_at") or snapshot.get("fetched_at")
    return payload
