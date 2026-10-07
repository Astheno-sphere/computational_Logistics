"""Compiler/header/target fixtures; generated objects are never executed."""
from contextlib import ExitStack
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

from scripts import frontier_v8_c_toolchain as toolchain


ROOT = Path(__file__).resolve().parents[1]
BOOT = '00000000-0000-0000-0000-000000000001'
MARKERS = (
    'const long frontier_v8_header_pidfd_open = ((1 << 8) + 9L);',
    'const unsigned int frontier_v8_target_int_bytes = 4;',
    'const unsigned int frontier_v8_target_long_bytes = 8;',
    'const unsigned int frontier_v8_target_pointer_bytes = 8;',
    'const unsigned int frontier_v8_target_char_bits = 8;',
    'const unsigned int frontier_v8_target_byte_order = 1234;')


def own_identity():
    return {'boot_id': BOOT, 'pid': 42, 'ppid': 7, 'pgrp': 42, 'session': 42,
            'start_ticks': 100, 'state': 'R', 'uid': os.getuid(), 'euid': os.getuid(),
            'proc_uids': [os.getuid()] * 4, 'parent_identity_verified': False,
            'ancestry_verified': False}


def object_bytes(*, elf_class=2, data=1, kind=1, machine=62):
    ident = b'\x7fELF' + bytes((elf_class, data, 1, 0, 0)) + b'\0' * 7
    order = '<' if data == 1 else '>'
    if elf_class == 1:
        return struct.pack(order + '16sHHIIIIIHHHHHH', ident, kind, machine, 1,
                           0, 0, 0, 0, 52, 0, 0, 0, 0, 0)
    return struct.pack(order + '16sHHIQQQIHHHHHH', ident, kind, machine, 1,
                       0, 0, 0, 0, 64, 0, 0, 0, 0, 0)


class FakeCompilerBackend:
    """Synthetic compiler artifacts and a ledger, without compiler processes."""
    def __init__(self, root, source, *, failure=None, drift=None):
        self.root, self.source = root, str(source)
        self.failure, self.drift = failure, drift
        self.calls, self.outputs, self.reads, self.snapshots = [], {}, {}, {}
        self.driver = '/fixture/cc'
        self.header = '/usr/include/fixture_header.h'

    def snapshot(self, path, limit):
        path = str(path)
        self.snapshots[path] = self.snapshots.get(path, 0) + 1
        drift = ((self.drift == 'driver' and path == self.driver)
                 or (self.drift == 'header' and path == self.header))
        changed = drift and self.snapshots[path] > 1
        body = path.encode() + (b' changed' if changed else b' stable')
        return {'path': path, 'sha256': hashlib.sha256(body).hexdigest(),
                'identity': [1, 2, 3, 4, len(body), 6, 7], 'bytes': len(body)}

    def resolve_compiler(self):
        self.calls.append(('resolve',))
        if self.failure == 'missing':
            raise FileNotFoundError('fixture cc unavailable')
        return {**self.snapshot(self.driver, toolchain.MAX_DRIVER), 'role_path': self.driver}

    def read_output(self, name, limit):
        self.reads[name] = self.reads.get(name, 0) + 1
        body = self.outputs[name]
        if self.drift == 'output' and name == 'version.stdout' and self.reads[name] > 1:
            body += b' changed'
        return body, {'path': str(self.root / name), 'sha256': hashlib.sha256(body).hexdigest(),
                      'identity': [1, 2, 3, 4, len(body), 6, 7], 'bytes': len(body)}

    def write_output(self, name, body):
        if name in self.outputs:
            raise FileExistsError(name)
        self.outputs[name] = body
        return self.read_output(name, toolchain.MAX_OUTPUT)[1]

    def run(self, label, argv):
        self.calls.append((label, argv))
        dependencies = (toolchain.TARGET + ': ' + self.source + ' ' + self.header + '\n').encode()
        stdout = dependencies if label == 'dependencies' else b'fixture compiler version\n'
        if label == 'preprocess':
            stdout = ('\n'.join(MARKERS) + '\n').encode()
            self.outputs['preprocess.d'] = dependencies
            if self.failure == 'dependency_set':
                self.outputs['preprocess.d'] = dependencies.replace(self.header.encode(), b'/other/header.h')
            if self.failure == 'macro':
                stdout = stdout.replace(b'((1 << 8) + 9L)', b'SYS_pidfd_open')
        if label == 'object':
            self.outputs['probe.o'] = object_bytes()
            stdout = b''
            if self.drift == 'cpp':
                self.outputs['captured.i'] += b' changed'
        self.outputs[label + '.stdout'], self.outputs[label + '.stderr'] = stdout, b''
        failed = self.failure == label or self.failure == 'timeout_' + label
        return {'label': label, 'argv': argv, 'status': 'failed' if failed else 'success',
                'returncode': None if self.failure == 'timeout_' + label else (1 if failed else 0),
                'timed_out': self.failure == 'timeout_' + label,
                'direct_child_pid': 42, 'kill_attempted': self.failure == 'timeout_' + label,
                'reap_completed': self.failure != 'timeout_' + label,
                'kill_error': None, 'reap_error': None, 'descendant_cleanup_verified': False,
                'stdout': self.read_output(label + '.stdout', toolchain.MAX_OUTPUT)[1],
                'stderr': self.read_output(label + '.stderr', toolchain.MAX_OUTPUT)[1]}


class ObserverFixture:
    """Real owned file boundaries with an explicitly injected compiler result."""
    def __enter__(self):
        self.stack = ExitStack()
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.source = self.directory / 'observer.py'
        self.source.write_bytes(b'# Injected observer file-binding fixture only.\n')
        self.probe = self.directory / 'frontier_v8_c_toolchain_probe.c'
        self.probe.write_bytes((ROOT / 'scripts' / self.probe.name).read_bytes())
        self.helper_path = self.directory / 'frontier_v8_containment_capability.py'
        self.helper_path.write_bytes((ROOT / 'scripts' / self.helper_path.name).read_bytes())
        self.bootstrap = self.directory / 'bootstrap'
        self.bootstrap.write_bytes(b'injected bootstrap bytes')
        with patch.object(toolchain, '__file__', str(self.source)):
            self.helper = toolchain.load_identity_helper()
        self.attempt = self.directory / 'attempt'
        self.request_path = self.directory / 'request.json'
        self.request = {
            'schema_version': 1, 'scope': toolchain.SCOPE, 'nonce': secrets.token_hex(32),
            'observer_sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(),
            'c_probe_sha256': hashlib.sha256(self.probe.read_bytes()).hexdigest(),
            'identity_helper_sha256': toolchain.HELPER_SHA,
            'attempt_directory': str(self.attempt),
            'host': {'node_alias': 'N1-1', 'hostname': 'fixture-host', 'boot_id': BOOT, 'uid': os.getuid()},
            'bootstrap': {'executable': str(self.bootstrap),
                          'sha256': hashlib.sha256(self.bootstrap.read_bytes()).hexdigest(),
                          'version': list(sys.version_info[:3])}}
        self.write_request()
        self.pipeline = Mock(return_value={**toolchain.AUTHORITY,
                                           **dict.fromkeys(toolchain.SUCCESS_FIELDS, True), 'status': 'success'})
        for target, attribute, value in (
                (toolchain, '__file__', str(self.source)),
                (toolchain, 'load_identity_helper', Mock(return_value=self.helper)),
                (toolchain, 'run_toolchain', self.pipeline),
                (toolchain, 'CompilerBackend', Mock()),
                (toolchain.sys, 'flags', SimpleNamespace(isolated=1, no_site=1)),
                (toolchain.sys, 'dont_write_bytecode', True),
                (toolchain.sys, 'platform', 'linux'),
                (toolchain.sys, 'executable', str(self.bootstrap)),
                (toolchain.os, 'uname', Mock(return_value=SimpleNamespace(nodename='fixture-host'))),
                (self.helper, 'capture_self_identity', Mock(side_effect=lambda: own_identity()))):
            self.stack.enter_context(patch.object(target, attribute, value))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def write_request(self):
        body = json.dumps(self.request, sort_keys=True).encode()
        self.request_path.write_bytes(body)
        self.request_sha = hashlib.sha256(body).hexdigest()

    def observe(self):
        return toolchain.observe(str(self.request_path), self.request_sha)

    @property
    def marker(self):
        return self.attempt.with_name(self.attempt.name + '.consumed.json')


class CToolchainTests(unittest.TestCase):
    def assert_no_authority(self, value):
        for key in ('native_C_runtime_ABI_observed', 'own_pidfd_operations_verified',
                    'functional_containment_verified', 'containment_available',
                    'execution_available', 'resource_authority', 'model_runtime_ABI_observed'):
            self.assertIs(value[key], False)

    def test_dependencies_accept_only_fixed_target_source_and_absolute_headers(self):
        source = '/owned/probe.c'
        body = (b'frontier_v8_source_dependencies: /owned/probe.c ' + bytes((92, 10))
                + b' /usr/include/header.h /usr/include/next.h\n')
        self.assertEqual(set(toolchain.parse_dependencies(body, source)),
                         {source, '/usr/include/header.h', '/usr/include/next.h'})

    def test_dependencies_refuse_ambiguous_duplicate_unsafe_and_virtual_paths(self):
        source = '/owned/probe.c'
        for body in (
                b'wrong_target: /owned/probe.c /usr/include/header.h\n',
                b'frontier_v8_source_dependencies: /usr/include/header.h\n',
                b'frontier_v8_source_dependencies: /owned/probe.c /owned/probe.c\n',
                b'frontier_v8_source_dependencies: /owned/probe.c relative.h\n',
                b'frontier_v8_source_dependencies: /owned/probe.c /tmp/../header.h\n',
                b'frontier_v8_source_dependencies: /owned/probe.c /proc/self/fd/0\n',
                b'frontier_v8_source_dependencies: /owned/probe.c /dev/zero\n',
                b'frontier_v8_source_dependencies: /owned/probe.c /usr/include/escaped\\ header.h\n',
                b'frontier_v8_source_dependencies: /owned/probe.c /usr/include/header.h\0\n',
                b'frontier_v8_source_dependencies: /owned/probe.c\nother: /other.h\n'):
            with self.subTest(body=body), self.assertRaises((ValueError, OSError)):
                toolchain.parse_dependencies(body, source)

    def test_cpp_markers_preserve_opaque_expanded_expression_and_target_values(self):
        facts = toolchain.parse_cpp_facts(('\n'.join(MARKERS) + '\n').encode())
        self.assertEqual(facts, {'SYS_pidfd_open_expression': '((1 << 8) + 9L)',
                                'target_int_bytes': 4, 'target_long_bytes': 8,
                                'target_pointer_bytes': 8, 'target_char_bits': 8,
                                'target_byte_order': 1234})

    def test_cpp_missing_duplicate_or_unexpanded_marker_is_terminal(self):
        for index in range(len(MARKERS)):
            for rows in (MARKERS[:index] + MARKERS[index + 1:], MARKERS + (MARKERS[index],)):
                with self.subTest(index=index, rows=rows), self.assertRaises(ValueError):
                    toolchain.parse_cpp_facts(('\n'.join(rows) + '\n').encode())
        for token in ('SYS_pidfd_open', '__NR_pidfd_open', 'unknown_constant'):
            rows = (MARKERS[0].replace('((1 << 8) + 9L)', token),) + MARKERS[1:]
            with self.subTest(token=token), self.assertRaises(ValueError):
                toolchain.parse_cpp_facts(('\n'.join(rows) + '\n').encode())

    def test_elf_descriptor_reports_rel_object_without_architecture_or_runtime_inference(self):
        for elf_class, data, machine in ((1, 1, 3), (2, 1, 62), (2, 2, 183)):
            with self.subTest(elf_class=elf_class, data=data, machine=machine):
                self.assertEqual(toolchain.parse_elf_object(object_bytes(
                    elf_class=elf_class, data=data, machine=machine)),
                    {'elf_class': elf_class, 'data_encoding': data,
                     'machine': machine, 'elf_type': 1})

    def test_elf_descriptor_refuses_truncation_nonobject_and_unsupported_encoding(self):
        for body in (b'\x7fELF', b'not an object', object_bytes(kind=2), object_bytes(kind=3),
                     object_bytes(elf_class=3), object_bytes(data=0)):
            with self.subTest(body=body), self.assertRaises(ValueError):
                toolchain.parse_elf_object(body)

    def test_pipeline_compiles_captured_cpp_only_and_never_links_or_runs_product(self):
        backend = FakeCompilerBackend(Path('/fixture/output'), '/owned/probe.c')
        result = toolchain.run_toolchain(Path('/owned/probe.c'), backend)
        self.assertEqual(result['status'], 'success', result)
        self.assert_no_authority(result)
        self.assertTrue(all(result[key] is True for key in toolchain.SUCCESS_FIELDS))
        self.assertEqual([call[0] for call in backend.calls],
                         ['resolve', 'version', 'dependencies', 'preprocess', 'object'])
        object_argv = backend.calls[-1][1]
        self.assertIn('-c', object_argv)
        self.assertEqual(object_argv[object_argv.index('-x') + 1], 'cpp-output')
        self.assertIn('/fixture/output/captured.i', object_argv)
        self.assertNotIn('/owned/probe.c', object_argv)
        self.assertEqual(backend.outputs['captured.i'], backend.outputs['preprocess.stdout'])
        self.assertEqual(result['product_link_or_execution_attempts'], 0)
        self.assertEqual(result['pidfd_or_syscall_entry_attempts'], 0)
        self.assertIs(result['complete_toolchain_execution_closure_authenticated'], False)

    def test_pipeline_missing_compiler_nonzero_and_timeout_are_terminal(self):
        for failure in ('missing', 'version', 'dependencies', 'preprocess', 'object', 'timeout_preprocess'):
            with self.subTest(failure=failure):
                backend = FakeCompilerBackend(Path('/fixture/output'), '/owned/probe.c', failure=failure)
                result = toolchain.run_toolchain(Path('/owned/probe.c'), backend)
                self.assertEqual(result['status'], 'failed')
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is False for key in toolchain.SUCCESS_FIELDS))
                labels = [call[0] for call in backend.calls]
                self.assertEqual(len(labels), len(set(labels)))
                if failure == 'missing':
                    self.assertEqual(labels, ['resolve'])
                else:
                    self.assertEqual(labels[-1], failure.removeprefix('timeout_'))

    def test_pipeline_header_driver_output_and_captured_cpp_drift_fail(self):
        for drift in ('header', 'driver', 'output', 'cpp'):
            with self.subTest(drift=drift):
                backend = FakeCompilerBackend(Path('/fixture/output'), '/owned/probe.c', drift=drift)
                result = toolchain.run_toolchain(Path('/owned/probe.c'), backend)
                self.assertEqual(result['status'], 'failed')
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is False for key in toolchain.SUCCESS_FIELDS))

    def test_pipeline_dependency_mismatch_or_unexpanded_macro_stops_before_object(self):
        for failure in ('dependency_set', 'macro'):
            with self.subTest(failure=failure):
                backend = FakeCompilerBackend(Path('/fixture/output'), '/owned/probe.c', failure=failure)
                result = toolchain.run_toolchain(Path('/owned/probe.c'), backend)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual([call[0] for call in backend.calls],
                                 ['resolve', 'version', 'dependencies', 'preprocess'])

    def test_request_binds_exact_nine_fields_raw_hash_source_probe_and_bootstrap(self):
        with ObserverFixture() as fixture:
            def parse(body, expected=None):
                return toolchain.parse_request(body, expected or hashlib.sha256(body).hexdigest(),
                    fixture.request['observer_sha256'], fixture.request['c_probe_sha256'], fixture.helper)
            body = fixture.request_path.read_bytes()
            self.assertEqual(parse(body), fixture.request)
            for key, value in (('schema_version', True), ('scope', 'old-scope'), ('nonce', 'short'),
                    ('observer_sha256', '0' * 64), ('c_probe_sha256', '0' * 64),
                    ('identity_helper_sha256', '0' * 64), ('extra', True),
                    ('attempt_directory', '/proc/self/fd/0'), ('attempt_directory', '/tmp/../unsafe'),
                    ('host', {**fixture.request['host'], 'uid': True}),
                    ('bootstrap', {**fixture.request['bootstrap'], 'executable': '/dev/null'})):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    parse(json.dumps({**fixture.request, key: value}).encode())
            for changed in (body.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'),
                            body.replace(b'"schema_version": 1', b'"schema_version": NaN')):
                with self.subTest(body=changed), self.assertRaises(ValueError):
                    parse(changed)
            with self.assertRaises(ValueError):
                parse(body + b' ', fixture.request_sha)

    def test_observer_prevalidation_failure_never_consumes_or_invokes_compiler(self):
        for change in ('source', 'probe', 'helper', 'bootstrap', 'host', 'request_symlink'):
            with self.subTest(change=change), ObserverFixture() as fixture:
                if change in ('source', 'probe', 'helper', 'bootstrap'):
                    path = getattr(fixture, 'helper_path' if change == 'helper' else change)
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

    def test_observer_success_has_no_authority_and_cannot_reconsume(self):
        with ObserverFixture() as fixture:
            result = fixture.observe()
            self.assertEqual(result['status'], 'compiler_header_target_observed', result)
            self.assert_no_authority(result)
            self.assertTrue(all(result[key] is True for key in toolchain.SUCCESS_FIELDS))
            self.assertIs(result['input_and_self_identity_postvalidation_passed'], True)
            self.assertEqual(json.loads((fixture.attempt / 'receipt.json').read_bytes()), result)
            marker = fixture.marker.read_bytes()
            with self.assertRaises((ValueError, OSError)):
                fixture.observe()
            self.assertEqual(fixture.pipeline.call_count, 1)
            self.assertEqual(fixture.marker.read_bytes(), marker)

    def test_observer_compiler_failure_and_input_self_marker_drift_retain_failed_receipt(self):
        for failure in ('compiler', 'input', 'self', 'marker'):
            with self.subTest(failure=failure), ObserverFixture() as fixture:
                success = fixture.pipeline.return_value
                if failure == 'compiler':
                    fixture.pipeline.return_value = {**toolchain.AUTHORITY,
                        **dict.fromkeys(toolchain.SUCCESS_FIELDS, False), 'status': 'failed'}
                elif failure == 'self':
                    fixture.helper.capture_self_identity.side_effect = [own_identity(),
                        {**own_identity(), 'start_ticks': 101}]
                else:
                    def pipeline(*args):
                        path = fixture.source if failure == 'input' else fixture.marker
                        path.write_bytes(path.read_bytes() + b' changed')
                        return success
                    fixture.pipeline.side_effect = pipeline
                result = fixture.observe()
                self.assertEqual(result['status'], 'failed')
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is False for key in toolchain.SUCCESS_FIELDS))
                self.assertTrue(fixture.marker.exists())
                self.assertEqual(json.loads((fixture.attempt / 'receipt.json').read_bytes()), result)
                self.assertIs(result['input_and_self_identity_postvalidation_passed'], failure == 'compiler')

    def test_backend_cc_role_is_controlled_and_missing_role_has_no_fallback(self):
        helper = toolchain.load_identity_helper()
        backend = toolchain.CompilerBackend(helper, Path('/unused'), -1)
        with patch.object(toolchain.shutil, 'which', return_value=None) as which:
            with self.assertRaises(ValueError):
                backend.resolve_compiler()
        which.assert_called_once_with('cc', path='/usr/bin:/bin')

    def test_backend_raw_streams_and_environment_are_bound_to_direct_child(self):
        helper = toolchain.load_identity_helper()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            (directory / 'tmp').mkdir()
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                backend = toolchain.CompilerBackend(helper, directory, fd)
                child = Mock(pid=42)
                child.wait.return_value = 0
                def popen(argv, **kwargs):
                    self.assertEqual(argv, ['/fixture/cc', '--version'])
                    self.assertEqual(kwargs['env'], {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
                        'TMPDIR': str(directory / 'tmp'), 'CUDA_VISIBLE_DEVICES': '', 'NVIDIA_VISIBLE_DEVICES': 'none'})
                    self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
                    self.assertTrue(kwargs['close_fds'])
                    kwargs['stdout'].write(b'fixture compiler version\n')
                    kwargs['stderr'].write(b'fixture diagnostics\n')
                    return child
                with patch.dict(os.environ, {'CPATH': '/untrusted/include', 'LD_PRELOAD': '/untrusted.so'}), \
                        patch.object(toolchain.subprocess, 'Popen', side_effect=popen):
                    result = backend.run('version', ['/fixture/cc', '--version'])
                self.assertEqual(result['status'], 'success')
                self.assertEqual((directory / 'version.stdout').read_bytes(), b'fixture compiler version\n')
                self.assertEqual(result['stdout']['sha256'], hashlib.sha256(b'fixture compiler version\n').hexdigest())
                child.wait.assert_called_once_with(timeout=30)
                child.kill.assert_not_called()
                self.assertIs(result['descendant_cleanup_verified'], False)
            finally:
                os.close(fd)

    def test_backend_timeout_records_one_direct_kill_and_bounded_reap_or_unknown(self):
        helper = toolchain.load_identity_helper()
        for unknown in (False, True):
            with self.subTest(unknown=unknown), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary).resolve()
                fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    backend = toolchain.CompilerBackend(helper, directory, fd)
                    child = Mock(pid=42)
                    child.wait.side_effect = [subprocess.TimeoutExpired(['fixture'], 30),
                        subprocess.TimeoutExpired(['fixture'], 2) if unknown else -9]
                    if unknown:
                        child.kill.side_effect = ProcessLookupError('fixture child unavailable')
                    with patch.object(toolchain.subprocess, 'Popen', return_value=child):
                        result = backend.run('timeout', ['/fixture/cc'])
                    self.assertEqual(result['status'], 'failed')
                    self.assertIs(result['timed_out'], True)
                    self.assertIs(result['kill_attempted'], True)
                    child.kill.assert_called_once_with()
                    self.assertEqual([call.kwargs for call in child.wait.call_args_list],
                                     [{'timeout': 30}, {'timeout': 2}])
                    self.assertIs(result['reap_completed'], not unknown)
                    self.assertIs(result['descendant_cleanup_verified'], False)
                    if unknown:
                        self.assertEqual(result['kill_error']['type'], 'ProcessLookupError')
                        self.assertEqual(result['reap_error']['type'], 'TimeoutExpired')
                finally:
                    os.close(fd)

    @unittest.skipUnless(sys.platform == 'linux', 'Real compiler/header/object pipeline requires Ubuntu Linux CI')
    def test_real_linux_pipeline_compiles_fixed_tu_to_bound_object_without_execution(self):
        helper = toolchain.load_identity_helper()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            (directory / 'tmp').mkdir()
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                result = toolchain.run_toolchain(ROOT / 'scripts/frontier_v8_c_toolchain_probe.c',
                                                toolchain.CompilerBackend(helper, directory, fd))
                self.assertEqual(result['status'], 'success', result)
                self.assert_no_authority(result)
                self.assertTrue(all(result[key] is True for key in toolchain.SUCCESS_FIELDS))
                self.assertEqual([command['label'] for command in result['commands']],
                                 ['version', 'dependencies', 'preprocess', 'object'])
                self.assertEqual((directory / 'captured.i').read_bytes(), (directory / 'preprocess.stdout').read_bytes())
                self.assertEqual(result['object']['sha256'], hashlib.sha256((directory / 'probe.o').read_bytes()).hexdigest())
                self.assertEqual(result['object']['elf_type'], 1)
                self.assertEqual(result['product_link_or_execution_attempts'], 0)
                self.assertEqual(result['pidfd_or_syscall_entry_attempts'], 0)
                self.assertTrue(all(command['kill_attempted'] is False for command in result['commands']))
            finally:
                os.close(fd)

    @unittest.skipUnless(sys.platform == 'linux', 'Real isolated compiler CLI requires Ubuntu Linux CI')
    def test_real_linux_isolated_cli_returns_exact_receipt_and_no_runtime_authority(self):
        source = ROOT / 'scripts/frontier_v8_c_toolchain.py'
        probe = ROOT / 'scripts/frontier_v8_c_toolchain_probe.c'
        helper = toolchain.load_identity_helper()
        executable = Path(os.path.realpath(sys.executable))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            attempt, request_path = directory / 'attempt', directory / 'request.json'
            request = {'schema_version': 1, 'scope': toolchain.SCOPE, 'nonce': secrets.token_hex(32),
                'observer_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'c_probe_sha256': hashlib.sha256(probe.read_bytes()).hexdigest(),
                'identity_helper_sha256': toolchain.HELPER_SHA, 'attempt_directory': str(attempt),
                'host': {'node_alias': 'N1-1', 'hostname': os.uname().nodename,
                         'boot_id': helper.capture_self_identity()['boot_id'], 'uid': os.getuid()},
                'bootstrap': {'executable': str(executable), 'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
                              'version': list(sys.version_info[:3])}}
            body = json.dumps(request, sort_keys=True).encode()
            request_path.write_bytes(body)
            completed = subprocess.run([str(executable), '-B', '-I', '-S', str(source), '--observe-c-toolchain',
                '--request', str(request_path), '--expected-request-sha256', hashlib.sha256(body).hexdigest()],
                capture_output=True, timeout=180, check=False)
            self.assertEqual(completed.returncode, 0, (completed.stdout, completed.stderr))
            self.assertEqual(completed.stderr, b'')
            result = json.loads(completed.stdout)
            self.assertEqual(result['status'], 'compiler_header_target_observed')
            self.assertEqual(json.loads((attempt / 'receipt.json').read_bytes()), result)
            self.assert_no_authority(result)
            self.assertTrue(all(result[key] is True for key in toolchain.SUCCESS_FIELDS))
            self.assertIs(result['input_and_self_identity_postvalidation_passed'], True)
            self.assertEqual(result['product_link_or_execution_attempts'], 0)
            self.assertEqual(result['pidfd_or_syscall_entry_attempts'], 0)
            self.assertEqual(json.loads(attempt.with_name('attempt.consumed.json').read_bytes())['nonce'], request['nonce'])

    def test_execute_refuses_before_parser_helper_request_or_compiler(self):
        with patch.object(toolchain, 'load_identity_helper') as helper, \
                patch.object(toolchain, 'observe') as observe, \
                patch.object(toolchain, 'CompilerBackend') as backend, \
                patch.object(toolchain.argparse, 'ArgumentParser') as parser:
            for argv in (['--execute'], ['--request', '/missing', '--execute=true']):
                with self.assertRaises((ValueError, OSError)):
                    toolchain.main(argv)
            for mocked in (helper, observe, backend, parser):
                mocked.assert_not_called()


if __name__ == '__main__':
    unittest.main()
