"""Independent raw proc/file/HTTP/time-series CPU fixtures; no models or GPUs."""
import base64
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import frontier_v8_restoration_audit as audit


BOOT = '01234567-89ab-cdef-0123-456789abcdef'


def identity(pid, birth=None, ppid=51, group=None):
    return {'boot_id': BOOT, 'pid': pid, 'uid': 1000,
            'start_ticks': birth or pid + 1000, 'ppid': ppid,
            'pgrp': group or pid, 'session': group or pid}


class Handler(BaseHTTPRequestHandler):
    status_code = 200

    def do_GET(self):
        self.send_response(self.status_code)
        if self.path == '/redirect':
            self.send_header('Location', 'http://192.0.2.1/never-requested')
        self.end_headers()
        self.wfile.write(b'{"available":true}')

    def log_message(self, *args):
        pass


class Fixture:
    def __init__(self, directory, port):
        self.root = Path(directory).resolve(); self.proc = self.root / 'proc'
        boot = self.proc / 'sys/kernel/random'; boot.mkdir(parents=True)
        (boot / 'boot_id').write_text(BOOT + '\n')
        self.tree = self.root / 'checkpoint'; self.tree.mkdir()
        for name, content in [('optimizer.bin', b'fixed optimizer'), ('sampler.bin', b'fixed sampler'),
                              ('config.json', b'{"batch":14}')]:
            (self.tree / name).write_bytes(content)
        self.progress = self.root / 'progress.json'; self.set_progress(0)
        roles = [('rank', i) for i in range(4)] + [('coordinator', 0)] + [('service', i) for i in range(3)]
        originals = []
        for i, (role, ordinal) in enumerate(roles):
            item = identity(101 + i); command = self.add(item)
            originals.append({'role': role, 'ordinal': ordinal, 'identity': item,
                              'cmdline_sha256': hashlib.sha256(command).hexdigest()})
        self.gpus = {'gpus': [{'index': i, 'uuid': 'GPU-fixture-' + str(i), 'name': 'NVIDIA H100',
                              'total_memory_mib': 81559, 'used_memory_mib': 1, 'idle_memory_mib': 0}
                             for i in range(8)], 'compute_processes': []}
        self.gpu_file = self.root / 'gpu.json'; self.write_gpu()
        self.baseline = {'schema_version': 1, 'mode': 'borrowed_same_process', 'acquisition_id': 'a' * 32,
                         'node_alias': 'ms-n1-1', 'boot_id': BOOT, 'uid': 1000,
                         'immutable_roots': [str(self.tree)],
                         'immutable_files': [{'path': str(p), 'size': p.stat().st_size,
                                              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                             for p in sorted(self.tree.iterdir())],
                         'original_processes': originals,
                         'services': [{'url': 'http://127.0.0.1:' + str(port) + '/' + str(i),
                                       'process_pid': 106 + i, 'expected_status': 200} for i in range(3)],
                         'progress': [{'path': str(self.progress), 'extractor': 'json_integer',
                                       'key_path': ['step'], 'before_value': 0}],
                         'actual_optimizer_boundary_verified': False,
                         'protected_gpu_inventory': {'gpus': [{k: g[k] for k in
                             ('index', 'uuid', 'name', 'total_memory_mib')} for g in self.gpus['gpus'][:2]],
                             'compute_processes': []}}
        self.now = 10.0; self.advance = True

    def add(self, item, state='S', uid=None):
        path = self.proc / str(item['pid']); path.mkdir(exist_ok=True)
        fields = [state, str(item['ppid']), str(item['pgrp']), str(item['session'])] + ['0'] * 15 + [str(item['start_ticks'])]
        (path / 'stat').write_text(str(item['pid']) + ' (fixture (with ) parentheses)) ' + ' '.join(fields) + '\n')
        (path / 'status').write_text('Uid:\t' + '\t'.join(str(uid if uid is not None else item['uid']) for _ in range(4)) + '\n')
        command = ('python\0fixture-' + str(item['pid']) + '\0').encode()
        (path / 'cmdline').write_bytes(command)
        return command

    def set_progress(self, value):
        self.progress.write_text(json.dumps({'step': value}))

    def write_gpu(self):
        self.gpu_file.write_text(json.dumps(self.gpus))

    def sleep(self, duration):
        self.now += duration
        if self.advance:
            self.set_progress(int(self.now - 10))

    def observe(self, owned=None, **kwargs):
        return audit.observe_restore(self.baseline, owned or [], recovery_started_monotonic=10,
            recovery_deadline_monotonic=13, proc_root=self.proc, gpu_fixture_path=self.gpu_file,
            clock=lambda: self.now, wall_clock=lambda: -999999, sleep=self.sleep, **kwargs)


class RestorationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def setUp(self):
        Handler.status_code = 200
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.f = Fixture(self.temp.name, self.server.server_port)

    def failure(self, result, text):
        self.assertEqual(result['verification']['status'], 'resource_recovery_observation_failed')
        self.assertTrue(any(text in item for item in result['verification']['failures']), result)
        self.assertFalse(result['verification']['queue_restore_proven'])

    def test_raw_fulltree_same_process_http_and_progress_pass_without_authority(self):
        result = self.f.observe([identity(501)])
        self.assertEqual(result['verification']['status'], 'same_process_resource_recovery_observed')
        self.assertEqual(result['verification']['progress_series'][str(self.f.progress)], [0, 1])
        self.assertEqual(len(result['observations']), 2)
        self.assertEqual(base64.b64decode(result['observations'][0]['services'][0]['body']), b'{"available":true}')
        self.assertFalse(result['verification']['optimizer_boundary_proven'])
        self.assertFalse(result['verification']['queue_restore_proven'])
        self.assertFalse(result['verification']['execution_available'])
        self.assertTrue(result['fixture_inputs']['proc_root_injected'])

    def test_wrong_fullhash_same_size_fails(self):
        (self.f.tree / 'optimizer.bin').write_bytes(b'wrong optimizer')
        self.failure(self.f.observe(), 'immutable fullhash')

    def test_extra_unlisted_optimizer_leaf_fails_complete_inventory(self):
        (self.f.tree / 'unlisted.bin').write_bytes(b'not silently omitted')
        self.failure(self.f.observe(), 'immutable tree inventory')

    def test_symlink_in_immutable_tree_fails(self):
        (self.f.tree / 'link').symlink_to(self.f.progress)
        self.failure(self.f.observe(), 'symlink/special immutable leaf')

    def test_tree_traversal_permission_error_cannot_silently_prune(self):
        def inaccessible(root, *, followlinks, onerror):
            onerror(PermissionError('fixture unreadable subtree'))
            yield str(root), [], []
        with patch.object(audit.os, 'walk', side_effect=inaccessible):
            self.failure(self.f.observe(), 'immutable tree traversal failed')

    def test_leaf_mutation_after_final_fd_stat_fails(self):
        path = self.f.tree / 'config.json'; real = os.fstat; calls = []
        def changing(fd):
            value = real(fd); calls.append(fd)
            if len(calls) == 2:
                path.write_bytes(b'{"batch":15}')
            return value
        with patch.object(audit.os, 'fstat', side_effect=changing):
            with self.assertRaisesRegex(audit.RestorationAuditError, 'changed while hashing'):
                audit._fingerprint(path, lambda: 10)

    def test_original_pid_reuse_fails(self):
        item = dict(self.f.baseline['original_processes'][0]['identity']); item['start_ticks'] += 1
        self.f.add(item)
        self.failure(self.f.observe(), 'original same-process identity')

    def test_original_uid_and_boot_mismatch_fail(self):
        self.f.add(self.f.baseline['original_processes'][0]['identity'], uid=1001)
        self.failure(self.f.observe(), 'original same-process identity')
        (self.f.proc / 'sys/kernel/random/boot_id').write_text('99999999-89ab-cdef-0123-456789abcdef\n')
        self.failure(self.f.observe(), 'boot identity differs')

    def test_original_stopped_and_missing_fail(self):
        self.f.add(self.f.baseline['original_processes'][0]['identity'], state='T')
        self.failure(self.f.observe(), 'original stopped/dead')
        shutil.rmtree(self.f.proc / '101')
        self.failure(self.f.observe(), 'original process absent')

    def test_original_reparent_after_bound_parent_exit_preserves_same_birth(self):
        parent = identity(51, ppid=1); self.f.add(parent)
        shutil.rmtree(self.f.proc / '51')
        for spec in self.f.baseline['original_processes']:
            changed = dict(spec['identity']); changed['ppid'] = 1; self.f.add(changed)
        result = self.f.observe(original_parent_identity=parent)
        self.assertEqual(result['verification']['status'], 'same_process_resource_recovery_observed')
        self.assertIsNone(result['observations'][0]['original_parent'])

    def test_original_reparent_requires_proof_bound_parent_exited(self):
        parent = identity(51, ppid=1); self.f.add(parent)
        changed = dict(self.f.baseline['original_processes'][0]['identity']); changed['ppid'] = 1
        self.f.add(changed)
        self.failure(self.f.observe(), 'lacks bound parent')
        self.failure(self.f.observe(original_parent_identity=parent), 'parent remains alive')

    def test_original_reparent_after_bound_parent_zombie_with_empty_cmdline(self):
        parent = identity(51, ppid=1); self.f.add(parent, state='Z')
        (self.f.proc / '51/cmdline').write_bytes(b'')
        for spec in self.f.baseline['original_processes']:
            changed = dict(spec['identity']); changed['ppid'] = 1; self.f.add(changed)
        result = self.f.observe(original_parent_identity=parent)
        self.assertEqual(result['verification']['failures'], [])

    def test_known_owned_birth_cannot_escape_via_reparenting_and_setsid(self):
        original = identity(501); escaped = dict(original)
        escaped.update(ppid=1, pgrp=999, session=999); self.f.add(escaped)
        self.failure(self.f.observe([original]), 'owned worker still alive')

    def test_static_progress_reaches_monotonic_deadline_without_pass(self):
        self.f.advance = False
        self.failure(self.f.observe(), 'bounded recovery deadline expired')
        self.assertEqual(self.f.now, 13)

    def test_noninteger_progress_fails(self):
        self.f.set_progress(True)
        self.failure(self.f.observe(), 'progress is not an integer')

    def test_http_503_response_is_actual_availability_failure(self):
        Handler.status_code = 503
        result = self.f.observe(); self.failure(result, 'HTTP availability')
        self.assertEqual(result['observations'][0]['services'][0]['status'], 503)

    def test_redirect_cannot_follow_external_host(self):
        Handler.status_code = 302
        self.f.baseline['services'][0]['url'] = 'http://127.0.0.1:' + str(self.server.server_port) + '/redirect'
        result = self.f.observe(); self.failure(result, 'HTTP availability')
        self.assertEqual(result['observations'][0]['services'][0]['status'], 302)

    def test_owned_worker_alive_and_unlisted_same_group_descendant_fail(self):
        worker = identity(501); self.f.add(worker)
        self.failure(self.f.observe([worker]), 'owned worker still alive')
        shutil.rmtree(self.f.proc / '501'); self.f.add(identity(502, group=501))
        self.failure(self.f.observe([worker]), 'owned group/session survivor')

    def test_protected_gpu_metadata_and_process_changes_fail(self):
        self.f.gpus['gpus'][0]['uuid'] = 'GPU-changed'; self.f.write_gpu()
        self.failure(self.f.observe(), 'protected GPU0/1 inventory')
        self.f.gpus['gpus'][0]['uuid'] = 'GPU-fixture-0'
        self.f.add(identity(301)); self.f.gpus['compute_processes'] = [
            {'gpu_uuid': 'GPU-fixture-0', 'pid': 301, 'process_name': 'python'}]
        self.f.write_gpu(); self.failure(self.f.observe(), 'protected GPU0/1 inventory')

    def test_protected_compute_birth_and_command_independently_observed(self):
        process = identity(301); command = self.f.add(process)
        app = {'gpu_uuid': 'GPU-fixture-0', 'pid': 301, 'process_name': 'python'}
        self.f.gpus['compute_processes'] = [app]; self.f.write_gpu()
        self.f.baseline['protected_gpu_inventory']['compute_processes'] = [
            {**app, 'identity': process, 'cmdline_sha256': hashlib.sha256(command).hexdigest()}]
        self.assertEqual(self.f.observe()['verification']['failures'], [])
        (self.f.proc / '301/cmdline').write_bytes(b'changed command\0')
        self.failure(self.f.observe(), 'protected GPU0/1 inventory')

    def test_dynamic_memory_utilization_does_not_change_protected_identity(self):
        self.f.gpus['gpus'][0]['used_memory_mib'] = 777; self.f.write_gpu()
        self.assertEqual(self.f.observe()['verification']['failures'], [])

    def test_saved_verifier_reparses_raw_not_observer_success_boolean(self):
        result = self.f.observe(); altered = copy.deepcopy(result)
        altered['verification'] = {'status': 'all_true'}
        altered['observations'][1]['progress'][0]['body_sha256'] = '0' * 64
        self.assertTrue(audit.verify_restoration(self.f.baseline, altered)['failures'])
        result['verification'] = {'status': 'caller_false'}
        self.assertEqual(audit.verify_restoration(self.f.baseline, result)['failures'], [])

    def test_wall_clock_jumps_have_no_recovery_control_effect(self):
        result = self.f.observe()
        self.assertEqual(result['verification']['failures'], [])
        self.assertEqual(result['observations'][0]['observed_at_epoch_s'], -999999)

    def test_monotonic_time_reversal_invalidates_saved_observation(self):
        result = self.f.observe()
        result['observations'][1]['observed_at_monotonic'] = 9
        self.assertIn('observation outside recovery deadline',
                      audit.verify_restoration(self.f.baseline, result)['failures'])

    def test_default_GPU_backend_uses_absolute_binary_and_scrubbed_environment(self):
        outputs = [b'0,GPU-fixture-0,NVIDIA H100,81559\n1,GPU-fixture-1,NVIDIA H100,81559\n', b'']
        with patch.object(audit.subprocess, 'check_output', side_effect=outputs) as query:
            payload = audit._gpu_query(2)
        self.assertEqual(payload['gpu_csv'], outputs[0])
        for call in query.call_args_list:
            self.assertEqual(call.args[0][0], '/usr/bin/nvidia-smi')
            self.assertEqual(call.kwargs['env'], {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})

    def test_fresh_raw_CSV_query_is_independently_parsed(self):
        csv_bytes = b'0, GPU-fixture-0, NVIDIA H100, 81559\n1, GPU-fixture-1, NVIDIA H100, 81559\n'
        result = audit.observe_restore(self.f.baseline, [], recovery_started_monotonic=10,
            recovery_deadline_monotonic=13, proc_root=self.f.proc, clock=lambda: self.f.now,
            sleep=self.f.sleep, gpu_query=lambda timeout: {'gpu_csv': csv_bytes, 'compute_csv': b''})
        self.assertEqual(result['verification']['failures'], [])
        self.assertEqual(result['observations'][0]['gpu']['format'], 'csv')

    def test_oversized_deadline_and_claimed_optimizer_boundary_rejected_before_reads(self):
        with self.assertRaisesRegex(audit.RestorationAuditError, 'bounded recovery'):
            audit.observe_restore(self.f.baseline, [], recovery_started_monotonic=0,
                                  recovery_deadline_monotonic=1501)
        self.f.baseline['actual_optimizer_boundary_verified'] = True
        with self.assertRaisesRegex(audit.RestorationAuditError, 'optimizer boundary'):
            self.f.observe()

    def test_no_borrow_can_hash_stage_inputs_without_queue_claim(self):
        self.f.baseline.update(mode='no_borrow', original_processes=[], services=[], progress=[])
        result = self.f.observe()
        self.assertEqual(result['verification']['failures'], [])
        self.assertFalse(result['verification']['queue_restore_proven'])

    def test_baseline_missing_rank_and_nonloopback_endpoint_fail(self):
        baseline = copy.deepcopy(self.f.baseline); baseline['original_processes'].pop(0)
        with self.assertRaisesRegex(audit.RestorationAuditError, 'four ranks'):
            audit.validate_baseline(baseline)
        baseline = copy.deepcopy(self.f.baseline); baseline['services'][0]['url'] = 'http://example.com:80/'
        with self.assertRaisesRegex(audit.RestorationAuditError, 'loopback'):
            audit.validate_baseline(baseline)

    def test_production_cli_refuses_before_any_paths_or_reads(self):
        with patch.object(audit, '_read', side_effect=AssertionError('read must not happen')):
            with self.assertRaisesRegex(audit.RestorationAuditError, 'Production restoration CLI unavailable'):
                audit.main(['--baseline', '/missing', '--audit'])


if __name__ == '__main__':
    unittest.main()
