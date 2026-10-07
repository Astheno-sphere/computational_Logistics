import copy
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import run_posttraining_evaluation as queue


def plan():
    predecessors = []
    for pid, ticks in queue.PROCESS_STARTS.items():
        predecessors.append({'pid': pid, 'start_ticks': ticks, 'uid': 1000,
                             'ppid': 1 if pid == 1437936 else 1437936 if pid == 1444386 else 1444386,
                             'cwd': '/mnt/localssd/open-jev/latency-repo-8360b88' if pid == 1437936 else str(queue.TRAIN_CHECKOUT),
                             'command_sha256': 'a' * 64,
                             'cuda_visible_devices': '' if pid == 1437936 else ','.join(queue.GPUS)})
    return {'schema_version': 1, 'hostname': queue.HOST, 'gpu_uuids': queue.GPUS,
            'predecessors': predecessors, 'stages': queue.stages(), 'pending': queue.PENDING,
            'output': str(queue.BASE / 'queues/posttraining-20260920')}


def completed_status():
    return {'status': 'complete', 'phase': 'resumed_training_finished', 'training_exit_code': 0,
            'child_pid': 1444386, 'supervisor_pid': 1239866}


class PosttrainingTests(unittest.TestCase):
    def test_plan_rejects_retired_supervisor_wrong_cards_and_noop_command(self):
        queue.validate_plan(plan())
        for change in ('pid', 'gpu', 'command'):
            value = copy.deepcopy(plan())
            if change == 'pid':
                value['predecessors'][0]['pid'] = 1239866
            elif change == 'gpu':
                value['gpu_uuids'] = value['gpu_uuids'][::-1]
            else:
                value['stages'][0]['command'] = ['python', '-c', 'pass']
            with self.assertRaises(ValueError):
                queue.validate_plan(value)

    def test_prepare_only_does_not_query_processes_gpus_or_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'; path.write_text(json.dumps(plan()))
            with patch.object(queue, 'process_identity') as proc, patch.object(queue, 'cards_free') as gpu, \
                    patch.object(queue, 'run_child') as child:
                result = queue.run(SimpleNamespace(plan=path, prepare_only=True))
            self.assertEqual(result['status'], 'prepared_not_launched')
            self.assertEqual(set(result['pending']), {'contact', 'amount'})
            proc.assert_not_called(); gpu.assert_not_called(); child.assert_not_called()

    def test_finished_status_does_not_override_live_rank(self):
        value = plan(); rank = value['predecessors'][-1]
        with patch.object(queue, 'read', return_value=completed_status()), \
                patch.object(queue, 'process_identity', side_effect=lambda pid: rank if pid == rank['pid'] else None):
            self.assertFalse(queue.predecessors_finished(value))

    def test_reused_pid_aborts_without_signals(self):
        value = plan(); changed = {**value['predecessors'][0], 'start_ticks': 1}
        with patch.object(queue, 'read', return_value=completed_status()), \
                patch.object(queue, 'process_identity', return_value=changed), patch.object(queue.os, 'killpg') as signal:
            with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                queue.predecessors_finished(value)
            signal.assert_not_called()

    def test_failed_or_incomplete_final_training_never_becomes_ready(self):
        for status in ({'status': 'failed'}, {**completed_status(), 'training_exit_code': 1},
                       {**completed_status(), 'phase': 'four_gpu_27b_training_resumed'}):
            with patch.object(queue, 'read', return_value=status), patch.object(queue, 'process_identity', return_value=None):
                with self.assertRaises(RuntimeError):
                    queue.predecessors_finished(plan())

    def test_successful_training_uses_actual_identity_not_stale_metadata_pid(self):
        with patch.object(queue, 'read', return_value=completed_status()), patch.object(queue, 'process_identity', return_value=None):
            self.assertTrue(queue.predecessors_finished(plan()))

    def test_real_lease_contention_is_not_bypassed(self):
        with tempfile.TemporaryDirectory() as directory:
            with queue.leases(['lease'], Path(directory)):
                with self.assertRaises(BlockingIOError):
                    with queue.leases(['lease'], Path(directory)):
                        self.fail('lease acquired twice')

    def test_busy_lease_does_not_even_query_cards(self):
        with patch.object(queue, 'leases', side_effect=BlockingIOError), patch.object(queue, 'cards_free') as gpu:
            self.assertFalse(queue.allocation_available())
            gpu.assert_not_called()

    def test_foreign_gpu_process_blocks_allocation(self):
        cards = '\n'.join(f'{i},{uuid},0,0' for i, uuid in enumerate(queue.GPUS))
        with patch.object(queue.subprocess, 'check_output', side_effect=[cards, queue.GPUS[0] + ',999']):
            self.assertFalse(queue.cards_free())
        with patch.object(queue.subprocess, 'check_output', side_effect=[cards, '']):
            self.assertTrue(queue.cards_free())

    def test_changed_gpu_uuid_aborts(self):
        cards = '\n'.join(f'{i},GPU-wrong,0,0' for i in range(4))
        with patch.object(queue.subprocess, 'check_output', return_value=cards):
            with self.assertRaisesRegex(RuntimeError, 'UUID'):
                queue.cards_free()

    def test_zero_exit_does_not_replace_matching_expansion_artifacts(self):
        ready = {'implementation_sha256': {}, 'models': {'27b': {'checkpoint_sha256': 'good'}}, 'data_identity': {}}
        manifest = {'status': 'complete', 'gpus_free_after_cleanup': True, 'model_order': ['27b'],
                    'models': {'27b': {'exit_codes': [0] * 4}}, 'gpu_uuids': queue.GPUS,
                    'dataset_profile': queue.PROFILE, 'implementation_sha256': {}}
        summary = {'status': 'complete', 'total_rows': 40281, 'checkpoint': ready['models']['27b'], 'data_identity': {}}
        with patch.object(queue, 'read', side_effect=[manifest, summary]), patch.object(queue, 'file_info', return_value={}):
            queue.verify_expansion(ready)
        summary['total_rows'] = 512
        with patch.object(queue, 'read', side_effect=[manifest, summary]):
            with self.assertRaisesRegex(ValueError, '40,281'):
                queue.verify_expansion(ready)

    def test_service_requires_fixed_settings_every_measurement_and_cleanup(self):
        stage = queue.stages()[2]
        ready = {'models': {'27b': {'checkpoint_sha256': 'expected'}}}
        manifest = {'status': 'complete', 'code_commit': queue.SERVICE_COMMIT, 'physical_gpu': 3,
                    'configuration': {'max_length': 16384, 'batch_size': 1, 'measurements': queue.MEASUREMENTS,
                                      'include_doom': True, 'doom_decision_mode': 'typed-v1'},
                    'models': {'27b': {'expected_identity': {'checkpoint_sha256': 'expected', 'max_length': 16384},
                                      'measurements': {name: {'exit_code': 0} for name in queue.MEASUREMENTS},
                                      'gpu_after_shutdown': {'compute_processes': []}}}}
        with patch.object(queue, 'read', return_value=manifest), patch.object(queue, 'file_info', return_value={}):
            queue.verify_service(stage, ready)
        for change in ('batch', 'measurement', 'cleanup'):
            bad = copy.deepcopy(manifest)
            if change == 'batch': bad['configuration']['batch_size'] = 16
            elif change == 'measurement': del bad['models']['27b']['measurements']['games']
            else: bad['models']['27b']['gpu_after_shutdown']['compute_processes'] = [{'pid': 9}]
            with patch.object(queue, 'read', return_value=bad), self.assertRaises(ValueError):
                queue.verify_service(stage, ready)

    def audit_fixture(self, root):
        evaluation, training, gate = root / 'evaluation', root / 'training', root / 'gate'
        gate.mkdir(); (evaluation / '27b').mkdir(parents=True); training.mkdir()
        names = ['evaluation/' + n for n in ('plan.json', 'summary.json', 'merged-test.jsonl', 'merged-ood.jsonl')]
        names += [f'evaluation/shard-{r}.{s}' for r in range(4) for s in ('json', 'jsonl', 'log')]
        names += ['training/' + n for n in ('run.json', 'summary.json', 'training.jsonl', 'calibration.jsonl', 'trained_test.jsonl', 'reload_check.jsonl')]
        names += ['training/checkpoint/' + n for n in ('head.pt', 'model.json', 'temperature.json', 'adapter/adapter_config.json', 'adapter/adapter_model.safetensors')]
        files = {}
        for name in names:
            path = Path(name); base = evaluation / '27b' if path.parts[0] == 'evaluation' else training
            target = base.joinpath(*path.parts[1:]); target.parent.mkdir(parents=True, exist_ok=True); target.write_text(name)
            files[name] = queue.file_info(target)
        (evaluation / 'manifest.json').write_text('manifest')
        source = {'status': 'ready', 'source_commit': queue.EXPANSION_COMMIT, 'source_root': str(evaluation), 'files': files}
        capture = {'status': 'copied_completed_expansion', 'read_only_remote': True, 'source_before': source, 'source_after': source,
                   'controller_manifests': {key: queue.file_info(evaluation / 'manifest.json') for key in ('before', 'after')}}
        (gate / 'capture.json').write_text(json.dumps(capture))
        ready = {'models': {'27b': {'checkpoint_sha256': 'expected'}}, 'data_identity': {}}
        auditor = queue.ROOT / 'reports/full-data-eval-expansion-n1-v1'
        report = {'status': 'passed', 'evaluation_source_commit': queue.EXPANSION_COMMIT, 'model_evaluation_complete': True,
                  'controller_complete_at_capture': True, 'checkpoint': ready['models']['27b'], 'data_identity': {},
                  'coverage': {'expected_rows': 40281, 'unique_ids': 40281, 'shard_rows': [10071, 10070, 10070, 10070],
                               'missing': 0, 'duplicate': 0, 'failed': 0},
                  'verification': {'capture_sha256': queue.file_info(gate / 'capture.json')['sha256'],
                                   'audit_code_sha256': {n: queue.file_info(auditor / n)['sha256'] for n in ('verify.py', 'expansion_contract.py')}}}
        (gate / '27b-audit.json').write_text(json.dumps(report))
        return evaluation, training, gate, ready, report

    def test_audit_gate_requires_complete_matching_unchanged_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            evaluation, training, gate, ready, _ = self.audit_fixture(Path(directory))
            with patch.object(queue, 'EXPANSION_OUTPUT', evaluation), patch.object(queue, 'TRAIN', training):
                self.assertTrue(queue.independent_audit_ready(gate, ready))
                (training / 'checkpoint/head.pt').write_text('different weights')
                with self.assertRaisesRegex(ValueError, 'evidence changed'):
                    queue.independent_audit_ready(gate, ready)

    def test_failed_audit_and_wrong_checkpoint_never_open_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            evaluation, training, gate, ready, report = self.audit_fixture(Path(directory))
            for change in ('status', 'checkpoint'):
                bad = copy.deepcopy(report)
                bad[change] = 'failed' if change == 'status' else {'checkpoint_sha256': 'other'}
                (gate / '27b-audit.json').write_text(json.dumps(bad))
                with patch.object(queue, 'EXPANSION_OUTPUT', evaluation), patch.object(queue, 'TRAIN', training):
                    with self.assertRaisesRegex(ValueError, 'audit failed'):
                        queue.independent_audit_ready(gate, ready)

    def test_missing_audit_waits_without_any_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(queue, 'run_child') as child:
                self.assertFalse(queue.independent_audit_ready(Path(directory), {}))
                child.assert_not_called()

    def test_owned_child_is_reaped_if_status_write_fails(self):
        child = Mock(pid=321); child.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, patch.object(queue.subprocess, 'Popen', return_value=child), \
                patch.object(queue.os, 'killpg') as kill:
            with self.assertRaisesRegex(OSError, 'full'):
                queue.run_child(queue.stages()[0], Path(directory) / 'log', Mock(side_effect=OSError('full')))
            kill.assert_called_once_with(321, queue.signal.SIGTERM)
            child.wait.assert_called_once()

    def test_nonzero_child_exit_stops_sequence(self):
        child = Mock(pid=321); child.wait.return_value = 1; child.poll.return_value = 1
        with tempfile.TemporaryDirectory() as directory, patch.object(queue.subprocess, 'Popen', return_value=child):
            with self.assertRaisesRegex(RuntimeError, 'no next stage'):
                queue.run_child(queue.stages()[0], Path(directory) / 'log', Mock())

    def test_full_sequence_uses_audit_barrier_and_preserves_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            value = plan(); value['output'] = str(Path(directory) / 'queue')
            path = Path(directory) / 'plan.json'; path.write_text(json.dumps(value))
            args = SimpleNamespace(plan=path, prepare_only=False, expected_commit='a' * 40, wait_hours=1, poll_seconds=1)
            events = []
            def child(stage, log, update): events.append(stage['name'])
            def audited(*args): events.append('audit'); return True
            with patch.object(queue, 'validate_plan'), patch.object(queue.socket, 'gethostname', return_value=queue.HOST), \
                    patch.object(queue.os, 'getuid', return_value=1000), patch.dict(queue.os.environ, {'CUDA_VISIBLE_DEVICES': ''}), \
                    patch.object(queue, 'check_checkout'), patch.object(queue, 'predecessors_finished', return_value=True), \
                    patch.object(queue, 'final_checkpoint_readiness', return_value={'models': {}}), \
                    patch.object(queue, 'leases', side_effect=lambda *a: nullcontext()), \
                    patch.object(queue, 'allocation_available', return_value=True), patch.object(queue, 'run_child', side_effect=child), \
                    patch.object(queue, 'verify_expansion', return_value={}), patch.object(queue, 'verify_service', return_value={}), \
                    patch.object(queue, 'independent_audit_ready', side_effect=audited), patch.object(queue, 'benchmark_separation') as separation:
                result = queue.run(args)
                with self.assertRaises(FileExistsError): queue.run(args)
            self.assertEqual(events, ['expansion', 'audit', 'service_2b_9b', 'audit', 'service_27b'])
            self.assertEqual(result['status'], 'complete_with_pending_stages')
            self.assertEqual(set(result['pending']), {'contact', 'amount'})
            separation.assert_called_once()


if __name__ == '__main__':
    unittest.main()
