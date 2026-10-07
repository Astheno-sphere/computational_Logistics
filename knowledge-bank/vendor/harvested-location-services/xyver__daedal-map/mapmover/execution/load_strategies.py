"""Load-strategy helpers extracted from the main executor."""

from __future__ import annotations

import re
import time

import pandas as pd

from mapmover.runtime.geography_reference import canonicalize_loc_id
from mapmover.runtime.source_hints import resolve_geo_contract

USA_STATE_ABBREVIATIONS = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}

USA_STATE_ABBREVIATION_VALUES = {value.lower(): value for value in USA_STATE_ABBREVIATIONS.values()}


def _normalize_loc_id_like_token(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = canonicalize_loc_id(text)
    if normalized.startswith("EEZ-") or re.fullmatch(r"X[A-Z0-9]{1,7}", normalized):
        return normalized

    parts = [segment for segment in normalized.split("-") if segment]
    if not parts or len(parts[0]) not in {2, 3} or not parts[0].isalpha():
        return ""

    for segment in parts[1:]:
        if segment.startswith("G") and segment[1:].isdigit():
            continue
        if segment.isdigit():
            continue
        if segment.isalnum() and len(segment) <= 5:
            continue
        return ""

    return normalized


def _classify_pushdown_filters(filters: dict | None) -> tuple[dict, dict, list[tuple[str, str, object]]]:
    """Translate generic order filters into the shared select_rows contract."""
    exact_filters: dict = {}
    in_filters: dict = {}
    compare_filters: list[tuple[str, str, object]] = []

    if not isinstance(filters, dict) or not filters:
        return exact_filters, in_filters, compare_filters

    for field, value in filters.items():
        if field.endswith("_min"):
            col = field[:-4]
            if col and value is not None:
                compare_filters.append((col, ">=", value))
            continue
        if field.endswith("_max"):
            col = field[:-4]
            if col and value is not None:
                compare_filters.append((col, "<=", value))
            continue

        if isinstance(value, dict):
            min_value = value.get("min")
            max_value = value.get("max")
            if min_value is not None:
                compare_filters.append((field, ">=", min_value))
            if max_value is not None:
                compare_filters.append((field, "<=", max_value))

            op = str(value.get("op") or "").strip().lower()
            if op == "in":
                candidates = [candidate for candidate in (value.get("values") or []) if candidate is not None]
                if candidates:
                    in_filters[field] = candidates
            elif op in {"eq", "="} and "value" in value:
                exact_filters[field] = value.get("value")
            elif op in {"!=", "ne", ">", "gt", ">=", "gte", "<", "lt", "<=", "lte"} and "value" in value:
                op_map = {
                    "!=": "!=",
                    "ne": "!=",
                    ">": ">",
                    "gt": ">",
                    ">=": ">=",
                    "gte": ">=",
                    "<": "<",
                    "lt": "<",
                    "<=": "<=",
                    "lte": "<=",
                }
                compare_filters.append((field, op_map[op], value.get("value")))
            continue

        if isinstance(value, (list, tuple, set)):
            candidates = [candidate for candidate in value if candidate is not None]
            if candidates:
                in_filters[field] = candidates
            continue

        if isinstance(value, bool):
            exact_filters[field] = value
            continue

        if value is not None:
            exact_filters[field] = value

    return exact_filters, in_filters, compare_filters


def _timestamp_pushdown_bounds(item: dict, year: int | None, year_start: int | None, year_end: int | None) -> tuple[str | None, str | None]:
    """Return inclusive ISO-UTC bounds for a timestamp-backed source."""
    raw_start = item.get("date_start")
    raw_end = item.get("date_end")
    start = pd.to_datetime(raw_start, errors="coerce", utc=True)
    end = pd.to_datetime(raw_end, errors="coerce", utc=True)

    if pd.isna(start):
        selected_start = year_start if year_start is not None else year
        if selected_start is not None:
            start = pd.Timestamp(int(selected_start), 1, 1, tz="UTC")
    if pd.isna(end):
        selected_end = year_end if year_end is not None else year
        if selected_end is not None:
            end = pd.Timestamp(int(selected_end), 12, 31, 23, 59, 59, tz="UTC")

    # A bare YYYY-MM end means the whole calendar month, rather than midnight
    # at its first day.
    if isinstance(raw_end, str) and re.fullmatch(r"\d{4}-\d{2}", raw_end.strip()) and not pd.isna(end):
        end = end + pd.offsets.MonthEnd(1) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    def format_bound(value):
        return None if pd.isna(value) else value.strftime("%Y-%m-%dT%H:%M:%SZ")

    return format_bound(start), format_bound(end)


def _source_max_admin_level(metadata: dict | None) -> int | None:
    if not isinstance(metadata, dict):
        return None

    coverage = metadata.get("geographic_coverage") if isinstance(metadata.get("geographic_coverage"), dict) else {}
    admin_levels = coverage.get("admin_levels") if isinstance(coverage.get("admin_levels"), list) else []
    candidates = []
    for level in admin_levels:
        try:
            candidates.append(int(level))
        except (TypeError, ValueError):
            pass

    geographic_level = metadata.get("geographic_level")
    values = geographic_level if isinstance(geographic_level, list) else [geographic_level]
    for value in values:
        text = str(value or "").strip().lower()
        if text.startswith("admin_") and text[6:].isdigit():
            candidates.append(int(text[6:]))

    return max(candidates) if candidates else None


def _source_country(metadata: dict | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    coverage = metadata.get("geographic_coverage") if isinstance(metadata.get("geographic_coverage"), dict) else {}
    return str(coverage.get("country") or metadata.get("country") or "").strip().upper()


def _resolve_usa_state_prefix(region: str | None) -> str:
    if not region:
        return ""

    region_text = str(region or "").strip().lower().replace("_", " ").replace("-", " ")
    for suffix in (" state", " usa", " us"):
        if region_text.endswith(suffix):
            region_text = region_text[: -len(suffix)].strip()
    abbrev = USA_STATE_ABBREVIATIONS.get(region_text) or USA_STATE_ABBREVIATION_VALUES.get(region_text)
    if abbrev:
        return f"USA-{abbrev}"
    return ""


def collect_source_metadata(
    *,
    items: list,
    expand_region_func,
    load_disaster_aggregate_data_func,
    load_source_metadata_func,
    logger,
    trace_id: str,
) -> dict:
    """Collect source metadata and cache aggregate loads before item execution."""
    target_countries = set()
    geo_levels = set()
    sources_used = {}
    aggregate_item_cache = {}

    for item in items:
        region = item.get("region")
        countries = expand_region_func(region)
        if countries:
            target_countries.update(countries)

        source_id = item.get("source_id")
        if source_id and source_id not in sources_used:
            try:
                aggregate_like_source = str(source_id or "").strip().endswith("_aggregates")
                if item.get("mode") == "aggregate" or aggregate_like_source:
                    aggregate_df, metadata = load_disaster_aggregate_data_func(source_id, item)
                    if aggregate_df is None:
                        metadata = load_source_metadata_func(source_id)
                    else:
                        cache_key = (
                            source_id,
                            item.get("metric"),
                            item.get("region"),
                            item.get("year"),
                            item.get("year_start"),
                            item.get("year_end"),
                            item.get("aggregate_use_rolling"),
                            item.get("aggregate_window_years"),
                            item.get("aggregate_rollup_level"),
                            item.get("aggregate_all_years"),
                            None,
                            (),
                            (),
                            (),
                        )
                        aggregate_item_cache[cache_key] = (aggregate_df, dict(metadata or {}))
                else:
                    metadata = load_source_metadata_func(source_id)
                if not metadata:
                    raise ValueError(f"Could not load metadata for {source_id}")
                sources_used[source_id] = metadata
                geographic_level = metadata.get("geographic_level", "country")
                if isinstance(geographic_level, list):
                    for level in geographic_level:
                        geo_levels.add(level)
                else:
                    geo_levels.add(geographic_level)
            except Exception as exc:
                logger.warning(f"[executor:{trace_id}] failed to collect source metadata for {source_id}: {exc}")

    return {
        "target_countries": target_countries,
        "geo_levels": geo_levels,
        "sources_used": sources_used,
        "aggregate_item_cache": aggregate_item_cache,
    }


def load_order_item_dataframe(
    *,
    item: dict,
    temporal_mode: bool,
    aggregate_item_cache: dict,
    load_disaster_aggregate_data_func,
    load_source_data_func,
    expand_region_func=None,
    load_source_metadata_func=None,
) -> tuple:
    """Load one order item's dataframe and metadata using the current strategy."""
    year = item.get("year")
    year_start = item.get("year_start")
    year_end = item.get("year_end")
    region = item.get("region")
    if not region:
        _plural_regions = item.get("regions")
        if isinstance(_plural_regions, (list, tuple)) and len(_plural_regions) == 1 and _plural_regions[0]:
            region = str(_plural_regions[0])
    filters = item.get("filters") or {}
    if not isinstance(filters, dict):
        filters = {}
    metric = item.get("metric")
    source_id = item.get("source_id")
    aggregate_like_source = str(source_id or "").strip().endswith("_aggregates")

    source_metadata = {}
    if source_id and load_source_metadata_func is not None:
        try:
            source_metadata = load_source_metadata_func(source_id) or {}
        except Exception:
            source_metadata = {}
    source_temporal = source_metadata.get("temporal_coverage") if isinstance(source_metadata.get("temporal_coverage"), dict) else {}
    source_time_field = str(source_temporal.get("field") or source_metadata.get("time_field") or "").strip()
    source_granularity = str(source_temporal.get("granularity") or source_temporal.get("frequency") or "").strip().lower()
    # Annual tables with both timestamp and year use the integer year for
    # filtering.  It is timezone-safe and lets the query push down the full
    # requested timeline before any generic row cap is considered.
    timestamp_backed_source = (
        source_time_field in {"timestamp", "date", "time", "month", "week"}
        and source_granularity not in {"annual", "year", "yearly"}
    )

    # Year is only a safe storage predicate for sources that actually carry a
    # year column. Timestamp-backed monthly/daily sources need ISO bounds so a
    # request for December does not silently load an arbitrary capped slice.
    pushdown_year = year if (year and not year_start and not year_end and not timestamp_backed_source) else None
    pushdown_prefix = _normalize_loc_id_like_token(region)
    filters_for_pushdown = dict(filters)
    filter_loc_id_prefix = _normalize_loc_id_like_token(filters_for_pushdown.pop("loc_id_prefix", ""))
    if not pushdown_prefix and filter_loc_id_prefix:
        pushdown_prefix = filter_loc_id_prefix
    # Filter location at the source for named regions when the source's loc_id
    # contract makes that safe. Marine sources need X*/EEZ-* resolution. USA
    # admin_2+ USA sources need state/county prefixes before the render cap, or a
    # query like "North Carolina tracts" may load an unrelated national slice
    # and then filter to zero.
    # See live_source_qa_checklist.md (time-before-location / cap-window trap).
    if (
        not pushdown_prefix
        and region
        and expand_region_func is not None
        and load_source_metadata_func is not None
        and source_id
    ):
        is_marine = False
        is_usa_high_admin = False
        try:
            _meta = source_metadata
            is_marine = str(_meta.get("geographic_level") or "").strip().lower() == "marine_zone"
            is_usa_high_admin = _source_country(_meta) == "USA" and (_source_max_admin_level(_meta) or 0) >= 2
        except Exception:
            is_marine = False
            is_usa_high_admin = False
        if is_marine:
            try:
                _resolved = expand_region_func(region, prefer_water_body=True)
            except TypeError:
                _resolved = expand_region_func(region)
            if isinstance(_resolved, (set, list, tuple)) and len(_resolved) == 1:
                _code = _normalize_loc_id_like_token(next(iter(_resolved)))
                if _code:
                    pushdown_prefix = _code
        elif is_usa_high_admin:
            state_prefix = _resolve_usa_state_prefix(region)
            if state_prefix:
                pushdown_prefix = state_prefix
            else:
                try:
                    _resolved = expand_region_func(region)
                except TypeError:
                    _resolved = expand_region_func(region, prefer_water_body=False)
                loc_prefixes = [
                    _normalize_loc_id_like_token(value)
                    for value in (_resolved or [])
                    if str(value or "").strip().upper().startswith("USA-")
                ]
                loc_prefixes = [value for value in loc_prefixes if value]
                if len(loc_prefixes) == 1:
                    pushdown_prefix = loc_prefixes[0]

    # Time-before-location for broad queries: when no specific location is being
    # pushed down and the time range was auto-defaulted by the order-taker (not
    # explicitly requested), drop the range so the latest year is loaded for ALL
    # locations. Otherwise a wide default range (e.g. 10 years x ~300 monthly
    # marine zones) overflows the row cap and truncates to an alphabetical slice
    # of zones -- showing 44 regions instead of the whole world. A specific
    # location (pushdown_prefix set) keeps its full range so "that place across a
    # long time" still loads its whole series. An explicit user-requested range
    # has no _defaulted_time_range marker and is always honored.
    # See live_source_qa_checklist.md (time-before-location / cap-window trap).
    if (
        not pushdown_prefix
        and pushdown_year is None
        and item.get("_defaulted_time_range")
        and (year_start is not None or year_end is not None)
    ):
        # Collapse to the latest year of the defaulted range and push it down
        # explicitly. Nulling the range is not enough: a range elsewhere flips
        # the executor into temporal/animation mode, which suppresses the
        # latest-year default, so we set the single-year pushdown directly.
        latest_default_year = year_end if year_end is not None else year_start
        year = latest_default_year
        pushdown_year = latest_default_year
        year_start = None
        year_end = None

    exact_filters, in_filters, compare_filters = _classify_pushdown_filters(filters_for_pushdown)
    requested_geo_level = item.get("geo_level")
    if requested_geo_level and load_source_metadata_func is not None and "geo_level" not in exact_filters:
        try:
            source_metadata = load_source_metadata_func(source_id) if source_id else {}
        except Exception:
            source_metadata = {}
        geo_contract = resolve_geo_contract(requested_geo_level, source_metadata)
        if (
            geo_contract.source_filter_field == "geo_level"
            and geo_contract.filter_strategy == "equals"
            and geo_contract.source_level_value
        ):
            exact_filters["geo_level"] = geo_contract.source_level_value
    if timestamp_backed_source:
        timestamp_start, timestamp_end = _timestamp_pushdown_bounds(item, year, year_start, year_end)
        if timestamp_start is not None:
            compare_filters.append((source_time_field, ">=", timestamp_start))
        if timestamp_end is not None:
            compare_filters.append((source_time_field, "<=", timestamp_end))
    elif pushdown_year is None:
        if year_start is not None:
            compare_filters.append(("year", ">=", year_start))
        if year_end is not None:
            compare_filters.append(("year", "<=", year_end))
    requested_columns = [
        "loc_id",
        "geo_level",
        "year",
        "timestamp",
        "date",
        "time",
        "month",
        "week",
        "lat",
        "latitude",
        "centroid_lat",
        "lon",
        "longitude",
        "centroid_lon",
        "end_latitude",
        "end_longitude",
    ]
    if metric:
        requested_columns.append(str(metric))
    sort_spec = item.get("sort")
    if isinstance(sort_spec, dict) and sort_spec.get("by"):
        requested_columns.append(str(sort_spec.get("by")))
    requested_columns.extend(str(field).strip() for field in filters.keys() if str(field).strip())
    requested_columns = [value for value in dict.fromkeys(requested_columns) if value]

    if item.get("mode") == "aggregate" or aggregate_like_source:
        cache_key = (
            item.get("source_id"),
            item.get("metric"),
            item.get("region"),
            item.get("year"),
            item.get("year_start"),
            item.get("year_end"),
            item.get("aggregate_use_rolling"),
            item.get("aggregate_window_years"),
            item.get("aggregate_rollup_level"),
            item.get("aggregate_all_years"),
            pushdown_prefix,
            tuple(sorted((exact_filters or {}).items())),
            tuple((field, tuple(values) if isinstance(values, list) else values) for field, values in sorted((in_filters or {}).items())),
            tuple(compare_filters or []),
        )
        cached = aggregate_item_cache.get(cache_key)
        if cached is not None:
            return cached[0].copy(), dict(cached[1] or {})
        df, metadata = load_disaster_aggregate_data_func(item.get("source_id"), item)
        if df is None or metadata is None:
            return load_source_data_func(
                item.get("source_id"),
                year=pushdown_year,
                loc_id_prefix=pushdown_prefix,
                exact_filters=exact_filters or None,
                in_filters=in_filters or None,
                compare_filters=compare_filters or None,
                columns=requested_columns,
                prefer_latest_year_when_unspecified=not temporal_mode and year is None and year_start is None and year_end is None,
                requested_limit=None if sort_spec else item.get("limit"),
                data_file=item.get("data_file"),
            )
        return df, metadata

    return load_source_data_func(
        item.get("source_id"),
        year=pushdown_year,
        loc_id_prefix=pushdown_prefix,
        exact_filters=exact_filters or None,
        in_filters=in_filters or None,
        compare_filters=compare_filters or None,
        columns=requested_columns,
        prefer_latest_year_when_unspecified=not temporal_mode and year is None and year_start is None and year_end is None,
        requested_limit=None if sort_spec else item.get("limit"),
        data_file=item.get("data_file"),
    )
