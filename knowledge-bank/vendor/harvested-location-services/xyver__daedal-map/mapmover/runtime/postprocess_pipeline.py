"""Shared pre-validation postprocess pipeline helpers."""

import re

from .loc_id_resolution import resolve_admin_text_to_loc_id
from .query_constraint_primitives import extract_query_constraints


EVENT_QUALIFIER_SINGLE_TARGET_PATTERNS = (
    re.compile(r"\bthe\s+biggest\s+(?P<noun>[a-z_]+)\b"),
    re.compile(r"\bthe\s+largest\s+(?P<noun>[a-z_]+)\b"),
    re.compile(r"\bthe\s+smallest\s+(?P<noun>[a-z_]+)\b"),
    re.compile(r"\bthe\s+strongest\s+(?P<noun>[a-z_]+)\b"),
    re.compile(r"\bthe\s+highest\s+(?P<noun>[a-z_]+)\b"),
    re.compile(r"\bthe\s+lowest\s+(?P<noun>[a-z_]+)\b"),
    re.compile(r"\bthe\s+most\s+severe\s+(?P<noun>[a-z_]+)\b"),
    re.compile(r"\bthe\s+least\s+severe\s+(?P<noun>[a-z_]+)\b"),
)


def _query_requests_single_ranked_event(query_text: str) -> bool:
    normalized = str(query_text or "").strip().lower()
    if not normalized:
        return False
    for pattern in EVENT_QUALIFIER_SINGLE_TARGET_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        noun = str(match.group("noun") or "").strip().lower()
        if noun and not noun.endswith("s"):
            return True
    return False


def promote_filter_time_granularity(items: list) -> None:
    """Lift legacy filter-scoped time_granularity onto the item itself."""
    for item in items:
        if not isinstance(item, dict) or item.get("time_granularity"):
            continue
        filters = item.get("filters")
        if not isinstance(filters, dict):
            continue
        granularity = str(filters.get("time_granularity") or "").strip().lower()
        if not granularity:
            continue
        item["time_granularity"] = granularity
        next_filters = dict(filters)
        next_filters.pop("time_granularity", None)
        if next_filters:
            item["filters"] = next_filters
        else:
            item.pop("filters", None)


def _coerce_coverage_year(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def inject_original_query_hints(items: list, original_query: str) -> None:
    """Copy the original query into item-level hints when the LLM omitted it."""
    if not original_query:
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        item_hints = item.get("_hints") if isinstance(item.get("_hints"), dict) else {}
        if not item_hints.get("original_query"):
            item_hints["original_query"] = original_query
            item["_hints"] = item_hints


def apply_preprocessor_time_hints(
    items: list,
    time_hints: dict,
    load_source_metadata,
) -> None:
    """Apply preprocessor-derived time ranges when the LLM left years blank."""
    hinted_granularity = str(time_hints.get("time_granularity") or "").strip().lower()
    if not time_hints.get("is_time_series"):
        for item in items:
            if (
                isinstance(item, dict)
                and hinted_granularity
                and not item.get("time_granularity")
            ):
                item["time_granularity"] = hinted_granularity
        return
    for item in items:
        if hinted_granularity and not item.get("time_granularity"):
            item["time_granularity"] = hinted_granularity
        if item.get("year") is None and not item.get("year_start") and not item.get("year_end"):
            if time_hints.get("year_start") and time_hints.get("year_end"):
                item["year_start"] = time_hints["year_start"]
                item["year_end"] = time_hints["year_end"]
            elif time_hints.get("pattern_type") == "trend" and item.get("source_id"):
                metadata = load_source_metadata(item["source_id"])
                if metadata:
                    temp = metadata.get("temporal_coverage", {})
                    if temp.get("start") and temp.get("end"):
                        item["year_start"] = temp["start"]
                        item["year_end"] = temp["end"]


def apply_default_time_windows(
    items: list,
    load_source_metadata,
    *,
    default_year_span: int = 10,
) -> None:
    """Apply a bounded shared default when an otherwise valid item has no time filters."""
    open_ended_time_markers = (
        "all time",
        "of all time",
        "ever recorded",
        "ever observed",
        "in history",
        "historically",
    )

    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("year") is not None or item.get("year_start") or item.get("year_end"):
            continue
        if item.get("date_start") or item.get("date_end"):
            continue

        hints = item.get("_hints") if isinstance(item.get("_hints"), dict) else {}
        query_text = " ".join(
            part for part in (
                str(hints.get("original_query") or "").strip().lower(),
                str(item.get("summary") or "").strip().lower(),
            )
            if part
        )
        if any(marker in query_text for marker in open_ended_time_markers):
            item["_time_hint_applied"] = True
            continue

        source_id = item.get("source_id")
        if not source_id:
            continue

        metadata = load_source_metadata(source_id) or {}
        temporal = metadata.get("temporal_coverage", {}) if isinstance(metadata, dict) else {}
        available_start = _coerce_coverage_year(temporal.get("start"))
        available_end = _coerce_coverage_year(temporal.get("end"))

        if available_end is None:
            continue

        default_end = available_end
        default_start = max(available_end - (default_year_span - 1), available_start or available_end)
        if default_start > default_end:
            continue

        item["year_start"] = default_start
        item["year_end"] = default_end
        item["_defaulted_time_range"] = {
            "year_start": default_start,
            "year_end": default_end,
            "available_start": available_start,
            "available_end": available_end,
        }


def apply_event_qualifier_defaults(
    items: list,
    load_source_metadata,
    load_reference_json,
) -> None:
    """Apply deterministic default event ranking when the query uses vague superlatives."""
    reference = load_reference_json("query_synonyms.json") or {}
    pack_defaults = reference.get("event_qualifier_defaults") if isinstance(reference, dict) else {}
    if not isinstance(pack_defaults, dict) or not pack_defaults:
        return

    for item in items:
        if not isinstance(item, dict) or item.get("sort"):
            continue

        source_id = str(item.get("source_id") or "").strip()
        if not source_id:
            continue

        metadata = load_source_metadata(source_id) or {}
        if not isinstance(metadata, dict):
            continue

        data_type = str(metadata.get("data_type") or "").strip().lower()
        significance_column = str(metadata.get("significance_column") or "").strip()
        event_mode = str(item.get("mode") or "").strip().lower()
        if data_type != "events" and not significance_column and event_mode != "events":
            continue

        pack_id = str(item.get("pack_id") or metadata.get("pack_id") or "").strip().lower()
        qualifier_defaults = pack_defaults.get(pack_id)
        if not isinstance(qualifier_defaults, dict) or not qualifier_defaults:
            continue

        hints = item.get("_hints") if isinstance(item.get("_hints"), dict) else {}
        query_text = " ".join(
            part for part in (
                str(hints.get("original_query") or "").strip().lower(),
                str(item.get("summary") or "").strip().lower(),
            )
            if part
        )
        if not query_text:
            continue

        selected_metric = None
        selected_order = "desc"
        for qualifier, config in qualifier_defaults.items():
            qualifier_text = str(qualifier or "").strip().lower()
            if not qualifier_text or qualifier_text not in query_text:
                continue
            if isinstance(config, dict):
                metric_text = str(config.get("metric") or "").strip()
                order_text = str(config.get("order") or "desc").strip().lower()
            else:
                metric_text = str(config or "").strip()
                order_text = "desc"
            if metric_text:
                selected_metric = metric_text
                selected_order = "asc" if order_text == "asc" else "desc"
                break
        if not selected_metric:
            continue

        item["sort"] = {"by": selected_metric, "order": selected_order}
        if not item.get("limit") and _query_requests_single_ranked_event(query_text):
            item["limit"] = 1


def _looks_country_level_region(region: str) -> bool:
    value = str(region or "").strip()
    if not value:
        return True
    if re.fullmatch(r"^[A-Z]{3}(?:-[A-Z0-9]+)*$", value):
        return value.count("-") == 0
    normalized = value.lower()
    return normalized in {"global", "world", "canada", "usa", "us", "united states", "australia"}


def _looks_canonical_region_id(region: str) -> bool:
    value = str(region or "").strip().upper()
    if not value:
        return False
    return bool(
        re.fullmatch(r"[A-Z]{3}(?:-[A-Z0-9]+)*", value)
        or value.startswith("EEZ-")
        or value.startswith("X")
    )


def apply_query_derived_order_hints(
    items: list,
    load_source_metadata,
    *,
    hints: dict | None = None,
) -> None:
    """Apply preprocessor-derived canonical region/filter hints to incomplete items."""
    shared_constraints = (hints or {}).get("query_constraints") if isinstance(hints, dict) else None
    for item in items:
        if not isinstance(item, dict):
            continue

        hints = item.get("_hints") if isinstance(item.get("_hints"), dict) else {}
        query_text = " ".join(
            part for part in (
                str(hints.get("original_query") or "").strip(),
                str(item.get("summary") or "").strip(),
            )
            if part
        )
        if not query_text:
            continue

        query_constraints = shared_constraints or extract_query_constraints(
            query_text,
            resolve_admin_text_to_loc_id_func=resolve_admin_text_to_loc_id,
            load_reference_file_func=lambda _path: {},
            reference_dir=None,
        )

        source_id = str(item.get("source_id") or "").strip()
        metadata = load_source_metadata(source_id) or {}
        metrics = metadata.get("metrics") if isinstance(metadata, dict) else {}

        area_constraint = query_constraints.get("area_constraint") if isinstance(query_constraints, dict) else {}
        if not isinstance(area_constraint, dict):
            area_constraint = {}
        area_threshold_km2 = area_constraint.get("normalized_value")
        if area_threshold_km2 is not None:
            metric_keys = set(metrics.keys()) if isinstance(metrics, dict) else set()
            if "area_km2" in metric_keys or "burned_acres" in metric_keys:
                filters = item.get("filters") if isinstance(item.get("filters"), dict) else {}
                existing_min = filters.get("area_km2_min")
                try:
                    existing_value = float(existing_min) if existing_min is not None else None
                except (TypeError, ValueError):
                    existing_value = None
                filters["area_km2_min"] = (
                    max(existing_value, area_threshold_km2)
                    if existing_value is not None
                    else area_threshold_km2
                )
                item["filters"] = filters

        region_loc_id = str((query_constraints or {}).get("region_loc_id") or "").strip()
        current_region = str(item.get("region") or "").strip()
        if region_loc_id and (
            _looks_country_level_region(current_region)
            or not _looks_canonical_region_id(current_region)
        ):
            item["region"] = region_loc_id


def run_pre_validation_pipeline(
    items: list,
    hints: dict,
    catalog: dict,
    detect_event_mode,
    normalize_aggregate_metric_mode,
    normalize_order_items,
    expand_full_pack_loads,
    expand_wildcard_metrics,
    expand_all_derived_fields,
) -> tuple[list, int]:
    """Run the deterministic item expansion pipeline before validation."""
    items = detect_event_mode(items, hints)
    items = normalize_aggregate_metric_mode(items, hints, catalog)
    items = normalize_order_items(items, catalog)
    items = expand_full_pack_loads(items, catalog)
    items = expand_wildcard_metrics(items)
    metric_count = sum(1 for item in items if item.get("type") != "derived_result")
    expanded_items = expand_all_derived_fields(items)
    return expanded_items, metric_count


def split_derived_specs(expanded_items: list) -> tuple[list, list]:
    """Separate derived-result specs from regular validated items."""
    regular_items = []
    derived_specs = []
    for item in expanded_items:
        if item.get("type") == "derived_result":
            derived_specs.append(item)
        else:
            regular_items.append(item)
    return regular_items, derived_specs


def validate_regular_items(
    regular_items: list,
    catalog: dict,
    normalize_source_declared_scope,
    validate_item,
) -> tuple[list, list, int]:
    """Validate regular items and collect error summaries."""
    validated_items = []
    errors = []
    valid_count = 0

    for item in regular_items:
        item = normalize_source_declared_scope(item)
        validated = validate_item(item, catalog)
        validated_items.append(validated)
        if validated.get("_valid"):
            valid_count += 1
        else:
            errors.append(validated.get("_error", "Unknown error"))

    return validated_items, errors, valid_count


def build_validation_summary(validated_items: list, errors: list, valid_count: int) -> str:
    """Build the human-readable validation summary string."""
    total = len(validated_items)
    if errors:
        return f"{valid_count}/{total} items valid. Errors: {'; '.join(errors)}"
    return f"All {total} items validated successfully"
