import copy
import json
import unittest

from scripts.build_provider_suite import workload_for_row


class ProviderSuiteTest(unittest.TestCase):
    def test_gold_and_metadata_excluded_and_all_forms_roundtrip(self):
        for kind, options, target in [('noul', ['no', 'yes'], [0, 1]),
                                      ('choice', ['B: wait', 'A: go'], [0, 1]),
                                      ('choice', ['answer without delimiter', 'other'], [1, 0]),
                                      ('score', ['none', 'some', 'all'], [0, 1, 0])]:
            row = {'id':'private-id', 'source':'source', 'group_id':'private-group', 'split':'test',
                   'kind':kind, 'state':{'text':'visible'}, 'question':'Visible question',
                   'options':options, 'target':target, 'metadata':{'oracle':'PRIVATE_ORACLE'}}
            original = copy.deepcopy(row)
            workload, gold = workload_for_row(row)
            self.assertEqual(row, original)
            self.assertNotIn('PRIVATE_ORACLE', json.dumps(workload))
            self.assertNotIn('target', workload['request'])
            self.assertEqual(gold['target'], target)
            self.assertEqual(gold['request_sha256'], workload['request_sha256'])


if __name__ == '__main__':
    unittest.main()
