"""Shared request-shaping rules for interactive point resolution."""

from __future__ import annotations

from typing import Any


GLOBAL_BULK_PRESETS = {
    "global_admin_0": 0,
    "global_admin_1": 1,
}
POINT_LOOKUP_MODES = {"standard", "deep"}


def apply_point_lookup_mode(
    value: Any,
    *,
    country_scope: str | None,
    target_admin_level: int | None,
    admin_1_scope: str | None = None,
    bulk_preset: str | None = None,
) -> tuple[str, int | None, int | None, dict[str, Any] | None]:
    """Return mode, exact target, I/O ceiling, and an optional error.

    Standard resolution may fan out by discovered country but never opens a
    country's Admin1-owned deep partitions. Deep resolution can open those
    partitions only when one country and one Admin1 owner are declared up front.
    """
    mode = str(value or "standard").strip().lower()
    if mode not in POINT_LOOKUP_MODES:
        return mode, target_admin_level, None, {
            "code": "invalid_lookup_mode",
            "message": "lookup_mode must be standard or deep.",
            "supported_values": sorted(POINT_LOOKUP_MODES),
        }
    if mode == "standard":
        if target_admin_level is not None and target_admin_level > 3:
            return mode, target_admin_level, 3, {
                "code": "deep_mode_required",
                "message": (
                    "Standard point resolution stops at Admin 3 and never opens deep "
                    "partitions. Use lookup_mode='deep' with exactly one country_scope "
                    "and one admin_1_scope."
                ),
            }
        return mode, target_admin_level, 3, None
    if bulk_preset:
        return mode, target_admin_level, None, {
            "code": "deep_mode_preset_conflict",
            "message": "Deep point resolution cannot use a cross-country bulk_preset.",
        }
    if not country_scope:
        return mode, target_admin_level, None, {
            "code": "deep_country_scope_required",
            "message": (
                "Deep point resolution accepts exactly one country per call. "
                "Provide one ISO3 country_scope and split multi-country input."
            ),
        }
    if target_admin_level is not None and target_admin_level <= 3:
        return mode, target_admin_level, None, {
            "code": "standard_mode_sufficient",
            "message": "Admin 0-3 requests belong in standard lookup mode.",
        }
    if not admin_1_scope:
        return mode, target_admin_level, None, {
            "code": "deep_admin_1_scope_required",
            "message": (
                "Admin 4+ point resolution accepts one Admin 1 owner per call. "
                "Provide admin_1_scope using the Admin 1 loc_id returned by a "
                "standard lookup, and split points by that value."
            ),
        }
    normalized_admin_1 = str(admin_1_scope).strip()
    if not normalized_admin_1.startswith(f"{str(country_scope).strip().upper()}-"):
        return mode, target_admin_level, None, {
            "code": "deep_scope_mismatch",
            "message": "admin_1_scope must belong to country_scope.",
            "country_scope": str(country_scope).strip().upper(),
            "admin_1_scope": normalized_admin_1,
        }
    return mode, target_admin_level, None, None


def apply_global_bulk_preset(
    value: Any,
    *,
    country_scope: str | None,
    target_admin_level: int | None,
) -> tuple[str | None, str | None, int | None, dict[str, Any] | None]:
    """Validate a cross-country preset and apply its bounded admin level."""
    preset = str(value or "").strip().lower() or None
    if preset is None:
        return None, country_scope, target_admin_level, None
    if preset not in GLOBAL_BULK_PRESETS:
        return preset, country_scope, target_admin_level, {
            "code": "invalid_bulk_preset",
            "message": "bulk_preset must be global_admin_0 or global_admin_1.",
            "supported_values": list(GLOBAL_BULK_PRESETS),
        }
    preset_level = GLOBAL_BULK_PRESETS[preset]
    conflicts = []
    if country_scope:
        conflicts.append("country_scope")
    if target_admin_level is not None and target_admin_level != preset_level:
        conflicts.append("target_admin_level")
    if conflicts:
        return preset, country_scope, target_admin_level, {
            "code": "bulk_preset_conflict",
            "message": (
                "A global bulk preset replaces country_scope and fixes the target admin "
                "level; remove the conflicting fields."
            ),
            "conflicting_fields": conflicts,
        }
    return preset, None, preset_level, None


def point_bulk_shape_error(
    *,
    point_count: int,
    country_scope: str | None,
    target_admin_level: int | None,
    bulk_preset: str | None,
    lookup_mode: str = "standard",
    threshold: int,
) -> dict[str, Any] | None:
    """Require either one country/level bank or an authored global preset."""
    if point_count <= threshold or bulk_preset in GLOBAL_BULK_PRESETS or lookup_mode == "standard":
        return None
    missing = []
    if not country_scope:
        missing.append("country_scope")
    if target_admin_level is None:
        missing.append("target_admin_level")
    if not missing:
        return None
    return {
        "code": "bulk_scope_required",
        "message": (
            f"Point batches above {threshold} must declare one country_scope and one "
            "target_admin_level, or use bulk_preset global_admin_0/global_admin_1. "
            "Split other multi-country inputs into separate calls."
        ),
        "missing_fields": missing,
        "supported_cross_country_presets": list(GLOBAL_BULK_PRESETS),
    }
