"""Periodic memory evidence in service logs; no external monitor or history store."""
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import time
import uuid

logger = logging.getLogger(__name__)
# The application logger also writes an unrotated local file. Send these
# samples directly to stdout for Railway capture, without duplicating to disk.
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    logger.addHandler(logging.StreamHandler(sys.stdout))
_EPOCH = uuid.uuid4().hex
_START = time.monotonic()
_FILE_HANDLER = None


def _ensure_file_log():
    """Attach a bounded persistent-volume log in Railway; never fail startup."""
    global _FILE_HANDLER
    if _FILE_HANDLER is not None:
        return str(_FILE_HANDLER.baseFilename)
    default = '/mnt/artifact-cache/memory_samples.jsonl' if os.environ.get('DEPLOYMENT', '').lower() == 'railway' else ''
    configured = os.environ.get('MEMORY_SAMPLE_LOG_PATH', default).strip()
    if not configured:
        return None
    try:
        path = Path(configured)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=10 * 1024 * 1024, backupCount=6, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        _FILE_HANDLER = handler
        return str(path)
    except OSError as exc:
        logger.warning('Persistent memory sample log unavailable: %s', exc)
        return None


def sample_memory():
    """Inspect loaded objects only; no SQL, cache loads, GC or profiling."""
    from mapmover.memory_diagnostics import (
        loaded_dataframe_cache_memory, loaded_owner_memory, process_memory_snapshot,
    )
    import sys

    started = time.monotonic()
    row = {
        'schema_version': 2, 'generated_at': datetime.now(timezone.utc).isoformat(),
        'process_epoch': _EPOCH, 'pid': os.getpid(),
        'uptime_seconds': round(started - _START, 3),
    }
    process = process_memory_snapshot()
    row['process'] = process.get('status_kib', {})
    row['smaps_rollup'] = process.get('smaps_rollup_kib', {})
    row['glibc_allocator'] = process.get('glibc_allocator', {})
    row['python_runtime'] = process.get('python_runtime', {})
    row['python_tracemalloc'] = process.get('python_tracemalloc', {'enabled': False})
    row['arrow_memory_pool'] = process.get('arrow_memory_pool', {'loaded': False})
    row['cgroup_current_bytes'] = process.get('cgroup_current_bytes')
    row['cgroup_peak_bytes'] = process.get('cgroup_peak_bytes')
    row['cgroup'] = process.get('cgroup_stat', {})
    row['cgroup_events'] = process.get('cgroup_events', {})
    for key in ('status_error', 'smaps_rollup_error', 'cgroup_stat_error', 'cgroup_events_error'):
        if process.get(key):
            row[key] = process[key]
    owners = loaded_owner_memory(include_entries=False)['owners']
    # Keep log entries small; per-key detail remains available on demand.
    row['owners'] = {key: {k: v for k, v in owner.items() if k != 'entry_estimates'}
                     for key, owner in owners.items()}
    row['dataframe_caches'] = loaded_dataframe_cache_memory()
    pool = sys.modules.get('mapmover.duckdb_helpers')
    if pool is not None and hasattr(pool, '_QUERY_POOL'):
        # Exact lease activity plus non-blocking pool occupancy; no SQL is run.
        if hasattr(pool, 'query_pool_activity_status'):
            row['query_pool'] = pool.query_pool_activity_status()
        else:
            row['query_pool'] = {
                'created': pool._QUERY_POOL_CREATED, 'idle': pool._QUERY_POOL.qsize(),
                'capacity': pool._QUERY_POOL_SIZE, 'generation': pool._QUERY_POOL_GENERATION,
                'approximate': True,
            }
    artifacts = sys.modules.get('mapmover.runtime.published_artifacts')
    if artifacts is not None:
        row['artifact_activity'] = dict(artifacts._CACHE_STATS)
    security = sys.modules.get('mapmover.security')
    limiter = getattr(security, 'rate_limiter', None) if security else None
    if limiter is not None and hasattr(limiter, 'stats'):
        row['rate_limiter'] = limiter.stats()
    execution = sys.modules.get('mapmover.mcp_execution')
    if execution is not None and hasattr(execution, 'execution_status'):
        row['mcp_execution'] = execution.execution_status()
    row['sample_seconds'] = round(time.monotonic() - started, 4)
    row['measurement_note'] = 'Process fields are KiB except Threads. Python estimates overlap and exclude native buffers. Cgroup includes other processes and file cache.'
    return row


def start_memory_logging():
    """One-minute cloud default; MEMORY_SAMPLE_SECONDS=0 disables collection."""
    default = '60' if os.environ.get('DEPLOYMENT', '').lower() == 'railway' else '0'
    try:
        interval = float(os.environ.get('MEMORY_SAMPLE_SECONDS', default))
        if not 0 <= interval <= 86400:
            raise ValueError('interval outside 0..86400')
    except ValueError:
        logger.warning('Invalid MEMORY_SAMPLE_SECONDS; using deployment default')
        interval = float(default)
    stop = threading.Event()
    if interval == 0:
        return lambda: None
    file_path = _ensure_file_log()
    logger.info('memory_logging_started interval_seconds=%s persistent_log=%s', interval, file_path or 'disabled')
    interval = max(60, interval)

    def run():
        next_due = time.monotonic()
        while not stop.is_set():
            if stop.wait(max(0, next_due - time.monotonic())):
                return
            try:
                observed = time.monotonic()
                lag = max(0.0, observed - next_due)
                missed = int(lag // interval)
                row = sample_memory()
                row['configured_interval_seconds'] = interval
                row['scheduled_lag_seconds'] = round(lag, 3)
                row['missed_intervals'] = missed
                logger.info('memory_sample %s', json.dumps(row, separators=(',', ':')))
            except Exception:
                logger.exception('Memory sample failed')
            next_due += interval * (missed + 1)

    thread = threading.Thread(target=run, name='memory-logging', daemon=True)
    thread.start()

    def close():
        stop.set()
        thread.join(timeout=2)

    return close
