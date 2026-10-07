"""Progressive public discovery projections for MCP catalog tools.

The generated catalogs remain the source of truth. Lite views return only the
fields needed to choose a pack and the next tool. Full MCP views add query
metadata; download views hand off the complete raw JSON without embedding it.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from catalog_coverage_shared import (
    normalize_scope,
    normalize_time_range,
    resolve_pack_coverage_match,
)


APP_ORIGIN = "https://app.daedalmap.com"
DATA_CATALOG_DOWNLOAD_URL = f"{APP_ORIGIN}/api/v1/catalog/download"
GEOMETRY_CATALOG_DOWNLOAD_URL = (
    f"{APP_ORIGIN}/api/v1/geometry/catalog/download"
)

CATALOG_DOWNLOADS = {
    "data": {
        "download_url": DATA_CATALOG_DOWNLOAD_URL,
        "summary_endpoint": f"{APP_ORIGIN}/api/v1/historical/catalog",
    },
    "geometry": {
        "download_url": GEOMETRY_CATALOG_DOWNLOAD_URL,
        "summary_endpoint": f"{APP_ORIGIN}/api/v1/geometry/catalog",
    },
}

# One canonical autonomous-agent path shared by instructions and help.
DATA_ACCESS_WORKFLOW = {
    "goal": "Find a published pack, learn its exact contract, then retrieve only the requested rows.",
    "steps": [
        {
            "stage": "discover",
            "tool": "get_catalog",
            "arguments": {"catalog": "data", "detail": "lite"},
            "outcome": "Choose one pack_id from its topic, geography, and time coverage.",
        },
        {
            "stage": "inspect",
            "tool": "get_pack",
            "arguments": {"catalog": "data", "pack_id": "<selected pack_id>", "detail": "lite"},
            "outcome": "Choose exact metrics, dimensions, filters, geography, and time bounds.",
        },
        {
            "stage": "retrieve",
            "tool": "get_data",
            "arguments": {"pack_id": "<selected pack_id>", "metrics": ["<selected metric_id>"], "filters": {}, "limit": 100},
            "outcome": "Return the requested published data rows.",
        },
    ],
    "help": {
        "overview": {"tool": "get_tool_help", "arguments": {"topic": "overview"}},
        "exact_tool": {"tool": "get_tool_help", "arguments": {"tool_name": "<tool name>"}},
    },
}


def data_access_workflow() -> dict[str, Any]:
    """Return an isolated copy so responses cannot mutate shared guidance."""
    return deepcopy(DATA_ACCESS_WORKFLOW)


def _copy_present(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: source[key] for key in keys if source.get(key) is not None}


def _compact_pack_row(pack: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(pack.get("pack_id") or pack.get("id") or "").strip()
    row = _copy_present(
        pack,
        (
            "pack_id",
            "pack_name",
            "title",
            "short_description",
            "category",
            "data_types",
            "scopes",
            "geographic_levels",
            "empty_geographic_levels_meaning",
            "temporal_start",
            "temporal_end",
            "canonical_available_through",
            "live_updates_enabled",
            "processing_state",
            "metric_count",
            "source_count",
            "free_detail",
            "paid_data_calls",
            "preferred_tool",
            "live_fallback_tool",
        ),
    )
    if pack_id:
        row.setdefault("pack_id", pack_id)
        row["next_call"] = {
            "tool": "get_pack",
            "arguments": {"catalog": "data", "pack_id": pack_id, "detail": "lite"},
        }
        row["download_url"] = f"{APP_ORIGIN}/api/v1/packs/{pack_id}/download"
    return row


def compact_catalog_payload(payload: Any) -> Any:
    """Return the small, stable cross-pack discovery view used by get_catalog."""
    if not isinstance(payload, dict):
        return payload
    packs = [
        _compact_pack_row(item)
        for item in payload.get("packs") or []
        if isinstance(item, dict)
    ]
    result = _copy_present(
        payload,
        ("catalog_version", "schema_version", "generated_at", "source_mode"),
    )
    result.update(
        {
            "view": "lite",
            "pack_count": len(packs),
            "packs": packs,
            "usage": {
                "next_step": "Call get_pack for one selected pack before querying it.",
                "full_catalog": "Use the download URL for bulk catalog inspection instead of asking MCP to repeat the complete catalog.",
            },
            "next_step": data_access_workflow()["steps"][1],
            "full_catalog": {
                "download_url": DATA_CATALOG_DOWNLOAD_URL,
                "agent_catalog_url": f"{APP_ORIGIN}/api/v1/agent/catalog",
            },
        }
    )
    uncertain = [
        _compact_pack_row(item)
        for item in payload.get("uncertain_packs") or []
        if isinstance(item, dict)
    ]
    if uncertain or "uncertain_packs" in payload:
        result["uncertain_packs"] = uncertain
        result["uncertain_count"] = len(uncertain)
    result.update(_copy_present(
        payload,
        ("excluded_count", "result_status", "resolved_query"),
    ))
    return result


def filter_data_catalog_payload(
    payload: Any,
    *,
    loc_id: str | None = None,
    time_range: Any = None,
    detail: str | None = None,
) -> Any:
    """Resolve a conservative place/time catalog intersection.

    Confirmed matches stay in ``packs``. Packs whose authored coverage is not
    precise enough to decide are returned separately instead of being silently
    included as matches or discarded as misses.
    """
    if not isinstance(payload, dict):
        return payload
    requested_loc_id = str(loc_id or "").strip().upper() or None
    country = requested_loc_id.split("-", 1)[0] if requested_loc_id else None
    if country and normalize_scope(country) != country:
        raise ValueError("loc_id must begin with an ISO3 country code")
    requested_time = normalize_time_range(time_range)
    if not requested_loc_id and requested_time is None:
        result = dict(payload)
        result["resolved_query"] = {
            "catalog": "data", "loc_id": None, "country_scope": None,
            "time_range": None, "filter_applied": False,
        }
        return result

    matched: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    excluded = 0
    for raw in payload.get("packs") or []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        place_match, time_match = resolve_pack_coverage_match(row, country, requested_time)
        row["catalog_match"] = {
            "place": "match" if place_match is True else "unknown" if place_match is None else "no_match",
            "time": "match" if time_match is True else "unknown" if time_match is None else "no_match",
        }
        if place_match is False or time_match is False:
            excluded += 1
        elif place_match is None or time_match is None:
            uncertain.append(row)
        else:
            matched.append(row)

    result = dict(payload)
    selected_detail = str(detail or payload.get("view") or payload.get("detail") or "lite")
    result.update({
        "packs": matched,
        "pack_count": len(matched),
        "uncertain_packs": uncertain,
        "uncertain_count": len(uncertain),
        "excluded_count": excluded,
        "result_status": "empty" if not matched else "partial" if uncertain else "complete",
        "resolved_query": {
            "catalog": "data",
            "loc_id": requested_loc_id,
            "country_scope": country,
            "time_range": requested_time,
            "filter_applied": True,
            "unknown_coverage_policy": "returned_separately_not_counted_as_match",
            "rerun": {
                "tool": "get_catalog",
                "arguments": {
                    "catalog": "data", "detail": selected_detail,
                    **({"loc_id": requested_loc_id} if requested_loc_id else {}),
                    **({"time_range": requested_time} if requested_time else {}),
                },
            },
        },
    })
    return result


def full_catalog_payload(payload: Any, pack_details: dict[str, Any]) -> Any:
    """Return all pack cards plus their metric ids, without raw policy records."""
    if not isinstance(payload, dict):
        return payload
    def project(items: Any) -> list[dict[str, Any]]:
        projected = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            row = _compact_pack_row(item)
            pack_id = str(row.get("pack_id") or "")
            detail = pack_details.get(pack_id)
            if isinstance(detail, dict):
                metrics = detail.get("metrics")
                if isinstance(metrics, dict):
                    row["metrics"] = list(metrics)
                elif isinstance(metrics, list):
                    row["metrics"] = [
                        value.get("metric_id") or value.get("id") or value
                        if isinstance(value, dict) else value
                        for value in metrics
                    ]
                row.update(_copy_present(detail, ("query_dimensions", "supported_query_shapes")))
            projected.append(row)
        return projected

    packs = project(payload.get("packs"))
    result = _copy_present(payload, ("catalog_version", "schema_version", "generated_at", "source_mode"))
    result.update({
        "catalog": "data",
        "detail": "full",
        "pack_count": len(packs),
        "packs": packs,
        "next_step": data_access_workflow()["steps"][1],
        "download": catalog_download_payload("data"),
    })
    uncertain = project(payload.get("uncertain_packs"))
    if uncertain or "uncertain_packs" in payload:
        result["uncertain_packs"] = uncertain
        result["uncertain_count"] = len(uncertain)
    result.update(_copy_present(
        payload,
        ("excluded_count", "result_status", "resolved_query"),
    ))
    return result


def catalog_download_payload(catalog: str) -> dict[str, Any]:
    """Return a link-only handoff without loading either catalog into memory."""
    selected = str(catalog or "data").strip().lower()
    if selected not in CATALOG_DOWNLOADS:
        raise ValueError("catalog must be 'data' or 'geometry'")
    next_step = (
        {
            "stage": "inspect",
            "tool": "get_pack",
            "arguments": {"catalog": "geometry", "pack_id": "geography", "detail": "lite"},
        }
        if selected == "geometry"
        else data_access_workflow()["steps"][1]
    )
    return {
        "ok": True,
        "catalog": selected,
        "detail": "download",
        **CATALOG_DOWNLOADS[selected],
        "media_type": "application/json",
        "usage": "Download the complete public catalog directly; MCP does not inline the full catalog.",
        "next_step": next_step,
    }


def _data_query_call(payload: dict[str, Any]) -> dict[str, Any]:
    quick_start = payload.get("quick_start") if isinstance(payload.get("quick_start"), dict) else {}
    template = quick_start.get("first_query_template")
    if not isinstance(template, dict):
        template = {"pack_id": str(payload.get("pack_id") or "<selected pack_id>"), "limit": 100}
    if template.get("tool") and isinstance(template.get("arguments"), dict):
        execution_tool = str(template["tool"])
        arguments = deepcopy(template["arguments"])
    else:
        routing = payload.get("routing") if isinstance(payload.get("routing"), dict) else {}
        execution_tool = str(payload.get("preferred_tool") or routing.get("preferred_tool") or "get_data")
        arguments = deepcopy(template)
    legacy_data_tools = {
        "query_dataset",
        "get_earthquake_events",
        "get_volcanic_activity",
        "get_tsunami_events",
        "get_fx_rates",
    }
    if execution_tool in legacy_data_tools:
        execution_tool = "get_data"
    if execution_tool == "get_data":
        arguments.pop("source_id", None)
        arguments.setdefault("pack_id", str(payload.get("pack_id") or "<selected pack_id>"))
        arguments.setdefault("metrics", [])
        arguments.setdefault("filters", {})
    return {"tool": execution_tool, "arguments": arguments}


def _compact_quick_start(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result = _copy_present(
        value,
        (
            "why_it_exists",
            "first_query_template",
            "starter_metrics",
            "starter_sources",
            "starter_tools",
        ),
    )
    start_here = value.get("start_here")
    if isinstance(start_here, list):
        result["start_here"] = start_here[:3]
    important_rules = value.get("important_rules")
    if isinstance(important_rules, list):
        result["important_rules"] = important_rules[:3]
    return result or None


def compact_pack_detail(payload: Any, *, catalog: str = "data") -> Any:
    """Return bounded one-pack routing metadata without source/provenance dumps."""
    if not isinstance(payload, dict):
        return payload
    selected_catalog = str(catalog or "data").strip().lower()
    if selected_catalog not in {"data", "geometry"}:
        raise ValueError("catalog must be 'data' or 'geometry'")
    pack_id = str(payload.get("pack_id") or payload.get("id") or "").strip()
    result = _copy_present(
        payload,
        (
            "pack_id",
            "pack_name",
            "title",
            "description",
            "catalog_short_description",
            "category",
            "data_types",
            "location",
            "topic_tags",
            "temporal_coverage",
            "coverage_description",
            "canonical_available_through",
            "live_updates_enabled",
            "processing_state",
            "source_count",
            "source_ids",
            "metric_count",
            "supported_query_shapes",
            "preferred_tool",
            "live_fallback_tool",
            "live_fallback_when",
            "pricing",
            "routing",
        ),
    )
    quick_start = _compact_quick_start(payload.get("quick_start"))
    if quick_start:
        result["quick_start"] = quick_start
    if selected_catalog == "geometry":
        tools = []
        for item in payload.get("tools") or []:
            if isinstance(item, dict) and item.get("name"):
                tools.append(_copy_present(item, ("name", "summary")))
        result.update({"tool_count": len(tools), "tools": tools})
        if payload.get("display_name") is not None:
            result["display_name"] = payload["display_name"]
    next_step = _data_query_call(payload)
    if quick_start and next_step.get("tool") == "get_data":
        quick_start["first_query_template"] = deepcopy(next_step["arguments"])
    result.update({
        "catalog": selected_catalog,
        "kind": "tool_family" if selected_catalog == "geometry" else "data_pack",
        "detail": "lite",
        "download_url": f"{APP_ORIGIN}/api/v1/packs/{pack_id}/download" if pack_id else None,
        "full_call": {
            "tool": "get_pack",
            "arguments": {
                "catalog": selected_catalog,
                "pack_id": pack_id,
                "detail": "full",
            },
        },
        "download_call": {
            "tool": "get_pack",
            "arguments": {
                "catalog": selected_catalog,
                "pack_id": pack_id,
                "detail": "download",
            },
        },
        "next_step": next_step,
    })
    return result


def annotate_full_pack_detail(payload: Any, *, catalog: str) -> Any:
    """Give full data and geometry records the same small response envelope."""
    if not isinstance(payload, dict):
        return payload
    selected_catalog = str(catalog or "data").strip().lower()
    if selected_catalog not in {"data", "geometry"}:
        raise ValueError("catalog must be 'data' or 'geometry'")
    result = dict(payload)
    pack_id = str(result.get("pack_id") or result.get("id") or "").strip()
    result.update({
        "catalog": selected_catalog,
        "kind": "tool_family" if selected_catalog == "geometry" else "data_pack",
        "detail": "full",
        "download_url": f"{APP_ORIGIN}/api/v1/packs/{pack_id}/download" if pack_id else None,
        "next_step": _data_query_call(payload),
    })
    return result


def mcp_full_pack_detail(payload: Any, *, catalog: str) -> Any:
    """Return detailed query metadata while leaving raw policy evidence to download."""
    if not isinstance(payload, dict):
        return payload
    omitted = {"material_policy", "license_evidence"}
    result = {key: deepcopy(value) for key, value in payload.items() if key not in omitted}
    next_step = _data_query_call(payload)
    quick_start = result.get("quick_start") if isinstance(result.get("quick_start"), dict) else None
    if quick_start is not None and next_step.get("tool") == "get_data":
        quick_start["first_query_template"] = deepcopy(next_step["arguments"])
    if str(result.get("preferred_tool") or "") in {
        "query_dataset", "get_earthquake_events", "get_volcanic_activity", "get_tsunami_events", "get_fx_rates",
    }:
        result["preferred_tool"] = "get_data"
    return annotate_full_pack_detail(result, catalog=catalog)


def pack_download_payload(pack_id: str, *, catalog: str, payload: Any) -> dict[str, Any]:
    """Return a link-only raw-metadata handoff and the executable next call."""
    selected_catalog = str(catalog or "data").strip().lower()
    if selected_catalog not in {"data", "geometry"}:
        raise ValueError("catalog must be 'data' or 'geometry'")
    normalized = str(pack_id or "").strip()
    return {
        "ok": True,
        "catalog": selected_catalog,
        "kind": "tool_family" if selected_catalog == "geometry" else "data_pack",
        "pack_id": normalized,
        "detail": "download",
        "download_url": f"{APP_ORIGIN}/api/v1/packs/{normalized}/download",
        "media_type": "application/json",
        "next_step": _data_query_call(payload if isinstance(payload, dict) else {"pack_id": normalized}),
    }
