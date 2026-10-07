"""Shared normalization helpers for machine-facing API/MCP contracts."""

from __future__ import annotations

import re
from typing import Any

from mapmover.data_loading import load_source_metadata
from mapmover.runtime.geography_reference import (
    load_conversions,
    load_iso_codes,
    load_usa_admin,
    resolve_country_subdivision_slug_loc_id,
)
from mapmover.runtime.region_expansion import expand_region as expand_runtime_region
from mapmover.runtime.geometry_catalog import (
    expand_geometry_loc_id,
    is_deprecated_geometry_loc_id,
    is_known_geometry_loc_id,
)
from mapmover.runtime.source_hints import get_single_metric_default


REGION_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_]{0,29}$")
LOC_IDISH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_country_subdivision_slug_cache: dict[tuple[str, str], str | None] = {}


def _normalize_machine_region_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    if "-" in text:
        parts = [segment for segment in text.split("-") if segment]
        if len(parts) >= 3 and len(parts[0]) == 3 and parts[0].isalpha():
            return "-".join([parts[0].upper(), *parts[1:]])

    return text


def _expand_machine_region_token(value: str) -> list[str]:
    normalized = _normalize_machine_region_token(value)
    if not normalized:
        return []

    if is_deprecated_geometry_loc_id(normalized):
        return []

    if is_known_geometry_loc_id(normalized):
        return expand_geometry_loc_id(normalized)

    if normalized.isupper() and len(normalized) == 3 and normalized.isalpha():
        iso3_to_name = (load_iso_codes() or {}).get("iso3_to_name", {})
        if normalized in iso3_to_name:
            return [normalized]
        return []

    if not LOC_IDISH_RE.match(normalized):
        return []

    expanded = expand_runtime_region(
        normalized,
        resolve_country_subdivision_slug_loc_id_func=lambda region: resolve_country_subdivision_slug_loc_id(
            region,
            cache_dict=_country_subdivision_slug_cache,
        ),
        regional_groups={},
        load_conversions_func=load_conversions,
        load_iso_codes_func=load_iso_codes,
        load_usa_admin_func=load_usa_admin,
    )
    if expanded:
        normalized_values: list[str] = []
        for item in sorted(expanded):
            item_text = _normalize_machine_region_token(item)
            if item_text and item_text not in normalized_values:
                normalized_values.append(item_text)
        return normalized_values

    if "-" in normalized and len(normalized.split("-", 1)[0]) == 3:
        return [normalized.upper()]

    return []


def normalize_machine_region_ids(region_ids: Any) -> tuple[list[str] | None, str | None]:
    """Normalize machine-lane region filters through the shared geography seam.

    This keeps canonical execution ids strict while allowing shared geography
    concepts such as subdivision slug aliases and regional group expansion.
    """
    if region_ids and (not isinstance(region_ids, list) or any(not str(value).strip() for value in region_ids)):
        return None, "region_ids must be a non-empty list of ids."

    normalized_region_ids: list[str] = []
    seen_region_ids: set[str] = set()
    for value in region_ids or []:
        expanded_values = _expand_machine_region_token(str(value))
        if not expanded_values:
            return None, f"region_id '{value}' is not recognized."
        for expanded in expanded_values:
            if expanded not in seen_region_ids:
                seen_region_ids.add(expanded)
                normalized_region_ids.append(expanded)

    return normalized_region_ids, None


def normalize_machine_metrics(spec: Any, metrics: Any) -> tuple[list[str] | None, str | None, dict[str, Any] | None]:
    """Normalize machine-lane metrics through shared source metadata defaults."""
    normalized_metrics = [str(metric).strip() for metric in (metrics or []) if str(metric).strip()]
    if normalized_metrics:
        return normalized_metrics, None, None

    available_metric_ids = [
        str(metric_id).strip()
        for metric_id in getattr(spec, "metrics", {}).keys()
        if str(metric_id).strip()
    ]
    metadata_source_id = str(getattr(spec, "metadata_source_id", None) or getattr(spec, "source_id", "")).strip()
    metadata = load_source_metadata(metadata_source_id) or {}
    default_metric = get_single_metric_default(metadata)
    available_metrics = sorted(available_metric_ids)

    if str(getattr(spec, "query_mode", "") or "").strip() == "single_source_events" and "event_count" in getattr(spec, "metrics", {}):
        return ["event_count"], None, None

    non_count_metrics = [metric_id for metric_id in available_metric_ids if metric_id != "event_count"]
    if len(non_count_metrics) == 1:
        return [non_count_metrics[0]], None, None

    if default_metric and default_metric in getattr(spec, "metrics", {}):
        return [default_metric], None, None

    return None, "At least one valid metric is required.", {"available_metrics": available_metrics}
