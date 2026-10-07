"""Saved-corpus and browser-artifact helpers for Research."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from shapely import wkt as shapely_wkt
from shapely.geometry import mapping as shapely_mapping

from mapmover import logger
from mapmover.api_query_runtime import execute_dataset_query, get_api_source_columns, get_api_source_spec
from mapmover.corpus_registry import corpus_registry
from mapmover.data_loading import get_source_path, load_catalog, load_source_metadata
from mapmover.duckdb_helpers import (
    is_cloud_mode,
    parquet_available,
    parquet_columns,
    path_to_uri,
    quote_ident,
    run_rows,
    select_columns_from_parquet,
)
from mapmover.geometry_handlers import get_selection_geometries
from mapmover.hosted_runtime_account import load_saved_corpus_for_user as _private_load_saved_corpus_for_user
from mapmover.session_cache import session_manager
from mapmover.source_time_contract import build_metric_year_ranges


RESEARCH_LIVE_SOURCE_ROW_THRESHOLD = 250_000
RESEARCH_LIVE_SOURCE_FILE_MB_THRESHOLD = 25.0
PRIVATE_BROWSER_ARTIFACT_OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "county-map-private" / "build" / "browser_artifacts" / "output"


def _infer_loc_id_details(loc_id) -> tuple[int | None, str | None]:
    text = str(loc_id or "").strip()
    if not text:
        return None, None
    segment_count = text.count("-")
    kind_map = {
        0: "country",
        1: "state_or_admin_1",
        2: "county",
        3: "tract",
        4: "blockgroup",
        5: "block",
    }
    return segment_count, kind_map.get(segment_count)


def _build_saved_corpus_summary(corpus_row: dict | None) -> dict | None:
    if not isinstance(corpus_row, dict):
        return None

    items = corpus_row.get("research_corpus_items") or []
    source_ids: list[str] = []
    source_seen = set()
    source_lookup = _catalog_source_lookup()
    resolved_sources = []
    resolved_transfer_bytes_total = 0
    resolved_stored_bytes_total = 0
    resolved_expanded_bytes_total = 0
    estimated_row_count_total = 0
    estimated_file_size_mb_total = 0.0
    derived_pack_ids: list[str] = []
    derived_pack_seen = set()

    for item in items:
        item_id = str(item.get("item_id") or "").strip()
        if not item_id or item_id in source_seen:
            continue
        source_seen.add(item_id)
        source_ids.append(item_id)
        source_meta = source_lookup.get(item_id)
        if isinstance(source_meta, dict):
            resolved_sources.append(deepcopy(source_meta))
            estimated_row_count_total += int(source_meta.get("row_count") or 0)
            estimated_file_size_mb_total += float((source_meta.get("size") or {}).get("transfer_mb") or source_meta.get("file_size_mb") or 0.0)
            pack_id = str(source_meta.get("pack_id") or "").strip()
            if pack_id and pack_id not in derived_pack_seen:
                derived_pack_seen.add(pack_id)
                derived_pack_ids.append(pack_id)
            browser_artifact = _normalize_browser_artifact(source_meta.get("browser_artifact"))
            if browser_artifact:
                resolved_transfer_bytes_total += int(browser_artifact.get("transfer_bytes") or 0)
                resolved_stored_bytes_total += int(browser_artifact.get("stored_bytes") or 0)
                resolved_expanded_bytes_total += int(browser_artifact.get("expanded_bytes") or 0)

    return {
        "id": corpus_row.get("id"),
        "name": corpus_row.get("name") or "Untitled corpus",
        "description": corpus_row.get("description") or "",
        "updated_at": corpus_row.get("updated_at"),
        "source_ids": source_ids,
        "pack_count": len(derived_pack_ids),
        "source_count": len(source_ids),
        "resolved_source_count": len(source_ids),
        "estimated_row_count_total": estimated_row_count_total,
        "estimated_file_size_mb_total": round(estimated_file_size_mb_total, 2),
        "derived_pack_ids": derived_pack_ids,
        "resolved_source_ids": source_ids,
        "sources": resolved_sources,
        "browser_artifact_totals": {
            "transfer_bytes": resolved_transfer_bytes_total,
            "stored_bytes": resolved_stored_bytes_total,
            "expanded_bytes": resolved_expanded_bytes_total,
            "transfer_mb": round(resolved_transfer_bytes_total / (1024 * 1024), 2),
            "stored_mb": round(resolved_stored_bytes_total / (1024 * 1024), 2),
            "expanded_mb": round(resolved_expanded_bytes_total / (1024 * 1024), 2),
        },
    }


def _load_saved_corpus_for_user(user_id: str, corpus_id: str) -> dict | None:
    corpus_row = _private_load_saved_corpus_for_user(user_id, corpus_id)
    return _build_saved_corpus_summary(corpus_row) if corpus_row else None


def _saved_corpus_request_key(corpus_id: str, source_id: str) -> str:
    seed = f"saved-corpus:{corpus_id}:{source_id}"
    return f"saved_{hashlib.md5(seed.encode('utf-8')).hexdigest()[:16]}"


def _expected_saved_corpus_source_ids(saved_corpus: dict | None) -> list[str]:
    if not isinstance(saved_corpus, dict):
        return []
    resolved = []
    seen = set()
    for source_id in saved_corpus.get("source_ids") or []:
        text = str(source_id or "").strip()
        if text and text not in seen:
            seen.add(text)
            resolved.append(text)
    return resolved


def _artifact_source_ids(artifacts: list[dict] | None) -> list[str]:
    resolved = []
    seen = set()
    for artifact in artifacts or []:
        text = str((artifact or {}).get("source_id") or "").strip()
        if text and text not in seen:
            seen.add(text)
            resolved.append(text)
    return resolved


def _artifacts_match_saved_corpus(artifacts: list[dict] | None, saved_corpus: dict | None) -> bool:
    expected = set(_expected_saved_corpus_source_ids(saved_corpus))
    if not expected:
        return True
    actual = set(_artifact_source_ids(artifacts))
    return actual == expected


def _annotate_manifest_saved_corpus_state(manifest: dict) -> dict:
    if not isinstance(manifest, dict):
        return manifest
    saved_corpus = manifest.get("saved_corpus")
    artifacts = manifest.get("artifacts") or []
    expected_source_ids = _expected_saved_corpus_source_ids(saved_corpus)
    if not expected_source_ids:
        manifest["stale_artifacts"] = False
        return manifest
    actual_source_ids = _artifact_source_ids(artifacts)
    manifest["expected_source_ids"] = expected_source_ids
    manifest["actual_source_ids"] = actual_source_ids
    manifest["stale_artifacts"] = set(actual_source_ids) != set(expected_source_ids)
    return manifest


def _source_summary_text(source_id: str, metadata: dict, row_count: int) -> str:
    source_name = str(metadata.get("source_name") or source_id).strip() or source_id
    coverage = str(metadata.get("coverage_description") or "").strip()
    if coverage and coverage.lower() != "unknown coverage":
        return f"{source_name}: {coverage} ({row_count:,} rows loaded for Research)."
    return f"{source_name}: {row_count:,} rows loaded for Research."


def _rows_to_temporal_result(
    rows: list[dict],
    source_id: str,
    metadata: dict,
    spec,
    dimension_columns: list[str] | None = None,
) -> dict:
    features_by_loc: dict[str, dict] = {}
    time_data: dict[str, dict] = {}
    metric_ids = list((metadata.get("metrics") or {}).keys())
    dimension_columns = [str(column).strip() for column in (dimension_columns or []) if str(column).strip()]
    if not metric_ids:
        metric_ids = [metric_id for metric_id in spec.metrics.keys() if metric_id != "event_count"]

    for row in rows:
        loc_id = row.get(spec.location_field)
        if loc_id is None:
            continue
        loc_id = str(loc_id)
        admin_level_num, geography_kind = _infer_loc_id_details(loc_id)
        name = row.get("name") or loc_id
        features_by_loc.setdefault(
            loc_id,
            {
                "type": "Feature",
                "properties": {
                    "loc_id": loc_id,
                    "name": name,
                    "admin_level_num": admin_level_num,
                    "geography_kind": geography_kind,
                },
            },
        )
        feature_props = features_by_loc[loc_id]["properties"]
        for column_name in dimension_columns:
            if column_name in row and column_name not in {spec.location_field, spec.time_field, "name"}:
                feature_props.setdefault(column_name, row.get(column_name))
        time_value = row.get(spec.time_field) if spec.time_field else None
        if time_value is None:
            continue
        time_key = str(time_value)
        metric_values = {
            metric_id: row.get(metric_id)
            for metric_id in metric_ids
            if metric_id in row
        }
        if admin_level_num is not None:
            metric_values["admin_level_num"] = admin_level_num
        if geography_kind:
            metric_values["geography_kind"] = geography_kind
        for column_name in dimension_columns:
            if column_name in row and column_name not in {spec.location_field, spec.time_field, "name"}:
                metric_values[column_name] = row.get(column_name)
        if not metric_values:
            continue
        time_data.setdefault(time_key, {})[loc_id] = metric_values

    sorted_time_keys = sorted(time_data.keys(), key=lambda token: (len(str(token)), str(token)))
    time_range = {
        "min": sorted_time_keys[0] if sorted_time_keys else None,
        "max": sorted_time_keys[-1] if sorted_time_keys else None,
        "available": sorted_time_keys,
        "granularity": "yearly",
        "useTimestamps": False,
    }

    return {
        "type": "data",
        "data_type": "metrics",
        "source_id": source_id,
        "time_field": spec.time_field or "year",
        "temporal_coverage": metadata.get("temporal_coverage") or {},
        "metrics": metadata.get("metrics") if isinstance(metadata.get("metrics"), dict) else {},
        "geojson": {
            "type": "FeatureCollection",
            "features": list(features_by_loc.values()),
        },
        "time_data": time_data,
        "time_range": time_range,
        # TEMPORARY MIRRORS: remove after all consumers switch to canonical time_*.
        "year_data": time_data,
        "multi_year": True,
        "year_range": sorted_time_keys,
        "available_metrics": metric_ids,
        "metric_time_ranges": build_metric_year_ranges(metadata),
        "metric_year_ranges": build_metric_year_ranges(metadata),
        "summary": _source_summary_text(source_id, metadata, len(rows)),
        "count": len(rows),
        "sources": [{"id": source_id, "name": str(metadata.get("source_name") or source_id)}],
    }


def _rows_to_static_result(rows: list[dict], source_id: str, metadata: dict, spec) -> dict:
    features = []
    metric_ids = list((metadata.get("metrics") or {}).keys())
    if not metric_ids:
        metric_ids = [metric_id for metric_id in spec.metrics.keys() if metric_id != "event_count"]
    for row in rows:
        props = dict(row)
        loc_id = props.get(spec.location_field)
        if loc_id is not None:
            props["loc_id"] = str(loc_id)
            admin_level_num, geography_kind = _infer_loc_id_details(loc_id)
            props.setdefault("admin_level_num", admin_level_num)
            props.setdefault("geography_kind", geography_kind)
        if "name" not in props and props.get("loc_id"):
            props["name"] = props["loc_id"]
        features.append({"type": "Feature", "properties": props})

    return {
        "type": "data",
        "data_type": "metrics",
        "source_id": source_id,
        "temporal_coverage": metadata.get("temporal_coverage") or {},
        "metrics": metadata.get("metrics") if isinstance(metadata.get("metrics"), dict) else {},
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
        "available_metrics": metric_ids,
        "metric_year_ranges": build_metric_year_ranges(metadata),
        "summary": _source_summary_text(source_id, metadata, len(rows)),
        "count": len(rows),
        "sources": [{"id": source_id, "name": str(metadata.get("source_name") or source_id)}],
    }


def _is_runtime_research_source(metadata: dict) -> bool:
    if not isinstance(metadata, dict):
        return False
    release_state = str(metadata.get("release_state") or "").strip().lower()
    return release_state == "published" or bool(metadata.get("pack_id"))


def _should_register_live_source_artifact(metadata: dict) -> bool:
    if not isinstance(metadata, dict):
        return False
    data_type = metadata.get("data_type")
    normalized_types = data_type if isinstance(data_type, list) else [data_type]
    normalized = {str(value or "").strip().lower() for value in normalized_types if value}
    if "geometry" in normalized:
        return False
    row_count = int(metadata.get("row_count") or 0)
    file_size_mb = float(metadata.get("file_size_mb") or 0.0)
    return row_count >= RESEARCH_LIVE_SOURCE_ROW_THRESHOLD or file_size_mb >= RESEARCH_LIVE_SOURCE_FILE_MB_THRESHOLD


def _find_primary_parquet(source_id: str, metadata: dict):
    source_dir = get_source_path(source_id)
    if source_dir is None:
        return None

    def candidate_accessible(candidate_path) -> bool:
        if not is_cloud_mode():
            return parquet_available(candidate_path)
        try:
            parquet_columns(candidate_path)
            return True
        except Exception:
            return False

    candidate_names: list[str] = []
    for rel_path in metadata.get("primary_files") or []:
        candidate = source_dir / str(rel_path)
        if candidate.suffix.lower() == ".parquet" and candidate_accessible(candidate):
            return candidate
        if candidate.suffix.lower() == ".parquet":
            candidate_names.append(str(rel_path))

    files_section = metadata.get("files") if isinstance(metadata.get("files"), dict) else {}
    for file_info in files_section.values():
        if not isinstance(file_info, dict):
            continue
        file_name = str(file_info.get("name") or file_info.get("filename") or "").strip()
        if file_name.lower().endswith(".parquet"):
            candidate_names.append(file_name)

    seen_candidates = set()
    for candidate_name in candidate_names:
        normalized_name = str(candidate_name or "").strip()
        if not normalized_name or normalized_name in seen_candidates:
            continue
        seen_candidates.add(normalized_name)
        candidate = source_dir / normalized_name
        if candidate_accessible(candidate):
            return candidate

    fallback_names: list[str] = []
    spec = get_api_source_spec(source_id)
    if spec and str(spec.parquet_name or "").strip():
        fallback_names.append(str(spec.parquet_name).strip())

    normalized_kind = str(metadata.get("data_type") or "").strip().lower()
    if normalized_kind == "events" or metadata.get("event_type"):
        fallback_names.extend([
            "events.parquet",
            "storms.parquet",
            "positions.parquet",
            "fires.parquet",
        ])

    fallback_names.extend((
        "all_countries.parquet",
        "all_regions.parquet",
        "data.parquet",
        "events.parquet",
        "full_range.parquet",
        "USA.parquet",
    ))

    seen_fallbacks = set()
    for fallback_name in fallback_names:
        if fallback_name in seen_fallbacks:
            continue
        seen_fallbacks.add(fallback_name)
        if fallback_name in candidate_names:
            continue
        candidate = source_dir / fallback_name
        if candidate_accessible(candidate):
            return candidate
    return None


def _load_runtime_rows(parquet_path, columns: list[str]) -> list[dict]:
    df = select_columns_from_parquet(parquet_path, columns)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def _load_runtime_rows_raw(parquet_path, columns: list[str]) -> list[dict]:
    available_columns = parquet_columns(parquet_path)
    selected = [column for column in columns if column in available_columns]
    if not selected:
        return []
    select_exprs = []
    for column in selected:
        if column == "geometry":
            select_exprs.append(f"CAST({quote_ident(column)} AS VARCHAR) AS {quote_ident(column)}")
        else:
            select_exprs.append(quote_ident(column))
    sql = "SELECT " + ", ".join(select_exprs) + " FROM read_parquet(?)"
    rows = run_rows(sql, [path_to_uri(parquet_path)])
    return [dict(zip(selected, row)) for row in rows]


def _hydrate_runtime_metrics_source(source_id: str, metadata: dict) -> dict:
    parquet_path = _find_primary_parquet(source_id, metadata)
    if parquet_path is None:
        return {"source_id": source_id, "status": "skipped", "reason": "missing_parquet"}

    try:
        available_columns = parquet_columns(parquet_path)
    except Exception as exc:
        return {"source_id": source_id, "status": "skipped", "reason": "source_unavailable", "detail": str(exc)}
    if "loc_id" not in available_columns:
        return {"source_id": source_id, "status": "skipped", "reason": "missing_location_field"}

    time_field = str(((metadata.get("temporal_coverage") or {}).get("field")) or "").strip() or None
    if time_field and time_field not in available_columns:
        time_field = None

    name_field = "name" if "name" in available_columns else ("NAME" if "NAME" in available_columns else None)
    metric_ids = [metric_id for metric_id in (metadata.get("metrics") or {}).keys() if metric_id in available_columns]

    select_columns = ["loc_id"]
    if time_field:
        select_columns.append(time_field)
    if name_field:
        select_columns.append(name_field)
    for metric_id in metric_ids:
        if metric_id not in select_columns:
            select_columns.append(metric_id)

    try:
        rows = _load_runtime_rows(parquet_path, select_columns)
    except Exception as exc:
        return {"source_id": source_id, "status": "skipped", "reason": "source_unavailable", "detail": str(exc)}
    if not rows:
        return {"source_id": source_id, "status": "skipped", "reason": "no_rows"}

    normalized_rows = []
    for row in rows:
        normalized = dict(row)
        if name_field and name_field != "name" and name_field in normalized:
            normalized["name"] = normalized.get(name_field)
        normalized_rows.append(normalized)

    pseudo_spec = SimpleNamespace(
        location_field="loc_id",
        time_field=time_field,
        metrics={metric_id: None for metric_id in metric_ids},
    )
    result = _rows_to_temporal_result(normalized_rows, source_id, metadata, pseudo_spec) if time_field else _rows_to_static_result(normalized_rows, source_id, metadata, pseudo_spec)
    return {"source_id": source_id, "status": "loaded", "row_count": len(normalized_rows), "result": result}


def _hydrate_runtime_geometry_source(source_id: str, metadata: dict) -> dict:
    parquet_path = _find_primary_parquet(source_id, metadata)
    if parquet_path is None:
        return {"source_id": source_id, "status": "skipped", "reason": "missing_parquet"}

    try:
        available_columns = parquet_columns(parquet_path)
    except Exception as exc:
        return {"source_id": source_id, "status": "skipped", "reason": "source_unavailable", "detail": str(exc)}
    if "geometry" not in available_columns:
        return {"source_id": source_id, "status": "skipped", "reason": "missing_geometry"}

    preferred_columns = [
        "loc_id", "parent_id", "name", "NAME", "feature_id", "building_id",
        "GlobalID", "OBJECTID", "BLDGIDENT", "TYPE", "BLDG_CM_TYPE", "BLDG_CM_LABEL",
        "BLDG_HEIGHT", "SOURCE", "geometry",
    ]
    select_columns = [column for column in preferred_columns if column in available_columns]
    try:
        rows = _load_runtime_rows_raw(parquet_path, select_columns)
    except Exception:
        return _hydrate_runtime_metrics_source(source_id, metadata)
    if not rows:
        return {"source_id": source_id, "status": "skipped", "reason": "no_rows"}

    features = []
    for row in rows:
        geometry_value = row.get("geometry")
        if not geometry_value:
            continue
        try:
            if isinstance(geometry_value, str):
                stripped = geometry_value.strip()
                if stripped.startswith("{"):
                    geometry = json.loads(stripped)
                else:
                    geometry = shapely_mapping(shapely_wkt.loads(stripped))
            else:
                geometry = geometry_value
        except Exception:
            continue
        props = {k: v for k, v in row.items() if k != "geometry"}
        if "feature_id" not in props:
            props["feature_id"] = (
                props.get("GlobalID")
                or props.get("OBJECTID")
                or props.get("BLDGIDENT")
                or props.get("loc_id")
            )
        if "name" not in props and props.get("NAME"):
            props["name"] = props.get("NAME")
        if "name" not in props:
            props["name"] = props.get("feature_id") or props.get("building_id") or props.get("BLDGIDENT") or props.get("loc_id")
        features.append({"type": "Feature", "geometry": geometry, "properties": props})

    if not features:
        return {"source_id": source_id, "status": "skipped", "reason": "no_features"}

    result = {
        "type": "data",
        "data_type": "geometry",
        "source_id": source_id,
        "overlay_type": metadata.get("overlay_type"),
        "geojson": {"type": "FeatureCollection", "features": features},
        "available_metrics": [],
        "summary": _source_summary_text(source_id, metadata, len(features)),
        "count": len(features),
        "sources": [{"id": source_id, "name": str(metadata.get("source_name") or source_id)}],
    }
    return {"source_id": source_id, "status": "loaded", "row_count": len(features), "result": result}


def _hydrate_runtime_source(source_id: str, metadata: dict) -> dict:
    data_type = metadata.get("data_type")
    kinds = data_type if isinstance(data_type, list) else [data_type]
    normalized_kinds = {str(kind or "").strip().lower() for kind in kinds if kind}
    if "geometry" in normalized_kinds:
        return _hydrate_runtime_geometry_source(source_id, metadata)
    return _hydrate_runtime_metrics_source(source_id, metadata)


def _hydrate_saved_source_into_research(*, session_id: str, corpus_id: str, source_id: str) -> dict:
    metadata = load_source_metadata(source_id) or {}
    if not _is_runtime_research_source(metadata):
        return {"source_id": source_id, "status": "skipped", "reason": "source_not_runtime_ready"}

    if _should_register_live_source_artifact(metadata):
        request_key = _saved_corpus_request_key(corpus_id, source_id)
        artifact = corpus_registry.register_live_source_artifact(
            session_id=session_id,
            request_key=request_key,
            source_id=source_id,
        )
        if artifact:
            return {
                "source_id": source_id,
                "status": "loaded",
                "row_count": int(metadata.get("row_count") or 0),
                "hydration_mode": "live_source",
            }

    runtime_outcome = _hydrate_runtime_source(source_id, metadata)
    result = runtime_outcome.get("result")
    if runtime_outcome.get("status") == "loaded" and result:
        request_key = _saved_corpus_request_key(corpus_id, source_id)
        session_manager.get_or_create(session_id).store_result(request_key, result)
        order = {
            "items": [{"source_id": source_id, "region": "global", "metric": None}],
            "summary": result.get("summary") or f"Loaded {source_id} into Research.",
        }
        corpus_registry.register_order_result(
            session_id=session_id,
            request_key=request_key,
            order=order,
            response=result,
        )
        return {
            "source_id": source_id,
            "status": "loaded",
            "row_count": int(runtime_outcome.get("row_count") or 0),
        }

    spec = get_api_source_spec(source_id)
    if spec is None:
        return runtime_outcome

    try:
        available_columns = get_api_source_columns(spec)
    except Exception as exc:
        logger.warning("Research hydration skipped source %s while reading columns: %s", source_id, exc)
        return {
            "source_id": source_id,
            "status": "skipped",
            "reason": "source_unavailable",
            "detail": str(exc),
        }
    if spec.location_field not in available_columns:
        return {"source_id": source_id, "status": "skipped", "reason": "missing_location_field"}

    select_columns = [spec.location_field]
    if spec.time_field and spec.time_field in available_columns:
        select_columns.append(spec.time_field)
    if "name" in available_columns:
        select_columns.append("name")
    dimension_columns: list[str] = []
    metadata_dimensions = metadata.get("dimensions") if isinstance(metadata.get("dimensions"), dict) else {}
    for dim_key, dim_spec in metadata_dimensions.items():
        if not isinstance(dim_spec, dict):
            continue
        column_name = str(dim_spec.get("column") or dim_key).strip()
        if not column_name or column_name not in available_columns:
            continue
        if column_name not in dimension_columns:
            dimension_columns.append(column_name)
        if column_name not in select_columns:
            select_columns.append(column_name)

    metric_ids = []
    for metric_id, metric_spec in spec.metrics.items():
        column_name = metric_spec.column
        if metric_id == "event_count":
            continue
        if column_name in available_columns and metric_id not in metric_ids:
            metric_ids.append(metric_id)
            if column_name not in select_columns:
                select_columns.append(column_name)

    try:
        rows = execute_dataset_query(
            spec,
            select_columns=select_columns,
            limit=None,
        )
    except Exception as exc:
        logger.warning("Research hydration skipped source %s while loading rows: %s", source_id, exc)
        return {
            "source_id": source_id,
            "status": "skipped",
            "reason": "source_unavailable",
            "detail": str(exc),
        }
    if not rows:
        return {"source_id": source_id, "status": "skipped", "reason": "no_rows"}

    if spec.time_field:
        result = _rows_to_temporal_result(rows, source_id, metadata, spec, dimension_columns=dimension_columns)
    else:
        result = _rows_to_static_result(rows, source_id, metadata, spec)

    request_key = _saved_corpus_request_key(corpus_id, source_id)
    session_manager.get_or_create(session_id).store_result(request_key, result)

    order = {
        "items": [
            {
                "source_id": source_id,
                "region": "global",
                "metric": metric_ids[0] if metric_ids else None,
            }
        ],
        "summary": result.get("summary") or f"Loaded {source_id} into Research.",
    }
    corpus_registry.register_order_result(
        session_id=session_id,
        request_key=request_key,
        order=order,
        response=result,
    )
    return {
        "source_id": source_id,
        "status": "loaded",
        "row_count": len(rows),
    }


def _hydrate_saved_corpus(session_id: str, saved_corpus: dict) -> dict:
    corpus_registry.clear_artifacts(session_id)
    source_ids = _expected_saved_corpus_source_ids(saved_corpus)

    hydration = {
        "loaded_sources": [],
        "skipped_sources": [],
    }
    for source_id in source_ids:
        outcome = _hydrate_saved_source_into_research(
            session_id=session_id,
            corpus_id=str(saved_corpus.get("id") or "saved"),
            source_id=source_id,
        )
        if outcome.get("status") == "loaded":
            logger.info("Research saved corpus hydrated source %s rows=%s", source_id, outcome.get("row_count"))
            hydration["loaded_sources"].append(outcome)
        else:
            logger.info(
                "Research saved corpus skipped source %s reason=%s detail=%s",
                source_id,
                outcome.get("reason"),
                outcome.get("detail"),
            )
            hydration["skipped_sources"].append(outcome)
    return hydration


def _json_safe_value(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, set):
        return [_json_safe_value(item) for item in value]
    return value


def _normalize_browser_artifact(raw_value: dict | None) -> dict | None:
    if not isinstance(raw_value, dict):
        return None

    def _coerce_int(value) -> int:
        try:
            return int(round(float(value or 0)))
        except (TypeError, ValueError):
            return 0

    storage_key = str(raw_value.get("storage_key") or "").strip()
    sha256 = str(raw_value.get("sha256") or "").strip()
    artifact_version = str(raw_value.get("artifact_version") or "").strip()
    format_name = str(raw_value.get("format") or "").strip()
    transfer_bytes = _coerce_int(raw_value.get("transfer_bytes"))
    stored_bytes = _coerce_int(raw_value.get("stored_bytes") or transfer_bytes)
    expanded_bytes = _coerce_int(raw_value.get("expanded_bytes"))
    if not storage_key:
        return None
    return {
        "contract_version": int(raw_value.get("contract_version") or 1),
        "artifact_version": artifact_version,
        "format": format_name,
        "storage_key": storage_key,
        "sha256": sha256,
        "transfer_bytes": transfer_bytes,
        "stored_bytes": stored_bytes,
        "expanded_bytes": expanded_bytes,
        "transfer_mb": round(transfer_bytes / (1024 * 1024), 2) if transfer_bytes > 0 else 0.0,
        "stored_mb": round(stored_bytes / (1024 * 1024), 2) if stored_bytes > 0 else 0.0,
        "expanded_mb": round(expanded_bytes / (1024 * 1024), 2) if expanded_bytes > 0 else 0.0,
        "generated_at": str(raw_value.get("generated_at") or "").strip(),
    }


def _catalog_source_lookup() -> dict[str, dict]:
    catalog = load_catalog() or {}
    lookup: dict[str, dict] = {}
    for source in catalog.get("sources") or []:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id") or "").strip()
        if source_id:
            lookup[source_id] = source
    return lookup


def _build_browser_install_manifest(saved_corpus: dict) -> dict:
    source_ids = _expected_saved_corpus_source_ids(saved_corpus)
    if not source_ids:
        raise ValueError("Saved corpus has no resolved sources")

    source_lookup = _catalog_source_lookup()
    manifest_sources = []
    total_transfer_bytes = 0
    total_stored_bytes = 0
    total_expanded_bytes = 0
    artifact_ready_source_count = 0

    for source_id in source_ids:
        source = source_lookup.get(source_id)
        if not isinstance(source, dict):
            raise ValueError(f"Published catalog is missing source metadata for {source_id}")
        artifact = _normalize_browser_artifact(source.get("browser_artifact"))
        artifact_ready = bool(
            artifact
            and artifact.get("transfer_bytes", 0) > 0
            and artifact.get("stored_bytes", 0) > 0
            and artifact.get("expanded_bytes", 0) > 0
        )
        if artifact_ready:
            artifact_ready_source_count += 1
            total_transfer_bytes += int(artifact["transfer_bytes"])
            total_stored_bytes += int(artifact["stored_bytes"])
            total_expanded_bytes += int(artifact["expanded_bytes"])
        proxy_path = f"/api/research/browser-save/source-artifact/{saved_corpus.get('id')}/{source_id}" if artifact_ready else ""
        direct_url = _presign_browser_artifact_url(artifact.get("storage_key")) if artifact_ready else ""
        manifest_sources.append({
            "source_id": source_id,
            "source_name": str(source.get("source_name") or source_id),
            "pack_id": str(source.get("pack_id") or "").strip(),
            "path": str(source.get("path") or "").strip(),
            "browser_artifact": artifact if artifact_ready else None,
            "size": source.get("size") if isinstance(source.get("size"), dict) else None,
            "download_url": direct_url,
            "download_path": proxy_path,
            "download_expires_in": _browser_artifact_url_ttl_seconds() if direct_url else 0,
        })
    install_mode = "source_artifacts" if artifact_ready_source_count == len(source_ids) else "manifest_only"

    return {
        "manifest_version": 1,
        "install_mode": install_mode,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "saved_corpus": {
            "id": saved_corpus.get("id"),
            "name": saved_corpus.get("name"),
            "updated_at": saved_corpus.get("updated_at"),
            "source_ids": saved_corpus.get("source_ids") or [],
            "resolved_source_ids": source_ids,
            "pack_count": saved_corpus.get("pack_count"),
            "source_count": saved_corpus.get("source_count"),
            "resolved_source_count": len(source_ids),
            "artifact_ready_source_count": artifact_ready_source_count,
        },
        "sources": manifest_sources,
        "totals": {
            "transfer_bytes": total_transfer_bytes,
            "stored_bytes": total_stored_bytes,
            "expanded_bytes": total_expanded_bytes,
            "transfer_mb": round(total_transfer_bytes / (1024 * 1024), 2),
            "stored_mb": round(total_stored_bytes / (1024 * 1024), 2),
            "expanded_mb": round(total_expanded_bytes / (1024 * 1024), 2),
        },
    }


def _browser_artifact_url_ttl_seconds() -> int:
    try:
        return max(60, min(3600, int(os.environ.get("BROWSER_ARTIFACT_SIGNED_URL_TTL", "600"))))
    except (TypeError, ValueError):
        return 600


def _presign_browser_artifact_url(storage_key: str | None) -> str:
    """Return a short-lived direct object-store URL, or empty for proxy fallback."""
    storage_key = str(storage_key or "").strip().lstrip("/")
    if not storage_key or not is_cloud_mode():
        return ""
    try:
        import boto3 as _boto3
        from mapmover.runtime_config import get_runtime_config

        cloud_cfg = get_runtime_config().get("cloud", {})
        bucket = os.environ.get("S3_BUCKET", "").strip() or str(cloud_cfg.get("bucket", "")).strip()
        endpoint_url = os.environ.get("S3_ENDPOINT_URL") or cloud_cfg.get("endpoint_url")
        region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "auto"
        if not bucket:
            return ""
        client = _boto3.client("s3", endpoint_url=endpoint_url, region_name=region)
        return str(client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": storage_key},
            ExpiresIn=_browser_artifact_url_ttl_seconds(),
        ) or "")
    except Exception as exc:
        logger.warning("Could not sign browser artifact %s; using Railway proxy: %s", storage_key, exc)
        return ""


def _read_browser_artifact_bytes(storage_key: str) -> tuple[bytes, str]:
    storage_key = str(storage_key or "").strip().lstrip("/")
    if not storage_key:
        raise FileNotFoundError("No browser artifact storage key provided")
    if is_cloud_mode():
        import boto3 as _boto3
        from botocore.exceptions import ClientError as _BotoClientError
        from mapmover.runtime_config import get_runtime_config

        cloud_cfg = get_runtime_config().get("cloud", {})
        bucket = os.environ.get("S3_BUCKET", "").strip() or str(cloud_cfg.get("bucket", "")).strip()
        endpoint_url = os.environ.get("S3_ENDPOINT_URL") or cloud_cfg.get("endpoint_url")
        region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "auto"
        client = _boto3.client("s3", endpoint_url=endpoint_url, region_name=region)
        try:
            obj = client.get_object(Bucket=bucket, Key=storage_key)
        except _BotoClientError as exc:
            error_code = (exc.response or {}).get("Error", {}).get("Code", "")
            status_code = (exc.response or {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error_code in ("NoSuchKey", "NoSuchBucket", "404") or status_code == 404:
                raise FileNotFoundError(
                    f"Browser artifact not found in cloud at key {storage_key}"
                ) from exc
            raise
        body = obj["Body"].read()
        content_type = str(obj.get("ContentType") or "application/gzip")
        return body, content_type

    local_path = (PRIVATE_BROWSER_ARTIFACT_OUTPUT_ROOT / storage_key.replace("/", os.sep)).resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"Local browser artifact not found: {local_path}")
    return local_path.read_bytes(), "application/gzip"


def _restore_browser_install_source_snapshots(
    session_id: str,
    saved_corpus: dict,
    source_snapshots: list[dict] | None,
) -> dict:
    expected_source_ids = _expected_saved_corpus_source_ids(saved_corpus)
    expected_source_set = set(expected_source_ids)
    if not expected_source_ids:
        raise ValueError("Saved corpus has no resolved sources")

    cache = session_manager.get_or_create(session_id)
    corpus_registry.clear_artifacts(session_id)
    corpus_registry.set_saved_corpus(session_id, saved_corpus)

    seen_source_ids: set[str] = set()
    for snapshot in source_snapshots or []:
        if not isinstance(snapshot, dict):
            continue
        source_meta = snapshot.get("source") or {}
        result = snapshot.get("result")
        source_id = str(source_meta.get("source_id") or "").strip()
        if not source_id:
            raise ValueError("Source snapshot is missing source_id")
        if source_id in seen_source_ids:
            continue
        if source_id not in expected_source_set:
            raise ValueError(f"Source snapshot {source_id} is not part of the saved corpus")
        if not isinstance(result, dict):
            raise ValueError(f"Source snapshot {source_id} is missing result payload")

        request_key = _saved_corpus_request_key(str(saved_corpus.get("id") or "saved"), source_id)
        cache.store_result(request_key, result)
        order = {
            "items": [
                {
                    "source_id": source_id,
                    "region": "global",
                    "metric": next(iter(result.get("available_metrics") or []), None),
                }
            ],
            "summary": result.get("summary") or f"Loaded {source_id} into Research.",
        }
        corpus_registry.register_order_result(
            session_id=session_id,
            request_key=request_key,
            order=order,
            response=result,
        )
        seen_source_ids.add(source_id)

    if seen_source_ids != expected_source_set:
        missing = sorted(expected_source_set - seen_source_ids)
        raise ValueError(
            "Browser source install is incomplete for this saved corpus "
            f"(missing source snapshots: {missing})"
        )

    return corpus_registry.manifest(session_id)


def _published_browser_install_source_snapshots(saved_corpus: dict) -> list[dict]:
    manifest = _build_browser_install_manifest(saved_corpus)
    decoded_snapshots: list[dict] = []
    for source_entry in manifest.get("sources") or []:
        browser_artifact = source_entry.get("browser_artifact") or {}
        storage_key = str(browser_artifact.get("storage_key") or "").strip()
        source_id = str(source_entry.get("source_id") or "").strip()
        if not storage_key:
            raise ValueError(f"Published browser artifact metadata is incomplete for {source_id or 'unknown source'}")
        artifact_bytes, _ = _read_browser_artifact_bytes(storage_key)
        try:
            json_bytes = gzip.decompress(artifact_bytes)
            decoded_snapshot = json.loads(json_bytes.decode("utf-8"))
        except Exception as exc:
            raise ValueError(
                f"Could not decode published browser artifact payload for {source_id or 'unknown source'}: {exc}"
            ) from exc
        if not isinstance(decoded_snapshot, dict):
            raise ValueError(f"Published browser artifact payload is invalid for {source_id or 'unknown source'}")
        decoded_snapshots.append(decoded_snapshot)
    return decoded_snapshots


def _restore_saved_corpus_from_published_browser_artifacts(session_id: str, saved_corpus: dict) -> dict:
    return _restore_browser_install_source_snapshots(
        session_id=session_id,
        saved_corpus=saved_corpus,
        source_snapshots=_published_browser_install_source_snapshots(saved_corpus),
    )


def _decode_browser_source_artifact_payloads(source_artifacts: list[dict] | None) -> list[dict]:
    decoded_snapshots: list[dict] = []
    for artifact_entry in source_artifacts or []:
        if not isinstance(artifact_entry, dict):
            continue
        payload = artifact_entry.get("payload")
        if isinstance(payload, memoryview):
            payload = payload.tobytes()
        elif isinstance(payload, bytearray):
            payload = bytes(payload)
        if not isinstance(payload, (bytes, bytearray)):
            raise ValueError("Browser source artifact payload must be binary")
        try:
            json_bytes = gzip.decompress(bytes(payload))
            decoded_snapshot = json.loads(json_bytes.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"Could not decode browser source artifact payload: {exc}") from exc
        if not isinstance(decoded_snapshot, dict):
            raise ValueError("Decoded browser source artifact payload is invalid")
        decoded_snapshots.append(decoded_snapshot)
    return decoded_snapshots


def _focus_entities_from_coverage(coverage: dict) -> tuple[int | None, list[str]]:
    if not isinstance(coverage, dict):
        return (None, [])
    admin_levels = coverage.get("admin_levels") or []
    if not admin_levels:
        return (None, [])
    lowest = min(int(level) for level in admin_levels if isinstance(level, (int, float)) or str(level).lstrip("-").isdigit())

    if lowest == 0:
        coverage_type = str(coverage.get("type") or "").strip().lower()
        if coverage_type == "country":
            country = str(coverage.get("country") or "").strip()
            return (0, [country] if country else [])
        if coverage_type in ("multi_country", "regional"):
            return (0, [str(c).strip() for c in (coverage.get("countries") or []) if str(c).strip()])
        if coverage_type == "global":
            return (0, [])
        return (None, [])

    if lowest == 1:
        country = str(coverage.get("country") or "").strip()
        states = coverage.get("states") or ([coverage.get("state")] if coverage.get("state") else [])
        if not country:
            return (None, [])
        return (1, [f"{country}-{str(s).strip()}" for s in states if str(s or "").strip()])

    if lowest == 2:
        country = str(coverage.get("country") or "").strip()
        state = str(coverage.get("state") or "").strip()
        counties = coverage.get("counties") or ([coverage.get("county")] if coverage.get("county") else [])
        if not (country and state):
            return (None, [])
        return (2, [f"{country}-{state}-{str(c).strip()}" for c in counties if str(c or "").strip()])

    return (None, [])


def _build_research_focus_geojson(session_id: str) -> dict | None:
    artifacts = corpus_registry.list_artifacts(session_id)
    if not artifacts:
        return None

    per_artifact: list[tuple[int, list[str]]] = []
    for artifact in artifacts:
        source_id = str(artifact.get("source_id") or "").strip()
        if not source_id:
            continue
        metadata = load_source_metadata(source_id) or {}
        coverage = metadata.get("geographic_coverage") if isinstance(metadata.get("geographic_coverage"), dict) else None
        level, entities = _focus_entities_from_coverage(coverage or {})
        if level is None:
            continue
        per_artifact.append((level, entities))

    if not per_artifact:
        return _build_research_focus_geojson_from_loaded_results(session_id)

    corpus_lowest = min(level for level, _ in per_artifact)
    union: list[str] = []
    seen = set()
    for level, entities in per_artifact:
        if level != corpus_lowest:
            continue
        for entity in entities:
            if entity and entity not in seen:
                seen.add(entity)
                union.append(entity)

    if not union:
        return None

    geojson = get_selection_geometries(union)
    if ((geojson or {}).get("features") or []):
        return geojson
    return _build_research_focus_geojson_from_loaded_results(session_id)


def _focus_candidates_from_loc_id(loc_id: str) -> list[tuple[str, int]]:
    text = str(loc_id or "").strip()
    if not text:
        return []
    candidates: list[tuple[str, int]] = [(text, 1)]
    parts = text.split("-")
    if len(parts) >= 3 and len(parts[1]) == 2 and parts[2].isdigit():
        candidates.append(("-".join(parts[:3]), 25))
    if len(parts) >= 2 and len(parts[1]) == 2:
        candidates.append(("-".join(parts[:2]), 10))
    return candidates


def _candidate_sort_key(item: tuple[str, int]) -> tuple[int, int, int, str]:
    candidate, weight = item
    parts = candidate.split("-")
    return (-weight, len(parts), len(candidate), candidate)


def _build_research_focus_geojson_from_loaded_results(session_id: str) -> dict | None:
    cache = session_manager.get(session_id)
    if cache is None:
        return None

    candidate_weights: dict[str, int] = {}
    for result in cache.export_results().values():
        geojson = (result or {}).get("geojson") or {}
        features = geojson.get("features") or []
        for feature in features[:1000]:
            props = feature.get("properties") or {}
            loc_id = str(props.get("loc_id") or "").strip()
            if not loc_id:
                continue
            for candidate, weight in _focus_candidates_from_loc_id(loc_id):
                candidate_weights[candidate] = candidate_weights.get(candidate, 0) + weight

    if not candidate_weights:
        return None

    for candidate, _weight in sorted(candidate_weights.items(), key=_candidate_sort_key):
        geojson = get_selection_geometries([candidate]) or {}
        if (geojson.get("features") or []):
            return geojson
    return None
