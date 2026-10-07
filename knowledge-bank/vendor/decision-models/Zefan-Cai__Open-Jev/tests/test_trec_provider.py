"""CPU-only tests with injected attempts; never call a provider or read qrels."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.evaluate_trec_provider import PROTOCOL, categorical_scores, load_input, run


def fixture():
    return {"schema_version": 1, "usage": "evaluation_only", "protocol": PROTOCOL,
            "queries": [{"benchmark": benchmark, "id": str(i), "query": "Which passage answers the question?",
                         "documents": [{"id": f"d{j}", "text": f"passage {j}"} for j in range(100)]}
                        for benchmark, count in (("dl19", 43), ("dl20", 54)) for i in range(count)]}


def sample_for(workload, model, *, special_last=False):
    decisions = {qid: 3 if special_last and workload["request"]["state"]["passages"][f"P{i+1}"] == "passage 99" else 0
                 for i, qid in enumerate(workload["request"]["questions"])}
    if model == "jev-1.13.0":
        response = {"model": model, "usage": {"input_tokens": 10},
                    "answers": {qid: {"type": "score", "score": value,
                                      "probabilities": {str(level): float(level == value) for level in range(4)}}
                                for qid, value in decisions.items()}}
    else:
        response = {"model": model, "status": "completed", "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"answers": decisions})}]}]}
    return {"request_id": workload["id"], "request_sha256": workload["request_sha256"], "mode": model,
            "phase": "measured", "repetition": 0, "success": True, "http_status": 200, "wall_ms": 12,
            "response": response, "raw_response": json.dumps(response), "decisions": decisions}


class TrecProviderTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.input = self.directory / "input.json"
        self.input.write_text(json.dumps(fixture()))
        self.sha = hashlib.sha256(self.input.read_bytes()).hexdigest()
        self.output = self.directory / "run"

    def execute(self, attempt, model="gpt-5.6-luna", **limits):
        return run(self.input, self.sha, self.output, model, "unit-test-secret", attempt_fn=attempt, **limits)

    def test_actual_scores_change_later_windows_and_requests_are_saved_before_calls(self):
        calls = []

        def attempt(workload, key, model, phase, repetition, timeout, max_output_tokens):
            saved = [json.loads(line) for line in (self.output / "requests.jsonl").read_text().splitlines()]
            previous = (self.output / "samples.jsonl").read_text().splitlines()
            self.assertEqual(len(saved), len(calls) + 1)
            self.assertEqual(len(previous), len(calls))
            self.assertEqual(saved[-1]["id"], workload["id"])
            payload_input = json.loads(saved[-1]["payload"]["input"])
            self.assertEqual(set(payload_input), {"state", "questions"})
            self.assertEqual(set(payload_input["state"]), {"query", "passages"})
            self.assertNotIn("benchmark", saved[-1]["payload"])
            self.assertEqual((phase, repetition, max_output_tokens), ("measured", 0, 2048))
            self.assertLessEqual(timeout, 60)
            calls.append(copy.deepcopy(workload))
            return sample_for(workload, model, special_last=True)

        report = self.execute(attempt, max_requests=9)
        self.assertEqual(report["total_attempts"], 9)
        self.assertEqual(report["queries"][0]["status"], "complete")
        self.assertEqual(report["queries"][0]["ranking"][0], "d99")
        self.assertEqual(report["queries"][1]["status"], "pending")
        self.assertEqual(report["query_status_counts"], {"complete": 1, "pending": 96})
        second = list(calls[1]["request"]["state"]["passages"].values())
        self.assertIn("passage 99", second)
        self.assertNotIn("passage 89", second)
        self.assertEqual(self.input.read_bytes(), (self.output / "input.json").read_bytes())
        self.assertFalse(report["qrels_read"])
        self.assertFalse(report["new_accuracy_metrics"])
        self.assertFalse(report["truncation_applied_by_runner"])

    def test_openai_envelope_preserves_integer_scores_without_probabilities(self):
        workload = {"id": "unit", "request_sha256": "hash", "request": {
            "state": {"query": "question", "passages": {"P1": "passage 99"}},
            "questions": {"relevance_P1": {"type": "score", "instructions": "Grade", "criteria": ["0", "1", "2", "3"]}}}}
        sample = sample_for(workload, "gpt-5.6-luna", special_last=True)
        self.assertEqual(categorical_scores(workload["request"], sample, "gpt-5.6-luna"),
                         {"answers": {"relevance_P1": {"type": "score", "score": 3}}})
        sample["decisions"]["relevance_P1"] = True
        with self.assertRaises(ValueError):
            categorical_scores(workload["request"], sample, "gpt-5.6-luna")

    def test_full_run_completes_all_97_queries_in_exactly_873_calls(self):
        calls = []

        def attempt(workload, key, model, phase, repetition, timeout):
            calls.append(workload["id"])
            return sample_for(workload, model)

        report = self.execute(attempt, model="jev-1.13.0")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(report["total_attempts"], 873)
        self.assertEqual(report["query_status_counts"], {"complete": 97})
        self.assertTrue(all(len(q["request_ids"]) == 9 and len(q["ranking"]) == 100 for q in report["queries"]))
        self.assertIsNone(report["known_estimated_cost_usd"])
        self.assertIsNone(report["unknown_cost_request_count"])

    def test_jev_mass_or_expectation_failure_is_retained_and_next_query_runs(self):
        for failure in ("mass", "expectation"):
            with self.subTest(failure=failure):
                self.output = self.directory / failure
                calls = []

                def attempt(workload, key, model, phase, repetition, timeout):
                    sample = sample_for(workload, model)
                    for answer in sample["response"]["answers"].values():
                        answer.update(score=2.87, probabilities={"0": .03, "1": .01, "2": .01, "3": .95})
                    if not calls:
                        first = next(iter(sample["response"]["answers"].values()))
                        if failure == "mass":
                            first["probabilities"]["3"] = .94
                        else:
                            first["score"] = 2.92
                    sample["raw_response"] = json.dumps(sample["response"])
                    calls.append(sample)
                    return sample

                report = self.execute(attempt, model="jev-1.13.0", max_requests=10)
                self.assertEqual(report["queries"][0]["status"], "failed")
                self.assertIsNone(report["queries"][0]["ranking"])
                self.assertEqual(report["queries"][1]["status"], "complete")
                self.assertEqual(report["queries"][1]["supplemental_ranking"], report["queries"][1]["ranking"])
                self.assertEqual(report["queries"][2]["status"], "pending")
                self.assertEqual(len(calls), 10)
                persisted = [json.loads(line) for line in (self.output / "samples.jsonl").read_text().splitlines()]
                self.assertEqual(persisted[0], calls[0])
                self.assertEqual(report["score_rounding_digits"], 2)

    def test_declared_mass_only_scalar_analysis_never_becomes_primary_ranking(self):
        calls = []

        def attempt(workload, key, model, phase, repetition, timeout):
            sample = sample_for(workload, model)
            for answer in sample["response"]["answers"].values():
                answer.update(score=2.87, probabilities={"0": .03, "1": .01, "2": .01, "3": .95})
            if not calls:
                next(iter(sample["response"]["answers"].values()))["probabilities"]["3"] = .94
                sample.update(success=False, error="probabilities do not sum to one")
            sample["raw_response"] = json.dumps(sample["response"])
            calls.append(sample)
            return sample

        report = self.execute(attempt, model="jev-1.13.0", max_requests=9)
        query = report["queries"][0]
        self.assertEqual(query["status"], "complete_scalar_only")
        self.assertFalse(query["strict_query_valid"])
        self.assertIsNone(query["ranking"])
        self.assertEqual(len(query["supplemental_ranking"]), 100)
        self.assertEqual(query["supplemental_ranking"], [f"d{i}" for i in range(100)])
        first = query["request_validations"][0]
        self.assertFalse(first["strict_valid"])
        self.assertTrue(first["scalar_usable"])
        self.assertAlmostEqual(first["strict_probability_mass_failure"][0]["mass"], .99)
        self.assertEqual(report["collection_counts"], {"http_200": 9, "transport_errors": 0,
                         "strict_valid_requests": 8, "strict_validation_failures": 1, "scalar_usable_requests": 9,
                         "strict_complete_queries": 0, "scalar_complete_queries": 1})
        self.assertTrue(report["supplemental_scalar_analysis"]["predeclared"])
        self.assertEqual(json.loads((self.output / "samples.jsonl").read_text().splitlines()[0]), calls[0])

    def test_mass_and_expectation_failure_cannot_use_scalar_analysis(self):
        def attempt(workload, key, model, phase, repetition, timeout):
            sample = sample_for(workload, model)
            first = next(iter(sample["response"]["answers"].values()))
            first.update(score=2.92, probabilities={"0": .03, "1": .01, "2": .01, "3": .94})
            sample.update(success=False, error="probabilities do not sum to one")
            sample["raw_response"] = json.dumps(sample["response"])
            return sample

        report = self.execute(attempt, model="jev-1.13.0", max_requests=1)
        self.assertEqual(report["queries"][0]["status"], "failed")
        self.assertIsNone(report["queries"][0]["supplemental_ranking"])
        self.assertIn("expectation", report["queries"][0]["error"])
        self.assertEqual(report["collection_counts"]["scalar_usable_requests"], 0)

    def test_endpoint_rejections_stop_all_remaining_queries(self):
        for status in (401, 403, 429, 503, 529):
            with self.subTest(status=status):
                self.output = self.directory / f"http-{status}"

                def attempt(workload, key, model, phase, repetition, timeout, **kwargs):
                    sample = sample_for(workload, model)
                    sample.update(success=False, http_status=status, raw_response='{"error":"rejected"}')
                    sample.pop("response")
                    return sample

                report = self.execute(attempt)
                self.assertEqual(report["status"], "stopped_endpoint")
                self.assertEqual(report["total_attempts"], 1)
                self.assertEqual(report["query_status_counts"], {"failed_endpoint": 1, "pending": 96})
                self.assertEqual(report["unknown_cost_request_count"], 1)

    def test_request_time_and_usage_cost_budgets_preserve_partial_and_pending(self):
        for budget in ("request", "time", "cost"):
            with self.subTest(budget=budget):
                self.output = self.directory / budget
                now = [0.0]

                def attempt(workload, key, model, phase, repetition, timeout, **kwargs):
                    sample = sample_for(workload, model)
                    now[0] += 2
                    if budget == "cost":
                        sample["response"]["usage"] = {"input_tokens": 100000, "output_tokens": 1, "total_tokens": 100001}
                        sample["raw_response"] = json.dumps(sample["response"])
                        sample["estimated_cost_usd"] = 0  # Runner must use actual usage, not this cached estimate.
                    return sample

                limits = {"max_requests": 1} if budget == "request" else {"max_seconds": 1} if budget == "time" else {"cost_limit_usd": .5}
                report = self.execute(attempt, model="gpt-6-astra", clock=lambda: now[0], **limits)
                self.assertEqual(report["total_attempts"], 1)
                self.assertEqual(report["stop_reason"], budget + "_budget")
                self.assertEqual(report["query_status_counts"], {"incomplete_budget": 1, "pending": 96})
                self.assertIsNone(report["queries"][0]["ranking"])
                self.assertEqual(len(report["queries"]), 97)
                if budget == "cost":
                    self.assertAlmostEqual(report["known_estimated_cost_usd"], 1.00005)

    def test_thrown_attempt_error_is_saved_redacted_and_cost_remains_unknown(self):
        def attempt(*args, **kwargs):
            raise TimeoutError("unit-test-secret connection failed")

        report = self.execute(attempt, max_requests=2)
        self.assertEqual(report["query_status_counts"], {"failed": 2, "pending": 95})
        self.assertEqual(report["unknown_cost_request_count"], 2)
        self.assertNotIn("unit-test-secret", (self.output / "samples.jsonl").read_text())
        self.assertIn("[REDACTED]", (self.output / "samples.jsonl").read_text())

    def test_nonfinite_parsed_response_keeps_exact_raw_text_and_fails_query(self):
        raw = []

        def attempt(workload, key, model, phase, repetition, timeout):
            sample = sample_for(workload, model)
            next(iter(sample["response"]["answers"].values()))["score"] = float("nan")
            sample["raw_response"] = json.dumps(sample["response"])
            raw.append(sample["raw_response"])
            return sample

        report = self.execute(attempt, model="jev-1.13.0", max_requests=1)
        self.assertEqual(report["queries"][0]["status"], "failed")
        saved = json.loads((self.output / "samples.jsonl").read_text(), parse_constant=lambda value: self.fail(value))
        self.assertEqual(saved["raw_response"], raw[0])
        self.assertIn("parsed_response_omitted", saved)
        self.assertIsNone(report["queries"][0]["supplemental_ranking"])

    def test_frozen_input_contract_rejects_gold_metadata_hash_mismatch_and_overwrite(self):
        for mutation in ("qrels", "passage_grade", "protocol", "hash"):
            with self.subTest(mutation=mutation):
                document = fixture()
                if mutation == "qrels": document["queries"][0]["qrels"] = {"d0": 3}
                if mutation == "passage_grade": document["queries"][0]["documents"][0]["grade"] = 3
                if mutation == "protocol": document["protocol"] = {**PROTOCOL, "window_size": 100}
                self.input.write_text(json.dumps(document))
                current_sha = hashlib.sha256(self.input.read_bytes()).hexdigest()
                with self.assertRaises(ValueError):
                    load_input(self.input, "0" * 64 if mutation == "hash" else current_sha)
        self.input.write_text(json.dumps(fixture()))
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.execute(lambda *args, **kwargs: self.fail("No provider call allowed"))


if __name__ == "__main__":
    unittest.main()
