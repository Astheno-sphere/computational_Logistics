"""
Runtime-local pack installation helpers.

This module handles the runtime-owned install/remove lifecycle.
It does not talk to the private registry yet; instead, it supports
bootstrapping installable packs from an existing local full data tree.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .artifact_utils import sha256_file
from .pack_state import (
    MANAGED_DATA_ROOT_MARKER,
    _normalize_pack_ids,
    load_pack_state,
    materialize_active_data_root,
    save_pack_state,
)
from .pack_downloader import stage_pack_artifact
from .paths import DATA_ROOT, PACKS_ROOT, ensure_dir


logger = logging.getLogger("mapmover")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def _ensure_pack_exists(pack_id: str, full_catalog: dict) -> list[dict]:
    sources = [
        dict(src)
        for src in full_catalog.get("sources", [])
        if src.get("pack_id") == pack_id
    ]
    if not sources:
        raise RuntimeError(f"Pack not found in catalog: {pack_id}")
    return sources


def _load_catalog_from_root(data_root: Path) -> dict:
    catalog_path = data_root / "catalog.json"
    if not catalog_path.exists():
        return {"sources": [], "total_sources": 0}
    data = _load_json(catalog_path)
    return data or {"sources": [], "total_sources": 0}


def _copy_source_into_pack(source_root: Path, dest_root: Path) -> None:
    if source_root.is_dir():
        shutil.copytree(source_root, dest_root, dirs_exist_ok=True)
        return
    ensure_dir(dest_root.parent)
    shutil.copy2(source_root, dest_root)


def _build_manifest(pack_id: str, pack_version: str, data_root: Path, catalog_fragment: dict) -> tuple[dict, str]:
    files = []
    for file_path in sorted(data_root.rglob("*")):
        if not file_path.is_file():
            continue
        files.append({
            "path": str(file_path.relative_to(data_root)).replace("\\", "/"),
            "size": file_path.stat().st_size,
            "sha256": sha256_file(file_path),
        })

    manifest = {
        "version": 1,
        "pack_id": pack_id,
        "pack_version": pack_version,
        "generated_at": _now_iso(),
        "source_ids": _normalize_pack_ids(
            src.get("source_id")
            for src in catalog_fragment.get("sources", [])
            if src.get("source_id")
        ),
        "file_count": len(files),
        "files": files,
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    manifest["manifest_hash"] = manifest_hash
    return manifest, manifest_hash


def _install_pack_record(
    pack_id: str,
    pack_version: str,
    data_root: Path,
    catalog_fragment: dict,
    full_catalog: dict,
    manifest_path: Path,
    manifest_hash: str,
    *,
    activate: bool,
) -> tuple[dict, dict | None]:
    state = load_pack_state()
    install_root = data_root.parent
    installed_packs = [entry for entry in state.get("installed_packs", []) if entry.get("pack_id") != pack_id]
    installed_packs.append(
        {
            "pack_id": pack_id,
            "version": pack_version,
            "install_root": str(install_root),
            "data_root": str(data_root),
            "catalog_path": str(data_root / "catalog.json"),
            "manifest_path": str(manifest_path),
            "manifest_hash": manifest_hash,
            "source_ids": [src.get("source_id") for src in catalog_fragment.get("sources", []) if src.get("source_id")],
            "installed_at": _now_iso(),
            "status": "installed",
        }
    )
    state["installed_packs"] = installed_packs
    if activate and pack_id not in state.get("active_pack_ids", []):
        state["active_pack_ids"] = _normalize_pack_ids([*state.get("active_pack_ids", []), pack_id])
        state["catalog_mode"] = "managed_packs"
    saved_state = save_pack_state(state)

    materialization = None
    if activate or saved_state.get("catalog_mode") == "managed_packs":
        materialization = materialize_active_data_root(full_catalog, saved_state)
    return saved_state, materialization


def install_pack_from_local_catalog(
    pack_id: str,
    full_catalog: dict,
    *,
    source_data_root: str | Path | None = None,
    activate: bool = False,
    replace_existing: bool = True,
) -> dict:
    """
    Bootstrap an installed pack from the current local full data tree.

    This is meant for the open-engine/self-host path while the real downloader
    is still being built. It assumes `DATA_ROOT` currently points at a full
    source tree, not an already-assembled managed data root.
    """
    source_root_base = Path(source_data_root) if source_data_root else DATA_ROOT
    catalog_for_install = full_catalog or {"sources": [], "total_sources": 0}
    if not any(src.get("pack_id") == pack_id for src in catalog_for_install.get("sources", [])):
        catalog_for_install = _load_catalog_from_root(source_root_base)

    if source_root_base.resolve() == DATA_ROOT.resolve() and MANAGED_DATA_ROOT_MARKER.exists():
        raise RuntimeError(
            "Local pack bootstrap requires an unmanaged full data tree; "
            f"DATA_ROOT currently looks like a managed runtime root: {DATA_ROOT}"
        )
    pack_sources = _ensure_pack_exists(pack_id, catalog_for_install)
    install_root = PACKS_ROOT / pack_id
    data_root = install_root / "data"
    manifest_path = install_root / "manifest.json"
    catalog_path = data_root / "catalog.json"

    if install_root.exists():
        if not replace_existing:
            raise RuntimeError(f"Pack is already installed: {pack_id}")
        shutil.rmtree(install_root)

    ensure_dir(data_root)

    copied_paths = []
    for source in pack_sources:
        rel_path = str(source.get("path") or "").strip()
        if not rel_path:
            continue
        source_root = source_root_base / rel_path
        if not source_root.exists():
            raise RuntimeError(f"Source path missing for {pack_id}: {source_root}")
        dest_root = data_root / rel_path
        _copy_source_into_pack(source_root, dest_root)
        copied_paths.append(rel_path)

    catalog_fragment = {
        "catalog_version": catalog_for_install.get("catalog_version"),
        "last_updated": catalog_for_install.get("last_updated"),
        "sources": pack_sources,
        "total_sources": len(pack_sources),
        "overlay_tree": catalog_for_install.get("overlay_tree", {}),
    }
    with catalog_path.open("w", encoding="utf-8") as fh:
        json.dump(catalog_fragment, fh, indent=2)

    with (data_root / "index.json").open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "version": 1,
                "pack_id": pack_id,
                "pack_version": "local-dev",
                "generated_at": _now_iso(),
                "source_count": len(pack_sources),
            },
            fh,
            indent=2,
        )

    manifest, manifest_hash = _build_manifest(pack_id, "local-dev", data_root, catalog_fragment)
    ensure_dir(manifest_path.parent)
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    saved_state, materialization = _install_pack_record(
        pack_id,
        "local-dev",
        data_root,
        catalog_fragment,
        catalog_for_install,
        manifest_path,
        manifest_hash,
        activate=activate,
    )

    return {
        "pack_id": pack_id,
        "installed": True,
        "source_data_root": str(source_root_base),
        "install_root": str(install_root),
        "data_root": str(data_root),
        "catalog_path": str(catalog_path),
        "manifest_path": str(manifest_path),
        "copied_paths": copied_paths,
        "source_count": len(pack_sources),
        "state": saved_state,
        "materialization": materialization,
    }


def install_pack_from_manifest(
    manifest_path: str | Path,
    *,
    activate: bool = False,
    replace_existing: bool = True,
) -> dict:
    """
    Install a pack from a staged manifest/data directory.

    Expected artifact shape:
    - <stage>/manifest.json
    - <stage>/data/...
    """
    manifest_path = Path(manifest_path)
    if manifest_path.is_dir():
        manifest_path = manifest_path / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Manifest not found: {manifest_path}")

    manifest = _load_json(manifest_path)
    pack_id = str(manifest.get("pack_id") or "").strip()
    pack_version = str(manifest.get("pack_version") or manifest.get("version") or "").strip() or "unknown"
    if not pack_id:
        raise RuntimeError(f"Manifest missing pack_id: {manifest_path}")

    stage_root = manifest_path.parent
    stage_data_root = stage_root / "data"
    if not stage_data_root.exists():
        raise RuntimeError(f"Manifest stage missing data/ directory: {stage_data_root}")

    stage_catalog_path = stage_data_root / "catalog.json"
    if not stage_catalog_path.exists():
        raise RuntimeError(f"Manifest stage missing data/catalog.json: {stage_catalog_path}")
    catalog_fragment = _load_catalog_from_root(stage_data_root)

    unverified_count = 0
    for file_info in manifest.get("files", []):
        rel_path = str(file_info.get("path") or "").strip()
        if not rel_path:
            continue
        source_file = stage_data_root.joinpath(*rel_path.split("/"))
        if not source_file.exists():
            raise RuntimeError(f"Manifest file missing from stage: {source_file}")
        expected_hash = str(file_info.get("sha256") or "").strip().lower()
        if not expected_hash:
            unverified_count += 1
        elif sha256_file(source_file).lower() != expected_hash:
            raise RuntimeError(f"Manifest hash mismatch for {source_file}")

    if unverified_count:
        logger.warning(
            "SECURITY WARNING: pack %s manifest has %d file entries with no sha256; "
            "these files were NOT verified during install",
            pack_id,
            unverified_count,
        )

    install_root = PACKS_ROOT / pack_id
    data_root = install_root / "data"
    final_manifest_path = install_root / "manifest.json"

    if install_root.exists():
        if not replace_existing:
            raise RuntimeError(f"Pack is already installed: {pack_id}")
        shutil.rmtree(install_root)

    ensure_dir(install_root)
    shutil.copytree(stage_data_root, data_root, dirs_exist_ok=True)
    shutil.copy2(manifest_path, final_manifest_path)
    manifest_hash = str(manifest.get("manifest_hash") or "").strip() or sha256_file(final_manifest_path)

    saved_state, materialization = _install_pack_record(
        pack_id,
        pack_version,
        data_root,
        catalog_fragment,
        catalog_fragment,
        final_manifest_path,
        manifest_hash,
        activate=activate,
    )

    return {
        "pack_id": pack_id,
        "installed": True,
        "install_root": str(install_root),
        "data_root": str(data_root),
        "catalog_path": str(data_root / "catalog.json"),
        "manifest_path": str(final_manifest_path),
        "source_count": len(catalog_fragment.get("sources", [])),
        "state": saved_state,
        "materialization": materialization,
    }


def install_pack_from_manifest_ref(
    manifest_ref: str,
    *,
    artifact_base_ref: str | None = None,
    activate: bool = False,
    replace_existing: bool = True,
) -> dict:
    staged = stage_pack_artifact(manifest_ref, artifact_base_ref=artifact_base_ref)
    installed = install_pack_from_manifest(
        staged["manifest_path"],
        activate=activate,
        replace_existing=replace_existing,
    )
    installed["staging"] = staged
    return installed


def uninstall_pack(pack_id: str, full_catalog: dict) -> dict:
    install_root = PACKS_ROOT / pack_id
    if install_root.exists():
        shutil.rmtree(install_root)

    state = load_pack_state()
    installed_packs = [entry for entry in state.get("installed_packs", []) if entry.get("pack_id") != pack_id]
    active_pack_ids = [pid for pid in state.get("active_pack_ids", []) if pid != pack_id]
    state["installed_packs"] = installed_packs
    state["active_pack_ids"] = active_pack_ids
    saved_state = save_pack_state(state)

    materialization = None
    if saved_state.get("catalog_mode") == "managed_packs":
        materialization = materialize_active_data_root(full_catalog, saved_state)

    return {
        "pack_id": pack_id,
        "removed": True,
        "install_root": str(install_root),
        "state": saved_state,
        "materialization": materialization,
    }
