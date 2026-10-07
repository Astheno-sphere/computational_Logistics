"""Linux process containment for fresh CPU fixtures, without resource authority.

The independent watchdog owns only its new worker and that worker's descendants.
It cannot restore a borrowed queue, checkpoint, sampling service or GPU lease.
No ready/armed/resource token is accepted or emitted. The production v8 launcher
must remain unavailable until a separate live resource/restoration protocol.

Controller loss is covered while this watchdog and the kernel remain alive.
Watchdog SIGKILL, host loss, privilege changes or an unreadable ownership tree
cannot promise cleanup: those cases never produce a successful proof.
"""
import argparse
import ctypes
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import select
import signal
import subprocess
import sys
import tempfile
import time


NONCE_KEY = 'FRONTIER_V8_PROCESS_NONCE'
MAX_CPU_SECONDS = 60.0
POLL_SECONDS = 0.01


class OwnedProcessError(RuntimeError):
    def __init__(self, message, receipt=None):
        super().__init__(message)
        self.receipt = receipt


@dataclass(frozen=True)
class ProcessIdentity:
    boot_id: str
    pid: int
    uid: int
    start_ticks: int
    ppid: int
    pgrp: int
    session: int


def _same_process(left, right):
    return (left.boot_id, left.pid, left.uid, left.start_ticks) == (
        right.boot_id, right.pid, right.uid, right.start_ticks)


def capture_identity(pid, proc_root=Path('/proc')):
    """Read kernel identity; this read-only helper grants no control rights."""
    proc_root = Path(proc_root)
    boot = (proc_root/'sys/kernel/random/boot_id').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', boot):
        raise OwnedProcessError('invalid kernel boot identity')
    stat = (proc_root/str(pid)/'stat').read_text()
    opening, closing = stat.find('('), stat.rfind(')')
    if opening < 1 or closing < opening or int(stat[:opening].strip()) != pid:
        raise OwnedProcessError('invalid process stat identity')
    fields = stat[closing+1:].split()
    if len(fields) < 20:
        raise OwnedProcessError('truncated process stat')
    uid_rows = [row for row in (proc_root/str(pid)/'status').read_text().splitlines()
                if row.startswith('Uid:')]
    if len(uid_rows) != 1:
        raise OwnedProcessError('missing process UID identity')
    uids = [int(value) for value in uid_rows[0].split()[1:]]
    if len(uids) != 4 or len(set(uids)) != 1:
        raise OwnedProcessError('process real/effective/saved/filesystem UIDs differ')
    return ProcessIdentity(boot, pid, uids[0], int(fields[19]),
                           int(fields[1]), int(fields[2]), int(fields[3]))


class _Kernel:
    def __init__(self, proc_root=Path('/proc')):
        self.proc_root = Path(proc_root)

    def identity(self, pid):
        return capture_identity(pid, self.proc_root)

    def children(self, pid):
        result = set()
        for task in (self.proc_root/str(pid)/'task').iterdir():
            try:
                result.update(int(x) for x in (task/'children').read_text().split())
            except FileNotFoundError:
                continue
        return result

    def nonce(self, pid):
        values = (self.proc_root/str(pid)/'environ').read_bytes().split(b'\0')
        return [value.split(b'=', 1)[1].decode() for value in values
                if value.startswith((NONCE_KEY+'=').encode())]

    def open_bound(self, expected):
        before = self.identity(expected.pid)
        if not _same_process(before, expected):
            raise OwnedProcessError('process identity changed before pidfd acquisition')
        fd = os.pidfd_open(expected.pid, 0)
        try:
            after = self.identity(expected.pid)
            if not _same_process(before, after):
                raise OwnedProcessError('process identity changed during pidfd acquisition')
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def exited(fd):
        poll = select.poll()
        poll.register(fd, select.POLLIN)
        return bool(poll.poll(0))

    @staticmethod
    def send(fd, signum):
        # No numeric PID/process-group signal fallback is permitted.
        signal.pidfd_send_signal(fd, signum, None, 0)


def _require_linux():
    if (sys.platform != 'linux' or not hasattr(os, 'pidfd_open')
            or not hasattr(signal, 'pidfd_send_signal') or not hasattr(select, 'poll')):
        raise OwnedProcessError('Linux pidfd process containment is unavailable')
    if os.getuid() != os.geteuid():
        raise OwnedProcessError('changed controller privilege is refused')


def _prctl(option, value):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(option, value, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl failed')


def _worker_parent_death(guard_pid):
    _prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG; leader backstop only.
    if os.getppid() != guard_pid:
        os._exit(125)


def _environment(nonce):
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
            'CUDA_VISIBLE_DEVICES': '', 'NVIDIA_VISIBLE_DEVICES': 'none', NONCE_KEY: nonce}


class _OwnedTree:
    """Only the single-threaded subreaper's freshly born child tree is eligible."""
    def __init__(self, kernel, guard, worker, nonce):
        if (worker.ppid != guard.pid or worker.uid != guard.uid
                or worker.boot_id != guard.boot_id or worker.start_ticks < guard.start_ticks
                or worker.pgrp != worker.pid or worker.session != worker.pid):
            raise OwnedProcessError('worker is not the fresh owned session leader')
        self.kernel, self.guard, self.worker, self.nonce = kernel, guard, worker, nonce
        self.members = {}
        self.errors = []
        self._add(worker, guard)

    def _add(self, identity, parent):
        if (identity.uid != self.guard.uid or identity.boot_id != self.guard.boot_id
                or identity.start_ticks < parent.start_ticks):
            raise OwnedProcessError('owned ancestry identity is invalid')
        fd = self.kernel.open_bound(identity)
        self.members[identity.pid] = {'identity': identity, 'parent': parent, 'fd': fd,
                                      'signals': [], 'nonce_observed': False}
        try:
            if not self.kernel.exited(fd):
                values = self.kernel.nonce(identity.pid)
                self.members[identity.pid]['nonce_observed'] = values == [self.nonce]
                if values != [self.nonce]:
                    self.errors.append('owned process nonce missing or changed')
        except (FileNotFoundError, PermissionError, UnicodeError):
            if not self.kernel.exited(fd):
                self.errors.append('owned process nonce is unreadable')

    def discover(self):
        # Traverse kernel child lists only. Shared host processes are neither
        # enumerated nor considered eligible because of matching argv/session.
        pending = [(pid, self.guard) for pid in self.kernel.children(self.guard.pid)]
        selected = {}
        while pending:
            pid, parent = pending.pop()
            if pid in selected:
                continue
            try:
                item = self.kernel.identity(pid)
            except FileNotFoundError:
                continue  # Exited descendants are adopted/rechecked at guard root.
            if item.ppid == self.guard.pid:
                parent = self.guard  # The subreaper adopted this owned orphan.
            elif item.ppid != parent.pid:
                raise OwnedProcessError('owned ancestry changed during discovery')
            if pid in self.members:
                if not _same_process(item, self.members[pid]['identity']):
                    raise OwnedProcessError('owned numeric PID was reused')
            else:
                try:
                    self._add(item, parent)
                except (FileNotFoundError, ProcessLookupError):
                    continue
            selected[pid] = item
            try:
                children = self.kernel.children(pid)
                after = self.kernel.identity(pid)
            except FileNotFoundError:
                if self.kernel.exited(self.members[pid]['fd']):
                    continue
                raise
            if not _same_process(item, after):
                raise OwnedProcessError('owned identity changed during child enumeration')
            pending.extend((child, item) for child in children)
        return selected

    def send(self, member, signum):
        fd = member['fd']
        if self.kernel.exited(fd):
            return
        try:
            current = self.kernel.identity(member['identity'].pid)
        except FileNotFoundError:
            if self.kernel.exited(fd):
                return
            raise
        if not _same_process(current, member['identity']):
            raise OwnedProcessError('owned process identity changed before signal')
        try:
            self.kernel.send(fd, signum)
        except ProcessLookupError:
            if self.kernel.exited(fd):
                return
            raise
        member['signals'].append(signum)

    def quiesce(self, process, cleanup_seconds):
        deadline = time.monotonic()+cleanup_seconds
        while time.monotonic() < deadline:
            self.discover()
            # Stop every live owned process before killing: they cannot continue
            # creating children once stopped. Newly adopted children are included.
            for member in list(self.members.values()):
                self.send(member, signal.SIGSTOP)
            self.discover()
            for member in list(self.members.values()):
                self.send(member, signal.SIGKILL)
            while True:
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    break
                if pid == 0:
                    break
                if pid == process.pid:
                    process.returncode = os.waitstatus_to_exitcode(status)
            self.discover()
            # Reparenting precedes pidfd exit notification. Observe every exit
            # first, then read the subreaper's children, avoiding an empty-tree
            # observation made before a dying parent adopts its descendants.
            if (all(self.kernel.exited(x['fd']) for x in self.members.values())
                    and not self.kernel.children(self.guard.pid)):
                process.wait(timeout=max(0.001, deadline-time.monotonic()))
                return {'status': 'owned_cpu_worker_tree_quiescence_proven',
                        'subreaper_children': [], 'worker_returncode': process.returncode,
                        'members': [{'identity': asdict(x['identity']),
                                     'observed_parent': asdict(x['parent']),
                                     'nonce_observed': x['nonce_observed'],
                                     'signals': x['signals'], 'pidfd_exit_observed': True}
                                    for x in self.members.values()]}
            time.sleep(POLL_SECONDS)
        raise OwnedProcessError('owned worker quiescence was not proven before cleanup deadline')

    def close(self):
        for member in self.members.values():
            os.close(member['fd'])


def _channel_state(fd):
    poll = select.poll()
    poll.register(fd, select.POLLIN | select.POLLHUP | select.POLLERR)
    if not poll.poll(0):
        return None
    return os.read(fd, 1)


def _exclusive_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.'+path.name+'.writing-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fp:
            json.dump(value, fp, indent=2, sort_keys=True)
            fp.write('\n')
            fp.flush()
            os.fsync(fp.fileno())
        # A hard link publishes completed bytes atomically and refuses an
        # existing final name. Existence can never expose an unfinished write.
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _watchdog(declaration_path, channel_fd):
    _require_linux()
    declaration_path = Path(declaration_path)
    spec = json.loads(declaration_path.read_text())
    kernel = _Kernel()
    controller = ProcessIdentity(**spec['controller'])
    guard = kernel.identity(os.getpid())
    process = tree = None
    controller_fd = None
    interrupted = []
    previous = {}
    result = {'schema_version': 1, 'scope': 'fresh_owned_CPU_worker_only',
              'nonce': spec['nonce'], 'controller': spec['controller'], 'guard': asdict(guard),
              'status': 'owned_cpu_worker_failed', 'reason': 'watchdog_prerequisite_failed',
              'quiescence': {'status': 'worker_not_started'},
              'limits': ['No GPU lease, queue/checkpoint/service restoration or model authority.',
                         'Controller loss containment requires this watchdog and kernel to survive.']}
    def interrupted_signal(signum, frame):
        interrupted.append(signum)
    try:
        if (guard.ppid != controller.pid or guard.uid != controller.uid
                or guard.boot_id != controller.boot_id or guard.session != guard.pid
                or guard.pgrp != guard.pid):
            raise OwnedProcessError('independent guard/controller relationship is invalid')
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != spec['source_sha256']:
            raise OwnedProcessError('watchdog source identity changed')
        controller_fd = kernel.open_bound(controller)
        _prctl(36, 1)  # PR_SET_CHILD_SUBREAPER: includes escaped sessions/orphaned descendants.
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[signum] = signal.signal(signum, interrupted_signal)
        # No worker starts until the controller registers this guard and sends S.
        while True:
            if kernel.exited(controller_fd):
                result['reason'] = 'controller_lost'
                return result
            if interrupted:
                result['reason'] = 'watchdog_interrupted'
                return result
            if time.monotonic() >= spec['deadline_monotonic']:
                result['reason'] = 'worker_deadline'
                return result
            message = _channel_state(channel_fd)
            if message == b'S':
                break
            if message is not None:
                result['reason'] = 'controller_channel_closed_or_invalid'
                return result
            time.sleep(POLL_SECONDS)
        with (declaration_path.parent/'worker.stdout.log').open('xb') as stdout, (
                declaration_path.parent/'worker.stderr.log').open('xb') as stderr:
            process = subprocess.Popen(spec['argv'], stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, close_fds=True, start_new_session=True,
                env=_environment(spec['nonce']),
                preexec_fn=lambda: _worker_parent_death(guard.pid))
        tree = _OwnedTree(kernel, guard, kernel.identity(process.pid), spec['nonce'])
        while True:
            tree.discover()
            if kernel.exited(controller_fd):
                result['reason'] = 'controller_lost'
                break
            if interrupted:
                result['reason'] = 'watchdog_interrupted'
                break
            if _channel_state(channel_fd) is not None:
                result['reason'] = 'controller_channel_closed_or_invalid'
                break
            if time.monotonic() >= spec['deadline_monotonic']:
                result['reason'] = 'worker_deadline'
                break
            if process.poll() is not None:
                result['reason'] = 'worker_complete' if process.returncode == 0 else 'worker_failed'
                if any(not kernel.exited(x['fd']) for x in tree.members.values()):
                    result['reason'] = 'descendant_outlived_worker'
                break
            time.sleep(POLL_SECONDS)
    except BaseException as error:
        result['error'] = str(error)
        result['reason'] = 'watchdog_error'
    finally:
        if process is not None:
            try:
                if tree is None:
                    tree = _OwnedTree(kernel, guard, kernel.identity(process.pid), spec['nonce'])
                result['quiescence'] = tree.quiesce(process, spec['cleanup_seconds'])
                result['ownership_errors'] = tree.errors
                if tree.errors:
                    result['reason'] = 'owned_identity_marker_failed'
                elif result['reason'] == 'worker_complete':
                    result['status'] = 'owned_cpu_worker_complete'
            except BaseException as error:
                result['quiescence'] = {'status': 'owned_cpu_worker_quiescence_unproven',
                                         'error': str(error)}
        if tree is not None:
            tree.close()
        if controller_fd is not None:
            os.close(controller_fd)
        os.close(channel_fd)
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        _exclusive_json(declaration_path.parent/'watchdog-receipt.json', result)
    return result


def run_owned_cpu_worker(argv, *, attempt_directory, timeout_seconds, cleanup_seconds=5.0):
    """Run one trusted CPU fixture, returning a process proof or raising with it.

    The caller supplies trusted CPU fixture code. Environment visibility does
    not establish a device reservation. This is not a model execution entry point.
    The output directory is fresh and exclusive. A private independent watchdog
    owns the new worker tree and writes its receipt even after controller loss.
    """
    _require_linux()
    if (not isinstance(argv, (list, tuple)) or not argv
            or any(not isinstance(x, str) or '\0' in x for x in argv)
            or not Path(argv[0]).is_absolute()):
        raise ValueError('an absolute executable argv is required; no shell is used')
    for value, maximum in ((timeout_seconds, MAX_CPU_SECONDS), (cleanup_seconds, 10.0)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError('invalid bounded CPU deadline')
    directory = Path(attempt_directory)
    if not directory.is_absolute() or directory.resolve() != directory:
        raise ValueError('fresh attempt directory must be absolute and have no symlink ancestors')
    kernel = _Kernel()
    controller = kernel.identity(os.getpid())
    nonce = secrets.token_hex(32)
    deadline = time.monotonic()+timeout_seconds
    directory.mkdir(mode=0o700)
    spec = {'schema_version': 1, 'scope': 'fresh_owned_CPU_worker_only', 'argv': list(argv),
            'nonce': nonce, 'controller': asdict(controller), 'deadline_monotonic': deadline,
            'cleanup_seconds': cleanup_seconds,
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    declaration = directory/'declaration.json'
    _exclusive_json(declaration, spec)
    read_fd, write_fd = os.pipe()
    guard_process = None
    guard_fd = None
    previous = {}
    interrupted = []
    def interrupted_signal(signum, frame):
        interrupted.append(signum)  # Defer until Popen construction registers the guard.
    try:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[signum] = signal.signal(signum, interrupted_signal)
        with (directory/'watchdog.stderr.log').open('xb') as stderr:
            guard_process = subprocess.Popen([sys.executable, '-I', '-S', str(Path(__file__).resolve()),
                '--watchdog', str(declaration), '--channel-fd', str(read_fd)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=stderr,
                start_new_session=True, close_fds=True, pass_fds=(read_fd,), env=_environment(nonce))
        guard = kernel.identity(guard_process.pid)
        if guard.ppid != controller.pid or guard.uid != controller.uid or guard.boot_id != controller.boot_id:
            raise OwnedProcessError('new guard is not a child of this controller')
        guard_fd = kernel.open_bound(guard)
        if not interrupted and not kernel.exited(guard_fd):
            os.write(write_fd, b'S')
        while not kernel.exited(guard_fd):
            if interrupted and write_fd is not None:
                os.close(write_fd)
                write_fd = None
            if time.monotonic() > deadline+cleanup_seconds+2:
                raise OwnedProcessError('independent watchdog completion is unproven')
            time.sleep(POLL_SECONDS)
        guard_process.wait(timeout=1)
        receipt_path = directory/'watchdog-receipt.json'
        if not receipt_path.is_file():
            raise OwnedProcessError('independent watchdog produced no process receipt')
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get('nonce') != nonce or receipt.get('controller') != asdict(controller)
                or receipt.get('guard') != asdict(guard)):
            raise OwnedProcessError('watchdog receipt identity mismatch')
        proof = receipt.get('quiescence', {})
        if (interrupted or guard_process.returncode != 0
                or receipt.get('status') != 'owned_cpu_worker_complete'
                or proof.get('status') != 'owned_cpu_worker_tree_quiescence_proven'
                or proof.get('subreaper_children') != []
                or proof.get('worker_returncode') != 0
                or not proof.get('members')
                or any(x.get('pidfd_exit_observed') is not True for x in proof['members'])):
            raise OwnedProcessError('owned CPU worker failed closed', receipt)
        return receipt
    finally:
        for fd in (read_fd, write_fd, guard_fd):
            if fd is not None:
                os.close(fd)
        if guard_process is not None and guard_process.returncode is None:
            try:
                # Closing the start/cancel pipe independently requests cleanup.
                # Reaping our direct child never signals another numeric PID.
                guard_process.wait(timeout=cleanup_seconds+2)
            except subprocess.TimeoutExpired:
                pass  # The caller already has no successful process proof.
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watchdog', required=True)
    parser.add_argument('--channel-fd', required=True, type=int)
    args = parser.parse_args()
    result = _watchdog(args.watchdog, args.channel_fd)
    return 0 if result['status'] == 'owned_cpu_worker_complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
