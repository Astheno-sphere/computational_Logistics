"""Check that rejection is never inference and comparable request data survives."""
import copy
import json
import unittest
from unittest.mock import patch

from scripts.benchmark_inference_latency import digest
from scripts.benchmark_jev_api_latency import attempt, validate


class JevLatencyTest(unittest.TestCase):
    def setUp(self):
        self.request = {"state": {"observation": "green"}, "questions": {
            "action": {"type": "choice", "instructions": "Choose", "criteria": {"z": "Go", "a": "Wait"}}}}
        self.workload = {"id": "green", "request": self.request, "request_sha256": digest(self.request)}
        self.response = {"model": "jev-1.13.0", "answers": {"action": {
            "type": "choice", "probabilities": {"a": .1, "z": .9}, "choice": "z"}}, "usage": {"input_tokens": 10}}

    def test_exact_inputs_and_valid_response(self):
        original = copy.deepcopy(self.request)
        connections = []
        response = self.response

        class Connection:
            def __init__(self, *args, **kwargs):
                connections.append(self)
            def request(self, method, path, body, headers):
                self.body, self.headers = json.loads(body), headers
            def getresponse(self):
                self.status = 200
                return self
            def read(self):
                return json.dumps(response).encode()
            def close(self):
                self.closed = True

        with patch('scripts.benchmark_jev_api_latency.http.client.HTTPSConnection', Connection):
            row = attempt(self.workload, 'secret-not-for-reports', 'jev-1.13.0', 'measured', 0, 1)
        self.assertTrue(row['success'])
        self.assertEqual(self.request, original)
        self.assertEqual(connections[0].body, {**original, 'model': 'jev-1.13.0'})
        self.assertEqual(list(connections[0].body['questions']['action']['criteria']), ['z', 'a'])
        self.assertNotIn('secret-not-for-reports', json.dumps(row))
        self.assertTrue(connections[0].closed)

    def test_rejection_retains_response_and_redacts_key(self):
        class Rejected:
            def __init__(self, *args, **kwargs):
                self.status = 403
            def request(self, *args):
                pass
            def getresponse(self):
                return self
            def read(self):
                return b'Permission denied. example-secret'
            def close(self):
                pass
        with patch('scripts.benchmark_jev_api_latency.http.client.HTTPSConnection', Rejected):
            row = attempt(self.workload, 'example-secret', 'jev-1.13.0', 'warmup', 0, 1)
        self.assertFalse(row['success'])
        self.assertEqual(row['http_status'], 403)
        self.assertIn('Permission denied.', row['raw_response'])
        self.assertNotIn('example-secret', json.dumps(row))
        self.assertNotIn('response', row)

    def test_wrong_model_and_malformed_outputs_fail(self):
        for mutation in ('model', 'coverage', 'probability', 'choice'):
            response = copy.deepcopy(self.response)
            if mutation == 'model': response['model'] = 'other'
            if mutation == 'coverage': response['answers']['extra'] = {}
            if mutation == 'probability': response['answers']['action']['probabilities']['z'] = float('nan')
            if mutation == 'choice': response['answers']['action']['choice'] = 'a'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(self.request, response, 'jev-1.13.0')


if __name__ == '__main__':
    unittest.main()
