"""Formulaic publication contract for the public data-tool universe.

Geometry tools intentionally remain outside this module because their richer,
tool-specific result shapes are owned by ``mcp_geometry_contract_shared``.
Both universes share the same access, help, and typed-error conventions.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tool_access_shared import (
    tool_account_item_limit,
    tool_capability_id,
    tool_family,
    tool_free_item_limit,
    tool_meter,
    tool_paid_item_limit,
    tool_price_micro_usd,
    tool_pricing,
    tool_pricing_version,
)


DATA_DISCOVERY_TOOL_IDS = frozenset({"get_catalog", "get_pack"})
DATA_QUERY_TOOL_IDS = frozenset({
    "get_data",
})
DATA_LIVE_TOOL_IDS = frozenset({"get_live_earthquake_events", "get_live_volcano_events"})
DATA_RELATIONSHIP_TOOL_IDS = frozenset({
    "get_event",
})
DATA_TOOL_IDS = frozenset().union(
    DATA_DISCOVERY_TOOL_IDS,
    DATA_QUERY_TOOL_IDS,
    DATA_LIVE_TOOL_IDS,
    DATA_RELATIONSHIP_TOOL_IDS,
)

DATA_TOOL_DESCRIPTIONS = {
    "get_catalog": "Discover data packs or geometry families progressively: lite selection, full metric/query inventory, or a raw catalog download URL. Choose one result and call get_pack next.",
    "get_pack": "Inspect one selected data pack or geometry family progressively: lite starter contract, full MCP query metadata, or a raw metadata download URL. Use its next_step to retrieve data or call the preferred geometry tool.",
    "get_data": "Retrieve rows from one selected published data pack using exact metrics, loc_id-based region filters, time/metric filters, sorting, and a row limit. Disaster event rows include stable event_id values for get_event drill-down. A parent administrative loc_id selects matching descendant rows at the pack's published grain. Call get_pack first; geometry families use their focused next-step tools.",
    "get_live_earthquake_events": "Fetch recent preliminary USGS earthquake events in the shared data-result shape. Use get_data with pack_id='earthquakes' for canonical enriched history.",
    "get_live_volcano_events": "Fetch recent preliminary Smithsonian/GVP eruption updates in the shared data-result shape. Use get_data with pack_id='volcanoes' for canonical history.",
    "get_event": "Retrieve one exact disaster event and explicitly requested relationships, affected places, native observations, or geometry. Use get_data to obtain the stable event_id first.",
}

_ERROR_PROPERTY = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "message": {"type": "string"},
        "details": {"type": "object"},
        "retry_hint": {"type": "string"},
    },
    "required": ["code", "message"],
    "additionalProperties": True,
}

_NEXT_STEP_PROPERTY = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "url": {"type": "string"},
        "tool": {"type": "string"},
        "arguments": {"type": "object"},
    },
    "anyOf": [{"required": ["action"]}, {"required": ["tool"]}],
    "additionalProperties": True,
}

_COMMON_PROPERTIES: dict[str, Any] = {
    "request_id": {"type": ["string", "null"]},
    "error": _ERROR_PROPERTY,
    "reason": {"type": "string"},
    "next_step": _NEXT_STEP_PROPERTY,
    "warnings": {"type": "array", "items": {"type": "object"}},
    "guidance": {"type": "object"},
    "clarification": {"type": "object"},
    "provenance": {"type": "object"},
}


def _result_schema(*, success_required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {**deepcopy(_COMMON_PROPERTIES), **deepcopy(properties)},
        "anyOf": [
            {"required": list(success_required)},
            {"required": ["error"]},
        ],
        "additionalProperties": True,
    }


def data_tool_output_schema(tool_name: str) -> dict[str, Any] | None:
    name = str(tool_name or "").strip()
    if name in DATA_QUERY_TOOL_IDS | DATA_LIVE_TOOL_IDS:
        return _result_schema(
            success_required=["source_id", "row_count", "rows"],
            properties={
                "capability_id": {"type": "string"},
                "pack_id": {"type": "string"},
                "source_id": {"type": "string"},
                "query_mode": {"type": "string"},
                "filters_applied": {"type": "object"},
                "sort": {"type": "array"},
                "limit": {"type": "integer"},
                "row_count": {"type": "integer", "minimum": 0},
                "truncated": {"type": "boolean"},
                "rows": {"type": "array", "items": {"type": "object"}},
            },
        )
    if name == "get_catalog":
        return _result_schema(
            success_required=["catalog", "detail"],
            properties={
                "catalog": {"type": "string", "enum": ["data", "geometry"]},
                "detail": {"type": "string", "enum": ["lite", "full", "download"]},
                "catalog_version": {"type": "string"},
                "generated_at": {"type": ["string", "null"]},
                "pack_count": {"type": "integer", "minimum": 0},
                "packs": {"type": "array", "items": {"type": "object"}},
                "tool_families": {"type": "array", "items": {"type": "object"}},
                "download_url": {"type": "string"},
            },
        )
    if name == "get_pack":
        return _result_schema(
            success_required=["catalog", "pack_id", "detail"],
            properties={
                "catalog": {"type": "string", "enum": ["data", "geometry"]},
                "pack_id": {"type": "string"},
                "detail": {"type": "string", "enum": ["lite", "full", "download"]},
                "sources": {"type": "array", "items": {"type": "object"}},
                "material_policy": {"type": "object"},
                "download_url": {"type": "string"},
                "full_call": {"type": "object"},
                "download_call": {"type": "object"},
            },
        )
    if name in DATA_RELATIONSHIP_TOOL_IDS:
        return _result_schema(
            success_required=["event_id", "pack_id", "event"],
            properties={
                "event_id": {"type": "string"},
                "pack_id": {"type": "string"},
                "source_id": {"type": "string"},
                "event_type": {"type": "string"},
                "schema_class": {"type": "string"},
                "event": {"type": "object"},
                "available": {"type": "object"},
                "included": {"type": "array", "items": {"type": "string"}},
                "relationships": {"type": "object"},
                "affected_places": {"type": "object"},
                "observations": {"type": "object"},
                "geometry": {"type": "object"},
                "next_steps": {"type": "object"},
            },
        )
    return None


def data_tool_publication_meta(tool_name: str) -> dict[str, Any] | None:
    name = str(tool_name or "").strip()
    if name not in DATA_TOOL_IDS:
        return None
    pricing = tool_pricing(name)
    limits = {
        "free": tool_free_item_limit(name),
        "account": tool_account_item_limit(name),
        "paid": tool_paid_item_limit(name),
    }
    access: dict[str, Any] = {
        "contract_version": "1.0.0",
        "capability_id": tool_capability_id(name),
        "family": tool_family(name),
        "pricing": pricing,
        "limits": {key: value for key, value in limits.items() if value is not None},
        "help": {"tool": "get_tool_help", "arguments": {"tool_name": name}},
    }
    if pricing == "by_pack":
        access["pricing_authority"] = {"tool": "get_catalog", "field": "packs[].material_policy"}
    else:
        access["meter"] = tool_meter(name)
        access["pricing_version"] = tool_pricing_version(name)
        access["price_micro_usd"] = tool_price_micro_usd(name)
    if name in DATA_DISCOVERY_TOOL_IDS:
        result_family = "catalog"
        input_family = "none" if name == "get_catalog" else "pack_selector"
    elif name in DATA_QUERY_TOOL_IDS | DATA_LIVE_TOOL_IDS:
        result_family = "rows"
        input_family = "structured_query" if name in DATA_QUERY_TOOL_IDS else "live_window"
    else:
        result_family = "relationships"
        input_family = "exact_event"
    return {
        "com.daedalmap/access": access,
        "com.daedalmap/data-contract": {
            "contract_version": "1.0.0",
            "input_family": input_family,
            "result_family": result_family,
            "canonical_help_tool": "get_tool_help",
        },
    }


def decorate_data_tool_definition(definition: dict[str, Any]) -> dict[str, Any]:
    """Attach the shared data publication contract without touching geometry."""
    name = str(definition.get("name") or "").strip()
    if name not in DATA_TOOL_IDS:
        return definition
    decorated = deepcopy(definition)
    decorated["description"] = DATA_TOOL_DESCRIPTIONS[name]
    decorated["outputSchema"] = data_tool_output_schema(name)
    decorated["annotations"] = {
        **(decorated.get("annotations") if isinstance(decorated.get("annotations"), dict) else {}),
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": name in DATA_LIVE_TOOL_IDS,
    }
    decorated["_meta"] = {
        **(decorated.get("_meta") if isinstance(decorated.get("_meta"), dict) else {}),
        **(data_tool_publication_meta(name) or {}),
    }
    return decorated


def decorate_shared_help_definition(definition: dict[str, Any]) -> dict[str, Any]:
    """Publish the free help convention that sits above both universes."""
    if str(definition.get("name") or "").strip() != "get_tool_help":
        return definition
    decorated = deepcopy(definition)
    decorated["description"] = (
        "Describe one tool visible on this facade, including its exact contract, "
        "or return a bounded workflow overview for one supported topic."
    )
    decorated["outputSchema"] = _result_schema(
        success_required=["ok", "tool_name"],
        properties={
            "ok": {"type": "boolean"},
            "tool_name": {"type": "string"},
            "title": {"type": ["string", "null"]},
            "purpose": {"type": "string"},
            "input_schema": {"type": "object"},
            "access": {"type": "object"},
            "examples": {"type": "array"},
            "important_output_fields": {"type": "array"},
            "recommended_next_calls": {"type": "array"},
        },
    )
    decorated["annotations"] = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    decorated["_meta"] = {
        "com.daedalmap/help": {
            "contract_version": "1.0.0",
            "scope": "current_facade",
            "discovery_predecessor": "tools/list",
            "access": "free",
        }
    }
    return decorated


def normalize_data_tool_error(
    tool_name: str,
    payload: Any,
    *,
    status_code: int | None = None,
) -> dict[str, Any]:
    """Give every data-tool denial one branchable error and next step."""
    normalized = dict(payload) if isinstance(payload, dict) else {}
    raw_error = normalized.get("error")
    if isinstance(raw_error, dict):
        error = dict(raw_error)
    else:
        error = {"message": str(raw_error or payload or "Data tool request failed.")}
    status = int(status_code or 0)
    default_codes = {
        400: "invalid_request",
        401: "authentication_required",
        402: "payment_required",
        403: "permission_required",
        404: "not_found",
        429: "rate_limit_exceeded",
    }
    code = str(error.get("code") or default_codes.get(status) or "data_tool_failed")
    error["code"] = code
    error["message"] = str(error.get("message") or "Data tool request failed.")
    normalized["error"] = error
    normalized["reason"] = code

    pack_id = str(normalized.get("pack_id") or "").strip()

    if status == 401:
        next_step = {"action": "sign_in", "url": "https://www.daedalmap.com/login"}
    elif status == 402:
        next_step = {"action": "choose_payment", "url": "https://www.daedalmap.com/account?tab=payments"}
    elif status == 403:
        next_step = {"action": "check_mcp_key_permissions", "url": "https://www.daedalmap.com/account?tab=agents"}
    elif status == 429:
        next_step = {"action": "retry_after_delay"}
    elif code in {"metric_not_available", "multi_source_not_supported"} and pack_id:
        if code == "multi_source_not_supported":
            error["retry_hint"] = (
                "Call get_pack with detail='full', then retry get_data with a metric subset "
                "that belongs to one published source. get_data does not accept source_id."
            )
        next_step = {
            "action": "inspect_pack_query_contract",
            "tool": "get_pack",
            "arguments": {"pack_id": pack_id, "detail": "full"},
        }
    elif code in {"unknown_source", "pack_not_found"}:
        next_step = {
            "action": "refresh_catalog",
            "tool": "get_catalog",
            "arguments": {"catalog": "data", "detail": "lite"},
        }
    elif code == "event_not_found" and pack_id:
        next_step = {
            "action": "find_current_event_id",
            "tool": "get_pack",
            "arguments": {"pack_id": pack_id, "detail": "lite"},
        }
    else:
        next_step = {
            "action": "review_tool_contract",
            "tool": "get_tool_help",
            "arguments": {"tool_name": str(tool_name or "")},
        }
    normalized["next_step"] = next_step
    return normalized
