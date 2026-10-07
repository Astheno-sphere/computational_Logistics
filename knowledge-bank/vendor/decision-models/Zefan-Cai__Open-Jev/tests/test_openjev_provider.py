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
from unittest.mock import Mock, patch

from jev.api import compile_request, format_response
from jev.server import make_server
from scripts import evaluate_openjev_provider as provider
from scripts.summarize_provider_quality import summarize


EXPECTED = {"model": "Qwen/Qwen3.5-2B", "method": "lora_decision_head",
            "base_revision": "1" * 40, "checkpoint_sha256": "2" * 64,
            "temperature": 1.25, "code_commit": "3" * 40, "max_length": 16384}
REQUEST = {"state": "The lamp is on.", "questions": {
    "choice": {"type": "choice", "instructions": "Select the matching state.",
               "criteria": {"off": "The lamp is off.", "on": "The lamp is on."}},
    "boolean": {"type": "noul", "instructions": "Is the lamp on?"},
    "score": {"type": "score", "instructions": "How certain is the lamp state?",
              "criteria": ["uncertain", "likely", "certain"]}}}


def response_for(request):
    response = format_response(compile_request(request["state"], request["questions"]),
                               [[.2, .8], [.2, .8], [.1, .3, .6]])
    response.update(model=EXPECTED["model"], usage={"input_tokens": 99, "output_tokens": 0},
                    metadata={**{k: v for k, v in EXPECTED.items() if k != "model"},
                              "prefix_cache": {"enabled": False}})
    return response


class Predictor:
    model_name, method = EXPECTED["model"], EXPECTED["method"]

    def __init__(self, transform=None):
        self.requests = []
        self.transform = transform

    def predict(self, request):
        self.requests.append(copy.deepcopy(request))
        response = response_for(request)
        if self.transform:
            self.transform(response, len(self.requests))
        return response


class OpenJevProviderTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def fixture(self, count=3):
        workloads = [{"id": str(i), "request": copy.deepcopy(REQUEST),
                      "request_sha256": provider.digest(REQUEST)} for i in range(count)]
        path = self.root / "requests.json"
        path.write_text(json.dumps({"schema_version": 1, "workloads": workloads}))
        return path, hashlib.sha256(path.read_bytes()).hexdigest(), workloads

    def serve(self, predictor):
        server = make_server(predictor, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.addCleanup(cleanup)
        return f"http://127.0.0.1:{server.server_port}/v1/systemone"

    def gold(self, workloads):
        return [{"request_id": row["id"], "request_sha256": row["request_sha256"],
                 "question_id": qid, "kind": kind, "answer_keys": keys, "target": target,
                 "source": "fixture", "split": "test", "group_id": row["id"]}
                for row in workloads for qid, kind, keys, target in (
                    ("choice", "choice", ["off", "on"], 1),
                    ("boolean", "noul", ["false", "true"], 1),
                    ("score", "score", ["0", "1", "2"], 2))]

    def test_real_loopback_more_than_32_workloads_one_attempt_and_existing_quality_scorer(self):
        path, sha, workloads = self.fixture(45)
        predictor = Predictor()
        output = self.root / "result"
        report = provider.run(path, sha, self.serve(predictor), EXPECTED, output)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["attempted_requests"], 45)
        self.assertEqual(report["pending_requests"], 0)
        self.assertEqual((report["started_requests"], report["in_flight_requests"]), (45, 0))
        self.assertEqual((output / "requests.json").read_bytes(), path.read_bytes())
        self.assertEqual(predictor.requests, [{**REQUEST, "model": "open-jev"}] * 45)
        samples = [json.loads(line) for line in (output / "samples.jsonl").read_text().splitlines()]
        self.assertEqual([s["request_id"] for s in samples], [w["id"] for w in workloads])
        journal = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
        self.assertEqual([s["request_id"] for s in journal], [w["id"] for w in workloads])
        self.assertTrue(all(s["phase"] == "measured" and s["repetition"] == 0 for s in samples))
        self.assertTrue(all(json.loads(s["raw_response"]) == s["response"] for s in samples))
        quality = summarize(self.gold(workloads), samples)
        self.assertEqual(quality["status"], "complete")
        self.assertEqual(quality["overall"]["hard_correct"], 135)
        with self.assertRaises(FileExistsError):
            provider.run(path, sha, self.serve(Predictor()), EXPECTED, output)
        self.assertEqual(len(predictor.requests), 45)

    def test_invalid_probability_is_retained_and_counts_zero_without_renormalization(self):
        path, sha, workloads = self.fixture()

        def alter(response, number):
            if number == 2:
                response["answers"]["choice"]["probabilities"]["off"] = .19
        output = self.root / "result"
        report = provider.run(path, sha, self.serve(Predictor(alter)), EXPECTED, output)
        self.assertEqual(report["status"], "complete_with_request_failures")
        samples = [json.loads(line) for line in (output / "samples.jsonl").read_text().splitlines()]
        self.assertEqual(samples[1]["error"], "probabilities do not sum to one")
        self.assertEqual(samples[1]["response"]["answers"]["choice"]["probabilities"]["off"], .19)
        quality = summarize(self.gold(workloads), samples)
        self.assertEqual(quality["overall"]["hard_correct"], 6)
        self.assertEqual(quality["overall"]["hard_targets"], 9)
        self.assertEqual(quality["overall"]["errors"], 3)

    def test_checkpoint_drift_stops_before_next_request_and_preserves_pending(self):
        path, sha, workloads = self.fixture()

        def alter(response, number):
            if number == 2:
                response["metadata"]["checkpoint_sha256"] = "4" * 64
        predictor = Predictor(alter)
        output = self.root / "result"
        report = provider.run(path, sha, self.serve(predictor), EXPECTED, output)
        self.assertEqual((report["status"], report["attempted_requests"], report["pending_requests"]),
                         ("stopped_fatal", 2, 1))
        samples = [json.loads(line) for line in (output / "samples.jsonl").read_text().splitlines()]
        self.assertEqual(samples[1]["error_type"], "IdentityError")
        quality = summarize(self.gold(workloads), samples)
        self.assertEqual(quality["pending_count"], 3)
        self.assertEqual(quality["overall"]["errors"], 3)
        self.assertEqual(len(predictor.requests), 2)

    def test_timeout_never_retries_or_advances(self):
        path, sha, _ = self.fixture()
        with patch.object(provider.http.client, "HTTPConnection") as factory:
            factory.return_value.getresponse.side_effect = TimeoutError("still computing")
            report = provider.run(path, sha, "http://127.0.0.1:8791/v1/systemone", EXPECTED, self.root / "result")
        self.assertEqual(factory.call_count, 1)
        factory.return_value.close.assert_called_once()
        self.assertEqual((report["status"], report["pending_requests"]), ("stopped_fatal", 2))

    def test_bad_input_or_identity_fails_before_connection_or_outputs(self):
        path, sha, workloads = self.fixture()
        endpoint = "http://127.0.0.1:8791/v1/systemone"
        with patch.object(provider.http.client, "HTTPConnection") as factory:
            with self.assertRaises(ValueError):
                provider.run(path, "0" * 64, endpoint, EXPECTED, self.root / "result")
            with self.assertRaises(ValueError):
                provider.run(path, sha, endpoint, {**EXPECTED, "code_commit": "main"}, self.root / "result")
            for bad in ("http://example.com:8791/v1/systemone", "https://127.0.0.1:8791/v1/systemone",
                        "http://token@127.0.0.1:8791/v1/systemone", endpoint + "?key=x"):
                with self.assertRaises(ValueError):
                    provider.run(path, sha, bad, EXPECTED, self.root / "result")
            factory.assert_not_called()
        self.assertFalse((self.root / "result").exists())
        workloads[1]["id"] = workloads[0]["id"]
        path.write_text(json.dumps({"schema_version": 1, "workloads": workloads}))
        with self.assertRaisesRegex(ValueError, "unique"):
            provider.load_workloads(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_malformed_inputs_and_request_hashes_are_rejected(self):
        path, _, workloads = self.fixture()
        for mode in ("gold_in_payload", "changed_hash", "duplicate_json"):
            changed = copy.deepcopy(workloads)
            if mode == "gold_in_payload":
                changed[0]["request"]["target"] = 1
            elif mode == "changed_hash":
                changed[0]["request"]["state"] = "modified"
            raw = json.dumps({"schema_version": 1, "workloads": changed}).encode()
            if mode == "duplicate_json":
                raw = raw.replace(b'"state":', b'"state": "duplicate", "state":', 1)
            path.write_bytes(raw)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                provider.load_workloads(path, hashlib.sha256(raw).hexdigest())

    def test_response_invariants_reject_cache_identity_and_inconsistent_scalar(self):
        mutations = [lambda r: r["metadata"]["prefix_cache"].update(enabled=True),
                     lambda r: r["metadata"].update(temperature=2),
                     lambda r: r["metadata"].update(code_commit="4" * 40),
                     lambda r: r["metadata"].update(prefix_cache=None),
                     lambda r: r.update(model="another-model"),
                     lambda r: r["answers"]["score"].update(score=.01),
                     lambda r: r["answers"]["boolean"].update(noul=True),
                     lambda r: r["answers"]["choice"].update(probabilities={"on": .8, "off": .2}),
                     lambda r: r["usage"].update(input_tokens=True)]
        for index, mutate in enumerate(mutations):
            response = response_for(REQUEST)
            mutate(response)
            with self.subTest(index=index), self.assertRaises(ValueError):
                provider.validate_response(REQUEST, response, EXPECTED)

    def test_nonfinite_wire_response_is_retained_without_invalid_json_in_output(self):
        path, sha, _ = self.fixture(1)
        received = Mock(status=200)
        received.read.return_value = b'{"value":1e999}'
        with patch.object(provider.http.client, "HTTPConnection") as factory:
            factory.return_value.getresponse.return_value = received
            report = provider.run(path, sha, "http://127.0.0.1:8791/v1/systemone", EXPECTED, self.root / "result")
        sample = json.loads((self.root / "result/samples.jsonl").read_bytes())
        self.assertFalse(sample["success"])
        self.assertNotIn("response", sample)
        self.assertEqual(sample["raw_response"], '{"value":1e999}')
        self.assertEqual(report["failed_requests"], 1)

    def test_budget_stops_without_an_attempt_and_preserves_all_pending(self):
        path, sha, _ = self.fixture()
        with patch.object(provider.time, "monotonic", side_effect=[0, 0, 10, 10]), \
                patch.object(provider, "attempt") as attempt:
            report = provider.run(path, sha, "http://127.0.0.1:8791/v1/systemone", EXPECTED,
                                  self.root / "result", max_seconds=1)
        attempt.assert_not_called()
        self.assertEqual((report["status"], report["pending_requests"]), ("stopped_budget", 3))

    def interrupt_live_client(self, hard_kill):
        path, sha, _ = self.fixture()
        seen, release = threading.Event(), threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                seen.set()
                release.wait(15)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        output = self.root / "result"
        command = [sys.executable, "-m", "scripts.evaluate_openjev_provider", "--requests", str(path),
                   "--input-sha256", sha, "--output", str(output), "--endpoint",
                   f"http://127.0.0.1:{server.server_port}/v1/systemone"]
        for key, value in EXPECTED.items():
            command.extend(["--expected-" + key.replace("_", "-"), str(value)])
        process = subprocess.Popen(command, cwd=Path(provider.__file__).resolve().parents[1],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(seen.wait(10), "Client never reached CPU fixture server")
            process.kill() if hard_kill else process.terminate()
            stdout, stderr = process.communicate(timeout=10)
            report = json.loads((output / "report.json").read_bytes())
            samples = [json.loads(line) for line in (output / "samples.jsonl").read_text().splitlines()]
            journal = [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]
            self.assertEqual(len(journal), 1)
            self.assertEqual(report["started_requests"], 1)
            self.assertEqual(report["pending_requests"], 2)
            if hard_kill:
                self.assertEqual(len(samples), 0)
                self.assertEqual(report["in_flight_requests"], 1)
                self.assertNotEqual(report["status"], "complete")
            else:
                self.assertEqual(process.returncode, 1, stdout + stderr)
                self.assertEqual(report["status"], "stopped_fatal")
                self.assertEqual(report["in_flight_requests"], 0)
                self.assertEqual(report["attempted_requests"], 1)
                self.assertFalse(samples[0]["success"])
                self.assertTrue(samples[0]["fatal"])
                self.assertEqual(samples[0]["error_type"], "KeyboardInterrupt")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            release.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_sigterm_retains_dispatched_request_as_failed_not_pending(self):
        self.interrupt_live_client(False)

    def test_sigkill_leaves_durable_inflight_dispatch_not_unattempted(self):
        self.interrupt_live_client(True)


if __name__ == "__main__":
    unittest.main()
