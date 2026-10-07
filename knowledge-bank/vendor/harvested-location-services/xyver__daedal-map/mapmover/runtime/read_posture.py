"""Shared read-posture helpers for local verification vs runtime-like reads."""

from __future__ import annotations

import os


def deployment_name() -> str:
    return str(os.environ.get("DEPLOYMENT", "")).strip().lower()


def storage_mode_name() -> str:
    return str(os.environ.get("STORAGE_MODE", "")).strip().lower()


def geometry_read_mode() -> str:
    """Return the explicit geometry/helper read posture for this process.

    Default rule:
    - DEPLOYMENT=local + STORAGE_MODE=local -> local verification mode
    - everything else -> runtime mode

    Optional override:
    - DAEDALMAP_GEOMETRY_READ_MODE=local|runtime
    """
    override = str(os.environ.get("DAEDALMAP_GEOMETRY_READ_MODE", "")).strip().lower()
    if override in {"local", "runtime"}:
        return override

    from ..runtime_config import get_data_plane_mode

    if get_data_plane_mode() == "cloud":
        return "runtime"

    if deployment_name() == "local" and storage_mode_name() == "local":
        return "local"
    return "runtime"


def prefer_local_geometry_reads() -> bool:
    return geometry_read_mode() == "local"
