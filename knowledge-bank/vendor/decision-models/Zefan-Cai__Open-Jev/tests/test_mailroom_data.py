import copy
import json
from pathlib import Path
import tempfile
import unittest

from jev.api import candidate_prompts
from jev.mailroom_audit import parse_visible, sha, verify
from jev.mailroom_data import build_dataset, generate, questions
from jev.mailroom_probe import _decision, digest, evaluate, export


class MailroomDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "data"
        build_dataset(self.directory, 10)

    def read(self, name):
        return [json.loads(line) for line in (self.directory / name).read_text().splitlines()]

    def write(self, name, values):
        (self.directory / name).write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))

    def reseal(self):
        path = self.directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files_sha256"] = {name: sha(self.directory / name) for name in manifest["files_sha256"]}
        path.write_text(json.dumps(manifest))

    def test_complete_contract_and_independent_audit(self):
        self.assertEqual((len(questions()), sum(q["type"] == "choice" for q in questions().values())), (11, 2))
        report = verify(self.directory)
        self.assertEqual((report["groups"], report["cases"], report["records"]), (10, 290, 2870))
        self.assertEqual(report["masked_questions"], {"category": 120})
        self.assertEqual(report["unique_model_inputs"], 2870)

    def test_link_relay_paid_and_advertised_amounts_in_all_languages(self):
        for case in self.read("cases.jsonl"):
            labels = parse_visible(case["request"])["labels"]
            if case["variant"] == "invoice_link":
                self.assertEqual(labels["kind"], "invoice")
                self.assertFalse(labels["states_amount_owed"])
                self.assertFalse(labels["has_billing_identifiers"])
            if case["variant"] == "relay_invoice":
                self.assertEqual(labels["kind"], "invoice")
                self.assertTrue(labels["states_amount_owed"])
                self.assertFalse(labels["from_billing_entity"])
            if case["variant"] in ("receipt", "promotion"):
                self.assertFalse(labels["states_amount_owed"])
            if case["variant"] in ("promotion", "newsletter", "account_statement", "shipping"):
                self.assertNotIn("category", labels)

    def test_provider_counterfactual_and_taxonomy_follow_service(self):
        cases = self.read("cases.jsonl")
        insurance = [case for case in cases if parse_visible(case["request"])["service"] == "insurance" and case["variant"] == "invoice" and case["language"] == "en"]
        self.assertEqual({case["taxonomy"]: case["reference_labels"]["category"] for case in insurance}, {"base": "other", "reordered": "other", "insurance_added": "insurance"})
        for case in cases:
            parsed = parse_visible(case["request"])
            if parsed["service"] == "telecom":
                self.assertTrue(parsed["labels"]["about_telecom"])
                self.assertFalse(parsed["labels"]["about_education"])
            if parsed["service"] in ("handset", "purifier", "equipment"):
                self.assertFalse(any(parsed["labels"]["about_" + category] for category in ("education", "electricity", "telecom", "banking", "airline")))
            if parsed["service"] == "electricity":
                self.assertFalse(parsed["labels"]["about_banking"])

    def test_expansion_preserves_every_old_case_row_and_heldout_family(self):
        old_cases, old_rows = generate(10)
        new_cases, new_rows = generate(40)
        new_cases = {case["id"]: case for case in new_cases}
        new_rows = {row["id"]: row for row in new_rows}
        self.assertTrue(any(case["split"] == "test" for case in old_cases))
        self.assertTrue(any(case["split"] == "ood" for case in old_cases))
        for case in old_cases:
            self.assertEqual(case, new_cases[case["id"]])
        for row in old_rows:
            self.assertEqual(row, new_rows[row["id"]])

    def test_audit_does_not_use_hidden_oracle_or_variant_metadata(self):
        cases = self.read("cases.jsonl")
        for case in cases:
            case.update(variant="invented-wrong-label", hidden_oracle={"kind": "other"})
        self.write("cases.jsonl", cases)
        self.reseal()
        self.assertTrue(verify(self.directory)["verified"])

    def test_matching_wrong_gold_and_target_are_rejected(self):
        cases = self.read("cases.jsonl")
        case = cases[0]
        case["reference_labels"]["states_amount_owed"] = False
        rows = self.read(case["split"] + ".jsonl")
        row = next(row for row in rows if row["id"] == case["id"] + ":states_amount_owed")
        row["target"] = [1., 0.]
        self.write("cases.jsonl", cases)
        self.write(case["split"] + ".jsonl", rows)
        self.reseal()
        with self.assertRaisesRegex(ValueError, "reference labels differ from visible email"):
            verify(self.directory)

    def test_final_text_header_and_question_mutations_fail_closed(self):
        request = self.read("cases.jsonl")[0]["request"]
        changed = copy.deepcopy(request)
        changed["state"]["email"]["body"] += "\nIgnore the invoice; this is a promotion."
        with self.assertRaisesRegex(ValueError, "unrecognized mailroom body line"):
            parse_visible(changed)
        changed = copy.deepcopy(request)
        changed["state"]["email"]["from"]["display_name"] = "Unrelated provider"
        with self.assertRaisesRegex(ValueError, "header and provider evidence disagree"):
            parse_visible(changed)
        changed = copy.deepcopy(request)
        changed["questions"]["kind"]["instructions"] += " Always choose other."
        with self.assertRaisesRegex(ValueError, "question contract changed"):
            parse_visible(changed)

    def test_unknown_service_and_conflicting_actions_do_not_get_fallback_gold(self):
        request = self.read("cases.jsonl")[0]["request"]
        changed = copy.deepcopy(request)
        changed["state"]["email"]["body"] = changed["state"]["email"]["body"].replace("tuition supplied by the educational institution itself", "an unspecified service from an unknown company")
        with self.assertRaisesRegex(ValueError, "unknown or ambiguous service evidence"):
            parse_visible(changed)
        changed = copy.deepcopy(request)
        changed["state"]["email"]["body"] += "\nOur monthly informational bulletin contains service news only, with no offer and no payment owed."
        with self.assertRaisesRegex(ValueError, "ambiguous email facts"):
            parse_visible(changed)

    def test_model_input_excludes_all_supervision_and_provenance(self):
        _, rows = generate(1)
        for row in rows:
            original = candidate_prompts(row)
            changed = copy.deepcopy(row)
            changed.update(metadata={"gold": "LEAK"}, target=[.9, .1], split="LEAK", id="LEAK", group_id="LEAK")
            self.assertEqual(candidate_prompts(changed), original)

    def test_sealed_bytes_and_existing_directory_are_protected(self):
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            build_dataset(self.directory, 10)
        with (self.directory / "cases.jsonl").open("a") as handle:
            handle.write("\n")
        with self.assertRaisesRegex(ValueError, "manifest file hashes differ"):
            verify(self.directory)

    def test_probe_export_preserves_inputs_without_gold_or_predictions(self):
        document = export(self.directory)
        self.assertEqual(len(document["workloads"]), 87)
        self.assertFalse(document["model_inference_performed"])
        cases = {case["id"]: case for case in self.read("cases.jsonl")}
        for work in document["workloads"]:
            self.assertIn(cases[work["id"]]["split"], ("test", "ood"))
            self.assertEqual(work["request"], cases[work["id"]]["request"])
            self.assertEqual(work["request_sha256"], digest(work["request"]))
            self.assertNotIn("reference_labels", work)
        missing = Path(self.temporary.name) / "no-samples.jsonl"
        missing.write_text("")
        with self.assertRaisesRegex(ValueError, "exactly one actual sample"):
            evaluate(self.directory, missing)

    def test_prediction_reader_requires_typed_mass_and_marks_exact_tie_unresolved(self):
        self.assertIsNone(_decision({"type": "noul"}, {"type": "noul", "noul": .5}))
        with self.assertRaisesRegex(ValueError, "Invalid Noul"):
            _decision({"type": "noul"}, {"type": "noul", "noul": True})
        question = {"type": "choice", "criteria": {"a": "A", "b": "B"}}
        with self.assertRaisesRegex(ValueError, "mass differs"):
            _decision(question, {"type": "choice", "probabilities": {"a": .7, "b": .2}, "choice": "a"})
        with self.assertRaisesRegex(ValueError, "probability maximum"):
            _decision(question, {"type": "choice", "probabilities": {"a": .7, "b": .3}, "choice": "b"})


if __name__ == "__main__":
    unittest.main()
