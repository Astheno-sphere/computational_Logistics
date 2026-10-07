"""New dedicated own-C product fixtures, without model or resource authority."""
from contextlib import ExitStack
import errno
import hashlib
import json
import os
from pathlib import Path
import secrets
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_owned_c_selfcheck as observer
from tests.test_frontier_v8_c_toolchain import FakeCompilerBackend, own_identity


ROOT = Path(__file__).resolve().parents[1]
BOOT = '00000000-0000-0000-0000-000000000001'
CPP_FACTS = {'SYS_pidfd_open_expression': '((1 << 8) + 9L)',
             'target_int_bytes': 4, 'target_long_bytes': 8,
             'target_pointer_bytes': 8, 'target_char_bits': 8,
             'target_byte_order': 1234}


def runtime_facts(**changes):
    """Explicit synthetic evidence; the header value is not a live syscall input."""
    return {'schema_version': 1, 'status': 'success', 'error_stage': 'none', 'error_errno': 0,
            'pid': 42, 'ppid': 7, 'uid': os.getuid(), 'euid': os.getuid(),
            'proc_self_pid': 42, 'header_pidfd_open': 265,
            'int_bytes': 4, 'long_bytes': 8, 'pointer_bytes': 8, 'char_bits': 8,
            'byte_order': 1234, 'header_pollin': 1, 'header_ebadf': errno.EBADF,
            'open_attempted': True, 'pidfd_acquired': True, 'pidfd': 3,
            'fdinfo_pid': 42, 'fdinfo_verified': True,
            'poll_attempted': True, 'poll_events': 1, 'poll_result': 0, 'poll_revents': 0,
            'close_attempted': True, 'close_calls': 1, 'close_result': 0, 'close_errno': 0,
            'ebadf_check_attempted': True, 'ebadf_result': -1,
            'ebadf_errno': errno.EBADF, 'ebadf_verified': True, **changes}


def command_facts(**changes):
    return {'direct_child_pid': 42, 'status': 'success', 'returncode': 0,
            'timed_out': False, 'reap_completed': True, **changes}


def product_bytes(*, elf_class=2, data=1, kind=3, machine=62,
                  interpreter=b'/fixture/loader\0', phnum=1):
    ident = b'\x7fELF' + bytes((elf_class, data, 1, 0, 0)) + b'\0' * 7
    order = '<' if data == 1 else '>'
    if elf_class == 1:
        offset = 52 + 32 * phnum
        header = struct.pack(order + '16sHHIIIIIHHHHHH', ident, kind, machine, 1,
                             0, 52, 0, 0, 52, 32, phnum, 0, 0, 0)
        segment = struct.pack(order + 'IIIIIIII', 3, offset, 0, 0,
                              len(interpreter), len(interpreter), 4, 1)
    else:
        offset = 64 + 56 * phnum
        header = struct.pack(order + '16sHHIQQQIHHHHHH', ident, kind, machine, 1,
                             0, 64, 0, 0, 64, 56, phnum, 0, 0, 0)
        segment = struct.pack(order + 'IIQQQQQQ', 3, 4, offset, 0, 0,
                              len(interpreter), len(interpreter), 1)
    return header + segment * phnum + interpreter


class FakeSelfcheckBackend(FakeCompilerBackend):
    """New link/runtime ledger on the prior synthetic object-only backend."""
    def __init__(self, root, source, *, failure=None, drift=None):
        super().__init__(root, source, failure=failure, drift=drift)
        self.runtime_calls = 0

    def snapshot(self, path, limit):
        row = super().snapshot(path, limit)
        if self.drift == 'interpreter' and str(path) == '/fixture/loader' \
                and self.snapshots[str(path)] > 1:
            row['sha256'] = '0' * 64
        if self.drift == 'link_input' and str(path) == '/fixture/link-input' \
                and self.snapshots[str(path)] > 1:
            row['sha256'] = '0' * 64
        return row

    def run(self, label, argv):
        if label not in ('link', 'runtime'):
            return super().run(label, argv)
        self.calls.append((label, argv))
        stdout = b''
        if label == 'link':
            self.outputs['link.map'] = (
                'LOAD ' + str(self.root / 'probe.o') + '\nLOAD /fixture/link-input\n').encode()
            self.outputs['selfcheck'] = product_bytes()
            if self.failure == 'link_map':
                self.outputs['link.map'] = b'LOAD /proc/self/fd/0\n'
            if self.failure == 'product':
                self.outputs['selfcheck'] = product_bytes(kind=1)
            if self.failure == 'descriptor':
                self.outputs['selfcheck'] = product_bytes(machine=183)
        else:
            self.runtime_calls += 1
            facts = runtime_facts()
            if self.failure == 'runtime_negative':
                facts = runtime_facts(status='failed', error_stage='pidfd_open', error_errno=38,
                    pidfd_acquired=False, pidfd=-1, fdinfo_pid=-1, fdinfo_verified=False,
                    poll_attempted=False, poll_events=0, poll_result=-1,
                    close_attempted=False, close_calls=0, close_result=-1,
                    ebadf_check_attempted=False, ebadf_result=0, ebadf_errno=0,
                    ebadf_verified=False)
            if self.failure == 'runtime_foreign':
                facts['proc_self_pid'] = 43
            if self.failure == 'runtime_false_ebadf':
                facts['ebadf_result'] = 0
            stdout = json.dumps(facts, sort_keys=True).encode()
            if self.failure == 'runtime_malformed':
                stdout = b'{incomplete'
            if self.failure == 'timeout_runtime':
                stdout = b''
            if self.drift == 'runtime_product':
                self.outputs['selfcheck'] += b' changed'
        self.outputs[label + '.stdout'], self.outputs[label + '.stderr'] = stdout, b''
        failed = self.failure in (label, 'timeout_' + label) or \
            (label == 'runtime' and self.failure == 'runtime_negative')
        return {'label': label, 'argv': argv, 'status': 'failed' if failed else 'success',
                'returncode': None if self.failure == 'timeout_' + label else (1 if failed else 0),
                'timed_out': self.failure == 'timeout_' + label,
                'direct_child_pid': 42, 'kill_attempted': self.failure == 'timeout_' + label,
                'reap_completed': self.failure != 'timeout_' + label,
                'kill_error': None, 'reap_error': None, 'descendant_cleanup_verified': False,
                'stdout': self.read_output(label + '.stdout', observer.MAX_BYTES)[1],
                'stderr': self.read_output(label + '.stderr', observer.MAX_BYTES)[1]}


class ObserverFixture:
    """Fresh owned file boundary with an injected new-product result only."""
    def __enter__(self):
        self.stack = ExitStack()
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.source = self.directory / 'observer.py'
        self.source.write_bytes(b'# Injected new observer file binding only.\n')
        for name in ('frontier_v8_owned_c_selfcheck.c', 'frontier_v8_containment_capability.py',
                     'frontier_v8_c_toolchain.py'):
            (self.directory / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
        self.probe = self.directory / 'frontier_v8_owned_c_selfcheck.c'
        self.helper_path = self.directory / 'frontier_v8_containment_capability.py'
        self.utility_path = self.directory / 'frontier_v8_c_toolchain.py'
        self.bootstrap = self.directory / 'bootstrap'
        self.bootstrap.write_bytes(b'Injected bootstrap bytes')
        with patch.object(observer, '__file__', str(self.source)):
            self.helper, self.utility = observer.load_utilities()
        self.attempt, self.request_path = self.directory / 'attempt', self.directory / 'request.json'
        self.request = {'schema_version': 1, 'scope': observer.SCOPE, 'nonce': secrets.token_hex(32),
            'observer_sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(),
            'c_probe_sha256': hashlib.sha256(self.probe.read_bytes()).hexdigest(),
            'identity_helper_sha256': observer.HELPER_SHA,
            'toolchain_sha256': observer.TOOLCHAIN_SHA, 'attempt_directory': str(self.attempt),
            'host': {'node_alias': 'N1-1', 'hostname': 'fixture-host', 'boot_id': BOOT, 'uid': os.getuid()},
            'bootstrap': {'executable': str(self.bootstrap),
                'sha256': hashlib.sha256(self.bootstrap.read_bytes()).hexdigest(),
                'version': list(sys.version_info[:3])}}
        self.write_request()
        self.pipeline = Mock(return_value={**observer.AUTHORITY,
            **dict.fromkeys(observer.SUCCESS, True), 'status': 'success'})
        for target, key, value in (
                (observer, '__file__', str(self.source)),
                (observer, 'load_utilities', Mock(return_value=(self.helper, self.utility))),
                (observer, 'run_selfcheck', self.pipeline),
                (self.utility, 'CompilerBackend', Mock()),
                (observer.sys, 'flags', SimpleNamespace(isolated=1, no_site=1)),
                (observer.sys, 'dont_write_bytecode', True),
                (observer.sys, 'platform', 'linux'),
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


class OwnedCSelfcheckTests(unittest.TestCase):
    def assert_no_authority(self, result):
        for key in observer.AUTHORITY:
            self.assertIs(result[key], False)

    def parse_runtime(self, facts, command=None):
        return observer.parse_runtime(json.dumps(facts, sort_keys=True).encode(),
            command or command_facts(), CPP_FACTS, 7, os.getuid())

    def test_runtime_success_recomputes_chain_and_preserves_scalar_header_facts(self):
        facts = runtime_facts()
        self.assertEqual(self.parse_runtime(facts), facts)
        self.assertEqual(facts['header_pidfd_open'], 265)
        self.assertEqual(CPP_FACTS['SYS_pidfd_open_expression'], '((1 << 8) + 9L)')

    def test_runtime_foreign_process_proc_parent_and_user_identities_are_refused(self):
        for key, value in (('pid', 43), ('ppid', 8), ('proc_self_pid', 43),
                           ('fdinfo_pid', 43), ('uid', os.getuid() + 1), ('euid', os.getuid() + 1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse_runtime(runtime_facts(**{key: value}))

    def test_runtime_forged_success_fails_without_actual_poll_close_and_ebadf_facts(self):
        for key, value in (('pidfd', -1), ('open_attempted', False), ('pidfd_acquired', False),
                ('fdinfo_verified', False), ('poll_attempted', False), ('poll_events', 0),
                ('poll_result', 1), ('poll_revents', 1), ('close_calls', 2),
                ('close_attempted', False), ('close_result', -1), ('close_errno', errno.EINTR),
                ('ebadf_check_attempted', False), ('ebadf_result', 0), ('ebadf_errno', errno.EINVAL),
                ('header_ebadf', errno.EINVAL), ('ebadf_verified', False), ('error_stage', 'poll')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse_runtime(runtime_facts(**{key: value}))

    def test_runtime_false_json_types_duplicate_keys_nonfinite_extra_and_partial_are_refused(self):
        for key in runtime_facts():
            replacement = 1 if type(runtime_facts()[key]) is bool else True
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse_runtime(runtime_facts(**{key: replacement}))
        body = json.dumps(runtime_facts(), sort_keys=True).encode()
        for bad in (body.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'),
                    body.replace(b'"schema_version": 1', b'"schema_version": NaN'),
                    body + b' {}', b'', b'{partial', b'[]'):
            with self.subTest(body=bad), self.assertRaises(ValueError):
                observer.parse_runtime(bad, command_facts(), CPP_FACTS, 7, os.getuid())
        with self.assertRaises(ValueError):
            self.parse_runtime(runtime_facts(extra=True))

    def test_runtime_success_requires_normal_reaped_zero_return_and_compiled_sizes(self):
        for command in (command_facts(status='failed', returncode=1),
                        command_facts(timed_out=True), command_facts(reap_completed=False),
                        command_facts(direct_child_pid=43)):
            with self.subTest(command=command), self.assertRaises(ValueError):
                self.parse_runtime(runtime_facts(), command)
        for key in ('int_bytes', 'long_bytes', 'pointer_bytes', 'char_bits', 'byte_order'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse_runtime(runtime_facts(**{key: runtime_facts()[key] + 1}))

    def test_runtime_negative_preserves_first_error_and_later_once_close_facts(self):
        facts = runtime_facts(status='failed', error_stage='poll', error_errno=errno.EINTR,
                              poll_result=-1)
        self.assertEqual(self.parse_runtime(facts, command_facts(status='failed', returncode=1)), facts)
        self.assertIs(facts['ebadf_verified'], True)
        self.assertEqual(facts['error_stage'], 'poll')
        with self.assertRaises(ValueError):
            self.parse_runtime({**facts, 'error_stage': 'none'}, command_facts(status='failed', returncode=1))

    def test_link_map_preserves_absolute_lexical_aliases_and_deduplicates_load_inventory(self):
        body = b'LOAD /owned/probe.o\nLOAD /usr/lib/gcc/../libc.so\nLOAD /owned/probe.o\n'
        self.assertEqual(observer.parse_link_map(body, '/owned/probe.o'),
                         ('/owned/probe.o', '/usr/lib/gcc/../libc.so'))

    def test_link_map_refuses_relative_malformed_missing_object_and_virtual_aliases(self):
        for body in (b'LOAD relative.o\n', b' LOAD /owned/probe.o\n',
                b'LOAD /owned/probe.o extra\n', b'LOAD /other/probe.o\n',
                b'LOAD /owned/probe.o\nLOAD /tmp/../proc/self/fd/0\n',
                b'LOAD /owned/probe.o\nLOAD /dev/null\n'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                observer.parse_link_map(body, '/owned/probe.o')
        with patch.object(observer.os.path, 'realpath', return_value='/proc/self/fd/0'), \
                self.assertRaises(ValueError):
            observer.parse_link_map(b'LOAD /owned/probe.o\n', '/owned/probe.o')

    def test_product_elf_reads_actual_interpreter_without_provider_filename_guess(self):
        for cls, data, machine in ((1, 1, 3), (2, 1, 62), (2, 2, 183)):
            with self.subTest(cls=cls, data=data):
                result = observer.parse_elf_product(product_bytes(elf_class=cls, data=data, machine=machine))
                self.assertEqual(result, {'elf_class': cls, 'data_encoding': data, 'elf_type': 3,
                    'machine': machine, 'interpreter': '/fixture/loader'})

    def test_product_elf_refuses_nonproduct_missing_duplicate_or_unsafe_interpreter(self):
        for body in (b'not elf', product_bytes(kind=1), product_bytes(phnum=0),
                product_bytes(phnum=2), product_bytes(interpreter=b'relative\0'),
                product_bytes(interpreter=b'/proc/self/fd/0\0'),
                product_bytes(interpreter=b'/fixture/loader'),
                product_bytes(interpreter=b'/fixture/lo\0ader\0'), product_bytes()[:80]):
            with self.subTest(body=body), self.assertRaises(ValueError):
                observer.parse_elf_product(body)

    def test_product_elf_refuses_out_of_bounds_program_table_and_interpreter_offsets(self):
        for offset, fmt, value in ((32, '<Q', 10000), (56, '<H', 128),
                                   (72, '<Q', 10000), (96, '<Q', 10000)):
            body = bytearray(product_bytes())
            struct.pack_into(fmt, body, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                observer.parse_elf_product(bytes(body))

    def test_new_pipeline_links_and_executes_only_fresh_product_once(self):
        _, utility = observer.load_utilities()
        backend = FakeSelfcheckBackend(Path('/fixture/output'), '/owned/new.c')
        result = observer.run_selfcheck(Path('/owned/new.c'), backend, utility, 7, os.getuid())
        self.assertEqual(result['status'], 'success', result)
        self.assert_no_authority(result)
        self.assertTrue(all(result[key] is True for key in observer.SUCCESS))
        self.assertEqual([call[0] for call in backend.calls],
                         ['resolve', 'version', 'dependencies', 'preprocess', 'object', 'link', 'runtime'])
        self.assertEqual(backend.calls[-1][1], ['/fixture/output/selfcheck'])
        self.assertEqual(backend.runtime_calls, 1)
        self.assertEqual(result['link_attempts'], 1)
        self.assertEqual(result['runtime_attempts'], 1)
        self.assertEqual(result['compile_leg']['product_link_or_execution_attempts'], 0)
        self.assertIs(result['compile_leg']['own_pidfd_operations_verified'], False)
        self.assertIs(result['complete_mapped_code_authenticated'], False)

    def test_new_pipeline_link_map_product_or_descriptor_failure_prevents_runtime(self):
        _, utility = observer.load_utilities()
        for failure in ('link', 'link_map', 'product', 'descriptor'):
            with self.subTest(failure=failure):
                backend = FakeSelfcheckBackend(Path('/fixture/output'), '/owned/new.c', failure=failure)
                result = observer.run_selfcheck(Path('/owned/new.c'), backend, utility, 7, os.getuid())
                self.assertEqual(result['status'], 'failed', result)
                self.assertEqual(backend.runtime_calls, 0)
                self.assertEqual(result['runtime_attempts'], 0)
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is False for key in observer.SUCCESS))

    def test_new_pipeline_negative_runtime_retains_actual_failed_C_facts_without_retry(self):
        _, utility = observer.load_utilities()
        backend = FakeSelfcheckBackend(Path('/fixture/output'), '/owned/new.c', failure='runtime_negative')
        result = observer.run_selfcheck(Path('/owned/new.c'), backend, utility, 7, os.getuid())
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(result['runtime_report']['error_stage'], 'pidfd_open')
        self.assertIs(result['pidfd_entry_attempted_reported'], True)
        self.assertEqual(backend.runtime_calls, 1)
        self.assert_no_authority(result)
        self.assertTrue(all(result[key] is False for key in observer.SUCCESS))

    def test_new_pipeline_runtime_malformed_foreign_false_success_and_timeout_remain_failed(self):
        _, utility = observer.load_utilities()
        for failure in ('runtime_malformed', 'runtime_foreign', 'runtime_false_ebadf', 'timeout_runtime'):
            with self.subTest(failure=failure):
                backend = FakeSelfcheckBackend(Path('/fixture/output'), '/owned/new.c', failure=failure)
                result = observer.run_selfcheck(Path('/owned/new.c'), backend, utility, 7, os.getuid())
                self.assertEqual(result['status'], 'failed', result)
                self.assertEqual(backend.runtime_calls, 1)
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is False for key in observer.SUCCESS))
                self.assertNotIn('runtime_report', result)

    def test_new_pipeline_interpreter_link_input_and_product_drift_cannot_succeed(self):
        _, utility = observer.load_utilities()
        for drift in ('interpreter', 'link_input', 'runtime_product'):
            with self.subTest(drift=drift):
                backend = FakeSelfcheckBackend(Path('/fixture/output'), '/owned/new.c', drift=drift)
                result = observer.run_selfcheck(Path('/owned/new.c'), backend, utility, 7, os.getuid())
                self.assertEqual(result['status'], 'failed', result)
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is False for key in observer.SUCCESS))
                self.assertEqual(backend.runtime_calls, int(drift == 'runtime_product'))

    def test_new_pipeline_fresh_boundary_checks_prevent_compile_or_runtime_after_drift(self):
        _, utility = observer.load_utilities()
        for checkpoint in ('before_compile', 'before_runtime'):
            with self.subTest(checkpoint=checkpoint):
                backend = FakeSelfcheckBackend(Path('/fixture/output'), '/owned/new.c')
                callback = Mock(side_effect=[ValueError('fresh boundary drift')] if checkpoint ==
                    'before_compile' else [None, ValueError('fresh boundary drift')])
                result = observer.run_selfcheck(Path('/owned/new.c'), backend, utility, 7,
                    os.getuid(), pre_runtime_check=callback)
                self.assertEqual(result['status'], 'failed', result)
                self.assertEqual(backend.runtime_calls, 0)
                self.assertEqual(result['runtime_attempts'], 0)
                self.assertEqual(callback.call_count, 1 if checkpoint == 'before_compile' else 2)
                if checkpoint == 'before_compile':
                    self.assertEqual(backend.calls, [])
                else:
                    self.assertEqual(backend.calls[-1][0], 'link')
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is False for key in observer.SUCCESS))

    def test_request_exact_ten_fields_bind_raw_hash_and_both_immutable_utilities(self):
        with ObserverFixture() as fixture:
            def parse(body, expected=None):
                return observer.parse_request(body, expected or hashlib.sha256(body).hexdigest(),
                    fixture.request['observer_sha256'], fixture.request['c_probe_sha256'], fixture.helper)
            body = fixture.request_path.read_bytes()
            self.assertEqual(parse(body), fixture.request)
            for key, value in (('schema_version', True), ('scope', 'old-scope'), ('nonce', 'short'),
                    ('observer_sha256', '0' * 64), ('c_probe_sha256', '0' * 64),
                    ('identity_helper_sha256', '0' * 64), ('toolchain_sha256', '0' * 64),
                    ('extra', True), ('attempt_directory', '/proc/self/fd/0'),
                    ('host', {**fixture.request['host'], 'uid': True}),
                    ('bootstrap', {**fixture.request['bootstrap'], 'version': [True, 1, 1]})):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    parse(json.dumps({**fixture.request, key: value}).encode())
            for bad in (body.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'),
                        body.replace(b'"schema_version": 1', b'"schema_version": Infinity')):
                with self.subTest(body=bad), self.assertRaises(ValueError):
                    parse(bad)
            with self.assertRaises(ValueError):
                parse(body + b' ', fixture.request_sha)

    def test_utility_capture_refuses_preloaded_cache_and_changed_immutable_body(self):
        for name in ('frontier_v8_owned_c_identity_helper', 'frontier_v8_owned_c_build_utility'):
            with self.subTest(name=name), patch.dict(sys.modules, {name: object()}), \
                    self.assertRaises(ValueError):
                observer.load_utilities()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            for name in ('frontier_v8_containment_capability.py', 'frontier_v8_c_toolchain.py'):
                (directory / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
            (directory / 'frontier_v8_c_toolchain.py').write_bytes(b'changed utility')
            with patch.object(observer, '__file__', str(directory / 'observer.py')), \
                    self.assertRaises(ValueError):
                observer.load_utilities()

    def test_observer_prevalidation_failure_never_consumes_or_runs_new_product(self):
        for change in ('source', 'probe', 'helper_path', 'utility_path', 'bootstrap', 'host', 'request_symlink'):
            with self.subTest(change=change), ObserverFixture() as fixture:
                if change in ('source', 'probe', 'helper_path', 'utility_path', 'bootstrap'):
                    path = getattr(fixture, change)
                    path.write_bytes(path.read_bytes() + b' changed')
                elif change == 'host':
                    fixture.request['host']['hostname'] = 'other-host'
                    fixture.write_request()
                else:
                    original = fixture.directory / 'original-request.json'
                    fixture.request_path.rename(original)
                    fixture.request_path.symlink_to(original)
                with self.assertRaises((ValueError, OSError)):
                    fixture.observe()
                fixture.pipeline.assert_not_called()
                self.assertFalse(fixture.marker.exists())
                self.assertFalse(fixture.attempt.exists())

    def test_observer_success_sets_only_narrow_C_flags_and_cannot_reconsume(self):
        with ObserverFixture() as fixture:
            result = fixture.observe()
            self.assertEqual(result['status'], 'owned_C_current_PID_descriptor_observed', result)
            self.assert_no_authority(result)
            self.assertTrue(all(result[key] is True for key in observer.SUCCESS))
            self.assertIs(result['input_and_self_identity_postvalidation_passed'], True)
            self.assertEqual(json.loads((fixture.attempt / 'receipt.json').read_bytes()), result)
            marker = fixture.marker.read_bytes()
            with self.assertRaises((ValueError, OSError)):
                fixture.observe()
            self.assertEqual(fixture.pipeline.call_count, 1)
            self.assertEqual(fixture.marker.read_bytes(), marker)
            self.assertIs(result['native_guard_executed_or_modified'], False)
            self.assertIs(result['os_api_shim_installed'], False)

    def test_observer_failed_product_and_postvalidation_drift_retain_consumed_negative_receipt(self):
        for failure in ('product', 'input', 'self', 'marker', 'utility'):
            with self.subTest(failure=failure), ObserverFixture() as fixture:
                success = fixture.pipeline.return_value
                if failure == 'product':
                    fixture.pipeline.return_value = {**observer.AUTHORITY,
                        **dict.fromkeys(observer.SUCCESS, False), 'status': 'failed'}
                elif failure == 'self':
                    fixture.helper.capture_self_identity.side_effect = [own_identity(),
                        {**own_identity(), 'start_ticks': 101}]
                else:
                    def pipeline(*args):
                        path = {'input': fixture.source, 'marker': fixture.marker,
                                'utility': fixture.utility_path}[failure]
                        path.write_bytes(path.read_bytes() + b' changed')
                        return success
                    fixture.pipeline.side_effect = pipeline
                result = fixture.observe()
                self.assertEqual(result['status'], 'failed', result)
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is False for key in observer.SUCCESS))
                self.assertTrue(fixture.marker.exists())
                self.assertEqual(json.loads((fixture.attempt / 'receipt.json').read_bytes()), result)
                self.assertIs(result['input_and_self_identity_postvalidation_passed'], failure == 'product')

    def test_backend_product_environment_and_direct_child_timeout_remain_bounded(self):
        helper, utility = observer.load_utilities()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            (directory / 'tmp').mkdir()
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                backend = utility.CompilerBackend(helper, directory, fd)
                child = Mock(pid=42)
                child.wait.side_effect = [subprocess.TimeoutExpired(['fixture'], 30), -9]
                def popen(argv, **kwargs):
                    self.assertEqual(argv, ['/fixture/new-product'])
                    self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
                    self.assertTrue(kwargs['close_fds'])
                    self.assertEqual(kwargs['env'], {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
                        'TMPDIR': str(directory / 'tmp'), 'CUDA_VISIBLE_DEVICES': '', 'NVIDIA_VISIBLE_DEVICES': 'none'})
                    return child
                with patch.object(utility.subprocess, 'Popen', side_effect=popen):
                    result = backend.run('runtime', ['/fixture/new-product'])
                self.assertEqual(result['status'], 'failed')
                self.assertIs(result['timed_out'], True)
                self.assertIs(result['reap_completed'], True)
                self.assertIs(result['descendant_cleanup_verified'], False)
                child.kill.assert_called_once_with()
                self.assertEqual([call.kwargs for call in child.wait.call_args_list],
                                 [{'timeout': 30}, {'timeout': 2}])
            finally:
                os.close(fd)

    def test_execute_refuses_before_parser_utility_request_or_new_product(self):
        with patch.object(observer, 'load_utilities') as utilities, \
                patch.object(observer, 'observe') as observe, \
                patch.object(observer, 'run_selfcheck') as selfcheck, \
                patch.object(observer.argparse, 'ArgumentParser') as parser:
            for argv in (['--execute'], ['--request', '/missing', '--execute=true']):
                with self.assertRaises(ValueError):
                    observer.main(argv)
            for mocked in (utilities, observe, selfcheck, parser):
                mocked.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux', 'Real dedicated C descriptor product requires Ubuntu Linux CI')
    def test_real_linux_dedicated_product_links_and_verifies_own_descriptor_once(self):
        helper, utility = observer.load_utilities()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            (directory / 'tmp').mkdir()
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                result = observer.run_selfcheck(ROOT / 'scripts/frontier_v8_owned_c_selfcheck.c',
                    utility.CompilerBackend(helper, directory, fd), utility, os.getpid(), os.getuid())
                self.assertEqual(result['status'], 'success', result)
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is True for key in observer.SUCCESS))
                self.assertEqual(result['runtime_attempts'], 1)
                self.assertEqual(result['runtime_report']['close_calls'], 1)
                self.assertEqual(result['runtime_report']['ebadf_result'], -1)
                self.assertEqual(result['runtime_report']['ebadf_errno'], errno.EBADF)
                self.assertEqual(result['runtime_report']['poll_result'], 0)
                self.assertEqual(result['runtime_report']['poll_revents'], 0)
                self.assertEqual(result['runtime_report']['proc_self_pid'], result['runtime_report']['pid'])
                self.assertEqual([command['label'] for command in result['commands']], ['link', 'runtime'])
                self.assertTrue(all(not command['kill_attempted'] for command in
                    result['compile_leg']['commands'] + result['commands']))
            finally:
                os.close(fd)

    @unittest.skipUnless(sys.platform == 'linux', 'Real isolated owned-C CLI requires Ubuntu Linux CI')
    def test_real_linux_isolated_C_cli_returns_bound_receipt_without_containment_authority(self):
        source = ROOT / 'scripts/frontier_v8_owned_c_selfcheck.py'
        probe = ROOT / 'scripts/frontier_v8_owned_c_selfcheck.c'
        helper, _ = observer.load_utilities()
        executable = Path(os.path.realpath(sys.executable))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            attempt, request_path = directory / 'attempt', directory / 'request.json'
            request = {'schema_version': 1, 'scope': observer.SCOPE, 'nonce': secrets.token_hex(32),
                'observer_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'c_probe_sha256': hashlib.sha256(probe.read_bytes()).hexdigest(),
                'identity_helper_sha256': observer.HELPER_SHA, 'toolchain_sha256': observer.TOOLCHAIN_SHA,
                'attempt_directory': str(attempt),
                'host': {'node_alias': 'N1-1', 'hostname': os.uname().nodename,
                    'boot_id': helper.capture_self_identity()['boot_id'], 'uid': os.getuid()},
                'bootstrap': {'executable': str(executable), 'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
                              'version': list(sys.version_info[:3])}}
            body = json.dumps(request, sort_keys=True).encode()
            request_path.write_bytes(body)
            completed = subprocess.run([str(executable), '-B', '-I', '-S', str(source),
                '--observe-owned-c-selfcheck', '--request', str(request_path),
                '--expected-request-sha256', hashlib.sha256(body).hexdigest()],
                capture_output=True, timeout=240, check=False)
            self.assertEqual(completed.returncode, 0, (completed.stdout, completed.stderr))
            self.assertEqual(completed.stderr, b'')
            result = json.loads(completed.stdout)
            self.assertEqual(result['status'], 'owned_C_current_PID_descriptor_observed')
            self.assertEqual(json.loads((attempt / 'receipt.json').read_bytes()), result)
            self.assert_no_authority(result)
            self.assertTrue(all(result[key] is True for key in observer.SUCCESS))
            self.assertIs(result['input_and_self_identity_postvalidation_passed'], True)
            self.assertEqual(result['selfcheck']['runtime_attempts'], 1)
            self.assertEqual(json.loads(attempt.with_name('attempt.consumed.json').read_bytes())['nonce'], request['nonce'])


if __name__ == '__main__':
    unittest.main()
