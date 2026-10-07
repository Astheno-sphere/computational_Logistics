"""New guardian fixtures; synthetic records are not observed kernel evidence.

Interface lineage: guardian-runtime-interface-example-r1.json, SHA256
3c6d35198bd9e7593a343a471075d49731276d100cdbcc0349ddcd6b9b6c6f24.
The private illustrative sample remains untouched and is not loaded at CI.
These independently constructed fixtures correct physical READY W/H/C ordering,
closed G command/report edges, W_ACK/EOF_W/H_ACK/EOF_H/C_ACK ordering, live-only snapshots, product stat5
projection, and separate C_H/G_H terminal-observation timestamps. The two case
timelines distinguish guard-loss FINISH from coordinator-loss adoption.

Pinned pure backend/ELF helpers below are test-only dependencies, outside the five
runtime/deployed sources. Importing their definitions runs no old CLI or tests.
"""
from contextlib import ExitStack
import copy
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import select
import signal
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_owned_c_guardian as observer


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_HELPER_PINS = {
    'tests/test_frontier_v8_c_toolchain.py':
        '538ba287c4f27eae26ed794b844c015a679c147af0d0efc0a848868bed81f31d',
    'tests/test_frontier_v8_owned_c_selfcheck.py':
        'd25d8a31e5df465f144c5076fc35c7f928222897235ffb0432019f23f58d43c4',
}
for helper_path, expected_sha in FIXTURE_HELPER_PINS.items():
    if hashlib.sha256((ROOT / helper_path).read_bytes()).hexdigest() != expected_sha:
        raise ValueError('Pure fixture helper bytes changed: ' + helper_path)

from tests.test_frontier_v8_c_toolchain import FakeCompilerBackend, own_identity
from tests.test_frontier_v8_owned_c_selfcheck import product_bytes


BOOT = '00000000-0000-0000-0000-000000000001'
NONCE = '1' * 64
UID = os.getuid()
PRODUCT = [1, 2, 0o100755, UID, len(product_bytes()), 6, 7]
CPP = {'SYS_pidfd_open_expression': '((1 << 8) + 9L)',
       'SYS_pidfd_send_signal_expression': '(10002L)',
       'PR_SET_CHILD_SUBREAPER_expression': '(10003)',
       'PR_GET_CHILD_SUBREAPER_expression': '(10004)',
       'target_int_bytes': 4, 'target_long_bytes': 8, 'target_pointer_bytes': 8,
       'target_char_bits': 8, 'target_byte_order': 1234}
EXTRA_MARKERS = (
    'const long frontier_v8_header_pidfd_send_signal = (10002L);',
    'const long frontier_v8_header_pr_set_child_subreaper = (10003);',
    'const long frontier_v8_header_pr_get_child_subreaper = (10004);')
PAIRS = {'G_C': ('guardian', 'coordinator'), 'G_H': ('guardian', 'guard'),
         'G_W': ('guardian', 'worker'), 'C_H': ('coordinator', 'guard'),
         'H_W': ('guard', 'worker')}


def operation(result=0, value=None, error=0, attempted=True):
    return {'attempted': attempted, 'result': result if attempted else None,
            'errno': error if attempted else None, 'value': value if attempted else None}


def command(**changes):
    return {'direct_child_pid': 42, 'status': 'success', 'returncode': 0,
            'timed_out': False, 'reap_completed': True, **changes}


def runtime_facts(case='guard_loss', nonce=NONCE, product=PRODUCT):
    """Coherent explicitly synthetic facts, constructed without private samples."""
    projected = dict(zip(('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'),
                         (product[0], product[1], *product[4:7])))
    roles = ('guardian', 'coordinator', 'guard', 'worker')
    ids = {role: {'pid': 42 + i, 'ppid': 7 if i == 0 else 41 + i,
                  'start_ticks': 100 + i, 'boot_id': BOOT, 'uid': UID, 'euid': UID,
                  'product_identity': copy.deepcopy(projected)} for i, role in enumerate(roles)}
    headers = {'pidfd_open': 265, 'pidfd_send_signal': 10002,
               'pr_set_child_subreaper': 10003, 'pr_get_child_subreaper': 10004,
               'SIGKILL': int(signal.SIGKILL), 'POLLIN': select.POLLIN,
               'POLLNVAL': select.POLLNVAL, 'F_GETFD': fcntl.F_GETFD,
               'FD_CLOEXEC': fcntl.FD_CLOEXEC, 'EBADF': errno.EBADF, 'PIPE_BUF': 4096,
               'target_int_bytes': 4, 'target_long_bytes': 8, 'target_pointer_bytes': 8,
               'target_char_bits': 8, 'target_byte_order': 1234,
               'pid_t_bytes': 4, 'uid_t_bytes': 4, 'pid_t_signed': True,
               'uid_t_signed': False, 'uint64_bytes': 8, 'int64_bytes': 8,
               'pid_representation': 'signed32', 'uid_representation': 'unsigned32',
               'uint64_representation': 'unsigned64', 'int64_representation': 'signed64',
               'pid_max': (1 << 31) - 1, 'uid_max': (1 << 32) - 1,
               'uint64_max': (1 << 64) - 1, 'int64_min': -(1 << 63),
               'int64_max': (1 << 63) - 1}
    t0 = 1000000000
    sequence = ['initial_identity', 'all_ready', 'arm_sent', 'all_arm_ack', 'primary_loss_command']
    sequence += (['H_signal', 'C_H_exit', 'H_reaped', 'H_exit', 'W_adoption', 'W_presignal',
                  'W_signal', 'W_exit', 'W_reaped', 'C_finish', 'C_finish_ack', 'C_exit', 'C_reaped']
                 if case == 'guard_loss' else
                 ['C_exit', 'C_reaped', 'H_adoption', 'H_signal', 'H_exit', 'H_reaped',
                  'W_adoption', 'W_presignal', 'W_signal', 'W_exit', 'W_reaped'])
    sequence += ['terminal', 'final']
    times = {name: t0 + (i + 1) * 1000000 for i, name in enumerate(sequence)}
    for name in ('H_adoption', 'C_H_exit', 'C_finish', 'C_finish_ack'):
        times.setdefault(name, None)
    deadlines = {'t0_ns': t0, **{name: t0 + seconds * 1000000000 for name, seconds in
                 [('work_ns', 5), ('cleanup_ns', 8), ('terminal_ns', 10),
                  ('guardian_total_ns', 12), ('child_self_expiry_ns', 14)]}}
    before_h = copy.deepcopy(ids)
    if case == 'coordinator_loss':
        before_h['coordinator'] = None
        before_h['guard']['ppid'] = ids['guardian']['pid']
    before_w = copy.deepcopy(ids)
    before_w['guard'] = None
    before_w['worker']['ppid'] = ids['guardian']['pid']
    if case == 'coordinator_loss':
        before_w['coordinator'] = None
    adoptions = []
    for role in (['worker'] if case == 'guard_loss' else ['guard', 'worker']):
        adoptions.append({'phase': role + '_adopted', 'target': role,
            'expected_old_parent': ids[role]['ppid'], 'observed_new_parent': ids['guardian']['pid'],
            'observed_identity': {**copy.deepcopy(ids[role]), 'ppid': ids['guardian']['pid']},
            'initial_identity_equal_except_ppid': True, 'guardian_identity': copy.deepcopy(ids['guardian']),
            'observed_at_ns': times['H_adoption' if role == 'guard' else 'W_adoption'], 'passed': True})

    def poll(tag, stage, at, terminal=False, attempted=True):
        owner, target = PAIRS[tag]
        fd = 3 + list(PAIRS).index(tag)
        return {'owner': owner, 'target': target, 'fd': fd, 'stage': stage,
                'attempts': int(attempted), 'requested_events': headers['POLLIN'],
                'result': int(terminal) if attempted else None,
                'revents': headers['POLLIN'] if terminal and attempted else 0 if attempted else None,
                'errno': 0 if attempted else None, 'observed_at_ns': at if attempted else None}

    pidfds = {}
    for i, (tag, (owner, target)) in enumerate(PAIRS.items()):
        killed_owner = tag == 'H_W'
        pidfds[tag] = {'owner': owner, 'target': target, 'fd': 3 + i,
            'open': operation(3 + i), 'identity_before': copy.deepcopy(ids[target]),
            'identity_after': copy.deepcopy(ids[target]),
            'fdinfo': {'attempted': True, 'pid': ids[target]['pid'], 'matches': True},
            'cloexec': operation(headers['FD_CLOEXEC']),
            'live_poll': poll(tag, 'initial_live', times['all_ready']),
            'close_mode': 'owner_SIGKILL_kernel_teardown' if killed_owner else 'explicit_close_then_immediate_EBADF',
            'explicit_close': operation(attempted=not killed_owner),
            'immediate_F_GETFD': operation(-1, error=errno.EBADF, attempted=not killed_owner),
            'kernel_teardown_limit': 'No explicit H_W close/EBADF observation' if killed_owner else None,
            'signal_budget': int(tag in ('G_H', 'G_W'))}
    polls = {tag: poll(tag, 'terminal', times[event], terminal=True,
                      attempted=not (tag == 'C_H' and case == 'coordinator_loss'))
             for tag, event in [('G_C', 'C_exit'), ('G_H', 'H_exit'),
                                ('G_W', 'W_exit'), ('C_H', 'C_H_exit')]}
    polls['H_W_EOF'] = poll('H_W', 'EOF_child_live', times['arm_sent'] + 100000)
    polls['C_H_EOF'] = poll('C_H', 'EOF_child_live', times['arm_sent'] + 200000)
    waits = {}
    for tag in ('G_C', 'G_H', 'G_W', 'C_H'):
        owner, target = PAIRS[tag]
        attempted = tag != ('G_H' if case == 'guard_loss' else 'C_H')
        raw = (0 if case == 'guard_loss' else 23 << 8) if tag == 'G_C' else int(signal.SIGKILL)
        exited = tag == 'G_C'
        waits[tag] = {'owner': owner, 'target': target, 'pid': ids[target]['pid'], 'stage': 'terminal',
            'attempted': attempted, 'attempts': int(attempted),
            'result': ids[target]['pid'] if attempted else None, 'raw_status': raw if attempted else None,
            'exited': exited if attempted else None,
            'exit_code': (0 if case == 'guard_loss' else 23) if exited and attempted else None,
            'signaled': not exited if attempted else None,
            'term_signal': int(signal.SIGKILL) if not exited and attempted else None,
            'errno': 0 if attempted else None,
            'observed_at_ns': times['C_reaped' if tag == 'G_C' else 'W_reaped' if tag == 'G_W' else 'H_reaped'] if attempted else None}
    signals = []
    for tag, phase, event in [('G_H', before_h, 'H_signal'), ('G_W', before_w, 'W_signal')]:
        target = PAIRS[tag][1]
        signals.append({'ledger_kind': 'planned', 'owner': 'guardian', 'target': target,
            'fd': pidfds[tag]['fd'], 'original_handle_tag': tag,
            'original_identity': copy.deepcopy(ids[target]), 'presignal_identity': copy.deepcopy(phase[target]),
            'symbol': 'SIGKILL', 'number_from_header': headers['SIGKILL'], 'flags': 0, 'attempts': 1,
            'attempt_budget_consumed_before_call': True, 'negative_state_entered': False,
            'later_planned_actions_disabled': False, 'result': 0, 'errno': 0, 'observed_at_ns': times[event]})
    order = [('ROLE_READY', 'worker'), ('ROLE_READY', 'guard'), ('ROLE_READY', 'coordinator'),
             ('ARM', 'guardian'),
             ('ROLE_ARM_ACK', 'worker'), ('PIPE_EOF_FACT', 'worker'), ('ROLE_ARM_ACK', 'guard'),
             ('PIPE_EOF_FACT', 'guard'), ('ROLE_ARM_ACK', 'coordinator'), ('ALL_ARM_ACK', 'coordinator')]
    order += ([('GUARD_WAIT_FACT', 'coordinator'), ('COORDINATOR_FINISH', 'guardian'),
               ('COORDINATOR_FINISH_ACK', 'coordinator')] if case == 'guard_loss' else
              [('COORDINATOR_EXIT23', 'guardian'), ('COORDINATOR_EXIT_ACK', 'coordinator')])
    packets = [{'edge': 'C_from_G' if role == 'guardian' else 'G_from_C',
                'kind': kind, 'role': role, 'stage_ordinal': i + 1,
                'case': case, 'nonce': nonce, 'shared_t0': t0, 'bytes': 384, 'PIPE_BUF_bound': 4096,
                'forwarded_original_frame': role == 'worker' if kind == 'PIPE_EOF_FACT' else role in ('guard', 'worker'),
                'complete': True,
                'parent_EOF_while_child_alive': kind == 'PIPE_EOF_FACT'}
               for i, (kind, role) in enumerate(order)]
    ledger = [{'owner': role, 'kind': 'command_read', 'fd': 20 + i, 'stage': 'after_ACK',
               'attempted': True, 'close_result': 0, 'close_errno': 0,
               'F_GETFD_result': -1, 'F_GETFD_errno': errno.EBADF,
               'observation_mode': 'explicit_close_then_immediate_EBADF', 'limit': None}
              for i, role in enumerate(('worker', 'guard'))]
    return {'schema_version': 1, 'scope': observer.SCOPE, 'case': case, 'nonce': nonce, 'status': 'success',
            'error': {'stage': 'none', 'role': None, 'operation': None, 'errno': None, 'bounded_detail': None},
            'headers': headers, 'subreaper': {'initial_get': operation(value=0),
                'set_enabled': operation(), 'verify_enabled_get': operation(value=1),
                'terminal_set_disabled': operation(), 'terminal_verify_disabled_get': operation(value=0)},
            'child_subreaper_get': {role: operation(value=0) for role in roles[1:]},
            'identities_initial': ids, 'identity_rechecks': {'before_H_signal': before_h, 'before_W_signal': before_w},
            'adoptions': adoptions, 'pidfds': pidfds, 'polls': polls, 'waits': waits, 'signals': signals,
            'fd_ledger': ledger, 'packets': packets, 'deadlines': deadlines, 'times_ns': times,
            'controls': {**observer.AUTHORITY, **dict.fromkeys(('physical_exclusion_verified',
                'guardian_loss_recovery_verified', 'observer_loss_recovery_verified',
                'host_loss_recovery_guaranteed', 'arbitrary_descendant_or_exec_containment_verified',
                'queue_restore_proven'), False)},
            'negative_state': {'entered': False, 'first_error_stage': None, 'first_error_operation': None,
                'first_error_at_ns': None, 'later_planned_signals_disabled': False, 'negative_cleanup_signals': [],
                'known_created': list(roles[1:]), 'known_bound': list(roles[1:]),
                'known_adopted': ['worker'] if case == 'guard_loss' else ['guard', 'worker'],
                'known_terminal': list(roles[1:]), 'known_reaped': list(roles[1:]), 'unknown_members': [],
                'terminal_reset_gate_complete': True, 'self_SIGPIPE_ignore': operation()}}


def failed_signal_facts(error=errno.EINTR):
    """Handled partial H-attempt failure, with W disabled and no cleanup signal."""
    row = runtime_facts()
    first = row['times_ns']['H_signal']
    row['status'] = 'failed'
    row['error'] = {'stage': 'h_signal', 'role': 'guardian', 'operation': 'pidfd_send_signal',
                    'errno': error, 'bounded_detail': None}
    row['negative_state'].update(entered=True, first_error_stage='h_signal',
        first_error_operation='pidfd_send_signal', first_error_at_ns=first,
        later_planned_signals_disabled=True, known_adopted=[], known_terminal=[], known_reaped=[],
        unknown_members=['coordinator', 'guard', 'worker'], terminal_reset_gate_complete=False)
    row['signals'][0].update(result=-1, errno=error, later_planned_actions_disabled=True)
    row['signals'][1].update(attempts=0, result=None, errno=None, observed_at_ns=None,
        presignal_identity=None, attempt_budget_consumed_before_call=False,
        negative_state_entered=True, later_planned_actions_disabled=True)
    row['adoptions'] = []
    row['identity_rechecks']['before_W_signal'] = dict.fromkeys(row['identities_initial'])
    row['subreaper']['terminal_set_disabled'] = operation(attempted=False)
    row['subreaper']['terminal_verify_disabled_get'] = operation(attempted=False)
    for tag in ('C_H', 'H_W'):
        row['pidfds'][tag].update(close_mode='unobserved', explicit_close=operation(attempted=False),
            immediate_F_GETFD=operation(attempted=False), kernel_teardown_limit=None)
    for tag in ('G_C', 'G_H', 'G_W', 'C_H'):
        row['polls'][tag].update(attempts=0, result=None, revents=None, errno=None, observed_at_ns=None)
        row['waits'][tag].update(attempted=False, attempts=0, result=None, raw_status=None,
            exited=None, exit_code=None, signaled=None, term_signal=None, errno=None, observed_at_ns=None)
    row['packets'] = row['packets'][:10]
    for name in row['times_ns']:
        if name not in ('initial_identity', 'all_ready', 'arm_sent', 'all_arm_ack', 'primary_loss_command', 'H_signal'):
            row['times_ns'][name] = None
    row['times_ns']['final'] = first + 1000000
    return row


def failed_reset_facts(case='guard_loss', reset_operation='prctl_set_disabled'):
    """Complete pre-reset case with an actual failed reset, never synthetic success."""
    row = runtime_facts(case)
    row['status'] = 'failed'
    row['error'] = {'stage': 'terminal_reset', 'role': 'guardian', 'operation': reset_operation,
                    'errno': errno.EINVAL, 'bounded_detail': None}
    row['negative_state'].update(entered=True, first_error_stage='terminal_reset',
        first_error_operation=reset_operation, first_error_at_ns=row['times_ns']['terminal'],
        later_planned_signals_disabled=True)
    for planned in row['signals']:
        planned['later_planned_actions_disabled'] = True
    if reset_operation == 'prctl_set_disabled':
        row['subreaper']['terminal_set_disabled'] = operation(-1, error=errno.EINVAL)
        row['subreaper']['terminal_verify_disabled_get'] = operation(attempted=False)
    else:
        row['subreaper']['terminal_verify_disabled_get'] = operation(-1, error=errno.EINVAL)
    return row


class FakeGuardianBackend(FakeCompilerBackend):
    """New guardian product/result injection; no compiler or product is executed."""
    def __init__(self, root, source, *, failure=None, drift=None):
        super().__init__(root, source, failure=failure, drift=drift)
        self.runtime_calls = 0

    def read_output(self, name, limit):
        body, row = super().read_output(name, limit)
        if name == 'guardian':
            row['identity'] = [1, 2, 0o100755, UID, len(body), 6, 7]
        return body, row

    def snapshot(self, path, limit):
        row = super().snapshot(path, limit)
        if self.drift in ('interpreter', 'link_input') and str(path) == (
                '/fixture/loader' if self.drift == 'interpreter' else '/fixture/link-input') \
                and self.snapshots[str(path)] > 1:
            row['sha256'] = '0' * 64
        return row

    def run(self, label, argv):
        if label not in ('link', 'runtime'):
            result = super().run(label, argv)
            if label == 'preprocess':
                self.outputs['preprocess.stdout'] += ('\n' + '\n'.join(EXTRA_MARKERS) + '\n').encode()
                if self.failure == 'guardian_marker':
                    self.outputs['preprocess.stdout'] = self.outputs['preprocess.stdout'].replace(
                        b'(10003)', b'PR_SET_CHILD_SUBREAPER')
                result['stdout'] = self.read_output('preprocess.stdout', observer.MAX_BYTES)[1]
            return result
        self.calls.append((label, argv))
        stdout = b''
        if label == 'link':
            self.outputs['link.map'] = ('LOAD ' + str(self.root / 'probe.o') +
                                        '\nLOAD /fixture/link-input\n').encode()
            self.outputs['guardian'] = product_bytes()
            if self.failure == 'link_map':
                self.outputs['link.map'] = b'LOAD /proc/self/fd/0\n'
            if self.failure == 'product':
                self.outputs['guardian'] = product_bytes(kind=1)
            if self.failure == 'descriptor':
                self.outputs['guardian'] = product_bytes(machine=183)
        else:
            self.runtime_calls += 1
            product = self.read_output('guardian', observer.MAX_BYTES)[1]['identity']
            facts = failed_signal_facts() if self.failure == 'runtime_negative' else runtime_facts(argv[1], argv[2], product)
            if self.failure == 'runtime_negative':
                for identity in facts['identities_initial'].values():
                    identity['product_identity'] = dict(zip(('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'),
                                                           (product[0], product[1], *product[4:7])))
            if self.failure == 'runtime_forged':
                facts['adoptions'][-1]['observed_identity']['start_ticks'] += 1
            stdout = json.dumps(facts, sort_keys=True).encode()
            if self.failure == 'runtime_malformed':
                stdout = b'{incomplete'
            if self.failure == 'timeout_runtime':
                stdout = b''
            if self.drift == 'runtime_product':
                self.outputs['guardian'] += b' changed'
        self.outputs[label + '.stdout'], self.outputs[label + '.stderr'] = stdout, b''
        failed = self.failure in (label, 'timeout_' + label) or (label == 'runtime' and self.failure == 'runtime_negative')
        return {'label': label, 'argv': argv, 'status': 'failed' if failed else 'success',
                'returncode': None if self.failure == 'timeout_' + label else 1 if failed else 0,
                'timed_out': self.failure == 'timeout_' + label, 'direct_child_pid': 42,
                'kill_attempted': self.failure == 'timeout_' + label,
                'reap_completed': self.failure != 'timeout_' + label, 'kill_error': None, 'reap_error': None,
                'descendant_cleanup_verified': False,
                'stdout': self.read_output(label + '.stdout', observer.MAX_BYTES)[1],
                'stderr': self.read_output(label + '.stderr', observer.MAX_BYTES)[1]}


class ObserverFixture:
    """Fresh local file boundaries with only the guardian pipeline injected."""
    def __enter__(self):
        self.stack = ExitStack()
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.source = self.directory / 'frontier_v8_owned_c_guardian.py'
        self.source.write_bytes(b'# Explicitly injected new observer file fixture.\n')
        self.probe = self.directory / 'frontier_v8_owned_c_guardian.c'
        self.probe.write_bytes(b'/* Injected nonexecuted new C file fixture. */\n')
        for name in ('frontier_v8_containment_capability.py', 'frontier_v8_c_toolchain.py',
                     'frontier_v8_owned_c_selfcheck.py'):
            (self.directory / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
        with patch.object(observer, '__file__', str(self.source)):
            self.helper, self.utility, self.linkage = observer.load_utilities()
        self.bootstrap = self.directory / 'bootstrap'
        self.bootstrap.write_bytes(b'Injected bootstrap fixture bytes')
        self.attempt, self.request_path = self.directory / 'attempt', self.directory / 'request.json'
        self.request = {'schema_version': 1, 'scope': observer.SCOPE, 'nonce': secrets.token_hex(32),
            'case': 'guard_loss', 'observer_sha256': observer.digest(self.source.read_bytes()),
            'c_probe_sha256': observer.digest(self.probe.read_bytes()),
            'identity_helper_sha256': observer.HELPER_SHA, 'toolchain_sha256': observer.TOOLCHAIN_SHA,
            'linkage_sha256': observer.LINKAGE_SHA, 'attempt_directory': str(self.attempt),
            'host': {'node_alias': 'N1-1', 'hostname': 'fixture-host', 'boot_id': BOOT, 'uid': UID},
            'bootstrap': {'executable': str(self.bootstrap), 'sha256': observer.digest(self.bootstrap.read_bytes()),
                          'version': list(sys.version_info[:3])}}
        self.write_request()
        self.pipeline = Mock(return_value={**observer.AUTHORITY, 'status': 'success'})
        for target, attribute, value in (
                (observer, '__file__', str(self.source)),
                (observer, 'load_utilities', Mock(return_value=(self.helper, self.utility, self.linkage))),
                (observer, 'run_guardian', self.pipeline), (self.utility, 'CompilerBackend', Mock()),
                (observer.sys, 'flags', SimpleNamespace(isolated=1, no_site=1)),
                (observer.sys, 'dont_write_bytecode', True), (observer.sys, 'platform', 'linux'),
                (observer.sys, 'executable', str(self.bootstrap)),
                (observer.os, 'uname', Mock(return_value=SimpleNamespace(nodename='fixture-host'))),
                (self.helper, 'capture_self_identity', Mock(side_effect=own_identity))):
            self.stack.enter_context(patch.object(target, attribute, value))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def write_request(self):
        body = json.dumps(self.request, sort_keys=True).encode()
        self.request_path.write_bytes(body)
        self.request_sha = observer.digest(body)

    def observe(self):
        return observer.observe(str(self.request_path), self.request_sha)

    @property
    def marker(self):
        return self.attempt.with_name(self.attempt.name + '.consumed.json')


class OwnedCGuardianTests(unittest.TestCase):
    def parse(self, row, cmd=None, **changes):
        arguments = {'cpp_facts': CPP, 'expected_parent_pid': 7, 'expected_uid': UID,
                     'expected_boot_id': BOOT, 'case': row['case'], 'nonce': NONCE,
                     'product_identity': PRODUCT, **changes}
        return observer.parse_runtime(json.dumps(row, sort_keys=True).encode(), cmd or command(), **arguments)

    def test_both_synthetic_case_orders_and_correct_parent_waits(self):
        for case in ('guard_loss', 'coordinator_loss'):
            with self.subTest(case=case):
                row = runtime_facts(case)
                self.assertEqual(self.parse(row), row)
                inactive = 'G_H' if case == 'guard_loss' else 'C_H'
                self.assertIs(row['waits'][inactive]['attempted'], False)
                self.assertTrue(all(value is False for value in row['controls'].values()))

    def test_runtime_closed_json_duplicate_nonfinite_and_size_rejected(self):
        good = json.dumps(runtime_facts()).encode()
        for body in (b'', b'{incomplete', b'[]', good[:-1] + b',"case":"guard_loss"}',
                     good.replace(b'1000000000', b'NaN', 1), b' ' * 65537):
            with self.subTest(body=body[:32]), self.assertRaises((ValueError, UnicodeError)):
                observer.parse_runtime(body, command(), CPP, 7, UID, BOOT, 'guard_loss', NONCE, PRODUCT)
        row = runtime_facts()
        row['extra'] = False
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_case_nonce_scope_and_command_identity_must_match(self):
        for key, value in [('case', 'normal'), ('nonce', '2' * 64), ('scope', 'old_scope'), ('schema_version', True)]:
            row = runtime_facts()
            row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(row)
        for changes in ({'direct_child_pid': 99}, {'status': 'failed', 'returncode': 1},
                        {'timed_out': True}, {'reap_completed': False}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.parse(runtime_facts(), command(**changes))

    def test_initial_ancestry_uid_boot_product_and_birth_types_rejected(self):
        for key, value in [('ppid', 99), ('uid', UID + 1), ('euid', UID + 1),
                           ('boot_id', '11111111-1111-1111-1111-111111111111'),
                           ('start_ticks', True), ('start_ticks', 1 << 64), ('pid', -1)]:
            row = runtime_facts()
            row['identities_initial']['worker'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(row)
        with self.assertRaises(ValueError):
            self.parse(runtime_facts(), product_identity=[1, 99, *PRODUCT[2:]])

    def test_forged_adoption_invariants_and_parent_snapshots_rejected(self):
        for case in ('guard_loss', 'coordinator_loss'):
            for key, value in [('ppid', 44), ('start_ticks', 999), ('uid', UID + 1),
                               ('boot_id', '11111111-1111-1111-1111-111111111111'),
                               ('product_identity', {'dev': 9, 'ino': 2, 'size': PRODUCT[4], 'mtime_ns': 6, 'ctime_ns': 7})]:
                row = runtime_facts(case)
                row['adoptions'][-1]['observed_identity'][key] = value
                with self.subTest(case=case, key=key), self.assertRaises(ValueError):
                    self.parse(row)
        row = runtime_facts('coordinator_loss')
        row['identity_rechecks']['before_H_signal']['worker']['ppid'] = 42
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_missing_adoption_and_fresh_snapshot_of_dead_role_rejected(self):
        for case in ('guard_loss', 'coordinator_loss'):
            row = runtime_facts(case)
            row['adoptions'].pop()
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.parse(row)
        for case, phase, role in [('guard_loss', 'before_W_signal', 'guard'),
                                 ('coordinator_loss', 'before_H_signal', 'coordinator')]:
            row = runtime_facts(case)
            row['identity_rechecks'][phase][role] = copy.deepcopy(row['identities_initial'][role])
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.parse(row)

    def test_wrong_wait_owner_raw_status_or_foreign_pid_rejected(self):
        for case, tag in [('guard_loss', 'C_H'), ('coordinator_loss', 'G_H')]:
            for key, value in [('owner', 'worker'), ('result', 99), ('pid', 99),
                               ('raw_status', 0), ('signaled', False), ('exit_code', 0)]:
                row = runtime_facts(case)
                row['waits'][tag][key] = value
                with self.subTest(case=case, key=key), self.assertRaises(ValueError):
                    self.parse(row)
        row = runtime_facts('coordinator_loss')
        row['waits']['G_C'].update(raw_status=0, exit_code=0)
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_unattempted_wait_or_operation_cannot_invent_success(self):
        row = runtime_facts()
        row['waits']['G_H']['result'] = 44
        with self.assertRaises(ValueError):
            self.parse(row)
        row = runtime_facts()
        row['pidfds']['H_W']['explicit_close']['result'] = 0
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_four_explicit_closes_and_killed_owner_teardown_are_distinct(self):
        row = runtime_facts()
        self.assertEqual(sum(x['explicit_close']['attempted'] for x in row['pidfds'].values()), 4)
        for tag in ('G_C', 'G_H', 'G_W', 'C_H'):
            changed = copy.deepcopy(row)
            changed['pidfds'][tag]['immediate_F_GETFD']['errno'] = 0
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.parse(changed)
        row['pidfds']['H_W'].update(close_mode='explicit_close_then_immediate_EBADF',
                                  explicit_close=operation(), immediate_F_GETFD=operation(-1, error=errno.EBADF))
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_fd_zero_is_valid_but_reused_guardian_handle_is_not(self):
        row = runtime_facts()
        handle = row['pidfds']['G_W']
        handle['fd'] = handle['open']['result'] = handle['live_poll']['fd'] = 0
        row['polls']['G_W']['fd'] = row['signals'][1]['fd'] = 0
        self.assertEqual(self.parse(row), row)
        handle['fd'] = handle['open']['result'] = handle['live_poll']['fd'] = 3
        row['polls']['G_W']['fd'] = row['signals'][1]['fd'] = 3
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_anchor_pidfd_fdinfo_and_live_poll_required_before_arm(self):
        for tag in PAIRS:
            row = runtime_facts()
            row['pidfds'][tag]['fdinfo']['pid'] += 1
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.parse(row)
        row = runtime_facts()
        row['pidfds']['G_H']['live_poll']['observed_at_ns'] = row['times_ns']['H_signal']
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_missing_ack_duplicate_frame_and_physical_eof_order_rejected(self):
        for kind, role in [('ROLE_ARM_ACK', 'worker'), ('PIPE_EOF_FACT', 'worker'), ('ALL_ARM_ACK', 'coordinator')]:
            row = runtime_facts()
            row['packets'] = [x for x in row['packets'] if (x['kind'], x['role']) != (kind, role)]
            for i, packet in enumerate(row['packets']):
                packet['stage_ordinal'] = i + 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.parse(row)
        row = runtime_facts()
        row['packets'][5], row['packets'][6] = row['packets'][6], row['packets'][5]
        for i, packet in enumerate(row['packets']):
            packet['stage_ordinal'] = i + 1
        with self.assertRaises(ValueError):
            self.parse(row)
        row = runtime_facts()
        row['packets'].append(copy.deepcopy(row['packets'][0]))
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_pipe_eof_requires_nonterminal_child_poll_and_typed_live_fact(self):
        for tag in ('H_W_EOF', 'C_H_EOF'):
            row = runtime_facts()
            row['polls'][tag].update(result=1, revents=select.POLLIN)
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.parse(row)
        row = runtime_facts()
        next(packet for packet in row['packets'] if packet['kind'] == 'PIPE_EOF_FACT')[
            'parent_EOF_while_child_alive'] = 1
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_eof_forwarding_distinguishes_the_two_parent_origins(self):
        for case in ('guard_loss', 'coordinator_loss'):
            for role in ('worker', 'guard'):
                row = runtime_facts(case)
                packet = next(packet for packet in row['packets']
                              if (packet['kind'], packet['role']) == ('PIPE_EOF_FACT', role))
                self.assertIs(packet['forwarded_original_frame'], role == 'worker')
                packet['forwarded_original_frame'] = role != 'worker'
                with self.subTest(case=case, role=role), self.assertRaises(ValueError):
                    self.parse(row)

    def test_success_packet_ledger_cannot_include_an_error_frame(self):
        for case in ('guard_loss', 'coordinator_loss'):
            row = runtime_facts(case)
            packet = copy.deepcopy(row['packets'][-1])
            packet.update(kind='ERROR_FACT', stage_ordinal=len(row['packets']) + 1)
            row['packets'].append(packet)
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.parse(row)

    def test_product_timestamps_require_signed64_even_when_all_bindings_match(self):
        for case in ('guard_loss', 'coordinator_loss'):
            for index in (5, 6):
                product = PRODUCT.copy()
                product[index] = 1 << 63
                row = runtime_facts(case, product=product)
                with self.subTest(case=case, stat_index=index), self.assertRaises(ValueError):
                    self.parse(row, product_identity=product)

    def test_required_guardian_commands_have_closed_edges_and_logical_order(self):
        for case, kind in [('guard_loss', 'ARM'), ('coordinator_loss', 'ARM'),
                           ('guard_loss', 'COORDINATOR_FINISH'), ('coordinator_loss', 'COORDINATOR_EXIT23')]:
            row = runtime_facts(case)
            row['packets'] = [packet for packet in row['packets'] if packet['kind'] != kind]
            for i, packet in enumerate(row['packets']):
                packet['stage_ordinal'] = i + 1
            with self.subTest(case=case, missing=kind), self.assertRaises(ValueError):
                self.parse(row)
        for kind, role, key, value in [
                ('ARM', 'guardian', 'edge', 'G_from_C'),
                ('ARM', 'guardian', 'role', 'coordinator'),
                ('ARM', 'guardian', 'forwarded_original_frame', True),
                ('ROLE_READY', 'worker', 'edge', 'C_from_G'),
                ('ROLE_READY', 'worker', 'forwarded_original_frame', False),
                ('ROLE_ARM_ACK', 'guard', 'forwarded_original_frame', False),
                ('ROLE_READY', 'coordinator', 'forwarded_original_frame', True)]:
            row = runtime_facts()
            next(packet for packet in row['packets'] if (packet['kind'], packet['role']) == (kind, role))[key] = value
            with self.subTest(kind=kind, role=role, key=key), self.assertRaises(ValueError):
                self.parse(row)
        for case, first, second in [
                ('guard_loss', ('ROLE_READY', 'coordinator'), ('ARM', 'guardian')),
                ('guard_loss', ('GUARD_WAIT_FACT', 'coordinator'), ('COORDINATOR_FINISH', 'guardian')),
                ('coordinator_loss', ('COORDINATOR_EXIT23', 'guardian'), ('COORDINATOR_EXIT_ACK', 'coordinator'))]:
            row = runtime_facts(case)
            positions = [next(i for i, packet in enumerate(row['packets'])
                              if (packet['kind'], packet['role']) == pair) for pair in (first, second)]
            left, right = positions
            row['packets'][left], row['packets'][right] = row['packets'][right], row['packets'][left]
            for i, packet in enumerate(row['packets']):
                packet['stage_ordinal'] = i + 1
            with self.subTest(case=case, first=first), self.assertRaises(ValueError):
                self.parse(row)

    def test_frame_size_nonce_partial_and_other_case_command_rejected(self):
        for key, value in [('bytes', 513), ('nonce', '2' * 64), ('complete', False), ('shared_t0', 0)]:
            row = runtime_facts()
            row['packets'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(row)
        row = runtime_facts()
        row['packets'][-1]['kind'] = 'COORDINATOR_EXIT_ACK'
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_loss_before_arm_and_case_timestamp_contradictions_rejected(self):
        for case, event in [('guard_loss', 'H_signal'), ('coordinator_loss', 'C_exit')]:
            row = runtime_facts(case)
            row['times_ns'][event] = row['times_ns']['arm_sent'] - 1
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.parse(row)
        row = runtime_facts()
        row['times_ns']['C_exit'] = row['times_ns']['W_reaped'] - 1
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_deadline_epoch_extension_overflow_and_extra_field_rejected(self):
        for key, value in [('cleanup_ns', 9000000001), ('child_self_expiry_ns', 16000000000),
                           ('t0_ns', 1 << 63), ('work_ns', True)]:
            row = runtime_facts()
            row['deadlines'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(row)
        row = runtime_facts()
        row['deadlines']['extra_cleanup_ns'] = 17000000000
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_exact_two_owned_signal_attempts_no_flags_or_budget_reset(self):
        for key, value in [('flags', 1), ('attempts', 2), ('fd', 99), ('owner', 'coordinator'),
                           ('original_handle_tag', 'G_C'), ('attempt_budget_consumed_before_call', False)]:
            row = runtime_facts()
            row['signals'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(row)
        row = runtime_facts()
        row['signals'].append(copy.deepcopy(row['signals'][0]))
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_subreaper_initial_child_and_terminal_reset_must_be_observed(self):
        for key, value in [('initial_get', operation(value=1)),
                           ('terminal_set_disabled', operation(result=-1, error=errno.EINVAL)),
                           ('terminal_verify_disabled_get', operation(value=1))]:
            row = runtime_facts()
            row['subreaper'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(row)
        row = runtime_facts()
        row['child_subreaper_get']['guard']['value'] = 1
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_model_resource_and_recovery_flags_never_promoted(self):
        for key in runtime_facts()['controls']:
            row = runtime_facts()
            row['controls'][key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(row)

    def test_handled_eintr_esrch_preserve_consumed_h_attempt_and_disabled_w(self):
        for error in (errno.EINTR, errno.ESRCH):
            row = failed_signal_facts(error)
            with self.subTest(error=error):
                self.assertEqual(self.parse(row, command(status='failed', returncode=1)), row)
                self.assertEqual(row['signals'][1]['attempts'], 0)
                self.assertEqual(row['negative_state']['negative_cleanup_signals'], [])

    def test_negative_state_cannot_signal_after_first_error_or_reset_unknown_roles(self):
        row = failed_signal_facts()
        row['signals'][1].update(attempts=1, result=0, errno=0,
            observed_at_ns=row['negative_state']['first_error_at_ns'] + 1,
            attempt_budget_consumed_before_call=True)
        with self.assertRaises(ValueError):
            self.parse(row, command(status='failed', returncode=1))
        row = failed_signal_facts()
        row['negative_state']['terminal_reset_gate_complete'] = True
        row['subreaper']['terminal_set_disabled'] = operation()
        row['subreaper']['terminal_verify_disabled_get'] = operation(value=0)
        with self.assertRaises(ValueError):
            self.parse(row, command(status='failed', returncode=1))

    def test_negative_attempt_budget_and_disabled_worker_facts_cannot_be_forged(self):
        for tag, key in [(0, 'attempt_budget_consumed_before_call'), (1, 'later_planned_actions_disabled')]:
            row = failed_signal_facts()
            row['signals'][tag][key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(row, command(status='failed', returncode=1))
        row = failed_signal_facts()
        row['negative_state']['negative_cleanup_signals'] = [{'target': 'worker'}]
        with self.assertRaises(ValueError):
            self.parse(row, command(status='failed', returncode=1))

    def test_missing_error_cutoff_or_failed_guard_with_late_cutoff_cannot_enable_worker(self):
        row = failed_signal_facts()
        row['negative_state']['first_error_at_ns'] = None
        with self.assertRaises(ValueError):
            self.parse(row, command(status='failed', returncode=1))
        for result, error in [(-1, errno.EINTR), (0, errno.ESRCH)]:
            row = runtime_facts()
            row['status'] = 'failed'
            row['error'] = {'stage': 'h_signal', 'role': 'guardian', 'operation': 'pidfd_send_signal',
                            'errno': error, 'bounded_detail': None}
            row['negative_state'].update(entered=True, first_error_stage='h_signal',
                first_error_operation='pidfd_send_signal', first_error_at_ns=row['times_ns']['final'],
                later_planned_signals_disabled=True, terminal_reset_gate_complete=False)
            row['subreaper']['terminal_set_disabled'] = operation(attempted=False)
            row['subreaper']['terminal_verify_disabled_get'] = operation(attempted=False)
            row['signals'][0].update(result=result, errno=error)
            for planned in row['signals']:
                planned['later_planned_actions_disabled'] = True
            with self.subTest(result=result, error=error), self.assertRaises(ValueError):
                self.parse(row, command(status='failed', returncode=1))

    def test_terminal_reset_failure_preserves_actual_negative_calls(self):
        for case in ('guard_loss', 'coordinator_loss'):
            for reset_operation in ('prctl_set_disabled', 'prctl_get_disabled'):
                row = failed_reset_facts(case, reset_operation)
                with self.subTest(case=case, operation=reset_operation):
                    observed = self.parse(row, command(status='failed', returncode=1))
                    self.assertEqual(observed, row)
                    self.assertEqual(observed['status'], 'failed')
                    field = 'terminal_set_disabled' if reset_operation == 'prctl_set_disabled' else 'terminal_verify_disabled_get'
                    self.assertEqual(observed['subreaper'][field]['result'], -1)
                    self.assertEqual(observed['subreaper'][field]['errno'], errno.EINVAL)
        row = failed_reset_facts(reset_operation='prctl_get_disabled')
        row['subreaper']['terminal_verify_disabled_get'] = operation(value=1)
        row['error']['errno'] = 0
        self.assertEqual(self.parse(row, command(status='failed', returncode=1)), row)

    def test_reset_bearing_failure_cannot_skip_complete_prereset_case_predicates(self):
        for case in ('guard_loss', 'coordinator_loss'):
            for reset_operation in ('prctl_set_disabled', 'prctl_get_disabled'):
                for failure in ('initial_get', 'set_enabled', 'verify_enabled_get', 'child_get',
                                'C_H_close', 'adoption', 'packet', 'deadline', 'fresh_snapshot', 'EOF_live'):
                    row = failed_reset_facts(case, reset_operation)
                    if failure in ('initial_get', 'set_enabled', 'verify_enabled_get'):
                        row['subreaper'][failure] = operation(attempted=False)
                    elif failure == 'child_get':
                        row['child_subreaper_get']['guard'] = operation(attempted=False)
                    elif failure == 'C_H_close':
                        row['pidfds']['C_H'].update(close_mode='unobserved',
                            explicit_close=operation(attempted=False), immediate_F_GETFD=operation(attempted=False))
                    elif failure == 'adoption':
                        row['adoptions'].pop()
                    elif failure == 'packet':
                        row['packets'] = [packet for packet in row['packets'] if packet['kind'] != 'ALL_ARM_ACK']
                        for i, packet in enumerate(row['packets']):
                            packet['stage_ordinal'] = i + 1
                    elif failure == 'deadline':
                        row['deadlines']['cleanup_ns'] += 1
                    elif failure == 'fresh_snapshot':
                        row['identity_rechecks']['before_W_signal']['worker']['ppid'] = 44
                    else:
                        row['polls']['H_W_EOF'].update(result=1, revents=select.POLLIN)
                    with self.subTest(case=case, operation=reset_operation, failure=failure), self.assertRaises(ValueError):
                        self.parse(row, command(status='failed', returncode=1))
        row = failed_reset_facts()
        row['error'].update(stage='other_error', operation='other_operation')
        row['negative_state'].update(first_error_stage='other_error', first_error_operation='other_operation')
        with self.assertRaises(ValueError):
            self.parse(row, command(status='failed', returncode=1))

    def test_late_adoption_remains_negative_and_cannot_reenable_planned_signal(self):
        row = failed_signal_facts()
        adoption = runtime_facts()['adoptions'][0]
        adoption['observed_at_ns'] = row['negative_state']['first_error_at_ns'] + 1
        row['adoptions'] = [adoption]
        row['negative_state']['known_adopted'] = ['worker']
        result = self.parse(row, command(status='failed', returncode=1))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['signals'][1]['attempts'], 0)
        row['signals'][1].update(attempts=1, result=0, errno=0, observed_at_ns=adoption['observed_at_ns'],
                                  attempt_budget_consumed_before_call=True)
        with self.assertRaises(ValueError):
            self.parse(row, command(status='failed', returncode=1))

    def test_additional_cpp_markers_are_opaque_bounded_expressions(self):
        body = ('\n'.join(EXTRA_MARKERS) + '\n').encode()
        self.assertEqual(observer.parse_guardian_cpp_markers(body),
                         {key: CPP[key] for key in CPP if key != 'SYS_pidfd_open_expression' and key.endswith('_expression')})
        for changed in (body + EXTRA_MARKERS[0].encode(), body.replace(b'(10003)', b'PR_SET_CHILD_SUBREAPER'),
                        body.replace(b'(10003)', b'__import__("os")'), body.replace(b'(10003)', b'"10003"')):
            with self.subTest(body=changed[:48]), self.assertRaises(ValueError):
                observer.parse_guardian_cpp_markers(changed)

    def pipeline(self, backend, case='guard_loss', precheck=None):
        helper, utility, linkage = observer.load_utilities()
        return observer.run_guardian(Path('/owned/new_guardian.c'), backend, utility, linkage,
                                     case, NONCE, 7, UID, BOOT, precheck)

    def test_synthetic_pipeline_runs_only_new_product_once_per_case(self):
        for case in ('guard_loss', 'coordinator_loss'):
            backend = FakeGuardianBackend(Path('/fixture/output'), '/owned/new_guardian.c')
            result = self.pipeline(backend, case)
            with self.subTest(case=case):
                self.assertEqual(result['status'], 'success')
                self.assertEqual(backend.runtime_calls, 1)
                self.assertEqual([x[0] for x in backend.calls],
                                 ['resolve', 'version', 'dependencies', 'preprocess', 'object', 'link', 'runtime'])
                self.assertEqual(result['runtime_attempts'], 1)
                self.assertTrue(all(result[key] is False for key in observer.AUTHORITY))

    def test_compile_link_marker_failure_never_runs_product(self):
        for failure in ('object', 'link', 'guardian_marker', 'link_map', 'product', 'descriptor'):
            backend = FakeGuardianBackend(Path('/fixture/output'), '/owned/new_guardian.c', failure=failure)
            with self.subTest(failure=failure):
                self.assertEqual(self.pipeline(backend)['status'], 'failed')
                self.assertEqual(backend.runtime_calls, 0)

    def test_pipeline_drift_precheck_and_runtime_failure_have_no_retry(self):
        for drift in ('header', 'driver', 'output', 'interpreter', 'link_input'):
            backend = FakeGuardianBackend(Path('/fixture/output'), '/owned/new_guardian.c', drift=drift)
            with self.subTest(drift=drift):
                self.assertEqual(self.pipeline(backend)['status'], 'failed')
                self.assertEqual(backend.runtime_calls, 0)
        backend = FakeGuardianBackend(Path('/fixture/output'), '/owned/new_guardian.c')
        precheck = Mock(side_effect=ValueError('fixture prevalidation failed'))
        self.assertEqual(self.pipeline(backend, precheck=precheck)['status'], 'failed')
        self.assertEqual(backend.calls, [])
        for failure in ('runtime_forged', 'runtime_malformed', 'timeout_runtime'):
            backend = FakeGuardianBackend(Path('/fixture/output'), '/owned/new_guardian.c', failure=failure)
            with self.subTest(failure=failure):
                self.assertEqual(self.pipeline(backend)['status'], 'failed')
                self.assertEqual(backend.runtime_calls, 1)

    def test_pipeline_preserves_handled_negative_and_product_drift(self):
        backend = FakeGuardianBackend(Path('/fixture/output'), '/owned/new_guardian.c', failure='runtime_negative')
        result = self.pipeline(backend)
        self.assertEqual(result['status'], 'failed')
        self.assertIs(result['runtime_returned_complete_facts'], True)
        self.assertEqual(result['runtime_report']['error']['stage'], 'h_signal')
        self.assertEqual(backend.runtime_calls, 1)
        backend = FakeGuardianBackend(Path('/fixture/output'), '/owned/new_guardian.c', drift='runtime_product')
        self.assertEqual(self.pipeline(backend)['status'], 'failed')
        self.assertEqual(backend.runtime_calls, 1)

    def test_observer_fresh_consumption_postvalidation_and_reuse_refusal(self):
        with ObserverFixture() as fixture:
            result = fixture.observe()
            self.assertEqual(result['status'], 'owned_C_guardian_adoption_observed')
            self.assertIs(result['input_and_self_identity_postvalidation_passed'], True)
            self.assertIs(result['captured_utilities']['old_observe_or_CLI_called'], False)
            self.assertTrue(fixture.marker.is_file())
            self.assertTrue(all(result[key] is False for key in observer.AUTHORITY))
            with self.assertRaises((ValueError, FileExistsError)):
                fixture.observe()
            fixture.pipeline.assert_called_once()

    def test_observer_bad_request_bootstrap_or_overlap_never_consumes(self):
        for failure in ('request_sha', 'case', 'scope', 'bootstrap', 'overlap', 'uid_bool'):
            with ObserverFixture() as fixture, self.subTest(failure=failure):
                if failure == 'request_sha':
                    fixture.request_sha = '0' * 64
                elif failure == 'bootstrap':
                    fixture.bootstrap.write_bytes(b'changed bootstrap')
                else:
                    if failure == 'case':
                        fixture.request['case'] = 'controller_loss'
                    elif failure == 'scope':
                        fixture.request['scope'] = 'old_scope'
                    elif failure == 'overlap':
                        fixture.request['attempt_directory'] = str(fixture.probe)
                    else:
                        fixture.request['host']['uid'] = True
                    fixture.write_request()
                with self.assertRaises(ValueError):
                    fixture.observe()
                fixture.pipeline.assert_not_called()
                self.assertFalse(fixture.marker.exists())

    def test_observer_postvalidation_drift_stays_consumed_and_negative(self):
        for failure in ('request', 'marker', 'bootstrap'):
            with ObserverFixture() as fixture, self.subTest(failure=failure):
                def drift(*args):
                    path = {'request': fixture.request_path, 'marker': fixture.marker,
                            'bootstrap': fixture.bootstrap}[failure]
                    path.write_bytes(path.read_bytes() + b' changed')
                    return {**observer.AUTHORITY, 'status': 'success'}
                fixture.pipeline.side_effect = drift
                result = fixture.observe()
                self.assertEqual(result['status'], 'failed')
                self.assertIs(result['input_and_self_identity_postvalidation_passed'], False)
                self.assertTrue(fixture.marker.exists())
                fixture.pipeline.assert_called_once()
                with self.assertRaises((ValueError, FileExistsError)):
                    fixture.observe()
                fixture.pipeline.assert_called_once()

    def test_execute_and_captured_utility_cache_are_refused(self):
        with self.assertRaises(ValueError), patch.object(observer, 'observe') as observe:
            observer.main(['--execute'])
        observe.assert_not_called()
        with patch.dict(sys.modules, {'frontier_v8_guardian_identity_helper': object()}), self.assertRaises(ValueError):
            observer.load_utilities()

    @unittest.skipUnless(sys.platform == 'linux', 'Actual fresh guard-loss adoption requires Linux')
    def test_real_linux_guard_loss_adoption_and_owned_reaps(self):
        self.real_case('guard_loss')

    @unittest.skipUnless(sys.platform == 'linux', 'Actual fresh coordinator-loss adoption requires Linux')
    def test_real_linux_coordinator_loss_adoption_and_owned_reaps(self):
        self.real_case('coordinator_loss')

    def real_case(self, case):
        helper, utility, linkage = observer.load_utilities()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            (directory / 'tmp').mkdir(mode=0o700)
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                result = observer.run_guardian(ROOT / 'scripts/frontier_v8_owned_c_guardian.c',
                    utility.CompilerBackend(helper, directory, fd), utility, linkage, case,
                    secrets.token_hex(32), os.getpid(), os.getuid(), helper.capture_self_identity()['boot_id'])
            finally:
                os.close(fd)
            self.assertEqual(result['status'], 'success', result.get('error'))
            self.assertEqual(result['link_attempts'], 1)
            self.assertEqual(result['runtime_attempts'], 1)
            self.assertIs(result['runtime_returned_complete_facts'], True)
            self.assertIs(result[observer.SUCCESS[0 if case == 'guard_loss' else 1]], True)
            self.assertTrue(all(result[key] is False for key in observer.AUTHORITY))
            facts = result['runtime_report']
            self.assertEqual([row['target'] for row in facts['adoptions']],
                             ['worker'] if case == 'guard_loss' else ['guard', 'worker'])
            self.assertEqual(sum(row['explicit_close']['attempted'] for row in facts['pidfds'].values()), 4)
            self.assertEqual([row['original_handle_tag'] for row in facts['signals']], ['G_H', 'G_W'])
            self.assertEqual([row['attempts'] for row in facts['signals']], [1, 1])
            self.assertEqual(facts['waits']['G_C']['raw_status'], 0 if case == 'guard_loss' else 5888)
            self.assertEqual(facts['waits']['G_W']['raw_status'], int(signal.SIGKILL))
            self.assertIs(facts['negative_state']['terminal_reset_gate_complete'], True)


if __name__ == '__main__':
    unittest.main()
