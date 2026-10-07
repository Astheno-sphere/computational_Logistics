"""Shared execution-time normalization helpers."""

from __future__ import annotations

from typing import Optional

import pandas as pd


def coerce_year(value) -> Optional[int]:
    """Best-effort year coercion for LLM-generated order fields."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
        return None


def coerce_date_year(value) -> Optional[int]:
    """Best-effort extraction of a calendar year from ISO-ish date fields."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return coerce_year(value)
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def normalize_year_filters(item: dict) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Normalize year/year_start/year_end in-place and bridge ISO date bounds to years."""
    year = coerce_year(item.get("year"))
    year_start = coerce_year(item.get("year_start"))
    year_end = coerce_year(item.get("year_end"))
    date_start_year = coerce_date_year(item.get("date_start"))
    date_end_year = coerce_date_year(item.get("date_end"))

    if year_start is None and date_start_year is not None:
        year_start = date_start_year
    if year_end is None and date_end_year is not None:
        year_end = date_end_year
    if year is None and year_start is not None and year_end is not None and year_start == year_end:
        year = year_start

    if year is not None:
        item["year"] = year
    if year_start is not None:
        item["year_start"] = year_start
    if year_end is not None:
        item["year_end"] = year_end

    return year, year_start, year_end


def normalize_geo_level(value) -> Optional[str]:
    """Normalize generic requested geo_level values from the order."""
    if not value:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"country", "admin_0"}:
        return "admin_0"
    friendly_levels = {
        "state": "admin_1",
        "states": "admin_1",
        "province": "admin_1",
        "provinces": "admin_1",
        "county": "admin_2",
        "counties": "admin_2",
        "tract": "admin_3",
        "tracts": "admin_3",
        "blockgroup": "admin_4",
        "blockgroups": "admin_4",
        "block_group": "admin_4",
        "block_groups": "admin_4",
        "block": "admin_5",
        "blocks": "admin_5",
    }
    if text in friendly_levels:
        return friendly_levels[text]
    if text.startswith("admin_") and text[6:].isdigit():
        return text
    return None


def extract_date_window(
    item: dict,
    *,
    normalize_year_filters_func=normalize_year_filters,
) -> tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """Infer a date window from order item fields."""
    date_start = pd.to_datetime(item.get("date_start"), errors="coerce")
    date_end = pd.to_datetime(item.get("date_end"), errors="coerce")

    year, year_start, year_end = normalize_year_filters_func(item)

    if pd.isna(date_start) and year_start:
        date_start = pd.Timestamp(year_start, 1, 1)
    if pd.isna(date_end) and year_end:
        date_end = pd.Timestamp(year_end, 12, 31)
    if pd.isna(date_start) and year:
        date_start = pd.Timestamp(year, 1, 1)
    if pd.isna(date_end) and year:
        date_end = pd.Timestamp(year, 12, 31)

    return (None if pd.isna(date_start) else date_start, None if pd.isna(date_end) else date_end)
