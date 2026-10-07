"""
Reusable aggregation contract for runtime and converters.

Core goals:
- One normalized AggregationSpec object
- Shared method/granularity aliases
- Deterministic temporal aggregation helper
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, Optional, Tuple

import pandas as pd


_METHOD_ALIASES = {
    "period_end": "last",
    "period_last": "last",
    "last": "last",
    "latest": "last",
    "period_avg": "mean",
    "period_average": "mean",
    "avg": "mean",
    "average": "mean",
    "mean": "mean",
    "sum": "sum",
    "min": "min",
    "max": "max",
}

_GRANULARITY_ALIASES = {
    "day": "daily",
    "daily": "daily",
    "week": "weekly",
    "weekly": "weekly",
    "month": "monthly",
    "monthly": "monthly",
    "year": "yearly",
    "yearly": "yearly",
    "annual": "yearly",
}

_FREQ_BY_GRANULARITY = {
    "daily": "D",
    "weekly": "W-FRI",
    "monthly": "ME",
    "yearly": "YE",
}

_POINT_IN_TIME_KEYWORDS = {
    "fx", "exchange", "currency", "price", "index", "rate", "local_per_usd"
}

_FLOW_KEYWORDS = {
    "count", "total", "deaths", "injuries", "damage", "rain", "precip", "area", "population"
}

_RATIO_KEYWORDS = {
    "pct", "percent", "ratio", "rate", "per_capita", "per capita"
}

_EXTREME_KEYWORDS = {
    "max", "min", "peak", "highest", "lowest"
}


@dataclass(frozen=True)
class AggregationSpec:
    axis: str = "temporal"
    method: str = "mean"
    time_granularity: str = "yearly"
    missing_policy: str = "skip"
    weight_metric: Optional[str] = None
    week_anchor: str = "FRI"
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_method(value: Optional[str], default: str = "mean") -> str:
    if not value:
        return default
    return _METHOD_ALIASES.get(str(value).strip().lower(), default)


def normalize_granularity(value: Optional[str], default: str = "yearly") -> str:
    if not value:
        return default
    return _GRANULARITY_ALIASES.get(str(value).strip().lower(), default)


def build_aggregation_spec(order_item: Dict[str, Any], source_metadata: Optional[Dict[str, Any]] = None) -> AggregationSpec:
    source_id = (order_item or {}).get("source_id", "")
    source_id = str(source_id).strip().lower()

    requested_granularity = order_item.get("time_granularity")
    default_granularity = "monthly" if source_id == "fx_usd_historical" else "yearly"
    granularity = normalize_granularity(requested_granularity, default=default_granularity)

    # FX defaults to point-in-time convention when not explicitly requested.
    default_method = "last" if source_id == "fx_usd_historical" else "mean"
    requested_method = order_item.get("aggregation")
    method = normalize_method(requested_method, default=default_method)

    axis = str(order_item.get("aggregation_axis", "temporal")).strip().lower()
    if axis not in {"temporal", "spatial", "grouping"}:
        axis = "temporal"

    note = ""
    if source_metadata and source_metadata.get("source_id"):
        note = f"source={source_metadata.get('source_id')}"

    return AggregationSpec(
        axis=axis,
        method=method,
        time_granularity=granularity,
        missing_policy=str(order_item.get("missing_policy", "skip")).strip().lower(),
        weight_metric=order_item.get("weight_metric"),
        week_anchor=str(order_item.get("week_anchor", "FRI")).strip().upper() or "FRI",
        note=note,
    )


def classify_metric_pattern(source_id: str, metric_name: str, metric_info: Optional[Dict[str, Any]] = None) -> str:
    """
    Coarse classifier aligned with AGGREGATION_SYSTEM decision table.
    Returns one of:
      additive | ratio | point_in_time | flow | extreme | composite | generic
    """
    source_id = (source_id or "").lower()
    name = (metric_name or "").lower()
    agg = ((metric_info or {}).get("aggregation") or "").lower()

    if source_id == "fx_usd_historical":
        return "point_in_time"

    if agg == "skip":
        return "composite"
    if agg in {"max", "min"}:
        return "extreme"
    if agg in {"avg", "weighted_avg", "mean", "average"}:
        return "ratio"
    if agg == "sum":
        return "additive"

    if any(k in name for k in _POINT_IN_TIME_KEYWORDS):
        return "point_in_time"
    if any(k in name for k in _EXTREME_KEYWORDS):
        return "extreme"
    if any(k in name for k in _RATIO_KEYWORDS):
        return "ratio"
    if any(k in name for k in _FLOW_KEYWORDS):
        return "flow"

    return "generic"


def _allowed_methods_for_pattern(pattern: str) -> set:
    if pattern == "point_in_time":
        return {"last", "mean"}
    if pattern == "flow":
        return {"sum", "mean"}
    if pattern == "extreme":
        return {"max", "min"}
    if pattern == "ratio":
        return {"mean"}
    if pattern == "composite":
        return set()
    if pattern == "additive":
        return {"sum"}
    return {"mean", "sum", "last", "min", "max"}


def validate_aggregation_policy(
    order_item: Dict[str, Any],
    *,
    source_metadata: Optional[Dict[str, Any]] = None,
    metric_name: Optional[str] = None,
    metric_info: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate order aggregation fields against the canonical policy.

    Returns:
      (is_valid, error_message_or_none, policy_trace_dict)
    """
    source_id = str((order_item or {}).get("source_id") or "").strip()
    granularity_raw = order_item.get("time_granularity")
    method_raw = order_item.get("aggregation")

    # If no aggregation override requested, policy check passes.
    if not granularity_raw and not method_raw:
        return True, None, {"checked": False, "reason": "no_temporal_override"}

    granularity = normalize_granularity(granularity_raw, default="yearly")
    method = normalize_method(method_raw, default=("last" if source_id.lower() == "fx_usd_historical" else "mean"))
    pattern = classify_metric_pattern(source_id, metric_name or "", metric_info)
    allowed_methods = _allowed_methods_for_pattern(pattern)

    trace = {
        "checked": True,
        "source_id": source_id,
        "metric": metric_name,
        "pattern": pattern,
        "requested_granularity": granularity_raw,
        "normalized_granularity": granularity,
        "requested_method": method_raw,
        "normalized_method": method,
        "allowed_methods": sorted(list(allowed_methods)),
    }

    if pattern == "composite" and method_raw:
        return False, "Composite metrics do not allow direct aggregation override.", trace

    if method not in allowed_methods:
        return False, (
            f"Aggregation '{method_raw}' is not allowed for metric pattern '{pattern}'. "
            f"Allowed: {', '.join(sorted(allowed_methods)) or 'none'}."
        ), trace

    # Granularity policy: annual sources only support yearly unless source has explicit higher-frequency runtime path.
    temporal = (source_metadata or {}).get("temporal_coverage", {})
    frequency = str(temporal.get("frequency", "")).lower()
    supports_high_freq_runtime = source_id.lower() == "fx_usd_historical"
    if frequency in {"annual", "yearly"} and granularity != "yearly" and not supports_high_freq_runtime:
        return False, (
            f"Source '{source_id}' has {frequency} coverage; time_granularity '{granularity_raw}' is not supported."
        ), trace

    return True, None, trace


def _apply_method(grouped: pd.core.resample.Resampler, method: str) -> pd.Series:
    if method == "last":
        return grouped.last()
    if method == "sum":
        return grouped.sum()
    if method == "min":
        return grouped.min()
    if method == "max":
        return grouped.max()
    # default and "mean"
    return grouped.mean()


def apply_temporal_aggregation(
    df: pd.DataFrame,
    spec: AggregationSpec,
    *,
    date_col: str,
    value_col: str,
    group_cols: Iterable[str] = ("loc_id",),
) -> pd.DataFrame:
    """
    Aggregate a time series to requested granularity.
    Returns columns: [*group_cols, date_col, value_col]
    """
    if df.empty or date_col not in df.columns or value_col not in df.columns:
        return pd.DataFrame(columns=[*group_cols, date_col, value_col])

    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.dropna(subset=[date_col, value_col])
    if work.empty:
        return pd.DataFrame(columns=[*group_cols, date_col, value_col])

    freq = _FREQ_BY_GRANULARITY.get(spec.time_granularity, "YE")
    out_frames = []
    by_cols = [c for c in group_cols if c in work.columns]

    if not by_cols:
        by_cols = []
        grouped_items = [((), work)]
    else:
        grouped_items = list(work.groupby(by_cols, dropna=False))

    for key, grp in grouped_items:
        series = grp.set_index(date_col)[value_col].sort_index()
        resampled = _apply_method(series.resample(freq), spec.method).dropna()
        if resampled.empty:
            continue
        part = pd.DataFrame({date_col: resampled.index, value_col: resampled.values})
        if by_cols:
            if not isinstance(key, tuple):
                key = (key,)
            for idx, col in enumerate(by_cols):
                part[col] = key[idx]
        out_frames.append(part)

    if not out_frames:
        return pd.DataFrame(columns=[*by_cols, date_col, value_col])

    out = pd.concat(out_frames, ignore_index=True)
    return out[[*by_cols, date_col, value_col]].sort_values([*by_cols, date_col]).reset_index(drop=True)
