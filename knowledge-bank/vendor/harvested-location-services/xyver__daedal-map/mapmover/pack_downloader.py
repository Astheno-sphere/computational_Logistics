"""
Pack artifact staging/downloader helpers.

This module downloads or copies a staged pack artifact into CACHE_DIR so the
runtime can verify it and then install it through the manifest-driven path.

Supported remote formats:
- legacy manifest + per-file data/ staging
- unified geometry contract:
  - current.json -> country releases/<version>/manifest.json -> selected edition -> ZIP
- legacy stable downloadable contract (non-geometry packs only):
  - current.json -> version.json -> pack.zip
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from geometry_download_shared import geometry_edition_projection as _geometry_edition_projection

from .artifact_utils import safe_extract_zip, sha256_file
from .paths import CACHE_DIR, ensure_dir


logger = logging.getLogger("mapmover")

PACK_STAGING_ROOT = CACHE_DIR / "pack-staging"


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "file"}


def _resolve_local_source(ref: str) -> Path:
    parsed = urlparse(ref)
    if parsed.scheme == "file":
        return Path(parsed.path)
    return Path(ref)


def _download_to_path(source: str, dest: Path) -> None:
    ensure_dir(dest.parent)
    if _looks_like_url(source):
        parsed = urlparse(source)
        if parsed.scheme == "file":
            shutil.copy2(_resolve_local_source(source), dest)
            return
        with requests.get(source, stream=True, timeout=120) as response:
            response.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
        return
    shutil.copy2(_resolve_local_source(source), dest)


def _load_json_from_ref(ref: str, expected_sha256: str | None = None) -> dict:
    if _looks_like_url(ref) and urlparse(ref).scheme in {"http", "https"}:
        response = requests.get(ref, timeout=60)
        response.raise_for_status()
        payload = response.content
    else:
        payload = _resolve_local_source(ref).read_bytes()
    if expected_sha256 and hashlib.sha256(payload).hexdigest() != expected_sha256.lower():
        raise RuntimeError(f"Release manifest hash mismatch: {ref}")
    data = json.loads(payload.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _looks_like_stable_current_manifest(manifest: dict) -> bool:
    return bool(manifest.get("current_version")) and bool(manifest.get("version_manifest_url"))


def _looks_like_geometry_current_manifest(manifest: dict) -> bool:
    return (
        manifest.get("package_profile") == "geometry"
        and bool(manifest.get("current_version"))
        and bool(manifest.get("release_manifest_url"))
        and bool(manifest.get("edition"))
    )


def _looks_like_stable_version_manifest(manifest: dict) -> bool:
    artifact = manifest.get("artifact") or {}
    return bool(manifest.get("version")) and isinstance(artifact, dict) and bool(artifact.get("download_url"))


def _stage_pack_zip_from_version_manifest(version_manifest: dict, stage_root: Path) -> dict:
    pack_id = str(version_manifest.get("source_id") or version_manifest.get("pack_id") or "").strip()
    pack_version = str(version_manifest.get("version") or "").strip() or "unknown"
    artifact = version_manifest.get("artifact") or {}
    artifact_url = str(artifact.get("download_url") or "").strip()
    expected_sha = str(artifact.get("sha256") or "").strip().lower()
    if not pack_id:
        raise RuntimeError("Version manifest missing source_id/pack_id")
    if not artifact_url:
        raise RuntimeError(f"Version manifest missing artifact.download_url for {pack_id}")
    if not expected_sha:
        # The stable downloadable contract is produced by our own exporter, so a
        # missing artifact hash means a broken release, not an optional field.
        raise RuntimeError(
            f"Version manifest missing artifact.sha256 for {pack_id}; refusing to install unverified pack artifact"
        )

    if stage_root.exists():
        shutil.rmtree(stage_root)
    ensure_dir(stage_root)

    artifact_dir = stage_root / "_artifact"
    ensure_dir(artifact_dir)
    artifact_zip = artifact_dir / "pack.zip"
    _download_to_path(artifact_url, artifact_zip)

    if sha256_file(artifact_zip).lower() != expected_sha:
        raise RuntimeError(f"Hash mismatch for staged pack artifact: {pack_id}")

    extract_root = stage_root / "_extract"
    safe_extract_zip(artifact_zip, extract_root)

    data_root = extract_root / "data"
    if not (data_root / "catalog.json").exists():
        raise RuntimeError(f"Downloaded pack artifact did not contain data/catalog.json for {pack_id}")

    for child in extract_root.iterdir():
        destination = stage_root / child.name
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        shutil.move(str(child), str(destination))
    shutil.rmtree(extract_root, ignore_errors=True)

    manifest_payload = {
        "version": 1,
        "pack_id": pack_id,
        "pack_version": pack_version,
        "generated_at": str(version_manifest.get("published_at") or ""),
        "files": version_manifest.get("files") or [],
    }
    manifest_hash = hashlib.sha256(json.dumps(manifest_payload, sort_keys=True).encode("utf-8")).hexdigest()
    manifest_payload["manifest_hash"] = manifest_hash
    manifest_path = stage_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    return {
        "pack_id": pack_id,
        "pack_version": pack_version,
        "stage_root": str(stage_root),
        "manifest_path": str(manifest_path),
        "data_root": str(stage_root / "data"),
        "downloaded_files": [str(item.get("path") or "").strip() for item in version_manifest.get("files", []) if str(item.get("path") or "").strip()],
        "artifact_url": artifact_url,
    }


def _default_artifact_base(manifest_ref: str) -> str:
    if _looks_like_url(manifest_ref):
        parsed = urlparse(manifest_ref)
        url_path = parsed.path or ""
        prefix, _, last_segment = url_path.rpartition("/")
        if last_segment == "manifest.json":
            base_path = prefix + "/data/"
        else:
            base_path = url_path.rstrip("/") + "/data/"
        return parsed._replace(path=base_path, query="", fragment="").geturl()
    manifest_path = _resolve_local_source(manifest_ref)
    return str(manifest_path.parent / "data")


def stage_pack_artifact(manifest_ref: str, artifact_base_ref: str | None = None) -> dict:
    manifest = _load_json_from_ref(manifest_ref)
    if _looks_like_geometry_current_manifest(manifest):
        release_ref = str(manifest.get("release_manifest_url") or "").strip()
        release = _load_json_from_ref(release_ref, manifest.get("release_manifest_sha256"))
        manifest = _geometry_edition_projection(release, manifest)
        manifest_ref = release_ref
    elif _looks_like_stable_current_manifest(manifest):
        version_ref = str(manifest.get("version_manifest_url") or "").strip()
        if not version_ref:
            raise RuntimeError(f"Current manifest missing version_manifest_url: {manifest_ref}")
        manifest = _load_json_from_ref(version_ref)
        manifest_ref = version_ref

    if _looks_like_stable_version_manifest(manifest):
        pack_id = str(manifest.get("source_id") or manifest.get("pack_id") or "").strip()
        pack_version = str(manifest.get("version") or "").strip() or "unknown"
        if not pack_id:
            raise RuntimeError(f"Version manifest missing source_id/pack_id: {manifest_ref}")
        stage_root = PACK_STAGING_ROOT / pack_id / pack_version
        return _stage_pack_zip_from_version_manifest(manifest, stage_root)

    pack_id = str(manifest.get("pack_id") or "").strip()
    pack_version = str(manifest.get("pack_version") or manifest.get("version") or "").strip() or "unknown"
    if not pack_id:
        raise RuntimeError(f"Manifest missing pack_id: {manifest_ref}")

    stage_root = PACK_STAGING_ROOT / pack_id / pack_version
    if stage_root.exists():
        shutil.rmtree(stage_root)
    data_root = stage_root / "data"
    ensure_dir(data_root)

    manifest_path = stage_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    artifact_base_ref = artifact_base_ref or manifest.get("artifact_base_url") or _default_artifact_base(manifest_ref)

    downloaded_files = []
    unverified_files = []
    for file_info in manifest.get("files", []):
        rel_path = str(file_info.get("path") or "").strip()
        if not rel_path:
            continue
        dest_path = data_root.joinpath(*rel_path.split("/"))
        if _looks_like_url(artifact_base_ref):
            source_ref = urljoin(artifact_base_ref if artifact_base_ref.endswith("/") else artifact_base_ref + "/", rel_path)
        else:
            source_ref = str(Path(artifact_base_ref).joinpath(*rel_path.split("/")))
        _download_to_path(source_ref, dest_path)
        expected_hash = str(file_info.get("sha256") or "").strip().lower()
        if not expected_hash:
            unverified_files.append(rel_path)
        elif sha256_file(dest_path).lower() != expected_hash:
            raise RuntimeError(f"Hash mismatch for staged file: {rel_path}")
        downloaded_files.append(rel_path)

    if unverified_files:
        logger.warning(
            "SECURITY WARNING: pack %s staged %d of %d files with no sha256 in the legacy manifest; "
            "these files were NOT verified",
            pack_id,
            len(unverified_files),
            len(downloaded_files),
        )

    return {
        "pack_id": pack_id,
        "pack_version": pack_version,
        "stage_root": str(stage_root),
        "manifest_path": str(manifest_path),
        "data_root": str(data_root),
        "downloaded_files": downloaded_files,
    }
