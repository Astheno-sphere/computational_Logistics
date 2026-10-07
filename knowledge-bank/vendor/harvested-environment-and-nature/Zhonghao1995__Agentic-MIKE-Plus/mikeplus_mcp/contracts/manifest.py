"""Provenance manifest for one modelling step/run (pure Python, no DHI imports).

A manifest ties together *what model*, *what inputs*, *what edits*, *what run
status*, *what results/figures* — each file with a sha256 — so a run can be
audited or re-compared later. Deterministic apart from ``created_utc``.
"""
from __future__ import annotations

import hashlib
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "agentic-mike/manifest/1"

# keys copied from a mike_run result (the QA gate + where the outputs went)
_RUN_KEYS = ("ok", "sqlite", "active_simulation", "result_files", "elapsed_s",
             "status", "completed", "errors", "warnings", "issues", "log_file")


def file_info(path) -> dict:
    """``{path, exists, bytes, sha256}`` for one file (sha256 = None if missing)."""
    p = Path(str(path))
    info = {"path": str(p), "exists": p.is_file(), "bytes": None, "sha256": None}
    if info["exists"]:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        info["bytes"] = p.stat().st_size
        info["sha256"] = h.hexdigest()
    return info


def build_manifest(*, case: str | None = None, model: str | None = None,
                   inputs=None, results=None, figures=None, run: dict | None = None,
                   edits=None, tool_calls=None, notes: str | None = None,
                   version: str | None = None) -> dict:
    run = run or {}
    return {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine": "mikeplus",
        "case": case,
        "model": file_info(model) if model else None,
        "inputs": [file_info(p) for p in (inputs or [])],
        "results": [file_info(p) for p in (results or [])],
        "figures": [file_info(p) for p in (figures or [])],
        "run": {k: run[k] for k in _RUN_KEYS if k in run},
        "edits": list(edits or []),
        "tool_calls": list(tool_calls or []),
        "notes": notes,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "mikeplus_mcp": version,
        },
    }


def missing_files(manifest: dict) -> list[str]:
    """Paths the manifest references that do not exist on disk."""
    out = []
    if manifest.get("model") and not manifest["model"]["exists"]:
        out.append(manifest["model"]["path"])
    for key in ("inputs", "results", "figures"):
        out.extend(f["path"] for f in manifest.get(key, []) if not f["exists"])
    return out
