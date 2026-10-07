"""One declared presence-only observation of native A's Linux prerequisites.

CPython and standard-library imports are trusted inputs. No native-A body is
imported, and no containment API is invoked. Presence grants no authority.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import sys


SCOPE = 'frontier_v8_native_prerequisite_presence_only'
NATIVE_COMMIT = '4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2'
NATIVE_SHA256 = '2d9edb599d48aa2c9e1e5971ce95ae833022622a9de3c8d1a1ca81f0f70debc2'
REQUEST_FIELDS = {'schema_version', 'scope', 'nonce', 'observer_sha256',
                  'attempt_directory', 'host', 'bootstrap'}
NODES = ('N1-1', 'N1-3', 'N4-1', 'N4-2', 'N4-3', 'N4-4')
MAX_SOURCE_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 16 * 1024
MAX_EXECUTABLE_BYTES = 64 * 1024 * 1024
OLD_ABI_ROOT = Path('/data/zefan/open-jev-v8-runtime-abi-20261003')
AUTHORITY = {'presence_only': True, 'functional_containment_verified': False,
             'containment_available': False, 'execution_available': False,
             'resource_authority': False}


class CapabilityError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CapabilityError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def normalized_path(value):
    require(type(value) is str and '\0' not in value, 'Actual path required')
    path = Path(value)
    require(path.is_absolute() and path.as_posix() == value
            and '..' not in path.parts and path.name, 'Normalized absolute path required')
    require(not any(path.is_relative_to(Path(root)) for root in ('/proc', '/sys', '/dev')),
            'Generic virtual filesystem paths refused before reads')
    return path


def open_parent(path):
    """Walk every real directory with no-follow; standard ancestors may be root-owned."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open('/', flags)
    try:
        for part in path.parent.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def read_regular(value, limit, *, owner=None):
    path = normalized_path(value)
    parent_fd = open_parent(path)
    fd = None
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=parent_fd)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode), 'Regular input required')
        require(owner is None or before.st_uid == owner, 'Request owner differs')
        require(before.st_size <= limit, 'Input exceeds fixed byte limit')
        chunks, count = [], 0
        while count <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
        require(count <= limit, 'Input exceeds fixed byte limit')
        require(file_identity(os.fstat(fd)) == file_identity(before), 'Input changed during read')
        after = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        require(file_identity(after) == file_identity(before), 'Input replaced after read')
        return b''.join(chunks), file_identity(before)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent_fd)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key rejected')
        result[key] = value
    return result


def parse_request(body, expected_sha256, source_sha256):
    require(type(expected_sha256) is str
            and re.fullmatch(r'[0-9a-f]{64}', expected_sha256), 'Explicit request hash required')
    require(digest(body) == expected_sha256, 'Request bytes differ')
    try:
        request = json.loads(body, object_pairs_hook=_unique_object,
                             parse_constant=lambda value: require(False, 'Nonfinite JSON rejected'))
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, CapabilityError):
            raise
        raise CapabilityError('Malformed request JSON') from error
    require(type(request) is dict and set(request) == REQUEST_FIELDS
            and type(request['schema_version']) is int and request['schema_version'] == 1
            and request['scope'] == SCOPE, 'Exact presence-only declaration required')
    require(type(request['nonce']) is str and re.fullmatch(r'[0-9a-f]{64}', request['nonce']),
            'Fresh declaration nonce required')
    require(request['observer_sha256'] == source_sha256, 'Observer source differs from request')
    host, bootstrap = request['host'], request['bootstrap']
    require(type(host) is dict and set(host) == {'node_alias', 'hostname', 'boot_id', 'uid'},
            'Exact host binding required')
    require(host['node_alias'] in NODES and type(host['hostname']) is str
            and 0 < len(host['hostname']) <= 255 and '\0' not in host['hostname']
            and type(host['uid']) is int and host['uid'] >= 0
            and type(host['boot_id']) is str
            and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', host['boot_id']),
            'Host declaration malformed')
    require(type(bootstrap) is dict and set(bootstrap) == {'executable', 'sha256', 'version'},
            'Exact bootstrap binding required')
    normalized_path(bootstrap['executable'])
    require(type(bootstrap['sha256']) is str
            and re.fullmatch(r'[0-9a-f]{64}', bootstrap['sha256'])
            and type(bootstrap['version']) is list and len(bootstrap['version']) == 3
            and all(type(value) is int and value >= 0 for value in bootstrap['version']),
            'Bootstrap declaration malformed')
    normalized_path(request['attempt_directory'])
    return request


def prerequisite_observation(platform_value, uid, euid, *, os_module=os,
                             signal_module=signal, select_module=select):
    """Preserve the frozen hasattr predicate, including present noncallable values."""
    modules = {'os.pidfd_open': (os_module, 'pidfd_open'),
               'signal.pidfd_send_signal': (signal_module, 'pidfd_send_signal'),
               'select.poll': (select_module, 'poll')}
    attributes = {name: {'present': hasattr(module, attribute),
                         'callable': callable(getattr(module, attribute, None))}
                  for name, (module, attribute) in modules.items()}
    predicates = {'sys.platform_is_linux': platform_value == 'linux',
                  **{name + '_present': row['present'] for name, row in attributes.items()},
                  'uid_matches_euid': uid == euid}
    return {**AUTHORITY, 'sys_platform': platform_value, 'uid': uid, 'euid': euid,
            'attributes': attributes, 'predicates': predicates,
            'missing_attributes': [name for name, row in attributes.items() if not row['present']],
            'native_prerequisite_predicate_passed': all(predicates.values())}


def _proc_bytes(path, limit):
    require(path in ('/proc/self/stat', '/proc/self/status', '/proc/sys/kernel/random/boot_id'),
            'Only fixed current-process proc reads permitted')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        body = os.read(fd, limit + 1)
        require(len(body) <= limit, 'Proc input exceeds fixed byte limit')
        return body
    finally:
        os.close(fd)


def parse_self_identity(boot_body, stat_body, status_body, pid, ppid, uid, euid):
    try:
        require(pid > 0 and ppid >= 0 and uid >= 0 and euid >= 0, 'Invalid self OS identity')
        boot = boot_body.decode('ascii').strip()
        require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot),
                'Invalid boot identity')
        prefix, separator, tail = stat_body.rpartition(b') ')
        opening = prefix.find(b'(')
        require(separator and opening > 0 and int(prefix[:opening].strip()) == pid,
                'Invalid self stat identity')
        fields = tail.split()
        require(len(fields) >= 20, 'Truncated self stat')
        actual_ppid, pgrp, session, start = (int(fields[index]) for index in (1, 2, 3, 19))
        require(actual_ppid == ppid and start > 0 and pgrp > 0 and session > 0,
                'Current process identity differs')
        rows = [row for row in status_body.decode('ascii').splitlines() if row.startswith('Uid:')]
        require(len(rows) == 1, 'Missing self UID identity')
        uids = [int(value) for value in rows[0].split()[1:]]
        require(len(uids) == 4 and all(value >= 0 for value in uids)
                and uids[:2] == [uid, euid], 'Current process UIDs differ')
        state = fields[0].decode('ascii')
    except (UnicodeError, ValueError, IndexError) as error:
        if isinstance(error, CapabilityError):
            raise
        raise CapabilityError('Malformed current process identity') from error
    return {'boot_id': boot, 'pid': pid, 'ppid': actual_ppid, 'pgrp': pgrp,
            'session': session, 'start_ticks': start, 'state': state,
            'uid': uid, 'euid': euid, 'proc_uids': uids,
            'parent_identity_verified': False, 'ancestry_verified': False}


def capture_self_identity():
    return parse_self_identity(_proc_bytes('/proc/sys/kernel/random/boot_id', 256),
                               _proc_bytes('/proc/self/stat', 65536),
                               _proc_bytes('/proc/self/status', 65536),
                               os.getpid(), os.getppid(), os.getuid(), os.geteuid())


def module_origins():
    result = {}
    for name in ('argparse', 'hashlib', 'json', 'os', 'pathlib', 're', 'select', 'signal', 'stat', 'sys'):
        module = sys.modules[name]
        spec = getattr(module, '__spec__', None)
        result[name] = {'file': getattr(module, '__file__', None),
                        'spec_origin': getattr(spec, 'origin', None)}
    return result


def write_json_at(directory_fd, name, value):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=directory_fd)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def _absent(directory_fd, name):
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise CapabilityError('Attempt root or consumed marker already exists')


def observe(request_path, expected_request_sha256):
    require(sys.flags.isolated == sys.flags.no_site == 1 and sys.dont_write_bytecode,
            'Fresh file entry requires -B -I -S')
    uid, euid = os.getuid(), os.geteuid()
    require(uid == euid, 'Changed observer privilege refused before writes')
    source_path = normalized_path(__file__)
    source_body, source_identity = read_regular(str(source_path), MAX_SOURCE_BYTES)
    request_path = normalized_path(request_path)
    request_body, request_identity = read_regular(str(request_path), MAX_REQUEST_BYTES, owner=uid)
    source_sha256 = digest(source_body)
    request = parse_request(request_body, expected_request_sha256, source_sha256)
    bootstrap_path = normalized_path(request['bootstrap']['executable'])
    executable_lexical = sys.executable
    actual_executable = os.path.realpath(sys.executable)
    require(actual_executable == str(bootstrap_path), 'Bootstrap executable differs')
    bootstrap_body, bootstrap_identity = read_regular(str(bootstrap_path), MAX_EXECUTABLE_BYTES)
    require(digest(bootstrap_body) == request['bootstrap']['sha256']
            and list(sys.version_info[:3]) == request['bootstrap']['version'], 'Bootstrap bytes/version differ')
    identity = capture_self_identity()
    require(identity['uid'] == identity['euid'] == request['host']['uid'] == uid
            and identity['boot_id'] == request['host']['boot_id']
            and os.uname().nodename == request['host']['hostname'], 'Current host identity differs')
    root = normalized_path(request['attempt_directory'])
    marker_name = root.name + '.consumed.json'
    marker = root.with_name(marker_name)
    require(not root.is_relative_to(OLD_ABI_ROOT), 'Old ABI output boundary refused')
    for output in (root, marker):
        require(all(output != path and not path.is_relative_to(output)
                    and not output.is_relative_to(path)
                    for path in (source_path, request_path, bootstrap_path)), 'Output overlaps an input')
    parent_fd = open_parent(root)
    root_fd = None
    try:
        boundary = os.fstat(parent_fd)
        require(boundary.st_uid == uid, 'Output boundary owner differs')
        _absent(parent_fd, root.name)
        _absent(parent_fd, marker_name)
        # Everything above is preconsumption validation. Never remove these outputs.
        write_json_at(parent_fd, marker_name, {**AUTHORITY, 'schema_version': 1,
                      'status': 'consumed', 'scope': SCOPE, 'nonce': request['nonce'],
                      'request_sha256': expected_request_sha256, 'observer_sha256': source_sha256,
                      'attempt_directory': str(root)})
        os.fsync(parent_fd)
        receipt = {**AUTHORITY, 'schema_version': 1, 'scope': SCOPE, 'status': 'failed',
                   'nonce': request['nonce'], 'request_sha256': expected_request_sha256,
                   'observer': {'file': str(source_path), 'sha256': source_sha256},
                   'native_reference': {'commit': NATIVE_COMMIT, 'sha256': NATIVE_SHA256,
                                        'function': '_require_linux', 'body_executed': False},
                   'trusted_inputs': 'CPython and standard-library imports; origins are descriptive',
                   'input_and_self_identity_postvalidation_passed': False}
        try:
            os.mkdir(root.name, 0o700, dir_fd=parent_fd)
            root_fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=parent_fd)
            root_info = os.fstat(root_fd)
            require(root_info.st_uid == uid, 'New output owner differs')
            receipt['prerequisites'] = prerequisite_observation(sys.platform, uid, euid)
            receipt['python'] = {'executable_lexical': executable_lexical,
                                 'executable_resolved': actual_executable,
                                 'executable_sha256': digest(bootstrap_body),
                                 'version': list(sys.version_info[:3]), 'version_string': sys.version,
                                 'implementation': sys.implementation.name,
                                 'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site,
                                 'dont_write_bytecode': sys.dont_write_bytecode}
            receipt['host'] = {**request['host'], 'node_alias_authenticated': False}
            receipt['self_identity'] = identity
            receipt['module_origins'] = module_origins()
            for path, body, original, limit, owner in (
                    (source_path, source_body, source_identity, MAX_SOURCE_BYTES, None),
                    (request_path, request_body, request_identity, MAX_REQUEST_BYTES, uid),
                    (bootstrap_path, bootstrap_body, bootstrap_identity, MAX_EXECUTABLE_BYTES, None)):
                after_body, after_identity = read_regular(str(path), limit, owner=owner)
                require(after_identity == original and after_body == body, 'Input differs at postvalidation')
            after = capture_self_identity()
            require(all(after[key] == identity[key] for key in
                        ('boot_id', 'pid', 'ppid', 'start_ticks', 'uid', 'euid', 'proc_uids')),
                    'Self identity differs at postvalidation')
            require(os.getuid() == os.geteuid() == uid, 'Privilege differs at postvalidation')
            require(sys.executable == executable_lexical
                    and os.path.realpath(sys.executable) == actual_executable
                    and list(sys.version_info[:3]) == request['bootstrap']['version']
                    and __file__ == str(source_path)
                    and os.uname().nodename == request['host']['hostname'],
                    'Source/bootstrap/host facts differ at postvalidation')
            check_fd = open_parent(root)
            try:
                check = os.fstat(check_fd)
                require((check.st_dev, check.st_ino, check.st_uid) ==
                        (boundary.st_dev, boundary.st_ino, uid), 'Output boundary changed')
                check = os.stat(root.name, dir_fd=check_fd, follow_symlinks=False)
                require(stat.S_ISDIR(check.st_mode) and (check.st_dev, check.st_ino, check.st_uid) ==
                        (root_info.st_dev, root_info.st_ino, uid), 'Output root changed')
            finally:
                os.close(check_fd)
            receipt['input_and_self_identity_postvalidation_passed'] = True
            receipt['status'] = 'presence_observed'
        except BaseException as error:
            receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
        if root_fd is not None:
            write_json_at(root_fd, 'receipt.json', receipt)
            os.fsync(root_fd)
        else:
            # A consumed mkdir/open failure still leaves a bounded failed receipt.
            write_json_at(parent_fd, root.name + '.failed-receipt.json', receipt)
        os.fsync(parent_fd)
        return receipt
    finally:
        if root_fd is not None:
            os.close(root_fd)
        os.close(parent_fd)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if any(value == '--execute' or value.startswith('--execute=') for value in argv):
        raise CapabilityError('Execution unavailable; presence-only observer')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-cpu', action='store_true')
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-request-sha256', required=True)
    args = parser.parse_args(argv)
    require(args.observe_cpu, 'Explicit presence observation required')
    receipt = observe(args.request, args.expected_request_sha256)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['status'] == 'presence_observed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (CapabilityError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
