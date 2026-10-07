"""Presence and file-boundary fixtures; no native or containment operations."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import secrets
import subprocess
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_containment_capability as capability


BOOT = 'b961bd5d-1d24-4c68-a500-d204ecbfb3d9'


def present_modules():
    forbidden = Mock(side_effect=AssertionError('Containment API must never be called'))
    return (SimpleNamespace(pidfd_open=forbidden),
            SimpleNamespace(pidfd_send_signal=forbidden), SimpleNamespace(poll=forbidden), forbidden)


def identity():
    return {'boot_id': BOOT, 'pid': 42, 'ppid': 7, 'pgrp': 42, 'session': 42,
            'start_ticks': 100, 'state': 'R', 'uid': os.getuid(), 'euid': os.getuid(),
            'proc_uids': [os.getuid()] * 4,
            'parent_identity_verified': False, 'ancestry_verified': False}


class CapabilityTests(unittest.TestCase):
    def assert_no_authority(self, value):
        self.assertTrue(value['presence_only'])
        for key in ('functional_containment_verified', 'containment_available',
                    'execution_available', 'resource_authority'):
            self.assertIs(value[key], False)

    def fixture(self, temp):
        root = Path(temp).resolve()
        source, executable = root / 'observer.py', root / 'python'
        source.write_bytes(b'# fixture source, never executed\n')
        executable.write_bytes(b'fixture executable, never executed\n')
        request_path = root / 'request.json'
        request = {'schema_version': 1, 'scope': capability.SCOPE, 'nonce': 'a' * 64,
                   'observer_sha256': capability.digest(source.read_bytes()),
                   'attempt_directory': str(root / 'attempt'),
                   'host': {'node_alias': 'N1-1', 'hostname': 'fixture-host', 'boot_id': BOOT,
                            'uid': os.getuid()},
                   'bootstrap': {'executable': str(executable),
                                 'sha256': capability.digest(executable.read_bytes()),
                                 'version': list(sys.version_info[:3])}}
        self.save_request(request_path, request)
        return source, executable, request_path, request

    @staticmethod
    def save_request(path, request):
        path.write_text(json.dumps(request), encoding='utf-8')
        return capability.digest(path.read_bytes())

    def observer_patches(self, source, executable, **kwargs):
        stack = ExitStack()
        stack.enter_context(patch.object(capability, '__file__', str(source)))
        stack.enter_context(patch.object(capability.sys, 'executable', str(executable)))
        stack.enter_context(patch.object(capability.sys, 'flags',
                                         SimpleNamespace(isolated=1, no_site=1)))
        stack.enter_context(patch.object(capability.sys, 'dont_write_bytecode', True))
        stack.enter_context(patch.object(capability.os, 'uname',
                                         return_value=SimpleNamespace(nodename='fixture-host')))
        stack.enter_context(patch.object(capability, 'capture_self_identity',
                                         **(kwargs or {'return_value': identity()})))
        return stack

    def observe_fixture(self, source, executable, request_path, **kwargs):
        with self.observer_patches(source, executable, **kwargs):
            return capability.observe(str(request_path), capability.digest(request_path.read_bytes()))

    def test_each_presence_predicate_is_reported_independently(self):
        for missing in ('os.pidfd_open', 'signal.pidfd_send_signal', 'select.poll'):
            with self.subTest(missing=missing):
                os_module, signal_module, select_module, forbidden = present_modules()
                module, attribute = {'os.pidfd_open': (os_module, 'pidfd_open'),
                                     'signal.pidfd_send_signal': (signal_module, 'pidfd_send_signal'),
                                     'select.poll': (select_module, 'poll')}[missing]
                delattr(module, attribute)
                row = capability.prerequisite_observation('linux', 1000, 1000,
                        os_module=os_module, signal_module=signal_module, select_module=select_module)
                self.assertEqual(row['missing_attributes'], [missing])
                self.assertFalse(row['native_prerequisite_predicate_passed'])
                self.assert_no_authority(row)
                forbidden.assert_not_called()
        os_module, signal_module, select_module, forbidden = present_modules()
        for platform_value, uid, euid, failed in (
                ('darwin', 1000, 1000, 'sys.platform_is_linux'),
                ('linux', 1000, 2000, 'uid_matches_euid')):
            row = capability.prerequisite_observation(platform_value, uid, euid,
                    os_module=os_module, signal_module=signal_module, select_module=select_module)
            self.assertFalse(row['predicates'][failed])
            self.assertEqual(row['missing_attributes'], [])
            self.assert_no_authority(row)
        forbidden.assert_not_called()

    def test_all_present_and_noncallable_preserve_hasattr_without_authority(self):
        for value in (None, 0, Mock(side_effect=AssertionError('must not call'))):
            with self.subTest(value=value):
                row = capability.prerequisite_observation('linux', 1, 1,
                        os_module=SimpleNamespace(pidfd_open=value),
                        signal_module=SimpleNamespace(pidfd_send_signal=value),
                        select_module=SimpleNamespace(poll=value))
                self.assertTrue(row['native_prerequisite_predicate_passed'])
                self.assertEqual(row['missing_attributes'], [])
                self.assertEqual(row['attributes']['select.poll']['callable'], callable(value))
                self.assert_no_authority(row)
                if isinstance(value, Mock):
                    value.assert_not_called()

    def test_recursive_duplicate_malformed_nonfinite_and_stale_requests_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            source, _, path, request = self.fixture(temp)
            for body, expected in ((b'{"x":1,"x":2}', 'Duplicate'),
                                   (b'{"outer":{"x":1,"x":2}}', 'Duplicate'),
                                   (b'\xff', 'Malformed'), (b'{', 'Malformed'),
                                   (b'{"x":NaN}', 'Nonfinite')):
                with self.subTest(body=body), self.assertRaisesRegex(capability.CapabilityError, expected):
                    capability.parse_request(body, capability.digest(body), request['observer_sha256'])
            body = path.read_bytes()
            with self.assertRaisesRegex(capability.CapabilityError, 'Request bytes'):
                capability.parse_request(body, '0' * 64, request['observer_sha256'])
            with self.assertRaisesRegex(capability.CapabilityError, 'Observer source'):
                capability.parse_request(body, capability.digest(body), '0' * 64)
            request['extra'] = 'refused'
            self.save_request(path, request)
            with self.assertRaisesRegex(capability.CapabilityError, 'Exact presence'):
                capability.parse_request(path.read_bytes(), capability.digest(path.read_bytes()),
                                         capability.digest(source.read_bytes()))

    def test_self_stat_handles_parentheses_and_uid_rows_and_birth(self):
        fields = ['R', '7', '42', '42'] + ['0'] * 15 + ['100']
        parsed = capability.parse_self_identity(BOOT.encode(),
                   ('42 (comm with ) parentheses) ' + ' '.join(fields)).encode(),
                   b'Name:\tfixture\nUid:\t1000\t1000\t1000\t1000\n', 42, 7, 1000, 1000)
        self.assertEqual(parsed['start_ticks'], 100)
        self.assertEqual(parsed['ppid'], 7)
        self.assertFalse(parsed['parent_identity_verified'])
        self.assertFalse(parsed['ancestry_verified'])
        for stat_body, status_body in ((b'42 (bad) R', b'Uid: 1000 1000 1000 1000'),
                                      (b'42 (ok) ' + ' '.join(fields).encode(), b'Uid: 9 9 9 9')):
            with self.assertRaises(capability.CapabilityError):
                capability.parse_self_identity(BOOT.encode(), stat_body, status_body, 42, 7, 1000, 1000)

    def test_missing_attribute_is_consumed_success_with_false_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            source, executable, path, request = self.fixture(temp)
            with self.observer_patches(source, executable), patch.object(capability.sys, 'platform', 'linux'), \
                    patch.object(capability.signal, 'pidfd_send_signal', create=True, new=None):
                # Removing the actual module attribute exercises exact absence.
                original = capability.signal.pidfd_send_signal
                del capability.signal.pidfd_send_signal
                try:
                    receipt = capability.observe(str(path), capability.digest(path.read_bytes()))
                finally:
                    capability.signal.pidfd_send_signal = original
            self.assertEqual(receipt['status'], 'presence_observed')
            self.assertIn('signal.pidfd_send_signal', receipt['prerequisites']['missing_attributes'])
            self.assert_no_authority(receipt)
            self.assert_no_authority(receipt['prerequisites'])
            self.assertFalse(receipt['native_reference']['body_executed'])
            root = Path(request['attempt_directory'])
            self.assertTrue(root.with_name('attempt.consumed.json').is_file())
            self.assertEqual(json.loads((root / 'receipt.json').read_text()), receipt)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertEqual((root / 'receipt.json').stat().st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(capability.CapabilityError, 'already exists'):
                self.observe_fixture(source, executable, path)

    def test_existing_root_or_marker_refuses_without_new_writes(self):
        for marker in (False, True):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as temp:
                source, executable, path, request = self.fixture(temp)
                root = Path(request['attempt_directory'])
                if marker:
                    root.with_name('attempt.consumed.json').write_text('immutable')
                else:
                    root.mkdir()
                before = sorted(Path(temp).iterdir())
                with self.assertRaisesRegex(capability.CapabilityError, 'already exists'):
                    self.observe_fixture(source, executable, path)
                self.assertEqual(sorted(Path(temp).iterdir()), before)

    def test_symlink_source_request_bootstrap_output_and_ancestor_refuse(self):
        for target in ('source', 'request', 'bootstrap', 'output', 'ancestor'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                source, executable, path, request = self.fixture(temp)
                root = Path(temp).resolve()
                if target in ('source', 'request', 'bootstrap'):
                    leaf = {'source': source, 'request': path, 'bootstrap': executable}[target]
                    original = leaf.with_name(leaf.name + '.original')
                    leaf.rename(original)
                    leaf.symlink_to(original)
                elif target == 'output':
                    Path(request['attempt_directory']).symlink_to(root, target_is_directory=True)
                else:
                    link = root / 'linked'
                    link.symlink_to(root, target_is_directory=True)
                    request['attempt_directory'] = str(link / 'attempt')
                    self.save_request(path, request)
                with self.assertRaises((capability.CapabilityError, OSError)):
                    self.observe_fixture(source, executable, path)
                self.assertFalse((root / 'attempt.consumed.json').exists())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            original = root / 'directory'
            original.mkdir()
            (original / 'input').write_bytes(b'bytes')
            link = root / 'linked'
            link.symlink_to(original, target_is_directory=True)
            with self.assertRaises(OSError):
                capability.read_regular(str(link / 'input'), 10)

    def test_wrong_uid_owner_source_bootstrap_host_and_overlap_refuse_before_writes(self):
        for field in ('source', 'bootstrap', 'host', 'overlap', 'version'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                source, executable, path, request = self.fixture(temp)
                if field == 'source':
                    source.write_bytes(b'changed')
                elif field == 'bootstrap':
                    executable.write_bytes(b'changed')
                elif field == 'host':
                    request['host']['hostname'] = 'different'
                elif field == 'overlap':
                    request['attempt_directory'] = str(source)
                else:
                    request['bootstrap']['version'] = [3, 1, 1]
                self.save_request(path, request)
                with self.assertRaises(capability.CapabilityError):
                    self.observe_fixture(source, executable, path)
                self.assertFalse((Path(temp).resolve() / 'attempt.consumed.json').exists())
        with tempfile.TemporaryDirectory() as temp:
            source, executable, path, _ = self.fixture(temp)
            with self.observer_patches(source, executable), \
                    patch.object(capability.os, 'geteuid', return_value=os.getuid() + 1), \
                    patch.object(capability, 'read_regular') as read:
                with self.assertRaisesRegex(capability.CapabilityError, 'privilege'):
                    capability.observe(str(path), 'a' * 64)
                read.assert_not_called()
            with self.assertRaisesRegex(capability.CapabilityError, 'Request owner'):
                capability.read_regular(str(path), 16384, owner=os.getuid() + 1)

    def test_postvalidation_failure_retains_consumed_failed_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            source, executable, path, request = self.fixture(temp)
            changed = {**identity(), 'boot_id': '00000000-0000-0000-0000-000000000000'}
            receipt = self.observe_fixture(source, executable, path, side_effect=[identity(), changed])
            self.assertEqual(receipt['status'], 'failed')
            self.assertIn('Self identity', receipt['error']['message'])
            self.assertFalse(receipt['input_and_self_identity_postvalidation_passed'])
            self.assert_no_authority(receipt)
            root = Path(request['attempt_directory'])
            self.assertTrue(root.with_name('attempt.consumed.json').exists())
            self.assertEqual(json.loads((root / 'receipt.json').read_text()), receipt)

    def test_nested_host_and_bootstrap_aliases_refuse_before_writes(self):
        for section, field, alias in (('host', 'uid', 'euid'),
                                      ('bootstrap', 'executable', 'realpath'),
                                      ('bootstrap', 'version', 'python_version')):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as temp:
                source, executable, path, request = self.fixture(temp)
                request[section][alias] = request[section].pop(field)
                self.save_request(path, request)
                with self.assertRaisesRegex(capability.CapabilityError, 'Exact .* binding'):
                    self.observe_fixture(source, executable, path)
                self.assertFalse((Path(temp).resolve() / 'attempt.consumed.json').exists())

    def test_designated_output_boundary_owner_refuses_before_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            source, executable, path, _ = self.fixture(temp)
            actual_fstat = os.fstat

            def changed_boundary(fd):
                info = actual_fstat(fd)
                if stat.S_ISDIR(info.st_mode):
                    return SimpleNamespace(st_uid=os.getuid() + 1)
                return info

            with self.observer_patches(source, executable), \
                    patch.object(capability.os, 'fstat', side_effect=changed_boundary):
                with self.assertRaisesRegex(capability.CapabilityError, 'boundary owner'):
                    capability.observe(str(path), capability.digest(path.read_bytes()))
            self.assertFalse((Path(temp).resolve() / 'attempt.consumed.json').exists())

    def test_consumed_mkdir_or_open_failure_retains_failed_sibling_receipt(self):
        for operation in ('mkdir', 'open'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temp:
                source, executable, path, request = self.fixture(temp)
                actual_open = os.open

                def fail_root_open(name, flags, *args, **kwargs):
                    if name == 'attempt' and flags & os.O_DIRECTORY:
                        raise OSError('fixture root open failure')
                    return actual_open(name, flags, *args, **kwargs)

                with self.observer_patches(source, executable), ExitStack() as stack:
                    if operation == 'mkdir':
                        stack.enter_context(patch.object(capability.os, 'mkdir',
                                            side_effect=OSError('fixture mkdir failure')))
                    else:
                        stack.enter_context(patch.object(capability.os, 'open', side_effect=fail_root_open))
                    receipt = capability.observe(str(path), capability.digest(path.read_bytes()))
                root = Path(request['attempt_directory'])
                self.assertEqual(receipt['status'], 'failed')
                self.assert_no_authority(receipt)
                self.assertTrue(root.with_name('attempt.consumed.json').exists())
                self.assertEqual(json.loads(root.with_name('attempt.failed-receipt.json').read_text()), receipt)

    def test_execute_refuses_before_parser_source_request_or_path_handling(self):
        with patch.object(capability, 'observe') as observe, \
                patch.object(capability, 'read_regular') as read, \
                patch.object(capability, 'normalized_path') as path, \
                patch.object(capability.argparse, 'ArgumentParser') as parser:
            for argv in (['--execute'], ['--request', '/missing', '--execute=true']):
                with self.assertRaisesRegex(capability.CapabilityError, 'Execution unavailable'):
                    capability.main(argv)
            for mocked in (observe, read, path, parser):
                mocked.assert_not_called()

    def test_main_stdout_contains_the_full_returned_presence_receipt(self):
        receipt = {**capability.AUTHORITY, 'status': 'presence_observed',
                   'prerequisites': {'native_prerequisite_predicate_passed': False},
                   'self_identity': identity(), 'observer': {'sha256': 'a' * 64}}
        with patch.object(capability, 'observe', return_value=receipt) as observe, \
                patch('builtins.print') as printed:
            result = capability.main(['--observe-cpu', '--request', '/fixture-request',
                                      '--expected-request-sha256', 'b' * 64])
        self.assertEqual(result, 0)
        observe.assert_called_once_with('/fixture-request', 'b' * 64)
        self.assertEqual(json.loads(printed.call_args.args[0]), receipt)

    def test_fixed_proc_reader_never_reads_parent_or_foreign_pid(self):
        with patch.object(capability, '_proc_bytes', side_effect=[BOOT.encode(),
                b'42 (fixture) R 7 42 42 ' + b'0 ' * 15 + b'100',
                b'Uid: 1000 1000 1000 1000']) as read, \
                patch.object(capability.os, 'getpid', return_value=42), \
                patch.object(capability.os, 'getppid', return_value=7), \
                patch.object(capability.os, 'getuid', return_value=1000), \
                patch.object(capability.os, 'geteuid', return_value=1000):
            capability.capture_self_identity()
            self.assertEqual([call.args[0] for call in read.call_args_list],
                             ['/proc/sys/kernel/random/boot_id', '/proc/self/stat', '/proc/self/status'])
        with self.assertRaisesRegex(capability.CapabilityError, 'Only fixed'):
            capability._proc_bytes('/proc/7/stat', 65536)

    def test_fixed_limits_and_normalized_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve() / 'large'
            path.write_bytes(b'abcd')
            with self.assertRaisesRegex(capability.CapabilityError, 'byte limit'):
                capability.read_regular(str(path), 3)
        for value in ('relative', '/tmp/../input', '/tmp//input', '/tmp/./input', '/tmp/input/', '/'):
            with self.subTest(value=value), self.assertRaises(capability.CapabilityError):
                capability.normalized_path(value)

    def test_generic_virtual_inputs_and_outputs_refuse_before_open(self):
        with patch.object(capability, 'open_parent') as parent, \
                patch.object(capability.os, 'open') as opened:
            for value in ('/proc', '/proc/self/stat', '/proc/123456/status',
                          '/proc/sys/kernel/random/boot_id', '/proc/attempt',
                          '/sys', '/sys/class/drm/card0', '/sys/attempt',
                          '/dev', '/dev/nvidia0', '/dev/null', '/dev/attempt'):
                with self.subTest(value=value), self.assertRaisesRegex(capability.CapabilityError, 'Generic virtual'):
                    capability.read_regular(value, capability.MAX_REQUEST_BYTES)
            parent.assert_not_called()
            opened.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux', 'Own-process proc fixture requires Linux')
    def test_real_linux_current_process_read_only_identity(self):
        with patch.object(capability.os, 'pidfd_open', create=True,
                           side_effect=AssertionError('No pidfd operation')) as pidfd, \
                patch.object(capability.signal, 'pidfd_send_signal', create=True,
                             side_effect=AssertionError('No signal operation')) as send, \
                patch.object(capability.select, 'poll', create=True,
                             side_effect=AssertionError('No poll operation')) as poll:
            row = capability.capture_self_identity()
            self.assertEqual(row['pid'], os.getpid())
            self.assertEqual(row['uid'], os.getuid())
            self.assertEqual(row['ppid'], os.getppid())
            self.assertGreater(row['start_ticks'], 0)
            self.assertFalse(row['ancestry_verified'])
            for mocked in (pidfd, send, poll):
                mocked.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux', 'Isolated file CLI fixture requires Linux')
    def test_real_linux_isolated_file_cli_with_fresh_synthetic_request(self):
        source = Path(capability.__file__).resolve()
        executable = Path(sys.executable).resolve()
        with tempfile.TemporaryDirectory() as temp:
            boundary = Path(temp).resolve()
            request_path, attempt = boundary / 'request.json', boundary / 'attempt'
            source_sha = capability.digest(source.read_bytes())
            request = {'schema_version': 1, 'scope': capability.SCOPE, 'nonce': secrets.token_hex(32),
                       'observer_sha256': source_sha, 'attempt_directory': str(attempt),
                       'host': {'node_alias': 'N1-1', 'hostname': os.uname().nodename,
                                'boot_id': capability.capture_self_identity()['boot_id'], 'uid': os.getuid()},
                       'bootstrap': {'executable': str(executable),
                                     'sha256': capability.digest(executable.read_bytes()),
                                     'version': list(sys.version_info[:3])}}
            request_sha = self.save_request(request_path, request)
            result = subprocess.run([str(executable), '-B', '-I', '-S', str(source), '--observe-cpu',
                                     '--request', str(request_path), '--expected-request-sha256', request_sha],
                                    capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            receipt = json.loads((attempt / 'receipt.json').read_bytes())
            marker = json.loads(attempt.with_name('attempt.consumed.json').read_bytes())
            self.assertEqual(summary, receipt)
            self.assertIn('predicates', summary['prerequisites'])
            self.assertEqual(summary['self_identity']['uid'], os.getuid())
            self.assertEqual(summary['observer']['sha256'], source_sha)
            for value in (summary, receipt, marker, receipt['prerequisites']):
                self.assert_no_authority(value)
            self.assertEqual(receipt['status'], 'presence_observed')
            self.assertEqual(receipt['observer'], {'file': str(source), 'sha256': source_sha})
            self.assertEqual(receipt['request_sha256'], request_sha)
            self.assertEqual(marker['observer_sha256'], source_sha)
            self.assertEqual(marker['request_sha256'], request_sha)
            self.assertTrue(receipt['input_and_self_identity_postvalidation_passed'])
            self.assertEqual(receipt['python']['executable_resolved'], str(executable))
            self.assertEqual(receipt['python']['isolated'], 1)
            self.assertEqual(receipt['python']['no_site'], 1)
            self.assertTrue(receipt['python']['dont_write_bytecode'])
            self.assertFalse(receipt['native_reference']['body_executed'])
            self.assertFalse(receipt['self_identity']['ancestry_verified'])


if __name__ == '__main__':
    unittest.main()
