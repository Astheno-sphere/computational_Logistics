"""Small CPU transport fixtures only; never model or held-out quality evidence."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.case_amount_extraction import amount_selection, amount_attributes, selection_reference, inspect_candidate, normalize_amount
from scripts import evaluate_amount_service as evaluator
from tests.test_contact_service import CONFIG, IDENTITY, RUN_ARGS, FixtureTransport as ContactFixtureTransport, reply


class FixtureTransport(ContactFixtureTransport):
    total_requests = 0

    def __call__(self, endpoint, body, timeout):
        FixtureTransport.total_requests += 1
        return super().__call__(endpoint, body, timeout)


def amount_case(text=None, *, identifier="amount-case", split="test", locale="US", layout="invoice", role="due"):
    text = f"Number format: {locale}\nCurrency declaration: USD\n" + (text or "Amount due: USD 12.34 | Flow: charge")
    request = amount_selection(text, role, locale=locale, layout=layout)
    attributes = []
    for candidate in request["state"]["candidates"]:
        b = amount_attributes(request, candidate)
        ref = inspect_candidate(b)
        attributes.append({"candidate_id": candidate, "request": b, "reference": ref,
                           "normalized_reference": normalize_amount(b, **{key: ref[key] for key in ("currency", "direction_known", "is_credit")})})
    return {"id": identifier, "family_id": identifier+"-family", "group_id": identifier+"-group", "split": split,
            "corpus": "amount", "selection_request": request, "selection_reference": selection_reference(request), "attributes": attributes}


def transport_for(span="span_0", *, present=1.0, currency="USD", known=1.0, credit=0.0):
    responses = [lambda request: reply(request, {"span": span, "target_present": present})]
    if span != "none":
        responses.append(lambda request: reply(request, {"currency": currency, "direction_known": known, "is_credit": credit}))
    return FixtureTransport(*responses)


def run_case(case, transport, stable=None):
    outcome = {**evaluator.case_identity(case), "status": "pending"}
    requests, attempts = io.StringIO(), io.StringIO()
    evaluator.evaluate_case(case, outcome, CONFIG, {} if stable is None else stable, requests, attempts, transport)
    return outcome, evaluator.summarize([case], [outcome]), requests.getvalue(), attempts.getvalue()


class AmountPipelineFixtures(unittest.TestCase):
    def test_b_uses_actual_wrong_role_even_when_presence_is_false(self):
        case = amount_case("Subtotal: EUR 11.00 | Flow: credit\nAmount due: USD 12.34 | Flow: charge")
        wire = transport_for(present=0.0, currency="EUR", credit=1.0)
        outcome, report, _, _ = run_case(case, wire)
        self.assertEqual(wire.requests, [{"model": "open-jev", **case["selection_request"]},
                                        {"model": "open-jev", **amount_attributes(case["selection_request"], "span_0")}])
        self.assertNotIn("requested_role", wire.requests[1]["state"])
        self.assertEqual(outcome["guard"]["amount"], "-11.00")
        self.assertEqual(report["metrics"]["b_defined_attributes_joint_on_actual_selection"], evaluator.metric(1, 1))
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))

    def test_equal_amount_at_other_offset_is_not_extraction_success(self):
        case = amount_case("Subtotal: USD 12.34 | Flow: charge\nAmount due: USD 12.34 | Flow: charge")
        outcome, report, _, _ = run_case(case, transport_for())
        self.assertEqual(outcome["guard"]["amount"], "12.34")
        self.assertEqual(report["metrics"]["exact_raw_span_on_unique_target"], evaluator.metric(0, 1))
        self.assertEqual(report["metrics"]["normalized_pair_on_reference_ready_target"], evaluator.metric(0, 1))

    def test_miss_none_is_span_correct_but_never_extracted(self):
        case = amount_case("Amount due: EUR 1\u202f234,56 | Flow: charge", locale="EU")
        wire = transport_for("none")
        outcome, report, _, _ = run_case(case, wire)
        self.assertEqual(case["selection_reference"]["reason"], "candidate_miss")
        self.assertEqual(report["metrics"]["a_none_candidate_miss"], evaluator.metric(1, 1))
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
        self.assertEqual(outcome["b"]["reason"], "a_selected_none")
        self.assertEqual(len(wire.requests), 1)
        self.assertNotIn("guard", outcome)

    def test_absent_and_ambiguous_refusals_have_no_unique_target_denominator(self):
        for text, reason, present in (("Amount due: not recorded | Flow: not stated", "target_absent", 0.0),
                                      ("Amount due: USD 12.34 | Flow: charge\nAmount due: USD 13.34 | Flow: charge", "ambiguous_target", 1.0)):
            _, report, _, _ = run_case(amount_case(text), transport_for("none", present=present))
            self.assertEqual(report["metrics"]["a_none_"+reason], evaluator.metric(1, 1))
            self.assertNotIn("final_value_on_unique_target", report["metrics"])

    def test_forced_single_none_still_requires_a_valid_response(self):
        case = amount_case("Amount due: not recorded | Flow: not stated")
        _, passed, _, _ = run_case(case, transport_for("none", present=0.0))
        _, failed, _, _ = run_case(case, FixtureTransport((503, b"fixture outage")))
        self.assertEqual(passed["metrics"]["a_forced_span"], evaluator.metric(1, 1))
        self.assertEqual(failed["metrics"]["a_forced_span"], evaluator.metric(0, 1))

    def test_undefined_credit_valid_probabilities_do_not_change_defined_score(self):
        case = amount_case("Amount due: USD 12.34 | Flow: not stated")
        reports = []
        for credit in (0.0, 0.5, 1.0):
            with patch.object(evaluator, "normalize_amount", wraps=normalize_amount) as normalize:
                outcome, report, _, _ = run_case(case, transport_for(known=0.0, credit=credit))
            self.assertIsNone(normalize.call_args.kwargs["is_credit"])
            self.assertEqual(outcome["guard"]["reason"], "direction_requires_review")
            self.assertNotIn("b_is_credit_on_reference_known_actual_selection", report["metrics"])
            self.assertEqual(report["actual_b_undefined_credit"], 1)
            self.assertEqual(report["metrics"]["b_defined_attributes_joint_on_actual_selection"], evaluator.metric(1, 1))
            self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
            self.assertEqual(report["reference_ready"], {"cases": 0, "unique_present_cases": 1, "coverage": 0.0})
            reports.append(report)
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(reports[1], reports[2])

    def test_reference_known_credit_scored_even_when_predicted_unknown(self):
        case = amount_case("Amount due: USD 12.34 | Flow: credit")
        for credit, expected in ((0.0, 0), (1.0, 1)):
            with patch.object(evaluator, "normalize_amount", wraps=normalize_amount) as normalize:
                _, report, _, _ = run_case(case, transport_for(known=0.0, credit=credit))
            self.assertIsNone(normalize.call_args.kwargs["is_credit"])
            self.assertEqual(report["metrics"]["b_is_credit_on_reference_known_actual_selection"], evaluator.metric(expected, 1))
            self.assertEqual(report["metrics"]["b_defined_attributes_joint_on_actual_selection"], evaluator.metric(0, 1))
            self.assertEqual(report["metrics"]["normalized_pair_on_reference_ready_target"], evaluator.metric(0, 1))

    def test_predicted_known_cannot_make_unknown_reference_normalizable(self):
        case = amount_case("Amount due: USD 12.34 | Flow: not stated")
        with patch.object(evaluator, "normalize_amount", wraps=normalize_amount) as normalize:
            outcome, report, _, _ = run_case(case, transport_for(known=1.0, credit=1.0))
        self.assertIs(normalize.call_args.kwargs["is_credit"], True)
        self.assertEqual(outcome["guard"]["status"], "review")
        self.assertNotIn("b_is_credit_on_reference_known_actual_selection", report["metrics"])
        self.assertEqual(report["metrics"]["b_defined_attributes_joint_on_actual_selection"], evaluator.metric(0, 1))

    def test_undefined_credit_still_requires_protocol_valid_probability(self):
        case = amount_case("Amount due: USD 12.34 | Flow: not stated")
        request = amount_attributes(case["selection_request"], "span_0")
        for invalid in (True, -0.1, 1.1, float("inf")):
            response = reply(request, {"currency": "USD", "direction_known": 0.0, "is_credit": 0.0})
            response["answers"]["is_credit"]["noul"] = invalid
            outcome, report, _, _ = run_case(case, FixtureTransport(
                lambda wire: reply(wire, {"span": "span_0", "target_present": 1.0}), response))
            self.assertNotEqual(outcome["b"]["status"], "ok")
            self.assertEqual(report["metrics"]["b_defined_attributes_joint_on_actual_selection"], evaluator.metric(0, 1))
            self.assertEqual(report["actual_b_undefined_credit"], 1)

    def test_supported_currencies_signs_and_long_decimal_remain_exact(self):
        examples = (("Amount due: USD 12.34 | Flow: charge", "US", "invoice", "USD", 0.0, "12.34"),
                    ("Payable now :: flow=rebate; value=-1.234,56 EUR", "EU", "ledger", "EUR", 1.0, "-1234.56"),
                    ("Amount due: GBP 123456789012345678901234567890.12 | Flow: credit", "US", "invoice", "GBP", 1.0, "-123456789012345678901234567890.12"),
                    ("Amount due: USD -0.00 | Flow: credit", "US", "invoice", "USD", 1.0, "0.00"))
        for text, locale, layout, currency, credit, amount in examples:
            outcome, report, _, _ = run_case(amount_case(text, locale=locale, layout=layout), transport_for(currency=currency, credit=credit))
            self.assertEqual((outcome["guard"]["currency"], outcome["guard"]["amount"]), (currency, amount))
            self.assertEqual(report["metrics"]["complete_output_on_unique_target"], evaluator.metric(1, 1))

    def test_presence_false_keeps_value_score_but_fails_complete_output(self):
        _, report, _, _ = run_case(amount_case(), transport_for(present=0.0))
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(1, 1))
        self.assertEqual(report["metrics"]["complete_output_on_unique_target"], evaluator.metric(0, 1))

    def test_reference_currency_review_keeps_known_credit_denominator(self):
        case = amount_case("Amount due: CAD 12.34 | Flow: credit")
        outcome, report, _, _ = run_case(case, transport_for(currency="review", credit=1.0))
        self.assertEqual(report["metrics"]["b_is_credit_on_reference_known_actual_selection"], evaluator.metric(1, 1))
        self.assertEqual(report["metrics"]["b_defined_attributes_joint_on_actual_selection"], evaluator.metric(1, 1))
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
        self.assertIsNone(outcome["guard"]["amount"])
        self.assertNotIn("normalized_pair_on_reference_ready_target", report["metrics"])

    def test_wrong_b_heads_collapsing_to_review_do_not_succeed(self):
        for overrides in ({"currency": "review"}, {"known": 0.0}, {"credit": 1.0}):
            outcome, report, _, _ = run_case(amount_case(), transport_for(**overrides))
            self.assertEqual(outcome["guard"]["status"], "review")
            self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
            self.assertEqual(report["metrics"]["normalized_pair_on_reference_ready_target"], evaluator.metric(0, 1))

    def test_partial_selection_cannot_be_repaired_by_predicted_known(self):
        case = amount_case("Amount due: (USD 12.34) | Flow: credit")
        outcome, report, _, _ = run_case(case, transport_for(credit=1.0))
        self.assertEqual(outcome["guard"]["reason"], "partial_or_unbound_candidate")
        self.assertEqual(report["metrics"]["exact_raw_span_on_unique_target"], evaluator.metric(0, 1))
        self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))

    def test_b_http_schema_and_identity_failure_preserve_a(self):
        case = amount_case()
        valid = reply(amount_attributes(case["selection_request"], "span_0"), {"currency": "USD", "direction_known": 1.0, "is_credit": 0.0})
        bad_schema = copy.deepcopy(valid); bad_schema["answers"]["currency"]["choice"] = "CAD"
        bad_identity = copy.deepcopy(valid); bad_identity["metadata"]["temperature"] = 2.0
        for response, status in (((500, b"\xffB fixture failure"), "http_error"), (bad_schema, "schema_error"), (bad_identity, "identity_error")):
            outcome, report, _, attempts = run_case(case, FixtureTransport(
                lambda request: reply(request, {"span": "span_0", "target_present": 1.0}), response))
            self.assertEqual(outcome["b"]["status"], status)
            self.assertEqual(report["metrics"]["a_span"], evaluator.metric(1, 1))
            self.assertEqual(report["metrics"]["b_is_credit_on_reference_known_actual_selection"], evaluator.metric(0, 1))
            self.assertEqual(report["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 1))
            self.assertEqual(report["guard"]["executed"], 0)
            self.assertEqual(len(attempts.splitlines()), 2)
            if status == "http_error":
                self.assertEqual(base64.b64decode(json.loads(attempts.splitlines()[1])["response_body_base64"]), response[1])

    def test_metadata_locks_before_invalid_a_answers(self):
        case = amount_case()
        bad = reply(case["selection_request"], {"span": "span_0", "target_present": 1.0})
        bad["answers"]["span"]["choice"] = "missing_candidate"
        stable = {}
        outcome, _, _, _ = run_case(case, FixtureTransport(bad), stable)
        self.assertEqual(outcome["a"]["status"], "schema_error")
        self.assertEqual(stable["temperature"], IDENTITY["temperature"])
        changed = reply(case["selection_request"], {"span": "span_0", "target_present": 1.0}, identity={**IDENTITY, "temperature": 2.0})
        outcome, _, _, _ = run_case(case, FixtureTransport(changed), stable)
        self.assertEqual(outcome["a"]["status"], "identity_error")


def fixture_dataset(directory):
    """Invalid nonheldout targets prove prefix routing precedes full case parsing."""
    data = directory/"data"/evaluator.VERSION
    data.mkdir(parents=True)
    cases = [amount_case(identifier="z-test", split="test"), amount_case(identifier="a-ood", split="ood")]
    families = [{"id": row["family_id"], "group_id": row["group_id"], "split": row["split"], "case_ids": [row["id"]]} for row in cases]
    for split in ("train", "calibration", "validation"):
        families.append({"id": split+"-family", "group_id": split+"-group", "split": split, "case_ids": ["unparsed-"+split]})
    (data/"families.jsonl").write_bytes(b"\n".join(evaluator.encoded(row) for row in reversed(families))+b"\n")
    ignored = b"".join(b'{"id":"unparsed-'+split.encode()+b'", TARGET_MUST_NOT_BE_DECODED\n' for split in ("train", "calibration", "validation"))
    (data/"cases.jsonl").write_bytes(ignored+b"\n".join(evaluator.encoded({k: v for k, v in row.items() if k != "corpus"}) for row in reversed(cases))+b"\n")
    for split in evaluator.SPLITS:
        (data/(split+".jsonl")).write_bytes(b"UNPARSED_TYPED_TARGET_BYTES\n")
    manifest = {"family_count": 5, "document_count": 5, "files_sha256": {path.name: evaluator.file_hash(path) for path in data.glob("*.jsonl")},
                "configuration": {"source_files_sha256": {"case_amount_extraction.py": evaluator.file_hash(evaluator.ROOT/"jev/case_amount_extraction.py")}}}
    (data/"manifest.json").write_bytes(evaluator.encoded(manifest))
    return data, cases, evaluator.file_hash(data/"manifest.json")


class AmountDriverFixtures(unittest.TestCase):
    def test_loader_never_decodes_nonheldout_or_typed_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            data, _, pinned = fixture_dataset(Path(temporary))
            with patch.object(evaluator, "MANIFEST_SHA256", pinned):
                selected, evidence = evaluator.load_cases(data.parent, ("ood", "test"))
            self.assertEqual([row["id"] for row in selected], ["z-test", "a-ood"])
            self.assertEqual(evidence["split_counts"], {"test": 1, "ood": 1})

    def test_changed_artifact_manifest_and_producer_fail_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            data, _, pinned = fixture_dataset(Path(temporary))
            with patch.object(evaluator, "MANIFEST_SHA256", pinned):
                (data/"train.jsonl").write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "artifact"):
                    evaluator.check_inputs(data.parent)
                manifest = json.loads((data/"manifest.json").read_bytes())
                manifest["files_sha256"]["train.jsonl"] = evaluator.file_hash(data/"train.jsonl")
                manifest["configuration"]["source_files_sha256"]["case_amount_extraction.py"] = "0"*64
                (data/"manifest.json").write_bytes(evaluator.encoded(manifest))
                with self.assertRaisesRegex(ValueError, "manifest"):
                    evaluator.check_inputs(data.parent)
            with patch.object(evaluator, "MANIFEST_SHA256", evaluator.file_hash(data/"manifest.json")):
                with self.assertRaisesRegex(ValueError, "source"):
                    evaluator.check_inputs(data.parent)

    def test_driver_preserves_actual_wire_and_labels_fixture_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); data, cases, pinned = fixture_dataset(directory)
            wire = FixtureTransport(*(response for _ in cases for response in transport_for().responses))
            with patch.object(evaluator, "MANIFEST_SHA256", pinned):
                report = evaluator.run_evaluation(data.parent, directory/"output", transport=wire, **RUN_ARGS)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["evidence_kind"], "software_fixture")
            self.assertFalse(report["is_model_quality_evidence"])
            self.assertEqual(report["summary"]["metrics"]["complete_output_on_unique_target"], evaluator.metric(2, 2))
            self.assertEqual(wire.requests, [request for case in cases for request in (
                {"model": "open-jev", **case["selection_request"]}, {"model": "open-jev", **amount_attributes(case["selection_request"], "span_0")})])
            attempts = [json.loads(line) for line in (directory/"output/attempts.jsonl").read_text().splitlines()]
            for attempt in attempts:
                raw = base64.b64decode(attempt["response_body_base64"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), attempt["response_body_sha256"])
            self.assertEqual(len((directory/"output/references.jsonl").read_text().splitlines()), 2)

    def test_interruption_during_b_retains_a_and_all_fixed_denominators(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); data, _, pinned = fixture_dataset(directory)
            wire = FixtureTransport(lambda request: reply(request, {"span": "span_0", "target_present": 1.0}), KeyboardInterrupt())
            with patch.object(evaluator, "MANIFEST_SHA256", pinned), self.assertRaises(KeyboardInterrupt):
                evaluator.run_evaluation(data.parent, directory/"output", transport=wire, **RUN_ARGS)
            report = json.loads((directory/"output/report.json").read_bytes())
            self.assertEqual(report["status"], "interrupted_or_failed")
            self.assertFalse(report["is_model_quality_evidence"])
            self.assertEqual(report["summary"]["metrics"]["a_span"], evaluator.metric(1, 2))
            self.assertEqual(report["summary"]["metrics"]["b_is_credit_on_reference_known_actual_selection"], evaluator.metric(0, 1))
            self.assertEqual(report["summary"]["metrics"]["final_value_on_unique_target"], evaluator.metric(0, 2))
            self.assertEqual(report["summary"]["metrics"]["normalized_pair_on_reference_ready_target"], evaluator.metric(0, 2))
            rows = [json.loads(line) for line in (directory/"output/outcomes.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["status"], "pending")

    def test_failed_default_http_path_never_marks_model_quality_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); data, _, pinned = fixture_dataset(directory)
            failed = FixtureTransport((503, b"mocked outage"), (503, b"mocked outage"))
            with patch.object(evaluator, "MANIFEST_SHA256", pinned), patch.object(evaluator, "http_attempt", failed):
                report = evaluator.run_evaluation(data.parent, directory/"failed", **RUN_ARGS)
            self.assertEqual(report["evidence_kind"], "http_service_evaluation")
            self.assertEqual(report["status"], "completed_with_errors")
            self.assertIsNone(report["service_identity"])
            self.assertFalse(report["is_model_quality_evidence"])

    def test_postrun_artifact_change_invalidates_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); data, cases, pinned = fixture_dataset(directory)
            def changing_response(request):
                (data/"train.jsonl").write_bytes(b"changed during fixture")
                return reply(request, {"currency": "USD", "direction_known": 1.0, "is_credit": 0.0})
            wire = FixtureTransport(*(response for _ in cases for response in (
                lambda request: reply(request, {"span": "span_0", "target_present": 1.0}), changing_response)))
            with patch.object(evaluator, "MANIFEST_SHA256", pinned), self.assertRaisesRegex(ValueError, "artifact"):
                evaluator.run_evaluation(data.parent, directory/"output", transport=wire, **RUN_ARGS)
            report = json.loads((directory/"output/report.json").read_bytes())
            self.assertEqual(report["status"], "interrupted_or_failed")
            self.assertFalse(report["is_model_quality_evidence"])

    def test_outputs_cannot_overwrite_data_or_follow_output_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); data, _, _ = fixture_dataset(directory)
            alias = directory/"alias"; alias.symlink_to(data, target_is_directory=True)
            for output in (data/"new", data, alias, directory/"alias/new"):
                with self.subTest(output=output), self.assertRaisesRegex(ValueError, "output directory"):
                    evaluator.run_evaluation(data.parent, output, transport=FixtureTransport(), **RUN_ARGS)

    def test_invalid_identity_split_and_transport_flags_fail_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            for override in ({"expected_revision": "main"}, {"expected_checkpoint_sha256": None}, {"splits": ["train"]},
                             {"splits": ["test", "test"]}, {"endpoint": "http://user:secret@example.invalid/api"},
                             {"expected_temperature": True}, {"timeout": float("inf")}):
                with self.subTest(override=override), self.assertRaises(ValueError):
                    evaluator.run_evaluation(Path(temporary)/"data", Path(temporary)/"output", transport=FixtureTransport(), **{**RUN_ARGS, **override})


if __name__ == "__main__":
    unittest.main()
