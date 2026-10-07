"""Reusable DuckDB helpers for parquet-backed runtime queries.

In local mode, all functions accept Path objects pointing to local parquet files.
In cloud mode, path_to_uri() converts local cache paths to s3:// URIs and the
DuckDB connection is configured with httpfs + object-storage credentials.
DuckDB fetches only the row groups it needs via HTTP range requests.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import queue
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from .runtime_config import force_remote_data_reads, get_data_plane_mode, get_runtime_config
from .catalog_surface import get_catalog_surface_override
from .runtime.published_artifacts import resolve_data_artifact_uri

try:
    import duckdb
except ImportError:
    duckdb = None


logger = logging.getLogger(__name__)
_MISSING_TIME_FILTER_WARNING_KEYS: set[tuple[str, tuple[str, ...]]] = set()
_PARQUET_COLUMNS_CACHE: dict[str, tuple[tuple[int, int], set[str]]] = {}
_PARQUET_CLOUD_COLUMNS_CACHE: dict[str, tuple[float, set[str]]] = {}
_PARQUET_COLUMNS_CACHE_LOCK = threading.Lock()


DUCKDB_EVENT_SOURCES = {
    # Legacy pack-level event ids
    "earthquakes",
    "floods",
    "hurricanes",
    "landslides",
    "tornadoes",
    "tsunamis",
    "volcanoes",
    # Current pack-facing event source ids after disaster source cleanup
    "earthquakes_events",
    "tsunamis_events",
    "volcanoes_events",
    # Wildfire event sources remain split by upstream family rather than a single
    # shared events parquet, so keep the concrete event-capable ids here.
    "global_fire_atlas",
    "wildfires_usa",
    "can_wildfires",
}


def duckdb_available() -> bool:
    return duckdb is not None


def can_query_event_source(source_id: str) -> bool:
    return duckdb_available() and source_id in DUCKDB_EVENT_SOURCES


# ---------------------------------------------------------------------------
# Cloud / httpfs helpers
# ---------------------------------------------------------------------------

def is_cloud_mode() -> bool:
    return get_data_plane_mode() == "cloud"


def _allow_local_source_fallback() -> bool:
    if force_remote_data_reads():
        return False
    override = get_catalog_surface_override()
    if override in {"published", "wip"}:
        return override == "wip"
    raw = str(os.environ.get("USE_WIP_CATALOG", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _get_s3_endpoint() -> str:
    """Return the R2/S3 endpoint without https:// prefix (as DuckDB expects)."""
    cloud_cfg = get_runtime_config().get("cloud", {})
    url = (os.environ.get("S3_ENDPOINT_URL", "").strip() or str(cloud_cfg.get("endpoint_url", "")).strip())
    if url.startswith("https://"):
        url = url[len("https://"):]
    elif url.startswith("http://"):
        url = url[len("http://"):]
    return url.rstrip("/")


def _get_data_root() -> Path:
    from .paths import DATA_ROOT
    return DATA_ROOT


def path_to_uri(local_path: Path) -> str:
    """Convert a local data path to an s3:// URI in cloud mode, or a local path string in local mode."""
    if not is_cloud_mode():
        return str(local_path)

    if _allow_local_source_fallback() and local_path.exists():
        return str(local_path)

    data_root = _get_data_root()

    try:
        # Do not hydrate large parquet inputs merely to execute a selective
        # DuckDB query.  Hydrating a 100+ MB country spine turns an exact
        # loc_id lookup into a full object download and can consume the entire
        # hosted response budget.  DuckDB/httpfs is explicitly configured for
        # remote range reads, so keep larger files authoritative in object
        # storage and hydrate only small, repeatedly reused query artifacts.
        max_query_cache_bytes = max(
            0,
            int(float(os.environ.get("PUBLISHED_ARTIFACT_CACHE_QUERY_MAX_FILE_MB", "32")) * 1024 * 1024),
        )
        return resolve_data_artifact_uri(
            local_path,
            data_root=data_root,
            lane="active",
            max_bytes=max_query_cache_bytes,
        )
    except ValueError:
        pass

    # Fallback: use the path as-is (shouldn't normally happen)
    return str(local_path)


def parquet_available(path: Path) -> bool:
    """Return True if the parquet file is accessible.
    In cloud mode, always returns True (DuckDB will raise if the file is missing remotely).
    In local mode, checks if the file exists on disk.
    """
    if is_cloud_mode():
        return path.exists() or True
    return path.exists()


def resolve_flood_events_path(global_dir: Path) -> Path:
    canonical_path = global_dir / "disasters/floods/events.parquet"
    if is_cloud_mode() or canonical_path.exists():
        return canonical_path
    legacy_enriched_path = global_dir / "disasters/floods/events_enriched.parquet"
    return legacy_enriched_path if legacy_enriched_path.exists() else canonical_path


def _configure_httpfs(con) -> None:
    """Configure object-storage access via httpfs on an existing connection."""
    # Some local/dev environments cannot write to the default DuckDB home under
    # the user profile. Point extension storage at our writable runtime cache so
    # cloud-mode queries behave the same way in hosted and local QA.
    from .paths import CACHE_DIR

    extension_dir = CACHE_DIR / "duckdb_extensions"
    extension_dir.mkdir(parents=True, exist_ok=True)
    extension_dir_sql = str(extension_dir).replace("'", "''")
    con.execute(f"SET extension_directory='{extension_dir_sql}'")
    try:
        con.execute("LOAD httpfs")
    except Exception:
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")
    endpoint = _get_s3_endpoint()
    if endpoint:
        con.execute(f"SET s3_endpoint='{endpoint}'")
    key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    region = os.environ.get("AWS_DEFAULT_REGION", "auto").strip() or "auto"
    if key:
        con.execute(f"SET s3_access_key_id='{key}'")
    if secret:
        con.execute(f"SET s3_secret_access_key='{secret}'")
    con.execute(f"SET s3_region='{region}'")
    con.execute("SET s3_url_style='path'")
    # Cache parquet footer/metadata globally across connections - eliminates
    # repeated HTTP HEAD+range requests for the same files on each new connection.
    con.execute("SET enable_http_metadata_cache=true")
    con.execute("SET http_keep_alive=true")


def _configure_common_runtime_settings(con) -> None:
    """Apply shared runtime safety settings to any DuckDB connection."""
    # Cap DuckDB's internal buffer pool so it doesn't grow unbounded under load.
    # Adjust DUCKDB_MEMORY_LIMIT env var to tune (default: 512MB).
    mem_limit = os.environ.get("DUCKDB_MEMORY_LIMIT", "512MB")
    con.execute(f"SET memory_limit='{mem_limit}'")
    # Constrained containers pay memory per active scan thread.  Two threads
    # retain useful parallelism without multiplying buffers up to the 488 MB
    # Railway ceiling; deployments with more headroom can opt upward.
    thread_count = max(1, int(os.environ.get("DUCKDB_THREADS", "2")))
    con.execute(f"SET threads={thread_count}")
    # SQL result order is never a storage contract here (callers that require
    # order use ORDER BY). Disabling preservation allows DuckDB to stream and
    # spill bounded queries instead of retaining insertion-order buffers.
    con.execute("SET preserve_insertion_order=false")


def build_guarded_connection(
    *,
    database: str = ":memory:",
    configure_cloud: bool | None = None,
):
    """Create a DuckDB connection with the shared runtime safety settings."""
    if duckdb is None:
        return None
    con = duckdb.connect(database=database)
    _configure_common_runtime_settings(con)
    if configure_cloud is None:
        configure_cloud = is_cloud_mode()
    if configure_cloud:
        _configure_httpfs(con)
    return con


# ---------------------------------------------------------------------------
# Thread-local connection pool
# ---------------------------------------------------------------------------
#
# Each worker thread keeps one fully-configured DuckDB connection that
# persists across queries. This eliminates per-query connection setup
# (LOAD httpfs + credentials + memory limit) which dominates "cheap"
# filter queries in cloud mode.
#
# Why thread-local instead of one shared connection + cursor():
#
#   - DuckDB cursor() shares the database and globally-scoped settings,
#     but session-scoped settings (notably s3_endpoint and httpfs
#     credentials in 1.5.0) do NOT propagate. A 2026-04-27 deploy of a
#     shared-primary design caused production 500s because cursors hit
#     the default AWS endpoint instead of R2.
#   - Thread-local sidesteps the scoping question entirely. Each
#     connection is fully configured by _configure_httpfs at creation
#     and never relies on inheritance.
#
# Trade-offs:
#
#   - Connection setup is paid once per worker thread (typically 5-40
#     threads in uvicorn), not once per process. Small upfront cost,
#     no per-query cost after that.
#   - Each thread keeps its own HTTP metadata cache. Caches do not
#     share across threads. Within ~10-20 queries on a thread, all hot
#     parquets are warm in that thread's cache.
#   - A bad query is isolated to its connection; recovery clears the
#     thread-local entry so the next call rebuilds.

_thread_state = threading.local()
_THREAD_CONNECTION_GENERATION = 0
_THREAD_CONNECTION_GENERATION_LOCK = threading.Lock()
_QUERY_POOL_SIZE = max(1, min(16, int(os.environ.get("DUCKDB_QUERY_POOL_SIZE", "6"))))
_QUERY_POOL: queue.LifoQueue = queue.LifoQueue(maxsize=_QUERY_POOL_SIZE)
_QUERY_POOL_CREATED = 0
_QUERY_POOL_LOCK = threading.Lock()
_QUERY_POOL_GENERATION = 0
_QUERY_POOL_ACTIVITY_LOCK = threading.Lock()
_QUERY_POOL_ACTIVITY = {
    "active": 0, "active_high_water": 0, "acquisitions": 0,
    "releases": 0, "discards": 0, "wait_count": 0,
    "wait_seconds_total": 0.0, "wait_seconds_max": 0.0, "timeouts": 0,
}


def _record_pool_acquire(wait_seconds: float) -> None:
    with _QUERY_POOL_ACTIVITY_LOCK:
        activity = _QUERY_POOL_ACTIVITY
        activity["active"] += 1
        activity["active_high_water"] = max(activity["active_high_water"], activity["active"])
        activity["acquisitions"] += 1
        if wait_seconds > 0.001:
            activity["wait_count"] += 1
            activity["wait_seconds_total"] += wait_seconds
            activity["wait_seconds_max"] = max(activity["wait_seconds_max"], wait_seconds)


def _record_pool_release(*, discard: bool) -> None:
    with _QUERY_POOL_ACTIVITY_LOCK:
        activity = _QUERY_POOL_ACTIVITY
        activity["active"] = max(0, activity["active"] - 1)
        activity["releases"] += 1
        if discard:
            activity["discards"] += 1


def query_pool_activity_status() -> dict:
    """Return cheap lifetime occupancy counters; no connection or SQL is touched."""
    with _QUERY_POOL_ACTIVITY_LOCK:
        activity = dict(_QUERY_POOL_ACTIVITY)
    activity["wait_seconds_total"] = round(float(activity["wait_seconds_total"]), 6)
    activity["wait_seconds_max"] = round(float(activity["wait_seconds_max"]), 6)
    activity.update({
        "capacity": _QUERY_POOL_SIZE,
        "created": _QUERY_POOL_CREATED,
        "idle": _QUERY_POOL.qsize(),
        "generation": _QUERY_POOL_GENERATION,
    })
    return activity


def inspect_query_pool_memory() -> dict:
    """Snapshot memory ownership from existing idle cloud-pool connections.

    This deliberately never creates a connection or inspects active leases.
    Idle connections are removed briefly without holding the pool lock while
    ``duckdb_memory()`` runs, then returned using the normal generation checks.
    """
    with _QUERY_POOL_LOCK:
        generation = _QUERY_POOL_GENERATION
        created = _QUERY_POOL_CREATED
        idle: list[tuple[object, int]] = []
        for _ in range(min(16, _QUERY_POOL.qsize())):
            try:
                idle.append(_QUERY_POOL.get_nowait())
            except queue.Empty:
                break
    rows: list[dict] = []
    skipped = 0
    totals = {"memory_usage_bytes": 0, "temporary_storage_bytes": 0}
    for con, con_generation in idle:
        if con_generation != generation:
            _release_query_connection(con, generation=con_generation, discard=True, leased=False)
            skipped += 1
            continue
        discard = False
        try:
            cursor = con.execute("SELECT * FROM duckdb_memory()")
            columns = [str(item[0]) for item in (cursor.description or [])]
            for values in cursor.fetchall():
                detail = dict(zip(columns, values))
                memory = int(detail.get("memory_usage_bytes") or 0)
                temporary = int(detail.get("temporary_storage_bytes") or 0)
                totals["memory_usage_bytes"] += memory
                totals["temporary_storage_bytes"] += temporary
                rows.append(detail)
        except Exception as exc:
            skipped += 1
            logger.debug("duckdb_memory diagnostic failed", exc_info=True)
            discard = _looks_like_connection_error(exc)
        finally:
            _release_query_connection(con, generation=con_generation, discard=discard, leased=False)
    activity = query_pool_activity_status()
    return {
        "mode": get_data_plane_mode(),
        "pool_size": _QUERY_POOL_SIZE,
        "created": created,
        "idle": len(idle),
        "inuse_estimate": max(0, created - len(idle)),
        "generation": generation,
        "sampled_idle": len(idle) - skipped,
        "skipped": skipped,
        "memory_usage_bytes": totals["memory_usage_bytes"],
        "temporary_storage_bytes": totals["temporary_storage_bytes"],
        "details": rows,
        "active_leases": activity["active"],
        "activity": activity,
    }


def _acquire_query_connection():
    global _QUERY_POOL_CREATED
    started = time.monotonic()
    try:
        con, generation = _QUERY_POOL.get_nowait()
        if generation != _QUERY_POOL_GENERATION:
            _release_query_connection(con, generation=generation, discard=True, leased=False)
            return _acquire_query_connection()
        _record_pool_acquire(time.monotonic() - started)
        return con, generation
    except queue.Empty:
        with _QUERY_POOL_LOCK:
            if _QUERY_POOL_CREATED < _QUERY_POOL_SIZE:
                _QUERY_POOL_CREATED += 1
                try:
                    result = (_build_thread_connection(), _QUERY_POOL_GENERATION)
                    _record_pool_acquire(time.monotonic() - started)
                    return result
                except Exception:
                    _QUERY_POOL_CREATED -= 1
                    raise
        try:
            result = _QUERY_POOL.get(timeout=30)
        except queue.Empty:
            with _QUERY_POOL_ACTIVITY_LOCK:
                _QUERY_POOL_ACTIVITY["timeouts"] += 1
            raise
        _record_pool_acquire(time.monotonic() - started)
        return result


def _release_query_connection(
    con, *, generation: int, discard: bool = False, leased: bool = True,
) -> None:
    global _QUERY_POOL_CREATED
    effective_discard = discard or generation != _QUERY_POOL_GENERATION
    if leased:
        _record_pool_release(discard=effective_discard)
    if effective_discard:
        try:
            con.close()
        except Exception:
            pass
        with _QUERY_POOL_LOCK:
            _QUERY_POOL_CREATED = max(0, _QUERY_POOL_CREATED - 1)
        return
    _QUERY_POOL.put((con, generation))


def _build_thread_connection():
    """Create and fully configure a DuckDB connection for the current thread."""
    return build_guarded_connection(database=":memory:")


def _get_thread_connection():
    """Return this thread's DuckDB connection, creating it on first use."""
    con = getattr(_thread_state, "con", None)
    generation = getattr(_thread_state, "generation", -1)
    if con is None or generation != _THREAD_CONNECTION_GENERATION:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
        con = _build_thread_connection()
        _thread_state.con = con
        _thread_state.generation = _THREAD_CONNECTION_GENERATION
    return con


def _drop_thread_connection() -> None:
    """Drop the current thread's connection; the next query rebuilds.

    Called when an exception suggests the connection may be in a bad state
    (e.g. transport-level error, broken pipe). Cursor-style query errors
    are rare to non-existent here because we use the connection directly.
    """
    con = getattr(_thread_state, "con", None)
    if con is not None:
        try:
            con.close()
        except Exception:
            pass
        _thread_state.con = None
        _thread_state.generation = -1


def reset_thread_connection_pool() -> int:
    """Invalidate all pooled thread-local DuckDB connections.

    The current thread drops immediately. Other worker threads lazily rebuild
    their connection on the next query when they observe the bumped generation.
    """
    global _THREAD_CONNECTION_GENERATION, _QUERY_POOL_CREATED, _QUERY_POOL_GENERATION
    with _THREAD_CONNECTION_GENERATION_LOCK:
        _THREAD_CONNECTION_GENERATION += 1
        generation = _THREAD_CONNECTION_GENERATION
    _drop_thread_connection()
    with _QUERY_POOL_LOCK:
        _QUERY_POOL_GENERATION += 1
        drained = 0
        while True:
            try:
                pooled, _ = _QUERY_POOL.get_nowait()
            except queue.Empty:
                break
            drained += 1
            try:
                pooled.close()
            except Exception:
                pass
        _QUERY_POOL_CREATED = max(0, _QUERY_POOL_CREATED - drained)
    return generation


def _make_connection():
    """Backward-compatible close-safe accessor used by debug endpoints."""
    if duckdb is None:
        return None
    return lease_query_connection()


# ---------------------------------------------------------------------------
# Core query runners
# ---------------------------------------------------------------------------

def _looks_like_connection_error(exc: BaseException) -> bool:
    """Heuristic: distinguish transport-level errors from query-level errors.

    Query errors (bad SQL, missing column, type mismatch) leave the
    connection healthy and we keep it pooled. Transport errors (broken
    socket, R2 reachability problems) suggest the connection state is
    suspect; drop and rebuild on the next call.
    """
    name = type(exc).__name__
    if name in {"IOException", "HTTPException", "ConnectionException"}:
        return True
    msg = str(exc).lower()
    return any(s in msg for s in ("broken pipe", "connection reset", "connection refused"))


class _QueryConnectionLease:
    """Close-compatible lease over the shared local/cloud query pools."""

    def __init__(self, connection, generation: int | None) -> None:
        self._connection = connection
        self._generation = generation
        self._discard = False
        self._closed = False

    def execute(self, *args, **kwargs):
        try:
            return self._connection.execute(*args, **kwargs)
        except Exception as exc:
            if _looks_like_connection_error(exc):
                self._discard = True
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._generation is not None:
            _release_query_connection(
                self._connection, generation=self._generation, discard=self._discard,
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, _traceback) -> None:
        if exc is not None and _looks_like_connection_error(exc):
            self._discard = True
        self.close()


def lease_query_connection() -> _QueryConnectionLease:
    """Lease a configured connection for a multi-statement bounded query."""
    if duckdb is None:
        raise RuntimeError("DuckDB is unavailable")
    if not is_cloud_mode():
        return _QueryConnectionLease(_get_thread_connection(), None)
    connection, generation = _acquire_query_connection()
    return _QueryConnectionLease(connection, generation)


def _execute_df(con, sql: str, params: list, *, raw_geoparquet: bool = False) -> pd.DataFrame:
    if not raw_geoparquet:
        return con.execute(sql, params).df()
    con.execute("SET enable_geoparquet_conversion=false")
    try:
        return con.execute(sql, params).df()
    finally:
        con.execute("SET enable_geoparquet_conversion=true")


def _execute_rows(con, sql: str, params: list, *, raw_geoparquet: bool = False) -> list[tuple]:
    if not raw_geoparquet:
        return con.execute(sql, params).fetchall()
    con.execute("SET enable_geoparquet_conversion=false")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.execute("SET enable_geoparquet_conversion=true")


def run_df(sql: str, params: list, *, raw_geoparquet: bool = False) -> pd.DataFrame:
    if duckdb is None:
        return pd.DataFrame()
    if not is_cloud_mode():
        con = _get_thread_connection()
        return _execute_df(con, sql, params, raw_geoparquet=raw_geoparquet)
    con, generation = _acquire_query_connection()
    discard = False
    try:
        return _execute_df(con, sql, params, raw_geoparquet=raw_geoparquet)
    except Exception as exc:
        if _looks_like_connection_error(exc):
            discard = True
        raise
    finally:
        _release_query_connection(con, generation=generation, discard=discard)


def run_rows(sql: str, params: list, *, raw_geoparquet: bool = False) -> list[tuple]:
    if duckdb is None:
        return []
    if not is_cloud_mode():
        con = _get_thread_connection()
        return _execute_rows(con, sql, params, raw_geoparquet=raw_geoparquet)
    con, generation = _acquire_query_connection()
    discard = False
    try:
        return _execute_rows(con, sql, params, raw_geoparquet=raw_geoparquet)
    except Exception as exc:
        if _looks_like_connection_error(exc):
            discard = True
        raise
    finally:
        _release_query_connection(con, generation=generation, discard=discard)


def _normalize_ts_for_duckdb(val: str | None) -> str | None:
    """Convert a ms-epoch timestamp string to an ISO datetime string for DuckDB.

    DuckDB's CAST(? AS TIMESTAMP) rejects raw millisecond integers like
    '1735718400000'. Detect them (>10 digits, all numeric) and convert to
    'YYYY-MM-DD HH:MM:SS' in UTC which DuckDB handles fine.
    """
    if val is None:
        return None
    s = str(val).strip()
    if s.lstrip("-").isdigit() and len(s) > 10:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(s) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return val


def parquet_columns(parquet_path: Path, *, raw_geoparquet: bool = False) -> set[str]:
    if duckdb is None:
        return set()
    cloud_mode = is_cloud_mode()
    if not cloud_mode:
        if not parquet_path.exists():
            return set()
        try:
            stat = parquet_path.stat()
            signature = (int(stat.st_mtime_ns), int(stat.st_size))
            cache_key = f"{parquet_path.resolve()}|raw={int(raw_geoparquet)}"
        except OSError:
            return set()
        with _PARQUET_COLUMNS_CACHE_LOCK:
            cached = _PARQUET_COLUMNS_CACHE.get(cache_key)
            if cached and cached[0] == signature:
                return set(cached[1])
    else:
        cache_key = "|".join((
            os.environ.get("S3_BUCKET", ""),
            os.environ.get("S3_PREFIX", ""),
            os.environ.get("S3_PUBLISHED_PREFIX", ""),
            str(parquet_path),
            f"raw={int(raw_geoparquet)}",
        ))
        try:
            cache_seconds = max(1, int(os.environ.get("PARQUET_SCHEMA_CACHE_SECONDS", "300")))
        except ValueError:
            cache_seconds = 300
        now = time.monotonic()
        with _PARQUET_COLUMNS_CACHE_LOCK:
            cached = _PARQUET_CLOUD_COLUMNS_CACHE.get(cache_key)
            if cached and cached[0] > now:
                return set(cached[1])
    uri = path_to_uri(parquet_path)
    rows = run_rows(
        "DESCRIBE SELECT * FROM read_parquet(?)", [uri], raw_geoparquet=raw_geoparquet
    )
    columns = {row[0] for row in rows}
    with _PARQUET_COLUMNS_CACHE_LOCK:
        if not cloud_mode:
            _PARQUET_COLUMNS_CACHE[cache_key] = (signature, set(columns))
        else:
            _PARQUET_CLOUD_COLUMNS_CACHE[cache_key] = (now + cache_seconds, set(columns))
    return columns


def clear_parquet_metadata_cache() -> None:
    """Discard cached local signatures and cloud schemas after an activation change."""
    with _PARQUET_COLUMNS_CACHE_LOCK:
        _PARQUET_COLUMNS_CACHE.clear()
        _PARQUET_CLOUD_COLUMNS_CACHE.clear()


def quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_event_parquet_path(source_dir: Path, event_file_key: str = "events") -> tuple[Path, dict]:
    meta_path = source_dir / "metadata.json"
    with open(meta_path, encoding="utf-8") as f:
        metadata = json.load(f)

    files_section = metadata.get("files")
    files_info = files_section if isinstance(files_section, dict) else {}
    file_info = files_info.get(event_file_key)
    if not isinstance(file_info, dict):
        file_info = None

    if not file_info:
        fallback_names = [
            f"{event_file_key}.parquet",
            "events.parquet",
            "fires.parquet",
            "positions.parquet",
            "storms.parquet",
        ]
        for name in fallback_names:
            candidate = source_dir / name
            if is_cloud_mode() or candidate.exists():
                return candidate, metadata
        if not is_cloud_mode():
            parquet_candidates = sorted(source_dir.glob("*.parquet"))
            for candidate in parquet_candidates:
                if candidate.name in ("all_countries.parquet", "all_regions.parquet"):
                    continue
                return candidate, metadata
        raise ValueError(f"No event file '{event_file_key}' found in {source_dir}")

    filename = file_info.get("name") or file_info.get("filename")
    if not filename:
        raise ValueError(f"No filename specified for '{event_file_key}' in {source_dir}")

    parquet_path = source_dir / filename
    if not is_cloud_mode() and not parquet_path.exists():
        raise ValueError(f"Event file not found: {parquet_path}")
    return parquet_path, metadata


# ---------------------------------------------------------------------------
# Query functions (all accept Path objects; path_to_uri is applied internally)
# ---------------------------------------------------------------------------

def select_distinct_event_ids(areas_path: Path, affected_loc_id: str, exact: bool = False, limit: int | None = None) -> list[str]:
    if duckdb is None or not parquet_available(areas_path):
        return []
    uri = path_to_uri(areas_path)
    comparator = "=" if exact else "LIKE"
    if exact:
        value = affected_loc_id
    else:
        escaped = (
            str(affected_loc_id)
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        value = f"{escaped}%"
    sql = (
        "SELECT DISTINCT event_id "
        "FROM read_parquet(?) "
        f"WHERE affected_loc_id {comparator} ? "
        "ORDER BY event_id"
    )
    if not exact:
        sql = sql.replace("ORDER BY", "ESCAPE '\\' ORDER BY", 1)
    params: list = [uri, value]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = run_rows(sql, params)
    return [row[0] for row in rows if row and row[0] is not None]


def select_event_ids_by_regions(parquet_path: Path, regions: Iterable[str]) -> list[str]:
    if duckdb is None or not parquet_available(parquet_path):
        return []
    uri = path_to_uri(parquet_path)
    regions = list(regions)
    sql = "SELECT event_id FROM read_parquet(?)"
    params: list = [uri]
    if regions:
        prefixes = [f"{r}%" for r in regions]
        exacts = list(regions)
        like_parts = ['"loc_id" LIKE ?' for _ in prefixes]
        eq_parts = ['"loc_id" = ?' for _ in exacts]
        sql += " WHERE " + " OR ".join(like_parts + eq_parts)
        params.extend(prefixes + exacts)
    rows = run_rows(sql, params)
    return [row[0] for row in rows if row and row[0] is not None]


def select_filtered_event_rows(
    parquet_path: Path,
    *,
    columns: Iterable[str] | None = None,
    year: int | None = None,
    start: str | None = None,
    end: str | None = None,
    min_value_filters: dict | None = None,
    exact_filters: dict | None = None,
    like_filters: dict | None = None,
    in_filters: dict | None = None,
    order_by_desc: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    if duckdb is None or not parquet_available(parquet_path):
        return pd.DataFrame()

    uri = path_to_uri(parquet_path)
    available_cols = parquet_columns(parquet_path)
    where: list[str] = []
    params: list = [uri]

    if year is not None and "year" in available_cols:
        where.append('"year" = ?')
        params.append(year)
    if start is not None and "timestamp" in available_cols:
        where.append('"timestamp" >= CAST(? AS TIMESTAMP)')
        params.append(_normalize_ts_for_duckdb(start))
    if end is not None and "timestamp" in available_cols:
        where.append('"timestamp" <= CAST(? AS TIMESTAMP)')
        params.append(_normalize_ts_for_duckdb(end))
    if (start is not None or end is not None) and "timestamp" not in available_cols:
        warning_key = (str(parquet_path), tuple(sorted(available_cols)))
        if warning_key not in _MISSING_TIME_FILTER_WARNING_KEYS:
            _MISSING_TIME_FILTER_WARNING_KEYS.add(warning_key)
            logger.warning(
                "select_filtered_event_rows ignored start/end for %s because no timestamp column exists. Available time-like columns: %s",
                parquet_path,
                [col for col in ("year", "start_date", "end_date", "date", "datetime") if col in available_cols],
            )

    for col, value in (min_value_filters or {}).items():
        if col in available_cols and value is not None:
            where.append(f"{quote_ident(col)} >= ?")
            params.append(value)

    for col, value in (exact_filters or {}).items():
        if col in available_cols and value is not None:
            where.append(f"{quote_ident(col)} = ?")
            params.append(value)

    for col, value in (like_filters or {}).items():
        if col in available_cols and value is not None:
            where.append(f"{quote_ident(col)} LIKE ?")
            params.append(value)

    for col, values in (in_filters or {}).items():
        values = list(values or [])
        if col in available_cols and values:
            placeholders = ", ".join("?" for _ in values)
            where.append(f"{quote_ident(col)} IN ({placeholders})")
            params.extend(values)

    # Projection is optional for backwards compatibility, but callers reading
    # large event artifacts should name the fields they actually need. Keep
    # predicate/order fields in the projection so existing post-processing
    # remains valid even when a caller only requests a narrow payload.
    if columns is None:
        select_expr = "*"
    else:
        required = [
            *(str(col) for col in columns),
            *(str(col) for col in (exact_filters or {})),
            *(str(col) for col in (in_filters or {})),
            *(str(col) for col in (like_filters or {})),
            *(str(col) for col in (min_value_filters or {})),
        ]
        if year is not None:
            required.append("year")
        if start is not None or end is not None:
            required.append("timestamp")
        if order_by_desc:
            required.append(order_by_desc)
        selected = list(dict.fromkeys(col for col in required if col in available_cols))
        select_expr = ", ".join(quote_ident(col) for col in selected) or "*"
    sql = f"SELECT {select_expr} FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if order_by_desc and order_by_desc in available_cols:
        sql += f" ORDER BY {quote_ident(order_by_desc)} DESC NULLS LAST"
    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(limit)

    return run_df(sql, params)


def select_rows_by_exact_value(
    parquet_path: Path,
    column: str,
    value,
    *,
    columns: Iterable[str] | None = None,
    limit: int | None = None,
    order_by: str | None = None,
) -> pd.DataFrame:
    if duckdb is None or not parquet_available(parquet_path):
        return pd.DataFrame()

    uri = path_to_uri(parquet_path)
    available_cols = parquet_columns(parquet_path)
    if column not in available_cols:
        return pd.DataFrame()

    if columns is None:
        select_expr = "*"
    else:
        selected = list(dict.fromkeys(
            [str(value) for value in columns] + [column] + ([order_by] if order_by else [])
        ))
        selected = [name for name in selected if name in available_cols]
        select_expr = ", ".join(quote_ident(name) for name in selected) or "*"
    sql = f"SELECT {select_expr} FROM read_parquet(?) WHERE {quote_ident(column)} = ?"
    params: list = [uri, value]
    if order_by and order_by in available_cols:
        sql += f" ORDER BY {quote_ident(order_by)} ASC NULLS LAST"
    if limit is not None and int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    return run_df(sql, params)


def select_rows(
    parquet_path: Path,
    *,
    columns: Iterable[str] | None = None,
    exact_filters: dict | None = None,
    in_filters: dict | None = None,
    compare_filters: list[tuple[str, str, object]] | None = None,
    starts_with_filters: dict | None = None,
    order_by: str | None = None,
    limit: int | None = None,
    raw_geoparquet: bool = False,
) -> pd.DataFrame:
    if duckdb is None or not parquet_available(parquet_path):
        return pd.DataFrame()

    uri = path_to_uri(parquet_path)
    available_cols = parquet_columns(parquet_path, raw_geoparquet=raw_geoparquet)
    selected = [c for c in (columns or []) if c in available_cols]
    select_expr = ", ".join(quote_ident(c) for c in selected) if selected else "*"

    requested_filter_columns = {
        *(exact_filters or {}).keys(),
        *(in_filters or {}).keys(),
        *(starts_with_filters or {}).keys(),
        *(column for column, _operator, _value in (compare_filters or [])),
    }
    missing_filter_columns = sorted(requested_filter_columns - available_cols)
    if missing_filter_columns:
        raise ValueError(
            f"Parquet filter column(s) are absent from {parquet_path}: "
            + ", ".join(missing_filter_columns)
        )

    where: list[str] = []
    params: list = [uri]

    for col, value in (exact_filters or {}).items():
        if col in available_cols and value is not None:
            where.append(f"{quote_ident(col)} = ?")
            params.append(value)

    for col, values in (in_filters or {}).items():
        values = [v for v in (values or []) if v is not None]
        if not values:
            return pd.DataFrame(columns=selected or list(available_cols))
        placeholders = ", ".join("?" for _ in values)
        where.append(f"{quote_ident(col)} IN ({placeholders})")
        params.extend(values)

    for col, op, value in (compare_filters or []):
        if col not in available_cols or value is None:
            continue
        if op not in {"=", "!=", ">", ">=", "<", "<="}:
            continue
        where.append(f"{quote_ident(col)} {op} ?")
        params.append(value)

    for col, prefix in (starts_with_filters or {}).items():
        if col in available_cols and prefix is not None:
            where.append(f"starts_with({quote_ident(col)}, ?)")
            params.append(prefix)

    sql = f"SELECT {select_expr} FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    if order_by and order_by in available_cols:
        sql += f" ORDER BY {quote_ident(order_by)} ASC NULLS LAST"
    if limit is not None and int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    return run_df(sql, params, raw_geoparquet=raw_geoparquet)


def count_rows(
    parquet_path: Path,
    *,
    exact_filters: dict | None = None,
    in_filters: dict | None = None,
    compare_filters: list[tuple[str, str, object]] | None = None,
    starts_with_filters: dict | None = None,
) -> int:
    if duckdb is None or not parquet_available(parquet_path):
        return 0

    uri = path_to_uri(parquet_path)
    available_cols = parquet_columns(parquet_path)
    where: list[str] = []
    params: list = [uri]

    for col, value in (exact_filters or {}).items():
        if col in available_cols and value is not None:
            where.append(f"{quote_ident(col)} = ?")
            params.append(value)

    for col, values in (in_filters or {}).items():
        values = [v for v in (values or []) if v is not None]
        if col in available_cols and values:
            placeholders = ", ".join("?" for _ in values)
            where.append(f"{quote_ident(col)} IN ({placeholders})")
            params.extend(values)

    for col, op, value in (compare_filters or []):
        if col not in available_cols or value is None:
            continue
        if op not in {"=", "!=", ">", ">=", "<", "<="}:
            continue
        where.append(f"{quote_ident(col)} {op} ?")
        params.append(value)

    for col, prefix in (starts_with_filters or {}).items():
        if col in available_cols and prefix is not None:
            where.append(f"starts_with({quote_ident(col)}, ?)")
            params.append(prefix)

    sql = "SELECT COUNT(*) FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = run_rows(sql, params)
    if not rows:
        return 0
    try:
        return int(rows[0][0] or 0)
    except Exception:
        return 0


def select_linked_values(
    links_path: Path,
    *,
    source_column: str,
    source_value: str,
    target_column: str,
    link_type: str | None = None,
) -> list[str]:
    if duckdb is None or not parquet_available(links_path):
        return []

    uri = path_to_uri(links_path)
    available_cols = parquet_columns(links_path)
    if source_column not in available_cols or target_column not in available_cols:
        return []

    sql = (
        f"SELECT DISTINCT {quote_ident(target_column)} "
        f"FROM read_parquet(?) "
        f"WHERE {quote_ident(source_column)} = ?"
    )
    params: list = [uri, source_value]
    if link_type is not None and "link_type" in available_cols:
        sql += ' AND "link_type" = ?'
        params.append(link_type)
    sql += f" ORDER BY {quote_ident(target_column)}"
    rows = run_rows(sql, params)
    return [row[0] for row in rows if row and row[0] is not None]


def select_linked_loc_ids(
    links_path: Path,
    *,
    source_column: str,
    source_loc_id: str,
    target_column: str,
    link_type: str | None = None,
) -> list[str]:
    return select_linked_values(
        links_path,
        source_column=source_column,
        source_value=source_loc_id,
        target_column=target_column,
        link_type=link_type,
    )


def select_peak_positions_by_storm_ids(positions_path: Path, storm_ids: Iterable[str]) -> pd.DataFrame:
    if duckdb is None or not parquet_available(positions_path):
        return pd.DataFrame()

    storm_ids = [s for s in storm_ids if s]
    if not storm_ids:
        return pd.DataFrame()

    df = select_filtered_event_rows(
        positions_path,
        columns=["storm_id", "timestamp", "latitude", "longitude", "wind_kt"],
        in_filters={"storm_id": storm_ids},
    )
    if df.empty:
        return df

    df = df.dropna(subset=["latitude", "longitude"])
    if df.empty or "storm_id" not in df.columns:
        return pd.DataFrame()

    if "wind_kt" in df.columns:
        df["wind_sort"] = df["wind_kt"].fillna(-1)
        idx = df.groupby("storm_id")["wind_sort"].idxmax()
        df = df.loc[idx].drop(columns=["wind_sort"], errors="ignore")
    else:
        df = df.sort_values(["storm_id", "timestamp"] if "timestamp" in df.columns else ["storm_id"])
        df = df.groupby("storm_id").head(1)

    return df


def select_filtered_partitioned_rows(
    parquet_paths: Iterable[Path],
    *,
    columns: Iterable[str] | None = None,
    year: int | None = None,
    start: str | None = None,
    end: str | None = None,
    min_value_filters: dict | None = None,
    exact_filters: dict | None = None,
    like_filters: dict | None = None,
    in_filters: dict | None = None,
) -> pd.DataFrame:
    if duckdb is None:
        return pd.DataFrame()

    if is_cloud_mode():
        # In S3 mode, convert paths to s3:// URIs - skip local exists check
        uris = [path_to_uri(Path(p)) for p in parquet_paths]
    else:
        uris = [str(Path(p)) for p in parquet_paths if Path(p).exists()]

    if not uris:
        return pd.DataFrame()

    # Get columns from first reachable file to build WHERE clause
    available_cols: set[str] = set()
    if is_cloud_mode():
        for uri in uris:
            try:
                rows = run_rows("DESCRIBE SELECT * FROM read_parquet(?)", [uri])
                available_cols = {row[0] for row in rows}
                break
            except Exception:
                continue
    else:
        available_cols = parquet_columns(Path(uris[0]))

    # Resolve the shared schema before building the projection. Previously
    # ``available_cols`` was referenced above its assignment whenever callers
    # supplied ``columns``, so partitioned datasets could only be read with
    # SELECT * in practice.
    if columns is None:
        select_expr = "*"
    else:
        required = [
            *(str(col) for col in columns),
            *(str(col) for col in (exact_filters or {})),
            *(str(col) for col in (in_filters or {})),
            *(str(col) for col in (like_filters or {})),
            *(str(col) for col in (min_value_filters or {})),
        ]
        if year is not None:
            required.append("year")
        if start is not None or end is not None:
            required.append("timestamp")
        selected = list(dict.fromkeys(col for col in required if col in available_cols))
        select_expr = ", ".join(quote_ident(col) for col in selected) or "*"

    # Build WHERE clause and filter params (not including the URI placeholder)
    where: list[str] = []
    filter_params: list = []

    if year is not None and "year" in available_cols:
        where.append('"year" = ?')
        filter_params.append(year)
    if start is not None and "timestamp" in available_cols:
        where.append('"timestamp" >= CAST(? AS TIMESTAMP)')
        filter_params.append(_normalize_ts_for_duckdb(start))
    if end is not None and "timestamp" in available_cols:
        where.append('"timestamp" <= CAST(? AS TIMESTAMP)')
        filter_params.append(_normalize_ts_for_duckdb(end))

    for col, value in (min_value_filters or {}).items():
        if col in available_cols and value is not None:
            where.append(f"{quote_ident(col)} >= ?")
            filter_params.append(value)

    for col, value in (exact_filters or {}).items():
        if col in available_cols and value is not None:
            where.append(f"{quote_ident(col)} = ?")
            filter_params.append(value)

    for col, value in (like_filters or {}).items():
        if col in available_cols and value is not None:
            where.append(f"{quote_ident(col)} LIKE ?")
            filter_params.append(value)

    for col, values in (in_filters or {}).items():
        values = list(values or [])
        if col in available_cols and values:
            placeholders_w = ", ".join("?" for _ in values)
            where.append(f"{quote_ident(col)} IN ({placeholders_w})")
            filter_params.extend(values)

    where_clause = " WHERE " + " AND ".join(where) if where else ""

    if is_cloud_mode():
        # Query each file individually so missing S3 files are silently skipped
        dfs = []
        for uri in uris:
            try:
                df = run_df(f"SELECT {select_expr} FROM read_parquet(?){where_clause}", [uri] + filter_params)
                if not df.empty:
                    dfs.append(df)
            except Exception as e:
                err = str(e)
                if "No files found" in err or "404" in err or "HTTP" in err:
                    continue
                raise
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    else:
        placeholders = ", ".join("?" for _ in uris)
        sql = f"SELECT {select_expr} FROM read_parquet([{placeholders}]){where_clause}"
        return run_df(sql, list(uris) + filter_params)


def select_columns_from_parquet(parquet_path: Path, columns: Iterable[str]) -> pd.DataFrame:
    if duckdb is None or not parquet_available(parquet_path):
        return pd.DataFrame()

    uri = path_to_uri(parquet_path)
    available_cols = parquet_columns(parquet_path)
    selected = [c for c in columns if c in available_cols]
    if not selected:
        return pd.DataFrame()

    sql = "SELECT " + ", ".join(quote_ident(c) for c in selected) + " FROM read_parquet(?)"
    return run_df(sql, [uri])


# ---------------------------------------------------------------------------
# In-memory TTL response cache
# Caches DataFrames from slow default GeoJSON queries so cold-start fetches
# from R2 do not block every incoming request.
# ---------------------------------------------------------------------------

_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[pd.DataFrame, float]] = {}  # key -> (df, expires_at)

DEFAULT_CACHE_TTL = int(os.environ.get("DUCKDB_CACHE_TTL", "300"))  # seconds

def get_default_preload_year_window(relative_years: int = 10) -> tuple[int, int]:
    current_year = datetime.now(timezone.utc).year
    start_year = max(1900, current_year - max(1, relative_years) + 1)
    return start_year, current_year


def get_default_preload_range_bounds(relative_years: int = 10) -> tuple[datetime, datetime, datetime, datetime]:
    start_year, end_year = get_default_preload_year_window(relative_years)
    return (
        datetime(start_year - 1, 12, 30, 0, 0, 0, tzinfo=timezone.utc),
        datetime(start_year, 1, 2, 23, 59, 59, tzinfo=timezone.utc),
        datetime(end_year, 12, 30, 0, 0, 0, tzinfo=timezone.utc),
        datetime(end_year + 1, 1, 2, 23, 59, 59, tzinfo=timezone.utc),
    )


def cache_get(key: str) -> pd.DataFrame | None:
    """Return cached DataFrame if still valid, else None.

    Non-permanent entries get a sliding TTL: each hit extends expiry by DEFAULT_CACHE_TTL.
    Permanent entries (expires_at == inf) are never expired or extended.
    """
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        df, expires_at = entry
        if now > expires_at:
            _CACHE.pop(key, None)
            return None
        # Slide expiry window on access for non-permanent entries
        if expires_at != float("inf"):
            _CACHE[key] = (df, now + DEFAULT_CACHE_TTL)
    return df


def cache_set(key: str, df: pd.DataFrame, ttl: int | None = None, permanent: bool = False) -> None:
    """Store a DataFrame in the cache.

    permanent=True: entry never expires (used for prewarmed base data).
    ttl: seconds until expiry; defaults to DEFAULT_CACHE_TTL if not permanent.
    """
    expires_at = float("inf") if permanent else time.monotonic() + (ttl if ttl is not None else DEFAULT_CACHE_TTL)
    with _CACHE_LOCK:
        _CACHE[key] = (df, expires_at)


def cache_clear(prefix: str | None = None) -> None:
    """Clear all cache entries, or only those whose key starts with prefix."""
    with _CACHE_LOCK:
        if prefix is None:
            _CACHE.clear()
        else:
            for k in list(_CACHE):
                if k.startswith(prefix):
                    del _CACHE[k]


def make_cache_key(source: str, **params) -> str:
    """Build a cache key from a source name and request params.

    Only non-None values are included. Sorted so key is stable regardless of
    argument order. Use the same helper in both the pre-warmer and route
    handlers so keys always match.

    Example:
        make_cache_key("floods", year=2021, include_geometry=True)
        -> "floods:include_geometry:True:year:2021"
    """
    relevant = {k: v for k, v in params.items() if v is not None and v is not False}

    def cache_value(value: object) -> str:
        # FastAPI parses query thresholds as floats while metadata/prewarm
        # defaults are often authored as integers. They represent the same
        # request and must address the same cache entry (500 == 500.0).
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    parts = [source] + [f"{key}:{cache_value(value)}" for key, value in sorted(relevant.items())]
    return ":".join(parts)


def _parse_cache_range_ts(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        s = str(value).strip()
        if s.lstrip("-").isdigit():
            return datetime.fromtimestamp(int(s) / 1000.0, tz=timezone.utc)
        dt = pd.to_datetime(s, utc=True)
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def is_default_preload_range(start: str | None, end: str | None) -> bool:
    """Return True for the frontend's default multi-year disaster preload window.

    Allows a little slack around midnight boundaries so browser timezone
    differences still map to the same warm cache bucket.
    """
    start_dt = _parse_cache_range_ts(start)
    end_dt = _parse_cache_range_ts(end)
    if start_dt is None or end_dt is None:
        return False
    preload_start_lower, preload_start_upper, preload_end_lower, preload_end_upper = get_default_preload_range_bounds()
    return preload_start_lower <= start_dt <= preload_start_upper and preload_end_lower <= end_dt <= preload_end_upper


def make_preload_cache_key(source: str, **params) -> str:
    """Canonical cache key for the frontend's rolling disaster preload workflow.

    The slice is permanent for the lifetime of a runtime process, so its key
    includes the computed UTC-year window.  A process that survives New Year
    therefore builds a fresh slice instead of treating last year's ten-year
    DataFrame as coverage for the new rolling window.
    """
    start_year, end_year = get_default_preload_year_window(relative_years=10)
    return make_cache_key(
        source,
        preset="preload_default_10_years",
        window_start_year=start_year,
        window_end_year=end_year,
        **params,
    )


def select_compatible_preload_slice(
    cache_key: str,
    *,
    start: str | None = None,
    end: str | None = None,
    time_column: str = "timestamp",
) -> pd.DataFrame | None:
    """Return a narrower time slice from a compatible held preload DataFrame.

    Callers must construct ``cache_key`` from the exact compatible source and
    filter profile. This helper deliberately knows only time containment: it
    must never treat a cache built with restrictive predicates as a response to
    a broader query. ``None`` means no compatible held DataFrame is available;
    an empty DataFrame means the compatible cache proved the requested interval
    has no rows.
    """
    cached = cache_get(cache_key)
    if cached is None:
        return None
    if start is None and end is None:
        return cached.copy()
    if time_column not in cached.columns:
        return None

    try:
        timestamps = pd.to_datetime(cached[time_column], errors="coerce", utc=True)

        def parse_bound(value: str | None):
            if value is None:
                return None
            raw = str(value).strip()
            if raw.lstrip("-").isdigit() and len(raw) > 10:
                return pd.to_datetime(int(raw), unit="ms", utc=True)
            return pd.to_datetime(raw, utc=True)

        start_ts = parse_bound(start)
        end_ts = parse_bound(end)
        mask = timestamps.notna()
        if start_ts is not None:
            mask &= timestamps >= start_ts
        if end_ts is not None:
            mask &= timestamps <= end_ts
        return cached.loc[mask].copy()
    except Exception as exc:
        logger.warning("Could not slice compatible preload cache %s: %s", cache_key, exc)
        return None


def select_filtered_event_rows_cached(
    parquet_path: Path,
    cache_key: str,
    ttl: int | None = None,
    permanent: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Like select_filtered_event_rows but checks/stores results in the TTL cache.

    Use this for default (no user-specific filters) queries to avoid cold R2
    fetches on every request. cached DataFrame is returned for cache_ttl seconds.
    """
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    df = select_filtered_event_rows(parquet_path, **kwargs)
    if not df.empty:
        cache_set(cache_key, df, ttl, permanent=permanent)
    return df


# ---------------------------------------------------------------------------
# Startup pre-warmer
# Runs the expensive default queries for each disaster source so the DuckDB
# http metadata cache and our in-memory DataFrame cache are both populated
# before the first user request arrives.
# ---------------------------------------------------------------------------

def _prewarm_source(source_id: str, parquet_path: Path, min_year_filter: dict | None) -> None:
    """Run the default query for one source and populate the cache."""
    import logging
    log = logging.getLogger(__name__)
    if not parquet_available(parquet_path):
        return
    cache_key = f"{source_id}:default:{min_year_filter}"
    if cache_get(cache_key) is not None:
        return  # already warm
    try:
        t0 = time.monotonic()
        df = select_filtered_event_rows(
            parquet_path,
            min_value_filters=min_year_filter,
        )
        elapsed = time.monotonic() - t0
        if not df.empty:
            cache_set(cache_key, df)
        log.info("prewarm %s: %d rows in %.1fs", source_id, len(df), elapsed)
    except Exception as exc:
        log.warning("prewarm %s failed: %s", source_id, exc)


def prewarm_disaster_sources(global_dir: Path) -> None:
    """Pre-warm the default queries for all disaster sources.

    Call this in a background thread from the app lifespan. It populates both
    the DuckDB http metadata cache and our in-memory DataFrame cache so that
    the first user request does not incur cold R2 latency.

    The rolling ten-year Explore window is pre-warmed with the exact filter
    params that the frontend overlay-controller.js uses (min_magnitude,
    min_area_km2, etc.) so that the first preset load hits the cache.
    """
    if not is_cloud_mode():
        return  # pre-warming only needed for R2 mode

    import logging
    log = logging.getLogger(__name__)

    # Prewarm the same relative-year window the Explore preset uses.
    preload_start_year, preload_end_year = get_default_preload_year_window(relative_years=10)
    preload_start = f"{preload_start_year:04d}-01-01 00:00:00"
    preload_end = f"{preload_end_year:04d}-12-31 23:59:59"

    earthquake_columns = (
        "event_id", "magnitude", "depth_km", "felt_radius_km", "damage_radius_km",
        "place", "timestamp", "year", "loc_id", "latitude", "longitude",
        "mainshock_id", "sequence_id",
    )
    tornado_columns = (
        "event_id", "tornado_scale", "tornado_length_mi", "tornado_width_yd",
        "felt_radius_km", "damage_radius_km", "timestamp", "time", "year",
        "deaths_direct", "injuries_direct", "damage_property", "location", "loc_id",
        "latitude", "longitude", "end_latitude", "end_longitude", "sequence_id",
        "sequence_position", "sequence_count", "display_start_timestamp",
        "display_end_timestamp", "display_animation_kind",
    )
    hurricane_storm_columns = (
        "storm_id", "name", "year", "basin", "max_wind_kt", "min_pressure_mb",
        "max_category", "num_positions", "start_date", "end_date", "made_landfall",
        "loc_id", "display_start_timestamp", "display_end_timestamp",
        "display_animation_kind",
    )
    hurricane_position_columns = ("storm_id", "timestamp", "latitude", "longitude")
    wildfire_columns = (
        "event_id", "timestamp", "latitude", "longitude", "area_km2", "burned_acres",
        "duration_days", "source", "has_progression", "loc_id", "parent_loc_id",
        "sibling_level", "iso3", "loc_confidence", "land_cover",
        "display_start_timestamp", "display_end_timestamp", "display_animation_kind",
    )

    # --- earthquakes (min_magnitude 5.5 from overlay-controller.js) ----------
    eq_path = global_dir / "disasters/earthquakes/events.parquet"
    preload_ck = make_preload_cache_key("earthquakes", min_magnitude=5.5)
    if cache_get(preload_ck) is None:
        try:
            t0 = time.monotonic()
            df = select_filtered_event_rows(
                eq_path,
                columns=earthquake_columns,
                start=preload_start,
                end=preload_end,
                min_value_filters={"magnitude": 5.5},
            )
            if not df.empty:
                cache_set(preload_ck, df, permanent=True)
            log.info("prewarm earthquakes preload-range: %d rows in %.1fs", len(df), time.monotonic() - t0)
        except Exception as exc:
            log.warning("prewarm earthquakes preload-range failed: %s", exc)

    # --- tsunamis (Explore default is every recorded event) ------------------
    ts_path = global_dir / "disasters/tsunamis/events.parquet"
    # This must use the same empty filter signature as OVERLAY_ENDPOINTS.
    # Water height/runup is an analysis metric, not a map-visibility gate; the
    # linked runup table is still fetched only for a selected event.
    preload_ck = make_preload_cache_key("tsunamis")
    if cache_get(preload_ck) is None:
        try:
            t0 = time.monotonic()
            df = select_filtered_event_rows(
                ts_path,
                start=preload_start,
                end=preload_end,
            )
            if not df.empty:
                cache_set(preload_ck, df, permanent=True)
            log.info("prewarm tsunamis preload-range: %d rows in %.1fs", len(df), time.monotonic() - t0)
        except Exception as exc:
            log.warning("prewarm tsunamis preload-range failed: %s", exc)

    # --- floods (default preset is severity 2+, data currently ends in 2019) --
    fl_path = resolve_flood_events_path(global_dir)
    flood_preload_end_year = min(preload_end_year, 2019)
    if preload_start_year <= flood_preload_end_year:
        preload_ck = make_preload_cache_key("floods", min_severity=2, include_geometry=True)
        if cache_get(preload_ck) is None:
            try:
                t0 = time.monotonic()
                flood_preload_start = f"{preload_start_year:04d}-01-01 00:00:00"
                flood_preload_end = f"{flood_preload_end_year:04d}-12-31 23:59:59"
                df = select_filtered_event_rows(
                    fl_path,
                    start=flood_preload_start,
                    end=flood_preload_end,
                    min_value_filters={"severity": 2},
                )
                if not df.empty:
                    cache_set(preload_ck, df, permanent=True)
                log.info("prewarm floods preload-range: %d rows in %.1fs", len(df), time.monotonic() - t0)
            except Exception as exc:
                log.warning("prewarm floods preload-range failed: %s", exc)

    # --- volcanoes/eruptions (default preset is VEI 3+, exclude ongoing) -----
    vol_path = global_dir / "disasters/volcanoes/events.parquet"
    preload_ck = make_preload_cache_key("volcanoes", min_vei=3, exclude_ongoing=True)
    if cache_get(preload_ck) is None:
        try:
            t0 = time.monotonic()
            df = select_filtered_event_rows(
                vol_path,
                start=preload_start,
                end=preload_end,
                min_value_filters={"VEI": 3},
            )
            if not df.empty and "is_ongoing" in df.columns:
                df = df[df["is_ongoing"] != True]
            if not df.empty:
                cache_set(preload_ck, df, permanent=True)
            log.info("prewarm volcanoes preload-range: %d rows in %.1fs", len(df), time.monotonic() - t0)
        except Exception as exc:
            log.warning("prewarm volcanoes preload-range failed: %s", exc)

    # --- tornadoes (default preset is EF2+, post-fetch scale filter) ----------
    tor_path = global_dir / "disasters/tornadoes/events.parquet"
    preload_ck = make_preload_cache_key("tornadoes", min_scale="EF2")
    if cache_get(preload_ck) is None:
        try:
            t0 = time.monotonic()
            df = select_filtered_event_rows(
                tor_path,
                columns=tornado_columns,
                start=preload_start,
                end=preload_end,
            )
            if not df.empty:
                cache_set(preload_ck, df, permanent=True)
            log.info("prewarm tornadoes preload-range: %d rows in %.1fs", len(df), time.monotonic() - t0)
        except Exception as exc:
            log.warning("prewarm tornadoes preload-range failed: %s", exc)

    # --- hurricanes (storms.parquet + positions.parquet; route assembles join)
    # Warm DuckDB metadata cache for both files; route handler caches the join.
    hur_storms_path = global_dir / "disasters/hurricanes/storms.parquet"
    hur_positions_path = global_dir / "disasters/hurricanes/positions.parquet"
    preload_ck = make_preload_cache_key("hurricanes_tracks", min_category="Cat1")
    if cache_get(preload_ck) is None:
        try:
            t0 = time.monotonic()
            # storms.parquet has no `timestamp` column - it has `start_date` /
            # `end_date` for each storm - so passing start/end here silently
            # falls through and returns ALL storms (1842-2026, 13.5k rows).
            # Filter by `year` directly so the join only covers storms in the
            # canonical rolling ten-year preload window. Without this, the cached
            # joined frame was ~303k rows instead of ~14k, and every hurricane
            # request paid pandas-on-300k cost.
            storms_df = select_filtered_event_rows(
                hur_storms_path,
                columns=hurricane_storm_columns,
            )
            if not storms_df.empty and "year" in storms_df.columns:
                storms_df = storms_df[
                    (storms_df["year"] >= preload_start_year) & (storms_df["year"] <= preload_end_year)
                ]
            if not storms_df.empty:
                cat_order = {"TD": 0, "TS": 1, "Cat1": 2, "Cat2": 3, "Cat3": 4, "Cat4": 5, "Cat5": 6}
                storms_df = storms_df[storms_df["max_category"].map(lambda x: cat_order.get(x, 0) >= 2)]
                if not storms_df.empty:
                    storm_ids = storms_df["storm_id"].tolist()
                    pos_df = select_filtered_event_rows(
                        hur_positions_path,
                        columns=hurricane_position_columns,
                        in_filters={"storm_id": storm_ids},
                    )
                    pos_df = pos_df.dropna(subset=["latitude", "longitude"])
                    if not pos_df.empty:
                        joined = pos_df.merge(
                            storms_df[
                                [
                                    "storm_id",
                                    "name",
                                    "year",
                                    "basin",
                                    "max_wind_kt",
                                    "min_pressure_mb",
                                    "max_category",
                                    "num_positions",
                                    "start_date",
                                    "end_date",
                                    "display_start_timestamp",
                                    "display_end_timestamp",
                                    "display_animation_kind",
                                    "made_landfall",
                                ]
                            ],
                            on="storm_id",
                            how="inner",
                        )
                        if not joined.empty:
                            cache_set(preload_ck, joined, permanent=True)
            log.info("prewarm hurricanes preload-range: %d joined rows in %.1fs", len(joined) if 'joined' in locals() else 0, time.monotonic() - t0)
        except Exception as exc:
            log.warning("prewarm hurricanes preload-range failed: %s", exc)

    # --- wildfires (the same global + USA + CAN union as the route) ---------
    # This is a deliberately broad multi-source union. Do not make it a
    # startup/readiness dependency by default: even predicate-pushed remote
    # reads can consume the entire interactive budget on a cold deployment.
    # A scheduled warmer may opt in once the process is ready.
    if os.environ.get("PREWARM_WILDFIRES", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        log.info("prewarm wildfires skipped (set PREWARM_WILDFIRES=1 for background warming)")
        log.info("Pre-warmer complete")
        return
    preload_ck = make_preload_cache_key("wildfires", min_area_km2=500, include_perimeter=False)
    if cache_get(preload_ck) is None:
        try:
            t0 = time.monotonic()
            from .paths import COUNTRIES_DIR

            wildfire_frames: list[pd.DataFrame] = []
            # The browser's default request has no location filter, so it
            # deliberately combines the regional source files with the compact
            # canonical global events index. The enriched year partitions are
            # detail assets and must stay out of overview/prewarm scans.
            regional_sources = (
                ("NIFC", global_dir / "disasters/wildfires/sources/usa/fires_enriched.parquet", COUNTRIES_DIR / "USA/disasters/wildfires/fires_enriched.parquet"),
                ("CNFDB", global_dir / "disasters/wildfires/sources/can/fires_enriched.parquet", COUNTRIES_DIR / "CAN/wildfires/fires_enriched.parquet"),
            )
            for source_name, preferred_path, fallback_path in regional_sources:
                source_path = preferred_path if is_cloud_mode() or preferred_path.exists() else fallback_path
                try:
                    # Push the rolling-window predicate into DuckDB. These
                    # regional files are large; loading the complete object
                    # and slicing timestamps in pandas kept startup disaster
                    # prewarm running indefinitely in hosted mode.
                    regional_df = select_filtered_event_rows(
                        source_path,
                        columns=wildfire_columns,
                        start=preload_start,
                        end=preload_end,
                        min_value_filters={"area_km2": 500},
                    )
                    if regional_df.empty:
                        continue
                    regional_df["timestamp"] = pd.to_datetime(regional_df["timestamp"], errors="coerce")
                    if "area_km2" in regional_df.columns:
                        regional_df = regional_df[regional_df["area_km2"] >= 500]
                    elif "burned_acres" in regional_df.columns:
                        regional_df["area_km2"] = regional_df["burned_acres"] * 0.00404686
                        regional_df = regional_df[regional_df["area_km2"] >= 500]
                    if not regional_df.empty:
                        if "source" not in regional_df.columns:
                            regional_df["source"] = source_name
                        wildfire_frames.append(regional_df)
                except Exception as exc:
                    log.warning("prewarm wildfires %s source failed: %s", source_name, exc)

            global_df = select_filtered_event_rows(
                global_dir / "disasters/wildfires/events.parquet",
                columns=wildfire_columns,
                start=preload_start,
                end=preload_end,
                min_value_filters={"area_km2": 500},
            )
            if not global_df.empty:
                global_df["timestamp"] = pd.to_datetime(global_df["timestamp"], errors="coerce")
                if "land_cover" not in global_df.columns:
                    global_df["land_cover"] = ""
                if "source" not in global_df.columns:
                    global_df["source"] = "global_fire_atlas"
                if "iso3" in global_df.columns:
                    global_df = global_df[~global_df["iso3"].isin(["USA", "CAN"])]
                if not global_df.empty:
                    wildfire_frames.append(global_df)

            df = pd.concat(wildfire_frames, ignore_index=True) if wildfire_frames else pd.DataFrame()
            if not df.empty:
                cache_set(preload_ck, df, permanent=True)
            log.info("prewarm wildfires preload-range: %d rows in %.1fs", len(df), time.monotonic() - t0)
        except Exception as exc:
            log.warning("prewarm wildfires preload-range failed: %s", exc)

    log.info("Pre-warmer complete")
