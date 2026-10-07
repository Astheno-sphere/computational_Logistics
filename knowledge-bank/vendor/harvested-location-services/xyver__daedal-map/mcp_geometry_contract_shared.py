"""Publication contract for the public MCP geometry-tool universe.

The geometry runtime intentionally returns richer, tool-specific objects than
the row-oriented data tools.  These schemas therefore lock the stable routing
and result fields while allowing country- and family-specific enrichment.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from mcp_tool_help_shared import blind_caller_publication_guidance
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


GEOMETRY_TOOL_IDS = frozenset({
    "resolve_point",
    "resolve_deep_point",
    "get_loc_id_info",
    "identify_dataset_geography",
    "identify_reference_system",
    "convert_reference",
    "compare_geographies",
    "get_geometry",
})

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
    "batch_id": {"type": ["string", "null"]},
    "ok": {"type": "boolean"},
    "error": _ERROR_PROPERTY,
    "reason": {"type": "string"},
    "next_step": _NEXT_STEP_PROPERTY,
    "warnings": {"type": "array", "items": {"type": "object"}},
    "guidance": {"type": "object"},
    "clarification": {"type": "object"},
    "meter_receipt": {"type": "object"},
    "settlement_receipt": {"type": "object"},
}

_POINT = {
    "anyOf": [
        {
            "type": "object",
            "properties": {
                "lat": {"type": "number"},
                "lon": {"type": "number"},
            },
            "required": ["lat", "lon"],
            "additionalProperties": True,
        },
        {"type": "null"},
    ]
}

_RESULT_ITEM = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "error": _ERROR_PROPERTY,
        "row_index": {"type": ["string", "integer", "null"]},
        "id": {"type": ["string", "integer", "null"]},
    },
    "additionalProperties": True,
}


def _result_schema(
    *,
    success_variants: list[list[str]],
    properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {**deepcopy(_COMMON_PROPERTIES), **deepcopy(properties)},
        "anyOf": [
            *({"required": list(required)} for required in success_variants),
            {"required": ["error"]},
        ],
        "additionalProperties": True,
    }


def geometry_tool_output_schema(tool_name: str) -> dict[str, Any] | None:
    """Return the stable success/error envelope for one geometry tool."""
    name = str(tool_name or "").strip()
    if name in {"resolve_point", "resolve_deep_point"}:
        return _result_schema(
            success_variants=[
                ["point", "stack"],
                ["point", "family", "family_result"],
                ["point_count", "results"],
            ],
            properties={
                "point": _POINT,
                "point_count": {"type": "integer", "minimum": 0},
                "resolved_count": {"type": "integer", "minimum": 0},
                "unresolved_count": {"type": "integer", "minimum": 0},
                "results": {"type": "array", "items": _RESULT_ITEM},
                "matched": {"type": ["object", "null"]},
                "stack": {"type": "array", "items": {"type": "object"}},
                "overlap_families": {"type": "array", "items": {"type": "object"}},
                "deepest_resolved_loc_id": {"type": ["string", "null"]},
                "deepest_resolved_admin_level": {"type": ["string", "integer", "null"]},
                "deepest_resolved_family": {"type": ["string", "null"]},
                "shallow_loc_id": {"type": "string"},
                "family": {"type": "string"},
                "family_result": {"type": "object"},
                "deeper_available": {"type": "boolean"},
                "available_deeper_admin_levels": {"type": "array"},
                "join_keys": {"type": "object"},
            },
        )
    if name == "get_loc_id_info":
        return _result_schema(
            success_variants=[["loc_id"], ["loc_id_count", "results"]],
            properties={
                "loc_id": {"type": "string"},
                "requested_loc_id": {"type": "string"},
                "name": {"type": ["string", "null"]},
                "iso3": {"type": ["string", "null"]},
                "family": {"type": ["string", "null"]},
                "admin_level": {"type": ["string", "integer", "null"]},
                "loc_id_count": {"type": "integer", "minimum": 0},
                "found_count": {"type": "integer", "minimum": 0},
                "missing_count": {"type": "integer", "minimum": 0},
                "results": {"type": "array", "items": _RESULT_ITEM},
                "hierarchy": {"type": "object"},
                "references": {"type": "object"},
                "data_packs": {"type": "array"},
                "geometry_families": {"type": "array"},
                "next_calls": {"type": "array"},
            },
        )
    if name in {"identify_dataset_geography", "identify_reference_system"}:
        return _result_schema(
            success_variants=[["ok", "status", "candidates"]],
            properties={
                "status": {"type": "string"},
                "limit": {"type": "integer", "minimum": 0},
                "identifier_count": {"type": "integer", "minimum": 0},
                "column_count": {"type": "integer", "minimum": 0},
                "candidates": {"type": "array", "items": {"type": "object"}},
                "recommended_binding": {"type": ["object", "null"]},
                "coordinate_binding": {"type": ["object", "null"]},
                "review_required": {"type": "boolean"},
            },
        )
    if name == "convert_reference":
        return _result_schema(
            success_variants=[["ok", "results"], ["item_count", "results"]],
            properties={
                "from_system": {"type": "string"},
                "to_system": {"type": "string"},
                "loc_id": {"type": ["string", "null"]},
                "from": {"type": "object"},
                "item_count": {"type": "integer", "minimum": 0},
                "converted_count": {"type": "integer", "minimum": 0},
                "unconverted_count": {"type": "integer", "minimum": 0},
                "results": {"type": "array", "items": _RESULT_ITEM},
            },
        )
    if name == "compare_geographies":
        return _result_schema(
            success_variants=[["ok", "spatial_relation"], ["item_count", "results"]],
            properties={
                "spatial_relation": {"type": ["string", "object", "null"]},
                "temporal_relation": {"type": ["string", "object", "null"]},
                "item_count": {"type": "integer", "minimum": 0},
                "compared_count": {"type": "integer", "minimum": 0},
                "failed_count": {"type": "integer", "minimum": 0},
                "results": {"type": "array", "items": _RESULT_ITEM},
            },
        )
    if name == "get_geometry":
        return _result_schema(
            success_variants=[["ok", "selection", "items"]],
            properties={
                "selection": {"type": "string", "enum": ["exact_loc_ids", "admin_scope"]},
                "scope": {"type": ["object", "null"]},
                "include_polygon": {"type": "boolean"},
                "requested": {"type": "integer", "minimum": 0},
                "available": {"type": "integer", "minimum": 0},
                "missing": {"type": "integer", "minimum": 0},
                "items": {"type": "array", "items": _RESULT_ITEM},
            },
        )
    return None


def geometry_tool_publication_meta(tool_name: str) -> dict[str, Any] | None:
    name = str(tool_name or "").strip()
    if name not in GEOMETRY_TOOL_IDS:
        return None
    result_families = {
        "resolve_point": "point_resolution",
        "resolve_deep_point": "point_resolution",
        "get_loc_id_info": "place_context",
        "identify_dataset_geography": "geography_identification",
        "identify_reference_system": "geography_identification",
        "convert_reference": "reference_conversion",
        "compare_geographies": "geography_relationship",
        "get_geometry": "geometry",
    }
    input_families = {
        "resolve_point": "coordinate",
        "resolve_deep_point": "scoped_coordinate",
        "get_loc_id_info": "loc_id",
        "identify_dataset_geography": "column_samples",
        "identify_reference_system": "identifier_samples",
        "convert_reference": "reference",
        "compare_geographies": "loc_id_pair",
        "get_geometry": "loc_id_selection",
    }
    limits = {
        "free": tool_free_item_limit(name),
        "account": tool_account_item_limit(name),
        "paid": tool_paid_item_limit(name),
    }
    pricing = tool_pricing(name)
    if pricing.startswith("paid"):
        above_free_limit = "payment under the authored policy; an active launch_free policy can waive settlement; requests above the active item limit return a typed cap error"
    elif pricing == "by_material":
        above_free_limit = "the selected material policy decides whether payment is required; requests above its lane limit return a typed cap error"
    else:
        above_free_limit = "typed cap error; split or narrow the request"
    access = {
        "contract_version": "1.0.0",
        "capability_id": tool_capability_id(name),
        "family": tool_family(name),
        "pricing": pricing,
        "pricing_scope": "authored_policy; active operator policy can waive settlement",
        "limits": {key: value for key, value in limits.items() if value is not None},
        "above_free_limit": above_free_limit,
        "meter": tool_meter(name),
        "pricing_version": tool_pricing_version(name),
        "price_micro_usd": tool_price_micro_usd(name),
        "help": {"tool": "get_tool_help", "arguments": {"tool_name": name}},
    }
    return {
        "com.daedalmap/access": access,
        "com.daedalmap/blind-caller": blind_caller_publication_guidance(name),
        "com.daedalmap/geometry-contract": {
            "contract_version": "1.0.0",
            "input_family": input_families[name],
            "result_family": result_families[name],
            "canonical_help_tool": "get_tool_help",
            "discovery_flow": ["get_catalog", "get_pack"],
        },
    }


def decorate_geometry_tool_definition(definition: dict[str, Any]) -> dict[str, Any]:
    """Attach output, access, and behavioral metadata to geometry tools."""
    name = str(definition.get("name") or "").strip()
    if name not in GEOMETRY_TOOL_IDS:
        return definition
    decorated = deepcopy(definition)
    decorated["outputSchema"] = geometry_tool_output_schema(name)
    decorated["annotations"] = {
        **(decorated.get("annotations") if isinstance(decorated.get("annotations"), dict) else {}),
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    decorated["_meta"] = {
        **(decorated.get("_meta") if isinstance(decorated.get("_meta"), dict) else {}),
        **(geometry_tool_publication_meta(name) or {}),
    }
    return decorated
