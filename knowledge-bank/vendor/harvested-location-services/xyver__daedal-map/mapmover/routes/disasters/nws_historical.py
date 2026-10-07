"""Historical NWS alert frames for WIP review and published Explore playback."""
from functools import lru_cache
import json
from pathlib import Path
import re

import pandas as pd
from fastapi import APIRouter, Request

from mapmover.auth_context import get_authenticated_user
from mapmover.catalog_surface import request_can_use_wip_catalog
from mapmover.duckdb_helpers import is_cloud_mode, parquet_available, path_to_uri, run_df, run_rows, select_rows
from mapmover.geometry_handlers import get_selection_geometries
from mapmover.paths import GLOBAL_DIR
from .helpers import msgpack_error, msgpack_response

router = APIRouter()
EVENTS = GLOBAL_DIR / "disasters" / "nws_alerts" / "events_with_zones.parquet"
V2_EVENTS = GLOBAL_DIR / "disasters" / "nws_alerts_v2" / "events.parquet"
YEARLY_TEXT_ROOT = GLOBAL_DIR / "disasters" / "nws_alerts" / "text_hydration" / "yearly"
_events_df: pd.DataFrame | None = None
_v2_events_df: pd.DataFrame | None = None
_history_payloads: dict[tuple[int, int], dict] = {}
_v2_history_payloads: dict[tuple[int, int], dict] = {}
_PRODUCT_ID_RE = re.compile(r"^(?P<year>\d{4})\d{8}-[A-Z0-9-]+$")
_TEXT_COVERAGE_YEARS = list(range(1986, 2026))


def _available_years() -> list[int]:
    """Discover years whose optional on-click bulletin text is hydrated."""
    if is_cloud_mode():
        return _TEXT_COVERAGE_YEARS
    if not YEARLY_TEXT_ROOT.exists():
        return []
    years = []
    for path in YEARLY_TEXT_ROOT.glob("*_finished.parquet"):
        match = re.fullmatch(r"(\d{4})_finished\.parquet", path.name)
        if match:
            years.append(int(match.group(1)))
    return sorted(set(years))


def _playback_years() -> list[int]:
    """Return continuous event-playback coverage, independent of detail text."""
    if is_cloud_mode():
        rows = run_rows(
            "SELECT DISTINCT CAST(substr(start_time, 1, 4) AS INTEGER) AS year "
            "FROM read_parquet(?) "
            "WHERE start_time IS NOT NULL "
            "ORDER BY year",
            [path_to_uri(EVENTS)],
        )
        return [int(row[0]) for row in rows if row and row[0] is not None]
    events = _load_events()
    timestamps = events.get("_start_at")
    if timestamps is None:
        return []
    years = timestamps.dropna().dt.year.astype(int).unique().tolist()
    return sorted(set(years))


def _load_events() -> pd.DataFrame:
    """Keep the compact event index resident; bulletin text remains on disk."""
    global _events_df
    if _events_df is None:
        _events_df = select_rows(EVENTS)
        if _events_df.empty and not is_cloud_mode():
            _events_df = pd.read_parquet(EVENTS)
        _events_df["_start_at"] = pd.to_datetime(_events_df["start_time"], utc=True, errors="coerce")
        _events_df["_end_at"] = pd.to_datetime(_events_df["end_time"], utc=True, errors="coerce")
    return _events_df


def _timestamp_utc_text(value: pd.Timestamp) -> str:
    return value.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _prepare_events_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        frame = frame.copy()
        frame["_start_at"] = pd.Series(dtype="datetime64[ns, UTC]")
        frame["_end_at"] = pd.Series(dtype="datetime64[ns, UTC]")
        return frame
    frame = frame.copy()
    frame["_start_at"] = pd.to_datetime(frame["start_time"], utc=True, errors="coerce")
    frame["_end_at"] = pd.to_datetime(frame["end_time"], utc=True, errors="coerce")
    return frame


def _query_cloud_events(where_sql: str, params: list) -> pd.DataFrame:
    uri = path_to_uri(EVENTS)
    frame = run_df(f"SELECT * FROM read_parquet(?) WHERE {where_sql}", [uri] + params)
    return _prepare_events_frame(frame)


def _events_for_range(start_year: int, end_year: int) -> pd.DataFrame:
    range_start = pd.Timestamp(f"{start_year}-01-01T00:00:00Z")
    range_end = pd.Timestamp(f"{end_year + 1}-01-01T00:00:00Z")
    if is_cloud_mode():
        return _query_cloud_events(
            "start_time < ? AND end_time >= ? AND end_time > start_time",
            [_timestamp_utc_text(range_end), _timestamp_utc_text(range_start)],
        )
    df = _load_events()
    return df[
        (df["_start_at"] < range_end)
        & (df["_end_at"] >= range_start)
        & (df["_end_at"] > df["_start_at"])
    ].copy()


def _events_active_at(moment: pd.Timestamp) -> pd.DataFrame:
    if is_cloud_mode():
        return _query_cloud_events(
            "start_time <= ? AND end_time > ?",
            [_timestamp_utc_text(moment), _timestamp_utc_text(moment)],
        )
    df = _load_events()
    return df[(df["_start_at"] <= moment) & (df["_end_at"] > moment)].copy()


def _load_v2_events() -> pd.DataFrame:
    """Keep the isolated lifecycle-v2 event index resident for local testing."""
    global _v2_events_df
    if _v2_events_df is None:
        _v2_events_df = pd.read_parquet(V2_EVENTS)
        _v2_events_df["_start_at"] = pd.to_datetime(_v2_events_df["start_time"], utc=True, errors="coerce")
        _v2_events_df["_end_at"] = pd.to_datetime(_v2_events_df["end_time"], utc=True, errors="coerce")
    return _v2_events_df


def _history_payload_for(
    df: pd.DataFrame,
    cache: dict[tuple[int, int], dict],
    start_year: int,
    end_year: int,
    summary_only: bool,
) -> dict:
    """Build a compact NWS playback payload for either source generation."""
    cache_key = (start_year, end_year)
    if cache_key not in cache:
        range_start = pd.Timestamp(f"{start_year}-01-01T00:00:00Z")
        range_end = pd.Timestamp(f"{end_year + 1}-01-01T00:00:00Z")
        frame = df[
            (df["_start_at"] < range_end)
            & (df["_end_at"] >= range_start)
            & (df["_end_at"] > df["_start_at"])
        ]
        needed = sorted({loc for value in frame.get("affected_loc_ids", []) for loc in str(value or "").split("|") if loc})
        county = get_selection_geometries(needed) if needed else {"features": []}
        counties = {
            str((feature.get("properties") or {}).get("loc_id")): feature.get("geometry")
            for feature in county.get("features", [])
            if (feature.get("properties") or {}).get("loc_id") and feature.get("geometry")
        }
        events = []
        for row in frame.to_dict("records"):
            starts_at, ends_at = row.get("_start_at"), row.get("_end_at")
            if pd.isna(starts_at) or pd.isna(ends_at):
                continue
            raw_geometry = row.get("native_geometry_geojson")
            events.append({
                "id": str(row.get("event_id") or ""),
                "start": int(starts_at.timestamp() * 1000),
                "end": int(ends_at.timestamp() * 1000),
                "point": [float(row["longitude"]), float(row["latitude"])],
                "geometry": json.loads(raw_geometry) if raw_geometry else None,
                "county_ids": [loc for loc in str(row.get("affected_loc_ids") or "").split("|") if loc],
                "properties": _event_properties(row),
            })
        cache[cache_key] = {
            "events": events, "counties": counties,
            "start": int(range_start.timestamp() * 1000),
            "end": int((range_end - pd.Timedelta(milliseconds=1)).timestamp() * 1000),
        }
    payload = cache[cache_key]
    if summary_only:
        return {"event_count": int(len(payload.get("events") or [])), "start": payload["start"], "end": payload["end"]}
    return payload


def _event_properties(row: dict) -> dict:
    """Return the popup-safe fields shared by single-frame and full-history APIs."""
    fields = (
        "event_id", "product_id", "event", "headline", "description", "instruction", "area",
        "expires", "certainty", "status", "message_type", "sender_name",
        "urgency", "severity", "is_emergency", "start_time", "end_time",
        "affected_area_names", "source_product_url", "phenomenon_code",
    )
    props = {
        key: value
        for key in fields
        if (value := row.get(key)) is not None
        and not (isinstance(value, float) and pd.isna(value))
    }
    # The VTEC geometry archive calls this affected_area_names; normalize it
    # to the live feed's popup contract without duplicating county geometry.
    if not props.get("area") and props.get("affected_area_names"):
        props["area"] = "\n".join(
            part.strip()
            for part in str(props["affected_area_names"]).split("|")
            if part.strip()
        )
    return props


def _check_access(req: Request, *, require_wip: bool) -> bool:
    if not require_wip:
        return True
    return request_can_use_wip_catalog(req, get_authenticated_user(req))


@lru_cache(maxsize=512)
def _load_yearly_text(product_id: str) -> dict:
    """Return one hydrated bulletin without preloading annual text into playback."""
    match = _PRODUCT_ID_RE.fullmatch(product_id)
    if not match:
        return {"product_id": product_id, "fetch_status": "invalid"}
    year = int(match.group("year"))
    path = YEARLY_TEXT_ROOT / f"{year}_finished.parquet"
    if year not in _available_years() or (not is_cloud_mode() and not path.exists()):
        return {"product_id": product_id, "fetch_status": "not_materialized"}
    columns = ["product_id", "headline", "description", "instruction", "area", "fetch_status"]
    frame = select_rows(path, columns=columns, exact_filters={"product_id": product_id})
    if frame.empty and not is_cloud_mode():
        frame = pd.read_parquet(path, columns=columns, filters=[("product_id", "=", product_id)])
    if frame.empty:
        return {"product_id": product_id, "fetch_status": "missing"}
    row = frame.iloc[0].to_dict()
    return {
        key: ("" if value is None or (isinstance(value, float) and pd.isna(value)) else value)
        for key, value in row.items()
    }


async def _historical_nws_alert_availability(req: Request, *, require_wip: bool):
    """Return event playback coverage and optional hydrated-detail coverage."""
    if not _check_access(req, require_wip=require_wip):
        return msgpack_error("WIP catalog access is limited to admin accounts.", 403)
    if not parquet_available(EVENTS):
        return msgpack_error("Historical NWS data is not installed.", 404)
    playback_years = _playback_years()
    if not playback_years:
        return msgpack_error("No historical NWS alert events are installed.", 404)
    text_years = _available_years()
    return msgpack_response({
        "available_years": playback_years,
        "newest_year": playback_years[-1],
        "hydrated_text_years": text_years,
    })


@router.get("/api/wip/nws-alerts/availability")
async def historical_nws_alert_availability(req: Request):
    return await _historical_nws_alert_availability(req, require_wip=True)


@router.get("/api/disasters/nws-alerts/availability")
async def published_historical_nws_alert_availability(req: Request):
    return await _historical_nws_alert_availability(req, require_wip=False)


async def _active_historical_nws_alerts(req: Request, at: str, *, require_wip: bool):
    """Return one historical NWS frame."""
    if not _check_access(req, require_wip=require_wip):
        return msgpack_error("WIP catalog access is limited to admin accounts.", 403)
    if not parquet_available(EVENTS):
        return msgpack_error("Historical NWS data is not installed.", 404)
    moment = pd.to_datetime(at, utc=True, errors="coerce")
    if pd.isna(moment):
        return msgpack_error("at must be an ISO timestamp", 400)
    active = _events_active_at(moment)
    needed = sorted({loc for value in active.get("affected_loc_ids", []) for loc in str(value or "").split("|") if loc})
    county = get_selection_geometries(needed) if needed else {"features": []}
    county_by_id = {(f.get("properties") or {}).get("loc_id"): f.get("geometry") for f in county.get("features", [])}
    features = []
    for row in active.to_dict("records"):
        # Cached frame columns are pandas Timestamps. They are query helpers,
        # not source data, and MessagePack cannot serialize them.
        props = _event_properties(row)
        props.update({"alert_id": row["event_id"], "severity": "Extreme" if row.get("is_emergency") else "Severe", "urgency": "Immediate"})
        raw = row.get("native_geometry_geojson")
        if raw:
            features.append({"type": "Feature", "geometry": json.loads(raw), "properties": {**props, "display": "polygon"}})
        else:
            for loc_id in str(row.get("affected_loc_ids") or "").split("|"):
                if county_by_id.get(loc_id):
                    features.append({"type": "Feature", "geometry": county_by_id[loc_id], "properties": {**props, "display": "county"}})
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]}, "properties": {**props, "display": "marker"}})
    return msgpack_response({"type": "FeatureCollection", "features": features, "active_alert_count": len(active)})


@router.get("/api/wip/nws-alerts")
async def active_historical_nws_alerts(req: Request, at: str):
    return await _active_historical_nws_alerts(req, at, require_wip=True)


@router.get("/api/disasters/nws-alerts")
async def published_active_historical_nws_alerts(req: Request, at: str):
    return await _active_historical_nws_alerts(req, at, require_wip=False)


async def _historical_nws_alerts(
    req: Request,
    start_year: int = 2025,
    end_year: int = 2025,
    summary_only: bool = False,
    *,
    require_wip: bool,
):
    """Return one selected local playback range, with shared counties deduplicated."""
    if not _check_access(req, require_wip=require_wip):
        return msgpack_error("WIP catalog access is limited to admin accounts.", 403)
    if not parquet_available(EVENTS):
        return msgpack_error("Historical NWS data is not installed.", 404)
    available_years = _playback_years()
    if not available_years:
        return msgpack_error("No historical NWS alert events are installed.", 404)
    start_year, end_year = sorted((start_year, end_year))
    # The timeline is a continuous requested domain. Sparse archive years are
    # valid empty spans, not a reason to reject the whole request.
    if start_year < available_years[0] or end_year > available_years[-1]:
        return msgpack_error("Requested NWS history is outside the installed 1986-2025 event coverage.", 404)
    cache_key = (start_year, end_year)
    if cache_key not in _history_payloads:
        range_start = pd.Timestamp(f"{start_year}-01-01T00:00:00Z")
        range_end = pd.Timestamp(f"{end_year + 1}-01-01T00:00:00Z")
        # The archive contains a small number of cancelled/partial products
        # whose recorded end is at or before their start.  They are naturally
        # absent from the one-frame query (end must be after the playhead), but
        # an incremental playback index would otherwise process their end
        # before their start and leave them permanently active.  Exclude them
        # at the source boundary so summary counts, geometry, and animation
        # all describe the same valid event set.
        frame = _events_for_range(start_year, end_year)
        if summary_only:
            return msgpack_response({
                "event_count": int(len(frame)),
                "start": int(range_start.timestamp() * 1000),
                "end": int((range_end - pd.Timedelta(milliseconds=1)).timestamp() * 1000),
            })
        needed = sorted({
            loc
            for value in frame.get("affected_loc_ids", [])
            for loc in str(value or "").split("|")
            if loc
        })
        county = get_selection_geometries(needed) if needed else {"features": []}
        counties = {
            str((feature.get("properties") or {}).get("loc_id")): feature.get("geometry")
            for feature in county.get("features", [])
            if (feature.get("properties") or {}).get("loc_id") and feature.get("geometry")
        }
        events = []
        for row in frame.to_dict("records"):
            starts_at = row.get("_start_at")
            ends_at = row.get("_end_at")
            if pd.isna(starts_at) or pd.isna(ends_at):
                continue
            raw_geometry = row.get("native_geometry_geojson")
            events.append({
                "id": str(row.get("event_id") or ""),
                "start": int(starts_at.timestamp() * 1000),
                "end": int(ends_at.timestamp() * 1000),
                "point": [float(row["longitude"]), float(row["latitude"])],
                "geometry": json.loads(raw_geometry) if raw_geometry else None,
                "county_ids": [loc for loc in str(row.get("affected_loc_ids") or "").split("|") if loc],
                "properties": _event_properties(row),
            })
        _history_payloads[cache_key] = {
            "events": events,
            "counties": counties,
            "start": int(range_start.timestamp() * 1000),
            "end": int((range_end - pd.Timedelta(milliseconds=1)).timestamp() * 1000),
            "available_years": available_years,
            "hydrated_text_years": _available_years(),
        }
    if summary_only:
        history = _history_payloads[cache_key]
        return msgpack_response({
            "event_count": int(len(history.get("events") or [])),
            "start": history["start"],
            "end": history["end"],
        })
    return msgpack_response(_history_payloads[cache_key])


@router.get("/api/wip/nws-alerts/history")
async def historical_nws_alerts(
    req: Request,
    start_year: int = 2025,
    end_year: int = 2025,
    summary_only: bool = False,
):
    return await _historical_nws_alerts(
        req,
        start_year=start_year,
        end_year=end_year,
        summary_only=summary_only,
        require_wip=True,
    )


@router.get("/api/disasters/nws-alerts/history")
async def published_historical_nws_alerts(
    req: Request,
    start_year: int = 2025,
    end_year: int = 2025,
    summary_only: bool = False,
):
    return await _historical_nws_alerts(
        req,
        start_year=start_year,
        end_year=end_year,
        summary_only=summary_only,
        require_wip=False,
    )


async def _historical_nws_alert_text(req: Request, product_id: str, *, require_wip: bool):
    """Load one historical bulletin's parsed text when its popup is opened."""
    if not _check_access(req, require_wip=require_wip):
        return msgpack_error("WIP catalog access is limited to admin accounts.", 403)
    product_id = str(product_id or "").strip()
    if not _PRODUCT_ID_RE.fullmatch(product_id):
        return msgpack_error("Invalid NWS product ID.", 400)
    try:
        return msgpack_response(_load_yearly_text(product_id))
    except Exception:
        return msgpack_error("Historical NWS bulletin text is unavailable.", 500)


@router.get("/api/wip/nws-alerts/text")
async def historical_nws_alert_text(req: Request, product_id: str):
    return await _historical_nws_alert_text(req, product_id, require_wip=True)


@router.get("/api/disasters/nws-alerts/text")
async def published_historical_nws_alert_text(req: Request, product_id: str):
    return await _historical_nws_alert_text(req, product_id, require_wip=False)


@router.get("/api/wip/nws-alerts-v2/availability")
async def historical_nws_alert_v2_availability(req: Request):
    """Availability for the isolated lifecycle-corrected NWS v2 source."""
    if not request_can_use_wip_catalog(req, get_authenticated_user(req)):
        return msgpack_error("WIP catalog access is limited to admin accounts.", 403)
    if not V2_EVENTS.exists():
        return msgpack_error("Historical NWS v2 WIP data is not installed.", 404)
    timestamps = _load_v2_events().get("_start_at")
    years = sorted(set(timestamps.dropna().dt.year.astype(int).tolist())) if timestamps is not None else []
    if not years:
        return msgpack_error("No historical NWS v2 alert events are installed.", 404)
    return msgpack_response({"available_years": years, "newest_year": years[-1], "hydrated_text_years": _available_years()})


@router.get("/api/wip/nws-alerts-v2/history")
async def historical_nws_alerts_v2(
    req: Request,
    start_year: int = 2025,
    end_year: int = 2025,
    summary_only: bool = False,
):
    """Serve isolated lifecycle-v2 playback without changing canonical NWS."""
    if not request_can_use_wip_catalog(req, get_authenticated_user(req)):
        return msgpack_error("WIP catalog access is limited to admin accounts.", 403)
    if not V2_EVENTS.exists():
        return msgpack_error("Historical NWS v2 WIP data is not installed.", 404)
    df = _load_v2_events()
    timestamps = df.get("_start_at")
    years = sorted(set(timestamps.dropna().dt.year.astype(int).tolist())) if timestamps is not None else []
    if not years:
        return msgpack_error("No historical NWS v2 alert events are installed.", 404)
    start_year, end_year = sorted((start_year, end_year))
    if start_year < years[0] or end_year > years[-1]:
        return msgpack_error("Requested NWS v2 history is outside the installed 1986-2025 event coverage.", 404)
    payload = _history_payload_for(df, _v2_history_payloads, start_year, end_year, summary_only)
    if summary_only:
        return msgpack_response(payload)
    return msgpack_response({
        **payload,
        "available_years": years,
        "hydrated_text_years": _available_years(),
    })
