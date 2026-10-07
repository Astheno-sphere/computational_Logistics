"""Shared population dependency helpers extracted from postprocessor."""

from __future__ import annotations


def get_source_admin_levels(metadata: dict | None) -> list[int]:
    if not metadata:
        return []

    admin_levels = metadata.get("admin_levels")
    if isinstance(admin_levels, list):
        return sorted(
            {
                int(level)
                for level in admin_levels
                if isinstance(level, (int, float)) or str(level).isdigit()
            }
        )

    geo_level = metadata.get("geographic_level")
    if isinstance(geo_level, list):
        values = []
        for level in geo_level:
            text = str(level or "")
            if text.startswith("admin_") and text[6:].isdigit():
                values.append(int(text[6:]))
        return sorted(set(values))
    if isinstance(geo_level, str) and geo_level.startswith("admin_") and geo_level[6:].isdigit():
        return [int(geo_level[6:])]
    if geo_level in {"country", "admin_0"}:
        return [0]

    coverage = metadata.get("geographic_coverage") if isinstance(metadata.get("geographic_coverage"), dict) else {}
    coverage_levels = coverage.get("admin_levels")
    if isinstance(coverage_levels, list):
        return sorted(
            {
                int(level)
                for level in coverage_levels
                if isinstance(level, (int, float)) or str(level).isdigit()
            }
        )
    return []


def scope_matches_population_region(metadata: dict | None, region: str | None) -> bool:
    if not metadata:
        return False
    coverage = metadata.get("geographic_coverage", {}) or {}
    coverage_type = str(coverage.get("type") or "global").lower()
    if not region:
        return coverage_type == "global"

    region_upper = str(region).strip().upper()
    country = region_upper.split("-")[0] if region_upper else ""

    if coverage_type == "global":
        return True
    if coverage_type == "country":
        return str(coverage.get("country") or "").upper() == country
    if coverage_type == "regional":
        missing = {
            str(code).upper()
            for code in coverage.get("common_missing", []) or []
        }
        common_count = coverage.get("common_count")
        if common_count:
            return country not in missing
        return False
    return False


def find_population_metric_key(source_id: str, *, load_source_metadata_func, population_family: str) -> str | None:
    metadata = load_source_metadata_func(source_id) or {}
    metrics = metadata.get("metrics", {}) or {}
    preferred = (
        (((metadata.get("selection_priority") or {}).get(population_family) or {}).get("metric"))
        or ""
    )
    if preferred and preferred in metrics:
        return preferred
    for candidate in ("population", "total_pop"):
        if candidate in metrics:
            return candidate
    return None


def resolve_population_dependency(
    *,
    region: str | None,
    preferred_source_id: str | None,
    target_level: int | None,
    cache_dict: dict,
    population_family: str,
    find_population_metric_key_func,
    load_source_metadata_func,
    get_source_admin_levels_func,
    scope_matches_population_region_func,
    load_catalog_func,
) -> tuple[str | None, str]:
    cache_key = (region or "", preferred_source_id or "", target_level)
    cached = cache_dict.get(cache_key)
    if cached:
        return cached

    if preferred_source_id:
        preferred_metric = find_population_metric_key_func(preferred_source_id)
        preferred_metadata = load_source_metadata_func(preferred_source_id) or {}
        preferred_levels = get_source_admin_levels_func(preferred_metadata)
        if preferred_metric and (
            target_level is None
            or not preferred_levels
            or target_level in preferred_levels
        ):
            resolved = (preferred_source_id, preferred_metric)
            cache_dict[cache_key] = resolved
            return resolved

    candidates = []
    catalog = load_catalog_func() or {}
    for source in catalog.get("sources", []):
        source_id = source.get("source_id")
        if not source_id:
            continue
        metadata = load_source_metadata_func(source_id) or {}
        priority = ((metadata.get("selection_priority") or {}).get(population_family) or {})
        metric_key = priority.get("metric")
        if not metric_key:
            continue
        if metric_key not in (metadata.get("metrics") or {}):
            continue
        if not scope_matches_population_region_func(metadata, region):
            continue

        admin_levels = get_source_admin_levels_func(metadata)
        if target_level is not None and admin_levels and target_level not in admin_levels:
            continue

        candidates.append(
            (
                int(priority.get("priority_rank", 9999)),
                source_id,
                metric_key,
            )
        )

    candidates.sort(key=lambda item: (item[0], item[1]))
    resolved = (candidates[0][1], candidates[0][2]) if candidates else (None, "population")
    cache_dict[cache_key] = resolved
    return resolved
