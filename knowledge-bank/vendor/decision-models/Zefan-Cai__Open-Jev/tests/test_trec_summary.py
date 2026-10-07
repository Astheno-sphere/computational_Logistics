"""Offline evidence replay and full-qrel denominator tests; no provider calls."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from scripts.evaluate_trec_provider import digest, openai_api, run
from scripts.summarize_trec_provider import AuditError, summarize
from tests.test_trec_provider import fixture, sample_for


class TrecSummaryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.input = self.directory / "input.json"
        self.input.write_text(json.dumps(fixture()))
        self.input_sha = hashlib.sha256(self.input.read_bytes()).hexdigest()
        self.output = self.directory / "run"
        self.manifests, self.manifest_sha = {}, {}
        for benchmark in ("dl19", "dl20"):
            path = self.directory / benchmark
            path.mkdir()
            queries = [q for q in fixture()["queries"] if q["benchmark"] == benchmark]
            candidates = [{"id": q["id"], "query": q["query"], "documents": [
                {**doc, "bm25_rank": index, "bm25_score": 100 - index}
                for index, doc in enumerate(q["documents"], 1)]} for q in queries]
            (path / "candidates.jsonl").write_text("".join(json.dumps(q) + "\n" for q in candidates))
            (path / "qrels.txt").write_text("".join(f"{q['id']} 0 {doc} {grade}\n" for q in queries
                                                    for doc, grade in (("d99", 2), ("outside-top100", 3), ("d0", 1))))
            manifest = {"usage": "evaluation_only", "benchmark": "TREC-" + benchmark.upper(),
                        "retriever": {"name": "BM25", "top_k": 100, "k1": .9, "b": .4},
                        "files_sha256": {name: hashlib.sha256((path / name).read_bytes()).hexdigest()
                                         for name in ("candidates.jsonl", "qrels.txt")}}
            self.manifests[benchmark] = path / "manifest.json"
            self.manifests[benchmark].write_text(json.dumps(manifest))
            self.manifest_sha[benchmark] = hashlib.sha256(self.manifests[benchmark].read_bytes()).hexdigest()

    def collect(self, *, model="jev-1.13.0", max_requests=9, mass_first=False, fail_second=False):
        calls = []

        def attempt(workload, key, selected, phase, repetition, timeout, **kwargs):
            sample = sample_for(workload, selected, special_last=True)
            if selected != "jev-1.13.0":
                sample["payload_sha256"] = digest(openai_api.payload_for(workload["request"], selected, kwargs["max_output_tokens"]))
            if mass_first and not calls:
                first = next(iter(sample["response"]["answers"].values()))
                first.update(score=.76, probabilities={"0": .54, "1": .2, "2": .2, "3": .05})
                sample.update(success=False, error="probabilities do not sum to one")
                sample["raw_response"] = json.dumps(sample["response"])
            if fail_second and len(calls) == 1:
                sample.update(success=False, http_status=500, raw_response='{"error":"failed"}')
                sample.pop("response")
            calls.append(workload["id"])
            return sample

        return run(self.input, self.input_sha, self.output, model, "test-secret",
                   max_requests=max_requests, attempt_fn=attempt)

    def summary(self):
        return summarize(self.output, self.manifests, input_sha256=self.input_sha, manifest_sha256=self.manifest_sha)

    def mutate_report(self, update):
        path = self.output / "report.json"
        value = json.loads(path.read_text())
        update(value)
        path.write_text(json.dumps(value))

    def mutate_log(self, filename, update):
        path = self.output / filename
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        update(rows)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_partial_run_uses_full_qrels_and_direct_grade_including_outside_candidates(self):
        self.collect()
        result = self.summary()
        ideal = 3 + 2 / math.log2(3) + 1 / math.log2(4)
        expected = (2 + 1 / math.log2(3)) / ideal
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["metrics_are_provisional_lower_bounds"])
        self.assertEqual(result["qrel_query_denominator"], 97)
        self.assertAlmostEqual(result["benchmarks"]["dl19"]["primary_strict"]["value"], expected / 43)
        self.assertEqual(result["benchmarks"]["dl20"]["primary_strict"]["value"], 0)
        self.assertAlmostEqual(result["combined_query_weighted"]["primary_strict_ndcg_at_10"], expected / 97)
        self.assertAlmostEqual(result["benchmarks"]["dl19"]["downloaded_bm25_baseline"]["value"], 1 / ideal)
        self.assertNotIn("passage 99", json.dumps(result))
        self.assertNotIn("test-secret", json.dumps(result))
        self.assertEqual(result["new_provider_calls"], 0)

    def test_mass_only_query_primary_zero_and_supplemental_uses_actual_saved_scalars(self):
        self.collect(mass_first=True)
        result = self.summary()
        self.assertEqual(result["query_status_counts"]["complete_scalar_only"], 1)
        self.assertEqual(result["benchmarks"]["dl19"]["strict_complete_queries"], 0)
        self.assertEqual(result["benchmarks"]["dl19"]["scalar_complete_queries"], 1)
        self.assertEqual(result["benchmarks"]["dl19"]["primary_strict"]["value"], 0)
        self.assertGreater(result["benchmarks"]["dl19"]["supplemental_actual_scalar"]["value"], 0)
        self.assertEqual(result["replayed_collection_counts"]["strict_validation_failures"], 1)

    def test_mass_only_then_hard_error_does_not_publish_either_ranking(self):
        self.collect(mass_first=True, fail_second=True, max_requests=2)
        result = self.summary()
        self.assertEqual(result["query_status_counts"], {"failed": 1, "pending": 96})
        self.assertEqual(result["combined_query_weighted"]["primary_strict_ndcg_at_10"], 0)
        self.assertEqual(result["combined_query_weighted"]["supplemental_actual_scalar_ndcg_at_10"], 0)

    def test_python310_mass_diagnostics_replay_exactly_without_relaxing_validation(self):
        self.collect(mass_first=True)

        def diagnostic(report):
            return report["queries"][0]["request_validations"][0]["strict_probability_mass_failure"][0]

        # Python 3.10's left-to-right sum for .54, .2, .2, .05 differs from
        # Python 3.12+'s compensated sum in both derived diagnostic fields.
        self.mutate_report(lambda report: diagnostic(report).update(
            mass=.99, raw_probability_expectation=.7500000000000001))
        result = self.summary()
        self.assertEqual(result["query_status_counts"]["complete_scalar_only"], 1)
        self.assertEqual(result["replayed_collection_counts"]["strict_validation_failures"], 1)
        self.assertEqual(result["combined_query_weighted"]["primary_strict_ndcg_at_10"], 0)
        original = (self.output / "report.json").read_bytes()
        mutations = [
            # No general epsilon: even a one-ULP value outside either exact
            # algorithm, or a pair mixing algorithms, must be rejected.
            lambda r: diagnostic(r).update(mass=math.nextafter(.99, -math.inf)),
            lambda r: diagnostic(r).update(raw_probability_expectation=.75),
            lambda r: diagnostic(r).update(score=math.nextafter(.76, math.inf)),
            lambda r: diagnostic(r).update(question_id="relevance_P999"),
            lambda r: r["queries"][0]["request_validations"][0].update(strict_valid=True),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                (self.output / "report.json").write_bytes(original)
                self.mutate_report(mutation)
                with self.assertRaises(AuditError):
                    self.summary()

    def test_full_openai_collection_has_no_fabricated_scalar_probability_analysis(self):
        self.collect(model="gpt-5.6-luna", max_requests=873)
        result = self.summary()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["query_status_counts"], {"complete": 97})
        self.assertFalse(result["metrics_are_provisional_lower_bounds"])
        self.assertIsNone(result["benchmarks"]["dl19"]["supplemental_actual_scalar"])
        self.assertEqual(result["raw_snapshot"]["captured_samples"], 873)

    def test_top_level_running_status_never_becomes_complete_even_after_all_queries(self):
        self.collect(max_requests=873)
        self.mutate_report(lambda report: report.update(status="running"))
        self.assertEqual(self.summary()["status"], "partial")

    def test_finished_collection_with_mass_failure_retains_full_denominator(self):
        self.collect(max_requests=873, mass_first=True)
        result = self.summary()
        self.assertEqual(result["runner_status"], "completed_with_query_failures")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["query_status_counts"], {"complete_scalar_only": 1, "complete": 96})
        self.assertEqual(result["benchmarks"]["dl19"]["strict_complete_queries"], 42)
        self.assertEqual(result["benchmarks"]["dl19"]["scalar_complete_queries"], 43)
        self.assertLess(result["combined_query_weighted"]["primary_strict_ndcg_at_10"],
                        result["combined_query_weighted"]["supplemental_actual_scalar_ndcg_at_10"])

    def test_rejects_permutation_tampering_flags_and_adaptive_window_changes(self):
        self.collect()
        original = (self.output / "report.json").read_bytes()
        mutations = [
            lambda r: r["queries"][0]["ranking"].__setitem__(0, "not-a-candidate"),
            lambda r: r["queries"][0]["ranking"].reverse(),
            lambda r: r["queries"][0].update(strict_query_valid=False),
            lambda r: r["queries"][0]["windows"][1]["document_ids"].reverse(),
            lambda r: r["queries"][0]["request_validations"][0].update(strict_valid=False),
            lambda r: r.update(status="complete"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                (self.output / "report.json").write_bytes(original)
                self.mutate_report(mutation)
                with self.assertRaises(AuditError):
                    self.summary()

    def test_rejects_raw_payload_response_model_or_order_tampering(self):
        self.collect(model="gpt-5.6-luna")
        originals = {name: (self.output / name).read_bytes() for name in ("requests.jsonl", "samples.jsonl")}
        mutations = [
            ("requests.jsonl", lambda rows: rows[0]["payload"].update(model="gpt-6-astra")),
            ("samples.jsonl", lambda rows: rows[0].update(mode="gpt-6-astra")),
            ("samples.jsonl", lambda rows: rows[0].pop("payload_sha256")),
            ("samples.jsonl", lambda rows: rows[0].update(raw_response='{"different":true}')),
            ("samples.jsonl", lambda rows: rows.reverse()),
            ("samples.jsonl", lambda rows: rows.append(copy.deepcopy(rows[0]))),
            ("samples.jsonl", lambda rows: rows.pop()),
        ]
        for filename, mutation in mutations:
            with self.subTest(filename=filename, mutation=mutation):
                for name, raw in originals.items():
                    (self.output / name).write_bytes(raw)
                self.mutate_log(filename, mutation)
                with self.assertRaises(AuditError):
                    self.summary()

    def test_input_and_qrel_manifest_hashes_are_required(self):
        self.collect()
        with self.assertRaises(ValueError):
            summarize(self.output, self.manifests, input_sha256="0" * 64, manifest_sha256=self.manifest_sha)
        (self.manifests["dl19"].parent / "qrels.txt").write_text("0 0 d0 0\n")
        with self.assertRaises(ValueError):
            self.summary()

    def test_live_report_prefix_may_have_unscored_newer_raw_records(self):
        self.collect(max_requests=18)
        self.mutate_report(lambda r: r.update(status="running"))
        report = json.loads((self.output / "report.json").read_text())
        second = report["queries"][1]
        second.update(status="pending", ranking=None, supplemental_ranking=None, strict_query_valid=None,
                      request_ids=[], request_validations=[], call_wall_ms=[], windows=[])
        report.update(total_attempts=9, query_status_counts={"complete": 1, "pending": 96})
        report["collection_counts"] = {"http_200": 9, "transport_errors": 0, "strict_valid_requests": 9,
                                        "strict_validation_failures": 0, "scalar_usable_requests": 9,
                                        "strict_complete_queries": 1, "scalar_complete_queries": 1}
        (self.output / "report.json").write_text(json.dumps(report))
        result = self.summary()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["raw_snapshot"]["unscored_request_tail"], 9)
        self.assertEqual(result["benchmarks"]["dl19"]["strict_complete_queries"], 1)


if __name__ == "__main__":
    unittest.main()
