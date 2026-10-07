"""Independent read-only recovery observations; no queue or execution authority.

Reads Linux proc files, complete immutable inventories, loopback HTTP, progress
and fresh GPU query bytes. It imports neither the episode nor capture code.
The public CLI remains closed; injected inputs are explicit CPU fixtures.
"""
import base64
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


NODES = {'ms-n1-1', 'ms-n1-3', 'ms-n4-1', 'ms-n4-2', 'ms-n4-3', 'ms-n4-4'}
IDENTITY = {'boot_id', 'pid', 'uid', 'start_ticks', 'ppid', 'pgrp', 'session'}
HEX = re.compile(r'[0-9a-f]{64}')
BOOT = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
MAX_BYTES = 1024 * 1024


class RestorationAuditError(ValueError):
    pass


def require(value, message):
    if not value:
        raise RestorationAuditError(message)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _absolute(value):
    require(isinstance(value, str) and Path(value).is_absolute()
            and Path(value).as_posix() == value and '..' not in Path(value).parts,
            'regular absolute path required')
    return Path(value)


def _identity(value):
    require(isinstance(value, dict) and set(value) == IDENTITY, 'exact process identity required')
    require(isinstance(value['boot_id'], str) and BOOT.fullmatch(value['boot_id']), 'boot identity required')
    for name in IDENTITY - {'boot_id'}:
        require(type(value[name]) is int and value[name] >= (0 if name in ('uid', 'ppid') else 1),
                'integer process identity required: ' + name)
    return value


def _service(value):
    require(isinstance(value, dict) and set(value) == {'url', 'process_pid', 'expected_status'},
            'exact service spec required')
    parsed = urlsplit(value['url'])
    require(parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', '::1')
            and parsed.username is None and parsed.password is None and not parsed.fragment
            and parsed.port is not None and 1 <= parsed.port <= 65535,
            'explicit loopback HTTP endpoint required')
    require(type(value['process_pid']) is int and value['process_pid'] > 0
            and type(value['expected_status']) is int and value['expected_status'] == 200,
            'service PID and status200 required')


def _progress_spec(value):
    require(isinstance(value, dict)
            and set(value) == {'path', 'extractor', 'key_path', 'before_value'},
            'exact progress spec required')
    _absolute(value['path'])
    require(value['extractor'] == 'json_integer' and isinstance(value['key_path'], list)
            and value['key_path'] and all(isinstance(k, str) and k for k in value['key_path'])
            and type(value['before_value']) is int and value['before_value'] >= 0,
            'integer JSON progress required')


def _protected_shape(value):
    require(isinstance(value, dict) and set(value) == {'gpus', 'compute_processes'},
            'protected GPU inventory required')
    require(isinstance(value['gpus'], list) and len(value['gpus']) == 2
            and {g['index'] for g in value['gpus']} == {0, 1}, 'physical GPU0/1 required')
    for gpu in value['gpus']:
        require(set(gpu) == {'index', 'uuid', 'name', 'total_memory_mib'}
                and type(gpu['index']) is int and isinstance(gpu['uuid'], str)
                and gpu['uuid'].startswith('GPU-') and isinstance(gpu['name'], str) and gpu['name']
                and type(gpu['total_memory_mib']) is int and gpu['total_memory_mib'] > 0,
                'typed protected GPU metadata required')
    uuids = {g['uuid'] for g in value['gpus']}
    require(len(uuids) == 2 and isinstance(value['compute_processes'], list), 'unique protected GPUs required')
    pairs = []
    for item in value['compute_processes']:
        require(set(item) == {'gpu_uuid', 'pid', 'process_name', 'identity', 'cmdline_sha256'}
                and item['gpu_uuid'] in uuids and isinstance(item['process_name'], str),
                'typed protected compute identity required')
        _identity(item['identity'])
        require(item['pid'] == item['identity']['pid'] and HEX.fullmatch(item['cmdline_sha256']),
                'protected process binding required')
        pairs.append((item['gpu_uuid'], item['pid']))
    require(len(set(pairs)) == len(pairs), 'duplicate protected compute PID')


def validate_baseline(baseline):
    required = {'schema_version', 'mode', 'acquisition_id', 'node_alias', 'boot_id', 'uid',
                'immutable_roots', 'immutable_files', 'original_processes', 'services', 'progress',
                'protected_gpu_inventory', 'actual_optimizer_boundary_verified'}
    metadata = {'hostname', 'observer', 'gpu_samples_monotonic', 'gpu_samples',
                'candidate_vacant_gpu_uuids', 'resource_authority', 'execution_available', 'limits'}
    require(isinstance(baseline, dict) and required <= set(baseline)
            and set(baseline) <= required | metadata, 'strict recovery baseline required')
    require(type(baseline['schema_version']) is int and baseline['schema_version'] == 1
            and baseline['mode'] in ('no_borrow', 'borrowed_same_process')
            and isinstance(baseline['acquisition_id'], str)
            and re.fullmatch('[0-9a-f]{32}', baseline['acquisition_id'])
            and baseline['node_alias'] in NODES and BOOT.fullmatch(baseline['boot_id'])
            and type(baseline['uid']) is int and baseline['uid'] >= 0,
            'fresh typed acquisition identity required')
    require(baseline['actual_optimizer_boundary_verified'] is False
            and baseline.get('resource_authority', False) is False
            and baseline.get('execution_available', False) is False,
            'CPU observation cannot assert optimizer boundary or execution authority')
    roots = baseline['immutable_roots']; files = baseline['immutable_files']
    require(isinstance(roots, list) and isinstance(files, list), 'immutable inventory lists required')
    for root in roots:
        _absolute(root)
    require(len(set(roots)) == len(roots)
            and all(not Path(a).is_relative_to(Path(b)) for a in roots for b in roots if a != b),
            'unique disjoint immutable roots required')
    for item in files:
        require(isinstance(item, dict) and set(item) == {'path', 'size', 'sha256'},
                'exact immutable file fingerprint required')
        _absolute(item['path'])
        require(type(item['size']) is int and item['size'] >= 0 and HEX.fullmatch(item['sha256']),
                'full immutable hash and size required')
    require(len({f['path'] for f in files}) == len(files), 'duplicate immutable file')
    originals = baseline['original_processes']; services = baseline['services']; progress = baseline['progress']
    require(all(isinstance(v, list) for v in (originals, services, progress)), 'typed queue lists required')
    for item in originals:
        require(isinstance(item, dict)
                and set(item) == {'role', 'ordinal', 'identity', 'cmdline_sha256'}
                and item['role'] in ('rank', 'coordinator', 'service')
                and type(item['ordinal']) is int and item['ordinal'] >= 0,
                'typed original role required')
        _identity(item['identity'])
        require(item['identity']['boot_id'] == baseline['boot_id']
                and item['identity']['uid'] == baseline['uid'] and HEX.fullmatch(item['cmdline_sha256']),
                'original UID/boot/command binding required')
    require(len({p['identity']['pid'] for p in originals}) == len(originals), 'duplicate original PID')
    for service in services:
        _service(service)
    for item in progress:
        _progress_spec(item)
    require(len({s['url'] for s in services}) == len(services)
            and len({p['path'] for p in progress}) == len(progress), 'duplicate endpoint/progress path')
    if baseline['mode'] == 'no_borrow':
        require(not originals and not services and not progress, 'no_borrow cannot claim queue recovery')
    else:
        require({(p['role'], p['ordinal']) for p in originals}
                == {('rank', i) for i in range(4)} | {('coordinator', 0)} | {('service', i) for i in range(3)}
                and len(originals) == 8 and len(services) == 3 and progress and roots and files,
                'borrowed recovery requires four ranks/coordinator/three services/tree/progress')
        require({s['process_pid'] for s in services}
                == {p['identity']['pid'] for p in originals if p['role'] == 'service'},
                'service endpoints must bind original service PIDs')
    _protected_shape(baseline['protected_gpu_inventory'])
    return baseline


def validate_restoration_spec(baseline, restoration_spec):
    validate_baseline(baseline)
    require(isinstance(restoration_spec, dict)
            and set(restoration_spec) == {'schema_version', 'max_recovery_seconds', 'poll_interval_s',
                                         'proc_root', 'gpu_fixture_path'}, 'strict restoration spec required')
    require(type(restoration_spec['schema_version']) is int and restoration_spec['schema_version'] == 1
            and _number(restoration_spec['max_recovery_seconds'])
            and 0 < restoration_spec['max_recovery_seconds'] <= 1500
            and _number(restoration_spec['poll_interval_s'])
            and 0 < restoration_spec['poll_interval_s'] <= 60, 'bounded recovery required')
    _absolute(restoration_spec['proc_root'])
    if restoration_spec['gpu_fixture_path'] is not None:
        _absolute(restoration_spec['gpu_fixture_path'])
    return restoration_spec


def _b64(raw):
    return base64.b64encode(raw).decode('ascii')


def _bytes(value):
    return base64.b64decode(value, validate=True)


def _read(path, limit=MAX_BYTES):
    path = Path(path)
    require(path.resolve() == path and stat.S_ISREG(path.lstat().st_mode), 'regular non-symlink input required')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'raw input exceeds bounded read')
    return raw


def _parse_stat(raw, pid):
    text = raw.decode('utf-8'); closing = text.rfind(')')
    require(closing > 0 and int(text[:text.index('(')].strip()) == pid, 'proc stat PID differs')
    fields = text[closing + 1:].split()
    require(len(fields) >= 20, 'short proc stat')
    return {'pid': pid, 'ppid': int(fields[1]), 'pgrp': int(fields[2]),
            'session': int(fields[3]), 'start_ticks': int(fields[19])}, fields[0]


def _parse_process(raw, boot, require_command=True):
    require(isinstance(raw, dict) and set(raw) == {'pid', 'stat', 'status', 'cmdline'}, 'raw process required')
    values, state = _parse_stat(_bytes(raw['stat']), raw['pid'])
    matches = re.findall(rb'^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', _bytes(raw['status']), re.M)
    require(len(matches) == 1 and len(set(matches[0])) == 1, 'process real/effective/saved/fs UIDs differ')
    identity = {'boot_id': boot, 'uid': int(matches[0][0]), **values}
    _identity(identity)
    command = _bytes(raw['cmdline'])
    require(command or not require_command, 'empty live cmdline')
    return {'identity': identity, 'state': state, 'cmdline_sha256': hashlib.sha256(command).hexdigest()}


def _proc(pid, root):
    p = root / str(pid)
    if not p.exists():
        return None
    before = _read(p / 'stat')
    result = {'pid': pid, 'stat': _b64(before), 'status': _b64(_read(p / 'status')),
              'cmdline': _b64(_read(p / 'cmdline'))}
    require(_parse_stat(before, pid)[0] == _parse_stat(_read(p / 'stat'), pid)[0],
            'process identity changed during capture')
    return result


def _tree(root, remaining=lambda: None):
    require(root.resolve() == root and stat.S_ISDIR(root.lstat().st_mode), 'regular immutable root required')
    paths = []
    def traversal_error(error):
        raise RestorationAuditError('immutable tree traversal failed: ' + str(error))
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=traversal_error):
        remaining()
        for name in dirs:
            require(stat.S_ISDIR((Path(directory) / name).lstat().st_mode), 'symlink/special immutable directory')
        for name in files:
            remaining()
            path = Path(directory) / name
            require(stat.S_ISREG(path.lstat().st_mode), 'symlink/special immutable leaf')
            paths.append(str(path))
    return sorted(paths)


def _fingerprint(path, remaining):
    require(path.resolve() == path, 'immutable path has symlink parent')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.fstat(fd); require(stat.S_ISREG(before.st_mode), 'immutable file is not regular')
        digest = hashlib.sha256()
        while True:
            remaining(); chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(fd); leaf = path.lstat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and (leaf.st_dev, leaf.st_ino, leaf.st_size, leaf.st_mtime_ns, leaf.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                'immutable file changed while hashing')
        return {'path': str(path), 'size': after.st_size, 'sha256': digest.hexdigest()}
    finally:
        os.close(fd)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http(url, timeout, http_open):
    opener = http_open or build_opener(ProxyHandler({}), _NoRedirect()).open
    try:
        with opener(url, timeout=timeout) as response:
            body = response.read(MAX_BYTES + 1); status_code = response.getcode()
        require(len(body) <= MAX_BYTES, 'HTTP body too large')
        return {'url': url, 'status': status_code, 'body': _b64(body), 'body_sha256': hashlib.sha256(body).hexdigest()}
    except HTTPError as exc:
        body = exc.read(MAX_BYTES + 1); exc.close()
        require(len(body) <= MAX_BYTES, 'HTTP error body too large')
        return {'url': url, 'status': exc.code, 'body': _b64(body), 'body_sha256': hashlib.sha256(body).hexdigest()}


def _gpu_query(timeout):
    result = {}
    deadline = time.monotonic() + timeout
    for key, query in [('gpu_csv', 'index,uuid,name,memory.total'),
                       ('compute_csv', 'gpu_uuid,pid,process_name')]:
        flag = '--query-gpu=' if key == 'gpu_csv' else '--query-compute-apps='
        result[key] = subprocess.check_output(['/usr/bin/nvidia-smi', flag + query, '--format=csv,noheader,nounits'],
                                              timeout=max(0.001, min(deadline - time.monotonic(), 5)),
                                              stderr=subprocess.PIPE,
                                              env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
    return result


def _gpu_payload(payload):
    if isinstance(payload, bytes):
        return {'format': 'json', 'raw': _b64(payload)}
    require(isinstance(payload, dict) and set(payload) == {'gpu_csv', 'compute_csv'}
            and all(isinstance(v, bytes) for v in payload.values()), 'raw GPU query bytes required')
    return {'format': 'csv', **{k: _b64(v) for k, v in payload.items()}}


def _parse_gpu(raw):
    if raw['format'] == 'json':
        payload = json.loads(_bytes(raw['raw'])); gpus = payload['gpus']; apps = payload['compute_processes']
    else:
        require(raw['format'] == 'csv', 'raw GPU format differs')
        gpus = []
        for row in csv.reader(io.StringIO(_bytes(raw['gpu_csv']).decode()), skipinitialspace=True):
            require(len(row) == 4, 'GPU CSV width differs')
            gpus.append({'index': int(row[0]), 'uuid': row[1].strip(), 'name': row[2].strip(),
                         'total_memory_mib': int(row[3])})
        apps = []
        for row in csv.reader(io.StringIO(_bytes(raw['compute_csv']).decode()), skipinitialspace=True):
            require(len(row) == 3, 'compute CSV width differs')
            apps.append({'gpu_uuid': row[0].strip(), 'pid': int(row[1]), 'process_name': row[2].strip()})
    require(isinstance(gpus, list) and isinstance(apps, list), 'raw GPU lists required')
    selected = [{k: g[k] for k in ('index', 'uuid', 'name', 'total_memory_mib')}
                for g in gpus if g['index'] in (0, 1)]
    require(len(selected) == 2 and {g['index'] for g in selected} == {0, 1}, 'protected GPU metadata missing/duplicate')
    ids = {g['uuid'] for g in selected}
    selected_apps = [{k: a[k] for k in ('gpu_uuid', 'pid', 'process_name')}
                     for a in apps if a['gpu_uuid'] in ids]
    require(len({(a['gpu_uuid'], a['pid']) for a in selected_apps}) == len(selected_apps), 'duplicate protected compute PID')
    return sorted(selected, key=lambda g: g['index']), sorted(selected_apps, key=lambda a: (a['gpu_uuid'], a['pid']))


def _progress_value(raw, spec):
    value = json.loads(_bytes(raw['body']))
    for key in spec['key_path']:
        require(isinstance(value, dict) and key in value, 'progress key missing')
        value = value[key]
    require(type(value) is int and value >= 0, 'progress is not an integer')
    return value


def _collect(baseline, owned, proc_root, remaining, http_open, gpu_query, gpu_fixture_path, original_parent):
    boot = _read(proc_root / 'sys/kernel/random/boot_id')
    trees = {r: _tree(Path(r), remaining) for r in baseline['immutable_roots']}
    files = [_fingerprint(Path(f['path']), remaining) for f in baseline['immutable_files']]
    require(trees == {r: _tree(Path(r), remaining) for r in trees}, 'immutable tree changed while hashing')
    originals = {str(p['identity']['pid']): _proc(p['identity']['pid'], proc_root)
                 for p in baseline['original_processes']}
    owned_raw = {str(p['pid']): _proc(p['pid'], proc_root) for p in owned}
    group_scan = []
    groups = {p['pgrp'] for p in owned}; sessions = {p['session'] for p in owned}
    if owned:
        for p in sorted(proc_root.iterdir(), key=lambda p: p.name):
            if not p.name.isdigit():
                continue
            try:
                content = _read(p / 'stat'); fields, state = _parse_stat(content, int(p.name))
            except FileNotFoundError:
                continue
            if fields['pgrp'] in groups or fields['session'] in sessions:
                group_scan.append({'pid': int(p.name), 'stat': _b64(content)})
    payload = _read(Path(gpu_fixture_path)) if gpu_fixture_path else (gpu_query or _gpu_query)(remaining())
    gpu_raw = _gpu_payload(payload); _, apps = _parse_gpu(gpu_raw)
    protected = {str(app['pid']): _proc(app['pid'], proc_root) for app in apps}
    services = [_http(s['url'], min(5, remaining()), http_open) for s in baseline['services']]
    progress = []
    for spec in baseline['progress']:
        content = _read(Path(spec['path']))
        progress.append({'path': spec['path'], 'body': _b64(content),
                         'body_sha256': hashlib.sha256(content).hexdigest()})
    remaining()
    return {'boot_id': _b64(boot), 'immutable_trees': trees, 'immutable_files': files,
            'original_processes': originals, 'owned_processes': owned_raw, 'owned_group_scan': group_scan,
            'original_parent': _proc(original_parent['pid'], proc_root) if original_parent else None,
            'gpu': gpu_raw, 'protected_processes': protected, 'services': services, 'progress': progress}


def verify_restoration(baseline, raw_result):
    """Recompute from saved raw reads; ignore observer success booleans/status."""
    validate_baseline(baseline)
    failures = []; progress_series = {p['path']: [] for p in baseline['progress']}
    try:
        require(raw_result['schema_version'] == 1 and raw_result['acquisition_id'] == baseline['acquisition_id'],
                'result acquisition differs')
        owned = raw_result['owned_identities']
        for identity in owned:
            _identity(identity)
        require(len({p['pid'] for p in owned}) == len(owned), 'duplicate owned identity')
        parent = raw_result.get('original_parent_identity')
        if parent is not None:
            _identity(parent)
            require(parent['boot_id'] == baseline['boot_id'] and parent['uid'] == baseline['uid'],
                    'original parent UID/boot differs')
        start = raw_result['recovery_started_monotonic']; deadline = raw_result['recovery_deadline_monotonic']
        require(_number(start) and _number(deadline) and 0 < deadline - start <= 1500, 'recovery deadline differs')
        require(not raw_result.get('collection_error'), 'independent read failed: ' + str(raw_result.get('collection_error')))
        observations = raw_result['observations']; require(observations, 'no independent observations')
        prior_time = start
        for observation in observations:
            when = observation['observed_at_monotonic']
            require(_number(when) and prior_time <= when <= deadline, 'observation outside recovery deadline')
            prior_time = when; boot = _bytes(observation['boot_id']).decode().strip()
            require(boot == baseline['boot_id'], 'boot identity differs')
            require(observation['immutable_files'] == baseline['immutable_files'], 'immutable fullhash/size differs')
            expected_trees = {r: sorted(f['path'] for f in baseline['immutable_files']
                                       if Path(f['path']).is_relative_to(Path(r))) for r in baseline['immutable_roots']}
            require(observation['immutable_trees'] == expected_trees, 'immutable tree inventory differs')
            require(set(observation['original_processes'])
                    == {str(p['identity']['pid']) for p in baseline['original_processes']}, 'original inventory differs')
            for spec in baseline['original_processes']:
                current = observation['original_processes'][str(spec['identity']['pid'])]
                require(current is not None, 'original process absent')
                fact = _parse_process(current, boot)
                fields = IDENTITY - {'ppid'}
                require(all(fact['identity'][k] == spec['identity'][k] for k in fields)
                        and fact['cmdline_sha256'] == spec['cmdline_sha256'],
                        'original same-process identity differs')
                if fact['identity']['ppid'] != spec['identity']['ppid']:
                    require(parent is not None and spec['identity']['ppid'] == parent['pid'],
                            'original reparenting lacks bound parent')
                    current_parent = observation['original_parent']
                    parent_fact = _parse_process(current_parent, boot, require_command=False) if current_parent else None
                    require(parent_fact is None or parent_fact['state'] in ('Z', 'X', 'x')
                            or any(parent_fact['identity'][k] != parent[k]
                                   for k in ('boot_id', 'pid', 'uid', 'start_ticks')),
                            'original reparented while bound parent remains alive')
                require(fact['state'] not in ('T', 't', 'Z', 'X', 'x'), 'original stopped/dead')
            require(set(observation['owned_processes']) == {str(p['pid']) for p in owned}, 'owned inventory differs')
            for spec in owned:
                current = observation['owned_processes'][str(spec['pid'])]
                if current is not None:
                    fact = _parse_process(current, boot, require_command=False)
                    require(any(fact['identity'][k] != spec[k] for k in ('boot_id', 'pid', 'uid', 'start_ticks')),
                            'owned worker still alive')
            for item in observation['owned_group_scan']:
                fields, _ = _parse_stat(_bytes(item['stat']), item['pid'])
                require(not any(fields['pgrp'] == p['pgrp'] or fields['session'] == p['session'] for p in owned),
                        'owned group/session survivor')
            gpus, apps = _parse_gpu(observation['gpu']); normalized = []
            require(set(observation['protected_processes']) == {str(a['pid']) for a in apps}, 'protected proc inventory differs')
            for app in apps:
                current = observation['protected_processes'][str(app['pid'])]
                require(current is not None, 'protected process absent')
                fact = _parse_process(current, boot)
                require(fact['state'] not in ('T', 't', 'Z', 'X', 'x'), 'protected process stopped/dead')
                normalized.append({**app, 'identity': fact['identity'], 'cmdline_sha256': fact['cmdline_sha256']})
            expected = baseline['protected_gpu_inventory']
            require(gpus == sorted(expected['gpus'], key=lambda g: g['index'])
                    and normalized == sorted(expected['compute_processes'], key=lambda a: (a['gpu_uuid'], a['pid'])),
                    'protected GPU0/1 inventory differs')
            require(len(observation['services']) == len(baseline['services']), 'service inventory differs')
            for spec, response in zip(baseline['services'], observation['services']):
                body = _bytes(response['body'])
                require(response['url'] == spec['url'] and response['status'] == spec['expected_status']
                        and hashlib.sha256(body).hexdigest() == response['body_sha256'], 'HTTP availability/hash failed')
            require(len(observation['progress']) == len(baseline['progress']), 'progress inventory differs')
            for spec, response in zip(baseline['progress'], observation['progress']):
                require(response['path'] == spec['path']
                        and hashlib.sha256(_bytes(response['body'])).hexdigest() == response['body_sha256'],
                        'progress raw hash/path differs')
                progress_series[spec['path']].append(_progress_value(response, spec))
        for spec in baseline['progress']:
            values = progress_series[spec['path']]
            require(len(values) >= 2 and values[0] >= spec['before_value']
                    and all(a <= b for a, b in zip(values, values[1:]))
                    and values[-1] > values[0] and values[-1] > spec['before_value'], 'progress advancement pending')
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        failures.append(str(exc))
    return {'schema_version': 1, 'status': ('same_process_resource_recovery_observed' if not failures
                                           else 'resource_recovery_observation_failed'),
            'failures': failures, 'progress_series': progress_series, 'queue_restore_proven': False,
            'optimizer_boundary_proven': False, 'execution_available': False, 'resource_authority': False,
            'model_calls': 0, 'queue_controls': 0,
            'limits': ['Read-only same-process availability/content/progress observations only.',
                       'No actual queue adapter or recoverable optimizer boundary is proved.',
                       'HTTP200 proves endpoint availability, not socket ownership, an authenticated response from its declared service PID, or successful rollouts.',
                       'Declared worker identities and same-group scan do not prove completeness of escaped-session descendants; the episode guard must independently prove its whole tracked tree quiescent.']}


def observe_restore(baseline, owned_processes, *, recovery_started_monotonic, recovery_deadline_monotonic,
                    proc_root='/proc', poll_interval_s=1.0, clock=time.monotonic, wall_clock=time.time,
                    sleep=time.sleep, http_open=None, gpu_query=None, gpu_fixture_path=None,
                    original_parent_identity=None):
    validate_baseline(baseline)
    validate_restoration_spec(baseline, {'schema_version': 1,
        'max_recovery_seconds': recovery_deadline_monotonic - recovery_started_monotonic,
        'poll_interval_s': poll_interval_s, 'proc_root': str(proc_root),
        'gpu_fixture_path': str(gpu_fixture_path) if gpu_fixture_path is not None else None})
    require(isinstance(owned_processes, list), 'owned identities list required')
    for identity in owned_processes:
        _identity(identity)
        require(identity['boot_id'] == baseline['boot_id'] and identity['uid'] == baseline['uid'],
                'owned boot/UID differs')
    require(len({p['pid'] for p in owned_processes}) == len(owned_processes)
            and not {p['pid'] for p in owned_processes} & {p['identity']['pid'] for p in baseline['original_processes']},
            'owned identities overlap originals/each other')
    require(_number(recovery_started_monotonic) and _number(recovery_deadline_monotonic),
            'same-boot monotonic recovery deadline required')
    require(recovery_started_monotonic <= clock() < recovery_deadline_monotonic,
            'current monotonic time outside recovery interval')
    baseline = json.loads(json.dumps(baseline, allow_nan=False))
    owned_processes = json.loads(json.dumps(owned_processes, allow_nan=False))
    if original_parent_identity is not None:
        _identity(original_parent_identity)
        original_parent_identity = dict(original_parent_identity)
    raw_result = {'schema_version': 1, 'acquisition_id': baseline['acquisition_id'],
                  'owned_identities': owned_processes, 'recovery_started_monotonic': recovery_started_monotonic,
                  'recovery_deadline_monotonic': recovery_deadline_monotonic, 'observations': [],
                  'original_parent_identity': original_parent_identity,
                  'fixture_inputs': {'proc_root_injected': str(proc_root) != '/proc',
                                     'gpu_query_injected': gpu_query is not None,
                                     'gpu_fixture_path': str(gpu_fixture_path) if gpu_fixture_path else None}}
    def remaining():
        available = recovery_deadline_monotonic - clock()
        require(available > 0, 'bounded recovery deadline expired')
        return available
    while True:
        try:
            remaining()
            observation = _collect(baseline, owned_processes, Path(proc_root), remaining,
                                   http_open, gpu_query, gpu_fixture_path, original_parent_identity)
            observation['observed_at_monotonic'] = clock()
            observation['observed_at_epoch_s'] = wall_clock()
            raw_result['observations'].append(observation)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raw_result['collection_error'] = type(exc).__name__ + ': ' + str(exc)
        result = verify_restoration(baseline, raw_result)
        if not result['failures'] or result['failures'] != ['progress advancement pending']:
            return {**raw_result, 'verification': result}
        try:
            sleep(min(poll_interval_s, remaining()))
        except (OSError, ValueError) as exc:
            raw_result['collection_error'] = type(exc).__name__ + ': ' + str(exc)
            return {**raw_result, 'verification': verify_restoration(baseline, raw_result)}


def main(argv=None):
    raise RestorationAuditError('Production restoration CLI unavailable: live queue adapter, optimizer boundary and independently reviewed control authority remain unproved')


if __name__ == '__main__':
    main()
