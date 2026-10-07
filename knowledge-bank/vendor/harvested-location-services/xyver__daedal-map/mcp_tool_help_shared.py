"""Blind-caller guidance for every public DaedalMap MCP tool.

Schemas and descriptions remain in ``mcp_surface_shared``. Access limits remain
in ``tool_access_shared``. This module owns the semantic help fields that cannot
be inferred safely from JSON Schema alone: when to use a tool, refusals,
examples, important outputs, provenance, and the next useful call.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mcp_discovery_shared import data_access_workflow

from tool_access_shared import (
    tool_account_item_limit,
    tool_effective_rate_limit,
    tool_free_item_limit,
    tool_inline_item_limit,
    tool_is_paid_bulk,
    tool_paid_item_limit,
    tool_pricing,
    tool_public_pricing,
    tool_profile,
)


def _g(use_when, do_not_use_for, example, outputs, next_calls=(), provenance=()):
    return {
        "use_when": list(use_when),
        "do_not_use_for": list(do_not_use_for),
        "examples": [example],
        "important_output_fields": list(outputs),
        "provenance_fields": list(provenance),
        "recommended_next_calls": list(next_calls),
    }


TOOL_GUIDANCE: dict[str, dict[str, Any]] = {
    "get_tool_help": _g(
        ["You found a tool through MCP discovery and need its usage contract or a working example."],
        ["Executing the target tool", "Replacing tools/list discovery"],
        {"tool_name": "resolve_point"},
        ["purpose", "input_schema", "interaction_contract", "examples", "access", "recommended_next_calls", "available_on_facades"],
    ),
    "get_catalog": _g(
        ["You need to discover currently published data packs or geometry families and their country coverage."],
        ["Querying pack rows", "Inspecting one selected family-country release"],
        {"catalog": "geometry", "detail": "lite"}, ["packs", "families", "countries", "download"], ["get_pack"]
    ),
    "get_pack": _g(
        ["You selected one data pack or geometry family and need its metadata and live contract before calling it."],
        ["Executing a dataset query", "Fetching geometry"],
        {"catalog": "geometry", "pack_id": "postal_area", "detail": "lite"},
        ["catalog", "pack_id", "detail", "countries", "reference_systems", "release", "next_step", "download_url"],
        ["get_data", "convert_reference", "get_geometry", "get_tool_help"], ["source metadata", "release/freshness fields"]
    ),
    "resolve_point": _g(
        ["You have one WGS84 coordinate or a bounded point array and need the deepest available first-pass administrative loc_id chain (global baseline through Admin 2; adopted country banks may reach Admin 3)."],
        ["Resolving names or outside codes", "Returning polygons", "Resolving Admin 4-6"],
        {"lat": 49.2827, "lon": -123.1207},
        ["deepest_resolved_loc_id", "stack", "resolution_mode", "available_deeper_admin_levels"],
        ["resolve_deep_point", "get_loc_id_info", "get_geometry"]
    ),
    "resolve_deep_point": _g(
        ["A shallow lookup returned an Admin 1-3 loc_id and one coordinate or scoped point array needs deeper administrative detail or one shape-backed family."],
        ["First-pass country discovery", "Multiple families", "Returning polygons", "Cross-scope point arrays"],
        {"lat": 34.0522, "lon": -118.2437, "shallow_loc_id": "USA-CA-037", "family": "postal_area"},
        ["shallow_loc_id", "family", "family_result"],
        ["get_loc_id_info", "get_geometry"]
    ),
    "get_loc_id_info": _g(
        ["You already have loc_id values and need identity, catalog coverage, geometry-family availability, hierarchy, lifecycle, or attached references."],
        ["Returning full polygons", "Calculating pairwise overlap"],
        {"loc_id": "CAN-BC", "include_hierarchy": True},
        ["loc_id", "parent_id", "hierarchy", "valid_from", "valid_to", "supersession", "references"],
        ["get_geometry", "compare_geographies"],
        ["source_system", "source_vintage", "release_id", "bank_id"]
    ),
    "identify_reference_system": _g(
        ["You have unknown geography identifiers or want to verify a declared system, level, vintage, and matching shape bank."],
        ["Passing the user's prose question as arguments", "Converting every dataset row", "Returning polygons", "Claiming full-dataset validation from a sample"],
        {"identifiers": ["06073000100", "06073000201"], "expected": {"system": "us_census_geoid", "geo_level": "tract", "vintage": "2020"}, "country_scope": "USA"},
        ["status", "candidates", "match_rate", "geometry_available_count", "geometry_bank_ids", "recommended_binding"],
        ["convert_reference", "get_geometry"],
        ["reference system", "source vintage", "geometry bank ids", "validation scope"],
    ),
    "identify_dataset_geography": _g(
        ["You have bounded samples from several table columns and need DaedalMap to select and identify the geography."],
        ["Uploading the complete source file", "Pre-classifying systems in browser code", "Returning polygons", "Converting every row"],
        {"columns": [{"name": "municipality_code", "values": ["1200013", "1200054"]}], "dataset_context": {"file_name": "population.csv", "row_count": 200}},
        ["status", "candidates", "recommended_candidate_id", "recommended_binding"],
        ["identify_reference_system", "convert_reference", "resolve_point"],
        ["selected input column", "reference system", "country scope", "admin level", "sample match rate"],
    ),
    "convert_reference": _g(
        ["You need an outside reference expressed as loc_id, or one reference system expressed in another through loc_id."],
        ["Resolving coordinates", "Discarding one-to-many weights"],
        {"from_system": "zip", "value": "00601", "to_system": "nws_fire"},
        ["from", "to_system", "results", "relationship_type", "weight"],
        ["get_loc_id_info", "get_geometry"],
        ["source and target systems", "bridge vintage", "relationship method", "artifact id"]
    ),
    "compare_geographies": _g(
        ["You have two loc_ids and need supported containment/common-ancestry or temporal-validity evidence."],
        ["Resolving names", "Treating deeper topology, overlap, or successor fields as a stable public guarantee"],
        {"left_loc_id": "CAN-BC", "right_loc_id": "CAN"},
        ["spatial_relation", "temporal_relation", "containment", "common_ancestor"],
        ["get_loc_id_info", "get_geometry"],
        ["left.bank_id", "right.bank_id", "geometry vintages", "calculation method"]
    ),
    "get_geometry": _g(
        ["You have exact loc_ids, or one administrative parent and target level, and need a fast shape-availability check, bbox, centroid, or opt-in polygons."],
        ["Identifying unknown geography", "Resolving names", "Inferring independent families from admin ancestry", "Bulk export packaging"],
        {"scope": {"parent_loc_id": "USA-TX", "admin_level": "admin_2"}, "include_polygon": False},
        ["selection", "scope", "requested", "available", "missing", "items"],
        ["get_loc_id_info"],
        ["bank_id", "geometry_vintage", "source", "license", "release_id"]
    ),
    "get_event": _g(
        ["You have an exact event_id from get_data and need to inspect or traverse that event."],
        ["Searching broadly for events", "Unbounded graph traversal", "Loading geometry implicitly"],
        {"event_id": "USA-HRCN-2022301N07140", "pack_id": "hurricanes", "include": ["relationships", "observations"]},
        ["event", "available", "relationships", "affected_places", "observations", "geometry"],
        ["get_data"], ["source event id", "relationship source/method", "companion-layer provenance"]
    ),
    "get_data": _g(
        ["You selected a published data pack and need its canonical rows or supported aggregate metrics."],
        ["Calling geometry tool families", "Passing internal source_id values", "Guessing metrics without get_pack", "Unbounded event scans"],
        {"pack_id": "currency", "metrics": ["local_per_usd"], "filters": {"region_ids": ["CAN"], "time": {"start": "2024-01-01", "end": "2024-01-31"}}},
        ["rows", "row_count", "source_id", "pack_id", "filters_applied", "provenance"], ["get_pack"], ["source metadata", "release/freshness", "license"]
    ),
}


# A tools/list caller must be able to recover when the value in hand belongs
# to a different geography workflow. Keep these redirects beside the richer
# help guidance so the published definition and get_tool_help cannot drift.
GEOMETRY_WRONG_INPUT_FIRST_CALL: dict[str, list[dict[str, str]]] = {
    "resolve_point": [
        {"when": "outside identifier or place name", "tool": "convert_reference"},
        {"when": "unknown dataset columns", "tool": "identify_dataset_geography"},
    ],
    "resolve_deep_point": [
        {"when": "coordinate without a shallow loc_id", "tool": "resolve_point"},
    ],
    "get_loc_id_info": [
        {"when": "coordinate", "tool": "resolve_point"},
        {"when": "outside identifier or place name", "tool": "convert_reference"},
    ],
    "identify_dataset_geography": [
        {"when": "one already-selected identifier column", "tool": "identify_reference_system"},
    ],
    "identify_reference_system": [
        {"when": "dataset whose geography column is unknown", "tool": "identify_dataset_geography"},
    ],
    "convert_reference": [
        {"when": "coordinate", "tool": "resolve_point"},
        {"when": "dataset whose geography column is unknown", "tool": "identify_dataset_geography"},
        {"when": "unknown country family or reference system", "tool": "get_pack"},
    ],
    "compare_geographies": [
        {"when": "outside identifiers or names", "tool": "convert_reference"},
    ],
    "get_geometry": [
        {"when": "coordinate", "tool": "resolve_point"},
        {"when": "outside identifier or place name", "tool": "convert_reference"},
        {"when": "loc_id identity or hierarchy details", "tool": "get_loc_id_info"},
    ],
}


def blind_caller_publication_guidance(tool_name: str) -> dict[str, Any]:
    """Compact semantic routing fields suitable for tools/list metadata."""
    name = str(tool_name or "").strip()
    guidance = TOOL_GUIDANCE.get(name) or {}
    use_when = list(guidance.get("use_when") or ())
    return {
        "question_answered": use_when[0] if use_when else "",
        "does_not_do": list(guidance.get("do_not_use_for") or ()),
        "wrong_input_first_call": deepcopy(GEOMETRY_WRONG_INPUT_FIRST_CALL.get(name) or []),
        "next_tools": list(guidance.get("recommended_next_calls") or ()),
        "full_help": {"tool": "get_tool_help", "arguments": {"tool_name": name}},
    }

def geometry_topic_help_payload(
    question: str | None = None,
    *,
    catalog_capabilities: dict[str, Any] | None = None,
    available_tool_names: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    capabilities = dict(catalog_capabilities or {})
    return {
        "ok": True,
        "tool_name": "get_tool_help",
        "help_topic": "geometry",
        "summary": "Start here before using DaedalMap geometry tools. The tools resolve coordinates and identifiers onto loc_id, inspect geography, and return bounded shape results.",
        "core_rule": "Learn the durable geometry model here, then use get_catalog to select a canonical family and get_pack to inspect its country-specific systems before constructing an execution call.",
        "coverage": capabilities,
        "start_here": [
            {
                "step": 1,
                "tool": "get_catalog",
                "arguments": {"catalog": "geometry", "detail": "lite", "country_scope": "<ISO3 when known>"},
                "purpose": "Discover canonical families and the countries where each currently exists. Omit country_scope for the global family directory.",
            },
            {
                "step": 2,
                "tool": "get_pack",
                "arguments": {"catalog": "geometry", "pack_id": "<selected family>", "country_scope": "<ISO3 when detail is needed>", "detail": "lite"},
                "purpose": "Read broad country availability, or add country_scope for that country's systems and release details.",
            },
            {
                "step": 3,
                "tool": "get_tool_help",
                "arguments": {"tool_name": "<tool selected below>"},
                "purpose": "Read the exact input schema before constructing the call.",
            },
            {
                "step": 4,
                "purpose": "Use the country result and one of the workflows below; keep identifiers as strings.",
            },
        ],
        "concepts": {
            "loc_id": "The stable DaedalMap geography identifier shared by geometry and data tools.",
            "administrative_spine": {
                "rule": "Each country selects one complete, nested administrative hierarchy. Countries have different depths and native tier names.",
                "discovery": "Use get_catalog(catalog='geometry', detail='lite', country_scope='<ISO3>') for the active depth and current query guidance.",
            },
            "reference_families": {
                "rule": "Postal areas, places, watersheds, electoral districts, Indigenous regions, weather zones, water bodies, and other families are independent reference systems unless the catalog says they belong to the selected spine.",
                "discovery": "Use get_catalog(catalog='geometry') to choose a family, then get_pack for its countries. Add country_scope to get_pack only for that country's systems, vintages, levels, and artifacts.",
            },
            "catalog_authority": "Coverage is generated from admitted releases. Do not assume that every country has the same depth, families, or physical query layout.",
            "query_cost": "Opening and searching geometry partitions is the main cold-path cost. Item count still matters, but calls aligned with the catalog's query guidance are usually faster than calls spread across unrelated regions or families.",
        },
        "request_rules": [
            {
                "request": "one exploratory point",
                "rule": "Call resolve_point. It infers the country and returns the deepest available result through Admin 3 without opening deep partitions.",
            },
            {
                "request": "multiple administrative points",
                "rule": "Use resolve_point with points=[...] for a cross-country batch; it performs global Admin 0 discovery and then opens only each discovered country's adopted Admin 0-3 bank or bounded global Admin 0-2 baseline shard.",
            },
            {
                "request": "points at a partitioned deep level",
                "rule": "First call resolve_point with points=[...], group by the shallow loc_id used as scope, then call resolve_deep_point once per scope and family.",
            },
            {
                "request": "geometry for known loc_ids",
                "rule": "Keep administrative loc_ids aligned with the country's query guidance. Keep independent reference-family loc_ids grouped by country and family; do not infer administrative ownership from overlap.",
            },
            {
                "request": "large or nationwide deep coverage",
                "rule": "Use the country catalog entry to enumerate the declared partition owners and make bounded MCP calls for one owner at a time.",
            },
        ],
        "interaction_contract": {
            "natural_language_owner": "calling_client_llm",
            "execution_input": "strict_json_schema",
            "per_tool_help": {"tool": "get_tool_help", "arguments": {"tool_name": "<exact tool name from tools/list>"}},
            "rules": [
                "The calling LLM interprets ordinary user language; deterministic geometry tools do not parse prose unless their schema explicitly accepts a question field.",
                "Use tools/list, then get_tool_help for the exact tool before an unfamiliar call.",
                "Preserve external identifiers as strings, especially when they have leading zeros.",
                "Inspect error.code, warnings, guidance, and clarification after a failed or ambiguous call.",
                "Ask the person only when clarification.required is true; otherwise repair the call directly.",
            ],
        },
        "workflows": [
            {
                "name": "coordinates_to_geography",
                "steps": ["resolve_point", "get_loc_id_info only when details are requested", "get_geometry only when shape availability or shapes are requested"],
            },
            {
                "name": "shallow_administrative_points",
                "example": {
                    "tool": "resolve_point",
                    "arguments": {
                        "points": [{"lat": 45.039641, "lon": -103.313618}],
                        "target_admin_level": 3,
                    },
                },
                "steps": ["confirm coverage", "send points from one country", "reuse the returned loc_id chain"],
            },
            {
                "name": "partitioned_deep_points_across_multiple_regions",
                "steps": [
                    "read the selected country's catalog entry and query_guidance",
                    "resolve to the declared partition-owner level",
                    "group points by the returned owner loc_id",
                    "call resolve_deep_point separately for each scope and family with shallow_loc_id",
                ],
                "important": "resolve_point with a points array is the shallow bulk pass. resolve_deep_point accepts one shallow scope and one family per call; administrative requests derive the Admin 1 partition internally.",
            },
            {
                "name": "known_loc_ids_to_shapes",
                "steps": [
                    "separate administrative loc_ids from independent reference-family loc_ids",
                    "group them according to the country catalog entry and family",
                    "call get_geometry once per group with include_polygon=false for availability, bbox, and centroid",
                    "repeat with include_polygon=true only when polygon coordinates are needed",
                ],
            },
            {
                "name": "known_or_suspected_dataset_identifiers",
                "steps": ["identify_reference_system on at most 100 representative string keys", "use the unambiguous geography_binding", "call convert_reference with a bounded items batch when the source system is confirmed"],
            },
            {
                "name": "one_external_reference",
                "steps": ["get_catalog when the family is unknown", "get_pack for family/country details", "convert_reference through loc_id"],
            },
            {
                "name": "relationships_and_time",
                "steps": ["get_loc_id_info for available data/geometry plus identity and hierarchy", "compare_geographies for supported pairwise containment/common ancestry and temporal validity"],
            },
        ],
        "available_tools": sorted(
            name for name in available_tool_names
            if name in TOOL_GUIDANCE
            and (name == "get_tool_help" or tool_profile(name).get("family") == "geography")
        ),
        "notes": [
            capabilities.get("public_claim") or "Coverage is read from geometry_catalog.json; do not hardcode a country list or depth.",
            "loc_id is the reserve geography identifier used by data packs and geometry tools.",
            "Known identifier crosswalks bypass point and polygon rediscovery.",
            "A mixed-vintage point chain is context, not strict stored parentage.",
            "Use bbox/centroid by default; full polygons are opt-in and more tightly bounded.",
            "Batch limits are safety ceilings, not a promise that unrelated partitions should be mixed in one call.",
            "Paying raises hosted throughput; it does not unlock a different geometry truth set.",
        ],
        "input_question": str(question or "").strip() or None,
    }
TOPIC_TOOLS: dict[str, tuple[str, ...]] = {
    "overview": ("get_catalog", "get_pack", "get_data", "convert_reference", "resolve_point", "get_geometry"),
    "data": ("get_catalog", "get_pack", "get_data"),
    "disasters": (
        "get_catalog", "get_pack", "get_data", "get_event",
    ),
    "custom_data": (
        "identify_dataset_geography", "identify_reference_system", "convert_reference",
    ),
}


TOPIC_SUMMARIES = {
    "overview": "Enter the loc_id universe through a resolution or onboarding tool, then use loc_id-based discovery, data, geometry, and relationship tools.",
    "data": "Use get_catalog to select a data pack, get_pack to learn its fields and routing, then query rows with loc_id-based region filters.",
    "disasters": "Use get_data to find event rows and stable event_ids, then get_event to inspect one event's relationships, affected places, native observations, or explicit geometry.",
    "custom_data": "Identify geography from bounded samples, confirm the reference system, then convert a bounded identifier batch through loc_id.",
}


def topic_help_payload(
    topic: str,
    *,
    question: str | None = None,
    available_tool_names: list[str] | tuple[str, ...] = (),
    catalog_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one bounded workflow overview through the shared help tool."""
    selected = str(topic or "").strip().lower()
    available = set(available_tool_names)
    if selected == "geometry":
        payload = geometry_topic_help_payload(
            question,
            catalog_capabilities=catalog_capabilities,
            available_tool_names=available_tool_names,
        )
        payload["available_tools"] = [
            name for name in payload.get("available_tools") or []
            if not available or name in available
        ]
        return payload
    if selected not in TOPIC_TOOLS:
        raise ValueError("topic must be overview, data, disasters, custom_data, or geometry")
    tools = [name for name in TOPIC_TOOLS[selected] if not available or name in available]
    if selected in {"overview", "data", "disasters"}:
        workflow = data_access_workflow()
        start_here = workflow["steps"]
        next_step = start_here[0]
    else:
        start_here = [
            {
                "stage": "identify",
                "tool": "identify_dataset_geography",
                "arguments": {"columns": [{"name": "<column name>", "values": ["<bounded string sample>"]}]},
            },
            {"stage": "inspect", "tool": "get_tool_help", "arguments": {"tool_name": "<selected builder tool>"}},
        ]
        workflow = {"goal": TOPIC_SUMMARIES[selected], "steps": start_here}
        next_step = start_here[0]
    payload = {
        "ok": True,
        "tool_name": "get_tool_help",
        "help_topic": selected,
        "summary": TOPIC_SUMMARIES[selected],
        "available_tools": tools,
        "workflow": workflow,
        "start_here": start_here,
        "next_step": next_step,
        "input_question": str(question or "").strip() or None,
    }
    if selected == "overview":
        payload["loc_id_boundary"] = {
            "rule": "Data, geometry, relationship, and scope tools consume canonical loc_ids; onboarding and resolution tools bring outside geography into that universe.",
            "entry_paths": [
                {"input": "known loc_ids", "next": "get_catalog or the exact loc_id-based tool"},
                {"input": "coordinates", "tool": "resolve_point"},
                {"input": "outside code or place name", "tool": "convert_reference"},
                {"input": "unknown user dataset column", "tool": "identify_dataset_geography"},
            ],
        }
    return payload


def tool_help_payload(
    tool_name: str,
    *,
    tool_definition: dict[str, Any],
    available_on_facades: list[str],
    effective_limits: dict[str, Any] | None = None,
    local_installed: bool = False,
) -> dict[str, Any]:
    name = str(tool_name or "").strip()
    guidance = deepcopy(TOOL_GUIDANCE.get(name) or {})
    profile = tool_profile(name)
    limits = {
        "free_item_limit": tool_free_item_limit(name),
        "inline_item_limit": tool_inline_item_limit(name),
    }
    if tool_is_paid_bulk(name):
        limits.update({
            "account_item_limit": tool_account_item_limit(name),
            "paid_item_limit": tool_paid_item_limit(name),
        })
    limits = {key: value for key, value in limits.items() if value is not None}
    if effective_limits:
        limits.update({key: value for key, value in effective_limits.items() if value is not None})
    pricing = tool_pricing(name)
    rate_limits = {
        lane: {"limit": values[0], "window_seconds": values[1]}
        for lane in ("free", "account", "paid")
        for values in (tool_effective_rate_limit(name, lane=lane),)
    }
    access = {
        "pricing": tool_public_pricing(name),
        "pricing_scope": "authored_policy; active operator policy can waive settlement",
        "free_discovery": name in {"get_tool_help", "get_catalog", "get_pack", "identify_dataset_geography", "identify_reference_system"},
        "limits": limits,
        "above_free_limit": "payment_required" if pricing.startswith("paid") else (
            "bounded_inline_limit_error" if name in {"create_geometry_export", "create_conversion_job"} else "typed_cap_error"
        ),
        "rate_limited_independently": True,
        "rate_limits": rate_limits,
        "trusted_artifact_bypass": [
            "shared_route_call_limit",
            "per_tool_call_limit",
            "item_cap",
            "payment_challenge",
        ],
    }
    if local_installed:
        access.update({
            "access_lane": "local_installed",
            "rate_limited_independently": False,
            "service_item_caps_enforced": False,
            "payment_required": False,
            "resource_boundary": "local machine memory, disk, and process availability",
        })
        if access["limits"]:
            access["hosted_limits"] = access["limits"]
            access["limits"] = {}
        access["hosted_rate_limits"] = access.pop("rate_limits")
        access["above_free_limit"] = "local_machine_resources"
    if name == "resolve_point" and not local_installed:
        access["caller_tiers"] = {
            "anonymous": {"included_items": limits.get("free_item_limit"), "above_limit": "payment_required"},
            "verified_account": {"included_items": limits.get("account_item_limit"), "above_limit": "payment_required"},
            "paid_plan": {"included_items": limits.get("paid_item_limit"), "above_limit": "interactive_limit_exceeded"},
        }
        access["bulk_shape"] = {
            "threshold": limits.get("free_item_limit"),
            "shallow_tool": "resolve_point: one point or a cross-country point array; Admin0 discovery is followed by an adopted Admin0-3 country bank or the bounded global Admin0-2 baseline shard",
            "deep_tool": "resolve_deep_point: one point or point array plus one shallow_loc_id and one family; family defaults to administrative",
        }
    elif name == "resolve_deep_point" and not local_installed:
        shared_limit = limits.get("free_item_limit")
        access["caller_tiers"] = {
            "anonymous": {"included_items": shared_limit, "above_limit": "not_available"},
            "verified_account": {"included_items": shared_limit, "above_limit": "not_available"},
            "paid_plan": {"included_items": shared_limit, "above_limit": "not_available"},
        }
        access["bulk_shape"] = {
            "partition_scope": "exactly one admin_1_loc_id per call",
            "maximum_items": limits.get("free_item_limit"),
            "payment_policy": "free within the per-call ceiling",
        }
    return {
        "ok": True,
        "tool_name": name,
        "title": tool_definition.get("title"),
        "purpose": tool_definition.get("description"),
        "input_schema": deepcopy(tool_definition.get("inputSchema") or {}),
        "interaction_contract": {
            "natural_language_owner": "calling_client_llm",
            "execution_input": "strict_json_schema",
            "rules": [
                "Translate the user's request into this tool's input_schema; do not pass prose unless the schema explicitly defines a natural-language question or query field.",
                "Preserve identifiers as strings when leading zeros or source formatting may matter.",
                "Do not invent pack ids, source ids, metric ids, filter fields, reference systems, loc_ids, or vintages; use discovery tools and returned contracts.",
                "On error, inspect error.code, warnings, guidance, and clarification before retrying.",
                "Ask the user only when clarification.required is true; otherwise correct the tool call without burdening the user.",
            ],
            "clarification_shape": {
                "required": "boolean",
                "reason": "stable_machine_code",
                "questions": [{
                    "id": "stable_answer_id",
                    "prompt": "one concise user-facing question",
                    "answer_schema": "JSON Schema for the answer",
                    "maps_to": "target argument path when directly mappable",
                }],
            },
        },
        **guidance,
        "access": access,
        "capability_id": profile.get("capability_id"),
        "family": profile.get("family"),
        "available_on_facades": sorted(set(available_on_facades)),
    }


def validate_tool_guidance(tool_names: set[str]) -> list[str]:
    errors: list[str] = []
    missing = sorted(tool_names - set(TOOL_GUIDANCE))
    extra = sorted(set(TOOL_GUIDANCE) - tool_names)
    if missing:
        errors.append("missing guidance: " + ", ".join(missing))
    if extra:
        errors.append("guidance for unpublished tools: " + ", ".join(extra))
    for name in sorted(tool_names & set(TOOL_GUIDANCE)):
        guidance = TOOL_GUIDANCE[name]
        for field in ("use_when", "do_not_use_for", "examples", "important_output_fields", "recommended_next_calls", "provenance_fields"):
            if field not in guidance or not isinstance(guidance[field], list):
                errors.append(f"{name}: {field} must be a list")
        if not guidance.get("use_when") or not guidance.get("do_not_use_for") or not guidance.get("examples"):
            errors.append(f"{name}: blind-caller guidance is incomplete")
    return errors


def validate_guidance_examples(tool_definitions: list[dict[str, Any]]) -> list[str]:
    """Catch stale top-level example arguments when a tool schema changes."""
    errors: list[str] = []
    definitions = {str(item.get("name") or ""): item for item in tool_definitions}
    for name, guidance in sorted(TOOL_GUIDANCE.items()):
        definition = definitions.get(name)
        if definition is None:
            continue
        schema = definition.get("inputSchema") or {}
        properties = set((schema.get("properties") or {}).keys())
        required = set(schema.get("required") or ())
        for index, example in enumerate(guidance.get("examples") or (), start=1):
            if not isinstance(example, dict):
                errors.append(f"{name}: example {index} must be an object")
                continue
            unknown = sorted(set(example) - properties)
            missing = sorted(required - set(example))
            if unknown and schema.get("additionalProperties") is False:
                errors.append(f"{name}: example {index} has unknown arguments: {', '.join(unknown)}")
            if missing:
                errors.append(f"{name}: example {index} is missing required arguments: {', '.join(missing)}")
    return errors
