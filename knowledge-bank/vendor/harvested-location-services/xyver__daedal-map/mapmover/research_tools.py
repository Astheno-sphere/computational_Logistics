"""Research artifact tools.

Tools operate on the corpus registry and existing session cache. They return bounded
JSON-serializable results for LLM context.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from pathlib import Path
from typing import Any

from mapmover import logger
from mapmover.corpus_registry import corpus_registry
from mapmover.data_loading import (
    get_source_path,
    load_api_pack_detail,
    load_catalog,
    load_source_metadata,
    load_source_reference,
)
from mapmover.loc_id_join import apply_loc_id_subset_filter, unique_loc_ids_from_rows
from mapmover.source_time_contract import build_metric_year_ranges
from mapmover.duckdb_helpers import (
    build_guarded_connection,
    parquet_columns,
    path_to_uri,
    quote_ident,
    run_df,
)
from mapmover.foundation_helpers import bridge_loc_id_family, get_foundation_helper_registry
from mapmover.geometry_handlers import get_selection_geometries
from mapmover.runtime.result_cap import apply_row_count_cap_to_payload
from mapmover.runtime.source_hints import build_reference_summary, build_source_routing_guidance, get_routing_hints
from mapmover.runtime.source_hints import get_metric_alias_matches
from mapmover.runtime.warning_policy import DEFAULT_DISPLAY_WARNING_POLICY
from mapmover.runtime.warning_primitives import (
    interrupt_display_payload_if_needed,
)
from mapmover.session_cache import session_manager

try:
    import duckdb
except Exception:  # pragma: no cover - optional runtime dependency
    duckdb = None


RESEARCH_TOOL_DEFINITIONS = [
    {
        "name": "ask_research_sources",
        "description": "Bind this question to the explicit source_ids already loaded in the active Research corpus. Call before any evidence query. This never calls an LLM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pack_ids": {"type": "array", "items": {"type": "string"}},
                "source_ids": {"type": "array", "items": {"type": "string"}},
                "question": {"type": "string"},
            },
        },
    },
    {
        "name": "get_research_pack",
        "description": "Read the published source contract for one bound pack before constructing a query: metrics, fields, time, geography, and source guidance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string"},
                "source_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["pack_id"],
        },
    },
    {
        "name": "query_research_source_data",
        "description": "Run one deterministic query_dataset-style query against one concrete source_id inside the full source_ids boundary returned by ask_research_sources. This is the same source-query contract used by the Research MCP and never calls an LLM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_ids": {"type": "array", "items": {"type": "string"}},
                "pack_ids": {"type": "array", "items": {"type": "string"}},
                "query": {"type": "object"},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["source_ids", "query"],
        },
    },
    {
        "name": "build_artifact_display_subset",
        "description": "Build a feature subset from one loaded artifact for map display or highlighting. If limit is omitted, return all matched features.",
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "filters": {"type": "object"},
                "order_by": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "direction": {"type": "string", "enum": ["asc", "desc"]},
                        },
                    },
                },
                "limit": {"type": "integer", "minimum": 1},
                "fit": {"type": "boolean"},
                "context_visibility": {"type": "string", "enum": ["keep", "replace"]},
                "style": {
                    "type": "object",
                    "properties": {
                        "fill_color": {"type": "string"},
                        "stroke_color": {"type": "string"},
                    },
                },
            },
            "required": ["artifact_id"],
        },
    },
]


RESEARCH_TOOL_MAX_INPUT_ROWS = max(
    1000,
    int(os.environ.get("RESEARCH_TOOL_MAX_INPUT_ROWS", "200000")),
)


def _normalize_source_ids(value) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return list(dict.fromkeys(str(item or "").strip() for item in values if str(item or "").strip()))


def _active_research_source_ids(session_id: str) -> list[str]:
    return list(
        dict.fromkeys(
            str(artifact.get("source_id") or "").strip()
            for artifact in corpus_registry.list_artifacts(session_id)
            if str(artifact.get("source_id") or "").strip()
        )
    )


def _build_research_query_contract(sources: list[dict], *, boundary: list[str]) -> dict:
    """Match the MCP's query-planning guidance for the app-side client."""
    contracts: list[dict] = []
    for source in sources:
        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            continue
        contract = {
            "source_id": source_id,
            "metric_ids": sorted((source.get("metrics") or {}).keys()),
            "filterable_fields": list(source.get("filterable_fields") or []),
            "sortable_fields": list(source.get("sortable_fields") or []),
            "location_field": source.get("location_field"),
            "time_field": source.get("time_field"),
            "temporal_coverage": source.get("temporal_coverage"),
        }
        try:
            from mapmover.api_query_runtime import get_api_source_spec
            spec = get_api_source_spec(source_id)
        except Exception:
            spec = None
        if spec is not None:
            contract.update({
                "metric_ids": sorted(spec.metrics.keys()),
                "filterable_fields": sorted(spec.filterable_fields),
                "sortable_fields": sorted(spec.sortable_fields),
                "default_limit": spec.default_limit,
                "max_limit": spec.max_limit,
                "time_granularity": spec.time_granularity,
                "location_filter_mode": spec.location_filter_mode,
            })
        semantics = {
            metric_id: metric.get("response_semantics")
            for metric_id, metric in (source.get("metrics") or {}).items()
            if isinstance(metric, dict) and isinstance(metric.get("response_semantics"), dict)
        }
        if semantics:
            contract["metric_response_semantics"] = semantics
        contracts.append(contract)
    return {
        "execution_tool": "query_research_source_data",
        "boundary_argument": "Copy the exact source_ids returned by ask_research_sources into every query_research_source_data call.",
        "query_payload": {
            "source_id": "One source_id inside the active boundary.",
            "metrics": "Exact metric_ids from that source contract.",
            "filters.region_ids": "Canonical geographic loc_ids.",
            "filters.time": "Use {value} or {start, end}; timestamp sources use ISO-8601 timestamps.",
            "filters.equals": "Exact matches for published filterable fields.",
            "sort": "Exact sortable fields or selected metric aliases.",
            "limit": "Positive integer no greater than the selected source max_limit.",
        },
        "rules": [
            "Select only metrics the question needs; do not add an unrelated severity or observation metric.",
            "Query one concrete source inside the full boundary at a time.",
            "A shared loc_id field is not proof of a join; query compatible rows or a source-owned bridge before claiming one.",
            "Use only returned rows and source metadata for claims.",
        ],
        "sources": contracts,
    }


def _bind_research_sources(session_id: str, tool_input: dict) -> dict:
    """Bind the app Research turn to the same explicit source boundary as MCP."""
    active_source_ids = _active_research_source_ids(session_id)
    requested_source_ids = _normalize_source_ids(tool_input.get("source_ids"))
    requested_pack_ids = _normalize_source_ids(tool_input.get("pack_ids"))
    active_by_pack: dict[str, list[str]] = {}
    for source_id in active_source_ids:
        pack_id = str((load_source_metadata(source_id) or {}).get("pack_id") or "").strip()
        if pack_id:
            active_by_pack.setdefault(pack_id, []).append(source_id)

    boundary = requested_source_ids or [
        source_id
        for pack_id in requested_pack_ids
        for source_id in active_by_pack.get(pack_id, [])
    ]
    if not boundary and not requested_pack_ids:
        boundary = active_source_ids
    unavailable = [source_id for source_id in boundary if source_id not in active_source_ids]
    missing_packs = [pack_id for pack_id in requested_pack_ids if not active_by_pack.get(pack_id)]
    if unavailable or missing_packs or not boundary:
        return {
            "tool_name": "ask_research_sources",
            "outcome": "error",
            "error": {
                "code": "source_outside_active_corpus",
                "message": "Research can query only sources currently loaded in this corpus.",
                "available_source_ids": active_source_ids,
                "unavailable_source_ids": unavailable,
                "unavailable_pack_ids": missing_packs,
            },
        }
    pack_ids = list(
        dict.fromkeys(
            str((load_source_metadata(source_id) or {}).get("pack_id") or "").strip()
            for source_id in boundary
            if str((load_source_metadata(source_id) or {}).get("pack_id") or "").strip()
        )
    )
    return {
        "tool_name": "ask_research_sources",
        "outcome": "ok",
        "pack_ids": pack_ids,
        "source_ids": boundary,
        "source_boundary": boundary,
        "binding_rule": "Copy this exact source_ids list unchanged into every query_research_source_data call.",
        "server_llm_used": False,
        "reasoning_owner": "client_llm",
        "execution_path": "shared_dataset_query_runtime",
    }


def _get_bound_research_pack(session_id: str, tool_input: dict) -> dict:
    pack_id = str(tool_input.get("pack_id") or "").strip()
    active_source_ids = _active_research_source_ids(session_id)
    boundary = _normalize_source_ids(tool_input.get("source_ids")) or active_source_ids
    if not pack_id:
        return {"tool_name": "get_research_pack", "outcome": "error", "error": {"code": "missing_pack_id"}}
    detail = load_api_pack_detail(pack_id) or {}
    if not detail:
        catalog = load_catalog() or {}
        pack_row = next(
            (row for row in catalog.get("packs") or [] if str(row.get("pack_id") or "").strip() == pack_id),
            {},
        )
        detail = dict(pack_row or {})
        detail["sources"] = []
        for source_id in detail.get("source_ids") or []:
            metadata = load_source_metadata(source_id) or {}
            if not metadata:
                continue
            detail["sources"].append({
                "source_id": source_id,
                "source_name": metadata.get("source_name") or source_id,
                "description": metadata.get("description") or "",
                "data_type": metadata.get("data_type") or "metrics",
                "location_field": metadata.get("location_field") or "loc_id",
                "time_field": metadata.get("time_field"),
                "temporal_coverage": metadata.get("temporal_coverage"),
                "metrics": metadata.get("metrics") or {},
                "filterable_fields": metadata.get("filterable_fields") or [],
                "sortable_fields": metadata.get("sortable_fields") or [],
                "reference_guidance": load_source_reference(source_id) or {},
            })
    sources = [
        source for source in detail.get("sources") or []
        if str(source.get("source_id") or "").strip() in boundary
        and str(source.get("source_id") or "").strip() in active_source_ids
    ]
    if not sources:
        return {
            "tool_name": "get_research_pack",
            "outcome": "error",
            "error": {"code": "pack_outside_active_corpus", "available_source_ids": active_source_ids},
        }
    return {
        "tool_name": "get_research_pack",
        "outcome": "ok",
        "pack": {**detail, "source_ids": [str(source.get("source_id")) for source in sources], "sources": sources},
        "source_boundary": boundary,
        "research_query_contract": _build_research_query_contract(sources, boundary=boundary),
        "server_llm_used": False,
        "reasoning_owner": "client_llm",
        "execution_path": "shared_dataset_query_runtime",
    }


def _query_bound_research_source(session_id: str, tool_input: dict, *, original_query: str = "") -> dict:
    """Execute the MCP's query_dataset payload through the shared app executor."""
    boundary = _normalize_source_ids(tool_input.get("source_ids"))
    active_source_ids = _active_research_source_ids(session_id)
    query = dict(tool_input.get("query") or {})
    source_id = str(query.get("source_id") or "").strip()
    if not boundary or not source_id or source_id not in boundary or source_id not in active_source_ids:
        return {
            "tool_name": "query_research_source_data",
            "outcome": "error",
            "error": {"code": "source_outside_boundary", "allowed_source_ids": boundary, "requested_source_id": source_id},
        }
    if tool_input.get("limit") is not None and "limit" not in query:
        query["limit"] = tool_input.get("limit")
    metadata = load_source_metadata(source_id) or {}
    matched_metrics = [metric for _, metric in get_metric_alias_matches(metadata, original_query)]
    specific_metrics = list(dict.fromkeys(metric for metric in matched_metrics if metric != "event_count"))
    intended_metrics = specific_metrics or list(dict.fromkeys(matched_metrics))
    if len(intended_metrics) == 1:
        # The source owns its aliases. A single explicit metric intent wins
        # over an LLM's attempt to decorate a table with adjacent fields.
        query["metrics"] = intended_metrics
    try:
        from starlette.requests import Request
        from mapmover.routes.api_query import execute_query_dataset_payload

        request_headers = [(b"accept", b"application/json"), (b"user-agent", b"DaedalMap-Research/0.2")]
        # Cloud QA for a paid pack must exercise the published data path with a
        # real trusted-artifact credential.  This is intentionally opt-in and
        # limited to an already-tagged QA suite; it never changes ordinary
        # Research traffic or bypasses server-side token validation.
        qa_artifact_token = os.getenv("QA_RESEARCH_ARTIFACT_TOKEN", "").strip()
        if qa_artifact_token and os.getenv("LLM_USAGE_FORCE_QA_USER_ID", "").strip():
            request_headers.append((b"authorization", f"Bearer {qa_artifact_token}".encode("utf-8")))
        request = Request({
            "type": "http", "method": "POST", "path": "/api/v1/query/dataset",
            "headers": request_headers,
            "client": ("research", 0), "server": ("research", 0), "scheme": "http", "query_string": b"",
        })
        # This is an in-process, corpus-bound Research tool call, not the
        # public endpoint. The MCP's local executor accepts the same bounded
        # source query without the public anti-scan gate.
        request.state.research_source_contract = True
        response = asyncio.run(execute_query_dataset_payload(request, query))
        result = json.loads(bytes(response.body).decode("utf-8"))
    except Exception as exc:
        return {"tool_name": "query_research_source_data", "outcome": "error", "error": {"code": "data_query_failed", "message": str(exc)}}
    if response.status_code >= 400:
        error = result.get("error") if isinstance(result.get("error"), dict) else result
        return {"tool_name": "query_research_source_data", "outcome": "error", "error": {"code": error.get("code") or "shared_query_failed", "message": error.get("message")}, "source_boundary": boundary}
    return {
        "tool_name": "query_research_source_data",
        "outcome": "ok",
        **result,
        "source_boundary": boundary,
        "server_llm_used": False,
        "reasoning_owner": "client_llm",
        "execution_path": "shared_dataset_query_runtime",
    }


def _normalize_tool_input(tool_name: str, tool_input: Any) -> dict:
    if not isinstance(tool_input, dict):
        return {}

    normalized: dict[str, Any] = {}
    if tool_name in {"ask_research_sources", "get_research_pack", "query_research_source_data"}:
        for key in ("source_ids", "pack_ids"):
            if key in tool_input:
                normalized[key] = _normalize_source_ids(tool_input.get(key))
        if "question" in tool_input:
            normalized["question"] = str(tool_input.get("question") or "")
        if "pack_id" in tool_input:
            normalized["pack_id"] = str(tool_input.get("pack_id") or "").strip()
        if isinstance(tool_input.get("query"), dict):
            normalized["query"] = dict(tool_input["query"])
        if "limit" in tool_input:
            normalized["limit"] = tool_input.get("limit")
        return normalized

    artifact_id = tool_input.get("artifact_id")
    if artifact_id is not None:
        normalized["artifact_id"] = str(artifact_id)

    for key in ("fields", "metrics", "group_by"):
        values = tool_input.get(key)
        if isinstance(values, list):
            normalized[key] = [str(value) for value in values if value is not None and str(value).strip()]

    filters = tool_input.get("filters")
    if isinstance(filters, dict):
        normalized["filters"] = filters

    order_by = tool_input.get("order_by")
    if isinstance(order_by, list):
        cleaned_order = []
        for item in order_by:
            if not isinstance(item, dict):
                continue
            field = item.get("field")
            if field is None or not str(field).strip():
                continue
            direction = str(item.get("direction") or "desc").strip().lower()
            cleaned_order.append(
                {
                    "field": str(field),
                    "direction": "asc" if direction == "asc" else "desc",
                }
            )
        normalized["order_by"] = cleaned_order

    if "limit" in tool_input:
        normalized["limit"] = tool_input.get("limit")
    if tool_name == "query_artifact_subset_join":
        subset_artifact_id = tool_input.get("subset_artifact_id")
        if subset_artifact_id is not None:
            normalized["subset_artifact_id"] = str(subset_artifact_id)
        subset_filters = tool_input.get("subset_filters")
        if isinstance(subset_filters, dict):
            normalized["subset_filters"] = subset_filters
    if tool_name == "bridge_loc_ids":
        loc_ids = tool_input.get("loc_ids")
        if isinstance(loc_ids, list):
            normalized["loc_ids"] = [str(value) for value in loc_ids if value is not None and str(value).strip()]
        target_family = str(tool_input.get("target_family") or "geometry").strip().lower()
        normalized["target_family"] = target_family if target_family in {"geometry", "local"} else "geometry"
    if tool_name == "build_artifact_display_subset":
        if "fit" in tool_input:
            normalized["fit"] = bool(tool_input.get("fit"))
        if "context_visibility" in tool_input:
            visibility = str(tool_input.get("context_visibility") or "keep").strip().lower()
            normalized["context_visibility"] = visibility if visibility in {"keep", "replace"} else "keep"
        style = tool_input.get("style")
        if isinstance(style, dict):
            cleaned_style = {}
            fill_color = str(style.get("fill_color") or "").strip()
            stroke_color = str(style.get("stroke_color") or "").strip()
            if fill_color:
                cleaned_style["fill_color"] = fill_color
            if stroke_color:
                cleaned_style["stroke_color"] = stroke_color
            if cleaned_style:
                normalized["style"] = cleaned_style

    return normalized


def _jsonable(value: Any):
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        return _jsonable(value.item())
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _get_cached_result(session_id: str, request_key: str) -> dict | None:
    cache = session_manager.get(session_id)
    if not cache:
        return None
    result = cache.get_cached_result(request_key)
    if result is not None:
        return result
    root_key = str(request_key or "").split(":", 1)[0]
    return cache.get_cached_result(root_key) if root_key else None


def _artifact_is_live_source(artifact: dict | None) -> bool:
    return str((artifact or {}).get("hydration_mode") or "").strip().lower() == "live_source"


def _find_primary_parquet_for_live_source(source_id: str, metadata: dict) -> Path | None:
    source_dir = get_source_path(source_id)
    if source_dir is None:
        return None

    candidate_names: list[str] = []
    for rel_path in metadata.get("primary_files") or []:
        text = str(rel_path or "").strip()
        if text:
            candidate_names.append(text)

    files_section = metadata.get("files") if isinstance(metadata.get("files"), dict) else {}
    for file_info in files_section.values():
        if not isinstance(file_info, dict):
            continue
        file_name = str(file_info.get("name") or file_info.get("filename") or "").strip()
        if file_name:
            candidate_names.append(file_name)

    for rel_path in candidate_names:
        candidate = source_dir / rel_path
        if candidate.suffix.lower() == ".parquet":
            return candidate
    for fallback_name in ("data.parquet", "events.parquet", "USA.parquet"):
        candidate = source_dir / fallback_name
        if candidate.exists():
            return candidate
    return None


def _query_live_source_rows(
    artifact: dict,
    tool_input: dict,
    *,
    default_limit: int | None,
    maximum_limit: int | None,
    required_columns: list[str] | None = None,
) -> dict:
    if duckdb is None:
        return {"error": "duckdb_unavailable", "artifact_id": artifact.get("artifact_id")}

    source_id = str(artifact.get("source_id") or "").strip()
    metadata = load_source_metadata(source_id) or {}
    parquet_path = _find_primary_parquet_for_live_source(source_id, metadata)
    if parquet_path is None:
        return {"error": "artifact_data_unavailable", "artifact_id": artifact.get("artifact_id")}

    available_columns = parquet_columns(parquet_path)
    if not available_columns:
        return {"error": "artifact_data_unavailable", "artifact_id": artifact.get("artifact_id")}

    filters = tool_input.get("filters") or {}
    fields = [f for f in (tool_input.get("fields") or []) if f in available_columns]
    metrics = [m for m in (tool_input.get("metrics") or []) if m in available_columns]
    group_by = [g for g in (tool_input.get("group_by") or []) if g in available_columns]
    required = [column for column in (required_columns or []) if column in available_columns]

    selected = []
    for column in [*group_by, *fields, *metrics, *required]:
        if column and column not in selected:
            selected.append(column)
    if not selected:
        for fallback in ("loc_id", "name", "year", "timestamp"):
            if fallback in available_columns and fallback not in selected:
                selected.append(fallback)
    if not selected:
        return {"rows": [], "row_count": 0, "truncated": False}

    params: list[Any] = [path_to_uri(parquet_path)]
    where_parts: list[str] = []
    for field, expected in filters.items():
        if field not in available_columns:
            continue
        ident = quote_ident(field)
        if isinstance(expected, dict):
            if "hierarchy_any" in expected:
                hierarchy_parts = []
                for condition in expected.get("hierarchy_any") or []:
                    if not isinstance(condition, dict):
                        continue
                    if "eq" in condition:
                        hierarchy_parts.append(f"{ident} = ?")
                        params.append(condition["eq"])
                    if "starts_with" in condition:
                        prefix = str(condition.get("starts_with") or "").strip()
                        if prefix:
                            hierarchy_parts.append(f"{ident} LIKE ?")
                            params.append(prefix + "%")
                    if "prefix" in condition:
                        prefix = str(condition.get("prefix") or "").strip()
                        if prefix:
                            hierarchy_parts.append(f"{ident} LIKE ?")
                            params.append(prefix + "%")
                    if "contains" in condition:
                        needle = str(condition.get("contains") or "").strip()
                        if needle:
                            hierarchy_parts.append(f"lower(CAST({ident} AS VARCHAR)) LIKE ?")
                            params.append("%" + needle.lower() + "%")
                    if "contains_any" in condition:
                        for needle in condition.get("contains_any") or []:
                            text = str(needle or "").strip()
                            if text:
                                hierarchy_parts.append(f"lower(CAST({ident} AS VARCHAR)) LIKE ?")
                                params.append("%" + text.lower() + "%")
                    if "contains_segment" in condition:
                        segment = str(condition.get("contains_segment") or "").strip()
                        if segment:
                            hierarchy_parts.append(f"('-' || CAST({ident} AS VARCHAR) || '-') LIKE ?")
                            params.append("%-" + segment + "-%")
                if hierarchy_parts:
                    where_parts.append("(" + " OR ".join(hierarchy_parts) + ")")
                continue
            if "min" in expected:
                where_parts.append(f"{ident} >= ?")
                params.append(expected["min"])
            if "max" in expected:
                where_parts.append(f"{ident} <= ?")
                params.append(expected["max"])
            if "eq" in expected:
                where_parts.append(f"{ident} = ?")
                params.append(expected["eq"])
            if "in" in expected and expected["in"]:
                placeholders = ", ".join("?" for _ in expected["in"])
                where_parts.append(f"{ident} IN ({placeholders})")
                params.extend(expected["in"])
            if "starts_with" in expected:
                prefix = str(expected["starts_with"] or "").strip()
                if prefix:
                    where_parts.append(f"{ident} LIKE ?")
                    params.append(prefix + "%")
            if "prefix" in expected:
                prefix = str(expected["prefix"] or "").strip()
                if prefix:
                    where_parts.append(f"{ident} LIKE ?")
                    params.append(prefix + "%")
            if "starts_with_any" in expected and expected["starts_with_any"]:
                prefix_parts = []
                for prefix in expected["starts_with_any"]:
                    text = str(prefix or "").strip()
                    if not text:
                        continue
                    prefix_parts.append(f"{ident} LIKE ?")
                    params.append(text + "%")
                if prefix_parts:
                    where_parts.append("(" + " OR ".join(prefix_parts) + ")")
            if "contains" in expected:
                needle = str(expected["contains"] or "").strip()
                if needle:
                    where_parts.append(f"lower(CAST({ident} AS VARCHAR)) LIKE ?")
                    params.append("%" + needle.lower() + "%")
            if "contains_any" in expected and expected["contains_any"]:
                needle_parts = []
                for needle in expected["contains_any"]:
                    text = str(needle or "").strip()
                    if not text:
                        continue
                    needle_parts.append(f"lower(CAST({ident} AS VARCHAR)) LIKE ?")
                    params.append("%" + text.lower() + "%")
                if needle_parts:
                    where_parts.append("(" + " OR ".join(needle_parts) + ")")
        elif isinstance(expected, list) and expected:
            placeholders = ", ".join("?" for _ in expected)
            where_parts.append(f"{ident} IN ({placeholders})")
            params.extend(expected)
        else:
            where_parts.append(f"{ident} = ?")
            params.append(expected)

    if group_by:
        select_parts = [quote_ident(field) for field in group_by]
        for metric in metrics:
            ident = quote_ident(metric)
            select_parts.append(f"sum({ident}) AS {quote_ident(metric + '_sum')}")
            select_parts.append(f"avg({ident}) AS {quote_ident(metric + '_avg')}")
            select_parts.append(f"count({ident}) AS {quote_ident(metric + '_count')}")
            select_parts.append(f"min({ident}) AS {quote_ident(metric + '_min')}")
            select_parts.append(f"max({ident}) AS {quote_ident(metric + '_max')}")
        sql = f"SELECT {', '.join(select_parts)} FROM read_parquet(?)"
    else:
        sql = f"SELECT {', '.join(quote_ident(field) for field in selected)} FROM read_parquet(?)"

    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if group_by:
        sql += " GROUP BY " + ", ".join(quote_ident(field) for field in group_by)

    order_parts = []
    allowed_order_fields = set(selected) | {f"{metric}_{suffix}" for metric in metrics for suffix in ("sum", "avg", "count", "min", "max")}
    for sort in tool_input.get("order_by") or []:
        field = sort.get("field")
        if group_by and field in metrics:
            field = f"{field}_sum"
        direction = "ASC" if sort.get("direction") == "asc" else "DESC"
        if field in allowed_order_fields:
            order_parts.append(f"{quote_ident(field)} {direction}")
    if order_parts:
        sql += " ORDER BY " + ", ".join(order_parts)

    limit = _normalize_optional_limit(tool_input.get("limit"), maximum=maximum_limit)
    if limit is None:
        limit = default_limit

    count_sql = f"SELECT count(*) AS row_count FROM ({sql}) q"
    row_count_df = run_df(count_sql, params)
    row_count = int(row_count_df.iloc[0]["row_count"]) if not row_count_df.empty else 0
    if limit is not None:
        sql += " LIMIT ?"
        query_params = [*params, limit]
    else:
        query_params = params

    output_df = run_df(sql, query_params)
    output = output_df.to_dict("records") if not output_df.empty else []
    return apply_row_count_cap_to_payload({
        "rows": _jsonable(output),
        "row_count": row_count,
        "truncated": bool(limit is not None and row_count > limit),
    })


def _estimate_result_row_count(result: dict) -> int:
    count = 0
    geojson = result.get("geojson") if isinstance(result, dict) else None
    if isinstance(geojson, dict):
        features = geojson.get("features")
        if isinstance(features, list):
            count += len(features)
    year_data = result.get("year_data") if isinstance(result, dict) else None
    if isinstance(year_data, dict):
        for loc_map in year_data.values():
            if isinstance(loc_map, dict):
                count += len(loc_map)
    return count


def _artifact_query_too_broad_payload(
    artifact: dict,
    *,
    tool_name: str,
    estimated_rows: int,
) -> dict:
    artifact_id = str(artifact.get("artifact_id") or "").strip() or None
    return {
        "error": "artifact_query_too_broad",
        "tool_name": tool_name,
        "artifact_id": artifact_id,
        "row_count": int(estimated_rows),
        "max_input_rows": RESEARCH_TOOL_MAX_INPUT_ROWS,
        "message": (
            f"This loaded artifact is too large to materialize directly in Research "
            f"({estimated_rows:,} rows estimated, cap {RESEARCH_TOOL_MAX_INPUT_ROWS:,}). "
            "Narrow the filters, use a smaller corpus, or query a live source-backed artifact instead."
        ),
    }


def _rows_from_result(result: dict) -> list[dict]:
    rows = []
    feature_names = {}
    time_field = str(result.get("time_field") or "year").strip() or "year"
    for feature in (result.get("geojson") or {}).get("features") or []:
        props = dict(feature.get("properties") or {})
        loc_id = props.get("loc_id") or feature.get("id")
        if loc_id:
            feature_names[str(loc_id)] = props.get("name") or loc_id
        if not result.get("year_data"):
            rows.append(_jsonable(props))

    year_data = result.get("year_data") or {}
    for year, loc_map in year_data.items():
        for loc_id, metrics in (loc_map or {}).items():
            time_value = int(year) if str(year).isdigit() else year
            row = {"loc_id": loc_id, "name": feature_names.get(str(loc_id), loc_id), time_field: time_value}
            row.update(metrics or {})
            rows.append(_jsonable(row))
    return rows


def _feature_identity_from_props(props: dict, feature_id=None):
    for key in ("feature_id", "building_id", "BLDGIDENT", "OBJECTID", "GlobalID", "loc_id"):
        value = props.get(key)
        if value is not None and value != "":
            return str(value)
    if feature_id is not None and feature_id != "":
        return str(feature_id)
    return None


def _feature_lookup_from_result(result: dict) -> dict[str, dict]:
    lookup = {}
    for feature in (result.get("geojson") or {}).get("features") or []:
        props = dict(feature.get("properties") or {})
        identity = _feature_identity_from_props(props, feature.get("id"))
        if identity:
            lookup[identity] = _jsonable(feature)
    return lookup


def _normalize_limit(value) -> int:
    try:
        return max(1, min(int(value), 1000))
    except Exception:
        return 25


def _normalize_optional_limit(value, *, maximum: int | None = None) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = max(1, int(value))
    except Exception:
        return None
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _bridge_loc_ids(loc_ids: list[str], *, target_family: str = "geometry") -> dict:
    mappings = []
    for loc_id in loc_ids or []:
        source = str(loc_id or "").strip()
        if not source:
            continue
        bridged = bridge_loc_id_family(source, target_family=target_family)
        mappings.append(
            {
                "source_loc_id": source,
                "bridged_loc_id": bridged,
                "changed": bridged != source,
            }
        )
    changed_count = sum(1 for item in mappings if item.get("changed"))
    return {
        "target_family": target_family,
        "mapping_count": len(mappings),
        "changed_count": changed_count,
        "mappings": mappings,
        "foundation_helper_family": "country_crosswalks",
    }


def _filter_rows_python(rows: list[dict], filters: dict | None) -> list[dict]:
    if not filters:
        return rows

    def match_condition(actual: Any, condition: dict) -> bool:
        if not isinstance(condition, dict):
            return actual == condition
        if "eq" in condition and actual != condition["eq"]:
            return False
        if "min" in condition and (actual is None or actual < condition["min"]):
            return False
        if "max" in condition and (actual is None or actual > condition["max"]):
            return False
        if "in" in condition and actual not in condition["in"]:
            return False
        if "starts_with" in condition:
            prefix = str(condition["starts_with"] or "")
            if not prefix or actual is None or not str(actual).startswith(prefix):
                return False
        if "prefix" in condition:
            prefix = str(condition["prefix"] or "")
            if not prefix or actual is None or not str(actual).startswith(prefix):
                return False
        if "starts_with_any" in condition:
            prefixes = [str(prefix or "") for prefix in (condition["starts_with_any"] or []) if str(prefix or "")]
            if prefixes:
                if actual is None or not any(str(actual).startswith(prefix) for prefix in prefixes):
                    return False
        if "contains" in condition:
            needle = str(condition["contains"] or "").strip().lower()
            haystack = str(actual or "").strip().lower()
            if not needle or needle not in haystack:
                return False
        if "contains_any" in condition:
            needles = [str(value or "").strip().lower() for value in (condition["contains_any"] or []) if str(value or "").strip()]
            haystack = str(actual or "").strip().lower()
            if needles and not any(needle in haystack for needle in needles):
                return False
        if "contains_segment" in condition:
            segment = str(condition["contains_segment"] or "").strip()
            actual_text = str(actual or "").strip()
            if not segment or not actual_text:
                return False
            if f"-{segment}-" not in f"-{actual_text}-":
                return False
        return True

    def matches(row: dict) -> bool:
        for field, expected in filters.items():
            actual = row.get(field)
            if isinstance(expected, dict):
                if "hierarchy_any" in expected:
                    conditions = expected.get("hierarchy_any") or []
                    if conditions and not any(match_condition(actual, condition) for condition in conditions):
                        return False
                    continue
                if not match_condition(actual, expected):
                    return False
            elif isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    return [row for row in rows if matches(row)]


def _rows_for_artifact(
    session_id: str,
    artifact: dict,
    *,
    filters: dict | None = None,
    required_columns: list[str] | None = None,
) -> dict:
    tool_input = {"filters": filters or {}}
    if _artifact_is_live_source(artifact):
        return _query_live_source_rows(
            artifact,
            tool_input,
            default_limit=None,
            maximum_limit=None,
            required_columns=required_columns,
        )
    result = _get_cached_result(session_id, artifact.get("request_key"))
    if not result:
        return {"error": "artifact_data_unavailable", "artifact_id": artifact.get("artifact_id")}
    rows = _rows_from_result(result)
    filtered_rows = _filter_rows_python(rows, filters or {})
    if required_columns:
        trimmed_rows = []
        for row in filtered_rows:
            trimmed_rows.append({key: row.get(key) for key in required_columns if key in row})
        filtered_rows = trimmed_rows
    return {"rows": filtered_rows, "row_count": len(filtered_rows), "truncated": False}


def _query_rows_python(
    rows: list[dict],
    tool_input: dict,
    *,
    default_limit: int | None = 25,
    maximum_limit: int | None = 1000,
) -> dict:
    rows = _filter_rows_python(rows, tool_input.get("filters"))
    fields = tool_input.get("fields") or []
    metrics = tool_input.get("metrics") or []
    group_by = tool_input.get("group_by") or []
    selected = [f for f in [*group_by, *fields, *metrics] if f]
    if not selected and rows:
        selected = list(rows[0].keys())

    if group_by:
        grouped: dict[tuple, dict] = {}
        for row in rows:
            key = tuple(row.get(field) for field in group_by)
            bucket = grouped.setdefault(key, {field: row.get(field) for field in group_by})
            for metric in metrics:
                value = row.get(metric)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    state = bucket.setdefault(f"_{metric}_values", [])
                    state.append(value)
        output = []
        for bucket in grouped.values():
            row = {field: bucket.get(field) for field in group_by}
            for metric in metrics:
                values = bucket.get(f"_{metric}_values", [])
                row[f"{metric}_sum"] = sum(values) if values else None
                row[f"{metric}_avg"] = sum(values) / len(values) if values else None
                row[f"{metric}_count"] = len(values)
                row[f"{metric}_min"] = min(values) if values else None
                row[f"{metric}_max"] = max(values) if values else None
            output.append(row)
        rows = output
    else:
        rows = [{field: row.get(field) for field in selected if field in row} for row in rows]

    for sort in reversed(tool_input.get("order_by") or []):
        field = sort.get("field")
        if group_by and field in metrics:
            field = f"{field}_avg"
        reverse = sort.get("direction", "desc") == "desc"
        if field:
            rows.sort(key=lambda row: (row.get(field) is None, row.get(field)), reverse=reverse)

    limit = _normalize_optional_limit(tool_input.get("limit"), maximum=maximum_limit)
    if limit is None:
        limit = default_limit
    if limit is None:
        return {"rows": rows, "row_count": len(rows), "truncated": False}
    return apply_row_count_cap_to_payload({
        "rows": rows[:limit],
        "row_count": len(rows),
        "truncated": len(rows) > limit,
    })


def _query_artifact_subset_join(
    session_id: str,
    artifact: dict,
    subset_artifact: dict,
    tool_input: dict,
) -> dict:
    subset_filters = tool_input.get("subset_filters") if isinstance(tool_input.get("subset_filters"), dict) else {}
    subset_rows_result = _rows_for_artifact(
        session_id,
        subset_artifact,
        filters=subset_filters,
        required_columns=["loc_id"],
    )
    if subset_rows_result.get("error"):
        return subset_rows_result

    subset_loc_ids = unique_loc_ids_from_rows(subset_rows_result.get("rows") or [])

    filters = dict(tool_input.get("filters") or {})
    filters = apply_loc_id_subset_filter(filters, subset_loc_ids)
    joined_tool_input = {
        "filters": filters,
        "fields": list(tool_input.get("fields") or []),
        "metrics": list(tool_input.get("metrics") or []),
        "group_by": list(tool_input.get("group_by") or []),
        "order_by": list(tool_input.get("order_by") or []),
    }
    if "limit" in tool_input:
        joined_tool_input["limit"] = tool_input.get("limit")

    if _artifact_is_live_source(artifact):
        query_result = _query_live_source_rows(
            artifact,
            joined_tool_input,
            default_limit=25,
            maximum_limit=1000,
        )
    else:
        result = _get_cached_result(session_id, artifact.get("request_key"))
        if not result:
            return {"error": "artifact_data_unavailable", "artifact_id": artifact.get("artifact_id")}
        estimated_rows = _estimate_result_row_count(result)
        if estimated_rows > RESEARCH_TOOL_MAX_INPUT_ROWS:
            return _artifact_query_too_broad_payload(
                artifact,
                tool_name="query_artifact_subset_join",
                estimated_rows=estimated_rows,
            )
        rows = _rows_from_result(result)
        query_result = _query_rows_duckdb(rows, joined_tool_input, default_limit=25, maximum_limit=1000)

    query_result["subset_artifact_id"] = subset_artifact.get("artifact_id")
    query_result["subset_row_count"] = int(subset_rows_result.get("row_count", 0) or 0)
    query_result["subset_loc_id_count"] = len(subset_loc_ids)
    return query_result


def _quote_identifier(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _query_rows_duckdb(
    rows: list[dict],
    tool_input: dict,
    *,
    default_limit: int | None = 25,
    maximum_limit: int | None = 1000,
) -> dict:
    if duckdb is None:
        return _query_rows_python(rows, tool_input, default_limit=default_limit, maximum_limit=maximum_limit)
    try:
        import pandas as pd
    except Exception:
        return _query_rows_python(rows, tool_input, default_limit=default_limit, maximum_limit=maximum_limit)

    if not rows:
        return {"rows": [], "row_count": 0, "truncated": False}

    df = pd.DataFrame(rows)
    con = build_guarded_connection(database=":memory:", configure_cloud=False)
    try:
        con.register("artifact_rows", df)
        where_parts = []
        params = []

        def comparison_identifier(field: str, expected: dict, identifier: str) -> str:
            """Cast a text-encoded numeric column only for numeric ranges.

            Hydrated artifacts preserve source values, and some otherwise
            yearly datasets therefore carry ``year`` as a VARCHAR. DuckDB
            will not compare that to the numeric bounds the Research model
            emits. Detect a wholly numeric column rather than guessing from
            its name, so timestamps and ordinary text retain their native
            comparison semantics.
            """
            if not any(key in expected for key in ("min", "max")):
                return identifier
            raw_values = df[field].dropna()
            if raw_values.empty:
                return identifier
            coerced = pd.to_numeric(raw_values, errors="coerce")
            if len(coerced) and coerced.notna().all():
                return f"TRY_CAST({identifier} AS DOUBLE)"
            return identifier

        for field, expected in (tool_input.get("filters") or {}).items():
            if field not in df.columns:
                continue
            ident = _quote_identifier(field)
            if isinstance(expected, dict):
                comparison_ident = comparison_identifier(field, expected, ident)
                if "hierarchy_any" in expected:
                    hierarchy_parts = []
                    for condition in expected.get("hierarchy_any") or []:
                        if not isinstance(condition, dict):
                            continue
                        if "eq" in condition:
                            hierarchy_parts.append(f"{ident} = ?")
                            params.append(condition["eq"])
                        if "starts_with" in condition:
                            prefix = str(condition.get("starts_with") or "").strip()
                            if prefix:
                                hierarchy_parts.append(f"{ident} LIKE ?")
                                params.append(prefix + "%")
                        if "prefix" in condition:
                            prefix = str(condition.get("prefix") or "").strip()
                            if prefix:
                                hierarchy_parts.append(f"{ident} LIKE ?")
                                params.append(prefix + "%")
                        if "contains" in condition:
                            needle = str(condition.get("contains") or "").strip()
                            if needle:
                                hierarchy_parts.append(f"lower(CAST({ident} AS VARCHAR)) LIKE ?")
                                params.append("%" + needle.lower() + "%")
                        if "contains_any" in condition:
                            for needle in condition.get("contains_any") or []:
                                text = str(needle or "").strip()
                                if text:
                                    hierarchy_parts.append(f"lower(CAST({ident} AS VARCHAR)) LIKE ?")
                                    params.append("%" + text.lower() + "%")
                        if "contains_segment" in condition:
                            segment = str(condition.get("contains_segment") or "").strip()
                            if segment:
                                hierarchy_parts.append(f"('-' || CAST({ident} AS VARCHAR) || '-') LIKE ?")
                                params.append("%-" + segment + "-%")
                    if hierarchy_parts:
                        where_parts.append("(" + " OR ".join(hierarchy_parts) + ")")
                    continue
                if "min" in expected:
                    where_parts.append(f"{comparison_ident} >= ?")
                    params.append(expected["min"])
                if "max" in expected:
                    where_parts.append(f"{comparison_ident} <= ?")
                    params.append(expected["max"])
                if "eq" in expected:
                    where_parts.append(f"{ident} = ?")
                    params.append(expected["eq"])
                if "in" in expected and expected["in"]:
                    placeholders = ", ".join("?" for _ in expected["in"])
                    where_parts.append(f"{ident} IN ({placeholders})")
                    params.extend(expected["in"])
                if "starts_with" in expected:
                    prefix = str(expected["starts_with"] or "").strip()
                    if prefix:
                        where_parts.append(f"{ident} LIKE ?")
                        params.append(prefix + "%")
                if "prefix" in expected:
                    prefix = str(expected["prefix"] or "").strip()
                    if prefix:
                        where_parts.append(f"{ident} LIKE ?")
                        params.append(prefix + "%")
                if "starts_with_any" in expected and expected["starts_with_any"]:
                    prefix_parts = []
                    for prefix in expected["starts_with_any"]:
                        text = str(prefix or "").strip()
                        if not text:
                            continue
                        prefix_parts.append(f"{ident} LIKE ?")
                        params.append(text + "%")
                    if prefix_parts:
                        where_parts.append("(" + " OR ".join(prefix_parts) + ")")
                if "contains" in expected:
                    needle = str(expected["contains"] or "").strip()
                    if needle:
                        where_parts.append(f"lower(CAST({ident} AS VARCHAR)) LIKE ?")
                        params.append("%" + needle.lower() + "%")
                if "contains_any" in expected and expected["contains_any"]:
                    needle_parts = []
                    for needle in expected["contains_any"]:
                        text = str(needle or "").strip()
                        if not text:
                            continue
                        needle_parts.append(f"lower(CAST({ident} AS VARCHAR)) LIKE ?")
                        params.append("%" + text.lower() + "%")
                    if needle_parts:
                        where_parts.append("(" + " OR ".join(needle_parts) + ")")
            elif isinstance(expected, list) and expected:
                placeholders = ", ".join("?" for _ in expected)
                where_parts.append(f"{ident} IN ({placeholders})")
                params.extend(expected)
            else:
                where_parts.append(f"{ident} = ?")
                params.append(expected)

        fields = [f for f in (tool_input.get("fields") or []) if f in df.columns]
        metrics = [m for m in (tool_input.get("metrics") or []) if m in df.columns]
        group_by = [g for g in (tool_input.get("group_by") or []) if g in df.columns]
        if group_by:
            select_parts = [_quote_identifier(field) for field in group_by]
            for metric in metrics:
                ident = _quote_identifier(metric)
                select_parts.append(f"sum({ident}) AS {_quote_identifier(metric + '_sum')}")
                select_parts.append(f"avg({ident}) AS {_quote_identifier(metric + '_avg')}")
                select_parts.append(f"count({ident}) AS {_quote_identifier(metric + '_count')}")
                select_parts.append(f"min({ident}) AS {_quote_identifier(metric + '_min')}")
                select_parts.append(f"max({ident}) AS {_quote_identifier(metric + '_max')}")
            sql = f"SELECT {', '.join(select_parts)} FROM artifact_rows"
        else:
            selected = [*fields, *metrics] or list(df.columns)
            sql = f"SELECT {', '.join(_quote_identifier(field) for field in selected if field in df.columns)} FROM artifact_rows"

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        if group_by:
            sql += " GROUP BY " + ", ".join(_quote_identifier(field) for field in group_by)

        order_parts = []
        for sort in tool_input.get("order_by") or []:
            field = sort.get("field")
            if group_by and field in metrics:
                field = f"{field}_sum"
            if isinstance(field, str) and field not in df.columns:
                for suffix in ("_sum", "_avg", "_count", "_min", "_max"):
                    if field.endswith(suffix):
                        base_field = field[: -len(suffix)]
                        if group_by and base_field in metrics:
                            field = f"{base_field}{suffix}"
                            break
                        if base_field in df.columns:
                            field = base_field
                            break
            direction = "ASC" if sort.get("direction") == "asc" else "DESC"
            allowed = (
                set(df.columns)
                | {f"{m}_sum" for m in metrics}
                | {f"{m}_avg" for m in metrics}
                | {f"{m}_count" for m in metrics}
                | {f"{m}_min" for m in metrics}
                | {f"{m}_max" for m in metrics}
            )
            if field in allowed:
                order_parts.append(f"{_quote_identifier(field)} {direction}")
        if order_parts:
            sql += " ORDER BY " + ", ".join(order_parts)

        limit = _normalize_optional_limit(tool_input.get("limit"), maximum=maximum_limit)
        if limit is None:
            limit = default_limit
        count_sql = f"SELECT count(*) AS row_count FROM ({sql}) q"
        row_count = con.execute(count_sql, params).fetchone()[0]
        if limit is not None:
            sql += f" LIMIT {limit}"
        output = con.execute(sql, params).fetchdf().to_dict("records")
        return apply_row_count_cap_to_payload({
            "rows": _jsonable(output),
            "row_count": row_count,
            "truncated": bool(limit is not None and row_count > limit),
        })
    finally:
        con.close()


def _loc_id_depth(loc_id: Any) -> int | None:
    text = str(loc_id or "").strip()
    if not text:
        return None
    return text.count("-")


def _rewrite_hierarchical_loc_id_filters(tool_input: dict) -> dict:
    if not isinstance(tool_input, dict):
        return {}

    filters = tool_input.get("filters")
    if not isinstance(filters, dict) or "loc_id" not in filters:
        return tool_input

    expected = filters.get("loc_id")
    hierarchy_conditions: list[dict[str, str]] = []

    def add_loc_id(value: Any):
        text = str(value or "").strip()
        if not text:
            return
        depth = _loc_id_depth(text)
        exact_condition = {"eq": text}
        if exact_condition not in hierarchy_conditions:
            hierarchy_conditions.append(exact_condition)
        if depth is not None and depth < 5:
            descendant_condition = {"starts_with": text + "-"}
            if descendant_condition not in hierarchy_conditions:
                hierarchy_conditions.append(descendant_condition)
        if "-" not in text:
            segment_condition = {"contains_segment": text}
            if segment_condition not in hierarchy_conditions:
                hierarchy_conditions.append(segment_condition)

    if isinstance(expected, dict):
        if "eq" in expected:
            add_loc_id(expected.get("eq"))
        elif "in" not in expected and "starts_with" not in expected and "starts_with_any" not in expected:
            return tool_input
        for value in expected.get("in") or []:
            add_loc_id(value)
        if "starts_with" in expected:
            prefix = str(expected.get("starts_with") or "").strip()
            if prefix:
                condition = {"starts_with": prefix}
                if condition not in hierarchy_conditions:
                    hierarchy_conditions.append(condition)
        for prefix in expected.get("starts_with_any") or []:
            text = str(prefix or "").strip()
            if text:
                condition = {"starts_with": text}
                if condition not in hierarchy_conditions:
                    hierarchy_conditions.append(condition)
    elif isinstance(expected, list):
        for value in expected:
            add_loc_id(value)
    else:
        add_loc_id(expected)

    if not hierarchy_conditions:
        return tool_input

    rewritten = {
        key: value
        for key, value in filters.items()
        if key != "loc_id"
    }
    rewritten["loc_id"] = {"hierarchy_any": hierarchy_conditions}
    patched = dict(tool_input)
    patched["filters"] = rewritten
    return patched


_NON_METRIC_ROW_KEYS = {"loc_id", "name", "geography_kind", "admin_level_num"}
_NON_VALUE_FIELD_KEYS = _NON_METRIC_ROW_KEYS | {"year", "timestamp", "time", "data_time"}


def _coerce_year_token(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value == int(value) else None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 4 and text[:4].lstrip("-").isdigit():
        try:
            return int(text[:4])
        except ValueError:
            return None
    if text.lstrip("-").isdigit():
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _should_use_yearly_time_keys(rows: list[dict], time_field: str, temporal_granularity: str) -> bool:
    if temporal_granularity in {"yearly", "annual"}:
        return True
    if time_field == "year":
        return True

    raw_values: list = []
    coerced_years: list[int] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        value = row.get(time_field)
        if value is None or value == "":
            continue
        raw_values.append(value)
        year_value = _coerce_year_token(value)
        if year_value is None:
            return False
        coerced_years.append(year_value)

    if not raw_values or not coerced_years:
        return False

    raw_distinct = {str(value) for value in raw_values}
    year_distinct = set(coerced_years)

    # Annual timestamp-like series (e.g. pandas Timestamp at Jan 1 each year)
    # should collapse cleanly to one unique year token per unique raw token.
    return len(raw_distinct) == len(year_distinct)


def _infer_primary_metric(matched_rows: list, time_field: str, requested: str | None) -> str:
    if requested:
        return str(requested)
    for row in matched_rows:
        for key, value in (row or {}).items():
            if key in _NON_VALUE_FIELD_KEYS or key == time_field:
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return str(key)
    return ""


def _expand_display_rows_to_full_time_history(
    artifact: dict,
    tool_input: dict,
    matched_rows: list[dict],
    *,
    source_rows: list[dict] | None = None,
) -> list[dict]:
    time_field = str((artifact or {}).get("time_field") or "year").strip() or "year"
    if not matched_rows or not time_field:
        return matched_rows

    filters = tool_input.get("filters") or {}

    loc_ids: list[str] = []
    for row in matched_rows:
        loc_id = row.get("loc_id")
        if loc_id is None:
            continue
        text = str(loc_id)
        if text and text not in loc_ids:
            loc_ids.append(text)
    if not loc_ids:
        return matched_rows

    # For a narrowly selected set of locations, display should reopen the full
    # local time history even if the ranking/query step used an explicit year
    # filter (e.g. "winner in 2023, then show it on the map"). For broad
    # many-feature displays, preserve the caller's explicit time slice.
    if time_field in filters and len(loc_ids) > 25:
        return matched_rows

    if source_rows is not None:
        expanded = []
        for row in source_rows:
            loc_id = row.get("loc_id")
            if loc_id is None or str(loc_id) not in loc_ids:
                continue
            expanded.append(row)
        return expanded or matched_rows

    if not _artifact_is_live_source(artifact):
        return matched_rows

    expanded_tool_input = {
        "filters": {
            key: value
            for key, value in filters.items()
            if key != "loc_id" and key != time_field
        },
        "fields": list(tool_input.get("fields") or []),
        "metrics": list(tool_input.get("metrics") or []),
    }
    expanded_tool_input["filters"]["loc_id"] = {"in": loc_ids}

    expanded_result = _query_live_source_rows(
        artifact,
        expanded_tool_input,
        default_limit=None,
        maximum_limit=None,
        required_columns=["loc_id", time_field],
    )
    expanded_rows = expanded_result.get("rows") or []
    return expanded_rows or matched_rows


def _build_research_map_payload(
    matched_rows: list,
    query_result: dict,
    artifact: dict,
    tool_input: dict,
    *,
    feature_lookup: dict | None = None,
    time_field_hint: str | None = None,
    source_result: dict | None = None,
) -> dict:
    """Produce an Explore-shaped data payload from research tool output.

    Output shape matches what Explore's renderStandardDataPayload expects:
    {data_type, source_id, geographic_level, geojson, loc_ids, year_data?, years?,
    metric?, fit, context_visibility, rows, row_count, truncated, ...}

    The frontend treats this exactly like an Explore chat response, so the choropleth,
    TimeSlider, popup, and hover all work without research-specific renderers.
    """
    matched_rows = _expand_display_rows_to_full_time_history(
        artifact,
        tool_input,
        matched_rows,
        source_rows=_rows_from_result(source_result) if isinstance(source_result, dict) else None,
    )
    feature_lookup = feature_lookup or {}
    declared_data_type = str(artifact.get("data_type") or "data").lower()
    source_id = artifact.get("source_id")
    time_field = str(
        time_field_hint
        or artifact.get("time_field")
        or "year"
    ).strip() or "year"
    temporal_coverage = source_result.get("temporal_coverage") if isinstance(source_result, dict) and isinstance(source_result.get("temporal_coverage"), dict) else {}
    temporal_granularity = str(temporal_coverage.get("granularity") or "").strip().lower()
    use_yearly_keys = _should_use_yearly_time_keys(matched_rows, time_field, temporal_granularity)
    geographic_level = (
        artifact.get("geographic_level")
        or (matched_rows[0].get("geography_kind") if matched_rows else None)
    )

    # Group rows by loc_id so one geometry feature -> one entry, regardless of how many
    # time-rows feed it. This fixes the prior "22 references to the same Python dict"
    # bug for multi-year metric queries.
    loc_id_order: list[str] = []
    rows_by_loc_id: dict[str, list[dict]] = {}
    for row in matched_rows:
        loc_id = row.get("loc_id")
        if loc_id is None:
            continue
        key = str(loc_id)
        bucket = rows_by_loc_id.get(key)
        if bucket is None:
            rows_by_loc_id[key] = [row]
            loc_id_order.append(key)
        else:
            bucket.append(row)

    # Resolve geometry. Prefer features already in the artifact's cached geojson;
    # fall back to the selection-geometry path for metric/live-source artifacts.
    feature_by_loc_id: dict[str, dict] = {}
    for key, lookup_feature in feature_lookup.items():
        props = (lookup_feature or {}).get("properties") or {}
        lid = props.get("loc_id") or key
        if lid is not None and (lookup_feature or {}).get("geometry"):
            feature_by_loc_id.setdefault(str(lid), _jsonable(lookup_feature))

    missing = [lid for lid in loc_id_order if lid not in feature_by_loc_id]
    if missing:
        selection_geojson = get_selection_geometries(missing)
        for feature in (selection_geojson or {}).get("features") or []:
            props = dict(feature.get("properties") or {})
            lid = props.get("loc_id")
            if lid is None:
                continue
            feature_by_loc_id[str(lid)] = _jsonable(feature)

    # Build time_data for time-varying data families. time_data is keyed by the
    # time value as a string, then by loc_id, with the full per-row metric bundle
    # as the value (so the popup can show every metric per year, not just the
    # primary).
    time_data: dict[str, dict[str, dict]] = {}
    years_seen: list[str] = []
    has_time_axis = False
    for loc_id in loc_id_order:
        for row in rows_by_loc_id[loc_id]:
            time_value = row.get(time_field)
            if time_value is None or time_value == "":
                continue
            has_time_axis = True
            normalized_time_value = time_value
            if use_yearly_keys:
                normalized_time_value = _coerce_year_token(time_value)
                if normalized_time_value is None:
                    normalized_time_value = _coerce_year_token(row.get("year"))
                if normalized_time_value is None:
                    continue
            time_key = str(normalized_time_value)
            bucket = time_data.setdefault(time_key, {})
            metrics_dict = {
                k: v for k, v in row.items()
                if k not in _NON_VALUE_FIELD_KEYS and k != time_field
            }
            bucket[loc_id] = metrics_dict
            if time_key not in years_seen:
                years_seen.append(time_key)

    years_sorted = sorted(years_seen, key=lambda y: (len(y), y))

    # Build one feature per loc_id. Attach the most recent row's values as
    # feature.properties so the static (non-animated) view has reasonable defaults
    # and so the popup builder has at-rest values to show.
    features = []
    for loc_id in loc_id_order:
        feature = feature_by_loc_id.get(loc_id)
        if not feature:
            continue
        loc_rows = rows_by_loc_id[loc_id]
        latest_row = loc_rows[-1]
        props = dict(feature.get("properties") or {})
        for k, v in (latest_row or {}).items():
            props[k] = v
        props.setdefault("loc_id", loc_id)
        feature["properties"] = _jsonable(props)
        features.append(feature)

    metric = _infer_primary_metric(matched_rows, time_field, tool_input.get("metric"))

    # Classify the payload by data shape, not by the artifact's stamped data_type.
    # The hydration layer stamps everything `metrics`, but a designation list
    # like usa_opportunity_zones is structurally a geometry overlay (loc_ids +
    # attribute labels, no time axis, no metric values). See MAPPING.md
    # "Queryable Geometry Overlays" and data_pipeline.md "Attribute-Overlay
    # Datasets".
    if has_time_axis:
        data_type = "metrics"
    elif declared_data_type == "events":
        data_type = "events"
    else:
        data_type = "geometry"

    payload: dict = {
        "artifact_id": artifact.get("artifact_id"),
        "source_id": source_id,
        "data_type": data_type,
        "declared_data_type": declared_data_type,
        "geographic_level": geographic_level,
        "geojson": {"type": "FeatureCollection", "features": features},
        "loc_ids": loc_id_order,
        "feature_count": len(features),
        "fit": bool(tool_input.get("fit", True)),
        "context_visibility": str(tool_input.get("context_visibility") or "keep"),
        "rows": matched_rows,
        "row_count": int(query_result.get("row_count", 0) or 0),
        "truncated": bool(query_result.get("truncated")),
    }
    if has_time_axis:
        # Coerce time keys to integers when possible so the TimeSlider's
        # year-based min/max math works for SDG/LODES-style yearly data. For
        # non-numeric time keys (date strings, ISO weeks, months), fall back to
        # string-sorted boundaries which the slider walks as labels.
        numeric_years: list[int] = []
        for token in years_sorted:
            try:
                numeric_years.append(int(token))
            except (ValueError, TypeError):
                numeric_years = []
                break

        # Collect every metric key that appears in time_data so the slider's
        # metric-picker UI sees the full set.
        metric_keys_seen: set[str] = set()
        for loc_bucket in time_data.values():
            for metrics_dict in loc_bucket.values():
                for k, v in (metrics_dict or {}).items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        metric_keys_seen.add(str(k))
        available_metrics = sorted(metric_keys_seen)

        primary_metric = metric or (available_metrics[0] if available_metrics else "")

        artifact_metric_year_ranges = artifact.get("metric_year_ranges") if isinstance(artifact.get("metric_year_ranges"), dict) else {}
        metric_year_ranges = {}
        for metric_name in available_metrics:
            if metric_name in artifact_metric_year_ranges and isinstance(artifact_metric_year_ranges[metric_name], dict):
                metric_year_ranges[str(metric_name)] = _jsonable(artifact_metric_year_ranges[metric_name])
        if not metric_year_ranges:
            metric_year_ranges = build_metric_year_ranges(
                source_result if isinstance(source_result, dict) else {},
                available_metrics,
                fallback_min=(numeric_years[0] if numeric_years else None),
                fallback_max=(numeric_years[-1] if numeric_years else None),
                fallback_available_years=numeric_years,
            )

        canonical_time_range = None
        if numeric_years:
            canonical_time_range = {
                "min": numeric_years[0],
                "max": numeric_years[-1],
                "available": numeric_years,
                "granularity": "yearly" if use_yearly_keys else None,
                "useTimestamps": False if use_yearly_keys else None,
            }
        else:
            canonical_time_range = {
                "min": years_sorted[0],
                "max": years_sorted[-1],
                "available": years_sorted,
                "granularity": "yearly" if use_yearly_keys else None,
                "useTimestamps": False if use_yearly_keys else None,
            }

        payload["time_data"] = time_data
        payload["time_range"] = canonical_time_range
        # TEMPORARY MIRRORS: remove after all consumers switch to canonical time_*.
        payload["year_data"] = time_data
        payload["years"] = years_sorted
        payload["time_field"] = "year" if use_yearly_keys else time_field
        payload["multi_year"] = len(years_sorted) > 1
        if numeric_years:
            payload["year_range"] = {
                "min": numeric_years[0],
                "max": numeric_years[-1],
                "available_years": numeric_years,
                "granularity": "yearly" if use_yearly_keys else None,
                "useTimestamps": False if use_yearly_keys else None,
            }
        else:
            payload["year_range"] = {
                "min": years_sorted[0],
                "max": years_sorted[-1],
                "available_years": years_sorted,
                "granularity": "yearly" if use_yearly_keys else None,
                "useTimestamps": False if use_yearly_keys else None,
            }
        payload["metric"] = primary_metric
        payload["metric_key"] = primary_metric
        payload["available_metrics"] = available_metrics
        payload["metric_time_ranges"] = metric_year_ranges
        payload["metric_year_ranges"] = metric_year_ranges
        if artifact.get("scene_periods"):
            payload["scene_periods"] = _jsonable(artifact.get("scene_periods"))
        if artifact.get("raster_clip_levels"):
            payload["raster_clip_levels"] = _jsonable(artifact.get("raster_clip_levels"))
    if isinstance(tool_input.get("style"), dict):
        payload["style"] = dict(tool_input["style"])

    logger.info(
        "Research display payload source=%s artifact=%s data_type=%s features=%s loc_ids=%s years=%s truncated=%s",
        source_id,
        artifact.get("artifact_id"),
        data_type,
        len(features),
        len(loc_id_order),
        len(years_sorted),
        payload["truncated"],
    )
    return payload


def _build_display_subset(result: dict, artifact: dict, tool_input: dict) -> dict:
    explicit_limit = _normalize_optional_limit(tool_input.get("limit"), maximum=None)
    force_large_display = bool(tool_input.get("_force_large_display"))
    warning_policy = tool_input.get("_display_warning_policy") or DEFAULT_DISPLAY_WARNING_POLICY
    estimated_rows = _estimate_result_row_count(result)
    interrupted_payload = interrupt_display_payload_if_needed(
        estimated_rows,
        policy=warning_policy,
        force_large_display=force_large_display,
        artifact_id=artifact.get("artifact_id"),
    )
    if explicit_limit is None and interrupted_payload is not None:
        return interrupted_payload
    if estimated_rows > RESEARCH_TOOL_MAX_INPUT_ROWS:
        return _artifact_query_too_broad_payload(
            artifact,
            tool_name="build_artifact_display_subset",
            estimated_rows=estimated_rows,
        )

    rows = _rows_from_result(result)
    query_default_limit = None if explicit_limit is not None else (warning_policy.hard_cap + 1)
    query_result = _query_rows_duckdb(rows, tool_input, default_limit=query_default_limit, maximum_limit=None)
    row_count = int(query_result.get("row_count", 0) or 0)
    interrupted_payload = interrupt_display_payload_if_needed(
        row_count,
        policy=warning_policy,
        force_large_display=force_large_display,
        artifact_id=artifact.get("artifact_id"),
    )
    if explicit_limit is None and interrupted_payload is not None:
        return interrupted_payload
    matched_rows = query_result.get("rows") or []
    feature_lookup = _feature_lookup_from_result(result)
    return _build_research_map_payload(
        matched_rows,
        query_result,
        artifact,
        tool_input,
        feature_lookup=feature_lookup,
        time_field_hint=result.get("time_field"),
        source_result=result,
    )


def execute_research_tool(
    session_id: str,
    tool_name: str,
    tool_input: dict,
    *,
    force_large_display: bool = False,
    display_warning_policy=DEFAULT_DISPLAY_WARNING_POLICY,
    original_query: str = "",
) -> dict:
    try:
        tool_input = _normalize_tool_input(tool_name, tool_input)
        if tool_name == "ask_research_sources":
            return _bind_research_sources(session_id, tool_input)
        if tool_name == "get_research_pack":
            return _get_bound_research_pack(session_id, tool_input)
        if tool_name == "query_research_source_data":
            return _query_bound_research_source(session_id, tool_input, original_query=original_query)
        if tool_name == "bridge_loc_ids":
            loc_ids = tool_input.get("loc_ids") or []
            artifact_id = tool_input.get("artifact_id")
            if artifact_id and not corpus_registry.get_artifact(session_id, artifact_id):
                return {"error": "artifact_not_found", "artifact_id": artifact_id}
            return _bridge_loc_ids(loc_ids, target_family=str(tool_input.get("target_family") or "geometry"))
        if tool_name == "list_artifacts":
            return {"artifacts": corpus_registry.list_artifacts(session_id)}

        artifact_id = tool_input.get("artifact_id")
        artifact = corpus_registry.get_artifact(session_id, artifact_id) if artifact_id else None
        if not artifact:
            return {"error": "artifact_not_found", "artifact_id": artifact_id}

        tool_input = _rewrite_hierarchical_loc_id_filters(tool_input)

        if tool_name == "describe_artifact":
            artifact.pop("order", None)
            source_id = str(artifact.get("source_id") or "").strip()
            metadata = load_source_metadata(source_id) or {}
            reference_summary = build_reference_summary(load_source_reference(source_id) or {})
            artifact["foundation_helpers"] = {
                "available_mode_profile": (get_foundation_helper_registry().get("mode_profiles") or {}).get("research", []),
                "loc_id_bridge_available": True,
            }
            artifact["source_guidance"] = {
                "routing_hints": get_routing_hints(metadata),
                "routing_guidance": build_source_routing_guidance(metadata, source_id),
                "reference_summary": reference_summary,
            }
            return {"artifact": artifact}

        if tool_name == "query_artifact_slice":
            if _artifact_is_live_source(artifact):
                query_result = _query_live_source_rows(artifact, tool_input, default_limit=25, maximum_limit=1000)
                return {
                    "artifact_id": artifact_id,
                    "fields": artifact.get("fields", []),
                    **query_result,
                }
            result = _get_cached_result(session_id, artifact.get("request_key"))
            if not result:
                return {"error": "artifact_data_unavailable", "artifact_id": artifact_id}
            estimated_rows = _estimate_result_row_count(result)
            if estimated_rows > RESEARCH_TOOL_MAX_INPUT_ROWS:
                return _artifact_query_too_broad_payload(
                    artifact,
                    tool_name="query_artifact_slice",
                    estimated_rows=estimated_rows,
                )
            rows = _rows_from_result(result)
            query_result = _query_rows_duckdb(rows, tool_input, default_limit=25, maximum_limit=1000)
            return {
                "artifact_id": artifact_id,
                "fields": artifact.get("fields", []),
                **query_result,
            }

        if tool_name == "query_artifact_subset_join":
            subset_artifact_id = tool_input.get("subset_artifact_id")
            subset_artifact = corpus_registry.get_artifact(session_id, subset_artifact_id) if subset_artifact_id else None
            if not subset_artifact:
                return {"error": "artifact_not_found", "artifact_id": subset_artifact_id}
            query_result = _query_artifact_subset_join(session_id, artifact, subset_artifact, tool_input)
            return {
                "artifact_id": artifact_id,
                "fields": artifact.get("fields", []),
                **query_result,
            }

        if tool_name == "build_artifact_display_subset":
            if _artifact_is_live_source(artifact):
                if force_large_display:
                    tool_input = dict(tool_input or {})
                    tool_input["_force_large_display"] = True
                tool_input["_display_warning_policy"] = display_warning_policy
                explicit_limit = _normalize_optional_limit(tool_input.get("limit"), maximum=None)
                query_default_limit = None if explicit_limit is not None else (display_warning_policy.hard_cap + 1)
                query_result = _query_live_source_rows(
                    artifact,
                    tool_input,
                    default_limit=query_default_limit,
                    maximum_limit=None,
                    required_columns=["loc_id"],
                )
                if query_result.get("error"):
                    return query_result
                row_count = int(query_result.get("row_count", 0) or 0)
                force_large_display = bool(tool_input.get("_force_large_display"))
                interrupted_payload = interrupt_display_payload_if_needed(
                    row_count,
                    policy=display_warning_policy,
                    force_large_display=force_large_display,
                    artifact_id=artifact.get("artifact_id"),
                )
                if explicit_limit is None and interrupted_payload is not None:
                    return interrupted_payload
                matched_rows = query_result.get("rows") or []
                return _build_research_map_payload(
                    matched_rows,
                    query_result,
                    artifact,
                    tool_input,
                )
            result = _get_cached_result(session_id, artifact.get("request_key"))
            if not result:
                return {"error": "artifact_data_unavailable", "artifact_id": artifact_id}
            if force_large_display:
                tool_input = dict(tool_input or {})
                tool_input["_force_large_display"] = True
            tool_input["_display_warning_policy"] = display_warning_policy
            return _build_display_subset(result, artifact, tool_input)

        return {"error": "unknown_tool", "tool_name": tool_name}
    except Exception as exc:
        logger.exception(
            "Research tool execution failed session=%s tool=%s artifact_id=%s",
            session_id,
            tool_name,
            (tool_input or {}).get("artifact_id") if isinstance(tool_input, dict) else None,
        )
        return {
            "error": "tool_execution_failed",
            "tool_name": tool_name,
            "detail": str(exc),
        }
