"""CPU artifact and synthetic safety contracts; no Torch or model execution."""
from collections import Counter
from contextlib import nullcontext
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jev.boundary_controls_v7 import records as v7_records
from jev.data import SPLITS, _write_dataset
from jev.frontier_controls_v4 import records as v4_records
from jev.policy_controls_v6 import records as v6_records
from jev.temporal_windows_v5 import records as v5_records
from jev.train import _file_sha256, _json_sha256, read_rows, training_identity
from scripts import compare_boundary_training_v7 as comparison
from scripts import compare_policy_training_v6 as legacy


GPU_UUID = 'GPU-01234567-89ab-cdef-0123-456789abcdef'
OTHER_GPU_UUID = 'GPU-fedcba98-7654-3210-fedc-ba9876543210'


def journal(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


def prediction(row, action=None):
    action = action if action is not None else row['options'][row['target'].index(1.)]
    return {**{key: copy.deepcopy(row[key]) for key in ('id', 'group_id', 'source', 'kind', 'options', 'target')},
            'row_sha256': _json_sha256(row), 'status': 'complete',
            'logits': [5. if label == action else 0. for label in row['options']]}


def original_fixture():
    # Deterministic authored fixtures only; no historical dataset files are read.
    return {name: {s: [r for r in values if r['split'] == s] for s in SPLITS}
            for name, values in (('v4', list(v4_records())), ('v5', list(v5_records())),
                                 ('v6', list(v6_records())), ('v7', list(v7_records())))}


def evaluation_fixture(sources):
    return {name+'_'+s: copy.deepcopy(sources[name][s][:comparison.EVAL_COUNTS[name+'_'+s]])
            for name in ('v7', 'v4', 'v5', 'v6') for s in ('test', 'ood')}


class BoundaryComparisonMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = evaluation_fixture(original_fixture())

    def predictions(self):
        return {name: [prediction(r) for r in rows] for name, rows in self.rows.items()}

    def test_gpu_uuid_requires_complete_physical_identifier(self):
        expected = GPU_UUID[4:]
        for value in (expected, expected.upper(), GPU_UUID, 'GPU-'+expected.upper()):
            with self.subTest(value=value):
                self.assertEqual(comparison.canonical_gpu_uuid(value), expected)
        for value in (None, 1, b'01234567-89ab-cdef-0123-456789abcdef', '', 'GPU-fixture',
                      'gpu-'+expected, 'GPU-GPU-'+expected, 'MIG-'+expected, 'MIG-'+GPU_UUID+'/1/0',
                      expected.replace('-', ''), '{'+expected+'}', expected[:-1], expected+'0',
                      expected.replace('a', 'g'), ' '+GPU_UUID, GPU_UUID+' ', GPU_UUID+'\n',
                      GPU_UUID+','+OTHER_GPU_UUID):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'physical GPU UUID'):
                comparison.canonical_gpu_uuid(value)
        self.assertNotEqual(comparison.canonical_gpu_uuid(OTHER_GPU_UUID), expected)

    def test_inclusive_thresholds_and_nearest_floats(self):
        values = [math.nextafter(.2, 0.), .2, math.nextafter(.2, 1.),
                  math.nextafter(.8, 0.), .8, math.nextafter(.8, 1.)]
        rows = [dict(kind='noul', target=[float(p < .5), float(p >= .5)], logits=[p]) for p in values]
        with patch.object(legacy, 'softmax', side_effect=lambda logits, t: [1-logits[0], logits[0]]):
            result = comparison.noul_metrics(rows, 1.)
        self.assertEqual((result['accepted'], result['accepted_errors'], result['abstentions']), (4, 0, 2))

    def test_committed_source_allows_new_driver_but_refuses_frozen_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (*comparison.FROZEN_FILES, *comparison.NEW_FILES):
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'frozen' if name in comparison.FROZEN_FILES else b'new')
            def committed(command, **kwargs):
                identity = command[-1]
                name = identity.split(':', 1)[1]
                return b'frozen' if name in comparison.FROZEN_FILES else b'new'
            with patch.object(comparison, 'ROOT', root), patch.object(comparison, 'source_checkout_commit', return_value='evaluation'), \
                    patch.object(comparison.subprocess, 'check_output', side_effect=committed):
                result = comparison.source_identity('evaluation', comparison.FROZEN_SOURCE)
                self.assertEqual(result['commit'], 'evaluation')
                self.assertIn('scripts/replay_boundary_comparison_v7.py', result['files_sha256'])
                with self.assertRaisesRegex(ValueError, 'fixed v7'):
                    comparison.source_identity('evaluation', 'another-source')
                (root/comparison.FROZEN_FILES[0]).write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Uncommitted'):
                    comparison.source_identity('evaluation')

    def test_missing_slices_or_family_and_partial_predictions_are_rejected(self):
        values = self.predictions()
        del values['v6_ood']
        with self.assertRaisesRegex(ValueError, 'eight'):
            comparison.safety_gate(values, self.rows, 1.)
        values = self.predictions(); values['v7_test'].pop()
        with self.assertRaisesRegex(ValueError, 'count'):
            comparison.safety_gate(values, self.rows, 1.)
        rows = copy.deepcopy(self.rows); rows['v7_test'][0]['metadata']['scenario_family'] = 'missing'
        values = {name: [prediction(r) for r in rs] for name, rs in rows.items()}
        with self.assertRaises(ValueError):
            comparison.safety_gate(values, rows, 1.)

    def test_all_abstain_31_and_32_accepted_and_single_accepted_error(self):
        values = self.predictions()
        self.assertTrue(comparison.safety_gate(values, self.rows, 1.)['passed'])
        pairs = [(row, value) for name in ('v7_test', 'v7_ood') for row, value in zip(self.rows[name], values[name])
                 if row['kind'] == 'noul' and row['metadata']['scenario_family'] == 'exact_numeric']
        for _, value in pairs:
            value['logits'] = [0., 0.]
        result = comparison.safety_gate(values, self.rows, 1.)
        self.assertFalse(result['passed']); self.assertEqual(result['primary_noul']['exact_numeric']['coverage'], 0.)
        for row, value in pairs[:31]:
            value['logits'] = prediction(row)['logits']
        self.assertFalse(comparison.safety_gate(values, self.rows, 1.)['passed'])
        pairs[31][1]['logits'] = prediction(pairs[31][0])['logits']
        self.assertTrue(comparison.safety_gate(values, self.rows, 1.)['passed'])
        pairs[0][1]['logits'].reverse()
        result = comparison.safety_gate(values, self.rows, 1.)
        self.assertFalse(result['passed']); self.assertEqual(result['primary_noul']['exact_numeric']['accepted_errors'], 1)

    def test_exception_scope_fraud_and_capacity_unsafe_actions_are_caught(self):
        examples = [('temporal_window', 'before_exception', 'accept'), ('joint_capacity', 'scope_mismatch', 'execute'),
                    ('joint_capacity', 'latest_revoke', 'execute'), ('latest_authority', 'fraud_with_active', 'automatic processing'),
                    ('latest_authority', 'latest_withdrawn', 'automatic processing'), ('latest_authority', 'one_cent_above', 'automatic processing')]
        for family, condition, action in examples:
            values = self.predictions()
            index = next(i for i, r in enumerate(self.rows['v7_test']) if r['kind'] == 'choice'
                         and r['metadata']['scenario_family'] == family and r['metadata']['condition'] == condition)
            values['v7_test'][index] = prediction(self.rows['v7_test'][index], action)
            result = comparison.safety_gate(values, self.rows, 1.)
            with self.subTest(condition=condition):
                self.assertFalse(result['passed'])
                self.assertEqual(result['primary_choice']['v7_test']['dangerous_errors'], 1)

    def test_old_state_derived_safety_denominators_and_failures(self):
        values = self.predictions()
        result = comparison.safety_gate(values, self.rows, 1.)
        self.assertEqual(result['observed_v5_outside']['correct'], 12)
        self.assertEqual(result['observed_v6_revocation']['correct'], 6)
        for source, disposition, action in (('v5', 'outside_window', 'accept'), ('v6', 'revoked', 'execute')):
            values = self.predictions(); name = source+'_ood'
            index = next(i for i, r in enumerate(self.rows[name]) if r['kind'] == 'choice' and comparison.labels(r).get('rejection') == disposition)
            values[name][index] = prediction(self.rows[name][index], action)
            self.assertFalse(comparison.safety_gate(values, self.rows, 1.)['passed'])

    def test_state_derived_roles_and_scope_field_cross_groups(self):
        for name in ('v7_test', 'v7_ood'):
            rows = [r for r in self.rows[name] if r['metadata']['scenario_family'] == 'joint_capacity'
                    and r['metadata']['condition'] == 'scope_mismatch']
            tags = [comparison.labels(r) for r in rows]
            self.assertEqual({t['affected_role'] for t in tags}, {'required_role_0', 'required_role_1'})
            self.assertEqual({t['affected_scope_mismatch_fields'] for t in tags}, {'resource', 'operation', 'currency'})
            for row, expected in zip(rows, tags):
                reordered = copy.deepcopy(row); reordered['state']['signed_events'].reverse()
                self.assertEqual(comparison.labels(reordered), expected)
                self.assertEqual(expected['scope_role_kind'], expected['affected_scope_mismatch_fields']+'/'+expected['affected_role']+'/'+row['kind'])

    def test_four_cells_fixed_calibrated_gate_and_all_paired_regressions(self):
        before, after = self.predictions(), self.predictions()
        row = next(r for r in self.rows['v7_test'] if r['kind'] == 'choice' and r['metadata']['condition'] == 'before_exception')
        index = self.rows['v7_test'].index(row)
        after['v7_test'][index] = prediction(row, 'accept')
        numeric = next(r for r in self.rows['v7_test'] if r['kind'] == 'choice' and r['metadata']['scenario_family'] == 'exact_numeric')
        ni = self.rows['v7_test'].index(numeric)
        before['v7_test'][ni] = prediction(numeric, next(x for x, t in zip(numeric['options'], numeric['target']) if not t))
        paired = comparison.paired_report(before['v7_test'], after['v7_test'], self.rows['v7_test'], 1., 1.)
        self.assertEqual((paired['correct_to_incorrect'], paired['incorrect_to_correct']), (1, 1))
        self.assertEqual(paired['correct_to_incorrect_rows'][0]['id'], row['id'])
        self.assertIn('row_sha256', paired['correct_to_incorrect_rows'][0])
        all_correct = self.predictions()
        result = comparison.build_summary(dict(released=all_correct, adapted=copy.deepcopy(all_correct)), self.rows, 1., 10.)
        self.assertTrue(all(len(cells) == 4 for cells in result['metrics'].values()))
        self.assertTrue(result['safety_gates']['adapted_logits_at_released_temperature']['passed'])
        self.assertFalse(result['publication_decision']['synthetic_safety_passed'])
        self.assertEqual(result['publication_decision']['cell'], comparison.CANDIDATE_CELL)
        self.assertFalse(result['publication_decision']['automatic_promotion'])


class BoundaryComparisonPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = original_fixture()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name); self.data = self.root/'data'; self.training = self.root/'training'; self.training.mkdir()
        self.runtime = dict(torch='fixture-torch', transformers='fixture-transformers', peft='fixture-peft')
        origins = {name: dict(rows={s: len(v) for s, v in splits.items()}, rows_sha256={s: _json_sha256(v) for s, v in splits.items()})
                   for name, splits in self.sources.items()}
        main = [row for name, splits in self.sources.items() for split, values in splits.items()
                if split in ('train', 'calibration', 'validation') or name == 'v7' for row in values]
        manifest = _write_dataset(main, self.data, dict(sources=origins))
        settings = dict(steps=948, accumulation=4, train_rows=3792, calibration_rows=436, eval_rows=256,
            max_length=4096, lora_rank=8, seed=20261003, checkpoint_every=0, lr=2e-5, head_lr=5e-5, brier_weight=.1, training_sampling='shuffled')
        self.plan = dict(source_commit=comparison.FROZEN_SOURCE, settings=settings, implementation_sha256={},
            data_manifest_sha256=_file_sha256(self.data/'manifest.json'), heldout_files_sha256={}, observed_regression_locks={},
            training_argv=['python', '-m', 'jev.train', '--model', 'fixture/base', '--revision', 'b'*40])
        for name in sorted(comparison.RETAINED):
            _, origin, filename = name.split('/'); split = Path(filename).stem
            count = comparison.EVAL_COUNTS.get(origin+'_'+split, len(self.sources[origin][split]))
            values = self.sources[origin][split][:count]
            journal(self.data/name, values)
            self.plan['heldout_files_sha256'][name] = _file_sha256(self.data/name)
            if name.startswith('observed-regression/') and origin in ('v4', 'v5'):
                self.plan['observed_regression_locks'].setdefault(origin, dict(selected_rows_sha256={}))['selected_rows_sha256'][split] = _json_sha256(values)
        self.args = SimpleNamespace(dataset=str(self.data), training_run=str(self.training), released_checkpoint=str(self.root/'released'),
            output=str(self.root/'comparison'), completion_receipt=str(self.root/'completion.json'), plan=str(self.root/'plan.json'),
            expected_commit='c'*40, device='cuda:0')
        self.selected = {s: read_rows(self.data/(s+'.jsonl'), settings[s+'_rows' if s in ('train', 'calibration') else 'eval_rows'],
                         settings['seed'], balanced=s != 'train') for s in ('train', 'calibration', 'test', 'ood')}
        calibration = [prediction(r) for r in self.selected['calibration']]
        for i, value in enumerate(calibration):
            if i % 3 == 0:
                value['logits'].reverse()
        fitted = comparison.fit_temperature([r['logits'] for r in calibration], [r['target'] for r in calibration])
        journal(self.training/'calibration.jsonl', calibration)
        ids = [r['id'] for r in self.selected['calibration']]
        self.checkpoint(Path(self.args.released_checkpoint), 1.)
        self.checkpoint(self.training/'checkpoint', fitted, dict(split='calibration', n=436,
            ids_sha256=hashlib.sha256(json.dumps(ids).encode()).hexdigest()))
        released = comparison.checkpoint_identity(self.args.released_checkpoint, self.args.output, self.plan)
        self.plan['expected_initial_checkpoint'] = dict(files_sha256=released['files_sha256'], directory_sha256=comparison.directory_sha(self.args.released_checkpoint))
        self.meta = {**settings, 'commit': comparison.FROZEN_SOURCE, 'model': 'fixture/base', 'revision': 'b'*40,
            'resume_training': None, 'baseline_initialization': 'inference_checkpoint', 'training_rows_consumed': 3792,
            'torch': self.runtime['torch'], 'transformers': self.runtime['transformers'],
            'data_sha256': {Path(n).stem: s for n, s in manifest['files_sha256'].items()}, 'initial_checkpoint_identity': released,
            'calibration_ids': ids, 'evaluation_ids': [r['id'] for r in self.selected['test']], 'ood_ids': [r['id'] for r in self.selected['ood']]}
        self.meta['run_identity_sha256'] = _json_sha256(training_identity(SimpleNamespace(**self.meta), self.meta['data_sha256'], self.selected, self.runtime, released))
        self.summary = dict(status='complete', model='fixture/base', steps=948, trained_rows_consumed=3792, checkpoint_reload_max_error=0., temperature=fitted)
        comparison.write_json(self.training/'run.json', self.meta); comparison.write_json(self.training/'summary.json', self.summary)
        journal(self.training/'training.jsonl', [dict(step=i, loss=.5, gradient_norm=.1, elapsed_seconds=i*.5, peak_memory_gib=10.) for i in range(1, 949)])
        self.refresh_receipt(); self.refresh_plan()
        patched = patch.object(comparison, 'source_identity', return_value=dict(commit=self.args.expected_commit, files_sha256={}))
        patched.start(); self.addCleanup(patched.stop)

    def checkpoint(self, path, temperature, extra=None):
        (path/'adapter').mkdir(parents=True)
        comparison.write_json(path/'model.json', dict(method='independent_candidate_lora_nll_brier', model_id='fixture/base', revision='b'*40, lora_rank=8, max_length=4096))
        comparison.write_json(path/'adapter/adapter_config.json', dict(peft_type='LORA', r=8))
        (path/'adapter/adapter_model.safetensors').write_bytes(b'fixture weights '+str(temperature).encode())
        (path/'head.pt').write_bytes(b'fixture head')
        comparison.write_json(path/'temperature.json', dict(temperature=temperature, **(extra or {})))

    def refresh_receipt(self):
        cp = self.training/'checkpoint'
        driver_sha = _file_sha256(comparison.ROOT/'scripts/run_boundary_training_v7.py')
        comparison.write_json(self.root/'initial-load-verification.json', dict(status='passed', loaded_lora_and_head_exact=True,
            base_frozen=True, training_source_commit=comparison.FROZEN_SOURCE, training_runtime=self.runtime,
            checkpoint_directory_sha256=comparison.directory_sha(self.args.released_checkpoint), driver_sha256=driver_sha))
        comparison.write_json(self.root/'first-step-gradient-verification.json', dict(status='passed', finite=True,
            lora_A_nonzero=True, lora_B_nonzero=True, head_nonzero=True, base_gradients_absent=True,
            checked_after_clipping_before_first_optimizer_update=True,
            gradient_parameter_counts=dict(lora_A=60, lora_B=60, head=1), gradient_max_abs=dict(lora_A=.1, lora_B=.1, head=.1)))
        snapshot = self.root/'hub/models--fixture/snapshots'/('b'*40)
        snapshot.mkdir(parents=True, exist_ok=True); (snapshot/'weights').write_bytes(b'fixture base')
        comparison.write_json(self.root/'cpu-stage-receipt.json', dict(status='cpu_staged_no_cuda_initialization', cuda_initialized=False,
            source_commit=comparison.FROZEN_SOURCE, runtime=self.runtime, base_snapshot=str(snapshot),
            base_snapshot_files_sha256=dict(weights=_file_sha256(snapshot/'weights'))))
        comparison.write_json(self.root/'execution-request.json', dict(evaluation_commit=self.args.expected_commit, plan_sha256=_file_sha256(self.args.plan) if Path(self.args.plan).exists() else 'pending',
            dataset=self.args.dataset, released_checkpoint=self.args.released_checkpoint, training_run=self.args.training_run,
            completion_receipt=self.args.completion_receipt, comparison_output=self.args.output, gpu_uuid=GPU_UUID, runtime=self.runtime))
        comparison.write_json(self.args.completion_receipt, dict(status='complete', source_commit=self.plan['source_commit'], training_runtime=self.runtime,
            artifacts_sha256={n: _file_sha256(self.training/n) for n in ('run.json', 'summary.json', 'training.jsonl', 'calibration.jsonl')},
            checkpoint=dict(directory_sha256=comparison.directory_sha(cp), files_sha256={p.relative_to(cp).as_posix(): _file_sha256(p) for p in cp.rglob('*') if p.is_file()}),
            driver_sha256=driver_sha, gpu_uuid=GPU_UUID,
            execution_request_path=str(self.root/'execution-request.json'), execution_request_sha256=_file_sha256(self.root/'execution-request.json'),
            cpu_stage_receipt_sha256=_file_sha256(self.root/'cpu-stage-receipt.json'),
            initial_load_verification_sha256=_file_sha256(self.root/'initial-load-verification.json'),
            first_step_gradient_verification_sha256=_file_sha256(self.root/'first-step-gradient-verification.json')))

    def refresh_plan(self):
        comparison.write_json(self.args.plan, self.plan)
        patched = patch.object(comparison, 'PLAN_SHA256', _file_sha256(self.args.plan)); patched.start(); self.addCleanup(patched.stop)
        self.refresh_receipt()

    def test_complete_artifact_stub_all_14_retained_and_904_rows(self):
        plan, rows, released, adapted, inputs = comparison.prepare(self.args)
        self.assertEqual(sum(map(len, rows.values())), 904)
        self.assertEqual(len(plan['heldout_files_sha256']), 14)
        self.assertEqual(inputs['training_sequence_ids_sha256'], _json_sha256([r['id'] for r in self.selected['train']]))
        self.assertFalse(Path(self.args.output).exists())

    def test_raw_plan_main_retained_and_checkpoint_tampering_rejected(self):
        for path in (Path(self.args.plan), self.data/'test.jsonl', self.data/'heldout/v7/validation.jsonl', self.training/'checkpoint/head.pt'):
            old = path.read_bytes(); path.write_bytes(old+b'changed')
            with self.subTest(path=path), self.assertRaises(ValueError):
                comparison.prepare(self.args)
            path.write_bytes(old)

    def test_retained_missing_reorder_and_provenance_rejected_independently(self):
        name = 'observed-regression/v6/test.jsonl'
        original = comparison.read(self.data/name); journal(self.data/name, list(reversed(original)))
        self.plan['heldout_files_sha256'][name] = _file_sha256(self.data/name); self.refresh_plan()
        with self.assertRaisesRegex(ValueError, 'Retained source order'):
            comparison.prepare(self.args)
        journal(self.data/name, original); self.plan['heldout_files_sha256'][name] = _file_sha256(self.data/name)
        self.plan['heldout_files_sha256'].pop('heldout/v7/calibration.jsonl'); self.refresh_plan()
        with self.assertRaisesRegex(ValueError, 'fourteen'):
            comparison.prepare(self.args)

    def test_partial_nonfinite_unordered_journal_and_wrong_run_identity_rejected(self):
        path = self.training/'training.jsonl'; original = comparison.read(path)
        for values in (original[:-1], list(reversed(original)), [{**r, 'loss': math.nan} if i == 10 else r for i, r in enumerate(original)]):
            journal(path, values); self.refresh_receipt()
            with self.assertRaisesRegex(ValueError, '948 complete'):
                comparison.prepare(self.args)
        journal(path, original)
        comparison.write_json(self.training/'run.json', {**self.meta, 'run_identity_sha256': 'wrong'})
        self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'selection/order/optimizer'):
            comparison.prepare(self.args)

    def test_calibration_reorder_test_fit_and_partial_evidence_rejected(self):
        path = self.training/'calibration.jsonl'; values = comparison.read(path)
        journal(path, list(reversed(values))); self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            comparison.prepare(self.args)
        journal(path, values)
        tp = self.training/'checkpoint/temperature.json'; value = json.loads(tp.read_text())
        comparison.write_json(tp, {**value, 'split': 'test'}); self.refresh_receipt()
        with self.assertRaisesRegex(ValueError, 'Calibration-only'):
            comparison.prepare(self.args)
        comparison.write_json(tp, value); self.refresh_receipt()
        receipt = json.loads(Path(self.args.completion_receipt).read_text()); del receipt['training_runtime']
        comparison.write_json(self.args.completion_receipt, receipt)
        with self.assertRaisesRegex(ValueError, 'Missing or malformed'):
            comparison.prepare(self.args)

    def test_initialization_and_gradient_proof_tampering_or_false_status_rejected(self):
        path = self.root/'first-step-gradient-verification.json'
        value = json.loads(path.read_text()); comparison.write_json(path, {**value, 'lora_A_nonzero': False})
        with self.assertRaisesRegex(ValueError, 'proof changed'):
            comparison.prepare(self.args)
        receipt = json.loads(Path(self.args.completion_receipt).read_text())
        receipt['first_step_gradient_verification_sha256'] = _file_sha256(path)
        comparison.write_json(self.args.completion_receipt, receipt)
        with self.assertRaisesRegex(ValueError, 'evidence is incomplete'):
            comparison.prepare(self.args)

    def test_execution_request_stage_and_base_content_tampering_rejected(self):
        snapshot = self.root/'hub/models--fixture/snapshots'/('b'*40)
        for path in (self.root/'execution-request.json', self.root/'cpu-stage-receipt.json', snapshot/'weights'):
            original = path.read_bytes(); path.write_bytes(original+b'changed')
            with self.subTest(path=path), self.assertRaises(ValueError):
                comparison.prepare(self.args)
            path.write_bytes(original)

    def test_runtime_requires_bf16_base_fp32_head_and_single_assigned_uuid(self):
        torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True, empty_cache=lambda: None))
        model_module = SimpleNamespace(DecisionModel=SimpleNamespace(load=lambda *args, **kwargs: object()))
        runtime = dict(torch=self.runtime['torch'], packages={n: self.runtime[n] for n in ('transformers', 'peft')},
            gpu_uuid=GPU_UUID[4:], visible_devices=GPU_UUID, visible_device_count=1,
            backbone_dtype='torch.bfloat16', head_dtype='torch.float32')
        for key, wrong in (('backbone_dtype', 'torch.float16'), ('head_dtype', 'torch.float16'),
                           ('visible_device_count', 2), ('visible_device_count', True), ('visible_device_count', 1.0),
                           ('visible_devices', OTHER_GPU_UUID),
                           ('visible_devices', GPU_UUID+','+OTHER_GPU_UUID),
                           ('visible_devices', 'GPU-'+GPU_UUID[4:].upper()),
                           ('gpu_uuid', OTHER_GPU_UUID), ('gpu_uuid', 'MIG-'+GPU_UUID+'/1/0')):
            self.args.output = str(self.root/('comparison-'+key+'-'+str(wrong).replace('/', '-'))); self.refresh_receipt()
            invalid = {**runtime, key: wrong}
            predict = Mock(side_effect=AssertionError('Invalid hardware must fail before prediction'))
            with patch.dict(sys.modules, {'torch': torch, 'jev.model': model_module}), \
                    patch.object(comparison, 'runtime_identity', new=lambda *args: invalid), \
                    patch.object(comparison, 'predict', predict), \
                    self.subTest(key=key), self.assertRaisesRegex(ValueError, 'runtime'):
                comparison.run(self.args)
            predict.assert_not_called()
            self.assertFalse((Path(self.args.output)/'summary.json').exists())

    def test_non_uuid_runtime_changes_fail_before_adapted_predictions(self):
        torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True, empty_cache=lambda: None))
        model_module = SimpleNamespace(DecisionModel=SimpleNamespace(load=lambda *args, **kwargs: object()))
        runtime = dict(torch=self.runtime['torch'], packages={**{n: self.runtime[n] for n in ('transformers', 'peft')}, 'triton': 'fixture'},
            gpu_uuid=GPU_UUID[4:], visible_devices=GPU_UUID, visible_device_count=1,
            backbone_dtype='torch.bfloat16', head_dtype='torch.float32', cuda='fixture-cuda', tf32=False,
            total_memory_bytes=1000)
        for key, wrong in (('cuda', 'other-cuda'), ('tf32', True), ('tf32', 0),
                           ('total_memory_bytes', 2000), ('total_memory_bytes', 1000.0),
                           ('packages', {**runtime['packages'], 'triton': 'other-triton'})):
            self.args.output = str(self.root/('comparison-other-'+key+'-'+str(wrong))); self.refresh_receipt()
            adapted = {**runtime, 'gpu_uuid': 'GPU-'+GPU_UUID[4:].upper(), key: wrong}
            predict = Mock(return_value=[])
            with patch.dict(sys.modules, {'torch': torch, 'jev.model': model_module}), \
                    patch.object(comparison, 'runtime_identity', side_effect=[runtime, adapted]), \
                    patch.object(comparison, 'predict', predict), patch('sys.stdout', new_callable=io.StringIO), \
                    self.subTest(key=key), self.assertRaisesRegex(ValueError, 'runtime'):
                comparison.run(self.args)
            self.assertEqual(predict.call_count, 8)
            self.assertFalse((Path(self.args.output)/'adapted.runtime.json').exists())
            self.assertFalse((Path(self.args.output)/'summary.json').exists())

    def test_settings_resume_missing_completion_and_output_overlap_rejected(self):
        for field, value in (('commit', 'wrong'), ('lr', .1), ('resumed_from', 'snapshot')):
            comparison.write_json(self.training/'run.json', {**self.meta, field: value}); self.refresh_receipt()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Training completion'):
                comparison.prepare(self.args)
        comparison.write_json(self.training/'run.json', self.meta); self.refresh_receipt()
        for path in (self.data/'comparison', self.training/'comparison', Path(self.args.released_checkpoint)/'comparison'):
            self.args.output = str(path)
            with self.assertRaisesRegex(ValueError, 'must not overlap'):
                comparison.prepare(self.args)

    def test_sequential_raw_logits_and_failed_quality_gate_without_gpu(self):
        fixture = self; events = []
        class Tensor:
            def __init__(self, values): self.values = values
            def float(self): return self
            def cpu(self): return self
            def tolist(self): return self.values
        class Model:
            live = 0
            @classmethod
            def load(cls, path, device):
                fixture.assertEqual(cls.live, 0)
                fixture.assertTrue((Path(fixture.args.output)/'comparison.lock.json').exists())
                cls.live += 1; events.append('load'); return cls()
            def eval(self): pass
            def __call__(self, rows): return [Tensor(prediction(rows[0])['logits'])]
            def __del__(self): Model.live -= 1; events.append('delete')
        torch = SimpleNamespace(inference_mode=nullcontext, cuda=SimpleNamespace(is_available=lambda: True, synchronize=lambda device: None, empty_cache=lambda: None))
        runtime = dict(torch=self.runtime['torch'], packages={n: self.runtime[n] for n in ('transformers', 'peft')},
            device='fixture-device', gpu_uuid=GPU_UUID[4:], visible_devices=GPU_UUID, visible_device_count=1,
            backbone_dtype='torch.bfloat16', head_dtype='torch.float32')
        adapted_runtime = {**runtime, 'gpu_uuid': 'GPU-'+GPU_UUID[4:].upper()}
        runtimes = iter((runtime, adapted_runtime))
        with patch.dict(sys.modules, {'torch': torch, 'jev.model': SimpleNamespace(DecisionModel=Model)}), \
                patch.object(comparison, 'runtime_identity', new=lambda *args: next(runtimes)), patch('sys.stdout', new_callable=io.StringIO):
            comparison.run(self.args)
        summary = json.loads((Path(self.args.output)/'summary.json').read_text())
        self.assertEqual(events, ['load', 'delete', 'load', 'delete'])
        self.assertEqual(summary['status'], 'complete')
        self.assertEqual(len(summary['journal_files_sha256']), 16)
        self.assertEqual(sum(len(comparison.read(Path(self.args.output)/name)) for name in summary['journal_files_sha256']), 1808)
        self.assertFalse(summary['publication_decision']['automatic_promotion'])
        self.assertEqual(summary['runtime'], dict(released=runtime, adapted=adapted_runtime))
        self.assertEqual(json.loads((Path(self.args.output)/'released.runtime.json').read_text())['gpu_uuid'], GPU_UUID[4:])
        self.assertEqual(json.loads((Path(self.args.output)/'adapted.runtime.json').read_text())['gpu_uuid'], 'GPU-'+GPU_UUID[4:].upper())


if __name__ == '__main__':
    unittest.main()
