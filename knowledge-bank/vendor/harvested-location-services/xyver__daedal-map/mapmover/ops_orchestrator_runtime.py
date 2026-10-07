"""Lane-owned Ops orchestrator runtime helpers."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from mapmover.geometry_handlers import get_selection_geometries
from mapmover import logger
from mapmover.foundation_helpers import load_reference_dict
from mapmover.preprocessor_locations import detect_location_candidates
from mapmover.routes.disasters.related import _classify_exact_event_identifier
from mapmover.runtime.llm_policy import sampling_kwargs
from mapmover.runtime.loc_id_resolution import resolve_point_to_loc_id_stack
from mapmover.runtime.preprocess_user_intents import normalize_query_for_location_matching
from mapmover.runtime_config import get_runtime_config
from mapmover.paths import DATA_ROOT
from mapmover.ops_feed_registry import ops_feed_ids, ops_feed_record

try:
    import boto3
except ImportError:
    boto3 = None

try:
    import msgpack
except ImportError:
    msgpack = None

try:
    from botocore.config import Config as BotocoreConfig
except ImportError:
    BotocoreConfig = None

try:
    import requests
except ImportError:
    requests = None


PRIVATE_ROOT = Path(__file__).resolve().parents[2] / "county-map-private"
REFERENCE_ROOT = Path(__file__).resolve().parent / "reference"
CURRENCY_MAP_PATH = REFERENCE_ROOT / "country_currency_map.csv"


def _bounded_float_env(name: str, default: float, minimum: float) -> float:
    try:
        return max(minimum, float(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


LIVE_STATE_SNAPSHOT_TTL_SECONDS = _bounded_float_env(
    "OPS_SNAPSHOT_CACHE_TTL_SECONDS", 300.0, 60.0
)
LIVE_STATE_HISTORY_TTL_SECONDS = 60.0
DEFAULT_OPS_HISTORY_RETENTION_HOURS = 72
DEFAULT_OPS_HISTORY_DISPLAY_HOURS = 72
DEFAULT_OPS_LIVE_STATE_BASE_URL = "https://daedalmap.com"
HURRICANE_LIVE_FEED = "hurricanes_live"
WILDFIRE_LIVE_FEED = "wildfires"
WILDFIRE_OPS_COLLECTORS = ("wildfires_us_nifc", "wildfires_can_cwfis")
WILDFIRE_COLLECTOR_ISO3 = {
    "wildfires_us_nifc": "USA",
    "wildfires_can_cwfis": "CAN",
}
HURRICANE_LEGACY_OPS_FEED = "hurricanes"
HURRICANE_OPS_COLLECTORS = ("tc_nhc", "tc_gdacs", "tc_jtwc", "tc_jma")
# A 50 km² default keeps the combined North American live fire snapshot quick
# enough to be a dependable Ops overlay. Chat can still explicitly request a
# lower cutoff or all fires; detailed perimeters are fetched separately for a
# settled close viewport.
WILDFIRE_DEFAULT_MIN_AREA_KM2 = 50.0
# The live source perimeters are authoritative, but several incidents contain
# hundreds of thousands of vertices.  Sending those raw shapes to every Ops
# page load made a normal wildfire report exceed 40 MB.  Keep an honestly
# shaped, map-scale outline while reserving source-native detail for the
# collector/archive and event drill-down paths.
WILDFIRE_MAP_MAX_PERIMETER_POSITIONS = 240
HURRICANE_SOURCE_PRIORITY = {"NHC": 50, "JTWC": 40, "JMA": 35, "GDACS": 10}
# The advisory authority varies by basin.  GDACS deliberately remains context
# only: it may identify an event, but it never wins an observed/forecast track
# while a warning centre has a usable advisory.
HURRICANE_BASIN_SOURCE_PRIORITY = {
    "AL": {"NHC": 70, "JTWC": 35, "JMA": 20, "GDACS": 10},
    "EP": {"NHC": 70, "JTWC": 35, "JMA": 20, "GDACS": 10},
    "CP": {"NHC": 70, "JTWC": 40, "JMA": 20, "GDACS": 10},
    "WP": {"JMA": 70, "JTWC": 65, "NHC": 20, "GDACS": 10},
    "IO": {"JTWC": 70, "JMA": 25, "NHC": 20, "GDACS": 10},
    "SH": {"JTWC": 70, "JMA": 30, "NHC": 20, "GDACS": 10},
}
# A current source is authoritative while its advisory is still reasonably
# current.  Beyond this window, a basin-overlapping warning centre may take
# over the live marker/forecast until the primary source resumes.
HURRICANE_AUTHORITY_FALLBACK_MAX_AGE_HOURS = 6
# Observed tracks are intentionally composited at this cadence.  It matches
# the native 3–6h advisory cadence, collapses repeated poll copies, and lets
# a fallback fill a genuine primary-source gap without creating zigzags.
HURRICANE_TRACK_SLOT_HOURS = 3
HURRICANE_ACTIVE_FIX_MAX_AGE_HOURS = 18
HURRICANE_SOURCE_PAGES = {
    "NHC": "https://www.nhc.noaa.gov/cyclones/",
    "GDACS": "https://www.gdacs.org/",
    "JTWC": "https://www.metoc.navy.mil/jtwc/jtwc.html",
    "JMA": "https://www.data.jma.go.jp/multi/cyclone/index.html?lang=en",
}
HURRICANE_SOURCE_LABELS = {
    "NHC": "National Hurricane Center",
    "GDACS": "GDACS Tropical Cyclone Alerts",
    "JTWC": "Joint Typhoon Warning Center",
    "JMA": "Japan Meteorological Agency",
}
# Live-track colour is an identity property, not an advisory property.  A
# warning centre can revise intensity/category between retained snapshots;
# changing the visual identity of the same storm while an operator scrubs the
# timeline makes a continuous track look like a different event.  Keep a
# small, high-contrast deterministic palette so every feature for one storm
# (observed line, current fix, forecast, and hover geometry) has one colour.
HURRICANE_STORM_COLORS = (
    "#35d0ff", "#ffcf5c", "#ff6f91", "#a78bfa",
    "#44d7a8", "#ff9f5c", "#60a5fa", "#f472b6",
)

HURRICANE_PLACEHOLDER_NAMES = {
    "unnamed", "invest", "tropical depression", "tropical storm",
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
    "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
}
USGS_FDSN_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
_LIVE_STATE_CACHE: dict[tuple[str, str], tuple[float, object]] = {}
_LIVE_STATE_CACHE_LOCK = threading.Lock()
_LIVE_STATE_STATUS: dict[tuple[str, str], str] = {}
_LIVE_STATE_STATUS_LOCK = threading.Lock()


def _normalize_ops_feed_id(feed: object) -> str:
    text = str(feed or "").strip()
    if text == HURRICANE_LEGACY_OPS_FEED:
        return HURRICANE_LIVE_FEED
    return text


def _is_hurricane_live_feed(feed: object) -> bool:
    return _normalize_ops_feed_id(feed) == HURRICANE_LIVE_FEED


def _hurricane_storm_color(storm_id: object) -> str:
    """Return one stable display colour for a canonical live storm ID."""
    encoded = str(storm_id or "").strip().upper().encode("utf-8")
    digest = hashlib.sha256(encoded).digest()
    return HURRICANE_STORM_COLORS[digest[0] % len(HURRICANE_STORM_COLORS)]


def _normalize_hurricane_source_identity(storm: dict) -> dict:
    """Return one source record with a collision-free agency identity.

    Older retained JMA snapshots incorrectly exposed the JMA annual sequence
    as an ATCF/JTWC ``WP`` ID.  Normalize at composition time as well as in the
    collector so the current 72-hour replay repairs itself immediately after a
    runtime deploy instead of waiting for the old records to expire.
    """
    normalized = dict(storm)
    source = str(normalized.get("source") or "").strip().upper()
    identity = dict(normalized.get("identity")) if isinstance(normalized.get("identity"), dict) else {}
    aliases = dict(identity.get("aliases")) if isinstance(identity.get("aliases"), dict) else {}
    if source == "JMA":
        jma_number = str(aliases.get("jma_number") or "").strip().upper()
        if jma_number:
            source_id = f"JMA-{jma_number}"
            original_id = str(normalized.get("storm_id") or "").strip()
            if original_id and original_id != source_id:
                normalized["source_storm_id"] = original_id
            aliases.pop("atcf_id", None)
            identity = {**identity, "canonical_id": source_id, "aliases": aliases}
            normalized["identity"] = identity
            normalized["storm_id"] = source_id
    return normalized


def _hurricane_name_year_key(storm: dict) -> str:
    """Return a conservative cross-agency correlation key for named storms."""
    name = str(storm.get("name") or "").strip()
    normalized_name = re.sub(r"[-_\s]?\d{2,4}$", "", name).strip().lower()
    if not normalized_name or normalized_name in HURRICANE_PLACEHOLDER_NAMES:
        return ""
    if re.fullmatch(r"(?:tropical\s+(?:depression|storm)\s+)?\d+[a-z]?", normalized_name):
        return ""
    year = str(storm.get("year") or "")[:4]
    return f"{normalized_name}:{year}" if year else ""


def _hurricane_logical_identity(storm: dict, fallback_key: str) -> tuple[str, dict]:
    """Choose one stable logical ID without mistaking JMA numbers for ATCF."""
    source_identities = storm.get("source_identities") if isinstance(storm.get("source_identities"), dict) else {}
    for source in ("NHC", "JTWC", "JMA", "GDACS"):
        identity = source_identities.get(source)
        if not isinstance(identity, dict):
            continue
        canonical_id = str(identity.get("canonical_id") or "").strip()
        if canonical_id:
            return canonical_id, dict(identity)
    identity = storm.get("identity") if isinstance(storm.get("identity"), dict) else {}
    canonical_id = str(identity.get("canonical_id") or fallback_key or storm.get("storm_id") or "").strip()
    return canonical_id, {**identity, "canonical_id": canonical_id}


def _hurricane_source_priority_for_storm(storm: dict, source: object | None = None) -> int:
    """Return the dynamic warning-centre preference for one storm/basin."""
    basin = str(storm.get("basin") or "").strip().upper()
    source_key = str(source or storm.get("source") or "").strip().upper()
    return HURRICANE_BASIN_SOURCE_PRIORITY.get(basin, HURRICANE_SOURCE_PRIORITY).get(source_key, 0)


def _hurricane_candidate_time(candidate: dict) -> datetime:
    """Return the advisory time that best describes a candidate's live fix.

    Collectors do not all populate ``issued_at`` consistently.  A current
    position timestamp is therefore the most dependable freshness signal;
    using only issuance time made an older preferred-basin source win over a
    newer usable advisory (and could select an otherwise unrenderable one).
    """
    current = candidate.get("current_position") if isinstance(candidate.get("current_position"), dict) else {}
    return (
        _parse_iso_datetime(current.get("timestamp") or current.get("valid_at") or current.get("time"))
        or _parse_iso_datetime(candidate.get("issued_at") or candidate.get("valid_from"))
        or datetime.min.replace(tzinfo=timezone.utc)
    )


def _hurricane_has_position(candidate: dict) -> bool:
    point = candidate.get("current_position") if isinstance(candidate.get("current_position"), dict) else {}
    try:
        float(point.get("latitude")); float(point.get("longitude"))
        return True
    except (TypeError, ValueError):
        return False


def _hurricane_has_forecast(candidate: dict) -> bool:
    return bool(candidate.get("forecast_points") or candidate.get("forecast_track"))


def _hurricane_candidate_is_fresh(candidate: dict, *, now: datetime | None = None) -> bool:
    observed_at = _hurricane_candidate_time(candidate)
    if observed_at == datetime.min.replace(tzinfo=timezone.utc):
        return False
    reference = now or datetime.now(timezone.utc)
    age_hours = (reference - observed_at).total_seconds() / 3600.0
    return -1.0 <= age_hours <= HURRICANE_AUTHORITY_FALLBACK_MAX_AGE_HOURS


def _select_hurricane_authority_candidate(
    storm: dict,
    candidates: list[dict],
    *,
    usable,
    now: datetime | None = None,
) -> dict | None:
    """Select the basin authority, falling back only when it is missing/stale."""
    eligible = [
        item for item in candidates
        if usable(item) and str(item.get("source") or "").strip().upper() != "GDACS"
    ]
    if not eligible:
        return None
    fresh = [item for item in eligible if _hurricane_candidate_is_fresh(item, now=now)]
    pool = fresh or eligible
    return max(
        pool,
        key=lambda item: (
            _hurricane_source_priority_for_storm(storm, item.get("source")),
            _hurricane_candidate_time(item),
        ),
    )


def _compose_hurricane_candidates(storm: dict) -> dict:
    """Choose one observed and one forecast authority for a canonical storm."""
    candidates = [item for item in (storm.get("source_candidates") or {}).values() if isinstance(item, dict)]
    if not candidates:
        return storm
    observed = _select_hurricane_authority_candidate(
        storm,
        candidates,
        usable=_hurricane_has_position,
    )
    forecast = _select_hurricane_authority_candidate(
        storm,
        candidates,
        usable=_hurricane_has_forecast,
    )
    selected = dict(observed or forecast or storm)
    if forecast:
        for field in ("forecast_points", "forecast_track", "uncertainty_geometry", "forecast_horizon_hours", "valid_through"):
            selected[field] = forecast.get(field)
    selected["contributing_sources"] = list(dict.fromkeys(
        str(item.get("source") or "").upper() for item in candidates if item.get("source")
    ))
    selected["selected_observed_source"] = str(observed.get("source") or "").upper() if observed else None
    selected["selected_forecast_source"] = str(forecast.get("source") or "").upper() if forecast else None
    selected["source_candidates"] = []
    return selected

FEED_ALIASES = {
    "earthquakes": ("earthquake", "earthquakes", "quake", "quakes", "seismic"),
    "currency": ("currency", "currencies", "fx", "exchange rate", "exchange rates", "usd"),
    "tsunamis": ("tsunami", "tsunamis", "runup", "runups"),
    "volcanoes": ("volcano", "volcanoes", "eruption", "eruptions", "vei"),
    WILDFIRE_LIVE_FEED: ("wildfire", "wildfires", "fire", "fires", "nifc", "cwfis"),
    HURRICANE_LIVE_FEED: ("hurricane", "hurricanes", "storm", "storms", "cyclone", "typhoon"),
    "usa_nws_alerts": ("nws", "nws alerts", "weather alert", "weather alerts", "warning", "warnings", "alert", "alerts"),
    "noaa_swpc": ("space weather", "space weather alerts", "geomagnetic", "solar storm", "radio blackout"),
    "noaa_aurora": ("aurora", "aurora conditions", "northern lights"),
    "era5_land_temperature": (
        "land temperature", "land-air temperature", "air temperature",
        "temperature anomaly", "temperature anomalies", "2m temperature",
    ),
    "cams_air_quality": ("air quality", "air pollution", "cams air quality", "particulate matter"),
    "noaa_ndbc": ("buoy", "buoys", "ocean buoy", "marine buoy", "ndbc"),
    "ocean_sst": ("sea surface temperature", "ocean temperature", "ocean sst", "sst"),
}

COUNT_QUERY_PATTERNS = (
    r"\bhow many\b",
    r"\bnumber of\b",
    r"\bcount of\b",
    r"\bcount\b",
)

MAP_FOCUS_PATTERNS = (
    r"\bshow me\b",
    r"\bshow them\b",
    r"\bshow those\b",
    r"\bshow it\b",
    r"\btake me to\b",
    r"\bzoom to\b",
    r"\bgo to\b",
    r"\bmap them\b",
    r"\bmap those\b",
    r"\bmap it\b",
    r"\bput them on the map\b",
    r"\bput those on the map\b",
    r"\blocate\b",
    r"\bwhere is\b",
)

SINGULAR_FOCUS_PATTERNS = (
    r"\bshow it\b",
    r"\bshow that\b",
    r"\bshow this\b",
    r"\bmap it\b",
    r"\bmap that\b",
    r"\bmap this\b",
    r"\bshow the biggest\b",
    r"\bshow the largest\b",
    r"\bshow the strongest\b",
    r"\bshow the worst\b",
    r"\bshow the highest\b",
    r"\bshow the lowest\b",
    r"\bshow the smallest\b",
    r"\bshow the one\b",
    r"\bmap the biggest\b",
    r"\bmap the largest\b",
    r"\bmap the strongest\b",
    r"\bmap the worst\b",
    r"\bmap the highest\b",
    r"\bmap the lowest\b",
    r"\bmap the smallest\b",
    r"\bmap the one\b",
)

SUPERLATIVE_PATTERNS = (
    r"\bbiggest\b",
    r"\blargest\b",
    r"\bsmallest\b",
    r"\bworst\b",
    r"\bstrongest\b",
    r"\bhighest\b",
    r"\blowest\b",
    r"\bmost severe\b",
    r"\bleast severe\b",
)

AREA_IMPACT_PATTERNS = (
    r"\baffect(?:ing|ed|s)?\b",
    r"\bnear(?:by)?\b",
    r"\bclose to\b",
    r"\baround\b",
    r"\bin this area\b",
    r"\bin that area\b",
    r"\bin my area\b",
    r"\bfrom here\b",
    r"\bhere\b",
)

FEED_FOCUS_SPECS = {
    WILDFIRE_LIVE_FEED: {
        "metric_keys": ("area_km2", "burned_acres"),
        "label": "wildfire",
        "id_keys": ("event_id", "incident_id", "fire_name"),
    },
    "earthquakes": {
        "metric_keys": ("magnitude",),
        "label": "earthquake",
        "id_keys": ("event_id",),
    },
    "tsunamis": {
        "metric_keys": ("max_water_height_m", "runup_m", "eq_magnitude"),
        "label": "tsunami event",
        "id_keys": ("event_id",),
    },
    "volcanoes": {
        "metric_keys": ("VEI", "vei"),
        "label": "volcano event",
        "id_keys": ("event_id", "volcano_name"),
    },
    HURRICANE_LIVE_FEED: {
        "metric_keys": ("max_category", "category", "max_wind_kt"),
        "label": "storm",
        "id_keys": ("storm_id", "name"),
    },
}

FEED_HISTORY_METRIC_ALIASES = {
    "earthquakes": {
        "metric_keys": ("magnitude",),
        "aliases": ("magnitude", "mag", "m"),
        "label": "magnitude",
    },
    "tsunamis": {
        "metric_keys": ("max_water_height_m", "runup_m", "eq_magnitude"),
        "aliases": ("runup", "height", "water height", "magnitude", "mag"),
        "label": "severity",
    },
    "volcanoes": {
        "metric_keys": ("VEI", "vei"),
        "aliases": ("vei",),
        "label": "VEI",
    },
    WILDFIRE_LIVE_FEED: {
        "metric_keys": ("area_km2", "burned_acres"),
        "aliases": ("area", "area km2", "acres", "burned acres"),
        "label": "size",
    },
}

OPS_DEFAULT_LOAD_SNAPSHOT = "snapshot"
OPS_DEFAULT_LOAD_HISTORY = "history"
OPS_DEFAULT_LOAD_VALUES = {OPS_DEFAULT_LOAD_SNAPSHOT, OPS_DEFAULT_LOAD_HISTORY}

DEEP_HISTORY_PATTERNS = (
    r"\bchange\b",
    r"\bchanged\b",
    r"\bchanges\b",
    r"\bhistory\b",
    r"\bhistorical\b",
    r"\btrend\b",
    r"\btrends\b",
    r"\btimeline\b",
    r"\bsince\b",
    r"\bprevious\b",
    r"\bearlier\b",
    r"\bbefore\b",
    r"\bhow has\b",
    r"\bwhat changed\b",
    r"\blast\s+\d+",
    r"\bpast\s+\d+",
    r"\btoday\b",
    r"\byesterday\b",
    r"\bintensif",
    r"\bworsen",
    r"\bimprov",
    r"\bgrow",
    r"\bgrew\b",
    r"\bdecrease\b",
    r"\bincrease\b",
)


def _history_messages(chat_history: list | None, limit: int = 10) -> list[dict]:
    out: list[dict] = []
    for msg in (chat_history or [])[-limit:]:
        role = str((msg or {}).get("role") or "user").strip().lower()
        content = str((msg or {}).get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        out.append({"role": role, "content": content})
    return out


def _extract_text(response) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(part.strip() for part in parts if str(part).strip()).strip()


def _object_store_bucket() -> str:
    cloud_cfg = get_runtime_config().get("cloud", {}) or {}
    return str(os.environ.get("S3_BUCKET", "") or str(cloud_cfg.get("bucket", "")) or "").strip()


def _live_state_prefix() -> str:
    configured = str(os.environ.get("S3_LIVE_STATE_PREFIX", "") or "").strip().strip("/")
    if configured:
        return configured
    published_prefix = (
        str(os.environ.get("S3_PUBLISHED_PREFIX", "") or "").strip()
        or str(os.environ.get("S3_PREFIX", "") or "").strip()
        or str((get_runtime_config().get("cloud", {}) or {}).get("prefix", "") or "").strip()
        or "published"
    )
    published_prefix = published_prefix.strip("/")
    return f"{published_prefix}/live_state/collectors" if published_prefix else "live_state/collectors"


def _build_object_store_client():
    if boto3 is None or not _object_store_bucket():
        return None
    cloud_cfg = get_runtime_config().get("cloud", {}) or {}
    endpoint_url = (
        str(os.environ.get("S3_ENDPOINT_URL", "") or "").strip()
        or str(cloud_cfg.get("endpoint_url", "") or "").strip()
        or None
    )
    region = (
        str(os.environ.get("AWS_DEFAULT_REGION", "") or "").strip()
        or str(os.environ.get("AWS_REGION", "") or "").strip()
        or "auto"
    )
    # Live-state reads happen on the interactive request path.  Bound failed
    # cloud attempts so a missing network route cannot turn one unavailable
    # feed into a long serial page load.
    client_kwargs = {
        "endpoint_url": endpoint_url,
        "region_name": region,
    }
    if BotocoreConfig is not None:
        client_kwargs["config"] = BotocoreConfig(
            connect_timeout=3,
            read_timeout=5,
            retries={"max_attempts": 1, "mode": "standard"},
        )
    return boto3.client("s3", **client_kwargs)


def _read_json_object(relative_key: str) -> dict | None:
    client = _build_object_store_client()
    if client is None:
        return None
    key = f"{_live_state_prefix()}/{relative_key}".strip("/")
    try:
        response = client.get_object(Bucket=_object_store_bucket(), Key=key)
        payload = json.loads(response["Body"].read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _read_local_live_state_snapshot(collector: str) -> dict | None:
    """Read an unpublished local collector artifact only in explicit offline mode.

    Ops is a cloud-backed operational surface in every runtime, including a
    developer's localhost session.  A local data mirror can be stale or partial,
    so it must never silently decide what an operator sees.  The fallback exists
    solely for deliberate offline collector development:
    ``OPS_ALLOW_LOCAL_LIVE_STATE_FALLBACK=1``.
    """
    runtime_mode = str(get_runtime_config().get("runtime_mode", "local")).strip().lower()
    allow_local_fallback = str(
        os.environ.get("OPS_ALLOW_LOCAL_LIVE_STATE_FALLBACK", "")
    ).strip().lower() in {"1", "true", "yes"}
    if (
        runtime_mode != "local"
        or not allow_local_fallback
        or not re.fullmatch(r"[A-Za-z0-9_-]+", collector)
    ):
        return None
    paths = (
        DATA_ROOT / "live_state" / "collectors" / collector / "snapshot.json",
        PRIVATE_ROOT / "live" / "state" / collector / "snapshot.json",
    )
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _is_live_state_snapshot(payload: object) -> bool:
    """Reject empty relay/object responses before they mask a usable fallback."""
    return (
        isinstance(payload, dict)
        and bool(payload.get("collector"))
        and isinstance(payload.get("payload_summary"), dict)
    )


def _read_jsonl_object(relative_key: str) -> list[dict]:
    client = _build_object_store_client()
    if client is None:
        return []
    key = f"{_live_state_prefix()}/{relative_key}".strip("/")
    try:
        response = client.get_object(Bucket=_object_store_bucket(), Key=key)
        raw = response["Body"].read().decode("utf-8")
    except Exception:
        return []
    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _is_local_live_state_base_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return True
    host = str(parsed.hostname or "").strip().lower()
    if not parsed.scheme or not host:
        return True
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local")


def _site_live_state_base_url() -> str:
    explicit = (
        str(os.environ.get("OPS_LIVE_STATE_BASE_URL", "") or "").strip()
        or str(os.environ.get("OPS_CONTROL_PLANE_URL", "") or "").strip()
    ).rstrip("/")
    if explicit:
        return explicit

    app_cfg = get_runtime_config().get("app", {}) or {}
    candidates = [
        os.environ.get("CLOUD_URL", ""),
        os.environ.get("SITE_URL", ""),
        app_cfg.get("site_url", ""),
        DEFAULT_OPS_LIVE_STATE_BASE_URL,
    ]
    for candidate in candidates:
        value = str(candidate or "").strip().rstrip("/")
        if value and not _is_local_live_state_base_url(value):
            return value
    return DEFAULT_OPS_LIVE_STATE_BASE_URL


def _live_state_site_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = (
        str(os.environ.get("CLOUD_INTERNAL_API_TOKEN", "") or "").strip()
        or str(os.environ.get("CLOUD_TOKEN", "") or "").strip()
    )
    if token:
        headers["x-internal-api-key"] = token
    return headers


def _live_state_cache_ttl(kind: str) -> float:
    if kind == "history":
        return LIVE_STATE_HISTORY_TTL_SECONDS
    return LIVE_STATE_SNAPSHOT_TTL_SECONDS


def _get_live_state_cache(collector: str, kind: str) -> object | None:
    key = (collector, kind)
    now = time.monotonic()
    with _LIVE_STATE_CACHE_LOCK:
        record = _LIVE_STATE_CACHE.get(key)
        if not record:
            return None
        cached_at, payload = record
        if now - cached_at > _live_state_cache_ttl(kind):
            _LIVE_STATE_CACHE.pop(key, None)
            return None
        return payload


def _set_live_state_cache(collector: str, kind: str, payload: object) -> None:
    key = (collector, kind)
    with _LIVE_STATE_CACHE_LOCK:
        _LIVE_STATE_CACHE[key] = (time.monotonic(), payload)


def _set_live_state_status(collector: str, kind: str, status: str) -> None:
    key = (collector, kind)
    with _LIVE_STATE_STATUS_LOCK:
        _LIVE_STATE_STATUS[key] = status


def _get_live_state_status(collector: str, kind: str) -> str:
    key = (collector, kind)
    with _LIVE_STATE_STATUS_LOCK:
        return str(_LIVE_STATE_STATUS.get(key) or "").strip()


def _cloud_live_state_expected() -> bool:
    return bool(_object_store_bucket())


def _fetch_live_state_via_site(
    collector_name: str,
    kind: str,
    *,
    frame_hash: str | None = None,
) -> dict | list | None:
    if requests is None:
        return None
    base_url = _site_live_state_base_url()
    collector = str(collector_name or "").strip()
    if not base_url or not collector or kind not in {"snapshot", "history", "timeline-index", "frame"}:
        return None
    suffix = f"/{frame_hash}" if kind == "frame" and frame_hash else ""
    try:
        response = requests.get(
            f"{base_url}/api/internal/live-state/{collector}/{kind}{suffix}",
            headers=_live_state_site_headers(),
            timeout=4,
        )
        if response.status_code >= 300:
            return None
        payload = response.json()
    except Exception:
        return None
    if kind in {"snapshot", "timeline-index", "frame"}:
        return payload if isinstance(payload, dict) else None
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return None


def _load_snapshot_child_safely(collector_name: str) -> dict | None:
    """A composite feed must survive one physical upstream/source failing."""
    try:
        return load_current_state_snapshot(collector_name)
    except Exception:
        return None


def _load_history_child_safely(collector_name: str) -> list[dict]:
    """A composite feed's retained view must also survive one child failure."""
    try:
        entries = load_current_state_history(collector_name)
        return entries if isinstance(entries, list) else []
    except Exception:
        return []


def _wildfire_event_with_geography(event: dict, collector_name: str) -> dict:
    """Attach the collector's stable geography to a wildfire event.

    New collector snapshots publish these fields themselves. The fallback is
    kept here so previously published snapshots and retained history can also
    be filtered correctly.
    """
    result = dict(event)
    iso3 = str(result.get("iso3") or WILDFIRE_COLLECTOR_ISO3.get(collector_name) or "").upper()
    if iso3:
        result["iso3"] = iso3
        state = str(result.get("state") or "").strip().upper()
        result.setdefault("loc_id", f"{iso3}-{state}" if iso3 == "USA" and state else iso3)
    return result


def load_current_state_snapshot(
    collector_name: str,
    _composed_children: list[dict] | None = None,
) -> dict | None:
    collector = _normalize_ops_feed_id(collector_name)
    if not collector:
        return None
    if collector == HURRICANE_LIVE_FEED:
        # Each authority is an independent runtime read. Loading them together
        # avoids turning four site-fallback timeouts into a serial startup cost.
        if _composed_children is None:
            with ThreadPoolExecutor(max_workers=len(HURRICANE_OPS_COLLECTORS)) as executor:
                children = list(executor.map(_load_snapshot_child_safely, HURRICANE_OPS_COLLECTORS))
        else:
            children = _composed_children
        children = [item for item in children if isinstance(item, dict)]
        if not children:
            return None
        storms_by_key: dict[str, dict] = {}
        name_year_index: dict[str, str] = {}
        for child in children:
            summary = child.get("payload_summary") if isinstance(child.get("payload_summary"), dict) else {}
            for raw_item in summary.get("storms") or []:
                if not isinstance(raw_item, dict):
                    continue
                item = _normalize_hurricane_source_identity(raw_item)
                name_year_key = _hurricane_name_year_key(item)
                identity = item.get("identity") if isinstance(item.get("identity"), dict) else {}
                canonical_id = str(identity.get("canonical_id") or "").strip()
                key = (
                    name_year_index.get(name_year_key)
                    or canonical_id
                    or name_year_key
                    or str(item.get("storm_id") or "")
                )
                if name_year_key:
                    name_year_index[name_year_key] = key
                existing = storms_by_key.get(key)
                source = str(item.get("source") or "").upper()
                if existing is None:
                    normalized = dict(item)
                    normalized["contributing_sources"] = [source] if source else []
                    normalized["source_identities"] = {
                        source: identity
                    } if source and identity else {}
                    normalized["source_candidates"] = {source: dict(item)} if source else {}
                    if source == "GDACS":
                        normalized["gdacs_alert"] = {
                            field: item.get(field)
                            for field in (
                                "alert_level", "alert_score", "countries", "iso3",
                                "population_affected", "vulnerability", "description",
                                "source_url",
                            )
                        }
                    storms_by_key[key] = normalized
                    continue
                existing_source = str(existing.get("source") or "").upper()
                if source == "GDACS":
                    existing["gdacs_alert"] = {
                        key: item.get(key)
                        for key in (
                            "alert_level", "alert_score", "countries", "iso3",
                            "population_affected", "vulnerability", "description",
                            "source_url",
                        )
                    }
                if source and source not in existing.get("contributing_sources", []):
                    existing.setdefault("contributing_sources", []).append(source)
                if source and identity:
                    existing.setdefault("source_identities", {})[source] = identity
                if source:
                    existing.setdefault("source_candidates", {})[source] = dict(item)
                if HURRICANE_SOURCE_PRIORITY.get(source, 0) > HURRICANE_SOURCE_PRIORITY.get(existing_source, 0):
                    replacement = dict(item)
                    replacement["contributing_sources"] = existing.get("contributing_sources", [])
                    replacement["source_identities"] = existing.get("source_identities", {})
                    replacement["source_candidates"] = existing.get("source_candidates", {})
                    if existing.get("gdacs_alert"):
                        replacement["gdacs_alert"] = existing["gdacs_alert"]
                    storms_by_key[key] = replacement
        storms = []
        for group_key, grouped in storms_by_key.items():
            logical_id, logical_identity = _hurricane_logical_identity(grouped, group_key)
            composed = _compose_hurricane_candidates(grouped)
            selected_source_id = str(composed.get("storm_id") or "").strip()
            if selected_source_id and selected_source_id != logical_id:
                composed["source_storm_id"] = selected_source_id
            composed["storm_id"] = logical_id
            composed["identity"] = logical_identity
            composed["source_identities"] = grouped.get("source_identities", {})
            if grouped.get("gdacs_alert"):
                composed["gdacs_alert"] = grouped["gdacs_alert"]
            storms.append(composed)
        hashes = [str(item.get("payload_hash") or "") for item in children]
        latest_checked = max(str(item.get("last_checked_at") or "") for item in children)
        latest_changed = max(str(item.get("last_changed_at") or "") for item in children)
        retention_hours = DEFAULT_OPS_HISTORY_RETENTION_HOURS
        child_retention_hours = []
        for child in children:
            try:
                hours = int(child.get("ops_history_retention_hours"))
                if hours > 0:
                    child_retention_hours.append(hours)
            except Exception:
                pass
        if child_retention_hours:
            retention_hours = max(child_retention_hours)
        # Keep the collector archive retention long enough for investigation,
        # but the default Ops map/replay surface is intentionally the recent
        # operational window. Otherwise the page first paints the retained
        # 336h collector view and then immediately collapses to the 72h scrubber.
        display_hours = min(DEFAULT_OPS_HISTORY_DISPLAY_HOURS, retention_hours)
        payload_summary = {
            "logical_feed": HURRICANE_LIVE_FEED,
            "storm_count": len(storms),
            "source_count": len(children),
            "sources": [str(item.get("collector") or "") for item in children],
            "storms": storms,
        }
        return {
            "collector": HURRICANE_LIVE_FEED,
            "fetched_at": latest_checked,
            "last_checked_at": latest_checked,
            "last_changed_at": latest_changed,
            "collector_status": "ok" if storms else "quiet",
            "payload_summary": payload_summary,
            "payload_hash": hashlib.sha256("|".join(hashes).encode("utf-8")).hexdigest(),
            "schema_version": 1,
            "feed_type": "forecast",
            "ops_history_enabled": True,
            "ops_history_retention_hours": retention_hours,
            "ops_history_display_hours": min(display_hours, retention_hours),
            "ops_default_load": "history",
        }
    if collector == WILDFIRE_LIVE_FEED:
        if _composed_children is None:
            with ThreadPoolExecutor(max_workers=len(WILDFIRE_OPS_COLLECTORS)) as executor:
                children = list(executor.map(_load_snapshot_child_safely, WILDFIRE_OPS_COLLECTORS))
        else:
            children = _composed_children
        children = [item for item in children if isinstance(item, dict)]
        if not children:
            return None
        events = []
        for child in children:
            summary = child.get("payload_summary") if isinstance(child.get("payload_summary"), dict) else {}
            child_collector = str(child.get("collector") or "")
            events.extend(
                _wildfire_event_with_geography(item, child_collector)
                for item in (summary.get("events") or [])
                if isinstance(item, dict)
            )
        area_values = []
        for event in events:
            try:
                area_values.append(float(event.get("area_km2")))
            except (TypeError, ValueError):
                continue
        checked = max(str(item.get("last_checked_at") or "") for item in children)
        changed = max(str(item.get("last_changed_at") or "") for item in children)
        return {"collector": WILDFIRE_LIVE_FEED, "fetched_at": checked, "last_checked_at": checked,
                "last_changed_at": changed, "collector_status": "ok" if events else "quiet",
                "payload_summary": {"logical_feed": WILDFIRE_LIVE_FEED, "event_count": len(events), "active_count": len(events), "source_count": len(children), "max_area_km2": max(area_values) if area_values else None, "events": events},
                "payload_hash": hashlib.sha256("|".join(str(item.get("payload_hash") or "") for item in children).encode("utf-8")).hexdigest(),
                "schema_version": 1, "feed_type": "live_only", "ops_history_enabled": True,
                "ops_history_retention_hours": DEFAULT_OPS_HISTORY_RETENTION_HOURS,
                "ops_history_display_hours": DEFAULT_OPS_HISTORY_DISPLAY_HOURS, "ops_default_load": "snapshot"}
    cached = _get_live_state_cache(collector, "snapshot")
    if _is_live_state_snapshot(cached):
        _set_live_state_status(collector, "snapshot", "cache")
        return cached
    snapshot = (
        _fetch_live_state_via_site(collector, "snapshot")
        if collector == "usa_nws_alerts"
        else _read_json_object(f"{collector}/snapshot.json")
    )
    if _is_live_state_snapshot(snapshot):
        _set_live_state_cache(collector, "snapshot", snapshot)
        _set_live_state_status(
            collector,
            "snapshot",
            "railway_hot" if collector == "usa_nws_alerts" else "cloud",
        )
        return snapshot
    snapshot = (
        _read_json_object(f"{collector}/snapshot.json")
        if collector == "usa_nws_alerts"
        else _fetch_live_state_via_site(collector, "snapshot")
    )
    if _is_live_state_snapshot(snapshot):
        _set_live_state_cache(collector, "snapshot", snapshot)
        _set_live_state_status(collector, "snapshot", "site_fallback")
        return snapshot
    snapshot = _read_local_live_state_snapshot(collector)
    if _is_live_state_snapshot(snapshot):
        _set_live_state_cache(collector, "snapshot", snapshot)
        _set_live_state_status(collector, "snapshot", "local_fallback")
        return snapshot
    _set_live_state_status(
        collector,
        "snapshot",
        "cloud_unavailable" if _cloud_live_state_expected() else "cloud_not_configured",
    )
    return None


def _compose_logical_history(
    logical_feed: str,
    physical_collectors: tuple[str, ...],
    child_histories: list[list[dict]],
) -> list[dict]:
    """Reconstruct complete logical frames at each physical-child change.

    A raw union of child histories is not a valid map replay: it makes one
    child look like the entire wildfire/hurricane feed. Carry forward each
    healthy child's latest known snapshot, then run the same composition used
    for the current logical state.
    """
    changes: list[tuple[str, str, dict]] = []
    for collector, entries in zip(physical_collectors, child_histories):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            observed_at = str(
                entry.get("published_at")
                or entry.get("last_changed_at")
                or entry.get("upstream_issued_at")
                or ""
            ).strip()
            if observed_at:
                changes.append((observed_at, collector, entry))
    changes.sort(key=lambda item: item[0])

    latest_by_collector: dict[str, dict] = {}
    composed_entries: list[dict] = []
    previous_hash = ""
    for observed_at, collector, entry in changes:
        latest_by_collector[collector] = {
            **entry,
            # History entries are snapshots in compact form; retain their
            # physical identity so the normal logical composer can attribute
            # geography and authority correctly.
            "collector": str(entry.get("collector") or collector),
        }
        logical_snapshot = load_current_state_snapshot(
            logical_feed,
            _composed_children=list(latest_by_collector.values()),
        )
        if not isinstance(logical_snapshot, dict):
            continue
        payload_hash = str(logical_snapshot.get("payload_hash") or "")
        if payload_hash and payload_hash == previous_hash:
            continue
        previous_hash = payload_hash
        composed_entries.append({
            "collector": logical_feed,
            "published_at": observed_at,
            "last_changed_at": observed_at,
            "upstream_issued_at": logical_snapshot.get("upstream_issued_at"),
            "collector_status": logical_snapshot.get("collector_status"),
            "payload_hash": payload_hash,
            "payload_summary": logical_snapshot.get("payload_summary"),
            "schema_version": logical_snapshot.get("schema_version"),
            "feed_type": logical_snapshot.get("feed_type"),
            "ops_default_load": logical_snapshot.get("ops_default_load"),
        })
    return composed_entries


def load_current_state_history(collector_name: str, limit: int | None = None) -> list[dict]:
    collector = _normalize_ops_feed_id(collector_name)
    if not collector:
        return []
    if collector == HURRICANE_LIVE_FEED:
        # Fetch independently, then retain one authority-prioritized logical
        # storm state for each child change.
        with ThreadPoolExecutor(max_workers=len(HURRICANE_OPS_COLLECTORS)) as executor:
            child_histories = list(executor.map(_load_history_child_safely, HURRICANE_OPS_COLLECTORS))
        entries = _compose_logical_history(HURRICANE_LIVE_FEED, HURRICANE_OPS_COLLECTORS, child_histories)
        return entries[-limit:] if limit is not None and limit >= 0 else entries
    if collector == WILDFIRE_LIVE_FEED:
        with ThreadPoolExecutor(max_workers=len(WILDFIRE_OPS_COLLECTORS)) as executor:
            child_histories = list(executor.map(_load_history_child_safely, WILDFIRE_OPS_COLLECTORS))
        entries = _compose_logical_history(WILDFIRE_LIVE_FEED, WILDFIRE_OPS_COLLECTORS, child_histories)
        return entries[-limit:] if limit is not None and limit >= 0 else entries
    cached = _get_live_state_cache(collector, "history")
    if isinstance(cached, list):
        _set_live_state_status(collector, "history", "cache")
        entries = cached
    else:
        entries = (
            _fetch_live_state_via_site(collector, "history")
            if collector == "usa_nws_alerts"
            else _read_jsonl_object(f"{collector}/history.jsonl")
        )
        if isinstance(entries, list) and entries:
            _set_live_state_status(
                collector,
                "history",
                "railway_hot" if collector == "usa_nws_alerts" else "cloud",
            )
        else:
            entries = (
                _read_jsonl_object(f"{collector}/history.jsonl")
                if collector == "usa_nws_alerts"
                else _fetch_live_state_via_site(collector, "history")
            )
            if isinstance(entries, list) and entries:
                _set_live_state_status(collector, "history", "site_fallback")
    if not isinstance(entries, list):
        entries = []
    if isinstance(entries, list) and entries:
        _set_live_state_cache(collector, "history", entries)
    else:
        _set_live_state_status(
            collector,
            "history",
            "cloud_unavailable" if _cloud_live_state_expected() else "cloud_not_configured",
        )
    if limit is not None and limit >= 0:
        return entries[-limit:]
    return entries


def load_current_state_timeline_index(collector_name: str) -> dict | None:
    """Read compact cursor metadata without touching a retained raw archive."""
    collector = _normalize_ops_feed_id(collector_name)
    if not collector or not re.fullmatch(r"[A-Za-z0-9_-]+", collector):
        return None
    payload = (
        _fetch_live_state_via_site(collector, "timeline-index")
        if collector == "usa_nws_alerts"
        else _read_json_object(f"{collector}/timeline_index.json")
    )
    if collector == "usa_nws_alerts" and not isinstance(payload, dict):
        payload = _read_json_object(f"{collector}/timeline_index.json")
    if not isinstance(payload, dict) or not isinstance(payload.get("frames"), list):
        return None
    return payload


def load_current_state_timeline_frame(collector_name: str, frame_key: object) -> dict | None:
    """Read one independently published retained snapshot for an Ops cursor."""
    collector = _normalize_ops_feed_id(collector_name)
    key = str(frame_key or "").strip().replace("\\", "/")
    if (
        not collector
        or not re.fullmatch(r"[A-Za-z0-9_-]+", collector)
        or not re.fullmatch(r"timeline_frames/[a-f0-9]{64}\.json", key)
    ):
        return None
    if collector == "usa_nws_alerts":
        payload_hash = key.removeprefix("timeline_frames/").removesuffix(".json")
        payload = _fetch_live_state_via_site(collector, "frame", frame_hash=payload_hash)
        if isinstance(payload, dict):
            return payload
    return _read_json_object(f"{collector}/{key}")


def load_nws_recent_timeline_bundle() -> dict | None:
    """Load the VPS-compacted, bounded NWS playback projection."""
    cached = _get_live_state_cache("usa_nws_alerts", "timeline_bundle")
    if isinstance(cached, dict):
        return cached
    client = _build_object_store_client()
    if client is None or msgpack is None:
        return None
    try:
        key = f"{_live_state_prefix()}/usa_nws_alerts/recent_72h.msgpack.gz"
        raw = client.get_object(Bucket=_object_store_bucket(), Key=key)["Body"].read()
        payload = msgpack.unpackb(gzip.decompress(raw), raw=False)
    except Exception:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("intervals"), list):
        return None
    _set_live_state_cache("usa_nws_alerts", "timeline_bundle", payload)
    return payload


def load_aurora_frame_bundle() -> dict:
    """Load compact retained Aurora frames for the overlay's real-history loop."""
    cached = _get_live_state_cache("noaa_aurora", "frames")
    if isinstance(cached, dict):
        return cached
    raw = None
    client = _build_object_store_client()
    if client is not None:
        try:
            key = f"{_live_state_prefix()}/noaa_aurora/frames.json.gz"
            raw = client.get_object(Bucket=_object_store_bucket(), Key=key)["Body"].read()
        except Exception:
            raw = None
    if raw is None and str(get_runtime_config().get("runtime_mode", "local")).strip().lower() == "local":
        try:
            raw = (PRIVATE_ROOT / "live" / "state" / "noaa_aurora" / "frames.json.gz").read_bytes()
        except OSError:
            raw = None
    try:
        payload = json.loads(gzip.decompress(raw).decode("utf-8")) if raw else {}
    except (OSError, ValueError, TypeError):
        payload = {}
    result = payload if isinstance(payload, dict) else {}
    _set_live_state_cache("noaa_aurora", "frames", result)
    return result


def _snapshot_to_geojson(snapshot: dict) -> dict | None:
    if not isinstance(snapshot, dict):
        return None
    collector = str(snapshot.get("collector") or "").strip()
    summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
    if collector != "earthquakes":
        return None
    events = summary.get("events") or []
    features = []
    for event in events:
        try:
            lon = float(event.get("longitude"))
            lat = float(event.get("latitude"))
        except (TypeError, ValueError):
            continue
        props = {
            "event_id": event.get("event_id"),
            "timestamp": event.get("timestamp"),
            "magnitude": event.get("magnitude"),
            "depth_km": event.get("depth_km"),
            "place": event.get("place"),
            "source": event.get("source"),
            "collector": collector,
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )
    if not features:
        return None
    return {"type": "FeatureCollection", "features": features}


def _simplify_wildfire_perimeter_geometry(geometry: dict, *, max_positions: int) -> dict:
    """Decimate perimeter rings deterministically for an interactive map.

    This is deliberately not an area calculation or an attempt to improve the
    source geometry.  It simply preserves a closed, representative outline at
    the zoom level where an Ops overview is useful.
    """
    if max_positions < 8:
        return geometry
    geometry_type = str(geometry.get("type") or "")
    coordinates = geometry.get("coordinates")
    polygons = coordinates if geometry_type == "MultiPolygon" else [coordinates]
    if not isinstance(polygons, list):
        return geometry
    total_positions = sum(
        len(ring)
        for polygon in polygons if isinstance(polygon, list)
        for ring in polygon if isinstance(ring, list)
    )
    if total_positions <= max_positions:
        return geometry

    def compact_ring(ring: list, budget: int) -> list:
        closed = len(ring) >= 2 and ring[0] == ring[-1]
        points = ring[:-1] if closed else ring[:]
        if len(points) <= max(3, budget - 1):
            result = points[:]
        else:
            keep = max(3, budget - 1)
            result = [points[min(len(points) - 1, int(index * len(points) / keep))] for index in range(keep)]
        if result and (closed or len(result) >= 3):
            result.append(result[0])
        return result

    # Source multipolygons can carry thousands of tiny islands/holes. A
    # per-ring cap is not a payload cap in that case. For the overview keep
    # the largest exterior rings only; the detailed source geometry remains
    # available in the current artifact and event drill-down path.
    exterior_rings = [
        (index, polygon[0])
        for index, polygon in enumerate(polygons)
        if isinstance(polygon, list) and polygon and isinstance(polygon[0], list) and len(polygon[0]) >= 4
    ]
    if not exterior_rings:
        return geometry
    max_rings = max(1, max_positions // 4)
    selected_indexes = {
        index for index, _ring in sorted(exterior_rings, key=lambda item: len(item[1]), reverse=True)[:max_rings]
    }
    selected_total = sum(len(ring) for index, ring in exterior_rings if index in selected_indexes)
    simplified_polygons = []
    for index, polygon in enumerate(polygons):
        if index not in selected_indexes:
            continue
        ring = polygon[0]
        budget = max(4, round(max_positions * len(ring) / max(selected_total, 1)))
        simplified_rings = [compact_ring(ring, budget)]
        simplified_polygons.append(simplified_rings)
    return {
        **geometry,
        "coordinates": simplified_polygons if geometry_type == "MultiPolygon" else simplified_polygons[0],
    }


def _wildfire_perimeter_geometry(row: dict, *, max_positions: int | None = None) -> dict | None:
    """Return a valid perimeter geometry when a live collector supplied one."""
    perimeter = row.get("perimeter")
    if isinstance(perimeter, str):
        try:
            perimeter = json.loads(perimeter)
        except (TypeError, ValueError):
            return None
    if not isinstance(perimeter, dict):
        return None
    geometry = perimeter.get("geometry") if perimeter.get("type") == "Feature" else perimeter
    if str(geometry.get("type") or "") not in {"Polygon", "MultiPolygon"}:
        return None
    if not geometry.get("coordinates"):
        return None
    if max_positions is not None:
        return _simplify_wildfire_perimeter_geometry(geometry, max_positions=max_positions)
    return geometry


def _build_point_event_display_payload(
    snapshot: dict | None,
    *,
    collector: str,
    event_type: str,
    label: str,
    minimum_area_km2: float | None = None,
    perimeter_minimum_area_km2: float | None = None,
) -> dict | None:
    if not isinstance(snapshot, dict):
        return None
    summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
    rows = summary.get("events") if isinstance(summary.get("events"), list) else None
    if not rows:
        return None

    features: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        props = dict(row)
        props.setdefault("collector", collector)
        if collector == "volcanoes":
            props.setdefault("VEI", row.get("vei"))
        if collector == WILDFIRE_LIVE_FEED:
            acres = row.get("burned_acres")
            try:
                props.setdefault("area_km2", float(acres) * 0.00404686)
            except (TypeError, ValueError):
                pass
        wildfire_area_km2 = None
        if collector == WILDFIRE_LIVE_FEED:
            try:
                wildfire_area_km2 = float(props.get("area_km2"))
            except (TypeError, ValueError):
                wildfire_area_km2 = None
            if minimum_area_km2 is not None and (wildfire_area_km2 is None or wildfire_area_km2 < minimum_area_km2):
                continue
        include_perimeter = (
            collector == WILDFIRE_LIVE_FEED
            and perimeter_minimum_area_km2 is not None
            and wildfire_area_km2 is not None
            and wildfire_area_km2 >= perimeter_minimum_area_km2
        )
        geometry = (
            _wildfire_perimeter_geometry(row, max_positions=WILDFIRE_MAP_MAX_PERIMETER_POSITIONS)
            if include_perimeter else None
        )
        # Perimeters are either promoted to bounded feature geometry above or
        # fetched through the viewport detail endpoint. Keeping the original
        # polygon JSON in properties duplicates megabytes of coordinates in
        # the ordinary point-marker response.
        if collector == WILDFIRE_LIVE_FEED:
            props.pop("perimeter", None)
        if geometry is None:
            try:
                lon = float(row.get("longitude"))
                lat = float(row.get("latitude"))
            except (TypeError, ValueError):
                continue
            geometry = {"type": "Point", "coordinates": [lon, lat]}
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": props,
            }
        )

    if not features:
        return None

    count = len(features)
    return {
        "type": "events",
        "data_type": "events",
        "event_type": event_type,
        "source_id": f"{collector}_live_ops",
        "snapshot_hash": snapshot.get("payload_hash"),
        "dataset_name": label,
        "source_name": label,
        "summary": f"Showing latest {label.lower()} snapshot ({count} items).",
        "count": count,
        "fit": False,
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
    }


def _build_wildfire_display_payload(
    snapshot: dict | None,
    *,
    minimum_area_km2: float = WILDFIRE_DEFAULT_MIN_AREA_KM2,
    perimeter_minimum_area_km2: float | None = None,
) -> dict | None:
    """Build a bounded overview payload without discarding the full snapshot.

    Default Ops loading is a readability view.  Explicit chat filters may ask
    for every current incident; in that case small fires remain renderable as
    source-coordinate markers while only map-scale fires carry a simplified
    perimeter.
    """
    payload = _build_point_event_display_payload(
        snapshot,
        collector=WILDFIRE_LIVE_FEED,
        event_type="wildfire",
        label="Ops Wildfire Snapshot",
        minimum_area_km2=minimum_area_km2,
        # The initial Ops overview is marker-only. Perimeters are a separate
        # viewport detail request once the operator zooms in far enough for
        # their shape to be useful.
        perimeter_minimum_area_km2=perimeter_minimum_area_km2,
    )
    if payload:
        payload["ops_min_area_km2"] = minimum_area_km2
        payload["ops_show_all"] = minimum_area_km2 <= 0
        payload["ops_perimeter_min_area_km2"] = perimeter_minimum_area_km2
    return payload


def _build_live_hurricane_display_payload(
    snapshot: dict | None,
    *,
    as_of: datetime | None = None,
) -> dict | None:
    """Build one display payload from the merged live advisory collectors.

    ``as_of`` makes retained replay answer the cursor's time rather than the
    server's wall clock.  That keeps a trail additive between advisory fixes:
    the last known position remains current until a newer one arrives.
    """
    if not isinstance(snapshot, dict):
        return None
    summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
    storms = summary.get("storms") if isinstance(summary.get("storms"), list) else []
    features = []
    storm_ids = set()
    now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    history_hours = _ops_history_display_hours_for_snapshot(snapshot)
    history_cutoff = now - timedelta(hours=max(history_hours, 1))

    def source_key(storm: dict) -> str:
        return str(storm.get("source") or "").strip().upper()

    def source_page_url(storm: dict) -> str | None:
        explicit = str(storm.get("source_page_url") or "").strip()
        if explicit:
            return explicit
        return HURRICANE_SOURCE_PAGES.get(source_key(storm))

    def source_label(storm: dict) -> str:
        key = source_key(storm)
        return (
            HURRICANE_SOURCE_LABELS.get(key)
            or str(storm.get("source_name") or storm.get("source") or "").strip()
            or "Tropical cyclone advisory source"
        )

    def numeric_value(*values) -> float | None:
        for value in values:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                return parsed
        return None

    def category_from_wind(wind_kt: float | None) -> str | None:
        if wind_kt is None:
            return None
        if wind_kt >= 137:
            return "Cat5"
        if wind_kt >= 113:
            return "Cat4"
        if wind_kt >= 96:
            return "Cat3"
        if wind_kt >= 83:
            return "Cat2"
        if wind_kt >= 64:
            return "Cat1"
        if wind_kt >= 34:
            return "TS"
        return "TD"

    def point_time(point: dict | None, *fallbacks: object) -> datetime | None:
        if not isinstance(point, dict):
            for fallback in fallbacks:
                parsed = _parse_iso_datetime(fallback)
                if parsed is not None:
                    return parsed
            return None
        for key in ("timestamp", "valid_at", "time", "issued_at"):
            parsed = _parse_iso_datetime(point.get(key))
            if parsed is not None:
                return parsed
        for fallback in fallbacks:
            parsed = _parse_iso_datetime(fallback)
            if parsed is not None:
                return parsed
        return None

    def forecast_horizon_cutoff(storm: dict) -> datetime:
        try:
            hours = int(storm.get("forecast_horizon_hours") or 120)
        except Exception:
            hours = 120
        return now + timedelta(hours=max(hours, 1))

    def point_coord(storm: dict, point: dict) -> list[float] | None:
        try:
            longitude = float(point.get("longitude"))
            latitude = float(point.get("latitude"))
        except (TypeError, ValueError):
            return None
        # NHC source positions are west-longitude for the Atlantic and east/
        # central Pacific basins. Older retained NHC snapshots were parsed by
        # a numeric-only reader and lost the `W` suffix (for example Fausto
        # 151.7W became +151.7). Repair that known legacy shape at display time
        # so the current view and every retained replay frame stay coherent
        # while corrected collector snapshots replace the old rows.
        if source_key(storm) == "NHC" and 0.0 < longitude <= 180.0:
            longitude = -longitude
        if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
            return None
        return [longitude, latitude]

    def distance_km(first: list[float], second: list[float]) -> float:
        lon1, lat1 = map(math.radians, first)
        lon2, lat2 = map(math.radians, second)
        a = (
            math.sin((lat2 - lat1) / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        )
        return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(a)))

    def normalized_coord_pair(storm: dict, raw_coord: object) -> list[float] | None:
        if not isinstance(raw_coord, (list, tuple)) or len(raw_coord) < 2:
            return None
        return point_coord(storm, {"longitude": raw_coord[0], "latitude": raw_coord[1]})

    for storm in storms:
        if not isinstance(storm, dict):
            continue
        storm_id = str(storm.get("storm_id") or "").strip()
        if not storm_id:
            continue
        current = storm.get("current_position") if isinstance(storm.get("current_position"), dict) else {}
        future_cutoff = forecast_horizon_cutoff(storm)
        observed_points = [
            point for point in (storm.get("observed_track") or [])
            if (
                isinstance(point, dict)
                and (observed_time := point_time(point, storm.get("issued_at"))) is not None
                and history_cutoff <= observed_time <= now
            )
        ]
        observed_points.sort(key=lambda point: point_time(point, storm.get("issued_at")) or datetime.min.replace(tzinfo=timezone.utc))
        forecast_points = [
            point for point in (storm.get("forecast_points") or [])
            if (
                isinstance(point, dict)
                and (forecast_time := point_time(point, storm.get("issued_at"))) is not None
                and now <= forecast_time <= future_cutoff
            )
        ]
        wind_candidates = [
            numeric_value(storm.get("max_wind_kt"), storm.get("wind_kt"), current.get("wind_kt"))
        ]
        wind_candidates.extend(
            numeric_value(point.get("wind_kt"))
            for point in observed_points
        )
        wind_candidates.extend(
            numeric_value(point.get("wind_kt"))
            for point in forecast_points
        )
        max_wind_kt = max(
            [value for value in wind_candidates if value is not None],
            default=None,
        )
        current_wind_kt = numeric_value(current.get("wind_kt"), storm.get("wind_kt"), max_wind_kt)
        category = (
            storm.get("category")
            or storm.get("max_category")
            or category_from_wind(max_wind_kt)
            or category_from_wind(current_wind_kt)
        )
        product_url = str(storm.get("source_product_url") or storm.get("source_url") or "").strip() or None
        page_url = source_page_url(storm)
        base_props = {
            "storm_id": storm_id,
            "storm_color": _hurricane_storm_color(storm_id),
            "name": storm.get("name"),
            "basin": storm.get("basin"),
            "source": storm.get("source"),
            "selected_observed_source": storm.get("selected_observed_source"),
            "selected_forecast_source": storm.get("selected_forecast_source"),
            "source_name": source_label(storm),
            "source_url": page_url or product_url,
            "source_page_url": page_url,
            "source_product_url": product_url,
            "advisory_number": storm.get("advisory_number"),
            "issued_at": storm.get("issued_at"),
            "wind_kt": current_wind_kt,
            "max_wind_kt": max_wind_kt,
            "category": category,
            "max_category": category,
            "event_type": "hurricane",
        }
        observed = []
        observed_times = []
        for point in observed_points:
            coord = point_coord(storm, point)
            observed_at = point_time(point, storm.get("issued_at"))
            if not coord or observed_at is None:
                continue
            if observed and observed_times:
                prior_at = observed_times[-1]
                elapsed_hours = max(0.0, (observed_at - prior_at).total_seconds() / 3600.0) if prior_at else 0.0
                # A real tropical cyclone cannot cross an ocean basin between
                # two advisory fixes.  Keep generous room for fast motion and
                # sparse reports, but reject a malformed longitude/latitude
                # before it turns one bad row into a map-spanning line.
                allowed_km = 500.0 + (300.0 * elapsed_hours)
                if elapsed_hours > 0 and distance_km(observed[-1], coord) > allowed_km:
                    logger.warning("ops hurricane: dropped implausible track jump storm=%s at=%s", storm_id, observed_at.isoformat())
                    continue
            if observed and observed[-1] == coord:
                continue
            observed.append(coord)
            observed_times.append(observed_at)
        current_time = point_time(current, storm.get("issued_at"))
        current_in_history_window = current_time is not None and history_cutoff <= current_time <= now
        current_coord = point_coord(storm, current) if current_in_history_window else None
        latest_observed_time = max(
            [value for value in observed_times if value is not None],
            default=None,
        )
        current_is_latest_observed = (
            current_time is not None
            and (latest_observed_time is None or current_time >= latest_observed_time)
        )
        if current_coord and current_is_latest_observed and (not observed or observed[-1] != current_coord):
            observed.append(current_coord)
        last_observed_time = max(
            [value for value in [*observed_times, current_time] if value is not None],
            default=None,
        )
        age_hours = max(0.0, (now - last_observed_time).total_seconds() / 3600.0) if last_observed_time else None
        # A forecast belongs to an active advisory, not merely to a recently
        # received position.  Agencies can leave a final position fresh while
        # explicitly closing the advisory; that terminal timestamp must win
        # so a completed storm never keeps a stale forecast on the live map.
        advisory_ended_at = _parse_iso_datetime(storm.get("valid_through"))
        advisory_has_ended = bool(advisory_ended_at is not None and advisory_ended_at < now)
        is_active = bool(
            age_hours is not None
            and age_hours <= HURRICANE_ACTIVE_FIX_MAX_AGE_HOURS
            and not storm.get("retained_history_only")
            and not advisory_has_ended
        )
        # Ended/recently inactive storms remain useful in Ops history, but take
        # an immediate readability drop before slowly fading through retention.
        if is_active:
            track_opacity = 0.95
        else:
            fade_age = max(0.0, (age_hours or HURRICANE_ACTIVE_FIX_MAX_AGE_HOURS) - HURRICANE_ACTIVE_FIX_MAX_AGE_HOURS)
            retention_hours = max(1.0, (now - history_cutoff).total_seconds() / 3600.0)
            track_opacity = max(0.10, 0.65 * (1.0 - min(0.82, fade_age / retention_hours)))
        base_props.update({
            "track_state": "active" if is_active else "ended_recent",
            "track_opacity": round(track_opacity, 3),
            "last_observed_at": last_observed_time.isoformat() if last_observed_time else None,
            "advisory_ended_at": advisory_ended_at.isoformat() if advisory_ended_at else None,
            "source_priority": _hurricane_source_priority_for_storm(storm),
        })
        forecast_pairs = [
            (coord, forecast_at)
            for point in forecast_points
            if (coord := point_coord(storm, point)) is not None
            and (forecast_at := point_time(point, storm.get("issued_at"))) is not None
        ]
        forecast_coords = [coord for coord, _ in forecast_pairs]
        if not forecast_coords:
            raw_track = storm.get("forecast_track") if isinstance(storm.get("forecast_track"), dict) else {}
            raw_coords = raw_track.get("coordinates") if raw_track.get("type") == "LineString" else []
            forecast_coords = [coord for coord in (normalized_coord_pair(storm, raw_coord) for raw_coord in raw_coords) if coord]
        if not observed and not current_coord and not forecast_coords:
            continue
        storm_ids.add(storm_id)
        if len(observed) >= 2:
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": observed},
                "properties": {
                    **base_props,
                    "track_kind": "observed",
                    "line_style": "solid",
                },
            })
        if current_coord:
            current_properties = dict(current)
            current_properties["longitude"] = current_coord[0]
            current_properties["latitude"] = current_coord[1]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": current_coord},
                "properties": {
                    **base_props,
                    **current_properties,
                    "track_kind": "current",
                },
            })
        if is_active and forecast_coords:
            coords = forecast_coords
            forecast_times = [stamp for _, stamp in forecast_pairs]
            if current_coord and (not coords or coords[0] != current_coord):
                coords = [current_coord, *coords]
                # The source current fix is the honest first forecast anchor.
                # Preserve its time so the browser can reveal only the
                # source-issued dotted segments that are valid at its cursor.
                forecast_times = [current_time, *forecast_times]
            if len(coords) >= 2:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        **base_props,
                        "track_kind": "forecast",
                        "line_style": "dotted",
                        "forecast_timestamps": [
                            stamp.isoformat() if stamp is not None else None
                            for stamp in forecast_times
                        ],
                    },
                })
        uncertainty = storm.get("uncertainty_geometry")
        if is_active and forecast_coords and isinstance(uncertainty, dict) and uncertainty.get("type") in {"Polygon", "MultiPolygon"}:
            features.append({
                "type": "Feature",
                "geometry": uncertainty,
                "properties": {
                    **base_props,
                    "track_kind": "forecast_uncertainty",
                },
            })
    if not features:
        return None
    forecast_times = [
        _parse_iso_datetime(stamp)
        for feature in features
        if isinstance(feature, dict)
        and isinstance(feature.get("properties"), dict)
        and feature["properties"].get("track_kind") == "forecast"
        for stamp in (feature["properties"].get("forecast_timestamps") or [])
    ]
    forecast_times = [stamp for stamp in forecast_times if stamp is not None]
    return {
        "type": "data",
        "data_type": "events",
        "event_type": "hurricane",
        "source_id": "hurricanes_live_ops",
        "snapshot_hash": snapshot.get("payload_hash"),
        "dataset_name": "Hurricanes",
        "source_name": "Tropical cyclone advisory sources",
        "summary": f"Showing {len(storm_ids)} active storms from advisory sources.",
        "count": len(storm_ids),
        "fit": False,
        "forecast_end_at": max(forecast_times).isoformat() if forecast_times else None,
        "geojson": {"type": "FeatureCollection", "features": features},
    }


def _sample_rows(rows: list[dict], fields: tuple[str, ...], limit: int) -> list[dict]:
    sampled: list[dict] = []
    for row in (rows or [])[:limit]:
        if not isinstance(row, dict):
            continue
        sampled.append({field: row.get(field) for field in fields if field in row})
    return sampled


@lru_cache(maxsize=1)
def _load_country_currency_map() -> list[dict]:
    rows: list[dict] = []
    if not CURRENCY_MAP_PATH.exists():
        return rows
    try:
        with open(CURRENCY_MAP_PATH, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not isinstance(row, dict):
                    continue
                loc_id = str(row.get("loc_id") or "").strip()
                currency_code = str(row.get("currency_code") or "").strip().upper()
                if not loc_id or not currency_code:
                    continue
                rows.append(
                    {
                        "loc_id": loc_id,
                        "currency_code": currency_code,
                    }
                )
    except Exception:
        return []
    return rows


def _build_currency_display_payload(snapshot: dict | None) -> dict | None:
    if not isinstance(snapshot, dict):
        return None
    summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
    rates = summary.get("rates") if isinstance(summary.get("rates"), list) else []
    if not rates:
        return None

    latest_by_code: dict[str, dict] = {}
    for rate in rates:
        if not isinstance(rate, dict):
            continue
        code = str(rate.get("currency_code") or "").strip().upper()
        if not code:
            continue
        latest_by_code[code] = rate

    loc_ids: list[str] = []
    rows_by_loc_id: dict[str, dict] = {}
    for mapping in _load_country_currency_map():
        loc_id = str(mapping.get("loc_id") or "").strip()
        code = str(mapping.get("currency_code") or "").strip().upper()
        rate = latest_by_code.get(code)
        if not loc_id or rate is None:
            continue
        try:
            local_per_usd = float(rate.get("local_per_usd"))
        except (TypeError, ValueError):
            continue
        rows_by_loc_id[loc_id] = {
            "loc_id": loc_id,
            "local_per_usd": local_per_usd,
            "currency_code": code,
            "date": rate.get("date"),
            "source_id": rate.get("source_id"),
        }
        loc_ids.append(loc_id)

    if not rows_by_loc_id:
        return None

    selection_geojson = get_selection_geometries(loc_ids) or {}
    features = []
    year_bucket: dict[str, dict] = {}
    for feature in selection_geojson.get("features") or []:
        if not isinstance(feature, dict):
            continue
        props = dict(feature.get("properties") or {})
        loc_id = str(props.get("loc_id") or "").strip()
        row = rows_by_loc_id.get(loc_id)
        if row is None:
            continue
        metric_props = {
            **props,
            "local_per_usd": row.get("local_per_usd"),
            "currency_code": row.get("currency_code"),
            "date": row.get("date"),
            "source_id": row.get("source_id"),
        }
        features.append(
            {
                "type": "Feature",
                "geometry": feature.get("geometry"),
                "properties": metric_props,
            }
        )
        year_bucket[loc_id] = {
            "local_per_usd": row.get("local_per_usd"),
            "currency_code": row.get("currency_code"),
            "date": row.get("date"),
            "source_id": row.get("source_id"),
        }

    if not features:
        return None

    return {
        "type": "data",
        "data_type": "metrics",
        "source_id": "currency_live_ops",
        "snapshot_hash": snapshot.get("payload_hash"),
        "dataset_name": "Ops Currency Snapshot",
        "source_name": "Live currency snapshot",
        "geographic_level": "admin_0",
        "summary": f"Showing latest FX snapshot for {len(features)} countries.",
        "count": len(features),
        "fit": False,
        "metric_key": "local_per_usd",
        "available_metrics": ["local_per_usd"],
        "loc_ids": sorted(year_bucket.keys()),
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
    }


def _default_history_window_entries(*, snapshot: dict, history_entries: list[dict]) -> tuple[list[dict], str]:
    hours = _ops_history_display_hours_for_snapshot(snapshot)
    cutoff = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=max(hours, 1))
    timeline: list[dict] = []
    if isinstance(snapshot, dict):
        timeline.append(snapshot)
    timeline.extend(entry for entry in history_entries if isinstance(entry, dict))
    in_window = []
    for entry in timeline:
        observed_at = _history_observed_at(entry)
        if observed_at is None or observed_at < cutoff:
            continue
        in_window.append(entry)
    return in_window, f"the default Ops display window ({hours}h)"


def _ops_default_load_mode(snapshot: dict | None) -> str:
    if not isinstance(snapshot, dict):
        return OPS_DEFAULT_LOAD_SNAPSHOT
    raw = str(snapshot.get("ops_default_load") or "").strip().lower()
    if raw in OPS_DEFAULT_LOAD_VALUES:
        return raw
    return OPS_DEFAULT_LOAD_SNAPSHOT


def _with_hurricane_history_tracks(snapshot: dict, entries: list[dict]) -> dict:
    summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
    storms = [dict(item) for item in summary.get("storms") or [] if isinstance(item, dict)]
    positions: dict[str, dict[str, dict]] = {}
    source_priority_by_storm: dict[str, int] = {}

    def identity_keys(storm: dict) -> set[str]:
        identity = storm.get("identity") if isinstance(storm.get("identity"), dict) else {}
        canonical = str(identity.get("canonical_id") or storm.get("storm_id") or "").strip().lower()
        name = re.sub(
            r"[-_\s]?\d{2,4}$",
            "",
            str(storm.get("name") or "").strip(),
        ).strip().lower()
        year = str(storm.get("year") or "")[:4]
        return {value for value in (canonical, f"{name}:{year}" if name else "") if value}

    current_by_key = {}

    def register_storm(storm: dict, *, retained_only: bool = False, append_if_new: bool = True) -> dict | None:
        storm_id = str(storm.get("storm_id") or "").strip()
        if not storm_id:
            return None
        target = next(
            (current_by_key.get(key) for key in identity_keys(storm) if current_by_key.get(key)),
            None,
        )
        source_priority = _hurricane_source_priority_for_storm(storm)
        if target is None:
            target = dict(storm)
            if retained_only:
                target["retained_history_only"] = True
            if append_if_new:
                storms.append(target)
        else:
            target_id = str(target.get("storm_id") or storm_id)
            existing_priority = source_priority_by_storm.get(target_id, 0)
            if source_priority > existing_priority:
                for field in (
                    "name", "basin", "source", "source_url", "advisory_number",
                    "issued_at", "forecast_track", "forecast_points",
                    "uncertainty_geometry", "identity",
                ):
                    if storm.get(field) not in (None, "", []):
                        target[field] = storm.get(field)
        target_id = str(target.get("storm_id") or storm_id)
        source_priority_by_storm[target_id] = max(
            source_priority_by_storm.get(target_id, 0),
            source_priority,
        )
        for key in identity_keys(target) | identity_keys(storm):
            current_by_key[key] = target
        return target

    def add_position(target: dict, point: dict | None, *, source: str | None = None, fallback_timestamp: str | None = None) -> None:
        if not isinstance(point, dict):
            return
        candidate_source = str(source or "").strip().upper()
        # GDACS is impact/alert context, not a warning centre. Its collector
        # timestamps the last supplied storm location with every alert poll,
        # which can replay one old fix hundreds of times and turn retained
        # history into a false fan of lines. Keep its alert metadata, but let
        # only advisory agencies contribute the observed track/current point.
        if candidate_source == "GDACS":
            return
        timestamp = str(point.get("timestamp") or fallback_timestamp or "").strip()
        if not timestamp:
            return
        observed_at = _parse_iso_datetime(timestamp)
        if observed_at is None:
            return
        try:
            latitude = float(point.get("latitude"))
            longitude = float(point.get("longitude"))
        except (TypeError, ValueError):
            return
        # Preserve the NHC longitude repair at the point's actual provenance,
        # not only at the eventual composed-storm record. A retained storm can
        # start from a fallback authority and later receive NHC positions; if
        # the legacy NHC row lost its W suffix, using target.source below
        # would fail to repair it and create a world-spanning join.
        if candidate_source == "NHC" and 0.0 < longitude <= 180.0:
            longitude = -longitude
        if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
            return
        storm_id = str(target.get("storm_id") or "").strip()
        if not storm_id:
            return
        # One source-owned fix per three-hour slot.  This keeps the primary
        # warning centre's geometry coherent while allowing an overlapping
        # source to fill an actual gap instead of producing parallel/fan
        # tracks from every collector poll.
        slot_hour = (observed_at.hour // HURRICANE_TRACK_SLOT_HOURS) * HURRICANE_TRACK_SLOT_HOURS
        slot_at = observed_at.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
        slot_key = slot_at.isoformat()
        storm_positions = positions.setdefault(storm_id, {})
        priority = _hurricane_source_priority_for_storm(target, source)
        existing = storm_positions.get(slot_key)
        existing_priority = int(existing.get("_source_priority") or 0) if existing else -1
        existing_timestamp = _parse_iso_datetime(existing.get("timestamp")) if existing else None
        # Basin authority wins an overlap; the later same-source fix is the
        # most accurate representative for its slot.
        if existing and (
            existing_priority > priority
            or (existing_priority == priority and existing_timestamp is not None and existing_timestamp >= observed_at)
        ):
            return
        storm_positions[slot_key] = {
            **point,
            "timestamp": timestamp,
            "latitude": latitude,
            "longitude": longitude,
            "_source_priority": priority,
        }

    for storm in storms:
        target = register_storm(storm, append_if_new=False)
        if target is None:
            continue
        for point in storm.get("observed_track") or []:
            if isinstance(point, dict):
                add_position(
                    target,
                    point,
                    source=str(storm.get("source") or ""),
                    fallback_timestamp=str(point.get("timestamp") or storm.get("issued_at") or ""),
                )
        add_position(
            target,
            storm.get("current_position") if isinstance(storm.get("current_position"), dict) else None,
            source=str(storm.get("source") or ""),
            fallback_timestamp=str(storm.get("issued_at") or ""),
        )

    for entry in entries:
        entry_summary = entry.get("payload_summary") if isinstance(entry.get("payload_summary"), dict) else {}
        for historical in entry_summary.get("storms") or []:
            if not isinstance(historical, dict):
                continue
            target = next(
                (current_by_key.get(key) for key in identity_keys(historical) if current_by_key.get(key)),
                None,
            )
            if target is None:
                # A GDACS alert is not enough to establish a retained track.
                # If a warning-centre record for the storm exists it will
                # create the display event; the raw GDACS history remains
                # retained by its collector for alert/impact research.
                if str(historical.get("source") or "").strip().upper() == "GDACS":
                    continue
                target = register_storm(historical, retained_only=True)
            if target is None:
                continue
            for point in historical.get("observed_track") or []:
                if isinstance(point, dict):
                    add_position(
                        target,
                        point,
                        source=str(historical.get("source") or ""),
                        fallback_timestamp=str(point.get("timestamp") or historical.get("issued_at") or ""),
                    )
            add_position(
                target,
                historical.get("current_position") if isinstance(historical.get("current_position"), dict) else None,
                source=str(historical.get("source") or ""),
                fallback_timestamp=str(historical.get("issued_at") or ""),
            )

    for storm in storms:
        storm_positions = positions.get(str(storm.get("storm_id")), {})
        if storm_positions:
            sorted_position_keys = sorted(storm_positions)
            storm["observed_track"] = [
                {
                    field: value
                    for field, value in storm_positions[key].items()
                    if field != "_source_priority"
                }
                for key in sorted_position_keys
            ]
            if storm.get("retained_history_only") or not isinstance(storm.get("current_position"), dict):
                latest_key = sorted_position_keys[-1]
                storm["current_position"] = {
                    field: value
                    for field, value in storm_positions[latest_key].items()
                    if field != "_source_priority"
                }
    return {
        **snapshot,
        "payload_summary": {
            **summary,
            "storms": storms,
        },
    }


def _build_hurricane_replay_payload(
    snapshot: dict | None,
    entries: list[dict],
    *,
    as_of: datetime,
    history_hours: int,
) -> dict | None:
    """Return bounded storm track records for browser-side Ops replay."""
    if not isinstance(snapshot, dict):
        return None
    composed = _with_hurricane_history_tracks(snapshot, entries)
    summary = composed.get("payload_summary") if isinstance(composed.get("payload_summary"), dict) else {}
    cutoff = as_of - timedelta(hours=max(1, int(history_hours)))
    storms = []
    for storm in summary.get("storms") or []:
        if not isinstance(storm, dict):
            continue
        storm_id = str(storm.get("storm_id") or "").strip()
        if not storm_id:
            continue
        points = []
        for point in storm.get("observed_track") or []:
            if not isinstance(point, dict):
                continue
            observed_at = _parse_iso_datetime(point.get("timestamp"))
            if observed_at is None or observed_at < cutoff or observed_at > as_of:
                continue
            try:
                latitude = float(point.get("latitude"))
                longitude = float(point.get("longitude"))
            except (TypeError, ValueError):
                continue
            points.append({
                "timestamp": observed_at.isoformat(),
                "latitude": latitude,
                "longitude": longitude,
                "wind_kt": point.get("wind_kt"),
                "pressure_mb": point.get("pressure_mb"),
                "category": point.get("category"),
                "status": point.get("status"),
                "r34_ne": point.get("r34_ne"),
                "r34_se": point.get("r34_se"),
                "r34_sw": point.get("r34_sw"),
                "r34_nw": point.get("r34_nw"),
                "r50_ne": point.get("r50_ne"),
                "r50_se": point.get("r50_se"),
                "r50_sw": point.get("r50_sw"),
                "r50_nw": point.get("r50_nw"),
                "r64_ne": point.get("r64_ne"),
                "r64_se": point.get("r64_se"),
                "r64_sw": point.get("r64_sw"),
                "r64_nw": point.get("r64_nw"),
            })
        points.sort(key=lambda item: item["timestamp"])
        if not points:
            continue
        storms.append({
            "storm_id": storm_id,
            "name": storm.get("name"),
            "basin": storm.get("basin"),
            "source": storm.get("source"),
            "storm_color": _hurricane_storm_color(storm_id),
            "source_name": storm.get("source_name"),
            "source_url": storm.get("source_url"),
            "source_page_url": storm.get("source_page_url"),
            "source_product_url": storm.get("source_product_url"),
            "advisory_number": storm.get("advisory_number"),
            "issued_at": storm.get("issued_at"),
            "valid_through": storm.get("valid_through"),
            "current_position": storm.get("current_position") if isinstance(storm.get("current_position"), dict) else None,
            "forecast_horizon_hours": storm.get("forecast_horizon_hours"),
            "forecast_points": storm.get("forecast_points") if isinstance(storm.get("forecast_points"), list) else [],
            "forecast_track": storm.get("forecast_track") if isinstance(storm.get("forecast_track"), dict) else None,
            "uncertainty_geometry": storm.get("uncertainty_geometry") if isinstance(storm.get("uncertainty_geometry"), dict) else None,
            "selected_observed_source": storm.get("selected_observed_source"),
            "selected_forecast_source": storm.get("selected_forecast_source"),
            "observed_track": points,
        })
    if not storms:
        return None
    return {
        "type": "hurricane_replay",
        "history_hours": history_hours,
        "range_end": as_of.isoformat(),
        "storms": storms,
    }


def _hurricane_replay_cursor_times(replay_payload: dict | None, *, range_start: datetime, now: datetime) -> list[datetime]:
    """Return cursor anchors from bounded storm records, not display frames."""
    if not isinstance(replay_payload, dict):
        return []
    times: set[datetime] = {range_start, now}
    for storm in replay_payload.get("storms") or []:
        if not isinstance(storm, dict):
            continue
        for point in [*(storm.get("observed_track") or []), *(storm.get("forecast_points") or [])]:
            if not isinstance(point, dict):
                continue
            parsed = (
                _parse_iso_datetime(point.get("timestamp"))
                or _parse_iso_datetime(point.get("valid_at"))
                or _parse_iso_datetime(point.get("time"))
                or _parse_iso_datetime(point.get("issued_at"))
            )
            if parsed is not None and parsed >= range_start:
                times.add(parsed)
    return sorted(times)


def _build_default_history_payload(*, feed: str, snapshot: dict, history_entries: list[dict]) -> dict | None:
    in_window, window_label = _default_history_window_entries(
        snapshot=snapshot,
        history_entries=history_entries,
    )
    if _is_hurricane_live_feed(feed):
        payload = _build_live_hurricane_display_payload(
            _with_hurricane_history_tracks(snapshot, in_window)
        )
        if payload and window_label:
            payload["window_label"] = window_label
        return payload
    return _build_history_event_payload(feed=feed, in_window=in_window, window_label=window_label)


def _build_snapshot_display_payload(
    feed: str,
    snapshot: dict | None,
    *,
    as_of: datetime | None = None,
) -> dict | None:
    if feed == "earthquakes":
        return _build_point_event_display_payload(
            snapshot,
            collector="earthquakes",
            event_type="earthquake",
            label="Ops Earthquake Snapshot",
        )
    if feed == "tsunamis":
        return _build_point_event_display_payload(
            snapshot,
            collector="tsunamis",
            event_type="tsunami",
            label="Ops Tsunami Snapshot",
        )
    if feed == "volcanoes":
        return _build_point_event_display_payload(
            snapshot,
            collector="volcanoes",
            event_type="volcano",
            label="Ops Volcano Snapshot",
        )
    if feed == WILDFIRE_LIVE_FEED:
        return _build_wildfire_display_payload(snapshot)
    if _is_hurricane_live_feed(feed):
        return _build_live_hurricane_display_payload(snapshot, as_of=as_of)
    if feed == "currency":
        return _build_currency_display_payload(snapshot)
    return None


def _build_display_payloads(state_by_feed: dict[str, tuple[dict | None, list[dict]]]) -> list[dict]:
    payloads: list[dict] = []
    for feed in (
        "earthquakes",
        "tsunamis",
        "volcanoes",
        WILDFIRE_LIVE_FEED,
        HURRICANE_LIVE_FEED,
        "currency",
    ):
        snapshot, history_entries = state_by_feed.get(feed, (None, []))
        default_load = _ops_default_load_mode(snapshot)
        payload = None
        if default_load == OPS_DEFAULT_LOAD_HISTORY and isinstance(snapshot, dict):
            payload = _build_default_history_payload(
                feed=feed,
                snapshot=snapshot,
                history_entries=history_entries,
            )
        if payload is None:
            payload = _build_snapshot_display_payload(feed, snapshot)
        if payload:
            payload["ops_default_view"] = default_load
            payloads.append(payload)
    return payloads


def _build_ops_payload_for_feed(feed: str) -> dict | None:
    snapshot = load_current_state_snapshot(feed)
    if not isinstance(snapshot, dict):
        return None
    default_load = _ops_default_load_mode(snapshot)
    if default_load == OPS_DEFAULT_LOAD_HISTORY:
        history_payload = _build_default_history_payload(
            feed=feed,
            snapshot=snapshot,
            history_entries=load_current_state_history(feed),
        )
        if history_payload:
            history_payload["ops_default_view"] = default_load
            return history_payload
    payload = _build_snapshot_display_payload(feed, snapshot)
    if payload:
        payload["ops_default_view"] = default_load
    return payload


def _ops_timeline_entry_time(entry: dict) -> datetime | None:
    """Return the authoritative capture time for one retained Ops frame."""
    if not isinstance(entry, dict):
        return None
    for key in ("published_at", "fetched_at", "last_checked_at"):
        parsed = _parse_iso_datetime(entry.get(key))
        if parsed is not None:
            return parsed
    return None


def _ops_timeline_cadence_seconds(snapshot: dict | None) -> int | None:
    """Derive the collector cadence from its existing snapshot envelope."""
    if not isinstance(snapshot, dict):
        return None
    fetched_at = _parse_iso_datetime(snapshot.get("fetched_at"))
    expected_next_at = _parse_iso_datetime(snapshot.get("expected_next_at"))
    if fetched_at is None or expected_next_at is None:
        return None
    seconds = int((expected_next_at - fetched_at).total_seconds())
    return seconds if seconds > 0 else None


def _ops_timeline_entries(feed: str, snapshot: dict | None, history_entries: list[dict]) -> list[dict]:
    """Return unique changed snapshots, ordered for a short Ops scrubber."""
    by_identity: dict[tuple[str, str], dict] = {}
    for entry in [*(history_entries or []), snapshot]:
        if not isinstance(entry, dict):
            continue
        observed_at = _ops_timeline_entry_time(entry)
        if observed_at is None:
            continue
        identity = (observed_at.isoformat(), str(entry.get("payload_hash") or ""))
        by_identity[identity] = entry
    return sorted(by_identity.values(), key=lambda entry: _ops_timeline_entry_time(entry) or datetime.min.replace(tzinfo=timezone.utc))


def ops_timeline_preload_history_contract(feed: str) -> dict | None:
    """Return the canonical feed-owned retained-history preload declaration."""
    record = ops_feed_record(feed)
    contract = record.get("timeline") if isinstance(record, dict) else None
    if isinstance(contract, dict):
        return dict(contract)
    return None


def build_ops_timeline_payload(*, effective_feeds: list[str], history_hours: int = DEFAULT_OPS_HISTORY_RETENTION_HOURS) -> dict:
    """Build one retained-history payload for the shared Ops scrubber.

    This deliberately returns the already-retained frames together.  Once the
    local browser receives this payload, dragging the cursor is a client-side
    render change, not a sequence of network requests.
    """
    now = datetime.now(timezone.utc).replace(microsecond=0)
    snapshots = {
        feed: load_current_state_snapshot(feed)
        for feed in effective_feeds
    }
    # Retained source history can be longer (NWS and hurricane child archives
    # deliberately are), but the shared Ops replay is a bounded 72-hour
    # operational cursor. Keep the transport bounded server-side as well as
    # in the browser.
    # ``max(base, *values)`` turns into ``max(base)`` when this request only
    # has external providers (Aurora/raster) and therefore no collector feed.
    # In that one-argument form Python expects an iterable. Build one explicit
    # collection so a timeline with only external frames remains valid.
    requested_hours = min(DEFAULT_OPS_HISTORY_DISPLAY_HOURS, max([
        max(1, int(history_hours)),
        *(_ops_timeline_display_hours_for_snapshot(snapshot) for snapshot in snapshots.values()),
    ]))
    range_start = now - timedelta(hours=requested_hours)
    feeds: dict[str, list[dict]] = {}
    hurricane_replay: dict[str, dict] = {}
    for feed in effective_feeds:
        snapshot = snapshots.get(feed)
        # NWS has a compact Railway-backed timeline index which the route layer
        # installs below. Avoid downloading its much longer retained archive
        # merely to construct entries that will immediately be replaced.
        history_entries = [] if feed == "usa_nws_alerts" else load_current_state_history(feed)
        entries = _ops_timeline_entries(feed, snapshot, history_entries)
        frames: list[dict] = []
        if _is_hurricane_live_feed(feed):
            in_window = [
                item for item in entries
                if (_ops_timeline_entry_time(item) or datetime.min.replace(tzinfo=timezone.utc)) >= range_start
            ]
            replay_payload = _build_hurricane_replay_payload(
                snapshot,
                in_window,
                as_of=now,
                history_hours=requested_hours,
            )
            if replay_payload is not None:
                hurricane_replay[feed] = replay_payload
                cursor_times = _hurricane_replay_cursor_times(
                    replay_payload,
                    range_start=range_start,
                    now=now,
                )
                frames = [
                    {
                        "start_at": cursor_time.isoformat(),
                        "end_at": cursor_times[index + 1].isoformat() if index + 1 < len(cursor_times) else None,
                        "payload_hash": snapshot.get("payload_hash") if isinstance(snapshot, dict) else None,
                        "timeline_provider": "hurricane_replay",
                    }
                    for index, cursor_time in enumerate(cursor_times)
                ]
                if frames:
                    feeds[feed] = frames
                continue
        for index, entry in enumerate(entries):
            start = _ops_timeline_entry_time(entry)
            if start is None:
                continue
            next_start = _ops_timeline_entry_time(entries[index + 1]) if index + 1 < len(entries) else None
            # A current state remains authoritative until a newer retained
            # state replaces it. Do not expire the latest event frame merely
            # because a collector is late relative to its expected cadence:
            # that made a live hurricane count coexist with an empty map.
            end = next_start
            if end is not None and end < range_start:
                continue
            display_snapshot = entry
            if _is_hurricane_live_feed(feed):
                continue
            display_payload = _build_snapshot_display_payload(feed, display_snapshot, as_of=start)
            if display_payload is None:
                continue
            display_payload["ops_default_view"] = "snapshot"
            frames.append({
                "start_at": start.isoformat(),
                "end_at": end.isoformat() if end is not None else None,
                "payload_hash": entry.get("payload_hash"),
                "display_payload": display_payload,
            })
        if frames:
            feeds[feed] = frames
    forecast_end_candidates = [
        parsed
        for frames in feeds.values()
        for frame in frames
        if isinstance(frame, dict)
        and isinstance(frame.get("display_payload"), dict)
        and (parsed := _parse_iso_datetime(frame["display_payload"].get("forecast_end_at"))) is not None
    ]
    forecast_end_candidates.extend(
        parsed
        for replay in hurricane_replay.values()
        for storm in (replay.get("storms") or [])
        if isinstance(storm, dict)
        for point in (storm.get("forecast_points") or [])
        if isinstance(point, dict)
        and (parsed := (
            _parse_iso_datetime(point.get("valid_at"))
            or _parse_iso_datetime(point.get("timestamp"))
            or _parse_iso_datetime(point.get("time"))
            or _parse_iso_datetime(point.get("issued_at"))
        )) is not None
    )
    forecast_end = max(forecast_end_candidates, default=None)
    payload = {
        "range_start": range_start.isoformat(),
        "range_end": now.isoformat(),
        "history_hours": requested_hours,
        # Forecast is a separate source-timed extension of the shared cursor.
        # Its display remains bounded by the advisory's own valid points.
        "forecast_end": forecast_end.isoformat() if forecast_end is not None else None,
        "cursor_step_seconds": 300,
        "feeds": feeds,
        # Transport this declarative switch with the frame index.  The client
        # only maps known providers to known endpoints; this is a per-feed
        # policy, never arbitrary client-directed fetching.
        "preload_history": {
            feed: contract
            for feed in feeds
            if not _is_hurricane_live_feed(feed)
            if (contract := ops_timeline_preload_history_contract(feed)) is not None
        },
    }
    if hurricane_replay:
        payload["hurricane_replay"] = hurricane_replay
    return payload


def _compact_payload_summary(collector: str, summary: dict, *, sample_limit: int = 3) -> dict:
    if not isinstance(summary, dict):
        return {}

    if collector == "earthquakes":
        return {
            "event_count": summary.get("event_count"),
            "max_magnitude": summary.get("max_magnitude"),
            "top_events": _sample_rows(
                summary.get("events") or [],
                ("event_id", "timestamp", "place", "magnitude", "depth_km"),
                sample_limit,
            ),
        }
    if collector == "currency":
        priority = {"USD": 0, "EUR": 1, "JPY": 2, "GBP": 3, "CNY": 4, "CAD": 5}
        rates = sorted(
            [row for row in (summary.get("rates") or []) if isinstance(row, dict)],
            key=lambda row: (priority.get(str(row.get("currency_code") or "").upper(), 99), str(row.get("currency_code") or "")),
        )
        return {
            "rate_count": summary.get("rate_count"),
            "base_currency": summary.get("base_currency"),
            "latest_snapshot_date": summary.get("latest_snapshot_date"),
            "sample_rates": _sample_rows(
                rates,
                ("currency_code", "date", "local_per_usd", "source_id"),
                max(sample_limit, 5),
            ),
        }
    if collector == "tsunamis":
        return {
            "event_count": summary.get("event_count"),
            "runup_count": summary.get("runup_count"),
            "top_events": _sample_rows(
                summary.get("events") or [],
                ("event_id", "timestamp", "country", "location", "cause", "eq_magnitude", "max_water_height_m"),
                sample_limit,
            ),
        }
    if collector == "volcanoes":
        return {
            "event_count": summary.get("event_count"),
            "ongoing_count": summary.get("ongoing_count"),
            "top_events": _sample_rows(
                summary.get("events") or [],
                ("event_id", "timestamp", "volcano_name", "activity_type", "vei", "is_ongoing"),
                sample_limit,
            ),
        }
    if collector == WILDFIRE_LIVE_FEED:
        return {
            "event_count": summary.get("event_count"),
            "active_count": summary.get("active_count"),
            "max_area_km2": summary.get("max_area_km2"),
            "top_events": _sample_rows(
                summary.get("events") or [],
                ("event_id", "fire_name", "state", "county_name", "source", "status", "area_km2", "last_updated"),
                sample_limit,
            ),
        }
    if _is_hurricane_live_feed(collector):
        return {
            "storm_count": summary.get("storm_count"),
            "position_count": summary.get("position_count"),
            "top_storms": _sample_rows(
                summary.get("storms") or [],
                (
                    "storm_id", "name", "year", "basin", "source",
                    "issued_at", "max_wind_kt", "max_category", "end_date",
                ),
                sample_limit,
            ),
        }
    if collector == "noaa_swpc":
        return {
            "alert_count": summary.get("alert_count"),
            "active_scales": summary.get("active_scales"),
            "alerts": _sample_rows(
                summary.get("alerts") or [],
                ("alert_id", "issued_utc", "alert_type", "noaa_scale", "summary"),
                sample_limit,
            ),
        }
    if collector == "noaa_aurora":
        return {
            "forecast_time": summary.get("forecast_time"),
            "aurora_visible": summary.get("aurora_visible"),
            "max_probability": summary.get("max_probability"),
            "visible_cell_count": summary.get("visible_cell_count"),
            "strong_cell_count": summary.get("strong_cell_count"),
            "north_boundary_lat": summary.get("north_boundary_lat"),
            "south_boundary_lat": summary.get("south_boundary_lat"),
        }
    if collector == "ocean_sst":
        return {
            "product": summary.get("product"),
            "grid_date": summary.get("grid_date"),
            "variables": summary.get("variables"),
            "units": summary.get("units"),
            "grid_shape": summary.get("grid_shape"),
            "resolution_deg": summary.get("resolution_deg"),
        }
    if collector == "noaa_ndbc":
        warmest_station = summary.get("warmest_station")
        coldest_station = summary.get("coldest_station")
        rows = [row for row in (summary.get("buoys") or []) if isinstance(row, dict)]
        warmest_row = next((row for row in rows if row.get("station_id") == warmest_station), None)
        coldest_row = next((row for row in rows if row.get("station_id") == coldest_station), None)
        return {
            "buoy_count": summary.get("buoy_count"),
            "sst_buoy_count": summary.get("sst_buoy_count"),
            "warmest_sst_c": summary.get("warmest_sst_c"),
            "warmest_station": warmest_station,
            "warmest_buoy": {
                key: warmest_row.get(key)
                for key in ("station_id", "lat", "lon", "sst_c", "air_c", "wave_m", "wind_mps", "obs_utc")
                if isinstance(warmest_row, dict) and key in warmest_row
            },
            "coldest_sst_c": summary.get("coldest_sst_c"),
            "coldest_station": coldest_station,
            "coldest_buoy": {
                key: coldest_row.get(key)
                for key in ("station_id", "lat", "lon", "sst_c", "air_c", "wave_m", "wind_mps", "obs_utc")
                if isinstance(coldest_row, dict) and key in coldest_row
            },
        }
    if collector == "airnow":
        return {
            "reporting_area_count": summary.get("reporting_area_count"),
            "by_parameter": summary.get("by_parameter"),
            "worst_aqi": summary.get("worst_aqi"),
            "worst_area": summary.get("worst_area"),
            "observation_kind": summary.get("observation_kind"),
            "coverage_note": summary.get("coverage_note"),
        }
    compact: dict = {}
    for key in ("event_count", "incident_count", "storm_count", "position_count", "rate_count", "alert_count"):
        if key in summary:
            compact[key] = summary.get(key)
    if not compact:
        compact["keys"] = sorted(summary.keys())[:12]
    return compact


def _compact_feed_snapshot(feed: str, snapshot: dict | None, history_entries: list[dict]) -> dict:
    record = ops_feed_record(feed)
    raw_chat_default = record.get("chat_default") if isinstance(record, dict) else None
    chat_default = {
        field: str(raw_chat_default.get(field) or "").strip()
        for field in ("message",)
    } if isinstance(raw_chat_default, dict) else {}
    chat_default = {field: value for field, value in chat_default.items() if value}
    if not isinstance(snapshot, dict):
        snapshot_status = _get_live_state_status(feed, "snapshot")
        history_status = _get_live_state_status(feed, "history")
        return {
            "feed": feed,
            "collector_status": snapshot_status or "missing",
            "history_entry_count": len(history_entries),
            "history_available": bool(history_entries),
            "live_state_status": {
                "snapshot": snapshot_status or "missing",
                "history": history_status or "missing",
            },
            "chat_default": chat_default,
            "summary": {},
        }
    summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
    return {
        "feed": feed,
        "collector_status": snapshot.get("collector_status"),
        "fetched_at": snapshot.get("fetched_at"),
        "last_checked_at": snapshot.get("last_checked_at"),
        "last_changed_at": snapshot.get("last_changed_at"),
        "expected_next_at": snapshot.get("expected_next_at"),
        "payload_hash": snapshot.get("payload_hash"),
        "previous_payload_hash": snapshot.get("previous_payload_hash"),
        "changed_since_previous": snapshot.get("changed_since_previous"),
        "history_entry_count": len(history_entries),
        "history_available": bool(history_entries),
        # Chat and public copy describe the bounded replay window, never the
        # longer operator/archive retention period.
        "display_history_hours": _ops_history_display_hours_for_snapshot(snapshot),
        "live_state_status": {
            "snapshot": _get_live_state_status(feed, "snapshot") or "unknown",
            "history": _get_live_state_status(feed, "history") or "unknown",
        },
        "chat_default": chat_default,
        "summary": _compact_payload_summary(feed, summary),
    }


def _build_recent_change_entry(feed: str, snapshot: dict | None, history_entries: list[dict]) -> dict | None:
    if not isinstance(snapshot, dict):
        return None
    if not history_entries and not snapshot.get("last_changed_at"):
        return None
    latest_history = history_entries[-1] if history_entries else {}
    latest_summary = latest_history.get("payload_summary") if isinstance(latest_history, dict) else {}
    return {
        "feed": feed,
        "collector_status": snapshot.get("collector_status"),
        "last_changed_at": snapshot.get("last_changed_at"),
        "payload_hash": snapshot.get("payload_hash"),
        "previous_payload_hash": snapshot.get("previous_payload_hash"),
        "history_entry_count": len(history_entries),
        "latest_change": _compact_payload_summary(feed, latest_summary, sample_limit=2),
    }


def _build_headline_summary(feed_snapshots: list[dict]) -> str:
    if not feed_snapshots:
        return "No Ops feeds are active in this watch."
    status_counts: dict[str, int] = {}
    for item in feed_snapshots:
        status = str(item.get("collector_status") or "unknown").strip() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    ordered_status = ", ".join(f"{status}:{count}" for status, count in sorted(status_counts.items()))
    notable_bits: list[str] = []
    for item in feed_snapshots[:3]:
        feed = str(item.get("feed") or "").strip()
        summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
        for key in ("event_count", "incident_count", "storm_count", "rate_count"):
            if key in summary and summary.get(key) is not None:
                notable_bits.append(f"{feed} {key}={summary.get(key)}")
                break
    if notable_bits:
        return f"Active Ops report with {len(feed_snapshots)} feeds ({ordered_status}). " + "; ".join(notable_bits)
    return f"Active Ops report with {len(feed_snapshots)} feeds ({ordered_status})."


def _build_map_items(feed_snapshots: list[dict]) -> list[dict]:
    items: list[dict] = []
    for snapshot in feed_snapshots:
        summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
        top_key = None
        for candidate in ("top_events", "top_storms", "sample_rates"):
            if summary.get(candidate):
                top_key = candidate
                break
        items.append(
            {
                "feed": snapshot.get("feed"),
                "collector_status": snapshot.get("collector_status"),
                "summary_key": top_key,
                "items": (summary.get(top_key) or [])[:3] if top_key else [],
            }
        )
    return items


def prewarm_ops_snapshots(
    feeds: list[str] | tuple[str, ...] | None = None,
    *,
    force_refresh: bool = False,
) -> dict:
    """Warm the bounded current snapshot for every default Ops watch feed."""
    targets = list(dict.fromkeys(
        _normalize_ops_feed_id(feed)
        for feed in (feeds or ops_feed_ids(flag="default_watch"))
        if _normalize_ops_feed_id(feed)
    ))
    if force_refresh:
        with _LIVE_STATE_CACHE_LOCK:
            for key in list(_LIVE_STATE_CACHE):
                if key[1] == "snapshot":
                    _LIVE_STATE_CACHE.pop(key, None)

    started = time.monotonic()
    warmed: list[str] = []
    missing: list[str] = []
    max_workers = max(1, min(len(targets), 8))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(load_current_state_snapshot, feed): feed for feed in targets}
        for future in as_completed(future_map):
            feed = future_map[future]
            try:
                snapshot = future.result()
            except Exception:
                logger.warning("Ops snapshot prewarm failed for %s", feed, exc_info=True)
                snapshot = None
            (warmed if isinstance(snapshot, dict) else missing).append(feed)

    result = {
        "requested": len(targets),
        "warmed": sorted(warmed),
        "missing": sorted(missing),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    if targets and not warmed:
        raise RuntimeError(f"No Ops snapshots could be warmed: {', '.join(sorted(missing))}")
    logger.info("Ops snapshot prewarm complete: %s", result)
    return result


def build_ops_report(
    *,
    watch: dict,
    effective_feeds: list[str],
    history_feeds: list[str] | None = None,
) -> dict:
    feed_snapshots: list[dict] = []
    recent_change_index: list[dict] = []
    geojson = None
    snapshot_hashes: dict[str, str] = {}
    snapshots_by_feed: dict[str, dict] = {}
    history_feed_set = {str(feed or "").strip() for feed in (history_feeds or []) if str(feed or "").strip()}
    state_by_feed: dict[str, tuple[dict | None, list[dict]]] = {}

    def _load_feed_state(feed: str) -> tuple[dict | None, list[dict]]:
        snapshot = load_current_state_snapshot(feed)
        # Initial Ops reports are snapshot-only. Retained histories belong to
        # the explicit timeline/deeper-load path and must not delay first paint.
        should_load_history = feed in history_feed_set
        history_entries = load_current_state_history(feed) if should_load_history else []
        return snapshot, history_entries

    max_workers = max(1, min(len(effective_feeds), 8))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_load_feed_state, feed): feed for feed in effective_feeds}
        for future in as_completed(future_map):
            feed = future_map[future]
            try:
                state_by_feed[feed] = future.result()
            except Exception:
                state_by_feed[feed] = (None, [])

    for feed in effective_feeds:
        snapshot, history_entries = state_by_feed.get(feed, (None, []))
        if isinstance(snapshot, dict):
            snapshots_by_feed[feed] = snapshot
            payload_hash = str(snapshot.get("payload_hash") or "").strip()
            if payload_hash:
                snapshot_hashes[feed] = payload_hash
            if geojson is None:
                geojson = _snapshot_to_geojson(snapshot)
        feed_snapshot = _compact_feed_snapshot(feed, snapshot, history_entries)
        feed_snapshots.append(feed_snapshot)
        change_entry = _build_recent_change_entry(feed, snapshot, history_entries)
        if change_entry:
            recent_change_index.append(change_entry)

    recent_change_index.sort(
        key=lambda entry: str(entry.get("last_changed_at") or ""),
        reverse=True,
    )
    report = {
        "report_version": 1,
        "watch_id": watch.get("watch_id"),
        "generated_at": max((str(item.get("last_checked_at") or "") for item in feed_snapshots), default=None),
        "effective_feeds": effective_feeds,
        "snapshot_hashes": snapshot_hashes,
        "headline_summary": _build_headline_summary(feed_snapshots),
        "feed_snapshots": feed_snapshots,
        "recent_change_index": recent_change_index[:6],
        "map_items": _build_map_items(feed_snapshots),
        "geojson": geojson,
        "display_payloads": _build_display_payloads(state_by_feed),
    }
    return report


def _query_requests_broad_recent_changes(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    if "what changed" in text or "what's changed" in text or "whats changed" in text:
        return True
    if "changed recently" in text or "recent changes" in text:
        return True
    if "recently changed" in text:
        return True
    return False


def _build_prompt_safe_ops_report(report: dict | None) -> dict:
    if not isinstance(report, dict):
        return {}
    raw_snapshots = report.get("feed_snapshots") or []
    prompt_safe_snapshots: list[dict] = []
    for item in raw_snapshots if isinstance(raw_snapshots, list) else []:
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        history_entries = cleaned.pop("history_entry_count", None)
        if history_entries is not None:
            cleaned["retained_history_entry_count"] = history_entries
        prompt_safe_snapshots.append(cleaned)
    raw_recent_changes = report.get("recent_change_index") or []
    prompt_safe_recent_changes: list[dict] = []
    for item in raw_recent_changes if isinstance(raw_recent_changes, list) else []:
        if not isinstance(item, dict):
            continue
        cleaned = dict(item)
        history_entries = cleaned.pop("history_entry_count", None)
        if history_entries is not None:
            cleaned["retained_history_entry_count"] = history_entries
        prompt_safe_recent_changes.append(cleaned)
    return {
        "report_version": report.get("report_version"),
        "watch_id": report.get("watch_id"),
        "generated_at": report.get("generated_at"),
        "effective_feeds": report.get("effective_feeds") or [],
        "snapshot_hashes": report.get("snapshot_hashes") or {},
        "headline_summary": report.get("headline_summary"),
        "feed_snapshots": prompt_safe_snapshots,
        "recent_change_index": prompt_safe_recent_changes,
        "map_items": report.get("map_items") or [],
    }


def _query_requests_deep_history(query: str, hints: dict | None = None) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    if any(re.search(pattern, text) for pattern in DEEP_HISTORY_PATTERNS):
        return True
    time_hints = (hints or {}).get("time") if isinstance(hints, dict) else {}
    if isinstance(time_hints, dict) and any(time_hints.get(key) for key in ("specific_year", "start_year", "end_year")):
        return True
    return False


def _parse_iso_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _history_observed_at(entry: dict | None) -> datetime | None:
    if not isinstance(entry, dict):
        return None
    for key in ("published_at", "last_changed_at", "fetched_at", "last_checked_at", "upstream_issued_at"):
        parsed = _parse_iso_datetime(entry.get(key))
        if parsed is not None:
            return parsed
    return None


def _extract_history_window(query: str, hints: dict | None = None) -> tuple[datetime | None, str | None]:
    text = str(query or "").strip().lower()
    if not text:
        return None, None
    now = datetime.now(timezone.utc)

    hours_match = re.search(r"\b(?:last|past)\s+(\d{1,3})\s+hours?\b", text)
    if hours_match:
        hours = max(1, int(hours_match.group(1)))
        return now.replace(microsecond=0) - timedelta(hours=hours), f"the last {hours} hour{'s' if hours != 1 else ''}"

    days_match = re.search(r"\b(?:last|past)\s+(\d{1,3})\s+days?\b", text)
    if days_match:
        days = max(1, int(days_match.group(1)))
        return now.replace(microsecond=0) - timedelta(days=days), f"the last {days} day{'s' if days != 1 else ''}"

    if re.search(r"\btoday\b", text):
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return cutoff, "today"

    if re.search(r"\byesterday\b", text):
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        return cutoff, "yesterday and today"

    time_hints = (hints or {}).get("time") if isinstance(hints, dict) else {}
    start_year = time_hints.get("start_year") if isinstance(time_hints, dict) else None
    end_year = time_hints.get("end_year") if isinstance(time_hints, dict) else None
    if isinstance(start_year, int):
        start_dt = datetime(start_year, 1, 1, tzinfo=timezone.utc)
        label = f"since {start_year}"
        if isinstance(end_year, int) and end_year >= start_year:
            start_dt = datetime(start_year, 1, 1, tzinfo=timezone.utc)
            label = f"{start_year}-{end_year}"
        return start_dt, label

    return None, None


def _requested_history_window_hours(query: str, hints: dict | None = None) -> int | None:
    text = str(query or "").strip().lower()
    if not text:
        return None

    hours_match = re.search(r"\b(?:last|past)\s+(\d{1,3})\s+hours?\b", text)
    if hours_match:
        return max(1, int(hours_match.group(1)))

    days_match = re.search(r"\b(?:last|past)\s+(\d{1,3})\s+days?\b", text)
    if days_match:
        return max(1, int(days_match.group(1))) * 24

    if re.search(r"\btoday\b", text):
        return 24

    if re.search(r"\byesterday\b", text):
        return 48

    time_hints = (hints or {}).get("time") if isinstance(hints, dict) else {}
    start_year = time_hints.get("start_year") if isinstance(time_hints, dict) else None
    if isinstance(start_year, int):
        now = datetime.now(timezone.utc)
        start_dt = datetime(start_year, 1, 1, tzinfo=timezone.utc)
        return max(1, int((now - start_dt).total_seconds() // 3600))

    return None


def _ops_history_retention_hours_for_snapshot(snapshot: dict | None) -> int:
    if isinstance(snapshot, dict):
        raw = snapshot.get("ops_history_retention_hours")
        try:
            hours = int(raw)
            if hours > 0:
                return hours
        except Exception:
            pass
    return DEFAULT_OPS_HISTORY_RETENTION_HOURS


def _ops_history_display_hours_for_snapshot(snapshot: dict | None) -> int:
    if isinstance(snapshot, dict):
        raw = snapshot.get("ops_history_display_hours")
        try:
            hours = int(raw)
            if hours > 0:
                retention_hours = _ops_history_retention_hours_for_snapshot(snapshot)
                return min(hours, retention_hours)
        except Exception:
            pass
    return min(DEFAULT_OPS_HISTORY_DISPLAY_HOURS, _ops_history_retention_hours_for_snapshot(snapshot))


def _ops_timeline_display_hours_for_snapshot(snapshot: dict | None) -> int:
    """Return the short interactive cursor window without reducing retention."""
    history_hours = _ops_history_display_hours_for_snapshot(snapshot)
    if isinstance(snapshot, dict):
        try:
            hours = int(snapshot.get("ops_timeline_display_hours") or history_hours)
            if hours > 0:
                return min(hours, history_hours)
        except (TypeError, ValueError):
            pass
    return history_hours


def _mentioned_feeds(query: str, effective_feeds: list[str]) -> list[str]:
    text = str(query or "").strip().lower()
    matched: list[str] = []
    for feed in effective_feeds:
        aliases = FEED_ALIASES.get(feed, ()) + (feed.replace("_", " "), feed)
        for alias in aliases:
            alias_text = str(alias or "").strip().lower()
            if alias_text and alias_text in text:
                matched.append(feed)
                break
    return matched


def _query_requests_map_focus(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    return any(re.search(pattern, text) for pattern in MAP_FOCUS_PATTERNS)


def _query_requests_singular_focus(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    return any(re.search(pattern, text) for pattern in SINGULAR_FOCUS_PATTERNS)


def _query_requests_superlative(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    return any(re.search(pattern, text) for pattern in SUPERLATIVE_PATTERNS)


def _superlative_picks(query: str) -> list[str]:
    text = str(query or "").strip().lower()
    if not text:
        return []
    picks: list[str] = []
    if any(token in text for token in ("biggest", "largest", "strongest", "worst", "highest", "most severe")):
        picks.append("max")
    if any(token in text for token in ("smallest", "lowest", "least severe")):
        picks.append("min")
    return picks


def _extract_identifier_reference(query: str) -> tuple[str | None, str | None]:
    text = str(query or "").strip()
    if not text:
        return None, None
    lowered = text.lower()
    patterns = (
        (r"\bevent[_\s]?id\s*[:=]?\s*([A-Za-z0-9._:-]+)", "event_id"),
        (r"\bstorm[_\s]?id\s*[:=]?\s*([A-Za-z0-9._:-]+)", "storm_id"),
        (r"\bincident[_\s]?id\s*[:=]?\s*([A-Za-z0-9._:-]+)", "incident_id"),
    )
    for pattern, key in patterns:
        match = re.search(pattern, lowered, flags=re.IGNORECASE)
        if match:
            value = str(match.group(1) or "").strip()
            if value:
                return key, value

    token_candidates = re.findall(r"[A-Za-z0-9._:-]{4,}", text)
    for candidate in token_candidates:
        hinted_packs, strict = _classify_exact_event_identifier(candidate)
        if strict and hinted_packs:
            return "event_id", str(candidate).strip()
    return None, None


def _recent_feed_from_history(chat_history: list | None, effective_feeds: list[str]) -> str | None:
    for message in reversed(chat_history or []):
        if str((message or {}).get("role") or "").strip().lower() != "user":
            continue
        content = str((message or {}).get("content") or "").strip()
        mentioned = _mentioned_feeds(content, effective_feeds)
        if len(mentioned) == 1:
            return mentioned[0]
    return None


def _recent_feed_from_cache(*, cache, effective_feeds: list[str]) -> str | None:
    history_feed, _history_payload = _resolve_cached_history_payload(
        cache=cache,
        effective_feeds=effective_feeds,
    )
    if history_feed:
        return history_feed
    focus_feed, _focus_payload, _focus_feature = _resolve_cached_focus_target(
        cache=cache,
        report={"display_payloads": []},
        effective_feeds=effective_feeds,
    )
    if focus_feed:
        return focus_feed
    return None


def _infer_followup_feed(
    *,
    query: str,
    chat_history: list | None,
    effective_feeds: list[str],
    cache,
    report: dict | None = None,
) -> str | None:
    explicit = _mentioned_feeds(query, effective_feeds)
    if len(explicit) == 1:
        return explicit[0]
    recent_feed = _recent_feed_from_history(chat_history, effective_feeds)
    if recent_feed:
        return recent_feed
    cached_feed = _recent_feed_from_cache(cache=cache, effective_feeds=effective_feeds)
    if cached_feed:
        return cached_feed
    if isinstance(report, dict):
        recent = report.get("recent_change_index") if isinstance(report.get("recent_change_index"), list) else []
        for entry in recent:
            feed = str((entry or {}).get("feed") or "").strip()
            if feed in effective_feeds:
                return feed
    if len(effective_feeds) == 1:
        return effective_feeds[0]
    return None


def _report_display_payload_by_feed(report: dict | None) -> dict[str, dict]:
    payloads: dict[str, dict] = {}
    for payload in (report or {}).get("display_payloads") or []:
        if not isinstance(payload, dict):
            continue
        source_id = str(payload.get("source_id") or "").strip()
        if source_id == "currency_live_ops":
            payloads["currency"] = payload
        # `hurricanes_ops` was the retired IBTrACS-based display payload.
        # IBTrACS remains a canonical historical/API source, but it is not an
        # operational display authority.  Do not let an older cached report
        # reintroduce its completed best tracks into the live Hurricanes feed.
        elif source_id == "hurricanes_live_ops":
            payloads[HURRICANE_LIVE_FEED] = payload
        elif source_id.endswith("_live_ops"):
            payloads[source_id[:-9]] = payload
    return payloads


def _feature_numeric_value(feature: dict, keys: tuple[str, ...]) -> float | None:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    for key in keys:
        value = props.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _focus_feature_name(feed: str, props: dict) -> str:
    if feed == WILDFIRE_LIVE_FEED:
        return str(props.get("fire_name") or props.get("event_id") or "Unnamed wildfire").strip()
    if feed == "earthquakes":
        return str(props.get("place") or props.get("event_id") or "Unnamed earthquake").strip()
    if feed == "tsunamis":
        return str(props.get("location") or props.get("country") or props.get("event_id") or "Unnamed tsunami").strip()
    if feed == "volcanoes":
        return str(props.get("volcano_name") or props.get("event_id") or "Unnamed volcano").strip()
    if _is_hurricane_live_feed(feed):
        return str(props.get("name") or props.get("storm_id") or "Unnamed storm").strip()
    return str(props.get("event_id") or props.get("storm_id") or "Unnamed event").strip()


def _focus_feature_location(feed: str, props: dict) -> str | None:
    if feed == WILDFIRE_LIVE_FEED:
        county = str(props.get("county_name") or "").strip()
        state = str(props.get("state") or "").strip()
        if county and state:
            return f"{county}, {state}"
        if str(props.get("source") or "").strip().lower() == "cwfis_m3":
            return "Canada"
        return county or state or None
    if feed == "tsunamis":
        location = str(props.get("location") or "").strip()
        country = str(props.get("country") or "").strip()
        if location and country and location.lower() not in country.lower():
            return f"{location}, {country}"
        return location or country or None
    if _is_hurricane_live_feed(feed):
        basin = str(props.get("basin") or "").strip()
        return basin or None
    return None


def _focus_metric_text(feed: str, props: dict) -> str | None:
    if feed == WILDFIRE_LIVE_FEED:
        try:
            return f"{float(props.get('area_km2')):,.2f} km² burned"
        except (TypeError, ValueError):
            return None
    if feed == "earthquakes":
        value = props.get("magnitude")
        return f"magnitude {value}" if value not in (None, "") else None
    if feed == "tsunamis":
        value = props.get("max_water_height_m")
        return f"{value} m max water height" if value not in (None, "") else None
    if feed == "volcanoes":
        value = props.get("VEI") if props.get("VEI") not in (None, "") else props.get("vei")
        return f"VEI {value}" if value not in (None, "") else None
    if _is_hurricane_live_feed(feed):
        category = props.get("max_category") if props.get("max_category") not in (None, "") else props.get("category")
        wind = props.get("max_wind_kt")
        if category not in (None, "") and wind not in (None, ""):
            return f"Category {category}, {wind} kt"
        if category not in (None, ""):
            return f"Category {category}"
        if wind not in (None, ""):
            return f"{wind} kt"
    return None


def _format_ops_timestamp(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%b %d, %Y %H:%M UTC")


def _geometry_bbox(geometry: dict | None) -> tuple[float, float, float, float] | None:
    if not isinstance(geometry, dict):
        return None
    coords = geometry.get("coordinates")
    if not isinstance(coords, list):
        return None

    points: list[tuple[float, float]] = []

    def _walk(node) -> None:
        if not isinstance(node, list) or not node:
            return
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            try:
                points.append((float(node[0]), float(node[1])))
            except (TypeError, ValueError):
                return
            return
        for child in node:
            _walk(child)

    _walk(coords)
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return min(lons), min(lats), max(lons), max(lats)


def _bbox_contains_point(bbox: tuple[float, float, float, float], lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _bbox_overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return ((min_lon + max_lon) / 2.0, (min_lat + max_lat) / 2.0)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_km * c


def _extract_query_point(query: str) -> tuple[float, float] | None:
    text = str(query or "").strip()
    if not text:
        return None
    match = re.search(
        r"(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)",
        text,
    )
    if not match:
        return None
    try:
        first = float(match.group(1))
        second = float(match.group(2))
    except (TypeError, ValueError):
        return None
    if abs(first) <= 90 and abs(second) <= 180:
        return second, first
    if abs(first) <= 180 and abs(second) <= 90:
        return first, second
    return None


def _location_candidate_from_query(query: str) -> dict | None:
    detected = detect_location_candidates(
        query,
        normalize_query_for_location_matching=normalize_query_for_location_matching,
        reference_dir=REFERENCE_ROOT,
        load_reference_file=load_reference_dict,
    )
    candidate = detected.get("best") if isinstance(detected, dict) else None
    return candidate if isinstance(candidate, dict) else None


def _geometry_for_loc_id(loc_id: str | None) -> dict | None:
    value = str(loc_id or "").strip()
    if not value:
        return None
    try:
        geojson = get_selection_geometries([value])
    except Exception:
        return None
    if not isinstance(geojson, dict):
        return None
    features = geojson.get("features")
    if not isinstance(features, list):
        return None
    for feature in features:
        if isinstance(feature, dict) and isinstance(feature.get("geometry"), dict):
            return feature.get("geometry")
    return None


def _resolve_area_target(
    *,
    query: str,
    watch: dict,
    selected_popup: dict | None = None,
) -> dict | None:
    point = _extract_query_point(query)
    if point is not None:
        lon, lat = point
        resolved = resolve_point_to_loc_id_stack(lon, lat, include_geometry=True)
        matched = resolved.get("matched") if isinstance(resolved.get("matched"), dict) else {}
        geojson = resolved.get("geojson") if isinstance(resolved.get("geojson"), dict) else {}
        features = geojson.get("features") if isinstance(geojson.get("features"), list) else []
        geometry = None
        for feature in features:
            if isinstance(feature, dict) and isinstance(feature.get("geometry"), dict):
                geometry = feature.get("geometry")
                break
        bbox = _geometry_bbox(geometry) if geometry else None
        return {
            "label": str(matched.get("name") or f"{lat:.3f}, {lon:.3f}").strip(),
            "loc_id": str(matched.get("loc_id") or "").strip() or None,
            "point": {"lon": lon, "lat": lat},
            "bbox": bbox,
            "source": "query_point",
        }

    lowered = str(query or "").strip().lower()
    if re.search(r"\b(here|this area|that area|my area|this location|that location)\b", lowered):
        if isinstance(selected_popup, dict):
            geometry = selected_popup.get("geometry") if isinstance(selected_popup.get("geometry"), dict) else None
            props = selected_popup.get("properties") if isinstance(selected_popup.get("properties"), dict) else {}
            loc_id = str(selected_popup.get("loc_id") or props.get("loc_id") or "").strip() or None
            if geometry is None and loc_id:
                geometry = _geometry_for_loc_id(loc_id)
            bbox = _geometry_bbox(geometry) if geometry else None
            if bbox or loc_id:
                return {
                    "label": str(selected_popup.get("name") or props.get("name") or loc_id or "selected area").strip(),
                    "loc_id": loc_id,
                    "bbox": bbox,
                    "point": None,
                    "source": "selected_popup",
                }
        geography = watch.get("geography") if isinstance(watch.get("geography"), dict) else {}
        viewport = geography.get("viewport") if isinstance(geography.get("viewport"), dict) else {}
        bounds = viewport.get("bounds") if isinstance(viewport.get("bounds"), dict) else {}
        try:
            west = float(bounds.get("west"))
            south = float(bounds.get("south"))
            east = float(bounds.get("east"))
            north = float(bounds.get("north"))
        except (TypeError, ValueError):
            west = south = east = north = None
        if None not in (west, south, east, north):
            return {
                "label": str(watch.get("label") or "current map area").strip(),
                "loc_id": None,
                "bbox": (west, south, east, north),
                "point": {"lon": (west + east) / 2.0, "lat": (south + north) / 2.0},
                "source": "watch_viewport",
            }

    candidate = _location_candidate_from_query(query)
    if not candidate:
        return None
    loc_id = str(candidate.get("loc_id") or "").strip()
    geometry = _geometry_for_loc_id(loc_id)
    bbox = _geometry_bbox(geometry) if geometry else None
    if not bbox and loc_id:
        return {
            "label": str(candidate.get("matched_term") or loc_id).strip(),
            "loc_id": loc_id,
            "bbox": None,
            "point": None,
            "source": "query_location",
        }
    return {
        "label": str(candidate.get("matched_term") or loc_id).strip(),
        "loc_id": loc_id or None,
        "bbox": bbox,
        "point": None,
        "source": "query_location",
    }


def _query_requests_area_impact(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    if _extract_query_point(text) is not None:
        return True
    return any(re.search(pattern, text) for pattern in AREA_IMPACT_PATTERNS)


def _feature_match_distance_km(feature: dict, target: dict) -> float | None:
    geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
    bbox = _geometry_bbox(geometry)
    point = target.get("point") if isinstance(target.get("point"), dict) else None
    target_bbox = target.get("bbox")
    if point is not None:
        lon = point.get("lon")
        lat = point.get("lat")
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []
                if len(coords) >= 2:
                    try:
                        feature_lon = float(coords[0])
                        feature_lat = float(coords[1])
                    except (TypeError, ValueError):
                        feature_lon = feature_lat = None
                    if feature_lon is not None and feature_lat is not None:
                        return _haversine_km(float(lat), float(lon), feature_lat, feature_lon)
            if bbox is not None:
                center_lon, center_lat = _bbox_center(bbox)
                return _haversine_km(float(lat), float(lon), center_lat, center_lon)
    if bbox is not None and isinstance(target_bbox, tuple):
        center_lon, center_lat = _bbox_center(bbox)
        target_center_lon, target_center_lat = _bbox_center(target_bbox)
        return _haversine_km(target_center_lat, target_center_lon, center_lat, center_lon)
    return None


def _feature_matches_area_target(feature: dict, target: dict) -> bool:
    geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
    if not geometry:
        return False
    target_point = target.get("point") if isinstance(target.get("point"), dict) else None
    target_bbox = target.get("bbox")
    if target_point is not None:
        lon = target_point.get("lon")
        lat = target_point.get("lat")
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []
                if len(coords) >= 2:
                    try:
                        feature_lon = float(coords[0])
                        feature_lat = float(coords[1])
                    except (TypeError, ValueError):
                        feature_lon = feature_lat = None
                    if feature_lon is not None and feature_lat is not None:
                        return _haversine_km(float(lat), float(lon), feature_lat, feature_lon) <= 75.0
            bbox = _geometry_bbox(geometry)
            return bool(bbox and _bbox_contains_point(bbox, float(lon), float(lat)))
    if isinstance(target_bbox, tuple):
        bbox = _geometry_bbox(geometry)
        return bool(bbox and _bbox_overlaps(bbox, target_bbox))
    return False


def _build_area_impact_answer(*, report: dict, effective_feeds: list[str], target: dict) -> str | None:
    payloads = _report_display_payload_by_feed(report)
    if not payloads:
        return None

    matches: list[dict] = []
    for feed in effective_feeds:
        payload = payloads.get(feed)
        if not isinstance(payload, dict):
            continue
        matched_features = [
            feature
            for feature in _payload_features(payload)
            if isinstance(feature, dict) and _feature_matches_area_target(feature, target)
        ]
        if not matched_features:
            continue
        matched_features.sort(
            key=lambda feature: (
                _feature_match_distance_km(feature, target)
                if _feature_match_distance_km(feature, target) is not None
                else 10**9
            )
        )
        sample_feature = matched_features[0]
        props = sample_feature.get("properties") if isinstance(sample_feature.get("properties"), dict) else {}
        descriptor = _focus_feature_name(feed, props)
        metric = _focus_metric_text(feed, props)
        timestamp = _focus_timestamp(feed, props)
        summary_bits = [descriptor]
        if metric:
            summary_bits.append(metric)
        if timestamp:
            summary_bits.append(timestamp)
        matches.append(
            {
                "feed": feed,
                "count": len(matched_features),
                "summary": ", ".join(summary_bits),
            }
        )

    label = str(target.get("label") or "that area").strip() or "that area"
    if not matches:
        return f"I do not see current Ops events intersecting {label} right now."

    matches.sort(key=lambda item: (-int(item["count"]), str(item["feed"])))
    lead = matches[:3]
    parts = []
    for item in lead:
        feed = str(item["feed"])
        count = int(item["count"])
        feed_label = _feed_singular_label(feed) if count == 1 else _feed_display_name(feed)
        parts.append(f"{count} {feed_label} ({item['summary']})")
    joined = "; ".join(parts)
    if len(matches) == 1:
        return f"Yes. I see {joined} affecting {label}."
    return f"Yes. I see {joined} affecting {label}."


def _focus_timestamp(feed: str, props: dict) -> str | None:
    for key in ("last_updated", "timestamp", "end_date", "start_date"):
        formatted = _format_ops_timestamp(props.get(key))
        if formatted:
            return formatted
    return None


def _payload_features(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    geojson = payload.get("geojson")
    if not isinstance(geojson, dict):
        return []
    features = geojson.get("features")
    return features if isinstance(features, list) else []


def _select_extrema_feature_from_payload(
    *,
    feed: str,
    payload: dict | None,
    pick: str = "max",
) -> tuple[dict, dict, float] | tuple[None, None, None]:
    spec = FEED_FOCUS_SPECS.get(feed)
    if not spec:
        return None, None, None
    best_feature = None
    best_value = None
    for feature in _payload_features(payload):
        if not isinstance(feature, dict):
            continue
        value = _feature_numeric_value(feature, spec["metric_keys"])
        if value is None:
            continue
        if (
            best_value is None
            or (pick == "max" and value > best_value)
            or (pick == "min" and value < best_value)
        ):
            best_feature = feature
            best_value = value
    if best_feature is None or best_value is None:
        return None, None, None
    return payload, best_feature, float(best_value)


def _category_rank(value: object) -> float:
    text = str(value or "").strip().upper()
    ranks = {
        "TD": 0.0,
        "TS": 1.0,
        "CAT1": 2.0,
        "CAT2": 3.0,
        "CAT3": 4.0,
        "CAT4": 5.0,
        "CAT5": 6.0,
    }
    return ranks.get(text, -1.0)


def _coords_text(lat: object, lon: object) -> str | None:
    try:
        lat_value = float(lat)
        lon_value = float(lon)
    except (TypeError, ValueError):
        return None
    lat_dir = "N" if lat_value >= 0 else "S"
    lon_dir = "E" if lon_value >= 0 else "W"
    return f"{abs(lat_value):.1f}{lat_dir}, {abs(lon_value):.1f}{lon_dir}"


def _selected_popup_feed(selected_popup: dict | None, effective_feeds: list[str]) -> str | None:
    if not isinstance(selected_popup, dict):
        return None
    normalized_effective_feeds = [_normalize_ops_feed_id(feed) for feed in effective_feeds or []]
    props = selected_popup.get("properties") if isinstance(selected_popup.get("properties"), dict) else {}
    event_type = str(selected_popup.get("event_type") or props.get("event_type") or "").strip().lower()
    if event_type in {"hurricane", "storm", "cyclone", "typhoon"} and HURRICANE_LIVE_FEED in normalized_effective_feeds:
        return HURRICANE_LIVE_FEED
    if str(props.get("storm_id") or "").strip() and HURRICANE_LIVE_FEED in normalized_effective_feeds:
        return HURRICANE_LIVE_FEED
    return None


def _selected_storm_identity(selected_popup: dict | None) -> tuple[str | None, str | None]:
    if not isinstance(selected_popup, dict):
        return None, None
    props = selected_popup.get("properties") if isinstance(selected_popup.get("properties"), dict) else {}
    storm_id = str(
        props.get("storm_id")
        or selected_popup.get("event_id")
        or ""
    ).strip()
    storm_name = str(
        props.get("name")
        or selected_popup.get("name")
        or ""
    ).strip()
    return storm_id or None, storm_name or None


def _latest_position_for_storm(rows: list[dict], storm_id: str | None) -> dict | None:
    if not storm_id:
        return None
    matching = [
        row for row in rows
        if isinstance(row, dict) and str(row.get("storm_id") or "").strip() == storm_id
    ]
    if not matching:
        return None
    return max(matching, key=lambda row: str(row.get("timestamp") or ""))


def _build_selected_hurricane_history_answer(selected_popup: dict | None) -> str | None:
    storm_id, storm_name = _selected_storm_identity(selected_popup)
    if not storm_id and not storm_name:
        return None

    entries = load_current_state_history(HURRICANE_LIVE_FEED)
    label = storm_name or storm_id or "the selected storm"
    if not entries:
        return (
            f"I know which storm is selected ({label}), but there is no retained Ops hurricane history "
            "available yet in this environment, so I cannot compare the last few days."
        )

    timeline: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        summary = entry.get("payload_summary") if isinstance(entry.get("payload_summary"), dict) else {}
        storms = summary.get("storms") if isinstance(summary.get("storms"), list) else []
        positions = summary.get("positions") if isinstance(summary.get("positions"), list) else []
        matched_storm = None
        if storm_id:
            for storm in storms:
                if not isinstance(storm, dict):
                    continue
                if str(storm.get("storm_id") or "").strip() == storm_id:
                    matched_storm = storm
                    break
        if matched_storm is None and storm_name:
            for storm in storms:
                if not isinstance(storm, dict):
                    continue
                if str(storm.get("name") or "").strip().lower() == storm_name.lower():
                    matched_storm = storm
                    break
        if matched_storm is None:
            continue
        resolved_storm_id = str(matched_storm.get("storm_id") or storm_id or "").strip() or None
        timeline.append(
            {
                "published_at": entry.get("published_at") or entry.get("last_changed_at") or entry.get("upstream_issued_at"),
                "storm": matched_storm,
                "position": _latest_position_for_storm(positions, resolved_storm_id),
            }
        )

    if not timeline:
        return (
            f"I know which storm is selected ({label}), but it is not present in the retained Ops hurricane "
            "history window yet, so I cannot compare its recent changes."
        )

    ordered = sorted(timeline, key=lambda item: str(item.get("published_at") or ""))
    earliest = ordered[0]
    latest = ordered[-1]

    early_storm = earliest.get("storm") if isinstance(earliest.get("storm"), dict) else {}
    latest_storm = latest.get("storm") if isinstance(latest.get("storm"), dict) else {}
    early_position = earliest.get("position") if isinstance(earliest.get("position"), dict) else {}
    latest_position = latest.get("position") if isinstance(latest.get("position"), dict) else {}

    early_name = str(early_storm.get("name") or storm_name or storm_id or "Selected storm").strip()
    early_category = early_position.get("category") or early_storm.get("max_category")
    latest_category = latest_position.get("category") or latest_storm.get("max_category")
    early_wind = early_position.get("wind_kt") or early_storm.get("max_wind_kt")
    latest_wind = latest_position.get("wind_kt") or latest_storm.get("max_wind_kt")
    early_time = _format_ops_timestamp(
        early_position.get("timestamp") or early_storm.get("end_date") or earliest.get("published_at")
    )
    latest_time = _format_ops_timestamp(
        latest_position.get("timestamp") or latest_storm.get("end_date") or latest.get("published_at")
    )

    sentences: list[str] = [
        f"{early_name} appears in {len(ordered)} retained Ops hurricane snapshots in the current live history window."
    ]

    change_bits: list[str] = []
    if early_category not in (None, "") and latest_category not in (None, ""):
        if str(early_category) == str(latest_category):
            change_bits.append(f"it remained at {latest_category}")
        elif _category_rank(latest_category) > _category_rank(early_category):
            change_bits.append(f"it strengthened from {early_category} to {latest_category}")
        elif _category_rank(latest_category) < _category_rank(early_category):
            change_bits.append(f"it weakened from {early_category} to {latest_category}")
        else:
            change_bits.append(f"its classification changed from {early_category} to {latest_category}")

    try:
        if early_wind not in (None, "") and latest_wind not in (None, ""):
            early_wind_value = float(early_wind)
            latest_wind_value = float(latest_wind)
            wind_delta = latest_wind_value - early_wind_value
            if abs(wind_delta) < 0.5:
                change_bits.append(f"winds stayed near {latest_wind_value:.0f} kt")
            elif wind_delta > 0:
                change_bits.append(f"winds increased from {early_wind_value:.0f} kt to {latest_wind_value:.0f} kt")
            else:
                change_bits.append(f"winds decreased from {early_wind_value:.0f} kt to {latest_wind_value:.0f} kt")
    except (TypeError, ValueError):
        pass

    if change_bits:
        sentences.append("Over that window, " + " and ".join(change_bits) + ".")

    if early_time and latest_time:
        sentences.append(f"Window compared: {early_time} to {latest_time}.")

    latest_coords = _coords_text(latest_position.get("latitude"), latest_position.get("longitude"))
    latest_basin = str(latest_storm.get("basin") or "").strip()
    if latest_coords and latest_basin:
        sentences.append(f"Latest retained position is near {latest_coords} in basin {latest_basin}.")
    elif latest_coords:
        sentences.append(f"Latest retained position is near {latest_coords}.")

    return " ".join(sentences)


def _try_selected_history_answer(
    *,
    query: str,
    selected_popup: dict | None,
    effective_feeds: list[str],
) -> str | None:
    if not _query_requests_deep_history(query):
        return None
    selected_feed = _selected_popup_feed(selected_popup, effective_feeds)
    if not _is_hurricane_live_feed(selected_feed):
        return None
    return _build_selected_hurricane_history_answer(selected_popup)


def _select_focus_candidate(
    *,
    feed: str,
    report: dict,
    pick: str = "max",
) -> tuple[dict, dict, float] | tuple[None, None, None]:
    spec = FEED_FOCUS_SPECS.get(feed)
    if not spec:
        return None, None, None
    payload = _report_display_payload_by_feed(report).get(feed) or _build_ops_payload_for_feed(feed)
    return _select_focus_candidate_from_payload(feed=feed, payload=payload, pick=pick)


def _select_focus_candidate_from_payload(
    *,
    feed: str,
    payload: dict | None,
    pick: str = "max",
) -> tuple[dict, dict, float] | tuple[None, None, None]:
    spec = FEED_FOCUS_SPECS.get(feed)
    if not spec or not isinstance(payload, dict):
        return None, None, None
    return _select_extrema_feature_from_payload(feed=feed, payload=payload, pick=pick)


def _feature_matches_identifier(feed: str, feature: dict, identifier_key: str | None, identifier_value: str | None) -> bool:
    if not identifier_value:
        return False
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    candidate_keys: list[str] = []
    if identifier_key:
        candidate_keys.append(identifier_key)
    candidate_keys.extend(FEED_FOCUS_SPECS.get(feed, {}).get("id_keys", ()))
    lowered_value = str(identifier_value).strip().lower()
    for key in candidate_keys:
        value = str(props.get(key) or "").strip().lower()
        if value and value == lowered_value:
            return True
    return False


def _find_feature_by_identifier(
    *,
    feed: str,
    payload: dict | None,
    identifier_key: str | None,
    identifier_value: str | None,
) -> tuple[dict, dict] | tuple[None, None]:
    if not isinstance(payload, dict) or not identifier_value:
        return None, None
    features = (payload.get("geojson") or {}).get("features") if isinstance(payload.get("geojson"), dict) else None
    if not isinstance(features, list):
        return None, None
    for feature in features:
        if isinstance(feature, dict) and _feature_matches_identifier(feed, feature, identifier_key, identifier_value):
            return payload, feature
    return None, None


def _focus_identifier(feed: str, feature: dict) -> dict:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    spec = FEED_FOCUS_SPECS.get(feed) or {}
    for key in spec.get("id_keys", ()):
        value = str(props.get(key) or "").strip()
        if value:
            return {"key": key, "value": value}
    return {}


def _store_ops_focus_target(cache, *, feed: str, payload: dict, feature: dict) -> None:
    if not isinstance(getattr(cache, "map_state", None), dict):
        return
    cache.map_state["ops_focus_target"] = {
        "feed": feed,
        "source_id": payload.get("source_id"),
        "identifier": _focus_identifier(feed, feature),
        "feature": feature,
    }


def _store_ops_history_payload(cache, *, feed: str, payload: dict) -> None:
    if not isinstance(getattr(cache, "map_state", None), dict):
        return
    cache.map_state["ops_history_payload"] = {
        "feed": feed,
        "payload": payload,
    }


def _resolve_cached_history_payload(*, cache, effective_feeds: list[str]) -> tuple[str, dict] | tuple[None, None]:
    map_state = cache.map_state if isinstance(getattr(cache, "map_state", None), dict) else {}
    stored = map_state.get("ops_history_payload") if isinstance(map_state, dict) else None
    if not isinstance(stored, dict):
        return None, None
    feed = str(stored.get("feed") or "").strip()
    payload = stored.get("payload")
    if not feed or feed not in effective_feeds or not isinstance(payload, dict):
        return None, None
    return feed, payload


def _resolve_cached_focus_target(*, cache, report: dict, effective_feeds: list[str]) -> tuple[str, dict, dict] | tuple[None, None, None]:
    map_state = cache.map_state if isinstance(getattr(cache, "map_state", None), dict) else {}
    stored = map_state.get("ops_focus_target") if isinstance(map_state, dict) else None
    if not isinstance(stored, dict):
        return None, None, None
    feed = str(stored.get("feed") or "").strip()
    if not feed or feed not in effective_feeds:
        return None, None, None
    payload = _report_display_payload_by_feed(report).get(feed) or _build_ops_payload_for_feed(feed)
    if not isinstance(payload, dict):
        fallback_feature = stored.get("feature")
        if isinstance(fallback_feature, dict):
            return feed, {
                "type": stored.get("source_id") == "hurricanes_live_ops" and "data" or "events",
                "data_type": "events",
                "event_type": FEED_FOCUS_SPECS.get(feed, {}).get("label"),
                "source_id": stored.get("source_id"),
                "geojson": {"type": "FeatureCollection", "features": [fallback_feature]},
            }, fallback_feature
        return None, None, None
    features = (payload.get("geojson") or {}).get("features") if isinstance(payload.get("geojson"), dict) else []
    identifier = stored.get("identifier") if isinstance(stored.get("identifier"), dict) else {}
    key = str(identifier.get("key") or "").strip()
    value = str(identifier.get("value") or "").strip()
    if key and value:
        for feature in features or []:
            props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
            if str(props.get(key) or "").strip() == value:
                return feed, payload, feature
    fallback_feature = stored.get("feature")
    if isinstance(fallback_feature, dict):
        return feed, payload, fallback_feature
    return None, None, None


def _superlative_word(pick: str) -> str:
    return "smallest" if pick == "min" else "largest"


def _build_focus_chat_message(*, feed: str, feature: dict, pick: str = "max") -> str:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    label = FEED_FOCUS_SPECS.get(feed, {}).get("label") or "event"
    name = _focus_feature_name(feed, props)
    location = _focus_feature_location(feed, props)
    metric = _focus_metric_text(feed, props)
    timestamp = _focus_timestamp(feed, props)
    pieces = [f"The {_superlative_word(pick)} active {label} is {name}"]
    if location:
        pieces[-1] += f" in {location}"
    if metric:
        pieces[-1] += f", with {metric}"
    pieces[-1] += "."
    if timestamp:
        pieces.append(f"Last updated {timestamp}.")
    return " ".join(pieces)


def _build_history_focus_chat_message(*, feed: str, feature: dict, pick: str = "max") -> str:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    label = FEED_FOCUS_SPECS.get(feed, {}).get("label") or "event"
    name = _focus_feature_name(feed, props)
    location = _focus_feature_location(feed, props)
    metric = _focus_metric_text(feed, props)
    timestamp = _focus_timestamp(feed, props)
    pieces = [f"The {_superlative_word(pick)} retained {label} in that window is {name}"]
    if location:
        pieces[-1] += f" in {location}"
    if metric:
        pieces[-1] += f", with {metric}"
    pieces[-1] += "."
    if timestamp:
        pieces.append(f"Observed {timestamp}.")
    return " ".join(pieces)


def _build_multi_focus_chat_message(
    *,
    feed: str,
    picks: list[str],
    features_by_pick: dict[str, dict],
    retained: bool,
) -> str | None:
    lines: list[str] = []
    for pick in picks:
        feature = features_by_pick.get(pick)
        if not isinstance(feature, dict):
            continue
        if retained:
            lines.append(_build_history_focus_chat_message(feed=feed, feature=feature, pick=pick))
        else:
            lines.append(_build_focus_chat_message(feed=feed, feature=feature, pick=pick))
    if not lines:
        return None
    lines.append(
        "This answer uses the retained Ops history window, not the current live snapshot."
        if retained
        else "This answer uses the current displayed Ops snapshot."
    )
    return " ".join(lines)


def _build_focus_map_result(*, feed: str, payload: dict, feature: dict, watch: dict, effective_feeds: list[str], message: str | None = None) -> dict:
    subset_payload = dict(payload)
    subset_payload["geojson"] = {
        "type": "FeatureCollection",
        "features": [feature],
    }
    subset_payload["count"] = 1
    subset_payload["fit"] = True
    summary = message or _build_focus_chat_message(feed=feed, feature=feature)
    subset_payload["summary"] = summary
    subset_payload["message"] = summary
    subset_payload["watch_id"] = watch.get("watch_id")
    subset_payload["watch_context"] = watch
    subset_payload["effective_feeds"] = effective_feeds
    return subset_payload


def _build_ranked_focus_map_result(*, feed: str, payload: dict, features: list[dict], watch: dict, effective_feeds: list[str]) -> dict:
    """Return a requested ranked subset as a map payload, not one focused item."""
    subset_payload = dict(payload)
    subset_payload["geojson"] = {"type": "FeatureCollection", "features": features}
    subset_payload["count"] = len(features)
    subset_payload["fit"] = True
    label = _feed_display_name(feed)
    summary = f"Showing the {len(features)} largest active {label} by area."
    subset_payload["summary"] = summary
    subset_payload["message"] = summary
    subset_payload["watch_id"] = watch.get("watch_id")
    subset_payload["watch_context"] = watch
    subset_payload["effective_feeds"] = effective_feeds
    return subset_payload


def _load_history_focus_payload(
    *,
    feed: str,
    query: str,
    hints: dict | None = None,
    cache=None,
) -> dict | None:
    live_snapshot = load_current_state_snapshot(feed) or {}
    history_entries = load_current_state_history(feed)
    in_window, window_label = _history_entries_in_window(
        snapshot=live_snapshot,
        history_entries=history_entries,
        query=query,
        hints=hints,
    )
    history_payload = _build_history_event_payload(
        feed=feed,
        in_window=in_window,
        window_label=window_label,
    )
    if history_payload:
        _store_ops_history_payload(cache, feed=feed, payload=history_payload)
    return history_payload


def _select_deep_history_feeds(
    *,
    query: str,
    effective_feeds: list[str],
    report: dict,
    chat_history: list | None = None,
    cache=None,
    hints: dict | None = None,
    max_feeds: int = 2,
) -> list[str]:
    explicit = _mentioned_feeds(query, effective_feeds)
    if explicit:
        if _query_requests_deep_history(query, hints=hints):
            return explicit[:max_feeds]
        return explicit[:1]

    if not _query_requests_deep_history(query, hints=hints):
        inferred_feed = _infer_followup_feed(
            query=query,
            chat_history=chat_history,
            effective_feeds=effective_feeds,
            cache=cache,
            report=report,
        )
        if inferred_feed:
            return [inferred_feed]
        return []

    recent_feed = _recent_feed_from_history(chat_history, effective_feeds)
    if recent_feed:
        return [recent_feed]
    cached_feed = _recent_feed_from_cache(cache=cache, effective_feeds=effective_feeds)
    if cached_feed:
        return [cached_feed]
    if len(effective_feeds) == 1:
        return effective_feeds[:1]
    recent = report.get("recent_change_index") if isinstance(report, dict) else []
    chosen: list[str] = []
    for entry in recent or []:
        feed = str((entry or {}).get("feed") or "").strip()
        if feed and feed in effective_feeds and feed not in chosen:
            chosen.append(feed)
        if len(chosen) >= max_feeds:
            return chosen
    return effective_feeds[:max_feeds]


def _report_snapshot_by_feed(report: dict | None) -> dict[str, dict]:
    snapshots: dict[str, dict] = {}
    for item in (report or {}).get("feed_snapshots") or []:
        if not isinstance(item, dict):
            continue
        feed = str(item.get("feed") or "").strip()
        if feed:
            snapshots[feed] = item
    return snapshots


def _is_count_query(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    return any(re.search(pattern, text) for pattern in COUNT_QUERY_PATTERNS)


def _query_explicitly_requests_current_snapshot(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    current_patterns = (
        r"\bcurrent\b",
        r"\bright now\b",
        r"\bactive now\b",
        r"\bcurrently\b",
        r"\bcurrent watch\b",
        r"\bcurrent snapshot\b",
        r"\bnow\b",
    )
    return any(re.search(pattern, text) for pattern in current_patterns)


def _feed_prefers_history_by_default(feed: str) -> bool:
    record = ops_feed_record(feed)
    timeline = record.get("timeline") if isinstance(record, dict) else {}
    if not isinstance(timeline, dict):
        return False
    if bool(timeline.get("preload_history")):
        return True
    mode = str(timeline.get("mode") or "").strip()
    presentation = {
        str(value).strip()
        for value in (record.get("presentation") or [])
        if str(value).strip()
    }
    return mode in {"full_snapshot", "additive_history"} or bool(presentation & {"ticker", "metric_values"})


def _feed_display_name(feed: str) -> str:
    names = {
        WILDFIRE_LIVE_FEED: "wildfires",
        HURRICANE_LIVE_FEED: "storms",
        "earthquakes": "earthquakes",
        "tsunamis": "tsunamis",
        "volcanoes": "volcanoes",
        "currency": "currencies",
        "usa_nws_alerts": "NWS alerts",
        "noaa_aurora": "aurora model cells",
        "noaa_swpc": "space weather alerts",
    }
    return names.get(feed, feed.replace("_", " "))


def _feed_singular_label(feed: str) -> str:
    names = {
        WILDFIRE_LIVE_FEED: "wildfire",
        HURRICANE_LIVE_FEED: "storm",
        "earthquakes": "earthquake",
        "tsunamis": "tsunami",
        "volcanoes": "volcano event",
        "currency": "currency rate",
        "usa_nws_alerts": "NWS alert",
        "noaa_aurora": "aurora model cell",
        "noaa_swpc": "space weather alert",
    }
    return names.get(feed, feed.replace("_", " "))


def _feed_status_time(snapshot: dict) -> str | None:
    for key in ("last_changed_at", "fetched_at", "last_checked_at"):
        formatted = _format_ops_timestamp(snapshot.get(key))
        if formatted:
            return formatted
    return None


def _feed_history_id_set(feed: str, summary: dict) -> set[str]:
    if not isinstance(summary, dict):
        return set()
    rows = []
    id_keys: tuple[str, ...] = ()
    if feed == "earthquakes":
        rows = summary.get("events") or []
        id_keys = ("event_id",)
    elif feed == "tsunamis":
        rows = summary.get("events") or []
        id_keys = ("event_id",)
    elif feed == "volcanoes":
        rows = summary.get("events") or []
        id_keys = ("event_id",)
    elif feed == WILDFIRE_LIVE_FEED:
        rows = summary.get("events") or []
        id_keys = ("event_id",)
    elif _is_hurricane_live_feed(feed):
        rows = summary.get("storms") or []
        id_keys = ("storm_id",)
    elif feed == "currency":
        rows = summary.get("rates") or []
        id_keys = ("currency_code",)
    elif feed == "noaa_swpc":
        rows = summary.get("alerts") or []
        id_keys = ("alert_id",)
    elif feed == "usa_nws_alerts":
        rows = summary.get("alerts") or []
        id_keys = ("alert_id",)

    ids: set[str] = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        for key in id_keys:
            value = str(row.get(key) or "").strip()
            if value:
                ids.add(value)
                break
    return ids


def _history_count_noun(feed: str) -> str:
    nouns = {
        "earthquakes": "earthquakes",
        "tsunamis": "tsunami events",
        "volcanoes": "volcano events",
        WILDFIRE_LIVE_FEED: "wildfires",
        HURRICANE_LIVE_FEED: "storms",
        "currency": "currency rates",
        "noaa_swpc": "space weather alerts",
        "usa_nws_alerts": "NWS alerts",
        "noaa_aurora": "aurora model cells",
    }
    return nouns.get(feed, _feed_display_name(feed))


def _feed_to_explore_pack(feed: str) -> str:
    mapping = {
        "earthquakes": "earthquakes",
        "tsunamis": "tsunamis",
        "volcanoes": "volcanoes",
        WILDFIRE_LIVE_FEED: "wildfires",
        HURRICANE_LIVE_FEED: "hurricanes",
    }
    return mapping.get(feed, "")


def _build_exact_event_explore_handoff(feed: str, identifier_value: str) -> str:
    pack_id = _feed_to_explore_pack(feed)
    noun = _history_count_noun(feed)
    identifier = str(identifier_value or "").strip()
    if not pack_id or not identifier:
        return (
            f"I could not find that {noun} record in the retained Ops window. "
            "Ops only keeps a bounded live-history window; use Explore for the full historical record."
        )
    return (
        f"I could not find that {noun} record in the retained Ops window. "
        f"Ops only keeps a bounded live-history window; try Explore for the full historical record: "
        f"/explore?pack={pack_id}&event_id={identifier}"
    )


def _history_entries_in_window(
    *,
    snapshot: dict,
    history_entries: list[dict],
    query: str,
    hints: dict | None = None,
) -> tuple[list[dict], str | None]:
    cutoff, window_label = _extract_history_window(query, hints=hints)
    if cutoff is None:
        return [], None
    timeline: list[dict] = []
    if isinstance(snapshot, dict):
        timeline.append(snapshot)
    timeline.extend(entry for entry in history_entries if isinstance(entry, dict))
    in_window: list[dict] = []
    for entry in timeline:
        observed_at = _history_observed_at(entry)
        if observed_at is None or observed_at < cutoff:
            continue
        in_window.append(entry)
    return in_window, window_label


def _build_history_event_payload(*, feed: str, in_window: list[dict], window_label: str | None) -> dict | None:
    if feed not in {"earthquakes", "tsunamis", "volcanoes", WILDFIRE_LIVE_FEED}:
        return None
    features: list[dict] = []
    seen_ids: set[str] = set()
    for entry in in_window:
        summary = entry.get("payload_summary") if isinstance(entry.get("payload_summary"), dict) else {}
        rows = summary.get("events") if isinstance(summary.get("events"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                lon = float(row.get("longitude"))
                lat = float(row.get("latitude"))
            except (TypeError, ValueError):
                continue
            identifier = str(row.get("event_id") or row.get("id") or "").strip()
            if not identifier:
                identifier = f"{feed}:{row.get('timestamp')}:{row.get('place') or row.get('location') or lat}:{lon}"
            if identifier in seen_ids:
                continue
            seen_ids.add(identifier)
            props = dict(row)
            props.setdefault("collector", feed)
            if feed == "volcanoes":
                props.setdefault("VEI", row.get("vei"))
            if feed == WILDFIRE_LIVE_FEED:
                acres = row.get("burned_acres")
                try:
                    props.setdefault("area_km2", float(acres) * 0.00404686)
                except (TypeError, ValueError):
                    pass
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": props,
                }
            )
    if not features:
        return None
    title = f"Ops {feed.replace('_', ' ').title()} History"
    label = window_label or "the retained window"
    return {
        "type": "events",
        "data_type": "events",
        "event_type": FEED_FOCUS_SPECS.get(feed, {}).get("label") or _feed_display_name(feed),
        "source_id": f"{feed}_history_ops",
        "dataset_name": title,
        "source_name": title,
        "summary": f"Showing {len(features)} retained {_history_count_noun(feed)} from {label}.",
        "count": len(features),
        "window_label": label,
        "fit": True,
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
    }


def _build_history_count_answer(*, feed: str, snapshot: dict, history_entries: list[dict], query: str, hints: dict | None = None) -> str | None:
    cutoff, _ = _extract_history_window(query, hints=hints)
    requested_hours = _requested_history_window_hours(query, hints=hints)
    configured_hours = _ops_history_retention_hours_for_snapshot(snapshot)
    in_window, window_label = _history_entries_in_window(
        snapshot=snapshot,
        history_entries=history_entries,
        query=query,
        hints=hints,
    )
    if window_label is None:
        return None

    noun = _history_count_noun(feed)
    if not in_window:
        available_count = len(history_entries)
        if available_count == 0:
            history_status = _get_live_state_status(feed, "history")
            if history_status == "cloud_unavailable":
                return f"I could not read cloud Ops history for {noun}, so I cannot answer for {window_label} right now."
            if history_status == "cloud_not_configured":
                return f"Cloud Ops history is not configured in this runtime for {noun}, so I cannot answer for {window_label}."
            return f"I do not have retained Ops history for {noun} in this environment yet, so I cannot answer for {window_label}."
        return f"I do not have any retained {noun} history entries covering {window_label}."

    unique_ids: set[str] = set()
    peak_count: int | None = None
    newest_time: datetime | None = None
    oldest_time: datetime | None = None
    for entry in in_window:
        summary = entry.get("payload_summary") if isinstance(entry.get("payload_summary"), dict) else {}
        unique_ids.update(_feed_history_id_set(feed, summary))
        count_value, _ = _active_count_for_feed(feed, summary, query.lower())
        if count_value is not None:
            peak_count = count_value if peak_count is None else max(peak_count, count_value)
        observed_at = _history_observed_at(entry)
        if observed_at is not None:
            newest_time = observed_at if newest_time is None or observed_at > newest_time else newest_time
            oldest_time = observed_at if oldest_time is None or observed_at < oldest_time else oldest_time

    if unique_ids:
        count = len(unique_ids)
        message = f"There {'was' if count == 1 else 'were'} {count} {noun} seen in retained Ops history over {window_label}."
    elif peak_count is not None:
        message = f"The peak retained count for {noun} over {window_label} was {peak_count}."
    else:
        return f"I found retained history for {noun} over {window_label}, but not a stable count field to summarize it yet."

    availability_prefix = ""
    if oldest_time and newest_time:
        retained_span = newest_time - oldest_time
        requested_span = None
        if cutoff is not None:
            requested_span = datetime.now(timezone.utc) - cutoff
        requested_exceeds_contract = bool(requested_hours and requested_hours > configured_hours)
        retained_is_shorter_than_request = bool(requested_span and retained_span < requested_span)
        if requested_exceeds_contract or retained_is_shorter_than_request:
            availability_prefix = (
                f"Ops only retains about {configured_hours} hours of history for {noun}, "
                f"so this answer uses the available retained window from "
                f"{oldest_time.strftime('%b %d, %Y %H:%M UTC')} to {newest_time.strftime('%b %d, %Y %H:%M UTC')}. "
            )
        else:
            message += f" Latest update: {newest_time.strftime('%b %d, %Y %H:%M UTC')}."
    return f"{availability_prefix}{message}".strip()


def _extract_history_metric_filter(query: str, feed: str) -> tuple[tuple[str, ...], str, float, str] | None:
    spec = FEED_HISTORY_METRIC_ALIASES.get(feed)
    if not spec:
        return None
    text = str(query or "").strip().lower()
    if not text:
        return None
    alias_pattern = "|".join(re.escape(alias) for alias in spec["aliases"])
    patterns = (
        (rf"\b(?:over|above|greater than|more than)\s+(?:{alias_pattern})\s+(\d+(?:\.\d+)?)\b", ">"),
        (rf"\b(?:under|below|less than)\s+(?:{alias_pattern})\s+(\d+(?:\.\d+)?)\b", "<"),
        (rf"\b(?:{alias_pattern})\s+(?:over|above|greater than|more than)\s+(\d+(?:\.\d+)?)\b", ">"),
        (rf"\b(?:{alias_pattern})\s+(?:under|below|less than)\s+(\d+(?:\.\d+)?)\b", "<"),
        (rf"\b(?:{alias_pattern})\s+(?:at least|>=)\s*(\d+(?:\.\d+)?)\b", ">="),
        (rf"\b(?:{alias_pattern})\s+(?:at most|<=)\s*(\d+(?:\.\d+)?)\b", "<="),
        (rf"\b(?:{alias_pattern})\s+(\d+(?:\.\d+)?)\+?\b", ">="),
    )
    for pattern, operator in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            threshold = float(match.group(1))
        except (TypeError, ValueError):
            continue
        return spec["metric_keys"], operator, threshold, str(spec["label"])
    return None


def _cached_history_features(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    geojson = payload.get("geojson")
    if not isinstance(geojson, dict):
        return []
    features = geojson.get("features")
    return features if isinstance(features, list) else []


def _feature_matches_metric_filter(feature: dict, metric_keys: tuple[str, ...], operator: str, threshold: float) -> bool:
    value = _feature_numeric_value(feature, metric_keys)
    if value is None:
        return False
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    return False


def _build_cached_history_followup_count_answer(*, feed: str, payload: dict, query: str) -> str | None:
    features = _cached_history_features(payload)
    if not features:
        return None
    window_label = str(payload.get("window_label") or "that retained window").strip()
    noun = _history_count_noun(feed)
    metric_filter = _extract_history_metric_filter(query, feed)
    if metric_filter is None:
        count = len(features)
        return f"There {'was' if count == 1 else 'were'} {count} {noun} in {window_label}."
    metric_keys, operator, threshold, metric_label = metric_filter
    filtered = [
        feature for feature in features
        if isinstance(feature, dict) and _feature_matches_metric_filter(feature, metric_keys, operator, threshold)
    ]
    count = len(filtered)
    threshold_text = int(threshold) if float(threshold).is_integer() else threshold
    return (
        f"There {'was' if count == 1 else 'were'} {count} {noun} with {metric_label} {operator} {threshold_text} "
        f"in {window_label}."
    )


def _wildfire_area_request(query: str, *, wildfire_context: bool = False) -> tuple[str, float, str] | None:
    """Parse a current-fire size request into the shared km² display unit."""
    text = str(query or "").strip().lower()
    if not text or (not wildfire_context and not any(token in text for token in ("fire", "wildfire"))):
        return None
    operator = ">="
    if re.search(r"\b(?:under|below|less than)\b", text):
        operator = "<"
    elif re.search(r"\b(?:and|or)\s+above\b|\bat\s+least\b", text):
        operator = ">="
    elif re.search(r"\b(?:over|above|greater than|more than)\b", text):
        operator = ">"
    # In this wildfire-only parser, a bare `km` means square kilometres.
    # Accept common operational shorthand and normalize every input unit before
    # applying the one shared area_km2 filter.
    match = re.search(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>acres?|hectares?|ha|km2|square\s*(?:kilometers?|kilometres?)|sq\.?\s*km|km)\b",
        text,
    )
    if match:
        unit = re.sub(r"\s+", "", match.group("unit").lower())
        value = float(match.group("value"))
        if unit in {"acre", "acres"}:
            value_km2 = value * 0.00404686
        elif unit in {"ha", "hectare", "hectares"}:
            value_km2 = value * 0.01
        else:
            value_km2 = value
        return operator, value_km2, f"{value_km2:.2f} km\u00b2"
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:acres?|acre)\b", text)
    if match:
        value_km2 = float(match.group(1)) * 0.00404686
        return operator, value_km2, f"{value_km2:.2f} km²"
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:km²|km2|square\s*kilometers?)\b", text)
    if match:
        value_km2 = float(match.group(1))
        return operator, value_km2, f"{value_km2:.2f} km²"
    if re.search(r"\b(?:show|list)\s+all\s+(?:wild)?fires?\b", text):
        return ">=", 0.0, "all sizes"
    return None


def _wildfire_country_request(query: str, *, wildfire_context: bool = False) -> str | None:
    """Return an ISO3 scope for explicit USA/Canada wildfire commands."""
    text = str(query or "").strip().lower()
    if not text or not wildfire_context:
        return None
    mentions_usa = bool(re.search(r"\b(?:usa|u\.?s\.?a\.?|united states|america)\b", text))
    mentions_canada = bool(re.search(r"\bcanada\b", text))
    excluding = bool(re.search(r"\b(?:hide|exclude|without|except|remove)\b", text))
    if mentions_canada and excluding and not mentions_usa:
        return "USA"
    if mentions_usa and excluding and not mentions_canada:
        return "CAN"
    if mentions_usa and not mentions_canada:
        return "USA"
    if mentions_canada and not mentions_usa:
        return "CAN"
    return None


def _try_wildfire_snapshot_filter_result(
    *,
    query: str,
    report: dict,
    effective_feeds: list[str],
    chat_history: list | None,
    cache,
) -> dict | None:
    if WILDFIRE_LIVE_FEED not in effective_feeds:
        return None
    explicit_wildfire = bool(re.search(r"\b(?:wild)?fires?\b", str(query or "").lower()))
    inferred_feed = _infer_followup_feed(
        query=query,
        chat_history=chat_history,
        effective_feeds=effective_feeds,
        cache=cache,
        report=report,
    )
    wildfire_context = explicit_wildfire or inferred_feed == WILDFIRE_LIVE_FEED
    requested = _wildfire_area_request(
        query,
        wildfire_context=wildfire_context,
    )
    country_scope = _wildfire_country_request(query, wildfire_context=wildfire_context)
    if requested is None and country_scope is None:
        return None
    # A country-only command requests the complete current roster for that
    # country rather than silently reapplying the 5 km² readability default.
    operator, threshold_km2, threshold_label = requested or (">=", 0.0, "all sizes")
    # The normal report intentionally ships only the map-readable wildfire
    # overview.  A direct filter is entitled to inspect the full current
    # snapshot, but still keeps low-area fires as markers rather than sending
    # their often enormous native perimeters across the interactive path.
    source_payload = _build_wildfire_display_payload(
        load_current_state_snapshot(WILDFIRE_LIVE_FEED),
        minimum_area_km2=0.0,
        perimeter_minimum_area_km2=None,
    )
    # Keep the pure report path useful in offline QA fixtures and when a
    # transient current-state read fails after the report was already built.
    if source_payload is None:
        source_payload = _report_display_payload_by_feed(report).get(WILDFIRE_LIVE_FEED)
    geojson = source_payload.get("geojson") if isinstance(source_payload, dict) else None
    features = geojson.get("features") if isinstance(geojson, dict) else None
    if not isinstance(features, list):
        return None
    filtered = [
        feature for feature in features
        if isinstance(feature, dict)
        and _feature_matches_metric_filter(feature, ("area_km2",), operator, threshold_km2)
        and (
            country_scope is None
            or str((feature.get("properties") or {}).get("iso3") or "").upper() == country_scope
        )
    ]
    filtered_payload = {
        **source_payload,
        "ops_min_area_km2": threshold_km2 if operator in {">", ">="} else None,
        "ops_show_all": threshold_km2 == 0 and operator == ">=",
        "ops_country_iso3": country_scope,
        "summary": f"Showing {len(filtered):,} current {country_scope + ' ' if country_scope else ''}wildfires at {operator} {threshold_label}.",
        "count": len(filtered),
        "geojson": {**geojson, "features": filtered},
    }
    display_payloads = [
        filtered_payload if str(item.get("source_id") or "") == str(source_payload.get("source_id") or "") else item
        for item in (report.get("display_payloads") or [])
        if isinstance(item, dict)
    ]
    return {
        "message": f"Showing all {len(filtered):,} current {country_scope + ' ' if country_scope else ''}wildfires with area {operator} {threshold_label}.",
        "display_payloads": display_payloads,
    }


def _load_exact_history_feature(
    *,
    feed: str,
    identifier_key: str | None,
    identifier_value: str | None,
    cache=None,
) -> tuple[dict, dict] | tuple[None, None]:
    if feed not in {"earthquakes", "tsunamis", "volcanoes", WILDFIRE_LIVE_FEED}:
        return None, None
    if not identifier_value:
        return None, None
    history_entries = load_current_state_history(feed)
    features: list[dict] = []
    for entry in history_entries:
        summary = entry.get("payload_summary") if isinstance(entry.get("payload_summary"), dict) else {}
        rows = summary.get("events") if isinstance(summary.get("events"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            identifier = str(
                row.get(identifier_key or "")
                or row.get("event_id")
                or row.get("storm_id")
                or row.get("incident_id")
                or ""
            ).strip()
            if not identifier or identifier.lower() != str(identifier_value).strip().lower():
                continue
            try:
                lon = float(row.get("longitude"))
                lat = float(row.get("latitude"))
            except (TypeError, ValueError):
                continue
            props = dict(row)
            props.setdefault("collector", feed)
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
            features.append(feature)
    if not features:
        if feed == "earthquakes":
            return _recover_exact_earthquake_feature(
                identifier_value=identifier_value,
                retention_hours=DEFAULT_OPS_HISTORY_RETENTION_HOURS,
                cache=cache,
            )
        return None, None
    payload = {
        "type": "events",
        "data_type": "events",
        "event_type": FEED_FOCUS_SPECS.get(feed, {}).get("label") or _feed_display_name(feed),
        "source_id": f"{feed}_history_ops",
        "dataset_name": f"Ops {feed.replace('_', ' ').title()} Exact Event",
        "source_name": f"Ops {feed.replace('_', ' ').title()} Exact Event",
        "summary": f"Showing retained {_feed_display_name(feed)} event {identifier_value}.",
        "count": len(features),
        "window_label": "the retained Ops window",
        "fit": True,
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
    }
    _store_ops_history_payload(cache, feed=feed, payload=payload)
    return payload, features[0]


def _earthquake_feature_to_row(feature: dict) -> dict | None:
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
    coords = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []
    if len(coords) < 2:
        return None
    timestamp_ms = props.get("time")
    magnitude = props.get("mag")
    if not isinstance(timestamp_ms, (int, float)) or magnitude is None:
        return None
    try:
        timestamp = datetime.fromtimestamp(float(timestamp_ms) / 1000.0, tz=timezone.utc)
        lon = float(coords[0])
        lat = float(coords[1])
        depth_km = float(coords[2]) if len(coords) > 2 else 0.0
        magnitude_value = float(magnitude)
    except (TypeError, ValueError, OverflowError):
        return None
    raw_id = str(feature.get("id") or "").strip()
    if not raw_id:
        return None
    event_id = raw_id if raw_id.startswith("us") else f"us{raw_id}"
    return {
        "event_id": event_id,
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "latitude": lat,
        "longitude": lon,
        "magnitude": magnitude_value,
        "depth_km": depth_km,
        "place": str(props.get("place") or "").strip(),
        "source": "usgs",
    }


def _recover_exact_earthquake_feature(
    *,
    identifier_value: str | None,
    retention_hours: int = DEFAULT_OPS_HISTORY_RETENTION_HOURS,
    cache=None,
) -> tuple[dict, dict] | tuple[None, None]:
    if requests is None:
        return None, None
    event_id = str(identifier_value or "").strip()
    if not event_id:
        return None, None
    try:
        response = requests.get(
            USGS_FDSN_EVENT_URL,
            params={"format": "geojson", "eventid": event_id},
            timeout=10,
        )
        if response.status_code >= 300:
            return None, None
        payload = response.json()
    except Exception:
        return None, None
    feature_payload = None
    if isinstance(payload, dict):
        if payload.get("type") == "Feature":
            feature_payload = payload
        else:
            features = payload.get("features")
            if isinstance(features, list) and features:
                feature_payload = features[0]
    if not isinstance(feature_payload, dict):
        return None, None
    row = _earthquake_feature_to_row(feature_payload)
    if not isinstance(row, dict):
        return None, None
    try:
        event_dt = datetime.strptime(str(row.get("timestamp") or ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None, None
    if event_dt < datetime.now(timezone.utc) - timedelta(hours=max(int(retention_hours), 1)):
        return None, None
    props = dict(row)
    props.setdefault("collector", "earthquakes")
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
        "properties": props,
    }
    recovered_payload = {
        "type": "events",
        "data_type": "events",
        "event_type": FEED_FOCUS_SPECS.get("earthquakes", {}).get("label") or "earthquake",
        "source_id": "earthquakes_recent_api_recovery",
        "dataset_name": "Ops Earthquakes Exact Event Recovery",
        "source_name": "Ops Earthquakes Exact Event Recovery",
        "summary": f"Showing recovered earthquake event {event_id} from the recent USGS window.",
        "count": 1,
        "window_label": "the retained Ops window",
        "fit": True,
        "geojson": {
            "type": "FeatureCollection",
            "features": [feature],
        },
    }
    _store_ops_history_payload(cache, feed="earthquakes", payload=recovered_payload)
    return recovered_payload, feature


def _active_count_for_feed(feed: str, summary: dict, query_text: str) -> tuple[int | None, str | None]:
    if not isinstance(summary, dict):
        return None, None
    if feed == WILDFIRE_LIVE_FEED:
        value = summary.get("active_count")
        return (int(value), "active wildfires") if value is not None else (None, None)
    if _is_hurricane_live_feed(feed):
        value = summary.get("storm_count")
        return (int(value), "active storms") if value is not None else (None, None)
    if feed == "volcanoes":
        value = summary.get("ongoing_count")
        if value is not None:
            return int(value), "ongoing volcano events"
        value = summary.get("event_count")
        return (int(value), "volcano events") if value is not None else (None, None)
    if feed == "earthquakes":
        value = summary.get("event_count")
        return (int(value), "earthquakes") if value is not None else (None, None)
    if feed == "tsunamis":
        value = summary.get("event_count")
        return (int(value), "tsunami events") if value is not None else (None, None)
    if feed == "currency":
        value = summary.get("rate_count")
        return (int(value), "currency rates") if value is not None else (None, None)
    if feed == "noaa_swpc":
        value = summary.get("alert_count")
        return (int(value), "space weather alerts") if value is not None else (None, None)
    if feed == "usa_nws_alerts":
        value = summary.get("alert_count")
        return (int(value), "NWS alerts") if value is not None else (None, None)
    if feed == "noaa_aurora":
        value = summary.get("visible_cell_count")
        return (int(value), "aurora model cells") if value is not None else (None, None)
    for key in ("active_count", "ongoing_count", "storm_count", "event_count", "incident_count", "rate_count"):
        value = summary.get(key)
        if value is not None:
            return int(value), _feed_display_name(feed)
    return None, None


def _severity_rank(scale: str) -> tuple[int, int]:
    text = str(scale or "").strip().upper()
    if len(text) < 2:
        return (-1, -1)
    family_order = {"G": 3, "S": 2, "R": 1}
    try:
        level = int(text[1:])
    except ValueError:
        level = -1
    return (family_order.get(text[:1], 0), level)


def _try_warning_severity_answer(*, effective_feeds: list[str], report: dict) -> str | None:
    if "noaa_swpc" not in effective_feeds:
        return None
    snapshot = _report_snapshot_by_feed(report).get("noaa_swpc") or {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    active_scales = [str(value or "").strip().upper() for value in (summary.get("active_scales") or []) if str(value or "").strip()]
    if not active_scales:
        alert_count = summary.get("alert_count")
        if alert_count == 0:
            return "There are no active space weather alerts in the current watch."
        return None
    top_scale = max(active_scales, key=_severity_rank)
    alerts = [item for item in (summary.get("alerts") or []) if isinstance(item, dict)]
    matching = [item for item in alerts if str(item.get("noaa_scale") or "").strip().upper() == top_scale]
    top_summary = str((matching[0] or {}).get("summary") or "").strip() if matching else ""
    freshness = _feed_status_time(snapshot)
    if top_summary and freshness:
        return f"The highest active space weather warning is {top_scale}. {top_summary}. Last update: {freshness}."
    if top_summary:
        return f"The highest active space weather warning is {top_scale}. {top_summary}."
    if freshness:
        return f"The highest active space weather warning in the current watch is {top_scale}. Last update: {freshness}."
    return f"The highest active space weather warning in the current watch is {top_scale}."


_NWS_SEVERITY_RANK = {
    "Unknown": 0,
    "Minor": 1,
    "Moderate": 2,
    "Severe": 3,
    "Extreme": 4,
}


def _query_requests_nws_severity_increase(query: str) -> bool:
    text = str(query or "").strip().lower()
    if not text:
        return False
    if not re.search(r"\b(severity|severe|warning|warnings|alert|alerts)\b", text):
        return False
    increase_terms = (
        r"\bincreased?\b",
        r"\bescalat",
        r"\bworsen",
        r"\bmore severe\b",
        r"\bhigher severity\b",
        r"\bupgraded?\b",
    )
    return any(re.search(pattern, text) for pattern in increase_terms)


def _nws_severity_score(value: object) -> int:
    text = str(value or "").strip()
    return _NWS_SEVERITY_RANK.get(text, -1)


def _nws_alerts_from_snapshot(snapshot: dict | None) -> list[dict]:
    if not isinstance(snapshot, dict):
        return []
    summary = snapshot.get("payload_summary") if isinstance(snapshot.get("payload_summary"), dict) else {}
    if not summary and isinstance(snapshot.get("summary"), dict):
        summary = snapshot.get("summary") or {}
    alerts = summary.get("alerts") if isinstance(summary.get("alerts"), list) else []
    return [alert for alert in alerts if isinstance(alert, dict)]


def _short_nws_area(area: object) -> str:
    parts = [p.strip() for p in str(area or "").split(";") if p.strip()]
    if not parts:
        return ""
    if len(parts) <= 2:
        return "; ".join(parts)
    return "; ".join(parts[:2]) + f" +{len(parts) - 2} more"


def _nws_alert_label(alert: dict) -> str:
    event = str(alert.get("event") or "NWS alert").strip()
    area = _short_nws_area(alert.get("area"))
    if area:
        return f"{event} - {area}"
    return event


def _format_nws_severity_change(alert: dict, first_severity: str, current_severity: str) -> str:
    label = _nws_alert_label(alert)
    message_type = str(alert.get("message_type") or "").strip()
    suffix = f" ({message_type})" if message_type else ""
    return f"{label}: {first_severity} to {current_severity}{suffix}"


def _try_nws_severity_increase_answer(
    *,
    query: str,
    effective_feeds: list[str],
    chat_history: list | None,
    report: dict,
    cache,
    hints: dict | None = None,
) -> str | None:
    if "usa_nws_alerts" not in effective_feeds:
        return None
    if not _query_requests_nws_severity_increase(query):
        return None
    feed = _infer_followup_feed(
        query=query,
        chat_history=chat_history,
        effective_feeds=effective_feeds,
        cache=cache,
        report=report,
    )
    if feed and feed != "usa_nws_alerts":
        return None

    live_snapshot = load_current_state_snapshot("usa_nws_alerts") or {}
    history_entries = load_current_state_history("usa_nws_alerts")
    cutoff, window_label = _extract_history_window(query, hints=hints)
    if cutoff is None:
        cutoff = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(
            hours=_ops_history_retention_hours_for_snapshot(live_snapshot)
        )
        window_label = "the retained Ops window"

    active_by_id: dict[str, dict] = {}
    for alert in _nws_alerts_from_snapshot(live_snapshot):
        alert_id = str(alert.get("alert_id") or "").strip()
        if alert_id:
            active_by_id[alert_id] = alert

    if not active_by_id:
        return "There are no active NWS alerts in the current snapshot to compare for severity increases."

    observations: list[tuple[datetime, str, dict]] = []
    for entry in history_entries:
        observed_at = _history_observed_at(entry)
        if observed_at is None or observed_at < cutoff:
            continue
        delta = entry.get("delta") if isinstance(entry.get("delta"), dict) else {}
        for bucket in ("added", "updated"):
            rows = delta.get(bucket) if isinstance(delta.get(bucket), list) else []
            for alert in rows:
                if isinstance(alert, dict):
                    observations.append((observed_at, bucket, alert))

    current_time = _history_observed_at(live_snapshot) or datetime.now(timezone.utc)
    for alert in active_by_id.values():
        observations.append((current_time, "current", alert))

    first_by_id: dict[str, tuple[datetime, dict]] = {}
    for observed_at, _bucket, alert in sorted(observations, key=lambda item: item[0]):
        alert_id = str(alert.get("alert_id") or "").strip()
        if not alert_id or alert_id not in active_by_id:
            continue
        if _nws_severity_score(alert.get("severity")) < 0:
            continue
        first_by_id.setdefault(alert_id, (observed_at, alert))

    increased: list[tuple[int, str]] = []
    for alert_id, current_alert in active_by_id.items():
        first_observation = first_by_id.get(alert_id)
        if not first_observation:
            continue
        first_alert = first_observation[1]
        first_score = _nws_severity_score(first_alert.get("severity"))
        current_score = _nws_severity_score(current_alert.get("severity"))
        if current_score > first_score:
            first_severity = str(first_alert.get("severity") or "Unknown")
            current_severity = str(current_alert.get("severity") or "Unknown")
            increased.append((current_score, _format_nws_severity_change(current_alert, first_severity, current_severity)))

    if increased:
        increased.sort(key=lambda item: item[0], reverse=True)
        shown = [line for _score, line in increased[:8]]
        more = len(increased) - len(shown)
        extra = f" Plus {more} more." if more > 0 else ""
        return (
            f"{len(increased)} active NWS alert{' has' if len(increased) == 1 else 's have'} increased in severity over {window_label}: "
            + "; ".join(shown)
            + extra
        )

    if not observations:
        history_status = _get_live_state_status("usa_nws_alerts", "history")
        if history_status == "cloud_unavailable":
            return "I could not read cloud Ops history for NWS alerts, so I cannot compare severity increases right now."
        if history_status == "cloud_not_configured":
            return "Cloud Ops history is not configured in this runtime for NWS alerts, so I cannot compare severity increases."
        return "I do not have retained NWS alert history in this environment yet, so I cannot compare severity increases."

    return f"I found retained NWS alert history for {window_label}, but none of the currently active alerts show a severity increase in that retained window."


def _format_lat_band(north_boundary: object, south_boundary: object) -> str | None:
    try:
        north = float(north_boundary) if north_boundary is not None else None
    except (TypeError, ValueError):
        north = None
    try:
        south = float(south_boundary) if south_boundary is not None else None
    except (TypeError, ValueError):
        south = None
    parts: list[str] = []
    if north is not None:
        parts.append(f"north of about {abs(north):.0f}N")
    if south is not None:
        parts.append(f"south of about {abs(south):.0f}S")
    if not parts:
        return None
    return " and ".join(parts)


def _try_aurora_visibility_answer(*, effective_feeds: list[str], report: dict) -> str | None:
    if "noaa_aurora" not in effective_feeds:
        return None
    snapshot = _report_snapshot_by_feed(report).get("noaa_aurora") or {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    if not summary:
        return None
    visible = bool(summary.get("aurora_visible"))
    max_probability = summary.get("max_probability")
    band = _format_lat_band(summary.get("north_boundary_lat"), summary.get("south_boundary_lat"))
    forecast_time = _format_ops_timestamp(summary.get("forecast_time")) or str(summary.get("forecast_time") or "").strip()
    if not visible:
        if forecast_time:
            return f"The latest aurora model frame does not show a visible band right now. Model time: {forecast_time}."
        return "The latest aurora model frame does not show a visible band right now."
    probability_text = ""
    if max_probability not in (None, ""):
        probability_text = f" with peak probability around {max_probability}%"
    if band and forecast_time:
        return f"The latest aurora model frame shows a visible band {band}{probability_text}. Model time: {forecast_time}."
    if band:
        return f"The latest aurora model frame shows a visible band {band}{probability_text}."
    if forecast_time:
        return f"The latest aurora model frame shows a visible band{probability_text}. Model time: {forecast_time}."
    return f"The latest aurora model frame shows a visible band{probability_text}."


def _focus_feed_from_query(
    *,
    query: str,
    chat_history: list | None,
    effective_feeds: list[str],
    cache,
) -> str | None:
    mentioned = _mentioned_feeds(query, effective_feeds)
    if len(mentioned) == 1:
        return mentioned[0]
    recent_feed = _recent_feed_from_history(chat_history, effective_feeds)
    if recent_feed:
        return recent_feed
    cached_feed, _payload, _feature = _resolve_cached_focus_target(
        cache=cache,
        report={"display_payloads": []},
        effective_feeds=effective_feeds,
    )
    return cached_feed


def _try_focus_result(
    *,
    query: str,
    report: dict,
    watch: dict,
    effective_feeds: list[str],
    chat_history: list | None,
    cache,
    hints: dict | None = None,
) -> dict | None:
    lower = str(query or "").strip().lower()
    if not lower:
        return None

    show_only = _query_requests_map_focus(lower) and not _query_requests_superlative(lower)
    if show_only:
        singular_focus = _query_requests_singular_focus(lower)
        cached_feed, cached_payload, cached_feature = _resolve_cached_focus_target(
            cache=cache,
            report=report,
            effective_feeds=effective_feeds,
        )
        if singular_focus and cached_feed and cached_payload and cached_feature:
            return _build_focus_map_result(
                feed=cached_feed,
                payload=cached_payload,
                feature=cached_feature,
                watch=watch,
                effective_feeds=effective_feeds,
                message=f"Showing {_focus_feature_name(cached_feed, cached_feature.get('properties') or {})}.",
            )
        history_feed, history_payload = _resolve_cached_history_payload(
            cache=cache,
            effective_feeds=effective_feeds,
        )
        history_features = (history_payload.get("geojson") or {}).get("features") if isinstance((history_payload or {}).get("geojson"), dict) else []
        if history_feed and isinstance(history_features, list) and history_features:
            payload = dict(history_payload)
            payload["fit"] = True
            return payload
        if cached_feed and cached_payload and cached_feature:
            return _build_focus_map_result(
                feed=cached_feed,
                payload=cached_payload,
                feature=cached_feature,
                watch=watch,
                effective_feeds=effective_feeds,
                message=f"Showing {_focus_feature_name(cached_feed, cached_feature.get('properties') or {})}.",
            )

    if not _query_requests_superlative(lower):
        return None

    picks = _superlative_picks(lower)
    if not picks:
        return None

    feed = _focus_feed_from_query(
        query=lower,
        chat_history=chat_history,
        effective_feeds=effective_feeds,
        cache=cache,
    )
    if not feed:
        return None

    ranked_match = re.search(r"\b(\d{1,2})\s+(?:biggest|largest)\b", lower)
    if feed == WILDFIRE_LIVE_FEED and ranked_match:
        requested_count = max(1, min(int(ranked_match.group(1)), 50))
        payload = _report_display_payload_by_feed(report).get(feed)
        spec = FEED_FOCUS_SPECS[feed]
        ranked_features = sorted(
            (
                feature for feature in _payload_features(payload)
                if _feature_numeric_value(feature, spec["metric_keys"]) is not None
            ),
            key=lambda feature: _feature_numeric_value(feature, spec["metric_keys"]) or 0,
            reverse=True,
        )[:requested_count]
        if ranked_features:
            _store_ops_focus_target(cache, feed=feed, payload=payload, feature=ranked_features[0])
            return _build_ranked_focus_map_result(
                feed=feed,
                payload=payload,
                features=ranked_features,
                watch=watch,
                effective_feeds=effective_feeds,
            )

    history_feed, history_payload = _resolve_cached_history_payload(
        cache=cache,
        effective_feeds=effective_feeds,
    )
    if history_feed == feed:
        features_by_pick: dict[str, dict] = {}
        stored_feature = None
        payload = history_payload if isinstance(history_payload, dict) else None
        for pick in picks:
            candidate_payload, feature, _score = _select_focus_candidate_from_payload(feed=feed, payload=history_payload, pick=pick)
            if candidate_payload and feature:
                payload = candidate_payload
                features_by_pick[pick] = feature
                if stored_feature is None:
                    stored_feature = feature
        if payload and stored_feature and features_by_pick:
            _store_ops_focus_target(cache, feed=feed, payload=payload, feature=stored_feature)
            focus_message = _build_multi_focus_chat_message(feed=feed, picks=picks, features_by_pick=features_by_pick, retained=True)
            if not focus_message:
                return None
            if _query_requests_map_focus(lower):
                return _build_focus_map_result(
                    feed=feed,
                    payload=payload,
                    feature=stored_feature,
                    watch=watch,
                    effective_feeds=effective_feeds,
                    message=focus_message,
                )
            return {
                "type": "chat",
                "message": focus_message,
            }

    if _query_requests_deep_history(lower, hints=hints):
        history_payload = _load_history_focus_payload(
            feed=feed,
            query=query,
            hints=hints,
            cache=cache,
        )
        features_by_pick = {}
        stored_feature = None
        payload = history_payload if isinstance(history_payload, dict) else None
        for pick in picks:
            candidate_payload, feature, _score = _select_focus_candidate_from_payload(feed=feed, payload=history_payload, pick=pick)
            if candidate_payload and feature:
                payload = candidate_payload
                features_by_pick[pick] = feature
                if stored_feature is None:
                    stored_feature = feature
        if payload and stored_feature and features_by_pick:
            _store_ops_focus_target(cache, feed=feed, payload=payload, feature=stored_feature)
            focus_message = _build_multi_focus_chat_message(feed=feed, picks=picks, features_by_pick=features_by_pick, retained=True)
            if not focus_message:
                return None
            if _query_requests_map_focus(lower):
                return _build_focus_map_result(
                    feed=feed,
                    payload=payload,
                    feature=stored_feature,
                    watch=watch,
                    effective_feeds=effective_feeds,
                    message=focus_message,
                )
            return {
                "type": "chat",
                "message": focus_message,
            }

    payload = None
    stored_feature = None
    features_by_pick = {}
    for pick in picks:
        candidate_payload, feature, _score = _select_focus_candidate(feed=feed, report=report, pick=pick)
        if candidate_payload and feature:
            payload = candidate_payload
            features_by_pick[pick] = feature
            if stored_feature is None:
                stored_feature = feature
    if not payload or not stored_feature or not features_by_pick:
        return None

    _store_ops_focus_target(cache, feed=feed, payload=payload, feature=stored_feature)
    focus_message = _build_multi_focus_chat_message(feed=feed, picks=picks, features_by_pick=features_by_pick, retained=False)
    if not focus_message:
        return None

    if _query_requests_map_focus(lower):
        return _build_focus_map_result(
            feed=feed,
            payload=payload,
            feature=stored_feature,
            watch=watch,
            effective_feeds=effective_feeds,
            message=focus_message,
        )

    return {
        "type": "chat",
        "message": focus_message,
    }


def _try_exact_event_result(
    *,
    query: str,
    report: dict,
    watch: dict,
    effective_feeds: list[str],
    chat_history: list | None,
    cache,
) -> dict | None:
    identifier_key, identifier_value = _extract_identifier_reference(query)
    if not identifier_value:
        return None
    feed = _infer_followup_feed(
        query=query,
        chat_history=chat_history,
        effective_feeds=effective_feeds,
        cache=cache,
        report=report,
    )
    if not feed:
        return None

    payload = _report_display_payload_by_feed(report).get(feed) or _build_ops_payload_for_feed(feed)
    matched_payload, matched_feature = _find_feature_by_identifier(
        feed=feed,
        payload=payload,
        identifier_key=identifier_key,
        identifier_value=identifier_value,
    )
    if matched_payload and matched_feature:
        _store_ops_focus_target(cache, feed=feed, payload=matched_payload, feature=matched_feature)
        return _build_focus_map_result(
            feed=feed,
            payload=matched_payload,
            feature=matched_feature,
            watch=watch,
            effective_feeds=effective_feeds,
            message=f"Showing {_focus_feature_name(feed, matched_feature.get('properties') or {})}.",
        )

    history_feed, history_payload = _resolve_cached_history_payload(cache=cache, effective_feeds=effective_feeds)
    if history_feed == feed:
        matched_payload, matched_feature = _find_feature_by_identifier(
            feed=feed,
            payload=history_payload,
            identifier_key=identifier_key,
            identifier_value=identifier_value,
        )
        if matched_payload and matched_feature:
            _store_ops_focus_target(cache, feed=feed, payload=matched_payload, feature=matched_feature)
            return _build_focus_map_result(
                feed=feed,
                payload=matched_payload,
                feature=matched_feature,
                watch=watch,
                effective_feeds=effective_feeds,
                message=f"Showing {_focus_feature_name(feed, matched_feature.get('properties') or {})}.",
            )

    matched_payload, matched_feature = _load_exact_history_feature(
        feed=feed,
        identifier_key=identifier_key,
        identifier_value=identifier_value,
        cache=cache,
    )
    if matched_payload and matched_feature:
        _store_ops_focus_target(cache, feed=feed, payload=matched_payload, feature=matched_feature)
        return _build_focus_map_result(
            feed=feed,
            payload=matched_payload,
            feature=matched_feature,
            watch=watch,
            effective_feeds=effective_feeds,
            message=f"Showing {_focus_feature_name(feed, matched_feature.get('properties') or {})}.",
        )
    return {
        "type": "chat",
        "message": _build_exact_event_explore_handoff(feed, identifier_value),
    }


def _try_ocean_hotspot_answer(*, query: str, effective_feeds: list[str], report: dict) -> str | None:
    lower = str(query or "").lower()
    asks_ocean = bool(re.search(r"\b(ocean|sea|sst|temperature|water|buoy|buoys)\b", lower))
    asks_hot = bool(re.search(r"\b(hottest|warmest|highest|maximum|max|hot spot|hotspot)\b", lower))
    asks_cold = bool(re.search(r"\b(coldest|coolest|lowest|minimum|min)\b", lower))
    if not asks_ocean or not (asks_hot or asks_cold):
        return None
    if "noaa_ndbc" not in effective_feeds:
        return None

    snapshot = _report_snapshot_by_feed(report).get("noaa_ndbc") or {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    key = "coldest_buoy" if asks_cold and not asks_hot else "warmest_buoy"
    buoy = summary.get(key) if isinstance(summary.get(key), dict) else {}
    if not buoy:
        live_snapshot = load_current_state_snapshot("noaa_ndbc") or {}
        live_summary = live_snapshot.get("payload_summary") if isinstance(live_snapshot.get("payload_summary"), dict) else {}
        station_key = "coldest_station" if asks_cold and not asks_hot else "warmest_station"
        station = live_summary.get(station_key)
        rows = [row for row in (live_summary.get("buoys") or []) if isinstance(row, dict)]
        buoy = next((row for row in rows if row.get("station_id") == station), {})
    if not buoy:
        return None

    station = buoy.get("station_id") or "unknown"
    sst = buoy.get("sst_c")
    lat = buoy.get("lat")
    lon = buoy.get("lon")
    observed = buoy.get("obs_utc")
    label = "coldest" if asks_cold and not asks_hot else "warmest"
    parts = [f"The {label} live ocean point I can answer from Ops right now is NDBC buoy {station}"]
    if sst is not None:
        parts.append(f"with sea temperature {sst} deg C")
    if lat is not None and lon is not None:
        parts.append(f"at {lat}, {lon}")
    sentence = " ".join(parts) + "."
    if observed:
        sentence += f" Observed at {observed} UTC."
    sentence += " This is from the live buoy snapshot, not a full raw-grid max over every OISST raster cell."
    return sentence


def _try_direct_ops_answer(
    *,
    query: str,
    report: dict,
    watch: dict,
    effective_feeds: list[str],
    chat_history: list | None = None,
    hints: dict | None = None,
    cache=None,
    selected_popup: dict | None = None,
) -> str | None:
    text = str(query or "").strip()
    lower = text.lower()
    if not text:
        return None

    if "what feeds" in lower and "active" in lower:
        return f"Active watch has {len(effective_feeds)} feeds: {', '.join(effective_feeds)}."
    if re.search(r"\bhow many feeds\b", lower):
        return f"Active watch has {len(effective_feeds)} feeds."

    ocean_hotspot_answer = _try_ocean_hotspot_answer(
        query=text,
        effective_feeds=effective_feeds,
        report=report,
    )
    if ocean_hotspot_answer:
        return ocean_hotspot_answer

    if (
        ("highest severity" in lower or "most severe" in lower)
        and ("warning" in lower or "warnings" in lower or "alert" in lower or "alerts" in lower)
    ):
        warning_answer = _try_warning_severity_answer(
            effective_feeds=effective_feeds,
            report=report,
        )
        if warning_answer:
            return warning_answer

    generic_aurora_query = (
        "aurora" in lower
        and ("where" in lower or "see" in lower or "visible" in lower)
        and not re.search(r"\b(here|near me|my area|from here|from my|in my area)\b", lower)
    )
    if generic_aurora_query:
        aurora_answer = _try_aurora_visibility_answer(
            effective_feeds=effective_feeds,
            report=report,
        )
        if aurora_answer:
            return aurora_answer

    if _query_requests_area_impact(text):
        target = _resolve_area_target(
            query=text,
            watch=watch,
            selected_popup=selected_popup,
        )
        if target:
            area_answer = _build_area_impact_answer(
                report=report,
                effective_feeds=effective_feeds,
                target=target,
            )
            if area_answer:
                return area_answer

    if not _is_count_query(text):
        return None

    feed = _infer_followup_feed(
        query=text,
        chat_history=chat_history,
        effective_feeds=effective_feeds,
        cache=cache,
        report=report,
    )
    if not feed:
        return None
    snapshot = _report_snapshot_by_feed(report).get(feed) or {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}

    prefers_history = _feed_prefers_history_by_default(feed) and not _query_explicitly_requests_current_snapshot(text)
    if prefers_history or _query_requests_deep_history(text, hints=hints):
        history_entries = load_current_state_history(feed)
        live_snapshot = load_current_state_snapshot(feed) or {}
        history_answer = _build_history_count_answer(
            feed=feed,
            snapshot=live_snapshot,
            history_entries=history_entries,
            query=text,
            hints=hints,
        )
        in_window, window_label = _history_entries_in_window(
            snapshot=live_snapshot,
            history_entries=history_entries,
            query=text,
            hints=hints,
        )
        history_payload = _build_history_event_payload(
            feed=feed,
            in_window=in_window,
            window_label=window_label,
        )
        if history_payload:
            _store_ops_history_payload(cache, feed=feed, payload=history_payload)
        if history_answer:
            return history_answer

    cached_history_feed, cached_history_payload = _resolve_cached_history_payload(
        cache=cache,
        effective_feeds=effective_feeds,
    )
    if prefers_history and cached_history_feed == feed and isinstance(cached_history_payload, dict):
        cached_history_answer = _build_cached_history_followup_count_answer(
            feed=feed,
            payload=cached_history_payload,
            query=text,
        )
        if cached_history_answer:
            return cached_history_answer

    count, noun = _active_count_for_feed(feed, summary, lower)
    if count is None or not noun:
        return None

    freshness = _feed_status_time(snapshot)
    if freshness:
        return f"There are {count} {noun} in the current watch. Last update: {freshness}."
    return f"There are {count} {noun} in the current watch."


def _compact_history_entries(feed: str, entries: list[dict], *, limit: int = 6) -> list[dict]:
    compact: list[dict] = []
    for entry in entries[-limit:]:
        if not isinstance(entry, dict):
            continue
        summary = entry.get("payload_summary") if isinstance(entry.get("payload_summary"), dict) else {}
        compact.append(
            {
                "fetched_at": entry.get("fetched_at"),
                "last_checked_at": entry.get("last_checked_at"),
                "last_changed_at": entry.get("last_changed_at"),
                "collector_status": entry.get("collector_status"),
                "payload_hash": entry.get("payload_hash"),
                "previous_payload_hash": entry.get("previous_payload_hash"),
                "changed_since_previous": entry.get("changed_since_previous"),
                "summary": _compact_payload_summary(feed, summary, sample_limit=2),
            }
        )
    return compact


def build_targeted_history_context(
    *,
    query: str,
    effective_feeds: list[str],
    report: dict,
    chat_history: list | None = None,
    cache=None,
    hints: dict | None = None,
) -> dict | None:
    feeds = _select_deep_history_feeds(
        query=query,
        effective_feeds=effective_feeds,
        report=report,
        chat_history=chat_history,
        cache=cache,
        hints=hints,
    )
    if not feeds:
        return None
    feed_contexts: list[dict] = []
    for feed in feeds:
        entries = load_current_state_history(feed)
        feed_contexts.append(
            {
                "feed": feed,
                "retained_history_entry_count": len(entries),
                "history_entry_count_note": "This is the number of retained history snapshots, not the number of events/items.",
                "entries": _compact_history_entries(feed, entries),
            }
        )
    return {
        "requested_by_query": True,
        "feeds": feed_contexts,
    }


def run_ops_chat(
    *,
    query: str,
    chat_history: list | None,
    watch: dict,
    effective_feeds: list[str],
    ops_orchestrator,
    usage_recorder,
    cache,
    selected_popup: dict | None = None,
) -> dict:
    if not effective_feeds:
        return {
            "type": "chat",
            "message": "Ops has no active feeds in this watch yet.",
            "watch_id": watch.get("watch_id"),
            "watch_context": watch,
            "effective_feeds": [],
        }

    preloaded = ops_orchestrator.preprocess(
        query=query,
        watch_context={
            "label": watch.get("label"),
            "sources": effective_feeds,
            "available_sources": watch.get("available_feeds") or [],
            "inactive_sources": watch.get("inactive_feeds") or [],
            "geography": watch.get("geography"),
        },
    )
    hints = preloaded.get("hints") if isinstance(preloaded, dict) else {}
    watch_context = preloaded.get("watch_context") if isinstance(preloaded, dict) else {}
    report_history_feeds = effective_feeds if _query_requests_broad_recent_changes(query) else []

    report = build_ops_report(
        watch=watch,
        effective_feeds=effective_feeds,
        history_feeds=report_history_feeds,
    )
    if isinstance(getattr(cache, "map_state", None), dict):
        cache.map_state["ops_report"] = report

    nws_severity_answer = _try_nws_severity_increase_answer(
        query=query,
        effective_feeds=effective_feeds,
        chat_history=chat_history,
        report=report,
        cache=cache,
        hints=hints,
    )
    if nws_severity_answer:
        result = {
            "type": "chat",
            "message": nws_severity_answer,
            "summary": f"Ops watch: {watch.get('label') or 'Watch'} | feeds: {', '.join(effective_feeds)}",
            "watch_id": watch.get("watch_id"),
            "watch_context": watch,
            "effective_feeds": effective_feeds,
            "ops_report": report,
        }
        if report.get("display_payloads"):
            result["display_payloads"] = report.get("display_payloads")
        if report.get("geojson"):
            result["geojson"] = report["geojson"]
        return result

    wildfire_filter_result = _try_wildfire_snapshot_filter_result(
        query=query,
        report=report,
        effective_feeds=effective_feeds,
        chat_history=chat_history,
        cache=cache,
    )
    if wildfire_filter_result:
        result = {
            "type": "chat",
            "message": wildfire_filter_result["message"],
            "summary": f"Ops watch: {watch.get('label') or 'Watch'} | feeds: {', '.join(effective_feeds)}",
            "watch_id": watch.get("watch_id"),
            "watch_context": watch,
            "effective_feeds": effective_feeds,
            "ops_report": report,
            "display_payloads": wildfire_filter_result["display_payloads"],
        }
        if report.get("geojson"):
            result["geojson"] = report["geojson"]
        return result

    exact_event_result = _try_exact_event_result(
        query=query,
        report=report,
        watch=watch,
        effective_feeds=effective_feeds,
        chat_history=chat_history,
        cache=cache,
    )
    if exact_event_result:
        exact_event_result.setdefault("watch_id", watch.get("watch_id"))
        exact_event_result.setdefault("watch_context", watch)
        exact_event_result.setdefault("effective_feeds", effective_feeds)
        exact_event_result["ops_report"] = report
        if report.get("display_payloads") and "display_payloads" not in exact_event_result:
            exact_event_result["display_payloads"] = report.get("display_payloads")
        if report.get("geojson") and "geojson" not in exact_event_result:
            exact_event_result["geojson"] = report["geojson"]
        return exact_event_result

    focus_result = _try_focus_result(
        query=query,
        report=report,
        watch=watch,
        effective_feeds=effective_feeds,
        chat_history=chat_history,
        cache=cache,
        hints=hints,
    )
    if focus_result:
        focus_result.setdefault("watch_id", watch.get("watch_id"))
        focus_result.setdefault("watch_context", watch)
        focus_result.setdefault("effective_feeds", effective_feeds)
        focus_result["ops_report"] = report
        if report.get("display_payloads") and "display_payloads" not in focus_result:
            focus_result["display_payloads"] = report.get("display_payloads")
        if report.get("geojson") and "geojson" not in focus_result:
            focus_result["geojson"] = report["geojson"]
        if focus_result.get("type") == "chat":
            focus_result.setdefault(
                "summary",
                f"Ops watch: {watch.get('label') or 'Watch'} | feeds: {', '.join(effective_feeds)}",
            )
        return focus_result

    direct_answer = _try_direct_ops_answer(
        query=query,
        report=report,
        watch=watch,
        effective_feeds=effective_feeds,
        chat_history=chat_history,
        hints=hints,
        cache=cache,
        selected_popup=selected_popup,
    )
    selected_history_answer = _try_selected_history_answer(
        query=query,
        selected_popup=selected_popup,
        effective_feeds=effective_feeds,
    )
    if selected_history_answer:
        result = {
            "type": "chat",
            "message": selected_history_answer,
            "summary": f"Ops watch: {watch.get('label') or 'Watch'} | feeds: {', '.join(effective_feeds)}",
            "watch_id": watch.get("watch_id"),
            "watch_context": watch,
            "effective_feeds": effective_feeds,
            "ops_report": report,
        }
        if report.get("display_payloads"):
            result["display_payloads"] = report.get("display_payloads")
        if report.get("geojson"):
            result["geojson"] = report["geojson"]
        return result
    if direct_answer:
        result = {
            "type": "chat",
            "message": direct_answer,
            "summary": f"Ops watch: {watch.get('label') or 'Watch'} | feeds: {', '.join(effective_feeds)}",
            "watch_id": watch.get("watch_id"),
            "watch_context": watch,
            "effective_feeds": effective_feeds,
            "ops_report": report,
        }
        # The text answer and map must refer to the same current OVATION
        # issuance. The browser holds that frame until Aurora is toggled.
        if str(direct_answer).startswith("The latest aurora model frame"):
            result["ui_action"] = "freeze_aurora_latest"
        if report.get("display_payloads"):
            result["display_payloads"] = report.get("display_payloads")
        if report.get("geojson"):
            result["geojson"] = report["geojson"]
        return result

    targeted_history = build_targeted_history_context(
        query=query,
        effective_feeds=effective_feeds,
        report=report,
        chat_history=chat_history,
        cache=cache,
        hints=hints,
    )
    prompt_safe_report = _build_prompt_safe_ops_report(report)
    system_prompt = ops_orchestrator.build_system_prompt(watch_context=watch_context, hints=hints)
    llm_runtime = ops_orchestrator.build_llm_runtime_context(system_prompt)
    system_blocks = llm_runtime["system_blocks"]
    llm_selection = llm_runtime["llm_selection"]
    client = llm_runtime["client"]

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Active Ops watch JSON:\n" + json.dumps(watch_context, default=str, separators=(",", ":")),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Compact Ops report JSON:\n" + json.dumps(prompt_safe_report, default=str, separators=(",", ":")),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
    ]
    if targeted_history:
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Targeted feed history JSON:\n" + json.dumps(targeted_history, default=str, separators=(",", ":")),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        )
    if isinstance(selected_popup, dict):
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Selected popup JSON:\n" + json.dumps(selected_popup, default=str, separators=(",", ":")),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        )
    messages.extend(_history_messages(chat_history))
    messages.append({"role": "user", "content": query})

    response = client.messages.create(
        model=llm_selection.model,
        system=system_blocks,
        messages=messages,
        max_tokens=700,
        **sampling_kwargs(llm_selection.model, llm_selection.temperature),
    )
    if usage_recorder is not None:
        usage_recorder.record(response)
    message = _extract_text(response) or "Ops report loaded, but I could not produce a fuller answer yet."
    summary = f"Ops watch: {watch.get('label') or 'Watch'} | feeds: {', '.join(effective_feeds)}"
    result = {
        "type": "chat",
        "message": message,
        "summary": summary,
        "watch_id": watch.get("watch_id"),
        "watch_context": watch_context,
        "effective_feeds": effective_feeds,
        "ops_report": report,
    }
    if report.get("display_payloads"):
        result["display_payloads"] = report.get("display_payloads")
    if targeted_history:
        result["ops_targeted_history"] = targeted_history
    if report.get("geojson"):
        result["geojson"] = report["geojson"]
    return result
