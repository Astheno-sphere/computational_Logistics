"""Check-only preallocation fixtures; no live GPU or model calls."""
from dataclasses import asdict, replace
import fcntl
import hashlib
import importlib._bootstrap_external
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from scripts import frontier_v8_live_host as host
from scripts import frontier_v8_owned_process as process
from scripts import frontier_v8_resource_episode as episode
from tests.test_frontier_v8_resource_episode import BOOT, FakeKernel, gpu_fixture


ROOT = Path(__file__).resolve().parents[1]
LINUX = sys.platform == 'linux' and hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal')
AUTHORITY = ('physical_exclusion_proven', 'live_resource_lease_issued',
             'model_execution_authority', 'execution_available', 'complete_resource_episode_proven')


def source_fixture(root, operational_root=ROOT):
    """Synthetic source verifier only; it proves no Git or native import closure."""
    for role in ('scientific', 'native'):
        (root / role).mkdir()
    files = ['scripts/frontier_v8_live_host.py', 'scripts/frontier_v8_owned_process.py',
             'scripts/frontier_v8_resource_episode.py']
    receipt = {'schema_version': 1, 'status': 'three_clean_sources_verified_CPU_only',
        'context': {'fixture_receipt': str(root / 'sources.json')},
        'scientific': {'root': str(root / 'scientific'), 'commit': '1' * 40, 'files_sha256': {}},
        'native': {'root': str(root / 'native'), 'commit': '2' * 40, 'files_sha256': {}},
        'operational': {'root': str(operational_root), 'commit': '3' * 40,
            'files_sha256': {name: hashlib.sha256((operational_root / name).read_bytes()).hexdigest()
                             for name in files}},
        'external_files_sha256': {}, 'scope': 'three_source_CPU_verification_only',
        'execution_available': False, 'resource_authority': False,
        'model_execution_authority': False, 'model_calls': 0}
    (root / 'sources.json').write_text(json.dumps(receipt))
    return receipt


def stage_fixture(root, attempt_id, scientific_commit):
    stage = {'schema_version': 1, 'status': 'cpu_staged_no_cuda_initialization',
             'cuda_initialized': False, 'attempt_id': attempt_id, 'source_commit': scientific_commit}
    path = root / 'stage.json'
    path.write_text(json.dumps(stage))
    return {'stage_path': str(path), 'stage_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class LiveHostUnitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.guard = process.ProcessIdentity(BOOT, os.getpid(), os.getuid(), 20,
                                            os.getpid() + 1, os.getpid(), os.getpid())
        self.controller = process.ProcessIdentity(BOOT, self.guard.ppid, os.getuid(), 10,
                                                 1, self.guard.ppid, self.guard.ppid)
        self.kernel = FakeKernel(self.root / 'proc', [self.controller, self.guard])
        self.kernel.write(self.guard, nonce='a' * 64)
        self.probe, self.probe_path = gpu_fixture(), self.root / 'gpu.json'
        self.write_probe()
        self.host_path = self.root / 'host.json'
        self.host_path.write_text(json.dumps({'hostname': 'fixture-host',
                                            'local_ipv4s': [host.NODES['ms-n1-1']]}))
        self.source = source_fixture(self.root)
        now = time.monotonic()
        self.spec = {'schema_version': 1, 'mode': 'no_borrow',
            'attempt_id': 'frontier-v8-' + '1' * 16, 'acquisition_id': 'a' * 32,
            'node_alias': 'ms-n1-1', 'expected_hostname': 'fixture-host',
            'gpu_uuid': 'GPU-fixture-2', 'controller': asdict(self.controller),
            'guard': asdict(self.guard), 'nonce': 'a' * 64,
            'work_started_monotonic': now, 'work_deadline_monotonic': now + 30,
            'restoration_seconds': 2, 'lease_directory': str(self.root / 'leases'),
            'source_binding': {'receipt_path': str(self.root / 'sources.json'),
                               'receipt_canonical_sha256': host._canonical(self.source)}}
        self.spec['stage_binding'] = stage_fixture(self.root, self.spec['attempt_id'],
                                                   self.source['scientific']['commit'])
        self.verifier = Mock(side_effect=lambda context: json.loads(json.dumps(self.source)))

    def write_probe(self):
        self.probe_path.write_text(json.dumps(self.probe))

    def bind(self, spec=None):
        owner = host.bind_cpu_fixture_preallocation(self.spec if spec is None else spec,
            gpu_fixture_path=self.probe_path, host_fixture_path=self.host_path,
            source_verifier=self.verifier, kernel=self.kernel)
        self.addCleanup(owner.close)
        return owner

    def test_positive_fixture_is_immutable_check_only_and_cannot_be_promoted(self):
        owner = self.bind()
        self.assertIsNone(owner.assert_owned())
        self.assertEqual(owner.bindings['scope'], host.CPU_SCOPE)
        self.assertTrue(owner.bindings['injected_GPU'])
        self.assertTrue(owner.bindings['source_verifier_injected'])
        self.assertFalse(owner.bindings['linux_pidfd_evidence'])
        for key in AUTHORITY:
            self.assertIs(owner.bindings[key], False)
        with self.assertRaises(TypeError):
            owner.bindings['module_origins']['process']['source_role'] = 'native'
        self.assertEqual(owner.bindings['module_origins']['process']['source_role'], 'operational')
        self.assertIn('marker_bytes_only', owner.bindings['stage_scope'])
        with self.assertRaisesRegex(host.LiveHostError, 'model authority unavailable'):
            owner.require_model_authority()
        with patch.object(process, '_require_linux'):
            with self.assertRaisesRegex(host.LiveHostError, 'strict no-borrow'):
                host.bind_guard_preallocation(owner)
        with self.assertRaisesRegex(host.LiveHostError, 'strict no-borrow'):
            self.bind(episode.ResourceEpisodeOwner.__new__(episode.ResourceEpisodeOwner))

    def test_production_cli_and_unissued_owner_remain_closed(self):
        with self.assertRaisesRegex(host.LiveHostError, 'production execution unavailable'):
            host.main(['--execute'])
        with self.assertRaisesRegex(host.LiveHostError, 'issued by the guard'):
            host.NoBorrowPreallocationOwner(None, None, None, None, None, host.LIVE_SCOPE, None)
        with self.assertRaises(TypeError):
            host.bind_guard_preallocation(self.spec, kernel=self.kernel)
        with self.assertRaisesRegex(host.LiveHostError, 'explicit CPU fixture'):
            host.bind_cpu_fixture_preallocation(self.spec, gpu_fixture_path=self.probe_path,
                host_fixture_path=self.host_path, source_verifier=None, kernel=self.kernel)

    def test_strict_spec_rejects_borrowed_routes_and_unbounded_or_untyped_values(self):
        changes = ({'mode': 'borrowed_same_process'}, {'node_alias': 'ms-n1-2'},
            {'schema_version': True}, {'attempt_id': 'reused'}, {'acquisition_id': 'A' * 32},
            {'nonce': 'n' * 64}, {'work_deadline_monotonic': self.spec['work_started_monotonic'] + 4501},
            {'work_deadline_monotonic': float('inf')}, {'work_started_monotonic': float('nan')},
            {'restoration_seconds': 1501}, {'restoration_seconds': True}, {'unexpected': True})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(host.LiveHostError):
                self.bind({**self.spec, **change})
        bounded = {**self.spec, 'work_deadline_monotonic': self.spec['work_started_monotonic'] + 4500,
                   'restoration_seconds': 1500}
        self.assertEqual(host._spec(bounded)['restoration_seconds'], 1500)

    def test_alias_ip_and_hostname_are_checked_before_gpu_or_lease(self):
        for observation in ({'hostname': 'other', 'local_ipv4s': [host.NODES['ms-n1-1']]},
                            {'hostname': 'fixture-host', 'local_ipv4s': ['127.0.0.1']}):
            self.host_path.write_text(json.dumps(observation))
            with self.subTest(observation=observation), patch.object(episode, '_gpu_probe') as query:
                with self.assertRaisesRegex(host.LiveHostError, 'alias/IP/hostname'):
                    self.bind()
                query.assert_not_called()
            self.assertFalse((self.root / 'leases').exists())

    def test_real_host_reader_uses_hostname_and_only_local_fib_addresses(self):
        root = self.root / 'host-proc'
        (root / 'net').mkdir(parents=True)
        (root / 'sys/kernel').mkdir(parents=True)
        (root / 'sys/kernel/hostname').write_text('fixture-host\n')
        (root / 'net/fib_trie').write_text(' |-- 100.64.180.123\n  /32 host LOCAL\n'
                                         ' |-- 192.0.2.1\n  /24 link UNICAST\n')
        self.assertEqual(host._host(root), {'hostname': 'fixture-host',
                                          'local_ipv4s': ['100.64.180.123']})

    def test_protected_unknown_non_h100_and_occupied_selected_gpus_are_refused(self):
        for selected in ('GPU-fixture-0', 'GPU-fixture-1', 'GPU-absent'):
            with self.subTest(selected=selected), self.assertRaisesRegex(host.LiveHostError, 'physical H100'):
                self.bind({**self.spec, 'gpu_uuid': selected})
        self.probe['gpus'][2]['name'] = 'NVIDIA A100'
        self.write_probe()
        with self.assertRaisesRegex(host.LiveHostError, 'physical H100'):
            self.bind()
        self.probe['gpus'][2]['name'] = 'NVIDIA H100'
        self.probe['compute_processes'] = [{'gpu_uuid': 'GPU-fixture-2', 'pid': self.guard.pid,
                                          'process_name': 'foreign'}]
        self.write_probe()
        with self.assertRaisesRegex(host.LiveHostError, 'occupied'):
            self.bind()
        self.assertFalse((self.root / 'leases').exists())

    def test_selected_gpu_requires_idle_memory_and_utilization_measurements(self):
        for changes in ({'memory_used_mib': 17}, {'utilization_percent': 1}, {'memory_used_mib': None}):
            self.probe = gpu_fixture()
            if changes.get('memory_used_mib', 0) is None:
                del self.probe['gpus'][2]['memory_used_mib']
                del self.probe['gpus'][2]['utilization_percent']
            else:
                self.probe['gpus'][2].update(changes)
            self.write_probe()
            with self.subTest(changes=changes), self.assertRaisesRegex(episode.EpisodeOwnershipError, 'idle memory'):
                self.bind()

    def test_selected_and_protected_uuid_mutation_invalidates_existing_owner(self):
        owner = self.bind()
        for index in (2, 0, 1):
            self.probe['gpus'][index]['uuid'] = 'GPU-changed'
            self.write_probe()
            with self.subTest(index=index), self.assertRaises((host.LiveHostError, episode.EpisodeOwnershipError)):
                owner.assert_owned()
            self.probe = gpu_fixture()
            self.write_probe()
            owner.assert_owned()

    def test_host_loss_and_new_selected_compute_invalidate_existing_owner(self):
        owner = self.bind()
        self.host_path.write_text(json.dumps({'hostname': 'changed',
                                             'local_ipv4s': [host.NODES['ms-n1-1']]}))
        with self.assertRaisesRegex(host.LiveHostError, 'alias/IP/hostname'):
            owner.assert_owned()
        self.host_path.write_text(json.dumps({'hostname': 'fixture-host',
                                             'local_ipv4s': [host.NODES['ms-n1-1']]}))
        self.probe['compute_processes'] = [{'gpu_uuid': 'GPU-fixture-2', 'pid': self.guard.pid,
                                          'process_name': 'new unrelated compute'}]
        self.write_probe()
        with self.assertRaisesRegex(host.LiveHostError, 'occupied'):
            owner.assert_owned()

    def test_protected_compute_birth_and_command_bytes_are_bound(self):
        foreign = replace(self.guard, pid=self.guard.pid + 2, ppid=1,
                          pgrp=self.guard.pid + 2, session=self.guard.pid + 2)
        self.kernel.items[foreign.pid] = foreign
        self.kernel.write(foreign)
        self.probe['compute_processes'] = [{'gpu_uuid': 'GPU-fixture-0', 'pid': foreign.pid,
                                          'process_name': 'protected'}]
        self.write_probe()
        owner = self.bind()
        self.kernel.items[foreign.pid] = replace(foreign, start_ticks=foreign.start_ticks + 1)
        with self.assertRaisesRegex(host.LiveHostError, 'protected GPU'):
            owner.assert_owned()
        self.kernel.items[foreign.pid] = foreign
        (self.kernel.proc_root / str(foreign.pid) / 'cmdline').write_bytes(b'changed\0')
        with self.assertRaisesRegex(host.LiveHostError, 'protected GPU'):
            owner.assert_owned()

    def test_current_guard_identity_nonce_and_direct_fresh_session_are_required(self):
        for changes in ({'start_ticks': 21}, {'uid': self.guard.uid + 1},
                        {'boot_id': '99999999-89ab-cdef-0123-456789abcdef'},
                        {'ppid': 1}, {'pgrp': self.controller.pid}, {'session': self.controller.pid}):
            self.kernel.items[self.guard.pid] = replace(self.guard, **changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(host.LiveHostError, 'guard child'):
                self.bind()
        self.kernel.items[self.guard.pid] = self.guard
        self.kernel.write(self.guard, nonce='b' * 64)
        with self.assertRaisesRegex(host.LiveHostError, 'guard child'):
            self.bind()
        self.assertFalse((self.root / 'leases').exists())

    def test_controller_birth_uid_boot_or_bound_exit_invalidates_owner(self):
        owner = self.bind()
        for changes in ({'start_ticks': 11}, {'uid': self.controller.uid + 1},
                        {'boot_id': '99999999-89ab-cdef-0123-456789abcdef'}):
            self.kernel.items[self.controller.pid] = replace(self.controller, **changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(host.LiveHostError, 'guard child'):
                owner.assert_owned()
        self.kernel.items[self.controller.pid] = self.controller
        for pid in (self.controller.pid, self.guard.pid):
            self.kernel.exits.add(pid)
            with self.subTest(pid=pid), self.assertRaisesRegex(host.LiveHostError, 'pidfd has exited'):
                owner.assert_owned()
            self.kernel.exits.remove(pid)

    def test_bound_guard_nonce_birth_and_ancestry_are_rechecked(self):
        owner = self.bind()
        for changes in ({'start_ticks': self.guard.start_ticks + 1}, {'ppid': 1},
                        {'session': self.controller.pid}):
            self.kernel.items[self.guard.pid] = replace(self.guard, **changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(host.LiveHostError, 'guard child'):
                owner.assert_owned()
        self.kernel.items[self.guard.pid] = self.guard
        self.kernel.write(self.guard, nonce='b' * 64)
        with self.assertRaisesRegex(host.LiveHostError, 'guard child'):
            owner.assert_owned()

    def test_acquisition_race_fails_after_pidfds_without_issuing_authority(self):
        original = self.kernel.open_bound
        def racing(item):
            fd = original(item)
            if item.pid == self.guard.pid:
                self.kernel.items[item.pid] = replace(item, start_ticks=item.start_ticks + 1)
            return fd
        with patch.object(self.kernel, 'open_bound', side_effect=racing):
            with self.assertRaisesRegex(host.LiveHostError, 'guard child'):
                self.bind()
        self.assertTrue((self.root / 'leases/GPU-fixture-2.reservation.json').is_file())
        for fd in self.kernel.fds:
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_private_lease_flock_inode_and_exact_marker_bytes_are_required(self):
        owner = self.bind()
        item = owner._entry
        fcntl.flock(item['fd'], fcntl.LOCK_UN)
        with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'no longer held'):
            owner.assert_owned()
        fcntl.flock(item['fd'], fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = Path(item['marker'])
        saved = marker.read_bytes()
        altered = json.loads(saved)
        altered['physical_exclusion_proven'] = True
        marker.write_text(json.dumps(altered))
        self.assertEqual(marker.stat().st_ino, item['marker_inode'])
        with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'reservation marker changed'):
            owner.assert_owned()
        marker.write_bytes(saved)
        Path(item['path']).unlink()
        Path(item['path']).write_text('replacement')
        with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'inode/path changed'):
            owner.assert_owned()

    def test_closed_descriptor_is_detected_and_close_preserves_reservation(self):
        owner = self.bind()
        item = owner._entry
        # Keep the owner fd number valid while replacing the underlying inode.
        replacement = os.open('/dev/null', os.O_RDONLY)
        try:
            os.dup2(replacement, item['fd'])
        finally:
            os.close(replacement)
        with self.assertRaisesRegex(episode.EpisodeOwnershipError, 'inode/path changed'):
            owner.assert_owned()
        marker = Path(item['marker'])
        owner.close()
        self.assertTrue(marker.is_file())
        with self.assertRaisesRegex(host.LiveHostError, 'closed'):
            owner.assert_owned()
        with self.assertRaises(FileExistsError):
            self.bind()

    def test_public_lease_permissions_are_refused_before_marker(self):
        directory = self.root / 'leases'
        directory.mkdir(mode=0o755)
        directory.chmod(0o755)
        with self.assertRaisesRegex(host.LiveHostError, 'private UID-owned'):
            self.bind()
        self.assertFalse(list(directory.glob('*.reservation.json')))

    def test_source_receipt_dependency_and_stage_mutations_are_refused(self):
        owner = self.bind()
        source_path = self.root / 'sources.json'
        source_path.write_text(json.dumps({**self.source, 'model_execution_authority': True}))
        with self.assertRaisesRegex(host.LiveHostError, 'source receipt digest'):
            owner.assert_owned()
        source_path.write_text(json.dumps(self.source))
        original = self.source['operational']['files_sha256']['scripts/frontier_v8_live_host.py']
        self.source['operational']['files_sha256']['scripts/frontier_v8_live_host.py'] = '0' * 64
        with self.assertRaisesRegex(host.LiveHostError, 'fresh three-source'):
            owner.assert_owned()
        self.source['operational']['files_sha256']['scripts/frontier_v8_live_host.py'] = original
        stage_path = Path(self.spec['stage_binding']['stage_path'])
        stage_path.write_bytes(stage_path.read_bytes() + b'\n')
        with self.assertRaisesRegex(host.LiveHostError, 'stage marker bytes changed'):
            owner.assert_owned()

    def test_wrong_stage_attempt_source_and_cuda_flag_are_refused_even_when_rehashed(self):
        stage_path = Path(self.spec['stage_binding']['stage_path'])
        saved = json.loads(stage_path.read_bytes())
        for changes in ({'attempt_id': 'frontier-v8-' + '2' * 16}, {'source_commit': 'f' * 40},
                        {'cuda_initialized': True}, {'schema_version': True}):
            stage_path.write_text(json.dumps({**saved, **changes}))
            binding = {'stage_path': str(stage_path), 'stage_sha256': hashlib.sha256(stage_path.read_bytes()).hexdigest()}
            with self.subTest(changes=changes), self.assertRaisesRegex(host.LiveHostError, 'stage marker attempt/source'):
                self.bind({**self.spec, 'stage_binding': binding})

    def test_source_hash_mismatch_and_source_overlapping_lease_fail_before_reservation(self):
        self.source['operational']['files_sha256']['scripts/frontier_v8_owned_process.py'] = '0' * 64
        (self.root / 'sources.json').write_text(json.dumps(self.source))
        binding = {**self.spec['source_binding'], 'receipt_canonical_sha256': host._canonical(self.source)}
        with self.assertRaisesRegex(host.LiveHostError, 'dependency source hash'):
            self.bind({**self.spec, 'source_binding': binding})
        self.source['operational']['files_sha256']['scripts/frontier_v8_owned_process.py'] = hashlib.sha256(Path(process.__file__).read_bytes()).hexdigest()
        (self.root / 'sources.json').write_text(json.dumps(self.source))
        binding['receipt_canonical_sha256'] = host._canonical(self.source)
        with self.assertRaisesRegex(host.LiveHostError, 'overlaps a source'):
            self.bind({**self.spec, 'source_binding': binding,
                       'lease_directory': str(self.root / 'native/leases')})

    def test_deadline_precedes_process_gpu_reads_and_delayed_probe_is_rechecked(self):
        expired = self.spec['work_deadline_monotonic']
        with patch.object(host.time, 'monotonic', return_value=expired), patch.object(self.kernel, 'identity') as identity, patch.object(episode, '_gpu_probe') as query:
            with self.assertRaises(host.PreallocationDeadlineExceeded):
                self.bind()
            identity.assert_not_called()
            query.assert_not_called()
        clock = [self.spec['work_started_monotonic']]
        def delayed(path):
            clock[0] = expired
            return episode._normalize_gpu_probe(self.probe)
        with patch.object(host.time, 'monotonic', side_effect=lambda: clock[0]), patch.object(episode, '_gpu_probe', side_effect=delayed):
            with self.assertRaises(host.PreallocationDeadlineExceeded):
                self.bind()
        self.assertFalse((self.root / 'leases').exists())

    def test_owned_deadline_expiry_stops_before_fresh_probe_and_clock_errors_stay_distinct(self):
        owner = self.bind()
        with patch.object(host.time, 'monotonic', return_value=self.spec['work_deadline_monotonic']), patch.object(owner, '_query') as query:
            with self.assertRaises(host.PreallocationDeadlineExceeded):
                owner.assert_owned()
            query.assert_not_called()
        for invalid in (self.spec['work_started_monotonic'] - 1, float('nan'), float('inf')):
            with self.subTest(invalid=invalid), patch.object(host.time, 'monotonic', return_value=invalid):
                with self.assertRaises(host.LiveHostError) as failure:
                    owner.assert_owned()
                self.assertNotIsInstance(failure.exception, host.PreallocationDeadlineExceeded)

    def test_bound_loader_source_executes_instead_of_forged_timestamp_pyc(self):
        # Explicit trusted-interpreter metadata injection stays inside this CPU fixture.
        operational = self.root / 'operational'
        (operational / 'scripts').mkdir(parents=True)
        copies = {}
        for module in (host, process, episode):
            copied = operational / 'scripts' / Path(module.__file__).name
            copied.write_bytes(Path(module.__file__).read_bytes())
            copies[module] = copied
        loader = operational / 'scripts/frontier_v8_source_loader.py'
        good, evil = self.root / 'source-executed', self.root / 'pyc-executed'
        loader.write_text('import json\nfrom pathlib import Path\n'
            + 'Path(' + repr(str(good)) + ').write_text("verified source")\n'
            + 'def verify_three_sources(context):\n'
            + '    return json.loads(Path(context["fixture_receipt"]).read_bytes())\n')
        self.source['operational']['root'] = str(operational)
        self.source['operational']['files_sha256']['scripts/frontier_v8_source_loader.py'] = hashlib.sha256(loader.read_bytes()).hexdigest()
        (self.root / 'sources.json').write_text(json.dumps(self.source))
        binding = {**self.spec['source_binding'], 'receipt_canonical_sha256': host._canonical(self.source)}
        forged_code = compile('from pathlib import Path\nPath(' + repr(str(evil)) + ').write_text("forged pyc")\n', str(loader), 'exec')
        st = loader.stat()
        cached = Path(importlib.util.cache_from_source(str(loader)))
        cached.parent.mkdir()
        cached.write_bytes(importlib._bootstrap_external._code_to_timestamp_pyc(
            forged_code, int(st.st_mtime), st.st_size))
        # Prove the fixture really is an accepted cache, then remove its effect.
        spec = importlib.util.spec_from_file_location('_forged_cache_fixture', loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(evil.is_file())
        evil.unlink()
        with patch.object(host, '__file__', str(copies[host])), patch.object(process, '__file__', str(copies[process])), patch.object(episode, '__file__', str(copies[episode])):
            current, origins, fingerprint = host._verify_sources(binding)
        self.assertTrue(good.is_file())
        self.assertFalse(evil.exists())
        self.assertEqual(current, self.source)
        self.assertEqual(origins['source_loader']['sha256'], hashlib.sha256(loader.read_bytes()).hexdigest())
        self.assertEqual(fingerprint['canonical_sha256'], binding['receipt_canonical_sha256'])


@unittest.skipUnless(LINUX, 'Real Linux pidfd CPU preallocation fixture')
class LiveHostLinuxTests(unittest.TestCase):
    def test_real_fresh_worker_checks_pidfds_but_receipt_never_grants_gpu_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = source_fixture(root)
            gpu_path, host_path = root / 'gpu.json', root / 'host.json'
            gpu_path.write_text(json.dumps(gpu_fixture()))
            host_path.write_text(json.dumps({'hostname': 'fixture-host',
                                           'local_ipv4s': [host.NODES['ms-n1-1']]}))
            attempt = 'frontier-v8-' + '1' * 16
            stage = stage_fixture(root, attempt, source['scientific']['commit'])
            spec = {'schema_version': 1, 'mode': 'no_borrow', 'attempt_id': attempt,
                'acquisition_id': 'a' * 32, 'node_alias': 'ms-n1-1',
                'expected_hostname': 'fixture-host', 'gpu_uuid': 'GPU-fixture-2',
                'restoration_seconds': 2, 'lease_directory': str(root / 'leases'),
                'source_binding': {'receipt_path': str(root / 'sources.json'),
                                   'receipt_canonical_sha256': host._canonical(source)},
                'stage_binding': stage}
            config_path = root / 'spec.json'
            config_path.write_text(json.dumps(spec))
            output = root / 'preallocation-checks.json'
            worker = root / 'trusted-cpu-worker.py'
            worker.write_text('from dataclasses import asdict\nimport json, os, sys, time\nfrom pathlib import Path\n'
                + 'sys.path.insert(0, ' + repr(str(ROOT)) + ')\n'
                + 'from scripts import frontier_v8_live_host as h, frontier_v8_owned_process as p\n'
                + 'spec = json.loads(Path(' + repr(str(config_path)) + ').read_bytes())\n'
                + 'guard = p.capture_identity(os.getpid())\n'
                + 'spec.update(guard=asdict(guard), controller=asdict(p.capture_identity(guard.ppid)), '
                + 'nonce=os.environ[p.NONCE_KEY], work_started_monotonic=time.monotonic(), '
                + 'work_deadline_monotonic=time.monotonic()+5)\n'
                + 'def verify(context):\n    return json.loads(Path(context["fixture_receipt"]).read_bytes())\n'
                + 'owner = h.bind_cpu_fixture_preallocation(spec, gpu_fixture_path=' + repr(str(gpu_path))
                + ', host_fixture_path=' + repr(str(host_path)) + ', source_verifier=verify)\n'
                + 'try:\n    owner.assert_owned()\n'
                + '    Path(' + repr(str(output)) + ').write_text(json.dumps(h._thaw(owner.bindings)))\n'
                + 'finally:\n    owner.close()\n')
            receipt = process.run_owned_cpu_worker([sys.executable, '-I', '-S', str(worker)],
                attempt_directory=root / 'owned-process', timeout_seconds=8, cleanup_seconds=3)
            checks = json.loads(output.read_bytes())
            self.assertTrue(checks['linux_pidfd_evidence'])
            self.assertEqual(checks['scope'], host.CPU_SCOPE)
            self.assertTrue(checks['injected_GPU'])
            self.assertTrue(checks['source_verifier_injected'])
            self.assertEqual(checks['guard']['ppid'], checks['controller']['pid'])
            for key in AUTHORITY:
                self.assertIs(checks[key], False)
            self.assertEqual(receipt['quiescence']['status'], 'owned_cpu_worker_tree_quiescence_proven')
            self.assertTrue(receipt['quiescence']['members'])
            self.assertTrue(all(row['pidfd_exit_observed'] for row in receipt['quiescence']['members']))
            self.assertTrue((root / 'leases/GPU-fixture-2.reservation.json').is_file())


if __name__ == '__main__':
    unittest.main()
