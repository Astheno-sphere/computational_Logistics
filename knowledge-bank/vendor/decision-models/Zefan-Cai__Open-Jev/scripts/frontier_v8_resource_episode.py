"""Independent Linux resource episodes for CPU fixtures, without GPU authority.

The injected GPU inventory exercises the reservation protocol without querying a
device. Original processes must be fresh nonce-bound descendants of this fixture
controller. They receive only pidfd STOP/CONT. There is no foreign queue adapter,
optimizer checkpoint replay, or production model launch in this module.

Reservations are cooperative flock leases plus persistent fail-closed markers.
A marker survives watchdog/kernel loss or missing restoration proof. Operators
must not remove it on the strength of an exit code or a ready boolean.
"""
import argparse
import csv
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import threading
import time
from types import MappingProxyType

if __package__:
    from . import frontier_v8_owned_process as process
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import frontier_v8_owned_process as process


MAX_WORK_SECONDS = 4500.0
MAX_RESTORATION_SECONDS = 1500.0
ORIGINAL_NONCE_KEY = 'FRONTIER_V8_ORIGINAL_FIXTURE_NONCE'
MANIFEST_KEY = 'FRONTIER_V8_CPU_EPISODE_MANIFEST'
ELIGIBLE_NODES = {'ms-n1-1', 'ms-n1-3', 'ms-n4-1', 'ms-n4-2', 'ms-n4-3', 'ms-n4-4'}
POLL_SECONDS = 0.02


class ResourceEpisodeError(RuntimeError):
    def __init__(self, message, receipt=None):
        super().__init__(message)
        self.receipt = receipt


class EpisodeOwnershipError(ResourceEpisodeError):
    pass


class EpisodeWorkDeadlineExceeded(EpisodeOwnershipError):
    pass


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _auditor():
    from scripts import frontier_v8_restoration_audit
    return frontier_v8_restoration_audit


def _source_closure():
    paths = {'episode': Path(__file__).resolve(), 'process': Path(process.__file__).resolve(),
             'audit': Path(_auditor().__file__).resolve()}
    return {name: {'path': str(_absolute(path)), 'sha256': hashlib.sha256(_raw_bytes(path)).hexdigest()}
            for name, path in paths.items()}


def _check_source_closure(expected):
    if not isinstance(expected, dict) or expected != _source_closure():
        raise EpisodeOwnershipError('CPU episode/process/auditor source closure changed')


def _bounded(value, maximum):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 < value <= maximum):
        raise ValueError('episode deadline must be positive, finite and within its bound')
    return float(value)


def _absolute(path):
    result = Path(path)
    if not result.is_absolute() or result.resolve() != result:
        raise ValueError('episode paths must be absolute and have no symlink ancestors')
    return result


def _raw_bytes(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise EpisodeOwnershipError('episode input is not a regular file')
        raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise EpisodeOwnershipError('episode input exceeds its fixture size bound')
        fingerprint = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if (fingerprint(before) != fingerprint(os.fstat(stream.fileno()))
                or fingerprint(before) != fingerprint(os.stat(path, follow_symlinks=False))):
            raise EpisodeOwnershipError('episode input bytes or path changed during read')
        return raw


def _json(path):
    return json.loads(_raw_bytes(path))


def _gpu_probe(path):
    """Read raw injected fixture records; never imports CUDA or invokes a GPU tool."""
    value = _json(path)
    return _normalize_gpu_probe(value)


def _normalize_gpu_probe(value):
    if not isinstance(value, dict) or not isinstance(value.get('gpus'), list) or not isinstance(value.get('compute_processes'), list):
        raise EpisodeOwnershipError('invalid raw CPU GPU fixture inventory')
    gpus = {}
    for item in value['gpus']:
        if (not isinstance(item, dict) or type(item.get('index')) is not int
                or item['index'] < 0 or not isinstance(item.get('uuid'), str)
                or not re.fullmatch(r'GPU-[A-Za-z0-9-]+', item['uuid'])
                or not isinstance(item.get('name'), str)
                or type(item.get('total_memory_mib')) is not int or item['total_memory_mib'] <= 0
                or item['index'] in gpus):
            raise EpisodeOwnershipError('invalid physical GPU fixture identity')
        gpus[item['index']] = {key: item[key] for key in ('index', 'uuid', 'name', 'total_memory_mib')}
        if ('memory_used_mib' in item or 'utilization_percent' in item):
            if (type(item.get('memory_used_mib')) is not int or type(item.get('utilization_percent')) is not int
                    or not 0 <= item['memory_used_mib'] <= item['total_memory_mib']
                    or not 0 <= item['utilization_percent'] <= 100):
                raise EpisodeOwnershipError('invalid GPU idle-baseline fixture measurement')
            gpus[item['index']].update(memory_used_mib=item['memory_used_mib'], utilization_percent=item['utilization_percent'])
    if not {0, 1} <= set(gpus) or len({x['uuid'] for x in gpus.values()}) != len(gpus):
        raise EpisodeOwnershipError('protected physical GPU0/1 inventory is required')
    computes = []
    for item in value['compute_processes']:
        if (not isinstance(item, dict) or item.get('gpu_uuid') not in {x['uuid'] for x in gpus.values()}
                or type(item.get('pid')) is not int or item['pid'] <= 0
                or not isinstance(item.get('process_name'), str)):
            raise EpisodeOwnershipError('invalid compute process fixture record')
        computes.append({key: item[key] for key in ('gpu_uuid', 'pid', 'process_name')})
    if len({(x['gpu_uuid'], x['pid']) for x in computes}) != len(computes):
        raise EpisodeOwnershipError('duplicate compute fixture record')
    return {'gpus': [gpus[x] for x in sorted(gpus)],
            'compute_processes': sorted(computes, key=lambda x: (x['gpu_uuid'], x['pid']))}


def read_live_gpu_inventory(executable='/usr/bin/nvidia-smi'):
    """Concrete read-only backend; this function itself never grants a lease.

    The CPU episode entrypoint never calls it. Future independently reviewed
    host integration may use it; tests inject subprocess bytes instead of
    querying a real GPU. Commands are absolute argv without a shell.
    """
    path = _absolute(executable)
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
        raise EpisodeOwnershipError('live GPU probe executable must be root-owned and immutable to users')
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}
    def query(fields):
        result = subprocess.run([str(path), '--query-' + fields, '--format=csv,noheader,nounits'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=environment, check=True, timeout=5)
        if len(result.stdout) > 4 * 1024 * 1024:
            raise EpisodeOwnershipError('live GPU probe output exceeds its bound')
        return result.stdout.decode('utf-8', errors='strict')
    gpu_before = query('gpu=index,uuid,name,memory.total,memory.used,utilization.gpu')
    compute = query('compute-apps=gpu_uuid,pid,process_name')
    gpu_after = query('gpu=index,uuid,name,memory.total,memory.used,utilization.gpu')
    def parse_gpus(raw):
        gpus = []
        for row in csv.reader(raw.splitlines(), skipinitialspace=True):
            if len(row) != 6:
                raise EpisodeOwnershipError('malformed live GPU inventory CSV')
            gpus.append({'index': int(row[0]), 'uuid': row[1].strip(), 'name': row[2].strip(),
                         'total_memory_mib': int(row[3]), 'memory_used_mib': int(row[4]), 'utilization_percent': int(row[5])})
        return _normalize_gpu_probe({'gpus': gpus, 'compute_processes': []})['gpus']
    first, last = parse_gpus(gpu_before), parse_gpus(gpu_after)
    if [_gpu_identity(x) for x in first] != [_gpu_identity(x) for x in last]:
        raise EpisodeOwnershipError('physical GPU identity changed during live probe')
    processes = []
    for row in csv.reader(compute.splitlines(), skipinitialspace=True):
        if len(row) != 3:
            raise EpisodeOwnershipError('malformed live compute inventory CSV')
        processes.append({'gpu_uuid': row[0].strip(), 'pid': int(row[1]), 'process_name': row[2].strip()})
    result = _normalize_gpu_probe({'gpus': last, 'compute_processes': processes})
    for gpu, before in zip(result['gpus'], first):
        gpu['idle_samples'] = [{key: sample[key] for key in ('memory_used_mib', 'utilization_percent')}
                               for sample in (before, gpu)]
    return result


def _nonce(kernel, pid, key):
    values = (kernel.proc_root / str(pid) / 'environ').read_bytes().split(b'\0')
    prefix = (key + '=').encode()
    return [x[len(prefix):].decode() for x in values if x.startswith(prefix)]


def _descendant(kernel, item, ancestor):
    """Fresh kernel ancestry, never argv, process group or old PID matching."""
    seen = set()
    while item.pid != ancestor.pid:
        if item.pid in seen or item.ppid <= 1:
            raise EpisodeOwnershipError('process is outside this fresh controller tree')
        seen.add(item.pid)
        if item.uid != ancestor.uid or item.boot_id != ancestor.boot_id or item.start_ticks < ancestor.start_ticks:
            raise EpisodeOwnershipError('process birth/UID/boot is outside this fixture')
        item = kernel.identity(item.ppid)
    if not process._same_process(item, ancestor):
        raise EpisodeOwnershipError('controller ancestry identity changed')


class _OriginalTree:
    """Fresh captured CPU fixture originals; no termination or restart methods."""
    def __init__(self, kernel, controller, baseline, nonce):
        if not isinstance(nonce, str) or not re.fullmatch(r'[0-9a-f]{32,64}', nonce):
            raise EpisodeOwnershipError('borrowed CPU fixture requires its original nonce')
        self.kernel, self.controller, self.nonce = kernel, controller, nonce
        self.members = {}
        try:
            for row in baseline['original_processes']:
                expected = process.ProcessIdentity(**row['identity'])
                current = kernel.identity(expected.pid)
                if current != expected:
                    raise EpisodeOwnershipError('original baseline is not its current kernel identity')
                self._add(current)
            self.discover()
        except BaseException:
            self.close()
            raise

    def _add(self, item):
        if item.pid == self.controller.pid:
            raise EpisodeOwnershipError('the original fixture cannot contain its controller')
        _descendant(self.kernel, item, self.controller)
        if _nonce(self.kernel, item.pid, ORIGINAL_NONCE_KEY) != [self.nonce]:
            raise EpisodeOwnershipError('original process lacks this fresh fixture nonce')
        self.members[item.pid] = {'identity': item, 'fd': self.kernel.open_bound(item), 'signals': []}

    def discover(self):
        pending = list(self.members)
        seen = set()
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            member = self.members[pid]
            if self.kernel.exited(member['fd']):
                raise EpisodeOwnershipError('original fixture process exited')
            item = self.kernel.identity(pid)
            if not process._same_process(item, member['identity']):
                raise EpisodeOwnershipError('original process birth changed')
            for child in self.kernel.children(pid):
                if child not in self.members:
                    self._add(self.kernel.identity(child))
                pending.append(child)

    def _signal(self, member, signum):
        if signum not in (signal.SIGSTOP, signal.SIGCONT):
            raise EpisodeOwnershipError('original fixture only permits STOP/CONT')
        if self.kernel.exited(member['fd']):
            raise EpisodeOwnershipError('original fixture died before restoration')
        item = self.kernel.identity(member['identity'].pid)
        if not process._same_process(item, member['identity']):
            raise EpisodeOwnershipError('original fixture identity changed before signal')
        if _nonce(self.kernel, item.pid, ORIGINAL_NONCE_KEY) != [self.nonce]:
            raise EpisodeOwnershipError('original fixture nonce changed before signal')
        self.kernel.send(member['fd'], signum)
        member['signals'].append(signum)

    def pause(self, deadline):
        while time.monotonic() < deadline:
            self.discover()
            for member in self.members.values():
                self._signal(member, signal.SIGSTOP)
            self.discover()
            if all(self._stopped(x['identity'].pid) for x in self.members.values()):
                return
            time.sleep(POLL_SECONDS)
        raise EpisodeOwnershipError('original fixture pause was not observed before deadline')

    def _stopped(self, pid):
        raw = (self.kernel.proc_root / str(pid) / 'stat').read_text()
        return raw[raw.rfind(')') + 1:].split()[0] in ('T', 't')

    def resume(self):
        failures = []
        for member in self.members.values():
            try:
                self._signal(member, signal.SIGCONT)
            except BaseException as error:
                failures.append(str(error))
        return {'members': [{'identity': asdict(x['identity']), 'signals': x['signals']}
                            for x in self.members.values()], 'failures': failures}

    def close(self):
        for member in self.members.values():
            os.close(member['fd'])
        self.members.clear()


class _LeaseSet:
    def __init__(self, directory, acquisition_id):
        self.directory, self.acquisition_id = _absolute(directory), acquisition_id
        self.entries = []

    def acquire(self, selected):
        self.directory.mkdir(mode=0o700, exist_ok=True)
        st = self.directory.stat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise EpisodeOwnershipError('lease directory must be private and UID-owned')
        for gpu in sorted(selected, key=lambda x: x['uuid']):
            path = self.directory / (gpu['uuid'] + '.lease')
            marker = self.directory / (gpu['uuid'] + '.reservation.json')
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            item = {'fd': fd, 'path': str(path), 'marker': str(marker), 'gpu': gpu}
            self.entries.append(item)
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise EpisodeOwnershipError('lease inode must be a private regular file')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            item.update(device=st.st_dev, inode=st.st_ino)
            process._exclusive_json(marker, {'schema_version': 1, 'resource_scope': 'linux_cpu_fixture_only',
                'acquisition_id': self.acquisition_id, 'gpu_uuid': gpu['uuid'], 'boot_id': process.capture_identity(os.getpid()).boot_id})
            marker_st = marker.stat()
            item.update(marker_device=marker_st.st_dev, marker_inode=marker_st.st_ino,
                        marker_sha256=hashlib.sha256(_raw_bytes(marker)).hexdigest())

    def release(self, deadline_monotonic):
        # Only the watchdog calls this after independently verified restoration.
        def require_time():
            if time.monotonic() >= deadline_monotonic:
                raise EpisodeOwnershipError('reservation release crossed its bounded recovery deadline')
        require_time()
        for item in self.entries:
            _check_lease(item, self.acquisition_id)
        require_time()
        for item in self.entries:
            require_time()
            Path(item['marker']).unlink()
            item['marker_released'] = True
        directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        for item in self.entries:
            fcntl.flock(item['fd'], fcntl.LOCK_UN)
        require_time()

    def close(self):
        # Closing cannot erase a persistent unproven-reservation marker.
        for item in self.entries:
            os.close(item['fd'])


def _check_lease(item, acquisition_id):
    fd_st, path_st = os.fstat(item['fd']), os.stat(item['path'], follow_symlinks=False)
    expected = (item['device'], item['inode'])
    if (not stat.S_ISREG(path_st.st_mode) or (fd_st.st_dev, fd_st.st_ino) != expected
            or (path_st.st_dev, path_st.st_ino) != expected or fd_st.st_uid != os.getuid()):
        raise EpisodeOwnershipError('retained lease descriptor/inode/path changed')
    marker_st = os.stat(item['marker'], follow_symlinks=False)
    if (not stat.S_ISREG(marker_st.st_mode)
            or (marker_st.st_dev, marker_st.st_ino) != (item['marker_device'], item['marker_inode'])
            or _json(item['marker']).get('acquisition_id') != acquisition_id
            or hashlib.sha256(_raw_bytes(item['marker'])).hexdigest() != item['marker_sha256']):
        raise EpisodeOwnershipError('persistent reservation marker changed')
    probe_fd = os.open(item['path'], os.O_RDWR | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        fcntl.flock(probe_fd, fcntl.LOCK_UN)
        raise EpisodeOwnershipError('exclusive lease is no longer held')
    finally:
        os.close(probe_fd)


class ResourceEpisodeOwner:
    """Live CPU-fixture owner; its object shape cannot grant production authority."""
    def __init__(self, manifest, kernel=None):
        self._manifest = json.loads(json.dumps(manifest))
        _check_source_closure(manifest.get('source_closure'))
        start, deadline = manifest.get('work_started_monotonic'), manifest.get('work_deadline_monotonic')
        if (type(start) not in (int, float) or type(deadline) not in (int, float)
                or not math.isfinite(start) or not math.isfinite(deadline) or start < 0
                or not 0 < deadline - start <= MAX_WORK_SECONDS):
            raise EpisodeOwnershipError('owner work deadline is missing, invalid or exceeds its bound')
        _bounded(manifest.get('restoration_seconds'), MAX_RESTORATION_SECONDS)
        self._kernel = kernel or process._Kernel()
        self._guard = process.ProcessIdentity(**manifest['guard'])
        self._controller = process.ProcessIdentity(**manifest['controller'])
        self._subject = self._kernel.identity(os.getpid())
        self._guard_fd = self._kernel.open_bound(self._guard)
        try:
            self._controller_fd = self._kernel.open_bound(self._controller)
        except BaseException:
            os.close(self._guard_fd)
            raise
        values = dict(manifest['owner_binding'])
        values.update(resource_scope='linux_cpu_fixture_only', nonce=manifest['nonce'],
                      boot_id=self._guard.boot_id, acquisition_id=manifest['acquisition_id'],
                      gpu_uuid=manifest['leases'][0]['gpu']['uuid'], work_started_monotonic=start,
                      work_deadline_monotonic=deadline, restoration_seconds=manifest['restoration_seconds'],
                      cpu_source_closure=manifest['source_closure'])
        self.bindings = _freeze(values)

    @classmethod
    def from_environment(cls):
        if MANIFEST_KEY not in os.environ:
            raise EpisodeOwnershipError('no inherited CPU episode owner manifest')
        value = _json(_absolute(os.environ[MANIFEST_KEY]))
        owner = cls(value)
        try:
            owner.assert_owned()
        except BaseException:
            owner.close()
            raise
        return owner

    def assert_owned(self):
        try:
            self._check_deadline()
            _check_source_closure(self._manifest['source_closure'])
            current = self._kernel.identity(os.getpid())
            if not process._same_process(current, self._subject):
                raise EpisodeOwnershipError('owner process identity changed')
            if self._kernel.exited(self._guard_fd) or self._kernel.exited(self._controller_fd):
                raise EpisodeOwnershipError('episode guard or controller is no longer alive')
            guard = self._kernel.identity(self._guard.pid)
            controller = self._kernel.identity(self._controller.pid)
            if (guard != self._guard or not process._same_process(controller, self._controller)
                    or guard.ppid != controller.pid or guard.uid != controller.uid
                    or guard.boot_id != controller.boot_id or guard.start_ticks < controller.start_ticks
                    or guard.session != guard.pid or guard.pgrp != guard.pid):
                raise EpisodeOwnershipError('live guard/controller relationship changed')
            if current.pid != guard.pid:
                if (current.ppid != guard.pid or current.session != current.pid or current.pgrp != current.pid
                        or current.start_ticks < guard.start_ticks or current.uid != guard.uid
                        or current.boot_id != guard.boot_id
                        or self._kernel.nonce(current.pid) != [self._manifest['nonce']]):
                    raise EpisodeOwnershipError('owner is not the fresh direct guard-owned worker')
            for item in self._manifest['leases']:
                _check_lease(item, self._manifest['acquisition_id'])
            backend = self._manifest.get('probe_backend', 'cpu_fixture')
            if backend == 'cpu_fixture':
                probe = _gpu_probe(self._manifest['gpu_probe_path'])
            elif backend == 'nvidia_smi':
                probe = read_live_gpu_inventory()
            else:
                raise EpisodeOwnershipError('unsupported fresh GPU probe backend')
            protected = _protected(probe, self._kernel)
            if protected != self._manifest['protected_inventory']:
                raise EpisodeOwnershipError('protected physical GPU0/1 changed')
            inventory = {x['uuid']: x for x in probe['gpus']}
            selected = {x['gpu']['uuid'] for x in self._manifest['leases']}
            for item in self._manifest['leases']:
                observed = inventory.get(item['gpu']['uuid'])
                if (observed is None or _gpu_identity(observed) != _gpu_identity(item['gpu']) or item['gpu']['index'] < 2):
                    raise EpisodeOwnershipError('selected physical GPU fixture identity changed')
                if not any(x['gpu_uuid'] == item['gpu']['uuid'] for x in probe['compute_processes']):
                    _idle_gpu(observed)
            original = {x['identity']['pid']: x['identity'] for x in self._manifest['original_processes']}
            for row in probe['compute_processes']:
                if row['gpu_uuid'] not in selected:
                    continue
                identity = self._kernel.identity(row['pid'])
                if row['pid'] in original:
                    if not process._same_process(identity, process.ProcessIdentity(**original[row['pid']])):
                        raise EpisodeOwnershipError('borrowed fixture compute birth changed')
                    raw = (self._kernel.proc_root / str(identity.pid) / 'stat').read_text()
                    if raw[raw.rfind(')') + 1:].split()[0] not in ('T', 't'):
                        raise EpisodeOwnershipError('borrowed fixture original is no longer paused')
                else:
                    _descendant(self._kernel, identity, guard)
                    if self._kernel.nonce(identity.pid) != [self._manifest['nonce']]:
                        raise EpisodeOwnershipError('compute process has no owned worker nonce')
            self._check_deadline()
            return None
        except EpisodeOwnershipError:
            raise
        except BaseException as error:
            raise EpisodeOwnershipError('live episode ownership cannot be proven: ' + str(error)) from error

    def _check_deadline(self):
        now = time.monotonic()
        if not math.isfinite(now) or now < self._manifest['work_started_monotonic']:
            raise EpisodeOwnershipError('live owner clock is nonfinite or reversed')
        if now >= self._manifest['work_deadline_monotonic']:
            raise EpisodeWorkDeadlineExceeded('live owner work deadline has expired')

    def close(self):
        for key in ('_guard_fd', '_controller_fd'):
            fd = getattr(self, key, None)
            if fd is not None:
                os.close(fd)
                setattr(self, key, None)


def _protected(probe, kernel):
    gpus = [_gpu_identity(x) for x in probe['gpus'] if x['index'] in (0, 1)]
    uuids = {x['uuid'] for x in gpus}
    computes = []
    for row in probe['compute_processes']:
        if row['gpu_uuid'] in uuids:
            current = kernel.identity(row['pid'])
            cmdline = (kernel.proc_root / str(current.pid) / 'cmdline').read_bytes()
            computes.append({**row, 'identity': asdict(current), 'cmdline_sha256': hashlib.sha256(cmdline).hexdigest()})
    return {'gpus': gpus, 'compute_processes': computes}


def _gpu_identity(gpu):
    return {key: gpu[key] for key in ('index', 'uuid', 'name', 'total_memory_mib')}


def _idle_gpu(gpu):
    for sample in gpu.get('idle_samples', [gpu]):
        if ('memory_used_mib' not in sample or 'utilization_percent' not in sample
                or sample['memory_used_mib'] > 16 or sample['utilization_percent'] != 0):
            raise EpisodeOwnershipError('selected GPU has no proven fresh idle memory baseline')


def _selected(probe, indices, original_pids, borrowed):
    if (not isinstance(indices, (list, tuple)) or not indices
            or any(type(x) is not int or x < 2 for x in indices) or len(set(indices)) != len(indices)):
        raise EpisodeOwnershipError('only distinct physical fixture GPUs >=2 may be reserved')
    inventory = {x['index']: x for x in probe['gpus']}
    if any(x not in inventory for x in indices):
        raise EpisodeOwnershipError('selected fixture GPU is absent')
    selected = [inventory[x] for x in sorted(indices)]
    uuids = {x['uuid'] for x in selected}
    if borrowed:
        original_uuids = {x['gpu_uuid'] for x in probe['compute_processes'] if x['pid'] in original_pids}
        if not original_uuids or original_uuids != uuids:
            raise EpisodeOwnershipError('borrowed fixture must reserve all original GPUs together')
    elif len(indices) != 1:
        raise EpisodeOwnershipError('minimal free CPU fixture reserves exactly one GPU')
    if not borrowed:
        for gpu in selected:
            _idle_gpu(gpu)
    for row in probe['compute_processes']:
        if row['gpu_uuid'] in uuids and (not borrowed or row['pid'] not in original_pids):
            raise EpisodeOwnershipError('selected fixture GPU is not proven free of unrelated compute')
    return selected


def _watchdog(declaration_path, channel_fd):
    process._require_linux()
    spec = _json(declaration_path)
    directory = Path(declaration_path).parent
    kernel = process._Kernel()
    controller = process.ProcessIdentity(**spec['controller'])
    guard = kernel.identity(os.getpid())
    controller_fd = None
    original = owner = worker = tree = None
    leases = _LeaseSet(spec['lease_directory'], spec['baseline']['acquisition_id'])
    interrupted = []
    result = {'schema_version': 1, 'resource_scope': 'linux_cpu_fixture_only',
        'acquisition_id': spec['baseline']['acquisition_id'], 'nonce': spec['nonce'],
        'controller': asdict(controller), 'guard': asdict(guard),
        'status': 'cpu_resource_episode_failed', 'reason': 'prerequisite_failed',
        'reservations_released': False, 'quiescence': {'status': 'worker_not_started'},
        'production_execution_available': False, 'queue_restore_proven': False}
    try:
        if (guard.ppid != controller.pid or guard.uid != controller.uid or guard.boot_id != controller.boot_id
                or guard.session != guard.pid or guard.pgrp != guard.pid or guard.start_ticks < controller.start_ticks):
            raise EpisodeOwnershipError('independent resource watchdog is not this fresh controller child')
        controller_fd = kernel.open_bound(controller)
        _check_source_closure(spec.get('source_closure'))
        process._prctl(36, 1)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(signum, lambda signum, frame: interrupted.append(signum))
        audit = _auditor()
        audit.validate_restoration_spec(spec['baseline'], spec['restoration_spec'])
        while True:
            if kernel.exited(controller_fd):
                result['reason'] = 'controller_lost'
                return result
            if interrupted or time.monotonic() >= spec['work_deadline_monotonic']:
                result['reason'] = 'watchdog_interrupted' if interrupted else 'work_deadline'
                return result
            message = process._channel_state(channel_fd)
            if message == b'S':
                break
            if message is not None:
                result['reason'] = 'controller_channel_closed_or_invalid'
                return result
            time.sleep(POLL_SECONDS)
        probe = _gpu_probe(spec['gpu_probe_path'])
        protected = _protected(probe, kernel)
        if protected != spec['baseline']['protected_gpu_inventory']:
            raise EpisodeOwnershipError('fresh protected inventory differs from independent baseline')
        if spec['borrow_originals']:
            original = _OriginalTree(kernel, controller, spec['baseline'], spec['original_fixture_nonce'])
        original_pids = set(original.members) if original is not None else set()
        selected = _selected(probe, spec['gpu_indices'], original_pids, spec['borrow_originals'])
        leases.acquire(selected)
        if original is not None:
            original.pause(spec['work_deadline_monotonic'])
        manifest = {'schema_version': 1, 'resource_scope': 'linux_cpu_fixture_only',
            'controller': asdict(controller), 'guard': asdict(guard), 'nonce': spec['nonce'],
            'acquisition_id': spec['baseline']['acquisition_id'], 'leases': leases.entries,
            'gpu_probe_path': spec['gpu_probe_path'], 'protected_inventory': protected,
            'work_started_monotonic': spec['work_started_monotonic'],
            'work_deadline_monotonic': spec['work_deadline_monotonic'],
            'restoration_seconds': spec['restoration_seconds'],
            'source_closure': spec['source_closure'],
            'original_processes': [{'identity': asdict(x['identity'])} for x in original.members.values()] if original else [],
            'owner_binding': spec['owner_binding']}
        process._exclusive_json(directory / 'owner-manifest.json', manifest)
        owner = ResourceEpisodeOwner(manifest)
        owner.assert_owned()
        environment = process._environment(spec['nonce'])
        environment[MANIFEST_KEY] = str(directory / 'owner-manifest.json')
        with (directory / 'worker.stdout.log').open('xb') as stdout, (directory / 'worker.stderr.log').open('xb') as stderr:
            worker = subprocess.Popen(spec['argv'], stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                close_fds=True, pass_fds=tuple(x['fd'] for x in leases.entries), start_new_session=True,
                env=environment, preexec_fn=lambda: process._worker_parent_death(guard.pid))
        tree = process._OwnedTree(kernel, guard, kernel.identity(worker.pid), spec['nonce'])
        while True:
            tree.discover()
            if kernel.exited(controller_fd):
                result['reason'] = 'controller_lost'
                break
            if interrupted:
                result['reason'] = 'watchdog_interrupted'
                break
            if process._channel_state(channel_fd) is not None:
                result['reason'] = 'controller_channel_closed_or_invalid'
                break
            if time.monotonic() >= spec['work_deadline_monotonic']:
                result['reason'] = 'work_deadline'
                break
            try:
                owner.assert_owned()
            except EpisodeWorkDeadlineExceeded as error:
                result['reason'], result['work_deadline_error'] = 'work_deadline', str(error)
                break
            except EpisodeOwnershipError as error:
                result['ownership_error'] = str(error)
                # Controller exit can cross the earlier pidfd check and owner validation.
                result['reason'] = 'controller_lost' if kernel.exited(controller_fd) else 'ownership_lost'
                break
            if worker.poll() is not None:
                result['reason'] = 'worker_complete' if worker.returncode == 0 else 'worker_failed'
                if any(not kernel.exited(x['fd']) for x in tree.members.values()):
                    result['reason'] = 'descendant_outlived_worker'
                break
            time.sleep(POLL_SECONDS)
    except EpisodeWorkDeadlineExceeded as error:
        result['reason'], result['work_deadline_error'] = 'work_deadline', str(error)
    except BaseException as error:
        result['error'] = str(error)
        result['reason'] = 'watchdog_error'
    finally:
        recovery_started = time.monotonic()
        recovery_deadline = recovery_started + spec['restoration_seconds']
        result['recovery_started_monotonic'] = recovery_started
        result['recovery_deadline_monotonic'] = recovery_deadline
        result['recovery_started_epoch_s'] = time.time()
        owned_processes = []
        cleanup_proven = worker is None
        if worker is not None:
            try:
                if tree is None:
                    tree = process._OwnedTree(kernel, guard, kernel.identity(worker.pid), spec['nonce'])
                result['quiescence'] = tree.quiesce(worker, min(10.0, spec['restoration_seconds']))
                result['ownership_errors'] = tree.errors
                owned_processes = [asdict(x['identity']) for x in tree.members.values()]
                cleanup_proven = not tree.errors
            except BaseException as error:
                result['quiescence'] = {'status': 'owned_worker_quiescence_unproven', 'error': str(error)}
        if original is not None:
            result['original_resume'] = original.resume()
        try:
            audit = _auditor()
            observations = audit.observe_restore(spec['baseline'], owned_processes,
                recovery_started_monotonic=recovery_started, recovery_deadline_monotonic=recovery_deadline,
                proc_root=spec['restoration_spec']['proc_root'],
                poll_interval_s=spec['restoration_spec']['poll_interval_s'],
                gpu_fixture_path=spec['gpu_probe_path'], original_parent_identity=asdict(controller))
            process._exclusive_json(directory / 'restoration-observations.json', observations)
            verification = audit.verify_restoration(spec['baseline'], observations)
            result['restoration_verification'] = verification
            process._exclusive_json(directory / 'restoration-verification.json', verification)
            if (cleanup_proven and not result.get('original_resume', {}).get('failures')
                    and verification.get('status') == 'same_process_resource_recovery_observed'
                    and verification.get('failures') == []
                    and verification.get('queue_restore_proven') is False
                    and verification.get('execution_available') is False
                    and verification.get('resource_authority') is False):
                if leases.entries:
                    leases.release(recovery_deadline)
                if time.monotonic() >= recovery_deadline:
                    raise EpisodeOwnershipError('independent restoration publication exceeded its deadline')
                result['reservations_released'] = True
                if result['reason'] == 'worker_complete':
                    result['status'] = 'cpu_resource_episode_complete'
        except BaseException as error:
            result['restoration_error'] = str(error)
            result['partial_reservation_release'] = [x['gpu']['uuid'] for x in leases.entries if x.get('marker_released')]
        if tree is not None:
            tree.close()
        if original is not None:
            original.close()
        if owner is not None:
            owner.close()
        leases.close()
        if controller_fd is not None:
            os.close(controller_fd)
        os.close(channel_fd)
        result['interrupted_signals'] = interrupted
        process._exclusive_json(directory / 'watchdog-receipt.json', result)
    return result


def run_cpu_resource_episode(argv, *, episode_directory, baseline, restoration_spec,
        lease_directory, gpu_probe_path, gpu_indices, owner_binding, timeout_seconds=MAX_WORK_SECONDS,
        restoration_seconds=MAX_RESTORATION_SECONDS, borrow_originals=False, original_fixture_nonce=None):
    """Exercise a fresh independent guard using trusted Linux CPU fixture code.

    Baseline/spec are independently validated before any launch or reservation.
    GPU records are injected fixtures; CUDA visibility stays empty. The episode
    directory must be outside the scientific task directory. No retry is allowed.
    """
    process._require_linux()
    if threading.current_thread() is not threading.main_thread():
        raise ValueError('resource episode controller must run in the main thread')
    if (not isinstance(argv, (list, tuple)) or not argv or not Path(argv[0]).is_absolute()
            or any(not isinstance(x, str) or '\0' in x for x in argv)):
        raise ValueError('an absolute executable argv is required')
    work = _bounded(timeout_seconds, MAX_WORK_SECONDS)
    restoration = _bounded(restoration_seconds, MAX_RESTORATION_SECONDS)
    if type(borrow_originals) is not bool or not isinstance(owner_binding, dict):
        raise ValueError('explicit fixture mode and owner bindings are required')
    directory, lease_path, probe_path = map(_absolute, (episode_directory, lease_directory, gpu_probe_path))
    if not isinstance(baseline, dict) or baseline.get('node_alias') not in ELIGIBLE_NODES:
        raise ValueError('episode requires an eligible fresh baseline')
    if baseline.get('mode') != ('borrowed_same_process' if borrow_originals else 'no_borrow'):
        raise ValueError('fixture mode and independent baseline disagree')
    _auditor().validate_restoration_spec(baseline, restoration_spec)
    if (restoration_spec['max_recovery_seconds'] != restoration
            or restoration_spec['gpu_fixture_path'] != str(probe_path)
            or restoration_spec['proc_root'] != '/proc'):
        raise ValueError('restoration bounds and raw CPU fixture path must match episode')
    task = owner_binding.get('task_directory')
    if task and (_absolute(task) == directory or _absolute(task) in directory.parents):
        raise ValueError('episode metadata must be outside the scientific task directory')
    kernel = process._Kernel()
    controller = kernel.identity(os.getpid())
    if baseline['boot_id'] != controller.boot_id or baseline['uid'] != controller.uid:
        raise EpisodeOwnershipError('baseline UID/boot differs from current controller')
    probe = _gpu_probe(probe_path)
    original = None
    try:
        if borrow_originals:
            original = _OriginalTree(kernel, controller, baseline, original_fixture_nonce)
        _selected(probe, gpu_indices, set(original.members) if original else set(), borrow_originals)
    finally:
        if original is not None:
            original.close()
    nonce = secrets.token_hex(32)
    work_started = time.monotonic()
    spec = {'schema_version': 1, 'resource_scope': 'linux_cpu_fixture_only', 'argv': list(argv),
        'controller': asdict(controller), 'baseline': baseline, 'restoration_spec': restoration_spec,
        'gpu_probe_path': str(probe_path), 'gpu_indices': list(gpu_indices), 'lease_directory': str(lease_path),
        'owner_binding': owner_binding, 'borrow_originals': borrow_originals,
        'original_fixture_nonce': original_fixture_nonce, 'nonce': nonce,
        'work_started_monotonic': work_started,
        'work_deadline_monotonic': work_started + work, 'restoration_seconds': restoration}
    spec['source_closure'] = _source_closure()
    directory.mkdir(mode=0o700)
    declaration = directory / 'declaration.json'
    process._exclusive_json(declaration, spec)
    read_fd, write_fd = os.pipe()
    guard = guard_fd = None
    interrupted, previous = [], {}
    try:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[signum] = signal.signal(signum, lambda signum, frame: interrupted.append(signum))
        with (directory / 'watchdog.stderr.log').open('xb') as stderr:
            guard = subprocess.Popen([sys.executable, '-I', '-S', str(Path(__file__).resolve()),
                '--cpu-fixture-watchdog', str(declaration), '--channel-fd', str(read_fd)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=stderr,
                start_new_session=True, close_fds=True, pass_fds=(read_fd,), env=process._environment(nonce))
        guard_identity = kernel.identity(guard.pid)
        if (guard_identity.ppid != controller.pid or guard_identity.uid != controller.uid
                or guard_identity.boot_id != controller.boot_id):
            raise EpisodeOwnershipError('new resource guard is not this controller child')
        guard_fd = kernel.open_bound(guard_identity)
        if not interrupted and not kernel.exited(guard_fd):
            os.write(write_fd, b'S')
        while not kernel.exited(guard_fd):
            if interrupted and write_fd is not None:
                os.close(write_fd)
                write_fd = None
            if time.monotonic() > spec['work_deadline_monotonic'] + restoration + 2:
                raise ResourceEpisodeError('watchdog restoration completion is unproven')
            time.sleep(POLL_SECONDS)
        guard.wait(timeout=1)
        receipt = _json(directory / 'watchdog-receipt.json')
        if (receipt.get('nonce') != nonce or receipt.get('controller') != asdict(controller)
                or receipt.get('guard') != asdict(guard_identity)):
            raise ResourceEpisodeError('resource watchdog receipt identity mismatch', receipt)
        if (interrupted or guard.returncode != 0 or receipt.get('status') != 'cpu_resource_episode_complete'
                or receipt.get('reservations_released') is not True):
            raise ResourceEpisodeError('CPU resource episode failed closed', receipt)
        return receipt
    finally:
        for fd in (read_fd, write_fd, guard_fd):
            if fd is not None:
                os.close(fd)
        if guard is not None and guard.returncode is None:
            try:
                guard.wait(timeout=restoration + 2)
            except subprocess.TimeoutExpired:
                pass
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu-fixture-watchdog')
    parser.add_argument('--channel-fd', type=int)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    if args.execute or not args.cpu_fixture_watchdog or args.channel_fd is None:
        raise ResourceEpisodeError('production resource launch is unavailable; fresh host/source and optimizer-boundary integration required')
    result = _watchdog(_absolute(args.cpu_fixture_watchdog), args.channel_fd)
    return 0 if result['status'] == 'cpu_resource_episode_complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
