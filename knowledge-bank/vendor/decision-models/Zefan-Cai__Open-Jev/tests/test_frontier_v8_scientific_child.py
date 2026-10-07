"""CPU child fixtures: real frozen scoring arithmetic, fake training/ownership."""
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import compare_frontier_training_v8 as frozen_comparator
from scripts import run_frontier_training_v8 as frozen_driver
from scripts import frontier_v8_scientific_child as child
from tests.test_frontier_v8_comparison_replay_integration import (
    GPU, MEMORY, data_fixture, runtime)


ROOT = Path(__file__).resolve().parents[1]


class FixtureOwner:
    """This Python fixture has no pidfds, GPU lease or restoration authority."""
    def __init__(self, bindings, events):
        self.bindings, self.events, self.valid = MappingProxyType(bindings), events, True

    def assert_owned(self):
        self.events.append('fixture_owner_check')
        if not self.valid:
            raise RuntimeError('Fixture owner lost; this is not actual kernel authority')


class ScientificChildTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task = self.root/('frontier-v8-'+'a'*32)
        self.task.mkdir()
        self.metadata = self.root/'metadata'; self.metadata.mkdir()
        self.plan = json.loads((ROOT/'reports/frontier-v8-training-protocol-20261003/training-plan.json').read_text())
        self.events, self.written, self.training_runs = [], {}, 0
        self.context = {
            'scientific_root': str(self.root/'science'), 'native_root': str(self.root/'native'),
            'operational_root': str(self.root/'resource'), 'plan': str(self.root/'plan.json'),
            'freeze': str(self.root/'freeze.json'), 'native_declaration': str(self.root/'native-declaration.json'),
            'operational_declaration': str(self.root/'resource-declaration.json'),
            'metadata_directory': str(self.metadata), 'scientific_source_commit': child.SCIENCE_A,
            'native_source_commit': child.NATIVE_A, 'resource_source_commit': 'f'*40,
            'native_declaration_sha256': '1'*64, 'operational_declaration_sha256': '2'*64,
            'plan_sha256': child.PLAN_SHA, 'freeze_sha256': child.FREEZE_SHA}
        def args(request):
            return SimpleNamespace(request=str(request), plan=self.context['plan'], freeze=self.context['freeze'],
                expected_commit=child.SCIENCE_A, expected_plan_sha256=child.PLAN_SHA,
                expected_freeze_sha256=child.FREEZE_SHA)
        self.context['training_args'] = args(self.task/'execution-request.json')
        self.context['comparison_args'] = args(self.metadata/'comparison-request.json')
        self.request = {'attempt_id': self.task.name, 'task_directory': str(self.task),
            'python': '/fake-runtime/python3.11', 'dataset': str(self.root/'fixture-data'),
            'training_run': str(self.task/'training'), 'comparison_output': str(self.task/'comparison'),
            'completion_receipt': str(self.task/'training-completion.json'),
            'released_checkpoint': str(self.root/'released'), 'base_snapshot': str(self.root/'hf/snapshot'),
            'hf_cache': str(self.root/'hf'), 'runtime_receipt': str(self.task/'cpu-stage-receipt.json'),
            'runtime_receipt_sha256': '3'*64, 'resource_receipt': str(self.task/'resource-ready.json')}
        bindings = {'resource_scope': 'linux_cpu_fixture_only', 'attempt_id': self.task.name,
            'nonce': 'b'*64, 'gpu_uuid': GPU, 'visible_devices': '3', 'device': 'cuda:0',
            'scientific_source_commit': child.SCIENCE_A, 'native_source_commit': child.NATIVE_A,
            'resource_source_commit': 'f'*40, 'plan_sha256': child.PLAN_SHA,
            'freeze_sha256': child.FREEZE_SHA, 'execution_request_sha256': '4'*64,
            'runtime_receipt_sha256': '3'*64}
        self.owner = FixtureOwner(bindings, self.events)
        self.preflight = {'status': 'cpu_preflight_passed_launch_unavailable',
            'request_sha256': '4'*64, 'source_sha256': self.plan['implementation_sha256'],
            'resolved_training_argv': frozen_driver.translated_argv(self.plan, self.request)}
        self.validation = {
            'completed_steps': 733, 'consumed_rows': 2932,
            'artifacts_sha256': {name: '5'*64 for name in
                ('run.json', 'summary.json', 'training.jsonl', 'calibration.jsonl', 'reload_check.jsonl')},
            'checkpoint': {'files_sha256': {'head.pt': '6'*64}, 'directory_sha256': '7'*64},
            'calibration': {'journal_sha256': '5'*64, 'ordered_ids_sha256': '8'*64,
                            'count': 496, 'temperature': 2.0}}

    def verify_sources(self, context):
        self.events.append('fixture_source_checker')
        return context.copy()

    def prepare(self, args, *, claimed):
        self.events.append('fixture_scientific_prepare')
        self.assertTrue(claimed, 'Future episode caller owns the consumed attempt')
        self.assertIs(args, self.context['training_args'])
        return self.request, self.plan, self.preflight

    def translated(self, plan, request):
        self.events.append('frozen_translated_argv')
        return frozen_driver.translated_argv(plan, request)

    def run_training(self, args):
        self.events.append('fixture_train_run')
        self.training_runs += 1
        self.assertEqual({name: getattr(args, name) for name in self.plan['settings']}, self.plan['settings'])
        self.assertEqual(args.data, self.request['dataset'])
        self.assertEqual(args.output, self.request['training_run'])
        self.assertEqual(args.initial_checkpoint, self.request['released_checkpoint'])
        self.assertIsNone(args.resume_training)

    @contextmanager
    def observe(self, trainer, plan, bindings, publication, base, scientific_root, *, assert_owned):
        self.events.append('fixture_observer_enter')
        assert_owned()
        self.assertEqual(bindings['source_commit'], child.SCIENCE_A)
        self.assertEqual(publication['directory_sha256'], plan['expected_initial_checkpoint']['directory_sha256'])
        self.assertEqual(base['files_sha256'], plan['expected_base_snapshot_files_sha256'])
        self.assertEqual(scientific_root, self.context['scientific_root'])
        try:
            yield {'status': 'injected_observer_no_real_gradients'}
        finally:
            self.events.append('fixture_observer_exit')

    def validate(self, path, plan, preflight):
        self.events.append('fixture_validate_original_completion')
        self.assertEqual(path, self.request['training_run'])
        return copy.deepcopy(self.validation)

    def write_json(self, path, value):
        self.events.append('fixture_write:'+Path(path).name)
        with Path(path).open('x') as handle:
            json.dump(value, handle, sort_keys=True, allow_nan=False)
        self.written[str(path)] = copy.deepcopy(value)

    def sha(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def comparison_preflight(self, args):
        self.events.append('fixture_comparison_preflight')
        request = self.written[args.request]
        completion = self.written[self.request['completion_receipt']]
        self.assertEqual(request['training_execution_request'], self.context['training_args'].request)
        self.assertEqual(request['training_preflight_receipt'], completion['training_preflight_receipt'])
        self.assertEqual(completion['training_preflight_receipt_sha256'], self.sha(completion['training_preflight_receipt']))
        self.assertEqual(completion['execution_request_sha256'], self.preflight['request_sha256'])
        self.assertEqual(completion['runtime_receipt_sha256'], self.request['runtime_receipt_sha256'])
        self.assertEqual(completion['artifacts_sha256'], self.validation['artifacts_sha256'])
        self.assertEqual(completion['calibration'], self.validation['calibration'])
        self.assertEqual((completion['completed_steps'], completion['consumed_rows']), (733, 2932))
        self.assertTrue(completion['fixed_final_checkpoint'])
        self.assertTrue(completion['defer_heldout'])
        self.assertFalse(completion['resume_training'])
        self.assertFalse(completion['automatic_promotion'])
        return {'bindings': {'source_commit': child.SCIENCE_A,
            'plan_sha256': child.PLAN_SHA, 'freeze_receipt_sha256': child.FREEZE_SHA,
            'runtime': self.plan['runtime'], 'gpu_uuid': GPU, 'visible_devices': '3', 'device': 'cuda:0',
            'checkpoint_directory_sha256': {
                'released': self.plan['expected_initial_checkpoint']['directory_sha256'], 'adapted': '7'*64}}}

    def read_comparison_inputs(self, request, plan):
        self.events.append('fixture_materialize_handwritten_rows')
        return data_fixture()  # Invented CPU contract rows, no actual heldout bodies.

    def make_loader(self, plan, bindings, checkpoints, base, scientific_root, *, assert_owned):
        audits = []
        @contextmanager
        def loader(weight, phase):
            assert_owned()
            self.events.append('fixture_load:'+weight+'/'+phase)
            audits.append({'scope': 'oracle_cpu_logits_fixture', 'weight': weight, 'phase': phase})
            def predict(row):
                assert_owned()
                if phase == 'heldout':
                    self.assertIn('fixture_load:adapted/calibration', self.events)
                correct = row['target'].index(1.)
                return {'logits': [5. if i == correct else 0. for i in range(len(row['options']))],
                        'latency_seconds': .01, 'cuda_memory': dict(MEMORY)}
            yield runtime(plan, weight, phase), predict
        loader.audits = audits
        return loader

    def modules(self, **overrides):
        values = dict(verify_sources=self.verify_sources,
            driver=SimpleNamespace(prepare=self.prepare, translated_argv=self.translated,
                                   validate_completed_run=self.validate),
            trainer=SimpleNamespace(run=self.run_training),
            native=SimpleNamespace(observe_training=self.observe, make_loader=self.make_loader),
            comparator=SimpleNamespace(preflight=self.comparison_preflight,
                                       score_bundle=frozen_comparator.score_bundle),
            read_comparison_inputs=self.read_comparison_inputs, write_json=self.write_json, sha=self.sha)
        values.update(overrides)
        return child.CPUFixtureModules(**values)

    def test_complete_fixture_original_four_loads_twenty_two_journals_and_binding(self):
        result = child.run_cpu_fixture_pipeline(self.context, self.owner, self.modules())
        self.assertEqual(self.training_runs, 1)
        self.assertEqual(self.events[:3], ['fixture_owner_check', 'fixture_source_checker', 'fixture_owner_check'])
        self.assertLess(self.events.index('fixture_observer_exit'), self.events.index('fixture_validate_original_completion'))
        self.assertLess(self.events.index('fixture_validate_original_completion'), self.events.index('fixture_comparison_preflight'))
        self.assertEqual([event for event in self.events if event.startswith('fixture_load:')],
            ['fixture_load:released/calibration', 'fixture_load:adapted/calibration',
             'fixture_load:released/heldout', 'fixture_load:adapted/heldout'])
        manifest = result['fixture_comparison_manifest']
        self.assertEqual(len(manifest['journals']), 22)
        self.assertEqual(sum(j['count'] for j in manifest['journals'].values()), 4784)
        output = Path(self.request['comparison_output'])
        events = [json.loads(line) for line in (output/'events.jsonl').read_text().splitlines()]
        fits = [event['index'] for event in events if event['event'] == 'calibration_fitted']
        heldout_start = [event['index'] for event in events
                         if event['event'] == 'journal_started' and event['slice'] != 'calibration']
        self.assertEqual(len(fits), 2)
        self.assertLess(max(fits), min(heldout_start))
        summary = json.loads((output/'summary.json').read_text())
        self.assertEqual(len(summary['gates']), 4)
        self.assertEqual(summary['model_loads'], 4)
        self.assertFalse(result['execution_available'])
        self.assertFalse(result['resource_authority'])
        self.assertEqual(result['actual_training_runs'], 0)
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['provenance']['training_preflight_run_and_completion_validation'],
                         'injected_CPU_fixture')
        self.assertEqual(set(path.name for path in self.task.iterdir()),
                         {'cpu-preflight.json', 'training-completion.json', 'comparison'})
        self.assertEqual(self.written[str(self.metadata/'training-observation.json')]['status'],
                         'injected_observer_no_real_gradients')

    def test_actual_entries_refuse_before_files_paths_or_import_factories(self):
        with patch('builtins.open') as opened:
            with self.assertRaises(child.ScientificChildUnavailable):
                child.main(['--execute', '--request', '/untrusted/unreadable.json'])
            with self.assertRaises(child.ScientificChildUnavailable):
                child.load_production_modules({'ready': True, 'owner': self.owner})
            with self.assertRaises(child.ScientificChildUnavailable):
                child.execute_child({'execution_available': True})
        opened.assert_not_called()
        self.assertEqual(self.events, [])
        self.assertFalse(any(self.task.iterdir()))

    def test_owner_failure_precedes_all_path_and_source_callbacks(self):
        self.owner.valid = False
        with patch.object(child, 'check_prepared_layout') as layout:
            with self.assertRaisesRegex(RuntimeError, 'Fixture owner lost'):
                child.run_cpu_fixture_pipeline(self.context, self.owner, self.modules())
            layout.assert_not_called()
        self.assertEqual(self.events, ['fixture_owner_check'])

    def test_json_ready_flags_or_production_gpu_scope_cannot_unlock_fixture(self):
        with self.assertRaisesRegex(ValueError, 'owner.assert_owned'):
            child.run_cpu_fixture_pipeline(self.context, {'ready': True}, self.modules())
        bindings = dict(self.owner.bindings); bindings['resource_scope'] = 'gpu_lease'
        with self.assertRaisesRegex(ValueError, 'refuses production'):
            child.run_cpu_fixture_pipeline(self.context, FixtureOwner(bindings, self.events), self.modules())
        self.assertEqual(self.training_runs, 0)

    def test_source_root_declarations_and_owner_binding_fail_before_prepare(self):
        for field, value in (('native_root', self.context['scientific_root']),
                             ('freeze', self.context['native_root']+'/freeze.json'),
                             ('plan_sha256', '0'*64)):
            with self.subTest(field=field):
                context = self.context.copy(); context[field] = value
                with self.assertRaises(ValueError):
                    child.run_cpu_fixture_pipeline(context, self.owner, self.modules())
        self.assertNotIn('fixture_scientific_prepare', self.events)

    def test_additional_metadata_or_comparison_request_inside_task_refused(self):
        for name in ('metadata', 'request'):
            with self.subTest(name=name):
                context = self.context.copy()
                if name == 'metadata': context['metadata_directory'] = str(self.task/'extra')
                else:
                    context['comparison_args'] = copy.copy(context['comparison_args'])
                    context['comparison_args'].request = str(self.task/'extra-request.json')
                with self.assertRaisesRegex(ValueError, 'outside the scientific task'):
                    child.run_cpu_fixture_pipeline(context, self.owner, self.modules())
        self.assertFalse(self.written)

    def test_translated_argv_mismatch_or_current_stage_mismatch_stops_before_training(self):
        self.preflight['resolved_training_argv'] = ['forbidden_saved_argv']
        with self.assertRaisesRegex(ValueError, 'argv differs'):
            child.run_cpu_fixture_pipeline(self.context, self.owner, self.modules())
        self.preflight['resolved_training_argv'] = frozen_driver.translated_argv(self.plan, self.request)
        self.request['runtime_receipt_sha256'] = '9'*64
        with self.assertRaisesRegex(ValueError, 'current-stage'):
            child.run_cpu_fixture_pipeline(self.context, self.owner, self.modules())
        self.assertEqual(self.training_runs, 0)

    def test_training_failure_restores_observation_and_never_materializes_comparison(self):
        def failed_training(args):
            self.events.append('fixture_train_failed')
            raise RuntimeError('Injected original training failure')
        with self.assertRaisesRegex(RuntimeError, 'training failure'):
            child.run_cpu_fixture_pipeline(self.context, self.owner,
                self.modules(trainer=SimpleNamespace(run=failed_training)))
        self.assertIn('fixture_observer_exit', self.events)
        self.assertNotIn('fixture_validate_original_completion', self.events)
        self.assertNotIn('fixture_materialize_handwritten_rows', self.events)
        self.assertNotIn(self.request['completion_receipt'], self.written)

    def test_invalid_fixed_completion_does_not_write_success_wrapper_or_compare(self):
        for change in ('steps', 'artifacts', 'temperature', 'override_status'):
            with self.subTest(change=change):
                validation = copy.deepcopy(self.validation)
                if change == 'steps': validation['completed_steps'] = 732
                if change == 'artifacts': validation['artifacts_sha256'].pop('reload_check.jsonl')
                if change == 'temperature': validation['calibration']['temperature'] = float('nan')
                if change == 'override_status': validation['status'] = 'false_complete'
                with self.assertRaises(ValueError):
                    child._completion(self.request, self.plan, self.preflight, validation,
                                      self.context, self.owner.bindings, 'a'*64)
        self.assertFalse(self.written)

    def test_owner_loss_after_training_stops_before_validation_and_comparison(self):
        def training_then_lose(args):
            self.run_training(args)
            self.owner.valid = False
        with self.assertRaisesRegex(RuntimeError, 'owner lost'):
            child.run_cpu_fixture_pipeline(self.context, self.owner,
                self.modules(trainer=SimpleNamespace(run=training_then_lose)))
        self.assertEqual(self.training_runs, 1)
        self.assertNotIn('fixture_validate_original_completion', self.events)
        self.assertNotIn('fixture_materialize_handwritten_rows', self.events)

    def test_fixture_attempt_reuse_cannot_overwrite_original_preflight(self):
        path = self.task/'cpu-preflight.json'
        path.write_text('Existing consumed fixture bytes')
        with self.assertRaises(FileExistsError):
            child.run_cpu_fixture_pipeline(self.context, self.owner, self.modules())
        self.assertEqual(path.read_text(), 'Existing consumed fixture bytes')
        self.assertEqual(self.training_runs, 0)


if __name__ == '__main__':
    unittest.main()
