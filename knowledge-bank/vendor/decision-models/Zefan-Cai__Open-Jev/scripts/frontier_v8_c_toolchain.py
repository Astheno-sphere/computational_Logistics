"""Separate compiler/header/compile-target observation; never link or run products."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
from types import ModuleType


SCOPE = 'frontier_v8_C_toolchain_header_target_observation'
HELPER_SHA = '1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412'
HELPER_NAME = 'frontier_v8_toolchain_identity_helper'
FIELDS = {'schema_version', 'scope', 'nonce', 'observer_sha256', 'c_probe_sha256',
          'identity_helper_sha256', 'attempt_directory', 'host', 'bootstrap'}
SUCCESS_FIELDS = ('toolchain_invocation_observed', 'header_dependency_closure_observed',
                  'SYS_pidfd_open_header_constant_observed', 'compiler_target_ABI_observed')
AUTHORITY = dict.fromkeys(('native_C_runtime_ABI_observed', 'own_pidfd_operations_verified',
                          'functional_containment_verified', 'containment_available',
                          'execution_available', 'resource_authority',
                          'model_runtime_ABI_observed'), False)
TARGET = 'frontier_v8_source_dependencies'
MAX_OUTPUT = 8 * 1024 * 1024
MAX_HEADER = 4 * 1024 * 1024
MAX_HEADERS_TOTAL = 64 * 1024 * 1024
MAX_DRIVER = 64 * 1024 * 1024
FORBIDDEN_OUTPUT_PREFIXES = (
    '/data/zefan/open-jev-v8-runtime-abi-20261003',
    '/data/zefan/open-jev-v8-containment-presence-',
    '/data/zefan/open-jev-v8-pidfd-selfcheck-',
    '/data/zefan/open-jev-v8-linux-runtime-20261003',
)


class ToolchainError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ToolchainError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def error_fact(error):
    return {'type': type(error).__name__, 'message': str(error)}


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

def parse_request(body, expected_sha256, source_sha256, probe_sha256, helper):
    require(type(expected_sha256) is str and re.fullmatch(r'[0-9a-f]{64}', expected_sha256)
            and digest(body) == expected_sha256, 'Explicit exact request bytes required')
    request = json.loads(body, object_pairs_hook=helper._unique_object,
                         parse_constant=lambda value: require(False, 'Nonfinite JSON refused'))
    require(type(request) is dict and set(request) == FIELDS
            and type(request['schema_version']) is int and request['schema_version'] == 1
            and request['scope'] == SCOPE, 'Exact separate toolchain declaration required')
    require(type(request['nonce']) is str and re.fullmatch(r'[0-9a-f]{64}', request['nonce'])
            and request['observer_sha256'] == source_sha256
            and request['c_probe_sha256'] == probe_sha256
            and request['identity_helper_sha256'] == HELPER_SHA,
            'Fresh nonce and exact observer/probe/helper hashes required')
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
            and all(type(value) is int and value >= 0 for value in bootstrap['version']),
            'Exact bootstrap declaration required')
    helper.normalized_path(bootstrap['executable'])
    helper.normalized_path(request['attempt_directory'])
    return request


def parse_dependencies(body, source):
    """Reject unsupported make syntax rather than interpret shell/make expressions."""
    require(type(body) is bytes and len(body) <= MAX_OUTPUT, 'Bounded dependency bytes required')
    text = body.decode('ascii').replace('\\\n', ' ')
    require(text.count(':') == 1 and text.split(':', 1)[0] == TARGET
            and not any(char in text for char in '\0\\#$;|'), 'Unsupported dependency syntax')
    paths = text.split(':', 1)[1].split()
    require(0 < len(paths) <= 512 and len(set(paths)) == len(paths)
            and source in paths, 'Exact source and unique bounded dependency set required')
    for value in paths:
        path = Path(value)
        require(re.fullmatch(r'/[A-Za-z0-9_./+\-]+', value)
                and path.as_posix() == value and '..' not in path.parts and path.name
                and not any(path.is_relative_to(Path(root)) for root in ('/proc', '/sys', '/dev')),
                'Normalized real nonvirtual dependency paths required')
    return tuple(paths)


def parse_cpp_facts(body):
    require(type(body) is bytes and len(body) <= MAX_OUTPUT, 'Bounded captured CPP bytes required')
    text = body.decode('ascii')
    facts = {}
    markers = (('header_pidfd_open', 'SYS_pidfd_open_expression', 'long'),
               ('target_int_bytes', 'target_int_bytes', 'unsigned int'),
               ('target_long_bytes', 'target_long_bytes', 'unsigned int'),
               ('target_pointer_bytes', 'target_pointer_bytes', 'unsigned int'),
               ('target_char_bits', 'target_char_bits', 'unsigned int'),
               ('target_byte_order', 'target_byte_order', 'unsigned int'))
    for marker, key, c_type in markers:
        name = 'frontier_v8_' + marker
        require(len(re.findall(r'\b' + name + r'\b', text)) == 1, 'Missing or duplicate CPP marker')
        match = re.search(r'\bconst\s+' + c_type + r'\s+' + name + r'\s*=\s*([^;]+);', text)
        require(match is not None, 'Malformed CPP constant declaration')
        expression = match.group(1).strip()
        if key == 'SYS_pidfd_open_expression':
            # Token recognition only: ordinary object compilation evaluates the C expression.
            token = r'(?:0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]*|<<|>>|[()+\-*/%~&|^]'
            require(0 < len(expression) <= 1024
                    and re.fullmatch(r'(?:\s*(?:' + token + r'))+\s*', expression),
                    'Expanded numeric C expression required; no evaluator or substitution')
            facts[key] = expression
        else:
            require(re.fullmatch(r'[0-9]+', expression) and 0 < int(expression) <= 65536,
                    'Positive bounded compiler-target constant required')
            facts[key] = int(expression)
    return facts


def parse_elf_object(body):
    require(type(body) is bytes and 16 <= len(body) <= MAX_OUTPUT
            and body[:4] == b'\x7fELF' and body[4] in (1, 2)
            and body[5] in (1, 2) and body[6] == 1, 'Supported ELF object required')
    size = 52 if body[4] == 1 else 64
    order = '<' if body[5] == 1 else '>'
    require(len(body) >= size, 'Truncated ELF object')
    kind, machine, version = struct.unpack_from(order + 'HHI', body, 16)
    header_size = struct.unpack_from(order + 'H', body, 40 if body[4] == 1 else 52)[0]
    require(kind == 1 and version == 1 and header_size == size,
            'Relocatable compile-target ELF object required')
    return {'elf_class': body[4], 'data_encoding': body[5], 'machine': machine, 'elf_type': kind}


class CompilerBackend:
    """Trusted compiler/filesystem; bounded direct-child wait, no descendant guard."""
    def __init__(self, helper, root, root_fd):
        self.helper, self.root, self.root_fd = helper, root, root_fd
        self.compiler_role_path = None

    def snapshot(self, path, limit):
        body, identity = self.helper.read_regular(str(path), limit)
        return {'path': str(path), 'sha256': digest(body), 'identity': list(identity), 'bytes': len(body)}

    def resolve_compiler(self):
        role = shutil.which('cc', path='/usr/bin:/bin')
        require(role is not None, 'Declared cc role unavailable; no fallback')
        path = Path(os.path.realpath(role))
        body, identity = self.helper.read_regular(str(path), MAX_DRIVER)
        require(body[:4] == b'\x7fELF' and identity[2] & 0o111, 'Bounded executable ELF compiler driver required')
        self.compiler_role_path = role
        return {'path': str(path), 'role_path': role, 'sha256': digest(body),
                'identity': list(identity), 'bytes': len(body)}

    def read_output(self, name, limit):
        path = self.root / name
        body, identity = self.helper.read_regular(str(path), limit, owner=os.getuid())
        return body, {'path': str(path), 'sha256': digest(body),
                      'identity': list(identity), 'bytes': len(body)}

    def write_output(self, name, body):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self.root_fd)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
            written_identity = list(self.helper.file_identity(os.fstat(handle.fileno())))
        captured, row = self.read_output(name, MAX_OUTPUT)
        require(captured == body and row['identity'] == written_identity,
                'Written captured CPP output binding differs')
        return row

    def run(self, label, argv):
        result = {'label': label, 'argv': argv, 'status': 'failed', 'returncode': None,
                  'timed_out': False, 'direct_child_pid': None, 'kill_attempted': False,
                  'reap_completed': False, 'kill_error': None, 'reap_error': None,
                  'descendant_cleanup_verified': False}
        streams = []
        try:
            for suffix in ('stdout', 'stderr'):
                fd = os.open(label + '.' + suffix, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.root_fd)
                streams.append(os.fdopen(fd, 'wb'))
            env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
                   'TMPDIR': str(self.root / 'tmp'), 'CUDA_VISIBLE_DEVICES': '',
                   'NVIDIA_VISIBLE_DEVICES': 'none'}
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=streams[0],
                                     stderr=streams[1], cwd=str(self.root), env=env,
                                     close_fds=True)
            result['direct_child_pid'] = child.pid
            try:
                result['returncode'] = child.wait(timeout=30)
                result['reap_completed'] = True
            except subprocess.TimeoutExpired:
                result['timed_out'] = True
                result['kill_attempted'] = True
                try:
                    child.kill()
                except Exception as error:
                    result['kill_error'] = error_fact(error)
                try:
                    result['returncode'] = child.wait(timeout=2)
                    result['reap_completed'] = True
                except Exception as error:
                    result['reap_error'] = error_fact(error)
            if not result['timed_out'] and result['returncode'] == 0:
                result['status'] = 'success'
        except Exception as error:
            result['error'] = error_fact(error)
        finally:
            for stream in streams:
                stream.flush()
                os.fsync(stream.fileno())
                stream.close()
        try:
            for suffix in ('stdout', 'stderr'):
                result[suffix] = self.read_output(label + '.' + suffix, MAX_OUTPUT)[1]
        except Exception as error:
            result['status'] = 'failed'
            result['output_error'] = error_fact(error)
        self.helper.write_json_at(self.root_fd, label + '.json', result)
        return result


def run_toolchain(source, backend):
    result = {**AUTHORITY, **dict.fromkeys(SUCCESS_FIELDS, False), 'status': 'failed',
              'commands': [], 'product_link_or_execution_attempts': 0,
              'pidfd_or_syscall_entry_attempts': 0,
              'complete_toolchain_execution_closure_authenticated': False}
    try:
        compiler = backend.resolve_compiler()
        result['compiler'] = compiler
        executable = compiler['path']
        common = [executable, '-std=gnu11', '-D_GNU_SOURCE=1']
        commands = (('version', [executable, '--version']),
                    ('dependencies', common + ['-M', '-MT', TARGET, str(source)]),
                    ('preprocess', common + ['-E', '-P', '-MD', '-MF',
                                            str(backend.root / 'preprocess.d'), '-MT', TARGET,
                                            str(source)]),
                    ('object', [executable, '-std=gnu11', '-x', 'cpp-output', '-c',
                                str(backend.root / 'captured.i'), '-o', str(backend.root / 'probe.o')]))
        headers, output_bindings = {}, {}
        for label, argv in commands:
            command = backend.run(label, argv)
            result['commands'].append(command)
            require(command['status'] == 'success', 'Declared compiler invocation failed: ' + label)
            for suffix in ('stdout', 'stderr'):
                output_bindings[label + '.' + suffix] = command[suffix]
            if label == 'dependencies':
                body, _ = backend.read_output('dependencies.stdout', MAX_OUTPUT)
                dependencies = parse_dependencies(body, str(source))
                total = 0
                for path in dependencies:
                    canonical = os.path.realpath(path)
                    row = backend.snapshot(canonical, MAX_HEADER)
                    total += row['bytes']
                    require(total <= MAX_HEADERS_TOTAL, 'Header closure exceeds fixed total byte limit')
                    headers[path] = row
                result['headers'] = headers
            if label == 'preprocess':
                body, row = backend.read_output('preprocess.d', MAX_OUTPUT)
                output_bindings['preprocess.d'] = row
                require(set(parse_dependencies(body, str(source))) == set(headers),
                        'Compiler dependency listings differ')
                cpp, _ = backend.read_output('preprocess.stdout', MAX_OUTPUT)
                result['cpp_facts'] = parse_cpp_facts(cpp)
                output_bindings['captured.i'] = backend.write_output('captured.i', cpp)
            if label in ('preprocess', 'object'):
                for path, row in headers.items():
                    require(os.path.realpath(path) == row['path']
                            and backend.snapshot(row['path'], MAX_HEADER) == row,
                            'Source/header bytes or identity changed')
        body, row = backend.read_output('probe.o', MAX_OUTPUT)
        result['object'] = {**row, **parse_elf_object(body)}
        output_bindings['probe.o'] = row
        require(backend.snapshot(executable, MAX_DRIVER) ==
                {key: value for key, value in compiler.items() if key != 'role_path'}
                and os.path.realpath(compiler['role_path']) == executable,
                'Compiler driver bytes/identity/role changed')
        for name, original in output_bindings.items():
            require(backend.read_output(name, MAX_OUTPUT)[1] == original,
                    'Captured compiler output changed')
        result['output_bindings'] = output_bindings
        result['status'] = 'success'
        result.update(dict.fromkeys(SUCCESS_FIELDS, True))
    except Exception as error:
        result['error'] = error_fact(error)
    return result


def observe(request_path, expected_sha256):
    require(sys.flags.isolated == sys.flags.no_site == 1 and sys.dont_write_bytecode
            and sys.platform == 'linux' and os.getuid() == os.geteuid(),
            'Fresh Linux -B -I -S file entry with equal UID/eUID required')
    helper = load_identity_helper()
    source = helper.normalized_path(__file__)
    probe = source.with_name('frontier_v8_c_toolchain_probe.c')
    request_path = helper.normalized_path(request_path)
    uid = os.getuid()
    inputs = []
    for path, limit, owner in ((source, helper.MAX_SOURCE_BYTES, None),
                              (probe, helper.MAX_SOURCE_BYTES, None),
                              (Path(helper.__file__), helper.MAX_SOURCE_BYTES, None),
                              (request_path, helper.MAX_REQUEST_BYTES, uid)):
        body, identity = helper.read_regular(str(path), limit, owner=owner)
        inputs.append((path, body, identity, limit, owner))
    source_body, probe_body, helper_body, request_body = (row[1] for row in inputs)
    require(helper_body == helper._captured_bytes and inputs[2][2] == helper._captured_identity,
            'Captured immutable helper changed')
    request = parse_request(request_body, expected_sha256, digest(source_body), digest(probe_body), helper)
    bootstrap = helper.normalized_path(request['bootstrap']['executable'])
    executable_lexical = sys.executable
    require(os.path.realpath(sys.executable) == str(bootstrap), 'Bootstrap executable differs')
    bootstrap_body, bootstrap_identity = helper.read_regular(str(bootstrap), helper.MAX_EXECUTABLE_BYTES)
    require(digest(bootstrap_body) == request['bootstrap']['sha256']
            and list(sys.version_info[:3]) == request['bootstrap']['version'], 'Bootstrap bytes/version differ')
    inputs.append((bootstrap, bootstrap_body, bootstrap_identity, helper.MAX_EXECUTABLE_BYTES, None))
    identity = helper.capture_self_identity()
    require(identity['uid'] == identity['euid'] == request['host']['uid'] == uid
            and identity['boot_id'] == request['host']['boot_id']
            and os.uname().nodename == request['host']['hostname'], 'Current host/self identity differs')
    root = helper.normalized_path(request['attempt_directory'])
    require(not any(str(root).startswith(prefix) for prefix in FORBIDDEN_OUTPUT_PREFIXES),
            'Consumed earlier output boundary refused')
    marker = root.with_name(root.name + '.consumed.json')
    for output in (root, marker):
        require(all(output != row[0] and not output.is_relative_to(row[0])
                    and not row[0].is_relative_to(output) for row in inputs), 'Output overlaps an input')
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
                             'c_probe_sha256': digest(probe_body), 'identity_helper_sha256': HELPER_SHA,
                             'attempt_directory': str(root)})
        os.fsync(parent)
        marker_body, marker_identity = helper.read_regular(str(marker), helper.MAX_REQUEST_BYTES, owner=uid)
        receipt = {**AUTHORITY, **dict.fromkeys(SUCCESS_FIELDS, False),
                   'schema_version': 1, 'scope': SCOPE, 'status': 'failed', 'nonce': request['nonce'],
                   'request_sha256': expected_sha256, 'attempt_directory': str(root),
                   'source': {'file': str(source), 'sha256': digest(source_body)},
                   'c_probe': {'file': str(probe), 'sha256': digest(probe_body)},
                   'identity_helper': {'file': helper.__file__, 'sha256': HELPER_SHA,
                                       'captured_byte_body_executed': True,
                                       'old_observe_or_CLI_called': False},
                   'self_identity': identity, 'host': {**request['host'], 'node_alias_authenticated': False},
                   'bootstrap': {'executable_lexical': executable_lexical,
                                 'executable_resolved': str(bootstrap), 'sha256': digest(bootstrap_body),
                                 'version': list(sys.version_info[:3])},
                   'input_and_self_identity_postvalidation_passed': False,
                   'trusted_inputs': 'CPython/stdlib/compiler/filesystem; not a sandbox or full toolchain closure',
                   'native_guard_executed_or_modified': False, 'os_api_shim_installed': False,
                   'product_link_or_execution_attempts': 0, 'pidfd_or_syscall_entry_attempts': 0}
        try:
            os.mkdir(root.name, 0o700, dir_fd=parent)
            root_fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=parent)
            root_info = os.fstat(root_fd)
            require(root_info.st_uid == uid, 'New output owner differs')
            os.mkdir('tmp', 0o700, dir_fd=root_fd)
            receipt['toolchain'] = run_toolchain(probe, CompilerBackend(helper, root, root_fd))
            for path, body, original, limit, owner in inputs:
                later, later_identity = helper.read_regular(str(path), limit, owner=owner)
                require(later == body and later_identity == original, 'Input changed at postvalidation')
            marker_after, marker_after_identity = helper.read_regular(
                str(marker), helper.MAX_REQUEST_BYTES, owner=uid)
            require(marker_after == marker_body and marker_after_identity == marker_identity,
                    'Consumed marker bytes/identity changed')
            after = helper.capture_self_identity()
            require(all(after[key] == identity[key] for key in
                        ('boot_id', 'pid', 'ppid', 'start_ticks', 'uid', 'euid', 'proc_uids'))
                    and os.getuid() == os.geteuid() == uid, 'Self identity/privilege changed')
            require(__file__ == str(source) and helper.__file__ == str(source.with_name(
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
            if receipt['toolchain']['status'] == 'success':
                receipt['status'] = 'compiler_header_target_observed'
                receipt.update(dict.fromkeys(SUCCESS_FIELDS, True))
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
        raise ToolchainError('Execution unavailable; separate compiler/header/compile-target observation only')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-c-toolchain', action='store_true')
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-request-sha256', required=True)
    args = parser.parse_args(argv)
    require(args.observe_c_toolchain, 'Explicit separately declared toolchain observation required')
    receipt = observe(args.request, args.expected_request_sha256)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['status'] == 'compiler_header_target_observed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
