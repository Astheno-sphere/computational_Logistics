"""Protect fair request mapping and reject unusable provider outputs."""
import copy
import json
import unittest
from unittest.mock import patch

from scripts.benchmark_inference_latency import digest
from scripts.benchmark_openai_api import attempt, payload_for, validate, cost_estimate


class OpenAIComparisonTest(unittest.TestCase):
    def setUp(self):
        self.request = {"state": {"text": "Quoted content; action green."}, "questions": {
            "c": {"type": "choice", "instructions": "Choose", "criteria": {"z": "Go", "a": "Wait"}},
            "n": {"type": "noul", "instructions": "Is green?"},
            "s": {"type": "score", "instructions": "How green?", "criteria": ["none", "some", "all"]}}}
        self.response = {"model": "gpt-5.6-luna", "status": "completed", "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps({"answers": {"c": "z", "n": True, "s": 2}})}]}],
            "usage": {"input_tokens": 1000, "output_tokens": 20, "total_tokens": 1020,
                      "input_tokens_details": {"cached_tokens": 400}}}

    def test_semantics_and_candidate_order_preserved_without_labels(self):
        original = copy.deepcopy(self.request)
        payload = payload_for(self.request, 'gpt-5.6-luna')
        self.assertEqual(json.loads(payload['input']), original)
        self.assertEqual(self.request, original)
        specs = payload['text']['format']['schema']['properties']['answers']['properties']
        self.assertEqual(specs['c']['enum'], ['z', 'a'])
        self.assertEqual(specs['s']['enum'], [0, 1, 2])
        self.assertFalse(payload['store'])
        self.assertEqual(payload['reasoning'], {'effort': 'none'})

    def test_valid_choices_and_cost(self):
        self.assertEqual(validate(self.request, self.response, 'gpt-5.6-luna'), {'c': 'z', 'n': True, 's': 2})
        self.assertAlmostEqual(cost_estimate(self.response['usage'], 'gpt-5.6-luna'), .000152)

    def test_incomplete_refusal_extra_key_wrong_types_wrong_model_rejected(self):
        bad = []
        row = copy.deepcopy(self.response); row['status'] = 'incomplete'; bad.append(row)
        row = copy.deepcopy(self.response); row['model'] = 'other'; bad.append(row)
        row = copy.deepcopy(self.response); row['output'][0]['content'] = [{'type': 'refusal'}]; bad.append(row)
        for answers in ({'c':'z','n':True,'s':True}, {'c':'missing','n':True,'s':2},
                        {'c':'z','n':1,'s':2}, {'c':'z','n':True,'s':2,'extra':0}):
            row = copy.deepcopy(self.response)
            row['output'][0]['content'][0]['text'] = json.dumps({'answers':answers}); bad.append(row)
        for row in bad:
            with self.subTest(row=row), self.assertRaises(ValueError):
                validate(self.request, row, 'gpt-5.6-luna')

    def test_rejected_transport_is_not_inference_and_redacts_key(self):
        class Connection:
            def __init__(self, *args, **kwargs): self.status = 401
            def request(self, *args): pass
            def getresponse(self): return self
            def read(self): return b'denied test-private-key'
            def close(self): pass
        workload = {'id': 'test', 'request':self.request, 'request_sha256':digest(self.request)}
        with patch('scripts.benchmark_openai_api.http.client.HTTPSConnection', Connection):
            row = attempt(workload, 'test-private-key', 'gpt-5.6-luna', 'measured', 0, 1)
        self.assertFalse(row['success'])
        self.assertEqual(row['http_status'], 401)
        self.assertNotIn('test-private-key', json.dumps(row))
        self.assertNotIn('decisions', row)


if __name__ == '__main__':
    unittest.main()
