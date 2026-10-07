"""Own-descriptor fixtures; no foreign process, signal or model operation."""
from contextlib import ExitStack
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_pidfd_selfcheck as selfcheck


BOOT = '00000000-0000-0000-0000-000000000001'
ROOT = Path(__file__).resolve().parents[1]


def own_identity():
    return {'boot_id': BOOT, 'pid': 42, 'ppid': 7, 'pgrp': 42, 'session': 42,
            'start_ticks': 100, 'state': 'R', 'uid': os.getuid(), 'euid': os.getuid(),
            'proc_uids': [os.getuid()] * 4, 'parent_identity_verified': False,
            'ancestry_verified': False}


class ObserverFixture:
    """Real file boundaries with injected host and descriptor observations."""
    def __enter__(self):
        self.stack = ExitStack()
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.source = self.directory / 'observer.py'
        self.source.write_bytes(b'# Injected observer file-binding fixture only.\n')
        self.helper_path = self.directory / 'frontier_v8_containment_capability.py'
        self.helper_path.write_bytes((ROOT / 'scripts' / self.helper_path.name).read_bytes())
        self.bootstrap = self.directory / 'bootstrap'
        self.bootstrap.write_bytes(b'injected bootstrap bytes')
        with patch.object(selfcheck, '__file__', str(self.source)):
            self.helper = selfcheck.load_identity_helper()
        self.attempt = self.directory / 'attempt'
        self.request_path = self.directory / 'request.json'
        self.request = {
            'schema_version': 1, 'scope': selfcheck.SCOPE, 'nonce': secrets.token_hex(32),
            'observer_sha256': hashlib.sha256(self.source.read_bytes()).hexdigest(),
            'identity_helper_sha256': selfcheck.HELPER_SHA,
            'attempt_directory': str(self.attempt),
            'host': {'node_alias': 'N1-1', 'hostname': 'fixture-host',
                     'boot_id': BOOT, 'uid': os.getuid()},
            'bootstrap': {'executable': str(self.bootstrap),
                          'sha256': hashlib.sha256(self.bootstrap.read_bytes()).hexdigest(),
                          'version': list(sys.version_info[:3])}}
        self.write_request()
        for target, attribute, value in (
                (selfcheck, '__file__', str(self.source)),
                (selfcheck, 'load_identity_helper', Mock(return_value=self.helper)),
                (selfcheck.sys, 'flags', SimpleNamespace(isolated=1, no_site=1)),
                (selfcheck.sys, 'dont_write_bytecode', True),
                (selfcheck.sys, 'platform', 'linux'),
                (selfcheck.sys, 'executable', str(self.bootstrap)),
                (selfcheck.os, 'uname', Mock(return_value=SimpleNamespace(nodename='fixture-host'))),
                (self.helper, 'capture_self_identity', Mock(side_effect=lambda: own_identity()))):
            self.stack.enter_context(patch.object(target, attribute, value))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def write_request(self):
        body = json.dumps(self.request, sort_keys=True).encode()
        self.request_path.write_bytes(body)
        self.request_sha = hashlib.sha256(body).hexdigest()

    def observe(self, backend_factory=None):
        factory = (lambda helper: FakeBackend()) if backend_factory is None else backend_factory
        return selfcheck.observe(str(self.request_path), self.request_sha, backend_factory=factory)

    @property
    def marker(self):
        return self.attempt.with_name(self.attempt.name + '.consumed.json')


class FakeBackend:
    """A call ledger distinguishes observations, close attempts and fallback."""
    def __init__(self, *, fd=11, open_errno=None, poll_result=None, fail=None,
                 fd_pid=42, provider_drift=False, closed=True, close_error=None):
        self.fd, self.open_errno = fd, open_errno
        self.poll_result = [] if poll_result is None else poll_result
        self.fail, self.fd_pid = fail, fd_pid
        self.provider_drift, self.closed = provider_drift, closed
        self.close_error, self.calls, self.provider_reads = close_error, [], 0

    def provenance(self):
        self.calls.append(('provenance',))
        self.provider_reads += 1
        if self.fail == 'provenance':
            raise ValueError('fixture provider unavailable')
        return {'address': 8192, 'provider_sha256': 'b' * 64,
                'provider_identity': [1, 2, 3 if self.provider_drift and self.provider_reads > 1 else 2]}

    def open_pidfd(self, pid):
        self.calls.append(('open', pid))
        if self.fail == 'open':
            raise OSError(errno.ENOSYS, 'fixture open failure')
        return self.fd, self.open_errno

    def fd_identity(self, fd):
        self.calls.append(('fd_identity', fd))
        if self.fail == 'fd_identity':
            raise ValueError('fixture fdinfo unavailable')
        return {'pid': self.fd_pid, 'nspid': [self.fd_pid]}

    def poll_self_fd(self, fd):
        self.calls.append(('poll', fd))
        if self.fail == 'poll':
            raise OSError(errno.EIO, 'fixture poll failure')
        return self.poll_result

    def close_fd(self, fd):
        self.calls.append(('close', fd))
        if self.close_error:
            raise self.close_error

    def is_fd_closed(self, fd):
        self.calls.append(('closed', fd))
        if self.fail == 'closed':
            raise OSError(errno.EIO, 'fixture fstat failure')
        return self.closed


class PidfdSelfcheckTests(unittest.TestCase):
    def assert_no_authority(self, value):
        for key in ('functional_containment_verified', 'containment_available',
                    'execution_available', 'resource_authority', 'model_runtime_ABI_observed'):
            self.assertIs(value[key], False)

    def assert_failed(self, value):
        self.assertEqual(value['status'], 'failed')
        self.assertIs(value['own_pidfd_operations_verified'], False)
        self.assert_no_authority(value)

    def test_provider_mapping_preserves_actual_non_libc_provider(self):
        row = selfcheck.parse_provider_mapping(
            b'00001000-00003000 r-xp 00000400 08:01 42 /opt/provider named.so\n', 0x2000)
        self.assertEqual(row, {'start': 0x1000, 'end': 0x3000, 'perms': 'r-xp',
                              'offset': 0x400, 'device_major': 8, 'device_minor': 1,
                              'inode': 42, 'lexical_path': '/opt/provider named.so'})

    def test_provider_mapping_refuses_unbound_ambiguous_deleted_or_anonymous(self):
        good = b'00001000-00003000 r-xp 00000000 08:01 42 /opt/provider.so\n'
        for raw, address in ((good, 0x3000), (good + good, 0x2000),
                             (good.replace(b'r-xp', b'r--p'), 0x2000),
                             (good.replace(b'/opt/provider.so', b'[vdso]'), 0x2000),
                             (good.replace(b'/opt/provider.so', b'/opt/provider.so (deleted)'), 0x2000),
                             (good.replace(b' 42 ', b' 0 '), 0x2000),
                             (b'malformed mapping\n', 0x2000)):
            with self.subTest(raw=raw, address=address), self.assertRaises((ValueError, OSError)):
                selfcheck.parse_provider_mapping(raw, address)

    def test_fdinfo_unique_current_pid_and_optional_descriptive_namespace(self):
        self.assertEqual(selfcheck.parse_fdinfo(b'pos:\t0\nPid:\t42\nNSpid:\t42 7\n', 42),
                         {'pid': 42, 'nspid': [42, 7]})
        self.assertEqual(selfcheck.parse_fdinfo(b'Pid:\t42\n', 42), {'pid': 42, 'nspid': None})
        for body in (b'Pid: 7\n', b'Pid: 42\nPid: 42\n', b'Pid: nope\n',
                     b'Pid: -1\n', b'no pid\n', b'Pid: 42\nNSpid: nope\n'):
            with self.subTest(body=body), self.assertRaises((ValueError, OSError)):
                selfcheck.parse_fdinfo(body, 42)

    def test_success_and_fd_zero_close_the_exact_returned_descriptor(self):
        for fd in (0, 11):
            with self.subTest(fd=fd):
                backend = FakeBackend(fd=fd)
                result = selfcheck.probe_self_pidfd(own_identity(), backend)
                self.assertEqual(result['status'], 'own_pidfd_operations_observed')
                self.assertIs(result['own_pidfd_operations_verified'], True)
                self.assertIs(result['c_abi_pidfd_call_attempted'], True)
                self.assert_no_authority(result)
                self.assertEqual(result['steps']['opened_fd'], fd)
                self.assertEqual([call for call in backend.calls if call[0] == 'open'], [('open', 42)])
                self.assertEqual([call for call in backend.calls if call[0] == 'poll'], [('poll', fd)])
                self.assertEqual([call for call in backend.calls if call[0] == 'close'], [('close', fd)])
                close_index = backend.calls.index(('close', fd))
                self.assertEqual(backend.calls[close_index + 1], ('closed', fd))
                self.assertEqual(backend.calls[-1], ('provenance',))

    def test_errno_negative_open_is_terminal_without_close_or_fallback(self):
        for number in (errno.ENOSYS, errno.EPERM, errno.EMFILE):
            with self.subTest(errno=number):
                backend = FakeBackend(fd=-1, open_errno=number)
                result = selfcheck.probe_self_pidfd(own_identity(), backend)
                self.assert_failed(result)
                self.assertEqual(sum(call[0] == 'open' for call in backend.calls), 1)
                self.assertFalse(any(call[0] in ('fd_identity', 'poll', 'close', 'closed') for call in backend.calls))
                self.assertEqual(result['open_errno'], number)

    def test_invalid_returned_fd_never_closes_a_guessed_descriptor(self):
        for fd in (-2, False, None):
            with self.subTest(fd=fd):
                backend = FakeBackend(fd=fd)
                self.assert_failed(selfcheck.probe_self_pidfd(own_identity(), backend))
                self.assertFalse(any(call[0] == 'close' for call in backend.calls))

    def test_wrong_descriptor_pid_refuses_poll_but_closes_once(self):
        backend = FakeBackend(fd_pid=7)
        self.assert_failed(selfcheck.probe_self_pidfd(own_identity(), backend))
        self.assertFalse(any(call[0] == 'poll' for call in backend.calls))
        self.assertEqual([call for call in backend.calls if call[0] == 'close'], [('close', 11)])

    def test_unexpected_poll_events_fail_and_close_once(self):
        for events in ([(11, 1)], [(11, 32)], [(7, 1)]):
            with self.subTest(events=events):
                backend = FakeBackend(poll_result=events)
                self.assert_failed(selfcheck.probe_self_pidfd(own_identity(), backend))
                self.assertEqual([call for call in backend.calls if call[0] == 'close'], [('close', 11)])

    def test_failures_after_open_keep_exactly_one_close_and_immediate_check(self):
        for stage in ('fd_identity', 'poll', 'closed'):
            with self.subTest(stage=stage):
                backend = FakeBackend(fail=stage)
                self.assert_failed(selfcheck.probe_self_pidfd(own_identity(), backend))
                index = backend.calls.index(('close', 11))
                self.assertEqual(backend.calls[index + 1], ('closed', 11))
                self.assertEqual(sum(call[0] == 'close' for call in backend.calls), 1)

    def test_close_EINTR_is_not_retried_and_cannot_pass(self):
        backend = FakeBackend(close_error=OSError(errno.EINTR, 'fixture close interrupted'))
        result = selfcheck.probe_self_pidfd(own_identity(), backend)
        self.assert_failed(result)
        self.assertIn('close_error', result)
        self.assertEqual([call for call in backend.calls if call[0] == 'close'], [('close', 11)])
        self.assertEqual(backend.calls[backend.calls.index(('close', 11)) + 1], ('closed', 11))

    def test_fd_still_open_and_provider_drift_cannot_be_verified(self):
        for kwargs in ({'closed': False}, {'provider_drift': True}):
            with self.subTest(kwargs=kwargs):
                backend = FakeBackend(**kwargs)
                self.assert_failed(selfcheck.probe_self_pidfd(own_identity(), backend))
                self.assertEqual(sum(call[0] == 'close' for call in backend.calls), 1)

    def test_provider_failure_before_open_has_no_descriptor_operation(self):
        backend = FakeBackend(fail='provenance')
        self.assert_failed(selfcheck.probe_self_pidfd(own_identity(), backend))
        self.assertEqual(backend.calls, [('provenance',)])

    def test_backend_named_process_export_has_exact_typed_prototype(self):
        function = Mock()
        with patch.object(selfcheck.sys, 'platform', 'linux'), \
                patch.object(selfcheck.ctypes, 'CDLL', return_value=SimpleNamespace(pidfd_open=function)) as library, \
                patch.object(selfcheck.ctypes, 'cast', return_value=SimpleNamespace(value=8192)) as cast:
            backend = selfcheck.SelfPidfdBackend(SimpleNamespace())
        library.assert_called_once_with(None, use_errno=True)
        self.assertEqual(function.argtypes, (ctypes.c_int, ctypes.c_uint))
        self.assertIs(function.restype, ctypes.c_int)
        cast.assert_called_once_with(function, ctypes.c_void_p)
        self.assertEqual(backend.address, 8192)
        with patch.object(selfcheck.sys, 'platform', 'linux'), \
                patch.object(selfcheck.ctypes, 'CDLL', return_value=SimpleNamespace()):
            with self.assertRaises(AttributeError):
                selfcheck.SelfPidfdBackend(SimpleNamespace())

    def test_backend_calls_only_current_pid_flags_zero_and_captures_errno_immediately(self):
        backend = selfcheck.SelfPidfdBackend.__new__(selfcheck.SelfPidfdBackend)
        ledger = []
        backend.function = Mock(side_effect=lambda *args: ledger.append(('call', args)) or -1)
        with patch.object(selfcheck.os, 'getpid', return_value=42), \
                patch.object(selfcheck.ctypes, 'set_errno', side_effect=lambda value: ledger.append(('set', value))), \
                patch.object(selfcheck.ctypes, 'get_errno', side_effect=lambda: ledger.append(('get',)) or errno.ENOSYS):
            for pid in (0, -1, 7, True, None, 2147483648):
                with self.subTest(pid=pid), self.assertRaises(ValueError):
                    backend.open_pidfd(pid)
            self.assertEqual(ledger, [])
            self.assertEqual(backend.open_pidfd(42), (-1, errno.ENOSYS))
        self.assertEqual(ledger, [('set', 0), ('call', (42, 0)), ('get',)])

    def test_provider_disk_identity_is_descriptive_and_must_match_mapping(self):
        helper = selfcheck.load_identity_helper()
        backend = selfcheck.SelfPidfdBackend.__new__(selfcheck.SelfPidfdBackend)
        backend.helper, backend.address = helper, 8192
        with tempfile.TemporaryDirectory() as temporary:
            provider = Path(temporary).resolve() / 'provider named.so'
            provider.write_bytes(b'\x7fELF injected provider bytes, never loaded')
            info = provider.stat()
            row = ('1000-3000 r-xp 00000000 {:x}:{:x} {} {}\n'.format(
                os.major(info.st_dev), os.minor(info.st_dev), info.st_ino, provider)).encode()
            with patch.object(selfcheck, 'read_own_proc', return_value=row):
                value = backend.provenance()
                self.assertEqual(value['canonical_path'], str(provider))
                self.assertEqual(value['provider_sha256'], hashlib.sha256(provider.read_bytes()).hexdigest())
                self.assertEqual(value['file_identity'], list(helper.file_identity(info)))
                self.assertEqual(value['pointer_bytes'], ctypes.sizeof(ctypes.c_void_p))
                self.assertIs(value['provider_hash_predeclared'], False)
                self.assertIs(value['mapped_payload_authenticated'], False)
                provider.write_bytes(b'not ELF')
                with self.assertRaises(ValueError):
                    backend.provenance()
                provider.unlink()
                provider.mkdir()
                with self.assertRaises((ValueError, OSError)):
                    backend.provenance()
            provider.rmdir()
            provider.write_bytes(b'\x7fELF fixture')
            info = provider.stat()
            wrong_inode = ('1000-3000 r-xp 00000000 {:x}:{:x} {} {}\n'.format(
                os.major(info.st_dev), os.minor(info.st_dev), info.st_ino + 1, provider)).encode()
            with patch.object(selfcheck, 'read_own_proc', return_value=wrong_inode):
                with self.assertRaises(ValueError):
                    backend.provenance()

    def test_backend_polls_only_returned_fd_and_closed_check_requires_EBADF(self):
        backend = selfcheck.SelfPidfdBackend.__new__(selfcheck.SelfPidfdBackend)
        poller = Mock()
        poller.poll.return_value = []
        with patch.object(selfcheck.select, 'poll', return_value=poller) as constructor:
            self.assertEqual(backend.poll_self_fd(0), [])
        constructor.assert_called_once_with()
        poller.register.assert_called_once_with(0, selfcheck.select.POLLIN)
        poller.poll.assert_called_once_with(0)
        for error, expected in ((OSError(errno.EBADF, 'closed'), True),
                                (OSError(errno.EIO, 'other error'), False), (None, False)):
            with self.subTest(error=error), patch.object(selfcheck.os, 'fstat', side_effect=error):
                self.assertIs(backend.is_fd_closed(11), expected)

    def test_captured_helper_refuses_cache_changed_bytes_and_symlink_boundaries(self):
        helper_bytes = (ROOT / 'scripts/frontier_v8_containment_capability.py').read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            source = directory / 'observer.py'
            path = directory / 'frontier_v8_containment_capability.py'
            path.write_bytes(helper_bytes)
            with patch.object(selfcheck, '__file__', str(source)):
                helper = selfcheck.load_identity_helper()
                self.assertEqual(helper._captured_bytes, helper_bytes)
                self.assertEqual(helper._captured_identity, helper.file_identity(path.stat()))
                self.assertEqual(helper.normalized_path.__code__.co_filename, str(path))
                self.assertNotIn(selfcheck.HELPER_NAME, sys.modules)
                with patch.dict(sys.modules, {selfcheck.HELPER_NAME: SimpleNamespace()}):
                    with self.assertRaises(ValueError):
                        selfcheck.load_identity_helper()
                path.write_bytes(helper_bytes + b'\n')
                with self.assertRaises(ValueError):
                    selfcheck.load_identity_helper()
                original = directory / 'original.py'
                original.write_bytes(helper_bytes)
                path.unlink()
                path.symlink_to(original)
                with self.assertRaises((ValueError, OSError)):
                    selfcheck.load_identity_helper()
            linked = directory / 'linked'
            linked.symlink_to(directory, target_is_directory=True)
            with patch.object(selfcheck, '__file__', str(linked / 'observer.py')):
                with self.assertRaises((ValueError, OSError)):
                    selfcheck.load_identity_helper()

    def test_request_requires_exact_raw_eight_field_declaration(self):
        with ObserverFixture() as fixture:
            parsed = selfcheck.parse_request(fixture.request_path.read_bytes(), fixture.request_sha,
                                            fixture.request['observer_sha256'], fixture.helper)
            self.assertEqual(parsed, fixture.request)
            mutations = (
                ('schema_version', True), ('scope', 'old-scope'), ('nonce', 'short'),
                ('observer_sha256', '0' * 64), ('identity_helper_sha256', '0' * 64),
                ('extra', False), ('attempt_directory', '/proc/self/fd/0'),
                ('attempt_directory', '/tmp/../unsafe'),
                ('host', {**fixture.request['host'], 'uid': True}),
                ('bootstrap', {**fixture.request['bootstrap'], 'executable': '/dev/null'}))
            for key, value in mutations:
                request = {**fixture.request, key: value}
                body = json.dumps(request).encode()
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    selfcheck.parse_request(body, hashlib.sha256(body).hexdigest(),
                                            fixture.request['observer_sha256'], fixture.helper)
            body = fixture.request_path.read_bytes()
            for changed in (body.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'),
                            body.replace(b'"schema_version": 1', b'"schema_version": NaN')):
                with self.subTest(body=changed), self.assertRaises(ValueError):
                    selfcheck.parse_request(changed, hashlib.sha256(changed).hexdigest(),
                                            fixture.request['observer_sha256'], fixture.helper)
            with self.assertRaises(ValueError):
                selfcheck.parse_request(body + b' ', fixture.request_sha,
                                        fixture.request['observer_sha256'], fixture.helper)

    def test_observer_prevalidation_failure_never_consumes_or_resolves_backend(self):
        for change in ('source', 'helper', 'bootstrap', 'host', 'symlink_request', 'unsafe_attempt'):
            with self.subTest(change=change), ObserverFixture() as fixture:
                if change == 'source':
                    fixture.source.write_bytes(b'changed source')
                elif change == 'helper':
                    fixture.helper_path.write_bytes(fixture.helper_path.read_bytes() + b'\n')
                elif change == 'bootstrap':
                    fixture.bootstrap.write_bytes(b'changed bootstrap')
                elif change == 'host':
                    fixture.request['host']['hostname'] = 'other-host'
                    fixture.write_request()
                elif change == 'symlink_request':
                    original = fixture.directory / 'original-request.json'
                    fixture.request_path.rename(original)
                    fixture.request_path.symlink_to(original)
                else:
                    fixture.request['attempt_directory'] = '/proc/self/fd/0'
                    fixture.write_request()
                factory = Mock()
                with self.assertRaises((ValueError, OSError)):
                    fixture.observe(factory)
                factory.assert_not_called()
                self.assertFalse(fixture.marker.exists())
                self.assertFalse(fixture.attempt.exists())

    def test_observer_success_is_consumed_once_and_receipt_has_no_authority(self):
        with ObserverFixture() as fixture:
            result = fixture.observe()
            self.assertEqual(result['status'], 'own_pidfd_operations_observed')
            self.assertIs(result['own_pidfd_operations_verified'], True)
            self.assertIs(result['input_and_self_identity_postvalidation_passed'], True)
            self.assert_no_authority(result)
            self.assertEqual(json.loads((fixture.attempt / 'receipt.json').read_bytes()), result)
            marker_bytes = fixture.marker.read_bytes()
            factory = Mock()
            with self.assertRaises((ValueError, OSError)):
                fixture.observe(factory)
            factory.assert_not_called()
            self.assertEqual(fixture.marker.read_bytes(), marker_bytes)
            self.assertEqual(json.loads((fixture.attempt / 'receipt.json').read_bytes()), result)

    def test_constructor_probe_and_postvalidation_failures_retain_consumed_receipts(self):
        for failure in ('constructor', 'probe', 'source_post', 'self_post'):
            with self.subTest(failure=failure), ObserverFixture() as fixture:
                def factory(helper):
                    if failure == 'constructor':
                        raise AttributeError('fixture missing named export')
                    if failure == 'source_post':
                        fixture.source.write_bytes(b'changed after consumption')
                    return FakeBackend(fd=-1, open_errno=errno.ENOSYS) if failure == 'probe' else FakeBackend()
                if failure == 'self_post':
                    fixture.helper.capture_self_identity.side_effect = [own_identity(),
                                                                        {**own_identity(), 'start_ticks': 101}]
                result = fixture.observe(factory)
                self.assert_failed(result)
                self.assertTrue(fixture.marker.exists())
                self.assertEqual(json.loads((fixture.attempt / 'receipt.json').read_bytes()), result)
                if failure == 'constructor':
                    self.assertNotIn('self_probe', result)
                    self.assertEqual(result['error']['type'], 'AttributeError')
                elif failure == 'probe':
                    self.assertEqual(result['self_probe']['open_errno'], errno.ENOSYS)
                    self.assertIs(result['input_and_self_identity_postvalidation_passed'], True)
                else:
                    self.assertIs(result['self_probe']['own_pidfd_operations_verified'], True)
                    self.assertIs(result['input_and_self_identity_postvalidation_passed'], False)

    @unittest.skipUnless(sys.platform == 'linux', 'Real own-pidfd fixture requires Ubuntu Linux CI')
    def test_real_linux_default_backend_observes_only_own_descriptor(self):
        helper = selfcheck.load_identity_helper()
        identity = helper.capture_self_identity()
        before_api = getattr(os, 'pidfd_open', None)
        result = selfcheck.probe_self_pidfd(identity, selfcheck.SelfPidfdBackend(helper))
        self.assertEqual(result['status'], 'own_pidfd_operations_observed', result)
        self.assertIs(result['own_pidfd_operations_verified'], True)
        self.assert_no_authority(result)
        self.assertEqual(result['fd_identity']['pid'], os.getpid())
        self.assertEqual(result['poll_events'], [])
        self.assertIs(result['steps']['closed_fd_observed'], True)
        self.assertEqual(result['provider_before'], result['provider_after'])
        self.assertEqual(result['provider_before']['route'], 'process_global_named_C_export')
        self.assertIs(getattr(os, 'pidfd_open', None), before_api)

    @unittest.skipUnless(sys.platform == 'linux', 'Real isolated file CLI requires Ubuntu Linux CI')
    def test_real_linux_fresh_file_cli_returns_complete_consumed_receipt(self):
        source = ROOT / 'scripts/frontier_v8_pidfd_selfcheck.py'
        helper = selfcheck.load_identity_helper()
        executable = Path(os.path.realpath(sys.executable))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            attempt, request_path = directory / 'attempt', directory / 'request.json'
            request = {
                'schema_version': 1, 'scope': selfcheck.SCOPE, 'nonce': secrets.token_hex(32),
                'observer_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'identity_helper_sha256': selfcheck.HELPER_SHA, 'attempt_directory': str(attempt),
                'host': {'node_alias': 'N1-1', 'hostname': os.uname().nodename,
                         'boot_id': helper.capture_self_identity()['boot_id'], 'uid': os.getuid()},
                'bootstrap': {'executable': str(executable),
                              'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
                              'version': list(sys.version_info[:3])}}
            body = json.dumps(request, sort_keys=True).encode()
            request_path.write_bytes(body)
            completed = subprocess.run(
                [str(executable), '-B', '-I', '-S', str(source), '--observe-own-pidfd',
                 '--request', str(request_path), '--expected-request-sha256', hashlib.sha256(body).hexdigest()],
                capture_output=True, timeout=30, check=False)
            self.assertEqual(completed.returncode, 0, (completed.stdout, completed.stderr))
            self.assertEqual(completed.stderr, b'')
            result = json.loads(completed.stdout)
            self.assertEqual(json.loads((attempt / 'receipt.json').read_bytes()), result)
            self.assertEqual(result['status'], 'own_pidfd_operations_observed')
            self.assertIs(result['own_pidfd_operations_verified'], True)
            self.assertIs(result['input_and_self_identity_postvalidation_passed'], True)
            self.assert_no_authority(result)
            self.assertEqual(result['self_probe']['fd_identity']['pid'], result['self_identity']['pid'])
            self.assertNotEqual(result['self_identity']['pid'], os.getpid())
            self.assertEqual(result['child_processes_created'], 0)
            self.assertEqual(result['signal_operations'], 0)
            self.assertIs(result['native_guard_executed_or_modified'], False)
            self.assertIs(result['os_api_shim_installed'], False)
            self.assertEqual(json.loads(attempt.with_name('attempt.consumed.json').read_bytes())['nonce'],
                             request['nonce'])

    def test_execute_refuses_before_parser_helper_request_or_export_resolution(self):
        with patch.object(selfcheck, 'load_identity_helper') as helper, \
                patch.object(selfcheck, 'observe') as observe, \
                patch.object(selfcheck, 'SelfPidfdBackend') as backend, \
                patch.object(selfcheck.argparse, 'ArgumentParser') as parser, \
                patch.object(selfcheck.ctypes, 'CDLL') as library:
            for argv in (['--execute'], ['--request', '/missing', '--execute=true']):
                with self.assertRaises((ValueError, OSError)):
                    selfcheck.main(argv)
            for mocked in (helper, observe, backend, parser, library):
                mocked.assert_not_called()


if __name__ == '__main__':
    unittest.main()
