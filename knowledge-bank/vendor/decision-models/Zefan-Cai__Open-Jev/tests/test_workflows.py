import copy
import json
from pathlib import Path
import tempfile
import unittest

from jev.api import candidate_prompts, compile_request
from jev.case_workflows import (build_dataset, counterfactuals, evaluate_predictions,
                                example_state, generate_cases)
from jev.data import SPLITS, read_jsonl, validate_records
from jev.workflows import (ACTION_RULES, gate_actions, policy_fixture_actions,
                           policy_fixture_response, select_actions, workflow_request)


class WorkflowTests(unittest.TestCase):
    def test_all_workflows_compile_as_target_free_independent_questions(self):
        for name in ACTION_RULES:
            request = workflow_request(name, example_state(name))
            records = compile_request(**request)
            self.assertEqual(len(records), len(ACTION_RULES[name]))
            self.assertTrue(all(row["kind"] == "noul" for row in records))
            for row in records:
                self.assertNotIn("target", row)
                text = candidate_prompts(row)[0]
                for forbidden in ("reference_actions", "reference_kind", "counterfactual_variant", "targets", "control_latents"):
                    self.assertNotIn(forbidden, text)

    def test_refund_requires_exact_account_object_amount_and_current_consent(self):
        original = example_state("customer_service", 0)
        self.assertIn("REFUND", policy_fixture_actions("customer_service", original))
        changes = [lambda s: s.update(consents=[]),
                   lambda s: s["identity"].update(account_id="different"),
                   lambda s: s["consents"][0].update(object_id="different"),
                   lambda s: s["consents"][0].update(amount_cents=s["pending_proposal"]["amount_cents"] - 1),
                   lambda s: s["consents"][0].update(status="pending"),
                   lambda s: s["consents"][0].update(proposal_id="old-proposal"),
                   lambda s: s["consents"][0].update(response_message_id="earlier-turn"),
                   lambda s: s["account"]["charges"][0].update(status="pending"),
                   lambda s: s["account"]["refunds"].append({"charge_id": s["pending_proposal"]["object_id"], "amount_cents": s["pending_proposal"]["amount_cents"], "status": "settled"})]
        for mutate in changes:
            state = copy.deepcopy(original)
            mutate(state)
            self.assertNotIn("REFUND", policy_fixture_actions("customer_service", state))
            decision = gate_actions("customer_service", state, ["SAY", "REFUND"])
            self.assertEqual(decision["allowed_actions"], ["SAY"])
            self.assertEqual(decision["blocked_actions"][0]["action"], "REFUND")
            self.assertFalse(decision["executed"])

    def test_card_and_cancellation_account_facts_gate_mutations(self):
        for scenario, action, collection in ((1, "FREEZE CARD", "cards"), (2, "CANCEL", "subscription")):
            state = example_state("customer_service", scenario)
            self.assertIn(action, policy_fixture_actions("customer_service", state))
            if collection == "cards":
                state["account"][collection][0]["status"] = "frozen"
            else:
                state["account"][collection]["status"] = "cancelled"
            self.assertNotIn(action, gate_actions("customer_service", state, [action])["allowed_actions"])

    def test_customer_empty_resolved_negation_and_account_claim_conflict(self):
        self.assertEqual(policy_fixture_actions("customer_service", example_state("customer_service", 6)), [])
        self.assertEqual(policy_fixture_actions("customer_service", example_state("customer_service", 5)), ["CLOSE"])
        self.assertNotIn("REFUND", policy_fixture_actions("customer_service", example_state("customer_service", 7)))
        self.assertIn("FLAG FOR REVIEW", policy_fixture_actions("customer_service", example_state("customer_service", 11)))
        self.assertNotEqual(policy_fixture_actions("customer_service", example_state("customer_service", 0)), ["REFUND"])

    def test_security_priority_grant_expiry_and_production_isolation(self):
        state = example_state("security_incidents", 12)
        self.assertEqual(policy_fixture_actions("security_incidents", state), ["ISOLATE HOST"])
        state["asset"].update(environment="production", redundancy="single")
        self.assertEqual(policy_fixture_actions("security_incidents", state), ["KILL PROCESS"])
        state["events"].append({"asset_id": state["asset"]["id"], "kind": "connection", "status": "active", "destination_reputation": "malicious", "reach": "organization"})
        self.assertEqual(policy_fixture_actions("security_incidents", state), ["BLOCK DESTINATION"])
        self.assertEqual(gate_actions("security_incidents", state, ["KILL PROCESS"])["allowed_actions"], [])
        state["responder_grants"][0]["valid_to_day"] = state["alert"]["day"] - 1
        self.assertEqual(policy_fixture_actions("security_incidents", state), ["ESCALATE URGENT"])
        self.assertEqual(gate_actions("security_incidents", state, ["BLOCK DESTINATION"])["allowed_actions"], [])

    def test_security_maintenance_must_match_asset_activity_and_time(self):
        original = example_state("security_incidents", 0)
        self.assertEqual(policy_fixture_actions("security_incidents", original), ["AUTO CLOSE"])
        for key, value in (("asset_id", "another-asset"), ("activity", "another-activity"), ("end_day", original["alert"]["day"] - 1)):
            state = copy.deepcopy(original)
            state["maintenance"][0][key] = value
            self.assertEqual(policy_fixture_actions("security_incidents", state), ["ESCALATE TIER2"])

    def test_agent_permission_is_evaluated_at_call_time_with_exact_scope(self):
        original = example_state("agent_trace_observability", 0)
        self.assertEqual(policy_fixture_actions("agent_trace_observability", original), ["AUTO-CLOSE"])
        for key, value in (("approved_at", original["tool_calls"][0]["started_at"] + 1), ("resource", "another-resource"), ("tool", "different-tool"), ("status", "pending")):
            state = copy.deepcopy(original)
            state["permission_grants"][0][key] = value
            self.assertEqual(policy_fixture_actions("agent_trace_observability", state), ["PAGE ON-CALL"])
        for scenario, action in ((1, "NOT A BUG"), (2, "HUMAN REVIEW"), (3, "PRIORITY REVIEW"), (4, "FILE ISSUE · ROUTE"), (6, "COUNT ONLY")):
            self.assertEqual(policy_fixture_actions("agent_trace_observability", example_state("agent_trace_observability", scenario)), [action])

    def test_invoice_financial_boundaries_and_grants(self):
        original = example_state("invoice_processing", 0)
        self.assertEqual(policy_fixture_actions("invoice_processing", original), ["PAY"])
        self.assertEqual(policy_fixture_actions("invoice_processing", example_state("invoice_processing", 1)), ["SCHEDULE"])
        self.assertEqual(policy_fixture_actions("invoice_processing", example_state("invoice_processing", 2)), ["SHORT PAY"])
        changes = [lambda s: s.update(approvals=[]),
                   lambda s: s["approvals"][0].update(max_amount_cents=s["invoice"]["quantity"] * s["invoice"]["unit_price_cents"] - 1),
                   lambda s: s["approvals"][0].update(vendor_id="another-vendor"),
                   lambda s: s["approvals"][0].update(approved_at_day=s["today"] + 1),
                   lambda s: s["approvals"][0].update(valid_until_day=s["today"] - 1),
                   lambda s: s["invoice"].update(payment_account="new-unverified-account"),
                   lambda s: s["invoice"].update(quantity=True),
                   lambda s: s["prior_invoices"].append({"vendor_id": s["invoice"]["vendor_id"], "invoice_number": s["invoice"]["number"], "status": "paid"})]
        for mutate in changes:
            state = copy.deepcopy(original)
            mutate(state)
            self.assertNotIn("PAY", policy_fixture_actions("invoice_processing", state))
            self.assertEqual(gate_actions("invoice_processing", state, ["PAY"])["allowed_actions"], [])

    def test_exclusive_workflows_use_one_disposition_while_customer_can_fan_out(self):
        for name in ("security_incidents", "agent_trace_observability"):
            response = {"answers": {action: {"type": "noul", "noul": 0.8} for action in ACTION_RULES[name]}}
            self.assertEqual(len(select_actions(name, response)), 1)
        name = "customer_service"
        self.assertGreater(len(select_actions(name, policy_fixture_response(name, example_state(name)))), 1)
        with self.assertRaises(ValueError):
            select_actions(name, {"answers": {}}, threshold=float("nan"))

    def test_generated_groups_stay_together_and_models_cannot_see_references(self):
        cases = list(generate_cases(80, 11))
        self.assertEqual(cases, list(generate_cases(80, 11)))
        self.assertEqual(validate_records(row for _, rows in cases for row in rows)["groups"], 320)
        all_positive = set()
        for case, rows in cases:
            all_positive.update((case["workflow"], action) for action in case["reference_actions"])
            compiled = compile_request(case["state"], case["questions"])
            for record, row in zip(compiled, rows):
                self.assertEqual([record[k] for k in ("state", "question", "kind", "options")], [row[k] for k in ("state", "question", "kind", "options")])
                self.assertEqual(row["target"], case["targets"][record["id"]])
                self.assertNotIn("reference_actions", candidate_prompts(row)[0])
            self.assertEqual(select_actions(case["workflow"], policy_fixture_response(case["workflow"], case["state"])), case["reference_actions"])
        self.assertEqual(all_positive, {(name, action) for name, actions in ACTION_RULES.items() for action in actions})

    def test_manifest_and_saved_jsonl_are_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = build_dataset(temporary, 20, 123)
            self.assertEqual(first, build_dataset(temporary, 20, 123))
            self.assertEqual(first["official_examples_used"], 0)
            rows = [row for split in SPLITS for row in read_jsonl(Path(temporary) / f"{split}.jsonl")]
            self.assertEqual(validate_records(rows), first["summary"])
            self.assertEqual(len(list(read_jsonl(Path(temporary) / "workflow_cases.jsonl"))), 240)

    def test_evaluation_rejects_fixture_claims_and_bad_case_alignment(self):
        case, _ = next(generate_cases(1))
        predicted = {"case_id": case["case_id"], "predictor_kind": "policy_fixture_oracle", "response": policy_fixture_response(case["workflow"], case["state"])}
        with self.assertRaises(ValueError):
            evaluate_predictions([case], [predicted])
        predicted["predictor_kind"] = "learned"  # Test-only simulated predictor output.
        report = evaluate_predictions([case], [predicted])
        self.assertEqual(report["overall"]["raw_exact_match"], 1.0)
        with self.assertRaises(ValueError):
            evaluate_predictions([case], [predicted, predicted])
        with self.assertRaises(ValueError):
            evaluate_predictions([case], [])


class WorkflowServiceEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = [case for case, _ in generate_cases(80, 42)]

    def test_selection_is_heldout_balanced_group_distinct_and_label_independent(self):
        from collections import Counter
        from scripts.evaluate_workflow_service import select_cases
        chosen = select_cases(self.cases, ("test", "ood"), 2, 19)
        self.assertEqual(len(chosen), 16)
        self.assertEqual(len({case["group_id"] for case in chosen}), 16)
        self.assertEqual(Counter((case["workflow"], case["split"]) for case in chosen),
                         {(workflow, split): 2 for workflow in ACTION_RULES for split in ("test", "ood")})
        self.assertEqual([case["case_id"] for case in chosen],
                         [case["case_id"] for case in select_cases(list(reversed(self.cases)), ("test", "ood"), 2, 19)])
        changed_labels = [{**case, "reference_actions": [], "targets": {}} for case in self.cases]
        self.assertEqual([case["case_id"] for case in chosen],
                         [case["case_id"] for case in select_cases(changed_labels, ("test", "ood"), 2, 19)])
        with self.assertRaises(ValueError):
            select_cases(self.cases, ("train",), 1)
        with self.assertRaises(ValueError):
            select_cases(self.cases, ("test",), 1000)

    def test_selection_rejects_cross_split_parent_groups_and_duplicate_ids(self):
        from scripts.evaluate_workflow_service import select_cases
        duplicate = copy.deepcopy(self.cases[0])
        with self.assertRaises(ValueError):
            select_cases([*self.cases, duplicate], per_workflow=1)
        duplicate["case_id"] += ":another-id"
        duplicate["split"] = "test" if duplicate["split"] != "test" else "ood"
        with self.assertRaises(ValueError):
            select_cases([*self.cases, duplicate], per_workflow=1)
        duplicate["group_id"] += ":renamed-group"
        with self.assertRaisesRegex(ValueError, "model input crosses splits"):
            select_cases([*self.cases, duplicate], per_workflow=1)

    def test_prediction_identity_binds_case_state_questions_and_split(self):
        from scripts.evaluate_workflow_service import case_identity, validate_prediction_identities
        case = self.cases[0]
        prediction = case_identity(case)
        validate_prediction_identities([case], [prediction])
        for key in ("case_id", "group_id", "workflow", "split", "state_sha256", "questions_sha256", "request_sha256"):
            with self.assertRaises(ValueError, msg=key):
                validate_prediction_identities([case], [{**prediction, key: "wrong"}])
        with self.assertRaises(ValueError):
            validate_prediction_identities([case], [prediction, prediction])

    def test_service_identity_rejects_oracle_mismatch_and_tracks_artifact_digest(self):
        from scripts.evaluate_workflow_service import response_identity
        case = self.cases[0]
        # Synthetic test response only; no quality result is reported.
        response = {"model": "Qwen/test", "answers": {action: {"type": "noul", "noul": 0.4} for action in case["questions"]},
                    "metadata": {"method": "lora_decision_head", "temperature": 1.0,
                                 "candidate_sequences": len(case["questions"]), "checkpoint_sha256": "a" * 64,
                                 "base_revision": "b" * 40, "code_commit": "c" * 40}}
        identity = response_identity(case, response, expected_model="Qwen/test", expected_method="lora_decision_head")
        self.assertEqual(identity["checkpoint_sha256"], "a" * 64)
        with self.assertRaises(ValueError):
            response_identity(case, response, expected_model="another-model")
        for field, value in (("method", "policy_fixture_oracle"), ("temperature", float("nan")),
                             ("checkpoint_sha256", "not-a-digest"), ("candidate_sequences", 1)):
            altered = copy.deepcopy(response)
            altered["metadata"][field] = value
            with self.assertRaises(ValueError, msg=field):
                response_identity(case, altered)
        altered = copy.deepcopy(response)
        altered["answers"].pop(next(iter(altered["answers"])))
        with self.assertRaises(ValueError):
            response_identity(case, altered)

    def test_http_runner_preserves_responses_and_aborts_on_service_change(self):
        from scripts.evaluate_workflow_service import run_evaluation

        class TestClient:
            count = 0

            def ask(self, state, questions, model):
                self.count += 1
                return {"model": "Qwen/test", "answers": {action: {"type": "noul", "noul": 0.4} for action in questions},
                        "metadata": {"method": "lora_decision_head", "temperature": 1.0,
                                     "candidate_sequences": len(questions), "checkpoint_sha256": ("a" if self.count == 1 else "b") * 64}}

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "cases.jsonl"
            source.write_text("".join(json.dumps(case) + "\n" for case in self.cases))
            output = Path(temporary) / "evaluation"
            with self.assertRaisesRegex(ValueError, "identity changed"):
                run_evaluation(source, output, splits=("test",), per_workflow=1, client=TestClient())
            self.assertEqual(len(list(read_jsonl(output / "responses.jsonl"))), 2)
            self.assertEqual(len(list(read_jsonl(output / "predictions.jsonl"))), 1)
            self.assertFalse((output / "report.json").exists())
            self.assertEqual(json.loads((output / "failure.json").read_text())["completed_cases"], 1)


if __name__ == "__main__":
    unittest.main()
