"""Project source-owned metric caveats into executable display orders."""

from __future__ import annotations

import re


def _coerce_year(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    match = re.match(r"^-?\d{1,6}", text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def collect_metric_caveats(items: list[dict], *, load_source_metadata_func) -> list[str]:
    """Return deduplicated required framing for metrics actually selected.

    The caveat belongs to the source contract, not to the model's prose.  It is
    attached only after an order is validated, so an unrelated metric does not
    produce a warning merely because its column exists in the source.
    """
    caveats: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("_valid"):
            continue
        source_id = str(item.get("source_id") or "").strip()
        metric_id = str(item.get("metric") or "").strip()
        if not source_id or not metric_id:
            continue
        metadata = load_source_metadata_func(source_id) or {}
        metric = (metadata.get("metrics") or {}).get(metric_id) or {}
        semantics = metric.get("response_semantics") if isinstance(metric, dict) else {}
        framing = str((semantics or {}).get("required_framing") or "").strip()
        if not framing:
            continue
        item["source_caveats"] = list(dict.fromkeys([*(item.get("source_caveats") or []), framing]))
        if framing not in caveats:
            caveats.append(framing)
    return caveats


def append_source_caveats(summary: str | None, caveats: list[str]) -> str | None:
    """Append source-owned caveats once to the user-visible execution summary."""
    text = str(summary or "").strip()
    for caveat in caveats:
        if caveat.lower() not in text.lower():
            text = f"{text} {caveat}".strip()
    return text or None


def collect_metric_response_obligations(
    source_id: str,
    metric_ids: list[str],
    *,
    load_source_metadata_func,
) -> list[dict]:
    """Return source-owned answer obligations for metrics in a result payload.

    This is intentionally attached at the tool-result boundary, next to the
    rows that caused the obligation.  Client prompts can still describe the
    general rule, but deterministic tools should carry the specific caveats
    that apply to the returned fields.
    """
    source = str(source_id or "").strip()
    if not source:
        return []
    metadata = load_source_metadata_func(source) or {}
    metrics = metadata.get("metrics") or {}
    obligations: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for metric_id in metric_ids or []:
        metric_key = str(metric_id or "").strip()
        if not metric_key:
            continue
        metric = metrics.get(metric_key) or {}
        semantics = metric.get("response_semantics") if isinstance(metric, dict) else {}
        if not isinstance(semantics, dict) or not semantics:
            continue
        required_framing = str(semantics.get("required_framing") or "").strip()
        canonical_term = str(semantics.get("canonical_term") or "").strip()
        if not required_framing and not canonical_term:
            continue
        identity = (source, metric_key)
        if identity in seen:
            continue
        seen.add(identity)
        obligations.append(
            {
                "source_id": source,
                "metric": metric_key,
                "canonical_term": canonical_term or None,
                "required_framing": required_framing or None,
                "avoid_unqualified_terms": [
                    str(term).strip()
                    for term in (semantics.get("avoid_unqualified_terms") or [])
                    if str(term).strip()
                ],
                "accepted_framing_terms_any": [
                    str(term).strip()
                    for term in (
                        semantics.get("accepted_framing_terms_any")
                        or semantics.get("required_response_terms_any")
                        or []
                    )
                    if str(term).strip()
                ],
            }
        )
    return obligations


def collect_metric_availability(
    source_id: str,
    metric_ids: list[str],
    *,
    load_source_metadata_func,
) -> dict[str, dict]:
    """Return compact source-owned temporal availability for selected metrics."""
    source = str(source_id or "").strip()
    if not source:
        return {}
    metadata = load_source_metadata_func(source) or {}
    metrics = metadata.get("metrics") or {}
    availability: dict[str, dict] = {}
    for metric_id in metric_ids or []:
        metric_key = str(metric_id or "").strip()
        if not metric_key:
            continue
        metric = metrics.get(metric_key) or {}
        if not isinstance(metric, dict):
            continue
        entry: dict = {}
        years = metric.get("years")
        if (
            isinstance(years, list)
            and len(years) >= 2
            and years[0] is not None
            and years[1] is not None
        ):
            entry["start"] = years[0]
            entry["end"] = years[1]
            entry["years"] = [years[0], years[1]]
        for key in ("countries", "density"):
            if metric.get(key) is not None:
                entry[key] = metric.get(key)
        if entry:
            availability[metric_key] = entry
    return availability


def collect_metric_availability_warnings(
    metric_availability: dict[str, dict],
    normalized_time: dict | None,
) -> list[dict]:
    """Warn when a requested time cannot contain non-null selected metrics."""
    if not metric_availability or not isinstance(normalized_time, dict):
        return []

    requested_start = _coerce_year(normalized_time.get("start"))
    requested_end = _coerce_year(normalized_time.get("end"))
    requested_value = _coerce_year(normalized_time.get("value"))
    if requested_value is not None:
        requested_start = requested_value
        requested_end = requested_value
    if requested_start is None and requested_end is None:
        return []
    if requested_start is None:
        requested_start = requested_end
    if requested_end is None:
        requested_end = requested_start
    if requested_start is None or requested_end is None:
        return []

    outside: list[dict] = []
    for metric_id, availability in metric_availability.items():
        available_start = _coerce_year(availability.get("start"))
        available_end = _coerce_year(availability.get("end"))
        if available_start is None or available_end is None:
            continue
        if requested_end < available_start or requested_start > available_end:
            outside.append(
                {
                    "metric": metric_id,
                    "requested_start": requested_start,
                    "requested_end": requested_end,
                    "available_start": available_start,
                    "available_end": available_end,
                }
            )
    if not outside:
        return []
    return [
        {
            "code": "requested_time_outside_metric_availability",
            "message": (
                "The requested time range is outside the non-null year range "
                "published for one or more selected metrics."
            ),
            "metrics": outside,
        }
    ]


def collect_metric_response_contract(
    source_id: str,
    metric_ids: list[str],
    *,
    normalized_time: dict | None,
    load_source_metadata_func,
) -> dict[str, object]:
    """Return all source-owned metric response metadata for a query result."""
    response_obligations = collect_metric_response_obligations(
        source_id,
        metric_ids,
        load_source_metadata_func=load_source_metadata_func,
    )
    metric_availability = collect_metric_availability(
        source_id,
        metric_ids,
        load_source_metadata_func=load_source_metadata_func,
    )
    availability_warnings = collect_metric_availability_warnings(
        metric_availability,
        normalized_time,
    )
    return {
        "metric_availability": metric_availability,
        "response_obligations": response_obligations,
        "warnings": availability_warnings,
    }
