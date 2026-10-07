"""Shared access contract for immutable runtime artifacts.

This module owns object-store location and basic bytes/JSON reads for data,
geometry, reference, catalog, and raster artifacts.  It intentionally does not
serve mutable control/Ops objects or account-owned/generated artifacts.

It also owns the bounded Tier-2 local hydration cache for immutable published
artifacts. Callers should use this contract instead of constructing published
bucket keys, creating their own S3 clients, or inventing another disk cache.
"""

from __future__ import annotations

import json
import hashlib
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from ..runtime_config import get_runtime_config


ArtifactLane = Literal["active", "published"]
_CACHE_INDEX_NAME = "index.json"
_CACHE_LOCK = threading.RLock()
_HYDRATION_LOCKS: dict[str, threading.Lock] = {}
_VERIFIED_FILES: dict[str, tuple[int, int, str]] = {}
_REMOTE_IDENTITIES: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_STATS = {
    "disk_hits": 0,
    "disk_misses": 0,
    "remote_reads": 0,
    "hydrations": 0,
    "hydrated_bytes": 0,
    "evictions": 0,
    "evicted_bytes": 0,
    "bypassed_disabled": 0,
    "bypassed_mutable_lane": 0,
    "bypassed_size": 0,
    "errors": 0,
}


@dataclass(frozen=True)
class PublishedArtifactRef:
    """Canonical object identity for one immutable runtime artifact."""

    relative_path: str
    bucket: str
    key: str
    prefix: str
    endpoint_url: str | None
    region: str
    lane: ArtifactLane

    @property
    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"


def _cloud_config() -> dict[str, Any]:
    config = get_runtime_config().get("cloud", {}) or {}
    return config if isinstance(config, dict) else {}


def _normalize_relative_path(relative_path: str | Path) -> str:
    raw = str(relative_path).strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if (
        not raw
        or raw in {".", ".."}
        or path.is_absolute()
        or PureWindowsPath(raw).is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"Artifact path must be a safe non-empty relative path: {relative_path!r}")
    return path.as_posix()


def artifact_prefix(lane: ArtifactLane = "published") -> str:
    """Return the one configured object prefix for the requested immutable lane."""
    cloud_cfg = _cloud_config()
    active = (
        os.environ.get("S3_PREFIX", "").strip()
        or str(cloud_cfg.get("prefix", "")).strip()
    )
    if lane == "active":
        return (active or "published").strip("/")
    if lane != "published":
        raise ValueError(f"Unsupported artifact lane: {lane}")
    return (
        os.environ.get("S3_PUBLISHED_PREFIX", "").strip()
        or active
        or "published"
    ).strip("/")


def artifact_ref(
    relative_path: str | Path,
    *,
    lane: ArtifactLane = "published",
) -> PublishedArtifactRef:
    """Build the canonical object-store identity for an immutable artifact."""
    cloud_cfg = _cloud_config()
    bucket = os.environ.get("S3_BUCKET", "").strip() or str(cloud_cfg.get("bucket", "")).strip()
    if not bucket:
        raise RuntimeError("Published artifact access requires S3_BUCKET or cloud.bucket")
    relative = _normalize_relative_path(relative_path)
    prefix = artifact_prefix(lane)
    key = f"{prefix}/{relative}" if prefix else relative
    endpoint_url = os.environ.get("S3_ENDPOINT_URL", "").strip() or str(
        cloud_cfg.get("endpoint_url", "") or ""
    ).strip()
    region = (
        os.environ.get("AWS_DEFAULT_REGION", "").strip()
        or os.environ.get("AWS_REGION", "").strip()
        or "auto"
    )
    return PublishedArtifactRef(
        relative_path=relative,
        bucket=bucket,
        key=key,
        prefix=prefix,
        endpoint_url=endpoint_url or None,
        region=region,
        lane=lane,
    )


def relative_data_path(path: Path, *, data_root: Path) -> str:
    """Return a canonical published path for a file under DATA_ROOT."""
    try:
        relative = path.resolve().relative_to(data_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Artifact path is outside DATA_ROOT: {path}") from exc
    return _normalize_relative_path(relative)


def data_artifact_ref(
    path: Path,
    *,
    data_root: Path,
    lane: ArtifactLane = "active",
) -> PublishedArtifactRef:
    return artifact_ref(relative_data_path(path, data_root=data_root), lane=lane)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_bytes(name: str, default_mb: int) -> int:
    try:
        value_mb = int(os.environ.get(name, str(default_mb)))
    except (TypeError, ValueError):
        value_mb = default_mb
    return max(0, value_mb) * 1024 * 1024


def artifact_cache_enabled() -> bool:
    """Whether immutable local artifact hydration is enabled for this runtime."""
    return _env_bool("PUBLISHED_ARTIFACT_CACHE_ENABLED", True)


def artifact_cache_root() -> Path:
    configured = os.environ.get("PUBLISHED_ARTIFACT_CACHE_DIR", "").strip()
    if configured:
        return Path(configured)
    from ..paths import CACHE_DIR

    return CACHE_DIR / "published-artifacts"


def artifact_cache_quota_bytes() -> int:
    return _env_bytes("PUBLISHED_ARTIFACT_CACHE_QUOTA_MB", 2048)


def artifact_cache_max_file_bytes() -> int:
    # The Canada reference relationship graph is currently about 669 MB.
    # Keep the cache bounded by the independent 2 GB total quota, while
    # allowing reviewed runtime banks of this size to hydrate once instead of
    # forcing a remote Parquet scan on every MCP call.
    return _env_bytes("PUBLISHED_ARTIFACT_CACHE_MAX_FILE_MB", 1024)


def artifact_cache_revalidate_seconds() -> int:
    try:
        return max(0, int(os.environ.get("PUBLISHED_ARTIFACT_CACHE_REVALIDATE_SECONDS", "300")))
    except (TypeError, ValueError):
        return 300


def artifact_cache_eviction_grace_seconds() -> int:
    """Minimum age before a cached path may be unlinked.

    ``path_to_uri`` hands local paths to DuckDB after releasing the cache lock.
    Without a grace window, a concurrent hydration can evict that path between
    resolution and ``read_parquet()``, producing a missing-file race.  The
    grace is longer than the hosted query budget; when no old entry is safe to
    evict, hydration simply falls back to the authoritative S3 URI.
    """

    try:
        return max(
            0,
            int(os.environ.get("PUBLISHED_ARTIFACT_CACHE_EVICTION_GRACE_SECONDS", "120")),
        )
    except (TypeError, ValueError):
        return 120


def _cache_eligible(ref: PublishedArtifactRef) -> bool:
    if not artifact_cache_enabled():
        _CACHE_STATS["bypassed_disabled"] += 1
        return False
    # An active candidate/WIP prefix is not immutable. An active read may use
    # Tier 2 only when it resolves to the same prefix as the published lane.
    if ref.lane == "active" and ref.prefix != artifact_prefix("published"):
        _CACHE_STATS["bypassed_mutable_lane"] += 1
        return False
    return True


def _cache_key(ref: PublishedArtifactRef) -> str:
    return ref.uri


def _cache_path(ref: PublishedArtifactRef) -> Path:
    digest = hashlib.sha256(_cache_key(ref).encode("utf-8")).hexdigest()
    suffix = "".join(PurePosixPath(ref.relative_path).suffixes)[-24:]
    return artifact_cache_root() / "objects" / digest[:2] / f"{digest}{suffix}"


def _index_path() -> Path:
    return artifact_cache_root() / _CACHE_INDEX_NAME


def _load_index() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(_index_path().read_text(encoding="utf-8"))
        entries = payload.get("entries") if isinstance(payload, dict) else None
        return entries if isinstance(entries, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_index(entries: dict[str, dict[str, Any]]) -> None:
    root = artifact_cache_root()
    root.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "1.0", "entries": entries}
    fd, temp_name = tempfile.mkstemp(prefix="index-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, _index_path())
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_local_file(path: Path, entry: dict[str, Any]) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    expected_size = int(entry.get("bytes") or -1)
    expected_sha = str(entry.get("sha256") or "").strip().lower()
    if stat.st_size != expected_size or not expected_sha:
        return False
    verification_key = str(path.resolve())
    cached = _VERIFIED_FILES.get(verification_key)
    signature = (stat.st_size, stat.st_mtime_ns, expected_sha)
    if cached == signature:
        return True
    if _sha256_file(path).lower() != expected_sha:
        return False
    _VERIFIED_FILES[verification_key] = signature
    return True


def _safe_entry_path(entry: dict[str, Any]) -> Path | None:
    raw = str(entry.get("local_path") or "").strip()
    if not raw:
        return None
    path = Path(raw).resolve()
    objects_root = (artifact_cache_root() / "objects").resolve()
    try:
        path.relative_to(objects_root)
    except ValueError:
        return None
    return path


def _remote_identity(ref: PublishedArtifactRef) -> dict[str, Any]:
    key = _cache_key(ref)
    now = time.time()
    with _CACHE_LOCK:
        cached = _REMOTE_IDENTITIES.get(key)
        if cached and now - cached[0] <= artifact_cache_revalidate_seconds():
            return dict(cached[1])
    response = _object_store_client(ref).head_object(Bucket=ref.bucket, Key=ref.key)
    modified = response.get("LastModified")
    identity = {
        "bytes": int(response.get("ContentLength") or 0),
        "etag": str(response.get("ETag") or "").strip('"'),
        "last_modified": modified.isoformat() if isinstance(modified, datetime) else str(modified or ""),
    }
    with _CACHE_LOCK:
        _REMOTE_IDENTITIES[key] = (now, identity)
    return dict(identity)


def _entry_matches_remote(entry: dict[str, Any], remote: dict[str, Any]) -> bool:
    if int(entry.get("bytes") or -1) != int(remote.get("bytes") or 0):
        return False
    remote_etag = str(remote.get("etag") or "")
    remote_modified = str(remote.get("last_modified") or "")
    return bool(
        (remote_etag and remote_etag == str(entry.get("etag") or ""))
        or (remote_modified and remote_modified == str(entry.get("last_modified") or ""))
    )


def _remove_entry(entries: dict[str, dict[str, Any]], key: str) -> int:
    entry = entries.pop(key, None) or {}
    path = _safe_entry_path(entry)
    size = int(entry.get("bytes") or 0)
    try:
        if path is not None and path.is_file():
            path.unlink()
    except OSError:
        pass
    if path is not None:
        _VERIFIED_FILES.pop(str(path), None)
    return size


def _evict_for(entries: dict[str, dict[str, Any]], incoming_bytes: int, *, keep_key: str) -> bool:
    quota = artifact_cache_quota_bytes()
    if quota <= 0 or incoming_bytes > quota:
        return False
    existing_bytes = sum(int(entry.get("bytes") or 0) for entry in entries.values())
    safe_before = time.time() - artifact_cache_eviction_grace_seconds()
    candidates = sorted(
        (
            (key, entry)
            for key, entry in entries.items()
            if key != keep_key
            and float(entry.get("last_accessed") or 0) <= safe_before
        ),
        key=lambda item: (float(item[1].get("last_accessed") or 0), item[0]),
    )
    for key, _entry in candidates:
        if existing_bytes + incoming_bytes <= quota:
            break
        removed = _remove_entry(entries, key)
        existing_bytes -= removed
        _CACHE_STATS["evictions"] += 1
        _CACHE_STATS["evicted_bytes"] += removed
    return existing_bytes + incoming_bytes <= quota


def _hydration_lock(key: str) -> threading.Lock:
    with _CACHE_LOCK:
        return _HYDRATION_LOCKS.setdefault(key, threading.Lock())


def resolve_artifact_path(
    relative_path: str | Path,
    *,
    lane: ArtifactLane = "published",
    max_bytes: int | None = None,
) -> Path | None:
    """Return a verified local artifact, hydrating it when safely bounded.

    Any cache, metadata, or hydration failure returns ``None`` so callers can
    fall back to the authoritative object-store read.
    """
    ref = artifact_ref(relative_path, lane=lane)
    if not _cache_eligible(ref):
        return None
    key = _cache_key(ref)
    with _hydration_lock(key):
        try:
            remote = _remote_identity(ref)
            size_limit = artifact_cache_max_file_bytes() if max_bytes is None else max(0, max_bytes)
            if int(remote["bytes"]) > size_limit:
                _CACHE_STATS["bypassed_size"] += 1
                return None
            with _CACHE_LOCK:
                entries = _load_index()
                entry = entries.get(key) or {}
                local_path = _safe_entry_path(entry) or _cache_path(ref)
                if entry and _entry_matches_remote(entry, remote) and _verified_local_file(local_path, entry):
                    entry["last_accessed"] = time.time()
                    entries[key] = entry
                    _write_index(entries)
                    _CACHE_STATS["disk_hits"] += 1
                    return local_path
                _CACHE_STATS["disk_misses"] += 1
                if entry:
                    _remove_entry(entries, key)
                if not _evict_for(entries, int(remote["bytes"]), keep_key=key):
                    _write_index(entries)
                    _CACHE_STATS["bypassed_size"] += 1
                    return None

            local_path = _cache_path(ref)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f"{local_path.name}-", suffix=".tmp", dir=local_path.parent)
            digest = hashlib.sha256()
            written = 0
            try:
                response = _object_store_client(ref).get_object(Bucket=ref.bucket, Key=ref.key)
                with os.fdopen(fd, "wb") as stream:
                    while True:
                        chunk = response["Body"].read(1024 * 1024)
                        if not chunk:
                            break
                        stream.write(chunk)
                        digest.update(chunk)
                        written += len(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
                if written != int(remote["bytes"]):
                    raise IOError(f"Artifact length changed during hydration: expected {remote['bytes']}, got {written}")
                os.replace(temp_name, local_path)
            finally:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    pass

            now = time.time()
            entry = {
                "bucket": ref.bucket,
                "key": ref.key,
                "relative_path": ref.relative_path,
                "lane": ref.lane,
                "local_path": str(local_path),
                "bytes": written,
                "sha256": digest.hexdigest(),
                "etag": remote["etag"],
                "last_modified": remote["last_modified"],
                "cached_at": now,
                "last_accessed": now,
            }
            with _CACHE_LOCK:
                entries = _load_index()
                if not _evict_for(entries, written, keep_key=key):
                    try:
                        local_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    _write_index(entries)
                    _CACHE_STATS["bypassed_size"] += 1
                    return None
                entries[key] = entry
                _write_index(entries)
                stat = local_path.stat()
                _VERIFIED_FILES[str(local_path.resolve())] = (stat.st_size, stat.st_mtime_ns, entry["sha256"])
                _CACHE_STATS["hydrations"] += 1
                _CACHE_STATS["hydrated_bytes"] += written
            return local_path
        except Exception:
            _CACHE_STATS["errors"] += 1
            return None


def resolve_data_artifact_uri(
    path: Path,
    *,
    data_root: Path,
    lane: ArtifactLane = "active",
    max_bytes: int | None = None,
) -> str:
    """Resolve a DATA_ROOT artifact to verified local storage or its S3 URI."""
    relative = relative_data_path(path, data_root=data_root)
    local = resolve_artifact_path(relative, lane=lane, max_bytes=max_bytes)
    return str(local) if local is not None else artifact_ref(relative, lane=lane).uri


def artifact_cache_status() -> dict[str, Any]:
    """Return bounded operational telemetry without exposing credentials."""
    with _CACHE_LOCK:
        entries = _load_index() if artifact_cache_enabled() else {}
        total_bytes = sum(int(entry.get("bytes") or 0) for entry in entries.values())
        return {
            "enabled": artifact_cache_enabled(),
            "root": str(artifact_cache_root()),
            "entry_count": len(entries),
            "bytes": total_bytes,
            "quota_bytes": artifact_cache_quota_bytes(),
            "max_file_bytes": artifact_cache_max_file_bytes(),
            "revalidate_seconds": artifact_cache_revalidate_seconds(),
            "eviction_grace_seconds": artifact_cache_eviction_grace_seconds(),
            **_CACHE_STATS,
        }


def _object_store_client(ref: PublishedArtifactRef):
    import boto3

    return boto3.client("s3", endpoint_url=ref.endpoint_url, region_name=ref.region)


def read_artifact_bytes(
    relative_path: str | Path,
    *,
    lane: ArtifactLane = "published",
) -> bytes:
    """Read immutable artifact bytes from object storage.

    Missing objects and transport errors intentionally propagate so each domain
    caller can apply its existing fallback/error policy.
    """
    local_path = resolve_artifact_path(relative_path, lane=lane)
    if local_path is not None:
        return local_path.read_bytes()
    ref = artifact_ref(relative_path, lane=lane)
    _CACHE_STATS["remote_reads"] += 1
    response = _object_store_client(ref).get_object(Bucket=ref.bucket, Key=ref.key)
    return response["Body"].read()


def read_artifact_json(
    relative_path: str | Path,
    *,
    lane: ArtifactLane = "published",
) -> Any:
    """Read and decode one immutable JSON artifact."""
    return json.loads(read_artifact_bytes(relative_path, lane=lane))
