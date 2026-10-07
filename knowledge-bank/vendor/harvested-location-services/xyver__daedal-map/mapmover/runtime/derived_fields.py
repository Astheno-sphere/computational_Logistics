"""Shared derived-field expansion helpers."""

from __future__ import annotations


DEFAULT_DERIVED_EXPANSIONS = {
    "per_capita": {
        "denominator": "population",
        "label_suffix": "Per Capita",
    },
    "density": {
        "denominator": "area_sq_km",
        "denominator_source": "world_factbook_static",
        "label_suffix": "Density",
    },
    "per_1000": {
        "denominator": "population",
        "multiplier": 1000,
        "label_suffix": "Per 1000",
    },
}


def expand_derived_shortcut(
    item: dict,
    *,
    derived_expansions: dict,
    resolve_population_dependency_func,
    get_source_admin_levels_func,
    metric_display_name_func,
    population_family: str,
) -> list:
    """Expand a shortcut like `derived=per_capita` into component items."""
    derived_type = item.get("derived")
    if not derived_type or derived_type not in derived_expansions:
        return [item]

    expansion = derived_expansions[derived_type]
    source_id = item.get("source_id")
    metric = item.get("metric")
    region = item.get("region")
    year = item.get("year")
    year_start = item.get("year_start")
    year_end = item.get("year_end")

    base_props = {"region": region}
    if year:
        base_props["year"] = year
    if year_start:
        base_props["year_start"] = year_start
    if year_end:
        base_props["year_end"] = year_end

    expanded = []

    source_admin_levels = get_source_admin_levels_func(source_id)
    target_level = max(source_admin_levels) if source_admin_levels else None
    numerator_candidates = [metric]
    numerator_display = metric_display_name_func(source_id, metric) if source_id and metric else None
    if numerator_display and numerator_display not in numerator_candidates:
        numerator_candidates.append(numerator_display)

    expanded.append({
        "source_id": source_id,
        "metric": metric,
        "for_derivation": True,
        **base_props,
    })

    denom_metric = expansion["denominator"]
    denom_source = expansion.get("denominator_source", source_id)
    if denom_metric == population_family:
        resolved_source, resolved_metric = resolve_population_dependency_func(
            region=region,
            preferred_source_id=source_id,
            target_level=target_level,
        )
        if resolved_source:
            denom_source = resolved_source
            denom_metric = resolved_metric

    expanded.append({
        "source_id": denom_source,
        "metric": denom_metric,
        "for_derivation": True,
        **base_props,
    })

    label = f"{metric} {expansion['label_suffix']}"
    denominator_candidates = [denom_metric]
    denom_display = metric_display_name_func(denom_source, denom_metric) if denom_source and denom_metric else None
    if denom_display and denom_display not in denominator_candidates:
        denominator_candidates.append(denom_display)
    derived_result = {
        "type": "derived_result",
        "numerator": metric,
        "denominator": denom_metric,
        "numerator_candidates": numerator_candidates,
        "denominator_candidates": denominator_candidates,
        "label": label,
    }
    if expansion.get("multiplier"):
        derived_result["multiplier"] = expansion["multiplier"]
    expanded.append(derived_result)

    return expanded


def expand_cross_source_derived(item: dict) -> list:
    """Expand a cross-source derived field into component items."""
    if item.get("type") != "derived":
        return [item]

    numerator = item.get("numerator", {})
    denominator = item.get("denominator", {})
    region = item.get("region")
    year = item.get("year")
    year_start = item.get("year_start")
    year_end = item.get("year_end")

    if isinstance(numerator, str):
        numerator = {"metric": numerator}
    if isinstance(denominator, str):
        denominator = {"metric": denominator}

    base_props = {"region": region}
    if year:
        base_props["year"] = year
    if year_start:
        base_props["year_start"] = year_start
    if year_end:
        base_props["year_end"] = year_end

    expanded = []

    num_source = numerator.get("source_id", item.get("source_id"))
    num_metric = numerator.get("metric")
    if num_source and num_metric:
        expanded.append({
            "source_id": num_source,
            "metric": num_metric,
            "for_derivation": True,
            **base_props,
        })

    denom_source = denominator.get("source_id", item.get("source_id"))
    denom_metric = denominator.get("metric")
    if denom_source and denom_metric:
        expanded.append({
            "source_id": denom_source,
            "metric": denom_metric,
            "for_derivation": True,
            **base_props,
        })

    derived_result = {
        "type": "derived_result",
        "numerator": num_metric,
        "denominator": denom_metric,
        "label": item.get("label", f"{num_metric}/{denom_metric}"),
    }
    if item.get("multiplier"):
        derived_result["multiplier"] = item["multiplier"]
    expanded.append(derived_result)

    return expanded


def expand_all_derived_fields(
    items: list,
    *,
    derived_expansions: dict,
    resolve_population_dependency_func,
    get_source_admin_levels_func,
    metric_display_name_func,
    population_family: str,
) -> list:
    """Expand all derived-field shorthand in an items list."""
    expanded = []

    for item in items:
        if item.get("derived") and item.get("derived") in derived_expansions:
            expanded.extend(
                expand_derived_shortcut(
                    item,
                    derived_expansions=derived_expansions,
                    resolve_population_dependency_func=resolve_population_dependency_func,
                    get_source_admin_levels_func=get_source_admin_levels_func,
                    metric_display_name_func=metric_display_name_func,
                    population_family=population_family,
                )
            )
        elif item.get("type") == "derived":
            expanded.extend(expand_cross_source_derived(item))
        else:
            expanded.append(item)

    return expanded
