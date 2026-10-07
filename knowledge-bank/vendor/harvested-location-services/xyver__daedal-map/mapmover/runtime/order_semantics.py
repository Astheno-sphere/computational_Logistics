"""Shared order-semantic helpers for event vs aggregate routing."""

from pathlib import Path
import re

from mapmover.data_loading import load_catalog
from mapmover.foundation_helpers import load_reference_json
from mapmover.paths import DATA_ROOT
from mapmover.runtime.source_hints import source_geometry_kind, source_geometry_subkind

EVENT_DISPLAY_PATTERNS = [
    "show me", "show the", "display", "map of", "map the",
    "where are", "where were", "where did", "where have",
    "which", "what", "list", "find",
    "struck", "hit", "affected", "impacted",
    "occurred", "happened",
    "significant", "major", "severe", "largest", "strongest", "deadliest",
    "magnitude", "category", "m4", "m5", "m6", "m7",
    "cat 1", "cat 2", "cat 3", "cat 4", "cat 5",
    "individual", "events", "event", "tracks", "track", "points",
]

AGGREGATE_PATTERNS = [
    "how many", "how much", "count", "total", "number of",
    "statistics", "stats", "average", "sum",
    "per year", "annually", "yearly", "annual", "over time",
    "trend", "compare", "frequency", "exposure",
    "per capita", "historically",
    "rolling", "between the 1990s", "between the 2010s",
    "aggregate", "aggregated",
]

EXPLICIT_EVENT_VIEW_PATTERNS = [
    "individual", "individual events", "events", "event",
    "tracks", "track", "track points", "points",
    "occurred", "happened", "struck", "hit",
    "significant", "major", "severe", "largest", "strongest", "deadliest",
    "magnitude", "category", "m4", "m5", "m6", "m7",
    "cat 1", "cat 2", "cat 3", "cat 4", "cat 5",
]

EXPLICIT_AGGREGATE_VIEW_PATTERNS = [
    "aggregate", "aggregated", "annual", "annually", "yearly", "per year",
    "count", "counts", "frequency", "trend", "compare", "rolling",
]

RECENT_EVENT_PATTERNS = [
    "most recent",
    "latest",
    "newest",
    "recent",
]

EVENT_STYLE_ADJECTIVES = (
    "significant",
    "major",
    "severe",
    "largest",
    "strongest",
    "deadliest",
)

HISTORICAL_EVENT_IMPACT_TERMS = (
    "impact",
    "impacts",
    "damage",
    "damages",
    "deaths",
    "fatalities",
    "struck",
    "hit",
    "happened",
    "occurred",
    "caused",
    "deadliest",
    "destructive",
    "most affected",
)

AGGREGATE_ONLY_PATTERNS = (
    "how many",
    "count",
    "counts",
    "number of",
    "total",
    "average",
    "avg",
    "mean",
    "sum",
    "frequency",
    "trend",
    "compare",
    "ranking",
    "rank",
    "highest",
    "lowest",
    "most affected",
    "per year",
    "rolling",
    "exposure",
    "share",
    "rate",
)


def _semantic_query_text(query: str) -> str:
    text = str(query or "").strip()
    if not text:
        return ""
    marker = " qa mode:"
    lower = text.lower()
    idx = lower.find(marker)
    if idx >= 0:
        text = text[:idx]
    return text.strip().lower()


def _catalog_sources(catalog: dict) -> list[dict]:
    sources = catalog.get("sources", [])
    return sources if isinstance(sources, list) else []


def _get_catalog_source(catalog: dict, source_id: str | None) -> dict | None:
    if not source_id:
        return None
    for source in _catalog_sources(catalog):
        if source.get("source_id") == source_id:
            return source
    return None


def _scope_matches_region(scope: str, region: str | None) -> bool:
    if not region:
        return scope == "global"
    value = str(region).lower()
    if scope == "CAN":
        return value.startswith("can") or value.startswith("canada")
    if scope == "USA":
        return value.startswith("usa") or value.startswith("us-")
    if scope == "global":
        return True
    return value.startswith(scope.lower())


def _source_supports_events(source: dict | None) -> bool:
    data_type = (source or {}).get("data_type")
    if isinstance(data_type, list):
        return "events" in data_type
    return data_type == "events"


def _source_geojson_shape(catalog_source: dict | None) -> str:
    return str((catalog_source or {}).get("geojson_shape") or "").strip().lower()


def _source_is_location_shape(catalog_source: dict | None) -> bool:
    return source_geometry_kind(catalog_source) == "entity" and source_geometry_subkind(catalog_source) == "point"


def _resolve_aggregate_admin2_dir(source_path: str) -> Path:
    source_dir = Path(source_path)
    if (
        source_dir.name.lower() == "admin2"
        and source_dir.parent.name.lower() == "aggregates"
        and source_dir.parent.parent.name.lower() == "sources"
    ):
        return source_dir.parent.parent.parent / "aggregates" / "admin2"
    if source_dir.name.lower() == "aggregates" and source_dir.parent.name.lower() == "sources":
        return source_dir.parent.parent / "aggregates" / "admin2"
    if source_dir.name.lower() == "admin2" and source_dir.parent.name.lower() == "aggregates":
        return source_dir
    if source_dir.name.lower() == "aggregates":
        return source_dir / "admin2"
    return source_dir / "aggregates" / "admin2"


def _source_has_aggregate_files(catalog_source: dict | None) -> bool:
    files = (catalog_source or {}).get("files") or {}
    if not isinstance(files, dict):
        files = {}
    if any(key in files for key in ("yearly", "rolling_10y", "rolling_20y")):
        return True

    source_path = (catalog_source or {}).get("path")
    if not source_path:
        return False
    aggregate_dir = _resolve_aggregate_admin2_dir(str(DATA_ROOT / source_path))
    candidates = (
        aggregate_dir / "yearly.parquet",
        aggregate_dir / "rolling_10y.parquet",
        aggregate_dir / "rolling_20y.parquet",
    )
    return any(path.exists() for path in candidates)


def _source_supports_aggregate_mode(catalog_source: dict | None) -> bool:
    if source_geometry_kind(catalog_source) == "entity":
        return False
    data_type = (catalog_source or {}).get("data_type")
    if isinstance(data_type, list):
        if "events" in data_type and "metrics" not in data_type:
            return False
    elif data_type == "events":
        return False
    return _source_has_aggregate_files(catalog_source)


def _query_requests_recent_events(query: str) -> bool:
    query_lower = str(query or "").strip().lower()
    if not query_lower:
        return False
    return any(pattern in query_lower for pattern in RECENT_EVENT_PATTERNS)


def _query_requests_single_latest_event(query: str) -> bool:
    query_lower = str(query or "").strip().lower()
    if not query_lower:
        return False
    if not any(pattern in query_lower for pattern in ("most recent", "latest", "newest")):
        return False
    return not any(pattern in query_lower for pattern in ("top ", "show me 10", "show 10", "ten most recent"))


def _load_disaster_overlay_reference() -> dict:
    data = load_reference_json("disasters.json")
    overlays = data.get("overlays", {}) if isinstance(data, dict) else {}
    return overlays if isinstance(overlays, dict) else {}


def _item_disaster_key(item: dict, catalog_source: dict | None) -> str | None:
    overlays = _load_disaster_overlay_reference()
    for candidate in (
        (catalog_source or {}).get("event_type"),
        item.get("pack_id"),
    ):
        text = str(candidate or "").strip().lower()
        if not text:
            continue
        if text in overlays:
            return text
        plural = f"{text}s"
        if plural in overlays:
            return plural
    return None


def _query_has_time_window(query: str) -> bool:
    query_lower = _semantic_query_text(query)
    if not query_lower:
        return False
    if re.search(r"\b(?:since|from|between|during|in)\s+\d{4}\b", query_lower):
        return True
    return any(
        token in query_lower
        for token in (
            "last 10 years",
            "last 20 years",
            "last 30 years",
            "past 10 years",
            "past 20 years",
            "past 30 years",
            "this year",
            "last year",
        )
    )


def _query_requests_event_window(query: str) -> bool:
    query_lower = _semantic_query_text(query)
    if not query_lower:
        return False
    has_event_subject = any(pattern in query_lower for pattern in EVENT_DISPLAY_PATTERNS)
    has_time_window = _query_has_time_window(query_lower)
    has_aggregate_only = any(pattern in query_lower for pattern in AGGREGATE_ONLY_PATTERNS)
    return has_event_subject and has_time_window and not has_aggregate_only


def _query_explicit_view_mode(query: str) -> tuple[bool, bool]:
    query_lower = _semantic_query_text(query)
    if not query_lower:
        return False, False
    explicit_events = any(pattern in query_lower for pattern in EXPLICIT_EVENT_VIEW_PATTERNS)
    explicit_aggregate = any(pattern in query_lower for pattern in EXPLICIT_AGGREGATE_VIEW_PATTERNS)
    return explicit_events, explicit_aggregate


def _query_signals_event_vs_aggregate(query: str) -> tuple[bool, bool]:
    query_lower = _semantic_query_text(query)
    if not query_lower:
        return False, False
    wants_events = any(pattern in query_lower for pattern in EVENT_DISPLAY_PATTERNS)
    wants_aggregate = any(pattern in query_lower for pattern in AGGREGATE_PATTERNS)
    if _query_requests_event_window(query_lower):
        wants_events = True
        wants_aggregate = False
    return wants_events, wants_aggregate


def _query_prefers_event_source(query: str) -> bool:
    query_lower = _semantic_query_text(query)
    if not query_lower:
        return False
    explicit_events, explicit_aggregate = _query_explicit_view_mode(query_lower)
    if explicit_events and not explicit_aggregate:
        return True
    if _query_requests_event_window(query_lower):
        return True
    has_event_adjective = any(re.search(rf"\b{re.escape(token)}\b", query_lower) for token in EVENT_STYLE_ADJECTIVES)
    has_aggregate_only = any(pattern in query_lower for pattern in AGGREGATE_ONLY_PATTERNS)
    has_historical_year = bool(re.search(r"\b(?:19|20)\d{2}\b", query_lower))
    has_historical_impact = any(term in query_lower for term in HISTORICAL_EVENT_IMPACT_TERMS)
    if has_historical_year and has_historical_impact and not has_aggregate_only:
        return True
    return has_event_adjective and not has_aggregate_only


def _query_semantic_filter_tokens(query: str, disaster_key: str | None) -> list[tuple[str, dict]]:
    if not disaster_key:
        return []
    overlays = _load_disaster_overlay_reference()
    overlay = overlays.get(disaster_key) or {}
    semantic_filters = overlay.get("semantic_filters") or {}
    if not isinstance(semantic_filters, dict):
        return []
    query_lower = str(query or "").strip().lower()
    matched = []
    for token, spec in semantic_filters.items():
        if not isinstance(spec, dict):
            continue
        if re.search(rf"\b{re.escape(str(token).lower())}\b", query_lower):
            matched.append((str(token), spec))
    return matched


def apply_disaster_semantic_filters(item: dict, catalog_source: dict | None, query: str) -> None:
    disaster_key = _item_disaster_key(item, catalog_source)
    matched = _query_semantic_filter_tokens(query, disaster_key)
    if not matched:
        return

    filters = item.get("filters")
    if not isinstance(filters, dict):
        filters = {}

    for _, spec in matched:
        field = str(spec.get("field") or "").strip()
        if not field or field in filters:
            continue
        if "min" in spec:
            filters[field] = {"min": spec.get("min")}
        elif "max" in spec:
            filters[field] = {"max": spec.get("max")}

    if filters:
        item["filters"] = filters


def _apply_aggregate_query_hints(item: dict, query: str) -> None:
    item["mode"] = "aggregate"
    item.pop("event_file", None)

    if item.get("aggregate_use_rolling") is None and ("rolling" in query or "last 10 years" in query or "past 10 years" in query):
        item["aggregate_use_rolling"] = True
        item["aggregate_window_years"] = 10
    elif item.get("aggregate_use_rolling") is None and ("last 20 years" in query or "past 20 years" in query):
        item["aggregate_use_rolling"] = True
        item["aggregate_window_years"] = 20
    elif item.get("aggregate_use_rolling") is None and ("last 30 years" in query or "past 30 years" in query):
        item["aggregate_use_rolling"] = True
        item["aggregate_window_years"] = 30

    if "historically" in query:
        item["aggregate_all_years"] = True

    if "countries" in query or "country" in query:
        item["aggregate_rollup_level"] = "admin_0"
    elif "counties" in query or "county" in query:
        item["aggregate_rollup_level"] = "admin_2"
    elif not item.get("region") and not item.get("aggregate_rollup_level"):
        geo_terms = (
            "county", "counties", "state", "states", "province", "provinces",
            "district", "districts", "tract", "tracts", "admin_1", "admin_2", "admin_3",
        )
        if not any(term in query for term in geo_terms):
            item["aggregate_rollup_level"] = "admin_0"


def _preferred_event_file_key(catalog_source: dict | None) -> str | None:
    files = (catalog_source or {}).get("files") or {}
    if not isinstance(files, dict):
        files = {}
    for key in ("events", "fires", "storms", "positions", "tracks"):
        if key in files:
            return key
    if _source_supports_events(catalog_source):
        return "events"
    return None


def _resolve_pack_source_by_shape(
    catalog: dict,
    pack_id: str | None,
    region: str | None,
    desired_shape: str,
) -> str | None:
    if not pack_id:
        return None
    pack_sources = [
        s for s in _catalog_sources(catalog)
        if s.get("pack_id") == pack_id and s.get("geojson_shape") == desired_shape
    ]
    if not pack_sources:
        return None
    exact_matches = [
        s for s in pack_sources
        if s.get("scope") != "global" and _scope_matches_region(s.get("scope", "global"), region)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0].get("source_id")
    global_matches = [s for s in pack_sources if s.get("scope") == "global"]
    if len(global_matches) == 1:
        return global_matches[0].get("source_id")
    if len(pack_sources) == 1:
        return pack_sources[0].get("source_id")
    return None


def _resolve_pack_aggregate_source(
    catalog: dict,
    pack_id: str | None,
    region: str | None,
) -> str | None:
    if not pack_id:
        return None
    pack_sources = [
        s for s in _catalog_sources(catalog)
        if s.get("pack_id") == pack_id and _source_supports_aggregate_mode(s)
    ]
    if not pack_sources:
        return None

    exact_matches = [
        s for s in pack_sources
        if s.get("scope") != "global" and _scope_matches_region(s.get("scope", "global"), region)
    ]
    candidates = exact_matches or pack_sources
    candidates = sorted(
        candidates,
        key=lambda s: (
            0 if "aggregate" in str(s.get("source_id") or "").lower() else 1,
            0 if _source_geojson_shape(s) == "geometry_shape" else 1,
            str(s.get("source_id") or ""),
        ),
    )
    return candidates[0].get("source_id") if candidates else None


def _pack_source_supports_metric(source: dict, metric: str) -> bool:
    source_id = str(source.get("source_id") or "").strip()
    metric_lower = str(metric or "").strip().lower()
    if not source_id or not metric_lower:
        return False
    from mapmover.data_loading import load_source_metadata

    metadata = load_source_metadata(source_id) or {}
    metrics = metadata.get("metrics") or {}
    if not isinstance(metrics, dict):
        return False
    for key, info in metrics.items():
        if str(key or "").strip().lower() == metric_lower:
            return True
        if isinstance(info, dict) and str(info.get("name") or "").strip().lower() == metric_lower:
            return True
    return False


def resolve_pack_source_for_metric(
    catalog: dict,
    pack_id: str | None,
    region: str | None,
    metric: str | None,
) -> str | None:
    if not pack_id or not metric:
        return None
    pack_sources = [s for s in _catalog_sources(catalog) if s.get("pack_id") == pack_id]
    if not pack_sources:
        return None

    exact_matches = [
        s for s in pack_sources
        if s.get("scope") != "global"
        and _scope_matches_region(s.get("scope", "global"), region)
        and _pack_source_supports_metric(s, metric)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0].get("source_id")

    global_matches = [
        s for s in pack_sources
        if s.get("scope") == "global" and _pack_source_supports_metric(s, metric)
    ]
    if len(global_matches) == 1:
        return global_matches[0].get("source_id")

    any_matches = [s for s in pack_sources if _pack_source_supports_metric(s, metric)]
    if len(any_matches) == 1:
        return any_matches[0].get("source_id")
    return None


def resolve_pack_source_by_shape(
    catalog: dict,
    pack_id: str | None,
    region: str | None,
    desired_shape: str,
) -> str | None:
    """Public wrapper for resolving a pack sibling source by geojson_shape."""
    return _resolve_pack_source_by_shape(catalog, pack_id, region, desired_shape)


def scope_matches_region(scope: str, region: str | None) -> bool:
    """Public wrapper for scope-to-region coverage matching."""
    return _scope_matches_region(scope, region)


def item_prefers_geometry_pack_source(item: dict | None) -> bool:
    """Return True when the query semantics suggest a geometry-shape sibling."""
    item = item or {}
    text = " ".join(
        str(value or "")
        for value in (
            item.get("summary"),
            item.get("metric"),
            item.get("region"),
            ((item.get("_hints") or {}).get("original_query") if isinstance(item.get("_hints"), dict) else ""),
        )
    ).lower()
    geometry_terms = (
        "county",
        "counties",
        "district",
        "districts",
        "admin_2",
        "admin2",
        "tract",
        "tracts",
        "state",
        "states",
        "province",
        "provinces",
        "top ",
        "highest",
        "lowest",
        "rank",
        "ranking",
    )
    return any(term in text for term in geometry_terms)


def resolve_pack_source(
    catalog: dict,
    pack_id: str | None,
    region: str | None,
    item: dict | None = None,
) -> str | None:
    """Resolve the best concrete source for a pack-scoped request."""
    if not pack_id:
        return None

    pack_sources = [s for s in _catalog_sources(catalog) if s.get("pack_id") == pack_id]
    if not pack_sources:
        return None

    if item_prefers_geometry_pack_source(item or {"pack_id": pack_id, "region": region}):
        geometry_sources = [s for s in pack_sources if s.get("geojson_shape") == "geometry_shape"]
        exact_geometry = [
            s for s in geometry_sources
            if s.get("scope") != "global" and _scope_matches_region(s.get("scope", "global"), region)
        ]
        if len(exact_geometry) == 1:
            return exact_geometry[0].get("source_id")

        global_geometry = [s for s in geometry_sources if s.get("scope") == "global"]
        if len(global_geometry) == 1:
            return global_geometry[0].get("source_id")

    exact_matches = [
        s for s in pack_sources
        if s.get("scope") != "global" and _scope_matches_region(s.get("scope", "global"), region)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0].get("source_id")
    if len(exact_matches) > 1:
        return None

    global_matches = [s for s in pack_sources if s.get("scope") == "global"]
    if len(global_matches) == 1:
        return global_matches[0].get("source_id")
    if len(pack_sources) == 1:
        return pack_sources[0].get("source_id")
    return None


def detect_event_mode(items: list, hints: dict = None) -> list:
    query = ""
    if hints:
        query = hints.get("original_query", "").lower()

    geography_aggregate_terms = [
        "counties", "county", "countries", "country",
        "regions", "region", "areas"
    ]
    requests_recent_events = _query_requests_recent_events(query)
    requests_single_latest_event = _query_requests_single_latest_event(query)
    wants_events, wants_aggregate = _query_signals_event_vs_aggregate(query)

    if wants_events == wants_aggregate:
        event_nouns = ["earthquake", "quake", "volcano", "eruption", "wildfire",
                      "fire", "hurricane", "cyclone", "storm", "tsunami", "tornado"]
        has_event_noun = any(noun in query for noun in event_nouns)
        has_geo_agg = any(term in query for term in geography_aggregate_terms)
        if has_event_noun and has_geo_agg:
            wants_aggregate = True
            wants_events = False
        else:
            wants_events = has_event_noun

    catalog = load_catalog()
    updated_items = []

    for item in items:
        source_id = item.get("source_id", "")
        catalog_source = _get_catalog_source(catalog, source_id)
        pack_id = item.get("pack_id") or (catalog_source or {}).get("pack_id")
        if pack_id and not item.get("pack_id"):
            item["pack_id"] = pack_id

        if wants_events and not wants_aggregate and pack_id:
            event_source_id = _resolve_pack_source_by_shape(catalog, pack_id, item.get("region"), "event_shape")
            if event_source_id:
                item["source_id"] = event_source_id
                if event_source_id != source_id:
                    item["_resolved_from_pack"] = True
                source_id = event_source_id
                catalog_source = _get_catalog_source(catalog, source_id)
        elif wants_aggregate and pack_id:
            aggregate_source_id = _resolve_pack_aggregate_source(catalog, pack_id, item.get("region"))
            if aggregate_source_id:
                item["source_id"] = aggregate_source_id
                if aggregate_source_id != source_id:
                    item["_resolved_from_pack"] = True
                source_id = aggregate_source_id
                catalog_source = _get_catalog_source(catalog, source_id)
            else:
                geometry_source_id = _resolve_pack_source_by_shape(catalog, pack_id, item.get("region"), "geometry_shape")
                if geometry_source_id and _source_supports_aggregate_mode(_get_catalog_source(catalog, geometry_source_id)):
                    item["source_id"] = geometry_source_id
                    if geometry_source_id != source_id:
                        item["_resolved_from_pack"] = True
                    source_id = geometry_source_id
                    catalog_source = _get_catalog_source(catalog, source_id)

        event_file_key = _preferred_event_file_key(catalog_source)
        supports_events = _source_supports_events(catalog_source)

        if supports_events and event_file_key and wants_events and not wants_aggregate:
            metric = item.get("metric", "")
            explicit_aggregate = metric and any(
                agg in metric.lower() for agg in ["count", "total", "sum", "avg", "mean"]
            )

            if not explicit_aggregate:
                item["mode"] = "events"
                item["event_file"] = event_file_key
                if requests_recent_events:
                    item["sort"] = {"by": "timestamp", "order": "desc"}
                    if requests_single_latest_event and not item.get("limit"):
                        item["limit"] = 1
                if metric in ("*", "all", "all_metrics", ""):
                    item.pop("metric", None)
        elif wants_aggregate and _source_supports_aggregate_mode(catalog_source):
            _apply_aggregate_query_hints(item, query)

        updated_items.append(item)

    return updated_items


def normalize_aggregate_metric_mode(items: list, hints: dict = None, catalog: dict | None = None) -> list:
    catalog = catalog or load_catalog()
    query = ""
    if hints:
        query = str(hints.get("original_query", "") or "").lower()

    updated_items = []
    for item in items:
        source_id = item.get("source_id")
        catalog_source = _get_catalog_source(catalog, source_id)
        if (
            source_id
            and not item.get("mode")
            and (catalog_source or {}).get("metrics")
            and _source_supports_aggregate_mode(catalog_source)
        ):
            _apply_aggregate_query_hints(item, query)
        updated_items.append(item)
    return updated_items


def query_prefers_event_source(query: str) -> bool:
    return _query_prefers_event_source(query)


def source_supports_aggregate_mode(catalog_source: dict | None) -> bool:
    return _source_supports_aggregate_mode(catalog_source)


def apply_aggregate_query_hints(item: dict, query: str) -> None:
    _apply_aggregate_query_hints(item, query)


def reroute_item_to_event_sibling(item: dict, catalog: dict) -> bool:
    pack_id = item.get("pack_id")
    if not pack_id:
        return False
    event_source_id = _resolve_pack_source_by_shape(catalog, pack_id, item.get("region"), "event_shape")
    if not event_source_id:
        return False
    item["source_id"] = event_source_id
    item["_resolved_from_pack"] = True
    item["mode"] = "events"
    item["event_file"] = "events"
    for field in (
        "aggregate_use_rolling",
        "aggregate_window_years",
        "aggregate_rollup_level",
        "aggregate_all_years",
    ):
        item.pop(field, None)
    return True


def reroute_item_to_aggregate_sibling(
    item: dict,
    catalog: dict,
    *,
    resolve_pack_aggregate_source_func=None,
) -> bool:
    pack_id = item.get("pack_id")
    if not pack_id:
        return False
    resolver = resolve_pack_aggregate_source_func or _resolve_pack_aggregate_source
    aggregate_source_id = resolver(catalog, pack_id, item.get("region"))
    if not aggregate_source_id:
        return False
    if str(item.get("source_id") or "").strip() == str(aggregate_source_id).strip():
        return False
    item["source_id"] = aggregate_source_id
    item["_resolved_from_pack"] = True
    item["_lock_source_id"] = True
    item.pop("mode", None)
    item.pop("event_file", None)
    item.pop("metric_label", None)
    return True
