"""Resource-episode preparation: raw CPU inventory and real Linux pidfd fixtures."""
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.request import urlopen

from scripts import frontier_v8_resource_episode as episode
from scripts import frontier_v8_owned_process as process


ROOT = Path(__file__).resolve().parents[1]
BOOT = '01234567-89ab-cdef-0123-456789abcdef'
LINUX = sys.platform == 'linux' and hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal')


def gpu_fixture():
    return {'gpus': [{'index': i, 'uuid': 'GPU-fixture-' + str(i), 'name': 'NVIDIA H100',
                     'total_memory_mib': 81559, 'memory_used_mib': 0, 'utilization_percent': 0}
                    for i in range(4)], 'compute_processes': []}


def baseline_for(probe, identity=None):
    return {'schema_version': 1, 'mode': 'no_borrow', 'acquisition_id': 'a' * 32,
        'node_alias': 'ms-n1-1', 'boot_id': identity.boot_id if identity else BOOT,
        'uid': identity.uid if identity else os.getuid(), 'immutable_roots': [], 'immutable_files': [],
        'original_processes': [], 'services': [], 'progress': [], 'actual_optimizer_boundary_verified': False,
        'protected_gpu_inventory': {'gpus': [episode._gpu_identity(g) for g in probe['gpus'][:2]],
                                    'compute_processes': []}}


def restoration_spec(probe_path, seconds=2):
    return {'schema_version': 1, 'max_recovery_seconds': seconds, 'poll_interval_s': 0.04,
            'proc_root': '/proc', 'gpu_fixture_path': str(probe_path)}


class FakeKernel:
    def __init__(self, proc_root, identities):
        self.proc_root = Path(proc_root)
        self.items = {x.pid: x for x in identities}
        self.fds, self.exits, self.calls = {}, set(), []
        for item in identities:
            self.write(item)

    def write(self, item, nonce='n' * 64, original='a' * 32, state='S'):
        directory = self.proc_root / str(item.pid)
        directory.mkdir(parents=True, exist_ok=True)
        fields = [state, str(item.ppid), str(item.pgrp), str(item.session)] + ['0'] * 15 + [str(item.start_ticks)]
        (directory / 'stat').write_text(str(item.pid) + ' (fixture) ' + ' '.join(fields))
        (directory / 'environ').write_bytes((process.NONCE_KEY + '=' + nonce + '\0'
            + episode.ORIGINAL_NONCE_KEY + '=' + original + '\0').encode())
        (directory / 'cmdline').write_bytes(b'python\0fixture\0')

    def identity(self, pid):
        return self.items[pid]

    def open_bound(self, item):
        if not process._same_process(item, self.items[item.pid]):
            raise process.OwnedProcessError('identity changed')
        fd = os.open('/dev/null', os.O_RDONLY)
        self.fds[fd] = item.pid
        return fd

    def exited(self, fd):
        return self.fds[fd] in self.exits

    def children(self, pid):
        return {x.pid for x in self.items.values() if x.ppid == pid}

    def nonce(self, pid):
        return episode._nonce(self, pid, process.NONCE_KEY)

    def send(self, fd, signum):
        pid = self.fds[fd]
        self.calls.append((pid, signum))
        self.write(self.items[pid], state='T' if signum == signal.SIGSTOP else 'S')


class ResourceEpisodeUnitTests(unittest.TestCase):
    def setUp(self):
        capture = patch.object(process, 'capture_identity', return_value=SimpleNamespace(boot_id=BOOT))
        capture.start()
        self.addCleanup(capture.stop)

    def test_work_and_restoration_bounds_are_distinct(self):
        for bad in (True, 0, -1, float('inf'), float('nan'), 4501):
            with self.assertRaises(ValueError):
                episode._bounded(bad, 4500)
        self.assertEqual(episode._bounded(4500, 4500), 4500)
        with self.assertRaises(ValueError):
            episode._bounded(1501, 1500)

    def test_gpu0_and_gpu1_are_never_selected(self):
        for indices in ([0], [1], [2, 2], [], [4], [True]):
            with self.assertRaises(episode.EpisodeOwnershipError):
                episode._selected(gpu_fixture(), indices, set(), False)

    def test_low_utilization_cannot_hide_compute(self):
        probe = gpu_fixture()
        probe['compute_processes'].append({'gpu_uuid': 'GPU-fixture-2', 'pid': 52, 'process_name': 'foreign'})
        with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'unrelated compute'):
            episode._selected(probe, [2], set(), False)

    def test_free_gpu_requires_idle_memory_measurement(self):
        probe = gpu_fixture()
        for changes in ({'memory_used_mib': 17}, {'utilization_percent': 1}):
            changed = json.loads(json.dumps(probe))
            changed['gpus'][2].update(changes)
            with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'idle memory'):
                episode._selected(changed, [2], set(), False)
        del probe['gpus'][2]['memory_used_mib']
        with self.assertRaises(episode.EpisodeOwnershipError):
            episode._selected(probe, [2], set(), False)

    def test_borrowed_scope_reserves_all_original_gpus(self):
        probe = gpu_fixture()
        probe['compute_processes'] = [{'gpu_uuid': 'GPU-fixture-' + str(i), 'pid': 52,
                                      'process_name': 'fixture'} for i in (2, 3)]
        with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'all original GPUs'):
            episode._selected(probe, [2], {52}, True)
        self.assertEqual(len(episode._selected(probe, [2, 3], {52}, True)), 2)
        probe['compute_processes'].append({'gpu_uuid': 'GPU-fixture-2', 'pid': 53, 'process_name': 'foreign'})
        with self.assertRaises(episode.EpisodeOwnershipError):
            episode._selected(probe, [2, 3], {52}, True)

    def test_raw_gpu_inventory_refuses_duplicates_and_unknown_compute(self):
        for change in ('duplicate', 'unknown', 'protected_missing'):
            probe = gpu_fixture()
            if change == 'duplicate':
                probe['gpus'].append(probe['gpus'][0])
            elif change == 'unknown':
                probe['compute_processes'] = [{'gpu_uuid': 'GPU-absent', 'pid': 51, 'process_name': 'x'}]
            else:
                probe['gpus'] = probe['gpus'][1:]
            with self.assertRaises(episode.EpisodeOwnershipError):
                episode._normalize_gpu_probe(probe)

    def test_owner_bindings_are_recursively_immutable(self):
        values = episode._freeze({'stage': {'hashes': ['x']}})
        with self.assertRaises(TypeError):
            values['stage']['hashes'] = []
        self.assertEqual(values['stage']['hashes'], ('x',))

    def test_production_cli_is_closed(self):
        with self.assertRaisesRegex(episode.ResourceEpisodeError, 'production resource launch is unavailable'):
            episode.main(['--execute'])

    def test_fake_manifest_without_inherited_owner_is_not_authority(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'no inherited'):
                episode.ResourceEpisodeOwner.from_environment()

    def test_live_gpu_reader_uses_absolute_bounded_shell_free_queries(self):
        csv = b'0, GPU-fixture-0, NVIDIA H100, 81559, 0, 0\n1, GPU-fixture-1, NVIDIA H100, 81559, 0, 0\n2, GPU-fixture-2, NVIDIA H100, 81559, 0, 0\n'
        results = [SimpleNamespace(stdout=csv), SimpleNamespace(stdout=b''), SimpleNamespace(stdout=csv)]
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0)), patch.object(episode.subprocess, 'run', side_effect=results) as run:
            observed = episode.read_live_gpu_inventory()
        self.assertEqual(observed['gpus'][2]['index'], 2)
        self.assertEqual(run.call_count, 3)
        for args, kwargs in run.call_args_list:
            self.assertEqual(args[0][0], '/usr/bin/nvidia-smi')
            self.assertEqual(kwargs['timeout'], 5)
            self.assertNotIn('shell', kwargs)
            self.assertNotIn('CUDA_VISIBLE_DEVICES', kwargs['env'])

    def test_live_gpu_reader_rejects_inventory_change_between_reads(self):
        first = b'0, GPU-fixture-0, NVIDIA H100, 81559, 0, 0\n1, GPU-fixture-1, NVIDIA H100, 81559, 0, 0\n'
        last = first.replace(b'GPU-fixture-0', b'GPU-changed')
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0)), patch.object(episode.subprocess, 'run', side_effect=[SimpleNamespace(stdout=first), SimpleNamespace(stdout=b''), SimpleNamespace(stdout=last)]):
            with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'changed during live probe'):
                episode.read_live_gpu_inventory()

    def test_live_probe_allows_protected_activity_but_requires_both_selected_idle_samples(self):
        first = b'0, GPU-fixture-0, NVIDIA H100, 81559, 2000, 10\n1, GPU-fixture-1, NVIDIA H100, 81559, 0, 0\n2, GPU-fixture-2, NVIDIA H100, 81559, 17, 0\n'
        last = first.replace(b'2000, 10', b'3000, 20').replace(b'17, 0', b'0, 0')
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0)), patch.object(episode.subprocess, 'run', side_effect=[SimpleNamespace(stdout=first), SimpleNamespace(stdout=b''), SimpleNamespace(stdout=last)]):
            probe = episode.read_live_gpu_inventory()
        self.assertEqual(probe['gpus'][0]['memory_used_mib'], 3000)
        with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'idle memory'):
            episode._selected(probe, [2], set(), False)

    def test_unproven_lease_survives_descriptor_close(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            first = episode._LeaseSet(root / 'leases', 'a' * 32)
            first.acquire([gpu_fixture()['gpus'][2]])
            episode._check_lease(first.entries[0], 'a' * 32)
            first.close()
            self.assertTrue((root / 'leases/GPU-fixture-2.reservation.json').is_file())
            second = episode._LeaseSet(root / 'leases', 'b' * 32)
            try:
                with self.assertRaises(FileExistsError):
                    second.acquire([gpu_fixture()['gpus'][2]])
            finally:
                second.close()

    def test_inode_replacement_and_unlocked_lease_are_detected(self):
        import fcntl
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            leases = episode._LeaseSet(root / 'leases', 'a' * 32)
            leases.acquire([gpu_fixture()['gpus'][2]])
            try:
                item = leases.entries[0]
                fcntl.flock(item['fd'], fcntl.LOCK_UN)
                with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'no longer held'):
                    episode._check_lease(item, 'a' * 32)
                fcntl.flock(item['fd'], fcntl.LOCK_EX | fcntl.LOCK_NB)
                Path(item['path']).unlink()
                Path(item['path']).write_text('replacement')
                with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'inode/path changed'):
                    episode._check_lease(item, 'a' * 32)
            finally:
                leases.close()

    def test_same_inode_marker_rewrite_cannot_preserve_reservation_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            leases = episode._LeaseSet(root / 'leases', 'a' * 32)
            leases.acquire([gpu_fixture()['gpus'][2]])
            try:
                item = leases.entries[0]
                marker = Path(item['marker'])
                original_bytes = marker.read_bytes()
                for key, value in (('gpu_uuid', 'GPU-changed'), ('boot_id', '99999999-89ab-cdef-0123-456789abcdef'),
                                   ('resource_scope', 'production'), ('unexpected', True)):
                    altered = json.loads(original_bytes)
                    altered[key] = value
                    marker.write_text(json.dumps(altered))
                    self.assertEqual(marker.stat().st_ino, item['marker_inode'])
                    self.assertEqual(altered['acquisition_id'], 'a' * 32)
                    with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'reservation marker changed'):
                        episode._check_lease(item, 'a' * 32)
                    marker.write_bytes(original_bytes)
                    episode._check_lease(item, 'a' * 32)
            finally:
                leases.close()

    def test_release_deadline_failure_keeps_every_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            leases = episode._LeaseSet(root / 'leases', 'a' * 32)
            leases.acquire(gpu_fixture()['gpus'][2:])
            try:
                with patch.object(episode.time, 'monotonic', return_value=11):
                    with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'bounded recovery deadline'):
                        leases.release(10)
                self.assertEqual(len(list((root / 'leases').glob('*.reservation.json'))), 2)
                self.assertFalse(any(x.get('marker_released') for x in leases.entries))
            finally:
                leases.close()

    def test_source_closure_requires_all_three_exact_regular_sources(self):
        closure = episode._source_closure()
        self.assertEqual(set(closure), {'episode', 'process', 'audit'})
        episode._check_source_closure(closure)
        for name in closure:
            changed = json.loads(json.dumps(closure))
            changed[name]['sha256'] = '0' * 64
            with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'source closure changed'):
                episode._check_source_closure(changed)

    def test_delayed_restoration_evidence_publication_cannot_release_lease(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            controller = process.ProcessIdentity(BOOT, 90, os.getuid(), 100, 1, 90, 90)
            guard = process.ProcessIdentity(BOOT, os.getpid(), os.getuid(), 101, 90, os.getpid(), os.getpid())
            worker_identity = process.ProcessIdentity(BOOT, 91, os.getuid(), 102, guard.pid, 91, 91)
            kernel = FakeKernel(root / 'proc', [controller, guard, worker_identity])
            probe = gpu_fixture()
            probe_path = root / 'gpu.json'
            probe_path.write_text(json.dumps(probe))
            spec = {'controller': asdict(controller), 'baseline': baseline_for(probe), 'nonce': 'n' * 64,
                'source_closure': episode._source_closure(), 'lease_directory': str(root / 'leases'),
                'restoration_spec': restoration_spec(probe_path), 'gpu_probe_path': str(probe_path),
                'gpu_indices': [2], 'borrow_originals': False, 'original_fixture_nonce': None,
                'work_started_monotonic': 0, 'work_deadline_monotonic': 10, 'restoration_seconds': 2,
                'owner_binding': {}, 'argv': [sys.executable, '-c', 'pass']}
            declaration = root / 'declaration.json'
            declaration.write_text(json.dumps(spec))
            worker_fd = kernel.open_bound(worker_identity)
            tree = Mock(members={91: {'identity': worker_identity, 'fd': worker_fd}}, errors=[])
            tree.quiesce.return_value = {'status': 'owned_cpu_worker_tree_quiescence_proven'}
            worker = Mock(pid=91, returncode=0)
            worker.poll.return_value = 0
            auditor = episode._auditor()
            verification = {'status': 'same_process_resource_recovery_observed', 'failures': [],
                'queue_restore_proven': False, 'execution_available': False, 'resource_authority': False}
            now = [0.0]
            publish = process._exclusive_json
            def delayed_publish(path, value):
                publish(path, value)
                if Path(path).name == 'restoration-verification.json':
                    now[0] = 3.0
            read_fd, write_fd = os.pipe()
            try:
                with patch.object(process, '_require_linux'), patch.object(process, '_Kernel', return_value=kernel), patch.object(process, '_prctl'), patch.object(process, '_channel_state', side_effect=[b'S', None]), patch.object(process, '_OwnedTree', return_value=tree), patch.object(process, '_exclusive_json', side_effect=delayed_publish), patch.object(episode.subprocess, 'Popen', return_value=worker), patch.object(episode.time, 'monotonic', side_effect=lambda: now[0]), patch.object(auditor, 'observe_restore', return_value={'scope': 'mocked_CPU_deadline_fixture'}), patch.object(auditor, 'verify_restoration', return_value=verification), patch.object(episode.signal, 'signal'):
                    receipt = episode._watchdog(declaration, read_fd)
                self.assertFalse(receipt['reservations_released'])
                self.assertIn('bounded recovery deadline', receipt['restoration_error'])
                self.assertEqual(len(list((root / 'leases').glob('*.reservation.json'))), 1)
            finally:
                os.close(write_fd)
                os.close(worker_fd)

    def test_owner_deadline_race_preserves_causal_failure_classification(self):
        """Real owner/lease reads; process and independent audit are CPU mocks."""
        cases = [('owner_first_check', 'work_deadline'), ('owner_final_check', 'work_deadline'),
                 ('prelaunch_final_check', 'work_deadline'), ('reversed_clock', 'ownership_lost'),
                 ('nonfinite_clock', 'ownership_lost'), ('identity_loss_past_deadline', 'ownership_lost'),
                 ('controller_loss_after_guard_precheck', 'controller_lost'),
                 ('live_controller_identity_loss', 'ownership_lost')]
        for boundary, expected_reason in cases:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                controller = process.ProcessIdentity(BOOT, 90, os.getuid(), 100, 1, 90, 90)
                guard = process.ProcessIdentity(BOOT, os.getpid(), os.getuid(), 101, 90, os.getpid(), os.getpid())
                worker_identity = process.ProcessIdentity(BOOT, 91, os.getuid(), 102, guard.pid, 91, 91)
                kernel = FakeKernel(root / 'proc', [controller, guard, worker_identity])
                probe_path = root / 'gpu.json'
                probe_path.write_text(json.dumps(gpu_fixture()))
                spec = {'controller': asdict(controller), 'baseline': baseline_for(gpu_fixture()),
                    'nonce': 'n' * 64, 'source_closure': episode._source_closure(),
                    'lease_directory': str(root / 'leases'), 'restoration_spec': restoration_spec(probe_path),
                    'gpu_probe_path': str(probe_path), 'gpu_indices': [2], 'borrow_originals': False,
                    'original_fixture_nonce': None, 'work_started_monotonic': 0,
                    'work_deadline_monotonic': 10, 'restoration_seconds': 2,
                    'owner_binding': {}, 'argv': [sys.executable, '-c', 'pass']}
                declaration = root / 'declaration.json'
                declaration.write_text(json.dumps(spec))
                worker_fd = kernel.open_bound(worker_identity)
                tree = Mock(members={91: {'identity': worker_identity, 'fd': worker_fd}}, errors=[])
                tree.quiesce.return_value = {'status': 'owned_cpu_worker_tree_quiescence_proven'}
                worker = Mock(pid=91, returncode=0)
                worker.poll.return_value = None
                auditor = episode._auditor()
                verification = {'status': 'same_process_resource_recovery_observed', 'failures': [],
                    'queue_restore_proven': False, 'execution_available': False, 'resource_authority': False}
                now, clock_sequence, probes = [0.0], [], []
                raw_probe = episode._gpu_probe
                def clock_read():
                    if clock_sequence:
                        now[0] = clock_sequence.pop(0)
                    result = now[0]
                    if not math.isfinite(result) or result < 0:
                        now[0] = 0.0  # Recovery receives a valid clock in this classification fixture.
                    return result
                def discover():
                    if boundary == 'owner_first_check':
                        clock_sequence.extend([0.0, 10.0])  # Guard passes; owner's first check expires.
                    elif boundary == 'controller_loss_after_guard_precheck':
                        original_exited = kernel.exited
                        def exit_after_precheck(fd):
                            exited = original_exited(fd)
                            if kernel.fds[fd] == controller.pid:
                                kernel.exits.add(controller.pid)  # After the guard reads False, before owner checks.
                            return exited
                        kernel.exited = exit_after_precheck
                tree.discover.side_effect = discover
                def crossing_probe(path):
                    value = raw_probe(path)
                    probes.append(path)
                    target = 2 if boundary == 'prelaunch_final_check' else 3
                    if len(probes) == target and boundary != 'owner_first_check':
                        if boundary != 'live_controller_identity_loss':
                            now[0] = -0.1 if boundary == 'reversed_clock' else (
                                float('nan') if boundary == 'nonfinite_clock' else 10.0)
                        if boundary in ('identity_loss_past_deadline', 'live_controller_identity_loss'):
                            value['gpus'][0]['uuid'] = 'GPU-changed'
                    return value
                read_fd, write_fd = os.pipe()
                try:
                    with patch.object(process, '_require_linux'), patch.object(process, '_Kernel', return_value=kernel), patch.object(process, '_prctl'), patch.object(process, '_channel_state', side_effect=[b'S', None]), patch.object(process, '_OwnedTree', return_value=tree), patch.object(episode.subprocess, 'Popen', return_value=worker) as launch, patch.object(episode.time, 'monotonic', side_effect=clock_read), patch.object(episode, '_gpu_probe', side_effect=crossing_probe), patch.object(auditor, 'observe_restore', return_value={'scope': 'mocked_CPU_classification_fixture'}) as restore, patch.object(auditor, 'verify_restoration', return_value=verification), patch.object(episode.signal, 'signal'):
                        receipt = episode._watchdog(declaration, read_fd)
                    self.assertEqual(receipt['reason'], expected_reason, json.dumps(receipt))
                    self.assertEqual(receipt['status'], 'cpu_resource_episode_failed')
                    self.assertTrue(receipt['reservations_released'])
                    self.assertEqual(restore.call_count, 1)
                    if boundary == 'prelaunch_final_check':
                        launch.assert_not_called()
                    else:
                        self.assertEqual(tree.quiesce.call_count, 1)
                    if expected_reason in ('ownership_lost', 'controller_lost'):
                        self.assertIn('ownership_error', receipt)
                        self.assertNotIn('work_deadline_error', receipt)
                        self.assertEqual(controller.pid in kernel.exits, expected_reason == 'controller_lost')
                    else:
                        self.assertIn('work_deadline_error', receipt)
                        self.assertNotIn('ownership_error', receipt)
                finally:
                    os.close(write_fd)
                    os.close(worker_fd)

    def test_originals_refuse_foreign_ancestry_nonce_and_birth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            controller = process.ProcessIdentity(BOOT, 90, os.getuid(), 100, 1, 90, 90)
            valid = process.ProcessIdentity(BOOT, 91, os.getuid(), 101, 90, 91, 91)
            for item, nonce in ((controller, 'a' * 32), (replace(valid, ppid=1), 'a' * 32), (replace(valid, start_ticks=99), 'a' * 32), (valid, 'b' * 32)):
                kernel = FakeKernel(root, [controller, item])
                kernel.write(item, original=nonce)
                baseline = {'original_processes': [{'identity': asdict(item)}]}
                with self.assertRaises(episode.EpisodeOwnershipError):
                    episode._OriginalTree(kernel, controller, baseline, 'a' * 32)

    def test_originals_only_stop_cont_same_process_even_after_controller_loss(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            controller = process.ProcessIdentity(BOOT, 90, os.getuid(), 100, 1, 90, 90)
            original = process.ProcessIdentity(BOOT, 91, os.getuid(), 101, 90, 91, 91)
            kernel = FakeKernel(root, [controller, original])
            tree = episode._OriginalTree(kernel, controller, {'original_processes': [{'identity': asdict(original)}]}, 'a' * 32)
            try:
                tree.pause(time.monotonic() + 1)
                kernel.items.pop(controller.pid)
                kernel.items[91] = replace(original, ppid=1)
                self.assertEqual(tree.resume()['failures'], [])
                self.assertEqual(kernel.calls, [(91, signal.SIGSTOP), (91, signal.SIGCONT)])
                with self.assertRaises(episode.EpisodeOwnershipError):
                    tree._signal(tree.members[91], signal.SIGKILL)
            finally:
                tree.close()

    def test_owner_live_relationship_and_fresh_probe_are_rechecked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            controller = process.ProcessIdentity(BOOT, 90, os.getuid(), 100, 1, 90, 90)
            guard = process.ProcessIdentity(BOOT, 91, os.getuid(), 101, 90, 91, 91)
            subject = process.ProcessIdentity(BOOT, os.getpid(), os.getuid(), 102, 91, os.getpid(), os.getpid())
            kernel = FakeKernel(root / 'proc', [controller, guard, subject])
            probe = gpu_fixture()
            probe_path = root / 'gpu.json'
            probe_path.write_text(json.dumps(probe))
            leases = episode._LeaseSet(root / 'leases', 'a' * 32)
            leases.acquire([probe['gpus'][2]])
            manifest = {'guard': asdict(guard), 'controller': asdict(controller), 'nonce': 'n' * 64,
                'acquisition_id': 'a' * 32, 'leases': leases.entries, 'gpu_probe_path': str(probe_path),
                'protected_inventory': baseline_for(probe)['protected_gpu_inventory'],
                'original_processes': [], 'owner_binding': {'attempt_id': 'frontier-v8-' + '1' * 16}}
            started = time.monotonic()
            manifest.update(work_started_monotonic=started, work_deadline_monotonic=started + 30, restoration_seconds=2)
            manifest['source_closure'] = episode._source_closure()
            owner = episode.ResourceEpisodeOwner(manifest, kernel)
            try:
                self.assertIsNone(owner.assert_owned())
                with patch.object(episode.time, 'monotonic', return_value=started + 30), patch.object(episode, '_gpu_probe') as gpu_query, patch.object(kernel, 'identity') as proc_query:
                    with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'deadline has expired'):
                        owner.assert_owned()
                gpu_query.assert_not_called()
                proc_query.assert_not_called()
                with patch.object(episode.time, 'monotonic', side_effect=[started + 1, started + 30]):
                    with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'deadline has expired'):
                        owner.assert_owned()
                probe['gpus'][0]['uuid'] = 'GPU-changed'
                probe_path.write_text(json.dumps(probe))
                with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'GPU0/1 changed'):
                    owner.assert_owned()
                probe['gpus'][0]['uuid'] = 'GPU-fixture-0'
                probe_path.write_text(json.dumps(probe))
                kernel.exits.add(controller.pid)
                with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'no longer alive'):
                    owner.assert_owned()
            finally:
                owner.close()
                leases.close()


@unittest.skipUnless(LINUX, 'Linux pidfd and subreaper CPU fixture')
class ResourceEpisodeLinuxTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.probe = gpu_fixture()
        self.probe_path = self.root / 'gpu.json'
        self.probe_path.write_text(json.dumps(self.probe))
        self.baseline = baseline_for(self.probe, process.capture_identity(os.getpid()))
        self.children = []
        self.addCleanup(self._close_children)

    def _close_children(self):
        for child in self.children:
            if child.poll() is None:
                fd = os.pidfd_open(child.pid)
                try:
                    signal.pidfd_send_signal(fd, signal.SIGCONT)
                finally:
                    os.close(fd)
                child.terminate()
            child.wait(timeout=5)

    def run_episode(self, code, **updates):
        kwargs = {'episode_directory': self.root / 'episode', 'baseline': self.baseline,
            'restoration_spec': restoration_spec(self.probe_path), 'lease_directory': self.root / 'leases',
            'gpu_probe_path': self.probe_path, 'gpu_indices': [2], 'owner_binding': {'attempt_id': 'frontier-v8-' + '1' * 16},
            'timeout_seconds': 2, 'restoration_seconds': 2}
        kwargs.update(updates)
        return episode.run_cpu_resource_episode([sys.executable, '-c', code], **kwargs)

    def test_worker_receives_real_owner_and_success_releases_lease(self):
        code = "import sys;sys.path.insert(0," + repr(str(ROOT)) + ");from scripts.frontier_v8_resource_episode import ResourceEpisodeOwner;owner=ResourceEpisodeOwner.from_environment();owner.assert_owned();assert owner.bindings['resource_scope']=='linux_cpu_fixture_only';owner.close()"
        receipt = self.run_episode(code)
        self.assertEqual(receipt['status'], 'cpu_resource_episode_complete')
        self.assertTrue(receipt['reservations_released'])
        self.assertFalse(list((self.root / 'leases').glob('*.reservation.json')))

    def test_worker_failure_preserves_failure_and_restoration_evidence(self):
        with self.assertRaises(episode.ResourceEpisodeError) as failure:
            self.run_episode('raise RuntimeError("fixture failure")')
        self.assertEqual(failure.exception.receipt['reason'], 'worker_failed')
        self.assertTrue(failure.exception.receipt['reservations_released'])
        self.assertTrue((self.root / 'episode/restoration-observations.json').is_file())
        self.assertTrue((self.root / 'episode/worker.stderr.log').is_file())

    def test_escaped_new_descendant_is_cleaned_and_unrelated_fixture_survives(self):
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
        self.children.append(unrelated)
        child_path = self.root / 'new-child-pid.json'
        code = 'import json,subprocess,sys,time;from pathlib import Path;c=subprocess.Popen([sys.executable,"-c","import time;time.sleep(20)"],start_new_session=True);Path(' + repr(str(child_path)) + ').write_text(json.dumps(c.pid));time.sleep(.2);raise SystemExit(9)'
        with self.assertRaises(episode.ResourceEpisodeError) as failure:
            self.run_episode(code)
        child_pid = json.loads(child_path.read_text())
        members = failure.exception.receipt['quiescence']['members']
        self.assertIn(child_pid, [x['identity']['pid'] for x in members])
        self.assertTrue(all(x['pidfd_exit_observed'] for x in members))
        self.assertIsNone(unrelated.poll())

    def test_timeout_fails_closed_before_launch_or_proves_new_tree_quiescence(self):
        with self.assertRaises(episode.ResourceEpisodeError) as failure:
            self.run_episode('import time;time.sleep(10)', timeout_seconds=0.15)
        self.assertEqual(failure.exception.receipt['reason'], 'work_deadline')
        proof = failure.exception.receipt['quiescence']
        if proof['status'] == 'worker_not_started':
            # Controller startup consumes this same 0.15-second budget.
            self.assertEqual(proof, {'status': 'worker_not_started'})
            self.assertNotIn('worker', failure.exception.receipt)
            self.assertNotIn('worker_identity', failure.exception.receipt)
            for name in ('worker.stdout.log', 'worker.stderr.log'):
                self.assertFalse((self.root / 'episode' / name).exists())
        else:
            self.assertEqual(proof['status'], 'owned_cpu_worker_tree_quiescence_proven')
            self.assertTrue(proof['members'])
            self.assertTrue(all(x['pidfd_exit_observed'] for x in proof['members']))
        self.assertTrue(failure.exception.receipt['reservations_released'])

    def test_lost_gpu_identity_never_releases_reservation(self):
        code = 'import json,time;from pathlib import Path;p=Path(' + repr(str(self.probe_path)) + ");v=json.loads(p.read_text());v['gpus'][0]['uuid']='GPU-changed';p.write_text(json.dumps(v));time.sleep(10)"
        with self.assertRaises(episode.ResourceEpisodeError) as failure:
            self.run_episode(code, restoration_seconds=0.2,
                restoration_spec=restoration_spec(self.probe_path, 0.2))
        self.assertEqual(failure.exception.receipt['reason'], 'ownership_lost')
        self.assertFalse(failure.exception.receipt['reservations_released'])
        self.assertTrue(list((self.root / 'leases').glob('*.reservation.json')))

    def test_independent_spec_validation_happens_before_launch(self):
        with patch.object(episode.subprocess, 'Popen') as launch:
            with self.assertRaises(Exception):
                self.run_episode('pass', restoration_spec={'schema_version': 1})
        launch.assert_not_called()
        self.assertFalse((self.root / 'episode').exists())

    def test_controller_loss_guard_cleans_worker_and_writes_independent_receipt(self):
        config = {'root': str(self.root), 'probe': str(self.probe_path), 'baseline': self.baseline}
        config_path = self.root / 'controller-config.json'
        config_path.write_text(json.dumps(config))
        code = "import json,os,sys;from pathlib import Path;sys.path.insert(0," + repr(str(ROOT)) + ");from scripts import frontier_v8_resource_episode as e;c=json.loads(Path(sys.argv[1]).read_text());e.run_cpu_resource_episode([sys.executable,'-c','import time;time.sleep(20)'],episode_directory=Path(c['root'])/'episode',baseline=c['baseline'],restoration_spec=" + repr(restoration_spec(self.probe_path)) + ",lease_directory=Path(c['root'])/'leases',gpu_probe_path=c['probe'],gpu_indices=[2],owner_binding={},timeout_seconds=3,restoration_seconds=2)"
        controller = subprocess.Popen([sys.executable, '-c', code, str(config_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(controller)
        manifest = self.root / 'episode/owner-manifest.json'
        self.wait_for(manifest.is_file)
        guard_pid = json.loads(manifest.read_text())['guard']['pid']
        self.wait_for(lambda: bool(process._Kernel().children(guard_pid)))
        fd = os.pidfd_open(controller.pid)
        try:
            signal.pidfd_send_signal(fd, signal.SIGKILL)
        finally:
            os.close(fd)
        controller.wait(timeout=5)
        receipt_path = self.root / 'episode/watchdog-receipt.json'
        self.wait_for(receipt_path.is_file)
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt['reason'], 'controller_lost')
        self.assertTrue(receipt['reservations_released'])
        self.assertEqual(receipt['quiescence']['status'], 'owned_cpu_worker_tree_quiescence_proven')

    @staticmethod
    def wait_for(predicate, seconds=6):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        raise AssertionError('CPU fixture prerequisite did not appear')

    def _borrowed_originals(self):
        nonce = 'b' * 32
        immutable = self.root / 'immutable'
        immutable.mkdir()
        config = immutable / 'optimizer-fixture.json'
        config.write_text('{"fixture":true}\n')
        progress = self.root / 'progress.json'
        progress.write_text('{"step":0}')
        roles = [('rank', i) for i in range(4)] + [('coordinator', 0)] + [('service', i) for i in range(3)]
        ports = []
        environment = dict(os.environ)
        environment[episode.ORIGINAL_NONCE_KEY] = nonce
        originals = []
        for role, ordinal in roles:
            if role == 'service':
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    port = listener.getsockname()[1]
                ports.append(port)
                code = "from http.server import HTTPServer,BaseHTTPRequestHandler\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.end_headers();self.wfile.write(b'fixture')\n def log_message(self,*args):pass\nHTTPServer(('127.0.0.1'," + str(port) + "),H).serve_forever()"
            elif role == 'rank' and ordinal == 0:
                code = "import json,time;from pathlib import Path;p=Path(" + repr(str(progress)) + ")\ni=0\nwhile True:\n i+=1;t=p.with_suffix('.writing');t.write_text(json.dumps({'step':i}));t.replace(p);time.sleep(.04)"
            else:
                code = 'import time;time.sleep(60)'
            child = subprocess.Popen([sys.executable, '-c', code], env=environment,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            self.children.append(child)
            self.wait_for(lambda: Path('/proc', str(child.pid), 'cmdline').read_bytes().startswith(sys.executable.encode()))
            current = process.capture_identity(child.pid)
            originals.append({'role': role, 'ordinal': ordinal, 'identity': asdict(current),
                'cmdline_sha256': hashlib.sha256(Path('/proc', str(child.pid), 'cmdline').read_bytes()).hexdigest()})
        for port in ports:
            def healthy():
                try:
                    with urlopen('http://127.0.0.1:' + str(port), timeout=.1) as response:
                        return response.status == 200
                except OSError:
                    return False
            self.wait_for(healthy)
        self.baseline.update(mode='borrowed_same_process', immutable_roots=[str(immutable)],
            immutable_files=[{'path': str(config), 'size': config.stat().st_size,
                              'sha256': hashlib.sha256(config.read_bytes()).hexdigest()}], original_processes=originals,
            services=[{'url': 'http://127.0.0.1:' + str(port), 'process_pid': row['identity']['pid'], 'expected_status': 200}
                      for port, row in zip(ports, originals[-3:])],
            progress=[{'path': str(progress), 'extractor': 'json_integer', 'key_path': ['step'],
                       'before_value': json.loads(progress.read_text())['step']}])
        self.probe['compute_processes'] = [{'gpu_uuid': 'GPU-fixture-' + str(index),
            'pid': originals[0]['identity']['pid'], 'process_name': 'python'} for index in (2, 3)]
        self.probe_path.write_text(json.dumps(self.probe))
        return nonce

    def test_borrowed_originals_resume_same_birth_and_progress_without_restart(self):
        nonce = self._borrowed_originals()
        receipt = self.run_episode('import time;time.sleep(.15)', gpu_indices=[2, 3],
            borrow_originals=True, original_fixture_nonce=nonce)
        self.assertTrue(receipt['reservations_released'])
        self.assertEqual(len(receipt['original_resume']['members']), 8)
        for row in self.baseline['original_processes']:
            current = asdict(process.capture_identity(row['identity']['pid']))
            self.assertEqual(current, row['identity'])
        for row in receipt['original_resume']['members']:
            self.assertIn(signal.SIGSTOP, row['signals'])
            self.assertEqual(row['signals'][-1], signal.SIGCONT)
            self.assertNotIn(signal.SIGKILL, row['signals'])

    def test_borrowed_original_nonce_mismatch_is_refused_before_launch(self):
        self._borrowed_originals()
        with patch.object(episode.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'nonce'):
                self.run_episode('pass', gpu_indices=[2, 3], borrow_originals=True, original_fixture_nonce='c' * 32)
        launch.assert_not_called()
        self.assertFalse((self.root / 'episode').exists())

    def test_borrowed_timeout_resumes_all_originals(self):
        nonce = self._borrowed_originals()
        with self.assertRaises(episode.ResourceEpisodeError) as failure:
            self.run_episode('import time;time.sleep(20)', timeout_seconds=.5,
                gpu_indices=[2, 3], borrow_originals=True, original_fixture_nonce=nonce)
        self.assertEqual(failure.exception.receipt['reason'], 'work_deadline')
        self.assert_originals_resumed(failure.exception.receipt, released=True)

    def test_borrowed_failed_gate_nonzero_resumes_all_originals(self):
        nonce = self._borrowed_originals()
        with self.assertRaises(episode.ResourceEpisodeError) as failure:
            self.run_episode('raise SystemExit(73)', gpu_indices=[2, 3],
                borrow_originals=True, original_fixture_nonce=nonce)
        self.assertEqual(failure.exception.receipt['reason'], 'worker_failed')
        self.assertEqual(failure.exception.receipt['quiescence']['worker_returncode'], 73)
        self.assert_originals_resumed(failure.exception.receipt, released=True)

    def test_borrowed_ownership_loss_resumes_but_keeps_unproven_lease(self):
        nonce = self._borrowed_originals()
        code = 'import json,time;from pathlib import Path;p=Path(' + repr(str(self.probe_path)) + ");v=json.loads(p.read_text());v['gpus'][0]['uuid']='GPU-changed';p.write_text(json.dumps(v));time.sleep(20)"
        with self.assertRaises(episode.ResourceEpisodeError) as failure:
            self.run_episode(code, gpu_indices=[2, 3], borrow_originals=True,
                original_fixture_nonce=nonce, restoration_seconds=.3,
                restoration_spec=restoration_spec(self.probe_path, .3))
        self.assertEqual(failure.exception.receipt['reason'], 'ownership_lost')
        self.assert_originals_resumed(failure.exception.receipt, released=False)

    def test_borrowed_hash_failure_keeps_reservations_after_resume(self):
        nonce = self._borrowed_originals()
        config = self.baseline['immutable_files'][0]['path']
        code = 'from pathlib import Path;Path(' + repr(config) + ").write_text('changed')"
        with self.assertRaises(episode.ResourceEpisodeError) as failure:
            self.run_episode(code, gpu_indices=[2, 3], borrow_originals=True,
                original_fixture_nonce=nonce, restoration_seconds=.3,
                restoration_spec=restoration_spec(self.probe_path, .3))
        self.assert_originals_resumed(failure.exception.receipt, released=False)
        self.assertEqual(failure.exception.receipt['restoration_verification']['status'], 'resource_recovery_observation_failed')

    def test_borrowed_controller_sigkill_restores_same_process_tree(self):
        receipt = self._borrowed_controller_signal(signal.SIGKILL)
        self.assertEqual(receipt['reason'], 'controller_lost')
        self.assertTrue(receipt['reservations_released'])

    def test_borrowed_catchable_interrupt_restores_same_process_tree(self):
        receipt = self._borrowed_controller_signal(signal.SIGTERM)
        self.assertEqual(receipt['reason'], 'controller_channel_closed_or_invalid')
        self.assertTrue(receipt['reservations_released'])

    def assert_originals_resumed(self, receipt, *, released):
        self.assertEqual(receipt['reservations_released'], released)
        self.assertEqual(len(receipt['original_resume']['members']), 8)
        self.assertEqual(receipt['original_resume']['failures'], [])
        for member in receipt['original_resume']['members']:
            expected = process.ProcessIdentity(**member['identity'])
            current = process.capture_identity(expected.pid)
            self.assertTrue(process._same_process(current, expected))
            raw = Path('/proc', str(current.pid), 'stat').read_text()
            self.assertNotIn(raw[raw.rfind(')') + 1:].split()[0], ('T', 't', 'Z', 'X', 'x'))
            self.assertIn(signal.SIGSTOP, member['signals'])
            self.assertEqual(member['signals'][-1], signal.SIGCONT)
            self.assertTrue(all(x in (signal.SIGSTOP, signal.SIGCONT) for x in member['signals']))

    def _borrowed_controller_signal(self, signum):
        configuration = self.root / 'borrowed-controller-config.json'
        configuration.write_text(json.dumps({'root': str(self.root), 'baseline': self.baseline}))
        code = "import json,sys;from pathlib import Path;sys.path.insert(0," + repr(str(ROOT)) + ");from tests.test_frontier_v8_resource_episode import ResourceEpisodeLinuxTests,gpu_fixture;c=json.loads(Path(sys.argv[1]).read_text());f=ResourceEpisodeLinuxTests();f.root=Path(c['root']);f.baseline=c['baseline'];f.probe=gpu_fixture();f.probe_path=f.root/'gpu.json';f.children=[];nonce=f._borrowed_originals();f.run_episode('import time;time.sleep(20)',gpu_indices=[2,3],borrow_originals=True,original_fixture_nonce=nonce,timeout_seconds=4)"
        controller = subprocess.Popen([sys.executable, '-c', code, str(configuration)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.children.append(controller)
        manifest_path = self.root / 'episode/owner-manifest.json'
        self.wait_for(manifest_path.is_file)
        manifest = json.loads(manifest_path.read_text())
        self.wait_for(lambda: bool(process._Kernel().children(manifest['guard']['pid'])))
        # Retain exact pidfds before intentionally losing the fixture controller.
        original_fds = [(process.ProcessIdentity(**row['identity']), process._Kernel().open_bound(
            process.ProcessIdentity(**row['identity']))) for row in manifest['original_processes']]
        controller_fd = os.pidfd_open(controller.pid)
        try:
            signal.pidfd_send_signal(controller_fd, signum)
            receipt_path = self.root / 'episode/watchdog-receipt.json'
            self.wait_for(receipt_path.is_file)
            receipt = json.loads(receipt_path.read_text())
            self.assert_originals_resumed(receipt, released=True)
            return receipt
        finally:
            os.close(controller_fd)
            # Teardown of our synthetic fixture, outside episode restoration.
            for identity, fd in original_fds:
                if not process._Kernel().exited(fd):
                    signal.pidfd_send_signal(fd, signal.SIGCONT)
                    signal.pidfd_send_signal(fd, signal.SIGTERM)
                os.close(fd)
            controller.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
