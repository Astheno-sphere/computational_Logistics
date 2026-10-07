"""Fixed owned C exec/descendant CPU fixtures; production/model authority is unavailable."""
import argparse
import errno
import select
import signal
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType

SCOPE = 'frontier_v8_owned_C_fixed_exec_descendant_CPU_fixture'
HELPER_SHA = '1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412'
TOOLCHAIN_SHA = '2175f96e939993db69eb14348fa3115ae583416a1d38307f38f23bd378d003c0'
LINKAGE_SHA = '3374d4ed4ef1bafa38d8f4340ffcc042ee396d966228a682adf890182108b47c'
C_NAMES = ('frontier_v8_owned_c_exec_guardian.c', 'frontier_v8_owned_c_exec_leaf.c',
           'frontier_v8_owned_c_exec_protocol.h')
AUTHORITY = dict.fromkeys(('functional_containment_verified', 'containment_available',
    'execution_available', 'resource_authority', 'model_runtime_ABI_observed',
    'production_controller_guard_completed', 'GPU_or_foreign_restore'), False)
SUCCESS = ('fixed_exec_transition_observed', 'fixed_normal_descendant_reap_observed',
           'fixed_worker_loss_descendant_adoption_reap_observed')
FIELDS = {'schema_version', 'scope', 'nonce', 'observer_sha256', 'c_sources_sha256',
    'identity_helper_sha256', 'toolchain_sha256', 'linkage_sha256', 'case',
    'attempt_directory', 'host', 'bootstrap', 'authority'}
MAX_BYTES = 8 * 1024 * 1024
MAX_RUNTIME_BYTES = 256 * 1024
FORBIDDEN_OUTPUT_PREFIXES = (
    '/data/zefan/open-jev-v8-runtime-abi-', '/data/zefan/open-jev-v8-containment-presence-',
    '/data/zefan/open-jev-v8-pidfd-selfcheck-', '/data/zefan/open-jev-v8-linux-runtime-',
    '/data/zefan/open-jev-v8-c-toolchain-', '/data/zefan/open-jev-v8-owned-c-selfcheck-',
    '/data/zefan/open-jev-v8-owned-c-lifecycle-', '/data/zefan/open-jev-v8-owned-c-guardian-')


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
    name = 'frontier_v8_exec_descendant_identity_helper'
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
    name = 'frontier_v8_exec_descendant_build_utility'
    require(digest(utility_body) == TOOLCHAIN_SHA and name not in sys.modules,
            'Captured toolchain source/cache differs')
    utility = ModuleType(name)
    utility.__file__, utility.__package__ = str(utility_path), None
    exec(compile(utility_body, str(utility_path), 'exec', dont_inherit=True), utility.__dict__)
    utility._captured_bytes, utility._captured_identity = utility_body, utility_identity
    linkage_path = source.with_name('frontier_v8_owned_c_selfcheck.py')
    linkage_body, linkage_identity = helper.read_regular(str(linkage_path), helper.MAX_SOURCE_BYTES)
    name = 'frontier_v8_exec_descendant_linkage_utility'
    require(digest(linkage_body) == LINKAGE_SHA and name not in sys.modules,
            'Captured linkage source/cache differs')
    linkage = ModuleType(name)
    linkage.__file__, linkage.__package__ = str(linkage_path), None
    exec(compile(linkage_body, str(linkage_path), 'exec', dont_inherit=True), linkage.__dict__)
    linkage._captured_bytes, linkage._captured_identity = linkage_body, linkage_identity
    return helper, utility, linkage


def parse_request(body, expected_sha256, observer_sha256, c_sources_sha256, helper):
    require(type(expected_sha256) is str and re.fullmatch(r'[0-9a-f]{64}', expected_sha256)
            and digest(body) == expected_sha256, 'Exact request bytes required')
    row = json.loads(body, object_pairs_hook=helper._unique_object,
                     parse_constant=lambda value: require(False, 'Nonfinite JSON refused'))
    require(type(row) is dict and set(row) == FIELDS and type(row['schema_version']) is int
            and row['schema_version'] == 1 and row['scope'] == SCOPE, 'Exact closed exec fixture request required')
    require(type(row['nonce']) is str and re.fullmatch(r'[0-9a-f]{64}', row['nonce'])
            and row['observer_sha256'] == observer_sha256
            and type(row['c_sources_sha256']) is dict and set(row['c_sources_sha256']) == set(C_NAMES)
            and row['c_sources_sha256'] == c_sources_sha256
            and all(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value)
                    for value in row['c_sources_sha256'].values())
            and row['identity_helper_sha256'] == HELPER_SHA
            and row['toolchain_sha256'] == TOOLCHAIN_SHA and row['linkage_sha256'] == LINKAGE_SHA
            and type(row['case']) is str and row['case'] in ('normal', 'worker_loss'),
            'Exact fresh source closure, case and nonce required')
    require(type(row['authority']) is dict and set(row['authority']) == set(AUTHORITY)
            and all(value is False for value in row['authority'].values()), 'Broad authority must remain false')
    host, bootstrap = row['host'], row['bootstrap']
    require(type(host) is dict and set(host) == {'node_alias', 'hostname', 'boot_id', 'uid'}
            and host['node_alias'] in helper.NODES and type(host['hostname']) is str
            and 0 < len(host['hostname']) <= 255 and '\0' not in host['hostname']
            and type(host['uid']) is int and 0 <= host['uid'] <= (1 << 32) - 1
            and type(host['boot_id']) is str and re.fullmatch(
                r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', host['boot_id']),
            'Exact allowed host identity required')
    require(type(bootstrap) is dict and set(bootstrap) == {'executable', 'sha256', 'version'}
            and type(bootstrap['sha256']) is str and re.fullmatch(r'[0-9a-f]{64}', bootstrap['sha256'])
            and type(bootstrap['version']) is list and len(bootstrap['version']) == 3
            and all(type(x) is int and 0 <= x <= 10000 for x in bootstrap['version']),
            'Exact bootstrap declaration required')
    helper.normalized_path(bootstrap['executable'])
    helper.normalized_path(row['attempt_directory'])
    return row


def parse_exec_cpp_markers(body):
    require(type(body) is bytes and len(body) <= MAX_BYTES, 'Bounded CPP bytes required')
    text, facts = body.decode('ascii'), {}
    token = r'(?:0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]*|<<|>>|[()+\-*/%~&|^]'
    for marker, key in (
            ('header_pidfd_send_signal', 'SYS_pidfd_send_signal_expression'),
            ('header_pr_set_child_subreaper', 'PR_SET_CHILD_SUBREAPER_expression'),
            ('header_pr_get_child_subreaper', 'PR_GET_CHILD_SUBREAPER_expression'),
            *((('header_' + symbol.lower()), symbol + '_expression') for symbol in
              ('F_GETFD', 'F_SETFD', 'F_DUPFD_CLOEXEC', 'FD_CLOEXEC', 'O_CLOEXEC',
               'O_NOFOLLOW', 'O_NONBLOCK', 'F_GETFL', 'F_SETFL', 'EBADF', 'SIGKILL',
               'SIGPIPE', 'POLLIN', 'POLLNVAL', 'PIPE_BUF'))):
        name = 'frontier_v8_' + marker
        require(len(re.findall(r'\b' + name + r'\b', text)) == 1, 'One captured CPP marker required')
        match = re.search(r'\bconst\s+long\s+' + name + r'\s*=\s*([^;]+);', text)
        require(match is not None, 'Exact long marker required')
        value = match.group(1).strip()
        require(0 < len(value) <= 1024 and re.fullmatch(r'(?:\s*(?:' + token + r'))+\s*', value),
                'Opaque expanded C expression required')
        facts[key] = value
    return facts


def parse_runtime(body, command, cpp_facts, expected_parent_pid, expected_uid, expected_boot_id,
                  case, nonce, guardian_product_identity, leaf_product_identity, fault='none'):
    """Validate typed returned facts and recompute only the two fixed CPU outcomes."""
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'Duplicate C JSON key refused')
            value[key] = item
        return value

    def fields(value, names):
        require(type(value) is dict and set(value) == set(names.split()), 'Exact C fact fields required')

    def number(value, low=0, high=(1 << 63) - 1, optional=False):
        require((optional and value is None) or (type(value) is int and low <= value <= high),
                'Bounded typed C integer required')

    def boolean(value):
        require(type(value) is bool, 'Typed C boolean required')

    def name(value, choices=None, optional=False):
        require((optional and value is None) or (type(value) is str and
                re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', value) and
                (choices is None or value in choices)), 'Closed C fact label required')

    def operation(value):
        fields(value, 'attempted result errno value observed_at_ns')
        boolean(value['attempted'])
        number(value['result'], -1, (1 << 31) - 1, optional=True)
        number(value['errno'], high=(1 << 31) - 1, optional=True)
        number(value['value'], -1, (1 << 31) - 1, optional=True)
        number(value['observed_at_ns'], optional=True)
        require(value['attempted'] or all(value[k] is None for k in
                ('result', 'errno', 'value', 'observed_at_ns')), 'Unattempted operation has invented results')
        require(not value['attempted'] or all(value[k] is not None for k in
                ('result', 'errno')), 'Attempted operation lacks an actual result/errno')
        require(not value['attempted'] or value['observed_at_ns'] is not None
                or (row['status'] != 'success' and error['operation'] == 'clock_gettime'),
                'Missing syscall observation time requires an explicit failed clock branch')

    def product(value):
        fields(value, 'dev ino size mtime_ns ctime_ns')
        for key, item in value.items():
            number(item, high=(1 << (63 if key.endswith('_ns') else 64)) - 1)

    def identity(value):
        if value is None:
            return
        fields(value, 'pid ppid start_ticks boot_id uid euid product_identity')
        for key in ('pid', 'ppid'):
            number(value[key], 1, (1 << 31) - 1)
        number(value['start_ticks'], 1, (1 << 64) - 1)
        for key in ('uid', 'euid'):
            number(value[key], high=(1 << 32) - 1)
        require(type(value['boot_id']) is str and re.fullmatch(
            r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value['boot_id']), 'Typed boot identity required')
        product(value['product_identity'])

    def poll(value):
        fields(value, 'owner target handle fd stage attempts requested_events result revents errno observed_at_ns')
        name(value['owner'], roles)
        name(value['target'], roles)
        name(value['handle'], pairs)
        name(value['stage'], ('initial_live', 'postexec_live', 'armed_live', 'presignal_live', 'terminal'))
        require((value['owner'], value['target']) == pairs[value['handle']], 'Poll handle ownership differs')
        number(value['fd'], -1, (1 << 31) - 1)
        number(value['attempts'], high=(1 << 31) - 1)
        number(value['requested_events'], high=(1 << 15) - 1)
        number(value['result'], -1, 1, optional=True)
        number(value['revents'], high=(1 << 15) - 1, optional=True)
        number(value['errno'], high=(1 << 31) - 1, optional=True)
        number(value['observed_at_ns'], optional=True)
        require(value['attempts'] or all(value[k] is None for k in
                ('result', 'revents', 'errno', 'observed_at_ns')), 'Unattempted poll has invented results')
        require(not value['attempts'] or (all(value[k] is not None for k in ('result', 'revents', 'errno'))
                and (value['observed_at_ns'] is not None or
                     (row['status'] != 'success' and error['operation'] == 'clock_gettime'))),
                'Attempted poll requires known actual results or an explicit failed clock')

    require(type(body) is bytes and 0 < len(body) <= MAX_RUNTIME_BYTES, 'Bounded complete C JSON required')
    row = json.loads(body, object_pairs_hook=unique,
                     parse_constant=lambda value: require(False, 'Nonfinite C JSON refused'))
    fields(row, 'schema_version scope case fault nonce status error headers products subreaper '
                'child_subreaper_get local_sigpipe identities_initial identity_rechecks exec_protocol '
                'adoptions pidfds polls waits signals fd_ledger fd_flags packets command_forwards '
                'deadlines times_ns controls negative_state')
    require(type(row['schema_version']) is int and row['schema_version'] == 1 and row['scope'] == SCOPE
            and type(case) is str and case in ('normal', 'worker_loss') and row['case'] == case
            and type(fault) is str and fault in ('none', 'exec_fd_closed', 'witness_cloexec_cleared')
            and row['fault'] == fault and type(nonce) is str and re.fullmatch(r'[0-9a-f]{64}', nonce)
            and row['nonce'] == nonce, 'Exact fixed exec case/fault/nonce required')
    name(row['status'], ('success', 'failed', 'unknown'))
    roles = ('guardian', 'preexec_worker', 'worker', 'descendant')
    pairs = {'G_E': ('guardian', 'worker'), 'G_D': ('guardian', 'descendant'),
             'E_D': ('worker', 'descendant')}
    error = row['error']
    fields(error, 'stage role operation errno result observed_at_ns')
    name(error['stage'])
    name(error['role'], roles, optional=True)
    name(error['operation'], optional=True)
    number(error['errno'], high=(1 << 31) - 1, optional=True)
    number(error['result'], -1, (1 << 31) - 1, optional=True)
    number(error['observed_at_ns'], optional=True)
    require(error['stage'] != 'none' or all(error[k] is None for k in error if k != 'stage'),
            'No-error record contains results')
    h = row['headers']
    fields(h, 'pidfd_open pidfd_send_signal pr_set_child_subreaper pr_get_child_subreaper SIGKILL '
              'SIGPIPE POLLIN POLLNVAL F_GETFD F_SETFD F_DUPFD_CLOEXEC FD_CLOEXEC O_CLOEXEC '
              'O_NOFOLLOW O_NONBLOCK F_GETFL F_SETFL EBADF PIPE_BUF target_int_bytes '
              'target_long_bytes target_pointer_bytes target_char_bits target_byte_order pid_t_bytes '
              'uid_t_bytes pid_t_signed uid_t_signed uint64_bytes int64_bytes pid_representation '
              'uid_representation uint64_representation int64_representation pid_max uid_max '
              'uint64_max int64_min int64_max')
    for key in ('pidfd_open', 'pidfd_send_signal', 'pr_set_child_subreaper',
                'pr_get_child_subreaper', 'F_GETFL', 'F_GETFD', 'F_SETFD', 'F_SETFL'):
        number(h[key], high=(1 << 63) - 1)
    for key in ('SIGKILL', 'SIGPIPE', 'POLLIN', 'POLLNVAL', 'F_DUPFD_CLOEXEC', 'FD_CLOEXEC',
                'O_CLOEXEC', 'O_NOFOLLOW', 'O_NONBLOCK', 'EBADF', 'PIPE_BUF', 'target_int_bytes',
                'target_long_bytes', 'target_pointer_bytes', 'target_char_bits', 'target_byte_order',
                'pid_t_bytes', 'uid_t_bytes', 'uint64_bytes', 'int64_bytes'):
        number(h[key], 1, (1 << 31) - 1)
    require(all(type(cpp_facts[k]) is int and h[k] == cpp_facts[k] for k in
                ('target_int_bytes', 'target_long_bytes', 'target_pointer_bytes',
                 'target_char_bits', 'target_byte_order'))
            and all(type(cpp_facts[k]) is str and cpp_facts[k] for k in
                ('SYS_pidfd_open_expression', 'SYS_pidfd_send_signal_expression',
                 'PR_SET_CHILD_SUBREAPER_expression', 'PR_GET_CHILD_SUBREAPER_expression',
                 *(symbol + '_expression' for symbol in ('F_GETFD', 'F_SETFD', 'F_DUPFD_CLOEXEC',
                 'FD_CLOEXEC', 'O_CLOEXEC', 'O_NOFOLLOW', 'O_NONBLOCK', 'F_GETFL', 'F_SETFL',
                 'EBADF', 'SIGKILL', 'SIGPIPE', 'POLLIN', 'POLLNVAL', 'PIPE_BUF'))))
            and h['target_int_bytes'] == h['pid_t_bytes'] == h['uid_t_bytes'] == 4
            and h['target_char_bits'] == h['uint64_bytes'] == h['int64_bytes'] == 8
            and h['target_long_bytes'] in (4, 8) and h['target_pointer_bytes'] in (4, 8)
            and h['pid_t_signed'] is True and h['uid_t_signed'] is False
            and h['pid_representation'] == 'signed32' and h['uid_representation'] == 'unsigned32'
            and h['uint64_representation'] == 'unsigned64' and h['int64_representation'] == 'signed64'
            and type(h['pid_max']) is int and h['pid_max'] == (1 << 31) - 1
            and type(h['uid_max']) is int and h['uid_max'] == (1 << 32) - 1
            and type(h['uint64_max']) is int and h['uint64_max'] == (1 << 64) - 1
            and type(h['int64_min']) is int and h['int64_min'] == -(1 << 63)
            and type(h['int64_max']) is int and h['int64_max'] == (1 << 63) - 1
            and h['SIGKILL'] == signal.SIGKILL and h['SIGPIPE'] == signal.SIGPIPE
            and h['POLLIN'] == select.POLLIN and h['POLLNVAL'] == select.POLLNVAL
            and h['EBADF'] == errno.EBADF and h['PIPE_BUF'] >= 512
            and h['pr_set_child_subreaper'] != h['pr_get_child_subreaper']
            and all(h[k] <= (1 << (h['target_long_bytes'] * 8 - 1)) - 1 for k in
                    ('pidfd_open', 'pidfd_send_signal')), 'Fresh scalar/header baseline differs')
    fields(row['products'], 'guardian leaf')
    for value in row['products'].values():
        product(value)
    expected = {key: dict(zip(('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'),
                             (value[0], value[1], *value[4:7]))) for key, value in
                (('guardian', guardian_product_identity), ('leaf', leaf_product_identity))}
    require(row['products'] == expected and expected['guardian'] != expected['leaf'],
            'Two distinct freshly bound products required')
    sr = row['subreaper']
    fields(sr, 'initial_get set_one get_one reset_zero final_get')
    fields(row['child_subreaper_get'], 'preexec_worker worker descendant')
    for value in (*sr.values(), *row['child_subreaper_get'].values()):
        operation(value)
    fields(row['local_sigpipe'], 'guardian worker descendant')
    for value in row['local_sigpipe'].values():
        fields(value, 'query set_ignore')
        for item in value.values():
            operation(item)
    ids = row['identities_initial']
    fields(ids, 'guardian preexec_worker worker descendant')
    checks = row['identity_rechecks']
    fields(checks, 'preexec postexec armed_worker armed_descendant presignal_worker '
                   'presignal_descendant guardian_before_descendant_signal')
    for value in (*ids.values(), *checks.values()):
        identity(value)
    require(type(command) is dict and command.get('timed_out') is False
            and command.get('kill_attempted') is False and command.get('reap_completed') is True
            and type(command.get('returncode')) is int and command.get('status') in ('success', 'failed'),
            'Normally reaped outer direct child without timeout/kill required')
    number(command.get('direct_child_pid'), 1, (1 << 31) - 1)
    argv = command.get('argv')
    require(type(argv) is list and len(argv) == 5 and argv[1:3] == [case, nonce] and argv[4] == fault,
            'Exact fixed guardian runtime argv required')
    for value, basename in ((argv[0], 'guardian'), (argv[3], 'leaf')):
        require(type(value) is str and '\0' not in value and Path(value).is_absolute()
                and str(Path(value)) == value and '..' not in Path(value).parts
                and Path(value).name == basename and not any(Path(value).is_relative_to(Path(p))
                    for p in ('/proc', '/sys', '/dev')), 'Bounded new product runtime path required')
    for role, value in ids.items():
        if value is not None:
            require(value['uid'] == value['euid'] == expected_uid and value['boot_id'] == expected_boot_id
                    and value['product_identity'] == expected[
                        'guardian' if role in ('guardian', 'preexec_worker') else 'leaf'],
                    'Present role identity differs from declared host/product')
    if ids['guardian'] is not None:
        require(ids['guardian']['pid'] == command['direct_child_pid']
                and ids['guardian']['ppid'] == expected_parent_pid, 'Guardian direct-child identity differs')
    for role in ('preexec_worker', 'worker'):
        if ids[role] is not None:
            require(ids['guardian'] is not None and ids[role]['ppid'] == ids['guardian']['pid']
                    and ids[role]['pid'] != ids['guardian']['pid'], 'Fixed worker parent differs')
    if ids['preexec_worker'] is not None and ids['worker'] is not None:
        require(all(ids['preexec_worker'][k] == ids['worker'][k] for k in
                ('pid', 'ppid', 'start_ticks', 'boot_id', 'uid', 'euid')),
                'Exec must preserve the original process identity')
    if ids['descendant'] is not None:
        require(ids['worker'] is not None and ids['descendant']['ppid'] == ids['worker']['pid']
                and ids['descendant']['pid'] not in (ids['worker']['pid'], ids['guardian']['pid']),
                'Fixed descendant initial parent differs')
    ex = row['exec_protocol']
    fields(ex, 'attempted entered_at_ns returned result errno error_pipe_eof_at_ns '
               'startup_closed startup_private original_stdio')
    for key in ('attempted', 'returned'):
        boolean(ex[key])
    for key in ('entered_at_ns', 'error_pipe_eof_at_ns'):
        number(ex[key], optional=True)
    number(ex['result'], -1, (1 << 31) - 1, optional=True)
    number(ex['errno'], high=(1 << 31) - 1, optional=True)
    require(ex['attempted'] or all(ex[k] is None for k in ('entered_at_ns', 'result', 'errno')),
            'Unattempted exec has invented results')
    require(ex['returned'] or ex['result'] is ex['errno'] is None, 'Unreturned exec has invented return')
    fields(ex['startup_closed'], 'leaf_exec leaf_witness exec_error_write')
    fields(ex['startup_private'], 'command_read report_write')
    for value in (*ex['startup_closed'].values(), *ex['startup_private'].values()):
        fields(value, 'fd fact')
        number(value['fd'], -1, (1 << 31) - 1)
        operation(value['fact'])
    fields(ex['original_stdio'], 'worker descendant')
    for values in ex['original_stdio'].values():
        require(type(values) is list and len(values) == 3, 'Three original stdio slots required')
        for index, value in enumerate(values):
            fields(value, 'fd fact')
            require(type(value['fd']) is int and value['fd'] == index, 'Original stdio index differs')
            operation(value['fact'])
    fds = row['pidfds']
    fields(fds, 'G_E G_D E_D')
    for tag, value in fds.items():
        fields(value, 'owner target fd open identity_before identity_after fdinfo_pid fdinfo_matches '
                      'cloexec initial_live close F_GETFD_after_close owner_death_teardown')
        require((value['owner'], value['target']) == pairs[tag], 'Pidfd ownership differs')
        number(value['fd'], -1, (1 << 31) - 1)
        for key in ('open', 'cloexec', 'close', 'F_GETFD_after_close'):
            operation(value[key])
        for key in ('identity_before', 'identity_after'):
            identity(value[key])
        number(value['fdinfo_pid'], -1, (1 << 31) - 1, optional=True)
        boolean(value['fdinfo_matches'])
        boolean(value['owner_death_teardown'])
        poll(value['initial_live'])
    require(type(row['polls']) is list and len(row['polls']) <= 64, 'Bounded original-handle polls required')
    for value in row['polls']:
        poll(value)
    waits = row['waits']
    fields(waits, 'G_E E_D G_D')
    for tag, value in waits.items():
        fields(value, 'owner target pid attempts result raw_status errno observed_at_ns')
        require((value['owner'], value['target']) == pairs[tag], 'Fixed wait ownership differs')
        number(value['pid'], -1, (1 << 31) - 1)
        number(value['attempts'], high=(1 << 31) - 1)
        number(value['result'], -1, (1 << 31) - 1, optional=True)
        number(value['raw_status'], high=65535, optional=True)
        number(value['errno'], high=(1 << 31) - 1, optional=True)
        number(value['observed_at_ns'], optional=True)
        require(value['attempts'] or all(value[k] is None for k in
                ('result', 'raw_status', 'errno', 'observed_at_ns')), 'Unattempted wait has results')
        require(not value['attempts'] or (value['pid'] > 0 and value['result'] is not None
                and value['errno'] is not None and (value['observed_at_ns'] is not None or
                    (row['status'] != 'success' and error['operation'] == 'clock_gettime'))),
                'Attempted wait requires actual fixed target/result or an explicit failed clock')
        require(value['raw_status'] is None or value['result'] == value['pid'] > 0,
                'Only an actually reaped fixed child has a terminal raw wait status')
    fields(row['signals'], 'G_E G_D')
    for tag, value in row['signals'].items():
        fields(value, 'owner target budget consumed attempts fd signal flags result errno '
                      'observed_at_ns presignal_identity')
        require((value['owner'], value['target']) == pairs[tag], 'Original signal ownership differs')
        boolean(value['consumed'])
        number(value['budget'], high=1)
        number(value['attempts'], high=1)
        number(value['fd'], -1, (1 << 31) - 1)
        number(value['signal'], high=(1 << 31) - 1)
        number(value['flags'], high=(1 << 32) - 1)
        number(value['result'], -1, 0, optional=True)
        number(value['errno'], high=(1 << 31) - 1, optional=True)
        number(value['observed_at_ns'], optional=True)
        identity(value['presignal_identity'])
        require(value['budget'] == int(case == 'worker_loss') and value['attempts'] <= value['budget']
                and value['consumed'] is bool(value['attempts'])
                and (value['attempts'] or all(value[k] is None for k in
                     ('result', 'errno', 'observed_at_ns', 'presignal_identity'))),
                'Combined original signal budget or unattempted results differ')
        if value['attempts']:
            require(value['fd'] == fds[tag]['fd'] >= 0 and value['signal'] == h['SIGKILL']
                    and value['flags'] == 0 and value['observed_at_ns'] is not None
                    and value['errno'] is not None and value['presignal_identity'] is not None,
                    'Planned signal must use the original bound handle')
    ledger = row['fd_ledger']
    require(type(ledger) is list and len(ledger) <= 128, 'Bounded FD provenance ledger required')
    labels = ('guardian_product', 'leaf_exec', 'leaf_witness', 'command_read', 'command_write',
              'report_read', 'report_write', 'exec_error_read', 'exec_error_write', 'G_E',
              'child_command_read', 'child_command_write', 'child_report_read', 'child_report_write',
              'E_D', 'G_D', 'original_stdin', 'original_stdout', 'original_stderr')
    epochs = ('preexec', 'exec_entry', 'child_generation', 'original_stdio')
    seen = set()
    for value in ledger:
        fields(value, 'owner label epoch fd evidence close F_GETFD_after_close')
        name(value['owner'], roles)
        name(value['label'], labels)
        name(value['epoch'], epochs)
        name(value['evidence'], ('explicit_once_close', 'exec_entry_closed', 'parent_report_EOF',
                               'owner_death', 'original_absent', 'unreturned_loss_close'))
        number(value['fd'], -1, (1 << 31) - 1)
        for key in ('close', 'F_GETFD_after_close'):
            operation(value[key])
        tag = (value['owner'], value['label'], value['epoch'])
        require(tag not in seen, 'Duplicate FD acquisition provenance refused')
        seen.add(tag)
        if value['evidence'] != 'explicit_once_close':
            require(not value['close']['attempted'], 'Nonexplicit closure cannot invent close results')
        if value['evidence'] in ('original_absent', 'owner_death', 'parent_report_EOF', 'unreturned_loss_close'):
            require(not value['F_GETFD_after_close']['attempted'], 'Unobserved closure cannot invent EBADF')
    require(type(row['fd_flags']) is list and len(row['fd_flags']) <= 32, 'Bounded private descriptor flags required')
    flag_tags = {}
    for value in row['fd_flags']:
        fields(value, 'owner label epoch fd F_GETFD_before F_SETFD F_GETFD_after F_GETFL')
        name(value['owner'], roles)
        name(value['label'], labels)
        name(value['epoch'], epochs)
        number(value['fd'], high=(1 << 31) - 1)
        tag = (value['owner'], value['label'], value['epoch'])
        if tag in flag_tags:
            previous = flag_tags[tag]
            require(fault == 'witness_cloexec_cleared' and row['status'] != 'success'
                    and tag == ('preexec_worker', 'leaf_witness', 'preexec')
                    and len(previous) == 1 and previous[0]['fd'] == value['fd'],
                    'Duplicate FD flag acquisition provenance refused')
            previous.append(value)
        else:
            flag_tags[tag] = [value]
        for key in ('F_GETFD_before', 'F_SETFD', 'F_GETFD_after', 'F_GETFL'):
            operation(value[key])
    packets = row['packets']
    require(type(packets) is list and len(packets) <= 128, 'Bounded private packets required')
    for value in packets:
        fields(value, 'source transport edge direction kind sequence aux sent_at_ns observed_at_ns '
                      'shared_t0_ns bytes PIPE_BUF_bound forwarded_original')
        for key in ('source', 'transport'):
            name(value[key], roles)
        name(value['edge'], ('G_E', 'E_D', 'exec_error'))
        name(value['direction'], ('command', 'report'))
        name(value['kind'])
        number(value['sequence'], 1, (1 << 31) - 1)
        number(value['aux'], -1, (1 << 31) - 1)
        for key in ('sent_at_ns', 'observed_at_ns', 'shared_t0_ns'):
            number(value[key])
        number(value['bytes'], 1, 512)
        number(value['PIPE_BUF_bound'], 512, (1 << 31) - 1)
        boolean(value['forwarded_original'])
    require(type(row['command_forwards']) is list and len(row['command_forwards']) <= 8,
            'Bounded command forwarding gates required')
    for value in row['command_forwards']:
        fields(value, 'owner kind original_sequence observed_at_ns')
        require(value['owner'] == 'worker', 'Only E forwards to D')
        name(value['kind'], ('ARM', 'FINISH'))
        number(value['original_sequence'], 1, (1 << 32) - 1)
        number(value['observed_at_ns'])
    require(type(row['adoptions']) is list and len(row['adoptions']) <= 1, 'One fixed descendant adoption at most')
    for value in row['adoptions']:
        fields(value, 'target old_parent new_parent identity guardian_identity observed_at_ns')
        require(value['target'] == 'descendant', 'Only D adoption is in scope')
        for key in ('old_parent', 'new_parent'):
            number(value[key], 1, (1 << 31) - 1)
        identity(value['identity'])
        identity(value['guardian_identity'])
        number(value['observed_at_ns'])
    deadlines, times = row['deadlines'], row['times_ns']
    fields(deadlines, 't0_ns work_ns cleanup_ns terminal_ns Gtotal_ns child_expiry_ns')
    for value in deadlines.values():
        number(value)
    t0 = deadlines['t0_ns']
    require(all(deadlines[key] == t0 + offset * 1000000000 for key, offset in
                (('work_ns', 5), ('cleanup_ns', 8), ('terminal_ns', 10),
                 ('Gtotal_ns', 12), ('child_expiry_ns', 14))), 'Exact shared absolute budgets required')
    fields(times, 'initial preexec_ready exec_sent exec_entered postexec_ready postexec_validated '
                  'create_D_sent D_ready all_bound arm_sent all_arm_ack primary finish_sent E_signal '
                  'E_terminal E_reaped D_adopted D_signal D_terminal D_reaped FD_complete reset final')
    for value in times.values():
        number(value, optional=True)
        require(value is None or t0 <= value < deadlines['Gtotal_ns'], 'Observed G time outside finite budget')
    for value in packets:
        require(value['shared_t0_ns'] == t0 and t0 <= value['sent_at_ns'] <= value['observed_at_ns']
                < deadlines['Gtotal_ns'] and value['bytes'] <= value['PIPE_BUF_bound'],
                'Partial/oversized/reversed packet or shared clock differs')
    sequences, clocks = {}, {}
    kinds = ('PRE_EXEC_READY', 'EXEC', 'EXEC_ENTER', 'POST_EXEC_READY', 'CREATE_D',
             'D_CREATED', 'D_READY', 'HANDLE_FACT', 'ARM', 'ARM_ACK', 'ALL_ARM_ACK',
             'FINISH', 'D_FINISH_ACK', 'E_FINISH_ACK', 'FD_CLOSE_FACT', 'FD_FLAGS_FACT',
             'SUBREAPER_GET', 'SIGPIPE_FACT', 'STARTUP_FD_FACT', 'WAIT_FACT', 'POLL_FACT',
             'COMMAND_FORWARDED', 'ERROR', 'EXEC_ERROR', 'PRODUCT_CHECK')
    for value in packets:
        key = (value['source'], value['edge'])
        require(value['kind'] in kinds and value['sequence'] == sequences.get(key, 0) + 1
                and value['sent_at_ns'] >= clocks.get(key, t0),
                'Missing/repeated packet sequence or reverse source clock')
        sequences[key], clocks[key] = value['sequence'], value['sent_at_ns']
        require((value['direction'] == 'command') is (value['source'] == 'guardian')
                and value['forwarded_original'] is (value['source'] == 'descendant')
                and value['transport'] == ('worker' if value['source'] == 'descendant'
                                           else value['source']), 'Private packet provenance differs')
        require(value['edge'] in (('E_D',) if value['source'] == 'descendant' else
                                  ('G_E', 'exec_error') if value['source'] == 'preexec_worker' else ('G_E',))
                and (value['edge'] != 'exec_error' or value['kind'] == 'EXEC_ERROR')
                and (value['source'] != 'guardian' or value['kind'] in ('EXEC', 'CREATE_D', 'ARM', 'FINISH')),
                'Closed G-visible packet source/edge/kind required')
    require(not packets or len({value['bytes'] for value in packets}) == 1,
            'Every observed private frame must have the same captured C size')
    controls = row['controls']
    fields(controls, ' '.join((*AUTHORITY, 'fixed_exec_transition_verified', 'normal_reap_verified',
                              'worker_loss_adoption_verified')))
    require(all(controls[k] is False for k in AUTHORITY), 'Broad authority must remain false')
    for value in controls.values():
        boolean(value)
    negative = row['negative_state']
    fields(negative, 'created bound adopted terminal reaped unknown descendant_creation_authorized '
                     'descendant_creation_observed negative_cleanup_signal_attempts')
    for key in ('created', 'bound', 'adopted', 'terminal', 'reaped', 'unknown'):
        values = negative[key]
        require(type(values) is list and all(type(v) is str and v in ('worker', 'descendant') for v in values)
                and len(values) == len(set(values)) <= 2,
                'Fixed observed negative-state sets required')
    for key in ('descendant_creation_authorized', 'descendant_creation_observed'):
        boolean(negative[key])
    require(type(negative['negative_cleanup_signal_attempts']) is int
            and negative['negative_cleanup_signal_attempts'] == 0, 'Negative signals are forbidden')
    require(all(set(negative[key]) <= set(negative['created']) for key in
                ('bound', 'adopted', 'terminal', 'reaped'))
            and set(negative['unknown']) <= set(negative['created']) |
                ({'descendant'} if negative['descendant_creation_authorized'] else set())
            and set(negative['reaped']) <= set(negative['terminal'])
            and (not negative['descendant_creation_observed'] or
                 (negative['descendant_creation_authorized'] and 'descendant' in negative['created'])),
            'Observed fixed process sets are inconsistent')
    if error['stage'] != 'none' and error['observed_at_ns'] is not None:
        received_errors = [value['observed_at_ns'] for value in packets
                           if value['kind'] in ('ERROR', 'EXEC_ERROR') and value['source'] == error['role']]
        cutoff = error['observed_at_ns'] if error['role'] == 'guardian' else (
            min(received_errors) if received_errors else None)
        require(cutoff is not None and all(not value['attempts'] or value['observed_at_ns'] <= cutoff
                    for value in row['signals'].values())
                and all(value['kind'] not in ('EXEC', 'CREATE_D', 'ARM', 'FINISH')
                        or value['sent_at_ns'] <= cutoff for value in packets),
                'First guardian-observed failure must disable later planned signal/command')
    failed_signals = [value for value in row['signals'].values()
                      if value['attempts'] and (value['result'] != 0 or value['errno'] != 0)]
    for failed in failed_signals:
        require(error['stage'] != 'none' and all(value is failed or not value['attempts']
                or value['observed_at_ns'] <= failed['observed_at_ns'] for value in row['signals'].values()),
                'Uncertain signal permanently disables later signal attempts')
    def ok(value, result=0, err=0, expected_value=None):
        return (value['attempted'] and value['result'] == result and value['errno'] == err
                and (expected_value is None or value['value'] == expected_value)
                and value['observed_at_ns'] is not None
                and t0 <= value['observed_at_ns'] < deadlines['terminal_ns'])

    def closed(value):
        return (ok(value['close']) and ok(value['F_GETFD_after_close'], -1, h['EBADF'])
                and value['close']['observed_at_ns'] <= value['F_GETFD_after_close']['observed_at_ns'])

    def same(value, baseline, adopted=False):
        return (value is not None and baseline is not None and all(value[k] == baseline[k]
                for k in baseline if not (adopted and k == 'ppid'))
                and (not adopted or value['ppid'] == ids['guardian']['pid']))

    def terminal_wait(tag, raw):
        value = waits[tag]
        baseline = ids[pairs[tag][1]]
        return (baseline is not None and value['attempts'] > 0
                and value['pid'] == value['result'] == baseline['pid']
                and value['raw_status'] == raw and value['errno'] == 0
                and value['observed_at_ns'] is not None
                and t0 <= value['observed_at_ns'] < deadlines['terminal_ns'])

    partial_reset = row['status'] != 'success' and sr['reset_zero']['attempted']
    if row['status'] == 'success' or partial_reset:
        require(fault == 'none' and all(value is not None for value in ids.values())
                and (partial_reset or (error['stage'] == 'none' and command['status'] == 'success'
                                       and command['returncode'] == 0)),
                'Success requires the complete normal outer process and fixed tree')
        required = ('initial', 'preexec_ready', 'exec_sent', 'exec_entered', 'postexec_ready',
                    'postexec_validated', 'create_D_sent', 'D_ready', 'all_bound', 'arm_sent',
                    'all_arm_ack', 'primary', 'E_terminal', 'E_reaped', 'D_terminal', 'D_reaped',
                    'FD_complete', 'reset', 'final')
        require(all(times[k] is not None for k in required if not
                    (partial_reset and k in ('reset', 'final'))), 'Success causal boundaries are incomplete')
        ready = required[:12]
        require(all(times[a] <= times[b] for a, b in zip(ready, ready[1:]))
                and times['primary'] < deadlines['work_ns']
                and max(times['E_reaped'], times['D_reaped']) <= times['FD_complete'] < deadlines['terminal_ns']
                and (partial_reset or times['FD_complete'] <= times['reset']
                     <= times['final'] < deadlines['terminal_ns']),
                'Exec/readiness/action/terminal chronology differs')
        require(ok(sr['initial_get'], expected_value=0) and ok(sr['set_one'], expected_value=1)
                and ok(sr['get_one'], expected_value=1)
                and sr['initial_get']['observed_at_ns'] <= sr['set_one']['observed_at_ns']
                <= sr['get_one']['observed_at_ns'] <= times['preexec_ready']
                and all(ok(value, expected_value=0) for value in row['child_subreaper_get'].values()),
                'Actual subreaper get/set/child facts are incomplete')
        if partial_reset:
            require(error['role'] == 'guardian' and error['stage'] == 'terminal'
                    and error['operation'] in ('prctl', 'clock_gettime')
                    and error['observed_at_ns'] is not None and sr['reset_zero']['value'] == 0
                    and times['FD_complete'] <= error['observed_at_ns'] < deadlines['terminal_ns']
                    and (sr['reset_zero']['observed_at_ns'] is None and error['operation'] == 'clock_gettime'
                         or sr['reset_zero']['observed_at_ns'] is not None and times['FD_complete']
                         <= sr['reset_zero']['observed_at_ns'] <= error['observed_at_ns'])
                    and (not sr['final_get']['attempted'] or
                         (ok(sr['reset_zero'], expected_value=0) and sr['reset_zero']['observed_at_ns']
                          <= error['observed_at_ns'] and (sr['final_get']['observed_at_ns'] is None
                          and error['operation'] == 'clock_gettime' or sr['final_get']['observed_at_ns'] is not None
                          and sr['reset_zero']['observed_at_ns'] <= sr['final_get']['observed_at_ns']
                          <= error['observed_at_ns']))),
                    'Partial reset requires complete pre-reset facts and a later actual reset/clock error')
            if error['operation'] == 'prctl':
                require(any(value['attempted'] and value['result'] == -1 and value['errno'] == error['errno']
                            and value['result'] == error['result'] for value in (sr['reset_zero'], sr['final_get'])),
                        'Partial prctl reset failure must retain the actual failing call result')
        else:
            require(ok(sr['reset_zero'], expected_value=0) and ok(sr['final_get'], expected_value=0)
                    and times['FD_complete'] <= sr['reset_zero']['observed_at_ns']
                    <= sr['final_get']['observed_at_ns'] <= times['final'],
                    'Actual successful reset and post-reset time required')
        for value in row['local_sigpipe'].values():
            require(ok(value['query']) and value['query']['value'] in (0, 1)
                    and ok(value['set_ignore'], expected_value=1), 'Actual local SIGPIPE disposition required')
        require(checks['preexec'] == ids['preexec_worker'] and checks['postexec'] == ids['worker']
                and checks['armed_worker'] == ids['worker'] and checks['armed_descendant'] == ids['descendant']
                and ex['attempted'] and not ex['returned'] and ex['result'] is ex['errno'] is None
                and ex['entered_at_ns'] is not None and times['exec_sent'] <= ex['entered_at_ns']
                <= times['postexec_ready'] and ex['error_pipe_eof_at_ns'] is not None
                and ex['entered_at_ns'] <= ex['error_pipe_eof_at_ns'] <= times['postexec_validated'],
                'Descriptor exec requires EOF and independent same-process product transition')
        startup_fds = [value['fd'] for value in (*ex['startup_closed'].values(),
                                                 *ex['startup_private'].values())]
        require(len(set(startup_fds)) == 5 and all(fd > 2 for fd in startup_fds)
                and all(ok(value['fact'], -1, h['EBADF']) and value['fact']['observed_at_ns']
                        <= times['postexec_ready'] for value in ex['startup_closed'].values())
                and all(ok(value['fact'], value['fact']['result']) and value['fact']['result'] >= 0
                        and not value['fact']['result'] & h['FD_CLOEXEC']
                        and value['fact']['observed_at_ns'] <= times['postexec_ready']
                        for value in ex['startup_private'].values())
                and max(value['fact']['observed_at_ns'] for value in ex['startup_closed'].values())
                <= min(value['fact']['observed_at_ns'] for value in ex['startup_private'].values())
                and all(not value['fact']['attempted'] for values in ex['original_stdio'].values()
                        for value in values), 'Leaf entry must observe three closed and two retained handles')
        for tag, value in fds.items():
            baseline = ids['preexec_worker' if tag == 'G_E' else 'descendant']
            require(value['fd'] >= 0 and ok(value['open'], value['fd'], expected_value=0)
                    and value['identity_before'] == value['identity_after'] == baseline
                    and value['fdinfo_pid'] == baseline['pid'] and value['fdinfo_matches']
                    and ok(value['cloexec'], value['cloexec']['result'])
                    and value['cloexec']['result'] & h['FD_CLOEXEC']
                    and value['initial_live']['fd'] == value['fd']
                    and value['initial_live']['attempts'] == 1
                    and value['initial_live']['result'] == value['initial_live']['revents']
                        == value['initial_live']['errno'] == 0
                    and value['open']['observed_at_ns'] <= value['initial_live']['observed_at_ns']
                    <= (times['exec_sent'] if tag == 'G_E' else times['all_bound']),
                    'All three newly bound original pidfds require identity/fdinfo/live/CLOEXEC facts')
        require(fds['G_E']['fd'] != fds['G_D']['fd'], 'Two live G handles cannot alias')
        for tag in ('G_E', 'G_D'):
            require(closed(fds[tag]) and not fds[tag]['owner_death_teardown'],
                    'Guardian pidfd requires explicit once-close and immediate EBADF')
            require(any(q['handle'] == tag and q['fd'] == fds[tag]['fd'] and q['attempts'] == 1
                        and q['result'] == q['revents'] == q['errno'] == 0
                        and q['observed_at_ns'] is not None and times['all_arm_ack']
                        <= q['observed_at_ns'] <= times['primary'] for q in row['polls']),
                    'Fresh live checks after all ARM acknowledgments required')
        require(any(q['handle'] == 'G_E' and q['fd'] == fds['G_E']['fd'] and q['attempts'] == 1
                    and q['result'] == q['revents'] == q['errno'] == 0
                    and q['observed_at_ns'] is not None and ex['entered_at_ns']
                    <= q['observed_at_ns'] <= times['postexec_validated'] for q in row['polls']),
                'Original preexec G_E must remain live after product transition')
        by_fd = {(v['owner'], v['label'], v['epoch']): v for v in ledger}
        for value in ledger:
            if value['evidence'] == 'explicit_once_close':
                require(closed(value), 'Every claimed explicit closure requires an immediate EBADF')
            if value['epoch'] == 'original_stdio':
                require(value['label'] in ('original_stdin', 'original_stdout', 'original_stderr')
                        and ((value['owner'] == 'preexec_worker' and value['evidence'] == 'explicit_once_close')
                             or (value['owner'] in ('worker', 'descendant')
                                 and value['evidence'] == 'original_absent' and value['fd'] == -1)),
                        'Original stdio epoch must never close a reused child pipe number')
        for role in ('preexec_worker', 'worker', 'descendant'):
            for index, label in enumerate(('original_stdin', 'original_stdout', 'original_stderr')):
                value = by_fd.get((role, label, 'original_stdio'))
                require(value is not None and (value['fd'] == index and closed(value)
                        if role == 'preexec_worker' else value['evidence'] == 'original_absent'),
                        'Three actual X stdio closes and six absent E/D slots required')
        for label, value in ex['startup_closed'].items():
            item = by_fd.get(('worker', label, 'exec_entry'))
            require(item is not None and item['evidence'] == 'exec_entry_closed'
                    and item['fd'] == value['fd'] and item['F_GETFD_after_close'] == value['fact'],
                    'Exec closure evidence must preserve the named original descriptor')
        x_flags = {(v['label'], v['epoch']): v for v in row['fd_flags'] if v['owner'] == 'preexec_worker'}
        for label, item in {**ex['startup_closed'], **ex['startup_private']}.items():
            value = x_flags.get((label, 'preexec'))
            require(value is not None and value['fd'] == item['fd']
                    and ok(value['F_GETFD_before'], value['F_GETFD_before']['result'])
                    and value['F_GETFD_before']['result'] & h['FD_CLOEXEC'],
                    'Actual X exec descriptor CLOEXEC provenance required')
            if label in ex['startup_private']:
                require(ok(value['F_SETFD']) and ok(value['F_GETFD_after'], value['F_GETFD_after']['result'])
                        and not value['F_GETFD_after']['result'] & h['FD_CLOEXEC'],
                        'Only the two retained private endpoints must clear CLOEXEC')
            else:
                require(not value['F_SETFD']['attempted'], 'Exec product/witness/error writer must retain CLOEXEC')
        narrow = {'fixed_exec_transition_verified': True, 'normal_reap_verified': case == 'normal',
                  'worker_loss_adoption_verified': case == 'worker_loss'}
        require(all(controls[k] is (False if partial_reset else v) for k, v in narrow.items())
                and set(negative['created']) == set(negative['bound']) == set(negative['terminal'])
                    == set(negative['reaped']) == {'worker', 'descendant'}
                and not negative['unknown'] and negative['descendant_creation_authorized']
                and negative['descendant_creation_observed'], 'Recomputed successful fixed-role terminal sets differ')
        if case == 'normal':
            require(times['finish_sent'] is not None and times['primary'] <= times['finish_sent']
                    < deadlines['work_ns'] and times['finish_sent'] <= times['D_terminal']
                    <= times['D_reaped'] <= times['E_terminal'] <= times['E_reaped']
                    and all(times[k] is None for k in ('E_signal', 'D_adopted', 'D_signal'))
                    and not row['adoptions'] and not negative['adopted']
                    and all(not value['attempts'] for value in row['signals'].values())
                    and terminal_wait('E_D', 0) and terminal_wait('G_E', 0)
                    and not waits['G_D']['attempts'] and closed(fds['E_D'])
                    and not fds['E_D']['owner_death_teardown'],
                    'Normal outcome requires E reap D, G reap E, zero signals/adoptions')
        else:
            loss_order = ('primary', 'E_signal', 'E_terminal', 'E_reaped', 'D_adopted',
                          'D_signal', 'D_terminal', 'D_reaped')
            require(all(times[k] is not None for k in loss_order)
                    and all(times[a] <= times[b] for a, b in zip(loss_order, loss_order[1:]))
                    and times['E_signal'] < deadlines['work_ns'] and times['D_signal'] < deadlines['cleanup_ns']
                    and times['finish_sent'] is None and terminal_wait('G_E', h['SIGKILL'])
                    and terminal_wait('G_D', h['SIGKILL']) and not waits['E_D']['attempts']
                    and not fds['E_D']['close']['attempted'] and not fds['E_D']['F_GETFD_after_close']['attempted']
                    and fds['E_D']['owner_death_teardown'] and negative['adopted'] == ['descendant']
                    and len(row['adoptions']) == 1, 'Worker loss requires exact direct/adopted reaps and owner-death limits')
            adoption = row['adoptions'][0]
            require(adoption['old_parent'] == ids['worker']['pid']
                    and adoption['new_parent'] == ids['guardian']['pid']
                    and same(adoption['identity'], ids['descendant'], True)
                    and same(adoption['guardian_identity'], ids['guardian'])
                    and times['E_reaped'] <= adoption['observed_at_ns'] <= times['D_signal']
                    and same(checks['presignal_worker'], ids['worker'])
                    and same(checks['presignal_descendant'], ids['descendant'], True)
                    and same(checks['guardian_before_descendant_signal'], ids['guardian']),
                    'Same descendant adoption must be independently observed after E reap')
            for tag, target in (('G_E', 'worker'), ('G_D', 'descendant')):
                value = row['signals'][tag]
                require(value['attempts'] == 1 and value['result'] == value['errno'] == 0
                        and same(value['presignal_identity'], ids[target], tag == 'G_D')
                        and value['observed_at_ns'] == times['E_signal' if tag == 'G_E' else 'D_signal'],
                        'Each planned original signal must succeed once after its exact identity gate')
        expected_ledger = {}
        def expect(role, epoch, names, evidence='explicit_once_close'):
            for label in names.split():
                expected_ledger[(role, label, epoch)] = evidence
        expect('guardian', 'preexec', 'guardian_product leaf_exec leaf_witness command_read command_write '
               'report_read report_write exec_error_read exec_error_write G_E')
        expect('guardian', 'child_generation', 'G_D')
        expect('preexec_worker', 'preexec', 'guardian_product command_write report_read exec_error_read')
        expect('preexec_worker', 'original_stdio', 'original_stdin original_stdout original_stderr')
        for role in ('worker', 'descendant'):
            expect(role, 'original_stdio', 'original_stdin original_stdout original_stderr', 'original_absent')
        expect('worker', 'exec_entry', 'leaf_exec leaf_witness exec_error_write', 'exec_entry_closed')
        expect('worker', 'child_generation', 'child_command_read child_report_write')
        expect('descendant', 'preexec', 'command_read report_write')
        expect('descendant', 'child_generation', 'child_command_write child_report_read')
        if case == 'normal':
            expect('worker', 'preexec', 'command_read')
            expect('worker', 'preexec', 'report_write', 'parent_report_EOF')
            expect('worker', 'child_generation', 'child_command_write child_report_read E_D')
            expect('descendant', 'child_generation', 'child_command_read')
            expect('descendant', 'child_generation', 'child_report_write', 'parent_report_EOF')
        else:
            expect('worker', 'preexec', 'command_read report_write', 'owner_death')
            expect('worker', 'child_generation', 'child_command_write child_report_read E_D', 'owner_death')
            expect('descendant', 'child_generation', 'child_command_read child_report_write', 'unreturned_loss_close')
        require(set(by_fd) == set(expected_ledger) and all(by_fd[k]['evidence'] == v
                for k, v in expected_ledger.items()), 'Exactly forty fixed managed FD provenance rows required')
        for key, value in by_fd.items():
            if value['evidence'] != 'original_absent':
                require(value['fd'] >= 0, 'Every acquired managed FD must preserve its actual number')
            if value['evidence'] == 'explicit_once_close':
                end = (times['preexec_ready'] if value['owner'] == 'preexec_worker' else
                       times['E_reaped'] if value['owner'] == 'worker' else
                       times['D_reaped'] if value['owner'] == 'descendant' else times['FD_complete'])
                require(value['F_GETFD_after_close']['observed_at_ns'] <= end,
                        'Close/EBADF evidence must precede its owner reap or guardian FD completion')
        for tag, value in fds.items():
            item = by_fd[(pairs[tag][0], tag, 'preexec' if tag == 'G_E' else 'child_generation')]
            require(item['fd'] == value['fd'] and item['close'] == value['close']
                    and item['F_GETFD_after_close'] == value['F_GETFD_after_close'],
                    'Pidfd and FD closure ledgers must agree on each original handle')
        for label, value in ex['startup_private'].items():
            require(by_fd[('worker', label, 'preexec')]['fd'] == value['fd']
                    and by_fd[('descendant', label, 'preexec')]['fd'] == value['fd'],
                    'Retained exec endpoints must stay in their original acquisition generation')
        for value in row['fd_flags']:
            require(ok(value['F_GETFD_before'], value['F_GETFD_before']['result'])
                    and value['F_GETFD_before']['result'] >= 0, 'Every observed FD flag query must succeed')
            if value['epoch'] == 'original_stdio':
                require(value['owner'] == 'guardian' and value['label'] in
                        ('original_stdin', 'original_stdout', 'original_stderr')
                        and value['fd'] == ('original_stdin', 'original_stdout', 'original_stderr').index(value['label']),
                        'Only the G inherited stdio generation remains live')
                continue
            require(value['F_GETFD_before']['observed_at_ns'] <= times['all_bound']
                    and ok(value['F_GETFL'], value['F_GETFL']['result']) and value['F_GETFL']['result'] >= 0,
                    'Private FD flags require actual pre-ARM live queries')
            if value['label'] in ('command_read', 'command_write', 'report_read', 'report_write',
                                  'exec_error_read', 'exec_error_write', 'child_command_read',
                                  'child_command_write', 'child_report_read', 'child_report_write'):
                require(value['F_GETFL']['result'] & h['O_NONBLOCK'], 'Every private pipe must be nonblocking')
            if value['F_SETFD']['attempted']:
                require(value['owner'] in ('preexec_worker', 'worker')
                        and value['label'] in ('command_read', 'report_write')
                        and value['epoch'] == 'preexec' and ok(value['F_SETFD'])
                        and ok(value['F_GETFD_after'], value['F_GETFD_after']['result'])
                        and not value['F_GETFD_after']['result'] & h['FD_CLOEXEC'],
                        'Only the two inherited private exec endpoints may clear CLOEXEC')
        for tag, boundary in (('G_E', 'E_terminal'),
                              ('E_D' if case == 'normal' else 'G_D', 'D_terminal')):
            require(any(q['handle'] == tag and q['stage'] == 'terminal' and q['fd'] == fds[tag]['fd']
                        and q['attempts'] > 0 and q['requested_events'] == h['POLLIN']
                        and q['result'] == 1 and q['revents'] & h['POLLIN']
                        and not q['revents'] & h['POLLNVAL'] and q['errno'] == 0
                        and q['observed_at_ns'] == times[boundary] for q in row['polls']),
                    'Named terminal times must bind actual original-handle poll observations')
        require(waits['G_E']['observed_at_ns'] == times['E_reaped']
                and waits['E_D' if case == 'normal' else 'G_D']['observed_at_ns'] == times['D_reaped'],
                'Named reap times must bind actual successful original-child waits')
        if case == 'worker_loss':
            require(times['E_reaped'] < deadlines['cleanup_ns'] and adoption['observed_at_ns']
                    == times['D_adopted'] < deadlines['cleanup_ns']
                    and any(q['handle'] == 'G_D' and q['stage'] == 'presignal_live'
                            and q['fd'] == fds['G_D']['fd'] and q['result'] == q['revents'] == q['errno'] == 0
                            and q['attempts'] == 1 and q['observed_at_ns'] is not None
                            and times['D_adopted'] <= q['observed_at_ns'] <= times['D_signal'] for q in row['polls']),
                    'D signal needs actual post-reap adoption and a fresh post-adoption live observation')
        def event(source, kind):
            values = [v for v in packets if v['source'] == source and v['kind'] == kind]
            require(len(values) == 1, 'Exactly one fixed causal packet required: ' + source + '/' + kind)
            return values[0]
        require(not any(v['kind'] in ('ERROR', 'EXEC_ERROR') for v in packets),
                'Successful packet stream must not contain a saved error')
        commands = [v for v in packets if v['source'] == 'guardian']
        require([v['kind'] for v in commands] == ['EXEC', 'CREATE_D', 'ARM'] +
                (['FINISH'] if case == 'normal' else []) and all(v['aux'] == 0
                and v['sent_at_ns'] < deadlines['work_ns'] for v in commands),
                'Exact once-only fixed command chain before work deadline required')
        for kind, boundary in (('EXEC', 'exec_sent'), ('CREATE_D', 'create_D_sent'), ('ARM', 'arm_sent')):
            require(event('guardian', kind)['sent_at_ns'] == times[boundary],
                    'Named action boundary must bind its actual original command frame')
        pre, enter, post = event('preexec_worker', 'PRE_EXEC_READY'), event('preexec_worker', 'EXEC_ENTER'), event('worker', 'POST_EXEC_READY')
        product_checks = [v for v in packets if v['kind'] == 'PRODUCT_CHECK']
        require(len(product_checks) == 2 and [v['aux'] for v in product_checks] == [1, 2]
                and all(v['source'] == 'preexec_worker' and v['observed_at_ns']
                        <= pre['observed_at_ns'] and v['sent_at_ns'] <= pre['sent_at_ns']
                        for v in product_checks),
                'Two original leaf/witness product-check packets must precede PRE_EXEC_READY')
        created, ready = event('worker', 'D_CREATED'), event('descendant', 'D_READY')
        armed, all_ack = event('descendant', 'ARM_ACK'), event('worker', 'ALL_ARM_ACK')
        require(pre['observed_at_ns'] <= times['preexec_ready'] <= times['exec_sent']
                <= enter['sent_at_ns'] <= post['sent_at_ns'] and post['observed_at_ns']
                <= times['postexec_ready'] <= times['postexec_validated'] <= times['create_D_sent']
                <= created['sent_at_ns'] and times['create_D_sent'] <= ready['sent_at_ns']
                and created['observed_at_ns'] <= ready['observed_at_ns'] and ready['observed_at_ns']
                <= times['D_ready'] <= times['all_bound'] <= times['arm_sent']
                <= armed['sent_at_ns'] <= all_ack['sent_at_ns'] and all_ack['observed_at_ns']
                <= times['all_arm_ack'] < deadlines['work_ns'] and armed['aux'] == all_ack['aux'] == 3,
                'POST gate, fixed creation, full bindings and ARM acknowledgment order required')
        handle_packet = event('worker', 'HANDLE_FACT')
        require(handle_packet['aux'] == 2 and times['create_D_sent'] <= handle_packet['sent_at_ns']
                and handle_packet['observed_at_ns'] <= times['all_bound'], 'E_D anchor must arrive before ARM')
        wanted_forwards = [('ARM', 3)] + ([('FINISH', 4)] if case == 'normal' else [])
        require([(v['kind'], v['original_sequence']) for v in row['command_forwards']] == wanted_forwards,
                'Each fixed command needs its original sequence in exactly one forwarding gate')
        forward_packets = [v for v in packets if v['source'] == 'worker' and v['kind'] == 'COMMAND_FORWARDED']
        require(len(forward_packets) == len(wanted_forwards), 'Every forwarded command must be returned once')
        for value, packet in zip(row['command_forwards'], forward_packets):
            original = event('guardian', value['kind'])
            ack = event('descendant', 'ARM_ACK' if value['kind'] == 'ARM' else 'D_FINISH_ACK')
            require(original['sequence'] == value['original_sequence'] and packet['aux'] ==
                    (9 if value['kind'] == 'ARM' else 12) and original['sent_at_ns']
                    <= value['observed_at_ns'] <= ack['sent_at_ns']
                    and value['observed_at_ns'] <= packet['sent_at_ns']
                    and packet['observed_at_ns'] <= ack['observed_at_ns']
                    and value['observed_at_ns'] < deadlines['work_ns'],
                    'Fresh forwarding gate must retain the original command before the D acknowledgment')
        if case == 'normal':
            finish, d_ack, e_ack = event('guardian', 'FINISH'), event('descendant', 'D_FINISH_ACK'), event('worker', 'E_FINISH_ACK')
            require(finish['sent_at_ns'] == times['finish_sent'] <= d_ack['sent_at_ns']
                    <= times['D_terminal'] <= times['D_reaped'] <= e_ack['sent_at_ns']
                    <= times['E_terminal'] and d_ack['aux'] == e_ack['aux'] == 4,
                    'Normal fixed FINISH/ACK/EOF/reap chain is incomplete')
        else:
            require(not any(v['kind'] in ('FINISH', 'D_FINISH_ACK', 'E_FINISH_ACK') for v in packets),
                    'Loss case cannot substitute the normal terminal command chain')
        return row
    require(not any(controls[k] for k in
            ('fixed_exec_transition_verified', 'normal_reap_verified', 'worker_loss_adoption_verified')),
            'Negative outcome cannot claim narrow success')
    require(partial_reset or (not sr['reset_zero']['attempted'] and not sr['final_get']['attempted']),
            'Negative/unknown state cannot reset the subreaper')
    return row


def build_product(source, header, backend, utility, linkage, name, record):
    record.update({'status': 'failed', 'link_attempts': 0})
    record['compile_leg'] = build = utility.run_toolchain(source, backend)
    require(build['status'] == 'success', 'Fresh C compile leg failed: ' + name)
    require(str(header) in build['headers'], 'Exact new protocol header dependency required')
    cpp, _ = backend.read_output('preprocess.stdout', MAX_BYTES)
    build['cpp_facts'].update(parse_exec_cpp_markers(cpp))
    compiler, product, obj = build['compiler'], backend.root / name, backend.root / 'probe.o'
    record['link_attempts'] = 1
    link = backend.run('link', [compiler['path'], str(obj), '-Wl,-Map,' + str(backend.root / 'link.map'),
                                '-o', str(product)])
    record['link'] = link
    require(link['status'] == 'success', 'Fresh fixed ELF link failed: ' + name)
    raw, map_row = backend.read_output('link.map', MAX_BYTES)
    links, total = {}, 0
    for path in linkage.parse_link_map(raw, obj):
        links[path] = item = backend.snapshot(os.path.realpath(path), utility.MAX_DRIVER)
        total += item['bytes']
        require(total <= utility.MAX_HEADERS_TOTAL, 'Postlink inventory byte limit exceeded')
    raw, product_row = backend.read_output(name, MAX_BYTES)
    require(product_row['identity'][2] & 0o111, 'Executable product mode required')
    record['product'] = {**product_row, **linkage.parse_elf_product(raw)}
    require(all(record['product'][key] == build['object'][key]
                for key in ('elf_class', 'data_encoding', 'machine')), 'Object/product descriptors differ')
    interp_path = record['product']['interpreter']
    record['interpreter'] = interp = backend.snapshot(os.path.realpath(interp_path), utility.MAX_DRIVER)
    record['link_inputs_after_link'] = links
    bound = {**build['output_bindings'], 'link.map': map_row, name: product_row,
             'link.stdout': link['stdout'], 'link.stderr': link['stderr']}
    record['output_bindings'] = bound

    def recheck():
        for path, item in {**build['headers'], **links}.items():
            require(os.path.realpath(path) == item['path']
                    and backend.snapshot(item['path'], utility.MAX_DRIVER) == item, 'Input/link snapshot drift')
        require(os.path.realpath(compiler['role_path']) == compiler['path']
                and backend.snapshot(compiler['path'], utility.MAX_DRIVER) ==
                {key: value for key, value in compiler.items() if key != 'role_path'}, 'Compiler role drift')
        require(os.path.realpath(interp_path) == interp['path']
                and backend.snapshot(interp['path'], utility.MAX_DRIVER) == interp, 'Interpreter descriptor drift')
        for key, item in bound.items():
            require(backend.read_output(key, MAX_BYTES)[1] == item, 'Bound output drift')
    recheck()
    record['status'] = 'success'
    return recheck


def run_fixture(sources, backend, utility, linkage, case, nonce, expected_parent_pid, expected_uid,
                expected_boot_id, pre_runtime_check=None, fault='none'):
    result = {**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'status': 'failed', 'builds': {},
              'runtime_attempts': 0, 'runtime_returned_complete_facts': False,
              'complete_mapped_code_authenticated': False, 'fault': fault}
    opened, rechecks, products = [], [], {}
    try:
        require(type(case) is str and case in ('normal', 'worker_loss')
                and type(nonce) is str and re.fullmatch(r'[0-9a-f]{64}', nonce)
                and type(fault) is str and fault in ('none', 'exec_fd_closed', 'witness_cloexec_cleared')
                and type(sources) is dict and set(sources) == set(C_NAMES), 'Closed new C fixture arguments required')
        if pre_runtime_check is not None:
            pre_runtime_check()
        for name, source_name in (('leaf', C_NAMES[1]), ('guardian', C_NAMES[0])):
            os.mkdir(name, 0o700, dir_fd=backend.root_fd)
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=backend.root_fd)
            opened.append(fd)
            os.mkdir('tmp', 0o700, dir_fd=fd)
            leg = utility.CompilerBackend(backend.helper, backend.root / name, fd)
            record = result['builds'][name] = {}
            rechecks.append(build_product(sources[source_name], sources[C_NAMES[2]], leg,
                                          utility, linkage, name, record))
            products[name] = record['product']
        require(result['builds']['leaf']['compile_leg']['cpp_facts'] ==
                result['builds']['guardian']['compile_leg']['cpp_facts'], 'Cross-product CPP facts differ')
        require(result['builds']['leaf']['compile_leg']['headers'][str(sources[C_NAMES[2]])] ==
                result['builds']['guardian']['compile_leg']['headers'][str(sources[C_NAMES[2]])],
                'Common header bytes/identity differ across builds')
        for recheck in rechecks:
            recheck()
        if pre_runtime_check is not None:
            pre_runtime_check()
        result['runtime_attempts'] = 1
        argv = [products['guardian']['path'], case, nonce, products['leaf']['path'], fault]
        command = backend.run('runtime', argv)
        result['runtime_command'] = command
        require(command['argv'] == argv, 'Actual runtime argv differs from the two bound products')
        raw, runtime_stdout = backend.read_output('runtime.stdout', MAX_RUNTIME_BYTES)
        stderr, runtime_stderr = backend.read_output('runtime.stderr', MAX_RUNTIME_BYTES)
        require(runtime_stdout == command['stdout'] and runtime_stderr == command['stderr']
                and runtime_stdout['bytes'] == len(raw) and runtime_stdout['sha256'] == digest(raw)
                and runtime_stderr['bytes'] == len(stderr) and runtime_stderr['sha256'] == digest(stderr)
                and not stderr, 'Runtime returned stream bytes/bindings differ')
        result['runtime_report'] = facts = parse_runtime(raw, command,
            result['builds']['guardian']['compile_leg']['cpp_facts'], expected_parent_pid, expected_uid,
            expected_boot_id, case, nonce, products['guardian']['identity'], products['leaf']['identity'], fault)
        result['runtime_returned_complete_facts'] = True
        for recheck in rechecks:
            recheck()
        require(backend.read_output('runtime.stdout', MAX_RUNTIME_BYTES) == (raw, runtime_stdout)
                and backend.read_output('runtime.stderr', MAX_RUNTIME_BYTES) == (stderr, runtime_stderr),
                'Runtime outputs drifted after parser/input checks')
        result['runtime_output_bindings'] = {key: command[key] for key in ('stdout', 'stderr')}
        require(command['status'] == 'success' and facts['status'] == 'success' and fault == 'none',
                'Fixed exec/descendant fixture returned a negative result')
        result[SUCCESS[0]] = True
        result[SUCCESS[1 if case == 'normal' else 2]] = True
        result['status'] = 'success'
    except Exception as error:
        result['error'] = error_fact(error)
    finally:
        for fd in opened:
            os.close(fd)
    return result


def observe(request_path, expected_sha256):
    require(sys.platform == 'linux' and sys.flags.isolated == sys.flags.no_site == 1
            and sys.dont_write_bytecode and os.getuid() == os.geteuid(),
            'Fresh equal-UID Linux -B -I -S file entry required')
    helper, utility, linkage = load_utilities()
    source = helper.normalized_path(__file__)
    sources = {name: source.with_name(name) for name in C_NAMES}
    uid, inputs = os.getuid(), []
    ordered = [source, *(sources[name] for name in C_NAMES), Path(helper.__file__),
               Path(utility.__file__), Path(linkage.__file__)]
    for path in ordered:
        raw, identity = helper.read_regular(str(path), helper.MAX_SOURCE_BYTES)
        inputs.append((path, raw, identity, helper.MAX_SOURCE_BYTES, None))
    request_file = helper.normalized_path(request_path)
    raw, identity = helper.read_regular(str(request_file), helper.MAX_REQUEST_BYTES, owner=uid)
    inputs.append((request_file, raw, identity, helper.MAX_REQUEST_BYTES, uid))
    for index, module in ((4, helper), (5, utility), (6, linkage)):
        require(inputs[index][1:3] == (module._captured_bytes, module._captured_identity),
                'Captured utility input drift')
    c_hashes = {name: digest(inputs[index + 1][1]) for index, name in enumerate(C_NAMES)}
    request = parse_request(inputs[7][1], expected_sha256, digest(inputs[0][1]), c_hashes, helper)
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
                             'observer_sha256': digest(inputs[0][1]), 'c_sources_sha256': c_hashes,
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

            receipt['fixture'] = run_fixture(sources, utility.CompilerBackend(helper, root, root_fd),
                utility, linkage, request['case'], request['nonce'], own['pid'], uid, own['boot_id'],
                validate_inputs)
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
            if receipt['fixture']['status'] == 'success':
                receipt['status'] = 'fixed_owned_C_exec_descendant_observed'
                receipt[SUCCESS[0]] = True
                receipt[SUCCESS[1 if request['case'] == 'normal' else 2]] = True
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
    if any(x == '--execute' or x.startswith('--execute=') for x in argv):
        raise ValueError('Execution unavailable; separately declared fixed owned C CPU fixture only')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-owned-c-exec-descendant', action='store_true')
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-request-sha256', required=True)
    args = parser.parse_args(argv)
    require(args.observe_owned_c_exec_descendant, 'Explicit new fixed exec/descendant observer required')
    receipt = observe(args.request, args.expected_request_sha256)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['status'] == 'fixed_owned_C_exec_descendant_observed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(json.dumps({**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'schema_version': 1,
                          'scope': SCOPE, 'status': 'failed', 'error': error_fact(error)}, sort_keys=True))
        sys.exit(1)
