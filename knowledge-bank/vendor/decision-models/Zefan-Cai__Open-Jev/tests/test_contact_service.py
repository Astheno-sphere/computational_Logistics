"""CPU software fixtures only: no real HTTP service, model or quality evidence."""
import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.api import compile_request, format_response
from jev.case_email_selection import email_selection, reference
from jev.case_phone_extraction import phone_selection, selection_reference, phone_attributes, inspect_candidate, normalize_phone
from scripts import evaluate_contact_service as evaluator

HAS_PHONE = importlib.util.find_spec("phonenumbers") is not None
requires_phone = unittest.skipUnless(HAS_PHONE, "requires optional .[phone] extra")
IDENTITY = {"model": "Qwen/Qwen3.5-2B", "method": "lora_decision_head", "base_revision": "a"*40,
            "checkpoint_sha256": "b"*64, "temperature": 1.5, "code_commit": "c"*40, "max_length": 4096}
CONFIG = {"endpoint": "http://fixture.invalid/v1/systemone", "model_alias": "open-jev", "timeout": 1,
          "expected_identity": {key: IDENTITY[key] for key in ("model", "method", "base_revision", "checkpoint_sha256")}}
RUN_ARGS = {"expected_model": IDENTITY["model"], "expected_method": IDENTITY["method"],
            "expected_revision": IDENTITY["base_revision"], "expected_checkpoint_sha256": IDENTITY["checkpoint_sha256"]}


def email_case(text=None, *, identifier="email-case", split="test"):
    text = text or "Receipt destination | status=current | email: Owner@example.invalid"
    request = email_selection(text, "receipt")
    return {"id": identifier, "family_id": identifier+"-family", "group_id": identifier+"-group", "split": split,
            "corpus": "email", "request": request, "reference": reference(request)}


def phone_case(text=None, *, identifier="phone-case", split="test"):
    text = text or "Mobile: +1 202-555-0123 | Region: US"
    request = phone_selection(text, "mobile")
    attributes = []
    for candidate in request["state"]["candidates"]:
        b = phone_attributes(request, candidate)
        ref = inspect_candidate(b)
        attributes.append({"candidate_id": candidate, "reference": ref,
                           "normalized_reference": normalize_phone(b, region=ref["region"])})
    return {"id": identifier, "family_id": identifier+"-family", "group_id": identifier+"-group", "split": split,
            "corpus": "phone", "selection_request": request, "selection_reference": selection_reference(request),
            "attributes": attributes}


def reply(request, choices, *, identity=None):
    records = compile_request(state=request["state"], questions=request["questions"])
    probabilities = []
    for row in records:
        answer = choices[row["id"]]
        if row["kind"] == "noul":
            probabilities.append([1-answer, answer])
        else:
            probabilities.append([float(key == answer) for key in row["answer_keys"]])
    result = format_response(records, probabilities)
    identity = identity or IDENTITY
    result.update(model=identity["model"], metadata={key: value for key, value in identity.items() if key != "model"})
    result["metadata"]["candidate_sequences"] = sum(1 if row["kind"] == "noul" else len(row["options"]) for row in records)
    return result


class FixtureTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, endpoint, body, timeout):
        request = json.loads(body)
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("Unexpected extra fixture request; real HTTP is prohibited")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            response = response(request)
        status, raw = response if isinstance(response, tuple) else (200, evaluator.encoded(response))
        return {"http_status": status, "transport_error": None, "elapsed_seconds": 0.0}, raw


def run_case(case, transport, stable=None):
    outcome = {**evaluator.case_identity(case), "status": "pending"}
    requests, attempts = io.StringIO(), io.StringIO()
    evaluator.evaluate_case(case, outcome, CONFIG, {} if stable is None else stable, requests, attempts, transport)
    return outcome, evaluator.summarize([case], [outcome]), requests.getvalue(), attempts.getvalue()


class ContactPipelineFixtures(unittest.TestCase):
    def test_email_wrong_role_copy_is_not_requested_target_success(self):
        case = email_case("Billing contact | status=current | email: Other@example.invalid\nReceipt destination | status=current | email: Owner@example.invalid")
        wire = FixtureTransport(lambda request: reply(request, {"span": "span_0", "target_present": 1.0}))
        outcome, report, _, _ = run_case(case, wire)
        self.assertEqual(outcome["guard"]["status"], "copied")
        self.assertEqual(report["metrics"]["exact_raw_span_on_unique_target"]["correct"], 0)
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
        self.assertEqual(report["guard"]["executed"], 1)

    def test_equal_email_at_other_offset_still_fails(self):
        case = email_case("Billing contact | status=current | email: Same@example.invalid\nReceipt destination | status=current | email: Same@example.invalid")
        outcome, report, _, _ = run_case(case, FixtureTransport(lambda request: reply(request, {"span": "span_0", "target_present": 1.0})))
        self.assertEqual(outcome["guard"]["email"], case["reference"]["target_spans"][0]["text"])
        self.assertEqual(report["metrics"]["final_value_on_unique_target"]["correct"], 0)

    def test_miss_none_is_span_correct_but_extraction_failure(self):
        case = email_case('Receipt destination | status=current | email: "quoted box"@example.invalid')
        outcome, report, _, _ = run_case(case, FixtureTransport(lambda request: reply(request, {"span": "none", "target_present": 1.0})))
        self.assertEqual(case["reference"]["reason"], "candidate_miss")
        self.assertEqual(report["metrics"]["a_none_candidate_miss"], evaluator.metric(1, 1))
        self.assertEqual(report["metrics"]["exact_raw_span_on_unique_target"], evaluator.metric(0, 1))
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
        self.assertNotIn("guard", outcome)

    def test_absent_and_ambiguous_refusals_do_not_enter_unique_target_metric(self):
        for text, reason in (("Receipt destination | status=current | email: not recorded", "target_absent"),
                             ("Receipt destination | status=current | email: A@example.invalid\nReceipt destination | status=current | email: B@example.invalid", "ambiguous_target")):
            case = email_case(text)
            _, report, _, _ = run_case(case, FixtureTransport(lambda request: reply(request, {"span": "none", "target_present": float(reason != "target_absent")})))
            self.assertEqual(report["metrics"]["a_none_"+reason], evaluator.metric(1, 1))
            self.assertNotIn("final_value_on_unique_target", report["metrics"])

    def test_forced_no_candidate_still_requires_valid_response(self):
        case = email_case("Receipt destination | status=current | email: not recorded")
        _, passed, _, _ = run_case(case, FixtureTransport(lambda request: reply(request, {"span": "none", "target_present": 0.0})))
        _, failed, _, _ = run_case(case, FixtureTransport((503, b"fixture outage")))
        self.assertEqual(passed["metrics"]["a_forced_span"], evaluator.metric(1, 1))
        self.assertEqual(failed["metrics"]["a_forced_span"], evaluator.metric(0, 1))

    def test_http_error_preserves_wire_bytes_and_all_case_denominators(self):
        case = email_case()
        outcome, report, requests, attempts = run_case(case, FixtureTransport((503, b"\xffraw fixture failure")))
        wire = json.loads(attempts)
        self.assertEqual(base64.b64decode(wire["response_body_base64"]), b"\xffraw fixture failure")
        self.assertEqual(wire["http_status"], 503)
        self.assertEqual(json.loads(requests)["request_json"], wire["request_json"])
        self.assertEqual(outcome["a"]["status"], "http_error")
        self.assertEqual(report["metrics"]["a_span_on_recalled"], evaluator.metric(0, 1))
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))

    def test_json_probability_candidate_and_sequence_errors_cannot_succeed(self):
        case = email_case()
        valid = reply(case["request"], {"span": "span_0", "target_present": 1.0})
        modifications = []
        for mutator in (
            lambda row: row["answers"]["span"].update(choice="missing_candidate"),
            lambda row: row["answers"]["span"].update(probabilities={"span_0": 0.2, "none": 0.2}),
            lambda row: row["answers"]["span"].update(confidence=0.0),
            lambda row: row["answers"]["target_present"].update(noul=True),
            lambda row: row["metadata"].update(candidate_sequences=4),
        ):
            row = copy.deepcopy(valid); mutator(row); modifications.append(row)
        modifications += [(200, b'{"answers":{},"answers":{}}'), (200, b'{"value":NaN}')]
        for bad in modifications:
            outcome, report, _, attempts = run_case(case, FixtureTransport(bad))
            self.assertNotEqual(outcome["a"]["status"], "ok")
            self.assertEqual(report["metrics"]["a_presence"]["correct"], 0)
            self.assertEqual(len(attempts.splitlines()), 1)

    def test_choice_tie_preserves_actual_service_choice(self):
        case = email_case("Billing contact | status=current | email: Other@example.invalid\nReceipt destination | status=current | email: Owner@example.invalid")
        records = compile_request(**case["request"])
        response = format_response(records, [[0.5, 0.5, 0.0], [0.0, 1.0]])
        response["answers"]["span"]["choice"] = "span_1"
        response.update(model=IDENTITY["model"], metadata={**{key:value for key,value in IDENTITY.items() if key != "model"}, "candidate_sequences": 4})
        outcome, report, _, _ = run_case(case, FixtureTransport(response))
        self.assertEqual(outcome["a"]["prediction"]["span"], "span_1")
        self.assertEqual(report["metrics"]["final_value_on_unique_target"]["correct"], 1)

    def test_metadata_identity_locks_even_when_first_answers_are_invalid(self):
        case = email_case()
        first = reply(case["request"], {"span":"span_0", "target_present":1.0})
        first["answers"]["span"]["choice"] = "missing_candidate"
        stable = {}
        outcome, _, _, _ = run_case(case, FixtureTransport(first), stable)
        self.assertEqual(outcome["a"]["status"], "schema_error")
        self.assertEqual(stable["temperature"], IDENTITY["temperature"])
        changed = reply(case["request"], {"span":"span_0", "target_present":1.0}, identity={**IDENTITY,"temperature":2.0})
        outcome, _, _, _ = run_case(case, FixtureTransport(changed), stable)
        self.assertEqual(outcome["a"]["status"], "identity_error")

    @requires_phone
    def test_phone_b_uses_actual_wrong_role_even_when_presence_is_false(self):
        case = phone_case("Billing: +1 416-555-0156 | Region: CA\nMobile: +1 202-555-0123 | Region: US")
        wire = FixtureTransport(lambda request: reply(request, {"span": "span_0", "target_present": 0.0}),
                                lambda request: reply(request, {"region": "CA"}))
        outcome, report, _, _ = run_case(case, wire)
        self.assertEqual(len(wire.requests), 2)
        self.assertEqual(wire.requests[1], {"model":"open-jev", **phone_attributes(case["selection_request"], "span_0")})
        self.assertNotIn("requested_role", wire.requests[1]["state"])
        self.assertEqual(outcome["guard"]["status"], "formatted")
        self.assertEqual(report["metrics"]["b_region_on_actual_selection"], evaluator.metric(1, 1))
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
        self.assertEqual(report["metrics"]["e164_on_reference_formattable_target"], evaluator.metric(0, 1))

    def test_phone_none_with_presence_true_does_not_send_b(self):
        case = phone_case("Mobile: +44\u202f7700\u202f900123 | Region: GB")
        wire = FixtureTransport(lambda request: reply(request, {"span": "none", "target_present": 1.0}))
        outcome, report, _, _ = run_case(case, wire)
        self.assertEqual(len(wire.requests), 1)
        self.assertEqual(outcome["b"]["reason"], "a_selected_none")
        self.assertEqual(report["b_not_attempted"], {"a_selected_none": 1})
        self.assertEqual(report["metrics"]["exact_raw_span_on_unique_target"], evaluator.metric(0, 1))

    @requires_phone
    def test_b_failure_retains_a_score_and_b_fixed_denominator(self):
        case = phone_case()
        outcome, report, _, attempts = run_case(case, FixtureTransport(
            lambda request: reply(request, {"span": "span_0", "target_present": 1.0}), (500, b"B fixture failure")))
        self.assertEqual(report["metrics"]["a_span"], evaluator.metric(1, 1))
        self.assertEqual(report["metrics"]["b_region_on_actual_selection"], evaluator.metric(0, 1))
        self.assertEqual(report["metrics"]["e164_on_reference_formattable_target"], evaluator.metric(0, 1))
        self.assertEqual(outcome["status"], "b_error")
        self.assertEqual(len(attempts.splitlines()), 2)
        self.assertEqual(report["guard"]["executed"], 0)

    @requires_phone
    def test_unknown_region_none_output_is_not_extraction_success(self):
        case = phone_case("Mobile: +1 202-555-0123 | Region: not stated")
        for region, expected in (("unknown", 1), ("review", 0), ("US", 0)):
            _, report, _, _ = run_case(case, FixtureTransport(
                lambda request: reply(request, {"span": "span_0", "target_present": 1.0}),
                lambda request: reply(request, {"region": region})))
            self.assertEqual(report["metrics"]["b_region_on_actual_selection"]["correct"], expected)
            self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
            self.assertEqual(report["reference_value_available"], {"cases": 0, "unique_present_cases": 1, "coverage": 0.0})
            self.assertNotIn("e164_on_reference_formattable_target", report["metrics"])

    @requires_phone
    def test_partial_actual_candidate_gets_b_without_gold_repair(self):
        case = phone_case("Mobile: (+1 202-555-0123) | Region: US")
        wire = FixtureTransport(lambda request: reply(request, {"span": "span_0", "target_present": 1.0}),
                                lambda request: reply(request, {"region": "review"}))
        outcome, report, _, _ = run_case(case, wire)
        self.assertEqual(len(wire.requests), 2)
        self.assertEqual(outcome["guard"]["reason"], "partial_or_unbound_candidate")
        self.assertEqual(report["metrics"]["b_region_on_actual_selection"]["correct"], 1)
        self.assertEqual(report["metrics"]["exact_raw_span_on_unique_target"]["correct"], 0)

    @requires_phone
    def test_identity_change_between_a_b_and_across_corpora_is_rejected(self):
        case = phone_case()
        changed = {**IDENTITY, "temperature": 2.0}
        outcome, report, _, _ = run_case(case, FixtureTransport(
            lambda request: reply(request, {"span": "span_0", "target_present": 1.0}),
            lambda request: reply(request, {"region": "US"}, identity=changed)))
        self.assertEqual(outcome["b"]["status"], "identity_error")
        self.assertEqual(report["metrics"]["b_region_on_actual_selection"]["correct"], 0)
        stable = {}
        run_case(email_case(), FixtureTransport(lambda request: reply(request, {"span":"span_0", "target_present":1.0})), stable)
        outcome, _, _, _ = run_case(case, FixtureTransport(lambda request: reply(request, {"span":"span_0", "target_present":1.0}, identity=changed)), stable)
        self.assertEqual(outcome["a"]["status"], "identity_error")

    @requires_phone
    def test_possible_but_invalid_gb_can_succeed_with_exact_e164(self):
        case = phone_case("Mobile: 07700 900123 | Region: GB")
        outcome, report, _, _ = run_case(case, FixtureTransport(
            lambda request: reply(request, {"span":"span_0", "target_present":1.0}),
            lambda request: reply(request, {"region":"GB"})))
        self.assertFalse(outcome["guard"]["valid"])
        self.assertEqual(report["metrics"]["e164_on_reference_formattable_target"], evaluator.metric(1, 1))


def fixture_dataset(directory):
    """Malformed train JSON proves training targets are never decoded by loader."""
    data = directory / "data" / evaluator.PROFILES["email"][0]
    data.mkdir(parents=True)
    cases = [email_case(identifier="z-test", split="test"), email_case(identifier="a-ood", split="ood")]
    families = [{"id": row["family_id"], "group_id": row["group_id"], "split": row["split"], "case_ids": [row["id"]]} for row in cases]
    families.append({"id":"training-family", "group_id":"training-group", "split":"train", "case_ids":["unparsed-train"]})
    (data/"families.jsonl").write_bytes(b"\n".join(evaluator.encoded(row) for row in reversed(families))+b"\n")
    (data/"cases.jsonl").write_bytes(b'{"id":"unparsed-train", TRAIN_TARGET_MUST_NOT_BE_DECODED\n'+b"\n".join(evaluator.encoded({k:v for k,v in row.items() if k != "corpus"}) for row in reversed(cases))+b"\n")
    for split in evaluator.SPLITS:
        (data/(split+".jsonl")).write_bytes(b"UNPARSED_TYPED_TARGET_BYTES\n")
    manifest = {"family_count":3,"document_count":3,"files_sha256":{path.name:evaluator.file_hash(path) for path in data.glob("*.jsonl")},
                "configuration":{"source_files_sha256":{"case_email_selection.py":evaluator.file_hash(evaluator.ROOT/"jev/case_email_selection.py")}}}
    (data/"manifest.json").write_bytes(evaluator.encoded(manifest))
    return data, cases, evaluator.file_hash(data/"manifest.json")


class ContactDriverFixtures(unittest.TestCase):
    def test_loader_hashes_training_bytes_without_parsing_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            data, cases, pinned = fixture_dataset(Path(temporary))
            with patch.dict(evaluator.PROFILES, {"email":(data.name,pinned)}):
                selected, evidence = evaluator.load_cases(data.parent, ("email",), ("test","ood"))
            self.assertEqual([row["id"] for row in selected], ["z-test", "a-ood"])
            self.assertEqual(evidence["email"]["selected_cases"], 2)

    def test_changed_manifest_artifact_and_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            data, _, pinned = fixture_dataset(Path(temporary))
            with patch.dict(evaluator.PROFILES, {"email":(data.name,pinned)}):
                (data/"train.jsonl").write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "artifact"):
                    evaluator.check_inputs(data.parent, "email")
                manifest = json.loads((data/"manifest.json").read_bytes())
                manifest["files_sha256"]["train.jsonl"] = evaluator.file_hash(data/"train.jsonl")
                manifest["configuration"]["source_files_sha256"]["case_email_selection.py"] = "0"*64
                (data/"manifest.json").write_bytes(evaluator.encoded(manifest))
                with self.assertRaisesRegex(ValueError, "manifest"):
                    evaluator.check_inputs(data.parent, "email")
                evaluator.PROFILES["email"] = (data.name,evaluator.file_hash(data/"manifest.json"))
                with self.assertRaisesRegex(ValueError, "source"):
                    evaluator.check_inputs(data.parent, "email")

    def test_fixture_driver_preserves_original_requests_and_raw_responses(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary); data, cases, pinned=fixture_dataset(directory)
            wire=FixtureTransport(*(lambda request:reply(request,{"span":"span_0","target_present":1.0}) for _ in cases))
            with patch.dict(evaluator.PROFILES,{"email":(data.name,pinned)}):
                report=evaluator.run_evaluation(data.parent,directory/"output",corpora=("email",),transport=wire,**RUN_ARGS)
            self.assertEqual(report["evidence_kind"],"software_fixture")
            self.assertFalse(report["is_model_quality_evidence"])
            self.assertEqual(report["documents"],2)
            self.assertEqual(wire.requests,[{"model":"open-jev",**row["request"]} for row in cases])
            attempts=[json.loads(line) for line in (directory/"output/attempts.jsonl").read_text().splitlines()]
            for attempt in attempts:
                raw=base64.b64decode(attempt["response_body_base64"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(),attempt["response_body_sha256"])
            self.assertTrue((directory/"output/references.jsonl").is_file())

    def test_interruption_retains_unattempted_documents_in_denominators(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary); data, _, pinned=fixture_dataset(directory)
            wire=FixtureTransport(lambda request:reply(request,{"span":"span_0","target_present":1.0}),KeyboardInterrupt())
            with patch.dict(evaluator.PROFILES,{"email":(data.name,pinned)}):
                with self.assertRaises(KeyboardInterrupt):
                    evaluator.run_evaluation(data.parent,directory/"output",corpora=("email",),transport=wire,**RUN_ARGS)
            report=json.loads((directory/"output/report.json").read_bytes())
            self.assertEqual(report["status"],"interrupted_or_failed")
            self.assertEqual(report["by_corpus"]["email"]["metrics"]["a_span"],evaluator.metric(1,2))
            self.assertEqual(report["by_corpus"]["email"]["metrics"]["final_value_on_unique_target"],evaluator.metric(1,2))

    def test_failed_default_http_path_never_marks_model_quality_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary); data, _, pinned=fixture_dataset(directory)
            failed=FixtureTransport((503,b"mocked outage"),(503,b"mocked outage"))
            with patch.dict(evaluator.PROFILES,{"email":(data.name,pinned)}), patch.object(evaluator,"http_attempt",failed):
                report=evaluator.run_evaluation(data.parent,directory/"failed",corpora=("email",),**RUN_ARGS)
            self.assertEqual(report["status"],"completed_with_errors")
            self.assertEqual(report["evidence_kind"],"http_service_evaluation")
            self.assertFalse(report["is_model_quality_evidence"])
            interrupted=FixtureTransport(lambda request:reply(request,{"span":"span_0","target_present":1.0}),KeyboardInterrupt())
            with patch.dict(evaluator.PROFILES,{"email":(data.name,pinned)}), patch.object(evaluator,"http_attempt",interrupted):
                with self.assertRaises(KeyboardInterrupt):
                    evaluator.run_evaluation(data.parent,directory/"interrupted",corpora=("email",),**RUN_ARGS)
            report=json.loads((directory/"interrupted/report.json").read_bytes())
            self.assertIsNotNone(report["service_identity"])
            self.assertFalse(report["is_model_quality_evidence"])

    def test_outputs_cannot_overwrite_inputs_or_follow_output_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary); data, _, _=fixture_dataset(directory)
            alias=directory/"alias"; alias.symlink_to(data,target_is_directory=True)
            for output in (data/"new",data,alias,directory/"alias/new"):
                with self.subTest(output=output), self.assertRaisesRegex(ValueError,"output directory"):
                    evaluator.run_evaluation(data.parent,output,corpora=("email",),transport=FixtureTransport(),**RUN_ARGS)

    def test_expected_identity_and_split_flags_fail_before_any_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            for override in ({"expected_revision":"main"},{"expected_checkpoint_sha256":None},{"splits":["train"]},
                             {"endpoint":"http://user:secret@example.invalid/api"},{"expected_temperature":True}):
                with self.subTest(override=override), self.assertRaises(ValueError):
                    evaluator.run_evaluation(Path(temporary)/"data",Path(temporary)/"output",corpora=("email",),transport=FixtureTransport(),**{**RUN_ARGS,**override})


if __name__ == "__main__":
    unittest.main()
