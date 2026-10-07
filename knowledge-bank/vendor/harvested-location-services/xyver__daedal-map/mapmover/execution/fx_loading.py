from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def load_fx_with_aggregation(
    source_id: str,
    item: dict,
    metadata: dict,
    *,
    build_aggregation_spec_func,
    apply_temporal_aggregation_func,
    get_source_path_func,
    select_columns_from_parquet_func,
    extract_date_window_func,
) -> tuple[Optional[pd.DataFrame], dict]:
    """
    Load FX data through the shared temporal aggregation contract.

    Returns:
        (df_or_none, trace)
    """
    trace = {
        "source_id": source_id,
        "requested": {
            "time_granularity": item.get("time_granularity"),
            "aggregation": item.get("aggregation"),
            "date_start": item.get("date_start"),
            "date_end": item.get("date_end"),
            "year": item.get("year"),
            "year_start": item.get("year_start"),
            "year_end": item.get("year_end"),
        },
    }

    spec = build_aggregation_spec_func(item, metadata)
    trace["spec"] = spec.to_dict()

    has_temporal_override = bool(
        item.get("time_granularity")
        or item.get("aggregation")
        or item.get("date_start")
        or item.get("date_end")
        or source_id == "fx_usd_historical"
    )
    if not has_temporal_override:
        trace["applied"] = {"path": "all_countries.parquet", "mode": "native_yearly"}
        return None, trace

    requested_granularity = str(spec.time_granularity or "").strip().lower()
    runtime_source_id = source_id
    parquet_name = "data.parquet"
    if requested_granularity == "weekly":
        runtime_source_id = "fx_usd_historical_weekly"
    elif requested_granularity == "monthly":
        runtime_source_id = "fx_usd_historical_monthly"

    source_dir = get_source_path_func(runtime_source_id)
    published_path = source_dir / parquet_name
    if not published_path.exists():
        trace["applied"] = {
            "path": "all_countries.parquet",
            "mode": "fallback_no_published_temporal_source",
            "resolved_source_id": runtime_source_id,
        }
        return None, trace

    try:
        fx = select_columns_from_parquet_func(published_path, ["date", "loc_id", "local_per_usd"])
        if fx.empty:
            fx = pd.read_parquet(published_path, columns=["date", "loc_id", "local_per_usd"])
    except Exception as e:
        trace["applied"] = {
            "path": "all_countries.parquet",
            "mode": "fallback_read_error",
            "resolved_source_id": runtime_source_id,
            "error": str(e),
        }
        return None, trace

    start_ts, end_ts = extract_date_window_func(item)
    if start_ts is not None:
        fx = fx[pd.to_datetime(fx["date"], errors="coerce") >= start_ts]
    if end_ts is not None:
        fx = fx[pd.to_datetime(fx["date"], errors="coerce") <= end_ts]

    if fx.empty:
        trace["applied"] = {
            "path": str(published_path),
            "mode": "empty_after_filter",
            "resolved_source_id": runtime_source_id,
        }
        return pd.DataFrame(columns=["loc_id", "timestamp", "date", "time_granularity", "source", "local_per_usd"]), trace

    aggregated = apply_temporal_aggregation_func(
        fx,
        spec,
        date_col="date",
        value_col="local_per_usd",
        group_cols=("loc_id",),
    )

    if aggregated.empty:
        trace["applied"] = {
            "path": str(published_path),
            "mode": "empty_after_aggregation",
            "resolved_source_id": runtime_source_id,
        }
        return pd.DataFrame(columns=["loc_id", "timestamp", "date", "time_granularity", "source", "local_per_usd"]), trace

    timestamps = pd.to_datetime(aggregated["date"], errors="coerce", utc=True)
    aggregated = aggregated.loc[timestamps.notna()].copy()
    aggregated["timestamp"] = (timestamps.loc[timestamps.notna()].astype("int64") // 1_000_000).astype("int64")
    aggregated["time_granularity"] = requested_granularity or "daily"
    aggregated["source"] = source_id

    trace["applied"] = {
        "path": str(published_path),
        "mode": "published_temporal_aggregation",
        "resolved_source_id": runtime_source_id,
        "requested_granularity": spec.time_granularity,
        "requested_method": spec.method,
        "coerced_output": "native_temporal_runtime",
        "input_rows": int(len(fx)),
        "post_agg_rows": int(len(aggregated)),
        "temporal_rows": int(len(aggregated)),
    }
    return aggregated[["loc_id", "timestamp", "date", "time_granularity", "source", "local_per_usd"]], trace
