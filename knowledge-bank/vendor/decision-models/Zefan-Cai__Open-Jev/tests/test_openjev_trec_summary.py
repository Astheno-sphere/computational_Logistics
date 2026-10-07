import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.api import compile_request, format_response
from scripts import evaluate_openjev_trec as collector
from scripts import summarize_openjev_trec as audit
from tests.test_trec_provider import fixture


EXPECTED = {"model": "Qwen/Qwen3.5-2B", "method": "lora_decision_head",
            "base_revision": "1" * 40, "checkpoint_sha256": "2" * 64,
            "temperature": 1.25, "code_commit": "3" * 40, "max_length": 16384}


def sample_for(workload, endpoint, expected, timeout):
    request = workload["request"]
    probabilities = []
    for text in request["state"]["passages"].values():
        # Every most-likely grade is zero. Tiny expected-score differences must
        # still determine order; rounding to two decimals would lose them all.
        number = int(text.split()[-1])
        probability = .25 + number * .00001
        probabilities.append([1 - probability, 0.0, 0.0, probability])
    response = format_response(compile_request(request["state"], request["questions"]), probabilities)
    response.update(model=expected["model"], usage={"input_tokens": 123, "output_tokens": 0},
                    metadata={**{k: v for k, v in expected.items() if k != "model"},
                              "prefix_cache": {"enabled": False}})
    return {"request_id": workload["id"], "request_sha256": workload["request_sha256"],
            "mode": expected["model"], "phase": "measured", "repetition": 0, "success": True,
            "http_status": 200, "wall_ms": 1.0, "response": response,
            "raw_response": json.dumps(response)}


class OpenJevTrecSummaryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input = self.root / "input.json"
        self.document = fixture()
        self.input.write_text(json.dumps(self.document))
        self.input_sha = hashlib.sha256(self.input.read_bytes()).hexdigest()
        self.output = self.root / "run"
        self.holdouts, self.hashes = {}, {}
        for name, count in (("dl19", 43), ("dl20", 54)):
            directory = self.root / name
            directory.mkdir()
            rows = [{"id": str(i), "query": "Which passage answers the question?",
                     "documents": [{"id": f"d{j}", "text": f"passage {j}",
                                    "bm25_rank": j + 1, "bm25_score": float(100 - j)} for j in range(100)]}
                    for i in range(count)]
            (directory / "candidates.jsonl").write_text(''.join(json.dumps(row) + '\n' for row in rows))
            (directory / "qrels.txt").write_text(''.join(f"{i} 0 {doc} {grade}\n" for i in range(count)
                                                       for doc, grade in (("d99", 3), ("d98", 2), ("d97", 1), ("outside", 3))))
            manifest = {"usage": "evaluation_only", "benchmark": "TREC-" + name.upper(),
                        "retriever": {"name": "BM25", "top_k": 100, "k1": .9, "b": .4},
                        "files_sha256": {file: hashlib.sha256((directory / file).read_bytes()).hexdigest()
                                         for file in ("candidates.jsonl", "qrels.txt")}}
            path = directory / "manifest.json"
            path.write_text(json.dumps(manifest))
            self.holdouts[name] = path
            self.hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def collect(self, attempt=sample_for, max_requests=9):
        return collector.run(self.input, self.input_sha, "http://127.0.0.1:8791/v1/systemone",
                             EXPECTED, self.output, max_requests=max_requests, attempt_fn=attempt)

    def summarize(self):
        # Offline audit must not issue requests, even to localhost, or spawn a process.
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')), \
                patch('subprocess.Popen', side_effect=AssertionError('Subprocess forbidden')):
            return audit.summarize(self.output, self.holdouts, input_sha256=self.input_sha, manifest_sha256=self.hashes)

    def rewrite(self, name, change):
        path = self.output / name
        if name.endswith('.jsonl'):
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            change(rows)
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        else:
            value = json.loads(path.read_bytes())
            change(value)
            path.write_text(json.dumps(value))

    def test_full_run_replays_expected_scores_and_full_qrels_without_network(self):
        run = self.collect(max_requests=873)
        self.assertEqual(run['queries'][0]['ranking'][:3], ['d99', 'd98', 'd97'])
        report = self.summarize()
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['qrel_query_denominator'], 97)
        self.assertEqual(report['raw_snapshot']['samples'], 873)
        dcg = 3 + 2 / math.log2(3) + 1 / math.log2(4)
        ideal = 3 + 3 / math.log2(3) + 2 / math.log2(4) + 1 / math.log2(5)
        for name, count in (('dl19', 43), ('dl20', 54)):
            result = report['benchmarks'][name]
            self.assertEqual(result['qrel_query_denominator'], count)
            self.assertEqual(result['strict_complete_queries'], count)
            self.assertAlmostEqual(result['primary_strict']['value'], dcg / ideal)
            self.assertEqual(result['downloaded_bm25_baseline']['value'], 0)
        self.assertAlmostEqual(report['combined_query_weighted']['primary_strict_ndcg_at_10'], dcg / ideal)
        self.assertNotIn('passage 99', json.dumps(report))
        self.assertNotIn('Which passage answers', json.dumps(report))
        self.assertEqual(report['new_provider_calls'], 0)

    def test_partial_keeps_full43_54_denominators_and_pending_zero(self):
        self.collect()
        report = self.summarize()
        self.assertEqual(report['status'], 'partial')
        self.assertTrue(report['metrics_are_provisional_lower_bounds'])
        self.assertEqual(report['query_status_counts'], {'complete': 1, 'pending': 96})
        metric = report['benchmarks']['dl19']['primary_strict']
        self.assertEqual(len(metric['missing_run_queries']), 42)
        self.assertAlmostEqual(metric['value'], metric['per_query']['0'] / 43)
        self.assertEqual(report['benchmarks']['dl20']['primary_strict']['value'], 0)
        self.assertAlmostEqual(report['combined_query_weighted']['primary_strict_ndcg_at_10'], metric['per_query']['0'] / 97)

    def test_failed_first_query_has_no_fallback_and_next_complete_still_full_denominator(self):
        calls = []

        def attempt(*args):
            sample = sample_for(*args)
            if not calls:
                answer = next(iter(sample['response']['answers'].values()))
                answer['probabilities']['0'] -= .01
                sample.update(success=False, error='probabilities do not sum to one')
                sample['raw_response'] = json.dumps(sample['response'])
            calls.append(sample)
            return sample
        self.collect(attempt, max_requests=10)
        report = self.summarize()
        self.assertEqual(report['query_status_counts'], {'failed': 1, 'complete': 1, 'pending': 95})
        metric = report['benchmarks']['dl19']['primary_strict']
        self.assertEqual(metric['per_query']['0'], 0)
        self.assertGreater(metric['per_query']['1'], 0)
        self.assertEqual(metric['qrel_query_denominator'], 43)
        self.assertEqual(report['raw_snapshot']['failed_requests'], 1)

    def test_reordered_payload_is_rejected_even_when_sorted_digest_unchanged(self):
        self.collect()
        before = json.loads((self.output / 'requests.jsonl').read_text().splitlines()[0])
        self.rewrite('requests.jsonl', lambda rows: rows[0].update(payload=dict(reversed(list(rows[0]['payload'].items())))))
        after = json.loads((self.output / 'requests.jsonl').read_text().splitlines()[0])
        self.assertEqual(audit.client.digest(before['payload']), audit.client.digest(after['payload']))
        with self.assertRaisesRegex(audit.AuditError, 'wire payload'):
            self.summarize()

    def test_changed_identity_raw_body_ranking_or_adaptive_window_is_rejected(self):
        self.collect()
        originals = {name: (self.output / name).read_bytes() for name in ['samples.jsonl', 'report.json']}
        cases = [
            ('samples.jsonl', lambda rows: rows[0]['response']['metadata'].update(checkpoint_sha256='4' * 64)),
            ('report.json', lambda v: v['queries'][0]['ranking'].reverse()),
            ('report.json', lambda v: v['queries'][0]['windows'][1]['document_ids'].reverse()),
            ('report.json', lambda v: v['source_sha256'].update(client='0' * 64)),
            ('report.json', lambda v: v.update(started_requests=8)),
        ]
        for index, (name, change) in enumerate(cases):
            for filename, raw in originals.items():
                (self.output / filename).write_bytes(raw)
            self.rewrite(name, change)
            with self.subTest(index=index), self.assertRaises((audit.AuditError, ValueError)):
                self.summarize()

    def test_matching_raw_and_parsed_cache_change_still_fails_identity(self):
        self.collect()

        def change(rows):
            rows[0]['response']['metadata']['prefix_cache']['enabled'] = True
            rows[0]['raw_response'] = json.dumps(rows[0]['response'])
        self.rewrite('samples.jsonl', change)
        with self.assertRaisesRegex(audit.AuditError, 'strict Open-Jev'):
            self.summarize()

    def test_dangling_dispatch_and_extra_journal_tail_cannot_be_scored(self):
        self.collect()
        path = self.output / 'samples.jsonl'
        original = path.read_bytes()
        path.write_bytes(b'\n'.join(original.splitlines()[:-1]) + b'\n')
        with self.assertRaisesRegex(audit.AuditError, 'Unsettled'):
            self.summarize()
        path.write_bytes(original)
        self.rewrite('requests.jsonl', lambda rows: rows.append({**copy.deepcopy(rows[-1]), 'id': 'extra'}))
        with self.assertRaisesRegex(audit.AuditError, 'Unsettled'):
            self.summarize()

    def test_changed_qrels_or_manifest_are_rejected(self):
        self.collect()
        path = self.holdouts['dl19'].parent / 'qrels.txt'
        path.write_text(path.read_text() + 'unknown 0 d0 3\n')
        with self.assertRaises(ValueError):
            self.summarize()

    def test_raw_boolean_and_probability_order_cannot_hide_behind_python_equality(self):
        self.collect()
        path = self.output / 'samples.jsonl'
        original = path.read_bytes()
        for mode in ('boolean', 'order'):
            path.write_bytes(original)

            def change(rows):
                raw = json.loads(rows[0]['raw_response'])
                answer = next(iter(raw['answers'].values()))
                if mode == 'boolean':
                    answer['probabilities']['1'] = False
                else:
                    answer['probabilities'] = dict(reversed(list(answer['probabilities'].items())))
                # Python's equality misses both these differences.
                self.assertEqual(raw, rows[0]['response'])
                rows[0]['raw_response'] = json.dumps(raw)
            self.rewrite('samples.jsonl', change)
            with self.subTest(mode=mode), self.assertRaisesRegex(audit.AuditError, 'Raw and parsed'):
                self.summarize()

    def test_mandatory_fatal_cannot_be_relabelled_to_continue_more_queries(self):
        calls = []

        def attempt(*args):
            sample = sample_for(*args)
            if not calls:
                sample.update(success=False, http_status=422, error_type='ValueError', error='HTTP422')
            calls.append(sample)
            return sample
        self.collect(attempt, max_requests=10)
        self.assertEqual(self.summarize()['raw_snapshot']['samples'], 10)
        original = (self.output / 'samples.jsonl').read_bytes()
        for values in ({'http_status': 500}, {'error_type': 'TimeoutError'}, {'error_type': 'IdentityError'}):
            (self.output / 'samples.jsonl').write_bytes(original)
            self.rewrite('samples.jsonl', lambda rows: rows[0].update(**values))
            with self.subTest(values=values), self.assertRaisesRegex(audit.AuditError, 'Mandatory fatal'):
                self.summarize()

    def test_pending_query_cannot_precede_processed_queries(self):
        self.collect()

        def change(report):
            first, second = report['queries'][:2]
            report['queries'][0] = {**copy.deepcopy(second), 'id': first['id']}
            report['queries'][1] = {**copy.deepcopy(first), 'id': second['id']}
        self.rewrite('report.json', change)
        with self.assertRaises(audit.AuditError):
            self.summarize()


if __name__ == '__main__':
    unittest.main()
