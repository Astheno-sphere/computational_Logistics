"""
Runtime-mode helpers.

Two clean modes, no local cache:
- local: reads data directly from DATA_ROOT on disk
- cloud: reads JSON metadata via boto3.get_object(), parquet via DuckDB httpfs
"""

from __future__ import annotations

from .runtime_config import get_runtime_config


def get_runtime_mode(configured_mode: str | None = None) -> str:
    if configured_mode:
        mode = str(configured_mode).strip().lower()
    else:
        mode = str(get_runtime_config().get("runtime_mode", "local")).strip().lower() or "local"
    if mode not in {"local", "cloud"}:
        raise RuntimeError(f"Unsupported RUNTIME_MODE: {mode}")
    return mode
