"""Shared result-cap helper for order-execution paths.

Every order-execution path (event, metrics, aggregate, location_shape, layered)
should run its rendered DataFrame through `apply_runtime_result_cap` before
handing it to the response builder. The helper enforces a row cap, returns a
structured `cap_info` block when the cap is hit. This helper is a technical
truncation guard, not the broad user-facing display-warning gate.

See: county-map-private/docs/future/runtime_and_lane_unification_plan.md
section "Recently Identified Shared Helper Gaps" for the migration order and
call-site inventory.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional, Tuple


DEFAULT_RENDER_CAP = 5000
MAX_RENDER_CAP = 5000


def _read_metadata_cap(source_metadata: Any, key: str, default: int) -> int:
    """Read a positive integer cap from `runtime.<key>` in source metadata.

    Falls back to the default if the metadata block is missing, malformed, or
    specifies a non-positive value.
    """
    if not isinstance(source_metadata, dict):
        return default
    runtime_block = source_metadata.get("runtime")
    if not isinstance(runtime_block, dict):
        return default
    raw = runtime_block.get(key)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def apply_runtime_result_cap(
    df: Any,
    source_metadata: Optional[dict] = None,
    requested_limit: Optional[int] = None,
) -> Tuple[Any, Optional[dict]]:
    """Cap a result DataFrame and return `(df_capped, cap_info)`.

    The cap value is the minimum of:
      - `requested_limit` if positive
      - `runtime.default_render_cap` from source metadata (default 1000)
      - `runtime.max_render_cap` from source metadata (default 5000)

    `cap_info` is None when the cap was not hit. When the cap is hit it is a
    dict with: `cap_hit, returned_rows, available_rows, cap_value, cap_reason,
    cap_kind`.

    The DataFrame is sliced via `.head(cap_value)` so callers should sort
    before calling if order matters. If `df` is None or has no `__len__`, the
    helper returns `(df, None)` unchanged.
    """
    if df is None:
        return df, None
    try:
        available_rows = len(df)
    except TypeError:
        return df, None

    default_cap = _read_metadata_cap(source_metadata, "default_render_cap", DEFAULT_RENDER_CAP)
    max_cap = _read_metadata_cap(source_metadata, "max_render_cap", MAX_RENDER_CAP)

    cap_value = min(default_cap, max_cap)
    cap_reason = "runtime.default_render_cap"
    if requested_limit is not None:
        try:
            requested_int = int(requested_limit)
        except (TypeError, ValueError):
            requested_int = 0
        if requested_int > 0:
            bounded = min(requested_int, max_cap)
            cap_value = bounded
            cap_reason = "requested_limit" if requested_int <= max_cap else "runtime.max_render_cap"

    if available_rows <= cap_value:
        if isinstance(source_metadata, dict):
            prefilter_cap_info = source_metadata.get("_runtime_prefilter_cap_info")
            if isinstance(prefilter_cap_info, dict) and prefilter_cap_info.get("cap_hit"):
                return df, prefilter_cap_info
        return df, None

    try:
        df_capped = df.head(cap_value)
    except AttributeError:
        df_capped = df[:cap_value]

    cap_info = {
        "cap_hit": True,
        "returned_rows": cap_value,
        "available_rows": available_rows,
        "cap_value": cap_value,
        "cap_reason": cap_reason,
        "cap_kind": "technical_truncation",
    }
    return df_capped, cap_info


def merge_cap_info(*infos: Optional[dict]) -> Optional[dict]:
    """Combine multiple `cap_info` blocks for layered/multi-item orders.

    Returns the most restrictive cap encountered, with `available_rows` summed
    across inputs so a layered order can report the total drop. Returns None
    when no inputs report a hit.
    """
    hits = [info for info in infos if isinstance(info, dict) and info.get("cap_hit")]
    if not hits:
        return None
    total_available = 0
    returned_rows = 0
    cap_value = None
    cap_reason = "merged"
    cap_kind = "technical_truncation"
    for info in hits:
        total_available += int(info.get("available_rows") or 0)
        returned_rows += int(info.get("returned_rows") or 0)
        candidate_cap = info.get("cap_value")
        if isinstance(candidate_cap, int) and (cap_value is None or candidate_cap < cap_value):
            cap_value = candidate_cap
            cap_reason = info.get("cap_reason") or cap_reason
        candidate_kind = str(info.get("cap_kind") or "").strip()
        if candidate_kind:
            cap_kind = candidate_kind
    return {
        "cap_hit": True,
        "returned_rows": returned_rows,
        "available_rows": total_available,
        "cap_value": cap_value,
        "cap_reason": cap_reason,
        "cap_kind": cap_kind,
    }


def build_cap_info_from_counts(
    *,
    returned_rows: int,
    available_rows: int,
    cap_value: int | None = None,
    cap_reason: str = "requested_limit",
    cap_kind: str = "technical_truncation",
) -> Optional[dict]:
    """Build normalized cap info from explicit row counts.

    Use this when callers already know total matched rows and returned rows but
    are not flowing through the DataFrame-based cap helper.
    """
    returned_rows = max(0, int(returned_rows))
    available_rows = max(0, int(available_rows))
    if available_rows <= returned_rows:
        return None
    if cap_value is None:
        cap_value = returned_rows
    return {
        "cap_hit": True,
        "returned_rows": returned_rows,
        "available_rows": available_rows,
        "cap_value": int(cap_value),
        "cap_reason": cap_reason,
        "cap_kind": str(cap_kind or "technical_truncation"),
    }


def apply_runtime_feature_cap_to_payload(
    payload: Any,
    source_metadata: Optional[dict] = None,
    requested_limit: Optional[int] = None,
) -> tuple[Any, Optional[dict]]:
    """Cap `geojson.features` on a result/display payload.

    Returns `(payload_capped, cap_info)`. If the payload has no feature list,
    it is returned unchanged with `cap_info=None`.
    """
    if not isinstance(payload, dict):
        return payload, None
    geojson = payload.get("geojson")
    if not isinstance(geojson, dict):
        return payload, None
    features = geojson.get("features")
    if not isinstance(features, list):
        return payload, None

    capped_features, cap_info = apply_runtime_result_cap(
        features,
        source_metadata=source_metadata,
        requested_limit=requested_limit,
    )
    if cap_info is None:
        return payload, None

    next_payload = deepcopy(payload)
    next_geojson = dict(next_payload.get("geojson") or {})
    next_geojson["features"] = list(capped_features)
    next_payload["geojson"] = next_geojson
    next_payload["truncated"] = True
    next_payload = apply_cap_info_to_payload(next_payload, cap_info)
    return next_payload, cap_info


def apply_cap_info_to_payload(payload: Any, cap_info: Optional[dict]) -> Any:
    """Attach normalized cap/truncation fields to a response payload.

    This keeps the shared output contract aligned across Explore, Research,
    metrics responses, and any future orchestrator wrappers.
    """
    if not isinstance(payload, dict):
        return payload
    if not isinstance(cap_info, dict) or not cap_info:
        return payload

    next_payload = payload
    next_payload["cap_info"] = cap_info
    next_payload["truncated"] = bool(cap_info.get("cap_hit"))
    next_payload.setdefault("available_count", cap_info.get("available_rows"))
    next_payload.setdefault("returned_count", cap_info.get("returned_rows"))
    return next_payload


def copy_cap_fields_to_payload(payload: Any, source_payload: Any) -> Any:
    """Copy normalized cap fields from one payload/result dict onto another."""
    if not isinstance(payload, dict) or not isinstance(source_payload, dict):
        return payload
    cap_info = source_payload.get("cap_info")
    if not isinstance(cap_info, dict) or not cap_info:
        return payload

    next_payload = dict(payload)
    if source_payload.get("available_count") is not None:
        next_payload["available_count"] = source_payload.get("available_count")
    if source_payload.get("returned_count") is not None:
        next_payload["returned_count"] = source_payload.get("returned_count")
    if source_payload.get("truncated") is not None:
        next_payload["truncated"] = bool(source_payload.get("truncated"))
    return apply_cap_info_to_payload(next_payload, cap_info)


def apply_row_count_cap_to_payload(
    payload: Any,
    *,
    rows_key: str = "rows",
    row_count_key: str = "row_count",
    cap_reason: str = "requested_limit",
) -> Any:
    """Attach shared cap fields to row-based payloads when rows are truncated."""
    if not isinstance(payload, dict):
        return payload
    rows = payload.get(rows_key)
    if not isinstance(rows, list):
        return payload
    try:
        available_rows = int(payload.get(row_count_key) or 0)
    except (TypeError, ValueError):
        return payload
    cap_info = build_cap_info_from_counts(
        returned_rows=len(rows),
        available_rows=available_rows,
        cap_reason=cap_reason,
    )
    return apply_cap_info_to_payload(payload, cap_info)


def cap_payload_for_source(
    payload: Any,
    *,
    source_id: Any,
    load_source_metadata_func,
    requested_limit: Optional[int] = None,
    cap_payload_func=None,
) -> tuple[Any, Optional[dict]]:
    """Cap a result/display payload using the metadata for one source.

    This centralizes the shared orchestrator behavior:
    - normalize source_id
    - load source metadata if available
    - apply the feature-cap helper
    """
    if cap_payload_func is None:
        cap_payload_func = apply_runtime_feature_cap_to_payload

    normalized_source_id = str(source_id or "").strip()
    source_metadata = (
        load_source_metadata_func(normalized_source_id) or {}
        if normalized_source_id and load_source_metadata_func is not None
        else {}
    )
    return cap_payload_func(
        payload,
        source_metadata=source_metadata,
        requested_limit=requested_limit,
    )
