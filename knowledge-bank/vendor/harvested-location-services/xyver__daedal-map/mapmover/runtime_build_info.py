"""Runtime build/deploy fingerprint helpers."""

from __future__ import annotations

import os


def runtime_build_info() -> dict[str, str]:
    commit = (
        str(
            os.getenv("RAILWAY_GIT_COMMIT_SHA")
            or os.getenv("SOURCE_VERSION")
            or os.getenv("GIT_COMMIT")
            or os.getenv("COMMIT_SHA")
            or ""
        )
        .strip()
    )
    branch = (
        str(
            os.getenv("RAILWAY_GIT_BRANCH")
            or os.getenv("GIT_BRANCH")
            or os.getenv("BRANCH")
            or ""
        )
        .strip()
    )
    deployment = str(os.getenv("DEPLOYMENT", "")).strip()
    runtime_mode = str(os.getenv("RUNTIME_MODE", "")).strip()
    install_mode = str(os.getenv("INSTALL_MODE", "")).strip()
    return {
        "commit": commit,
        "commit_short": commit[:7] if commit else "",
        "branch": branch,
        "deployment": deployment,
        "runtime_mode": runtime_mode,
        "install_mode": install_mode,
    }
