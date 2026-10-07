"""Fixed owned C worker lifecycle observations; no production or model authority."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import stat
import sys
from types import ModuleType


SCOPE = 'frontier_v8_owned_C_direct_worker_lifecycle_fixture'
HELPER_SHA = '1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412'
LINKAGE_SHA = '3374d4ed4ef1bafa38d8f4340ffcc042ee396d966228a682adf890182108b47c'
TOOLCHAIN_SHA = '2175f96e939993db69eb14348fa3115ae583416a1d38307f38f23bd378d003c0'
FIELDS = {'schema_version', 'scope', 'nonce', 'observer_sha256', 'c_probe_sha256',
          'identity_helper_sha256', 'toolchain_sha256', 'linkage_sha256', 'case', 'attempt_directory', 'host', 'bootstrap'}
AUTHORITY = dict.fromkeys(('functional_containment_verified', 'containment_available',
                          'execution_available', 'resource_authority',
                          'model_runtime_ABI_observed', 'production_controller_guard_completed',
                          'GPU_or_foreign_restore'), False)
SUCCESS = ('normal_owned_direct_worker_lifecycle_observed',
           'controlled_controller_loss_worker_reaped_observed')
MAX_BYTES = 8 * 1024 * 1024
FORBIDDEN_OUTPUT_PREFIXES = (
    '/data/zefan/open-jev-v8-runtime-abi-', '/data/zefan/open-jev-v8-containment-presence-',
    '/data/zefan/open-jev-v8-pidfd-selfcheck-', '/data/zefan/open-jev-v8-linux-runtime-',
    '/data/zefan/open-jev-v8-c-toolchain-', '/data/zefan/open-jev-v8-owned-c-selfcheck-',
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
    name = 'frontier_v8_lifecycle_identity_helper'
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
    name = 'frontier_v8_lifecycle_build_utility'
    require(digest(utility_body) == TOOLCHAIN_SHA and name not in sys.modules,
            'Captured toolchain source/cache differs')
    utility = ModuleType(name)
    utility.__file__, utility.__package__ = str(utility_path), None
    exec(compile(utility_body, str(utility_path), 'exec', dont_inherit=True), utility.__dict__)
    utility._captured_bytes, utility._captured_identity = utility_body, utility_identity
    linkage_path = source.with_name('frontier_v8_owned_c_selfcheck.py')
    linkage_body, linkage_identity = helper.read_regular(str(linkage_path), helper.MAX_SOURCE_BYTES)
    name = 'frontier_v8_lifecycle_linkage_utility'
    require(digest(linkage_body) == LINKAGE_SHA and name not in sys.modules,
            'Captured linkage source/cache differs')
    linkage = ModuleType(name)
    linkage.__file__, linkage.__package__ = str(linkage_path), None
    exec(compile(linkage_body, str(linkage_path), 'exec', dont_inherit=True), linkage.__dict__)
    linkage._captured_bytes, linkage._captured_identity = linkage_body, linkage_identity
    return helper, utility, linkage


def parse_request(body, expected_sha256, source_sha256, probe_sha256, helper):
    require(type(expected_sha256) is str and re.fullmatch(r'[0-9a-f]{64}', expected_sha256)
            and digest(body) == expected_sha256, 'Exact request bytes required')
    request = json.loads(body, object_pairs_hook=helper._unique_object,
                         parse_constant=lambda value: require(False, 'Nonfinite JSON refused'))
    require(type(request) is dict and set(request) == FIELDS
            and type(request['schema_version']) is int and request['schema_version'] == 1
            and request['scope'] == SCOPE, 'Exact new lifecycle declaration required')
    require(type(request['nonce']) is str and re.fullmatch(r'[0-9a-f]{64}', request['nonce'])
            and request['observer_sha256'] == source_sha256 and request['c_probe_sha256'] == probe_sha256
            and request['identity_helper_sha256'] == HELPER_SHA
            and request['toolchain_sha256'] == TOOLCHAIN_SHA
            and request['linkage_sha256'] == LINKAGE_SHA
            and type(request['case']) is str and request['case'] in ('normal', 'controller_loss'), 'Exact closure and fresh nonce required')
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


def parse_runtime(body, command, cpp_facts, expected_parent_pid, expected_uid,
                  expected_boot_id, case, nonce, product_identity):
    """Recompute fixed outcomes from controlled-C facts, under its trusted baseline."""
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'Duplicate C JSON key refused')
            value[key] = item
        return value

    def fields(value, names):
        require(type(value) is dict and set(value) == set(names.split()), 'Exact fact fields required')

    def number(value, *, low=0, high=(1 << 63) - 1, optional=False):
        require((optional and value is None) or (type(value) is int and low <= value <= high),
                'Bounded typed integer required')

    def numeric_record(value, names, optional=True):
        for key in names.split():
            number(value[key], low=-1 if key in ('fd', 'result', 'open_result', 'close_result',
                                                'ebadf_result') else 0,
                   high=(1 << 31) - 1, optional=optional)

    def stat7(value):
        require(type(value) is list and len(value) == 7, 'Exact product stat7 required')
        for item in value:
            number(item, high=(1 << 64) - 1)

    require(type(body) is bytes and 0 < len(body) <= 65536, 'Bounded complete C JSON required')
    row = json.loads(body, object_pairs_hook=unique,
                     parse_constant=lambda value: require(False, 'Nonfinite C JSON refused'))
    fields(row, 'schema_version scope status case nonce error headers identities identity_rechecks '
                'product_identity product_rechecks handshakes pidfds polls waits worker_signal '
                'deadlines self_sigpipe_ignore inherited_closes coordinator_cleanup_signals')
    require(type(row['schema_version']) is int and row['schema_version'] == 1 and row['scope'] == SCOPE
            and type(row['status']) is str and row['status'] in ('success', 'failed')
            and type(case) is str and case in ('normal', 'controller_loss') and row['case'] == case
            and type(nonce) is str and re.fullmatch(r'[0-9a-f]{64}', nonce) and row['nonce'] == nonce,
            'Exact fixed case/nonce scope required')
    fields(row['error'], 'stage errno')
    require(type(row['error']['stage']) is str and re.fullmatch(r'[a-z_]+', row['error']['stage']),
            'Typed first error stage required')
    number(row['error']['errno'], high=(1 << 31) - 1)
    h = row['headers']
    fields(h, 'pidfd_open pidfd_send_signal sigkill sigpipe pollin pollnval ebadf int_bytes long_bytes '
              'pointer_bytes char_bits byte_order packet_magic identity_packet_bytes command_packet_bytes '
              'terminal_packet_bytes controller_loss_exit_code')
    for value in h.values():
        number(value)
    require(all(h[k] == cpp_facts['target_' + k] for k in
                ('int_bytes', 'long_bytes', 'pointer_bytes', 'char_bits', 'byte_order'))
            and h['char_bits'] == 8 and h['controller_loss_exit_code'] == 23
            and h['sigkill'] == signal.SIGKILL and h['sigpipe'] == signal.SIGPIPE
            and h['pollin'] == select.POLLIN and h['pollnval'] == select.POLLNVAL
            and h['ebadf'] == errno.EBADF
            and all(0 < h[k] <= 4096 for k in ('identity_packet_bytes', 'command_packet_bytes',
                                             'terminal_packet_bytes'))
            and all(h[k] > 0 for k in ('sigkill', 'sigpipe', 'pollin', 'pollnval', 'ebadf', 'packet_magic')),
            'Reviewed C header/scalar/packet baseline differs')
    ids, checks = row['identities'], row['identity_rechecks']
    fields(ids, 'coordinator controller guard worker')
    fields(checks, 'guard_before_arm worker_before_arm guard_before_signal worker_before_signal')
    for value in (*ids.values(), *checks.values()):
        if value is None:
            continue
        fields(value, 'pid ppid uid euid start_ticks boot_id')
        for key in ('pid', 'ppid', 'uid', 'euid', 'start_ticks'):
            number(value[key], low=1 if key in ('pid', 'ppid', 'start_ticks') else 0)
        require(value['uid'] == value['euid'] == expected_uid and value['boot_id'] == expected_boot_id,
                'Observed boot/UID differs')
    if row['product_identity'] is not None:
        stat7(row['product_identity'])
        require(row['product_identity'] == list(product_identity), 'Bound runtime product differs')
    fields(row['product_rechecks'], 'before_arm before_signal')
    for value in row['product_rechecks'].values():
        if value is not None:
            stat7(value)
    packets = row['handshakes']
    fields(packets, 'controller_ready guard_ready guard_start worker_ready guard_worker_ready '
                    'case_arm case_ack controller_quit worker_quit guard_terminal')
    roles = {'controller_ready': 'controller', 'guard_ready': 'guard', 'guard_start': 'coordinator',
             'worker_ready': 'worker', 'guard_worker_ready': 'guard', 'case_arm': 'coordinator',
             'case_ack': 'guard', 'controller_quit': 'coordinator', 'worker_quit': 'guard',
             'guard_terminal': 'guard'}
    for key, value in packets.items():
        if value is None:
            continue
        fields(value, 'bytes magic kind role nonce case')
        number(value['bytes'], low=1, high=4096)
        number(value['magic'], low=1)
        size = ('terminal_packet_bytes' if key == 'guard_terminal' else
                'identity_packet_bytes' if key.endswith('ready') else 'command_packet_bytes')
        require(value['bytes'] == h[size] and value['magic'] == h['packet_magic']
                and value['kind'] == key and value['role'] == roles[key]
                and value['nonce'] == nonce and value['case'] == case, 'Private packet binding differs')
    fds = row['pidfds']
    fields(fds, 'coordinator_controller coordinator_guard guard_controller guard_worker')
    for value in fds.values():
        if value is None:
            continue
        fields(value, 'acquisition fd open_result open_errno fdinfo_pid close_calls close_result '
                      'close_errno ebadf_result ebadf_errno')
        require(value['acquisition'] in ('open', 'inherited', 'none'), 'Typed pidfd acquisition required')
        numeric_record(value, 'fd open_result open_errno fdinfo_pid close_result close_errno '
                              'ebadf_result ebadf_errno')
        number(value['close_calls'], high=1)
    polls = row['polls']
    fields(polls, 'controller_alive_before_arm controller_exit guard_controller_exit worker_exit guard_exit')
    for value in polls.values():
        if value is None:
            continue
        fields(value, 'calls fd result revents events errno')
        numeric_record(value, 'result revents errno')
        numeric_record(value, 'calls fd events', optional=False)
    waits = row['waits']
    fields(waits, 'controller guard worker')
    for key, value in waits.items():
        if value is None:
            continue
        fields(value, 'owner calls pid result status errno exited exit_code signaled term_signal')
        require(value['owner'] == ('guard' if key == 'worker' else 'coordinator'), 'Wait ownership differs')
        number(value['calls'], high=(1 << 31) - 1)
        numeric_record(value, 'pid result errno exit_code term_signal')
        number(value['status'], high=65535, optional=True)
        for name in ('exited', 'signaled'):
            require(value[name] is None or type(value[name]) is bool, 'Typed wait classification required')
        if value['status'] is not None:
            raw = value['status']
            ex, sig = os.WIFEXITED(raw), os.WIFSIGNALED(raw)
            require(value['exited'] is ex and value['signaled'] is sig
                    and value['exit_code'] == (os.WEXITSTATUS(raw) if ex else None)
                    and value['term_signal'] == (os.WTERMSIG(raw) if sig else None),
                    'Raw wait classification differs')
    fields(row['coordinator_cleanup_signals'], 'controller guard')
    for value in (row['worker_signal'], *row['coordinator_cleanup_signals'].values()):
        if value is not None:
            fields(value, 'attempts fd number flags result errno')
            number(value['attempts'], high=1)
            numeric_record(value, 'fd number flags result errno')
    fields(row['inherited_closes'], 'controller guard worker')
    for values in row['inherited_closes'].values():
        require(values is None or (type(values) is list and len(values) <= 32), 'Bounded close ledger required')
        for value in values or ():
            fields(value, 'fd kind result errno ebadf_result ebadf_errno')
            require(type(value['kind']) is str and re.fullmatch(r'[a-z_]+', value['kind']), 'Typed FD role required')
            numeric_record(value, 'fd result errno ebadf_result ebadf_errno', optional=False)
    d = row['deadlines']
    fields(d, 't0_ns work_ns cleanup_ns terminal_ns worker_ns total_ns guard_arm_ns guard_ack_ns '
              'controller_command_ns controller_exit_ns worker_signal_ns worker_exit_ns worker_reaped_ns '
              'guard_terminal_ns coordinator_final_ns')
    for value in d.values():
        number(value, optional=True)
    sigpipe = row['self_sigpipe_ignore']
    if sigpipe is not None:
        fields(sigpipe, 'result errno')
        numeric_record(sigpipe, 'result errno', optional=False)
    if row['status'] == 'failed':
        require(row['error']['stage'] != 'none', 'Negative must retain first error')
        return row

    require(command['status'] == 'success' and command['returncode'] == 0
            and command['reap_completed'] is True and command['timed_out'] is False
            and row['error'] == {'stage': 'none', 'errno': 0} and sigpipe == {'result': 0, 'errno': 0},
            'Actual coordinator normal return required')
    require(all(value is not None for value in ids.values()) and ids['coordinator']['pid'] == command['direct_child_pid']
            and ids['coordinator']['ppid'] == expected_parent_pid
            and len({x['pid'] for x in ids.values()}) == 4
            and ids['controller']['ppid'] == ids['guard']['ppid'] == ids['coordinator']['pid']
            and ids['worker']['ppid'] == ids['guard']['pid'], 'Owned fork identities differ')
    for role in ('guard', 'worker'):
        require(checks[role + '_before_arm'] == ids[role]
                and checks[role + '_before_signal'] == (ids[role] if case == 'controller_loss' else None),
                'Fresh case identity recheck differs')
    require(row['product_identity'] is not None and row['product_rechecks']['before_arm'] == row['product_identity']
            and row['product_rechecks']['before_signal'] ==
                (row['product_identity'] if case == 'controller_loss' else None), 'Product rechecks differ')
    require(all(x is not None for k, x in packets.items() if k != 'worker_quit')
            and (packets['worker_quit'] is not None) == (case == 'normal'), 'Complete ARM/ACK packet chain required')
    for key, fd in fds.items():
        require(fd is not None and fd['acquisition'] == ('inherited' if key == 'guard_controller' else 'open')
                and fd['fd'] is not None and fd['fd'] >= 0 and fd['fdinfo_pid'] == ids[key.split('_')[-1]]['pid']
                and fd['close_calls'] == 1 and fd['close_result'] == fd['close_errno'] == 0
                and fd['ebadf_result'] == -1 and fd['ebadf_errno'] == h['ebadf'], 'Owned FD closure chain differs')
        require((fd['open_result'] is None and fd['open_errno'] is None) if key == 'guard_controller' else
                (fd['open_result'] == fd['fd'] and fd['open_errno'] == 0), 'Pidfd open/inheritance differs')
    require(fds['guard_controller']['fd'] == fds['coordinator_controller']['fd'], 'Inherited controller FD differs')
    for key, value in polls.items():
        target = {'controller_alive_before_arm': 'guard_controller', 'controller_exit': 'coordinator_controller',
                  'guard_controller_exit': 'guard_controller', 'worker_exit': 'guard_worker',
                  'guard_exit': 'coordinator_guard'}[key]
        require(value is not None and value['calls'] > 0 and value['fd'] == fds[target]['fd']
                and value['events'] == h['pollin'] and value['errno'] == 0, 'Anchored pidfd poll required')
        require(value['result'] == value['revents'] == 0 if key == 'controller_alive_before_arm' else
                value['result'] == 1 and value['revents'] is not None and value['revents'] & h['pollin']
                and not value['revents'] & h['pollnval'], 'Actual expected pidfd event differs')
    for key, value in waits.items():
        require(value is not None and value['calls'] > 0 and value['pid'] == value['result'] == ids[key]['pid']
                and value['errno'] == 0, 'Matching parent waitpid required')
        require(value['signaled'] is True and value['term_signal'] == h['sigkill']
                if key == 'worker' and case == 'controller_loss' else
                value['exited'] is True and value['exit_code'] ==
                (23 if key == 'controller' and case == 'controller_loss' else 0), 'Fixed role wait outcome differs')
    no_signal = {'attempts': 0, 'fd': None, 'number': None, 'flags': None, 'result': None, 'errno': None}
    require(all(x == no_signal for x in row['coordinator_cleanup_signals'].values()), 'Success coordinator signals must be zero')
    require(row['worker_signal'] == (no_signal if case == 'normal' else
            {'attempts': 1, 'fd': fds['guard_worker']['fd'], 'number': h['sigkill'], 'flags': 0, 'result': 0, 'errno': 0}),
            'Single owned worker signal ledger differs')
    for values in row['inherited_closes'].values():
        # A later private pipe may reuse a closed stdio number; names distinguish handles.
        require(values is not None and len({(x['kind'], x['fd']) for x in values}) == len(values)
                and all(x['fd'] >= 0 and x['result'] == x['errno'] == 0 and x['ebadf_result'] == -1
                        and x['ebadf_errno'] == h['ebadf'] for x in values), 'Inherited per-role closes differ')
    require({'controller_pidfd', 'guard_report_write', 'guard_command_read',
             'worker_ready_read', 'worker_command_write'} <=
            {x['kind'] for x in row['inherited_closes']['worker']},
            'Worker inherited liveness/report writers must be closed before readiness')
    require('controller_command_write' in {x['kind'] for x in row['inherited_closes']['guard']},
            'Guard must close inherited controller command writer')
    controller_copies = [x for x in row['inherited_closes']['worker'] if x['kind'] == 'controller_pidfd']
    require(len(controller_copies) == 1 and controller_copies[0]['fd'] == fds['guard_controller']['fd'],
            'Worker closure must match the inherited controller pidfd')
    t0 = d['t0_ns']
    require(t0 is not None and all(d[key] == t0 + seconds * 1000000000 for key, seconds in
            (('work_ns', 5), ('cleanup_ns', 8), ('terminal_ns', 10), ('worker_ns', 12), ('total_ns', 14)))
            and all(d[k] is not None for k in d if k != 'worker_signal_ns'), 'Inherited absolute budgets differ')
    require(t0 <= d['guard_arm_ns'] <= d['guard_ack_ns'] <= d['controller_command_ns'] <= d['work_ns']
            and d['controller_command_ns'] <= d['controller_exit_ns'] <= d['worker_exit_ns'] <=
                d['worker_reaped_ns'] <= d['cleanup_ns']
            and d['worker_reaped_ns'] <= d['guard_terminal_ns'] <= d['terminal_ns']
            and d['guard_terminal_ns'] <= d['coordinator_final_ns'] <= d['total_ns'], 'Monotonic event ordering differs')
    require(d['worker_signal_ns'] is None if case == 'normal' else d['worker_signal_ns'] is not None
            and d['controller_exit_ns'] <= d['worker_signal_ns'] <= d['worker_exit_ns'] <= d['cleanup_ns'],
            'Owned signal cleanup deadline differs')
    return row


def run_lifecycle(source, backend, utility, linkage, case, nonce, expected_parent_pid,
                  expected_uid, expected_boot_id, pre_runtime_check=None):
    result = {**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'status': 'failed',
              'commands': [], 'link_attempts': 0, 'runtime_attempts': 0,
              'runtime_returned_complete_facts': False, 'complete_mapped_code_authenticated': False}
    try:
        require(type(case) is str and case in ('normal', 'controller_loss')
                and type(nonce) is str and re.fullmatch(r'[0-9a-f]{64}', nonce),
                'Closed case and fresh nonce required before compiler entry')
        if pre_runtime_check is not None:
            pre_runtime_check()
        result['compile_leg'] = build = utility.run_toolchain(source, backend)
        require(build['status'] == 'success', 'Fresh dedicated C compile leg failed')
        compiler = build['compiler']
        product, object_path = backend.root / 'lifecycle', backend.root / 'probe.o'
        result['link_attempts'] = 1
        command = backend.run('link', [compiler['path'], str(object_path), '-Wl,-Map,' +
                                       str(backend.root / 'link.map'), '-o', str(product)])
        result['commands'].append(command)
        require(command['status'] == 'success', 'Fixed owned C lifecycle link failed')
        body, map_row = backend.read_output('link.map', MAX_BYTES)
        links, total = {}, 0
        for path in linkage.parse_link_map(body, object_path):
            links[path] = row = backend.snapshot(os.path.realpath(path), utility.MAX_DRIVER)
            total += row['bytes']
            require(total <= utility.MAX_HEADERS_TOTAL, 'Link inventory total byte limit exceeded')
        body, product_row = backend.read_output('lifecycle', MAX_BYTES)
        require(product_row['identity'][2] & 0o111, 'Executable product mode required')
        result['product'] = {**product_row, **linkage.parse_elf_product(body)}
        require(all(result['product'][key] == build['object'][key]
                    for key in ('elf_class', 'data_encoding', 'machine')),
                'Object and product ELF descriptors differ')
        interpreter_path = result['product']['interpreter']
        interpreter = backend.snapshot(os.path.realpath(interpreter_path), utility.MAX_DRIVER)
        result['interpreter'] = interpreter
        result['link_inputs_after_link'] = links
        bound = {**build['output_bindings'], 'link.map': map_row, 'lifecycle': product_row,
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
        runtime = backend.run('runtime', [str(product), case, nonce])
        result['commands'].append(runtime)
        runtime_body, _ = backend.read_output('runtime.stdout', MAX_BYTES)
        # Handled negative C facts survive a nonzero child returncode.
        result['runtime_report'] = facts = parse_runtime(runtime_body, runtime, build['cpp_facts'],
                                                        expected_parent_pid, expected_uid, expected_boot_id,
                                                        case, nonce, product_row['identity'])
        result['runtime_returned_complete_facts'] = True
        bound.update({'runtime.stdout': runtime['stdout'], 'runtime.stderr': runtime['stderr']})
        recheck()
        result['output_bindings'] = bound
        require(runtime['status'] == 'success' and facts['status'] == 'success',
                'Fixed owned C lifecycle returned a terminal negative result')
        result[SUCCESS[0 if case == 'normal' else 1]] = True
        result['status'] = 'success'
    except Exception as error:
        result['error'] = error_fact(error)
    return result


def observe(request_path, expected_sha256):
    require(sys.platform == 'linux' and sys.flags.isolated == sys.flags.no_site == 1
            and sys.dont_write_bytecode and os.getuid() == os.geteuid(),
            'Fresh equal-UID Linux -B -I -S file entry required')
    helper, utility, linkage = load_utilities()
    source = helper.normalized_path(__file__)
    probe = source.with_name('frontier_v8_owned_c_lifecycle.c')
    uid, inputs = os.getuid(), []
    for path, limit, owner in ((source, helper.MAX_SOURCE_BYTES, None),
                              (probe, helper.MAX_SOURCE_BYTES, None),
                              (Path(helper.__file__), helper.MAX_SOURCE_BYTES, None),
                              (Path(utility.__file__), helper.MAX_SOURCE_BYTES, None),
                              (Path(linkage.__file__), helper.MAX_SOURCE_BYTES, None),
                              (helper.normalized_path(request_path), helper.MAX_REQUEST_BYTES, uid)):
        body, identity = helper.read_regular(str(path), limit, owner=owner)
        inputs.append((path, body, identity, limit, owner))
    require(inputs[2][1:3] == (helper._captured_bytes, helper._captured_identity)
            and inputs[3][1:3] == (utility._captured_bytes, utility._captured_identity)
            and inputs[4][1:3] == (linkage._captured_bytes, linkage._captured_identity),
            'Captured utility inputs changed')
    request = parse_request(inputs[5][1], expected_sha256, digest(inputs[0][1]), digest(inputs[1][1]), helper)
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
                             'identity_helper_sha256': HELPER_SHA, 'toolchain_sha256': TOOLCHAIN_SHA,
                             'linkage_sha256': LINKAGE_SHA, 'case': request['case']})
        os.fsync(parent)
        marker_body, marker_identity = helper.read_regular(str(marker), helper.MAX_REQUEST_BYTES, owner=uid)
        receipt = {**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'schema_version': 1, 'scope': SCOPE,
                   'status': 'failed', 'nonce': request['nonce'], 'case': request['case'], 'request_sha256': expected_sha256,
                   'attempt_directory': str(root), 'self_identity': own, 'host': request['host'],
                   'node_alias_authenticated': False, 'input_and_self_identity_postvalidation_passed': False,
                   'captured_utilities': {'identity_sha256': HELPER_SHA, 'toolchain_sha256': TOOLCHAIN_SHA,
                                          'linkage_sha256': LINKAGE_SHA,
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

            receipt['lifecycle'] = run_lifecycle(probe, utility.CompilerBackend(helper, root, root_fd),
                                               utility, linkage, request['case'], request['nonce'],
                                               own['pid'], uid, own['boot_id'], validate_inputs)
            validate_inputs()
            require(__file__ == str(source) and helper.__file__ == str(source.with_name(
                        'frontier_v8_containment_capability.py'))
                    and utility.__file__ == str(source.with_name('frontier_v8_c_toolchain.py'))
                    and linkage.__file__ == str(source.with_name('frontier_v8_owned_c_selfcheck.py'))
                    and sys.executable == lexical_executable
                    and os.path.realpath(sys.executable) == str(bootstrap)
                    and list(sys.version_info[:3]) == request['bootstrap']['version']
                    and os.uname().nodename == request['host']['hostname'], 'Entry/bootstrap/host drift')
            receipt['input_and_self_identity_postvalidation_passed'] = True
            if receipt['lifecycle']['status'] == 'success':
                receipt['status'] = 'owned_C_direct_worker_lifecycle_observed'
                receipt[SUCCESS[0 if request['case'] == 'normal' else 1]] = True
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
        raise ValueError('Execution unavailable; separately declared fixed owned C lifecycle fixture only')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-owned-c-lifecycle', action='store_true')
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-request-sha256', required=True)
    args = parser.parse_args(argv)
    require(args.observe_owned_c_lifecycle, 'Explicit separate fixed owned-C lifecycle observation required')
    receipt = observe(args.request, args.expected_request_sha256)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['status'] == 'owned_C_direct_worker_lifecycle_observed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
