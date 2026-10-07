"""One separately declared current-process C-export pidfd selfcheck.

CPython, its stdlib/ctypes startup and the dynamic loader are trusted inputs.
This is not a native guard shim, process controller or model entrypoint.
"""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import sys
from types import ModuleType


SCOPE = 'frontier_v8_own_pidfd_functional_selfcheck'
HELPER_SHA = '1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412'
HELPER_NAME = 'frontier_v8_selfcheck_identity_helper'
FIELDS = {'schema_version', 'scope', 'nonce', 'observer_sha256',
          'identity_helper_sha256', 'attempt_directory', 'host', 'bootstrap'}
AUTHORITY = {'functional_containment_verified': False, 'containment_available': False,
             'execution_available': False, 'resource_authority': False,
             'model_runtime_ABI_observed': False}
MAX_MAPS_BYTES = 4 * 1024 * 1024
MAX_PROVIDER_BYTES = 64 * 1024 * 1024
FORBIDDEN_OUTPUT_PREFIXES = (
    '/data/zefan/open-jev-v8-runtime-abi-20261003',
    '/data/zefan/open-jev-v8-containment-presence-',
    '/data/zefan/open-jev-v8-linux-runtime-20261003',
)


class SelfcheckError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SelfcheckError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def load_identity_helper():
    """Compile exact captured immutable helper bytes, without an old CLI call."""
    source = Path(__file__)
    require(source.is_absolute() and source.as_posix() == __file__
            and '..' not in source.parts
            and not any(source.is_relative_to(Path(p)) for p in ('/proc', '/sys', '/dev')),
            'Canonical nonvirtual file entry required')
    path = source.with_name('frontier_v8_containment_capability.py')
    require(HELPER_NAME not in sys.modules, 'Preloaded identity-helper cache refused')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    parent = os.open('/', flags)
    fd = None
    try:
        for part in path.parent.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=parent)
            os.close(parent)
            parent = next_fd
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=parent)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= 1024 * 1024,
                'Bounded regular immutable helper required')
        chunks, count = [], 0
        while count <= 1024 * 1024:
            chunk = os.read(fd, min(65536, 1024 * 1024 + 1 - count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
        body = b''.join(chunks)
        after = os.fstat(fd)
        leaf = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        identity = tuple(getattr(before, field) for field in fields)
        require(count <= 1024 * 1024
                and tuple(getattr(after, field) for field in fields) == identity
                and tuple(getattr(leaf, field) for field in fields) == identity
                and digest(body) == HELPER_SHA, 'Immutable helper bytes/identity differ')
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)
    helper = ModuleType(HELPER_NAME)
    helper.__file__ = str(path)
    helper.__package__ = None
    exec(compile(body, str(path), 'exec', dont_inherit=True), helper.__dict__)
    helper._captured_bytes = body
    helper._captured_identity = identity
    return helper


def parse_request(body, expected_sha256, source_sha256, helper):
    require(type(expected_sha256) is str and re.fullmatch(r'[0-9a-f]{64}', expected_sha256)
            and digest(body) == expected_sha256, 'Explicit exact request bytes required')
    request = json.loads(body, object_pairs_hook=helper._unique_object,
                         parse_constant=lambda value: require(False, 'Nonfinite JSON refused'))
    require(type(request) is dict and set(request) == FIELDS
            and type(request['schema_version']) is int and request['schema_version'] == 1
            and request['scope'] == SCOPE, 'Exact separate selfcheck declaration required')
    require(type(request['nonce']) is str and re.fullmatch(r'[0-9a-f]{64}', request['nonce'])
            and request['observer_sha256'] == source_sha256
            and request['identity_helper_sha256'] == HELPER_SHA,
            'Fresh nonce and exact source/helper hashes required')
    host, bootstrap = request['host'], request['bootstrap']
    require(type(host) is dict and set(host) == {'node_alias', 'hostname', 'boot_id', 'uid'}
            and host['node_alias'] in helper.NODES and type(host['hostname']) is str
            and 0 < len(host['hostname']) <= 255 and '\0' not in host['hostname']
            and type(host['uid']) is int and host['uid'] >= 0
            and type(host['boot_id']) is str
            and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', host['boot_id']),
            'Exact host declaration required')
    require(type(bootstrap) is dict and set(bootstrap) == {'executable', 'sha256', 'version'}
            and type(bootstrap['sha256']) is str
            and re.fullmatch(r'[0-9a-f]{64}', bootstrap['sha256'])
            and type(bootstrap['version']) is list and len(bootstrap['version']) == 3
            and all(type(v) is int and v >= 0 for v in bootstrap['version']),
            'Exact bootstrap declaration required')
    helper.normalized_path(bootstrap['executable'])
    helper.normalized_path(request['attempt_directory'])
    return request


def parse_provider_mapping(body, address):
    require(type(address) is int and address > 0, 'Actual function address required')
    matches = []
    for line in body.decode('utf-8', errors='strict').splitlines():
        fields = line.split(None, 5)
        require(len(fields) >= 5, 'Malformed own maps row')
        bounds = fields[0].split('-')
        require(len(bounds) == 2, 'Malformed own maps interval')
        start, end = (int(value, 16) for value in bounds)
        if start <= address < end:
            require(len(fields) == 6 and 'x' in fields[1] and len(fields[1]) == 4
                    and fields[5].startswith('/') and '\\' not in fields[5]
                    and not fields[5].endswith(' (deleted)'),
                    'Symbol requires undeleted executable file-backed own mapping')
            device = fields[3].split(':')
            require(len(device) == 2 and int(fields[4]) > 0, 'Actual provider device/inode required')
            matches.append({'start': start, 'end': end, 'perms': fields[1],
                            'offset': int(fields[2], 16), 'device_major': int(device[0], 16),
                            'device_minor': int(device[1], 16), 'inode': int(fields[4]),
                            'lexical_path': fields[5]})
    require(len(matches) == 1, 'Unique executable symbol-provider mapping required')
    return matches[0]


def parse_fdinfo(body, own_pid):
    require(type(own_pid) is int and own_pid > 0, 'Positive current own PID required')
    rows = body.decode('ascii').splitlines()
    pid_rows = [row.split() for row in rows if row.startswith('Pid:')]
    require(len(pid_rows) == 1 and len(pid_rows[0]) == 2
            and int(pid_rows[0][1]) == own_pid, 'Returned descriptor must target current own PID')
    ns_rows = [row.split() for row in rows if row.startswith('NSpid:')]
    require(len(ns_rows) <= 1, 'Duplicate descriptor namespace row refused')
    nspid = [int(value) for value in ns_rows[0][1:]] if ns_rows else None
    require(nspid is None or (nspid and all(value >= 0 for value in nspid)),
            'Malformed descriptor namespace row')
    return {'pid': own_pid, 'nspid': nspid}


def read_own_proc(path, limit):
    require(path == '/proc/self/maps' or re.fullmatch(r'/proc/self/fdinfo/[0-9]+', path),
            'Only fixed own maps or internally derived own fdinfo permitted')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        chunks, count = [], 0
        while count <= limit:
            body = os.read(fd, min(65536, limit + 1 - count))
            if not body:
                break
            chunks.append(body)
            count += len(body)
        require(count <= limit, 'Own proc bytes exceed fixed limit')
        return b''.join(chunks)
    finally:
        os.close(fd)


class SelfPidfdBackend:
    """Named process-global export; no guessed syscall number or library path."""
    def __init__(self, helper):
        require(sys.platform == 'linux' and ctypes.sizeof(ctypes.c_int) == 4
                and ctypes.sizeof(ctypes.c_uint) == 4, 'Linux C integer ABI required')
        self.helper = helper
        self.library = ctypes.CDLL(None, use_errno=True)
        self.function = self.library.pidfd_open
        require(callable(self.function), 'Named pidfd_open C export unavailable')
        self.function.argtypes = (ctypes.c_int, ctypes.c_uint)
        self.function.restype = ctypes.c_int
        self.address = ctypes.cast(self.function, ctypes.c_void_p).value
        require(type(self.address) is int and self.address > 0, 'Named export address unavailable')

    def provenance(self):
        mapping = parse_provider_mapping(read_own_proc('/proc/self/maps', MAX_MAPS_BYTES),
                                         self.address)
        canonical = os.path.realpath(mapping['lexical_path'])
        body, identity = self.helper.read_regular(canonical, MAX_PROVIDER_BYTES)
        require(body.startswith(b'\x7fELF') and identity[1] == mapping['inode']
                and os.major(identity[0]) == mapping['device_major']
                and os.minor(identity[0]) == mapping['device_minor'],
                'Mapped provider and canonical regular file identity differ')
        return {'route': 'process_global_named_C_export', 'symbol': 'pidfd_open',
                'function_address': self.address, 'mapping': mapping,
                'canonical_path': canonical, 'provider_sha256': digest(body),
                'provider_bytes': len(body), 'file_identity': list(identity),
                'c_int_bytes': ctypes.sizeof(ctypes.c_int),
                'c_uint_bytes': ctypes.sizeof(ctypes.c_uint),
                'pointer_bytes': ctypes.sizeof(ctypes.c_void_p),
                'provider_hash_predeclared': False, 'mapped_payload_authenticated': False}

    def open_pidfd(self, pid):
        require(type(pid) is int and pid == os.getpid() and 0 < pid <= 2147483647,
                'Named export accepts only actual current own PID')
        ctypes.set_errno(0)
        fd = self.function(pid, 0)
        captured_errno = ctypes.get_errno() if fd < 0 else None
        return fd, captured_errno

    def fd_identity(self, fd):
        require(type(fd) is int and fd >= 0, 'Internally returned descriptor required')
        return parse_fdinfo(read_own_proc('/proc/self/fdinfo/' + str(fd), 65536), os.getpid())

    def poll_self_fd(self, fd):
        poller = select.poll()
        poller.register(fd, select.POLLIN)
        return poller.poll(0)

    def close_fd(self, fd):
        os.close(fd)

    def is_fd_closed(self, fd):
        try:
            os.fstat(fd)
        except OSError as error:
            return error.errno == errno.EBADF
        return False


def error_fact(error):
    value = {'type': type(error).__name__, 'message': str(error)}
    if isinstance(error, OSError):
        value['errno'] = error.errno
    return value


def probe_self_pidfd(identity, backend):
    result = {**AUTHORITY, 'status': 'failed', 'own_pidfd_operations_verified': False,
              'c_abi_pidfd_call_attempted': False,
              'steps': {'open_attempted': False, 'opened_fd': None,
                        'fd_identity_verified': False, 'poll_attempted': False,
                        'live_poll_empty': False, 'close_attempted': False,
                        'close_returned': False, 'closed_fd_observed': False,
                        'provider_postvalidation_passed': False}}
    fd = None
    try:
        require(type(identity['pid']) is int and identity['pid'] > 0, 'Current own PID required')
        result['provider_before'] = backend.provenance()
        result['steps']['open_attempted'] = True
        result['c_abi_pidfd_call_attempted'] = True
        returned, captured_errno = backend.open_pidfd(identity['pid'])
        require(type(returned) is int, 'Named C export returned a noninteger descriptor')
        if returned < 0:
            result['open_errno'] = captured_errno
            raise SelfcheckError('Named pidfd_open failed; no fallback')
        fd = returned
        result['steps']['opened_fd'] = fd
        result['fd_identity'] = backend.fd_identity(fd)
        require(result['fd_identity']['pid'] == identity['pid'], 'Descriptor PID differs from self')
        result['steps']['fd_identity_verified'] = True
        result['steps']['poll_attempted'] = True
        events = backend.poll_self_fd(fd)
        result['poll_events'] = events
        require(events == [], 'Live own pidfd poll(0) must return no events')
        result['steps']['live_poll_empty'] = True
    except Exception as error:
        result['error'] = error_fact(error)
    finally:
        if fd is not None:
            result['steps']['close_attempted'] = True
            try:
                backend.close_fd(fd)
                result['steps']['close_returned'] = True
            except Exception as error:
                result['close_error'] = error_fact(error)
            # No other descriptor-opening operation may intervene here. Never
            # close a reused number again, including after an EINTR result.
            try:
                result['steps']['closed_fd_observed'] = backend.is_fd_closed(fd)
                require(result['steps']['closed_fd_observed'], 'Closed descriptor not observed EBADF')
            except Exception as error:
                result['closed_fd_error'] = error_fact(error)
    if 'provider_before' in result:
        try:
            result['provider_after'] = backend.provenance()
            require(result['provider_after'] == result['provider_before'], 'Symbol provider changed')
            result['steps']['provider_postvalidation_passed'] = True
        except Exception as error:
            result['provider_error'] = error_fact(error)
    failures = any(key in result for key in ('error', 'close_error', 'closed_fd_error', 'provider_error'))
    if not failures and all(result['steps'][key] for key in (
            'fd_identity_verified', 'live_poll_empty', 'close_returned',
            'closed_fd_observed', 'provider_postvalidation_passed')):
        result['status'] = 'own_pidfd_operations_observed'
        result['own_pidfd_operations_verified'] = True
    return result


def observe(request_path, expected_sha256, *, backend_factory=SelfPidfdBackend):
    require(sys.flags.isolated == sys.flags.no_site == 1 and sys.dont_write_bytecode
            and sys.platform == 'linux' and os.getuid() == os.geteuid(),
            'Fresh Linux -B -I -S file entry with equal UID/eUID required')
    helper = load_identity_helper()
    source_path = helper.normalized_path(__file__)
    source_body, source_identity = helper.read_regular(str(source_path), helper.MAX_SOURCE_BYTES)
    helper_body, helper_identity = helper.read_regular(helper.__file__, helper.MAX_SOURCE_BYTES)
    require(helper_body == helper._captured_bytes and helper_identity == helper._captured_identity,
            'Captured identity helper changed')
    request_path = helper.normalized_path(request_path)
    uid = os.getuid()
    request_body, request_identity = helper.read_regular(str(request_path), helper.MAX_REQUEST_BYTES,
                                                       owner=uid)
    request = parse_request(request_body, expected_sha256, digest(source_body), helper)
    bootstrap = helper.normalized_path(request['bootstrap']['executable'])
    executable_lexical = sys.executable
    require(os.path.realpath(sys.executable) == str(bootstrap), 'Bootstrap executable differs')
    bootstrap_body, bootstrap_identity = helper.read_regular(str(bootstrap), helper.MAX_EXECUTABLE_BYTES)
    require(digest(bootstrap_body) == request['bootstrap']['sha256']
            and list(sys.version_info[:3]) == request['bootstrap']['version'], 'Bootstrap bytes/version differ')
    identity = helper.capture_self_identity()
    require(identity['uid'] == identity['euid'] == request['host']['uid'] == uid
            and identity['boot_id'] == request['host']['boot_id']
            and os.uname().nodename == request['host']['hostname'], 'Current host/self identity differs')
    root = helper.normalized_path(request['attempt_directory'])
    require(not any(str(root).startswith(prefix) for prefix in FORBIDDEN_OUTPUT_PREFIXES),
            'Consumed earlier output boundary refused')
    marker = root.with_name(root.name + '.consumed.json')
    for output in (root, marker):
        require(all(output != path and not output.is_relative_to(path)
                    and not path.is_relative_to(output)
                    for path in (source_path, Path(helper.__file__), request_path, bootstrap)),
                'Output overlaps an input')
    parent = helper.open_parent(root)
    root_fd = None
    try:
        boundary = os.fstat(parent)
        require(boundary.st_uid == uid, 'Owned output parent required')
        helper._absent(parent, root.name)
        helper._absent(parent, marker.name)
        helper.write_json_at(parent, marker.name, {**AUTHORITY, 'schema_version': 1,
                             'status': 'consumed', 'scope': SCOPE, 'nonce': request['nonce'],
                             'request_sha256': expected_sha256, 'observer_sha256': digest(source_body),
                             'identity_helper_sha256': HELPER_SHA, 'attempt_directory': str(root)})
        os.fsync(parent)
        receipt = {**AUTHORITY, 'schema_version': 1, 'scope': SCOPE, 'status': 'failed',
                   'own_pidfd_operations_verified': False, 'nonce': request['nonce'],
                   'request_sha256': expected_sha256,
                   'source': {'file': str(source_path), 'sha256': digest(source_body)},
                   'identity_helper': {'file': helper.__file__, 'sha256': HELPER_SHA,
                                       'captured_byte_body_executed': True,
                                       'old_observe_or_CLI_called': False},
                   'native_guard_executed_or_modified': False, 'os_api_shim_installed': False,
                   'signal_operations': 0, 'child_processes_created': 0,
                   'input_and_self_identity_postvalidation_passed': False,
                   'trusted_inputs': 'CPython/stdlib/ctypes/dynamicloader/named C-export provider; not a sandbox',
                   'host': {**request['host'], 'node_alias_authenticated': False},
                   'self_identity': identity,
                   'bootstrap': {'executable_lexical': executable_lexical,
                                 'executable_resolved': str(bootstrap),
                                 'sha256': digest(bootstrap_body), 'version': list(sys.version_info[:3])}}
        try:
            os.mkdir(root.name, 0o700, dir_fd=parent)
            root_fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=parent)
            root_info = os.fstat(root_fd)
            require(root_info.st_uid == uid, 'New output owner differs')
            receipt['self_probe'] = probe_self_pidfd(identity, backend_factory(helper))
            for path, body, original, limit, owner in (
                    (source_path, source_body, source_identity, helper.MAX_SOURCE_BYTES, None),
                    (Path(helper.__file__), helper_body, helper_identity, helper.MAX_SOURCE_BYTES, None),
                    (request_path, request_body, request_identity, helper.MAX_REQUEST_BYTES, uid),
                    (bootstrap, bootstrap_body, bootstrap_identity, helper.MAX_EXECUTABLE_BYTES, None)):
                later, later_identity = helper.read_regular(str(path), limit, owner=owner)
                require(later == body and later_identity == original, 'Input changed at postvalidation')
            after = helper.capture_self_identity()
            require(all(after[key] == identity[key] for key in
                        ('boot_id', 'pid', 'ppid', 'start_ticks', 'uid', 'euid', 'proc_uids'))
                    and os.getuid() == os.geteuid() == uid, 'Self identity/privilege changed')
            require(__file__ == str(source_path) and helper.__file__ == str(source_path.with_name(
                        'frontier_v8_containment_capability.py'))
                    and sys.executable == executable_lexical
                    and os.path.realpath(sys.executable) == str(bootstrap)
                    and list(sys.version_info[:3]) == request['bootstrap']['version']
                    and os.uname().nodename == request['host']['hostname'],
                    'Source/bootstrap/host changed at postvalidation')
            check = helper.open_parent(root)
            try:
                latest = os.fstat(check)
                require((latest.st_dev, latest.st_ino, latest.st_uid) ==
                        (boundary.st_dev, boundary.st_ino, uid), 'Output parent changed')
                latest = os.stat(root.name, dir_fd=check, follow_symlinks=False)
                require(stat.S_ISDIR(latest.st_mode) and (latest.st_dev, latest.st_ino, latest.st_uid) ==
                        (root_info.st_dev, root_info.st_ino, uid), 'Output directory changed')
            finally:
                os.close(check)
            receipt['input_and_self_identity_postvalidation_passed'] = True
            if receipt['self_probe']['own_pidfd_operations_verified']:
                receipt['status'] = 'own_pidfd_operations_observed'
                receipt['own_pidfd_operations_verified'] = True
        except Exception as error:
            receipt['error'] = error_fact(error)
        if root_fd is not None:
            helper.write_json_at(root_fd, 'receipt.json', receipt)
            os.fsync(root_fd)
        else:
            helper.write_json_at(parent, root.name + '.failed-receipt.json', receipt)
        os.fsync(parent)
        return receipt
    finally:
        if root_fd is not None:
            os.close(root_fd)
        os.close(parent)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if any(value == '--execute' or value.startswith('--execute=') for value in argv):
        raise SelfcheckError('Execution unavailable; own-descriptor functional selfcheck only')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-own-pidfd', action='store_true')
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-request-sha256', required=True)
    args = parser.parse_args(argv)
    require(args.observe_own_pidfd, 'Explicit separately declared own-descriptor selfcheck required')
    receipt = observe(args.request, args.expected_request_sha256)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['own_pidfd_operations_verified'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
