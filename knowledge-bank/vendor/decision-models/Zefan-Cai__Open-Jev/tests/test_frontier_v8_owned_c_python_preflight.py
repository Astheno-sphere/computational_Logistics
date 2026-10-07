"""Synthetic CPU fixtures; the tests/docs author is a source author.

Temporary package trees are illustrative data, never PR27 or MS evidence.
Root owns the final focused run with all ten closure hashes before/after.
"""

import copy
import errno
import json
import os
from pathlib import Path
import secrets
import struct
import sys
import sysconfig
import tempfile
import unittest
from unittest.mock import patch

from scripts import frontier_v8_owned_c_python_preflight as observer
from scripts import frontier_v8_python_runtime_preflight as worker


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'requirements-linux-py311-cu128-20261002.lock'
BOOT = '00000000-0000-0000-0000-000000000001'
NONCE = 'a' * 64  # Pure synthetic token, never dispatched to a host.
PACKAGES = ('torch', 'transformers', 'peft', 'triton', 'safetensors', 'accelerate')


def encoded(row):
    return json.dumps(row, sort_keys=True, separators=(',', ':')).encode()


def synthetic_python_elf(elf_class=2, data_encoding=1, *, size=512,
                         path=b'/lib/synthetic-loader.so\0', phnum=1):
    """Illustrative ELF descriptors only; these bytes are never executed."""
    order = '<' if data_encoding == 1 else '>'
    ehsize, phsize = (52, 32) if elf_class == 1 else (64, 56)
    body = bytearray(max(size, ehsize + phsize * phnum, 256 + len(path)))
    body[:7] = b'\x7fELF' + bytes((elf_class, data_encoding, 1))
    struct.pack_into(order + 'HHI', body, 16, 3, 513, 1)
    struct.pack_into(order + ('I' if elf_class == 1 else 'Q'), body,
                     28 if elf_class == 1 else 32, ehsize)
    struct.pack_into(order + 'HHH', body, 40 if elf_class == 1 else 52,
                     ehsize, phsize, phnum)
    for index in range(phnum):
        start = ehsize + index * phsize
        struct.pack_into(order + 'I', body, start, 3)
        struct.pack_into(order + ('I' if elf_class == 1 else 'Q'), body,
                         start + (4 if elf_class == 1 else 8), 256)
        struct.pack_into(order + ('I' if elf_class == 1 else 'Q'), body,
                         start + (16 if elf_class == 1 else 32), len(path))
    body[256:256 + len(path)] = path
    return bytes(body)


def source_hashes(actual=False):
    def sha(name, dummy):
        return observer.digest((ROOT / 'scripts' / name).read_bytes()) if actual else dummy * 64
    return {'observer_sha256': sha(Path(observer.__file__).name, '1'),
            'worker_sha256': sha(observer.WORKER_NAME, '2'),
            'c_sources_sha256': {name: sha(name, str(i + 3))
                                for i, name in enumerate(observer.C_NAMES)},
            'identity_helper_sha256': observer.HELPER_SHA,
            'toolchain_sha256': observer.TOOLCHAIN_SHA,
            'linkage_sha256': observer.LINKAGE_SHA}


def live_request():
    """Closed illustrative real-route schema; no filesystem/host is accessed."""
    venv = '/data/zefan/open-jev-v8-linux-runtime-20261003/fixed/attempts/install-r1/venv'
    return {'schema_version': 1, 'scope': observer.SCOPE, 'case': 'normal',
        'nonce': NONCE, 'input_kind': 'real_readonly_runtime', 'python_version': [3, 11, 15],
        'runtime': {'venv_root': venv, 'site': venv + '/lib/python3.11/site-packages',
            'alias': venv + '/bin/python', 'config': {'path': venv + '/pyvenv.cfg', 'sha256': '5' * 64},
            'interpreter': {'path': '/usr/local/bin/python3.11', 'sha256': '6' * 64},
            'stdlib': '/usr/local/lib/python3.11', 'lib_dynload': '/usr/local/lib/python3.11/lib-dynload',
            'stdlib_zip': '/usr/local/lib/python311.zip'},
        'lock': {'path': '/data/zefan/new-source/requirements-linux-py311-cu128-20261002.lock',
                 'sha256': observer.LOCK_SHA},
        'authority': dict(observer.AUTHORITY),
        'host': {'node_alias': 'N1-1', 'hostname': 'synthetic', 'boot_id': BOOT, 'uid': os.getuid()},
        'sources': source_hashes(),
        'attempt_directory': '/data/zefan/open-jev-v8-owned-python-preflight-bridge-normal-'
                             '20261004T000000Z-' + NONCE[:16] + '/attempt-r1',
        'bootstrap': {'path': '/usr/local/bin/python3.11', 'sha256': '7' * 64,
                      'python_version': [3, 11, 15]},
        'source_A': '8' * 40, 'scientific_A': observer.SCIENCE_A, 'native_A': observer.NATIVE_A}


def synthetic_python(runtime, version):
    """Illustrative isolated child shape, not the parent's actual startup flags."""
    names = ('os', 'sys', 'hashlib', 'json', 're', 'select', 'signal', 'stat', 'time',
             'fcntl', 'pathlib', 'email.parser', 'importlib.machinery', 'types', 'zipimport')
    origins = {}
    for name in names:
        origin = sys.modules[name].__spec__.origin
        kind = 'builtin' if origin == 'built-in' else 'frozen' if origin == 'frozen' else 'stdlib_file'
        # File origins are synthetic paths in the declared root for this constructor.
        if kind == 'stdlib_file':
            origin = str(Path(runtime['stdlib']) / (name.replace('.', '/') + '.py'))
        origins[name] = {'classification': kind, 'origin': origin}
    return {'python_version': version, 'sys_executable': '', 'sys_prefix': runtime['stdlib'],
            'sys_base_prefix': runtime['stdlib'],
            'sys_path': [runtime[name] for name in ('stdlib_zip', 'stdlib', 'lib_dynload')],
            'flags': {'isolated': 1, 'no_site': 1, 'dont_write_bytecode': True},
            'stdlib_origins': origins,
            'importer_cache': [{'path': runtime['stdlib_zip'], 'kind': 'absent'},
                               {'path': runtime['stdlib'], 'kind': 'FileFinder'},
                               {'path': runtime['lib_dynload'], 'kind': 'FileFinder'}],
            'stdlib_zip_present': False}


def synthetic_bootstrap(request):
    """Synthetic captured-FD records used only by pure schema tests."""
    t0 = 1000000000
    captured = {}
    for name, fd, body, sha in (
        ('worker', 8, b'fixed-worker', request['sources']['worker_sha256']),
        ('request', 9, encoded(request), observer.digest(encoded(request)))):
        info = [1, fd, 0o100600, len(body), 3, 4]
        captured[name] = {'fd': fd, 'sha256': sha, 'length': len(body),
                         'before': info, 'after': list(info), 'close_return': None,
                         'badfd_result': None, 'badfd_exception': 'OSError',
                         'badfd_errno': errno.EBADF}
    initial = ['-c', 'PP_BOOT1', '8', '9', '10', '11', captured['worker']['sha256'],
               captured['request']['sha256'], request['nonce'], request['case'], str(t0),
               request['input_kind'], '.'.join(map(str, request['python_version']))]
    return {'schema_version': 1, 'nonce': request['nonce'], 'case': request['case'],
            'input_kind': request['input_kind'], 'python_version_expected': request['python_version'],
            'command_fd': 10, 'report_fd': 11, 't0_ns': t0,
            'deadlines': {name: t0 + seconds * 1000000000 for name, seconds in
                          (('work_ns', 20), ('cleanup_ns', 25), ('terminal_ns', 28),
                           ('total_ns', 30), ('expiry_ns', 35))},
            'captured': captured, 'initial_argv': initial, 'orig_argv': None,
            'bootstrap_sha256': None, 'logical_file': observer.WORKER_NAME,
            'logical_arguments': [observer.WORKER_NAME, request['case'], request['nonce'], request['input_kind']]}


class SyntheticSite:
    """Only temporary dist-info and six poisonous source entries, no install."""

    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.site = self.root / 'venv/lib' / ('python%d.%d' % sys.version_info[:2]) / 'site-packages'
        self.site.mkdir(parents=True)
        self.venv = self.root / 'venv'
        (self.venv / 'bin').mkdir()
        self.alias = self.venv / 'bin/python'
        self.interpreter = Path(sys.executable).resolve()
        self.alias.symlink_to(self.interpreter)
        self.config = self.venv / 'pyvenv.cfg'
        self.config.write_text('home = ' + str(self.interpreter.parent) + '\ninclude-system-site-packages = false\n')
        self.pins = worker.parse_lock(LOCK.read_bytes())
        self.metadata = {}
        for name, version in self.pins.items():
            directory = self.site / (name.replace('-', '_') + '-' + version + '.dist-info')
            directory.mkdir()
            path = self.metadata[name] = directory / 'METADATA'
            path.write_text('Metadata-Version: 2.1\nName: ' + name + '\nVersion: ' + version + '\n\n')
        self.sentinel = self.root / 'forbidden-package-execution'
        poison = 'from pathlib import Path\nPath(' + repr(str(self.sentinel)) + ').write_text("executed")\nraise RuntimeError("poison must not execute")\n'
        for name in PACKAGES:
            (self.site / name).mkdir()
            (self.site / name / '__init__.py').write_text(poison)
        (self.site / 'sitecustomize.py').write_text(poison)
        (self.site / 'usercustomize.py').write_text(poison)
        (self.site / 'poison.pth').write_text('import sitecustomize\n')
        self.lock = self.root / LOCK.name
        self.lock.write_bytes(LOCK.read_bytes())
        return self

    def __exit__(self, *args):
        self.temporary.cleanup()

    def fixture_request(self, case, boot):
        stdlib = Path(sysconfig.get_path('stdlib')).resolve()
        dynload = Path(sysconfig.get_config_var('DESTSHARED')).resolve()
        row = live_request()
        row.update(case=case, nonce=secrets.token_hex(32), input_kind='synthetic_CI_fixture',
                   python_version=list(sys.version_info[:3]), source_A='0' * 40,
                   sources=source_hashes(actual=True))
        attempt = self.root / 'attempt-r1'
        attempt.mkdir()
        (attempt / 'tmp').mkdir()
        row['attempt_directory'] = str(attempt)
        row['runtime'] = {'venv_root': str(self.venv), 'site': str(self.site),
            'alias': str(self.alias), 'config': {'path': str(self.config),
                'sha256': observer.digest(self.config.read_bytes())},
            'interpreter': {'path': str(self.interpreter),
                'sha256': observer.digest(self.interpreter.read_bytes())},
            'stdlib': str(stdlib), 'lib_dynload': str(dynload),
            'stdlib_zip': str(stdlib.parent / ('python%d%d.zip' % sys.version_info[:2]))}
        row['host'] = {'node_alias': 'N1-1', 'hostname': os.uname().nodename,
                       'boot_id': boot, 'uid': os.getuid()}
        row['bootstrap'] = {'path': str(self.interpreter),
            'sha256': row['runtime']['interpreter']['sha256'], 'python_version': list(sys.version_info[:3])}
        row['lock'] = {'path': str(self.lock), 'sha256': observer.LOCK_SHA}
        path = self.root / 'request.json'
        body = encoded(row)
        path.write_bytes(body)
        return path, observer.digest(body), row


def replace_python_body(row, data):
    """Bind illustrative DATA bytes after a semantic mutation, without relaunch."""
    raw = encoded(data)
    sha = observer.digest(raw)
    row['python_body'] = {'complete': True, 'declared_length': len(raw),
                         'declared_sha256': sha, 'length': len(raw), 'raw_hex': raw.hex()}
    packet = next(packet for packet in row['protocol'] if packet['kind'] == 'DATA')
    packet.update(length=len(raw), sha256=sha, payload=str(len(raw)) + ' ' + sha)


def synthetic_native_receipt(fixture, case='normal'):
    """Illustrative parser input, never native/host output or ABI evidence.

    The temporary tree supplies actual file metadata only. Every PID, clock,
    native call and scalar value below is synthetic. Tests mutate this one row
    rather than executing another process or borrowing an old receipt.
    """
    request_path, request_sha, request = fixture.fixture_request(case, BOOT)
    snapshot = worker.readonly_snapshot(request['runtime'], fixture.pins)
    _, lock = worker.capture_regular(str(fixture.lock), 65536)
    lock['pins'] = fixture.pins
    t0 = 1000000000
    at = lambda offset: t0 + offset
    empty = lambda: {'attempted': False, 'result': None, 'errno': None, 'at_ns': None}
    fact = lambda result=0, error=0, offset=10: {
        'attempted': True, 'result': result, 'errno': error, 'at_ns': at(offset)}
    fds = dict(zip(('interpreter', 'worker_script', 'request', 'command_read', 'command_write',
                    'report_read', 'report_write', 'exec_error_read', 'exec_error_write', 'G_P'),
                   range(3, 13)))
    fds.update(original_stdin=0, original_stdout=1, original_stderr=2)
    interpreter = snapshot['runtime_inputs']['alias']['identity']
    guardian = [1, 41, 0o100700, 4096, 3, 4]
    script = [1, 44, 0o100600, len(b'fixed-worker'), 3, 4]
    requested = [1, 45, 0o100600, len(encoded(request)), 3, 4]
    helper_stat = lambda value: value[:3] + [os.getuid()] + value[3:]
    bootstrap_literal = 'fixed illustrative bootstrap literal; never executed'
    bindings = {'worker_path': '/synthetic/' + observer.WORKER_NAME,
        'request_path': str(request_path), 'request_sha256': request_sha,
        'boot_id': BOOT, 'uid': os.getuid(), 'parent_pid': 40,
        'guardian_identity': helper_stat(guardian), 'interpreter_identity': helper_stat(interpreter),
        'worker_identity': helper_stat(script), 'request_identity': helper_stat(requested),
        'bootstrap_literal': bootstrap_literal, 'lock_pins': fixture.pins}
    argv = ['/synthetic/guardian', case, request['nonce'], request['runtime']['interpreter']['path'],
            bindings['worker_path'], str(request_path), request['runtime']['interpreter']['sha256'],
            request['sources']['worker_sha256'], request_sha,
            '.'.join(map(str, request['python_version'])), request['input_kind'], 'none']
    python_argv = [argv[3], '-B', '-I', '-S', '-c', bootstrap_literal, 'PP_BOOT1',
                   str(fds['worker_script']), str(fds['request']), str(fds['command_read']),
                   str(fds['report_write']), argv[7], request_sha, request['nonce'], case,
                   str(t0), request['input_kind'], argv[9]]
    startup = synthetic_bootstrap(request)
    startup.update(command_fd=fds['command_read'], report_fd=fds['report_write'],
                   initial_argv=['-c', *python_argv[6:]], orig_argv=python_argv,
                   bootstrap_sha256=observer.digest(bootstrap_literal.encode()))
    for name, value, fd in (('worker', script, fds['worker_script']), ('request', requested, fds['request'])):
        startup['captured'][name].update(fd=fd, before=value, after=list(value), length=value[3])
    identity = lambda pid, ppid, birth, product: {'pid': pid, 'ppid': ppid, 'uid': os.getuid(),
        'euid': os.getuid(), 'birth': birth, 'boot_id': BOOT, 'state': 'S', 'product': product}
    p = identity(43, 42, 100, interpreter)
    data = {'schema_version': 1, 'scope': observer.SCOPE, 'case': case, 'nonce': request['nonce'],
        'input_kind': request['input_kind'],
        'identity': {key: value for key, value in p.items() if key not in ('state', 'product')},
        'python': synthetic_python(request['runtime'], request['python_version']),
        'startup': startup, 'lock': lock,
        'snapshots': {'before': snapshot, 'after': copy.deepcopy(snapshot)},
        'pipcheck_performed': 0, 'dependency_consistency_verified': False, 'authority': dict(observer.AUTHORITY)}
    data['identity']['proc_exe'] = {'path': argv[3], 'identity': interpreter}
    native = {'SYS_pidfd_open': 101, 'SYS_pidfd_send_signal': 102,
        'F_GETFD': 1, 'F_SETFD': 2, 'FD_CLOEXEC': 1, 'O_CLOEXEC': 4, 'O_NOFOLLOW': 8,
        'O_NONBLOCK': 16, 'F_GETFL': 3, 'EBADF': errno.EBADF, 'EAGAIN': errno.EAGAIN,
        'EINTR': errno.EINTR, 'ESRCH': errno.ESRCH, 'SIGKILL': 9, 'SIGPIPE': 13,
        'POLLIN': 1, 'POLLNVAL': 32, 'PIPE_BUF': 4096, 'RLIMIT_CORE': 4, 'RLIMIT_CPU': 0,
        'int_bytes': 4, 'long_bytes': 8, 'pointer_bytes': 8, 'char_bits': 8, 'byte_order': 1,
        'pid_t_bytes': 4, 'pid_t_signed': 1, 'uid_t_bytes': 4, 'uid_t_signed': 0,
        'dev_t_bytes': 8, 'ino_t_bytes': 8, 'rlim_t_bytes': 8, 'observed_pipe_buf': 4096,
        'rlimits': {'reported': True, 'core_requested': [0, 0], 'core_result': 0, 'core_errno': 0,
                    'cpu_requested': [20, 21], 'cpu_result': 0, 'cpu_errno': 0},
        'sigpipe': {'set': fact(), 'get': fact(), 'ignored': True}}
    cpp = {'target_int_bytes': 4, 'target_long_bytes': 8, 'target_pointer_bytes': 8,
           'target_char_bits': 8, 'target_byte_order': 1,
           'extra_header_expressions': {name: '1' for name in observer.EXTRA_HEADERS}}
    poll = lambda purpose, offset, result=0, revents=0: {'fd': fds['G_P'], 'result': result,
        'revents': revents, 'errno': 0, 'at_ns': at(offset), 'purpose': purpose}
    closed = lambda owner, label, offset=200: {'owner': owner, 'label': label, 'generation': 1,
        'fd': fds[label], 'evidence': 'explicit_once_close',
        'close': fact(offset=offset) if owner == 'G' else {**fact(), 'at_ns': None},
        'badfd': fact(-1, errno.EBADF, offset+1) if owner == 'G' else {**fact(-1, errno.EBADF), 'at_ns': None}}
    g_order = ('command_read', 'report_write', 'exec_error_write', 'interpreter', 'worker_script',
               'request', 'exec_error_read', 'G_P', 'command_write', 'report_read')
    ledger = [closed('G', label, 30 if index < 6 else 95 if index == 6 else 200)
              for index, label in enumerate(g_order)]
    child_labels = ('command_write', 'report_read', 'exec_error_read',
                    'original_stdin', 'original_stdout', 'original_stderr')
    ledger += [closed('X', label) for label in child_labels]
    for owner, label, evidence in (('X', 'interpreter', 'exec_cloexec'),
                                  ('X', 'exec_error_write', 'exec_cloexec'),
                                  ('P', 'report_write', 'parent_report_eof'),
                                  ('P', 'command_read', 'unknown' if case == 'normal' else 'owner_death')):
        ledger.append({'owner': owner, 'label': label, 'generation': 1, 'fd': fds[label],
                       'evidence': evidence, 'close': empty(), 'badfd': empty()})
    inherited = {'worker_script', 'request', 'command_read', 'report_write'}
    flags = [{'owner': 'G', 'label': label, 'generation': 1, 'fd': fds[label],
        'before': fact(1), 'set': fact(), 'after': fact(0 if label in inherited else 1),
        'getfl': fact(16 if 'command' in label or 'report' in label or 'exec_error' in label else 0)}
        for label in list(fds)[:9]]
    pre = ' '.join('%d 0 0 0 -1 %d' % (fds[label], errno.EBADF) for label in child_labels) + ' 0 0 0 0'
    ready = ' '.join(map(str, [p[key] for key in ('pid', 'ppid', 'uid', 'euid', 'birth')]
                    + request['python_version'] + [1, 1, 1]
                    + [request['sources']['worker_sha256'], request_sha]))
    order = [('X', 'PRE_READY', 40, pre), ('G', 'GO', 50, ''), ('X', 'EXEC_ENTER', 60, ''),
        ('P', 'READY', 90, ready), ('G', 'CHECK', 100, ''), ('P', 'DATA', 105, ''),
        ('P', 'ARM', 120, ''), ('G', 'ARM_ACK', 130, ''), ('P', 'ACK', 140, '')]
    if case == 'normal':
        order += [('G', 'FINISH', 151, ''), ('P', 'FINISH_ACK', 160, '')]
    sequences, packets = {'G': 0, 'child': 0}, []
    for role, kind, offset, payload in order:
        group = 'G' if role == 'G' else 'child'
        sequences[group] += 1
        packets.append({'role': role, 'direction': 'sent' if role == 'G' else 'received',
            'seq': sequences[group], 'kind': kind, 'at_ns': at(offset), 'observed_ns': at(offset),
            'length': None, 'sha256': None, 'payload': payload})
    row = {'schema_version': 1, 'scope': observer.SCOPE, 'case': case, 'nonce': request['nonce'],
        'input_kind': request['input_kind'], 'fault': 'none', 'native_success': True, 'error': None,
        't0_ns': t0, 'deadlines': startup['deadlines'], 'runtime_argv': argv,
        'python_exec_argv': python_argv, 'kernel_python_argv': python_argv,
        'expected_hashes': {'interpreter': argv[6], 'worker': argv[7], 'request': request_sha},
        'products': {'guardian': guardian, 'interpreter': interpreter},
        'identities': {'G': identity(42, 40, 99, guardian), 'X': identity(43, 42, 100, guardian),
                       'P_transition': p, 'P_pre_action': copy.deepcopy(p)},
        'exec': {'attempted': True, 'returned': False, 'result': None, 'errno': None,
                 'enter_ns': at(60), 'error_eof_ns': at(80), 'error_pipe_result': None},
        'handle': {'fd': fds['G_P'], 'open': fact(fds['G_P'], offset=20), 'flags': fact(1, offset=21),
                   'fdinfo_pid': p['pid'], 'live_poll': poll('initial_live', 22),
                   'close': fact(offset=200), 'badfd': fact(-1, errno.EBADF, 201)},
        'signal': {'budget_consumed': case == 'worker_loss', 'attempts': int(case == 'worker_loss'),
            'fd': fds['G_P'], 'flags': 0, 'result': 0 if case == 'worker_loss' else None,
            'errno': 0 if case == 'worker_loss' else None, 'at_ns': at(150) if case == 'worker_loss' else None},
        'wait': {'attempts': 1, 'result_pid': p['pid'], 'raw_status': 0 if case == 'normal' else 9,
                 'errno': 0, 'at_ns': at(180)},
        'polls': [poll('initial_live', 22), poll('pre_action_live', 145), poll('terminal', 170, 1, 1)],
        'fd_ledger': ledger, 'fd_flags': flags, 'protocol': packets, 'python_body': {},
        'times': dict(zip(observer.TIME_NAMES, map(at, (40, 50, 90, 110, 120, 140, 150, 170, 180, 210, 220)))),
        'native_facts': native}
    replace_python_body(row, data)
    command = {'argv': argv, 'status': 'success', 'returncode': 0, 'reap_completed': True,
               'timed_out': False, 'kill_attempted': False, 'direct_child_pid': 42}
    return row, command, cpp, request, bindings


class PythonPreflightTests(unittest.TestCase):
    def assert_no_authority(self, row):
        for key in observer.AUTHORITY:
            self.assertIs(row[key], False, key)

    def test_python_interpreter_header_view_preserves_four_class_endian_descriptors_and_full_hash(self):
        _, _, linkage = observer.load_utilities()
        for elf_class in (1, 2):
            for data_encoding in (1, 2):
                with self.subTest(elf_class=elf_class, data_encoding=data_encoding):
                    small = synthetic_python_elf(elf_class, data_encoding)
                    original = linkage.parse_elf_product(small)
                    full = small + b'x' * (observer.MAX_BYTES + 17 - len(small))
                    parsed = observer.parse_python_interpreter(full, linkage)
                    self.assertEqual(set(parsed), set(original) | {
                        'captured_bytes', 'captured_sha256', 'header_view_bytes', 'header_view_sha256'})
                    self.assertEqual({key: parsed[key] for key in original}, original)
                    self.assertEqual(parsed['captured_bytes'], len(full))
                    self.assertEqual(parsed['captured_sha256'], observer.digest(full))
                    self.assertEqual(parsed['header_view_bytes'], observer.MAX_BYTES)
                    self.assertEqual(parsed['header_view_sha256'], observer.digest(full[:observer.MAX_BYTES]))
                    self.assertNotEqual(parsed['captured_sha256'], parsed['header_view_sha256'])
                    small_parsed = observer.parse_python_interpreter(small, linkage)
                    self.assertEqual(small_parsed['captured_bytes'], len(small))
                    self.assertEqual(small_parsed['header_view_bytes'], len(small))
                    self.assertEqual(small_parsed['captured_sha256'], small_parsed['header_view_sha256'])

    def test_python_interpreter_trailing_changes_keep_view_hash_and_change_full_hash(self):
        _, _, linkage = observer.load_utilities()
        prefix = synthetic_python_elf(size=observer.MAX_BYTES)
        first = observer.parse_python_interpreter(prefix + b'a', linkage)
        second = observer.parse_python_interpreter(prefix + b'b', linkage)
        self.assertEqual(first['header_view_sha256'], second['header_view_sha256'])
        self.assertEqual(first['header_view_bytes'], second['header_view_bytes'])
        self.assertEqual(first['captured_bytes'], second['captured_bytes'])
        self.assertNotEqual(first['captured_sha256'], second['captured_sha256'])

    def test_python_interpreter_header_view_rejects_full_cap_type_and_malformed_headers(self):
        _, _, linkage = observer.load_utilities()
        valid = synthetic_python_elf()
        for body in (bytearray(valid), memoryview(valid), None, valid[:63],
                     valid + b'x' * (observer.MAX_INTERPRETER + 1 - len(valid))):
            with self.subTest(input_type=type(body).__name__, length=len(body) if body is not None else None), \
                    self.assertRaises(ValueError):
                observer.parse_python_interpreter(body, linkage)
        for label, offset, fmt, value in (
            ('ident_magic', 0, 'I', 0), ('ident_class', 4, 'B', 3),
            ('ident_encoding', 5, 'B', 3), ('ident_version', 6, 'B', 0),
            ('ELF_type', 16, 'H', 1), ('ELF_version', 20, 'I', 0),
            ('header_size', 52, 'H', 52), ('ph_size', 54, 'H', 32),
            ('ph_count_zero', 56, 'H', 0), ('ph_count_over_cap', 56, 'H', 129),
            ('ph_before_header', 32, 'Q', 63), ('overflow_like_phoff', 32, 'Q', (1 << 64) - 1)):
            bad = bytearray(valid)
            struct.pack_into('<' + fmt, bad, offset, value)
            with self.subTest(fault=label), self.assertRaises(ValueError):
                observer.parse_python_interpreter(bytes(bad), linkage)
        with self.assertRaises(ValueError):
            observer.parse_python_interpreter(valid[:64], linkage)

    def test_python_interpreter_tables_and_PT_INTERP_must_fit_actual_prefix_without_fallback(self):
        _, _, linkage = observer.load_utilities()
        full = synthetic_python_elf(size=observer.MAX_BYTES + 4096)
        for fault in ('table_outside', 'table_crosses', 'segment_outside', 'segment_crosses', 'segment_overflow'):
            bad = bytearray(full)
            if fault.startswith('table'):
                target = observer.MAX_BYTES + 64 if fault == 'table_outside' else observer.MAX_BYTES - 55
                bad[target:target + 56] = bad[64:120]
                struct.pack_into('<Q', bad, 32, target)
            else:
                target = ((1 << 64) - 1 if fault == 'segment_overflow' else
                          observer.MAX_BYTES + 64 if fault == 'segment_outside' else observer.MAX_BYTES - 1)
                if target < len(bad):
                    path = b'/lib/synthetic-loader.so\0'
                    bad[target:target + len(path)] = path
                struct.pack_into('<Q', bad, 72, target)
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                observer.parse_python_interpreter(bytes(bad), linkage)

    def test_python_interpreter_PT_INTERP_requires_unique_terminated_nonvirtual_absolute_path(self):
        _, _, linkage = observer.load_utilities()
        duplicate = synthetic_python_elf(phnum=2)
        absent = bytearray(synthetic_python_elf())
        struct.pack_into('<I', absent, 64, 1)
        for label, body in [('duplicate', duplicate), ('absent', bytes(absent))] + [
            (repr(path), synthetic_python_elf(path=path)) for path in (
                b'/lib/unterminated.so', b'/lib/interior\0nul.so\0', b'/lib/nonascii\xff.so\0',
                b'relative-loader.so\0', b'/lib/../loader.so\0', b'/lib//loader.so\0',
                b'/proc/self/fd/3\0', b'/sys/loader.so\0', b'/dev/loader.so\0', b'/\0',
                b'/lib/' + b'x' * 4096 + b'\0')]:
            with self.subTest(fault=label), self.assertRaises(ValueError):
                observer.parse_python_interpreter(body, linkage)

    def test_python_interpreter_actual_trailing_full_hash_drift_stops_before_build_or_runtime(self):
        helper, utility, linkage = observer.load_utilities()
        with SyntheticSite() as site:
            # A temporary synthetic executable-mode file, never a launched product.
            site.interpreter = site.root / 'synthetic-python-ELF'
            body = synthetic_python_elf(size=observer.MAX_BYTES + 17)
            site.interpreter.write_bytes(body)
            site.interpreter.chmod(0o700)
            site.alias.unlink()
            site.alias.symlink_to(site.interpreter)
            request_path, request_sha, request = site.fixture_request('normal', BOOT)
            with site.interpreter.open('r+b') as stream:
                stream.seek(-1, os.SEEK_END)
                stream.write(b'x')
            changed = site.interpreter.read_bytes()
            self.assertEqual(observer.digest(body[:observer.MAX_BYTES]), observer.digest(changed[:observer.MAX_BYTES]))
            self.assertNotEqual(request['runtime']['interpreter']['sha256'], observer.digest(changed))
            attempt = Path(request['attempt_directory'])
            fd = os.open(attempt, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                backend = utility.CompilerBackend(helper, attempt, fd)
                with patch.object(observer, 'build_product') as build, patch.object(observer, 'run_runtime') as runtime:
                    result = observer.run_fixture(request_path, request_sha, backend,
                        utility, linkage, os.getpid(), os.getuid(), BOOT)
                    build.assert_not_called()
                    runtime.assert_not_called()
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['error']['message'], 'Exact executable Python ELF required')
                self.assertEqual(result['runtime_attempts'], 0)
                self.assertFalse(any(result[name] for name in observer.SUCCESS))
                self.assert_no_authority(result)
            finally:
                os.close(fd)

    def test_real_request_is_closed_exact_pinned_and_fixture_route_is_refused(self):
        row = live_request()
        raw = encoded(row)
        self.assertEqual(observer.parse_request(raw, observer.digest(raw), source_hashes()), row)
        for label, edit in (
            ('extra', lambda r: r.update(unreviewed=True)),
            ('fixture', lambda r: r.update(input_kind='synthetic_CI_fixture')),
            ('version', lambda r: r.update(python_version=[3, 14, 0])),
            ('authority', lambda r: r['authority'].update(execution_available=True)),
            ('source', lambda r: r['sources'].update(worker_sha256='f' * 64)),
            ('lock', lambda r: r['lock'].update(sha256='f' * 64)),
            ('escape', lambda r: r['runtime'].update(site='/tmp/other-site')),
            ('oldattempt', lambda r: r.update(attempt_directory=r['attempt_directory'].replace('attempt-r1', 'attempt-r2')))):
            with self.subTest(label=label):
                bad = copy.deepcopy(row)
                edit(bad)
                body = encoded(bad)
                with self.assertRaises(ValueError):
                    observer.parse_request(body, observer.digest(body), source_hashes())
        with self.assertRaises(ValueError):
            observer.parse_request(raw, '0' * 64, source_hashes())

    def test_closed_json_rejects_duplicate_and_nonfinite_and_truncated_bodies(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                observer.closed_json(raw)

    def test_execute_refusal_precedes_request_utility_or_runtime_processing(self):
        with patch.object(observer, 'observe') as observe, patch.object(observer, 'load_utilities') as load:
            with self.assertRaisesRegex(ValueError, 'execution unavailable'):
                observer.main(['--execute'])
            observe.assert_not_called()
            load.assert_not_called()

    def test_frozen_lock_bytes_and_exact_single_metadata_headers(self):
        pins = worker.parse_lock(LOCK.read_bytes())
        self.assertEqual(len(pins), 76)
        self.assertEqual(pins['torch'], '2.8.0+cu128')
        self.assertEqual(worker.parse_metadata(b'Name: HuggingFace_Hub\nVersion: 1.33.0\n\n'),
                         ('huggingface-hub', '1.33.0'))
        with self.assertRaises(ValueError):
            worker.parse_lock(LOCK.read_bytes() + b'\n')
        for raw in (b'Name: torch\n\n', b'Name: torch\nVersion: 1\nVersion: 2\n\n',
                    b'Name: torch\nName: TORCH\nVersion: 1\n\n', b'Name: \nVersion: 1\n\n',
                    b'Name: torch\nVersion: bad version\n\n', b'x' * (worker.MAX_METADATA + 1)):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                worker.parse_metadata(raw)

    def test_metadata_snapshot_requires_exact_76_no_missing_extra_duplicate_or_version(self):
        for fault in ('missing', 'extra', 'duplicate', 'version', 'legacy'):
            with self.subTest(fault=fault), SyntheticSite() as fixture:
                if fault == 'missing':
                    missing = fixture.metadata['pip']
                    missing.unlink()
                    missing.parent.rmdir()
                elif fault == 'extra':
                    extra = fixture.site / 'extra-1.dist-info'
                    extra.mkdir()
                    (extra / 'METADATA').write_bytes(b'Name: extra\nVersion: 1\n\n')
                elif fault == 'duplicate':
                    fixture.metadata['pip'].write_bytes(b'Name: TORCH\nVersion: 2.8.0+cu128\n\n')
                elif fault == 'version':
                    fixture.metadata['torch'].write_bytes(b'Name: torch\nVersion: 2.8.1+cu128\n\n')
                else:
                    (fixture.site / 'old.egg-info').mkdir()
                with self.assertRaises(ValueError):
                    worker.metadata_snapshot(str(fixture.site), fixture.pins)

    def test_metadata_explicit_scan_and_byte_limits_are_independent_from_source_lookup(self):
        with SyntheticSite() as fixture:
            snapshot = worker.metadata_snapshot(str(fixture.site), fixture.pins)
            self.assertEqual(snapshot['versions'], fixture.pins)
            self.assertEqual(snapshot['explicit_scan']['passes'], 1)
            self.assertEqual(snapshot['explicit_scan']['entries'], 85)  # 76 metadata +6 packages +3 poison startup files.
            self.assertEqual(snapshot['explicit_scan']['metadata_bytes'],
                             sum(path.stat().st_size for path in fixture.metadata.values()))
            with patch.object(worker, 'MAX_SITE_ENTRIES', 84), self.assertRaises(ValueError):
                worker.metadata_snapshot(str(fixture.site), fixture.pins)
            with patch.object(worker, 'MAX_METADATA_TOTAL', 1), self.assertRaises(ValueError):
                worker.metadata_snapshot(str(fixture.site), fixture.pins)
            self.assertEqual(set(worker.source_origins(str(fixture.site))), set(PACKAGES))
            self.assertFalse(fixture.sentinel.exists())

    def test_metadata_and_six_origin_no_follow_reject_symlink_escape(self):
        for fault in ('metadata_directory', 'metadata_file', 'package_directory', 'package_init'):
            with self.subTest(fault=fault), SyntheticSite() as fixture:
                if fault.startswith('metadata'):
                    source = fixture.metadata['torch']
                    if fault == 'metadata_directory':
                        moved = fixture.root / 'outside.dist-info'
                        source.parent.rename(moved)
                        source.parent.symlink_to(moved, target_is_directory=True)
                    else:
                        moved = fixture.root / 'outside-METADATA'
                        source.rename(moved)
                        source.symlink_to(moved)
                    with self.assertRaises((ValueError, OSError)):
                        worker.metadata_snapshot(str(fixture.site), fixture.pins)
                else:
                    source = fixture.site / 'torch' / '__init__.py'
                    if fault == 'package_directory':
                        moved = fixture.root / 'outside-package'
                        source.parent.rename(moved)
                        source.parent.symlink_to(moved, target_is_directory=True)
                    else:
                        moved = fixture.root / 'outside-init.py'
                        source.rename(moved)
                        source.symlink_to(moved)
                    with self.assertRaises((ValueError, OSError)):
                        worker.source_origins(str(fixture.site))
                self.assertFalse(fixture.sentinel.exists())

    def test_source_positions_read_poison_bytes_without_loading_packages_or_customization(self):
        loaded_before = {name for name in sys.modules if name.split('.')[0] in PACKAGES}
        with SyntheticSite() as fixture:
            origins = worker.source_origins(str(fixture.site))
            self.assertEqual(set(origins), set(PACKAGES))
            for name, fact in origins.items():
                path = fixture.site / name / '__init__.py'
                self.assertEqual(fact['path'], str(path))
                self.assertEqual(fact['sha256'], observer.digest(path.read_bytes()))
            self.assertFalse(fixture.sentinel.exists())
            self.assertFalse(any(fixture.site.rglob('__pycache__')))
        self.assertEqual({name for name in sys.modules if name.split('.')[0] in PACKAGES}, loaded_before)

    def test_readonly_snapshots_reject_actual_metadata_source_config_and_alias_drift(self):
        for fault in ('metadata', 'source', 'config', 'alias'):
            with self.subTest(fault=fault), SyntheticSite() as fixture:
                _, _, request = fixture.fixture_request('normal', BOOT)
                runtime = request['runtime']
                before = worker.readonly_snapshot(runtime, fixture.pins)
                self.assertTrue(worker.compare_snapshots(before, worker.readonly_snapshot(runtime, fixture.pins)))
                if fault == 'metadata':
                    with fixture.metadata['torch'].open('ab') as stream:
                        stream.write(b'Fixture-Change: recorded\n')
                elif fault == 'source':
                    with (fixture.site / 'torch/__init__.py').open('ab') as stream:
                        stream.write(b'# changed\n')
                elif fault == 'config':
                    with fixture.config.open('ab') as stream:
                        stream.write(b'# changed\n')
                else:
                    fixture.alias.unlink()
                    fixture.alias.symlink_to(fixture.root / 'unavailable-interpreter')
                with self.assertRaises((ValueError, OSError)):
                    after = worker.readonly_snapshot(runtime, fixture.pins)
                    worker.compare_snapshots(before, after)
                self.assertFalse(fixture.sentinel.exists())

    def test_readonly_alias_and_config_must_match_actual_declared_input(self):
        for fault in ('config_hash', 'system_site', 'duplicate_config', 'alias_backing'):
            with self.subTest(fault=fault), SyntheticSite() as fixture:
                _, _, request = fixture.fixture_request('normal', BOOT)
                runtime = request['runtime']
                if fault == 'config_hash':
                    runtime['config']['sha256'] = '0' * 64
                elif fault in ('system_site', 'duplicate_config'):
                    fixture.config.write_text('include-system-site-packages = true\n' if fault == 'system_site'
                                              else 'include-system-site-packages = false\n' * 2)
                    runtime['config']['sha256'] = observer.digest(fixture.config.read_bytes())
                else:
                    runtime['interpreter']['path'] = str(fixture.root / 'wrong-backing')
                with self.assertRaises((ValueError, OSError)):
                    worker.runtime_observation(runtime)

    def test_startup_flags_version_and_site_exclusion_are_required_without_sys_executable_inference(self):
        runtime = live_request()['runtime']
        observation = synthetic_python(runtime, [3, 11, 15])
        self.assertIs(worker.validate_startup(observation, runtime, [3, 11, 15], 'real_readonly_runtime'), observation)
        self.assertEqual(observation['sys_executable'], '')
        for fault in ('flags', 'bool_flags', 'version', 'site', 'foreign_path', 'missing_zip',
                      'duplicate_path', 'foreign_origin', 'foreign_cache'):
            bad = copy.deepcopy(observation)
            if fault == 'flags':
                bad['flags']['no_site'] = 0
            elif fault == 'bool_flags':
                bad['flags']['isolated'] = True
            elif fault == 'version':
                bad['python_version'] = [3, 11, 16]
            elif fault in ('site', 'foreign_path'):
                bad['sys_path'].append(runtime['site'] if fault == 'site' else '/tmp/unreviewed')
            elif fault == 'missing_zip':
                bad['sys_path'].remove(runtime['stdlib_zip'])
            elif fault == 'duplicate_path':
                bad['sys_path'].append(runtime['stdlib'])
            elif fault == 'foreign_origin':
                bad['stdlib_origins']['pathlib'] = {'classification': 'stdlib_file', 'origin': '/tmp/unreviewed.py'}
            else:
                bad['importer_cache'][0]['kind'] = 'UnreviewedFinder'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                worker.validate_startup(bad, runtime, [3, 11, 15], 'real_readonly_runtime')

    def test_bootstrap_binds_original_handles_python_None_close_and_exact_deadlines(self):
        request = live_request()
        startup = synthetic_bootstrap(request)
        self.assertIs(worker.validate_bootstrap(startup, request), startup)
        for fault in ('duplicate_handle', 'C_close_return', 'fabricated_fcntl_return', 'badfd', 'hash', 'capture_drift',
                      'initial_argv', 'deadline_reset', 'fabricated_orig_argv'):
            bad = copy.deepcopy(startup)
            if fault == 'duplicate_handle':
                bad['report_fd'] = bad['command_fd']
            elif fault == 'C_close_return':
                bad['captured']['worker']['close_return'] = 0
            elif fault == 'fabricated_fcntl_return':
                bad['captured']['worker']['badfd_result'] = -1
            elif fault == 'badfd':
                bad['captured']['request']['badfd_errno'] = 0
            elif fault == 'hash':
                bad['captured']['worker']['sha256'] = 'f' * 64
            elif fault == 'capture_drift':
                bad['captured']['request']['after'][-1] += 1
            elif fault == 'initial_argv':
                bad['initial_argv'][2] = '99'
            elif fault == 'deadline_reset':
                bad['deadlines']['work_ns'] += 1
            else:
                bad['bootstrap_sha256'] = 'f' * 64
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                worker.validate_bootstrap(bad, request)

    def test_result_requires_complete_equal_snapshots_six_positions_and_no_dependency_grant(self):
        with SyntheticSite() as fixture:
            _, _, request = fixture.fixture_request('normal', BOOT)
            snapshot = worker.readonly_snapshot(request['runtime'], fixture.pins)
            _, lock = worker.capture_regular(str(fixture.lock), 65536)
            lock['pins'] = fixture.pins
            row = {'schema_version': 1, 'scope': observer.SCOPE, 'case': request['case'],
                'nonce': request['nonce'], 'input_kind': request['input_kind'],
                'identity': {'pid': 43, 'ppid': 42, 'uid': os.getuid(), 'euid': os.getuid(),
                    'birth': 100, 'boot_id': BOOT,
                    'proc_exe': {'path': str(fixture.interpreter),
                                 'identity': list(snapshot['runtime_inputs']['alias']['identity'])}},
                'python': synthetic_python(request['runtime'], request['python_version']),
                'startup': synthetic_bootstrap(request), 'lock': lock,
                'snapshots': {'before': snapshot, 'after': copy.deepcopy(snapshot)},
                'pipcheck_performed': 0, 'dependency_consistency_verified': False,
                'authority': dict(observer.AUTHORITY)}
            self.assertIs(worker.validate_result(row, request, fixture.pins), row)
            for fault in ('partial', 'extra', 'after_drift', 'six_missing', 'metadata_root',
                          'explicit_scan', 'dependency', 'authority', 'boot_identity'):
                bad = copy.deepcopy(row)
                if fault == 'partial':
                    del bad['snapshots']['after']
                elif fault == 'extra':
                    bad['unknown_receipt'] = True
                elif fault == 'after_drift':
                    bad['snapshots']['after']['metadata']['metadata_sha256']['torch'] = 'f' * 64
                elif fault == 'six_missing':
                    del bad['snapshots']['before']['package_origins']['torch']
                elif fault == 'metadata_root':
                    bad['snapshots']['before']['metadata']['distribution_roots']['torch'] = '/tmp/unreviewed'
                elif fault == 'explicit_scan':
                    bad['snapshots']['before']['metadata']['explicit_scan']['passes'] = 2
                elif fault == 'dependency':
                    bad['dependency_consistency_verified'] = True
                elif fault == 'authority':
                    bad['authority']['execution_available'] = True
                else:
                    bad['identity']['boot_id'] = '00000000-0000-0000-0000-000000000002'
                with self.subTest(fault=fault), self.assertRaises(ValueError):
                    worker.validate_result(bad, request, fixture.pins)

    def test_DATA_positive_cursor_never_retransmits_accepted_bytes_and_EAGAIN_keeps_deadline(self):
        state = {'nonce': NONCE, 'sequence': 4, 'last': 1000, 't0_ns': 1000,
                 'command_fd': 10, 'report_fd': 11, 'pipe_buf': 4096}
        wait = BlockingIOError(errno.EAGAIN, 'bounded wait')
        with patch.object(worker, '_control') as control, patch.object(worker, '_now', return_value=1001), \
                patch.object(worker, '_poll') as poll, patch.object(worker.os, 'write', side_effect=[wait, 2, 1, 3]) as write:
            worker._data(state, b'abcdef', 2000)
            control.assert_called_once_with(state, 'DATA', '6 ' + observer.digest(b'abcdef'), 2000)
            self.assertEqual([args[0][1] for args in write.call_args_list],
                             [b'abcdef', b'abcdef', b'cdef', b'def'])
            poll.assert_called_once_with(state, 11, worker.select.POLLOUT, 2000)
        with patch.object(worker, '_control') as control, self.assertRaises(ValueError):
            worker._data(state, b'x' * (worker.MAX_BODY + 1), 2000)
        control.assert_not_called()

    def test_control_partial_write_once_and_command_partial_EOF_order_and_clock_boundaries(self):
        def state():
            return {'nonce': NONCE, 'sequence': 3, 'last': 1000, 't0_ns': 1000,
                    'command_fd': 10, 'report_fd': 11, 'pipe_buf': 4096}
        current = state()
        with patch.object(worker, '_now', return_value=1001), patch.object(worker.os, 'write', return_value=2) as write:
            with self.assertRaisesRegex(ValueError, 'Partial control'):
                worker._control(current, 'READY', 'bound', 2000)
            write.assert_called_once()
            self.assertEqual(current['sequence'], 4)
        command = ('PP1 G ' + NONCE + ' 2 CHECK 1001\n').encode()
        with patch.object(worker, '_now', return_value=1001), \
                patch.object(worker.os, 'read', side_effect=[command[:7], command[7:]]):
            worker._command(state(), 2, 'CHECK', 2000)
        for raw in (command[:-1], command.replace(b' 2 CHECK ', b' 3 CHECK '),
                    command.replace(b' CHECK ', b' FINISH '), command.replace(NONCE.encode(), b'b' * 64),
                    command.replace(b'1001\n', b'2001\n'), b'x' * 513):
            with self.subTest(raw=raw[:80]), patch.object(worker, '_now', return_value=1001), \
                    patch.object(worker.os, 'read', side_effect=[raw, b'']), self.assertRaises(ValueError):
                worker._command(state(), 2, 'CHECK', 2000)
        for clock in (999, 2000):
            with self.subTest(clock=clock), patch.object(worker.time, 'monotonic_ns', return_value=clock), \
                    self.assertRaises(ValueError):
                worker._now(state(), 2000)

    def test_capture_rejects_symlink_ancestry_nonregular_limit_and_actual_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            path = root / 'file'
            path.write_bytes(b'exact')
            raw, binding = observer.captured_regular(path, 5)
            self.assertEqual(raw, b'exact')
            self.assertEqual(binding, observer.identity(path.stat()))
            with self.assertRaises(ValueError):
                observer.captured_regular(path, 4)
            alias = root / 'alias'
            alias.symlink_to(path)
            with self.assertRaises(OSError):
                observer.captured_regular(alias, 5)
            real = root / 'directory'
            real.mkdir()
            (real / 'child').write_bytes(b'a')
            parent_alias = root / 'parent-alias'
            parent_alias.symlink_to(real, target_is_directory=True)
            with self.assertRaises(OSError):
                observer.captured_regular(parent_alias / 'child', 5)
            with self.assertRaises(ValueError):
                observer.captured_regular(real, 5)
            original_read = os.read
            def drifting_read(fd, limit):
                raw = original_read(fd, limit)
                if raw:
                    path.write_bytes(b'drift')
                return raw
            with patch.object(observer.os, 'read', side_effect=drifting_read):
                with self.assertRaises(ValueError):
                    observer.captured_regular(path, 5)

    def test_captured_pure_utility_tuple_bindings_match_reads_and_stat_drift_stops_before_build(self):
        helper, utility, linkage = observer.load_utilities()
        for module in (helper, utility, linkage):
            with self.subTest(utility=Path(module.__file__).name):
                raw, info = helper.read_regular(module.__file__, observer.MAX_SOURCE)
                self.assertIs(type(info), tuple)
                self.assertIs(type(module._captured_identity), tuple)
                self.assertEqual((raw, info), (module._captured_bytes, module._captured_identity))
                selected = [info[index] for index in (0, 1, 2, 4, 5, 6)]
                self.assertEqual(observer.product_tuple(info), selected)
                self.assertEqual(observer.product_tuple(list(info)), selected)

        with SyntheticSite() as site:
            request_path, request_sha, request = site.fixture_request('normal', BOOT)
            attempt = Path(request['attempt_directory'])
            fd = os.open(attempt, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            backend = utility.CompilerBackend(helper, attempt, fd)
            original_read = helper.read_regular
            try:
                for module, index in ((helper, 1), (utility, 5), (linkage, 4)):
                    with self.subTest(changed_utility=Path(module.__file__).name):
                        def changed_stat(path, limit, *, owner=None):
                            raw, info = original_read(path, limit, owner=owner)
                            if str(path) == module.__file__:
                                changed = list(info)
                                changed[index] += 1
                                info = tuple(changed)
                            return raw, info
                        # Simulated identity drift retains actual captured bytes;
                        # no pinned utility file, process or native API is changed.
                        with patch.object(helper, 'read_regular', side_effect=changed_stat), \
                                patch.object(observer, 'build_product') as build, \
                                patch.object(observer, 'run_runtime') as runtime:
                            result = observer.run_fixture(request_path, request_sha, backend,
                                utility, linkage, os.getpid(), os.getuid(), BOOT)
                            build.assert_not_called()
                            runtime.assert_not_called()
                        self.assertEqual(result['status'], 'failed')
                        self.assertEqual(result['runtime_attempts'], 0)
                        self.assertFalse(result['runtime_returned_complete_facts'])
                        self.assertEqual(result['error']['message'], 'Captured utility bytes/identity drift')
                        self.assertFalse(any(result[name] for name in observer.SUCCESS))
                        self.assert_no_authority(result)
            finally:
                os.close(fd)

    def parse_native(self, fixture, row=None):
        original, command, cpp, request, bindings = fixture
        return observer.parse_runtime(encoded(original if row is None else row),
                                      command, cpp, request, bindings, worker)

    def reject_native_mutations(self, fixture, changes):
        for label, change in changes:
            with self.subTest(fault=label):
                bad = copy.deepcopy(fixture[0])
                change(bad)
                with self.assertRaises(ValueError):
                    self.parse_native(fixture, bad)

    def test_native_parser_accepts_only_joint_synthetic_normal_and_loss_facts(self):
        for case in ('normal', 'worker_loss'):
            with self.subTest(case=case), SyntheticSite() as site:
                fixture = synthetic_native_receipt(site, case)
                self.assertEqual(self.parse_native(fixture), fixture[0])
                data = observer.closed_json(bytes.fromhex(fixture[0]['python_body']['raw_hex']))
                self.assert_no_authority(data['authority'])
                self.assertEqual(data['pipcheck_performed'], 0)
                self.assertFalse(site.sentinel.exists())

    def test_native_DATA_hash_length_truncation_and_header_are_bound_to_same_bytes(self):
        with SyntheticSite() as site:
            fixture = synthetic_native_receipt(site)
            self.reject_native_mutations(fixture, (
                ('body_hash', lambda row: row['python_body'].update(declared_sha256='f' * 64)),
                ('truncated', lambda row: row['python_body'].update(raw_hex=row['python_body']['raw_hex'][:-2])),
                ('incomplete', lambda row: row['python_body'].update(complete=False)),
                ('declared_length', lambda row: row['python_body'].update(declared_length=row['python_body']['length'] + 1)),
                ('header_hash', lambda row: row['protocol'][5].update(sha256='f' * 64,
                    payload=str(row['protocol'][5]['length']) + ' ' + 'f' * 64)),
                ('header_length', lambda row: row['protocol'][5].update(length=row['protocol'][5]['length'] + 1,
                    payload=str(row['protocol'][5]['length'] + 1) + ' ' + row['protocol'][5]['sha256'])),
                ('nonhex', lambda row: row['python_body'].update(raw_hex='gg'))))

    def test_native_protocol_writer_sequence_READY_and_action_order_cannot_be_reset(self):
        with SyntheticSite() as site:
            fixture = synthetic_native_receipt(site)
            self.reject_native_mutations(fixture, (
                ('sequence', lambda row: row['protocol'][6].update(seq=1)),
                ('duplicate', lambda row: row['protocol'].insert(6, copy.deepcopy(row['protocol'][5]))),
                ('role', lambda row: row['protocol'][3].update(role='X')),
                ('direction', lambda row: row['protocol'][4].update(direction='received')),
                ('READY_pid', lambda row: row['protocol'][3].update(payload='999 ' + row['protocol'][3]['payload'].split(' ', 1)[1])),
                ('READY_flags', lambda row: row['protocol'][3].update(payload=row['protocol'][3]['payload'].replace(' 1 1 1 ', ' 1 0 1 '))),
                ('PRE_READY', lambda row: row['protocol'][0].update(payload='0')),
                ('arm_before_DATA', lambda row: row['protocol'].__setitem__(slice(5, 7), [row['protocol'][6], row['protocol'][5]])),
                ('action_before_ACK', lambda row: row['times'].update(primary_ns=row['times']['ack_ns'] - 1))))

    def test_native_transition_requires_same_PID_birth_boot_UID_parent_and_products(self):
        with SyntheticSite() as site:
            fixture = synthetic_native_receipt(site)
            self.reject_native_mutations(fixture, (
                ('PID', lambda row: row['identities']['P_transition'].update(pid=44)),
                ('birth', lambda row: row['identities']['P_pre_action'].update(birth=101)),
                ('boot', lambda row: row['identities']['X'].update(boot_id='00000000-0000-0000-0000-000000000002')),
                ('UID', lambda row: row['identities']['P_transition'].update(uid=os.getuid() + 1)),
                ('parent', lambda row: row['identities']['P_pre_action'].update(ppid=40)),
                ('product', lambda row: row['identities']['P_transition'].update(product=row['products']['guardian'])),
                ('dead', lambda row: row['identities']['P_pre_action'].update(state='Z')),
                ('returned_exec_success', lambda row: row['exec'].update(returned=True, result=0, errno=0)),
                ('missing_exec_EOF', lambda row: row['exec'].update(error_eof_ns=None)),
                ('kernel_argv', lambda row: row['kernel_python_argv'].__setitem__(1, '-E'))))

    def test_native_exact_reap_and_direct_G_observation_cannot_be_inferred_from_EOF(self):
        with SyntheticSite() as site:
            fixture = synthetic_native_receipt(site)
            self.reject_native_mutations(fixture, (
                ('wrong_reaped_PID', lambda row: row['wait'].update(result_pid=42)),
                ('unattempted_wait', lambda row: row['wait'].update(attempts=0)),
                ('unknown_wait', lambda row: row['wait'].update(raw_status=None)),
                ('wrong_wait_status', lambda row: row['wait'].update(raw_status=9)),
                ('wait_error', lambda row: row['wait'].update(errno=errno.EINTR)),
                ('no_terminal_poll', lambda row: row['polls'].pop()),
                ('no_report_EOF', lambda row: row['fd_ledger'].__setitem__(18,
                    {**row['fd_ledger'][18], 'evidence': 'unknown'}))))
            for label, change in (('timeout', {'timed_out': True}), ('outer_kill', {'kill_attempted': True}),
                                  ('not_reaped', {'reap_completed': False}), ('wrong_G', {'direct_child_pid': 44}),
                                  ('nonzero_G', {'returncode': 1})):
                with self.subTest(fault=label):
                    bad = list(fixture)
                    bad[1] = {**fixture[1], **change}
                    with self.assertRaises(ValueError):
                        self.parse_native(bad)

    def test_native_signal_uses_original_once_budget_after_ACK_and_never_normal(self):
        for case in ('normal', 'worker_loss'):
            with self.subTest(case=case), SyntheticSite() as site:
                fixture = synthetic_native_receipt(site, case)
                edits = [
                    ('attempts_twice', lambda row: row['signal'].update(attempts=2)),
                    ('consumed_reset', lambda row: row['signal'].update(budget_consumed=not row['signal']['budget_consumed'])),
                    ('flags', lambda row: row['signal'].update(flags=1))]
                if case == 'normal':
                    edits.append(('normal_signal', lambda row: row['signal'].update(budget_consumed=True,
                        attempts=1, result=0, errno=0, at_ns=row['times']['primary_ns'])))
                else:
                    edits += [
                        ('different_handle', lambda row: row['signal'].update(fd=99)),
                        ('failed_signal', lambda row: row['signal'].update(result=-1, errno=errno.ESRCH)),
                        ('unknown_signal', lambda row: row['signal'].update(result=None, errno=None)),
                        ('signal_before_ACK', lambda row: row['signal'].update(at_ns=row['times']['ack_ns'] - 1))]
                self.reject_native_mutations(fixture, edits)

    def test_native_absolute_deadlines_and_terminal_completion_never_reset(self):
        with SyntheticSite() as site:
            fixture = synthetic_native_receipt(site)
            self.reject_native_mutations(fixture, (
                ('reset_work', lambda row: row['deadlines'].update(work_ns=row['deadlines']['work_ns'] + 1)),
                ('primary_expired', lambda row: row['times'].update(primary_ns=row['deadlines']['work_ns'])),
                ('terminal_expired', lambda row: row['times'].update(terminal_ns=row['deadlines']['cleanup_ns'])),
                ('FD_completion_expired', lambda row: row['times'].update(fd_complete_ns=row['deadlines']['terminal_ns'])),
                ('final_expired', lambda row: row['times'].update(final_ns=row['deadlines']['total_ns'])),
                ('unknown_final', lambda row: row['times'].update(final_ns=None)),
                ('packet_clock_reversed', lambda row: row['protocol'][6].update(observed_ns=row['t0_ns'])),
                ('future_packet', lambda row: row['protocol'][3].update(at_ns=row['deadlines']['expiry_ns'] + 1))))

    def test_native_semantic_FD_close_inheritance_and_returned_DATA_are_required(self):
        with SyntheticSite() as site:
            fixture = synthetic_native_receipt(site)
            self.reject_native_mutations(fixture, (
                ('duplicate_original', lambda row: row['fd_ledger'].append(copy.deepcopy(row['fd_ledger'][0]))),
                ('close_unknown', lambda row: row['fd_ledger'][0].update(evidence='unknown', close={
                    'attempted': False, 'result': None, 'errno': None, 'at_ns': None}, badfd={
                    'attempted': False, 'result': None, 'errno': None, 'at_ns': None})),
                ('reclose_generation', lambda row: row['fd_ledger'][0].update(generation=0)),
                ('not_EBADF', lambda row: row['fd_ledger'][0]['badfd'].update(errno=0)),
                ('retained_script_CLOEXEC', lambda row: row['fd_flags'][1]['after'].update(result=1)),
                ('exec_error_not_CLOEXEC', lambda row: row['fd_flags'][8]['after'].update(result=0)),
                ('pidfd_dead', lambda row: row['handle']['live_poll'].update(result=1, revents=1))))
            for label, change in (
                ('package_missing', lambda data: data['snapshots']['before']['package_origins'].pop('torch')),
                ('metadata_version', lambda data: data['snapshots']['before']['metadata']['versions'].update(torch='wrong')),
                ('dependency_grant', lambda data: data.update(dependency_consistency_verified=True)),
                ('P_identity', lambda data: data['identity'].update(birth=101)),
                ('captured_worker_stat', lambda data: data['startup']['captured']['worker']['after'].__setitem__(1, 99)),
                ('fabricated_P_fcntl_return', lambda data: data['startup']['captured']['worker'].update(badfd_result=-1))):
                with self.subTest(fault=label):
                    bad = copy.deepcopy(fixture[0])
                    data = observer.closed_json(bytes.fromhex(bad['python_body']['raw_hex']))
                    change(data)
                    replace_python_body(bad, data)
                    with self.assertRaises(ValueError):
                        self.parse_native(fixture, bad)

    def test_negative_native_close_failure_preserves_actual_results_and_rejects_malformed_facts(self):
        with SyntheticSite() as site:
            fixture = synthetic_native_receipt(site)
            for close_errno in (errno.EINTR, errno.EBADF):
                with self.subTest(close_errno=close_errno):
                    row = copy.deepcopy(fixture[0])
                    failed = row['fd_ledger'][0]
                    failed['close'].update(result=-1, errno=close_errno)
                    row.update(native_success=False, fd_ledger=[failed], protocol=[],
                        python_body={'complete': False, 'declared_length': None, 'declared_sha256': None,
                                     'length': 0, 'raw_hex': ''}, kernel_python_argv=None,
                        error={'stage': 'first_parent_close', 'operation': 'once_close_EBADF',
                               'errno': close_errno, 'result_known': True, 'result': -1,
                               'at_ns': failed['close']['at_ns']})
                    row['identities'].update(P_transition=None, P_pre_action=None)
                    row['exec'] = {'attempted': None, 'returned': None, 'result': None, 'errno': None,
                                   'enter_ns': None, 'error_eof_ns': None, 'error_pipe_result': None}
                    row['handle']['close'] = row['handle']['badfd'] = {
                        'attempted': False, 'result': None, 'errno': None, 'at_ns': None}
                    row['polls'] = row['polls'][:1]
                    row['wait'] = {'attempts': 0, 'result_pid': None, 'raw_status': None,
                                   'errno': None, 'at_ns': None}
                    row['times'] = dict.fromkeys(observer.TIME_NAMES)
                    parsed = self.parse_native(fixture, row)
                    self.assertEqual(parsed, row)
                    self.assertFalse(parsed['native_success'])
                    self.assertEqual(parsed['fd_ledger'][0]['close']['result'], -1)
                    self.assertEqual(parsed['fd_ledger'][0]['close']['errno'], close_errno)
                    self.assertEqual(parsed['fd_ledger'][0]['badfd']['result'], -1)
                    self.assertEqual(parsed['fd_ledger'][0]['badfd']['errno'], errno.EBADF)
                    self.assertEqual(parsed['signal']['attempts'], 0)
                    for label, change in (
                        ('missing_close_errno', lambda bad: bad['fd_ledger'][0]['close'].pop('errno')),
                        ('unattempted_known_result', lambda bad: bad['fd_ledger'][0]['close'].update(attempted=False)),
                        ('noninteger_badfd', lambda bad: bad['fd_ledger'][0]['badfd'].update(result='-1')),
                        ('extra_error_field', lambda bad: bad['error'].update(inferred_cleanup=True))):
                        with self.subTest(fault=label):
                            bad = copy.deepcopy(row)
                            change(bad)
                            with self.assertRaises(ValueError):
                                self.parse_native(fixture, bad)

    @unittest.skipUnless(sys.platform == 'linux', 'Actual C to Python normal fixture requires Linux')
    def test_real_linux_normal_readonly_76_six_poison_case(self):
        self.real_case('normal')

    @unittest.skipUnless(sys.platform == 'linux', 'Actual C to Python worker-loss fixture requires Linux')
    def test_real_linux_worker_loss_once_pidfd_reap_case(self):
        self.real_case('worker_loss')

    @unittest.skipUnless(sys.platform == 'linux', 'Actual closed interpreter FD fexecve fixture requires Linux')
    def test_real_linux_closed_exec_fd_actual_EBADF_no_ARM_or_signal(self):
        self.real_case('normal', 'closed_exec')

    @unittest.skipUnless(sys.platform == 'linux', 'Actual Python bootstrap hash failure fixture requires Linux')
    def test_real_linux_bootstrap_script_hash_failure_no_ARM_or_signal(self):
        self.real_case('normal', 'script_hash')

    def real_case(self, case, fault='none'):
        helper, utility, linkage = observer.load_utilities()
        boot = helper.capture_self_identity()['boot_id']
        with SyntheticSite() as fixture:
            request, expected, row = fixture.fixture_request(case, boot)
            attempt = Path(row['attempt_directory'])
            fd = os.open(attempt, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                result = observer.run_fixture(request, expected,
                    utility.CompilerBackend(helper, attempt, fd), utility, linkage,
                    os.getpid(), os.getuid(), boot, fault=fault)
                self.assert_no_authority(result)
                self.assertEqual(result['runtime_attempts'], 1, result)
                self.assertTrue(result['runtime_returned_complete_facts'], result)
                native = result['runtime_report']
                self.assertEqual(native['wait']['raw_status'],
                    (0 if case == 'normal' else 9) if fault == 'none'
                    else ((71 if fault == 'closed_exec' else 70) << 8))
                self.assertFalse(fixture.sentinel.exists())
                if fault == 'none':
                    self.assertEqual(result['status'], 'success', result)
                    self.assertEqual(native['signal']['attempts'], int(case == 'worker_loss'))
                    self.assertIs(result[observer.SUCCESS[0]], True)
                    self.assertIs(result[observer.SUCCESS[1]], True)
                    self.assertIs(result[observer.SUCCESS[2]], case == 'normal')
                    self.assertIs(result[observer.SUCCESS[3]], case == 'worker_loss')
                else:
                    self.assertEqual(result['status'], 'failed', result)
                    self.assertFalse(any(result[name] for name in observer.SUCCESS))
                    self.assertEqual(native['signal']['attempts'], 0)
                    self.assertIsNone(native['times']['arm_ns'])
                    if fault == 'closed_exec':
                        self.assertTrue(native['exec']['attempted'])
                        self.assertTrue(native['exec']['returned'])
                        self.assertEqual(native['exec']['errno'], errno.EBADF)
                    else:
                        self.assertIsNone(native['exec']['attempted'])
                        self.assertIsNone(native['exec']['returned'])
                        self.assertIsNone(native['exec']['result'])
                        self.assertIsNone(native['exec']['errno'])
                        self.assertIsNone(native['identities']['P_transition'])
            finally:
                os.close(fd)


if __name__ == '__main__':
    unittest.main()
