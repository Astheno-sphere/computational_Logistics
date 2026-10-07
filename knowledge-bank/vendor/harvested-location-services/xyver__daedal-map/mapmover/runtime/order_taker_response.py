"""Shared response parsing and validation helpers for the order taker."""

from __future__ import annotations

import json

from mapmover.aggregation_system import validate_aggregation_policy
from mapmover.data_loading import load_catalog, load_source_metadata
from mapmover.runtime.order_taker_prompt import get_source_visibility_mode
from mapmover.runtime.order_semantics import (
    source_supports_aggregate_mode as source_supports_aggregate_mode_impl,
)
from mapmover.runtime.population_resolution import get_source_admin_levels
from mapmover.runtime.query_intent_primitives import query_prefers_event_source
from mapmover.runtime.source_hints import (
    get_hint_alias_terms,
    get_metric_alias_matches,
    get_query_alias_matches,
    get_routing_hints,
    get_single_metric_default,
    get_supported_geography_summary,
    get_unsupported_metric_aliases,
    infer_requested_geo_level_from_query,
    select_pack_family_source_for_query as select_pack_family_source_for_query_impl,
    select_query_guided_metric,
)


def _runtime_level_number(runtime_level: str | None) -> int | None:
    text = str(runtime_level or "").strip().lower()
    if text.startswith("admin_") and text[6:].isdigit():
        return int(text[6:])
    if text == "admin_0":
        return 0
    return None


def _source_supports_requested_geo_level(metadata: dict | None, requested_geo_level: str | None) -> bool:
    requested_number = _runtime_level_number(requested_geo_level)
    if requested_number is None or not isinstance(metadata, dict):
        return True

    source_levels = get_source_admin_levels(metadata)
    if not source_levels:
        return True

    return max(source_levels) >= requested_number


def validate_order_item(item: dict) -> dict:
    item.pop("_error", None)
    item.pop("_valid", None)
    _normalize_item_year_fields(item)
    load_scope = str(item.get("load_scope") or "").strip().lower()
    if item.get("pack_id") and (load_scope in {"pack", "all_sources", "full_pack"} or item.get("all_sources") is True):
        item.pop("_error", None)
        item["_valid"] = True
        return item
    source_id = item.get("source_id")
    metric = item.get("metric")
    year = item.get("year")
    user_query = str(((item.get("_hints") or {}).get("original_query")) or item.get("summary") or "").strip()
    pack_id = str(item.get("pack_id") or "").strip()

    if not source_id:
        if item.get("pack_id"):
            source_id = _resolve_source_for_validation(item)
            if source_id:
                item["source_id"] = source_id
                item["_resolved_from_pack"] = True
            else:
                item["_valid"] = False
                item["_error"] = f"Unable to resolve pack_id '{item.get('pack_id')}' to a source"
                return item
        if not source_id:
            item["_valid"] = False
            item["_error"] = "Missing source_id"
            return item

    preferred_metadata = None
    if pack_id and user_query:
        preferred_source_id, preferred_metadata = _select_pack_family_source_for_query(pack_id, user_query)
        if preferred_source_id:
            source_id = preferred_source_id
            item["source_id"] = preferred_source_id

    metadata = preferred_metadata or load_source_metadata(source_id)
    if not metadata:
        item["_valid"] = False
        item["_error"] = f"Unknown source: {source_id}"
        return item
    if get_source_visibility_mode() == "live" and not metadata.get("pack_id"):
        item["_valid"] = False
        item["_error"] = f"Source '{source_id}' is not published in live mode"
        return item

    if user_query:
        inferred_metric_candidates = _select_metadata_guided_metrics(user_query, metadata)
        inferred_metric = inferred_metric_candidates[0] if inferred_metric_candidates else _select_metadata_guided_metric(user_query, metadata)
        if inferred_metric:
            item["metric"] = inferred_metric
            metric = inferred_metric
        inferred_geo_level = infer_requested_geo_level_from_query(user_query, metadata)
        if inferred_geo_level:
            item["geo_level"] = inferred_geo_level

    metrics = metadata.get("metrics", {})
    if metric in ("*", "all", "all_metrics"):
        item["_valid"] = True
        return item
    if metric and metric not in metrics:
        resolved_metric, close_matches = _resolve_metric_for_validation(metric, metrics)
        if resolved_metric:
            item["metric"] = resolved_metric
            metric = resolved_metric
        else:
            if close_matches:
                item["_valid"] = False
                item["_error"] = f"Column '{metric}' not found. Did you mean: {', '.join(close_matches[:3])}?"
            else:
                item["_valid"] = False
                item["_error"] = f"Column '{metric}' not found in {source_id}"
            return item

    temp = metadata.get("temporal_coverage", {})
    start_year = _coerce_year(temp.get("start"))
    end_year = _coerce_year(temp.get("end"))
    if year and start_year and end_year:
        if year < start_year or year > end_year:
            item["_valid"] = False
            item["_error"] = f"Year {year} outside range {start_year}-{end_year}"
            return item

    year_start = item.get("year_start")
    year_end = item.get("year_end")
    if year_start and year_end and start_year and end_year:
        if year_start < start_year:
            item["_valid"] = False
            item["_error"] = f"Year start {year_start} before available data ({start_year})"
            return item
        if year_end > end_year:
            item["_valid"] = False
            item["_error"] = f"Year end {year_end} after available data ({end_year})"
            return item
        if year_start > year_end:
            item["_valid"] = False
            item["_error"] = f"Year start {year_start} is after year end {year_end}"
            return item

    temporal = metadata.get("temporal_coverage", {})
    frequency = str(temporal.get("frequency", "")).lower()
    requested_granularity = str(item.get("time_granularity") or "").strip().lower()
    if frequency in {"annual", "yearly"} and requested_granularity in {"daily", "weekly", "monthly", "annual"}:
        item["_normalized_time_granularity"] = {
            "from": item.get("time_granularity"),
            "to": "yearly",
            "reason": f"source_frequency={frequency}",
        }
        item["time_granularity"] = "yearly"

    metric_info = metrics.get(metric, {}) if metric else {}
    policy_ok, policy_error, policy_trace = validate_aggregation_policy(
        item,
        source_metadata=metadata,
        metric_name=metric,
        metric_info=metric_info,
    )
    item["_aggregation_policy"] = policy_trace
    if not policy_ok:
        item["_valid"] = False
        item["_error"] = policy_error or "Invalid aggregation policy"
        return item

    if metric and not item.get("metric_label"):
        name = metric_info.get("name", metric)
        unit = metric_info.get("unit", "")
        item["metric_label"] = f"{name} ({unit})" if unit and unit != "unknown" else name

    item.pop("_error", None)
    item["_valid"] = True
    return item


def _scope_matches_region_for_validation(scope: str, region) -> bool:
    if not region:
        return scope == "global"
    r = str(region).lower()
    if scope == "CAN":
        return r.startswith("can") or r.startswith("canada")
    if scope == "USA":
        return r.startswith("usa") or r.startswith("us-")
    if scope == "global":
        return True
    return r.startswith(str(scope).lower())


def _item_prefers_geometry_source_for_validation(item: dict) -> bool:
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
        "county", "counties", "district", "districts", "admin_2", "admin2",
        "tract", "tracts", "state", "states", "province", "provinces",
        "top ", "highest", "lowest", "rank", "ranking",
    )
    return any(term in text for term in geometry_terms)


def _resolve_source_for_validation(item: dict) -> str | None:
    pack_id = item.get("pack_id")
    if not pack_id:
        return item.get("source_id")
    catalog = load_catalog() or {}
    sources = catalog.get("sources", [])
    pack_sources = [src for src in sources if src.get("pack_id") == pack_id]
    if not pack_sources:
        return item.get("source_id")

    region = item.get("region")
    if _item_prefers_geometry_source_for_validation(item):
        geometry_sources = [src for src in pack_sources if src.get("geojson_shape") == "geometry_shape"]
        exact_geometry = [
            src for src in geometry_sources
            if src.get("scope") != "global" and _scope_matches_region_for_validation(src.get("scope", "global"), region)
        ]
        if exact_geometry:
            return exact_geometry[0].get("source_id")
        global_geometry = [src for src in geometry_sources if src.get("scope") == "global"]
        if global_geometry:
            return global_geometry[0].get("source_id")

    exact_matches = [
        src for src in pack_sources
        if src.get("scope") != "global" and _scope_matches_region_for_validation(src.get("scope", "global"), region)
    ]
    if exact_matches:
        return exact_matches[0].get("source_id")

    global_matches = [src for src in pack_sources if src.get("scope") == "global"]
    if global_matches:
        return global_matches[0].get("source_id")
    return pack_sources[0].get("source_id")


def _resolve_metric_for_validation(metric: str, metrics: dict) -> tuple[str | None, list[str]]:
    metric_lower = str(metric or "").strip().lower()
    if not metric_lower or not isinstance(metrics, dict):
        return None, []

    exact_match = None
    close_matches = []
    best_keyword_match = None
    best_keyword_score = 0
    metric_words = set(metric_lower.replace("_", " ").replace("-", " ").split())

    for key, value in metrics.items():
        key_lower = str(key).lower()
        if key_lower == metric_lower:
            return key, []
        phrases = [key_lower]
        if isinstance(value, dict):
            name = str(value.get("name") or "").strip().lower()
            if name:
                phrases.append(name)
            keywords = value.get("keywords") or []
            if isinstance(keywords, list):
                phrases.extend(str(keyword).strip().lower() for keyword in keywords if keyword)
        elif value:
            phrases.append(str(value).strip().lower())

        for phrase in phrases:
            if not phrase:
                continue
            if phrase == metric_lower:
                exact_match = key
                break
            if metric_lower in phrase or phrase in metric_lower:
                close_matches.append(key)
                phrase_words = set(phrase.replace("_", " ").replace("-", " ").split())
                score = len(metric_words & phrase_words) + 2
                if score > best_keyword_score:
                    best_keyword_match = key
                    best_keyword_score = score
            else:
                phrase_words = set(phrase.replace("_", " ").replace("-", " ").split())
                score = len(metric_words & phrase_words)
                if score > best_keyword_score:
                    best_keyword_match = key
                    best_keyword_score = score
        if exact_match:
            break

    if exact_match:
        return exact_match, []
    deduped = list(dict.fromkeys(close_matches))
    if best_keyword_match and best_keyword_score > 0:
        return best_keyword_match, deduped
    return None, deduped


def validate_order(order: dict) -> dict:
    items = order.get("items", [])
    expanded_items = []
    for item in items:
        if not isinstance(item, dict):
            expanded_items.append(item)
            continue
        metric_value = item.get("metric")
        if isinstance(metric_value, list):
            metric_candidates = [str(metric).strip() for metric in metric_value if str(metric).strip()]
            if not metric_candidates:
                expanded_items.append(item)
                continue
            for metric_name in metric_candidates:
                next_item = dict(item)
                next_item["metric"] = metric_name
                expanded_items.append(next_item)
            continue
        expanded_items.append(item)

    validated_items = []
    all_valid = True
    for item in expanded_items:
        validated = validate_order_item(item)
        validated_items.append(validated)
        if not validated.get("_valid", False):
            all_valid = False
    order["items"] = validated_items
    order["_all_valid"] = all_valid
    return order


def _coerce_year(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
        return None


def _coerce_date_year(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return _coerce_year(value)
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _normalize_item_year_fields(item: dict) -> None:
    year = _coerce_year(item.get("year"))
    year_start = _coerce_year(item.get("year_start"))
    year_end = _coerce_year(item.get("year_end"))
    date_start_year = _coerce_date_year(item.get("date_start"))
    date_end_year = _coerce_date_year(item.get("date_end"))
    if year_start is None and date_start_year is not None:
        year_start = date_start_year
    if year_end is None and date_end_year is not None:
        year_end = date_end_year
    if year is None and year_start is not None and year_end is not None and year_start == year_end:
        year = year_start
    if year is not None:
        item["year"] = year
    if year_start is not None:
        item["year_start"] = year_start
    if year_end is not None:
        item["year_end"] = year_end


def _matches_unsupported_metric_alias(user_query: str, metadata: dict) -> bool:
    query_lower = str(user_query or "").strip().lower()
    if not query_lower or not isinstance(metadata, dict):
        return False
    aliases = get_unsupported_metric_aliases(metadata)
    for alias in aliases:
        alias_text = str(alias or "").strip().lower()
        if alias_text and alias_text in query_lower:
            return True
    return False


def _summarize_supported_geography(metadata: dict) -> str:
    return get_supported_geography_summary(metadata)


def _build_metadata_unsupported_metric_clarify(user_query: str, metadata: dict) -> dict:
    source_name = metadata.get("source_name") or metadata.get("source_id") or "this source"
    metrics = metadata.get("metrics") or {}
    metric_names = []
    for info in metrics.values():
        if not isinstance(info, dict):
            continue
        name = str(info.get("name") or "").strip()
        if name:
            metric_names.append(name)
    metric_names = list(dict.fromkeys(metric_names))
    metric_lines = metric_names[:6]
    geo_summary = _summarize_supported_geography(metadata)

    unsupported_label = "that metric"
    aliases = get_unsupported_metric_aliases(metadata)
    query_lower = str(user_query or "").strip().lower()
    for alias in aliases:
        alias_text = str(alias or "").strip()
        if alias_text and alias_text.lower() in query_lower:
            normalized = alias_text
            if " " not in alias_text and alias_text.isalpha() and len(alias_text) <= 5:
                normalized = alias_text.upper()
            unsupported_label = normalized
            break

    lines = [f"{source_name} does not include {unsupported_label}. It is not currently available in this pack."]
    if metric_lines:
        lines.append("Available metrics for this source include:")
        lines.extend(f"- {name}" for name in metric_lines)
    lines.append(f"This source supports {geo_summary}.")
    lines.append("Which of the available metrics would you like instead?")
    return {"type": "clarify", "message": "\n\n".join([lines[0], "\n".join(lines[1:])])}


def _query_looks_multi_source_comparison(user_query: str) -> bool:
    query_lower = str(user_query or "").strip().lower()
    if not query_lower:
        return False
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
    padded = f" {query_lower} "
    return any(term in padded for term in comparison_terms)


def _query_looks_same_source_comparison(user_query: str) -> bool:
    query_lower = str(user_query or "").strip().lower()
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
        " more ",
        " less ",
        " than ",
    )
    return any(term in padded for term in comparison_terms)


def _query_looks_dual_metric_screen(user_query: str) -> bool:
    query_lower = str(user_query or "").strip().lower()
    if not query_lower:
        return False
    padded = f" {query_lower} "
    has_conjunction = " and " in padded
    high_low_terms = (
        (" high ", " low "),
        (" highest ", " lowest "),
        (" more ", " less "),
    )
    return has_conjunction and any(left in padded and right in padded for left, right in high_low_terms)


def _distinct_candidate_pack_count(hints: dict | None) -> int:
    candidates = (((hints or {}).get("candidates") or {}).get("sources") or {}).get("candidates") or []
    packs: set[str] = set()
    for candidate in candidates[:5]:
        try:
            confidence = float(candidate.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.35:
            continue
        pack_id = str(candidate.get("pack_id") or candidate.get("source_id") or "").strip()
        if pack_id:
            packs.add(pack_id)
    return len(packs)


def _candidate_pack_count_for_guided_sources(user_query: str, hints: dict | None) -> int:
    packs: set[str] = set()
    for source_id in _iter_candidate_source_ids(hints):
        metadata = load_source_metadata(source_id) or {}
        if not metadata:
            continue
        metrics = _select_metadata_guided_metrics(user_query, metadata)
        metric = metrics[0] if metrics else _select_metadata_guided_metric(user_query, metadata)
        is_event_like = str(metadata.get("data_type") or "").strip().lower() == "events" or bool(metadata.get("significance_column"))
        if metric or is_event_like:
            pack_id = str(metadata.get("pack_id") or source_id).strip()
            if pack_id:
                packs.add(pack_id)
    return len(packs)


def _select_metadata_guided_metric(user_query: str, metadata: dict) -> str:
    return select_query_guided_metric(user_query, metadata)


def _select_metadata_guided_metrics(user_query: str, metadata: dict) -> list[str]:
    routing_hints = get_routing_hints(metadata)
    query_lower = str(user_query or "").strip().lower()
    pair_aliases = routing_hints.get("metric_pair_aliases") or []
    if isinstance(pair_aliases, list) and query_lower:
        for pair in pair_aliases:
            if not isinstance(pair, dict):
                continue
            aliases = pair.get("aliases") or []
            metrics_for_pair = pair.get("metrics") or []
            if not isinstance(aliases, list) or not isinstance(metrics_for_pair, list):
                continue
            alias_terms = [str(alias or "").strip().lower() for alias in aliases if str(alias or "").strip()]
            if not alias_terms or not all(alias in query_lower for alias in alias_terms):
                continue
            metrics = []
            for metric_name in metrics_for_pair:
                metric_text = str(metric_name or "").strip()
                if metric_text and metric_text not in metrics:
                    metrics.append(metric_text)
            if metrics:
                return metrics

    alias_matches = get_metric_alias_matches(metadata, user_query)
    metrics: list[str] = []
    for _, metric_name in alias_matches:
        metric_text = str(metric_name or "").strip()
        if metric_text and metric_text not in metrics:
            metrics.append(metric_text)
    return metrics


def _iter_candidate_source_ids(hints: dict | None) -> list[str]:
    if not hints or not isinstance(hints, dict):
        return []
    source_ids: list[str] = []

    detected_source = hints.get("detected_source") or {}
    detected_source_id = str(detected_source.get("source_id") or "").strip()
    if detected_source_id:
        source_ids.append(detected_source_id)

    candidates = (((hints.get("candidates") or {}).get("sources") or {}).get("candidates") or [])
    for candidate in candidates[:8]:
        source_id = str((candidate or {}).get("source_id") or "").strip()
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids


def _iter_pack_family_source_ids(hints: dict | None) -> list[str]:
    if not hints or not isinstance(hints, dict):
        return []
    detected_source = hints.get("detected_source") or {}
    pack_id = str(detected_source.get("pack_id") or "").strip()
    if not pack_id:
        return []
    catalog = load_catalog() or {}
    source_ids: list[str] = []
    for src in catalog.get("sources", []):
        if str(src.get("pack_id") or "").strip() != pack_id:
            continue
        source_id = str(src.get("source_id") or "").strip()
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids


def _query_requests_over_time_analysis(hints: dict | None) -> bool:
    if not isinstance(hints, dict):
        return False
    time_hints = hints.get("time") or {}
    if not isinstance(time_hints, dict):
        return False

    if time_hints.get("is_time_series"):
        return True

    pattern_type = str(time_hints.get("pattern_type") or "").strip().lower()
    if pattern_type in {"trend", "historical"}:
        return True

    year_start = time_hints.get("year_start")
    year_end = time_hints.get("year_end")
    return bool(year_start and year_end and year_start != year_end)


def _score_metadata_guided_source(query: str, metadata: dict) -> tuple[float, str]:
    metric = _select_metadata_guided_metric(query, metadata)
    query_alias_matches = get_query_alias_matches(metadata, query)
    inferred_geo_level = infer_requested_geo_level_from_query(query, metadata)
    if inferred_geo_level and not _source_supports_requested_geo_level(metadata, inferred_geo_level):
        return 0.0, ""
    if not (metric or query_alias_matches or inferred_geo_level):
        return 0.0, ""

    score = 0.0
    if metric:
        score += 10.0
    if query_alias_matches:
        score += float(len(query_alias_matches) * 2)
    score += float(get_routing_hints(metadata).get("query_priority", 0.0) or 0.0)
    if inferred_geo_level:
        score += 1.0
    return score, metric


def _build_metadata_guided_pack_aggregate_order(user_query: str, hints: dict | None) -> dict | None:
    if not user_query or not isinstance(hints, dict):
        return None
    if not _query_requests_over_time_analysis(hints):
        return None

    detected_source = hints.get("detected_source") or {}
    pack_id = str(detected_source.get("pack_id") or "").strip()
    if not pack_id:
        return None

    catalog = load_catalog() or {}
    pack_sources = [
        src for src in (catalog.get("sources") or [])
        if str(src.get("pack_id") or "").strip() == pack_id
    ]
    if not pack_sources:
        return None

    best_source = None
    best_metadata = None
    best_metric = ""
    best_score = 0.0
    for src in pack_sources:
        if not source_supports_aggregate_mode_impl(src):
            continue
        source_id = str(src.get("source_id") or "").strip()
        if not source_id:
            continue
        metadata = load_source_metadata(source_id) or {}
        if not metadata:
            continue
        score, metric = _score_metadata_guided_source(user_query, metadata)
        if score <= 0.0:
            continue
        if score > best_score:
            best_source = src
            best_metadata = metadata
            best_metric = metric
            best_score = score

    if not best_source or not best_metadata or not best_metric:
        return None

    region = _preferred_region_from_hints(hints)
    time_hints = hints.get("time") or {}
    year_start = time_hints.get("year_start")
    year_end = time_hints.get("year_end")
    inferred_geo_level = infer_requested_geo_level_from_query(user_query, best_metadata)

    item = {
        "source_id": str(best_source.get("source_id") or "").strip(),
        "pack_id": pack_id,
        "_hints": {"original_query": user_query},
        "metric": best_metric,
    }
    if inferred_geo_level:
        item["geo_level"] = inferred_geo_level
    if region:
        item["region"] = region
    if year_start and year_end:
        item["year_start"] = year_start
        item["year_end"] = year_end
    elif year_start:
        item["year"] = year_start

    metric_info = (best_metadata.get("metrics") or {}).get(best_metric) or {}
    metric_name = str(metric_info.get("name") or best_metric).strip()
    source_name = str(best_metadata.get("source_name") or item["source_id"]).strip()
    summary = f"{metric_name} from {source_name}"
    if item.get("year_start") and item.get("year_end"):
        summary += f", {item['year_start']}-{item['year_end']}"
    elif item.get("year"):
        summary += f" for {item['year']}"
    if item.get("region"):
        summary += f" in {item['region']}"

    return {
        "type": "order",
        "order": {
            "summary": summary,
            "items": [item],
        },
        "summary": summary,
    }


def _select_metadata_guided_source(user_query: str, hints: dict | None) -> tuple[str, dict] | tuple[None, None]:
    best_source_id = None
    best_metadata = None
    best_score = 0.0

    candidate_source_ids = _iter_candidate_source_ids(hints)
    for source_id in _iter_pack_family_source_ids(hints):
        if source_id not in candidate_source_ids:
            candidate_source_ids.append(source_id)

    for source_id in candidate_source_ids:
        metadata = load_source_metadata(source_id) or {}
        if not metadata:
            continue

        inferred_geo_level = infer_requested_geo_level_from_query(user_query, metadata)
        if inferred_geo_level and not _source_supports_requested_geo_level(metadata, inferred_geo_level):
            continue

        alias_matches = _select_metadata_guided_metrics(user_query, metadata)
        query_alias_matches = get_query_alias_matches(metadata, user_query)
        score = float(len(alias_matches) * 10)
        if alias_matches:
            score += get_routing_hints(metadata).get("query_priority", 0.0) or 0.0
        else:
            default_metric = _select_metadata_guided_metric(user_query, metadata)
            if default_metric:
                score += 1.0 + float(get_routing_hints(metadata).get("query_priority", 0.0) or 0.0)
        if query_alias_matches:
            score += float(len(query_alias_matches) * 2)

        if score > best_score:
            best_source_id = source_id
            best_metadata = metadata
            best_score = score

    if best_source_id and best_metadata and best_score > 0:
        return best_source_id, best_metadata
    return None, None


def _preferred_region_from_hints(hints: dict | None) -> str:
    if not hints or not isinstance(hints, dict):
        return ""
    query_constraints = hints.get("query_constraints") or {}
    region_loc_id = str(query_constraints.get("region_loc_id") or "").strip()
    if region_loc_id:
        return region_loc_id
    location = hints.get("location") or {}
    loc_id = str(location.get("loc_id") or "").strip()
    if loc_id:
        return loc_id
    return str(location.get("iso3") or "").strip()


def _select_pack_family_source_for_query(pack_id: str, user_query: str) -> tuple[str | None, dict | None]:
    if not pack_id or not user_query:
        return None, None
    best_source_id, best_metadata, _ = select_pack_family_source_for_query_impl(
        pack_id,
        user_query,
        catalog=load_catalog() or {},
        load_source_metadata_func=load_source_metadata,
    )
    if best_source_id and best_metadata:
        return best_source_id, best_metadata
    return None, None


def _is_event_like_source(metadata: dict | None) -> bool:
    if not isinstance(metadata, dict):
        return False
    data_type = str(metadata.get("data_type") or "").strip().lower()
    return data_type == "events" or bool(metadata.get("significance_column"))


def _build_metadata_guided_two_source_order(user_query: str, hints: dict | None) -> dict | None:
    if not hints or not isinstance(hints, dict):
        return None
    if _candidate_pack_count_for_guided_sources(user_query, hints) > 2:
        return None

    region = _preferred_region_from_hints(hints)
    time_hints = hints.get("time") or {}
    year_start = time_hints.get("year_start")
    year_end = time_hints.get("year_end")

    scored_candidates: list[tuple[float, str, dict, str]] = []
    for source_id in _iter_candidate_source_ids(hints):
        metadata = load_source_metadata(source_id) or {}
        if not metadata:
            continue
        metrics = _select_metadata_guided_metrics(user_query, metadata)
        metric = metrics[0] if metrics else _select_metadata_guided_metric(user_query, metadata)
        if not metric and not _is_event_like_source(metadata):
            continue
        score = float(len(metrics) * 10)
        if metric:
            score += float(get_routing_hints(metadata).get("query_priority", 0.0) or 0.0)
        else:
            score += 0.5 + float(get_routing_hints(metadata).get("query_priority", 0.0) or 0.0)
        scored_candidates.append((score, source_id, metadata, metric))

    if len(scored_candidates) < 2:
        return None

    items: list[dict] = []
    summaries: list[str] = []
    used_sources: set[str] = set()
    for _, source_id, metadata, metric in sorted(scored_candidates, key=lambda item: item[0], reverse=True):
        pack_id = str(metadata.get("pack_id") or source_id).strip()
        if source_id in used_sources:
            continue
        item = {
            "source_id": source_id,
            "pack_id": pack_id,
            "_hints": {"original_query": user_query},
        }
        inferred_geo_level = infer_requested_geo_level_from_query(user_query, metadata)
        if inferred_geo_level:
            item["geo_level"] = inferred_geo_level
        if metric:
            item["metric"] = metric
        if region:
            item["region"] = region
        if year_start and year_end:
            item["year_start"] = year_start
            item["year_end"] = year_end
        elif year_start:
            item["year"] = year_start
        items.append(item)

        metric_info = (metadata.get("metrics") or {}).get(metric) or {}
        label = str(metric_info.get("name") or metric or metadata.get("source_name") or source_id).strip()
        summaries.append(label)
        used_sources.add(source_id)
        if len(items) >= 2:
            break

    if len(items) < 2:
        return None

    summary = " vs ".join(summaries[:2])
    if year_start and year_end:
        summary += f", {year_start}-{year_end}"
    elif year_start:
        summary += f" for {year_start}"
    if region:
        summary += f" in {region}"

    return {
        "type": "order",
        "order": {
            "summary": summary,
            "items": items,
        },
        "summary": summary,
    }


def _build_metadata_guided_order(user_query: str, hints: dict | None) -> dict | None:
    if not hints or not isinstance(hints, dict):
        return None

    if _query_looks_multi_source_comparison(user_query):
        if _distinct_candidate_pack_count(hints) > 2:
            return None
        two_source_order = _build_metadata_guided_two_source_order(user_query, hints)
        if two_source_order is not None:
            return two_source_order

    detected_source = hints.get("detected_source") or {}
    source_id = str(detected_source.get("source_id") or "").strip()
    metadata = load_source_metadata(source_id) or {} if source_id else {}
    inferred_geo_level = infer_requested_geo_level_from_query(user_query, metadata) if metadata else None
    if source_id and metadata and inferred_geo_level and not _source_supports_requested_geo_level(metadata, inferred_geo_level):
        source_id = ""
        metadata = {}
    selected_source_id, selected_metadata = _select_metadata_guided_source(user_query, hints)
    if not source_id or not metadata:
        source_id, metadata = selected_source_id, selected_metadata
    if not source_id or not metadata:
        return None

    routing_hints = get_routing_hints(metadata)
    wants_event_view = query_prefers_event_source(user_query)
    supports_view_mode_clarify = "view_mode" in (routing_hints.get("clarify_path_dimensions") or [])

    metrics = _select_metadata_guided_metrics(user_query, metadata)
    metric = metrics[0] if metrics else _select_metadata_guided_metric(user_query, metadata)
    if not metric:
        default_metric = get_single_metric_default(metadata)
        if default_metric and not wants_event_view:
            metric = default_metric
    if (
        (not metric and not wants_event_view)
        and selected_source_id
        and selected_metadata
        and selected_source_id != source_id
    ):
        selected_metrics = _select_metadata_guided_metrics(user_query, selected_metadata)
        selected_metric = selected_metrics[0] if selected_metrics else _select_metadata_guided_metric(user_query, selected_metadata)
        if not selected_metric:
            default_metric = get_single_metric_default(selected_metadata)
            if default_metric:
                selected_metric = default_metric
        if selected_metric:
            source_id = selected_source_id
            metadata = selected_metadata
            routing_hints = get_routing_hints(metadata)
            supports_view_mode_clarify = "view_mode" in (routing_hints.get("clarify_path_dimensions") or [])
            metrics = selected_metrics
            metric = selected_metric
            inferred_geo_level = infer_requested_geo_level_from_query(user_query, metadata)
    if not metric and not (wants_event_view and supports_view_mode_clarify):
        return None

    region = _preferred_region_from_hints(hints)

    time_hints = hints.get("time") or {}
    year_start = time_hints.get("year_start")
    year_end = time_hints.get("year_end")

    def build_item(metric_name: str) -> dict:
        item = {
            "source_id": source_id,
            "pack_id": str(metadata.get("pack_id") or detected_source.get("pack_id") or "").strip(),
            "_hints": {"original_query": user_query},
        }
        if inferred_geo_level:
            item["geo_level"] = inferred_geo_level
        if metric_name:
            item["metric"] = metric_name
        if region:
            item["region"] = region
        if year_start and year_end:
            item["year_start"] = year_start
            item["year_end"] = year_end
        elif year_start:
            item["year"] = year_start
        return item

    items = [build_item(metric)]
    if (_query_looks_same_source_comparison(user_query) or _query_looks_dual_metric_screen(user_query)) and len(metrics) >= 2:
        items = [build_item(metric_name) for metric_name in metrics[:2]]

    source_name = str(metadata.get("source_name") or source_id).strip()
    metric_names = []
    for item in items:
        metric_key = str(item.get("metric") or "").strip()
        metric_info = (metadata.get("metrics") or {}).get(metric_key) or {}
        metric_names.append(str(metric_info.get("name") or metric_key or source_name).strip())
    metric_summary = " vs ".join(metric_names)
    summary = f"{metric_summary} from {source_name}"
    if items[0].get("year_start") and items[0].get("year_end"):
        summary += f", {items[0]['year_start']}-{items[0]['year_end']}"
    elif items[0].get("year"):
        summary += f" for {items[0]['year']}"
    if items[0].get("region"):
        summary += f" in {items[0]['region']}"

    return {
        "type": "order",
        "order": {
            "summary": summary,
            "items": items,
        },
        "summary": summary,
    }


def _build_query_override_order(user_query: str, items: list[dict]) -> dict | None:
    if not user_query or not items:
        return None
    first_item = next((item for item in items if isinstance(item, dict)), None)
    if not first_item:
        return None

    source_id = str(first_item.get("source_id") or "").strip()
    pack_id = str(first_item.get("pack_id") or "").strip()
    region = first_item.get("region")
    year = first_item.get("year")
    year_start = first_item.get("year_start")
    year_end = first_item.get("year_end")

    metadata = None
    if pack_id:
        source_id, metadata = _select_pack_family_source_for_query(pack_id, user_query)
    if (not source_id or not metadata) and first_item.get("source_id"):
        source_id = str(first_item.get("source_id") or "").strip()
        metadata = load_source_metadata(source_id) or {}
    if not source_id or not metadata:
        return None

    metrics = _select_metadata_guided_metrics(user_query, metadata)
    metric = metrics[0] if metrics else _select_metadata_guided_metric(user_query, metadata)
    inferred_geo_level = infer_requested_geo_level_from_query(user_query, metadata)
    if not metric and not inferred_geo_level:
        return None

    def build_item(metric_name: str | None) -> dict:
        item = {
            "source_id": source_id,
            "pack_id": str(metadata.get("pack_id") or pack_id or "").strip(),
            "_hints": {"original_query": user_query},
        }
        if metric_name:
            item["metric"] = metric_name
        if inferred_geo_level:
            item["geo_level"] = inferred_geo_level
        if region:
            item["region"] = region
        if year_start and year_end:
            item["year_start"] = year_start
            item["year_end"] = year_end
        elif year:
            item["year"] = year
        return item

    order_items = [build_item(metric)]
    if (_query_looks_same_source_comparison(user_query) or _query_looks_dual_metric_screen(user_query)) and len(metrics) >= 2:
        order_items = [build_item(metric_name) for metric_name in metrics[:2]]

    summary = str(first_item.get("summary") or "").strip() or str(user_query).strip()
    return {
        "type": "order",
        "order": {
            "summary": summary,
            "items": order_items,
        },
        "summary": summary,
    }


def _apply_metadata_guided_response_normalization(result: dict, *, user_query: str, hints: dict | None) -> dict:
    if not isinstance(result, dict) or result.get("type") not in {"chat", "clarify"}:
        return result
    if not hints or not isinstance(hints, dict):
        return result
    aggregate_guided_order = _build_metadata_guided_pack_aggregate_order(user_query, hints)
    if aggregate_guided_order is not None:
        return aggregate_guided_order
    items = (((result.get("order") or {}) if isinstance(result.get("order"), dict) else {}).get("items") or [])
    source_id, metadata = _select_metadata_guided_source(user_query, hints)
    if not source_id or not metadata:
        detected_source = hints.get("detected_source") or {}
        source_id = detected_source.get("source_id")
        metadata = load_source_metadata(source_id) or {} if source_id else {}
    if not source_id or not metadata:
        return result
    if _matches_unsupported_metric_alias(user_query, metadata):
        return _build_metadata_unsupported_metric_clarify(user_query, metadata)
    guided_order = _build_metadata_guided_order(user_query, hints)
    if guided_order is None:
        guided_order = _build_query_override_order(user_query, items)
    if guided_order is not None:
        return guided_order
    return result


def _apply_metadata_guided_order_normalization(result: dict, *, user_query: str, hints: dict | None) -> dict:
    if not isinstance(result, dict) or result.get("type") != "order":
        return result
    if not hints or not isinstance(hints, dict):
        return result

    order = result.get("order") or {}
    items = order.get("items") or []
    selected_source_id, selected_metadata = _select_metadata_guided_source(user_query, hints)
    guided_order = _build_metadata_guided_order(user_query, hints)
    guided_items = ((guided_order.get("order") or {}).get("items") or []) if isinstance(guided_order, dict) else []

    updated_items = []
    enriched_items = False
    inferred_levels_present = False
    should_override_single_metric = len([item for item in items if isinstance(item, dict)]) == 1
    for item in items:
        if not isinstance(item, dict):
            updated_items.append(item)
            continue
        source_id = str(item.get("source_id") or "").strip()
        metadata = selected_metadata if source_id and source_id == selected_source_id else (load_source_metadata(source_id) or {} if source_id else {})
        inferred_geo_level = infer_requested_geo_level_from_query(user_query, metadata)
        current_geo_level = str(item.get("geo_level") or "").strip()
        guided_metric = _select_metadata_guided_metric(user_query, metadata) if should_override_single_metric else ""
        current_metric = str(item.get("metric") or "").strip()

        if (
            guided_metric
            and current_metric
            and guided_metric != current_metric
        ) or (inferred_geo_level and inferred_geo_level != current_geo_level):
            updated_item = dict(item)
            if guided_metric and current_metric and guided_metric != current_metric:
                updated_item["metric"] = guided_metric
            if inferred_geo_level and inferred_geo_level != current_geo_level:
                updated_item["geo_level"] = inferred_geo_level
            updated_items.append(updated_item)
            enriched_items = True
            inferred_levels_present = True
            continue
        if inferred_geo_level:
            inferred_levels_present = True
        updated_items.append(item)

    if enriched_items:
        order["items"] = updated_items
        result["order"] = order
        items = updated_items

    source_ids = {str(item.get("source_id") or "").strip() for item in items if isinstance(item, dict) and item.get("source_id")}
    current_metrics = [str(item.get("metric") or "").strip() for item in items if isinstance(item, dict) and item.get("metric")]
    guided_sources = {str(item.get("source_id") or "").strip() for item in guided_items if isinstance(item, dict) and item.get("source_id")}
    guided_metrics = [str(item.get("metric") or "").strip() for item in guided_items if isinstance(item, dict) and item.get("metric")]
    guided_geo_levels = [str(item.get("geo_level") or "").strip() for item in guided_items if isinstance(item, dict) and item.get("geo_level")]
    guided_metric_matches = get_metric_alias_matches(selected_metadata, user_query) if isinstance(selected_metadata, dict) else []

    should_prefer_guided = False
    if guided_items:
        if selected_source_id and source_ids and selected_source_id not in source_ids:
            should_prefer_guided = True
        elif guided_sources and guided_sources != source_ids:
            should_prefer_guided = True
        elif guided_metrics and guided_metrics != current_metrics:
            should_prefer_guided = True
        elif inferred_levels_present and guided_geo_levels:
            current_geo_levels = [str(item.get("geo_level") or "").strip() for item in items if isinstance(item, dict)]
            if guided_geo_levels != current_geo_levels:
                should_prefer_guided = True
        elif guided_metric_matches:
            should_prefer_guided = True

    if should_prefer_guided and guided_order and guided_order.get("type") == "order":
        return guided_order

    should_upgrade = False
    if _query_looks_dual_metric_screen(user_query) and len(source_ids) < 2:
        should_upgrade = True
    elif _query_looks_multi_source_comparison(user_query) and len(source_ids) < 2:
        should_upgrade = True

    if not should_upgrade:
        return result

    if not guided_order or guided_order.get("type") != "order":
        return result

    guided_items = ((guided_order.get("order") or {}).get("items") or [])
    if len(guided_items) <= len(items):
        return result
    return guided_order


def parse_llm_response(content: str, hints: dict = None, user_query: str = "") -> dict:
    parsed_json = None
    if "```json" in content:
        try:
            json_str = content.split("```json")[1].split("```")[0].strip()
            parsed_json = json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            pass
    elif content.strip().startswith("{"):
        try:
            parsed_json = json.loads(content.strip())
        except json.JSONDecodeError:
            pass

    if parsed_json and isinstance(parsed_json, dict):
        response_type = parsed_json.get("type", "order")
        if response_type == "navigate":
            return {
                "type": "navigate",
                "locations": parsed_json.get("locations", []),
                "message": parsed_json.get("message", "Navigating to location"),
            }
        if response_type == "geometry_remove":
            return {
                "type": "geometry_remove",
                "regions": parsed_json.get("regions", []),
                "geometry_type": parsed_json.get("geometry_type", "zcta"),
                "message": parsed_json.get("message", "Removing geometry"),
            }
        if response_type == "disambiguate":
            return {
                "type": "disambiguate",
                "options": parsed_json.get("options", []),
                "message": parsed_json.get("message", "Multiple locations found"),
                "query_term": parsed_json.get("query_term", "location"),
            }
        if response_type == "filter_update":
            return {
                "type": "filter_update",
                "overlay": parsed_json.get("overlay", ""),
                "filters": parsed_json.get("filters", {}),
                "message": parsed_json.get("message", "Updating filters"),
            }
        if response_type == "overlay_toggle":
            return {
                "type": "overlay_toggle",
                "overlay": parsed_json.get("overlay", ""),
                "enabled": parsed_json.get("enabled", True),
                "message": parsed_json.get("message", ""),
            }
        if response_type == "chat":
            result = {"type": "chat", "message": parsed_json.get("message", "")}
            return _apply_metadata_guided_response_normalization(result, user_query=user_query, hints=hints)
        if response_type == "clarify":
            result = {"type": "clarify", "message": parsed_json.get("message", "Could you provide more details?")}
            return _apply_metadata_guided_response_normalization(result, user_query=user_query, hints=hints)
        order = validate_order(parsed_json)
        result = {
            "type": "order",
            "order": order,
            "summary": order.get("summary", "Data request"),
        }
        return _apply_metadata_guided_order_normalization(result, user_query=user_query, hints=hints)

    if "?" in content and len(content) < 200:
        result = {"type": "clarify", "message": content}
        return _apply_metadata_guided_response_normalization(result, user_query=user_query, hints=hints)
    result = {"type": "chat", "message": content}
    return _apply_metadata_guided_response_normalization(result, user_query=user_query, hints=hints)
