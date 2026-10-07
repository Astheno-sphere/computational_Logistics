"""Read current Linux resource facts. A capture is never a GPU lease.

The borrowed queue adapter and optimizer-boundary proof are deliberately absent.
This reader can inventory a specified same-process queue for later independent
auditing; neither an owner name nor low utilization establishes authorization.
"""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import time

from scripts.frontier_v8_owned_process import capture_identity


NODES = {'ms-n1-1': '100.64.180.123', 'ms-n1-3': '100.113.206.109',
         'ms-n4-1': '100.73.246.72', 'ms-n4-2': '100.88.50.20',
         'ms-n4-3': '100.94.49.109', 'ms-n4-4': '100.112.105.35'}
HASH = re.compile(r'[0-9a-f]{64}')
GPU_UUID = re.compile(r'GPU-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')


class CaptureError(ValueError):
    pass


def _absolute(path):
    p = Path(path)
    if not p.is_absolute() or p.resolve() != p:
        raise CaptureError('absolute paths without symlink ancestors required')
    return p


def fullhash(path):
    """Hash regular bytes while checking both the path and open-file identity."""
    p = _absolute(path)
    before = p.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise CaptureError('inventory leaf is not a regular file')
    descriptor = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        opened = os.fstat(descriptor)
        fingerprint = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if fingerprint(before) != fingerprint(opened):
            raise CaptureError('inventory identity changed before hashing')
        digest = hashlib.sha256()
        with os.fdopen(descriptor, 'rb', closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024*1024), b''):
                digest.update(chunk)
        if (fingerprint(opened) != fingerprint(os.fstat(descriptor))
                or fingerprint(opened) != fingerprint(p.stat(follow_symlinks=False))):
            raise CaptureError('inventory bytes or path changed during hashing')
        return {'path': str(p), 'size': opened.st_size, 'sha256': digest.hexdigest()}
    finally:
        os.close(descriptor)


def inventory(roots, files):
    """Require complete declared directory trees; reject all special leaves."""
    selected = set()
    normalized = []
    def leaves_of(root):
        leaves = set()
        identities = {}
        def scan_error(error):
            raise CaptureError('inventory directory scan failed') from error
        for current, directories, names in os.walk(root, followlinks=False, onerror=scan_error):
            current = _absolute(current)
            info = current.stat(follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                raise CaptureError('inventory directory changed type')
            identities[str(current)] = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns)
            for name in directories:
                p = Path(current)/name
                if p.is_symlink() or not p.is_dir():
                    raise CaptureError('inventory directory symlink or special node')
            leaves.update(Path(current)/name for name in names)
        return leaves, identities
    directory_identities = {}
    for path in roots:
        root = _absolute(path)
        if not root.is_dir() or any(root == x or root.is_relative_to(x)
                                    or x.is_relative_to(root) for x in normalized):
            raise CaptureError('inventory roots overlap or are not directories')
        normalized.append(root)
        leaves, identities = leaves_of(root)
        selected.update(leaves)
        directory_identities.update(identities)
    for path in files:
        p = _absolute(path)
        if p in selected:
            raise CaptureError('duplicate inventory file')
        selected.add(p)
    result = [fullhash(p) for p in sorted(selected)]
    # A new/deleted file is not hidden by a successful hash of earlier leaves.
    after, after_identities = set(), {}
    for root in normalized:
        leaves, identities = leaves_of(root)
        after.update(leaves)
        after_identities.update(identities)
    expected = {p for p in selected if any(p.is_relative_to(root) for root in normalized)}
    if after != expected or directory_identities != after_identities:
        raise CaptureError('inventory tree changed during hashing')
    return result


def process_fact(pid, proc_root=Path('/proc')):
    before = capture_identity(pid, proc_root)
    command = (Path(proc_root)/str(pid)/'cmdline').read_bytes()
    status = (Path(proc_root)/str(pid)/'stat').read_text()
    state = status[status.rfind(')')+1:].split()[0]
    after = capture_identity(pid, proc_root)
    if before != after or state in ('Z', 'X', 'x') or not command:
        raise CaptureError('process changed or is not live')
    return {'identity': asdict(before), 'cmdline_sha256': hashlib.sha256(command).hexdigest(),
            'state': state}


def gpu_query():
    results = []
    for query in ('--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu',
                  '--query-compute-apps=gpu_uuid,pid,process_name'):
        argv = ['/usr/bin/nvidia-smi', query, '--format=csv,noheader,nounits']
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=10, check=False)
        if result.returncode or result.stderr:
            raise CaptureError('GPU read-only query failed')
        results.append(result.stdout)
    return tuple(results)


def parse_gpu(raw, proc_root=Path('/proc')):
    gpu_text, compute_text = raw
    gpus, apps = [], []
    for row in csv.reader(gpu_text.splitlines(), skipinitialspace=True):
        row = [x.strip() for x in row]
        if len(row) != 6 or not GPU_UUID.fullmatch(row[1]) or 'H100' not in row[2]:
            raise CaptureError('invalid H100 GPU inventory')
        index, total, memory, utilization = map(int, [row[0], *row[3:]])
        if index < 0 or total <= 0 or not 0 <= memory <= total or not 0 <= utilization <= 100:
            raise CaptureError('invalid GPU numeric observation')
        gpus.append({'index': index, 'uuid': row[1], 'name': row[2],
                     'total_memory_mib': total, 'memory_used_mib': memory,
                     'utilization_percent': utilization})
    if (len(gpus) != 8 or {x['index'] for x in gpus} != set(range(8))
            or len({x['uuid'] for x in gpus}) != 8):
        raise CaptureError('expected eight unique physical H100s')
    uuids = {x['uuid'] for x in gpus}
    for row in csv.reader(compute_text.splitlines(), skipinitialspace=True):
        row = [x.strip() for x in row]
        if len(row) != 3 or row[0] not in uuids or not row[1].isdigit():
            raise CaptureError('invalid compute-process inventory')
        fact = process_fact(int(row[1]), proc_root)
        apps.append({'gpu_uuid': row[0], 'pid': int(row[1]), 'process_name': row[2],
                     'identity': fact['identity'], 'cmdline_sha256': fact['cmdline_sha256']})
    if len({(x['gpu_uuid'], x['pid']) for x in apps}) != len(apps):
        raise CaptureError('duplicate compute-process observation')
    return {'gpus': sorted(gpus, key=lambda x: x['index']),
            'compute_processes': sorted(apps, key=lambda x: (x['gpu_uuid'], x['pid'])),
            'raw_gpu_csv': gpu_text, 'raw_compute_csv': compute_text}


def protected_inventory(sample):
    gpus = [{key: gpu[key] for key in ('index', 'uuid', 'name', 'total_memory_mib')}
            for gpu in sample['gpus'] if gpu['index'] in (0, 1)]
    protected = {gpu['uuid'] for gpu in gpus}
    return {'gpus': gpus, 'compute_processes': [x for x in sample['compute_processes']
                                              if x['gpu_uuid'] in protected]}


def _progress_value(spec):
    if (spec['extractor'] != 'json_integer' or not isinstance(spec['key_path'], list)
            or not spec['key_path'] or any(not isinstance(k, str) or not k for k in spec['key_path'])):
        raise CaptureError('unsupported progress extractor')
    p = _absolute(spec['path'])
    if not p.is_file() or p.is_symlink():
        raise CaptureError('progress path is not regular')
    value = json.loads(p.read_text())
    for key in spec['key_path']:
        value = value[key]
    if type(value) is not int or value < 0:
        raise CaptureError('progress is not a nonnegative integer')
    return value


def capture_current(request, *, proc_root=Path('/proc'), query=gpu_query,
                    clock=time.monotonic, sleep=time.sleep):
    """Read-only snapshot with two vacancy samples, never a reservation grant.

    Actual request paths must already exist on the selected host. Runtime/data/
    source/weight files are supplied as exact expected hashes and fully reread.
    This does not import Torch, parse heldout rows or prove optimizer semantics.
    """
    if (request.get('schema_version') != 1 or request.get('node_alias') not in NODES
            or not re.fullmatch(r'[0-9a-f]{32}', request.get('acquisition_id', ''))
            or request.get('mode') not in ('no_borrow', 'borrowed_same_process')):
        raise CaptureError('invalid fresh capture request')
    uid = os.getuid()
    observer = process_fact(os.getpid(), proc_root)['identity']
    if observer['uid'] != uid:
        raise CaptureError('observer UID differs')
    before_time = clock()
    first = parse_gpu(query(), proc_root)
    sleep(0.1)
    second = parse_gpu(query(), proc_root)
    after_time = clock()
    if (not math.isfinite(after_time) or not 0.1 <= after_time-before_time <= 30
            or protected_inventory(first) != protected_inventory(second)):
        raise CaptureError('GPU samples/protected state changed during capture')
    records = inventory(request.get('immutable_roots', []), request.get('immutable_files', []))
    required = request.get('expected_files_sha256', {})
    observed = {x['path']: x['sha256'] for x in records}
    if (not isinstance(required, dict) or any(not HASH.fullmatch(h) for h in required.values())
            or any(observed.get(str(_absolute(p))) != h for p, h in required.items())):
        raise CaptureError('current source/runtime/data/weight file hash mismatch')
    originals = []
    for item in request.get('original_processes', []):
        fact = process_fact(item['pid'], proc_root)
        if fact['identity']['uid'] != uid or fact['identity']['boot_id'] != observer['boot_id']:
            raise CaptureError('original queue UID/boot differs; capture refuses control scope')
        originals.append({'role': item['role'], 'ordinal': item['ordinal'],
                          'identity': fact['identity'], 'cmdline_sha256': fact['cmdline_sha256']})
    progress = [{**spec, 'before_value': _progress_value(spec)}
                for spec in request.get('progress', [])]
    if request['mode'] == 'no_borrow' and (originals or progress or request.get('services')):
        raise CaptureError('no_borrow cannot contain original queue state')
    occupied = {x['gpu_uuid'] for s in (first, second) for x in s['compute_processes']}
    candidate_vacant = [x['uuid'] for x in second['gpus'] if x['index'] >= 2
                        and x['uuid'] not in occupied and x['memory_used_mib'] <= 16
                        and x['utilization_percent'] == 0
                        and any(y['uuid'] == x['uuid'] and y['index'] == x['index']
                                and y['memory_used_mib'] <= 16 and y['utilization_percent'] == 0
                                for y in first['gpus'])]
    result = {'schema_version': 1, 'mode': request['mode'],
              'acquisition_id': request['acquisition_id'], 'node_alias': request['node_alias'],
              'boot_id': observer['boot_id'], 'uid': uid, 'hostname': socket.gethostname(),
              'observer': observer, 'gpu_samples_monotonic': [before_time, after_time],
              'gpu_samples': [first, second], 'candidate_vacant_gpu_uuids': candidate_vacant,
              'protected_gpu_inventory': protected_inventory(second),
              'immutable_roots': request.get('immutable_roots', []), 'immutable_files': records,
              'original_processes': originals, 'services': request.get('services', []),
              'progress': progress, 'actual_optimizer_boundary_verified': False,
              'resource_authority': False, 'execution_available': False,
              'limits': ['Snapshot only, not a lease. Vacancy must be freshly rechecked under a live reservation.',
                         'Declared bytes do not prove package ABI or a recoverable optimizer boundary.',
                         'No borrowed queue adapter or foreign-process control is provided by this reader.']}
    after_observer = process_fact(os.getpid(), proc_root)['identity']
    if observer != after_observer:
        raise CaptureError('observer changed during full capture')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--read-only', action='store_true')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    if args.execute or not args.read_only:
        raise CaptureError('capture has no execution or queue-control entry point')
    if args.request is None:
        raise CaptureError('read-only capture requires a current request')
    print(json.dumps(capture_current(json.loads(args.request.read_text())), indent=2,
                     sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
