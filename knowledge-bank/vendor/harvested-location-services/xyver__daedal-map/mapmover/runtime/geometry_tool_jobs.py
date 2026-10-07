"""Shared runtime helpers for public/admin geometry tool jobs.

These helpers keep MCP, HTTP, and future admin surfaces on one contract. They
wrap existing geometry-spine seams for scope listing, availability checks, and
reference exchange; durable queues/artifacts can replace the in-memory registry
without changing public tool shapes.
"""

from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import io
import json
import math
import time
import uuid
import zipfile
from copy import deepcopy
from typing import Any

from tool_access_shared import resize_charge_quote, tool_charge_quote, tool_charge_units

from ..geometry_handlers import GEOMETRY_INDEX_COLUMNS, get_geometry_index, load_country_parquet
from .admin_hierarchy import infer_admin_level_from_loc_id
from .admin_spine_query import query_descendant_scope
from .country_geography import get_country_supported_deep_admin_levels
from .geography_reference import translate_geometry_id_to_local_id
from .reference_exchange import (
    convert_reference,
    convert_references_batch,
    get_geometry_availability,
    get_geometry_references,
    resolve_loc_id_input,
    resolve_reference,
    resolve_references_batch,
)
from .reference_identification import normalize_identifier_system


_JOB_REGISTRY: dict[str, dict[str, Any]] = {}
_JOB_IDEMPOTENCY: dict[tuple[str, str], tuple[str, str]] = {}

_CONVERSION_TOP_LEVEL_FIELDS = {
    "request_id", "quote_id", "from_system", "geography_binding", "to_system",
    "items", "row_count", "target_admin_level", "iso3", "relationship_vintage",
    "min_share", "limit", "output_format", "output_name",
}
_CONVERSION_ITEM_FIELDS = {
    "value", "row_index", "id", "from_system", "to_system", "iso3",
    "target_admin_level", "relationship_vintage", "min_share", "limit", "data",
}

GEOMETRY_EXPORT_FORMATS = {"geojson", "geojson_gzip", "zip"}
CONVERSION_EXPORT_FORMATS = {"json_rows", "csv", "jsonl", "parquet"}
_RESERVED_OUTPUT_PREFIX = "daedalmap_"
# Default synchronous safety boundaries. They are sized to keep ordinary warm
# runtime calls inside the product's 10-20 second response-time budget and may
# be tuned by the route's authored/env operational limit.
GEOMETRY_EXPORT_INLINE_LIMIT = 250
CONVERSION_INLINE_LIMIT = 7_500
CONVERSION_ESTIMATE_SAMPLE_LIMIT = 32


def _clean_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if hasattr(value, "item"):
        try:
            return _clean_json(value.item())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_json(item) for item in value]
    return str(value)


def _conversion_contract_error(payload: dict[str, Any], *, allow_row_count: bool) -> dict[str, Any] | None:
    allowed_top = set(_CONVERSION_TOP_LEVEL_FIELDS)
    if not allow_row_count:
        allowed_top.discard("row_count")
    unknown_top = sorted(set(payload) - allowed_top)
    item_errors = []
    for index, item in enumerate(payload.get("items") or []):
        if not isinstance(item, dict):
            continue
        unknown = sorted(set(item) - _CONVERSION_ITEM_FIELDS)
        if unknown:
            item_errors.append({"row_index": index, "unknown_arguments": unknown})
        if "value" in item and not isinstance(item.get("value"), str):
            item_errors.append({"row_index": index, "code": "identifier_strings_required", "field": "value"})
        data = item.get("data")
        if data is not None:
            if not isinstance(data, dict):
                item_errors.append({"row_index": index, "code": "row_data_object_required", "field": "data"})
            else:
                if len(data) > 200:
                    item_errors.append({"row_index": index, "code": "too_many_row_fields", "field": "data", "maximum": 200})
                reserved = sorted(str(key) for key in data if str(key).lower().startswith(_RESERVED_OUTPUT_PREFIX))
                if reserved:
                    item_errors.append({"row_index": index, "code": "reserved_output_fields", "fields": reserved})
                non_scalar = sorted(
                    str(key) for key, value in data.items()
                    if value is not None and not isinstance(value, (str, bool, int, float))
                )
                if non_scalar:
                    item_errors.append({"row_index": index, "code": "spreadsheet_scalar_required", "fields": non_scalar})
    output_format = str(payload.get("output_format") or "json_rows").strip().lower()
    if output_format not in CONVERSION_EXPORT_FORMATS:
        item_errors.append({
            "code": "unsupported_output_format",
            "field": "output_format",
            "supported": sorted(CONVERSION_EXPORT_FORMATS),
        })
    if not unknown_top and not item_errors:
        return None
    return {
        "ok": False,
        "error": {
            "code": "invalid_conversion_contract",
            "message": "Conversion calls use a closed JSON contract; remove unknown fields and keep identifier values as strings.",
            "unknown_arguments": unknown_top,
            "item_errors": item_errors,
            "accepted_arguments": sorted(allowed_top),
            "accepted_item_arguments": sorted(_CONVERSION_ITEM_FIELDS),
        },
        "guidance": {
            "action": "translate_then_retry",
            "message": "Do not pass the user's prose question or original columns directly on the item. Map the identifier to items[].value, put spreadsheet columns in items[].data, and retain a caller key in row_index or id.",
            "help_tool": "get_tool_help",
        },
        "clarification": {"required": False, "reason": "client_call_correction", "questions": []},
    }


def _admin_level_value(value: Any) -> int | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    aliases = {"country": 0, "state": 1, "province": 1, "county": 2}
    if raw in aliases:
        return aliases[raw]
    if raw.startswith("admin_"):
        raw = raw.split("_", 1)[1]
    try:
        return max(0, int(raw))
    except ValueError:
        return None


def _bbox_value(value: Any) -> tuple[float, float, float, float] | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        return None
    if len(parts) != 4:
        return None
    try:
        return tuple(float(part) for part in parts)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _country_code_from_loc_id(loc_id: str) -> str:
    return str(loc_id or "").strip().split("-", 1)[0].upper()


def _base_admin_scope_rows(parent_loc_id: str, admin_level: int, bbox: tuple[float, float, float, float] | None) -> list[dict[str, Any]]:
    parent_level = infer_admin_level_from_loc_id(parent_loc_id)
    if parent_level is None or admin_level > 2:
        return []
    iso3 = _country_code_from_loc_id(parent_loc_id)
    df = load_country_parquet(iso3, admin_level=admin_level, columns=GEOMETRY_INDEX_COLUMNS)
    if df is None or df.empty:
        return []
    if parent_level > 0 and "parent_id" in df.columns:
        parent_ids = {parent_loc_id, translate_geometry_id_to_local_id(parent_loc_id)}
        df = df[df["parent_id"].map(lambda value: translate_geometry_id_to_local_id(str(value or "").strip()) in parent_ids)]
    if bbox is not None and not df.empty:
        min_lon, min_lat, max_lon, max_lat = bbox
        if all(col in df.columns for col in ("bbox_min_lon", "bbox_max_lon", "bbox_min_lat", "bbox_max_lat")):
            df = df[
                (df["bbox_max_lon"] >= min_lon)
                & (df["bbox_min_lon"] <= max_lon)
                & (df["bbox_max_lat"] >= min_lat)
                & (df["bbox_min_lat"] <= max_lat)
            ]
    return [row for row in df.to_dict("records") if isinstance(row, dict)]


def _unsupported_deep_scope_error(parent_loc_id: str, admin_level: int, bbox: tuple[float, float, float, float] | None) -> dict[str, Any] | None:
    if admin_level <= 3:
        return None
    iso3 = _country_code_from_loc_id(parent_loc_id)
    supported_levels = get_country_supported_deep_admin_levels(iso3)
    if admin_level not in supported_levels:
        return {
            "ok": False,
            "parent_loc_id": parent_loc_id,
            "admin_level": admin_level,
            "error": {
                "code": "unsupported_admin_level",
                "message": f"{iso3} does not publish admin_{admin_level} geometry through this scope tool",
            },
            "supported_deep_admin_levels": [f"admin_{level}" for level in supported_levels],
        }
    parent_level = infer_admin_level_from_loc_id(parent_loc_id)
    if parent_level is None:
        return {
            "ok": False,
            "parent_loc_id": parent_loc_id,
            "admin_level": admin_level,
            "error": {"code": "invalid_scope", "message": "parent_loc_id is not a recognized admin loc_id shape"},
            "supported_deep_admin_levels": [f"admin_{level}" for level in supported_levels],
        }
    if parent_level < 1:
        return {
            "ok": False,
            "parent_loc_id": parent_loc_id,
            "admin_level": admin_level,
            "error": {
                "code": "scope_too_broad",
                "message": "Country-wide deep scope spans multiple Admin1 banks; choose an admin_1 parent so the query can stay on one Parquet file.",
            },
            "supported_deep_admin_levels": [f"admin_{level}" for level in supported_levels],
        }
    return None


def _conversion_binding_error(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Validate binding metadata without re-identifying any dataset values."""
    binding = payload.get("geography_binding")
    if not isinstance(binding, dict):
        return None
    system = normalize_identifier_system(binding.get("system"))
    if not system:
        return {"ok": False, "error": {"code": "invalid_geography_binding", "message": "geography_binding.system is required"}}
    if system == "us_census_geoid":
        country = str(binding.get("country_scope") or "USA").strip().upper()
        vintage = str(binding.get("vintage") or "2020").strip().lower()
        if country != "USA" or vintage not in {"2020", "census_2020"}:
            return {
                "ok": False,
                "error": {
                    "code": "unsupported_geography_binding",
                    "message": "US Census GEOID conversion supports the USA 2020 identifier binding",
                },
            }
    return None


def _row_summary(row: dict[str, Any]) -> dict[str, Any]:
    raw_loc_id = str(row.get("loc_id") or "").strip()
    loc_id = translate_geometry_id_to_local_id(raw_loc_id) if raw_loc_id else None
    raw_parent_id = str(row.get("parent_id") or "").strip()
    parent_id = translate_geometry_id_to_local_id(raw_parent_id) if raw_parent_id else None
    bbox = None
    if all(key in row for key in ("bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat")):
        bbox = [row.get("bbox_min_lon"), row.get("bbox_min_lat"), row.get("bbox_max_lon"), row.get("bbox_max_lat")]
    centroid = None
    if row.get("centroid_lon") is not None and row.get("centroid_lat") is not None:
        centroid = {"lon": row.get("centroid_lon"), "lat": row.get("centroid_lat")}
    return _clean_json(
        {
            "loc_id": loc_id or row.get("loc_id"),
            "name": row.get("name"),
            "parent_id": parent_id or row.get("parent_id"),
            "admin_level": row.get("admin_level"),
            "code": row.get("code"),
            "bbox": bbox,
            "centroid": centroid,
        }
    )


def _scope_rows(parent_loc_id: str, admin_level: int, bbox: tuple[float, float, float, float] | None) -> list[dict[str, Any]]:
    """Compatibility scope reader for holdings without an Admin Spine layout.

    This intentionally performs at most one index query and one legacy base
    query. The former parent-by-parent frontier expansion multiplied Parquet
    opens at every level and is not a safe runtime fallback.
    """
    index = get_geometry_index(parent_loc_id=parent_loc_id, admin_level=admin_level, bbox=bbox)
    rows = [row for row in (index.get("rows") or []) if isinstance(row, dict)]
    if rows:
        return rows

    return _base_admin_scope_rows(parent_loc_id, admin_level, bbox) or rows


def resolve_loc_id_scope(payload: dict[str, Any], *, default_limit: int | None = 100) -> dict[str, Any]:
    scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else payload
    parent_loc_id = str(scope.get("parent_loc_id") or payload.get("parent_loc_id") or "").strip()
    admin_level = _admin_level_value(scope.get("admin_level") if isinstance(scope, dict) else payload.get("admin_level"))
    if not parent_loc_id:
        return {"ok": False, "error": {"code": "invalid_scope", "message": "parent_loc_id is required"}}
    parent_resolution = resolve_loc_id_input(parent_loc_id)
    if not parent_resolution.get("ok"):
        return _clean_json({
            "ok": False,
            "parent_loc_id": parent_loc_id,
            "error": parent_resolution.get("error"),
            "candidate_loc_ids": parent_resolution.get("candidate_loc_ids"),
        })
    requested_parent_loc_id = parent_loc_id
    parent_loc_id = str(parent_resolution.get("loc_id") or parent_loc_id)
    if admin_level is None:
        return {"ok": False, "error": {"code": "invalid_scope", "message": "admin_level is required"}}
    bbox = _bbox_value(scope.get("bbox") if isinstance(scope, dict) else payload.get("bbox"))
    requested_limit = payload.get("limit")
    limit = max(0, int(requested_limit)) if requested_limit is not None else (
        max(0, int(default_limit)) if default_limit is not None else None
    )
    offset = max(0, int(payload.get("offset") or 0))
    count_only = bool(payload.get("count_only"))
    unsupported = _unsupported_deep_scope_error(parent_loc_id, admin_level, bbox)
    if unsupported:
        return _clean_json(unsupported)
    direct = query_descendant_scope(
        _country_code_from_loc_id(parent_loc_id),
        parent_loc_id,
        admin_level,
        bbox=bbox,
        limit=limit,
        offset=offset,
        count_only=count_only,
    )
    if direct is not None:
        total = int(direct.get("total_count") or 0)
        page = [_row_summary(row) for row in direct.get("rows") or []]
    else:
        rows = [_row_summary(row) for row in _scope_rows(parent_loc_id, admin_level, bbox)]
        total = len(rows)
        page = [] if count_only else (rows[offset:] if limit is None else rows[offset : offset + limit])
    result = {
            "ok": True,
            "parent_loc_id": parent_loc_id,
            "admin_level": admin_level,
            "bbox": list(bbox) if bbox else None,
            "total_count": total,
            "returned_count": len(page),
            "limit": limit,
            "offset": offset,
            "truncated": (offset + len(page)) < total,
            "loc_ids": [row.get("loc_id") for row in page if row.get("loc_id")],
            "rows": page,
        }
    if parent_resolution.get("resolved_from_public_alias"):
        result.update({
            "requested_parent_loc_id": requested_parent_loc_id,
            "resolved_from_public_alias": True,
            "public_alias_reference_system": parent_resolution.get("reference_system"),
        })
    return _clean_json(result)


def resolve_geometry_selection(
    payload: dict[str, Any], *, scope_limit: int | None = 10000,
) -> tuple[list[str], dict[str, Any] | None]:
    """Resolve one exact or administrative-scope geometry selection.

    Explicit IDs retain caller order while duplicates are collapsed before any
    Parquet work. Administrative scopes use the query-layout router, which
    keeps Admin 0-3 reads on the national bank and deep reads on one Admin 1
    partition. Independent geometry families are deliberately not inferred
    from administrative ancestry.
    """
    if isinstance(payload.get("loc_ids"), list):
        return list(dict.fromkeys(
            str(item).strip() for item in payload.get("loc_ids") or [] if str(item).strip()
        )), None
    loc_id = str(payload.get("loc_id") or "").strip()
    if loc_id:
        return [loc_id], None
    if isinstance(payload.get("scope"), dict) or payload.get("parent_loc_id"):
        scope_payload = {**payload}
        if scope_limit is not None:
            scope_payload["limit"] = scope_limit
        scope_result = resolve_loc_id_scope(scope_payload, default_limit=scope_limit)
        if not scope_result.get("ok"):
            return [], scope_result
        return [str(item) for item in scope_result.get("loc_ids") or [] if str(item).strip()], scope_result
    return [], {"ok": False, "error": {"code": "invalid_request", "message": "loc_ids or scope is required"}}


def _estimate_geometry_bytes(available_count: int, *, include_polygon: bool, output_format: str) -> tuple[int, int]:
    metadata_bytes = available_count * 700
    polygon_bytes = available_count * 45000 if include_polygon else 0
    uncompressed = metadata_bytes + polygon_bytes
    compressed_ratio = 0.18 if output_format in {"geojson_gzip", "zip"} else 1.0
    return uncompressed, max(0, int(uncompressed * compressed_ratio))


def _format_error(output_format: str, supported: set[str]) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "unsupported_output_format",
            "message": f"Output format '{output_format}' is not implemented by this runtime.",
            "supported_formats": sorted(supported),
        },
        "guidance": {
            "action": "choose_supported_format",
            "message": "Choose one of the advertised formats; format names are never silently ignored.",
        },
        "clarification": {"required": False, "reason": "client_call_correction", "questions": []},
    }


def _bounded_inline_error(*, request_kind: str, requested: int, limit: int) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "limit_exceeded",
        "error": {
            "code": "bounded_inline_limit_exceeded",
            "message": f"{request_kind} v0 executes at most {limit} items in one call; {requested} were requested.",
        },
        "requested_count": requested,
        "inline_limit": limit,
        "guidance": {
            "action": "use_download_or_custom_builder",
            "message": "Split a small interactive request, use a downloadable official pack for bulk local work, or wait for the Custom Data Builder durable artifact lane.",
        },
        "clarification": {"required": False, "reason": "published_v0_execution_boundary", "questions": []},
    }


def _safe_output_name(value: Any, default: str) -> str:
    raw = str(value or default).strip()
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in raw).strip("-")
    return safe[:80] or default


def _inline_artifact(*, output_format: str, filename: str, media_type: str, content: bytes, text: bool) -> dict[str, Any]:
    artifact = {
        "inline": True,
        "format": output_format,
        "filename": filename,
        "media_type": media_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    if text:
        artifact.update({"encoding": "utf-8", "content": content.decode("utf-8")})
    else:
        artifact.update({"encoding": "base64", "content_base64": base64.b64encode(content).decode("ascii")})
    return artifact


def _geometry_export_artifact(result: dict[str, Any], *, output_format: str, output_name: str = "geometry-export") -> dict[str, Any]:
    features = []
    for item in result.get("results") or []:
        if not isinstance(item, dict):
            continue
        properties = {key: value for key, value in item.items() if key not in {"geometry", "info"}}
        if item.get("info") is not None:
            properties["info"] = item.get("info")
        features.append({"type": "Feature", "geometry": item.get("geometry"), "properties": properties})
    payload = json.dumps(
        {"type": "FeatureCollection", "features": features},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    name = _safe_output_name(output_name, "geometry-export")
    if output_format == "geojson":
        return _inline_artifact(output_format=output_format, filename=f"{name}.geojson", media_type="application/geo+json", content=payload, text=True)
    if output_format == "geojson_gzip":
        return _inline_artifact(output_format=output_format, filename=f"{name}.geojson.gz", media_type="application/gzip", content=gzip.compress(payload), text=False)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{name}.geojson", payload)
    return _inline_artifact(output_format=output_format, filename=f"{name}.zip", media_type="application/zip", content=buffer.getvalue(), text=False)


def estimate_geometry_package(
    payload: dict[str, Any],
    *,
    scope_limit: int = 10000,
    execution_limit: int | None = GEOMETRY_EXPORT_INLINE_LIMIT,
) -> dict[str, Any]:
    output_format = str(payload.get("format") or "geojson_gzip").strip().lower()
    if output_format not in GEOMETRY_EXPORT_FORMATS:
        return _format_error(output_format, GEOMETRY_EXPORT_FORMATS)
    include_polygon = bool(payload.get("include_polygon", True))
    loc_ids, scope_result = resolve_geometry_selection(payload, scope_limit=scope_limit)
    if not loc_ids:
        return scope_result or {"ok": False, "error": {"code": "empty_request", "message": "No loc_ids found"}}
    availability = get_geometry_availability(loc_ids)
    available_count = int(availability.get("available") or 0)
    missing_count = int(availability.get("missing") or max(0, len(loc_ids) - available_count))
    uncompressed, transfer = _estimate_geometry_bytes(available_count, include_polygon=include_polygon, output_format=output_format)
    execution_limit = max(1, int(execution_limit)) if execution_limit is not None else None
    within_limit = execution_limit is None or len(loc_ids) <= execution_limit
    delivery_mode = "inline" if within_limit else "not_available_in_v0"
    charge_units = _geometry_charge_units(available_count if include_polygon else len(loc_ids), include_polygon=include_polygon, minimum=True)
    quote = tool_charge_quote("create_geometry_export", charge_units)
    create_arguments = {
        "loc_ids": loc_ids,
        "format": output_format,
        "output_name": payload.get("output_name") or "geometry-export",
        "include_polygon": include_polygon,
    }
    quote_id = _quote_id("geoquote", create_arguments, quote)
    return _clean_json(
        {
            "ok": True,
            "quote_id": quote_id,
            "request_kind": "geometry_package",
            "loc_id_count": len(loc_ids),
            "available_shape_count": available_count,
            "missing_shape_count": missing_count,
            "estimated_uncompressed_bytes": uncompressed,
            "estimated_transfer_bytes": transfer,
            "format": output_format,
            "include_polygon": include_polygon,
            "recommended_delivery_mode": delivery_mode,
            "within_execution_limit": within_limit,
            "execution_limit": execution_limit,
            "license_citation_required": True,
            "execution_limits": {"geometry_export_loc_ids": execution_limit, "unrestricted_local_runtime": execution_limit is None},
            "charge_units": charge_units,
            "pricing_version": quote["pricing_version"],
            "quote": {"quote_id": quote_id, **quote},
            "scope": scope_result,
            "create_call": {
                "tool": "create_geometry_export",
                "arguments": {"quote_id": quote_id, **create_arguments},
            } if within_limit else None,
            "guidance": None if within_limit else _bounded_inline_error(
                request_kind="geometry export",
                requested=len(loc_ids),
                limit=execution_limit,
            )["guidance"],
        }
    )


def _geometry_charge_units(item_count: int, *, include_polygon: bool, minimum: bool = False) -> int:
    field = "polygon_items_per_charge_unit" if include_polygon else "metadata_items_per_charge_unit"
    return tool_charge_units("create_geometry_export", item_count, divisor_field=field, minimum=minimum)


def _conversion_charge_units(item_count: int, *, minimum: bool = False) -> int:
    return tool_charge_units("create_conversion_job", item_count, minimum=minimum)


def _quote_id(prefix: str, payload: dict[str, Any], quote: dict[str, Any]) -> str:
    bound_payload = {
        key: value for key, value in payload.items()
        if key not in {"quote_id", "request_id"}
    }
    basis = json.dumps(
        {"arguments": bound_payload, "pricing": quote},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"{prefix}_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]



def _new_job(
    kind: str,
    request_payload: dict[str, Any],
    *,
    status: str = "completed",
    result: dict[str, Any] | None = None,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_id = str(request_payload.get("request_id") or "").strip()
    fingerprint = hashlib.sha256(
        json.dumps(request_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    idempotency_key = (kind, request_id)
    if request_id and idempotency_key in _JOB_IDEMPOTENCY:
        prior_fingerprint, prior_job_id = _JOB_IDEMPOTENCY[idempotency_key]
        if prior_fingerprint != fingerprint:
            return {
                "ok": False,
                "error": {
                    "code": "idempotency_conflict",
                    "message": "request_id was already used with a different job payload",
                },
            }
        return _clean_json(_JOB_REGISTRY[prior_job_id])

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    job_id = f"{kind}_{uuid.uuid4().hex[:16]}"
    job = {
        "ok": True,
        "job_id": job_id,
        "kind": kind,
        "status": status,
        "progress": 1.0 if status == "completed" else 0.0,
        "created_at": now,
        "updated_at": now,
        "result": result,
        "artifact": artifact,
        "callback_state": "not_configured",
        "next_call": {
            "tool": "get_job_status",
            "arguments": {"job_id": job_id},
        },
    }
    _JOB_REGISTRY[job_id] = job
    if request_id:
        _JOB_IDEMPOTENCY[idempotency_key] = (fingerprint, job_id)
    return _clean_json(job)


def create_geometry_export(
    payload: dict[str, Any],
    *,
    inline_limit: int | None = GEOMETRY_EXPORT_INLINE_LIMIT,
    pricing_quote: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inline_limit = max(1, int(inline_limit)) if inline_limit is not None else None
    output_format = str(payload.get("format") or "geojson_gzip").strip().lower()
    if output_format not in GEOMETRY_EXPORT_FORMATS:
        return _format_error(output_format, GEOMETRY_EXPORT_FORMATS)
    include_polygon = bool(payload.get("include_polygon", True))
    loc_ids, scope_result = resolve_geometry_selection(
        payload, scope_limit=None if inline_limit is None else 10000,
    )
    if not loc_ids:
        return scope_result or {"ok": False, "error": {"code": "empty_request", "message": "No loc_ids found"}}
    if inline_limit is not None and len(loc_ids) > inline_limit:
        return _bounded_inline_error(request_kind="geometry export", requested=len(loc_ids), limit=inline_limit)
    result = get_geometry_references(loc_ids, include_polygon=include_polygon, include_info=True)
    artifact = _geometry_export_artifact(
        result,
        output_format=output_format,
        output_name=payload.get("output_name") or "geometry-export",
    )
    successful_items = int(result.get("available") or 0)
    charge_units = _geometry_charge_units(successful_items, include_polygon=include_polygon)
    meter_receipt = {
        "tool_name": "create_geometry_export",
        "requested_items": len(loc_ids),
        "successful_items": successful_items,
        "unresolved_items": max(0, len(loc_ids) - successful_items),
        "charge_units": charge_units,
        "quote": (
            resize_charge_quote(pricing_quote, charge_units)
            if pricing_quote
            else tool_charge_quote("create_geometry_export", charge_units)
        ),
    }
    return _new_job(
        "geometry_export",
        payload,
        status="completed",
        artifact=artifact,
        result={
            "delivery_mode": "inline",
            "format": output_format,
            "requested": result.get("requested", len(loc_ids)),
            "available": result.get("available"),
            "missing": result.get("missing"),
            "meter_receipt": meter_receipt,
        },
    )


def _conversion_row(payload: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Apply a verified geography binding as defaults without overriding row values."""
    row = {**payload, **item}
    binding = payload.get("geography_binding") if isinstance(payload.get("geography_binding"), dict) else {}
    if binding:
        row.setdefault("from_system", binding.get("system"))
        row.setdefault("target_admin_level", binding.get("geo_level"))
        row.setdefault("relationship_vintage", binding.get("vintage"))
        row.setdefault("iso3", binding.get("country_scope"))
    return row


def _conversion_cache_key(row: dict[str, Any]) -> str:
    fields = (
        "from_system", "value", "to_system", "iso3", "target_admin_level",
        "relationship_vintage", "min_share", "limit",
    )
    return json.dumps({field: row.get(field) for field in fields}, sort_keys=True, default=str)


def _run_conversion_row(row: dict[str, Any], *, default_limit: int) -> dict[str, Any]:
    country_scope = str(row.get("iso3") or "").strip().upper() or None
    if row.get("to_system"):
        return convert_reference(
            from_system=str(row.get("from_system") or ""),
            value=str(row.get("value") or ""),
            to_system=str(row.get("to_system") or ""),
            iso3=country_scope,
            target_admin_level=row.get("target_admin_level") or "admin_2",
            relationship_vintage=row.get("relationship_vintage"),
            min_share=row.get("min_share"),
            limit=int(row.get("limit") or default_limit),
        )
    return resolve_reference(
        from_system=str(row.get("from_system") or ""),
        value=str(row.get("value") or ""),
        iso3=country_scope,
        target_admin_level=row.get("target_admin_level") or "admin_2",
        relationship_vintage=row.get("relationship_vintage"),
        min_share=row.get("min_share"),
        limit=int(row.get("limit") or default_limit),
    )


def _conversion_reference_request(row: dict[str, Any], *, default_limit: int) -> dict[str, Any]:
    request = {
        "from_system": str(row.get("from_system") or ""),
        "value": str(row.get("value") or ""),
        "iso3": str(row.get("iso3") or "").strip().upper() or None,
        "target_admin_level": row.get("target_admin_level") or "admin_2",
        "relationship_vintage": row.get("relationship_vintage"),
        "min_share": row.get("min_share"),
        "limit": int(row.get("limit") or default_limit),
    }
    if row.get("to_system"):
        request["to_system"] = str(row.get("to_system"))
    return request


def _resolve_conversion_items(
    payload: dict[str, Any],
    items: list[Any],
    *,
    default_limit: int = 10,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Resolve conversion rows in one deduplicated batch for estimates and jobs."""
    resolution_cache: dict[str, dict[str, Any]] = {}
    unique_rows: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        row = _conversion_row(payload, item)
        unique_rows.setdefault(_conversion_cache_key(row), row)
    if unique_rows:
        keys = list(unique_rows)
        requests = [
            _conversion_reference_request(unique_rows[key], default_limit=default_limit)
            for key in keys
        ]
        batch_results: list[dict[str, Any] | None] = [None] * len(requests)
        resolution_indexes = [index for index, request in enumerate(requests) if not request.get("to_system")]
        conversion_indexes = [index for index, request in enumerate(requests) if request.get("to_system")]
        if resolution_indexes:
            resolved = resolve_references_batch([requests[index] for index in resolution_indexes])
            for index, result in zip(resolution_indexes, resolved):
                batch_results[index] = result
        if conversion_indexes:
            converted = convert_references_batch([requests[index] for index in conversion_indexes])
            for index, result in zip(conversion_indexes, converted):
                batch_results[index] = result
        resolution_cache.update(
            (key, result if isinstance(result, dict) else {
                "ok": False,
                "error": {"code": "missing_batch_result", "message": "No conversion result was returned"},
            })
            for key, result in zip(keys, batch_results)
        )

    results: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            results.append({
                "row_index": index,
                "ok": False,
                "error": {"code": "invalid_item", "message": "each item must be an object"},
            })
            continue
        row = _conversion_row(payload, item)
        cache_key = _conversion_cache_key(row)
        if cache_key not in resolution_cache:
            resolution_cache[cache_key] = _run_conversion_row(row, default_limit=default_limit)
        result = deepcopy(resolution_cache[cache_key])
        if item.get("row_index") is not None:
            result["row_index"] = item.get("row_index")
        results.append(result)
    return resolution_cache, results


def _conversion_output_row(item: dict[str, Any], result: dict[str, Any], *, fallback_index: int) -> dict[str, Any]:
    row = dict(item.get("data") or {})
    row["row_index"] = item.get("row_index", fallback_index)
    if item.get("id") is not None:
        row["row_id"] = item.get("id")
    row["loc_id"] = result.get("resolved_loc_id") or result.get("loc_id")
    admin_level = result.get("admin_level") or (result.get("crosswalk") or {}).get("target_admin_level")
    if admin_level:
        row["admin_level"] = admin_level
    error = result.get("error")
    if isinstance(error, dict):
        row["error"] = error.get("message") or error.get("code")
    elif error:
        row["error"] = str(error)
    return _clean_json(row)


def _tabular_artifact(rows: list[dict[str, Any]], *, output_format: str, output_name: str) -> dict[str, Any] | None:
    if output_format == "json_rows":
        return None
    name = _safe_output_name(output_name, "daedalmap-conversion")
    columns = list(dict.fromkeys(key for row in rows for key in row))
    normalized = [{column: row.get(column) for column in columns} for row in rows]
    if output_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(normalized)
        return _inline_artifact(
            output_format=output_format,
            filename=f"{name}.csv",
            media_type="text/csv",
            content=buffer.getvalue().encode("utf-8-sig"),
            text=True,
        )
    if output_format == "jsonl":
        content = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in normalized).encode("utf-8")
        return _inline_artifact(
            output_format=output_format,
            filename=f"{name}.jsonl",
            media_type="application/x-ndjson",
            content=content,
            text=True,
        )
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return {
            "inline": False,
            "format": output_format,
            "error": {"code": "parquet_dependency_unavailable", "message": "The runtime does not have pyarrow installed."},
        }
    sink = pa.BufferOutputStream()
    pq.write_table(pa.Table.from_pylist(normalized), sink, compression="snappy")
    return _inline_artifact(
        output_format=output_format,
        filename=f"{name}.parquet",
        media_type="application/vnd.apache.parquet",
        content=sink.getvalue().to_pybytes(),
        text=False,
    )


def estimate_conversion_job(
    payload: dict[str, Any],
    *,
    sample_limit: int = CONVERSION_ESTIMATE_SAMPLE_LIMIT,
    execution_limit: int | None = CONVERSION_INLINE_LIMIT,
) -> dict[str, Any]:
    contract_error = _conversion_contract_error(payload, allow_row_count=True)
    if contract_error:
        return contract_error
    binding_error = _conversion_binding_error(payload)
    if binding_error:
        return binding_error
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    try:
        declared_row_count = max(0, int(payload.get("row_count") or 0)) if "row_count" in payload else None
    except (TypeError, ValueError):
        return {"ok": False, "error": {"code": "invalid_request", "message": "row_count must be a non-negative integer"}}
    if declared_row_count is not None and declared_row_count < len(items):
        return {
            "ok": False,
            "error": {
                "code": "invalid_request",
                "message": "row_count cannot be smaller than the supplied item sample",
            },
        }
    row_count = declared_row_count if declared_row_count is not None else len(items)
    bounded_sample_limit = min(CONVERSION_ESTIMATE_SAMPLE_LIMIT, max(0, int(sample_limit)))
    sample_items = items[:bounded_sample_limit]
    _sample_cache, sample_results = _resolve_conversion_items(payload, sample_items)
    sampled_rows = len(sample_results)
    resolvable_sample_rows = sum(1 for result in sample_results if result.get("ok"))
    sample_error_rows = max(0, sampled_rows - resolvable_sample_rows)
    if sampled_rows:
        estimated_resolvable_rows = round(row_count * resolvable_sample_rows / sampled_rows)
        estimated_error_rows = max(0, row_count - estimated_resolvable_rows)
        identifier_check = {
            "status": "passed" if sample_error_rows == 0 else ("failed" if resolvable_sample_rows == 0 else "partial"),
            "sampled_rows": sampled_rows,
            "resolvable_rows": resolvable_sample_rows,
            "error_rows": sample_error_rows,
            "resolvable_share": resolvable_sample_rows / sampled_rows,
        }
    else:
        estimated_resolvable_rows = None
        estimated_error_rows = None
        identifier_check = None
    output_format = str(payload.get("output_format") or "json_rows").strip().lower()
    binding = payload.get("geography_binding") if isinstance(payload.get("geography_binding"), dict) else None
    execution_limit = max(1, int(execution_limit)) if execution_limit is not None else None
    within_limit = row_count > 0 and (execution_limit is None or row_count <= execution_limit)
    charge_units = _conversion_charge_units(row_count, minimum=True)
    quote = tool_charge_quote("create_conversion_job", charge_units)
    quote_id = _quote_id("convquote", {
        "geography_binding": binding,
        "from_system": payload.get("from_system"),
        "to_system": payload.get("to_system"),
        "target_admin_level": payload.get("target_admin_level"),
        "iso3": payload.get("iso3"),
        "relationship_vintage": payload.get("relationship_vintage"),
        "row_count": row_count,
        "output_format": output_format,
    }, quote)
    return _clean_json(
        {
            "ok": True,
            "quote_id": quote_id,
            "request_kind": "conversion_job",
            "row_count": row_count,
            "sampled_rows": sampled_rows,
            "estimated_resolvable_rows": estimated_resolvable_rows,
            "estimated_error_rows": estimated_error_rows,
            "estimated_output_bytes": max(1000, row_count * (500 if output_format == "parquet" else 900)),
            "output_format": output_format,
            "preserves_input_columns": True,
            "recommended_delivery_mode": "inline" if within_limit else "not_available_in_v0",
            "within_execution_limit": within_limit,
            "execution_limit": execution_limit,
            "charge_units": charge_units,
            "pricing_version": quote["pricing_version"],
            "quote": {"quote_id": quote_id, **quote},
            "resolution_plan": {
                "mode": "known_identifier_crosswalk" if binding else "declared_reference_resolution",
                "geography_binding": binding,
                "deduplicate_by_identifier": True,
                "spatial_lookup_required": False,
            },
            "identifier_check": identifier_check,
            "create_call": {
                "tool": "create_conversion_job",
                "arguments": {**{key: value for key, value in payload.items() if key != "row_count"}, "quote_id": quote_id},
            } if within_limit and items and row_count == len(items) else None,
            "guidance": (
                None
                if within_limit and items and row_count == len(items)
                else {
                    "action": "submit_complete_dataset",
                    "message": "Pass every dataset row in items to create_conversion_job; it validates each row and returns structured failures for unmatched identifiers.",
                }
                if within_limit
                else _bounded_inline_error(
                    request_kind="conversion",
                    requested=row_count,
                    limit=execution_limit,
                )["guidance"]
            ),
        }
    )


def create_conversion_job(
    payload: dict[str, Any],
    *,
    inline_limit: int | None = CONVERSION_INLINE_LIMIT,
    pricing_quote: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inline_limit = max(1, int(inline_limit)) if inline_limit is not None else None
    contract_error = _conversion_contract_error(payload, allow_row_count=False)
    if contract_error:
        return contract_error
    binding_error = _conversion_binding_error(payload)
    if binding_error:
        return binding_error
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    output_format = str(payload.get("output_format") or "json_rows").strip().lower()
    if not items:
        return {"ok": False, "error": {"code": "invalid_request", "message": "items are required for conversion execution"}}
    if inline_limit is not None and len(items) > inline_limit:
        return _bounded_inline_error(request_kind="conversion", requested=len(items), limit=inline_limit)
    # Identification is a separate MCP step. A confirmed binding is consumed
    # directly here; execution validates individual values while performing the
    # bulk transform/join and never re-runs identification or geometry checks.
    identifier_check = None
    output_rows = []
    resolution_cache, results = _resolve_conversion_items(payload, items)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        result = results[index]
        output_rows.append(_conversion_output_row(item, result, fallback_index=index))
    artifact = _tabular_artifact(
        output_rows,
        output_format=output_format,
        output_name=str(payload.get("output_name") or "daedalmap-conversion"),
    )
    successful_distinct = sum(1 for item in resolution_cache.values() if item.get("ok"))
    successful_rows = sum(1 for item in results if item.get("ok"))
    charge_units = _conversion_charge_units(successful_rows)
    meter_receipt = {
        "tool_name": "create_conversion_job",
        "requested_items": len(items),
        "successful_items": successful_rows,
        "unresolved_items": max(0, len(items) - successful_rows),
        "distinct_items_resolved": len(resolution_cache),
        "successful_distinct_items": successful_distinct,
        "duplicate_items_collapsed": max(0, len(items) - len(resolution_cache)),
        "charge_units": charge_units,
        "quote": (
            resize_charge_quote(pricing_quote, charge_units)
            if pricing_quote
            else tool_charge_quote("create_conversion_job", charge_units)
        ),
    }
    return _new_job(
        "conversion_job",
        payload,
        status="completed",
        artifact=artifact,
        result={
            "delivery_mode": "inline",
            "output_format": output_format,
            "row_count": len(items),
            "distinct_geography_count": len(resolution_cache),
            "converted_count": sum(1 for item in results if item.get("ok")),
            "error_count": sum(1 for item in results if not item.get("ok")),
            "identifier_check": identifier_check,
            "meter_receipt": meter_receipt,
            "resolution_plan": {
                "mode": "known_identifier_crosswalk" if isinstance(payload.get("geography_binding"), dict) else "declared_reference_resolution",
                "geography_binding": payload.get("geography_binding") if isinstance(payload.get("geography_binding"), dict) else None,
                "deduplicate_by_identifier": True,
                "deduplicated_resolution_count": len(resolution_cache),
                "spatial_lookup_required": False,
            },
            # Preserve the rich per-row diagnostic shape for interactive calls,
            # but do not duplicate it beside a large spreadsheet artifact.
            "results": results if len(items) <= 100 else None,
            "detailed_results_included": len(items) <= 100,
            "output_rows": output_rows if output_format == "json_rows" else None,
        },
    )


def get_job_status(job_id: str) -> dict[str, Any]:
    job = _JOB_REGISTRY.get(str(job_id or "").strip())
    if not job:
        return {"ok": False, "job_id": job_id, "status": "not_found", "error": {"code": "job_not_found", "message": "No job found for job_id"}}
    return _clean_json(job)
