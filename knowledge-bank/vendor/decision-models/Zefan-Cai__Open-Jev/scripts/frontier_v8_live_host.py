"""No-borrow preallocation checks, without model or physical GPU authority.

Default reads are real Linux proc and absolute nvidia-smi reads. Injected host,
GPU and source-verifier fixtures have a separate, non-promotable scope. Held
flock descriptors are cooperative reservations only. There is no model-worker
bridge, queue adapter, lease release protocol or complete recovery episode here.
The canonical process/parser imports come from the operational checkout, even
when their bytes equal a frozen native file; actual origins are recorded.
Those already imported dependencies assume a trusted clean interpreter; their
file attributes and disk hashes do not attest arbitrary preloaded Python code.
"""
from dataclasses import asdict
import fcntl
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import secrets
import time

from scripts import frontier_v8_owned_process as process
from scripts import frontier_v8_resource_episode as episode


NODES = {'ms-n1-1': '100.64.180.123', 'ms-n1-3': '100.113.206.109',
         'ms-n4-1': '100.73.246.72', 'ms-n4-2': '100.88.50.20',
         'ms-n4-3': '100.94.49.109', 'ms-n4-4': '100.112.105.35'}
LIVE_SCOPE = 'live_host_preallocation_checks_only'
CPU_SCOPE = 'injected_CPU_preallocation_fixture_no_resource_authority'
_ISSUER = object()
_FIELDS = {'schema_version', 'mode', 'attempt_id', 'acquisition_id', 'node_alias',
           'expected_hostname', 'gpu_uuid', 'controller', 'guard', 'nonce',
           'work_started_monotonic', 'work_deadline_monotonic', 'restoration_seconds',
           'lease_directory', 'source_binding', 'stage_binding'}


class LiveHostError(RuntimeError):
    pass


class PreallocationDeadlineExceeded(LiveHostError):
    pass


def _require(condition, message):
    if not condition:
        raise LiveHostError(message)


def _canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _identity(value):
    _require(isinstance(value, dict) and set(value) == set(process.ProcessIdentity.__dataclass_fields__),
             'exact current process identity required')
    _require(isinstance(value['boot_id'], str) and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value['boot_id']),
             'kernel boot identity required')
    for name in set(value) - {'boot_id'}:
        _require(type(value[name]) is int and value[name] >= (0 if name in ('uid', 'ppid') else 1),
                 'typed process identity required')
    return process.ProcessIdentity(**value)


def _spec(value):
    _require(isinstance(value, dict) and set(value) == _FIELDS, 'strict no-borrow preallocation specification required')
    _require(type(value['schema_version']) is int and value['schema_version'] == 1
             and value['mode'] == 'no_borrow' and value['node_alias'] in NODES,
             'borrowed queues and ineligible nodes are unavailable')
    for name, pattern in [('attempt_id', r'frontier-v8-[0-9a-f]{16,64}'),
                          ('acquisition_id', r'[0-9a-f]{32}'), ('nonce', r'[0-9a-f]{32,128}')]:
        _require(isinstance(value[name], str) and re.fullmatch(pattern, value[name]), 'fresh attempt/acquisition/nonce required')
    _require(isinstance(value['expected_hostname'], str) and value['expected_hostname']
             and isinstance(value['gpu_uuid'], str) and value['gpu_uuid'].startswith('GPU-'),
             'declared hostname and physical GPU UUID required')
    _identity(value['controller']); _identity(value['guard'])
    start, deadline = value['work_started_monotonic'], value['work_deadline_monotonic']
    _require(type(start) in (int, float) and type(deadline) in (int, float)
             and math.isfinite(start) and math.isfinite(deadline) and start >= 0
             and 0 < deadline - start <= 4500, 'bounded same-boot work interval required')
    try:
        episode._bounded(value['restoration_seconds'], 1500)
        episode._absolute(value['lease_directory'])
    except (ValueError, TypeError) as error:
        raise LiveHostError(str(error)) from error
    return json.loads(json.dumps(value, allow_nan=False))


def _deadline(spec):
    now = time.monotonic()
    _require(math.isfinite(now) and now >= spec['work_started_monotonic'], 'invalid or reversed owner clock')
    if now >= spec['work_deadline_monotonic']:
        raise PreallocationDeadlineExceeded('preallocation work deadline exceeded')


def _host(proc_root):
    root = Path(proc_root)
    addresses, last = set(), None
    for row in (root / 'net/fib_trie').read_text().splitlines():
        match = re.search(r'\|-- (\d+(?:\.\d+){3})\s*$', row)
        if match:
            last = str(ipaddress.IPv4Address(match[1]))
        elif '/32 host LOCAL' in row and last is not None:
            addresses.add(last)
    return {'hostname': (root / 'sys/kernel/hostname').read_text().strip(),
            'local_ipv4s': sorted(addresses)}


def _bound_file(binding, path_key, digest_key):
    _require(isinstance(binding, dict) and set(binding) == {path_key, digest_key}
             and isinstance(binding[digest_key], str) and re.fullmatch(r'[0-9a-f]{64}', binding[digest_key]),
             'exact content binding required')
    path = episode._absolute(binding[path_key])
    return path, episode._raw_bytes(path)


def _origins(receipt, extra=None):
    operational = receipt['operational']
    root = episode._absolute(operational['root'])
    files = operational['files_sha256']
    paths = {'adapter': Path(__file__).resolve(), 'process': Path(process.__file__).resolve(),
             'parser': Path(episode.__file__).resolve()}
    if extra is not None:
        paths['source_loader'] = Path(extra).resolve()
    result = {}
    for name, path in paths.items():
        _require(path.is_relative_to(root), 'adapter dependency came from another source checkout')
        digest = hashlib.sha256(episode._raw_bytes(path)).hexdigest()
        _require(files.get(path.relative_to(root).as_posix()) == digest,
                 'operational dependency source hash changed')
        result[name] = {'path': str(path), 'sha256': digest, 'source_role': 'operational'}
    return result


def _verify_sources(binding, fixture_verifier=None):
    path, raw = _bound_file(binding, 'receipt_path', 'receipt_canonical_sha256')
    saved = json.loads(raw)
    _require(_canonical(saved) == binding['receipt_canonical_sha256'], 'source receipt digest differs')
    _require(saved.get('scope') == 'three_source_CPU_verification_only'
             and saved.get('status') == 'three_clean_sources_verified_CPU_only'
             and all(saved.get(key) is False for key in ('execution_available', 'resource_authority', 'model_execution_authority')),
             'source verification receipt cannot grant execution authority')
    origins = _origins(saved)
    if fixture_verifier is not None:
        current = fixture_verifier(saved['context'])
    else:
        loader_path = episode._absolute(saved['operational']['root']) / 'scripts/frontier_v8_source_loader.py'
        origins = _origins(saved, loader_path)
        alias = '_frontier_v8_preallocation_source_' + secrets.token_hex(16)
        loader_spec = importlib.util.spec_from_file_location(alias, loader_path)
        module = importlib.util.module_from_spec(loader_spec)
        raw_loader = episode._raw_bytes(loader_path)
        _require(hashlib.sha256(raw_loader).hexdigest() == origins['source_loader']['sha256'],
                 'source loader bytes changed before execution')
        sys.modules[alias] = module
        try:
            # Execute the exact hashed source, never SourceFileLoader's .pyc cache.
            exec(compile(raw_loader, str(loader_path), 'exec'), module.__dict__)
            current = module.verify_three_sources(saved['context'])
        finally:
            sys.modules.pop(alias, None)
    _require(_canonical(current) == _canonical(saved), 'fresh three-source verification differs from bound receipt')
    _origins(saved, None if fixture_verifier is not None else loader_path)
    return saved, origins, {'path': str(path), 'canonical_sha256': _canonical(saved),
                            'bytes_sha256': hashlib.sha256(raw).hexdigest()}


def _bindings(spec, fixture_verifier):
    source, origins, fingerprint = _verify_sources(spec['source_binding'], fixture_verifier)
    path, raw = _bound_file(spec['stage_binding'], 'stage_path', 'stage_sha256')
    _require(hashlib.sha256(raw).hexdigest() == spec['stage_binding']['stage_sha256'], 'declared CPU stage marker bytes changed')
    stage = json.loads(raw)
    _require(type(stage.get('schema_version')) is int and stage['schema_version'] == 1
             and stage.get('status') == 'cpu_staged_no_cuda_initialization'
             and stage.get('cuda_initialized') is False and stage.get('attempt_id') == spec['attempt_id']
             and stage.get('source_commit') == source['scientific']['commit'],
             'CPU stage marker attempt/source binding differs')
    lease = episode._absolute(spec['lease_directory'])
    _require(all(not lease.is_relative_to(episode._absolute(source[name]['root']))
                 for name in ('scientific', 'native', 'operational')), 'lease metadata overlaps a source checkout')
    return {'source_receipt': fingerprint, 'module_origins': origins,
            'stage_marker': {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()},
            'stage_scope': 'declared_CPU_marker_bytes_only_not_runtime_data_weights_validation'}


def _processes(spec, kernel):
    controller, guard = _identity(spec['controller']), _identity(spec['guard'])
    current = kernel.identity(os.getpid())
    _require(current == guard and guard.pid != controller.pid
             and guard.ppid == controller.pid and guard.uid == controller.uid
             and guard.boot_id == controller.boot_id and guard.start_ticks >= controller.start_ticks
             and guard.session == guard.pid and guard.pgrp == guard.pid
             and process._same_process(kernel.identity(controller.pid), controller)
             and kernel.nonce(guard.pid) == [spec['nonce']],
             'preallocation issuer is not this fresh nonce/session guard child')
    return controller, guard


def _capture(spec, kernel, query, host_query, scope, fixture_verifier):
    _deadline(spec)
    controller, guard = _processes(spec, kernel)
    host = host_query()
    _require(isinstance(host, dict) and host.get('hostname') == spec['expected_hostname']
             and NODES[spec['node_alias']] in host.get('local_ipv4s', []),
             'declared alias/IP/hostname differs from current host')
    bindings = _bindings(spec, fixture_verifier)
    probe = query()
    selected = [x for x in probe['gpus'] if x['uuid'] == spec['gpu_uuid']]
    _require(len(selected) == 1 and selected[0]['index'] >= 2 and 'H100' in selected[0]['name'],
             'only one actual physical H100 UUID >=2 may be checked')
    _require(not any(x['gpu_uuid'] == spec['gpu_uuid'] for x in probe['compute_processes']),
             'selected physical GPU is occupied')
    episode._idle_gpu(selected[0])
    protected = episode._protected(probe, kernel)
    _processes(spec, kernel)
    _deadline(spec)
    return {'schema_version': 1, 'scope': scope, 'mode': 'no_borrow', 'attempt_id': spec['attempt_id'],
            'node_alias': spec['node_alias'], 'host': host, 'controller': asdict(controller), 'guard': asdict(guard),
            'gpu': episode._gpu_identity(selected[0]), 'raw_gpu_observation': probe,
            'protected_gpu_inventory': protected, **bindings,
            'physical_exclusion_proven': False, 'live_resource_lease_issued': False,
            'model_execution_authority': False, 'execution_available': False,
            'complete_resource_episode_proven': False,
            'limits': ['Instantaneous raw reads and cooperative flock do not exclude nonparticipating consumers.',
                       'CPU stage marker hashes do not validate full runtime/data/weights or ABI.',
                       'Canonical dependency origins assume a trusted clean interpreter, not arbitrary cached Python code.',
                       'New model-worker bridge and recovery protocol remain pending; borrowed route is closed.']}


def capture_live_preallocation(spec):
    """Read actual host facts; no lease or model authority is issued."""
    process._require_linux()
    value, kernel = _spec(spec), process._Kernel()
    return _capture(value, kernel, episode.read_live_gpu_inventory,
                    lambda: _host(kernel.proc_root), LIVE_SCOPE, None)


def _lease(spec, snapshot):
    directory = episode._absolute(spec['lease_directory'])
    directory.mkdir(mode=0o700, exist_ok=True)
    st = directory.stat()
    _require(stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o077,
             'private UID-owned cooperative lease directory required')
    path = directory / (spec['gpu_uuid'] + '.lease')
    marker = directory / (spec['gpu_uuid'] + '.reservation.json')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        st = os.fstat(fd)
        _require(stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o077,
                 'private regular cooperative lease inode required')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        process._exclusive_json(marker, {'schema_version': 1, 'resource_scope': snapshot['scope'],
            'acquisition_id': spec['acquisition_id'], 'attempt_id': spec['attempt_id'],
            'gpu_uuid': spec['gpu_uuid'], 'boot_id': snapshot['guard']['boot_id'],
            'physical_exclusion_proven': False, 'model_execution_authority': False})
        marker_st = marker.stat()
        return {'fd': fd, 'path': str(path), 'marker': str(marker), 'gpu': snapshot['gpu'],
                'device': st.st_dev, 'inode': st.st_ino, 'marker_device': marker_st.st_dev,
                'marker_inode': marker_st.st_ino, 'marker_sha256': hashlib.sha256(episode._raw_bytes(marker)).hexdigest()}
    except BaseException:
        os.close(fd)
        raise


class NoBorrowPreallocationOwner:
    """Issued by this adapter only; assert_owned checks facts, never allocation rights."""
    def __init__(self, issuer, spec, kernel, query, host_query, scope, fixture_verifier):
        _require(issuer is _ISSUER, 'preallocation owner must be issued by the guard adapter')
        self._spec, self._kernel = spec, kernel
        self._query, self._host_query = query, host_query
        self._scope, self._fixture_verifier = scope, fixture_verifier
        self._controller_fd = self._guard_fd = self._entry = None
        self._closed = False
        try:
            snapshot = _capture(spec, kernel, query, host_query, scope, fixture_verifier)
            self._controller_fd = kernel.open_bound(_identity(spec['controller']))
            self._guard_fd = kernel.open_bound(_identity(spec['guard']))
            self._entry = _lease(spec, snapshot)
            self.bindings = episode._freeze({**snapshot, 'nonce': spec['nonce'],
                'acquisition_id': spec['acquisition_id'],
                'work_deadline_monotonic': spec['work_deadline_monotonic'],
                'restoration_seconds': spec['restoration_seconds'],
                'linux_pidfd_evidence': type(kernel) is process._Kernel and kernel.proc_root == Path('/proc'),
                'injected_GPU': scope == CPU_SCOPE, 'source_verifier_injected': fixture_verifier is not None})
            self.assert_owned()
        except BaseException:
            self.close()
            raise

    def assert_owned(self):
        _require(not self._closed, 'preallocation owner was closed')
        _deadline(self._spec)
        _require(not self._kernel.exited(self._controller_fd) and not self._kernel.exited(self._guard_fd),
                 'bound guard/controller pidfd has exited')
        episode._check_lease(self._entry, self._spec['acquisition_id'])
        current = _capture(self._spec, self._kernel, self._query, self._host_query,
                           self._scope, self._fixture_verifier)
        _require(current['gpu'] == dict(self.bindings['gpu'])
                 and current['protected_gpu_inventory'] == _thaw(self.bindings['protected_gpu_inventory'])
                 and current['module_origins'] == _thaw(self.bindings['module_origins']),
                 'selected/protected GPU or operational source origins changed')
        _deadline(self._spec)
        return None

    def require_model_authority(self):
        raise LiveHostError('model authority unavailable: physical exclusion and a new guard/model bridge are pending')

    def close(self):
        self._closed = True
        for fd in (self._controller_fd, self._guard_fd, self._entry['fd'] if self._entry else None):
            if fd is not None:
                os.close(fd)
        self._controller_fd = self._guard_fd = self._entry = None
        # Persistent marker remains: no complete recovery/release protocol exists.


def _thaw(value):
    if hasattr(value, 'items'):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def bind_guard_preallocation(spec):
    """Check-only real host owner; its cooperative marker grants no GPU authority."""
    process._require_linux()
    value, kernel = _spec(spec), process._Kernel()
    return NoBorrowPreallocationOwner(_ISSUER, value, kernel, episode.read_live_gpu_inventory,
        lambda: _host(kernel.proc_root), LIVE_SCOPE, None)


def bind_cpu_fixture_preallocation(spec, *, gpu_fixture_path, host_fixture_path,
                                  source_verifier, kernel=None):
    """Explicit injected GPU/host/source fixtures; never promoted to LIVE_SCOPE."""
    _require(callable(source_verifier), 'explicit CPU fixture source verifier required')
    value = _spec(spec)
    gpu_path, host_path = map(episode._absolute, (gpu_fixture_path, host_fixture_path))
    selected_kernel = kernel if kernel is not None else process._Kernel()
    return NoBorrowPreallocationOwner(_ISSUER, value, selected_kernel,
        lambda: episode._gpu_probe(gpu_path), lambda: episode._json(host_path), CPU_SCOPE, source_verifier)


def main(argv=None):
    raise LiveHostError('production execution unavailable; preallocation checks are not model authority')


if __name__ == '__main__':
    main()
