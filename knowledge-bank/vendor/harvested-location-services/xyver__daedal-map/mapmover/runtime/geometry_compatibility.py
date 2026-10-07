"""Versioned compatibility reads for released global admin geometry ids."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import pandas as pd

from ..duckdb_helpers import is_cloud_mode, parquet_columns, select_rows
from ..paths import GEOMETRY_DIR

COMPATIBILITY_RELEASE_ID = "geoboundaries_v2_to_exact_2026"
COMPATIBILITY_ROOT = GEOMETRY_DIR / "crosswalks" / COMPATIBILITY_RELEASE_ID
ALIASES_PATH = COMPATIBILITY_ROOT / "aliases.parquet"
LEGACY_AREAS_PATH = COMPATIBILITY_ROOT / "legacy_areas.parquet"


def _read_parquet(path: Path, *, columns: list[str] | None = None) -> pd.DataFrame:
    if path.exists():
        available = parquet_columns(path)
        selected = [column for column in (columns or available) if column in available]
        return pd.read_parquet(path, columns=selected or None)
    if not is_cloud_mode():
        return pd.DataFrame()
    try:
        return select_rows(path, columns=columns)
    except Exception:
        return pd.DataFrame()


@lru_cache(maxsize=1)
def compatibility_aliases() -> dict[str, str]:
    frame = _read_parquet(ALIASES_PATH, columns=["source_loc_id", "target_loc_id"])
    if frame.empty:
        return {}
    return {
        str(source).strip().upper(): str(target).strip().upper()
        for source, target in zip(frame["source_loc_id"], frame["target_loc_id"])
        if str(source).strip() and str(target).strip()
    }


@lru_cache(maxsize=1)
def retained_legacy_loc_ids() -> set[str]:
    frame = _read_parquet(LEGACY_AREAS_PATH, columns=["loc_id"])
    if frame.empty or "loc_id" not in frame:
        return set()
    return {
        str(value).strip().upper()
        for value in frame["loc_id"].dropna().astype(str)
        if str(value).strip()
    }


def compatibility_loc_ids() -> set[str]:
    return set(compatibility_aliases()) | retained_legacy_loc_ids()


def translate_compatibility_loc_id(loc_id: str) -> str:
    value = str(loc_id or "").strip().upper()
    return compatibility_aliases().get(value, value)


def requested_aliases(loc_ids: Iterable[str]) -> dict[str, str]:
    aliases = compatibility_aliases()
    return {
        value: aliases[value]
        for raw in loc_ids
        if (value := str(raw or "").strip().upper()) in aliases
    }


def load_legacy_geometry_rows(
    loc_ids: Iterable[str],
    *,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    requested = sorted({str(value or "").strip().upper() for value in loc_ids if str(value or "").strip()})
    if not requested:
        return pd.DataFrame()
    read_columns = columns
    if read_columns and "loc_id" not in read_columns:
        read_columns = ["loc_id", *read_columns]
    if LEGACY_AREAS_PATH.exists():
        available = parquet_columns(LEGACY_AREAS_PATH)
        selected = [column for column in (read_columns or available) if column in available]
        return pd.read_parquet(
            LEGACY_AREAS_PATH,
            columns=selected or None,
            filters=[("loc_id", "in", requested)],
        )
    if not is_cloud_mode():
        return pd.DataFrame()
    try:
        return select_rows(
            LEGACY_AREAS_PATH,
            columns=read_columns,
            in_filters={"loc_id": requested},
        )
    except Exception:
        return pd.DataFrame()


def load_current_alias_target_rows(
    target_loc_ids: Iterable[str],
    *,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Read alias targets from the global bank, bypassing national overrides."""
    requested = sorted({str(value or "").strip().upper() for value in target_loc_ids if str(value or "").strip()})
    if not requested:
        return pd.DataFrame()
    grouped: dict[str, list[str]] = {}
    for loc_id in requested:
        grouped.setdefault(loc_id.split("-", 1)[0], []).append(loc_id)
    frames: list[pd.DataFrame] = []
    for iso3, iso_ids in grouped.items():
        path = GEOMETRY_DIR / f"{iso3}.parquet"
        read_columns = columns
        if read_columns and "loc_id" not in read_columns:
            read_columns = ["loc_id", *read_columns]
        if path.exists():
            available = parquet_columns(path)
            selected = [column for column in (read_columns or available) if column in available]
            frame = pd.read_parquet(
                path,
                columns=selected or None,
                filters=[("loc_id", "in", iso_ids)],
            )
        elif is_cloud_mode():
            try:
                frame = select_rows(path, columns=read_columns, in_filters={"loc_id": iso_ids})
            except Exception:
                frame = pd.DataFrame()
        else:
            frame = pd.DataFrame()
        if frame is not None and not frame.empty:
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
