"""Passive process accounting; no cache loads, GC, or profiler resets."""
import ctypes
import gc
import os
from pathlib import Path
import sys
import time
import hashlib
import tracemalloc

OWNERS = (
    ('ops_state', 'mapmover.ops_orchestrator_runtime', '_LIVE_STATE_CACHE'),
    ('foundation_reference', 'mapmover.foundation_helpers', '_REFERENCE_JSON_CACHE'),
    ('foundation_assets', 'mapmover.foundation_helpers', '_COUNTRY_JSON_ASSET_CACHE'),
    ('foundation_crosswalks', 'mapmover.foundation_helpers', '_COUNTRY_CROSSWALK_CACHE'),
    ('foundation_exact', 'mapmover.foundation_helpers', '_GLOBAL_COUNTRIES_CACHE'),
    ('foundation_display', 'mapmover.foundation_helpers', '_GLOBAL_COUNTRY_DISPLAY_CACHE'),
    ('admin_hierarchy', 'mapmover.runtime.admin_hierarchy', '_BASE_GEOMETRY_CACHE'),
    ('admin_identity', 'mapmover.runtime.admin_spine_query', '_SHALLOW_IDENTITY_CACHE'),
    ('sessions', 'mapmover.session_cache', 'session_manager'),
    ('corpus', 'mapmover.corpus_registry', 'corpus_registry'),
    ('orders', 'mapmover.order_queue', 'order_queue'),
)

_STATUS_FIELDS = (
    'VmPeak', 'VmSize', 'VmHWM', 'VmRSS', 'RssAnon', 'RssFile', 'RssShmem',
    'VmData', 'VmStk', 'VmExe', 'VmLib', 'VmPTE', 'VmSwap', 'Threads',
)
_SMAPS_FIELDS = (
    'Rss', 'Pss', 'Pss_Anon', 'Pss_File', 'Pss_Shmem', 'Shared_Clean',
    'Shared_Dirty', 'Private_Clean', 'Private_Dirty', 'Anonymous',
    'AnonHugePages', 'Swap', 'SwapPss', 'Locked',
)
_CGROUP_STAT_FIELDS = (
    'anon', 'file', 'kernel', 'kernel_stack', 'pagetables', 'percpu', 'sock',
    'shmem', 'file_mapped', 'file_dirty', 'file_writeback', 'swapcached',
    'inactive_anon', 'active_anon', 'inactive_file', 'active_file',
    'workingset_refault_anon', 'workingset_refault_file', 'pgfault', 'pgmajfault',
)


def _proc_kib(path: str, fields: tuple[str, ...]) -> dict[str, int]:
    """Read selected Linux proc key/value rows whose values are expressed in KiB."""
    wanted = set(fields)
    result: dict[str, int] = {}
    for line in Path(path).read_text().splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        if key in wanted:
            result[key] = int(value.split()[0])
    return result


def _flat_int_file(path: str, fields: tuple[str, ...] | None = None) -> dict[str, int]:
    wanted = set(fields) if fields else None
    result: dict[str, int] = {}
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and (wanted is None or parts[0] in wanted):
            result[parts[0]] = int(parts[1])
    return result


def _read_int(path: str) -> int | None:
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return None


class _Mallinfo2(ctypes.Structure):
    _fields_ = [
        ('arena', ctypes.c_size_t), ('ordblks', ctypes.c_size_t),
        ('smblks', ctypes.c_size_t), ('hblks', ctypes.c_size_t),
        ('hblkhd', ctypes.c_size_t), ('usmblks', ctypes.c_size_t),
        ('fsmblks', ctypes.c_size_t), ('uordblks', ctypes.c_size_t),
        ('fordblks', ctypes.c_size_t), ('keepcost', ctypes.c_size_t),
    ]


def glibc_allocator_snapshot() -> dict:
    """Return glibc heap/mmap counters when available; never mutate allocator state."""
    if os.name != 'posix':
        return {'available': False, 'reason': 'non_posix'}
    try:
        libc = ctypes.CDLL(None)
        mallinfo2 = libc.mallinfo2
        mallinfo2.restype = _Mallinfo2
        info = mallinfo2()
        return {
            'available': True,
            'arena_bytes': int(info.arena),
            'allocated_heap_bytes': int(info.uordblks),
            'free_heap_bytes': int(info.fordblks),
            'releasable_top_bytes': int(info.keepcost),
            'mmap_region_count': int(info.hblks),
            'mmap_bytes': int(info.hblkhd),
            'free_chunk_count': int(info.ordblks),
            'note': 'glibc mallinfo2 process totals; native owners are not identified.',
        }
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        return {'available': False, 'reason': type(exc).__name__}


def process_memory_snapshot() -> dict:
    """Return cheap OS/allocator categories that explain RSS without loading app data."""
    result: dict = {
        'pid': os.getpid(),
        'python_runtime': {
            'allocated_blocks': sys.getallocatedblocks(),
            'gc_generation_counts': list(gc.get_count()),
            'gc_thresholds': list(gc.get_threshold()),
        },
        'glibc_allocator': glibc_allocator_snapshot(),
    }
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        result['python_tracemalloc'] = {
            'enabled': True, 'current_bytes': current, 'peak_bytes': peak,
            'note': 'Only allocations traced after tracing started; native library allocations may be absent.',
        }
    else:
        result['python_tracemalloc'] = {'enabled': False}
    arrow = sys.modules.get('pyarrow')
    if arrow is not None and hasattr(arrow, 'default_memory_pool'):
        try:
            pool = arrow.default_memory_pool()
            max_memory = pool.max_memory()
            result['arrow_memory_pool'] = {
                'loaded': True, 'backend': pool.backend_name,
                'allocated_bytes': int(pool.bytes_allocated()),
                'max_allocated_bytes': None if max_memory is None else int(max_memory),
                'note': 'Arrow default pool only; excludes other pools and allocator-retained pages.',
            }
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            result['arrow_memory_pool'] = {'loaded': True, 'error': type(exc).__name__}
    else:
        result['arrow_memory_pool'] = {'loaded': False}
    try:
        result['status_kib'] = _proc_kib('/proc/self/status', _STATUS_FIELDS)
    except (OSError, ValueError) as exc:
        result['status_error'] = str(exc)
    try:
        result['smaps_rollup_kib'] = _proc_kib('/proc/self/smaps_rollup', _SMAPS_FIELDS)
    except (OSError, ValueError) as exc:
        result['smaps_rollup_error'] = str(exc)
    result['cgroup_current_bytes'] = _read_int('/sys/fs/cgroup/memory.current')
    result['cgroup_peak_bytes'] = _read_int('/sys/fs/cgroup/memory.peak')
    try:
        result['cgroup_stat'] = _flat_int_file('/sys/fs/cgroup/memory.stat', _CGROUP_STAT_FIELDS)
    except (OSError, ValueError) as exc:
        result['cgroup_stat_error'] = str(exc)
    try:
        result['cgroup_events'] = _flat_int_file('/sys/fs/cgroup/memory.events')
    except (OSError, ValueError) as exc:
        result['cgroup_events_error'] = str(exc)
    return result


def traced_allocation_top(*, limit=15) -> dict:
    """Read existing tracing state; never turn tracing on in a live process."""
    if not tracemalloc.is_tracing():
        return {'enabled': False, 'instruction': 'Start the process with PYTHONTRACEMALLOC=10 for a diagnostic instance.'}
    snapshot = tracemalloc.take_snapshot()
    rows = []
    for stat in snapshot.statistics('lineno')[:limit]:
        frame = stat.traceback[0]
        rows.append({'file': frame.filename, 'line': frame.lineno,
                     'size_bytes': stat.size, 'block_count': stat.count})
    current, peak = tracemalloc.get_traced_memory()
    return {'enabled': True, 'current_bytes': current, 'peak_bytes': peak,
            'top_allocations': rows,
            'note': 'Traced Python allocations only. Do not sum with RSS, Arrow pool, or glibc totals.'}


def loaded_dataframe_cache_memory() -> dict:
    """Measure already-loaded DataFrame caches without importing or populating them."""
    now = time.monotonic()
    result: dict = {}
    duckdb_module = sys.modules.get('mapmover.duckdb_helpers')
    if duckdb_module is None:
        result['query_results'] = {'loaded': False}
    else:
        lock = getattr(duckdb_module, '_CACHE_LOCK', None)
        cache = getattr(duckdb_module, '_CACHE', None)
        if lock is None or cache is None:
            result['query_results'] = {'loaded': False}
        else:
            with lock:
                entries = list(cache.values())
            summary = {
                'loaded': True, 'entries': len(entries), 'bytes': 0,
                'active_entries': 0, 'active_bytes': 0,
                'expired_entries': 0, 'expired_bytes': 0,
                'permanent_entries': 0, 'permanent_bytes': 0,
            }
            for frame, expires_at in entries:
                try:
                    size = int(frame.memory_usage(deep=True).sum())
                except (AttributeError, TypeError, ValueError):
                    size = int(sys.getsizeof(frame))
                summary['bytes'] += size
                if expires_at == float('inf'):
                    bucket = 'permanent'
                elif now > expires_at:
                    bucket = 'expired'
                else:
                    bucket = 'active'
                summary[f'{bucket}_entries'] += 1
                summary[f'{bucket}_bytes'] += size
            result['query_results'] = summary

    geometry_module = sys.modules.get('mapmover.geometry_handlers')
    if geometry_module is None:
        result['geometry'] = {'loaded': False}
    else:
        lock = getattr(geometry_module, '_country_parquet_cache_lock', None)
        cache = getattr(geometry_module, '_country_parquet_cache', None)
        if lock is None or cache is None:
            result['geometry'] = {'loaded': False}
        else:
            with lock:
                frames = list(cache.values())
            sizes = []
            for frame in frames:
                try:
                    sizes.append(int(frame.memory_usage(deep=True).sum()))
                except (AttributeError, TypeError, ValueError):
                    sizes.append(int(sys.getsizeof(frame)))
            result['geometry'] = {
                'loaded': True, 'entries': len(frames), 'bytes': sum(sizes),
                'policy': 'permanent_until_relief_or_refresh',
            }
    result['note'] = 'DataFrame deep-size estimates exclude native allocator retention and transient query copies.'
    return result


def bounded_size(value, *, max_nodes=20000, seconds=0.03):
    """Approximate Python graph bytes, explicitly excluding unknown native buffers."""
    pending = [value]
    seen = set()
    total = 0
    deadline = time.monotonic() + seconds
    truncated = False
    while pending:
        if len(seen) >= max_nodes or time.monotonic() >= deadline:
            truncated = True
            break
        item = pending.pop()
        identity = id(item)
        if identity in seen:
            continue
        seen.add(identity)
        total += sys.getsizeof(item)
        # Limit traversal frontier as well as visited nodes.
        remaining = max_nodes - len(seen) - len(pending)
        children = None
        if isinstance(item, dict):
            def pairs():
                for key, child in item.items():
                    yield key
                    yield child
            children = pairs()
        elif isinstance(item, (list, tuple, set, frozenset)):
            children = iter(item)
        elif type(item).__module__.startswith('mapmover.') and hasattr(item, '__dict__'):
            children = iter((vars(item),))
        if children is not None:
            try:
                for child in children:
                    if remaining <= 0:
                        truncated = True
                        break
                    pending.append(child)
                    remaining -= 1
            except RuntimeError:
                truncated = True  # A concurrent owner mutation is not a diagnostic failure.
    return {'estimated_python_bytes': total, 'visited_nodes': len(seen), 'truncated': truncated}


def loaded_owner_memory(*, include_entries=True):
    result = {}
    for label, module_name, attribute in OWNERS:
        module = sys.modules.get(module_name)
        value = getattr(module, attribute, None) if module else None
        if value is None:
            result[label] = {'loaded': False}
            continue
        result[label] = {'loaded': True, **bounded_size(value)}
        if isinstance(value, (dict, list, tuple, set)):
            result[label]['entries'] = len(value)
        if isinstance(value, dict) and include_entries:
            details = []
            try:
                for key, child in value.items():
                    if len(details) >= 32:
                        break
                    key_text = str(key) if label == 'ops_state' else hashlib.sha256(str(key).encode()).hexdigest()[:12]
                    details.append({'key': key_text, **bounded_size(child, max_nodes=5000, seconds=0.005)})
            except RuntimeError:
                result[label]['changed_during_sample'] = True
            result[label]['entry_estimates'] = details
            result[label]['entries_sampled'] = len(details)
    return {'owners': result, 'note': 'Bounded Python estimates only; truncated graphs are partial. Owners may share objects; do not sum as unique RAM. Native buffers are not identified by this traversal.'}
