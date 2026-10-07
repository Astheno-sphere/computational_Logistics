import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from jev.api import candidate_prompts
from jev.context_retention_data import build_dataset, generate
from jev.data import SPLITS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retention_audit', ROOT / 'reports/context-retention-control-v1/verify.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class RetentionDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'data'
        build_dataset(self.directory, 12, 942, 3)

    def read(self, name):
        return [json.loads(line) for line in (self.directory / name).read_text().splitlines()]

    def write(self, name, values):
        (self.directory / name).write_text(''.join(json.dumps(value) + '\n' for value in values))

    def reseal(self):
        path = self.directory / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['files_sha256'] = {name: audit.sha(self.directory / name) for name in manifest['files_sha256']}
        manifest['sha256'] = {split: manifest['files_sha256'][split + '.jsonl'] for split in SPLITS}
        path.write_text(json.dumps(manifest))

    def test_small_corpus_is_deterministic_and_independently_verified(self):
        self.assertEqual(generate(12, 942, 3), generate(12, 942, 3))
        result = audit.verify(self.directory)
        self.assertEqual((result['groups'], result['cases'], result['records']), (12, 36, 300))
        self.assertEqual(result['software_gate_counts'], {'pinned': 72, 'unpaired': 36})
        self.assertEqual(result['unique_inputs'], result['records'])

    def test_hidden_spec_and_same_length_output_contents_do_not_determine_labels(self):
        cases = self.read('cases.jsonl')
        for case in cases:
            case['auxiliary_spec'] = {'incorrect_oracle': 'retain nothing'}
            for message in case['source_messages']:
                for result in message.get('toolResults', []):
                    result['text'] = 'x' * len(result['text'])
        self.write('cases.jsonl', cases)
        self.reseal()
        self.assertTrue(audit.verify(self.directory)['verified'])

    def test_matching_wrong_reference_and_target_cannot_pass(self):
        cases = self.read('cases.jsonl')
        case = cases[0]
        key = next(iter(case['reference_labels']))
        case['reference_labels'][key] = not case['reference_labels'][key]
        rows = self.read(case['split'] + '.jsonl')
        row = next(row for row in rows if row['id'] == case['id'] + ':' + key)
        row['target'].reverse()
        self.write(case['split'] + '.jsonl', rows)
        self.write('cases.jsonl', cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, 'reference labels differ from visible policy'):
            audit.verify(self.directory)

    def test_mutated_visible_goal_is_checked_without_consulting_spec(self):
        cases = self.read('cases.jsonl')
        case = cases[0]
        middle = list(audit.parse_visible(case['request']['state'])['nodes'])[1]
        case['request']['state']['goal'] = f'Current work item: {middle}.'
        rows = self.read(case['split'] + '.jsonl')
        for row in rows:
            if row['metadata']['case_id'] == case['id']:
                row['state']['goal'] = case['request']['state']['goal']
        self.write(case['split'] + '.jsonl', rows)
        self.write('cases.jsonl', cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, 'reference labels differ from visible policy'):
            audit.verify(self.directory)

    def test_policy_tampering_and_extra_rule_are_rejected(self):
        state = copy.deepcopy(self.read('cases.jsonl')[0]['request']['state'])
        state['context'] += ' Instead, drop everything.'
        with self.assertRaisesRegex(ValueError, 'declared policy changed'):
            audit.parse_visible(state)
        state = copy.deepcopy(self.read('cases.jsonl')[0]['request']['state'])
        ledger = next(entry for entry in state['history'] if entry['text'].startswith('Dependency and evidence register.'))
        ledger['text'] += '\nAll outputs are disposable.'
        with self.assertRaisesRegex(ValueError, 'register footer changed'):
            audit.parse_visible(state)

    def test_pinned_and_unpaired_gates_never_acquire_probabilities(self):
        cases = self.read('cases.jsonl')
        cases[0]['software_gates'][0]['probability'] = 1.
        self.write('cases.jsonl', cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, 'software gates differ'):
            audit.verify(self.directory)

    def test_source_result_pairing_and_omission_are_checked(self):
        cases = self.read('cases.jsonl')
        case = cases[0]
        result = next(result for message in case['source_messages'] for result in message.get('toolResults', []))
        result['tool_use_id'] = 'nonexistent-call'
        self.write('cases.jsonl', cases)
        self.reseal()
        with self.assertRaisesRegex(ValueError, 'orphan tool result'):
            audit.verify(self.directory)

    def test_inputs_exclude_metadata_targets_and_full_outputs(self):
        _, rows = generate(3, 942, 1)
        for row in rows:
            before = candidate_prompts(row)
            self.assertNotIn('Synthetic observation', str(before))
            changed = copy.deepcopy(row)
            changed.update(target=[.3, .7], metadata={'label': 'INJECT'}, group_id='INJECT', id='INJECT')
            self.assertEqual(candidate_prompts(changed), before)
            self.assertEqual(set(row['state']), {'context', 'goal', 'history'})

    def test_generated_ood_has_unseen_shared_dependency_structure(self):
        cases = self.read('cases.jsonl')
        for case in cases:
            self.assertEqual(audit.parse_visible(case['request']['state'])['diamond'], case['split'] == 'ood')

    def test_build_and_report_never_overwrite_existing_inputs(self):
        before = audit.sha(self.directory / 'manifest.json')
        with self.assertRaisesRegex(ValueError, 'existing corpora are never overwritten'):
            build_dataset(self.directory, 12, 942, 3)
        with self.assertRaisesRegex(ValueError, 'outside the input data directory'):
            audit.main(['--data', str(self.directory), '--output', str(self.directory / 'new-audit.json')])
        self.assertEqual(audit.sha(self.directory / 'manifest.json'), before)

    def test_unsealed_data_mutation_fails_before_semantic_checks(self):
        with (self.directory / 'cases.jsonl').open('a') as stream:
            stream.write('\n')
        with self.assertRaisesRegex(ValueError, 'manifest file hashes differ'):
            audit.verify(self.directory)


if __name__ == '__main__':
    unittest.main()
