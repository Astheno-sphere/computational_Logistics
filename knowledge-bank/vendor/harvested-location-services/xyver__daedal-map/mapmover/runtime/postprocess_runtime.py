"""Shared runtime implementation for postprocess order workflow."""

from __future__ import annotations

import logging

from mapmover.data_loading import get_pack_metadata, load_catalog, load_source_metadata, load_source_reference
from mapmover.duckdb_helpers import parquet_columns
from mapmover.foundation_helpers import load_reference_json
from mapmover.paths import DATA_ROOT
from mapmover.runtime.aggregate_primitives import (
    apply_aggregate_query_hints as apply_aggregate_query_hints_impl,
    get_disaster_aggregate_metric_columns as get_disaster_aggregate_metric_columns_impl,
    source_has_aggregate_files as source_has_aggregate_files_impl,
    source_has_metrics as source_has_metrics_impl,
    source_is_location_shape as source_is_location_shape_impl,
    source_supports_aggregate_mode as source_supports_aggregate_mode_impl,
)
from mapmover.runtime.clarify_primitives import build_clarify_result
from mapmover.runtime.clarify_routing_primitives import (
    build_multiple_paths_clarify as build_multiple_paths_clarify_impl,
    build_pack_load_clarify as build_pack_load_clarify_impl,
    detect_full_pack_load_clarify as detect_full_pack_load_clarify_impl,
    detect_multiple_path_clarify as detect_multiple_path_clarify_impl,
    expand_full_pack_loads as expand_full_pack_loads_impl,
)
from mapmover.runtime.derived_fields import (
    DEFAULT_DERIVED_EXPANSIONS,
    expand_all_derived_fields as expand_all_derived_fields_impl,
)
from mapmover.runtime.disaster_semantic_filters import (
    apply_disaster_semantic_filters as apply_disaster_semantic_filters_impl,
    item_disaster_key as item_disaster_key_impl,
    load_disaster_overlays as load_disaster_overlays_impl,
    query_semantic_filter_tokens as query_semantic_filter_tokens_impl,
)
from mapmover.runtime.metric_expansion import (
    expand_wildcard_metrics as expand_wildcard_metrics_impl,
)
from mapmover.runtime.order_routing import (
    normalize_order_items as normalize_order_items_impl,
    resolve_source_for_item as resolve_source_for_item_impl,
)
from mapmover.runtime.order_semantics import (
    detect_event_mode as detect_event_mode_impl,
    normalize_aggregate_metric_mode as normalize_aggregate_metric_mode_impl,
    resolve_pack_source as resolve_pack_source_impl,
    reroute_item_to_aggregate_sibling as reroute_item_to_aggregate_sibling_impl,
    resolve_pack_source_by_shape,
    _resolve_pack_aggregate_source as resolve_pack_aggregate_source_impl,
    resolve_pack_source_for_metric,
)
from mapmover.runtime.population_resolution import (
    find_population_metric_key as find_population_metric_key_impl,
    get_source_admin_levels as get_source_admin_levels_impl,
    resolve_population_dependency as resolve_population_dependency_impl,
    scope_matches_population_region as scope_matches_population_region_impl,
)
from mapmover.runtime.postprocess_contracts import build_processed_order_result
from mapmover.runtime.postprocess_normalization import (
    apply_comparison_defaults as apply_comparison_defaults_impl,
    build_comparison_derived_spec as build_comparison_derived_spec_impl,
    clamp_item_years_to_metric as clamp_item_years_to_metric_impl,
    expand_filter_value_aliases as expand_filter_value_aliases_impl,
    format_metric_label as format_metric_label_impl,
    normalize_item_filters as normalize_item_filters_impl,
    normalize_location_shape_metric as normalize_location_shape_metric_impl,
    normalize_source_declared_scope as normalize_source_declared_scope_impl,
    rewrite_processed_order_summary as rewrite_processed_order_summary_impl,
)
from mapmover.runtime.postprocess_pipeline import (
    apply_event_qualifier_defaults,
    apply_default_time_windows,
    apply_preprocessor_time_hints,
    apply_query_derived_order_hints,
    build_validation_summary,
    inject_original_query_hints,
    promote_filter_time_granularity,
    run_pre_validation_pipeline,
    split_derived_specs,
    validate_regular_items,
)
from mapmover.runtime.postprocess_runtime_support import (
    detect_full_pack_load_clarify_runtime,
    detect_multiple_path_clarify_runtime,
    expand_all_derived_fields_runtime,
    expand_full_pack_loads_runtime,
    expand_wildcard_metrics_runtime,
    validate_postprocess_item_runtime,
)
from mapmover.runtime.postprocess_source_helpers import (
    catalog_sources as catalog_sources_impl,
    get_catalog_source as get_catalog_source_impl,
    get_item_source_metadata as get_item_source_metadata_impl,
    is_full_pack_load as is_full_pack_load_impl,
    metric_display_name as metric_display_name_impl,
    source_has_aggregate_files as source_has_aggregate_files_helper,
    source_requires_metric as source_requires_metric_impl,
    source_supports_aggregate_mode as source_supports_aggregate_mode_helper,
    source_supports_events as source_supports_events_impl,
)
from mapmover.runtime.postprocess_validation import validate_item as validate_item_impl
from mapmover.runtime.source_response_semantics import (
    append_source_caveats,
    collect_metric_caveats,
)
from mapmover.runtime.query_intent_primitives import (
    query_explicit_view_mode as query_explicit_view_mode_impl,
    query_prefers_event_source as query_prefers_event_source_impl,
    query_requests_short_current_window as query_requests_short_current_window_impl,
)
from mapmover.runtime.retry_primitives import (
    reroute_item_to_event_sibling as reroute_item_to_event_sibling_impl,
)
from mapmover.runtime.source_hints import (
    get_query_alias_matches,
    get_routing_hints,
    infer_requested_geo_level_from_query,
    select_query_guided_metric,
)
from mapmover.runtime.warning_policy import DEFAULT_METRIC_WARNING_POLICY
from mapmover.runtime.warning_primitives import build_metric_warning
from mapmover.source_time_contract import metadata_metric_year_range


DERIVED_EXPANSIONS = DEFAULT_DERIVED_EXPANSIONS
POPULATION_FAMILY = "population"
_POPULATION_RESOLUTION_CACHE = {}


def _query_looks_multi_source_comparison(query: str) -> bool:
    query_lower = str(query or "").strip().lower()
    if not query_lower:
        return False
    padded = f" {query_lower} "
    comparison_terms = (
        " compare ",
        " compared ",
        " against ",
        " versus ",
        " vs ",
        " alongside ",
        " correlation ",
        " correlated ",
        " relationship ",
        " related to ",
    )
    return any(term in padded for term in comparison_terms)


def _score_pack_sibling_for_query(query: str, metadata: dict) -> float:
    metric = select_query_guided_metric(query, metadata)
    query_alias_matches = get_query_alias_matches(metadata, query)
    inferred_geo_level = infer_requested_geo_level_from_query(query, metadata)
    if not (metric or query_alias_matches or inferred_geo_level):
        return 0.0

    score = 0.0
    if metric:
        score += 10.0
    if query_alias_matches:
        score += float(len(query_alias_matches) * 2)
    score += float(get_routing_hints(metadata).get("query_priority", 0.0) or 0.0)
    if inferred_geo_level:
        score += 1.0
    return score


def _diversify_same_pack_comparison_items(
    validated_items: list[dict],
    catalog: dict,
    validate_item,
) -> list[dict]:
    if len(validated_items) < 2:
        return validated_items

    query = ""
    for item in validated_items:
        hints = item.get("_hints") or {}
        query = str(hints.get("original_query") or "").strip()
        if query:
            break
    if not _query_looks_multi_source_comparison(query):
        return validated_items

    pack_to_indices: dict[str, list[int]] = {}
    for index, item in enumerate(validated_items):
        if not item.get("_valid"):
            continue
        pack_id = str(item.get("pack_id") or "").strip()
        source_id = str(item.get("source_id") or "").strip()
        if not pack_id or not source_id:
            continue
        pack_to_indices.setdefault(pack_id, []).append(index)

    for pack_id, indices in pack_to_indices.items():
        if len(indices) < 2:
            continue

        sibling_source_ids = [
            str(src.get("source_id") or "").strip()
            for src in catalog_sources_impl(catalog)
            if str(src.get("pack_id") or "").strip() == pack_id
        ]
        sibling_source_ids = [source_id for source_id in sibling_source_ids if source_id]
        if len(sibling_source_ids) < 2:
            continue

        used_sources: set[str] = set()
        for index in indices:
            item = validated_items[index]
            current_source_id = str(item.get("source_id") or "").strip()
            if current_source_id and current_source_id not in used_sources:
                used_sources.add(current_source_id)
                continue

            best_alternative = None
            best_score = 0.0
            for sibling_source_id in sibling_source_ids:
                if sibling_source_id in used_sources:
                    continue
                metadata = load_source_metadata(sibling_source_id) or {}
                if not metadata:
                    continue
                score = _score_pack_sibling_for_query(query, metadata)
                if score > best_score:
                    best_alternative = sibling_source_id
                    best_score = score

            if not best_alternative or best_score <= 0.0:
                continue

            rerouted_item = dict(item)
            rerouted_item["source_id"] = best_alternative
            rerouted_item["_resolved_from_pack"] = True
            rerouted_item["_lock_source_id"] = True
            rerouted_item.pop("metric_label", None)

            metadata = load_source_metadata(best_alternative) or {}
            metrics = metadata.get("metrics") or {}
            metric = str(rerouted_item.get("metric") or "").strip()
            if metric and metric not in metrics:
                rerouted_item.pop("metric", None)

            rerouted_item = validate_item(rerouted_item, catalog)
            if not rerouted_item.get("_valid"):
                continue

            validated_items[index] = rerouted_item
            used_sources.add(best_alternative)

    return validated_items


def run_postprocess_order(
    order: dict,
    hints: dict = None,
    *,
    metric_warning_policy=DEFAULT_METRIC_WARNING_POLICY,
) -> dict:
    catalog = load_catalog()
    items = order.get("items", [])
    original_query = str((hints or {}).get("original_query") or "").strip()
    overlays = load_disaster_overlays_impl(load_reference_json_func=load_reference_json)

    def expand_full_pack_loads(items: list, catalog: dict) -> list:
        return expand_full_pack_loads_runtime(
            items,
            catalog,
            expand_full_pack_loads_func=expand_full_pack_loads_impl,
            is_full_pack_load_func=is_full_pack_load_impl,
            catalog_sources_func=catalog_sources_impl,
            get_catalog_pack_func=lambda catalog, pack_id: get_pack_metadata(pack_id, catalog) if pack_id else None,
            source_supports_events_func=source_supports_events_impl,
            source_has_metrics_func=source_has_metrics_impl,
        )

    def validate_item(item: dict, catalog: dict) -> dict:
        return validate_postprocess_item_runtime(
            item,
            catalog,
            validate_item_func=validate_item_impl,
            resolve_pack_source_func=resolve_pack_source_impl,
            get_catalog_pack_func=lambda catalog, pack_id: get_pack_metadata(pack_id, catalog) if pack_id else None,
            catalog_sources_func=catalog_sources_impl,
            get_catalog_source_func=get_catalog_source_impl,
            normalize_item_filters_func=lambda item, catalog_source: normalize_item_filters_impl(
                item,
                catalog_source,
                load_source_metadata_func=load_source_metadata,
            ),
            normalize_location_shape_metric_func=lambda item, catalog_source: normalize_location_shape_metric_impl(
                item,
                catalog_source,
                source_is_location_shape_func=source_is_location_shape_impl,
            ),
            apply_disaster_semantic_filters_func=lambda item, catalog_source, query: apply_disaster_semantic_filters_impl(
                item,
                catalog_source,
                query,
                overlays=overlays,
                item_disaster_key_func=lambda item, catalog_source: item_disaster_key_impl(
                    item,
                    catalog_source,
                    overlays=overlays,
                    load_source_metadata_func=load_source_metadata,
                ),
                query_semantic_filter_tokens_func=lambda query, disaster_key: query_semantic_filter_tokens_impl(
                    query,
                    disaster_key,
                    overlays=overlays,
                ),
            ),
            source_has_metrics_func=source_has_metrics_impl,
            source_supports_aggregate_mode_func=lambda catalog_source: source_supports_aggregate_mode_helper(
                catalog_source,
                source_supports_aggregate_mode_func=source_supports_aggregate_mode_impl,
                source_has_aggregate_files_func=lambda catalog_source: source_has_aggregate_files_helper(
                    catalog_source,
                    source_has_aggregate_files_func=source_has_aggregate_files_impl,
                    data_root=DATA_ROOT,
                ),
            ),
            apply_aggregate_query_hints_func=apply_aggregate_query_hints_impl,
            source_supports_events_func=source_supports_events_impl,
            query_prefers_event_source_func=query_prefers_event_source_impl,
            query_requests_short_current_window_func=query_requests_short_current_window_impl,
            reroute_item_to_event_sibling_func=reroute_item_to_event_sibling_impl,
            reroute_item_to_aggregate_sibling_func=reroute_item_to_aggregate_sibling_impl,
            resolve_pack_source_by_shape_func=resolve_pack_source_by_shape,
            resolve_pack_aggregate_source_func=resolve_pack_aggregate_source_impl,
            load_source_metadata_func=load_source_metadata,
            expand_filter_value_aliases_func=expand_filter_value_aliases_impl,
            source_requires_metric_func=lambda item, catalog_source: source_requires_metric_impl(
                item,
                catalog_source,
                source_is_location_shape_func=source_is_location_shape_impl,
                source_has_metrics_func=source_has_metrics_impl,
            ),
            get_disaster_aggregate_metric_columns_func=lambda catalog_source: get_disaster_aggregate_metric_columns_impl(
                catalog_source,
                data_root=DATA_ROOT,
                parquet_columns_func=parquet_columns,
            ),
            format_metric_label_func=format_metric_label_impl,
            resolve_pack_source_for_metric_func=resolve_pack_source_for_metric,
            clamp_item_years_to_metric_func=lambda item, metadata, metric_key: clamp_item_years_to_metric_impl(
                item,
                metadata,
                metric_key,
                metadata_metric_year_range_func=metadata_metric_year_range,
            ),
            select_query_guided_metric_func=select_query_guided_metric,
        )

    def expand_wildcard_metrics(items: list) -> list:
        return expand_wildcard_metrics_runtime(
            items,
            expand_wildcard_metrics_func=expand_wildcard_metrics_impl,
            load_catalog_func=load_catalog,
            resolve_pack_source_func=resolve_pack_source_impl,
            load_source_metadata_func=load_source_metadata,
            metadata_metric_year_range_func=metadata_metric_year_range,
        )

    def expand_all_derived_fields(items: list) -> list:
        return expand_all_derived_fields_runtime(
            items,
            expand_all_derived_fields_func=expand_all_derived_fields_impl,
            derived_expansions=DERIVED_EXPANSIONS,
            resolve_population_dependency_func=lambda *, region, preferred_source_id, target_level: resolve_population_dependency_impl(
                region=region,
                preferred_source_id=preferred_source_id,
                target_level=target_level,
                cache_dict=_POPULATION_RESOLUTION_CACHE,
                population_family=POPULATION_FAMILY,
                find_population_metric_key_func=lambda source_id: find_population_metric_key_impl(
                    source_id,
                    load_source_metadata_func=load_source_metadata,
                    population_family=POPULATION_FAMILY,
                ),
                load_source_metadata_func=load_source_metadata,
                get_source_admin_levels_func=get_source_admin_levels_impl,
                scope_matches_population_region_func=scope_matches_population_region_impl,
                load_catalog_func=load_catalog,
            ),
            get_source_admin_levels_func=lambda source_id: get_source_admin_levels_impl(load_source_metadata(source_id) or {}),
            metric_display_name_func=lambda source_id, metric_key: metric_display_name_impl(
                source_id,
                metric_key,
                load_source_metadata_func=load_source_metadata,
            ),
            population_family=POPULATION_FAMILY,
        )

    inject_original_query_hints(items, original_query)
    promote_filter_time_granularity(items)

    time_hints = hints.get("time", {}) if hints else {}
    apply_preprocessor_time_hints(items, time_hints, load_source_metadata)
    apply_default_time_windows(items, load_source_metadata)
    apply_event_qualifier_defaults(items, load_source_metadata, load_reference_json)
    apply_query_derived_order_hints(items, load_source_metadata, hints=hints)

    clarify_message = detect_multiple_path_clarify_runtime(
        items,
        catalog,
        detect_multiple_path_clarify_func=detect_multiple_path_clarify_impl,
        hints=hints,
        query_explicit_view_mode_func=query_explicit_view_mode_impl,
        get_item_source_metadata_func=lambda item, catalog: get_item_source_metadata_impl(
            item,
            catalog,
            resolve_pack_source_func=resolve_pack_source_impl,
            load_source_metadata_func=load_source_metadata,
        ),
        build_multiple_paths_clarify_func=build_multiple_paths_clarify_impl,
    )
    if clarify_message:
        return build_clarify_result(order, items, clarify_message)

    full_pack_clarify = detect_full_pack_load_clarify_runtime(
        items,
        catalog,
        detect_full_pack_load_clarify_func=detect_full_pack_load_clarify_impl,
        is_full_pack_load_func=is_full_pack_load_impl,
        get_catalog_pack_func=lambda catalog, pack_id: get_pack_metadata(pack_id, catalog) if pack_id else None,
        build_pack_load_clarify_func=build_pack_load_clarify_impl,
    )
    if full_pack_clarify:
        return build_clarify_result(order, items, full_pack_clarify)

    expanded_items, metric_count = run_pre_validation_pipeline(
        items,
        hints,
        catalog,
        detect_event_mode_impl,
        normalize_aggregate_metric_mode_impl,
        lambda items, catalog: normalize_order_items_impl(
            items,
            catalog,
            resolve_source_for_item_func=lambda item, catalog: resolve_source_for_item_impl(
                item,
                catalog,
                resolve_pack_source_func=resolve_pack_source_impl,
            ),
            logger=logging.getLogger(__name__),
        ),
        expand_full_pack_loads,
        expand_wildcard_metrics,
        expand_all_derived_fields,
    )
    regular_items, derived_specs = split_derived_specs(expanded_items)
    derived_intent = (hints or {}).get("derived_intent") if hints else None
    if derived_intent:
        for item in regular_items:
            item["_comparison_derived_intent"] = derived_intent
            source_id = item.get("source_id")
            if not source_id:
                continue
            apply_comparison_defaults_impl(
                item,
                load_source_metadata(source_id) or {},
                derived_intent,
            )
    validated_items, errors, valid_count = validate_regular_items(
        regular_items,
        catalog,
        lambda item: normalize_source_declared_scope_impl(
            item,
            load_source_metadata_func=load_source_metadata,
            load_source_reference_func=load_source_reference,
        ),
        validate_item,
    )
    validated_items = _diversify_same_pack_comparison_items(
        validated_items,
        catalog,
        validate_item,
    )
    errors = [item.get("_error", "Unknown error") for item in validated_items if not item.get("_valid")]
    valid_count = sum(1 for item in validated_items if item.get("_valid"))
    if derived_intent:
        for item in validated_items:
            if not item.get("_valid"):
                continue
            source_id = item.get("source_id")
            if not source_id:
                continue
            spec = build_comparison_derived_spec_impl(
                item,
                load_source_metadata(source_id) or {},
            )
            if spec:
                derived_specs.append(spec)
                order["summary"] = spec.get("label") or order.get("summary")
    summary = build_validation_summary(validated_items, errors, valid_count)

    metric_warning = build_metric_warning(metric_count, policy=metric_warning_policy)

    display_summary = rewrite_processed_order_summary_impl(
        order,
        validated_items,
        load_source_metadata_func=load_source_metadata,
    )
    source_caveats = collect_metric_caveats(
        validated_items,
        load_source_metadata_func=load_source_metadata,
    )

    return build_processed_order_result(
        order,
        validated_items=validated_items,
        derived_specs=derived_specs,
        validation_summary=summary,
        all_valid=len(errors) == 0,
        summary=append_source_caveats(display_summary, source_caveats),
        metric_warning=metric_warning,
    )
