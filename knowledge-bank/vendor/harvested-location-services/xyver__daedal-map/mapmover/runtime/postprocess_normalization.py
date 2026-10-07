"""Shared postprocess normalization helpers."""

from __future__ import annotations

import json


def _coerce_temporal_year(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _normalize_filter_alias_text(value) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _build_filter_field_aliases(metadata: dict | None) -> dict[str, str]:
    if not isinstance(metadata, dict):
        return {}

    aliases: dict[str, str] = {}

    def _register(alias_value, field_name: str) -> None:
        alias_text = _normalize_filter_alias_text(alias_value)
        target_text = str(field_name or "").strip()
        if alias_text and target_text:
            aliases.setdefault(alias_text, target_text)

    for field_name in metadata.get("filterable_fields") or []:
        _register(field_name, field_name)

    dimensions = metadata.get("dimensions") if isinstance(metadata.get("dimensions"), dict) else {}
    for dim_key, dim_spec in dimensions.items():
        if isinstance(dim_spec, dict):
            column = str(dim_spec.get("column") or dim_key).strip()
            for alias_value in (
                dim_key,
                column,
                dim_spec.get("name"),
                dim_spec.get("label"),
            ):
                _register(alias_value, column)
        else:
            _register(dim_key, dim_key)

    return aliases


def normalize_item_filters(
    item: dict,
    catalog_source: dict | None,
    *,
    load_source_metadata_func,
) -> None:
    metadata = None
    filterable_fields = (catalog_source or {}).get("filterable_fields") or []
    if not filterable_fields:
        source_id = item.get("source_id")
        metadata = load_source_metadata_func(source_id) if source_id else {}
        filterable_fields = (metadata or {}).get("filterable_fields") or []
    if not isinstance(filterable_fields, list) or not filterable_fields:
        return

    filters = item.get("filters")
    if not isinstance(filters, dict):
        filters = {}

    reserved = {
        "type", "source_id", "pack_id", "metric", "metric_label", "region", "year", "year_start", "year_end",
        "date_start", "date_end", "time_granularity", "aggregation", "aggregation_axis", "missing_policy", "weight_metric", "week_anchor",
        "geo_level", "mode", "event_file", "filters", "sort", "limit", "summary", "all_sources", "load_scope",
        "aggregate_use_rolling", "aggregate_window_years", "aggregate_rollup_level", "aggregate_all_years",
    }

    moved = False
    for field_name in filterable_fields:
        if field_name == "loc_id":
            continue
        if field_name in item and field_name not in reserved and field_name not in filters:
            filters[field_name] = item.pop(field_name)
            moved = True

    if moved or filters:
        if metadata is None:
            source_id = item.get("source_id")
            metadata = load_source_metadata_func(source_id) if source_id else {}
        field_aliases = _build_filter_field_aliases(metadata)
        if field_aliases:
            normalized_filters = {}
            for field_name, field_value in filters.items():
                mapped_field = field_aliases.get(_normalize_filter_alias_text(field_name), field_name)
                if mapped_field in normalized_filters:
                    continue
                normalized_filters[mapped_field] = field_value
            filters = normalized_filters
        item["filters"] = filters


def normalize_location_shape_metric(
    item: dict,
    catalog_source: dict | None,
    *,
    source_is_location_shape_func,
) -> None:
    if not source_is_location_shape_func(catalog_source):
        return
    metric = str(item.get("metric") or "").strip().lower()
    if metric in {"", "*", "all", "all_metrics", "latitude", "longitude", "lat", "lon", "lng"}:
        item.pop("metric", None)


def expand_filter_value_aliases(item: dict, metadata: dict | None) -> None:
    filters = item.get("filters")
    if not isinstance(filters, dict) or not filters:
        return
    routing_hints = metadata.get("routing_hints", {}) if isinstance(metadata, dict) else {}
    filter_aliases = routing_hints.get("filter_value_aliases") or {}
    if not isinstance(filter_aliases, dict):
        return

    for field, alias_map in filter_aliases.items():
        if field not in filters or not isinstance(alias_map, dict):
            continue
        raw_value = filters.get(field)
        values = raw_value if isinstance(raw_value, (list, tuple, set)) else [raw_value]
        expanded: list = []
        changed = False
        for value in values:
            if value is None:
                continue
            alias_key = str(value).strip().lower()
            mapped = alias_map.get(alias_key)
            if isinstance(mapped, list):
                expanded.extend(mapped)
                changed = True
            elif mapped is not None:
                expanded.append(mapped)
                changed = True
            else:
                expanded.append(value)
        if changed:
            deduped = []
            seen = set()
            for value in expanded:
                marker = json.dumps(value, sort_keys=True, default=str)
                if marker in seen:
                    continue
                seen.add(marker)
                deduped.append(value)
            filters[field] = deduped
    item["filters"] = filters


def format_metric_label(metric_key: str) -> str:
    return str(metric_key or "").replace("_", " ").strip().title()


def clamp_item_years_to_metric(
    item: dict,
    metadata: dict | None,
    metric_key: str | None,
    *,
    metadata_metric_year_range_func,
) -> None:
    metric_min_year, metric_max_year = metadata_metric_year_range_func(metadata, metric_key)
    if metric_min_year is None or metric_max_year is None:
        return

    changed = False

    year = item.get("year")
    if isinstance(year, int):
        clamped_year = min(max(year, metric_min_year), metric_max_year)
        if clamped_year != year:
            item["year"] = clamped_year
            changed = True

    year_start = item.get("year_start")
    year_end = item.get("year_end")
    if isinstance(year_start, int) and isinstance(year_end, int):
        clamped_start = max(year_start, metric_min_year)
        clamped_end = min(year_end, metric_max_year)
        if clamped_start > clamped_end:
            clamped_start = metric_min_year
            clamped_end = metric_max_year
        if clamped_start != year_start:
            item["year_start"] = clamped_start
            changed = True
        if clamped_end != year_end:
            item["year_end"] = clamped_end
            changed = True

    item["_metric_year_range"] = {"min": metric_min_year, "max": metric_max_year}
    if changed:
        item["_time_range_clamped"] = True


def rewrite_processed_order_summary(
    order: dict,
    validated_items: list[dict],
    *,
    load_source_metadata_func,
) -> str | None:
    if not validated_items:
        return order.get("summary")
    if not any(item.get("_time_range_clamped") for item in validated_items):
        return order.get("summary")
    if len(validated_items) != 1:
        return order.get("summary")

    item = validated_items[0]
    if not item.get("_valid"):
        return order.get("summary")

    metric_label = str(item.get("metric_label") or item.get("metric") or item.get("source_id") or "Result").strip()
    source_id = str(item.get("source_id") or "").strip()
    metadata = load_source_metadata_func(source_id) or {}
    source_name = str(metadata.get("source_name") or source_id).strip()
    region = str(item.get("region") or "").strip()
    year = item.get("year")
    year_start = item.get("year_start")
    year_end = item.get("year_end")

    if isinstance(year, int):
        time_text = f"in {year}"
    elif isinstance(year_start, int) and isinstance(year_end, int):
        time_text = f"in {year_start}" if year_start == year_end else f"from {year_start} to {year_end}"
    else:
        metric_range = item.get("_metric_year_range") or {}
        metric_min_year = metric_range.get("min")
        metric_max_year = metric_range.get("max")
        if isinstance(metric_min_year, int) and isinstance(metric_max_year, int):
            time_text = f"in {metric_min_year}" if metric_min_year == metric_max_year else f"from {metric_min_year} to {metric_max_year}"
        else:
            return order.get("summary")

    if region and region.lower() != "global":
        return f"{metric_label} for {region} {time_text} under {source_name}"
    return f"{metric_label} {time_text} under {source_name}"


def normalize_source_declared_scope(
    item: dict,
    *,
    load_source_metadata_func,
    load_source_reference_func=None,
) -> dict:
    source_id = item.get("source_id")
    if not source_id:
        return item

    metadata = load_source_metadata_func(source_id) or {}
    reference = load_source_reference_func(source_id) or {} if load_source_reference_func else {}
    coverage = metadata.get("geographic_coverage", {}) or {}
    reference_scope = reference.get("scope", {}) if isinstance(reference, dict) else {}
    metadata_scope = metadata.get("scope", {}) or {}
    scope = reference_scope if isinstance(reference_scope, dict) else {}
    if not scope and isinstance(metadata_scope, dict):
        scope = metadata_scope
    canonical_region = str(
        coverage.get("canonical_region")
        or metadata.get("canonical_region")
        or scope.get("canonical_region")
        or ""
    ).strip().lower()
    if not canonical_region:
        return item

    aliases_raw = (
        coverage.get("region_aliases")
        or metadata.get("region_aliases")
        or scope.get("region_aliases")
        or []
    )
    aliases = {
        str(alias).strip().lower()
        for alias in aliases_raw
        if str(alias).strip()
    }
    loc_id_anchor = str(
        coverage.get("loc_id_anchor")
        or metadata.get("loc_id_anchor")
        or scope.get("loc_id_anchor")
        or ""
    ).strip()

    region = str(item.get("region") or "").strip().lower()
    if not region or region == canonical_region or region in aliases:
        item["region"] = loc_id_anchor or canonical_region
    return item


def apply_comparison_defaults(
    item: dict,
    metadata: dict | None,
    derived_intent: dict | None,
) -> None:
    if not isinstance(item, dict) or not isinstance(metadata, dict) or not isinstance(derived_intent, dict):
        return

    if str(derived_intent.get("family") or "").strip().lower() != "comparison":
        return

    comparison_hints = metadata.get("comparison_hints")
    if not isinstance(comparison_hints, dict):
        return

    intent_type = str(derived_intent.get("type") or "").strip().lower()
    supported_modes = {
        str(mode).strip().lower()
        for mode in (comparison_hints.get("supported_modes") or [])
        if str(mode).strip()
    }
    if intent_type and supported_modes and intent_type not in supported_modes:
        return

    default_metric = str(comparison_hints.get("default_comparison_metric") or "").strip()
    if default_metric and not item.get("metric"):
        item["metric"] = default_metric

    has_explicit_time = item.get("year") is not None or item.get("year_start") or item.get("year_end")
    only_defaulted_time = bool(item.get("_defaulted_time_range")) and not item.get("_time_hint_applied")
    if has_explicit_time and not only_defaulted_time:
        item["_comparison_intent"] = intent_type
        return

    default_window = comparison_hints.get("default_window") or {}
    start_year = derived_intent.get("start_year") or default_window.get("start_year")
    end_year = derived_intent.get("end_year")
    if not end_year:
        temporal = metadata.get("temporal_coverage") or {}
        end_year = _coerce_temporal_year(temporal.get("end"))

    if start_year and end_year and int(start_year) <= int(end_year):
        item["year_start"] = int(start_year)
        item["year_end"] = int(end_year)

    item["_comparison_intent"] = intent_type


def build_comparison_derived_spec(
    item: dict,
    metadata: dict | None,
) -> dict | None:
    if not isinstance(item, dict) or not isinstance(metadata, dict):
        return None

    comparison_hints = metadata.get("comparison_hints")
    if not isinstance(comparison_hints, dict):
        return None

    intent_type = str(item.get("_comparison_intent") or "").strip().lower()
    if intent_type not in {"improvement", "decline", "change", "volatility"}:
        return None

    metric_key = str(item.get("metric") or "").strip()
    if not metric_key:
        return None

    year_start = item.get("year_start")
    year_end = item.get("year_end")
    if not isinstance(year_start, int) or not isinstance(year_end, int) or year_start >= year_end:
        return None

    metric_hints = (comparison_hints.get("metrics") or {}).get(metric_key) or {}
    better_direction = str(metric_hints.get("better_direction") or "").strip().lower()
    metric_name = str((((metadata.get("metrics") or {}).get(metric_key) or {}).get("name")) or metric_key).strip()

    if intent_type == "improvement":
        label = f"Improvement in {metric_name} since {year_start}"
    elif intent_type == "decline":
        label = f"Decline in {metric_name} since {year_start}"
    elif intent_type == "volatility":
        label = f"Change magnitude in {metric_name} since {year_start}"
    else:
        label = f"Change in {metric_name} since {year_start}"

    return {
        "type": "derived_result",
        "calculation": "time_delta",
        "intent": intent_type,
        "metric": metric_key,
        "metric_candidates": [metric_key, metric_name],
        "start_year": year_start,
        "end_year": year_end,
        "better_direction": better_direction,
        "label": label,
    }
