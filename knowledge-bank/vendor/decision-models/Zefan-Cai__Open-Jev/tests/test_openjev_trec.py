"""CPU fixtures for frozen Open-Jev TREC collection; no model, qrels or remote API."""
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import evaluate_openjev_trec as runner
from tests.test_trec_provider import fixture

EXPECTED = {"model": "Qwen/Qwen3.5-2B", "method": "lora_decision_head",
            "base_revision": "1" * 40, "checkpoint_sha256": "2" * 64,
            "temperature": 1.25, "code_commit": "3" * 40, "max_length": 16384}
ENDPOINT = "http://127.0.0.1:8791/v1/systemone"


def sample_for(workload, expected=EXPECTED, *, special_last=False):
    answers = {}
    for index, qid in enumerate(workload["request"]["questions"]):
        text = workload["request"]["state"]["passages"][f"P{index + 1}"]
        value = .5004 if special_last and text == "passage 99" else .5
        answers[qid] = {"type": "score", "score": value,
                        "probabilities": {"0": 1 - value, "1": value, "2": 0.0, "3": 0.0}}
    response = {"model": expected["model"], "usage": {"input_tokens": 10, "output_tokens": 0},
                "metadata": {**{k: v for k, v in expected.items() if k != "model"}, "prefix_cache": {"enabled": False}},
                "answers": answers}
    raw = json.dumps(response)
    return {"request_id": workload["id"], "request_sha256": workload["request_sha256"], "mode": expected["model"],
            "phase": "measured", "repetition": 0, "transport": "http_loopback_fresh_connection", "success": True,
            "http_status": 200, "wall_ms": 12, "started_at": "2026-09-21T00:00:00+00:00",
            "response": response, "raw_response": raw, "response_bytes": len(raw.encode())}


class OpenJevTrecTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input = self.root / "input.json"
        self.input.write_text(json.dumps(fixture()))
        self.input_sha = hashlib.sha256(self.input.read_bytes()).hexdigest()
        self.output = self.root / "run"

    def execute(self, attempt=None, **limits):
        return runner.run(self.input, self.input_sha, ENDPOINT, EXPECTED, self.output,
                          attempt_fn=attempt or (lambda workload, *_: sample_for(workload)), **limits)

    def records(self, name):
        return [json.loads(line) for line in (self.output / name).read_bytes().splitlines() if line.strip()]

    def test_adaptive_float_scores_and_journal_precede_each_actual_request(self):
        calls = []

        def attempt(workload, endpoint, expected, timeout):
            journal, samples = self.records("requests.jsonl"), self.records("samples.jsonl")
            report = json.loads((self.output / "report.json").read_bytes())
            self.assertEqual((len(journal), len(samples)), (len(calls) + 1, len(calls)))
            self.assertEqual((report["started_requests"], report["attempted_requests"], report["in_flight_requests"]),
                             (len(calls) + 1, len(calls), 1))
            self.assertEqual(journal[-1]["id"], workload["id"])
            payload = journal[-1]["payload"]
            self.assertEqual(list(payload), ["state", "questions", "model"])
            self.assertEqual(list(payload["state"]), ["query", "passages"])
            self.assertEqual(payload["model"], "open-jev")
            self.assertEqual(journal[-1]["request_sha256"], runner.client.digest(workload["request"]))
            self.assertEqual(journal[-1]["payload_sha256"], runner.client.digest(payload))
            self.assertEqual(endpoint, ENDPOINT)
            self.assertEqual(expected, EXPECTED)
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 300)
            calls.append(copy.deepcopy(workload))
            return sample_for(workload, expected, special_last=True)

        report = self.execute(attempt, max_requests=9)
        self.assertEqual(report["status"], "stopped_budget")
        self.assertEqual(report["query_status_counts"], {"complete": 1, "pending": 96})
        first = report["queries"][0]
        self.assertEqual(first["ranking"][0], "d99")
        self.assertTrue(first["strict_query_valid"])
        self.assertEqual(len(first["windows"]), 9)
        second_texts = list(calls[1]["request"]["state"]["passages"].values())
        self.assertIn("passage 99", second_texts)
        self.assertNotIn("passage 89", second_texts)
        self.assertIsNone(report["score_rounding_digits"])
        self.assertNotIn("supplemental_ranking", first)
        self.assertFalse(report["qrels_read"])
        self.assertFalse(report["truncation_applied_by_runner"])
        self.assertFalse(report["new_accuracy_metrics"])
        self.assertFalse(report["prefix_cache"])
        self.assertEqual(report["in_flight_requests"], 0)
        self.assertEqual((self.output / "input.json").read_bytes(), self.input.read_bytes())

    def test_all_97_queries_close_in_873_unique_requests_with_stable_ties(self):
        report = self.execute()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["query_status_counts"], {"complete": 97})
        self.assertEqual((report["started_requests"], report["attempted_requests"], report["successful_requests"]), (873, 873, 873))
        self.assertEqual((report["failed_requests"], report["pending_queries"], report["in_flight_requests"]), (0, 0, 0))
        self.assertEqual(len({row["id"] for row in self.records("requests.jsonl")}), 873)
        for query in report["queries"]:
            self.assertEqual(query["ranking"], [f"d{i}" for i in range(100)])
            self.assertEqual(len(query["request_ids"]), 9)
            self.assertEqual(len(query["windows"]), 9)
        self.assertEqual(report["source_sha256"], runner.source_hashes())

    def test_nonfatal_invalid_probability_is_saved_as_failure_then_next_query_runs(self):
        calls = []

        def attempt(workload, endpoint, expected, timeout):
            sample = sample_for(workload)
            if not calls:
                next(iter(sample["response"]["answers"].values()))["probabilities"]["0"] = .49
                sample["raw_response"] = json.dumps(sample["response"])
            calls.append(workload["id"])
            return sample

        report = self.execute(attempt, max_requests=10)
        self.assertEqual(report["query_status_counts"], {"failed": 1, "complete": 1, "pending": 95})
        self.assertFalse(report["queries"][0]["strict_query_valid"])
        self.assertIsNone(report["queries"][0]["ranking"])
        sample = self.records("samples.jsonl")[0]
        self.assertFalse(sample["success"])
        self.assertEqual(sample["error"], "probabilities do not sum to one")
        self.assertEqual(next(iter(sample["response"]["answers"].values()))["probabilities"]["0"], .49)
        self.assertEqual((report["failed_requests"], report["successful_requests"]), (1, 9))

    def test_identity_drift_and_timeout_stop_without_advancing(self):
        for problem in ("identity", "timeout", "interrupt"):
            with self.subTest(problem=problem):
                self.output = self.root / problem
                calls = []

                def attempt(workload, *_):
                    calls.append(workload["id"])
                    if problem == "timeout":
                        raise TimeoutError("handler may still be computing")
                    if problem == "interrupt":
                        raise KeyboardInterrupt("interrupted during dispatch")
                    sample = sample_for(workload)
                    sample["response"]["metadata"]["checkpoint_sha256"] = "4" * 64
                    sample["raw_response"] = json.dumps(sample["response"])
                    return sample

                report = self.execute(attempt)
                self.assertEqual(len(calls), 1)
                self.assertEqual(report["status"], "stopped_fatal")
                self.assertEqual(report["query_status_counts"], {"failed_fatal": 1, "pending": 96})
                self.assertIsNone(report["queries"][0]["ranking"])
                self.assertFalse(report["queries"][0]["strict_query_valid"])
                self.assertEqual(report["in_flight_requests"], 0)
                self.assertTrue(self.records("samples.jsonl")[0]["fatal"])

    def test_out_of_range_scalar_is_failed_before_persisting_success(self):
        for scalar, level in ((-1e-9, 0), (3 + 1e-9, 3)):
            with self.subTest(scalar=scalar):
                self.output = self.root / f"scalar-{level}"
                calls = []

                def attempt(workload, *_):
                    sample = sample_for(workload)
                    if not calls:
                        answer = next(iter(sample["response"]["answers"].values()))
                        answer.update(score=scalar, probabilities={str(i): float(i == level) for i in range(4)})
                        sample["raw_response"] = json.dumps(sample["response"])
                    calls.append(workload["id"])
                    return sample

                report = self.execute(attempt, max_requests=10)
                self.assertEqual(report["query_status_counts"], {"failed": 1, "complete": 1, "pending": 95})
                self.assertEqual((report["failed_requests"], report["successful_requests"]), (1, 9))
                sample = self.records("samples.jsonl")[0]
                self.assertFalse(sample["success"])
                self.assertEqual(sample["error"], "Invalid typed numeric answer")
                self.assertEqual(next(iter(sample["response"]["answers"].values()))["score"], scalar)
                self.assertIsNone(report["queries"][0]["ranking"])

    def test_raw_response_binding_preserves_numeric_types_and_mapping_order(self):
        for mutation in ("boolean", "order"):
            with self.subTest(mutation=mutation):
                self.output = self.root / mutation

                def attempt(workload, *_):
                    sample = sample_for(workload)
                    raw_value = json.loads(sample["raw_response"])
                    answer = next(iter(raw_value["answers"].values()))
                    if mutation == "boolean":
                        answer["probabilities"]["2"] = False
                    else:
                        answer["probabilities"] = dict(reversed(list(answer["probabilities"].items())))
                    sample["raw_response"] = json.dumps(raw_value)
                    return sample

                report = self.execute(attempt, max_requests=1)
                self.assertEqual(report["queries"][0]["status"], "failed")
                self.assertIsNone(report["queries"][0]["ranking"])
                sample = self.records("samples.jsonl")[0]
                self.assertFalse(sample["success"])
                self.assertEqual(sample["error"], "Successful sample does not match its HTTP response")

    def test_request_and_time_budgets_keep_incomplete_and_unattempted_queries(self):
        for kind in ("request", "time"):
            self.output = self.root / kind
            ticks = [0.0]

            def attempt(workload, *_):
                ticks[0] += 2
                return sample_for(workload)

            limits = {"max_requests": 1} if kind == "request" else {"max_seconds": 1}
            report = self.execute(attempt, clock=lambda: ticks[0], **limits)
            self.assertEqual(report["status"], "stopped_budget")
            self.assertEqual(report["stop_reason"], kind + "_budget")
            self.assertEqual(report["query_status_counts"], {"incomplete_budget": 1, "pending": 96})
            self.assertEqual(report["pending_queries"], 97)
            self.assertEqual(report["attempted_requests"], 1)
            self.assertIsNone(report["queries"][0]["ranking"])
            self.assertEqual(len(report["queries"][0]["windows"]), 1)

    def test_all_failed_queries_remain_full_denominator_without_extra_requests(self):
        def attempt(workload, *_):
            sample = sample_for(workload)
            sample.update(success=False, http_status=413, error="HTTP 413; context too long", raw_response='{"error":"too long"}')
            sample.pop("response")
            return sample

        report = self.execute(attempt)
        self.assertEqual(report["status"], "completed_with_query_failures")
        self.assertEqual(report["query_status_counts"], {"failed": 97})
        self.assertEqual(report["attempted_requests"], 97)
        self.assertEqual(report["pending_queries"], 0)
        self.assertTrue(all(q["ranking"] is None for q in report["queries"]))

    def test_http_server_failure_stops_and_bad_preflight_never_connects(self):
        def attempt(workload, *_):
            sample = sample_for(workload)
            sample.update(success=False, http_status=500, raw_response='{"error":"failed"}', error="HTTP 500")
            sample.pop("response")
            return sample

        report = self.execute(attempt)
        self.assertEqual((report["status"], report["attempted_requests"]), ("stopped_fatal", 1))
        with patch.object(runner.client, "attempt") as request:
            for kwargs in ({"max_requests": 874}, {"max_requests": True}, {"timeout": 301},
                           {"max_seconds": 10801}, {"timeout": float("nan")}):
                with self.assertRaises(ValueError):
                    runner.run(self.input, self.input_sha, ENDPOINT, EXPECTED, self.root / "bad", **kwargs)
            with self.assertRaises(ValueError):
                runner.run(self.input, "0" * 64, ENDPOINT, EXPECTED, self.root / "bad")
            with self.assertRaises(ValueError):
                runner.run(self.input, self.input_sha, "https://example.com/v1/inference", EXPECTED, self.root / "bad")
            with self.assertRaises(ValueError):
                runner.run(self.input, self.input_sha, ENDPOINT, {**EXPECTED, "code_commit": "main"}, self.root / "bad")
            with self.assertRaises(FileExistsError):
                runner.run(self.input, self.input_sha, ENDPOINT, EXPECTED, self.output)
            request.assert_not_called()
        self.assertFalse((self.root / "bad").exists())

    def serve(self, *, blocked=False):
        arrived, release = threading.Event(), threading.Event()
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(payload)
                arrived.set()
                if blocked:
                    release.wait(timeout=10)
                workload = {"id": "unused", "request_sha256": "unused", "request": payload}
                body = sample_for(workload, special_last=True)["raw_response"].encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            release.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.addCleanup(cleanup)
        return f"http://127.0.0.1:{server.server_port}/v1/systemone", arrived, requests

    def test_real_loopback_uses_owned_service_and_unrounded_expected_scores(self):
        document = fixture()
        document["queries"][0]["query"] = "Retain the frozen replacement character: \ufffd"
        document["queries"][0]["documents"][98]["text"] = "passage 98 \ufffd " + "unchanged " * 129
        self.input.write_text(json.dumps(document, ensure_ascii=False))
        self.input_sha = hashlib.sha256(self.input.read_bytes()).hexdigest()
        endpoint, _, requests = self.serve()
        report = runner.run(self.input, self.input_sha, endpoint, EXPECTED, self.output, max_requests=9)
        self.assertEqual(len(requests), 9)
        self.assertTrue(all(set(request) == {"state", "questions", "model"} for request in requests))
        self.assertEqual(requests[0]["state"]["query"], document["queries"][0]["query"])
        self.assertEqual(requests[0]["state"]["passages"]["P19"], document["queries"][0]["documents"][98]["text"])
        self.assertEqual(report["queries"][0]["ranking"][0], "d99")
        self.assertEqual(report["successful_requests"], 9)
        self.assertTrue(all(s["success"] and json.loads(s["raw_response"]) == s["response"] for s in self.records("samples.jsonl")))

    def test_sigterm_settles_failed_dispatch_but_sigkill_leaves_unknown_outcome(self):
        for terminate in (True, False):
            with self.subTest(terminate=terminate):
                self.output = self.root / ("sigterm" if terminate else "sigkill")
                endpoint, arrived, requests = self.serve(blocked=True)
                command = [sys.executable, "-m", "scripts.evaluate_openjev_trec", "--input", str(self.input),
                           "--input-sha256", self.input_sha, "--endpoint", endpoint, "--output", str(self.output)]
                for key, value in EXPECTED.items():
                    command.extend(["--expected-" + key.replace("_", "-"), str(value)])
                process = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    self.assertTrue(arrived.wait(timeout=5))
                    self.assertEqual(len(self.records("requests.jsonl")), 1)
                    (process.terminate if terminate else process.kill)()
                    stdout, stderr = process.communicate(timeout=5)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate(timeout=5)
                self.assertEqual(len(requests), 1)
                report = json.loads((self.output / "report.json").read_bytes())
                if terminate:
                    self.assertEqual(process.returncode, 1, stderr.decode())
                    self.assertEqual(report["status"], "stopped_fatal")
                    self.assertEqual((report["started_requests"], report["attempted_requests"], report["in_flight_requests"]), (1, 1, 0))
                    self.assertEqual(report["queries"][0]["status"], "failed_fatal")
                    sample = self.records("samples.jsonl")[0]
                    self.assertEqual(sample["error_type"], "KeyboardInterrupt")
                    self.assertTrue(sample["fatal"])
                else:
                    self.assertLess(process.returncode, 0)
                    self.assertEqual(report["status"], "running")
                    self.assertEqual((report["started_requests"], report["attempted_requests"], report["in_flight_requests"]), (1, 0, 1))
                    self.assertEqual(self.records("samples.jsonl"), [])


if __name__ == "__main__":
    unittest.main()
