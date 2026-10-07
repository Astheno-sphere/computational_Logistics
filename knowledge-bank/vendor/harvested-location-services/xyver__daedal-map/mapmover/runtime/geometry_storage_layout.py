"""Single path contract for the contained Published Geometry namespace."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any


def _country(value: str) -> str:
    country = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", country):
        raise ValueError(f"Invalid country code: {value!r}")
    return country


def country_release_id(profile: dict[str, Any]) -> str:
    release_id = str(profile.get("release_id") or (profile.get("active_release") or {}).get("release_id") or "").strip()
    if not re.fullmatch(r"[a-z0-9_]+", release_id):
        raise ValueError("Country profile has no safe active release_id")
    return release_id


def catalog_artifact_path(data_root: Path, record: Any) -> Path | None:
    """Resolve one catalog artifact record beneath the shared data root."""
    relative = str(record.get("path") or "").strip() if isinstance(record, dict) else ""
    normalized = PurePosixPath(relative.replace("\\", "/"))
    if (
        not relative
        or normalized.is_absolute()
        or any(part in {"", ".", ".."} for part in normalized.parts)
        or not normalized.parts
        or normalized.parts[0] != "geometry"
    ):
        return None
    return data_root.joinpath(*normalized.parts)


def country_admin_spine_root(data_root: Path, country: str, profile: dict[str, Any]) -> Path:
    code = _country(country)
    return data_root / "geometry" / "countries" / code / "admin_spine" / "exact" / country_release_id(profile)


def country_reference_root(data_root: Path, country: str, profile: dict[str, Any]) -> Path:
    code = _country(country)
    return data_root / "geometry" / "countries" / code / "reference" / country_release_id(profile)


def country_crosswalk_artifact_path(
    data_root: Path, relative: str, *, cloud_mode: bool,
) -> Path | None:
    """Resolve a release-owned crosswalk with its local authoring-tree fallback."""
    clean = catalog_artifact_path(data_root, {"path": relative})
    if clean is None or cloud_mode or clean.is_file():
        return clean
    parts = PurePosixPath(str(relative).replace("\\", "/")).parts
    if (
        len(parts) >= 7
        and parts[:2] == ("geometry", "countries")
        and re.fullmatch(r"[A-Z]{3}", parts[2])
        and parts[3] == "crosswalks"
        and re.fullmatch(r"[a-z0-9_]+", parts[4])
    ):
        authoring = data_root.joinpath(*parts[:4], *parts[5:])
        if authoring.is_file():
            return authoring
    return clean


def country_catalog_relative(country: str) -> str:
    return f"geometry/countries/{_country(country)}/reference/catalog.json"


def country_release_manifest_relative(country: str, profile: dict[str, Any]) -> str:
    code = _country(country)
    version = str(profile.get("release_version") or "").strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}", version):
        raise ValueError("Country profile has no safe release_version")
    return f"geometry/countries/{code}/releases/{version}/manifest.json"


def released_artifact_paths_by_hash(manifest: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Return the clean published paths declared by one contained release."""
    paths: dict[str, tuple[str, ...]] = {}
    for item in manifest.get("objects") or []:
        if not isinstance(item, dict):
            continue
        digest = str(item.get("sha256") or "").strip().lower()
        declared = tuple(
            str(path).replace("\\", "/")
            for path in item.get("source_paths") or []
            if str(path).startswith("geometry/")
        )
        if re.fullmatch(r"[0-9a-f]{64}", digest) and declared:
            paths[digest] = declared
    return paths


def released_artifact_path(
    source_path: str,
    sha256: str,
    paths_by_hash: dict[str, tuple[str, ...]],
) -> str:
    """Resolve an embedded source path through the release's hash authority.

    Reference-graph indexes deliberately pin payload hashes.  The contained
    namespace release manifest maps those same hashes to their current object
    paths, so readers do not need hard-coded migration rules or path aliases.
    """
    original = str(source_path or "").replace("\\", "/")
    candidates = paths_by_hash.get(str(sha256 or "").strip().lower()) or ()
    if not candidates:
        raise ValueError(f"Released artifact hash is absent from the active manifest: {sha256}")
    # A release manifest may intentionally retain both its release-owned path
    # and a byte-identical stable runtime projection.  When the graph index
    # already names one of those declared paths, that exact path is the
    # unambiguous authority; basename matching is only a migration fallback.
    if original in candidates:
        return original
    if len(candidates) == 1:
        return candidates[0]
    basename = original.rsplit("/", 1)[-1]
    same_name = [path for path in candidates if path.rsplit("/", 1)[-1] == basename]
    if len(same_name) == 1:
        return same_name[0]
    raise ValueError(f"Released artifact hash has ambiguous active paths: {sha256}")


def global_admin0_point_relative() -> str:
    return "geometry/global/runtime/admin_0_point.parquet"


def global_admin0_exact_relative() -> str:
    return "geometry/global/exact/admin_0.parquet"


def global_admin0_display_relative() -> str:
    return "geometry/global/display/admin_0.parquet"


def _global_admin0_path(
    geometry_root: Path, relative: str, legacy_local: str, *, cloud_mode: bool,
) -> Path:
    """Resolve a clean Published path with an explicit local-authoring fallback."""
    clean = geometry_root.joinpath(*PurePosixPath(relative).parts[1:])
    if cloud_mode or clean.is_file():
        return clean
    legacy = geometry_root.joinpath(*PurePosixPath(legacy_local).parts[1:])
    return legacy if legacy.is_file() else clean


def global_admin0_exact_path(data_root: Path, *, cloud_mode: bool) -> Path:
    return _global_admin0_path(
        data_root / "geometry", global_admin0_exact_relative(), "geometry/admin0/full.parquet",
        cloud_mode=cloud_mode,
    )


def global_admin0_display_path(data_root: Path, *, cloud_mode: bool) -> Path:
    return _global_admin0_path(
        data_root / "geometry", global_admin0_display_relative(), "geometry/admin0/display.parquet",
        cloud_mode=cloud_mode,
    )


def global_admin0_exact_path_from_geometry_root(
    geometry_root: Path, *, cloud_mode: bool,
) -> Path:
    return _global_admin0_path(
        geometry_root, global_admin0_exact_relative(), "geometry/admin0/full.parquet",
        cloud_mode=cloud_mode,
    )


def global_admin0_display_path_from_geometry_root(
    geometry_root: Path, *, cloud_mode: bool,
) -> Path:
    return _global_admin0_path(
        geometry_root, global_admin0_display_relative(), "geometry/admin0/display.parquet",
        cloud_mode=cloud_mode,
    )


def global_admin0_point_path(data_root: Path, record: Any, *, cloud_mode: bool) -> Path | None:
    """Resolve the published bank, retaining only the local source-tree path."""
    clean = catalog_artifact_path(data_root, record)
    if clean is None or cloud_mode or clean.is_file():
        return clean
    source = data_root / "geometry/runtime/global_admin0_point/point_bank.parquet"
    return source if source.is_file() else clean
