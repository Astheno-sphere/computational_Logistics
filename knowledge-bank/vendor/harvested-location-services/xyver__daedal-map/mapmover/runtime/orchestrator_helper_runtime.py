"""Shared helper runtime for orchestrator-adjacent utility logic."""

from __future__ import annotations

from mapmover.foundation_helpers import load_runtime_explainer_helpers
from mapmover.runtime.orchestrator_result_cap import cap_runtime_payload
from mapmover.runtime.filter_primitives import normalize_sort_spec
from mapmover.runtime.warning_primitives import estimate_display_feature_count


def requested_limit_from_order(order: dict | None) -> int | None:
    if not isinstance(order, dict):
        return None
    items = order.get("items") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        sort_spec = normalize_sort_spec(item.get("sort")) or {}
        raw_limit = sort_spec.get("limit")
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            continue
        if limit > 0:
            return limit
    return None


def best_source_metadata(hints: dict, load_source_metadata_func) -> dict | None:
    candidate_ids: list[str] = []
    detected = hints.get("detected_source") or {}
    detected_source_id = str(detected.get("source_id") or "").strip()
    if detected_source_id:
        candidate_ids.append(detected_source_id)

    source_bundle = ((hints.get("candidates") or {}).get("sources") or {})
    best_candidate = source_bundle.get("best") or {}
    best_source_id = str(best_candidate.get("source_id") or "").strip()
    if best_source_id and best_source_id not in candidate_ids:
        candidate_ids.append(best_source_id)

    for candidate in source_bundle.get("candidates") or []:
        source_id = str((candidate or {}).get("source_id") or "").strip()
        if source_id and source_id not in candidate_ids:
            candidate_ids.append(source_id)

    for source_id in candidate_ids:
        metadata = load_source_metadata_func(source_id) or {}
        if isinstance(metadata, dict) and metadata:
            metadata.setdefault("source_id", source_id)
            return metadata
    return None


def resolve_result_source_id(result: dict) -> str:
    if not isinstance(result, dict):
        return ""
    return str(
        result.get("source_id")
        or result.get("dataset")
        or (((result.get("order") or {}).get("items") or [{}])[0].get("source_id"))
        or ""
    ).strip()


def apply_runtime_result_cap_to_payload_result(
    result: dict,
    *,
    confirmed_order: dict | None = None,
    load_source_metadata_func=None,
) -> dict:
    if not isinstance(result, dict) or load_source_metadata_func is None:
        return result
    source_id = resolve_result_source_id(result)
    if not source_id:
        return result
    precap_display_feature_count = estimate_display_feature_count(result)
    requested_limit = requested_limit_from_order(confirmed_order)
    payload, _cap_info = cap_runtime_payload(
        result,
        source_id=source_id,
        load_source_metadata_func=load_source_metadata_func,
        requested_limit=requested_limit,
    )
    if isinstance(payload, dict):
        payload["_precap_display_feature_count"] = int(precap_display_feature_count)
    return payload


def maybe_build_explainer_chat_response(
    *,
    query: str,
    hints: dict | None,
    build_chat_response_func,
    auth_user: dict | None = None,
    load_source_metadata_func=None,
    load_source_reference_func=None,
    lane: str | None = None,
) -> dict | None:
    if load_source_metadata_func is None:
        return None
    helper = load_runtime_explainer_helpers()
    build_explainer_response_func = helper["build_explainer_response"]

    source_metadata = best_source_metadata(hints or {}, load_source_metadata_func)
    if not source_metadata:
        return None

    source_reference = None
    if load_source_reference_func is not None:
        source_id = str(source_metadata.get("source_id") or "").strip()
        if source_id:
            source_reference = load_source_reference_func(source_id)

    if lane:
        explainer = build_explainer_response_func(source_metadata, query, source_reference, lane=lane)
    else:
        # Preserve the small helper seam used by existing lane-specific tests
        # and third-party orchestrators that still accept the original
        # three-argument callback.
        explainer = build_explainer_response_func(source_metadata, query, source_reference)
    if not isinstance(explainer, dict):
        return None

    return build_chat_response_func(
        explainer.get("text") or "I can describe that source, but I do not have a fuller summary yet.",
        auth_user=auth_user,
        source_id=explainer.get("source_id"),
        pack_id=explainer.get("pack_id"),
        explainer_sections=explainer.get("sections"),
        stub_order=explainer.get("stub_order"),
    )
