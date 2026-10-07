from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..duckdb_helpers import is_cloud_mode, parquet_columns
from ..foundation_helpers import load_country_crosswalk
from ..paths import COUNTRY_GEOMETRY_DIR, GEOMETRY_DIR
from .read_posture import prefer_local_geometry_reads
from ..runtime_config import force_remote_data_reads
from .published_artifacts import read_artifact_json


def parquet_accessible(path: Path | None) -> bool:
    """Return True when a parquet path exists locally or is cloud-readable."""
    if path is None:
        return False
    if path.exists() and not force_remote_data_reads():
        return True
    if prefer_local_geometry_reads():
        return False
    if not is_cloud_mode():
        return False
    try:
        cols = parquet_columns(path)
        return bool(cols)
    except Exception:
        return False


def _read_active_json(relative_path: str) -> dict[str, Any] | None:
    """Read one active-lane JSON control, preferring a coherent local tree."""
    local_path = GEOMETRY_DIR.parent / relative_path
    if local_path.exists() and not force_remote_data_reads():
        try:
            payload = json.loads(local_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError):
            return None
    if not prefer_local_geometry_reads() and is_cloud_mode():
        try:
            payload = read_artifact_json(relative_path, lane="active")
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None
    return None


@lru_cache(maxsize=256)
def resolve_country_display_release(iso3: str) -> dict[str, Any] | None:
    """Resolve Display banks from the one contained country release."""
    country = str(iso3 or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", country):
        return None
    index_path = f"geometry/countries/{country}/index.json"
    index = _read_active_json(index_path)
    index_unit = (index.get("release_unit") or {}) if isinstance(index, dict) else {}
    if not isinstance(index, dict) or str(index_unit.get("id") or "").upper() != country:
        return None
    current = index.get("current") or {}
    manifest_pin = current.get("manifest") or {}
    manifest_path = str(manifest_pin.get("path") or "").replace("\\", "/")
    if not re.fullmatch(rf"geometry/countries/{country}/releases/\d+\.\d+\.\d+/manifest\.json", manifest_path):
        return None
    manifest = _read_active_json(manifest_path)
    manifest_unit = (manifest.get("release_unit") or {}) if isinstance(manifest, dict) else {}
    if not isinstance(manifest, dict) or str(manifest_unit.get("id") or "").upper() != country:
        return None
    display_prefix = str((manifest.get("runtime") or {}).get("display") or "").replace("\\", "/")
    expected_prefix = f"geometry/countries/{country}/admin_spine/display/"
    if not display_prefix.startswith(expected_prefix) or not display_prefix.endswith("/"):
        return None
    release_id = display_prefix.rstrip("/").rsplit("/", 1)[-1]
    if not re.fullmatch(r"[a-z0-9_]+", release_id):
        return None

    artifacts: list[dict[str, Any]] = []
    for object_record in manifest.get("objects") or []:
        for value in object_record.get("source_paths") or []:
            relative = str(value).replace("\\", "/").strip("/")
            if not relative.startswith(display_prefix) or not relative.endswith(".parquet"):
                continue
            suffix = relative[len(display_prefix):]
            if suffix == "admin_0_3.parquet":
                levels, owner = [0, 1, 2, 3], "national"
            elif re.fullmatch(r"deep/[A-Z]{3}-.+\.parquet", suffix):
                levels, owner = [4, 5, 6], Path(suffix).stem
            else:
                continue
            artifacts.append({
                "role": "display_simplified_geometry",
                "sha256": object_record.get("sha256"),
                "size_bytes": object_record.get("size_bytes"),
                "path": GEOMETRY_DIR.parent / relative,
                "relative_path": relative,
                "admin_levels": levels,
                "physical_owner": owner,
            })
    if not artifacts:
        return None
    return {
        "country": country,
        "release_id": release_id,
        "pointer": index,
        "manifest": manifest,
        "artifacts": artifacts,
    }


def resolve_country_admin_spine_source(iso3: str) -> Path | None:
    """Use the catalog-owned exact layout selected by point resolution."""
    country = str(iso3 or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", country):
        return None
    # Keep name lookup on the same release selector already exercised by the
    # hosted point resolver.  Duplicating index/manifest interpretation here
    # allowed the two runtime paths to disagree in cloud mode.
    from .admin_spine_query import layout_root

    return layout_root(country) / "admin_0_3.parquet"


def resolve_country_display_geometry_sources(
    iso3: str,
    *,
    admin_level: int | None = None,
    physical_owner: str | None = None,
) -> list[Path]:
    """Return declared Display parquets relevant to a level/physical owner."""
    release = resolve_country_display_release(iso3)
    if not release:
        return []
    owner = str(physical_owner or "").strip()
    paths: list[Path] = []
    for artifact in release["artifacts"]:
        levels = artifact.get("admin_levels") or []
        if admin_level is not None and int(admin_level) not in levels:
            continue
        artifact_owner = str(artifact.get("physical_owner") or "").strip()
        if owner and artifact_owner not in {"national", owner}:
            continue
        # The admitted manifest is the availability contract. Avoid a separate
        # object-store metadata probe before every visual query; the actual
        # projected read remains the definitive health check.
        paths.append(artifact["path"])
    return paths


def resolve_country_display_geometry_source(iso3: str) -> Path | None:
    """Compatibility helper returning the active Admin0--3 Display bank."""
    paths = resolve_country_display_geometry_sources(iso3, admin_level=2)
    return paths[0] if paths else None


def resolve_country_geometry_source(iso3: str, *, admin_level: int | None = None) -> dict[str, Any]:
    """
    Resolve the canonical geometry-loading source for a country request.

    Returned dict keys:
    - `parquet_file`: selected parquet path or None
    - `crosswalk`: loaded crosswalk dict or None
    - `uses_crosswalk`: whether runtime loc_ids must bridge to geometry ids
    - `source_kind`: `authority_spine`, `country_base`, `crosswalk_base`,
      `global_base`, or `missing`
    """
    iso3 = str(iso3 or "").strip().upper()
    if not iso3:
        return {
            "parquet_file": None,
            "crosswalk": None,
            "uses_crosswalk": False,
            "source_kind": "missing",
        }

    country_root = COUNTRY_GEOMETRY_DIR / iso3
    catalog_spine_file = (
        resolve_country_admin_spine_source(iso3)
        if admin_level is None or 0 <= admin_level <= 3
        else None
    )
    authority_spine_file = (
        catalog_spine_file
        if catalog_spine_file is not None
        else country_root / "admin_spine" / "admin_0_3.parquet"
    )
    country_geom_file = country_root / "geometry.parquet"
    global_geom_file = GEOMETRY_DIR / f"{iso3}.parquet"
    crosswalk = load_country_crosswalk(iso3)

    # The released country admin spine is the authority for Admin0-3.  This
    # convention is shared by AUS, CAN, USA, and future country programs; do
    # not add country-specific county or state banks ahead of it.
    if (admin_level is None or 0 <= admin_level <= 3) and parquet_accessible(authority_spine_file):
        return {
            "parquet_file": authority_spine_file,
            "crosswalk": None,
            "uses_crosswalk": False,
            "source_kind": "authority_spine",
        }

    if parquet_accessible(country_geom_file):
        return {
            "parquet_file": country_geom_file,
            "crosswalk": None,
            "uses_crosswalk": False,
            "source_kind": "country_base",
        }

    if crosswalk and parquet_accessible(global_geom_file):
        return {
            "parquet_file": global_geom_file,
            "crosswalk": crosswalk,
            "uses_crosswalk": True,
            "source_kind": "crosswalk_base",
        }

    if parquet_accessible(global_geom_file):
        return {
            "parquet_file": global_geom_file,
            "crosswalk": None,
            "uses_crosswalk": False,
            "source_kind": "global_base",
        }

    return {
        "parquet_file": None,
        "crosswalk": crosswalk if isinstance(crosswalk, dict) else None,
        "uses_crosswalk": False,
        "source_kind": "missing",
    }
