"""Cross-disaster relationship endpoints."""

from __future__ import annotations

import pandas as pd
import re
import json
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from mapmover import logger
from mapmover.catalog_surface import catalog_surface_scope
from mapmover.data_loading import get_source_path, load_catalog, load_source_metadata
from mapmover.duckdb_helpers import (
    duckdb_available,
    is_cloud_mode,
    parquet_available,
    select_filtered_event_rows,
    select_rows,
)
from mapmover.paths import GLOBAL_DIR
from mapmover.runtime_config import get_runtime_config
from mapmover.storage_mode import get_runtime_mode
from mapmover.execution.event_execution import _build_single_event_message
from mapmover.execution.event_loading import resolve_event_parquet_path_for_source

from .helpers import msgpack_error, msgpack_response
from .earthquakes import get_earthquake_property_builders
from .landslides import get_landslide_property_builders
from .tsunamis import get_tsunami_property_builders
from .volcanoes import get_eruption_property_builders


router = APIRouter()


LINK_COLUMNS = [
    "parent_loc_id",
    "child_loc_id",
    "parent_event_id",
    "child_event_id",
    "link_type",
    "source",
    "confidence",
]

# Event-facing reads deliberately exclude heavy shape payloads.  Geometry is
# projected only when get_event callers explicitly request it.
EVENT_SUMMARY_COLUMNS = [
    "event_id", "source_event_id", "upstream_event_id", "storm_id", "eruption_id",
    "event_type", "name", "place", "location", "volcano_name", "fire_name",
    "loc_id", "parent_loc_id", "containing_loc_id", "iso3", "country", "region",
    "timestamp", "start_date", "end_date", "end_timestamp", "year", "last_updated",
    "latitude", "longitude", "end_latitude", "end_longitude",
    "magnitude", "depth_km", "severity", "VEI", "is_ongoing", "status",
    "area_km2", "burned_acres", "duration_days", "max_wind_kt", "min_pressure_mb",
    "max_category", "num_positions", "made_landfall", "has_wind_radii",
    "has_geometry", "has_progression", "runup_count", "aftershock_count",
    "mainshock_id", "sequence_id", "sequence_position", "sequence_count",
    "deaths", "injuries", "displaced", "damage_usd", "damage_millions",
    "source", "source_url", "data_quality",
]
EVENT_GEOMETRY_COLUMNS = ["perimeter", "track_coords", "bbox"]
EVENT_DETAIL_LIMIT = 500


def _json_safe_event_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, tuple):
        return [_json_safe_event_value(item) for item in value]
    if isinstance(value, list):
        return [_json_safe_event_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe_event_value(item) for key, item in value.items()}
    return value

EVENT_TABLES = {
    "earthquake": {
        "path": GLOBAL_DIR / "disasters/earthquakes/events.parquet",
        "builders": get_earthquake_property_builders,
    },
    "tsunami": {
        "path": GLOBAL_DIR / "disasters/tsunamis/events.parquet",
        "builders": get_tsunami_property_builders,
    },
    "volcano": {
        "path": GLOBAL_DIR / "disasters/volcanoes/events.parquet",
        "builders": get_eruption_property_builders,
    },
    "landslide": {
        "path": GLOBAL_DIR / "disasters/landslides/events.parquet",
        "builders": get_landslide_property_builders,
    },
}
EVENT_TYPE_PACK_IDS = {
    "earthquake": "earthquakes",
    "tsunami": "tsunamis",
    "volcano": "volcanoes",
    "hurricane": "hurricanes",
    "tornado": "tornadoes",
    "wildfire": "wildfires",
    "flood": "floods",
    "landslide": "landslides",
}

MAX_CHAIN_DEPTH = 2
MAX_DISCOVERY_LIMIT = 50
DISASTER_LINK_API_PACKS = {"earthquakes", "tsunamis", "volcanoes", "wildfires"}
EVENT_TYPE_ALIASES = {
    "earthquake": "earthquake",
    "earthquakes": "earthquake",
    "eq": "earthquake",
    "tsunami": "tsunami",
    "tsunamis": "tsunami",
    "volcano": "volcano",
    "volcanoes": "volcano",
    "eruption": "volcano",
    "eruptions": "volcano",
    "hurricane": "hurricane",
    "hurricanes": "hurricane",
    "storm": "hurricane",
    "tornado": "tornado",
    "tornadoes": "tornado",
    "wildfire": "wildfire",
    "wildfires": "wildfire",
    "fire": "wildfire",
    "fires": "wildfire",
    "flood": "flood",
    "floods": "flood",
    "landslide": "landslide",
    "landslides": "landslide",
}
EVENT_TYPE_LOC_TOKENS = {
    "earthquake": "EQ",
    "tsunami": "TSUN",
    "volcano": "VOLC",
    "hurricane": "HRCN",
    "tornado": "TORN",
    "wildfire": "FIRE",
    "flood": "FLOOD",
    "landslide": "LAND",
}
EXACT_EVENT_SOURCE_OVERRIDES = {
    "earthquakes_events": {
        "id_fields": ("event_id",),
        "metadata_source_id": "earthquakes_events",
        "parquet_path": GLOBAL_DIR / "disasters/earthquakes/events.parquet",
    },
    "hurricanes": {
        "id_fields": ("storm_id", "event_id"),
        "parquet_path": GLOBAL_DIR / "disasters/hurricanes/events.parquet",
    },
    "volcanoes_events": {
        "id_fields": ("event_id",),
        "metadata_source_id": "volcanoes_events",
        "parquet_path": GLOBAL_DIR / "disasters/volcanoes/events.parquet",
    },
    "tsunamis_events": {
        "id_fields": ("event_id",),
        "metadata_source_id": "tsunamis_events",
        "parquet_path": GLOBAL_DIR / "disasters/tsunamis/events.parquet",
    },
    "global_fire_atlas": {
        "id_fields": ("loc_id", "event_id"),
        "metadata_source_id": "global_fire_atlas",
        "parquet_path": GLOBAL_DIR / "disasters/wildfires/events.parquet",
    },
    "wildfires_usa": {
        "id_fields": ("loc_id", "event_id"),
        "metadata_source_id": "wildfires_usa",
        "parquet_path": GLOBAL_DIR / "disasters/wildfires/sources/usa/fires_enriched.parquet",
    },
    "can_wildfires": {
        "id_fields": ("loc_id", "event_id"),
        "metadata_source_id": "can_wildfires",
        "parquet_path": GLOBAL_DIR / "disasters/wildfires/sources/can/fires_enriched.parquet",
    },
    "tornadoes": {"id_fields": ("event_id",), "parquet_path": GLOBAL_DIR / "disasters/tornadoes/events.parquet"},
    "floods": {"id_fields": ("event_id",), "parquet_path": GLOBAL_DIR / "disasters/floods/events.parquet"},
    "landslides": {"id_fields": ("event_id",), "parquet_path": GLOBAL_DIR / "disasters/landslides/events.parquet"},
    "drought": {"id_fields": ("event_id",), "parquet_path": GLOBAL_DIR / "disasters/drought/events.parquet"},
}
EVENT_SEARCH_SOURCE_OVERRIDES = {
    "hurricanes": {"name_fields": ("name",), "country_field": None},
    "volcanoes_events": {"name_fields": ("volcano_name",), "country_field": "country"},
    "wildfires_usa": {"name_fields": ("fire_name",), "country_field": None},
    "can_wildfires": {"name_fields": ("fire_name",), "country_field": None},
}
LAT_FIELDS = ("lat", "latitude", "centroid_lat")
LON_FIELDS = ("lon", "longitude", "centroid_lon")
TIME_FIELDS = ("timestamp", "observed_at", "event_time", "start_time", "updated_at", "last_updated", "time", "date")
EXACT_EVENT_ID_RULES = [
    {"regex": re.compile(r"-TSUN-", re.IGNORECASE), "packs": ("tsunamis",), "strict": True},
    {"regex": re.compile(r"-FIRE-", re.IGNORECASE), "packs": ("wildfires",), "strict": True},
    {"regex": re.compile(r"^ts\d{4,}$", re.IGNORECASE), "packs": ("tsunamis",), "strict": True},
    {"regex": re.compile(r"^ve\d{4,}$", re.IGNORECASE), "packs": ("volcanoes",), "strict": True},
    {"regex": re.compile(r"^(?:dfo|gfd)-\d+$", re.IGNORECASE), "packs": ("floods",), "strict": True},
    {"regex": re.compile(r"^\d{7}[ns]\d{5}$", re.IGNORECASE), "packs": ("hurricanes",), "strict": True},
    {"regex": re.compile(r"^can-\d+$", re.IGNORECASE), "packs": ("tornadoes",), "strict": True},
    {"regex": re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE), "packs": ("wildfires",), "strict": True},
    {"regex": re.compile(r"^[A-Z]{2}\d{17,20}$", re.IGNORECASE), "packs": ("wildfires",), "strict": True},
    {"regex": re.compile(r"^[A-Z]{2}(?:-[A-Z]{2})?-\d{4}-[A-Za-z0-9-]+$", re.IGNORECASE), "packs": ("wildfires",), "strict": True},
    {"regex": re.compile(r"(?:-torn-|tornado)", re.IGNORECASE), "packs": ("tornadoes",), "strict": True},
    {"regex": re.compile(r"^(?:us|ak|at|av|ci|hv|mb|nc|nm|nn|pr|pt|se|tx|uu|uw)[a-z0-9._-]{3,}$", re.IGNORECASE), "packs": ("earthquakes",), "strict": True},
    {"regex": re.compile(r"^(?:iscgem|iscgemsup|rusms|noaa-sig|gcmtc|gcmtb|official|cent|ld|eqh|cdmg|aacse|ismpkansas|ok|snm|wes|flag|ew|ott)", re.IGNORECASE), "packs": ("earthquakes",), "strict": True},
    {"regex": re.compile(r"(?:irwin|mtbs|-fire-)", re.IGNORECASE), "packs": ("wildfires",), "strict": True},
]


def _load_exact_event_catalog() -> dict:
    """Load the published API surface used by the exact-event API.

    Exact-event resolution is an API operation, even when it is reached from
    an Explore URL.  Using the request's default Explore catalog surface here
    incorrectly hides API/MCP-only event sources before their Parquets can be
    queried.
    """
    with catalog_surface_scope("api"):
        catalog = load_catalog() or {}
    return catalog if isinstance(catalog, dict) else {}


def _classify_exact_event_identifier(identifier_value: str) -> tuple[list[str], bool]:
    normalized = str(identifier_value or "").strip()
    if not normalized:
        return [], False

    for rule in EXACT_EVENT_ID_RULES:
        if rule["regex"].search(normalized):
            return list(rule["packs"]), bool(rule["strict"])

    if normalized.isdigit():
        return ["tornadoes", "wildfires"], False

    return ["wildfires"], False


def _infer_exact_event_pack_hints(identifier_value: str) -> list[str]:
    hints, _strict = _classify_exact_event_identifier(identifier_value)
    return hints


def _catalog_event_sources_for_pack(pack_id: str) -> list[dict]:
    normalized_pack_id = str(pack_id or "").strip().lower()
    if not normalized_pack_id:
        return []

    catalog = _load_exact_event_catalog()
    candidates: list[dict] = []
    for source in catalog.get("sources", []):
        if not isinstance(source, dict):
            continue
        if str(source.get("pack_id") or "").strip().lower() != normalized_pack_id:
            continue
        if str(source.get("data_type") or "").strip().lower() != "events":
            continue

        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            continue

        override = EXACT_EVENT_SOURCE_OVERRIDES.get(source_id, {})
        path_text = str(source.get("path") or "").strip()
        path_parts = Path(path_text).parts if path_text else ()
        normalized_path = path_text.replace("\\", "/")
        event_type = str(
            source.get("event_type")
            or override.get("event_type")
            or normalized_pack_id.rstrip("s")
        ).strip().lower()

        candidate = {
            "pack_id": normalized_pack_id,
            "source_id": source_id,
            "event_type": event_type,
            "id_fields": tuple(override.get("id_fields") or ("event_id",)),
            "metadata_source_id": str(override.get("metadata_source_id") or source_id).strip(),
            "_path_depth": len(path_parts) if path_parts else 999,
            "_normalized_path": normalized_path,
        }
        if override.get("parquet_path"):
            candidate["parquet_path"] = override["parquet_path"]
        candidates.append(candidate)

    candidates.sort(
        key=lambda entry: (
            0 if "/sources/" not in str(entry.get("_normalized_path") or "") else 1,
            int(entry.get("_path_depth") or 999),
            str(entry.get("source_id") or ""),
        )
    )
    return candidates


def _wildfire_exact_source_priority(identifier_value: str, source_id: str) -> int:
    normalized = str(identifier_value or "").strip()
    normalized_source = str(source_id or "").strip().lower()
    if not normalized or normalized_source not in {"global_fire_atlas", "wildfires_usa", "can_wildfires"}:
        return 50

    if re.match(r"^[A-Z]{2}\d{17,20}$", normalized, re.IGNORECASE):
        if normalized_source == "wildfires_usa":
            return 0
        if normalized_source == "can_wildfires":
            return 1
        return 2

    if re.match(r"^[A-Z]{2}(?:-[A-Z]{2})?-\d{4}-[A-Za-z0-9-]+$", normalized, re.IGNORECASE):
        if normalized_source == "can_wildfires":
            return 0
        if normalized_source == "wildfires_usa":
            return 1
        return 2

    if re.search(r"(?:irwin|mtbs)", normalized, re.IGNORECASE):
        if normalized_source == "wildfires_usa":
            return 0
        return 1 if normalized_source == "global_fire_atlas" else 2

    if re.search(r"-fire-", normalized, re.IGNORECASE):
        if normalized_source in {"wildfires_usa", "can_wildfires"}:
            return 0
        return 2

    return 50


def _sort_exact_event_candidates(candidates: list[dict], identifier_value: str = "") -> list[dict]:
    normalized_identifier = str(identifier_value or "").strip()
    if not normalized_identifier:
        return candidates

    def _sort_key(entry: dict):
        pack_id = str(entry.get("pack_id") or "").strip().lower()
        source_id = str(entry.get("source_id") or "").strip()
        if pack_id == "wildfires":
            return (
                0,
                _wildfire_exact_source_priority(normalized_identifier, source_id),
                0 if "/sources/" in str(entry.get("_normalized_path") or "") else 1,
                int(entry.get("_path_depth") or 999),
                str(source_id),
            )
        return (
            1,
            0 if "/sources/" not in str(entry.get("_normalized_path") or "") else 1,
            int(entry.get("_path_depth") or 999),
            str(source_id),
        )

    return sorted(candidates, key=_sort_key)


def _get_exact_event_candidates(pack_id: str | None = None, identifier_value: str = "") -> list[dict]:
    if pack_id:
        return _sort_exact_event_candidates(
            _catalog_event_sources_for_pack(pack_id),
            identifier_value=identifier_value,
        )

    catalog = _load_exact_event_catalog()
    pack_ids: list[str] = []
    seen_pack_ids: set[str] = set()
    for source in catalog.get("sources", []):
        if not isinstance(source, dict):
            continue
        if str(source.get("data_type") or "").strip().lower() != "events":
            continue
        candidate_pack_id = str(source.get("pack_id") or "").strip().lower()
        if not candidate_pack_id or candidate_pack_id in seen_pack_ids:
            continue
        seen_pack_ids.add(candidate_pack_id)
        pack_ids.append(candidate_pack_id)

    candidates: list[dict] = []
    for candidate_pack_id in pack_ids:
        candidates.extend(_catalog_event_sources_for_pack(candidate_pack_id))
    return _sort_exact_event_candidates(candidates, identifier_value=identifier_value)


def _resolve_exact_event_parquet(source_id: str):
    return resolve_event_parquet_path_for_source(
        source_id,
        "events",
        get_source_path_func=get_source_path,
        load_source_metadata_func=load_source_metadata,
        is_cloud_mode_func=is_cloud_mode,
    )


def _resolve_exact_event_parquet_for_candidate(candidate: dict):
    direct_path = candidate.get("parquet_path")
    if direct_path:
        return Path(direct_path), {}
    return _resolve_exact_event_parquet(str(candidate.get("source_id") or ""))


def _load_exact_event_metadata(candidate: dict) -> dict:
    metadata_source_id = str(candidate.get("metadata_source_id") or "").strip()
    if not metadata_source_id:
        return {}
    metadata = load_source_metadata(metadata_source_id)
    return metadata if isinstance(metadata, dict) else {}


def _find_first_present(row: dict, candidates: tuple[str, ...]):
    for field in candidates:
        value = row.get(field)
        if value is not None and not pd.isna(value):
            return value
    return None


def _parse_bbox_props(value) -> tuple[float, float, float, float] | None:
    if value is None or pd.isna(value):
        return None
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return None
    if not isinstance(parsed, (list, tuple)) or len(parsed) != 4:
        return None
    try:
        min_lon, min_lat, max_lon, max_lat = [float(v) for v in parsed]
    except Exception:
        return None
    return min_lon, min_lat, max_lon, max_lat


def _parse_track_coords(value) -> list[list[float]] | None:
    if value is None or pd.isna(value):
        return None
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return None
    if not isinstance(parsed, list) or len(parsed) < 2:
        return None
    coords: list[list[float]] = []
    for item in parsed:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            lon = float(item[0])
            lat = float(item[1])
        except Exception:
            continue
        coords.append([lon, lat])
    return coords if len(coords) >= 2 else None


def _build_exact_event_geometry(props: dict, event_type: str) -> dict | None:
    lat = _find_first_present(props, LAT_FIELDS)
    lon = _find_first_present(props, LON_FIELDS)
    if lat is not None and lon is not None:
        return {"type": "Point", "coordinates": [float(lon), float(lat)]}

    bbox = _parse_bbox_props(props.get("bbox"))
    if bbox is not None:
        min_lon, min_lat, max_lon, max_lat = bbox
        props.setdefault("bbox_min_lon", min_lon)
        props.setdefault("bbox_min_lat", min_lat)
        props.setdefault("bbox_max_lon", max_lon)
        props.setdefault("bbox_max_lat", max_lat)
        centroid_lon = (min_lon + max_lon) / 2.0
        centroid_lat = (min_lat + max_lat) / 2.0
        props.setdefault("centroid_lon", centroid_lon)
        props.setdefault("centroid_lat", centroid_lat)
        return {"type": "Point", "coordinates": [centroid_lon, centroid_lat]}

    if event_type == "hurricane":
        track_coords = _parse_track_coords(props.get("track_coords"))
        if track_coords:
            mid_index = max(0, len(track_coords) // 2)
            centroid_lon = float(track_coords[mid_index][0])
            centroid_lat = float(track_coords[mid_index][1])
            props.setdefault("centroid_lon", centroid_lon)
            props.setdefault("centroid_lat", centroid_lat)
            return {"type": "Point", "coordinates": [centroid_lon, centroid_lat]}

    return None


def _build_exact_event_feature(row: dict, event_type: str, source_id: str, pack_id: str, identifier_field: str, metadata: dict | None = None) -> dict | None:
    props = {}
    for key, value in row.items():
        if value is None or pd.isna(value):
            continue
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, pd.Timestamp):
            value = value.isoformat()
        props[key] = value

    exact_value = str(props.get(identifier_field) or "").strip()
    if exact_value and "event_id" not in props:
        props["event_id"] = exact_value
    props["event_type"] = props.get("event_type") or event_type
    geometry = _build_exact_event_geometry(props, event_type)
    if geometry is None:
        return None
    metadata = metadata or {}
    source_name = str(metadata.get("source_name", source_id))
    source_url = str(metadata.get("source_url", ""))

    payload = {
        "type": "events",
        "data_type": "events",
        "source_id": source_id,
        "pack_id": pack_id,
        "event_type": event_type,
        "geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": props,
                }
            ],
        },
        "count": 1,
        "summary": f"Showing {pack_id} event {props.get('event_id') or exact_value}",
        "sources": [{
            "id": source_id,
            "name": source_name,
            "url": source_url,
        }],
    }
    message = _build_single_event_message(event_type, props, query_text=f"show {event_type} event")
    if message:
        payload["message"] = message
    return payload


def _query_exact_event(candidate: dict, identifier_field: str, identifier_value: str) -> pd.DataFrame:
    parquet_path, _metadata = _resolve_exact_event_parquet_for_candidate(candidate)
    variants = [identifier_value]
    if isinstance(identifier_value, str):
        lowered = identifier_value.lower()
        uppered = identifier_value.upper()
        for variant in (lowered, uppered):
            if variant not in variants:
                variants.append(variant)

    for variant in variants:
        df = select_rows(
            parquet_path,
            exact_filters={identifier_field: variant},
        )
        if not df.empty:
            return df

    return pd.DataFrame()


def _query_exact_event_projected(
    candidate: dict,
    identifier_field: str,
    identifier_value: str,
    *,
    include_geometry: bool = False,
) -> pd.DataFrame:
    """Resolve one event while projecting away shape columns by default."""
    parquet_path, _metadata = _resolve_exact_event_parquet_for_candidate(candidate)
    columns = list(EVENT_SUMMARY_COLUMNS)
    if identifier_field not in columns:
        columns.append(identifier_field)
    if include_geometry:
        columns.extend(EVENT_GEOMETRY_COLUMNS)
    variants = [identifier_value]
    if isinstance(identifier_value, str):
        for variant in (identifier_value.lower(), identifier_value.upper()):
            if variant not in variants:
                variants.append(variant)
    for variant in variants:
        df = select_rows(
            parquet_path,
            columns=columns,
            exact_filters={identifier_field: variant},
            limit=1,
        )
        if not df.empty:
            return df
    return pd.DataFrame()


def _resolve_event_record(
    identifier_value: str,
    *,
    pack_id: str | None = None,
    include_geometry: bool = False,
) -> tuple[dict, dict] | None:
    normalized_identifier = str(identifier_value or "").strip()
    if not normalized_identifier:
        return None
    candidates = _get_exact_event_candidates(
        str(pack_id).strip().lower() if pack_id else None,
        identifier_value=normalized_identifier,
    )
    if not pack_id:
        hinted_packs, strict_hint = _classify_exact_event_identifier(normalized_identifier)
        if hinted_packs:
            hinted = set(hinted_packs)
            candidates = sorted(candidates, key=lambda entry: 0 if entry["pack_id"] in hinted else 1)
            if strict_hint:
                candidates = [entry for entry in candidates if entry["pack_id"] in hinted]

    for candidate in candidates:
        for identifier_field in candidate.get("id_fields") or ("event_id",):
            try:
                df = _query_exact_event_projected(
                    candidate,
                    identifier_field,
                    normalized_identifier,
                    include_geometry=include_geometry,
                )
            except Exception as exc:
                logger.warning(
                    "Projected event lookup failed for %s.%s=%s: %s",
                    candidate.get("source_id"), identifier_field, normalized_identifier, exc,
                )
                continue
            if df.empty:
                continue
            row = {
                str(key): _json_safe_event_value(value)
                for key, value in df.iloc[0].to_dict().items()
                if _json_safe_event_value(value) is not None
            }
            exact_value = str(row.get(identifier_field) or normalized_identifier).strip()
            row.setdefault("event_id", exact_value)
            return candidate, row
    return None


def _event_relationship_rows(event_id: str, *, depth: int, limit: int) -> dict:
    """Traverse the event graph by event IDs, never by shared geography loc_ids."""
    links_path = GLOBAL_DIR / "disasters/links.parquet"
    if not parquet_available(links_path):
        return {"depth": depth, "links": [], "count": 0, "truncated": False}

    effective_depth = max(1, min(int(depth or 1), MAX_CHAIN_DEPTH))
    effective_limit = max(1, min(int(limit or 100), EVENT_DETAIL_LIMIT))
    queue: list[tuple[str, int]] = [(event_id, 0)]
    visited: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    links: list[dict] = []

    while queue and len(links) < effective_limit:
        current_event_id, current_depth = queue.pop(0)
        if current_event_id in visited:
            continue
        visited.add(current_event_id)
        if current_depth >= effective_depth:
            continue
        parents = select_rows(
            links_path,
            columns=LINK_COLUMNS + ["derivation_method"],
            exact_filters={"parent_event_id": current_event_id},
            limit=effective_limit,
        )
        children = select_rows(
            links_path,
            columns=LINK_COLUMNS + ["derivation_method"],
            exact_filters={"child_event_id": current_event_id},
            limit=effective_limit,
        )
        directed = [(parents, "outgoing"), (children, "incoming")]
        for frame, direction in directed:
            for _, raw in frame.iterrows():
                parent = str(raw.get("parent_event_id") or "").strip()
                child = str(raw.get("child_event_id") or "").strip()
                link_type = str(raw.get("link_type") or "linked").strip()
                if not parent or not child:
                    continue
                edge_key = (parent, child, link_type)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                related_event_id = child if direction == "outgoing" else parent
                links.append({
                    "parent_event_id": parent,
                    "child_event_id": child,
                    "related_event_id": related_event_id,
                    "related_event_type": _extract_event_type(related_event_id),
                    "direction": direction,
                    "relationship": link_type,
                    "source": _json_safe_event_value(raw.get("source")),
                    "method": _json_safe_event_value(raw.get("derivation_method")),
                    "confidence": _json_safe_event_value(raw.get("confidence")),
                    "depth": current_depth + 1,
                })
                if len(links) >= effective_limit:
                    break
                if related_event_id not in visited:
                    queue.append((related_event_id, current_depth + 1))
            if len(links) >= effective_limit:
                break
    return {
        "depth": effective_depth,
        "links": links,
        "count": len(links),
        "truncated": bool(queue) or len(links) >= effective_limit,
    }


def _event_affected_places(candidate: dict, event_id: str, *, limit: int) -> dict:
    pack_id = str(candidate.get("pack_id") or "").strip().lower()
    source_id = str(candidate.get("source_id") or "").strip().lower()
    event_area_name = pack_id
    if pack_id == "wildfires" and source_id == "wildfires_usa":
        event_area_name = "wildfires_usa"
    elif pack_id == "wildfires" and source_id == "can_wildfires":
        event_area_name = "wildfires_can"
    candidate_paths = [GLOBAL_DIR / f"disasters/event_areas/{event_area_name}.parquet"]
    try:
        event_path, _ = _resolve_exact_event_parquet_for_candidate(candidate)
        source_local_path = event_path.parent / "event_areas.parquet"
        if source_local_path not in candidate_paths:
            candidate_paths.append(source_local_path)
    except Exception:
        pass
    effective_limit = max(1, min(int(limit or 100), EVENT_DETAIL_LIMIT))
    rows = pd.DataFrame()
    available = False
    for path in candidate_paths:
        if not parquet_available(path):
            continue
        available = True
        rows = select_rows(
            path,
            columns=["event_id", "affected_loc_id", "impact_type", "area_km2", "pct_affected", "distance_km"],
            exact_filters={"event_id": event_id},
            limit=effective_limit + 1,
        )
        if not rows.empty:
            break
    if not available:
        return {"places": [], "count": 0, "truncated": False, "available": False}
    truncated = len(rows) > effective_limit
    places = []
    for _, row in rows.head(effective_limit).iterrows():
        places.append({
            str(key): _json_safe_event_value(value)
            for key, value in row.to_dict().items()
            if key != "event_id" and _json_safe_event_value(value) is not None
        })
    return {"places": places, "count": len(places), "truncated": truncated, "available": True}


def _event_observations(candidate: dict, row: dict, *, limit: int) -> dict:
    pack_id = str(candidate.get("pack_id") or "").strip().lower()
    event_id = str(row.get("event_id") or "").strip()
    effective_limit = max(1, min(int(limit or 100), EVENT_DETAIL_LIMIT))
    path: Path | None = None
    filters: dict = {"event_id": event_id}
    columns: list[str] = []
    kind = "none"
    order_by: str | None = None

    if pack_id == "hurricanes":
        path = GLOBAL_DIR / "disasters/hurricanes/positions.parquet"
        columns = ["event_id", "frame_id", "storm_id", "observed_at", "timestamp", "latitude", "longitude", "wind_kt", "pressure_mb", "category", "status"]
        kind, order_by = "track_positions", "timestamp"
    elif pack_id == "tsunamis":
        path = GLOBAL_DIR / "disasters/tsunamis/runups.parquet"
        columns = ["event_id", "runup_id", "timestamp", "latitude", "longitude", "location", "water_height_m", "horizontal_inundation_m", "dist_from_source_km", "arrival_travel_time_min", "deaths", "loc_id"]
        kind, order_by = "runups", "timestamp"
    elif pack_id == "earthquakes":
        path, _ = _resolve_exact_event_parquet_for_candidate(candidate)
        anchor_id = str(row.get("mainshock_id") or event_id).strip()
        filters = {"mainshock_id": anchor_id}
        columns = ["event_id", "mainshock_id", "sequence_id", "is_mainshock", "timestamp", "latitude", "longitude", "magnitude", "depth_km", "place", "loc_id"]
        kind, order_by = "aftershocks", "timestamp"
    elif pack_id == "wildfires":
        year = row.get("year")
        if year is None:
            match = re.search(r"(?:^|-)((?:19|20)\d{2})(?:-|$)", event_id)
            year = int(match.group(1)) if match else None
        if year is not None:
            path = GLOBAL_DIR / f"disasters/wildfires/fire_progression_{int(year)}.parquet"
            columns = ["event_id", "frame_id", "frame_part_id", "date", "day_num", "area_km2", "loc_id", "source"]
            kind, order_by = "progression_frames", "date"
    elif pack_id == "tornadoes" and row.get("sequence_id"):
        path, _ = _resolve_exact_event_parquet_for_candidate(candidate)
        filters = {"sequence_id": row["sequence_id"]}
        columns = ["event_id", "sequence_id", "sequence_position", "sequence_count", "timestamp", "latitude", "longitude", "end_latitude", "end_longitude", "magnitude", "loc_id"]
        kind, order_by = "event_sequence", "timestamp"

    if path is None or not parquet_available(path):
        return {"kind": kind, "rows": [], "count": 0, "truncated": False, "available": False}
    rows = select_rows(
        path,
        columns=columns,
        exact_filters=filters,
        order_by=order_by,
        limit=effective_limit + 1,
    )
    truncated = len(rows) > effective_limit
    shaped = [
        {
            str(key): _json_safe_event_value(value)
            for key, value in item.items()
            if _json_safe_event_value(value) is not None
        }
        for item in rows.head(effective_limit).to_dict(orient="records")
    ]
    return {"kind": kind, "rows": shaped, "count": len(shaped), "truncated": truncated, "available": True}


def _parse_event_geometry(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return None
    return value if isinstance(value, dict) and value.get("type") else None


def _event_geometry(candidate: dict, row: dict, *, mode: str, limit: int) -> dict:
    pack_id = str(candidate.get("pack_id") or "").strip().lower()
    event_id = str(row.get("event_id") or "").strip()
    if pack_id == "hurricanes":
        positions = _event_observations(candidate, row, limit=limit)
        coords = [
            [item["longitude"], item["latitude"]]
            for item in positions.get("rows", [])
            if item.get("longitude") is not None and item.get("latitude") is not None
        ]
        return {"kind": "track", "geometry": {"type": "LineString", "coordinates": coords} if len(coords) >= 2 else None, "observation_count": len(coords), "truncated": positions.get("truncated", False)}
    if pack_id == "tornadoes":
        coords = []
        for lon_key, lat_key in (("longitude", "latitude"), ("end_longitude", "end_latitude")):
            if row.get(lon_key) is not None and row.get(lat_key) is not None:
                coords.append([float(row[lon_key]), float(row[lat_key])])
        geometry = {"type": "LineString", "coordinates": coords} if len(coords) == 2 else None
        return {"kind": "path", "geometry": geometry}
    progression_path: Path | None = None
    if pack_id == "wildfires":
        year = row.get("year")
        if year is None:
            match = re.search(r"(?:^|-)((?:19|20)\d{2})(?:-|$)", event_id)
            year = int(match.group(1)) if match else None
        progression_path = GLOBAL_DIR / f"disasters/wildfires/fire_progression_{int(year)}.parquet" if year is not None else None
    if pack_id == "wildfires" and mode == "timeline":
        if progression_path is not None and parquet_available(progression_path):
            effective_limit = max(1, min(int(limit or 100), EVENT_DETAIL_LIMIT))
            frames = select_rows(
                progression_path,
                columns=["event_id", "frame_id", "frame_part_id", "date", "day_num", "area_km2", "perimeter"],
                exact_filters={"event_id": event_id},
                order_by="date",
                limit=effective_limit + 1,
            )
            features = []
            for item in frames.head(effective_limit).to_dict(orient="records"):
                geometry = _parse_event_geometry(item.pop("perimeter", None))
                if geometry:
                    features.append({"type": "Feature", "geometry": geometry, "properties": {key: _json_safe_event_value(value) for key, value in item.items() if key != "event_id"}})
            return {"kind": "progression", "features": features, "count": len(features), "truncated": len(frames) > effective_limit}
    geometry = _parse_event_geometry(row.get("perimeter"))
    if geometry:
        return {"kind": "perimeter", "geometry": geometry}
    if pack_id == "wildfires" and progression_path is not None and parquet_available(progression_path):
        # Find the actual last frame using metadata-only columns first.  Do not
        # mistake the last row inside a response limit for the event's current
        # perimeter, and do not read every historical polygon to find it.
        frame_index = select_rows(
            progression_path,
            columns=["event_id", "frame_id", "frame_part_id", "date", "day_num", "area_km2"],
            exact_filters={"event_id": event_id},
        )
        if not frame_index.empty:
            sort_columns = [column for column in ("date", "day_num", "frame_id") if column in frame_index.columns]
            if sort_columns:
                frame_index = frame_index.sort_values(sort_columns, ascending=True, na_position="first")
            latest = frame_index.iloc[-1]
            latest_frame_id = latest.get("frame_id")
            frame_filters = {"event_id": event_id}
            if latest_frame_id is not None and not pd.isna(latest_frame_id):
                frame_filters["frame_id"] = latest_frame_id
            frame_rows = select_rows(
                progression_path,
                columns=["event_id", "frame_id", "frame_part_id", "date", "day_num", "area_km2", "perimeter"],
                exact_filters=frame_filters,
                limit=EVENT_DETAIL_LIMIT,
            )
            features = []
            for item in frame_rows.to_dict(orient="records"):
                frame_geometry = _parse_event_geometry(item.pop("perimeter", None))
                if frame_geometry:
                    features.append({
                        "type": "Feature",
                        "geometry": frame_geometry,
                        "properties": {
                            key: _json_safe_event_value(value)
                            for key, value in item.items()
                            if key != "event_id" and _json_safe_event_value(value) is not None
                        },
                    })
            if features:
                representative = features[0]["geometry"] if len(features) == 1 else {
                    "type": "FeatureCollection",
                    "features": features,
                }
                return {
                    "kind": "perimeter",
                    "geometry": representative,
                    "frame": features[0]["properties"],
                    "part_count": len(features),
                }
    if row.get("longitude") is not None and row.get("latitude") is not None:
        return {"kind": "point", "geometry": {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]}}
    return {"kind": "none", "geometry": None}


def get_event_payload(
    event_id: str,
    *,
    pack_id: str | None = None,
    include: list[str] | None = None,
    relationship_depth: int = 1,
    geometry_mode: str = "current",
    limit: int = 100,
) -> dict | None:
    """Return one event plus explicitly requested companion layers."""
    requested = {str(value or "").strip().lower() for value in (include or []) if str(value or "").strip()}
    resolved = _resolve_event_record(
        event_id,
        pack_id=pack_id,
        include_geometry="geometry" in requested,
    )
    if resolved is None:
        return None
    candidate, row = resolved
    resolved_pack_id = str(candidate.get("pack_id") or "").strip().lower()
    canonical_event_id = str(row.get("event_id") or event_id).strip()
    geometry_fields = {key: row.pop(key) for key in EVENT_GEOMETRY_COLUMNS if key in row}
    geometry_row = {**row, **geometry_fields}
    payload = {
        "event": row,
        "event_id": canonical_event_id,
        "pack_id": resolved_pack_id,
        "source_id": candidate.get("source_id"),
        "event_type": candidate.get("event_type"),
        "schema_class": (
            "event_track" if resolved_pack_id == "hurricanes"
            else "event_polygon_progression" if resolved_pack_id == "wildfires"
            else "event_point"
        ),
        "available": {
            "relationships": True,
            "affected_places": resolved_pack_id in {"earthquakes", "floods", "hurricanes", "tornadoes", "tsunamis", "volcanoes", "wildfires"},
            "observations": resolved_pack_id in {"earthquakes", "hurricanes", "tornadoes", "tsunamis", "wildfires"},
            "geometry": True,
        },
        "included": sorted(requested),
    }
    if "relationships" in requested:
        payload["relationships"] = _event_relationship_rows(
            canonical_event_id, depth=relationship_depth, limit=limit,
        )
    if "affected_places" in requested:
        payload["affected_places"] = _event_affected_places(
            candidate, canonical_event_id, limit=limit,
        )
    if "observations" in requested:
        payload["observations"] = _event_observations(candidate, row, limit=limit)
    if "geometry" in requested:
        payload["geometry"] = _event_geometry(
            candidate, geometry_row, mode=geometry_mode, limit=limit,
        )
    payload["next_steps"] = {
        key: {
            "tool": "get_event",
            "arguments": {"event_id": canonical_event_id, "pack_id": resolved_pack_id, "include": [key]},
        }
        for key, available in payload["available"].items()
        if available and key not in requested
    }
    return payload


def _normalize_event_search_text(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^\w\s-]", " ", text)
    text = re.sub(r"\bmount\b", "mt", text)
    text = re.sub(r"\bsaint\b", "st", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_event_search_variants(query_text: str) -> list[str]:
    normalized = _normalize_event_search_text(query_text)
    if not normalized:
        return []
    variants: list[str] = [normalized]
    removable_prefixes = (
        "show me ",
        "find ",
        "get ",
        "load ",
        "open ",
        "see ",
        "watch ",
        "monitor ",
        "track ",
        "the ",
    )
    changed = True
    while changed:
        changed = False
        latest = variants[-1]
        for prefix in removable_prefixes:
            if latest.startswith(prefix):
                next_variant = latest[len(prefix) :].strip()
                if next_variant and next_variant not in variants:
                    variants.append(next_variant)
                    changed = True
                    break

    stop_tokens = {
        "volcano",
        "volcanoes",
        "volcanos",
        "eruption",
        "eruptions",
        "hurricane",
        "hurricanes",
        "storm",
        "storms",
        "cyclone",
        "cyclones",
        "typhoon",
        "typhoons",
        "event",
        "events",
        "show",
        "me",
        "the",
        "in",
        "at",
        "for",
        "us",
        "usa",
        "united",
        "states",
    }
    trimmed_tokens = [
        token
        for token in variants[-1].split()
        if token not in stop_tokens
    ]
    if trimmed_tokens:
        trimmed = " ".join(trimmed_tokens).strip()
        if trimmed and trimmed not in variants:
            variants.append(trimmed)
    if variants[-1].startswith("mt "):
        no_mt = variants[-1][3:].strip()
        if no_mt and no_mt not in variants:
            variants.append(no_mt)
    return variants


def _name_search_overrides_for_candidate(candidate: dict) -> dict:
    return EVENT_SEARCH_SOURCE_OVERRIDES.get(str(candidate.get("source_id") or "").strip(), {})


def _search_named_event_candidates(
    query_text: str,
    *,
    pack_id: str | None = None,
    limit: int = 10,
) -> list[dict]:
    import pyarrow.parquet as pq

    variants = _build_event_search_variants(query_text)
    if not variants:
        return []

    candidates = _get_exact_event_candidates(str(pack_id).strip().lower() if pack_id else None)
    results: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for candidate in candidates:
        overrides = _name_search_overrides_for_candidate(candidate)
        name_fields = tuple(overrides.get("name_fields") or ())
        if not name_fields:
            continue
        id_fields = tuple(candidate.get("id_fields") or ("event_id",))
        primary_id_field = str(id_fields[0] or "event_id").strip()

        parquet_path, _metadata = _resolve_exact_event_parquet_for_candidate(candidate)
        requested_columns: list[str] = list(dict.fromkeys(
            [primary_id_field, *name_fields, overrides.get("country_field"), "year", "timestamp"]
        ))
        requested_columns = [column for column in requested_columns if column]
        columns = requested_columns
        try:
            available_columns = set(pq.read_schema(parquet_path).names)
            columns = [column for column in requested_columns if column in available_columns]
        except Exception:
            columns = requested_columns
        try:
            df = pd.read_parquet(parquet_path, columns=columns)
        except Exception as exc:
            logger.warning("Named event search failed for %s: %s", candidate.get("source_id"), exc)
            continue
        if df.empty:
            continue

        best_mask = None
        for variant in variants:
            variant_tokens = [token for token in variant.split() if token]
            if not variant_tokens:
                continue
            current_mask = pd.Series(False, index=df.index)
            for field in name_fields:
                if field not in df.columns:
                    continue
                normalized_series = (
                    df[field]
                    .fillna("")
                    .astype(str)
                    .map(_normalize_event_search_text)
                )
                field_mask = normalized_series.apply(lambda text: all(token in text for token in variant_tokens))
                current_mask = current_mask | field_mask
            if bool(current_mask.any()):
                best_mask = current_mask
                break
        if best_mask is None:
            continue

        matches = df.loc[best_mask].copy()
        sort_columns = [column for column in ("timestamp", "year") if column in matches.columns]
        if sort_columns:
            matches = matches.sort_values(by=sort_columns, ascending=False, na_position="last")

        for _, row in matches.head(limit).iterrows():
            event_id = str(row.get(primary_id_field) or "").strip()
            if not event_id:
                continue
            key = (str(candidate.get("source_id") or ""), event_id)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            label = ""
            for field in name_fields:
                field_value = str(row.get(field) or "").strip()
                if field_value:
                    label = field_value
                    break
            if not label:
                label = event_id

            result = {
                "pack_id": candidate.get("pack_id"),
                "source_id": candidate.get("source_id"),
                "event_type": candidate.get("event_type"),
                "event_id": event_id,
                "label": label,
            }
            country_field = overrides.get("country_field")
            if country_field and row.get(country_field) is not None and not pd.isna(row.get(country_field)):
                result["country"] = str(row.get(country_field)).strip()
            if row.get("year") is not None and not pd.isna(row.get("year")):
                result["year"] = int(row.get("year"))
            if row.get("timestamp") is not None and not pd.isna(row.get("timestamp")):
                result["timestamp"] = row.get("timestamp").isoformat()
            results.append(result)
            if len(results) >= limit:
                return results

    return results


def search_named_event_candidates(
    query_text: str,
    *,
    pack_id: str | None = None,
    limit: int = 10,
) -> list[dict]:
    return _search_named_event_candidates(query_text, pack_id=pack_id, limit=limit)


def _resolve_exact_event_payload(identifier_value: str, pack_id: str | None = None) -> dict | None:
    normalized_identifier = str(identifier_value or "").strip()
    if not normalized_identifier:
        return None

    if pack_id:
        normalized_pack = str(pack_id).strip().lower()
        candidates = _get_exact_event_candidates(normalized_pack, identifier_value=normalized_identifier)
    else:
        candidates = _get_exact_event_candidates(identifier_value=normalized_identifier)
        hinted_packs, strict_hint = _classify_exact_event_identifier(normalized_identifier)
        if hinted_packs:
            hinted_set = set(hinted_packs)
            if strict_hint:
                candidates = [entry for entry in candidates if entry["pack_id"] in hinted_set]
            else:
                candidates = sorted(
                    candidates,
                    key=lambda entry: (0 if entry["pack_id"] in hinted_set else 1, hinted_packs.index(entry["pack_id"]) if entry["pack_id"] in hinted_set else 999)
                )

    for candidate in candidates:
        source_id = candidate["source_id"]
        event_type = candidate["event_type"]
        metadata = _load_exact_event_metadata(candidate)
        for identifier_field in candidate["id_fields"]:
            try:
                df = _query_exact_event(candidate, identifier_field, normalized_identifier)
            except Exception as exc:
                logger.warning("Exact event lookup failed for %s.%s=%s: %s", source_id, identifier_field, normalized_identifier, exc)
                continue
            if df.empty:
                continue
            row = df.head(1).iloc[0].to_dict()
            payload = _build_exact_event_feature(
                row,
                event_type=event_type,
                source_id=source_id,
                pack_id=candidate["pack_id"],
                identifier_field=identifier_field,
                metadata=metadata,
            )
            if payload:
                return payload
    named_candidates = _search_named_event_candidates(
        normalized_identifier,
        pack_id=pack_id,
        limit=5,
    )
    if len(named_candidates) == 1:
        matched_event_id = str(named_candidates[0].get("event_id") or "").strip()
        matched_pack_id = str(named_candidates[0].get("pack_id") or "").strip().lower() or None
        if matched_event_id:
            return _resolve_exact_event_payload(matched_event_id, pack_id=matched_pack_id)

    # Earthquake exact ids are a critical live/ops path. Keep a direct fallback
    # to the earthquake loader so exact-event lookup still works even if the
    # generic candidate resolution misses a cloud/runtime edge case.
    normalized_pack = str(pack_id or "").strip().lower()
    if normalized_pack == "earthquakes":
        try:
            df = _load_earthquake_exact_event_row(normalized_identifier)
        except Exception as exc:
            logger.warning(
                "Earthquake exact fallback failed for %s: %s",
                normalized_identifier,
                exc,
            )
        else:
            if not df.empty:
                metadata = load_source_metadata("earthquakes_events") or {}
                row = df.head(1).iloc[0].to_dict()
                payload = _build_exact_event_feature(
                    row,
                    event_type="earthquake",
                    source_id="earthquakes_events",
                    pack_id="earthquakes",
                    identifier_field="event_id",
                    metadata=metadata,
                )
                if payload:
                    return payload
    return None


def _load_earthquake_exact_event_row(event_id: str) -> pd.DataFrame:
    events_path = GLOBAL_DIR / "disasters/earthquakes/events.parquet"
    if not parquet_available(events_path):
        return pd.DataFrame()
    if duckdb_available():
        return select_rows(events_path, exact_filters={"event_id": event_id}, limit=1)
    df = pd.read_parquet(events_path)
    if "event_id" not in df.columns:
        return pd.DataFrame()
    return df[df["event_id"] == event_id].head(1).copy()


def _read_link_rows(links_path, column: str, loc_id: str) -> pd.DataFrame:
    if duckdb_available():
        return select_rows(
            links_path,
            columns=LINK_COLUMNS,
            exact_filters={column: loc_id},
        )
    return pd.read_parquet(links_path, columns=LINK_COLUMNS, filters=[(column, "==", loc_id)])


def _normalize_link_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    if "parent_event_id" not in df.columns:
        df["parent_event_id"] = None
    if "child_event_id" not in df.columns:
        df["child_event_id"] = None
    if "parent_loc_id" in df.columns:
        mask = df["parent_event_id"].isna() | (df["parent_event_id"].astype(str).str.strip() == "")
        df.loc[mask, "parent_event_id"] = df.loc[mask, "parent_loc_id"].map(_extract_event_id)
    if "child_loc_id" in df.columns:
        mask = df["child_event_id"].isna() | (df["child_event_id"].astype(str).str.strip() == "")
        df.loc[mask, "child_event_id"] = df.loc[mask, "child_loc_id"].map(_extract_event_id)
    return df


def _extract_event_type(loc_id: str) -> str:
    type_map = {
        "EQ": "earthquake",
        "TSUN": "tsunami",
        "VOLC": "volcano",
        "HRCN": "hurricane",
        "TORN": "tornado",
        "FIRE": "wildfire",
        "FLOOD": "flood",
        "LAND": "landslide",
    }
    parts = [part.strip().upper() for part in str(loc_id or "").split("-") if str(part or "").strip()]
    for part in parts:
        if part in type_map:
            return type_map[part]
    return "unknown"


def _extract_event_id(loc_id: str) -> str:
    parts = loc_id.split("-")
    if len(parts) >= 3:
        for i, part in enumerate(parts):
            if part in ["EQ", "TSUN", "VOLC", "HRCN", "TORN", "FIRE", "FLOOD", "LAND"]:
                return "-".join(parts[i + 1 :])
    return parts[-1] if parts else loc_id


def _normalize_event_type_filter(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return EVENT_TYPE_ALIASES.get(normalized, normalized)


def _safe_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _loc_id_like_pattern_for_event_type(event_type: str | None) -> str | None:
    normalized = _normalize_event_type_filter(event_type)
    if not normalized:
        return None
    token = EVENT_TYPE_LOC_TOKENS.get(normalized)
    if not token:
        return None
    return f"%-{token}-%"


def _event_score_from_properties(props: dict | None) -> float:
    if not isinstance(props, dict):
        return 0.0

    event_type = _normalize_event_type_filter(props.get("event_type"))
    score = 0.0

    deaths = _safe_float(props.get("deaths"))
    if deaths is not None:
        score += min(deaths, 100000.0) * 0.05

    damage = _safe_float(props.get("damage_millions"))
    if damage is not None:
        score += min(damage, 100000.0) * 0.02

    if event_type == "earthquake":
        magnitude = _safe_float(props.get("magnitude"))
        if magnitude is not None:
            score += magnitude * 100.0
    elif event_type == "tsunami":
        height = _safe_float(props.get("max_water_height_m"))
        eq_magnitude = _safe_float(props.get("eq_magnitude"))
        if height is not None:
            score += height * 80.0
        if eq_magnitude is not None:
            score += eq_magnitude * 40.0
    elif event_type == "volcano":
        vei = _safe_float(props.get("VEI"))
        if vei is not None:
            score += vei * 120.0
    elif event_type == "hurricane":
        wind = _safe_float(props.get("max_wind_kt"))
        if wind is not None:
            score += wind * 1.5
    elif event_type == "wildfire":
        area = _safe_float(props.get("area_sq_km")) or _safe_float(props.get("acres"))
        if area is not None:
            score += min(area, 1000000.0) * 0.005
    elif event_type == "flood":
        duration = _safe_float(props.get("duration_days"))
        if duration is not None:
            score += duration * 8.0

    return round(score, 2)


def _summarize_chain_node(feature: dict) -> dict:
    props = dict((feature or {}).get("properties") or {})
    return {
        "loc_id": str(props.get("loc_id") or "").strip() or None,
        "event_id": str(props.get("event_id") or _extract_event_id(str(props.get("loc_id") or ""))).strip() or None,
        "event_type": _normalize_event_type_filter(props.get("event_type")),
        "timestamp": props.get("timestamp"),
        "year": _safe_int(props.get("year")),
        "country": props.get("country"),
        "title": props.get("title") or props.get("name") or props.get("place") or props.get("volcano_name"),
        "score": _event_score_from_properties(props),
    }


def _build_chain_match(
    node_loc_ids: list[str],
    links: list[dict],
    feature_cache: dict[str, dict | None],
) -> dict | None:
    nodes: list[dict] = []
    total_score = 0.0
    for loc_id in node_loc_ids:
        feature = feature_cache.get(loc_id)
        if feature is None:
            return None
        node_summary = _summarize_chain_node(feature)
        nodes.append(node_summary)
        total_score += float(node_summary.get("score") or 0.0)

    total_confidence = 0.0
    for link in links:
        confidence = _safe_float(link.get("confidence"))
        if confidence is not None:
            total_confidence += confidence * 25.0

    score = round(total_score + total_confidence, 2)
    return {
        "score": score,
        "depth": max(0, len(nodes) - 1),
        "chain_signature": " -> ".join([str(node.get("event_type") or "unknown") for node in nodes]),
        "nodes": nodes,
        "links": links,
    }


def _chain_matches_filters(
    chain: dict,
    *,
    start_event_type: str | None,
    via_event_type: str | None,
    end_event_type: str | None,
    year_start: int | None,
    year_end: int | None,
) -> bool:
    nodes = chain.get("nodes") or []
    if not nodes:
        return False

    node_types = [_normalize_event_type_filter(node.get("event_type")) for node in nodes]
    if start_event_type and node_types[0] != start_event_type:
        return False
    if end_event_type and node_types[-1] != end_event_type:
        return False
    if via_event_type:
        middle_types = node_types[1:-1] if len(node_types) > 2 else []
        if via_event_type not in middle_types:
            return False

    if year_start is not None or year_end is not None:
        years = [node.get("year") for node in nodes if isinstance(node.get("year"), int)]
        if years:
            pivot_year = max(years)
            if year_start is not None and pivot_year < year_start:
                return False
            if year_end is not None and pivot_year > year_end:
                return False

    return True


def _discover_disaster_link_chains(
    *,
    start_event_type: str | None = None,
    via_event_type: str | None = None,
    end_event_type: str | None = None,
    year_start: int | None = None,
    year_end: int | None = None,
    limit: int = 10,
) -> dict:
    normalized_start = _normalize_event_type_filter(start_event_type)
    normalized_via = _normalize_event_type_filter(via_event_type)
    normalized_end = _normalize_event_type_filter(end_event_type)
    effective_limit = max(1, min(int(limit or 10), MAX_DISCOVERY_LIMIT))

    if not any([normalized_start, normalized_via, normalized_end]):
        return {
            "count": 0,
            "chains": [],
            "message": "At least one event-type filter is required",
        }

    links_path = GLOBAL_DIR / "disasters/links.parquet"
    if not parquet_available(links_path):
        return {
            "count": 0,
            "chains": [],
            "message": "Links data not available",
        }

    def load_candidate_links(*, parent_event_type: str | None = None, child_event_type: str | None = None) -> pd.DataFrame:
        parent_pattern = _loc_id_like_pattern_for_event_type(parent_event_type)
        child_pattern = _loc_id_like_pattern_for_event_type(child_event_type)
        try:
            if duckdb_available():
                return _normalize_link_rows(
                    select_filtered_event_rows(
                        links_path,
                        like_filters={
                            "parent_loc_id": parent_pattern,
                            "child_loc_id": child_pattern,
                        },
                    )
                )
            df = pd.read_parquet(links_path, columns=LINK_COLUMNS)
        except Exception as exc:
            runtime_mode = get_runtime_mode(get_runtime_config().get("runtime_mode", "local"))
            if runtime_mode == "cloud":
                logger.warning("Disaster link discovery parquet unavailable in cloud runtime: %s", exc)
                return pd.DataFrame(columns=LINK_COLUMNS)
            raise

        if parent_pattern:
            token = str(parent_pattern).strip("%")
            df = df[df["parent_loc_id"].astype(str).str.contains(token, regex=False, na=False)]
        if child_pattern:
            token = str(child_pattern).strip("%")
            df = df[df["child_loc_id"].astype(str).str.contains(token, regex=False, na=False)]
        return _normalize_link_rows(df)

    raw_candidates: list[tuple[list[str], list[dict]]] = []

    direct_df = load_candidate_links(
        parent_event_type=normalized_start,
        child_event_type=normalized_end,
    )
    if not normalized_via:
        for _, row in direct_df.iterrows():
            raw_candidates.append((
                [str(row["parent_loc_id"]), str(row["child_loc_id"])],
                [{
                    "parent_loc_id": str(row["parent_loc_id"]),
                    "child_loc_id": str(row["child_loc_id"]),
                    "parent_event_id": str(row.get("parent_event_id") or _extract_event_id(str(row["parent_loc_id"]))),
                    "child_event_id": str(row.get("child_event_id") or _extract_event_id(str(row["child_loc_id"]))),
                    "link_type": str(row.get("link_type") or "linked"),
                    "source": row.get("source"),
                    "confidence": row.get("confidence"),
                }],
            ))

    if normalized_via or (normalized_start and normalized_end):
        left_df = load_candidate_links(
            parent_event_type=normalized_start,
            child_event_type=normalized_via,
        )
        right_df = load_candidate_links(
            parent_event_type=normalized_via,
            child_event_type=normalized_end,
        )

        if not left_df.empty and not right_df.empty:
            merged = left_df.merge(
                right_df,
                left_on="child_loc_id",
                right_on="parent_loc_id",
                suffixes=("_a", "_b"),
            )
            for _, row in merged.iterrows():
                raw_candidates.append((
                    [
                        str(row["parent_loc_id_a"]),
                        str(row["child_loc_id_a"]),
                        str(row["child_loc_id_b"]),
                    ],
                    [
                        {
                            "parent_loc_id": str(row["parent_loc_id_a"]),
                            "child_loc_id": str(row["child_loc_id_a"]),
                            "parent_event_id": str(row.get("parent_event_id_a") or _extract_event_id(str(row["parent_loc_id_a"]))),
                            "child_event_id": str(row.get("child_event_id_a") or _extract_event_id(str(row["child_loc_id_a"]))),
                            "link_type": str(row.get("link_type_a") or "linked"),
                            "source": row.get("source_a"),
                            "confidence": row.get("confidence_a"),
                        },
                        {
                            "parent_loc_id": str(row["parent_loc_id_b"]),
                            "child_loc_id": str(row["child_loc_id_b"]),
                            "parent_event_id": str(row.get("parent_event_id_b") or _extract_event_id(str(row["parent_loc_id_b"]))),
                            "child_event_id": str(row.get("child_event_id_b") or _extract_event_id(str(row["child_loc_id_b"]))),
                            "link_type": str(row.get("link_type_b") or "linked"),
                            "source": row.get("source_b"),
                            "confidence": row.get("confidence_b"),
                        },
                    ],
                ))

    requested_loc_ids = sorted({
        loc_id
        for node_loc_ids, _links in raw_candidates
        for loc_id in node_loc_ids
    })
    feature_cache = _load_event_features_by_loc_ids(requested_loc_ids)

    chain_matches: list[dict] = []
    seen_signatures: set[tuple[str, ...]] = set()
    for node_loc_ids, links in raw_candidates:
        signature = tuple(node_loc_ids)
        if signature in seen_signatures:
            continue
        if any(feature_cache.get(loc_id) is None for loc_id in node_loc_ids):
            continue
        chain = _build_chain_match(node_loc_ids, links, feature_cache)
        if chain is None:
            continue
        if not _chain_matches_filters(
            chain,
            start_event_type=normalized_start,
            via_event_type=normalized_via,
            end_event_type=normalized_end,
            year_start=year_start,
            year_end=year_end,
        ):
            continue
        seen_signatures.add(signature)
        chain_matches.append(chain)

    chain_matches.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            int(item.get("depth") or 0),
            str(item.get("chain_signature") or ""),
        )
    )
    limited = chain_matches[:effective_limit]
    return {
        "count": len(limited),
        "total_matches": len(chain_matches),
        "chains": limited,
        "message": None if limited else "No matching cross-disaster chains found",
    }


def _build_event_feature_from_row(loc_id: str, event_type: str, config: dict, row: dict) -> dict | None:
    latitude = row.get("latitude")
    longitude = row.get("longitude")
    if pd.isna(latitude) or pd.isna(longitude):
        return None

    builder_factory = config.get("builders")
    if builder_factory:
        builders = builder_factory()
        props = {name: builder(row) for name, builder in builders.items()}
    else:
        props = {}
        for key, value in row.items():
            if value is None or pd.isna(value):
                continue
            if hasattr(value, "item"):
                value = value.item()
            if isinstance(value, pd.Timestamp):
                value = value.isoformat()
            props[key] = value
    props["event_type"] = event_type
    props["loc_id"] = props.get("loc_id") or loc_id

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [float(longitude), float(latitude)],
        },
        "properties": props,
    }


def _prepare_linked_event_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    prepared = df.copy()
    if "timestamp" in prepared.columns:
        prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce")
    if "year" not in prepared.columns and "timestamp" in prepared.columns:
        prepared["year"] = prepared["timestamp"].dt.year
    sort_columns = [column for column in ("timestamp", "year") if column in prepared.columns]
    if sort_columns:
        ascending = [False] * len(sort_columns)
        prepared = prepared.sort_values(sort_columns, ascending=ascending, na_position="last")
    return prepared


def _load_linked_event_rows(loc_id: str) -> tuple[str | None, dict, pd.DataFrame]:
    event_type = _extract_event_type(loc_id)
    pack_id = EVENT_TYPE_PACK_IDS.get(event_type)
    if not pack_id:
        return event_type, {}, pd.DataFrame()

    candidates = _get_exact_event_candidates(pack_id=pack_id, identifier_value=loc_id)
    if not candidates:
        return event_type, {}, pd.DataFrame()

    fallback_config = EVENT_TABLES.get(event_type, {})
    for candidate in candidates:
        parquet_path, _ = _resolve_exact_event_parquet_for_candidate(candidate)
        if not parquet_available(parquet_path):
            continue
        try:
            df = select_rows(parquet_path, exact_filters={"loc_id": loc_id})
        except Exception as exc:
            logger.warning("Failed resolving linked event %s from %s: %s", loc_id, parquet_path, exc)
            continue
        if df.empty:
            continue

        candidate_event_type = str(candidate.get("event_type") or event_type or "").strip().lower()
        config = dict(fallback_config)
        return candidate_event_type, config, _prepare_linked_event_rows(df)

    return event_type, fallback_config, pd.DataFrame()


def _load_event_feature_by_loc_id(loc_id: str) -> dict | None:
    event_type, config, df = _load_linked_event_rows(loc_id)
    if not event_type or df.empty:
        return None

    row = df.iloc[0].to_dict()
    if not config and event_type not in EVENT_TABLES:
        config = {}
    return _build_event_feature_from_row(loc_id, event_type, config, row)


def _load_event_features_by_loc_ids(loc_ids: list[str]) -> dict[str, dict | None]:
    requested = [str(loc_id) for loc_id in loc_ids if str(loc_id or "").strip()]
    result: dict[str, dict | None] = {loc_id: None for loc_id in requested}
    if not requested:
        return result

    for loc_id in requested:
        result[loc_id] = _load_event_feature_by_loc_id(loc_id)

    return result


def _read_related_rows_for_loc_id(loc_id: str) -> pd.DataFrame:
    links_path = GLOBAL_DIR / "disasters/links.parquet"
    if not parquet_available(links_path):
        return pd.DataFrame(columns=LINK_COLUMNS + ["direction", "related_loc_id"])

    children = _normalize_link_rows(_read_link_rows(links_path, "parent_loc_id", loc_id).copy())
    parents = _normalize_link_rows(_read_link_rows(links_path, "child_loc_id", loc_id).copy())

    if children.empty or "parent_loc_id" not in children.columns:
        children = pd.DataFrame(columns=LINK_COLUMNS)
    children["direction"] = "triggered"
    children["related_loc_id"] = children["child_loc_id"]

    if parents.empty or "child_loc_id" not in parents.columns:
        parents = pd.DataFrame(columns=LINK_COLUMNS)
    parents["direction"] = "triggered_by"
    parents["related_loc_id"] = parents["parent_loc_id"]

    frames = [frame for frame in (children, parents) if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=LINK_COLUMNS + ["direction", "related_loc_id"])
    return pd.concat(frames, ignore_index=True)


def _filter_related_rows_for_popup(
    root_loc_id: str,
    related_rows: pd.DataFrame,
    *,
    cross_type_only: bool = True,
) -> pd.DataFrame:
    if related_rows.empty or not cross_type_only:
        return related_rows

    root_event_type = _extract_event_type(root_loc_id)
    if not root_event_type or root_event_type == "unknown":
        return related_rows

    filtered_rows = related_rows[
        related_rows["related_loc_id"].map(_extract_event_type) != root_event_type
    ].copy()
    return filtered_rows


def _build_chain_payload(root_loc_id: str, depth: int, *, cross_type_only: bool = True) -> dict:
    effective_depth = max(1, min(int(depth or 1), MAX_CHAIN_DEPTH))
    queue: list[tuple[str, int]] = [(root_loc_id, 0)]
    visited_nodes: set[str] = set()
    feature_by_loc_id: dict[str, dict] = {}
    chain_links: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()

    while queue:
        current_loc_id, current_depth = queue.pop(0)
        if current_loc_id in visited_nodes:
            continue
        visited_nodes.add(current_loc_id)

        feature = _load_event_feature_by_loc_id(current_loc_id)
        if feature is not None:
            feature["properties"]["chain_depth"] = current_depth
            feature_by_loc_id[current_loc_id] = feature

        if current_depth >= effective_depth:
            continue

        related_rows = _read_related_rows_for_loc_id(current_loc_id)
        related_rows = _filter_related_rows_for_popup(
            current_loc_id,
            related_rows,
            cross_type_only=cross_type_only,
        )
        if related_rows.empty:
            continue

        for _, row in related_rows.iterrows():
            parent_loc_id = row.get("parent_loc_id")
            child_loc_id = row.get("child_loc_id")
            parent_event_id = row.get("parent_event_id") or _extract_event_id(str(parent_loc_id))
            child_event_id = row.get("child_event_id") or _extract_event_id(str(child_loc_id))
            link_type = row.get("link_type") or "linked"
            direction = row.get("direction") or "linked"
            related_loc_id = row.get("related_loc_id")
            if not parent_loc_id or not child_loc_id or not related_loc_id:
                continue

            edge_key = (str(parent_loc_id), str(child_loc_id), str(link_type))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                chain_links.append(
                    {
                        "parent_loc_id": str(parent_loc_id),
                        "child_loc_id": str(child_loc_id),
                        "parent_event_id": str(parent_event_id) if parent_event_id else None,
                        "child_event_id": str(child_event_id) if child_event_id else None,
                        "related_loc_id": str(related_loc_id),
                        "link_type": str(link_type),
                        "direction": str(direction),
                        "source": row.get("source"),
                        "confidence": row.get("confidence"),
                    }
                )

            if related_loc_id not in visited_nodes:
                queue.append((str(related_loc_id), current_depth + 1))

    source_feature = feature_by_loc_id.get(root_loc_id)
    related_features = [
        feature
        for loc_id, feature in feature_by_loc_id.items()
        if loc_id != root_loc_id
    ]

    return {
        "source": source_feature,
        "features": [source_feature] + related_features if source_feature is not None else related_features,
        "links": chain_links,
        "depth": effective_depth,
        "count": len(related_features),
    }


def _extract_exact_event_reference(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None

    geojson = payload.get("geojson")
    if not isinstance(geojson, dict):
        return None
    features = geojson.get("features")
    if not isinstance(features, list) or not features:
        return None
    feature = features[0]
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties")
    if not isinstance(props, dict):
        return None

    loc_id = str(props.get("loc_id") or "").strip()
    if not loc_id:
        return None

    return {
        "event_id": str(props.get("event_id") or "").strip() or None,
        "loc_id": loc_id,
        "pack_id": str(payload.get("pack_id") or "").strip() or None,
        "source_id": str(payload.get("source_id") or "").strip() or None,
        "event_type": str(payload.get("event_type") or props.get("event_type") or "").strip() or None,
    }


def _resolve_exact_event_reference(identifier_value: str, *, pack_id: str | None = None) -> dict | None:
    payload = _resolve_exact_event_payload(identifier_value, pack_id=pack_id)
    if payload is None:
        return None
    return _extract_exact_event_reference(payload)


def _build_related_events_payload(loc_id: str, *, cross_type_only: bool = True) -> dict:
    if not loc_id:
        return {"event_id": loc_id, "related": [], "count": 0, "message": "Missing event loc_id"}

    links_path = GLOBAL_DIR / "disasters/links.parquet"
    if not parquet_available(links_path):
        return {"event_id": loc_id, "related": [], "count": 0, "message": "Links data not available"}

    try:
        children = _normalize_link_rows(_read_link_rows(links_path, "parent_loc_id", loc_id).copy())
        parents = _normalize_link_rows(_read_link_rows(links_path, "child_loc_id", loc_id).copy())
    except Exception as exc:
        runtime_mode = get_runtime_mode(get_runtime_config().get("runtime_mode", "local"))
        if runtime_mode == "cloud":
            logger.warning("Related events links parquet unavailable in cloud runtime: %s", exc)
            return {
                "event_id": loc_id,
                "related": [],
                "count": 0,
                "message": "Related-disaster links are not available in the published runtime data.",
            }
        raise

    if children.empty or "parent_loc_id" not in children.columns:
        children = pd.DataFrame(columns=LINK_COLUMNS)
    children["direction"] = "triggered"
    children["related_loc_id"] = children["child_loc_id"]

    if parents.empty or "child_loc_id" not in parents.columns:
        parents = pd.DataFrame(columns=LINK_COLUMNS)
    parents["direction"] = "triggered_by"
    parents["related_loc_id"] = parents["parent_loc_id"]

    frames = [frame for frame in (children, parents) if not frame.empty]
    if not frames:
        related = pd.DataFrame(columns=LINK_COLUMNS + ["direction", "related_loc_id"])
    else:
        related = pd.concat(frames, ignore_index=True)
    related = _filter_related_rows_for_popup(
        loc_id,
        related,
        cross_type_only=cross_type_only,
    )
    if len(related) == 0:
        message = (
            "No cross-disaster links found for this event in links.parquet"
            if cross_type_only
            else "No related disasters found for this event in links.parquet"
        )
        return {
            "event_id": loc_id,
            "related": [],
            "count": 0,
            "by_type": {},
            "cross_type_only": cross_type_only,
            "message": message,
        }

    related_list = []
    for _, row in related.iterrows():
        related_loc_id = row["related_loc_id"]
        related_list.append(
            {
                "loc_id": related_loc_id,
                "event_id": (
                    row.get("child_event_id") if row["direction"] == "triggered" else row.get("parent_event_id")
                ) or _extract_event_id(related_loc_id),
                "event_type": _extract_event_type(related_loc_id),
                "link_type": row["link_type"],
                "direction": row["direction"],
                "source": row["source"],
                "confidence": row["confidence"],
            }
        )

    type_counts = {}
    for item in related_list:
        event_type = item["event_type"]
        type_counts[event_type] = type_counts.get(event_type, 0) + 1

    return {
        "event_id": loc_id,
        "related": related_list,
        "count": len(related_list),
        "by_type": type_counts,
        "cross_type_only": cross_type_only,
        "message": None,
    }


def _build_related_chain_response(loc_id: str, *, depth: int, cross_type_only: bool = True) -> dict:
    payload = _build_chain_payload(
        loc_id,
        depth,
        cross_type_only=cross_type_only,
    )
    return {
        "type": "FeatureCollection",
        "features": payload["features"],
        "source": payload["source"],
        "links": payload["links"],
        "depth": payload["depth"],
        "count": payload["count"],
        "cross_type_only": cross_type_only,
        "loc_id": loc_id,
    }


@router.get("/api/events/related/{loc_id:path}")
async def get_related_events(loc_id: str, cross_type_only: bool = Query(default=True)):
    """Get related disaster events for a given event loc_id."""
    try:
        return msgpack_response(_build_related_events_payload(loc_id, cross_type_only=cross_type_only))
    except Exception as e:
        logger.error(f"Error fetching related events for {loc_id}: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/events/by-loc/{loc_id:path}")
async def get_event_by_loc_id(loc_id: str):
    """Resolve a linked disaster event into a map-ready feature using canonical loc_id."""
    try:
        if not loc_id:
            return msgpack_error("Missing event loc_id", 400)

        feature = _load_event_feature_by_loc_id(loc_id)
        if feature is None:
            return msgpack_error(f"Linked event {loc_id} could not be resolved", 404)

        return msgpack_response(
            {
                "type": "FeatureCollection",
                "features": [feature],
                "event_type": feature["properties"].get("event_type"),
                "loc_id": loc_id,
            }
        )
    except Exception as e:
        logger.error(f"Error resolving linked event {loc_id}: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/events/exact/{event_id:path}")
async def get_event_by_exact_id(event_id: str, pack_id: str | None = Query(default=None)):
    """Resolve one stable event id across canonical event sources."""
    try:
        if not event_id:
            return msgpack_error("Missing event id", 400)

        payload = _resolve_exact_event_payload(event_id, pack_id=pack_id)
        if payload is None:
            scope_text = f" in pack {pack_id}" if pack_id else ""
            return msgpack_error(f"Event {event_id} was not found{scope_text}", 404)

        return msgpack_response(payload)
    except Exception as e:
        logger.error(f"Error resolving exact event {event_id}: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/events/search")
async def search_events(q: str, pack_id: str | None = Query(default=None), limit: int = Query(default=10, ge=1, le=25)):
    """Search deterministic event ids by source-specific stable names or labels."""
    try:
        if not str(q or "").strip():
            return msgpack_error("Missing event search query", 400)

        matches = _search_named_event_candidates(
            q,
            pack_id=pack_id,
            limit=int(limit),
        )
        return msgpack_response(
            {
                "query": q,
                "pack_id": pack_id,
                "count": len(matches),
                "matches": matches,
            }
        )
    except Exception as e:
        logger.error(f"Error searching events for {q}: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/events/chain/{loc_id:path}")
async def get_related_event_chain(
    loc_id: str,
    depth: int = 1,
    cross_type_only: bool = Query(default=True),
):
    """Resolve a linked disaster chain into map-ready features and edges."""
    try:
        if not loc_id:
            return msgpack_error("Missing event loc_id", 400)

        payload = _build_related_chain_response(
            loc_id,
            depth=depth,
            cross_type_only=cross_type_only,
        )
        if payload["source"] is None:
            return msgpack_error(f"Linked event {loc_id} could not be resolved", 404)
        return msgpack_response(payload)
    except Exception as e:
        logger.error(f"Error building linked event chain for {loc_id}: {e}")
        return msgpack_error(str(e), 500)


@router.get("/api/v1/disaster-links/event/{event_id:path}")
async def get_disaster_links_for_exact_event(
    event_id: str,
    pack_id: str | None = Query(default=None),
    cross_type_only: bool = Query(default=True),
):
    """Resolve one exact disaster event id into related-link rows."""
    try:
        if not str(event_id or "").strip():
            return JSONResponse({"error": "Missing event id"}, status_code=400)

        reference = _resolve_exact_event_reference(event_id, pack_id=pack_id)
        if reference is None:
            scope_text = f" in pack {pack_id}" if pack_id else ""
            return JSONResponse({"error": f"Event {event_id} was not found{scope_text}"}, status_code=404)

        resolved_pack_id = str(reference.get("pack_id") or "").strip().lower()
        if resolved_pack_id not in DISASTER_LINK_API_PACKS:
            return JSONResponse(
                {
                    "error": f"Shared disaster links are not published for pack {resolved_pack_id or pack_id or 'unknown'}"
                },
                status_code=400,
            )

        payload = _build_related_events_payload(
            str(reference["loc_id"]),
            cross_type_only=cross_type_only,
        )
        payload.update(
            {
                "query_event_id": str(event_id),
                "resolved_event": reference,
                "supported_link_types": ["triggered"],
                "default_cross_type_only": True,
                "cross_hazard_only": True,
            }
        )
        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"Error fetching public disaster links for {event_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/v1/disaster-links/chain/{event_id:path}")
async def get_disaster_link_chain_for_exact_event(
    event_id: str,
    pack_id: str | None = Query(default=None),
    depth: int = Query(default=1, ge=1, le=MAX_CHAIN_DEPTH),
    cross_type_only: bool = Query(default=True),
):
    """Resolve one exact disaster event id into a related-link chain payload."""
    try:
        if not str(event_id or "").strip():
            return JSONResponse({"error": "Missing event id"}, status_code=400)

        reference = _resolve_exact_event_reference(event_id, pack_id=pack_id)
        if reference is None:
            scope_text = f" in pack {pack_id}" if pack_id else ""
            return JSONResponse({"error": f"Event {event_id} was not found{scope_text}"}, status_code=404)

        resolved_pack_id = str(reference.get("pack_id") or "").strip().lower()
        if resolved_pack_id not in DISASTER_LINK_API_PACKS:
            return JSONResponse(
                {
                    "error": f"Shared disaster links are not published for pack {resolved_pack_id or pack_id or 'unknown'}"
                },
                status_code=400,
            )

        payload = _build_related_chain_response(
            str(reference["loc_id"]),
            depth=depth,
            cross_type_only=cross_type_only,
        )
        if payload["source"] is None:
            return JSONResponse({"error": f"Linked event {reference['loc_id']} could not be resolved"}, status_code=404)

        payload.update(
            {
                "query_event_id": str(event_id),
                "resolved_event": reference,
                "supported_link_types": ["triggered"],
                "default_cross_type_only": True,
                "cross_hazard_only": True,
            }
        )
        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"Error building public disaster link chain for {event_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/v1/disaster-links/search")
async def search_disaster_link_chains(
    start_event_type: str | None = Query(default=None),
    via_event_type: str | None = Query(default=None),
    end_event_type: str | None = Query(default=None),
    year_start: int | None = Query(default=None),
    year_end: int | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=MAX_DISCOVERY_LIMIT),
):
    """Discover ranked cross-disaster chains without requiring a seed event id."""
    try:
        normalized_year_start = _safe_int(year_start)
        normalized_year_end = _safe_int(year_end)
        normalized_limit = _safe_int(limit) or 10
        payload = _discover_disaster_link_chains(
            start_event_type=start_event_type,
            via_event_type=via_event_type,
            end_event_type=end_event_type,
            year_start=normalized_year_start,
            year_end=normalized_year_end,
            limit=normalized_limit,
        )
        payload.update(
            {
                "query": {
                    "start_event_type": _normalize_event_type_filter(start_event_type),
                    "via_event_type": _normalize_event_type_filter(via_event_type),
                    "end_event_type": _normalize_event_type_filter(end_event_type),
                    "year_start": normalized_year_start,
                    "year_end": normalized_year_end,
                    "limit": normalized_limit,
                },
                "supported_link_types": ["triggered"],
                "cross_hazard_only": True,
            }
        )
        if payload.get("message") == "At least one event-type filter is required":
            return JSONResponse(payload, status_code=400)
        return JSONResponse(payload)
    except Exception as e:
        logger.error("Error searching public disaster links: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
