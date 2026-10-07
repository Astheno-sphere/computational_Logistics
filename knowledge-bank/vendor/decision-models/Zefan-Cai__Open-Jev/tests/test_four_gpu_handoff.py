import json
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from scripts import run_four_gpu_handoff as handoff


class HandoffTests(unittest.TestCase):
    def job(self, output):
        return {'pid': 123, 'start_ticks': 456, 'uid': 1000, 'cwd': '/original',
                'command': ['python', '-m', 'jev.train'], 'cuda_visible_devices': 'GPU-original',
                'output': str(output), 'tag': '2b', 'model': 'Qwen/Qwen3.5-2B',
                'revision': 'a' * 40, 'steps': 20204, 'run_identity_sha256': 'identity'}

    def test_pid_reuse_never_permits_signal(self):
        job = self.job('/unused')
        with patch.object(handoff, 'process_identity', return_value={**job, 'start_ticks': 789}), \
                patch.object(handoff.os, 'pidfd_open', create=True) as opened:
            with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                handoff.retire_old_27b(job, lambda _: None)
            opened.assert_not_called()

    def test_last_optimizer_step_is_not_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            job = self.job(output)
            (output / 'training.jsonl').write_text('{"step":20204}\n')
            with patch.object(handoff, 'process_identity', return_value=job):
                self.assertIsNone(handoff.completed_model(job, 'commit'))
            with patch.object(handoff, 'process_identity', return_value=None):
                with self.assertRaisesRegex(RuntimeError, 'without a complete summary'):
                    handoff.completed_model(job, 'commit')

    def test_bad_reload_or_calibration_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            job = self.job(output)
            (output / 'checkpoint').mkdir()
            summary = {'status': 'complete', 'model': job['model'], 'steps': job['steps'],
                       'checkpoint_reload_max_error': 0.1}
            (output / 'summary.json').write_text(json.dumps(summary))
            (output / 'run.json').write_text(json.dumps({'run_identity_sha256': 'identity', 'calibration_ids': ['cal1']}))
            (output / 'checkpoint/temperature.json').write_text(json.dumps({'split': 'test', 'n': 1, 'temperature': 1}))
            with patch.object(handoff, 'process_identity', return_value=None):
                with self.assertRaisesRegex(ValueError, 'reload checks'):
                    handoff.completed_model(job, 'commit')
                summary['checkpoint_reload_max_error'] = 0
                (output / 'summary.json').write_text(json.dumps(summary))
                with self.assertRaisesRegex(ValueError, 'calibration provenance'):
                    handoff.completed_model(job, 'commit')

    def test_snapshot_failure_precedes_pidfd_and_signal(self):
        job = self.job('/unused')
        with patch.object(handoff, 'process_identity', return_value=job), \
                patch.object(handoff, 'latest_verified_snapshot', side_effect=ValueError('checksum mismatch')), \
                patch.object(handoff.os, 'pidfd_open', create=True) as opened:
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                handoff.retire_old_27b(job, lambda _: None)
            opened.assert_not_called()

    def test_wrong_model_or_noop_phase_commands_are_rejected(self):
        plan = json.loads((handoff.ROOT / 'configs/n1-four-gpu-handoff.json').read_text())
        handoff.validate_commands(plan)
        for field in ('evaluation_command', 'training_command'):
            changed = copy.deepcopy(plan)
            changed[field] = [sys.executable, '-c', 'pass']
            with self.assertRaisesRegex(ValueError, 'Phase command differs'):
                handoff.validate_commands(changed)
        plan['jobs']['27b']['model'] = 'different-model'
        with self.assertRaisesRegex(ValueError, 'original Open-Jev command'):
            handoff.validate_commands(plan)

    def test_changed_frozen_inputs_after_wait_prevent_retirement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {'jobs': {'2b': {}, '9b': {}, '27b': {}}}
            path = root / 'plan.json'
            path.write_text(json.dumps(plan))
            args = type('Args', (), {'plan': str(path), 'expected_commit': 'commit',
                                    'prepare_only': False, 'output_root': str(root / 'out'),
                                    'wait_timeout': 10, 'poll_seconds': 0.01})()
            with patch.object(handoff, 'validate_plan', side_effect=['commit', ValueError('Frozen input changed')]), \
                    patch.object(handoff, 'acquire_locks'), \
                    patch.object(handoff, 'completed_model', return_value={'valid': True}), \
                    patch.object(handoff, 'only_original_27b_on_cards', return_value=True), \
                    patch.object(handoff, 'retire_old_27b') as retire:
                with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
                    handoff.run(args)
                retire.assert_not_called()

    def test_zero_exit_does_not_replace_completed_eval_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'manifest.json').write_text(json.dumps({'status': 'complete', 'models': {'2b': {}}}))
            with self.assertRaisesRegex(ValueError, 'complete matching manifest'):
                handoff.verify_evaluation({'evaluation_output': directory}, {})

    def test_foreign_gpu_process_blocks_retirement(self):
        cards = [{'uuid': f'GPU-{i}', 'compute_processes': [], 'memory_used_mib': 0,
                  'utilization_percent': 0} for i in range(4)]
        plan = {'gpu_uuids': [f'GPU-{i}' for i in range(4)], 'jobs': {'27b': {'pid': 123}}}
        cards[2]['compute_processes'] = [{'pid': 123}]
        with patch.object(handoff, 'gpu_snapshot', side_effect=cards):
            self.assertTrue(handoff.only_original_27b_on_cards(plan))
        cards[0]['compute_processes'] = [{'pid': 999}]
        with patch.object(handoff, 'gpu_snapshot', side_effect=cards):
            self.assertFalse(handoff.only_original_27b_on_cards(plan))

    def test_evaluation_failure_prevents_training(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {'jobs': {'2b': {}, '9b': {}, '27b': {}}, 'environment': {},
                    'evaluation_command': ['eval'], 'training_command': ['train']}
            path = root / 'plan.json'
            path.write_text(json.dumps(plan))
            args = type('Args', (), {'plan': str(path), 'expected_commit': 'commit',
                                    'prepare_only': False, 'output_root': str(root / 'out'),
                                    'wait_timeout': 10, 'poll_seconds': 0.01})()
            with patch.object(handoff, 'validate_plan', return_value='commit'), \
                    patch.object(handoff, 'acquire_locks'), \
                    patch.object(handoff, 'completed_model', return_value={'valid': True}), \
                    patch.object(handoff, 'only_original_27b_on_cards', return_value=True), \
                    patch.object(handoff, 'retire_old_27b', return_value={'retained': True}), \
                    patch.object(handoff, 'require_free_gpu'), \
                    patch.object(handoff, 'run_child', side_effect=RuntimeError('eval failed')) as child:
                with self.assertRaisesRegex(RuntimeError, 'eval failed'):
                    handoff.run(args)
                self.assertEqual(child.call_count, 1)
                self.assertEqual(child.call_args.args[0], ['eval'])
            status = json.loads((root / 'out/status.json').read_text())
            self.assertEqual(status['status'], 'failed')
            self.assertIn('eval failed', status['error'])

    def test_recording_failure_reaps_already_started_child(self):
        with tempfile.TemporaryDirectory() as directory:
            child = Mock(pid=123)
            child.poll.return_value = None
            child.wait.return_value = -15
            with patch.object(handoff.subprocess, 'Popen', return_value=child), \
                    patch.object(handoff.os, 'killpg') as kill:
                with self.assertRaisesRegex(OSError, 'disk full'):
                    handoff.run_child(['child'], Path(directory) / 'child.log', {},
                                      Mock(side_effect=OSError('disk full')), 'evaluation')
                kill.assert_called_once_with(123, handoff.signal.SIGTERM)
                child.wait.assert_called_once_with(timeout=30)

    def test_signals_enter_cleanup_path(self):
        with self.assertRaisesRegex(KeyboardInterrupt, 'signal'):
            handoff.interrupt(handoff.signal.SIGTERM, None)

    @unittest.skipUnless(hasattr(os, 'killpg'), 'requires POSIX process groups')
    def test_real_termination_reaps_owned_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = """import json,os,signal,sys
from pathlib import Path
from scripts import run_four_gpu_handoff as h
signal.signal(signal.SIGTERM,h.interrupt)
def update(phase,**fields):
    Path(sys.argv[1]).write_text(json.dumps(fields))
h.run_child([sys.executable,'-c','import time; time.sleep(60)'],Path(sys.argv[2]),os.environ.copy(),update,'test')
"""
            controller = subprocess.Popen([sys.executable, '-c', code, str(root / 'child.json'), str(root / 'child.log')],
                                          cwd=handoff.ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            child_pid = None
            try:
                deadline = time.monotonic() + 10
                while not (root / 'child.json').exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                child_pid = json.loads((root / 'child.json').read_text())['child_pid']
                controller.terminate()
                controller.wait(timeout=10)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if controller.poll() is None:
                    controller.kill()
                    controller.wait(timeout=10)
                if child_pid is not None:
                    try:
                        os.kill(child_pid, handoff.signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == '__main__':
    unittest.main()
