"""Shared sparse-year clarify helpers."""

from __future__ import annotations


def check_sparse_year(
    df,
    metric_col: str,
    selected_year: int,
    metadata: dict | None,
) -> dict | None:
    """Return a clarify result when the auto-selected year has sparse coverage."""
    metrics = (metadata or {}).get("metrics", {})
    metric_info = metrics.get(metric_col) if isinstance(metrics, dict) else None
    if not isinstance(metric_info, dict):
        return None

    density = float(metric_info.get("density") or 0)
    countries = int(metric_info.get("countries") or 0)
    expected_per_year = density * countries

    if expected_per_year < 5:
        return None

    actual_count = int((df[metric_col].notna() & (df["year"] == selected_year)).sum())
    if actual_count >= expected_per_year * 0.25:
        return None

    year_counts = (
        df[df[metric_col].notna()]
        .groupby("year")[metric_col]
        .count()
        .sort_index()
    )
    if year_counts.empty:
        return None

    best_count = int(year_counts.max())
    good_years = year_counts[year_counts >= max(int(best_count * 0.5), int(expected_per_year * 0.25))]
    if good_years.empty:
        return None

    suggested_year = int(good_years.index.max())
    suggested_count = int(year_counts[suggested_year])
    if suggested_year == selected_year:
        return None

    metric_name = metric_info.get("name") or metric_col
    noun = "country" if actual_count == 1 else "countries"
    msg = (
        f"{selected_year} only has data for {actual_count} {noun} "
        f"for \"{metric_name}\". "
        f"{suggested_year} has much better coverage ({suggested_count} countries). "
        f"Would you like to use {suggested_year} instead, or specify a different year?"
    )
    return {
        "type": "clarify",
        "message": msg,
        "geojson": {"type": "FeatureCollection", "features": []},
        "count": 0,
    }
