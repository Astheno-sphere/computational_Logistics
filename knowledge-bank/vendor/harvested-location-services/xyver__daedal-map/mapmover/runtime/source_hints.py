"""Shared metadata/reference hint helpers used across runtime lanes."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ..foundation_helpers import load_reference_json
from .country_geography import (
    get_country_overlap_levels,
    get_country_sub_admin_levels,
)


_IRREGULAR_GEO_PLURALS = {
    "county": "counties",
    "city": "cities",
}

_DEFAULT_RUNTIME_LEVEL_NAMES = {
    "admin_0": "country",
    "admin_1": "state",
    "admin_2": "county",
    "admin_3": "tract",
    "admin_4": "blockgroup",
    "admin_5": "block",
}


@dataclass(frozen=True)
class ResolvedGeoContract:
    requested_token: str
    runtime_level: str | None
    country_level_name: str | None
    source_anchor_runtime_level: str | None
    geometry_kind: str
    geometry_subkind: str | None
    hierarchy_relation: str
    source_level_value: str | None
    source_filter_field: str
    filter_strategy: str


def _normalize_geo_alias_text(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _pluralize_geo_token(token: str) -> str:
    text = str(token or "").strip().lower()
    if not text:
        return ""
    if text in _IRREGULAR_GEO_PLURALS:
        return _IRREGULAR_GEO_PLURALS[text]
    if text.endswith("s"):
        return text
    if text.endswith("y") and len(text) > 1 and text[-2] not in "aeiou":
        return text[:-1] + "ies"
    return text + "s"


def _expand_geo_alias_variants(value: str) -> list[str]:
    normalized = _normalize_geo_alias_text(value)
    if not normalized:
        return []

    variants: list[str] = []

    def _add(text: str) -> None:
        if text and text not in variants:
            variants.append(text)

    _add(normalized)

    spaced = normalized.replace("_", " ")
    if spaced != normalized:
        _add(spaced.replace(" ", "_"))

    parts = [part for part in normalized.split("_") if part]
    if parts:
        plural_last = parts[:-1] + [_pluralize_geo_token(parts[-1])]
        _add("_".join(plural_last))

        singular_last = parts[-1]
        if singular_last in _IRREGULAR_GEO_PLURALS.values():
            reverse = {v: k for k, v in _IRREGULAR_GEO_PLURALS.items()}
            singular_last = reverse.get(singular_last, singular_last)
            _add("_".join(parts[:-1] + [singular_last]))

    if normalized == "blockgroup":
        _add("block_group")
        _add("block_groups")
    if normalized == "block_group":
        _add("blockgroup")
        _add("blockgroups")

    return variants


def _normalize_runtime_geo_level(value: str | None) -> str | None:
    text = _normalize_geo_alias_text(value or "")
    if text.startswith("admin_") and text[6:].isdigit():
        return text
    return None


def _fallback_runtime_level_from_friendly(value: str | None) -> str | None:
    normalized = _normalize_geo_alias_text(value or "")
    if not normalized:
        return None
    for runtime_level, friendly_name in _DEFAULT_RUNTIME_LEVEL_NAMES.items():
        if normalized == friendly_name:
            return runtime_level
    return None


def _runtime_level_number(value: str | None) -> int | None:
    runtime_level = _normalize_runtime_geo_level(value)
    if runtime_level is None:
        return None
    try:
        return int(runtime_level.split("_", 1)[1])
    except (IndexError, TypeError, ValueError):
        return None


def get_routing_hints(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}
    routing_hints = metadata.get("routing_hints")
    return routing_hints if isinstance(routing_hints, dict) else {}


def get_comparison_hints(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}
    comparison_hints = metadata.get("comparison_hints")
    return comparison_hints if isinstance(comparison_hints, dict) else {}


def get_hint_alias_terms(metadata: dict | None, *fields: str) -> list[str]:
    routing_hints = get_routing_hints(metadata)
    aliases: list[str] = []
    for field_name in fields:
        field_values = routing_hints.get(field_name) or []
        if isinstance(field_values, dict):
            values = field_values.keys()
        elif isinstance(field_values, list):
            values = field_values
        else:
            continue
        for value in values:
            text = str(value or "").strip().lower()
            if text and text not in aliases:
                aliases.append(text)
    return aliases


def get_hint_query_priority(metadata: dict | None) -> float:
    routing_hints = get_routing_hints(metadata)
    try:
        value = float(routing_hints.get("query_priority") or 0.0)
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, min(0.25, value))


def get_single_metric_default(metadata: dict | None) -> str:
    routing_hints = get_routing_hints(metadata)
    return str(routing_hints.get("single_metric_default") or "").strip()


def get_unsupported_metric_aliases(metadata: dict | None) -> list[str]:
    routing_hints = get_routing_hints(metadata)
    aliases = routing_hints.get("unsupported_metric_aliases") or []
    if not isinstance(aliases, list):
        return []
    return [str(alias).strip() for alias in aliases if str(alias).strip()]


def get_supported_geography_summary(metadata: dict | None) -> str:
    routing_hints = get_routing_hints(metadata)
    geo_summary = str(routing_hints.get("supported_geography_summary") or "").strip()
    if geo_summary:
        return geo_summary
    if not isinstance(metadata, dict):
        return "see source metadata"
    geo_levels = metadata.get("geographic_level")
    if isinstance(geo_levels, list):
        cleaned = [str(level).replace("_", " ") for level in geo_levels if level]
        if cleaned:
            return ", ".join(cleaned)
    if geo_levels:
        return str(geo_levels).replace("_", " ")
    return "see source metadata"


def get_geo_level_aliases(metadata: dict | None) -> dict[str, str]:
    routing_hints = get_routing_hints(metadata)
    aliases = routing_hints.get("geo_level_aliases") or {}
    if not isinstance(aliases, dict):
        return {}
    normalized: dict[str, str] = {}
    for alias, target in aliases.items():
        target_text = _normalize_geo_alias_text(target)
        if not target_text:
            continue
        for alias_text in _expand_geo_alias_variants(alias):
            normalized[alias_text] = target_text
    return normalized


def get_country_geo_level_aliases(metadata: dict | None) -> dict[str, str]:
    """Load country-owned geo-level names from crosswalk overlap + sub-admin data.

    This is the canonical country-level naming seam. Source metadata
    geo_level_aliases should only supplement this when a source uses a local
    spelling or source-specific label that is not appropriate to store in the
    country crosswalk.
    """
    if not isinstance(metadata, dict):
        return {}

    geographic_coverage = metadata.get("geographic_coverage") or {}
    iso3 = str(geographic_coverage.get("country") or "").strip().upper()
    if not iso3:
        return {}

    sub_admin_levels = get_country_sub_admin_levels(iso3)
    overlap_levels = get_country_overlap_levels(iso3)
    if not sub_admin_levels and not overlap_levels:
        return {}

    aliases: dict[str, str] = {}
    for admin_level, info in overlap_levels.items():
        if not isinstance(info, dict):
            continue
        canonical_level = _normalize_geo_alias_text(admin_level)
        if not canonical_level:
            continue

        for field_name in ("display_name", "canonical_dataset_label", "local_name"):
            for alias_text in _expand_geo_alias_variants(info.get(field_name) or ""):
                aliases[alias_text] = canonical_level

        for alias in info.get("aliases") or []:
            for alias_text in _expand_geo_alias_variants(alias):
                aliases[alias_text] = canonical_level

    for admin_level, info in sub_admin_levels.items():
        if not isinstance(info, dict):
            continue
        canonical_level = _normalize_geo_alias_text(admin_level)
        if not canonical_level:
            continue

        for field_name in ("name", "display_name", "canonical_dataset_label"):
            for alias_text in _expand_geo_alias_variants(info.get(field_name) or ""):
                aliases[alias_text] = canonical_level

        for alias in info.get("aliases") or []:
            for alias_text in _expand_geo_alias_variants(alias):
                aliases[alias_text] = canonical_level

    return aliases


def get_country_runtime_level_names(metadata: dict | None) -> dict[str, str]:
    """Return canonical runtime-level -> country-local display name mapping."""
    names = dict(_DEFAULT_RUNTIME_LEVEL_NAMES)
    if not isinstance(metadata, dict):
        return names

    geographic_coverage = metadata.get("geographic_coverage") or {}
    iso3 = str(geographic_coverage.get("country") or "").strip().upper()
    if not iso3:
        return names

    sub_admin_levels = get_country_sub_admin_levels(iso3)
    overlap_levels = get_country_overlap_levels(iso3)
    if not sub_admin_levels and not overlap_levels:
        return names

    for admin_level, info in overlap_levels.items():
        runtime_level = _normalize_runtime_geo_level(admin_level)
        if runtime_level is None or not isinstance(info, dict):
            continue
        for field_name in ("display_name", "canonical_dataset_label", "local_name"):
            candidate = _normalize_geo_alias_text(info.get(field_name) or "")
            if candidate:
                names[runtime_level] = candidate
                break

    for admin_level, info in sub_admin_levels.items():
        runtime_level = _normalize_runtime_geo_level(admin_level)
        if runtime_level is None or not isinstance(info, dict):
            continue
        for field_name in ("canonical_dataset_label", "display_name", "name"):
            candidate = _normalize_geo_alias_text(info.get(field_name) or "")
            if candidate:
                names[runtime_level] = candidate
                break
    return names


def get_source_anchor_runtime_level(metadata: dict | None) -> str | None:
    if not isinstance(metadata, dict):
        return None

    geographic_level = metadata.get("geographic_level")
    if isinstance(geographic_level, list):
        runtime_levels = [
            _normalize_runtime_geo_level(level)
            for level in geographic_level
        ]
        runtime_levels = [level for level in runtime_levels if level]
        if runtime_levels:
            return max(runtime_levels, key=lambda level: _runtime_level_number(level) or -1)
    else:
        runtime_level = _normalize_runtime_geo_level(geographic_level)
        if runtime_level:
            return runtime_level

    admin_levels = metadata.get("admin_levels")
    if isinstance(admin_levels, list):
        numbers: list[int] = []
        for level in admin_levels:
            try:
                numbers.append(int(level))
            except (TypeError, ValueError):
                continue
        if numbers:
            return f"admin_{max(numbers)}"

    coverage = metadata.get("geographic_coverage") or {}
    coverage_levels = coverage.get("admin_levels")
    if isinstance(coverage_levels, list):
        numbers = []
        for level in coverage_levels:
            try:
                numbers.append(int(level))
            except (TypeError, ValueError):
                continue
        if numbers:
            return f"admin_{max(numbers)}"

    return None


def _metadata_supported_runtime_levels(metadata: dict | None) -> set[str]:
    if not isinstance(metadata, dict):
        return set()

    values = metadata.get("geographic_level")
    if isinstance(values, list):
        levels = {
            _normalize_runtime_geo_level(value)
            for value in values
        }
        return {level for level in levels if level}

    level = _normalize_runtime_geo_level(values)
    return {level} if level else set()


def infer_geometry_kind(metadata: dict | None) -> tuple[str, str | None]:
    if not isinstance(metadata, dict):
        return "admin", None

    data_type = metadata.get("data_type")
    if isinstance(data_type, list):
        data_types = {str(value or "").strip().lower() for value in data_type if str(value or "").strip()}
    else:
        data_types = {str(data_type or "").strip().lower()} if str(data_type or "").strip() else set()

    geojson_shape = str(metadata.get("geojson_shape") or "").strip().lower()

    if "events" in data_types:
        if "track" in geojson_shape:
            return "event", "track"
        if "point" in geojson_shape or geojson_shape == "location_shape":
            return "event", "point"
        if "line" in geojson_shape:
            return "event", "line"
        return "event", "area" if geojson_shape else None

    if geojson_shape == "building_shape":
        return "entity", "area"
    if geojson_shape == "location_shape":
        return "entity", "point"
    if "geometry" in data_types and geojson_shape and geojson_shape not in {"area", "polygon"}:
        if "point" in geojson_shape:
            return "entity", "point"
        return "entity", "area"

    return "admin", None


def source_geometry_kind(metadata: dict | None) -> str:
    return infer_geometry_kind(metadata)[0]


def source_geometry_subkind(metadata: dict | None) -> str | None:
    return infer_geometry_kind(metadata)[1]


def derive_source_geo_level_from_loc_id(loc_id: str, metadata: dict | None) -> str | None:
    """Infer a canonical runtime geo level from source-native loc_id shape.

    This is intentionally metadata-gated. Runtime should only infer a synthetic
    geo level when the source family is known to encode a stable hierarchy in
    its loc_id format and does not already expose an explicit geo_level column.
    """
    if not loc_id or not isinstance(metadata, dict):
        return None

    source_id = str(metadata.get("source_id") or "").strip().lower()
    source_name = str(metadata.get("source_name") or "").strip().lower()
    keywords = {
        str(value or "").strip().lower()
        for value in (metadata.get("keywords") or [])
        if str(value or "").strip()
    }
    supported_levels = _metadata_supported_runtime_levels(metadata)

    is_eurostat_family = (
        source_id == "eurostat"
        or "eurostat" in source_name
        or "nuts" in keywords
    )
    if not is_eurostat_family:
        return None

    text = str(loc_id).strip()
    derived_level = None
    if "-" not in text:
        derived_level = "admin_0" if len(text) == 3 else None
    else:
        suffix = text.split("-", 1)[1]
        code_len = len(suffix)
        if code_len == 3:
            derived_level = "admin_1"
        elif code_len == 4:
            derived_level = "admin_2"
        elif code_len == 5:
            derived_level = "admin_3"

    if derived_level and (not supported_levels or derived_level in supported_levels):
        return derived_level
    return None


def build_source_runtime_geo_contract_map(metadata: dict | None) -> dict[str, dict[str, str]]:
    """Map canonical runtime levels to source-row filter semantics.

    Each value has:
    - `source_level_value`: the row value the source expects
    - `source_filter_field`: usually `geo_level`, but may be `loc_id`
    - `filter_strategy`: `equals` or `prefix`
    - `hierarchy_relation`: `exact`, `descendant`, or `ancestor`
    """
    source_aliases = get_geo_level_aliases(metadata)
    country_aliases = get_country_geo_level_aliases(metadata)
    source_anchor_runtime_level = get_source_anchor_runtime_level(metadata)
    source_anchor_number = _runtime_level_number(source_anchor_runtime_level)
    contracts: dict[str, dict[str, str]] = {}

    for alias_text, target_text in source_aliases.items():
        runtime_level = _normalize_runtime_geo_level(target_text)
        if runtime_level is None:
            runtime_level = country_aliases.get(target_text)
        if runtime_level is None:
            runtime_level = country_aliases.get(alias_text)
        if runtime_level is None:
            runtime_level = _fallback_runtime_level_from_friendly(alias_text)
        if runtime_level is None:
            continue

        filter_field = "geo_level"
        filter_strategy = "equals"
        source_level_value = target_text
        hierarchy_relation = "exact"
        if target_text == "loc_id":
            filter_field = "loc_id"
            filter_strategy = "prefix"
            source_level_value = None
            requested_number = _runtime_level_number(runtime_level)
            if requested_number is not None and source_anchor_number is not None:
                if source_anchor_number > requested_number:
                    hierarchy_relation = "descendant"
                elif source_anchor_number < requested_number:
                    hierarchy_relation = "ancestor"

        existing = contracts.get(runtime_level)
        if (
            existing
            and existing.get("source_filter_field") == "geo_level"
            and filter_field != "geo_level"
        ):
            continue
        contracts[runtime_level] = {
            "source_level_value": source_level_value or "",
            "source_filter_field": filter_field,
            "filter_strategy": filter_strategy,
            "hierarchy_relation": hierarchy_relation,
        }

    return contracts


def resolve_geo_contract(requested_geo_level: str | None, metadata: dict | None) -> ResolvedGeoContract:
    """Resolve one request-level geography token against country + source hints."""
    requested_token = _normalize_geo_alias_text(requested_geo_level or "")
    if not requested_token:
        return ResolvedGeoContract(
            requested_token="",
            runtime_level=None,
            country_level_name=None,
            source_anchor_runtime_level=get_source_anchor_runtime_level(metadata),
            geometry_kind=infer_geometry_kind(metadata)[0],
            geometry_subkind=infer_geometry_kind(metadata)[1],
            hierarchy_relation="unknown",
            source_level_value=None,
            source_filter_field="geo_level",
            filter_strategy="equals",
        )

    country_aliases = get_country_geo_level_aliases(metadata)
    runtime_level = _normalize_runtime_geo_level(requested_token)
    if runtime_level is None:
        runtime_level = country_aliases.get(requested_token)
    if runtime_level is None:
        source_aliases = get_geo_level_aliases(metadata)
        target_text = source_aliases.get(requested_token)
        runtime_level = _normalize_runtime_geo_level(target_text)
        if runtime_level is None and target_text:
            runtime_level = country_aliases.get(target_text)
    if runtime_level is None:
        runtime_level = _fallback_runtime_level_from_friendly(requested_token)

    runtime_names = get_country_runtime_level_names(metadata)
    source_runtime_map = build_source_runtime_geo_contract_map(metadata)
    source_anchor_runtime_level = get_source_anchor_runtime_level(metadata)
    geometry_kind, geometry_subkind = infer_geometry_kind(metadata)
    source_anchor_number = _runtime_level_number(source_anchor_runtime_level)
    requested_number = _runtime_level_number(runtime_level)
    source_contract = source_runtime_map.get(runtime_level or "", {})

    source_level_value = str(source_contract.get("source_level_value") or "").strip() or None
    source_filter_field = str(source_contract.get("source_filter_field") or "geo_level").strip() or "geo_level"
    filter_strategy = str(source_contract.get("filter_strategy") or "equals").strip() or "equals"
    hierarchy_relation = str(source_contract.get("hierarchy_relation") or "exact").strip() or "exact"

    if not source_contract and requested_number is not None and source_anchor_number is not None:
        if source_anchor_number > requested_number:
            source_filter_field = "loc_id"
            filter_strategy = "prefix"
            hierarchy_relation = "descendant"
            source_level_value = None
        elif source_anchor_number < requested_number:
            hierarchy_relation = "ancestor"
            source_level_value = None

    if source_level_value is None and runtime_level and source_filter_field == "geo_level":
        supported_levels = _metadata_supported_runtime_levels(metadata)
        if runtime_level in supported_levels and not source_contract:
            source_level_value = runtime_level

    if source_level_value is None and runtime_level and source_filter_field == "geo_level":
        fallback_name = runtime_names.get(runtime_level)
        if fallback_name:
            source_level_value = fallback_name

    return ResolvedGeoContract(
        requested_token=requested_token,
        runtime_level=runtime_level,
        country_level_name=runtime_names.get(runtime_level) if runtime_level else None,
        source_anchor_runtime_level=source_anchor_runtime_level,
        geometry_kind=geometry_kind,
        geometry_subkind=geometry_subkind,
        hierarchy_relation=hierarchy_relation,
        source_level_value=source_level_value,
        source_filter_field=source_filter_field,
        filter_strategy=filter_strategy,
    )


def infer_requested_geo_level_from_query(query: str | None, metadata: dict | None) -> str | None:
    """Infer a canonical runtime geo level from query text using shared aliases."""
    query_text = _normalize_geo_alias_text(query or "")
    if not query_text:
        return None

    aliases = get_country_geo_level_aliases(metadata)
    aliases.update(get_geo_level_aliases(metadata))
    for runtime_level, friendly_name in get_country_runtime_level_names(metadata).items():
        if not runtime_level or not friendly_name:
            continue
        for alias_text in _expand_geo_alias_variants(friendly_name):
            aliases.setdefault(alias_text, runtime_level)
    for runtime_level, friendly_name in _DEFAULT_RUNTIME_LEVEL_NAMES.items():
        for alias_text in _expand_geo_alias_variants(friendly_name):
            aliases.setdefault(alias_text, runtime_level)
    if not aliases:
        return None

    best_match: tuple[int, str] | None = None
    padded_query = f"_{query_text}_"
    for alias_text, target_level in aliases.items():
        normalized_alias = _normalize_geo_alias_text(alias_text)
        if not normalized_alias:
            continue
        if f"_{normalized_alias}_" not in padded_query:
            continue
        score = len(normalized_alias)
        if best_match is None or score > best_match[0]:
            best_match = (score, target_level)

    return best_match[1] if best_match else None


def normalize_requested_geo_level_for_source(requested_geo_level: str | None, metadata: dict | None) -> str | None:
    contract = resolve_geo_contract(requested_geo_level, metadata)
    return contract.source_level_value or contract.runtime_level


def get_metric_alias_matches(metadata: dict | None, query: str | None) -> list[tuple[str, str]]:
    routing_hints = get_routing_hints(metadata)
    metric_aliases = routing_hints.get("metric_aliases") or {}
    query_lower = str(query or "").strip().lower()
    if not isinstance(metric_aliases, dict) or not query_lower:
        return []

    matches: list[tuple[str, str]] = []
    for alias, metric_name in metric_aliases.items():
        alias_text = str(alias or "").strip().lower()
        metric_text = str(metric_name or "").strip()
        if alias_text and metric_text and alias_text in query_lower:
            matches.append((alias_text, metric_text))
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    return matches


def get_query_alias_matches(metadata: dict | None, query: str | None) -> list[str]:
    query_lower = str(query or "").strip().lower()
    if not query_lower:
        return []

    raw_matches: list[str] = []
    for alias in get_hint_alias_terms(metadata, "query_aliases", "broad_topic_aliases"):
        if alias and alias in query_lower and alias not in raw_matches:
            raw_matches.append(alias)

    filtered_matches: list[str] = []
    for alias in sorted(raw_matches, key=len, reverse=True):
        if any(alias in existing for existing in filtered_matches):
            continue
        filtered_matches.append(alias)
    return filtered_matches


def select_query_guided_metric(query: str | None, metadata: dict | None) -> str:
    alias_matches = get_metric_alias_matches(metadata, query)
    if alias_matches:
        return str(alias_matches[0][1] or "").strip()

    routing_hints = get_routing_hints(metadata)
    if not routing_hints.get("prefer_order_for_analytics"):
        return ""
    default_metric = get_single_metric_default(metadata)
    if not default_metric:
        return ""
    broad_aliases = get_hint_alias_terms(metadata, "broad_topic_aliases", "query_aliases")
    query_lower = str(query or "").strip().lower()
    if any(alias in query_lower for alias in broad_aliases):
        return str(default_metric).strip()
    return ""


def select_pack_family_source_for_query(
    pack_id: str,
    query: str | None,
    *,
    catalog: dict | None,
    load_source_metadata_func,
) -> tuple[str | None, dict | None, str]:
    if not pack_id or not query:
        return None, None, ""

    best_source_id = None
    best_metadata = None
    best_metric = ""
    best_score = 0.0

    for src in (catalog or {}).get("sources", []):
        if str(src.get("pack_id") or "").strip() != pack_id:
            continue
        source_id = str(src.get("source_id") or "").strip()
        if not source_id:
            continue
        metadata = load_source_metadata_func(source_id) or {}
        if not metadata:
            continue

        metric = select_query_guided_metric(query, metadata)
        query_alias_matches = get_query_alias_matches(metadata, query)
        inferred_geo_level = infer_requested_geo_level_from_query(query, metadata)
        has_query_signal = bool(metric or query_alias_matches or inferred_geo_level)
        if not has_query_signal:
            continue
        score = 0.0
        if metric:
            score += 10.0
        if query_alias_matches:
            score += float(len(query_alias_matches) * 2)
        score += float(get_routing_hints(metadata).get("query_priority", 0.0) or 0.0)
        if inferred_geo_level:
            score += 1.0

        if score > best_score:
            best_source_id = source_id
            best_metadata = metadata
            best_metric = metric
            best_score = score

    if best_source_id and best_score > 0:
        return best_source_id, best_metadata, best_metric
    return None, None, ""


def build_scenario_routing_lines(scenario_defaults: dict | None) -> list[str]:
    if not isinstance(scenario_defaults, dict):
        return []
    lines: list[str] = []
    for concept_key, scenario_map in scenario_defaults.items():
        if not isinstance(scenario_map, dict) or not scenario_map:
            continue
        pretty_concept = {
            "projected_risk_score": "projected risk score",
            "hazard_multiplier": "hazard multiplier",
            "projected_annual_loss_rate_band": "projected annual loss rate band",
            "annual_loss_rate_change_band": "annual loss rate change band",
        }.get(concept_key, str(concept_key).replace("_", " "))
        scenario_examples = []
        for scenario_key, metric_name in scenario_map.items():
            metric_text = str(metric_name or "").strip()
            if not metric_text:
                continue
            pretty_scenario = str(scenario_key).replace("_", " ")
            scenario_examples.append(f'"{pretty_scenario}" -> metric="{metric_text}"')
        if scenario_examples:
            lines.append(
                f"For {pretty_concept} requests, map scenario language to explicit metrics as follows: "
                + "; ".join(scenario_examples[:6])
                + "."
            )
    return lines


def build_comparison_routing_lines(comparison_hints: dict | None) -> list[str]:
    if not isinstance(comparison_hints, dict) or not comparison_hints:
        return []

    lines: list[str] = []
    supported_modes = [
        str(mode).strip()
        for mode in (comparison_hints.get("supported_modes") or [])
        if str(mode).strip()
    ]
    default_metric = str(comparison_hints.get("default_comparison_metric") or "").strip()
    default_window = comparison_hints.get("default_window") or {}
    default_start_year = default_window.get("start_year")
    clarify_on_broad = bool(comparison_hints.get("clarify_on_broad_comparison"))

    if default_metric:
        if supported_modes:
            mode_text = ", ".join(supported_modes[:4])
            lines.append(
                f'For over-time comparison asks that clearly match this source, default to metric="{default_metric}" and comparison modes [{mode_text}] unless the user names a different supported metric.'
            )
        else:
            lines.append(
                f'For over-time comparison asks that clearly match this source, default to metric="{default_metric}" unless the user names a different supported metric.'
            )

    if default_start_year:
        lines.append(
            f"For broad change/improvement asks with no baseline year, use {default_start_year} as the default comparison start year unless the user specifies another time window."
        )

    metrics = comparison_hints.get("metrics") or {}
    if isinstance(metrics, dict) and default_metric and isinstance(metrics.get(default_metric), dict):
        metric_hint = metrics.get(default_metric) or {}
        better_direction = str(metric_hint.get("better_direction") or "").strip().lower()
        label = str(metric_hint.get("label_for_improvement") or "").strip()
        if better_direction == "down":
            lines.append(
                f'For metric="{default_metric}", treat improvement as a decrease'
                + (f" because it represents {label}" if label else "")
                + "."
            )
        elif better_direction == "up":
            lines.append(
                f'For metric="{default_metric}", treat improvement as an increase'
                + (f" because it represents {label}" if label else "")
                + "."
            )

    if clarify_on_broad:
        lines.append(
            "If the user asks for improvement/decline/change without enough topic detail and multiple metrics are materially valid, prefer a grounded clarify instead of silently choosing a different metric family."
        )

    return lines


def build_source_routing_guidance(metadata: dict | None, source_id: str) -> list[str]:
    routing_hints = get_routing_hints(metadata)
    comparison_hints = get_comparison_hints(metadata)
    geometry_kind, geometry_subkind = infer_geometry_kind(metadata)
    source_anchor_runtime_level = get_source_anchor_runtime_level(metadata)
    if not source_id:
        source_id = str((metadata or {}).get("source_id") or "").strip()
    pack_id = str((metadata or {}).get("pack_id") or "").strip()
    lines = [
        f'When this detected source clearly matches the query, keep the order item anchored to source_id="{source_id}" instead of switching to a different same-pack source.'
    ]
    if pack_id:
        lines.append(
            f'If the query is clearly anchored to pack_id="{pack_id}", prefer this pack family and its sibling sources before switching to a different pack for a single overlapping metric.'
        )

    default_metric = get_single_metric_default(metadata)
    if routing_hints.get("prefer_order_for_analytics") and default_metric:
        lines.append(
            f'For broad analytical queries that clearly match this source, prefer type="order" with metric="{default_metric}" unless the user asks for a different metric.'
        )
        lines.append(
            "This includes count/share/ranking questions. Do not fall back to chat just because the source is static, tract-level, or analytical."
        )

    if routing_hints.get("clarify_on_missing_metric"):
        lines.append(
            'For broad topic/goal queries without a specific metric, respond with type="clarify" and ask the user which metric they want using human-readable metric names.'
        )

    if geometry_kind == "entity":
        if geometry_subkind == "point":
            lines.append(
                'For anchored entity-point sources ("show/find/map/list/count [locations/facilities/sites/stations] in X"), prefer type="order" anchored to this source instead of chat. It is valid to omit metric entirely when the goal is to show or filter matching entity points.'
            )
        elif geometry_subkind == "area":
            lines.append(
                "For anchored entity-area sources such as buildings, parcels, or sites, keep the order anchored to the entity source and bridge downward through the loc_id hierarchy for parent geographies instead of treating county/tract/blockgroup requests as direct same-level entity rows."
            )
        else:
            lines.append(
                "For anchored entity sources, preserve the entity layer semantics instead of rewriting them as admin geometry."
            )
        if source_anchor_runtime_level:
            lines.append(
                f"This source is anchored at {source_anchor_runtime_level}; higher-level geography requests should usually filter descendants through loc_id hierarchy rather than forcing a same-level geo_level equality."
            )

    filter_advice = str(routing_hints.get("filter_advice") or "").strip()
    if filter_advice:
        lines.append(f"Filter guidance: {filter_advice}")

    unsupported_aliases = get_unsupported_metric_aliases(metadata)
    if unsupported_aliases:
        examples = ", ".join(unsupported_aliases[:4])
        lines.append(
            f"If the user asks for an unsupported metric such as {examples}, clarify honestly using the supported metrics above and accurately mention the supported geography ({get_supported_geography_summary(metadata)})."
        )

    lines.extend(build_comparison_routing_lines(comparison_hints))
    lines.extend(build_scenario_routing_lines(routing_hints.get("scenario_metric_defaults")))

    metric_aliases = routing_hints.get("metric_aliases") or {}
    if isinstance(metric_aliases, dict) and metric_aliases:
        alias_examples = []
        for alias, metric_name in metric_aliases.items():
            alias_text = str(alias or "").strip()
            metric_text = str(metric_name or "").strip()
            if alias_text and metric_text:
                alias_examples.append(f'"{alias_text}" -> metric="{metric_text}"')
        if alias_examples:
            lines.append(
                "When the query uses one of these metric phrases, map it directly to the matching metric: "
                + "; ".join(alias_examples[:8])
                + "."
            )

    if geometry_kind == "entity" and geometry_subkind == "point":
        lines.append(
            'For point-location registry queries ("show/find/map/list/count locations in X"), prefer type="order" anchored to this source. Use loc_id for country filters and facility_type/source/website when the query names a facility class or asks for websites/public spaces. It is valid to omit metric entirely for location listings and filtered point maps.'
        )
        lines.append(
            'If this detected location source already clearly matches the user query, do not switch to type="chat" just to describe the source. Queries such as "show all fab labs in the United States", "show all public Prusa spaces on the map", or "map all fab labs globally" should return a real order with region and filters when needed.'
        )

    return lines


def build_query_matched_metric_guidance(metadata: dict | None, query: str | None) -> list[str]:
    query_text = str(query or "").strip()
    if not query_text:
        return []

    routing_hints = get_routing_hints(metadata)
    lines: list[str] = []

    metric_matches = get_metric_alias_matches(metadata, query_text)
    if metric_matches:
        alias_text, metric_name = metric_matches[0]
        lines.append(
            f'The user query already contains the metric phrase "{alias_text}". Return type="order" and set metric="{metric_name}" unless the user explicitly asks for a different metric.'
        )
        lines.append(
            "Do not switch to chat or ask a follow-up just to restate the matching metric when the request already includes a clear time range, geography, or comparison."
        )

    if routing_hints.get("prefer_order_for_analytics"):
        default_metric = get_single_metric_default(metadata)
        broad_aliases = get_hint_alias_terms(metadata, "broad_topic_aliases", "query_aliases")
        query_lower = query_text.lower()
        if default_metric and any(alias in query_lower for alias in broad_aliases):
            lines.append(
                f'This query matches the source topic closely enough to default to metric="{default_metric}". Prefer type="order" instead of chat when the user is asking to show, compare, trend, rank, or map the data.'
            )

    return lines


def build_pack_family_preference_guidance(
    detected_source: dict | None,
    source_candidates: dict | None,
) -> list[str]:
    detected = detected_source or {}
    detected_pack_id = str(detected.get("pack_id") or "").strip()
    detected_source_id = str(detected.get("source_id") or "").strip()
    if not detected_pack_id:
        return []

    candidates = (source_candidates or {}).get("candidates") or []
    same_pack_ids: list[str] = []
    outside_pack_ids: list[str] = []
    for candidate in candidates:
        source_id = str(candidate.get("source_id") or "").strip()
        candidate_pack_id = str(candidate.get("pack_id") or "").strip()
        if not source_id:
            continue
        if candidate_pack_id == detected_pack_id:
            if source_id not in same_pack_ids:
                same_pack_ids.append(source_id)
        elif candidate_pack_id and source_id not in outside_pack_ids:
            outside_pack_ids.append(source_id)

    lines = [
        f'The current query appears to belong to pack_id="{detected_pack_id}". Stay inside that pack family by default.'
    ]
    if same_pack_ids:
        sibling_ids = [source_id for source_id in same_pack_ids if source_id != detected_source_id]
        if sibling_ids:
            lines.append(
                "If the metric is ambiguous, clarify within this pack family first instead of jumping to another pack. "
                f"Same-pack candidates here include: {', '.join(sibling_ids[:5])}."
            )
    if outside_pack_ids:
        lines.append(
            "Do not jump to another pack just because a similar metric exists there. "
            f"Only switch packs if the user explicitly asks for it or this pack family cannot answer. Other candidate packs are represented by: {', '.join(outside_pack_ids[:5])}."
        )
    return lines


def build_reference_summary(reference_data: dict | None) -> str:
    if not isinstance(reference_data, dict) or not reference_data:
        return ""

    parts: list[str] = []

    goal = reference_data.get("goal")
    if isinstance(goal, dict):
        name = str(goal.get("name") or "").strip()
        description = str(goal.get("description") or "").strip()
        if name:
            parts.append(f"Goal: {name}")
        if description:
            parts.append(f"Description: {description}")

    about = reference_data.get("about")
    dataset = reference_data.get("this_dataset")
    if isinstance(about, dict) or isinstance(dataset, dict):
        if isinstance(about, dict):
            name = str(about.get("name") or "").strip()
            publisher = str(about.get("publisher") or "").strip()
            history = str(about.get("history") or "").strip()
            if name:
                parts.append(f"About: {name}")
            if publisher:
                parts.append(f"Publisher: {publisher}")
            if history:
                parts.append(f"Background: {history[:220]}")
        if isinstance(dataset, dict):
            focus = str(dataset.get("focus") or "").strip()
            if focus:
                parts.append(f"Dataset focus: {focus}")

    pack = reference_data.get("pack")
    if isinstance(pack, dict):
        pack_name = str(pack.get("name") or "").strip()
        pack_description = str(pack.get("description") or "").strip()
        if pack_name:
            parts.append(f"Pack: {pack_name}")
        if pack_description:
            parts.append(f"Pack description: {pack_description}")

    comparison_language_hints = reference_data.get("comparison_language_hints") or {}
    if isinstance(comparison_language_hints, dict) and comparison_language_hints:
        improvement_aliases = comparison_language_hints.get("improvement_aliases") or []
        decline_aliases = comparison_language_hints.get("decline_aliases") or []
        volatility_aliases = comparison_language_hints.get("volatility_aliases") or []
        if improvement_aliases:
            parts.append(
                "Comparison language: improvement terms include "
                + ", ".join(str(alias).strip() for alias in improvement_aliases[:5] if str(alias).strip())
                + "."
            )
        if decline_aliases:
            parts.append(
                "Decline terms include "
                + ", ".join(str(alias).strip() for alias in decline_aliases[:5] if str(alias).strip())
                + "."
            )
        if volatility_aliases:
            parts.append(
                "Volatility terms include "
                + ", ".join(str(alias).strip() for alias in volatility_aliases[:5] if str(alias).strip())
                + "."
            )

    comparison_metric_families = reference_data.get("comparison_metric_families") or {}
    if isinstance(comparison_metric_families, dict) and comparison_metric_families:
        family_bits = []
        for family_name, family_metrics in list(comparison_metric_families.items())[:4]:
            if isinstance(family_metrics, list) and family_metrics:
                family_bits.append(
                    f'{str(family_name).strip()} -> {", ".join(str(metric).strip() for metric in family_metrics[:3] if str(metric).strip())}'
                )
        if family_bits:
            parts.append("Comparison families: " + "; ".join(family_bits) + ".")

    comparison_preference_hints = reference_data.get("comparison_preference_hints") or {}
    if isinstance(comparison_preference_hints, dict) and comparison_preference_hints:
        default_family = str(comparison_preference_hints.get("default_improvement_family") or "").strip()
        default_metric = str(comparison_preference_hints.get("default_improvement_metric") or "").strip()
        if default_family or default_metric:
            preference_bits = []
            if default_family:
                preference_bits.append(f"default improvement family = {default_family}")
            if default_metric:
                preference_bits.append(f'default improvement metric = "{default_metric}"')
            parts.append("Comparison preference: " + "; ".join(preference_bits) + ".")

    comparison_clarify_hints = reference_data.get("comparison_clarify_hints") or {}
    if isinstance(comparison_clarify_hints, dict) and comparison_clarify_hints:
        clarify_summary = str(comparison_clarify_hints.get("summary") or "").strip()
        if clarify_summary:
            parts.append(f"Comparison clarify guidance: {clarify_summary}")

    comparison_examples = reference_data.get("comparison_examples") or []
    if isinstance(comparison_examples, list) and comparison_examples:
        cleaned_examples = [str(example).strip() for example in comparison_examples if str(example).strip()]
        if cleaned_examples:
            parts.append("Comparison examples: " + " | ".join(cleaned_examples[:3]))

    qualifier_hints = reference_data.get("qualifier_hints") or {}
    if isinstance(qualifier_hints, dict) and qualifier_hints:
        qualifier_bits = []
        for qualifier, meaning in list(qualifier_hints.items())[:6]:
            qualifier_text = str(qualifier).strip()
            meaning_text = str(meaning).strip()
            if qualifier_text and meaning_text:
                qualifier_bits.append(f"{qualifier_text} -> {meaning_text}")
        if qualifier_bits:
            parts.append("Qualifier guidance: " + "; ".join(qualifier_bits) + ".")

    relationship_language_hints = reference_data.get("relationship_language_hints") or {}
    relationship_summary = build_relationship_language_summary(relationship_language_hints)
    if relationship_summary:
        parts.append(relationship_summary)

    return "\n".join(parts)


def _pack_id_to_event_type(pack_id: str | None) -> str:
    normalized = str(pack_id or "").strip().lower()
    aliases = {
        "earthquakes": "earthquake",
        "tsunamis": "tsunami",
        "volcanoes": "volcano",
        "hurricanes": "hurricane",
        "tornadoes": "tornado",
        "floods": "flood",
        "wildfires": "wildfire",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized.endswith("ies") and len(normalized) > 3:
        return normalized[:-3] + "y"
    if normalized.endswith("s") and len(normalized) > 1:
        return normalized[:-1]
    return normalized


def _clean_string_list(value: object, *, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
            if limit is not None and len(cleaned) >= limit:
                break
    return cleaned


def _normalize_query_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _query_contains_any_phrase(query: str, phrases: object) -> bool:
    normalized_query = _normalize_query_text(query)
    if not normalized_query:
        return False
    for phrase in _clean_string_list(phrases):
        if _normalize_query_text(phrase) and _normalize_query_text(phrase) in normalized_query:
            return True
    return False


_GENERIC_EXACT_EVENT_PATTERNS = (
    re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE),
    re.compile(r"^(?:dfo|gfd)-\d+$", re.IGNORECASE),
    re.compile(r"^ts\d{4,}$", re.IGNORECASE),
    re.compile(r"^ve\d{4,}$", re.IGNORECASE),
    re.compile(r"^[A-Z]{2}\d{17,20}$", re.IGNORECASE),
    re.compile(r"^[A-Z]{2}(?:-[A-Z]{2})?-\d{4}-[A-Za-z0-9-]+$", re.IGNORECASE),
    re.compile(r"(?:irwin|mtbs|-fire-)", re.IGNORECASE),
)


def _query_looks_like_exact_event_reference(query: str) -> bool:
    normalized_query = _normalize_query_text(query)
    if not normalized_query:
        return False
    for token in normalized_query.split():
        for pattern in _GENERIC_EXACT_EVENT_PATTERNS:
            if pattern.search(token):
                return True
    return False


def _shared_disaster_relationship_reference() -> dict:
    data = load_reference_json("disaster_links.json")
    return data if isinstance(data, dict) else {}


def _shared_relationship_language_relationships() -> list[dict]:
    reference = _shared_disaster_relationship_reference()
    language_hints = reference.get("relationship_language_hints") or {}
    relationships = language_hints.get("relationships") or []
    return relationships if isinstance(relationships, list) else []


def _relationship_involves_pack(relationship: dict, pack_id: str) -> bool:
    normalized_pack_id = str(pack_id or "").strip().lower()
    if not normalized_pack_id:
        return False
    for side_name in ("side_a", "side_b"):
        side = relationship.get(side_name) or {}
        pack_ids = side.get("pack_ids") or []
        if isinstance(pack_ids, list):
            for candidate in pack_ids:
                if str(candidate or "").strip().lower() == normalized_pack_id:
                    return True
    pack_event_type = _pack_id_to_event_type(normalized_pack_id)
    for side_name in ("side_a", "side_b"):
        side = relationship.get(side_name) or {}
        if str(side.get("event_type") or "").strip().lower() == pack_event_type:
            return True
    return False


def _query_mentions_relationship_side(query: str, side: dict) -> bool:
    normalized_query = _normalize_query_text(query)
    if not normalized_query or not isinstance(side, dict):
        return False
    aliases = _clean_string_list(side.get("aliases"))
    event_type = str(side.get("event_type") or "").strip()
    if event_type:
        aliases.append(event_type)
    for alias in aliases:
        normalized_alias = _normalize_query_text(alias)
        if normalized_alias and normalized_alias in normalized_query:
            return True
    return False


def _relationship_query_match_kind(query: str, relationship: dict) -> str:
    side_a = relationship.get("side_a") or {}
    side_b = relationship.get("side_b") or {}
    mentions_a = _query_mentions_relationship_side(query, side_a)
    mentions_b = _query_mentions_relationship_side(query, side_b)
    if not (mentions_a and mentions_b):
        if _query_contains_any_phrase(query, relationship.get("a_to_b_phrases")):
            return "forward"
        if _query_contains_any_phrase(query, relationship.get("b_to_a_phrases")):
            return "reverse"
        if _query_contains_any_phrase(query, relationship.get("neutral_phrases")):
            return "neutral"
        return ""
    if _query_contains_any_phrase(query, relationship.get("b_to_a_phrases")):
        return "reverse"
    if _query_contains_any_phrase(query, relationship.get("a_to_b_phrases")):
        return "forward"
    if _query_contains_any_phrase(query, relationship.get("neutral_phrases")):
        return "neutral"
    normalized_query = _normalize_query_text(query)
    if any(token in normalized_query for token in ("linked", "links", "related", "relationship", "relationships")):
        return "neutral"
    return "mentioned_both"


def _not_paired_query_matches(query: str, relationship: dict) -> bool:
    side_a = relationship.get("side_a") or {}
    side_b = relationship.get("side_b") or {}
    if _query_mentions_relationship_side(query, side_a) and _query_mentions_relationship_side(query, side_b):
        return True
    return _query_contains_any_phrase(query, relationship.get("example_queries"))


def _build_not_paired_relationship_summary(not_paired_relationships: list[dict], *, pack_id: str | None = None) -> str:
    if not isinstance(not_paired_relationships, list) or not not_paired_relationships:
        return ""
    filtered_relationships = [relationship for relationship in not_paired_relationships if isinstance(relationship, dict)]
    if pack_id:
        filtered_relationships = [
            relationship
            for relationship in filtered_relationships
            if _relationship_involves_pack(relationship, pack_id)
        ]
    if not filtered_relationships:
        return ""

    bits: list[str] = []
    for relationship in filtered_relationships[:4]:
        side_a = relationship.get("side_a") or {}
        side_b = relationship.get("side_b") or {}
        side_a_type = str(side_a.get("event_type") or "").strip()
        side_b_type = str(side_b.get("event_type") or "").strip()
        if not side_a_type or not side_b_type:
            continue
        phrase_bits: list[str] = [f"{side_a_type} x {side_b_type}"]
        note = str(relationship.get("note") or "").strip()
        if note:
            phrase_bits.append(note)
        query_behavior = str(relationship.get("query_behavior") or "").strip().lower()
        if query_behavior == "state_not_published":
            phrase_bits.append("if asked, state that no published link family exists yet")
        example_queries = _clean_string_list(relationship.get("example_queries"), limit=2)
        if example_queries:
            phrase_bits.append("examples: " + " | ".join(example_queries))
        bits.append("; ".join(phrase_bits))
    if not bits:
        return ""
    return "Not-paired relationship guidance: " + " || ".join(bits) + "."


def build_query_specific_disaster_relationship_guidance(query: str | None, pack_id: str | None) -> str:
    normalized_query = _normalize_query_text(query)
    normalized_pack_id = str(pack_id or "").strip().lower()
    if not normalized_query or not normalized_pack_id:
        return ""

    reference = _shared_disaster_relationship_reference()
    language_hints = reference.get("relationship_language_hints") or {}
    relationships = language_hints.get("relationships") or []
    if isinstance(relationships, list):
        for relationship in relationships:
            if not isinstance(relationship, dict) or not _relationship_involves_pack(relationship, normalized_pack_id):
                continue
            match_kind = _relationship_query_match_kind(normalized_query, relationship)
            if not match_kind:
                continue
            side_a = relationship.get("side_a") or {}
            side_b = relationship.get("side_b") or {}
            side_a_type = str(side_a.get("event_type") or "").strip()
            side_b_type = str(side_b.get("event_type") or "").strip()
            if not side_a_type or not side_b_type:
                continue
            guidance_bits = [
                f"Relationship query resolution: this query matches the published {side_a_type} -> {side_b_type} family."
            ]
            if match_kind == "reverse":
                guidance_bits.append("The user phrased it in the reverse direction.")
                if str(relationship.get("reverse_query_behavior") or "").strip().lower() == "correct_and_continue_with_canonical_family":
                    guidance_bits.append(
                        f"Correct to the canonical {side_a_type} -> {side_b_type} direction and continue with the linked events."
                    )
                    guidance_bits.append(
                        f"Do not describe {side_b_type} -> {side_a_type} as a separately published reverse family."
                    )
                else:
                    guidance_bits.append("Clarify the canonical direction before proceeding.")
            else:
                guidance_bits.append("Treat this as a linked-events request against the existing published family.")
                guidance_bits.append(
                    f"Do not describe {side_b_type} -> {side_a_type} as a separately published reverse family."
                )
            if not _query_looks_like_exact_event_reference(normalized_query):
                guidance_bits.append(
                    "The user did not provide an exact event id. Do not attempt direct disaster-links event or chain execution yet."
                )
                guidance_bits.append(
                    "Clarify for an exact anchor event, or clarify for region/time if the user wants a broader view of the canonical family."
                )
            guidance_bits.append("Do not say this relationship family is absent.")
            guidance_bits.append("Do not fall back to unrelated separate-layer overlays unless the user asks for that instead.")
            return " ".join(guidance_bits)

    not_paired_relationships = language_hints.get("not_paired_relationships") or []
    if isinstance(not_paired_relationships, list):
        for relationship in not_paired_relationships:
            if not isinstance(relationship, dict) or not _relationship_involves_pack(relationship, normalized_pack_id):
                continue
            if not _not_paired_query_matches(normalized_query, relationship):
                continue
            side_a = relationship.get("side_a") or {}
            side_b = relationship.get("side_b") or {}
            side_a_type = str(side_a.get("event_type") or "").strip()
            side_b_type = str(side_b.get("event_type") or "").strip()
            if not side_a_type or not side_b_type:
                continue
            return (
                "Relationship query resolution: this query matches the not-paired "
                f"{side_a_type} x {side_b_type} family. State that no published cross-disaster link family exists "
                "in either direction today. Do not remap this query to a different published family."
            )
    return ""


def build_relationship_language_summary(language_hints: dict | None, *, pack_id: str | None = None) -> str:
    if not isinstance(language_hints, dict):
        return ""
    relationships = language_hints.get("relationships") or []
    if not isinstance(relationships, list) or not relationships:
        return ""
    if pack_id:
        relationships = [
            relationship
            for relationship in relationships
            if isinstance(relationship, dict) and _relationship_involves_pack(relationship, pack_id)
        ]
    else:
        relationships = [relationship for relationship in relationships if isinstance(relationship, dict)]
    if not relationships:
        return ""

    bits: list[str] = []
    for relationship in relationships[:3]:
        side_a = relationship.get("side_a") or {}
        side_b = relationship.get("side_b") or {}
        side_a_type = str(side_a.get("event_type") or "").strip()
        side_b_type = str(side_b.get("event_type") or "").strip()
        if not side_a_type or not side_b_type:
            continue
        phrase_bits: list[str] = [f"{side_a_type} -> {side_b_type}"]
        forward_phrases = _clean_string_list(relationship.get("a_to_b_phrases"), limit=2)
        if forward_phrases:
            phrase_bits.append("forward phrases: " + " | ".join(forward_phrases))
        neutral_phrases = _clean_string_list(relationship.get("neutral_phrases"), limit=2)
        if neutral_phrases:
            phrase_bits.append("neutral phrases: " + " | ".join(neutral_phrases))
        if bool(relationship.get("clarify_when_reversed")) and not bool(relationship.get("reverse_edge_supported")):
            reversed_phrases = _clean_string_list(relationship.get("b_to_a_phrases"), limit=2)
            if reversed_phrases:
                phrase_bits.append("reversed wording should clarify: " + " | ".join(reversed_phrases))
            else:
                phrase_bits.append("reversed wording should clarify")
            reverse_query_behavior = str(relationship.get("reverse_query_behavior") or "").strip().lower()
            if reverse_query_behavior == "correct_and_continue_with_canonical_family":
                phrase_bits.append("reverse wording should correct to the canonical direction and continue with linked events")
        example_queries = _clean_string_list(relationship.get("example_queries"), limit=2)
        if example_queries:
            phrase_bits.append("examples: " + " | ".join(example_queries))
        bits.append("; ".join(phrase_bits))
    if not bits:
        return ""
    return "Relationship language guidance: " + " || ".join(bits) + "."


def build_shared_disaster_relationship_guidance(pack_id: str | None) -> str:
    normalized_pack_id = str(pack_id or "").strip().lower()
    if not normalized_pack_id:
        return ""
    reference = _shared_disaster_relationship_reference()
    language_hints = reference.get("relationship_language_hints") or {}
    summary = build_relationship_language_summary(language_hints, pack_id=normalized_pack_id)
    not_paired_summary = _build_not_paired_relationship_summary(
        language_hints.get("not_paired_relationships") or [],
        pack_id=normalized_pack_id,
    )
    summary_bits = [bit for bit in (summary, not_paired_summary) if bit]
    if not summary_bits:
        return ""
    summary = "\n".join(summary_bits)

    metaquestion_examples = _clean_string_list(language_hints.get("metaquestion_examples"), limit=3)
    if metaquestion_examples:
        summary += "\nRelationship metaquestions: " + " | ".join(metaquestion_examples) + "."
    return summary
