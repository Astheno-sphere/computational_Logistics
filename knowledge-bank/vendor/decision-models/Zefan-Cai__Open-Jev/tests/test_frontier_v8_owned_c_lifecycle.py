"""Fixed owned-C fixture parsing and lifecycle cases; no production authority."""
from contextlib import ExitStack
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import secrets
import select
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_owned_c_lifecycle as observer
from tests.test_frontier_v8_c_toolchain import FakeCompilerBackend, own_identity
from tests.test_frontier_v8_owned_c_selfcheck import product_bytes


ROOT = Path(__file__).resolve().parents[1]
BOOT = '00000000-0000-0000-0000-000000000001'
NONCE = 'a' * 64  # Synthetic parser/backend fixture token, never a host request.
CPP = {'SYS_pidfd_open_expression': '((1 << 8) + 9L)', 'target_int_bytes': 4,
       'target_long_bytes': 8, 'target_pointer_bytes': 8, 'target_char_bits': 8,
       'target_byte_order': 1234}
PRODUCT = [1, 2, 0o100700, os.getuid(), 128, 6, 7]
NO_SIGNAL = {'attempts': 0, 'fd': None, 'number': None, 'flags': None, 'result': None, 'errno': None}


def command(**changes):
    return {'direct_child_pid': 42, 'status': 'success', 'returncode': 0,
            'timed_out': False, 'reap_completed': True, **changes}


def runtime_facts(case='normal', nonce=NONCE, product=PRODUCT):
    """Synthetic authoritative-shaped facts, without processes or kernel operations."""
    ids = {role: {'pid': pid, 'ppid': parent, 'uid': os.getuid(), 'euid': os.getuid(),
        'start_ticks': 100 + pid, 'boot_id': BOOT} for role, pid, parent in
        (('coordinator', 42, 7), ('controller', 43, 42), ('guard', 44, 42), ('worker', 45, 44))}
    headers = {'pidfd_open': 265, 'pidfd_send_signal': 266, 'sigkill': int(signal.SIGKILL),
        'sigpipe': int(signal.SIGPIPE), 'pollin': select.POLLIN, 'pollnval': select.POLLNVAL,
        'ebadf': errno.EBADF, 'int_bytes': 4, 'long_bytes': 8, 'pointer_bytes': 8,
        'char_bits': 8, 'byte_order': 1234, 'packet_magic': 0x4a45564c,
        'identity_packet_bytes': 64, 'command_packet_bytes': 64, 'terminal_packet_bytes': 64,
        'controller_loss_exit_code': 23}
    senders = {'controller_ready': 'controller', 'guard_ready': 'guard', 'guard_start': 'coordinator',
        'worker_ready': 'worker', 'guard_worker_ready': 'guard', 'case_arm': 'coordinator',
        'case_ack': 'guard', 'controller_quit': 'coordinator', 'worker_quit': 'guard',
        'guard_terminal': 'guard'}
    packets = {kind: {'bytes': 64, 'magic': headers['packet_magic'], 'kind': kind, 'role': role,
        'nonce': nonce, 'case': case} for kind, role in senders.items()}
    if case == 'controller_loss':
        packets['worker_quit'] = None
    handles = {}
    for key, fd, role in (('coordinator_controller', 10, 'controller'), ('coordinator_guard', 11, 'guard'),
                         ('guard_controller', 10, 'controller'), ('guard_worker', 0, 'worker')):
        inherited = key == 'guard_controller'
        handles[key] = {'acquisition': 'inherited' if inherited else 'open', 'fd': fd,
            'open_result': None if inherited else fd, 'open_errno': None if inherited else 0,
            'fdinfo_pid': ids[role]['pid'], 'close_calls': 1, 'close_result': 0, 'close_errno': 0,
            'ebadf_result': -1, 'ebadf_errno': errno.EBADF}
    polls = {}
    for key, handle in (('controller_alive_before_arm', 'guard_controller'),
            ('controller_exit', 'coordinator_controller'), ('guard_controller_exit', 'guard_controller'),
            ('worker_exit', 'guard_worker'), ('guard_exit', 'coordinator_guard')):
        polls[key] = {'calls': 1, 'fd': handles[handle]['fd'], 'events': select.POLLIN,
            'result': 0 if key == 'controller_alive_before_arm' else 1,
            'revents': 0 if key == 'controller_alive_before_arm' else select.POLLIN, 'errno': 0}
    waits = {}
    for role in ('controller', 'guard', 'worker'):
        killed = role == 'worker' and case == 'controller_loss'
        code = 23 if role == 'controller' and case == 'controller_loss' else 0
        waits[role] = {'owner': 'guard' if role == 'worker' else 'coordinator', 'calls': 1,
            'pid': ids[role]['pid'], 'result': ids[role]['pid'],
            'status': int(signal.SIGKILL) if killed else code << 8, 'errno': 0,
            'exited': not killed, 'exit_code': None if killed else code,
            'signaled': killed, 'term_signal': int(signal.SIGKILL) if killed else None}
    def closed(fd, kind):
        return {'fd': fd, 'kind': kind, 'result': 0, 'errno': 0,
                'ebadf_result': -1, 'ebadf_errno': errno.EBADF}
    t0 = 10_000_000_000
    deadlines = {'t0_ns': t0, 'work_ns': t0 + 5_000_000_000,
        'cleanup_ns': t0 + 8_000_000_000, 'terminal_ns': t0 + 10_000_000_000,
        'worker_ns': t0 + 12_000_000_000, 'total_ns': t0 + 14_000_000_000,
        'guard_arm_ns': t0 + 100, 'guard_ack_ns': t0 + 200, 'controller_command_ns': t0 + 300,
        'controller_exit_ns': t0 + 400, 'worker_signal_ns': t0 + 500 if case == 'controller_loss' else None,
        'worker_exit_ns': t0 + 600, 'worker_reaped_ns': t0 + 700,
        'guard_terminal_ns': t0 + 800, 'coordinator_final_ns': t0 + 900}
    return {'schema_version': 1, 'scope': observer.SCOPE, 'status': 'success', 'case': case, 'nonce': nonce,
        'error': {'stage': 'none', 'errno': 0}, 'headers': headers, 'identities': ids,
        'identity_rechecks': {'guard_before_arm': copy.deepcopy(ids['guard']),
            'worker_before_arm': copy.deepcopy(ids['worker']),
            'guard_before_signal': copy.deepcopy(ids['guard']) if case == 'controller_loss' else None,
            'worker_before_signal': copy.deepcopy(ids['worker']) if case == 'controller_loss' else None},
        'product_identity': list(product), 'product_rechecks': {'before_arm': list(product),
            'before_signal': list(product) if case == 'controller_loss' else None},
        'handshakes': packets, 'pidfds': handles, 'polls': polls, 'waits': waits,
        'worker_signal': {'attempts': 1, 'fd': 0, 'number': int(signal.SIGKILL), 'flags': 0,
                          'result': 0, 'errno': 0} if case == 'controller_loss' else copy.deepcopy(NO_SIGNAL),
        'coordinator_cleanup_signals': {'controller': copy.deepcopy(NO_SIGNAL), 'guard': copy.deepcopy(NO_SIGNAL)},
        'inherited_closes': {'controller': [closed(1, 'stdout')],
            'guard': [closed(12, 'controller_command_write'), closed(0, 'stdin')],
            'worker': [closed(10, 'controller_pidfd'), closed(13, 'guard_report_write'),
                closed(14, 'guard_command_read'), closed(0, 'worker_ready_read'), closed(7, 'worker_command_write')]},
        'deadlines': deadlines, 'self_sigpipe_ignore': {'result': 0, 'errno': 0}}


class FakeLifecycleBackend(FakeCompilerBackend):
    """New fixed link/runtime output ledger, with no compiler or process launch."""
    def __init__(self, root, source, *, failure=None, drift=None):
        super().__init__(root, source, failure=failure, drift=drift)
        self.runtime_calls = 0

    def snapshot(self, path, limit):
        row = super().snapshot(path, limit)
        if self.drift == 'interpreter' and str(path) == '/fixture/loader' and self.snapshots[str(path)] > 1:
            row['sha256'] = '0' * 64
        return row

    def run(self, label, argv):
        if label not in ('link', 'runtime'):
            return super().run(label, argv)
        self.calls.append((label, argv))
        stdout = b''
        if label == 'link':
            self.outputs['link.map'] = ('LOAD ' + str(self.root / 'probe.o') + '\nLOAD /fixture/link-input\n').encode()
            self.outputs['lifecycle'] = product_bytes()
            if self.failure == 'link_map':
                self.outputs['link.map'] = b'LOAD /proc/self/fd/0\n'
        else:
            self.runtime_calls += 1
            product = self.read_output('lifecycle', observer.MAX_BYTES)[1]['identity']
            row = runtime_facts(argv[1], argv[2], product)
            if self.failure == 'runtime_negative':
                row.update(status='failed', error={'stage': 'controller_early_exit', 'errno': 0})
                row['waits']['worker'] = row['worker_signal'] = None
                row['pidfds']['guard_worker'] = None
            if self.failure == 'runtime_foreign':
                row['identities']['worker']['ppid'] += 1
            stdout = json.dumps(row, sort_keys=True).encode()
            if self.failure == 'runtime_malformed':
                stdout = b'{partial'
            if self.failure == 'timeout_runtime':
                stdout = b''
            if self.drift == 'runtime_product':
                self.outputs['lifecycle'] += b' changed'
        self.outputs[label + '.stdout'], self.outputs[label + '.stderr'] = stdout, b''
        timeout = self.failure == 'timeout_' + label
        failed = self.failure == label or timeout or (label == 'runtime' and self.failure == 'runtime_negative')
        return {'label': label, 'argv': argv, 'status': 'failed' if failed else 'success',
            'returncode': None if timeout else 1 if failed else 0, 'timed_out': timeout,
            'direct_child_pid': 42, 'kill_attempted': timeout, 'reap_completed': not timeout,
            'kill_error': None, 'reap_error': None, 'descendant_cleanup_verified': False,
            'stdout': self.read_output(label + '.stdout', observer.MAX_BYTES)[1],
            'stderr': self.read_output(label + '.stderr', observer.MAX_BYTES)[1]}


class ObserverFixture:
    """Fresh owned file boundary and explicitly injected lifecycle result."""
    def __enter__(self):
        self.stack = ExitStack()
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.source = self.directory / 'observer.py'
        self.source.write_bytes(b'# Injected lifecycle observer file only.\n')
        for name in ('frontier_v8_owned_c_lifecycle.c', 'frontier_v8_containment_capability.py',
                     'frontier_v8_c_toolchain.py', 'frontier_v8_owned_c_selfcheck.py'):
            (self.directory / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
        self.probe = self.directory / 'frontier_v8_owned_c_lifecycle.c'
        self.helper_path = self.directory / 'frontier_v8_containment_capability.py'
        self.utility_path = self.directory / 'frontier_v8_c_toolchain.py'
        self.linkage_path = self.directory / 'frontier_v8_owned_c_selfcheck.py'
        self.bootstrap = self.directory / 'bootstrap'
        self.bootstrap.write_bytes(b'Injected bootstrap bytes')
        with patch.object(observer, '__file__', str(self.source)):
            self.helper, self.utility, self.linkage = observer.load_utilities()
        self.attempt, self.request_path = self.directory / 'attempt', self.directory / 'request.json'
        self.request = {'schema_version': 1, 'scope': observer.SCOPE, 'nonce': secrets.token_hex(32),
            'case': 'normal', 'observer_sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(),
            'c_probe_sha256': hashlib.sha256(self.probe.read_bytes()).hexdigest(),
            'identity_helper_sha256': observer.HELPER_SHA, 'toolchain_sha256': observer.TOOLCHAIN_SHA,
            'linkage_sha256': observer.LINKAGE_SHA, 'attempt_directory': str(self.attempt),
            'host': {'node_alias': 'N1-1', 'hostname': 'fixture-host', 'boot_id': BOOT, 'uid': os.getuid()},
            'bootstrap': {'executable': str(self.bootstrap),
                'sha256': hashlib.sha256(self.bootstrap.read_bytes()).hexdigest(), 'version': list(sys.version_info[:3])}}
        self.write_request()
        self.pipeline = Mock(return_value={**observer.AUTHORITY, 'status': 'success',
            observer.SUCCESS[0]: True, observer.SUCCESS[1]: False})
        for target, key, value in ((observer, '__file__', str(self.source)),
                (observer, 'load_utilities', Mock(return_value=(self.helper, self.utility, self.linkage))),
                (observer, 'run_lifecycle', self.pipeline), (self.utility, 'CompilerBackend', Mock()),
                (observer.sys, 'flags', SimpleNamespace(isolated=1, no_site=1)),
                (observer.sys, 'dont_write_bytecode', True), (observer.sys, 'platform', 'linux'),
                (observer.sys, 'executable', str(self.bootstrap)),
                (observer.os, 'uname', Mock(return_value=SimpleNamespace(nodename='fixture-host'))),
                (self.helper, 'capture_self_identity', Mock(side_effect=lambda: own_identity()))):
            self.stack.enter_context(patch.object(target, key, value))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def write_request(self):
        body = json.dumps(self.request, sort_keys=True).encode()
        self.request_path.write_bytes(body)
        self.request_sha = hashlib.sha256(body).hexdigest()

    def observe(self):
        return observer.observe(str(self.request_path), self.request_sha)

    @property
    def marker(self):
        return self.attempt.with_name(self.attempt.name + '.consumed.json')


class OwnedCLifecycleTests(unittest.TestCase):
    def parse(self, row, cmd=None):
        return observer.parse_runtime(json.dumps(row, sort_keys=True).encode(), cmd or command(),
            CPP, 7, os.getuid(), BOOT, row['case'], NONCE, PRODUCT)

    def assert_no_authority(self, row):
        for key in observer.AUTHORITY:
            self.assertIs(row[key], False)

    def test_normal_and_loss_facts_require_distinct_raw_wait_and_signal_chains(self):
        for case in ('normal', 'controller_loss'):
            with self.subTest(case=case):
                row = runtime_facts(case)
                self.assertEqual(self.parse(row), row)

    def test_foreign_pid_parent_uid_boot_birth_or_duplicate_fork_identity_is_refused(self):
        for role, key, value in (('coordinator', 'pid', 99), ('coordinator', 'ppid', 8),
                ('controller', 'ppid', 7), ('worker', 'ppid', 42), ('guard', 'uid', os.getuid() + 1),
                ('worker', 'boot_id', 'foreign'), ('worker', 'start_ticks', 0), ('guard', 'pid', 43)):
            row = runtime_facts()
            row['identities'][role][key] = value
            with self.subTest(role=role, key=key), self.assertRaises(ValueError):
                self.parse(row)

    def test_identity_and_product_recheck_drift_cannot_become_success(self):
        for case in ('normal', 'controller_loss'):
            for change in ('birth', 'product', 'missing'):
                row = runtime_facts(case)
                if change == 'birth':
                    row['identity_rechecks']['worker_before_arm']['start_ticks'] += 1
                elif change == 'product':
                    row['product_rechecks']['before_arm'][6] += 1
                else:
                    row['identity_rechecks']['guard_before_arm'] = None
                with self.subTest(case=case, change=change), self.assertRaises(ValueError):
                    self.parse(row)

    def test_missing_partial_wrong_arm_ack_nonce_role_or_case_packet_is_refused(self):
        for key in ('guard_start', 'guard_worker_ready', 'case_arm', 'case_ack', 'guard_terminal'):
            for change in ('missing', 'bytes', 'nonce', 'role', 'case'):
                row = runtime_facts()
                if change == 'missing':
                    row['handshakes'][key] = None
                else:
                    row['handshakes'][key][change] = {'bytes': 1, 'nonce': 'b' * 64,
                        'role': 'worker', 'case': 'controller_loss'}[change]
                with self.subTest(key=key, change=change), self.assertRaises(ValueError):
                    self.parse(row)

    def test_wrong_owned_pidfd_fdinfo_inheritance_or_twice_close_is_refused(self):
        for key, field, value in (('guard_controller', 'fd', 99), ('guard_worker', 'fdinfo_pid', 43),
                ('coordinator_guard', 'acquisition', 'inherited'), ('guard_worker', 'close_calls', 2),
                ('coordinator_controller', 'ebadf_result', 0), ('guard_controller', 'ebadf_errno', errno.EINVAL)):
            row = runtime_facts()
            row['pidfds'][key][field] = value
            with self.subTest(key=key, field=field), self.assertRaises(ValueError):
                self.parse(row)

    def test_worker_inherited_controller_handle_and_unrelated_writer_close_are_required(self):
        for change in ('wrong_controller_fd', 'missing_report_writer', 'double_same_handle', 'bad_close'):
            row = runtime_facts()
            ledger = row['inherited_closes']['worker']
            if change == 'wrong_controller_fd':
                ledger[0]['fd'] += 1
            elif change == 'missing_report_writer':
                ledger[:] = [x for x in ledger if x['kind'] != 'guard_report_write']
            elif change == 'double_same_handle':
                ledger.append(copy.deepcopy(ledger[0]))
            else:
                ledger[0]['result'] = -1
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(row)

    def test_stdio_number_reuse_by_distinct_private_pipe_kind_is_valid(self):
        row = runtime_facts()
        row['inherited_closes']['worker'].append({'fd': 0, 'kind': 'stdin', 'result': 0,
            'errno': 0, 'ebadf_result': -1, 'ebadf_errno': errno.EBADF})
        self.assertEqual(self.parse(row), row)

    def test_false_poll_readiness_wrong_fd_or_invalid_descriptor_is_refused(self):
        for key, field, value in (('controller_alive_before_arm', 'result', 1),
                ('guard_controller_exit', 'fd', 11), ('worker_exit', 'result', 0),
                ('controller_exit', 'revents', select.POLLNVAL), ('guard_exit', 'calls', 0)):
            row = runtime_facts()
            row['polls'][key][field] = value
            with self.subTest(key=key, field=field), self.assertRaises(ValueError):
                self.parse(row)

    def test_wrong_parent_waitpid_raw_status_or_forged_macro_classification_is_refused(self):
        for role, field, value in (('worker', 'owner', 'coordinator'), ('controller', 'result', 44),
                ('guard', 'status', 1 << 8), ('worker', 'signaled', True), ('controller', 'exit_code', 23)):
            row = runtime_facts()
            row['waits'][role][field] = value
            with self.subTest(role=role, field=field), self.assertRaises(ValueError):
                self.parse(row)

    def test_coherent_sigterm_header_signal_and_wait_forgery_is_still_refused(self):
        row = runtime_facts('controller_loss')
        row['headers']['sigkill'] = int(signal.SIGTERM)
        row['worker_signal']['number'] = int(signal.SIGTERM)
        row['waits']['worker']['status'] = row['waits']['worker']['term_signal'] = int(signal.SIGTERM)
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_loss_requires_one_worker_signal_and_normal_requires_zero_all_signals(self):
        for case, change in (('controller_loss', 'twice'), ('controller_loss', 'none'),
                             ('normal', 'worker'), ('normal', 'coordinator')):
            row = runtime_facts(case)
            if change == 'twice':
                row['worker_signal']['attempts'] = 2
            elif change == 'none':
                row['worker_signal'] = copy.deepcopy(NO_SIGNAL)
            else:
                signal_row = {'attempts': 1, 'fd': 0, 'number': int(signal.SIGKILL), 'flags': 0, 'result': 0, 'errno': 0}
                if change == 'worker':
                    row['worker_signal'] = signal_row
                else:
                    row['coordinator_cleanup_signals']['guard'] = signal_row
            with self.subTest(case=case, change=change), self.assertRaises(ValueError):
                self.parse(row)

    def test_normal_controller_exit_precedes_worker_exit_and_fixed_deadlines_cannot_reset(self):
        for change in ('early_worker', 'reverse_arm', 'late_signal', 'reset_budget', 'missing_time'):
            row = runtime_facts('controller_loss' if change == 'late_signal' else 'normal')
            d = row['deadlines']
            if change == 'early_worker':
                d['controller_exit_ns'] = d['worker_exit_ns'] + 1
            elif change == 'reverse_arm':
                d['guard_ack_ns'] = d['guard_arm_ns'] - 1
            elif change == 'late_signal':
                d['worker_signal_ns'] = d['cleanup_ns'] + 1
            elif change == 'reset_budget':
                d['work_ns'] += 1
            else:
                d['guard_ack_ns'] = None
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(row)

    def test_exact_json_keys_boolean_integers_duplicates_nonfinite_and_partial_are_refused(self):
        row = runtime_facts()
        for group, key in (('headers', 'sigkill'), ('deadlines', 'guard_arm_ns'), ('error', 'errno')):
            bad = copy.deepcopy(row); bad[group][key] = True
            with self.subTest(group=group), self.assertRaises(ValueError):
                self.parse(bad)
        body = json.dumps(row, sort_keys=True).encode()
        for bad in (body.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'),
                    body.replace(b'"schema_version": 1', b'"schema_version": NaN'), body + b' {}', b'{partial'):
            with self.subTest(body=bad), self.assertRaises(ValueError):
                observer.parse_runtime(bad, command(), CPP, 7, os.getuid(), BOOT, 'normal', NONCE, PRODUCT)
        row['extra'] = True
        with self.assertRaises(ValueError):
            self.parse(row)

    def test_negative_preserves_first_error_and_unknown_guard_worker_cleanup(self):
        row = runtime_facts()
        row.update(status='failed', error={'stage': 'controller_early_exit', 'errno': 0})
        row['identities']['worker'] = row['waits']['worker'] = row['worker_signal'] = None
        row['pidfds']['guard_worker'] = row['pidfds']['guard_controller'] = None
        self.assertEqual(self.parse(row, command(status='failed', returncode=1)), row)
        row['error']['stage'] = 'none'
        with self.assertRaises(ValueError):
            self.parse(row, command(status='failed', returncode=1))

    def test_success_requires_reaped_normal_coordinator_return(self):
        for cmd in (command(status='failed', returncode=1), command(reap_completed=False),
                    command(timed_out=True), command(direct_child_pid=41)):
            with self.subTest(command=cmd), self.assertRaises(ValueError):
                self.parse(runtime_facts(), cmd)

    def test_pipeline_uses_new_case_nonce_product_once_and_sets_only_matching_flag(self):
        _, utility, linkage = observer.load_utilities()
        for case in ('normal', 'controller_loss'):
            backend = FakeLifecycleBackend(Path('/fixture/output'), '/owned/new.c')
            result = observer.run_lifecycle(Path('/owned/new.c'), backend, utility, linkage,
                case, NONCE, 7, os.getuid(), BOOT)
            with self.subTest(case=case):
                self.assertEqual(result['status'], 'success', result)
                self.assert_no_authority(result)
                self.assertEqual(backend.calls[-1][1], ['/fixture/output/lifecycle', case, NONCE])
                self.assertEqual(backend.runtime_calls, 1)
                self.assertIs(result[observer.SUCCESS[case == 'controller_loss']], True)
                self.assertIs(result[observer.SUCCESS[case == 'normal']], False)
                self.assertEqual(result['compile_leg']['product_link_or_execution_attempts'], 0)
                self.assertIs(result['compile_leg']['own_pidfd_operations_verified'], False)

    def test_pipeline_rejects_external_case_or_nonce_before_any_compiler_entry(self):
        _, utility, linkage = observer.load_utilities()
        for case, nonce in (('arbitrary', NONCE), ('normal', 'short'), ('normal', True)):
            backend = FakeLifecycleBackend(Path('/fixture/output'), '/owned/new.c')
            result = observer.run_lifecycle(Path('/owned/new.c'), backend, utility, linkage,
                case, nonce, 7, os.getuid(), BOOT)
            self.assertEqual(result['status'], 'failed'); self.assertEqual(backend.calls, [])

    def test_pipeline_link_failure_or_interpreter_drift_prevents_runtime(self):
        _, utility, linkage = observer.load_utilities()
        for failure, drift in (('link', None), ('link_map', None), (None, 'interpreter')):
            backend = FakeLifecycleBackend(Path('/fixture/output'), '/owned/new.c', failure=failure, drift=drift)
            result = observer.run_lifecycle(Path('/owned/new.c'), backend, utility, linkage,
                'normal', NONCE, 7, os.getuid(), BOOT)
            self.assertEqual(result['status'], 'failed', result); self.assertEqual(backend.runtime_calls, 0)

    def test_pipeline_failed_runtime_facts_survive_rc_one_without_retry(self):
        _, utility, linkage = observer.load_utilities()
        backend = FakeLifecycleBackend(Path('/fixture/output'), '/owned/new.c', failure='runtime_negative')
        result = observer.run_lifecycle(Path('/owned/new.c'), backend, utility, linkage,
            'normal', NONCE, 7, os.getuid(), BOOT)
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['runtime_report']['error']['stage'], 'controller_early_exit')
        self.assertIs(result['runtime_returned_complete_facts'], True)
        self.assertEqual(backend.runtime_calls, 1); self.assert_no_authority(result)

    def test_pipeline_partial_foreign_timeout_and_product_drift_never_succeed(self):
        _, utility, linkage = observer.load_utilities()
        for failure, drift in (('runtime_malformed', None), ('runtime_foreign', None),
                               ('timeout_runtime', None), (None, 'runtime_product')):
            backend = FakeLifecycleBackend(Path('/fixture/output'), '/owned/new.c', failure=failure, drift=drift)
            result = observer.run_lifecycle(Path('/owned/new.c'), backend, utility, linkage,
                'normal', NONCE, 7, os.getuid(), BOOT)
            self.assertEqual(result['status'], 'failed', result); self.assertEqual(backend.runtime_calls, 1)
            self.assert_no_authority(result)

    def test_boundary_callback_failure_stops_compile_or_new_runtime(self):
        _, utility, linkage = observer.load_utilities()
        for before_compile in (True, False):
            backend = FakeLifecycleBackend(Path('/fixture/output'), '/owned/new.c')
            callback = Mock(side_effect=[ValueError('boundary drift')] if before_compile else
                            [None, ValueError('boundary drift')])
            result = observer.run_lifecycle(Path('/owned/new.c'), backend, utility, linkage,
                'normal', NONCE, 7, os.getuid(), BOOT, callback)
            self.assertEqual(result['status'], 'failed'); self.assertEqual(backend.runtime_calls, 0)
            self.assertEqual(callback.call_count, 1 if before_compile else 2)

    def test_request_exact_twelve_fields_bind_closed_case_raw_hash_and_three_utilities(self):
        with ObserverFixture() as f:
            def parse(body, expected=None):
                return observer.parse_request(body, expected or hashlib.sha256(body).hexdigest(),
                    f.request['observer_sha256'], f.request['c_probe_sha256'], f.helper)
            body = f.request_path.read_bytes(); self.assertEqual(parse(body), f.request)
            for key, value in (('schema_version', True), ('case', 'other'), ('case', True),
                    ('linkage_sha256', '0' * 64), ('toolchain_sha256', '0' * 64), ('nonce', 'short'),
                    ('extra', True), ('attempt_directory', '/proc/self/fd/0')):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    parse(json.dumps({**f.request, key: value}).encode())
            with self.assertRaises(ValueError):
                parse(body + b' ', f.request_sha)

    def test_captured_utility_cache_or_changed_linkage_body_is_refused(self):
        original_loader = observer.load_utilities
        for name in ('frontier_v8_lifecycle_identity_helper', 'frontier_v8_lifecycle_build_utility',
                     'frontier_v8_lifecycle_linkage_utility'):
            with patch.dict(sys.modules, {name: object()}), self.assertRaises(ValueError):
                observer.load_utilities()
        with ObserverFixture() as f:
            f.linkage_path.write_bytes(b'changed immutable linkage')
            with patch.object(observer, 'load_utilities', original_loader):
                with self.assertRaises((ValueError, OSError)):
                    f.observe()

    def test_prevalidation_failure_never_consumes_or_runs_lifecycle_product(self):
        for change in ('source', 'probe', 'helper_path', 'utility_path', 'linkage_path', 'bootstrap'):
            with self.subTest(change=change), ObserverFixture() as f:
                path = getattr(f, change); path.write_bytes(path.read_bytes() + b' changed')
                with self.assertRaises((ValueError, OSError)):
                    f.observe()
                f.pipeline.assert_not_called(); self.assertFalse(f.marker.exists()); self.assertFalse(f.attempt.exists())

    def test_success_receipt_has_no_authority_and_attempt_cannot_be_reconsumed(self):
        with ObserverFixture() as f:
            row = f.observe()
            self.assertEqual(row['status'], 'owned_C_direct_worker_lifecycle_observed', row)
            self.assert_no_authority(row); self.assertIs(row[observer.SUCCESS[0]], True)
            self.assertIs(row[observer.SUCCESS[1]], False)
            self.assertEqual(json.loads((f.attempt / 'receipt.json').read_bytes()), row)
            marker = f.marker.read_bytes()
            with self.assertRaises((ValueError, OSError)):
                f.observe()
            self.assertEqual(f.pipeline.call_count, 1); self.assertEqual(f.marker.read_bytes(), marker)

    def test_failed_product_or_postvalidation_drift_stays_consumed_and_negative(self):
        for failure in ('product', 'source', 'marker', 'self'):
            with self.subTest(failure=failure), ObserverFixture() as f:
                success = f.pipeline.return_value
                if failure == 'product':
                    f.pipeline.return_value = {**observer.AUTHORITY, **dict.fromkeys(observer.SUCCESS, False), 'status': 'failed'}
                elif failure == 'self':
                    f.helper.capture_self_identity.side_effect = [own_identity(), {**own_identity(), 'start_ticks': 101}]
                else:
                    def pipeline(*args):
                        path = f.source if failure == 'source' else f.marker
                        path.write_bytes(path.read_bytes() + b' changed'); return success
                    f.pipeline.side_effect = pipeline
                row = f.observe()
                self.assertEqual(row['status'], 'failed', row); self.assert_no_authority(row)
                self.assertTrue(f.marker.exists()); self.assertFalse(any(row[key] for key in observer.SUCCESS))

    def test_execute_refuses_before_parser_utilities_request_or_lifecycle(self):
        with patch.object(observer, 'load_utilities') as utilities, patch.object(observer, 'observe') as observe, \
                patch.object(observer, 'run_lifecycle') as lifecycle, patch.object(observer.argparse, 'ArgumentParser') as parser:
            for argv in (['--execute'], ['--request', '/missing', '--execute=true']):
                with self.assertRaises(ValueError):
                    observer.main(argv)
            for mocked in (utilities, observe, lifecycle, parser):
                mocked.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux', 'Real owned C normal fixture requires Ubuntu Linux CI')
    def test_real_linux_normal_case_observes_arm_ack_orderly_worker_and_parent_reaps(self):
        self.real_case('normal')

    @unittest.skipUnless(sys.platform == 'linux', 'Real owned C controller-loss fixture requires Ubuntu Linux CI')
    def test_real_linux_controller_loss_case_observes_single_worker_sigkill_and_guard_reap(self):
        self.real_case('controller_loss')

    def real_case(self, case):
        helper, utility, linkage = observer.load_utilities()
        boot = helper.capture_self_identity()['boot_id']
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve(); (directory / 'tmp').mkdir()
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                result = observer.run_lifecycle(ROOT / 'scripts/frontier_v8_owned_c_lifecycle.c',
                    utility.CompilerBackend(helper, directory, fd), utility, linkage, case,
                    secrets.token_hex(32), os.getpid(), os.getuid(), boot)
                self.assertEqual(result['status'], 'success', result); self.assert_no_authority(result)
                self.assertEqual(result['runtime_attempts'], 1)
                facts = result['runtime_report']
                self.assertEqual(facts['waits']['worker']['owner'], 'guard')
                self.assertEqual(facts['waits']['guard']['owner'], 'coordinator')
                self.assertEqual(facts['worker_signal']['attempts'], int(case == 'controller_loss'))
                self.assertEqual(facts['waits']['controller']['exit_code'], 23 if case == 'controller_loss' else 0)
                self.assertTrue(all(x['close_calls'] == 1 and x['ebadf_result'] == -1 for x in facts['pidfds'].values()))
                self.assertTrue(all(not cmd['kill_attempted'] for cmd in result['compile_leg']['commands'] + result['commands']))
            finally:
                os.close(fd)


if __name__ == '__main__':
    unittest.main()
