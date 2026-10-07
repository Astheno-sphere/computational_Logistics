"""Fixed surviving C guardian adoption observations; no production or model authority."""
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


SCOPE = 'frontier_v8_owned_C_guardian_adoption_CPU_fixture'
HELPER_SHA = '1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412'
LINKAGE_SHA = '3374d4ed4ef1bafa38d8f4340ffcc042ee396d966228a682adf890182108b47c'
TOOLCHAIN_SHA = '2175f96e939993db69eb14348fa3115ae583416a1d38307f38f23bd378d003c0'
FIELDS = {'schema_version', 'scope', 'nonce', 'observer_sha256', 'c_probe_sha256',
          'identity_helper_sha256', 'toolchain_sha256', 'linkage_sha256', 'case', 'attempt_directory', 'host', 'bootstrap'}
AUTHORITY = dict.fromkeys(('functional_containment_verified', 'containment_available',
                          'execution_available', 'resource_authority',
                          'model_runtime_ABI_observed', 'production_controller_guard_completed',
                          'GPU_or_foreign_restore'), False)
SUCCESS = ('controlled_guard_loss_worker_adoption_reap_observed',
           'controlled_coordinator_loss_guard_worker_adoption_reap_observed')
MAX_BYTES = 8 * 1024 * 1024
FORBIDDEN_OUTPUT_PREFIXES = (
    '/data/zefan/open-jev-v8-runtime-abi-', '/data/zefan/open-jev-v8-containment-presence-',
    '/data/zefan/open-jev-v8-pidfd-selfcheck-', '/data/zefan/open-jev-v8-linux-runtime-',
    '/data/zefan/open-jev-v8-c-toolchain-', '/data/zefan/open-jev-v8-owned-c-selfcheck-',
    '/data/zefan/open-jev-v8-owned-c-lifecycle-',
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
    name = 'frontier_v8_guardian_identity_helper'
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
    name = 'frontier_v8_guardian_build_utility'
    require(digest(utility_body) == TOOLCHAIN_SHA and name not in sys.modules,
            'Captured toolchain source/cache differs')
    utility = ModuleType(name)
    utility.__file__, utility.__package__ = str(utility_path), None
    exec(compile(utility_body, str(utility_path), 'exec', dont_inherit=True), utility.__dict__)
    utility._captured_bytes, utility._captured_identity = utility_body, utility_identity
    linkage_path = source.with_name('frontier_v8_owned_c_selfcheck.py')
    linkage_body, linkage_identity = helper.read_regular(str(linkage_path), helper.MAX_SOURCE_BYTES)
    name = 'frontier_v8_guardian_linkage_utility'
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
            and request['scope'] == SCOPE, 'Exact new guardian adoption declaration required')
    require(type(request['nonce']) is str and re.fullmatch(r'[0-9a-f]{64}', request['nonce'])
            and request['observer_sha256'] == source_sha256 and request['c_probe_sha256'] == probe_sha256
            and request['identity_helper_sha256'] == HELPER_SHA
            and request['toolchain_sha256'] == TOOLCHAIN_SHA
            and request['linkage_sha256'] == LINKAGE_SHA
            and type(request['case']) is str and request['case'] in ('guard_loss', 'coordinator_loss'), 'Exact closure and fresh nonce required')
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


def parse_guardian_cpp_markers(body):
    """Recognize captured header expressions; the compiler evaluates the C."""
    require(type(body) is bytes and len(body) <= MAX_BYTES, 'Bounded CPP bytes required')
    text = body.decode('ascii')
    facts = {}
    token = r'(?:0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]*|<<|>>|[()+\-*/%~&|^]'
    for marker, key in (
            ('header_pidfd_send_signal', 'SYS_pidfd_send_signal_expression'),
            ('header_pr_set_child_subreaper', 'PR_SET_CHILD_SUBREAPER_expression'),
            ('header_pr_get_child_subreaper', 'PR_GET_CHILD_SUBREAPER_expression')):
        name = 'frontier_v8_' + marker
        require(len(re.findall(r'\b' + name + r'\b', text)) == 1, 'One captured CPP marker required')
        match = re.search(r'\bconst\s+long\s+' + name + r'\s*=\s*([^;]+);', text)
        require(match is not None, 'Exact captured long marker required')
        value = match.group(1).strip()
        require(0 < len(value) <= 1024 and re.fullmatch(r'(?:\s*(?:' + token + r'))+\s*', value),
                'Opaque expanded numeric C expression required')
        facts[key] = value
    return facts


def parse_runtime(body, command, cpp_facts, expected_parent_pid, expected_uid,
                  expected_boot_id, case, nonce, product_identity):
    """Recompute the two closed outcomes under the reviewed C/compiler baseline."""
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'Duplicate C JSON key refused')
            value[key] = item
        return value

    def fields(value, names):
        require(type(value) is dict and set(value) == set(names.split()), 'Exact fact fields required')

    def number(value, low=0, high=(1 << 63) - 1, optional=False):
        require((optional and value is None) or (type(value) is int and low <= value <= high),
                'Bounded typed C integer required')

    def boolean(value):
        require(type(value) is bool, 'Typed boolean required')

    def operation(value):
        fields(value, 'attempted result errno value')
        boolean(value['attempted'])
        number(value['result'], -1, (1 << 31) - 1, optional=True)
        number(value['errno'], high=(1 << 31) - 1, optional=True)
        number(value['value'], high=(1 << 31) - 1, optional=True)
        require(value['attempted'] or all(value[k] is None for k in ('result', 'errno', 'value')),
                'Unattempted operation cannot carry invented results')

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
        fields(value['product_identity'], 'dev ino size mtime_ns ctime_ns')
        for key, item in value['product_identity'].items():
            number(item, high=(1 << (63 if key.endswith('_ns') else 64)) - 1)

    def poll_fact(value):
        fields(value, 'owner target fd stage attempts requested_events result revents errno observed_at_ns')
        require(value['owner'] in roles and value['target'] in roles and value['stage'] in
                ('initial_live', 'terminal', 'EOF_child_live'), 'Declared poll roles/stage required')
        number(value['fd'], -1, (1 << 31) - 1)
        number(value['attempts'], high=(1 << 31) - 1)
        number(value['requested_events'], high=(1 << 15) - 1)
        number(value['result'], -1, 1, optional=True)
        number(value['revents'], high=(1 << 15) - 1, optional=True)
        number(value['errno'], high=(1 << 31) - 1, optional=True)
        number(value['observed_at_ns'], optional=True)
        require(value['attempts'] or all(value[k] is None for k in
                ('result', 'revents', 'errno', 'observed_at_ns')), 'Unattempted poll has results')

    require(type(body) is bytes and 0 < len(body) <= 65536, 'Bounded complete C JSON required')
    row = json.loads(body, object_pairs_hook=unique,
                     parse_constant=lambda value: require(False, 'Nonfinite C JSON refused'))
    fields(row, 'schema_version scope case nonce status error headers subreaper child_subreaper_get '
                'identities_initial identity_rechecks adoptions pidfds polls waits signals fd_ledger '
                'packets deadlines times_ns controls negative_state')
    require(type(row['schema_version']) is int and row['schema_version'] == 1 and row['scope'] == SCOPE
            and type(case) is str and case in ('guard_loss', 'coordinator_loss') and row['case'] == case
            and type(nonce) is str and re.fullmatch(r'[0-9a-f]{64}', nonce) and row['nonce'] == nonce
            and row['status'] in ('success', 'failed', 'unknown'), 'Exact guardian case/nonce required')
    roles = ('guardian', 'coordinator', 'guard', 'worker')
    error = row['error']
    fields(error, 'stage role operation errno bounded_detail')
    require(type(error['stage']) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', error['stage'])
            and error['role'] in (*roles, None)
            and (error['operation'] is None or (type(error['operation']) is str and
                 re.fullmatch(r'[a-z][a-z0-9_]{0,63}', error['operation'])))
            and (error['bounded_detail'] is None or (type(error['bounded_detail']) is str
                 and len(error['bounded_detail']) <= 256)), 'Bounded first error required')
    number(error['errno'], high=(1 << 31) - 1, optional=True)
    h = row['headers']
    fields(h, 'pidfd_open pidfd_send_signal pr_set_child_subreaper pr_get_child_subreaper SIGKILL POLLIN '
              'POLLNVAL F_GETFD FD_CLOEXEC EBADF PIPE_BUF target_int_bytes target_long_bytes '
              'target_pointer_bytes target_char_bits target_byte_order pid_t_bytes uid_t_bytes '
              'pid_t_signed uid_t_signed uint64_bytes int64_bytes pid_representation uid_representation '
              'uint64_representation int64_representation pid_max uid_max uint64_max int64_min int64_max')
    for key in ('pidfd_open', 'pidfd_send_signal', 'pr_set_child_subreaper', 'pr_get_child_subreaper'):
        number(h[key], high=(1 << 63) - 1)
    for key in ('SIGKILL', 'POLLIN', 'POLLNVAL', 'F_GETFD', 'FD_CLOEXEC', 'EBADF', 'PIPE_BUF',
                'target_int_bytes', 'target_long_bytes', 'target_pointer_bytes', 'target_char_bits',
                'target_byte_order', 'pid_t_bytes', 'uid_t_bytes', 'uint64_bytes', 'int64_bytes'):
        number(h[key], 1, (1 << 31) - 1)
    import fcntl
    require(all(h[key] == cpp_facts[key] for key in ('target_int_bytes', 'target_long_bytes',
                'target_pointer_bytes', 'target_char_bits', 'target_byte_order'))
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
            and h['SIGKILL'] == signal.SIGKILL and h['POLLIN'] == select.POLLIN
            and h['POLLNVAL'] == select.POLLNVAL and h['EBADF'] == errno.EBADF
            and h['F_GETFD'] == fcntl.F_GETFD and h['FD_CLOEXEC'] == fcntl.FD_CLOEXEC
            and h['pr_set_child_subreaper'] != h['pr_get_child_subreaper']
            and all(h[k] <= (1 << (h['target_long_bytes'] * 8 - 1)) - 1 for k in
                    ('pidfd_open', 'pidfd_send_signal'))
            and h['pr_set_child_subreaper'] <= h['pid_max'] and h['pr_get_child_subreaper'] <= h['pid_max'],
            'Captured C scalar/header/representation baseline differs')
    sr = row['subreaper']
    fields(sr, 'initial_get set_enabled verify_enabled_get terminal_set_disabled terminal_verify_disabled_get')
    fields(row['child_subreaper_get'], 'coordinator guard worker')
    for value in (*sr.values(), *row['child_subreaper_get'].values()):
        operation(value)
    ids = row['identities_initial']
    fields(ids, 'guardian coordinator guard worker')
    for value in ids.values():
        identity(value)
    expected_product = dict(zip(('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'),
                                (product_identity[0], product_identity[1], *product_identity[4:7])))
    initial_tree_valid = (all(x is not None for x in ids.values())
        and len({x['pid'] for x in ids.values()}) == 4
        and ids['guardian']['pid'] == command['direct_child_pid']
        and ids['guardian']['ppid'] == expected_parent_pid
        and ids['coordinator']['ppid'] == ids['guardian']['pid']
        and ids['guard']['ppid'] == ids['coordinator']['pid']
        and ids['worker']['ppid'] == ids['guard']['pid']
        and all(x['uid'] == x['euid'] == expected_uid and x['boot_id'] == expected_boot_id
                and x['product_identity'] == expected_product for x in ids.values()))
    checks = row['identity_rechecks']
    fields(checks, 'before_H_signal before_W_signal')
    for values in checks.values():
        fields(values, 'guardian coordinator guard worker')
        for value in values.values():
            identity(value)
    adoptions = row['adoptions']
    require(type(adoptions) is list and len(adoptions) <= 2, 'Two closed adoption facts at most')
    for value in adoptions:
        fields(value, 'phase target expected_old_parent observed_new_parent observed_identity '
                      'initial_identity_equal_except_ppid guardian_identity observed_at_ns passed')
        require(value['target'] in ('guard', 'worker') and value['phase'] in ('guard_adopted', 'worker_adopted'),
                'Closed adoption role required')
        for key in ('expected_old_parent', 'observed_new_parent'):
            number(value[key], 1, (1 << 31) - 1)
        identity(value['observed_identity'])
        identity(value['guardian_identity'])
        boolean(value['initial_identity_equal_except_ppid'])
        boolean(value['passed'])
        number(value['observed_at_ns'])
    fds = row['pidfds']
    fields(fds, 'G_C G_H G_W C_H H_W')
    pairs = {'G_C': ('guardian', 'coordinator'), 'G_H': ('guardian', 'guard'),
             'G_W': ('guardian', 'worker'), 'C_H': ('coordinator', 'guard'), 'H_W': ('guard', 'worker')}
    for tag, value in fds.items():
        fields(value, 'owner target fd open identity_before identity_after fdinfo cloexec live_poll close_mode '
                      'explicit_close immediate_F_GETFD kernel_teardown_limit signal_budget')
        require((value['owner'], value['target']) == pairs[tag], 'Immutable pidfd owner/target differs')
        number(value['fd'], -1, (1 << 31) - 1)
        for key in ('open', 'cloexec', 'explicit_close', 'immediate_F_GETFD'):
            operation(value[key])
        for key in ('identity_before', 'identity_after'):
            identity(value[key])
        fields(value['fdinfo'], 'attempted pid matches')
        boolean(value['fdinfo']['attempted'])
        boolean(value['fdinfo']['matches'])
        number(value['fdinfo']['pid'], -1, (1 << 31) - 1, optional=True)
        require(value['fdinfo']['attempted'] or value['fdinfo']['pid'] is None,
                'Unattempted fdinfo cannot report a PID')
        poll_fact(value['live_poll'])
        require(value['close_mode'] in ('unobserved', 'explicit_close_then_immediate_EBADF',
                'owner_SIGKILL_kernel_teardown') and (value['kernel_teardown_limit'] is None or
                (type(value['kernel_teardown_limit']) is str and len(value['kernel_teardown_limit']) <= 128)),
                'Typed descriptor observation mode required')
        number(value['signal_budget'], high=1)
        require(value['signal_budget'] == int(tag in ('G_H', 'G_W')), 'Combined handle budget differs')
    fields(row['polls'], 'G_C G_H G_W C_H H_W_EOF C_H_EOF')
    for value in row['polls'].values():
        poll_fact(value)
    waits = row['waits']
    fields(waits, 'G_C G_H G_W C_H')
    for tag, value in waits.items():
        fields(value, 'owner target pid stage attempted attempts result raw_status exited exit_code '
                      'signaled term_signal errno observed_at_ns')
        require((value['owner'], value['target']) == pairs[tag] and value['stage'] == 'terminal',
                'Declared parent wait role required')
        number(value['pid'], -1, (1 << 31) - 1)
        boolean(value['attempted'])
        number(value['attempts'], high=(1 << 31) - 1)
        for key in ('result', 'exit_code', 'term_signal', 'errno'):
            number(value[key], -1 if key == 'result' else 0, (1 << 31) - 1, optional=True)
        number(value['raw_status'], high=65535, optional=True)
        number(value['observed_at_ns'], optional=True)
        for key in ('exited', 'signaled'):
            require(value[key] is None or type(value[key]) is bool, 'Typed wait classification required')
        require(value['attempted'] or (value['attempts'] == 0 and all(value[k] is None for k in
                ('result', 'raw_status', 'exited', 'exit_code', 'signaled', 'term_signal', 'errno', 'observed_at_ns'))),
                'Unattempted wait has invented results')
        if value['raw_status'] is not None:
            raw = value['raw_status']
            ex, sig = os.WIFEXITED(raw), os.WIFSIGNALED(raw)
            require(value['exited'] is ex and value['signaled'] is sig
                    and value['exit_code'] == (os.WEXITSTATUS(raw) if ex else None)
                    and value['term_signal'] == (os.WTERMSIG(raw) if sig else None),
                    'Recomputed raw wait classification differs')
    signals = row['signals']
    require(type(signals) is list and len(signals) == 2, 'Exactly two planned signal rows required')
    for value in signals:
        fields(value, 'ledger_kind owner target fd original_handle_tag original_identity presignal_identity '
                      'symbol number_from_header flags attempts attempt_budget_consumed_before_call '
                      'negative_state_entered later_planned_actions_disabled result errno observed_at_ns')
        require(value['ledger_kind'] == 'planned' and value['owner'] == 'guardian'
                and value['original_handle_tag'] in ('G_H', 'G_W')
                and value['target'] == pairs[value['original_handle_tag']][1]
                and value['symbol'] == 'SIGKILL', 'Closed planned signal target required')
        number(value['fd'], -1, (1 << 31) - 1)
        number(value['number_from_header'], high=(1 << 31) - 1)
        number(value['flags'], high=(1 << 32) - 1)
        number(value['attempts'], high=1)
        number(value['result'], -1, (1 << 31) - 1, optional=True)
        number(value['errno'], high=(1 << 31) - 1, optional=True)
        number(value['observed_at_ns'], optional=True)
        for key in ('attempt_budget_consumed_before_call', 'negative_state_entered', 'later_planned_actions_disabled'):
            boolean(value[key])
        identity(value['original_identity'])
        identity(value['presignal_identity'])
        require(value['attempts'] or all(value[k] is None for k in ('result', 'errno', 'observed_at_ns')),
                'Unattempted signal cannot claim success')
        require(value['attempt_budget_consumed_before_call'] is bool(value['attempts']),
                'Every attempted signal consumes its original handle before the call')
        if value['attempts']:
            require(initial_tree_valid and value['negative_state_entered'] is False and value['result'] in (-1, 0)
                    and value['errno'] is not None and value['observed_at_ns'] is not None
                    and value['number_from_header'] == h['SIGKILL'] and value['flags'] == 0
                    and value['fd'] >= 0 and value['fd'] == fds[value['original_handle_tag']]['fd']
                    and value['original_identity'] is not None and value['presignal_identity'] is not None
                    and value['original_identity'] == ids[value['target']],
                    'Only original planned handles may be signalled before negative state')
    require([x['original_handle_tag'] for x in signals] == ['G_H', 'G_W'], 'Unique combined signal handles required')
    ledger = row['fd_ledger']
    require(type(ledger) is list and len(ledger) <= 128, 'Bounded FD ledger required')
    for value in ledger:
        fields(value, 'owner kind fd stage attempted close_result close_errno F_GETFD_result F_GETFD_errno '
                      'observation_mode limit')
        require(value['owner'] in roles and type(value['kind']) is str
                and re.fullmatch(r'[A-Za-z_]{1,64}', value['kind']) and type(value['stage']) is str
                and re.fullmatch(r'[A-Za-z_]{1,64}', value['stage']), 'Bounded named FD role required')
        number(value['fd'], -1, (1 << 31) - 1)
        boolean(value['attempted'])
        for key in ('close_result', 'F_GETFD_result'):
            number(value[key], -1, (1 << 31) - 1, optional=True)
        for key in ('close_errno', 'F_GETFD_errno'):
            number(value[key], high=(1 << 31) - 1, optional=True)
        require(value['observation_mode'] in ('unobserved', 'explicit_close_then_immediate_EBADF',
                'parent_EOF_while_child_alive', 'owner_SIGKILL_kernel_teardown')
                and (value['limit'] is None or (type(value['limit']) is str and len(value['limit']) <= 128)),
                'Explicit FD observation mode required')
        require(value['attempted'] or all(value[k] is None for k in
                ('close_result', 'close_errno', 'F_GETFD_result', 'F_GETFD_errno')),
                'Unobserved closure cannot invent a return')
    packets = row['packets']
    require(type(packets) is list and len(packets) <= 128, 'Bounded private packet ledger required')
    kinds = ('ROLE_READY', 'HANDLE_FACT', 'ARM', 'ROLE_ARM_ACK', 'FD_CLOSE_FACT', 'PIPE_EOF_FACT',
             'ALL_ARM_ACK', 'COORDINATOR_EXIT23', 'COORDINATOR_EXIT_ACK', 'GUARD_WAIT_FACT',
             'COORDINATOR_FINISH', 'COORDINATOR_FINISH_ACK', 'HANDLE_CLOSE_FACT',
             'CHILD_SUBREAPER_GET', 'TERMINAL_POLL_FACT', 'ERROR_FACT')
    for value in packets:
        fields(value, 'edge kind role stage_ordinal case nonce shared_t0 bytes PIPE_BUF_bound '
                      'forwarded_original_frame complete parent_EOF_while_child_alive')
        require(value['kind'] in kinds and value['role'] in roles and value['edge'] in ('G_from_C', 'C_from_G')
                and value['case'] == case
                and value['nonce'] == nonce, 'Private frame binding differs')
        number(value['stage_ordinal'], 1, 128)
        number(value['shared_t0'])
        number(value['bytes'], 1, 512)
        number(value['PIPE_BUF_bound'], 1, (1 << 31) - 1)
        require(value['bytes'] <= value['PIPE_BUF_bound'], 'Measured atomic pipe bound exceeded')
        for key in ('forwarded_original_frame', 'complete', 'parent_EOF_while_child_alive'):
            boolean(value[key])
    d, t = row['deadlines'], row['times_ns']
    fields(d, 't0_ns work_ns cleanup_ns terminal_ns guardian_total_ns child_self_expiry_ns')
    fields(t, 'initial_identity all_ready arm_sent all_arm_ack primary_loss_command C_exit C_reaped C_H_exit '
              'H_adoption H_signal H_exit H_reaped W_adoption W_presignal W_signal W_exit W_reaped '
              'C_finish C_finish_ack terminal final')
    for value in d.values():
        number(value, optional=True)
    for value in t.values():
        number(value, optional=True)
    controls = (*AUTHORITY, 'physical_exclusion_verified', 'guardian_loss_recovery_verified',
                'observer_loss_recovery_verified', 'host_loss_recovery_guaranteed',
                'arbitrary_descendant_or_exec_containment_verified', 'queue_restore_proven')
    fields(row['controls'], ' '.join(controls))
    require(all(value is False for value in row['controls'].values()), 'Broad authority must remain unavailable')
    n = row['negative_state']
    fields(n, 'entered first_error_stage first_error_operation first_error_at_ns later_planned_signals_disabled '
              'negative_cleanup_signals known_created known_bound known_adopted known_terminal known_reaped '
              'unknown_members terminal_reset_gate_complete self_SIGPIPE_ignore')
    for key in ('entered', 'later_planned_signals_disabled', 'terminal_reset_gate_complete'):
        boolean(n[key])
    require(n['negative_cleanup_signals'] == [] and type(n['negative_cleanup_signals']) is list,
            'Negative directed signals must be zero')
    for key in ('known_created', 'known_bound', 'known_adopted', 'known_terminal', 'known_reaped', 'unknown_members'):
        value = n[key]
        require(type(value) is list and len(value) <= 3 and all(type(x) is str and x in roles[1:] for x in value)
                and len(set(value)) == len(value), 'Exact member sets required')
    for key in ('first_error_stage', 'first_error_operation'):
        require(n[key] is None or (type(n[key]) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', n[key])),
                'Typed negative first error required')
    number(n['first_error_at_ns'], optional=True)
    operation(n['self_SIGPIPE_ignore'])
    if row['status'] != 'success':
        require(error['stage'] != 'none' and n['entered'] is True
                and n['later_planned_signals_disabled'] is True
                and n['first_error_stage'] == error['stage'] and n['first_error_operation'] == error['operation'],
                'Negative result must retain first error and disable later actions')
        for kind, event in (('ARM', 'arm_sent'), ('COORDINATOR_EXIT23', 'primary_loss_command'),
                            ('COORDINATOR_FINISH', 'C_finish')):
            if any(x['kind'] == kind for x in packets):
                require(t[event] is not None and n['first_error_at_ns'] is not None
                        and t[event] <= n['first_error_at_ns'], 'Managed-role command after first error forbidden')
        require(all(x['attempts'] or (x['later_planned_actions_disabled'] is True
                    and x['negative_state_entered'] is True) for x in signals),
                'Every unused planned signal must stay disabled after failure')
        require(not any(x['attempts'] for x in signals) or n['first_error_at_ns'] is not None,
                'Attempted signals require an observed first-error cutoff')
        if signals[0]['attempts'] and (signals[0]['result'] != 0 or signals[0]['errno'] != 0):
            require(signals[1]['attempts'] == 0 and not n['terminal_reset_gate_complete']
                    and not sr['terminal_set_disabled']['attempted']
                    and not sr['terminal_verify_disabled_get']['attempted'],
                    'A failed guard signal permanently disables worker action and reset')
        if n['first_error_at_ns'] is not None:
            require(all(not x['attempts'] or (x['observed_at_ns'] is not None and
                    x['observed_at_ns'] <= n['first_error_at_ns']) for x in signals),
                    'Signal after first error is forbidden')
        for value in signals:
            if not value['attempts']:
                continue
            role = value['target']
            adopted = role == 'worker' or case == 'coordinator_loss'
            expected = {**ids[role], 'ppid': ids['guardian']['pid']} if adopted else ids[role]
            require(value['presignal_identity'] == expected, 'Negative ledger retains exact presignal identity')
            if adopted:
                matches = [x for x in adoptions if x['target'] == role and x['passed'] is True
                           and x['observed_identity'] == expected and x['initial_identity_equal_except_ppid'] is True
                           and x['observed_at_ns'] <= value['observed_at_ns']]
                require(len(matches) == 1, 'A later adoption cannot authorize an earlier signal')
        reset = sr['terminal_set_disabled']['attempted'] or sr['terminal_verify_disabled_get']['attempted']
        if reset or n['terminal_reset_gate_complete']:
            require(row['status'] == 'failed' and error['stage'] == 'terminal_reset'
                    and error['operation'] in ('prctl_set_disabled', 'prctl_get_disabled')
                    and n['terminal_reset_gate_complete'] is True, 'Only terminal reset failure may carry a reset gate')
            setter, getter = sr['terminal_set_disabled'], sr['terminal_verify_disabled_get']
            if error['operation'] == 'prctl_set_disabled':
                require(setter['attempted'] and setter['result'] == -1 and setter['errno'] is not None
                        and setter['errno'] > 0 and not getter['attempted'], 'Retain actual failed reset setter')
            else:
                require(setter == {'attempted': True, 'result': 0, 'errno': 0, 'value': None}
                        and getter['attempted'] and (getter['result'] == -1 and getter['errno'] is not None
                        and getter['errno'] > 0 or getter['result'] == 0 and getter['errno'] == 0
                        and getter['value'] is not None and getter['value'] != 0), 'Retain actual failed reset verification')
            # Reuse every ordinary case predicate with only the failed terminal reset normalized.
            # This derived predicate input is neither returned nor saved as an observed receipt.
            probe = json.loads(json.dumps(row))
            probe.update(status='success', error={'stage': 'none', 'role': None, 'operation': None,
                                                  'errno': None, 'bounded_detail': None})
            probe['subreaper']['terminal_set_disabled'] = {'attempted': True, 'result': 0, 'errno': 0, 'value': None}
            probe['subreaper']['terminal_verify_disabled_get'] = {'attempted': True, 'result': 0, 'errno': 0, 'value': 0}
            probe['negative_state'].update(entered=False, first_error_stage=None, first_error_operation=None,
                                         first_error_at_ns=None, later_planned_signals_disabled=False)
            for value in probe['signals']:
                value['later_planned_actions_disabled'] = False
            parse_runtime(json.dumps(probe, separators=(',', ':')).encode(),
                          {**command, 'status': 'success', 'returncode': 0}, cpp_facts,
                          expected_parent_pid, expected_uid, expected_boot_id, case, nonce, product_identity)
        return row

    require(command['status'] == 'success' and command['returncode'] == 0
            and command['reap_completed'] is True and command['timed_out'] is False
            and error == {'stage': 'none', 'role': None, 'operation': None, 'errno': None, 'bounded_detail': None},
            'Guardian normal return and no first error required')
    require(initial_tree_valid, 'Fixed fork parentage/boot/UID/product differs')
    for key, value in sr.items():
        expected = 1 if key == 'verify_enabled_get' else 0 if key.endswith('get') else None
        require(value == {'attempted': True, 'result': 0, 'errno': 0, 'value': expected},
                'Five actual process-local subreaper operations required')
    require(all(x == {'attempted': True, 'result': 0, 'errno': 0, 'value': 0}
                for x in row['child_subreaper_get'].values()), 'Actual child subreaper0 facts required')
    require(n['entered'] is False and n['later_planned_signals_disabled'] is False
            and n['first_error_stage'] is n['first_error_operation'] is n['first_error_at_ns'] is None
            and n['unknown_members'] == [] and n['terminal_reset_gate_complete'] is True
            and all(set(n[k]) == set(roles[1:]) for k in
                    ('known_created', 'known_bound', 'known_terminal', 'known_reaped'))
            and set(n['known_adopted']) == ({'worker'} if case == 'guard_loss' else {'guard', 'worker'})
            and n['self_SIGPIPE_ignore'] == {'attempted': True, 'result': 0, 'errno': 0, 'value': None},
            'Complete narrow terminal/reset gate required')
    for phase, snapshot in checks.items():
        for role, value in snapshot.items():
            live = role != 'guard' or phase == 'before_H_signal'
            live = live and (role != 'coordinator' or case == 'guard_loss')
            adopted = role == 'worker' and phase == 'before_W_signal' or role == 'guard' and case == 'coordinator_loss'
            expected = {**ids[role], 'ppid': ids['guardian']['pid']} if adopted else ids[role]
            require(value == (expected if live else None), 'Live-only fresh presignal identity differs')
    expected_targets = ['worker'] if case == 'guard_loss' else ['guard', 'worker']
    require([x['target'] for x in adoptions] == expected_targets, 'Exact separate adoption sequence required')
    for value in adoptions:
        role = value['target']
        expected = {**ids[role], 'ppid': ids['guardian']['pid']}
        require(value['phase'] == role + '_adopted' and value['expected_old_parent'] == ids[role]['ppid']
                and value['observed_new_parent'] == ids['guardian']['pid']
                and value['observed_identity'] == expected and value['guardian_identity'] == ids['guardian']
                and value['initial_identity_equal_except_ppid'] is True and value['passed'] is True
                and value['observed_at_ns'] == t['H_adoption' if role == 'guard' else 'W_adoption'],
                'Explicit adoption snapshot and invariant identity required')
    for tag, value in fds.items():
        require(value['fd'] >= 0 and value['open'] == {'attempted': True, 'result': value['fd'], 'errno': 0, 'value': None}
                and value['identity_before'] == value['identity_after'] == ids[value['target']]
                and value['fdinfo'] == {'attempted': True, 'pid': ids[value['target']]['pid'], 'matches': True}
                and value['cloexec']['attempted'] is True and value['cloexec']['errno'] == 0
                and value['cloexec']['value'] is None and value['cloexec']['result'] is not None
                and value['cloexec']['result'] >= 0
                and value['cloexec']['result'] & h['FD_CLOEXEC'], 'Bound original pidfd required')
        live = value['live_poll']
        require((live['owner'], live['target']) == pairs[tag] and live['fd'] == value['fd']
                and live['stage'] == 'initial_live' and live['attempts'] > 0
                and live['requested_events'] == h['POLLIN'] and live['result'] == live['revents'] == live['errno'] == 0
                and live['observed_at_ns'] is not None and d['t0_ns'] <= live['observed_at_ns'] <= t['arm_sent'],
                'All five anchors must be observed live before ARM')
        if tag == 'H_W':
            unattempted = {'attempted': False, 'result': None, 'errno': None, 'value': None}
            require(value['close_mode'] == 'owner_SIGKILL_kernel_teardown'
                    and value['explicit_close'] == value['immediate_F_GETFD'] == unattempted
                    and value['kernel_teardown_limit'] == 'No explicit H_W close/EBADF observation',
                    'Killed-owner teardown cannot invent explicit closure')
        else:
            require(value['close_mode'] == 'explicit_close_then_immediate_EBADF'
                    and value['explicit_close'] == {'attempted': True, 'result': 0, 'errno': 0, 'value': None}
                    and value['immediate_F_GETFD'] == {'attempted': True, 'result': -1, 'errno': h['EBADF'], 'value': None}
                    and value['kernel_teardown_limit'] is None, 'Four explicit once-close/EBADF facts required')
    require(len({fds[x]['fd'] for x in ('G_C', 'G_H', 'G_W')}) == 3, 'Guardian handles must be distinct')
    inactive_wait = 'G_H' if case == 'guard_loss' else 'C_H'
    for tag, value in waits.items():
        require(value['pid'] == ids[value['target']]['pid'], 'Wait bound original PID required')
        if tag == inactive_wait:
            require(value['attempted'] is False, 'No wait on a role owned by another parent')
            continue
        expected_status = (0 if case == 'guard_loss' else 23 << 8) if tag == 'G_C' else h['SIGKILL']
        require(value['attempted'] is True and value['attempts'] > 0
                and value['result'] == value['pid'] and value['errno'] == 0 and value['raw_status'] == expected_status,
                'Exact proper-parent terminal wait required')
        event = {'G_C': 'C_reaped', 'G_H': 'H_reaped', 'C_H': 'H_reaped', 'G_W': 'W_reaped'}[tag]
        require(value['observed_at_ns'] == t[event], 'Parent wait timestamp differs')
    for tag, value in row['polls'].items():
        if tag in ('H_W_EOF', 'C_H_EOF'):
            handle = 'H_W' if tag == 'H_W_EOF' else 'C_H'
            require((value['owner'], value['target']) == pairs[handle] and value['fd'] == fds[handle]['fd']
                    and value['stage'] == 'EOF_child_live' and value['attempts'] > 0
                    and value['requested_events'] == h['POLLIN'] and value['result'] == value['revents'] == value['errno'] == 0
                    and value['observed_at_ns'] is not None and t['arm_sent'] <= value['observed_at_ns'] <= t['all_arm_ack'],
                    'Parent EOF requires an actual nonterminal anchored child poll')
            continue
        require((value['owner'], value['target']) == pairs[tag] and value['fd'] == fds[tag]['fd']
                and value['stage'] == 'terminal' and value['requested_events'] == h['POLLIN'],
                'Bound terminal pidfd poll required')
        if tag == 'C_H' and case == 'coordinator_loss':
            require(value['attempts'] == 0, 'Coordinator cannot observe guard after exiting')
        else:
            require(value['attempts'] > 0 and value['result'] == 1 and value['errno'] == 0
                    and value['revents'] is not None and value['revents'] & h['POLLIN']
                    and not value['revents'] & h['POLLNVAL'] and value['observed_at_ns'] ==
                    t[{'G_C': 'C_exit', 'G_H': 'H_exit', 'C_H': 'C_H_exit', 'G_W': 'W_exit'}[tag]],
                    'Actual terminal pidfd event required')
    for value in signals:
        tag, role = value['original_handle_tag'], value['target']
        require(value['fd'] == fds[tag]['fd'] and value['attempts'] == 1
                and value['number_from_header'] == h['SIGKILL'] and value['flags'] == 0
                and value['result'] == value['errno'] == 0 and value['attempt_budget_consumed_before_call'] is True
                and value['negative_state_entered'] is False and value['later_planned_actions_disabled'] is False
                and value['original_identity'] == ids[role]
                and value['presignal_identity'] == checks['before_H_signal' if tag == 'G_H' else 'before_W_signal'][role]
                and value['observed_at_ns'] == t['H_signal' if tag == 'G_H' else 'W_signal'],
                'Exactly two adopted/armed owned signal attempts required')
    require(len({(x['owner'], x['kind'], x['fd'], x['stage']) for x in ledger}) == len(ledger)
            and all(not x['attempted'] or (x['close_result'] == x['close_errno'] == 0
                    and x['F_GETFD_result'] == -1 and x['F_GETFD_errno'] == h['EBADF']) for x in ledger),
            'Real named inherited/pipe closures required')
    require(all(any(x['owner'] == role and x['kind'] == 'command_read' and x['attempted'] for x in ledger)
                for role in ('guard', 'worker')), 'Guard/worker command reader closure must precede parking')
    require(not any(x['kind'] == 'ERROR_FACT' for x in packets)
            and all(x['complete'] and x['shared_t0'] == d['t0_ns'] for x in packets)
            and [x['stage_ordinal'] for x in packets] == list(range(1, len(packets) + 1)),
            'Complete ordered private frame chain required')
    def packet_index(kind, role):
        found = [i for i, x in enumerate(packets) if x['kind'] == kind and x['role'] == role]
        require(len(found) == 1, 'One required private frame per role/stage')
        return found[0]
    order = [('ROLE_READY', 'worker'), ('ROLE_READY', 'guard'), ('ROLE_READY', 'coordinator'), ('ARM', 'guardian'),
             ('ROLE_ARM_ACK', 'worker'), ('PIPE_EOF_FACT', 'worker'), ('ROLE_ARM_ACK', 'guard'),
             ('PIPE_EOF_FACT', 'guard'), ('ROLE_ARM_ACK', 'coordinator'), ('ALL_ARM_ACK', 'coordinator')]
    indices = [packet_index(*x) for x in order]
    require(indices == sorted(indices), 'Physical READY/ACK/EOF order differs')
    require(all(packets[packet_index('PIPE_EOF_FACT', role)]['parent_EOF_while_child_alive']
                for role in ('worker', 'guard')), 'Parent-observed EOF while child live required')
    command_kinds = ('ARM', 'COORDINATOR_EXIT23', 'COORDINATOR_FINISH')
    for value in packets:
        is_command = value['kind'] in command_kinds
        require((value['edge'], value['role']) == ('C_from_G', 'guardian') if is_command else
                value['edge'] == 'G_from_C' and value['role'] in roles[1:], 'Exact private command/report edge required')
        if is_command or value['role'] == 'coordinator':
            require(value['forwarded_original_frame'] is False, 'Direct frame cannot claim forwarding')
        elif value['kind'] in ('ROLE_READY', 'ROLE_ARM_ACK', 'HANDLE_FACT', 'FD_CLOSE_FACT',
                                'HANDLE_CLOSE_FACT', 'CHILD_SUBREAPER_GET', 'TERMINAL_POLL_FACT'):
            require(value['forwarded_original_frame'] is True, 'Nested role frames must be forwarded unchanged')
        elif value['kind'] == 'PIPE_EOF_FACT':
            require(value['forwarded_original_frame'] is (value['role'] == 'worker'),
                    'EOF forwarding must retain its actual parent actor')
    ending = ('COORDINATOR_FINISH_ACK' if case == 'guard_loss' else 'COORDINATOR_EXIT_ACK')
    require(packet_index(ending, 'coordinator') > indices[-1], 'Case terminal ACK must follow ARM')
    if case == 'guard_loss':
        require(indices[-1] < packet_index('GUARD_WAIT_FACT', 'coordinator') <
                packet_index('COORDINATOR_FINISH', 'guardian') < packet_index(ending, 'coordinator'),
                'Coordinator guard parent-wait report required')
    else:
        require(indices[-1] < packet_index('COORDINATOR_EXIT23', 'guardian') < packet_index(ending, 'coordinator'),
                'Explicit coordinator loss command required before its exit ACK')
    require(not any(x['kind'] in (('COORDINATOR_EXIT23', 'COORDINATOR_EXIT_ACK') if case == 'guard_loss'
                    else ('COORDINATOR_FINISH', 'COORDINATOR_FINISH_ACK', 'GUARD_WAIT_FACT')) for x in packets),
            'Other case packet cannot authorize current loss')
    t0 = d['t0_ns']
    require(t0 is not None and all(d[key] == t0 + seconds * 1000000000 for key, seconds in
            (('work_ns', 5), ('cleanup_ns', 8), ('terminal_ns', 10), ('guardian_total_ns', 12),
             ('child_self_expiry_ns', 14))), 'One inherited absolute deadline epoch required')
    sequence = ('initial_identity', 'all_ready', 'arm_sent', 'all_arm_ack', 'primary_loss_command')
    # Exit names denote these particular pidfd terminal observations, not kernel death times.
    sequence += (('H_signal', 'C_H_exit', 'H_reaped', 'H_exit', 'W_adoption', 'W_presignal', 'W_signal',
                  'W_exit', 'W_reaped', 'C_finish', 'C_finish_ack', 'C_exit', 'C_reaped')
                 if case == 'guard_loss' else ('C_exit', 'C_reaped', 'H_adoption', 'H_signal', 'H_exit',
                  'H_reaped', 'W_adoption', 'W_presignal', 'W_signal', 'W_exit', 'W_reaped'))
    sequence += ('terminal', 'final')
    require(all(t[key] is not None for key in sequence)
            and [t0, *[t[key] for key in sequence]] == sorted([t0, *[t[key] for key in sequence]])
            and t['primary_loss_command'] < d['work_ns'] and t['W_reaped'] < d['cleanup_ns']
            and t['H_reaped'] < d['cleanup_ns'] and t['terminal'] < d['terminal_ns']
            and t['final'] < d['guardian_total_ns'], 'Finite actual case event ordering required')
    require(t['H_signal'] < (d['work_ns'] if case == 'guard_loss' else d['cleanup_ns'])
            and t['W_signal'] < d['cleanup_ns'], 'Signal entry must respect its case deadline')
    require(t['H_adoption'] is None if case == 'guard_loss' else
            t['C_finish'] is t['C_finish_ack'] is t['C_H_exit'] is None, 'Inactive case timestamps must remain unknown')
    return row


def run_guardian(source, backend, utility, linkage, case, nonce, expected_parent_pid,
                  expected_uid, expected_boot_id, pre_runtime_check=None):
    result = {**AUTHORITY, **dict.fromkeys(SUCCESS, False), 'status': 'failed',
              'commands': [], 'link_attempts': 0, 'runtime_attempts': 0,
              'runtime_returned_complete_facts': False, 'complete_mapped_code_authenticated': False}
    try:
        require(type(case) is str and case in ('guard_loss', 'coordinator_loss')
                and type(nonce) is str and re.fullmatch(r'[0-9a-f]{64}', nonce),
                'Closed case and fresh nonce required before compiler entry')
        if pre_runtime_check is not None:
            pre_runtime_check()
        result['compile_leg'] = build = utility.run_toolchain(source, backend)
        require(build['status'] == 'success', 'Fresh dedicated C compile leg failed')
        cpp, _ = backend.read_output('preprocess.stdout', MAX_BYTES)
        build['cpp_facts'].update(parse_guardian_cpp_markers(cpp))
        compiler = build['compiler']
        product, object_path = backend.root / 'guardian', backend.root / 'probe.o'
        result['link_attempts'] = 1
        command = backend.run('link', [compiler['path'], str(object_path), '-Wl,-Map,' +
                                       str(backend.root / 'link.map'), '-o', str(product)])
        result['commands'].append(command)
        require(command['status'] == 'success', 'Fixed owned C guardian adoption link failed')
        body, map_row = backend.read_output('link.map', MAX_BYTES)
        links, total = {}, 0
        for path in linkage.parse_link_map(body, object_path):
            links[path] = row = backend.snapshot(os.path.realpath(path), utility.MAX_DRIVER)
            total += row['bytes']
            require(total <= utility.MAX_HEADERS_TOTAL, 'Link inventory total byte limit exceeded')
        body, product_row = backend.read_output('guardian', MAX_BYTES)
        require(product_row['identity'][2] & 0o111, 'Executable product mode required')
        result['product'] = {**product_row, **linkage.parse_elf_product(body)}
        require(all(result['product'][key] == build['object'][key]
                    for key in ('elf_class', 'data_encoding', 'machine')),
                'Object and product ELF descriptors differ')
        interpreter_path = result['product']['interpreter']
        interpreter = backend.snapshot(os.path.realpath(interpreter_path), utility.MAX_DRIVER)
        result['interpreter'] = interpreter
        result['link_inputs_after_link'] = links
        bound = {**build['output_bindings'], 'link.map': map_row, 'guardian': product_row,
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
                'Fixed owned C guardian adoption returned a terminal negative result')
        result[SUCCESS[0 if case == 'guard_loss' else 1]] = True
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
    probe = source.with_name('frontier_v8_owned_c_guardian.c')
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

            receipt['guardian'] = run_guardian(probe, utility.CompilerBackend(helper, root, root_fd),
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
            if receipt['guardian']['status'] == 'success':
                receipt['status'] = 'owned_C_guardian_adoption_observed'
                receipt[SUCCESS[0 if request['case'] == 'guard_loss' else 1]] = True
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
        raise ValueError('Execution unavailable; separately declared fixed owned C guardian adoption fixture only')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe-owned-c-guardian', action='store_true')
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-request-sha256', required=True)
    args = parser.parse_args(argv)
    require(args.observe_owned_c_guardian, 'Explicit separate fixed owned-C guardian adoption observation required')
    receipt = observe(args.request, args.expected_request_sha256)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['status'] == 'owned_C_guardian_adoption_observed' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
