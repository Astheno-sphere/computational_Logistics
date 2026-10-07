import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jev.api import compile_request, format_response
from scripts import jevbench_openjev as benchmark


IDENTITY = {"model": "Qwen/Qwen3.5-2B", "method": "lora_decision_head",
            "base_revision": "1" * 40, "checkpoint_sha256": "2" * 64,
            "temperature": 1.25, "code_commit": "3" * 40, "max_length": 16384}
ENDPOINT = "http://127.0.0.1:8791/v1/systemone"
UPSTREAM = Path(__file__).resolve().parents[1] / "runs/jevbench-20260921/upstream"


def fixtures():
    questions = [
        {"type": "noul", "instructions": "Is the lamp on?"},
        {"type": "choice", "instructions": "Choose the lamp state.",
         "criteria": {"z_on": "On", "a_off": "Off"}},
        {"type": "score", "instructions": "Rate certainty.",
         "criteria": ["unknown", "likely", "certain"]},
    ]
    tasks = [SimpleNamespace(id=str(index), state="The lamp is on.", question=question,
                             labels=labels, expected=target, provenance={"private_gold": "sentinel"})
             for index, question, labels, target in zip(
                 range(3), questions, (["no", "yes"], ["a_off", "z_on"], ["0", "1", "2"]),
                 ("yes", "z_on", 2))]
    return SimpleNamespace(tasks=tasks, base=SimpleNamespace(build_question=lambda task: copy.deepcopy(task.question)))


def response_for(request):
    records = compile_request(request["state"], request["questions"])
    keys = records[0]["answer_keys"]
    response = format_response(records, [[1 / len(keys)] * len(keys)])
    response.update(model=IDENTITY["model"], usage={"input_tokens": 42, "output_tokens": 0},
                    metadata={**{key: value for key, value in IDENTITY.items() if key != "model"},
                              "prefix_cache": {"enabled": False}})
    return response


class JevBenchOpenJevTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.document = benchmark.request_document(fixtures())
        self.path = self.root / "requests.json"
        self.path.write_bytes(benchmark.json_bytes(self.document))
        self.input_sha = benchmark.sha256(self.path.read_bytes())

    def fake_http(self, factory, responses=None, statuses=None):
        requests = self.document["workloads"]
        if responses is None:
            responses = [response_for(row["request"]) for row in requests]
        if statuses is None:
            statuses = [200] * len(responses)
        received = [SimpleNamespace(status=status, read=lambda body=benchmark.json_bytes(body): body)
                    for status, body in zip(statuses, responses)]
        factory.return_value.getresponse.side_effect = received

    def collect(self):
        return benchmark.collect(self.path, self.input_sha, ENDPOINT, IDENTITY, self.root / "run")

    def read(self, name):
        return [json.loads(line) for line in (self.root / "run" / name).read_text().splitlines()]

    def test_request_gold_separation_and_original_candidate_order(self):
        for task, row in zip(fixtures().tasks, self.document["workloads"]):
            self.assertEqual(set(row["request"]), {"state", "questions"})
            self.assertEqual(row["request"]["questions"], {"decision": task.question})
            self.assertNotIn("private_gold", json.dumps(row))
            self.assertNotIn('"expected"', json.dumps(row))
        self.assertEqual(list(self.document["workloads"][1]["request"]["questions"]["decision"]["criteria"]),
                         ["z_on", "a_off"])

    def test_one_attempt_per_task_and_durable_journal(self):
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            self.fake_http(factory)
            report = self.collect()
            sent = [json.loads(call.args[2]) for call in factory.return_value.request.call_args_list]
        self.assertEqual(factory.call_count, 3)
        self.assertEqual(sent, [{**row["request"], "model": "open-jev"} for row in self.document["workloads"]])
        self.assertEqual(report["status"], "complete")
        self.assertEqual((report["started_requests"], report["attempted_requests"], report["pending_requests"],
                          report["in_flight_requests"]), (3, 3, 0, 0))
        self.assertEqual([row["request_id"] for row in self.read("attempts.jsonl")], ["0", "1", "2"])
        self.assertEqual((self.root / "run/requests.json").read_bytes(), self.path.read_bytes())
        self.assertIsNone(report["cost_usd"])
        with self.assertRaises(FileExistsError):
            self.collect()

    def test_rounding_distribution_is_retained_without_normalizing_or_pre_rejecting(self):
        responses = [response_for(row["request"]) for row in self.document["workloads"]]
        probabilities = {"z_on": .51, "a_off": .5}
        responses[1]["answers"]["decision"]["probabilities"] = probabilities
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            self.fake_http(factory, responses)
            report = self.collect()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(self.read("samples.jsonl")[1]["probs_as_returned"], probabilities)

    def test_identity_drift_fails_and_stops_before_next_dispatch(self):
        responses = [response_for(row["request"]) for row in self.document["workloads"]]
        responses[1]["metadata"]["checkpoint_sha256"] = "4" * 64
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            self.fake_http(factory, responses)
            report = self.collect()
        self.assertEqual(factory.call_count, 2)
        self.assertEqual((report["status"], report["failed_requests"], report["pending_requests"]),
                         ("stopped_fatal", 1, 1))
        self.assertEqual(self.read("samples.jsonl")[1]["error_type"], "IdentityError")

    def test_timeout_never_retries_and_keeps_pending_distinct(self):
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            factory.return_value.getresponse.side_effect = TimeoutError("still computing")
            report = self.collect()
        self.assertEqual(factory.call_count, 1)
        self.assertEqual((report["status"], report["failed_requests"], report["pending_requests"]),
                         ("stopped_fatal", 1, 2))

    def test_context_refusal_counts_failure_then_continues(self):
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            self.fake_http(factory, statuses=[422, 200, 200])
            report = self.collect()
        self.assertEqual((report["status"], report["attempted_requests"], report["failed_requests"]),
                         ("complete_with_request_failures", 3, 1))

    def test_bad_hash_or_identity_rejected_before_request_and_output(self):
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            with self.assertRaises(ValueError):
                benchmark.collect(self.path, "0" * 64, ENDPOINT, IDENTITY, self.root / "run")
            with self.assertRaises(ValueError):
                benchmark.collect(self.path, self.input_sha, ENDPOINT,
                                  {**IDENTITY, "code_commit": "main"}, self.root / "run")
            with self.assertRaises(ValueError):
                benchmark.collect(self.path, self.input_sha, "https://example.com/v1/systemone",
                                  IDENTITY, self.root / "run")
            factory.assert_not_called()
        self.assertFalse((self.root / "run").exists())

    def test_interruption_after_dispatch_leaves_an_in_flight_record(self):
        with patch.object(benchmark, "attempt", side_effect=SystemExit("simulated process stop")):
            with self.assertRaises(SystemExit):
                self.collect()
        report = json.loads((self.root / "run/report.json").read_bytes())
        self.assertEqual((report["started_requests"], report["attempted_requests"], report["in_flight_requests"],
                          report["pending_requests"]), (1, 0, 1, 2))
        self.assertEqual(len(self.read("attempts.jsonl")), 1)

    def test_duplicate_json_and_nonfinite_responses_fail_without_silent_repair(self):
        row = self.document["workloads"][0]
        for raw in (b'{"answers":{},"answers":{}}', b'{"value":NaN}', b'{"value":1e999}'):
            with self.subTest(raw=raw), patch.object(benchmark.http.client, "HTTPConnection") as factory:
                factory.return_value.getresponse.return_value = SimpleNamespace(status=200, read=lambda: raw)
                result = benchmark.attempt(row, ENDPOINT, IDENTITY, 10)
            self.assertFalse(result["success"])
            self.assertEqual(result["raw_response"], raw.decode())


@unittest.skipUnless(UPSTREAM.is_dir(), "requires the clean pinned JevBench checkout; no download in tests")
class PinnedJevBenchIntegrationTest(unittest.TestCase):
    collect = JevBenchOpenJevTest.collect

    def setUp(self):
        JevBenchOpenJevTest.setUp(self)
        self.upstream = benchmark.load_upstream(UPSTREAM)

    def test_pinned_public_counts_and_exact_requests_match_upstream_adapter(self):
        document = benchmark.request_document(self.upstream)
        self.assertEqual(len(document["workloads"]), 231)
        self.assertEqual(benchmark.sha256(benchmark.json_bytes(document)),
                         "2e20ff5f94dd04d015b3a7b9abd955757b6c5be25b55b97fcd141cb52f88b4aa")
        for task, row in zip(self.upstream.tasks, document["workloads"]):
            self.assertEqual(row["request"], {"state": task.state, "questions": {
                "decision": self.upstream.base.build_question(task)}})

    def test_exact_upstream_rounding_and_tie_rules(self):
        task = SimpleNamespace(labels=["z", "a"], expected="a", question={"type": "choice"})
        score = self.upstream.scoring.score_task
        self.assertTrue(score({"z": .5, "a": .5}, task)["correct"])
        rounded = score({"z": .5, "a": .51}, task)
        self.assertTrue(rounded["valid"])
        self.assertFalse(rounded["strict_valid"])
        self.assertTrue(rounded["renormalized"])
        self.assertAlmostEqual(sum(rounded["probs"].values()), 1)
        self.assertFalse(score({"z": .5, "a": .55}, task)["valid"])

    def test_public_summary_uses_gold_only_offline_and_accounts_for_pending(self):
        document = benchmark.request_document(self.upstream)
        self.path.write_bytes(benchmark.json_bytes(document))
        self.input_sha = benchmark.sha256(self.path.read_bytes())
        first = document["workloads"][0]
        good_response = response_for(first["request"])
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            factory.return_value.getresponse.side_effect = [
                SimpleNamespace(status=200, read=lambda: benchmark.json_bytes(good_response)),
                TimeoutError("still computing")]
            report = self.collect()
        self.assertEqual((report["attempted_requests"], report["failed_requests"], report["pending_requests"]),
                         (2, 1, 229))
        result = benchmark.summarize(UPSTREAM, self.root / "run")
        self.assertEqual((result["n_planned"], result["n_attempted"], result["pending_requests"]), (231, 2, 229))
        self.assertEqual(result["failed_requests"], 1)
        self.assertFalse(result["complete"])
        self.assertNotIn("composite", result)
        self.assertIsNone(result["price_per_1000_decisions_usd"])
        self.assertNotIn(first["id"], json.dumps(result))
        self.assertNotIn(first["request"]["state"], json.dumps(result))
        self.assertEqual(result["protocol"]["sum_tolerance_rounding"], .02)
        samples = (self.root / "run/samples.jsonl").read_text()
        with (self.root / "run/samples.jsonl").open("a") as stream:
            stream.write(samples.splitlines()[0] + "\n")
        with self.assertRaisesRegex(ValueError, "unique attempted prefix"):
            benchmark.summarize(UPSTREAM, self.root / "run")

    def test_completed_report_cannot_hide_a_partial_journal(self):
        self.path.write_bytes(benchmark.json_bytes(benchmark.request_document(self.upstream)))
        self.input_sha = benchmark.sha256(self.path.read_bytes())
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            factory.return_value.getresponse.side_effect = TimeoutError("fixture")
            self.collect()
        report_path = self.root / "run/report.json"
        report = json.loads(report_path.read_bytes())
        report.update(status="complete", planned_requests=231, started_requests=231, attempted_requests=231,
                      successful_requests=231, failed_requests=0, pending_requests=0, in_flight_requests=0)
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "Completed report counts"):
            benchmark.summarize(UPSTREAM, self.root / "run")

    def test_boolean_probability_cannot_be_rewritten_as_float_during_replay(self):
        document = benchmark.request_document(self.upstream)
        self.path.write_bytes(benchmark.json_bytes(document))
        self.input_sha = benchmark.sha256(self.path.read_bytes())
        index = next(i for i, row in enumerate(document["workloads"])
                     if row["request"]["questions"]["decision"]["type"] == "choice")
        responses = []
        for row in document["workloads"][:index + 1]:
            response = response_for(row["request"])
            if row["request"]["questions"]["decision"]["type"] == "choice":
                answer = response["answers"]["decision"]
                answer["probabilities"] = {key: position == 0 for position, key in enumerate(answer["probabilities"])}
            responses.append(SimpleNamespace(status=200, read=lambda body=benchmark.json_bytes(response): body))
        with patch.object(benchmark.http.client, "HTTPConnection") as factory:
            factory.return_value.getresponse.side_effect = [*responses, TimeoutError("fixture")]
            self.collect()
        path = self.root / "run/samples.jsonl"
        samples = [json.loads(line) for line in path.read_text().splitlines()]
        sample = samples[index]
        sample["response"]["answers"]["decision"]["probabilities"] = {key: float(value) for key, value in sample["probs_as_returned"].items()}
        sample["probs_as_returned"] = sample["response"]["answers"]["decision"]["probabilities"]
        path.write_text("".join(json.dumps(row) + "\n" for row in samples))
        with self.assertRaisesRegex(ValueError, "Saved response evidence differs"):
            benchmark.summarize(UPSTREAM, self.root / "run")


if __name__ == "__main__":
    unittest.main()
