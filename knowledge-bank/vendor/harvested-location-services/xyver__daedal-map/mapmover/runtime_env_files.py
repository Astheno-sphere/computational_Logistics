from __future__ import annotations

import os
from pathlib import Path


def runtime_env_file_candidates(workspace_root: Path) -> list[Path]:
    """Return env files the public runtime may load automatically.

    The public repo should load only its own `.env` plus an optional workspace
    root `.env`. Extra files, including a private-repo `.env`, must be opted
    into explicitly through `COUNTY_MAP_EXTRA_ENV_FILES`.
    """
    workspace_root = Path(workspace_root)
    candidates = [
        workspace_root / "county-map" / ".env",
        workspace_root / ".env",
    ]

    raw_extra = str(os.getenv("COUNTY_MAP_EXTRA_ENV_FILES", "")).strip()
    if raw_extra:
        for item in raw_extra.split(os.pathsep):
            candidate = str(item or "").strip()
            if candidate:
                candidates.append(Path(candidate))

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped
