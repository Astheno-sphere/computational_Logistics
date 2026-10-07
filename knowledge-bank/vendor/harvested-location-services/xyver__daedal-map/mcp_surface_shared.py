from __future__ import annotations

from mcp_data_contract_shared import decorate_data_tool_definition, decorate_shared_help_definition
from mcp_discovery_shared import data_access_workflow
from mcp_geometry_contract_shared import decorate_geometry_tool_definition

def _pack_id_description() -> str:
    return "Pack identifier from get_catalog. Newly catalog-admitted packs require no MCP schema change."


def _data_filters_schema() -> dict:
    scalar_or_list = {
        "anyOf": [
            {"type": ["string", "number", "integer", "boolean", "null"]},
            {"type": "array", "items": {"type": ["string", "number", "integer", "boolean"]}},
        ]
    }
    return {
        "type": "object",
        "properties": {
            "region_ids": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "minLength": 1},
                "description": "Canonical country or hierarchical loc_ids from get_pack, such as JPN or USA-TX.",
            },
            "time": {
                "type": "object",
                "properties": {
                    "value": {"anyOf": [{"type": "string", "format": "date-time"}, {"type": "string", "format": "date"}, {"type": "integer"}]},
                    "start": {"anyOf": [{"type": "string", "format": "date-time"}, {"type": "string", "format": "date"}, {"type": "integer"}]},
                    "end": {"anyOf": [{"type": "string", "format": "date-time"}, {"type": "string", "format": "date"}, {"type": "integer"}]},
                    "granularity": {"type": "string", "enum": ["daily", "weekly", "monthly", "yearly", "timestamp"]},
                },
                "anyOf": [
                    {"required": ["value"]},
                    {"required": ["start"]},
                    {"required": ["end"]},
                ],
                "additionalProperties": False,
                "description": "Inclusive ISO-8601 date/datetime or integer-year selection. Use YYYY-MM-DD, not partial YYYY-MM strings.",
            },
            "equals": {
                "type": "object",
                "additionalProperties": scalar_or_list,
                "description": "Exact field/value filters using filterable fields published by get_pack.",
            },
            "compare": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "minLength": 1},
                        "op": {"type": "string", "enum": ["=", "!=", ">", ">=", "<", "<="]},
                        "value": {},
                    },
                    "required": ["field", "op", "value"],
                    "additionalProperties": False,
                },
                "description": "Threshold filters using filterable fields or selected metric ids published by get_pack.",
            },
        },
        # Pack-specific direct field filters remain legal, but the four shared
        # shapes above are explicit so clients do not have to guess them.
        "additionalProperties": scalar_or_list,
    }


def _data_sort_schema() -> dict:
    item = {
        "type": "object",
        "properties": {
            "field": {"type": "string", "minLength": 1},
            "direction": {"type": "string", "enum": ["asc", "desc"]},
        },
        "required": ["field"],
        "additionalProperties": False,
    }
    return {
        "anyOf": [item, {"type": "array", "items": item}],
        "description": "Sort by a sortable field from get_pack; direction defaults to asc.",
    }


def _query_props() -> dict:
    return {
        "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing and idempotency."},
        "metrics": {"type": "array", "items": {"type": "string"}, "description": "Metric ids to return."},
        "filters": {"type": "object", "description": "Structured filters including time ranges, region_ids, and compare clauses."},
        "sort": {"anyOf": [{"type": "array"}, {"type": "object"}], "description": "Optional sort instructions for row-returning queries."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum number of rows to return."},
        "output": {"type": "object", "description": "Optional output controls such as response format hints."},
    }


def _query_tool(name: str, title: str, description: str, required: list[str]) -> dict:
    return {
        "name": name,
        "title": title,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": dict(_query_props()),
            "required": list(required),
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    }


def build_mcp_instructions(*, safety_notice: str | None = None) -> str:
    flow = " -> ".join(step["tool"] for step in data_access_workflow()["steps"])
    base = (
        f"Geospatial data MCP server. Autonomous data workflow: {flow}. "
        "get_catalog is the current authority for "
        "available packs and each pack's free or paid access lane. The calling "
        "LLM translates the user's natural-language request into strict tool "
        "JSON; execution tools do not parse prose. Start with get_catalog, then "
        "get_pack before querying a new pack. Call get_tool_help before an "
        "unfamiliar tool. On a typed error, preserve the user's intent, inspect "
        "error/guidance/clarification, correct the arguments from the schema, "
        "and ask the user only when clarification.required is true."
    )
    if safety_notice:
        return f"{base} Safety: {safety_notice}"
    return base


PAUSED_PUBLIC_TOOL_NAMES = frozenset({
    "get_live_earthquake_events",
    "get_live_volcano_events",
    # Retained for the future custom-data/bulk-export product, but hidden from
    # ordinary public MCP discovery and execution until that workflow has a
    # durable queue/artifact lifecycle.
    "resolve_loc_id_scope",
    "estimate_geometry_package",
    "create_geometry_export",
    "estimate_conversion_job",
    "create_conversion_job",
    "get_job_status",
})


def build_tool_definitions(*, include_paused: bool = False) -> list[dict]:
    definitions = [
        {
            "name": "get_tool_help",
            "title": "Get Tool Help",
            "description": "Free unified guidance. Pass tool_name for the exact contract of one visible tool, or topic for an overview and workflow guidance. topic='geometry' contains the loc_id and geometry-family orientation formerly published as a separate helper.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "Exact tool name from tools/list. Do not combine with topic."},
                    "topic": {"type": "string", "enum": ["overview", "data", "disasters", "custom_data", "geometry"], "description": "Workflow overview. Do not combine with tool_name."},
                    "question": {"type": "string", "description": "Optional question used only with a topic overview."},
                },
                "oneOf": [
                    {"required": ["tool_name"], "not": {"required": ["topic"]}},
                    {"required": ["topic"], "not": {"required": ["tool_name"]}},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_catalog",
            "title": "List Available Packs and Geometry Families",
            "description": "Broad directory discovery only: use this before selecting a pack or geometry family. It lists available data packs or geometry families and supports optional coverage filtering; it does not inspect one known loc_id or return one entry's full contract. For data, loc_id plus time_range filters the directory to confirmed place-and-time coverage while keeping unknown coverage separate. Geometry results list families and release units. After choosing one result, call get_pack with that exact pack_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "catalog": {"type": "string", "enum": ["data", "geometry"], "default": "data", "description": "Catalog family. The geography facade defaults to geometry; other facades default to data."},
                    "detail": {"type": "string", "enum": ["lite", "full", "download"], "default": "lite", "description": "Use lite to select a pack, full for expanded metric/query inventories, or download for the complete raw catalog URL."},
                    "country_scope": {"type": "string", "description": "Optional ISO3 focus for catalog='geometry' with detail='lite'."},
                    "loc_id": {"type": "string", "description": "Optional DaedalMap loc_id for catalog='data'. Combine with time_range to discover packs confirmed for both place and time. For place details without pack filtering, use get_loc_id_info."},
                    "time_range": {
                        "type": "object",
                        "properties": {
                            "start": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                            "end": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                        },
                        "additionalProperties": False,
                        "description": "Optional inclusive discovery window for catalog='data'. At least one bound is required.",
                    },
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_pack",
            "title": "Inspect One Selected Pack or Geometry Family",
            "description": "Single-entry contract lookup only: use this after get_catalog and supply one exact pack_id. It returns that selected data pack's query fields and access metadata, or that selected geometry family's countries and global domains. Add country_scope or release_unit to inspect its systems, releases, vintages, levels, and artifacts. It does not list the whole catalog, inspect a place, or retrieve rows or shapes; follow next_step to the appropriate execution tool.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "catalog": {"type": "string", "enum": ["data", "geometry"], "description": "Metadata family. When omitted, geometry facades default to geometry and known geometry-family ids are inferred; all other calls default to data."},
                    "pack_id": {"type": "string", "description": _pack_id_description()},
                    "detail": {"type": "string", "enum": ["lite", "full", "download"], "default": "lite", "description": "Use lite to decide and start, full for detailed MCP query metadata, or download for the complete raw metadata file."},
                    "country_scope": {"type": "string", "pattern": "^[A-Za-z]{3}$", "description": "Optional ISO3 country for a geometry family. Omit it to learn which countries publish the family; provide it for country-specific versions, vintages, levels, and artifacts."},
                    "release_unit": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$", "description": "Optional non-country geometry release unit such as GLOBAL or MARINE. Do not combine with country_scope."},
                },
                "required": ["pack_id"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_event",
            "title": "Get Event",
            "description": "Retrieve and traverse one exact disaster event. The lightweight default returns event identity and core attributes without heavy shape columns. Add relationships for cross-hazard event links, affected_places for event-to-loc_id coverage, observations for native tracks/progression/runups/sequences, or geometry for explicit shapes. Start with get_data to find an event_id; use get_pack to discover published relationship families.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "minLength": 1, "description": "Exact stable event_id returned by a disaster-pack get_data row."},
                    "pack_id": {"type": "string", "description": "Optional disaster pack hint. Recommended when known to avoid probing unrelated event sources."},
                    "include": {
                        "type": "array",
                        "uniqueItems": True,
                        "items": {"type": "string", "enum": ["relationships", "affected_places", "observations", "geometry"]},
                        "description": "Optional companion layers. Omit for the lightweight event summary. Geometry is never returned implicitly.",
                    },
                    "relationship_depth": {"type": "integer", "minimum": 1, "maximum": 2, "default": 1, "description": "Bounded cross-hazard traversal depth when relationships is included."},
                    "geometry_mode": {"type": "string", "enum": ["current", "timeline"], "default": "current", "description": "current returns the representative/current shape; timeline returns bounded progression frames where supported."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100, "description": "Per-section ceiling for relationships, affected places, observations, or geometry frames."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "resolve_point",
            "title": "Resolve Point(s) (Shallow)",
            "description": "Compact first-pass reverse geocoding for one WGS84 coordinate or a bounded point array. Returns the deepest available administrative loc_id chain: the global baseline reaches Admin 2, while adopted country query banks may reach Admin 3. It does not open deep partitions or side-family shape banks. Use a returned shallow loc_id with resolve_deep_point for Admin 4-6 or one explicit family. Single and bulk requests share this contract; access limits are based on point count.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "minimum": -90, "maximum": 90, "description": "Latitude in WGS84 decimal degrees."},
                    "lon": {"type": "number", "minimum": -180, "maximum": 180, "description": "Longitude in WGS84 decimal degrees."},
                    "points": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                                "row_index": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                                "id": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                            },
                            "required": ["lat", "lon"],
                            "additionalProperties": False,
                        },
                        "description": "Bounded WGS84 point array. Use top-level lat/lon instead for one point.",
                    },
                    "target_admin_level": {
                        "anyOf": [{"type": "string"}, {"type": "integer"}],
                        "description": "Optional exact requested level from Admin 0-3. Omit it to return the deepest available shallow level.",
                    },
                    "include_marine_context": {"type": "boolean", "default": False, "description": "Opt in to parallel Marine overlaps for land matches. Defaults to false so ordinary administrative resolution stays lightweight. Offshore Marine fallback still applies."},
                    "batch_id": {"type": "string", "description": "Optional caller-supplied batch id echoed for point arrays."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "oneOf": [
                    {"required": ["lat", "lon"], "not": {"required": ["points"]}},
                    {"required": ["points"], "not": {"anyOf": [{"required": ["lat"]}, {"required": ["lon"]}]}},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "resolve_deep_point",
            "title": "Resolve Point(s) (Deep)",
            "description": "Second-pass resolution for one WGS84 coordinate or a bounded point array. Supply one shared shallow_loc_id returned by resolve_point and one canonical family from get_catalog(catalog='geometry'). family defaults to administrative; shape-backed families use direct bbox-to-exact-shape lookup without crosswalks. Single and bulk requests share this scoped contract.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "minimum": -90, "maximum": 90, "description": "Latitude in WGS84 decimal degrees."},
                    "lon": {"type": "number", "minimum": -180, "maximum": 180, "description": "Longitude in WGS84 decimal degrees."},
                    "points": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                                "row_index": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                                "id": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                            },
                            "required": ["lat", "lon"],
                            "additionalProperties": False,
                        },
                        "description": "Points already known to fall within the supplied shallow_loc_id scope.",
                    },
                    "shallow_loc_id": {"type": "string", "minLength": 5, "description": "The deepest canonical Admin 1-3 loc_id returned by resolve_point, such as USA-NY-061-009903."},
                    "target_admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}], "description": "Optional exact Admin 4-6 level. Omit for the deepest available match."},
                    "family": {"type": "string", "pattern": "^[a-z0-9_]+$", "default": "administrative", "description": "One family selector. Defaults to administrative; use marine for the direct Marine resolver, or a canonical country family such as postal_area, watershed, or land_management_region."},
                    "batch_id": {"type": "string", "description": "Optional caller-supplied batch id echoed for point arrays."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "required": ["shallow_loc_id"],
                "oneOf": [
                    {"required": ["lat", "lon"], "not": {"required": ["points"]}},
                    {"required": ["points"], "not": {"anyOf": [{"required": ["lat"]}, {"required": ["lon"]}]}},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_loc_id_info",
            "title": "Inspect Known loc_id Identities",
            "description": "Known-place navigation and enrichment tool: use only when you already have one canonical loc_id or a bounded loc_ids array. It returns identity, strict stored parentage, lifecycle, shape status, and place-specific data-pack and geometry-family availability with executable next calls. Supply as_of for a precision-aware source-release date review alert. It does not list the global catalog and does not return polygon coordinates; use get_catalog to browse everything or get_geometry for shapes. Set include_hierarchy for same-release ancestors and include_references for maintained external or cross-family connections. Historical records are never replaced automatically. No payment required.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "loc_id": {"type": "string", "description": "DaedalMap loc_id, e.g. 'USA-CA'."},
                    "loc_ids": {"type": "array", "items": {"type": "string"}, "description": "DaedalMap loc_ids to inspect together, including every loc_id from a resolve_point stack. Default public cap is deployment-configurable."},
                    "as_of": {"type": "string", "description": "Optional ISO day, month, or year (YYYY-MM-DD, YYYY-MM, or YYYY). Reviews the current Full source edition and returns a Double-check date alert for coarse or stale coverage; it does not select historical geometry."},
                    "include_hierarchy": {"type": "boolean", "description": "When true, include strict stored parent and ancestor data. This never invents a parent edge across mixed releases. Default false."},
                    "include_references": {"type": "boolean", "description": "When true, include known external or side-chain references attached to each loc_id. Default false."},
                    "systems": {"type": "array", "items": {"type": "string"}, "description": "Optional reference systems to include when include_references is true, such as zcta, nws_fire, overlay_tribal, or overlay_nws_public_zone."},
                    "iso3": {"type": "string", "description": "Optional country hint for crosswalk artifacts. Defaults to the loc_id country when possible."},
                    "target_admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}], "description": "Admin level for crosswalk-backed reverse reference lookup. Inferred when omitted."},
                    "min_share": {"type": "number", "minimum": 0, "maximum": 1, "description": "Optional minimum target-area share for reverse overlap references."},
                    "limit_per_system": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Maximum overlap references to return per bridge/system. Default 10."},
                    "batch_id": {"type": "string", "description": "Optional caller-supplied batch id for tracing."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "anyOf": [
                    {"required": ["loc_id"]},
                    {"required": ["loc_ids"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "identify_dataset_geography",
            "title": "Choose Geography Columns From a Dataset",
            "description": "Multi-column dataset classifier: use when you do not yet know which column or latitude/longitude pair represents geography. Pass bounded samples from several named scalar columns; it selects the plausible geography column(s), then proposes a country, level, and maintained reference-system binding. It does not validate a preselected identifier column value-by-value; after selecting a code column, use identify_reference_system when explicit verification is needed. Returns up to three reviewable bindings and recommends only an unambiguous high-confidence result. No geometry is loaded and no full dataset is retained. No payment required.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "columns": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 64,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "values": {"type": "array", "maxItems": 32, "items": {"type": "string"}},
                                "nonempty_count": {"type": "integer", "minimum": 0},
                            },
                            "required": ["name", "values"],
                            "additionalProperties": False,
                        },
                        "description": "Structurally filtered columns with deterministic representative scalar values. Do not pre-label their geographic system.",
                    },
                    "dataset_context": {
                        "type": "object",
                        "properties": {
                            "file_name": {"type": "string"},
                            "sheet_name": {"type": "string"},
                            "row_count": {"type": "integer", "minimum": 0},
                        },
                        "additionalProperties": False,
                    },
                    "country_scope": {"type": "string", "description": "Optional caller-declared ISO3 hint. Omit when unknown."},
                    "request_id": {"type": "string"},
                },
                "required": ["columns"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "identify_reference_system",
            "title": "Identify One Identifier Column's Reference System",
            "description": "Single-column code-system classifier: use after an identifier column has already been selected, or to inspect one bounded set of like geography codes. Pass only identifier strings from that one field so leading zeros are preserved. It determines or verifies the system, country, level, vintage, and compatible geometry bank; it does not choose among dataset columns, convert the full dataset, or return polygons. Use identify_dataset_geography instead when column selection is still unknown. Ambiguous results remain unselected until the caller retries with expected.system; a known system can be verified by supplying expected on the first call. No payment required.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "One geography identifier to inspect."},
                    "identifiers": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                        "description": "A bounded representative identifier sample. Duplicate values are checked once. Values must be strings so leading zeros are preserved.",
                    },
                    "expected": {
                        "type": "object",
                        "properties": {
                            "system": {"type": "string", "description": "Caller-declared reference system, such as us_census_geoid, loc_id, zcta, or a catalog reference system. Supply it immediately when known, or after choosing an identification result."},
                            "geo_level": {"anyOf": [{"type": "string"}, {"type": "integer"}], "description": "Expected geography level, such as tract or admin_3."},
                            "vintage": {"type": "string", "description": "Expected source/reference vintage, such as 2020."},
                            "country_scope": {"type": "string", "description": "Expected ISO3 country scope."},
                        },
                        "additionalProperties": False,
                    },
                    "country_scope": {"type": "string", "description": "Optional ISO3 country hint used to narrow candidate banks."},
                    "dataset_context": {
                        "type": "object",
                        "description": "Bounded, non-row dataset clues used to rank plausible interpretations without replacing exact identifier verification.",
                        "properties": {
                            "file_name": {"type": "string"},
                            "sheet_name": {"type": "string"},
                            "column_name": {"type": "string"},
                            "column_names": {"type": "array", "items": {"type": "string"}, "maxItems": 1000},
                            "row_geography": {"type": "string", "description": "Optional plain-language clue such as county, tract, or ZIP area."},
                            "local_format_match_rate": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "additionalProperties": False,
                    },
                    "validation_scope": {"type": "string", "enum": ["sample", "all_distinct_identifiers"], "description": "Describes whether the bounded input is a sample or, only when it fits the identification cap, the complete distinct-key set. This tool validates every supplied identifier; create_conversion_job validates every row in the full dataset."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "anyOf": [
                    {"required": ["identifier"]},
                    {"required": ["identifiers"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "convert_reference",
            "title": "Convert Geographic Reference",
            "description": "The single geographic reference converter. Converts one reference, or a bounded list, through DaedalMap loc_id: X -> loc_id -> Y. Omit to_system to enter the loc_id universe; provide it for any-to-any conversion. Use get_pack first when the family or country-specific system is unknown. The tools/list access metadata states authored free, account, and paid item allowances; the active operator policy may waive payment. Exceeding the active item ceiling returns a typed cap error.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "from_system": {"type": "string", "description": "Input reference system, such as zip, overlay_zcta, nws_fire, tribal, admin_boundary, or loc_id."},
                    "value": {"type": "string", "description": "Identifier or name in the input system."},
                    "to_system": {"type": "string", "default": "daedalmap.loc_id", "description": "Optional output reference system. Defaults to DaedalMap loc_id; provide zcta, nws_fire, overlay_nws_public_zone, overlay_tribal, admin_local, or another catalog system for any-to-any conversion."},
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "from_system": {"type": "string", "description": "Input reference system for this row. Defaults to top-level from_system when omitted."},
                                "value": {"type": "string", "description": "Identifier or name in the input system."},
                                "to_system": {"type": "string", "description": "Output reference system for this row. Defaults to top-level to_system when omitted."},
                                "iso3": {"type": "string", "description": "Optional country hint for this row."},
                                "target_admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}], "description": "Optional intermediate admin target level for this row."},
                                "relationship_vintage": {"type": "string", "description": "Optional relationship vintage for this row."},
                                "min_share": {"type": "number", "minimum": 0, "maximum": 1, "description": "Optional minimum overlap share threshold for this row."},
                                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Maximum ranked output references for this row."},
                                "country_hint": {"type": "string", "description": "Optional country hint for admin/name resolution."},
                                "admin_level_hint": {"type": "integer", "minimum": 0, "maximum": 6, "description": "Optional admin-level hint for admin/name resolution."},
                                "as_of": {"type": "string", "description": "ISO date or year used for time-bounded identities."},
                                "row_index": {"anyOf": [{"type": "integer"}, {"type": "string"}], "description": "Optional caller row identifier echoed in the result."},
                                "id": {"anyOf": [{"type": "integer"}, {"type": "string"}], "description": "Optional caller identifier echoed in the result."},
                            },
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                        "description": "Reference conversions to run in one call. Default public cap is deployment-configurable.",
                    },
                    "iso3": {"type": "string", "description": "Country hint for crosswalk artifacts. Default USA."},
                    "target_admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}], "description": "Admin level used as the intermediate crosswalk target. Default admin_2."},
                    "relationship_vintage": {"type": "string", "description": "Optional source relationship vintage to require."},
                    "min_share": {"type": "number", "minimum": 0, "maximum": 1, "description": "Optional minimum overlap share threshold."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Maximum ranked output references to return. Default 10."},
                    "country_hint": {"type": "string", "description": "Optional country hint for admin/name resolution."},
                    "admin_level_hint": {"type": "integer", "minimum": 0, "maximum": 6, "description": "Optional admin-level hint for admin/name resolution."},
                    "as_of": {"type": "string", "description": "ISO date or year used for time-bounded identities."},
                    "batch_id": {"type": "string", "description": "Optional caller-supplied batch id for tracing."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "anyOf": [
                    {"required": ["from_system", "value"]},
                    {"required": ["items"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "compare_geographies",
            "title": "Compare Geographic Identities",
            "description": "Compare two geographic identities for the public guarantees implemented today: containment/common ancestry and temporal validity for the requested vintages. The response may include additional maintained evidence, but callers must not rely on deeper topology or relationship semantics as a stable contract until that review is complete. Use convert_reference first for names or outside identifiers. No payment required.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "left_loc_id": {"type": "string", "description": "First DaedalMap loc_id."},
                    "right_loc_id": {"type": "string", "description": "Second DaedalMap loc_id."},
                    "as_of": {"type": "string", "description": "ISO date or year applied to both identities."},
                    "left_as_of": {"type": "string", "description": "Optional ISO date or year for the left identity; overrides as_of."},
                    "right_as_of": {"type": "string", "description": "Optional ISO date or year for the right identity; overrides as_of."},
                    "include_successors": {"type": "boolean", "description": "Include direct successors and present-day descendants for maintained historical identities. Default true."},
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "left_loc_id": {"type": "string"},
                                "right_loc_id": {"type": "string"},
                                "as_of": {"type": "string"},
                                "left_as_of": {"type": "string"},
                                "right_as_of": {"type": "string"},
                                "include_successors": {"type": "boolean"},
                                "row_index": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                                "id": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                            },
                            "required": ["left_loc_id", "right_loc_id"],
                            "additionalProperties": False,
                        },
                        "description": "Bounded geography pairs to compare in one call.",
                    },
                    "batch_id": {"type": "string", "description": "Optional caller-supplied batch id for tracing."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "anyOf": [
                    {"required": ["left_loc_id", "right_loc_id"]},
                    {"required": ["items"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_geometry",
            "title": "Retrieve Shapes for Known loc_ids",
            "description": "Shape availability and bounded coordinate retrieval only: use when you already have exact loc_ids, or one administrative parent_loc_id plus target admin_level. The default fast preflight returns has_shape, shape metadata, centroid, and bounding box; set include_polygon=true only for GeoJSON coordinates. Use get_loc_id_info for hierarchy, identity, catalog coverage, or crosswalk facts; get_geometry does not return those place details. Administrative scope queries stay within the optimized Admin Spine layout, while independent geometry families require exact loc_ids. Historical geometry is returned first and successors are never substituted automatically. Access is selected-material dependent: tools/list metadata gives the lane ceilings, while the chosen geometry bank decides whether payment is required.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "loc_id": {"type": "string", "description": "DaedalMap loc_id, such as USA-CA-037, USA-Z-00601, USA-NWSFZ-AKZ317, EEZ-USA, or IHO1953-240001002."},
                    "loc_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string"}, "description": "Exact DaedalMap loc_ids to fetch in one call. Default public cap is deployment-configurable and lower when include_polygon is true."},
                    "scope": {
                        "type": "object",
                        "properties": {
                            "parent_loc_id": {"type": "string", "description": "Administrative parent loc_id, such as USA-TX or CAN-BC."},
                            "admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}], "description": "Descendant level to retrieve, such as admin_2, 2, or county."},
                            "bbox": {"anyOf": [{"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}, {"type": "string"}], "description": "Optional minLon,minLat,maxLon,maxLat intersection filter."},
                        },
                        "required": ["parent_loc_id", "admin_level"],
                        "additionalProperties": False,
                    },
                    "include_polygon": {"type": "boolean", "description": "When true, include the full GeoJSON geometry. Default false."},
                    "batch_id": {"type": "string", "description": "Optional caller-supplied batch id for tracing."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "oneOf": [
                    {"required": ["loc_id"]},
                    {"required": ["loc_ids"]},
                    {"required": ["scope"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "resolve_loc_id_scope",
            "title": "Resolve loc_id Scope",
            "description": "Strict hierarchy traversal. Given one stored parent loc_id and target admin level, returns descendants from that coherent parent chain. This is not the mixed-vintage latest-per-depth point resolver and must not bridge release seams. Use it before shape exports such as every county in a selected parent scope. No natural-language decoding is performed.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "parent_loc_id": {"type": "string", "description": "Parent DaedalMap loc_id, such as USA or CAN-BC."},
                    "admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}], "description": "Target level, such as admin_2, 2, county, or state."},
                    "scope": {
                        "type": "object",
                        "properties": {
                            "parent_loc_id": {"type": "string"},
                            "admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                            "bbox": {"anyOf": [{"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}, {"type": "string"}]},
                        },
                        "additionalProperties": False,
                    },
                    "bbox": {"anyOf": [{"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}, {"type": "string"}], "description": "Optional minLon,minLat,maxLon,maxLat filter."},
                    "limit": {"type": "integer", "minimum": 0, "maximum": 1000, "description": "Maximum rows to return inline. Counts are returned even when rows are truncated."},
                    "offset": {"type": "integer", "minimum": 0, "description": "Offset for preview paging."},
                    "count_only": {"type": "boolean", "description": "When true, return counts without loc_id rows."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "anyOf": [
                    {"required": ["parent_loc_id", "admin_level"]},
                    {"required": ["scope"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "estimate_geometry_package",
            "title": "Estimate Geometry Package",
            "description": "Dry-run estimate for a selected geometry export: exact loc_id count, shape/vintage availability, bytes, delivery mode, citation requirements, and charge units. This estimates an export artifact, not a canonical DaedalMap geometry release bundle.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "loc_id": {"type": "string", "description": "Single loc_id to package."},
                    "loc_ids": {"type": "array", "items": {"type": "string"}, "description": "Explicit loc_ids to package."},
                    "scope": {
                        "type": "object",
                        "properties": {
                            "parent_loc_id": {"type": "string"},
                            "admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                            "bbox": {"anyOf": [{"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}, {"type": "string"}]},
                        },
                        "additionalProperties": False,
                    },
                    "format": {"type": "string", "enum": ["geojson", "geojson_gzip", "zip"], "description": "Implemented delivery format. Unsupported format names are rejected rather than silently returning another representation."},
                    "output_name": {"type": "string", "maxLength": 80, "description": "Optional safe base filename for the export."},
                    "include_polygon": {"type": "boolean", "description": "Estimate full shapes when true; metadata-only when false."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "anyOf": [
                    {"required": ["loc_id"]},
                    {"required": ["loc_ids"]},
                    {"required": ["scope"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "create_geometry_export",
            "title": "Create Geometry Export",
            "description": "Creates a synchronous v0 geometry export from exact loc_ids or one strict scope as real GeoJSON, gzipped GeoJSON, or zipped GeoJSON. Hosted service default: 250 selected loc_ids, sized around a 10-20 second response budget and configurable by deployment. A direct local-runtime loopback caller has no service item cap. Use estimate_geometry_package or get_tool_help for the effective access lane.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_id": {"type": "string", "description": "Quote id returned by estimate_geometry_package, when available."},
                    "loc_id": {"type": "string"},
                    "loc_ids": {"type": "array", "items": {"type": "string"}, "description": "Selected loc_ids. The default synchronous limit is 250; larger calls return a typed operational-limit response."},
                    "scope": {
                        "type": "object",
                        "properties": {
                            "parent_loc_id": {"type": "string"},
                            "admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                            "bbox": {"anyOf": [{"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}, {"type": "string"}]},
                        },
                        "additionalProperties": False,
                    },
                    "format": {"type": "string", "enum": ["geojson", "geojson_gzip", "zip"]},
                    "output_name": {"type": "string", "maxLength": 80},
                    "include_polygon": {"type": "boolean"},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "anyOf": [
                    {"required": ["loc_id"]},
                    {"required": ["loc_ids"]},
                    {"required": ["scope"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
        {
            "name": "estimate_conversion_job",
            "title": "Estimate loc_id Conversion Job",
            "description": "Free dry-run quote for uploaded or pasted user data conversion. Checks a fixed representative sample of up to 32 supplied rows through the real conversion resolver, then estimates total resolvable rows, output bytes, errors, and charge units. row_count is the full dataset size and is not replaced by the sample size. Conversion execution validates every submitted row and reports structured failures for unmatched keys. For a coordinate file, set geography_binding.mode to coordinates and send point_count (valid coordinate pairs counted locally), row_count, and request_id instead of items: no point is resolved, the quote is the ceiling for exactly those points, and resolve_point called with the same request_id reuses its quote_id. Quotes are maximums; execution charges only successfully resolved rows or points.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "from_system": {"type": "string", "description": "Input reference system for rows."},
                    "geography_binding": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["reference", "loc_id", "coordinates"]},
                            "system": {"type": "string", "description": "Declared identifier system. Used when from_system is omitted. Not used for mode coordinates."},
                            "geo_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                            "vintage": {"type": "string"},
                            "id_column": {"type": "string", "description": "Identifier-column name for future artifact inputs; inline items continue to use value."},
                            "country_scope": {"type": "string"},
                        },
                        "additionalProperties": False,
                        "description": "Known dataset-geography declaration. Identifier modes require system; the estimate verifies it against distinct identifiers and avoids point containment. Mode coordinates quotes point resolution from point_count.",
                    },
                    "to_system": {"type": "string", "description": "Optional output reference system. Omit to normalize to loc_id."},
                    "items": {"type": "array", "items": {"type": "object", "properties": {
                        "value": {"type": "string", "description": "Identifier value; keep as a string to preserve leading zeros."},
                        "data": {"type": "object", "maxProperties": 200, "additionalProperties": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "integer"}, {"type": "boolean"}, {"type": "null"}]}, "description": "Original spreadsheet columns to preserve. Column names beginning daedalmap_ are reserved for generated output fields."},
                        "row_index": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                        "id": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                        "from_system": {"type": "string"}, "to_system": {"type": "string"}, "iso3": {"type": "string"},
                        "target_admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                        "relationship_vintage": {"type": "string"}, "min_share": {"type": "number", "minimum": 0, "maximum": 1},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    }, "required": ["value"], "additionalProperties": False}, "description": "Representative sample or full rows; the estimate resolves at most the first 32. Row-level fields may override top-level defaults."},
                    "row_count": {"type": "integer", "minimum": 0, "description": "Expected total row count when only a sample or artifact pointer is provided."},
                    "point_count": {"type": "integer", "minimum": 0, "description": "Coordinate mode only: rows with a valid latitude/longitude pair. The quote ceiling; blank or invalid rows are excluded and never charged."},
                    "batch_id": {"type": "string", "description": "Coordinate mode only: batch id the resolve_point run will send."},
                    "target_admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                    "iso3": {"type": "string"},
                    "relationship_vintage": {"type": "string"},
                    "min_share": {"type": "number", "minimum": 0, "maximum": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "output_format": {"type": "string", "enum": ["json_rows", "csv", "jsonl", "parquet"], "description": "Enriched-row output format. CSV is spreadsheet-friendly; Parquet is compact and typed; JSON Lines is stream-friendly."},
                    "output_name": {"type": "string", "maxLength": 80, "description": "Optional safe base filename."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "anyOf": [
                    {"required": ["from_system", "items"]},
                    {"required": ["from_system", "row_count"]},
                    {"required": ["geography_binding", "items"]},
                    {"required": ["geography_binding", "row_count"]},
                    {"required": ["geography_binding", "point_count", "request_id"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "create_conversion_job",
            "title": "Create loc_id Conversion Job",
            "description": "Creates a synchronous v0 user-data conversion job with preserved scalar fields and JSON rows, CSV, JSON Lines, or Parquet output. Hosted service default: 7,500 rows, tuned around a 10-20 second response budget. A direct local-runtime loopback caller has no service item cap; local machine resources are the boundary. Identifier deduplication keeps repeated geography keys efficient.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_id": {"type": "string", "description": "Quote id returned by estimate_conversion_job, when available."},
                    "from_system": {"type": "string"},
                    "geography_binding": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["reference", "loc_id"]},
                            "system": {"type": "string"},
                            "geo_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                            "vintage": {"type": "string"},
                            "id_column": {"type": "string"},
                            "country_scope": {"type": "string"},
                        },
                        "required": ["system"],
                        "additionalProperties": False,
                    },
                    "to_system": {"type": "string", "description": "Optional output reference system. Omit to normalize to loc_id."},
                    "items": {"type": "array", "items": {"type": "object", "properties": {
                        "value": {"type": "string", "description": "Identifier value; keep as a string to preserve leading zeros."},
                        "data": {"type": "object", "maxProperties": 200, "additionalProperties": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "integer"}, {"type": "boolean"}, {"type": "null"}]}, "description": "Original spreadsheet columns to preserve. Column names beginning daedalmap_ are reserved for generated output fields."},
                        "row_index": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                        "id": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                        "from_system": {"type": "string"}, "to_system": {"type": "string"}, "iso3": {"type": "string"},
                        "target_admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                        "relationship_vintage": {"type": "string"}, "min_share": {"type": "number", "minimum": 0, "maximum": 1},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    }, "required": ["value"], "additionalProperties": False}, "description": "Rows to convert; row-level fields may override top-level defaults."},
                    "target_admin_level": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                    "iso3": {"type": "string"},
                    "relationship_vintage": {"type": "string"},
                    "min_share": {"type": "number", "minimum": 0, "maximum": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "output_format": {"type": "string", "enum": ["json_rows", "csv", "jsonl", "parquet"]},
                    "output_name": {"type": "string", "maxLength": 80},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "required": ["items"],
                "anyOf": [
                    {"required": ["from_system"]},
                    {"required": ["geography_binding"]},
                ],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": False},
        },
        {
            "name": "get_job_status",
            "title": "Get Geometry Job Status",
            "description": "Retrieves a completed bounded v0 geometry export or conversion job by job_id. The current public contract creates completed inline jobs only; durable queued jobs and downloadable artifact links remain a future Custom Data Builder capability.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job id returned by create_geometry_export or create_conversion_job."},
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                },
                "required": ["job_id"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_live_earthquake_events",
            "title": "Get Live Earthquake Events",
            "description": "Free live wrapper. Calls the USGS FDSN API for recent preliminary earthquake events normalized to DaedalMap event fields. Use this only when the caller explicitly wants live/preliminary upstream results or needs a very recent window not yet present in the published canonical earthquake lane. This is not the enriched canonical history lane.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                    "hours": {"type": "integer", "minimum": 1, "maximum": 168, "description": "Recent lookback window in hours. Ignored when start_time is provided."},
                    "start_time": {"type": "string", "description": "Optional inclusive ISO-8601 start datetime."},
                    "end_time": {"type": "string", "description": "Optional exclusive-ish ISO-8601 end datetime. Defaults to now."},
                    "min_magnitude": {"type": "number", "description": "Minimum earthquake magnitude. Defaults to 2.5."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum live rows to return."},
                    "orderby": {"type": "string", "enum": ["time", "time-asc", "magnitude", "magnitude-asc"], "description": "USGS result ordering."},
                    "min_latitude": {"type": "number", "description": "Optional bounding box minimum latitude."},
                    "max_latitude": {"type": "number", "description": "Optional bounding box maximum latitude."},
                    "min_longitude": {"type": "number", "description": "Optional bounding box minimum longitude."},
                    "max_longitude": {"type": "number", "description": "Optional bounding box maximum longitude."},
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_live_volcano_events",
            "title": "Get Live Volcano Events",
            "description": "Free live wrapper. Calls the Smithsonian/GVP WFS for recent preliminary volcanic eruption updates normalized to DaedalMap event fields. This is not the enriched canonical history lane.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing."},
                    "days": {"type": "integer", "minimum": 1, "maximum": 730, "description": "Recent lookback window in days. Ignored when start_time is provided."},
                    "start_time": {"type": "string", "description": "Optional inclusive ISO-8601 start datetime or date."},
                    "end_time": {"type": "string", "description": "Optional inclusive ISO-8601 end datetime or date. Defaults to now."},
                    "min_vei": {"type": "number", "description": "Optional minimum Volcanic Explosivity Index."},
                    "ongoing_only": {"type": "boolean", "description": "When true, only return eruptions marked continuing by GVP."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum live rows to return."},
                    "orderby": {"type": "string", "enum": ["time", "time-asc", "vei", "vei-asc"], "description": "Result ordering."},
                },
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_data",
            "title": "Get Data",
            "description": "The single workhorse for published data-pack rows inside the loc_id universe. After get_pack, pass its pack_id, exact metric ids, structured filters, sort, and row limit. filters.region_ids accepts canonical loc_ids; an administrative parent such as USA-TX matches descendant rows at the pack's published geography grain. Disaster event rows always include their stable event_id; pass that id to get_event for relationships, affected places, native observations, or explicit event geometry. Use resolution/onboarding tools before get_data when the input is coordinates, outside codes, names, or an unidentified user column. Pack metadata owns source routing, time grain, geography, access, and pack-specific rules; callers do not choose internal source_id values. Geometry tool families use their focused next_step tools instead of this row-query contract.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "Optional caller-supplied request id for tracing and idempotency."},
                    "pack_id": {"type": "string", "minLength": 1, "description": _pack_id_description()},
                    "metrics": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}, "description": "Exact metric ids from get_pack. Use event_count for aggregate counts only when get_pack publishes it."},
                    "filters": _data_filters_schema(),
                    "sort": _data_sort_schema(),
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum number of rows to return for the requested source or pack."},
                    "output": {
                        "type": "object",
                        "properties": {
                            "format": {"type": "string", "enum": ["rows"], "default": "rows"},
                            "include_provenance": {"type": "boolean", "default": False},
                        },
                        "additionalProperties": False,
                        "description": "Optional response controls. v1 supports rows only.",
                    },
                },
                "required": ["pack_id", "metrics", "filters"],
                "additionalProperties": False,
            },
            "annotations": {"readOnlyHint": True},
        },
    ]
    return [
        decorate_shared_help_definition(
            decorate_geometry_tool_definition(decorate_data_tool_definition(definition))
        )
        for definition in definitions
        if include_paused or str(definition.get("name") or "") not in PAUSED_PUBLIC_TOOL_NAMES
    ]
