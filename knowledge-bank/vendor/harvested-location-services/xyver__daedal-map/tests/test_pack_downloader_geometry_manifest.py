from __future__ import annotations

import hashlib

import pytest

from mapmover.pack_downloader import _geometry_edition_projection, _load_json_from_ref


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def test_geometry_download_projection_comes_from_unified_release_manifest() -> None:
    digest = _digest("payload")
    release = {
        "manifest_kind": "geometry_release_unit",
        "version": "1.2.3",
        "released_at": "2026-09-16T00:00:00Z",
        "objects": [{"sha256": digest, "size_bytes": 17}],
        "editions": {
            "detail": {
                "delivery": "download",
                "files": [{"path": "exact/data.parquet", "object_sha256": digest}],
                "artifact": {
                    "filename": "test-detail-1.2.3.zip",
                    "download_url": "https://example.test/test-detail-1.2.3.zip",
                    "sha256": _digest("zip"),
                    "size_bytes": 99,
                },
            }
        },
    }
    current = {
        "package_profile": "geometry",
        "package_id": "test-detail",
        "current_version": "1.2.3",
        "edition": "detail",
        "release_manifest_url": "https://example.test/releases/1.2.3/manifest.json",
    }

    selected = _geometry_edition_projection(release, current)

    assert selected["pack_id"] == "test-detail"
    assert selected["artifact"] == release["editions"]["detail"]["artifact"]
    assert selected["files"] == [{
        "path": "exact/data.parquet", "sha256": digest, "size_bytes": 17,
    }]


def test_geometry_download_projection_fails_on_unknown_object() -> None:
    release = {
        "manifest_kind": "geometry_release_unit",
        "version": "1.0.0",
        "objects": [],
        "editions": {
            "lite": {
                "delivery": "download",
                "files": [{"path": "README.md", "object_sha256": _digest("missing")}],
                "artifact": {},
            }
        },
    }
    current = {
        "package_profile": "geometry",
        "package_id": "test-lite",
        "current_version": "1.0.0",
        "edition": "lite",
        "release_manifest_url": "https://example.test/releases/1.0.0/manifest.json",
    }

    with pytest.raises(RuntimeError, match="unknown object"):
        _geometry_edition_projection(release, current)


def test_geometry_manifest_pointer_hash_is_verified(tmp_path) -> None:
    path = tmp_path / "manifest.json"
    payload = b'{"version":"1.0.0"}\n'
    path.write_bytes(payload)
    assert _load_json_from_ref(str(path), hashlib.sha256(payload).hexdigest()) == {"version": "1.0.0"}
    with pytest.raises(RuntimeError, match="hash mismatch"):
        _load_json_from_ref(str(path), _digest("different"))
