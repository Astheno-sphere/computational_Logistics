"""Shared postprocess validation helpers."""

from __future__ import annotations

from .source_hints import (
    get_metric_alias_matches,
    get_routing_hints,
    get_single_metric_default,
    get_supported_geography_summary,
    get_unsupported_metric_aliases,
    infer_requested_geo_level_from_query,
    select_pack_family_source_for_query,
    select_query_guided_metric,
    source_geometry_kind,
    source_geometry_subkind,
)


def _should_enforce_event_count_intent(
    query: str,
    metadata: dict | None,
    inferred_metric: str | None,
) -> bool:
    """Keep a plain event-listing request from acquiring an unrelated metric.

    This is deliberately source-neutral: a source opts in by declaring an
    ``event_count`` alias.  We only replace an LLM-selected metric when every
    explicit metric phrase in the user's query resolves to that event-count
    metric.  A query that also names deaths, water height, damage, etc. keeps
    its more specific requested metric.
    """
    if str(inferred_metric or "").strip() != "event_count":
        return False
    matches = get_metric_alias_matches(metadata, query)
    return bool(matches) and {metric for _, metric in matches} == {"event_count"}


def _coerce_year_hint(value) -> int | None:
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


def _currency_granularity_source_id(item: dict) -> str | None:
    if str(item.get("pack_id") or "").strip() != "currency":
        return None
    granularity = str(item.get("time_granularity") or "").strip().lower()
    if granularity == "weekly":
        return "fx_usd_historical_weekly"
    if granularity == "monthly":
        return "fx_usd_historical_monthly"
    if granularity == "daily":
        return "fx_usd_historical"
    return None


def _apply_nri_highest_risk_filter(item: dict, metadata: dict | None, query: str, metric: str | None) -> None:
    if not isinstance(metadata, dict) or not metric:
        return
    routing_hints = get_routing_hints(metadata)
    if str(routing_hints.get("family_role") or "").strip() != "hazard_member_of_nri_pack":
        return
    query_lower = str(query or "").strip().lower()
    if not query_lower:
        return
    if not any(token in query_lower for token in ("highest risk", "highest-risk", "top 10%", "top 10 percent")):
        return
    default_metric = get_single_metric_default(metadata)
    if default_metric and str(metric).strip() != str(default_metric).strip():
        return

    filters = item.get("filters")
    if not isinstance(filters, dict):
        filters = {}
        item["filters"] = filters

    existing = filters.get(metric)
    if existing is None:
        filters[metric] = {"min": 90}
        return
    if isinstance(existing, dict):
        try:
            current_min = float(existing.get("min")) if existing.get("min") is not None else None
        except (TypeError, ValueError):
            current_min = None
        if current_min is None or current_min < 90:
            existing["min"] = 90


def _normalize_nri_highest_risk_metric(item: dict, metadata: dict | None, query: str, metric: str | None) -> str | None:
    if not isinstance(metadata, dict):
        return metric
    routing_hints = get_routing_hints(metadata)
    if str(routing_hints.get("family_role") or "").strip() != "hazard_member_of_nri_pack":
        return metric

    query_lower = str(query or "").strip().lower()
    if not any(token in query_lower for token in ("highest risk", "highest-risk", "top 10%", "top 10 percent")):
        return metric

    default_metric = get_single_metric_default(metadata)
    if not default_metric:
        return metric

    metric_text = str(metric or "").strip()
    if not metric_text:
        item["metric"] = default_metric
        return default_metric

    if metric_text in {"risk_value", "risk_score"}:
        item["metric"] = default_metric
        return default_metric

    return metric


def _build_unsupported_multi_hazard_event_weighted_clarify(
    metadata: dict | None,
    query: str,
) -> str | None:
    if not isinstance(metadata, dict):
        return None
    routing_hints = get_routing_hints(metadata)
    if str(routing_hints.get("family_role") or "").strip() != "hazard_member_of_nri_pack":
        return None

    query_lower = str(query or "").strip().lower()
    if not query_lower:
        return None

    hazard_terms = (
        "earthquake",
        "wildfire",
        "flood",
        "hurricane",
        "drought",
        "heat",
        "tornado",
        "tsunami",
        "volcano",
        "landslide",
    )
    mentioned_hazards = [term for term in hazard_terms if term in query_lower]
    if len(set(mentioned_hazards)) < 2:
        return None

    event_weight_terms = (
        "weighted by number of events",
        "weighted by events",
        "event-weighted",
        "event weighted",
    )
    if not any(term in query_lower for term in event_weight_terms):
        return None

    if "risk" not in query_lower:
        return None

    if not any(term in query_lower for term in ("county", "counties", "admin region", "admin regions")):
        return None

    return (
        "Combined multi-hazard county risk weighted by event counts needs a cross-pack aggregate join. "
        "A single NRI hazard-risk source cannot execute earthquake and wildfire event-weighted aggregates by county yet."
    )


def _build_unsupported_metric_error(metadata: dict | None, query: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    query_lower = str(query or "").strip().lower()
    if not query_lower:
        return None

    for alias in get_unsupported_metric_aliases(metadata):
        alias_text = str(alias or "").strip()
        if not alias_text or alias_text.lower() not in query_lower:
            continue
        label = alias_text.upper() if " " not in alias_text and alias_text.isalpha() and len(alias_text) <= 5 else alias_text
        source_name = metadata.get("source_name") or metadata.get("source_id") or "this source"
        metric_names = []
        for info in (metadata.get("metrics") or {}).values():
            if not isinstance(info, dict):
                continue
            name = str(info.get("name") or "").strip()
            if name:
                metric_names.append(name)
        metric_names = list(dict.fromkeys(metric_names))
        available = "; ".join(metric_names[:6])
        suffix = f" Available metrics include: {available}." if available else ""
        return (
            f"{source_name} does not include {label}. "
            f"This source supports {get_supported_geography_summary(metadata)}.{suffix}"
        )
    return None


def validate_item(
    item: dict,
    catalog: dict,
    *,
    validate_item_func,
    resolve_pack_source_func,
    get_catalog_pack_func,
    catalog_sources_func,
    get_catalog_source_func,
    normalize_item_filters_func,
    normalize_location_shape_metric_func,
    apply_disaster_semantic_filters_func,
    source_has_metrics_func,
    source_supports_aggregate_mode_func,
    apply_aggregate_query_hints_func,
    source_supports_events_func,
    query_prefers_event_source_func,
    query_requests_short_current_window_func,
    reroute_item_to_event_sibling_func,
    reroute_item_to_aggregate_sibling_func,
    resolve_pack_source_by_shape_func,
    resolve_pack_aggregate_source_func,
    load_source_metadata_func,
    expand_filter_value_aliases_func,
    source_requires_metric_func,
    get_disaster_aggregate_metric_columns_func,
    format_metric_label_func,
    resolve_pack_source_for_metric_func,
    clamp_item_years_to_metric_func,
    select_query_guided_metric_func,
) -> dict:
    """Validate one postprocessed order item against catalog and metadata."""
    item.pop("_error", None)
    item.pop("_valid", None)
    source_id = item.get("source_id")
    metric = item.get("metric")
    query = str(((item.get("_hints") or {}).get("original_query")) or "").lower()

    def _query_requests_regional_aggregate(query_text: str) -> bool:
        if not query_text:
            return False
        aggregate_terms = (
            "county", "counties", "state", "states", "province", "provinces",
            "admin region", "admin regions", "region", "regions",
            "affected by", "affected areas", "burned area", "event count",
            "frequency", "exposure", "trend", "increasing", "decreasing",
            "rank ", "ranking", "population at risk", "gdp at risk",
        )
        return any(term in query_text for term in aggregate_terms)

    if item.get("type") == "derived_result":
        item["_valid"] = True
        return item

    if item.get("type") == "derived":
        item["_valid"] = True
        item["_needs_expansion"] = True
        return item

    if not source_id and item.get("pack_id"):
        resolved_source = resolve_pack_source_func(catalog, item.get("pack_id"), item.get("region"), item)
        if not resolved_source and query:
            pack_metadata = get_catalog_pack_func(catalog, item.get("pack_id"))
            comparison_hints = (pack_metadata or {}).get("comparison_hints") or {}
            comparison_intent = item.get("_comparison_derived_intent")
            if isinstance(comparison_hints, dict):
                source_intent_defaults = comparison_hints.get("source_intent_defaults") or {}
                if isinstance(comparison_intent, dict) and isinstance(source_intent_defaults, dict):
                    intent_key = str(comparison_intent.get("type") or "").strip().lower()
                    intent_source = str(source_intent_defaults.get(intent_key) or "").strip()
                    if intent_source:
                        resolved_source = intent_source
                if not resolved_source and isinstance(comparison_intent, dict):
                    default_comparison_source = str(comparison_hints.get("default_comparison_source") or "").strip()
                    if default_comparison_source:
                        resolved_source = default_comparison_source
            goal_source_defaults = comparison_hints.get("goal_source_defaults") or {}
            if isinstance(goal_source_defaults, dict):
                for topic, topic_source_id in goal_source_defaults.items():
                    topic_text = str(topic or "").strip().lower()
                    source_text = str(topic_source_id or "").strip()
                    if topic_text and source_text and topic_text in query:
                        resolved_source = source_text
                        item["_lock_source_id"] = True
                        break
        if not resolved_source and query:
            resolved_source, _, inferred_metric = select_pack_family_source_for_query(
                str(item.get("pack_id") or "").strip(),
                query,
                catalog=catalog,
                load_source_metadata_func=load_source_metadata_func,
            )
            if inferred_metric and not item.get("metric"):
                item["metric"] = inferred_metric
        if resolved_source:
            item["source_id"] = resolved_source
            item["_resolved_from_pack"] = True
            source_id = resolved_source
        else:
            item["_valid"] = False
            item["_error"] = f"Unable to resolve pack_id '{item.get('pack_id')}' to a concrete source"
            return item

    if not source_id:
        item["_valid"] = False
        item["_error"] = "Missing source_id"
        return item

    if not item.get("pack_id"):
        pack = get_catalog_pack_func(catalog, source_id)
        if pack:
            item["pack_id"] = source_id
            item.pop("source_id", None)
            resolved_source = resolve_pack_source_func(catalog, source_id, item.get("region"), item)
            if resolved_source:
                item["source_id"] = resolved_source
                item["_resolved_from_pack"] = True
                source_id = resolved_source
            else:
                item["_valid"] = False
                item["_error"] = f"Unable to resolve pack_id '{source_id}' to a concrete source"
                return item

    sources = catalog_sources_func(catalog)
    source_ids = [s.get("source_id") for s in sources] if isinstance(sources, list) else list(sources.keys())
    if source_id not in source_ids:
        item["_valid"] = False
        item["_error"] = f"Unknown source: {source_id}"
        return item

    catalog_source = get_catalog_source_func(catalog, source_id)
    if catalog_source and not item.get("pack_id"):
        source_pack_id = str(catalog_source.get("pack_id") or "").strip()
        if source_pack_id:
            item["pack_id"] = source_pack_id
    pack_id = str(item.get("pack_id") or "").strip()
    explicit_currency_source = _currency_granularity_source_id(item)
    if explicit_currency_source and explicit_currency_source != source_id:
        item["source_id"] = explicit_currency_source
        item["_resolved_from_pack"] = True
        source_id = explicit_currency_source
        catalog_source = get_catalog_source_func(catalog, source_id)
    if pack_id and query and not item.get("_lock_source_id"):
        # Query-guided pack routing is for broad pack requests.  If the order
        # already named a concrete source_id, keep that source anchored.
        pack_routing_allowed = bool(item.get("_resolved_from_pack"))
        preferred_source_id, preferred_metadata, preferred_metric = select_pack_family_source_for_query(
            pack_id,
            query,
            catalog=catalog,
            load_source_metadata_func=load_source_metadata_func,
        )
        if explicit_currency_source:
            preferred_source_id = explicit_currency_source
        if pack_routing_allowed and preferred_source_id and preferred_source_id != source_id:
            item["source_id"] = preferred_source_id
            item["_resolved_from_pack"] = True
            source_id = preferred_source_id
            catalog_source = get_catalog_source_func(catalog, source_id)
            preferred_metadata = preferred_metadata or load_source_metadata_func(source_id)
            metric = item.get("metric")
            preferred_metrics = (preferred_metadata or {}).get("metrics") or {}
            if metric and metric not in preferred_metrics:
                item.pop("metric", None)
                metric = ""
            if item.get("_comparison_intent") and not metric:
                comparison_hints = (preferred_metadata or {}).get("comparison_hints") or {}
                comparison_metric = str(comparison_hints.get("default_comparison_metric") or "").strip()
                if comparison_metric:
                    item["metric"] = comparison_metric
                    metric = comparison_metric
            if catalog_source and not item.get("pack_id"):
                source_pack_id = str(catalog_source.get("pack_id") or "").strip()
                if source_pack_id:
                    item["pack_id"] = source_pack_id
        if preferred_source_id and preferred_source_id == source_id and preferred_metadata:
            metadata = preferred_metadata
        else:
            metadata = load_source_metadata_func(source_id)
        inferred_metric = preferred_metric or select_query_guided_metric(query, metadata)
        if inferred_metric and (not metric or _should_enforce_event_count_intent(query, metadata, inferred_metric)):
            item["metric"] = inferred_metric
            metric = inferred_metric
        inferred_geo_level = infer_requested_geo_level_from_query(query, metadata)
        if inferred_geo_level:
            item["geo_level"] = inferred_geo_level
    else:
        metadata = None
    unsupported_multi_hazard = _build_unsupported_multi_hazard_event_weighted_clarify(metadata, query)
    if unsupported_multi_hazard:
        item["_valid"] = False
        item["_error"] = unsupported_multi_hazard
        return item
    normalize_item_filters_func(item, catalog_source)
    normalize_location_shape_metric_func(item, catalog_source)
    metric = item.get("metric")
    apply_disaster_semantic_filters_func(item, catalog_source, query)

    if (
        not item.get("mode")
        and source_has_metrics_func(catalog_source)
        and source_supports_aggregate_mode_func(catalog_source)
    ):
        apply_aggregate_query_hints_func(item, query)
    elif item.get("mode") == "aggregate":
        apply_aggregate_query_hints_func(item, query)

    if item.get("mode") == "events" and not source_supports_events_func(catalog_source):
        item.pop("event_file", None)
        if (
            item.get("aggregate_use_rolling")
            or item.get("aggregate_window_years")
            or item.get("aggregate_rollup_level")
            or item.get("aggregate_all_years")
            or source_supports_aggregate_mode_func(catalog_source)
        ):
            item["mode"] = "aggregate"
        else:
            item.pop("mode", None)

    if (
        (
            query_prefers_event_source_func(query)
            or query_requests_short_current_window_func(query)
        )
        and not source_supports_events_func(catalog_source)
        and reroute_item_to_event_sibling_func(
            item,
            catalog,
            resolve_pack_source_by_shape_func=resolve_pack_source_by_shape_func,
        )
    ):
        return validate_item_func(item, catalog)

    if (
        pack_id
        and query
        and _query_requests_regional_aggregate(query)
        and item.get("mode") != "events"
        and not item.get("event_file")
        and not source_supports_aggregate_mode_func(catalog_source)
        and reroute_item_to_aggregate_sibling_func(
            item,
            catalog,
            resolve_pack_aggregate_source_func=resolve_pack_aggregate_source_func,
        )
    ):
        return validate_item_func(item, catalog)

    if item.get("mode") == "events":
        item.pop("_error", None)
        item["_valid"] = True
        return item

    metadata = metadata or load_source_metadata_func(source_id)
    unsupported_metric_error = _build_unsupported_metric_error(metadata, query)
    if unsupported_metric_error:
        item["_valid"] = False
        item["_error"] = unsupported_metric_error
        return item

    expand_filter_value_aliases_func(item, metadata)
    comparison_intent = item.get("_comparison_derived_intent")
    comparison_hints = metadata.get("comparison_hints") or {}
    if isinstance(comparison_intent, dict) and isinstance(comparison_hints, dict):
        item["_comparison_intent"] = str(comparison_intent.get("type") or "").strip().lower()
        if not metric:
            comparison_metric = str(comparison_hints.get("default_comparison_metric") or "").strip()
            if comparison_metric:
                item["metric"] = comparison_metric
                metric = comparison_metric
        has_explicit_time = item.get("year") is not None or item.get("year_start") or item.get("year_end")
        only_defaulted_time = bool(item.get("_defaulted_time_range")) and not item.get("_time_hint_applied")
        if (not has_explicit_time) or only_defaulted_time:
            default_window = comparison_hints.get("default_window") or {}
            start_year = _coerce_year_hint(comparison_intent.get("start_year")) or _coerce_year_hint(default_window.get("start_year"))
            end_year = _coerce_year_hint(comparison_intent.get("end_year"))
            if end_year is None:
                temporal = metadata.get("temporal_coverage") or {}
                end_year = _coerce_year_hint(temporal.get("end"))
            if start_year is not None and end_year is not None and start_year <= end_year:
                item["year_start"] = start_year
                item["year_end"] = end_year

    if source_requires_metric_func(item, catalog_source) and not metric:
        guided_metric = select_query_guided_metric_func(query, metadata)
        if guided_metric:
            item["metric"] = guided_metric
            metric = guided_metric
        else:
            default_metric = get_single_metric_default(metadata)
            if default_metric:
                item["metric"] = default_metric
                metric = default_metric
        if not metric and (
            query_prefers_event_source_func(query)
            or query_requests_short_current_window_func(query)
        ) and reroute_item_to_event_sibling_func(
            item,
            catalog,
            resolve_pack_source_by_shape_func=resolve_pack_source_by_shape_func,
        ):
            return validate_item_func(item, catalog)
        if not metric:
            item["_valid"] = False
            item["_error"] = f"Source '{source_id}' requires a concrete metric before execution"
            return item

    if not metadata:
        item.pop("_error", None)
        item["_valid"] = True
        return item

    metrics = metadata.get("metrics", {})
    aggregate_metric_cols = set()
    if item.get("mode") == "aggregate":
        aggregate_metric_cols = get_disaster_aggregate_metric_columns_func(catalog_source)

    if metric and metric not in metrics and metric in aggregate_metric_cols:
        item["metric_label"] = format_metric_label_func(metric)
        item.pop("_error", None)
        item["_valid"] = True
        return item

    if metric and metric not in metrics:
        metric_lower = metric.lower()
        exact_match = None
        for key in metrics.keys():
            if key.lower() == metric_lower:
                exact_match = key
                break

        if not exact_match:
            for key, value in metrics.items():
                if isinstance(value, dict):
                    name = value.get("name", "")
                    if name.lower() == metric_lower:
                        exact_match = key
                        break

        if exact_match:
            item["metric"] = exact_match
            metric = exact_match
        else:
            if item.get("mode") == "aggregate" and aggregate_metric_cols:
                aggregate_exact_match = next((col for col in aggregate_metric_cols if col.lower() == metric_lower), None)
                if aggregate_exact_match:
                    item["metric"] = aggregate_exact_match
                    item["metric_label"] = format_metric_label_func(aggregate_exact_match)
                    item.pop("_error", None)
                    item["_valid"] = True
                    return item
                aggregate_derived_match = next(
                    (
                        col for col in (
                            f"total_{metric_lower}",
                            f"avg_{metric_lower}",
                            f"max_{metric_lower}",
                        )
                        if col in aggregate_metric_cols
                    ),
                    None,
                )
                if aggregate_derived_match:
                    item["metric"] = aggregate_derived_match
                    item["metric_label"] = format_metric_label_func(aggregate_derived_match)
                    item.pop("_error", None)
                    item["_valid"] = True
                    return item

            if not item.get("_lock_source_id"):
                pack_metric_source = resolve_pack_source_for_metric_func(
                    catalog,
                    item.get("pack_id"),
                    item.get("region"),
                    metric,
                )
                if pack_metric_source and pack_metric_source != source_id:
                    item["source_id"] = pack_metric_source
                    item["_resolved_from_pack"] = True
                    return validate_item_func(item, catalog)

            close_matches = []
            for key, value in metrics.items():
                name = value.get("name", "") if isinstance(value, dict) else ""
                if metric_lower in key.lower() or key.lower() in metric_lower:
                    close_matches.append(key)
                elif name and (metric_lower in name.lower() or name.lower() in metric_lower):
                    close_matches.append(key)
            if item.get("mode") == "aggregate":
                for col in aggregate_metric_cols:
                    if metric_lower in col.lower() or col.lower() in metric_lower:
                        close_matches.append(col)
            close_matches = list(dict.fromkeys(close_matches))
            if close_matches:
                item["_valid"] = False
                item["_error"] = f"Metric '{metric}' not found. Did you mean: {', '.join(close_matches[:3])}?"
            else:
                item["_valid"] = False
                item["_error"] = f"Metric '{metric}' not found in {source_id}"
            return item

    if metric:
        metric = _normalize_nri_highest_risk_metric(item, metadata, query, metric)
        metric_info = metrics.get(metric, {})
        name = metric_info.get("name", metric)
        unit = metric_info.get("unit", "")
        if unit and unit != "unknown":
            item["metric_label"] = f"{name} ({unit})"
        else:
            item["metric_label"] = name

        clamp_item_years_to_metric_func(item, metadata, metric)
        _apply_nri_highest_risk_filter(item, metadata, query, metric)

    if not item.get("sort") and metric:
        row_count = metadata.get("row_count") if isinstance(metadata, dict) else None
        geometry_kind = source_geometry_kind(metadata)
        geometry_subkind = source_geometry_subkind(metadata)
        if (
            isinstance(row_count, int)
            and row_count >= 50000
            and (
                geometry_kind == "admin"
                or (geometry_kind == "entity" and geometry_subkind == "area")
            )
            and any(term in query for term in ("tallest", "highest", "lowest", "top ", "most "))
        ):
            item["sort"] = {"by": metric, "order": "desc", "limit": 100}

    item.pop("_error", None)
    item["_valid"] = True
    return item


__all__ = ["validate_item"]
