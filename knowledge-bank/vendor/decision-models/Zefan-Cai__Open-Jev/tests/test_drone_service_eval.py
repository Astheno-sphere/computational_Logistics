import base64
import copy
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from jev.api import compile_request, format_response
from jev.case_drone import drone_teacher, generate_cases
from scripts.evaluate_drone_service import (encoded, run_evaluation, score_response,
    select_cases, service_identity, sha256, strict_json, summarize, validate_case, validate_response)


def fixture_response(request, probabilities=None):
    """Synthetic test fixture only; production has no oracle inference backend."""
    records = compile_request(**request)
    answers = drone_teacher(request["state"])
    if probabilities is None:
        probabilities = [[float(key == answers[record["id"]]) for key in record["answer_keys"]]
                         for record in records]
    response = format_response(records, probabilities)
    response.update(model="test/drone", metadata={"method": "lora_decision_head", "temperature": 1.0,
        "base_revision": "a" * 40, "checkpoint_sha256": "b" * 64, "code_commit": "c" * 40,
        "max_length": 16384, "candidate_sequences": sum(1 if r["kind"] == "noul" else len(r["options"]) for r in records)})
    return response


class MemoryResponse:
    status = 200

    def __init__(self, body, partial=False):
        self.body, self.partial = body, partial

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        if self.partial:
            raise IncompleteRead(self.body, 100)
        return self.body


class DroneServiceEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = generate_cases(groups=12, ood_groups=3)
        for case in cls.cases:
            if case["split"] != "ood":
                case["split"] = "test"

    def write_source(self, directory):
        path = Path(directory) / "cases.jsonl"
        path.write_bytes(b"".join(encoded(case) + b"\n" for case in self.cases))
        path.with_name("manifest.json").write_bytes(encoded({"cases_file": path.name,
            "cases_sha256": sha256(path.read_bytes()), "case_count": len(self.cases)}))
        return path

    def test_selection_is_label_independent_order_invariant_and_grouped(self):
        selected = select_cases(self.cases, parents_per_split=2, variants_per_parent=3, max_cases=5)
        changed = copy.deepcopy(self.cases)
        for case in changed:
            case["answers"], case["derivation"] = object(), object()
        repeated = select_cases(changed[::-1], parents_per_split=2, variants_per_parent=3, max_cases=5)
        self.assertEqual([c["id"] for c in selected], [c["id"] for c in repeated])
        self.assertEqual([c["split"] for c in selected], ["test", "ood", "test", "ood", "test"])
        self.assertEqual(len({c["group_id"] for c in selected}), 4)
        leaked = copy.deepcopy(self.cases[0])
        leaked.update(id=leaked["id"] + "-leak", split="ood")
        with self.assertRaisesRegex(ValueError, "parent group crosses"):
            select_cases([*self.cases, leaked], parents_per_split=1)
        leaked["group_id"] += "-new"
        with self.assertRaisesRegex(ValueError, "identical runtime request"):
            select_cases([*self.cases, leaked], parents_per_split=1)

    def test_exact_requests_teacher_and_derivation_are_required(self):
        for kind in ("question", "answer", "trace", "order"):
            case = copy.deepcopy(self.cases[0])
            if kind == "question":
                case["request"]["questions"]["risk"]["instructions"] = "Different rubric"
            elif kind == "answer":
                case["answers"]["risk"] = "not a label"
            elif kind == "trace":
                case["derivation"]["required_gap_width_m"] = -10
            else:
                q = case["request"]["questions"]["maneuver"]
                q["criteria"] = dict(reversed(list(q["criteria"].items())))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_case(case)

    def test_noul_has_one_scoring_sequence_and_artifact_identity_is_exact(self):
        case = self.cases[0]
        records, response = validate_case(case), fixture_response(case["request"])
        actual = service_identity(response, records, {"model": "test/drone", "base_revision": "a" * 40})
        self.assertEqual(actual["checkpoint_sha256"], "b" * 64)
        response["metadata"]["candidate_sequences"] += 1
        with self.assertRaisesRegex(ValueError, "candidate sequence"):
            service_identity(response, records, {})
        for key, value in (("base_revision", "main"), ("checkpoint_sha256", None), ("temperature", True)):
            changed = fixture_response(case["request"])
            changed["metadata"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                service_identity(changed, records, {})

    def test_modal_ties_scalar_error_and_noul_threshold(self):
        case = next(c for c in self.cases if c["answers"]["risk"] == "1"
                    and c["answers"]["target_truly_lost"] == "false")
        records = validate_case(case)
        maneuver = [float(key == case["answers"]["maneuver"]) for key in records["maneuver"]["answer_keys"]]
        response = fixture_response(case["request"], [maneuver, [0.5, 0.0, 0.5], [0.5, 0.5]])
        scored = score_response(case, response, records)
        self.assertEqual(scored["decision"]["risk_level"], "0")
        self.assertTrue(scored["decision"]["target_truly_lost"])
        self.assertEqual(scored["correct"]["risk_level"], 0)
        self.assertEqual(scored["correct"]["complete_decision"], 0)
        self.assertEqual(scored["probability_errors"], {"risk_brier": 1.5,
            "risk_scalar_absolute_error": 0, "risk_scalar_squared_error": 0, "target_loss_brier": 0.25})
        # Choice ties may select any offered maximizer, while Score modal ties
        # use the declared lowest ordinal index.
        count = len(maneuver)
        response = fixture_response(case["request"], [[1 / count] * count, [0, 1, 0], [1, 0]])
        response["answers"]["maneuver"]["choice"] = records["maneuver"]["answer_keys"][-1]
        validate_response(response, records)

    def test_strict_all_head_contracts_reject_malformed_fields(self):
        case = self.cases[0]
        records = validate_case(case)
        mutations = {
            "missing head": lambda a: a.pop("risk"),
            "extra head": lambda a: a.update(extra={"type": "noul", "noul": 1}),
            "noul bool": lambda a: a["target_truly_lost"].update(noul=True),
            "noul nan": lambda a: a["target_truly_lost"].update(noul=float("nan")),
            "noul range": lambda a: a["target_truly_lost"].update(noul=1.01),
            "noul extra": lambda a: a["target_truly_lost"].update(confidence=1),
            "choice confidence absent": lambda a: a["maneuver"].pop("confidence"),
            "choice confidence bool": lambda a: a["maneuver"].update(confidence=True),
            "choice confidence wrong": lambda a: a["maneuver"].update(confidence=0),
            "choice illegal": lambda a: a["maneuver"].update(choice="invented"),
            "score confidence absent": lambda a: a["risk"].pop("confidence"),
            "score confidence wrong": lambda a: a["risk"].update(confidence=0),
            "score scalar wrong": lambda a: a["risk"].update(score=99),
            "score scalar bool": lambda a: a["risk"].update(score=False),
            "score legend absent": lambda a: a["risk"].pop("legend"),
            "score legend wrong": lambda a: a["risk"].update(legend={"0": "invented"}),
            "score probs bool": lambda a: a["risk"]["probabilities"].update({"0": True}),
            "score probs infinity": lambda a: a["risk"]["probabilities"].update({"0": float("inf")}),
            "score probs missing": lambda a: a["risk"]["probabilities"].pop("0"),
            "score probs extra": lambda a: a["risk"]["probabilities"].update({"3": 0}),
        }
        for label, mutate in mutations.items():
            response = fixture_response(case["request"])
            mutate(response["answers"])
            with self.subTest(label=label), self.assertRaises(ValueError):
                validate_response(response, records)
        for text in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'):
            with self.assertRaises(ValueError):
                strict_json(text)
        for level, outside in ((0, -1e-7), (2, 2 + 1e-7)):
            size = len(records["maneuver"]["options"])
            response = fixture_response(case["request"], [[1 / size] * size,
                                        [float(i == level) for i in range(3)], [1, 0]])
            response["answers"]["risk"]["score"] = outside
            with self.assertRaises(ValueError):
                validate_response(response, records)

    def test_forced_maneuver_is_separate_and_all_failures_stay_in_denominators(self):
        normal = self.cases[0]
        forced = next(c for c in self.cases if c["variant"] == "single_permitted_maneuver")
        cases = [normal, forced]
        records = {c["id"]: validate_case(c) for c in cases}
        scored = score_response(forced, fixture_response(forced["request"]), records[forced["id"]])
        self.assertEqual(scored["correct"], {"forced_maneuver": 1, "risk_level": 1, "target_loss": 1, "complete_decision": 1})
        for status in ("http_error", "schema_error", "identity_error", "pending"):
            outcomes = [] if status == "pending" else [{"case_id": c["id"], "status": status} for c in cases]
            report = summarize(cases, outcomes, records)
            self.assertEqual([report["metrics"][key]["total"] for key in
                             ("maneuver", "forced_maneuver", "risk_level", "target_loss", "complete_decision")], [1, 1, 2, 2, 2])
            self.assertTrue(all(metric["correct"] == 0 for metric in report["metrics"].values()))
            probability = report["probability_metrics_valid_only"]
            self.assertEqual(probability["coverage"], 0)
            self.assertIsNone(probability["risk_brier"])
            self.assertIsNone(probability["target_loss_brier"])

    def test_offline_transport_failures_identity_and_wire_evidence(self):
        modes = ["ok", "500", "bad_json", "schema", "identity", "disconnect", "partial", "nan"]
        sent = []
        with tempfile.TemporaryDirectory() as directory:
            source, output = self.write_source(directory), Path(directory) / "eval"

            def transport(request, timeout):
                # Everything is frozen before the very first simulated call.
                self.assertEqual(len((output / "requests.jsonl").read_text().splitlines()), len(modes))
                mode = modes[len(sent)]
                sent.append(request.data)
                if mode == "500":
                    raise HTTPError(request.full_url, 500, "test error", {}, io.BytesIO(b"failure-body"))
                if mode == "disconnect":
                    raise URLError("offline fixture disconnect")
                if mode == "partial":
                    return MemoryResponse(b'{"truncated":', partial=True)
                response = fixture_response({k: v for k, v in json.loads(request.data).items() if k != "model"})
                if mode == "schema":
                    del response["answers"]["risk"]["confidence"]
                if mode == "identity":
                    response["metadata"]["checkpoint_sha256"] = "d" * 64
                raw = encoded(response)
                if mode == "bad_json":
                    raw = b"not-json"
                if mode == "nan":
                    raw = b'{"answers":NaN}'
                return MemoryResponse(raw)

            with patch("scripts.evaluate_drone_service.urlopen", side_effect=transport):
                report = run_evaluation(source, output, splits=("test",), parents_per_split=1,
                                        variants_per_parent=len(modes), expected_model="test/drone")
            self.assertEqual(report["status"], "complete_with_errors")
            self.assertTrue(report["complete"])
            self.assertEqual(report["attempted_cases"], 8)
            self.assertEqual(report["status_counts"], {"ok": 1, "http_error": 3, "schema_error": 3, "identity_error": 1})
            self.assertEqual(report["overall"]["metrics"]["complete_decision"], {"correct": 1, "total": 8, "accuracy": 1/8})
            self.assertEqual(report["overall"]["probability_metrics_valid_only"]["coverage"], 1/8)
            requests = [json.loads(line) for line in (output / "requests.jsonl").read_text().splitlines()]
            outcomes = [json.loads(line) for line in (output / "outcomes.jsonl").read_text().splitlines()]
            for body, request, outcome in zip(sent, requests, outcomes):
                self.assertEqual(set(json.loads(body)), {"model", "state", "questions"})
                self.assertEqual(body, request["request_json"].encode())
                self.assertEqual(sha256(body), request["request_body_sha256"])
                self.assertEqual(request["request_body_sha256"], outcome["request_body_sha256"])
                raw = base64.b64decode(outcome["response_body_base64"])
                self.assertEqual(sha256(raw), outcome["response_body_sha256"])
            self.assertEqual(base64.b64decode(outcomes[1]["response_body_base64"]), b"failure-body")
            self.assertEqual(base64.b64decode(outcomes[6]["response_body_base64"]), b'{"truncated":')
            self.assertEqual((output / "source-manifest.json").read_bytes(), source.with_name("manifest.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                run_evaluation(source, output)
            source.write_bytes(source.read_bytes() + b"\n")
            with patch("scripts.evaluate_drone_service.urlopen") as unused:
                with self.assertRaisesRegex(ValueError, "checksum/count"):
                    run_evaluation(source, Path(directory) / "changed", parents_per_split=1)
                unused.assert_not_called()

    def test_interrupted_run_preserves_all_denominators_and_frozen_requests(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            source, output = self.write_source(directory), Path(directory) / "eval"

            def transport(request, timeout):
                calls.append(request.data)
                if len(calls) == 2:
                    raise KeyboardInterrupt()
                body = json.loads(request.data)
                return MemoryResponse(encoded(fixture_response({key: body[key] for key in ("state", "questions")})))

            with patch("scripts.evaluate_drone_service.urlopen", side_effect=transport):
                with self.assertRaises(KeyboardInterrupt):
                    run_evaluation(source, output, splits=("test",), parents_per_split=1, variants_per_parent=6)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["status"], "interrupted")
            self.assertFalse(report["complete"])
            self.assertEqual((report["attempted_cases"], report["completed_attempts"], report["pending_cases"], report["not_dispatched_cases"]), (2, 1, 5, 4))
            self.assertEqual(report["overall"]["metrics"]["complete_decision"]["total"], 6)
            self.assertEqual(report["overall"]["metrics"]["complete_decision"]["correct"], 1)
            self.assertEqual(report["overall"]["probability_metrics_valid_only"]["coverage"], 1/6)
            self.assertEqual(len((output / "requests.jsonl").read_text().splitlines()), 6)
            self.assertEqual(len((output / "references.jsonl").read_text().splitlines()), 6)
            self.assertEqual(len((output / "outcomes.jsonl").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
