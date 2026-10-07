"""Dedicated current-PID C descriptor selfcheck; no containment or model authority."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
from types import ModuleType


SCOPE = 'frontier_v8_owned_kernel_C_selfcheck'
HELPER_SHA = '1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412'
TOOLCHAIN_SHA = '2175f96e939993db69eb14348fa3115ae583416a1d38307f38f23bd378d003c0'
FIELDS = {'schema_version', 'scope', 'nonce', 'observer_sha256', 'c_probe_sha256',
          'identity_helper_sha256', 'toolchain_sha256', 'attempt_directory', 'host', 'bootstrap'}
AUTHORITY = dict.fromkeys(('functional_containment_verified', 'containment_available',
                          'execution_available', 'resource_authority',
                          'model_runtime_ABI_observed'), False)
SUCCESS = ('native_C_runtime_ABI_observed', 'own_pidfd_operations_verified')
MAX_BYTES = 8 * 1024 * 1024
FORBIDDEN_OUTPUT_PREFIXES = (
    '/data/zefan/open-jev-v8-runtime-abi-', '/data/zefan/open-jev-v8-containment-presence-',
    '/data/zefan/open-jev-v8-pidfd-selfcheck-', '/data/zefan/open-jev-v8-linux-runtime-',
    '/data/zefan/open-jev-v8-c-toolchain-',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def error_fact(error):
    return {'type': type(error).__name__, 'message': str(error)}


def load_utilities():
    """Execute captured pinned utility bytes, never their old observe/CLI routes."""
    source = Path(__file__)
    require(source.is_absolute() and source.as_posix() == __file__ and '..' not in source.parts
            and not any(source.is_relative_to(Path(p)) for p in ('/proc', '/sys', '/dev')),
            'Canonical nonvirtual file entry required')
    helper_path = source.with_name('frontier_v8_containment_capability.py')
    name = 'frontier_v8_owned_c_identity_helper'
    require(name not in sys.modules, 'Captured helper cache refused')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    parent, fd = os.open('/', flags), None
    try:
        for part in helper_path.parent.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=parent)
            os.close(parent)
            parent = next_fd
        fd = os.open(helper_path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
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
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        identity = tuple(getattr(before, key) for key in keys)
        require(count <= 1024 * 1024 and digest(body) == HELPER_SHA
                and tuple(getattr(os.fstat(fd), key) for key in keys) == identity
                and tuple(getattr(os.stat(helper_path.name, dir_fd=parent, follow_symlinks=False), key)
                          for key in keys) == identity, 'Captured helper bytes/identity differ')
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)
    helper = ModuleType(name)
    helper.__file__, helper.__package__ = str(helper_path), None
    exec(compile(body, str(helper_path), 'exec', dont_inherit=True), helper.__dict__)
    helper._captured_bytes, helper._captured_identity = body, identity
    utility_path = source.with_name('frontier_v8_c_toolchain.py')
    utility_body, utility_identity = helper.read_regular(str(utility_path), helper.MAX_SOURCE_BYTES)
    name = 'frontier_v8_owned_c_build_utility'
    require(digest(utility_body) == TOOLCHAIN_SHA and name not in sys.modules,
            'Captured toolchain source/cache differs')
    utility = ModuleType(name)
    utility.__file__, utility.__package__ = str(utility_path), None
    exec(compile(utility_body, str(utility_path), 'exec', dont_inherit=True), utility.__dict__)
    utility._captured_bytes, utility._captured_identity = utility_body, utility_identity
    return helper, utility


def parse_request(body, expected_sha256, source_sha256, probe_sha256, helper):
    require(type(expected_sha256) is str and re.fullmatch(r'[0-9a-f]{64}', expected_sha256)
            and digest(body) == expected_sha256, 'Exact request bytes required')
    request = json.loads(body, object_pairs_hook=helper._unique_object,
                         parse_constant=lambda value: require(False, 'Nonfinite JSON refused'))
    require(type(request) is dict and set(request) == FIELDS
            and type(request['schema_version']) is int and request['schema_version'] == 1
            and request['scope'] == SCOPE, 'Exact new selfcheck declaration required')
    require(type(request['nonce']) is str and re.fullmatch(r'[0-9a-f]{64}', request['nonce'])
            and request['observer_sha256'] == source_sha256 and request['c_probe_sha256'] == probe_sha256
            and request['identity_helper_sha256'] == HELPER_SHA
            and request['toolchain_sha256'] == TOOLCHAIN_SHA, 'Exact closure and fresh nonce required')
    host, bootstrap = request['host'], request['bootstrap']
    require(type(host) is dict and set(host) == {'node_alias', 'hostname', 'boot_id', 'uid'}
            and host['node_alias'] in helper.NODES and type(host['hostname']) is str
            and 0 < len(host['hostname']) <= 255 and '\0' not in host['hostname']
            and type(host['uid']) is int and host['uid'] >= 0
            and type(host['boot_id']) is str
            and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', host['boot_id']),
            'Exact host declaration required')
    require(type(bootstrap) is dict and set(bootstrap) == {'executable', 'sha256', 'version'}
            and type(bootstrap['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', bootstrap['sha256'])
            and type(bootstrap['version']) is list and len(bootstrap['version']) == 3
            and all(type(x) is int and x >= 0 for x in bootstrap['version']),
            'Exact bootstrap declaration required')
    helper.normalized_path(bootstrap['executable'])
    helper.normalized_path(request['attempt_directory'])
    return request


def parse_link_map(body, object_path):
    """Descriptive LOAD inventory; not the complete inputs or bytes used during link."""
    require(type(body) is bytes and len(body) <= MAX_BYTES, 'Bounded linker map required')
    paths = []
    for line in body.decode('ascii').splitlines():
        if not re.match(r'^\s*LOAD\b', line):
            continue
        match = re.fullmatch(r'LOAD (/[A-Za-z0-9_./+\-]+)', line)
        require(match is not None, 'Unsupported linker LOAD row')
        value = match.group(1)
        path = Path(value)
        normalized = Path(os.path.normpath(value))
        canonical = Path(os.path.realpath(value))
        require(path.as_posix() == value and path.name
                and not any(candidate.is_relative_to(Path(p))
                            for candidate in (normalized, canonical)
                            for p in ('/proc', '/sys', '/dev')),
                'Absolute nonvirtual linker LOAD alias required')
        if value not in paths:
            paths.append(value)
    require(0 < len(paths) <= 256 and str(object_path) in paths,
            'New object and bounded linker LOAD inventory required')
    return tuple(paths)


def parse_elf_product(body):
    """Read ELF descriptors and the actual PT_INTERP path without architecture guesses."""
    require(type(body) is bytes and 64 <= len(body) <= MAX_BYTES
            and body[:4] == b'\x7fELF' and body[4] in (1, 2) and body[5] in (1, 2)
            and body[6] == 1, 'Bounded supported ELF product required')
    cls, order = body[4], '<' if body[5] == 1 else '>'
    kind, machine, version = struct.unpack_from(order + 'HHI', body, 16)
    if cls == 1:
        phoff = struct.unpack_from(order + 'I', body, 28)[0]
        ehsize, phsize, phnum = struct.unpack_from(order + 'HHH', body, 40)
        expected_ehsize, expected_phsize = 52, 32
    else:
        phoff = struct.unpack_from(order + 'Q', body, 32)[0]
        ehsize, phsize, phnum = struct.unpack_from(order + 'HHH', body, 52)
        expected_ehsize, expected_phsize = 64, 56
    require(kind in (2, 3) and version == 1 and ehsize == expected_ehsize
            and phsize == expected_phsize and 0 < phnum <= 128 and phoff >= ehsize
            and phoff + phsize * phnum <= len(body), 'Supported dynamic ELF header required')
    interpreters = []
    for index in range(phnum):
        start = phoff + index * phsize
        if struct.unpack_from(order + 'I', body, start)[0] != 3:
            continue
        offset = struct.unpack_from(order + ('I' if cls == 1 else 'Q'), body,
                                    start + (4 if cls == 1 else 8))[0]
        size = struct.unpack_from(order + ('I' if cls == 1 else 'Q'), body,
                                  start + (16 if cls == 1 else 32))[0]
        require(2 <= size <= 4096 and offset >= ehsize and offset + size <= len(body),
                'Bounded PT_INTERP segment required')
        raw = body[offset:offset + size]
        require(raw[-1:] == b'\0' and b'\0' not in raw[:-1], 'One terminated PT_INTERP path required')
        value = raw[:-1].decode('ascii')
        path = Path(value)
        require(re.fullmatch(r'/[A-Za-z0-9_./+\-]+', value) and path.as_posix() == value
                and '..' not in path.parts and path.name
                and not any(path.is_relative_to(Path(p)) for p in ('/proc', '/sys', '/dev')),
                'Absolute nonvirtual actual PT_INTERP path required')
        interpreters.append(value)
    require(len(interpreters) == 1, 'Exactly one PT_INTERP required; static products unsupported')
    return {'elf_class': cls, 'data_encoding': body[5], 'elf_type': kind,
            'machine': machine, 'interpreter': interpreters[0]}


def parse_runtime(body, command, cpp_facts, expected_parent_pid, expected_uid):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate C JSON key refused')
            result[key] = value
        return result
    require(type(body) is bytes and 0 < len(body) <= 16384, 'Bounded complete C JSON required')
    row = json.loads(body, object_pairs_hook=unique,
                     parse_constant=lambda value: require(False, 'Nonfinite C JSON refused'))
    booleans = ('open_attempted', 'pidfd_acquired', 'fdinfo_verified', 'poll_attempted',
                'close_attempted', 'ebadf_check_attempted', 'ebadf_verified')
    integers = ('schema_version', 'error_errno', 'pid', 'ppid', 'uid', 'euid', 'header_pidfd_open',
                'int_bytes', 'long_bytes', 'pointer_bytes', 'char_bits', 'byte_order', 'proc_self_pid',
                'pidfd', 'fdinfo_pid', 'poll_result', 'poll_revents', 'close_calls', 'close_result',
                'close_errno', 'ebadf_result', 'ebadf_errno', 'poll_events', 'header_pollin', 'header_ebadf')
    require(type(row) is dict and set(row) == set(booleans + integers + ('status', 'error_stage'))
            and all(type(row[key]) is bool for key in booleans)
            and all(type(row[key]) is int for key in integers) and row['schema_version'] == 1
            and row['status'] in ('success', 'failed') and type(row['error_stage']) is str
            and re.fullmatch(r'[a-z_]+', row['error_stage']) and row['error_errno'] >= 0,
            'Exact typed C runtime facts required')
    require(type(command.get('direct_child_pid')) is int and row['pid'] == command['direct_child_pid']
            and row['pid'] > 0 and row['ppid'] == expected_parent_pid
            and row['uid'] == row['euid'] == expected_uid, 'Fresh direct C self identity differs')
    for key in ('int_bytes', 'long_bytes', 'pointer_bytes', 'char_bits', 'byte_order'):
        require(row[key] == cpp_facts['target_' + key], 'C runtime scalar target baseline differs')
    require(row['header_pidfd_open'] >= 0 and row['close_calls'] in (0, 1)
            and row['close_attempted'] == (row['close_calls'] == 1), 'C descriptor bookkeeping differs')
    if row['status'] == 'success':
        require(command['status'] == 'success' and command['returncode'] == 0
                and command['reap_completed'] and not command['timed_out']
                and row['error_stage'] == 'none' and row['error_errno'] == 0
                and all(row[key] for key in booleans) and row['pidfd'] >= 0
                and row['proc_self_pid'] == row['fdinfo_pid'] == row['pid']
                and row['poll_result'] == row['poll_revents'] == 0
                and row['poll_events'] == row['header_pollin'] > 0
                and row['close_calls'] == 1 and row['close_result'] == row['close_errno'] == 0
                and row['ebadf_result'] == -1
                and row['ebadf_errno'] == row['header_ebadf'] == errno.EBADF,
                'C successful own descriptor chain differs')
    else:
        require(row['error_stage'] != 'none', 'Failed C result must retain a failing operation')
    return row


def run_selfcheck(source, backend, utility, expected_parent_pid, expected_uid, pre_runtime_check=None):
    result = {**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'status': 'failed',
              'commands': [], 'link_attempts': 0, 'runtime_attempts': 0,
              'pidfd_entry_attempted_reported': None, 'complete_mapped_code_authenticated': False}
    try:
        if pre_runtime_check is not None:
            pre_runtime_check()
        result['compile_leg'] = build = utility.run_toolchain(source, backend)
        require(build['status'] == 'success', 'Fresh dedicated C compile leg failed')
        compiler = build['compiler']
        product, object_path = backend.root / 'selfcheck', backend.root / 'probe.o'
        result['link_attempts'] = 1
        command = backend.run('link', [compiler['path'], str(object_path), '-Wl,-Map,' +
                                       str(backend.root / 'link.map'), '-o', str(product)])
        result['commands'].append(command)
        require(command['status'] == 'success', 'Dedicated C link failed')
        body, map_row = backend.read_output('link.map', MAX_BYTES)
        links, total = {}, 0
        for path in parse_link_map(body, object_path):
            links[path] = row = backend.snapshot(os.path.realpath(path), utility.MAX_DRIVER)
            total += row['bytes']
            require(total <= utility.MAX_HEADERS_TOTAL, 'Link inventory total byte limit exceeded')
        body, product_row = backend.read_output('selfcheck', MAX_BYTES)
        require(product_row['identity'][2] & 0o111, 'Executable product mode required')
        result['product'] = {**product_row, **parse_elf_product(body)}
        require(all(result['product'][key] == build['object'][key]
                    for key in ('elf_class', 'data_encoding', 'machine')),
                'Object and product ELF descriptors differ')
        interpreter_path = result['product']['interpreter']
        interpreter = backend.snapshot(os.path.realpath(interpreter_path), utility.MAX_DRIVER)
        result['interpreter'] = interpreter
        result['link_inputs_after_link'] = links
        bound = {**build['output_bindings'], 'link.map': map_row, 'selfcheck': product_row,
                 'link.stdout': command['stdout'], 'link.stderr': command['stderr']}

        def recheck():
            for path, row in {**build['headers'], **links}.items():
                require(os.path.realpath(path) == row['path']
                        and backend.snapshot(row['path'], utility.MAX_DRIVER) == row,
                        'Source/header/link inventory drift')
            require(os.path.realpath(compiler['role_path']) == compiler['path']
                    and backend.snapshot(compiler['path'], utility.MAX_DRIVER) ==
                    {key: value for key, value in compiler.items() if key != 'role_path'},
                    'Compiler driver/role drift')
            require(os.path.realpath(interpreter_path) == interpreter['path']
                    and backend.snapshot(interpreter['path'], utility.MAX_DRIVER) == interpreter,
                    'Actual interpreter descriptor drift')
            for name, row in bound.items():
                require(backend.read_output(name, MAX_BYTES)[1] == row, 'Bound output drift')
        recheck()
        if pre_runtime_check is not None:
            pre_runtime_check()
        result['runtime_attempts'] = 1
        runtime = backend.run('runtime', [str(product)])
        result['commands'].append(runtime)
        runtime_body, _ = backend.read_output('runtime.stdout', MAX_BYTES)
        # Handled negative C facts survive a nonzero child returncode.
        result['runtime_report'] = facts = parse_runtime(runtime_body, runtime, build['cpp_facts'],
                                                        expected_parent_pid, expected_uid)
        result['pidfd_entry_attempted_reported'] = facts['open_attempted']
        bound.update({'runtime.stdout': runtime['stdout'], 'runtime.stderr': runtime['stderr']})
        recheck()
        result['output_bindings'] = bound
        require(runtime['status'] == 'success' and facts['status'] == 'success',
                'Dedicated C selfcheck returned a terminal negative result')
        result.update(dict.fromkeys(SUCCESS, True))
        result['status'] = 'success'
    except Exception as error:
        result['error'] = error_fact(error)
    return result


def observe(request_path, expected_sha256):
    require(sys.platform == 'linux' and sys.flags.isolated == sys.flags.no_site == 1
            and sys.dont_write_bytecode and os.getuid() == os.geteuid(),
            'Fresh equal-UID Linux -B -I -S file entry required')
    helper, utility = load_utilities()
    source = helper.normalized_path(__file__)
    probe = source.with_name('frontier_v8_owned_c_selfcheck.c')
    uid, inputs = os.getuid(), []
    for path, limit, owner in ((source, helper.MAX_SOURCE_BYTES, None),
                              (probe, helper.MAX_SOURCE_BYTES, None),
                              (Path(helper.__file__), helper.MAX_SOURCE_BYTES, None),
                              (Path(utility.__file__), helper.MAX_SOURCE_BYTES, None),
                              (helper.normalized_path(request_path), helper.MAX_REQUEST_BYTES, uid)):
        body, identity = helper.read_regular(str(path), limit, owner=owner)
        inputs.append((path, body, identity, limit, owner))
    require(inputs[2][1:3] == (helper._captured_bytes, helper._captured_identity)
            and inputs[3][1:3] == (utility._captured_bytes, utility._captured_identity),
            'Captured utility inputs changed')
    request = parse_request(inputs[4][1], expected_sha256, digest(inputs[0][1]), digest(inputs[1][1]), helper)
    bootstrap = helper.normalized_path(request['bootstrap']['executable'])
    lexical_executable = sys.executable
    require(os.path.realpath(sys.executable) == str(bootstrap), 'Bootstrap executable differs')
    body, identity = helper.read_regular(str(bootstrap), helper.MAX_EXECUTABLE_BYTES)
    require(digest(body) == request['bootstrap']['sha256']
            and list(sys.version_info[:3]) == request['bootstrap']['version'], 'Bootstrap bytes/version differ')
    inputs.append((bootstrap, body, identity, helper.MAX_EXECUTABLE_BYTES, None))
    own = helper.capture_self_identity()
    require(own['uid'] == own['euid'] == request['host']['uid'] == uid
            and own['boot_id'] == request['host']['boot_id']
            and os.uname().nodename == request['host']['hostname'], 'Current host/self identity differs')
    root = helper.normalized_path(request['attempt_directory'])
    require(not any(str(root).startswith(prefix) for prefix in FORBIDDEN_OUTPUT_PREFIXES),
            'Consumed earlier host output boundary refused')
    marker = root.with_name(root.name + '.consumed.json')
    for output in (root, marker):
        require(all(output != row[0] and not output.is_relative_to(row[0])
                    and not row[0].is_relative_to(output) for row in inputs), 'Output overlaps input')
    parent, root_fd = helper.open_parent(root), None
    try:
        boundary = os.fstat(parent)
        require(boundary.st_uid == uid, 'Owned fresh output parent required')
        helper._absent(parent, root.name)
        helper._absent(parent, marker.name)
        helper.write_json_at(parent, marker.name, {**AUTHORITY, 'schema_version': 1, 'status': 'consumed',
                             'scope': SCOPE, 'nonce': request['nonce'], 'request_sha256': expected_sha256,
                             'observer_sha256': digest(inputs[0][1]), 'c_probe_sha256': digest(inputs[1][1]),
                             'identity_helper_sha256': HELPER_SHA, 'toolchain_sha256': TOOLCHAIN_SHA})
        os.fsync(parent)
        marker_body, marker_identity = helper.read_regular(str(marker), helper.MAX_REQUEST_BYTES, owner=uid)
        receipt = {**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'schema_version': 1, 'scope': SCOPE,
                   'status': 'failed', 'nonce': request['nonce'], 'request_sha256': expected_sha256,
                   'attempt_directory': str(root), 'self_identity': own, 'host': request['host'],
                   'node_alias_authenticated': False, 'input_and_self_identity_postvalidation_passed': False,
                   'captured_utilities': {'identity_sha256': HELPER_SHA, 'toolchain_sha256': TOOLCHAIN_SHA,
                                          'old_observe_or_CLI_called': False},
                   'trusted_baseline': 'CPython/stdlib/compiler/linker/loader/libc/filesystem; not full mapped-code auth',
                   'native_guard_executed_or_modified': False, 'os_api_shim_installed': False}
        try:
            os.mkdir(root.name, 0o700, dir_fd=parent)
            root_fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=parent)
            root_info = os.fstat(root_fd)
            require(root_info.st_uid == uid, 'Output directory owner differs')
            os.mkdir('tmp', 0o700, dir_fd=root_fd)

            def validate_inputs():
                for path, body, identity, limit, owner in inputs:
                    require(helper.read_regular(str(path), limit, owner=owner) == (body, identity),
                            'Input bytes/identity drift')
                require(helper.read_regular(str(marker), helper.MAX_REQUEST_BYTES, owner=uid) ==
                        (marker_body, marker_identity), 'Consumed marker drift')
                after = helper.capture_self_identity()
                require(all(after[key] == own[key] for key in
                            ('boot_id', 'pid', 'ppid', 'start_ticks', 'uid', 'euid', 'proc_uids'))
                        and os.getuid() == os.geteuid() == uid, 'Observer self identity drift')

            receipt['selfcheck'] = run_selfcheck(probe, utility.CompilerBackend(helper, root, root_fd),
                                                utility, own['pid'], uid, validate_inputs)
            validate_inputs()
            require(__file__ == str(source) and helper.__file__ == str(source.with_name(
                        'frontier_v8_containment_capability.py'))
                    and utility.__file__ == str(source.with_name('frontier_v8_c_toolchain.py'))
                    and sys.executable == lexical_executable
                    and os.path.realpath(sys.executable) == str(bootstrap)
                    and list(sys.version_info[:3]) == request['bootstrap']['version']
                    and os.uname().nodename == request['host']['hostname'], 'Entry/bootstrap/host drift')
            check = helper.open_parent(root)
            try:
                latest = os.fstat(check)
                require((latest.st_dev, latest.st_ino, latest.st_uid) ==
                        (boundary.st_dev, boundary.st_ino, uid), 'Output parent drift')
                latest = os.stat(root.name, dir_fd=check, follow_symlinks=False)
                require(stat.S_ISDIR(latest.st_mode) and (latest.st_dev, latest.st_ino, latest.st_uid) ==
                        (root_info.st_dev, root_info.st_ino, uid), 'Output directory drift')
            finally:
                os.close(check)
            receipt['input_and_self_identity_postvalidation_passed'] = True
            if receipt['selfcheck']['status'] == 'success':
                receipt['status'] = 'owned_C_current_PID_descriptor_observed'
                receipt.update(dict.fromkeys(SUCCESS, True))
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
        raise ValueError('Execution unavailable; separately declared own-current-PID C selfcheck only')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-owned-c-selfcheck', action='store_true')
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-request-sha256', required=True)
    args = parser.parse_args(argv)
    require(args.observe_owned_c_selfcheck, 'Explicit separate own-C selfcheck required')
    receipt = observe(args.request, args.expected_request_sha256)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['status'] == 'owned_C_current_PID_descriptor_observed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
