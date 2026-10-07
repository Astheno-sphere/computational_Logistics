"""CPU ownership fixtures; live pidfd tests run only on Linux, without models/GPU."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_owned_process as owned


BOOT = '01234567-89ab-cdef-0123-456789abcdef'
ROOT = Path(__file__).resolve().parents[1]


def identity(pid, ppid, birth=100, uid=1000, session=None):
    return owned.ProcessIdentity(BOOT, pid, uid, birth, ppid, pid,
                                 pid if session is None else session)


class ProcFixture:
    def __init__(self, root):
        self.root = Path(root)
        boot = self.root/'sys/kernel/random'
        boot.mkdir(parents=True)
        (boot/'boot_id').write_text(BOOT+'\n')

    def add(self, item, comm='CPU fixture (with ) parentheses)', state='S', uids=None):
        p = self.root/str(item.pid)
        p.mkdir(exist_ok=True)
        fields = [state, str(item.ppid), str(item.pgrp), str(item.session)]+['0']*15+[str(item.start_ticks)]
        (p/'stat').write_text(str(item.pid)+' ('+comm+') '+' '.join(fields)+'\n')
        (p/'status').write_text('Uid:\t'+'\t'.join(str(x) for x in (uids or [item.uid]*4))+'\n')
        task = p/'task'/str(item.pid)
        task.mkdir(parents=True, exist_ok=True)
        (task/'children').write_text('')
        (p/'environ').write_bytes((owned.NONCE_KEY+'=nonce').encode()+b'\0')


class FakeKernel:
    def __init__(self, *items):
        self.items = {x.pid: x for x in items}
        self.exits = set()
        self.calls = []
        self.closed = []
        self.nonces = {}
        self.on_send = None

    def identity(self, pid):
        if pid not in self.items:
            raise FileNotFoundError(pid)
        return self.items[pid]

    def identities(self):
        return dict(self.items)

    def children(self, pid):
        return {x.pid for x in self.items.values() if x.ppid == pid}

    def open_bound(self, expected):
        if not owned._same_process(self.identity(expected.pid), expected):
            raise owned.OwnedProcessError('fixture identity mismatch')
        self.calls.append(('open', expected.pid))
        return expected.pid+10000

    def exited(self, fd):
        return fd-10000 in self.exits

    def nonce(self, pid):
        return self.nonces.get(pid, ['nonce'])

    def send(self, fd, signum):
        pid = fd-10000
        self.calls.append(('signal', pid, signum))
        if self.on_send:
            self.on_send(pid, signum)
        if signum == signal.SIGKILL:
            self.exits.add(pid)
            parent = self.items.pop(pid).ppid
            for child, item in list(self.items.items()):
                if item.ppid == pid:
                    self.items[child] = replace(item, ppid=parent)


class OwnedProcessFixtureTests(unittest.TestCase):
    def test_proc_stat_parentheses_and_uid_are_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = ProcFixture(temp)
            expected = identity(51, 50, birth=200)
            fixture.add(expected)
            self.assertEqual(owned.capture_identity(51, Path(temp)), expected)
            fixture.add(expected, uids=[1000, 0, 0, 0])
            with self.assertRaisesRegex(owned.OwnedProcessError, 'UIDs differ'):
                owned.capture_identity(51, Path(temp))

    def test_boot_and_truncated_stat_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = ProcFixture(temp)
            fixture.add(identity(51, 50))
            (Path(temp)/'sys/kernel/random/boot_id').write_text('old-host')
            with self.assertRaisesRegex(owned.OwnedProcessError, 'boot identity'):
                owned.capture_identity(51, Path(temp))
            (Path(temp)/'sys/kernel/random/boot_id').write_text(BOOT)
            (Path(temp)/'51/stat').write_text('51 (fixture) S 50')
            with self.assertRaisesRegex(owned.OwnedProcessError, 'truncated'):
                owned.capture_identity(51, Path(temp))

    def test_pidfd_open_sandwich_refuses_reuse_boot_or_uid_change(self):
        original = identity(51, 50)
        for changed in (replace(original, start_ticks=101), replace(original, uid=1001),
                        replace(original, boot_id='f'*36)):
            with self.subTest(changed=changed), patch.object(owned.os, 'pidfd_open', create=True, return_value=17) as opened, patch.object(owned.os, 'close') as closed:
                kernel = owned._Kernel()
                with patch.object(kernel, 'identity', side_effect=[original, changed]):
                    with self.assertRaisesRegex(owned.OwnedProcessError, 'during pidfd'):
                        kernel.open_bound(original)
                opened.assert_called_once_with(51, 0)
                closed.assert_called_once_with(17)
        kernel = owned._Kernel()
        with patch.object(kernel, 'identity', return_value=replace(original, start_ticks=999)), patch.object(owned.os, 'pidfd_open', create=True) as opened:
            with self.assertRaisesRegex(owned.OwnedProcessError, 'before pidfd'):
                kernel.open_bound(original)
            opened.assert_not_called()

    def test_pidfd_signals_have_no_numeric_pid_fallback(self):
        with patch.object(owned.signal, 'pidfd_send_signal', create=True) as send, patch.object(owned.os, 'kill') as kill, patch.object(owned.os, 'killpg') as killpg:
            owned._Kernel.send(17, signal.SIGKILL)
            send.assert_called_once_with(17, signal.SIGKILL, None, 0)
            kill.assert_not_called()
            killpg.assert_not_called()

    def test_interrupted_json_write_never_exposes_final_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'receipt.json'
            def interrupted(value, fp, **kwargs):
                fp.write('{"unfinished":')
                fp.flush()
                self.assertFalse(target.exists())
                raise OSError('CPU fixture interrupted JSON write')
            with patch.object(owned.json, 'dump', side_effect=interrupted):
                with self.assertRaisesRegex(OSError, 'interrupted JSON'):
                    owned._exclusive_json(target, {'complete': 1})
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_atomic_link_publishes_complete_flushed_json_only(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'receipt.json'
            value = {'process_proof': {'members': [1, 2], 'status': 'complete'}}
            real_link, real_fsync = os.link, os.fsync
            order = []
            def fsync(fd):
                order.append('fsync')
                return real_fsync(fd)
            def publish(source, final):
                self.assertFalse(target.exists())
                self.assertEqual(json.loads(Path(source).read_text()), value)
                self.assertEqual(order, ['fsync'])
                order.append('link')
                return real_link(source, final)
            with patch.object(owned.os, 'fsync', side_effect=fsync), patch.object(owned.os, 'link', side_effect=publish):
                owned._exclusive_json(target, value)
            self.assertEqual(order, ['fsync', 'link', 'fsync'])
            self.assertEqual(json.loads(target.read_text()), value)
            self.assertEqual(list(Path(temp).iterdir()), [target])

    def test_exclusive_json_preserves_existing_final_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'receipt.json'
            target.write_bytes(b'{"original": true}\n')
            with self.assertRaises(FileExistsError):
                owned._exclusive_json(target, {'replacement': True})
            self.assertEqual(target.read_bytes(), b'{"original": true}\n')
            self.assertEqual(list(Path(temp).iterdir()), [target])

    def tree(self):
        guard, worker = identity(50, 49), identity(51, 50, birth=101)
        kernel = FakeKernel(guard, worker)
        return kernel, owned._OwnedTree(kernel, guard, worker, 'nonce')

    def test_ancestry_excludes_unrelated_even_same_session_and_nonce(self):
        kernel, tree = self.tree()
        child = replace(identity(52, 51, birth=102), session=900, pgrp=900)
        unrelated = replace(identity(99, 1, birth=103), session=51, pgrp=51)
        kernel.items.update({52: child, 99: unrelated})
        tree.discover()
        self.assertEqual(set(tree.members), {51, 52})
        tree.send(tree.members[52], signal.SIGKILL)
        self.assertNotIn(('open', 99), kernel.calls)
        self.assertIn(('signal', 52, signal.SIGKILL), kernel.calls)
        self.assertIn(99, kernel.items)

    def test_orphan_adopted_by_subreaper_remains_owned(self):
        kernel, tree = self.tree()
        kernel.items[52] = identity(52, 50, birth=102)
        tree.discover()
        self.assertEqual(tree.members[52]['parent'].pid, 50)

    def test_birth_uid_and_initial_session_mismatch_fail_closed(self):
        guard = identity(50, 49)
        worker = identity(51, 50, birth=101)
        for changed in (replace(worker, uid=1001), replace(worker, start_ticks=99),
                        replace(worker, ppid=1), replace(worker, session=44)):
            with self.subTest(changed=changed):
                kernel = FakeKernel(guard, changed)
                with self.assertRaises(owned.OwnedProcessError):
                    owned._OwnedTree(kernel, guard, changed, 'nonce')
                self.assertEqual(kernel.calls, [])
        kernel, tree = self.tree()
        kernel.items[52] = identity(52, 51, birth=90)
        with self.assertRaisesRegex(owned.OwnedProcessError, 'ancestry'):
            tree.discover()
        self.assertNotIn(('open', 52), kernel.calls)

    def test_nonce_mismatch_does_not_confer_success_or_capture_unrelated(self):
        kernel, tree = self.tree()
        kernel.items[52] = identity(52, 51, birth=102)
        kernel.nonces[52] = []
        tree.discover()
        self.assertEqual(tree.errors, ['owned process nonce missing or changed'])
        self.assertFalse(tree.members[52]['nonce_observed'])

    def test_reused_pid_is_refused_before_signal(self):
        kernel, tree = self.tree()
        kernel.items[51] = replace(kernel.items[51], start_ticks=999)
        with self.assertRaisesRegex(owned.OwnedProcessError, 'before signal'):
            tree.send(tree.members[51], signal.SIGKILL)
        self.assertFalse(any(x[0] == 'signal' for x in kernel.calls))
        with self.assertRaisesRegex(owned.OwnedProcessError, 'reused'):
            tree.discover()

    def test_child_born_during_cleanup_is_included_and_pidfds_prove_exit(self):
        kernel, tree = self.tree()
        kernel.items[99] = identity(99, 1, birth=102)
        def spawn(pid, signum):
            if pid == 51 and signum == signal.SIGSTOP and 52 not in kernel.exits:
                kernel.items[52] = identity(52, 51, birth=102)
        kernel.on_send = spawn
        process = Mock(pid=51, returncode=-9)
        with patch.object(owned.os, 'waitpid', side_effect=ChildProcessError), patch.object(owned.os, 'kill') as kill, patch.object(owned.os, 'killpg') as killpg:
            proof = tree.quiesce(process, 0.2)
        self.assertEqual(proof['status'], 'owned_cpu_worker_tree_quiescence_proven')
        self.assertEqual({x['identity']['pid'] for x in proof['members']}, {51, 52})
        self.assertTrue(all(x['pidfd_exit_observed'] for x in proof['members']))
        self.assertIn(99, kernel.items)
        kill.assert_not_called()
        killpg.assert_not_called()

    def test_cleanup_never_claims_success_with_live_pidfd(self):
        kernel, tree = self.tree()
        kernel.send = lambda fd, signum: None
        process = Mock(pid=51, returncode=None)
        with patch.object(owned.os, 'waitpid', return_value=(0, 0)):
            with self.assertRaisesRegex(owned.OwnedProcessError, 'not proven'):
                tree.quiesce(process, 0.02)

    def test_cpu_environment_discards_inherited_loader_credentials_and_devices(self):
        with patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': '0,1', 'AWS_SECRET_ACCESS_KEY': 'fixture-secret', 'PYTHONPATH': '/shared', 'LD_PRELOAD': '/shared/library'}):
            environment = owned._environment('nonce')
        self.assertEqual(environment['CUDA_VISIBLE_DEVICES'], '')
        self.assertEqual(environment['NVIDIA_VISIBLE_DEVICES'], 'none')
        for key in ('AWS_SECRET_ACCESS_KEY', 'PYTHONPATH', 'LD_PRELOAD'):
            self.assertNotIn(key, environment)

    def test_unavailable_kernel_creates_no_attempt_or_process(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(owned.sys, 'platform', 'darwin'), patch.object(owned.subprocess, 'Popen') as spawn:
            output = Path(temp)/'fresh'
            with self.assertRaisesRegex(owned.OwnedProcessError, 'unavailable'):
                owned.run_owned_cpu_worker([sys.executable, '-c', 'pass'], attempt_directory=output, timeout_seconds=1)
            self.assertFalse(output.exists())
            spawn.assert_not_called()

    def test_invalid_bounds_shell_or_reused_directory_do_not_spawn(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(owned, '_require_linux'), patch.object(owned.subprocess, 'Popen') as spawn:
            for value in (True, 0, -1, 61, float('nan'), float('inf')):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    owned.run_owned_cpu_worker([sys.executable], attempt_directory=Path(temp)/'fresh', timeout_seconds=value)
            with self.assertRaises(ValueError):
                owned.run_owned_cpu_worker('python pass', attempt_directory=Path(temp)/'fresh', timeout_seconds=1)
            with self.assertRaises(ValueError):
                owned.run_owned_cpu_worker(['python', '-c', 'pass'], attempt_directory=Path(temp)/'fresh', timeout_seconds=1)
            spawn.assert_not_called()

    def test_existing_attempt_and_symlink_parent_are_refused(self):
        controller = identity(49, 1)
        with tempfile.TemporaryDirectory() as temp, patch.object(owned, '_require_linux'), patch.object(owned, '_Kernel', return_value=FakeKernel(controller)), patch.object(owned.os, 'getpid', return_value=49), patch.object(owned.subprocess, 'Popen') as spawn:
            root = Path(temp).resolve()
            existing = root/'old-attempt'
            existing.mkdir()
            with self.assertRaises(FileExistsError):
                owned.run_owned_cpu_worker([sys.executable], attempt_directory=existing, timeout_seconds=1)
            link = root/'link'
            link.symlink_to(existing, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink ancestors'):
                owned.run_owned_cpu_worker([sys.executable], attempt_directory=link/'fresh', timeout_seconds=1)
            spawn.assert_not_called()

    def test_signal_during_guard_popen_defers_cancel_and_never_arms_worker(self):
        controller, guard = identity(49, 1), identity(50, 49, birth=101)
        kernel = FakeKernel(controller, guard)
        handlers = {}
        previous = {x: object() for x in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        def install(signum, handler):
            old = handlers.get(signum, previous[signum])
            handlers[signum] = handler
            return old
        def spawn(argv, **kwargs):
            declaration = Path(argv[argv.index('--watchdog')+1])
            spec = json.loads(declaration.read_text())
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            kernel.exits.add(50)
            (declaration.parent/'watchdog-receipt.json').write_text(json.dumps({
                'nonce': spec['nonce'], 'controller': spec['controller'],
                'guard': owned.asdict(guard), 'status': 'owned_cpu_worker_failed',
                'quiescence': {'status': 'worker_not_started'}}))
            return Mock(pid=50)
        with tempfile.TemporaryDirectory() as temp, patch.object(owned, '_require_linux'), patch.object(owned, '_Kernel', return_value=kernel), patch.object(owned.os, 'getpid', return_value=49), patch.object(owned.os, 'pipe', return_value=(90, 91)), patch.object(owned.os, 'close') as close, patch.object(owned.os, 'write') as write, patch.object(owned.signal, 'signal', side_effect=install), patch.object(owned.subprocess, 'Popen', side_effect=spawn) as opened:
            with self.assertRaises(owned.OwnedProcessError) as caught:
                owned.run_owned_cpu_worker([sys.executable], attempt_directory=Path(temp).resolve()/'fresh', timeout_seconds=1)
            self.assertEqual(caught.exception.receipt['quiescence']['status'], 'worker_not_started')
            write.assert_not_called()
            self.assertTrue(opened.call_args.kwargs['start_new_session'])
            self.assertEqual(opened.call_args.kwargs['pass_fds'], (90,))
            self.assertIn(91, [x.args[0] for x in close.call_args_list])
        self.assertEqual(handlers, previous)

    def test_missing_guard_receipt_cannot_claim_process_proof(self):
        controller, guard = identity(49, 1), identity(50, 49, birth=101)
        kernel = FakeKernel(controller, guard)
        kernel.exits.add(50)
        with tempfile.TemporaryDirectory() as temp, patch.object(owned, '_require_linux'), patch.object(owned, '_Kernel', return_value=kernel), patch.object(owned.os, 'getpid', return_value=49), patch.object(owned.os, 'pipe', return_value=(90, 91)), patch.object(owned.os, 'close'), patch.object(owned.subprocess, 'Popen', return_value=Mock(pid=50)):
            with self.assertRaisesRegex(owned.OwnedProcessError, 'no process receipt'):
                owned.run_owned_cpu_worker([sys.executable], attempt_directory=Path(temp).resolve()/'fresh', timeout_seconds=1)

    def test_guard_signal_during_worker_popen_cleans_registered_child(self):
        controller, guard, worker = identity(49, 1), identity(50, 49, birth=101), identity(51, 50, birth=102)
        kernel = FakeKernel(controller, guard, worker)
        handlers = {}
        def install(signum, handler):
            old = handlers.get(signum, signal.SIG_DFL)
            handlers[signum] = handler
            return old
        def spawn(*args, **kwargs):
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            return Mock(pid=51, returncode=-9)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'declaration.json'
            path.write_text(json.dumps({'nonce': 'nonce', 'controller': owned.asdict(controller),
                'source_sha256': hashlib.sha256(Path(owned.__file__).read_bytes()).hexdigest(),
                'deadline_monotonic': time.monotonic()+1, 'cleanup_seconds': 0.2, 'argv': [sys.executable]}))
            with patch.object(owned, '_require_linux'), patch.object(owned, '_Kernel', return_value=kernel), patch.object(owned.os, 'getpid', return_value=50), patch.object(owned, '_prctl'), patch.object(owned, '_channel_state', return_value=b'S'), patch.object(owned.signal, 'signal', side_effect=install), patch.object(owned.subprocess, 'Popen', side_effect=spawn), patch.object(owned.os, 'close'), patch.object(owned.os, 'waitpid', side_effect=ChildProcessError):
                receipt = owned._watchdog(path, 90)
            self.assertEqual(receipt['reason'], 'watchdog_interrupted')
            self.assertEqual(receipt['status'], 'owned_cpu_worker_failed')
            self.assertEqual(receipt['quiescence']['status'], 'owned_cpu_worker_tree_quiescence_proven')
            self.assertIn(('signal', 51, signal.SIGKILL), kernel.calls)

    def test_pidfd_exit_is_observed_before_final_empty_child_proof(self):
        kernel, tree = self.tree()
        original_exited, original_children = kernel.exited, kernel.children
        order = []
        def exited(fd):
            order.append('exit')
            return original_exited(fd)
        def children(pid):
            order.append('children')
            return original_children(pid)
        kernel.exited, kernel.children = exited, children
        with patch.object(owned.os, 'waitpid', side_effect=ChildProcessError):
            proof = tree.quiesce(Mock(pid=51, returncode=-9), 0.2)
        self.assertEqual(proof['status'], 'owned_cpu_worker_tree_quiescence_proven')
        self.assertEqual(order[-2:], ['exit', 'children'])

    def test_independent_watchdog_binds_controller_loss_and_quiesces_worker(self):
        controller, guard, worker = identity(49, 1), identity(50, 49, birth=101), identity(51, 50, birth=102)
        kernel = FakeKernel(controller, guard, worker)
        process = Mock(pid=51, returncode=-9)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'declaration.json'
            path.write_text(json.dumps({'nonce': 'nonce', 'controller': owned.asdict(controller),
                'source_sha256': hashlib.sha256(Path(owned.__file__).read_bytes()).hexdigest(),
                'deadline_monotonic': time.monotonic()+1, 'cleanup_seconds': 0.2,
                'argv': [sys.executable, '-c', 'pass']}))
            def spawn(*args, **kwargs):
                kernel.exits.add(49)
                return process
            with patch.object(owned, '_require_linux'), patch.object(owned, '_Kernel', return_value=kernel), patch.object(owned.os, 'getpid', return_value=50), patch.object(owned, '_prctl') as prctl, patch.object(owned, '_channel_state', return_value=b'S'), patch.object(owned.subprocess, 'Popen', side_effect=spawn) as opened, patch.object(owned.os, 'close'), patch.object(owned.os, 'waitpid', side_effect=ChildProcessError):
                receipt = owned._watchdog(path, 90)
            self.assertEqual(receipt['reason'], 'controller_lost')
            self.assertEqual(receipt['status'], 'owned_cpu_worker_failed')
            self.assertEqual(receipt['quiescence']['status'], 'owned_cpu_worker_tree_quiescence_proven')
            self.assertTrue(opened.call_args.kwargs['start_new_session'])
            self.assertTrue(opened.call_args.kwargs['close_fds'])
            prctl.assert_called_once_with(36, 1)
            self.assertEqual(json.loads((Path(temp)/'watchdog-receipt.json').read_text()), receipt)
            self.assertNotIn('resource_authority', receipt)
            self.assertNotIn('ready', receipt)

    def test_dead_controller_never_starts_worker(self):
        controller, guard = identity(49, 1), identity(50, 49, birth=101)
        kernel = FakeKernel(controller, guard)
        kernel.exits.add(49)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'declaration.json'
            path.write_text(json.dumps({'nonce': 'nonce', 'controller': owned.asdict(controller),
                'source_sha256': hashlib.sha256(Path(owned.__file__).read_bytes()).hexdigest(),
                'deadline_monotonic': time.monotonic()+1, 'cleanup_seconds': 0.2, 'argv': [sys.executable]}))
            with patch.object(owned, '_require_linux'), patch.object(owned, '_Kernel', return_value=kernel), patch.object(owned.os, 'getpid', return_value=50), patch.object(owned, '_prctl'), patch.object(owned.subprocess, 'Popen') as opened, patch.object(owned.os, 'close'):
                receipt = owned._watchdog(path, 90)
            self.assertEqual(receipt['reason'], 'controller_lost')
            self.assertEqual(receipt['quiescence']['status'], 'worker_not_started')
            opened.assert_not_called()


LIVE_PIDFD = sys.platform == 'linux' and hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal')


@unittest.skipUnless(LIVE_PIDFD, 'live Linux pidfd kernel required; CPU fixtures above remain active')
class OwnedProcessLinuxTests(unittest.TestCase):
    def test_live_cpu_worker_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            result = owned.run_owned_cpu_worker([sys.executable, '-I', '-S', '-c', 'print("CPU fixture")'],
                attempt_directory=Path(temp)/'fresh', timeout_seconds=5)
            self.assertEqual(result['status'], 'owned_cpu_worker_complete')
            self.assertEqual(result['quiescence']['worker_returncode'], 0)
            self.assertEqual(result['quiescence']['subreaper_children'], [])

    def test_live_cpu_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(owned.OwnedProcessError) as caught:
                owned.run_owned_cpu_worker([sys.executable, '-I', '-S', '-c', 'import time; time.sleep(10)'],
                    attempt_directory=Path(temp)/'fresh', timeout_seconds=0.25)
            self.assertEqual(caught.exception.receipt['reason'], 'worker_deadline')
            self.assertEqual(caught.exception.receipt['quiescence']['status'], 'owned_cpu_worker_tree_quiescence_proven')

    def test_live_forked_escaped_session_is_contained(self):
        code = 'import os,time; p=os.fork();\nif p==0:\n os.setsid(); time.sleep(10)\nelse:\n time.sleep(.1)'
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(owned.OwnedProcessError) as caught:
                owned.run_owned_cpu_worker([sys.executable, '-I', '-S', '-c', code],
                    attempt_directory=Path(temp)/'fresh', timeout_seconds=5)
            receipt = caught.exception.receipt
            self.assertEqual(receipt['reason'], 'descendant_outlived_worker')
            self.assertEqual(len(receipt['quiescence']['members']), 2)
            self.assertTrue(all(x['pidfd_exit_observed'] for x in receipt['quiescence']['members']))

    def test_live_controller_sigkill_leaves_independent_quiescence_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'fresh'
            worker_pid = Path(temp)/'worker.pid'
            code = 'import os,time; from pathlib import Path; Path('+repr(str(worker_pid))+').write_text(str(os.getpid())); time.sleep(30)'
            controller_code = ('import sys; from pathlib import Path; sys.path.insert(0, '+repr(str(ROOT))+'); '
                'from scripts.frontier_v8_owned_process import run_owned_cpu_worker; '
                'run_owned_cpu_worker('+repr([sys.executable, '-I', '-S', '-c', code])+', attempt_directory=Path('+repr(str(directory))+'), timeout_seconds=10)')
            controller = subprocess.Popen([sys.executable, '-I', '-S', '-c', controller_code],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            kernel = owned._Kernel()
            controller_fd = kernel.open_bound(kernel.identity(controller.pid))
            worker_fd = None
            try:
                deadline = time.monotonic()+5
                while not worker_pid.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(worker_pid.exists(), 'fresh CPU fixture did not start')
                worker_fd = kernel.open_bound(kernel.identity(int(worker_pid.read_text())))
                kernel.send(controller_fd, signal.SIGKILL)
                controller.wait(timeout=2)
                receipt_path = directory/'watchdog-receipt.json'
                while not receipt_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                receipt = json.loads(receipt_path.read_text())
                self.assertEqual(receipt['reason'], 'controller_lost')
                self.assertEqual(receipt['quiescence']['status'], 'owned_cpu_worker_tree_quiescence_proven')
                self.assertTrue(kernel.exited(worker_fd))
            finally:
                if controller.poll() is None:
                    kernel.send(controller_fd, signal.SIGKILL)
                    controller.wait(timeout=2)
                os.close(controller_fd)
                if worker_fd is not None:
                    os.close(worker_fd)


if __name__ == '__main__':
    unittest.main()
