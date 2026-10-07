from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any

from fastapi.responses import JSONResponse

from mapmover.api_query_runtime import is_temporal_time_field
from mapmover.api_query_shared import build_api_error_response
from mapmover.runtime.api_contract_normalization import (
    normalize_machine_metrics,
    normalize_machine_region_ids,
)


PLAIN_YEAR_RE = re.compile(r"^-?\d{1,6}$")


def _build_query_scope_warning(scope: dict[str, Any], message: str) -> dict[str, Any]:
    estimated_work_score = int(scope.get("estimated_work_score") or 0)
    scope_class = str(scope.get("scope_class") or "").strip() or "broad"
    suggestions = scope.get("pricing_guidance") or query_scope_suggestions(scope)
    return {
        "level": "hard_cap",
        "measure": "query_scope",
        "scope_class": scope_class,
        "estimated_work_score": estimated_work_score,
        "message": message,
        "suggested_narrowing": list(suggestions) if isinstance(suggestions, list) else [],
    }


def _build_query_scope_cap_info(scope: dict[str, Any]) -> dict[str, Any]:
    estimated_work_score = max(1, int(scope.get("estimated_work_score") or 0))
    return {
        "cap_hit": True,
        "returned_rows": 0,
        "available_rows": estimated_work_score,
        "cap_value": 0,
        "cap_reason": "query_scope_gate",
        "cap_kind": "display_warning",
        "measure": "query_scope",
    }


def format_query_time_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def parse_temporal_filter_value(raw_value: Any) -> str:
    if isinstance(raw_value, (datetime, date)):
        return raw_value.isoformat()
    if raw_value is None:
        raise ValueError("missing")
    normalized = str(raw_value).strip()
    if not normalized:
        raise ValueError("blank")
    # DuckDB accepts the value later as a bound TIMESTAMP parameter. Validate
    # it here so malformed or partial strings become the public
    # ``invalid_time_range`` contract instead of escaping as a conversion
    # exception and turning the whole MCP request into an HTTP 500.
    candidate = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("invalid_temporal_value") from exc
    return normalized


def is_plain_year_token(raw_value: Any) -> bool:
    if isinstance(raw_value, bool) or raw_value is None:
        return False
    if isinstance(raw_value, int):
        return True
    text = str(raw_value).strip()
    return bool(text and PLAIN_YEAR_RE.match(text))


def format_year_start(year: int) -> str:
    return f"{int(year):04d}-01-01T00:00:00"


def format_year_end(year: int) -> str:
    return f"{int(year):04d}-12-31T23:59:59"


def env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def coerce_scope_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.year
    if isinstance(value, date):
        return value.year
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text[:4])
    except ValueError:
        return None


def scope_time_span_years(
    normalized_time: dict[str, Any],
    *,
    available_start: Any = None,
    available_end: Any = None,
) -> tuple[int | None, Any, Any, bool]:
    if "value" in normalized_time:
        value = normalized_time.get("value")
        return 1, value, value, False

    start = normalized_time.get("start")
    end = normalized_time.get("end")
    estimated = False
    if start is None:
        start = available_start
        estimated = True
    if end is None:
        end = available_end
        estimated = True

    start_year = coerce_scope_year(start)
    end_year = coerce_scope_year(end)
    if start_year is None or end_year is None:
        return None, start, end, estimated
    return max(1, end_year - start_year + 1), start, end, estimated


def query_scope_suggestions(scope: dict[str, Any]) -> list[str]:
    suggestions = [
        "Small queries stay cheap; very broad scans cost more or need narrower filters.",
    ]
    if not scope.get("has_time_filter"):
        suggestions.append("Add a time range, such as year_start/year_end or start/end.")
    elif scope.get("time_span_years") and int(scope.get("time_span_years") or 0) > 5:
        suggestions.append("Use a narrower time window when you only need a sample or top-N result.")
    if not scope.get("has_region_filter"):
        suggestions.append("Add region_ids to limit the geographic scope.")
    if not scope.get("is_event_count"):
        suggestions.append("Use event_count when you only need an aggregate count.")
    if scope.get("user_sort_count") and not scope.get("has_region_filter"):
        suggestions.append("Avoid sorting across a full dataset unless you also filter by time or geography.")
    return suggestions


def build_query_scope(
    spec,
    *,
    normalized_region_ids: list[str],
    normalized_time: dict[str, Any],
    raw_compare_filters: Any,
    normalized_sort: list[dict[str, str]],
    requested_sort_count: int,
    metrics: list[str],
    limit: int,
    output_format: str,
    available_start: Any = None,
    available_end: Any = None,
) -> dict[str, Any]:
    time_span_years, time_start, time_end, time_span_estimated = scope_time_span_years(
        normalized_time,
        available_start=available_start,
        available_end=available_end,
    )
    compare_filter_count = len(raw_compare_filters) if isinstance(raw_compare_filters, list) else 0
    is_event_count = metrics == ["event_count"]
    has_region_filter = bool(normalized_region_ids)
    has_time_filter = bool(normalized_time)

    work_score = 0
    if not has_time_filter and spec.time_field:
        work_score += 40
    elif time_span_years is not None:
        if time_span_years > 50:
            work_score += 30
        elif time_span_years > 25:
            work_score += 20
        elif time_span_years > 5:
            work_score += 10

    region_count = len(normalized_region_ids)
    if not has_region_filter:
        work_score += 20
    elif region_count > 25:
        work_score += 20
    elif region_count > 10:
        work_score += 10

    if not is_event_count:
        work_score += 15
    if requested_sort_count:
        work_score += 20 if not has_region_filter and (time_span_years is None or time_span_years > 5) else 10
    if compare_filter_count:
        work_score = max(0, work_score - min(15, compare_filter_count * 5))
    if limit > 500:
        work_score += 10

    if work_score >= 75:
        scope_class = "too_broad"
    elif work_score >= 45:
        scope_class = "broad"
    elif work_score >= 20:
        scope_class = "standard"
    else:
        scope_class = "small"

    return {
        "pack_id": spec.pack_id,
        "source_id": spec.source_id,
        "query_mode": spec.query_mode,
        "output_format": output_format,
        "limit": int(limit),
        "source_max_limit": int(spec.max_limit),
        "time_field": spec.time_field,
        "time_start": format_query_time_value(time_start),
        "time_end": format_query_time_value(time_end),
        "time_span_years": time_span_years,
        "time_span_estimated": bool(time_span_estimated),
        "has_time_filter": has_time_filter,
        "region_count": region_count,
        "has_region_filter": has_region_filter,
        "compare_filter_count": compare_filter_count,
        "sort_count": len(normalized_sort),
        "user_sort_count": requested_sort_count,
        "sort_fields": [str(item.get("field") or "") for item in normalized_sort if item.get("field")],
        "metric_count": len(metrics),
        "is_event_count": is_event_count,
        "scope_class": scope_class,
        "estimated_work_score": work_score,
        "pricing_guidance": query_scope_suggestions(
            {
                "has_time_filter": has_time_filter,
                "time_span_years": time_span_years,
                "has_region_filter": has_region_filter,
                "is_event_count": is_event_count,
                "user_sort_count": requested_sort_count,
            }
        ),
    }


def query_scope_rejection(scope: dict[str, Any]) -> dict[str, Any] | None:
    if str(scope.get("query_mode") or "") != "single_source_events":
        return None

    no_time = not scope.get("has_time_filter")
    no_region = not scope.get("has_region_filter")
    is_event_count = bool(scope.get("is_event_count"))
    time_span_years = scope.get("time_span_years")
    try:
        span = int(time_span_years) if time_span_years is not None else None
    except (TypeError, ValueError):
        span = None

    max_unscoped_years = env_int("QUERY_MAX_UNSCOPED_YEARS", 5, minimum=1)
    max_region_years = env_int("QUERY_MAX_REGION_YEARS", 50, minimum=1)
    max_aggregate_unscoped_years = env_int("QUERY_MAX_AGGREGATE_UNSCOPED_YEARS", 50, minimum=1)
    max_region_ids = env_int("QUERY_MAX_REGION_IDS", 25, minimum=1)
    reject_score = env_int("QUERY_REJECT_WORK_SCORE", 75, minimum=1)

    if int(scope.get("region_count") or 0) > max_region_ids:
        reason = f"region_ids is limited to {max_region_ids} entries for live dataset queries."
    elif no_time and no_region and not is_event_count:
        reason = "Event row queries must include a time filter or region_ids."
    elif no_time and no_region and bool(scope.get("user_sort_count")):
        reason = "Sorting a full event dataset without time or geography filters is too broad for live API access."
    elif no_region and span is not None and span > (max_aggregate_unscoped_years if is_event_count else max_unscoped_years):
        reason = "This time window is too broad without region_ids for live API access."
    elif scope.get("has_region_filter") and span is not None and span > max_region_years and not is_event_count:
        reason = "This time window is too broad for row-level live API access."
    elif int(scope.get("estimated_work_score") or 0) >= reject_score:
        reason = "This request is too broad for live API access."
    else:
        return None

    display_warning = _build_query_scope_warning(scope, reason)
    cap_info = _build_query_scope_cap_info(scope)
    return {
        "code": "query_too_broad",
        "message": reason,
        "details": {
            "scope_class": scope.get("scope_class"),
            "estimated_work_score": scope.get("estimated_work_score"),
            "suggestions": scope.get("pricing_guidance") or query_scope_suggestions(scope),
            "display_warning": display_warning,
            "cap_info": cap_info,
        },
        "retry_hint": "Narrow the request by time, geography, or aggregation before retrying.",
    }


def parse_time_filter(
    spec,
    time_filter: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, str, Any]]]:
    normalized_time: dict[str, Any] = {}
    exact_filters: dict[str, Any] = {}
    compare_filters: list[tuple[str, str, Any]] = []

    if spec.time_field is None:
        return normalized_time, exact_filters, compare_filters

    exact_value = time_filter.get("value")
    start_value = time_filter.get("start")
    end_value = time_filter.get("end")

    if exact_value is None and "year" in time_filter:
        exact_value = time_filter.get("year")
    if start_value is None and "year_start" in time_filter:
        start_value = time_filter.get("year_start")
    if end_value is None and "year_end" in time_filter:
        end_value = time_filter.get("year_end")

    if is_temporal_time_field(spec):
        if exact_value is not None:
            if is_plain_year_token(exact_value):
                year_value = int(str(exact_value).strip())
                normalized_time["start"] = format_year_start(year_value)
                normalized_time["end"] = format_year_end(year_value)
                compare_filters.append((spec.time_field, ">=", normalized_time["start"]))
                compare_filters.append((spec.time_field, "<=", normalized_time["end"]))
                return normalized_time, exact_filters, compare_filters
            coerced_value = parse_temporal_filter_value(exact_value)
            exact_filters[spec.time_field] = coerced_value
            normalized_time["value"] = coerced_value
            return normalized_time, exact_filters, compare_filters

        coerced_start = None
        coerced_end = None
        if start_value is not None:
            if is_plain_year_token(start_value):
                coerced_start = format_year_start(int(str(start_value).strip()))
            else:
                coerced_start = parse_temporal_filter_value(start_value)
            normalized_time["start"] = coerced_start
            compare_filters.append((spec.time_field, ">=", coerced_start))
        if end_value is not None:
            if is_plain_year_token(end_value):
                coerced_end = format_year_end(int(str(end_value).strip()))
            else:
                coerced_end = parse_temporal_filter_value(end_value)
            normalized_time["end"] = coerced_end
            compare_filters.append((spec.time_field, "<=", coerced_end))
        if coerced_start is not None and coerced_end is not None and coerced_start > coerced_end:
            raise ValueError("start_after_end")
        return normalized_time, exact_filters, compare_filters

    # Year-mode (non-temporal) sources. Inputs may be plain years (2000) OR full
    # date strings (2000-01-01) when an agent reuses one query shape across packs;
    # coerce both to a year rather than raw int() (which raised an uncaught
    # ValueError -> 500 on date strings for mixed year/timestamp sources).
    def _coerce_year(raw: Any) -> int | None:
        if is_plain_year_token(raw):
            return int(str(raw).strip())
        return coerce_scope_year(raw)

    if exact_value is not None:
        coerced_value = _coerce_year(exact_value)
        if coerced_value is None:
            raise ValueError("invalid_time_value")
        exact_filters[spec.time_field] = coerced_value
        normalized_time["value"] = coerced_value
        return normalized_time, exact_filters, compare_filters

    coerced_start = None
    coerced_end = None
    if start_value is not None:
        coerced_start = _coerce_year(start_value)
        if coerced_start is None:
            raise ValueError("invalid_time_value")
        normalized_time["start"] = coerced_start
        compare_filters.append((spec.time_field, ">=", coerced_start))
    if end_value is not None:
        coerced_end = _coerce_year(end_value)
        if coerced_end is None:
            raise ValueError("invalid_time_value")
        normalized_time["end"] = coerced_end
        compare_filters.append((spec.time_field, "<=", coerced_end))
    if coerced_start is not None and coerced_end is not None and coerced_start > coerced_end:
        raise ValueError("start_after_end")
    return normalized_time, exact_filters, compare_filters


def validate_metrics(
    spec,
    metrics: Any,
    *,
    request_id: str | None,
) -> tuple[list[str] | None, JSONResponse | None]:
    if metrics is not None and not isinstance(metrics, list):
        return None, build_api_error_response(
            request_id,
            "metric_not_available",
            "At least one valid metric is required.",
            400,
            details={"available_metrics": sorted(spec.metrics)},
            retry_hint="Choose one or more published metrics for this source.",
        )

    normalized_metrics, metrics_error, metrics_details = normalize_machine_metrics(spec, metrics)
    if metrics_error:
        return None, build_api_error_response(
            request_id,
            "metric_not_available",
            metrics_error,
            400,
            details=metrics_details,
            retry_hint="Choose one or more published metrics for this source.",
        )

    for metric in normalized_metrics:
        if metric not in spec.metrics:
            return None, build_api_error_response(
                request_id,
                "metric_not_available",
                f"Metric '{metric}' is not available for source '{spec.source_id}'.",
                400,
                details={"unknown_metric": metric, "available_metrics": sorted(spec.metrics)},
                retry_hint="Choose a metric listed for this source in the catalog.",
            )

    if "event_count" in normalized_metrics and len(normalized_metrics) > 1:
        return None, build_api_error_response(
            request_id,
            "metric_not_available",
            "event_count must be requested on its own.",
            400,
            retry_hint="Request event_count alone, or request raw event metrics without event_count.",
        )

    return normalized_metrics, None


def normalize_region_ids(region_ids: Any) -> tuple[list[str] | None, str | None]:
    return normalize_machine_region_ids(region_ids)
