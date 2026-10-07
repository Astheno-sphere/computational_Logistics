import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from jev.case_sponsor_segments import generate, build_dataset, request_for
from jev.api import compile_request, candidate_prompts
from jev.data import validate_records
from scripts.audit_sponsor_segments import audit, classify_visible_segment


class SponsorSegmentTest(unittest.TestCase):
    def test_generated_contract_and_labels(self):
        cases, rows = generate(groups=30, ood_groups=6)
        self.assertEqual(len(rows), 30 * 3 * 9)
        self.assertEqual(validate_records(rows)['groups'], 30)
        for case in cases:
            for segment in case['request']['state']['segments']:
                self.assertEqual(classify_visible_segment(segment['text']), case['reference_by_segment'][segment['id']])
        self.assertEqual({key for row in rows for key, p in zip(row['options'], row['target']) if p == 1}, set(rows[0]['options']))

    def test_financial_evidence_and_ownership_counterexamples(self):
        self.assertEqual(classify_visible_segment('We purchased the Example product with our own funds and have received no compensation for this evaluation.'), 'content')
        self.assertEqual(classify_visible_segment('Example is our own store, owned by this channel. Please visit it.'), 'self_promo')
        self.assertEqual(classify_visible_segment('Example is a third-party sponsor paying for this message.'), 'sponsor')
        self.assertEqual(classify_visible_segment('This might be a commercial relationship with Example; it has not been confirmed.'), 'other')
        with self.assertRaises(ValueError):
            classify_visible_segment('Brand. Offer. Code.')

    def test_marker_timestamp_and_neighbour_not_label_oracle(self):
        cases, _ = generate(groups=5, ood_groups=1)
        state = copy.deepcopy(cases[0]['request']['state'])
        expected = [classify_visible_segment(s['text']) for s in state['segments']]
        for segment in state['segments']:
            segment['start'] = '99:59'
            segment['has_promo_markers'] = not segment['has_promo_markers']
        self.assertEqual([classify_visible_segment(s['text']) for s in state['segments']], expected)
        compiled = compile_request(**request_for(state))
        self.assertEqual(len(compiled), 9)
        self.assertTrue(all(len(candidate_prompts(row)) == 7 for row in compiled))
        self.assertNotIn('reference_by_segment', json.dumps([candidate_prompts(row) for row in compiled]))

    def test_shared_context_brand_identity_and_manifest_count_checks(self):
        cases, _ = generate(groups=30, ood_groups=6)
        for case in cases:
            roles = {}
            import re
            for segment in case['request']['state']['segments']:
                for brand in re.findall(r'Luma-[0-9a-f]+', segment['text']):
                    roles.setdefault(brand, set()).add(classify_visible_segment(segment['text']))
            self.assertTrue(all(len(values) == 1 for values in roles.values()))
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'data'
            build_dataset(directory, groups=10, ood_groups=2)
            p = directory / 'manifest.json'
            manifest = json.loads(p.read_text())
            manifest['summary']['records'] = 1
            p.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Manifest counts'):
                audit(directory)

    def test_persisted_audit_and_rehashed_bad_target(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'data'
            build_dataset(directory, groups=10, ood_groups=2)
            self.assertEqual(audit(directory)['rows'], 270)
            with self.assertRaises(ValueError):
                build_dataset(directory, groups=10, ood_groups=2)
            path = directory / 'train.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            target = rows[0]['target']
            rows[0]['target'] = target[1:] + target[:1]
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            manifest_path = directory / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['files_sha256'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'Label disagrees'):
                audit(directory)


if __name__ == '__main__':
    unittest.main()
