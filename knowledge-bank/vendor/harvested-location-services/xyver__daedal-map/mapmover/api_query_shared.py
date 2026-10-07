from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def get_api_analytics_metadata(
    req: Request,
    *,
    request_fingerprint: str | None = None,
    query_scope: dict[str, Any] | None = None,
    access_lane: str | None = None,
) -> dict[str, Any]:
    existing = getattr(req.state, "analytics_metadata", None)
    metadata = dict(existing) if isinstance(existing, dict) else {}
    metadata.setdefault("surface", getattr(req.state, "analytics_surface", None) or "agent_api")
    if access_lane:
        metadata["access_lane"] = access_lane
    if request_fingerprint:
        metadata["request_fingerprint"] = request_fingerprint
    if query_scope:
        metadata["query_scope"] = query_scope
    req.state.analytics_metadata = metadata
    return metadata


def json_safe_value(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def build_api_error_response(
    request_id: str | None,
    code: str,
    message: str,
    status_code: int,
    *,
    details: dict[str, Any] | None = None,
    retry_hint: str | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details:
        payload["error"]["details"] = details
    if retry_hint:
        payload["error"]["retry_hint"] = retry_hint
    return JSONResponse(payload, status_code=status_code)


def normalize_api_request_id(payload: dict[str, Any]) -> str | None:
    request_id = payload.get("request_id")
    if request_id is None:
        return f"api-{uuid.uuid4().hex[:12]}"
    request_id = str(request_id).strip()
    return request_id or f"api-{uuid.uuid4().hex[:12]}"


def canonical_request_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): canonical_request_value(value[key])
            for key in sorted(value.keys(), key=lambda item: str(item))
        }
    if isinstance(value, list):
        return [canonical_request_value(item) for item in value]
    if isinstance(value, tuple):
        return [canonical_request_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def canonical_compare_filters(compare_filters: list[tuple[str, str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for field_name, op, value in compare_filters:
        normalized.append(
            {
                "field": str(field_name),
                "op": str(op),
                "value": canonical_request_value(value),
            }
        )
    normalized.sort(
        key=lambda item: (
            item["field"],
            item["op"],
            json.dumps(item["value"], ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        )
    )
    return normalized


def build_request_fingerprint_payload(
    *,
    source_id: str,
    pack_id: str,
    query_mode: str,
    metrics: list[str],
    normalized_region_ids: list[str],
    normalized_time: dict[str, Any],
    equals_filters: dict[str, Any],
    compare_filters: list[tuple[str, str, Any]],
    normalized_sort: list[dict[str, str]],
    limit: int,
    output_format: str,
) -> dict[str, Any]:
    return {
        "capability_id": "dataset_query",
        "source_id": source_id,
        "pack_id": pack_id,
        "query_mode": query_mode,
        "metrics": sorted(str(metric) for metric in metrics),
        "filters": {
            "region_ids": sorted(str(region_id) for region_id in normalized_region_ids),
            "time": canonical_request_value(normalized_time),
            "equals": canonical_request_value(equals_filters),
            "compare": canonical_compare_filters(compare_filters),
        },
        "sort": canonical_request_value(normalized_sort),
        "limit": int(limit),
        "output_format": str(output_format),
    }


def request_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        canonical_request_value(payload),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
