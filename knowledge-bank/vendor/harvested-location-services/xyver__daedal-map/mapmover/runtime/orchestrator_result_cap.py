"""Shared runtime result-cap helpers for lane orchestrators."""

from __future__ import annotations

from mapmover.foundation_helpers import load_runtime_result_cap_helpers
from mapmover.runtime.result_cap import cap_payload_for_source


def cap_runtime_payload(
    payload: dict,
    *,
    source_id: str,
    load_source_metadata_func,
    requested_limit: int | None = None,
):
    helper = load_runtime_result_cap_helpers()
    return cap_payload_for_source(
        payload,
        source_id=source_id,
        load_source_metadata_func=load_source_metadata_func,
        requested_limit=requested_limit,
        cap_payload_func=helper["apply_runtime_feature_cap_to_payload"],
    )


def cap_runtime_result_field(
    result: dict,
    *,
    field_name: str,
    source_id: str,
    load_source_metadata_func,
    requested_limit: int | None = None,
) -> tuple[dict, dict | None]:
    if not isinstance(result, dict):
        return result, None
    payload = result.get(field_name)
    if not isinstance(payload, dict):
        return result, None
    capped_payload, cap_info = cap_runtime_payload(
        payload,
        source_id=source_id,
        load_source_metadata_func=load_source_metadata_func,
        requested_limit=requested_limit,
    )
    next_result = dict(result)
    next_result[field_name] = capped_payload
    return next_result, cap_info


def cap_runtime_result_list_field(
    result: dict,
    *,
    field_name: str,
    source_id_func,
    load_source_metadata_func,
) -> tuple[dict, list[dict]]:
    if not isinstance(result, dict):
        return result, []
    payloads = result.get(field_name)
    if not isinstance(payloads, list):
        return result, []

    capped_payloads = []
    cap_infos: list[dict] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            capped_payloads.append(payload)
            continue
        source_id = str(source_id_func(payload, result) or "").strip()
        capped_payload, cap_info = cap_runtime_payload(
            payload,
            source_id=source_id,
            load_source_metadata_func=load_source_metadata_func,
        )
        capped_payloads.append(capped_payload)
        if cap_info:
            cap_infos.append(cap_info)

    next_result = dict(result)
    next_result[field_name] = capped_payloads
    return next_result, cap_infos
