import base64
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from jev.api import compile_request, format_response
from jev.case_browser import browser_teacher, generate_cases
from scripts.evaluate_browser_service import (encoded, head_counts, run_evaluation,
                                              score_response, select_cases, service_identity,
                                              sha256, validate_case)


def fixture_response(request):
    """Test-server fixture only; the production evaluator has no oracle backend."""
    records = compile_request(request["state"], request["questions"])
    active = browser_teacher(request["state"])
    response = format_response(records, [[float(key == active.get(record["id"], record["answer_keys"][0]))
                                         for key in record["answer_keys"]] for record in records])
    response.update(model="test/model", metadata={"method": "lora_decision_head", "temperature": 1.0,
                    "base_revision": "a" * 40, "checkpoint_sha256": "b" * 64, "code_commit": "c" * 40,
                    "max_length": 16384, "candidate_sequences": sum(len(r["options"]) for r in records)})
    return response


def choose(answer, key):
    answer["choice"] = key
    answer["probabilities"] = {candidate: float(candidate == key) for candidate in answer["probabilities"]}


class FixtureServer:
    def __init__(self, modes):
        self.modes, self.bodies = modes, []

    def __enter__(self):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                mode = owner.modes[len(owner.bodies)]
                owner.bodies.append(body)
                if mode == "disconnect":
                    self.close_connection = True
                    return
                response = fixture_response(json.loads(body))
                if mode == "schema":
                    del response["answers"][next(iter(response["answers"]))]
                elif mode == "confidence":
                    del response["answers"]["operation"]["confidence"]
                elif mode == "wrong_operation":
                    answer = response["answers"]["operation"]
                    choose(answer, next(key for key in answer["probabilities"] if key != answer["choice"]))
                elif mode == "identity":
                    response["metadata"]["checkpoint_sha256"] = "d" * 64
                payload = b"not-json" if mode == "bad_json" else encoded(response)
                if mode == "http_error":
                    payload = b'{"error":"test fixture failure"}'
                self.send_response(503 if mode == "http_error" else 200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/v1/systemone"
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class BrowserServiceEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = generate_cases(groups=12, ood_groups=3)
        for case in cls.cases:
            if case["split"] != "ood":
                case["split"] = "test"

    def write_source(self, directory):
        source = Path(directory) / "cases.jsonl"
        source.write_bytes(b"".join(encoded(case) + b"\n" for case in self.cases))
        source.with_name("manifest.json").write_bytes(encoded({"cases_file": source.name,
            "cases_sha256": sha256(source.read_bytes()), "case_count": len(self.cases)}))
        return source

    def test_selection_is_label_independent_grouped_balanced_and_order_invariant(self):
        selected = select_cases(self.cases, parents_per_split=2, variants_per_parent=3, max_cases=5)
        self.assertEqual([case["split"] for case in selected], ["test", "ood", "test", "ood", "test"])
        self.assertEqual(len({case["group_id"] for case in selected}), 4)
        poisoned = copy.deepcopy(self.cases)
        for case in poisoned:
            case["active_answers"] = object()
        changed = select_cases(list(reversed(poisoned)), parents_per_split=2, variants_per_parent=3, max_cases=5)
        self.assertEqual([case["id"] for case in selected], [case["id"] for case in changed])
        leaked = copy.deepcopy(self.cases[0])
        leaked.update(id=leaked["id"] + "-leak", split="ood")
        with self.assertRaisesRegex(ValueError, "parent group crosses"):
            select_cases([*self.cases, leaked], parents_per_split=1)

    def test_active_heads_are_scored_even_for_wrong_operation_and_forced_heads_are_separate(self):
        case = next(case for case in self.cases if case["active_answers"]["operation"] == "TYPE_TEXT"
                    and case["variant"] == "observed")
        records = validate_case(case)
        response = fixture_response(case["request"])
        # Any valid inactive predictions are permitted; there is no inactive gold.
        for key, answer in response["answers"].items():
            if key not in case["active_answers"]:
                choose(answer, list(answer["probabilities"])[-1])
        correct, _ = score_response(case, response, records)
        self.assertEqual(correct, {"operation": 1, "proposal_exact": 1, "active_conditional": 2, "forced_active_conditional": 0})
        choose(response["answers"]["operation"], "WAIT")
        correct, _ = score_response(case, response, records)
        self.assertEqual(correct, {"operation": 0, "proposal_exact": 0, "active_conditional": 2, "forced_active_conditional": 0})
        forced = next(case for case in self.cases if case["variant"] == "single_candidate_target"
                      and case["active_answers"]["operation"] == "TYPE_TEXT")
        counts = head_counts(forced, validate_case(forced))
        self.assertEqual({key: len(value) for key, value in counts.items()}, {"active_conditional": 1, "forced_active_conditional": 1})
        missing = fixture_response(case["request"])
        del missing["answers"][next(key for key in missing["answers"] if key not in case["active_answers"])]
        with self.assertRaises(ValueError):
            score_response(case, missing, records)

    def test_confidence_is_required_and_consistent_even_on_inactive_heads(self):
        case = next(case for case in self.cases if case["active_answers"]["operation"] == "TYPE_TEXT"
                    and case["variant"] == "observed")
        records = validate_case(case)
        inactive = next(key for key in records if key not in case["active_answers"])
        for key in ("operation", inactive):
            for value in (None, "1", 2, 0, True):
                with self.subTest(key=key, value=value):
                    response = fixture_response(case["request"])
                    if value is None:
                        del response["answers"][key]["confidence"]
                    else:
                        response["answers"][key]["confidence"] = value
                    with self.assertRaisesRegex(ValueError, "confidence"):
                        score_response(case, response, records)

    def test_real_http_failures_remain_in_denominators_and_wire_bytes_are_retained(self):
        modes = ["ok", "http_error", "bad_json", "schema", "wrong_operation", "disconnect", "confidence"]
        with tempfile.TemporaryDirectory() as directory, FixtureServer(modes) as server:
            source = self.write_source(directory)
            output = Path(directory) / "eval"
            report = run_evaluation(source, output, endpoint=server.endpoint, splits=("test",),
                                    parents_per_split=1, variants_per_parent=7, expected_model="test/model")
            self.assertEqual(report["status"], "complete_with_errors")
            self.assertTrue(report["complete"])
            self.assertEqual((report["selected_cases"], report["attempted_cases"], report["error_cases"]), (7, 7, 5))
            self.assertEqual(report["overall"]["metrics"]["operation"], {"correct": 1, "total": 7, "accuracy": 1/7})
            self.assertEqual(report["overall"]["metrics"]["proposal_exact"]["correct"], 1)
            self.assertEqual(report["status_counts"], {"ok": 2, "http_error": 2, "schema_error": 3})
            requests = [json.loads(line) for line in (output / "requests.jsonl").read_text().splitlines()]
            outcomes = [json.loads(line) for line in (output / "outcomes.jsonl").read_text().splitlines()]
            for body, request, outcome in zip(server.bodies, requests, outcomes):
                self.assertEqual(body, request["request_json"].encode())
                self.assertEqual(sha256(body), request["request_body_sha256"])
                self.assertEqual(request["request_body_sha256"], outcome["request_body_sha256"])
                self.assertEqual(set(json.loads(body)), {"model", "state", "questions"})
                self.assertEqual(sha256(base64.b64decode(outcome["response_body_base64"])), outcome["response_body_sha256"])
            self.assertEqual(base64.b64decode(outcomes[2]["response_body_base64"]), b"not-json")
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                run_evaluation(source, output)
            source.write_bytes(source.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "checksum/count"):
                run_evaluation(source, Path(directory) / "changed", parents_per_split=1)

    def test_identity_drift_and_missing_checkpoint_are_failures(self):
        case = self.cases[0]
        response = fixture_response(case["request"])
        del response["metadata"]["checkpoint_sha256"]
        with self.assertRaisesRegex(ValueError, "checkpoint SHA-256"):
            service_identity(response, validate_case(case), {})
        with tempfile.TemporaryDirectory() as directory, FixtureServer(["ok", "identity"]) as server:
            report = run_evaluation(self.write_source(directory), Path(directory) / "eval", endpoint=server.endpoint,
                                    splits=("test",), parents_per_split=1, variants_per_parent=2)
            self.assertEqual(report["status_counts"], {"ok": 1, "identity_error": 1})
            self.assertEqual(report["overall"]["metrics"]["operation"]["total"], 2)
            self.assertEqual(report["overall"]["metrics"]["operation"]["correct"], 1)
            self.assertEqual(report["service_identity"]["checkpoint_sha256"], "b" * 64)


if __name__ == "__main__":
    unittest.main()
