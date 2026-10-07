from __future__ import annotations

from pathlib import Path
from typing import Any

from ..foundation_helpers import load_country_crosswalk
from ..paths import COUNTRY_GEOMETRY_DIR


def load_country_geometry_profile(iso3: str) -> dict[str, Any]:
    """Return the country crosswalk/profile payload for runtime-owned helpers."""
    payload = load_country_crosswalk(str(iso3 or "").strip().upper())
    return payload if isinstance(payload, dict) else {}


def get_country_sub_admin_levels(iso3: str) -> dict[str, dict[str, Any]]:
    """Return declared canonical deep admin levels for a country."""
    levels = load_country_geometry_profile(iso3).get("sub_admin_levels") or {}
    if not isinstance(levels, dict):
        return {}
    spine_levels: dict[str, dict[str, Any]] = {}
    for key, info in levels.items():
        if not isinstance(info, dict):
            continue
        spine_role = str(info.get("spine_role") or "strict_nested").strip().lower()
        if spine_role in {"strict_nested", "admin_spine", "spine"}:
            spine_levels[str(key)] = info
    return spine_levels


def get_country_level_config(iso3: str, admin_level: int | str) -> dict[str, Any] | None:
    """Return one canonical sub-admin level block from the country geometry profile."""
    key = admin_level if isinstance(admin_level, str) and admin_level.startswith("admin_") else f"admin_{admin_level}"
    config = get_country_sub_admin_levels(iso3).get(key)
    return config if isinstance(config, dict) else None


def get_country_supported_deep_admin_levels(iso3: str) -> list[int]:
    """Return declared canonical deep admin levels (3+) for a country."""
    levels: list[int] = []
    for key in get_country_sub_admin_levels(iso3).keys():
        if not isinstance(key, str) or not key.startswith("admin_"):
            continue
        try:
            level_value = int(key.split("_", 1)[1])
        except (TypeError, ValueError):
            continue
        if level_value >= 3:
            levels.append(level_value)
    return sorted(set(levels))


def get_country_overlap_levels(iso3: str) -> dict[str, dict[str, Any]]:
    """Return overlap-only local admin naming hints from the country profile."""
    levels = load_country_geometry_profile(iso3).get("overlap_levels") or {}
    return levels if isinstance(levels, dict) else {}


def get_country_regional_overlap_systems(iso3: str) -> dict[str, dict[str, Any]]:
    """Return regional overlap naming systems (for example NUTS) from the profile."""
    systems = load_country_geometry_profile(iso3).get("regional_overlap_systems") or {}
    return systems if isinstance(systems, dict) else {}


def get_country_location_aliases(iso3: str) -> dict[str, str]:
    """Return direct country-owned location aliases that map names to loc_ids."""
    aliases = load_country_geometry_profile(iso3).get("location_aliases") or {}
    return aliases if isinstance(aliases, dict) else {}


def _country_level_geometry_exists(iso3: str, info: dict[str, Any]) -> bool:
    folder = info.get("folder")
    if not folder:
        return False

    countries_dir = Path(COUNTRY_GEOMETRY_DIR)
    direct_path = countries_dir / iso3 / f"{folder}.parquet"
    partition_dir = countries_dir / iso3 / folder
    return direct_path.exists() or partition_dir.exists()


def build_country_geometry_alias_context_lines(iso3: str) -> list[str]:
    """Format country-owned geometry alias guidance for prompt/context surfaces."""
    iso3_value = str(iso3 or "").strip().upper()
    if not iso3_value:
        return []

    overlap_blocks = []
    for level_key, info in get_country_overlap_levels(iso3_value).items():
        aliases = info.get("aliases") or []
        if aliases:
            overlap_blocks.append(
                f"{level_key}: canonical={info.get('canonical_dataset_label', info.get('display_name', 'unknown'))}; "
                f"aliases={', '.join(aliases[:8])}; status={info.get('runtime_status', 'unknown')}"
            )

    sub_admin_blocks = []
    for level_key, info in get_country_sub_admin_levels(iso3_value).items():
        if not _country_level_geometry_exists(iso3_value, info):
            continue
        aliases = info.get("aliases") or []
        if aliases:
            sub_admin_blocks.append(
                f"{level_key}: canonical={info.get('canonical_dataset_label', info.get('name', 'unknown'))}; "
                f"aliases={', '.join(aliases[:10])}"
            )

    regional_blocks = []
    for system_name, system_info in get_country_regional_overlap_systems(iso3_value).items():
        aliases_by_level = system_info.get("aliases") or {}
        if not isinstance(aliases_by_level, dict):
            continue
        for level_key, aliases in aliases_by_level.items():
            if aliases:
                regional_blocks.append(f"{system_name}.{level_key}: {', '.join(aliases[:8])}")

    lines: list[str] = []
    if regional_blocks:
        lines.append("Regional overlap aliases:")
        lines.extend(f"  - {line}" for line in regional_blocks)
    if overlap_blocks:
        lines.append("Recognized overlap-only local names:")
        lines.extend(f"  - {line}" for line in overlap_blocks)
    if sub_admin_blocks:
        lines.append("Adopted country-specific deeper aliases:")
        lines.extend(f"  - {line}" for line in sub_admin_blocks)
    return lines
