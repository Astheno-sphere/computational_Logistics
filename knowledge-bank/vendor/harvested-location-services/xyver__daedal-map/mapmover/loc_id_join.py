"""Shared loc_id join helpers for Explore and Research."""

from __future__ import annotations


def normalize_loc_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def unique_loc_ids_from_rows(rows: list[dict] | None) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        loc_id = normalize_loc_id(row.get("loc_id"))
        if not loc_id or loc_id in seen:
            continue
        seen.add(loc_id)
        resolved.append(loc_id)
    return resolved


def apply_loc_id_subset_filter(filters: dict | None, loc_ids: list[str] | None) -> dict:
    patched = dict(filters or {})
    patched["loc_id"] = {"in": list(loc_ids or [])}
    return patched
